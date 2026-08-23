# Phaiakes9 (AMD Ryzen AI Max+ 395 / Radeon 8060S) 로컬 LLM 성능 극대화 런북

> **대상 머신**: GMKtec EVO-X2 · Ryzen AI Max+ 395(Strix Halo) · Radeon 8060S(gfx1151) · 128GB LPDDR5X-8000 · Windows 11
> **목적**: WhyMath L3 로컬 추론(Ollama·Qwen 계열)의 처리량·지연을 이 하드웨어에서 물리 한계 근처까지 끌어올리는 조건을 **측정으로** 확정한다.
> **작성**: 2026-08-21 · 브랜치 `claude/amd-395-gpu-diagnosis-jinh6i`  
> **갱신**: 2026-08-23 · PR #854/#855 후속 측정(OPS-50/51/52) — Vulkan 라벨 분리·상주 재확인·MoE 파싱 안정화

---

## ★ 확정 결론 — Phaiakes9 성능 극대화 조건 (2026-08-22/23 실측)

레버를 하나씩 갈라 측정한 최종 권고. **왕복 지연**(prefill + 생성)이 판단축이다 — WhyMath 호출은 긴 프롬프트·짧은 출력이 주력이기 때문이다.

| # | 조건 | 값 | 실측 근거 |
|---|---|---|---|
| 1 | **모델 구조** | dense보다 **MoE** | 27B dense 11.4 t/s vs 30B-A3B **68.7** t/s(ROCm·flash on) — **6.0배**. 최대 레버 |
| 2 | **모델 상주** | `OLLAMA_MAX_LOADED_MODELS=3`+ · `OLLAMA_KEEP_ALIVE=30m` | 재방문 로드 2,340 ms → **3~5 ms** — 상주 확인(2026-08-23) |
| 3 | **flash attention** | `OLLAMA_FLASH_ATTENTION=1` | MoE 생성 **+23%**(55.6→68.7 t/s). dense 27B는 거의 변화 없음 |
| 4 | **백엔드** | **ROCm 유지** (`OLLAMA_IGPU_ENABLE` 미설정) | Vulkan은 생성 +9~25%를 주지만 prefill을 **−75%** 깎는다. **실제 Vulkan 강제는 `OLLAMA_LLM_LIBRARY=vulkan` 필요**(2026-08-23 신규) |
| 5 | **컨텍스트 예산** | `OLLAMA_CONTEXT_LENGTH=8192` · `OLLAMA_NUM_PARALLEL=1` | 자동 262,144는 로드 실패를 유발 |
| 6 | **VGM** | 64 GB (이미 설정됨) | 레지스트리 실측 65,536 MB |
| 7 | **위생** | 주기적 재시작 · 고아 `llama-server` 정리 | 커밋 여유 0.9 GB → 205 GB 회복. 방치 시 **전건 로드 실패** |

**적용 명령** (`resident` 프리셋이 3·5를 포함하고, 4는 `IGPU_ENABLE`을 두지 않는 것이 곧 적용이다):
```powershell
[Environment]::SetEnvironmentVariable("OLLAMA_CONTEXT_LENGTH","8192","User")
[Environment]::SetEnvironmentVariable("OLLAMA_NUM_PARALLEL","1","User")
[Environment]::SetEnvironmentVariable("OLLAMA_FLASH_ATTENTION","1","User")
[Environment]::SetEnvironmentVariable("OLLAMA_MAX_LOADED_MODELS","3","User")
[Environment]::SetEnvironmentVariable("OLLAMA_KEEP_ALIVE","30m","User")
[Environment]::SetEnvironmentVariable("OLLAMA_IGPU_ENABLE",$null,"User")   # Vulkan 후보 제외 = ROCm 유지
# 적용하려면 Ollama 재시작 필요
```

**넘을 수 없는 벽**: 생성 속도 상한은 메모리 대역폭 256 GB/s가 정한다(§2). dense 27B의 11.7 t/s는
이론 상한 15.5의 75%로 **이미 물리 한계 근처**다. 여기서 더 얻으려면 설정이 아니라 **모델을 바꿔야 한다**(레버 1).

---

## 0. 이 문서의 근거 등급 (읽기 전에)

이 저장소 규칙상 **검증 없는 실행 안내는 금지**다. 아래 표기를 각 주장에 붙였다.

| 등급 | 뜻 | 이 문서에서의 취급 |
|---|---|---|
| **[계산]** | 하드웨어 사양에서 직접 유도 (본 문서 §2) | 검산 가능·재현 가능 |
| **[문헌]** | 외부 실측 보고·공식 문서 (§8 출처) | 방향은 신뢰, **수치는 이 머신에서 재측정 필요** |
| **[코드]** | 이 저장소 코드에서 확인 | 사실 |
| **[미측정]** | Phaiakes9에서 아직 안 잰 것 | **가정 금지 — 측정 후 이 표를 갱신** |

> ✅ **2026-08-22 Phase 0·1 완주.** 환경 실측(9/9 섹션) + **벤치 5모델 전건 성공**(10/10 런, 전부 GPU 100%).
> §2의 대역폭 상한 계산 모델이 **전 구간에서 검증**됐고, dense↔MoE 대조가 나왔다. §5 진단표 참조.
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

> ✅ **Phaiakes9 현재 상태 = ROCm 사용 중 (2026-08-22 실측)**. 서버 로그가 두 줄로 말해 준다:
> ```
> library=Vulkan  msg="dropping integrated GPU; to enable, set OLLAMA_IGPU_ENABLE=1"  name=Vulkan0
> library=ROCm    msg="inference compute"  compute=gfx1151  type=iGPU  total="99.7 GiB"
> ```
> 즉 **Vulkan 장치는 iGPU라는 이유로 버려졌고, ROCm이 gfx1151을 잡아 실제 추론 장치로 선택됐다.**
> `HSA_OVERRIDE_GFX_VERSION` 없이도 인식된다(문헌의 우회는 이 버전에선 불요).
> ⇒ **"ROCm이 안 잡힌다"는 최초 전제는 이 머신에 해당하지 않는다.** 남은 질문은 "잡혔는가"가 아니라
> **"Vulkan으로 바꾸면 더 빠른가"** 이며, 그것이 Phase 4다.
> 🔴 **2026-08-23 실측**: `OLLAMA_IGPU_ENABLE=1`만으로는 Ollama가 Vulkan을 선택하지 않고 여전히 ROCm을 택했다. 실제 Vulkan을 강제하려면 `OLLAMA_LLM_LIBRARY=vulkan`이 필요했다. 이 조합으로 측정한 결과가 §5.1의 `vulkan_forced` 열이다.
- 같은 하드웨어 비교에서 **ROCm은 프롬프트 처리 +20%, Vulkan은 토큰 생성 +25%** 로 서로 반대 방향의 우위가 보고된다.
- Ollama에서 Vulkan은 **실험적**으로 0.12.6부터 들어왔고 `OLLAMA_VULKAN=1`(끄기 `=0`)로 제어된다. iGPU는 `OLLAMA_IGPU_ENABLE=1`을 **명시해야** GPU를 쓰는 사례가 보고된다(안 하면 GPU를 *감지하고도* CPU로 돈다).
- ROCm 경로는 `HSA_OVERRIDE_GFX_VERSION=11.5.1`로 gfx1151 인식이 풀린 보고가 있다.
- **주의**: 위 두 경로의 환경변수는 **섞으면 안 된다**. ROCm 경로에서 `HIP_VISIBLE_DEVICES=-1`을 켜면 GPU가 통째로 꺼진다.
- **WhyMath 판단축**: 생성 t/s가 아니라 **왕복 지연**으로 고른다. §4 Phase 4가 두 경로를 각각 잰다.

