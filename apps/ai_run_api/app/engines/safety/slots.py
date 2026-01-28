"""Safety 도메인 — 슬롯 정의 & 파일명→슬롯 매칭 (도트 표기법)."""

from __future__ import annotations

import re
from typing import NamedTuple


class SlotDef(NamedTuple):
    name: str
    required: bool
    patterns: list[re.Pattern[str]]


SLOTS: list[SlotDef] = [
    SlotDef(
        name="safety.tbm",
        required=True,
        patterns=[re.compile(r"(?i)tbm|tool.?box.?meet|작업전.?회의")],
    ),
    SlotDef(
        name="safety.education.status",
        required=True,
        patterns=[re.compile(r"(?i)edu.*status|교육.*현황|교육.*이수")],
    ),
    SlotDef(
        name="safety.fire.inspection",
        required=True,
        patterns=[re.compile(r"(?i)fire.*insp|소방.*점검")],
    ),
    SlotDef(
        name="safety.risk.assessment",
        required=True,
        patterns=[re.compile(r"(?i)risk.?assess|위험성.?평가")],
    ),
    SlotDef(
        name="safety.checklist",
        required=False,
        patterns=[re.compile(r"(?i)safety.?check|안전.?점검")],
    ),
    SlotDef(
        name="safety.site.photos",
        required=False,
        patterns=[re.compile(r"(?i)site.?photo|현장.?사진")],
    ),
]


def get_required_slot_names() -> list[str]:
    return [s.name for s in SLOTS if s.required]


def get_all_slot_names() -> list[str]:
    return [s.name for s in SLOTS]


def match_filename_to_slot(filename: str) -> tuple[str, float] | None:
    for slot in SLOTS:
        for pat in slot.patterns:
            if pat.search(filename):
                return slot.name, 0.85
    return None
