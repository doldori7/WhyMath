# L3a. 라우터 설계서 — 입력 분류기 + fast/mid/quality 분기 로직

> `docs/architecture/03_content_generation.md`(L3 캐논)의 **상세 하위 설계서**.
> 03 문서 §1 "모델 라우터"·"모델 풀" 표를 *데이터 기반 분기 로직*으로 구체화한다.
> 근거 데이터: `MEMORY.md` 2026-05-19 결정 로그(qwen2-math:1.5b GPU 측정, fast/mid/quality 3단계 라인업 확정) + 2026-05-16 로그(7b·27b GPU baseline).
>
> **범위**: *설계* 트랙. 입력 분류기·분기 결정 로직·에스컬레이션 체인·스키마 *명세*까지. 실제 구현(`.py`)·테스트는 후속 마일스톤 **M1.2**.

---

## 0. 이 설계서가 해소하는 것 — 두 라우팅 축의 명칭 충돌

L3 라우팅에는 **서로 다른 두 축**이 있다. 기존 문서는 이 둘을 한 단어(`mid`)로 겹쳐 써 모순 위험이 있었다.

| | 축1 — **비용·위치 축** (에스컬레이션) | 축2 — **로컬 모델 크기 축** |
|---|---|---|
| 질문 | "클라우드로 *올라갈* 것인가?" | "로컬에서 *어느 크기* 모델인가?" |
| 값 | `LOCAL` / `CLOUD_MID` / `CLOUD_HIGH` | `FAST`(1.5b) / `MID`(7b) / `QUALITY`(27b) |
| 비용 | 0원 / ~$0.003·0.015 / ~$0.015·0.075 | 전부 0원 (Phaiakes9 로컬) |
| 출처 | 03 문서·llm-architect.md 기존 `LLMTier` | 2026-05-19 벤치 라인업 |
| 목표 분포 | **80 / 18 / 2** (유지) | LOCAL(80%) *내부* 세분 |

**핵심**: 2026-05-19 확정된 `fast/mid/quality`는 *전부 로컬 Qwen 모델*(1.5b/7b/27b)이다. 이는 기존 `LLMTier.LOCAL/MID/HIGH`(비용·위치 축)와 **다른 축** — `LOCAL` 티어 *내부의* 모델 크기 세부 분기다. 두 축에 `mid`가 동시에 존재하여 충돌한다(클라우드 MID = Claude Sonnet vs 로컬 mid = qwen2-math:7b).

### 0.1 명칭 충돌 해소 규칙 (이 문서 전체·후속 코드에 적용)

1. **`mid`를 *단독으로* 쓰지 않는다.** 항상 축을 접두사로 한정한다.
   - 축1: `CLOUD_MID` (클라우드 중급, Claude Sonnet 계열)
   - 축2: 로컬 7b는 `LocalModelTier.MID` 또는 산문에서 `로컬 mid(7b)`로 표기
2. **축1 enum을 `CLOUD_` 접두사로 명시한다.** 기존 `LLMTier.MID/HIGH` → `CostTier.CLOUD_MID/CLOUD_HIGH`로 개명. `LOCAL`은 유지.
   - 이유: `MID`라는 맨이름이 두 축 어디에도 단독으로 속하지 않게 만들어, 코드·문서·Langfuse 태그에서 *어느 축인지 항상 자명*하게 한다.
3. **라우팅 결정은 항상 (축1, 축2) 쌍으로 표현한다.** 축2(`local_model`)는 축1이 `LOCAL`일 때만 의미를 가진다. 축1이 `CLOUD_*`이면 `local_model = None`.
   - 표기 관례: `LOCAL/FAST`, `LOCAL/MID`, `LOCAL/QUALITY`, `CLOUD_MID`, `CLOUD_HIGH`.

> **호환성 메모**: 03 문서·llm-architect.md의 기존 `LLMTier`(LOCAL/MID/HIGH)는 *축1만* 표현하던 단일 enum이었다. 본 설계는 이를 (a) 축1 `CostTier`(LOCAL/CLOUD_MID/CLOUD_HIGH)와 (b) 축2 `LocalModelTier`(FAST/MID/QUALITY)로 **분해**한다. 기존 `LLMTier.MID`→`CostTier.CLOUD_MID`, `LLMTier.HIGH`→`CostTier.CLOUD_HIGH`로 1:1 대응되므로 기존 라우팅 규칙은 의미 보존되며, *로컬 내부 세분*만 신규 추가된다. (llm-architect.md 정의 갱신은 별도 검토 — 본 설계서가 근거.)

