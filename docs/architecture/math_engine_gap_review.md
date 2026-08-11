# 수식 엔진(Math Engine) 모듈 — 외부 EOS 틀 대조 갭 점검·설계 (2026-08-03 · **2026-08-11 재검증**)

> ⚠️ **읽기 순서 안내 (2026-08-11)**: §0~§부록은 **2026-08-03 시점의 대조 기록**이며, 그중
> **7곳이 그 뒤 main 변화로 낡았다**. 낡은 대목에는 각각 `[→ §7-Δn]` 표시를 달았다. **현행 판정은
> §7이 정본**이다. 이 문서가 8일간 미병합 브랜치에 고립돼 있던 경위와 회수 기록도 §7에 있다.

> **범위**: 외부 참고 문서 『07. 수식(Math Engine)』(기능 28 MathLive 입력 · 29 자연표기↔LaTeX 변환 ·
> 30 수식 검증 · 31 그래프 생성, 세부 기능 40개 — **WhyMath 전용이 아닌 일반적인 EOS 틀**, Kiki
> 제공)을 현 코드베이스와 대조해 빠진 부분을 점검하고, 진짜 갭을 WhyMath 불변식(Layer Separation ·
> 표현≠의미 · 동치 판정 SymPy 단일 권위 · 교수학 금기 · dead code 금지 · 침묵 실패 금지 · 측정 없는
> 도입 없음) 안에서 설계한 기록.
> **형식**: `ai_recommendation_module_gap_review.md`(기능 80~83, 2026-08-01) 답습 — 시리즈
> **11번째** 자매편.
> **결론**: 착수 가설("수식 엔진이 얇다")은 **반증됐다** — CAS 검증 축은 초과 충족이고 MathLive
> 입력은 실기기 실측을 마친 성숙 구현이다. 뚫린 곳은 엔진이 아니라 그 엔진에 들어가는 **입력의
> 정규화 권위**와 나오는 **판정의 변별력**이다. 진짜 갭 5건을 설계(D1~D5, D5는 페이퍼)하고 실행
> 4건을 백로그에 등재했다. 의도적 미채택 10건 · 정직한 공백 8종 · 유보 발화조건 6건. 정본 stale
> 5곳을 이번 대조에서 실측으로 잡아 정정한다.

관련 정본: `math_dsl_evolution.md`(§3.3 자체 CAS anti-goal·`ReasoningStep` 권장) ·
`math_dsl_part4_ast_review.md`(AST 5계층 의도적 미구축 판정) · `notation_contract.md`(py↔js 교차
골든 선례·§5 speech 경계) · `math_dsl_risk_register.md`(Q6·Q8·Q10-⑦) · `05_interaction.md` ·
`05b_visualization_classification.md` · `nlp_module_gap_review.md`(§3 D3 NLP-03·§2-④ MathML 승계) ·
`visualization_module_gap_review.md`(VIZ-01/02/03 승계) · `MEMORY.md` 결정 로그(2026-08-03·2026-08-11).
**[2026-08-11 추가]** `dsl_integration_gap_review.md`(2026-08-10 · DSL 표면 전수 8종+준표면 2종
끝-끝 실측 · §5 math_dsl 계열 stale 정오표 10건) — 이 문서보다 **뒤에 착륙한 상위 실측**이므로
표기·계약 축에서 충돌 시 그쪽이 우선한다.

---

## §0. 세 가지 전제 정리

### ①-a 착수 가설이 세 번 뒤집혔다 (스코프 고정)

1. **"수식 엔진이 얇다"** → **반증.** 검증 축은 **초과 충족**이다 — `identity_status` 4상태
   (`l3/symbolic_equivalence.py:132`) + `verify_step` 3상태(`l3/verify_step.py:183`, 비대수 단계·
   연쇄등식·해집합 보존·이질 형태·부분집합 모호를 각각 별도 분기) + `verify_answer`
   (`l3/verify_answer.py:272`) + 개념형 검증기 15종 + 자연표기 실사용 픽스처 동결
   (`tests/backend/l3/test_natural_notation_verify.py`). "만들어야 한다"가 아니라 **"만든 것이
   학생에게 어떻게 도달하는가"**가 문제다.
2. **"LaTeX→평문 3벌은 중복이니 합치면 된다"** → **반증(부분).** 실측하면 3벌은 사본이 아니라
   **서로 다른 3개 규칙**이다(부록 A). 웹은 암묵 곱셈을 강제 삽입하는데 백엔드는 그 해석을
   의도적으로 거부한다(`symbolic_equivalence.py:74-75`). "중복 제거"는 오진이고, 정확한 처방은
   **판정 일치의 기계적 강제**다. Dart가 Python을 import할 수 없는 이상 구현 3벌은 원리적으로
   남는다 — 줄일 수 있는 것은 *권위*이지 *구현체 수*가 아니다.
3. **"MathLive가 미완이다"** → **반증.** vendored iife 839KB + 3단 폴백(vendored→CDN→평문) +
   `MOB-03`(레이아웃)·`MOB-06`(제출 계약)·`MOB-07`(`\displaylines` 단계 연동) 실기기 실측 완료.
   갭 아님(§1 기능 28).

세 반증의 방향이 같다: 이 모듈은 "못 만든" 게 아니라 **"만든 것의 권위·변별력이 어디 있는지
아무도 못 세는"** 상태다.

### ①-b 틀의 아키텍처와 정본의 차이 (갭 판정의 전제)

틀은 Math Engine을 *"수식을 입력받아 이해·검증·시각화하는 자족 엔진"*으로 그린다. WhyMath 정본은
그것을 **의도적으로 엔진화하지 않는다**:

| 틀이 엔진에 맡기는 것 | WhyMath 정본의 대체 | 근거 |
|---|---|---|
| 자체 수식 표현·변형 엔진 | **SymPy = 검증 *커널*, 정체성 아님** | `math_dsl_evolution.md:97,298` — 자체 CAS = anti-goal("SymPy 재구현 = 즉사") |
| 5계층 AST(Lexical→Semantic) | **의도적 미구축** — SymPy 직접 권위 | `math_dsl_part4_ast_review.md:20,32` |
| 관용적 입력의 적극 해석 | **보수적 거부** — 모호하면 `unverifiable` | `symbolic_equivalence.py:74-75`(`sin x`·`xy` 추정 안 함) |
| 자체 그래프 엔진 | **선언적 spec + 렌더러 = Plugin** | `l3/visualization.py:6-8`(L3는 명세만·렌더는 L5) |

**따라서 이 문서는 "AST가 없다"·"CAS가 없다"·"관용 표기를 못 읽는다"를 갭으로 세지 않는다.**
갭은 **정본이 스스로 선언한 경계를 코드가 지키지 못하는 지점**에서만 성립한다. D1~D4는 전부 그
형태다 — 각각 (D1) *"입력 정규화 단일 권위"* 선언 위반, (D2) *"실증 없는 심볼 추가 금지"* 선언
위반, (D3) *"모르면 모른다고"* 선언의 학생 대면 소실, (D4) 학년 축 선언 자체의 부재.

### ①-c 이 대조가 승계만 하고 재설계하지 않는 축 (범위 봉인)

| 축 | 소유 태스크 | 이 문서의 행동 |
|---|---|---|
| 서버측 답 채점(클라 `is_correct` 권위) | `NLP-02-server-answer-grading-shadow` | **승계·재설계 금지.** 기능 30에서 ⏸ 표기만 — **done** `[→ §7-Δ4]` |
| 풀이 단계 *분해*(1 제출→N 단계) | `NLP-03-solution-segmentation-contract` | **경계 분할**(§3 D1 박스) — ~~`depends_on: MATH-01` 추가~~ **철회** `[→ §7-Δ5]` |
| 시각화 공급·계약·표현력 | `VIZ-01`(done)·`VIZ-02`·`VIZ-03`·`S4-03` | **승계.** 기능 31은 ⏸ 다수 — `VIZ-02`·`VIZ-03`도 **done**, `VIZ-04`~`06` 신설·done `[→ §7-Δ3]` |
| 차원(단위) 정합 | `E1-01-dimensional-consistency` | **승계**(§2-④) — 수학 축 아님 |
| 클라 수학 판정 0 동결 | `ARCH-10-client-mathlogic-gate` | 변별력 공백만 지적(§4-③), 태스크 신설 없음 |

