# app/engines/esg/validators.py

"""
ESG validators
- validate_slot(): 파일 1건 단독 검증(E1/E2/E8 단건/OCR/BLUR)

※ 20260129 이종헌 수정: 고지서 파싱(_parse_bill_fields / _parse_date_any)은 cross_validators.py로 이동
"""

from __future__ import annotations
from typing import Any
import pandas as pd

# 20260130 이종헌 추가: df.columns 중 aliases에 해당하는 첫 컬럼명을 반환(대소문자/공백 무시).
def _pick_col(df: pd.DataFrame, aliases: tuple[str, ...]) -> str | None:
    if df.empty:
        return None
    norm = {str(c).strip().lower(): c for c in df.columns}
    for a in aliases:
        key = str(a).strip().lower()
        if key in norm:
            return norm[key]
    return None


def _has_unit_hint(df: pd.DataFrame, hints: tuple[str, ...]) -> bool:
    cols = [str(c).lower() for c in df.columns]
    return any(any(h in c for h in hints) for c in cols)


def _spike_threshold(ratio: float) -> str | None:
    """ratio = today / baseline. WARN: >=1.25 or <=0.75, FAIL: >=1.50 or <=0.50."""
    if ratio >= 1.50 or ratio <= 0.50:
        return "FAIL"
    if ratio >= 1.25 or ratio <= 0.75:
        return "WARN"
    return None


# ════════════════════════════════════════════════════════════
# 1) 파일 단독 검증(validate_slot)
# ════════════════════════════════════════════════════════════

def _esg_read_df(df_preview: str) -> pd.DataFrame:
    import io
    if not df_preview:
        return pd.DataFrame()
    try:
        return pd.read_csv(io.StringIO(df_preview))
    except Exception:
        return pd.DataFrame()


def _esg_validate_usage_basic(df: pd.DataFrame, value_col: str) -> list[str]:
    reasons: list[str] = []
    if df.empty:
        return ["PARSE_FAILED"]

    if value_col not in df.columns:
        return ["HEADER_MISMATCH"]

    # 음수/0 체크
    try:
        s = pd.to_numeric(df[value_col], errors="coerce").dropna()
        if (s <= 0).any():
            reasons.append("E1_NEGATIVE_OR_ZERO")
    except Exception:
        pass

    return reasons


def _esg_validate_spike_daily(df: pd.DataFrame, time_col: str, value_col: str) -> list[str]:
    """
    E2: 7일 평균 baseline 기반
    - 15건 이상 데이터는 일 단위로 합산해서 계산
    """
    if df.empty or time_col not in df.columns or value_col not in df.columns:
        return []

    reasons: list[str] = []
    try:
        ts = pd.to_datetime(df[time_col], errors="coerce")
        v = pd.to_numeric(df[value_col], errors="coerce")
        tmp = pd.DataFrame({"ts": ts, "v": v}).dropna()
        if tmp.empty:
            return []

        tmp["d"] = tmp["ts"].dt.date
        daily = tmp.groupby("d")["v"].sum().sort_index()

        # 최소 10건이 있어야 비교 가능
        if len(daily) < 10:
            return []

        # 마지막 하루만 체크 (데모용)
        last_day = daily.index[-1]
        baseline = daily.iloc[-8:-1].mean()  # 직전 7일 평균
        if baseline and baseline > 0:
            ratio = float(daily.loc[last_day] / baseline)
            sev = _spike_threshold(ratio)
            if sev == "FAIL":
                reasons.append("E2_SPIKE_FAIL")
            elif sev == "WARN":
                reasons.append("E2_SPIKE_WARN")
    except Exception:
        pass

    return reasons


def _esg_validate_ethics_sections(pdf_text: str) -> list[str]:
    """E8: 필수 섹션 키워드 존재 여부(비교적 단순)"""
    if not pdf_text:
        return ["PARSE_FAILED"]

    must_keywords = [
        "부패", "금품", "이해충돌", "공정", "인권", "괴롭힘", "개인정보", "정보보호", "사고", "보호", "징계"
    ]
    hit = sum(1 for k in must_keywords if k in pdf_text)
    if hit < 5:  # 데모용: 너무 엄격하지 않게
        return ["E8_SECTION_MISSING"]
    return []


def _esg_validate_ocr_unreadable(extracted: dict) -> list[str]:
    """
    흐린 사진/스캔 대응:
    - OCR_FAILED reason이 이미 있거나
    - text 길이가 너무 짧으면 unreadable
    """
    reasons: list[str] = []
    text = extracted.get("text", "") or ""
    base_reasons = extracted.get("reasons", []) or []
    if "OCR_FAILED" in base_reasons or len(text.strip()) < 80:
        reasons.append("G_OCR_UNREADABLE")
    return reasons


