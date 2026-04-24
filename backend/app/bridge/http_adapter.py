from typing import Any
import logging
import httpx
from app.bridge.base import AgentResult, BridgeAdapter, LLMClient

logger = logging.getLogger(__name__)


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

        # Configurable timeout — default 3600s (1 hour) for agentic flows
        timeout = config.get("timeout_seconds", 3600)

        # Optional auth token — sent as Authorization header on every request
        headers = {}
        auth_token = config.get("auth_token", "")
        if auth_token:
            # Support both "Bearer xxx" and raw "xxx" formats
            if not auth_token.startswith("Bearer "):
                auth_token = f"Bearer {auth_token}"
            headers["Authorization"] = auth_token

        if not auth_token:
            logger.warning(
                "No auth_token configured for HTTP adapter at %s — "
                "eval endpoints on the target agent are unprotected. "
                "Run 'agenticeval generate-token' to create one.",
                self.base_url,
            )

        self._client = httpx.AsyncClient(base_url=self.base_url, timeout=float(timeout), headers=headers)
        logger.info(f"HTTPAdapter connected to {self.base_url} (timeout={timeout}s)")

    async def disconnect(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    async def health_check(self) -> bool:
        if not self._client: return False
        try:
            resp = await self._client.get(self.endpoints.get("health", "/eval/health"))
            if resp.status_code == 401:
                raise ValueError(
                    "Target agent returned 401 Unauthorized — "
                    "check your auth_token configuration"
                )
            return resp.status_code == 200
        except httpx.RequestError:
            return False

    async def send_test(self, test_data: dict[str, Any], session_id: str | None = None) -> AgentResult:
        if not self._client:
            return AgentResult(messages=[], success=False, error="Not connected")
        endpoint = self.endpoints.get("send_test", "/eval/run")
        logger.info(f"Sending test to {self.base_url}{endpoint}")
        try:
            payload = dict(test_data)
            if session_id is not None:
                payload["session_id"] = session_id
            resp = await self._client.post(endpoint, json=payload)
            if resp.status_code != 200:
                error_msg = f"HTTP {resp.status_code}: {resp.text[:500]}"
                logger.error(f"Agent returned error: {error_msg}")
                return AgentResult(messages=[], success=False, error=error_msg)
            data = resp.json()
            msg_count = len(data.get("messages", []))
            sub_count = len(data.get("sub_agent_messages", []))
            logger.info(f"Agent returned {msg_count} messages, {sub_count} sub-agent messages")
            return AgentResult(
                messages=data.get("messages", []),
                sub_agent_messages=data.get("sub_agent_messages", []),
                metadata=data.get("metadata", {}),
                success=True,
            )
        except httpx.TimeoutException as e:
            logger.error(f"Timeout waiting for agent response: {e}")
            return AgentResult(messages=[], success=False, error=f"Timeout: agent did not respond within the configured timeout. {e}")
        except httpx.RequestError as e:
            logger.error(f"Request error: {e}")
            return AgentResult(messages=[], success=False, error=str(e))

    async def get_judge_llm(self) -> LLMClient | None:
        if not self._client:
            return None
        judge_endpoint = self.endpoints.get("judge", "/eval/judge")
        return HTTPJudgeLLMClient(self._client, judge_endpoint)

    def adapter_type(self) -> str: return "http"
    def target_description(self) -> str: return self._description
