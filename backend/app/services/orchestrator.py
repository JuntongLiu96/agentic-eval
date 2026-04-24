import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, AsyncGenerator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.bridge.registry import create_adapter
from app.models.adapter import Adapter
from app.models.dataset import TestCase
from app.models.eval_result import EvalResult
from app.models.eval_run import EvalRun, RunStatus
from app.models.scorer import Scorer
from app.services.aggregator import aggregate_run_results, multi_round_summary
from app.services.judge import assemble_judge_prompt, parse_judge_response, resolve_judge_llm
from app.services.turns import parse_turns
from app.bridge.base import AgentResult

logger = logging.getLogger(__name__)


async def _run_judge(
    judge_client: Any, scorer: Scorer, expected: Any,
    agent_messages: list, sub_agent_messages: list | None,
) -> dict[str, Any]:
    """Assemble judge prompt, call LLM, parse response."""
    judge_messages = assemble_judge_prompt(
        eval_prompt=scorer.eval_prompt, expected_result=expected,
        agent_messages=agent_messages,
        sub_agent_messages=sub_agent_messages or None,
    )
    judge_response = await judge_client.chat(judge_messages)
    return parse_judge_response(judge_response, scorer.pass_threshold)


def _build_all_messages(agent_result: Any) -> Any:
    """Build the stored messages object from agent result."""
    if agent_result.sub_agent_messages:
        return {"main": agent_result.messages, "sub_agents": agent_result.sub_agent_messages}
    return agent_result.messages


async def run_eval(run_id: int, db: AsyncSession) -> AsyncGenerator[dict[str, Any], None]:
    run = await db.get(EvalRun, run_id)
    if not run:
        yield {"type": "error", "message": "Run not found"}; return
    scorer = await db.get(Scorer, run.scorer_id)
    if not scorer:
        yield {"type": "error", "message": "Scorer not found"}; return
    adapter_row = await db.get(Adapter, run.adapter_id)
    if not adapter_row:
        yield {"type": "error", "message": "Adapter not found"}; return
    result = await db.execute(select(TestCase).where(TestCase.dataset_id == run.dataset_id))
    test_cases = result.scalars().all()
    if not test_cases:
        yield {"type": "error", "message": "Dataset has no test cases"}; return

    judge_config = json.loads(run.judge_config) if isinstance(run.judge_config, str) else run.judge_config
    adapter_config = json.loads(adapter_row.config) if isinstance(adapter_row.config, str) else adapter_row.config
    num_rounds = run.num_rounds
    round_mode = run.round_mode

    bridge = create_adapter(adapter_row.adapter_type)
    try:
        await bridge.connect(adapter_config)
    except Exception as e:
        run.status = RunStatus.failed; await db.commit()
        yield {"type": "error", "message": f"Failed to connect adapter: {e}"}; return

    try:
        try:
            adapter_llm = await bridge.get_judge_llm()
            judge_client = resolve_judge_llm(judge_config, adapter_llm)
        except Exception as e:
            run.status = RunStatus.failed
            run.finished_at = datetime.now(timezone.utc)
            await db.commit()
            yield {"type": "error", "message": str(e)}
            return

        run.status = RunStatus.running
        run.started_at = datetime.now(timezone.utc)
        await db.commit()
        total_cases = len(test_cases)
        logger.info(f"Run #{run_id} started: {total_cases} cases x {num_rounds} rounds ({round_mode} mode)")
        yield {"type": "run_started", "run_id": run_id, "total_cases": total_cases,
               "num_rounds": num_rounds, "round_mode": round_mode}

        try:
            if round_mode == "scorer":
                async for event in _run_scorer_mode(run, scorer, bridge, judge_client, test_cases, num_rounds, db):
                    yield event
            else:
                async for event in _run_agent_mode(run, scorer, bridge, judge_client, test_cases, num_rounds, db):
                    yield event
        except Exception as e:
            logger.exception(f"Run #{run_id} failed during evaluation: {e}")
            run.status = RunStatus.failed
            run.finished_at = datetime.now(timezone.utc)
            await db.commit()
            yield {"type": "error", "message": f"Run failed: {e}"}
            return

        run.status = RunStatus.completed
        run.finished_at = datetime.now(timezone.utc)
        await db.commit()

        if num_rounds > 1:
            pass_threshold = scorer.pass_threshold if scorer.pass_threshold is not None else 60.0
            summary = await multi_round_summary(run_id, num_rounds, round_mode, pass_threshold, db)
        else:
            summary = await aggregate_run_results(run_id, db)
        yield {"type": "run_completed", "run_id": run_id, "summary": summary}
    finally:
        try:
            await bridge.disconnect()
        except Exception as e:
            logger.warning(f"Run #{run_id}: bridge.disconnect() raised: {e}")


