from unittest.mock import patch
from typer.testing import CliRunner
from cli.main import app

runner = CliRunner()


class TestTemplatesListCmd:
    @patch("cli.templates.ApiClient")
    def test_list_templates(self, MockClient):
        mock = MockClient.return_value
        mock.get.return_value = [
            {"id": 1, "name": "Tool Correctness", "description": "test",
             "category": "tool-correctness", "output_format": "binary",
             "template_prompt": "...", "example_scorer": {}, "usage_instructions": "..."}
        ]
        result = runner.invoke(app, ["templates", "list"])
        assert result.exit_code == 0
        assert "Tool Correctness" in result.stdout

    @patch("cli.templates.ApiClient")
    def test_list_empty(self, MockClient):
        mock = MockClient.return_value
        mock.get.return_value = []
        result = runner.invoke(app, ["templates", "list"])
        assert result.exit_code == 0
        assert "No templates" in result.stdout


class TestTemplatesGetCmd:
    @patch("cli.templates.ApiClient")
    def test_get_template(self, MockClient):
        mock = MockClient.return_value
        mock.get.return_value = {
            "id": 1, "name": "Tool Correctness", "description": "Check tool calls",
            "category": "tool-correctness", "output_format": "binary",
            "template_prompt": "You are evaluating...",
            "example_scorer": {"name": "example"},
            "usage_instructions": "Copy the prompt and..."
        }
        result = runner.invoke(app, ["templates", "get", "1"])
        assert result.exit_code == 0
        assert "Tool Correctness" in result.stdout
        assert "You are evaluating" in result.stdout
