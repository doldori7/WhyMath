# EOS Core ↔ Math Adapter 경계 — 현행 패키지 배정표 (EOS-65 작성 · EOS-67 집행 · EOS-69 상환)

> **지위**: `EOS-65-core-adapter-boundary-map` 산출물. `EOS-66`(SubjectAdapter 계약)·
> `EOS-67`(import-linter 강제)의 **선결 입력**이며, G1(2026-09-27) 차단 조건
> "Core→Math 정적 의존 0"의 *판정 기준 그 자체*다.
>
> **배정 정본은 이 문서가 아니라 코드다** — `scripts/analysis/eos_core_adapter_boundary_scan.py`
> 의 `BOUNDARY_MAP`이 단일 진실 원천이고, 본 문서는 그 표를 전사·해설한다(선례:
> `eos_anchor_asset_audit.py`의 `ANCHOR_DEFS`가 EOS-51 앵커 동결 정본). 배정을 바꾸려면
> 스크립트를 고친다 — 문서만 고치면 이중 진실 원천이 된다.
>
> ## 집행 상태 (2026-09-01 `EOS-69` 기준)
>
> 이 문서와 스캔 스크립트는 *계측기*다. 강제는 **`EOS-67`**(import-linter 계약 2건 + CI 배선
> 동결)이 하고, 빚 상환은 **`EOS-69`**(SubjectAdapter 경유 배선)가 했다.
>
> - **위반 15건 → 1건**(심볼 기준) · **9간선 → 1간선**(모듈 기준). 상세 = §4.
> - 남은 1건은 C분류(`api._ocr_state` → `l5.ocr.factory` 타입 주석)이며 EOS-69 범위 밖이다.
> - 여전히 "Core가 수학을 전혀 모른다"고 말하면 안 된다 — MIXED 34모듈은 그대로이고(§4 한계),
>   이 계약은 *직접 import*만 본다. 성립한 것은 **A·B분류 경로가 계약을 경유한다**는 것까지다.
>
> 대조 시점: 2026-09-01 · 스캔 대상 **563 모듈 / 158,677 LOC**(CORE 303·ADAPTER 50·MIXED 34·
> INFRA 176) · 스캔 오류 0 · **CORE의 sympy import 여전히 0건**.
> (직전 스냅샷: 2026-08-31 · main `3f512962` · 556 모듈 / 155,435 LOC · 위반 15건.)

---

## §1. 판정 규칙

계획서 100 §3.7의 단일 문장이 규칙이다 — **"Core가 이차방정식을 알게 만들면 안 된다."**
이를 판정 가능한 형태로 옮기면:

| 배정 | 정의 | 판별 질문 |
|---|---|---|
| **CORE** | 과목과 무관한 교육 실행 엔진 | Physics를 붙일 때 **이 모듈을 고쳐야 하는가?** 아니오 → CORE |
| **ADAPTER** | 수학 의미론(기호 조작·수식 표기·수학 엔티티 타입)을 인코딩 | 이 모듈이 아는 것이 *수학*인가? 예 → ADAPTER |
| **INFRA** | 횡단 관심사(설정·DB 세션·보안·관측성·하네스) | 계층 계약의 대상이 아님 |
| **MIXED** | 한 모듈 안에 CORE 기계와 ADAPTER 의미론이 동거 | 파일 단위로 못 가름 → **그대로 MIXED로 적는다** |

**MIXED를 반올림하지 않는 이유**: 애매한 모듈을 CORE로 반올림하면 위반 수가 부풀고, ADAPTER로
반올림하면 위반이 숨는다. 둘 다 EOS-67의 baseline 설계를 잘못 이끈다. 34건은 애매한 채로 남겼다.

**수학 신호는 근거이지 판정이 아니다.** 스캔이 재는 `sympy` import 수와 수학 어휘 밀도는
배정을 *뒷받침*할 뿐 결정하지 않는다. 밀도 0이어도 ADAPTER인 모듈이 있고(수학 엔티티를 실어
나르는 순수 적재기 — `l1.formula_graph`), 밀도가 높아도 CORE인 모듈이 있다(수학 코퍼스를
다루는 범용 하네스). 배정은 사람이 하고 근거만 기계가 잰다.

---

