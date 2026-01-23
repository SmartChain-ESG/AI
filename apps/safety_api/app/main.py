"""
TBM Safety Management System API
FastAPI application for analyzing TBM videos for safety compliance
"""

from fastapi import FastAPI, File, UploadFile, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List
import shutil
import tempfile
from pathlib import Path
import logging
import sys

# Add parent directory to path to import safety_modules
sys.path.append(str(Path(__file__).parent.parent))

from safety_modules.person_detection import PersonDetector
from safety_modules.helmet_detection import HelmetDetector
from safety_modules.speech_analysis import SpeechAnalyzer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="TBM Safety Management API",
    description="API for analyzing TBM (Tool Box Meeting) videos for safety compliance",
    version="1.0.0"
)

# Global model instances (initialized on startup)
person_detector: Optional[PersonDetector] = None
helmet_detector: Optional[HelmetDetector] = None
speech_analyzer: Optional[SpeechAnalyzer] = None


# Pydantic models for request/response
class AnalysisConfig(BaseModel):
    """Configuration for video analysis"""
    sample_interval: int = Field(default=30, description="Process every Nth frame")
    person_confidence: float = Field(default=0.5, ge=0.0, le=1.0, description="Person detection confidence threshold")
    helmet_confidence: float = Field(default=0.5, ge=0.0, le=1.0, description="Helmet detection confidence threshold")
    required_helmet_compliance: float = Field(default=100.0, ge=0.0, le=100.0, description="Required helmet compliance rate")
    required_keyword_coverage: float = Field(default=80.0, ge=0.0, le=100.0, description="Required keyword coverage rate")
    custom_keywords: Optional[List[str]] = Field(default=None, description="Custom safety keywords to check")


class AnalysisResult(BaseModel):
    """Complete analysis result"""
    video_filename: str
    person_detection: dict
    helmet_detection: dict
    speech_analysis: dict
    overall_compliance: bool
    compliance_summary: dict


@app.on_event("startup")
async def startup_event():
    """Initialize models on startup"""
    global person_detector, helmet_detector, speech_analyzer

    try:
        logger.info("Initializing models...")

        # Initialize person detector
        person_detector = PersonDetector(confidence_threshold=0.5)
        logger.info("Person detector initialized")

        # Initialize helmet detector (requires custom trained model)
        helmet_model_path = Path(__file__).parent.parent / "models" / "helmet_model.pt"
        if helmet_model_path.exists():
            helmet_detector = HelmetDetector(model_path=str(helmet_model_path), confidence_threshold=0.5)
            logger.info("Helmet detector initialized")
        else:
            logger.warning(f"Helmet model not found at {helmet_model_path}. Helmet detection will not be available.")
            helmet_detector = None

        # Initialize speech analyzer
        speech_analyzer = SpeechAnalyzer()
        logger.info("Speech analyzer initialized")

        logger.info("All models initialized successfully")

    except Exception as e:
        logger.error(f"Failed to initialize models: {e}")
        # Continue startup even if some models fail


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "TBM Safety Management API",
        "version": "1.0.0",
        "status": "running",
        "models": {
            "person_detector": person_detector is not None,
            "helmet_detector": helmet_detector is not None,
            "speech_analyzer": speech_analyzer is not None
        }
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "models_loaded": {
            "person_detector": person_detector is not None,
            "helmet_detector": helmet_detector is not None,
            "speech_analyzer": speech_analyzer is not None
        }
    }


