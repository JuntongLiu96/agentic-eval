import io

import pytest


@pytest.mark.asyncio
async def test_export_csv(client):
    ds_resp = await client.post("/api/datasets", json={"name": "DS"})
    ds_id = ds_resp.json()["id"]
    await client.post(f"/api/datasets/{ds_id}/testcases", json={
        "name": "TC1",
        "data": {"prompt": "Hello"},
        "expected_result": {"answer": "Hi"},
        "metadata": {"source": "manual"},
    })
    await client.post(f"/api/datasets/{ds_id}/testcases", json={
        "name": "TC2",
        "data": {"prompt": "Bye"},
        "expected_result": {"answer": "Goodbye"},
    })
    response = await client.get(f"/api/datasets/{ds_id}/export")
    assert response.status_code == 200
    assert "text/csv" in response.headers["content-type"]
    lines = response.text.strip().split("\n")
    assert len(lines) == 3  # header + 2 rows
    assert "name" in lines[0]


@pytest.mark.asyncio
async def test_import_csv(client):
    ds_resp = await client.post("/api/datasets", json={"name": "DS"})
    ds_id = ds_resp.json()["id"]
    csv_content = 'name,data,expected_result,metadata\nTC1,"{""prompt"": ""Hello""}","{""answer"": ""Hi""}","{}"\nTC2,"{""prompt"": ""Bye""}","{""answer"": ""Goodbye""}","{}"\n'
    response = await client.post(
        f"/api/datasets/{ds_id}/import",
        files={"file": ("test.csv", csv_content, "text/csv")},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["imported_count"] == 2

    # Verify test cases were created
    tc_resp = await client.get(f"/api/datasets/{ds_id}/testcases")
    assert len(tc_resp.json()) == 2


@pytest.mark.asyncio
async def test_import_csv_missing_columns(client):
    ds_resp = await client.post("/api/datasets", json={"name": "DS"})
    ds_id = ds_resp.json()["id"]
    csv_content = "name,wrong_col\nTC1,value\n"
    response = await client.post(
        f"/api/datasets/{ds_id}/import",
        files={"file": ("test.csv", csv_content, "text/csv")},
    )
    assert response.status_code == 400