---

## §1. 기능 28~31 전수 대조 (세부 40개)

판정 기호: ✅ 충족·초과 / △ 부분(부품은 있는데 *배선·정본* 없음) / ⚠️ 진짜 갭 → D / ⏸ 기존 태스크
승계 / 🚫 의도적 미채택 → §2

### 기능 28 — MathLive 수식 입력 (10항 / 갭 0)

| 세부 기능 | WhyMath 현행 | 판정 |
|---|---|---|
| 수식 편집기 임베드 | `mathlive_input_webview.dart` + vendored iife(`src/mobile/assets/mathlive_input/`, 839KB) | ✅ |
| 가상 수식 키보드·팔레트 | MathLive 0.110.0 번들 기본 | ✅ |
| 터치·제스처 입력 | `MOB-03` 레이아웃 실기기 실측 | ✅ |
| LaTeX 직렬화 산출 | `mathlive_input_screen.dart:104` `Navigator.pop(_latex.trim())` — `MOB-06` 제출 계약 | ✅ |
| 다중 행 입력 | `\displaylines{}` — `MOB-07`로 단계 필드 분배 완결 | ✅ (사고 이력은 §6) |
| 오프라인·자산 폴백 | **3단 폴백**(vendored iife→CDN→평문 textarea, `assets/mathlive_input/index.html:75-76`) | ✅ **초과** |
| 실시간 미리보기 | MathLive 내장 | ✅ |
| 입력→풀이 단계 필드 연동 | `MOB-07` done — `chat_screen.dart:156-170` `latexToPlainSolution` 경유 | ✅ |
| 접근성(수식 낭독) | `l3/speech`는 *출력* 축(SSML)이고 입력 위젯 자체 a11y는 미측정 | §4-① |
| 필기·스타일러스 입력 | 없음 — OCR 축이 대체(도달 0회) | ⏸ `NLP-01` |

> **결론**: 기능 28은 **갭 0.** 이 문서가 D를 만들지 않는 유일한 기능이며, 그 사실 자체를 기록해
> 다음 세션의 중복 착수를 막는다.

### 기능 29 — 자연표기 ↔ LaTeX 양방향 변환 (10항 / 갭 1)

| 세부 기능 | WhyMath 현행 | 판정 |
|---|---|---|
| LaTeX → 계산 가능 표기 | **3벌이 서로 다른 규칙**(백엔드 `l5/ocr/verify.py:61-74` · Dart `latex_to_plain.dart:131-140` · 웹 `mathExpr.js:12-28` — 부록 A) | ⚠️ → **D1** |
| 계산 표기 → LaTeX(백엔드 **생성**) | `sympy.latex` 사용 **0건**(전 저장소 확인) | 🚫 §2-⑨ (유효) |
| 유니코드 정규화(전각·U+2212·그리스·`²`) | `to_sympy_source`(`symbolic_equivalence.py:88`) — NFKC 순서 잠금까지 | ✅ **초과** |
| 암묵 곱셈(`2x`·`(x+1)(x-1)`) | `_PARSE_TRANSFORMS`(`:73`) implicit_multiplication | ✅ |
| 함수 병치(`sin x`) | **의도적 거부**(`:74-75`) | 🚫 §2-⑧ |
| 캐럿 없는 지수(`x2`) | **의도적 보류**(수열 `a1` 모호·`test_natural_notation_verify.py` 동결) | 🚫 §2-⑧ |
| 자연 근호(`√3`) | 백엔드 미지원 — 웹만 부분(`\sqrt` LaTeX만) | §5-③ / D5 |
| 연쇄 등식(`a=b=c`) | `split_relation_chain`/`verify_relation_chain`(`:174,193`) | ✅ **초과** |
| MathML 변환 | 없음 | 🚫 §2-⑥ (`nlp_module_gap_review.md §2-④` 승계) |
| 표기 계약 교차검증 | py↔js **2자**만 + `data/` CI 트리거 부재(부록 B) `[→ §7-Δ1]` | ⚠️ → **D1** / §정정 |
| **역방향 — LaTeX → 학생 가독 표기(표시)** `[→ §7-Δ6 신규]` | MathLive 미리보기·OCR 결과가 **원문 LaTeX를 그대로 학생에게 노출** | ⚠️ → **D6**(2026-08-11 신규) |

### 기능 30 — 수식 검증 4단계 (10항 / 갭 2)

| 세부 기능 | WhyMath 현행 | 판정 |
|---|---|---|
| **①문법** — 파싱 가능성 | `parse_check_latex`(`l5/ocr/verify.py:77`) → **`ok: bool` 1개** | ⚠️ → **D3** |
| **①문법** — 오류 *위치* | 없음(`reason`은 한국어 자유문) | ⚠️ → **D3** |
| **①문법** — 오류 *사유 코드* | 없음 — `undecidable`/`parse_error`가 `unverifiable`로 접힘(`verify_step.py:180`) | ⚠️ → **D3** |
| **②의미** — 미정의 함수 거부 | `canonicalize.py:47-59` `condition_dsl_violation`(`AppliedUndef`) **1건** | △ (§4-②) |
| **②의미** — 정의역·차원 | 차원 검증 0 | 🚫 §2-④(`E1-01` 승계) |
| **③교육과정 범위** | **미구현**(가장 가까운 것 = speech 학년밴드·거부 없이 표시만) | ⚠️ → **D4** |
| **④CAS** — 항등성 | `identity_status` **4상태** | ✅ **초과** |
| **④CAS** — 단계 전이 | `verify_step` 3상태 + 해집합 보존·이질형태·부분집합 모호 분기 | ✅ **초과** |
| **④CAS** — 답 검산 | `verify_answer` + 개념형 검증기 15종 | ✅ **초과** |
| 검증 결과의 학생 대면 표현 | `'N단계 중 M단계 확인 · 확인 보류 일부'` **한 문장**(부록 D) | ⚠️ → **D3** |

### 기능 31 — 그래프 생성 (10항 / 신규 갭 0 · 파생 1)

| 세부 기능 | WhyMath 현행 | 판정 |
|---|---|---|
| 2D 함수 그래프 | `Graph2dSpec`(`schema/visualization.py:56`) + 웹 계산기 2141행 + WebView | ⏸ `VIZ-01`(도달률 6.97%) `[→ §7-Δ3]` |
| 슬라이더 파라미터 조작 | `Graph2dSpec.parameters` | ✅ |
| 정의역·치역 지정 | `domain`·`y_range` | ⏸ `VIZ-03` **→ done** `[→ §7-Δ3]` |
| 음함수·부등식·극좌표·매개변수 | 웹 `classify`는 지원 / spec 표현력 부족 | ⏸ `VIZ-03` **→ done** `[→ §7-Δ3]` |
| 3D 곡면 | `Surface3dSpec` 좌석·렌더 미배선 | ⏸ `S4-03` |
| spec 내 함수식 검증 | `l3/visualization.py:22` **"후속"이라 자인** — 파싱 검증 0 | ⚠️ **D1 파생**(§3 D1) |
| 생성기 허용 타입 ⊆ 렌더 가능 타입 | 하드코딩 4종 | ⏸ `VIZ-02` **→ done**(`render_contract.json` 파생) `[→ §7-Δ3]` |
| 애니메이션(Manim) | 스키마 좌석만·구현 0 | ⏸ `S4-03`(todo·유효) `[→ §7-Δ3]` |
| 외부 그래프 엔진(Desmos·GeoGebra) | 미채택 | 🚫 §2-① |
| 그래프 이미지 인식(image→spec) | 없음 | 🚫 §5(`nlp_module_gap_review.md §5-⑥` 승계) |

> **결론**: 신규 D를 만들지 않는다. 유일한 미소유 항목(spec 함수식 파싱 검증)은 **표기 정규화
> 문제**이므로 D1이 순수 함수를 제공하고 **배선은 `VIZ-03`이 소비**한다(§5-⑤).

---

## §2. 의도적 미채택 판정 (협상 불가 근거 — 10건)

