# 구축 플레이북 Part 4(AST 의미 엔진) 설계-준수 검토

> **상태**: 검토(review) + 항목4 마감(구현) · **계층**: 횡단(L3 동치 권위 · L4 오개념) · **작성일**: 2026-07-02
> **검토 대상**: `docs/standards/playbook_part_review_questions.md` **Part 4 — AST 의미 엔진**
> (법칙: *AST 5계층 분리 · Canonical 정규화는 교육적 범위만*)
> **상위/관련**: `math_dsl_principles_review.md`(§3.5 AST 5계층 공백 분석 — 본 문서가 그 후속 `/plan`) ·
> `math_dsl_risk_register.md`(Q9 "AST 5계층 = 과설계" · risk #6 AST duplication) · `math_dsl_evolution.md`
> (§1 "명시적 수식 AST 없음 = 확정") · `notation_contract.md`(§3 입력 정규화 후속) ·
> `src/backend/whymath_backend/l3/symbolic_equivalence.py`(동치 권위 단일 primitive)

---

## 0. 요지 (BLUF)

Part 4의 4개 검문 중 **①②③은 이미 준수**하며, 그 준수 방식은 *5계층 AST 엔진을 짓지 않은 것*이다 —
이는 공백이 아니라 **의도된 정답**(risk_register Q9 · evolution §1)이다. **④(입력 정규화)만이 실질
공백**이었고, 본 검토와 함께 *SymPy 진입 전 표기 정규화*로 마감했다(코드: `symbolic_equivalence.py`).

> **핵심 구분**: Part 4의 두 법칙을 혼동하지 않는다.
> - "AST 5계층 분리" = *구조* 법칙 → 우리는 SymPy 직접 권위로 **의도적 미구축**(항목①). full AST는
>   단계검증 코퍼스·WH-S Tier3(Lean) 성숙 전 과설계(Q9).
> - "Canonical 정규화는 교육 범위만" = *경계* 법칙 → `identity_status`가 정의역 의존·초월식을
>   `undecidable`로 보수 반환(강제 정규화 안 함·항목②). self-CAS는 명시 anti-goal.
> - 항목④는 위 둘 중 어느 것도 아닌 **표기(notation) 정규화**(Parsing 경계) — messy 입력(`2x`·전각·
>   `−`)을 canonical로 *접는* 전처리이지 canonical/CAS 정규화가 아니다. 그래서 "교육 범위만" 원칙과
>   충돌 없이 마감할 수 있었다.

---

## 1. 4개 검문 판정

### ① AST 5계층 분리 · Parsing에 교육 의미 미혼입 — **정합(의도적 미구축)**
- 형식적 5계층(Parsing → Canonical → Educational Semantic → Interaction → Visualization)은 **부재**하며
  이것이 정답이다. 대신 *권위 경계*로 사실상 분리돼 있다:
  - **Parsing + Canonical + 동치**: SymPy 단일 권위(`l3/symbolic_equivalence.py`·`verify_step.py`).
  - **Educational Semantic**(개념 연결): L1 개념/원자 그래프(Neo4j·`ConceptEdge`) — 수식 구조와 물리 분리.
  - **Interaction / Visualization**: `l4/learning_scene.py`·`schema/visualization.py`(선언적 spec·stateless).
  - **Speech**: `l3/speech_parse.py` — 자족(hermetic) AST(별도 계층·notation_contract §5).
- **Parsing에 교육 의미 혼입 0**: SymPy 파싱 결과에 개념 태그·오개념·렌더러가 섞이지 않는다. semantic은
  전적으로 그래프 소관이라 *구조적으로* 혼입 불가.

### ② Canonical 정규화 교육 범위 한정 · CAS/삼각 collapse 미번짐 — **강하게 정합**
- `identity_status`는 `expand` + `simplify().is_zero`만 쓴다. **정의역 의존·초월식은 `undecidable`로
  보수 반환**(`√(x²)` vs `x`·`log(a+b)` vs `log a+log b`) — 강제 정규화하지 않는다.
- 삼각 항등식은 *판정*은 하되(`sin²+cos²=1`) collapse rewrite 규칙을 노드/엔진에 심지 않는다.
  self-CAS 구축은 `evolution.md` §2.1 anti-goal. **"교육 범위만" 경계 준수**.

### ③ semantic_tags를 AST 밖에서 관리 · Math State ≠ UI State — **정합(구조적 보장)**
- AST에 붙일 `semantic_tags` 필드 자체가 없다(AST가 없으므로). 개념 연결은 L1 그래프에만 존재 →
  *누출할 곳이 없어* 요건을 구성적으로 충족.
- **Math ⊥ UI/Interaction/Animation state**: invariant Q10-⑤(risk_register). spec은 stateless·
  `extra="forbid"`, `learning_scene`는 interaction state 누출 0.

### ④ implicit multiplication · unary minus · chained equality · 입력정규화(전각/Unicode) — **공백 → 마감**
검토 시점 상태(마감 전):

| 하위 항목 | 마감 전 | 마감 후 |
|---|---|---|
| 유니코드 위첨자(`x²`) | 처리(기존 `_SUPERSCRIPT`) | 유지(NFKC 이전 순서 잠금) |
| unary minus(`-x`·`--x`·`-(x+1)`) | SymPy 네이티브 | 유지(테스트로 명시) |
| **implicit multiplication**(`2x`·`(x+1)(x-1)`) | ❌ `parse_error`→unverifiable | ✅ `_parse`(암묵곱)로 접음 |
| **비ASCII 연산자**(`−`U+2212·`×`·`÷`·`·`) | ❌ 파싱 실패 | ✅ `_OPERATOR_MAP` |
| **전각/NFKC**(`２ｘ`·`（）`) | ❌ 미처리 | ✅ NFKC 접기 |
| **그리스문자**(`π`·`θ`) | ❌ 미인식 | ✅ `_GREEK_MAP`(교육 범위 최소) |
| **chained equality**(`a=b=c`) | ❌ 미지원 | ✅ `split_relation_chain`·`verify_relation_chain` |

**구현**(`l3/symbolic_equivalence.py`):
- `to_sympy_source`를 *표기 정규화 단일 권위*로 확장 — 순서: `strip → 위첨자→**n → 연산자맵 →
  그리스맵 → NFKC`. **순서가 정확성의 핵심**(NFKC가 `²`를 `2`로 분해하므로 위첨자를 먼저 접어야 함·
  직접 실측).
- `identity_status` 파싱을 `sympify(convert_xor=True)` → `parse_expr(transformations=
  standard_transformations + (implicit_multiplication, convert_xor))`로 교체. **`pregenerate/
  validator.py`와 동일한 보수 선택**(`implicit_multiplication`만·`_application` 아님 — 함수 적용 병치
  `sin x`·순수 문자 병치 `xy`는 추정 안 함·CLAUDE.md "확실하지 않으면 모른다"). 두 파싱 진입점을
  같은 관례로 맞춰 "동치 권위 이원화"(risk #6) drift를 줄인다.
- chained equality: `a=b=c`를 인접 등식 쌍으로 분해해 *기존 동치 권위(`identity_status`)를 재사용*
  판정(병렬 진실 금지). 비교/부등(`==`·`<=`)·빈 항은 `ValueError`(조용한 오분리 금지).
- **하류 로직 불변**: `expand`·`simplify().is_zero`·`is_polynomial`·`free_symbols` 판정과 4상태
  (identity/not_identity/undecidable/parse_error)는 그대로. 회귀 게이트로 잠금.

**공유 계약(notation_contract) 불변**: SymPy↔mathjs interop의 canonical(explicit `*` + caret + ASCII)은
바꾸지 않았다. 입력 정규화는 *백엔드 진입 messy 입력*을 canonical로 접는 전처리이지 계약 변경이
아니다 → blast radius 최소(js/mathjs 무영향·전각/chained/그리스는 py-only 정규화).

---

## 2. 메타 질문 — 7대 붕괴 연쇄 관점 인지행동 분석

> *"이 파트의 구조가 실제 서비스에서 실패하는 이유를, 노드폭발 … 인지 행동 기준으로 분석하라."*

- **노드폭발 / 관계폭발**: 5계층 AST를 지었다면 변형식(`FormulaNode`)·정규화 규칙이 노드가 돼 즉시
  폭발한다. SymPy 직접 권위는 *수식을 노드화하지 않으므로* 이 연쇄의 진입로를 원천 차단한다.
  항목④ 정규화도 노드가 아니라 *함수 한 곳*(`to_sympy_source`)이라 폭발 표면이 없다.
- **유지보수 지옥**: 최대 위험은 "동치 규칙이 두 언어(SymPy·mathjs)에 따로"(risk #4·#6)다. 항목④를
  *백엔드 단일 정규화 권위*로 넣고 공유 계약을 안 건드림으로써, 정규화 규칙이 py 한 곳에 모여
  drift 표면이 오히려 줄었다(mathjs는 렌더 전용 유지).
- **AI 추론 실패**: 학생 인지행동은 "손으로 `2x`·`x²`·`x−1`을 쓴다"이다. 마감 전엔 이 자연스러운
  표기가 `unverifiable`로 조용히 떨어져 *튜터가 옳은 풀이를 못 읽는* 침묵 실패였다. 정규화가 인지행동
  (표면 표기)과 판정(canonical 의미)을 잇는다. 단, `xy`·`sin x`는 *추정하지 않고* 보수 유지 —
  "확실하지 않으면 모른다"가 거짓 판정보다 안전(정확성 #1).
- **교육 일관성 붕괴**: 항목②의 `undecidable` 보수성이 방파제다. CAS로 억지 정규화하면 정의역
  오류(`√(x²)=x`)를 "맞다"로 위장해 오개념을 심는다 — 미구축이 일관성을 지킨다.

---

## 3. 결론

1. **Part 4 ①②③ 준수** — 5계층 AST 미구축·canonical 교육 범위 한정·semantic 외부화·Math⊥UI는
   이미 구조/스키마로 박혀 있다(재확인).
2. **④ 마감** — 입력 표기 정규화(implicit mult·전각/NFKC·비ASCII 연산자·그리스·chained equality)를
   SymPy 진입 전 단일 권위에서 처리. 코드 0→구현, 테스트 동반(`test_input_normalization.py`).
3. **경계 지킴** — 정규화는 표기(notation) 계층에 한정. canonical/CAS로 번지지 않음(항목②·anti-goal
   불변). 공유 계약 canonical 불변(risk #6 표면 축소).
4. **후속(범위 밖)**: `verify_answer.py`는 자체 관계 파싱 경로(to_sympy_source 미경유)라 이번 정규화
   미적용 — 답안 검증 정규화 일원화는 별도 슬라이스. 그리스 전 알파벳·함수 적용 병치(`sin x`)는
   수요 확인 후. chained equality 엔드포인트 배선도 후속(현재 primitive만).

---

## 참고
- 코드: `src/backend/whymath_backend/l3/symbolic_equivalence.py`(`to_sympy_source`·`identity_status`·
  `split_relation_chain`·`verify_relation_chain`) · `l3/verify_step.py` · `l4/misconception/wrong_form_match.py`(소비자)
- 테스트: `tests/backend/l3/test_input_normalization.py`(신규) · `test_symbolic_equivalence.py`(회귀)
- 상위: `math_dsl_principles_review.md` §3.5 · `math_dsl_risk_register.md` Q9·#6 · `notation_contract.md` §3
- 원칙: `CLAUDE.md`(의사결정 우선순위·"확실하지 않으면 모른다"·표현≠의미)
- 변경 이력: v0.1 (2026-07-02 — Part 4 검토 + 항목4 입력 정규화 마감)