---

## A. 두 라우팅 축의 통합 — 합성 흐름

### A.1 그라운딩 데이터 (2026-05-19 벤치, Phaiakes9 / Windows Ollama 0.24.0 + DirectML / Radeon 8060S Strix Halo)

| 로컬 티어 (축2) | 모델 | 디스크 | p50(c=1) | tok/s(c=1) | tok/s(c=4) | SLA 게이트 p50<2s | 동기 가능? |
|---|---|---|---|---|---|---|---|
| **FAST** | qwen2-math:1.5b | 934MB | **1,010ms** | 124.25 | 142.91 (+15%) | ✅ **PASS** | 예 (즉답) |
| **MID** | qwen2-math:7b | 4.4GB | 3,918ms | 32.63 | 33.81 (+4%) | ❌ FAIL (허용범위) | 예 (즉답엔 길다) |
| **QUALITY** | qwen3.5:27b | 17GB | 13,886ms | 9.22 | 9.28 (~0%) | ❌ FAIL (동기 불가) | **아니오 (비동기 전용)** |

핵심 함의 (결정 로그에서):
- **FAST(1.5b)만 SLA 게이트 통과** → *동기 대화 즉답*의 기본 경로. c=4에서 throughput이 +15% 증가(병렬 작동) → *피크 트래픽 흡수*까지 단일 GPU로 가능.
- **MID(7b) p50≈4초**: 동기 호출은 가능하나 *즉답엔 길다*. 정밀 풀이·2~3단계 추론·메인 학생 대화용. c=4에서 p50 15초로 폭발 → 동시성 제한 필요.
- **QUALITY(27b) p50≈14초 + 병렬 미작동**(GPU 100% 단일 점유) → **동기 불가. 백그라운드/비동기 큐 전용.**

### A.2 합성 흐름 (한 요청이 두 축을 통과하는 순서)

```
              ┌─────────────────────── 입력 분류기 (B장) ───────────────────────┐
요청(RoutingRequest+) ─▶ │ 신호 수집: task_type·difficulty·requires_reasoning·       │
                         │           sync·conversation_phase·subscription·budget   │
                         └───────────────────────────────┬───────────────────────┘
                                                          ▼
                            ┌──────────── 축1 결정: 클라우드로 올라가나? ────────────┐
                            │ killer/prove ─────────────────────────▶ CLOUD_HIGH (2%)│
                            │ 어려운 추론 & premium↑ ────────────────▶ CLOUD_MID  (18%)│
                            │ 그 외 ─────────────────────────────────▶ LOCAL    (80%)│
                            └───────────────────────────────┬───────────────────────┘
                                              LOCAL일 때만   ▼
                            ┌──────────── 축2 결정: 로컬 어느 크기? (C장) ───────────┐
                            │ 동기 즉답·분류·1단계 산술 ──────────────▶ FAST    (1.5b)│
                            │ 정밀 풀이·2~3단계 추론·메인 대화 ───────▶ MID     (7b) │
                            │ 검증·복잡 추론·PRM·백그라운드(비동기) ──▶ QUALITY (27b)│
                            └───────────────────────────────┬───────────────────────┘
                                                             ▼
                                              RoutingDecision (G장 스키마)
                                       {cost_tier, local_model, mode(sync/async), reason,
                                        est_latency_ms, est_cost_krw}
```

- **80%는 LOCAL로 떨어진 뒤 다시 FAST/MID/QUALITY로 갈라진다.** 즉 축2는 축1의 LOCAL 가지 *안에서만* 작동한다.
- **18%는 CLOUD_MID**(Claude Sonnet 4.6), **2%는 CLOUD_HIGH**(Claude Opus 4.7) — 03 문서 모델 풀·목표 분포 그대로.
- CLOUD 경로에서는 `local_model = None`. 축2는 평가하지 않는다.

---

## B. 입력 분류기 (Input Classifier)

라우팅 *결정*에 앞서, 요청의 신호를 수집·정규화하는 단계. 분류기 자체는 *규칙 기반*(휴리스틱)이며, 일부 신호(특히 `difficulty`·`requires_reasoning`)는 **FAST 티어 LLM 호출지점 ①/②**(개념 추출·깊이 추론)로 추정될 수 있다 — 이 경우 분류기가 라우터를 *재귀적으로* 1회 경유(FAST 고정)한다. (CLAUDE.md "LLM 호출은 항상 라우터 경유" 준수.)

