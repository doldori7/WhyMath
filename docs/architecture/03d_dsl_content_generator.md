# 03d. DSL 콘텐츠 생성기 (Domain-Specific Language Content Generator)

> **문서 성격**: L3 콘텐츠 생성·검증의 서브 설계서. `03`(무엇을) → `03a`(어떻게 라우팅) → `03b`(WH-S 솔버) → `03c`(무엇을 저장·렌더)에 이어 **`03d`(콘텐츠를 DSL로 정의·검증·컴파일하는 방법)**.
>
> **한 줄**: LLM이 만든 자연어 콘텐츠를 교육 DSL로 정의하고, 결정론 검증·수학 검증·교육 검증을 통과한 것만 컴파일해 Runtime으로 넘긴다.

---

## 0. 왜 이 문서가 필요한가

WhyMath의 L3는 이미 `ConceptDSL`(렌더러-중립 개념 자산), `SolutionPath`(개념 시퀀스 풀이), `verify_answer/verify_step`(SymPy 기반 수학 검증)을 가지고 있다. 그러나 **"LLM이 콘텐츠를 만들 때 어떤 형태로 만들어야 하는가"**와 **"그 형태가 틀리면 어떻게 복구하는가"**는 여전히 암묵적이다.

DSL 콘텐츠 생성기는 이 간극을 메운다. LLM이 자유 텍스트로 콘텐츠를 만들어 DB에 직접 쓰게 하는 대신, **LLM → DSL 정의 → 다중 검증 → 컴파일 → Runtime 객체**로 이어지는 파이프라인을 명시한다.

이 문서의 핵심 주장은 세 가지다.

1. **LLM은 생성하고, 결정론적 엔진은 판정한다.**
2. **DSL은 콘텐츠의 Intermediate Representation(IR)이다.**
3. **수학 정답 FAIL은 다른 점수로 상쇄할 수 없다.**

---

## 1. WhyMath 아키텍처에서의 위치

WhyMath의 7계층에서 DSL 콘텐츠 생성기는 **L3 콘텐츠 생성·검증 계층의 내부 컴파일러**다.

```
L1  데이터 기반      — 교육과정·개념그래프·오개념 카탈로그 (자산 소유)
L2  학습자 모델      — BKT·IRT·숙달 상태 (소비)
L3  콘텐츠 생성·검증  — ★ DSL 콘텐츠 생성기 위치 ★
L4  교수학 엔진      — 렌더·적응·코칭·LearningScene (소비)
L5  상호작용        — Flutter·웹 클라이언트 (렌더)
L6  응용 모드        — 학교진도·수능·영재 모드 (오케스트레이션)
L7  커뮤니티        — 피드백·공유 (후속)
```

**경계 불변식**:
- L3는 L4를 임포트하지 않는다. L4가 L3를 호출한다.
- DSL의 `adaptation` 필드는 *적응 힌트*만 담는다. 실제 파라미터 변경은 L4에서 실행한다.
- `lint-imports`로 이 경계를 정적 강제한다.

---

## 2. DSL이 필요한 이유

일반적인 AI 콘텐츠 생성 흐름:

```
"중학교 2학년 연립방정식 문제 만들어줘"
        ↓
      LLM
        ↓
  자연어 문제 생성
        ↓
      저장
```

이 방식의 문제점:
- 정답 오류를 사후에 잡기 어렵다.
- 조건 누락·난이도 불일치를 재현 불가능하게 만든다.
- 풀이와 정답의 일관성을 기계가 검증할 수 없다.
- 오개념 태깅·자동 채점·문제 변형이 어렵다.

DSL을 사용하면:

```
사용자 요구
    ↓
Content Specification (무엇을 만들 것인가)
    ↓
Prompt Builder
    ↓
LLM (자연어 → DSL 생성)
    ↓
DSL Parser
    ↓
Syntax Validator
    ↓
Schema Validator
    ↓
Semantic Validator
    ↓
Math Validator ──→ SymPy
    ↓
Education Validator
    ↓
Quality Gate
    ↓
Content Compiler
    ↓
Runtime Object (Problem / SolutionPath / LearningScene 입력)
```

**핵심**: LLM은 콘텐츠를 *생각*하고, DSL은 콘텐츠를 *정의*하며, Runtime은 콘텐츠를 *실행*한다.

---

## 3. 설계 원칙

### 원칙 1 — LLM이 직접 콘텐츠 DB를 수정하지 않는다

```
LLM
 ↓
DSL
 ↓
Validator
 ↓
Compiler
 ↓
DB / Cache / Runtime
```

