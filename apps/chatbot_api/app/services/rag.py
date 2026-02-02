from __future__ import annotations

from app.core.prompts import SYSTEM_PROMPT, CONTEXTUALIZE_SYSTEM_PROMPT, build_user_prompt, build_contextualize_prompt
from app.schemas.chat import ChatResponse, SourceItem, SourceLoc, SourceType
from app.services.llm import generate_answer
from app.services.retriever import Retriever


def _score_to_confidence(score: float) -> str:
    if score >= 0.85:
        return "high"
    if score >= 0.65:
        return "medium"
    return "low"


class RAGService:
    def __init__(self) -> None:
        self.retriever = Retriever()

    def answer(self, question: str, *, domain: str, top_k: int, doc_name: str | None = None, history: list[dict] | None = None) -> ChatResponse:
        # 1. Query Rewriting (대화 맥락이 있으면 질문 구체화)
        search_query = question
        if history:
            # 가벼운 모델(Light)로 빠르게 질문 재구성
            rewrite_prompt = build_contextualize_prompt(history, question)
            rewritten = generate_answer(CONTEXTUALIZE_SYSTEM_PROMPT, rewrite_prompt, use_heavy=False)
            print(f"Original: {question} -> Rewritten: {rewritten}")  # 로그 확인용
            search_query = rewritten

        hits = self.retriever.search(search_query, top_k=top_k, domain=domain, doc_name=doc_name)

        # Top-k 크게 가져오고, 실제 컨텍스트는 3~5개로 압축 (설계서 권장)
        context_hits = sorted(hits, key=lambda x: x["score"], reverse=True)[:5]

        context_lines: list[str] = []
        sources: list[SourceItem] = []

        for idx, h in enumerate(context_hits, start=1):
            meta = h["meta"]
            s_type = SourceType(meta.get("type", "manual"))
            title = meta.get("title", meta.get("path", "unknown"))
            path = meta.get("path", "unknown")
            source_id = meta.get("source_id", f"{s_type}:{path}:{idx}")

            loc = SourceLoc(
                page=meta.get("page"),
                start=meta.get("start"),
                end=meta.get("end"),
                line_start=meta.get("line_start"),
                line_end=meta.get("line_end"),
            )
            snippet = h["text"][:900]  # 컨텍스트 폭주 방지

            sources.append(
                SourceItem(
                    source_id=source_id,
                    title=title,
                    type=s_type,
                    path=path,
                    loc=loc,
                    snippet=snippet,
                    score=h["score"],
                )
            )

            # LLM에 들어갈 컨텍스트 블록: 사람이 봐도 “출처 추적” 가능하게
            cite = _format_cite_tag(sources[-1])
            context_lines.append(f"[{idx}] {cite}\n{snippet}\n")

        context_block = "\n".join(context_lines)
        
        # 최종 답변 생성 시에는 '재구성된 질문'을 사용하여 LLM이 명확한 맥락을 잡도록 함
        user_prompt = build_user_prompt(search_query, context_block)

        # 답변 생성: 기본은 heavy로(너 설계 기준: 최종 답변은 heavy)
        answer = generate_answer(SYSTEM_PROMPT, user_prompt, use_heavy=True)

        top_score = sources[0].score if sources else 0.0
        return ChatResponse(
            answer=answer,
            sources=sources,
            confidence=_score_to_confidence(top_score),
            notes="근거 자료에 없는 내용은 추정하지 않았습니다." if sources else "관련 근거를 찾지 못했습니다.",
        )


def _format_cite_tag(src: SourceItem) -> str:
    if src.type == SourceType.code and src.loc.line_start and src.loc.line_end:
        return f"[code:{src.title} L{src.loc.line_start}-L{src.loc.line_end}]"
    if src.loc.page:
        return f"[{src.type}:{src.title} p.{src.loc.page}]"
    return f"[{src.type}:{src.title}]"
