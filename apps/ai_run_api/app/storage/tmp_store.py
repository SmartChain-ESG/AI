"""인메모리 패키지 저장소 — preview 누적용 (기획서 §2.3).

package_id 기준으로 slot_hint / required_slot_status를 누적 저장한다.
추후 DB(PostgreSQL)로 교체 예정.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from app.schemas.run import SlotHint, SlotStatus


@dataclass
class PackageState:
    package_id: str
    domain: str
    slot_hints: list[SlotHint] = field(default_factory=list)
    slot_statuses: list[SlotStatus] = field(default_factory=list)


_store: dict[str, PackageState] = {}


def generate_package_id() -> str:
    return f"PKG_{uuid.uuid4().hex[:12].upper()}"


def get_or_create(package_id: str | None, domain: str) -> PackageState:
    if package_id and package_id in _store:
        return _store[package_id]
    pid = package_id or generate_package_id()
    state = PackageState(package_id=pid, domain=domain)
    _store[pid] = state
    return state


def update_hints(package_id: str, new_hints: list[SlotHint]) -> None:
    state = _store[package_id]
    # file_id가 겹치면 최신으로 덮어쓰기 위해 맵으로 관리
    hint_map = {h.file_id: h for h in state.slot_hints}
    for h in new_hints:
        hint_map[h.file_id] = h
    state.slot_hints = list(hint_map.values())


def remove_hints(package_id: str, file_ids: list[str]) -> None:
    """삭제된 파일 ID 목록을 받아 저장소에서 제거한다."""
    if package_id not in _store:
        return
    state = _store[package_id]
    state.slot_hints = [h for h in state.slot_hints if h.file_id not in file_ids]


def update_statuses(package_id: str, statuses: list[SlotStatus]) -> None:
    _store[package_id].slot_statuses = statuses


def get_state(package_id: str) -> PackageState | None:
    return _store.get(package_id)
