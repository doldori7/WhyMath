# EOS Core ↔ Math Adapter 경계 — 현행 패키지 배정표 v1 (EOS-65)

> **지위**: `EOS-65-core-adapter-boundary-map` 산출물. `EOS-66`(SubjectAdapter 계약)·
> `EOS-67`(import-linter 강제)의 **선결 입력**이며, G1(2026-09-27) 차단 조건
> "Core→Math 정적 의존 0"의 *판정 기준 그 자체*다.
>
> **배정 정본은 이 문서가 아니라 코드다** — `scripts/analysis/eos_core_adapter_boundary_scan.py`
> 의 `BOUNDARY_MAP`이 단일 진실 원천이고, 본 문서는 그 표를 전사·해설한다(선례:
> `eos_anchor_asset_audit.py`의 `ANCHOR_DEFS`가 EOS-51 앵커 동결 정본). 배정을 바꾸려면
> 스크립트를 고친다 — 문서만 고치면 이중 진실 원천이 된다.
>
> ## ⚠️ 정본화 ≠ 집행 — 이 표는 **아무것도 강제하지 않는다**
>
> 이 문서와 스캔 스크립트는 *계측기*다. 배정을 기계가 강제하는 지점은 **`EOS-67`**
> (import-linter forbidden 계약 + CI 배선 동결)이며, 그것이 착지하기 전까지:
>
> - ~~새 코드가 경계를 넘어도 **CI는 통과한다**.~~ → **2026-08-31 `EOS-67` 착지로 해소** —
>   import-linter 계약 2건이 CI lint 스텝에서 판정한다(§5). 아래 두 줄은 여전히 유효하다.
> - 아래 "위반 15건"은 *막고 있는 상태에서 남은 15건*이 아니라 **아무도 막지 않은 상태의 15건**이다.
> - 따라서 이 문서의 존재를 근거로 "경계가 있다"고 말하면 안 된다. 지금 있는 것은 **경계의 정의**뿐이다.
>
> 대조 시점: 2026-08-31 · main `3f512962` 기준 · 스캔 대상 **556 모듈 / 155,435 LOC** · 스캔 오류 0.

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
> `l2`·`l6`의 수학 신호 0건, 위반 15건(EOS-69가 줄인다).

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

## §4. CORE → ADAPTER import 위반 — 실측 15건

`EOS-67`의 baseline 허용 필요 여부를 판정하는 근거다(EOS-65 acceptance ②).

**결론: baseline 허용이 필요하다.** 위반이 0이 아니므로, EOS-67이 계약을 걸면 **즉시 CI가 적색**이
된다. 15건을 고치고 계약을 거는 것과, 계약을 걸며 15건을 만료 있는 baseline으로 동결하는 것 중
후자를 권고한다(§5).

### 15건 전수 — 성격별 3분류

| 성격 | 건수 | 위반 | 판단 |
|---|---:|---|---|
| **A. 진성 위반** — Core가 수학 검증을 직접 호출 | **11** | `api.coach` → `verify_final_answer`(2)·`verify_solution`(1) · `l6.blueprint.assembly` → `verify_solution`(1)·`verify_step`(2) · `l3.pedagogy.slot_generator` → `symbolic_equivalence`(2) · `l3.render.adapters` → `verify_answer`(1)·`equivalent.rephrase`(2) | EOS-66 SubjectAdapter가 흡수해야 할 정확히 그 지점 |
| **B. 오배치 유틸** — 경계 문제가 아니라 파일 위치 문제 | **3** | `l3.render.adapters` → `l3.equivalent.josa`(`eul_reul`·`eun_neun`·`i_ga`) | `josa.py`는 **한국어 조사 받침 판별**(모듈 docstring 자인)로 과목과 무관하다. 수학 패키지 안에 살 이유가 없다 — 옮기면 위반 3건이 소멸한다 |
| **C. DI 배선** — 어댑터 팩토리 참조 | **1** | `api._ocr_state` → `l5.ocr.factory.OcrComponents` | 구현체 직접 참조. EOS-66 Protocol 경유로 바꾸면 해소되는 부류 |

### A분류가 말하는 것

11건 전부가 **"Core가 정답을 판정하려고 수학 모듈을 부른다"**는 한 가지 형태다. `api.coach`(학생
대화 표면)·`l6.blueprint.assembly`(모드 조립)·`l3.render.adapters`(콘텐츠 렌더)는 셋 다 과목을
몰라야 하는 자리인데, 셋 다 수학 검증 함수를 직접 import한다.

이것이 **EOS-66이 필요한 이유의 실측 증거**다. `SubjectAdapter.evaluate_answer()`가 있었다면
이 11건은 Protocol 호출 1개로 대체됐을 자리다. 반대로 EOS-66 없이 EOS-67 계약만 걸면 이 11건은
고칠 방법이 없어 baseline에 영구 동결된다 — **순서가 EOS-66 → EOS-67이어야 하는 근거**다.

