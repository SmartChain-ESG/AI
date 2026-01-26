# 1. 팀 권장 3.11-slim 베이스로 수정
FROM python:3.11-slim

# 2. 필수 시스템 패키지 설치 (의존성 빌드용)
RUN apt-get update && apt-get install -y build-essential && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 3. 모델 파일 폴더 미리 생성 (팀 공지 준수)
RUN mkdir -p /app/models

# 4. 의존성 설치 (용량 최적화)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. 소스 코드 복사
COPY . .

# 6. 환경 변수 설정
ENV PYTHONPATH=/app

# 7. 컴플라이언스 팀 전용 포트 노출
EXPOSE 8002

# 8. 진입점 및 포트 고정 (팀 공지 준수)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8002"]