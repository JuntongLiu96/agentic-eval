import pytest


@pytest.mark.asyncio
async def test_create_dataset(client):
    response = await client.post("/api/datasets", json={
        "name": "Search Tool Eval",
        "description": "Evaluates search tool accuracy",
        "target_type": "tool",
        "tags": ["search", "tool"],
    })
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Search Tool Eval"
    assert data["target_type"] == "tool"
    assert data["tags"] == ["search", "tool"]
    assert "id" in data


@pytest.mark.asyncio
async def test_list_datasets(client):
    await client.post("/api/datasets", json={"name": "Dataset 1"})
    await client.post("/api/datasets", json={"name": "Dataset 2"})
    response = await client.get("/api/datasets")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2


@pytest.mark.asyncio
async def test_get_dataset(client):
    create_resp = await client.post("/api/datasets", json={"name": "My Dataset"})
    dataset_id = create_resp.json()["id"]
    response = await client.get(f"/api/datasets/{dataset_id}")
    assert response.status_code == 200
    assert response.json()["name"] == "My Dataset"


@pytest.mark.asyncio
async def test_get_dataset_not_found(client):
    response = await client.get("/api/datasets/999")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_dataset(client):
    create_resp = await client.post("/api/datasets", json={"name": "Old Name"})
    dataset_id = create_resp.json()["id"]
    response = await client.put(f"/api/datasets/{dataset_id}", json={"name": "New Name"})
    assert response.status_code == 200
    assert response.json()["name"] == "New Name"


@pytest.mark.asyncio
async def test_delete_dataset(client):
    create_resp = await client.post("/api/datasets", json={"name": "To Delete"})
    dataset_id = create_resp.json()["id"]
    response = await client.delete(f"/api/datasets/{dataset_id}")
    assert response.status_code == 204
    get_resp = await client.get(f"/api/datasets/{dataset_id}")
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_create_test_case(client):
    ds_resp = await client.post("/api/datasets", json={"name": "DS"})
    ds_id = ds_resp.json()["id"]
    response = await client.post(f"/api/datasets/{ds_id}/testcases", json={
        "name": "Test 1",
        "data": {"prompt": "What is 2+2?"},
        "expected_result": {"answer": "4"},
    })
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Test 1"
    assert data["data"] == {"prompt": "What is 2+2?"}


@pytest.mark.asyncio
async def test_list_test_cases(client):
    ds_resp = await client.post("/api/datasets", json={"name": "DS"})
    ds_id = ds_resp.json()["id"]
    await client.post(f"/api/datasets/{ds_id}/testcases", json={
        "name": "TC1", "data": {}, "expected_result": {},
    })
    await client.post(f"/api/datasets/{ds_id}/testcases", json={
        "name": "TC2", "data": {}, "expected_result": {},
    })
    response = await client.get(f"/api/datasets/{ds_id}/testcases")
    assert response.status_code == 200
    assert len(response.json()) == 2


@pytest.mark.asyncio
async def test_update_test_case(client):
    ds_resp = await client.post("/api/datasets", json={"name": "DS"})
    ds_id = ds_resp.json()["id"]
    tc_resp = await client.post(f"/api/datasets/{ds_id}/testcases", json={
        "name": "Old", "data": {"a": 1}, "expected_result": {"b": 2},
    })
    tc_id = tc_resp.json()["id"]
    response = await client.put(f"/api/testcases/{tc_id}", json={"name": "New"})
    assert response.status_code == 200
    assert response.json()["name"] == "New"


@pytest.mark.asyncio
async def test_delete_test_case(client):
    ds_resp = await client.post("/api/datasets", json={"name": "DS"})
    ds_id = ds_resp.json()["id"]
    tc_resp = await client.post(f"/api/datasets/{ds_id}/testcases", json={
        "name": "TC", "data": {}, "expected_result": {},
    })
    tc_id = tc_resp.json()["id"]
    response = await client.delete(f"/api/testcases/{tc_id}")
    assert response.status_code == 204
