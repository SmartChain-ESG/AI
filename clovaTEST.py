import base64, time, uuid, os
from pathlib import Path
import requests
from fastapi import FastAPI, UploadFile, File, HTTPException
from dotenv import load_dotenv
import uvicorn

# 1. 환경 변수 로드 (최상단)
load_dotenv()

INVOKE_URL = os.getenv("CLOVA_INVOKE_URL")
X_OCR_SECRET = os.getenv("CLOVA_OCR_SECRET")

app = FastAPI()

def call_clova_bytes(file_bytes: bytes, fmt: str, name: str, enable_table: bool=True) -> dict:
    """CLOVA OCR API 실제 호출 함수"""
    print(f"--- API 호출 시작 ---")
    print(f"URL: {INVOKE_URL}")
    print(f"Secret Key 존재여부: {bool(X_OCR_SECRET)}")

    if not INVOKE_URL or not X_OCR_SECRET:
        raise HTTPException(status_code=500, detail=".env 파일의 설정값을 확인해주세요.")

    payload = {
        "version": "V2",
        "requestId": str(uuid.uuid4()),
        "timestamp": int(time.time()*1000),
        "lang": "ko",
        "enableTableDetection": enable_table,
        "images": [{
            "format": fmt,
            "name": name,
            "data": base64.b64encode(file_bytes).decode("utf-8")
        }]
    }
    headers = {"Content-Type": "application/json", "X-OCR-SECRET": X_OCR_SECRET}
    
    try:
        r = requests.post(INVOKE_URL, headers=headers, json=payload, timeout=120)
        if r.status_code >= 400:
            print(f"CLOVA 에러 메시지: {r.text}")
            raise HTTPException(status_code=500, detail=f"CLOVA API Error: {r.text}")
        return r.json()
    except Exception as e:
        print(f"호출 중 예외 발생: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

def normalize_raw(ocr: dict) -> dict:
    """OCR 결과 표준화 로직"""
    images = ocr.get("images", [])
    if not images: return {"fields": [], "tables": []}
    img = images[0]
    
    fields = [{
        "text": f.get("inferText"),
        "conf": f.get("inferConfidence"),
        "bbox": f.get("boundingPoly"),
        "lineBreak": f.get("lineBreak", False),
    } for f in (img.get("fields") or [])]

    tables_out = []
    for t in (img.get("tables") or []):
        cells_out = []
        for c in (t.get("cells") or []):
            cell_text = " ".join(
                w.get("inferText","")
                for line in (c.get("cellTextLines") or [])
                for w in (line.get("cellWords") or [])
            ).strip()
            cells_out.append({
                "rowIndex": c.get("rowIndex"),
                "columnIndex": c.get("columnIndex"),
                "rowSpan": c.get("rowSpan"),
                "columnSpan": c.get("columnSpan"),
                "conf": c.get("inferConfidence"),
                "text": cell_text,
            })
        tables_out.append({"cells": cells_out})
    return {"fields": fields, "tables": tables_out}

@app.post("/ocr")
async def ocr_endpoint(file: UploadFile = File(...)):
    name = file.filename
    ext = Path(name).suffix.lower().lstrip(".")
    if ext not in ("jpg","jpeg","png","pdf","tif","tiff"):
        raise HTTPException(status_code=400, detail="지원하지 않는 확장자입니다.")
    
    data = await file.read()
    ocr = call_clova_bytes(data, fmt="jpg" if ext in ("jpg", "jpeg") else ext, name=name)
    raw = normalize_raw(ocr)
    return {"raw": raw, "clova": ocr}

if __name__ == "__main__":
    print("=== 서버 구동 준비 중 ===")
    print(f"INVOKE_URL 로드 상태: {bool(INVOKE_URL)}")
    uvicorn.run(app, host="127.0.0.1", port=8000)