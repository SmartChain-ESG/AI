# app/engines/esg/slots.py

"""
ESG 도메인 — 슬롯 정의 + 파일명 기반 슬롯 추정기

- Preview 단계에서는 파일명만 보고 슬롯을 "추정"한다.
- 너무 넓게 매칭되면 아무거나 잡히므로,
  1) 전기/가스/수도는 usage/bill을 분리
  2) 윤리강령/배포로그/서약서도 분리
  3) "고지서" 같은 약한 단어는 단독으로 과매칭하지 않게 설계
"""

from __future__ import annotations

import re
from typing import NamedTuple


class SlotDef(NamedTuple):
    name: str
    required: bool
    patterns: list[re.Pattern[str]]


# -----------------------------
# 공통: 파일명 정규화 유틸(간단)
# -----------------------------
_SEP_RE = re.compile(r"[\s\-_()\[\]{}]+")


def _norm(s: str) -> str:
    s = s.strip()
    s = _SEP_RE.sub(" ", s)
    return s


# -----------------------------
# 패턴 설계 원칙
# - STRONG: 단독으로도 슬롯을 특정할 수 있는 패턴
# - WEAK: 단독으로는 과매칭 위험 → 다른 단어와 함께 있을 때만 의미
#   => 여기서는 WEAK를 가능한 한 STRONG 패턴에 포함(AND 형태)로 구성
# -----------------------------

# 전기 사용량(usage): "전력/전기 + 사용량" or "Usage_kWh" or "kWh meter/interval"
_ELEC_USAGE = re.compile(
    r"(?i)"
    r"("
    r"(전기|전력|electric(ity)?|kepco|한전).*(사용|사용량|usage|meter|계측|측정)"
    r"|"
    r"(usage[_\-\s]?kwh|kwh[_\-\s]?usage|power[_\-\s]?usage)"
    r"|"
    r"(15\s*min|15분|quarter\s*hour|interval).*(kwh|전력|전기)"
    r")"
)

# 전기 고지서(bill): "전기/전력/한전 + 고지서/요금/청구서" or "bill/invoice/statement + electricity"
_ELEC_BILL = re.compile(
    r"(?i)"
    r"("
    r"(전기|전력|electric(ity)?|kepco|한전).*(고지서|요금|청구서|invoice|bill|statement)"
    r"|"
    r"(bill|invoice|statement).*(electric(ity)?|kepco|한전|전기|전력)"
    r")"
)

# 도시가스 사용량(usage): "도시가스/가스 + 사용량" or "flow_m3/energy_MJ"
_GAS_USAGE = re.compile(
    r"(?i)"
    r"("
    r"(도시\s*가스|도시가스|gas).*(사용|사용량|usage|meter|계측|측정)"
    r"|"
    r"(flow[_\-\s]?m3|m3[_\-\s]?flow|energy[_\-\s]?mj|calorific)"
    r"|"
    r"(co2e|탄소|온실가스).*(gas|가스|도시가스)"
    r")"
)

# 도시가스 고지서(bill): "도시가스 + 고지서/요금" or "bill + gas"
_GAS_BILL = re.compile(
    r"(?i)"
    r"("
    r"(도시\s*가스|도시가스|gas).*(고지서|요금|청구서|invoice|bill|statement)"
    r"|"
    r"(bill|invoice|statement).*(gas|도시가스|가스)"
    r")"
)

# 수도 사용량(usage): "수도/상수도/물 + 사용량" or "water usage" or "m3 + water"
_WATER_USAGE = re.compile(
    r"(?i)"
    r"("
    r"(수도|상수도|하수도|물|water).*(사용|사용량|usage|meter|계측|측정)"
    r"|"
    r"(water[_\-\s]?usage|usage[_\-\s]?water)"
    r"|"
    r"(m3|㎥).*(수도|상수도|water|물)"
    r")"
)

# 수도 고지서(bill): "수도/상수도 + 고지서/요금" or "bill + water"
_WATER_BILL = re.compile(
    r"(?i)"
    r"("
    r"(수도|상수도|하수도|water|물).*(고지서|요금|청구서|invoice|bill|statement)"
    r"|"
    r"(bill|invoice|statement).*(water|수도|상수도|물)"
    r")"
)

# GHG 산정 근거(옵션): "배출계수/방법론/Scope/산정식"
_GHG_EVIDENCE = re.compile(
    r"(?i)"
    r"(ghg|scope\s*[12]|배출계수|산정(식|방법)|방법론|emission\s*factor|inventory)"
)

# MSDS/SDS: "MSDS/SDS/물질안전보건자료"
_HAZ_MSDS = re.compile(
    r"(?i)"
    r"(msds|sds|물질\s*안전\s*보건\s*자료|물질안전|안전\s*자료|material\s*safety)"
)

# 유해물질 목록 xlsx: "유해물질/화학물질 + 목록/재고/보관"
_HAZ_INVENTORY = re.compile(
    r"(?i)"
    r"("
    r"(유해|화학|위험|hazmat|chemical).*(목록|리스트|inventory|재고|보관|storage|stock)"
    r")"
)

