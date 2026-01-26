# app/main.py
from fastapi.staticfiles import StaticFiles
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1.review import router as review_router
from app.core.config import settings
from app.db.database import engine, Base
from app.models import audit
from app.api.v1 import review, history, chat

# 서버 시작 시 DB 테이블 생성
Base.metadata.create_all(bind=engine)

app = FastAPI(title=settings.APP_NAME, version="1.0.0")

# CORS 설정: 프론트엔드 연동용
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API 라우터 등록
app.include_router(review_router, prefix="/api/v1/review", tags=["Compliance Review"])

# 이력 조회 API
app.include_router(history.router, prefix="/api/v1/history", tags=["History"])

# 챗봇 라우터 등록!
app.include_router(chat.router, prefix="/api/v1/chat", tags=["Chat"])

# 업로드 폴더가 없으면 생성
if not os.path.exists("uploads"):
    os.makedirs("uploads")

# /uploads 경로로 들어오면 실제 uploads 폴더의 파일을 보여줌
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

@app.get("/health")
def health_check():
    return {"status": "healthy", "environment": settings.ENVIRONMENT}