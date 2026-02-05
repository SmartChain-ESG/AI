import os
import requests
import streamlit as st

st.set_page_config(page_title="Compliance Chatbot", layout="centered")

API_BASE = os.getenv("CHATBOT_API_BASE", "http://127.0.0.1:8001")  # 네 챗봇 서버 포트로!
CHAT_ENDPOINT = f"{API_BASE}/api/chat"
SYNC_ENDPOINT = f"{API_BASE}/api/admin/sync"

st.title("HD HHI Compliance Advisor (Test UI)")

# 사이드바 설정
with st.sidebar:
    st.subheader("Settings")
    api_base = st.text_input("API Base URL", API_BASE)
    domain = st.selectbox("domain", ["all", "compliance", "esg", "safety"], index=0)
    top_k = st.slider("top_k", 1, 15, 5)
    file_url = st.text_input("File URL (Optional)", help="테스트할 PDF의 URL을 입력하세요 (예: S3 Presigned URL)")
    if file_url:
        st.info("📄 파일 URL이 입력되었습니다. 아래 채팅창에 질문을 입력하면 분석이 시작됩니다.")

    st.divider()
    st.subheader("Admin (Sync)")
    admin_key = st.text_input("X-API-KEY", type="password", help="ADMIN_API_KEY 값")
    if st.button("Run /api/admin/sync"):
        try:
            r = requests.post(f"{api_base}/api/admin/sync", headers={"X-API-KEY": admin_key}, timeout=300)
            st.write("status:", r.status_code)
            st.json(r.json())
        except Exception as e:
            st.error(str(e))

# 세션 히스토리
if "messages" not in st.session_state:
    st.session_state.messages = []

# 기존 대화 표시
for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

# 입력
prompt = st.chat_input("질문을 입력하세요")
if prompt:
    # 사용자 메시지
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # 이전 대화 기록 구성 (현재 질문 제외, user/assistant만)
    history = []
    for m in st.session_state.messages[:-1]:
        if m["role"] in ["user", "assistant"]:
            history.append({"role": m["role"], "content": m["content"]})

    # 서버 호출
    payload = {
        "message": prompt,
        "file_url": file_url if file_url else None,
        "session_id": "streamlit-demo",   # 필요하면 유저별로 바꿔도 됨
        "domain": domain,
        "top_k": top_k,
        "history": history,
    }

    with st.chat_message("assistant"):
        with st.spinner("생각 중..."):
            try:
                r = requests.post(f"{api_base}/api/chat", json=payload, timeout=120)
                r.raise_for_status()
                data = r.json()

                answer = data.get("answer", "")
                sources = data.get("sources", [])
                confidence = data.get("confidence", "")
                notes = data.get("notes", "")

                st.markdown(answer)

                # 근거 표시
                if sources:
                    with st.expander("Sources"):
                        for s in sources:
                            st.write(f"- **{s.get('title')}** (p.{s.get('loc', {}).get('page')}) score={s.get('score')}")
                            snippet = s.get("snippet")
                            if snippet:
                                st.code(snippet[:1000])

                if confidence or notes:
                    st.caption(f"confidence: {confidence} | notes: {notes}")

                st.session_state.messages.append({"role": "assistant", "content": answer})

            except Exception as e:
                st.error(f"API 호출 실패: {e}")