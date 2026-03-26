from typing import Any
import httpx
from app.bridge.base import AgentResult, BridgeAdapter

class HTTPAdapter(BridgeAdapter):
    def __init__(self):
        self.base_url: str = ""
        self.endpoints: dict[str, str] = {}
        self._client: httpx.AsyncClient | None = None
        self._description: str = ""

    async def connect(self, config: dict[str, Any]) -> None:
        self.base_url = config["base_url"]
        self.endpoints = config.get("endpoints", {"send_test": "/eval/run", "health": "/eval/health"})
        self._description = config.get("description", f"HTTP agent at {self.base_url}")
        self._client = httpx.AsyncClient(base_url=self.base_url, timeout=300.0)

    async def disconnect(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    async def health_check(self) -> bool:
        if not self._client: return False
        try:
            resp = await self._client.get(self.endpoints.get("health", "/eval/health"))
            return resp.status_code == 200
        except httpx.RequestError:
            return False

    async def send_test(self, test_data: dict[str, Any]) -> AgentResult:
        if not self._client:
            return AgentResult(messages=[], success=False, error="Not connected")
        try:
            resp = await self._client.post(self.endpoints.get("send_test", "/eval/run"), json=test_data)
            if resp.status_code != 200:
                return AgentResult(messages=[], success=False, error=f"HTTP {resp.status_code}: {resp.text[:500]}")
            data = resp.json()
            return AgentResult(messages=data.get("messages", []), metadata=data.get("metadata", {}), success=True)
        except httpx.RequestError as e:
            return AgentResult(messages=[], success=False, error=str(e))

    def adapter_type(self) -> str: return "http"
    def target_description(self) -> str: return self._description
