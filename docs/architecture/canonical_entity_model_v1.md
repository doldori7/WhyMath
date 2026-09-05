# Canonical Entity Model v1 — 핵심 엔티티 19종 동결

> **한 줄**: 9월 스키마에 들어갈 **핵심 엔티티를 19종으로 고정**하고, 현행 78테이블을 그 19종
> 또는 "핵심 외"에 **전수 귀속**시킨다. 검토해 온 나머지 노드는 9월에 넣지 않는다.

- **결정일**: 2026-09-05 (Kiki 지시 — "이날은 코드 개발을 멈추고 핵심 엔티티를 고정한다")
- **태스크**: `ARCH-37-canonical-entity-model-freeze`
- **실측 기준**: `Base.metadata` 전수 스캔 **78테이블** (2026-09-05)
- **시점 근거**: W2(9/7~9/13) = "되돌릴 수 없는 스키마 확정" 주간
  (`docs/strategy/eos_transition_declaration_2026-08-30.md` §5). 이 문서는 W2 **직전**에
  대상 목록을 확정해 W2가 무엇을 확정하는지 흔들리지 않게 한다.

---

## ⚖️ 집행 고지 (정본화 ≠ 집행)

CLAUDE.md "정본화를 집행으로 착각한 완료 선언 금지"에 따라 **이 문서가 강제하는 것과 강제하지
않는 것을 먼저** 적는다.

### 기계가 강제하는 것 — `tests/backend/db/test_canonical_entity_model_freeze.py`

| # | 검사 | 깨지면 |
|---|---|---|
| ① | 78테이블 **전수 귀속** — 좌석 또는 핵심-외 중 정확히 한쪽 | 신규 테이블이 생기면 **RED** |
| ② | 19종 **좌석 실재** + 엔티티 개수 19 고정 | 좌석 삭제·개명, 20번째 엔티티 추가 시 **RED** |
| ③ | **좌석 부재 4종** 예약 이름 금지 (§3) | `hints`·`assessment_result` 등이 생기면 **RED** |
| ④ | **문서 정합** — 정본이 78테이블·19엔티티를 전부 적고 있다 | 표가 코드보다 뒤처지면 **RED** |

### 기계가 강제하지 **않는** 것 (있는 척 금지)

- **배정의 옳음**. 기계는 배정의 *전수성*만 본다 — "이 테이블이 *올바른* 엔티티에 갔는가"는
  사람 판단이며 이 문서의 산문이 근거다.
- **컬럼 수준 스키마**. 어떤 필드를 갖는지는 각 모델의 기존 ORM 테스트 소관이다.
- **코드 밖 저작 스키마와의 정합**. `schemas/v1.1/*.yaml`·`schemas/v1.0/`과의 대조는
  기계 집행이 **없다** — 알려진 드리프트는 §7에 그대로 적는다.
- **런타임 사용 여부**. 좌석이 있다고 writer가 있다는 뜻이 아니다(§7-C).

---

## §1. 핵심 엔티티 19종 — 위반 판정 가능한 정의

각 항목은 **"이것이다 / 이것이 아니다"** 쌍으로 적는다. "대체로 이런 느낌"은 판정 근거가 되지
못하므로, 새 코드가 어느 엔티티인지 다툴 때 아래의 *아니다* 절이 결론을 낸다.

### 교육과정 축

1. **Subject** — 학습 내용의 최상위 분류 축.
   - *이다*: 한 문항·개념이 어느 과목에 속하는지 말하는 **분류 값**.
   - *아니다*: 자체 생명주기를 갖는 레코드가 아니다. → **좌석 부재**(§3-A), 열(column) 축으로 유지.

2. **Curriculum** — 한 국가·시기의 교육과정 **판(version)** 그 자체.
   - *이다*: "2022 개정 교육과정 수학과"처럼 **개정 단위로 통째 교체되는 것**.
   - *아니다*: 그 안의 단원·성취기준 개별 항목이 아니다(그것은 CurriculumNode).