DB에 들어가는 것은 **검증된 DSL의 컴파일 결과**뿐이다. LLM 출력은 항상 검증 전 원시물로 취급한다(CLAUDE.md "LLM 응답을 검증 없이 학생에게 제공 금지").

### 원칙 2 — DSL은 교육 콘텐츠의 IR이다

컴파일러 관점에서:

```
Natural Language
       ↓
     LLM
       ↓
Education DSL        ← 사람이 읽을 수 있는 정의(YAML/JSON)
       ↓
Pydantic IR          ← 기계가 다루는 정본(ConceptDSL·ProblemDSL·SolutionPath)
       ↓
Compiler
       ↓
Runtime Object
```

- **Human-readable 형식(YAML/JSON)**은 저작·검토·버전 관리용이다.
- **Canonical IR**은 Pydantic 모델 + 렌더러-중립 LaTeX + 구조 태그다.
- DSL AST는 *참조·정규화·버전 관리*용으로만 사용한다. **수학 동치는 SymPy가 단일 권위**다(`math_dsl_evolution.md` §2.1).

### 원칙 3 — 수학은 별도의 검증기를 사용한다

LLM에게 "답이 7인지 확인해"라고 맡기지 않는다.

```
DSL
 ↓
Math Parser
 ↓
SymPy Solver
 ↓
Answer Verification
```

### 원칙 4 — 교육 메타데이터도 DSL에 포함한다

단순히 문제/정답만 정의하지 않는다.

- curriculum
- grade
- subject
- concept
- skill
- difficulty
- misconception
- cognitive_level
- prerequisite
- hint
- solution
- assessment

### 원칙 5 — 품질 점수보다 수학 정답이 우선한다

```
Math Correctness = FAIL
        ↓
전체 콘텐츠 = FAIL
```

수학 정답 오류는 다른 점수로 상쇄할 수 없다.

---

## 4. DSL 구조

### 4.1 3층 구조

WhyMath는 제안의 10개 영역 DSL을 다음 3층에 배치한다.

| 층 | 엔티티 | 책임 | 포함 영역 |
|---|---|---|---|
| **개념층** | `ConceptDSL` (기존) | "무엇을 가르치는가" | metadata, curriculum, concept, assessment(선택) |
| **문제층** | `ProblemDSL` + `SolutionPath` + `Hint` (신규/기존) | "평가와 풀이의 구조" | problem, variables, answer, solution, hint, assessment |
| **장면층** | `LearningScene` (L4, 기존) | "학생에게 어떻게 제시할 것인가" | adaptation(소비), pedagogy strategy |

`adaptation`은 DSL에 *메타데이터*로 포함되지만, 실제 파라미터 변경·개인화는 L4에서 실행한다.

### 4.2 Human-readable DSL 예시

```yaml
content:
  id: ALG-LIN-000123
  type: problem

  curriculum:
    subject: mathematics
    grade: middle_2
    domain: algebra
    concept: simultaneous_equations

  difficulty:
    level: 3
    target_time_sec: 120

  learning:
    skill:
      - equation_transformation
      - substitution

  problem:
    template: |
      x + y = {a}
      x - y = {b}
      일 때 x의 값을 구하여라.
    variables:
      a:
        type: integer
        range: [3, 15]
      b:
        type: integer
        range: [-5, 5]
    constraints:
      - "(a + b) % 2 == 0"

  answer:
    type: integer
    expression: "(a + b) / 2"

  solution:
    steps:
      - content: "두 식을 더한다."
        formula: "2x = a + b"
      - content: "양변을 2로 나눈다."
        formula: "x = (a + b) / 2"

  hints:
    - level: 1
      text: "두 식을 더해 보세요."
    - level: 2
      text: "y가 소거되도록 두 식을 계산하세요."

  misconception:
    target:
      - MIS-EQ-001
    diagnostic:
      trigger:
        answer_pattern: "x = a"
```

### 4.3 Canonical IR — Pydantic 모델

YAML은 사람용이다. 시스템 내부 정본은 Pydantic 모델이다.

```python
class ProblemDSL(BaseModel):
    content_id: str
    curriculum: CurriculumMeta
    difficulty: DifficultyMeta
    problem: ProblemTemplate
    answer: AnswerSpec
    solution: list[SolutionStepSpec]
    hints: list[HintSpec]
    misconception: MisconceptionSpec | None = None
    adaptation: AdaptationSpec | None = None
```

---

## 5. 검증 파이프라인

### 5.1 6단계 검증기

