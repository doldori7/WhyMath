# 풀이(Solution) 엔진 모듈 — 외부 EOS 틀 3차 대조(R3) 갭 점검·설계 (2026-08-11)

> **범위**: 외부 참고 문서 『06. 풀이(Solution)』(기능 23~27: 단계별 풀이 생성 · 다양한 풀이법
> 생성 · 힌트 생성 · AI 채점 · 풀이 비교 — **WhyMath 전용이 아닌 일반 EOS 틀**, Kiki 제공)의
> **3차 제출**에 대한 대조 기록. 1·2차는 `solution_module_gap_review.md`(2026-07-29 · 2026-08-03)에
> 있고 **이 문서는 그것을 수정하지 않는다**(§0-② 참조).
>
> **결론 한 줄**: 기능 판정은 **뒤집기 0**이고 D6(`S4-19`)는 **완결**됐다. 그런데 이 모듈의
> 최대 갭은 더 이상 "안 만든 기능"이 아니다 — **D1 완료분 2,153줄이 병합되지 않아 main에 없고**
> (미병합 고립 4회차), **테스트가 양쪽 다 초록인 채 학생 도달이 0인 죽은 사슬**(`step_panel`)이
> 가동 중인 서빙 표면에 박혀 있으며, **그 두 유형 모두 선언≠배선 탐지기의 사각**이다.
> 신규 설계 R1~R4, 백로그 등재 3건(`SOL-01`·`SOL-02`·`SOL-03`), 원본 정정 3건.
>
> **실측 기준**: HEAD `959ec4ad` (2026-08-11).

관련 정본: `solution_module_gap_review.md`(1·2차 — D1~D6 정본) ·
`03_content_generation.md`(SolutionPath·동치성 정직 경계) · `03b_wh_s_solver_harness.md` ·
`04_pedagogy_engine.md`·`04a_wh1_tutoring_harness.md`(답 미루기·힌트 경제) ·
`05a_learning_scene_dsl.md`(scene DSL) · `problem_bank_gap_review_r2.md`(§0 고립 실측 선례).

---

## §0. 재점검 사유 — 왜 3차를 새로 쓰는가

### ① 동일 문서 3차 제출임을 확정한다 (추론 아님)

제출된 `.docx`의 기능 번호(23~27)·제목·표 구조·「WhyMath 전체 구조에서의 위치」·「EOS 관점
에서의 연계 구조」 2절이 1·2차 대조 대상과 **동일**하다. 1차는 기능 23~27을, 2차는 그 2절
(배선 축)을 추가로 crosswalk 했다 — **문서 쪽에 새 표면은 남아 있지 않다**.

따라서 R3의 일은 문서를 다시 읽는 것이 아니라 **코드 쪽 8일치 델타를 읽는 것**이다.
그 델타가 내놓은 것이 §3이다.

### ② 원본을 in-place 수정하지 않는 이유

`problem_bank_gap_review_r2.md`(2026-08-03)·`gamification_module_gap_review_r2.md`(2026-08-04)가
확립한 규약을 따른다 — **원본 비수정 + 별도 파일**. 근거 3가지:

- 원본은 이미 408줄·41KB이고 1차(§1~§4)와 2차(§5)가 층으로 쌓여 있다. 3차를 in-place로
  섞으면 "어느 판정이 언제 것인지"가 무너진다.
- 판정 **뒤집기가 0**이라 덮어쓸 내용 자체가 없다. 덮어쓰면 오히려 1·2차의 실측 시점 정보가
  소실된다.
- 원본의 stale 지점은 §정정에 **기록**한다(수정이 아니라 델타 — gamification r2 §4 동형).

원본에는 이 문서로 오는 포인터 1줄만 추가한다.

### ③ 승계 선언 — 재판정하지 않는 것

- **설계 D1~D5**(원본 §3) — 전건 유효. 재설계 0.
- **의도적 미채택 6건**(원본 §2) — 전건 승계. 재론 0. (§2에 재확인만)
- **잔여 연동 트리거 6종**(원본 §4) — 전건 승계. 발화 조건 갱신은 §6.
- **`S4-09`~`S4-12` acceptance** — 수정하지 않는다. R3가 만드는 것은 *그것을 막고 있는 것*을
  치우는 태스크뿐이다.

---

## §1. 기능 23~27 재대조 — 바뀐 칸만