3. **CurriculumNode** — 교육과정 안의 **한 항목**(영역·단원·성취기준·성취수준·교과서 단원).
   - *이다*: Curriculum 판에 종속돼 **판이 바뀌면 함께 교체되는** 구조 항목.
   - *아니다*: 개념 그 자체가 아니다. 플레이북 "Curriculum은 Overlay" 원칙 — 개념은 영속하고
     교육과정 매핑만 교체된다. 이 축에 개념을 넣으면 개정 때 개념이 함께 죽는다.

4. **LearningObjective** — 소단원의 **한 학습목표**(주 지식유형으로 교수법 팩에 바인딩).
   - *이다*: 학생이 무엇을 할 수 있게 되는지의 진술 + 그 진술이 붙는 소단원 컨테이너.
   - *아니다*: 성취기준 원문이 아니다(그것은 CurriculumNode·NCIC 공공누리). 교과서 학습목표
     **본문**은 저작권 게이트 대상이라 여기 복제 금지.

### 지식 축

5. **Concept** — 교육적으로 압축된 인지 그래프의 **노드**(순수 개념).
   - *이다*: `math.<area>.<slug>` canonical ID로 영속하는 개념 원자.
   - *아니다*: renderer·curriculum·prompt·misconception·UI·embedding을 **품지 않는다**
     (Concept Purity — 8대 구조 원칙 ①). 그 6종은 전부 핵심-외 테이블로 외부화돼 있다(§2-B).
   - ⚠ **혼재 3좌석**: `concept`(관계형) · `concept_node`(그래프 프로젝션) · `atom_node`(원자 백본).
     판정 불가라 **그대로 적는다** — 통합 여부는 §5 후속 판단.

6. **Skill** — 개념을 **실행**하는 능력 단위(`skill.<slug>`).
   - *이다*: 숙련도 추적의 단위이자 증거가 귀속되는 대상.
   - *아니다*: 개념이 아니다. Concept이 "무엇을 아는가"라면 Skill은 "무엇을 할 수 있는가".

7. **Misconception** — 반복 관측되는 **오개념 카탈로그 항목**(`M0425` + kebab crosswalk).
   - *이다*: 학생 개인과 무관하게 존재하는 **유형 정의**.
   - *아니다*: 특정 학생의 오개념 **추정**이 아니다(그것은 §2-C 판정 보류).
   - 계약: 초기 context에 preload 금지 — reactive retrieval만(붕괴 방어).

### 콘텐츠 축

8. **Problem** — 학생에게 제시되는 **한 문항**과 그 정답 단계.
   - *이다*: 자체 코퍼스의 문항. 구조(스키마) + 렌더러-중립 LaTeX 본문.
   - *아니다*: 검정교과서·평가원 기출 **본문 복제가 아니다** — 구조 메타데이터만 인용하고
     본문은 자체 동등문제로 대체한다(절대 금기).

9. **Solution** — 한 문항에 대한 **풀이 경로**와 그 검증 산출.
   - *이다*: 접근법 1개 = 경로 1개(한 문항에 다중 경로 허용). 다중 풀이의 본질적 동치성이 이 축.
   - *아니다*: 학생이 실제로 쓴 풀이가 아니다(그것은 LearningEvent의 `student_solution_step`).
     **정본 풀이 ↔ 학생 풀이**를 섞으면 채점 대상과 정답지가 같은 테이블에 산다.

10. **Hint** — 등급화된 **힌트**(1=가장 은근 ~ 3=거의 정답).
    - *이다*: "바로 정답 제공 금지 · 가능한 가장 빠른 단계에서 멈춤"의 데이터 표현.
    - *아니다*: 힌트를 **썼다는 기록**이 아니다(그것은 LearningEvent의 `hint_usage`).
    - → **좌석 부재**(§3-B). 설계 정본은 있고 저장 좌석이 없다.

