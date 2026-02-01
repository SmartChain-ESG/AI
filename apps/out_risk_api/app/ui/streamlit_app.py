# AI/apps/out_risk_api/app/ui/streamlit_app.py

# 20260131 이종헌 수정: ESG 탭(협력사 외부 이슈 모니터링) Streamlit - 다수 협력사 일괄 감지 + 정렬 + 사유 3줄 요약
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Tuple

import streamlit as st

try:
    import httpx
    _HTTPX_OK = True
except Exception:
    httpx = None
    _HTTPX_OK = False


# 역할: Streamlit 페이지 기본 설정을 적용함
def esg_setup_page() -> None:
    st.set_page_config(
        page_title="ESG 외부 이슈 모니터링(참고용)",
        layout="wide",
    )

# 수정: dict 리스트를 markdown 표로 변환(=pyarrow 완전 미사용)
def esg_to_md_table(rows: list[dict], max_rows: int = 50) -> str:
    if not rows:
        return "표시할 데이터가 없습니다."

    safe_rows = rows[:max_rows]
    cols = list(safe_rows[0].keys())

    def esc(v: object) -> str:
        s = "" if v is None else str(v)
        return s.replace("|", "\\|").replace("\n", " ")

    header = "| " + " | ".join(cols) + " |"
    sep = "| " + " | ".join(["---"] * len(cols)) + " |"
    body = ["| " + " | ".join(esc(r.get(c, "")) for c in cols) + " |" for r in safe_rows]
    return "\n".join([header, sep] + body)


# 수정: pyarrow 설치/로딩 상태에 따라 표 렌더링을 자동으로 전환(에러 방지)
# 수정: pyarrow 설치/로딩 상태에 따라 표 렌더링을 자동으로 전환(에러 방지)
def esg_render_table(rows: list[dict], max_rows: int = 50) -> None:
    safe_rows = (rows or [])[: max(1, int(max_rows or 50))]

    if not safe_rows:
        st.info("표시할 데이터가 없습니다.")
        return

    try:
        import pyarrow  # noqa: F401  # 수정: pyarrow 로딩 가능 여부만 확인
        import pandas as pd  # 수정: dataframe 렌더링을 위해 사용

        df = pd.DataFrame(safe_rows)
        st.dataframe(df, use_container_width=True, height=420)  # 수정: pyarrow 가능할 때만 dataframe
        return
    except Exception:
        st.markdown(esg_to_md_table(safe_rows, max_rows=max_rows), unsafe_allow_html=False)  # 수정: fallback



# 수정: pyarrow 없이도 테이블을 보여주기 위한 markdown table 변환기
def esg_to_md_table(rows: list[dict], max_rows: int = 50) -> str:
    if not rows:
        return "표시할 데이터가 없습니다."

    safe_rows = rows[:max_rows]
    columns = list(safe_rows[0].keys())

    def esc(v: object) -> str:
        s = "" if v is None else str(v)
        s = s.replace("|", "\\|").replace("\n", " ")
        return s

    header = "| " + " | ".join(columns) + " |"
    sep = "| " + " | ".join(["---"] * len(columns)) + " |"
    body = ["| " + " | ".join(esc(r.get(c, "")) for c in columns) + " |" for r in safe_rows]
    return "\n".join([header, sep] + body)



# 역할: 협력사 목록 JSON을 파싱해 [{name,biz_no,vendor_id}]로 정규화함
def esg_parse_vendors_json(raw: str) -> Tuple[List[Dict[str, str]], Optional[str]]:
    if not (raw or "").strip():
        return [], "vendors JSON이 비어있습니다."
    try:
        obj = json.loads(raw)
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
    except Exception as e:
        return [], f"vendors JSON 파싱 실패: {e}"


# 역할: 단일 협력사용 ExternalRiskDetectRequest payload를 생성함(명세 스키마 유지)
def esg_build_payload_for_vendor(
    vendor: Dict[str, str],
    time_window_days: int,
    categories: List[str],
    search_enabled: bool,
    search_query: str,
    max_results: int,
    sources: List[str],
    lang: str,
    rag_enabled: bool,
    top_k: int,
    chunk_size: int,
    strict_grounding: bool,
    return_evidence_text: bool,
) -> Dict[str, Any]:
    return {
        "company": {
            "name": vendor.get("name", ""),
            "biz_no": vendor.get("biz_no") or None,
            "vendor_id": vendor.get("vendor_id") or None,
        },
        "time_window_days": int(time_window_days),
        "categories": categories,
        "search": {
            "enabled": bool(search_enabled),
            "query": search_query or "",
            "max_results": int(max_results),
            "sources": sources,
            "lang": lang or "ko",
        },
        "documents": [],  # ESG 탭 모니터링은 기본적으로 검색 기반(참고용)
        "rag": {
            "enabled": bool(rag_enabled),
            "top_k": int(top_k),
            "chunk_size": int(chunk_size),
        },
        "options": {
            "strict_grounding": bool(strict_grounding),
            "return_evidence_text": bool(return_evidence_text),
        },
    }