| # | 문서 제안 | 불채택 근거 |
|---|---|---|
| ① | Desmos·GeoGebra 등 외부 그래프 엔진 채택(31) | **렌더러 = Plugin** — 코어에 렌더러 구현체를 넣지 않는다는 `05 §5.2`·`visualization_module_gap_review.md` 결정 승계(+ 오프라인·라이선스·미성년자 데이터 유출 제약) |
| ② | 자체 CAS·재작성 규칙 트리(29·30) | `math_dsl_evolution.md:97,298` **명시 anti-goal** — *"SymPy 재구현 = 즉사"*. SymPy는 검증 *커널*이지 정체성이 아니다 |
| ③ | AST 5계층 의미 엔진(30) | `math_dsl_part4_ast_review.md:20,32` — **의도적 미구축이 이미 "정합" 판정**을 받았다. 재론은 결정 번복이지 갭이 아니다 |
| ④ | 차원(단위) 검증(30) | 수학 축이 아니라 물리 축이며 `E1-01-dimensional-consistency`가 **이미 소유** — 중복 등재 금지 |
| ⑤ | **학생 입력에 대한 교육과정 범위 거부**(30) | 교수학 금기 정면 위반 — *"고2 방법은 쓰지 마세요"*는 부정적 피드백의 정서적 강화이자 학습 차단이다. **D4는 생성물 전용**으로 좌표를 옮겨서만 성립 |
| ⑥ | MathML 변환(29) | `nlp_module_gap_review.md §2-④` 승계 — **표현 ≠ 의미**, MathML은 렌더러 관심사 |
| ⑦ | 문항 본문 완전 AST화·수식 변형 노드화(29·30) | `math_dsl_risk_register.md` Q3·Q8 조합 폭발. 허용된 것은 `FormulaNode` canonical *참조* 노드뿐(변형 금지·`test_formula_governance.py` 동결) |
| ⑧ | 관용 표기 적극 해석 — `sin x`·`xy`·`x2`(29) | **이미 의도적 거부로 동결**(`symbolic_equivalence.py:74-75`·`test_natural_notation_verify.py`). 거짓 incorrect 0이 정확도 #1이며 추정은 그 축을 깬다 |
| ⑨ | 백엔드 LaTeX **생성**(`sympy.latex`)(29) | 렌더 권위는 클라 KaTeX/MathLive다. 사용 0건은 갭이 아니라 **경계** — 백엔드가 LaTeX를 만들면 렌더 권위가 이원화된다 |
| ⑩ | 입력 중 실시간 서버 검증(28·30) | 교수학 금기(즉답 제공·생산적 막힘 파괴) + LLM/CPU 비용. 정본 전략은 *제출 시 검증*이다 |

---

## §3. 진짜 갭 설계 (D1~D4 실행 · D5 페이퍼)

### D1 — 수식 판정의 입력 정규화 권위가 클라이언트 단독에 있다 (최우선 · `MATH-01`)

**문제.** `notation_contract.md §3`가 *"입력 정규화 단일 권위 = `to_sympy_source`"*라고 선언한다.
그런데 **LaTeX 계층 정규화는 그 함수 안에 없다**. `to_sympy_source`는 유니코드·전각·그리스·NFKC만
처리하고, `\frac`·`\sqrt`·`\cdot`·`\displaylines` 해체는 **세 곳에 흩어져 있다** — 그중 학생 제출
경로에 있는 것은 **Dart**다. 즉 *"수식 판정의 입력을 무엇으로 접을지"*를 결정하는 권위가 사실상
클라이언트에 있다.

**먼저 반증한 것 — "사본 3개"가 아니다.** 세 구현은 중첩 `\frac`·암묵 곱셈 삽입·`\div`·`\sqrt`
괄호 수에서 서로 다르게 동작한다(부록 A). 웹은 `$1*$2`로 암묵 곱셈을 **강제 삽입**하는데 이는
백엔드가 의도적으로 거부한 해석(`sin x` 추정 금지)과 정면 충돌한다. 따라서 처방은 "합치기"가
아니다.

**핵심 판단 — 줄일 수 있는 것은 *권위*이지 *구현체 수*가 아니다.** Dart는 Python을 import할 수
없다. 3벌 구현은 남는다. 남길 수 없는 것은 "어느 것이 맞는지 아무도 정하지 않은 상태"다.
`notation_contract.json` 선례가 이미 그 해법(py↔js 교차 골든)을 증명했다. D1은 **Dart를 3자로
편입**한다.

**정합 설계** (신규 추상 0 · LLM 0 · 신규 API 필드 0):
- ① `data/notation_contract.json`에 `latex_cases` 블록 **확장**(신설 아님)
- ② `l5/ocr/verify.py::_latex_to_sympifiable`(private·L5·OCR 스코프)를 **`l3/symbolic_equivalence.py`
  public 순수 함수로 이관** — 선언과 코드의 불일치를 코드 쪽에서 닫는다
- ③ **3자 교차 골든** py ↔ js ↔ Dart 신규 편입(`File('../../data/...')` —
  `no_math_logic_governance_test.dart:100`이 이미 `File()`로 소스를 읽는 선례). 웹은 canonical
  문자열 일치가 아니라 **mathjs 동일 수치**로 검증(렌더 경계 불변)
- ④ **`ci.yml` 경로 필터 backend·mobile·web 셋에 `data/notation_contract.json` 추가** — 이걸 빼면
  D1이 만든 게이트가 D2가 지적하는 유령이 된다(부록 B). **`[→ §7-Δ1·Δ2]` 이 항은 2026-08-11에
  범위가 정정됐다 — backend·web은 이미 메워졌고 mobile 하나만 남았으나, 봉인 대상은 계약 파일
  3건으로 늘었고 그중 2건은 이미 라이브 미집행 상태다.**
- ⑤ 상한: `latex_cases`는 **입력→산출 쌍만, 조건 분기 금지**(재작성 규칙 트리는 anti-goal)

**`NLP-03`과의 경계**:

| | `NLP-03` (분해) | `MATH-01` (정규화) |
|---|---|---|
| 질문 | 1 제출 → N 단계로 어떻게 쪼개는가 | 각 단계 문자열을 어떤 표기로 접는가 |
| 계약 파일 | `data/segmentation_contract.json`(신규) | `data/notation_contract.json`(기존 확장) |
| 입력형 | 문자열 1개 | 단계 문자열 1개 |
| 산출형 | `list[str]` | `str` |
| `\displaylines` | **행 구분자 `\\`로의 분해** | **래퍼 `{}` 해체** |

`\displaylines`는 래퍼 벗기기(표기)와 행 분해(구조)가 한 함수에 붙어 있으나, 이 슬라이스는
함수를 쪼개지 않는다 — 계약을 둘로 나누고 각각의 골든이 자기 축만 단언한다. `NLP-03`의
`depends_on`에 `MATH-01`을 명시했다(§0-①c).

**dead code 금지 충족**: 신규 모듈 0 · 신규 계약 파일 0 · 기존 private 함수의 **이관**(추가 아님).
**측정 없는 도입 없음**: 첫 실행에서 py/js/dart 불일치 건수가 곧 이 계약의 필요성 근거다(0건이면
과잉이라는 정직한 신호 — §4).
**변별력**: `latex_cases`의 canonical 한 줄을 의도적으로 틀리게 바꿔 셋 다 red가 되는지 실측 →
복원해 green. dart/js 어느 쪽도 fixture 부재를 skip으로 흡수하지 않는다(파일 부재=실패).

**범위 밖**: (a) 원문 LaTeX를 API로 함께 보내는 shadow 이중 회계(발화 조건 §5-①). (b)
`Graph2dSpec.function` 파싱 검증의 배선은 `VIZ-03` 소관(§5-⑤).

**태스크**: `MATH-01-notation-normalization-authority` (stage S3 · priority 2) — acceptance ④는
2026-08-11 재검증으로 갱신됨(`[→ §7-Δ1·Δ2]`)

---

### D2 — 표기 지원집합 정본이 존재하지 않는 구현을 가리킨다 (`MATH-02`)

**문제.** `.github/workflows/ci.yml:290`이 `python -m whymath_backend.l3.notation_coverage`를
**실제로 매 PR 돌리고 있고 green**이다. 그런데 그 게이트의 지원집합이 근거로 지목하는 파일 5종
(`src/mobile/lib/features/chat/domain/math_notation.dart` · `src/mobile/test/notation_canonical_test.dart` ·
`math_notation_audit_test.dart` · `math_text_test.dart` · `docs/architecture/notation_semantics_layer.md`)이
**전부 부재**(실측 확인). 원인은 `NS-03` notes와 `MEMORY.md:1137`에 이미 자인돼 있다 —
`NS-02-notation-canonical-layer`가 미병합 브랜치(`claude/shadow-data-s3-pilot-nh5kbz`)에 고립돼
착륙하지 못했고, 순수 데이터인 manifest만 회수됐다.

