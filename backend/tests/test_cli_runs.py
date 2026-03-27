from unittest.mock import patch
from typer.testing import CliRunner
from cli.main import app

runner = CliRunner()


class TestRunsListCmd:
    @patch("cli.runs.ApiClient")
    def test_list_runs(self, MockClient):
        mock = MockClient.return_value
        mock.get.return_value = [
            {"id": 1, "name": "run-1", "dataset_id": 1, "scorer_id": 1,
             "adapter_id": 1, "status": "completed",
             "judge_config": {}, "created_at": "2026-01-01T00:00:00",
             "started_at": None, "finished_at": None}
        ]
        result = runner.invoke(app, ["runs", "list"])
        assert result.exit_code == 0
        assert "run-1" in result.stdout

    @patch("cli.runs.ApiClient")
    def test_list_empty(self, MockClient):
        mock = MockClient.return_value
        mock.get.return_value = []
        result = runner.invoke(app, ["runs", "list"])
        assert result.exit_code == 0
        assert "No runs" in result.stdout


class TestRunsGetCmd:
    @patch("cli.runs.ApiClient")
    def test_get_run(self, MockClient):
        mock = MockClient.return_value
        mock.get.return_value = {
            "id": 1, "name": "run-1", "dataset_id": 2, "scorer_id": 3,
            "adapter_id": 4, "status": "completed",
            "judge_config": {"use_target_llm": True},
            "created_at": "2026-01-01T00:00:00",
            "started_at": "2026-01-01T00:01:00",
            "finished_at": "2026-01-01T00:02:00"
        }
        result = runner.invoke(app, ["runs", "get", "1"])
        assert result.exit_code == 0
        assert "run-1" in result.stdout
        assert "completed" in result.stdout


class TestRunsCreateCmd:
    @patch("cli.runs.ApiClient")
    def test_create_run(self, MockClient):
        mock = MockClient.return_value
        mock.post.return_value = {
            "id": 10, "name": "test-run", "dataset_id": 1, "scorer_id": 2,
            "adapter_id": 3, "status": "pending", "judge_config": {},
            "created_at": "2026-01-01", "started_at": None, "finished_at": None
        }
        result = runner.invoke(app, ["runs", "create",
                                     "--dataset", "1", "--scorer", "2", "--adapter", "3",
                                     "--name", "test-run"])
        assert result.exit_code == 0
        assert "test-run" in result.stdout


class TestRunsStartCmd:
    @patch("cli.runs.ApiClient")
    def test_start_run(self, MockClient):
        mock = MockClient.return_value
        mock.post.return_value = {
            "status": "completed",
            "summary": {"total": 5, "passed": 4, "pass_rate": 0.8},
            "events": []
        }
        result = runner.invoke(app, ["runs", "start", "1"])
        assert result.exit_code == 0
        assert "completed" in result.stdout.lower() or "pass" in result.stdout.lower()


class TestRunsResultsCmd:
    @patch("cli.runs.ApiClient")
    def test_results(self, MockClient):
        mock = MockClient.return_value
        mock.get.return_value = [
            {"id": 1, "run_id": 1, "test_case_id": 1, "passed": True,
             "score": {"passed": True}, "judge_reasoning": "Good",
             "agent_messages": [], "duration_ms": 100}
        ]
        result = runner.invoke(app, ["runs", "results", "1"])
        assert result.exit_code == 0
        assert "\u2713" in result.stdout


class TestRunsCompareCmd:
    @patch("cli.runs.ApiClient")
    def test_compare_runs(self, MockClient):
        mock = MockClient.return_value
        mock.get.return_value = {
            "run1": {"id": 1, "summary": {"total": 3, "passed": 2, "pass_rate": 0.67}},
            "run2": {"id": 2, "summary": {"total": 3, "passed": 3, "pass_rate": 1.0}},
            "comparisons": [
                {"test_case_id": 1, "run1_passed": True, "run2_passed": True, "changed": False},
                {"test_case_id": 2, "run1_passed": False, "run2_passed": True, "changed": True},
            ]
        }
        result = runner.invoke(app, ["runs", "compare", "1", "2"])
        assert result.exit_code == 0
        assert "Run 1" in result.stdout or "run1" in result.stdout.lower()


class TestRunsExportCmd:
    @patch("cli.runs.ApiClient")
    def test_export_run(self, MockClient):
        mock = MockClient.return_value
        mock.download.return_value = None
        result = runner.invoke(app, ["runs", "export", "1", "--output", "results.csv"])
        assert result.exit_code == 0
        assert "results.csv" in result.stdout


class TestRunsDeleteCmd:
    @patch("cli.runs.ApiClient")
    def test_delete_run(self, MockClient):
        mock = MockClient.return_value
        mock.delete.return_value = None
        result = runner.invoke(app, ["runs", "delete", "1", "--yes"])
        assert result.exit_code == 0
        assert "Deleted" in result.stdout


class TestTopLevelRunCmd:
    @patch("cli.main.ApiClient")
    def test_run_creates_and_starts(self, MockClient):
        mock = MockClient.return_value
        # First call: POST /api/runs (create), Second call: POST /api/runs/10/start
        mock.post.side_effect = [
            {"id": 10, "name": "quick-run", "dataset_id": 1, "scorer_id": 2,
             "adapter_id": 3, "status": "pending", "judge_config": {},
             "created_at": "2026-01-01", "started_at": None, "finished_at": None},
            {"status": "completed", "summary": {"total": 2, "passed": 2, "pass_rate": 1.0},
             "events": []},
        ]
        result = runner.invoke(app, ["run", "--dataset", "1", "--scorer", "2", "--adapter", "3"])
        assert result.exit_code == 0
        assert "completed" in result.stdout.lower() or "pass" in result.stdout.lower()
        assert mock.post.call_count == 2