### L4. 런타임: Ollama 번들 llama.cpp vs standalone llama.cpp [문헌]
- standalone 최신 llama.cpp가 더 빠른 사례가 반복 보고된다(Qwen3-30B-A3B ~101 t/s).
- **하지만 교체 비용이 있다**: WhyMath는 `l3/providers/ollama.py`에 Ollama 클라이언트로 배선돼 있다 [코드]. 교체하려면 `llama-server`의 OpenAI 호환 API로 프로바이더를 새로 쓰거나(라우터 경유 원칙은 유지), Ollama를 그대로 두어야 한다.
- **판단 기준**: Phase 6에서 standalone이 **+20% 이상**일 때만 배선 변경을 태스크로 등재한다. 그 미만이면 Ollama 유지가 총비용상 이득이다.
- 🔴 **ROCm 7.2.1 standalone 시도 (2026-08-23, OPS-52)** [실측]: AMD 공식 Windows wheel(`rocm_sdk_core/devel/libraries_custom` 7.2.1)을 `work/rocm-7.2.1-standalone/`에 격리 설치하고, Ollama 0.32.15 lib의 `amdhip64.dll`/`hipblas.dll`을 standalone 7.2 DLL로 교체한 뒤 Ollama를 재기동했다.
  - GPU offload는 정상(`size_vram` 18GB), 모델 로드도 성공.
  - 그러나 **qwen3:30b-a3b 64토큰 생성이 첫 호출 왕복 13.93초로 측정**, 동일 조건의 내장 ROCm 7.1(왕복 15.99초, eval time 46.56 t/s)보다 실사용 지연에서 이득이 없었다.
  - Ollama 0.32.15는 내장 ROCm 7.1(`rocm_v7_1/amdhip64_7.dll`)을 사용 중이며, 7.2 standalone과는 ABI/API 호환성 문제로 보인다.
  - **결론: 현재 Ollama 버전에서는 ROCm 7.2 standalone 교체를 하지 않는다.** Ollama가 ROCm 7.2를 공식 지원하거나 내장 버전이 올라가면 재시도. 복원 스크립트는 `scripts/ops/restore_rocm72_builtin.py`.

### L5. 모델·양자화 선택 — **가장 큰 레버** [계산]
- **MoE 우선**. §2 표대로 dense 27B(≈10 t/s) → MoE 30B-A3B(≈100 t/s)는 10배다.
- ✅ **비교에 필요한 모델이 이미 다 깔려 있다 (2026-08-22 실측)** — `qwen3:30b-a3b`(17.3GB·MoE)와
  `qwen3-coder:30b`(17.3GB·MoE)가 `qwen3.5:27b`(16.2GB·dense)와 나란히 있다. **다운로드 없이 즉시 대조 가능**하다.
  이 세 모델의 t/s 비교가 이 프로젝트에서 가장 값어치 있는 단일 측정이다.
- 양자화는 **Q4_K_M / IQ4_XS**가 크기·품질 균형점. Q8_0은 크기가 2배 → 대역폭 바운드 구간에서 **속도가 절반**이 된다.
- 🔴 **실측 확정(2026-08-22)**: `qwen3.5:27b` **11.9 t/s** vs `qwen3:30b-a3b` **71.5 t/s** = **생성 6.0배 · prefill 3.9배**.
  같은 17GB급인데 MoE는 토큰당 약 2.7 GB만 읽는다.
- **WhyMath 제안(결정 아님 — 정확도 대조가 남았다)**: QUALITY 티어 `qwen3.5:27b`(dense)를 MoE로 교체하면 **비동기 티어를 동기로 승격**할 수 있는 크기의 이득이다(12.4초 → 2.3초, 동일 프롬프트·128토큰 실측).
  **단, 속도만으로 결정하지 않는다** — 채택 조건 3건(라우터 경유·실측 근거·MEMORY 결정 로그) 중 실측 근거의 *정확도 축*이 아직 없다. 결함 주입 강등전으로 대조한 뒤 결정한다. → §6.

### L6. 모델 상주 정책 · 컨텍스트 예산 — WhyMath에서 **체감 1순위** [코드+계산+실측]