### 이 숫자의 한계 (정직한 공백)

- **MIXED 34모듈은 위반 계산에서 빠진다.** CORE로 배정된 것만 출발점으로 센다. MIXED를 CORE로
  간주하면 위반은 늘어난다 — 즉 **15는 하한이다.**
- **정적 import만 잡는다.** 동적 import·문자열 경유 참조·DI 컨테이너 등록은 안 보인다.
- **재수출(re-export) 경유는 원 소유 패키지로 귀속되지 않는다.** `__init__`이 다시 내보낸 심볼을
  통해 들어가는 간접 경로는 이 스캔의 사각이다.

---

## §5. 집행 — `EOS-67` 착지 (2026-08-31)

**정적 강제가 착지했다.** 이 문서 머리의 "⚠️ 정본화 ≠ 집행" 경고는 §5 범위에서는 **해소됐다** —
`src/backend/pyproject.toml`에 import-linter `forbidden` 계약 2건이 서고, CI lint 스텝
(`run: lint-imports`)이 매 PR에서 이를 판정한다. 남은 미집행은 §4 A분류의 *경유 배선*(EOS-69)이다.

| 계약 | source | 유예 | 상태 |
|---|---|---|---|
| **baseline 0 — 이미 깨끗한 구역** | `l1` · `l2` · `schema` | **없음** | KEPT. 이 구역이 수학을 새로 끌어오면 즉시 적색 |
| **baseline 있음 — EOS-69가 해소** | `api` · `l4` · `l6` · `l3` CORE 키 20 | 20 | KEPT (20 ignored) |

**유예 20건의 성격은 둘로 갈린다** (pyproject 주석에 그룹 ①②로 분리 표기):

- **그룹 ① 구조적 제외 11건 — 빚이 아니다.** 출발점이 ADAPTER(3) 또는 MIXED(8)인 간선이다.
  계약은 "CORE로 지정한 모듈"만 구속하므로 애초에 위반이 아니고, 부모 패키지를 source로 잡은
  탓에 걸릴 뿐이다. MIXED를 지금 강제하면 §1이 유보한 판정을 조기에 강요하게 된다.
- **그룹 ② baseline 9건 — 이것이 빚이다.** §4 A·B·C분류의 심볼 15건을 모듈 단위로 축약한 수다
  (`api.coach` 3심볼→2간선 · `l6.blueprint.assembly` 3→2 · `l3.render.adapters` 6→3 ·
  `l3.pedagogy.slot_generator` 2→1 · `api._ocr_state` 1→1). 소유자는 **`EOS-69`**.

**만료는 날짜가 아니라 기계다.** `unmatched_ignore_imports_alerting`이 기본 `ERROR`이므로,
EOS-69가 어떤 간선을 없애면 대응하는 유예 줄이 매치되지 않아 `lint-imports`가 실패한다 —
CI가 "이 줄을 지워라"라고 말한다. 실측 확인(뮤테이션 C): `l6.blueprint.assembly`의
`verify_step` import를 제거하니 `No matches for ignored import ...`로 exit 1. 유예가 조용히
눌러앉을 수 없다("만료 없는 유예 금지"의 코드 집행). 사람이 읽을 재확인 지점은 **G1(9/27)** —
그때까지 9줄이 그대로면 EOS-69 진척이 0이라는 뜻이다.

**드리프트 방지**: `tests/infra/test_eos_boundary_contract_wiring.py`가 pyproject의 forbidden
목록을 `BOUNDARY_MAP`(정본)과 대조하고, CI가 `lint-imports`를 실제로 부르는지, 만료 정책이
꺼지지 않았는지를 함께 동결한다. pyproject만 고치고 정본을 안 고치면 CI가 적색이 된다.

**측정 축의 한계(명시)**: 계약은 `allow_indirect_imports = true`로 **직접 import만** 판정한다.
경계 스캔이 AST 직접 import를 세므로 축을 맞춘 것이다 — 간접까지 세면 계약과 이 문서가 서로
다른 숫자를 말하게 된다. 따라서 `api.coach → l4 → l4.solution_coaching → wrong_form_match`
같은 *경유* 의존은 이 계약이 잡지 않는다. 그 축은 MIXED 모듈 해소와 함께 다룰 별개 문제다.

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

`EOS-67` 착지 시 — baseline에 실제로 들어간 항목과 이 문서 §4의 15건을 대조하고, 해제된 건수를
§4 표에 갱신한다. 배정 자체의 변경은 `BOUNDARY_MAP`을 고치고 본 문서를 재전사한다.
