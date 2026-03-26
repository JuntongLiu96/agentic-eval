import asyncio
import json
import uuid
from typing import Any
from app.bridge.base import AgentResult, BridgeAdapter

class StdioAdapter(BridgeAdapter):
    def __init__(self):
        self.command: str = ""
        self.args: list[str] = []
        self.cwd: str | None = None
        self.timeout_seconds: int = 300
        self._process: asyncio.subprocess.Process | None = None
        self._description: str = ""

    async def connect(self, config: dict[str, Any]) -> None:
        self.command = config["command"]
        self.args = config.get("args", [])
        self.cwd = config.get("cwd")
        self.timeout_seconds = config.get("timeout_seconds", 300)
        self._description = config.get("description", f"Stdio agent: {self.command}")

    async def _ensure_process(self) -> asyncio.subprocess.Process:
        if self._process is None or self._process.returncode is not None:
            self._process = await asyncio.create_subprocess_exec(
                self.command, *self.args,
                stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE, cwd=self.cwd,
            )
        return self._process

    async def disconnect(self) -> None:
        if self._process and self._process.returncode is None:
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
            line = await asyncio.wait_for(process.stdout.readline(), timeout=10)
            if not line: return False
            data = json.loads(line.decode().strip())
            return data.get("type") == "health_ok"
        except (asyncio.TimeoutError, json.JSONDecodeError, OSError):
            return False

    async def send_test(self, test_data: dict[str, Any]) -> AgentResult:
        try:
            process = await self._ensure_process()
            request_id = str(uuid.uuid4())
            msg = json.dumps({"type": "run_test", "id": request_id, "data": test_data}) + "\n"
            process.stdin.write(msg.encode())
            await process.stdin.drain()
            line = await asyncio.wait_for(process.stdout.readline(), timeout=self.timeout_seconds)
            if not line:
                return AgentResult(messages=[], success=False, error="Subprocess closed stdout")
            data = json.loads(line.decode().strip())
            if data.get("type") == "error":
                return AgentResult(messages=[], success=False, error=data.get("message", "Unknown error"))
            return AgentResult(messages=data.get("messages", []), metadata=data.get("metadata", {}), success=True)
        except asyncio.TimeoutError:
            await self.disconnect()
            return AgentResult(messages=[], success=False, error="Adapter timeout")
        except json.JSONDecodeError as e:
            return AgentResult(messages=[], success=False, error=f"Invalid JSON: {e}")
        except OSError as e:
            return AgentResult(messages=[], success=False, error=f"Process error: {e}")

    def adapter_type(self) -> str: return "stdio"
    def target_description(self) -> str: return self._description
