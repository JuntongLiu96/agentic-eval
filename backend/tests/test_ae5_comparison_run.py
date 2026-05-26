"""AE-5: comparison-run primitive — cold-baseline vs warm-run delta metrics."""

from __future__ import annotations

import json

import pytest

from app.models.adapter import Adapter
from app.models.dataset import Dataset, TestCase
from app.models.eval_result import EvalResult
from app.models.eval_run import EvalRun
from app.models.scorer import Scorer


async def _seed_paired_runs(db_session):
    """Two runs over the same test case, with trajectory_steps differing."""
    ds = Dataset(name="ds", target_type="custom", tags="[]")
    sc = Scorer(name="sc", eval_prompt="x", tags="[]")
    ad = Adapter(name="ad", adapter_type="http", config="{}")
    db_session.add_all([ds, sc, ad])
    await db_session.flush()
    tc = TestCase(dataset_id=ds.id, name="CA-X", data="{}",
                  expected_result="{}", metadata_="{}")
    db_session.add(tc)
    await db_session.flush()

    baseline = EvalRun(name="cold", dataset_id=ds.id, scorer_id=sc.id, adapter_id=ad.id)
    warm = EvalRun(name="warm", dataset_id=ds.id, scorer_id=sc.id, adapter_id=ad.id)
    db_session.add_all([baseline, warm])
    await db_session.flush()

    db_session.add(EvalResult(
        run_id=baseline.id, test_case_id=tc.id, round_number=1, passed=True,
        score=json.dumps({"agent_metadata": {"trajectory_steps": 50, "files_recall": 0.6}}),
    ))
    db_session.add(EvalResult(
        run_id=warm.id, test_case_id=tc.id, round_number=1, passed=True,
        score=json.dumps({"agent_metadata": {"trajectory_steps": 10, "files_recall": 0.95}}),
    ))
    await db_session.commit()
    return baseline.id, warm.id, tc.id


@pytest.mark.asyncio
async def test_comparison_run_computes_n_reduction_and_metric_deltas(client, db_session):
    b_id, w_id, tc_id = await _seed_paired_runs(db_session)
    resp = await client.post("/api/runs/comparison", json={
        "baseline_run_id": b_id, "warm_run_id": w_id,
        "metrics": ["n_reduction", "files_recall"],
    })
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["baseline_run_id"] == b_id
    assert body["warm_run_id"] == w_id
    assert len(body["pairs"]) == 1
    pair = body["pairs"][0]
    assert pair["test_case_id"] == tc_id
    assert pair["deltas"]["n_reduction"] == pytest.approx(1 - 10 / 50)
    assert pair["deltas"]["files_recall"] == pytest.approx(0.95 - 0.6)


@pytest.mark.asyncio
async def test_comparison_run_requires_valid_run_ids(client):
    resp = await client.post("/api/runs/comparison", json={
        "baseline_run_id": 99999, "warm_run_id": 99998,
    })
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_comparison_run_rejects_missing_ids(client):
    resp = await client.post("/api/runs/comparison", json={})
    assert resp.status_code == 422
