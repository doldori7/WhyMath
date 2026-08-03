# AI 콘텐츠 생성 모듈 — 2차 재점검 (2026-08-03)

> **범위**: 외부 참고 문서 『AI 콘텐츠 생성』(기능 58~61 + 확장 후보 62~68 — **WhyMath 전용이 아닌
> 일반적인 EOS 틀**, Kiki 제공)을 대조한 1차 점검(`ai_content_generation_gap_review.md`, 2026-07-30,
> PR #650)이 저장소에 이미 존재한다. 이번 문서는 68개를 처음부터 다시 대조하지 않는다 — **①1차
> 판정을 재확인 ②1차 이후 착지분을 반영 ③1차가 놓친 새 갭을 찾는** 2차 재점검이다.
> **형식**: `curriculum_module_gap_review.md`가 이전 5편의 자매편인 것과 동형 — 1차 문서를 대체하지
> 않고 자매편으로 신설. 1차 문서의 판정 이력은 그대로 보존한다(재작성 금지).
>
> **결론**: 1차 판정 58~68은 전부 **유지**(재확인 결과 변경 없음). 1차 이후 `S3-27`·`ARCH-21`이
> **done**으로 착지했으나 `S3-26`·`OPS-16`은 여전히 todo — 404 체인은 코드 변화 없이 그대로다.
> 이번 재점검에서 새로 실측한 G1(학생 도달 상한 4)은 조사 결과 **신규 갭이 아니라 `CUR-02`와 동일
> 근본 원인**(중복 등재 안 함). G2/G3(교수법 팩 콘텐츠 슬롯 파이프라인이 프로덕션 호출자 0·학생
> reader 0로 완전히 격리)는 **진짜 신규 갭**이며 1차 문서 §0이 인용한 "PED-01은 가동 중인 코드다"
> 논거의 사각지대다. 태스크 1건 등재.

관련 정본: `ai_content_generation_gap_review.md`(1차·58~68 전 판정) ·
`curriculum_module_gap_review.md`(D2 `CUR-02`·"완비된 소비 경로 + 미도달 공급원" 7회차) ·
`03_content_generation.md`·`04d_adaptive_pedagogy_engine.md`(교수법-중립 DSL·§0 논거 원본) ·
`PED-01-pedagogy-pack-dsl-foundation.yaml`(acceptance: "LLM 0·결정론 픽스처는 의도적") ·
`MEMORY.md` 결정 로그(2026-08-03).

---

## §0. 1차 판정 재확인 — 기능 58~68

전면 재판정이 아니라 **"1차 판정이 여전히 성립하는가"**만 짧게 재확인한다. 근거는 1차 문서 본문
참조.

| # | 1차 판정 (요약) | 재확인 결과 |
|---|---|---|
| 58 개념 설명 자동 생성 | 부분: 렌더 실가동·자산 437 충전 / 감사 0·어댑터 1/5 구조적 404 | **유지** — 404 체인 코드 재실측 불변(§1) |
| 59 예제 자동 생성 | 강함(생성) / 관측 불가(유형·시각) | **유지** — 단 `problem_type_codes`는 `S3-27` 착지로 관측 가능해짐(§1) |
| 60 스토리형 문제 생성 | 미채택 — 게임화·타깃 페르소나 금기 | **유지**(재검토 트리거 없음) |
| 61 실생활 적용 문제 생성 | 미채택 — `S3-15` 결정적 실패 선례 | **유지**(재검토 트리거 없음) |
| 62 힌트 자동 생성 | ⏸ `S4-11` 승계 | **유지**(todo) |
| 63 풀이·해설 자동 생성 | ⏸ `S4-09`·`S4-10` 승계 | **유지**(todo) |
| 64 변형 문제 생성 | ⏸ `S4-14` 승계 | **유지**(todo) |
| 65 멀티모달 콘텐츠 생성 | 🚫/⏸ `S4-03` 승계 | **유지**(todo) |
| 66 교수전략 기반 콘텐츠 생성 | 🚫 — 정본이 더 정교(§0 논거) | **유지, 단 사각지대 발견**(G2/G3 — 아래) |
| 67 수준별 콘텐츠 변환 | 🚫 — 페르소나 밖 승계 | **유지** |
| 68 오개념 교정 콘텐츠 생성 | ✅ 초과 충족 | **유지** |

---

## §1. 1차 이후 착지분 (2026-07-30 → 2026-08-03)

| 태스크 | 1차 시점 | 현재 | 재확인 |
|---|---|---|---|
| `S3-27`(문항 유형 필드 신설+결정론 백필) | todo | **done** | `schema/problem.py`에 `problem_type_codes` 필드 실재. `harness/problem_type_mapping.py`가 스켈레톤 생성기 18종→17유형 결정론 매핑, `problem_bank_coverage.py`에 `zero_coverage_types()` 등 유형×단원 축 추가 확인 |
| `ARCH-21`(QA 파이프라인 오케스트레이터) | todo | **done** | `harness/qa_pipeline.py` 7축(`corpus_audit`·`equivalence_canonicalize`·`concept_graph_reachability`·`misconception_crosslink_demotion`·`coach_prose_leak`·`content_provenance`·`defect_injection_demotion`) 실재. **단, 7축 중 개념 콘텐츠(`concept_content_v1`) 결함 감사 축은 없다** — `concept_graph_reachability`는 원자 *그래프 구조* 도달성이지 437행 콘텐츠 결함 감사가 아니다. 1차 D5 §4-트리거②("D2 감사 착지 후 결함주입 강등전 신설")의 전제가 아직 안 왔다는 뜻 — D5 판정 자체는 불변 |
| `S3-26`(개념 공급 무결성 — 404+감사) | todo | **todo(불변)** | 404 체인 재실측: `l3/render/dsl.py:171` `assessment=None,` 무조건 → `l3/render/adapters.py:222-224`(`ProblemBasedAdapter.can_render` = `dsl.assessment is not None` → 항상 False) → `api/study.py:189-193`(`result.rendered is None` → `HTTPException(404, "이 개념의 학습 콘텐츠가 아직 준비되지 않았습니다.")`). 코드 변화 없음 |
| `OPS-16`(L3 프롬프트 정본화+감사) | todo | **todo(불변)** | 재확인만, 코드 변화 없음 |

---

## §2. 신규 발견

### G1. 학생 도달 상한 = 4개 목표 — **신규 갭 아님, `CUR-02`와 동일 근본 원인(중복 등재 배제)**

`S3-26`이 404 체인을 전부 고쳐도, `/v1/me/objectives/{objective_id}/study`(`api/study.py`)가 서빙
가능한 학습목표 자체가 `data/corpus/units_v1/quadratic_maxmin.unit.yaml` **1개 파일·4목표**뿐이다
(디렉터리 전수 확인: 파일 1개). 개념 자산 437건·어댑터 5종·캐시 배선이 전부 완비돼도 이 상한과
무관하다 — 학생이 실제로 여는 관문은 objective 스코프이기 때문이다(`api/study.py` 모듈 docstring:
`evidence_event`가 `objective_id`·`k_type` NOT NULL을 요구해 라우터가 objective 축으로 설계됨).

**판정**: 이것은 `docs/architecture/curriculum_module_gap_review.md` §3 D2
(`CUR-02-objective-coverage-observability`)와 **정확히 같은 사실**이다 — 그 문서가 이미 "성취기준
895건 중 1건(4목표)만 분해"를 §6 "완비된 소비 경로 + 미도달 공급원" **7회차**로 등재했다. 여기서
"1건"이 가리키는 소단원이 바로 `quadratic_maxmin`이다. 새로 만들 태스크가 없다 — `CUR-02`가 이미
이 갭을 담당한다. 이 문서에서는 참조로만 남기고 중복 등재하지 않는다(CLAUDE.md 처리 규약 — 이미
등재된 태스크의 재등재 금지와 동형).

### G2/G3. 두 번째 콘텐츠 조성 파이프라인이 완전히 격리돼 있다 — **진짜 신규 갭**

1차 문서 §0은 `PED-01`(교수법 팩)·`PED-02`(런타임 선택기)·`PED-03`(적응 정책)·`REND-01`(렌더
어댑터)·`CACHE-01`(공급)을 "설계 문서가 아니라 가동 중인 코드"로 인용해 "교수전략이 생성의 *입력*이
아니라 *런타임 선택*"이라는 정본 논거(§0)의 근거로 삼았다. 이 논거 자체는 옳다. 그런데 재점검에서
전수 grep한 결과, `PED-01` 계보에는 **1차가 언급하지 않은 또 다른 콘텐츠 조성 파이프라인**이 있다:

```
l1/pedagogy/unit_compiler.py::compile_unit()
        │  (.unit.yaml → unit_spec·learning_objective 행 + 발주서 work_order)
        ▼
l3/pedagogy/slot_generator.py   →  PedagogyContentSlot 행 생성 (status=DRAFT)
        │  (결정론 픽스처 — 숫자형은 SymPy identity_status로 실제 검증, 개념형은 sympy_verified=None)
        ▼
l3/pedagogy/prescreen.py        →  DRAFT → PRESCREENED (기계 게이트)
        ▼
l3/pedagogy/review.py           →  PRESCREENED → APPROVED | REJECTED (검수)
```

**실측 (전수 grep, 2026-08-03)**:

| 확인 항목 | 결과 |
|---|---|
| `slot_generator.py`/`prescreen.py`/`review.py`의 프로덕션 호출자 | **0개**. 저장소 전체에서 이 3파일의 함수를 import하는 곳은 자기 자신의 테스트뿐 |
| 유일한 실행자 | `tests/backend/api/test_e2e_pedagogy_pilot_integration.py` — "이차함수 소단원 1개를 5단계 파이프라인 전 구간으로 실 PG에서 1회 관통"하는 walking-skeleton E2E. `PED-01` acceptance 원문이 "LLM 0 — 생성은 결정론 SymPy 검증 픽스처(hermetic 생성 단계). 런타임은 팩 주입 조립만"이라고 **의도를 명시**하고 있다 — 이 자체는 설계대로다 |
| `pedagogy_content_slot` 테이블의 학생 대면 reader | **0개**. 학생이 실제로 받는 콘텐츠 경로는 `l4/content_supply.py::supply()` → `l3/render/dsl.py::from_concept_content()`(`concept_content_v1` 437행) 하나뿐이고, `content_supply.py`는 `PedagogyContentSlot`을 **import조차 하지 않는다**(`grep -n "pedagogy_content_slot\|PedagogyContentSlot" l4/content_supply.py` 결과 0건) |
| APPROVED 슬롯의 downstream 소비처 | **0개**. `review.py`가 `PRESCREENED → APPROVED`로 승격은 하지만, APPROVED 슬롯을 읽어가는 코드가 저장소 어디에도 없다 |

**즉 WhyMath는 "AI 콘텐츠 생성"에 해당하는 조성 계층을 두 벌 갖고 있다**:

1. **정적 코퍼스 자체저작** (`concept_content_v1`, 437행) — 학생에게 실제로 도달함(단, D2/`S3-26`이
   다루는 어댑터 1/5 404·감사 0 문제가 있음)
2. **DSL 발주서 기반 결정론 슬롯 생성기** (`pedagogy_content_slot`) — DRAFT→PRESCREENED→APPROVED
   상태기계까지 완비돼 있는데, **입구(프로덕션 호출자)도 출구(학생 reader)도 없다**

둘은 서로를 모른다. 이건 `curriculum_module_gap_review.md` §6의 "완비된 소비 경로 + 미도달 공급원"
패턴의 **역**이다 — 여기는 **"완비된 조성 파이프라인 + 미도달 소비 경로"**다. §4에서 같은 반복
실수 계열의 8번째 사례로 등재한다.

> **틀과의 관계**: 확장 후보 66("교수전략 기반 콘텐츠 생성")에 대한 1차 판정(§0 정본 논거로 미채택)
> 자체는 옳지만, 그 판정이 근거로 든 "가동 중인 코드"의 범위를 좁혀야 한다 — PED 계보 코드는
> *존재*하지만 *가동*(프로덕션 실행)되고 있지는 않다. 판정 결론은 바뀌지 않는다(교수법 팩을 생성
> 입력으로 되돌리자는 뜻이 아니다) — 다만 "가동 중"이라는 서술은 이 파이프라인에 한해 **정정**한다.

---

## §3. 설계 D6 — 콘텐츠 슬롯 파이프라인 도달성 관측 (신규 태스크)

**목적**: `pedagogy_content_slot` 파이프라인의 프로덕션 호출자 0·학생 reader 0 상태를 **관측 가능한
사실**로 만든다. LLM 생성을 새로 여는 것은 범위 밖이다 — `PED-01` acceptance가 결정론 픽스처를
의도적 선택으로 명시했고, 1차 문서 D1(맥락 문항 생성 기각)이 세운 절제 원칙과 동형으로 "검증 없는
실행 안내 금지" 하에 성급한 LLM 개방을 하지 않는다.

- **경계 판단이 핵심 산출물** — 코드보다 먼저 답해야 할 질문: `pedagogy_content_slot` 축을
  ⓐ `concept_content_v1`/`S3-26`과 **합류**시킬지(예: `supply()`가 APPROVED 슬롯도 조회 대상에
  포함) ⓑ **분리 유지**(소단원 단위 조성 학습 vs 개념 단위 즉시 학습 — 다른 학습 표면)할지. 두
  데이터 모델(`ConceptDSL` vs `PedagogyContentSlot`)이 달라 합류는 변환 계층을 요구한다.
  - **권장 방향(설계 초안 — 최종 확정은 태스크 실행 세션)**: **분리 유지 + 관측만 우선.** 합류는
    조합 폭발·역방향 의존 위험(무한 온톨로지 금지 원칙과 인접)이 있고, 지금은 소단원 자체가
    1개(`quadratic_maxmin`, G1/`CUR-02` 미해소)라 합류해도 학생 도달 증가가 **0**이다. `CUR-02`가
    먼저 소단원 수를 늘려야 "합류할 가치"가 생긴다 — §4 트리거로 남긴다.
- **이번 태스크는 관측 축으로 한정**:
  ① `pedagogy_content_slot` 상태별(DRAFT/PRESCREENED/APPROVED/REJECTED) 건수 리포트
  ② "프로덕션 API 소비자 0"을 기계로 동결하는 거버넌스 테스트 — 신규 호출자가 생기면 이 테스트가
  의도적으로 깨져 "계약이 바뀌었다" 신호가 되게 한다(침묵 드리프트 금지)
  ③ E2E 파일럿 테스트가 실제로 5단계를 관통하는지 CI 배선 재확인(`tests/infra/
  test_test_suite_wiring.py` 등록 여부 실측 — "검증 장치를 만들고 배선 확인 없이 완료 선언 금지")
  ④ 신규 저작·신규 학생 대면 축은 **0**(이번 태스크로는 열지 않음 — §4 트리거만 문서화)
- **변별력 검증**: 상태별 건수 리포트가 파일럿 테스트 실행 전/후로 실제 값이 바뀌는지 확인. 거버넌스
  테스트는 결함 주입(신규 import 1줄 추가)으로 실패 상태에서 실제 실패 신호를 내는지 실측한 뒤 복원.

**등재**: 아래 §5 실행 로그 참조(백로그 CLI로 ID 확정).

---

## §4. 반복 실수 — "완비된 소비 경로 + 미도달 공급원" 계열에 역방향 8회차 추가

`curriculum_module_gap_review.md` §6이 누적한 표(1~7회차, 전부 "만들고 **잇지 않음**" 형태)에 이번
재점검에서 발견한 **역방향 사례**를 교차 참조로 등재한다.

| 회차 | 사례 | 형태 |
|---|---|---|
| 1~7 | (curriculum §6 표 — OCR·시각화·추천·PED 세션 컬럼·`select_probe`·`LearningObjective` 등) | 만들고 **잇지 않음**(소비 경로 완비, 공급원 미도달) |
| **8** | **`pedagogy_content_slot` 5단계 상태기계 완비(DRAFT→PRESCREENED→APPROVED) + 프로덕션 호출자 0·학생 reader 0** | **역방향** — 만들고 **아무도 부르지 않음**(조성 파이프라인 완비, 소비 경로 미도달) |

8회차가 1~7회차와 다른 점: 앞선 일곱은 "공급이 하류에 안 닿는다"(콘텐츠는 있는데 파이프라인 배선이
없음)인 반면, 8회차는 **파이프라인 자체는 완비돼 있는데 그 파이프라인을 켜는 스위치가 어디에도
없다**(입구도 출구도 0). 원인은 같다 — walking-skeleton/파일럿 코드가 "1회 관통 증명"이 목적이면
프로덕션 배선은 후속 결정으로 미뤄지고, 그 "후속"이 등재되지 않으면 영구히 대기 상태로 남는다.

---

## §5. 실행 로그

- 신규 태스크 등재: `PED-06-content-slot-pipeline-reachability`(`scripts/harness/backlog.py add`,
  track=infra-debt·stage=S3·priority=3·owner=claude) — 등재 후 `backlog.py validate` green(태스크
  157건) 확인.

---

## 부록 — 실측 근거·관련 코드

- **404 체인 재실측**: `l3/render/dsl.py:171`(`assessment=None,` 무조건) → `l3/render/adapters.py:222-224`
  (`ProblemBasedAdapter.can_render` = `dsl.assessment is not None` → 항상 False) →
  `api/study.py:189-193`(`HTTPException(404, ...)`)
- **`S3-27` 착지 확인**: `schema/problem.py`(`problem_type_codes` 필드) ·
  `harness/problem_type_mapping.py`(생성기 identity→17유형 매핑) ·
  `harness/problem_bank_coverage.py`(`zero_coverage_types()` 등 유형 축)
- **`ARCH-21` 착지 확인**: `harness/qa_pipeline.py`(`build_report()` — 7축: `corpus_audit`·
  `equivalence_canonicalize`·`concept_graph_reachability`·`misconception_crosslink_demotion`·
  `coach_prose_leak`·`content_provenance`·`defect_injection_demotion`)
- **G1 확인**: `data/corpus/units_v1/`(`quadratic_maxmin.unit.yaml` 1개 파일·4목표) ·
  `docs/architecture/curriculum_module_gap_review.md`(§3 D2·`CUR-02`·§6 7회차)
- **G2/G3 확인**: `l1/pedagogy/unit_compiler.py`(`compile_unit()` → `work_order`) ·
  `l3/pedagogy/slot_generator.py`(DRAFT 생성·결정론 픽스처·SymPy `identity_status` 검증) ·
  `l3/pedagogy/prescreen.py`(DRAFT→PRESCREENED) · `l3/pedagogy/review.py`(PRESCREENED→APPROVED|
  REJECTED) · `l4/content_supply.py`(`PedagogyContentSlot` import 0건) ·
  `tests/backend/api/test_e2e_pedagogy_pilot_integration.py`(유일한 5단계 관통 실행자) ·
  `backlog/tasks/PED-01-pedagogy-pack-dsl-foundation.yaml`(acceptance: "LLM 0 … 결정론 SymPy 검증
  픽스처" — 의도 명시)
