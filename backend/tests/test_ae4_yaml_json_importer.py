"""AE-4: structured YAML/JSON dataset importer.

CSV round-trips lose structure for nested ``data`` / ``expected_result`` /
``metadata`` fields. The YAML/JSON importer accepts a document of shape
``{name, rows: [{name, data, expected_result, metadata}, ...]}`` and creates the
Dataset + TestCases directly.
"""

from __future__ import annotations

import io
import json

import pytest
import yaml


DOC = {
    "name": "evomem-code-agent",
    "description": "AE-4 import smoke",
    "target_type": "custom",
    "tags": ["evomem", "code_agent"],
    "rows": [
        {
            "name": "CA-001",
            "data": {"prompt": "Upgrade Spring Boot 2.7 to 3.2"},
            "expected_result": {"must_present": ["jakarta"]},
            "metadata": {"case_id": "CA-001", "scope": {"org_id": "acme"}},
        },
        {
            "name": "CA-009",
            "data": {"prompt": "Novel task"},
            "expected_result": {},
            "metadata": {"case_id": "CA-009"},
        },
    ],
}


async def _assert_dataset_created(client, resp, expected_rows: int):
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["name"] == "evomem-code-agent"
    assert body["tags"] == ["evomem", "code_agent"]

    cases = await client.get(f"/api/datasets/{body['id']}/testcases")
    assert cases.status_code == 200
    rows = cases.json()
    assert len(rows) == expected_rows
    names = sorted(r["name"] for r in rows)
    assert names == ["CA-001", "CA-009"]
    # Nested data round-trips as a JSON string in the cell.
    ca001 = next(r for r in rows if r["name"] == "CA-001")
    data = ca001["data"]
    if isinstance(data, str):
        data = json.loads(data)
    assert data == {"prompt": "Upgrade Spring Boot 2.7 to 3.2"}


@pytest.mark.asyncio
async def test_import_yaml_creates_dataset_and_test_cases(client):
    payload = yaml.safe_dump(DOC).encode("utf-8")
    resp = await client.post(
        "/api/datasets/import-yaml",
        files={"file": ("cases.yaml", payload, "application/x-yaml")},
    )
    await _assert_dataset_created(client, resp, expected_rows=2)


@pytest.mark.asyncio
async def test_import_json_creates_dataset_and_test_cases(client):
    payload = json.dumps(DOC).encode("utf-8")
    resp = await client.post(
        "/api/datasets/import-json",
        files={"file": ("cases.json", payload, "application/json")},
    )
    await _assert_dataset_created(client, resp, expected_rows=2)


@pytest.mark.asyncio
async def test_import_yaml_rejects_invalid_doc(client):
    bad = b"rows:\n  - just_a_row_no_top_name: true\n"
    resp = await client.post(
        "/api/datasets/import-yaml",
        files={"file": ("bad.yaml", bad, "application/x-yaml")},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_import_json_rejects_malformed_json(client):
    resp = await client.post(
        "/api/datasets/import-json",
        files={"file": ("bad.json", b"{not json", "application/json")},
    )
    assert resp.status_code == 400