> 🔴 **Phaiakes9에서 즉시 손봐야 할 것이 실측으로 드러났다 (2026-08-22)**
>
> | 항목 | 현재값 | 문제 | 권장 |
> |---|---|---|---|
> | `OLLAMA_CONTEXT_LENGTH` | unset → **자동 262,144** | 로그: `vram-based default context ... default_num_ctx=262144`. ROCm이 VRAM을 99.7 GiB로 보고해 **256K 컨텍스트**가 기본값이 됐다 | **8192~32768 명시** |
> | `OLLAMA_NUM_PARALLEL` | **4** | KV 캐시가 병렬 슬롯 수만큼 곱해진다 | **1~2** |
> | `OLLAMA_FLASH_ATTENTION` | **false** | KV 메모리·속도 손해 | **1** |
> | `OLLAMA_MAX_LOADED_MODELS` | **2** | 라우터는 6개 핀을 오간다 → 스왑 발생 | **4** |
> | `OLLAMA_KEEP_ALIVE` | 10m | 무난 | 30m |
>
> **왜 컨텍스트가 1순위인가** [계산]: 27B급에서 KV 캐시는 대략 컨텍스트 길이에 비례한다.
> 256K × 4병렬은 물리적으로 불가능한 크기라 Ollama의 자동 fit이 끼어들어 **로드 때마다 예측 불가능하게 줄인다** —
> 로드 시간이 길어지고, 최악의 경우 GPU에 다 못 올려 **CPU로 흘러내린다**(= `gpu_fraction < 1`).
> 8K로 명시하면 같은 계산에서 KV가 1/32이 된다. WhyMath 호출은 대부분 단문이므로 손해가 없다.
- 라우터는 한 학습 흐름에서 MATH(1.5b/7b)·GENERAL(3b/7b)·VISION(8b)·QUALITY(27b)를 **오간다** [코드 `LOCAL_MODEL_MATRIX`]. Ollama 기본값은 동시 상주 모델 수가 적어, 모델이 바뀔 때마다 **언로드→로드**가 일어난다.
- 27B를 디스크에서 다시 올리는 비용은 수 초 단위다. 이게 붙으면 **모델 스왑이 p50 지연을 지배**한다 — 토큰 속도를 아무리 올려도 안 보인다.
- **그래서 VGM 64GB의 진짜 값어치는 "큰 모델 하나"가 아니라 "여러 모델 동시 상주"다.**
- 설정(창 A에서 1회, 영구):
  ```powershell
  # [실행 시스템] Windows PowerShell (Phaiakes9)
  cd C:\Users\kiki\Desktop\__AI\WhyMath
  [Environment]::SetEnvironmentVariable("OLLAMA_CONTEXT_LENGTH","8192","User")
  [Environment]::SetEnvironmentVariable("OLLAMA_NUM_PARALLEL","2","User")
  [Environment]::SetEnvironmentVariable("OLLAMA_FLASH_ATTENTION","1","User")
  [Environment]::SetEnvironmentVariable("OLLAMA_MAX_LOADED_MODELS","4","User")
  [Environment]::SetEnvironmentVariable("OLLAMA_KEEP_ALIVE","30m","User")
  # 자가검증 — 값이 실제로 박혔는지 (레지스트리를 되읽는다. 현재 셸 변수가 아님)
  "OLLAMA_CONTEXT_LENGTH","OLLAMA_NUM_PARALLEL","OLLAMA_FLASH_ATTENTION","OLLAMA_MAX_LOADED_MODELS","OLLAMA_KEEP_ALIVE" |
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

### 🤖 Phase 2~5 자동 실행 — `tune_and_bench.ps1` (권장)

수작업 단계(환경변수 → Ollama 재시작 → 실효 설정 확인 → 벤치)를 전부 스크립트가 한다.
**2026-08-22 진단에서 측정 4회가 측정 자체가 아닌 이유로 공전했기 때문이다** — 재시작 누락 2회, 고아 프로세스 1회, 인자 파싱 1회.

```powershell
# [실행 시스템] Windows PowerShell (Phaiakes9 본체)
cd C:\Users\kiki\Desktop\__AI\WhyMath
powershell -ExecutionPolicy Bypass -File .\scripts\ops\tune_and_bench.ps1 -Presets "baseline,resident,vulkan"
```

프리셋마다 ①환경변수 적용 ②Ollama·고아 전부 종료 ③재기동 ④`/api/version` 응답 대기
⑤**`server.log`의 실효 설정이 의도와 일치하는지 대조**(불일치면 즉시 중단 — 잘못된 상태로 재지 않는다) ⑥벤치.
마지막에 프리셋 간 비교표를 출력한다. Windows 고성능 전원 계획도 함께 적용하며 되돌리는 명령을 출력한다
(`-SkipPowerPlan`으로 생략 가능).

| 프리셋 | 내용 | 측정 모델 | 소요 |
|---|---|---|---|
| `baseline` | 현행 확정 조건(ctx 8192 · np 1) — 비교 기준선 | 3b·7b·27b·30b-a3b | ~2분 |
| `resident` | L6 상주 정책 — **같은 모델 재방문 시 `load_ms`가 0에 수렴하는지** | 1.5b·3b·7b **× 2회** (`-NoUnload`) | ~1분 |
| `vulkan` | L3 백엔드 대조 — `OLLAMA_IGPU_ENABLE=1`로 Vulkan 장치를 살린다 | 3b·7b·27b·30b-a3b | ~2분 |

**3개 전부 = 약 5분** (2026-08-22 clean 런 실측값 기반 추정: 로드 3.0~16.0초 + 생성 + 프리셋당 재기동 오버헤드 ~25초).

> **`resident`의 모델이 다른 이유** — 상주 효과는 *같은 모델을 다시 부를 때* 드러나므로 3모델을 2회씩 방문한다.
> 27B(16.2GB)를 넣지 않는 것은 의도적이다: 3모델 합이 22GB가 되어 **커밋 여유 20GB 천장을 넘고, 그러면
> 상주가 아니라 실패를 재현하게 된다**. 1.5b+3b+7b = 7.1GB는 안전하다.

> ⚠️ **전면 버튼(54/85/140W)은 OS에서 못 바꾼다.** 스크립트는 Windows 전원 계획만 고성능으로 돌린다 —
> 140W는 **눈으로 확인**해야 한다.

### Phase 3. 전원 모드 140W (수동 참고)
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

**Vulkan을 실제로 강제하려면** `OLLAMA_IGPU_ENABLE=1`에 더해 `OLLAMA_LLM_LIBRARY=vulkan`이 필요했다(2026-08-23 실측). `tune_and_bench.ps1`에는 이 조합의 `vulkan_forced` 프리셋이 추가됐다.

```powershell
# ── 창 B (서버 전용) ──────────────────────────────────────────────
cd C:\Users\kiki\Desktop\__AI\WhyMath
$env:OLLAMA_DEBUG="1"; $env:OLLAMA_VULKAN="1"; $env:OLLAMA_IGPU_ENABLE="1"; $env:OLLAMA_LLM_LIBRARY="vulkan"
ollama serve
```

> 창 B의 로그에서 `gfx1151` / `8060S` / `ROCm` / `Vulkan` / `library=` 줄을 찾아 evidence 파일에 함께 남긴다.
> **`ollama serve`가 "address already in use"로 죽으면** 좀비 프로세스가 11434를 잡고 있는 것이다(2026-07-17 선례).
> `Get-NetTCPConnection -LocalPort 11434 | Select OwningProcess` 로 확인 후 종료한다 — `/health` 응답이나 프로세스 존재는 **성공 근거가 아니다**.

### Phase 5. 상주 정책 (L6) 적용 후 **왕복 지연** 재측정
§3 L6의 환경변수를 박고 Ollama 재시작 → `-Label resident`로 재측정. 여기서는 t/s보다 **`load_ms`가 0에 수렴하는지**가 판정치다.

### Phase 6 (조건부). standalone llama.cpp / WSL ROCm
Phase 1~5로 §2 기대치에 도달했으면 **하지 않는다**. 도달 못 했을 때만 진행하며, WSL2 경로에는 **ROCm이 .wslconfig 메모리에 묶여 96GB UMA를 못 쓰는** 알려진 제약이 있다 [문헌] — Windows 네이티브가 먼저다.

---

## 5. 진단표 (측정 기록)

| Phase | 설정 | `gpu_fraction` | `gen_tps` (7b) | `gen_tps` (27b) | `prompt_tps` | 판정 |
|---|---|---|---|---|---|---|
| 0 | 현행 그대로 | | | | | **환경 실측 완료 2026-08-22**(아래) |
| 1 | ctx 8192 · np 1 · 고아 정리 | **1.0** | **42.3** | **11.9** | 293~2,331 | ✅ 2026-08-22 10/10 성공 (MoE 30B = 71.5) |
| 2 | VGM 64GB | — | — | — | — | ✅ **이미 충족**(카브아웃 64.4GB 실측) — 조정 불요 |
| 3 | +140W | — | — | — | — | [미측정] — 전면 버튼 수동, 추정치 없음 |
| 4a | Vulkan (`OLLAMA_IGPU_ENABLE=1`) | 1.0 | — | — | — | ⚠️ 2026-08-23: 서버가 ROCm 선택(아래 §5.1) |
| 4b | ROCm (**현재 기본값**) | 1.0 | 41.0 | 11.5 | 278 | ✅ 2026-08-23 flash on 기준 |
| 4c | Vulkan 강제 (`OLLAMA_LLM_LIBRARY=vulkan`) | 1.0 | 46.8 | 12.3 | **70** | ✅ 2026-08-23 실제 Vulkan(아래 §5.1) |
| 5 | 상주 정책 | 1.0 | 39.7 | — | — | ✅ 2026-08-23 재방문 load_ms 3~5 ms(아래 §5.2) |
| 6 | llama.cpp standalone / ROCm 7.2 | — | — | — | — | [미시도] — OPS-52 추적 |

**기대 기준선**(§2 [계산]): 7b = 30~41 t/s · 27b = 8.5~11 t/s · 1.5b = 141~179 t/s

### 5.1 2026-08-23 후속 측정 — ROCm vs Vulkan 실제 라벨 분리

> 실행: `tune_and_bench.ps1 -Presets "baseline,rocm,vulkan,vulkan_forced,resident"` (Phase 0 evidence `evidence_20260823_092752` 참조)
> PowerShell 출력 인코딩 문제로 `.gpu_evidence\*.csv`가 정본이다.

| 프리셋 | 3b gen/prompt | 7b gen/prompt | 27b dense gen/prompt | 30b-a3b MoE gen/prompt | 서버 선택 백엔드 |
|---|---|---|---|---|---|
| `baseline` (ROCm, flash off) | 72.4 / 2,465 | 39.0 / 1,192 | 11.4 / 279 | 55.6 / 874 | **ROCm gfx1151** |
| `rocm` (flash on) | 81.1 / 2,542 | 41.0 / 1,236 | 11.5 / 278 | 68.7 / 1,132 | **ROCm gfx1151** |
| `vulkan` (`IGPU_ENABLE=1`) | 93.9 / 2,220 | 46.6 / 974 | 12.4 / 73 | 80.8 / 1,153 | **ROCm gfx1151** (⚠️ Vulkan 미선택) |
| `vulkan_forced` (`LLM_LIBRARY=vulkan`) | 91.1 / 2,144 | 46.8 / 974 | 12.3 / **70** | 85.8 / 1,177 | **Vulkan** ✅ |

**새로 확인된 사실**

1. **`OLLAMA_IGPU_ENABLE=1`만으로는 Vulkan이 선택되지 않는다.** Ollama 스케줄러가 여전히 ROCm을 선택한다. 진짜 Vulkan을 강제하려면 `OLLAMA_LLM_LIBRARY=vulkan`이 필요하다.
2. **실제 Vulkan은 dense 27B의 prefill을 75% 깎는다.** ROCm 278 t/s → Vulkan 70 t/s. 생성은 11.5 → 12.3 t/s로 소폭 증가. WhyMath 판단축(왕복 지연)에서 ROCm 유지가 재확인됐다.
3. **flash attention 효과는 MoE에 집중된다.** dense 27B는 거의 변화 없음(+1%), MoE 30B-A3B는 생성 55.6 → 68.7 t/s(+24%), 왕복 지연 4,004 ms → 2,407 ms.

### 5.2 2026-08-23 상주 정책 재확인

| 모델 | 1회차 load_ms | 재방문 load_ms | 단축 |
|---|---|---|---|
| `qwen2-math:1.5b` | 2,796.5 | 5.3 | 527배 |
| `qwen2.5:3b` | 2,653.9 | 3.2 | 829배 |
| `qwen2.5:7b` | 4,158.3 | 3.7 | 1,124배 |

`MAX_LOADED_MODELS=3`으로 1.5b+3b+7b(합 7.1GB)가 모두 상주했다. **단, `qwen2-math:1.5b`는 2회차 호출에서 빈 응답(RuntimeException)이 2회 발생**했다 — 이 모델의 학습 컨텍스트 상한이 4096이라 상주 슬롯의 8192와 맞지 않거나, 캐시 히트 경로의 edge case일 수 있다. 상주 프리셋에서 1.5b를 제외하거나 별도 검증이 필요하다(OPS-51 후속).

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

### Phase 0 완주 (2026-08-22 07:38 · `evidence_20260822_073859` · 9/9 `[OK]`)

| 항목 | 실측값 | 판정 |
|---|---|---|
| **백엔드** | `library=ROCm compute=gfx1151 type=iGPU total=99.7 GiB` | ✅ **ROCm이 이미 GPU를 잡고 있다** |
| Vulkan 장치 | `dropping integrated GPU; to enable, set OLLAMA_IGPU_ENABLE=1` | iGPU라 자동 제외 → Phase 4에서 살려 비교 |
| Ollama | `0.32.15` · server UP (`0.0.0.0:11434`) | ✅ |
| 전용 VRAM(레지스트리) | **65,536 MB = 64.0 GB** | ✅ 카브아웃 추정 64.4GB와 0.4GB 차 = 펌웨어 예약 |
| ROCm 보고 VRAM | 99.7 GiB | 전용 64GB + 공유(RAM 절반 ~32GB) 합산치 |
| **기본 컨텍스트** | **`default_num_ctx=262144`** (VRAM 기반 자동) | 🔴 **과대** — L6 참조 |
| `OLLAMA_NUM_PARALLEL` | 4 | 🔴 KV × 4 |
| `OLLAMA_FLASH_ATTENTION` | false | 🔴 꺼짐 |
| `OLLAMA_MAX_LOADED_MODELS` | 2 | ⚠️ 라우터 6핀 대비 부족 |
| `OLLAMA_KEEP_ALIVE` / `OLLAMA_MODELS` | 10m / `D:\ollama_models` | — |
| 전원 계획 | `381b4222…` = **균형 조정(Balanced)** | ⚠️ 고성능 아님 → Phase 3 |
| 설치 모델 15종 | `qwen3.5:27b`(dense) · **`qwen3:30b-a3b`·`qwen3-coder:30b`(MoE)** · `qwen2.5:{3b,7b,14b,32b}` · `qwen2-math:{1.5b,7b}` · `qwen3-vl:8b` · `deepseek-r1:32b` · `gpt-oss:20b` · `llama3.3`(39.6GB) · `bge-m3` | ✅ **dense↔MoE 대조에 필요한 모델이 이미 전부 있다** |

### Phase 1 베이스라인 1차 (2026-08-22 07:54 · `bench_baseline_20260822_075405.csv`)

| 모델 | gen t/s | prompt t/s | gpu_fraction | ctx | 기대치(§2) | 판정 |
|---|---|---|---|---|---|---|
| `qwen2-math:1.5b` | **163.3 / 164.6** | 5,262 / 91,950 | **1.0** | 4096 | 141~179 | ✅ **기대 범위 적중** |
| 나머지 7종 | — | — | — | — | — | 🔴 **HTTP 500 전건 실패** |

**이 결과가 확정한 것 2가지**
1. **GPU 추론이 실제로 작동한다** — `gpu_fraction=1.0`(전량 GPU) + 164 t/s.
2. **§2의 대역폭 상한 계산 모델이 이 머신에서 검증됐다** — 예측 141~179 t/s, 실측 164 t/s.
   ⇒ 같은 모델로 예측한 **dense 27B ≈ 8.5~11 t/s** 역시 신뢰할 수 있는 수치다.

**500 연쇄 — 미규명 [측정 중]**
- 성공한 유일한 모델의 `ctx = 4096`(이 모델의 학습 컨텍스트 상한). 실패한 7종은 모두 **더 긴 컨텍스트를 지원**하는 모델이다.
- ⇒ **가설**: 기본 컨텍스트 262,144(L6 참조)가 이 7종에는 그대로 적용돼 KV 할당이 실패한다. 1.5b만 자기 상한 4096에 걸려 살아남았다.
- **이 가설은 아직 검증되지 않았다.** 1차 도구가 500의 *응답 본문*을 버리고 예외 타입명만 남겨 원인 판정이 불가능했다(도구 결함, 수정 완료).

### 🔴 로드 실패 근본 원인 (2026-08-22 08:01 · `bench_diag` 로그)

`qwen3:30b-a3b`(qwen3moe) 로드 시퀀스가 로그에 그대로 남았다:

```
1차: alloc_tensor_range: failed to allocate ROCm_Host buffer of size 16049422336   (14.95 GiB, 호스트)
     → "reducing automatic context and retrying once"  old_num_ctx=262144 → new_num_ctx=32768
