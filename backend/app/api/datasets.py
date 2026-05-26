import csv
import io
import json
from typing import Any

import yaml
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api._helpers import db_get_or_404
from app.db.database import get_db
from app.models.dataset import Dataset, TestCase
from app.schemas.dataset import (
    DatasetCreate,
    DatasetResponse,
    DatasetUpdate,
    TestCaseCreate,
    TestCaseResponse,
    TestCaseUpdate,
)

router = APIRouter(prefix="/api", tags=["datasets"])


# --- Dataset CRUD ---


@router.post("/datasets", response_model=DatasetResponse, status_code=201)
async def create_dataset(payload: DatasetCreate, db: AsyncSession = Depends(get_db)):
    dataset = Dataset(
        name=payload.name,
        description=payload.description,
        target_type=payload.target_type,
        tags=json.dumps(payload.tags),
    )
    db.add(dataset)
    await db.commit()
    await db.refresh(dataset)
    return dataset


@router.get("/datasets", response_model=list[DatasetResponse])
async def list_datasets(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Dataset).order_by(Dataset.created_at.desc()))
    return result.scalars().all()


@router.get("/datasets/{dataset_id}", response_model=DatasetResponse)
async def get_dataset(dataset_id: int, db: AsyncSession = Depends(get_db)):
    return await db_get_or_404(Dataset, dataset_id, db, detail="Dataset not found")


@router.put("/datasets/{dataset_id}", response_model=DatasetResponse)
async def update_dataset(
    dataset_id: int, payload: DatasetUpdate, db: AsyncSession = Depends(get_db)
):
    dataset = await db_get_or_404(Dataset, dataset_id, db, detail="Dataset not found")
    if payload.name is not None:
        dataset.name = payload.name
    if payload.description is not None:
        dataset.description = payload.description
    if payload.target_type is not None:
        dataset.target_type = payload.target_type
    if payload.tags is not None:
        dataset.tags = json.dumps(payload.tags)
    await db.commit()
    await db.refresh(dataset)
    return dataset


@router.delete("/datasets/{dataset_id}", status_code=204)
async def delete_dataset(dataset_id: int, db: AsyncSession = Depends(get_db)):
    dataset = await db.get(Dataset, dataset_id, options=[selectinload(Dataset.test_cases)])
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    await db.delete(dataset)
    await db.commit()


# --- TestCase CRUD ---


@router.post(
    "/datasets/{dataset_id}/testcases", response_model=TestCaseResponse, status_code=201
)
async def create_test_case(
    dataset_id: int, payload: TestCaseCreate, db: AsyncSession = Depends(get_db)
):
    await db_get_or_404(Dataset, dataset_id, db, detail="Dataset not found")
    tc = TestCase(
        dataset_id=dataset_id,
        name=payload.name,
        data=json.dumps(payload.data),
        expected_result=json.dumps(payload.expected_result),
        metadata_=json.dumps(payload.metadata),
    )
    db.add(tc)
    await db.commit()
    await db.refresh(tc)
    return tc


@router.get("/datasets/{dataset_id}/testcases", response_model=list[TestCaseResponse])
async def list_test_cases(dataset_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(TestCase).where(TestCase.dataset_id == dataset_id)
    )
    return result.scalars().all()


@router.put("/testcases/{testcase_id}", response_model=TestCaseResponse)
async def update_test_case(
    testcase_id: int, payload: TestCaseUpdate, db: AsyncSession = Depends(get_db)
):
    tc = await db_get_or_404(TestCase, testcase_id, db, detail="TestCase not found")
    if payload.name is not None:
        tc.name = payload.name
    if payload.data is not None:
        tc.data = json.dumps(payload.data)
    if payload.expected_result is not None:
        tc.expected_result = json.dumps(payload.expected_result)
    if payload.metadata is not None:
        tc.metadata_ = json.dumps(payload.metadata)
    await db.commit()
    await db.refresh(tc)
    return tc


@router.delete("/testcases/{testcase_id}", status_code=204)
async def delete_test_case(testcase_id: int, db: AsyncSession = Depends(get_db)):
    tc = await db_get_or_404(TestCase, testcase_id, db, detail="TestCase not found")
    await db.delete(tc)
    await db.commit()


