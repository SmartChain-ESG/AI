# 함수 이름은 각 도메인 명으로 시작할 것. 
# preview / submit으로 나뉨

app/
├── main.py                          # FastAPI 진입점
├── core/
│   ├── config.py                    # 환경변수
│   └── errors.py                    # HTTP 예외
├── api/
│   └── run.py                       # POST /run/preview, /run/submit
├── schemas/
│   └── run.py                       # 기획서 §3 기준 스키마
├── pipeline/
│   ├── preview.py                   # §4.1 Preview 파이프라인
│   ├── triage.py                    # §4.2 Phase 1: 파일 분류
│   └── submit.py                    # §4.2 Phase 1~6 전체 Submit
├── engines/
│   ├── registry.py                  # 도메인 디스패치
│   ├── safety/  (slots.py, rules.py)
│   ├── compliance/  (slots.py, rules.py)
│   └── esg/  (slots.py, rules.py)
├── extractors/
│   ├── pdf_text.py                  # PDF 추출 + 조건부 OCR
│   ├── xlsx.py                      # 엑셀/CSV 파싱
│   └── ocr/
│       ├── clova_client.py          # Clova OCR
│       └── ocr_router.py           # 이미지 OCR
├── llm/
│   ├── client.py                    # GPT-4o-mini / GPT-4o
│   └── prompts.py                   # 프롬프트 모음
├── storage/
│   ├── downloader.py                # SAS URL 다운로드
│   └── tmp_store.py                 # 인메모리 패키지 누적 저장
└── db/                              # (추후 PostgreSQL)