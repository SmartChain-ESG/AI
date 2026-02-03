# AI/apps/ai_run_api/ui/streamlit_app.py

"""AI Run API 테스트 UI — Streamlit."""

from __future__ import annotations

import os
import tempfile
import uuid
from datetime import date, timedelta

import httpx
import pandas as pd
import streamlit as st

# ── 페이지 설정 ──────────────────────────────────────────
st.set_page_config(page_title="AI Run API", layout="wide")
st.title("AI Run API - Test UI")

# ── 사이드바 ─────────────────────────────────────────────
with st.sidebar:
    st.header("Settings")
    api_base = st.text_input("API Base URL", value="http://localhost:8000")
    domain = st.selectbox("Domain", ["safety", "compliance", "esg"])
    period_start = st.date_input("Period Start", value=date.today() - timedelta(days=90))
    period_end = st.date_input("Period End", value=date.today())

# ── 파일 업로드 (공통) ───────────────────────────────────
uploaded_files = st.file_uploader(
    "Upload files (PDF / XLSX / JPG / PNG)",
    type=["pdf", "xlsx", "xls", "csv", "jpg", "jpeg", "png"],
    accept_multiple_files=True,
)

# session state 초기화
if "package_id" not in st.session_state:
    st.session_state.package_id = None
if "slot_hints" not in st.session_state:
    st.session_state.slot_hints = []
if "file_refs" not in st.session_state:
    st.session_state.file_refs = []


def _save_uploaded_files(files) -> list[dict]:
    """업로드 파일을 임시 디렉토리에 저장하고 FileRef 목록 반환."""
    refs = []
    for f in files:
        file_id = str(uuid.uuid4())
        tmp_dir = tempfile.gettempdir()
        path = os.path.join(tmp_dir, f"{file_id}_{f.name}")
        with open(path, "wb") as fp:
            fp.write(f.getbuffer())
        refs.append({
            "file_id": file_id,
            "storage_uri": path.replace("\\", "/"),
            "file_name": f.name,
        })
    return refs


# ── 탭 ──────────────────────────────────────────────────
tab_preview, tab_submit = st.tabs(["Preview", "Submit"])

# ═══════════════════════════════════════════════════════════
# TAB 1: PREVIEW
# ═══════════════════════════════════════════════════════════
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
                resp = httpx.post(
                    f"{api_base}/run/preview",
                    json=payload,
                    timeout=30.0,
                )
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                st.error(f"API Error: {e}")
                data = None

        if data:
            st.session_state.package_id = data["package_id"]
            st.session_state.slot_hints = data.get("slot_hint", [])

            st.success(f"package_id: `{data['package_id']}`")

            # slot_hint 테이블
            hints = data.get("slot_hint", [])
            if hints:
                st.markdown("**Slot Hints**")
                df_hints = pd.DataFrame(hints)
                st.dataframe(df_hints, use_container_width=True)
            else:
                st.info("No slots matched.")

            # required_slot_status 테이블
            statuses = data.get("required_slot_status", [])
            if statuses:
                st.markdown("**Required Slot Status**")
                df_status = pd.DataFrame(statuses)

                def _highlight_missing(row):
                    if row["status"] == "MISSING":
                        return ["background-color: #ffcccc"] * len(row)
                    return [""] * len(row)

                st.dataframe(
                    df_status.style.apply(_highlight_missing, axis=1),
                    use_container_width=True,
                )

            # missing slots
            missing = data.get("missing_required_slots", [])
            if missing:
                st.warning(f"Missing required slots: {', '.join(missing)}")

    if not uploaded_files:
        st.caption("Upload files to run preview.")

# ═══════════════════════════════════════════════════════════
# TAB 2: SUBMIT
# ═══════════════════════════════════════════════════════════
with tab_submit:
    st.subheader("Submit - Full Validation")

    # package_id 표시
    pkg_id = st.session_state.package_id
    if pkg_id:
        st.info(f"package_id: `{pkg_id}`")
    else:
        st.warning("Run Preview first to get a package_id.")

    # slot_hint 편집
    hints = st.session_state.slot_hints
    if hints:
        st.markdown("**Slot Hints (editable)**")
        df_edit = pd.DataFrame(hints)
        edited = st.data_editor(df_edit, use_container_width=True, num_rows="dynamic")
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
                resp = httpx.post(
                    f"{api_base}/run/submit",
                    json=payload,
                    timeout=120.0,
                )
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                st.error(f"API Error: {e}")
                data = None

        if data:
            # verdict + risk badge
            verdict = data.get("verdict", "")
            risk = data.get("risk_level", "")

            col1, col2 = st.columns(2)
            with col1:
                if verdict == "PASS":
                    st.success(f"Verdict: {verdict}")
                else:
                    st.error(f"Verdict: {verdict}")
            with col2:
                if risk == "HIGH":
                    st.error(f"Risk Level: {risk}")
                else:
                    st.success(f"Risk Level: {risk}")

            # why
            st.markdown("**Why**")
            st.write(data.get("why", ""))

            # slot_results 테이블
            slot_results = data.get("slot_results", [])
            if slot_results:
                st.markdown("**Slot Results**")
                rows = []
                for sr in slot_results:
                    rows.append({
                        "slot_name": sr["slot_name"],
                        "verdict": sr["verdict"],
                        "reasons": ", ".join(sr.get("reasons", [])),
                        "file_names": ", ".join(sr.get("file_names", [])),
                    })
                df_sr = pd.DataFrame(rows)

                def _highlight_verdict(row):
                    if row["verdict"] == "PASS":
                        return ["background-color: #ccffcc"] * len(row)
                    return ["background-color: #ffcccc"] * len(row)

                st.dataframe(
                    df_sr.style.apply(_highlight_verdict, axis=1),
                    use_container_width=True,
                )

            # clarifications
            clarifications = data.get("clarifications", [])
            if clarifications:
                st.markdown("**Clarifications**")
                for cl in clarifications:
                    with st.expander(f"{cl['slot_name']}"):
                        st.write(cl["message"])
                        if cl.get("file_ids"):
                            st.caption(f"Files: {', '.join(cl['file_ids'])}")

            # extras
            extras = data.get("extras", {})
            if extras:
                st.markdown("**Extras**")
                st.json(extras)

    if not pkg_id:
        st.caption("Run Preview first, then come here to submit.")
