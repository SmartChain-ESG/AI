from __future__ import annotations

import logging
import uuid

from fastapi import Request


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


def get_request_id(request: Request) -> str:
    rid = request.headers.get("x-request-id")
    return rid or str(uuid.uuid4())