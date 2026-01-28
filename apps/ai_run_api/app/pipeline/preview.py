# app/pipeline/preview.py

"""
Preview 파이프라인 (기획서 §4.1).

1. 입력 검증
2. 파일명 키워드 매칭 → 슬롯 추정
3. 도메인별 필수 슬롯과 비교 → 현황판
4. package_id 발급(첫 호출) + 누적 저장 + 결과 반환
"""

from __future__ import annotations

from app.engines.registry import get_slots_module
from app.schemas.run import (
    FileRef,
    PreviewRequest,
    PreviewResponse,
    SlotHint,
    SlotStatus,
)
from app.storage.tmp_store import get_or_create, update_hints, update_statuses


def _suggest_slots(files: list[FileRef], domain: str) -> list[SlotHint]:
    slots_mod = get_slots_module(domain)
    hints: list[SlotHint] = []
    for f in files:
        fname = f.file_name or f.storage_uri.rsplit("/", 1)[-1]
        result = slots_mod.match_filename_to_slot(fname)
        if result:
            slot_name, confidence = result
            hints.append(
                SlotHint(
                    file_id=f.file_id,
                    slot_name=slot_name,
                    confidence=confidence,
                    match_reason="filename_keyword",
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
            statuses.append(SlotStatus(slot_name=slot.name, status="SUBMITTED"))
        elif slot.required:
            statuses.append(SlotStatus(slot_name=slot.name, status="MISSING"))
            missing.append(slot.name)
        else:
            statuses.append(SlotStatus(slot_name=slot.name, status="MISSING"))

    return statuses, missing


def run_preview(req: PreviewRequest) -> PreviewResponse:
    # 1. package_id 발급/조회 + 누적 저장소
    state = get_or_create(req.package_id, req.domain)

    # 2. 새 파일 슬롯 추정
    new_hints = _suggest_slots(req.added_files, req.domain)

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
