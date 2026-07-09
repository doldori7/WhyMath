#!/usr/bin/env bash
# S1 탈출 게이트 ① — 실기기 학습 루프 15분 시연 원커맨드 기동.
#
# 하드 블로커 3종을 한 번에 해소한다(docs/architecture/s1_e2e_demo_script.md §1):
#   ① 인증  — WHYMATH_DEMO_AUTH_ENABLED=true + /v1/auth/demo/callback으로 실 JWT 자동 발급 → DEMO_TOKEN
#   ② API_URL — LAN IP를 탐지해 정확한 `flutter run --dart-define=API_URL=...` 명령을 출력
#   ③ LLM 키 — /status로 LLM 모드(라이브/Ollama/결정론) 보고(없어도 루프는 결정론 경로로 완주)
#
# ★로컬 시연 호스트 전용. JWT 시크릿은 매 실행 런타임 생성(하드코딩 0), DB는 throwaway compose PG.
# 시연 후 정리: scripts/demo/stop_demo.sh
#
# 사용법: 리포 루트에서  bash scripts/demo/run_demo.sh
set -euo pipefail

# ── 경로·상수 ────────────────────────────────────────────────────────────────
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"
BACKEND_DIR="$REPO_ROOT/src/backend"
COMPOSE_FILE="$REPO_ROOT/docker-compose.demo.yml"
PORT="${WHYMATH_DEMO_PORT:-8000}"
PID_FILE="$REPO_ROOT/.demo_uvicorn.pid"

# ── 시연 전용 환경(런타임 생성 시크릿·하드코딩 0) ───────────────────────────────
# 호스트 포트 55432 — docker-compose.demo.yml과 동일(로컬 PostgreSQL의 표준 5432와 충돌 회피).
export WHYMATH_DATABASE_URL="${WHYMATH_DATABASE_URL:-postgresql+asyncpg://whymath@127.0.0.1:55432/whymath}"
export WHYMATH_DEMO_AUTH_ENABLED=true
export WHYMATH_JWT_SECRET_KEY="${WHYMATH_JWT_SECRET_KEY:-$(python3 -c 'import secrets;print(secrets.token_urlsafe(48))')}"

echo "▶ [1/6] throwaway Postgres 기동…"
docker compose -f "$COMPOSE_FILE" up -d demo-db
echo "  · PG healthy 대기…"
for _ in $(seq 1 60); do
  if docker compose -f "$COMPOSE_FILE" exec -T demo-db pg_isready -U whymath -d whymath >/dev/null 2>&1; then
    echo "  · PG ready."
    break
  fi
  sleep 1
done

echo "▶ [2/6] alembic 스키마 마이그레이션(upgrade head)…"
( cd "$BACKEND_DIR" && alembic -c alembic.ini upgrade head )

echo "▶ [3/6] 진단 문제 시드(멱등)…"
python3 "$REPO_ROOT/scripts/demo/seed_demo.py"

echo "▶ [4/6] backend(uvicorn) 기동 — 0.0.0.0:$PORT (실기기 LAN 도달)…"
( cd "$BACKEND_DIR" && exec uvicorn "whymath_backend.app:create_app" --factory \
    --host 0.0.0.0 --port "$PORT" ) &
echo $! > "$PID_FILE"
echo "  · /health 대기…"
for _ in $(seq 1 60); do
  if curl -sf "http://127.0.0.1:$PORT/health" >/dev/null 2>&1; then
    echo "  · backend ready."
    break
  fi
  sleep 1
done

echo "▶ [5/6] 데모 토큰 발급(/v1/auth/demo/callback) — 데모 사용자 lazy upsert…"
TOKEN_JSON="$(curl -sf -X POST "http://127.0.0.1:$PORT/v1/auth/demo/callback" \
  -H 'content-type: application/json' \
  -d '{"code":"demo","redirect_uri":"https://demo/cb"}')"
ACCESS_TOKEN="$(printf '%s' "$TOKEN_JSON" | python3 -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')"
if [ -z "${ACCESS_TOKEN:-}" ]; then
  echo "✗ 토큰 발급 실패 — 응답: $TOKEN_JSON" >&2
  exit 1
fi

echo "▶ [6/6] LLM 모드·인증 sanity·실행 명령…"
# LLM 모드 보고(블로커 ③) — 라이브/Ollama면 발문 LLM, 아니면 결정론 degraded(루프는 완주).
STATUS_JSON="$(curl -sf "http://127.0.0.1:$PORT/status" 2>/dev/null || echo '{}')"
python3 - "$STATUS_JSON" <<'PY'
import json, sys
try:
    s = json.loads(sys.argv[1] or "{}")
except Exception:
    s = {}
local = bool(s.get("reachable"))
cloud = bool(s.get("cloud_configured"))
if local or cloud:
    src = " + ".join(x for x, on in (("Ollama(로컬)", local), ("클라우드", cloud)) if on)
    print(f"  · LLM 모드: 라이브({src}) — 코치 발문/문제 생성 LLM 사용.")
else:
    print("  · LLM 모드: 결정론(degraded) — 키/Ollama 없음. 코치 발문·검증 신호는 결정론 경로로 표시(루프 완주 가능).")
PY

# 인증+시드+비미성년 게이트 통합 sanity(앱 없이 1회 확인).
if curl -sf -H "Authorization: Bearer $ACCESS_TOKEN" "http://127.0.0.1:$PORT/v1/me/next-problem" >/dev/null 2>&1; then
  echo "  · sanity: /v1/me/next-problem 200 — 인증·시드·비미성년 게이트 OK."
else
  echo "  · sanity: /v1/me/next-problem 비200 — 시드/LLM 상태 확인 필요(루프는 진행 가능할 수 있음)."
fi

# LAN IP 탐지(실기기가 붙을 주소). 실패 시 수동 안내.
LAN_IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
[ -z "${LAN_IP:-}" ] && LAN_IP="<이 머신의 LAN IP: 'hostname -I' 또는 'ipconfig getifaddr en0'>"

cat <<EOF

════════════════════════════════════════════════════════════════════════
 실기기 시연 준비 완료. 패드에서 아래 명령으로 앱을 실행하세요(src/mobile에서):

   flutter run \\
     --dart-define=API_URL=http://$LAN_IP:$PORT \\
     --dart-define=DEMO_TOKEN=$ACCESS_TOKEN

 앱이 이미 인증된 상태로 부팅됩니다(router가 /problem로 이동) →
 온보딩→진단→문제→코치(영속 세션)→CoachSignalCard 검증 신호 = 1루프 완주.
 시연 대본: docs/architecture/s1_e2e_demo_script.md

 ⚠ 게이트 G-kiki-device-demo는 Kiki가 실기기 15분 루프를 *녹화*할 때까지 PENDING입니다.
 정리: bash scripts/demo/stop_demo.sh
════════════════════════════════════════════════════════════════════════
EOF
