"""FastAPI application entry point."""

from __future__ import annotations

from fastapi import FastAPI

from app.api.run import router

app = FastAPI(
    title="AI Run API",
    version="1.0.0",
    description="협력사 자료(PDF/XLSX/이미지)를 도메인(safety/compliance/esg)별로 자동 검증하는 공통 엔진",
)

app.include_router(router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
