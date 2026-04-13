import json
import pytest
from app.models.dataset import Dataset, TestCase
from app.models.eval_result import EvalResult
from app.models.eval_run import EvalRun
from app.models.scorer import Scorer
from app.models.adapter import Adapter
from app.services.aggregator import aggregate_run_results, multi_round_summary, multi_round_per_tc_summary


@pytest.fixture
async def multi_round_run(db_session):
    """Create a run with 2 rounds, 2 test cases, results for each."""
    ds = Dataset(name="DS")
    db_session.add(ds)
    await db_session.flush()

    tc1 = TestCase(dataset_id=ds.id, name="TC1", data='{"prompt":"a"}', expected_result='{}')
    tc2 = TestCase(dataset_id=ds.id, name="TC2", data='{"prompt":"b"}', expected_result='{}')
    db_session.add_all([tc1, tc2])
    await db_session.flush()

    scorer = Scorer(name="S", eval_prompt="test", pass_threshold=60)
    adapter = Adapter(name="A", adapter_type="http", config='{"base_url":"http://fake:9999"}')
    db_session.add_all([scorer, adapter])
    await db_session.flush()

    run = EvalRun(name="multi", dataset_id=ds.id, scorer_id=scorer.id,
                  adapter_id=adapter.id, num_rounds=2, round_mode="agent")
    db_session.add(run)
    await db_session.flush()

    # Round 1: TC1=80 pass, TC2=50 fail
    db_session.add(EvalResult(run_id=run.id, test_case_id=tc1.id, round_number=1,
                              score=json.dumps(80), passed=True, duration_ms=100))
    db_session.add(EvalResult(run_id=run.id, test_case_id=tc2.id, round_number=1,
                              score=json.dumps(50), passed=False, duration_ms=200))
    # Round 2: TC1=90 pass, TC2=70 pass
    db_session.add(EvalResult(run_id=run.id, test_case_id=tc1.id, round_number=2,
                              score=json.dumps(90), passed=True, duration_ms=150))
    db_session.add(EvalResult(run_id=run.id, test_case_id=tc2.id, round_number=2,
                              score=json.dumps(70), passed=True, duration_ms=250))
    await db_session.commit()
    return run


@pytest.mark.asyncio
async def test_aggregate_still_works_single_round(db_session):
    """Existing aggregator should still work for single-round runs."""
    ds = Dataset(name="DS")
    db_session.add(ds)
    await db_session.flush()
    tc = TestCase(dataset_id=ds.id, name="TC1", data='{"prompt":"a"}', expected_result='{}')
    db_session.add(tc)
    await db_session.flush()
    scorer = Scorer(name="S", eval_prompt="test")
    adapter = Adapter(name="A", adapter_type="http", config='{"base_url":"http://fake:9999"}')
    db_session.add_all([scorer, adapter])
    await db_session.flush()
    run = EvalRun(name="single", dataset_id=ds.id, scorer_id=scorer.id, adapter_id=adapter.id)
    db_session.add(run)
    await db_session.flush()
    db_session.add(EvalResult(run_id=run.id, test_case_id=tc.id, round_number=1,
                              score=json.dumps(85), passed=True, duration_ms=100))
    await db_session.commit()

    summary = await aggregate_run_results(run.id, db_session)
    assert summary["total"] == 1
    assert summary["passed"] == 1


@pytest.mark.asyncio
async def test_multi_round_summary_per_round(multi_round_run, db_session):
    """multi_round_summary should return per-round summaries."""
    result = await multi_round_summary(multi_round_run.id, multi_round_run.num_rounds,
                                        multi_round_run.round_mode, 60.0, db_session)
    assert result["num_rounds"] == 2
    assert result["round_mode"] == "agent"
    assert len(result["round_summaries"]) == 2
    # Round 1: 1 passed out of 2
    r1 = result["round_summaries"][0]
    assert r1["round"] == 1
    assert r1["total"] == 2
    assert r1["passed"] == 1
    # Round 2: 2 passed out of 2
    r2 = result["round_summaries"][1]
    assert r2["round"] == 2
    assert r2["total"] == 2
    assert r2["passed"] == 2


