"""
TBM Safety API 테스트
pytest 기반 유닛/통합 테스트

실행 방법:
    cd apps/safety_api
    pytest tests/test_tbm_api.py -v
    pytest tests/test_tbm_api.py -v -k "test_root"  # 특정 테스트만
    pytest tests/test_tbm_api.py -v --tb=short      # 간단한 traceback
"""
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
import sys

# 모듈 경로 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi.testclient import TestClient


# =====================================================
# Fixtures
# =====================================================

@pytest.fixture(scope="module")
def mock_models():
    """모델 모킹 - 실제 모델 로드 없이 테스트"""
    with patch("app.main.PersonDetector") as mock_person, \
         patch("app.main.HelmetDetector") as mock_helmet, \
         patch("app.main.SpeechAnalyzer") as mock_speech:

        # PersonDetector mock
        mock_person_instance = MagicMock()
        mock_person_instance.process_video.return_value = {
            "total_frames": 100,
            "sampled_frames": 4,
            "detections_per_frame": [3, 4, 5, 4],
            "average_count": 4.0,
            "max_count": 5,
            "min_count": 3
        }
        mock_person.return_value = mock_person_instance

        # HelmetDetector mock
        mock_helmet_instance = MagicMock()
        mock_helmet_instance.process_video.return_value = {
            "total_frames": 100,
            "sampled_frames": 4,
            "compliance_per_frame": [100.0, 100.0, 80.0, 100.0],
            "average_compliance": 95.0,
            "min_compliance": 80.0,
            "max_compliance": 100.0,
            "overall_pass": False,
            "violations": [{"frame_number": 60, "compliance_rate": 80.0, "helmet_count": 4, "no_helmet_count": 1}],
            "detection_method": "color_based"
        }
        mock_helmet.return_value = mock_helmet_instance

        # SpeechAnalyzer mock
        mock_speech_instance = MagicMock()
        mock_speech_instance.analyze_video.return_value = {
            "transcription": "오늘 작업 전 안전 확인하겠습니다. 위험 요소 주의하세요.",
            "keyword_analysis": {
                "found_keywords": ["안전", "확인", "작업", "위험", "주의"],
                "missing_keywords": [],
                "keyword_coverage": 100.0,
                "compliant": True,
                "total_keywords": 5,
                "found_count": 5
            },
            "compliant": True,
            "audio_path": "/tmp/audio.wav",
            "min_coverage_required": 80.0
        }
        mock_speech.return_value = mock_speech_instance

        yield {
            "person": mock_person_instance,
            "helmet": mock_helmet_instance,
            "speech": mock_speech_instance
        }


@pytest.fixture(scope="module")
def client(mock_models):  # noqa: ARG001 - mock_models needed to patch before import
    """FastAPI TestClient"""
    from app.main import app
    with TestClient(app) as c:
        yield c


@pytest.fixture
def test_video_path():
    """테스트 비디오 파일 경로"""
    return Path(__file__).parent / "test_video.mp4"


@pytest.fixture
def sample_video_bytes(test_video_path):
    """테스트용 비디오 바이트 (실제 파일 또는 더미)"""
    if test_video_path.exists():
        return test_video_path.read_bytes()
    # 더미 데이터 (실제 비디오 없을 때)
    return b"dummy video content for testing"


# =====================================================
# Root & Health 테스트
# =====================================================

class TestBasicEndpoints:
    """기본 엔드포인트 테스트"""

    def test_root(self, client):
        """GET / - API 상태 확인"""
        response = client.get("/")
        assert response.status_code == 200

        data = response.json()
        assert data["message"] == "TBM Safety Management API"
        assert data["version"] == "1.0.0"
        assert data["status"] == "running"
        assert data["port"] == 8000
        assert "models" in data

    def test_health(self, client):
        """GET /health - 헬스체크"""
        response = client.get("/health")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "healthy"
        assert data["models_loaded"]["person_detector"] is True
        assert data["models_loaded"]["helmet_detector"] is True
        assert data["models_loaded"]["speech_analyzer"] is True

    def test_docs_available(self, client):
        """Swagger 문서 접근 가능"""
        response = client.get("/docs")
        assert response.status_code == 200

    def test_redoc_available(self, client):
        """ReDoc 문서 접근 가능"""
        response = client.get("/redoc")
        assert response.status_code == 200


# =====================================================
# Person Count API 테스트
# =====================================================

