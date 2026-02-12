"""AI Run API test UI."""

from __future__ import annotations

import os
import re
import tempfile
import uuid
from datetime import date, timedelta

import httpx
import pandas as pd
import streamlit as st

st.set_page_config(page_title="AI Run API", layout="wide")
st.title("AI Run API - Test UI")


def _save_uploaded_files(files) -> list[dict]:
    refs: list[dict] = []
    for f in files:
        file_id = str(uuid.uuid4())
        path = os.path.join(tempfile.gettempdir(), f"{file_id}_{f.name}")
        with open(path, "wb") as fp:
            fp.write(f.getbuffer())
        refs.append(
            {
                "file_id": file_id,
                "storage_uri": path.replace("\\", "/"),
                "file_name": f.name,
            }
        )
    return refs


def _clarification_map(clarifications: list[dict]) -> dict[str, str]:
    out: dict[str, str] = {}
    for cl in clarifications or []:
        slot_name = str(cl.get("slot_name", "")).strip()
        msg = str(cl.get("message", "")).strip()
        if slot_name and msg:
            out[slot_name] = msg
    return out


def _why_breakdown(why_text: str) -> list[dict]:
    rows: list[dict] = []
    for raw in (why_text or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        m = re.match(r"^\[(.*?)\]\s*:\s*(.*)$", line)
        if m:
            rows.append({"file_name": m.group(1).strip(), "reason": m.group(2).strip()})
        else:
            rows.append({"file_name": "-", "reason": line})
    return rows


def _split_points(text: str) -> list[str]:
    if not text:
        return []
    return [x.strip() for x in text.split("|") if x.strip()]


with st.sidebar:
    st.header("Settings")
    api_base = st.text_input("API Base URL", value="http://localhost:8000")
    domain = st.selectbox("Domain", ["safety", "compliance", "esg"])
    period_start = st.date_input("Period Start", value=date.today() - timedelta(days=90))
    period_end = st.date_input("Period End", value=date.today())

uploaded_files = st.file_uploader(
    "Upload files (PDF / XLSX / JPG / PNG)",
    type=["pdf", "xlsx", "xls", "csv", "jpg", "jpeg", "png"],
    accept_multiple_files=True,
)

if "package_id" not in st.session_state:
    st.session_state.package_id = None
if "slot_hints" not in st.session_state:
    st.session_state.slot_hints = []
if "file_refs" not in st.session_state:
    st.session_state.file_refs = []

tab_preview, tab_submit = st.tabs(["Preview", "Submit"])

with tab_preview:
    st.subheader("Preview - Slot Estimation")
    if st.button("Run Preview", disabled=not uploaded_files):
        file_refs = _save_uploaded_files(uploaded_files)
        st.session_state.file_refs = file_refs
        payload = {
            "domain": domain,
            "period_start": str(period_start),
            "period_end": str(period_end),
            "package_id": st.session_state.package_id,
            "added_files": file_refs,
        }
        with st.spinner("Calling /run/preview ..."):
            try:
                resp = httpx.post(f"{api_base}/run/preview", json=payload, timeout=40.0)
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                st.error(f"API Error: {e}")
                data = None
        if data:
            st.session_state.package_id = data["package_id"]
            st.session_state.slot_hints = data.get("slot_hint", [])
            st.success(f"package_id: `{data['package_id']}`")
            if data.get("slot_hint"):
                st.markdown("**Slot Hints**")
                st.dataframe(pd.DataFrame(data["slot_hint"]), use_container_width=True)
            if data.get("required_slot_status"):
                st.markdown("**Required Slot Status**")
                st.dataframe(pd.DataFrame(data["required_slot_status"]), use_container_width=True)
            if data.get("missing_required_slots"):
                st.warning(f"Missing required slots: {', '.join(data['missing_required_slots'])}")

with tab_submit:
    st.subheader("Submit - Full Validation")
    pkg_id = st.session_state.package_id
    if pkg_id:
        st.info(f"package_id: `{pkg_id}`")
    else:
        st.warning("Run Preview first.")

    hints = st.session_state.slot_hints
    if hints:
        st.markdown("**Slot Hints (editable)**")
        edited = st.data_editor(pd.DataFrame(hints), use_container_width=True, num_rows="dynamic")
    else:
        edited = pd.DataFrame()

    if st.button("Run Submit", disabled=(not pkg_id or not st.session_state.file_refs)):
        slot_hint_list = edited.to_dict("records") if not edited.empty else []
        payload = {
            "package_id": pkg_id,
            "domain": domain,
            "period_start": str(period_start),
            "period_end": str(period_end),
            "files": st.session_state.file_refs,
            "slot_hint": slot_hint_list,
        }
        with st.spinner("Calling /run/submit ..."):
            try:
                resp = httpx.post(f"{api_base}/run/submit", json=payload, timeout=180.0)
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                st.error(f"API Error: {e}")
                data = None

        if data:
            verdict = data.get("verdict", "")
            risk = data.get("risk_level", "")
            c1, c2 = st.columns(2)
            with c1:
                (st.success if verdict == "PASS" else st.error)(f"Verdict: {verdict}")
            with c2:
                (st.error if risk == "HIGH" else st.success)(f"Risk Level: {risk}")

            why_text = str(data.get("why", "") or "")
            st.markdown("**Why**")
            st.text(why_text)

            why_rows = _why_breakdown(why_text)
            if why_rows:
                st.markdown("**Why Breakdown (파일별)**")
                st.dataframe(pd.DataFrame(why_rows), use_container_width=True)

            slot_results = data.get("slot_results", []) or []
            clarifications = data.get("clarifications", []) or []
            cl_map = _clarification_map(clarifications)

            if slot_results:
                rows: list[dict] = []
                for sr in slot_results:
                    extras = sr.get("extras", {}) or {}
                    rows.append(
                        {
                            "slot_name": sr.get("slot_name", ""),
                            "verdict": sr.get("verdict", ""),
                            "reasons": ", ".join(sr.get("reasons", [])),
                            "reason_descriptions": extras.get("reason_descriptions", ""),
                            "analysis_message": extras.get("analysis_message", ""),
                            "analysis_detail": extras.get("analysis_detail", ""),
                            "file_names": ", ".join(sr.get("file_names", [])),
                        }
                    )
                st.markdown("**Slot Results**")
                st.dataframe(pd.DataFrame(rows), use_container_width=True)

                st.markdown("**검증 결과 및 특이사항**")
                for sr in slot_results:
                    slot_name = sr.get("slot_name", "unknown")
                    verdict = sr.get("verdict", "")
                    files = ", ".join(sr.get("file_names", []) or [])
                    reasons = ", ".join(sr.get("reasons", []) or [])
                    extras = sr.get("extras", {}) or {}
                    with st.expander(f"{slot_name} | {verdict}", expanded=(verdict != "PASS")):
                        if files:
                            st.caption(f"Files: {files}")
                        st.markdown(f"- 판정: `{verdict}`")
                        if reasons:
                            st.markdown(f"- 사유 코드: `{reasons}`")
                        if extras.get("reason_descriptions"):
                            st.markdown(f"- 사유 설명: {extras['reason_descriptions']}")
                        if extras.get("analysis_message"):
                            st.markdown(f"- 추가 설명: {extras['analysis_message']}")
                        if extras.get("analysis_detail"):
                            st.markdown(f"- 상세 근거: {extras['analysis_detail']}")

                        points_key = "success_points" if verdict == "PASS" else "issue_points"
                        points = _split_points(str(extras.get(points_key, "")))
                        if points:
                            st.markdown("- 근거 항목")
                            for p in points:
                                st.markdown(f"  - {p}")
                        if cl_map.get(slot_name):
                            st.markdown(f"- Clarification: {cl_map[slot_name]}")
            else:
                st.error("slot_results is empty.")

            if clarifications:
                st.markdown("**Clarifications (원문)**")
                for cl in clarifications:
                    title = cl.get("slot_name", "unknown")
                    with st.expander(title):
                        st.write(str(cl.get("message", "")))
                        if cl.get("file_ids"):
                            st.caption(f"Files: {', '.join(cl['file_ids'])}")

            with st.expander("Raw Response (BE 전달용)"):
                st.json(data)

