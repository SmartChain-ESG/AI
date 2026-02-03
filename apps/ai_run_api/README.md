# ai_run_api - 협력사 문서 자동 검증 엔진 [메인]

협력사가 제출하는 안전/컴플라이언스/ESG 문서(PDF, XLSX, 이미지)를 자동으로 분류하고,
규칙 기반 검증 + LLM 분석을 결합하여 verdict(판정) 및 risk level(위험도)을 산출합니다.

## 엔드포인트

| Method | Path | 설명 |
|--------|------|------|
| `GET` | `/health` | 서버 상태 확인 |
| `POST` | `/run/preview` | 파일 분류 + 슬롯 추정 |
| `POST` | `/run/submit` | 6단계 파이프라인 실행 → verdict + risk_level 반환 |

## 실행 방법

```bash
# 서버 실행 (포트 8000)
uvicorn app.main:app --reload --port 8000 --app-dir apps/ai_run_api

# Streamlit UI
streamlit run apps/ai_run_api/app/ui/streamlit_app.py
```

## 디렉토리 구조

```
app/
├── main.py                 # FastAPI 진입점 + /health
├── api/run.py              # POST /run/preview, /run/submit
├── schemas/run.py          # Pydantic 스키마 (Verdict, RiskLevel, SlotResult 등)
├── pipeline/
│   ├── preview.py          # Preview 파이프라인 (슬롯 추정)
│   ├── triage.py           # Phase 1: 파일 분류
│   └── submit.py           # Phase 1~6 Submit 파이프라인
├── engines/
│   ├── registry.py         # 도메인 디스패치 (safety/compliance/esg)
│   ├── safety/             # 안전 도메인 검증
│   ├── compliance/         # 컴플라이언스 도메인 검증
│   └── esg/                # ESG 도메인 검증
├── extractors/
│   ├── pdf_text.py         # PDF 텍스트 추출 + 조건부 OCR 폴백
│   ├── xlsx.py             # XLSX/CSV 파싱
│   ├── ocr/                # Naver Clova OCR
│   └── yolo/               # YOLO26n 인원수 감지
├── llm/
│   ├── client.py           # ask_llm() / ask_llm_vision()
│   └── prompts.py          # 도메인별 프롬프트
├── storage/
│   ├── downloader.py       # SAS URL → 바이트 다운로드
│   └── tmp_store.py        # 인메모리 패키지 임시 저장
└── core/
    ├── config.py           # 환경변수
    └── errors.py           # HTTP 예외 클래스
```

## Submit 파이프라인 (6단계)

```
(1) TRIAGE        파일 분류 — 확장자/MIME 판별
        ↓
(2) SLOT APPLY    slot_hint 적용 — 파일을 도메인 슬롯에 매핑
        ↓
(3) EXTRACT       파싱/OCR — PDF→텍스트, XLSX→DataFrame, 이미지→OCR+Vision+YOLO
        ↓
(4) VALIDATE      룰 검증 — validators.py 규칙 + LLM 이상탐지
        ↓
(4.5) CROSS       교차 검증 — 슬롯 간 1:1 비교 (출석부 vs 사진)
        ↓
(5) CLARIFY       보완요청 생성 — 한국어 안내문 작성
        ↓
(6) JUDGE FINAL   최종 집계 — verdict + risk_level + why 산출
```

## 환경변수

| 변수명 | 설명 |
|--------|------|
| `OPENAI_API_KEY` | OpenAI API 키 |
| `OPENAI_MODEL_LIGHT` | 텍스트/데이터 분석 모델 (기본: gpt-4o-mini) |
| `OPENAI_MODEL_HEAVY` | Vision/최종판정 모델 (기본: gpt-5.1) |
| `CLOVA_INVOKE_URL` | Naver Clova OCR API URL |
| `CLOVA_OCR_SECRET` | Clova OCR Secret Key |
