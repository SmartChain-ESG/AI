# app/frontend/dashboard.py
import streamlit as st
import requests
import json
from datetime import datetime

# FastAPI 백엔드 주소 (백엔드 서버에서 StaticFiles 설정이 되어 있어야 합니다)
BASE_URL = "http://127.0.0.1:8002/api/v1"
FILE_SERVER_URL = "http://127.0.0.1:8002/uploads" # 파일 서빙 경로

st.set_page_config(page_title="AI Compliance Dash", layout="wide", page_icon="🛡️")

# --- 커스텀 스타일 ---
st.markdown("""
    <style>
    .main { background-color: #f5f7f9; }
    .stButton>button { width: 100%; border-radius: 5px; height: 3em; }
    .stChatMessage { border-radius: 15px; }
    /* PDF 뷰어 테두리 설정 */
    iframe { border: 1px solid #ddd; border-radius: 10px; }
    </style>
    """, unsafe_allow_html=True)

st.title("🛡️ 하도급법 AI 컴플라이언스 비서")
st.caption("계약서를 업로드하고 실시간 리스크 분석 및 법률 챗봇과 대화하세요.")

# --- 사이드바: 검토 이력 ---
with st.sidebar:
    st.header("📂 검토 이력")
    if st.button("🔄 리스트 새로고침"):
        st.rerun()
    
    try:
        response = requests.get(f"{BASE_URL}/history/")
        if response.status_code == 200:
            history = response.json()
            for item in history:
                date_str = datetime.fromisoformat(item['created_at']).strftime("%m/%d %H:%M")
                label = f"📄 {item['filename']} ({date_str})"
                
                # 버튼 클릭 시 세션에 ID와 파일명 저장
                if st.button(label, key=f"hist_{item['id']}"):
                    st.session_state.selected_audit_id = item['id']
                    st.session_state.selected_filename = item['filename']
        else:
            st.error("이력을 불러오지 못했습니다.")
    except Exception as e:
        st.warning("백엔드 서버 연결을 확인하세요.")

# --- 메인 영역: 2컬럼 레이아웃 ---
col1, col2 = st.columns([1.2, 1]) # 왼쪽 미리보기 공간을 살짝 더 넓게 설정

with col1:
    # 1. 문서가 선택된 경우 -> 미리보기 표시
    if "selected_audit_id" in st.session_state:
        filename = st.session_state.selected_filename
        st.subheader(f"📄 문서 미리보기: {filename}")
        
        file_url = f"{FILE_SERVER_URL}/{filename}"
        
        # 파일 확장자에 따른 표시 방식 분기
        if filename.lower().endswith(('.png', '.jpg', '.jpeg')):
            st.image(file_url, use_container_width=True)
        elif filename.lower().endswith('.pdf'):
            # PDF를 iframe으로 출력 (Streamlit에서 가장 깔끔한 방식)
            pdf_display = f'<iframe src="{file_url}" width="100%" height="800" type="application/pdf"></iframe>'
            st.markdown(pdf_display, unsafe_allow_html=True)
        
        if st.button("❌ 미리보기 닫기 (신규 업로드)"):
            del st.session_state.selected_audit_id
            st.rerun()

    # 2. 문서가 선택되지 않은 경우 -> 신규 업로드 화면 표시
    else:
        st.subheader("📤 신규 문서 분석")
        uploaded_file = st.file_uploader("검토할 계약서 이미지/PDF 업로드", type=["png", "jpg", "jpeg", "pdf"])
        
        if st.button("🚀 즉시 분석 시작", type="primary"):
            if uploaded_file:
                with st.spinner("AI 변호사가 계약서를 정밀 분석 중입니다..."):
                    files = {"file": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)}
                    res = requests.post(f"{BASE_URL}/review/upload", files=files)
                    if res.status_code == 200:
                        data = res.json()
                        st.success(f"분석 완료! 리스크 점수: {data['risk_score']}점")
                        st.balloons()
                        st.json(data)
                        st.rerun() # 업로드 후 리스트 갱신을 위해 재실행
                    else:
                        st.error("분석 중 오류가 발생했습니다.")
            else:
                st.warning("파일을 먼저 올려주세요!")

with col2:
    st.subheader("💬 AI 법률 상담")
    
    if "selected_audit_id" in st.session_state:
        audit_id = st.session_state.selected_audit_id
        st.info(f"**대상 문서:** {st.session_state.selected_filename}")
        
        # 1. 문서가 바뀌면 채팅 내역 초기화
        if "last_audit_id" not in st.session_state or st.session_state.last_audit_id != audit_id:
            st.session_state.chat_messages = []
            st.session_state.last_audit_id = audit_id

        # 2. 상세 데이터 가져오기 (요약 표시용)
        detail = requests.get(f"{BASE_URL}/history/{audit_id}").json()
        
        # 3. 채팅 UI 구성
        chat_container = st.container(height=550)
        
        with chat_container:
            st.write(f"**[AI 분석 요약]**")
            st.write(detail['summary'])
            st.divider()
            
            # 이전 대화 내용 출력 (누적된 메시지 표시)
            for msg in st.session_state.chat_messages:
                with st.chat_message(msg["role"]):
                    st.markdown(msg["content"])
                    if "sources" in msg:
                        st.caption(f"📍 참고 법령: {', '.join(msg['sources'])}")

        # 4. 사용자 질문 입력 및 처리
        if user_input := st.chat_input("문서 내용을 보며 궁금한 점을 질문하세요..."):
            # 사용자 메시지 화면에 즉시 표시 및 저장
            st.session_state.chat_messages.append({"role": "user", "content": user_input})
            with chat_container:
                st.chat_message("user").write(user_input)
                
                with st.spinner("법률 지식 검색 및 답변 생성 중..."):
                    chat_res = requests.post(
                        f"{BASE_URL}/chat/", 
                        json={"audit_id": audit_id, "message": user_input}
                    )
                    
                    if chat_res.status_code == 200:
                        data = chat_res.json()
                        answer = data["answer"] # 백엔드 응답의 answer
                        sources = data.get("referenced_laws", []) # 백엔드 응답의 소스
                        
                        # 어시스턴트 답변 표시
                        with st.chat_message("assistant"):
                            st.markdown(answer)
                            if sources:
                                st.caption(f"📍 참고 법령: {', '.join(sources)}")
                        
                        # 대화 기록에 저장
                        st.session_state.chat_messages.append({
                            "role": "assistant", 
                            "content": answer, 
                            "sources": sources
                        })
                    else:
                        st.error("서버 응답 오류가 발생했습니다.")
    else:
        st.write("👈 왼쪽 이력에서 문서를 선택하면 대화가 시작됩니다.")