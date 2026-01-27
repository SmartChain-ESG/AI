# app/main.py
from __future__ import annotations

import json
import logging
import os
import traceback
import uuid
from typing import Any, Optional

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import esg_get_db
from app.db import repo as db_repo
from app.graph.build import esg_build_graph
from app.utils.files import esg_save_uploads
from app.utils.diff import esg_compute_resubmit_diff
from app.utils.llm_flag import esg_llm_trace_init


# ------------------------------------------------------------
# Logging
# ------------------------------------------------------------
logger = logging.getLogger("esg_api")
logging.basicConfig(level=logging.INFO)

# ESG_DEBUG=1 이면 500 detail에 traceback까지 포함(로컬 개발용)
ESG_DEBUG = os.getenv("ESG_DEBUG", "0") == "1"


def esg_raise_500(e: Exception) -> None:
    if ESG_DEBUG:
        tb = traceback.format_exc()
        logger.error(tb)
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}\n\n{tb}")
    raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")


def esg_safe_json_loads(s: Optional[str]) -> Any:
    """Form으로 들어오는 JSON string을 안전하게 dict/list로 변환"""
    if not s:
        return None
    try:
        return json.loads(s)
    except Exception:
        return None


def esg_fallback_questions_from_issues(issues: list[dict[str, Any]]) -> list[str]:
    """issues만으로 보완요청 문구 최소 생성(LLM 없어도 데모가 돌도록)"""
    if not issues:
        return []
    qs: list[str] = []
    for it in issues:
        lv = str(it.get("level", "")).upper()
        if lv not in ("FAIL", "WARN"):
            continue
        code = it.get("code", "UNKNOWN")
        slot = it.get("slot_name") or it.get("slotName") or "-"
        msg = it.get("message") or ""
        qs.append(f"[{code}] ({slot}) 보완 제출이 필요합니다. {msg}".strip())
        if len(qs) >= 6:
            break
    return qs or ["[보완요청] 추가 자료 제출을 요청드립니다."]


def esg_fallback_anomaly_candidates(_result_json: dict[str, Any]) -> list[dict[str, Any]]:
    """A-1(이상치 원인 후보) fallback 카드"""
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


