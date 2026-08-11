# 게임화(Gamification) 모듈 — 외부 EOS 틀 대조 **3차 재점검(r3)** (2026-08-11)

> **범위**: v1(`gamification_module_gap_review.md`, 2026-08-03) · r2(`..._r2.md`, 2026-08-04)와
> **동일한 외부 참고 문서**(『18. 게임화(Gamification)』 기능 75 레벨 · 76 경험치(XP) · 77 배지 ·
> 78 도전과제(퀘스트) · 79 학습 연속기록(Streak), 세부 55개 + 연계 7단 — WhyMath 전용이 아닌
> 일반적 틀, Kiki 제공)을 **r2 이후 7일간의 착지분이 만든 지형**과 다시 대조한 기록.
> **성격**: 처음부터의 재대조가 아니라 **델타 재점검**이다. v1 §2의 **의도적 미채택 11건**은
> 근거(CLAUDE.md·정본 20+ 인용)가 하나도 바뀌지 않았으므로 **전건 승계하며 재판정하지 않는다**
> (§2에서 트리거만 3차 재심). D 번호는 r2의 D5~D7에 이어 **D8부터** 붙인다.
> **판정 기호**: ✅ 해소 / ⚠️ 진짜 갭 → D / 🔴 회귀·악화 / ⏸ 기존 태스크 승계 / 🚫 의도적 미채택
>
> **결론 4줄**:
> 1. **최대 갭 = 계약의 우회로 존치**. `PED-08`(D5)은 학생 안전 라우트를 신설했으나, 원시 라우트
>    `GET /v1/me/harness-metrics`는 신 라우트와 **문자 그대로 동일한 게이트**(`ConsentedUser`)로
>    원시 16지표 + `gaming_suspect` 낙인 라벨 + 내부 전용 2종을 학생 토큰에 그대로 반환한다.
>    r2 D5가 이 표면을 동결한 근거("ops·리포트가 원시값으로 소비")는 **오탐**이었다 —
>    실측하면 ops 2종은 HTTP를 타지 않고 파이썬 함수를 직접 부르며, **HTTP 소비자는 0건**이다.
>    유일하게 가능한 호출자가 계약이 보호하려던 그 학생이다 → **D8**.
> 2. **두 번째 갭 = 안전 라우트에 소비자 0, 그리고 잔여가 추적을 잃었다**. `/growth-evidence`의
>    Flutter 호출 0건. `PED-15`가 그 사실을 "정직한 잔여"로 **기록하고 후속 태스크 없이 done**
>    처리했다(`acceptance: []`). 정직한 자인이 추적을 대신했다 → **D10**.
> 3. **세 번째 갭 = 반게임화라는 결정의 효능을 측정할 경로가 죽어 있다**. 최우선 검증 가설
>    D7 retention ≥ 30%(`risks.md:119` 외 전략 문서 4곳)의 유일한 측정 경로 KPI2가
>    **writer 0인 `LearningSession`**을 읽고, 그 결과를 `NO_DATA(genuine 부재)`로 표기한다 —
>    v1 D1-③이 분리하라고 못 박은 **`구조적 불가`가 `무데이터`로 위장**된다 → **D11**.
> 4. **기능 79(복귀 지원)는 7일간 진전 0**이나 **다른 세션 브랜치에 완결 구현이 있다**
>    (`4cb8d9d3`·695줄·테스트 4파일). **재구현 금지**, 회수·만료 관리 대상 → **D12**.

