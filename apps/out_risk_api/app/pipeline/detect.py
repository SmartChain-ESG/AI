from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import List, Optional

try:
    from langchain_openai import ChatOpenAI
    _LC_AVAILABLE = True
except Exception:
    ChatOpenAI = None
    _LC_AVAILABLE = False

from app.schemas.risk import (
    ExternalRiskDetectBatchRequest,
    ExternalRiskDetectBatchResponse,
    ExternalRiskDetectVendorResult,
    SearchPreviewRequest,
    SearchPreviewResponse,
    DocItem,
    RiskLevel,
)
from app.search.provider import esg_search_documents
from app.core import config as app_config

logger = logging.getLogger("out_risk.detect")


async def esg_search_preview(req: SearchPreviewRequest) -> SearchPreviewResponse:
    docs: List[DocItem] = await esg_search_documents(req)
    return SearchPreviewResponse(
        vendor=req.vendor,
        used=True,
        docs_count=len(docs),
        documents=docs,
    )


async def esg_detect_external_risk_batch(req: ExternalRiskDetectBatchRequest) -> ExternalRiskDetectBatchResponse:
    esg_per_vendor_timeout_sec = 6.0
    sem = asyncio.Semaphore(2)

    async def _run_one(vendor: str) -> ExternalRiskDetectVendorResult:
        async with sem:
            try:
                return await asyncio.wait_for(
                    esg_detect_external_risk_one(vendor, req),
                    timeout=esg_per_vendor_timeout_sec,
                )
            except asyncio.TimeoutError:
                return ExternalRiskDetectVendorResult(
                    vendor=vendor,
                    external_risk_level=RiskLevel.LOW,
                    total_score=0.0,
                    docs_count=0,
                    reason_1line=f"{vendor} 관련 외부 이슈 분석이 시간 제한으로 중단되었습니다.",
                    reason_3lines=[
                        "외부 이슈 감지가 시간 제한으로 중단되었습니다.",
                        f"단건 처리 제한: {esg_per_vendor_timeout_sec:.0f}s",
                        "search.max_results / time_window_days를 줄여 재시도하세요.",
                    ],
                    evidence=[],
                )

    results = await asyncio.gather(*[_run_one(v) for v in req.vendors])
    return ExternalRiskDetectBatchResponse(results=results)


async def esg_detect_external_risk_one(vendor: str, req: ExternalRiskDetectBatchRequest) -> ExternalRiskDetectVendorResult:
    docs: List[DocItem] = await esg_search_documents(_esg_build_search_req(vendor, req))
    docs_used = docs

    if req.rag.enabled and docs:
        try:
            from app.rag.chroma import esg_get_rag
            rag = esg_get_rag()
            if rag.esg_ready():
                text_items = []
                for d in docs:
                    text = " ".join([t for t in [d.title, d.snippet, d.url] if t])
                    text_items.append(
                        {
                            "text": text,
                            "metadata": {
                                "doc_id": d.doc_id,
                                "source": d.source,
                                "url": d.url,
                                "title": d.title,
                                "published_at": d.published_at,
                            },
                        }
                    )

                upserted = rag.esg_upsert(text_items, chunk_size=app_config.RAG_CHUNK_SIZE_DEFAULT)
                retrieved = rag.esg_retrieve(query=vendor, top_k=app_config.RAG_TOP_K_DEFAULT)
                doc_ids = {
                    (r.get("metadata") or {}).get("doc_id")
                    for r in retrieved
                    if isinstance(r, dict)
                }
                doc_ids = {d for d in doc_ids if d}
                if doc_ids:
                    filtered = [d for d in docs if d.doc_id in doc_ids]
                    if filtered:
                        docs_used = filtered
                logger.info(
                    "RAG used vendor=%s upserted=%s retrieved=%s docs_used=%s",
                    vendor,
                    upserted,
                    len(retrieved),
                    len(docs_used),
                )
            else:
                logger.warning("RAG skipped (not ready) vendor=%s", vendor)
        except Exception as e:
            logger.warning("RAG error vendor=%s err=%s", vendor, e)

    reason_3lines = _esg_make_reason_3lines(vendor, docs_used)
    reason_1line = await _esg_make_reason_1line(vendor, docs_used)
    total_score = _esg_calc_total_score(docs_used)
    level = _esg_level_from_score(total_score)

    return ExternalRiskDetectVendorResult(
        vendor=vendor,
        external_risk_level=level,
        total_score=float(total_score),
        docs_count=len(docs_used),
        reason_1line=reason_1line,
        reason_3lines=reason_3lines,
        evidence=docs_used[:10],
    )


