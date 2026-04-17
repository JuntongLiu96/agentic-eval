"""OpenClaw Bridge Adapter — evaluates an OpenClaw Agent via the ACP bridge.

Spawns ``openclaw acp`` as a subprocess and speaks ACP (JSON-RPC 2.0 over stdio)
to drive a Gateway-backed agent session.  The adapter also exposes the OpenClaw
LLM proxy (``localhost:4140/v1``) as a judge LLM so evaluations can reuse the
same model provider.
"""

import asyncio
import json
import logging
import re
import uuid
from pathlib import Path
from typing import Any

import httpx

from app.bridge.base import AgentResult, BridgeAdapter, LLMClient
from app.bridge.subprocess_base import SubprocessAdapter

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Judge LLM — proxies through the OpenClaw LLM endpoint (OpenAI-compatible)
# ---------------------------------------------------------------------------

class OpenClawJudgeLLMClient:
    """LLMClient that calls the OpenClaw LLM proxy (OpenAI chat/completions)."""

    def __init__(self, client: httpx.AsyncClient, model: str):
        self._client = client
        self._model = model

    async def chat(self, messages: list[dict[str, str]]) -> str:
        resp = await self._client.post(
            "/chat/completions",
            json={"model": self._model, "messages": messages},
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]


# ---------------------------------------------------------------------------
# ACP helpers
# ---------------------------------------------------------------------------

def _jsonrpc_request(method: str, params: dict[str, Any], req_id: int) -> bytes:
    """Build a JSON-RPC 2.0 request line."""
    obj = {"jsonrpc": "2.0", "id": req_id, "method": method, "params": params}
    return (json.dumps(obj, separators=(",", ":")) + "\n").encode()


# ---------------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------------

