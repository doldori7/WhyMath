# 수식 표기 계약 — SymPy(동치 권위) ↔ mathjs(렌더 전용)

> **상태**: 구현(슬라이스) · **계층**: 횡단(L3 backend · L5 web) · **작성일**: 2026-06-30
> **상위**: `math_dsl_risk_register.md`(부채 Q10-⑦ "동치 권위 1개")·`math_dsl_remediation_design.md`(설계 2).
> **공유 fixture**: `data/notation_contract.json`(단일 진실) · **golden test**:
> `tests/backend/l3/test_notation_contract.py`(py) ↔ `src/web/graphing-calculator/test/notation_contract.test.js`(js).

---

## 1. 권위 경계 (협상 불가)

- **SymPy = 수식 동치·정오 판정 단일 권위.** `l3/verify_step.py`(단계 동치)·`l3/verify_answer.py`
  (Tier1 수치 검산). `sympify(expr, convert_xor=True)` + `expand`/`simplify().is_zero`.
- **mathjs = 렌더·수치 평가 전용.** `src/web/graphing-calculator/src/lib/graph2dSpec.js`·`mathExpr.js`.
  `math.parse`/`compile`/`evaluate`·`toTex`. **동치/정오 판정에 절대 관여하지 않는다.** `sameGraph`의
  수치 비교는 렌더 보조이지 정오 근거가 아니다.
- 부채(`risk_register` Q6·Q10-⑦)는 "엔진 중복"이 아니라 **두 파서가 같은 표기를 다르게 해석하는
  drift**다. 이 계약 + golden test가 그 drift를 막는다.

## 2. 공유 표기 (canonical)

| 표기 | 규칙 | SymPy | mathjs |
|---|---|---|---|
| 거듭제곱 | **caret `^` 표준** | `convert_xor=True`로 `^`·`**` 둘 다 읽음 | `^`만 인식 — 어댑터가 `**`→`^` 변환(`graph2dSpec.js`) |
| 곱 | **명시 `*` (canonical)** | `sympify`는 implicit mult 미지원 → `*` 필수 | implicit(`2x`)도 관용하나 계약은 `*`만 |
| 표준함수 | `sin·cos·tan·sqrt·log·exp` 등 | 지원 | 지원 |
| 변수 | ASCII(`x·y·a·b·t`) | 지원 | 지원 |

**canonical = 명시 `*` + caret `^` + ASCII.** 이 형태에서 두 파서가 *같은 입력을 같은 수치로* 해석함을
golden test가 보증한다(`numeric_cases`). 동치 판정(`equivalence_cases`)은 backend 권위만 검증한다.

## 3. 계약 범위 밖 (후속·web 입력 관용)

- **implicit multiplication**(`2x`·`(x+1)(x-1)`): mathjs는 관용하나 SymPy `sympify`는 미지원 →
  공유 계약 아님. 학생/LLM 입력에서 implicit가 들어오면 *백엔드 진입 전* 명시 `*`로 정규화해야 한다
  (정규화 헬퍼는 후속).
- **unicode**(`π`·`α`): mathjs 미인식(`pi`·`alpha` 철자 필요). 입력 정규화 후속.
- **문자 정규화**(NFC/NFD·전각): 후속.

## 4. Golden test 운영

- 단일 fixture `data/notation_contract.json` 을 양 CI가 각자 읽는다(backend `pytest`·web `vitest`).
- py: `numeric_cases`를 `sympify(...).evalf` 로 평가해 기대값 일치 + `equivalence_cases`를 `verify_step`로 판정.
- js: `numeric_cases`를 `math.evaluate`로 평가해 기대값 일치 + `**`→`^` 어댑터 1건. (동치 판정 없음.)
- 새 표기 케이스는 **fixture에만 추가**하면 양측이 자동 검증한다(계약 단일 출처).

---

## 참고
- 코드: `l3/verify_step.py`·`l3/verify_answer.py`·`src/web/graphing-calculator/src/lib/{graph2dSpec,mathExpr}.js`
- 상위: `math_dsl_risk_register.md`·`math_dsl_remediation_design.md`
- 변경 이력: v0.1 (2026-06-30 — 계약 명문화 + golden test 착수)
