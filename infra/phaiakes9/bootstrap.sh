#!/usr/bin/env bash
# Phaiakes9 — Ubuntu 24.04 초기 부트스트랩 (M1.0a Phase D + E)
#
# 사용:
#   bash bootstrap.sh                       # 모든 단계
#   WHYMATH_SKIP_ROCM=1 bash bootstrap.sh   # ROCm 단계 스킵 (CPU 폴백)
#   WHYMATH_LAN_CIDR="10.0.0.0/24" bash bootstrap.sh   # Ollama LAN 허용 대역 지정
#
# 멱등성:
#   - 모든 단계는 재실행 안전. 이미 적용된 설정은 변경 안 함.
#   - 실패 단계에서 즉시 중단 (set -euo pipefail)
#
# 환경변수:
#   WHYMATH_LAN_CIDR      Ollama 11434 포트 허용 대역 (디폴트: 192.168.0.0/16)
#   WHYMATH_SKIP_ROCM     "1" 이면 ROCm 설치 스킵 (CPU 전용 운영)
#   WHYMATH_TIMEZONE      시간대 (디폴트: Asia/Seoul)

set -euo pipefail

readonly LAN_CIDR="${WHYMATH_LAN_CIDR:-192.168.0.0/16}"
readonly SKIP_ROCM="${WHYMATH_SKIP_ROCM:-0}"
readonly TIMEZONE="${WHYMATH_TIMEZONE:-Asia/Seoul}"
readonly LOG_PREFIX="[bootstrap]"

require_root_or_sudo() {
    if [[ "${EUID}" -ne 0 ]] && ! command -v sudo >/dev/null 2>&1; then
        echo "${LOG_PREFIX} ❌ root 권한 또는 sudo 가 필요합니다." >&2
        exit 1
    fi
}

run_sudo() {
    if [[ "${EUID}" -eq 0 ]]; then
        "$@"
    else
        sudo "$@"
    fi
}

step() {
    echo ""
    echo "${LOG_PREFIX} ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "${LOG_PREFIX} $*"
    echo "${LOG_PREFIX} ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
}

# ============================================================================
# 1. 사전 점검
# ============================================================================
step "1/8 사전 점검"

require_root_or_sudo

if ! grep -q "Ubuntu 24" /etc/os-release 2>/dev/null; then
    echo "${LOG_PREFIX} ⚠️  Ubuntu 24.x 가 아닙니다. 계속 진행하지만 일부 단계가 실패할 수 있습니다."
    grep "^PRETTY_NAME" /etc/os-release || true
fi

echo "${LOG_PREFIX} 호스트명: $(hostnamectl --static 2>/dev/null || hostname)"
echo "${LOG_PREFIX} 커널: $(uname -r)"
echo "${LOG_PREFIX} LAN 대역 (Ollama 허용): ${LAN_CIDR}"
echo "${LOG_PREFIX} ROCm 스킵: ${SKIP_ROCM}"
echo "${LOG_PREFIX} 시간대: ${TIMEZONE}"

# ============================================================================
# 2. 필수 도구 설치
# ============================================================================
step "2/8 필수 도구 설치"

run_sudo apt-get update -qq
run_sudo apt-get install -y -qq \
    curl jq git \
    build-essential \
    ufw chrony \
    unattended-upgrades \
    htop lsof \
    ca-certificates gnupg lsb-release
echo "${LOG_PREFIX} ✅ 필수 도구 설치 완료"

# ============================================================================
# 3. 시간대 + chrony
# ============================================================================
step "3/8 시간대 설정 (${TIMEZONE}) + chrony"

run_sudo timedatectl set-timezone "${TIMEZONE}"
run_sudo systemctl enable --now chrony

echo "${LOG_PREFIX} 현재 시각: $(date)"
echo "${LOG_PREFIX} ✅ 시간 동기화 활성화"

# ============================================================================
# 4. sshd 하드닝
# ============================================================================
step "4/8 sshd 하드닝 (root 차단·비밀번호 차단·키 인증만)"