```
DSL 입력
   │
   ▼
① Syntax Validator      YAML/JSON 파싱, 필수 필드, 자료형, enum, 버전
   │
   ▼
② Schema Validator      Pydantic 모델 검증
   │
   ▼
③ Semantic Validator    학년-개념 일관성, 난이도-선수스킬 일관성
   │
   ▼
④ Math Validator        SymPy 정답·풀이·제약 검증
   │
   ▼
⑤ Education Validator   읽기 수준, 성취기준 매핑, 교육학적 적합성
   │
   ▼
⑥ Duplicate Validator   해시/임베딩 기반 중복 검사
   │
   ▼
Quality Gate
```

### 5.2 Quality Gate

```
                    DSL
                     │
                     ▼
             ┌───────────────┐
             │ Quality Gate  │
             └───────┬───────┘
                     │
        ┌────────────┼────────────┐
        ▼            ▼            ▼
     Syntax        Math        Education
      100%        ≥99%          ≥95%
        │            │            │
        └────────────┼────────────┘
                     ▼
                   PASS
                     │
                     ▼
                  Publish
```

**LLM confidence는 Quality Gate로 사용하지 않는다.**

### 5.3 품질 점수

```
Q = 0.25 × Math Correctness
  + 0.20 × Educational Alignment
  + 0.15 × Solution Consistency
  + 0.15 × Difficulty Accuracy
  + 0.10 × Language Quality
  + 0.10 × Originality
  + 0.05 × Metadata Completeness
```

단, `Math Correctness = FAIL`이면 전체 FAIL.

---

## 6. Variable DSL — 문제 변형

WhyMath에서 문제 생성보다 **문제 변형**이 훨씬 중요하다.

### 6.1 기본 구조

```yaml
problem:
  template: |
    {a}x + {b} = {c}

variables:
  a:
    type: integer
    range: [2, 9]
  b:
    type: integer
    range: [-20, 20]
  c:
    type: integer
    range: [-20, 40]

constraints:
  - "(c - b) % a == 0"
```

### 6.2 생성 결과

하나의 템플릿 정의로 다음을 자동 생성한다:

- `2x + 4 = 12`
- `3x - 6 = 9`
- `5x + 10 = 35`
- `7x - 14 = 21`

### 6.3 결정론적 생성

- 난수 시드를 입력받아 동일 시드 → 동일 인스턴스.
- SymPy로 제약을 검증한 후 치환.
- 제약을 만족하는 조합이 없으면 실패 신호 반환.

---

## 7. Repair Loop

LLM이 처음 생성한 DSL이 검증을 통과하지 못하면 사용자에게 실패를 노출하지 않는다.

```
DSL 생성
   ↓
Validation
   ↓
FAIL
   ↓
Repair Engine
   ↓
LLM (수정 요청)
   ↓
수정 DSL
   ↓
Validation
   ↓
PASS → 계속 진행
```

**상한**: 최대 3회 재시도. 3회 실패 시 `Human Review Queue`로 전달.

---

## 8. API 명세

### 8.1 생성

```
POST /api/v1/dsl/generate
```

요청:
```json
{
  "subject": "mathematics",
  "grade": "middle_2",
  "concept": "simultaneous_equations",
  "difficulty": 3,
  "count": 10,
  "purpose": "practice",
  "seed": 42
}
```

응답:
```json
{
  "generation_id": "GEN-20260815-001",
  "status": "validated",
  "contents": [
    {
      "content_id": "ALG-000123",
      "dsl_version": "1.2",
      "quality_score": 0.97,
      "publishable": true
    }
  ]
}
```

### 8.2 검증

```
POST /api/v1/dsl/validate
```

요청:
```json
{
  "dsl": "..."
}
```

응답:
```json
{
  "syntax": "PASS",
  "schema": "PASS",
  "semantic": "PASS",
  "math": "PASS",
  "education": "PASS",
  "duplicate": "PASS",
  "quality_score": 0.98,
  "publishable": true,
  "signals": []
}
```

### 8.3 컴파일

```
POST /api/v1/dsl/compile
```

응답:
```json
{
  "content_id": "ALG-000123",
  "runtime_type": "math_problem",
  "render": {
    "type": "equation_problem"
  },
  "grading": {
    "type": "numeric"
  },
  "concept_dsl": { ... }
}
```

---

## 9. 데이터 모델

### 9.1 핵심 테이블

```sql
content_definition      -- DSL의 정의 메타
content_version         -- 버전·DSL 원문·해시
content_validation      -- 검증 결과 이력
content_instance        -- Variable DSL로부터 파생된 실제 문제 인스턴스
content_usage           -- 학생 사용 이벤트
content_feedback        -- 피드백·신고
```

### 9.2 콘텐츠 생명주기

```
IDEA
 ↓
GENERATED
 ↓
PARSED
 ↓
VALIDATED
 ↓
VERIFIED
 ↓
REVIEWED
 ↓
PUBLISHED
 ↓
USED
 ↓
ANALYZED
 ↓
IMPROVED
 ↓
DEPRECATED
```

