from unittest.mock import patch
from typer.testing import CliRunner
from cli.main import app

runner = CliRunner()


class TestAdaptersListCmd:
    @patch("cli.adapters.ApiClient")
    def test_list_adapters(self, MockClient):
        mock = MockClient.return_value
        mock.get.return_value = [
            {"id": 1, "name": "http-agent", "adapter_type": "http",
             "config": {"base_url": "http://localhost:5000"},
             "description": "test agent", "created_at": "2026-01-01T00:00:00"}
        ]
        result = runner.invoke(app, ["adapters", "list"])
        assert result.exit_code == 0
        assert "http-agent" in result.stdout

    @patch("cli.adapters.ApiClient")
    def test_list_empty(self, MockClient):
        mock = MockClient.return_value
        mock.get.return_value = []
        result = runner.invoke(app, ["adapters", "list"])
        assert result.exit_code == 0
        assert "No adapters" in result.stdout


class TestAdaptersGetCmd:
    @patch("cli.adapters.ApiClient")
    def test_get_adapter(self, MockClient):
        mock = MockClient.return_value
        mock.get.return_value = {
            "id": 1, "name": "http-agent", "adapter_type": "http",
            "config": {"base_url": "http://localhost:5000"},
            "description": "a service agent", "created_at": "2026-01-01T00:00:00"
        }
        result = runner.invoke(app, ["adapters", "get", "1"])
        assert result.exit_code == 0
        assert "http-agent" in result.stdout
        assert "http://localhost:5000" in result.stdout


class TestAdaptersCreateCmd:
    @patch("cli.adapters.ApiClient")
    def test_create_adapter(self, MockClient):
        mock = MockClient.return_value
        mock.post.return_value = {
            "id": 2, "name": "my-adapter", "adapter_type": "http",
            "config": {"base_url": "http://localhost:3000"},
            "description": "new", "created_at": "2026-01-01"
        }
        result = runner.invoke(app, ["adapters", "create", "--name", "my-adapter",
                                     "--type", "http",
                                     "--config", '{"base_url": "http://localhost:3000"}'])
        assert result.exit_code == 0
        assert "my-adapter" in result.stdout

    @patch("cli.adapters.ApiClient")
    def test_create_http_auto_generates_token(self, MockClient):
        """HTTP adapter without auth_token should auto-generate one."""
        mock = MockClient.return_value
        mock.post.return_value = {
            "id": 3, "name": "auto-token", "adapter_type": "http",
            "config": {"base_url": "http://localhost:5000"},
            "description": "", "created_at": "2026-01-01"
        }
        result = runner.invoke(app, ["adapters", "create", "--name", "auto-token",
                                     "--type", "http",
                                     "--config", '{"base_url": "http://localhost:5000"}'])
        assert result.exit_code == 0
        # Token should be printed in output
        assert "Auto-generated auth token" in result.stdout
        # The POST payload should contain auth_token in config
        call_args = mock.post.call_args
        posted_config = call_args[1]["json"]["config"]
        assert "auth_token" in posted_config
        token = posted_config["auth_token"]
        assert len(token) == 64
        assert all(c in "0123456789abcdef" for c in token)

    @patch("cli.adapters.ApiClient")
    def test_create_http_preserves_existing_token(self, MockClient):
        """HTTP adapter with auth_token already set should not overwrite it."""
        mock = MockClient.return_value
        mock.post.return_value = {
            "id": 4, "name": "existing-token", "adapter_type": "http",
            "config": {"base_url": "http://localhost:5000", "auth_token": "my-custom-token"},
            "description": "", "created_at": "2026-01-01"
        }
        result = runner.invoke(app, ["adapters", "create", "--name", "existing-token",
                                     "--type", "http",
                                     "--config", '{"base_url": "http://localhost:5000", "auth_token": "my-custom-token"}'])
        assert result.exit_code == 0
        # Should NOT show auto-generated message
        assert "Auto-generated auth token" not in result.stdout
        # The POST payload should preserve the original token
        call_args = mock.post.call_args
        posted_config = call_args[1]["json"]["config"]
        assert posted_config["auth_token"] == "my-custom-token"

    @patch("cli.adapters.ApiClient")
    def test_create_non_http_no_auto_token(self, MockClient):
        """Non-HTTP adapter types should not get auto-generated tokens."""
        mock = MockClient.return_value
        mock.post.return_value = {
            "id": 5, "name": "stdio-agent", "adapter_type": "stdio",
            "config": {"command": "python", "args": ["agent.py"]},
            "description": "", "created_at": "2026-01-01"
        }
        result = runner.invoke(app, ["adapters", "create", "--name", "stdio-agent",
                                     "--type", "stdio",
                                     "--config", '{"command": "python", "args": ["agent.py"]}'])
        assert result.exit_code == 0
        assert "Auto-generated auth token" not in result.stdout
        call_args = mock.post.call_args
        posted_config = call_args[1]["json"]["config"]
        assert "auth_token" not in posted_config


