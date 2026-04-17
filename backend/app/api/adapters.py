import json
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api._helpers import db_get_or_404
from app.bridge.registry import create_adapter
from app.db.database import get_db
from app.models.adapter import Adapter
from app.schemas.adapter import AdapterCreate, AdapterResponse, AdapterUpdate

router = APIRouter(prefix="/api", tags=["adapters"])

@router.post("/adapters", response_model=AdapterResponse, status_code=201)
async def create_adapter_endpoint(payload: AdapterCreate, db: AsyncSession = Depends(get_db)):
    adapter = Adapter(name=payload.name, adapter_type=payload.adapter_type,
                     config=json.dumps(payload.config), description=payload.description)
    db.add(adapter)
    await db.commit()
    await db.refresh(adapter)
    return adapter

@router.get("/adapters", response_model=list[AdapterResponse])
async def list_adapters(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Adapter).order_by(Adapter.created_at.desc()))
    return result.scalars().all()

@router.get("/adapters/{adapter_id}", response_model=AdapterResponse)
async def get_adapter(adapter_id: int, db: AsyncSession = Depends(get_db)):
    return await db_get_or_404(Adapter, adapter_id, db, detail="Adapter not found")

@router.put("/adapters/{adapter_id}", response_model=AdapterResponse)
async def update_adapter(adapter_id: int, payload: AdapterUpdate, db: AsyncSession = Depends(get_db)):
    adapter = await db_get_or_404(Adapter, adapter_id, db, detail="Adapter not found")
    if payload.name is not None: adapter.name = payload.name
    if payload.adapter_type is not None: adapter.adapter_type = payload.adapter_type
    if payload.config is not None: adapter.config = json.dumps(payload.config)
    if payload.description is not None: adapter.description = payload.description
    await db.commit()
    await db.refresh(adapter)
    return adapter

@router.delete("/adapters/{adapter_id}", status_code=204)
async def delete_adapter(adapter_id: int, db: AsyncSession = Depends(get_db)):
    adapter = await db_get_or_404(Adapter, adapter_id, db, detail="Adapter not found")
    await db.delete(adapter)
    await db.commit()

@router.post("/adapters/{adapter_id}/health")
async def health_check_adapter(adapter_id: int, db: AsyncSession = Depends(get_db)):
    adapter_row = await db_get_or_404(Adapter, adapter_id, db, detail="Adapter not found")
    try:
        bridge = create_adapter(adapter_row.adapter_type)
        config = json.loads(adapter_row.config)
        await bridge.connect(config)
        healthy = await bridge.health_check()
        await bridge.disconnect()
        return {"healthy": healthy}
    except Exception as e:
        return {"healthy": False, "error": str(e)}
