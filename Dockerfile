FROM python:3.11-slim

# 작업 디렉토리 설정
WORKDIR /app

# 시스템 패키지 업데이트 및 필요 패키지 설치 (ReportLab용 의존성 포함)
RUN apt-get update && apt-get install -y \
    curl \
    libfreetype6-dev \
    libjpeg-dev \
    libpng-dev \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# 비root 사용자 생성 (보안을 위해)
RUN groupadd -r appuser && useradd -r -g appuser appuser

# 환경변수 설정
ENV PYTHONPATH=/app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV MODEL_SERVER_URL=http://host.docker.internal:8001

# requirements.txt 복사 및 의존성 설치 (레이어 캐싱 최적화)
COPY requirements.txt .

# pip 업그레이드 및 의존성 설치
RUN python -m pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt

# 애플리케이션 코드 복사
COPY . .

# 데이터 디렉토리 권한 설정
RUN mkdir -p /app/app/data && \
    chown -R appuser:appuser /app

# 비root 사용자로 전환
USER appuser

# 포트 노출
EXPOSE 8000

# 헬스체크 추가 (curl 대신 python 사용 - 더 안전)
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/docs')" || exit 1

# 애플리케이션 실행
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]