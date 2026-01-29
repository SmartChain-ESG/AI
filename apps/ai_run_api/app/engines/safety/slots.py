
# =========================
# 3) 슬롯 정의 & 파일명→슬롯 매칭
#    - 이번에 올린 실제 파일명 기준 패턴을 강화
# =========================

from __future__ import annotations

import re
from typing import NamedTuple


class SlotDef(NamedTuple):
    name: str
    required: bool
    patterns: list[re.Pattern[str]]


SLOTS: list[SlotDef] = [
    # (선택) TBM — 이번 테스트 업로드에는 없음
    SlotDef(
        name="safety.tbm",
        required=False,
        patterns=[
            re.compile(r"(?i)\btbm\b|tool.?box.?meet|작업전.?회의|TBM"),
        ],
    ),

    # 교육 이수 현황 (xlsx)
    SlotDef(
        name="safety.education.status",
        required=True,
        patterns=[
            re.compile(r"(?i)edu.*status|교육.*현황|교육.*이수|안전교육.*현황|안전교육이수현황"),
        ],
    ),

    # 소방 점검표 (pdf/xlsx)
    SlotDef(
        name="safety.fire.inspection",
        required=True,
        patterns=[
            re.compile(r"(?i)fire.*insp|소방.*점검|소방시설.*점검|소방시설자체점검|자체점검.*결과표"),
        ],
    ),

    # 위험성평가서 (xlsx/pdf)
    SlotDef(
        name="safety.risk.assessment",
        required=True,
        patterns=[
            re.compile(r"(?i)risk.?assess|위험성.?평가|위험성평가서"),
        ],
    ),

    # 안전보건관리체계(매뉴얼) — S1 구성요건 검사용 (pdf)
    SlotDef(
        name="safety.management.system",
        required=True,
        patterns=[
            re.compile(r"(?i)management.*system|안전보건관리체계|관리체계.*매뉴얼|체계구축매뉴얼"),
        ],
    ),

    # 일반 점검표(선택)
    SlotDef(
        name="safety.checklist",
        required=False,
        patterns=[
            re.compile(r"(?i)safety.?check|안전.?점검|점검표"),
        ],
    ),

    # 현장 사진(선택) — 이미지 묶음/단일
    SlotDef(
        name="safety.site.photos",
        required=False,
        patterns=[
            re.compile(r"(?i)site.?photo|현장.?사진|현장사진"),
        ],
    ),

    # 교육 출석부 (스캔 PDF) — 날짜, 교육명, 이름, 서명
    SlotDef(
        name="safety.education.attendance",
        required=False,
        patterns=[
            re.compile(r"(?i)attend|출석부|출석명단|교육.*출석|출석.*명부"),
        ],
    ),

    # 교육일 사진 (이미지) — 교육 현장 촬영본
    SlotDef(
        name="safety.education.photo",
        required=False,
        patterns=[
            re.compile(r"(?i)edu.*photo|교육.*사진|교육일.*사진|교육현장"),
        ],
    ),
]


def get_required_slot_names() -> list[str]:
    return [s.name for s in SLOTS if s.required]


def get_all_slot_names() -> list[str]:
    return [s.name for s in SLOTS]


def match_filename_to_slot(filename: str) -> tuple[str, float] | None:
    """
    파일명 기반 1차 매칭.
    - confidence는 규칙 기반 초기값(추후: 파일 내용/메타 검증으로 보정)
    """
    for slot in SLOTS:
        for pat in slot.patterns:
            if pat.search(filename):
                # required 슬롯은 약간 더 신뢰도 부여
                base = 0.88 if slot.required else 0.85
                return slot.name, base
    return None
