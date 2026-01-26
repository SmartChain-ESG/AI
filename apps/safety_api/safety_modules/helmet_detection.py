"""
Helmet Detection Module
Detects whether people are wearing safety helmets in TBM video frames

🔄 Current Implementation: Basic YOLO + Color-based detection (temporary)
📌 Future: Replace with custom-trained helmet detection model
"""

import cv2
import numpy as np
from typing import List, Dict, Tuple, Optional
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


def convert_numpy_types(obj):
    """
    NumPy 타입을 Python 기본 타입으로 변환
    JSON 직렬화를 위해 필수
    """
    if isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.bool_):
        return bool(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, dict):
        return {k: convert_numpy_types(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_numpy_types(item) for item in obj]
    else:
        return obj


class HelmetDetector:
    """
    Detects safety helmets and classifies whether persons are wearing them.
    
    Current: Uses yolo26n for person detection + color-based helmet detection
    Future: Will use custom-trained helmet detection model
    """

    def __init__(self, model_path: Optional[str] = None, confidence_threshold: float = 0.5):
        """
        Initialize the HelmetDetector.

        Args:
            model_path: Path to the trained helmet detection model file
            confidence_threshold: Minimum confidence score for detections (0.0 to 1.0)
        """
        self.confidence_threshold = confidence_threshold
        self.model_path = model_path
        self.model = None
        self.use_custom_model = False

        # Class mapping for helmet detection (커스텀 모델용)
        # Typical classes: 0=helmet, 1=no-helmet, 2=person
        self.class_names = {
            0: 'helmet',
            1: 'no-helmet',
            2: 'person'
        }

        # 모델 저장 디렉토리 (Docker: /app/models, 로컬: ./models)
        models_dir = Path("/app/models") if Path("/app/models").exists() else Path("./models")
        models_dir.mkdir(parents=True, exist_ok=True)

        try:
            from ultralytics import YOLO
            if model_path and Path(model_path).exists():
                # 커스텀 헬멧 감지 모델 사용
                self.model = YOLO(model_path)
                self.use_custom_model = True
                logger.info(f"✅ Loaded custom helmet detection model from {model_path}")
            else:
                # 기본 YOLO 모델을 models 폴더에서 로드
                default_model_path = models_dir / 'yolo26n.pt'
                
                if default_model_path.exists():
                    # 이미 다운로드된 모델 사용
                    self.model = YOLO(str(default_model_path))
                    logger.info(f"⚠️  Loaded yolo26n from {default_model_path} (color-based helmet detection)")
                else:
                    # 처음 실행: 다운로드 후 models 폴더로 이동
                    logger.info("Downloading yolo26n model...")
                    self.model = YOLO('yolo26n.pt')
                    
                    # 다운로드된 모델을 models 폴더로 이동
                    current_model = Path('yolo26n.pt')
                    if current_model.exists():
                        import shutil
                        shutil.move(str(current_model), str(default_model_path))
                        logger.info(f"Moved model to {default_model_path}")
                    
                    logger.info("⚠️  Using color-based helmet detection (temporary)")
                
                self.use_custom_model = False
                logger.info("📝 To use custom model: train helmet detection model and provide path")
                
        except ImportError:
            logger.error("ultralytics package not installed. Please install: pip install ultralytics")
            raise
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            raise

    def _detect_helmet_by_color(self, head_roi: np.ndarray) -> Tuple[bool, float]:
        """
        색상 기반 헬멧 감지 (임시 방법)
        건설 현장 헬멧 색상: 노란색, 주황색, 흰색, 빨간색, 파란색
        
        Args:
            head_roi: 머리 영역 이미지 (person bbox 상단 30%)
            
        Returns:
            Tuple[bool, float]: (헬멧 착용 여부, 신뢰도)
        """
        if head_roi is None or head_roi.size == 0 or head_roi.shape[0] < 10 or head_roi.shape[1] < 10:
            return False, 0.0
        
        try:
            # BGR to HSV 변환
            hsv = cv2.cvtColor(head_roi, cv2.COLOR_BGR2HSV)
            
            # 헬멧 색상 범위 정의 (HSV)
            helmet_colors = [
                # 노란색 헬멧 (가장 흔함)
                ([20, 100, 100], [30, 255, 255]),
                # 주황색 헬멧
                ([10, 100, 100], [20, 255, 255]),
                # 흰색 헬멧
                ([0, 0, 200], [180, 30, 255]),
                # 빨간색 헬멧
                ([0, 100, 100], [10, 255, 255]),
                ([170, 100, 100], [180, 255, 255]),  # 빨간색 wrap-around
                # 파란색 헬멧
                ([100, 100, 100], [130, 255, 255]),
                # 초록색 헬멧
                ([40, 100, 100], [80, 255, 255]),
            ]
            
            total_pixels = head_roi.shape[0] * head_roi.shape[1]
            max_helmet_ratio = 0.0
            
            for lower, upper in helmet_colors:
                lower_bound = np.array(lower, dtype=np.uint8)
                upper_bound = np.array(upper, dtype=np.uint8)
                
                # 색상 마스크 생성
                mask = cv2.inRange(hsv, lower_bound, upper_bound)
                helmet_pixels = cv2.countNonZero(mask)
                helmet_ratio = helmet_pixels / total_pixels
                
                max_helmet_ratio = max(max_helmet_ratio, helmet_ratio)
            
            # 15% 이상이 헬멧 색상이면 착용으로 판단
            has_helmet = max_helmet_ratio > 0.15
            confidence = min(max_helmet_ratio * 5, 1.0)  # 0.15 -> 0.75 confidence
            
            return has_helmet, confidence
            
        except Exception as e:
            logger.debug(f"Color detection error: {e}")
            return False, 0.0

    def detect_helmets(self, image: np.ndarray) -> Dict:
        """
        Detect helmets and non-helmeted persons in an image.

        Args:
            image: Input image as numpy array (BGR format)

        Returns:
            Dictionary containing:
                - helmets: List of helmet detections
                - no_helmets: List of no-helmet detections
                - total_persons: Total number of persons detected
                - helmet_compliance_rate: Percentage of persons wearing helmets
                - detection_method: 'custom_model' or 'color_based'
        """
        if self.model is None:
            raise RuntimeError("Model not initialized.")

        helmets = []
        no_helmets = []

        try:
            # ===== 커스텀 모델 사용 =====
            if self.use_custom_model:
                results = self.model(image, conf=self.confidence_threshold, verbose=False)

                for result in results:
                    boxes = result.boxes
                    for box in boxes:
                        x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                        confidence = float(box.conf[0].cpu().numpy())
                        class_id = int(box.cls[0].cpu().numpy())

                        detection = {
                            'bbox': [float(x1), float(y1), float(x2), float(y2)],
                            'confidence': float(confidence),
                            'class_id': int(class_id),
                            'class_name': self.class_names.get(class_id, 'unknown')
                        }

                        if class_id == 0:  # helmet
                            helmets.append(detection)
                        elif class_id == 1:  # no-helmet
                            no_helmets.append(detection)
            
            # ===== 기본 YOLO + 색상 기반 감지 (임시) =====
            else:
                # Person detection only
                results = self.model(image, conf=self.confidence_threshold, verbose=False, classes=[0])

                for result in results:
                    boxes = result.boxes
                    for box in boxes:
                        x1, y1, x2, y2 = map(int, box.xyxy[0].cpu().numpy())
                        person_conf = float(box.conf[0].cpu().numpy())
                        
                        # 머리 영역 추출 (바운딩 박스 상단 30%)
                        person_height = y2 - y1
                        head_height = int(person_height * 0.3)
                        head_y1 = max(0, y1)
                        head_y2 = min(image.shape[0], y1 + head_height)
                        head_x1 = max(0, x1)
                        head_x2 = min(image.shape[1], x2)
                        
                        head_roi = image[head_y1:head_y2, head_x1:head_x2]
                        
                        # 색상 기반 헬멧 감지
                        has_helmet, helmet_conf = self._detect_helmet_by_color(head_roi)
                        
                        detection = {
                            'bbox': [float(x1), float(y1), float(x2), float(y2)],
                            'class_id': int(0 if has_helmet else 1),
                            'class_name': 'helmet' if has_helmet else 'no-helmet',
                            'person_confidence': float(person_conf),
                            'helmet_confidence': float(helmet_conf)
                        }

                        if has_helmet:
                            helmets.append(detection)
                        else:
                            no_helmets.append(detection)

        except Exception as e:
            logger.error(f"Error during helmet detection: {e}")

        total_persons = len(helmets) + len(no_helmets)
        compliance_rate = (len(helmets) / total_persons * 100) if total_persons > 0 else 0

        result = {
            'helmets': helmets,
            'no_helmets': no_helmets,
            'helmet_count': len(helmets),
            'no_helmet_count': len(no_helmets),
            'total_persons': total_persons,
            'helmet_compliance_rate': compliance_rate,
            'detection_method': 'custom_model' if self.use_custom_model else 'color_based'
        }
        
        # ✅ NumPy 타입을 Python 기본 타입으로 변환
        return convert_numpy_types(result)

    def check_compliance(self, image: np.ndarray, required_rate: float = 100.0) -> bool:
        """
        Check if helmet compliance meets the required rate.

        Args:
            image: Input image as numpy array (BGR format)
            required_rate: Required compliance rate (0-100)

        Returns:
            True if compliance rate meets or exceeds required rate
        """
        result = self.detect_helmets(image)
        return result['helmet_compliance_rate'] >= required_rate

    def process_video(self, video_path: str, sample_interval: int = 30,
                     required_compliance: float = 100.0) -> Dict:
        """
        Process a video file and check helmet compliance in sampled frames.

        Args:
            video_path: Path to the video file
            sample_interval: Process every Nth frame (default: 30)
            required_compliance: Required compliance rate (0-100)

        Returns:
            Dictionary containing:
                - total_frames: total number of frames in video
                - sampled_frames: number of frames analyzed
                - compliance_per_frame: list of compliance rates per frame
                - average_compliance: average compliance rate across all frames
                - min_compliance: minimum compliance rate
                - max_compliance: maximum compliance rate
                - overall_pass: whether video meets required compliance
                - violations: list of frame numbers with violations
                - detection_method: method used for detection
        """
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise ValueError(f"Cannot open video file: {video_path}")

        frame_count = 0
        compliance_per_frame = []
        violations = []

        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                if frame_count % sample_interval == 0:
                    result = self.detect_helmets(frame)
                    compliance_rate = result['helmet_compliance_rate']
                    compliance_per_frame.append(compliance_rate)

                    if compliance_rate < required_compliance:
                        violations.append({
                            'frame_number': int(frame_count),
                            'compliance_rate': float(compliance_rate),
                            'helmet_count': int(result['helmet_count']),
                            'no_helmet_count': int(result['no_helmet_count'])
                        })

                    logger.debug(f"Frame {frame_count}: {compliance_rate:.1f}% compliance")

                frame_count += 1

        finally:
            cap.release()

        if not compliance_per_frame:
            result = {
                'total_frames': int(frame_count),
                'sampled_frames': 0,
                'compliance_per_frame': [],
                'average_compliance': 0.0,
                'min_compliance': 0.0,
                'max_compliance': 0.0,
                'overall_pass': False,
                'violations': [],
                'detection_method': 'custom_model' if self.use_custom_model else 'color_based'
            }
            return convert_numpy_types(result)

        average_compliance = np.mean(compliance_per_frame)

        result = {
            'total_frames': int(frame_count),
            'sampled_frames': int(len(compliance_per_frame)),
            'compliance_per_frame': [float(x) for x in compliance_per_frame],
            'average_compliance': float(average_compliance),
            'min_compliance': float(min(compliance_per_frame)),
            'max_compliance': float(max(compliance_per_frame)),
            'overall_pass': bool(average_compliance >= required_compliance),
            'violations': violations,
            'detection_method': 'custom_model' if self.use_custom_model else 'color_based'
        }
        
        # ✅ NumPy 타입을 Python 기본 타입으로 변환
        return convert_numpy_types(result)

    def draw_detections(self, image: np.ndarray, detections: Dict) -> np.ndarray:
        """
        Draw bounding boxes and labels on the image.

        Args:
            image: Input image as numpy array (BGR format)
            detections: Detection dictionary from detect_helmets()

        Returns:
            Image with drawn bounding boxes
        """
        img_copy = image.copy()

        # Draw helmets in green
        for det in detections['helmets']:
            x1, y1, x2, y2 = [int(coord) for coord in det['bbox']]
            confidence = det['confidence']
            cv2.rectangle(img_copy, (x1, y1), (x2, y2), (0, 255, 0), 2)
            label = f"Helmet: {confidence:.2f}"
            cv2.putText(img_copy, label, (x1, y1 - 10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

        # Draw no-helmets in red
        for det in detections['no_helmets']:
            x1, y1, x2, y2 = [int(coord) for coord in det['bbox']]
            confidence = det['confidence']
            cv2.rectangle(img_copy, (x1, y1), (x2, y2), (0, 0, 255), 2)
            label = f"NO HELMET: {confidence:.2f}"
            cv2.putText(img_copy, label, (x1, y1 - 10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)

        # Add compliance rate text
        compliance_rate = detections['helmet_compliance_rate']
        method = detections.get('detection_method', 'unknown')
        status_text = f"Compliance: {compliance_rate:.1f}% ({method})"
        status_color = (0, 255, 0) if compliance_rate == 100 else (0, 0, 255)
        cv2.putText(img_copy, status_text, (10, 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 1, status_color, 2)

        return img_copy