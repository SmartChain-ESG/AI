# app/engines/esg/cross_validators.py

"""
ESG cross validators
- esg_cross_checks(): 슬롯 간 교차검증 (E3 / 피크 비교 / 폐기교차 / MSDS 커버리지 / 서약일 비교 등)

submit에서 이 파일의 esg_cross_checks()를 호출할 예정이라는 점 확실히 인지함.

※ 20260129 이종헌 수정: 고지서 파싱(_parse_bill_fields / _parse_date_any)을 validators.py에서 이 파일로 이동
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any

import pandas as pd

from app.engines.esg.validators import (
    _spike_threshold,
    _esg_read_df,
)


# 20260129 이종헌 수정: (이전 validators.py) 날짜 파서 이동
def _parse_date_any(text: str) -> date | None:
    """YYYY-MM-DD / YYYY.MM.DD / YYYY/MM/DD 패턴 1개만 추출."""
    if not text:
        return None
    m = re.search(r"(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})", text)
    if not m:
        return None
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


# 20260129 이종헌 수정: (이전 validators.py) 고지서 파서 이동
def _parse_bill_fields(pdf_text: str) -> dict[str, Any]:
    """고지서 PDF에서 기간/합계 추출."""
    out: dict[str, Any] = {
        "bill_total": None,
        "bill_unit": None,
        "bill_period_start": None,
        "bill_period_end": None,
    }
    if not pdf_text:
        return out
    m = re.search(r"당월\s*사용량\s*([\d,]+)\s*(kwh|kWh|m3|m³|톤)", pdf_text, re.IGNORECASE)
    if m:
        out["bill_total"] = float(m.group(1).replace(",", ""))
        out["bill_unit"] = m.group(2)
    m2 = re.search(
        r"(\d{4}[.\-/]\d{1,2}[.\-/]\d{1,2})\s*[~\-]\s*(\d{4}[.\-/]\d{1,2}[.\-/]\d{1,2})",
        pdf_text,
    )
    if m2:
        out["bill_period_start"] = _parse_date_any(m2.group(1))
        out["bill_period_end"] = _parse_date_any(m2.group(2))
    return out


def _pick_first(extractions_by_slot: dict[str, list[dict]], candidates: set[str]) -> dict | None:
    for s in candidates:
        xs = extractions_by_slot.get(s) or []
        if xs:
            return xs[0]
    return None


def _pick_all(extractions_by_slot: dict[str, list[dict]], candidates: set[str]) -> list[dict]:
    out: list[dict] = []
    for s in candidates:
        out += (extractions_by_slot.get(s) or [])
    return out


def _daily_peak(df: pd.DataFrame, time_col: str, value_col: str) -> float | None:
    try:
        # 20260130 이종헌 추가: 컬럼 없으면 alias로 대체
        if time_col not in df.columns:
          for c in ("date", "timestamp", "datetime", "ts", "일자", "날짜"):
            if c in df.columns:
                time_col = c
                break
        if value_col not in df.columns:
            for c in ("Usage_kWh", "usage_kwh", "kwh", "flow_m3", "usage_m3", "Usage_m3", "m3", "㎥", "사용량"):
                if c in df.columns:
                    value_col = c
                    break
        ts = pd.to_datetime(df[time_col], errors="coerce")
        v = pd.to_numeric(df[value_col], errors="coerce")
        tmp = pd.DataFrame({"ts": ts, "v": v}).dropna()
        if tmp.empty:
            return None
        tmp["d"] = tmp["ts"].dt.date
        daily = tmp.groupby("d")["v"].sum()
        if daily.empty:
            return None
        return float(daily.max())
    except Exception:
        return None


def _monthly_sum(df: pd.DataFrame, time_col: str, value_col: str) -> dict[tuple[int, int], float]:
    out: dict[tuple[int, int], float] = {}
    try:
        # 20260130 이종헌 추가: 컬럼 없으면 alias로 대체 
        if time_col not in df.columns:
          for c in ("date", "timestamp", "datetime", "ts", "일자", "날짜"):
              if c in df.columns:
                  time_col = c
                  break
        if value_col not in df.columns:
            for c in ("Usage_kWh", "usage_kwh", "kwh", "flow_m3", "usage_m3", "Usage_m3", "m3", "㎥", "사용량"):
                if c in df.columns:
                    value_col = c
                    break
        ts = pd.to_datetime(df[time_col], errors="coerce")
        v = pd.to_numeric(df[value_col], errors="coerce")
        tmp = pd.DataFrame({"ts": ts, "v": v}).dropna()
        if tmp.empty:
            return out
        tmp["y"] = tmp["ts"].dt.year
        tmp["m"] = tmp["ts"].dt.month
        g = tmp.groupby(["y", "m"])["v"].sum()
        for (y, m), total in g.items():
            out[(int(y), int(m))] = float(total)
        return out
    except Exception:
        return out


def _bill_month_key(fields: dict[str, Any]) -> tuple[int, int] | None:
    d = fields.get("bill_period_end") or fields.get("bill_period_start")
    if not d:
        return None
    return (int(d.year), int(d.month))


def _compare_month_total(slot_name: str, xlsx_total: float | None, bill_total: float | None, tol_pct: float, month: str) -> dict[str, Any]:
    if xlsx_total is None or bill_total is None or bill_total <= 0:
        return {
            "slot_name": slot_name,
            "reasons": ["E3_BILL_FIELDS_MISSING"],
            "verdict": "NEED_FIX",
            "extras": {"month": month},
        }

    diff_pct = abs(xlsx_total - bill_total) / bill_total * 100.0
    verdict = "PASS"
    reasons: list[str] = []

    if diff_pct > tol_pct:
        reasons.append("E3_BILL_MISMATCH")
        verdict = "FAIL" if diff_pct >= 20.0 else "NEED_FIX"

    return {
        "slot_name": slot_name,
        "reasons": reasons,
        "verdict": verdict,
        "extras": {
            "month": month,
            "xlsx_total": round(float(xlsx_total), 3),
            "bill_total": round(float(bill_total), 3),
            "diff_pct": round(float(diff_pct), 2),
            "tol_pct": tol_pct,
        },
    }


def _parse_disposal_list(df: pd.DataFrame) -> list[dict[str, Any]]:
    """폐기/처리 목록 XLSX에서 최소 파싱(컬럼명 조금 달라도 동작하게)"""
    if df.empty:
        return []

    cols = {c: c.lower() for c in df.columns}

    def pick(*keys: str) -> str | None:
        for c, lc in cols.items():
            if any(k in lc for k in keys):
                return c
        return None

    col_name = pick("물질", "material", "item", "품명")
    col_qty = pick("수량", "량", "qty", "quantity", "amount")
    col_date = pick("일자", "날짜", "date", "처리일", "반출일")

    if not col_name or not col_date:
        return []

    out: list[dict[str, Any]] = []
    for _, row in df.iterrows():
        name = str(row.get(col_name, "")).strip()
        d = str(row.get(col_date, "")).strip()
        if not name or not d:
            continue
        out.append({
            "name": name,
            "date_raw": d,
            "qty_raw": str(row.get(col_qty, "")).strip() if col_qty else "",
        })
    return out


def _disposal_evidence_probe(pdf_text: str) -> dict[str, Any]:
    """증빙 PDF가 최소한의 정보를 포함하는지 빠르게 체크"""
    if not pdf_text:
        return {"has_date": False, "has_qty": False, "has_company": False}

    has_date = bool(re.search(r"\d{4}[.\-/]\d{1,2}[.\-/]\d{1,2}", pdf_text))
    has_qty = bool(re.search(r"([\d,]+)\s*(kg|톤|t|l|L|m3|m³)", pdf_text, re.IGNORECASE))
    has_company = bool(re.search(r"(주식회사|㈜|처리업체|수거|운반|위탁)", pdf_text))
    return {"has_date": has_date, "has_qty": has_qty, "has_company": has_company}


def _inventory_chemicals(df: pd.DataFrame) -> list[dict[str, Any]]:
    """
    유해물질 목록에서 (물질명, MSDS_필수) 추출
    - 네가 만든 DEMO 파일 헤더(물질명, MSDS_필수)를 우선 사용
    """
    if df.empty:
        return []

    name_col = "물질명" if "물질명" in df.columns else None
    req_col = "MSDS_필수" if "MSDS_필수" in df.columns else None

    if not name_col:
        return []

    out: list[dict[str, Any]] = []
    for _, row in df.iterrows():
        name = str(row.get(name_col, "")).strip()
        if not name:
            continue
        msds_req = str(row.get(req_col, "Y")).strip().upper() if req_col else "Y"
        out.append({"name": name, "msds_required": msds_req == "Y"})
    return out


def _msds_coverage(chemicals: list[dict[str, Any]], msds_docs: list[dict]) -> tuple[list[str], list[str]]:
    """inventory 물질명이 제출된 MSDS 문서(text/file_name)에 있는지 체크"""
    msds_text_all = " ".join([(d.get("text", "") or "") for d in msds_docs]).lower()
    msds_names_all = " ".join([(d.get("file_name", "") or d.get("source_file_name", "") or "") for d in msds_docs]).lower()

    missing_required: list[str] = []
    missing_optional: list[str] = []

    for c in chemicals:
        nm = c["name"].lower()
        hit = (nm in msds_text_all) or (nm in msds_names_all)
        if hit:
            continue
        if c["msds_required"]:
            missing_required.append(c["name"])
        else:
            missing_optional.append(c["name"])

    return missing_required, missing_optional


def esg_cross_checks(
    extractions_by_slot: dict[str, list[dict]],
    period_start: date,
    period_end: date,
) -> list[dict[str, Any]]:
    """
    submit.py에서 슬롯별 그루핑이 끝난 다음 1회 호출
    반환: "추가 슬롯결과" 리스트(slot_name, reasons, verdict, extras)
    """
    out: list[dict[str, Any]] = []

    # 슬롯 후보(네 slots.py / 기존 validate_slot 네이밍 둘 다 허용)
    ELEC_USAGE = {"esg.energy.electricity.usage_xlsx", "esg.energy.electricity.usage"}
    GAS_USAGE = {"esg.energy.gas.usage_xlsx", "esg.energy.gas.usage"}
    WATER_USAGE = {"esg.energy.water.usage_xlsx", "esg.energy.water.usage"}

    ELEC_BILL = {"esg.energy.electricity.bill_pdf", "esg.energy.electricity.bill"}
    GAS_BILL = {"esg.energy.gas.bill_pdf", "esg.energy.gas.bill"}
    WATER_BILL = {"esg.energy.water.bill_pdf", "esg.energy.water.bill"}

    INV = {"esg.hazmat.inventory_xlsx", "esg.hazmat.inventory"}
    MSDS = {"esg.hazmat.msds_pdf", "esg.hazmat.msds"}

    WASTE_LIST = {"esg.hazmat.disposal.list_xlsx", "esg.hazmat.disposal.list"}
    WASTE_EVI = {"esg.hazmat.disposal.evidence_pdf", "esg.hazmat.disposal.evidence"}

    ETHICS_LATEST = {"esg.governance.ethics.latest_pdf"}
    PLEDGE = {"esg.governance.pledge_pdf", "esg.ethics.pledge"}

    # ─────────────────────────────────────────────────────────
    # Cross-1) 2024 대비 2025 피크(이상치 탐지)
    # - 2024 기준 데이터가 없으면 WARN 처리
    # ─────────────────────────────────────────────────────────
    base_2024 = _pick_first(extractions_by_slot, {"esg.energy.electricity.usage_2024_xlsx"})
    cur_2025 = _pick_first(extractions_by_slot, ELEC_USAGE)

    if not base_2024:
        out.append({
            "slot_name": "esg.energy.electricity.peak_2024_vs_2025",
            "reasons": ["BASELINE_2024_MISSING"],
            "verdict": "WARN",
            "extras": {},
        })
    elif base_2024 and cur_2025:
        df24 = _esg_read_df(base_2024.get("df_preview", ""))
        df25 = _esg_read_df(cur_2025.get("df_preview", ""))
        if df24.empty or df25.empty:
            out.append({
                "slot_name": "esg.energy.electricity.peak_2024_vs_2025",
                "reasons": ["PARSE_FAILED"],
                "verdict": "WARN",
                "extras": {},
            })
        else:
            p24 = _daily_peak(df24, "date", "Usage_kWh")
            p25 = _daily_peak(df25, "date", "Usage_kWh")
            if not p24 or not p25 or p24 <= 0:
                out.append({
                    "slot_name": "esg.energy.electricity.peak_2024_vs_2025",
                    "reasons": ["BASELINE_INVALID"],
                    "verdict": "WARN",
                    "extras": {},
                })
            else:
                ratio = float(p25 / p24)
                sev = _spike_threshold(ratio)
                reasons: list[str] = []
                verdict = "PASS"
                if sev == "FAIL":
                    reasons.append("E_PEAK_SPIKE_FAIL")
                    verdict = "FAIL"
                elif sev == "WARN":
                    reasons.append("E_PEAK_SPIKE_WARN")
                    verdict = "WARN"
                out.append({
                    "slot_name": "esg.energy.electricity.peak_2024_vs_2025",
                    "reasons": reasons,
                    "verdict": verdict,
                    "extras": {"peak_2024": round(p24, 3), "peak_2025": round(p25, 3), "ratio": round(ratio, 3)},
                })

    # ─────────────────────────────────────────────────────────
    # Cross-2) 2026 10/11/12: usage 월합계 vs 고지서 당월 사용량
    # ─────────────────────────────────────────────────────────
    def cross_month_match(
        usage_candidates: set[str],
        bill_candidates: set[str],
        time_col: str,
        val_col: str,
        out_slot: str,
        tol_pct: float,
    ) -> None:
        usage = _pick_first(extractions_by_slot, usage_candidates)
        bills = _pick_all(extractions_by_slot, bill_candidates)
        if not usage or not bills:
            return

        df = _esg_read_df(usage.get("df_preview", ""))
        if df.empty or time_col not in df.columns or val_col not in df.columns:
            out.append({"slot_name": out_slot, "reasons": ["PARSE_FAILED"], "verdict": "NEED_FIX", "extras": {}})
            return

        month_sum = _monthly_sum(df, time_col, val_col)

        for b in bills:
            fields = _parse_bill_fields(b.get("text", ""))
            mk = _bill_month_key(fields)
            if not mk:
                out.append({"slot_name": out_slot, "reasons": ["E3_BILL_FIELDS_MISSING"], "verdict": "NEED_FIX", "extras": {}})
                continue

            month_str = f"{mk[0]}-{mk[1]:02d}"
            xlsx_total = month_sum.get(mk)
            bill_total = fields.get("bill_total")
            out.append(_compare_month_total(out_slot, xlsx_total, bill_total, tol_pct, month_str))

    cross_month_match(ELEC_USAGE, ELEC_BILL, "date", "Usage_kWh", "esg.energy.electricity.month_match", 1.0)
    cross_month_match(GAS_USAGE, GAS_BILL, "timestamp", "flow_m3", "esg.energy.gas.month_match", 2.0)
    cross_month_match(WATER_USAGE, WATER_BILL, "timestamp", "Usage_m3", "esg.energy.water.month_match", 1.0)

    # ─────────────────────────────────────────────────────────
    # Cross-3) 폐기/처리 목록 XLSX + 폐기 증빙 PDF
    # ─────────────────────────────────────────────────────────
    waste_list = _pick_first(extractions_by_slot, WASTE_LIST)
    waste_evi = _pick_first(extractions_by_slot, WASTE_EVI)

    if waste_list or waste_evi:
        if not waste_list or not waste_evi:
            out.append({
                "slot_name": "esg.hazmat.disposal.cross_check",
                "reasons": ["E_WASTE_EVIDENCE_MISSING"],
                "verdict": "NEED_FIX",
                "extras": {},
            })
        else:
            df = _esg_read_df(waste_list.get("df_preview", ""))
            items = _parse_disposal_list(df)
            probe = _disposal_evidence_probe(waste_evi.get("text", ""))

            reasons: list[str] = []
            verdict = "PASS"

            if not items:
                reasons.append("E_WASTE_LIST_PARSE_FAILED")
                verdict = "NEED_FIX"

            if not (probe["has_date"] and probe["has_qty"] and probe["has_company"]):
                reasons.append("E_WASTE_EVIDENCE_FIELDS_WEAK")
                verdict = "NEED_FIX"

            pdf_text = (waste_evi.get("text", "") or "").lower()
            missing_names: list[str] = []
            for it in items[:10]:
                if it["name"].lower() not in pdf_text:
                    missing_names.append(it["name"])

            if missing_names:
                reasons.append("E_WASTE_NAME_MISMATCH")
                verdict = "FAIL"

            out.append({
                "slot_name": "esg.hazmat.disposal.cross_check",
                "reasons": list(dict.fromkeys(reasons)),
                "verdict": verdict,
                "extras": {"missing_names": missing_names},
            })

    # ─────────────────────────────────────────────────────────
    # Cross-4) 유해물질 목록(Inventory) vs MSDS 제출 커버리지
    # ─────────────────────────────────────────────────────────
    inv = _pick_first(extractions_by_slot, INV)
    msds_docs = _pick_all(extractions_by_slot, MSDS)

    if inv:
        df = _esg_read_df(inv.get("df_preview", ""))
        chems = _inventory_chemicals(df)

        if not chems:
            out.append({
                "slot_name": "esg.hazmat.msds.coverage",
                "reasons": ["E_INVENTORY_PARSE_FAILED"],
                "verdict": "NEED_FIX",
                "extras": {},
            })
        else:
            missing_req, missing_opt = _msds_coverage(chems, msds_docs)
            reasons: list[str] = []
            verdict = "PASS"

            if missing_req:
                reasons.append("E_MSDS_MISSING_REQUIRED")
                verdict = "FAIL"
            elif missing_opt:
                reasons.append("E_MSDS_MISSING_OPTIONAL")
                verdict = "WARN"

            out.append({
                "slot_name": "esg.hazmat.msds.coverage",
                "reasons": reasons,
                "verdict": verdict,
                "extras": {"missing_required": missing_req, "missing_optional": missing_opt},
            })

    # ─────────────────────────────────────────────────────────
    # (기존) Cross-5) 서약일 < 윤리강령 개정일 → WARN
    # ─────────────────────────────────────────────────────────
    ethics_latest = _pick_first(extractions_by_slot, ETHICS_LATEST)
    pledge = _pick_first(extractions_by_slot, PLEDGE)

    if ethics_latest and pledge:
        rev = _parse_date_any(ethics_latest.get("text", ""))
        pled = _parse_date_any(pledge.get("text", ""))
        if rev and pled and pled < rev:
            out.append({
                "slot_name": "esg.governance.pledge_check",
                "reasons": ["E9_PLEDGE_BEFORE_REVISION"],
                "verdict": "WARN",
                "extras": {"revision_date": str(rev), "pledge_date": str(pled)},
            })

    return out