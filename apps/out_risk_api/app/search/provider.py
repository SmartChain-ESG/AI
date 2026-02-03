from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional

import httpx

from app.schemas.risk import DocItem, SearchPreviewRequest
from app.search.aliases import esg_expand_company_terms
from app.search.rss import esg_search_rss

logger = logging.getLogger("out_risk")

GDELT_DOC_API = "https://api.gdeltproject.org/api/v2/doc/doc"


def _build_gdelt_query(terms: List[str]) -> str:
    quoted = [f"\"{t}\"" for t in terms if t]
    if not quoted:
        return ""
    if len(quoted) == 1:
        return quoted[0]
    return "(" + " OR ".join(quoted) + ")"


def _build_gdelt_url(query: str, max_records: int = 20) -> str:
    params = {
        "query": query,
        "mode": "ArtList",
        "format": "json",
        "maxrecords": str(max_records),
        "sort": "DateDesc",
    }
    return str(httpx.URL(GDELT_DOC_API, params=params))


def _esg_keywords() -> List[str]:
    return [
        # Safety / Labor
        "사고", "산재", "산업재해", "중대재해", "중대재해처벌법", "사망", "부상",
        "작업중", "안전", "안전사고", "안전관리", "위험물", "폭발", "화재", "붕괴",
        "노동", "노조", "파업", "분쟁", "해고", "임금체불", "근로감독",
        "산업안전보건법", "안전보건", "노동안전",
        # Environment / Climate
        "환경", "환경규제", "환경오염", "오염", "대기오염", "수질오염", "토양오염",
        "폐수", "배출", "배출가스", "유출", "누출", "유해물질", "화학물질",
        "탄소", "온실가스", "탄소배출", "배출권", "기후", "ESG",
        # Legal / Compliance
        "불법", "위반", "수사", "조사", "압수수색", "기소", "고소", "고발", "혐의",
        "법원", "재판", "판결", "벌금", "과징금", "제재", "처분", "영업정지", "허가취소",
        "공정위", "공정거래위원회", "금감원", "금융감독원", "검찰", "경찰", "감사원",
        # Governance / Integrity
        "횡령", "배임", "뇌물", "부패", "비리", "부정", "조작", "담합",
        "내부통제", "컴플라이언스", "윤리", "감사", "회계", "분식", "허위공시", "공시위반",
        "정정공시", "내부자거래",
        # Product / Recall
        "리콜", "결함", "불량", "품질", "환불", "환수",
        # Human rights / Fair trade
        "인권", "차별", "괴롭힘", "직장내", "성희롱", "갑질", "하도급", "불공정",
        "민원", "피해", "피해자", "집단소송",
        # English
        "accident", "fatal", "injury", "safety", "strike", "labor",
        "pollution", "spill", "emission", "violation", "sanction", "penalty", "fine",
        "lawsuit", "indict", "investigation", "prosecution", "raid",
        "bribery", "corruption", "fraud", "misconduct", "recall", "defect",
        "esg", "compliance", "governance", "audit", "whistleblower",
        "carbon", "emission", "climate", "human rights",
    ]


def _esg_filter_docs_relaxed(docs: List[DocItem], terms: List[str]) -> List[DocItem]:
    if not docs:
        return []
    terms_l = [t.lower() for t in terms if t]
    keys_l = [k.lower() for k in _esg_keywords()]
    kept: List[DocItem] = []
    for d in docs:
        hay = " ".join([d.title or "", d.snippet or "", d.source or "", d.url or ""]).lower()
        has_company = any(t in hay for t in terms_l) if terms_l else True
        has_keyword = any(k in hay for k in keys_l)
        # 완화: GDELT는 회사명 쿼리로 가져오므로 키워드만 충족해도 통과
        if has_keyword and (has_company or not terms_l):
            kept.append(d)
    return kept


async def esg_search_gdelt(req: SearchPreviewRequest) -> List[DocItem]:
    esg_timeout = httpx.Timeout(3.0, connect=2.0)

    try:
        logger.info("GDELT search start vendor=%s", req.vendor)
        gdelt_url: Optional[str] = getattr(req, "gdelt_url", None)
        terms = esg_expand_company_terms(req.vendor) or [req.vendor]
        if not gdelt_url:
            query = _build_gdelt_query(terms[:3])
            gdelt_url = _build_gdelt_url(query)

        async with httpx.AsyncClient(timeout=esg_timeout) as client:
            r = await client.get(gdelt_url)

        ctype = (r.headers.get("content-type") or "").lower()
        if "json" not in ctype:
            logger.warning("GDELT non-json response: status=%s ctype=%s", r.status_code, ctype)
            return []

        try:
            data = r.json()
        except json.JSONDecodeError:
            logger.warning("GDELT json decode failed: status=%s head=%s", r.status_code, r.text[:120])
            return []

        docs = _esg_parse_gdelt_to_docs(data)
        filtered = _esg_filter_docs_relaxed(docs, terms)
        logger.info("GDELT docs raw=%s filtered=%s", len(docs), len(filtered))
        if not filtered and docs:
            logger.warning("GDELT returned docs but none matched ESG keywords: %s", terms)
        return filtered
    except httpx.TimeoutException:
        logger.warning("GDELT timeout")
        return []
    except Exception as e:
        logger.exception("GDELT error: %s", e)
        return []


def _esg_parse_gdelt_to_docs(data: Dict[str, Any]) -> List[DocItem]:
    items = data.get("articles") or data.get("data") or data.get("results") or []
    docs: List[DocItem] = []

    for i, it in enumerate(items):
        title = (it.get("title") or it.get("name") or "").strip()
        url = (it.get("url") or it.get("sourceUrl") or it.get("link") or "").strip()
        source = (it.get("sourceCountry") or it.get("source") or it.get("domain") or "GDELT").strip()
        published_at = (it.get("seendate") or it.get("publishedAt") or it.get("date") or None)

        if not title or not url:
            continue

        docs.append(
            DocItem(
                doc_id=f"gdelt_{i}",
                title=title,
                url=url,
                source=source,
                published_at=str(published_at) if published_at else None,
                snippet=(it.get("summary") or it.get("snippet") or None),
            )
        )

    return docs


async def esg_search_documents(req: SearchPreviewRequest) -> List[DocItem]:
    try:
        docs = await asyncio.wait_for(esg_search_gdelt(req), timeout=3.5)
    except asyncio.TimeoutError:
        docs = []
    if docs:
        return docs[:10]
    try:
        rss_docs = await asyncio.wait_for(asyncio.to_thread(esg_search_rss, req), timeout=3.5)
    except asyncio.TimeoutError:
        rss_docs = []
    return rss_docs[:10]
