#AI/apps/out_risk_api/main.py

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

class UTF8JSONResponse(JSONResponse):
    media_type = "application/json; charset=utf-8"

    def render(self, content: object) -> bytes:
        return json.dumps(content, ensure_ascii=False, allow_nan=False).encode("utf-8")


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
    def esg_health() -> dict:
        # Importing app_config triggers .env load there
        api_key_loaded = bool(app_config.OPENAI_API_KEY)
        return {
            "ok": True,
            "service": "out_risk_api",
            "env_loaded": api_key_loaded,
            "env_path": "app.core.config",
        }

    return app


app = esg_create_app()
