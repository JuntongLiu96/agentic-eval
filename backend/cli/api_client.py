"""Shared HTTP client for CLI commands. Wraps httpx sync calls."""
import httpx
import typer

DEFAULT_TIMEOUT = 30.0

# Global CLI state — holds --base-url value. Shared across all subcommands.
# Lives here (not in main.py) to avoid circular imports between main ↔ subcommands.
state = {"base_url": "http://localhost:8000"}


class ApiClient:
    def __init__(self, base_url: str = "http://localhost:8000", timeout: float = DEFAULT_TIMEOUT):
        self.base_url = base_url
        self.timeout = timeout

    def _url(self, path: str) -> str:
        return f"{self.base_url}{path}"

    def _handle_connect_error(self) -> None:
        typer.echo(
            f"Error: Cannot connect to server at {self.base_url}. "
            "Is the backend running? (Start with: uvicorn app.main:app)",
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