2차: ggml_backend_cuda_buffer_type_alloc_buffer: allocating 17524.43 MiB on device 0:
     cudaMalloc failed: out of memory
     alloc_tensor_range: failed to allocate ROCm0 buffer of size 18375698432        (17.11 GiB, 디바이스)
```

그런데 같은 로그에서 fitter는 **"메모리 충분"** 이라고 판단했다:

```
| ROCm0 | 102129 = 101832 + (29980 = 17524 + 12288 + 168) + -29683 |
projected to use 29980 MiB vs 101832 MiB free → "no changes needed"
system memory total=63.6 GiB free=36.5 GiB free_swap=2.8 GiB
gpu memory library=ROCm available=99.1 GiB free=99.6 GiB
```

**핵심**: 보고된 free 99.6 GiB와 실제 할당 가능량이 다르다. 메모리 회계의 `unaccounted`가 **-29,683 MiB(음수)** 인 것이
그 불일치의 지문이다. 문헌의 Windows Strix Halo 할당 이슈(ROCm #5940 — Windows에서 hipMalloc이 VRAM 대신 shared로
새거나 실패)와 부합한다.

**확정된 것**: 1.5b(0.9GB, ctx 4096)는 성공, MoE 30B(17.3GB)는 실패. **실제 천장은 그 사이 어딘가이며 아직 미측정이다.**

### 🔴 사다리 측정 결과 — **모델 크기 문제가 아니다** (2026-08-22 08:07 · `bench_ladder`)

`OLLAMA_CONTEXT_LENGTH=8192` 적용 상태에서 7종 전건 실패. 실패한 **할당 크기**를 작은 순으로 세우면:

| 모델 | 실패한 할당 | 버퍼 종류 |
|---|---|---|
| `qwen3.5:27b` | **1.00 GiB** | **CPU** (+ `0xc0000409` 스택 오버런 크래시) |
| `qwen3-vl:8b` | **1.38 GiB** | **CPU** |
| `qwen2.5:3b` | **1.79 GiB** | ROCm0 |
| `qwen2.5:7b` | 4.07 GiB | ROCm0 |
| `qwen2.5:14b` | 7.96 GiB | ROCm0 |
| `gpt-oss:20b` | 11.75 GiB | ROCm0 |
| `qwen3:30b-a3b` | 17.11 GiB | ROCm0 |

**판정 전환**: 천장이 낮은 게 아니라 **천장이 없다시피 하다**. 1.00 GiB짜리 **CPU 버퍼**(GPU가 아니다) 할당조차 실패했다.
그 시점의 시스템 상태:

```
system memory total=63.6 GiB  free=34.9 GiB  free_swap=891.3 MiB
gpu memory library=ROCm available=99.1 GiB free=99.6 GiB
```

**물리 여유 34.9 GiB에서 1.0 GiB CPU 할당이 실패한다** — 이건 물리 메모리 문제가 아니라
**Windows 커밋 한도(= 물리 RAM + 페이지파일)** 문제다. `free_swap`이 07:56 **2.8 GiB** → 08:08 **891 MiB**로
줄어든 것이 그 지문이다. 페이지파일이 고갈되면 커밋 한도가 막히고, 물리 여유와 무관하게 모든 대형 할당이 거부된다.

⇒ **대책 사다리의 순서가 바뀐다. 페이지파일이 1순위다.**

### 🔴 구속 자원은 **Windows 커밋 여유** — 그리고 고아 `llama-server` (2026-08-22 08:2x 실측)

| 지표 | 값 | 해석 |
|---|---|---|
| 커밋 한도 | 255.6 GB | 물리 63.6 + 페이지파일 192 |
| **커밋 여유** | **0.9 GB** | 🔴 **진짜 벽.** llama.cpp의 `free_swap=891.3 MiB`와 정확히 일치 |
| 페이지파일 | 할당 192 GB / 사용 **1.0 GB** | ✅ **넉넉하다 — 페이지파일 확대 가설은 기각** |
| 물리 여유 | 34.9 GB | 물리 메모리는 문제가 아니다 |

**고아 프로세스 실측**: `/api/ps`는 "상주 모델 0건"인데 `llama-server` 프로세스가 **2개** 살아 있었다
(시작 시각 **2026-08-21 08:47 / 09:22** — 하루 전부터 남아 있었다). 강제 종료하자:

```
CommitFree_GB : 0.9  →  20.2      (고아 2개가 잡고 있던 커밋 = 19.3 GB)
```

⇒ **실패한 로드가 남긴 고아가 커밋을 점유해 다음 로드를 실패시키는 자기증식 구조**다.
첫 실패 이후의 모든 측정이 이 오염 위에서 이루어졌다.

**미규명 [측정 중]**: 고아를 치운 뒤에도 커밋 점유가 235 GB로 남는다. 물리 여유 34.9 GB·페이지파일 사용 1.0 GB와
산술이 맞지 않으므로 커밋 회계에 다른 요인이 있다. **"llama-server가 ROCm 힙 99.7 GiB를 각각 매핑한다"는 가설은 기각**
(고아 2개의 실제 점유는 19.3 GB였다). 원인을 더 파기 전에 **20.2 GB 여유에서 어디까지 로드되는지**를 먼저 잰다.

**후보 대책 사다리** (위에서부터 싸고 되돌리기 쉬운 순서)

| # | 대책 | 근거 | 되돌리기 |
|---|---|---|---|
| **1** | **고아 `llama-server` 정리 → Ollama 재시작** | 🔴 **1순위(08:2x 실측 확정)** — 커밋 여유 0.9→20.2 GB 회복. 매 측정 **전에** 확인한다 | 없음(정리일 뿐) |
| ~~1b~~ | ~~페이지파일 확대~~ | ❌ **기각** — 이미 192 GB 할당·1.0 GB 사용. 부족하지 않았다 | — |
| 2 | `OLLAMA_CONTEXT_LENGTH=8192` + `OLLAMA_NUM_PARALLEL=1` | 로그의 `-c 131072 -np 4`가 컨텍스트만 12,288 MiB를 먹었다. 둘은 **곱해지므로 하나의 KV 예산 레버**로 다룬다. ctx는 적용됐고 np는 재시작 대기 | 환경변수 삭제 |
| 3 | Vulkan 백엔드(`OLLAMA_IGPU_ENABLE=1`) | 할당 경로가 ROCm과 다르다. 속도 비교가 아니라 **우회 수단**으로 먼저 쓴다 | 환경변수 삭제 |
| 4 | VGM 하향(64GB → 32GB) | 호스트 할당이 실패하는 상황이면 Windows 가용 RAM 63.6GB가 오히려 병목이다. **반직관적이므로 1~3 실패 후에만** | Adrenalin 원복 + 재부팅 |

**모델 크기 사다리로 천장을 먼저 잰다** — 대책을 고르기 전에 "어디까지 되는가"를 알아야 한다:
`qwen2.5:3b`(1.8) → `qwen2.5:7b`(4.4) → `qwen3-vl:8b`(5.7) → `qwen2.5:14b`(8.4) → `gpt-oss:20b`(12.8) → `qwen3.5:27b`(16.2) → `qwen3:30b-a3b`(17.3)

### ✅ Phase 1 확정 측정 (2026-08-22 08:29 · `bench_clean_20260822_082902.csv` · 10/10 성공)

`OLLAMA_CONTEXT_LENGTH=8192` · `NUM_PARALLEL=1` · 고아 프로세스 정리 후. **전 모델 `gpu_fraction = 1.0`(전량 GPU).**

| 모델 | 크기 | **생성 t/s** | 예측(§2) | 유효 대역폭 | 효율 | prefill t/s | 로드 |
|---|---|---|---|---|---|---|---|
| `qwen2.5:3b` | 2.0 GB | **83.4** | 70~90 | 167 GB/s | 65% | 2,331 | 3.0s |
| `qwen2.5:7b` | 4.7 GB | **42.3** | 30~38 | 199 GB/s | 78% | 1,230 | 4.8s |
| `qwen2.5:14b` | 8.4 GB | **22.2** | — | 187 GB/s | 73% | 662 | 7.5s |
| `qwen3.5:27b` (dense) | 16.2 GB | **11.9** | 8.5~11 | 193 GB/s | 75% | 293 | 16.0s |
| **`qwen3:30b-a3b` (MoE)** | 17.3 GB | **71.5** | 74~94 | — | — | 1,148 | 13.4s |

**① 대역폭 모델이 전 구간에서 검증됐다** — dense 4종의 유효 대역폭이 **167~199 GB/s(피크 256의 65~78%)** 로 일관된다.
즉 §2의 `상한 ≈ 대역폭 ÷ 활성 가중치`는 이 하드웨어에서 **실측으로 성립하는 법칙**이다. 예측 범위도 전부 적중하거나 소폭 상회했다.

**② dense 27B → MoE 30B-A3B = 생성 6.0배, prefill 3.9배** 🔴
같은 17GB급 적재량인데 MoE는 토큰당 **약 2.7 GB**만 읽는다(dense 27B는 16.2 GB 전량). 이 프로젝트에서 가장 큰 단일 레버다.

**③ 로드 시간이 지연을 지배한다** — 27B 로드 16.0초 vs 생성 128토큰 10.7초. **모델 스왑 1회가 생성보다 비싸다**(L6 근거 실측 확정).

**④ 커밋 여유는 20.7 → 20.9 GB로 안정** — 고아 프로세스 0. **정리만으로 전건 실패가 전건 성공이 됐다.**

**⑤ 도구 결함 7회차(같은 실행에서 발견·수정)**: 2회차 prefill이 **프롬프트 캐시 히트**라 43,542 t/s 같은 허수를 냈다.
위 prefill 열은 캐시 없는 1회차 값이다. 대책 = 매 실행 고유 접두사로 캐시 무력화 + 요약의 중앙값을 하위 중앙값으로 정정
(`floor(n/2)`는 n=2에서 *최댓값*을 골랐다).

### ⚠️ 재현성 — 같은 조건 두 번 측정이 8~18% 벌어졌다 (2026-08-22)

`clean`(08:29)과 `baseline`(09:40)은 **같은 설정**(ctx 8192 · np 1 · flash off · 전원 균형)인데 결과가 다르다:

| 모델 | clean 08:29 | baseline 09:40 | 차이 |
|---|---|---|---|
| `qwen2.5:3b` | 83.4 | 76.1 | **−8.8%** |
| `qwen2.5:7b` | 42.3 | 39.8 | −5.9% |
| `qwen3.5:27b` | 11.9 | 11.7 | −1.8% |
| **`qwen3:30b-a3b`** | 71.5 | **58.7** | **−17.9%** |
| 27B 로드 | 16.0s | 23.4s | +46% |

**[미규명]**. 후보: ①전원 상태(전면 버튼 54/85/140W는 OS에서 안 보인다 — 두 측정 사이에 달랐을 수 있다)
②발열에 따른 클럭 하강 ③배경 부하. **MoE가 가장 크게 흔들린 것**은 이 모델이 전문가 라우팅으로
메모리 접근 패턴이 불규칙해 캐시·전력 상태에 민감하다는 가설과 부합하나 확인되지 않았다.

**측정 규칙에 반영**: 프리셋 간 차이가 **20% 미만이면 유의하다고 말하지 않는다.** 이 재현성 폭이 그만큼이다.
전원 레버(L2)를 고정한 뒤 다시 재는 것이 우선이며, 그래서 오케스트레이터가 고성능 계획을 **없으면 만들어서** 적용한다.

> ✅ **캐시 무력화는 작동 확인**: 이번 런의 `prompt_tps`는 run1 2,488 / run2 2,487로 일치한다.
> 이전 런의 43,542 t/s 같은 허수가 사라졌다.

### ✅ 프리셋 3종 완주 (2026-08-22 21:17~21:20 · 고성능 전원 계획 적용 · `bench_{baseline,resident,vulkan}_2026082221*`)

#### ① 커밋 미스터리 해소 — 재시작이 답이었다

`CommitFree_GB`가 **20.9 → 205.5 GB**로 돌아왔다. 커밋 한도 255.6 GB 중 정체불명의 235 GB를 점유하던 것은
**시간이 지나며 누적되는 상태**였고, 머신 재시작으로 해소된다. ⇒ **운영 규칙: 로컬 LLM을 쓰는 머신은 주기적으로 재시작한다.**
(어제의 전건 로드 실패는 이 누적 + 고아 프로세스의 합작이었다.)

#### ② 상주 정책(L6) — 재방문 로드가 **2.6 ms**, 600~900배 단축

| 모델 | 1회차 로드 | 재방문 로드 | 단축 |
|---|---|---|---|
| `qwen2-math:1.5b` | 2,353 ms | **2.6 ms** | 905배 |
| `qwen2.5:3b` | 1,587 ms | **2.6 ms** | 610배 |
| `qwen2.5:7b` | 2,340 ms | **2.6 ms** | 900배 |

**L6 가설이 실측으로 확정됐다.** 라우터가 6개 핀을 오가는 구조에서 스왑 비용이 사실상 사라진다.
`MAX_LOADED_MODELS=3` + `KEEP_ALIVE=30m`로 3모델(7.1 GB)이 전부 상주했다.

#### ③ 백엔드·flash attention — **[교란 있음, 재측정 필요]**

| 모델 | `baseline`(ROCm·flash off) | `vulkan`(IGPU_ENABLE=1·flash **on**) | 차이 |
|---|---|---|---|
| `qwen2.5:3b` | 75.2 | 81.4 | +8.1% |
| `qwen2.5:7b` | 39.8 | 41.9 | +5.2% |
| `qwen3.5:27b` | 11.7 | 11.9 | +1.9% |
| **`qwen3:30b-a3b`** | 58.2 | **70.8** | **+21.5%** (prefill +26.8%) |

⚠️ **이 비교는 그대로 결론이 될 수 없다 — 두 가지 결함이 있다.**
1. **레버 2개가 동시에 바뀌었다**(백엔드 + flash attention). 어느 쪽 효과인지 갈리지 않는다.
2. **`vulkan` 프리셋이 Vulkan을 썼다는 보장이 없다.** `OLLAMA_IGPU_ENABLE=1`은 Vulkan iGPU 장치를 *후보로 살릴 뿐*이고,
   실제 선택은 서버 로그의 `msg="inference compute" library=…`가 정본이다. 그 줄을 확인하지 않았다.

**대책(반영 완료)**: `rocm` 프리셋 신설 — `vulkan`과 **`OLLAMA_IGPU_ENABLE` 하나만** 다르다.
`baseline → rocm`이 flash attention 효과, `rocm → vulkan`이 백엔드 효과로 갈린다.
오케스트레이터는 이제 매 프리셋마다 서버가 **실제로 고른 `library`/`compute`를 출력**한다.

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\ops\tune_and_bench.ps1 -Presets "baseline,rocm,vulkan"
```

