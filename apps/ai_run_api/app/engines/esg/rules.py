# app/engines/esg/rules.py

"""
ESG 도메인 — rules 메타(헤더 기대치/사유코드)

주의:
- 현재 submit 파이프라인은 XLSX 추출 시 EXPECTED_HEADERS만 참조한다.
- 따라서 여기서는 "너무 빡센 헤더 강제"를 피하고,
  최소한의 키워드 수준으로만 기대치를 둔다.
- 실제 정교한 검증(E3/E9 등)은 (추후) esg/validators.py에서 수행하는 게 맞다.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any

# -------------------------------------------------------
# XLSX 최소 헤더 기대치(너무 엄격하면 실데이터에서 다 깨짐)
# - extractor가 "부분 포함"으로 검사한다는 가정 하에 키워드 중심으로 둔다.
# - 만약 extractor가 "정확 일치"를 강제한다면:
#     => 여기 목록을 빈 리스트로 두고, 검증은 validators에서 하는 편이 안전.
# -------------------------------------------------------
EXPECTED_HEADERS: dict[str, list[str]] = {
    # 전기 사용량: date + kwh 계열
    "esg.energy.electricity.usage": ["date", "kwh"],
    # 전기 고지서(PDF)는 헤더 검사 안 함
    "esg.energy.electricity.bill": [],
    # 가스 사용량: timestamp + m3 or energy
    "esg.energy.gas.usage": ["time", "m3"],
    "esg.energy.gas.bill": [],
    # 수도 사용량
    "esg.energy.water.usage": ["date", "m3"],
    "esg.energy.water.bill": [],
    # GHG 근거 문서(PDF)라서 헤더 없음
    "esg.energy.ghg.evidence": [],
    # 유해물질 목록(있을 때): material + qty 계열
    "esg.hazmat.inventory": ["물질", "수량"],
    # 폐기 목록
    "esg.hazmat.disposal.list": ["물질", "처리"],
    # MSDS/폐기증빙/윤리문서/서약서는 PDF/IMG이므로 헤더 없음
    "esg.hazmat.msds": [],
    "esg.hazmat.disposal.evidence": [],
    "esg.ethics.code": [],
    "esg.ethics.distribution.log": ["배포", "확인"],
    "esg.ethics.pledge": [],
    "esg.ethics.poster.image": [],
}


# -------------------------------------------------------
# reason code 표준(가능한 한 공통 코드 유지)
# -------------------------------------------------------
REASON_CODES: dict[str, str] = {
    # 공통
    "MISSING_SLOT": "필수 슬롯 누락",
    "PARSE_FAILED": "파싱 실패",
    "HEADER_MISMATCH": "필수 컬럼(헤더) 불일치",
    "DATE_MISMATCH": "기간 불일치",
    "UNIT_MISSING": "단위 누락",
    "EVIDENCE_MISSING": "근거문서 누락",
    "OCR_FAILED": "OCR 판독 불가",

    # 에너지(E)
    "E1_NEGATIVE_OR_ZERO": "사용량이 0 또는 음수",
    "E1_DATE_PARSE_FAILED": "날짜 파싱 실패",
    "E1_DUPLICATE_DATE": "날짜 중복",
    "E1_GAP_DETECTED": "기간 연속성 결함",
    "E2_SPIKE_DETECTED": "사용량 급증/급감 이상치",
    "E3_BILL_MISMATCH": "고지서 합계와 사용량 합계 불일치",
    "E3_BILL_PERIOD_UNCERTAIN": "고지서 기간 추출 불확실",
    "E4_GHG_EVIDENCE_MISSING": "온실가스 산정 근거 문서 누락",

    # 유해물질(H)
    "E5_MSDS_MISSING": "유해물질 목록 대비 MSDS 누락",
    "E6_STOCK_SPIKE": "유해물질 수량 급증",
    "E6_INSPECTION_OVERDUE": "점검일 경과",
    "E7_DISPOSAL_INCONSISTENT": "폐기/처리 정합성 불일치",

    # 윤리(G)
    "E8_OLD_REVISION": "윤리강령 개정일이 오래됨",
    "E8_MISSING_SECTIONS": "윤리강령 필수 섹션 누락",
    "E8_MULTI_VERSION": "여러 버전 동시 제출(혼선 가능)",
    "E9_NO_DISTRIBUTION_LOG": "배포/수신확인 로그 누락",
    "E9_NO_PLEDGE": "서약서 누락",
    "E9_PLEDGE_BEFORE_REVISION": "서약일이 개정일보다 과거(구버전 서약 가능성)",
    "E9_DISTR_BEFORE_REVISION": "배포일이 개정일보다 과거(구버전 배포 가능성)",
    "G_OCR_UNREADABLE": "문서 판독 불가(스캔/사진 품질 문제)",

    # LLM 공통
    "LLM_ANOMALY_DETECTED": "AI가 문서 이상 징후를 감지함",
    "LLM_MISSING_FIELDS":   "AI가 누락 항목을 감지함",
    "VIOLATION_DETECTED":   "AI가 위반 사항을 감지함",
}


# -------------------------------------------------------
# (옵션) 데모용 정책값(나중에 validators에서 사용)
# -------------------------------------------------------
POLICY: dict[str, object] = {
    "E3_TOLERANCE_ELECTRICITY_PCT": 1.0,
    "E3_TOLERANCE_GAS_PCT": 2.0,
    "E3_TOLERANCE_WATER_PCT": 2.0,
    "E9_CONFIRM_RATE_WARN": 80,
    "E9_CONFIRM_RATE_FAIL": 60,
}