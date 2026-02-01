# AI/apps/out_risk_api/app/search/rss.py

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import List

import httpx

from app.schemas.risk import DocItem, ExternalRiskDetectRequest
from app.search.rss_sources import RSS_FEEDS

# 신규: RSS 파싱은 표준 라이브러리로만(KISS)
import xml.etree.ElementTree as ET

# 신규: 검색 가시화용 로깅
import logging
logger = logging.getLogger("out_risk.search")


def esg_hash_id(value: str) -> str:
    return hashlib.sha256((value or "").encode("utf-8")).hexdigest()[:16


def esg_safe_ymd(pub_text: str) -> str:
    # 신규: RSS pubDate는 형식이 들쭉날쭉 → MVP는 파싱 실패해도 빈값
    s = (pub_text or "").strip()
    if not s:
        return ""

    # 신규: ISO 형태면 파싱 시도
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return dt.date().isoformat()
    except Exception:
        return ""


def esg_search_rss(req: ExternalRiskDetectRequest) -> List[DocItem]:
    feeds = list(RSS_FEEDS)
    if not feeds:
        return []

    items: List[DocItem] = []
    seen_url = set()

    with httpx.Client(timeout=10.0, follow_redirects=True) as client:
        for feed_url in feeds:
            try:
                r = client.get(feed_url)
                r.raise_for_status()
                xml = r.text
            except Exception as e:
                logger.warning("RSS fetch failed: %s (%s)", feed_url, str(e))
                continue

            try:
                root = ET.fromstring(xml)
                channel = root.find("channel")
                entries = channel.findall("item") if channel is not None else root.findall(".//item")
            except Exception as e:
                logger.warning("RSS parse failed: %s (%s)", feed_url, str(e))
                continue

            for it in entries[: int(req.search.max_results or 20)]:
                title = (it.findtext("title") or "").strip()
                link = (it.findtext("link") or "").strip()
                pub = (it.findtext("pubDate") or "").strip()

                if not link or link in seen_url:
                    continue
                seen_url.add(link)

                doc_id = esg_hash_id(link)
                published_at = esg_safe_ymd(pub)

                # 신규: 후보 수집이 목적이므로 snippet만 채워도 충분
                items.append(
                    DocItem(
                        doc_id=doc_id,
                        title=title or "untitled",
                        source=feed_url,
                        published_at=published_at,
                        url=link,
                        text="",
                        snippet=title or "rss_item",
                    )
                )

    return items