### B.1 입력 신호

| 신호 | 출처 | 라우팅에서의 역할 |
|---|---|---|
| `task_type` | 호출자(L4/L5) | 'explain','diagnose','coach','generate','verify','prove','extract','match','translate','self_verify' |
| `difficulty` | 문항 메타 또는 ①/② 추정 | 'easy','medium','hard','killer' — 축1·축2 동시 영향 |
| `requires_reasoning` | 호출자 또는 ② 추정 | 다단계 추론 필요 여부 — MID/QUALITY·CLOUD 승급 신호 |
| `sync`(신규) | 호출자 | True=동기 즉답 요구, False=비동기 허용 — **QUALITY 게이팅의 핵심** |
| `conversation_phase`(신규) | L4 대화 상태 | 'greeting','probing','hint','solution_reveal','followup' — 즉답성 판단 |
| `max_latency_ms` | 호출자 | SLA 한도. <2000이면 사실상 FAST 강제 |
| `student_subscription` | 세션 | 'free','basic','premium','gifted' — CLOUD 승급 가드 |
| `budget_krw`(개명) | 쿼터 매니저 | 이 호출 잔여 예산(원). 0이면 CLOUD 차단 → LOCAL 강등 |
| `call_site`(신규) | 호출자 | 5개 핵심 호출지점 식별자 ①~⑤ (없으면 일반 호출) |

> 명명: 기존 `RoutingRequest.budget_cents`는 *원(KRW)* 단위 일일 한도(03 문서·llm-architect.md)와 불일치했다. 본 설계는 `budget_krw`로 통일한다(E장).

### B.2 5개 핵심 호출지점별 기본 로컬 티어 매핑

03 문서 "LLM 핵심 호출지점" 5개 각각의 *기본(default) 축2 티어*. 분기 로직(C장)이 신호에 따라 이 기본값을 승급/강등할 수 있다.

| # | 호출지점 | 기본 축1 | 기본 축2(로컬) | 동기성 | 근거 |
|---|---|---|---|---|---|
| ① | **개념 추출** | LOCAL | **FAST** | sync | 반복성 높음·구조 추출 단순. 캐싱 적중률 큼. 03 문서 "대체로 LOCAL로 충분" |
| ② | **깊이 추론** | LOCAL | **MID** (난이도 hard↑면 QUALITY/CLOUD) | sync→async | 위계·선수개념 의존성 추론은 다단계. 03 문서 "난이도 높으면 MID/HIGH" |
| ③ | **번역·정규화** | LOCAL | **FAST** | sync | 표기 통일·동의어 정규화는 경량. 반복성 높음(캐싱) |
| ④ | **개념 ID 매칭** | LOCAL | **FAST** (모호하면 MID) | sync | 정식 노드 ID 매칭. 반복성 높음. 매칭 실패→사람 검수(C.4) |
| ⑤ | **자기검증** | LOCAL | **QUALITY** (비동기) | **async** | 환각 방어 ③. *생성 모델과 분리된* 더 강한 모델로 교차검증. 추가 비용→샘플링(F장) |

- **①③④(추출·번역·매칭)는 FAST + 캐싱**: 반복성이 높아 캐시 적중률 기여가 크다(03 문서). 동기 가능(p50 1초).
- **②(깊이 추론)는 MID 기본**: 다단계라 FAST로 부족할 수 있다. hard 이상이면 QUALITY(비동기) 또는 CLOUD 승급.
- **⑤(자기검증)는 QUALITY 비동기 전용**: 검증은 *생성보다 강한* 모델이어야 의미가 있다. 27b는 동기 불가이므로 자기검증은 본질적으로 비동기 큐. 비용 통제 위해 *샘플링*(신뢰도 높은 LOCAL 생성물엔 일부만, F장).

---

## C. 분기 결정 로직 (Decision Table + 의사코드)

### C.1 축1 결정표 (LOCAL / CLOUD_MID / CLOUD_HIGH)

평가 순서 = 위에서 아래. 첫 매치에서 확정. (03 문서·llm-architect.md `Router.route()` 규칙을 *비용축으로* 보존·확장.)

