from unittest.mock import patch
from typer.testing import CliRunner
from cli.main import app

runner = CliRunner()


class TestScorersListCmd:
    @patch("cli.scorers.ApiClient")
    def test_list_scorers(self, MockClient):
        mock = MockClient.return_value
        mock.get.return_value = [
            {"id": 1, "name": "sc1", "description": "test", "output_format": "binary",
             "eval_prompt": "...", "criteria": {}, "score_range": None,
             "pass_threshold": None, "tags": [],
             "created_at": "2026-01-01T00:00:00", "updated_at": "2026-01-01T00:00:00"}
        ]
        result = runner.invoke(app, ["scorers", "list"])
        assert result.exit_code == 0
        assert "sc1" in result.stdout

    @patch("cli.scorers.ApiClient")
    def test_list_empty(self, MockClient):
        mock = MockClient.return_value
        mock.get.return_value = []
        result = runner.invoke(app, ["scorers", "list"])
        assert result.exit_code == 0
        assert "No scorers" in result.stdout


class TestScorersGetCmd:
    @patch("cli.scorers.ApiClient")
    def test_get_scorer(self, MockClient):
        mock = MockClient.return_value
        mock.get.return_value = {
            "id": 1, "name": "sc1", "description": "desc", "output_format": "binary",
            "eval_prompt": "Judge this", "criteria": {"conditions": []},
            "score_range": None, "pass_threshold": None, "tags": ["a"],
            "created_at": "2026-01-01T00:00:00", "updated_at": "2026-01-01T00:00:00"
        }
        result = runner.invoke(app, ["scorers", "get", "1"])
        assert result.exit_code == 0
        assert "sc1" in result.stdout
        assert "Judge this" in result.stdout


class TestScorersCreateCmd:
    @patch("cli.scorers.ApiClient")
    def test_create_scorer(self, MockClient):
        mock = MockClient.return_value
        mock.post.return_value = {"id": 5, "name": "new-scorer", "description": "new",
                                  "output_format": "binary", "eval_prompt": "judge",
                                  "criteria": {}, "score_range": None, "pass_threshold": None,
                                  "tags": [], "created_at": "2026-01-01", "updated_at": "2026-01-01"}
        result = runner.invoke(app, ["scorers", "create", "--name", "new-scorer",
                                     "--output-format", "binary",
                                     "--eval-prompt", "judge"])
        assert result.exit_code == 0
        assert "new-scorer" in result.stdout


class TestScorersDeleteCmd:
    @patch("cli.scorers.ApiClient")
    def test_delete_scorer(self, MockClient):
        mock = MockClient.return_value
        mock.delete.return_value = None
        result = runner.invoke(app, ["scorers", "delete", "1", "--yes"])
        assert result.exit_code == 0
        assert "Deleted" in result.stdout
