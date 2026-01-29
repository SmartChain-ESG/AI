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

# 20260129 이종헌 추가: mac 파일 글자 깨짐 방지
from urllib.parse import unquote
import unicodedata

# 20260129 이종헌 추가: 코드변수로 필수 슬롯 제어
ENABLE_OPTIONAL_DEMO_SLOTS = False  # False=필수만, True=필수+옵션

_SLOTS_ALL: list["SlotDef"] | None = None  # 원본 백업


def _refresh_slots() -> None:
    global SLOTS, _SLOTS_ALL
    if _SLOTS_ALL is None:
        _SLOTS_ALL = list(SLOTS)  # 최초 1회 백업

    SLOTS = list(_SLOTS_ALL) if ENABLE_OPTIONAL_DEMO_SLOTS else [s for s in _SLOTS_ALL if s.required]
        
        
# -----------------------------
# 유틸: 파일명 정규화
# -----------------------------
_SEP_RE = re.compile(r"[\s\-_()\[\]{}]+")


# 20260129 이종헌 수정: ZIP 파일명 모지바케(cp437로 잘못 디코딩된 UTF-8)를 복구
def _hangul_count(s: str) -> int:
    return sum(1 for ch in s if "\uac00" <= ch <= "\ud7a3")


# 20260129 이종헌 수정: zipfile에서 종종 발생하는 cp437->utf8 깨짐 복구 시도
def _recover_zip_mojibake(s: str) -> str:
    """
    ZIP 내부 파일명이 cp437로 잘못 디코딩되어 'ßä...' 같은 형태로 깨진 경우,
    bytes를 다시 cp437로 encode한 뒤 utf-8로 decode하면 복구되는 케이스가 많다.
    """
    if not s:
        return s
    try:
        fixed = s.encode("cp437").decode("utf-8")
        # 복구 결과가 '더 한글스러우면' 채택
        if _hangul_count(fixed) > _hangul_count(s):
            return fixed
    except Exception:
        pass
    return s


# 20260129 이종헌 수정: 다양한 파일명 케이스 커버
# slots.py - import/정규식 정의 구간에 추가
_ID_PREFIX_RE = re.compile(r"^[0-9a-f]{8,}[_\-]+", re.IGNORECASE)

# 20260129 이종헌 수정: mac파일명 깨짐 방지
def _norm(s: str) -> str:
    s = (s or "").strip()
    # presigned url 등 query 제거 (storage_uri가 들어오는 케이스 대응)
    s = s.split("?", 1)[0]
    # 경로가 들어오면 basename만 사용
    s = s.rsplit("/", 1)[-1]
    # URL 인코딩된 파일명 복원 (%EA%.. -> 한글)
    s = unquote(s)
    # ZIP 모지바케 복구
    s = _recover_zip_mojibake(s)
    # macOS 한글(NFD) → NFC 정규화 (키워드 매칭 안정화)
    s = unicodedata.normalize("NFC", s)
    # file_id prefix 제거(있으면)
    s = _ID_PREFIX_RE.sub("", s)

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
K_LOG = ("배포", "수신", "확인율", "로그", "distribution", "receipt", "ack", "read", "배포로그")
K_PLEDGE = ("서약서", "확인서", "pledge", "acknowledgement", "acknowledgment")
K_POSTER = ("포스터", "poster", "캠페인", "campaign", "홍보", "사진", "image", "이미지")


# -----------------------------
# 슬롯 정의
# -----------------------------
# 20260129 이종헌 수정: 목데이터 수정으로 인한 필수 슬롯 변경
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
        required=True,
        must_any_1=K_WATER,
        must_any_2=K_USAGE,
        boost=("m3", "㎥", "water usage", "수도사용량"),
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
        must_any_2=K_HAZ,
        boost=("msds", "sds", "material safety"),
    ),
    SlotDef(
        name="esg.hazmat.inventory",
        required=True, 
        must_any_1=K_HAZ,
        must_any_2=K_INV,
        boost=("inventory", "재고", "보관", "storage", "유해물질목록"),
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
        required=True,
        must_any_1=K_ETHICS,
        must_any_2=K_LOG,
        boost=("확인율", "distribution", "log", "receipt", "배포로그", "배포", "로그"),
    ),
    SlotDef(
        name="esg.ethics.pledge",
        required=True,  
        must_any_1=K_ETHICS,
        must_any_2=K_PLEDGE,
        boost=("서약서", "pledge", "확인서", "acknowledgement", "acknowledgment"),
    ),
    SlotDef(
        name="esg.ethics.poster.image",
        required=True,
        must_any_1=K_POSTER,
        must_any_2=K_ETHICS,
        boost=("poster", "포스터", "캠페인", "사진", "image", "이미지"),
    ),
]


def get_required_slot_names() -> list[str]:
    _refresh_slots()
    return [s.name for s in SLOTS if s.required]


def get_all_slot_names() -> list[str]:
    _refresh_slots()
    return [s.name for s in SLOTS]


# 20260129 이종헌 수정: 과매칭 방지용 “최소 점수” (0매칭 방지와 과매칭 방지의 균형값)
_MIN_SCORE = 4

# 20260129 이종헌 수정: 둘 다(도메인+목적) 맞으면 확실히 올려주는 보너스
_PAIR_BONUS = 3


def match_filename_to_slot(filename: str) -> tuple[str, float] | None:
    _refresh_slots()
    """
    파일명만 보고 슬롯 추정(점수 기반, Soft Gate).
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

        if not (has1 or has2 or has_regex):
            continue

        score = 0

        if has1:
            score += 2
            score += _count_any(f, s.must_any_1)

        if has2:
            score += 2
            score += _count_any(f, s.must_any_2)

        if has1 and has2:
            score += _PAIR_BONUS

        score += _count_any(f, s.boost)

        if has_regex:
            score += 2

        if s.name == "esg.ethics.code":
            if _has_any(f, K_LOG) or _has_any(f, K_PLEDGE) or _has_any(f, K_POSTER):
                score -= 4  # log/pledge/poster 신호가 있으면 code 감점

        if score > best_score:
            best_score = score
            best_slot = s.name
            

    if not best_slot or best_score < _MIN_SCORE:
        return None

    if best_score <= 6:
        conf = 0.78
    elif best_score <= 10:
        conf = 0.85
    else:
        conf = 0.92

    return best_slot, conf