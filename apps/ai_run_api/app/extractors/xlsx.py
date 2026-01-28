"""XLSX/CSV 파싱 — 헤더 검증, 날짜 추출."""

from __future__ import annotations

import io
import re
from datetime import date

import pandas as pd

DATE_RE = re.compile(r"(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})")


def _read_df(data: bytes, ext: str) -> pd.DataFrame:
    buf = io.BytesIO(data)
    if ext in (".xls", ".xlsx"):
        return pd.read_excel(buf)
    return pd.read_csv(buf)


def _extract_dates_from_df(df: pd.DataFrame) -> list[str]:
    dates: list[str] = []
    for col in df.columns:
        for val in df[col].dropna().astype(str):
            for m in DATE_RE.findall(val):
                dates.append(f"{m[0]}-{int(m[1]):02d}-{int(m[2]):02d}")
    return dates


async def extract_xlsx(
    data: bytes,
    ext: str,
    expected_headers: list[str],
    period_start: date,
    period_end: date,
) -> dict:
    """XLSX/CSV에서 헤더/날짜 검증.

    Returns dict with keys:
        df_preview, dates, date_in_range, reasons
    """
    df = _read_df(data, ext)
    reasons: list[str] = []

    # 헤더 검증
    if expected_headers:
        actual = [str(c).strip() for c in df.columns]
        missing = [h for h in expected_headers if not any(h in a for a in actual)]
        if missing:
            reasons.append("HEADER_MISMATCH")

    dates = _extract_dates_from_df(df)

    date_in_range = True
    for d in dates:
        try:
            dt = date.fromisoformat(d)
            if not (period_start <= dt <= period_end):
                date_in_range = False
                reasons.append("DATE_MISMATCH")
                break
        except ValueError:
            pass

    if not dates:
        reasons.append("NO_DATE_FOUND")

    return {
        "df_preview": df.head(20).to_csv(index=False),
        "dates": dates,
        "date_in_range": date_in_range,
        "reasons": reasons,
    }