관련 정본: `gamification_module_gap_review.md`(v1 — 판정 근거의 원본) ·
`gamification_module_gap_review_r2.md`(r2 — 이 문서의 모체) ·
`docs/design/ui/02_student_ui_master_plan.md:87-95`("성장의 증거" 5원칙 — v1 D3 착지분) ·
`docs/design/ui/00_index.md:42-43`(전역 UI 불변식 #1 표현≠의미 · #2 반게임화) ·
`src/backend/whymath_backend/harness/growth_evidence_exposure.py`(노출 계약 정본 — `PED-06` 산출) ·
`src/backend/whymath_backend/api/me.py:3062-3069`(원시 표면) · `:3254-3261`(학생 안전 표면) ·
`src/backend/whymath_backend/harness/pilot_kpi_baseline.py`(5 KPI 리포트 — 리텐션 측정 정본) ·
`docs/strategy/risks.md:117-121`(핵심 가정 ① D7 retention) ·
`operations_module_gap_review_r3.md`(동일 문서 3차 재제출 → r3 전환 선례·절 구성 답습) ·
`MEMORY.md` 결정 로그(2026-08-03 v1 · 2026-08-04 r2 · 2026-08-11 본 문서).

---

## §0. 재점검 사유 — 왜 r2를 덮어쓰지 않고 r3를 새로 쓰는가

### ① 동일 문서 3차 재제출임을 수치로 확정한다 (추론 아님)

제출 문서와 r2 §0-①이 기록한 구성이 **세부 개수까지 일치**한다:

| 기능 | 제출 문서 세부 항목 수 | v1·r2 기록 |
|---|---|---|
| 75 레벨 시스템 | 6 | 75:6 |
| 76 경험치(XP) | 12 (획득 8 + 추가기능 4) | 76:12 |
| 77 배지 | 14 (종류 10 + 관리 4) | 77:14 |
| 78 도전과제 | 12 (종류 7 + 보상 5) | 78:12 |
| 79 Streak | 11 (기능 7 + 보상 4) | 79:11 |
| **합계** | **55** | **55** |

연계 구조 7단(`문제풀이→XP→레벨→배지→퀘스트 해금→Streak→추가보상`)도 동일하다. 따라서 이것은
새 요구가 아니라 **3차 재제출**이며, 새 판정이 아니라 **델타**가 답이다.

### ② r2를 in-place 수정하지 않는 이유

r2 §0-②가 확립한 처리를 그대로 승계한다. r2는 이미 완료된 태스크 `PED-08`·`MOB-10`의 `notes`가
**판정 근거로 지목하는 원본**이다(`PED-08.notes`: "`gamification_module_gap_review_r2.md` §6 D5").
완료된 태스크의 근거 문서를 소급 변조하면 "왜 그렇게 결정했는가"의 기록이 사라진다.
따라서 **v1·r2는 그대로 두고, 정정은 이 문서 §정정이 보유**한다.

### ③ 재점검이 필요한 사유 3종

| 사유 | 내용 |
|---|---|
| ⑴ r2 판정표 stale | r2가 등재한 D5·D6이 착지했고, 그 사이 `ARCH-27`·`PED-13`이 게임화 축을 추가로 움직였다 |
| ⑵ r2 **설계 근거 자체의 오탐** | D5가 "원시 표면 유지"를 정당화한 전제가 실측으로 무너졌다(§2 G1). 이것은 판정 갱신이 아니라 **근거 정정**이라 r2 안에서는 처리할 수 없다 |
| ⑶ 이전 2회가 보지 않은 평면 | v1·r2는 **노출**(무엇을 보여줄 것인가)만 봤다. **측정**(반게임화라는 결정이 실제로 작동하는가)은 두 번 다 대조되지 않았다 — §2 G4가 그 평면의 첫 대조다 |

---

## §1. r2 판정의 변경분 — 바뀐 칸만 (나머지는 승계)

r2 §1의 판정표에서 **바뀐 칸은 4개**다.

| 기능 | 세부 | r2 판정 | r3 판정 | 사유 |
|---|---|---|---|---|
| 75 | 단원별 숙련도(`mastery_to_level`) | ⚠️ → D6 | ✅ **해소** | `MOB-10`(`5988c5bd`·#730) 착지. 서버가 `ConceptDiagnosis.mastery_level`(`api/me.py:1236`)을 산출하고 `me_screen`이 렌더. 원시 확률·θ는 미노출 유지 |
| 76 | (대체) 성장 증거 노출 계약 | ⚠️ → D5 | ⚠️ **형태 변경 → D8** | `PED-08`(`71155c98`·#726)이 안전 라우트를 신설해 **미집행**은 해소. 그러나 원시 라우트가 학생 토큰에 열린 채 남아 **우회로 존치**로 형태만 바뀌었다(§2 G1) |
| 77·78 | 배지·퀘스트 전건 | 🚫 | 🚫 **승계 + 기계 강화** | `ARCH-27`이 5원칙 #2(비교 금지)를 서버·클라 양쪽 기계 강제로 전환(비교 파생 어근 10종). 게임화 축 8종은 기존 유지 |
| 79 | (대체) 재진입 경로 | ⚠️ → D7 | 🔴 **7일 무진전 · 고립** | `MOB-11` status `todo`·`updated: 2026-08-04` 그대로. 단 다른 세션 브랜치에 완결 구현 존재(§2 G6) |

**게임화 5모듈 코드 0은 불변**이다. `ARCH-26`(Dart 8 → 현재 **16**정규식 · Python 어열 **21**종 ·
`metric_name` 금지 어근 8종 · `consecutive_active_days` writer 0 동결)에 `ARCH-27`이 비교 파생
축을 더해, 이제 **양방향 변별력 고정핀**(true-positive 13종 · benign 23종 · red 재현 로그)까지
갖췄다. v1 §6 8회차("규정하고 기계화 안 함")는 **이 축에서 완전히 상환됐다**.

---

## §2. 잔여 갭 — 실측

### G1 — 계약의 우회로가 존치한다 (최대 갭 · 안전 축) → D8

`PED-08`이 만든 `GET /v1/me/growth-evidence`(`api/me.py:3255`)는 **잘 만들어졌다**:

| 계약 요소 | 위치 | 실측 |
|---|---|---|
| 계약 경유 강제 | `me.py:3298,3326` | `classify_metric_exposure`(`growth_evidence_exposure.py:124`)·`narrate_calibration_brier`(`:90`)만 경유 |
| 내부 전용 2종 | `me.py:3213-3214` | `diagnosis_agreement_rate`·`tokens_per_turn`이 **스키마에 필드 부재**(런타임 필터 아님) |
| 낙인 라벨 | `me.py:3221-3242` | 계약 원문 `suppressed_reason`이 verdict 코드명을 리터럴로 포함하므로 **서빙 층 소유 문장으로 치환**. `api/`·`schema/` 전체에서 `GAMING_SUSPECT` 히트 0 |
| Brier | `me.py:3155-3168` | 하위 필드가 `narrative` 단 1개 — 원 스칼라 구조적 배제 |
| 도달 관측 | `me.py:3287` | 원시 표면과 **별도 슬롯**(`_growth_evidence_state.py:31`) |
| 거버넌스 | `tests/backend/api/test_me_growth_evidence.py` 8클래스 | OpenAPI `properties` 수준 구조 증명(`:352-365`) 포함 |

**그런데 원시 표면이 학생에게 열린 채 그대로 있다.** 두 라우트의 인증 의존성이 **문자 그대로
같다**:

| | 원시 표면 | 학생 안전 표면 |
|---|---|---|
| 라우트 | `api/me.py:3063` `/harness-metrics` | `api/me.py:3255` `/growth-evidence` |
| 게이트 | `api/me.py:3069` `user: ConsentedUser` | `api/me.py:3261` `user: ConsentedUser` |
| 응답 | `SurrogateMetrics` 원시 **16 Metric + R15 verdict** | 계약 경유 9지표 + Brier 서술 |
| 학생에게 나가는 금지 항목 | `diagnosis_agreement_rate` · `tokens_per_turn` · `gaming_suspect` | 0 |

**r2 D5가 원시 표면을 동결한 근거는 오탐이었다.** r2 §6 D5는 이렇게 적었다 —
"`/harness-metrics`는 ops·리포트가 원시값으로 소비하는 표면이라 응답을 축소하면 그 경로가
깨진다". 실측하면 **ops 2종은 HTTP를 타지 않는다**:

- `harness/surrogate_baseline_report.py:314` — `await compute_wh1_surrogate_metrics(...)` 직접 호출
- `harness/pilot_kpi_baseline.py:809` — 동일

그리고 라우트 자신의 주석이 이를 확인해 준다(`api/me.py:3060-3061`): "코호트 전체 집계
(`user_id=None`)는 ops/스크립트가 **직접 호출** — 이 엔드포인트는 *본인 집계 신호만* 노출".
Flutter 호출도 0건(`src/mobile/lib/` 전수 `harness` grep 0). 즉 **이 라우트의 HTTP 소비자는
0건**이고, 유일하게 호출할 수 있는 주체는 **계약이 보호하려던 그 학생**이다.

**세 슬라이스가 각각 인지하고 각각 회피했다** — 이것이 이 갭의 성격이다:

| 슬라이스 | 날짜 | 인지 내용 | 처리 |
|---|---|---|---|
| `PED-08` | 08-07 | acceptance ⑩ "범위 밖 동결 — `/harness-metrics` 응답 변경(원시 표면 유지)" | 신 라우트 신설로 **우회** |
| `S4-19` | 08-10 | `wh1_evaluation.py:1839` "`harness-metrics`가 `response_model=SurrogateMetrics`로 **전 필드를 학생 토큰에 자동 서빙**하므로(2026-08-10 실측)" | 자기 파생 지표를 거기 **안 넣는 것**으로 대응 |
| `PED-15` | 08-10 | 도달 감사 중 라우트 소비 구조 확인 | 잔여만 기록 |

계약 모듈의 자기 선언(`growth_evidence_exposure.py:131`: "이 함수가 **유일한 노출 판정 경로**가
되게 한다")은 **여전히 거짓**이다. r2에서는 "계약을 아무도 안 지나감"이었고, r3에서는
"계약을 지나는 길이 생겼는데 **지나지 않는 길도 그대로 있음**"이다.

### G2 — 안전 라우트에 소비자 0 · 정직한 잔여가 추적을 잃었다 → D10

`/v1/me/growth-evidence`를 부르는 곳이 학생 클라이언트에 **0건**이다
(`src/mobile/lib/` 전수 `growth` grep 0 · `test/`도 0). 클라가 호출하는 `/v1/me/*`는
`problems_api.dart`의 4개뿐(`next-problem` · `problems/{id}` · `diagnosis/concepts` ·
`weak-concepts/{id}/learning-path`).

`OPS-22` 감사기가 이를 발견해 `PED-15`가 섰고, **done으로 닫혔다**. 닫힌 방식이 문제다 —
`PED-15`의 `acceptance`는 **빈 배열**이고, artifacts에 이렇게 적혀 있다:

> "…**정직한 잔여**: 이 엔드포인트를 소비하는 모바일 클라이언트는 여전히 0건(성장 증거 화면
> 없음) — 도달 증명이지 학생 화면 배선이 아니다."

정확한 자인이다. 그런데 **그 잔여를 잇는 후속 태스크가 0건**이다. 잔여는 문서에만 살아 있고
`backlog.py next`의 계산에는 존재하지 않는다. **정직한 기록이 추적을 대신했다.**

결과: `PED-06`(관측) → `PED-08`(서빙) → `PED-15`(도달 증명)로 3슬라이스가 진행됐고,
**학생은 여전히 성장의 증거를 한 번도 본 적이 없다**. 남은 것은 위젯 한 겹이다.

### G3 — 계약↔서빙 스키마가 양방향으로 드리프트했고, 게이트가 동어반복이다 → D9

계약 표(`_STATIC_TIER`, `growth_evidence_exposure.py:65-83`)와 서빙 스키마
(`GrowthEvidenceResponse`, `api/me.py:3170-3219`)가 **양쪽으로 어긋난다**:

| 방향 | 대상 | 실측 |
|---|---|---|
| 계약 → 서빙 누락 | `gap_recovery_leadtime_days`(⑯·`PED-13`) | `_STATIC_TIER:78`이 **`STUDENT_VISIBLE`로 판정**했는데 `GrowthEvidenceResponse`에 필드가 **없다**(`api/me.py` 전체 히트 0). 보여도 된다고 판정된 지표가 유일한 노출 표면에서 빠졌다 |
| 서빙 → 계약 누락 | `strategy_diversity`·`strategy_repeat_rate`·`client_state_mismatch_rate`(`wh1_evaluation.py:409,418,427`) | `_STATIC_TIER`에 **아예 없다**. `classify_metric_exposure`의 루프가 `_STATIC_TIER.items()`만 순회하므로 이 3종은 **판정 대상 밖**인데 `/harness-metrics`로는 나간다 |

**거버넌스가 이를 못 잡는 이유**: `tests/backend/api/test_me_growth_evidence.py:52`가
`_DECLARED_FIELDS = set(GrowthEvidenceResponse.model_fields)` — **검증 대상 모델 자기 자신에서
기대값을 파생**한다. 모델이 무엇이든 항상 자기와 같으므로 통과한다. 계약 표와 대조하는 assert가
없다. 이것은 CLAUDE.md "**변별력 없는 검증 스텝 금지**"의 교과서적 사례다 — 성공/실패 양쪽에서
같은 값을 내는 검사다.

### G4 — 반게임화라는 결정의 효능을 측정할 경로가 죽어 있다 (신규 평면) → D11

v1·r2는 **노출**만 봤다. 이번에 처음 대조하는 평면은 **측정**이다: 게임화를 *쓰지 않기로 한*
결정이 실제로 작동하는지 우리는 아는가?

전략 정본은 이 질문을 최우선으로 못 박는다:

| 문서 | 내용 |
|---|---|
| `docs/strategy/risks.md:119` | 핵심 가정 ① 검증 지표 = **D7 retention ≥ 30%** (β 사용자 기준) |
| `docs/strategy/market_analysis.md:121` | "**가장 먼저 검증해야 할 가설** = D7 retention" |
| `docs/strategy/business_plan_master_v1.md:95` | Phase 1 종료 게이트 "D7 재방문율 ≥ 30%" |
| `docs/strategy/execution_bridge_2026-07.md:64` | 동일 게이트 |

유일한 측정 경로는 `harness/pilot_kpi_baseline.py`의 **KPI2 리텐션**
(`compute_retention`, `:166`)이다. 그 입력이 문제다:

```
pilot_kpi_baseline.py:825 →  compute_retention([(row[0], row[1]) for row in session_rows])
                             ↑ session_rows = select(LearningSession.user_id, LearningSession.started_at)
```

**`LearningSession`은 `src/` 전체에서 단 한 번도 생성되지 않는다**(생성자 호출 0건 — 테스트에서만
11건). 그리고 이것은 사고가 아니라 결정이다 — `S3-16` acceptance ③이 "`learning_session` 행
writer는 **미신설을 결정으로 명시**(단일 스칼라가 정본 5분류와 축 불일치)"라고 못 박았다.

즉 **회사의 최우선 검증 가설을 재는 계기가 영구히 0을 가리킨다.** 더 나쁜 것은 그 0이 어떻게
표기되는가다 — `compute_retention` docstring(`:183`):

> "표본 정직성(중요): 사용자 0명일 때만 `NO_DATA`다(**genuine 부재**)."

v1 §3 D1-③이 **반드시 분리하라고 못 박은 3상태**(`미도달` / `무데이터` / **`구조적 불가`**)가
여기엔 적용되지 않았다. `PED-06`은 그 3상태를 `surrogate_baseline_report`에만 이식했고, 정작
`LearningSession`을 읽는 **다른 리포트**는 그대로 남았다. 결과적으로 이 리포트는
"생산자 자체가 없음"을 "**사용자가 없어서 데이터가 없음**"으로 말한다 — v1이 "다음 세션이 writer를
만들려 든다"며 경계한 바로 그 위장이다.

**대체 소스가 이미 있다.** `compute_retention`은 `Sequence[tuple[UUID | None, datetime | None]]`을
받는 **순수함수**이고, 호출부의 조회 소스만 바꾸면 된다:

| 후보 | 실 writer | 컬럼 |
|---|---|---|
| `LearningSession` | **0** (영구 미신설 결정) | `user_id` · `started_at` |
| **`Dialogue`** | **있음** — `api/coach.py:1891-1901`(`session.add(dialogue)`) | `user_id`(`db/models/dialogue.py:75`) · `started_at`(`:87`) |

`Dialogue`는 "한 문제 풀이 중 학생↔AI 대화 1단위"라 **세션과 의미가 다르지만**, 리텐션이 묻는
것은 "다른 날 다시 왔는가"이고 그 질문에는 답할 수 있다. 의미 차이는 지표명·note로 정직하게
표기하면 되며, 이는 없는 값을 지어내는 것이 아니라 **있는 관측을 쓰는 것**이다.

**근거 원칙**: CLAUDE.md "**작동 신호 없는 알고리즘 부착 금지 — '작동한 비율' 원칙**"
(2026-08-03). 알고리즘을 붙였으면 그것이 작동한 비율을 리포트가 말해야 한다. 이 원칙은
**채택한 것**만이 아니라 **채택하지 않기로 한 것**에도 적용된다 — 게임화를 안 쓴 결정의 효능이
측정되지 않으면, "반게임화가 옳았다"는 3차에 걸쳐 반복된 판정이 **검증된 적 없는 신념**으로
남는다.

### G5 — KPI3 정서안전이 이미 만료된 사유로 NO_DATA 고정 → D11에 병합

`pilot_kpi_baseline.py:511` `_tone_safety_no_data()`가 KPI3(정서안전·톤 위반)를 NO_DATA로
고정하는 사유(`:514`): "`l4.tone_filter.filter_tone`은 존재하나 **라이브 경로 미배선**이다".

실측하면 그 전제는 만료됐다:

- `harness/wh1_primary.py:235` — `filtered, report = filter_tone(utterance)` 라이브 호출
- 진입: `api/coach.py:77`(import) → `:1788`(`wh1_primary_enabled` 확인) → `:1619`(`run_wh1_primary_turn`)
- `config.py:168` — `wh1_primary_enabled: bool = Field(default=True)` (2026-07-20 GA)

5원칙 #5("정서 신호는 내부 결정 입력으로만")의 **관측**이 이미 해소된 사유로 꺼져 있다.
톤 위반은 게임화의 반대편 — 정서 안전 축의 유일한 상시 계측이므로, 이 stale은 §정정이 아니라
**설계 대상**이다.

### G6 — 기능 79(복귀 지원)는 7일 무진전이나, 구현은 고립돼 있다 → D12

`MOB-11`의 좌표가 **r2 시점 그대로 미변경**이다:

| 점검 | 실측 |
|---|---|
| `initialLocation` | `core/router.dart:103` → 무조건 온보딩. 미인증은 매 실행 노출 |
| 온보딩 1회-노출 영속 | 없음. `onboarding_screen.dart:12-14`가 자인. `shared_preferences` pubspec 미선언 |
| `dialogueId` 영속 | 없음. `chat_state.dart:24` 인메모리 |
| `GET /coach/sessions/{id}` | 정의는 `coach_api.dart:80-82`, **lib/ 호출처 0**(테스트 2곳뿐) |
| "이어하기" 류 UI 문자열 | **0건** |

그런데 **구현은 존재한다** — 다른 세션 브랜치 `claude/whymath-issues-review-k20m0w`의
`4cb8d9d3`(2026-08-09, "fix(MOB-11): 복귀 지원 최소 착지 — 온보딩 1회 노출 영속 + 마지막 대화
이어하기"): 695줄 추가, 신규 파일 4종(`onboarding_store.dart`·`onboarding_seen_controller.dart`·
`dialogue_store.dart` + `flutter_test_config.dart`), **테스트 4파일**. 그 브랜치는 오늘도 활동
중이며(최종 커밋 2026-08-11) main 미병합이다.

**따라서 r3는 이 축을 재설계하지 않는다.** 재구현은 병렬 세션 규약 위반이자 폐기 작업의 반복이다
(2026-07-27 `OPS-07` 735줄 폐기 선례). 필요한 것은 **회수 관리와 만료 지점**이다.

---

## §3. 미채택 11건 — 트리거 3차 재심 (전건 실측)

v1 §2의 의도적 미채택 11건을 **재판정하지 않되**, 각 항목의 미채택 근거가 여전히 유효한지
트리거만 확인한다. **11건 전건 유효** — 뒤집힌 항목 0.

| # | 미채택 항목 | 근거 유효성 (2026-08-11 실측) |
|---|---|---|
| 1 | XP 전체(획득 8 + 부가 4) | 유효. 코드 0 · `metric_name` 금지 어근 `xp` 기계 동결 |
| 2 | 학생 레벨(1~1000)·과목별 레벨 | 유효. 서열 스칼라 금기. `level` 히트는 전부 교육과정 어휘(`ConceptLevel`·`school_level`) |
| 3 | 배지 14종 | 유효. `BadgeEarned\w*` 게이트(Dart·Python 양쪽) |
| 4 | 퀘스트 12종 | 유효. `QuestUnlock\w*`·`DailyQuest` 게이트 |
| 5 | 연속 일수 카운터 | 유효. `consecutive_active_days` writer 0 **기계 동결**(`test_anti_gamification_governance.py:451-461`) |
| 6 | 랭킹·리더보드 | **강화됨**. `ARCH-27`이 비교 파생 어근 10종을 서버·클라 양쪽에 추가(8/9) |
| 7 | 코인·아이템 보상 | 유효. `CoinReward\w*` 게이트. `points` 히트는 문항 배점(`db/models/problem.py:129`) |
| 8 | 카운트다운 | 유효. 코드 0 |
| 9 | 보상형 알림 | **전제 강화**. `MOB-08`이 firebase 2종 제거 — 알림 인프라 자체가 없다 |
| 10 | dead table 소생 | 유효. `S3-16`이 `focus_score`·`engagement_score`·`learning_session` writer **영구 미신설**을 결정으로 명시 |
| 11 | `gamification_level` 확대 | 유효. 코드·DB 좌석 **0건**(문서 5곳에만 존재 — 페이퍼) |

**부수 확인**: 학생 클라이언트에 축하·칭찬·보상 연출 자산이 **0건**이다(`축하`·`잘했`·`훌륭`·
`confetti`·`trophy`·`reward` 등 전수 0 — 매칭되는 8줄은 전부 *금지를 선언한 주석*).
`assets/animations/`는 `.gitkeep` 1파일뿐. 반게임화는 **주석·테스트·디자인 토큰 3중으로 방어**돼
있다. 문제는 방어의 부족이 아니라 **그 반대편의 공백**이다.

---

## §4. 설계 D8~D12 (r2의 D5~D7에 번호 연속)

### D8 — 원시 표면의 학생 토큰 봉인 (G1 · 최대 갭 · `PED-22`)

**핵심 판단**: 계약을 또 만들지 않는다. **계약을 우회하는 길을 닫는 일**이다.

**채택 형태(Kiki 확정)**: 라우트 삭제도 응답 축소도 아닌 **운영자 게이트로 강등**.
근거 — 삭제는 되돌리기 비용이 크고 `/health/ready` 도달 카운터 섹션까지 정리해야 하며,
응답 축소는 우회로 자체를 남겨 "유일 판정 경로" 선언이 계속 거짓이다.

- **①** `GET /v1/me/harness-metrics`의 의존성을 `ConsentedUser` → **운영자 전용**으로 교체.
  `api/_auth.py:124` `RequireContentAdmin`이 선례이나 이 축은 콘텐츠 권한이 아니라 **운영 계측
  권한**이므로, 기존 의존성 재사용 가부·신설 필요 여부는 **구현 태스크가 실측으로 판정**한다
  (권한 의미가 다른 의존성의 임의 재사용 금지).
- **②** 라우트·응답 모델·도달 카운터 섹션은 **무변경** — ops 진단 경로를 보존한다.
- **③** **acceptance는 ①정본화와 ②집행 지점을 별항 분리**(2026-08-04 헌법 별항 — r2 §4-④가
  낳은 규칙). 여기서 집행 지점 = "학생 토큰 호출이 **실제로 403이 되는 라우트가 어디인가**".
- **④** **변별력 3방향 실측** — 학생 토큰 403 · 운영자 토큰 200 · 무인증 401. 세 방향 모두
  실제로 그 코드가 나오는지 확인한다(한 방향만 보면 위장된다).
- **⑤** 기존 통합테스트 3곳(`tests/backend/harness/test_wh1_evaluation_integration.py:361,428,444`)의
  인증 픽스처 갱신이 동반된다. 이 갱신을 **테스트 약화가 아니라 계약 변경**으로 커밋 메시지에
  명시한다(게이트 무력화와 구분되게).
- **⑥** 착지하면 `growth_evidence_exposure.py:131`의 "유일한 노출 판정 경로" 선언이 **처음으로
  참이 된다**. 이 문장을 acceptance의 완료 판정 문구로 쓴다.

**범위 밖 동결**: 응답 모델 변경 · `/growth-evidence` 변경 · 클라 배선(D10 소관) ·
`focus_score`/`engagement_score` 좌석(`S3-16` 소유).

### D9 — 계약↔서빙 대조 게이트 (G3 · `PED-23`)

**핵심 판단**: 새 계약이 아니라 **기존 두 정본이 서로 어긋나지 않게 묶는 핀**이다.

- **①** `_STATIC_TIER`의 `STUDENT_VISIBLE` 집합 ↔ `GrowthEvidenceResponse.model_fields`를
  **양방향 대조**. 기대값을 검증 대상 모델에서 파생하는 현행(`test_me_growth_evidence.py:52`)을
  제거한다 — 동어반복 해소가 이 태스크의 본체다.
- **②** `SurrogateMetrics` 필드 중 `_STATIC_TIER`에 **등재되지 않은 지표**가 있으면 red.
  판정 대상 밖 지표가 조용히 늘어나는 통로를 막는다(현재 3종 실재 — `strategy_diversity` 외).
- **③** **게이트를 먼저 세우고 누락을 상환하는 순서**를 지킨다. `gap_recovery_leadtime_days`
  누락이 이 게이트가 잡는 **첫 red**여야 한다 — 게이트가 처음부터 green이면 변별력이 없다
  (CLAUDE.md "변별력 없는 검증 스텝 금지").
- **④** ②의 상환 방향은 **자동 노출이 아니다**. 미등재 3종은 `_STATIC_TIER`에 **명시적으로
  등재**하되 계층 판정(`INTERNAL_ONLY`일 가능성 포함)은 지표 성격을 보고 정한다 — 게이트를
  green으로 만들려고 학생 노출로 밀지 않는다.

**범위 밖 동결**: 노출 계층 정책 자체의 개정 · 신규 지표 계산 · 클라 렌더.

### D10 — 성장 증거의 학생 화면 착지 (G2 · 5원칙 #1의 최초 실착지 · `MOB-17`)

**핵심 판단**: 서버 신규 계산 0. `PED-15`가 남긴 "정직한 잔여"를 **태스크로 승격**하는 일이다.

- **①** `/me` 탭에 "성장의 증거" 섹션 신설 — `GET /v1/me/growth-evidence`의 **첫 소비자**.
- **②** 클라는 서버가 준 `status`·`value`·`exposable_now`·`suppressed_reason`·`narrative`를
  **그대로 표시만** 한다. 임계값 계산·라벨 판정·서술 생성 금지(전역 UI 불변식 #1).
  `MOB-10`의 `mastery_level` 처리 방식을 답습한다.
- **③** **비교·순위·백분위 파생 0**(5원칙 #2 · `ARCH-27` 게이트가 기계로 막는다) ·
  **원시 확률·θ·Brier 스칼라 0**(5원칙 #1) · **차트 0**(v0 — `fl_chart` 제거 상태 유지,
  `pubspec_dependency_usage_governance_test.dart`의 선언↔사용 동시착지 게이트 준수).
- **④** `NO_DATA`·`exposable_now=False`를 **숨기지 않고 서술로 보인다**. 확신도 수집 UI가 없어
  ⑥ Brier가 "아직 예측 확신도 데이터가 없어요"만 내는 것은 **실패가 아니라 설계 의도**다
  (r2 §3-② 승계).
- **⑤** `anti_gamification_governance_test.dart`(현재 16정규식) 통과 필수.
- **⑥** **재확인 지점** — `api/_concept_orchestration.py:86`이 미측정 학생에게 `"초보"`를
  폴백으로 부여하는데(`api/me.py:1239`의 null 폴백과 비대칭), 이 섹션이 학생 대면이므로 구현 시
  그 라벨이 화면에 도달하는지 확인한다(§정정 ⑥).

**범위 밖 동결**: `/harness-metrics` 클라 배선(D8이 봉인) · 보호자 대시보드 · 확신도 수집 UI ·
`problem_screen` 재설계(θ·표준오차 렌더는 별도 슬라이스).

### D11 — 반게임화 효능 측정 복원 (G4 · G5 · `PED-24`)

**핵심 판단**: 신규 테이블 0 · 마이그레이션 0 · 신규 계산 0. **순수함수의 입력만 바꾼다.**

- **①** KPI2 리텐션의 조회 소스를 `LearningSession` → **`Dialogue`**(`user_id`·`started_at`)로
  교체. `compute_retention`(`pilot_kpi_baseline.py:166`)은 **재사용**한다.
- **②** 지표 의미 변화를 **정직하게 표기**한다 — `Dialogue`는 "문제 1개 풀이 중의 대화 1단위"라
  "앱 세션"과 다르다. 지표명·note에 무엇을 세는지 명시하고, 무엇을 세지 *못하는지*도 쓴다
  (대화를 열지 않은 방문은 안 잡힌다).
- **③** **3상태 표기 이식** — `미도달` / `무데이터` / **`구조적 불가`**. `PED-06`이
  `surrogate_baseline_report`에 만든 것을 재사용한다. `LearningSession` 기반으로 남는 지표
  (③ 세션 완주율 등)는 `구조적 불가`로 **분리 표기**하고 `genuine 부재`와 섞지 않는다.
- **④** KPI3 stale 해제 — `_tone_safety_no_data()`(`:511`)의 "라이브 경로 미배선" 근거가
  만료됐음을 실측 확인하고(`wh1_primary.py:235` · `config.py:168`), 관측 가능하면 NO_DATA를 푼다.
  **관측이 실제로 값을 내는지 확인한 뒤** 푼다(CLAUDE.md "검증 없는 실행 안내 금지"의 리포트 축).
- **⑤** **학생 노출 0** — 이 축은 **집계·운영 전용**이다. 리텐션·복귀 수치를 학생 화면에 두지
  않는다(5원칙 #4 · 기능 79 미채택 11건 승계). 연속 일수·달력·목표 설정·복구권을 만들지 않는다.
  "돌아온 학생을 세는 것"과 "돌아오라고 압박하는 것"은 다르다 — 전자는 운영의 눈이고 후자는
  금기다.
- **⑥** **변별력 양방향** — `Dialogue` 행을 서로 다른 날짜로 2건 주입하면 `returning_user_rate`가
  실제로 움직이고, 되돌리면 다시 NO_DATA로 돌아오는지 실측한다.

**범위 밖 동결**: `LearningSession` writer 신설(`S3-16`이 영구 미신설로 결정 — **되살리지 않는다**) ·
학생 대면 리텐션 노출 · 코호트 분석 인프라 · `focus_score`/`engagement_score` 좌석.

### D12 — 추적 위생 (신규 태스크 없음 · 기존 태스크 정정)

- **①** `MOB-11` notes의 분모 정정 — "백로그 176건 전수" → **255건**(비-done 69건). 전수 재확인
  결과 streak·리텐션·복귀·재진입·대시보드 축의 **열린 태스크는 여전히 `MOB-11` 1건뿐**이라는
  판정 자체는 유효하다.
- **②** `MOB-11`에 **미병합 구현 존재**를 notes로 기입 — 브랜치 `claude/whymath-issues-review-k20m0w`,
  커밋 `4cb8d9d3`(2026-08-09). **재구현 금지·회수 대상**임을 명시하고 **만료/재확인 지점**을 붙인다
  (CLAUDE.md "만료 없는 유예·제외 금지" — 그 브랜치가 병합되면 status를 done으로, 병합 없이
  방치되면 회수 태스크로).
- **③** `PED-08` artifacts 해시 정정 — `981d2b46`은 저장소에 **존재하지 않는** 프리-스쿼시 해시
  (`git cat-file -t` 실패 · `--all` 스캔에도 없음). 실제 착지 커밋은 `71155c98`(#726).

---

## §5. 정직한 공백 — 지금 하지 않는 것 (v1·r2 승계 + 갱신)

1. **5원칙 원칙 3(보정)이 구조적으로 미착지 — 3차 연속**. 확신도 수집 UI가 `src/mobile/lib/`에
   **0건**이라 ⑥ Brier는 영구 `NO_DATA`다. r2 §5-②가 정한 발화조건("`REC-01` 도달 리포트에서
   attempt 제출이 실제로 관측된 뒤")은 `REC-01`이 done이 됐으므로 **문면상 충족처럼 보이나
   실질 미충족**이다 — 클라의 attempt 제출 경로가 여전히 0이기 때문이다
   (`interaction_logger.dart:50`의 `POST /v1/interactions`는 시각화 조작 전용).
   → **발화조건을 "`REC-01` done"에서 "클라 attempt 제출 경로 실재"로 정밀화**한다(§6).
2. **보호자 대시보드 / `GUARDIAN_SUMMARY` 멤버십 0** — 승계(r2 §3-①, 과공학 방지).
   D10이 착지해도 이 계층은 벌리지 않는다.
3. **PRD 동기 섹션 신설** — **3차 연속 공백**. `prd_v1.2.md` 전문에 `동기|motivat|몰입|지속`
   히트 0. 다만 리텐션 **목표치**는 전략 문서 4곳에 있다 → §6 에스컬레이션으로 올리고
   **새 산문을 더하지 않는다**(D11이 측정을, `MOB-11`이 실행을 가진다).
4. **`gamification_level` 코드 실체화** — 코드·DB 좌석 0건(문서 5곳에만 존재). 자유학기제 모드가
   L6 게이팅에 실배선될 때로 승계. 그 시점에 `ARCH-26`·`ARCH-27` 게이트 오탐 회피 경로를 함께
   설계해야 한다는 조건도 승계.
5. **한국어 압박 문구는 기계 강제 불가** — `anti_gamification_governance_test.dart`의 16정규식은
   **영문 식별자 축**이라 "며칠 만이에요" 류 한국어 카피·이모지·시각 연출을 잡지 못한다.
   `MOB-11` acceptance ④는 **사람 검수 축**임을 명시한다 — 측정되지 않은 기계 게이트를 인간 검수
   대체로 선언하지 않는다(`superhuman_verification_standard.md`).
6. **`S3-16`의 미이행 약속** — acceptance ③이 약속한 `focus_score`·`engagement_score`
   **writer 0 동결 테스트가 저장소에 없다**(`consecutive_active_days`에는 있다). 이 좌석의
   소유자는 `S3-16`이므로 r3는 **소유권을 가져오지 않고** §정정 ⑤로 기록만 한다.

---

## §6. 발화 트리거 (기계로 관측 가능한 형태)

| 유보 항목 | 발화 트리거 (r3 갱신) |
|---|---|
| 확신도 수집 UI(원칙 3) | **정밀화** — `REC-01` done이 아니라 **`src/mobile/lib/`에서 attempt 제출 POST 경로가 1건 이상 실재**할 때. 현재 0(`POST /v1/interactions`는 시각화 조작 전용) |
| 보호자 대시보드·`GUARDIAN_SUMMARY` | 불변 — 보호자 리포트 표면이 별도 태스크로 착수될 때 |
| 복귀 유도 알림 | 불변(후퇴 유지) — `MOB-08`로 firebase 제거. FCM 실기능 태스크가 서고 pubspec 게이트를 통과해 재도입될 때 |
| `gamification_level` 실체화 | 불변 — 자유학기제 모드가 L6 게이팅에 실배선될 때 |
| `MOB-11` 고립 회수 | **신규** — 브랜치 `claude/whymath-issues-review-k20m0w`가 main에 병합되면 status를 done으로 정정. 병합 없이 **2026-08-18까지 경과**하면 회수 태스크 등재(`MOB-11.notes`에 만료 지점 기입 완료) |
| PRD 동기 섹션 | **에스컬레이션으로 전환**(§7) — 문서 신설이 아니라 소유자 배정 문제 |

---

## §7. 에스컬레이션 — "게이트는 있는데 소유자가 없다" (신규 태스크 없음)

**D7 retention ≥ 30%**는 전략 문서 4곳에서 Phase 1 종료 게이트이자 최우선 검증 가설이다.
그런데:

- 그것을 **재는 계기**는 죽어 있었다(G4 — D11이 상환).
- 그것을 **움직이는 열린 태스크**는 백로그 255건(비-done 69건) 전수에서 **`MOB-11` 1건뿐**이고,
  priority 3에 7일째 todo이며, 구현은 미병합 브랜치에 고립돼 있다(G6).
- 그것을 **설계하는 정본**은 `02_student_ui_master_plan.md:87-95`의 5원칙 한 곳뿐이고,
  PRD·ROADMAP에는 동기 섹션이 0건이다(§5-③).

즉 **회사가 가장 먼저 검증하겠다고 선언한 가설에 소유자가 없다.** 이것은 태스크 하나로 풀리는
문제가 아니라 우선순위 배정 문제이므로 **Kiki 판단으로 올린다**. r3가 할 수 있는 것은 계기를
살리는 것(D11)까지이고, `MOB-11`의 priority 상향·병합 결정은 사람 소유다.

---

## §8. 반복 실수 — **11회차** (재발방지 등재)

v1이 8회차까지, r2가 9회차, `operations_module_gap_review_r3.md`가 10회차를 사용했다.

| 회차 | 사례 | 형태 |
|---|---|---|
| 1~6 | (v1 승계) | 배선 부재 |
| 7 | 성장 지표를 클라가 호출하기로 결정한 적 없음 | 결정 부재 |
| 8 | 반게임화 불변식 20+ 인용 · 집행 테스트 0 | 규정하고 기계화 안 함 |
| 9 | 진단이 클라 메모리까지 왔는데 위젯이 안 읽음 | 도달했는데 렌더 0 |
| 10 | (운영 r3 소유) | — |
| **11** | 세 슬라이스가 원시 표면 누수를 **각각 인지하고 각각 회피**(G1) · `PED-15`가 잔여를 정직히 적고 **후속 없이 done**(G2) | **인지하고 우회 — 자인이 추적을 대신함** |

**앞 회차와의 차이**: 1~9회차는 *몰라서* 안 한 것이다. 11회차는 **알고도 옆으로 지나간** 것이다.
`S4-19`는 문제를 정확히 서술하고(`wh1_evaluation.py:1839`) 자기 지표를 그 표면에 넣지 않는
것으로 **자기 자신만 보호**했다. `PED-15`는 잔여를 문장으로 남겼지만 태스크로 남기지 않았다.

**왜 통과했는가**: 정직한 자인 주석은 **검토자에게 안전 신호로 읽힌다**. "우리는 이 문제를 안다"는
문장이 있으면 그 문제가 관리되고 있다고 느껴진다. 그러나 자인은 관리가 아니다 —
`backlog.py next`는 주석을 읽지 않는다.

**재발방지(규칙 후보)**: 태스크가 "정직한 잔여"를 artifacts·notes에 적고 닫을 때,
**그 잔여는 반드시 후속 태스크 ID를 동반해야 한다**. 후속 ID가 없으면 닫지 않는다.
이는 CLAUDE.md **"만료 없는 유예·제외 금지"**(2026-08-03)의 자매 규칙이다 — 그 규칙이
*유예*에 만료를 요구한다면, 이 규칙은 *잔여*에 **후계자**를 요구한다.
채택 여부는 Kiki 판단(§실행 3항).

---

## §정정 — stale 정본 (v1·r2는 수정하지 않고 여기 기록)

| # | 기존 기술 | r3 실측 | 처리 |
|---|---|---|---|
| ① | r2 §6 D5: "`/harness-metrics`는 **ops·리포트가 원시값으로 소비**하는 표면이라 응답을 축소하면 그 경로가 깨진다" | **오탐**. ops 2종은 `compute_wh1_surrogate_metrics`를 파이썬으로 직접 호출(`surrogate_baseline_report.py:314`·`pilot_kpi_baseline.py:809`). HTTP 소비자 0건 | D8이 상환 — 동결 근거가 사라졌으므로 봉인 가능 |
| ② | r2·`MOB-11` notes의 5원칙 원칙 4 앵커 `02_student_ui_master_plan.md:92-94` | 실제 **`:93-94`**(5원칙 전체는 `:87-95`) | 본 문서는 정정된 앵커 사용 |
| ③ | r2가 "D3 착지 확인"으로 인용한 `02_student_ui_master_plan.md` | r2 작성 시점(8/4) **main 미존재** — `d0639c78`(8/6·#668)이 부수적으로 실어 왔다. 내용 개정은 0이라 **판정은 유효** | 기록만 |
| ④ | `MOB-10` acceptance ②의 전제("진단 결과 타일이 `'준비 중'` placeholder") | 커밋 시점에 **이미 stale** — `PATH-05`(#728)가 개념명+코칭 문구를 선착지시켰고 MOB-10은 숙달 라벨만 추가 | 기록만(결과는 동일) |
| ⑤ | `S3-16` acceptance ③ "`focus_score`·`engagement_score` NULL 유지 **동결 테스트**" | 저장소에 **없다**. `consecutive_active_days`에는 있는 writer-freeze 게이트가 이 둘에는 부재 | 소유자 `S3-16` — r3는 기록만(중복 소유 회피) |
| ⑥ | `api/_concept_orchestration.py:86` `mastery_to_level` 폴백 | 미측정 학생에게 `"초보"` 부여 — `api/me.py:1239`의 null 폴백과 **비대칭**(미측정을 최하위 라벨로 표시 = 서열 신호 리스크) | D10 acceptance ⑥의 재확인 지점 |
| ⑦ | `PED-08` artifacts `981d2b46` | 저장소에 **존재하지 않는 해시**(프리-스쿼시). 실제 `71155c98`(#726) | D12-③이 정정 |
| ⑧ | `MOB-11` notes "백로그 **176건** 전수" | 현재 **255건**(비-done 69). 판정("관련 열린 태스크 1건뿐")은 유효 | D12-①이 정정 |

**오탐 방지 — 정정 대상이 아닌 것**: v1 §0-②의 "게임화 5모듈 코드 0"은 **여전히 정확**하며
이제 기계 게이트 2종(`ARCH-26`·`ARCH-27`)이 지킨다. v1 §2 미채택 11건도 §3에서 전건 유효 확인.

---

## §9. 실행 — 백로그 등재 · 중복 회피 대장

### 신규 등재 (전건 `backlog.py add` CLI 경유 — ID 손편집 0)

| 설계 | 태스크 | stage | priority |
|---|---|---|---|
| D8 | `PED-22-harness-metrics-operator-gate` | S3 | 2 |
| D9 | `PED-23-exposure-contract-serving-crosswalk-gate` | S3 | 3 |
| D10 | `MOB-17-growth-evidence-render` | S3 | 2 |
| D11 | `PED-24-antigamification-efficacy-measurement` | S3 | 3 |

**번호 배정은 CLI가 했다** — 최초 시도 `PED-17`·`MOB-16`은 CLI가 **원격 브랜치 충돌로 거부**했다
(`PED-17-study-generate-fallback-decision` @ `claude/whymath-ai-integration-check-5qqcp4` ·
`MOB-16-coaching-time-goal-axis-reach` @ `claude/whymath-ai-tutor-design-uq92g2`). 두 브랜치 모두
main 미병합이라 **로컬 파일 목록만 봤으면 보이지 않았을 인플라이트 번호**다. 거부를 우회하지 않고
CLI가 제안한 번호(`PED-22`·`MOB-17`)를 그대로 썼다(HARN-10 — 2026-07-18/25 `ARCH-13`,
2026-07-29 `OPS-15` 중복 배정 선례가 낳은 규칙이 실제로 작동한 사례).

### 기존 태스크 수정 (CLI에 notes·artifacts 정정 서브커맨드가 없어 YAML 직접 편집 — **상태 변경 아님**)

- `MOB-11` — 앵커 정정(`:92-94`→`:93-94`) · 분모 정정(176→255) · **미병합 구현 사실과
  재구현 금지** · **만료 지점 2026-08-18**(D12-①②)
- `PED-08` — artifacts 해시 정정 `981d2b46`(무효) → `71155c98`(#726)(D12-③)

### 중복 등재 금지 대장 (등재 *전* 열린 태스크 69건 전수 확인)

| 인접 소유자 | 소유 범위 | D8~D11과의 경계 |
|---|---|---|
| `S3-16`(done) | `focus_score`·`engagement_score`·`learning_session` writer 미신설 결정 | D11은 **writer를 만들지 않는다** — 읽는 소스를 바꿀 뿐 |
| `PATH-10`(todo) | 학습 경로 정렬 근거 렌더 + 그 섹션의 반게임화 동결 | D10은 **"성장의 증거" 섹션** — 학습 경로 타일과 다른 섹션 |
| `PED-14`(todo) | ⑨ `mastery_gain_rate`의 시간 정규화(분모) | D9·D10은 지표 **계산에 손대지 않는다** |
| `ASM-02`·`ASM-07`(done) | 등급·백분위·합격예측의 학생 영구 비노출 + 구조적 배제 | D8·D9는 **대리지표 11~16종**의 노출 판정 — 평가 예측 축과 무관 |
| `S3-32`(todo) | 학습 루프 닫힘(서버검증→돌아보기→attempt 적재) | §5-①의 확신도 UI 발화조건 **상류**. D10은 확신도 수집을 만들지 않는다 |
| `MOB-11`(todo·고립) | 복귀 지원(온보딩 영속·이어하기) | D8~D11 어느 것도 **재진입 축을 건드리지 않는다** |
| `OPS-22`/`PED-15`(done) | 선언≠배선 감사기 · `/growth-evidence` 도달 증명 | D10은 **학생 화면 배선** — `PED-15`가 명시적으로 범위 밖으로 남긴 잔여 |

---

## 부록 — 실측 근거 (2026-08-11 · 브랜치 `claude/whymath-gamification-design-8ap436` · HEAD `d088ae77`)

**G1 우회로 존치**
- `api/me.py:3063`(`/harness-metrics`) · `:3069`(`ConsentedUser`) · `:3060-3061`(ops는 직접 호출 주석)
- `api/me.py:3255`(`/growth-evidence`) · `:3261`(`ConsentedUser` — **동일 게이트**) ·
  `:3170-3219`(응답 스키마) · `:3213-3214`(내부 전용 2종 필드 부재) · `:3221-3242`(낙인 라벨 치환)
- `harness/growth_evidence_exposure.py:131`("유일한 노출 판정 경로") · `:124`(`classify_metric_exposure`) ·
  `:90`(`narrate_calibration_brier`) · `:65-83`(`_STATIC_TIER` 13지표)
- `harness/surrogate_baseline_report.py:314` · `harness/pilot_kpi_baseline.py:809`(둘 다 파이썬 직접 호출)
- `harness/wh1_evaluation.py:1839`(S4-19 자인 — "전 필드를 학생 토큰에 자동 서빙")
- `src/mobile/lib/` 전수 `harness`·`growth` grep **0건**
- `backlog/tasks/PED-08-....yaml` acceptance ⑩("원시 표면 유지")

**G2 소비자 0 · 추적 상실**
- `backlog/tasks/PED-15-growth-evidence-endpoint-client-wiring.yaml` — `acceptance: []` ·
  artifacts "정직한 잔여: …모바일 클라이언트는 여전히 0건"
- `src/mobile/lib/features/problems/data/problems_api.dart:30,44,54,72`(클라 `/v1/me/*` 4종 전부)

**G3 계약↔서빙 드리프트**
- `harness/growth_evidence_exposure.py:78`(`gap_recovery_leadtime_days` = `STUDENT_VISIBLE`) —
  `api/me.py` 전체 히트 0
- `harness/wh1_evaluation.py:409,418,427`(`_STATIC_TIER` 미등재 3종)
- `tests/backend/api/test_me_growth_evidence.py:52`(`_DECLARED_FIELDS`가 모델 자기 파생 — 동어반복)

**G4 측정 경로 사망**
- `harness/pilot_kpi_baseline.py:166`(`compute_retention` 순수함수) · `:183`("genuine 부재") ·
  `:825`(`LearningSession` 조회) · `:809`
- `LearningSession(` 생성자 호출 — `src/` **0건** / `tests/` 11건
- `backlog/tasks/S3-16-behavior-telemetry-writers.yaml` acceptance ③(writer 영구 미신설 결정)
- `db/models/dialogue.py:75`(`user_id`) · `:87`(`started_at`) · `api/coach.py:1891-1901`(실 writer)
- `docs/strategy/risks.md:117-121` · `market_analysis.md:121` ·
  `business_plan_master_v1.md:95` · `execution_bridge_2026-07.md:64`

**G5 KPI3 stale**
- `harness/pilot_kpi_baseline.py:511`(`_tone_safety_no_data`) · `:514`("라이브 경로 미배선")
- `harness/wh1_primary.py:235`(`filter_tone` 라이브 호출) · `api/coach.py:1619,1788` ·
  `config.py:168`(`wh1_primary_enabled` default True · 2026-07-20 GA)

**G6 복귀 지원 고립**
- `core/router.dart:103` · `onboarding_screen.dart:12-14` · `chat_state.dart:24` ·
  `coach_api.dart:80-82`(lib 호출처 0) · `pubspec.yaml`에 `shared_preferences` 미선언
- 미병합 구현: 브랜치 `claude/whymath-issues-review-k20m0w` · 커밋 `4cb8d9d3`(2026-08-09) ·
  16파일 +695/-32 · 테스트 4파일 · `git merge-base --is-ancestor 4cb8d9d3 HEAD` → **NO**

**§3 미채택 재심**
- `tests/backend/l1/test_anti_gamification_governance.py`(금지 어열 21종 · `metric_name` 어근 8종 ·
  `:451-461` `consecutive_active_days` writer 0 동결 · `:249-272` benign 23 · `:279-294` TP 13)
- `src/mobile/test/governance/anti_gamification_governance_test.dart`(16정규식 · 스캔 하한 30 ·
  현재 lib `.dart` 57파일) — 최종 변경 `e8717347`(ARCH-27 · 2026-08-09)
- 축하·보상 연출 자산 lib/ 전수 **0건**(매칭 8줄은 전부 금지 선언 주석) · `assets/animations/` = `.gitkeep`

**수치 재계수 (AST 파싱으로 독립 확인 — 눈으로 센 값이 아니다)**
- `SurrogateMetrics` 총 36필드 중 **`Metric`형 16** + `help_reduction_validated: HelpReductionValidation`(R15 결합 판정) 1
- `GrowthEvidenceResponse` 총 14필드 중 지표 뷰 10(= `GrowthEvidenceMetricView` 9 + `GrowthEvidenceBrierView` 1).
  `diagnosis_agreement_rate`·`tokens_per_turn` **부재 확인**
- `_STATIC_TIER` 13종(`STUDENT_VISIBLE` 11 · `INTERNAL_ONLY` 2)
- **계약→서빙 누락 = `gap_recovery_leadtime_days` 정확히 1종**
- **`_STATIC_TIER` 미등재 Metric = `strategy_diversity`·`strategy_repeat_rate`·`client_state_mismatch_rate` 정확히 3종**

**착지 확인**
- `PED-08` = `71155c98`(#726) · `MOB-10` = `5988c5bd`(#730) · `ARCH-27` = `e8717347`(#736) ·
  `MOB-11` = **미착지**(todo · `updated: 2026-08-04`)
- 백로그 총 **255건**(done 186 · todo 63 · blocked 5 · in_progress 1)
