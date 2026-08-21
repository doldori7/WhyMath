# Phaiakes9 로컬 LLM 스택 최적화 — 외부 제안 검토 + PC 설정 정본

> **성격**: 외부(ChatGPT) 제안 "Ryzen AI Max+ 395용 최적 LLM 구성"에 대한 **실측 기반 검토서** +
> 이 PC에서 실제로 바꿀 **설정 정본**.
>
> **관련 태스크**: `OPS-43-local-llm-stack-optimization`(todo) · `S4-16-residue-gate-demotion-battle`(blocked) · `KG-02`(blocked)
>
> **근거**: `MEMORY.md` 2026-05-16 / 2026-05-19 / **2026-08-14** 결정 로그 · `docs/architecture/03a_l3_router_design.md` §A.1 ·
> `src/backend/whymath_backend/l3/router.py` `LOCAL_MODEL_MATRIX` · `infra/phaiakes9/GPU_ACTIVATION_FOLLOWUP.md` §2.1
>
> **정직성 경계**: 이 문서의 *산술*(대역폭 유도치)은 실측 두 점에서 계산한 것이고, *원인 가설*은 가설이다.
> 어느 것도 실측을 대체하지 않는다 — §5 진단 사다리가 가설을 판정한다.

---

## 0. 결론 3줄

1. **제안의 전제가 우리 실측과 어긋난다.** 제안은 "이 PC는 상당히 좋은 로컬 LLM 머신"에서 출발하는데,
   우리 **2026-08-14 실측**은 같은 PC에서 `qwen3.5:27b`가 **0.5~1 tok/s**다 —
   2026-05-16 같은 모델 **9.22 tok/s** 대비 **9~18배 회귀**. **현 스택은 느린 게 아니라 고장 나 있다.**
2. **따라서 122B 도입은 지금 논의할 문제가 아니다.** 5% 효율로 도는 스택에 4배 큰 모델을 얹는 것은
   순서가 뒤바뀐 것이다. 게다가 §4 산술상 **dense 122B는 OPS-43 acceptance ①(60초 이내)을 원리적으로 못 넘는다.**
   반대로 **27B는 스택만 고치면 넘는다.**
3. **질문("최적 PC 설정")의 답은 §6 표**다. 핵심은 BIOS UMA 고정 · KV 캐시 예산(컨텍스트 길이 × 병렬수) ·
   백엔드(DirectML/Vulkan/ROCm) 실측 선택 — **셋 다 모델 교체 없이 되돌릴 수 있는 설정**이다.

---

## 1. 제안에서 **수용**하는 것

| 제안 | 판정 | 비고 |
|---|---|---|
| LLM = reasoning generator, Verifier = truth authority | ✅ **이미 우리 헌법** | CLAUDE.md "SymPy 단일 권위"·"검증 없이 학생 제공 금지". 새 제안이 아님 |
| 최종 PASS/FAIL은 LLM이 아니라 게이트 | ✅ 이미 정본 | `superhuman_verification_standard.md` 검증 권위 서열 ①기계증명 ②측정통과 게이트 ③인간폴백 |
| solver와 reviewer의 **목표를 반대로** 준다(적대적 프롬프트) | ✅ **진짜 새로운 부분** | 현 `cross_verify`는 K=3 *동일 목표* 다관점. 목표 반전은 미도입 — 채택 가치 있음 |
| 작은 모델 캐스케이드로 큰 모델 호출을 아낀다 | ✅ 이미 구현 | 축1(LOCAL/CLOUD)×축2(FAST/MID/QUALITY)×축3(MATH/GENERAL) 3축 라우터 |
| 7B/14B를 버리지 말고 보조로 | ✅ 이미 그렇게 함 | `LOCAL_MODEL_MATRIX` 1.5b/3b/7b 현역 |

**요약**: 제안의 *아키텍처 사상*은 우리가 이미 하고 있는 것과 거의 같다. 새로 얻을 것은
**적대적 리뷰어(목표 반전)** 한 가지다.

---

## 2. 제안이 **놓친** 결정적 사실 — 우리 실측

제안은 스펙시트(128GB·40CU·8000MT/s)에서 출발했고, 우리 로그는 정반대를 말한다.