| 우선 | 조건 | 축1 결정 | 근거 |
|---|---|---|---|
| 1 | `budget_krw <= 0` (쿼터 소진) | **LOCAL** | 비용 0원 강제. CLOUD 차단(E장) |
| 2 | `student_subscription == 'free'` | **LOCAL** | 무료 사용자 항상 로컬(기존 규칙1) |
| 3 | `difficulty == 'killer'` or `task_type == 'prove'` | **CLOUD_HIGH** | 킬러·증명(기존 규칙2). 단 쿼터·구독 가드 통과 시 |
| 4 | `requires_reasoning` and `subscription in {premium,gifted}` | **CLOUD_MID** | 어려운 진단(기존 규칙3) |
| 5 | (에스컬레이션 트리거 — D장) 로컬 결과 신뢰 미달 | **CLOUD_MID**→**CLOUD_HIGH** | 폴백 체인(D장) |
| 6 | 그 외 | **LOCAL** | 기본(기존 규칙4). 목표 분포 80% |

### C.2 축2 결정표 (LOCAL일 때만 — FAST / MID / QUALITY)

축1=LOCAL로 확정된 요청만 평가. 평가 순서 = 위에서 아래.

| 우선 | 조건 | 축2 결정 | 모드 | 근거(SLA) |
|---|---|---|---|---|
| 1 | `call_site == ⑤(자기검증)` | **QUALITY** | async | 검증은 강한 모델·비동기 |
| 2 | `sync == False` and (`task_type in {verify,generate}` or `difficulty in {hard,killer}`) | **QUALITY** | async | 27b 동기 불가 → 비동기 큐 전용 |
| 3 | `sync == True` and `max_latency_ms < 2000` | **FAST** | sync | FAST만 SLA 게이트 통과(p50 1초) |
| 4 | `conversation_phase in {greeting,followup}` or `task_type in {extract,match,translate}` or (`difficulty=='easy'` and not `requires_reasoning`) | **FAST** | sync | 즉답·분류·1단계 산술·경량 호출지점 ①③④ |
| 5 | `task_type in {explain,coach,diagnose}` and `requires_reasoning` | **MID** | sync | 정밀 풀이·2~3단계 추론·메인 학생 대화(p50 4초 허용) |
| 6 | `difficulty in {medium,hard}` and `sync == True` | **MID** | sync | 동기인데 추론 필요 → 7b(즉답보단 길지만 허용범위) |
| 7 | 그 외 | **FAST** | sync | 안전 기본값(가장 빠르고 SLA 충족) |

> **SLA 근거 요약**: *동기 즉답 = FAST*(유일하게 p50<2s) / *정밀 풀이·메인 대화 = MID*(p50≈4초, 허용) / *검증·복잡추론·백그라운드 = QUALITY*(p50≈14초, 비동기 강제). 이 3분기는 결정 로그가 명시한 "비용·품질·지연의 파레토 최적".

### C.3 핵심 분기 규칙 (산문 요약)

1. **동기 + 빠른 SLA(<2초) → 무조건 FAST.** 27b·7b는 p50가 게이트를 넘으므로 동기 즉답 자리에 올 수 없다.
2. **비동기 + 검증/생성/고난도 → QUALITY.** 27b는 동기 불가이므로 *비동기 큐로만* 호출된다(D.3).
3. **동기인데 추론이 필요 → MID.** 즉답은 아니지만(p50 4초) 정밀 풀이·메인 대화가 허용하는 범위.
4. **대화 인사·후속·경량 추출(①③④) → FAST.** 캐싱 적중률이 가장 큰 구간.
5. **자기검증(⑤)은 항상 QUALITY/비동기 + 샘플링.**

### C.4 의사코드