## §2. 계획서 100 §3.7 항목 ↔ 현행 패키지 대응

### EOS Core 14항목

| 계획서 Core 항목 | 현행 좌석 | 상태 |
|---|---|---|
| Identity | `security` · `consent` · `consent_grant` · `db.models.user*` | INFRA로 분류(횡단) |
| Curriculum | `l1.curriculum` · `l1.standards` · `db.models.curriculum_framework` | CORE ✓ |
| Knowledge Graph | `l1.atom_graph` · `l1.concept_graph` · `l1.skill_graph` · `l1.concept_atom_crosswalk` | CORE ✓ |
| Learning Model | `l2` 전체(22모듈) | CORE ✓ — 수학 신호 **0건** |
| Assessment | `l2.ability_estimation` · `l2.irt` · `l2.item_calibration` · `l3.pedagogy`(예심) | CORE ✓ |
| Recommendation | `l2.prerequisite_recommendation` · `l2.weak_concept_recommendation` · `l2.learning_path` | CORE ✓ |
| Content | `l1.concept_content` · `l1.problem_bank` · `l3.render` · `l3.dsl` | CORE(dsl은 MIXED) |
| Pedagogy | `l4`(polya·socratic·lthc·pedagogy) · `l1.pedagogy` | CORE ✓ |
| AI Orchestration | `l3.router` · `l3.providers` · `l3.pipeline` · `l3.cache` · `l3.queue` | CORE ✓ |
| Event | `schema.analytics_event` · `l2.evidence_event_store` · `db.models`(이벤트 테이블) | CORE ✓ |
| Analytics | `l2.learning_metrics_rollup` · `ops` | CORE / INFRA |
| QA | `l3.pedagogy`(예심·검수) · `harness`(게이트) | CORE / INFRA |
| Versioning | `schema`(schema_version) · alembic · `l3.prompt_assets` | 분산 — EOS-44/47/49 소유 |
| Security | `security` · `privacy` | INFRA ✓ |

**판정**: 14항목 중 **좌석이 없는 항목은 0건**이다. Core 기능은 전부 실재하며, 문제는 부재가
아니라 *섞임*(§4)이다.

### Math Adapter 10항목

| 계획서 Adapter 항목 | 현행 좌석 | 배정 |
|---|---|---|
| Math AST | `l3.speech`(AST→낭독) · `l3.equivalent`(정규화) | ADAPTER ✓ |
| LaTeX | `l3.render` 경유 · `schema.problem` 필드 · `l1.formula_graph` | 분산 — MIXED 다수 |
| Equation equivalence | `l3.equivalent`(26모듈·12,119loc) | ADAPTER ✓ |
| Symbolic manipulation | `l3.symbolic_equivalence` | ADAPTER ✓ |
| Graph rendering | `l3.visualization`(명세만) + 클라 렌더 | CORE — 명세는 구조라 중립 |
| Geometry representation | **좌석 없음** | 미구현(현행 코퍼스 범위 밖) |
| Proof structure | **좌석 없음** | 미구현(Lean4 보류 상태) |
| Mathematical expression parsing | `l5.ocr` · `l3.speech_parse` | ADAPTER ✓ |
| Math misconception detectors | `l4.misconception.wrong_form_match` (+shadow harvest) | ADAPTER ✓ |
| Math problem validators | `l3.verify_answer` · `verify_step` · `verify_final_answer` · `verify_solution` · `verifier` · `solution_set` · `finite_probability` · `statistical_claim` | ADAPTER ✓ |

**판정**: 10항목 중 **8건 좌석 실재 · 2건 미구현**(Geometry·Proof). 미구현 2건은 갭이 아니라
현행 범위 밖이다 — 앵커 6개(EOS-51 §2)에 기하 증명 단원이 없다.

---

## §3. 계층별 배정 실측

스캔 출력(`--json`) 집계. 어휘 밀도는 근거 자료다(§1 단서).

> **2026-08-31 갱신**: `EOS-66` 착지로 2모듈이 `BOUNDARY_MAP`에 추가됐다 —
> `schema.subject_adapter`(CORE·계약) · `l4.subject_adapter_math`(ADAPTER·구현). 그만큼
> 합계가 늘었고 **위반 수는 15로 불변**이다(어댑터는 ADAPTER→CORE 방향으로만 의존).