11. **Content** — 개념·소단원에 붙는 **설명 자산**(은유·오개념 설명·정식정의·허용표현·암기카드).
    - *이다*: 학생에게 보여줄 수 있는 서술형 자산과 그 슬롯.
    - *아니다*: 문항이 아니다(Problem). 개념 노드 자체도 아니다(Concept Purity).

### 학습자 축

12. **Learner** — 학생 **본인**(계정·프로필).
    - *이다*: 신원과 프로필. **미성년 민감정보**로 분류돼 암호화 저장 대상.
    - *아니다*: 학습 상태가 아니다(LearnerState). 인증 자격도 아니다(핵심-외).

13. **LearnerState** — 한 시점의 학습 **상태 스냅샷**.
    - *이다*: "지금 이 학생은 어떤 상태인가"의 시점 사진(개념·패턴 숙련 맵, 평균 풀이시간 등).
    - *아니다*: 숙련도의 **시계열 이력**이 아니다(MasteryState). 프로필 변경 이력도 아니다.

14. **MasteryState** — Skill·Concept별 **숙련도**와 그 변화 이력.
    - *이다*: 누적 증거를 반영한 현재 숙련 + append-only 이력.
    - *아니다*: 개별 증거 하나가 아니다(LearningEvent). 시험 결과도 아니다(Assessment).

### 평가 축

15. **Assessment** — 진단 평가 **세션**(초기 진단 + 주기적 재진단).
    - *이다*: "언제 무엇을 진단했는가"의 컨테이너.
    - *아니다*: 매 문항 채점이 아니다(LearningEvent).

16. **AssessmentResult** — 그 진단이 **산출한 판정**(단원별 진단·약점·강점·권장 경로).
    - *이다*: Assessment 1회의 결론.
    - → **좌석 부재**(§3-C). 현재 `assessment` 행 안의 JSONB 5필드로 **혼입**돼 있다.

### 행위·전략 축

17. **LearningEvent** — 학생이 남긴 **원시 학습 행위 기록**.
    - *이다*: 시도·제출·힌트 사용·대화 턴·풀이 단계·막힘 등 **일어난 일 그대로**.
    - *아니다*: 그 기록에서 **파생된 집계·판정이 아니다**. 롤업(일일 지표 등)은 핵심-외로 뺐다.
    - ⚠ 11좌석으로 가장 넓다. 4층 경계(Attempt·Evaluation·Assessment·Mastery)의 정밀 분해는
      **`EOS-79`가 소유**한다 — 이 문서는 그 태스크를 대체하지 않는다(§6).

18. **PedagogyStrategy** — 교수 **전략**과 그 팩(Polya·소크라테스 등 인지행동 기준 전략).
    - *이다*: "어떻게 가르칠 것인가"의 재사용 단위.
    - *아니다*: 개념도 콘텐츠도 아니다. 노드에 prompt를 넣지 않는다는 원칙의 반대편 좌석.

19. **ContentVersion** — 콘텐츠·엔티티의 **판 관리** 공통 축.
    - *이다*: "이 학생이 푼 그 문항의 그 시점 판은 무엇이었나"를 복원하는 축.
    - *아니다*: 엔티티마다 각자 만드는 버전 필드가 아니다 — **공통 거버넌스**가 원칙.
    - → **좌석 부재**(§3-D). 현재 각 테이블에 버전 컬럼이 **분산**돼 있다.

---

## §2. 현행 78테이블 전수 귀속표

> 이 표는 `tests/backend/db/test_canonical_entity_model_freeze.py`의 상수와 **1:1**이며,
> 검사 ①·④가 둘의 어긋남을 RED로 낸다.

### §2-A. 좌석 배정 — 41테이블

