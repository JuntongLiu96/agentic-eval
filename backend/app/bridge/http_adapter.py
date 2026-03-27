from typing import Any
import httpx
from app.bridge.base import AgentResult, BridgeAdapter, LLMClient


class HTTPJudgeLLMClient:
    """LLMClient that proxies chat calls through the target agent's /eval/judge endpoint."""

    def __init__(self, client: httpx.AsyncClient, endpoint: str):
        self._client = client
        self._endpoint = endpoint

    async def chat(self, messages: list[dict[str, str]]) -> str:
        resp = await self._client.post(self._endpoint, json={"messages": messages})
        resp.raise_for_status()
        return resp.json()["content"]


class HTTPAdapter(BridgeAdapter):
    def __init__(self):
        self.base_url: str = ""
        self.endpoints: dict[str, str] = {}
        self._client: httpx.AsyncClient | None = None
        self._description: str = ""

    async def connect(self, config: dict[str, Any]) -> None:
        self.base_url = config["base_url"]
        self.endpoints = config.get("endpoints", {
            "send_test": "/eval/run",
            "health": "/eval/health",
            "judge": "/eval/judge",
        })
        self._description = config.get("description", f"HTTP agent at {self.base_url}")

        # Optional auth token — sent as Authorization header on every request
        headers = {}
        auth_token = config.get("auth_token", "")
        if auth_token:
            # Support both "Bearer xxx" and raw "xxx" formats
            if not auth_token.startswith("Bearer "):
                auth_token = f"Bearer {auth_token}"
            headers["Authorization"] = auth_token

        self._client = httpx.AsyncClient(base_url=self.base_url, timeout=300.0, headers=headers)

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

    async def get_judge_llm(self) -> LLMClient | None:
        if not self._client:
            return None
        judge_endpoint = self.endpoints.get("judge", "/eval/judge")
        return HTTPJudgeLLMClient(self._client, judge_endpoint)

    def adapter_type(self) -> str: return "http"
    def target_description(self) -> str: return self._description
