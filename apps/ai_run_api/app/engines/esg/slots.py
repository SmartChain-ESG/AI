"""ESG 도메인 — 슬롯 정의 (기획서 §5.3). 담당자 확정 후 채울 것."""

from __future__ import annotations

import re
from typing import NamedTuple


class SlotDef(NamedTuple):
    name: str
    required: bool
    patterns: list[re.Pattern[str]]


SLOTS: list[SlotDef] = [
    SlotDef(
        name="esg.energy.usage",
        required=True,
        patterns=[re.compile(r"(?i)energy.*usage|전력.*사용|가스.*사용|에너지.*사용")],
    ),
    SlotDef(
        name="esg.energy.bill",
        required=False,
        patterns=[re.compile(r"(?i)energy.*bill|고지서|요금")],
    ),
    SlotDef(
        name="esg.hazmat.msds",
        required=True,
        patterns=[re.compile(r"(?i)msds|물질안전|유해물질")],
    ),
    SlotDef(
        name="esg.ethics.code",
        required=False,
        patterns=[re.compile(r"(?i)ethics|윤리.*강령")],
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
