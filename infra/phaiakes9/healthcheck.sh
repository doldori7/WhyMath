#!/usr/bin/env bash
# Phaiakes9 — Ollama 헬스체크
#
# 3단계 검증:
#   1. HTTP 200    — GET /
#   2. 모델 로드    — GET /api/tags 응답에 디폴트 모델 포함
#   3. 간단 generate — POST /api/generate 로 "2+2=" 응답 수신
#
# 환경변수:
#   WHYMATH_OLLAMA_HOST     ollama 호스트 (디폴트: http://localhost:11434)
#   WHYMATH_BENCH_MODEL     검증할 모델 (디폴트: qwen2.5-math:7b-instruct)
#   WHYMATH_HEALTH_TIMEOUT  generate 타임아웃 초 (디폴트: 30)
#
# 종료 코드:
#   0  3단계 모두 통과
#   1  1단계 실패 (HTTP 도달 불가)
#   2  2단계 실패 (모델 미로드)
#   3  3단계 실패 (generate 실패 또는 타임아웃)

set -euo pipefail

readonly HOST="${WHYMATH_OLLAMA_HOST:-http://localhost:11434}"
readonly MODEL="${WHYMATH_BENCH_MODEL:-qwen2.5-math:7b-instruct}"
readonly TIMEOUT_SEC="${WHYMATH_HEALTH_TIMEOUT:-30}"

echo "[healthcheck] 대상 호스트: ${HOST}"
echo "[healthcheck] 검증 모델: ${MODEL}"
echo "[healthcheck] generate 타임아웃: ${TIMEOUT_SEC}초"
echo ""

# ---- 1) HTTP 200 -----------------------------------------------------------
echo "[healthcheck] (1/3) HTTP 200 확인..."
http_status="$(curl -fsS -o /dev/null -w '%{http_code}' -m 5 "${HOST}/" || echo '000')"
if [[ "${http_status}" != "200" ]]; then
    echo "[healthcheck] ❌ HTTP ${http_status} — ollama 서비스가 ${HOST} 에서 응답하지 않습니다." >&2
    echo "[healthcheck]    → sudo systemctl status ollama" >&2
    echo "[healthcheck]    → sudo journalctl -u ollama -n 50" >&2
    exit 1
fi
echo "[healthcheck] ✅ HTTP 200"

# ---- 2) 모델 로드 ----------------------------------------------------------
echo ""
echo "[healthcheck] (2/3) /api/tags 에서 모델 존재 확인..."
tags_json="$(curl -fsS -m 10 "${HOST}/api/tags" || echo '{}')"
# jq가 있으면 정밀 비교, 없으면 grep 폴백
if command -v jq >/dev/null 2>&1; then
    found="$(echo "${tags_json}" | jq -r --arg m "${MODEL}" '.models[]? | select(.name == $m) | .name' | head -n1)"
else
    # 부분 일치 폴백 (qwen2.5-math:7b-instruct 같은 패턴이 본문에 등장하면 통과)
    if echo "${tags_json}" | grep -q "\"${MODEL}\""; then
        found="${MODEL}"
    else
        found=""
    fi
fi
if [[ -z "${found}" ]]; then
    echo "[healthcheck] ❌ 모델 '${MODEL}' 이 풀되어 있지 않습니다." >&2
    echo "[healthcheck]    → bash pull_models.sh" >&2
    echo "[healthcheck]    → 또는 WHYMATH_BENCH_MODEL 로 다른 모델 지정" >&2
    echo "[healthcheck] 현재 풀된 모델 목록:" >&2
    if command -v jq >/dev/null 2>&1; then
        echo "${tags_json}" | jq -r '.models[]?.name' >&2 || true
    else
        echo "${tags_json}" >&2
    fi
    exit 2
fi
echo "[healthcheck] ✅ 모델 발견: ${found}"

# ---- 3) generate 호출 ------------------------------------------------------
echo ""
echo "[healthcheck] (3/3) 간단 generate 호출 ('2+2='): 최대 ${TIMEOUT_SEC}초 대기..."
prompt_body=$(cat <<JSON
{"model": "${MODEL}", "prompt": "2+2=", "stream": false, "options": {"num_predict": 32}}
JSON
)
gen_response="$(curl -fsS -m "${TIMEOUT_SEC}" -H 'Content-Type: application/json' \
    -d "${prompt_body}" "${HOST}/api/generate" 2>&1 || echo 'CURL_FAILED')"

if [[ "${gen_response}" == "CURL_FAILED" ]] || [[ -z "${gen_response}" ]]; then
    echo "[healthcheck] ❌ generate 호출 실패 또는 타임아웃 (${TIMEOUT_SEC}초)" >&2
    exit 3
fi

# 응답에 "response" 필드가 있어야 함
if command -v jq >/dev/null 2>&1; then
    response_text="$(echo "${gen_response}" | jq -r '.response // empty')"
else
    response_text="$(echo "${gen_response}" | grep -o '"response":"[^"]*"' || echo '')"
fi

if [[ -z "${response_text}" ]]; then
    echo "[healthcheck] ❌ generate 응답에 'response' 필드 없음" >&2
    echo "[healthcheck] 응답 본문 (앞 500자):" >&2
    echo "${gen_response}" | head -c 500 >&2
    echo "" >&2
    exit 3
fi

# 응답이 너무 길면 잘라서 출력
response_preview="${response_text:0:120}"
echo "[healthcheck] ✅ generate 성공: '${response_preview}'..."

echo ""
echo "[healthcheck] ─────────────────────────────────────"
echo "[healthcheck] ✅ 3단계 헬스체크 모두 통과"
echo "[healthcheck] 다음 단계: bash benchmark/run_bench.sh"
exit 0