| 계층 | CORE | ADAPTER | MIXED | INFRA |
|---|---|---|---|---|
| `l1` 데이터 기반 | 75모듈 / 13,946 loc | — | 6 / 608 | — |
| `l2` 학습자 모델 | **22 / 5,035** | — | — | — |
| `l3` 생성·검증 | 39 / 8,910 | **39 / 19,938** | 15 / 3,019 | — |
| `l4` 교수학 | **77 / 14,920** | 3 / 485 | 4 / 588 | — |
| `l5` 상호작용 | 1 / 18 | 9 / 1,605 | — | — |
| `l6` 응용 모드 | **17 / 2,837** | — | — | — |
| `api` | 37 / 15,814 | — | 3 / 462 | — |
| `schema` | 33 / 7,194 | — | 6 / 3,549 | — |
| `db`·`ops`·`privacy`·`harness`·`whs` | — | — | — | 166 / 53,871 |
| **합계** | **301 / 68,732** | **51 / 22,028** | **34 / 8,226** | **174 / 58,587** |

> **이 표는 스냅샷이다** — 머지마다 수치가 바뀐다(2026-08-31만 해도 세 번 갱신했다).
> 판정을 다시 뽑으려면 `python3 scripts/analysis/eos_core_adapter_boundary_scan.py`를
> 돌린다. 표를 손으로 맞추기보다 **불변량**을 보는 편이 낫다 — CORE의 `sympy` import 0건,
> `l2`·`l6`의 수학 신호 0건, 위반 **1건**(EOS-69 상환 후 잔여 = C분류 OCR 1건).
>
> **2026-09-01 갱신(EOS-69)**: 모듈 2개가 `BOUNDARY_MAP`에 추가됐다 — `korean`(CORE·어문
> 유틸·7계층 최하위) · `subject_registry`(INFRA·조립 지점). 위 표의 계층별 수치는 2026-08-31
> 스냅샷 그대로이며(재전사 미실시), 변한 것은 위반 수(15→1)다.

**교차 검증 — CORE의 `sympy` import는 0건이다.** 전체 27건의 sympy import 중 ADAPTER 18 ·
MIXED 7 · INFRA 2(하네스)로 갈렸고 CORE는 정확히 0이다. 배정을 손으로 했는데 독립 신호가
경계와 일치했다는 뜻이라, 배정이 자의적이지 않다는 근거로 삼을 수 있다.

**가장 깨끗한 계층**: `l2`(학습자 모델)와 `l6`(응용 모드)는 수학 어휘·sympy 전부 0이다.
Physics를 붙일 때 **이 두 계층은 손대지 않아도 된다** — 계획서 100 §4-⑥의 합격 기준
("Math가 제대로 동작하고, Physics를 붙일 때 Core를 뜯지 않아도 되는 수준")이 이미 성립한 구역이다.

**가장 섞인 계층**: `l3`. 한 계층에 AI 오케스트레이션(CORE)과 수학 검증(ADAPTER)이 39:39로
동거한다. 경계선은 계층 사이가 아니라 **`l3` 한가운데를 지난다** — 7계층 축(현행 import-linter
계약)이 이 축을 볼 수 없는 이유이자, EOS-67이 별도 계약이어야 하는 이유다.

---

## §4. CORE → ADAPTER import 위반 — 15건 → **1건** (EOS-69 상환)

`EOS-67`의 baseline 설계 근거(EOS-65 acceptance ②)이자, `EOS-69`의 작업 목록이었다.

**결론(당시)**: baseline 허용이 필요했다 — 위반이 0이 아니라 계약을 걸면 즉시 CI 적색이었으므로,
15건을 만료 있는 baseline으로 동결하고 EOS-69가 갚는 순서를 택했다. **결론(현재)**: 그 빚은
14건(8간선) 상환됐고 1건(1간선)이 남았다.

### 상환 결과 (2026-09-01 실측)

| 성격 | 당시 | 현재 | 수단 |
|---|---:|---:|---|
| **A. 진성 위반** — Core가 수학 검증을 직접 호출·소비 | 11 | **0** | 호출 의존은 `SubjectAdapter` Protocol 경유(DI), 타입 의존은 중립 뷰 |
| **B. 오배치 유틸** — 경계가 아니라 파일 위치 문제 | 3 | **0** | `l3.equivalent.josa` → `whymath_backend.korean.josa` 이사 |
| **C. DI 배선** — 어댑터 부품 타입 참조 | 1 | **1** | 미해소(범위 밖 — 아래) |