class OpenClawAdapter(SubprocessAdapter, BridgeAdapter):
    """Bridge adapter that drives an OpenClaw Agent through the ACP bridge."""

    _log_prefix = "acp"

    def __init__(self) -> None:
        # Connection config
        self.gateway_url: str = ""
        self.auth_token: str = ""
        self.agent_id: str = "mew"
        self.session_key: str = ""
        self.timeout_seconds: int = 3600
        self.startup_timeout: int = 30
        self.llm_base_url: str = "http://localhost:4140"
        self.judge_model: str = "claude-sonnet-4.6"

        # Skills injection
        self.skills_dir: str = ""
        self._skills_prefix: str = ""

        # Internal state
        self._process: asyncio.subprocess.Process | None = None
        self._description: str = ""
        self._req_id: int = 0
        self._llm_client: httpx.AsyncClient | None = None

    # -- lifecycle -----------------------------------------------------------

    async def connect(self, config: dict[str, Any]) -> None:
        self.gateway_url = config.get("gateway_url", "ws://127.0.0.1:18789")
        self.auth_token = config.get("auth_token", "")
        self.agent_id = config.get("agent_id", "mew")
        self.session_key = config.get(
            "session_key", f"agent:{self.agent_id}:eval-{uuid.uuid4().hex[:8]}"
        )
        self.timeout_seconds = config.get("timeout_seconds", 3600)
        self.startup_timeout = config.get("startup_timeout", 30)
        self.llm_base_url = config.get("llm_base_url", "http://localhost:4140")
        self.judge_model = config.get("judge_model", "claude-sonnet-4.6")
        self.skills_dir = config.get("skills_dir", "")
        self._skills_prefix = self._load_skills(self.skills_dir) if self.skills_dir else ""
        self._description = config.get(
            "description",
            f"OpenClaw agent ({self.agent_id}) via {self.gateway_url}",
        )
        logger.info(
            "OpenClawAdapter configured: gateway=%s agent=%s session=%s timeout=%ds",
            self.gateway_url, self.agent_id, self.session_key, self.timeout_seconds,
        )

    async def disconnect(self) -> None:
        if self._process and self._process.returncode is None:
            logger.info("Terminating ACP bridge subprocess (pid=%s)", self._process.pid)
            self._process.terminate()
            try:
                await asyncio.wait_for(self._process.wait(), timeout=5)
            except asyncio.TimeoutError:
                self._process.kill()
        self._process = None
        # NOTE: _llm_client is intentionally NOT closed here.
        # disconnect() may be called between test cases (e.g. on timeout),
        # and the judge LLM client must survive for subsequent scoring.
        # Use close() for final teardown.

    async def close(self) -> None:
        """Final teardown — close the judge LLM client and any subprocess."""
        await self.disconnect()
        if self._llm_client:
            await self._llm_client.aclose()
            self._llm_client = None

    # -- Skills loading ------------------------------------------------------

    @staticmethod
    def _load_skills(skills_dir: str) -> str:
        """Scan *skills_dir* for SKILL.md files and build an injection prefix."""
        skills_path = Path(skills_dir)
        if not skills_path.is_dir():
            logger.warning("skills_dir does not exist or is not a directory: %s", skills_dir)
            return ""

        parts: list[str] = []
        for child in sorted(skills_path.iterdir()):
            skill_file = child / "SKILL.md"
            if not child.is_dir() or not skill_file.is_file():
                continue
            try:
                raw = skill_file.read_text(encoding="utf-8")
            except OSError as exc:
                logger.warning("Failed to read %s: %s", skill_file, exc)
                continue

            # Parse optional YAML frontmatter to extract name
            name = child.name
            body = raw
            fm_match = re.match(r"^---\s*\n(.*?)\n---\s*\n", raw, re.DOTALL)
            if fm_match:
                fm_text = fm_match.group(1)
                body = raw[fm_match.end():]
                # Lightweight name extraction (avoid heavy yaml dependency)
                for line in fm_text.splitlines():
                    if line.startswith("name:"):
                        name = line.split(":", 1)[1].strip().strip('"').strip("'")
                        break

            parts.append(f"## Skill: {name}\n{body.strip()}")
            logger.info("Loaded skill '%s' from %s", name, skill_file)

        if not parts:
            return ""

        header = (
            "[Available Skills]\n"
            "You have the following skills available. "
            "Read the skill content carefully and use the tools as described.\n\n"
        )
        return header + "\n\n".join(parts) + "\n[End Available Skills]\n\n"

    # -- ACP subprocess management ------------------------------------------

    async def _ensure_process(self) -> asyncio.subprocess.Process:
        """Start the ``openclaw acp`` bridge if not already running."""
        if self._process is not None and self._process.returncode is None:
            return self._process

        args = ["openclaw", "acp", "--session", self.session_key]
        if self.gateway_url:
            args.extend(["--url", self.gateway_url])
        if self.auth_token:
            args.extend(["--token", self.auth_token])

        logger.info("Starting ACP bridge: %s", " ".join(args))
        self._process = await asyncio.create_subprocess_exec(
            *args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        asyncio.create_task(self._drain_stderr())
        logger.info("ACP bridge started (pid=%s)", self._process.pid)

        # ACP initialize handshake
        await self._acp_initialize()
        return self._process

    def _next_id(self) -> int:
        self._req_id += 1
        return self._req_id

    async def _send_rpc(self, method: str, params: dict[str, Any]) -> int:
        """Send a JSON-RPC request and return the request id."""
        proc = await self._ensure_process()
        req_id = self._next_id()
        data = _jsonrpc_request(method, params, req_id)
        proc.stdin.write(data)  # type: ignore[union-attr]
        await proc.stdin.drain()  # type: ignore[union-attr]
        return req_id

    async def _call_rpc(
        self, method: str, params: dict[str, Any], timeout: float | None = None
    ) -> dict:
        """Send a JSON-RPC request and wait for the matching response."""
        timeout = timeout or self.timeout_seconds
        req_id = await self._send_rpc(method, params)
        deadline = asyncio.get_event_loop().time() + timeout
        while True:
            remaining = deadline - asyncio.get_event_loop().time()
            if remaining <= 0:
                raise asyncio.TimeoutError(f"Timeout waiting for RPC response to {method}")
            msg = await self._read_json_line(remaining)
            if msg is None:
                raise RuntimeError("ACP bridge closed stdout")
            # Skip notifications (no 'id' field)
            if "id" not in msg:
                logger.debug("[acp notification] %s", msg.get("method", "unknown"))
                continue
            if msg.get("id") == req_id:
                if "error" in msg:
                    err = msg["error"]
                    raise RuntimeError(
                        f"ACP error {err.get('code')}: {err.get('message', '')}"
                    )
                return msg.get("result", {})

    async def _acp_initialize(self) -> dict:
        """Perform the ACP initialize handshake."""
        result = await self._call_rpc(
            "initialize",
            {
                "protocolVersion": 1,
                "clientInfo": {"name": "agentic-eval", "version": "1.0.0"},
                "capabilities": {},
            },
            timeout=self.startup_timeout,
        )
        logger.info("ACP initialized: %s", result.get("agentInfo", {}))

        # Load (or create) the session so session/prompt can find it
        load_result = await self._call_rpc(
            "session/load",
            {
                "sessionId": self.session_key,
                "cwd": "/home/gerard",
                "mcpServers": [],
            },
            timeout=self.startup_timeout,
        )
        logger.info("ACP session loaded: %s", self.session_key)
        return result

    # -- BridgeAdapter interface --------------------------------------------

    async def health_check(self) -> bool:
        try:
            proc = await self._ensure_process()
            return proc.returncode is None
        except Exception as e:
            logger.warning("Health check failed: %s", e)
            return False

    async def send_test(self, test_data: dict[str, Any]) -> AgentResult:
        """Send a prompt to the OpenClaw agent and collect the response.

        ``test_data`` must contain a ``prompt`` key (the user message).
        Additional keys are passed as context metadata.
        """
        prompt = test_data.get("prompt", "")
        if not prompt:
            return AgentResult(
                messages=[], success=False, error="No prompt in test_data"
            )

        # Prepend skill context when available
        if self._skills_prefix:
            prompt = self._skills_prefix + prompt

        try:
            await self._ensure_process()

            # Build content parts for ACP session/prompt
            prompt_parts = [{"type": "text", "text": prompt}]

            req_id = await self._send_rpc(
                "session/prompt",
                {"sessionId": self.session_key, "prompt": prompt_parts},
            )

            # Collect streaming events until we get the final response
            messages: list[dict[str, Any]] = []
            sub_agent_messages: list[dict[str, Any]] = []
            metadata: dict[str, Any] = {}
            deadline = asyncio.get_event_loop().time() + self.timeout_seconds

            # Add the user message
            messages.append({"role": "user", "content": prompt})

            assistant_text_parts: list[str] = []
            tool_calls: list[dict[str, Any]] = []

            while True:
                remaining = deadline - asyncio.get_event_loop().time()
                if remaining <= 0:
                    logger.error("Timeout waiting for agent response (%ds)", self.timeout_seconds)
                    # Return what we have so far
                    if assistant_text_parts:
                        messages.append({
                            "role": "assistant",
                            "content": "".join(assistant_text_parts),
                        })
                    return AgentResult(
                        messages=messages,
                        sub_agent_messages=sub_agent_messages,
                        metadata=metadata,
                        success=False,
                        error=f"Timeout: agent did not complete within {self.timeout_seconds}s",
                    )

                msg = await self._read_json_line(remaining)
                if msg is None:
                    break

                # JSON-RPC response with our request id — final result
                if msg.get("id") == req_id:
                    if "error" in msg:
                        err = msg["error"]
                        error_msg = f"ACP error {err.get('code')}: {err.get('message', '')}"
                        logger.error("Agent returned error: %s", error_msg)
                        if assistant_text_parts:
                            messages.append({
                                "role": "assistant",
                                "content": "".join(assistant_text_parts),
                            })
                        return AgentResult(
                            messages=messages,
                            sub_agent_messages=sub_agent_messages,
                            metadata=metadata,
                            success=False,
                            error=error_msg,
                        )

                    # Result received — extract final content
                    result = msg.get("result", {})
                    result_content = result.get("content", [])
                    for part in result_content:
                        if isinstance(part, dict) and part.get("type") == "text":
                            assistant_text_parts.append(part.get("text", ""))

                    if assistant_text_parts:
                        messages.append({
                            "role": "assistant",
                            "content": "".join(assistant_text_parts),
                        })

                    metadata["acp_result"] = result
                    break

                # Notification — streaming events
                method = msg.get("method", "")
                params = msg.get("params", {})

                if method == "session/update":
                    # ACP session update notifications — extract message content
                    update = params.get("update", {})
                    update_type = update.get("sessionUpdate", "")
                    if update_type == "agent_message_chunk":
                        # Streaming text chunk from the agent
                        content = update.get("content", {})
                        chunk_text = content.get("text", "") if isinstance(content, dict) else str(content)
                        if chunk_text:
                            assistant_text_parts.append(chunk_text)
                    elif update_type == "tool_call":
                        tool_info = {
                            "type": "tool_call",
                            "method": method,
                            "name": update.get("name", update.get("toolName", "")),
                            "status": "started",
                        }
                        if update.get("input"):
                            tool_info["input"] = update["input"]
                        sub_agent_messages.append(tool_info)
                    elif update_type == "tool_call_update":
                        tool_info = {
                            "type": "tool_call",
                            "method": method,
                            "name": update.get("name", update.get("toolName", "")),
                            "status": "completed",
                        }
                        if update.get("output"):
                            tool_info["output"] = update["output"]
                        if update.get("input"):
                            tool_info["input"] = update["input"]
                        sub_agent_messages.append(tool_info)
                    else:
                        logger.debug("[acp session/update] type=%s", update_type)

                elif method == "notifications/message":
                    # Streaming text chunk (legacy notification format)
                    role = params.get("role", "assistant")
                    content_data = params.get("content", "")
                    if isinstance(content_data, str) and content_data:
                        assistant_text_parts.append(content_data)

                elif method in (
                    "notifications/tool_call",
                    "notifications/tool_call_update",
                ):
                    tool_info = {
                        "type": "tool_call",
                        "method": method,
                        "name": params.get("name", ""),
                        "status": params.get("status", ""),
                    }
                    if params.get("input"):
                        tool_info["input"] = params["input"]
                    if params.get("output"):
                        tool_info["output"] = params["output"]
                    sub_agent_messages.append(tool_info)

                elif method == "notifications/subagent":
                    sub_agent_messages.append({
                        "type": "subagent",
                        "method": method,
                        **params,
                    })

                # Other notifications are logged and skipped
                else:
                    logger.debug("[acp event] %s", method or "unknown")

            msg_count = len(messages)
            sub_count = len(sub_agent_messages)
            logger.info(
                "Agent returned %d messages, %d sub-agent messages",
                msg_count, sub_count,
            )
            return AgentResult(
                messages=messages,
                sub_agent_messages=sub_agent_messages,
                metadata=metadata,
                success=True,
            )

        except asyncio.TimeoutError as e:
            logger.error("Timeout: %s", e)
            await self.disconnect()
            return AgentResult(
                messages=[], success=False,
                error=f"Timeout: agent did not respond within {self.timeout_seconds}s",
            )
        except Exception as e:
            logger.error("send_test error: %s", e)
            return AgentResult(messages=[], success=False, error=str(e))

    async def get_judge_llm(self) -> LLMClient | None:
        if not self._llm_client or self._llm_client.is_closed:
            self._llm_client = httpx.AsyncClient(
                base_url=self.llm_base_url, timeout=120.0
            )
        return OpenClawJudgeLLMClient(self._llm_client, self.judge_model)

    def adapter_type(self) -> str:
        return "openclaw"

    def target_description(self) -> str:
        return self._description
