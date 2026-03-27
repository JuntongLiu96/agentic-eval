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
from app.services.aggregator import aggregate_run_results
from app.services.judge import assemble_judge_prompt, parse_judge_response, resolve_judge_llm

logger = logging.getLogger(__name__)

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
    logger.info(f"Run #{run_id} started with {len(test_cases)} test cases")
    yield {"type": "run_started", "run_id": run_id, "total_cases": len(test_cases)}

    for i, tc in enumerate(test_cases):
        logger.info(f"Run #{run_id} case {i+1}/{len(test_cases)}: {tc.name}")
        yield {"type": "case_started", "case_index": i, "case_name": tc.name, "total_cases": len(test_cases)}
        start_time = time.monotonic()
        test_data = json.loads(tc.data) if isinstance(tc.data, str) else tc.data
        expected = json.loads(tc.expected_result) if isinstance(tc.expected_result, str) else tc.expected_result

        agent_result = await bridge.send_test(test_data)

        if not agent_result.success:
            logger.warning(f"Run #{run_id} case {tc.name}: agent failed — {agent_result.error}")
            eval_result = EvalResult(run_id=run_id, test_case_id=tc.id,
                agent_messages=json.dumps(agent_result.messages), score=json.dumps({}),
                judge_reasoning=f"Agent error: {agent_result.error}", passed=False,
                duration_ms=int((time.monotonic() - start_time) * 1000))
            db.add(eval_result); await db.commit()
            yield {"type": "case_completed", "case_index": i, "case_name": tc.name, "passed": False, "error": agent_result.error}
            continue

        try:
            logger.info(f"Run #{run_id} case {tc.name}: agent returned {len(agent_result.messages)} messages, calling judge...")
            judge_messages = assemble_judge_prompt(
                eval_prompt=scorer.eval_prompt, expected_result=expected,
                agent_messages=agent_result.messages)
            judge_response = await judge_client.chat(judge_messages)
            parsed = parse_judge_response(judge_response, scorer.pass_threshold)
            logger.info(f"Run #{run_id} case {tc.name}: score={parsed['score']}, passed={parsed['passed']}")
            eval_result = EvalResult(run_id=run_id, test_case_id=tc.id,
                agent_messages=json.dumps(agent_result.messages), score=json.dumps(parsed["score"]),
                judge_reasoning=parsed["justification"], passed=parsed["passed"],
                duration_ms=int((time.monotonic() - start_time) * 1000))
        except Exception as e:
            logger.error(f"Run #{run_id} case {tc.name}: judge error — {e}")
            eval_result = EvalResult(run_id=run_id, test_case_id=tc.id,
                agent_messages=json.dumps(agent_result.messages), score=json.dumps({}),
                judge_reasoning=f"Judge error: {e}", passed=False,
                duration_ms=int((time.monotonic() - start_time) * 1000))

        db.add(eval_result); await db.commit()
        yield {"type": "case_completed", "case_index": i, "case_name": tc.name,
               "passed": eval_result.passed, "justification": eval_result.judge_reasoning}

    await bridge.disconnect()
    run.status = RunStatus.completed; run.finished_at = datetime.now(timezone.utc)
    await db.commit()
    summary = await aggregate_run_results(run_id, db)
    yield {"type": "run_completed", "run_id": run_id, "summary": summary}
