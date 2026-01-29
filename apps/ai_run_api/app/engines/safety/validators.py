"""Safety 도메인 — 슬롯별 세부 검증 로직.

extractor가 뽑아낸 결과(dict)를 받아 추가 reason 코드를 반환한다.
slot_name에 따라 해당 검증만 실행된다.
"""

from __future__ import annotations

import re
from datetime import date

import pandas as pd


# ── 교육 이수현황 (safety.education.status) ──────────────
_EDU_RATE_THRESHOLD = 80.0  # 이수율 기준(%)


def _validate_education(extracted: dict, df_preview: str) -> list[str]:
    """교육 이수현황 xlsx 전용 검증."""
    reasons: list[str] = []
    try:
        import io
        df = pd.read_csv(io.StringIO(df_preview))
    except Exception:
        return reasons

    # (1) 빈 테이블
    if df.empty or len(df) == 0:
        reasons.append("EMPTY_TABLE")
        return reasons

    # (2) 이수율 기준 미달
    rate_cols = [c for c in df.columns if "이수율" in str(c) and "전월" not in str(c)]
    for col in rate_cols:
        for val in df[col].dropna():
            try:
                num = float(str(val).replace("%", ""))
                if num < _EDU_RATE_THRESHOLD:
                    reasons.append("LOW_EDUCATION_RATE")
                    break
            except (ValueError, TypeError):
                pass
        if "LOW_EDUCATION_RATE" in reasons:
            break

    # (3) 특정 부서 이수율 0%
    for col in rate_cols:
        for val in df[col].dropna():
            try:
                num = float(str(val).replace("%", ""))
                if num == 0.0:
                    reasons.append("EDU_DEPT_ZERO")
                    break
            except (ValueError, TypeError):
                pass
        if "EDU_DEPT_ZERO" in reasons:
            break

    # (4) 이수율 전월 대비 급변 (±30%p)
    cur_cols = [c for c in df.columns if "현재" in str(c) and "이수율" in str(c)]
    prev_cols = [c for c in df.columns if "전월" in str(c) and "이수율" in str(c)]
    if cur_cols and prev_cols:
        try:
            cur = df[cur_cols[0]].apply(lambda v: float(str(v).replace("%", "")) if pd.notna(v) else None)
            prev = df[prev_cols[0]].apply(lambda v: float(str(v).replace("%", "")) if pd.notna(v) else None)
            diff = (cur - prev).dropna().abs()
            if (diff > 30).any():
                reasons.append("EDU_RATE_SPIKE")
        except Exception:
            pass

    # (5) 미래 날짜 교육일
    date_re = re.compile(r"(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})")
    today = date.today()
    for col in df.columns:
        if "날짜" in str(col) or "일자" in str(col) or "교육일" in str(col):
            for val in df[col].dropna().astype(str):
                for m in date_re.findall(val):
                    try:
                        dt = date(int(m[0]), int(m[1]), int(m[2]))
                        if dt > today:
                            reasons.append("EDU_FUTURE_DATE")
                    except ValueError:
                        pass
                if "EDU_FUTURE_DATE" in reasons:
                    break
        if "EDU_FUTURE_DATE" in reasons:
            break

    return list(dict.fromkeys(reasons))


# ── 위험성평가서 (safety.risk.assessment) ────────────────

def _validate_risk_assessment(extracted: dict, df_preview: str) -> list[str]:
    """위험성평가서 xlsx 전용 검증."""
    reasons: list[str] = []
    try:
        import io
        df = pd.read_csv(io.StringIO(df_preview))
    except Exception:
        return reasons

    if df.empty:
        reasons.append("EMPTY_TABLE")
        return reasons

    cols_lower = {str(c).strip(): c for c in df.columns}

    # (1) 감소대책/조치 비어있음
    action_cols = [v for k, v in cols_lower.items() if "대책" in k or "조치" in k or "action" in k.lower()]
    if action_cols:
        empty_count = df[action_cols[0]].isna().sum() + (df[action_cols[0]].astype(str).str.strip() == "").sum()
        if empty_count > len(df) * 0.3:
            reasons.append("RISK_ACTION_MISSING")
    else:
        reasons.append("RISK_ACTION_MISSING")

    # (2) 담당자 누락
    owner_cols = [v for k, v in cols_lower.items() if "담당" in k or "책임" in k]
    if owner_cols:
        empty_count = df[owner_cols[0]].isna().sum() + (df[owner_cols[0]].astype(str).str.strip() == "").sum()
        if empty_count > len(df) * 0.3:
            reasons.append("RISK_OWNER_MISSING")
    else:
        reasons.append("RISK_OWNER_MISSING")

    # (3) 점검일 누락
    date_cols = [v for k, v in cols_lower.items() if "점검일" in k or "일자" in k or "날짜" in k]
    if date_cols:
        empty_count = df[date_cols[0]].isna().sum() + (df[date_cols[0]].astype(str).str.strip() == "").sum()
        if empty_count > len(df) * 0.3:
            reasons.append("RISK_CHECKDATE_MISSING")

    return list(dict.fromkeys(reasons))


