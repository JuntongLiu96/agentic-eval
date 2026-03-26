import pytest


@pytest.mark.asyncio
async def test_list_templates(client):
    response = await client.get("/api/scorer-templates")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 4
    names = {t["name"] for t in data}
    assert "Tool Call Correctness" in names
    assert "Response Quality" in names


@pytest.mark.asyncio
async def test_get_template(client):
    list_resp = await client.get("/api/scorer-templates")
    template_id = list_resp.json()[0]["id"]
    response = await client.get(f"/api/scorer-templates/{template_id}")
    assert response.status_code == 200
    data = response.json()
    assert "template_prompt" in data
    assert "example_scorer" in data
    assert isinstance(data["example_scorer"], dict)


@pytest.mark.asyncio
async def test_get_template_not_found(client):
    response = await client.get("/api/scorer-templates/999")
    assert response.status_code == 404
