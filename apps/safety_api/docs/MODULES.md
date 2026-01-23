# 모듈 설명서

TBM Safety Management System의 각 분석 모듈에 대한 상세 설명

## 목차

1. [PersonDetector](#persondetector)
2. [HelmetDetector](#helmetdetector)
3. [SpeechAnalyzer](#speechanalyzer)

---

## PersonDetector

인원 수 감지 모듈 - YOLOv8을 사용하여 영상에서 사람을 감지하고 카운팅합니다.

### 주요 기능

- 실시간 인원 수 감지
- 영상 전체 분석 및 통계 제공
- 바운딩 박스 시각화

### 클래스 초기화

```python
PersonDetector(
    model_path: Optional[str] = None,
    confidence_threshold: float = 0.5
)
```

**Parameters:**
- `model_path`: 커스텀 모델 경로 (None이면 기본 YOLOv8n 사용)
- `confidence_threshold`: 감지 신뢰도 임계값 (0.0~1.0)

### 주요 메서드

#### `detect_persons(image: np.ndarray) -> List[Dict]`

단일 이미지에서 사람 감지

**Returns:**
```python
[
    {
        'bbox': [x1, y1, x2, y2],
        'confidence': 0.95,
        'class_id': 0
    },
    ...
]
```

#### `count_persons(image: np.ndarray) -> int`

이미지에서 감지된 인원 수 반환

#### `process_video(video_path: str, sample_interval: int = 30) -> Dict`

영상 전체 분석

**Returns:**
```python
{
    'total_frames': 3000,
    'sampled_frames': 100,
    'detections_per_frame': [5, 5, 6, ...],
    'average_count': 5.2,
    'max_count': 7,
    'min_count': 4
}
```

#### `draw_detections(image: np.ndarray, detections: List[Dict]) -> np.ndarray`

감지 결과를 이미지에 시각화

### 사용 예시

```python
from safety_modules.person_detection import PersonDetector
import cv2

# 초기화
detector = PersonDetector(confidence_threshold=0.5)

# 이미지 분석
image = cv2.imread("frame.jpg")
detections = detector.detect_persons(image)
count = detector.count_persons(image)

print(f"Detected {count} persons")

# 시각화
result_img = detector.draw_detections(image, detections)
cv2.imwrite("result.jpg", result_img)

# 영상 분석
video_result = detector.process_video("video.mp4", sample_interval=30)
print(f"Average: {video_result['average_count']:.1f} persons")
print(f"Max: {video_result['max_count']} persons")
```

### 성능 최적화

1. **샘플링 간격 조정**: 높은 값(60, 90)으로 설정하면 처리 속도 향상
2. **신뢰도 임계값**: 0.5~0.7 권장 (낮으면 오탐 증가, 높으면 누락 증가)
3. **GPU 사용**: CUDA 사용 시 자동으로 GPU 활용

---

## HelmetDetector

안전모 착용 감지 모듈 - 커스텀 학습된 YOLOv8 모델로 안전모 착용 여부를 판별합니다.

### 주요 기능

- 안전모 착용자 감지
- 미착용자 감지
- 착용률 계산 및 준수 여부 판단

### 클래스 초기화

```python
HelmetDetector(
    model_path: Optional[str] = None,
    confidence_threshold: float = 0.5
)
```

**Parameters:**
- `model_path`: 학습된 안전모 감지 모델 경로 (필수)
- `confidence_threshold`: 감지 신뢰도 임계값 (0.0~1.0)

### 클래스 매핑

```python
{
    0: 'helmet',       # 안전모 착용
    1: 'no-helmet',    # 안전모 미착용
    2: 'person'        # 사람 (선택사항)
}
```

### 주요 메서드

#### `detect_helmets(image: np.ndarray) -> Dict`

이미지에서 안전모 착용 여부 감지

**Returns:**
```python
{
    'helmets': [...],              # 안전모 착용자 목록
    'no_helmets': [...],           # 미착용자 목록
    'helmet_count': 4,
    'no_helmet_count': 1,
    'total_persons': 5,
    'helmet_compliance_rate': 80.0  # 착용률 (%)
}
```

#### `check_compliance(image: np.ndarray, required_rate: float = 100.0) -> bool`

준수율 확인

#### `process_video(video_path: str, sample_interval: int = 30, required_compliance: float = 100.0) -> Dict`

영상 분석 및 위반 사항 추적

**Returns:**
```python
{
    'total_frames': 3000,
    'sampled_frames': 100,
    'compliance_per_frame': [100.0, 100.0, 80.0, ...],
    'average_compliance': 95.5,
    'min_compliance': 80.0,
    'max_compliance': 100.0,
    'overall_pass': False,
    'violations': [
        {
            'frame_number': 60,
            'compliance_rate': 80.0,
            'helmet_count': 4,
            'no_helmet_count': 1
        }
    ]
}
```

### 사용 예시

```python
from safety_modules.helmet_detection import HelmetDetector
import cv2

# 초기화 (학습된 모델 필요)
detector = HelmetDetector(
    model_path="models/helmet_model.pt",
    confidence_threshold=0.6
)

# 이미지 분석
image = cv2.imread("worksite.jpg")
result = detector.detect_helmets(image)

print(f"Compliance: {result['helmet_compliance_rate']:.1f}%")
print(f"Helmets: {result['helmet_count']}, No helmets: {result['no_helmet_count']}")

# 준수 여부 확인
compliant = detector.check_compliance(image, required_rate=100.0)
print(f"Fully compliant: {compliant}")

# 영상 분석
video_result = detector.process_video("tbm.mp4", required_compliance=100.0)
print(f"Overall pass: {video_result['overall_pass']}")
print(f"Violations: {len(video_result['violations'])}")
```

### 모델 학습

안전모 감지 모델을 학습하려면:

1. **데이터셋 수집**
   - 안전모 착용/미착용 이미지 수집
   - 최소 500~1000장 권장
   - [Roboflow](https://universe.roboflow.com/search?q=helmet) 데이터셋 활용 가능

2. **라벨링**
   - 클래스: helmet, no-helmet
   - 바운딩 박스 주석 작업

3. **학습**
```python
from ultralytics import YOLO

model = YOLO('yolov8n.pt')
model.train(
    data='helmet_dataset.yaml',
    epochs=100,
    imgsz=640,
    batch=16
)
```

---

## SpeechAnalyzer

음성 분석 모듈 - Whisper STT를 사용하여 안전 스크립트 준수 여부를 판단합니다.

### 주요 기능

- 영상에서 오디오 추출
- 음성을 텍스트로 변환 (STT)
- 안전 키워드 포함 여부 확인
- 준수율 계산

### 클래스 초기화

```python
SpeechAnalyzer(
    stt_model: str = "openai/whisper-base",
    required_keywords: Optional[List[str]] = None,
    language: str = "ko"
)
```

**Parameters:**
- `stt_model`: Whisper 모델 (base, small, medium, large)
- `required_keywords`: 필수 안전 키워드 목록
- `language`: 음성 언어 코드 (ko: 한국어, en: 영어)

### 기본 안전 키워드 (한국어)

```python
[
    "안전",   # safety
    "주의",   # caution
    "확인",   # check
    "작업",   # work
    "위험",   # danger/hazard
]
```

### 주요 메서드

#### `extract_audio(video_path: str, output_path: Optional[str] = None) -> str`

영상에서 오디오 추출

**Returns:** 추출된 오디오 파일 경로 (.wav)

#### `transcribe_audio(audio_path: str) -> str`

오디오를 텍스트로 변환

**Returns:** 변환된 텍스트

#### `check_keywords(text: str, keywords: Optional[List[str]] = None) -> Dict`

텍스트에서 키워드 확인

**Returns:**
```python
{
    'found_keywords': ['안전', '작업', '주의'],
    'missing_keywords': ['위험', '확인'],
    'keyword_coverage': 60.0,  # 60%
    'compliant': False,
    'total_keywords': 5,
    'found_count': 3
}
```

#### `analyze_video(video_path: str, keywords: Optional[List[str]] = None, min_coverage: float = 80.0) -> Dict`

영상 전체 음성 분석

**Returns:**
```python
{
    'transcription': '전체 변환된 텍스트...',
    'keyword_analysis': {...},
    'compliant': True,
    'audio_path': '/tmp/audio.wav',
    'min_coverage_required': 80.0
}
```

### 사용 예시

```python
from safety_modules.speech_analysis import SpeechAnalyzer

# 기본 초기화
analyzer = SpeechAnalyzer(language="ko")

# 커스텀 키워드 설정
custom_keywords = ["안전", "보호구", "점검", "확인", "주의"]
analyzer = SpeechAnalyzer(
    required_keywords=custom_keywords,
    language="ko"
)

# 영상 분석
result = analyzer.analyze_video("tbm.mp4", min_coverage=80.0)

print("Transcription:")
print(result['transcription'])
print(f"\nKeyword coverage: {result['keyword_analysis']['keyword_coverage']:.1f}%")
print(f"Found: {result['keyword_analysis']['found_keywords']}")
print(f"Missing: {result['keyword_analysis']['missing_keywords']}")
print(f"Compliant: {result['compliant']}")

# 오디오 추출 및 개별 분석
audio_path = analyzer.extract_audio("video.mp4")
transcription = analyzer.transcribe_audio(audio_path)
keyword_result = analyzer.check_keywords(transcription)
```

### 모델 선택 가이드

| 모델 | 크기 | 속도 | 정확도 | 권장 용도 |
|------|------|------|--------|----------|
| tiny | 39M | 매우 빠름 | 낮음 | 테스트용 |
| base | 74M | 빠름 | 보통 | 일반 사용 |
| small | 244M | 보통 | 좋음 | 권장 |
| medium | 769M | 느림 | 매우 좋음 | 고정확도 필요 시 |
| large | 1550M | 매우 느림 | 최고 | 전문적 용도 |

### 성능 최적화

1. **모델 크기**: small 또는 base 권장 (정확도와 속도 균형)
2. **GPU 사용**: CUDA 사용 시 자동으로 GPU 활용
3. **오디오 품질**: 16kHz 샘플레이트로 자동 변환
4. **키워드 설정**: 너무 많은 키워드는 준수율 저하

### 한계점 및 주의사항

1. **배경 소음**: 시끄러운 환경에서 정확도 저하
2. **발음**: 명확한 발음이 중요
3. **방언**: 표준어 기준으로 학습됨
4. **처리 시간**: 영상 길이에 비례하여 증가

---

## 통합 사용 예시

세 모듈을 함께 사용하는 완전한 분석 시스템:

```python
from safety_modules import PersonDetector, HelmetDetector, SpeechAnalyzer
import cv2

# 모듈 초기화
person_detector = PersonDetector()
helmet_detector = HelmetDetector(model_path="models/helmet_model.pt")
speech_analyzer = SpeechAnalyzer(language="ko")

# 영상 분석
video_path = "tbm_meeting.mp4"

# 1. 인원 수 분석
person_result = person_detector.process_video(video_path)
print(f"Average persons: {person_result['average_count']:.1f}")

# 2. 안전모 착용 분석
helmet_result = helmet_detector.process_video(video_path)
print(f"Helmet compliance: {helmet_result['average_compliance']:.1f}%")

# 3. 음성 스크립트 분석
speech_result = speech_analyzer.analyze_video(video_path, min_coverage=80.0)
print(f"Speech compliance: {speech_result['keyword_analysis']['keyword_coverage']:.1f}%")

# 종합 판정
overall_pass = (
    helmet_result['overall_pass'] and
    speech_result['compliant']
)

print(f"\n=== Overall Result ===")
print(f"Pass: {overall_pass}")
```
