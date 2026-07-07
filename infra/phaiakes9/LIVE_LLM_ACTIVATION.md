# 라이브 LLM 활성화 런북 — 새 Phaiakes9 (라이젠 AI Max+ 395 · Windows 11)

> **대상 하드웨어**: GMKtec AMD 라이젠 AI Max+ 395 (Strix Halo) · Radeon 8060S iGPU(RDNA 3.5·40CU)
> · 통합 LPDDR5X(최대 128GB) · Windows 11 Pro.
> **목적**: 이 머신에서 WhyMath의 **라이브 LLM 파이프라인 3종**(발문 다양화 rephrase ·
> LLM 동등문제 생성 · misconception judge shadow)을 실제로 켜는 정확한 절차.
> **근거**: 전부 코드 정본에서 추출(라우터 매트릭스 `l3/router.py` · provider `l3/providers/` ·
> config env var `config.py`). 기존 `SETUP_GUIDE.md`는 Linux(systemd) 전제 — 본 런북은 Windows
> 우선, Linux 이관 시 SETUP_GUIDE로 합류.
>
> **PowerShell 규율**: `&&` 없음 · 한 줄씩 실행 (세션 인계 규약).

---

## 0. 이 하드웨어가 바꾸는 것 (한 줄)

통합 LPDDR5X 덕에 **QUALITY 티어(qwen3.5:27b)까지 GPU 메모리 상주**가 현실적 —
클라우드 승급(CLOUD_MID/HIGH) 의존도를 낮추고 라우터 목표 분포(LOCAL 80%)를 로컬에서 소화한다.

---

## 1. Ollama 설치 (Windows)

1. https://ollama.com/download/windows 에서 Windows 설치본 설치 (AMD GPU는 최신 Ollama가
   ROCm/Vulkan 백엔드로 자동 감지 — 8060S는 gfx1151).
2. GPU 오프로드 확인:
   ```powershell
   ollama run qwen2.5:3b "2+2="
   ```
   응답 후 작업 관리자에서 GPU(8060S) 사용률이 뛰는지 확인. GPU 미사용(CPU 폴백)이면
   Ollama 최신 버전 + AMD Adrenalin 드라이버 갱신 후 재시도.
3. (선택·성능) 시스템 환경 변수 — SETUP_GUIDE의 systemd 값을 Windows로 이식:
   ```powershell
   [Environment]::SetEnvironmentVariable("OLLAMA_MAX_LOADED_MODELS", "2", "User")
   [Environment]::SetEnvironmentVariable("OLLAMA_NUM_PARALLEL", "4", "User")
   [Environment]::SetEnvironmentVariable("OLLAMA_KEEP_ALIVE", "10m", "User")
   ```
   설정 후 Ollama 재시작(트레이 아이콘 Quit → 재실행).

---

## 2. 모델 pull — 코드 정본 6종 (⚠ pull_models.sh 기본값으론 부족)

`/status`의 `ready=true`는 **라우터 매트릭스 전 모델 설치**를 요구한다
(`LOCAL_MODEL_MATRIX` + `QUALITY_MODEL_ID`, `l3/providers/ollama.py::_REQUIRED_MODEL_IDS`):

```powershell
ollama pull qwen2-math:1.5b
ollama pull qwen2-math:7b
ollama pull qwen2.5:3b
ollama pull qwen2.5:7b
ollama pull qwen3.5:27b
ollama pull qwen3-vl:8b
```

| 태그 | 라우터 좌석 | 용도 |
|---|---|---|
| `qwen2-math:1.5b` | MATH×FAST | 풀이·즉답(p50≈1s) |
| `qwen2-math:7b` | MATH×MID | 풀이·깊이 |
| `qwen2.5:3b` | GENERAL×FAST | NLP·경량 저작 |
| `qwen2.5:7b` | GENERAL×MID | **동등문제 저작·rephrase·judge(general_mid)** |
| `qwen3.5:27b` | QUALITY(비동기 전용) | 킬러 난이도(동기 호출 금지) |
| `qwen3-vl:8b` | VISION×FAST | OCR·그래프(멀티모달) |

