# AI/apps/out_risk_api/app/search/provider.py

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List

import httpx

from app.schemas.risk import DocItem

logger = logging.getLogger("out_risk")


async def esg_search_gdelt(req) -> List[DocItem]:
    # 신규: 외부 검색이 느려져도 서버 전체가 기다리지 않게 타임아웃을 더 빡빡하게
    esg_timeout = httpx.Timeout(6.0, connect=3.0)

    try:
        async with httpx.AsyncClient(timeout=esg_timeout) as client:  # 수정: timeout 적용
            r = await client.get(req.gdelt_url)

        ctype = (r.headers.get("content-type") or "").lower()
        if "json" not in ctype:
            logger.warning("GDELT non-json response: status=%s ctype=%s", r.status_code, ctype)
            return []

        try:
            data = r.json()
        except json.JSONDecodeError:
            logger.warning("GDELT json decode failed: status=%s head=%s", r.status_code, r.text[:120])
            return []

        return _esg_parse_gdelt_to_docs(data)
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


async def esg_search_documents(req) -> List[DocItem]:
    return await esg_search_gdelt(req)
