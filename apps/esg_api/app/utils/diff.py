# app/utils/diff.py
from __future__ import annotations

from typing import Any


def _issue_key(issue: dict[str, Any]) -> str:
    # code + slot_name 기준으로 “동일 이슈”를 식별
    code = str(issue.get("code", ""))
    slot = str(issue.get("slot_name", ""))
    return f"{code}::{slot}"


def _count_levels(issues: list[dict[str, Any]]) -> tuple[int, int]:
    fail = 0
    warn = 0
    for it in issues:
        lv = str(it.get("level", "")).upper()
        if lv == "FAIL":
            fail += 1
        elif lv == "WARN":
            warn += 1
    return fail, warn


def esg_compute_resubmit_diff(prev_result: dict | None, current_result: dict) -> dict:
    """
    A-3 재제출 개선 비교
    - fixed_issues: 이전엔 있었는데 지금은 사라진 이슈
    - new_issues: 이전엔 없었는데 지금 생긴 이슈
    - delta_fail/warn: FAIL/WARN 건수 변화량
    """
    curr_issues = list(current_result.get("issues", []) or [])
    curr_fail, curr_warn = _count_levels(curr_issues)

    if not prev_result:
        return {
            "has_previous": False,
            "previous_status": None,
            "current_status": current_result.get("status"),
            "delta_fail": 0,
            "delta_warn": 0,
            "fixed_issues": [],
            "new_issues": [],
            "note": "",
        }

    prev_issues = list(prev_result.get("issues", []) or [])
    prev_fail, prev_warn = _count_levels(prev_issues)

    prev_map = {_issue_key(i): i for i in prev_issues}
    curr_map = {_issue_key(i): i for i in curr_issues}

    fixed_keys = sorted(list(set(prev_map.keys()) - set(curr_map.keys())))
    new_keys = sorted(list(set(curr_map.keys()) - set(prev_map.keys())))

    fixed_issues = [{"code": prev_map[k].get("code"), "slot_name": prev_map[k].get("slot_name")} for k in fixed_keys]
    new_issues = [{"code": curr_map[k].get("code"), "slot_name": curr_map[k].get("slot_name")} for k in new_keys]

    return {
        "has_previous": True,
        "previous_status": prev_result.get("status"),
        "current_status": current_result.get("status"),
        "delta_fail": curr_fail - prev_fail,
        "delta_warn": curr_warn - prev_warn,
        "fixed_issues": fixed_issues,
        "new_issues": new_issues,
        "note": "이전 실행 결과와 비교한 개선/변경 내역입니다.",
    }