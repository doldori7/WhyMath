# Phaiakes9 (AMD Ryzen AI Max+ 395 / Radeon 8060S) 로컬 LLM 성능 극대화 런북

> **대상 머신**: GMKtec EVO-X2 · Ryzen AI Max+ 395(Strix Halo) · Radeon 8060S(gfx1151) · 128GB LPDDR5X-8000 · Windows 11
> **목적**: WhyMath L3 로컬 추론(Ollama·Qwen 계열)의 처리량·지연을 이 하드웨어에서 물리 한계 근처까지 끌어올리는 조건을 **측정으로** 확정한다.
> **작성**: 2026-08-21 · 브랜치 `claude/amd-395-gpu-diagnosis-jinh6i`

---

## 0. 이 문서의 근거 등급 (읽기 전에)

이 저장소 규칙상 **검증 없는 실행 안내는 금지**다. 아래 표기를 각 주장에 붙였다.

| 등급 | 뜻 | 이 문서에서의 취급 |
|---|---|---|
| **[계산]** | 하드웨어 사양에서 직접 유도 (본 문서 §2) | 검산 가능·재현 가능 |
| **[문헌]** | 외부 실측 보고·공식 문서 (§8 출처) | 방향은 신뢰, **수치는 이 머신에서 재측정 필요** |
| **[코드]** | 이 저장소 코드에서 확인 | 사실 |
| **[미측정]** | Phaiakes9에서 아직 안 잰 것 | **가정 금지 — 측정 후 이 표를 갱신** |

> ⚠️ **성능 수치(t/s)는 여전히 전부 [계산] 또는 [문헌]이다** — Phaiakes9 벤치 실측은 0건.
> 다만 **환경 실측은 2026-08-22 Phase 0 1차로 착지했다**(하드웨어·드라이버·VGM 카브아웃). §5 진단표 참조.
> 게이트 `G-amd395-perf-baseline`(사람 게이트 대장)이 이 측정을 추적한다.

---

## 1. 사전 브리핑 (Kiki 직접 수행 과제 · 6항목)