> **실측 divergence(수정 전 주의)** ①: `infra/phaiakes9/pull_models.sh` 기본은 `qwen2-math:7b`
> **1종만** 받는다 — Linux에서 쓸 땐 `WHYMATH_MODELS_OVERRIDE="qwen2-math:1.5b,qwen2-math:7b,qwen2.5:3b,qwen2.5:7b,qwen3.5:27b"` 필요.
> ②: CLAUDE.md 기술 스택 표(Qwen3-Math·DeepSeek-Math)는 상위 의도이고 **코드 매트릭스(위 표)가
> 실제 pull 정본**. ③: `healthcheck.sh` 헤더 주석의 `qwen2.5-math:7b-instruct`는 stale.

---

## 3. WhyMath 백엔드 env (PowerShell)

```powershell
[Environment]::SetEnvironmentVariable("WHYMATH_OLLAMA_HOST", "http://127.0.0.1:11434", "User")
[Environment]::SetEnvironmentVariable("WHYMATH_OLLAMA_REQUEST_TIMEOUT_S", "120", "User")
```
- 타임아웃 기본 30s는 FAST 동기 기준 — **라이브 저작·rephrase는 120 권장**(7b 저작 p50≈4s·꼬리 여유).
- `WHYMATH_ANTHROPIC_API_KEY`는 **로컬 전용이면 설정하지 않는다**(라우터가 LOCAL 결정이면
  AnthropicProvider는 지연 연결이라 호출 자체가 없음. 클라우드 결정+키 없음이면 명확히 실패 —
  조용한 강등 없음).

레포 준비(새 PC 최초 1회):
```powershell
git clone https://github.com/doldori7/WhyMath.git
cd WhyMath\src\backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

---

## 4. 스모크 검증 (라이브 게이트)

```powershell
cd WhyMath\src\backend
.venv\Scripts\Activate.ps1
python -c "import asyncio; from whymath_backend.l3.providers.ollama import OllamaProvider; s = asyncio.run(OllamaProvider().check_status()); print('reachable:', s.reachable); print('missing:', list(s.missing)); print('READY:', s.all_present)"
```
기대: `reachable: True` · `missing: []` · `READY: True`. `missing`에 태그가 남으면 §2로.

(API 서버까지 띄우면 `GET /status`가 같은 판정을 JSON으로 준다 — `ready`·`missing` 필드.)

---

## 5. 파이프라인 ① — 발문 다양화 rephrase (가장 먼저·가장 안전)

**왜 먼저**: fail-closed 설계라 실패해도 원문 유지(수치 오염 원천 불가). 결정론 3중 검증
(방정식 substring 봉인·추가 등식 차단·위생)이 LLM 출력을 봉인. 산출물이 코퍼스 v0를 덮지 않고
별 경로에 생김.

```powershell
cd WhyMath\src\backend
.venv\Scripts\Activate.ps1
python -m whymath_backend.harness.problem_corpus_rephrase --in ..\..\data\corpus\problem_bank_generated_v0\problems.jsonl --out ..\..\data\corpus\problem_bank_rephrased_v0\problems.jsonl --temperature 0.9
```

- provider 미주입 → 내부에서 표준 CompositeProvider(Ollama 로컬) 자동 구성. 라우터가
  GENERAL(qwen2.5) 저작 패밀리로 태움.
- stdout JSON 리포트에서 확인: `rephrased`(성공 다양화 수) vs `unchanged`(원문 유지 수) +
  `unchanged_reason_sample`(사유 표본). **비-quad 발문(미적분 삼차 계열)은 방정식 추출 밖이라
  의도적으로 unchanged** — 정상.
- 산출 JSONL은 사람 검수 전 v0 — repo 커밋은 검토 후 결정(rephrase 산출물은 라이브 LLM 결과라
  기본 미커밋 규약).

## 6. 파이프라인 ② — LLM 동등문제 생성 (llm_generator·라이브 배치)

`l3/equivalent/llm_generator.py` docstring L40-92의 핸드오프 절차가 정본. 요약:

```python
# WhyMath\src\backend 에서 python 대화형 또는 스크립트
from whymath_backend.l3.equivalent.llm_generator import LLMEquivalentProblemGenerator
from whymath_backend.l3.providers.ollama import OllamaProvider
from whymath_backend.l4.misconception.catalog import CATALOG_BY_ID  # 배선부는 계약 면제
from whymath_backend.schema.enums import Subject

