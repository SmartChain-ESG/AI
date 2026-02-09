#AI/apps/out_risk_api/app/main.py

import os
import sys
import json
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

sys.path.append(os.path.dirname(__file__))

from app.api.risk import router as risk_router
from app.core import config as app_config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("out_risk.main")

# 20260203 이종헌 수정: UTF-8 고정 JSON 응답 클래스(한글 깨짐 방지)
class UTF8JSONResponse(JSONResponse):
    media_type = "application/json; charset=utf-8"

    def render(self, content: object) -> bytes:
        return json.dumps(content, ensure_ascii=False, allow_nan=False).encode("utf-8")


# 20260203 이종헌 수정: health/env 확인 기준을 app.core.config로 통일해 실행 위치 의존성 완화
def esg_create_app() -> FastAPI:
    app = FastAPI(
        title="out_risk_api",
        version="0.1.0",
        description="ESG risk monitoring API (Senior Analyst revision)",
        default_response_class=UTF8JSONResponse,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:8501",
            "http://127.0.0.1:8501",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(risk_router, tags=["risk"])

    @app.get("/health")
    # 20260203 이종헌 수정: OPENAI_API_KEY 로드 상태를 헬스체크로 직접 노출
    def esg_health() -> dict:
        api_key_loaded = bool(app_config.OPENAI_API_KEY)
        return {
            "ok": True,
            "service": "out_risk_api",
            "env_loaded": api_key_loaded,
            "env_path": "app.core.config",
        }

    return app


app = esg_create_app()
