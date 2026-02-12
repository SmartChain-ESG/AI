# app/pipeline/preview.py

"""
Preview 파이프라인 (기획서 §4.1).

1. 입력 검증
2. 파일명 키워드 매칭 → 슬롯 추정
   2-1. 룰 매칭 실패 시 LLM(light)으로 파일명 기반 슬롯 추정
3. 도메인별 필수 슬롯과 비교 → 현황판
4. package_id 발급(첫 호출) + 누적 저장 + 결과 반환
"""

from __future__ import annotations

import json

from app.engines.registry import get_slots_module
from app.llm.client import ask_llm
from app.schemas.run import (
    FileRef,
    PreviewRequest,
    PreviewResponse,
    SlotHint,
    SlotStatus,
)
from app.storage.tmp_store import get_or_create, remove_hints, update_hints, update_statuses


# ── LLM 슬롯 추정 프롬프트 ──────────────────────────────
_SLOT_MATCH_SYSTEM = (
    "You are a file classification assistant. "
    "Given a filename and a list of available slot names, "
    "determine which slot the file most likely belongs to. "
    "Judge ONLY by filename — do NOT assume file contents.\n"
    "Return JSON only: "
    '{"slot_name": "<best matching slot or null>", "confidence": <0.0-1.0>}\n'
    "If no slot matches at all, return: "
    '{"slot_name": null, "confidence": 0.0}\n'
    "Do NOT wrap in markdown."
)


async def _llm_match_slot(filename: str, slot_names: list[str]) -> tuple[str, float] | None:
    """룰 매칭 실패 시 LLM(light)으로 파일명 → 슬롯 추정."""
    user_msg = (
        f"Filename: {filename}\n"
        f"Available slots: {json.dumps(slot_names, ensure_ascii=False)}\n"
        "Which slot does this file belong to?"
    )
    try:
        raw = await ask_llm(_SLOT_MATCH_SYSTEM, user_msg, heavy=False)
        text = raw.strip()
        # 마크다운 코드블록 제거
        if "```" in text:
            import re
            m = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
            if m:
                text = m.group(1).strip()
        result = json.loads(text)
        slot = result.get("slot_name")
        conf = float(result.get("confidence", 0.0))
        if slot and slot in slot_names and conf > 0.3:
            return slot, round(conf, 2)
    except Exception:
        pass
    return None


async def _suggest_slots(files: list[FileRef], domain: str) -> list[SlotHint]:
    slots_mod = get_slots_module(domain)
    all_slot_names = [s.name for s in slots_mod.SLOTS]
    # slot_name -> display_name 매핑
    display_name_map = {s.name: s.display_name for s in slots_mod.SLOTS}
    hints: list[SlotHint] = []

    # LLM 폴백이 필요한 파일 모으기
    unmatched: list[tuple[FileRef, str]] = []

    for f in files:
        fname = f.file_name or f.storage_uri.rsplit("/", 1)[-1]
        result = slots_mod.match_filename_to_slot(fname)
        if result:
            slot_name, _ = result
            hints.append(
                SlotHint(
                    file_id=f.file_id,
                    slot_name=slot_name,
                    display_name=display_name_map.get(slot_name, ""),
                    confidence=0.99,
                    match_reason="filename_keyword",
                )
            )
        else:
            unmatched.append((f, fname))

    # 매칭 안 된 파일 → LLM 폴백
    for f, fname in unmatched:
        llm_result = await _llm_match_slot(fname, all_slot_names)
        if llm_result:
            slot_name, confidence = llm_result
            hints.append(
                SlotHint(
                    file_id=f.file_id,
                    slot_name=slot_name,
                    display_name=display_name_map.get(slot_name, ""),
                    confidence=confidence,
                    match_reason="llm_filename",
                )
            )

    return hints


def _evaluate_coverage(
    all_hints: list[SlotHint], domain: str
) -> tuple[list[SlotStatus], list[str]]:
    slots_mod = get_slots_module(domain)
    provided = {h.slot_name for h in all_hints}
    all_slots = slots_mod.SLOTS

    statuses: list[SlotStatus] = []
    missing: list[str] = []
    for slot in all_slots:
        if slot.name in provided:
            statuses.append(SlotStatus(slot_name=slot.name, display_name=slot.display_name, status="SUBMITTED"))
        elif slot.required:
            statuses.append(SlotStatus(slot_name=slot.name, display_name=slot.display_name, status="MISSING"))
            missing.append(slot.name)
        else:
            statuses.append(SlotStatus(slot_name=slot.name, display_name=slot.display_name, status="MISSING"))

    return statuses, missing


async def run_preview(req: PreviewRequest) -> PreviewResponse:
    # 1. package_id 발급/조회 + 누적 저장소
    state = get_or_create(req.package_id, req.domain)

    # 1-1. 삭제된 파일 힌트 제거 (누적 상태 업데이트)
    if req.removed_file_ids:
        remove_hints(state.package_id, req.removed_file_ids)

    # 2. 새 파일 슬롯 추정 (룰 + LLM 폴백)
    new_hints = await _suggest_slots(req.added_files, req.domain)

    # 3. 누적 저장
    update_hints(state.package_id, new_hints)

    # 4. 현황판 생성 (누적 기준)
    statuses, missing = _evaluate_coverage(state.slot_hints, req.domain)
    update_statuses(state.package_id, statuses)

    return PreviewResponse(
        package_id=state.package_id,
        slot_hint=state.slot_hints,
        required_slot_status=statuses,
        missing_required_slots=missing,
    )
