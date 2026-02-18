"""PDF 텍스트 추출 + 조건부 OCR (기획서 §2.3, §4.2).

OCR 조건: 페이지별 텍스트 30자 이하 비율이 20% 이상이면 OCR 수행.
"""

from __future__ import annotations

import re
from datetime import date

import fitz  # PyMuPDF

from app.extractors.ocr.clova_client import run_ocr

DATE_RE = re.compile(r"(\d{4})[.\-/년](\d{1,2})[.\-/월](\d{1,2})")

OCR_CHAR_THRESHOLD = 30
OCR_PAGE_RATIO_THRESHOLD = 0.20


def _extract_dates(text: str) -> list[str]:
    return [f"{m[0]}-{int(m[1]):02d}-{int(m[2]):02d}" for m in DATE_RE.findall(text)]


def _needs_ocr(page_texts: list[str]) -> bool:
    """페이지별 텍스트 30자 이하 비율이 20% 이상이면 True."""
    if not page_texts:
        return False
    short_pages = sum(1 for t in page_texts if len(t.strip()) <= OCR_CHAR_THRESHOLD)
    return (short_pages / len(page_texts)) >= OCR_PAGE_RATIO_THRESHOLD


def _has_signature_image(page: fitz.Page) -> bool:
    for img in page.get_images(full=True):
        rects = page.get_image_rects(img[0])
        if rects:
            for r in rects:
                if r.y0 > page.rect.height * 0.5 and r.width < 200 and r.height < 100:
                    return True
    return False


async def extract_pdf(
    data: bytes,
    period_start: date,
    period_end: date,
) -> dict:
    """PDF에서 텍스트/날짜/서명 추출. 필요 시 OCR 수행.

    Returns dict with keys:
        text, dates, date_in_range, signature_detected, ocr_applied, reasons
    """
    doc = fitz.open(stream=data, filetype="pdf")

    page_texts: list[str] = []
    sig_detected = False
    for page in doc:
        page_texts.append(page.get_text())
        if not sig_detected and _has_signature_image(page):
            sig_detected = True
    doc.close()

    full_text = "\n".join(page_texts)
    reasons: list[str] = []
    ocr_applied = False

    # 조건부 OCR
    if _needs_ocr(page_texts):
        try:
            ocr_text = await run_ocr(data, "pdf")
            full_text = ocr_text if len(ocr_text) > len(full_text) else full_text
            ocr_applied = True
        except Exception:
            # OCR 호출이 실패해도 기본 텍스트가 충분하면 판독 실패로 보지 않는다.
            if len(full_text.strip()) < 80:
                reasons.append("OCR_FAILED")

    dates = _extract_dates(full_text)

    # 날짜 범위 검증
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
    if not sig_detected:
        reasons.append("SIGNATURE_MISSING")

    return {
        "text": full_text,
        "dates": dates,
        "date_in_range": date_in_range,
        "signature_detected": sig_detected,
        "ocr_applied": ocr_applied,
        "reasons": reasons,
    }