# ------------------------------------------------------------
# App
# ------------------------------------------------------------
app = FastAPI(title="ESG AI API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 내부 개발용(필요 시 제한)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

graph = esg_build_graph()  # 서버 시작 시 1회 compile


@app.get("/healthz")
def esg_healthz():
    return {"ok": True}

@app.get("/health")
def esg_health():
    return {"status": "ok"}

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
    supplier_name: str | None = None
    current_status: str | None = None
    issues: list[dict[str, Any]] = Field(default_factory=list)
    # Day4 호환: 있으면 latest run 기반으로 읽어올 수도 있음
    draft_id: str | None = None


class SupplychainPredictResponse(BaseModel):
    supplier_name: str | None = None
    risk_level: str
    risk_score: float
    drivers: list[str]
    recommended_monitoring: list[str]
    note: str


# ------------------------------------------------------------
# Main: /ai/agent/run
# ------------------------------------------------------------
@app.post("/ai/agent/run")
def esg_run_agent(
    draft_id: str = Form(...),
    files: list[UploadFile] = File(...),
    # Day5 계약 확장(없어도 동작)
    slot_hint: str | None = Form(default=None),       # JSON string or plain string (권장: JSON)
    allowed_items: str | None = Form(default=None),   # JSON string list 권장
    company_id: str | None = Form(default=None),
    period_start: str | None = Form(default=None),
    period_end: str | None = Form(default=None),
    db: Session = Depends(esg_get_db),
):
    """
    업로드 저장 -> 이전 실행 조회 -> LangGraph 실행 -> 고정 스키마 result_json 구성 -> diff 계산 -> DB 저장
    """
    try:
        # 1) 업로드 저장
        saved_files = esg_save_uploads(files)

        # 2) 이전 실행 조회
        prev = db_repo.esg_db_get_latest_run_by_draft(db, draft_id)

        # 3) 입력 파라미터 파싱(JSON이면 dict/list로)
        parsed_slot_hint = esg_safe_json_loads(slot_hint)
        parsed_allowed_items = esg_safe_json_loads(allowed_items)
        if not isinstance(parsed_allowed_items, list):
            parsed_allowed_items = []

        # 4) init_state (중복 키 절대 금지)
        run_id = uuid.uuid4().hex[:12]
        init_state: dict[str, Any] = {
            "draft_id": draft_id,
            "company_id": company_id,
            "period": {"start": period_start, "end": period_end} if (period_start or period_end) else None,
            "files": saved_files,
            "allowed_items": parsed_allowed_items,
            "slot_hint": parsed_slot_hint,  # JSON dict이든 string이든(파싱 실패하면 None)
            "llm_trace": esg_llm_trace_init(),

            # 그래프 노드들이 채워갈 필드(고정 계약)
            "triage": {},
            "slot_map": [],
            "extracted": [],
            "validation": [],
            "issues": [],
            "evidence": [],
            "clarification_questions": [],
            "summary_cards": {},
            "anomaly_candidates": [],
            "status": "OK",
        }

        # 5) graph 실행
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
            # 혹시 list로 오면 역할별로 같은 내용 넣어둠(데모 방어)
            summary_cards = {"approver": raw_summary or [], "buyer": raw_summary or []}

        # 8) 질문 키 혼선 정리:
        # - 그래프가 questions로 넣었든, clarification_questions로 넣었든, 최종은 clarification_questions가 공식 계약
        cq = out.get("clarification_questions")
        if not cq:
            cq = out.get("questions")  # 하위 호환
        if not isinstance(cq, list):
            cq = []

        # 9) anomaly_candidates fallback
        anomaly_candidates = out.get("anomaly_candidates") or out.get("anomaly_candidates", [])
        if not anomaly_candidates:
            anomaly_candidates = esg_fallback_anomaly_candidates({})

        # 10) result_json (고정 키 세트, 중복 키 절대 금지)
        result_json: dict[str, Any] = {
            "run_id": run_id,
            "prev_run_id": prev.run_id if prev else None,
            "draft_id": draft_id,
            "status": out.get("status", "OK"),
            "triage": triage,

            "files": out.get("files", saved_files),
            "slot_map": out.get("slot_map", []),
            "extracted": out.get("extracted", []),

            "validation": out.get("validation", []),
            "issues": out.get("issues", []),
            "evidence": out.get("evidence", []),

            "clarification_questions": cq,
            "summary_cards": summary_cards,
            "anomaly_candidates": anomaly_candidates,

            # 관측용(LLM on/off, fallback 여부 확인)
            "llm_trace": out.get("llm_trace") or init_state.get("llm_trace"),
        }

        # 11) 질문 fallback (항상 최소 1개는 나오게)
        if not result_json["clarification_questions"]:
            result_json["clarification_questions"] = esg_fallback_questions_from_issues(result_json["issues"])

        # 12) A-3 diff
        prev_result = prev.result_json if prev else None
        result_json["resubmit_diff"] = esg_compute_resubmit_diff(prev_result, result_json)

        # 13) DB 저장
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
# (서브1) 규정/가이드 근거 조회 - Day5 데모(판정 영향 0)
# ------------------------------------------------------------
@app.post("/ai/rag/lookup", response_model=RagLookupResponse)
def esg_rag_lookup(req: RagLookupRequest):
    return RagLookupResponse(
        slot_name=req.slot_name,
        issue_code=req.issue_code,
        snippets=[
            RagSnippet(
                source="DEMO",
                excerpt="관련 근거를 찾지 못했습니다. (Day5: keyword/corpus 뼈대만 유지, Day6에 VectorDB로 교체)",
                page=None,
                score=None,
            )
        ],
        note="사이드 패널 참고용 근거 조회입니다. 메인 판정에는 사용되지 않습니다. (판정 영향 0)",
    )


# ------------------------------------------------------------
# (서브2) 공급망 리스크 예측(판정 영향 0) - Day5 데모
# ------------------------------------------------------------
@app.post("/ai/supplychain/predict", response_model=SupplychainPredictResponse)
def esg_supplychain_predict(req: SupplychainPredictRequest, db: Session = Depends(esg_get_db)):
    try:
        drivers: list[str] = []
        score = 0.35

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
                "급등/누락 재발 여부 모니터링",
                "보완요청 리드타임(재제출 지연) 추적",
            ],
            note="운영 참고용 예측 카드입니다. 메인 판정에는 사용되지 않습니다. (판정 영향 0)",
        )

    except HTTPException:
        raise
    except Exception as e:
        esg_raise_500(e)