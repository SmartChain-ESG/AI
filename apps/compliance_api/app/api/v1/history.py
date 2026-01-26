# app/api/v1/history.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime
from pydantic import BaseModel
from app.db.database import get_db
from app.models.audit import AuditLog

router = APIRouter()

# --- 1. 응답을 위한 Pydantic 모델 정의 ---
class HistorySchema(BaseModel):
    id: int
    filename: str
    risk_score: int
    summary: str
    feedback_text: str
    created_at: datetime

    class Config:
        from_attributes = True  # SQLAlchemy 객체를 자동으로 읽어오게 하는 설정

# --- 2. 라우터 수정 ---
@router.get("/", response_model=List[HistorySchema])
async def get_audit_history(db: Session = Depends(get_db)):
    """최근 검토 이력 목록 가져오기"""
    # DB에서 데이터를 가져옵니다.
    logs = db.query(AuditLog).order_by(AuditLog.created_at.desc()).all()
    return logs

@router.get("/{audit_id}", response_model=HistorySchema)
async def get_audit_detail(audit_id: int, db: Session = Depends(get_db)):
    """특정 검토 내역 상세 조회"""
    log = db.query(AuditLog).filter(AuditLog.id == audit_id).first()
    if not log:
        raise HTTPException(status_code=404, detail="해당 이력을 찾을 수 없습니다.")
    return log