# TBM Safety Management System

TBM (Tool Box Meeting) 안전 관리 시스템은 작업 현장의 안전 교육 영상을 분석하여 안전 준수 여부를 자동으로 판단하는 AI 기반 시스템입니다.

## 주요 기능

1. **인원 수 감지** (Person Detection)
   - YOLOv8 기반 객체 인식을 통한 인원 수 자동 카운팅
   - 영상 전체에 걸친 평균/최대/최소 인원 수 분석

2. **안전모 착용 감지** (Helmet Detection)
   - 커스텀 학습된 YOLOv8 모델을 통한 안전모 착용 여부 판별
   - 안전모 착용률 계산 및 준수 여부 판단

3. **안전 스크립트 분석** (Speech Analysis)
   - Whisper 기반 STT를 통한 음성 텍스트 변환
   - 필수 안전 키워드 포함 여부 확인
   - 안전 교육 스크립트 준수율 계산

## 프로젝트 구조

```
safety_api/
├── app/
│   └── main.py                  # FastAPI 애플리케이션
├── safety_modules/
│   ├── __init__.py
│   ├── person_detection.py      # 인원 수 감지 모듈
│   ├── helmet_detection.py      # 안전모 감지 모듈
│   └── speech_analysis.py       # 음성 분석 모듈
├── models/
│   └── helmet_model.pt          # 학습된 안전모 감지 모델 (별도 준비 필요)
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_person_detection.py
│   ├── test_helmet_detection.py
│   ├── test_speech_analysis.py
│   └── test_api.py
├── docs/
│   ├── API.md                   # API 문서
│   └── MODULES.md               # 모듈 설명 문서
├── requirements.txt
├── pytest.ini
└── README.md
```

## 설치 방법

### 1. 의존성 설치

```bash
cd apps/safety_api
pip install -r requirements.txt
```

### 2. GPU 지원 (선택사항)

CUDA를 사용하는 경우:
```bash
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118
```

### 3. 모델 준비

#### 인원 수 감지
- YOLOv8n 기본 모델 자동 다운로드 (첫 실행 시)

#### 안전모 감지
- 커스텀 학습 모델 필요
- `models/helmet_model.pt` 경로에 배치
- 학습 데이터셋 예시: [Roboflow Helmet Detection](https://universe.roboflow.com/search?q=helmet)

#### 음성 분석
- Whisper 모델 자동 다운로드 (첫 실행 시)

## 실행 방법

### API 서버 시작

```bash
cd apps/safety_api/app
python main.py
```

또는 uvicorn 직접 실행:
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

서버가 시작되면 다음 주소에서 접근 가능:
- API: http://localhost:8000
- API 문서 (Swagger): http://localhost:8000/docs
- API 문서 (ReDoc): http://localhost:8000/redoc

## API 사용 예시

### 1. 인원 수 분석

```bash
curl -X POST "http://localhost:8000/analyze/person-count" \
  -F "file=@video.mp4" \
  -F "sample_interval=30"
```

### 2. 안전모 착용 분석

```bash
curl -X POST "http://localhost:8000/analyze/helmet-compliance" \
  -F "file=@video.mp4" \
  -F "sample_interval=30" \
  -F "required_compliance=100.0"
```

### 3. 음성 안전 스크립트 분석

```bash
curl -X POST "http://localhost:8000/analyze/speech-compliance" \
  -F "file=@video.mp4" \
  -F "min_coverage=80.0"
```

### 4. 전체 분석

```bash
curl -X POST "http://localhost:8000/analyze/full" \
  -F "file=@video.mp4"
```

## 테스트 실행

```bash
# 전체 테스트 실행
pytest

# 특정 테스트 파일 실행
pytest tests/test_person_detection.py

# 느린 테스트 제외
pytest -m "not slow"

# 모델이 필요한 테스트 제외
pytest -m "not requires_model"
```

## 모듈 사용 예시

### PersonDetector

```python
from safety_modules.person_detection import PersonDetector
import cv2

detector = PersonDetector(confidence_threshold=0.5)

# 이미지에서 인원 수 감지
image = cv2.imread("image.jpg")
count = detector.count_persons(image)
print(f"Detected {count} persons")

# 영상 분석
result = detector.process_video("video.mp4", sample_interval=30)
print(f"Average person count: {result['average_count']}")
```

### HelmetDetector

```python
from safety_modules.helmet_detection import HelmetDetector
import cv2

detector = HelmetDetector(model_path="models/helmet_model.pt")

# 안전모 착용 검사
image = cv2.imread("image.jpg")
result = detector.detect_helmets(image)
print(f"Compliance rate: {result['helmet_compliance_rate']:.1f}%")

# 영상 분석
video_result = detector.process_video("video.mp4")
print(f"Overall pass: {video_result['overall_pass']}")
```

### SpeechAnalyzer

```python
from safety_modules.speech_analysis import SpeechAnalyzer

analyzer = SpeechAnalyzer(language="ko")

# 영상의 음성 분석
result = analyzer.analyze_video("video.mp4", min_coverage=80.0)
print(f"Transcription: {result['transcription']}")
print(f"Keyword coverage: {result['keyword_analysis']['keyword_coverage']:.1f}%")
print(f"Compliant: {result['compliant']}")
```

## 커스터마이즈

### 안전 키워드 설정

```python
custom_keywords = ["안전", "작업", "확인", "주의", "점검"]
analyzer = SpeechAnalyzer(required_keywords=custom_keywords)
```

### 신뢰도 임계값 조정

```python
# 낮은 임계값 = 더 많은 검출, 잠재적 오탐 증가
detector = PersonDetector(confidence_threshold=0.3)

# 높은 임계값 = 더 정확한 검출, 일부 누락 가능
detector = PersonDetector(confidence_threshold=0.7)
```

## 문제 해결

### GPU 메모리 부족
- 더 작은 모델 사용 (yolov8n 대신 yolov8s)
- 배치 크기 감소
- 샘플링 간격 증가

### 느린 처리 속도
- GPU 사용 확인
- 샘플링 간격 증가 (30 → 60)
- 더 작은 모델 사용

### 안전모 감지 정확도 낮음
- 더 많은 데이터로 모델 재학습
- 신뢰도 임계값 조정
- 작업 현장 특성에 맞는 데이터 수집

## 라이선스

이 프로젝트는 MIT 라이선스 하에 배포됩니다.

## 기여

버그 리포트나 기능 제안은 이슈 트래커를 통해 제출해주세요.
