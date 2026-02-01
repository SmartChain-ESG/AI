# AI/apps/out_rick_api/app/search/provider.py

# 20260131 이종헌 수정: ESG 외부 위험 감지용 검색 Provider
from __future__ import annotations

import hashlib
from datetime import datetime, timedelta
from typing import List, Optional
from urllib.parse import urlparse

import httpx

from app.schemas.risk import DocItem, ExternalRiskDetectRequest


# 역할: URL에서 도메인(출처명)만 뽑음
def esg_domain_from_url(url: str) -> str:
    try:
        host = urlparse(url).netloc
        return host.replace("www.", "") if host else "unknown"
    except Exception:
        return "unknown"


# 역할: 문자열을 안정적으로 doc_id로 변환(중복 제거용)
def esg_hash_id(value: str) -> str:
    return hashlib.sha256((value or "").encode("utf-8")).hexdigest()[:16]


# 역할: GDELT 날짜(YYYYMMDDhhmmss) → YYYY-MM-DD 변환
def esg_gdelt_date_to_ymd(seendate: str) -> str:
    try:
        if not seendate:
            return ""
        dt = datetime.strptime(seendate[:14], "%Y%m%d%H%M%S")
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return ""


# 역할: ESG 전용 검색 쿼리를 생성(회사명 + ESG 리스크 키워드)
def esg_build_esg_query(company_name: str, user_query: str) -> str:
    base = (user_query or "").strip()
    if not base:
        base = company_name

    # 20260131 이종헌 수정: ESG 전용 컨텍스트를 확실히 포함(안전/환경/법규/재무는 ESG 외부 위험 신호로 해석)
    esg_terms = '(환경 OR 오염 OR 민원 OR 제재 OR 행정처분 OR 과징금 OR 소송 OR 회생 OR 파산 OR 부도 OR 산재 OR 중대재해 OR 임금체불 OR 파업)'
    return f'("{base}") AND {esg_terms}'


# 역할: GDELT Doc API로 기사 목록을 가져와 DocItem으로 변환
def esg_search_gdelt(req: ExternalRiskDetectRequest) -> List[DocItem]:
    company_name = req.company.name
    query = esg_build_esg_query(company_name, req.search.query)

    end_dt = datetime.utcnow()
    start_dt = end_dt - timedelta(days=int(req.time_window_days or 90))
    start_str = start_dt.strftime("%Y%m%d%H%M%S")
    end_str = end_dt.strftime("%Y%m%d%H%M%S")

    # GDELT Doc 2.1: 무료/무키 방식(2일 MVP 적합)
    url = "https://api.gdeltproject.org/api/v2/doc/doc"
    params = {
        "query": query,
        "mode": "ArtList",
        "format": "json",
        "maxrecords": int(req.search.max_results or 20),
        "startdatetime": start_str,
        "enddatetime": end_str,
    }

    # 언어 힌트: 한국어 위주 보고 싶으면 kor
    if (req.search.lang or "ko").lower().startswith("ko"):
        params["query"] = params["query"] + " sourcelang:kor"  # 20260131 이종헌 수정: 한국어 우선

    items: List[DocItem] = []
    seen = set()

    with httpx.Client(timeout=10.0) as client:
        r = client.get(url, params=params)
        r.raise_for_status()
        data = r.json()

    articles = (data or {}).get("articles", []) or []
    for a in articles:
        article_url = (a.get("url") or "").strip()
        if not article_url or article_url in seen:
            continue
        seen.add(article_url)

        title = (a.get("title") or "").strip() or "untitled"
        seendate = (a.get("seendate") or "").strip()
        published_at = esg_gdelt_date_to_ymd(seendate) or ""

        source = esg_domain_from_url(article_url)
        snippet = (a.get("snippet") or "").strip()

        # 증거 인용은 snippet/text에서만 발췌해야 하므로, 최소한 snippet은 채움
        doc_id = esg_hash_id(article_url)

        items.append(
            DocItem(
                doc_id=doc_id,
                title=title,
                source=source,
                published_at=published_at or start_dt.strftime("%Y-%m-%d"),
                url=article_url,
                text="",  # MVP: 원문 크롤링은 다음 단계
                snippet=snippet or title,
            )
        )

    return items


# 역할: search.enabled=true일 때 문서 수집(현재는 GDELT 최소 구현)
def esg_search_documents(req: ExternalRiskDetectRequest) -> List[DocItem]:
    if not req.search.enabled:
        return []

    # sources 필터링(현재 MVP는 gdelt=뉴스 중심)
    sources = set(req.search.sources or [])
    if sources and "news" not in sources:
        return []  # 20260131 이종헌 수정: 요구사항의 sources에 news 없으면 아무것도 안 함(확장 지점)

    try:
        return esg_search_gdelt(req)
    except Exception:
        return []