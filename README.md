# AI 기반 협력사 자료 자동 검증 시스템

**협력사가 제출하는 안전/컴플라이언스/ESG 문서(PDF, XLSX, 이미지)를 자동으로 분류하고,
규칙 기반 검증 + LLM 분석을 결합하여 verdict(판정) 및 risk level(위험도)을 산출하는 Stateless FastAPI 시스템입니다.**

---

본 프로젝트는 초기 기획 단계에서 생성형 AI(Claude)를 활용해 개념적 구조와 로직 정리의 초안을 참고했으며,
실제 판단 기준의 구체화, 알고리즘 설계, FastAPI 구현 및 운영 로직은 모두 팀 내부에서 직접 설계·개발했습니다.

---

## 프로젝트 팀 구성 (Contributors)

프로젝트를 이끄는 핵심 인력 및 역할 분담 현황입니다.

| 역할 | 이름 | GitHub Profile | 주요 담당 기능 |
| :--- | :--- | :--- | :--- |
| **PM / 조장** | **이종헌** | [![jjongjjongR's GitHub](https://img.shields.io/badge/jjongjjongR-181717?style=for-the-badge&logo=github&logoColor=white)](https://github.com/jjongjjongR) | ESG |
| **AI 파트 리더** | **이수빈** | [![leesupin's GitHub](https://img.shields.io/badge/leesupin-181717?style=for-the-badge&logo=github&logoColor=white)](https://github.com/leesupin) | 안전-보건 |
| **AI Developer** | **배수한** | [![uh004's GitHub](https://img.shields.io/badge/uh004-181717?style=for-the-badge&logo=github&logoColor=white)](https://github.com/uh004) | 컴플라이언스 |

---

## Tech Stack

![Python](https://img.shields.io/badge/Python-3.10-3776AB?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)
![OpenAI](https://img.shields.io/badge/OpenAI_GPT-412991?style=for-the-badge&logo=openai&logoColor=white)
![YOLO26](https://img.shields.io/badge/YOLO26-00FFFF?style=for-the-badge&logo=yolo&logoColor=black)
![ChromaDB](https://img.shields.io/badge/ChromaDB-FF6F00?style=for-the-badge)
![Git](https://img.shields.io/badge/Git-F05032?style=for-the-badge&logo=git&logoColor=white)

| 구분 | 기술 |
|------|------|
| Framework | FastAPI + Uvicorn |
| LLM | OpenAI GPT-4o-mini (텍스트/데이터), GPT-5.1 (Vision/최종판정) |
| Object Detection | YOLO26n (CrowdHuman fine-tuned, 인원수 감지) |
| Vector DB | ChromaDB (RAG 기반 검색) |
| OCR | Naver Clova OCR |
| 파싱 | PyMuPDF (PDF), pandas + openpyxl (XLSX/CSV) |
| HTTP | httpx (비동기 다운로드/OCR 호출) |
| 검증 | Pydantic v2 스키마 |

---

## 시스템 아키텍처

```
apps/
├── ai_run_api/      [메인] 협력사 문서 자동 검증 엔진
├── chatbot_api/     [서브] 컴플라이언스 규정 Q&A 챗봇
└── out_risk_api/    [서브] 외부 뉴스 기반 ESG 리스크 분석
```

### API 포트 구성

| API | 포트 | 설명 |
|-----|------|------|
| ai_run_api | 8000 | 메인 검증 엔진 |
| chatbot_api | 8001 | 규정 Q&A 챗봇 |
| out_risk_api | 8002 | 외부 리스크 분석 |

---

## [메인] ai_run_api - 협력사 문서 자동 검증

### 엔드포인트

| Method | Path | 설명 |
|--------|------|------|
| `GET` | `/health` | 서버 상태 확인 |
| `POST` | `/run/preview` | 파일 분류 + 슬롯 추정 |
| `POST` | `/run/submit` | 6단계 파이프라인 실행 → verdict + risk_level 반환 |

### Submit 파이프라인 (6단계)

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

### Verdict & Risk Level 기준

**Verdict (슬롯 단위)**

| Verdict | 의미 | 조건 |
|---------|------|------|
| **NEED_FIX** | 파일 자체 문제 (분석 불가) | MISSING_SLOT, PARSE_FAILED, HEADER_MISMATCH 등 |
| **NEED_CLARIFY** | 내용 문제 (분석 완료, 이슈 발견) | VIOLATION_DETECTED, LOW_EDUCATION_RATE 등 |
| **PASS** | 이상 없음 | reason 없음 |

**Risk Level (업체 단위 집계)**

| Risk Level | 조건 |
|------------|------|
| **HIGH** | 하나라도 NEED_FIX가 있음 |
| **MEDIUM** | NEED_FIX 없음, Safety/Compliance에 NEED_CLARIFY 있음 |
| **LOW** | 모두 PASS 또는 ESG 도메인에만 NEED_CLARIFY |

### 디렉토리 구조

```
apps/ai_run_api/app/
├── main.py                 # FastAPI 진입점 + /health
├── api/run.py              # POST /run/preview, /run/submit
├── schemas/run.py          # Pydantic 스키마
├── pipeline/               # Preview, Triage, Submit 파이프라인
├── engines/                # 도메인별 검증 로직 (safety/compliance/esg)
├── extractors/             # PDF, XLSX, OCR, YOLO 추출기
├── llm/                    # LLM 클라이언트 + 프롬프트
├── storage/                # 다운로더, 임시 저장소
└── core/                   # 설정, 에러 처리
```

---

## [서브] chatbot_api - 컴플라이언스 Q&A 챗봇

사내 컴플라이언스 규정 문서를 벡터DB(ChromaDB)에 저장하고, RAG 기반으로 질문에 답변하는 챗봇입니다.

### 엔드포인트

| Method | Path | 설명 |
|--------|------|------|
| `GET` | `/health` | 서버 상태 확인 |
| `POST` | `/chat` | 사용자 질문 → RAG 기반 답변 |
| `POST` | `/admin/upload` | 규정 문서 업로드 (관리자용, API Key 필요) |

### 디렉토리 구조

```
apps/chatbot_api/app/
├── main.py                 # FastAPI 진입점
├── api/chat.py             # 채팅 엔드포인트
├── api/admin.py            # 관리자 문서 업로드
├── rag/                    # ChromaDB + RAG 로직
├── core/config.py          # pydantic-settings 기반 설정
└── vectordb/               # ChromaDB 저장 경로 (gitignore)
```

---

## [서브] out_risk_api - 외부 리스크 분석

협력사명으로 GDELT/RSS 뉴스를 검색하고, ESG 키워드 기반 감정 분석으로 외부 리스크 점수를 산출합니다.

### 엔드포인트

| Method | Path | 설명 |
|--------|------|------|
| `GET` | `/health` | 서버 상태 확인 |
| `POST` | `/risk/external/detect` | 협력사 리스트 → 외부 리스크 분석 |
| `POST` | `/risk/external/search/preview` | 검색 결과 미리보기 |

### 리스크 산출 방식

1. 협력사명으로 GDELT API / Google RSS 검색
2. ESG 키워드 필터링 (사고, 환경오염, 법적 분쟁 등)
3. 감정 분석으로 부정 문서 분류
4. 문서 발행일 기준 가중치 적용 (최근 30일: 1.5x, 90일: 1.0x, 180일: 0.7x)
5. 총점 기반 리스크 레벨 산출 (HIGH ≥10, MEDIUM ≥5, LOW <5)

### 디렉토리 구조

```
apps/out_risk_api/app/
├── main.py                 # FastAPI 진입점
├── api/risk.py             # 리스크 분석 엔드포인트
├── pipeline/detect.py      # 검색 → 분석 → 점수화 파이프라인
├── search/                 # GDELT, RSS 검색 프로바이더
├── analyze/sentiment.py    # 감정 분석 (키워드 기반)
├── rag/                    # ChromaDB 연동 (선택적 RAG)
└── core/config.py          # 환경변수 설정
```

---

## 실행 방법

### 1. 의존성 설치

```bash
pip install -r requirements.txt
```

### 2. 환경변수 설정

```bash
cp .env.example .env
# .env 파일 편집하여 API 키 등 설정
```

### 3. 서버 실행

```bash
# ai_run_api (메인) - 포트 8000
uvicorn app.main:app --reload --port 8000 --app-dir apps/ai_run_api

# chatbot_api (서브) - 포트 8001
uvicorn app.main:app --reload --port 8001 --app-dir apps/chatbot_api

# out_risk_api (서브) - 포트 8002
uvicorn app.main:app --reload --port 8002 --app-dir apps/out_risk_api
```

### 4. Streamlit 테스트 UI (선택)

```bash
# ai_run_api UI
streamlit run apps/ai_run_api/app/ui/streamlit_app.py

# chatbot_api UI
streamlit run apps/chatbot_api/app/ui/streamlit_app.py

# out_risk_api UI
streamlit run apps/out_risk_api/app/ui/streamlit_app.py
```

---

## 환경변수 (.env)

```env
# === 공통 ===
OPENAI_API_KEY="사용자지정"

# === ai_run_api ===
CLOVA_INVOKE_URL="사용자지정"
CLOVA_OCR_SECRET="사용자지정"
OPENAI_MODEL_LIGHT="gpt-4o-mini"
OPENAI_MODEL_HEAVY="gpt-5.1"

# === chatbot_api ===
OPENAI_EMBEDDING_MODEL="text-embedding-3-small"
CHATBOT_CHROMA_PATH="apps/chatbot_api/app/vectordb"
CHATBOT_CHROMA_COLLECTION="hd_hhi_compliance_kb"
ADMIN_API_KEY="사용자지정"

# === out_risk_api ===
OUT_RISK_CHROMA_PATH="apps/out_risk_api/app/vectordb"
OUT_RISK_CHROMA_COLLECTION="hd_hhi_out_risk_kb"
```

---

## AI 모델 전략

| 모델 | 환경변수 | 용도 |
|------|----------|------|
| GPT-4o-mini (Light) | `OPENAI_MODEL_LIGHT` | PDF 분석, 데이터 분석, 보완요청 생성 |
| GPT-5.1 (Heavy) | `OPENAI_MODEL_HEAVY` | Vision 이미지 분석, 최종 판정 |
| text-embedding-3-small | `OPENAI_EMBEDDING_MODEL` | RAG 임베딩 (chatbot_api) |
| YOLO26n (CrowdHuman Few-shot Learning) | — | 이미지 인원수 감지 (ai_run_api) |
