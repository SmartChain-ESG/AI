"""
Helmet Detection Module
Detects whether people are wearing safety helmets in TBM video frames
"""

import cv2
import numpy as np
from typing import List, Dict, Tuple, Optional
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class HelmetDetector:
    """
    Detects safety helmets and classifies whether persons are wearing them.
    Uses YOLOv8 trained on helmet detection dataset.
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

        # Class mapping for helmet detection
        # Typical classes: 0=helmet, 1=no-helmet, 2=person
        self.class_names = {
            0: 'helmet',
            1: 'no-helmet',
            2: 'person'
        }

        try:
            from ultralytics import YOLO
            if model_path and Path(model_path).exists():
                self.model = YOLO(model_path)
                logger.info(f"Loaded helmet detection model from {model_path}")
            else:
                logger.warning("No custom helmet model provided. Please train or provide a model.")
                # Note: You need to train or download a helmet detection model
                # Example datasets: https://universe.roboflow.com/search?q=helmet
        except ImportError:
            logger.error("ultralytics package not installed. Please install: pip install ultralytics")
            raise
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            raise

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
        """
        if self.model is None:
            raise RuntimeError("Model not initialized. Please provide a trained helmet detection model.")

        results = self.model(image, conf=self.confidence_threshold)

        helmets = []
        no_helmets = []

        for result in results:
            boxes = result.boxes
            for box in boxes:
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                confidence = float(box.conf[0].cpu().numpy())
                class_id = int(box.cls[0].cpu().numpy())

                detection = {
                    'bbox': [float(x1), float(y1), float(x2), float(y2)],
                    'confidence': confidence,
                    'class_id': class_id,
                    'class_name': self.class_names.get(class_id, 'unknown')
                }

                if class_id == 0:  # helmet
                    helmets.append(detection)
                elif class_id == 1:  # no-helmet
                    no_helmets.append(detection)

        total_persons = len(helmets) + len(no_helmets)
        compliance_rate = (len(helmets) / total_persons * 100) if total_persons > 0 else 0

        return {
            'helmets': helmets,
            'no_helmets': no_helmets,
            'helmet_count': len(helmets),
            'no_helmet_count': len(no_helmets),
            'total_persons': total_persons,
            'helmet_compliance_rate': compliance_rate
        }

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
                            'frame_number': frame_count,
                            'compliance_rate': compliance_rate,
                            'helmet_count': result['helmet_count'],
                            'no_helmet_count': result['no_helmet_count']
                        })

                    logger.debug(f"Frame {frame_count}: {compliance_rate:.1f}% compliance")

                frame_count += 1

        finally:
            cap.release()

        if not compliance_per_frame:
            return {
                'total_frames': frame_count,
                'sampled_frames': 0,
                'compliance_per_frame': [],
                'average_compliance': 0,
                'min_compliance': 0,
                'max_compliance': 0,
                'overall_pass': False,
                'violations': []
            }

        average_compliance = np.mean(compliance_per_frame)

        return {
            'total_frames': frame_count,
            'sampled_frames': len(compliance_per_frame),
            'compliance_per_frame': compliance_per_frame,
            'average_compliance': average_compliance,
            'min_compliance': min(compliance_per_frame),
            'max_compliance': max(compliance_per_frame),
            'overall_pass': average_compliance >= required_compliance,
            'violations': violations
        }

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
        status_text = f"Compliance: {compliance_rate:.1f}%"
        status_color = (0, 255, 0) if compliance_rate == 100 else (0, 0, 255)
        cv2.putText(img_copy, status_text, (10, 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 1, status_color, 2)

        return img_copy
