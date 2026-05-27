from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import update

from app.api.adapters import router as adapters_router
from app.api.datasets import router as datasets_router
from app.api.runs import router as runs_router
from app.api.scorers import router as scorers_router
from app.api.templates import router as templates_router
from app.db.database import async_session, init_db
from app.db.seed import seed_scorer_templates
from app.models.eval_run import EvalRun, RunStatus


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    async with async_session() as session:
        await seed_scorer_templates(session)
        # Reap orphan runs left "running" from a prior process that crashed
        # or was killed — no executor is alive to advance them.
        await session.execute(
            update(EvalRun)
            .where(EvalRun.status == RunStatus.running)
            .values(status=RunStatus.failed, finished_at=datetime.now(timezone.utc))
        )
        await session.commit()
    yield


app = FastAPI(title="AgenticEval", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(adapters_router)
app.include_router(datasets_router)
app.include_router(runs_router)
app.include_router(scorers_router)
app.include_router(templates_router)