> **20% 규칙 적용**: MoE의 +21.5%만 재현성 폭(8~18%)을 넘어선다. 나머지 3종(+1.9~8.1%)은 **유의하다고 말하지 않는다.**

#### ④ 재현성 3회차 — 전원 고정 후에도 첫 회차는 여전히 높다

| 모델 | clean 08:29 | baseline 09:40 | baseline 21:17 |
|---|---|---|---|
| `qwen2.5:3b` | 83.4 | 76.1 | 75.2 |
| `qwen2.5:7b` | 42.3 | 39.8 | 39.8 |
| `qwen3.5:27b` | 11.9 | 11.7 | 11.7 |
| `qwen3:30b-a3b` | 71.5 | 58.7 | 58.2 |

2·3회차는 서로 잘 맞는다(≤1.5%). **1회차만 높다.** 즉 재현성 문제는 무작위 산포가 아니라
**1회차 특이성**일 가능성이 크다 — 그 측정만 `-NoUnload` 없이 5모델을 돌린 첫 세션이었다. **[미규명]**

#### ⑤ 도구 결함 9회차 — 빈 응답을 0 t/s로 기록

`resident`의 재방문 첫 런이 `gen 0 t/s | out  tok`으로 찍혔다(`eval_count` 없음).
0은 측정이 아니라 실패인데 정상값으로 섞여 중앙값을 오염시킨다. **대책**: `eval_count ≤ 0`이면 실패로 분류한다.

