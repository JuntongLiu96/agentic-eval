import pytest

SCORER_A = {
    "name": "Tool Correctness",
    "description": "Checks if agent called the right tool",
    "eval_prompt": "Evaluate whether the agent called the correct tool with the correct parameters.\nScore 0-100: correct tool (50 points), correct params (50 points).\nReturn {\"score\": <0-100>, \"justification\": \"<detailed explanation>\"}.",
    "pass_threshold": 60,
    "tags": ["tool", "correctness"],
}

SCORER_B = {
    "name": "Response Quality",
    "eval_prompt": "Rate the response on correctness (1-5) and completeness (1-5).\nOverall score = average.\nReturn {\"score\": <1-5>, \"justification\": \"<detailed explanation>\"}.",
    "pass_threshold": 3.0,
}


@pytest.mark.asyncio
async def test_create_scorer(client):
    response = await client.post("/api/scorers", json=SCORER_A)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Tool Correctness"
    assert data["pass_threshold"] == 60
    assert "correct tool" in data["eval_prompt"]


@pytest.mark.asyncio
async def test_list_scorers(client):
    await client.post("/api/scorers", json=SCORER_A)
    await client.post("/api/scorers", json=SCORER_B)
    response = await client.get("/api/scorers")
    assert response.status_code == 200
    assert len(response.json()) == 2


@pytest.mark.asyncio
async def test_get_scorer(client):
    create_resp = await client.post("/api/scorers", json=SCORER_A)
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
    create_resp = await client.post("/api/scorers", json=SCORER_A)
    scorer_id = create_resp.json()["id"]
    response = await client.put(
        f"/api/scorers/{scorer_id}", json={"name": "Updated Name"}
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Updated Name"


@pytest.mark.asyncio
async def test_delete_scorer(client):
    create_resp = await client.post("/api/scorers", json=SCORER_A)
    scorer_id = create_resp.json()["id"]
    response = await client.delete(f"/api/scorers/{scorer_id}")
    assert response.status_code == 204
    get_resp = await client.get(f"/api/scorers/{scorer_id}")
    assert get_resp.status_code == 404
