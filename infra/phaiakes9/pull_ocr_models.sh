#!/usr/bin/env bash
# Phaiakes9 — L5 OCR 모델 풀 스크립트 (검출·인식 라이브 모델)
#
# 코드(L5 OCR)는 전부 머지됐고(PR #310·#314·#316·#317·#318), 남은 건 *실 모델 연결*뿐이다.
# 이 스크립트가 그 라이브 단계를 turnkey화한다. 라이브 검증 순서는 OCR_LIVE_VERIFICATION.md 참조.
#
# 사용:
#   bash pull_ocr_models.sh                  # 전체(VL + 한국어 rec). rapid-layout/rapid-latex/
#                                            # TexTeller는 첫 사용 시 자동 다운로드(아래 메모)
#   WHYMATH_OCR_VL_MODEL=qwen3-vl:4b bash pull_ocr_models.sh   # 더 가벼운 VL(3.3GB)로 오버라이드
#   WHYMATH_OCR_MODEL_DIR=/srv/whymath/models bash pull_ocr_models.sh  # 한국어 모델 위치
#
# 멱등성:
#   - ollama는 이미 풀된 모델을 증분 스킵. curl은 -C - 로 이어받기.
#   - VL 풀 실패해도 한국어 다운로드는 계속(부분 성공 허용). 단 둘 다 실패면 종료 코드 1.
#
# 환경변수:
#   WHYMATH_OCR_VL_MODEL   Qwen3-VL Ollama 태그 (디폴트: qwen3-vl:8b)
#                          ⚠️ 이 값은 router.py LOCAL_MODEL_MATRIX[(VISION,FAST)]와 *반드시 일치*
#                             해야 한다(현재 "qwen3-vl:8b"·6.1GB). 실제 ollama 태그가 다르면 코드도 함께 수정.
#                             태그(2026-06-23 확인): 2b·4b·8b(=latest)·30b·32b 로컬 / 235b-cloud.
#   WHYMATH_OCR_MODEL_DIR  한국어 rec 모델 디렉토리 (디폴트: ./models/korean)
#                          ⚠️ 서버의 WHYMATH_OCR_MODEL_DIR와 동일해야 한국어 모델이 로드된다.
#                             파일명은 recognize._rapidocr_rec_kwargs 규약 고정:
#                             korean_PP-OCRv4_rec.onnx · korean_dict.txt
#   WHYMATH_OLLAMA_HOST    ollama 호스트 (디폴트: http://localhost:11434)

set -euo pipefail

readonly VL_MODEL="${WHYMATH_OCR_VL_MODEL:-qwen3-vl:8b}"
readonly MODEL_DIR="${WHYMATH_OCR_MODEL_DIR:-./models/korean}"
readonly OLLAMA_HOST="${WHYMATH_OLLAMA_HOST:-http://localhost:11434}"
export OLLAMA_HOST

# 한국어 PP-OCRv4 인식 모델 출처(Phase A README §4-1 검증):
#   https://huggingface.co/cycloneboy/korean_PP-OCRv4_rec_infer
readonly KO_BASE="https://huggingface.co/cycloneboy/korean_PP-OCRv4_rec_infer/resolve/main"

ok=0
fail=0

# ── ① Qwen3-VL (멀티모달 수식 인식 — L3 라우터 경유 VISION 패밀리) ──────────────
echo "[pull_ocr] ① Qwen3-VL 풀: ${VL_MODEL} (@ ${OLLAMA_HOST})"
if command -v ollama >/dev/null 2>&1; then
    if ollama pull "${VL_MODEL}"; then
        echo "[pull_ocr]   ✅ ${VL_MODEL}"
        ok=$((ok + 1))
    else
        echo "[pull_ocr]   ⚠️ ${VL_MODEL} 풀 실패 — ollama에 해당 태그가 없을 수 있습니다."
        echo "[pull_ocr]      실제 태그를 확인해 WHYMATH_OCR_VL_MODEL로 지정하고,"
        echo "[pull_ocr]      router.py LOCAL_MODEL_MATRIX[(VISION,FAST)]도 동일하게 맞추세요."
        fail=$((fail + 1))
    fi
else
    echo "[pull_ocr]   ⚠️ ollama 미설치 — install_ollama.sh 먼저 실행하세요."
    fail=$((fail + 1))
fi

# ── ② 한국어 PP-OCRv4 인식 모델 + 사전 (텍스트 인식 한국어 wiring) ──────────────
echo "[pull_ocr] ② 한국어 rec 모델 → ${MODEL_DIR}"
mkdir -p "${MODEL_DIR}"
if curl -fsSL -C - "${KO_BASE}/model.onnx" -o "${MODEL_DIR}/korean_PP-OCRv4_rec.onnx" \
    && curl -fsSL -C - "${KO_BASE}/korean_dict.txt" -o "${MODEL_DIR}/korean_dict.txt"; then
    echo "[pull_ocr]   ✅ korean_PP-OCRv4_rec.onnx · korean_dict.txt"
    ok=$((ok + 1))
else
    echo "[pull_ocr]   ⚠️ 한국어 모델 다운로드 실패 — 네트워크/URL 확인(HuggingFace 도달성)."
    fail=$((fail + 1))
fi

# ── ③ 자동 다운로드 모델 (명시 pull 불요·첫 사용 시 받음) ──────────────────────
cat <<NOTE
[pull_ocr] ③ 아래는 첫 사용 시 자동 다운로드(여기서 명시 pull 불요):
    - rapidocr-onnxruntime : 검출 + (기본)텍스트 인식 ONNX        ([ocr] extra)
    - rapid-latex-ocr      : 경량 수식 인식 ONNX                   ([ocr] extra)
    - rapid-layout (PP)    : MFD 수식 영역 검출 PP 모델 ONNX        ([ocr-layout] extra)
    - OleehyO/TexTeller    : 고정밀 수식 인식(~1.2GB·transformers)  ([ocr-heavy] extra)
  설치: pip install -e ".[ocr,ocr-layout,ocr-heavy]"
  (오프라인/핀 환경은 HF 캐시를 미리 채우거나 모델을 ${MODEL_DIR} 등에 배치 후 경로 지정.)
NOTE

echo "[pull_ocr] 완료 — 성공 ${ok} · 실패 ${fail}"
# 둘 다(VL·한국어) 실패하면 비정상 종료. 하나라도 성공하면 0(부분 성공 허용).
if [[ "${ok}" -eq 0 ]]; then
    exit 1
fi
exit 0
