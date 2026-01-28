"""Safety 도메인 — 검증 규칙 정의.

- EXPECTED_HEADERS: 엑셀 슬롯의 필수 헤더
- REASON_CODES: 파이프라인에서 실제 생성되는 사유 코드 + 메시지
"""

from __future__ import annotations


# =========================
# 1) 슬롯별 기대 엑셀 헤더
# =========================
EXPECTED_HEADERS: dict[str, list[str]] = {
    "safety.tbm": ["작업내용", "참석자", "날짜"],

    # 20251126_성광벤드_안전교육이수현황.xlsx 기준
    "safety.education.status": ["부서", "현재_이수인원", "현재_대상인원", "현재_이수율", "전월_이수율"],

    # 소방 점검표 (엑셀로 올릴 때)
    "safety.fire.inspection": ["월", "점검항목", "수량", "결과", "조치내용", "조치기한", "증빙사진ID"],

    # 20251126_성광벤드_위험성평가서.xlsx 기준
    "safety.risk.assessment": ["순번", "작업명(Activity)", "유해위험요인", "감소대책(Action)", "담당자", "점검일", "판정", "테스트 목적"],

    "safety.checklist": ["점검항목", "결과", "날짜"],
}


# =========================
# 2) 파이프라인에서 실제 생성되는 사유 코드
# =========================
REASON_CODES: dict[str, str] = {
    # ── 공통 (extractors/pipeline) ──
    "MISSING_SLOT":       "필수 슬롯 누락",
    "HEADER_MISMATCH":    "필수 헤더 누락",
    "EMPTY_TABLE":        "표/데이터 행이 비어있음",
    "NO_DATE_FOUND":      "날짜 미발견",
    "DATE_MISMATCH":      "점검/교육/작성일이 제출 기간 밖",
    "SIGNATURE_MISSING":  "확인 서명란 미기재",
    "OCR_FAILED":         "OCR 판독 불가",

    # ── 교육 이수현황 (safety.education.status) ──
    "LOW_EDUCATION_RATE": "교육 이수율 기준 미달 (80% 미만)",
    "EDU_DEPT_ZERO":      "특정 부서/직무 이수율 0%",
    "EDU_RATE_SPIKE":     "이수율이 전월 대비 30%p 이상 급변",
    "EDU_FUTURE_DATE":    "교육일이 미래 날짜",

    # ── 위험성평가서 (safety.risk.assessment) ──
    "RISK_ACTION_MISSING":    "감소대책/조치 항목이 비어있음",
    "RISK_OWNER_MISSING":     "담당자 정보 누락",
    "RISK_CHECKDATE_MISSING": "점검일 누락",

    # ── 안전보건관리체계 PDF (safety.management.system) ──
    "MISSING_SECTION_ORG":      "문서에 '조직/책임/권한' 섹션이 없음",
    "MISSING_SECTION_RISK":     "문서에 '위험성평가' 섹션이 없음",
    "MISSING_SECTION_INCIDENT": "문서에 '사고 대응 절차' 섹션이 없음",
    "MISSING_SECTION_TRAINING": "문서에 '교육/점검' 섹션이 없음",
    "MISSING_SECTION_IMPROVE":  "문서에 '개선조치' 섹션이 없음",

    # ── 소방 점검 (safety.fire.inspection) ──
    "FIRE_ALL_GOOD_PATTERN":  "항목이 항상 '양호'로만 반복 (형식 제출 의심)",
    "FIRE_COPYPASTE_PATTERN": "총평/체크패턴이 반복 (복붙 의심)",
}