| # | 핵심 엔티티 | 좌석 테이블 | 좌석 수 |
|---|---|---|---|
| 1 | **Subject** | — **좌석 부재**(§3) | 0 |
| 2 | **Curriculum** | `curriculum_framework` · `curriculum_version` | 2 |
| 3 | **CurriculumNode** | `curriculum_entry` · `achievement_standard` · `achievement_level_unit` · `textbook_unit` · `textbook_mapping` | 5 |
| 4 | **LearningObjective** | `learning_objective` · `unit_spec` | 2 |
| 5 | **Concept** | `concept` · `concept_node` · `atom_node` | 3 |
| 6 | **Skill** | `skill_node` | 1 |
| 7 | **Misconception** | `misconception_catalog` | 1 |
| 8 | **Problem** | `problem` · `problem_step` | 2 |
| 9 | **Solution** | `solution_paths` · `solution_nodes` · `verified_solutions` · `verified_lemmas` | 4 |
| 10 | **Hint** | — **좌석 부재**(§3) | 0 |
| 11 | **Content** | `concept_content` · `pedagogy_content_slot` | 2 |
| 12 | **Learner** | `user_profile` | 1 |
| 13 | **LearnerState** | `user_state_snapshot` | 1 |
| 14 | **MasteryState** | `concept_mastery_history` · `skill_mastery_history` · `ability_snapshot` | 3 |
| 15 | **Assessment** | `assessment` | 1 |
| 16 | **AssessmentResult** | — **좌석 부재**(§3) | 0 |
| 17 | **LearningEvent** | `attempt_event` · `evidence_event` · `review_timer_event` · `hint_usage` · `answer_submission` · `problem_attempt` · `learning_session` · `student_solution_step` · `dead_end_log` · `dialogue` · `dialogue_turn` | 11 |
| 18 | **PedagogyStrategy** | `strategy_node` · `pedagogy_pack` | 2 |
| 19 | **ContentVersion** | — **좌석 부재**(§3) | 0 |

**좌석 합계 = 41**

### §2-B. 핵심 외 — 37테이블

핵심 19종에 **배정하지 않는다**. 사유를 값으로 강제해(테스트 상수) "일단 여기 던져 넣기"를
비싸게 만든다. 이 목록 자체가 **8대 구조 원칙의 외부화 증거**다 — 임베딩·렌더러·관계·오개념이
개념 노드에서 이미 분리돼 있다.

| 테이블 | 배정 제외 사유 |
|---|---|
| `atom_embedding` | 임베딩(벡터) — 개념 노드에 혼입 금지 |
| `atom_probe` | 부속 노드(원자 프로브) — 원자 백본 진단 보조 |
| `concept_edge` | 관계(엣지) — 개념↔개념 |
| `concept_embedding` | 임베딩(벡터) — 개념 노드에 혼입 금지 |
| `concept_fusion` | 관계(엣지) — 개념 융합 |
| `concept_standard_link` | 관계(엣지) — 개념↔성취기준 |
| `concept_visual_style` | 렌더러(시각 스타일) — 개념 노드에 혼입 금지 |
| `concept_visualization` | 렌더러(시각화 인텐트) — 개념 노드에 혼입 금지 |
| `content_provenance` | 권리·출처(생성 계보) |
| `content_rights` | 권리·출처(저작권 레일) |
| `content_source` | 권리·출처(저작권 레일) |
| `daily_learning_metrics` | 집계(롤업) — LearningEvent 파생물 |
| `defect_report` | 운영(결함 신고) |
| `deletion_audit` | 감사(파기 이력) |
| `derivation_edge` | 관계(엣지) — 콘텐츠 파생 계보(권리 축) |
| `device_credential` | 인증(기기 자격) |
| `evidence_links` | 관계(엣지) — 증거↔대상 |
| `formula_node` | 부속 노드(공식 택소노미) — Concept 승격은 정본 갱신 경유 |
| `generation_log` | 권리·출처(LLM 생성 로그) |
| `misconception_crosslink` | 관계(엣지) — 오개념 kebab↔M-id 크로스워크 |
| `misconception_embedding` | 임베딩(벡터) — 오개념 노드에 혼입 금지 |
| `misconception_hypothesis` | 판정 보류 — L2 오개념 추론 산출물. 카탈로그도 원시 이벤트도 아니다 |
| `misconception_relation` | 관계(엣지) — 오개념↔오개념 |
| `parental_consent` | 법령(법정대리인 동의) — 기계 대체 금지 축 |
| `privacy_audit` | 감사(개인정보 접근) |
| `problem_concept` | 관계(엣지) — 문항↔개념 |
| `problem_embedding` | 임베딩(벡터) — 문항에 혼입 금지 |
| `problem_relation` | 관계(엣지) — 문항↔문항 |
| `problem_solve_time_distribution` | 집계(롤업) — LearningEvent 파생물 |
| `problem_type_node` | 부속 노드(문항유형 택소노미) — Problem 승격은 정본 갱신 경유 |
| `refresh_token_session` | 인증(세션 토큰) |
| `rights_entity` | 권리·출처(저작권 레일) |
| `rights_holder` | 권리·출처(저작권 레일) |
| `source_entity` | 권리·출처(저작권 레일) |
| `user_behavior_metrics` | 집계(롤업) — LearningEvent 파생물 |
| `user_persona_history` | 사용자 이력(페르소나 변경) — LearnerState 아님 |
| `user_track_history` | 사용자 이력(트랙 변경) — LearnerState 아님 |

