import os

from fastapi import FastAPI, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://visionops:visionops@localhost:5432/visionops",
)

engine = create_async_engine(DATABASE_URL, pool_pre_ping=True)
app = FastAPI(title="VisionOps API")


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/health/db")
async def health_db():
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"db unreachable: {type(exc).__name__}")
    return {"db": "ok"}