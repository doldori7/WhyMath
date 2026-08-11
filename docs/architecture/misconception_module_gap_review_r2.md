# 오개념(Misconception) 모듈 — 외부 EOS 틀 **2차 대조(R2)** 갭 점검 (2026-08-11)

> **범위**: 외부 참고 문서 『03. 오개념(Misconception)』(0단계: 기능 11 오개념 DB · 12 오개념
> 자동 진단 · 13 맞춤 교정 전략 / 확장: 14 지식그래프 · 15 원인분석 · 16 예측 · 17 버전관리 ·
> 18 연구플랫폼 · 19 자동발견 — **WhyMath 전용이 아닌 일반적 EOS 틀**, Kiki 제공)의 **재제출**.
> 1차 대조는 `misconception_module_gap_review.md`(2026-08-03 · 시리즈 11번째 자매편 · 태스크
> 6건 등재 · PR #667 머지)로 이미 존재하므로, 이 문서는 **① 1차 판정의 8일 후 재판정 ② 1차가
> 보지 않은 축의 신규 실측**만 담는다. 1차 문서는 **덮어쓰지 않는다**(이력 보존 —
> `problem_bank_gap_review_r2.md`·`gamification_module_gap_review_r2.md` 선례 동형).
> **형식**: 위 두 r2 자매편 답습 — **같은 모듈의 첫 2차 대조**.
> **역할 분리 승계**: 1차가 Kiki 지정으로 세운 "갭점검(판정+근거) / 설계(어떻게 고칠지) 2문서
> 분리"를 그대로 따른다 — 이 문서는 판정만 담고, 해법은 각 행에서
> `04e_misconception_remediation_design.md §9`로 위임한다.
>
> **결론 — 착수 가설이 두 번 뒤집혔다.**
> 1. "오개념 교정은 아직 안 만들어졌다" → **아니다. 1차가 등재한 6건은 전부 구현이 끝났고,
>    단 한 건도 main에 없다**(§0-②). **미병합 고립 4회차**이며, 그중 2건은 두 세션이 각자
>    구현한 **이중 구현**이다.
> 2. "진짜 갭은 교정(13) 축이다"(1차 결론) → **더 큰 갭이 진단(12)의 *입력측*에 있다** —
>    WhyMath의 서명 입력 양식인 **손글씨(OCR) 풀이가 오개념 엔진에 한 건도 기여하지 않는다**
>    (§2 G1). 1차는 백엔드만 봤기 때문에 이 축을 볼 수 없었다.
>
> 신규 갭 6건(G1~G6)을 실측하고, 1차 판정 3칸을 정정하며(§1), 정본 stale 3곳을 기록한다(§5).

관련 정본: `misconception_module_gap_review.md`(1차 대조 — 재논증하지 않고 판정만 갱신) ·
`04e_misconception_remediation_design.md`(자매 설계 — §9가 이 문서의 갭을 받는다) ·
`04c_misconception_seven_stage_separation.md`(7레벨 정본 + §6 갭 장부) ·
`04b_misconception_judge_graduation.md`(judge 졸업) · `04a_wh1_tutoring_harness.md`(WH-1 하네스) ·
`problem_bank_gap_review_r2.md`(r2 포맷·고립 실측 선례) · `backlog/tasks/MISC-0*.yaml` ·
`MEMORY.md` 결정 로그.

---

## §0. 재점검 전제

### ① 동일 문서 재제출임을 항목 수로 확정

| 축 | 첨부 문서 | 1차가 대조한 항목 | 일치 |
|---|---|---|---|
| 0단계 기능 | 11 · 12 · 13 | 11 · 12 · 13 | ✅ |
| 기능 11 관리 항목 | 16종(ID·이름·설명·발생원인·관련개념·선수부족·심각도·빈도·학년·단원·성취기준·대표오답·진단규칙·교정전략·추천콘텐츠·논문·버전) | §1 표 16행 | ✅ |
| 기능 12 진단 방법 | 4종(Rule·패턴매칭·개념그래프·AI추론) | §2 표 4행 + 임베딩 1행 | ✅ |
| 기능 13 전략 | 8종 | §3 표 8행 | ✅ |
| 확장 제안 | 14~19 (6종) | §4(14·15·16) + §5(17·18·19) | ✅ |

**신규 항목 0건.** 따라서 1차의 논증을 반복하지 않고 **판정만 갱신**한다.

### ② 1차 등재 6건의 실제 상태 — main 착지 **0건** · 고립 **4회차** · **이중 구현 2건**

1차 문서는 판정과 함께 `MISC-01`~`MISC-06`을 등재했다. 8일 뒤 main의 백로그는 **6건 전부
`todo`**다. 그러나 이는 "아직 안 만든 것"이 아니다 — `git log --all` + 브랜치별 파일 실측 결과
**6건 전부 구현이 끝나 있고, 세 개의 미병합 브랜치에 흩어져 있다.**

| 태스크 | main 백로그 | 실제 구현 커밋 | 브랜치 | 열린 PR |
|---|---|---|---|---|
| MISC-01 시각화 결선 | todo | `0be94d00` **/ `c97aea73`** | `human-bottleneck-tasks-6dszy0` / `subject-problems-theory-check-7n9n72` | **#739** |
| MISC-02 선수복습 연동 | todo | `43e5d6d8` | `7n9n72` | **없음** |
| MISC-03 유사문제 서빙 | todo | `7096d16c` | `6dszy0` | **#739** |
| MISC-04 관계셋 격리 | todo | `7f9c5467` **/ `fbaaa990`** | `6dszy0` / `misc-04-misconception-relation-recovery` | **#739 / #744** |
| MISC-05 slip 관측 | todo | `5d544abc` | `7n9n72` | **없음** |
| MISC-06 재발신호 | todo | `caf4520a` | `7n9n72` | **없음** |
| (인접) ASM-06 오답→오개념 | todo | `087859bd` | `7n9n72` | **없음** |

**MISC-01·MISC-04는 두 세션이 각자 구현했다**(굵게 표기한 2커밋). MISC-04 쪽은 두 번째
브랜치가 스스로 *"#739가 빠뜨린 완료분"*이라 제목에 적고 있어(PR #744), 회수 실패를 회수로
덮는 중첩 상태다. MISC-02는 한 브랜치가 구현을 끝냈는데(`43e5d6d8`) **다른 브랜치는 같은
태스크를 `blocked`로 판정**했다(`6d61321d` — "acceptance 필드 오류 + 교수학 결정 필요") —
`S4-14`가 두 브랜치에서 정반대 판정을 받았던 `problem_bank_gap_review_r2.md` §0-①과 동형이다.

#### main 실측 — 무엇이 없는가

```
없음  src/backend/whymath_backend/l4/misconception/prerequisite_link.py     (MISC-02)
없음  src/backend/whymath_backend/l4/misconception/distractor_link.py       (ASM-06)
없음  src/backend/whymath_backend/db/models/misconception_relation.py       (MISC-04)
없음  src/backend/whymath_backend/harness/misconception_slip_report.py      (MISC-05)
```

그리고 1차가 **"반복 실수 7회차"**로 등재한 바로 그 증상이 그대로다 —
`visualize_misconception()`의 production 호출자는 **여전히 0건**(export 2곳 +
`tests/backend/l4/test_misconception_visualize.py`만). 두 브랜치가 각각 이 결선을 끝냈는데도
main의 학생은 8일째 그 코드에 닿지 않는다.

#### 이 고립은 **숨어 있지 않았다** — 하네스가 매번 말하고 있다

가장 중요한 단서다. `backlog.py next`를 돌리면 HARN-11 미머지-done 탐지기가 **매 실행마다**
다음을 출력한다(이 문서 작성 중 실측):

```
⚠ 후보 제외 MISC-01-visualization-shadow-rollout — 이미 완료(미머지): claude/human-bottleneck-tasks-6dszy0, claude/subject-problems-theory-check-7n9n72, merge/human-bottleneck-6dszy0
⚠ 후보 제외 MISC-02-prerequisite-coaching-misconception-link — 이미 완료(미머지): claude/subject-problems-theory-check-7n9n72
⚠ 후보 제외 MISC-03-misconception-similar-problem-serving — 이미 완료(미머지): ...
⚠ 후보 제외 MISC-05-root-symptom-slip-observation-report — 이미 완료(미머지): ...
⚠ 후보 제외 MISC-06-misconception-recurrence-signal — 이미 완료(미머지): ...
⚠ 후보 제외 ASM-06-distractor-misconception-reverse-link — 이미 완료(미머지): ...
```

(MISC-04만 이 목록에 없는 것은 해소돼서가 아니라 **원격 claim으로 이미 후보에서 빠져** HARN-11
검사 대상 집합(`ready`)에 들어가지 않기 때문이다 — `backlog.py:162`가 `ready`에만 스캔을 건다.
MISC-01이 세 브랜치에 중복 표기된 것도 이중 구현의 기계 증거다.)

따라서 이번 고립의 성격은 **"아무도 몰랐다"가 아니라 "기계가 매번 알려주는데 아무도 회수하지
않았다"**이다. 즉 결함은 탐지가 아니라 **회수 실행**에 있고, 탐지기를 하나 더 만드는 것은
대책이 아니다(§6-ⓐ).

**착수 금지 고지**: `misc-04-misconception-relation-recovery`·`subject-problems-theory-check-7n9n72`
두 브랜치는 이 문서 작성 시점에 **다른 세션이 claim 중**이다. 회수는 태스크로만 등재하고
실행하지 않는다(2026-07-27 OPS-07 병렬 구현 735줄 폐기 사고 회피).

### ③ 1차 수치 4종 — 드리프트 0 (전건 재실측)

| 수치 | 1차(2026-08-03) | R2 재실측(2026-08-11) | Δ |
|---|---|---|---|
| kebab 런타임 탐지 카탈로그 | 64종 | **64종** | 0 |
| M-id 콘텐츠 카탈로그 | 843건(18필드) | **843건(18필드)** | 0 |
| crosslink 라이브 | 64행 | **64행** | 0 |
| `concept_graph_v1` 437개념 중 `misconception_codes` 채움 | 0건 | **0건** | 0 |

런타임 게이트 기본값도 무변화: `misconception_semantic_mode="off"` ·
`misconception_judge_enabled=False` · `misconception_judge_shadow=False` ·
`misconception_crosslink_mode="off"` · `misconception_wrong_form_mode="off"`.

즉 **8일 동안 오개념 모듈의 학생 대면 상태는 한 비트도 바뀌지 않았다.**

---

## §1. 1차 판정 대비 Δ — 바뀐 칸만 3건

1차의 §1(기능11 16행)·§2(기능12)·§3(기능13 8행) 중 **재실측으로 판정이 달라진 칸만** 적는다.
나머지는 §0-③이 보인 대로 무변화이므로 1차 판정을 그대로 승계한다.

| 기능 | 1차 판정 | R2 실측 | 새 판정 |
|---|---|---|---|
| **12-④ AI(LLM) 추론** | "✅ 코어·기본 off" + 04c가 "현재 coach 미배선" | **coach에 실결선돼 있다** — `api/coach.py:780` `candidates = await judge_filter(candidates, student_input, judge=_make_judge())`. 플래그(`misconception_judge_enabled`)가 ON이면 즉시 발동. 라우터 경유도 준수(`judge_seam.py` → `l3.pipeline.generate`) | ✅ (배선 완료·게이트 off) |
| **13-③ 시각화** | "△ 코드 완비, production 호출자 0건" | **두 갈래로 갈라진다.** (a) `visualize_misconception()` 호출자는 **여전히 0건** — 1차 판정 유효. (b) 그러나 **오개념 → 개입 결정 → 학생 대면 요소**는 *다른 좌석으로 라이브*다: `POST /v1/scenes/weak-concept`(`api/scene.py`, `ConsentedUser`) → `scene_generation.py:231 _misconception_probes()` → `select_intervention` 결정트리 구동 → `MisconceptionProbeElement`가 `:384`에서 장면에 실린다 | △ (a 유효 / **b 신규 발견·라이브**) |
| **13-① 개념 재설명** | "⚠️ `supply()`에 misconception 입력 슬롯 없음" | **더 나쁘다 — 슬롯도 규칙도 있는데 신호원이 없다.** `l4/pedagogy/runtime_selector.py:145`에 `misconception_ids: tuple[str, ...] = field(default=())` 슬롯이 있고 `:203`에 규칙 R2(`if signals.misconception_ids: return PedagogyStrategy.ANALOGY`)가 있다. 그런데 프로덕션 유일 생산자 `api/study.py:155 StudentSignals(...)`는 `mastery_level`·`bkt_mastery`·`irt_theta` **3개만** 채운다 → 규칙 R2는 라이브에서 **절대 발화하지 않는다** | △ → **선언≠집행**(§2 G3) |

**13-③(b)의 의미**: 1차의 "교정 전략 8종 중 3종만 학생에게 도달"이라는 회계는 *coach 응답
경로만* 센 것이었다. scene 경로를 넣으면 **오개념→개입 결정→학생 대면**은 이미 두 경로로
성립한다. 다만 그 개입은 `select_intervention`의 2종(반례·거꾸로사고)이므로 **8종 중 몇 종이
도달하는가**라는 총평은 바뀌지 않는다 — 바뀌는 것은 "어느 좌석이 그 일을 하고 있는가"다.
`MISC-01`을 회수할 때 **이미 라이브인 scene 경로와의 중복 개입**을 반드시 확인해야 한다(같은
턴에 프로브와 시각화가 겹쳐 나가면 과개입).

---

## §2. 잔여 갭 — R2 신규 실측 6건

### G1 — 손글씨(OCR) 풀이가 오개념 엔진에 **0 기여** (최대 갭 · 진단 입력축) → `04e §9-D1`

WhyMath의 정체성 목록 첫 줄에 **"손글씨 풀이 단계별 검증"**이 있다(CLAUDE.md). 그런데 사진으로
제출된 풀이는 오개념 진단에 **한 글자도 들어가지 않는다.**

**추적 (전건 직접 Read)**

1. 진단·영속의 유일 입력은 `student_input`이다 — 세 핸들러 전부:
   `coach.py:1714`(stateless `/v1/coach`) · `:1769`(세션 생성) · `:2123`(턴 추가) 모두
   `await _compute_matches(body.student_input, ocr_confidence=..., judge_deps=...)`.
2. 모바일은 OCR 결과를 **`student_solution`으로** 보낸다:
   `chat_screen.dart:187` → `chat_controller.dart:135 sendOcrSolution(result)` — 이 호출은
   `studentInput` 인자를 **주지 않는다**(선언부 기본값 `String studentInput = ''`), 인식 LaTeX는
   `studentSolution: result.plainLatex`로 간다.
3. 백엔드의 정전(canonical) 매핑도 같은 규약이다:
   `api/ocr_handoff.py:49-51` — `student_input`은 *"학생의 대화 발화(OCR 산출 아님·호출자
   제공). 빈 문자열 허용"*, LaTeX는 `student_solution`.

**귀결**: 사진 제출 턴은 `_compute_matches('')` → `diagnose('')` → signals AND 매칭이 빈
문자열에서 성립할 수 없어 후보 **0건** → `curate_hypothesis`에 넘길 매치 0 → **가설 0 · 증거
0**, 응답 `misconceptions: []`.

**split-brain**: 정작 코치가 *실제로 하는 말*을 만드는 WH-1 primary 경로는 LaTeX를 본다 —
`coach.py:1620 run_wh1_primary_turn(student_solution=body.student_solution or body.student_input)`,
`wh1_primary_enabled` 기본 **True(GA)**. 즉 **발화는 학생의 풀이를 읽고, 학생 상태(가설·증거)는
읽지 않는다.** 같은 턴의 두 경로가 서로 다른 입력 정의를 쓰고 있다.

**충돌하는 정본 2개**: CLAUDE.md 정체성("손글씨 풀이 단계별 검증") · ALWAYS 교수학("모든 오답은
*오개념 후보* 분석 시도"). 사진으로 낸 오답은 후보화 자체가 되지 않는다.

**왜 무증상인가**: 실패가 예외가 아니라 정상 응답이다. `misconceptions: []`는 "매칭 없음"과
구별되지 않고(그 구별을 위해 만든 `no_confident_match` 플래그조차 후보가 애초에 0이면
`False`), 코치는 발화를 정상적으로 내놓는다. **"작동한 비율"을 말하는 신호가 없어서 8일이
아니라 그보다 오래 무증상이었을 수 있다.**

판정: **⚠️ (최대 갭)**

### G2 — 품질 게이트(floor 0.65)가 프로덕션 주경로에 미적용 → `04e §9-D2`

`apply_match_quality_gate`(top-1 신뢰도 < 0.65면 후보를 비움 — "억지 매칭 금지")의 호출부는
저장소 전체에서 **`api/coach.py:781` 단 1곳**이다(import·정의·`__all__` 제외).

그런데 `wh1_primary_enabled` 기본값은 **True(2026-07-20 GA)**이고, 그 경로의 진단은
`harness/wh1_loop.py:424 state.last_matches = diagnose(action.student_text)` — **floor를 거치지
않는다**. 이후 `intervene`의 0.5 임계만 적용된다.

즉 **같은 계약이 경로마다 다르게 집행된다**. 1차 §2가 인용한 "§3.3 품질 게이트"는 coach
응답 경로의 성질이지 시스템의 성질이 아니었다.

판정: **⚠️** — CLAUDE.md 금기 *"정본화를 집행으로 착각한 완료 선언 금지"*의 변형(계약은
정본화됐고 한 경로만 부른다).

### G3 — 선언≠집행: ANALOGY 규칙이 라이브에서 발화 불가 → `04e §9-D3`

§1 13-① 상세. `runtime_selector.py:203`의 규칙 R2는 **입력이 영원히 비어 있어** 도달 불가
코드다. `signals.misconception_ids`를 채우는 생산자는 저장소에 **0건**(동명 필드가 여럿
있으나 전부 다른 축 — `EquivalenceSpec.target_misconception_ids`(문항 생성 스펙) ·
`unit_dsl.misconception_ids`(교수법 DSL) · `pedagogy_dsl` ORM 컬럼).

한편 **채울 재료는 이미 있다**: `l2/learner_state.py:89 LearnerState.active_misconceptions:
list[str]`(PED-05 done, 생산자 `_get_active_misconception_ids` `:110`).

판정: **⚠️** — 1차 §8이 정리한 "만들고 신호원 하나를 안 이음" 계열(REC-02·D2와 동형).

### G4 — 교정 효과를 측정하는 축이 없다 ("작동한 비율" 원칙 미충족) → `04e §9-D4`

문서 13은 "교정 전략을 고르는 법"까지만 요구한다. **WhyMath 원칙은 한 걸음 더 요구한다** —
붙인 전략이 *실제로 작동했는지*를 응답·리포트가 말해야 한다(CLAUDE.md 금기 "작동 신호 없는
알고리즘 부착 금지").

현행 유일한 근사물은 `⑩ 오개념 해소율`인데:

- 정의 = `MisconceptionHypothesisRecord.is_active == false` **비율**
  (`harness/wh1_evaluation.py:1202`).
- 코드가 스스로 자백한다(`:1208-1213`): *"전용 resolved_at/사유 컬럼이 없어 '학생이 실제로
  오개념을 극복한 해소'와 '증거 부족으로 stale 정리된 비활성화'를 구분하지 못한다"*.
  감쇠(반감기 5턴)·반박·max_active 5 캡 절단이 전부 같은 `is_active=false`로 수렴한다.
- 그런데 노출 티어는 `harness/growth_evidence_exposure.py:79`
  `"misconception_resolution_rate": ExposureTier.STUDENT_VISIBLE` — **학생에게 보인다**.
- 그리고 근사임을 알리는 서술은 **구조적으로 전달되지 않는다**: `GrowthEvidenceMetricView`
  (`api/me.py:3125-3130`)가 *"`Metric.note`는 의도적으로 이 뷰에 없다 — 학생 대면 톤으로 검수된
  적 없는 내부 진단 문구라 범위 밖"*이라고 명시한다. 그 결정 자체는 옳다(검수 안 된 문구를
  학생에게 흘리지 않는다) — **문제는 그 결과로 "근사"라는 사실만 정확히 탈락한다는 것**이다.

귀결: 학생은 **가설이 조용히 시들었을 뿐인 것을 "내가 오개념을 극복한 비율"로 읽는다.**
의사결정 우선순위 #1(학생 안전·정서)과 AI·신뢰 금기("확실하지 않을 때 자신 있게 말함 금지")에
동시에 걸린다.

부수 귀결: 이 축이 정직해지기 전에는 **8종 교정 전략의 효과 비교가 불가능**하다 — 04e §1-4가
"개념재설명·구체사례는 편익이 아직 측정되지 않았다"며 유보한 그 측정이 바로 이것이다.

판정: **⚠️** — **Kiki 확정(2026-08-11): 티어 강등 후 재승격**(§5·`04e §9-D4`).

### G5 — crosswalk 검수 큐 111행 **전행 pending**, 사람 게이트 정체

`docs/data/misconception_crosslink_review_queue.json`의 `review_queue` = **111행**
(직접매핑 68 · 부분매핑 38 · 개념겹침 5), **`status`가 111행 전부 `pending`**. 마지막 내용
변경은 2026-07-02(#392 검수 반영)이고 이후 승인 0건이다.

그 결과 라이브 crosslink는 **64행 그대로**이고, M-id **843건 중 779건이 런타임 탐지와 무연결**
이라는 1차 §0 진단이 한 건도 좁혀지지 않았다. 승인은 기계가 대신할 수 없다 —
`l1/misconception/crosslink_gate.py`가 **거부만 기계 자율**로 허용하고 승인은 사람 서명
(`reviewer` + `reviewed_on` + 서명 stamp 정규식) 전용으로 동결한다.

판정: **🚫 (코드 갭 아님)** — 사람 게이트 사안이다. 이 문서는 사실만 기록하고 태스크를
만들지 않는다(법령·검수 유래 절차의 기계 대체 금지). 재촉이 필요하면 `backlog/gates.yaml`의
게이트 대장 소관이다.

### G6 — 교정축 코드 비대칭 (구조 관찰 — 1차 결론의 정량 재확인)

`src/backend/whymath_backend/l4/misconception/` **41파일** 중:

| 축 | 파일 수 | 대표 |
|---|---|---|
| 진단 | 15 | `diagnose`·`combined`·`match_gate`·`judge*`·`semantic/`·`wrong_form_match`·`distractor` |
| 상태(가설·증거·프로브) | 6 | `hypothesis`·`hypothesis_store`·`evidence_store`·`probe_selection`·`probes`·`warmstart` |
| crosswalk 운영 | 10 | `crosslink_*` |
| 관측·평가 | 7 | `shadow`·`*_shadow_harvest`·`semantic_eval`·`audit`·`validate` |
| **교정** | **3** (334줄) | `intervene`·`visualize`·`models` |

1차의 "진짜 갭은 교정 축"이라는 결론을 코드량이 독립적으로 재확인한다. 그리고 그 3파일 중
1개(`visualize.py`)는 §0-②가 보인 대로 아직 호출자가 없다.

판정: **관찰**(태스크 없음 — G1~G4 해소가 이 비대칭의 실질적 처방이다).

---

## §3. 의도적 미채택 — 1차 6건 전부 승계 (재론하지 않음)

① 발생 빈도 통계 · ② 개념 그래프 traversal 기반 오개념 추론 · ③ 오개념 초기 context preload ·
④ 관계 타입 자유 확장 · ⑤ BKT/DKT ↔ 오개념 융합 예측 · ⑥ 성적·서열류 예측.

근거는 1차 §6 그대로이며, R2에서 이 6건의 전제가 바뀐 정황은 **발견되지 않았다**. 오히려
격리 동결이 강화된 채 유지되고 있음을 재확인했다 —
`tests/backend/l4/test_misconception_seven_stage_manifest.py`의
`test_misconception_tables_disjoint_from_concept_tables` ·
`test_misconception_tables_have_no_foreign_key_into_concept` ·
`test_runtime_gate_defaults_are_reactive` 3종이 그대로 red-guard 중이다.

**주의**: §2 G1(D1) 해소는 이 목록의 ③(preload 금지)과 **무충돌**이다 — 진단 *입력*에 학생이
방금 제출한 자기 풀이를 넣는 것이지, 오개념 *내용*을 컨텍스트에 미리 싣는 것이 아니다.
reactive retrieval의 4중 강제(`warmstart.py`의 `list[str]` 타입 차단 · `test_wh1_shadow.py`
스파이 · `session_recall` 미주입 · 게이트 기본값 동결)는 그대로 유지된다.

---

## §4. 정직한 공백 — 지금 하지 않는 것

1. **1단계 14~16의 잔여**(관계셋 이후의 노드화·원인 분류축·예측) — 1차 §4 판정 유지.
   MISC-04(관계셋)가 **main에 착지한 뒤에야** 다음을 논한다. 지금은 착지조차 안 됐다(§0-②).
2. **2~3단계 17~19**(버전관리·연구플랫폼·자동발견) — 1차 §5 판정 유지. 전제조건(엔트리 단위
   타임스탬프 · 학술 재검수 · 843건 미검수 AI생성 · 미성년자 데이터 마이닝 동의)이 8일 동안
   하나도 충족되지 않았다. **발화 조건**: G5(검수 큐)가 풀려 카탈로그가 "검증된 콘텐츠"가 될 때.
3. **G5 crosswalk 승인 재촉** — 사람 게이트라 코드·태스크로 밀지 않는다(§2 G5).
4. **고립 회수의 *실행*** — 태스크로만 등재한다. 두 브랜치가 타 세션 claim 중이라
   지금 손대면 2026-07-27 OPS-07(병렬 구현 735줄 폐기)의 재현이다.
5. **`MISC-01`·`MISC-04` 이중 구현의 정본 판정** — 두 구현의 설계 판단이 다를 수 있어
   기계가 결정할 사안이 아니다. 회수 태스크 acceptance에 "어느 쪽을 정본으로 삼는지 실측 대조
   후 명시"를 넣고, 판정이 갈리면 사람 게이트로 올린다(`problem_bank_gap_review_r2.md` R2 선례).

---

## §5. 정정 — stale 정본 3곳 (소유 문서를 이 문서가 고치지 않고 기록만)

| # | 위치 | 현재 기술 | R2 실측 | 처리 |
|---|---|---|---|---|
| 1 | `04c_misconception_seven_stage_separation.md:130-131` | "런타임 탐지 정본(kebab-id **30종**)과 콘텐츠 카탈로그(M-id **839종**)" | **64종 · 843건** | 1차 §0-②가 이미 지적했으나 **8일째 미정정** → 이 R2가 재등재. 정정은 소유 문서(04c)의 몫 |
| 2 | `l4/misconception/judge.py:21,24` | "배선 경계(슬108: **coach 미배선**·하니스 측정만)" / "이번 슬라이스는 judge를 *coach에 배선하지 않는다*" | `api/coach.py:780`에 `judge_filter` 결선됨 | docstring 1곳 — 동작 무변경 |
| 3 | `04_pedagogy_engine.md:184` | 성공 기준 "오개념 **30개** + 개입" | 64종 | 소유 문서의 몫 |

(`02_learner_model.md:234`의 같은 계열 "30개" stale은 2026-08-01에 이미 실측 주석으로 정정돼
있다 — 재등재하지 않는다.)

---

## §6. 반복 실수 — 재발방지 등재 (CLAUDE.md 의무)

### ⓐ 미병합 브랜치 고립 — **4회차**

`problem_bank_gap_review_r2.md` §6-ⓐ가 3회차까지 정리한 계열의 다음 회차다.

| 회차 | 사례 | 형태 |
|---|---|---|
| 1~3 | S3-24/S3-25 · `education-os-architecture-mr0fbq` 외 · 문제은행 D1/D3/D5/D8 | 완료분이 PR 없이 브랜치에 잔류 |
| **4 (신규)** | **MISC-01~06 + ASM-06 — 7건 전부** | 완료분이 **3개 브랜치에 분산** 잔류. 3건은 열린 PR(#739·#744)에 있으나 머지되지 않고, 4건은 **PR조차 없다** |

**3회차와 다른 점 — 고립이 중복을 낳는 단계로 진행했다.** MISC-01·MISC-04가 **각각 두 세션에
의해 구현**됐고, MISC-02는 한쪽이 구현을 끝낸 태스크를 다른 쪽이 `blocked`로 판정했다. 즉
고립은 이제 "머지 대기"가 아니라 **작업 낭비를 능동적으로 생산하는 상태**다.

**두 결함을 분리해야 한다** — §0-②가 보인 대로 이 회차는 원인이 두 겹이다.

1. **중복 구현이 일어난 원인 = claim 실패**(예방 축). 2026-07-27 등재된 CLAUDE.md 금기
   *"상시 실패하는 fail-open 보호를 '보호 있음'으로 신뢰 금지"*가 지목한 그대로 —
   `refs/claims/*` push가 CCR git 프록시에서 상시 실패해 세션 간 claim이 fail-open으로 통과한다.
   읽기측 폴백 `HARN-07`이 이미 등재돼 있으므로 **새 규칙·새 태스크를 만들지 않고 그쪽을
   지목**한다(중복 등재 금지).
2. **완료분이 머지되지 않은 원인 = 회수 미실행**(상환 축). 이쪽은 **탐지 실패가 아니다.**
   HARN-11이 `next`를 돌릴 때마다 6건을 이름과 브랜치까지 찍어 알린다(§0-②). 그런데도 8일간
   회수되지 않았다.

**따라서 이 회차의 대책은 탐지기 신설이 아니다.** 탐지기를 하나 더 만드는 것은 이미 울리고
있는 경보에 경보를 더하는 일이고, 그 자체가 CLAUDE.md 금기 *"상시 실패하는 보호를 '보호
있음'으로 신뢰 금지"*가 경고한 **경고 습관화**의 재생산이다. 실질 대책은 **회수를 우선순위
1의 실행 태스크로 세우는 것**이다 → `MISC-11`(priority 1 · S3 · 현재 `backlog.py next`가
계산한 **최우선 후보**).

**부수 관찰**: `next`의 경고 6줄이 소음으로 읽히기 시작했다는 것 자체가 신호다. 같은 경고가
반복 관측되면 그 보호는 상시 무력 상태라는 규칙(2026-07-27)의 **탐지 측 변형**이다 — 규칙은
"fail-open 보호"를 다뤘고, 이번은 "정상 작동하지만 아무도 행동하지 않는 경보"다. 규칙을
확장할지는 이 R2가 단독으로 결정하지 않고 관찰로만 남긴다(반복 2회 전 규칙 신설 금지).

### ⓑ "만들고 ○○을 안 함" — **9·10회차**

1차 §8이 7·8회차(시각화 호출자 0 · 선수복습이 오개념을 모름)를 등재한 표의 연장이다.

| 회차 | 사례 | 형태 |
|---|---|---|
| (기존 1~8) | OPS-03·VIZ-01·NLP-01·D1·D2·REC-02 · 시각화 호출자 0 · 선수복습 미연동 | CI/적재/배포/입력/공급원 미결선 |
| **9 (신규)** | **ANALOGY 규칙(G3)** — 슬롯·규칙 완비, 생산자 0 | 만들고 **신호원을 안 이음** (8회차와 동형) |
| **10 (신규)** | **품질 게이트(G2)** — 계약 완비, 호출자 1/2 경로 | 만들고 **일부 경로에만 부름** — *신규 형태*: 기존 회차는 "0곳에서 부름"이었는데 이번은 **"한 곳에서만 부름"**이라 그 한 곳의 테스트가 green이라 무증상이 더 깊다 |

10회차는 CLAUDE.md 금기 *"정본화를 집행으로 착각한 완료 선언 금지"*의 **부분집행 변형**이다.
기존 규칙이 "계약을 서빙 코드가 부르는가"를 묻는다면, 이 변형은 **"계약을 서빙 코드가 *전부*
부르는가"**를 묻는다. 규칙 신설 대신 `OPS-22`(선언≠배선 일반 탐지기, PR #742 열림)가 이
축(단일 호출자 계약)을 잡을 수 있는지 확인하는 것이 우선이다 — 잡을 수 있으면 중복 등재하지
않는다.

### ⓒ 1차 대조 문서가 스스로 지적한 stale이 8일간 미정정 (§5-1)

1차 §0-②가 04c의 "30종"을 실측으로 잡아냈으나 소유 문서가 고치지 않았다. **갭 리뷰가 정정을
"소유 문서의 몫"으로 위임하면 아무도 안 고친다**는 것이 이번 실측이다. 대책: R2는 위임하지
않고 §5의 3곳을 **이 PR에서 직접 고친다**(수치·docstring 1줄 — 동작 무변경).

---

## §7. 등재 요약

| 태스크 | 갭 | stage | priority | 근거 |
|---|---|---|---|---|
| `MISC-07-ocr-solution-into-diagnosis` | G1 | S3 | 2 | 손글씨 제출 턴의 가설·증거 적재 0(§2 G1) |
| `MISC-08-match-gate-single-enforcement` | G2 | S3 | 3 | `apply_match_quality_gate` 호출자 1/2 경로(§2 G2) |
| `MISC-09-analogy-signal-wiring-or-removal` | G3 | S4 | 4 | 규칙 R2 라이브 발화 불가(§2 G3) |
| `MISC-10-resolution-rate-honesty` | G4 | S3 | 2 | 근사값이 STUDENT_VISIBLE·note 구조적 미전달(§2 G4) |
| `MISC-11-isolated-completion-recovery` | §0-② | S3 | 1 | 6+1건 고립·이중 구현 2건(§6-ⓐ) |

태스크는 전건 `scripts/harness/backlog.py add` CLI 경유로 등재했다(ID 손편집 0 · 번호 충돌은
CLI가 로컬 백로그 + 원격 claim 대장 양쪽에서 검사 — HARN-10). `--path` 선언으로 겹침 검사를
켰다.

**중복 소유권 회피 실측**(등재 전 열린 태스크 전수 확인): 열린 태스크 중 오개념·진단입력·
게이트·성장증거를 다루는 것은 `MISC-01`~`06`(1차 등재분, 고립 상태) · `ASM-06` ·
`PB-02`(선언≠배선 — S6 야간 재검증 코퍼스 축, 다른 대상) · `PED-14`(⑨ mastery_gain_rate
시간 정규화) · `S4-15` · `E1-04` · `E2-01`. **G1~G4를 다루는 태스크는 0건**이었다.
`PED-14`는 `growth_evidence_exposure.py`를 paths로 공유하나 **다른 지표(⑨ vs ⑩)**이므로
중복이 아니며, 양쪽 태스크 notes에 상호 참조를 남겨 동시 수정 시 충돌을 예고했다.

---

## 부록 — 실측 근거 (2026-08-11 · HEAD `959ec4ad` · 전건 직접 확인)

**§0-② 고립**
```
git log --all --oneline --since=2026-08-03 -- '*misconception*'
git branch -a --contains <sha>            # 커밋→브랜치 귀속 확인
git diff --name-only main...origin/<branch> | grep -i misconception
```
- `origin/claude/subject-problems-theory-check-7n9n72`(HEAD `849343f1`, 2026-08-11) — ASM-06·
  MISC-02·MISC-05·MISC-06 완료 커밋 + `backlog done` 처리까지. **열린 PR 없음**
- `origin/claude/human-bottleneck-tasks-6dszy0`(HEAD `67881979`, 2026-08-09) — MISC-01·03·04.
  머지 PR **#739 열림**
- `origin/claude/misc-04-misconception-relation-recovery`(HEAD `7eaaa695`) — MISC-04 재구현.
  PR **#744 열림** (제목: "#739가 빠뜨린 완료분")
- main 부재 4파일: `l4/misconception/prerequisite_link.py`·`distractor_link.py`·
  `db/models/misconception_relation.py`·`harness/misconception_slip_report.py`
- `grep -rn "visualize_misconception" src/` → `l4/__init__.py:50,110` ·
  `l4/misconception/__init__.py:44,71` (export 4건) 외 production 호출자 **0**

**§0-③ 수치**
- `l4/misconception/catalog.py` `Misconception(` 생성자 **64**
- `data/corpus/misconceptions_v1/misconceptions.json` `count`=**843**, 레코드 18필드
- `data/corpus/misconception_crosslinks_v1/crosslinks.json` **64**행
- `data/corpus/concept_graph_v1/graph.json` `concepts` **437** 중 `misconception_codes` 비어있지
  않은 것 **0** (edges 581)
- 게이트 기본값: `config.py:955`(`"off"`) · `:971`(`False`) · `:986`(`False`) · `:1004`(`"off"`) ·
  `:1021`(`"off"`)

**§1 Δ**
- `api/coach.py:780` `judge_filter(...)` / `:127` import
- `l4/misconception/judge.py:21,24` stale docstring 원문
- `api/scene.py` `POST /v1/scenes/weak-concept`(`ConsentedUser`) → `get_active_hypotheses` +
  `net_support_by_misconception` → `SceneLearnerContext`
- `l4/scene_generation.py:231 _misconception_probes()` · `:384 elements.extend(...)` ·
  `select_intervention` 재사용(신뢰도<0.5 → 프로브 미생성)
- `l4/pedagogy/runtime_selector.py:145`(슬롯) · `:203`(규칙 R2)
- `api/study.py:127 _build_signals(...)` · `:155 StudentSignals(mastery_level=, bkt_mastery=,
  irt_theta=)` — `misconception_ids` **미전달**

**§2 G1**
- `api/coach.py:1714`·`:1769`·`:2123` — `_compute_matches(body.student_input, ...)`
- `api/coach.py:704` `_compute_matches` 시그니처(첫 인자 `student_input: str`)
- `api/coach.py:1620` `run_wh1_primary_turn(student_solution=body.student_solution or
  body.student_input)` · `config.py:168 wh1_primary_enabled=True`
- `src/mobile/lib/features/chat/application/chat_controller.dart:135-137`
  (`String studentInput = ''`) · `:152 studentSolution: result.plainLatex`
- `src/mobile/lib/features/chat/presentation/chat_screen.dart:187 sendOcrSolution(result)`
  (인자 1개)
- `api/ocr_handoff.py:31-56` `ocr_result_to_coach_request` — `:41` "student_input: 학생의 대화
  발화(OCR 산출 아님)·빈 문자열 허용", `:51 student_solution=result.plain_latex or None`

**§2 G2**
- `grep -rn "apply_match_quality_gate" src/` → `api/coach.py:129`(import) · `:713`(주석) ·
  `:781`(**유일 호출**) · `l4/misconception/match_gate.py:44,126`(정의·`__all__`)
- `harness/wh1_loop.py:423-425` — `diagnose(action.student_text)`, 게이트 없음

**§2 G4**
- `harness/wh1_evaluation.py:395-400`(⑩ 필드 description) · `:1202-1219`
  (`_misconception_resolution_from_counts` — 자백 docstring · `total<=0` → NO_DATA)
- `harness/growth_evidence_exposure.py:79` `STUDENT_VISIBLE`
- `api/me.py:3125-3130` `GrowthEvidenceMetricView` docstring("`Metric.note`는 의도적으로 이
  뷰에 없다") · `:3227-3251 _render_growth_evidence_metric` · `:3208`(⑩ 필드) · `:3319`(렌더)

**§2 G5**
- `docs/data/misconception_crosslink_review_queue.json` `review_queue` **111**행 ·
  `status` 전행 `pending` · `link_type` 직접매핑 68 / 부분매핑 38 / 개념겹침 5
- `l1/misconception/crosslink_gate.py` — `promotion_violations`(승인 4조건) ·
  `load_gate_violations`(manual + 서명 stamp)
- `backlog/gates.yaml` `G-crosswalk-approval`(status `cleared` — 라이브 64행분 서명)

**§2 G6**
- `ls src/backend/whymath_backend/l4/misconception/` → 41 항목(`semantic/` 포함) ·
  교정 3파일 `intervene.py`(110) `visualize.py`(81) `models.py`(143)

**§3 격리 동결 재확인**
- `tests/backend/l4/test_misconception_seven_stage_manifest.py` —
  `test_misconception_tables_disjoint_from_concept_tables` ·
  `test_misconception_tables_have_no_foreign_key_into_concept` ·
  `test_runtime_gate_defaults_are_reactive`

---

**작성**: 2026-08-11 · **선행**: `misconception_module_gap_review.md`(2026-08-03) ·
**설계 위임**: `04e_misconception_remediation_design.md §9`
