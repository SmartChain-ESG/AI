# app/engines/esg/slots.py

"""
ESG 도메인 — 슬롯 정의 + 파일명 매칭
"""

from __future__ import annotations

import re
from typing import NamedTuple


class SlotDef(NamedTuple):
    name: str
    required: bool
    patterns: list[re.Pattern[str]]


SLOTS: list[SlotDef] = [
    # ── 에너지(E) ─────────────────────────────────────────
    SlotDef(
        name="esg.energy.electricity.usage_xlsx",
        required=True,
        patterns=[re.compile(r"(?i)(electric|power|kwh|전력|전기).*?(usage|사용|meter|계측)")],
    ),
    SlotDef(
        name="esg.energy.electricity.bill_pdf",
        required=True,
        patterns=[re.compile(r"(?i)(electric|power|전기).*?(bill|고지서|요금)")],
    ),
    SlotDef(
        name="esg.energy.gas.usage_xlsx",
        required=True,
        patterns=[re.compile(r"(?i)(gas|m3|m³|도시가스).*?(usage|사용|meter|계측)")],
    ),
    SlotDef(
        name="esg.energy.gas.bill_pdf",
        required=True,
        patterns=[re.compile(r"(?i)(gas|도시가스).*?(bill|고지서|요금)")],
    ),
    # 옵션: 수도 (있으면 데모 강화)
    SlotDef(
        name="esg.energy.water.usage_xlsx",
        required=False,
        patterns=[re.compile(r"(?i)(water|수도|상수도|하수도).*?(usage|사용|meter|계측)")],
    ),
    SlotDef(
        name="esg.energy.water.bill_pdf",
        required=False,
        patterns=[re.compile(r"(?i)(water|수도|상수도|하수도).*?(bill|고지서|요금)")],
    ),

    # ── 유해물질(E/S 혼합) ───────────────────────────────
    SlotDef(
        name="esg.hazmat.inventory_xlsx",
        required=True,  # 데모에서 누락 FAIL 만들기 좋음
        patterns=[re.compile(r"(?i)(haz|chemical|유해|화학|물질).*?(list|inventory|목록|대장)")],
    ),
    SlotDef(
        name="esg.hazmat.msds_pdf",
        required=True,
        patterns=[re.compile(r"(?i)msds|물질안전|sds")],
    ),
    SlotDef(
        name="esg.hazmat.disposal_xlsx",
        required=True,
        patterns=[re.compile(r"(?i)(disposal|waste|폐기|처리).*?(list|목록|대장|xlsx)")],
    ),
    SlotDef(
        name="esg.hazmat.disposal_pdf",
        required=True,
        patterns=[re.compile(r"(?i)(disposal|waste|폐기|처리).*(pdf|인계서|계약서|올바로)")],
    ),

    # ── 윤리강령(G) ──────────────────────────────────────
    SlotDef(
        name="esg.governance.ethics.latest_pdf",
        required=True,
        patterns=[re.compile(r"(?i)(ethics|code|윤리|행동강령).*(최신|latest|v3\.5|개정)")],
    ),
    SlotDef(
        name="esg.governance.ethics.old_pdf",
        required=False,
        patterns=[re.compile(r"(?i)(ethics|code|윤리|행동강령).*(구버전|old|v3\.2)")],
    ),
    SlotDef(
        name="esg.governance.distribution_log_xlsx",
        required=False,
        patterns=[re.compile(r"(?i)(배포|수신확인|distribution|ack).*?(log|xlsx)")],
    ),
    SlotDef(
        name="esg.governance.pledge_pdf",
        required=False,
        patterns=[re.compile(r"(?i)(pledge|서약)")],
    ),
    SlotDef(
        name="esg.governance.poster_image",
        required=False,
        patterns=[re.compile(r"(?i)(poster|포스터|사진|scan|스캔).*(윤리|행동강령|ethics)")],
    ),
]


def get_required_slot_names() -> list[str]:
    return [s.name for s in SLOTS if s.required]


def get_all_slot_names() -> list[str]:
    return [s.name for s in SLOTS]


def match_filename_to_slot(filename: str) -> tuple[str, float] | None:
    """파일명 키워드 매칭 (preview 단계에서 사용)"""
    for slot in SLOTS:
        for pat in slot.patterns:
            if pat.search(filename or ""):
                return slot.name, 0.85
    return None