| 시점 | 백엔드 | `qwen3.5:27b` | 출처 |
|---|---|---|---|
| 2026-05-16 | Windows Ollama 0.24.0 + **DirectML** | **9.22 tok/s** · p50 13,886ms | MEMORY 2026-05-16 / 03a §A.1 |
| 2026-08-14 | Windows 11 + Ollama + **ROCm** | **0.5~1 tok/s** · 115~300s/call (180s timeout 3/3) | MEMORY 2026-08-14 · OPS-43 notes |

**회귀 폭 9~18배.** MEMORY 2026-08-14 스스로 "하드웨어 한계가 아니라 소프트웨어 스택 문제로 추정"이라 적었다.
이 회귀가 S4-16을 blocked로 만들었고, S4-16이 KG-02를 blocked로 잡고 있다.

> **그래서 이 검토의 1순위 권고는 "122B를 살까"가 아니라 "왜 27B가 자기 기록의 1/10로 도는가"다.**
> 후자는 blocked 태스크 2건을 푼다. 전자는 아무것도 풀지 않는다.

---

## 3. 이 PC의 물리 상한 — 실측 두 점에서 유도

로컬 추론의 토큰 생성 속도는 사실상 **메모리 대역폭 / 토큰당 읽는 바이트**다.

```
이론 상한 = 8000 MT/s × 256 bit ÷ 8 = 256 GB/s   (LPDDR5X-8000 · 256-bit)

실효 대역폭 = 모델 크기 × tok/s
  2026-05(DirectML) : 17 GB × 9.22  ≈ 157 GB/s  → 이론 대비 61%   (iGPU로는 정상 범위)
  2026-08(ROCm)     : 17 GB × 0.75  ≈  13 GB/s  → 이론 대비  5%   ← 고장 신호
```

**5%는 CPU 추론보다도 느리다.** 2026-05-15 CPU baseline은 `qwen2-math:7b`(4.4GB) 12.62 tok/s = 약 56 GB/s였다.
같은 CPU 경로라면 27B는 약 3.3 tok/s가 나와야 한다. **0.5~1 tok/s는 순수 CPU보다 3~6배 더 느리다** —
이는 "GPU를 못 쓰는 상태"가 아니라 **"GPU와 CPU 사이에서 레이어가 쪼개져 매 토큰 복사가 일어나는 상태"**의 전형적 지문이다(§5 가설 A·B).

---

## 4. 122B 판정 — dense냐 MoE냐가 전부를 뒤집는다

제안은 `Qwen3.5 122B Q4_K_M`(약 70GB)을 주 추론 모델로 권한다. 위 산술을 그대로 적용하면:

| 시나리오 | 27B tok/s | 122B **dense** 추정 tok/s | OPS-43 ①(<60초) |
|---|---|---|---|
| 현 상태(고장) | 0.5~1 | **0.12~0.24** | ❌ 논외 |
| 스택 복구(2026-05 수준 157 GB/s) | 9.22 | **2.2** | ❌ 68~136초 |
| 이론 근접 튜닝(218 GB/s·85%) | 12.8 | **3.1** | ❌ 48~97초 (경계·불안정) |
| **27B, 스택 복구** | **9.22** | — | ✅ **16~33초** |

> **판정**: `cross_verify` 1콜의 실측 생성량(115~300초 × 0.5~1 tok/s ≈ 150~300 토큰)을 기준으로,
> **dense 122B는 스택을 완벽히 튜닝해도 OPS-43 acceptance ①을 못 넘는다. 27B는 스택 복구만으로 넘는다.**

**단, 122B가 MoE라면 결론이 뒤집힌다.** MoE는 토큰당 *활성 파라미터*만 읽으므로
"용량은 크고 대역폭은 좁은" 통합메모리 머신에 오히려 이상적이다. 활성 A10~20B급이면 8~15 tok/s가 나온다.

- **판별법 1줄**: 돌려 보고 tok/s를 본다. **2~3 tok/s면 dense(기각), 8 tok/s 이상이면 MoE(재검토 가치 있음)**.
- **주의**: 제안이 인용한 `mdq100/qwen3.5:122b-96g`는 **공식 Qwen 네임스페이스가 아닌 커뮤니티 재업로드**다.
  CLAUDE.md "환경 사실의 추론 등재 금지"·의존성 상한 원칙에 따라, 3자 quant는 *실측 후보*로만 다루고
  라우터 핀으로 승격하지 않는다.

**추가로 제안이 계산하지 않은 것 — 동거 불가**:

```
제안 스택 동시 상주 요구 = 122B(70GB) + R1-32B(20GB) + 27B(17GB) = 107GB  >  96GB VGM
게다가 96GB를 GPU에 고정하면 OS·페이지캐시에 32GB만 남아 70GB 모델은 RAM 캐시조차 안 된다
→ 모델 전환마다 NVMe에서 70GB 풀 리드(수십 초). 캐스케이드가 스와핑으로 붕괴한다.
```

반면 **현 스택 전체 + 32B 리뷰어는 64GB에 전부 동거한다**:

| 모델 | 크기 | 근거 |
|---|---|---|
| qwen2-math:1.5b | 1.4 GB | 2026-05-19 `ollama ps` 실측 |
| qwen2.5:3b | ~2.2 GB | 추정 |
| qwen2-math:7b | 5.2 GB | 2026-05-16 `ollama ps` 실측 |
| qwen2.5:7b | ~5.2 GB | 추정 |
| qwen3-vl:8b | 6.1 GB | 라우터 주석 실측 |
| qwen3.5:27b | 17 GB | 2026-05-19 실측 |
| (신규) 32B 리뷰어 Q4 | ~20 GB | 추정 |
| **합계** | **≈ 57 GB + KV** | **64GB VGM에 무스와핑 동거** |

> **그래서 VGM 권고는 96GB가 아니라 64GB다.** 96GB는 122B를 *단독 상주*시킬 때만 의미가 있고,
> 그 대가로 페이지캐시를 잃는다.

---

## 5. 회귀 원인 가설 + 진단 사다리 (가설을 판정하는 절차)

0.5~1 tok/s를 만드는 후보는 4개다. **전부 설정이지 하드웨어가 아니다.**

| # | 가설 | 왜 이 증상이 나오나 | 판별 신호 |
|---|---|---|---|
| **A** | BIOS UMA Frame Buffer가 `Auto`(작게 잡힘) | ROCm이 보고하는 VRAM이 작아 Ollama가 일부 레이어만 GPU에 올림 → 매 토큰 CPU↔GPU 왕복 | `ollama ps` PROCESSOR가 **100% GPU가 아님** |
| **B** | 컨텍스트 길이 × 병렬수로 **KV 캐시 폭발** | KV가 VRAM을 잡아먹어 A와 같은 부분 오프로드 유발. 27B에 128K 컨텍스트면 KV만 수십 GB | `OLLAMA_DEBUG=1` 서버 로그의 `offloaded X/Y layers` |
| **C** | ROCm 백엔드가 gfx1151에서 미성숙 | 5월 DirectML 9.22 → 8월 ROCm 0.75. **백엔드 교체가 회귀와 같은 구간에 있다** | DirectML/Vulkan으로 되돌려 재측정 |
| **D** | 전력 프로파일·써멀 | 지속 클럭 하락. 단 10배는 설명 못 함 | 보조 요인으로만 |

**A·B가 1순위다** — `ollama ps` 한 줄이 A를, 디버그 로그 한 줄이 B를 즉시 판정한다.
2026-05-19 로그에 **"Windows GPU 적재: 100% GPU, 1.4 GB VRAM (`ollama ps`)"** 라고 적혀 있으므로,
지금 같은 명령이 100% GPU가 **아니면** 그것이 회귀의 직접 증거다.

### 계측 갭 (먼저 메워야 하는 것)

`infra/phaiakes9/benchmark/bench_latency.py`는 `eval_count`(생성 토큰)만 읽고
**`prompt_eval_count`/`prompt_eval_duration`(프리필)을 기록하지 않는다**(`:210-211` 실측).

이 때문에 현재 벤치는 **"생성이 느린가"와 "프리필이 느린가"를 구분하지 못한다.**
`cross_verify`는 3개 풀이를 한 프롬프트에 넣으므로 프리필이 지배적일 수 있고,
그 경우 처방이 완전히 달라진다(대역폭 문제가 아니라 연산 문제 → 컨텍스트 축소·배치가 답).
**Ollama 응답에 이미 두 필드가 오므로 기록만 추가하면 되는 소규모 변경이다.**

---

## 6. 권고 PC 설정 (질문의 직접 답)

> **원칙**: 전부 되돌릴 수 있는 설정이다. 한 번에 다 바꾸지 말고 **§7 순서대로 한 축씩** 바꾸며 측정한다
> (동시 변경은 어느 것이 효과였는지 못 가린다).

### 6.1 BIOS

