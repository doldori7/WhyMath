# L5 OCR 라이브 검증 런북 (Phaiakes9)

OCR 코드는 전부 머지됐다(PR #310 Phase A · #314 MFD · #316 TexTeller/한국어 · #317 L3 멀티모달 ·
#318 Qwen3-VL). CI는 *가짜 모델*로 hermetic 검증만 한다(샌드박스에 GPU·모델 없음). 이 문서는
**실 모델을 연결해 라이브로 검증**하는 단계다 — Phaiakes9(GPU)에서 실행한다.

> 원칙: 모든 무거운 의존은 *지연 import*다. 미설치 백엔드를 고르면 *조용한 폴백 없이* 명확한
> RuntimeError가 난다(CLAUDE.md). 모델 파일은 레포에 커밋하지 않는다(배포 시 pull).

---

## 0. 사전 조건

- Phaiakes9 + Ollama 데몬 가동(`install_ollama.sh` → `ollama serve`). GPU 활성(`GPU_ACTIVATION_FOLLOWUP.md`).
- 백엔드 venv. `cd src/backend`.

## 1. 의존성 설치 (extras)

```bash
# 경량(검출·rapid-latex) + MFD(rapid-layout) + 고정밀(TexTeller·Qwen3-VL transformers)
pip install -e ".[dev,ocr,ocr-layout,ocr-heavy]"
```

| extra | 받는 것 | 쓰는 백엔드 |
|---|---|---|
| `ocr` | rapidocr-onnxruntime · rapid-latex-ocr · pillow · numpy | 검출·텍스트·경량 수식 |
| `ocr-layout` | rapid-layout (PP·**Apache-2.0**) | MFD 수식 영역 검출 |
| `ocr-heavy` | transformers · torch | TexTeller·Qwen3-VL 프로세서 |

## 2. 모델 받기

```bash
# Qwen3-VL(ollama) + 한국어 PP-OCRv4 rec 모델. rapid-layout/rapid-latex/TexTeller는 첫 사용 자동.
bash infra/phaiakes9/pull_ocr_models.sh
# VL 태그가 다르면:  WHYMATH_OCR_VL_MODEL=<실제태그> bash infra/phaiakes9/pull_ocr_models.sh
```

> ⚠️ **VL 태그 일치**: `WHYMATH_OCR_VL_MODEL`(또는 pull한 ollama 태그)은 `l3/router.py`의
> `LOCAL_MODEL_MATRIX[(ModelFamily.VISION, LocalModelTier.FAST)]`(현재 `"qwen3-vl:8b"`·`:latest`
> 드리프트 회피 명시 핀)와 **반드시 같아야** 라우터→provider 모델 해석이 맞는다. 실제 태그가
> 다르면 둘 다 수정. 태그(2026-06-23 확인): 2b·4b·8b(=latest)·30b·32b 로컬 / 235b-cloud.
> ⚠️ **한국어 파일명 고정**: `korean_PP-OCRv4_rec.onnx`·`korean_dict.txt`(`recognize._rapidocr_rec_kwargs`
> 규약). `WHYMATH_OCR_MODEL_DIR`는 pull 위치와 서버 설정이 같아야 한다.

## 3. 환경변수 (config.Settings·`WHYMATH_` prefix)

| env | 값 | 의미 |
|---|---|---|
| `WHYMATH_OCR_ENABLED` | `true` | 부팅 시 OCR 부품 1회 로드(app.state) |
| `WHYMATH_OCR_DETECTOR` | `paddle` / `mfd` | 줄검출 / **MFD 수식 영역 검출** |
| `WHYMATH_OCR_MFD_MODEL_TYPE` | `pp_layout_cdla`(기본) | MFD PP 모델(PP 계열만·AGPL 차단) |
| `WHYMATH_OCR_RECOGNIZER_BACKEND` | `rapid_latex` / `texteller` / `qwen_vl` | 수식 인식기 |
| `WHYMATH_OCR_LANGUAGE` | `korean` | 텍스트 인식 한국어 모델 |
| `WHYMATH_OCR_MODEL_DIR` | `./models/korean` | 한국어 rec 모델 위치(pull과 동일) |
| `WHYMATH_OLLAMA_HOST` | `http://localhost:11434` | Qwen3-VL용 L3 provider(Ollama) |

`qwen_vl` 백엔드는 **L3 라우터 경유**다 — app.state의 provider/cache/trace가 자동 주입된다(직접
Ollama 호출 없음). 미주입/미구성이면 명확한 RuntimeError.

## 4. @integration 테스트 (실 모델)

```bash
cd src/backend
WHYMATH_RUN_INTEGRATION=1 WHYMATH_OCR_ENABLED=true \
  .venv/bin/python -m pytest -c pyproject.toml \
  ../../tests/backend/api/test_ocr_integration.py -v
```

- `test_ocr_integration`은 `[ocr]` 미설치면 `importorskip`로 skip된다 — 설치돼 있으면 실행된다.
- 합성 수식 이미지를 파이프라인에 넣어 *구조(OcrResult)*가 나오는지 확인(내용 정확도는 비단언).

## 5. 풀 스택 스모크 (서버 → /v1/ocr)

```bash
WHYMATH_OCR_ENABLED=true WHYMATH_OCR_DETECTOR=mfd WHYMATH_OCR_LANGUAGE=korean \
WHYMATH_OCR_RECOGNIZER_BACKEND=qwen_vl WHYMATH_OCR_MODEL_DIR=./models/korean \
  uvicorn whymath_backend.app:create_app --factory --host 0.0.0.0 --port 8000

# 손글씨/인쇄 수식 이미지 1장 → 구조화 OcrResult(regions: bbox·content_type·latex·confidence)
curl -s -X POST http://localhost:8000/v1/ocr \
  -H "Authorization: Bearer <consented_user_token>" \
  -F "image=@문제.png" | jq .
```

검증 포인트: 응답이 *구조*(regions 배열에 bbox·content_type·latex·confidence)이고 **맨 문자열이
아니다**(표현≠의미). `plain_latex`가 채워지고, MFD가 2D 수식을 한 덩어리로 잡는지(검출 박스 수)
확인. 이후 `plain_latex`/`overall_confidence`/`solution_steps`를 `/v1/coach/sessions`에 넘기면
"사진 → OCR → 진단 → Polya" 흐름(coach.py 무변경 핸드오프).

## 6. 백엔드별 권장 조합

| 상황 | DETECTOR | RECOGNIZER | 비고 |
|---|---|---|---|
| 빠른 프로토타입 | `paddle` | `rapid_latex` | 경량 ONNX·즉답 |
| 2D 수식 정확도 | `mfd` | `texteller` | MFD 검출 + 고정밀 인식 |
| 손글씨·그래프·멀티모달 | `mfd` | `qwen_vl` | VL이 이미지 통째 이해(L3 경유) |

## 7. 트러블슈팅

- `RuntimeError: ...가 필요합니다 — pip install -e ".[ocr...]"` → 해당 extra 미설치. §1 재실행.
- VL 풀 실패 / 라우팅 모델 불일치 → §2 ⚠️ VL 태그 일치 확인(router.py 매트릭스 ↔ ollama 태그).
- 한국어가 깨짐(`YYklo昱`) → `WHYMATH_OCR_LANGUAGE=korean` + `WHYMATH_OCR_MODEL_DIR`에 한국어 모델
  파일명(고정) 존재 확인. 검출·VL은 언어 무관.
- AGPL 가드: `WHYMATH_OCR_MFD_MODEL_TYPE`에 `yolov8*`/`doclayout*`를 주면 RuntimeError(의도된 차단·
  PP 계열 Apache-2.0만 허용). `docs/data/licensing_safety.md` 참조.
