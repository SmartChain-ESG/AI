"""API 라우트 — /run/preview, /run/submit."""

from __future__ import annotations

from fastapi import APIRouter

from app.pipeline.preview import run_preview
from app.pipeline.submit import run_submit
from app.schemas.run import (
    PreviewRequest,
    PreviewResponse,
    SubmitRequest,
    SubmitResponse,
)

router = APIRouter(prefix="/run", tags=["run"])


@router.post("/preview", response_model=PreviewResponse)
async def preview(req: PreviewRequest) -> PreviewResponse:
    """파일이 업로드될 때마다 슬롯 추정 + 필수 항목 현황판 반환."""
    return await run_preview(req)


@router.post("/submit", response_model=SubmitResponse)
async def submit(req: SubmitRequest) -> SubmitResponse:
    """전체 파일 검증 — 다운로드 → 추출 → 룰 검증 → 최종 판정."""
    return await run_submit(req)
