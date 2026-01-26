import os
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List

# 내부 모듈 임포트
from app.db.database import get_db
from app.models.audit import AuditLog
from app.core.config import settings

# ✅ 에러 나는 langchain.chains/memory를 제외하고, 정상 작동하는 것만 사용
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_core.messages import HumanMessage, SystemMessage # 추가

router = APIRouter()

# --- [초기 설정] ---
DB_PATH = "vector_db/"
embeddings = OpenAIEmbeddings(model="text-embedding-3-small", openai_api_key=settings.OPENAI_API_KEY)
vectorstore = Chroma(persist_directory=DB_PATH, embedding_function=embeddings)
retriever = vectorstore.as_retriever(search_kwargs={"k": 3})

llm = ChatOpenAI(model_name="gpt-4o", temperature=0, openai_api_key=settings.OPENAI_API_KEY)

# 단순 질문 기록 저장용 (에러 방지용 임시 메모리)
sessions_history = {}

class ChatRequest(BaseModel):
    audit_id: int
    message: str

@router.post("/")
async def chat_with_law_expert(request: ChatRequest, db: Session = Depends(get_db)):
    log = db.query(AuditLog).filter(AuditLog.id == request.audit_id).first()
    if not log:
        raise HTTPException(status_code=404, detail="이력을 찾을 수 없습니다.")

    # 1. 수동으로 관련 법령 검색 (Chain 없이 직접 수행)
    relevant_docs = retriever.invoke(request.message)
    context_docs = "\n".join([doc.page_content for doc in relevant_docs])

    # 2. 프롬프트 구성
    system_prompt = (
        f"당신은 하도급법 전문 변호사입니다. 아래 [참고 법령]과 [계약서 분석 결과]를 바탕으로 답변하세요.\n\n"
        f"[참고 법령]\n{context_docs}\n\n"
        f"[계약서 정보]\n- 파일명: {log.filename}\n- 분석 요약: {log.summary}\n- 리스크: {log.feedback_text}"
    )
    
    # 3. LLM 실행 (직접 호출)
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=request.message)
    ]
    response = llm.invoke(messages)

    # 4. 소스 정리
    sources = list(set([doc.metadata.get('source', '알 수 없는 출처') for doc in relevant_docs]))

    return {
        "answer": response.content,
        "referenced_laws": sources,
        "chat_history_count": 0  # 임시 고정
    }