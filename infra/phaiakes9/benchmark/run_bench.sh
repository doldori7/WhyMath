#!/usr/bin/env bash
# Phaiakes9 — 벤치마크 실행 래퍼.
#
# bench_latency.py 를 호출하여 결과를 results/YYYY-MM-DD_HHMMSS.json 에 저장.
#
# 사용:
#   bash run_bench.sh
#   WHYMATH_BENCH_MODEL=qwen2.5-math:32b-instruct bash run_bench.sh
#   WHYMATH_BENCH_CONCURRENCY=1,4 bash run_bench.sh
#
# 환경변수:
#   WHYMATH_OLLAMA_HOST       ollama 호스트
#   WHYMATH_BENCH_MODEL       모델 ID
#   WHYMATH_BENCH_CONCURRENCY 콤마 구분 동시도
#   WHYMATH_BENCH_NUM_PREDICT 호출당 생성 토큰 한도
#   WHYMATH_BENCH_GATE_MS     게이트 p50 한도 ms
#   WHYMATH_BENCH_PYTHON      python 인터프리터 (디폴트: python3)
#   WHYMATH_BENCH_NO_HEALTH=1 헬스체크 스킵

set -euo pipefail

# 스크립트 자기 위치 기준 경로 (workdir 무관)
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
readonly SCRIPT_DIR
readonly INFRA_DIR="$(dirname "${SCRIPT_DIR}")"
readonly RESULTS_DIR="${INFRA_DIR}/results"
readonly PYTHON_BIN="${WHYMATH_BENCH_PYTHON:-python3}"

echo "[run_bench] 벤치마크 시작"
echo "[run_bench] 스크립트 위치: ${SCRIPT_DIR}"
echo "[run_bench] 결과 디렉토리: ${RESULTS_DIR}"
echo ""

# ---- 사전 점검 -------------------------------------------------------------
if ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
    echo "[run_bench] ❌ ${PYTHON_BIN} 명령을 찾을 수 없습니다." >&2
    echo "[run_bench]    sudo apt-get install -y python3 python3-pip" >&2
    exit 1
fi

# ollama Python 클라이언트 확인
if ! "${PYTHON_BIN}" -c "import ollama" >/dev/null 2>&1; then
    echo "[run_bench] ⚠️  Python 'ollama' 패키지 없음. 설치를 시도합니다..."
    if "${PYTHON_BIN}" -m pip install --user ollama >/dev/null 2>&1; then
        echo "[run_bench] ✅ ollama 설치 완료"
    else
        echo "[run_bench] ❌ ollama 설치 실패. 수동으로:" >&2
        echo "[run_bench]    ${PYTHON_BIN} -m pip install --user ollama" >&2
        exit 1
    fi
fi

# ---- 헬스체크 (선택) -------------------------------------------------------
if [[ "${WHYMATH_BENCH_NO_HEALTH:-0}" != "1" ]]; then
    echo "[run_bench] 헬스체크 실행 (스킵하려면 WHYMATH_BENCH_NO_HEALTH=1)..."
    if ! bash "${INFRA_DIR}/healthcheck.sh"; then
        echo "[run_bench] ❌ 헬스체크 실패. 위 에러 확인 후 재시도하세요." >&2
        exit 1
    fi
    echo ""
fi

# ---- 결과 디렉토리 ---------------------------------------------------------
mkdir -p "${RESULTS_DIR}"
TS="$(date '+%Y-%m-%d_%H%M%S')"
OUTPUT="${RESULTS_DIR}/${TS}.json"

# ---- 벤치마크 실행 ---------------------------------------------------------
echo "[run_bench] bench_latency.py 호출..."
echo ""
set +e
"${PYTHON_BIN}" "${SCRIPT_DIR}/bench_latency.py" --output "${OUTPUT}"
exit_code=$?
set -e

echo ""
echo "[run_bench] ─────────────────────────────────────"
echo "[run_bench] 종료 코드: ${exit_code}"
if [[ -f "${OUTPUT}" ]]; then
    echo "[run_bench] 결과 파일: ${OUTPUT}"
    # JSON 핵심 지표만 추출 (jq 있을 때)
    if command -v jq >/dev/null 2>&1; then
        echo "[run_bench] 핵심 지표:"
        jq -r '
            "  모델: \(.model)",
            "  표본: \(.samples)개",
            "  게이트 통과 (p50 < \(.gate_p50_ms)ms): \(.gate_p50_under_2s)",
            "  동시도별:",
            (.concurrency_runs[] | "    c=\(.concurrent): p50=\(.p50_ms)ms / p90=\(.p90_ms)ms / p99=\(.p99_ms)ms / tok_s=\(.tokens_per_sec)")
        ' "${OUTPUT}"
    fi
else
    echo "[run_bench] ⚠️  결과 파일이 생성되지 않았습니다." >&2
fi

echo ""
case "${exit_code}" in
    0) echo "[run_bench] ✅ 게이트 통과. MEMORY.md 결정 로그에 결과를 첨부하세요." ;;
    1) echo "[run_bench] ❌ 게이트 미달 (p50 >= 한도). 양자화/하드웨어/모델 점검." ;;
    *) echo "[run_bench] ❌ 벤치마크 실행 에러." ;;
esac

exit "${exit_code}"
