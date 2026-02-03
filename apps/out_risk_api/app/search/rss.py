# AI/apps/out_risk_api/app/search/rss.py

from __future__ import annotations
import hashlib
from datetime import datetime
from typing import List
import httpx
import logging
import xml.etree.ElementTree as ET
from urllib.parse import urlparse, quote_plus
from email.utils import parsedate_to_datetime

from app.schemas.risk import DocItem, ExternalRiskDetectRequest
from app.search.rss_sources import RSS_FEEDS
from app.search.aliases import esg_expand_company_terms

logger = logging.getLogger("out_risk.search")

def esg_hash_id(value: str) -> str:
    return hashlib.sha256((value or "").encode("utf-8")).hexdigest()[:16]

def esg_safe_ymd(pub_text: str) -> str:
    s = (pub_text or "").strip()
    if not s: return ""
    try:
        dt = parsedate_to_datetime(s)
        return dt.date().isoformat()
    except Exception:
        try:
            dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
            return dt.date().isoformat()
        except Exception:
            return ""

def esg_search_rss(req: ExternalRiskDetectRequest) -> List[DocItem]:
    """
    [핵심 함수] RSS 피드를 순회하며 리스크 기사를 수집합니다.
    """
    # 1. 동적 검색 피드 생성 로직 (함수 내부 정의)
    def esg_build_rss_search_feeds(req: ExternalRiskDetectRequest) -> list[str]:
        base_q = (req.search.query or "").strip() or (req.company.name or "").strip()
        if not base_q: return []
        
        # Alias 확장 (예: SK하이닉스 -> SK Hynix, 하이닉스)
        terms = esg_expand_company_terms(base_q) or [base_q]
        terms = terms[:2] # 타임아웃 방지를 위해 상위 2개 별칭만 사용
        
        return [f"https://news.google.com/rss/search?q={quote_plus(t)}&hl=ko&gl=KR&ceid=KR:ko" for t in terms]

    # 2. 모든 피드 합치기 (고정 피드 + 동적 검색 피드)
    feeds = list(RSS_FEEDS)
    feeds.extend(esg_build_rss_search_feeds(req))
    
    items: List[DocItem] = []
    seen_url = set()
    max_total = int(req.search.max_results or 20)
    max_feeds = min(3, len(feeds)) # 과도한 호출 방지 (최대 3개 피드만)

    # 3. HTTP 클라이언트 설정 (타임아웃 강화)
    timeout = httpx.Timeout(connect=1.0, read=1.5, write=1.0, pool=1.0)

    with httpx.Client(timeout=timeout, follow_redirects=True, headers={"User-Agent": "out_risk_api/0.1"}) as client:
        for feed_url in feeds[:max_feeds]:
            if len(items) >= max_total: break # 이미 다 모았으면 중단 (Early Exit)
            
            try:
                r = client.get(feed_url)
                r.raise_for_status()
                root = ET.fromstring(r.text)
                channel = root.find("channel")
                entries = channel.findall("item") if channel is not None else root.findall(".//item")
                
                for it in entries:
                    if len(items) >= max_total: break
                    
                    link = (it.findtext("link") or "").strip()
                    if not link or link in seen_url: continue
                    seen_url.add(link)

                    items.append(DocItem(
                        doc_id=esg_hash_id(link),
                        title=(it.findtext("title") or "").strip() or "untitled",
                        source=urlparse(link).netloc.replace("www.", "") or "unknown",
                        published_at=esg_safe_ymd(it.findtext("pubDate")),
                        url=link,
                        snippet=(it.findtext("title") or "").strip(),
                    ))
            except Exception as e:
                logger.warning("RSS fetch/parse failed: %s", str(e))
                continue

    return items