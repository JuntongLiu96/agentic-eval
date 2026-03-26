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
