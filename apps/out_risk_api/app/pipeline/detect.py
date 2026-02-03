# AI/apps/out_risk_api/app/pipeline/detect.py

from __future__ import annotations

import asyncio
from typing import List

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


async def esg_search_preview(req: SearchPreviewRequest) -> SearchPreviewResponse:
    docs: List[DocItem] = await esg_search_documents(req)
    return SearchPreviewResponse(
        vendor=req.vendor,
        used=True,
        docs_count=len(docs),
        documents=docs,
    )


async def esg_detect_external_risk_batch(req: ExternalRiskDetectBatchRequest) -> ExternalRiskDetectBatchResponse:
    # 신규: Streamlit 타임아웃을 막기 위해 "협력사 1개당 최대 처리시간"을 강제
    esg_per_vendor_timeout_sec = 12.0

    # 수정: 동시성은 너무 키우지 말고(외부검색 병목), 기본 2~3으로 안전하게
    sem = asyncio.Semaphore(2)

    async def _run_one(vendor: str) -> ExternalRiskDetectVendorResult:
        async with sem:
            try:
                # 신규: 협력사 단건이 오래 걸리면 강제로 끊고 결과는 "timeout"으로 반환
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

    reason_3lines = _esg_make_reason_3lines(vendor, docs)
    total_score = _esg_calc_total_score(docs)
    level = _esg_level_from_score(total_score)

    return ExternalRiskDetectVendorResult(
        vendor=vendor,
        external_risk_level=level,
        total_score=float(total_score),
        docs_count=len(docs),
        reason_3lines=reason_3lines,
        evidence=docs[:10],
    )


def _esg_build_search_req(vendor: str, req: ExternalRiskDetectBatchRequest):
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
        "문서 상위 10건을 evidence로 제공했습니다.",
    ]


def _esg_calc_total_score(docs: List[DocItem]) -> float:
    n = len(docs)
    if n <= 0:
        return 0.0
    if n <= 3:
        return 30.0
    if n <= 7:
        return 60.0
    return 90.0


def _esg_level_from_score(score: float) -> RiskLevel:
    if score >= 80.0:
        return RiskLevel.HIGH
    if score >= 40.0:
        return RiskLevel.MEDIUM
    return RiskLevel.LOW