async def _run_agent_mode(
    run: EvalRun, scorer: Scorer, bridge: Any, judge_client: Any,
    test_cases: list, num_rounds: int, db: AsyncSession,
) -> AsyncGenerator[dict[str, Any], None]:
    """Agent mode: re-run full agent + judge pipeline each round."""
    for rnd in range(1, num_rounds + 1):
        yield {"type": "round_started", "round": rnd, "total_rounds": num_rounds}
        for i, tc in enumerate(test_cases):
            async for event in _eval_single_case(
                run, scorer, bridge, judge_client, tc, i, len(test_cases), rnd, num_rounds,
                run_agent=True, cached_agent_result=None, db=db,
            ):
                yield event
        yield {"type": "round_completed", "round": rnd}


async def _run_scorer_mode(
    run: EvalRun, scorer: Scorer, bridge: Any, judge_client: Any,
    test_cases: list, num_rounds: int, db: AsyncSession,
) -> AsyncGenerator[dict[str, Any], None]:
    """Scorer mode: run agent once (round 0), then judge N times."""
    # Phase 1: Run agent for all test cases
    yield {"type": "round_started", "round": 0, "total_rounds": num_rounds, "phase": "agent_run"}
    cached_results: dict[int, Any] = {}
    for i, tc in enumerate(test_cases):
        test_data = json.loads(tc.data) if isinstance(tc.data, str) else tc.data
        yield {"type": "case_started", "round": 0, "case_index": i, "case_name": tc.name,
               "total_cases": len(test_cases)}
        start_time = time.monotonic()

        try:
            turns = parse_turns(test_data)
        except ValueError as e:
            yield {"type": "case_completed", "round": 0, "case_index": i, "case_name": tc.name,
                   "success": False, "error": str(e)}
            continue

        session_id = None
        all_messages = []
        all_sub_messages = []
        turn_results_list = []
        agent_failed = False

        for turn_index, turn in enumerate(turns):
            agent_result = await bridge.send_test({"prompt": turn["prompt"]}, session_id=session_id)
            if not agent_result.success:
                agent_failed = True
                break
            if session_id is None and agent_result.metadata.get("session_id"):
                session_id = agent_result.metadata["session_id"]
            all_messages.extend(agent_result.messages)
            all_sub_messages.extend(agent_result.sub_agent_messages)

        duration = int((time.monotonic() - start_time) * 1000)

        if agent_failed:
            cached_results[tc.id] = {"result": agent_result, "duration_ms": duration, "turn_results": []}
        else:
            combined = AgentResult(
                messages=all_messages,
                sub_agent_messages=all_sub_messages,
                metadata=agent_result.metadata if turns else {},
                success=True,
            )
            cached_results[tc.id] = {"result": combined, "duration_ms": duration, "turn_results": turn_results_list}

        yield {"type": "case_completed", "round": 0, "case_index": i, "case_name": tc.name,
               "success": not agent_failed}
    yield {"type": "round_completed", "round": 0}

    # Phase 2: Judge N times
    for rnd in range(1, num_rounds + 1):
        yield {"type": "round_started", "round": rnd, "total_rounds": num_rounds}
        for i, tc in enumerate(test_cases):
            cached = cached_results.get(tc.id)
            async for event in _eval_single_case(
                run, scorer, bridge, judge_client, tc, i, len(test_cases), rnd, num_rounds,
                run_agent=False, cached_agent_result=cached, db=db,
            ):
                yield event
        yield {"type": "round_completed", "round": rnd}


