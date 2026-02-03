from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

import streamlit as st

try:
    import httpx
    _HTTPX_OK = True
except Exception:
    httpx = None
    _HTTPX_OK = False

if TYPE_CHECKING:
    from httpx import Client as HttpxClient
else:
    HttpxClient = Any


def esg_setup_page() -> None:
    st.set_page_config(
        page_title="ESG 외부 이슈 모니터링(참고용)",
        layout="wide",
    )


def esg_escape_md(v: object) -> str:
    s = "" if v is None else str(v)
    return s.replace("|", "\\|").replace("\n", " ")


def esg_to_md_table(rows: List[Dict[str, Any]], max_rows: int = 50) -> str:
    if not rows:
        return "표시할 데이터가 없습니다."

    safe_rows = rows[: max(1, int(max_rows or 50))]
    cols = list(safe_rows[0].keys())

    header = "| " + " | ".join(cols) + " |"
    sep = "| " + " | ".join(["---"] * len(cols)) + " |"
    body = []
    for r in safe_rows:
        body.append("| " + " | ".join(esg_escape_md(r.get(c, "")) for c in cols) + " |")

    return "\n".join([header, sep] + body)


def esg_render_table(rows: List[Dict[str, Any]], max_rows: int = 50) -> None:
    st.markdown(esg_to_md_table(rows, max_rows=max_rows))


def esg_notice_httpx() -> None:
    if not _HTTPX_OK:
        st.error("httpx가 설치되어 있지 않습니다. `pip install httpx` 후 다시 실행하세요.")
        st.stop()


def esg_parse_vendors_json(raw: str) -> Tuple[List[Dict[str, str]], Optional[str]]:
    if not (raw or "").strip():
        return [], "vendors JSON이 비어있습니다."

    try:
        obj = json.loads(raw)
    except Exception as e:
        return [], f"vendors JSON 파싱 실패: {e}"

    if not isinstance(obj, list):
        return [], "vendors JSON은 리스트([]) 형태여야 합니다."

    out: List[Dict[str, str]] = []
    for v in obj:
        if not isinstance(v, dict):
            continue
        name = (v.get("name") or "").strip()
        if not name:
            continue
        out.append(
            {
                "name": name,
                "biz_no": (v.get("biz_no") or "").strip(),
                "vendor_id": (v.get("vendor_id") or "").strip(),
            }
        )

    if not out:
        return [], "vendors JSON에서 유효한 협력사(name 필수)를 찾지 못했습니다."

    return out, None


def esg_build_batch_detect_payload(
    vendors: List[Dict[str, str]],
    rag_enabled: bool,
) -> Dict[str, Any]:
    names = [v.get("name", "").strip() for v in vendors if (v.get("name") or "").strip()]
    return {
        "vendors": names,
        "rag": {"enabled": bool(rag_enabled)},
    }


def esg_build_preview_payload(
    vendor_name: str,
    rag_enabled: bool,
) -> Dict[str, Any]:
    return {
        "vendor": vendor_name,
        "rag": {"enabled": bool(rag_enabled)},
    }