**폐쇄 루프**: 사용 데이터가 다시 DSL 개선으로 돌아온다.

---

## 10. WhyMath 기존 자산과의 통합

### 10.1 재사용 대상

| 기존 컴포넌트 | DSL 생성기에서의 역할 |
|---|---|
| `l3/render/dsl.py::ConceptDSL` | 개념층 IR |
| `l3/render/adapter.py::PedagogyAdapter` | 렌더 입력 소비 |
| `l3/router.py` | LLM 호출 라우팅 |
| `l3/pipeline.py` | 생성 파이프라인 |
| `l3/pregenerate/validator.py` | 기본 위생 검증기 |
| `l3/verify_answer.py`, `verify_step.py` | 수학 검증 백엔드 |
| `l3/equivalent/*_skeleton_generator.py` | 문제 변형 생성 패턴 |
| `schemas/v1.1/solution_path.schema.yaml` | 풀이 경로 스키마 |
| `schemas/v1.1/problem.schema.yaml` | 문제 스키마 |

### 10.2 신규 모듈

```
src/backend/whymath_backend/l3/dsl/
├── __init__.py
├── models.py            # ContentSpecification, ProblemDSL, ValidationReport, CompiledContent
├── variable_engine.py   # 템플릿 + 변수 + 제약 → 인스턴스
├── validators.py        # 6단계 검증기
├── math_verifier.py     # SymPy 기반 수학 검증
├── repair.py            # Repair Loop
├── compiler.py          # DSL → Runtime Object
└── quality_gate.py      # 품질 게이트
```

---

## 11. L3/L4 경계

**L3 (DSL 콘텐츠 생성기)**:
- DSL 정의·검증·컴파일
- Variable DSL 인스턴스 생성
- 품질 점수 산출
- 수학 정답 검증(SymPy)

**L4 (교수학 엔진)**:
- 어떤 교수법으로 렌더할지 선택
- 학생 상태 기반 적응 파라미터 변경
- LearningScene 조립
- 힌트 단계 게이팅

**금지**: L3가 학생 상태를 보고 DSL을 직접 변형하지 않는다. DSL에는 `adaptation` 메타데이터만 포함되고, 실제 변경은 L4가 수행한다.

---

## 12. KPI

| KPI | 목표 |
|---|---|
| DSL Parse Success | ≥99.9% |
| Schema Validation | ≥99.9% |
| 수학 정답 정확도 | ≥99.9% |
| Solution Consistency | ≥99.5% |
| Auto Publish Rate | 초기 50% → 90%+ |
| Human Review Rate | 초기 50% → 10% 이하 |
| 콘텐츠 중복률 | <1% |

---

## 13. Phase 로드맵

### Phase 1 — MVP
- Problem DSL
- Answer DSL
- Solution DSL
- Hint DSL
- Variable DSL 기본
- Repair Loop (3회 상한)
- API 3종 (`generate`, `validate`, `compile`)

### Phase 2 — 변형·진단
- Variable DSL 고도화
- Constraint DSL
- Difficulty DSL
- Misconception DSL
- 품질 게이트 운영

### Phase 3 — 적응·평가
- Adaptive DSL
- Assessment DSL
- Experiment DSL

### Phase 4 — 다과목 확장
- Physics DSL
- Chemistry DSL
- Certification DSL

---

## 14. 절대 금기

1. **자체 CAS·기호 수학 엔진 금지** — SymPy를 유일한 검증 권위로 유지한다.
2. **LLM이 DB 직접 수정 금지** — 모든 저장은 검증·컴파일 통과 후.
3. **DSL에 교수 방식 지시어 금지** — `ConceptDSL` 중립성 불변식과 동일.
4. **수학 정답 오류 상쇄 금지** — Math FAIL은 전체 FAIL.
5. **L3가 L4 임포트 금지** — `lint-imports`로 정적 강제.

---

## 15. 참조

- `docs/architecture/03_content_generation.md` — L3 콘텐츠 생성·검증 전체
- `docs/architecture/03c_content_strategy_cache.md` — 콘텐츠 전략·캐시
- `docs/architecture/math_dsl_evolution.md` — MATH DSL 진화 방향
- `schemas/v1.1/problem.schema.yaml` — 문제 스키마
- `schemas/v1.1/solution_path.schema.yaml` — 풀이 경로 스키마
- `src/backend/whymath_backend/l3/render/dsl.py` — `ConceptDSL` 구현
- `src/backend/whymath_backend/l3/pregenerate/validator.py` — 기본 검증기
