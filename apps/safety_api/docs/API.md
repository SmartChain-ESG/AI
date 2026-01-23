# API 문서

TBM Safety Management System API 상세 문서

## 기본 정보

- **Base URL**: `http://localhost:8000`
- **Content-Type**: `multipart/form-data` (파일 업로드)
- **Response Format**: JSON

## 엔드포인트

### 1. Root

**GET** `/`

시스템 상태 및 버전 정보 반환

**Response:**
```json
{
  "message": "TBM Safety Management API",
  "version": "1.0.0",
  "status": "running",
  "models": {
    "person_detector": true,
    "helmet_detector": true,
    "speech_analyzer": true
  }
}
```

---

### 2. Health Check

**GET** `/health`

서버 및 모델 상태 확인

**Response:**
```json
{
  "status": "healthy",
  "models_loaded": {
    "person_detector": true,
    "helmet_detector": true,
    "speech_analyzer": true
  }
}
```

---

### 3. Person Count Analysis

**POST** `/analyze/person-count`

영상에서 인원 수 감지 및 분석

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| file | File | Yes | 분석할 영상 파일 (mp4, avi 등) |
| sample_interval | int | No | 프레임 샘플링 간격 (기본값: 30) |

**Request Example:**
```bash
curl -X POST "http://localhost:8000/analyze/person-count" \
  -F "file=@tbm_video.mp4" \
  -F "sample_interval=30"
```

**Response:**
```json
{
  "video_filename": "tbm_video.mp4",
  "total_frames": 3000,
  "sampled_frames": 100,
  "detections_per_frame": [5, 5, 6, 5, 5, ...],
  "average_count": 5.2,
  "max_count": 7,
  "min_count": 4
}
```

---

### 4. Helmet Compliance Analysis

**POST** `/analyze/helmet-compliance`

안전모 착용 여부 분석

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| file | File | Yes | 분석할 영상 파일 |
| sample_interval | int | No | 프레임 샘플링 간격 (기본값: 30) |
| required_compliance | float | No | 요구되는 준수율 0-100 (기본값: 100.0) |

**Request Example:**
```bash
curl -X POST "http://localhost:8000/analyze/helmet-compliance" \
  -F "file=@tbm_video.mp4" \
  -F "sample_interval=30" \
  -F "required_compliance=100.0"
```

**Response:**
```json
{
  "video_filename": "tbm_video.mp4",
  "total_frames": 3000,
  "sampled_frames": 100,
  "compliance_per_frame": [100.0, 100.0, 80.0, 100.0, ...],
  "average_compliance": 95.5,
  "min_compliance": 80.0,
  "max_compliance": 100.0,
  "overall_pass": false,
  "violations": [
    {
      "frame_number": 60,
      "compliance_rate": 80.0,
      "helmet_count": 4,
      "no_helmet_count": 1
    }
  ]
}
```

---

### 5. Speech Compliance Analysis

**POST** `/analyze/speech-compliance`

음성 인식을 통한 안전 스크립트 준수 여부 분석

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| file | File | Yes | 분석할 영상 파일 |
| min_coverage | float | No | 최소 키워드 포함률 0-100 (기본값: 80.0) |
| custom_keywords | List[str] | No | 커스텀 안전 키워드 목록 |

**Request Example:**
```bash
curl -X POST "http://localhost:8000/analyze/speech-compliance" \
  -F "file=@tbm_video.mp4" \
  -F "min_coverage=80.0"
```

**Response:**
```json
{
  "video_filename": "tbm_video.mp4",
  "transcription": "오늘 작업 전 안전 교육을 시작하겠습니다. 작업 시 주의해야 할 사항은...",
  "keyword_analysis": {
    "found_keywords": ["안전", "작업", "주의", "확인"],
    "missing_keywords": ["위험"],
    "keyword_coverage": 80.0,
    "compliant": true,
    "total_keywords": 5,
    "found_count": 4
  },
  "compliant": true,
  "audio_path": "/tmp/audio_xyz.wav",
  "min_coverage_required": 80.0
}
```

---

### 6. Full Analysis

**POST** `/analyze/full`

전체 안전 분석 (인원, 안전모, 음성 통합)

**Request Body (JSON):**
```json
{
  "sample_interval": 30,
  "person_confidence": 0.5,
  "helmet_confidence": 0.5,
  "required_helmet_compliance": 100.0,
  "required_keyword_coverage": 80.0,
  "custom_keywords": ["안전", "작업", "주의"]
}
```

**Request Example:**
```bash
curl -X POST "http://localhost:8000/analyze/full" \
  -F "file=@tbm_video.mp4" \
  -F 'config={"sample_interval": 30, "required_helmet_compliance": 100.0}'
```

**Response:**
```json
{
  "video_filename": "tbm_video.mp4",
  "person_detection": {
    "total_frames": 3000,
    "sampled_frames": 100,
    "average_count": 5.2,
    "max_count": 7,
    "min_count": 4
  },
  "helmet_detection": {
    "total_frames": 3000,
    "sampled_frames": 100,
    "average_compliance": 98.5,
    "overall_pass": false,
    "violations": [...]
  },
  "speech_analysis": {
    "transcription": "...",
    "keyword_analysis": {...},
    "compliant": true
  },
  "overall_compliance": false,
  "compliance_summary": {
    "helmet_compliance": 98.5,
    "speech_compliance": 80.0,
    "helmet_pass": false,
    "speech_pass": true,
    "overall_pass": false
  }
}
```

---

## 에러 코드

| Status Code | Description |
|-------------|-------------|
| 200 | 성공 |
| 422 | 잘못된 요청 파라미터 |
| 500 | 서버 내부 오류 (분석 실패) |
| 503 | 모델 초기화 안됨 |

## 에러 응답 예시

```json
{
  "detail": "Analysis failed: Could not open video file"
}
```

## 사용 제한

- 최대 파일 크기: 제한 없음 (서버 설정에 따라 다름)
- 지원 형식: MP4, AVI, MOV 등 OpenCV 지원 형식
- 처리 시간: 영상 길이와 샘플링 간격에 따라 다름

## Python 클라이언트 예시

```python
import requests

# 파일 업로드
files = {'file': open('tbm_video.mp4', 'rb')}
data = {'sample_interval': 30}

response = requests.post(
    'http://localhost:8000/analyze/person-count',
    files=files,
    data=data
)

result = response.json()
print(f"Average person count: {result['average_count']}")
```

## JavaScript 클라이언트 예시

```javascript
const formData = new FormData();
formData.append('file', fileInput.files[0]);
formData.append('sample_interval', 30);

fetch('http://localhost:8000/analyze/person-count', {
  method: 'POST',
  body: formData
})
.then(response => response.json())
.then(data => {
  console.log('Average person count:', data.average_count);
});
```
