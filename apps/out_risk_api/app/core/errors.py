# AI/apps/out_risk_api/app/core/errors.py

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, Optional


# 20260209 이종헌 신규: out_risk_api 공통 에러 코드 표준 정의
class OutRiskErrorCode(str, Enum):
    BAD_REQUEST = "OUT_RISK_BAD_REQUEST"
    VALIDATION_ERROR = "OUT_RISK_VALIDATION_ERROR"
    SEARCH_TIMEOUT = "OUT_RISK_SEARCH_TIMEOUT"
    SEARCH_FAILED = "OUT_RISK_SEARCH_FAILED"
    DETECT_TIMEOUT = "OUT_RISK_DETECT_TIMEOUT"
    CHROMA_TIMEOUT = "OUT_RISK_CHROMA_TIMEOUT"
    CHROMA_FAILED = "OUT_RISK_CHROMA_FAILED"
    LLM_TIMEOUT = "OUT_RISK_LLM_TIMEOUT"
    LLM_FAILED = "OUT_RISK_LLM_FAILED"
    INTERNAL_ERROR = "OUT_RISK_INTERNAL_ERROR"


# 20260209 이종헌 신규: HTTPException(detail=...)에서 재사용할 공통 에러 포맷
def esg_error_detail(
    code: OutRiskErrorCode,
    message: str,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    detail: Dict[str, Any] = {"code": code.value, "message": message}
    if extra:
        detail["extra"] = extra
    return detail
