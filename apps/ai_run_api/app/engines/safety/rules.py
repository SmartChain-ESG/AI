"""Safety 도메인 — 검증 룰 (기획서 §5.1)."""

from __future__ import annotations

# 슬롯별 기대 엑셀 헤더
EXPECTED_HEADERS: dict[str, list[str]] = {
    "safety.tbm": ["작업내용", "참석자", "날짜"],
    "safety.education.status": ["교육내용", "교육일", "참석자", "이수율"],
    "safety.fire.inspection": ["점검항목", "결과", "날짜"],
    "safety.risk.assessment": ["항목", "위험도", "날짜", "조치"],
    "safety.checklist": ["점검항목", "결과", "날짜"],
}

# 슬롯별 추가 검증 규칙
REASON_CODES: dict[str, str] = {
    "MISSING_SLOT": "필수 슬롯 누락",
    "DATE_MISMATCH": "점검일이 기간 밖",
    "OCR_FAILED": "OCR 판독 불가",
    "SIGNATURE_MISSING": "서명 누락",
    "HEADER_MISMATCH": "필수 헤더 누락",
    "NO_DATE_FOUND": "날짜 미발견",
    "LOW_EDUCATION_RATE": "교육 이수율 기준 미달",
}
