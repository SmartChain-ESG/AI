from __future__ import annotations

import hashlib
import logging
import xml.etree.ElementTree as ET
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import List
from urllib.parse import quote_plus, urlparse

import httpx

from app.schemas.risk import DocItem, SearchPreviewRequest
from app.search.aliases import esg_expand_company_terms

logger = logging.getLogger("out_risk.search")


def esg_hash_id(value: str) -> str:
    return hashlib.sha256((value or "").encode("utf-8")).hexdigest()[:16]


def esg_safe_ymd(pub_text: str) -> str:
    s = (pub_text or "").strip()
    if not s:
        return ""
    try:
        dt = parsedate_to_datetime(s)
        return dt.date().isoformat()
    except Exception:
        try:
            dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
            return dt.date().isoformat()
        except Exception:
            return ""


def _esg_keywords() -> List[str]:
    return [
        "사고", "산재", "산업재해", "중대재해", "중대재해처벌법", "사망", "부상",
        "작업중", "안전", "안전사고", "안전관리", "위험물", "폭발", "화재", "붕괴",
        "노동", "노조", "파업", "분쟁", "해고", "임금체불", "근로감독",
        "산업안전보건법", "안전보건", "노동안전",
        "환경", "환경규제", "환경오염", "오염", "대기오염", "수질오염", "토양오염",
        "폐수", "배출", "배출가스", "유출", "누출", "유해물질", "화학물질",
        "탄소", "온실가스", "탄소배출", "배출권", "기후", "ESG",
        "불법", "위반", "수사", "조사", "압수수색", "기소", "고소", "고발", "혐의",
        "법원", "재판", "판결", "벌금", "과징금", "제재", "처분", "영업정지", "허가취소",
        "공정위", "공정거래위원회", "금감원", "금융감독원", "검찰", "경찰", "감사원",
        "횡령", "배임", "뇌물", "부패", "비리", "부정", "조작", "담합",
        "내부통제", "컴플라이언스", "윤리", "감사", "회계", "분식", "허위공시", "공시위반",
        "정정공시", "내부자거래",
        "리콜", "결함", "불량", "품질", "환불", "환수",
        "인권", "차별", "괴롭힘", "직장내", "성희롱", "갑질", "하도급", "불공정",
        "민원", "피해", "피해자", "집단소송",
        "accident", "fatal", "injury", "safety", "strike", "labor",
        "pollution", "spill", "emission", "violation", "sanction", "penalty", "fine",
        "lawsuit", "indict", "investigation", "prosecution", "raid",
        "bribery", "corruption", "fraud", "misconduct", "recall", "defect",
        "esg", "compliance", "governance", "audit", "whistleblower",
        "carbon", "emission", "climate", "human rights",
    ]


def _esg_filter_docs_relaxed(docs: List[DocItem]) -> List[DocItem]:
    if not docs:
        return []
    keys_l = [k.lower() for k in _esg_keywords()]
    kept: List[DocItem] = []
    for d in docs:
        hay = " ".join([d.title or "", d.snippet or "", d.source or "", d.url or ""]).lower()
        if any(k in hay for k in keys_l):
            kept.append(d)
    return kept


def esg_search_rss(req: SearchPreviewRequest) -> List[DocItem]:
    """
    RSS 검색(완화 모드):
    - 회사명/별칭 검색 RSS만 사용
    - ESG 키워드 포함 기사만 통과
    """

    def esg_build_rss_search_feeds(req: SearchPreviewRequest) -> list[str]:
        base_q = (req.vendor or "").strip()
        if not base_q:
            return []
        terms = esg_expand_company_terms(base_q) or [base_q]
        terms = terms[:2]
        return [
            f"https://news.google.com/rss/search?q={quote_plus(t)}&hl=ko&gl=KR&ceid=KR:ko"
            for t in terms
        ]

    logger.info("RSS search start vendor=%s", req.vendor)
    feeds = esg_build_rss_search_feeds(req)
    if not feeds:
        return []

    items: List[DocItem] = []
    seen_url = set()
    max_total = 20
    max_feeds = min(2, len(feeds))

    timeout = httpx.Timeout(connect=1.0, read=1.2, write=1.0, pool=1.0)

    with httpx.Client(timeout=timeout, follow_redirects=True, headers={"User-Agent": "out_risk_api/0.1"}) as client:
        for feed_url in feeds[:max_feeds]:
            if len(items) >= max_total:
                break
            try:
                r = client.get(feed_url)
                r.raise_for_status()
                root = ET.fromstring(r.text)
                channel = root.find("channel")
                entries = channel.findall("item") if channel is not None else root.findall(".//item")

                for it in entries:
                    if len(items) >= max_total:
                        break
                    link = (it.findtext("link") or "").strip()
                    if not link or link in seen_url:
                        continue
                    seen_url.add(link)

                    items.append(
                        DocItem(
                            doc_id=esg_hash_id(link),
                            title=(it.findtext("title") or "").strip() or "untitled",
                            source=urlparse(link).netloc.replace("www.", "") or "unknown",
                            published_at=esg_safe_ymd(it.findtext("pubDate")),
                            url=link,
                            snippet=(it.findtext("title") or "").strip(),
                        )
                    )
            except Exception as e:
                logger.warning("RSS fetch/parse failed: %s", str(e))
                continue

    # de-dup by url/title then filter
    seen = set()
    uniq: List[DocItem] = []
    for d in items:
        key = ((d.title or "").strip().lower(), (d.url or "").strip().lower())
        if key in seen:
            continue
        seen.add(key)
        uniq.append(d)

    filtered = _esg_filter_docs_relaxed(uniq)[:10]
    logger.info("RSS docs raw=%s filtered=%s", len(items), len(filtered))
    return filtered
