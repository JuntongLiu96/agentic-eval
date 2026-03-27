import pytest
from unittest.mock import AsyncMock, patch
from app.bridge.base import AgentResult


@pytest.mark.asyncio
async def test_create_run(client):
    ds = await client.post("/api/datasets", json={"name": "DS"})
    scorer = await client.post("/api/scorers", json={
        "name": "S", "eval_prompt": "test",
    })
    adapter = await client.post("/api/adapters", json={
        "name": "A", "adapter_type": "http", "config": {"base_url": "http://fake:9999"},
    })
    run = await client.post("/api/runs", json={
        "dataset_id": ds.json()["id"], "scorer_id": scorer.json()["id"], "adapter_id": adapter.json()["id"],
    })
    assert run.status_code == 201
    assert run.json()["status"] == "pending"


@pytest.mark.asyncio
async def test_list_runs(client):
    ds = await client.post("/api/datasets", json={"name": "DS"})
    scorer = await client.post("/api/scorers", json={
        "name": "S", "eval_prompt": "test",
    })
    adapter = await client.post("/api/adapters", json={
        "name": "A", "adapter_type": "http", "config": {"base_url": "http://fake:9999"},
    })
    await client.post("/api/runs", json={
        "dataset_id": ds.json()["id"], "scorer_id": scorer.json()["id"], "adapter_id": adapter.json()["id"],
    })
    resp = await client.get("/api/runs")
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


@pytest.mark.asyncio
async def test_get_run(client):
    ds = await client.post("/api/datasets", json={"name": "DS"})
    scorer = await client.post("/api/scorers", json={
        "name": "S", "eval_prompt": "test",
    })
    adapter = await client.post("/api/adapters", json={
        "name": "A", "adapter_type": "http", "config": {"base_url": "http://fake:9999"},
    })
    run = await client.post("/api/runs", json={
        "dataset_id": ds.json()["id"], "scorer_id": scorer.json()["id"], "adapter_id": adapter.json()["id"],
    })
    resp = await client.get(f"/api/runs/{run.json()['id']}")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_get_run_not_found(client):
    assert (await client.get("/api/runs/999")).status_code == 404


@pytest.mark.asyncio
async def test_delete_run(client):
    ds = await client.post("/api/datasets", json={"name": "DS"})
    scorer = await client.post("/api/scorers", json={
        "name": "S", "eval_prompt": "test",
    })
    adapter = await client.post("/api/adapters", json={
        "name": "A", "adapter_type": "http", "config": {"base_url": "http://fake:9999"},
    })
    run = await client.post("/api/runs", json={
        "dataset_id": ds.json()["id"], "scorer_id": scorer.json()["id"], "adapter_id": adapter.json()["id"],
    })
    run_id = run.json()["id"]
    response = await client.delete(f"/api/runs/{run_id}")
    assert response.status_code == 204
    get_resp = await client.get(f"/api/runs/{run_id}")
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_run_not_found(client):
    assert (await client.delete("/api/runs/999")).status_code == 404


@pytest.mark.asyncio
async def test_start_run_with_mock(client):
    """Full integration test: create all resources, start run with mocked bridge+judge."""
    ds = await client.post("/api/datasets", json={"name": "DS"})
    ds_id = ds.json()["id"]
    await client.post(f"/api/datasets/{ds_id}/testcases", json={
        "name": "TC1", "data": {"prompt": "2+2?"}, "expected_result": {"answer": "4"},
    })
    scorer = await client.post("/api/scorers", json={
        "name": "S", "eval_prompt": "Check answer.\nScore 0-1: 1 if correct, 0 if wrong.\nReturn {\"score\": <0-1>, \"justification\": \"<why>\"}.",
        "pass_threshold": 1,
    })
    adapter = await client.post("/api/adapters", json={
        "name": "A", "adapter_type": "http", "config": {"base_url": "http://fake:9999"},
    })
    run = await client.post("/api/runs", json={
        "dataset_id": ds_id, "scorer_id": scorer.json()["id"], "adapter_id": adapter.json()["id"],
        "judge_config": {"use_target_llm": False, "override_model": "test", "override_api_key": "sk-test"},
    })
    run_id = run.json()["id"]

    mock_bridge = AsyncMock()
    mock_bridge.connect = AsyncMock()
    mock_bridge.disconnect = AsyncMock()
    mock_bridge.get_judge_llm = AsyncMock(return_value=None)
    mock_bridge.send_test = AsyncMock(return_value=AgentResult(
        messages=[{"role": "assistant", "content": "4"}], success=True,
    ))
    mock_judge = AsyncMock()
    mock_judge.chat = AsyncMock(return_value='{"score": 1, "justification": "The agent correctly answered 4."}')

    with patch("app.services.orchestrator.create_adapter", return_value=mock_bridge), \
         patch("app.services.orchestrator.resolve_judge_llm", return_value=mock_judge):
        resp = await client.post(f"/api/runs/{run_id}/start")
        assert resp.status_code == 200

    # Verify run completed
    run_resp = await client.get(f"/api/runs/{run_id}")
    assert run_resp.json()["status"] == "completed"

    # Verify results
    results_resp = await client.get(f"/api/runs/{run_id}/results")
    results = results_resp.json()
    assert len(results) == 1
    assert results[0]["passed"] is True
