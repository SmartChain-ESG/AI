# app/main.py
from __future__ import annotations

import json
import logging
import os
import traceback
import uuid
from typing import Any

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import esg_get_db
from app.db import repo as db_repo
from app.graph.build import esg_build_graph
from app.utils.files import esg_save_uploads
from app.utils.diff import esg_compute_resubmit_diff

# ------------------------------------------------------------
# Logging
# ------------------------------------------------------------
logger = logging.getLogger("esg_api")
logging.basicConfig(level=logging.INFO)

# ESG_DEBUG=1 이면 500에서 traceback까지 detail로 노출(로컬 개발용)
ESG_DEBUG = os.getenv("ESG_DEBUG", "0") == "1"

# ------------------------------------------------------------
# App
# ------------------------------------------------------------
app = FastAPI(
    title="ESG AI API",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 내부 개발용(필요 시 제한)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# LangGraph (build는 모듈 import 시 1회)
graph = esg_build_graph()

# ------------------------------------------------------------
# Health
# ------------------------------------------------------------
@app.get("/healthz")
def esg_healthz():
    return {"ok": True}


# ------------------------------------------------------------
# Models (서브서비스)
# ------------------------------------------------------------
class RagLookupRequest(BaseModel):
    slot_name: str
    issue_code: str
    company_id: str | None = None
    industry: str | None = None


class RagSnippet(BaseModel):
    source: str
    excerpt: str
    page: int | None = None
    score: float | None = None


class RagLookupResponse(BaseModel):
    slot_name: str
    issue_code: str
    snippets: list[RagSnippet]
    note: str


class SupplychainPredictRequest(BaseModel):
    # ✅ 오늘 스펙(권장)
    supplier_name: str | None = None
    current_status: str | None = None
    issues: list[dict[str, Any]] = Field(default_factory=list)

    # ✅ Day4 호환(있으면 latest run에서 가져오는 방식)
    draft_id: str | None = None


class SupplychainPredictResponse(BaseModel):
    supplier_name: str | None = None
    risk_level: str
    risk_score: float
    drivers: list[str]
    recommended_monitoring: list[str]
    note: str


# ------------------------------------------------------------
# Utils (함수명 규칙: esg_*)
# ------------------------------------------------------------
def esg_safe_json_loads(s: str | None) -> Any:
    """Form으로 들어오는 JSON string을 안전하게 dict/list로 변환"""
    if not s:
        return None
    try:
        return json.loads(s)
    except Exception:
        return None


def esg_fallback_questions_from_issues(issues: list[dict[str, Any]]) -> list[str]:
    """issues만으로 보완 질문 문구를 최소 생성(LLM 없어도 데모가 돌도록)"""
    if not issues:
        return []
    qs: list[str] = []
    for i in issues[:5]:
        code = i.get("code", "UNKNOWN")
        slot = i.get("slotName") or i.get("slot_name") or "-"
        msg = i.get("message") or ""
        qs.append(f"[{code}] ({slot}) 보완 제출이 필요합니다. {msg}".strip())
    return qs


def esg_fallback_anomaly_candidates(_result_json: dict[str, Any]) -> list[dict[str, Any]]:
    """Day4 A-1(이상치 원인 후보) fallback: 규칙/휴리스틱 카드"""
    rationale_tail = "추가 증빙 확인 후 원인 분류가 가능합니다."
    return [
        {
            "slot_name": "electricity_usage_2025",
            "title": "생산량 증가/설비 가동률 상승",
            "confidence": 0.55,
            "rationale": f"특정 기간 전력 급등은 생산/가동률 변화 가능성이 있습니다. {rationale_tail}",
            "suggested_evidence": [
                "기간별 생산량/가동시간 로그",
                "라인/설비별 가동률 리포트",
                "수주/출하 증가 근거",
            ],
        },
        {
            "slot_name": "electricity_usage_2025",
            "title": "설비 증설/신규 장비 도입",
            "confidence": 0.52,
            "rationale": f"신규 설비 도입 직후 전력 증가 패턴일 수 있습니다. {rationale_tail}",
            "suggested_evidence": [
                "설비 도입/설치 내역(계약/검수 문서)",
                "설비 시운전 기록",
                "설비별 전력 분해 데이터(가능 시)",
            ],
        },
        {
            "slot_name": "electricity_usage_2025",
            "title": "계측기/검침 오류 또는 단위·기간 착오",
            "confidence": 0.50,
            "rationale": f"비율이 큰 급증은 계측/입력 오류 가능성도 배제 불가. {rationale_tail}",
            "suggested_evidence": [
                "계측기 교정 성적서(해당 기간)",
                "전기요금 고지서 원본(PDF)",
                "검침값 원시 로그(계량기/EMS 로그)",
            ],
        },
    ]


def esg_raise_500(e: Exception) -> None:
    """
    로컬 개발에서 500이 났을 때 원인을 /docs 응답(detail)로 바로 확인하기 위한 함수.
    ESG_DEBUG=1이면 traceback도 포함.
    """
    if ESG_DEBUG:
        tb = traceback.format_exc()
        logger.error(tb)
        raise HTTPException(
            status_code=500,
            detail=f"{type(e).__name__}: {e}\n\n{tb}",
        )
    raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")


# ------------------------------------------------------------
# Main: /ai/agent/run
# ------------------------------------------------------------
@app.post("/ai/agent/run")
def esg_run_agent(
    draft_id: str = Form(...),
    files: list[UploadFile] = File(...),

    # ✅ 오늘 확정 계약(옵션)
    slot_hint: str | None = Form(None),      # JSON string
    allowed_items: str | None = Form(None),  # JSON string(list)
    company_id: str | None = Form(None),
    period_start: str | None = Form(None),
    period_end: str | None = Form(None),

    db: Session = Depends(esg_get_db),
):
    """
    업로드 파일 저장 -> (이전 실행 조회) -> LangGraph 실행 -> 결과 JSON 구성 -> (diff 계산) -> DB 저장
    """
    try:
        # 1) 업로드 저장 (tmp_uploads 또는 outputs에 누적됨)
        saved_files = esg_save_uploads(files)

        # 2) 이전 실행 조회(있으면 A-3 diff 계산에 사용)
        prev = db_repo.esg_db_get_latest_run_by_draft(db, draft_id)

        # 3) 입력 파라미터 JSON 파싱
        parsed_slot_hint = esg_safe_json_loads(slot_hint)
        parsed_allowed_items = esg_safe_json_loads(allowed_items)
        if not isinstance(parsed_allowed_items, list):
            parsed_allowed_items = []

        # 4) LangGraph 초기 state
        run_id = uuid.uuid4().hex[:12]
        init_state: dict[str, Any] = {
            "draft_id": draft_id,
            "company_id": company_id,
            "period": {"start": period_start, "end": period_end} if (period_start or period_end) else None,

            "files": saved_files,
            "allowed_items": parsed_allowed_items,
            "slot_hint": parsed_slot_hint,

            # 그래프 노드에서 채울 값(호환용)
            "triage": {},
            "slot_map": [],
            "extracted": [],
            "validation": [],
            "issues": [],
            "evidence": [],

            # LLM 노드 산출(오늘 스펙)
            "clarification_questions": [],
            "summary_cards": {},

            # Day4 호환(기존 필드)
            "questions": [],
            "status": "OK",
        }

        # 5) 그래프 실행
        out = dict(graph.invoke(init_state))

        # 6) triage 최소 보장
        triage = out.get("triage") or {
            "file_count": len(saved_files),
            "kinds": sorted(list({f.get("kind") for f in saved_files})),
            "exts": sorted(list({f.get("ext") for f in saved_files})),
        }

        # 7) summary_cards 정규화
        raw_summary = out.get("summary_cards")
        if isinstance(raw_summary, dict):
            summary_cards = raw_summary
        else:
            summary_cards = {"approver": raw_summary or [], "buyer": raw_summary or []}

        # 8) 결과 JSON 구성
        result_json: dict[str, Any] = {
            "run_id": run_id,
            "prev_run_id": prev.run_id if prev else None,
            "draft_id": draft_id,

            "status": out.get("status", "OK"),
            "triage": triage,

            "files": out.get("files", saved_files),
            "slot_map": out.get("slot_map", []),
            "extracted": out.get("extracted", []),

            # ✅ 오늘 확정 계약 키
            "validation": out.get("validation", []),
            "issues": out.get("issues", []),
            "evidence": out.get("evidence", []),

            "clarification_questions": out.get("clarification_questions", []),
            "summary_cards": summary_cards,

            # ✅ Day4 호환(기존 키 유지)
            "questions": out.get("questions", []),
        }

        # 9) 질문 fallback: questions/clarification_questions 둘 다 채우기
        if not result_json["questions"]:
            result_json["questions"] = esg_fallback_questions_from_issues(result_json["issues"])
        if not result_json["clarification_questions"]:
            result_json["clarification_questions"] = list(result_json["questions"])

        # 10) A-1 fallback
        anomaly_candidates = out.get("anomaly_candidates") or []
        if not anomaly_candidates:
            anomaly_candidates = esg_fallback_anomaly_candidates(result_json)
        result_json["anomaly_candidates"] = anomaly_candidates

        # 11) A-3 diff (DB 기반 비교)
        prev_result = prev.result_json if prev else None
        result_json["resubmit_diff"] = esg_compute_resubmit_diff(prev_result, result_json)

        # 12) DB 저장
        db_repo.esg_db_save_run(
            db,
            run_id=run_id,
            draft_id=draft_id,
            prev_run_id=(prev.run_id if prev else None),
            status=str(result_json["status"]),
            result_json=result_json,
        )
        db_repo.esg_db_save_files(db, run_id=run_id, files=saved_files)

        return result_json

    except HTTPException:
        raise
    except Exception as e:
        esg_raise_500(e)


@app.get("/ai/runs/{run_id}")
def esg_get_run(run_id: str, db: Session = Depends(esg_get_db)):
    try:
        run = db_repo.esg_db_get_run(db, run_id)
        if not run:
            raise HTTPException(status_code=404, detail="run not found")
        return run.result_json
    except HTTPException:
        raise
    except Exception as e:
        esg_raise_500(e)


@app.get("/ai/drafts/{draft_id}/latest")
def esg_get_latest_by_draft(draft_id: str, db: Session = Depends(esg_get_db)):
    try:
        run = db_repo.esg_db_get_latest_run_by_draft(db, draft_id)
        if not run:
            raise HTTPException(status_code=404, detail="no runs for this draft_id")
        return run.result_json
    except HTTPException:
        raise
    except Exception as e:
        esg_raise_500(e)


# ------------------------------------------------------------
# (서브1) 규정/가이드 근거 조회 - Day4 데모(판정 영향 0)
# ------------------------------------------------------------
@app.post("/ai/rag/lookup", response_model=RagLookupResponse)
def esg_rag_lookup(req: RagLookupRequest):
    return RagLookupResponse(
        slot_name=req.slot_name,
        issue_code=req.issue_code,
        snippets=[
            RagSnippet(
                source="DEMO",
                excerpt="관련 근거를 찾지 못했습니다. (데모: 문서 코퍼스 확장 필요)",
                page=None,
                score=None,
            )
        ],
        note="사이드 패널 참고용 근거 조회입니다. 메인 판정에는 사용되지 않습니다.(판정 영향 0)",
    )


# ------------------------------------------------------------
# (서브2) 공급망 리스크 예측(판정 영향 0) - Day4 데모 카드
# ------------------------------------------------------------
@app.post("/ai/supplychain/predict", response_model=SupplychainPredictResponse)
def esg_supplychain_predict(req: SupplychainPredictRequest, db: Session = Depends(esg_get_db)):
    try:
        drivers: list[str] = []
        score = 0.35

        # 1) 오늘 스펙: current_status/issues가 들어오면 그걸 우선 사용
        st = (req.current_status or "").upper().strip()
        issues = req.issues or []

        if st in {"OK", "WARN", "FAIL"}:
            if st == "FAIL":
                score = 0.70
                drivers.append("제출 데이터 검증 FAIL 발생")
            elif st == "WARN":
                score = 0.50
                drivers.append("제출 데이터 검증 WARN 발생")
            else:
                score = 0.30
                drivers.append("제출 데이터 검증 OK")

            if issues:
                drivers.append(f"이슈 {len(issues)}건 탐지")

        # 2) Day4 호환: draft_id가 들어오면 latest 상태로 보정
        elif req.draft_id:
            latest = db_repo.esg_db_get_latest_run_by_draft(db, req.draft_id)
            if latest:
                st2 = str(latest.status).upper()
                if st2 == "FAIL":
                    score = 0.65
                    drivers.append("제출 데이터 검증 FAIL 발생(최근 실행)")
                elif st2 == "WARN":
                    score = 0.50
                    drivers.append("제출 데이터 검증 WARN 발생(최근 실행)")
                else:
                    score = 0.30
                    drivers.append("제출 데이터 검증 OK(최근 실행)")
            else:
                drivers.append("해당 draft_id의 실행 이력이 없음(초기 상태)")

        # risk_level
        risk_level = "LOW"
        if score >= 0.65:
            risk_level = "MEDIUM"
        if score >= 0.80:
            risk_level = "HIGH"

        return SupplychainPredictResponse(
            supplier_name=req.supplier_name,
            risk_level=risk_level,
            risk_score=round(float(score), 2),
            drivers=drivers or ["데모: 내부 신호 기반 리스크 산정"],
            recommended_monitoring=[
                "고위험 기간(급등/누락) 재발 여부 모니터링",
                "보완요청 리드타임(재제출 지연) 추적",
            ],
            note="운영 참고용 예측 카드입니다(판정 영향 0). 외부 Search 연동 시 drivers를 확장할 수 있습니다.",
        )

    except HTTPException:
        raise
    except Exception as e:
        esg_raise_500(e)