class TestAdaptersUpdateCmd:
    @patch("cli.adapters.ApiClient")
    def test_update_config(self, MockClient):
        mock = MockClient.return_value
        mock.put.return_value = {
            "id": 1, "name": "my-adapter", "adapter_type": "http",
            "config": {"base_url": "http://localhost:3000", "auth_token": "Bearer new-token"},
            "description": "updated", "created_at": "2026-01-01"
        }
        result = runner.invoke(app, ["adapters", "update", "1",
                                     "--config", '{"base_url": "http://localhost:3000", "auth_token": "Bearer new-token"}'])
        assert result.exit_code == 0
        assert "Updated" in result.stdout

    @patch("cli.adapters.ApiClient")
    def test_update_nothing(self, MockClient):
        result = runner.invoke(app, ["adapters", "update", "1"])
        assert result.exit_code == 0
        assert "Nothing to update" in result.stdout


class TestAdaptersDeleteCmd:
    @patch("cli.adapters.ApiClient")
    def test_delete_adapter(self, MockClient):
        mock = MockClient.return_value
        mock.delete.return_value = None
        result = runner.invoke(app, ["adapters", "delete", "1", "--yes"])
        assert result.exit_code == 0
        assert "Deleted" in result.stdout


class TestAdaptersCheckCmd:
    @patch("cli.adapters.ApiClient")
    def test_health_check_healthy(self, MockClient):
        mock = MockClient.return_value
        mock.post.return_value = {"healthy": True}
        result = runner.invoke(app, ["adapters", "check", "1"])
        assert result.exit_code == 0
        assert "healthy" in result.stdout.lower() or "✓" in result.stdout

    @patch("cli.adapters.ApiClient")
    def test_health_check_unhealthy(self, MockClient):
        mock = MockClient.return_value
        mock.post.return_value = {"healthy": False, "error": "Connection refused"}
        result = runner.invoke(app, ["adapters", "check", "1"])
        assert result.exit_code == 0
        assert "Connection refused" in result.stdout or "unhealthy" in result.stdout.lower()


class TestGenerateTokenCmd:
    def test_generate_token_outputs_64_char_hex(self):
        result = runner.invoke(app, ["generate-token"])
        assert result.exit_code == 0
        # Output should contain a 64-character hex string (32 bytes)
        lines = result.stdout.strip().split("\n")
        # Find the token line (indented, 64 hex chars)
        token_found = False
        for line in lines:
            stripped = line.strip()
            if len(stripped) == 64 and all(c in "0123456789abcdef" for c in stripped):
                token_found = True
                break
        assert token_found, f"Expected 64-char hex token in output, got:\n{result.stdout}"

    def test_generate_token_shows_usage_instructions(self):
        result = runner.invoke(app, ["generate-token"])
        assert result.exit_code == 0
        assert "auth_token" in result.stdout
        assert "agenticeval adapters create" in result.stdout

    def test_generate_token_produces_unique_tokens(self):
        result1 = runner.invoke(app, ["generate-token"])
        result2 = runner.invoke(app, ["generate-token"])
        # Extract tokens (64-char hex lines)
        def extract_token(output):
            for line in output.strip().split("\n"):
                stripped = line.strip()
                if len(stripped) == 64 and all(c in "0123456789abcdef" for c in stripped):
                    return stripped
            return None
        token1 = extract_token(result1.stdout)
        token2 = extract_token(result2.stdout)
        assert token1 is not None
        assert token2 is not None
        assert token1 != token2
