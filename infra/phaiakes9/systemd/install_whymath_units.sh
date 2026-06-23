#!/usr/bin/env bash
# WhyMath / Phaiakes9 — systemd 유닛 설치 헬퍼(whymath-api·whymath-worker).
#
# 멱등: 유닛 복사 → daemon-reload → enable. env 파일은 *덮어쓰지 않는다*(시크릿 보존) —
# 없을 때만 example을 깔고 0600 권한을 준다(값은 운영자가 채운다).
#
# 사용:
#   sudo bash infra/phaiakes9/systemd/install_whymath_units.sh           # 설치 + enable(미기동)
#   sudo bash infra/phaiakes9/systemd/install_whymath_units.sh --now     # 설치 + enable --now
#
# 주의:
#   - root로 실행(systemd 디렉토리 쓰기·daemon-reload). 'whymath' 사용자/그룹이 있어야 한다.
#   - 기동 전에 /etc/whymath/whymath.env의 WHYMATH_JWT_SECRET_KEY 등을 채울 것(CLAUDE.md 보안).
set -euo pipefail

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly SYSTEMD_DIR="/etc/systemd/system"
readonly ENV_DIR="/etc/whymath"
readonly ENV_FILE="${ENV_DIR}/whymath.env"
readonly UNITS=("whymath-api.service" "whymath-worker.service")

ENABLE_NOW=0
if [[ "${1:-}" == "--now" ]]; then
    ENABLE_NOW=1
fi

if [[ "$(id -u)" -ne 0 ]]; then
    echo "[install] ⚠️ root 권한이 필요합니다 — sudo로 실행하세요." >&2
    exit 1
fi

# ① env 파일 — 없을 때만 example 복사(시크릿 덮어쓰기 금지).
install -d -m 700 "${ENV_DIR}"
if [[ -f "${ENV_FILE}" ]]; then
    echo "[install] ✅ 기존 ${ENV_FILE} 유지(덮어쓰지 않음)."
else
    install -m 600 "${SCRIPT_DIR}/whymath.env.example" "${ENV_FILE}"
    echo "[install] ⚠️ ${ENV_FILE} 생성(example) — WHYMATH_JWT_SECRET_KEY 등 값을 채우세요."
fi

# ② 유닛 파일 복사.
for unit in "${UNITS[@]}"; do
    install -m 644 "${SCRIPT_DIR}/${unit}" "${SYSTEMD_DIR}/${unit}"
    echo "[install] ✅ ${SYSTEMD_DIR}/${unit}"
done

# ③ 리로드 + enable.
systemctl daemon-reload
for unit in "${UNITS[@]}"; do
    if [[ "${ENABLE_NOW}" -eq 1 ]]; then
        systemctl enable --now "${unit}"
    else
        systemctl enable "${unit}"
    fi
done

echo "[install] 완료 — 상태: systemctl status ${UNITS[*]}"
echo "[install]        로그: journalctl -u whymath-api -f"
