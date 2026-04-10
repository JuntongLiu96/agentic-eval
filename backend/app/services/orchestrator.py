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
        adapter_llm = await bridge.get_judge_llm()
        judge_client = resolve_judge_llm(judge_config, adapter_llm)
    except ValueError as e:
        run.status = RunStatus.failed; await db.commit(); await bridge.disconnect()
        yield {"type": "error", "message": str(e)}; return

    run.status = RunStatus.running
    run.started_at = datetime.now(timezone.utc)
    await db.commit()
    total_cases = len(test_cases)
    logger.info(f"Run #{run_id} started: {total_cases} cases x {num_rounds} rounds ({round_mode} mode)")
    yield {"type": "run_started", "run_id": run_id, "total_cases": total_cases,
           "num_rounds": num_rounds, "round_mode": round_mode}

    if round_mode == "scorer":
        async for event in _run_scorer_mode(run, scorer, bridge, judge_client, test_cases, num_rounds, db):
            yield event
    else:
        async for event in _run_agent_mode(run, scorer, bridge, judge_client, test_cases, num_rounds, db):
            yield event

    await bridge.disconnect()
    run.status = RunStatus.completed
    run.finished_at = datetime.now(timezone.utc)
    await db.commit()

    if num_rounds > 1:
        pass_threshold = scorer.pass_threshold if scorer.pass_threshold is not None else 60.0
        summary = await multi_round_summary(run_id, num_rounds, round_mode, pass_threshold, db)
    else:
        summary = await aggregate_run_results(run_id, db)
    yield {"type": "run_completed", "run_id": run_id, "summary": summary}


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
        agent_result = await bridge.send_test(test_data)
        duration = int((time.monotonic() - start_time) * 1000)
        cached_results[tc.id] = {"result": agent_result, "duration_ms": duration}
        yield {"type": "case_completed", "round": 0, "case_index": i, "case_name": tc.name,
               "success": agent_result.success}
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
    """Evaluate a single test case for a single round."""
    test_data = json.loads(tc.data) if isinstance(tc.data, str) else tc.data
    expected = json.loads(tc.expected_result) if isinstance(tc.expected_result, str) else tc.expected_result

    logger.info(f"Run #{run.id} round {round_number} case {case_index + 1}/{total_cases}: {tc.name}")
    yield {"type": "case_started", "round": round_number, "case_index": case_index,
           "case_name": tc.name, "total_cases": total_cases}

    start_time = time.monotonic()

    if run_agent:
        agent_result = await bridge.send_test(test_data)
        agent_duration = int((time.monotonic() - start_time) * 1000)
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
        agent_result = cached_agent_result["result"]
        agent_duration = cached_agent_result["duration_ms"]

    if not agent_result.success:
        logger.warning(f"Run #{run.id} round {round_number} case {tc.name}: agent failed — {agent_result.error}")
        eval_result = EvalResult(
            run_id=run.id, test_case_id=tc.id, round_number=round_number,
            agent_messages=json.dumps(agent_result.messages), score=json.dumps({}),
            judge_reasoning=f"Agent error: {agent_result.error}", passed=False,
            duration_ms=agent_duration,
        )
        db.add(eval_result); await db.commit()
        yield {"type": "case_completed", "round": round_number, "case_name": tc.name,
               "passed": False, "error": agent_result.error}
        return

    try:
        parsed = await _run_judge(judge_client, scorer, expected,
                                   agent_result.messages, agent_result.sub_agent_messages)
        logger.info(f"Run #{run.id} round {round_number} case {tc.name}: "
                     f"score={parsed['score']}, passed={parsed['passed']}")
        all_messages = _build_all_messages(agent_result)
        total_duration = int((time.monotonic() - start_time) * 1000) if run_agent else agent_duration
        eval_result = EvalResult(
            run_id=run.id, test_case_id=tc.id, round_number=round_number,
            agent_messages=json.dumps(all_messages), score=json.dumps(parsed["score"]),
            judge_reasoning=parsed["justification"], passed=parsed["passed"],
            duration_ms=total_duration,
        )
    except Exception as e:
        logger.error(f"Run #{run.id} round {round_number} case {tc.name}: judge error — {e}")
        eval_result = EvalResult(
            run_id=run.id, test_case_id=tc.id, round_number=round_number,
            agent_messages=json.dumps(agent_result.messages), score=json.dumps({}),
            judge_reasoning=f"Judge error: {e}", passed=False,
            duration_ms=int((time.monotonic() - start_time) * 1000),
        )

    db.add(eval_result); await db.commit()
    yield {"type": "case_completed", "round": round_number, "case_index": case_index,
           "case_name": tc.name, "passed": eval_result.passed,
           "justification": eval_result.judge_reasoning}