**먼저 반증한 것 — "게이트가 가짜다"가 아니다.** 게이트의 *측정 기계*(토큰 추출·유니코드
판별·베이스라인 래칫·`--control-empty-support` 대조군)는 **진짜로 돌고 진짜로 변별력이 있다.**
가짜인 것은 **지원집합의 출처 주장**이다. severity를 정직하게 내린다 — "게이트 무효"가 아니라
**"게이트가 측정하는 대상의 정의가 근거를 잃었다"**.

**핵심 판단 — 이 실수의 형태는 새롭다.** VIZ-01·OPS-03·NLP-01은 *"만들었는데 안 돈다"*(증상=
부재)였다. 이건 **"도는데 근거가 없다"**(증상=**green**) — 정반대다. 더 위험하다: green이라
아무도 안 본다. `test_unproven_symbols_not_included`는 allowlist를 *넓히는* 것만 막고 **이미 든
항목의 근거 실재는 검사하지 않는다.**

**정합 설계** (신규 게이트 0 · 기존 게이트 경화):
- ① 근거를 **기계 판독 형태로 승격**: `KATEX_PROVEN_MACROS` 산문 주석 → `_PROVEN_MACRO_EVIDENCE`
  매핑(매크로 → 실증 파일 경로) + manifest `provenance` 블록
- ② **참조 무결성 검사 신설**: 모든 `evidence_path` 실재를 단언하는 테스트
- ③ **회계 정직화**: 근거 부재 항목은 삭제 대신 `status:"unproven"`으로 격리, 지원집합 파생에서
  제외 → 늘어난 코퍼스 누락을 베이스라인에 의식적으로 계상
- ④ NS-02 **회수 또는 포기 결정만** 기록(재구현은 범위 밖)

**dead code 금지 충족**: 신규 모듈 0. 기존 게이트에 근거 실재 축 1개 추가.
**변별력**: 경로 하나를 실재 파일로 바꾸면 green, 부재 파일로 되돌리면 red. **이 검사를 현행에
처음 적용하면 즉시 red여야 한다**(현재 전 항목이 유령이므로) — red가 안 나오면 검사 자체가
위장이다. 이 패턴("고치기 전에 검사가 red임을 먼저 실측")은 D1~D4 중 가장 강한 변별력 설계다.

**범위 밖**: NS-02 Dart 표기 파이프라인의 재구현(발화 조건 §5-②).

**태스크**: `MATH-02-notation-canon-reference-integrity` (stage S3 · priority 2)

---

### D3 — 검증 실패가 학생에게 무변별하다 (`MATH-03`)

**문제.** 백엔드는 실패를 매우 세밀하게 구분한다 — `parse_error`·`undecidable`·비대수 단계·빈
입력·이질 형태(ℝ↔유한)·부분집합 모호·변수 집합 불일치. 학생 화면에는 이 전부가
**`'확인 보류 일부'` 한 문장**으로 도착한다(`coach_signal_card.dart:140-143`).

손실은 **두 군데**에서 일어난다: ①백엔드에서 이미 접힘 — `IdentityVerdict` 4상태가
`VerifyStepState` 3상태로 접히고(`verify_step.py:180`), 기계 판독 사유 코드 없이 자유문 `reason`만
남는다. ②클라에서 통째로 버림 — `coach_models.dart:330-332`가 *"steps는 이번 슬라이스 범위 밖 —
카운트로 충분"*이라 명시하고 파싱하지 않는다.

**왜 이게 D인가 — 정본이 자기 선언을 못 지킨다.** `verify_step` docstring은 *"CLAUDE.md '확실하지
않으면 모른다'"*를 선언한다. 그런데 "모른다"의 종류를 학생이 구분할 수 없으면 "모른다"는 정보가
아니다. *"내 표기가 잘못됐다"*(고칠 수 있음)와 *"이건 계산으로 확인할 수 없는 종류의 단계다"*
(고칠 게 없음)는 학생 행동이 정반대인데 같은 문구를 받는다. `NLP-01` acceptance ③(503 vs 인식
실패 문구 분기)과 **정확히 동형**이며, 이번엔 검증 경로에서 재발했다(§6 계열 A).

**핵심 판단 — 3상태를 늘리지 않는다.** `VerifyStepState`를 4·5상태로 바꾸면 BKT·코치·집계·모바일
모델이 전부 흔들린다. **직교 필드**로 붙인다: `state`(3상태·불변) + `reason_code`(폐쇄 enum·신규).
`step_type`이 이미 직교 전파되는 것과 같은 패턴.

**정합 설계** (신규 상태 0 · 신규 테이블 0 · LLM 0):
- ① `VerifyStepResult`에 `reason_code` 추가(초안 7종: `parse_error`·`undecidable`·
  `non_algebraic_step`·`empty_input`·`heterogeneous_form`·`subset_ambiguous`·`variable_mismatch` —
  전 분기가 이미 코드에 존재하므로 신규 판정 로직 0(라벨링만))
- ② `SolutionVerificationResult`에 `unverifiable_by_reason` 카운트(steps 전체는 안 흘림 — 노출
  계약 유지)
- ③ 클라 문구는 **3분기**(운영 7 : 학생 3 비대칭을 명시 — 검증기 내부를 학생에게 노출하지 않는다):
  고칠 수 있는 것 / 고칠 게 없는 것 / 단정하지 않는 것. 부정 강화 금지·정답 미제공. 위젯 테스트
  동결

**측정 없는 도입 없음**: `unverifiable_by_reason` 분포가 "학생이 어디서 막히는가"의 첫 실측이며,
`parse_error` 비중이 D1·D5(자연표기 확장)의 발화 조건 데이터가 된다.
**변별력**: 두 종류 입력이 서로 다른 카운터·다른 문구를 내는지 실측 — 같으면 이 태스크 자체가
실패다.

**범위 밖**: (a) 오류 위치(문자 오프셋) 지시 — AST 5계층 축(§2-③), 영구 유보에 가깝다. (b)
`parse_check_latex`의 bool 계약 불변(OCR 신뢰도 강등 소비자가 bool을 씀). (c) `reason_code`는
검증 메타데이터이지 `ReasoningStep`(도메인 모델)이 아니다 — D5를 앞당기지 않는다.

**태스크**: `MATH-03-verify-reason-code-discrimination` (stage S3 · priority 2)

---

### D4 — 교육과정 표기 범위 축이 없다 (`MATH-04`)

**문제.** 생성된 문항·풀이·시각화가 대상 학년에 도입되지 않은 표기를 쓰고 있는지 검사하는 축이
0이다. 중3 문항에 `\int`가 들어가도 어떤 게이트도 반응하지 않는다.

**설계 제약(가장 먼저 못 박는다).** 이 축을 **학생 입력 거부**에 쓰면 교수학 금기 정면 위반이다.
**D4는 생성물(문항·풀이·시각화) 게이트 전용**이며, 이 제약을 **소스 스캔 거버넌스 테스트로
기계화**한다(선언으로만 두면 다음 세션이 학생 경로에 배선한다).

**핵심 판단 — 재료 3개가 다 있고, 잇는 매핑 1개만 없다.**

| 재료 | 실재 위치 | 상태 |
|---|---|---|
| 학년밴드 × 도입 구조 12종 | `l4/speech/profiles.py:18-70` `introduced_constructs` | 완성(거부 없이 `unresolved` 표시만) |
| 표기 토큰 전수 추출 | `l3/notation_coverage.py:64` `_MACRO_RE` + `is_math_glyph` | 완성 |
| **토큰 → 구조 키 매핑** | — | **0** |

**정합 설계**:
- ① `data/curriculum_notation_ranges.json` — `{token, construct}` 폐쇄 표. 구조 키는
  **`profiles.py`의 12종 그대로**(어휘 이원화 금지). 매핑 없는 토큰은 `unmapped`로 남기고 판정
  제외(리포트에 건수 노출)
