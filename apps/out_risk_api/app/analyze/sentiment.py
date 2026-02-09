# AI/apps/out_risk_api/app/analyze/sentiment.py

# 20260202 이종헌 수정: 긍/부정 분리(negative-only scoring) 규칙 주석 보강
from __future__ import annotations

from typing import List, Tuple

from app.schemas.risk import DocItem


# 20260202 이종헌 신규: 부정 강키워드 사전 정의(negative-only scoring 기준)
def _esg_negative_strong_keywords() -> List[str]:
    """부정 강도 높은 키워드(무조건 리스크로 분류)."""
    return [
        # 사고/안전
        "사고", "산재", "산업재해", "중대재해", "사망", "부상", "화재", "폭발", "붕괴",
        # 환경
        "오염", "폐수", "유출", "누출", "유해", "환경규제", "과징금", "제재",
        # 법적/규제
        "기소", "고소", "고발", "수사", "조사", "압수수색", "혐의", "재판", "판결",
        "벌금", "과징금", "영업정지", "허가취소", "불법", "위반",
        # 노사/인권
        "파업", "분쟁", "해고", "임금체불", "차별", "괴롭힘", "성희롱", "갑질",
        # 지배구조/부패
        "횡령", "배임", "뇌물", "부패", "비리", "부정", "조작", "담합",
        # 제품/리콜
        "리콜", "결함", "불량", "환불", "환수",
        # English
        "accident", "fatal", "injury", "pollution", "spill", "violation",
        "sanction", "penalty", "fine", "lawsuit", "indict", "investigation",
        "prosecution", "bribery", "corruption", "fraud", "misconduct", "recall",
    ]


# 20260202 이종헌 신규: 긍정/개선 키워드 사전 정의(리스크 점수 제외 기준)
def _esg_positive_keywords() -> List[str]:
    return [
        # 긍정/개선/투자
        "감축", "절감", "저감", "개선", "상향", "확대", "도입", "양산", "출시",
        "투자", "공급", "협약", "파트너십", "수상", "인증", "선정",
        "탄소저감", "친환경", "재생에너지", "에너지효율", "ESG경영",
        # English
        "reduction", "improve", "improved", "launch", "investment", "award",
        "certification", "partnership", "renewable", "efficiency",
    ]


# 20260202 이종헌 수정: 점수 반영 대상은 negative_docs만 남기도록 분리
def esg_split_docs_by_sentiment(docs: List[DocItem]) -> Tuple[List[DocItem], List[DocItem]]:
    """
    Rule-based polarity split.
    Returns (negative_docs, positive_or_neutral_docs)
    """
    if not docs:
        return [], []

    neg_strong = [k.lower() for k in _esg_negative_strong_keywords()]
    pos_keys = [k.lower() for k in _esg_positive_keywords()]

    negative: List[DocItem] = []
    non_negative: List[DocItem] = []

    for d in docs:
        hay = " ".join([d.title or "", d.snippet or "", d.source or "", d.url or ""]).lower()
        has_neg_strong = any(k in hay for k in neg_strong)
        has_pos = any(k in hay for k in pos_keys)

        # 우선순위:
        # 1) 강한 부정 키워드가 있으면 무조건 negative
        # 2) 긍정 키워드가 있고 강한 부정이 없으면 non_negative
        # 3) 그 외는 negative로 간주 (보수적)
        if has_neg_strong:
            negative.append(d)
        elif has_pos:
            non_negative.append(d)
        else:
            # 약한 부정/중립은 리스크로 보지 않도록 non_negative 처리
            non_negative.append(d)

    return negative, non_negative
