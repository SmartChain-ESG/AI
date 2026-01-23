# TBM 안전 관리 시스템 설치 가이드

## 빠른 시작

### 1. 프로젝트 구조 확인

```
safety_api/
├── app/
│   └── main.py                  # FastAPI 서버
├── safety_modules/
│   ├── __init__.py
│   ├── person_detection.py      # 인원 수 감지
│   ├── helmet_detection.py      # 안전모 감지
│   └── speech_analysis.py       # 음성 분석
├── models/                      # 학습된 모델 저장 위치
├── tests/                       # 테스트 코드
├── docs/                        # 문서
├── requirements.txt
└── README.md
```

### 2. 환경 설정

#### Python 버전
- Python 3.8 이상 권장

#### 가상 환경 생성 (권장)

**Windows:**
```bash
cd apps/safety_api
python -m venv venv
venv\Scripts\activate
```

**Linux/Mac:**
```bash
cd apps/safety_api
python3 -m venv venv
source venv/bin/activate
```

### 3. 의존성 설치

#### CPU 버전 (기본)
```bash
pip install -r requirements.txt
```

#### GPU 버전 (CUDA 11.8)
```bash
# 먼저 requirements.txt의 torch 관련 부분을 주석 처리하고
pip install -r requirements.txt

# 그 다음 GPU 버전 torch 설치
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118
```

#### GPU 버전 (CUDA 12.1)
```bash
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
```

### 4. 모델 준비

#### 인원 수 감지 (자동 다운로드)
- YOLOv8n 모델이 첫 실행 시 자동으로 다운로드됩니다
- 별도 작업 불필요

#### 안전모 감지 (수동 준비 필요)

**옵션 1: 사전 학습된 모델 사용**
1. Roboflow에서 헬멧 감지 데이터셋 검색
2. 사전 학습된 모델 다운로드
3. `models/helmet_model.pt`에 저장

**옵션 2: 직접 학습**

```python
from ultralytics import YOLO

# YOLOv8n 모델 로드
model = YOLO('yolov8n.pt')

# 학습
model.train(
    data='helmet_dataset.yaml',  # 데이터셋 설정 파일
    epochs=100,
    imgsz=640,
    batch=16,
    name='helmet_detector'
)

# 학습된 모델을 models/ 디렉토리로 복사
# runs/detect/helmet_detector/weights/best.pt -> models/helmet_model.pt
```

**데이터셋 구조 (helmet_dataset.yaml):**
```yaml
path: ./helmet_dataset
train: images/train
val: images/val

nc: 2  # number of classes
names: ['helmet', 'no-helmet']
```

#### 음성 분석 (자동 다운로드)
- Whisper 모델이 첫 실행 시 자동으로 다운로드됩니다
- 기본: whisper-base (74MB)
- 고정확도 필요 시: whisper-small (244MB) 또는 whisper-medium (769MB)

### 5. 서버 실행

```bash
cd apps/safety_api/app
python main.py
```

또는:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

서버가 정상 실행되면:
- API: http://localhost:8000
- API 문서: http://localhost:8000/docs

### 6. 동작 확인

브라우저에서 http://localhost:8000 접속:

```json
{
  "message": "TBM Safety Management API",
  "version": "1.0.0",
  "status": "running",
  "models": {
    "person_detector": true,
    "helmet_detector": false,  // 모델 미설치 시 false
    "speech_analyzer": true
  }
}
```

### 7. 테스트 실행

```bash
# 전체 테스트
pytest

# 특정 모듈만 테스트
pytest tests/test_person_detection.py -v

# 모델 의존 테스트 제외
pytest -m "not requires_model"
```

## 문제 해결

### 문제 1: ImportError: No module named 'ultralytics'

**해결:**
```bash
pip install ultralytics
```

### 문제 2: CUDA out of memory

**해결:**
1. 더 작은 배치 사이즈 사용
2. 샘플링 간격 증가 (30 → 60)
3. 더 작은 모델 사용 (yolov8n)

### 문제 3: moviepy 오디오 추출 오류

**해결 (Windows):**
```bash
# ffmpeg 설치
# https://ffmpeg.org/download.html 에서 다운로드
# 환경 변수 PATH에 ffmpeg bin 디렉토리 추가
```

**해결 (Linux):**
```bash
sudo apt-get install ffmpeg
```

**해결 (Mac):**
```bash
brew install ffmpeg
```

### 문제 4: Whisper 모델 다운로드 느림

**해결:**
- 미리 다운로드:
```python
from transformers import WhisperProcessor, WhisperForConditionalGeneration

processor = WhisperProcessor.from_pretrained("openai/whisper-base")
model = WhisperForConditionalGeneration.from_pretrained("openai/whisper-base")
```

### 문제 5: GPU가 인식되지 않음

**확인:**
```python
import torch
print(torch.cuda.is_available())  # True여야 함
print(torch.cuda.get_device_name(0))  # GPU 이름 출력
```

**해결:**
- CUDA Toolkit 재설치
- PyTorch GPU 버전 재설치
- NVIDIA 드라이버 업데이트

## 개발 팁

### 개발 모드로 실행

```bash
uvicorn app.main:app --reload --log-level debug
```

### API 테스트 (curl)

```bash
# 인원 수 분석
curl -X POST "http://localhost:8000/analyze/person-count" \
  -F "file=@test_video.mp4"

# 헬스 체크
curl http://localhost:8000/health
```

### API 테스트 (Python)

```python
import requests

files = {'file': open('test_video.mp4', 'rb')}
response = requests.post(
    'http://localhost:8000/analyze/person-count',
    files=files
)
print(response.json())
```

### 로깅 설정

[main.py](app/main.py)에서 로그 레벨 조정:

```python
logging.basicConfig(
    level=logging.DEBUG,  # INFO, WARNING, ERROR
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
```

## 프로덕션 배포

### Docker 사용 (권장)

**Dockerfile 생성:**
```dockerfile
FROM python:3.9

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**빌드 및 실행:**
```bash
docker build -t tbm-safety-api .
docker run -p 8000:8000 tbm-safety-api
```

### Gunicorn 사용

```bash
pip install gunicorn

gunicorn app.main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000
```

### Nginx 리버스 프록시

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## 성능 최적화

### 1. 모델 최적화
- ONNX 변환으로 추론 속도 향상
- TensorRT 사용 (NVIDIA GPU)

### 2. 캐싱
- Redis를 사용한 결과 캐싱
- 동일 영상 재분석 방지

### 3. 비동기 처리
- Celery를 사용한 백그라운드 작업
- RabbitMQ 또는 Redis 큐

### 4. 데이터베이스
- 분석 결과를 PostgreSQL/MongoDB에 저장
- 이력 관리 및 통계 분석

## 다음 단계

1. [README.md](README.md) - 프로젝트 개요
2. [API.md](docs/API.md) - API 상세 문서
3. [MODULES.md](docs/MODULES.md) - 모듈 사용법

## 지원

문제가 발생하면:
1. 로그 확인
2. 테스트 실행
3. 이슈 트래커에 버그 리포트
