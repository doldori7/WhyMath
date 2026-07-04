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

## 3. 계약 범위 밖 — 백엔드 입력 정규화가 canonical로 접음 (2026-07-02 마감)

아래는 *공유 계약*(SymPy↔mathjs interop)의 canonical(explicit `*` + caret + ASCII)이 **아니다** —
계약 canonical은 불변이다. 다만 학생/LLM/OCR의 messy 입력은 *백엔드 진입 시* `l3/symbolic_equivalence.py`
의 `to_sympy_source`(입력 정규화 단일 권위)가 canonical로 접는다(Part 4 항목4 마감·`math_dsl_part4_ast_review.md`).
mathjs(web 렌더)는 무영향 — 전각/그리스/chained는 py-only 정규화다.

- **implicit multiplication**(`2x`·`(x+1)(x-1)`): `identity_status`가 `parse_expr`(`implicit_multiplication`
  변환)로 접는다 — `pregenerate/validator.py`와 동일한 *보수* 선택(함수 적용 병치 `sin x`·순수 문자
  병치 `xy`는 추정 안 함). 공유 계약의 canonical은 여전히 explicit `*`(양 엔진 interop 축).
- **비ASCII 연산자**(`−`U+2212·`×`·`÷`·`·`·`⋅`·`∗`): NFKC가 안 접으므로 `_OPERATOR_MAP`으로 ASCII화.
  가장 흔한 함정은 SymPy가 못 읽는 U+2212 마이너스.
- **unicode 그리스**(`π`·`θ`·`α`): `_GREEK_MAP`(교육 범위 최소)으로 `pi`·`theta`·`alpha` 접기. 전
  알파벳 확장은 후속.
- **문자 정규화**(전각·NFKC): `unicodedata.normalize("NFKC", …)`로 전각(`２ｘ`→`2x`·`（）`→`()`) 접기
  (임베딩 NFKC 정규화 선례와 일관). ⚠️ 위첨자(`²`)는 NFKC가 `2`로 분해하므로 *NFKC 이전*에 `**2`로
  치환한다(순서 잠금).
- **chained equality**(`a=b=c`): `split_relation_chain`/`verify_relation_chain`이 인접 등식 쌍으로 분해해
  `identity_status`(동치 권위 단일)로 판정. 엔드포인트 배선은 후속.

## 4. Golden test 운영

- 단일 fixture `data/notation_contract.json` 을 양 CI가 각자 읽는다(backend `pytest`·web `vitest`).
- py: `numeric_cases`를 `sympify(...).evalf` 로 평가해 기대값 일치 + `equivalence_cases`를 `verify_step`로 판정.
- js: `numeric_cases`를 `math.evaluate`로 평가해 기대값 일치 + `**`→`^` 어댑터 1건. (동치 판정 없음.)
- 새 표기 케이스는 **fixture에만 추가**하면 양측이 자동 검증한다(계약 단일 출처).

## 5. 프레젠테이션 계층(speech) 경계 — 이 계약 밖이 설계상 정상 (2026-07-02 명문화)

수식 음성화(Math-to-Speech·`l3/speech_parse.py`·`l3/speech.py`)는 **이 계약의 당사자가 아니다.**
failure_mode_qa가 invariant ⑪("모든 수식 AST는 notation_contract 안·speech 포함")로 등록했으나,
실측 결과 speech는 SymPy↔mathjs와 **교차검증이 원리적으로 불가·불필요**한 별도 표기 계층이다:

- **입력 언어가 다르다**: 이 계약은 *ASCII 수식 소스*(`x^3`·`3*x^2`)의 SymPy↔mathjs 수치 상호운용이다.
  speech 입력은 *프레젠테이션 LaTeX*(`\frac`·`\sqrt{}`·`\int_a^b`·`\sin`)다.
- **산출이 다르다**: 계약은 수치값(`numeric_cases`)·동치 bool(`equivalence_cases`)로 검증한다.
  speech 산출은 한국어 낭독 문자열(운율 토큰·SSML)이라 "value"도 "equivalent"도 없다 — fixture에
  넣을 케이스 형(型)이 없다.
- **권위가 다르다**: 낭독은 국제 표준 canonical이 부재해 *자체 정본*(교사 검수 골든 코퍼스
  `tests/backend/l3/test_speech_rules.py`의 `HIGH_SCHOOL_GOLDEN` 38케이스 + `test_golden_corpus_size_gate`
  ≥30 동결)으로 검증된다. 이것이 speech의 표기 계약이다.
- **자족 파서(hermetic·의도적)**: speech는 자체 AST·토크나이저·재귀하강 파서를 갖고 SymPy/mathjs/
  `to_sympy_source`를 부르지 않는다 — *시각 그룹핑을 청각으로 보존*하려면 SymPy의 의미 정규화가
  오히려 해롭기 때문(`speech_parse.py` 상단 주석). `l5/ocr/verify.py` hermetic 철학 답습.

**공유 표기 축(caret `^`·명시 `*`·`/`)은 이미 speech와 정합**(`^`→Power·`*`→"곱하기"). 유일한 잠재
접점은 **유니코드 위첨자**(`to_sympy_source`는 `²`→`**2`로 접지만 speech는 미지 문자로 "알 수 없는
기호" 처리)인데, **같은 문자열을 두 경로에 동시에 흘리는 소비처가 없어**(speech는 LaTeX `x^2`로 입력·
아직 L4/L5 소비 배선 0) 활성 위험이 아니다. speech가 유니코드 위첨자를 낭독해야 하는 소비처가 생기면
그때 `_SUPERSCRIPT` 매핑과 정합시킨다(그 전까지 premature).

⇒ **결론**: ⑪은 "speech를 계약 3자로 확장"이 아니라 **경계 명문화**(본 절)로 충족한다. speech는 이
계약과 별개의 자족 표기 계층이며, 그 계약은 `test_speech_rules.py` 골든이다.

---

## 참고
- 코드: `l3/verify_step.py`·`l3/verify_answer.py`·`src/web/graphing-calculator/src/lib/{graph2dSpec,mathExpr}.js`
- 상위: `math_dsl_risk_register.md`·`math_dsl_remediation_design.md`
- 변경 이력: v0.1 (2026-06-30 — 계약 명문화 + golden test 착수) · v0.2 (2026-07-02 — §5 speech
  프레젠테이션 계층 경계 명문화: invariant ⑪은 계약 3자 확장이 아니라 경계 명시로 충족) · v0.3
  (2026-07-02 — §3 후속 마감: implicit mult·전각/NFKC·비ASCII 연산자·그리스·chained equality를 백엔드
  입력 정규화(`to_sympy_source`)로 처리·공유 계약 canonical 불변·Part 4 항목4·`math_dsl_part4_ast_review.md`)
