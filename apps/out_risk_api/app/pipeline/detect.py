#AI/apps/out_risk_api/app/pipeline/detech.py

# 20260131 이종헌 신규: LangGraph 기반 파이프라인(검색→RAG→분석→스코어→응답)
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from app.analyze.classifier import esg_guess_category, esg_pick_quote_and_offset
from app.analyze.summarizer import esg_summarize_and_why
from app.schemas.risk import (
    DocItem,
    EvidenceItem,
    ExternalRiskDetectRequest,
    ExternalRiskDetectResponse,
    Offset,
    RetrievalMeta,
    Signal,
)
from app.scoring.rules import esg_level_from_total, esg_recency_weight
from app.search.provider import esg_search_documents
from app.rag.chroma import esg_get_rag

try:
    from langgraph.graph import StateGraph, END

    _LG_AVAILABLE = True
except Exception:
    StateGraph = None
    END = None
    _LG_AVAILABLE = False


@dataclass
class esg_State:
    req: ExternalRiskDetectRequest
    docs: List[DocItem]
    search_used: bool
    rag_used: bool
    rag_hits: List[Dict[str, Any]]
    signals: List[Signal]
    total_score: float
    level: str


def esg_docs_to_text_items(docs: List[DocItem]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for d in docs:
        text = (d.text or "").strip() or (d.snippet or "").strip()
        if not text:
            continue
        out.append(
            {
                "text": text,
                "metadata": {
                    "doc_id": d.doc_id,
                    "title": d.title,
                    "source": d.source,
                    "url": d.url,
                    "published_at": d.published_at,
                },
            }
        )
    return out


def esg_build_signal_from_text(
    req: ExternalRiskDetectRequest,
    text: str,
    meta: Dict[str, Any],
) -> Signal:
    allowed = req.categories
    cls = esg_guess_category(text, allowed)

    summary_res = esg_summarize_and_why(
        text=text,
        category=cls.category,
        severity=cls.severity,
        strict_grounding=req.options.strict_grounding,
        model=None,
    )

    published_at = str(meta.get("published_at", "")) or ""
    weight = esg_recency_weight(published_at)
    score = float(cls.severity) * float(weight)

    evidence: List[EvidenceItem] = []
    if req.options.return_evidence_text:
        quote, s, e = esg_pick_quote_and_offset(text, cls.tags, max_len=200)
        if quote:
            evidence.append(
                EvidenceItem(
                    doc_id=str(meta.get("doc_id", "")),
                    source=str(meta.get("source", "")),
                    url=str(meta.get("url", "")),
                    quote=quote,
                    offset=Offset(start=s, end=e),
                )
            )

    return Signal(
        category=cls.category,
        severity=int(cls.severity),
        score=float(score),
        title=str(meta.get("title", "")),
        summary_ko=summary_res.summary_ko,
        why=summary_res.why,
        published_at=published_at,
        evidence=evidence,
        tags=list(cls.tags),
        is_estimated=bool(summary_res.is_estimated),
    )


def esg_recommendations_from_signals(signals: List[Signal]) -> List[str]:
    if not signals:
        return ["외부 위험 신호가 확인되지 않았습니다. 정기 모니터링을 유지하세요."]

    rec: List[str] = []
    if any(s.category == "SAFETY_ACCIDENT" and s.severity >= 3 for s in signals):
        rec.append("안전사고/산재 신호가 있어 안전보건 점검 및 교육 이력 확인을 권고합니다.")
    if any(s.category == "LEGAL_SANCTION" and s.severity >= 3 for s in signals):
        rec.append("법규 위반/행정처분 가능성이 있어 관련 처분 여부 및 개선조치 증빙 확인을 권고합니다.")
    if any(s.category == "FINANCE_LITIGATION" and s.severity >= 3 for s in signals):
        rec.append("재무불안/소송 가능성이 있어 거래 리스크(채무/소송/회생) 점검을 권고합니다.")
    if any(s.is_estimated for s in signals):
        rec.append("일부 신호는 근거가 부족한 '추정'입니다. 원문 확인 후 사실관계 검증을 권고합니다.")
    return rec or ["외부 이슈 가능성이 있어 원문 확인 및 내부 리스크 점검을 권고합니다."]


def esg_node_load_docs(state: esg_State) -> esg_State:
    docs = list(state.req.documents)
    search_used = False

    if state.req.search.enabled and not docs:
        docs = esg_search_documents(state.req)
        search_used = True

    state.docs = docs
    state.search_used = search_used
    return state


def esg_node_rag(state: esg_State) -> esg_State:
    state.rag_used = False
    state.rag_hits = []

    if not state.req.rag.enabled:
        return state

    text_items = esg_docs_to_text_items(state.docs)
    if not text_items:
        state.rag_used = True
        return state

    rag = esg_get_rag()
    if not rag.esg_ready():
        # Chroma/LC 미설치 혹은 키 없음이면 fallback(문서 텍스트 상위 일부만 사용)
        state.rag_used = True
        state.rag_hits = text_items[: max(1, int(state.req.rag.top_k or 6))]
        return state

    rag.esg_upsert(text_items, chunk_size=int(state.req.rag.chunk_size or 800))
    query = (state.req.search.query or "").strip() or state.req.company.name
    hits = rag.esg_retrieve(query=query, top_k=int(state.req.rag.top_k or 6))

    state.rag_used = True
    state.rag_hits = hits
    return state


def esg_node_analyze(state: esg_State) -> esg_State:
    signals: List[Signal] = []

    if state.rag_hits:
        for h in state.rag_hits:
            text = (h.get("text", "") or "").strip()
            meta = h.get("metadata", {}) or {}
            if not text:
                continue
            signals.append(esg_build_signal_from_text(state.req, text=text, meta=meta))
    else:
        # RAG 결과 없으면 docs 기반 분석
        for d in state.docs:
            text = (d.text or "").strip() or (d.snippet or "").strip()
            if not text:
                continue
            meta = {
                "doc_id": d.doc_id,
                "title": d.title,
                "source": d.source,
                "url": d.url,
                "published_at": d.published_at,
            }
            signals.append(esg_build_signal_from_text(state.req, text=text, meta=meta))

    state.signals = signals
    return state


def esg_node_score(state: esg_State) -> esg_State:
    total = float(sum(s.score for s in state.signals))
    state.total_score = total
    state.level = esg_level_from_total(total)
    return state


def esg_build_response(state: esg_State) -> ExternalRiskDetectResponse:
    top_sources = sorted(list({d.source for d in state.docs if d.source}))[:10]
    disclaimer = "본 결과는 외부 문서 기반의 보조 신호이며, 메인 판정을 변경하지 않습니다."
    if not state.docs:
        disclaimer += " (분석할 외부 문서가 없어 신호가 제한될 수 있습니다.)"

    return ExternalRiskDetectResponse(
        external_risk_level=state.level,  # type: ignore
        total_score=state.total_score,
        signals=state.signals,
        recommendations=esg_recommendations_from_signals(state.signals),
        disclaimer=disclaimer,
        retrieval_meta=RetrievalMeta(
            search_used=bool(state.req.search.enabled and state.search_used),
            rag_used=bool(state.req.rag.enabled and state.rag_used),
            docs_count=len(state.docs),
            top_sources=top_sources,
        ),
    )


def esg_build_graph() -> Optional[Any]:
    if not _LG_AVAILABLE or StateGraph is None:
        return None

    g = StateGraph(esg_State)
    g.add_node("load_docs", esg_node_load_docs)
    g.add_node("rag", esg_node_rag)
    g.add_node("analyze", esg_node_analyze)
    g.add_node("score", esg_node_score)

    g.set_entry_point("load_docs")
    g.add_edge("load_docs", "rag")
    g.add_edge("rag", "analyze")
    g.add_edge("analyze", "score")
    g.add_edge("score", END)
    return g.compile()


_GRAPH = esg_build_graph()


def esg_detect_external_risk(req: ExternalRiskDetectRequest) -> ExternalRiskDetectResponse:
    state = esg_State(
        req=req,
        docs=[],
        search_used=False,
        rag_used=False,
        rag_hits=[],
        signals=[],
        total_score=0.0,
        level="LOW",
    )

    if _GRAPH is not None:
        out = _GRAPH.invoke(state)
        if isinstance(out, dict):
            state = esg_State(**out)
        else:
            state = out
    else:
        state = esg_node_load_docs(state)
        state = esg_node_rag(state)
        state = esg_node_analyze(state)
        state = esg_node_score(state)

    return esg_build_response(state)