SSHD_DROPIN="/etc/ssh/sshd_config.d/00-whymath.conf"

# authorized_keys 가 비어 있으면 사용자가 잠길 수 있음 — 사전 점검
if [[ ! -s "${HOME}/.ssh/authorized_keys" ]]; then
    echo "${LOG_PREFIX} ❌ ~/.ssh/authorized_keys 가 비어 있습니다." >&2
    echo "${LOG_PREFIX}    sshd 하드닝 전에 공개키를 등록해야 합니다 (SETUP_GUIDE.md Phase C 참조)." >&2
    echo "${LOG_PREFIX}    잠금 방지를 위해 이 단계를 건너뜁니다." >&2
else
    run_sudo tee "${SSHD_DROPIN}" >/dev/null <<'EOF'
# WhyMath / Phaiakes9 sshd 하드닝 (bootstrap.sh 생성)
PermitRootLogin no
PasswordAuthentication no
PubkeyAuthentication yes
ChallengeResponseAuthentication no
KbdInteractiveAuthentication no
UsePAM yes
X11Forwarding no
ClientAliveInterval 300
ClientAliveCountMax 2
MaxAuthTries 3
EOF
    run_sudo chmod 644 "${SSHD_DROPIN}"
    if run_sudo sshd -t; then
        run_sudo systemctl reload ssh
        echo "${LOG_PREFIX} ✅ sshd 설정 적용 (${SSHD_DROPIN})"
    else
        echo "${LOG_PREFIX} ❌ sshd 설정 검증 실패. 드롭인 파일 제거." >&2
        run_sudo rm -f "${SSHD_DROPIN}"
        exit 1
    fi
fi

# ============================================================================
# 5. ufw 방화벽
# ============================================================================
step "5/8 ufw 방화벽 (SSH 22 + Ollama 11434 LAN 한정)"

run_sudo ufw --force reset >/dev/null
run_sudo ufw default deny incoming >/dev/null
run_sudo ufw default allow outgoing >/dev/null
run_sudo ufw allow 22/tcp comment 'SSH' >/dev/null
run_sudo ufw allow from "${LAN_CIDR}" to any port 11434 proto tcp comment 'Ollama LAN' >/dev/null
run_sudo ufw --force enable >/dev/null

run_sudo ufw status verbose
echo "${LOG_PREFIX} ✅ 방화벽 활성"

# ============================================================================
# 6. unattended-upgrades (보안 패치만)
# ============================================================================
step "6/8 unattended-upgrades (보안 패치 자동, 커널은 수동)"

run_sudo tee /etc/apt/apt.conf.d/52whymath-unattended >/dev/null <<'EOF'
// WhyMath: 보안 업데이트만 자동, 일반 업그레이드·커널은 수동 (운영 중 재부팅 방지)
Unattended-Upgrade::Allowed-Origins {
    "${distro_id}:${distro_codename}-security";
    "${distro_id}ESMApps:${distro_codename}-apps-security";
    "${distro_id}ESM:${distro_codename}-infra-security";
};
Unattended-Upgrade::Package-Blacklist {
    "linux-image-*";
    "linux-headers-*";
    "linux-generic*";
};
Unattended-Upgrade::Automatic-Reboot "false";
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
EOF
run_sudo systemctl enable --now unattended-upgrades
echo "${LOG_PREFIX} ✅ unattended-upgrades 활성"

# ============================================================================
# 7. AMD ROCm (Strix Halo) — 옵션
# ============================================================================
step "7/8 AMD ROCm 설치 (Strix Halo)"

if [[ "${SKIP_ROCM}" == "1" ]]; then
    echo "${LOG_PREFIX} ⏭️  WHYMATH_SKIP_ROCM=1 — ROCm 단계 스킵 (CPU 폴백 운영)"
