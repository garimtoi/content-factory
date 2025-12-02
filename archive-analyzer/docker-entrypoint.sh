#!/bin/bash
set -e

# 환경 변수로 설정 파일 업데이트
if [ -n "$SPREADSHEET_ID" ]; then
    echo "Using SPREADSHEET_ID: $SPREADSHEET_ID"
fi

if [ -n "$SYNC_INTERVAL" ]; then
    echo "Sync interval: ${SYNC_INTERVAL}s"
fi

# Python 스크립트 실행
exec python /app/sheets_sync.py \
    --interval "${SYNC_INTERVAL:-30}" \
    "$@"