1. **과제 명칭** — Phaiakes9 GPU 추론 경로 진단 및 성능 레버 1개씩 측정
2. **목적** — "8060S에서 GPU 추론이 되는가"를 넘어서 **어떤 설정 조합이 최대 t/s를 내는가**를 확정한다. 결과는 ①WhyMath L3 라우터의 로컬 티어 지연 상수(`LOCAL_LATENCY_MS`) 보정 ②로컬 vs OpenRouter 비용/정확도 비교 ③QUALITY 티어 모델(현 `qwen3.5:27b`) 유지 여부 판단에 쓰인다.
3. **구체적 절차** — Phase 0(증거 수집, 2분) → Phase 1(베이스라인 벤치, 5~15분) → Phase 2~5(레버 **하나씩** 바꾸고 재측정, 각 5~20분). 각 Phase는 스크립트 1개 실행이 전부이며, 결과는 `.gpu_evidence\` 아래 파일로 남는다.
4. **성공 기준** — Phase 0에서 `evidence_*.txt`가 생성되고 그 안에 GPU 이름·전용 VRAM 바이트 수가 찍힌다. Phase 1에서 `bench_*.csv`의 `gpu_fraction` 열이 1.0에 가까우면 GPU 추론, 0.0이면 CPU 추론이다. **실패 시 대처**: 스크립트가 `[FAIL]`로 끝나면 그 줄을 그대로 붙여넣고 멈춘다(추정으로 다음 단계 진행 금지).
5. **실행 환경** — Phaiakes9의 **Windows PowerShell**(= 평소 쓰는 그 창. SSH·WSL 진입 불요). 작업 디렉터리 `C:\Users\kiki\Desktop\__AI\WhyMath`. 선행 조건: Ollama for Windows 설치·기동, 이 브랜치 체크아웃.
6. **창 구분** — Phase 0~1은 **아무 PowerShell 창 1개**에서 끝난다(서버 점유 없음). Phase 4(백엔드 스위치)만 `ollama serve`가 창을 점유하므로 **창을 2개** 쓴다 — 해당 절에 명시.

### 선행: 브랜치 체크아웃 (창 A · Windows PowerShell)

```powershell
# [실행 시스템] Windows PowerShell (Phaiakes9 본체 · 진입 명령 불요)
cd C:\Users\kiki\Desktop\__AI\WhyMath
git fetch origin claude/amd-395-gpu-diagnosis-jinh6i
git checkout -B claude/amd-395-gpu-diagnosis-jinh6i origin/claude/amd-395-gpu-diagnosis-jinh6i
# 자가검증 — 스크립트 2개가 실제로 있는지 (없으면 여기서 멈춘다)
Test-Path .\scripts\ops\collect_gpu_evidence.ps1, .\scripts\ops\bench_ollama.ps1
```

> 두 줄 모두 `True`가 아니면 체크아웃이 안 된 것이다. 다음 단계로 넘어가지 않는다.

---

## 2. 먼저 알아야 할 것: 이 머신의 성능 상한은 **메모리 대역폭**이 정한다 [계산]

Strix Halo의 LPDDR5X-8000 / 256-bit 구성 → **피크 대역폭 256 GB/s**(`8000 MT/s × 32 B`).
LLM 토큰 생성은 매 토큰마다 활성 가중치를 통째로 읽으므로, **생성 속도 상한 ≈ 대역폭 ÷ 활성 가중치 바이트**다.

| 모델 (WhyMath 실제 핀 [코드]) | Q4 크기 | 이론 상한 | 현실 기대(상한의 55~70%) |
|---|---|---|---|
| `qwen2-math:1.5b` | ~1.0 GB | 256 t/s | **141 ~ 179 t/s** |
| `qwen2.5:3b` | ~2.0 GB | 128 t/s | **70 ~ 90 t/s** |
| `qwen2-math:7b` | ~4.4 GB | 58 t/s | **32 ~ 41 t/s** |
| `qwen2.5:7b` | ~4.7 GB | 55 t/s | **30 ~ 38 t/s** |
| `qwen3-vl:8b` | ~6.1 GB | 42 t/s | **23 ~ 29 t/s** (+비전 인코더 prefill 별도) |
| `qwen3.5:27b` (QUALITY·**dense**) | ~16.5 GB | **15.5 t/s** | **8.5 ~ 11 t/s** |
| (참고) 30B-A3B **MoE**, 활성 ~3B | 적재 17 GB / 활성 ~1.9 GB | 135 t/s | **74 ~ 94 t/s** |

> **Phaiakes9 실측 확인 (2026-08-22)**: `NUCBOX_EVO-X2` · AMD RYZEN AI MAX+ 395 (16C/32T) ·
> AMD Radeon(TM) 8060S (driver `32.0.31035.1003`, 2026-07-24) · **LPDDR5X 16GB × 8ch @ 8000 MT/s** ·
> Windows 11 Pro 26200. 즉 위 표의 대역폭 전제(8000 MT/s × 256-bit = 256 GB/s)는 **이 머신에서 확인된 값**이다.

**이 추정 모델은 외부 실측으로 검증된다**: 같은 하드웨어에서 Qwen3-30B-A3B가 llama.cpp/Vulkan으로 **~100 t/s** 보고 [문헌] — 위 표의 MoE 기대치(74~94)와 정합한다.

### 여기서 나오는 결론 3개

1. **27B dense가 10 t/s 근처로 나오면 그건 고장이 아니라 물리 한계다.** 드라이버·백엔드를 아무리 만져도 15.5 t/s를 넘지 못한다. 이 사실을 모르고 튜닝하면 며칠을 태운다.
2. **가장 큰 레버는 설정이 아니라 모델 구조다.** dense 27B → 동급 MoE(30B-A3B류)는 **약 10배**. 백엔드 튜닝(Vulkan↔ROCm)은 잘해야 ±25% [문헌].
3. **7B 이하 티어(WhyMath 주력)는 이미 대역폭 여유가 크다.** 여기서 부족하면 원인은 대역폭이 아니라 **GPU 오프로드 실패(CPU 폴백)** 이다 — §4 Phase 1의 `gpu_fraction`이 바로 그 판정치다.

---

## 3. 성능 극대화 조건 — 레버 7개 (효과 큰 순)

> **원칙: 한 번에 하나만 바꾸고 잰다.** 여러 개를 동시에 바꾸면 무엇이 효과였는지 영구히 알 수 없다.

### L1. 가변 그래픽 메모리(VGM) — GPU가 모델을 아예 못 올리는 1순위 원인 [문헌]

> ✅ **Phaiakes9 현재값 = 약 64GB (2026-08-22 실측) — 이 레버는 이미 권장 상태다.**
> 판정 근거: 물리 설치 128.0GB(16GB × 8ch) − Windows 가용 63.6GB = **카브아웃 64.4GB**.
> 이 계산은 관리자 권한도 dxdiag도 필요 없다(레지스트리 키는 권한 부족으로 막혔고 dxdiag는 실패했으나 판정은 성립했다).
> ⇒ **Phase 2(VGM 조정)는 건너뛴다.** 아래 설명은 값이 어긋났을 때의 조정 방법으로 남긴다.
- **무엇**: AMD Adrenalin → **성능 → 튜닝 → 가변 그래픽 메모리 → 사용자 지정**. 128GB 머신에서 최대 96GB. 설정 후 **재부팅**(펌웨어 레벨 저장 → 드라이버/OS 업데이트에도 유지).
- **왜**: Ollama·llama.cpp·LM Studio는 **"전용 GPU 메모리"** 보고값을 보고 "이 모델이 GPU에 들어가는가"를 판단한다. 전용값이 작으면 메모리가 남아돌아도 **CPU로 폴백**한다.
- **권장값(이 머신 한정 판단)**: **64GB**. 96GB가 아니다 —
  Phaiakes9는 추론 전용기가 아니라 **개발기**다(Docker Postgres `whymath-pg`·백엔드 uvicorn·Flutter 빌드가 상주). 96GB를 떼면 OS+개발 스택에 32GB만 남는다.
  WhyMath가 동시에 상주시켜야 할 모델 총합은 27b(16.5)+7b(4.7)+vl 8b(6.1)+KV ≈ **30~35GB** [계산] → 64GB면 충분하고 30GB 가까운 여유가 남는다.
- **주의** [문헌]: Windows ROCm/HIP 경로에는 **단일 프로세스 VRAM 할당이 32GB를 넘으면 shared memory로 흘러내리는** 보고(ROCm #5940, closed)가 있다. WhyMath 모델은 모두 32GB 미만이라 해당 없음 — 단, 나중에 70B급을 얹으면 이 벽을 먼저 의심한다.

### L2. 전원 모드 — 54W / 85W / **140W** [문헌]
- EVO-X2는 **전면 전용 버튼**으로 Quiet(54W)/Balanced(85W)/Performance(140W)를 전환한다(BIOS 진입 불요).
- 추가로 Windows **전원 모드 = 최고 성능**.
- **기대**: 토큰 생성(대역폭 바운드)보다 **프롬프트 처리(연산 바운드)** 에서 이득이 크다 [계산 근거: prefill은 GEMM, decode는 메모리 읽기]. WhyMath는 **긴 프롬프트 + 짧은 출력**(PRM 단계 검증·동치 판정) 비중이 커서 이 레버가 체감상 크게 작동할 수 있다 — **[미측정]**.

### L3. 백엔드: Vulkan vs ROCm/HIP [문헌]
- 같은 하드웨어 비교에서 **ROCm은 프롬프트 처리 +20%, Vulkan은 토큰 생성 +25%** 로 서로 반대 방향의 우위가 보고된다.
- Ollama에서 Vulkan은 **실험적**으로 0.12.6부터 들어왔고 `OLLAMA_VULKAN=1`(끄기 `=0`)로 제어된다. iGPU는 `OLLAMA_IGPU_ENABLE=1`을 **명시해야** GPU를 쓰는 사례가 보고된다(안 하면 GPU를 *감지하고도* CPU로 돈다).
- ROCm 경로는 `HSA_OVERRIDE_GFX_VERSION=11.5.1`로 gfx1151 인식이 풀린 보고가 있다.
- **주의**: 위 두 경로의 환경변수는 **섞으면 안 된다**. ROCm 경로에서 `HIP_VISIBLE_DEVICES=-1`을 켜면 GPU가 통째로 꺼진다.
- **WhyMath 판단축**: 생성 t/s가 아니라 **왕복 지연**으로 고른다. §4 Phase 4가 두 경로를 각각 잰다.

### L4. 런타임: Ollama 번들 llama.cpp vs standalone llama.cpp [문헌]
- standalone 최신 llama.cpp가 더 빠른 사례가 반복 보고된다(Qwen3-30B-A3B ~101 t/s).
- **하지만 교체 비용이 있다**: WhyMath는 `l3/providers/ollama.py`에 Ollama 클라이언트로 배선돼 있다 [코드]. 교체하려면 `llama-server`의 OpenAI 호환 API로 프로바이더를 새로 쓰거나(라우터 경유 원칙은 유지), Ollama를 그대로 두어야 한다.
- **판단 기준**: Phase 6에서 standalone이 **+20% 이상**일 때만 배선 변경을 태스크로 등재한다. 그 미만이면 Ollama 유지가 총비용상 이득이다.

### L5. 모델·양자화 선택 — **가장 큰 레버** [계산]
- **MoE 우선**. §2 표대로 dense 27B(≈10 t/s) → MoE 30B-A3B(≈100 t/s)는 10배다.
- 양자화는 **Q4_K_M / IQ4_XS**가 크기·품질 균형점. Q8_0은 크기가 2배 → 대역폭 바운드 구간에서 **속도가 절반**이 된다.
- **WhyMath 제안(결정 아님·측정 후 판단)**: QUALITY 티어 `qwen3.5:27b`(dense)는 이 하드웨어에서 구조적으로 느리다. 비동기 티어라 지연 허용치가 크긴 하나, 동급 MoE 대체가 성립하면 **비동기를 동기로 승격**할 수 있는 크기의 이득이다. → §6.

### L6. 모델 상주 정책 — WhyMath에서 **체감 1순위** [코드+계산]
- 라우터는 한 학습 흐름에서 MATH(1.5b/7b)·GENERAL(3b/7b)·VISION(8b)·QUALITY(27b)를 **오간다** [코드 `LOCAL_MODEL_MATRIX`]. Ollama 기본값은 동시 상주 모델 수가 적어, 모델이 바뀔 때마다 **언로드→로드**가 일어난다.
- 27B를 디스크에서 다시 올리는 비용은 수 초 단위다. 이게 붙으면 **모델 스왑이 p50 지연을 지배**한다 — 토큰 속도를 아무리 올려도 안 보인다.
- **그래서 VGM 64GB의 진짜 값어치는 "큰 모델 하나"가 아니라 "여러 모델 동시 상주"다.**
- 설정(창 A에서 1회, 영구):
  ```powershell
  # [실행 시스템] Windows PowerShell (Phaiakes9)
  cd C:\Users\kiki\Desktop\__AI\WhyMath
  [Environment]::SetEnvironmentVariable("OLLAMA_MAX_LOADED_MODELS","4","User")
  [Environment]::SetEnvironmentVariable("OLLAMA_KEEP_ALIVE","30m","User")
  [Environment]::SetEnvironmentVariable("OLLAMA_FLASH_ATTENTION","1","User")
  [Environment]::SetEnvironmentVariable("OLLAMA_NUM_PARALLEL","2","User")
  # 자가검증 — 값이 실제로 박혔는지 (레지스트리를 되읽는다. 현재 셸 변수가 아님)
  "OLLAMA_MAX_LOADED_MODELS","OLLAMA_KEEP_ALIVE","OLLAMA_FLASH_ATTENTION","OLLAMA_NUM_PARALLEL" |
    ForEach-Object { "{0} = {1}" -f $_, [Environment]::GetEnvironmentVariable($_,"User") }
  ```
  > 위 4줄이 **빈 값이 아니어야** 한다. 그리고 **Ollama를 재시작해야** 적용된다(트레이 아이콘 → Quit → 재실행).
- `OLLAMA_KV_CACHE_TYPE=q8_0`은 KV 캐시를 절반으로 줄여 긴 컨텍스트에서 이득이지만 **품질 영향이 있어 WhyMath 기본값으로 권장하지 않는다** — 컨텍스트가 실제로 모자랄 때만.

### L7. 컨텍스트 길이 — 필요한 만큼만 [계산]
- 컨텍스트를 키우면 KV 캐시가 선형으로 커지고(30B·200K에서 50~70GB 보고 [문헌]), 속도와 안정성을 함께 깎는다.
- WhyMath 호출은 대부분 단문 프롬프트다. **기본값(4K~8K) 유지**, 필요 호출만 개별 상향.

---

## 4. 진단 절차 — 레버 하나씩

### Phase 0. 증거 수집 (창 A · 2분)

```powershell
# [실행 시스템] Windows PowerShell (Phaiakes9)
cd C:\Users\kiki\Desktop\__AI\WhyMath
powershell -ExecutionPolicy Bypass -File .\scripts\ops\collect_gpu_evidence.ps1
```

- 산출물: `.gpu_evidence\evidence_<타임스탬프>.txt` (GPU 이름·드라이버·**전용 VRAM 바이트**·전원 계획·Ollama 버전/모델/상주 상태·`OLLAMA_*`/`HSA_*`/`GGML_*` 환경변수·Ollama 서버 로그의 GPU 탐지 줄)
- **자가검증**: 스크립트가 마지막에 파일 존재·크기를 되읽어 `[OK]`/`[FAIL]`과 함께 **exit code**를 낸다. `[FAIL]`이면 그 줄을 붙여넣고 멈춘다.
- 이 파일 하나가 §1에서 물어본 4가지(Ollama 버전 / 모델 / GPU 탐지 / `ollama ps`의 processor)를 **전부** 담는다.
- **옵션**: `-WithDxdiag`(느리고 실패 잦아 기본 꺼짐) · `-NativeTimeoutSec 30`(외부 명령 타임아웃) · `-OllamaHost`
- **권한**: 관리자 권한은 필요 없다. §4의 레지스트리 조회만 권한이 있으면 더 나오고, 없으면 [ERR]로 남기고 넘어간다 —
  VGM 판정은 §2 카브아웃이 담당하므로 영향 없다.

### Phase 1. 베이스라인 벤치 (창 A · 5~15분)

```powershell
# [실행 시스템] Windows PowerShell (Phaiakes9)
cd C:\Users\kiki\Desktop\__AI\WhyMath
powershell -ExecutionPolicy Bypass -File .\scripts\ops\bench_ollama.ps1 -Label baseline
```

- 산출물: `.gpu_evidence\bench_baseline_<타임스탬프>.csv` — 모델별 `gen_tps`(생성 t/s)·`prompt_tps`(프롬프트 처리 t/s)·`load_ms`·**`gpu_fraction`**
- **판정**:
  | 관측 | 뜻 | 다음 행동 |
  |---|---|---|
  | `gpu_fraction` ≈ 1.0 | GPU 추론 성립 | Phase 2로 (극대화 단계) |
  | `gpu_fraction` ≈ 0.0 | **CPU 폴백** | L1(VGM) → L3(백엔드 env) 순서로 원인 추적 |
  | 0 < `gpu_fraction` < 1 | 부분 오프로드 | VRAM 부족 → L1 상향 |
  | `gen_tps`가 §2 기대치의 **50% 미만** | 오프로드는 됐으나 느림 | L2(전원)·L3(백엔드) 후보 |
  | `gen_tps`가 §2 기대치 범위 안 | **이미 물리 한계 근처** | 더 짜지 말고 L5(모델 교체)로 |

### Phase 2. VGM 조정 (재부팅 포함)
AMD Adrenalin → 성능 → 튜닝 → 가변 그래픽 메모리 → 사용자 지정 **64GB** → 재부팅 → 재측정:
```powershell
cd C:\Users\kiki\Desktop\__AI\WhyMath
powershell -ExecutionPolicy Bypass -File .\scripts\ops\collect_gpu_evidence.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\ops\bench_ollama.ps1 -Label vgm64
```

### Phase 3. 전원 모드 140W
전면 버튼으로 Performance 전환 + Windows 전원 모드 최고 성능 → 재측정 (`-Label power140`).

### Phase 4. 백엔드 스위치 — **창 2개** ⚠️

> 이 Phase에서 **창 B는 `ollama serve`가 점유**한다. 창 B에 다른 명령을 붙여넣지 말 것.
> **창 B에서 Ctrl+C는 "복사"가 아니라 서버 중단 신호다.**

먼저 트레이의 Ollama를 **Quit**으로 완전 종료한다.

```powershell
# ── 창 B (서버 전용 · 이후 조작 금지) ──────────────────────────────
# [실행 시스템] Windows PowerShell (Phaiakes9)
cd C:\Users\kiki\Desktop\__AI\WhyMath
$env:OLLAMA_DEBUG="1"; $env:OLLAMA_VULKAN="1"; $env:OLLAMA_IGPU_ENABLE="1"
ollama serve
```

```powershell
# ── 창 C (측정용 · 새 창) ─────────────────────────────────────────
# [실행 시스템] Windows PowerShell (Phaiakes9)
cd C:\Users\kiki\Desktop\__AI\WhyMath
powershell -ExecutionPolicy Bypass -File .\scripts\ops\bench_ollama.ps1 -Label vulkan
```

ROCm 경로도 같은 방식으로 (창 B를 Ctrl+C로 내리고 다시):
```powershell
# ── 창 B (서버 전용 · 이후 조작 금지) ──────────────────────────────
cd C:\Users\kiki\Desktop\__AI\WhyMath
$env:OLLAMA_DEBUG="1"; $env:OLLAMA_VULKAN="0"; $env:HSA_OVERRIDE_GFX_VERSION="11.5.1"
Remove-Item Env:\HIP_VISIBLE_DEVICES -ErrorAction SilentlyContinue   # 있으면 GPU가 꺼진다
ollama serve
```
```powershell
# ── 창 C (측정용) ────────────────────────────────────────────────
cd C:\Users\kiki\Desktop\__AI\WhyMath
powershell -ExecutionPolicy Bypass -File .\scripts\ops\bench_ollama.ps1 -Label rocm
```

> 창 B의 로그에서 `gfx1151` / `8060S` / `ROCm` / `Vulkan` / `library=` 줄을 찾아 evidence 파일에 함께 남긴다.
> **`ollama serve`가 "address already in use"로 죽으면** 좀비 프로세스가 11434를 잡고 있는 것이다(2026-07-17 선례).
> `Get-NetTCPConnection -LocalPort 11434 | Select OwningProcess` 로 확인 후 종료한다 — `/health` 응답이나 프로세스 존재는 **성공 근거가 아니다**.

### Phase 5. 상주 정책 (L6) 적용 후 **왕복 지연** 재측정
§3 L6의 환경변수를 박고 Ollama 재시작 → `-Label resident`로 재측정. 여기서는 t/s보다 **`load_ms`가 0에 수렴하는지**가 판정치다.

### Phase 6 (조건부). standalone llama.cpp / WSL ROCm
Phase 1~5로 §2 기대치에 도달했으면 **하지 않는다**. 도달 못 했을 때만 진행하며, WSL2 경로에는 **ROCm이 .wslconfig 메모리에 묶여 96GB UMA를 못 쓰는** 알려진 제약이 있다 [문헌] — Windows 네이티브가 먼저다.

---

## 5. 진단표 (측정 기록 — **현재 전부 비어 있음**)

| Phase | 설정 | `gpu_fraction` | `gen_tps` (7b) | `gen_tps` (27b) | `prompt_tps` | 판정 |
|---|---|---|---|---|---|---|
| 0 | 현행 그대로 | | | | | **환경 실측 완료 2026-08-22**(아래) · 벤치 [미측정] |
| 2 | VGM 64GB | — | — | — | — | ✅ **이미 충족**(카브아웃 64.4GB 실측) — 조정 불요 |
| 3 | +140W | | | | | [미측정] |
| 4a | Vulkan | | | | | [미측정] |
| 4b | ROCm | | | | | [미측정] |
| 5 | 상주 정책 | | | | | [미측정] |
| 6 | llama.cpp standalone | | | | | [미측정] |

**기대 기준선**(§2 [계산]): 7b = 30~41 t/s · 27b = 8.5~11 t/s · 1.5b = 141~179 t/s

### Phase 0 1차 실측 (2026-08-22 · `evidence_20260822_003545`)

| 항목 | 실측값 | 판정 |
|---|---|---|
| 호스트 | `NUCBOX_EVO-X2` / GMKtec NucBox_EVO-X2 | — |
| CPU | AMD RYZEN AI MAX+ 395 · 16C/32T | — |
| GPU | AMD Radeon(TM) 8060S · driver `32.0.31035.1003`(2026-07-24) · Status OK | ✅ 드라이버 정상 |
| 메모리 | 16GB × 8ch @ **8000 MT/s** (설치 128.0GB) | ✅ 대역폭 전제 확인 |
| Windows 가용 | 63.6 GB | — |
| **GPU 카브아웃** | **64.4 GB** | ✅ **VGM 이미 64GB — L1 충족** |
| OS | Windows 11 Pro 26200 | — |
| 전원 계획 | `4e2a2b94-…` (Camomile) | ⚠️ 최고 성능 여부 미확인 → Phase 3 |
| 전용 VRAM 레지스트리 | `SecurityException` (권한 부족) | 무해 — §2로 대체 판정 |
| dxdiag | 90초 내 미생성 | 무해 — 기본 비활성으로 전환 |
| Ollama | **미수집** — v1 스크립트가 이 지점에서 정지 | 도구 결함, v2에서 수정 |

---

## 6. WhyMath 적용 — 측정이 끝나면 결정할 것 3개

1. **`LOCAL_LATENCY_MS` 보정** [코드] — 현재 라우터의 로컬 지연 상수는 벤치 p50 가정값이다. Phase 1~5 실측으로 갈아끼운다. 상수가 틀리면 라우터의 로컬↔클라우드 승급 판정이 통째로 틀어진다.
2. **QUALITY 티어 재검토** — `qwen3.5:27b`(dense)는 §2대로 이 하드웨어에서 ~10 t/s가 상한이다. 동급 MoE 대체가 성립하면 10배다. **단, 모델 교체는 CLAUDE.md 채택 조건 3건(라우터 경유·실측 근거·MEMORY 결정 로그)을 통과해야 하며, 검증 계약(SymPy 단일 권위·PRM·Langfuse 추적)은 불변이다.**
3. **로컬 vs OpenRouter 비교축** — t/s만으로 고르지 않는다. `detection accuracy` / `false alarm` / `왕복 지연` / `t/s` / `컨텍스트` / `비용` / `반복 실행 안정성` 7축으로 비교하고, **정확도 축은 결함 주입 강등전으로 판정**한다(`docs/standards/superhuman_verification_standard.md`). 로컬이 정확도에서 지더라도 지연·비용에서 이기는 구간이 있고, 그 반대도 있다.

---

## 7. 하지 말 것 (안티패턴)

- ❌ **여러 레버를 동시에 바꾸기** — 무엇이 효과였는지 영구히 알 수 없게 된다.
- ❌ **재설치부터 하기** — 드라이버·ROCm 재설치는 증거를 지운다. 측정이 먼저다.
- ❌ **`ollama ps`의 "100% GPU" 문자열만 보고 성공 판정** — 오프로드 비율은 맞아도 t/s가 기대치의 1/3일 수 있다. `gpu_fraction`과 `gen_tps`를 **둘 다** 본다.
- ❌ **`HIP_VISIBLE_DEVICES=-1`을 ROCm 경로에 남겨두기** — GPU가 통째로 꺼진다.
- ❌ **27B dense가 느린 것을 설정 탓으로 돌리기** — §2 물리 한계다.
- ❌ **검사 명령 출력을 `-q`/`tail`로 잘라 통과 선언** — 판정은 exit code로 한다(CLAUDE.md 2026-08-09 등재).
- ❌ **증거 수집 도구를 "마지막에 한 번 저장" 구조로 만들기** — 중간에 한 단계가 멈추면 **앞서 모은 증거가 통째로 사라진다**.
  섹션마다 파일에 append 하고, **외부 프로세스 호출에는 전부 타임아웃**을 건다. 멈추는 명령은 "멈춘다"는 사실 자체가 증거다.
  (사고 경위: 2026-08-22 v1 첫 실행에서 §6 `ollama` CLI가 무한 대기 → 화면에는 5개 섹션이 찍혔지만 파일은 생성조차 되지 않았다.
  단일 권한 실패(레지스트리)나 단일 도구 실패(dxdiag)가 전체 수집을 무력화하지 않도록 **판정 경로를 이중화**하는 것도 같은 원칙 —
  VGM 판정이 레지스트리·dxdiag 없이 카브아웃 계산으로 성립한 것이 그 예다.)

---

## 8. 출처 (모든 [문헌] 표기의 근거)

- AMD 공식 — [FAQs: AMD Variable Graphics Memory, VRAM, AI Model Sizes, Quantization](https://www.amd.com/en/blogs/2025/faqs-amd-variable-graphics-memory-vram-ai-model-sizes-quantization-mcp-more.html)
- AMD 공식 — [AI Inference on AMD Ryzen AI Max Processor (ROCm Blogs)](https://rocm.blogs.amd.com/artificial-intelligence/ryzen-uma-llm/README.html)
- AMD 공식 — [Strix Halo system optimization (ROCm Docs)](https://rocm.docs.amd.com/en/docs-7.2.0/how-to/system-optimization/strixhalo.html)
- Windows VRAM 할당 이슈 — [ROCm #5940 (Windows) Strix Halo: Memory allocations not going to VRAM](https://github.com/ROCm/ROCm/issues/5940)
- WSL2 제약 — [ROCm #6022 librocdxg fails to map Dedicated VRAM in WSL2](https://github.com/ROCm/ROCm/issues/6022)
- Ollama gfx1151 동작 설정 — [ollama #14855 AMD Strix Halo (gfx1151) ROCm Working Guide](https://github.com/ollama/ollama/issues/14855)
- Ollama Windows ROCm 파손 이력 — [ollama #9553](https://github.com/ollama/ollama/issues/9553) · [ollama #10993](https://github.com/ollama/ollama/issues/10993)
- Vulkan 실험 지원 — [Phoronix: ollama Rolls Out Experimental Vulkan Support](https://www.phoronix.com/news/ollama-Experimental-Vulkan) · [Ollama Hardware support](https://docs.ollama.com/gpu)
- 백엔드 비교 실측 — [llama.cpp: Vulkan vs ROCm on Strix Halo](https://www.soothill.io/blog/2026/08/03/llamacpp-vulkan-vs-rocm-strix-halo/) · [AMD Strix Halo Backend Benchmarks (grid)](https://kyuz0.github.io/amd-strix-halo-toolboxes/)
- 셋업·벤치 종합 — [strix-halo-guide](https://github.com/hogeheer499-commits/strix-halo-guide) · [strix-halo-gmktec-evo-x2 QWEN3-CODER-30B 벤치](https://github.com/pablo-ross/strix-halo-gmktec-evo-x2/blob/main/QWEN3-CODER-30B_BENCHMARK.md)
- VGM 설정 절차 — [How to Allocate VRAM on Strix Halo (Adrenalin)](https://www.jdhodges.com/blog/amd-strix-halo-vram-allocation-ryzen-ai-max-395/)
- 전원 모드 54/85/140W — [PCWorld: GMKtec EVO-X2 review](https://www.pcworld.com/article/3011421/gmktec-evo-x2-review.html)
