import pytest

HTTP_ADAPTER = {
    "name": "Test Service", "adapter_type": "http",
    "config": {"base_url": "http://localhost:9999", "endpoints": {"send_test": "/eval/run", "health": "/eval/health"}},
    "description": "Test HTTP agent",
}
STDIO_ADAPTER = {
    "name": "Test App", "adapter_type": "stdio",
    "config": {"command": "node", "args": ["eval-bridge.js"], "cwd": "/app"},
}

@pytest.mark.asyncio
async def test_create_adapter(client):
    response = await client.post("/api/adapters", json=HTTP_ADAPTER)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Test Service"
    assert data["adapter_type"] == "http"
    assert data["config"]["base_url"] == "http://localhost:9999"

@pytest.mark.asyncio
async def test_list_adapters(client):
    await client.post("/api/adapters", json=HTTP_ADAPTER)
    await client.post("/api/adapters", json=STDIO_ADAPTER)
    response = await client.get("/api/adapters")
    assert response.status_code == 200
    assert len(response.json()) == 2

@pytest.mark.asyncio
async def test_get_adapter(client):
    resp = await client.post("/api/adapters", json=HTTP_ADAPTER)
    response = await client.get(f"/api/adapters/{resp.json()['id']}")
    assert response.status_code == 200

@pytest.mark.asyncio
async def test_get_adapter_not_found(client):
    assert (await client.get("/api/adapters/999")).status_code == 404

@pytest.mark.asyncio
async def test_update_adapter(client):
    resp = await client.post("/api/adapters", json=HTTP_ADAPTER)
    response = await client.put(f"/api/adapters/{resp.json()['id']}", json={"name": "Updated"})
    assert response.status_code == 200
    assert response.json()["name"] == "Updated"

@pytest.mark.asyncio
async def test_delete_adapter(client):
    resp = await client.post("/api/adapters", json=HTTP_ADAPTER)
    assert (await client.delete(f"/api/adapters/{resp.json()['id']}")).status_code == 204
    assert (await client.get(f"/api/adapters/{resp.json()['id']}")).status_code == 404
