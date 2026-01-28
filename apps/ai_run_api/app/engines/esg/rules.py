# app/engines/esg/rules.py

"""
ESG 도메인 — 룰/임계값/간단 파서
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

# ── 헤더 기대값 (extract_xlsx가 HEADER_MISMATCH를 만들 때 사용) ──
EXPECTED_HEADERS: dict[str, list[str]] = {
    # 전기/가스/수도 usage (데모 파일 컬럼 기준)
    "esg.energy.electricity.usage_xlsx": ["date", "Usage_kWh"],
    "esg.energy.gas.usage_xlsx": ["timestamp", "flow_m3"],
    "esg.energy.water.usage_xlsx": ["date", "Usage_m3"],

    # 배포 로그(예시)
    "esg.governance.distribution_log_xlsx": ["문서명", "버전", "개정일"],
}

REASON_CODES: dict[str, str] = {
    # 공통
    "MISSING_SLOT": "필수 슬롯 누락",
    "HEADER_MISMATCH": "엑셀 컬럼 불일치",
    "PARSE_FAILED": "파싱 실패",

    # E1
    "E1_NEGATIVE_OR_ZERO": "음수/0 사용량 존재",
    "E1_DATE_PARSE_FAIL": "날짜 파싱 실패",
    "E1_DATE_DUPLICATED": "날짜 중복",
    "E1_UNIT_MISSING": "단위 추정 불가",

    # E2
    "E2_SPIKE_WARN": "급증/급감 감지(WARN)",
    "E2_SPIKE_FAIL": "급증/급감 감지(FAIL)",

    # E3
    "E3_BILL_FIELDS_MISSING": "고지서에서 기간/합계 추출 실패",
    "E3_BILL_MISMATCH": "고지서 합계와 XLSX 합계 불일치",

    # E4
    "E4_GHG_EVIDENCE_MISSING": "온실가스 산정 근거자료 누락",

    # E5~E7
    "E5_MSDS_MISSING": "목록 대비 MSDS 누락",
    "E7_DISPOSAL_INCONSISTENT": "폐기/처리 정합성 불일치",

    # E8~E9
    "E8_REVISION_OLD": "윤리강령 개정일이 오래됨",
    "E8_SECTION_MISSING": "윤리강령 필수 섹션 누락",
    "E9_PLEDGE_BEFORE_REVISION": "서약일이 개정일보다 과거",
    "E9_DISTRIBUTION_LOW_ACK": "배포 확인율 낮음",

    # OCR/이미지
    "G_OCR_UNREADABLE": "스캔/사진 판독 불가(OCR)",
}


def esg_parse_date_any(text: str) -> date | None:
    """YYYY-MM-DD / YYYY.MM.DD / YYYY/MM/DD 같은 패턴 1개만 뽑기"""
    if not text:
        return None
    m = re.search(r"(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})", text)
    if not m:
        return None
    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    try:
        return date(y, mo, d)
    except ValueError:
        return None


def esg_parse_bill_fields(pdf_text: str) -> dict[str, Any]:
    """
    고지서에서 기간/합계 뽑기 (아주 단순한 데모 파서)
    - 당월 사용량 134,340 kWh
    - 당월 사용량 18,480 m³
    """
    out: dict[str, Any] = {
        "bill_total": None,
        "bill_unit": None,
        "bill_period_start": None,
        "bill_period_end": None,
    }
    if not pdf_text:
        return out

    # 합계: "당월 사용량 134,340 kWh" / "당월사용량 18,480 m³"
    m = re.search(r"당월\s*사용량\s*([\d,]+)\s*(kwh|㎾h|m3|m³|㎥)", pdf_text, re.IGNORECASE)
    if m:
        out["bill_total"] = float(m.group(1).replace(",", ""))
        out["bill_unit"] = m.group(2)

    # 기간: "2025.11.01 ~ 2025.11.30" 같은 단순 패턴
    m2 = re.search(
        r"(\d{4}[.\-/]\d{1,2}[.\-/]\d{1,2})\s*[~\-]\s*(\d{4}[.\-/]\d{1,2}[.\-/]\d{1,2})",
        pdf_text,
    )
    if m2:
        out["bill_period_start"] = esg_parse_date_any(m2.group(1))
        out["bill_period_end"] = esg_parse_date_any(m2.group(2))

    return out


def esg_spike_threshold(ratio: float) -> str | None:
    """
    ratio = today / baseline
    - WARN: >= 1.25 or <= 0.75
    - FAIL: >= 1.50 or <= 0.50
    """
    if ratio >= 1.50 or ratio <= 0.50:
        return "FAIL"
    if ratio >= 1.25 or ratio <= 0.75:
        return "WARN"
    return None