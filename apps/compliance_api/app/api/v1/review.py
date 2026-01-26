# app/api/v1/review.py
from fastapi import APIRouter, UploadFile, File, Depends
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.models.audit import AuditLog
from app.services.pipeline import run_compliance_pipeline
from app.models.response import ComplianceResult
import shutil
import os

router = APIRouter()

# 파일을 저장할 디렉토리 설정
UPLOAD_DIR = "uploads"
if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)

@router.post("/upload", response_model=ComplianceResult)
async def upload_document(file: UploadFile = File(...), db: Session = Depends(get_db)):
    # 1. 파일을 로컬 uploads 폴더에 저장
    # 파일명이 중복될 경우를 대비해 나중에는 타임스탬프를 붙이는 게 좋지만, 일단 원본 이름으로 저장합니다.
    file_path = os.path.join(UPLOAD_DIR, file.filename)
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    # 중요: 파일을 저장하면서 커서가 끝으로 갔으므로, 다시 처음으로 돌려줘야 분석 엔진이 읽을 수 있습니다.
    await file.seek(0)

    # 2. 기존 분석 파이프라인 실행
    result = await run_compliance_pipeline(file)
    
    # 3. 분석 결과를 DB에 기록 (파일 이름을 함께 저장)
    db_log = AuditLog(
        filename=file.filename, # 실제 저장된 파일명
        risk_score=result.risk_score,
        summary=result.summary,
        feedback_text=result.feedback_text
    )
    db.add(db_log)
    db.commit()
    db.refresh(db_log)
    
    return result