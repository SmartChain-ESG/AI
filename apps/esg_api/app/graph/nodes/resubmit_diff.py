# app/graph/nodes/resubmit_diff.py
"""
A-3) resubmit_diff (Deprecated)
- Day4에서는 파일(outputs/{draft_id}_latest.json) 기반으로 비교했지만,
- 지금은 app/main.py에서 DB(prev_result) 기반으로 resubmit_diff를 계산한다.
- 따라서 이 노드는 side-effect(파일 I/O) 없이 no-op로 유지한다.
"""

from __future__ import annotations
from app.graph.state import EsgGraphState

def esg_resubmit_diff_node(state: EsgGraphState) -> EsgGraphState:
    # main.py에서 이미 result_json["resubmit_diff"]를 계산/저장하므로 여기서는 아무것도 하지 않음.
    # 혹시 그래프가 state["resubmit_diff"]를 기대하면 기본 형태만 보장.
    state.setdefault("resubmit_diff", {
        "has_previous": False,
        "previous_status": None,
        "current_status": state.get("status", "OK"),
        "delta_fail": 0,
        "delta_warn": 0,
        "fixed_issues": [],
        "new_issues": [],
        "note": "resubmit_diff는 API 레이어(DB 기반)에서 계산됩니다.",
    })
    return state