gen = LLMEquivalentProblemGenerator(
    OllamaProvider(),  # 실 Ollama(지연 연결). None이면 Composite 자동 구성
    misconception_catalog={mid: m.name_kr for mid, m in CATALOG_BY_ID.items()},
    topic_hint="이차방정식 — 두 근 중 큰 근을 구하는 형태(답 하나)",
    subject=Subject.공통,
    slug_prefix="wm-gen-quad",
)
# 이후 orchestrator.run_batch(spec, gen, n=…, store=…)로 게이트+dedup 경유 저장
```

- 온도 0.9·authoring_family=GENERAL 기본(qwen2-math는 저작 mode collapse — S2-h 실측).
- **LLM 출력은 S2-a 게이트 통과 전 학생 노출 자격 없음** — 게이트가 최종 봉인.
- 참고: 스켈레톤 결정론 배치(`problem_corpus_batch`)는 **LLM 0**이라 이 머신 GPU와 무관 —
  코퍼스 materialization은 어디서든 동일 산출.

## 7. 파이프라인 ③ — misconception judge (shadow부터)

그래듀에이션 규약(`docs/architecture/04b_misconception_judge_graduation.md`·shadow 런북) 준수 —
**바로 gate on 금지, shadow 측정 먼저**:

```powershell
[Environment]::SetEnvironmentVariable("WHYMATH_MISCONCEPTION_JUDGE_ROUTING", "general_mid", "User")
```
- `general_mid`(qwen2.5:7b) 권장 — 기본 `fast_math`(qwen2-math:1.5b)는 2026-06-15 라이브 측정에서
  한국어 판정 형식 미준수(FP 감소 0) 실측.
- shadow 측정: `WHYMATH_MISCONCEPTION_JUDGE_SHADOW=true` (+ semantic_mode=shadow 전제·비차단).
- **라이브 게이트(`WHYMATH_MISCONCEPTION_JUDGE_ENABLED=true`)는 shadow 지표 검토 후에만** —
  coach `_gate`(api/coach.py L574)가 이 플래그를 읽는다.

---

## 8. 순서 요약 (체크리스트)

- [ ] §1 Ollama 설치 + GPU 오프로드 확인
- [ ] §2 모델 6종 pull (`ollama list`로 확인)
- [ ] §3 env 2종 설정 + 레포/venv 준비
- [ ] §4 스모크: `check_status()` READY=True
- [ ] §5 rephrase 1회 실행 → 리포트에서 rephrased>0 확인 (**첫 라이브 이정표**)
- [ ] §6 llm_generator 소량(n=5) 배치 → accepted_stored 확인
- [ ] §7 judge shadow 측정 → 지표 검토 → (별도 결정) gate on
- [ ] 결과·수율을 MEMORY.md 결정 로그에 기록

## 9. 알려진 함정

| 증상 | 원인 | 조치 |
|---|---|---|
| `RuntimeError: ollama … 설치되지 않았습니다` | venv에 ollama 클라이언트 없음 | `pip install ollama` |
| `/status ready=false·missing=[…]` | §2 divergence ① — 모델 일부 미pull | missing 태그 그대로 pull |
| rephrase 전건 unchanged·"provider 예외" | Ollama 데몬 미기동/호스트 불일치 | `WHYMATH_OLLAMA_HOST` 확인·데몬 기동 |
| 저작이 같은 문제 반복(mode collapse) | MATH 패밀리로 저작 | authoring_family=GENERAL 기본 유지(S2-h) |
| QUALITY 27b 동기 호출 503 | 설계 의도(비동기 전용) | Celery 워커(concurrency 1) 경유·Linux 이관 시 |
| GPU 대신 CPU로 느림 | Ollama가 8060S 미감지 | Ollama·Adrenalin 최신화, `ollama ps`로 확인 |