### ✅ 레버 분리 측정 — flash attention과 백엔드를 갈랐다 (2026-08-22 21:30 · 3 프리셋 각 8/8 성공)

`baseline`(flash off) → `rocm`(flash **on**) → `vulkan`(flash on + `IGPU_ENABLE=1`). 인접 프리셋은 **레버 하나만** 다르다.

#### flash attention 효과 (`baseline` → `rocm`, 둘 다 ROCm)

| 모델 | 생성 | prefill | **왕복** |
|---|---|---|---|
| `qwen2.5:3b` | +7.2% | +3.7% | −18.9% |
| `qwen2.5:7b` | +3.7% | +3.3% | −14.0% |
| `qwen3.5:27b` | −0.5% | +3.1% | −4.3% |
| **`qwen3:30b-a3b`** | **+20.3%** | **+21.7%** | **−34.8%** |

⇒ **채택.** MoE에서 20% 규칙을 넘고, 나머지도 왕복이 일관되게 줄며 **손해가 없다.**

#### 백엔드 효과 (`rocm` → `vulkan`) — **트레이드오프**

| 모델 | 생성 | prefill | **왕복** |
|---|---|---|---|
| `qwen2.5:3b` | +14.4% | −12.4% | −7.3% |
| `qwen2.5:7b` | +12.5% | −24.9% | −3.9% |
| **`qwen3.5:27b`** | +9.3% | **−75.2%** | **+68.1%** (13.1s → 21.1s) |
| **`qwen3:30b-a3b`** | **+21.2%** | **−46.7%** | +8.8% |

