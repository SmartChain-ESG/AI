"""
TBM Safety Management System API
FastAPI application for analyzing TBM videos for safety compliance

Port: 8000 (안전보건팀)
Author: 이수빈
Team: AI 개발팀
"""

from fastapi import FastAPI, File, UploadFile, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List
import shutil
import tempfile
from pathlib import Path
import logging
import os

from safety_modules.person_detection import PersonDetector
from safety_modules.helmet_detection import HelmetDetector
from safety_modules.speech_analysis import SpeechAnalyzer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="TBM Safety Management API",
    description="AI-based TBM video analysis for construction safety compliance",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS 설정 (프론트엔드 연동을 위해 필수)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 프로덕션에서는 특정 도메인만 허용 권장
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global model instances (initialized on startup)
person_detector: Optional[PersonDetector] = None
helmet_detector: Optional[HelmetDetector] = None
speech_analyzer: Optional[SpeechAnalyzer] = None

# 모델 파일 경로 (Docker 컨테이너 내부 경로)
MODELS_DIR = Path("/app/models")


# Pydantic models for request/response
class AnalysisConfig(BaseModel):
    """Configuration for video analysis"""

    sample_interval: int = Field(default=30, description="Process every Nth frame")
    person_confidence: float = Field(
        default=0.5, ge=0.0, le=1.0, description="Person detection confidence threshold"
    )
    helmet_confidence: float = Field(
        default=0.5, ge=0.0, le=1.0, description="Helmet detection confidence threshold"
    )
    required_helmet_compliance: float = Field(
        default=100.0, ge=0.0, le=100.0, description="Required helmet compliance rate"
    )
    required_keyword_coverage: float = Field(
        default=80.0, ge=0.0, le=100.0, description="Required keyword coverage rate"
    )
    custom_keywords: Optional[List[str]] = Field(
        default=None, description="Custom safety keywords to check"
    )
    expected_person_count: Optional[int] = Field(
        default=None,
        ge=1,
        description="Expected minimum person count (PASS if max_count >= expected_person_count)",
    )


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

    logger.info("=" * 60)
    logger.info("🚀 TBM Safety API Starting Up")
    logger.info("=" * 60)
    logger.info(f"Port: 8000 (안전보건팀)")
    logger.info(f"Models Directory: {MODELS_DIR}")
    
    try:
        logger.info("Initializing AI models...")

        # 1. Person Detector 초기화
        logger.info("Loading Person Detector (yolo26n)...")
        person_detector = PersonDetector(
            confidence_threshold=float(os.getenv("PERSON_CONFIDENCE", "0.5"))
        )
        logger.info("✅ Person detector initialized")

        # 2. Helmet Detector 초기화
        logger.info("Loading Helmet Detector...")
        helmet_model_path = MODELS_DIR / "helmet_model.pt"
        
        if helmet_model_path.exists():
            logger.info(f"Found custom helmet model: {helmet_model_path}")
            helmet_detector = HelmetDetector(
                model_path=str(helmet_model_path),
                confidence_threshold=float(os.getenv("HELMET_CONFIDENCE", "0.5"))
            )
            logger.info("✅ Helmet detector initialized with custom model")
        else:
            logger.info("Custom helmet model not found, using color-based detection")
            helmet_detector = HelmetDetector(
                model_path=None,
                confidence_threshold=float(os.getenv("HELMET_CONFIDENCE", "0.5"))
            )
            logger.info("✅ Helmet detector initialized with color-based detection (temporary)")

        # 3. Speech Analyzer 초기화
        logger.info("Loading Speech Analyzer (Whisper)...")
        speech_analyzer = SpeechAnalyzer()
        logger.info("✅ Speech analyzer initialized")

        logger.info("=" * 60)
        logger.info("✅ All models initialized successfully")
        logger.info("🎉 Application startup complete")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"❌ Failed to initialize models: {e}")
        raise


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("🛑 Shutting down TBM Safety API")


