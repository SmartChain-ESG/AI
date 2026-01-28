"""Compliance 도메인 — 설정 및 규칙 정의.

- EXPECTED_HEADERS: 엑셀 슬롯의 필수 헤더
- REASON_CODES: 파이프라인에서 실제 생성되는 사유 코드 + 메시지
"""

from __future__ import annotations

# =========================================================
# 1) 슬롯별 기대 엑셀/테이블 헤더
# =========================================================
EXPECTED_HEADERS: dict[str, list[str]] = {
    "compliance.contract.sample": ["구분", "비율", "지급금액", "지급기일"],
    "compliance.education.privacy": ["사번", "성명", "소속", "과정명", "이수여부"],
    "compliance.fair.trade": ["점검자", "위험요소발견", "조치완료여부", "비고"],
}

# =========================================================
# 2) 파이프라인에서 실제 생성되는 사유 코드
# =========================================================
REASON_CODES: dict[str, str] = {
    # ── 공통 ──
    "MISSING_SLOT":   "필수 슬롯 누락",
    "HEADER_MISMATCH": "필수 헤더(컬럼) 누락",
    "EMPTY_TABLE":    "표/데이터 행이 비어있음",
    "OCR_FAILED":     "OCR 판독 불가/텍스트 추출 실패",
    "WRONG_YEAR":     "문서 대상 연도 불일치 (2025년 아님)",

    # ── 표준 근로/하도급 계약서 ──
    "KEYWORD_MISSING": "표준 계약서 필수 조항(선급금/지연이자 등) 누락",

    # ── 개인정보 교육 이수현황 ──
    "LOW_EDUCATION_RATE": "교육 이수율 기준 미달 (미이수 20% 초과)",
    "DATA_NOT_FOUND":     "교육 명단 데이터 식별 불가",

    # ── 공정거래 자율 점검표 ──
    "HIGH_RISK_DETECTED": "위험요소가 발견되었으나 조치되지 않음 (Risk:Y / Action:N)",

    # ── 법정의무 교육 계획서 ──
    "MISSING_MANDATORY_TRAINING": "주요 법정의무 교육(개인정보/성희롱/안전 등) 계획 누락",
}