def esg_httpx_post_json(client: HttpxClient, url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    r = client.post(url, json=payload)
    r.raise_for_status()
    return r.json()


def esg_call_detect_batch(api_base: str, payload: Dict[str, Any], timeout_s: float = 60.0) -> Dict[str, Any]:
    esg_notice_httpx()
    url = api_base.rstrip("/") + "/risk/external/detect"
    t = httpx.Timeout(timeout_s, connect=5.0, read=timeout_s)
    with httpx.Client(timeout=t, follow_redirects=True) as client:
        return esg_httpx_post_json(client, url, payload)


def esg_call_search_preview(api_base: str, payload: Dict[str, Any], timeout_s: float = 20.0) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    esg_notice_httpx()
    url = api_base.rstrip("/") + "/risk/external/search/preview"
    t = httpx.Timeout(timeout_s, connect=5.0, read=timeout_s)
    try:
        with httpx.Client(timeout=t, follow_redirects=True) as client:
            return esg_httpx_post_json(client, url, payload), None
    except Exception as e:
        msg = str(e)
        if "404" in msg or "Not Found" in msg:
            return None, "search preview 엔드포인트가 서버에 없습니다."
        return None, f"search preview 호출 실패: {e}"


def esg_level_rank(level: str) -> int:
    if level == "HIGH":
        return 2
    if level == "MEDIUM":
        return 1
    return 0


def esg_sort_key(row: Dict[str, Any]) -> Tuple[int, float]:
    return (esg_level_rank(str(row.get("external_risk_level", "LOW"))), float(row.get("total_score", 0) or 0))


def esg_reason_3lines_from_vendor_result(vr: Dict[str, Any]) -> str:
    lines = vr.get("reason_3lines") or []
    if not isinstance(lines, list) or not lines:
        return "사유 없음"
    return "\n".join([f"- {str(x)}" for x in lines[:3]])


def esg_render_vendor_detail(vr: Dict[str, Any]) -> None:
    st.subheader("협력사 상세(참고용)")

    st.markdown("**vendor**")
    st.write(vr.get("vendor"))

    st.markdown("**external_risk_level / total_score / docs_count**")
    st.json(
        {
            "external_risk_level": vr.get("external_risk_level"),
            "total_score": vr.get("total_score"),
            "docs_count": vr.get("docs_count"),
        }
    )

    st.markdown("### reason_1line")
    st.write(vr.get("reason_1line") or "요약 없음")

    st.markdown("### reason_3lines")
    st.text(esg_reason_3lines_from_vendor_result(vr))

    evs = vr.get("evidence") or []
    if not evs:
        st.info("표시할 evidence가 없습니다.")
        return

    st.markdown("### evidence (top 10)")
    rows: List[Dict[str, Any]] = []
    for d in evs[:10]:
        if not isinstance(d, dict):
            continue
        rows.append(
            {
                "title": d.get("title", ""),
                "source": d.get("source", ""),
                "published_at": d.get("published_at", ""),
                "url": d.get("url", ""),
            }
        )
    esg_render_table(rows, max_rows=10)


def esg_render_preview_docs(preview: Dict[str, Any], vendor_name: str) -> None:
    st.markdown(f"### 검색 미리보기(문서 확인) - {vendor_name}")
    docs = preview.get("documents")
    if not isinstance(docs, list) or not docs:
        st.info("preview에 documents가 없습니다.")
        st.json(preview)
        return

    rows: List[Dict[str, Any]] = []
    for d in docs[:20]:
        if not isinstance(d, dict):
            continue
        rows.append(
            {
                "title": d.get("title", ""),
                "source": d.get("source", ""),
                "published_at": d.get("published_at", ""),
                "url": d.get("url", ""),
            }
        )
    esg_render_table(rows, max_rows=20)


def esg_render() -> None:
    st.title("ESG 외부 이슈 모니터링(참고용)")
    st.caption("협력사 외부 이슈 신호를 참고용으로 요약/정렬해 보여줍니다. (메인 판정 변경 없음)")

    with st.sidebar:
        st.header("실행 설정")

        api_base = st.text_input("API Base URL", value="http://localhost:8002")
        st.divider()
        st.header("RAG (Chroma)")
        rag_enabled = st.toggle("rag.enabled", value=False)

        st.divider()
        st.header("협력사 목록(vendors)")
        example_vendors = [
            {"name": "포스코홀딩스", "biz_no": "", "vendor_id": ""},
            {"name": "현대제철", "biz_no": "", "vendor_id": ""},
            {"name": "성광벤드", "biz_no": "", "vendor_id": ""},
            {"name": "동국제강", "biz_no": "", "vendor_id": ""},
            {"name": "HD현대일렉트릭", "biz_no": "", "vendor_id": ""},
        ]
        vendors_raw = st.text_area(
            "vendors JSON (리스트)",
            value=json.dumps(example_vendors, ensure_ascii=False, indent=2),
            height=220,
        )

        vendors, v_err = esg_parse_vendors_json(vendors_raw)
        if v_err:
            st.error(v_err)

        st.divider()
        st.header("실행 버튼")
        run_preview_first = st.toggle("먼저 search preview로 문서 확인", value=False)
        run_all = st.button("외부 이슈 감지 실행", type="primary", disabled=bool(v_err))

    left, right = st.columns([1.25, 1.0])

    if "esg_results" not in st.session_state:
        st.session_state["esg_results"] = []
    if "esg_previews" not in st.session_state:
        st.session_state["esg_previews"] = {}

    if run_all:
        esg_notice_httpx()

        previews: Dict[str, Any] = {}
        if run_preview_first:
            with st.spinner("search preview 실행 중..."):
                for v in vendors:
                    name = (v.get("name") or "").strip()
                    if not name:
                        continue
                    pv_payload = esg_build_preview_payload(name, rag_enabled=bool(rag_enabled))
                    pv, pv_err = esg_call_search_preview(api_base, pv_payload, timeout_s=20.0)
                    if pv is not None:
                        previews[name] = pv
                    elif pv_err:
                        previews[name] = {"_error": pv_err}

        with st.spinner("협력사 외부 이슈 감지 실행 중..."):
            payload = esg_build_batch_detect_payload(vendors, rag_enabled=bool(rag_enabled))
            try:
                data = esg_call_detect_batch(api_base, payload, timeout_s=60.0)
                raw_results = data.get("results") or []
                if not isinstance(raw_results, list):
                    raw_results = []
                st.session_state["esg_results"] = sorted(raw_results, key=esg_sort_key, reverse=True)
                st.session_state["esg_previews"] = previews
            except Exception as e:
                st.error(f"detect 호출 실패: {e}")

    results_view: List[Dict[str, Any]] = st.session_state.get("esg_results", [])
    previews_view: Dict[str, Any] = st.session_state.get("esg_previews", {})

    with left:
        st.subheader("협력사 외부 이슈 리스트(참고용)")
        st.caption("정렬: 위험도(HIGH>MEDIUM>LOW) → total_score 내림차순 / 사유는 최대 3줄 요약")

        if not results_view:
            st.info("좌측에서 '외부 이슈 감지 실행'을 누르면 결과가 표시됩니다.")
        else:
            table_rows: List[Dict[str, Any]] = []
            for r in results_view:
                table_rows.append(
                    {
                        "협력사": r.get("vendor"),
                        "외부위험도": r.get("external_risk_level"),
                        "점수": r.get("total_score"),
                        "docs_count": r.get("docs_count"),
                        "사유(1줄)": r.get("reason_1line") or "",
                        "사유(3줄)": esg_reason_3lines_from_vendor_result(r),
                    }
                )
            esg_render_table(table_rows, max_rows=50)

            vendor_names = [r.get("vendor") for r in results_view if r.get("vendor")]
            selected = st.selectbox("우측 상세로 볼 협력사 선택", options=vendor_names, index=0)

    with right:
        if results_view:
            picked = None
            for r in results_view:
                if r.get("vendor") == selected:
                    picked = r
                    break

            if not picked:
                st.info("선택한 협력사의 상세 데이터가 없습니다.")
                return

            top = st.columns(3)
            top[0].metric("협력사", picked.get("vendor"))
            top[1].metric("external_risk_level", picked.get("external_risk_level", ""))
            top[2].metric("total_score", picked.get("total_score", 0))

            st.markdown("### 사유(1줄)")
            st.write(picked.get("reason_1line") or "요약 없음")

            st.markdown("### 사유(3줄)")
            st.text(esg_reason_3lines_from_vendor_result(picked))

            pv = previews_view.get(selected)
            if isinstance(pv, dict):
                st.divider()
                if pv.get("_error"):
                    st.warning(str(pv.get("_error")))
                else:
                    esg_render_preview_docs(pv, vendor_name=selected)

            st.divider()
            esg_render_vendor_detail(picked)


def esg_main() -> None:
    esg_setup_page()
    esg_render()


if __name__ == "__main__":
    esg_main()