```python
# 의사코드 — 실제 구현은 M1.2. 두 축을 순차 평가한다.
def route(req: RoutingRequest) -> RoutingDecision:
    # ── 축1: 비용·위치 (LOCAL / CLOUD_MID / CLOUD_HIGH) ──
    if req.budget_krw <= 0:                      # 쿼터 소진 → 비용 0원 강제
        cost = CostTier.LOCAL
    elif req.student_subscription == "free":     # 무료는 항상 로컬
        cost = CostTier.LOCAL
    elif req.difficulty == "killer" or req.task_type == "prove":
        cost = guard_cloud(req, CostTier.CLOUD_HIGH)   # 가드 미통과 시 LOCAL 강등
    elif req.requires_reasoning and req.student_subscription in ("premium", "gifted"):
        cost = guard_cloud(req, CostTier.CLOUD_MID)
    else:
        cost = CostTier.LOCAL

    # CLOUD 경로면 축2 없음
    if cost != CostTier.LOCAL:
        return RoutingDecision(cost_tier=cost, local_model=None, mode="sync",
                               reason="cloud escalation",
                               est_latency_ms=cloud_latency(cost),
                               est_cost_krw=cloud_cost(req, cost))

    # ── 축2: 로컬 모델 크기 (FAST / MID / QUALITY) ──
    if req.call_site == CallSite.SELF_VERIFY:                # ⑤ 자기검증
        local, mode = LocalModelTier.QUALITY, "async"
    elif (not req.sync) and (req.task_type in ("verify", "generate")
                             or req.difficulty in ("hard", "killer")):
        local, mode = LocalModelTier.QUALITY, "async"        # 27b 비동기 전용
    elif req.sync and req.max_latency_ms < 2000:
        local, mode = LocalModelTier.FAST, "sync"            # FAST만 SLA 통과
    elif (req.conversation_phase in ("greeting", "followup")
          or req.task_type in ("extract", "match", "translate")
          or (req.difficulty == "easy" and not req.requires_reasoning)):
        local, mode = LocalModelTier.FAST, "sync"            # 즉답·경량 ①③④
    elif req.task_type in ("explain", "coach", "diagnose") and req.requires_reasoning:
        local, mode = LocalModelTier.MID, "sync"             # 정밀 풀이·메인 대화
    elif req.difficulty in ("medium", "hard") and req.sync:
        local, mode = LocalModelTier.MID, "sync"
    else:
        local, mode = LocalModelTier.FAST, "sync"            # 안전 기본값

    return RoutingDecision(cost_tier=CostTier.LOCAL, local_model=local, mode=mode,
                           reason=f"local/{local.value}",
                           est_latency_ms=local_latency(local),  # FAST≈1010, MID≈3918, QUALITY≈13886
                           est_cost_krw=0.0)
```

> 환각 방어와의 관계: `route()`는 *어디서 생성할지*만 정한다. 생성된 응답은 03 문서 "환각 방어 통합 파이프라인"(스키마→SymPy/Lean→PRM→자기검증→사람검수)을 *반드시* 통과해야 학생에게 노출된다. 라우팅은 그 파이프라인을 *대체하지 않는다*. (CLAUDE.md 절대 금기 "LLM 응답을 검증 없이 학생에게 제공 금지".)

---

## D. 에스컬레이션·폴백 체인

### D.1 단방향 승급 사슬

```
FAST(1.5b) ─▶ MID(7b) ─▶ QUALITY(27b) ─▶ CLOUD_MID(Sonnet) ─▶ CLOUD_HIGH(Opus)
   로컬 ───────────────────────────────┘         클라우드 ──────────────┘
   (비용 0원)                                     (구독·예산 가드 필수)
```

- 로컬 3단계 안에서 먼저 올린다(비용 0원). 로컬 천장(QUALITY)에서도 미달일 때만 CLOUD로 넘어간다.
- CLOUD로의 승급은 **항상 구독·예산 가드**(`guard_cloud`)를 통과해야 한다. 미통과 시 *승급하지 않고* LOCAL 최선(QUALITY) 결과 + 신뢰도 경고로 마감하거나, 신뢰 미달이 심하면 **안전 응답 패턴**(03 문서 `SAFE_FALLBACK`)으로 답을 *미룬다*(CLAUDE.md 답 미루기 원칙과 정합).

### D.2 에스컬레이션 트리거

| 트리거 | 발동 시 승급 | 비고 |
|---|---|---|
| 자기 일관성 불일치(N회 다수결 미수렴) | 다음 티어 1단계 | 환각 방어 4번 |
| 신뢰도 낮음(PRM·verdict confidence < 임계) | 다음 티어 1단계 | 환각 방어 2번 |
| 타임아웃(티어 p50·p99 초과) | 동일 티어 재시도 1회 → 실패 시 *강등 후 비동기*(FAST 동기 실패 시 MID 비동기) | SLA 보호 |
| `difficulty=='killer'` / `task_type=='prove'` | 즉시 CLOUD_HIGH(축1 규칙3) | 로컬 단계 건너뜀 |
| 도구 검증 실패(SymPy/Lean 불일치) | 재생성(동일 티어) → 반복 실패 시 사람 검수 큐 | 환각 방어 ②/3번 |
| 개념 ID 매칭 실패(④) | FAST→MID 1회 → 실패 시 사람 검수 큐 | 03 문서 "매칭 실패 시 사람 검수" |

### D.3 QUALITY 비동기 큐 경로 (명시)

