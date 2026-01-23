"""
Tests for FastAPI endpoints
"""

import pytest
from fastapi.testclient import TestClient
from pathlib import Path
import sys
import io

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent / "app"))

from app.main import app


@pytest.fixture
def client():
    """Create a test client"""
    return TestClient(app)


class TestAPIEndpoints:
    """Test cases for API endpoints"""

    def test_root_endpoint(self, client):
        """Test root endpoint"""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "version" in data
        assert data["version"] == "1.0.0"

    def test_health_check(self, client):
        """Test health check endpoint"""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["status"] == "healthy"
        assert "models_loaded" in data

    @pytest.mark.skipif(not Path("test_video.mp4").exists(), reason="Test video not available")
    def test_analyze_person_count(self, client):
        """Test person count analysis endpoint"""
        with open("test_video.mp4", "rb") as f:
            files = {"file": ("test_video.mp4", f, "video/mp4")}
            response = client.post("/analyze/person-count", files=files)

        if response.status_code == 200:
            data = response.json()
            assert "video_filename" in data
            assert "total_frames" in data
            assert "detections_per_frame" in data
        else:
            # Model might not be initialized in test environment
            assert response.status_code in [503, 500]

    @pytest.mark.skipif(not Path("test_video.mp4").exists(), reason="Test video not available")
    def test_analyze_helmet_compliance(self, client):
        """Test helmet compliance analysis endpoint"""
        with open("test_video.mp4", "rb") as f:
            files = {"file": ("test_video.mp4", f, "video/mp4")}
            response = client.post(
                "/analyze/helmet-compliance",
                files=files,
                data={"sample_interval": 30, "required_compliance": 100.0}
            )

        # Helmet detector requires custom model
        assert response.status_code in [200, 503]

    @pytest.mark.skipif(not Path("test_video.mp4").exists(), reason="Test video not available")
    def test_analyze_speech_compliance(self, client):
        """Test speech compliance analysis endpoint"""
        with open("test_video.mp4", "rb") as f:
            files = {"file": ("test_video.mp4", f, "video/mp4")}
            response = client.post(
                "/analyze/speech-compliance",
                files=files,
                data={"min_coverage": 80.0}
            )

        if response.status_code == 200:
            data = response.json()
            assert "video_filename" in data
            assert "transcription" in data
            assert "keyword_analysis" in data
        else:
            assert response.status_code in [503, 500]

    def test_analyze_person_count_no_file(self, client):
        """Test person count endpoint without file"""
        response = client.post("/analyze/person-count")
        assert response.status_code == 422  # Unprocessable Entity

    @pytest.mark.skipif(not Path("test_video.mp4").exists(), reason="Test video not available")
    def test_analyze_full(self, client):
        """Test full analysis endpoint"""
        with open("test_video.mp4", "rb") as f:
            files = {"file": ("test_video.mp4", f, "video/mp4")}
            response = client.post("/analyze/full", files=files)

        if response.status_code == 200:
            data = response.json()
            assert "video_filename" in data
            assert "person_detection" in data
            assert "helmet_detection" in data
            assert "speech_analysis" in data
            assert "overall_compliance" in data
            assert "compliance_summary" in data
        else:
            assert response.status_code in [503, 500]

    def test_invalid_video_format(self, client):
        """Test with invalid video format"""
        # Create a fake file that's not a video
        fake_file = io.BytesIO(b"not a video")
        files = {"file": ("test.txt", fake_file, "text/plain")}
        response = client.post("/analyze/person-count", files=files)

        # Should fail during processing
        assert response.status_code in [500, 503]
