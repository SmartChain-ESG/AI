"""도메인별 엔진 디스패치 — slots/rules를 domain 문자열로 가져온다."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.engines.safety import slots as safety_slots, rules as safety_rules
from app.engines.compliance import slots as comp_slots, rules as comp_rules
from app.engines.esg import slots as esg_slots, rules as esg_rules

if TYPE_CHECKING:
    from types import ModuleType

_SLOT_MODULES: dict[str, ModuleType] = {
    "safety": safety_slots,
    "compliance": comp_slots,
    "esg": esg_slots,
}

_RULE_MODULES: dict[str, ModuleType] = {
    "safety": safety_rules,
    "compliance": comp_rules,
    "esg": esg_rules,
}


def get_slots_module(domain: str):
    return _SLOT_MODULES[domain]


def get_rules_module(domain: str):
    return _RULE_MODULES[domain]