### A분류 11건의 처리 — 부류가 둘이었다

A분류를 "전부 메서드 호출"로 읽으면 틀린다. 실측상 두 부류가 섞여 있었고, 수단도 달라야 했다.

| 위반 | 부류 | 판정 근거 | 수단 |
|---|---|---|---|
| `api.coach` → `verify_final_answer`(2심볼) | **호출** | `verify_final_answer(...)`를 실제로 부른다 | 계약 확장 `evaluate_final_answer` + DI |
| `l3.render.adapters` → `verify_answer`(1) | **호출** | `verify_answer(...)` 호출 | 기존 `evaluate_answer` 경유 |
| `l3.render.adapters` → `equivalent.rephrase`(2) | **호출** | `extract_equation`·`classify_invariance_failure` 호출 | 계약 확장 `check_content_seal` |
| `l3.pedagogy.slot_generator` → `symbolic_equivalence`(2) | **호출** | `identity_status(...)` 호출 | 계약 확장 `check_equivalence_claim` |
| `api.coach` → `verify_solution`(1) | **타입** | 함수 호출 0 — 결과 타입 주석으로만 소비 | 중립 뷰 `SolutionVerificationView` |
| `l6.blueprint.assembly` → `verify_solution`·`verify_step`(3) | **타입** | `partial_credit`이 수학 함수를 부르지 않고 `first_incorrect_index`·`state`를 **읽기만** 한다 | 중립 뷰(구조적 Protocol) |

**타입 의존을 Protocol 메서드로 밀어 넣지 않은 이유**: 흡수되지 않는다. `partial_credit`이
필요한 것은 "무엇을 해 달라"가 아니라 "결과를 어떤 모양으로 읽을 것인가"다. 억지로 메서드를
만들면 계약 표면만 부풀고(→ 새 과목마다 `NotImplementedError` 좌석 증가) 실제 의존은 그대로
남는다. 반대로 뷰는 **변환기가 아니라 구조적 Protocol**이라 값이 복사되지 않는다 — 3상태를
접을 수 있는 지점이 아예 생기지 않는다(변환기를 뒀다면 그 함수가 접힘 위험 지점이 됐을 것).

### 계약 표면 3 → 6 (그리고 왜 그 3개인가)

`SubjectAdapter` v1은 3메서드(`evaluate_answer`·`detect_misconception`·`validate_problem`)였고
EOS-69가 3개를 더했다. 추가 기준은 **(a) 과목 보편성 (b) 실재 위임 대상 (c) 실재 Core 호출부**
전부 통과이며, 근거 산문은 `schema/subject_adapter.py` 모듈 docstring이 정본이다. 요약:

- `evaluate_final_answer` — "답이 *정답 키*와 같은가"는 "답이 *조건*을 만족하는가"와 다른 질문이다
  (조건 없는 객관식엔 후자를 못 쓰고, 정답 키 없는 생성 문항엔 전자를 못 쓴다).
- `check_equivalence_claim` — 자체 저작 콘텐츠 검수의 "이 주장이 참인가". 4상태 → 3상태 매핑에서
  접히는 것은 *두 종류의 모름*(undecidable·parse_error)뿐이다.
- `check_content_seal` — "파생 텍스트가 원문 표기를 훼손했는가". 표기 지식이 있는 쪽만 답할 수 있다.

`explain`은 여전히 미포함이다 — 위임할 공개 진입점이 0건이라 기준 (b) 미통과(좌석만 는다).

### 남은 1건 — C분류를 EOS-69 범위 밖으로 판정한 근거

`api._ocr_state` → `l5.ocr.factory.OcrComponents`. **호출이 아니라 타입 주석 1건**이다
(`get_ocr_components`의 반환 타입·`set_ocr_components`의 인자). 남긴 이유:

1. **과목 능력이 아니다.** `OcrComponents`는 앱 수명 동안 공유되는 *자원 묶음*(모델 1회 로드)이지
   "과목이 답할 수 있는 질문"이 아니다. `SubjectAdapter`에 OCR 메서드를 넣으면 기준 (a)를
   억지로 통과시키는 셈이 되고, 실제로 필요한 것(부품 보유·503 사유 구분)은 계약이 못 담는다.
