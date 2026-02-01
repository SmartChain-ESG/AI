# AI/apps/out_risk_api/app/analyze/summarizer.py

# 20260131 이종헌 신규: ESG 외부 리스크 문서 요약/근거/추정(strict grounding) 생성기 (LLM optional)
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Optional

from app.schemas.risk import Category

try:
    from langchain_openai import ChatOpenAI
    _LC_AVAILABLE = True
except Exception:
    ChatOpenAI = None
    _LC_AVAILABLE = False


@dataclass
class esg_SummaryResult:
    summary_ko: str
    why: str
    is_estimated: bool


# 역할: 근거 텍스트가 너무 짧아 '추정' 처리해야 하는지 판단
def esg_is_evidence_weak(text: str) -> bool:
    t = (text or "").strip()
    return len(t) < 40


# 역할: strict 모드에서 추정이면 summary 앞에 '추정:'을 붙임
def esg_prefix_if_needed(strict: bool, is_estimated: bool, text: str) -> str:
    if strict and is_estimated and not (text or "").startswith("추정"):
        return "추정: " + (text or "")
    return text or ""


# 역할: ESG 외부 리스크 관점에서 2~3문장 요약 + 근거 문장 1개(why) 생성
def esg_summarize_and_why(
    text: str,
    category: Category,
    severity: int,
    strict_grounding: bool,
    model: Optional[str] = None,
) -> esg_SummaryResult:
    base = (text or "").strip()

    if not base:
        return esg_SummaryResult(
            summary_ko="추정: 외부 문서 근거가 충분하지 않습니다.",
            why="근거 부족(추정)",
            is_estimated=True,
        )

    weak = esg_is_evidence_weak(base)

    if _LC_AVAILABLE and os.getenv("OPENAI_API_KEY"):
        try:
            llm = ChatOpenAI(
                model=model or os.getenv("OPENAI_MODEL_LIGHT", "gpt-4o-mini"),
                temperature=0,
            )
            prompt = ( # 20260131 이종헌 수정: ESG 전용 컨텍스트 고정
                "너는 '협력사 ESG 외부 리스크'를 요약하는 분석기다.\n" 
                "규칙:\n"
                "- 입력 텍스트(출처)에 없는 사실은 절대 쓰지 말 것\n"
                "- 추정이면 반드시 '추정'이라고 표시할 것\n"
                "- 안전/노동/환경/법규/재무 이슈는 ESG 관점의 외부 위험 신호로만 요약할 것\n"
                f"- 카테고리={category}, 심각도={severity}\n\n"
                "아래 텍스트를 한국어 2~3문장으로 요약하고, 근거가 되는 문장 1개를 why로 그대로 인용해.\n"
                "출력 형식:\n"
                "summary_ko: ...\n"
                "why: ...\n"
                "is_estimated: true/false\n\n"
                "텍스트:\n"
                f"{base[:2500]}"
            )
            msg = llm.invoke(prompt)
            out = str(getattr(msg, "content", msg))

            m1 = re.search(r"summary_ko:\s*(.+)", out)
            m2 = re.search(r"why:\s*(.+)", out)
            m3 = re.search(r"is_estimated:\s*(true|false)", out, re.IGNORECASE)

            summary = (m1.group(1).strip() if m1 else base[:180].replace("\n", " "))
            why = (m2.group(1).strip() if m2 else base[:180].replace("\n", " "))
            is_estimated = (m3.group(1).lower() == "true") if m3 else weak

            summary = esg_prefix_if_needed(strict_grounding, is_estimated, summary)
            return esg_SummaryResult(summary_ko=summary, why=why, is_estimated=is_estimated)
        except Exception:
            pass

    snippet = base[:180].replace("\n", " ")
    is_estimated = weak if strict_grounding else False
    summary = f"{category} 관련 ESG 외부 위험 신호 가능성. {snippet}"  # 20260131 이종헌 수정: ESG 표현 추가
    summary = esg_prefix_if_needed(strict_grounding, is_estimated, summary)
    why = snippet

    return esg_SummaryResult(summary_ko=summary, why=why, is_estimated=is_estimated)
