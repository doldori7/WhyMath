# AI 추천(AI Recommendation) 모듈 — 외부 EOS 틀 대조 **3차 재점검(r3)** (2026-08-11)

> **범위**: v1(`ai_recommendation_module_gap_review.md`, 2026-08-01)·r2(`ai_recommendation_module_gap_review_2.md`,
> 2026-08-04)와 **동일한 외부 참고 문서**(『19. AI 추천』 — 기능 80 문제 추천 · 81 개념 추천 ·
> 82 학습 시간 추천 · 83 난이도 자동 조절, 세부 57개 + **「AI 추천 엔진 구조」 다이어그램** +
> **「WhyMath에서의 역할」 문단** — **WhyMath 전용이 아닌 일반적인 EOS 틀**, Kiki 제공 docx)를
> ⑴ **v1·r2가 한 번도 대조하지 않은 두 축**과 ⑵ **v1·r2 이후 착지분이 만든 새 지형**에 대해
> 다시 대조한 기록. 설계는 WhyMath 불변식(Layer Separation · Concept Purity · reactive retrieval ·
> 교수학 금기 · 반게임화 · dead code 금지 · 침묵 실패 금지 · 측정 없는 도입 없음 ·
> **정본화≠집행 금지** · **만료 없는 유예 금지**) 안에서만 한다.
>
> **성격**: 57세부 전수 재대조가 **아니다**. v1 §1 판정과 §2 의도적 미채택 9건, r2 G1~G3와
> 미채택 1건은 **전건 승계하고 재판정하지 않는다**. 다만 **§1(엔진 다이어그램 4입력·1출력 +
> 4방향 연동 주장)만은 델타가 아니라 merged 정본 최초 대조**다 — v1 전수 grep에서
> `학생 프로필|게임화 75|학습분석 32`가 **0건**이다(부록 D).
>
> **결론 4줄**:
> 1. **최대 발견은 갭이 아니라 고립이다.** r2 본문과 그것이 등재한 `REC-05`~`REC-08` 4건이
>    **main에 한 번도 도달한 적이 없었다**(원격 `claude/whymath-ai-recommendation-review-tv1f08`
>    `fdf46d7b` · main 대비 24커밋 · `merge-base --is-ancestor` 실패). 그중 **둘은 `status: done`이고
>    구현 커밋까지 있는데 그 커밋이 main 조상이 아니다.** 더 나쁜 것은 **`backlog validate`가 이
>    상태를 green으로 통과시킨다**는 점이다 — 대장은 고립을 보지 못한다. 이 문서가 문서·YAML을
>    회수했고 구현 회수는 **`REC-09`**가 소유한다(**D6**).
> 2. **두 번째 갭 = v1·r2가 만든 정직 표기가 렌더 경계에서 전량 소실된다.** `REC-01`의 4필드와
>    `REC-04`의 `band_calibrated` — **신규 5필드를 Flutter가 하나도 파싱하지 않는다**(참조 0건).
>    파싱하는 `standardError`·`measurementSufficient`조차 모델 파일 밖 **reader 0**이다. 그리고
>    같은 파일 주석이 *"problemId가 null이면 추천 후보가 없다(측정 충분·또는 미시딩)"*라고 두
>    원인을 뭉개는데, **서버는 이미 `candidate_zero_reason`으로 그 둘을 구분해 보내고 있다.**
>    값이 없어서 못 하는 것이 아니라 **온 값을 안 받고 모호함을 문서화**했다 → **D7**.
> 3. **판정 뒤집기 1건 — `persona_fit`.** v1 §4-⑦은 "전 문항 `{}`라 추천 가중 축이 실질 무효",
>    r2 §4-④는 "재실측 변화 없음"이라 적었다. **2026-08-11 코퍼스 실측: 2,643/2,643(100%) 보유**이며
>    수능 사전필터가 실제로 소비 중이다. **r2가 stale이다**(§정정 ㉯). 그럼에도 태스크는 0건이다 —
>    데이터 전제만 충족됐고 추천 가중 축 배선은 여전히 0이라 지금 다는 것은 "측정 없는 도입"이다(§7-⑪).
> 4. 진짜 갭 3건(D6~D8)을 설계하고 태스크 3건을 등재했다(`REC-09`·`REC-10`·`OPS-34`). 확장 축
>    **최초 대조에서 나온 신규 태스크는 0건**이고, 그 0이 회피가 아님을 §1-B 표가 증명한다 —
>    **연동 3방향의 부재 사유가 서로 다르다**(동결된 범위 / 타 모듈 소유 / 규범적 거부).
>    신규 의도적 미채택 1건 · 반복 실수 **10회차** 등재 · v1·r2 stale 4곳 정정.