| 항목 | 권고값 | 이유 |
|---|---|---|
| `UMA Frame Buffer Size` (Advanced → Graphics Configuration) | `Auto` → **`Fixed` 64 GB** | 가설 A 제거. `GPU_ACTIVATION_FOLLOWUP.md` §2.1이 이미 "최우선"으로 지목 |
| Above 4G Decoding / Resizable BAR | Enabled | 대용량 VRAM 접근 전제 |
| 전력 프로파일 (TDP) | 최고 성능 프로파일 | 프리필은 연산 바운드라 지속 클럭에 민감 |
| 메모리 속도 | LPDDR5X **8000 MT/s** 확인 | 다운클럭 시 §3 상한이 그대로 깎임 |

**64GB를 권하는 이유**: §4 표대로 현 스택 전 모델 + 32B 리뷰어가 57GB에 동거한다.
96GB는 dense 122B를 단독 상주시킬 때만 의미가 있고 페이지캐시를 잃는다.
**122B가 MoE로 판명되면 그때 96GB로 올린다** — 그전에는 손해다.

### 6.2 Ollama 환경변수 (Windows 사용자 환경변수)

| 변수 | 권고값 | 이유 |
|---|---|---|
| `OLLAMA_CONTEXT_LENGTH` | **8192** (필요분만) | **가설 B 직접 처방.** 실측 트래픽은 input p50 **74 토큰**·output p50 358(`router.py` 주석). 128K는 우리 워크로드에 없는 것을 위해 KV를 수십 GB 태우는 설정이다 |
| `OLLAMA_NUM_PARALLEL` | **1** (27B급), 4 (1.5b/3b) | KV는 병렬수에 **곱해진다**. 27B는 c=4에서 처리량 이득 **~0%**(03a §A.1 실측)라 병렬을 켤 이유가 없다. 1.5b는 c=4에서 +15%라 켤 값어치 있음 |
| `OLLAMA_FLASH_ATTENTION` | **1** | 긴 컨텍스트 속도 + KV 양자화 전제 |
| `OLLAMA_KV_CACHE_TYPE` | **q8_0** | KV 메모리 절반. 품질 영향 미미 (`FLASH_ATTENTION=1` 필요) |
| `OLLAMA_MAX_LOADED_MODELS` | **3** | 캐스케이드 상주 제어. 무제한이면 서로 밀어내며 재적재 |
| `OLLAMA_KEEP_ALIVE` | **-1** (핫 경로 모델) | 재적재 지연 제거 |
| `OLLAMA_DEBUG` | 진단 중 **1**, 평시 0 | `offloaded X/Y layers` 판독용(가설 B 판정) |
| `OLLAMA_MODELS` | 가장 빠른 NVMe 경로 | 모델 전환 시 디스크 리드가 지배적 |
| `OLLAMA_HOST` | `0.0.0.0` | 실기기 데모 도달(기존 `run_demo.ps1` 규약) |

### 6.3 백엔드 선택 — **추정 금지, 실측으로 고른다**

MEMORY 2026-05-16에 이런 줄이 있다:

> "DirectML 대신 Vulkan 명시 — 폐기: 두 백엔드 효율 차이 **미미 추정**(Strix Halo 특성)"

이것은 **실측이 아니라 추정**이고, CLAUDE.md "환경 사실의 추론 등재 금지"에 걸린다.
그리고 그 뒤 실제로 백엔드를 ROCm으로 바꿨을 때 **9~18배 회귀**가 났다 — 추정이 틀렸다는 증거다.

→ **DirectML · Vulkan · ROCm 3종을 동일 벤치로 측정해 고른다.** 우리는 이미 도구가 있다
(`bench_latency.py` + `sample_prompts.json`, temperature 고정·워밍업 1회·동일 8문항).

### 6.4 Windows

- 전원 관리: `최고의 성능`, iGPU 절전 해제
- WSL2 경유 금지: `172.17.112.1`은 **WSL2 CPU 경로**다(2026-05-20 실측 교훈).
  벤치·서빙 모두 **`127.0.0.1`(Windows 네이티브 GPU)** 을 쓴다
- 백신 실시간 검사에서 `OLLAMA_MODELS` 경로 제외(대용량 리드 지연)

---

## 7. 모델 스택 권고 (제안 수정판)