| 기능 | 2차 판정 | R3 재실측 | Δ |
|---|---|---|---|
| **23** 단계별 풀이 | 생성·검증 ✅ / 구조 좌석 ⚠️ D1 | `ProblemStep(` 생성자 호출이 **프로덕션 0건**(테스트 2곳만) → `GET /v1/problems/{id}/steps`(`api/problems.py:127`)는 **영구 빈 배열 리더**. `SolutionStep`·`Justification` 클래스 자체가 코드에 없고 `solution_path.schema.yaml` 헤더가 "상태: 명세 단계 / 검증 invariant(명세 — 테스트 미구현)"로 자인. `scene_generation.py:23` 자인 잔존 | 없음 (단 §3-① 고립이 원인임이 확정) |
| **24** 다양한 풀이법 | 설계만·소비 0 | `ApproachType` enum 부재 유지. `multi_solution_gen.md:28` "비유적" ↔ 스키마 `visual` 불일치 잔존. **추가 실측**: 프롬프트 자산 로더 `l3/prompt_assets.py:77-80` `_PROMPT_FILES`가 4종(`l3_equivalent_gen`·`l3_rephrase`·`l3_visualization`·`l3_cross_verify`)만 로드 — `multi_solution_gen.md`는 **로드조차 안 된다** | 없음 (D2 진입점 1개 추가 확인) |
| **25** 힌트 | 레벨 결정 ✅ / 내용 ⚠️ D3(최대 실행 갭) | `polya/engine.py:88` `sp = STAGE_PROMPTS[target_stage]` — 문제·단계 무관 정적 템플릿 4개(`polya/prompts.py:42/54/68/76`)가 **실제 발화 경로**임을 재확인. `hints` 테이블 0 · `HintNode`/`Hint` 클래스 0 · `reveal_score` 전 저장소 grep **0건** | 없음 |
| **26** AI 채점 | 강함 ✅ / D6 갭 | **D6(`S4-19`) 착지 완료**(2026-08-10 `a7a57b59` #760): `VerifyEventData`에 `n_correct`·`n_incorrect`·`n_unverifiable`·`unverified_ratio`·`first_incorrect_index`·`ocr_gated` additive(`event_data_contract.py:73+`) + reader 병기(`wh1_evaluation.py:1864-1941` `step_decision_rate`·`step_incorrect_rate`·NO_DATA 경로) + 노출 집행(`surrogate_baseline_report.py:31,254-262` — `SurrogateMetrics` 비확장) 전부 실측 확인 | ✅ **해소** |
| **27** 풀이 비교 | 없음(코드 0) | `solution_compar`·`compare_solution`·`계산량`·`직관성`·`일반성` 전건 `src/`·`schemas/` 매칭 **0**. `equivalence_cluster_id`·SolutionPath `embedding`·`preferred_solution_style` 전부 스키마만. `solution_embedding` pgvector 테이블 없음(문제/개념/원자/오개념 4종만 실재) | 없음 |

**판정 뒤집기 0.** 원본 §1의 기능 26 D6 행만 ✅로 닫힌다.

### §1-1. 배선 축(원본 §5-2) 재대조

| 문서 엣지 | 2차 판정 | R3 재실측 | Δ |
|---|---|---|---|
| 교육과정·개념 DB → 풀이 | ✅ | 변화 없음 | 없음 |
| 오개념 DB → 풀이 | ✅ (reactive·preload 금지 준수) | `l4/misconception/` ~40파일 유지 | 없음 |
| 문제은행 → 풀이 | ✅ | WH-S `run_solver`(`whs/harness.py:422`) 유지. **정책 실구현은 여전히 `ScriptedPolicy`(테스트)·`ChainReplayPolicy`(재생)뿐 — LLM `SolverPolicy` 구현체 0** | 없음 (§4-③ 트리거 유지) |
| 교수전략 → 풀이·힌트 | ⚠️ D3가 덮음 | 변화 없음(정적 템플릿) | 없음 |
| 채점 → 학생 모델 | ⚠️ D6 | **해소**(`S4-19`) | ✅ |
| 풀이 비교 → 학생 모델 | ⏸ | `preferred_solution_style` 코드 0 유지 | 없음 |

**신규 엣지 1건 발견** — 문서 다이어그램에는 없지만 코드에는 있는 축:
`풀이 → 학습 장면(LearningScene) → 학생 클라이언트`. 이 엣지가 §3-②의 죽은 사슬이다.

---

## §2. 의도적 미채택 — 원본 §2 6건 전건 승계

재론하지 않는다. 근거는 원본 §2 그대로다.

| # | 문서 제안 | 승계 |
|---|---|---|
| ① | 학생 대면 점수·부분점수·등급 | 승계 — 정본 대체 좌석은 3상태 판정 + BKT/IRT 숙달도 |
| ② | 초등 그림→대학 증명 4단 수준축 | 승계 — 단 근거 문구를 §정정 ㉮로 정밀화 |
| ③ | AI 생성 풀이·힌트의 무검증 노출 | 승계 — 단 집행 지점을 §정정 ㉰로 명확화 |
| ④ | 동치 자동 확정·"최적 풀이" 자동 선정 | 승계 |
| ⑤ | 힌트 유형 6종 신규 분류 enum | 승계 — 기존 3축 crosswalk(원본 §3 D3 표) 유효 |
| ⑥ | 표현·서술 감점형 채점 | 승계 |

---

## §3. 신규 갭 — 실측

### ① 최대 갭 — D1(`S4-09`) 완료분이 13일째 고립 (미병합 고립 **4회차**)

`claude/whymath-solution-review-40xspg`는 2026-07-29 `c4de268a`(= 1차 갭리뷰 PR #635)에서
분기했고, **공통 조상이 소실됐다**(`git merge-base` **exit 1** · trunk 657커밋 앞섬).

| 커밋 | 내용 | 상태 |
|---|---|---|
| `054f8f11` | S4-09 착수(claim) | — |
| `86212c43` | **S4-09 구현 완료** — 20파일 2,153줄 | **main에 없음** |
| `022140cb` | S4-09 done 기록 | 고립 브랜치 YAML에만 |
| `21e35d28`·`707c5665` | S4-10 WIP — 알려진 실패 1건 | 미완 |

`86212c43`이 만든 것(전부 main 부재): `l3/solution_path.py` 233줄(yaml 1:1 Pydantic +
invariant 검증기) · `whs/path_promotion.py` 523줄(verified만 구조 승격·멱등 CLI·매칭 실패
전건 검수 큐 JSONL) · `db/models/solution_path.py` 93줄 · `l3/solution_path_store.py` 56줄 ·
alembic `c6d7e8f1a2b4` · `problem_step` additive 6컬럼 · reader 소생 2종 · 테스트 7파일 998줄.

커밋 메시지가 남긴 검증 증적: **backend 7,637 passed · 0 failed · infra 258 · harness 195 ·
ruff/black/mypy --strict/import-linter green**.

**즉 D1은 "안 만든 것"이 아니라 "main에 없는 것"이다.** 그리고 `S4-10`(D2)·`S4-11`(D3)·
`S4-12`(D4)가 전부 `S4-09`에 depends라 **풀이 축 전체가 이 한 건에 막혀 있다**.

**왜 안 보였는가(재발방지의 핵심)**: 고립분의 `done`은 *고립 브랜치의 YAML*에 기록됐고
main 대장의 `S4-09.status`는 `todo`다. 하네스 `next`는 이 상태를 "이미 완료(미머지)"로
정확히 경고하고 있었으나(SessionStart 브리핑 실측), **경고는 착수를 막을 뿐 회수를 시작하지
않는다**. 저장소는 최근 일주일 고립 회수를 7건 처리했다 — `PB-01`(`0f143076`)·
`PATH-05`(`4adc6870`)·`S3-17`(`00bc2706`)·`REC-02`(`4620f747`)·`VIZ-06`(`ddfb130c`)·
`NLP-04`(`35e81dc1`)·`S4-18`(`e71ede5b`). **풀이 축만 그 배치에서 빠졌다.**

### ② 신규 유형 — `step_panel` 죽은 사슬: 테스트가 양쪽 다 초록인 채 학생 도달 0

2차 이후 클라 표면이 생기면서 **새로 만들어진** 형태다.

| 층 | 실측 | 상태 |
|---|---|---|
| 서버 스키마 | `l4/learning_scene.py:127` `StepPanelElement`(`solution_path_id`·`reveal_policy="deferred"`) | 좌석 있음 |
| 서버 **생산자** | `l4/scene_generation.py`가 `StepPanelElement`를 **한 번도 만들지 않는다** — 전 저장소 `grep StepPanel`이 정의·`__init__` export·docstring만 반환 | **0** |
| 클라 모델 | `src/mobile/lib/features/chat/data/scene_models.dart:113` `solutionPathId` | 있음 |
| 클라 렌더러 | `scene_renderer.dart:91` → `:204` `_StepPanelSeed` — "**단계별로 살펴보기** / 차근차근 단계를 펼쳐 볼 수 있어요" **고정 문구 카드** | 있음(빈 껍데기) |
| 데이터 | `solution_path` 테이블이 main에 없음(위 ①) | **0** |
| 테스트 | `test_learning_scene.py:93,97,140` · `test_scene_dsl_layer_governance.py:166` · `scene_models_test.dart:41,106` · `scene_renderer_test.dart:115` | **양쪽 다 초록** |
| 계약 동결 | `MOB-14`(#766)가 scene DSL 서버↔클라 계약을 동결 | ⚠️ |

`POST /v1/scenes/*`(`api/scene.py:144`)는 **학생에게 실제 서빙되는 라이브 경로**다. 즉 이
사슬은 "아직 안 낸 기능"이 아니라 **가동 중인 표면의 영구 빈칸**이다.

**이 유형이 위험한 이유**: 테스트 6곳과 계약 동결이 전부 초록이라 **"배선됨"이라는 신호를
낸다**. CLAUDE.md의 "검증 장치를 만들고 배선 확인 없이 완료 선언 금지"가 *장치가 안 도는*
경우를 막는다면, 이것은 **역방향 변형** — 장치는 정확히 도는데 **대상이 없다**. 테스트는
계약을 인증할 뿐 도달을 인증하지 않는다.

### ③ 두 유형 모두 선언≠배선 탐지기(OPS-22)의 사각이다

`ops/declared_unwired_audit.py`(1,276줄)는 4축을 정적 감사한다 —
`http_routes`·`event_consumers`·`timeseries_tables`·`harness_clis`. 풀이 축의 미배선은
**어느 축에도 안 걸린다**:

| 미배선 | 왜 안 걸리나 |
|---|---|
| `problem_step` writer 0 | HTTP 축은 *라우트 호출 유무*를 본다 → `GET /v1/problems/{id}/steps`는 테스트 호출이 있어 **`reached`로 분류**된다. 그런데 writer가 0이라 응답이 **항상 빈 배열**이다 — 도달률은 초록, 데이터는 0 |
| `problem_step`·`solution_nodes` 테이블 | 타임시리즈 축은 `_FLOORS["timeseries_models"]=1` 기준 3모델만 — 일반 ORM 테이블은 대상 밖 |
| `step_panel` kind | scene DSL 요소 kind는 라우트도 이벤트도 테이블도 CLI도 아니다 |
| `ReasoningType` enum(`schema/enums.py:535`) | enum 선언 vs 소비처 0(실사용은 주석·docstring뿐)은 축에 없다 |
| `solution_nodes.prm_score` | writer 0 — `data/corpus/whs_prm_v0/prm_dataset.jsonl` **1,282행 전건 `"prm_score":null`** |

현 `_MANIFEST`의 풀이 인접 등재는 `:931` `POST /v1/verify-step`(by-design)과 `:951-952`
EventType `답입력`·`시각화조작`(`pending-task:S4-22`) 둘뿐이다.

→ **미탐 유형의 이름**: "좌석 있음 + 소비자 있음 + **공급 데이터 0**". 이 저장소는 이 유형을
축별 사후 리포트로 6회 이상 대응해 왔다(`harness/assessment_seat_reach_report.py`·
`visualization_reach_report.py`·`concept_reach_report.py`·`ops/recommendation_reach_report.py`·
`pedagogy_content_slot_reach_report.py`) — **풀이 축에만 그 좌석이 없다.**

### ④ 미배선 자산 총목록 (실측 — 이 축의 전모)

| 자산 | 위치 | 소비처 |
|---|---|---|
| `SolutionPath`/`SolutionStep`/`Justification` | `schemas/v1.1/solution_path.schema.yaml` | 0 (구현은 고립분에) |
| `Hint`/`HintReveals`/`SolutionStepRef` | `schemas/v1.1/hint.schema.yaml` | 0 |
| `ReasoningType` enum | `schema/enums.py:535` | 0 (주석만) |
| `ApproachType` 6종 | 스키마 + `tests/backend/l1/test_strategy_governance.py:42` 리터럴 | 0 |
| `multi_solution_gen.md` | `docs/prompts/` | 0 (**로더에도 미등재**) |
| `prm_verification.md` | `docs/prompts/` | 0 |
| `problem_step` 테이블 | `db/models/problem.py:317` | reader 1(빈 배열), **writer 0** |
| `solution_nodes.prm_score` | `db/models/solution_node.py` | writer 0 (1,282건 전건 null) |
| `reveal_score` | `hint.schema.yaml:172` | 0 |
| `equivalence_cluster_id`·SolutionPath `embedding` | `solution_path.schema.yaml` | 0 |
| `preferred_solution_style` | `mastery_state.schema.yaml:136` | 0 |
| `learning_scene.solution_path_id` | `l4/learning_scene.py:135` | **댕글링**(+ 클라까지 도달) |
| `StepPanelElement` | `l4/learning_scene.py:127` | 생산자 0·렌더러 stub 有 |
| LLM `SolverPolicy` 구현체 | — | 없음(Scripted/ChainReplay만) |

### ⑤ 전제 변화 — 검수 큐는 가동 가능, 파일럿은 계속 블록

- `backlog/gates.yaml` `G-domain-partner`(병목 ④ — **검수 큐 가동 조건**)가 **`cleared`**
  (evidence: 2026-07-10 AI 검수 전환 결정). → D1 승격 어댑터의 검수 큐·D4 동치 군집 2차
  검수가 전제한 조건이 **성립**한다.
- `S3-01-pilot-cohort`는 **여전히 `todo`** → `S4-11`(D3)의 의존은 계속 막혀 있다.

---

## §4. 설계 R1~R4

> 원칙: **기능을 새로 발명하지 않는다.** D1~D6가 유효하므로 재설계 0. R3가 더하는 것은
> ⑴ 막힌 것을 뚫고 ⑵ 거짓 초록을 끄고 ⑶ 같은 사고가 다시 안 나게 **기계로** 고정하는 것뿐이다.

### R1. 고립된 D1 완료분 회수 — 최우선 (백로그 신규 `SOL-01`)

공통 조상이 소실됐으므로 merge/rebase가 아니라 **이식(re-port)** 이다 — `PB-01`·`S3-17`·
`VIZ-06`·`REC-02`·`S4-18`이 확립한 패턴.

- **범위**: `86212c43`의 13개 src + 7개 테스트 파일. `21e35d28`의 S4-10 WIP는 **범위 밖**
  (알려진 실패 1건 미해결 — `S4-10`이 처리). 이식분이 그 실패 테스트를 끌고 오지 않는지 확인.
- **재조정 3곳**(이식만으로 성립하지 않는 부분):
  ⑴ alembic `c6d7e8f1a2b4`의 `down_revision`을 trunk head `db8ae6d2d91c`로 재연결(단일 head·
  up/down 대칭) ⑵ `db/schema_version.py` `KNOWN_REVISIONS`·`EXPECTED_ALEMBIC_HEAD` 갱신
  (SEC-03 규약) ⑶ trunk 드리프트 흡수 — `c3882ab6`(S5l Tutoring Adapter·2026-08-06)이
  `api/problems.py`·`db/models/problem.py`·`l4/scene_generation.py`·`schema/problem.py`
  4파일을 전부 수정했다.
- **검증 재수행 필수**: 이식본은 원 커밋의 7,637 통과 증적을 **승계하지 않는다**(657커밋
  드리프트). CI가 실제로 쓰는 명령을 대상 경로·플래그까지 **그대로** 재실행하고 판정은
  **exit code**로 한다(`-q`·`| tail` 금지 — 2026-08-09 규칙). 백엔드 소스를 건드리므로
  **전체 스위트** 후에 회귀 없음을 말한다.
- **뮤테이션 원복 주의**: 검증 중 일부러 깨뜨렸다 되돌린다면 원복은 **`cp` 백업으로만**
  (`git checkout --`/`restore`/`stash` 금지 — 2026-08-10 OPS-24 사고).
- **완료 조건**: main에서 `S4-09` → `done` 전이(artifacts에 이식 커밋 증적) + 원 브랜치를
  정리 대상 기록.

### R2. 죽은 `step_panel` 사슬을 잇는다 (백로그 신규 `SOL-02`, depends `SOL-01`)

**클라 stub을 제거하지 않고 서버 생산자를 잇는다.** `SOL-01` 착지로 `solution_path` 데이터가
실재하므로 "소비처 없는 좌석 신설"이 아니라 **이미 있는 두 끝을 잇는 것**이다(dead code
금기 위반 아님). 신규 scene kind 0·신규 enum 0·신규 테이블 0.

- **생산자**: `l4/scene_generation.py`가 해당 개념·문항에 `solution_path`가 **실재할 때만**
  `StepPanelElement`를 방출한다(없으면 방출 0 — **빈 껍데기 금지**). 조회는 `SOL-01`이 만든
  `l3/solution_path_store` 헬퍼 재사용(재구현 금지). `scene_generation.py:23`의
  "step_panel(SolutionPath Python 구현 후속)" 자인 문구를 삭제하는 최종 지점.
- **집행 별항**(2026-08-04 헌법 — 정본화≠집행): acceptance에 ①생산자 배선과 ②**그 생산자가
  실제 서빙 경로에서 방출되는지**를 **별항으로 분리**한다. `POST /v1/scenes/*` 응답 실바디에
  step_panel이 (데이터 있을 때) 실리고 (없을 때) 안 실린다는 **변별력 테스트**. "생성기
  함수가 만들 수 있다"는 집행 증거가 아니다.
- **클라**: `_StepPanelSeed` 고정 문구 → `solutionPathId`로 실제 단계 조회·렌더.
- **교수학 경계(협상 불가)**: `reveal_policy="deferred"` 불변 · 전체 풀이 일괄 노출 금지 ·
  학생이 **스스로 펼친 단계까지만** · 펼치기 전 단계 내용·정답 미렌더(위젯 테스트로 동결) ·
  점수·등급 노출 0(원본 §2-①).
- **착지 증거**: `SOL-03` 리포트의 kind별 실방출 카운트에서 `step_panel`이 0을 벗어나는 것
  (선언이 아니라 실측 — "작동한 비율" 원칙).

### R3. 풀이 좌석 도달 리포트 + 탐지기 5번째 축 (백로그 신규 `SOL-03`, 비의존·병렬 가능)

- **도달 리포트**: `harness/assessment_seat_reach_report.py` 패턴을 **재구현하지 않고 이식**.
  특히 그 모듈의 **`_KNOWN_WRITER_CITATION`** 관용구("생성 경로 자체가 없음" vs "생성 경로는
  있으나 아직 호출된 적 없음"을 구분해 렌더)를 승계 — 카운트 0인 테이블에 writer가 실재하는데
  "생성 경로 부재"라고 말하면 **거짓 주장**이 된다.
  관측 3축: ⑴ `problem_step`·`verified_solutions`·`solution_nodes`(+`SOL-01` 후
  `solution_path`) 행 수 + writer 유무 정직 사유 ⑵ `strategy_tag`·`reasoning_type` 분포(값
  없어도 0으로 명시 — 조용한 생략 금지) ⑶ **scene DSL 요소 kind별 실방출 카운트**.
- **게이트 아님** — `visualization_reach_report`·`problem_bank_coverage` 원칙 승계: 0이어도
  exit 1 아님. 목표는 활성화가 아니라 **가시화**.
- **탐지기 5번째 축**: `declared_unwired_audit.py`에 `scene_element_kinds`(kind Literal 좌석
  ↔ 서버 생산자 실재) 신설. 판정 규약은 기존 그대로 —
  `reached`/`by-design:<사유>`/`pending-task:<id>`, **미분류가 exit 1**. 그랜드파더 만료
  계약(`status != done`, 아니면 `expired-waiver` exit 1) 자동 승계. `_FLOORS`에 수집기 파손
  하한 추가. 착지 시점 `step_panel`은 `pending-task:SOL-02`로 등재.
- **배선 확인 의무**: 새 리포트 CLI와 새 축이 **실제로 CI에서 실행되는지** 확인해야 완료
  (`tests/infra/test_test_suite_wiring.py`·`test_declared_unwired_audit_wiring.py` 짝 갱신).
  "저장소에 존재함"과 "돌아감"은 다르다.
- **변별력**: 새 축이 *실패 상태에서 실제로 실패 신호를 내는지* 확인한다 — 미분류 kind 합성
  주입 시 exit 1, by-design 사유 누락 거부, `expired-waiver` exit 1.

### R4. 재발방지 등재 (CLAUDE.md 실수 관리 의무)

새 산문 규칙을 만들지 않는다 — "다음엔 조심한다"는 대책이 아니다.

| 사고 유형 | 회차 | 대책 형태 |
|---|---|---|
| 미병합 브랜치 고립 | **4회차** | 코드는 이미 있다(`PB-02` 그랜드파더 만료 계약). R3는 **사각의 정체를 실측 기록**한다 — 고립분의 `done`이 *고립 브랜치의 YAML*에만 있어 main 대장은 `todo`로 보였고, `next`의 "이미 완료(미머지)" 경고는 **착수를 막을 뿐 회수를 시작하지 않는다**. 회수 착수는 `SOL-01`(태스크 = 추적 가능한 형태) |
| 테스트 초록 + 학생 도달 0 | 신규 형태(선언≠배선 계열 7회차+) | 코드 — `SOL-03`의 5번째 축(`scene_element_kinds`). 산문 아님 |

### 등재 요약

| ID | title | status | depends | priority |
|---|---|---|---|---|
| `SOL-01-isolated-solution-path-recovery` | 고립된 S4-09 완료분 회수 — 2,153줄 trunk 이식 + 전체 스위트 재검증 | todo | — | **1** |
| `SOL-02-step-panel-producer-wiring` | step_panel 죽은 사슬 배선 — 서버 생산자 + 클라 실단계 deferred 노출 | todo | `SOL-01` | 2 |
| `SOL-03-solution-seat-reach-and-audit-axis` | 풀이 좌석 도달 리포트 + 탐지기 5번째 축 | todo | — | 2 |

전건 `track: math-completion` · `stage: S4` · `layer: backend` · `owner: claude`.
등재는 `scripts/harness/backlog.py add` CLI 경유(번호 추론 금지 — HARN-10 가드).

**priority 값 주의(실측)**: selector 정렬은 `(stage 순서, priority, −해금 후속 수, id)` **오름차순**
이라 **숫자가 작을수록 먼저**다(`build_harness.md:48`). 회수 선례 `PB-01`이 `priority: 1`인 것과
같은 이유로 `SOL-01`을 1로 둔다. 등재 직후 `next`가 `SOL-01`을 1순위로 계산하는 것을 확인했다.

> ⚠️ 인접 실측(이 리뷰의 조치 범위 밖·기록만): 기존 `S4-09`(5)·`S4-10`(5)·`S4-12`(4)는 이
> 정렬 방향과 **역방향**으로 매겨져 있다 — 값만 보면 D4(`S4-12`)가 D1(`S4-09`)보다 먼저
> 계산된다(실제로는 depends가 막아 무해). "5=가장 중요"로 읽은 흔적이며, 태스크 priority에
> CLI 세터가 없어 값 정정은 YAML 편집이 유일한 경로다. 별건으로 다룬다.

---

## §5. 정직한 공백 — 지금 하지 않는 것

- **`S4-09` 코드 이식 자체** — `SOL-01`의 몫. 2,153줄 이식 + 전체 스위트 재검증은 독립 세션
  분량이고, 1 세션 = 1 도메인 규약·컨텍스트 위생에 따라 분리한다.
- **`S4-10`~`S4-12` 착수** — `SOL-01` 미착지 상태에서 전건 블록(depends).
- **`S4-11`(D3 힌트 내용)** — `S3-01` 파일럿 미착지로 계속 블록. **최대 실행 갭이라는 판정은
  유지되나 전제가 미성립**이므로 지금 뚫지 않는다.
- **PRM 단계 스코어러** — `prm_dataset.jsonl` 1,282행 전건 null 상태 유지. 원본 §4-② 트리거
  관리 승계(백로그 미등재 상태를 정직 기록).
- **LLM `SolverPolicy`** — 추론 인프라 도달 미해소. 원본 §4-③ 승계.
- **`ocr_enabled` 기본 활성화** — §정정 ㉯로 기록만. 활성화 판단은 배포·의존 축 소관이며 이
  리뷰의 범위가 아니다.
- **다른 세션 원격 claim 중인 태스크** — `MISC-04`·`QUAL-02`·`QUAL-04`·`S3-34`·`SEC-18`·
  `HARN-20`(병렬 세션 규약).

---

## §6. 유보 항목의 발화 조건 — 원본 §4 갱신

| # | 유보 축 | 원본 트리거 | R3 갱신 |
|---|---|---|---|
| ① | 스캐폴딩 페이딩·힌트 경제 | D3 착지 + `S3-01` 실측 | 변화 없음(`S3-01` todo) |
| ② | PRM 단계 스코어러 | WH-S LLM 정책 착륙 or 도구 검증 부족 실측 | 변화 없음 |
| ③ | WH-S LLM 솔버 정책 | 추론 인프라 도달 해소 | 변화 없음 |
| ④ | 자유 텍스트/OCR→단계 자동 분해 | 입력 계약 축 한계 + D1 구조 좌석 | **부분 진전** — `NLP-03`(풀이 단계 분해 규약) done. 다만 `api/_segmentation_state.py`가 "백엔드가 원문을 받아 직접 분해하는 라이브 경로는 없다"고 자인(0-전이 비율만 인프로세스 관측) → 현행 정책(묶음 제출 유도) 유지 |
| ⑤ | `preferred_solution_style`·노출 순서 개인화 | D2 자산 + 파일럿 | 변화 없음 |
| ⑥ | 학생 대면 다중 풀이 노출·비교 UI·갤러리 | D2·D4 자산 + 파일럿 | **좌석 1개 선착지** — `SOL-02`가 `step_panel`(단일 풀이 단계 점층 노출)을 잇는다. *다중* 풀이 비교 UI는 Phase 3 유보 불변 |

---

## §정정 — 원본 문서의 stale 지점 3건 (원본 비수정·여기 기록)

### ㉮ §2-② "4단 수준축" 불채택 근거의 부정확

원본 §2-②는 "초등 그림→대학 증명 4단 수준축"을 "enum 선점은 소비처 없는 저작 부채"로
불채택했다. **실측**: 동형 4단 enum이 **이미 코드에 실재하고 소비처도 있다** —
`schema/speech.py:33` `SpeechGradeBand`(초등/중등/고등/대학) + `l4/speech/profiles.py:18-53`
`PROFILES` + `POST /v1/speech/latex`(`api/speech.py:35`). 수식 *낭독* 규칙 분기용이다.

**판정 자체는 유효**(풀이 *표현 차등*으로 확장하지 않는다). 다만 근거를 정밀화한다 —
"4단 축이 없어서"가 아니라 **"낭독 축에는 소비처가 있고 풀이 축에는 없어서"**다. 향후 풀이
표현 차등이 논의되면 새 enum 신설이 아니라 `SpeechGradeBand`와의 축 관계(동일 축인가 직교
축인가)를 먼저 판정해야 한다.

### ㉯ §1 기능 26 "손글씨(OCR) 채점 ✅"의 입도

원본은 "`l5/ocr/` 파이프라인 실재 + 저신뢰 게이팅"으로 ✅ 판정했다. **실측**:
`config.py:1067` `ocr_enabled` **기본 `False`(opt-in)** — rapidocr·rapid_latex_ocr 등 무거운
extra 의존 때문에 미설치 환경·CI에서 끈다.

"구현 실재"와 "기본 가동"은 다르다. `NLP-01`이 잡은 "OCR 배포 경로 양쪽 비활성"과 같은 축이며,
✅는 **"구현 실재" 축에서만 성립**한다.

### ㉰ §3 D3 "게이트 3종 … `detect_answer_leakage` 재사용"의 오독 여지

`detect_answer_leakage`(`harness/pedagogical_rubric.py:85`)의 호출처는 **전부 `harness/`
안**이다 — 모듈 밖 호출은 `harness/prompt_asset_audit.py:159` 하나, 나머지는 같은 오프라인
하네스 모듈 내부(`pedagogical_rubric.py:133`). 즉 **오프라인 하네스 전용**이며 서빙 게이트가
아니다.

D3가 *오프라인 사전 생성·검수* 설계이므로 **재사용 자체는 정합**하다. 다만 이 문구가 "서빙
경로의 답 누출 게이트"로 오독될 여지가 있어 명확화한다 — **서빙 억제는 별개 장치**다
(`api/coach.py:1606` `run_wh1_primary_turn`이 하네스 verify 의무 §3.1·**정답 억제 §3.4**·L4
톤필터를 통과한 발화만 반환하며, `wh1_primary_enabled` 플래그 게이팅 + 실패 시 결정론 폴백).

---

## 부록 — 실측 근거·재현 명령 (2026-08-11 · HEAD `959ec4ad`)

### 고립 실측 (§3-①)

```bash
git log --oneline -8 origin/claude/whymath-solution-review-40xspg
git show --stat 86212c43 | tail -25
git merge-base HEAD origin/claude/whymath-solution-review-40xspg; echo "EXIT=$?"   # 1 = 공통 조상 소실
ls src/backend/whymath_backend/l3/solution_path.py \
   src/backend/whymath_backend/db/models/solution_path.py \
   src/backend/whymath_backend/l3/multi_solution.py                                 # 전건 부재
grep -rn "ApproachType" src/backend/whymath_backend/ | wc -l                        # 0
grep -n "^status:" backlog/tasks/S4-09-solution-path-materialization.yaml           # todo
```

### 죽은 사슬 실측 (§3-②)

```bash
grep -rn "StepPanel\|step_panel" src/backend/whymath_backend/          # 정의·export·docstring만
grep -rn "step_panel\|_StepPanelSeed" src/mobile/lib/                  # 모델·렌더러 stub
sed -n '204,223p' src/mobile/lib/features/chat/presentation/scene_renderer.dart
grep -rn "step_panel" tests/ src/mobile/test/                          # 양쪽 테스트 초록
grep -n "router = APIRouter" src/backend/whymath_backend/api/scene.py  # :140 /v1/scenes 라이브
```

### writer 0·미배선 실측 (§3-③·④)

```bash
grep -rn "ProblemStep(" src/backend/whymath_backend/                   # 2건 = Pydantic·ORM 클래스 정의뿐·인스턴스 생성 0
grep -rn "ReasoningType" src/backend/whymath_backend/ | grep -v "enums.py"   # 2건 전부 docstring(축 혼동 금지 주석)
grep -rn "reveal_score\|equivalence_cluster\|preferred_solution_style" src/  # 1건 = runtime_selector.py:104 docstring뿐
grep -c '"prm_score":null' data/corpus/whs_prm_v0/prm_dataset.jsonl    # 1282 (= 전건)
grep -n "AXIS_HTTP\|AXIS_EVENT\|AXIS_TIMESERIES\|AXIS_CLI" src/backend/whymath_backend/ops/declared_unwired_audit.py
grep -n "_FLOORS" -A 8 src/backend/whymath_backend/ops/declared_unwired_audit.py
```

### D6 착지 확인 (§1 기능 26)

```bash
grep -n "n_unverifiable\|ocr_gated" src/backend/whymath_backend/schema/event_data_contract.py
grep -n "step_decision_rate\|step_incorrect_rate" src/backend/whymath_backend/harness/wh1_evaluation.py
grep -n "step_decision_rate" src/backend/whymath_backend/harness/surrogate_baseline_report.py
grep -n "^status:" backlog/tasks/S4-19-live-step-verification-event-persist.yaml   # done
```

### 정정 근거 (§정정)

```bash
sed -n '28,40p' src/backend/whymath_backend/schema/speech.py           # ㉮ SpeechGradeBand 4단
sed -n '1067,1075p' src/backend/whymath_backend/config.py              # ㉯ ocr_enabled=False
grep -rn "detect_answer_leakage" src/backend/whymath_backend/          # ㉰ 6건 전부 harness/ 안(오프라인)
sed -n '1603,1612p' src/backend/whymath_backend/api/coach.py           # ㉰ 서빙 억제는 별개 장치
```

### 전제 확인 (§3-⑤)

```bash
sed -n '12,20p' backlog/gates.yaml                                     # G-domain-partner cleared
grep -n "^status:" backlog/tasks/S3-01-pilot-cohort.yaml               # todo
```
