import os
import sys
import logging
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# [추가] 환경 변수 로드 로직: 현재 파일 위치 기준 상위 3단계(AI/)의 .env 로드
# AI / apps / out_risk_api / main.py -> AI / .env
current_file = Path(__file__).resolve()
env_path = current_file.parent.parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

# 앱 모듈 경로 보강
sys.path.append(os.path.dirname(__file__))

from app.api.risk import router as risk_router

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("out_risk.main")

def esg_create_app() -> FastAPI:
    app = FastAPI(
        title="out_risk_api", 
        version="0.1.0",
        description="ESG 외부 리스크 모니터링 API (Senior Analyst 수정보완판)"
    )

    # CORS 설정
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3000", "http://127.0.0.1:3000",
            "http://localhost:5173", "http://127.0.0.1:5173",
            "http://localhost:8501", "http://127.0.0.1:8501",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(risk_router, tags=["risk"])

    @app.get("/health")
    def esg_health() -> dict:
        # .env 로드 여부 체크 (디버깅용)
        api_key_loaded = bool(os.getenv("OPENAI_API_KEY"))
        return {
            "ok": True, 
            "service": "out_risk_api", 
            "env_loaded": api_key_loaded,
            "env_path": str(env_path)
        }

    return app

app = esg_create_app()