# 20260129 이종헌 수정: 포스터 이미지 단일 검증(blur_score/laplacian_var 기반으로 흐림 판정)
def _esg_validate_image_blur(extracted: dict) -> list[str]:
    """
    단일 검증: 포스터 이미지가 흐린지(blur) 체크
    - extracted에 blur_score/laplacian_var 같은 값이 있으면 사용
    - 값이 없으면 판단 불가 → reason 없음
    """
    blur = extracted.get("blur_score")
    if blur is None:
        blur = extracted.get("laplacian_var")

    if blur is None:
        return []

    try:
        blur = float(blur)
        if blur < 35.0:  # 데모 임계값(낮을수록 흐림)
            return ["G_IMAGE_BLURRY"]
    except Exception:
        return []

    return []


# 20260129 이종헌 수정: validate_slot()에서 포스터 슬롯에 OCR_UNREADABLE + IMAGE_BLURRY를 함께 적용
# 20260129 이종헌 수정: 윤리강령 slot 네이밍(예: esg.ethics.code)도 같이 처리하도록 조건 확장
def validate_slot(slot_name: str, file_type: str, extracted: dict) -> list[str]:
    """submit.py에서 파일 1건 추출 끝난 직후 호출되는 함수"""
    reasons: list[str] = []

    # 20260130 이종헌 수정: 전기, 가스, 수도 완화
    # ── 전기 사용량(E1/E2) ──────────────────────────────────
    if slot_name in ("esg.energy.electricity.usage_xlsx", "esg.energy.electricity.usage") and file_type == "xlsx":
        df = _esg_read_df(extracted.get("df_preview", ""))

        time_col = _pick_col(df, ("date", "timestamp", "datetime", "ts", "일자", "날짜"))
        val_col = _pick_col(df, ("Usage_kWh", "usage_kwh", "kwh", "KWH", "사용량", "전력사용량"))

        # 20260130 이종헌 수정: 헤더가 기대와 다를 때: HEADER_MISMATCH
        if not val_col:
            reasons.append("HEADER_MISMATCH")
            return list(dict.fromkeys(reasons))

        # 20260130 이종헌 수정: 기본값/스파이크 검증
        reasons += _esg_validate_usage_basic(df, val_col)
        if time_col:
            reasons += _esg_validate_spike_daily(df, time_col, val_col)

        # 20260130 이종헌 수정: 단위 힌트(너무 빡빡하게 안함)
        if not _has_unit_hint(df, ("kwh", "kw h", "전력", "전기")):
            reasons.append("E1_UNIT_MISSING")

    # ── 가스 사용량(E1/E2) ──────────────────────────────────
    elif slot_name in ("esg.energy.gas.usage_xlsx", "esg.energy.gas.usage") and file_type == "xlsx":
        df = _esg_read_df(extracted.get("df_preview", ""))

        time_col = _pick_col(df, ("timestamp", "date", "datetime", "ts", "일자", "날짜"))
        val_col = _pick_col(df, ("flow_m3", "Flow_m3", "usage_m3", "Usage_m3", "m3", "㎥", "사용량", "가스사용량"))

        if not val_col:
            reasons.append("HEADER_MISMATCH")
            return list(dict.fromkeys(reasons))

        reasons += _esg_validate_usage_basic(df, val_col)
        if time_col:
            reasons += _esg_validate_spike_daily(df, time_col, val_col)

    # ── 수도 사용량 ───────────────────────────────────
    elif slot_name in ("esg.energy.water.usage_xlsx", "esg.energy.water.usage") and file_type == "xlsx":
        df = _esg_read_df(extracted.get("df_preview", ""))

        time_col = _pick_col(df, ("timestamp", "date", "datetime", "ts", "일자", "날짜"))
        val_col = _pick_col(df, ("Usage_m3", "usage_m3", "m3", "㎥", "사용량", "수도사용량"))

        if not val_col:
            reasons.append("HEADER_MISMATCH")
            return list(dict.fromkeys(reasons))

        reasons += _esg_validate_usage_basic(df, val_col)
        # 수도도 스파이크 체크 하고 싶으면 아래 2줄 유지
        if time_col:
            reasons += _esg_validate_spike_daily(df, time_col, val_col)

    # ── 윤리강령 텍스트 품질/섹션 ──────────────────────────
    elif (slot_name.startswith("esg.governance.ethics") or slot_name == "esg.ethics.code") and file_type == "pdf":
        reasons += _esg_validate_ethics_sections(extracted.get("text", ""))

    # ── 윤리 포스터 이미지/스캔본: OCR 실패 + blur ───────────
    elif (slot_name == "esg.governance.poster_image" or slot_name == "esg.ethics.poster.image") and file_type in ("image", "pdf"):
        reasons += _esg_validate_ocr_unreadable(extracted)
        reasons += _esg_validate_image_blur(extracted)

    # 중복 제거
    return list(dict.fromkeys(reasons))