else
    if command -v rocminfo >/dev/null 2>&1; then
        echo "${LOG_PREFIX} rocminfo 이미 설치됨 — 스킵"
    else
        # AMD 공식 설치 헬퍼. 24.04 PPA 기준 (배포판에 따라 URL 조정 필요할 수 있음)
        ROCM_DEB_URL="https://repo.radeon.com/amdgpu-install/latest/ubuntu/noble/amdgpu-install_6.2.60200-1_all.deb"
        TMP_DEB="/tmp/amdgpu-install.deb"
        if curl -fsSL -o "${TMP_DEB}" "${ROCM_DEB_URL}"; then
            run_sudo apt-get install -y -qq "${TMP_DEB}" || true
            # --no-dkms: 커널 모듈은 Ubuntu 메인라인 amdgpu 사용 (DKMS 충돌 회피)
            if run_sudo amdgpu-install -y --usecase=rocm,opencl --no-dkms; then
                echo "${LOG_PREFIX} ✅ ROCm 설치 완료"
            else
                echo "${LOG_PREFIX} ⚠️  ROCm 설치 일부 실패 — CPU 폴백으로 진행 가능"
            fi
            rm -f "${TMP_DEB}"
        else
            echo "${LOG_PREFIX} ⚠️  ROCm 설치 헬퍼 다운로드 실패 — CPU 폴백으로 진행 가능"
            echo "${LOG_PREFIX}    수동 설치: https://rocm.docs.amd.com/projects/install-on-linux/"
        fi
    fi

    # Strix Halo gfx1151 환경변수 (시스템 전역)
    HSA_ENV="/etc/profile.d/whymath-rocm.sh"
    if ! [[ -f "${HSA_ENV}" ]]; then
        run_sudo tee "${HSA_ENV}" >/dev/null <<'EOF'
# WhyMath: Strix Halo (gfx1151) ROCm 호환 강제
# ROCm 공식 지원 목록에 없을 경우 11.5.1 로 강제. 작동 확인 후 제거 가능.
export HSA_OVERRIDE_GFX_VERSION=11.5.1
EOF
        run_sudo chmod 644 "${HSA_ENV}"
        echo "${LOG_PREFIX} ✅ HSA_OVERRIDE_GFX_VERSION=11.5.1 환경 등록 (${HSA_ENV})"
    fi
fi

# ============================================================================
# 8. 검증 요약
# ============================================================================
step "8/8 검증 요약"

echo ""
echo "${LOG_PREFIX} 호스트명     : $(hostnamectl --static 2>/dev/null || hostname)"
echo "${LOG_PREFIX} 시간대       : $(timedatectl show -p Timezone --value)"
echo "${LOG_PREFIX} sshd 상태    : $(systemctl is-active ssh)"
echo "${LOG_PREFIX} ufw 상태     : $(run_sudo ufw status | head -n1)"
echo "${LOG_PREFIX} chrony 상태  : $(systemctl is-active chrony)"
if command -v rocminfo >/dev/null 2>&1; then
    gfx=$(rocminfo 2>/dev/null | grep -E "^\s*Name:\s*gfx" | head -n1 | awk '{print $2}')
    echo "${LOG_PREFIX} ROCm GPU     : ${gfx:-감지되지 않음}"
else
    echo "${LOG_PREFIX} ROCm GPU     : 미설치 (CPU 모드)"
fi

echo ""
echo "${LOG_PREFIX} ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "${LOG_PREFIX} ✅ bootstrap 완료"
echo "${LOG_PREFIX}"
echo "${LOG_PREFIX} 다음 단계:"
echo "${LOG_PREFIX}   1) sudo reboot         # 커널·드라이버 반영"
echo "${LOG_PREFIX}   2) ssh phaiakes9       # Windows PC에서 재접속 검증"
echo "${LOG_PREFIX}   3) bash install_ollama.sh"
echo "${LOG_PREFIX}   4) README.md §2 따라 Ollama·모델·벤치마크"
echo "${LOG_PREFIX} ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
