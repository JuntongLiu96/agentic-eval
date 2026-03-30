from unittest.mock import patch, MagicMock
from typer.testing import CliRunner
from cli.main import app

runner = CliRunner()


class TestDatasetsListCmd:
    @patch("cli.datasets.ApiClient")
    def test_list_datasets(self, MockClient):
        mock = MockClient.return_value
        mock.get.return_value = [
            {"id": 1, "name": "ds1", "description": "test", "target_type": "tool",
             "tags": ["a"], "created_at": "2026-01-01T00:00:00", "updated_at": "2026-01-01T00:00:00"}
        ]
        result = runner.invoke(app, ["datasets", "list"])
        assert result.exit_code == 0
        assert "ds1" in result.stdout

    @patch("cli.datasets.ApiClient")
    def test_list_datasets_empty(self, MockClient):
        mock = MockClient.return_value
        mock.get.return_value = []
        result = runner.invoke(app, ["datasets", "list"])
        assert result.exit_code == 0
        assert "No datasets" in result.stdout


class TestDatasetsGetCmd:
    @patch("cli.datasets.ApiClient")
    def test_get_dataset(self, MockClient):
        mock = MockClient.return_value
        mock.get.return_value = {
            "id": 1, "name": "ds1", "description": "test desc",
            "target_type": "tool", "tags": ["a", "b"],
            "created_at": "2026-01-01T00:00:00", "updated_at": "2026-01-01T00:00:00"
        }
        result = runner.invoke(app, ["datasets", "get", "1"])
        assert result.exit_code == 0
        assert "ds1" in result.stdout
        assert "test desc" in result.stdout


class TestDatasetsCreateCmd:
    @patch("cli.datasets.ApiClient")
    def test_create_dataset(self, MockClient):
        mock = MockClient.return_value
        mock.post.return_value = {"id": 5, "name": "newds", "description": "new",
                                  "target_type": "tool", "tags": [],
                                  "created_at": "2026-01-01T00:00:00", "updated_at": "2026-01-01T00:00:00"}
        result = runner.invoke(app, ["datasets", "create", "--name", "newds",
                                     "--description", "new", "--target-type", "tool"])
        assert result.exit_code == 0
        assert "newds" in result.stdout


class TestDatasetsDeleteCmd:
    @patch("cli.datasets.ApiClient")
    def test_delete_dataset(self, MockClient):
        mock = MockClient.return_value
        mock.delete.return_value = None
        result = runner.invoke(app, ["datasets", "delete", "1", "--yes"])
        assert result.exit_code == 0
        assert "Deleted" in result.stdout


class TestDatasetsImportCmd:
    @patch("cli.datasets.ApiClient")
    def test_import_csv(self, MockClient):
        mock = MockClient.return_value
        mock.upload.return_value = {"imported_count": 3}
        result = runner.invoke(app, ["datasets", "import-csv", "1", "--file", "data.csv"])
        assert result.exit_code == 0
        assert "3" in result.stdout


class TestDatasetsExportCmd:
    @patch("cli.datasets.ApiClient")
    def test_export_csv(self, MockClient):
        mock = MockClient.return_value
        mock.download.return_value = None
        result = runner.invoke(app, ["datasets", "export-csv", "1", "--output", "out.csv"])
        assert result.exit_code == 0
        assert "out.csv" in result.stdout


class TestAddCaseCmd:
    @patch("cli.datasets.ApiClient")
    def test_add_case(self, MockClient):
        mock = MockClient.return_value
        mock.post.return_value = {"id": 10, "name": "tc1", "dataset_id": 1,
                                  "data": {"prompt": "What is 2+2?"},
                                  "expected_result": {"answer": "4"}, "metadata": {}}
        result = runner.invoke(app, ["datasets", "add-case", "1",
                                     "--name", "tc1",
                                     "--prompt", "What is 2+2?",
                                     "--expected", '{"answer": "4"}'])
        assert result.exit_code == 0
        assert "tc1" in result.stdout


class TestListCasesCmd:
    @patch("cli.datasets.ApiClient")
    def test_list_cases(self, MockClient):
        mock = MockClient.return_value
        mock.get.return_value = [
            {"id": 1, "name": "tc1", "dataset_id": 1,
             "data": {"prompt": "What is 2+2?"}, "expected_result": {"answer": "4"}, "metadata": {}}
        ]
        result = runner.invoke(app, ["datasets", "list-cases", "1"])
        assert result.exit_code == 0
        assert "tc1" in result.stdout

    @patch("cli.datasets.ApiClient")
    def test_list_cases_empty(self, MockClient):
        mock = MockClient.return_value
        mock.get.return_value = []
        result = runner.invoke(app, ["datasets", "list-cases", "1"])
        assert result.exit_code == 0
        assert "No test cases" in result.stdout


class TestDeleteCaseCmd:
    @patch("cli.datasets.ApiClient")
    def test_delete_case(self, MockClient):
        mock = MockClient.return_value
        mock.delete.return_value = None
        result = runner.invoke(app, ["datasets", "delete-case", "1", "--yes"])
        assert result.exit_code == 0
        assert "Deleted" in result.stdout