# --- CSV Import/Export ---


@router.get("/datasets/{dataset_id}/export")
async def export_dataset_csv(dataset_id: int, db: AsyncSession = Depends(get_db)):
    dataset = await db_get_or_404(Dataset, dataset_id, db, detail="Dataset not found")

    result = await db.execute(
        select(TestCase).where(TestCase.dataset_id == dataset_id)
    )
    test_cases = result.scalars().all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["name", "data", "expected_result", "metadata"])
    for tc in test_cases:
        writer.writerow([tc.name, tc.data, tc.expected_result, tc.metadata_])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={dataset.name}.csv"},
    )


@router.post("/datasets/{dataset_id}/import")
async def import_dataset_csv(
    dataset_id: int,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    await db_get_or_404(Dataset, dataset_id, db, detail="Dataset not found")

    content = await file.read()
    text = content.decode("utf-8")
    reader = csv.DictReader(io.StringIO(text))

    required_cols = {"name", "data", "expected_result"}
    if not required_cols.issubset(set(reader.fieldnames or [])):
        raise HTTPException(
            status_code=400,
            detail=f"CSV must contain columns: {required_cols}. Got: {reader.fieldnames}",
        )

    count = 0
    for row in reader:
        tc = TestCase(
            dataset_id=dataset_id,
            name=row["name"],
            data=row["data"],
            expected_result=row["expected_result"],
            metadata_=row.get("metadata", "{}"),
        )
        db.add(tc)
        count += 1

    await db.commit()
    return {"imported_count": count}


# --- AE-4: YAML / JSON dataset import ---


def _coerce_cell(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, str):
        return v
    return json.dumps(v)


async def _create_dataset_from_doc(
    doc: dict, db: AsyncSession
) -> Dataset:
    if not isinstance(doc, dict) or "name" not in doc:
        raise HTTPException(
            status_code=400,
            detail="Document must be an object with a top-level 'name' and 'rows'.",
        )
    rows = doc.get("rows") or []
    if not isinstance(rows, list):
        raise HTTPException(status_code=400, detail="'rows' must be a list.")

    dataset = Dataset(
        name=doc["name"],
        description=doc.get("description", ""),
        target_type=doc.get("target_type", "custom"),
        tags=json.dumps(doc.get("tags", []) or []),
    )
    db.add(dataset)
    await db.flush()

    for row in rows:
        if not isinstance(row, dict) or "name" not in row:
            raise HTTPException(
                status_code=400, detail="Each row must be an object with a 'name'."
            )
        tc = TestCase(
            dataset_id=dataset.id,
            name=row["name"],
            data=_coerce_cell(row.get("data", {})),
            expected_result=_coerce_cell(row.get("expected_result", {})),
            metadata_=_coerce_cell(row.get("metadata", {})),
        )
        db.add(tc)
    await db.commit()
    await db.refresh(dataset)
    return dataset


@router.post("/datasets/import-yaml", response_model=DatasetResponse, status_code=201)
async def import_dataset_yaml(
    file: UploadFile = File(...), db: AsyncSession = Depends(get_db)
):
    """AE-4: Create a dataset + test cases from a structured YAML upload.

    Document shape: ``{name, description?, target_type?, tags?, rows: [{name, data,
    expected_result, metadata}, ...]}``. Avoids the CSV round-trip's lossy
    stringification of nested ``data`` / ``expected_result`` / ``metadata``.
    """
    content = await file.read()
    try:
        doc = yaml.safe_load(content.decode("utf-8"))
    except yaml.YAMLError as e:
        raise HTTPException(status_code=400, detail=f"Invalid YAML: {e}")
    return await _create_dataset_from_doc(doc, db)


@router.post("/datasets/import-json", response_model=DatasetResponse, status_code=201)
async def import_dataset_json(
    file: UploadFile = File(...), db: AsyncSession = Depends(get_db)
):
    """AE-4: Same as import-yaml but accepts a JSON document."""
    content = await file.read()
    try:
        doc = json.loads(content.decode("utf-8"))
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {e}")
    return await _create_dataset_from_doc(doc, db)