2. **해소 수단이 다른 축이다.** app.state 보유자를 *중립 부품 계약*으로 일반화하거나
   `api.ocr`(MIXED)과 함께 모듈 분할해야 한다 — 이 태스크가 세운 과목 계약과는 별개 설계다.
3. 그래서 baseline 1줄로 남기고 소유자 미지정으로 표기했다(pyproject 그룹 ② 주석).

### 이 숫자의 한계 (정직한 공백)

- **MIXED 34모듈은 위반 계산에서 빠진다.** CORE로 배정된 것만 출발점으로 센다. MIXED를 CORE로
  간주하면 위반은 늘어난다 — 즉 **남은 1건도 하한이다.**
- **정적 import만 잡는다.** 동적 import·문자열 경유 참조·DI 컨테이너 등록은 안 보인다.
  EOS-69의 조립 지점(`subject_registry`)은 이 사각을 **일부러 쓰지 않았다** — 기본 어댑터를
  `importlib.import_module` 문자열로 만들면 스캔도 `lint-imports`도 그 간선을 못 보게 되는데,
  그건 도구의 판정을 우회해 의존을 안 보이게 만드는 것이다. 정직한 정적 import로 두고 7계층
  계약에 **명시 유예 1줄**(조립 지점 예외)을 남겼다.
- **재수출(re-export) 경유는 원 소유 패키지로 귀속되지 않는다.** `__init__`이 다시 내보낸 심볼을
  통해 들어가는 간접 경로는 이 스캔의 사각이다.

---

## §5. 집행 — `EOS-67`(계약) + `EOS-69`(상환)

**정적 강제가 착지했다.** `src/backend/pyproject.toml`에 import-linter `forbidden` 계약 2건이
서고, CI lint 스텝(`run: lint-imports`)이 매 PR에서 이를 판정한다.

| 계약 | source | 유예 | 상태 |
|---|---|---|---|
| **baseline 0 — 이미 깨끗한 구역** | `korean` · `l1` · `l2` · `schema` | **없음** | KEPT. 이 구역이 수학을 새로 끌어오면 즉시 적색 |
| **baseline 있음 — EOS-69가 해소** | `api` · `l4` · `l6` · `l3` CORE 키 20 | 15 | KEPT (15 ignored) |
| **7계층 단방향** | `api`…`schema`·`korean` | **1**(조립 지점) | KEPT (1 ignored) |

**유예 15건의 성격**(pyproject 그룹 ①②):

- **그룹 ① 구조적 제외 14건 — 빚이 아니다.** 출발점이 ADAPTER(6) 또는 MIXED(8)인 간선이다.
  계약은 "CORE로 지정한 모듈"만 구속하므로 애초에 위반이 아니고, 부모 패키지를 source로 잡은
  탓에 걸릴 뿐이다. EOS-69로 3줄 늘었다 — 어댑터가 위임 대상을 3개 더 부르게 됐기 때문이며
  (`verify_final_answer`·`symbolic_equivalence`·`equivalent.rephrase`), ADAPTER→ADAPTER라
  정상이다.
- **그룹 ② baseline 1건 — 남은 빚.** 9간선에서 8간선이 상환됐다(§4). 남은 `api._ocr_state →
  l5.ocr.factory`는 과목 계약이 흡수할 대상이 아니라 소유자 미지정으로 남겼다.

**7계층 계약의 유예 1건**(신규): `subject_registry → l4.subject_adapter_math`. DI 좌석이 기본
구현체를 만들어야 해서 남는 **의존성 역전의 정적 그림자**다(논리 방향은 이미 Core ← 구현체).
`layers` 계약은 간접 체인까지 보므로 이것이 `l3 → l4`로 비친다. 유예의 *출발점이 계층 밖*
(조립 지점)이라는 점이 "그냥 역방향 의존"과 다른 지점이고, 그 사실을
`tests/infra/test_eos_boundary_contract_wiring.py`가 기계로 동결한다(유예 1건·출발점 검사·
만료 정책 검사).