async def _eval_single_case(
    run: EvalRun, scorer: Scorer, bridge: Any, judge_client: Any,
    tc: Any, case_index: int, total_cases: int, round_number: int, total_rounds: int,
    run_agent: bool, cached_agent_result: dict | None, db: AsyncSession,
) -> AsyncGenerator[dict[str, Any], None]:
    """Evaluate a single test case (single-turn or multi-turn) for a single round."""
    test_data = json.loads(tc.data) if isinstance(tc.data, str) else tc.data
    expected = json.loads(tc.expected_result) if isinstance(tc.expected_result, str) else tc.expected_result

    logger.info(f"Run #{run.id} round {round_number} case {case_index + 1}/{total_cases}: {tc.name}")
    yield {"type": "case_started", "round": round_number, "case_index": case_index,
           "case_name": tc.name, "total_cases": total_cases}

    start_time = time.monotonic()

    if run_agent:
        try:
            turns = parse_turns(test_data)
        except ValueError as e:
            eval_result = EvalResult(
                run_id=run.id, test_case_id=tc.id, round_number=round_number,
                agent_messages=json.dumps([]), score=json.dumps({}),
                judge_reasoning=f"Invalid test data: {e}", passed=False, duration_ms=0,
            )
            db.add(eval_result); await db.commit()
            yield {"type": "case_completed", "round": round_number, "case_name": tc.name,
                   "passed": False, "error": str(e)}
            return

        session_id = None
        all_messages = []
        all_sub_messages = []
        turn_results_list = []

        logger.info(f"Run #{run.id} case {tc.name}: {len(turns)} turns to execute")

        for turn_index, turn in enumerate(turns):
            logger.info(f"Run #{run.id} case {tc.name}: sending turn {turn_index + 1}/{len(turns)} "
                        f"(session_id={session_id})")
            agent_result = await bridge.send_test({"prompt": turn["prompt"]}, session_id=session_id)

            if not agent_result.success:
                logger.warning(f"Run #{run.id} round {round_number} case {tc.name} turn {turn_index}: "
                               f"agent failed — {agent_result.error}")
                eval_result = EvalResult(
                    run_id=run.id, test_case_id=tc.id, round_number=round_number,
                    agent_messages=json.dumps(all_messages), score=json.dumps({}),
                    judge_reasoning=f"Agent error at turn {turn_index}: {agent_result.error}",
                    passed=False, duration_ms=int((time.monotonic() - start_time) * 1000),
                    turn_results=json.dumps(turn_results_list) if turn_results_list else None,
                )
                db.add(eval_result); await db.commit()
                yield {"type": "case_completed", "round": round_number, "case_name": tc.name,
                       "passed": False, "error": agent_result.error}
                return

            if session_id is None and agent_result.metadata.get("session_id"):
                session_id = agent_result.metadata["session_id"]
                logger.info(f"Run #{run.id} case {tc.name}: captured session_id={session_id}")

            all_messages.extend(agent_result.messages)
            all_sub_messages.extend(agent_result.sub_agent_messages)
            logger.info(f"Run #{run.id} case {tc.name}: turn {turn_index} returned "
                        f"{len(agent_result.messages)} messages (total accumulated: {len(all_messages)})")

            if "expected_result" in turn:
                try:
                    turn_parsed = await _run_judge(
                        judge_client, scorer, turn["expected_result"],
                        all_messages, all_sub_messages or None,
                    )
                    turn_results_list.append({
                        "turn_index": turn_index,
                        "score": turn_parsed["score"],
                        "passed": turn_parsed["passed"],
                        "justification": turn_parsed["justification"],
                    })
                except Exception as e:
                    logger.error(f"Run #{run.id} round {round_number} case {tc.name} "
                                 f"turn {turn_index}: judge error — {e}")
                    turn_results_list.append({
                        "turn_index": turn_index,
                        "score": 0,
                        "passed": False,
                        "justification": f"Judge error: {e}",
                    })

            yield {"type": "turn_completed", "round": round_number, "case_name": tc.name,
                   "turn_index": turn_index, "total_turns": len(turns),
                   "turn_score": turn_results_list[-1] if turn_results_list and turn_results_list[-1]["turn_index"] == turn_index else None}

        agent_duration = int((time.monotonic() - start_time) * 1000)

        class _FinalResult:
            messages = all_messages
            sub_agent_messages = all_sub_messages
            success = True
        final_result = _FinalResult()
    else:
        if cached_agent_result is None:
            eval_result = EvalResult(
                run_id=run.id, test_case_id=tc.id, round_number=round_number,
                agent_messages=json.dumps([]), score=json.dumps({}),
                judge_reasoning="No cached agent result", passed=False, duration_ms=0,
            )
            db.add(eval_result); await db.commit()
            yield {"type": "case_completed", "round": round_number, "case_name": tc.name,
                   "passed": False, "error": "No cached agent result"}
            return
        final_result = cached_agent_result["result"]
        agent_duration = cached_agent_result["duration_ms"]
        all_messages = final_result.messages
        all_sub_messages = final_result.sub_agent_messages if hasattr(final_result, 'sub_agent_messages') else []
        turn_results_list = cached_agent_result.get("turn_results", [])

    try:
        parsed = await _run_judge(judge_client, scorer, expected,
                                   all_messages, all_sub_messages or None)
        logger.info(f"Run #{run.id} round {round_number} case {tc.name}: "
                     f"score={parsed['score']}, passed={parsed['passed']}")
        all_msg_obj = _build_all_messages(final_result)
        total_duration = int((time.monotonic() - start_time) * 1000) if run_agent else agent_duration
        eval_result = EvalResult(
            run_id=run.id, test_case_id=tc.id, round_number=round_number,
            agent_messages=json.dumps(all_msg_obj), score=json.dumps(parsed["score"]),
            judge_reasoning=parsed["justification"], passed=parsed["passed"],
            duration_ms=total_duration,
            turn_results=json.dumps(turn_results_list) if turn_results_list else None,
        )
    except Exception as e:
        logger.error(f"Run #{run.id} round {round_number} case {tc.name}: judge error — {e}")
        eval_result = EvalResult(
            run_id=run.id, test_case_id=tc.id, round_number=round_number,
            agent_messages=json.dumps(all_messages), score=json.dumps({}),
            judge_reasoning=f"Judge error: {e}", passed=False,
            duration_ms=int((time.monotonic() - start_time) * 1000),
            turn_results=json.dumps(turn_results_list) if turn_results_list else None,
        )

    db.add(eval_result); await db.commit()
    yield {"type": "case_completed", "round": round_number, "case_index": case_index,
           "case_name": tc.name, "passed": eval_result.passed,
           "justification": eval_result.judge_reasoning}