QUALITY(27b)는 **동기 호출 불가**(p50≈14초, 병렬 미작동). 따라서:

- QUALITY로 라우팅된 모든 요청은 **작업 큐**(비동기 워커)로 들어간다. 호출자에게는 즉시 `job_id` 반환 → 완료 시 콜백/폴링.
- **동기 맥락에서 QUALITY가 필요해진 경우**(예: 동기 대화 중 자기 일관성 붕괴 → 검증 필요): 학생에게는 FAST/MID로 *잠정 응답 + "정밀 검증 중"* 표시를 주고, QUALITY 검증은 백그라운드에서 수행 → 결과가 잠정 응답과 다르면 정정 푸시.
- QUALITY 워커 동시성은 **1**로 제한한다(GPU 100% 단일 점유, 병렬 시 throughput 무이득·p50 폭발). 큐 깊이가 임계 초과 시 ⑤ 자기검증 *샘플링 비율을 낮춰* 부하 조절(F장).

### D.4 구독·예산 가드 (`guard_cloud`)

```python
def guard_cloud(req, desired: CostTier) -> CostTier:
    # 클라우드 승급 전 가드. 미통과 시 LOCAL로 강등.
    if req.student_subscription == "free":
        return CostTier.LOCAL                       # 무료는 클라우드 금지
    if req.budget_krw < cloud_min_cost(desired):    # 잔여 예산 부족
        return CostTier.LOCAL                       # 강등(+ 신뢰도 경고)
    if desired == CostTier.CLOUD_HIGH and req.student_subscription == "basic":
        return CostTier.CLOUD_MID                   # basic은 HIGH 불가 → MID로 제한
    return desired
```

---

## E. 비용·예산·SLA 연동

### E.1 로컬의 "한도"는 *비용*이 아니라 *리소스*

로컬(FAST/MID/QUALITY)은 토큰당 0원이다(Phaiakes9). 따라서 일일 한도(원)는 **로컬 호출에는 직접 적용되지 않는다.** 로컬의 진짜 제약은:

- **GPU 리소스**: 특히 QUALITY(27b)는 단일 GPU 100% 점유 → *동시성 1*. MID(7b)는 c=4에서 p50 폭발 → 동시성 제한.
- **호출 횟수·큐 깊이**: 남용 방지·피크 흡수는 *rate limit*과 *큐 깊이*로 관리(예산이 아님).

### E.2 일일 한도(원)와 LOCAL/CLOUD 분기 관계

| 구독 | 일일 한도(원) | 의미 |
|---|---|---|
| free | 100 | 사실상 LOCAL 전용(축1 규칙2가 항상 LOCAL). 한도는 *클라우드 우발 호출 차단선* |
| basic | 500 | CLOUD_MID 소량 가능, CLOUD_HIGH 불가(D.4) |
| premium | 2,000 | CLOUD_MID 일상 + CLOUD_HIGH 제한적 |
| gifted | 5,000 | CLOUD_HIGH 포함 폭넓게 |

- **한도는 *클라우드 호출에만* 차감된다.** 로컬 호출은 0원이므로 한도를 소모하지 않는다 → `budget_krw`는 *클라우드 잔여 예산*으로 해석.
- `budget_krw <= 0`이면 축1 규칙1이 **LOCAL 강제**. 즉 예산 소진 = "오늘은 로컬만". 학생 경험은 *느려질 수 있어도 끊기지 않는다*(웰빙 우선, CLAUDE.md 의사결정 우선순위 1 > 6).

### E.3 목표 분포 80/18/2 모니터링 + SLA 게이트

- **목표 분포(축1)**: LOCAL 80% / CLOUD_MID 18% / CLOUD_HIGH 2%. Langfuse `cost_tier` 태그 집계로 *실측 분포*를 추적(F장). 80% 미달 시 라우팅 규칙·임계값 재조정 신호.
- **로컬 내부 분포(축2)**는 별도 관찰(FAST가 다수여야 SLA·throughput 유리). 명시적 목표치는 *미설정*(라우터 가동 후 실측으로 정함, H장).
- **SLA 게이트 p50 < 2초는 FAST만 충족.** 따라서 *동기 즉답 경로의 SLA*는 "FAST로 라우팅된 비율 × FAST p50"로 평가한다. MID/QUALITY는 SLA 게이트 대상이 아니라 *각자의 허용 지연*(MID≈4초 동기, QUALITY 비동기)으로 평가.

---

## F. 캐싱·Langfuse 연동