**핵심-외 합계 = 37** · 41 + 37 = **78** ✓

### §2-C. 판정 보류 1건 — 날조 금지

`misconception_hypothesis` 는 **특정 학생의 오개념 추정 레코드**다.

- Misconception(카탈로그)이 **아니다** — 학생에 종속된다.
- LearningEvent(원시 기록)도 **아니다** — 일어난 일이 아니라 L2가 *추론한 결론*이다.
- MasteryState도 **아니다** — 숙련도 축이 아니다.

**층을 늘리지 않는다**(관계 타입 폭발 금지의 동형). 20번째 엔티티를 만들지 않고 "핵심 외 ·
판정 보류"로 그대로 둔다. 이 결정을 뒤집으려면 §5 절차를 경유한다.

---

## §3. 좌석 부재 4종 — 부재를 동결한다

**부재는 실수가 아니라 결정이다.** 아래 4종은 "아직 안 만들었다"가 아니라 "9월에 만들지
않는다"이며, 검사 ③이 예약 이름(`subject`·`hints`·`assessment_result`·`content_version` 등)의
등장을 RED로 막는다.

### §3-A. Subject — 테이블로 만들지 않는다

- **현행 실체**: `Subject` enum 5값(공통·미적분·확통·기하·인공지능수학 — **수능 선택과목 축이며
  수학 교과 한정**) + 자유 텍스트 `subject` 컬럼 8테이블(`concept_content`·`curriculum_entry`·
  `achievement_standard` 등, 기본값 `"수학"`).
- **동결 사유**: 교과 확장(물리 등)의 트리거는 "물리 문항 첫 적재"로 이미 보류 대장에 있다
  (`docs/architecture/subject_expansion_readiness.md`). 그 전에 테이블을 만들면 **수능 선택과목
  축과 교과 축이 한 축으로 영구 혼동**된다.
- **9월 조치**: 없음. 열 축 유지.

### §3-B. Hint — 설계 정본은 있고 저장 좌석이 없다

- **현행 실체**: `schemas/v1.1/hint.schema.yaml`이 entity `Hint`·L4·`storage: "PostgreSQL 16
  (hints)"`·`primary_key: hint_id`로 선언한다. **그러나 `hints` 테이블은 존재하지 않는다.**
  `l3/solution_path.py`가 힌트 원천 텍스트를 담고, 구조화는 "L4 몫"으로 남아 있다.
  `hint_usage`는 **사용 기록**이지 힌트 본문이 아니다(`hint_id`는 FK 없는 자유 텍스트).
