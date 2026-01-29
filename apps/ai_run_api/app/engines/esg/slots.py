# app/engines/esg/slots.py

"""
ESG 도메인 — 슬롯 정의 + 파일명 기반 슬롯 추정기 (Soft Gate 버전)

목표
- Preview에서는 "파일명만"으로 슬롯 추정.
- 0매칭(미분류) 방지: '도메인 신호' 또는 '문서 목적 신호'가 하나만 있어도 후보로는 잡는다.
- 과매칭 방지: 둘 다 있을 때 점수를 크게 주고, 점수 하한선을 두어 아무 파일이나 매칭되지 않게 한다.
- 다중 후보가 걸리면 score로 1등 선택 (첫 매칭 즉시 반환 X)
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable


# -----------------------------
# 유틸: 파일명 정규화
# -----------------------------
_SEP_RE = re.compile(r"[\s\-_()\[\]{}]+")


def _norm(s: str) -> str:
    s = (s or "").strip()
    s = _SEP_RE.sub(" ", s)
    return s.lower()


def _has_any(text: str, keywords: Iterable[str]) -> bool:
    return any(k in text for k in keywords)


def _count_any(text: str, keywords: Iterable[str]) -> int:
    return sum(1 for k in keywords if k in text)


@dataclass(frozen=True)
class SlotDef:
    name: str
    required: bool

    # 20250129 이종헌 수정: 기존 "AND 조건(둘 다 만족해야 후보)"을 "점수 그룹"으로 사용
    # - must_any_1: 도메인 신호(전기/가스/윤리 등)
    # - must_any_2: 문서 목적 신호(usage/bill/log/pledge 등)
    # => 이제는 둘 중 하나만 있어도 후보가 될 수 있음(0매칭 방지)
    must_any_1: tuple[str, ...]
    must_any_2: tuple[str, ...]
    boost: tuple[str, ...]
    regex: re.Pattern[str] | None = None


# -----------------------------
# 키워드 사전(너무 넓지 않게)
# -----------------------------
K_ELEC = ("전기", "전력", "electricity", "electric", "kepco", "한전")
K_GAS = ("도시가스", "가스", "gas")
K_WATER = ("수도", "상수도", "하수도", "water", "수자원", "물")

K_USAGE = ("사용량", "usage", "meter", "계측", "측정", "interval", "15분", "15min", "kwh", "m3", "㎥")
K_BILL = ("고지서", "요금", "청구서", "bill", "invoice", "statement", "납부")

K_GHG = ("ghg", "scope", "배출계수", "산정", "방법론", "emission factor", "inventory")

K_MSDS = ("msds", "sds", "물질안전", "물질 안전", "보건자료", "material safety")
K_HAZ = ("유해", "화학", "위험", "hazmat", "chemical", "물질")
K_INV = ("목록", "리스트", "inventory", "재고", "보관", "storage", "stock")
K_DISPOSAL = ("폐기", "처리", "반출", "위탁", "disposal", "waste", "manifest", "올바로", "인계서", "인수인계", "처리확인", "consignment")

K_ETHICS = ("윤리", "행동강령", "윤리강령", "code of conduct", "conduct", "ethic", "ethics")
K_LOG = ("배포", "수신", "확인율", "로그", "distribution", "receipt", "ack", "read")
K_PLEDGE = ("서약서", "확인서", "pledge", "acknowledgement", "acknowledgment")
K_POSTER = ("포스터", "poster", "캠페인", "campaign", "홍보")


# -----------------------------
# 슬롯 정의
# -----------------------------
SLOTS: list[SlotDef] = [
    # Energy
    SlotDef(
        name="esg.energy.electricity.usage",
        required=True,
        must_any_1=K_ELEC,
        must_any_2=K_USAGE,
        boost=("usage_kwh", "kwh", "15분", "15min", "interval"),
    ),
    SlotDef(
        name="esg.energy.electricity.bill",
        required=False,
        must_any_1=K_ELEC,
        must_any_2=K_BILL,
        boost=("invoice", "bill", "statement", "고지서", "청구서"),
    ),
    SlotDef(
        name="esg.energy.gas.usage",
        required=True,
        must_any_1=K_GAS,
        must_any_2=K_USAGE,
        boost=("flow_m3", "m3", "㎥", "energy_mj", "mj"),
    ),
    SlotDef(
        name="esg.energy.gas.bill",
        required=False,
        must_any_1=K_GAS,
        must_any_2=K_BILL,
        boost=("invoice", "bill", "statement", "고지서", "청구서"),
    ),
    SlotDef(
        name="esg.energy.water.usage",
        required=False,
        must_any_1=K_WATER,
        must_any_2=K_USAGE,
        boost=("m3", "㎥", "water usage"),
    ),
    SlotDef(
        name="esg.energy.water.bill",
        required=False,
        must_any_1=K_WATER,
        must_any_2=K_BILL,
        boost=("invoice", "bill", "statement", "고지서", "청구서"),
    ),
    SlotDef(
        name="esg.energy.ghg.evidence",
        required=False,
        must_any_1=("ghg", "온실가스", "탄소", "co2", "scope"),
        must_any_2=K_GHG,
        boost=("emission factor", "배출계수", "scope1", "scope2"),
    ),

    # Hazmat
    SlotDef(
        name="esg.hazmat.msds",
        required=True,
        must_any_1=K_MSDS,
        must_any_2=K_HAZ,  # NOTE: 이제 "필수 게이트"가 아니라 점수 그룹
        boost=("msds", "sds", "material safety"),
    ),
    SlotDef(
        name="esg.hazmat.inventory",
        required=False,
        must_any_1=K_HAZ,
        must_any_2=K_INV,
        boost=("inventory", "재고", "보관", "storage"),
    ),
    SlotDef(
        name="esg.hazmat.disposal.list",
        required=False,
        must_any_1=K_DISPOSAL,
        must_any_2=("목록", "list", "manifest", "대장"),
        boost=("manifest", "올바로", "인계서"),
    ),
    SlotDef(
        name="esg.hazmat.disposal.evidence",
        required=False,
        must_any_1=K_DISPOSAL,
        must_any_2=("계약", "확인", "인계", "증빙", "pdf", "document", "report"),
        boost=("올바로", "인계서", "처리확인", "위탁"),
    ),

    # Ethics / Governance
    SlotDef(
        name="esg.ethics.code",
        required=True,
        must_any_1=K_ETHICS,
        must_any_2=("개정", "revision", "시행", "policy", "규정", "강령", "code"),
        boost=("code of conduct", "윤리강령", "행동강령"),
    ),
    SlotDef(
        name="esg.ethics.distribution.log",
        required=False,
        must_any_1=K_ETHICS,
        must_any_2=K_LOG,
        boost=("확인율", "distribution", "log", "receipt"),
    ),
    SlotDef(
        name="esg.ethics.pledge",
        required=False,
        must_any_1=K_ETHICS,
        must_any_2=K_PLEDGE,
        boost=("서약서", "pledge", "확인서"),
    ),
    SlotDef(
        name="esg.ethics.poster.image",
        required=False,
        must_any_1=K_POSTER,
        must_any_2=K_ETHICS,
        boost=("poster", "포스터", "캠페인"),
    ),
]


def get_required_slot_names() -> list[str]:
    return [s.name for s in SLOTS if s.required]


def get_all_slot_names() -> list[str]:
    return [s.name for s in SLOTS]


# 20260129 이종헌 수정: 과매칭 방지용 “최소 점수” (0매칭 방지와 과매칭 방지의 균형값)
_MIN_SCORE = 4

# 20260129 이종헌 수정: 둘 다(도메인+목적) 맞으면 확실히 올려주는 보너스
_PAIR_BONUS = 3


def match_filename_to_slot(filename: str) -> tuple[str, float] | None:
    """
    파일명만 보고 슬롯 추정(점수 기반, Soft Gate).

    20260129 이종헌 수정:
    - 기존: must_any_1 + must_any_2 를 "둘 다 만족"해야만 후보
    - 변경: 둘 중 하나라도 있으면 후보로 올리고,
            둘 다 있으면 점수(=confidence)를 크게 올려 1등으로 뽑히게 한다.
    - 단, 최소 점수(_MIN_SCORE) 미만이면 None 반환(아무거나 매칭 방지)
    """
    f = _norm(filename)
    if not f:
        return None

    best_slot: str | None = None
    best_score: int = 0

    for s in SLOTS:
        has1 = _has_any(f, s.must_any_1)
        has2 = _has_any(f, s.must_any_2)
        has_regex = bool(s.regex and s.regex.search(f))

        # 20260129 이종헌 수정: 하드 AND 제거: 둘 다 없어도 되는 게 아니라,
        #           "아무 신호도 없으면" 후보 제외 (랜덤 매칭 방지)
        if not (has1 or has2 or has_regex):
            continue

        score = 0

        # 20260129 이종헌 수정: 그룹별로 점수 부여 (하나만 있어도 점수는 생김)
        if has1:
            score += 2
            score += _count_any(f, s.must_any_1)

        if has2:
            score += 2
            score += _count_any(f, s.must_any_2)

        # 20260129 이종헌 수정: 둘 다 맞으면 추가 보너스 → 정확한 파일명이면 확실히 1등
        if has1 and has2:
            score += _PAIR_BONUS

        # boost는 그대로 가산
        score += _count_any(f, s.boost)

        # regex 보강
        if has_regex:
            score += 2

        if score > best_score:
            best_score = score
            best_slot = s.name

    # 20260129 이종헌 수정: 최소 점수 미달이면 매칭 안 함(과매칭 방지)
    if not best_slot or best_score < _MIN_SCORE:
        return None

    # 20260129 이종헌 수정: 점수 구간 재조정(Soft Gate 점수 체계에 맞춤)
    # 대략:
    # - 4~6: 약한 매칭(단어 1~2개만 맞은 수준)
    # - 7~10: 보통(도메인/목적 둘 중 하나 확실 + boost 일부)
    # - 11+: 강함(도메인+목적 모두 + boost 다수)
    if best_score <= 6:
        conf = 0.78
    elif best_score <= 10:
        conf = 0.85
    else:
        conf = 0.92

    return best_slot, conf
