# app/main.py
"""
FastAPI 엔트리/라우팅 (Day4)
- POST /ai/agent/run : 메인 검증 플로우 (A-1/A-2/A-3 포함 + DB 저장)
- GET  /ai/runs/{run_id}
- GET  /ai/drafts/{draft_id}/latest
- POST /ai/rag/lookup : (서브1) 규정/가이드 근거 조회 (Day4 데모 응답)
- POST /ai/supplychain/predict : (서브2) 공급망 리스크 예측 카드 (Day4 데모)
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Optional

from fastapi import FastAPI, UploadFile, File, Form, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.utils.files import esg_save_uploads
from app.graph.build import esg_build_graph

from app.db.session import Base, ENGINE, esg_get_db
from app.db import repo as db_repo
from app.utils.diff import esg_compute_resubmit_diff


# -----------------------------
# Side-service Request/Response (간단 스키마)
# -----------------------------
class RagLookupRequest(BaseModel):
    slot_name: str
    issue_code: str
    query: Optional[str] = None


class RagSnippet(BaseModel):
    source: str
    excerpt: str


class RagLookupResponse(BaseModel):
    slot_name: str
    issue_code: str
    snippets: list[RagSnippet]
    note: str


class SupplychainPredictRequest(BaseModel):
    supplier_name: str = Field(..., description="예: 성광벤드")
    draft_id: Optional[str] = Field(default=None, description="있으면 최신 run 기반으로 리스크 산정")


class SupplychainPredictResponse(BaseModel):
    supplier_name: str
    risk_level: str
    risk_score: float
    drivers: list[str]
    recommended_monitoring: list[str]
    note: str


app = FastAPI(title="AI Validation Service (Day4: Postgres Ready)")
graph = esg_build_graph()  # 서버 시작 시 1회 compile


@app.on_event("startup")
def _startup_create_tables():
    """
    Day4 MVP:
    - DB 연결을 몇 번 재시도한 뒤(create_all 전에) 테이블 생성
    - Day5~Day6에 Alembic으로 교체 예정
    """
    last_err: Exception | None = None

    for i in range(1, 21):  # 최대 20번
        try:
            with ENGINE.connect() as conn:
                conn.execute(text("SELECT 1"))
            # 연결 OK -> 테이블 생성
            Base.metadata.create_all(bind=ENGINE)
            print("[DB] create_all done")
            return
        except Exception as e:
            last_err = e
            print(f"[DB] waiting... ({i}/20) err={e}")
            time.sleep(0.5)

    raise RuntimeError(f"DB is not reachable after retries: {last_err}")


@app.get("/healthz")
def healthz():
    return {"ok": True}


# -----------------------------
# A-2: 보완요청서(문장) fallback 생성
# -----------------------------
def _fallback_questions_from_issues(issues: list[dict[str, Any]]) -> list[str]:
    qs: list[str] = []
    for it in issues:
        lv = str(it.get("level", "")).upper()
        if lv not in ("FAIL", "WARN"):
            continue

        code = it.get("code", "")
        slot = it.get("slot_name", "unknown")
        msg = it.get("message", "")

        if code == "ANOMALY_SPIKE_RATIO":
            qs.append(
                "전력 사용량 급증(10/12~10/19) 원인 확인을 위해 아래 자료를 추가 제출해 주세요: "
                "① 전기요금 고지서 원본(PDF) ② 계측기 교정 성적서(해당 기간) "
                "③ 생산량/가동률 일별 또는 주간 데이터(XLSX/CSV)."
            )
        elif slot == "code_of_conduct":
            qs.append(
                "행동강령/윤리 서약 문서의 최신 승인본을 제출해 주세요. "
                "승인일/결의 주체/버전 정보가 포함된 파일(이미지 또는 PDF)을 권장합니다."
            )
        else:
            qs.append(f"[보완요청] {slot}: {msg} (이슈코드: {code}) 관련 추가 근거/원본 자료를 제출해 주세요.")

        if len(qs) >= 3:
            break
    return qs


# -----------------------------
# A-1: 이상치 원인 후보 fallback (LLM 없이도 데모)
# -----------------------------
def _fallback_anomaly_candidates(result_json: dict[str, Any]) -> list[dict[str, Any]]:
    issues = result_json.get("issues", []) or []
    extracted = result_json.get("extracted", []) or []

    has_spike = any((i.get("code") == "ANOMALY_SPIKE_RATIO") for i in issues)
    if not has_spike:
        return []

    meta_2024 = None
    meta_2025 = None
    for x in extracted:
        if x.get("slot_name") == "electricity_usage_2024":
            meta_2024 = (x.get("meta") or {})
        if x.get("slot_name") == "electricity_usage_2025":
            meta_2025 = (x.get("meta") or {})

    r24 = (meta_2024 or {}).get("spike_ratio")
    r25 = (meta_2025 or {}).get("spike_ratio")
    normal_avg = (meta_2025 or {}).get("normal_avg")

    ref = []
    if r24 is not None and r25 is not None:
        ref.append(f"참고: 2024 동일 구간 spike_ratio={float(r24):.2f}, 2025={float(r25):.2f}")
    if normal_avg is not None:
        ref.append(f"2025 평시 평균={float(normal_avg):.0f}kWh")

    rationale_tail = " / ".join(ref) if ref else "급증 패턴 확인(10/12~10/19)"

    return [
        {
            "slot_name": "electricity_usage_2025",
            "title": "생산량 증가/가동률 상승",
            "confidence": 0.55,
            "rationale": f"급증 구간에 집중된 사용량 상승. {rationale_tail}",
            "suggested_evidence": [
                "생산량/가동률 일별 데이터(XLSX/CSV)",
                "설비 가동 로그(PLC/설비 로그)",
                "근무/교대 편성표(연장 가동 여부)",
            ],
        },
        {
            "slot_name": "electricity_usage_2025",
            "title": "설비 증설/신규 라인 가동",
            "confidence": 0.45,
            "rationale": f"특정 기간 집중 상승은 신규 설비/라인 변경과도 일치 가능. {rationale_tail}",
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


# -----------------------------
# Main: /ai/agent/run
# -----------------------------
@app.post("/ai/agent/run")
def esg_run_agent(
    draft_id: str = Form(...),
    files: list[UploadFile] = File(...),
    db: Session = Depends(esg_get_db),
):
    saved_files = esg_save_uploads(files)

    prev = db_repo.esg_db_get_latest_run_by_draft(db, draft_id)
    run_id = uuid.uuid4().hex[:12]

    init_state = {
        "draft_id": draft_id,
        "files": saved_files,
        "slot_hint": None,
        "slot_map": [],
        "extracted": [],
        "issues": [],
        "questions": [],
        "summary_cards": [],
        "status": "OK",
    }
    out = dict(graph.invoke(init_state))

    triage = out.get("triage") or {
        "file_count": len(saved_files),
        "kinds": sorted(list({f.get("kind") for f in saved_files})),
        "exts": sorted(list({f.get("ext") for f in saved_files})),
    }

    result_json: dict[str, Any] = {
        "run_id": run_id,
        "prev_run_id": prev.run_id if prev else None,
        "draft_id": draft_id,
        "status": out.get("status", "OK"),
        "triage": triage,
        "files": out.get("files", saved_files),
        "slot_map": out.get("slot_map", []),
        "extracted": out.get("extracted", []),
        "issues": out.get("issues", []),
        "questions": out.get("questions", []),
        "summary_cards": out.get("summary_cards", []),
    }

    if not result_json["questions"]:
        result_json["questions"] = _fallback_questions_from_issues(result_json["issues"])

    anomaly_candidates = out.get("anomaly_candidates")
    if not anomaly_candidates:
        anomaly_candidates = _fallback_anomaly_candidates(result_json)
    result_json["anomaly_candidates"] = anomaly_candidates or []

    prev_result = prev.result_json if prev else None
    result_json["resubmit_diff"] = esg_compute_resubmit_diff(prev_result, result_json)

    try:
        db_repo.esg_db_save_run(
            db,
            run_id=run_id,
            draft_id=draft_id,
            prev_run_id=(prev.run_id if prev else None),
            status=str(result_json["status"]),
            result_json=result_json,
        )
        db_repo.esg_db_save_files(db, run_id=run_id, files=saved_files)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB save failed: {e}")

    return result_json


@app.get("/ai/runs/{run_id}")
def esg_get_run(run_id: str, db: Session = Depends(esg_get_db)):
    run = db_repo.esg_db_get_run(db, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="run not found")
    return run.result_json


@app.get("/ai/drafts/{draft_id}/latest")
def esg_get_latest_by_draft(draft_id: str, db: Session = Depends(esg_get_db)):
    run = db_repo.esg_db_get_latest_run_by_draft(db, draft_id)
    if not run:
        raise HTTPException(status_code=404, detail="no runs for this draft_id")
    return run.result_json


# -----------------------------
# (서브1) 규정/가이드 근거 조회 - Day4 데모
# -----------------------------
@app.post("/ai/rag/lookup", response_model=RagLookupResponse)
def esg_rag_lookup(req: RagLookupRequest):
    return RagLookupResponse(
        slot_name=req.slot_name,
        issue_code=req.issue_code,
        snippets=[RagSnippet(source="DEMO", excerpt="관련 근거를 찾지 못했습니다. (데모: 문서 코퍼스 확장 필요)")],
        note="사이드 패널 참고용 근거 조회입니다. 메인 판정에는 사용되지 않습니다.",
    )


# -----------------------------
# (서브2) 공급망 예측(판정 영향 0) - Day4 데모 카드
# -----------------------------
@app.post("/ai/supplychain/predict", response_model=SupplychainPredictResponse)
def esg_supplychain_predict(req: SupplychainPredictRequest, db: Session = Depends(esg_get_db)):
    drivers: list[str] = []
    score = 0.35

    if req.draft_id:
        latest = db_repo.esg_db_get_latest_run_by_draft(db, req.draft_id)
        if latest:
            st = str(latest.status).upper()
            if st == "FAIL":
                score = 0.65
                drivers.append("제출 데이터 검증 FAIL 발생")
            elif st == "WARN":
                score = 0.50
                drivers.append("제출 데이터 검증 WARN 발생")
            else:
                score = 0.30
                drivers.append("제출 데이터 검증 OK")
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
        recommended_monitoring=[],
        note="운영 참고용 예측 카드입니다(판정 영향 0). 외부 데이터 연동 시 정교화 가능합니다.",
    )