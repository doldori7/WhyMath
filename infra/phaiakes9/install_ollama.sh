#!/usr/bin/env bash
# Phaiakes9 — Ollama 설치 스크립트 (멱등·재실행 안전)
#
# 사용: bash install_ollama.sh
#
# 동작:
#   1. 이미 설치되어 있으면 버전만 출력하고 종료 (멱등)
#   2. 미설치 시 공식 install.sh 호출
#   3. 설치 후 버전 확인
#
# 환경변수:
#   OLLAMA_INSTALL_URL  설치 스크립트 URL (디폴트: https://ollama.com/install.sh)
#                       프록시·미러 환경에서 덮어쓰기 가능

set -euo pipefail

readonly INSTALL_URL="${OLLAMA_INSTALL_URL:-https://ollama.com/install.sh}"

echo "[install_ollama] Ollama 설치 점검 시작"
echo "[install_ollama] 대상 머신: $(uname -srm)"

# 1) 멱등성 — 이미 설치되어 있으면 스킵
if command -v ollama >/dev/null 2>&1; then
    current_version="$(ollama --version 2>&1 || true)"
    echo "[install_ollama] ✅ Ollama가 이미 설치되어 있습니다: ${current_version}"
    echo "[install_ollama] (재설치를 원하면 sudo rm $(command -v ollama) 후 다시 실행하세요)"
    exit 0
fi

# 2) 필수 도구 확인
if ! command -v curl >/dev/null 2>&1; then
    echo "[install_ollama] ❌ curl이 필요합니다. 'sudo apt-get install -y curl' 후 다시 실행하세요." >&2
    exit 1
fi

# 3) 공식 설치 스크립트 호출
echo "[install_ollama] Ollama 미설치 — 공식 설치 스크립트 다운로드 중..."
echo "[install_ollama] URL: ${INSTALL_URL}"

# install.sh 자체가 sudo를 요구할 수 있으므로 -E 로 환경 보존
# (사용자가 sudo로 실행하지 않아도 install.sh 내부에서 sudo prompt를 띄움)
if ! curl -fsSL "${INSTALL_URL}" | sh; then
    echo "[install_ollama] ❌ 설치 실패. 네트워크/프록시 확인 후 재시도하세요." >&2
    echo "[install_ollama] 수동 설치: https://github.com/ollama/ollama/releases" >&2
    exit 1
fi

# 4) 설치 검증
if ! command -v ollama >/dev/null 2>&1; then
    echo "[install_ollama] ❌ 설치는 완료된 듯 하나 'ollama' 명령을 찾지 못했습니다." >&2
    echo "[install_ollama] PATH 확인 또는 새 셸을 열어 'ollama --version' 실행하세요." >&2
    exit 1
fi

echo "[install_ollama] ✅ 설치 완료: $(ollama --version 2>&1 || true)"
echo "[install_ollama] 다음 단계:"
echo "  1) sudo cp systemd/ollama.service /etc/systemd/system/ollama.service"
echo "  2) sudo systemctl daemon-reload && sudo systemctl enable --now ollama"
echo "  3) bash pull_models.sh"