# ── 안전보건관리체계 PDF (safety.management.system) ──────

_REQUIRED_SECTIONS = {
    "MISSING_SECTION_ORG": ["조직", "책임", "권한"],
    "MISSING_SECTION_RISK": ["위험성평가", "위험성 평가"],
    "MISSING_SECTION_INCIDENT": ["사고", "대응", "비상"],
    "MISSING_SECTION_TRAINING": ["교육", "점검"],
    "MISSING_SECTION_IMPROVE": ["개선", "조치"],
}


def _validate_management_system_pdf(text: str) -> list[str]:
    """안전보건관리체계 PDF — 필수 섹션 존재 여부 검사."""
    reasons: list[str] = []
    text_lower = text.lower()
    for reason_code, keywords in _REQUIRED_SECTIONS.items():
        if not any(kw in text_lower for kw in keywords):
            reasons.append(reason_code)
    return reasons


# ── 소방 점검 (safety.fire.inspection) ───────────────────

def _validate_fire_inspection_xlsx(df_preview: str) -> list[str]:
    """소방 점검표 xlsx 전용 검증."""
    reasons: list[str] = []
    try:
        import io
        df = pd.read_csv(io.StringIO(df_preview))
    except Exception:
        return reasons

    if df.empty:
        reasons.append("EMPTY_TABLE")
        return reasons

    # (1) 결과 컬럼이 모두 동일값 (올양호 패턴)
    result_cols = [c for c in df.columns if "결과" in str(c)]
    for col in result_cols:
        vals = df[col].dropna().astype(str).str.strip()
        if len(vals) >= 3 and vals.nunique() == 1:
            reasons.append("FIRE_ALL_GOOD_PATTERN")
            break

    return list(dict.fromkeys(reasons))


def _validate_fire_inspection_pdf(text: str) -> list[str]:
    """소방 점검표 PDF — 서명 외 추가 검증."""
    reasons: list[str] = []
    # 반복 패턴 감지 (같은 줄이 3번 이상)
    lines = [ln.strip() for ln in text.split("\n") if len(ln.strip()) > 10]
    if lines:
        from collections import Counter
        counts = Counter(lines)
        for ln, cnt in counts.most_common(3):
            if cnt >= 3:
                reasons.append("FIRE_COPYPASTE_PATTERN")
                break
    return reasons


# ── 공개 디스패치 함수 ───────────────────────────────────

def validate_slot(
    slot_name: str,
    file_type: str,
    extracted: dict,
) -> list[str]:
    """슬롯+파일타입에 맞는 세부 검증을 실행하여 추가 reason 코드를 반환."""
    extra_reasons: list[str] = []

    if slot_name == "safety.education.status" and file_type == "xlsx":
        extra_reasons = _validate_education(extracted, extracted.get("df_preview", ""))

    elif slot_name == "safety.risk.assessment" and file_type == "xlsx":
        extra_reasons = _validate_risk_assessment(extracted, extracted.get("df_preview", ""))

    elif slot_name == "safety.management.system" and file_type == "pdf":
        extra_reasons = _validate_management_system_pdf(extracted.get("text", ""))
        # 관리체계 매뉴얼은 서명란 검사 불필요 → extractor가 붙인 SIGNATURE_MISSING 제거
        if "reasons" in extracted:
            extracted["reasons"] = [r for r in extracted["reasons"] if r != "SIGNATURE_MISSING"]

    elif slot_name == "safety.fire.inspection":
        # 점검표는 서명란 검사 불필요
        if "reasons" in extracted:
            extracted["reasons"] = [r for r in extracted["reasons"] if r != "SIGNATURE_MISSING"]
        if file_type == "xlsx":
            extra_reasons = _validate_fire_inspection_xlsx(extracted.get("df_preview", ""))
        elif file_type == "pdf":
            extra_reasons = _validate_fire_inspection_pdf(extracted.get("text", ""))

    return extra_reasons