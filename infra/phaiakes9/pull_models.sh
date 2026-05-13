#!/usr/bin/env bash
# Phaiakes9 — Qwen 수학 모델 풀 스크립트
#
# 사용:
#   bash pull_models.sh                     # 디폴트: 7B만
#   WHYMATH_MODELS=mid bash pull_models.sh  # 7B + 32B
#   WHYMATH_MODELS=all bash pull_models.sh  # 7B + 32B + 72B
#   WHYMATH_MODELS_OVERRIDE="qwen3-math:7b,foo:bar" bash pull_models.sh
#       # 콤마 구분 임의 모델 ID 지정 (Qwen3-Math 실재 확인 시 대체)
#
# 멱등성:
#   - 이미 풀된 모델은 ollama가 알아서 스킵·증분 다운로드
#   - 실패 모델 1개로 전체 종료 코드 0 유지 (다른 모델은 사용 가능하도록)
#     단, 디폴트(7B) 1개도 못 풀면 종료 코드 1
#
# 환경변수:
#   WHYMATH_MODELS           default | 7b | mid | all  (디폴트: default == 7b)
#   WHYMATH_MODELS_OVERRIDE  콤마 구분 임의 모델 리스트 (다른 변수 무시)
#   WHYMATH_OLLAMA_HOST      ollama 호스트 (디폴트: http://localhost:11434)

set -euo pipefail

# ---- 환경변수 기본값 ---------------------------------------------------------
readonly MODE="${WHYMATH_MODELS:-default}"
readonly OVERRIDE="${WHYMATH_MODELS_OVERRIDE:-}"
readonly OLLAMA_HOST="${WHYMATH_OLLAMA_HOST:-http://localhost:11434}"

# ---- 모델 카탈로그 -----------------------------------------------------------
# Qwen2.5-Math-Instruct 시리즈는 ollama.ai/library/qwen2-math 또는
# https://ollama.com/library/qwen2.5 계열에서 실재 확인 가능.
# Qwen3-Math 가설 모델이 실재할 경우 WHYMATH_MODELS_OVERRIDE 로 직접 지정.
readonly MODEL_7B="qwen2.5-math:7b-instruct"
readonly MODEL_32B="qwen2.5-math:32b-instruct"
# 72B 모델은 Qwen2.5-Math 라인에 72B가 없을 수 있어 일반 Qwen2.5 72B를 폴백으로 사용
readonly MODEL_72B_PRIMARY="qwen2.5-math:72b-instruct"
readonly MODEL_72B_FALLBACK="qwen2.5:72b-instruct"

# ---- 풀 대상 결정 ------------------------------------------------------------
declare -a TARGETS=()
if [[ -n "${OVERRIDE}" ]]; then
    # 오버라이드: 콤마 구분 입력
    IFS=',' read -r -a TARGETS <<< "${OVERRIDE}"
    echo "[pull_models] 오버라이드 모드: ${#TARGETS[@]}개 모델"
else
    case "${MODE}" in
        default|7b)
            TARGETS=("${MODEL_7B}")
            ;;
        mid)
            TARGETS=("${MODEL_7B}" "${MODEL_32B}")
            ;;
        all)
            TARGETS=("${MODEL_7B}" "${MODEL_32B}" "${MODEL_72B_PRIMARY}")
            ;;
        *)
            echo "[pull_models] ❌ 알 수 없는 WHYMATH_MODELS=${MODE}" >&2
            echo "[pull_models] 허용 값: default | 7b | mid | all" >&2
            exit 1
            ;;
    esac
fi

echo "[pull_models] 모드: ${MODE} / 오버라이드: ${OVERRIDE:-(없음)}"
echo "[pull_models] 풀 대상 (${#TARGETS[@]}개):"
for m in "${TARGETS[@]}"; do echo "  - ${m}"; done

# ---- ollama 명령 확인 --------------------------------------------------------
if ! command -v ollama >/dev/null 2>&1; then
    echo "[pull_models] ❌ ollama 명령을 찾을 수 없습니다. install_ollama.sh 부터 실행하세요." >&2
    exit 1
fi

# ---- 서버 도달 확인 (선택적, 실패해도 진행) ---------------------------------
if ! curl -fsS -m 3 "${OLLAMA_HOST}" >/dev/null 2>&1; then
    echo "[pull_models] ⚠️  ${OLLAMA_HOST} 에 도달 불가. ollama 서비스가 떠 있는지 확인하세요."
    echo "[pull_models]    (CLI로 풀은 가능하지만 헬스체크가 실패할 수 있습니다)"
fi

# ---- 풀 실행 -----------------------------------------------------------------
declare -i success_count=0
declare -i fail_count=0
declare -a failed_models=()

pull_one() {
    local model="$1"
    echo ""
    echo "[pull_models] ⏬ ${model} 풀 시작..."
    if OLLAMA_HOST="${OLLAMA_HOST}" ollama pull "${model}"; then
        echo "[pull_models] ✅ ${model} 완료"
        success_count+=1
        return 0
    else
        echo "[pull_models] ⚠️  ${model} 실패 (다음 모델로 계속)"
        fail_count+=1
        failed_models+=("${model}")
        return 1
    fi
}

for model in "${TARGETS[@]}"; do
    pull_one "${model}" || true
done

# ---- 72B 폴백 ----------------------------------------------------------------
# all 모드에서 72B Math 모델이 실패하면 일반 Qwen2.5-72B 시도
if [[ "${MODE}" == "all" && -z "${OVERRIDE}" ]]; then
    if printf '%s\n' "${failed_models[@]}" | grep -qx "${MODEL_72B_PRIMARY}"; then
        echo ""
        echo "[pull_models] ↪️  72B Math 미존재 — 일반 ${MODEL_72B_FALLBACK} 폴백 시도"
        pull_one "${MODEL_72B_FALLBACK}" || true
    fi
fi

# ---- 결과 요약 ---------------------------------------------------------------
echo ""
echo "[pull_models] ─────────────────────────────────────"
echo "[pull_models] 완료: ${success_count}건 / 실패: ${fail_count}건"
if (( fail_count > 0 )); then
    echo "[pull_models] 실패 모델:"
    for m in "${failed_models[@]}"; do echo "  - ${m}"; done
    echo "[pull_models] (재시도하거나 WHYMATH_MODELS_OVERRIDE 로 실재 모델명 지정)"
fi

# ---- 디폴트 모델 풀 실패 시 비정상 종료 -------------------------------------
if (( success_count == 0 )); then
    echo "[pull_models] ❌ 단 하나의 모델도 풀하지 못했습니다." >&2
    exit 1
fi

# ---- 풀된 모델 목록 출력 -----------------------------------------------------
echo ""
echo "[pull_models] 현재 로컬 모델 목록:"
OLLAMA_HOST="${OLLAMA_HOST}" ollama list || true

echo ""
echo "[pull_models] 다음 단계: bash healthcheck.sh"
