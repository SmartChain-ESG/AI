"""
Tests for PersonDetector module
"""

import pytest
import numpy as np
import cv2
from pathlib import Path
import sys

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from safety_modules.person_detection import PersonDetector


@pytest.fixture
def person_detector():
    """Create a PersonDetector instance for testing"""
    return PersonDetector(confidence_threshold=0.5)


@pytest.fixture
def sample_image():
    """Create a sample test image"""
    # Create a blank 640x480 image
    image = np.zeros((480, 640, 3), dtype=np.uint8)
    return image


class TestPersonDetector:
    """Test cases for PersonDetector class"""

    def test_initialization(self):
        """Test PersonDetector initialization"""
        detector = PersonDetector(confidence_threshold=0.7)
        assert detector is not None
        assert detector.confidence_threshold == 0.7
        assert detector.model is not None

    def test_detect_persons(self, person_detector, sample_image):
        """Test person detection on sample image"""
        detections = person_detector.detect_persons(sample_image)
        assert isinstance(detections, list)
        # Empty image should have no detections
        assert len(detections) == 0

    def test_count_persons(self, person_detector, sample_image):
        """Test person counting"""
        count = person_detector.count_persons(sample_image)
        assert isinstance(count, int)
        assert count >= 0

    def test_detection_structure(self, person_detector):
        """Test detection dictionary structure"""
        # Create a more realistic test image with some content
        image = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        detections = person_detector.detect_persons(image)

        for detection in detections:
            assert 'bbox' in detection
            assert 'confidence' in detection
            assert 'class_id' in detection
            assert len(detection['bbox']) == 4
            assert 0 <= detection['confidence'] <= 1
            assert detection['class_id'] == 0  # person class

    def test_draw_detections(self, person_detector, sample_image):
        """Test drawing bounding boxes on image"""
        detections = [
            {
                'bbox': [100, 100, 200, 300],
                'confidence': 0.9,
                'class_id': 0
            }
        ]
        result_image = person_detector.draw_detections(sample_image, detections)
        assert result_image.shape == sample_image.shape
        # Verify image was modified (not equal to original)
        assert not np.array_equal(result_image, sample_image)

    def test_confidence_threshold(self):
        """Test different confidence thresholds"""
        detector_low = PersonDetector(confidence_threshold=0.3)
        detector_high = PersonDetector(confidence_threshold=0.8)

        assert detector_low.confidence_threshold == 0.3
        assert detector_high.confidence_threshold == 0.8

    @pytest.mark.skipif(not Path("test_video.mp4").exists(), reason="Test video not available")
    def test_process_video(self, person_detector):
        """Test video processing (requires test video file)"""
        result = person_detector.process_video("test_video.mp4", sample_interval=30)

        assert 'total_frames' in result
        assert 'sampled_frames' in result
        assert 'detections_per_frame' in result
        assert 'average_count' in result
        assert 'max_count' in result
        assert 'min_count' in result
        assert result['total_frames'] > 0
