# 소단원 DSL 파일럿 v1 — 데이터 카드

> **요약**: 소단원(unit) 명세 DSL(`unit/0.1`)의 **E2E 확인용 단일 파일럿**. 이차함수의 최대·최소
> (공통수학1, 성취기준 `[10공수1-02-06]`)를 4목표(CONCEPT/PROCEDURE/REPRESENT/MODELING)로 분해한
> 소단원 1건·학습목표(Objective) 4건이 전부다. `docs/architecture/01_data_foundation.md` 원칙
> ("모든 데이터셋은 `docs/data/[name].md`에 카드 작성")에 대응 카드가 없었던 공백을 이번 갭
> 리뷰(`curriculum_module_gap_review.md` §정정)에서 메운다.

---

## 1. 출처·프로비넌스

| 항목 | 값 |
|---|---|
| 형태 | 와이매스 자체 저작 소단원 명세 DSL(YAML) |
| 성취기준 코드 인용 | `[10공수1-02-06]` — NCIC 공공누리 제1유형 사실정보 인용(`data/corpus/standards_v1/standards.json`) |
| 개념 노드 인용 | `10공수1-02-06-1/2/3` — 원자 백본(`data/corpus/atom_graph_v1/graph.json`) 실측 확인 |
| 저작(목표 서술) | 와이매스 자체 저작(학습목표 서술은 성취기준 유래 자체 분해 — 검정교과서·평가원·EBS 본문 미포함) |
| 산출물 | `data/corpus/units_v1/{quadratic_maxmin.unit.yaml, _provenance.json}` (**커밋됨**) |
| 컴파일러 | `soraw-dsl/0.1`(`src/backend/whymath_backend/l1/pedagogy/unit_compiler.py`) — E2E 확인 완료 |

---

## 2. 스키마 (DSL → 모델)

| DSL 필드 | 모델(`db/models/pedagogy_dsl.py`) | 비고 |
|---|---|---|
| `unit_id`, `unit_version` | `UnitSpec` 복합 PK | 버전 보존(비교 연산은 없음 — `curriculum_module_gap_review.md` §4-①) |
| `standard_codes[]`, `concept_nodes[]` | `UnitSpec.standard_codes[]`·`concept_nodes[]` | 성취기준·원자 백본 느슨참조 |
| `objectives[].suffix/statement/standard_code/source_verb/k_type/concept_nodes` | `LearningObjective` | `id` = `{unit_id}:{unit_version}:{suffix}` |

## 3. 규모 (실측)

`_provenance.json`: `{"units": 1, "objectives": 4}` — 성취기준 895건 중 **1건**(≈0.1%)만 이
DSL로 분해됐다. 4목표는 CONCEPT("정의역 제한 최대·최소의 뜻")·PROCEDURE("최댓값·최솟값 구하기")·
REPRESENT("제한구간 그래프 해석")·MODELING("실생활 최적화").

## 4. 커버리지 확대 계획

이 카드가 서술하는 것은 **파일럿 그 자체**다 — 확대 파이프라인(자동 생성 여부·순서)은
`docs/architecture/curriculum_module_gap_review.md` §3 D2(`CUR-02-objective-coverage-observability`)
·§4-⑤·§5-⑥에서 다룬다. 이 카드는 그 관측 대상 데이터의 스냅샷 기록이며 자체 태스크를 갖지 않는다.