관련 정본: `ai_recommendation_module_gap_review.md`(**v1 — 판정 근거의 원본**) ·
`ai_recommendation_module_gap_review_2.md`(**r2 — 이 커밋에서 main에 최초 회수**) ·
`learning_path_module_gap_review_r2.md`(**§9 9회차 원칙 — D7의 직접 선례** · r2 형식의 모범) ·
`operations_module_gap_review_r3.md`(§8 3분할 서식 · D9 "정직 표기는 침묵 통과는 막지만 영구
미상환은 막지 못한다" — D8의 논리 원본) · `solution_module_gap_review_r3.md`(고립·죽은 사슬 취급) ·
`data_platform_module_gap_review.md`(`OPS-22` 선언≠배선 탐지기) · `02_learner_model.md` ·
`04a_wh1_tutoring_harness.md` · `docs/design/ui/00_index.md` **전역 UI 불변식 2**(반게임화) ·
`MEMORY.md` 결정 로그(2026-08-01 v1 · 2026-08-04 r2 · 2026-08-11 본 문서).

---

## §0. 재점검 사유 — 왜 v1·r2를 덮어쓰지 않고 r3를 쓰는가

### ① 문서 계보와 번호 대장

| 문서 | 날짜 | 설계 번호 | main 도달 | 상태 |
|---|---|---|---|---|
| `ai_recommendation_module_gap_review.md` (v1) | 2026-08-01 | **D1~D5** | ✅ (PR #661) | D1~D4 상환(`REC-01`~`REC-04` done) · D5 페이퍼 |
| `ai_recommendation_module_gap_review_2.md` (r2) | 2026-08-04 | **G1~G3** | ❌ → **이 커밋에서 회수** | G1·G3 유효 · G2 미착수(`REC-06` todo) |
| **`ai_recommendation_module_gap_review_r3.md`** (본 문서) | 2026-08-11 | **D6~D8** | — | 이 문서 |

**D 번호는 r2의 G1~G3에 이어 D6부터 연속한다**(운영 r3가 "r2에 이어 D7부터"로 세운 선례).
**G1~G3에 D 번호를 소급 부여하지 않는다** — 회수된 r2 본문과 `REC-05`~`REC-08`의 `notes`가 서로를
`G1`·`G2`·`G3`으로 가리키므로, 소급 개번은 회수와 동시에 참조 무결성을 깬다.

**파일명 불연속을 기록해 둔다**: v1은 `_gap_review.md`, r2는 `_gap_review_2.md`, 본 문서는
`_gap_review_r3.md`다. `_r{n}`이 현행 다수이자 최근 신규 전량이므로(`operations_r2`·`r3` ·
`learning_path_r2` · `solution_r3` · `gamification_r2` · `problem_bank_r2`) 여기서 정렬한다.
**r2 파일명은 개명하지 않는다** — `REC-05`~`REC-08`의 `notes`가 그 경로를 정본으로 지목하고 있어,
개명하면 회수와 동시에 4건의 참조를 stale하게 만든다. **이후 리비전은 `_r{n}`으로 통일한다.**

### ② r2가 main에 없었다 — 판정·태스크·구현 동시 고립

이것이 이번 재점검의 최대 발견이며, **갭이 아니라 프로세스 사고**다.

| 실측 | 값 |
|---|---|
| 고립원 | `origin/claude/whymath-ai-recommendation-review-tv1f08` @ `fdf46d7b` |
| main 대비 | **24커밋 앞섬** · `git merge-base --is-ancestor <branch> origin/main` → **EXIT=1**(미도달) |
| 고립 문서 | `ai_recommendation_module_gap_review_2.md` (346줄) |
| 고립 태스크 | `REC-05`(done) · `REC-06`(todo) · `REC-07`(todo·owner=kiki) · `REC-08`(done) — **main 백로그 0건** |
| 고립 구현 | `66bfe846`(REC-05 · `harness/attempt_grading_shadow_report.py`) · `1bac33bb`(REC-08 · `harness/selective_grading_demotion_eval.py` + `ci.yml`) — **둘 다 main 조상 아님**(EXIT=1) |
| 방치 기간 | 2026-08-04 → 08-11, **7일** |

**대장이 이 상태를 잡지 못한다는 것이 핵심이다.** 회수 직후 실측:

```
$ python3 scripts/harness/backlog.py validate
✔ 백로그 무결성 green — 태스크 259건, 게이트 10건, 트랙 3건   ← EXIT=0
```

`REC-05`·`REC-08`은 `status: done`이고 `artifacts`에 커밋 sha가 있는데 **그 sha가 main 조상이
아니다.** `validate`는 sha의 도달 가능성을 검사하지 않으므로 green이다. 즉 **"done + artifact 보유"가
"main에 있다"로 읽히는 무증상 상태**이며, 이는 CLAUDE.md "정본화를 집행으로 착각한 완료 선언 금지"의
**대장 평면 변형**이다 — 그 규칙이 "계약을 서빙 코드가 부르는가"를 묻는다면, 여기서 빠진 질문은
**"완료라고 적힌 그것이 트렁크에 있는가"**다.

**이 문서가 한 것과 하지 않은 것**을 명확히 가른다:
- **한 것** — r2 문서 + `REC-05`~`REC-08` YAML 4건을 `git checkout FETCH_HEAD -- <경로>`로 회수
  (`b8608bfd` math-engine 선례 · cherry-pick 아님 — 구현 커밋이 섞이지 않게).
- **하지 않은 것** — 구현 2커밋 회수. 소스 변경이라 갭 리뷰 시리즈 관례(문서+등재만)를 벗어난다.
  **`REC-09`가 유일 소유자**다(D6).
- **r2 본문은 무수정이다.** main에 처음 착지하는 문서이므로 "무엇이 2026-08-04에 참이었는가"를
  그대로 남기고, 델타는 전부 이 문서 §2·§정정이 보유한다.
- **`REC-05`·`REC-08`의 `status`를 손으로 되돌리지 않는다.** `done` 전이는 CLI 계약이고 역전이는
  계약에 없다. 대신 불일치를 §2 **고립 대장 표**로 드러내고 `REC-09` notes와 양방향 링크한다.

### ③ v1·r2 이후 착지 6건이 지형을 바꿨다

| 태스크 | 상태 | 이 문서에 미치는 영향 |
|---|---|---|
| `REC-01`(도달 관측) | done | `NextProblemResponse`에 신규 4필드 착지 → **D7의 재료이자 D7이 지적하는 경계** |
| `REC-02`(프로브 공급) | **done** | r2 시점 "타 세션 claim 중"이라 손대지 않았던 축. `harness/wh1_probe_supply.py` 신설·`wh1_primary`/`wh1_shadow` 양쪽 배선 → **§2 정정 ①** |
| `REC-03`(폐루프 회계) | done | `l2/recommendation_evidence.py` 처치 writer → **§1-B 학습분석 연동 판정의 근거** |
| `REC-04`(목적 분리) | done | `?purpose` + `l2/irt.py learning_band_weight` + `band_calibrated` → **D7의 다섯 번째 필드** |
| `S3-10` 재실행(08-07)·`S3-17` | done | `persona_fit` 100% 적재 + 수능 사전필터 소비 → **§정정 ㉯ 판정 뒤집기** |
| `NLP-02`·`S4-18`·`S3-16`·`PED-03`·`COLLAB-03`·`PED-06` | done | v1 §5 유보 조건들의 상류 — **§7 갱신** |

---

## §1. 최초 대조 — 틀의 두 축 ← **merged 정본 최초**

첨부 docx는 기능 80~83 뒤에 **「AI 추천 엔진 구조」 다이어그램**과 **「WhyMath에서의 역할」 문단**을
싣는다. v1은 다이어그램에서 **"단일 AI Recommendation Engine 컴포넌트"의 7계층 위반만** 판정했고
(§2-①), **입력 4축·출력 1축의 실재성**과 **역할 문단이 주장하는 4방향 연동**은 다루지 않았다.
r2도 델타 재점검이라 다루지 않았다. 본문 전수 grep에서 `학생 프로필|게임화 75|학습분석 32`가
**0건**이다(부록 D).

> **판정 기호**: ✅ 충족·초과 / △ 부분(부품은 있는데 *배선·정본* 없음) / ⚠️ 진짜 갭 → D /
> ⏸ 기존 태스크 승계 / 🚫 의도적 미채택 → §5
> 셀 문법: `✅ **단, …** → **Dn**` = "기능은 있다 / 그런데 도달·입력·기본값이 죽었다 / 그 축은 Dn이 다룬다"

### §1-A. 「AI 추천 엔진 구조」 — 4입력 → 1출력

| 틀의 축 | WhyMath 실재 | 판정 |
|---|---|---|
| **입력 ① 학생 프로필** | `persona_fit` **2,643/2,643(100%)** 적재(2026-08-11 실측) · θ·BKT 좌석 실재. **단 추천 가중 축으로의 배선은 0** — 현 소비는 수능 사전필터의 *자격 조건*(`api/me.py:2103`)이지 가중이 아니다 | △ 부분 → §7-⑪ (**v1 §4-⑦ 판정 뒤집기** — §정정 ㉯) |
| **입력 ② 학습 이력** | `ProblemAttempt` **0행** — 앱이 `POST /v1/me/attempts`를 호출하지 않는다(2026-08-11 재실측: Flutter `/v1/` **19경로** 전수에 부재) | ⏸ `REC-01`·`REC-07` 승계 |
| **입력 ③ 오개념 DB** | `distractor_map` **1,615문항 · 오개념 64종** + `REC-02` done(공급선 배선 — `harness/wh1_probe_supply.py`) | ✅ (**r2 시점 todo → done**) |
| **입력 ④ Knowledge Graph** | 원자 그래프 **2,683노드 / 2,210엣지** — 재실측에서도 **전부 `prerequisite`**(`EXTENDS` 0건) | △ 부분 ⏸ v1 §4-① 승계 |
| **출력 개인 맞춤형 학습 경로** | `next-problem`은 **단건 문항 반환**이지 경로가 아니다. 경로 축은 `l2/learning_path.py`·`PATH-*`가 별도 소유하며 두 축 간 호출 경로는 0 | △ 경계 분리(설계 의도) |
| **컴포넌트 형상** | 단일 Engine 박스 = 7계층 위반 | 🚫 **v1 §2-① 승계 · 재판정 없음** |

**이 표의 결론**: 틀이 그린 4입력 중 **실질 가동은 1개(오개념 DB)뿐**이고, 나머지 셋은 각각
*배선 없음*(프로필) · *입력 없음*(학습 이력) · *데이터 없음*(KG 심화 엣지)으로 **막힌 지점이 다르다.**
"입력이 부족하다"로 뭉치면 셋 다 같은 처방을 받게 되는데, 실제 처방은 각각 §7-⑪ · `REC-07` ·
v1 §4-①로 **서로 다른 소유자**에게 가 있다. 출력축(경로)은 부재가 아니라 **의도된 경계 분리**다 —
문항 추천(L2 CAT)과 개념 경로(L2 위상정렬)는 산출물의 단위가 다르며, 하나로 합치면 v1 §2-①이
거부한 단일 Engine으로 되돌아간다.

### §1-B. 「WhyMath에서의 역할」 — 4방향 연동 주장 vs 실재

틀은 이 4모듈이 *"학습 분석(32~36) · AI Tutor(37~41) · 학습 경로(54~57) · 게임화(75~79)와
**긴밀히 연동**"* 한다고 적는다. 실측 결과 **4방향 중 1개만 성립**한다.

| 틀의 주장 | 실재 | 실측 근거 | 판정 |
|---|---|---|---|
| **AI Tutor 37~41과 연동** | **실재** — 코치 응답이 개념 추천을 실제로 경유한다 | `api/coach.py:1766` → `_prerequisite_coaching_for`(`:969`) → L2 `recommend_prerequisite_gaps` → L4 `recommend_prerequisite_coaching` → HTTP `prerequisite_coaching` 필드(`:340`) | ✅ |
| **학습 분석 32~36과 연동** | **부재** — 집계가 추천 처치를 읽지 않는다 | `l2/learning_metrics_rollup.py`에서 `evidence_event|recommendation_evidence` grep **0건**. `REC-03`이 만든 처치 행을 읽는 집계가 없다 | ⏸ **승계 · 신규 태스크 0** |
| **학습 경로 54~57과 연동** | **부재(경계 분리)** — 추천은 단건, 경로는 `PATH-*` 소유 | 두 축 간 호출 경로 0. 단 개념 축에서는 BKT/IRT 신호를 공유한다(`l2/learning_path.py:95`) | △ ⏸ `PATH-*` 소유 |
| **게임화 75~79와 연동** | **부재(규범적 거부)** — `growth_evidence`·`/me/harness-metrics`는 `attempt_event` 기반이며 추천 처치와 무연결 | 전역 UI 불변식 2(반게임화)·`ARCH-26` 기계 게이트가 랭킹·스트릭·보상 연출을 소스 스캔으로 금지 | 🚫 **신규 의도적 미채택**(§5-⑪) |

**이 표가 존재하는 이유 — 부재 3건의 사유가 전부 다르다.**

- **학습 분석**은 *동결된 범위*다. `REC-03` acceptance ④가 "bandit 승격·보상 계산은 하지 않는다"를
  명시 동결했고, 결과 결합은 `session_id` 축이 성립하는 `S3-01-pilot-cohort` 이후로 미뤄져 있다
  (r2 §5-⑦ 승계). 지금 잇는 것은 **입력 없는 파이프라인**이다.
- **학습 경로**는 *타 모듈 소유*다. `learning_path_module_gap_review_r2.md`가 그 축의 `PATH-09`~`PATH-11`을
  이미 보유한다. 여기서 등재하면 중복이다.
- **게임화**는 *규범적 거부*다. 이것만이 "지금 못 한다"가 아니라 **"앞으로도 하지 않는다"**이며,
  §5에 미채택으로 등재해 다음 세션이 "빠진 연동"으로 오독하지 않게 한다.

**따라서 §1에서 나오는 신규 태스크는 0건이다.** 그 0이 회피가 아님을 이 표가 증명한다 —
"연동 3개 부재"라는 한 줄로 뭉치면 그 자체가 **D7이 지적하는 오류(원인 뭉개기)의 문서 평면
재생산**이 된다.

---

## §2. v1·r2 판정의 변경분 — 바뀐 칸만

전면 재판정이 아니다. **바뀐 칸만** 적고 나머지는 승계한다.

### 정정 ① — `REC-02`(D2 프로브 공급): **todo → done**

r2 §0은 `REC-02`를 "타 세션(`claude/whymath-probe-supply-h87afk`)이 원격 claim 중 — 이 문서는
손대지 않는다"로 두었다. **그 축은 2026-08-08 main에 착지했다**: `harness/wh1_probe_supply.py`
신설(`assemble_probe_candidate_pool`) · `wh1_primary.py:135`·`wh1_shadow.py:280` 양쪽이 후보를
실제로 채운다 · 후보 0의 사유별 계상 로그(`:100`)까지 붙었다. **v1 D2의 "도구6 상시 실패"는 상환됐다.**

### 정정 ② — `persona_fit`: **전 문항 `{}` → 2,643/2,643(100%)** ← **판정 뒤집기**

v1 §4-⑦은 "`persona_fit`이 전 문항 `{}`다 — 페르소나 적합도를 추천 가중으로 쓰는 축이 실질
무효"라 적었고, **r2 §4-④는 "재실측에서 변화 없음"이라 적었다**. 2026-08-11 코퍼스 전량 실측은
그 반대다 — **2,643문항 전건 보유(100%)**이며 `S3-17`이 수능 사전필터의 세 번째 OR 조건으로 실제
소비한다(`api/me.py:2103`). 적재는 `S3-10` 재실행(2026-08-07)으로, **r2 작성 3일 뒤**에 일어났다.
**r2가 stale이다**(§정정 ㉯).

### 정정 ③ — `REC-01`·`REC-04` 착지가 만든 새 경계

`NextProblemResponse`에 신규 5필드가 실렸다(`weight_axes_applied` · `candidate_pool_size` ·
`weak_concept_signal_count` · `candidate_zero_reason` · `band_calibrated`). **서버는 정직해졌는데
그 정직성이 클라 경계에서 전량 소실된다** → **D7**.

### 고립 대장 (D6 소유)

| 태스크 | 상태(브랜치 기준) | artifact | main 도달 | 소유자 |
|---|---|---|---|---|
| `REC-05-grading-coverage-ceiling` | **done** | `66bfe846` | ❌ EXIT=1 | **`REC-09`** |
| `REC-06-repeat-recommendation-visibility` | todo | — | (구현 없음) | 미착수 — 승계 |
| `REC-07-grading-authority-transfer-decision` | todo · **owner=kiki** | — | (사람 결정) | Kiki — 승계 |
| `REC-08-selective-grading-demotion-gate` | **done** | `1bac33bb` | ❌ EXIT=1 | **`REC-09`** |

> **정직 표기**: 위 `done` 2건은 **브랜치 기준으로 done이고 main 기준으로는 코드가 없다.** 이
> 문서는 그 불일치를 숨기지 않으며 `REC-09`가 유일 소유자다. `next` 실측에서 `REC-07`은
> owner=kiki라 자동 후보에 오르지 않는다(의도된 동작).

### 승계 (변화 없음 — 재대조 생략)

- **v1 §1 기능 80~83 세부 57개** 판정 · **v1 §2 의도적 미채택 9건** · **r2 G1**(채점 권위 자기잠금 —
  `Condition.formal` 파생 가능 문항 0) · **r2 G2**(반복 호출 시 동일 문항 고정) · **r2 G3**(다양성
  발화조건 정정).
- **`irt_difficulty_b` 코퍼스 0건** — JMLE 미실행 지속(재실측). 난이도는 여전히 휴리스틱 폴백.
- **`EXTENDS`(심화) 엣지 0건** — 원자 2,210엣지 전부 `prerequisite`(재실측).
- **`POST /v1/me/attempts` 클라 호출 0** — Flutter `/v1/` 19경로 전수에 부재(r2 시점 13경로에서
  6경로가 늘었으나 **attempts는 여전히 없다**).

---

## §3. 잔여 갭 설계 (D6~D8)

### D6 — r2 완료분 2건이 main에 도달하지 않았다 (최대 갭 · `REC-09`)

**문제**. §0-②가 실측 그 자체다. r2가 설계·구현까지 마친 `REC-05`(채점 가능성 상한 관측)와
`REC-08`(선택형·단답 서버 채점 결함 주입 강등전 — Wilson 게이트 + CI 배선)이 **7일간 main에
존재하지 않았다.** 그 결과 main만 보는 세션에게 이 축은 "아무도 본 적 없는 갭"으로 보이고,
**실제로 이번 r3가 착수 시점에 그 상태였다** — v1만 읽고 시작해 "r2가 없다"는 전제로 출발했다.

**정직한 부분과 아닌 부분을 가른다**. 정직한 부분 — 원 세션은 `backlog.py add` CLI를 경유했고
`done` 전이에 artifact sha를 붙여 규약대로 했다. 그 기록만 놓고 보면 흠이 없다. 정직하지 않게 된
부분 — **그 정직성이 main에서 관측 불가**다. 그리고 이것은 사람의 부주의가 아니라 **도구의 사각**이다:

```
$ python3 scripts/harness/backlog.py validate     →  EXIT=0 (green)
```

`validate`는 `artifacts`의 sha가 **트렁크에 도달했는지 검사하지 않는다.** 즉 "done + artifact 보유"가
"main에 있다"로 무증상 오독된다. 이는 CLAUDE.md **"정본화를 집행으로 착각한 완료 선언 금지"의
대장 평면 변형**이며, 그 규칙이 *"계약을 서빙 코드가 부르는가"*를 묻는다면 여기서 빠진 질문은
*"완료라고 적힌 그것이 트렁크에 있는가"*다.

**핵심 판단(범위 밖 선언)**. 이 문서 커밋은 **문서 + YAML만** 회수했다(코드 0줄 — 시리즈 관례).
구현 2커밋의 회수는 소스 변경이므로 **`REC-09`가 소유**한다. 그리고 **`REC-05`·`REC-08`의 설계를
재도출하지 않는다** — 회수는 승계이지 재설계가 아니다.

**정합 설계** (신규 스키마 0 · 마이그레이션 0 · **신규 태스크 ID 4건 신설 0**)
- **① 파일 체크아웃 회수**(이 커밋에서 완료) — `git checkout FETCH_HEAD -- <문서> <YAML 4건>`.
  cherry-pick이 아니라 파일 단위라 구현 커밋이 섞이지 않는다(`b8608bfd` math-engine 선례).
  **회수는 `backlog.py add`를 거치지 않는다** — 사람이 새 ID를 짓는 행위가 아니므로 HARN-10
  (ID 손편집 금지)에 저촉되지 않는다. 대신 회수 직후 `validate`로 번호 충돌 부재를 확인했다(green·259건).
- **② 구현 회수는 `REC-09`** — 대상 파일이 실측으로 확정돼 있다(`attempt_grading_shadow_report.py` ·
  `selective_grading_demotion_eval.py` · 두 테스트 · `ci.yml`). `REC-02` artifacts가 확립한 회수
  방법론(**cherry-pick → 원 커밋의 테스트 통과 주장을 신뢰하지 않고 독립 재실행**)을 acceptance에 박았다.
- **③ 병렬 세션 조율 선행** — `overlap` 실측에서 `S4-16-residue-gate-demotion-battle`
  (세션 `claude/whymath-ai-content-design-vafylb`)이 `harness/**`를 선언해
  `attempt_grading_shadow_report.py` 1건이 실제로 겹친다. 경고를 넘기지 않고 `REC-09` notes에
  "착수 전 그 세션 상태 확인"을 박았다(2026-07-27 교훈).

**dead code 금지 충족**: 회수 대상은 이미 소비자가 있는 산출물이다(`REC-08`은 CI 배선 포함).
**측정 없는 도입 없음**: 새로 만드는 것이 0이다.
**변별력(양방향)**: 회수 전 `REC-05`~`REC-08` 대장 등재 **0건** → 회수 후 **4건**(실측). 구현 축은
`merge-base --is-ancestor`가 회수 전 **EXIT=1** → 후 **EXIT=0**이어야 한다. 같은 값이면 회수가
일어나지 않은 것이다.

**acceptance 후보** → `REC-09` YAML에 등재된 4항이 정본(요지: ①양방향 도달 확인 ②독립 재검증 ·
exit code 판정 ③Wilson 게이트를 **어떤 잡이 실제로 실행하는지** 확인 ④`REC-06`·`REC-07`·선택형
채점 구현은 대신하지 않는다).

**의존**: 없음(즉시 착수 가능·단 §3-③ 조율 선행). **태스크**: 신설 — `REC-09-r2-isolated-implementation-recovery`.

---

### D7 — 추천 응답의 정직 표기가 **렌더 경계**에서 전량 소실 (`REC-10`)

**문제**. `src/mobile/lib/features/problems/data/problem_models.dart:33-54`의 `NextProblemResponse`는
**원래 5필드만 선언한다**(`problem_id`·`theta`·`difficulty`·`standard_error`·`measurement_sufficient`).
`REC-01`이 추가한 4필드와 `REC-04`의 `band_calibrated` — **신규 5필드 전건 미파싱**이다.
`src/mobile/` 전역 참조 **0건**(부록 A). 더해 파싱하는 `standardError`·`measurementSufficient`조차
모델 파일 밖 **reader 0**이다(부록 B).

결정적 인용 — 같은 파일 주석이 두 원인을 뭉갠다:

```dart
/// [problemId]가 null이면 추천 후보가 없다(측정 충분·또는 미시딩).
```

**서버는 그 둘을 이미 `candidate_zero_reason`으로 구분해 보내고 있다** — `"no_candidate_pool"`
(SQL 후보 조회 자체가 0건 · `api/me.py:1738`)과 `"all_candidates_gated_ineligible"`(후보는 있었으나
L6 게이팅이 전부 부적격 · `:1739`)로. 즉
**값이 없어서 못 하는 것이 아니라, 온 값을 안 받은 다음 모호함을 문서화**한 것이다.

**정직한 부분과 아닌 부분을 가른다**. 정직한 부분 — 서버는 `REC-01` acceptance ②를 그대로
이행했다("'적용 안 됨'과 '적용했는데 신호가 없음'이 구분된다"). 정직하지 않은 부분 — **그 구분이
학생 화면에 한 번도 도달한 적이 없다.** 그리고 이것은 **어느 태스크의 실패도 아니다**:
`REC-01`·`REC-04` 둘 다 `paths`가 backend만이라 렌더 좌석을 구조적으로 볼 수 없었다.
**두 태스크 사이에 소유자가 없는 경계**이며, 회수 전 백로그 전수 grep에서 `candidate_zero_reason`·
`weight_axes_applied`를 보유한 태스크는 **0건**이었다(부록 C).

**핵심 판단(범위 밖 선언)**. 이것은 `learning_path_module_gap_review_r2.md` §9가 세운 원칙 —
*"정직 표기는 그것을 만든 응답 밖으로 나갈 때 함께 가야 한다"* — 의 **추천축 재생산**이다.
학습 경로는 `ordering_basis`가 *파싱은 되는데 읽는 위젯이 0개*였고, 추천은 **파싱조차 안 된다** —
**한 단계 더 이르다.** §9에 회차를 잇되 **새 규칙은 신설하지 않는다**: 기존 원칙이 이미 이 부류를
덮으며, 이번은 규칙 신설 *이후* 다른 평면에서의 재발이다.

**정합 설계** (서버 **0줄** · 신규 API 0 · 신규 상태 0 · 네트워크 호출 추가 0 · 마이그레이션 0)
- **① 파싱 계약 복원** — freezed 모델에 신규 5필드를 `@JsonKey` + `@Default`로 선언. 서버 계약
  불변 · 기존 5필드 회귀 0.
- **② 사유별 문구 분기** — `problemId == null`일 때 `candidate_zero_reason` 값을 **유일한 근거**로
  삼아 서로 다른 중립 문구를 낸다. 기존 메시지 위젯 재사용(신규 화면 0).
- **③ 주석 정정** — "측정 충분·또는 미시딩"을 "서버가 사유를 구분해 보낸다"는 사실로 교체한다.
  **모호함을 문서화한 자리가 이 갭의 발원지**이므로 코드와 함께 고친다.
- **④ 미보정 정직 신호 도달** — `band_calibrated == false`(학습 목적)를 미보정 배지로 노출한다
  (`REC-04` acceptance ③ 승계).
- **⑤ 어조 제약(교수학)** — 문구는 학생의 결손이 아니라 **데이터·시스템의 한계**를 말한다
  (부정적 피드백의 정서적 강화 금지). `candidate_pool_size`·`weak_concept_signal_count` 같은
  **계측 수치를 학생에게 숫자로 노출하지 않는다** — 판단은 사유 라벨로만(`PATH-10` 선례).
- **⑥ 반게임화 선 긋기** — 이 표면에 랭킹·스트릭·카운트다운·보상 연출이 **0임을 테스트로 동결**
  (전역 UI 불변식 2 · `ARCH-26` 기계 게이트).

**dead code 금지 충족**: 추가하는 필드는 전건 즉시 소비 좌석을 갖는다 — 파싱만 하고 안 읽으면
**그것이 바로 이 갭의 재발**이므로 acceptance ③이 기계로 막는다.
**측정 없는 도입 없음**: 서버가 이미 측정해 보내는 값을 렌더할 뿐, 새 지표를 만들지 않는다.
**변별력(양방향)**: `candidate_zero_reason`이 서로 다른 두 값일 때 **위젯 트리 텍스트가 실제로
갈려야** 한다. 갈리지 않으면 이 설계가 실패다. 역방향으로 `problemId != null`인 정상 경로에서는
그 문구가 **나타나지 않아야** 한다.

**acceptance 후보** → `REC-10` YAML 4항이 정본(요지: ①**결함 재현 먼저**(사유가 달라도 텍스트가
같음을 재현하는 widget test) ②본체(5필드 파싱 + 사유별 문구 + 주석 정정) ③**7신호 전수 도달 +
양방향 변별력**, 신호 목록은 사람이 옮겨 적지 않고 **기계가 세게** 한다 ④어조·반게임화 동결 +
서버 변경·수치 노출·개인화 기본값 on·attempt POST 배선은 범위 밖).

**의존**: 없음(`REC-01`·`REC-04` 착지분 위에서 바로 가능). D6와 독립.
**태스크**: 신설 — `REC-10-next-problem-honesty-fields-render`(`layer=mobile`).

---

### D8 — 오프라인 리포트 **면제에 수취인이 없다** (`OPS-34`)

**문제**. `REC-01` acceptance ④는 "리포트를 어떤 잡이 실제로 실행하는지 확인한다(OPS-03·OPS-10 —
'저장소에 존재함'과 '돌아감'은 다르다)"를 요구했다. 그 답은 **by-design 면제**였다 —
`ops/declared_unwired_audit.py`가 `ops.recommendation_reach_report`를 포함한 **16개 산출물**을
`_OFFLINE_REPORT`로 분류한다:

> `by-design:빌드타임 관측 리포트(게이트 아님) — 수치를 보려고 사람이 돌린다. exit 0/2로 머지를
> 막는 판정기가 아니므로 CI 상시 배선 대상이 아니다`

**그런데 그 "사람"에게 돌리라고 지시하는 런북·주기·문서가 0건이다.** `recommendation_reach_report`를
언급하는 문서는 3건뿐이고 **전부 갭 리뷰 문서의 선례 인용**이지 실행 지시가 아니다(부록 G).
CLI(`argparse`)는 실재한다 — 없는 것은 **그것을 돌리는 사람과 시점**이다.

**정직한 부분과 아닌 부분을 가른다**. 정직한 부분 — 면제가 사전에 **명시**돼 있고 사유가 적혀
있다(침묵 통과가 아니다). 이 저장소는 이미 "미도달 *수*가 아니라 *미분류*가 실패다"라는 옳은
판정 규약을 갖고 있다. 정직하지 않은 부분 — **만료도 수취인도 없는 영구 면제**다. CLAUDE.md
**"만료 없는 유예·제외 금지"**(2026-08-03) 직접 저촉이며, 운영 r3 D9가 세운 논리 —
*"정직 표기는 침묵 통과는 막지만 영구 미상환은 막지 못한다"* — 의 **면제 사전 평면 재발**이다.

**핵심 판단(범위 밖 선언)**. 이 갭은 **추천축이 아니라 횡단 인프라축**이다 — 면제 16항 중 추천
관련은 2건뿐이다. 따라서 **추천 전용의 좁은 태스크를 만들지 않는다**(16건 중 2건만 고치는 것은
중복 등재의 씨앗). `infra-debt` 트랙으로 등재하고, **`OPS-29`에 의존을 건다**: `OPS-29`가
`ci.yml` 비차단 스텝에 이식하려는 분류·만료 계약(`ARCH-25` GrandfatherEntry 유래)과 **같은 계약**이며,
**세 곳에서 같은 만료 판정을 굴리면 이중 진실원천**이기 때문이다. `OPS-34`의 실체는 새 계약이
아니라 **`OPS-29` 계약의 대상 축 추가**다.

**중복 검사 실측**(등재 전 필수 확인 — 통과):
- `OPS-29`의 대상은 `ci.yml`의 `continue-on-error`/`|| true` 스텝이다(`paths: .github/workflows/ci.yml`).
  **면제 사전은 대상이 아니다.**
- `OPS-30`(알림 마지막 1홉)·`OPS-31`(백업 암호화·오프사이트)은 완전히 다른 축이다.
- `OPS-32`(의존성 선언↔사용)는 acceptance ⑤에서 "declared_unwired_audit의 5번째 축" 가능성을
  언급하나 **대상이 pyproject 의존성**이지 면제 사전이 아니다.

**정합 설계** (신규 계약 발명 0 · 신규 스키마 0)
각 `_OFFLINE_REPORT` 항목이 **수취인**을 선언하게 한다 — `runbook:<경로#앵커>` /
`report-schedule:<주기>` / `pending-task:<id>`. 선언 없는 항목은 **미분류 exit 1**.
`pending-task:<id>`는 태스크가 실재하고 `status != done`일 때만 유효하며, done인데 남아 있으면
red(= 면제를 걷으라는 신호). 착지는 `tests/infra/`(`infra-contracts` 잡이 이미 전량 실행하므로
CI 배선 확인은 그 사실 확인으로 충족).

**dead code 금지 충족**: 면제 사전은 이미 실동작하는 감사기의 일부다 — 필드 하나를 요구할 뿐이다.
**측정 없는 도입 없음**: 새 지표 0 · 새 실행 0(리포트를 CI로 승격하지 **않는다**).
**변별력(양방향)**: 수취인 선언 없는 항목 1건을 주입하면 **red**, 되돌리면 **green**을 둘 다 실측.

**acceptance 후보** → `OPS-34` YAML 4항이 정본(요지: ①현행 실측 고정 ②수취인 3종 선언·미선언
exit 1 ③**`OPS-29` 계약 코드 재사용·재구현 0** ④양방향 변별력 + CI 상시 승격 금지).

**의존**: `OPS-29`(계약 코드 원본). **태스크**: 신설 — `OPS-34-offline-report-recipient-contract`.

---

### 페이퍼 갭 (**코드 0 · 태스크 신설 없음**)

- **기능 82(학습 시간 추천)** — v1 D5를 **그대로 승계**한다. 세부 8개 중 6개는 §5에서 미채택이고
  남는 둘(간격·개입 시점)은 `S4-18`(done) · `S3-16`(done)이 소유했다. 시간축에서 정본이 인정하는
  축은 **분량이 아니라 간격**이라는 결론은 그대로다. r2가 단 부기 — "간격 축의 입력(BKT 숙달)도
  `problem_attempt` 0행이라 시간축 전체가 같은 상류 잠금 아래에 있다" — 도 유효하다.
- **r2 G2(반복 추천 고정 반환)** — `REC-06`이 회수돼 대장에 올랐고 todo다. **승계이며 재설계하지
  않는다.** 신규 등재 0.

---

### §3 등재 요약

| 태스크 | 설계 | owner | stage | prio | layer | 근거 |
|---|---|---|---|---|---|---|
| `REC-09-r2-isolated-implementation-recovery` | D6 | claude | S3 | 2 | backend | r2 완료 2건이 main 미도달 · `validate`가 green으로 통과 |
| `REC-10-next-problem-honesty-fields-render` | D7 | claude | S3 | 3 | **mobile** | 신규 5필드 파싱 0 · 기존 2필드 reader 0 · 소유 태스크 0 |
| `OPS-34-offline-report-recipient-contract` | D8 | claude | S4 | 3 | infra | 면제 16항에 수취인·만료 0 · `OPS-29` 계약 재사용 |
| `REC-05`·`REC-06`·`REC-07`·`REC-08`(회수) | r2 G1~G2 | claude/**kiki** | S3 | 2 | backend | **승계·재설계 금지** — 회수이지 등재가 아니다 |
| `REC-01`~`REC-04`·`NLP-02`·`S4-18`·`S3-16`·`S4-15`·`S3-01`·`ARCH-19`·`PATH-*`(기존) | — | — | — | — | — | **승계·재설계 금지** |

태스크는 전건 `backlog.py add` CLI 경유로 등재했다(ID 손편집 0 · 번호 충돌은 CLI가 로컬+원격 양쪽
검사 — HARN-10). `--path` 선언으로 겹침 검사를 켰다. **`validate` green 262건**(회수 전 255 →
회수 후 259 → 등재 후 262).

**CLI 거부 1건 실동작 기록**: `OPS-33`으로 시도했으나 CLI가 원격 `OPS-33-yaml-spec-unwired-audit-axis`와의
번호 충돌로 **거부**하고 `OPS-34`를 제안했다. **우회하지 않고 제안 번호를 수용**했다(CLAUDE.md
"거부의 우회 금지"). 부기 — 그 충돌 상대 브랜치(`claude/whymath-knowledge-design-4rxrax`)는 현
`git ls-remote --heads origin` 목록(47 refs)에 **없다**. 스캔과 브랜치 삭제 사이의 경합으로 보이나
**재시도하지 않았다** — 거부는 판정이지 장애물이 아니며, 번호 하나를 아끼려고 우회하는 것이
HARN-10이 막으려는 바로 그 행동이다.

---

## §5. 의도적 미채택 — v1 §2 **9건 + r2 1건 전건 승계** + 신규 1건

v1 §2 9건(단일 Engine 컴포넌트 · 협업 필터링 · SM-2/FSRS · `learning_session` writer · 집중·피로
라벨 · `similar_to` traversal · 성장곡선·목표점수 예측 · 주간 스케줄·하루 학습량 · 별도 AI 난이도
예측 모델 · 학습 스타일)과 r2가 유지한 판정은 **전건 승계**한다. **재검토 트리거가 발생한 항목이
하나도 없다.**

| # | 문서 제안 | 불채택 근거 |
|---|---|---|
| **⑪**(신규) | **추천 ↔ 게임화(75~79) 연동** — 「WhyMath에서의 역할」이 주장하는 4방향 중 하나 | **전역 UI 불변식 2(반게임화)와 정면 충돌.** 추천 신호를 게임화 표면에 잇는 순간 "무엇을 몇 개 더 풀었는가"가 노출 축이 되고, 이는 CLAUDE.md 금기 "학습 시간·정답률만으로 우열을 매기는 게임화 금지"·"무자비한 게임화·중독성 설계 금지"에 직접 닿는다. `ARCH-26`이 랭킹·스트릭·카운트다운·보상 연출을 **소스 스캔 기계 게이트**로 이미 금지하고 있어, 이 연동은 규범을 어길 뿐 아니라 **CI에서 red가 된다**. 성장의 증거는 게임화가 아니라 `PED-06` 노출 계약이 다루는 축이다 |

---

## §6. 정직한 공백 갱신 (v1 §4 9종 · r2 §4 5종 재판정)

| v1·r2 항목 | 2026-08-11 재판정 |
|---|---|
| v1 §4-① 심화(`EXTENDS`) 엣지 0건 | **유지** — 원자 2,210엣지 전부 `prerequisite`(재실측). "구현 안 함"이 아니라 **적재 안 됨** |
| v1 §4-② 보충(병렬 보강) 축 없음 | **유지** — 관계 타입 5~8개 제한 안에서 새 타입을 열 근거가 아직 없다 |
| v1 §4-③ 오답 유사 문제 재료 비어 있음 | **유지** — 계보 좌석 둘 다 writer 0(v1 §5-⑤ 발화조건 대기) |
| v1 §4-④ 시험 대비 "세트" 없음 | **유지** — 단건 추천이 검증되기 전에 열지 않는다 |
| v1 §4-⑤ DKT·협업 필터링 Phase 3+ | **유지** — `S3-01` todo(§7-③) |
| v1 §4-⑥ BKT 4파라미터 EM 미적합 | **유지** — 실응답이 필요하고 그것이 `REC-07` 잠금이다 |
| **v1 §4-⑦ `persona_fit` 전 문항 `{}`** | **삭제(해소)** — 2,643/2,643(100%) 적재 · 수능 사전필터 소비 중. **단 추천 가중 축 배선은 여전히 0**이므로 공백이 *이동*했다 → §7-⑪ |
| v1 §4-⑧ "다양성" 축 없음 | **유지** — r2 G3가 조건을 정정했다(D4 착지 ∧ **학생 축 노출 이력원 실재**, 후자 미충족) |
| v1 §4-⑨ ClickHouse 클라 코드 0 | **유지** |
| r2 §4-1 선택형 서버 채점 *구현* 안 함 | **유지** — 측정(`REC-05`) → 사람 결정(`REC-07`) → 구현 순서를 바꾸지 않는다 |
| r2 §4-2 `Condition.formal` 백필 안 함 | **유지** — 검수 없는 기계 생성은 거짓 pass/fail의 근원 |
| r2 §4-3 정답 위치 편향 = `ARCH-19` 승계 | **유지** |
| r2 §4-5 `REC-02` 범위 미접촉 | **해소** — `REC-02`가 main에 done으로 착지(§2 정정 ①) |
| **신규** | **`irt_difficulty_b` 코퍼스 0건 지속** — JMLE가 한 번도 돌지 않아 난이도는 항상 휴리스틱 폴백이다. 적합에는 실응답이 필요하고 그것이 `REC-07` 잠금이라 **새 태스크를 만들지 않는다**(`S4-15` 소유) |

---

## §7. 유보 항목의 발화 조건 갱신 (v1 §5 8건 + r2 ⑨)

| # | 유보 항목 | 2026-08-11 상태 |
|---|---|---|
| ① | 클라 attempt 제출 배선 | **트리거 무효 유지**(r2 G1) — 새 경로 = `REC-05` 측정 → `REC-07` 사람 결정. **단 `REC-05`가 main에 없었으므로 그 경로도 7일간 정지 상태였다** → `REC-09`가 해제 |
| ② | 개인화 기본값 on 전환 | **미발화 유지**(attempt 0행) |
| ③ | 협업 필터링·DKT | **미발화 유지**(`S3-01` todo) |
| ④ | 심화 개념 추천 | **미발화 유지**(`EXTENDS` 0건 재확인) |
| ⑤ | 오답 유사 문제 추천 | **미발화 유지**(계보 writer 0) |
| ⑥ | 밴드 임계 보정 | **미발화 유지** — `band_calibrated=false`가 서버에서 정직 표기 중. **단 그 표기가 클라에 도달하지 않는다** → D7 |
| ⑦ | bandit 승격 | **미발화 유지**(결합 축 부재 — §1-B 학습분석 행) |
| ⑧ | 다양성 제약 | **미발화 유지** — r2 G3 정정 조건(ⓐ D4 착지 ∧ ⓑ 학생 축 이력원 실재) 중 ⓑ 미충족 |
| ⑨ | 선택형 서버 채점 권위 이관 | **미발화 유지** — `REC-07`(owner=kiki)이 대장에 회수됐고 `depends_on`(`REC-05`·`REC-08`)이 둘 다 done이라 **의존은 해소 상태**이나, 그 done의 코드가 main에 없다(D6). `REC-09` 착지가 실질 선행 조건이다 |
| **⑩**(신규) | **r2 완료분 구현 회수** | `REC-09` 착수. 선행 조율 — `S4-16` 세션과 `attempt_grading_shadow_report.py` 겹침 확인 |
| **⑪**(신규) | **`persona_fit`을 추천 *가중 축*으로 배선** | **데이터 전제는 충족됐다**(100% 적재). 그러나 ⓐ 개인화 가중 자체가 기본 off이고 ⓑ 적합도 임계·가중 계수를 정할 실응답이 0이라, 지금 다는 것은 "측정 없는 도입"이다. 트리거 = **`REC-07` 결정으로 attempt가 쌓이기 시작하고 `S4-15` 보정 루프가 열릴 때.** 그전까지 `persona_fit`은 *자격 조건*(수능 사전필터)으로만 쓴다 |

---

## §정정 — v1·r2 stale (원본을 수정하지 않고 여기에만 기록)

| # | 위치 | 기존 기술 | 2026-08-11 실측 |
|---|---|---|---|
| ㉮ | v1 §4-⑦ | "`persona_fit`이 전 문항 `{}`다 — 추천 가중으로 쓰는 축이 실질 무효" | **2,643/2,643(100%) 보유.** 무효인 것은 데이터가 아니라 **가중 배선**이다 — 원인 지목이 한 칸 어긋나 있다 |
| ㉯ | r2 §4-④ | "`EXTENDS` 엣지·`problem_relation` writer·`persona_fit`은 1차 §4 그대로다. 재실측에서 변화 없음" | **`persona_fit`만 틀렸다.** `S3-10` 재실행(2026-08-07)이 r2 작성 **3일 뒤**에 적재를 끝냈다. `EXTENDS`·`problem_relation`은 r2 기술이 유효 |
| ㉰ | r2 §0 표 | "`REC-02`(D2 프로브 공급) **todo** — 타 세션 claim 중" | **done**(2026-08-08 main 착지 · `harness/wh1_probe_supply.py`). v1 §정정이 `REC-02`에 접어둔 `probe_selection.py:24` stale 주석의 처분도 그 착지에 포함됐는지는 **`REC-09` 착수 세션이 확인**한다 |
| ㉱ | 시리즈 명명 규약 | v1 `_gap_review.md` · r2 `_gap_review_2.md` | `_r{n}`이 현행 다수·최근 신규 전량. **본 문서부터 `_r{n}`으로 정렬**하며 r2 파일명은 참조 무결성 때문에 개명하지 않는다(§0-①) |

**㉮·㉯의 원본 수정을 하지 않는 이유**: v1·r2 본문은 **판정 시점의 기록**이며, 덮어쓰면 "왜 그
순서로 잠갔는가"가 사라진다(시리즈 규약). 특히 r2는 **이 커밋에서 main에 처음 착지하는 문서**라
2026-08-04의 상태를 그대로 보존하는 것이 회수의 의미다. 정정 사실은 여기에 남고 §6·§7이 소유한다.

---

## §9. 반복 실수 — **10회차** 등재

v1 §6(4~6회차) → r2 §6(7회차) → `learning_path r2` §9(9회차)로 이어진 표를 **10회차**로 잇는다.

| 회차 | 사례 | 형태 |
|---|---|---|
| 1 | `tests/infra` 199건 미실행(OPS-03) | 만들고 **CI에 배선 안 함** |
| 2 | 시각화 스택 도달 0회(VIZ-01) | 만들고 **적재 안 함** |
| 3 | OCR 전 파이프라인 비활성(NLP-01) | 만들고 **배포에 넣지 않음** |
| 4 | attempt POST 클라 호출 0(v1 D1) | 만들고 **입력을 잇지 않음** |
| 5 | 개인화 기본 off·개념 API 소비 0(v1 D1) | 만들고 **켜지 않음** |
| 6 | `select_probe` 후보 공급원 0(v1 D2) | 만들고 **공급원을 잇지 않음** |
| 7 | shadow 채점의 파생 가능 문항 0건(r2 G1) | 만들고 **재료가 0인 경로를 골랐음** |
| 8 | 학습경로 정렬 알고리즘이 기본값에서 96.4% 무력 | 만들고 **돌아는 가는데 무력** |
| 9 | `ordering_basis` 정직 표기가 영속·렌더 경계에서 소실(`learning_path r2` D4·D5) | 만들고 **응답 밖으로 못 내보냄** |
| **10** | **r2 문서·태스크·구현이 main 미도달 · `validate`는 green**(D6) | 만들고 **트렁크에 넣지 않음 — 그리고 대장이 그것을 못 본다** |

**10회차가 앞의 아홉과 다른 점**: 1~9는 전부 **코드·데이터 평면**의 사고였다. 10회차는
**대장(ledger) 평면**이다 — 만든 것도 정직했고, 기록도 규약대로였고, `validate`도 green이었다.
그런데 **그 전부가 트렁크 밖에 있었다.** 앞의 아홉을 잡아낸 장치들(도달 리포트·`declared_unwired_audit`·
정직 표기)은 전부 **트렁크 안에서 동작하는 검출기**라, 트렁크에 도달하지 못한 것은 구조적으로
볼 수 없다.

**남길 원칙**: **"done은 브랜치의 속성이 아니라 트렁크의 속성이다."** `artifacts`에 sha를 적는
것으로 완료가 성립하지 않는다 — 그 sha가 트렁크 조상인지가 완료의 정의다. 9회차 원칙("정직 표기는
그것을 만든 응답 밖으로 나갈 때 함께 가야 한다")의 **대장 평면 대응**이며, 둘 다 같은 형태다 —
**만든 자리에서는 참인데 한 겹 바깥에서 거짓이 된다.**

**재발방지 등재 형태**: 이 회차는 **새 규칙을 CLAUDE.md에 신설하지 않는다.** 기존 규칙
"정본화를 집행으로 착각한 완료 선언 금지"(2026-08-04)가 이 부류를 이미 덮으며, 필요한 것은 규칙이
아니라 **기계 검출**이다 — `validate`가 `artifacts` sha의 트렁크 도달을 검사하지 않는다는 사실이
D6 §문제에 실측으로 기록돼 있고, 그 검출기의 소유는 하네스 축(`HARN-*`)이다. **이 문서는 그
사실을 등재하되 하네스 태스크를 대신 만들지 않는다**(중복 등재 금지 — 미머지 고립 탐지는 이미
SessionStart 브리핑이 부분적으로 수행하고 있고, 그 브리핑이 `tv1f08`을 놓친 이유(최종 커밋 3일
이내라 임계 미달)까지 포함한 재설계는 하네스 소유자의 판단이다).

---

## §10. 실행

### 신규 등재 (3건 · 전건 `backlog.py add` CLI 경유)

| 태스크 | stage/prio | 설계 |
|---|---|---|
| `REC-09-r2-isolated-implementation-recovery` | S3 / 2 | D6 |
| `REC-10-next-problem-honesty-fields-render` | S3 / 3 | D7 |
| `OPS-34-offline-report-recipient-contract` | S4 / 3 | D8 |

### 회수 (등재가 아님 · `git checkout` 경유)

`docs/architecture/ai_recommendation_module_gap_review_2.md` + `REC-05`·`REC-06`·`REC-07`·`REC-08` YAML 4건.

### 기존 태스크 수정 — **없음**

`REC-01`·`REC-03`·`REC-04`는 전건 done이다. **완료 태스크의 판정 근거를 소급 변조하지 않는다.**
`persona_fit` 정정은 이 문서 §정정 ㉮·㉯만 보유한다. 회수된 `REC-05`~`REC-08`도 **무수정**이다.

### 게이트 등재 — **없음**

`REC-07`(채점 권위 이관 결정)이 **owner=kiki로 회수**되어 사람 결정 좌석이 이미 대장에 있다.
별도 `gates.yaml` 항목을 만들면 같은 결정을 두 곳에서 추적하게 된다(중복). `next` 실측에서
`REC-07`이 자동 후보에 오르지 않음을 확인했다.

### 중복 등재 금지 대장

| 주제 | 기존 소유자 |
|---|---|
| 선택형 서버 채점 커버리지 관측 | `REC-05`(회수·done) |
| 반복 추천 고정 가시화 | `REC-06`(회수·todo) |
| 채점 권위 이관 **결정** | `REC-07`(회수·owner=kiki) — **게이트 신설 안 함** |
| Wilson 게이트·결함 주입 강등전 | `REC-08`(회수·done) |
| 추천 처치 ↔ 결과 결합 / 학습분석 rollup 연동 | `REC-03` acceptance ④(범위 밖 동결) + `S3-01` |
| 오개념 프로브 공급 | `REC-02`(done) |
| 밴드 임계 보정 · 실응답 난이도 통계 | `S4-15` |
| `EXTENDS` 엣지 적재 | v1 §4-① 정직한 공백 |
| `irt_difficulty_b` JMLE 실적합 | `S4-15` |
| 정답 위치 편향 게이트 | `ARCH-19` |
| `ci.yml` 비차단 스텝 강제 선언 | `OPS-29` (`OPS-34`가 의존) |
| 런북 자인 공백 25종 · 알림 마지막 1홉 | `OPS-30`·`OPS-31` |
| 백엔드 의존성 선언↔사용 축 | `OPS-32` |
| 학습 경로 정렬 정직 표기(영속·렌더) | `PATH-09`·`PATH-10` |
| `persona_fit` 추천 가중 축 | **미등재가 의도** — §7-⑪ 발화 대기(측정 없는 도입 없음) |
| 게임화 연동 | **§5-⑪ 의도적 미채택** |
| 학습 시간 추천(기능 82) | v1 D5 페이퍼 승계 |
| `artifacts` sha의 트렁크 도달 검사 | **하네스 축 소유** — §9 참조, 이 문서가 대신 등재하지 않음 |

---

## 부록 — 실측 근거 (2026-08-11 실측)

브랜치 `claude/whymath-ai-recommendation-review-rcign3` · 기준 HEAD `d088ae77` ·
고립원 `origin/claude/whymath-ai-recommendation-review-tv1f08` @ `fdf46d7b`.

```bash
# A. REC-01·REC-04 신규 5필드의 Flutter 참조 (기대: 0)
grep -rn 'weight_axes_applied\|candidate_pool_size\|weak_concept_signal_count\|candidate_zero_reason\|band_calibrated' src/mobile/ | wc -l
#   → 0

# B. 기존 2필드의 모델 파일 밖 reader (기대: 0)
grep -rn 'standardError\|measurementSufficient' src/mobile/lib/ | grep -v 'problem_models' | wc -l
#   → 0

# C. 신규 5필드를 보유한 태스크 (회수·등재 전 기대: REC-04 1건만)
grep -rl 'candidate_zero_reason' backlog/tasks/
#   → 등재 후 REC-10 유일. weight_axes_applied·candidate_pool_size·weak_concept_signal_count는
#     등재 전 전 태스크에서 0건이었다(= 소유자 없는 경계)

# D. v1이 §1의 두 축을 대조한 적 없음 (기대: 0)
grep -c '학생 프로필\|게임화 75\|학습분석 32' docs/architecture/ai_recommendation_module_gap_review.md
#   → 0

# E. AI Tutor ↔ 개념 추천 연동만 실재 (기대: 사슬 전건 히트)
grep -n '_prerequisite_coaching_for' src/backend/whymath_backend/api/coach.py
#   → :969(정의) · :1766(호출)

# F. 학습분석 rollup이 추천 처치를 읽지 않음 (기대: 0)
grep -c 'evidence_event\|recommendation_evidence' src/backend/whymath_backend/l2/learning_metrics_rollup.py
#   → 0

# G. 오프라인 리포트 면제 16항 · 실행 지시 런북 0
grep -c '_OFFLINE_REPORT,' src/backend/whymath_backend/ops/declared_unwired_audit.py
#   → 16
grep -rl 'recommendation_reach_report' docs/
#   → 3건(ai_recommendation_module_gap_review_2.md · solution_module_gap_review_r3.md ·
#     data_platform_module_gap_review.md) — 전부 갭 리뷰의 선례 인용, 실행 지시 런북 0

# H. r2 고립 (기대: EXIT=1)
git merge-base --is-ancestor origin/claude/whymath-ai-recommendation-review-tv1f08 origin/main; echo "EXIT=$?"
git merge-base --is-ancestor 66bfe846 HEAD; echo "REC-05 code EXIT=$?"   # → 1
git merge-base --is-ancestor 1bac33bb HEAD; echo "REC-08 code EXIT=$?"   # → 1

# I. 대장이 고립을 못 본다 (회수 직후 · 기대: green)
python3 scripts/harness/backlog.py validate; echo "EXIT=$?"
#   → ✔ green 259건 · EXIT=0  (REC-05·REC-08이 done인데 sha가 main 조상이 아닌 채로)

# J. 코퍼스 재실측 (data/corpus/problem_bank*/**/*.jsonl 전량 파싱)
#   문항 2,643 / persona_fit 보유 2,643(100%) / difficulty_overall 2,643(100%)
#   distractor_map 1,615 · 오개념 id 64종 / irt_difficulty_b 0건
#   atom_graph_v1/graph.json — concepts 2,683 · edges 2,210 (전부 prerequisite · EXTENDS 0)

# K. Flutter가 호출하는 /v1/ 경로 전수 (19종 · 기대: /v1/me/attempts 부재)
grep -rnoE "'/v1/[^']*'" src/mobile/lib --include=*.dart | sed "s/.*'\(\/v1[^']*\)'/\1/" | sort -u
#   → auth/{$provider/callback,logout,refresh,sessions,sessions/$id} · coach{,/sessions,...}
#     · interactions · me/diagnosis/concepts · me/next-problem
#     · me/weak-concepts/$conceptId/learning-path · ocr · problems/$problemId
#     · reports/defects · scenes/weak-concept · users/me · verify-solution
#   → POST /v1/me/attempts 부재 (v1 실측 13종 → 19종으로 늘었으나 attempts는 여전히 없다)

# L. 백로그 규모 전이
#   회수 전 255 → 회수 후 259(REC-05~08) → 등재 후 262(REC-09·REC-10·OPS-34) · validate green
```

**추천 응답 신규 필드 정본**(D7 대상): `src/backend/whymath_backend/api/me.py`
`NextProblemResponse` — `weight_axes_applied`(적용 가중 축 목록) · `candidate_pool_size` ·
`weak_concept_signal_count`(약점 가중이 중립 1.0이 아니게 된 문항 수) ·
`candidate_zero_reason`(`"no_candidate_pool"` / `"all_candidates_gated_ineligible"` — 상수 정의
`api/me.py:1738-1739`) · `band_calibrated`(REC-04 · `purpose=learning`일 때만 False).

**클라 대상 좌석**(D7): `src/mobile/lib/features/problems/data/problem_models.dart:33-54`
(`NextProblemResponse` freezed 모델 · 주석 `:30-31`이 두 원인을 뭉갠 자리).
