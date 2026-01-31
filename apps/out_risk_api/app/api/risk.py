# AI/apps/out_risk_api/app/api/risk.py

# 20260131 이종헌 신규: POST /risk/external/detect 라우터(파이프라인 호출만 담당)
from fastapi import APIRouter

from app.pipeline.detect import esg_detect_external_risk
from app.schemas.risk import ExternalRiskDetectRequest, ExternalRiskDetectResponse

router = APIRouter()


@router.post("/risk/external/detect", response_model=ExternalRiskDetectResponse)
def esg_post_external_detect(payload: ExternalRiskDetectRequest) -> ExternalRiskDetectResponse:
    return esg_detect_external_risk(payload)
