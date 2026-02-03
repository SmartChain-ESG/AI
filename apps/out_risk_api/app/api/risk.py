# AI/apps/out_risk_api/app/api/risk.py

from __future__ import annotations

from fastapi import APIRouter, HTTPException
import chromadb

from app.schemas.risk import (
    ExternalRiskDetectBatchRequest,
    ExternalRiskDetectBatchResponse,
    SearchPreviewRequest,
    SearchPreviewResponse,
)

from app.pipeline.detect import esg_detect_external_risk_batch, esg_search_preview  # 신규: preview 함수 연결


router = APIRouter(prefix="/risk", tags=["risk"])


@router.post("/external/detect", response_model=ExternalRiskDetectBatchResponse)
async def esg_api_external_detect(req: ExternalRiskDetectBatchRequest) -> ExternalRiskDetectBatchResponse:
    try:
        return await esg_detect_external_risk_batch(req)  # 수정: async pipeline이면 반드시 await
    except Exception as e:
        # 수정: 500 원인 추적을 위해 최소한의 메시지만 래핑 (traceback은 서버 콘솔에 남도록)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/external/search/preview", response_model=SearchPreviewResponse)
async def esg_api_external_search_preview(req: SearchPreviewRequest) -> SearchPreviewResponse:
    try:
        return await esg_search_preview(req)  # 신규: Streamlit preview 404 제거
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/risk/external/heartbeat")
async def chroma_heartbeat():
    try:
        # 로컬/서버 모드에 따라 설정 (path는 프로젝트 구조에 맞게 수정)
        client = chromadb.PersistentClient(path="./chroma_db") 
        heartbeat = client.heartbeat() # Chroma 서버 살아있는지 확인
        return {"status": "ok", "heartbeat": heartbeat}
    except Exception as e:
        return {"status": "error", "message": str(e)}, 500