- ② `l3/curriculum_notation_gate.py` — `notation_coverage`와 **동형 CLI 규약**(exit 0/1 · `--json`
  · 베이스라인 래칫 · 대조군 플래그)
- ③ 학생 경로 차단의 기계화: `api/`·`l4/polya/`·`l4/socratic/`에서 이 모듈 import 0건을 소스
  스캔 거버넌스 테스트로 동결(결함 주입 실측 필수 — 현재도 자명하게 green이므로 임시 import로
  red를 실측한 뒤 되돌린다)
- ④ 판정은 **거부가 아니라 회계** — 초과 표기 발견해도 콘텐츠 미삭제, 래칫 계상 + 사람 판단

**변별력**: 같은 코퍼스에 고등 프로파일 → exit 0 / 초등 프로파일 → exit 1(`--force-grade-band`
대조군). 두 경우가 같으면 측정기가 학년 축을 실제로 보지 않는 것이다. 첫 실측 0건이면 이 축이
불필요했다는 정직한 신호이며 그대로 기록한다.

**범위 밖**: (a) 성취기준 코드 자동 태깅(교육과정 축·`curriculum-node-builder` 소관). (b) 학생
입력 거부(영구 미채택 — §2-⑤). (c) 생성 프롬프트 학년 제약 주입(생성 축·후속).

**태스크**: `MATH-04-curriculum-notation-range-gate` (stage S4 · priority 3)

---

### D5 — 수식 의미 계층 (**페이퍼 — 코드 0 · 태스크 신설 없음**)

**①-a `ReasoningStep`/`Justification` 미구현.** `math_dsl_evolution.md:288`이 1순위로 지목했는데
코드는 0이다. **지금 만들면 dead task다** — 소비자(다중 풀이 비교 `S4-10`·풀이 경로 실체화
`S4-09`)가 아직 없고, `NLP-03`이 분해 계약을 먼저 세워야 한다. 선행 순서: `S4-09` → `NLP-03` →
`ReasoningStep`(발화 조건 §5-④). *"정본이 1순위로 지목한 것을 또 미룬다"*는 반론이 유효하므로
**약한 논거임을 정직하게 기록**한다(§4).

`reason_code`(D3)와의 구분: `reason_code` = *"왜 판정 못 했는가"*(검증 메타데이터) /
`ReasoningStep` = *"이 단계가 어떤 종류의 추론인가"*(도메인 모델). 같은 것이 아니며 D3이 D5를
앞당기지 않는다.

**①-b 자연표기 확장(`√3`)의 발화 조건.** 현재 미지원은 버그가 아니라 결정이다(§2-⑧). 확장의
조건은 **D3의 `parse_error` 실측 분포가 그 표기 때문임을 보이는 것**뿐이다(§5-③). 확장하더라도
`sin x`·`x2`는 여전히 안 한다(거짓 incorrect 위험이 픽스처로 동결됨).

### 등재 요약

| 태스크 | 설계 | stage | priority | 근거 |
|---|---|---|---|---|
| `MATH-01-notation-normalization-authority` | D1 | S3 | 2 | **판정 입력 권위가 클라에** · 3벌이 이미 드리프트 · 계약 파일 신설 0 |
| `MATH-02-notation-canon-reference-integrity` | D2 | S3 | 2 | **CI 게이트가 유령 위에서 green** — "도는데 근거가 없다" 신형 실수 |
| `MATH-03-verify-reason-code-discrimination` | D3 | S3 | 2 | **NLP-01 ③ 동형 재발** · 신규 상태 0 · 학생 행동이 갈리는 구분 |
| `MATH-04-curriculum-notation-range-gate` | D4 | S4 | 3 | 축 자체 부재이나 학생 미도달 · 재료 3/4 실재 |
| `NLP-02`(기존) | 서버측 채점 | — | — | **승계·재설계 금지** |
| `NLP-03`(기존) | 단계 *분해* | — | — | **승계 + 경계 명시**(§3 D1 박스) + `depends_on: MATH-01` 추가 |
| `VIZ-02`·`VIZ-03`·`S4-03`(기존) | 기능 31 | — | — | **승계·재설계 금지** |
| `E1-01`(기존) | 차원 검증 | — | — | **승계**(§2-④) |

태스크는 전건 `backlog.py add` CLI 경유로 등재했다(ID 손편집 0). `NLP-03`의 `depends_on`은 CLI에
해당 필드 수정 명령이 없어 YAML을 직접 편집했다(하네스 `check-edit` 훅이 편집 후 무결성을 재검증
— 위반 시 자동 차단). `validate` green 157건(등재 전 153건).

---

## §4. 정직한 공백 — 지금 하지 않는 것 (8종)

1. **MathLive 자체의 접근성(스크린리더 수식 낭독)을 측정하지 않는다** — `l3/speech`는 *출력* 축
   (백엔드 SSML)이고 입력 위젯의 a11y는 별개다.
2. **의미 검증이 `AppliedUndef` 1건뿐인 것을 넓히지 않는다** — 정의역·분모 0·로그 진수 검사는
   SymPy `Assumptions`를 요구하고 `undecidable` 폭증을 부른다. D3 실측 후 판단.
3. **`no_math_logic_governance_test.dart`의 변별력 공백을 이번에 닫지 않는다** — 이 테스트는
   *"표기 변환은 판정이 아니다"*라며 `latex_to_plain.dart`를 통과시키는데, MOB-07 사고가
   "변환 오류 = 판정 오류"임을 실증했다. 이를 강화하는 올바른 방법은 토큰 추가가 아니라 D1의
   계약 골든이다(계약을 어기면 red). 별도 태스크는 중복이므로 여기 기록만 한다. `ARCH-10` 소유.
4. **`parse_check_latex`의 bool을 다상태로 바꾸지 않는다** — 소비자(`assemble.py:56` OCR 신뢰도
   강등)가 bool 계약을 쓴다. D3은 `reason_code` 부착까지만.
5. **성취기준 코드 ↔ 표기 자동 태깅을 하지 않는다** — D4의 매핑은 사람이 관리하는 폐쇄 표다.
6. **3벌 구현을 1벌로 줄이지 않는다** — Dart가 Python을 import할 수 없는 이상 원리적으로
   불가능하다. D1이 줄이는 것은 권위이지 구현체 수가 아니다.
7. **`notation_semantics_layer.md`를 이번에 쓰지 않는다** — 없는 문서를 쓰는 것보다 D2가 지목
   자체를 정직하게 고치는 것이 먼저다. NS-02 착륙(§5-②)과 함께 판단한다.
8. **`notation_missing_baseline.json`의 만료 정책을 만들지 않는다** — D2가 만드는 베이스라인
   증분을 누가 갚는지의 정책 공백이다. `known_gaps_out_of_scope`가 이미 3건 쌓여 있는 것이 그
   전조다. 이번 슬라이스는 회계 정직화까지만 하고 만료 정책은 미룬다.

---

## §5. 유보 항목의 발화 조건 (지금 안 만들되, 언제 만드는지 — 6건)

| # | 유보 항목 | 발화 트리거 |
|---|---|---|
| ① | 원문 LaTeX 전송 + 백엔드 재변환 shadow(D1 후속) | D1의 3자 골든에서 불일치가 실제로 관측되고, 그 불일치가 학생 판정에 영향을 준 사례가 하나라도 나왔을 때 |
| ② | NS-02 Dart 표기 파이프라인 착륙 | D2 ④의 처분 결정이 "회수"로 나고, `MATH-01` 계약이 먼저 서 있을 때 |
| ③ | 자연표기 확장(`√3` 등) | D3의 `parse_error` 실측 분포가 그 표기 때문임을 보였을 때. `sin x`·`x2`는 이 트리거로도 발화하지 않는다 |
| ④ | `ReasoningStep`/`Justification` 도입(D5) | `S4-09`(SolutionPath 실체화) 완료 그리고 `NLP-03`(분해 계약) 완료 후 |
| ⑤ | spec 함수식 SymPy 검증 배선(기능 31) | `VIZ-03`이 spec 표현력을 확장할 때 D1의 순수 함수를 소비. 별도 태스크 신설 금지 |
| ⑥ | 오류 위치 지시(D3 범위 밖) | AST 5계층 결정이 뒤집혔을 때만 — 현 결정 하에서는 영구 유보에 가깝다 |

