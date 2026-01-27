# AI/apps/esg_api/app/graph/nodes/slotting.py
"""
2) 슬롯 매핑 노드 (Day5)
- 규칙 기반 우선(데모 안정)
- unresolved만 LLM 보조
- LLM off/실패 시 폴백
"""

from __future__ import annotations

import os
from typing import Optional, Any

from app.graph.state import EsgGraphState
from app.llm.openai_client import esg_try_llm_parse_structured
from app.llm.schemas import EsgLLMSlottingOutput
from app.utils.llm_flag import esg_is_llm_enabled, esg_llm_trace_record


_ALLOWED_ITEMS = [
    "electricity_usage_2024",
    "electricity_usage_2025",
    "iso_45001",
    "code_of_conduct",
]


def _rule_based_slot(file_name: str, kind: str | None) -> Optional[str]:
    n = (file_name or "").lower()

    if kind == "XLSX":
        if "2024" in n:
            return "electricity_usage_2024"
        if "2025" in n:
            return "electricity_usage_2025"
        return None  # 연도 누락 -> unresolved로 LLM 보조 대상

    if kind == "PDF":
        return "iso_45001"

    if kind == "IMAGE":
        return "code_of_conduct"

    return None


def esg_slotting_node(state: EsgGraphState) -> EsgGraphState:
    files = state.get("files", []) or []
    llm_trace = state.get("llm_trace")

    # allowed_items는 Form으로 들어올 수도 있고, 없으면 기본값
    allowed_items = state.get("allowed_items") or _ALLOWED_ITEMS
    if not isinstance(allowed_items, list) or not allowed_items:
        allowed_items = _ALLOWED_ITEMS

    slot_hint = state.get("slot_hint")  # dict or None (있으면 프롬프트에 참고만)

    slot_map: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []

    # 1) 규칙 기반 먼저 매핑
    for f in files:
        fid = f.get("file_id")
        if not fid:
            continue

        slot = _rule_based_slot(f.get("file_name", ""), f.get("kind"))
        if slot:
            slot_map.append(
                {
                    "file_id": fid,
                    "slot_name": slot,
                    "reason": "rule-based mapping (demo fixed set)",
                    "confidence": 0.98,
                }
            )
        else:
            unresolved.append(
                {
                    "file_id": fid,
                    "file_name": f.get("file_name"),
                    "ext": f.get("ext"),
                    "kind": f.get("kind"),
                }
            )

    # 2) LLM 토글: unresolved만 LLM 보조
    if unresolved and esg_is_llm_enabled():
        try:
            system = (
                "You are a strict JSON generator.\n"
                "Map each file to exactly one slot_name from allowed_items.\n"
                "Return ONLY valid JSON that matches the schema.\n"
                "Use ONLY file_name/ext/kind and optional slot_hint.\n"
            )
            user = (
                f"allowed_items = {allowed_items}\n"
                f"slot_hint = {slot_hint}\n"
                f"files = {unresolved}\n\n"
                "Output schema:\n"
                "{ slot_map: [ { file_id, slot_name, reason, confidence } ] }\n"
            )

            model = os.getenv("OPENAI_MODEL_SLOT", "gpt-5-mini")
            parsed = esg_try_llm_parse_structured(
                model=model,
                system=system,
                user=user,
                schema_model=EsgLLMSlottingOutput,
                temperature=0.1,
                max_output_tokens=500,
            )

            if parsed:
                for it in parsed.slot_map:
                    slot_map.append(
                        {
                            "file_id": it.file_id,
                            "slot_name": it.slot_name,
                            "reason": it.reason,
                            "confidence": float(it.confidence),
                        }
                    )
                if llm_trace:
                    esg_llm_trace_record(llm_trace, node="slotting", used=True, fallback=False)
            else:
                # LLM이 None을 반환 -> 폴백
                for uf in unresolved:
                    slot_map.append(
                        {
                            "file_id": uf["file_id"],
                            "slot_name": "electricity_usage_2025",
                            "reason": "fallback (LLM returned null) - assume latest year",
                            "confidence": 0.2,
                        }
                    )
                if llm_trace:
                    esg_llm_trace_record(llm_trace, node="slotting", used=True, fallback=True, error="LLM returned null")

        except Exception as e:
            # LLM 호출 실패 -> 폴백
            for uf in unresolved:
                slot_map.append(
                    {
                        "file_id": uf["file_id"],
                        "slot_name": "electricity_usage_2025",
                        "reason": "fallback (LLM error) - assume latest year",
                        "confidence": 0.2,
                    }
                )
            if llm_trace:
                esg_llm_trace_record(llm_trace, node="slotting", used=True, fallback=True, error=str(e))

    else:
        # LLM 비활성인데 unresolved가 있으면 폴백만 수행
        if unresolved:
            for uf in unresolved:
                slot_map.append(
                    {
                        "file_id": uf["file_id"],
                        "slot_name": "electricity_usage_2025",
                        "reason": "fallback (LLM disabled) - assume latest year",
                        "confidence": 0.2,
                    }
                )
            if llm_trace:
                esg_llm_trace_record(llm_trace, node="slotting", used=False, fallback=True, error="LLM disabled")

    # 3) 모든 file_id가 1개 슬롯을 갖도록 강제 보정
    mapped = {m["file_id"] for m in slot_map}
    for f in files:
        fid = f.get("file_id")
        if fid and fid not in mapped:
            slot_map.append(
                {
                    "file_id": fid,
                    "slot_name": "electricity_usage_2025",
                    "reason": "forced fill to avoid missing mapping",
                    "confidence": 0.1,
                }
            )

    state["slot_map"] = slot_map
    return state