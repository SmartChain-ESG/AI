# chatbot_api - 컴플라이언스 Q&A 챗봇 [서브]

사내 컴플라이언스 규정 문서를 벡터DB(ChromaDB)에 저장하고,
RAG(Retrieval-Augmented Generation) 기반으로 질문에 답변하는 챗봇입니다.

## 엔드포인트

| Method | Path | 설명 |
|--------|------|------|
| `GET` | `/health` | 서버 상태 확인 |
| `POST` | `/chat` | 사용자 질문 → RAG 기반 답변 |
| `POST` | `/admin/upload` | 규정 문서 업로드 (관리자용, API Key 필요) |

## 실행 방법

```bash
# 서버 실행 (포트 8001)
uvicorn app.main:app --reload --port 8001 --app-dir apps/chatbot_api

# Streamlit UI
streamlit run apps/chatbot_api/app/ui/streamlit_app.py
```

## 디렉토리 구조

```
app/
├── main.py                 # FastAPI 진입점
├── api/
│   ├── chat.py             # 채팅 엔드포인트
│   └── admin.py            # 관리자 문서 업로드
├── rag/                    # ChromaDB + RAG 로직
├── core/
│   └── config.py           # pydantic-settings 기반 설정
├── ui/
│   └── streamlit_app.py    # 테스트 UI
└── vectordb/               # ChromaDB 저장 경로 (gitignore)
```

## 환경변수

| 변수명 | 설명 |
|--------|------|
| `OPENAI_API_KEY` | OpenAI API 키 |
| `OPENAI_EMBEDDING_MODEL` | 임베딩 모델 (기본: text-embedding-3-small) |
| `CHATBOT_CHROMA_PATH` | ChromaDB 저장 경로 (기본: apps/chatbot_api/app/vectordb) |
| `CHATBOT_CHROMA_COLLECTION` | ChromaDB 컬렉션명 (기본: hd_hhi_compliance_kb) |
| `ADMIN_API_KEY` | 관리자 API 키 (문서 업로드용) |