def _esg_build_search_req(vendor: str, req: ExternalRiskDetectBatchRequest) -> SearchPreviewRequest:
    return SearchPreviewRequest(vendor=vendor, rag=req.rag)


def _esg_make_reason_3lines(vendor: str, docs: List[DocItem]) -> List[str]:
    if not docs:
        return [
            f"{vendor} 관련 외부 문서가 수집되지 않았습니다.",
            "검색 공급자(GDELT/RSS) 응답 실패 또는 관련성 필터 과도 가능성이 있습니다.",
            "preview로 수집 결과를 먼저 확인하세요.",
        ]
    sources = sorted({d.source for d in docs if d.source})[:3]
    return [
        f"{vendor} 관련 외부 문서 {len(docs)}건을 수집했습니다.",
        f"주요 출처: {', '.join(sources) if sources else 'N/A'}",
        "문서 상위 10건을 evidence로 제공합니다.",
    ]


async def _esg_make_reason_1line(vendor: str, docs: List[DocItem]) -> str:
    if not docs:
        return f"{vendor} 관련 외부 이슈 문서가 확인되지 않았습니다."

    titles = [d.title for d in docs[:3] if d.title]
    joined = " / ".join(titles)

    if _LC_AVAILABLE:
        try:
            logger.info("reason_1line LLM start vendor=%s docs=%s", vendor, len(docs))
            prompt = (
                "다음 기사 제목들을 참고해 한 줄 요약을 한국어로 작성하세요. "
                "회사명과 핵심 키워드 중심으로 40자 이내.\n\n"
                f"회사: {vendor}\n"
                f"제목: {joined}"
            )

            def _invoke_llm() -> str:
                llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.2)
                msg = llm.invoke(prompt)
                return str(getattr(msg, "content", msg)).strip()

            out = await asyncio.wait_for(asyncio.to_thread(_invoke_llm), timeout=3.0)
            if out:
                logger.info("reason_1line LLM success vendor=%s", vendor)
                return out
        except asyncio.TimeoutError:
            logger.warning("reason_1line LLM timeout vendor=%s", vendor)
        except Exception as e:
            logger.warning("reason_1line LLM failed: %s", e)

    return f"{vendor} 관련 기사 {len(docs)}건 감지 (최근: {titles[0] if titles else 'N/A'})"


def _parse_date(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    v = value.strip()
    if not v:
        return None
    try:
        if "T" in v and v.endswith("Z"):
            return datetime.strptime(v, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
        return datetime.fromisoformat(v.replace("Z", "+00:00"))
    except Exception:
        return None


def _age_weight(published_at: Optional[str]) -> float:
    dt = _parse_date(published_at)
    if not dt:
        return 0.7
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    days = (now - dt).days
    if days <= 30:
        return 1.5
    if days <= 90:
        return 1.0
    if days <= 180:
        return 0.7
    return 0.4


def _esg_calc_total_score(docs: List[DocItem]) -> float:
    if not docs:
        return 0.0
    score = 0.0
    for d in docs:
        score += _age_weight(d.published_at)
    return min(10.0, round(score, 2))


def _esg_level_from_score(score: float) -> RiskLevel:
    if score >= 10.0:
        return RiskLevel.HIGH
    if score >= 5.0:
        return RiskLevel.MEDIUM
    return RiskLevel.LOW
