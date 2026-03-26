import pytest

BINARY_SCORER = {
    "name": "Tool Correctness",
    "description": "Checks if agent called the right tool",
    "output_format": "binary",
    "eval_prompt": "Evaluate whether the agent called the correct tool.",
    "criteria": {
        "conditions": [
            {"name": "correct_tool", "description": "Called expected tool"}
        ],
        "pass_rule": "all",
    },
    "tags": ["tool", "correctness"],
}

RUBRIC_SCORER = {
    "name": "Response Quality",
    "output_format": "rubric",
    "eval_prompt": "Rate the response quality.",
    "criteria": {
        "dimensions": [
            {"name": "correctness", "description": "Factual accuracy", "scale": {"min": 1, "max": 5}},
            {"name": "completeness", "description": "Covers all parts", "scale": {"min": 1, "max": 5}},
        ],
        "aggregation": "average",
    },
    "score_range": {"min": 1, "max": 5},
    "pass_threshold": 3.0,
}


@pytest.mark.asyncio
async def test_create_scorer(client):
    response = await client.post("/api/scorers", json=BINARY_SCORER)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Tool Correctness"
    assert data["output_format"] == "binary"
    assert data["criteria"]["pass_rule"] == "all"


@pytest.mark.asyncio
async def test_list_scorers(client):
    await client.post("/api/scorers", json=BINARY_SCORER)
    await client.post("/api/scorers", json=RUBRIC_SCORER)
    response = await client.get("/api/scorers")
    assert response.status_code == 200
    assert len(response.json()) == 2


@pytest.mark.asyncio
async def test_get_scorer(client):
    create_resp = await client.post("/api/scorers", json=BINARY_SCORER)
    scorer_id = create_resp.json()["id"]
    response = await client.get(f"/api/scorers/{scorer_id}")
    assert response.status_code == 200
    assert response.json()["name"] == "Tool Correctness"


@pytest.mark.asyncio
async def test_get_scorer_not_found(client):
    response = await client.get("/api/scorers/999")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_scorer(client):
    create_resp = await client.post("/api/scorers", json=BINARY_SCORER)
    scorer_id = create_resp.json()["id"]
    response = await client.put(
        f"/api/scorers/{scorer_id}", json={"name": "Updated Name"}
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Updated Name"


@pytest.mark.asyncio
async def test_delete_scorer(client):
    create_resp = await client.post("/api/scorers", json=BINARY_SCORER)
    scorer_id = create_resp.json()["id"]
    response = await client.delete(f"/api/scorers/{scorer_id}")
    assert response.status_code == 204
    get_resp = await client.get(f"/api/scorers/{scorer_id}")
    assert get_resp.status_code == 404