---

## §6. 반복 실수 — 두 계열 (재발방지 등재)

이 대조는 선례 계열 1개를 이어받고, 계열 1개를 새로 연다.

**계열 A — "무변별 실패" (D3 = 2회차)**

| 회차 | 사례 | 형태 |
|---|---|---|
| 1 | `ocr_controller.dart:71-74` — 503·401·422·네트워크가 같은 문구(`NLP-01` ③) | 사용자 대면 실패의 무변별 |
| 2 | `coach_signal_card.dart:140-143` — parse_error·undecidable·비대수·이질형태가 같은 문구(D3) | 동형 |

*"성공/실패 양쪽에서 같은 값을 내는 것은 검증이 아니라 위장"*이라는 규칙이, 두 번 모두 **검증
스텝이 아니라 학생 대면 표현**에서 되풀이됐다. 규칙의 적용 범위를 "학생이 다음에 할 행동이 갈리는
모든 분기"로 확장하는 것을 제안한다.

**계열 B — "돌긴 도는데 근거가 없다" (D2 = 1회차·신형)**

| 선례 계열 | 형태 | D2와의 차이 |
|---|---|---|
| OPS-03·VIZ-01·NLP-01 | 만들었는데 **안 돈다** | 증상: red도 green도 없음(부재) |
| D2 | **도는데 근거가 없다** | 증상: **green** — 그래서 아무도 안 본다 |

계열 A·기존 계열은 *부재*가 증상이었다. D2는 **green 자체가 증상**이다. 판정 기준을 *"게이트가
돌아가는가"*에서 **"게이트가 지목하는 근거가 실재하는가"**로 한 단계 더 밀어야 한다. D2의
`_PROVEN_MACRO_EVIDENCE` 실재 검사가 그 판정을 기계화하는 첫 사례다.

---

## §정정 — stale 정본 5곳 (이번 대조에서 실측으로 발견)

| 위치 | 현재 기술 | 실측 |
|---|---|---|
| `notation_contract.md §4` `[→ §7-Δ1]` | *"새 표기 케이스는 fixture에만 추가하면 양측이 자동 검증한다"* | **(2026-08-03 시점) PR에서 거짓.** `ci.yml:71,79,82` 경로 필터에 `data/`가 없어 `data/notation_contract.json`만 고친 PR은 backend·mobile·web 잡을 **전부 skip**한다(main push에서만 참). 2026-07-21 `schemas/` 사각 보완과 같은 구멍이 `data/`에 남았다 → D1-④가 봉인 |
| `latex_to_plain.dart:13-15` | *"백엔드 `_latex_to_sympifiable`의 치환 규칙을 그대로 미러"* | **부분 거짓.** 미러는 `_FRAC_RE`·`_SQRT_RE`·연산자 치환까지이고, `\leq`·`\neq`·간격 매크로·`\displaylines`는 Dart 고유 확장이다. "미러 + 확장"이 정확한 서술 |
| `l3/notation_coverage.py:11-13` | 지원집합 정본 = manifest + *"Dart 위젯 렌더 테스트가 실증한"* allowlist | **실증 파일 5종 전부 부재**(D2) |
| `symbolic_equivalence.py` / `notation_contract.md §3` | *"입력 정규화 단일 권위 = `to_sympy_source`"* | **LaTeX 계층은 그 안에 없다.** 권위 선언이 실제 커버리지보다 넓다 → D1-②가 코드 쪽에서 닫음 |
| `l3/visualization.py:22` | *"spec 내 함수식 SymPy 검증은 후속"* | 자인은 정확. 다만 **소유 태스크가 어디에도 없었다** → §5-⑤로 `VIZ-03`에 귀속 |

네 번째 항목만 방향이 다르다 — 앞 셋은 *"실제보다 못하다"*고 말하는 조용한 stale인데, `to_sympy_source`
건은 **"실제보다 낫다"고 말하는 stale**이다. 이쪽이 더 위험하다: 다음 세션이 "권위는 이미 하나네"
하고 검사를 건너뛴다.

---

## 부록 — 실측 근거 (2026-08-03 실측)

- **A. LaTeX→평문 3벌 대조표** — `l5/ocr/verify.py:33-74` · `latex_to_plain.dart:22-27,131-150` ·
  `mathExpr.js:12-28`. 중첩 `\frac`(1패스 vs 1패스 vs 6루프) · 암묵 곱셈 삽입(무·무·**유**) ·
  `\div`(유·유·**무**) · `\sqrt`(`sqrt((x))`·`sqrt((x))`·`sqrt(x)`) · `\leq`(무·`<=`·**부분매치
  잠재결함**) · `\operatorname`/`\mathrm`(무·무·유) · `\displaylines`(무·**유**·무)
- **B. CI 경로 필터** — `.github/workflows/ci.yml:71`(backend) · `:79`(mobile) · `:82`(web) —
  `data/` 부재(실측 확인). `:290` NS-03 게이트 스텝 실재.
- **C. 유령 정본** — `math_notation.dart`·`notation_canonical_test.dart`·
  `math_notation_audit_test.dart`·`math_text_test.dart`·`notation_semantics_layer.md` **5종 전부
  부재**(실측). `data/notation_support_manifest.json`·`notation_coverage.py:69-72,76` 주석이 지목.
  `data/notation_missing_baseline.json` 실재. `test_notation_coverage_eval.py:123`
  `test_unproven_symbols_not_included`는 *넓히기*만 차단.
- **D. 검증 무변별** — `symbolic_equivalence.py:123-130`(4상태) → `verify_step.py:180`(3상태로
  접힘·`reason` 자유문) → `verify_solution.py`(steps 보존) → `coach_models.dart:330-332`(steps
  **미파싱**·"카운트로 충분") → `coach_signal_card.dart:140-143`(`'확인 보류 일부'` 단일 문구)
- **E. D4 재사용 자산** — `l4/speech/profiles.py:18-70`(밴드 4 × 구조 12·거부 없음) ·
  `notation_coverage.py:64`(`_MACRO_RE`)·`is_math_glyph`
- **F. 미채택 근거** — `math_dsl_evolution.md:97,288,298` · `math_dsl_part4_ast_review.md:20,32` ·
  `symbolic_equivalence.py:74-75` · `test_natural_notation_verify.py`
- **G. `sympy.latex` 사용 0건**(전 저장소 grep 확인)
- **H. Dart의 `data/` 읽기 실현성** — `no_math_logic_governance_test.dart:100` `File('lib/...')`
  선례(flutter test cwd = `src/mobile`)

---

## §7. 2026-08-11 재검증 — 회수 + 8일 Δ (**현행 판정 정본**)

### §7.0 왜 이 절이 생겼나 — 미병합 고립 4회차

Kiki가 **같은 외부 틀 문서**(『07. 수식(Math Engine)』 기능 28~31)를 다시 주며 갭 점검을
요청했다. 착수하니 이 대조가 **이미 2026-08-03에 완료돼 있었고**, `MATH-01`~`04`와 함께
**PR #678(open)** 에 들어 있었다. 그런데 **8일간 main에 하나도 착륙하지 않았다** — 착수 시점
실측으로 `docs/architecture/math_engine_gap_review.md` 부재, `backlog/tasks/`에 `MATH-*` 0건
(태스크 239건).

`problem_bank_gap_review_r2.md` §6-ⓐ가 **"미병합 브랜치 고립 — 3회차"**로 등재한 계열의
**4회차**다. 이번 회차의 특징: 고립분이 *구현*이 아니라 **설계 문서 + 백로그 등재**라서 피해가
"코드 소실"이 아니라 **"같은 대조를 두 번 하게 만드는 것"**으로 나타났다. 실제로 이 세션은
그 중복 착수 직전까지 갔다.

**따라서 이 세션은 새 문서를 쓰지 않고 고립분을 회수했다.** 회수는 재작성이 아니라 git 경유
(`git checkout FETCH_HEAD -- <문서> <태스크 4건>`)로 원본을 그대로 가져온 뒤, 현행 main 기준
재검증 결과만 이 §7과 인라인 `[→ §7-Δn]` 표시로 덧붙였다. 1차 본문을 고쳐 쓰지 않은 이유는
**무엇이 언제 참이었는지가 이 문서의 가치**이기 때문이다 — 특히 Δ1은 "우리가 지적한 구멍이
그 사이 메워졌다"는 기록이라 지우면 손실이다.

