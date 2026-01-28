"""Compliance 도메인 — 슬롯 정의 (확장자 필터링 + 파일명 매칭).

- 슬롯별로 파일명 키워드(정규식) 기반 매칭을 수행한다.
- 확장자 필터링으로 .zip/.exe 등 비허용 파일은 빠르게 제외한다.

Return:
    match_filename_to_slot(): (slot_name, confidence) 또는 None
"""

from __future__ import annotations

import os
import re
from typing import NamedTuple


# 1) 허용 확장자 그룹 정의
EXT_DOCS = {".pdf", ".jpg", ".jpeg", ".png", ".tif", ".tiff"}  # 문서/이미지
EXT_DATA = {".xlsx", ".xls", ".csv"}  # 데이터
EXT_ALL = EXT_DOCS | EXT_DATA


class SlotDef(NamedTuple):
    name: str
    display_name: str
    required: bool
    patterns: list[re.Pattern[str]]
    accepted_exts: set[str]  # 허용 확장자


SLOTS: list[SlotDef] = [
    # 1. 근로계약서 + 하도급계약서
    SlotDef(
        name="compliance.contract.sample",
        display_name="표준 근로/하도급 계약서",
        required=True,
        # ✅ | 우선순위 안전하게 괄호로 묶음
        patterns=[re.compile(r"(?i)((근로|하도급).*계약|contract.*sample)")],
        accepted_exts=EXT_ALL,
    ),
    # 2. 개인정보교육
    SlotDef(
        name="compliance.education.privacy",
        display_name="개인정보보호 교육 이수 현황",
        required=True,
        patterns=[re.compile(r"(?i)(개인정보.*(교육|이수)|privacy.*edu)")],
        accepted_exts=EXT_ALL,
    ),
    # 3. 공정거래 점검표
    SlotDef(
        name="compliance.fair.trade",
        display_name="공정거래 자율 점검표",
        required=True,
        patterns=[re.compile(r"(?i)(공정거래.*점검|fair.*trade.*check)")],
        accepted_exts=EXT_ALL,
    ),
    # 4. 윤리경영 (선택)
    SlotDef(
        name="compliance.ethics.report",
        display_name="윤리경영 내부신고 현황",
        required=False,
        patterns=[re.compile(r"(?i)(부정부패|윤리경영|ethics.*report)")],
        accepted_exts=EXT_ALL,
    ),
    # 5. 컴플라이언스/법정의무 교육 (선택)
    SlotDef(
        name="compliance.education.plan",
        display_name="법정의무 교육 계획서",
        required=False,
        patterns=[re.compile(r"(?i)((컴플라이언스|법정의무).*교육|compliance.*plan)")],
        accepted_exts=EXT_ALL,
    ),
]


def match_filename_to_slot(filename: str) -> tuple[str, float] | None:
    """파일명 기반으로 슬롯을 추정한다.

    Args:
        filename: 업로드된 원본 파일명

    Return:
        (slot_name, confidence) 또는 None
    """
    # 1) 확장자 추출(소문자)
    _, ext = os.path.splitext(filename)
    ext = ext.lower()

    # 2) 파일명 정규화
    clean_name = filename.replace("_", " ").replace("-", " ")
    clean_name = re.sub(r"\s+", " ", clean_name).strip()  # ✅ 공백 정리 추가

    for slot in SLOTS:
        # 3) 확장자 필터링
        if ext not in slot.accepted_exts:
            continue

        # 4) 패턴 매칭
        for pat in slot.patterns:
            if pat.search(clean_name):
                return slot.name, 1.0

    return None


def get_required_slot_names() -> list[str]:
    return [s.name for s in SLOTS if s.required]


def get_all_slot_names() -> list[str]:
    return [s.name for s in SLOTS]