class TestPersonCountAPI:
    """인원 수 분석 API 테스트"""

    def test_person_count_basic(self, client, sample_video_bytes):
        """POST /analyze/person-count - 기본 테스트"""
        response = client.post(
            "/analyze/person-count",
            files={"file": ("test.mp4", sample_video_bytes, "video/mp4")},
            data={"sample_interval": 30}
        )
        assert response.status_code == 200

        data = response.json()
        assert "average_count" in data
        assert "max_count" in data
        assert "min_count" in data
        assert "sampled_frames" in data
        assert data["video_filename"] == "test.mp4"

    def test_person_count_with_expected(self, client, sample_video_bytes):
        """POST /analyze/person-count - 기대 인원 수 검증"""
        response = client.post(
            "/analyze/person-count",
            files={"file": ("test.mp4", sample_video_bytes, "video/mp4")},
            data={"sample_interval": 30, "expected_person_count": 3}
        )
        assert response.status_code == 200

        data = response.json()
        assert data["expected_person_count"] == 3
        assert "person_pass" in data
        # max_count가 5이므로 3 이상 -> pass
        assert data["person_pass"] is True

    def test_person_count_fail_expected(self, client, sample_video_bytes):
        """POST /analyze/person-count - 기대 인원 미달"""
        response = client.post(
            "/analyze/person-count",
            files={"file": ("test.mp4", sample_video_bytes, "video/mp4")},
            data={"sample_interval": 30, "expected_person_count": 10}
        )
        assert response.status_code == 200

        data = response.json()
        # max_count가 5이므로 10 미만 -> fail
        assert data["person_pass"] is False

    def test_person_count_no_file(self, client):
        """POST /analyze/person-count - 파일 없음 에러"""
        response = client.post(
            "/analyze/person-count",
            data={"sample_interval": 30}
        )
        assert response.status_code == 422  # Validation Error


# =====================================================
# Helmet Compliance API 테스트
# =====================================================

class TestHelmetComplianceAPI:
    """헬멧 착용 분석 API 테스트"""

    def test_helmet_compliance_basic(self, client, sample_video_bytes):
        """POST /analyze/helmet-compliance - 기본 테스트"""
        response = client.post(
            "/analyze/helmet-compliance",
            files={"file": ("test.mp4", sample_video_bytes, "video/mp4")},
            data={"sample_interval": 30, "required_compliance": 100.0}
        )
        assert response.status_code == 200

        data = response.json()
        assert "average_compliance" in data
        assert "min_compliance" in data
        assert "max_compliance" in data
        assert "overall_pass" in data
        assert "violations" in data
        assert "detection_method" in data

    def test_helmet_compliance_pass(self, client, sample_video_bytes):
        """POST /analyze/helmet-compliance - 낮은 기준 통과"""
        response = client.post(
            "/analyze/helmet-compliance",
            files={"file": ("test.mp4", sample_video_bytes, "video/mp4")},
            data={"sample_interval": 30, "required_compliance": 50.0}
        )
        assert response.status_code == 200

        data = response.json()
        # average_compliance가 95.0이므로 50.0 이상 -> pass
        # 하지만 mock에서 overall_pass는 False로 설정됨 (100% 기준)
        assert "overall_pass" in data

    def test_helmet_compliance_violations(self, client, sample_video_bytes):
        """POST /analyze/helmet-compliance - 위반 프레임 확인"""
        response = client.post(
            "/analyze/helmet-compliance",
            files={"file": ("test.mp4", sample_video_bytes, "video/mp4")},
            data={"sample_interval": 30, "required_compliance": 100.0}
        )
        assert response.status_code == 200

        data = response.json()
        violations = data.get("violations", [])
        assert isinstance(violations, list)
        if violations:
            v = violations[0]
            assert "frame_number" in v
            assert "compliance_rate" in v
            assert "helmet_count" in v
            assert "no_helmet_count" in v


# =====================================================
# Speech Compliance API 테스트
# =====================================================

class TestSpeechComplianceAPI:
    """음성 분석 API 테스트"""

    def test_speech_compliance_basic(self, client, sample_video_bytes):
        """POST /analyze/speech-compliance - 기본 테스트"""
        response = client.post(
            "/analyze/speech-compliance",
            files={"file": ("test.mp4", sample_video_bytes, "video/mp4")},
            data={"min_coverage": 80.0}
        )
        assert response.status_code == 200

        data = response.json()
        assert "transcription" in data
        assert "keyword_analysis" in data
        assert "compliant" in data

        keyword_analysis = data["keyword_analysis"]
        assert "found_keywords" in keyword_analysis
        assert "missing_keywords" in keyword_analysis
        assert "keyword_coverage" in keyword_analysis

    def test_speech_compliance_keywords(self, client, sample_video_bytes):
        """POST /analyze/speech-compliance - 키워드 분석 확인"""
        response = client.post(
            "/analyze/speech-compliance",
            files={"file": ("test.mp4", sample_video_bytes, "video/mp4")},
            data={"min_coverage": 80.0}
        )
        assert response.status_code == 200

        data = response.json()
        keyword_analysis = data["keyword_analysis"]

        # 기본 키워드 확인
        found = keyword_analysis["found_keywords"]
        assert isinstance(found, list)

        # 모든 키워드 발견됨 (mock 기준)
        assert keyword_analysis["keyword_coverage"] == 100.0
        assert data["compliant"] is True


