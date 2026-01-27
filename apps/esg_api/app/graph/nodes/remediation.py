# app/graph/nodes/remediation.py
"""
A-2) 보완요청서 생성 노드 (Day5: LLM 토글 + 폴백)
- 입력: issues(+extracted optional)
- 출력: state["questions"] (list[str])  ※ Day4 호환 키 유지
원칙:
- LLM_MODE=off 이거나 키가 없거나 호출 실패해도 ALWAYS 룰 기반(base_qs)로 동작
- LLM은 '문장 다듬기(polish)'만 수행 (판정/팩트 생성 금지)
"""

from __future__ import annotations

import os
from typing import Any

from app.graph.state import EsgGraphState
from app.llm.openai_client import esg_try_llm_parse_structured
from app.llm.schemas import EsgLLMQuestionsOutput
from app.utils.llm_flag import esg_is_llm_enabled, esg_llm_trace_record


def esg_remediation_template(issues: list[dict[str, Any]]) -> list[str]:
    """
    룰 기반 보완요청 문장 생성 (항상 동작, 데모 안정성 확보)
    - FAIL/WARN 중심
    - 최대 6개
    """
    qs: list[str] = []
    for it in issues:
        lvl = str(it.get("level", "")).upper()
        if lvl not in ("FAIL", "WARN"):
            continue

        code = str(it.get("code", "")).upper()
        slot = it.get("slot_name") or it.get("slotName") or "unknown"
        msg = it.get("message") or "관련 근거가 필요합니다."

        if code in ("ANOMALY_SPIKE_RATIO", "SPIKE_RATIO_WARN", "MISSING_BASELINE"):
            qs.append(
                "전력 사용량 급증(10/12~10/19) 원인 확인을 위해 아래 자료를 추가 제출해 주세요: "
                "① 전기요금 고지서 원본(PDF) ② 계측기 교정 성적서(해당 기간) "
                "③ 생산량/가동률 일별 또는 주간 데이터(XLSX/CSV)."
            )
        elif code in ("MISSING_CODE_OF_CONDUCT", "CANNOT_VERIFY_APPROVAL_INFO"):
            qs.append(
                "행동강령/윤리 서약 문서의 최신 승인본을 제출해 주세요. "
                "승인일/결의 주체/버전 정보가 포함된 파일(이미지 또는 PDF)을 권장합니다."
            )
        elif code == "MISSING_ISO_45001":
            qs.append("ISO 45001 인증서(PDF)를 제출해 주세요. 유효기간/발급기관/인증번호가 보이도록 제출 바랍니다.")
        elif code == "MISSING_ELECTRICITY_2024":
            qs.append("전년 대비 비교를 위해 2024년 전기 사용량 파일(XLSX)을 추가 제출해 주세요.")
        else:
            qs.append(f"[보완요청] ({slot}) {msg} (이슈코드: {code}) 관련 추가 근거/원본 자료를 제출해 주세요.")

        if len(qs) >= 6:
            break

    return qs if qs else ["[보완요청] 추가 자료 제출을 요청드립니다."]


def esg_remediation_llm(*, issues: list[dict[str, Any]], extracted: list[dict[str, Any]] | None = None) -> list[str] | None:
    """
    LLM로 문장 품질만 개선(polish)
    - facts/meaning 변경 금지
    - 결과는 {questions:[...]} JSON 스키마로만 받음
    """
    base_qs = esg_remediation_template(issues)

    model = os.getenv("OPENAI_MODEL_ISSUE", "gpt-5-mini")
    system = (
        "You are an enterprise compliance assistant.\n"
        "Rewrite the given draft requests into concise, polite Korean.\n"
        "- Do NOT invent facts.\n"
        "- Do NOT change the meaning.\n"
        "- Keep 2~6 items.\n"
        "Return ONLY valid JSON: {\"questions\": [\"...\"]}\n"
    )
    user = (
        f"draft_questions = {base_qs}\n"
        f"issues = {issues}\n"
        f"extracted = {extracted or []}\n"
        "Return improved questions (2~6)."
    )

    parsed = esg_try_llm_parse_structured(
        model=model,
        system=system,
        user=user,
        schema_model=EsgLLMQuestionsOutput,
        temperature=0.2,
        max_output_tokens=500,
    )
    if not parsed or not getattr(parsed, "questions", None):
        return None

    # 길이 제한/정리
    cleaned = [q.strip() for q in parsed.questions if isinstance(q, str) and q.strip()]
    return cleaned[:6] if cleaned else None


def esg_remediation_node(state: EsgGraphState) -> EsgGraphState:
    issues = state.get("issues", []) or []
    extracted = state.get("extracted", []) or []
    llm_trace = state.get("llm_trace")

    # 1) 룰 기반은 항상 생성
    base_qs = esg_remediation_template(issues)

    # 2) LLM 토글 OFF면 즉시 반환
    if not esg_is_llm_enabled():
        if llm_trace:
            esg_llm_trace_record(llm_trace, node="remediation", used=False, fallback=True, error="LLM disabled")
        state["questions"] = base_qs
        return state

    # 3) LLM ON이면 polish 시도, 실패하면 base 유지
    try:
        polished = esg_remediation_llm(issues=issues, extracted=extracted)
        if llm_trace:
            esg_llm_trace_record(llm_trace, node="remediation", used=True, fallback=(polished is None))
        state["questions"] = polished or base_qs
        return state
    except Exception as e:
        if llm_trace:
            esg_llm_trace_record(llm_trace, node="remediation", used=True, fallback=True, error=str(e))
        state["questions"] = base_qs
        return state