@app.post("/analyze/person-count", response_model=dict)
async def analyze_person_count(
    file: UploadFile = File(...),
    sample_interval: int = 30
):
    """
    Analyze video for person count detection.

    Args:
        file: Video file to analyze
        sample_interval: Process every Nth frame

    Returns:
        Person detection results
    """
    if person_detector is None:
        raise HTTPException(status_code=503, detail="Person detector not initialized")

    # Save uploaded file temporarily
    with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.filename).suffix) as tmp_file:
        shutil.copyfileobj(file.file, tmp_file)
        tmp_path = tmp_file.name

    try:
        logger.info(f"Analyzing person count in: {file.filename}")
        result = person_detector.process_video(tmp_path, sample_interval=sample_interval)
        result['video_filename'] = file.filename
        return result

    except Exception as e:
        logger.error(f"Person detection failed: {e}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

    finally:
        # Clean up temporary file
        Path(tmp_path).unlink(missing_ok=True)


@app.post("/analyze/helmet-compliance", response_model=dict)
async def analyze_helmet_compliance(
    file: UploadFile = File(...),
    sample_interval: int = 30,
    required_compliance: float = 100.0
):
    """
    Analyze video for helmet compliance.

    Args:
        file: Video file to analyze
        sample_interval: Process every Nth frame
        required_compliance: Required compliance rate (0-100)

    Returns:
        Helmet compliance results
    """
    if helmet_detector is None:
        raise HTTPException(
            status_code=503,
            detail="Helmet detector not initialized. Please provide a trained helmet detection model."
        )

    # Save uploaded file temporarily
    with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.filename).suffix) as tmp_file:
        shutil.copyfileobj(file.file, tmp_file)
        tmp_path = tmp_file.name

    try:
        logger.info(f"Analyzing helmet compliance in: {file.filename}")
        result = helmet_detector.process_video(
            tmp_path,
            sample_interval=sample_interval,
            required_compliance=required_compliance
        )
        result['video_filename'] = file.filename
        return result

    except Exception as e:
        logger.error(f"Helmet detection failed: {e}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

    finally:
        # Clean up temporary file
        Path(tmp_path).unlink(missing_ok=True)


@app.post("/analyze/speech-compliance", response_model=dict)
async def analyze_speech_compliance(
    file: UploadFile = File(...),
    min_coverage: float = 80.0,
    custom_keywords: Optional[List[str]] = None
):
    """
    Analyze video for safety script compliance using speech recognition.

    Args:
        file: Video file to analyze
        min_coverage: Minimum keyword coverage required (0-100)
        custom_keywords: Optional custom keywords to check

    Returns:
        Speech analysis results
    """
    if speech_analyzer is None:
        raise HTTPException(status_code=503, detail="Speech analyzer not initialized")

    # Save uploaded file temporarily
    with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.filename).suffix) as tmp_file:
        shutil.copyfileobj(file.file, tmp_file)
        tmp_path = tmp_file.name

    try:
        logger.info(f"Analyzing speech compliance in: {file.filename}")
        result = speech_analyzer.analyze_video(
            tmp_path,
            keywords=custom_keywords,
            min_coverage=min_coverage
        )
        result['video_filename'] = file.filename
        return result

    except Exception as e:
        logger.error(f"Speech analysis failed: {e}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

    finally:
        # Clean up temporary file
        Path(tmp_path).unlink(missing_ok=True)
        # Clean up extracted audio if exists
        if 'audio_path' in locals():
            Path(result.get('audio_path', '')).unlink(missing_ok=True)


@app.post("/analyze/full", response_model=AnalysisResult)
async def analyze_full(
    file: UploadFile = File(...),
    config: AnalysisConfig = AnalysisConfig()
):
    """
    Perform complete safety analysis on video (person count, helmet compliance, speech analysis).

    Args:
        file: Video file to analyze
        config: Analysis configuration parameters

    Returns:
        Complete analysis results with overall compliance status
    """
    if person_detector is None or speech_analyzer is None:
        raise HTTPException(
            status_code=503,
            detail="Required models not initialized"
        )

    # Save uploaded file temporarily
    with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.filename).suffix) as tmp_file:
        shutil.copyfileobj(file.file, tmp_file)
        tmp_path = tmp_file.name

    try:
        logger.info(f"Performing full analysis on: {file.filename}")

        # Person detection
        person_result = person_detector.process_video(tmp_path, sample_interval=config.sample_interval)

        # Helmet detection (if available)
        helmet_result = None
        if helmet_detector is not None:
            helmet_result = helmet_detector.process_video(
                tmp_path,
                sample_interval=config.sample_interval,
                required_compliance=config.required_helmet_compliance
            )
        else:
            helmet_result = {"status": "unavailable", "message": "Helmet detector not initialized"}

        # Speech analysis
        speech_result = speech_analyzer.analyze_video(
            tmp_path,
            keywords=config.custom_keywords,
            min_coverage=config.required_keyword_coverage
        )

        # Determine overall compliance
        helmet_compliant = helmet_result.get('overall_pass', True) if helmet_detector else True
        speech_compliant = speech_result.get('compliant', False)
        overall_compliant = helmet_compliant and speech_compliant

        # Build compliance summary
        compliance_summary = {
            'helmet_compliance': helmet_result.get('average_compliance', 0) if helmet_detector else None,
            'speech_compliance': speech_result['keyword_analysis']['keyword_coverage'],
            'helmet_pass': helmet_compliant,
            'speech_pass': speech_compliant,
            'overall_pass': overall_compliant
        }

        result = {
            'video_filename': file.filename,
            'person_detection': person_result,
            'helmet_detection': helmet_result,
            'speech_analysis': speech_result,
            'overall_compliance': overall_compliant,
            'compliance_summary': compliance_summary
        }

        logger.info(f"Full analysis complete. Overall compliance: {overall_compliant}")
        return result

    except Exception as e:
        logger.error(f"Full analysis failed: {e}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

    finally:
        # Clean up temporary files
        Path(tmp_path).unlink(missing_ok=True)
        if 'audio_path' in speech_result:
            Path(speech_result['audio_path']).unlink(missing_ok=True)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
