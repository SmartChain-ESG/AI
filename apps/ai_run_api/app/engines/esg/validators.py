# app/engines/esg/validators.py

"""
ESG validators
- validate_slot(): 파일 1개 단독 검증(E1/E2/E8 일부/OCR)
- esg_cross_checks(): 슬롯 간 정합성(E3/E5~E7/E9)
"""

from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from app.engines.esg import rules as R


# ────────────────────────────────────────────────────────
# 1) 파일 단독 검증 (validate_slot)
# ────────────────────────────────────────────────────────

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

    # 음수/0
    try:
        s = pd.to_numeric(df[value_col], errors="coerce").dropna()
        if (s <= 0).any():
            reasons.append("E1_NEGATIVE_OR_ZERO")
    except Exception:
        pass

    return reasons


def _esg_validate_spike_daily(df: pd.DataFrame, time_col: str, value_col: str) -> list[str]:
    """
    E2: 7일 평균 baseline 기반 (정말 단순)
    - 15분/시간 데이터는 일 단위로 합산해서 계산
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

        # 최소 10일은 있어야 비교 의미
        if len(daily) < 10:
            return []

        # 마지막 하루만 체크 (데모용)
        last_day = daily.index[-1]
        baseline = daily.iloc[-8:-1].mean()  # 직전 7일 평균
        if baseline and baseline > 0:
            ratio = float(daily.loc[last_day] / baseline)
            sev = R.esg_spike_threshold(ratio)
            if sev == "FAIL":
                reasons.append("E2_SPIKE_FAIL")
            elif sev == "WARN":
                reasons.append("E2_SPIKE_WARN")
    except Exception:
        pass

    return reasons


def _esg_validate_ethics_sections(pdf_text: str) -> list[str]:
    """E8: 필수 섹션 키워드 존재 여부(아주 단순)"""
    if not pdf_text:
        return ["PARSE_FAILED"]

    must_keywords = [
        "부패", "금품", "이해상충", "공정", "인권", "괴롭힘", "개인정보", "정보보호", "신고", "보호", "징계"
    ]
    hit = sum(1 for k in must_keywords if k in pdf_text)
    if hit < 5:  # 데모용: 너무 엄격하지 않게
        return ["E8_SECTION_MISSING"]
    return []


def _esg_validate_ocr_unreadable(extracted: dict) -> list[str]:
    """
    흐린 사진/스캔본 데모:
    - OCR_FAILED reason이 있거나
    - text 길이가 너무 짧으면 unreadable
    """
    reasons: list[str] = []
    text = extracted.get("text", "") or ""
    base_reasons = extracted.get("reasons", []) or []
    if "OCR_FAILED" in base_reasons or len(text.strip()) < 80:
        reasons.append("G_OCR_UNREADABLE")
    return reasons


def validate_slot(slot_name: str, file_type: str, extracted: dict) -> list[str]:
    """submit.py에서 파일 1개 추출 끝난 직후 호출되는 함수"""
    reasons: list[str] = []

    # ── 전기 사용량(E1/E2) ──────────────────────────────
    if slot_name == "esg.energy.electricity.usage_xlsx" and file_type == "xlsx":
        df = _esg_read_df(extracted.get("df_preview", ""))
        reasons += _esg_validate_usage_basic(df, "Usage_kWh")
        reasons += _esg_validate_spike_daily(df, "date", "Usage_kWh")

        # 단위(대충) 체크: 컬럼명에 kWh 없으면 UNIT_MISSING 처리
        if "Usage_kWh" not in df.columns:
            reasons.append("E1_UNIT_MISSING")

    # ── 가스 사용량(E1/E2) ───────────────────────────────
    elif slot_name == "esg.energy.gas.usage_xlsx" and file_type == "xlsx":
        df = _esg_read_df(extracted.get("df_preview", ""))
        reasons += _esg_validate_usage_basic(df, "flow_m3")
        reasons += _esg_validate_spike_daily(df, "timestamp", "flow_m3")

    # ── 수도 사용량(옵션) ─────────────────────────────────
    elif slot_name == "esg.energy.water.usage_xlsx" and file_type == "xlsx":
        df = _esg_read_df(extracted.get("df_preview", ""))
        reasons += _esg_validate_usage_basic(df, "Usage_m3")

    # ── 윤리강령 텍스트 품질/섹션 ─────────────────────────
    elif slot_name.startswith("esg.governance.ethics") and file_type == "pdf":
        reasons += _esg_validate_ethics_sections(extracted.get("text", ""))

    # ── 윤리 포스터(이미지/스캔본) OCR 실패 데모 ─────────
    elif slot_name == "esg.governance.poster_image" and file_type in ("image", "pdf"):
        reasons += _esg_validate_ocr_unreadable(extracted)

    # 중복 제거
    return list(dict.fromkeys(reasons))


# ────────────────────────────────────────────────────────
# 2) 슬롯 간 정합성 검사 (esg_cross_checks)
# ────────────────────────────────────────────────────────

def _esg_pick_first(extractions_by_slot: dict[str, list[dict]], slot: str) -> dict | None:
    xs = extractions_by_slot.get(slot) or []
    return xs[0] if xs else None


def _esg_sum_usage_in_period(df: pd.DataFrame, time_col: str, value_col: str, s: date, e: date) -> float | None:
    try:
        ts = pd.to_datetime(df[time_col], errors="coerce")
        v = pd.to_numeric(df[value_col], errors="coerce")
        tmp = pd.DataFrame({"ts": ts, "v": v}).dropna()
        if tmp.empty:
            return None
        tmp = tmp[(tmp["ts"].dt.date >= s) & (tmp["ts"].dt.date <= e)]
        if tmp.empty:
            return None
        return float(tmp["v"].sum())
    except Exception:
        return None


def esg_cross_checks(
    extractions_by_slot: dict[str, list[dict]],
    period_start: date,
    period_end: date,
) -> list[dict[str, Any]]:
    """
    submit.py에서 슬롯별 그룹핑이 끝난 다음 1회 호출
    반환: "추가 슬롯결과" 리스트 (slot_name, reasons, verdict, extras)
    """
    out: list[dict[str, Any]] = []

    # ── E3: 전기 usage ↔ 전기 bill 매칭 ───────────────────
    ele_usage = _esg_pick_first(extractions_by_slot, "esg.energy.electricity.usage_xlsx")
    ele_bill = _esg_pick_first(extractions_by_slot, "esg.energy.electricity.bill_pdf")
    if ele_usage and ele_bill:
        df = _esg_read_df(ele_usage.get("df_preview", ""))
        bill_fields = R.esg_parse_bill_fields(ele_bill.get("text", ""))
        if not (bill_fields["bill_total"] and bill_fields["bill_period_start"] and bill_fields["bill_period_end"]):
            out.append({
                "slot_name": "esg.energy.electricity.bill_match",
                "reasons": ["E3_BILL_FIELDS_MISSING"],
                "verdict": "NEED_FIX",
                "extras": {},
            })
        else:
            s = bill_fields["bill_period_start"]
            e = bill_fields["bill_period_end"]
            xlsx_total = _esg_sum_usage_in_period(df, "date", "Usage_kWh", s, e)
            bill_total = float(bill_fields["bill_total"])
            if xlsx_total is None or bill_total <= 0:
                out.append({
                    "slot_name": "esg.energy.electricity.bill_match",
                    "reasons": ["E3_BILL_FIELDS_MISSING"],
                    "verdict": "NEED_FIX",
                    "extras": {},
                })
            else:
                diff_pct = abs(xlsx_total - bill_total) / bill_total * 100.0
                tol = 1.0
                reasons = []
                verdict = "PASS"
                if diff_pct > tol:
                    reasons.append("E3_BILL_MISMATCH")
                    verdict = "NEED_FIX"
                out.append({
                    "slot_name": "esg.energy.electricity.bill_match",
                    "reasons": reasons,
                    "verdict": verdict,
                    "extras": {
                        "xlsx_total_kwh": round(xlsx_total, 3),
                        "bill_total_kwh": round(bill_total, 3),
                        "diff_pct": round(diff_pct, 2),
                        "bill_period": f"{s}~{e}",
                    },
                })

    # ── E3: 가스 usage ↔ 가스 bill 매칭 ───────────────────
    gas_usage = _esg_pick_first(extractions_by_slot, "esg.energy.gas.usage_xlsx")
    gas_bill = _esg_pick_first(extractions_by_slot, "esg.energy.gas.bill_pdf")
    if gas_usage and gas_bill:
        df = _esg_read_df(gas_usage.get("df_preview", ""))
        bill_fields = R.esg_parse_bill_fields(gas_bill.get("text", ""))
        if bill_fields["bill_total"] and bill_fields["bill_period_start"] and bill_fields["bill_period_end"]:
            s = bill_fields["bill_period_start"]
            e = bill_fields["bill_period_end"]
            xlsx_total = _esg_sum_usage_in_period(df, "timestamp", "flow_m3", s, e)
            bill_total = float(bill_fields["bill_total"])
            if xlsx_total is not None and bill_total > 0:
                diff_pct = abs(xlsx_total - bill_total) / bill_total * 100.0
                tol = 2.0
                reasons = []
                verdict = "PASS"
                if diff_pct > tol:
                    reasons.append("E3_BILL_MISMATCH")
                    verdict = "NEED_FIX"
                out.append({
                    "slot_name": "esg.energy.gas.bill_match",
                    "reasons": reasons,
                    "verdict": verdict,
                    "extras": {
                        "xlsx_total_m3": round(xlsx_total, 3),
                        "bill_total_m3": round(bill_total, 3),
                        "diff_pct": round(diff_pct, 2),
                        "bill_period": f"{s}~{e}",
                    },
                })

    # ── E9: 서약일 < 윤리강령 개정일 WARN ─────────────────
    ethics_latest = _esg_pick_first(extractions_by_slot, "esg.governance.ethics.latest_pdf")
    pledge = _esg_pick_first(extractions_by_slot, "esg.governance.pledge_pdf")
    if ethics_latest and pledge:
        rev = R.esg_parse_date_any(ethics_latest.get("text", "개정일"))
        pled = R.esg_parse_date_any(pledge.get("text", "서약일"))
        if rev and pled and pled < rev:
            out.append({
                "slot_name": "esg.governance.pledge_check",
                "reasons": ["E9_PLEDGE_BEFORE_REVISION"],
                "verdict": "NEED_FIX",  # 데모 기준: WARN 대신 NEED_FIX로도 가능
                "extras": {"revision_date": str(rev), "pledge_date": str(pled)},
            })

    return out