⇒ **ROCm 유지.** Vulkan은 문헌대로 생성에서 앞서지만 **prefill을 크게 깎는다.**
WhyMath는 긴 프롬프트·짧은 출력(PRM 단계 검증·동치 판정)이 주력이라 **왕복이 판단축**이고, 그 축에서 큰 모델이 크게 손해다.
생성 t/s만 봤다면 정반대 결론을 냈을 것이다.

> **[미확정] 백엔드 라벨** — `library=` 출력이 세 프리셋 모두 `ROCm`으로 찍혔다. 그러나 성능 지문(생성↑·prefill↓)은
> 백엔드 전환과 정확히 부합한다. **원인은 도구 결함 10회차**: 그 줄에 **시간 필터가 없어 이전 기동의 로그를 읽었을 수 있다**
> (bench 로그 tail에는 넣었던 필터를 여기엔 빠뜨렸다 — 같은 실수의 반복). 수정 완료, 다음 실행에서 확정된다.
> **결론(ROCm 유지)은 라벨이 아니라 왕복 수치에 근거하므로 이 미확정에 영향받지 않는다.**

**이 시점의 결론 전환**: 최초 질문("ROCm이 왜 안 잡히나")은 **이 머신에서 성립하지 않는다** — 이미 잡혀 있다.
실제 병목 후보는 ①과대 컨텍스트(256K) ②병렬 4 ③flash attention 꺼짐 ④전원 Balanced ⑤dense 27B의 대역폭 벽이다.

---

## 6. WhyMath 적용 — 측정이 끝나면 결정할 것 3개

1. ✅ **`LOCAL_LATENCY_MS` 보정 — 불요로 판정(2026-08-22)** [코드+실측]. 실측 왕복(prefill 796자 + 128토큰)을 현행 상수와 대조:

   | 티어 | 현행 상수 | 실측 | 판정 |
   |---|---|---|---|
   | FAST (`qwen2-math:1.5b`) | 1,010 ms | 906 ms | 상수가 10% 보수적 |
   | MID (`qwen2-math:7b`급) | 3,918 ms | 3,551 ms | 상수가 9% 보수적 |
   | QUALITY (`qwen3.5:27b`) | 13,886 ms | 12,406 ms | 상수가 11% 보수적 |

   **셋 다 실측이 상수보다 빠르다** — 즉 라우터는 로컬을 실제보다 느리다고 보고 있고, 이는 클라우드 승급 쪽으로
   기우는 *안전측* 오차다. 상수를 건드리면 승급 판정이 바뀌므로 **근거 없는 변경을 하지 않는다.** 상수는 검증됐다.
