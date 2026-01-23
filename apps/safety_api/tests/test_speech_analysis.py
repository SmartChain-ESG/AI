"""
Tests for SpeechAnalyzer module
"""

import pytest
from pathlib import Path
import sys

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from safety_modules.speech_analysis import SpeechAnalyzer


@pytest.fixture
def speech_analyzer():
    """Create a SpeechAnalyzer instance for testing"""
    return SpeechAnalyzer(language="ko")


class TestSpeechAnalyzer:
    """Test cases for SpeechAnalyzer class"""

    def test_initialization(self):
        """Test SpeechAnalyzer initialization"""
        analyzer = SpeechAnalyzer(language="ko")
        assert analyzer is not None
        assert analyzer.language == "ko"
        assert len(analyzer.required_keywords) > 0

    def test_custom_keywords(self):
        """Test initialization with custom keywords"""
        custom_kw = ["test1", "test2", "test3"]
        analyzer = SpeechAnalyzer(required_keywords=custom_kw)
        assert analyzer.required_keywords == custom_kw

    def test_check_keywords_all_present(self, speech_analyzer):
        """Test keyword checking when all keywords are present"""
        text = "안전 작업을 위해 주의하고 확인하며 위험 요소를 파악합니다"
        result = speech_analyzer.check_keywords(text)

        assert 'found_keywords' in result
        assert 'missing_keywords' in result
        assert 'keyword_coverage' in result
        assert 'compliant' in result

        assert result['keyword_coverage'] == 100.0
        assert result['compliant'] is True
        assert len(result['missing_keywords']) == 0

    def test_check_keywords_partial(self, speech_analyzer):
        """Test keyword checking with partial matches"""
        text = "안전 작업을 시작합니다"  # Only has '안전' and '작업'
        result = speech_analyzer.check_keywords(text)

        assert result['keyword_coverage'] < 100.0
        assert result['compliant'] is False
        assert len(result['found_keywords']) > 0
        assert len(result['missing_keywords']) > 0

    def test_check_keywords_none_present(self, speech_analyzer):
        """Test keyword checking when no keywords are present"""
        text = "Hello world this is a test"
        result = speech_analyzer.check_keywords(text)

        assert result['keyword_coverage'] == 0.0
        assert result['compliant'] is False
        assert len(result['found_keywords']) == 0
        assert len(result['missing_keywords']) == len(speech_analyzer.required_keywords)

    def test_check_keywords_custom(self, speech_analyzer):
        """Test keyword checking with custom keyword list"""
        text = "test apple banana orange"
        custom_keywords = ["apple", "banana"]
        result = speech_analyzer.check_keywords(text, keywords=custom_keywords)

        assert result['keyword_coverage'] == 100.0
        assert result['compliant'] is True
        assert set(result['found_keywords']) == set(custom_keywords)

    def test_check_keywords_case_insensitive(self, speech_analyzer):
        """Test that keyword checking is case insensitive"""
        keywords = ["Apple", "BANANA"]
        text = "I like apple and banana"
        result = speech_analyzer.check_keywords(text, keywords=keywords)

        assert result['keyword_coverage'] == 100.0
        assert result['compliant'] is True

    @pytest.mark.skipif(not Path("test_audio.wav").exists(), reason="Test audio not available")
    def test_transcribe_audio(self, speech_analyzer):
        """Test audio transcription (requires test audio file)"""
        transcription = speech_analyzer.transcribe_audio("test_audio.wav")
        assert isinstance(transcription, str)
        assert len(transcription) > 0

    @pytest.mark.skipif(not Path("test_video.mp4").exists(), reason="Test video not available")
    def test_extract_audio(self, speech_analyzer):
        """Test audio extraction from video"""
        audio_path = speech_analyzer.extract_audio("test_video.mp4")
        assert Path(audio_path).exists()
        assert audio_path.endswith('.wav')
        # Clean up
        Path(audio_path).unlink(missing_ok=True)

    @pytest.mark.skipif(not Path("test_video.mp4").exists(), reason="Test video not available")
    def test_analyze_video(self, speech_analyzer):
        """Test complete video analysis"""
        result = speech_analyzer.analyze_video("test_video.mp4", min_coverage=80.0)

        assert 'transcription' in result
        assert 'keyword_analysis' in result
        assert 'compliant' in result
        assert 'audio_path' in result

        assert isinstance(result['transcription'], str)
        assert isinstance(result['compliant'], bool)

        # Clean up
        if Path(result['audio_path']).exists():
            Path(result['audio_path']).unlink(missing_ok=True)

    def test_keyword_coverage_calculation(self):
        """Test keyword coverage calculation"""
        analyzer = SpeechAnalyzer(required_keywords=["a", "b", "c", "d"])

        # Test different scenarios
        test_cases = [
            ("a b c d", 100.0),
            ("a b c", 75.0),
            ("a b", 50.0),
            ("a", 25.0),
            ("x y z", 0.0),
        ]

        for text, expected_coverage in test_cases:
            result = analyzer.check_keywords(text)
            assert abs(result['keyword_coverage'] - expected_coverage) < 0.1
