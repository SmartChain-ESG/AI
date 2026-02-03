from __future__ import annotations

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


def _build_gdelt_url(query: str, max_records: int = 50) -> str:
    params = {
        "query": query,
        "mode": "ArtList",
        "format": "json",
        "maxrecords": str(max_records),
        "sort": "DateDesc",
    }
    return str(httpx.URL(GDELT_DOC_API, params=params))


async def esg_search_gdelt(req: SearchPreviewRequest) -> List[DocItem]:
    esg_timeout = httpx.Timeout(6.0, connect=3.0)

    try:
        gdelt_url: Optional[str] = getattr(req, "gdelt_url", None)
        if not gdelt_url:
            terms = esg_expand_company_terms(req.vendor) or [req.vendor]
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
        filtered = _esg_filter_docs_by_terms(docs, terms)
        if not filtered and docs:
            logger.warning("GDELT returned docs but none matched terms: %s", terms)
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


def _esg_filter_docs_by_terms(docs: List[DocItem], terms: List[str]) -> List[DocItem]:
    if not docs or not terms:
        return docs
    lowered = [t.lower() for t in terms if t]
    kept: List[DocItem] = []
    for d in docs:
        hay = " ".join([d.title or "", d.snippet or "", d.source or ""]).lower()
        if any(t in hay for t in lowered):
            kept.append(d)
    return kept


async def esg_search_documents(req: SearchPreviewRequest) -> List[DocItem]:
    docs = await esg_search_gdelt(req)
    if docs:
        return docs
    # Fallback to RSS if GDELT is empty
    return esg_search_rss(req)