| 역할 | 제안 | **본 검토 권고** | 근거 |
|---|---|---|---|
| 빠른 1차 | Qwen3.5 27B | **현행 유지**(1.5b/3b/7b 매트릭스) | 이미 3축 라우터로 배선·실측 완료 |
| 주 추론 | **Qwen3.5 122B** | **`qwen3.5:27b`(스택 복구 후)** | §4 — dense 122B는 OPS-43 ① 미달, 27B는 통과 |
| 독립 검증 | DeepSeek-R1-Distill-Qwen-32B | **후보로 채택·단 측정으로 선발** | 아래 ⚠️ |
| 최종 판정 | SymPy/수치 검증기 | **이미 정본** | CLAUDE.md SymPy 단일 권위 |

⚠️ **R1-Distill 계열의 숨은 비용 — 제안이 계산하지 않은 것**: R1 계열의 실질 비용은 파라미터가 아니라
**thinking 토큰 수**다. 32B Q4(20GB)는 스택 복구 시 약 7.8 tok/s인데, R1은 통상 1,000~8,000 사고 토큰을 뱉는다.
3,000 토큰이면 **1건당 약 6.4분**이다. 강등전 표본 240건이면 **약 25시간**(야간 배치로는 가능, 대화형은 불가).
→ 도입한다면 **비동기 배치 전용**이며, `num_predict` 상한으로 사고 길이를 반드시 잘라야 한다.

⚠️ **선발 기준은 MATH-500이 아니다.** 제안 스스로도 마지막에 그렇게 말한다.
우리 기준은 **"잘못된 풀이를 PASS시키지 않는가"** = S4-16 강등전의 검출률 Wilson 하한 / 오검출 Wilson 상한이다.
2026-08-14 실측에서 `qwen2.5:7b`는 오검출 100%, `qwen2-math:7b`는 검출 하한 0.4342 < 오검출 상한 0.8580으로
**구분력 자체가 없었다**. 공개 벤치 점수는 이 구분력을 예측하지 못했다.

⚠️ **적대적 리뷰어를 게이트로 선언하려면 강등전을 통과해야 한다.**
CLAUDE.md "측정 없는 기계 게이트를 인간 검수 대체로 선언 금지" —
목표 반전 프롬프트는 채택 가치가 있지만, 통과 전까지는 *보조 신호*이지 *판정자*가 아니다.

---

## 8. 실행 순서 (한 축씩 · 각 단계 후 동일 벤치 재측정)

```
STEP 0  현 상태 스냅샷      → ollama ps + bench 1회   (회귀 재현 확인 = 판정 기준선)
STEP 1  계측 갭 메우기      → bench에 prompt_eval_* 기록 추가 (프리필 vs 생성 분리)
STEP 2  KV 예산 축소        → CONTEXT_LENGTH=8192 · NUM_PARALLEL=1 · FLASH_ATTENTION=1 · KV=q8_0
        └─ 여기서 회복되면 원인 = 가설 B. BIOS 안 건드리고 끝.
STEP 3  BIOS UMA Fixed 64GB → 재측정
        └─ 여기서 회복되면 원인 = 가설 A.
STEP 4  백엔드 3종 비교      → ROCm vs DirectML vs Vulkan 동일 벤치
        └─ 여기서만 회복되면 원인 = 가설 C.
STEP 5  판정                → 27B가 60초/call 이내면 OPS-43 ① 충족 → S4-16 강등전 재개
STEP 6  (선택) 122B 판별    → tok/s 2~3=dense(기각) / 8+=MoE(재검토)
```

**STEP 2를 STEP 3보다 먼저 두는 이유**: 재부팅·BIOS 진입 없이 환경변수만으로 되돌릴 수 있어
**가장 싸고 가장 빨리 반증되는 가설**이기 때문이다.

---

## 9. Kiki 실행 런북 — STEP 0 (현 상태 스냅샷)

### 사전 브리핑 (6항목)

1. **과제 명칭**: Phaiakes9 로컬 LLM 스택 회귀 스냅샷 (STEP 0)
2. **목적**: 2026-08-14의 `qwen3.5:27b` 0.5~1 tok/s 회귀가 **지금도 재현되는지** 확인하고,
   `ollama ps`의 PROCESSOR 값으로 **가설 A(부분 오프로드)를 즉시 판정**한다.
   이 스냅샷이 STEP 2~4 튜닝의 **비교 기준선**이 된다. 결과는 OPS-43 acceptance ① 판정에 직접 쓰인다.
3. **구체적 절차**: ①브랜치 체크아웃 ②`ollama ps`로 적재 상태 확인(즉시) ③27B 벤치 1회(동시도 1 · 8문항 ·
   **회귀 상태면 15~40분**, 정상이면 2~3분) ④결과 JSON 확인.
