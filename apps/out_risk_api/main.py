# AI/apps/out_risk_api/main.py

# 20260131 이종헌 신규: FastAPI 엔트리포인트(라우터 등록 + 헬스체크)
from fastapi import FastAPI
from app.api.risk import router as risk_router


def esg_create_app() -> FastAPI:
    app = FastAPI(title="out_risk_api", version="1.0.0")
    app.include_router(risk_router, tags=["risk"])

    @app.get("/health")
    def esg_health() -> dict:
        return {"ok": True, "service": "out_risk_api"}

    return app


app = esg_create_app()