**만료는 날짜가 아니라 기계다.** `unmatched_ignore_imports_alerting`이 기본 `ERROR`이므로,
어떤 간선을 없애면 대응하는 유예 줄이 매치되지 않아 `lint-imports`가 실패한다 — CI가 "이 줄을
지워라"라고 말한다. 실측 확인(EOS-67 뮤테이션 C): `l6.blueprint.assembly`의 `verify_step`
import를 제거하니 `No matches for ignored import ...`로 exit 1. EOS-69 상환 때도 같은 일이
실제로 일어났다 — 간선을 없앤 뒤 유예 줄을 지우기 전까지 `lint-imports`가 적색이었다(만료
장치가 살아 있음의 라이브 증거). 사람이 읽을 재확인 지점은 **G1(9/27)**.

**드리프트 방지**: `tests/infra/test_eos_boundary_contract_wiring.py`가 pyproject의 forbidden
목록을 `BOUNDARY_MAP`(정본)과 대조하고, CI가 `lint-imports`를 실제로 부르는지, 만료 정책이
꺼지지 않았는지, 7계층 유예가 조립 지점 1건뿐인지를 함께 동결한다. pyproject만 고치고 정본을
안 고치면 CI가 적색이 된다.

**측정 축의 한계(명시)**: 계약은 `allow_indirect_imports = true`로 **직접 import만** 판정한다.
경계 스캔이 AST 직접 import를 세므로 축을 맞춘 것이다 — 간접까지 세면 계약과 이 문서가 서로
다른 숫자를 말하게 된다. 따라서 `api.coach → l4 → l4.solution_coaching → wrong_form_match`
같은 *경유* 의존은 이 계약이 잡지 않는다. 그 축은 MIXED 모듈 해소와 함께 다룰 별개 문제다.
**같은 이유로 `l3.render.adapters → subject_registry → l4.subject_adapter_math`도 EOS 계약은
위반으로 세지 않는다**(직접 간선이 아니다) — 그 체인을 보는 것은 7계층 `layers` 계약이고,
거기서는 명시 유예로 판정을 남겼다.

**재측정**: `python3 scripts/analysis/eos_core_adapter_boundary_scan.py` — 위반 수 변화가 진척
지표이고, `lint-imports`가 그 진척을 강제한다.

---

## §6. 재현

```bash
# [실행 시스템: 저장소 루트 — Linux/WSL 또는 Windows PowerShell]
cd C:\Users\kiki\Desktop\__AI\WhyMath   # PowerShell인 경우
python3 scripts/analysis/eos_core_adapter_boundary_scan.py
# 배정표·위반표·오류 수를 stdout으로, 진행 로그를 stderr로 낸다
python3 scripts/analysis/eos_core_adapter_boundary_scan.py --json out.json --markdown out.md
```

종료코드는 **스캔 성공 여부**만 뜻한다(0=측정됨·1=측정 실패). **위반 수로 exit 1을 내지 않는다** —
이 스크립트는 게이트가 아니라 계측기이며, 게이트는 EOS-67이 세운다. 측정 자체가 실패하면
"위반 0"이 아니라 exit 1이 나오게 설계했다(측정 실패가 통과로 위장되면 안 된다).

**변별력 확인 기록** (2026-08-31): `l2.bkt`(CORE)에 `l3.symbolic_equivalence`(ADAPTER) import를
주입 → 위반 **15 → 16**, 표에 `l2.bkt` 행 출현. cp 백업으로 원복 → **15**, `git diff` 공집합
확인. (원복을 `git checkout --`로 하지 않은 이유 = 2026-08-10 미커밋 구현분 소실 사고 규칙.)

---

## §7. 다음 검토일

**G1(2026-09-27)** — 차단 조건 "Core→Math 정적 의존 0"의 판정 시점. 그때 확인할 것:

1. 경계 스캔 위반 수(현재 1) — C분류 OCR 축이 착수됐는가.
2. pyproject 그룹 ② 유예 줄 수(현재 1) — 1보다 크면 새 빚이 생긴 것이다.
3. MIXED 34모듈(§3) — 위반 수의 하한성을 만드는 미판정 구역. 이쪽은 EOS-69 범위 밖이었다.

배정 자체의 변경은 `BOUNDARY_MAP`을 고치고 본 문서를 재전사한다.