- **동결 사유**: 답 미루기 4단계는 Phase 1 성공 기준이라 **언젠가 필요하다**. 다만 9월에 좌석을
  파면 본문 없는 빈 테이블이 되고, 그때 `hint_usage.hint_id`의 느슨참조를 FK로 조일지가
  함께 걸린다 — W2가 감당할 결정이 아니다.
- **9월 조치**: 없음. 승격은 §5 절차 + 별도 태스크.

### §3-C. AssessmentResult — `assessment` 안에 혼입돼 있다

- **현행 실체**: `assessment` 테이블의 JSONB 5필드
  (`concept_diagnosis`·`pattern_diagnosis`·`weak_points`·`strong_points`·`recommended_path`).
  세션(언제 진단했나)과 결과(무엇이 나왔나)가 **한 행에 산다**.
- **동결 사유**: 분리하면 진단 이력 조회 경로가 전부 바뀐다 — 소급 불가 변경이라 W2 대상이나,
  이번 주 근거로는 분리 이득이 실측되지 않았다.
- **9월 조치**: 없음. **혼입 상태를 인정하고 적는다**(날조 금지).

### §3-D. ContentVersion — 전용 좌석 없이 분산돼 있다

- **현행 실체**: `curriculum_version`(교육과정 판만 담당) + 각 테이블의 버전 컬럼
  (`unit_spec.unit_version`·`pedagogy_pack.pack_version`·`api_version`·`problem.curriculum_version`·
  `generation_log.prompt_version`) + `content_provenance`.
- **알려진 갭**: `concept_node`에 `version` 컬럼이 **없다**. 계획서가 경고한
  "엔티티마다 별도 버전 시스템을 만들지 말라"는 **유효한 경고**이며, 이 축은
  **`EOS-49`(ConceptVersion 계약)·`EOS-47`(attempt version pinning)이 소유**한다.
- **9월 조치**: 이 문서는 좌석을 만들지 않는다. 공통 버전 축 설계는 위 두 태스크로 넘긴다 —
  **여기서 20번째 엔티티를 급조하면 두 태스크와 충돌한다.**

---

## §4. 9월 스키마에 넣지 않는 것

Kiki 지시: *"기존에 검토해 온 훨씬 많은 Node를 모두 9월 schema에 넣는 것은 피한다."*
그 지시를 **판정 가능한 규칙**으로 옮기면 아래다.

1. **19종 밖의 새 1급 엔티티를 9월에 만들지 않는다.** 20번째가 필요해 보이면 먼저 §2-C처럼
   "핵심 외 · 판정 보류"로 적어 둔다 — 층을 늘리는 것이 마지막 수단이다.
2. **부속 노드는 부속으로 둔다.** `formula_node`·`problem_type_node`·`atom_probe`는 승격 후보이나
   9월 승격 금지. 승격은 §5 절차.
3. **관계 타입을 늘리지 않는다.** 현행 엣지 9종으로 충분한지 먼저 묻는다 —
   "이 관계가 없으면 AI 튜터링에서 실제 어떤 오류가 나는가"에 답하지 못하면 weak → 제거.
4. **개념 노드에 아무것도 더 붙이지 않는다.** renderer·curriculum·prompt·misconception·UI·
   embedding은 이미 전부 외부화돼 있다(§2-B가 그 증거) — 되돌리지 않는다.
5. **W2가 확정하는 소급 불가 스키마**(`REC-11`·`EOS-47`·`EOS-49`)는 이 동결의 **예외가 아니라
   대상**이다. 셋 다 기존 좌석의 컬럼 추가이지 새 엔티티가 아니다 — 이 동결과 충돌하지 않는다.

---

## §5. 동결을 푸는 절차

동결은 영구 금지가 아니라 **비용을 명시한 문턱**이다. 새 엔티티·새 좌석이 필요하면:

1. **어느 기존 엔티티로도 안 되는 이유**를 §1의 *아니다* 절과 대조해 적는다.
2. **backlog 태스크로 등재**한다(`backlog.py add` — 번호 눈으로 고르기 금지).
3. 이 문서의 §1·§2 표와 `test_canonical_entity_model_freeze.py`의 **상수를 함께** 고친다.
   둘 중 하나만 고치면 검사 ④가 RED를 낸다(그것이 이 검사의 목적이다).
