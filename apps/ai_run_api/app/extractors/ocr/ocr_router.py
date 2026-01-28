"""OCR 라우터 — 이미지 파일 OCR 처리."""

from __future__ import annotations

import re
from datetime import date

from app.extractors.ocr.clova_client import run_ocr

DATE_RE = re.compile(r"(\d{4})[.\-/년](\d{1,2})[.\-/월](\d{1,2})")


def _extract_dates(text: str) -> list[str]:
    return [f"{m[0]}-{int(m[1]):02d}-{int(m[2]):02d}" for m in DATE_RE.findall(text)]


async def extract_image(
    data: bytes,
    file_format: str,
    period_start: date,
    period_end: date,
) -> dict:
    """이미지에서 OCR 텍스트/날짜 추출.

    Returns dict with keys: text, dates, date_in_range, reasons
    """
    reasons: list[str] = []
    try:
        text = await run_ocr(data, file_format)
    except Exception:
        return {
            "text": "",
            "dates": [],
            "date_in_range": True,
            "reasons": ["OCR_FAILED"],
        }

    dates = _extract_dates(text)

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
        "text": text,
        "dates": dates,
        "date_in_range": date_in_range,
        "reasons": reasons,
    }
