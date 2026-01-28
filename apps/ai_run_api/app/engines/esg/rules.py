"""ESG 도메인 — 검증 룰 (기획서 §5.3). 담당자 확정 후 채울 것."""

from __future__ import annotations

EXPECTED_HEADERS: dict[str, list[str]] = {
    "esg.energy.usage": ["항목", "사용량", "단위", "기간"],
    "esg.energy.bill": ["항목", "금액", "기간"],
    "esg.hazmat.msds": ["물질명", "CAS번호", "위험등급"],
    "esg.ethics.code": ["조항", "내용"],
}

REASON_CODES: dict[str, str] = {
    "MISSING_SLOT": "필수 슬롯 누락",
    "ANOMALY_DETECTED": "사용량 급증/급감 이상치",
    "PERIOD_MISSING": "기간 누락",
    "UNIT_MISSING": "단위 누락",
    "EVIDENCE_MISSING": "근거문서 누락",
    "OCR_FAILED": "OCR 판독 불가",
}
