# Google Sheets <-> SQLite Sync Service
# 양방향 동기화 서비스 Docker 이미지

FROM python:3.11-slim

LABEL maintainer="GGP Academy"
LABEL description="Google Sheets <-> SQLite bidirectional sync service"

# 작업 디렉토리 설정
WORKDIR /app

# 시스템 의존성 설치
RUN apt-get update && apt-get install -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Python 의존성 설치
COPY requirements-sync.txt .
RUN pip install --no-cache-dir -r requirements-sync.txt

# 소스 코드 복사
COPY src/archive_analyzer/sheets_sync.py /app/sheets_sync.py

# 볼륨 마운트 포인트
# /data - SQLite 데이터베이스
# /config - GCP 서비스 계정 JSON

VOLUME ["/data", "/config"]

# 환경 변수 기본값
ENV SYNC_INTERVAL=30
ENV SPREADSHEET_ID=""
ENV DB_PATH="/data/pokervod.db"
ENV CREDENTIALS_PATH="/config/gcp-service-account.json"

# 헬스체크
HEALTHCHECK --interval=60s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sqlite3; sqlite3.connect('${DB_PATH}').execute('SELECT 1')" || exit 1

# 엔트리포인트 스크립트
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["--daemon"]
