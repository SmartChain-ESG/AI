# out_risk_api - 외부 리스크 분석 [서브]

협력사명으로 GDELT/RSS 뉴스를 검색하고,
ESG 키워드 기반 감정 분석으로 외부 리스크 점수를 산출합니다.

## 엔드포인트

| Method | Path | 설명 |
|--------|------|------|
| `GET` | `/health` | 서버 상태 확인 |
| `POST` | `/risk/external/detect` | 협력사 리스트 → 외부 리스크 분석 |
| `POST` | `/risk/external/search/preview` | 검색 결과 미리보기 |

## 실행 방법

```bash
# 서버 실행 (포트 8002)
uvicorn app.main:app --reload --port 8002 --app-dir apps/out_risk_api

# Streamlit UI
streamlit run apps/out_risk_api/app/ui/streamlit_app.py
```

## 디렉토리 구조

```
app/
├── main.py                 # FastAPI 진입점
├── api/
│   └── risk.py             # 리스크 분석 엔드포인트
├── pipeline/
│   └── detect.py           # 검색 → 분석 → 점수화 파이프라인
├── search/
│   ├── provider.py         # GDELT API 검색
│   ├── rss.py              # Google RSS 검색
│   └── aliases.py          # 회사명 별칭 확장
├── analyze/
│   └── sentiment.py        # 감정 분석 (키워드 기반)
├── rag/
│   └── chroma.py           # ChromaDB 연동 (선택적 RAG)
├── schemas/
│   └── risk.py             # Pydantic 스키마
├── core/
│   └── config.py           # 환경변수 설정
└── ui/
    └── streamlit_app.py    # 테스트 UI
```

## 리스크 산출 방식

1. 협력사명으로 GDELT API / Google RSS 검색
2. ESG 키워드 필터링 (사고, 환경오염, 법적 분쟁 등)
3. 감정 분석으로 부정 문서 분류
4. 문서 발행일 기준 가중치 적용
   - 최근 30일: 1.5x
   - 90일: 1.0x
   - 180일: 0.7x
   - 그 외: 0.4x
5. 총점 기반 리스크 레벨 산출
   - HIGH: ≥10점
   - MEDIUM: ≥5점
   - LOW: <5점

## 환경변수

| 변수명 | 설명 |
|--------|------|
| `OPENAI_API_KEY` | OpenAI API 키 |
| `OPENAI_MODEL_LIGHT` | LLM 모델 (기본: gpt-4o-mini) |
| `OUT_RISK_CHROMA_PATH` | ChromaDB 저장 경로 (기본: apps/out_risk_api/app/vectordb) |
| `OUT_RISK_CHROMA_COLLECTION` | ChromaDB 컬렉션명 (기본: out_risk) |
| `OUT_RISK_RAG_TOP_K_DEFAULT` | RAG 검색 상위 문서 개수 (기본: 6) |
| `OUT_RISK_RAG_CHUNK_SIZE_DEFAULT` | 문서 청크 크기 (기본: 800) |