4. MEMORY.md에 결정 로그를 남긴다.

**이 절차 자체에는 기계 집행이 없다** — 3번만 기계가 본다. 1·2·4는 사람 규율이다.

---

## §6. 인접 정본과의 경계 (중복 방지)

| 문서·태스크 | 소유 범위 | 이 문서와의 관계 |
|---|---|---|
| `EOS-79-evidence-layer-boundary-canon` | Attempt·Evaluation·Assessment·Mastery **4층 경계** | 이 문서 §1-17(LearningEvent)의 **내부 분해**를 소유. 대체하지 않음 — EOS-79는 그대로 진행 |
| `docs/standards/part9_id_policy_review.md` | 엔티티 **ID 형식**(`math.<area>.<slug>`·`skill.<slug>`·`M0425`) | ID는 이미 동결·CI 집행 완료. 이 문서는 ID를 **재정의하지 않는다** |
| `EOS-49` / `EOS-47` | **버전 축** 공통 계약 | §3-D의 미해결분을 소유 |
| `docs/architecture/32_learning_history.md` §4 | 학습이력 9엔티티 판정표 | 도메인 한정 부분 정본. 충돌 시 **이 문서가 상위** |
| `docs/reviews/eos_phase2_plan_300_gap_review_2026-09-03.md` §4.1 | 14객체 실측 대조표 | 리뷰 문서(정본 아님). 이 문서가 그 인벤토리를 19종으로 승격·확장 |
| `docs/architecture/eos_core_adapter_boundary.md` | 모듈 Core/Adapter 배정 | 축이 다름(모듈 vs 엔티티) |

---

## §7. 알려진 드리프트 — 그대로 적는다

기계 집행이 **없는** 축이라 사람이 읽어야 한다. 고치지 않고 적는 이유는, 지금 고치면
9월 동결의 범위가 아니라 리팩터가 되기 때문이다.

- **A. `schemas/v1.1` 저장소 선언이 낡았다.** `concept.schema.yaml`·`edge.schema.yaml`이
  `storage: Neo4j 5.x`라고 적지만, Neo4j는 **런타임 미도입**이고 정본은 PG 단일 평면이다
  (CLAUDE.md 2026-08-03 확정). 이 정본은 PG 실측을 따른다.
- **B. `schemas/v1.1/hint.schema.yaml`이 없는 테이블을 선언한다.** §3-B 참조 —
  설계 정본과 저장 실측이 어긋난 유일한 엔티티다.
- **C. 좌석이 있다고 writer가 있다는 뜻이 아니다.** `learning_session`은 스키마가 실재하나
  **writer 0**으로 실측됐다(계획서 300 검토 §4.1). 이 문서는 좌석의 *존재*만 동결하며
  **배선 여부는 판정하지 않는다** — 배선·폐기 판정은 별도 소유자가 필요하다.
- **D. `ROADMAP.md` 미반영 잔여 "스키마 v1.0↔v1.1 통합"이 여전히 열려 있다.**
  이 문서는 그 통합을 수행하지 않는다.

---

## 부록. 재현 명령

```bash
# WSL / Linux — 저장소 루트에서
cd /mnt/c/Users/kiki/Desktop/__AI/WhyMath
python -m pytest tests/backend/db/test_canonical_entity_model_freeze.py -v; echo "EXIT=$?"
```

```powershell
# Windows PowerShell (Phaiakes9) — 저장소 루트
cd C:\Users\kiki\Desktop\__AI\WhyMath
python -m pytest tests\backend\db\test_canonical_entity_model_freeze.py -v; echo "EXIT=$LASTEXITCODE"
```

판정은 **exit code**로 한다(출력 문자열 아님 — CLAUDE.md "검사 명령의 출력을 억제하거나 잘라서
판정 금지").
