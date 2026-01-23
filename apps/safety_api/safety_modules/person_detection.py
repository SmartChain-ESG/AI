"""
Person Detection Module
Detects and counts people in TBM video frames using YOLOv8
"""

import cv2
import numpy as np
from typing import List, Dict, Tuple, Optional
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class PersonDetector:
    """
    Detects and counts people in video frames using object detection.
    Uses YOLOv8 for person detection.
    """

    def __init__(self, model_path: Optional[str] = None, confidence_threshold: float = 0.5):
        """
        Initialize the PersonDetector.

        Args:
            model_path: Path to the trained model file. If None, uses default YOLOv8n.
            confidence_threshold: Minimum confidence score for detections (0.0 to 1.0)
        """
        self.confidence_threshold = confidence_threshold
        self.model_path = model_path
        self.model = None

        try:
            from ultralytics import YOLO
            if model_path and Path(model_path).exists():
                self.model = YOLO(model_path)
                logger.info(f"Loaded custom model from {model_path}")
            else:
                self.model = YOLO('yolov8n.pt')  # Default pretrained model
                logger.info("Loaded default YOLOv8n model")
        except ImportError:
            logger.error("ultralytics package not installed. Please install: pip install ultralytics")
            raise
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            raise

    def detect_persons(self, image: np.ndarray) -> List[Dict]:
        """
        Detect persons in a single image frame.

        Args:
            image: Input image as numpy array (BGR format)

        Returns:
            List of detection dictionaries with keys:
                - bbox: [x1, y1, x2, y2] bounding box coordinates
                - confidence: detection confidence score
                - class_id: class ID (0 for person in COCO dataset)
        """
        if self.model is None:
            raise RuntimeError("Model not initialized")

        results = self.model(image, conf=self.confidence_threshold, classes=[0])  # class 0 = person

        detections = []
        for result in results:
            boxes = result.boxes
            for box in boxes:
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                confidence = float(box.conf[0].cpu().numpy())
                class_id = int(box.cls[0].cpu().numpy())

                detections.append({
                    'bbox': [float(x1), float(y1), float(x2), float(y2)],
                    'confidence': confidence,
                    'class_id': class_id
                })

        return detections

    def count_persons(self, image: np.ndarray) -> int:
        """
        Count the number of persons detected in an image.

        Args:
            image: Input image as numpy array (BGR format)

        Returns:
            Number of persons detected
        """
        detections = self.detect_persons(image)
        return len(detections)

    def process_video(self, video_path: str, sample_interval: int = 30) -> Dict:
        """
        Process a video file and detect persons in sampled frames.

        Args:
            video_path: Path to the video file
            sample_interval: Process every Nth frame (default: 30, i.e., ~1 fps for 30fps video)

        Returns:
            Dictionary containing:
                - total_frames: total number of frames processed
                - detections_per_frame: list of detection counts per sampled frame
                - average_count: average number of persons detected
                - max_count: maximum number of persons detected
                - min_count: minimum number of persons detected
        """
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise ValueError(f"Cannot open video file: {video_path}")

        frame_count = 0
        detections_per_frame = []

        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                if frame_count % sample_interval == 0:
                    count = self.count_persons(frame)
                    detections_per_frame.append(count)
                    logger.debug(f"Frame {frame_count}: {count} persons detected")

                frame_count += 1

        finally:
            cap.release()

        if not detections_per_frame:
            return {
                'total_frames': frame_count,
                'detections_per_frame': [],
                'average_count': 0,
                'max_count': 0,
                'min_count': 0
            }

        return {
            'total_frames': frame_count,
            'sampled_frames': len(detections_per_frame),
            'detections_per_frame': detections_per_frame,
            'average_count': np.mean(detections_per_frame),
            'max_count': max(detections_per_frame),
            'min_count': min(detections_per_frame)
        }

    def draw_detections(self, image: np.ndarray, detections: List[Dict]) -> np.ndarray:
        """
        Draw bounding boxes on the image.

        Args:
            image: Input image as numpy array (BGR format)
            detections: List of detection dictionaries from detect_persons()

        Returns:
            Image with drawn bounding boxes
        """
        img_copy = image.copy()

        for det in detections:
            x1, y1, x2, y2 = [int(coord) for coord in det['bbox']]
            confidence = det['confidence']

            cv2.rectangle(img_copy, (x1, y1), (x2, y2), (0, 255, 0), 2)

            label = f"Person: {confidence:.2f}"
            cv2.putText(img_copy, label, (x1, y1 - 10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

        return img_copy
