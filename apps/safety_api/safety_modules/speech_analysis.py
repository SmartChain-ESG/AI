"""
Speech Analysis Module
Analyzes audio from TBM videos to check safety script compliance using STT
"""

import numpy as np
from typing import List, Dict, Optional, Tuple
from pathlib import Path
import logging
import re

logger = logging.getLogger(__name__)


class SpeechAnalyzer:
    """
    Analyzes speech from TBM videos to verify safety script compliance.
    Uses Speech-to-Text (STT) and keyword matching.
    """

    def __init__(self, stt_model: str = "openai/whisper-base",
                 required_keywords: Optional[List[str]] = None,
                 language: str = "ko"):
        """
        Initialize the SpeechAnalyzer.

        Args:
            stt_model: STT model to use (default: whisper-base)
            required_keywords: List of required safety keywords to check
            language: Language code for STT (default: "ko" for Korean)
        """
        self.stt_model_name = stt_model
        self.language = language
        self.model = None
        self.processor = None

        # Default required safety keywords for TBM (Korean)
        self.required_keywords = required_keywords or [
            "안전",  # safety
            "주의",  # caution
            "확인",  # check
            "작업",  # work
            "위험",  # danger/hazard
        ]

        self._initialize_stt_model()

    def _initialize_stt_model(self):
        """Initialize the STT model (Whisper)."""
        try:
            import torch
            from transformers import WhisperProcessor, WhisperForConditionalGeneration

            logger.info(f"Loading STT model: {self.stt_model_name}")
            self.processor = WhisperProcessor.from_pretrained(self.stt_model_name)
            self.model = WhisperForConditionalGeneration.from_pretrained(self.stt_model_name)

            # Use GPU if available
            if torch.cuda.is_available():
                self.model = self.model.to("cuda")
                logger.info("Using GPU for STT inference")
            else:
                logger.info("Using CPU for STT inference")

        except ImportError:
            logger.error("transformers or torch not installed. Please install: pip install transformers torch")
            raise
        except Exception as e:
            logger.error(f"Failed to load STT model: {e}")
            raise

    def extract_audio(self, video_path: str, output_path: Optional[str] = None) -> str:
        """
        Extract audio from video file.

        Args:
            video_path: Path to the video file
            output_path: Path to save extracted audio (WAV format)

        Returns:
            Path to the extracted audio file
        """
        try:
            from moviepy.editor import VideoFileClip
        except ImportError:
            logger.error("moviepy not installed. Please install: pip install moviepy")
            raise

        if output_path is None:
            output_path = str(Path(video_path).with_suffix('.wav'))

        video = VideoFileClip(video_path)
        audio = video.audio

        if audio is None:
            raise ValueError(f"No audio track found in video: {video_path}")

        audio.write_audiofile(output_path, logger=None)
        video.close()

        logger.info(f"Audio extracted to: {output_path}")
        return output_path

    def transcribe_audio(self, audio_path: str) -> str:
        """
        Transcribe audio file to text using STT.

        Args:
            audio_path: Path to the audio file (WAV format preferred)

        Returns:
            Transcribed text
        """
        if self.model is None or self.processor is None:
            raise RuntimeError("STT model not initialized")

        try:
            import torch
            import librosa

            # Load audio
            audio_array, sampling_rate = librosa.load(audio_path, sr=16000)

            # Process audio
            input_features = self.processor(
                audio_array,
                sampling_rate=sampling_rate,
                return_tensors="pt"
            ).input_features

            # Move to GPU if available
            if torch.cuda.is_available():
                input_features = input_features.to("cuda")

            # Generate transcription
            forced_decoder_ids = self.processor.get_decoder_prompt_ids(
                language=self.language,
                task="transcribe"
            )

            predicted_ids = self.model.generate(
                input_features,
                forced_decoder_ids=forced_decoder_ids
            )

            # Decode transcription
            transcription = self.processor.batch_decode(
                predicted_ids,
                skip_special_tokens=True
            )[0]

            logger.info(f"Transcription: {transcription[:100]}...")
            return transcription

        except ImportError:
            logger.error("librosa not installed. Please install: pip install librosa")
            raise
        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            raise

    def check_keywords(self, text: str, keywords: Optional[List[str]] = None) -> Dict:
        """
        Check if required safety keywords are present in the transcribed text.

        Args:
            text: Transcribed text to analyze
            keywords: List of keywords to check (uses default if None)

        Returns:
            Dictionary containing:
                - found_keywords: List of keywords found in text
                - missing_keywords: List of keywords not found
                - keyword_coverage: Percentage of required keywords found
                - compliant: Whether all required keywords are present
        """
        if keywords is None:
            keywords = self.required_keywords

        text_lower = text.lower()
        found_keywords = []
        missing_keywords = []

        for keyword in keywords:
            if keyword.lower() in text_lower:
                found_keywords.append(keyword)
            else:
                missing_keywords.append(keyword)

        coverage = (len(found_keywords) / len(keywords) * 100) if keywords else 0

        return {
            'found_keywords': found_keywords,
            'missing_keywords': missing_keywords,
            'keyword_coverage': coverage,
            'compliant': len(missing_keywords) == 0,
            'total_keywords': len(keywords),
            'found_count': len(found_keywords)
        }

    def analyze_video(self, video_path: str,
                     keywords: Optional[List[str]] = None,
                     min_coverage: float = 80.0) -> Dict:
        """
        Analyze video for safety script compliance.

        Args:
            video_path: Path to the video file
            keywords: List of required keywords (uses default if None)
            min_coverage: Minimum keyword coverage required for compliance (0-100)

        Returns:
            Dictionary containing:
                - transcription: Full transcribed text
                - keyword_analysis: Results from check_keywords()
                - compliant: Whether the video meets minimum coverage requirement
                - audio_path: Path to extracted audio file
        """
        try:
            # Extract audio from video
            audio_path = self.extract_audio(video_path)

            # Transcribe audio to text
            transcription = self.transcribe_audio(audio_path)

            # Check for required keywords
            keyword_analysis = self.check_keywords(transcription, keywords)

            # Determine overall compliance
            compliant = keyword_analysis['keyword_coverage'] >= min_coverage

            result = {
                'transcription': transcription,
                'keyword_analysis': keyword_analysis,
                'compliant': compliant,
                'audio_path': audio_path,
                'min_coverage_required': min_coverage
            }

            logger.info(f"Speech analysis complete. Compliant: {compliant}")
            logger.info(f"Keyword coverage: {keyword_analysis['keyword_coverage']:.1f}%")

            return result

        except Exception as e:
            logger.error(f"Video analysis failed: {e}")
            raise

    def analyze_audio_segments(self, audio_path: str,
                              segment_duration: int = 30,
                              keywords: Optional[List[str]] = None) -> Dict:
        """
        Analyze audio in segments to track keyword usage over time.

        Args:
            audio_path: Path to the audio file
            segment_duration: Duration of each segment in seconds
            keywords: List of required keywords

        Returns:
            Dictionary containing segment-by-segment analysis
        """
        try:
            import librosa

            # Load audio
            audio_array, sampling_rate = librosa.load(audio_path, sr=16000)
            total_duration = len(audio_array) / sampling_rate

            segment_samples = segment_duration * sampling_rate
            segments = []

            for start_sample in range(0, len(audio_array), segment_samples):
                end_sample = min(start_sample + segment_samples, len(audio_array))
                segment_audio = audio_array[start_sample:end_sample]

                # Save segment temporarily
                segment_path = f"temp_segment_{start_sample}.wav"
                import soundfile as sf
                sf.write(segment_path, segment_audio, sampling_rate)

                # Transcribe segment
                transcription = self.transcribe_audio(segment_path)

                # Analyze keywords
                keyword_analysis = self.check_keywords(transcription, keywords)

                segments.append({
                    'start_time': start_sample / sampling_rate,
                    'end_time': end_sample / sampling_rate,
                    'transcription': transcription,
                    'keyword_analysis': keyword_analysis
                })

                # Clean up temporary file
                Path(segment_path).unlink(missing_ok=True)

            return {
                'total_duration': total_duration,
                'segment_duration': segment_duration,
                'segments': segments,
                'total_segments': len(segments)
            }

        except Exception as e:
            logger.error(f"Segment analysis failed: {e}")
            raise
