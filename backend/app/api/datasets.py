import csv
import io
import json

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

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
    dataset = await db.get(Dataset, dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    return dataset


@router.put("/datasets/{dataset_id}", response_model=DatasetResponse)
async def update_dataset(
    dataset_id: int, payload: DatasetUpdate, db: AsyncSession = Depends(get_db)
):
    dataset = await db.get(Dataset, dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
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
    dataset = await db.get(Dataset, dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
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
    tc = await db.get(TestCase, testcase_id)
    if not tc:
        raise HTTPException(status_code=404, detail="TestCase not found")
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
    tc = await db.get(TestCase, testcase_id)
    if not tc:
        raise HTTPException(status_code=404, detail="TestCase not found")
    await db.delete(tc)
    await db.commit()


# --- CSV Import/Export ---


@router.get("/datasets/{dataset_id}/export")
async def export_dataset_csv(dataset_id: int, db: AsyncSession = Depends(get_db)):
    dataset = await db.get(Dataset, dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

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
    dataset = await db.get(Dataset, dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

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
