"""Shared helpers for adapters that drive a child process over stdio.

Both ``StdioAdapter`` and ``OpenClawAdapter`` spawn a subprocess and exchange
newline-delimited JSON on stdin/stdout, while draining stderr in the
background.  The two copies of ``_drain_stderr`` and ``_read_json_line`` were
nearly identical — only the log prefix differed — so they live here.

This module intentionally does **not** provide a shared ``_ensure_process``:
each adapter builds its argv/env differently (one uses ``config['command']``,
the other builds ``openclaw acp ...`` with a post-spawn ACP handshake), so the
spawn logic stays in the subclasses.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


class SubprocessAdapter:
    """Mixin with shared stdout/stderr helpers for stdio subprocess adapters.

    Subclasses must set ``self._process`` to the
    ``asyncio.subprocess.Process`` they spawned.  A ``_log_prefix`` attribute
    (string) may be provided to tag log lines; it defaults to
    ``"subprocess"``.
    """

    _process: asyncio.subprocess.Process | None
    _log_prefix: str = "subprocess"

    async def _drain_stderr(self) -> None:
        """Read stderr in background and log it.

        Prevents the stderr pipe buffer from filling and blocking the child.
        """
        proc = self._process
        if not proc or not proc.stderr:
            return
        try:
            while True:
                line = await proc.stderr.readline()
                if not line:
                    break
                text = line.decode().strip()
                if text:
                    logger.debug("[%s stderr] %s", self._log_prefix, text)
        except Exception:  # noqa: BLE001 — stderr drain must never raise
            pass

    async def _read_json_line(self, timeout: float) -> dict[str, Any] | None:
        """Read one valid JSON line from stdout, skipping non-JSON lines.

        Non-JSON lines (Electron GPU logs, DevTools messages, etc.) are
        skipped with a debug log so that the adapter is tolerant of noisy
        children.  Returns ``None`` if stdout is closed.  Raises
        ``asyncio.TimeoutError`` if no valid line arrives within *timeout*
        seconds.
        """
        proc = self._process
        if not proc or not proc.stdout:
            return None
        deadline = asyncio.get_event_loop().time() + timeout
        while True:
            remaining = deadline - asyncio.get_event_loop().time()
            if remaining <= 0:
                raise asyncio.TimeoutError()
            line = await asyncio.wait_for(proc.stdout.readline(), timeout=remaining)
            if not line:
                return None
            text = line.decode().strip()
            if not text:
                continue
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                logger.debug(
                    "[%s stdout, skipping non-JSON] %s",
                    self._log_prefix,
                    text[:200],
                )
                continue
