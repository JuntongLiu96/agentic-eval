"""Shared HTTP client for CLI commands. Wraps httpx sync calls."""
import json
import re
import httpx
import typer

DEFAULT_TIMEOUT = 30.0

# Global CLI state — holds --base-url value. Shared across all subcommands.
# Lives here (not in main.py) to avoid circular imports between main ↔ subcommands.
state = {"base_url": "http://localhost:9100"}


def parse_json_arg(text: str, arg_name: str = "--config") -> dict:
    """Parse a JSON string from a CLI argument, handling PowerShell quoting issues.

    PowerShell often mangles JSON by stripping inner quotes, turning
    '{"base_url": "http://localhost:8000"}' into '{base_url: http://localhost:8000}'.
    This function attempts to repair such mangled JSON before parsing.
    """
    # First try standard parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try to repair PowerShell-mangled JSON: {key: value} → {"key": "value"}
    repaired = text.strip()
    # Add quotes around unquoted keys: {base_url: → {"base_url":
    repaired = re.sub(r'{\s*(\w+)\s*:', r'{"\1":', repaired)
    repaired = re.sub(r',\s*(\w+)\s*:', r', "\1":', repaired)
    # Add quotes around unquoted string values (not numbers/bools/null)
    # Match ': value' where value is not already quoted, not a number, not true/false/null
    repaired = re.sub(
        r':\s*(?!")((?:https?://)?[^\s,}]+)',
        lambda m: ': "' + m.group(1) + '"' if not re.match(r'^(\d+\.?\d*|true|false|null)$', m.group(1)) else ': ' + m.group(1),
        repaired,
    )

    try:
        return json.loads(repaired)
    except json.JSONDecodeError:
        typer.echo(f"Error: Invalid JSON in {arg_name}: {text}", err=True)
        raise SystemExit(1)


class ApiClient:
    def __init__(self, base_url: str = "http://localhost:9100", timeout: float = DEFAULT_TIMEOUT):
        self.base_url = base_url
        self.timeout = timeout

    def _url(self, path: str) -> str:
        return f"{self.base_url}{path}"

    def _handle_connect_error(self) -> None:
        typer.echo(
            f"Error: Cannot connect to server at {self.base_url}. "
            "Is the backend running? (Start with: uvicorn app.main:app --port 9100)",
            err=True,
        )
        raise SystemExit(1)

    def _handle_error(self, resp: httpx.Response) -> None:
        try:
            detail = resp.json().get("detail", resp.text)
        except Exception:
            detail = resp.text
        typer.echo(f"Error {resp.status_code}: {detail}", err=True)
        raise SystemExit(1)

    def get(self, path: str, params: dict | None = None):
        try:
            resp = httpx.get(self._url(path), params=params, timeout=self.timeout)
        except httpx.ConnectError:
            self._handle_connect_error()
        if resp.status_code >= 400:
            self._handle_error(resp)
        if resp.status_code == 204 or not resp.text:
            return None
        return resp.json()

    def post(self, path: str, json: dict | None = None, timeout: float | None = None):
        try:
            resp = httpx.post(self._url(path), json=json, timeout=timeout or self.timeout)
        except httpx.ConnectError:
            self._handle_connect_error()
        if resp.status_code >= 400:
            self._handle_error(resp)
        if resp.status_code == 204 or not resp.text:
            return None
        return resp.json()

    def put(self, path: str, json: dict | None = None):
        try:
            resp = httpx.put(self._url(path), json=json, timeout=self.timeout)
        except httpx.ConnectError:
            self._handle_connect_error()
        if resp.status_code >= 400:
            self._handle_error(resp)
        if resp.status_code == 204 or not resp.text:
            return None
        return resp.json()

    def delete(self, path: str):
        try:
            resp = httpx.delete(self._url(path), timeout=self.timeout)
        except httpx.ConnectError:
            self._handle_connect_error()
        if resp.status_code >= 400:
            self._handle_error(resp)
        return None

    def upload(self, path: str, file_path: str, field_name: str = "file"):
        try:
            with open(file_path, "rb") as f:
                resp = httpx.post(self._url(path), files={field_name: f}, timeout=self.timeout)
        except httpx.ConnectError:
            self._handle_connect_error()
        if resp.status_code >= 400:
            self._handle_error(resp)
        return resp.json()

    def download(self, path: str, output_path: str) -> None:
        try:
            resp = httpx.get(self._url(path), timeout=self.timeout)
        except httpx.ConnectError:
            self._handle_connect_error()
        if resp.status_code >= 400:
            self._handle_error(resp)
        with open(output_path, "wb") as f:
            f.write(resp.content)