### F.1 캐시 키에 축1·축2 포함

기존 `ResponseCache._cache_key(prompt, system, model)`(llm-architect.md)의 `model`을 **`{cost_tier}:{local_model}`** 합성 식별자로 확장한다. 같은 프롬프트라도 *어느 티어가 생성했는지*가 캐시 정체성의 일부다(FAST 응답과 QUALITY 응답을 섞지 않는다).

```python
# 예시 — 캐시 키에 두 축을 포함
def _cache_key(prompt, system, cost_tier, local_model):
    model_id = f"{cost_tier}:{local_model or '-'}"   # 예: "LOCAL:FAST", "CLOUD_MID:-"
    content = f"{system}|||{prompt}|||{model_id}"
    return f"llm:cache:{sha256(content)}"
```

- **①③④(개념 추출·번역정규화·개념 ID 매칭)는 캐시 적중률 기여가 가장 크다**(반복성 높음). 동일 교과서 텍스트·동일 개념 표현은 재호출 없이 캐시 반환. 캐싱 KPI(30%→50%)의 주력.
- **⑤(자기검증)는 *샘플링*** — 신뢰도 높은 LOCAL 생성물은 일부만 자기검증(추가 비용·QUALITY 큐 부하 절감). 샘플링 비율은 D.3 큐 깊이에 따라 동적 조절.
- 캐시 적중 시에도 Langfuse에 *cache_hit=true*로 기록(분포·KPI 왜곡 방지).

### F.2 Langfuse 기록 필드 확장

기존 추적(llm-architect.md)에 다음을 추가한다.

| 필드 | 값 | 용도 |
|---|---|---|
| `cost_tier` | LOCAL/CLOUD_MID/CLOUD_HIGH | 80/18/2 분포 모니터링 |
| `local_model` | FAST/MID/QUALITY 또는 null | 로컬 내부 분포·티어별 품질 추적 |
| `mode` | sync/async | SLA 평가 분리(동기만 게이트 대상) |
| `latency_ms` | 실측 | 티어별 p50/p90/p99 — 벤치 회귀 감시 |
| `cost_krw` | 실측(로컬=0) | 학생당 월 비용 KPI |
| `call_site` | ①~⑤ 또는 null | 호출지점별 분포·캐싱 효과 |
| `cache_hit` | bool | 캐싱 적중률 KPI |
| `escalated_from` | 직전 티어(폴백 시) | 에스컬레이션 빈도 분석 |
| `student_id_hash` | 해시 | 직접 ID 금지(기존 규칙 유지) |

---

## G. 스키마 확장 (예시 — 실제 코드는 M1.2)

> 아래는 *설계 예시*다. 실제 `.py` 파일은 후속 구현에서 작성한다. 기존 `RoutingRequest`(llm-architect.md §라우팅 규칙)를 확장하고, 축을 분리한 신규 enum·결정 객체를 추가한다.

```python
from enum import Enum
from pydantic import BaseModel, Field

# ── 축1: 비용·위치 (기존 LLMTier.MID/HIGH → CLOUD_ 접두사로 개명) ──
class CostTier(str, Enum):
    LOCAL = "local"            # Phaiakes9 로컬 (0원) — 축2로 세분
    CLOUD_MID = "cloud_mid"    # Claude Sonnet 4.6 등 (구 LLMTier.MID)
    CLOUD_HIGH = "cloud_high"  # Claude Opus 4.7 / GPT-5 등 (구 LLMTier.HIGH)

# ── 축2: 로컬 모델 크기 (2026-05-19 벤치 라인업) ──
class LocalModelTier(str, Enum):
    FAST = "fast"        # qwen2-math:1.5b — p50 1.0s, SLA PASS, 동기 즉답
    MID = "mid"          # qwen2-math:7b  — p50 3.9s, 동기 가능(즉답엔 길다)
    QUALITY = "quality"  # qwen3.5:27b    — p50 13.9s, 비동기 전용

class CallSite(str, Enum):       # 5개 핵심 호출지점
    CONCEPT_EXTRACT = "extract"  # ①
    DEPTH_REASON = "depth"       # ②
    TRANSLATE = "translate"      # ③
    CONCEPT_MATCH = "match"      # ④
    SELF_VERIFY = "self_verify"  # ⑤

# ── 입력: 기존 RoutingRequest 확장 ──
class RoutingRequest(BaseModel):
    task_type: str                       # explain/diagnose/coach/generate/verify/prove/extract/match/translate/self_verify
    difficulty: str                      # easy/medium/hard/killer
    requires_reasoning: bool
    student_subscription: str            # free/basic/premium/gifted
    max_latency_ms: int = 30000
    budget_krw: float = 0.0              # (개명) 클라우드 잔여 예산(원). 0이면 LOCAL 강제
    # ── 신규 신호 ──
    sync: bool = True                    # True=동기 즉답 요구, False=비동기 허용
    conversation_phase: str | None = None  # greeting/probing/hint/solution_reveal/followup
    call_site: CallSite | None = None    # 5개 핵심 호출지점 식별(없으면 일반 호출)

# ── 출력: 두 축을 합성한 결정 객체 (신규) ──
class RoutingDecision(BaseModel):
    cost_tier: CostTier                  # 축1
    local_model: LocalModelTier | None   # 축2 (cost_tier=LOCAL일 때만, 아니면 None)
    mode: str = "sync"                   # sync/async (QUALITY는 async 강제)
    reason: str                          # 결정 근거(디버깅·Langfuse)
    est_latency_ms: int                  # 예상 지연(FAST≈1010/MID≈3918/QUALITY≈13886/CLOUD≈가변)
    est_cost_krw: float = 0.0           # 예상 비용(로컬=0)
```

