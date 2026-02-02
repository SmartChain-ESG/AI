# AI 기반 협력사 자료 자동 검증 시스템

**협력사가 제출하는 안전/컴플라이언스/ESG 문서(PDF, XLSX, 이미지)를 자동으로 분류하고,
규칙 기반 검증 + LLM 분석을 결합하여 verdict(판정) 및 risk level(위험도)을 산출하는 Stateless FastAPI 시스템입니다.**

---

본 프로젝트는 초기 기획 단계에서 생성형 AI(Claude)를 활용해 개념적 구조와 로직 정리의 초안을 참고했으며,
실제 판단 기준의 구체화, 알고리즘 설계, FastAPI 구현 및 운영 로직은 모두 팀 내부에서 직접 설계·개발했습니다.

---

## 👥 프로젝트 팀 구성 (Contributors)

프로젝트를 이끄는 핵심 인력 및 역할 분담 현황입니다.

| 역할 | 이름 | GitHub Profile | 주요 담당 기능 |
| :--- | :--- | :--- | :--- |
| **PM / 조장** | **이종헌** | [![jjongjjongR's GitHub](https://img.shields.io/badge/jjongjjongR-181717?style=for-the-badge&logo=github&logoColor=white)](https://github.com/jjongjjongR) | ESG |
| **AI 파트 리더** | **이수빈** | [![leesupin's GitHub](https://img.shields.io/badge/leesupin-181717?style=for-the-badge&logo=github&logoColor=white)](https://github.com/leesupin) | 안전-보건 |
| **AI Developer** | **배수한** | [![uh004's GitHub](https://img.shields.io/badge/uh004-181717?style=for-the-badge&logo=github&logoColor=white)](https://github.com/uh004) | 컴플라이언스 |

---

## 💻 Tech Stack

![Python](https://img.shields.io/badge/Python-3.10-3776AB?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)
![OpenAI](https://img.shields.io/badge/OpenAI_GPT--5.1-412991?style=for-the-badge&logo=openai&logoColor=white)
![YOLOv8](https://img.shields.io/badge/YOLOv8-00FFFF?style=for-the-badge&logo=yolo&logoColor=black)
![Git](https://img.shields.io/badge/Git-F05032?style=for-the-badge&logo=git&logoColor=white)

| 구분 | 기술 |
|------|------|
| Framework | FastAPI + Uvicorn |
| LLM | OpenAI GPT-4o-mini (텍스트/데이터), GPT-5.1 (Vision/최종판정) |
| Object Detection | YOLOv8n (CrowdHuman fine-tuned, 인원수 감지) |
| OCR | Naver Clova OCR |
| 파싱 | PyMuPDF (PDF), pandas + openpyxl (XLSX/CSV) |
| HTTP | httpx (비동기 다운로드/OCR 호출) |
| 검증 | Pydantic v2 스키마 |

---

## 🏗 시스템 아키텍처

```
Client (프론트엔드)
  │
  ├─ POST /run/preview   ← 파일 분류 + 슬롯 추정
  ├─ POST /run/submit    ← 6단계 파이프라인 실행
  └─ GET  /health        ← 헬스체크
```

### Apps 구조

```
apps/
├── ai_run_api/     ← 핵심 검증 엔진 (본 문서 대상)
├── chatboot_api/   ← 챗봇 API
├── out_risk_api/   ← 외부 리스크 분석 API
├── report_api/     ← 리포트 생성 API
└── safety_api/     ← (예정)
```

---

## 📂 ai_run_api 디렉토리 구조

```
app/
├── main.py                        # FastAPI 진입점 + /health
├── api/
│   └── run.py                     # POST /run/preview, /run/submit 라우터
├── schemas/
│   └── run.py                     # Pydantic 스키마 (Verdict, RiskLevel, SlotResult 등)
├── pipeline/
│   ├── preview.py                 # Preview 파이프라인 (슬롯 추정)
│   ├── triage.py                  # Phase 1: 파일 분류 (확장자/패턴 매칭)
│   └── submit.py                  # Phase 1~6 Submit 파이프라인
├── engines/
│   ├── registry.py                # 도메인 디스패치 (safety/compliance/esg)
│   ├── safety/
│   │   ├── slots.py               # 슬롯 정의 (필수/선택, 파일 패턴)
│   │   ├── rules.py               # REASON_CODES + EXPECTED_HEADERS
│   │   ├── validators.py          # 룰 기반 검증 로직
│   │   └── cross_validators.py    # 교차 검증 (출석부 vs 교육사진)
│   ├── compliance/
│   │   ├── slots.py
│   │   ├── rules.py
│   │   ├── validators.py
│   │   └── cross_validators.py
│   └── esg/
│       ├── slots.py
│       ├── rules.py
│       ├── validators.py
│       └── cross_validators.py    # 에너지/유해물질/윤리경영 교차 검증
├── extractors/
│   ├── pdf_text.py                # PDF 텍스트 추출 + 조건부 OCR 폴백
│   ├── xlsx.py                    # XLSX/CSV 파싱 (헤더 검증 포함)
│   ├── ocr/
│   │   ├── clova_client.py        # Naver Clova OCR 클라이언트
│   │   └── ocr_router.py          # 이미지 OCR 라우터
│   └── yolo/
│       ├── person_counter.py      # YOLOv8 인원수 감지 래퍼
│       └── yolo26n_crowdhuman_fewshot.pt  # CrowdHuman fine-tuned 모델 가중치
├── llm/
│   ├── client.py                  # ask_llm() / ask_llm_vision() (Light/Heavy 분기)
│   └── prompts.py                 # 도메인별 프롬프트 (PDF/Image/Data/Judge/Clarify)
├── storage/
│   ├── downloader.py              # SAS URL → 바이트 다운로드
│   └── tmp_store.py               # 인메모리 패키지 임시 저장
├── core/
│   ├── config.py                  # 환경변수 (OPENAI_API_KEY, MODEL 등)
│   └── errors.py                  # HTTP 예외 클래스
└── db/                            # (추후 PostgreSQL 연동 예정)
```

---

## 🔄 Submit 파이프라인 (6단계)

```
(1) TRIAGE        파일 분류 — 확장자/MIME 판별, 열 수 있는지 체크
        ↓
(2) SLOT APPLY    slot_hint 적용 — 파일을 도메인 슬롯에 매핑
        ↓
(3) EXTRACT       파싱/OCR — PDF→텍스트, XLSX→DataFrame, 이미지→OCR+Vision+YOLO
        ↓
(4) VALIDATE      룰 검증 — validators.py 규칙 + LLM 이상탐지 → reasons 도출
        ↓
(4.5) CROSS       교차 검증 — 슬롯 간 1:1 비교 (예: 출석부 인원 vs 사진 인원)
        ↓
(5) CLARIFY       보완요청 생성 — PASS가 아닌 슬롯에 대해 한국어 안내문 작성
        ↓
(6) JUDGE FINAL   최종 집계 — 전체 verdict + risk_level + why 산출
```

---

## ⚖️ Verdict & Risk Level 기준

### Verdict (슬롯 단위)

| Verdict | 의미 | 조건 |
|---------|------|------|
| **NEED_FIX** | 파일 자체 문제 (분석 불가) | MISSING_SLOT, PARSE_FAILED, HEADER_MISMATCH, EMPTY_TABLE, OCR_FAILED |
| **NEED_CLARIFY** | 내용 문제 (분석 완료, 이슈 발견) | VIOLATION_DETECTED, LOW_EDUCATION_RATE, SIGNATURE_MISSING, E2_SPIKE_DETECTED, E3_BILL_MISMATCH, LLM_ANOMALY_DETECTED 등 |
| **PASS** | 이상 없음 | reason 없음 |

### Risk Level (업체 단위 집계)

| Risk Level | 조건 |
|------------|------|
| **HIGH** | 하나라도 NEED_FIX가 있음 |
| **MEDIUM** | NEED_FIX 없음, Safety/Compliance에 NEED_CLARIFY 있음 |
| **LOW** | 모두 PASS 또는 ESG 도메인에만 NEED_CLARIFY |

> ESG의 NEED_CLARIFY(사용량 급증 등)는 모니터링 대상으로, risk_level을 LOW 이상으로 올리지 않습니다.

---

## 🤖 AI 모델 전략

| 모델 | 환경변수 | 용도 |
|------|----------|------|
| GPT-4o-mini (Light) | `OPENAI_MODEL_LIGHT` | PDF 분석, 데이터 분석, 보완요청 생성 |
| GPT-5.1 (Heavy) | `OPENAI_MODEL_HEAVY` | Vision 이미지 분석 (위반사항/장면 설명), 최종 판정 (JUDGE_FINAL) |
| YOLOv8n (CrowdHuman) | — | 이미지 인원수 감지 (교차검증용, YOLO 우선 → LLM 폴백) |

---

## 🚀 실행 방법

```bash
# 1. 의존성 설치
pip install -r requirements.txt

# 2. 환경변수 설정
cp .env.example .env
# .env 파일에 OPENAI_API_KEY, CLOVA_OCR_* 등 설정

# 3. 서버 실행
cd apps/ai_run_api
uvicorn app.main:app --reload --port 8000

# 4. 헬스체크
curl http://localhost:8000/health
```

### Streamlit 테스트 UI (선택)

```bash
streamlit run apps/ai_run_api/ui/streamlit_app.py
```

---

## 📋 API 엔드포인트

| Method | Path | 설명 |
|--------|------|------|
| `GET` | `/health` | 서버 상태 확인 |
| `POST` | `/run/preview` | 파일 분류 + 슬롯 추정 |
| `POST` | `/run/submit` | 6단계 파이프라인 실행 → verdict + risk_level 반환 |

---

## 🔧 환경변수

| 변수명 | 설명 |
|--------|------|
| `OPENAI_API_KEY` | OpenAI API 키 |
| `OPENAI_MODEL_LIGHT` | 텍스트/데이터 분석 모델 (기본: gpt-4o-mini) |
| `OPENAI_MODEL_HEAVY` | Vision/최종판정 모델 (기본: gpt-5.1) |
| `CLOVA_OCR_API_URL` | Naver Clova OCR API URL |
| `CLOVA_OCR_SECRET` | Clova OCR Secret Key |
