from __future__ import annotations

from fastapi import HTTPException, status


class FileFetchError(HTTPException):
    def __init__(self, uri: str, detail: str = "Failed to fetch file"):
        super().__init__(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"{detail}: {uri}",
        )


class UnsupportedDomainError(HTTPException):
    def __init__(self, domain: str):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported domain: {domain}",
        )


class UnsupportedFileTypeError(HTTPException):
    def __init__(self, ext: str):
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported file type: {ext}",
        )