### §7.1 Δ 대조표 — 1차 주장 대비 (7건)

| Δ | 1차(2026-08-03) 주장 | 2026-08-11 실측 | 방향 |
|---|---|---|---|
| **Δ1** | D1-④ · §정정① — `ci.yml` 경로 필터 backend·mobile·web **셋 다** `data/` 부재 | **backend(`:74`)·web(`:86`)은 이미 포함**(`notation_contract.json`·`render_contract.json`). **mobile(`:83`)만 미포함** | 좁아짐(호전) |
| **Δ2** | (미발견) | 그 잔여 구멍이 **이미 착륙한 Dart 골든 2개를 미집행시키고 있다** — `segmentation_contract_test.dart:96`·`scene_contract_test.dart:29`가 `File('../../data/...')`로 읽는 `data/segmentation_contract.json`·`data/scene_contract.json`이 mobile 필터에 없어 fixture-only PR에서 mobile 잡 통째 skip | **넓어짐(악화)** |
| **Δ3** | 기능 31 — `VIZ-02`·`VIZ-03` ⏸ 승계(미완) | **둘 다 done.** 추가로 `VIZ-04`(양식↔좌석 계약)·`VIZ-05`(4분류 원자 백본)·`VIZ-06`(극값 마커 회수) 신설·done. 잔여는 `S4-03`(3D·Manim)·`MISC-01`뿐 | 판정 갱신 |
| **Δ4** | `NLP-02`·`NLP-03` 승계(미완) | **둘 다 done**(`NLP-03`은 `NLP-04` 고립 회수로 착지 — 같은 계열의 회수 선례) | 판정 갱신 |
| **Δ5** | `NLP-03`에 `depends_on: MATH-01` 추가 | `NLP-03`이 **done**인 채로 미착수 태스크에 의존을 거는 형태 — 1차 문서 자신도 notes에 "선언과 실제 착수 순서가 어긋난 채 완료"라고 자인했다. **철회**한다 | 철회 |
| **Δ6** | 기능 29 "역방향"을 백엔드 `sympy.latex` 생성으로 읽고 §2-⑨ 미채택 | **읽기가 좁았다.** 틀의 역방향은 `LaTeX → AST → 자연표기`, 즉 **표시 축**이며 미채택된 적이 없다. 실측하니 **두 표면이 뚫려 있다** → **D6 신설**(§7.3) | **신규 갭** |
| **Δ7** | 관련 정본 목록 | `dsl_integration_gap_review.md`(2026-08-10)가 그 사이 착륙 — DSL 표면 전수 실측 + math_dsl 계열 stale 정오표 10건 보유. 표기·계약 축 충돌 시 그쪽 우선 | 정본 추가 |

**유효성 재확인(변경 없음)**: D2의 유령 정본 5종은 **여전히 전부 부재**, LaTeX→평문 3벌 구현
**여전히 3벌 실재**, D3의 무변별 체인(`verify_step.py` 3상태 접힘 → `coach_models.dart:330-331`
"카운트로 충분" 미파싱 → `coach_signal_card.dart:143` `'확인 보류 일부'`) **여전히 유효**,
D4 재료 3/4 실재·`curriculum_notation_gate.py` **여전히 부재**, `notation_contract.json`에
`latex_cases` **여전히 없음**(현 키: `numeric_cases`·`equivalence_cases`). **D2·D3·D4는 원문
그대로 유효하다.**

### §7.2 Δ1·Δ2가 뒤집는 것 — 구멍은 좁아졌는데 피해는 커졌다

1차는 CI 경로 필터 구멍을 *"D1이 만들 미래 게이트가 유령이 되는 것을 막는 예방 조치"*로 적었다.
재검증하면 **예방 조치가 아니라 이미 발생한 결함의 수습**이다:

- 봉인 대상이 1건(`notation_contract.json`)에서 **3건**으로 늘었다 —
  `segmentation_contract.json`(`NLP-03` 착지분)·`scene_contract.json`(`MOB-14` 착지분)이 추가됐다.
- 뒤 2건은 **미래가 아니라 현재**다. 그 계약을 검증하는 Dart 골든이 *이미 리포에 있고*, mobile
  잡이 skip되면 *그 골든이 안 돈다*. 즉 `NLP-03`·`MOB-14`가 세운 계약은 **fixture만 고치는 PR에
  대해 지금 이 순간 미집행**이다.

**이 형태는 §6 계열 B("도는데 근거가 없다")의 세 번째 변형이다.** 계열 B가 *게이트는 도는데
근거가 유령*이었다면, 이번 것은 **계약과 골든이 둘 다 실재하는데 트리거가 없어 안 도는** 형태다.
증상은 red도 green도 아닌 **skip**이며, skip은 required check에서 "충족"으로 계상된다
(`ci.yml:543`·`:667` 주석이 *"required check는 skipped=충족"*이라고 자인). 판정 기준을 한 단계 더
민다:

> "게이트가 도는가" → "게이트가 지목하는 근거가 실재하는가"(D2) → **"게이트를 트리거하는 경로가
> 그 게이트가 지키는 파일을 실제로 덮는가"**

`MATH-01` acceptance ①·④를 이에 맞춰 갱신했다(2026-08-11).

### §7.3 D6 — 역방향(LaTeX → 학생 가독 표기)의 학생 대면 공백 (`MATH-05` · 신규)

**문제.** 틀의 기능 29는 양방향을 요구하고, 역방향을 `LaTeX → AST → 자연표기`로 그린다. 1차는
이것을 백엔드 `sympy.latex` 생성으로 읽고 *"렌더 권위 이원화"*를 근거로 미채택했다(§2-⑨).
그 판단은 **백엔드 생성 축에 대해서는 지금도 옳다.** 그러나 틀이 그린 역방향의 **실제 용도는
표시**(학생이 읽을 표기로 되돌리기)이고, 그 축은 미채택된 적이 없으며 실측하면 뚫려 있다:

| 표면 | 실측 | 판정 |
|---|---|---|
| MathLive 입력 미리보기 | `mathlive_input_screen.dart:83-89` — `Text(_latex)` **원문 LaTeX** | ⚠️ 라이브 |
| OCR 인식 결과 | `ocr_capture_screen.dart:201` — `SelectableText(result.plainLatex)`(필드명과 달리 내용은 LaTeX) | ⚠️ 라이브 |
| 채팅 버블 | `chat_screen.dart:204` `latexToPlainSolution(latex)` 경유 | ✅ `MOB-06`이 해결 |
| 문항 본문 | `problem_screen.dart:155` plain `Text` | **라이브 아님** — 측정 근거 아래 |

**측정이 갭을 줄인 지점 (기록 의무).** 문항 본문 축은 "앱에 수식 렌더가 없다"는 이유로 크게 부를
수 있었으나, **코퍼스를 실측하니 갭이 아니었다** — `problem_bank_*` 7뱅크의 본문+해설+선지
**2,647건 중 LaTeX 매크로 포함 0건(0.00%)**. 코퍼스가 caret 평문 표기(`x^2 - 5x = 0`)를 쓰므로
학생이 보는 발문에 `\frac`이 뜨는 일이 현재는 없다. **잠재 공백으로만 적고 범위에서 뺀다**
(발화 조건: 코퍼스에 매크로가 관측될 때). *"측정 없는 도입 없음"은 갭을 만드는 방향뿐 아니라
**갭을 접는 방향**으로도 적용된다.*

**왜 이게 D인가 — 같은 앱 안에서 세 표면의 처리가 갈린다.** `MOB-06`이 채팅 버블 한 곳에
`latexToPlainSolution`을 배선했는데, 나머지 두 표면은 **같은 함수를 부르지 않는다.** 정본이
없어서가 아니라 **정본이 있는데 일부 표면에만 배선된** 형태다 — "만들었는데 안 돈다"(계열 B)와
"만들었는데 *일부만* 돈다"의 차이이며, 후자가 더 조용하다(대다수 경로가 정상이라 아무도 못 본다).