@app.get("/")
async def root():
    """Root endpoint - API status check"""
    return {
        "message": "TBM Safety Management API",
        "version": "1.0.0",
        "status": "running",
        "port": 8000,
        "team": "안전보건팀",
        "models": {
            "person_detector": person_detector is not None,
            "helmet_detector": helmet_detector is not None,
            "speech_analyzer": speech_analyzer is not None,
        },
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    if person_detector is None or helmet_detector is None or speech_analyzer is None:
        raise HTTPException(status_code=503, detail="Models not loaded")
    
    return {
        "status": "healthy",
        "port": 8000,
        "models_loaded": {
            "person_detector": True,
            "helmet_detector": True,
            "speech_analyzer": True,
        },
    }


@app.post("/analyze/person-count", response_model=dict)
async def analyze_person_count(
    file: UploadFile = File(...),
    sample_interval: int = Form(30),
    expected_person_count: Optional[int] = Form(None),
):
    """
    Analyze video for person count detection.

    Args:
        file: Video file to analyze
        sample_interval: Process every Nth frame
        expected_person_count: Expected minimum person count (PASS if max_count >= expected)

    Returns:
        Person detection results (+ person_pass if expected_person_count provided)
    """
    if person_detector is None:
        raise HTTPException(status_code=503, detail="Person detector not initialized")

    with tempfile.NamedTemporaryFile(
        delete=False, suffix=Path(file.filename).suffix
    ) as tmp_file:
        shutil.copyfileobj(file.file, tmp_file)
        tmp_path = tmp_file.name

    try:
        logger.info(f"Analyzing person count in: {file.filename}")
        result = person_detector.process_video(tmp_path, sample_interval=sample_interval)
        result["video_filename"] = file.filename

        # Add pass/fail based on max_count
        result["expected_person_count"] = expected_person_count
        if expected_person_count is not None:
            max_count = result.get("max_count")
            result["person_pass"] = (max_count is not None) and (
                max_count >= expected_person_count
            )
        else:
            result["person_pass"] = None

        return result

    except Exception as e:
        logger.error(f"Person detection failed: {e}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

    finally:
        Path(tmp_path).unlink(missing_ok=True)


@app.post("/analyze/helmet-compliance", response_model=dict)
async def analyze_helmet_compliance(
    file: UploadFile = File(...),
    sample_interval: int = Form(30),
    required_compliance: float = Form(100.0),
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
            detail="Helmet detector not initialized",
        )

    with tempfile.NamedTemporaryFile(
        delete=False, suffix=Path(file.filename).suffix
    ) as tmp_file:
        shutil.copyfileobj(file.file, tmp_file)
        tmp_path = tmp_file.name

    try:
        logger.info(f"Analyzing helmet compliance in: {file.filename}")
        result = helmet_detector.process_video(
            tmp_path,
            sample_interval=sample_interval,
            required_compliance=required_compliance,
        )
        result["video_filename"] = file.filename
        return result

    except Exception as e:
        logger.error(f"Helmet detection failed: {e}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

    finally:
        Path(tmp_path).unlink(missing_ok=True)


@app.post("/analyze/speech-compliance", response_model=dict)
async def analyze_speech_compliance(
    file: UploadFile = File(...),
    min_coverage: float = Form(80.0),
    custom_keywords: Optional[List[str]] = Form(None),
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

    with tempfile.NamedTemporaryFile(
        delete=False, suffix=Path(file.filename).suffix
    ) as tmp_file:
        shutil.copyfileobj(file.file, tmp_file)
        tmp_path = tmp_file.name

    result = None
    try:
        logger.info(f"Analyzing speech compliance in: {file.filename}")
        result = speech_analyzer.analyze_video(
            tmp_path, 
            keywords=custom_keywords, 
            min_keyword_coverage=min_coverage
        )
        result["video_filename"] = file.filename
        return result

    except Exception as e:
        logger.error(f"Speech analysis failed: {e}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

    finally:
        Path(tmp_path).unlink(missing_ok=True)
        if isinstance(result, dict):
            audio_path = result.get("audio_path")
            if audio_path:
                Path(audio_path).unlink(missing_ok=True)


@app.post("/analyze/full", response_model=AnalysisResult)
async def analyze_full(
    file: UploadFile = File(...),
    sample_interval: int = Form(30),
    required_helmet_compliance: float = Form(100.0),
    required_keyword_coverage: float = Form(80.0),
    expected_person_count: Optional[int] = Form(None),
    custom_keywords: Optional[List[str]] = Form(None),
):
    """
    Perform full analysis (person + helmet + speech).

    Args:
        file: Video file to analyze
        sample_interval: Process every Nth frame
        required_helmet_compliance: Required helmet compliance rate
        required_keyword_coverage: Required keyword coverage rate
        expected_person_count: Expected minimum person count
        custom_keywords: Optional custom safety keywords

    Returns:
        Complete analysis result with compliance summary
    """
    if person_detector is None or speech_analyzer is None:
        raise HTTPException(status_code=503, detail="Required models not initialized")

    with tempfile.NamedTemporaryFile(
        delete=False, suffix=Path(file.filename).suffix
    ) as tmp_file:
        shutil.copyfileobj(file.file, tmp_file)
        tmp_path = tmp_file.name

    speech_result = None
    try:
        logger.info(f"Performing full analysis on: {file.filename}")

        # 1. Person detection
        logger.info("Step 1/3: Person detection")
        person_result = person_detector.process_video(
            tmp_path, 
            sample_interval=sample_interval
        )

        if expected_person_count is not None:
            max_count = person_result.get("max_count")
            person_pass = (max_count is not None) and (max_count >= expected_person_count)
        else:
            person_pass = True  # 기준 없으면 overall 영향 X

        person_result["expected_person_count"] = expected_person_count
        person_result["person_pass"] = person_pass if expected_person_count is not None else None

        # 2. Helmet detection
        logger.info("Step 2/3: Helmet compliance")
        if helmet_detector is not None:
            helmet_result = helmet_detector.process_video(
                tmp_path,
                sample_interval=sample_interval,
                required_compliance=required_helmet_compliance,
            )
        else:
            helmet_result = {
                "status": "unavailable",
                "message": "Helmet detector not initialized"
            }

        # 3. Speech analysis
        logger.info("Step 3/3: Speech analysis")
        speech_result = speech_analyzer.analyze_video(
            tmp_path,
            keywords=custom_keywords,
            min_keyword_coverage=required_keyword_coverage,
        )

        # Compliance calculation
        helmet_compliant = helmet_result.get("overall_pass", True) if helmet_detector else True
        speech_compliant = speech_result.get("compliant", False)
        overall_compliant = person_pass and helmet_compliant and speech_compliant

        compliance_summary = {
            "person_expected": expected_person_count,
            "person_pass": person_pass if expected_person_count is not None else None,
            "helmet_compliance": helmet_result.get("average_compliance", 0) if helmet_detector else None,
            "speech_compliance": speech_result["keyword_analysis"]["keyword_coverage"],
            "helmet_pass": helmet_compliant,
            "speech_pass": speech_compliant,
            "overall_pass": overall_compliant,
        }

        logger.info("✅ Full analysis complete")
        
        return {
            "video_filename": file.filename,
            "person_detection": person_result,
            "helmet_detection": helmet_result,
            "speech_analysis": speech_result,
            "overall_compliance": overall_compliant,
            "compliance_summary": compliance_summary,
        }

    except Exception as e:
        logger.error(f"Full analysis failed: {e}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

    finally:
        Path(tmp_path).unlink(missing_ok=True)
        if isinstance(speech_result, dict):
            audio_path = speech_result.get("audio_path")
            if audio_path:
                Path(audio_path).unlink(missing_ok=True)


if __name__ == "__main__":
    import uvicorn
    # 포트 8000 고정 (안전보건팀)
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info"
    )