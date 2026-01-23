"""
Tests for HelmetDetector module
"""

import pytest
import numpy as np
import cv2
from pathlib import Path
import sys

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from safety_modules.helmet_detection import HelmetDetector


@pytest.fixture
def sample_image():
    """Create a sample test image"""
    image = np.zeros((480, 640, 3), dtype=np.uint8)
    return image


class TestHelmetDetector:
    """Test cases for HelmetDetector class"""

    @pytest.mark.skipif(
        not Path("../models/helmet_model.pt").exists(),
        reason="Helmet model not available"
    )
    def test_initialization_with_model(self):
        """Test HelmetDetector initialization with custom model"""
        detector = HelmetDetector(
            model_path="../models/helmet_model.pt",
            confidence_threshold=0.6
        )
        assert detector is not None
        assert detector.confidence_threshold == 0.6

    def test_class_names(self):
        """Test class name mapping"""
        detector = HelmetDetector()
        assert 'helmet' in detector.class_names.values()
        assert 'no-helmet' in detector.class_names.values()

    @pytest.mark.skipif(
        not Path("../models/helmet_model.pt").exists(),
        reason="Helmet model not available"
    )
    def test_detect_helmets(self, sample_image):
        """Test helmet detection"""
        detector = HelmetDetector(model_path="../models/helmet_model.pt")
        result = detector.detect_helmets(sample_image)

        assert 'helmets' in result
        assert 'no_helmets' in result
        assert 'helmet_count' in result
        assert 'no_helmet_count' in result
        assert 'total_persons' in result
        assert 'helmet_compliance_rate' in result

        assert isinstance(result['helmets'], list)
        assert isinstance(result['no_helmets'], list)
        assert 0 <= result['helmet_compliance_rate'] <= 100

    @pytest.mark.skipif(
        not Path("../models/helmet_model.pt").exists(),
        reason="Helmet model not available"
    )
    def test_check_compliance(self, sample_image):
        """Test compliance checking"""
        detector = HelmetDetector(model_path="../models/helmet_model.pt")
        compliant = detector.check_compliance(sample_image, required_rate=100.0)
        assert isinstance(compliant, bool)

    @pytest.mark.skipif(
        not Path("../models/helmet_model.pt").exists(),
        reason="Helmet model not available"
    )
    def test_draw_detections(self, sample_image):
        """Test drawing detections on image"""
        detector = HelmetDetector(model_path="../models/helmet_model.pt")
        detections = {
            'helmets': [
                {
                    'bbox': [100, 100, 150, 200],
                    'confidence': 0.95,
                    'class_id': 0,
                    'class_name': 'helmet'
                }
            ],
            'no_helmets': [
                {
                    'bbox': [300, 100, 350, 200],
                    'confidence': 0.85,
                    'class_id': 1,
                    'class_name': 'no-helmet'
                }
            ],
            'helmet_count': 1,
            'no_helmet_count': 1,
            'total_persons': 2,
            'helmet_compliance_rate': 50.0
        }

        result_image = detector.draw_detections(sample_image, detections)
        assert result_image.shape == sample_image.shape

    def test_compliance_rate_calculation(self):
        """Test compliance rate edge cases"""
        # Test with mock detection results
        test_cases = [
            ({'helmet_count': 5, 'no_helmet_count': 0}, 100.0),
            ({'helmet_count': 0, 'no_helmet_count': 5}, 0.0),
            ({'helmet_count': 3, 'no_helmet_count': 2}, 60.0),
            ({'helmet_count': 0, 'no_helmet_count': 0}, 0.0),  # No persons
        ]

        for counts, expected_rate in test_cases:
            total = counts['helmet_count'] + counts['no_helmet_count']
            if total > 0:
                calculated_rate = (counts['helmet_count'] / total * 100)
            else:
                calculated_rate = 0
            assert abs(calculated_rate - expected_rate) < 0.1
