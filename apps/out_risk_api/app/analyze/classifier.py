# AI/apps/out_risk_api/app/analyze/classifier.py

# 20260131 이종헌 신규: 문서 텍스트에서 카테고리/심각도(0~5)/태그를 규칙 기반으로 추정
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Tuple

from app.schemas.risk import Category


_KEYWORDS: Dict[Category, List[str]] = {
    "SAFETY_ACCIDENT": ["사고", "산재", "추락", "끼임", "사망", "부상", "안전", "중대재해"],
    "LEGAL_SANCTION": ["과징금", "행정처분", "위반", "처분", "검찰", "기소", "벌금", "제재"],
    "LABOR_DISPUTE": ["파업", "노조", "쟁의", "임금체불", "부당해고", "노사", "교섭"],
    "ENV_COMPLAINT": ["오염", "배출", "악취", "민원", "누출", "환경", "폐수", "먼지"],
    "FINANCE_LITIGATION": ["부도", "회생", "파산", "소송", "채무", "연체", "적자", "유동성"],
}


@dataclass
class esg_ClassifyResult:
    category: Category
    severity: int
    tags: List[str]


def esg_normalize_text(text: str) -> str:
    t = (text or "").lower()
    t = re.sub(r"\s+", " ", t).strip()
    return t


def esg_guess_category(text: str, allowed: List[Category]) -> esg_ClassifyResult:
    allowed = allowed or list(_KEYWORDS.keys())
    t = esg_normalize_text(text)

    best_cat: Category = allowed[0]
    best_hit = 0
    best_tags: List[str] = []

    for cat in allowed:
        kws = _KEYWORDS.get(cat, [])
        hit = sum(1 for k in kws if k in t)

        if hit > best_hit:
            best_hit = hit
            best_cat = cat
            best_tags = [k for k in kws if k in t][:5]

    severity = min(5, best_hit)
    return esg_ClassifyResult(category=best_cat, severity=severity, tags=best_tags)


def esg_pick_quote_and_offset(full_text: str, tags: List[str], max_len: int = 200) -> Tuple[str, int, int]:
    text = full_text or ""
    if not text:
        return "", 0, 0

    lower = text.lower()
    for tag in tags:
        idx = lower.find(tag.lower())
        if idx >= 0:
            start = max(0, idx - 60)
            end = min(len(text), start + max_len)
            return text[start:end], start, end

    end2 = min(len(text), max_len)
    return text[:end2], 0, end2
