"""YOLO 기반 인원수 감지 — yolo26n_crowdhuman_fewshot.pt."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from ultralytics import YOLO

_MODEL_PATH = Path(__file__).parent / "yolo26n_crowdhuman_fewshot.pt"
_model: YOLO | None = None


def _get_model() -> YOLO:
    global _model
    if _model is None:
        _model = YOLO(str(_MODEL_PATH))
    return _model


def count_persons(image_data: bytes) -> int:
    """이미지 바이트 → person class 감지 수 반환."""
    tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
    try:
        tmp.write(image_data)
        tmp.close()
        model = _get_model()
        results = model(tmp.name, verbose=False)
        count = sum(1 for box in results[0].boxes if int(box.cls) == 0)
        return count
    finally:
        os.unlink(tmp.name)
