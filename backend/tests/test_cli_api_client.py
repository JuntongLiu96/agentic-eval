import pytest
from unittest.mock import patch, MagicMock, mock_open
import httpx
from cli.api_client import ApiClient


class TestApiClient:
    def test_default_base_url(self):
        client = ApiClient()
        assert client.base_url == "http://localhost:9100"

    def test_custom_base_url(self):
        client = ApiClient(base_url="http://myhost:9000")
        assert client.base_url == "http://myhost:9000"

    def test_get_builds_url(self):
        client = ApiClient(base_url="http://localhost:9100")
        assert client._url("/api/datasets") == "http://localhost:9100/api/datasets"

    @patch("cli.api_client.httpx.get")
    def test_get_success(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = [{"id": 1, "name": "ds1"}]
        mock_get.return_value = mock_resp
        client = ApiClient()
        result = client.get("/api/datasets")
        assert result == [{"id": 1, "name": "ds1"}]
        mock_get.assert_called_once_with(
            "http://localhost:9100/api/datasets", params=None, timeout=30.0
        )

    @patch("cli.api_client.httpx.get")
    def test_get_error_raises(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_resp.text = '{"detail": "Not found"}'
        mock_get.return_value = mock_resp
        client = ApiClient()
        with pytest.raises(SystemExit):
            client.get("/api/datasets/999")

    @patch("cli.api_client.httpx.get")
    def test_get_connection_error(self, mock_get):
        mock_get.side_effect = httpx.ConnectError("Connection refused")
        client = ApiClient()
        with pytest.raises(SystemExit):
            client.get("/api/datasets")

    @patch("cli.api_client.httpx.post")
    def test_post_success(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_resp.json.return_value = {"id": 1, "name": "new"}
        mock_post.return_value = mock_resp
        client = ApiClient()
        result = client.post("/api/datasets", json={"name": "new"})
        assert result == {"id": 1, "name": "new"}

    @patch("cli.api_client.httpx.post")
    def test_post_with_custom_timeout(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"status": "ok"}
        mock_post.return_value = mock_resp
        client = ApiClient()
        client.post("/api/runs/1/start", timeout=600.0)
        mock_post.assert_called_once_with(
            "http://localhost:9100/api/runs/1/start", json=None, timeout=600.0
        )

    @patch("cli.api_client.httpx.put")
    def test_put_success(self, mock_put):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"id": 1, "name": "updated"}
        mock_put.return_value = mock_resp
        client = ApiClient()
        result = client.put("/api/datasets/1", json={"name": "updated"})
        assert result == {"id": 1, "name": "updated"}

    @patch("cli.api_client.httpx.delete")
    def test_delete_success(self, mock_delete):
        mock_resp = MagicMock()
        mock_resp.status_code = 204
        mock_resp.text = ""
        mock_delete.return_value = mock_resp
        client = ApiClient()
        result = client.delete("/api/datasets/1")
        assert result is None

    @patch("builtins.open", mock_open(read_data=b"fake,data"))
    @patch("cli.api_client.httpx.post")
    def test_upload_file(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"imported_count": 3}
        mock_post.return_value = mock_resp
        client = ApiClient()
        result = client.upload("/api/datasets/1/import", file_path="test.csv", field_name="file")
        assert result == {"imported_count": 3}

    @patch("builtins.open", mock_open())
    @patch("cli.api_client.httpx.get")
    def test_download_file(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b"name,data\ntest,{}"
        mock_get.return_value = mock_resp
        client = ApiClient()
        client.download("/api/datasets/1/export", output_path="out.csv")
        mock_get.assert_called_once()