# 역할: FastAPI 서버로 /risk/external/detect를 호출해 응답 JSON을 받음
def esg_call_api_detect(api_base: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    if not _HTTPX_OK:
        raise RuntimeError("httpx가 설치되어 있지 않습니다. pip install httpx 로 설치하세요.")
    url = api_base.rstrip("/") + "/risk/external/detect"
    with httpx.Client(timeout=30.0) as client:
        r = client.post(url, json=payload)
        r.raise_for_status()
        return r.json()


# 역할: signals에서 상위 3개만 뽑아 '사유 3줄 요약' 문자열을 만듦
def esg_reason_3lines(resp: Dict[str, Any]) -> str:
    sigs = resp.get("signals") or []
    if not sigs:
        return "외부 이슈 신호 없음"

    lines: List[str] = []
    for s in sigs[:3]:
        cat = s.get("category", "")
        summ = (s.get("summary_ko") or "").strip()
        if not summ:
            summ = (s.get("why") or "").strip()
        if len(summ) > 80:
            summ = summ[:80] + "…"
        lines.append(f"- {cat}: {summ}")

    return "\n".join(lines)


# 역할: 리스트 화면 정렬 키를 만들어 반환함(레벨 우선, 점수 다음)
def esg_sort_key(row: Dict[str, Any]) -> Tuple[int, float]:
    level = row.get("external_risk_level", "LOW")
    score = float(row.get("total_score", 0) or 0)
    # HIGH > MEDIUM > LOW
    level_rank = 2 if level == "HIGH" else 1 if level == "MEDIUM" else 0
    return (level_rank, score)


# 역할: 우측 상세 패널에 특정 협력사의 signals를 보여줌
def esg_render_vendor_detail(resp: Dict[str, Any]) -> None:
    st.subheader("협력사 상세(참고용)")
    st.write("disclaimer", resp.get("disclaimer", ""))
    st.markdown("**retrieval_meta**")
    st.json(resp.get("retrieval_meta") or {})

    sigs = resp.get("signals") or []
    if not sigs:
        st.info("표시할 signals가 없습니다.")
        return

    st.markdown("### Top signals")
    for i, s in enumerate(sigs[:10]):
        title = s.get("title") or "(no title)"
        score = s.get("score")
        cat = s.get("category")
        with st.expander(f"[{i+1}] {cat} | score={score} | {title}"):
            st.write("summary_ko", s.get("summary_ko"))
            st.write("why", s.get("why"))
            st.write("published_at", s.get("published_at"))
            st.write("tags", s.get("tags"))
            st.write("is_estimated", s.get("is_estimated"))

            evs = s.get("evidence") or []
            if evs:
                st.markdown("**evidence**")
                for ev in evs:
                    st.write(
                        {
                            "doc_id": ev.get("doc_id"),
                            "source": ev.get("source"),
                            "url": ev.get("url"),
                            "offset": ev.get("offset"),
                        }
                    )
                    st.code(ev.get("quote") or "", language="text")


# 역할: Streamlit 메인 화면을 구성하고, 일괄 실행/정렬/표시를 처리함
def esg_render() -> None:
    st.title("ESG 외부 이슈 모니터링(참고용)")
    st.caption("내가 관리하는 협력사들의 외부 이슈 신호를 참고용으로 요약/정렬해 보여줍니다. (메인 판정 변경 없음)")

    with st.sidebar:
        st.header("실행 설정")

        api_base = st.text_input("API Base URL", value="http://localhost:8000")
        time_window_days = st.number_input("time_window_days", min_value=1, max_value=3650, value=90, step=1)

        st.divider()
        st.header("카테고리(ESG 외부 위험 신호)")
        category_all = [
            "SAFETY_ACCIDENT",
            "LEGAL_SANCTION",
            "LABOR_DISPUTE",
            "ENV_COMPLAINT",
            "FINANCE_LITIGATION",
        ]
        categories = st.multiselect("categories", options=category_all, default=category_all)

        st.divider()
        st.header("SEARCH")
        search_enabled = st.toggle("search.enabled", value=True)
        search_query = st.text_input("search.query (비우면 회사명 사용)", value="")
        max_results = st.number_input("search.max_results", min_value=1, max_value=100, value=20, step=1)
        sources_all = ["news", "gov", "court", "public_db"]
        sources = st.multiselect("search.sources", options=sources_all, default=["news"])
        lang = st.selectbox("search.lang", options=["ko", "en"], index=0)

        st.divider()
        st.header("RAG (Chroma)")
        rag_enabled = st.toggle("rag.enabled", value=True)
        top_k = st.number_input("rag.top_k", min_value=1, max_value=50, value=6, step=1)
        chunk_size = st.number_input("rag.chunk_size", min_value=200, max_value=4000, value=800, step=50)

        st.divider()
        st.header("OPTIONS")
        strict_grounding = st.toggle("options.strict_grounding", value=True)
        return_evidence_text = st.toggle("options.return_evidence_text", value=True)

        st.divider()
        st.header("협력사 목록(vendors)")
        example_vendors = [
            {"name": "성광벤드", "biz_no": "", "vendor_id": ""},
            {"name": "협력사A", "biz_no": "", "vendor_id": ""},
            {"name": "협력사B", "biz_no": "", "vendor_id": ""},
        ]
        vendors_raw = st.text_area(
            "vendors JSON (리스트)",
            value=json.dumps(example_vendors, ensure_ascii=False, indent=2),
            height=220,
        )

        vendors, v_err = esg_parse_vendors_json(vendors_raw)
        if v_err:
            st.error(v_err)

        run_all = st.button("일괄 감지 실행", type="primary", disabled=bool(v_err))

    left, right = st.columns([1.2, 1.0])

    if "esg_results" not in st.session_state:
        st.session_state["esg_results"] = []  # type: ignore

    if run_all:
        results: List[Dict[str, Any]] = []
        errors: List[str] = []

        with st.spinner("협력사 외부 이슈 감지 실행 중..."):
            for v in vendors:
                try:
                    payload = esg_build_payload_for_vendor(
                        vendor=v,
                        time_window_days=int(time_window_days),
                        categories=categories or category_all,
                        search_enabled=bool(search_enabled),
                        search_query=search_query.strip(),
                        max_results=int(max_results),
                        sources=sources or ["news"],
                        lang=lang,
                        rag_enabled=bool(rag_enabled),
                        top_k=int(top_k),
                        chunk_size=int(chunk_size),
                        strict_grounding=bool(strict_grounding),
                        return_evidence_text=bool(return_evidence_text),
                    )
                    resp = esg_call_api_detect(api_base, payload)

                    row = {
                        "vendor_name": v.get("name"),
                        "external_risk_level": resp.get("external_risk_level"),
                        "total_score": float(resp.get("total_score", 0) or 0),
                        "reason_3lines": esg_reason_3lines(resp),
                        "_raw": resp,
                    }
                    results.append(row)
                except Exception as e:
                    errors.append(f"{v.get('name')}: {e}")

        # 정렬: 레벨(HIGH>MED>LOW) → 점수 내림차순
        results_sorted = sorted(results, key=esg_sort_key, reverse=True)
        st.session_state["esg_results"] = results_sorted  # type: ignore

        if errors:
            with left:
                st.warning("일부 협력사 실행 실패")
                for msg in errors:
                    st.write(msg)

    results_view: List[Dict[str, Any]] = st.session_state.get("esg_results", [])  # type: ignore

    with left:
        st.subheader("협력사 외부 이슈 리스트(참고용)")
        st.caption("정렬: 위험도(HIGH>MEDIUM>LOW) → total_score 내림차순 / 사유는 최대 3줄 요약")

        if not results_view:
            st.info("좌측에서 '일괄 감지 실행'을 누르면 결과가 표시됩니다.")
        else:
            table_rows = [
                {
                    "협력사": r.get("vendor_name"),
                    "외부위험도": r.get("external_risk_level"),
                    "점수": r.get("total_score"),
                    "사유(3줄)": r.get("reason_3lines"),
                }
                for r in results_view
            ]
            esg_render_table(table_rows)

            vendor_names = [r.get("vendor_name") for r in results_view]
            selected = st.selectbox("우측 상세로 볼 협력사 선택", options=vendor_names, index=0)

    with right:
        if results_view:
            picked = None
            for r in results_view:
                if r.get("vendor_name") == selected:
                    picked = r
                    break

            if picked and picked.get("_raw"):
                raw = picked["_raw"]
                top = st.columns(3)
                top[0].metric("협력사", picked.get("vendor_name"))
                top[1].metric("external_risk_level", raw.get("external_risk_level", ""))
                top[2].metric("total_score", raw.get("total_score", 0))
                st.markdown("### 사유(3줄)")
                st.text(picked.get("reason_3lines") or "")
                st.divider()
                esg_render_vendor_detail(raw)
            else:
                st.info("선택된 협력사의 상세 데이터를 찾지 못했습니다.")


# 역할: Streamlit 엔트리 함수로 페이지 설정 후 화면을 렌더링함
def esg_main() -> None:
    esg_setup_page()
    esg_render()


if __name__ == "__main__":
    esg_main()
