# app/api/v1/chat.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.db.database import get_db
from app.models.audit import AuditLog
from openai import AsyncOpenAI
from app.core.config import settings

router = APIRouter()
client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

# 채팅 요청 데이터 모델
class ChatRequest(BaseModel):
    audit_id: int  # 어느 문서에 대해 대화할 것인가?
    message: str   # 사용자 질문

@router.post("/")
async def chat_with_document(request: ChatRequest, db: Session = Depends(get_db)):
    # 1. 문맥 추출: DB에서 과거 분석 결과 조회
    log = db.query(AuditLog).filter(AuditLog.id == request.audit_id).first()
    if not log:
        raise HTTPException(status_code=404, detail="해당 분석 이력을 찾을 수 없습니다.")

    # 2. 문맥 구성(Context Construction): AI의 '단기 기억' 설계
    # 분석 결과를 바탕으로 AI에게 페르소나와 배경지식을 주입합니다.
    context_prompt = f"""
    당신은 하도급법 전문 변호사이며, 방금 다음 계약서를 검토했습니다:
    - 파일명: {log.filename}
    - 리스크 점수: {log.risk_score}점
    - 분석 요약: {log.summary}
    - 생성된 피드백: {log.feedback_text}
    
    사용자의 질문에 대해 위 분석 내용을 바탕으로 전문적이고 구체적으로 답변하세요.
    분석 결과에 없는 내용을 지어내지 말고, 근거가 필요하다면 '분석 결과에 따르면'이라고 명시하세요.
    """

    # 3. AI 호출 (문맥 + 사용자 질문)
    response = await client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": context_prompt},
            {"role": "user", "content": request.message}
        ]
    )

    return {"answer": response.choices[0].message.content}