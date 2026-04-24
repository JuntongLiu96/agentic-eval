import asyncio
import json
import logging
import uuid
from typing import Any
from app.bridge.base import AgentResult, BridgeAdapter, LLMClient
from app.bridge.subprocess_base import SubprocessAdapter

logger = logging.getLogger(__name__)


class StdioJudgeLLMClient:
    """LLMClient that sends judge requests through the target's stdin/stdout."""

    def __init__(self, adapter: "StdioAdapter"):
        self._adapter = adapter

    async def chat(self, messages: list[dict[str, str]]) -> str:
        process = await self._adapter._ensure_process()
        msg = json.dumps({"type": "judge", "messages": messages}) + "\n"
        process.stdin.write(msg.encode())
        await process.stdin.drain()
        line = await self._adapter._read_json_line(self._adapter.timeout_seconds)
        if line is None:
            raise RuntimeError("Subprocess closed stdout during judge call")
        if line.get("type") == "error":
            raise RuntimeError(line.get("message", "Judge call failed"))
        return line.get("content", "")


class StdioAdapter(SubprocessAdapter, BridgeAdapter):
    _log_prefix = "subprocess"

    def __init__(self):
        self.command: str = ""
        self.args: list[str] = []
        self.cwd: str | None = None
        self.timeout_seconds: int = 3600
        self.startup_timeout: int = 30
        self._process: asyncio.subprocess.Process | None = None
        self._description: str = ""

    async def connect(self, config: dict[str, Any]) -> None:
        self.command = config["command"]
        self.args = config.get("args", [])
        self.cwd = config.get("cwd")
        self.timeout_seconds = config.get("timeout_seconds", 3600)
        self.startup_timeout = config.get("startup_timeout", 30)
        self._description = config.get("description", f"Stdio agent: {self.command}")
        logger.info(f"StdioAdapter configured: {self.command} {' '.join(self.args)} (cwd={self.cwd}, timeout={self.timeout_seconds}s)")

    async def _ensure_process(self) -> asyncio.subprocess.Process:
        if self._process is None or self._process.returncode is not None:
            logger.info(f"Starting subprocess: {self.command} {' '.join(self.args)}")
            self._process = await asyncio.create_subprocess_exec(
                self.command, *self.args,
                stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE, cwd=self.cwd,
            )
            # Start a background task to drain stderr (log it, don't let it block)
            asyncio.create_task(self._drain_stderr())
            logger.info(f"Subprocess started (pid={self._process.pid})")
        return self._process

    async def disconnect(self) -> None:
        if self._process and self._process.returncode is None:
            logger.info(f"Terminating subprocess (pid={self._process.pid})")
            self._process.terminate()
            try: await asyncio.wait_for(self._process.wait(), timeout=5)
            except asyncio.TimeoutError: self._process.kill()
            self._process = None

    async def health_check(self) -> bool:
        try:
            process = await self._ensure_process()
            msg = json.dumps({"type": "health_check"}) + "\n"
            process.stdin.write(msg.encode())
            await process.stdin.drain()
            data = await self._read_json_line(self.startup_timeout)
            if data is None:
                return False
            return data.get("type") == "health_ok"
        except (asyncio.TimeoutError, OSError) as e:
            logger.warning(f"Health check failed: {e}")
            return False

    async def send_test(self, test_data: dict[str, Any], session_id: str | None = None) -> AgentResult:
        try:
            process = await self._ensure_process()
            request_id = str(uuid.uuid4())
            request_msg = {"type": "run_test", "id": request_id, "data": test_data}
            if session_id is not None:
                request_msg["session_id"] = session_id
            msg = json.dumps(request_msg) + "\n"
            logger.info(f"Sending test to subprocess (id={request_id[:8]})")
            process.stdin.write(msg.encode())
            await process.stdin.drain()
            data = await self._read_json_line(self.timeout_seconds)
            if data is None:
                return AgentResult(messages=[], success=False, error="Subprocess closed stdout")
            if data.get("type") == "error":
                error_msg = data.get("message", "Unknown error")
                logger.error(f"Subprocess returned error: {error_msg}")
                return AgentResult(messages=[], success=False, error=error_msg)
            msg_count = len(data.get("messages", []))
            sub_count = len(data.get("sub_agent_messages", []))
            logger.info(f"Subprocess returned {msg_count} messages, {sub_count} sub-agent messages")
            return AgentResult(
                messages=data.get("messages", []),
                sub_agent_messages=data.get("sub_agent_messages", []),
                metadata=data.get("metadata", {}),
                success=True,
            )
        except asyncio.TimeoutError:
            logger.error(f"Timeout waiting for subprocess response ({self.timeout_seconds}s)")
            await self.disconnect()
            return AgentResult(messages=[], success=False, error=f"Timeout: subprocess did not respond within {self.timeout_seconds}s")
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON from subprocess: {e}")
            return AgentResult(messages=[], success=False, error=f"Invalid JSON: {e}")
        except OSError as e:
            logger.error(f"Process error: {e}")
            return AgentResult(messages=[], success=False, error=f"Process error: {e}")

    async def get_judge_llm(self) -> LLMClient | None:
        return StdioJudgeLLMClient(self)

    def adapter_type(self) -> str: return "stdio"
    def target_description(self) -> str: return self._description
