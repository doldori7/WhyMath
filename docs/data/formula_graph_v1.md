# 와이매스 수식 그래프 v1 — 데이터 카드

> **FormulaNode canonical-only 코퍼스**(리치 Part 2 Phase 5a). canonical 수식 25개 · 8 family ·
> 전량 자체작성(수학적 사실·표준 표기). 소비처 연동(`formula_refs`·resolution)은 Phase 5b.

---

## 1. 출처·프로비넌스

- **출처**: 와이매스 **자체작성** canonical 수식 택소노미. 수식은 **수학적 사실·표준 표기**이므로
  저작권 무관(교과서·평가원 기출 *문항 본문* 미포함 — `standard_codes`는 연결 코드만).
- **입력**: `data/corpus/formula_graph_v1/formulas.jsonl`(저작) → `graph.json`+`_provenance.json`
  (`python -m data_pipeline.formula_graph transform-v1` 생성·sha256·결정론).
- **품질**: v1=`ai_estimated`(전문 검수 전·backend 프로젝션 `review_status`에 정직 표기).

## 2. 스키마 (`FormulaNode`)

| 필드 | 타입 | 비고 |
|---|---|---|
| `formula_id` | **PK** `str` | `formula.<slug>`(예 `formula.quadratic.roots`). **사람 관리 안정 code**(SymPy 계산값 아님·ID≠Signature) |
| `name_ko` | `str` | 표시명(한국어·자체작성) |
| `family` | `str` | 수식 family 그룹(곱셈공식·인수분해공식·근의공식·지수로그·삼각공식·미적분기본공식·기하공식·수열공식) |
| `latex` | `str` | display LaTeX(자체작성 표준 표기·화면용) |
| `dsl` | `str` | **SymPy-parseable canonical 식**(닫힌 검증 DSL). 동치 판정은 런타임 SymPy 위임 |
| `canonical_signature` | `str \| None` | 검색·dedup **보조** 메타(optional·정체성 아님·계산 backfill=5b) |
| `aliases` | `list[str]` | 같은 canonical 수식의 display 별칭(선택·**변형 열거 아님**) |
| `standard_codes` | `list[str]` | 연결 NCIC 성취기준 코드(선택·본문 미복제) |
| `constraints` | `list[str]` | **성립 조건·사용범위**(자체작성·예 `a ≠ 0`·`진수 > 0`). 무조건 항등식은 `[]`. 유도/증명 슬롯 아님 — 유도는 Theorem/Proof 축(P6·D2) 위임 (S4-06·실측 15/25건) |
| `mnemonic` | `str \| None` | 암기팁(자체작성·표준 정착 구절만 — 신코코신 등·대부분 None·날조 저작 금지) (S4-06·실측 14/25건) |
| `notes` | `str \| None` | 검수 메모(선택) |

**미도입(anti-explosion·SymPy 재구현 금지)**: `equivalence_class`(변형 열거 저장 금지·동치는 SymPy
런타임)·`sympy_repr`(dsl에서 파생). 변형식(변수명·항순서·표기)은 **노드화하지 않는다** — canonical
1개만 노드, 변형은 `l3/symbolic_equivalence.py`가 런타임 판정.

## 3. family (8종·각 ≥2)

곱셈공식(4)·인수분해공식(3)·근의공식(4)·지수로그(4)·삼각공식(3)·미적분기본공식(2)·기하공식(3)·
수열공식(2). = **25 수식**.

## 4. 불변식 (검증)

- `formula_id` **유일**(canonical 중복 금지·`validate_formulas` error).
- `latex`·`dsl` 비어있지 않음(모델 `min_length=1`).
- **dsl SymPy-parseable**: 전 수식 `dsl`이 `to_sympy_source`+`condition_dsl_violation` 통과
  (검증가능·동치는 SymPy 위임) — **backend 거버넌스**(`test_formula_governance`)가 동결
  (data-pipeline은 sympy-free).
- `family_singleton`(warning) 0(전 family ≥2).

## 5. 소비처·경계

- **적재**: `l1/formula_graph/populate.py` → `formula_node` 테이블(PG 프로젝션·code 키 멱등 upsert).
- **경계(5b로 분리)**: `formula_refs`(concept→formula) 대량 매핑·런타임 resolution·Tutor/Verifier
  연동·`canonical_signature` 계산 backfill은 **소비처 실재 시 Phase 5b**(dead code 회피·2a→2b·3→3b 선례).
- **동치 권위**: FormulaNode는 수식의 *정체성·참조*만. 두 식의 동치·거짓 판정은 계속
  `l3/symbolic_equivalence.py`(SymPy 단일 진실·risk_register Q10-⑦) — FormulaNode가 CAS를 흡수하지
  않는다(`math_dsl_evolution.md` §2.1 "SymPy 재구현 금지").

---

**버전**: v1 (Phase 5a·2026-07-08) · 관련: `skill_graph_v1.md`·`problem_type_graph_v1.md`·
`concept_node_layering_decision.md`·`math_dsl_evolution.md`·`math_dsl_risk_register.md`