2. **QUALITY 티어 재검토** → **`OPS-48` 정확도 축 실측 완료(2026-08-22/23)** [실측]. `qwen3.5:27b`(dense)와 `qwen3:30b-a3b`(MoE)를 같은 결함 주입 시험지로 Wilson 단측 경계·CLI exit 0/1로 판정한다.

   **① 초기 탐색(2026-08-22, 결함 50 · 무결함 50)** — 후보가 기준보다 열등하지 않았으나 **파싱 실패율 16%**로 리스크가 드러났다.

   | 지표 | qwen3.5:27b (기준) | qwen3:30b-a3b (후보) | 비고 |
   |---|---|---|---|
   | 처리 문항 / 미분류·파싱실패 | 100 / 1 | 100 / 16 | 후보가 clean에서도 10/50, broken_latex에서 4/7 파싱 실패 |
   | 검출률 (결함 中) | 24/49 = **0.490** | 28/44 = **0.636** | 95% Wilson 하한 0.376 → 0.512 |
   | 오경보율 (무결함 中) | 3/50 = **0.060** | 2/40 = **0.050** | 95% Wilson 상한 0.141 → 0.140 |
   | 왕복 지연(mean) | **7,376 ms** | **1,408 ms** | **5.2배** 빠름 |
   | 왕복 지연(median) | **6,867 ms** | **1,105 ms** | **6.2배** 빠름 |

   **② 파싱 안정화 후 확정 측정(2026-08-23, 결함 100 · 무결함 100 · seed 20260708)** — JSON schema에 `additionalProperties: false`와 `reason.maxLength: 80`을 추가하고 system prompt에 `reason`을 40자 이내로 제한한 뒤 재측정.

   | 지표 | qwen3.5:27b (기준) | qwen3:30b-a3b (후보) | 비고 |
   |---|---|---|---|
   | 처리 문항 / 미분류·파싱실패 | 200 / **0** | 200 / **0** | **파싱 실패율 16% → 0%** |
   | 검출률 (결함 100 中) | 53/100 = **0.530** | 72/100 = **0.720** | 95% Wilson 하한 0.448 → 0.641 |
   | 오경보율 (무결함 100 中) | 8/100 = **0.080** | **47/100 = 0.470** | 95% Wilson 상한 0.136 → **0.552** |
   | 왕복 지연(mean) | **4,980 ms** | **1,683 ms** | **3.0배** 빠름 |
   | 왕복 지연(median) | **4,766 ms** | **1,506 ms** | **3.2배** 빠름 |

   **“6배”와 “3배”가 공존하는 이유** — 둘은 서로 다른 지표다. §5.1 벤치의 “6.0배”는 **생성 t/s**(dense 11.5 vs MoE 68.7)를 말한다. §6.2 품질 배틀의 “3배”는 **왕복 지연 mean**이다. 50+50의 mean(5.2배)과 median(6.2배)가 크게 벌어진 것은, 파싱 실패할 때 후보가 512 토큰까지 긴 출력을 내며 latency outlier(최대 18,064 ms)를 만든 탓이다. 100+100에서 파싱이 안정화되자 출력 토큰 수가 126.6 → 36.1로 줄고 outlier가 사라져 mean과 median이 비슷해졌다. 동시에 dense 기준 지연도 7,376 ms → 4,980 ms로 줄어(설정 고정·캐시 무력화·모델 상주 효과) mean ratio는 3.0배로 수렴했다.

   **오경보가 5% → 47%로 폭증한 이유** — 핵심은 **파싱 실패 10건이 “미분류”에서 “오경보”로 재분류된 것**이다. 50+50에서 clean 문항 50개 중 10개는 JSON 파싱에 실패했지만 `detected=true`로 찍혔다. `parsed=false`라 이 10개는 오경보율 분모에서 제외되어 2/40 = 5%로 보였다. 100+100에서는 파싱이 0%로 안정화되어 이 10개가 `parsed=true`로 잡히면서 오경보에 합류했다. 거기에 더해 후보의 전반적인 탐지 민감도도 높아져, clean 문항 100개 중 47개를 결함으로 오판했다.

   **판정**: `require-candidate-not-worse-than-baseline` 마진 0.00 — **exit 1, FAIL**. 후보의 오경보 95% 상한(0.552)이 기준 상한(0.136)을 **크게 웃돌았다**. 검출률은 높지만 무결함 문항을 너무 많이 결함으로 잡는다.

   **결론**: **qwen3:30b-a3b는 QUALITY 티어 후보가 아니다.** 파싱 형식 안정화는 성공(16% → 0%)했으나, 정확도 축에서 기준 dense 모델보다 열등하다. QUALITY 티어는 현행 `qwen3.5:27b`(dense)를 유지한다. 향후 MoE 후보를 재검토할 때는 오경보율 Wilson 상한이 기준을 넘지 않는 것을 먼저 확인한다.
   - 실행기: `scripts/ops/run_moe_quality_battle.ps1`
   - 감사 파일: `data/audit/ops-48-moe-accuracy-battle-20260823_101954.jsonl`
   - 하니스: `src/backend/whymath_backend/harness/quality_tier_moe_accuracy_battle.py`

3. **로컬 vs OpenRouter 비교축** — t/s만으로 고르지 않는다. `detection accuracy` / `false alarm` / `왕복 지연` / `t/s` / `컨텍스트` / `비용` / `반복 실행 안정성` 7축으로 비교하고, **정확도 축은 결함 주입 강등전으로 판정**한다(`docs/standards/superhuman_verification_standard.md`). 로컬이 정확도에서 지더라도 지연·비용에서 이기는 구간이 있고, 그 반대도 있다.

---

## 7. 하지 말 것 (안티패턴)

- ❌ **여러 레버를 동시에 바꾸기** — 무엇이 효과였는지 영구히 알 수 없게 된다.
- ❌ **재설치부터 하기** — 드라이버·ROCm 재설치는 증거를 지운다. 측정이 먼저다.
- ❌ **`ollama ps`의 "100% GPU" 문자열만 보고 성공 판정** — 오프로드 비율은 맞아도 t/s가 기대치의 1/3일 수 있다. `gpu_fraction`과 `gen_tps`를 **둘 다** 본다.
- ❌ **`HIP_VISIBLE_DEVICES=-1`을 ROCm 경로에 남겨두기** — GPU가 통째로 꺼진다.
- ❌ **27B dense가 느린 것을 설정 탓으로 돌리기** — §2 물리 한계다.
- ❌ **검사 명령 출력을 `-q`/`tail`로 잘라 통과 선언** — 판정은 exit code로 한다(CLAUDE.md 2026-08-09 등재).
- ❌ **로그 tail을 시간 필터 없이 붙여 "이번 실행의 증거"로 읽기** — 실행이 아예 안 된 런에 **이전 런의 로그**가 붙어 나오면,
  없는 원인을 분석하게 된다. 실행 시작 시각 이후의 줄만 자르고, 해당 줄이 **0건이면 그 사실 자체를 보고**한다
  ("서버가 로드를 시도조차 하지 않았다" = 요청이 서버에 닿기 전에 거부됐다는 결정적 단서다).
  (사고 경위: 2026-08-22 `-Models` 파싱 버그로 실행이 안 된 두 런에 07:56 OOM 로그가 그대로 붙었다.)
- ❌ **`powershell.exe -File` 로 배열 인자를 넘기면서 콤마 분해를 기대하기** — `-File` 모드는 인자를 **문자열 그대로** 넘긴다.
  `-Models a,b` 는 원소 2개가 아니라 `"a,b"` 원소 1개로 도착해 서버에서 `invalid model name`이 된다.
  스크립트가 스스로 콤마를 분해하고, **서버에 던지기 전에 설치 목록과 대조**한다.
  (사고 경위: 2026-08-22 측정 2회가 이 한 가지 이유로 통째 공전했다.)
- ❌ **실패한 로드의 잔해를 치우지 않고 다음 측정 돌리기** — 실패한 `llama-server`는 종료되지 않고 남아 **커밋을 계속 점유**한다.
  그러면 다음 로드가 더 적은 자원으로 시작해 또 실패하고, 잔해가 하나 더 쌓인다. **실패가 실패를 만드는 자기증식**이다.
  측정 전에 `/api/ps`(상주 모델)와 `Get-Process llama-server`(실제 프로세스)를 **대조**하고, 불일치하면 정리부터 한다.
  (사고 경위: 2026-08-22, 하루 전 08:47·09:22에 뜬 고아 2개가 커밋 19.3 GB를 잡아 커밋 여유를 0.9 GB로 만들었다.
  그 상태에서 잰 사다리 측정 전체가 오염돼 있었다.)
- ❌ **물리 메모리 여유만 보고 "메모리는 충분하다"고 판정** — Windows의 구속 자원은 **커밋 한도(물리 + 페이지파일)** 이고,
  물리 여유 34.9 GB에서도 커밋 여유가 0.9 GB면 1.0 GiB 할당이 실패한다. 물리·커밋·페이지파일을 **각각** 본다.
- ❌ **HTTP 실패를 예외 *타입명*만으로 기록하기** — 500의 원인은 타입명이 아니라 **응답 본문**에 들어 있다.
  `System.Net.WebException`은 8개 모델이 전부 다른 이유로 죽어도 똑같이 찍힌다.
  (사고 경위: 2026-08-22 Phase 1 1차에서 7개 모델이 전건 500이었는데 본문을 버려 원인 판정이 불가능했고, 측정 1회가 통째로 공전했다.
  대책 = `Get-HttpErrorBody`(ErrorDetails.Message → Response 스트림 순서로 본문 추출) + 실패 시 서버 로그 tail 자동 첨부.)
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
