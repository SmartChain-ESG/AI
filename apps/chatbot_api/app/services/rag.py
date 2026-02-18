from __future__ import annotations

import logging

from app.core.prompts import (
    CONTEXTUALIZE_SYSTEM_PROMPT,
    SYSTEM_PROMPT,
    build_contextualize_prompt,
    build_user_prompt,
)
from app.schemas.chat import ChatResponse, SourceItem, SourceLoc, SourceType
from app.services.llm import generate_answer
from app.services.retriever import Retriever

logger = logging.getLogger(__name__)


def _score_to_confidence(score: float) -> str:
    if score >= 0.85:
        return "high"
    if score >= 0.65:
        return "medium"
    return "low"


class RAGService:
    def __init__(self) -> None:
        self.retriever = Retriever()

    def answer(
        self,
        question: str,
        *,
        domain: str,
        top_k: int,
        doc_name: str | None = None,
        history: list[dict] | None = None,
    ) -> ChatResponse:
        search_query = question
        if history:
            rewrite_prompt = build_contextualize_prompt(history, question)
            rewritten = generate_answer(
                CONTEXTUALIZE_SYSTEM_PROMPT,
                rewrite_prompt,
                use_heavy=False,
            )
            logger.debug("Original query: %s | Rewritten query: %s", question, rewritten)
            search_query = rewritten

        hits = self.retriever.search(
            search_query,
            top_k=top_k,
            domain=domain,
            doc_name=doc_name,
        )

        # Use top-scoring context snippets for answer generation.
        context_hits = sorted(hits, key=lambda x: x["score"], reverse=True)[:5]

        context_lines: list[str] = []
        sources: list[SourceItem] = []

        for idx, hit in enumerate(context_hits, start=1):
            meta = hit["meta"]
            source_type = SourceType(meta.get("type", "manual"))
            title = meta.get("title", meta.get("path", "unknown"))
            path = meta.get("path", "unknown")
            source_id = meta.get("source_id", f"{source_type}:{path}:{idx}")

            loc = SourceLoc(
                page=meta.get("page"),
                start=meta.get("start"),
                end=meta.get("end"),
                line_start=meta.get("line_start"),
                line_end=meta.get("line_end"),
            )

            snippet = hit["text"][:900]

            source = SourceItem(
                source_id=source_id,
                title=title,
                type=source_type,
                path=path,
                loc=loc,
                snippet=snippet,
                score=hit["score"],
            )
            sources.append(source)

            cite = _format_cite_tag(source)
            context_lines.append(f"[{idx}] {cite}\n{snippet}\n")

        context_block = "\n".join(context_lines)
        user_prompt = build_user_prompt(search_query, context_block)
        answer = generate_answer(SYSTEM_PROMPT, user_prompt, use_heavy=True)

        top_score = sources[0].score if sources else 0.0
        notes = (
            "근거 자료가 없는 내용은 추정하지 않습니다."
            if sources
            else "관련 근거를 찾지 못했습니다."
        )

        return ChatResponse(
            answer=answer,
            sources=sources,
            confidence=_score_to_confidence(top_score),
            notes=notes,
        )


def _format_cite_tag(src: SourceItem) -> str:
    if src.type == SourceType.code and src.loc.line_start and src.loc.line_end:
        return f"[code:{src.title} L{src.loc.line_start}-L{src.loc.line_end}]"
    if src.loc.page:
        return f"[{src.type}:{src.title} p.{src.loc.page}]"
    return f"[{src.type}:{src.title}]"