4. **성공 기준**:
   - **성공(=스냅샷 확보)**: `results/<타임스탬프>.json`이 생기고 `tok/s` 값이 출력된다.
     ⚠️ 벤치의 exit code는 SLA 게이트(p50<2초) 판정이라 **27B는 어차피 exit 1**이다 —
     이 단계에서 **exit 1은 실패가 아니다.** 우리가 보는 것은 exit code가 아니라 **tok/s 수치**다.
   - **실패**: JSON이 안 생기거나 `ollama` 접속 오류 → 대처: Ollama 서비스 기동 확인
     (`Get-Process ollama`), 없으면 Ollama 앱 실행 후 재시도.
   - **핵심 판독**: `ollama ps`의 `PROCESSOR` 열이 **`100% GPU`가 아니면 → 가설 A 확정**(부분 오프로드).
     2026-05-19에는 `100% GPU`였다.
5. **실행 환경**: Phaiakes9(= 평소 쓰는 이 PC) · **Windows PowerShell** · `C:\Users\kiki\Desktop\__AI\WhyMath` ·
   선행 조건: Ollama 서비스 기동 중 · `qwen3.5:27b` 이미 로컬에 있음.
6. **창 구분**: **새 PowerShell 창 1개**. 서버를 점유하지 않으므로 이후 조작 가능.

### 명령 블록

```powershell
# ── 실행 시스템: Windows PowerShell (Phaiakes9 = 이 PC 자신 · 별도 접속 불요)
cd C:\Users\kiki\Desktop\__AI\WhyMath

# 이 문서가 있는 브랜치로 (force-push 대비 -B 형태)
git fetch origin claude/llm-optimal-pc-setup-voyp4v
git checkout -B claude/llm-optimal-pc-setup-voyp4v origin/claude/llm-optimal-pc-setup-voyp4v

# ── 자가검증 ①: 벤치 스크립트가 실제로 있는가 (없으면 아래는 전부 무의미)
Test-Path .\infra\phaiakes9\benchmark\bench_latency.py

# ── 자가검증 ②: ollama 파이썬 클라이언트
python -m pip install --user ollama

# ── 판독 1 (즉시·가설 A 판정) : PROCESSOR 열을 본다
ollama ps

# ── 판독 2 : 27B 벤치 (동시도 1 · 회귀 상태면 15~40분 소요)
python .\infra\phaiakes9\benchmark\bench_latency.py `
  --model qwen3.5:27b `
  --host http://127.0.0.1:11434 `
  --concurrency 1 `
  --num-predict 512 `
  --output .\infra\phaiakes9\results\step0-27b-baseline.json
echo "EXIT=$LASTEXITCODE  (27B는 SLA 게이트상 1이 정상 — tok/s 수치를 보세요)"

# ── 자가검증 ③: 결과 파일이 실제로 생겼는가 + tok/s 값
Test-Path .\infra\phaiakes9\results\step0-27b-baseline.json
Get-Content .\infra\phaiakes9\results\step0-27b-baseline.json | ConvertFrom-Json |
  Select-Object -ExpandProperty concurrency_runs |
  Format-Table concurrent, p50_ms, tokens_per_sec, success_count, fail_count
```

**보고해 주실 것 3가지**: ① `ollama ps`의 PROCESSOR 열 ② `tokens_per_sec` 값 ③ `p50_ms` 값.
이 셋으로 STEP 2/3/4 중 어디부터 갈지가 결정됩니다.

---

## 10. 미결 사항 (정직 표기)

- **`qwen3.5:122b`의 dense/MoE 여부 미확인** — 이 문서의 122B 판정은 *dense 가정* 산술이다.
  MoE면 결론이 뒤집히며, 판별은 §4 "tok/s 한 번 재기"로 끝난다.
- **회귀 원인 미확정** — §5는 가설이고 §8이 판정 절차다. 아직 아무것도 실측하지 않았다.
- **`prompt_eval_*` 미계측** — 프리필/생성 분리 불가 상태. STEP 1에서 해소한다.
- **적대적 리뷰어 라우터 배선 미설계** — 현 `LOCAL_MODEL_MATRIX`에 리뷰어 티어 축이 없다.
  도입 시 03a 설계 변경 + CLAUDE.md 채택 3조건(라우터 경유·실측 근거·MEMORY 로그) 필요.
- 3자 quant(`mdq100/*`) 신뢰성 미검증 — 실측 후보로만 취급, 라우터 핀 승격 금지.
