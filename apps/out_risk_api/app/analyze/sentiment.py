# AI/apps/out_risk_api/app/analyze/sentiment.py

from __future__ import annotations

from typing import List, Tuple

from app.schemas.risk import DocItem


def _esg_negative_strong_keywords() -> List[str]:
    return [
        # safety / environment
        "사고", "산재", "산업재해", "중대재해", "사망", "부상", "화재", "폭발", "붕괴",
        "오염", "폐수", "유출", "누출", "유해", "환경규제", "과징금", "제재",
        # legal / compliance
        "기소", "고소", "고발", "수사", "조사", "압수수색", "혐의", "재판", "판결",
        "벌금", "영업정지", "허가취소", "불법", "위반",
        # labor / governance
        "파업", "분쟁", "해고", "임금체불", "차별", "괴롭힘", "성희롱", "갑질",
        "횡령", "배임", "뇌물", "부패", "비리", "부정", "조작", "담합",
        # product
        "리콜", "결함", "불량", "환불", "환수",
        # English
        "accident", "fatal", "injury", "pollution", "spill", "violation",
        "sanction", "penalty", "fine", "lawsuit", "indict", "investigation",
        "prosecution", "bribery", "corruption", "fraud", "misconduct", "recall",
    ]


def _esg_hard_negative_keywords() -> List[str]:
    # Hard negatives always stay in risk even if positive words co-exist.
    return [
        "사망", "중대재해", "폭발", "붕괴", "기소", "압수수색", "벌금", "영업정지", "허가취소",
        "indict", "prosecution", "fatal", "bribery", "corruption",
    ]


def _esg_positive_override_keywords() -> List[str]:
    # Explicit positive/social-contribution context for false-positive reduction.
    return [
        "장학생", "장학금", "장학", "수여", "후원", "기부", "사회공헌",
        "scholarship", "donation",
    ]


def esg_split_docs_by_sentiment(docs: List[DocItem]) -> Tuple[List[DocItem], List[DocItem]]:
    if not docs:
        return [], []

    neg_strong = [k.lower() for k in _esg_negative_strong_keywords()]
    hard_neg = [k.lower() for k in _esg_hard_negative_keywords()]
    pos_override = [k.lower() for k in _esg_positive_override_keywords()]

    negative: List[DocItem] = []
    non_negative: List[DocItem] = []

    for d in docs:
        hay = " ".join([d.title or "", d.snippet or "", d.source or "", d.url or ""]).lower()
        has_neg_strong = any(k in hay for k in neg_strong)
        has_hard_neg = any(k in hay for k in hard_neg)
        has_pos_override = any(k in hay for k in pos_override)

        if has_hard_neg:
            negative.append(d)
        elif has_neg_strong and not has_pos_override:
            negative.append(d)
        else:
            non_negative.append(d)

    return negative, non_negative