> **불변식(invariant)**: `cost_tier == LOCAL ⟺ local_model is not None`. `cost_tier in {CLOUD_MID, CLOUD_HIGH} ⟺ local_model is None`. `local_model == QUALITY ⟹ mode == "async"`. 구현 시 검증(validator)으로 강제한다.

---

## H. 미해결·후속

| # | 항목 | 내용 | 시점 |
|---|---|---|---|
| 1 | **FAST tier 품질 검증** | 1.5b가 *간단 산술·메타 응답·분류·①③④*에서 7b 대비 *품질 차이*가 충분히 작은지 측정. 차이가 크면 ①③④ 일부를 MID로 승급(C.2 조정). MEMORY.md 활성 작업·2026-05-19 후속 2번. | M1.2 (라우터 구현 시) |
| 2 | **로컬 내부 분포 목표치** | 축2(FAST/MID/QUALITY) 목표 비율 *미설정*. 라우터 가동 후 실측으로 정함(SLA·throughput상 FAST 다수가 유리). | 라우터 가동 후 |
| 3 | **mid/quality 지연 개선** | ROCm 7.2+ Linux native(옵션 F)로 7b·27b 2-5x 개선 시 *축2 결정표 임계값 재조정* 여지(MID 동기 즉답 편입 가능성, QUALITY 동기화 가능성). MEMORY.md 2026-05-19 후속 3번. | 옵션 F 완료 후 |
| 4 | **클라우드 티어 실제 연동** | CLOUD_MID(Sonnet)·CLOUD_HIGH(Opus) 실제 API 연동·비용 계측·`guard_cloud` 실측 임계값 보정. 현재는 *경로·가드 설계*만. | Phase 1 후반 |
| 5 | **`difficulty`·`requires_reasoning` 추정 경로** | 분류기가 ①/②(FAST)로 이 신호를 추정할 때의 *재귀 라우팅* 비용·정확도. 호출자가 직접 제공 vs LLM 추정의 트레이드오프. | M1.2 |
| 6 | **QUALITY 큐 SLA** | 비동기 큐의 *완료 시간 SLA*(동시성 1 가정 시 큐 대기 포함)·우선순위(자기검증 vs 백그라운드 생성) 정책 미정. | M1.2~Phase 2 |
| 7 | **llm-architect.md `LLMTier` 정의 갱신** | 본 설계의 `CostTier`/`LocalModelTier` 분해를 llm-architect.md·03 문서 인터페이스에 반영(별도 검토). 본 설계서가 근거. | 별도 |

---

> **요약**: 두 라우팅 축(비용·위치 `CostTier` × 로컬 크기 `LocalModelTier`)을 분리·합성하고 `mid` 명칭 충돌을 `CLOUD_MID`(축1) vs `LOCAL/MID`(축2) 한정 표기로 해소했다. 입력 분류기가 신호를 모아 축1(80/18/2)→축2(FAST/MID/QUALITY)를 순차 결정하며, SLA 데이터(FAST만 p50<2s, QUALITY 비동기 전용)가 모든 분기의 근거다. 라우팅은 *어디서 생성할지*만 정하고, 환각 방어 파이프라인을 대체하지 않는다.
