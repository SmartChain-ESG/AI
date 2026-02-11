# AI/apps/out_risk_api/app/pipeline/detect.py

from __future__ import annotations

import asyncio
import logging
from typing import List, Optional

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
from app.analyze.sentiment import esg_split_docs_by_sentiment
from app.analyze.classifier import esg_classify_and_score
from app.analyze.summarizer import esg_summarize_and_why
from app.scoring.rules import esg_level_from_total, esg_recency_weight
from app.core import config as app_config

logger = logging.getLogger("out_risk.detect")


# 20260201 이종헌 신규: preview 단계에서 검색 문서 개요 반환
async def esg_search_preview(req: SearchPreviewRequest) -> SearchPreviewResponse:
    docs: List[DocItem] = await esg_search_documents(req)
    return SearchPreviewResponse(
        vendor=req.vendor,
        used=True,
        docs_count=len(docs),
        documents=docs,
    )


# 20260211 이종헌 수정: 벤더 배치 타임아웃/병렬도 조정 및 단건 예외 격리
async def esg_detect_external_risk_batch(req: ExternalRiskDetectBatchRequest) -> ExternalRiskDetectBatchResponse:
    esg_per_vendor_timeout_sec = 12.0
    max_parallel = min(4, max(2, len(req.vendors)))
    sem = asyncio.Semaphore(max_parallel)

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
            except Exception as e:
                logger.warning("vendor detect failed vendor=%s err=%s", vendor, e)
                return ExternalRiskDetectVendorResult(
                    vendor=vendor,
                    external_risk_level=RiskLevel.LOW,
                    total_score=0.0,
                    docs_count=0,
                    reason_1line=f"{vendor} 관련 외부 이슈 분석 중 오류가 발생해 기본값으로 처리되었습니다.",
                    reason_3lines=[
                        "단건 분석 중 예외가 발생했습니다.",
                        "해당 벤더 결과는 LOW/0점으로 안전 처리되었습니다.",
                        "서버 로그의 vendor detect failed 항목을 확인하세요.",
                    ],
                    evidence=[],
                )

    results = await asyncio.gather(*[_run_one(v) for v in req.vendors])
    return ExternalRiskDetectBatchResponse(results=results)


# 20260203 이종헌 수정: 단일 벤더 검색→RAG(옵션)→감정분리→점수화 파이프라인
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

    negative_docs, non_negative_docs = esg_split_docs_by_sentiment(docs_used)
    docs_for_score = negative_docs

    reason_3lines = _esg_make_reason_3lines(vendor, docs_for_score, non_negative_docs)
    reason_1line = await _esg_make_reason_1line(vendor, docs_for_score)
    total_score = _esg_calc_total_score(docs_for_score)
    level = _esg_level_from_score(total_score)

    return ExternalRiskDetectVendorResult(
        vendor=vendor,
        external_risk_level=level,
        total_score=float(total_score),
        docs_count=len(docs_for_score),
        reason_1line=reason_1line,
        reason_3lines=reason_3lines,
        evidence=docs_for_score[:10],
    )


# 20260201 이종헌 신규: 벤더 단위 SearchPreviewRequest 빌더
def _esg_build_search_req(vendor: str, req: ExternalRiskDetectBatchRequest) -> SearchPreviewRequest:
    return SearchPreviewRequest(vendor=vendor, rag=req.rag)


# 20260211 이종헌 수정: 3줄 사유에 분류 정보(classifier) 포함
def _esg_make_reason_3lines(vendor: str, docs: List[DocItem], non_negative: List[DocItem]) -> List[str]:
    if not docs:
        return [
            f"{vendor} 관련 부정 외부 이슈 문서가 확인되지 않았습니다.",
            f"긍정/중립 문서 {len(non_negative)}건은 점수 계산에서 제외되었습니다.",
            "필요시 감정 키워드 규칙을 조정하세요.",
        ]
    sources = sorted({d.source for d in docs if d.source})[:3]
    category_line = "탐지 분류: GENERAL"
    try:
        _, signals = esg_classify_and_score(vendor, docs)
        if signals:
            category_line = f"탐지 분류: {signals[0].category.value} (sev={signals[0].severity})"
    except Exception as e:
        logger.warning("classifier skipped vendor=%s err=%s", vendor, e)
    return [
        f"{vendor} 관련 부정 문서 {len(docs)}건을 수집했습니다.",
        f"주요 출처: {', '.join(sources) if sources else 'N/A'}",
        category_line,
    ]


# 20260211 이종헌 수정: reason_1line 생성 경로를 summarizer 재사용으로 통일
async def _esg_make_reason_1line(vendor: str, docs: List[DocItem]) -> str:
    if not docs:
        return f"{vendor} 관련 외부 이슈 문서가 확인되지 않았습니다."

    titles = [d.title for d in docs[:3] if d.title]
    joined = " / ".join(titles)

    try:
        logger.info("reason_1line summarizer start vendor=%s docs=%s", vendor, len(docs))

        def _invoke_summarizer() -> str:
            summary = esg_summarize_and_why(
                text=joined,
                category="GENERAL",
                severity=3,
                strict_grounding=False,
                model=app_config.OPENAI_MODEL_LIGHT,
            )
            return (summary.summary_ko or "").strip()

        out = await asyncio.wait_for(asyncio.to_thread(_invoke_summarizer), timeout=3.0)
        if out:
            logger.info("reason_1line summarizer success vendor=%s", vendor)
            return out
    except asyncio.TimeoutError:
        logger.warning("reason_1line summarizer timeout vendor=%s", vendor)
    except Exception as e:
        logger.warning("reason_1line summarizer failed vendor=%s err=%s", vendor, e)

    return f"{vendor} 관련 기사 {len(docs)}건 감지 (최근: {titles[0] if titles else 'N/A'})"


# 20260211 이종헌 수정: 최근성 가중치 계산을 scoring.rules로 위임
def _age_weight(published_at: Optional[str]) -> float:
    return esg_recency_weight((published_at or "").strip())


# 20260201 이종헌 신규: 문서별 가중치 합산 후 총점(상한 10) 계산
def _esg_calc_total_score(docs: List[DocItem]) -> float:
    if not docs:
        return 0.0
    score = 0.0
    for d in docs:
        score += _age_weight(d.published_at)
    return min(10.0, round(score, 2))


# 20260211 이종헌 수정: 점수→등급 매핑을 scoring.rules로 위임
def _esg_level_from_score(score: float) -> RiskLevel:
    return esg_level_from_total(score)