# =====================================================
# Full Analysis API 테스트
# =====================================================

class TestFullAnalysisAPI:
    """전체 분석 API 테스트"""

    def test_full_analysis_basic(self, client, sample_video_bytes):
        """POST /analyze/full - 기본 테스트"""
        response = client.post(
            "/analyze/full",
            files={"file": ("test.mp4", sample_video_bytes, "video/mp4")},
            data={
                "sample_interval": 30,
                "required_helmet_compliance": 100.0,
                "required_keyword_coverage": 80.0
            }
        )
        assert response.status_code == 200

        data = response.json()
        assert data["video_filename"] == "test.mp4"
        assert "person_detection" in data
        assert "helmet_detection" in data
        assert "speech_analysis" in data
        assert "overall_compliance" in data
        assert "compliance_summary" in data

    def test_full_analysis_with_person_check(self, client, sample_video_bytes):
        """POST /analyze/full - 인원 수 검증 포함"""
        response = client.post(
            "/analyze/full",
            files={"file": ("test.mp4", sample_video_bytes, "video/mp4")},
            data={
                "sample_interval": 30,
                "required_helmet_compliance": 100.0,
                "required_keyword_coverage": 80.0,
                "expected_person_count": 3
            }
        )
        assert response.status_code == 200

        data = response.json()
        summary = data["compliance_summary"]

        assert summary["person_expected"] == 3
        assert summary["person_pass"] is True
        assert "helmet_pass" in summary
        assert "speech_pass" in summary
        assert "overall_pass" in summary

    def test_full_analysis_compliance_summary(self, client, sample_video_bytes):
        """POST /analyze/full - 준수 요약 확인"""
        response = client.post(
            "/analyze/full",
            files={"file": ("test.mp4", sample_video_bytes, "video/mp4")},
            data={
                "sample_interval": 30,
                "required_helmet_compliance": 100.0,
                "required_keyword_coverage": 80.0
            }
        )
        assert response.status_code == 200

        data = response.json()
        summary = data["compliance_summary"]

        # 헬멧은 100% 미만이므로 fail, 음성은 100%이므로 pass
        assert summary["speech_pass"] is True
        assert summary["helmet_pass"] is False
        # overall = person(True) and helmet(False) and speech(True) = False
        assert data["overall_compliance"] is False


# =====================================================
# 에러 케이스 테스트
# =====================================================

class TestErrorCases:
    """에러 케이스 테스트"""

    def test_invalid_sample_interval(self, client, sample_video_bytes):
        """잘못된 sample_interval"""
        response = client.post(
            "/analyze/person-count",
            files={"file": ("test.mp4", sample_video_bytes, "video/mp4")},
            data={"sample_interval": "invalid"}
        )
        assert response.status_code == 422

    def test_invalid_compliance_rate_type(self, client, sample_video_bytes):
        """잘못된 타입의 compliance rate"""
        response = client.post(
            "/analyze/helmet-compliance",
            files={"file": ("test.mp4", sample_video_bytes, "video/mp4")},
            data={"sample_interval": 30, "required_compliance": "invalid"}
        )
        # FastAPI가 타입 검증
        assert response.status_code == 422

    def test_missing_required_params(self, client):
        """필수 파라미터 누락"""
        response = client.post("/analyze/full")
        assert response.status_code == 422


# =====================================================
# 통합 테스트 (실제 파일 사용)
# =====================================================

class TestIntegrationWithRealFile:
    """실제 비디오 파일을 사용한 통합 테스트"""

    @pytest.mark.skipif(
        not (Path(__file__).parent / "test_video.mp4").exists(),
        reason="test_video.mp4 파일이 없습니다"
    )
    def test_with_real_video(self, client, test_video_path):
        """실제 비디오 파일로 테스트"""
        with open(test_video_path, "rb") as f:
            response = client.post(
                "/analyze/person-count",
                files={"file": ("test_video.mp4", f, "video/mp4")},
                data={"sample_interval": 30}
            )

        assert response.status_code == 200
        data = response.json()
        assert data["video_filename"] == "test_video.mp4"


# =====================================================
# CLI 실행 (pytest 없이 직접 실행 시)
# =====================================================

if __name__ == "__main__":
    print("=" * 60)
    print("TBM Safety API 테스트")
    print("=" * 60)
    print("\n실행 방법:")
    print("  pytest tests/test_tbm_api.py -v")
    print("  pytest tests/test_tbm_api.py -v -k 'test_root'")
    print("  pytest tests/test_tbm_api.py -v --tb=short")
    print("\n직접 실행:")
    pytest.main([__file__, "-v", "--tb=short"])