**정합 설계(신규 자산 0)**: 두 표면에 이미 정본인 `latexToPlainSolution`을 적용한다.
- `flutter_math_fork` **재도입 없음** — `pubspec.yaml:40-42`의 *"기능 착수 시 재도입"* 주석 유지.
  이 슬라이스는 **수식 조판 엔진 도입이 아니라 이미 있는 표기 변환의 미적용 표면 2곳을 닫는 것**
- 코어에 렌더러를 넣지 않는다(**Renderer = Plugin** 불변 · `05 §5.2`)
- `MATH-01`이 `latexToPlainSolution`을 3자 교차 골든 아래로 넣으면 **이 표시 경로까지 계약 지배를
  받는다** — D6은 D1의 소비자이지 경쟁자가 아니다

**변별력**: 변환 적용을 의도적으로 되돌리면 위젯 테스트가 red, 복원하면 green.

**범위 밖**: (a) 수식 조판 렌더(KaTeX·`flutter_math_fork`) — 별개 축·미채택 유지. (b) 백엔드
LaTeX 생성 — §2-⑨ 영구 미채택. (c) 문항 본문 — 위 측정으로 제외. (d) MathLive 위젯 접근성 — §4-①.

**태스크**: `MATH-05-reverse-notation-display-surface` (stage S3 · priority 3 · layer mobile)

### §7.4 정직한 공백 추가 — SymPy 연산 시간 상한 부재 (**태스크 신설 없음**)

`l3/` 전체에 계산 타임아웃·샌드박스가 **0건**이다(`SIGALRM`·`signal.alarm`·`setrlimit`·
`multiprocessing`·`asyncio.wait_for` 전부 부재 — grep 확인). `sympy.simplify()`는 상한 없이
실행되고, 그 경로는 `POST /v1/verify-step`·`/verify-solution`·`/verify-answer`로 HTTP 노출된다.

**처음엔 DoS 표면으로 보였으나 실측이 severity를 낮췄다** — 두 겹의 방어가 이미 있다:

1. **입력 크기 상한** — `api/verify.py:42-46` `_MAX_EXPR_LEN=4000` · `_MAX_CONDITIONS=50` ·
   `_MAX_ANSWER_VARS=50` + 필드 `max_length`. 주석이 *"남용 방어 상한"*으로 자인한다.
2. **인증 필수** — 세 엔드포인트 전부 `user: ConsentedUser`. **무인증 표면이 아니다.**

남는 것은 *"인증된 학생이 4000자 이내 병리적 식으로 CPU를 오래 점유할 수 있다"*는 **잠재 가용성
리스크**이고, **그 지연을 측정한 데이터가 0건**이다. 여기서 태스크를 만들면 정확히 *"측정 없는
도입"*이 된다. 따라서 **공백으로만 적는다.**

- **발화 조건**: verify 경로 p99 지연 관측이 배선되고, 꼬리가 실제로 관측될 때.
- **중복 회피 확인**: `SEC-18-prod-surface-hardening`(타 세션 claim 중)의 범위는 `/docs`·
  `/openapi.json` 무인증 노출 + CORS 결정 동결이라 **이 축과 겹치지 않음**을 원격 YAML로 확인했다.

### §7.5 등재 요약 (재검증 후 현행)

| 태스크 | 설계 | stage | prio | 상태 |
|---|---|---|---|---|
| `MATH-01-notation-normalization-authority` | D1 | S3 | 2 | 회수 + **acceptance ①④ 갱신**(Δ1·Δ2) |
| `MATH-02-notation-canon-reference-integrity` | D2 | S3 | 2 | 회수 — 실측 재현으로 **원문 유효** |
| `MATH-03-verify-reason-code-discrimination` | D3 | S3 | 2 | 회수 + **acceptance ② 선례 반영**(Δ·`rephrase.py`) |
| `MATH-04-curriculum-notation-range-gate` | D4 | S4 | 3 | 회수 — 실측 재현으로 **원문 유효** |
| `MATH-05-reverse-notation-display-surface` | **D6** | S3 | 3 | **신규 등재**(Δ6) |
| `NLP-03` `depends_on` 추가 | — | — | — | **철회**(Δ5) |
| SymPy 연산 시간 상한 | — | — | — | **태스크 신설 없음** — §7.4 공백 + 발화 조건 |

`MATH-05`는 `backlog.py add` CLI 경유로 등재했다(ID 손편집 0). `validate` green **244건**
(회수 직후 243건 · 회수 전 239건). `overlap MATH-05` 겹침 0.

### §7.6 §6 반복 실수 — 계열 추가

**계열 C — "미병합 고립" 4회차 (설계 문서 형태)**

| 회차 | 사례 | 고립분 | 피해 형태 |
|---|---|---|---|
| 1~3 | `problem_bank_gap_review_r2.md` §6-ⓐ 등재 3건(`NS-02` 등) | 구현·계약 | 코드 소실·게이트가 유령 근거 위에 서게 됨(= 이 문서의 **D2**) |
| 4 | **이 문서 자신 + `MATH-01`~`04`**(PR #678, 8일) | 설계 문서·백로그 | **같은 대조를 두 번 하게 만듦** — 중복 착수 직전까지 감 |

4회차가 앞 3회와 다른 점: 고립분이 코드가 아니라 **판단**이라 소실이 조용하다. 코드는 없으면
테스트가 red를 내지만, **"이미 내린 판단"은 없어도 아무 신호가 안 난다** — 다음 세션이 처음부터
다시 판단할 뿐이고, 그건 실패처럼 보이지 않는다. `D2`가 발견한 `NS-02` 고립도 정확히 이 형태로
1년 가까이 유지됐다.

이 문서에 이미 있는 방어(SessionStart 훅의 *"미머지 브랜치의 신규 설계 문서(중복 착수 확인)"*
목록)는 **작동했다** — 이 세션이 착수 전에 PR #678을 찾은 것이 그 훅 덕분이다. 규칙 신설이
아니라 **그 목록을 실제로 조회하는 것이 착수 절차의 일부임**을 여기 기록한다.

### §7.7 검증 — 무엇을 돌렸고 결과가 무엇인가

- `python3 scripts/harness/backlog.py validate` → **EXIT=0** · `태스크 244건, 게이트 7건, 트랙 3건`
  (회수 직후 기준선 243건 → `MATH-05` 등재 후 244건)
- `python3 scripts/harness/backlog.py overlap MATH-05-reverse-notation-display-surface` →
  **EXIT=0** · `겹침 없음`
- 코퍼스 LaTeX 매크로 실측 — `problem_bank_*/problems.jsonl` 7뱅크 본문+해설+선지 **2,647건 중
  0건(0.00%)**(§7.3의 범위 축소 근거)
- 소스 실측(전건 파일·라인 직접 확인): 유령 정본 5종 부재 · `ci.yml:74,83,86` 필터 3종 ·
  Dart 골든 2개의 `File('../../data/...')` 경로 · `mathlive_input_screen.dart:83-89` ·
  `ocr_capture_screen.dart:201` · `api/verify.py:42-46` 상한과 `ConsentedUser` 의존

**정직한 공백 — 돌리지 못한 것**: `python -m whymath_backend.l3.notation_coverage`를 이 세션
환경에서 직접 실행해 green을 재확인하려 했으나 **백엔드 의존(pydantic) 미설치로 실행 실패**
(`EXIT=1` · `ModuleNotFoundError: No module named 'pydantic'`). 게이트가 `ci.yml:296`에 배선돼
있다는 것은 정적으로 확인했으나, **"돌려서 green을 봤다"고 쓰지 않는다** — D2가 지적하는 실수의
형태가 정확히 "확인하지 않은 것을 확인한 것처럼 적는 것"이기 때문이다.

**변별력**: 이 슬라이스는 소스 로직 변경이 0이라 결함 주입 대상이 없다. 대신 §7이 *새로 주장하는*
사실 4개를 각각 **틀릴 수 있는 형태로** 확인했다 — ①mobile 필터에 계약 파일 3건 부재(필터 정규식
직접 대조) ②Dart 골든 2개가 그 파일을 실제로 읽음(`File()` 경로 확인) ③코퍼스 매크로 0.00%
(**갭이 아님을 증명하는 방향**의 측정 — 새 갭을 크게 부르려는 유인과 반대로 작동했다) ④두 표면의
원문 LaTeX 노출(소스 라인 확인). ③이 없었으면 D6은 실제보다 크게 적혔을 것이다.
