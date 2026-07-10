#!/usr/bin/env bash
# S1 시연 정리 — uvicorn 종료 + throwaway Postgres(볼륨째) 제거.
# 사용법: 리포 루트에서  bash scripts/demo/stop_demo.sh
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
COMPOSE_FILE="$REPO_ROOT/docker-compose.demo.yml"
PID_FILE="$REPO_ROOT/.demo_uvicorn.pid"

if [ -f "$PID_FILE" ]; then
  PID="$(cat "$PID_FILE")"
  if kill -0 "$PID" 2>/dev/null; then
    echo "▶ uvicorn 종료(pid=$PID)…"
    kill "$PID" 2>/dev/null || true
  fi
  rm -f "$PID_FILE"
fi

echo "▶ throwaway Postgres 제거(볼륨 포함)…"
docker compose -f "$COMPOSE_FILE" down -v

echo "정리 완료."
