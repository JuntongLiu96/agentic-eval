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


def _parse_case_metadata(tc: Any) -> dict[str, Any]:
    """Parse TestCase.metadata_ (DB column ``metadata``) into a dict.

    Defaults to an empty dict on malformed JSON so the eval doesn't crash on
    legacy rows. Always returns a fresh dict so callers can mutate safely.
    """
    raw = getattr(tc, "metadata_", None)
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return dict(raw)
    if isinstance(raw, str):
        if not raw.strip():
            return {}
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return {}
        return dict(parsed) if isinstance(parsed, dict) else {}
    return {}


async def _run_judge(
    judge_client: Any, scorer: Scorer, expected: Any,
    agent_messages: list, sub_agent_messages: list | None,
    agent_metadata: dict[str, Any] | None = None,
    testcase_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Assemble judge prompt, call LLM, parse response.

    AE-1: if the scorer is programmatic, dispatch to the deterministic scorer
    instead of calling an LLM at all.
    AE-2: ``agent_metadata`` is forwarded into the judge prompt for LLM scorers
    and is the *sole* input for programmatic scorers.
    AE-12: ``testcase_metadata`` (and ``expected``) are forwarded so a single
    generic scorer can read case-specific data — via ``{{testcase_metadata}}``
    / ``{{expected_result}}`` template variables for LLM judges, or via
    ``testcase_metadata.*`` / ``expected_result.*`` paths in programmatic rules.
    """
    scorer_type = getattr(scorer, "scorer_type", None) or "llm_judge"
    if scorer_type == "programmatic":
        from app.services.programmatic_scorer import evaluate_programmatic
        return evaluate_programmatic(
            scorer=scorer,
            agent_metadata=agent_metadata or {},
            agent_messages=agent_messages,
            testcase_metadata=testcase_metadata or {},
            expected_result=expected,
        )
    if scorer_type == "series":
        # AE-6: series scorers operate over multi-round metadata. When invoked
        # per-round (as here), evaluate as a 1-element series so non-cross-round
        # checks still run; callers that need true cross-round evaluation pull
        # results post-hoc and invoke ``evaluate_series`` directly.
        from app.services.series_scorer import evaluate_series
        return evaluate_series(scorer, [agent_metadata or {}])
    judge_messages = assemble_judge_prompt(
        eval_prompt=scorer.eval_prompt, expected_result=expected,
        agent_messages=agent_messages,
        sub_agent_messages=sub_agent_messages or None,
        agent_metadata=agent_metadata,
        testcase_metadata=testcase_metadata,
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
    # AE-13: optional extra scorers (multi-scorer-per-run). Build a map so the
    # per-case dispatcher can resolve scorer ids cheaply. The run's default
    # ``scorer`` is always included.
    scorer_map: dict[int, Scorer] = {scorer.id: scorer}
    try:
        extra_ids = json.loads(run.scorer_ids) if isinstance(run.scorer_ids, str) else (run.scorer_ids or [])
    except (json.JSONDecodeError, TypeError):
        extra_ids = []
    if isinstance(extra_ids, list):
        for sid in extra_ids:
            if not isinstance(sid, int) or sid in scorer_map:
                continue
            extra = await db.get(Scorer, sid)
            if extra:
                scorer_map[extra.id] = extra
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
                async for event in _run_scorer_mode(run, scorer, scorer_map, bridge, judge_client, test_cases, num_rounds, db):
                    yield event
            else:
                async for event in _run_agent_mode(run, scorer, scorer_map, bridge, judge_client, test_cases, num_rounds, db):
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
    run: EvalRun, scorer: Scorer, scorer_map: dict[int, Scorer], bridge: Any, judge_client: Any,
    test_cases: list, num_rounds: int, db: AsyncSession,
) -> AsyncGenerator[dict[str, Any], None]:
    """Agent mode: re-run full agent + judge pipeline each round."""
    for rnd in range(1, num_rounds + 1):
        yield {"type": "round_started", "round": rnd, "total_rounds": num_rounds}
        for i, tc in enumerate(test_cases):
            async for event in _eval_single_case(
                run, scorer, scorer_map, bridge, judge_client, tc, i, len(test_cases), rnd, num_rounds,
                run_agent=True, cached_agent_result=None, db=db,
            ):
                yield event
        yield {"type": "round_completed", "round": rnd}


async def _run_scorer_mode(
    run: EvalRun, scorer: Scorer, scorer_map: dict[int, Scorer], bridge: Any, judge_client: Any,
    test_cases: list, num_rounds: int, db: AsyncSession,
) -> AsyncGenerator[dict[str, Any], None]:
    """Scorer mode: run agent once (round 0), then judge N times."""
    # Phase 1: Run agent for all test cases
    yield {"type": "phase_started", "phase": "agent_run", "total_rounds": num_rounds}
    yield {"type": "round_started", "round": 0, "total_rounds": num_rounds, "phase": "agent_run"}
    cached_results: dict[int, Any] = {}
    for i, tc in enumerate(test_cases):
        test_data = json.loads(tc.data) if isinstance(tc.data, str) else tc.data
        # AE-3: forward TestCase.metadata to the bridge (case_id, scope, phase, round_idx, ...)
        case_metadata = _parse_case_metadata(tc)
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
        accumulated_metadata: dict[str, Any] = {}
        turn_results_list = []
        agent_failed = False

        for turn_index, turn in enumerate(turns):
            turn_meta = dict(case_metadata)
            turn_meta["phase"] = "agent_run"
            turn_meta["turn_index"] = turn_index
            agent_result = await bridge.send_test(
                {"prompt": turn["prompt"]},
                session_id=session_id,
                metadata=turn_meta,
            )
            if not agent_result.success:
                agent_failed = True
                break
            if session_id is None and agent_result.metadata.get("session_id"):
                session_id = agent_result.metadata["session_id"]
            all_messages.extend(agent_result.messages)
            all_sub_messages.extend(agent_result.sub_agent_messages)
            # AE-2: accumulate metadata across turns.
            if agent_result.metadata:
                accumulated_metadata.update(agent_result.metadata)

        duration = int((time.monotonic() - start_time) * 1000)

        if agent_failed:
            cached_results[tc.id] = {"result": agent_result, "duration_ms": duration, "turn_results": []}
        else:
            combined = AgentResult(
                messages=all_messages,
                sub_agent_messages=all_sub_messages,
                metadata=accumulated_metadata if turns else {},
                success=True,
            )
            cached_results[tc.id] = {"result": combined, "duration_ms": duration, "turn_results": turn_results_list}

        yield {"type": "case_completed", "round": 0, "case_index": i, "case_name": tc.name,
               "success": not agent_failed}
    yield {"type": "round_completed", "round": 0}

    # Phase 2: Judge N times
    yield {"type": "phase_started", "phase": "judge", "total_rounds": num_rounds}
    for rnd in range(1, num_rounds + 1):
        yield {"type": "round_started", "round": rnd, "total_rounds": num_rounds}
        for i, tc in enumerate(test_cases):
            cached = cached_results.get(tc.id)
            async for event in _eval_single_case(
                run, scorer, scorer_map, bridge, judge_client, tc, i, len(test_cases), rnd, num_rounds,
                run_agent=False, cached_agent_result=cached, db=db,
            ):
                yield event
        yield {"type": "round_completed", "round": rnd}


async def _eval_single_case(
    run: EvalRun, scorer: Scorer, scorer_map: dict[int, Scorer], bridge: Any, judge_client: Any,
    tc: Any, case_index: int, total_cases: int, round_number: int, total_rounds: int,
    run_agent: bool, cached_agent_result: dict | None, db: AsyncSession,
) -> AsyncGenerator[dict[str, Any], None]:
    """Evaluate a single test case (single-turn or multi-turn) for a single round.

    AE-13: a case may be scored by multiple scorers. Resolution order:
      1. ``case_metadata.scorer_ids`` (list[int]) — explicit per-case override
      2. ``case_metadata.scorer_id`` (int) — single per-case override
      3. all scorers in ``scorer_map`` (run default + AE-13 extras)
    One ``EvalResult`` row is persisted per (case, round, scorer).
    """
    test_data = json.loads(tc.data) if isinstance(tc.data, str) else tc.data
    expected = json.loads(tc.expected_result) if isinstance(tc.expected_result, str) else tc.expected_result
    # AE-3: forward TestCase.metadata to the bridge (case_id, scope, phase, round_idx, ...)
    case_metadata = _parse_case_metadata(tc)

    # AE-13: resolve which scorer(s) apply to this case.
    case_scorer_ids = case_metadata.get("scorer_ids")
    if not (isinstance(case_scorer_ids, list) and case_scorer_ids):
        single = case_metadata.get("scorer_id")
        case_scorer_ids = [single] if isinstance(single, int) else list(scorer_map.keys())
    scorers_for_case: list[Scorer] = []
    for sid in case_scorer_ids:
        s = scorer_map.get(sid)
        if s is None:
            s = await db.get(Scorer, sid)
            if s:
                scorer_map[s.id] = s
        if s:
            scorers_for_case.append(s)
    if not scorers_for_case:
        scorers_for_case = [scorer]

    logger.info(f"Run #{run.id} round {round_number} case {case_index + 1}/{total_cases}: {tc.name}")
    yield {"type": "case_started", "round": round_number, "case_index": case_index,
           "case_name": tc.name, "total_cases": total_cases}

    start_time = time.monotonic()

    if run_agent:
        try:
            turns = parse_turns(test_data)
        except ValueError as e:
            for s in scorers_for_case:
                eval_result = EvalResult(
                    run_id=run.id, test_case_id=tc.id, scorer_id=s.id, round_number=round_number,
                    agent_messages=json.dumps([]), score=json.dumps({}),
                    judge_reasoning=f"Invalid test data: {e}", passed=False, duration_ms=0,
                )
                db.add(eval_result)
            await db.commit()
            yield {"type": "case_completed", "round": round_number, "case_name": tc.name,
                   "passed": False, "error": str(e)}
            return

        session_id = None
        all_messages = []
        all_sub_messages = []
        accumulated_metadata: dict[str, Any] = {}
        turn_results_list = []

        logger.info(f"Run #{run.id} case {tc.name}: {len(turns)} turns to execute")

        for turn_index, turn in enumerate(turns):
            logger.info(f"Run #{run.id} case {tc.name}: sending turn {turn_index + 1}/{len(turns)} "
                        f"(session_id={session_id})")
            turn_meta = dict(case_metadata)
            turn_meta["round_idx"] = round_number
            turn_meta["turn_index"] = turn_index
            agent_result = await bridge.send_test(
                {"prompt": turn["prompt"]},
                session_id=session_id,
                metadata=turn_meta,
            )

            if not agent_result.success:
                logger.warning(f"Run #{run.id} round {round_number} case {tc.name} turn {turn_index}: "
                               f"agent failed — {agent_result.error}")
                for s in scorers_for_case:
                    eval_result = EvalResult(
                        run_id=run.id, test_case_id=tc.id, scorer_id=s.id, round_number=round_number,
                        agent_messages=json.dumps(all_messages), score=json.dumps({}),
                        judge_reasoning=f"Agent error at turn {turn_index}: {agent_result.error}",
                        passed=False, duration_ms=int((time.monotonic() - start_time) * 1000),
                        turn_results=json.dumps(turn_results_list) if turn_results_list else None,
                    )
                    db.add(eval_result)
                await db.commit()
                yield {"type": "case_completed", "round": round_number, "case_name": tc.name,
                       "passed": False, "error": agent_result.error}
                return

            if session_id is None and agent_result.metadata.get("session_id"):
                session_id = agent_result.metadata["session_id"]
                logger.info(f"Run #{run.id} case {tc.name}: captured session_id={session_id}")

            all_messages.extend(agent_result.messages)
            all_sub_messages.extend(agent_result.sub_agent_messages)
            # AE-2: merge per-turn metadata (later turns override earlier keys —
            # final-turn metrics like n_reduction reflect the whole trajectory).
            if agent_result.metadata:
                accumulated_metadata.update(agent_result.metadata)
            logger.info(f"Run #{run.id} case {tc.name}: turn {turn_index} returned "
                        f"{len(agent_result.messages)} messages (total accumulated: {len(all_messages)})")

            if "expected_result" in turn:
                try:
                    turn_parsed = await _run_judge(
                        judge_client, scorer, turn["expected_result"],
                        all_messages, all_sub_messages or None,
                        agent_metadata=accumulated_metadata,
                        testcase_metadata=case_metadata,
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
            metadata = accumulated_metadata
            success = True
        final_result = _FinalResult()
    else:
        if cached_agent_result is None:
            for s in scorers_for_case:
                eval_result = EvalResult(
                    run_id=run.id, test_case_id=tc.id, scorer_id=s.id, round_number=round_number,
                    agent_messages=json.dumps([]), score=json.dumps({}),
                    judge_reasoning="No cached agent result", passed=False, duration_ms=0,
                )
                db.add(eval_result)
            await db.commit()
            yield {"type": "case_completed", "round": round_number, "case_name": tc.name,
                   "passed": False, "error": "No cached agent result"}
            return
        final_result = cached_agent_result["result"]
        agent_duration = cached_agent_result["duration_ms"]
        all_messages = final_result.messages
        all_sub_messages = final_result.sub_agent_messages if hasattr(final_result, 'sub_agent_messages') else []
        turn_results_list = cached_agent_result.get("turn_results", [])

    final_metadata = getattr(final_result, "metadata", None) or {}
    all_msg_obj = _build_all_messages(final_result)
    total_duration = int((time.monotonic() - start_time) * 1000) if run_agent else agent_duration

    any_passed = False
    last_justification = ""
    for s in scorers_for_case:
        try:
            parsed = await _run_judge(judge_client, s, expected,
                                       all_messages, all_sub_messages or None,
                                       agent_metadata=final_metadata,
                                       testcase_metadata=case_metadata)
            logger.info(f"Run #{run.id} round {round_number} case {tc.name} scorer #{s.id}: "
                         f"score={parsed['score']}, passed={parsed['passed']}")
            eval_result = EvalResult(
                run_id=run.id, test_case_id=tc.id, scorer_id=s.id, round_number=round_number,
                agent_messages=json.dumps(all_msg_obj), score=json.dumps(parsed["score"]),
                judge_reasoning=parsed["justification"], passed=parsed["passed"],
                duration_ms=total_duration,
                turn_results=json.dumps(turn_results_list) if turn_results_list else None,
            )
            any_passed = any_passed or bool(parsed["passed"])
            last_justification = parsed["justification"]
        except Exception as e:
            logger.error(f"Run #{run.id} round {round_number} case {tc.name} scorer #{s.id}: judge error — {e}")
            eval_result = EvalResult(
                run_id=run.id, test_case_id=tc.id, scorer_id=s.id, round_number=round_number,
                agent_messages=json.dumps(all_messages), score=json.dumps({}),
                judge_reasoning=f"Judge error: {e}", passed=False,
                duration_ms=int((time.monotonic() - start_time) * 1000),
                turn_results=json.dumps(turn_results_list) if turn_results_list else None,
            )
            last_justification = f"Judge error: {e}"
        db.add(eval_result)
    await db.commit()
    yield {"type": "case_completed", "round": round_number, "case_index": case_index,
           "case_name": tc.name, "passed": any_passed,
           "justification": last_justification}
