"""AE-7: per-quadrant aggregation — group results by TestCase.metadata.quadrant."""

from __future__ import annotations

import json

import pytest

from app.models.adapter import Adapter
from app.models.dataset import Dataset, TestCase
from app.models.eval_result import EvalResult
from app.models.eval_run import EvalRun
from app.models.scorer import Scorer
from app.services.aggregator import _extract_quadrants, per_quadrant_summary


def test_extract_quadrants_handles_list_string_missing_and_malformed():
    assert _extract_quadrants(json.dumps({"quadrant": ["a", "b"]})) == ["a", "b"]
    assert _extract_quadrants(json.dumps({"quadrant": "solo"})) == ["solo"]
    assert _extract_quadrants(json.dumps({})) == []
    assert _extract_quadrants("") == []
    assert _extract_quadrants("not-json") == []
    assert _extract_quadrants(json.dumps({"quadrant": None})) == []


async def _seed_quadrant_run(db_session):
    ds = Dataset(name="ds", target_type="custom", tags="[]")
    sc = Scorer(name="sc", eval_prompt="x", tags="[]", pass_threshold=60.0)
    ad = Adapter(name="ad", adapter_type="http", config="{}")
    db_session.add_all([ds, sc, ad])
    await db_session.flush()

    tc1 = TestCase(dataset_id=ds.id, name="CA-001", data="{}", expected_result="{}",
                   metadata_=json.dumps({"quadrant": ["cross-episode", "execution-oriented"]}))
    tc2 = TestCase(dataset_id=ds.id, name="CA-002", data="{}", expected_result="{}",
                   metadata_=json.dumps({"quadrant": ["cross-episode", "execution-oriented"]}))
    tc3 = TestCase(dataset_id=ds.id, name="CA-005", data="{}", expected_result="{}",
                   metadata_=json.dumps({"quadrant": ["in-episode", "knowledge-oriented"]}))
    tc4 = TestCase(dataset_id=ds.id, name="GN-x", data="{}", expected_result="{}",
                   metadata_="{}")
    db_session.add_all([tc1, tc2, tc3, tc4])
    await db_session.flush()

    run = EvalRun(name="r", dataset_id=ds.id, scorer_id=sc.id, adapter_id=ad.id)
    db_session.add(run)
    await db_session.flush()

    db_session.add_all([
        EvalResult(run_id=run.id, test_case_id=tc1.id, round_number=1, passed=True,
                   score=json.dumps({"score": 90})),
        EvalResult(run_id=run.id, test_case_id=tc2.id, round_number=1, passed=False,
                   score=json.dumps({"score": 40})),
        EvalResult(run_id=run.id, test_case_id=tc3.id, round_number=1, passed=True,
                   score=json.dumps({"score": 80})),
        EvalResult(run_id=run.id, test_case_id=tc4.id, round_number=1, passed=True,
                   score=json.dumps({"score": 70})),
    ])
    await db_session.commit()
    return run.id


@pytest.mark.asyncio
async def test_per_quadrant_summary_buckets_results_by_quadrant_tag(db_session):
    run_id = await _seed_quadrant_run(db_session)
    out = await per_quadrant_summary(run_id, pass_threshold=60.0, db=db_session)

    # tc1 + tc2 contribute to both cross-episode and execution-oriented
    assert out["cross-episode"]["total"] == 2
    assert out["cross-episode"]["passed"] == 1
    assert out["cross-episode"]["pass_rate"] == 50.0
    assert out["execution-oriented"]["total"] == 2

    # tc3 contributes to in-episode + knowledge-oriented
    assert out["in-episode"]["total"] == 1
    assert out["in-episode"]["passed"] == 1
    assert out["knowledge-oriented"]["total"] == 1

    # tc4 (no quadrant) lands in unlabeled
    assert out["unlabeled"]["total"] == 1


@pytest.mark.asyncio
async def test_run_summary_endpoint_includes_by_quadrant(client, db_session):
    run_id = await _seed_quadrant_run(db_session)
    resp = await client.get(f"/api/runs/{run_id}/summary")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "by_quadrant" in body
    assert body["by_quadrant"]["cross-episode"]["total"] == 2
    assert body["by_quadrant"]["unlabeled"]["total"] == 1
