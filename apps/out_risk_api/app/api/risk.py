# AI/apps/out_risk_api/app/api/risk.py

from __future__ import annotations

import asyncio
from fastapi import APIRouter, HTTPException

from app.core.config import CHROMA_PERSIST_DIR
from app.pipeline.detect import esg_detect_external_risk_batch, esg_search_preview
from app.schemas.risk import (
    ExternalRiskDetectBatchRequest,
    ExternalRiskDetectBatchResponse,
    SearchPreviewRequest,
    SearchPreviewResponse,
)


router = APIRouter(prefix="/risk", tags=["risk"])


@router.post("/external/detect", response_model=ExternalRiskDetectBatchResponse)
async def esg_api_external_detect(req: ExternalRiskDetectBatchRequest) -> ExternalRiskDetectBatchResponse:
    try:
        return await asyncio.wait_for(esg_detect_external_risk_batch(req), timeout=20.0)
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Detect timed out")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/external/search/preview", response_model=SearchPreviewResponse)
async def esg_api_external_search_preview(req: SearchPreviewRequest) -> SearchPreviewResponse:
    try:
        return await asyncio.wait_for(esg_search_preview(req), timeout=8.0)
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Search preview timed out")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _chroma_heartbeat_sync() -> dict:
    import chromadb

    client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)
    heartbeat = client.heartbeat()
    return {"status": "ok", "heartbeat": heartbeat}


@router.get("/external/heartbeat")
async def chroma_heartbeat() -> dict:
    try:
        return await asyncio.wait_for(asyncio.to_thread(_chroma_heartbeat_sync), timeout=2.0)
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Chroma heartbeat timed out")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
