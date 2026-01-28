"""Compliance 도메인 — 슬롯 정의 (기획서 §5.2). 담당자 확정 후 채울 것."""

from __future__ import annotations

import re
from typing import NamedTuple


class SlotDef(NamedTuple):
    name: str
    required: bool
    patterns: list[re.Pattern[str]]


SLOTS: list[SlotDef] = [
    SlotDef(
        name="compliance.contract.sample",
        required=True,
        patterns=[re.compile(r"(?i)contract.*sample|표준.*근로.*계약")],
    ),
    SlotDef(
        name="compliance.contract.status",
        required=True,
        patterns=[re.compile(r"(?i)contract.*status|계약.*현황")],
    ),
    SlotDef(
        name="compliance.privacy.policy",
        required=True,
        patterns=[re.compile(r"(?i)privacy|개인정보.*처리|보안.*지침")],
    ),
    SlotDef(
        name="compliance.education.status",
        required=True,
        patterns=[re.compile(r"(?i)compliance.*edu|컴플.*교육|준법.*교육")],
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
