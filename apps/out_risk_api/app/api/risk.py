# AI/apps/out_risk_api/app/api/risk.py

from __future__ import annotations

import asyncio
from fastapi import APIRouter, HTTPException

from app.core.config import CHROMA_PERSIST_DIR
from app.core.errors import OutRiskErrorCode, esg_error_detail
from app.pipeline.detect import esg_detect_external_risk_batch, esg_search_preview
from app.schemas.risk import (
    ExternalRiskDetectBatchRequest,
    ExternalRiskDetectBatchResponse,
    SearchPreviewRequest,
    SearchPreviewResponse,
)


router = APIRouter(prefix="/risk", tags=["risk"])


# 20260211 이종헌 수정: detect API 타임아웃 확장 및 표준 에러 포맷 적용
@router.post("/external/detect", response_model=ExternalRiskDetectBatchResponse)
async def esg_api_external_detect(req: ExternalRiskDetectBatchRequest) -> ExternalRiskDetectBatchResponse:
    try:
        return await asyncio.wait_for(esg_detect_external_risk_batch(req), timeout=65.0)
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=504,
            detail=esg_error_detail(OutRiskErrorCode.DETECT_TIMEOUT, "Detect timed out"),
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=esg_error_detail(OutRiskErrorCode.INTERNAL_ERROR, str(e)),
        )


# 20260211 이종헌 수정: search preview API 표준 에러 포맷 적용
@router.post("/external/search/preview", response_model=SearchPreviewResponse)
async def esg_api_external_search_preview(req: SearchPreviewRequest) -> SearchPreviewResponse:
    try:
        return await asyncio.wait_for(esg_search_preview(req), timeout=8.0)
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=504,
            detail=esg_error_detail(OutRiskErrorCode.SEARCH_TIMEOUT, "Search preview timed out"),
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=esg_error_detail(OutRiskErrorCode.SEARCH_FAILED, str(e)),
        )


# 20260201 이종헌 신규: Chroma heartbeat 동기 호출 헬퍼
def _chroma_heartbeat_sync() -> dict:
    import chromadb

    client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)
    heartbeat = client.heartbeat()
    return {"status": "ok", "heartbeat": heartbeat}


# 20260211 이종헌 수정: heartbeat API 표준 에러 포맷 적용
@router.get("/external/heartbeat")
async def chroma_heartbeat() -> dict:
    try:
        return await asyncio.wait_for(asyncio.to_thread(_chroma_heartbeat_sync), timeout=2.0)
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=504,
            detail=esg_error_detail(OutRiskErrorCode.CHROMA_TIMEOUT, "Chroma heartbeat timed out"),
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=esg_error_detail(OutRiskErrorCode.CHROMA_FAILED, str(e)),
        )