# 폐기/처리 목록 xlsx: "폐기/처리 + 목록" or "disposal manifest"
_HAZ_DISPOSAL_LIST = re.compile(
    r"(?i)"
    r"(폐기|처리|반출|위탁).*(목록|리스트|list|manifest)"
)

# 폐기/처리 증빙 pdf: "올바로/인계서/위탁계약/처리확인" 등
_HAZ_DISPOSAL_EVIDENCE = re.compile(
    r"(?i)"
    r"(올바로|인계서|인수인계|위탁\s*계약|처리\s*확인|disposal|consignment|manifest|waste)"
)

# 윤리강령/행동강령(본 문서)
_ETHICS_CODE = re.compile(
    r"(?i)"
    r"(윤리\s*강령|행동\s*강령|code\s*of\s*conduct|ethics(\s*code)?|conduct\s*code)"
)

# 배포/수신확인 로그 xlsx
_ETHICS_DISTR_LOG = re.compile(
    r"(?i)"
    r"(배포|수신|확인율|수신\s*확인|distribution|ack(nowledg(e|ment))?|read\s*receipt|log)"
)

# 서약서 pdf
_ETHICS_PLEDGE = re.compile(
    r"(?i)"
    r"(서약서|확인서|pledge|acknowledg(e|ment)\s*form)"
)

# 윤리 포스터/사진(흐림 OCR 데모 용도) — 너무 넓게 잡지 않게 poster/포스터/캠페인 필수
_ETHICS_POSTER_IMAGE = re.compile(
    r"(?i)"
    r"(포스터|poster|캠페인|campaign).*(윤리|행동|ethic|conduct)"
)


SLOTS: list[SlotDef] = [
    # --- Energy (usage/bill) ---
    SlotDef(name="esg.energy.electricity.usage", required=True, patterns=[_ELEC_USAGE]),
    SlotDef(name="esg.energy.electricity.bill", required=False, patterns=[_ELEC_BILL]),
    SlotDef(name="esg.energy.gas.usage", required=True, patterns=[_GAS_USAGE]),
    SlotDef(name="esg.energy.gas.bill", required=False, patterns=[_GAS_BILL]),
    SlotDef(name="esg.energy.water.usage", required=False, patterns=[_WATER_USAGE]),
    SlotDef(name="esg.energy.water.bill", required=False, patterns=[_WATER_BILL]),
    SlotDef(name="esg.energy.ghg.evidence", required=False, patterns=[_GHG_EVIDENCE]),
    # --- Hazmat ---
    SlotDef(name="esg.hazmat.msds", required=True, patterns=[_HAZ_MSDS]),
    SlotDef(name="esg.hazmat.inventory", required=False, patterns=[_HAZ_INVENTORY]),
    SlotDef(name="esg.hazmat.disposal.list", required=False, patterns=[_HAZ_DISPOSAL_LIST]),
    SlotDef(name="esg.hazmat.disposal.evidence", required=False, patterns=[_HAZ_DISPOSAL_EVIDENCE]),
    # --- Governance (Ethics) ---
    SlotDef(name="esg.ethics.code", required=True, patterns=[_ETHICS_CODE]),
    SlotDef(name="esg.ethics.distribution.log", required=False, patterns=[_ETHICS_DISTR_LOG]),
    SlotDef(name="esg.ethics.pledge", required=False, patterns=[_ETHICS_PLEDGE]),
    SlotDef(name="esg.ethics.poster.image", required=False, patterns=[_ETHICS_POSTER_IMAGE]),
]


def get_required_slot_names() -> list[str]:
    return [s.name for s in SLOTS if s.required]


def get_all_slot_names() -> list[str]:
    return [s.name for s in SLOTS]


def match_filename_to_slot(filename: str) -> tuple[str, float] | None:
    """
    파일명만 보고 슬롯 추정.
    - 첫 매칭을 반환하되, "강한 패턴"일수록 confidence를 조금 더 준다.
    - 여기서는 단순하게:
        * 매칭되면 기본 0.85
        * 특정 키워드가 더 포함되면 0.90~0.95로 상승
    """
    fname = _norm(filename)

    for slot in SLOTS:
        for pat in slot.patterns:
            if pat.search(fname):
                conf = 0.85

                # 아주 간단한 가산점(과하지 않게)
                f = fname.lower()
                if slot.name.endswith(".usage") and ("usage_kwh" in f or "flow_m3" in f or "energy_mj" in f):
                    conf = 0.95
                elif slot.name.endswith(".bill") and ("invoice" in f or "statement" in f or "bill" in f or "고지서" in fname):
                    conf = 0.92
                elif slot.name == "esg.hazmat.msds" and ("msds" in f or "sds" in f):
                    conf = 0.95
                elif slot.name.startswith("esg.ethics") and ("윤리" in fname or "conduct" in f or "ethic" in f):
                    conf = 0.90

                return slot.name, conf

    return None