@pytest.mark.asyncio
async def test_multi_round_summary_averaged(multi_round_run, db_session):
    """multi_round_summary averaged should compute cross-round averages."""
    result = await multi_round_summary(multi_round_run.id, multi_round_run.num_rounds,
                                        multi_round_run.round_mode, 60.0, db_session)
    avg = result["averaged"]
    assert avg["total"] == 2
    # TC1 avg = (80+90)/2 = 85 → pass. TC2 avg = (50+70)/2 = 60 → pass (>=60).
    assert avg["passed"] == 2
    assert avg["avg_score"] == 72.5  # (85 + 60) / 2


@pytest.mark.asyncio
async def test_multi_round_per_tc_summary(multi_round_run, db_session):
    """multi_round_per_tc_summary should return one row per test case with averaged values."""
    rows = await multi_round_per_tc_summary(multi_round_run.id, multi_round_run.num_rounds, 60.0, db_session)
    assert len(rows) == 2

    # Sort by test_case_id for stable assertions
    rows.sort(key=lambda r: r["test_case_id"])

    # TC1: round 1 = 80 (pass), round 2 = 90 (pass) → avg=85, passed=True, 2/2
    tc1 = rows[0]
    assert tc1["test_case_name"] == "TC1"
    assert tc1["avg_score"] == 85.0
    assert tc1["passed"] is True
    assert tc1["rounds_passed"] == 2
    assert tc1["total_rounds"] == 2
    assert tc1["avg_duration_ms"] == 125  # (100+150)/2

    # TC2: round 1 = 50 (fail), round 2 = 70 (pass) → avg=60, passed=False (1 not > 2/2=1)
    # Wait — 1 > 1 is False, so tie → not passed. That's the 5:5 rule.
    tc2 = rows[1]
    assert tc2["test_case_name"] == "TC2"
    assert tc2["avg_score"] == 60.0
    assert tc2["passed"] is False  # 1 passed out of 2 → tie → not pass
    assert tc2["rounds_passed"] == 1
    assert tc2["total_rounds"] == 2
    assert tc2["avg_duration_ms"] == 225  # (200+250)/2


@pytest.mark.asyncio
async def test_multi_round_per_tc_majority_pass(db_session):
    """Test that majority vote works: 2/3 passed → pass, 1/3 → fail."""
    ds = Dataset(name="DS3")
    db_session.add(ds)
    await db_session.flush()

    tc = TestCase(dataset_id=ds.id, name="TC-majority", data='{"prompt":"x"}', expected_result='{}')
    db_session.add(tc)
    await db_session.flush()

    scorer = Scorer(name="S3", eval_prompt="test", pass_threshold=60)
    adapter = Adapter(name="A3", adapter_type="http", config='{"base_url":"http://fake:9999"}')
    db_session.add_all([scorer, adapter])
    await db_session.flush()

    run = EvalRun(name="majority", dataset_id=ds.id, scorer_id=scorer.id,
                  adapter_id=adapter.id, num_rounds=3, round_mode="agent")
    db_session.add(run)
    await db_session.flush()

    # 2 out of 3 rounds pass → should be overall pass
    db_session.add(EvalResult(run_id=run.id, test_case_id=tc.id, round_number=1,
                              score=json.dumps(70), passed=True, duration_ms=100))
    db_session.add(EvalResult(run_id=run.id, test_case_id=tc.id, round_number=2,
                              score=json.dumps(40), passed=False, duration_ms=200))
    db_session.add(EvalResult(run_id=run.id, test_case_id=tc.id, round_number=3,
                              score=json.dumps(80), passed=True, duration_ms=150))
    await db_session.commit()

    rows = await multi_round_per_tc_summary(run.id, 3, 60.0, db_session)
    assert len(rows) == 1
    tc_row = rows[0]
    assert tc_row["passed"] is True  # 2 > 3/2 = 1.5 → True
    assert tc_row["rounds_passed"] == 2
    assert tc_row["avg_score"] == 63.33  # (70+40+80)/3
