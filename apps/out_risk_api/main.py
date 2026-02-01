# AI/apps/out_risk_api/main.py

# 20260131 이종헌 수정: FastAPI 엔트리포인트 + CORS 허용 + 라우터 등록 + 헬스체크
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware  # 20260131 이종헌 수정: CORS 미들웨어 추가
from app.api.risk import router as risk_router


# 역할: FastAPI 앱을 만들고 라우터/미들웨어를 등록함
def esg_create_app() -> FastAPI:
    # 수정: Streamlit(8501)에서 API 호출 가능하도록 CORS 허용


    app = FastAPI()

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:8501",
            "http://127.0.0.1:8501",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


    # 20260131 이종헌 수정: Streamlit/로컬 프론트 테스트를 위한 CORS 허용
    # 운영 시에는 allow_origins를 구체 도메인으로 좁히는 것을 권장
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # 20260131 이종헌 수정: 테스트용 전체 허용
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(risk_router, tags=["risk"])

    @app.get("/health")
    def esg_health() -> dict:
        return {"ok": True, "service": "out_risk_api"}

    return app


app = esg_create_app()
