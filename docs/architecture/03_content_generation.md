# L3. 콘텐츠 생성·검증 (Content Generation & Verification)

> *비용 1/10*과 *환각 0*에 가까운 LLM 활용.

## 책임

LLM 호출의 *모든 책임*을 단일 계층으로 집약: 라우팅, 호출, 도구 호출, 검증, 캐싱, 비용 추적.

## 핵심 컴포넌트

### 1. 모델 라우터
- 입력: 작업 종류·난이도·예산·구독 티어 (+동기/비동기·대화 단계·호출지점)
- 출력: 비용·위치 티어 (LOCAL/CLOUD_MID/CLOUD_HIGH) + LOCAL 선택 시 **로컬 패밀리 (MATH/GENERAL)** × 로컬 크기 티어 (fast/mid/quality)
- **목표 분포(비용·위치 축): 로컬 80% / 중급 18% / 최고 2%**
- **태스크 유형(수학 vs NLP)으로 패밀리 분기**: 수학 계산·풀이 → MATH(qwen2-math), NLP 추출·정규화·매칭·분류 → GENERAL(qwen2.5). 2026-05-20 실측 근거(03a §0.2·§C.0).
- **상세 분기 설계 → `docs/architecture/03a_l3_router_design.md`**: 세 라우팅 축의 통합·명칭 충돌 해소·패밀리 축(§0)·입력 분류기(§B)·decision table·의사코드(§C: §C.0 패밀리/§C.2 크기)·에스컬레이션/폴백 체인(§D)·스키마 확장(§G). 본 문서가 *무엇을*이라면 03a는 *어떻게 분기하는가*다.

### 2. LLM 클라이언트 (단일 진입점)
- 모든 LLM 호출은 이 클라이언트 경유
- Langfuse 자동 추적
- Redis 캐싱
- 재시도·fallback

### 3. PRM 검증기
- 단계별 정확성 검증
- 후보: Qwen2.5-Math-PRM-72B (로컬)
- 학생 응답 *전에* 검증 통과 필수

### 4. 도구 호출 (Tool Use)

| 도구 | 용도 |
|---|---|
| SymPy | 수식 계산·풀이 (LLM에 계산 시키지 말 것) |
| Wolfram Alpha | SymPy로 안 되는 복잡 케이스 |
| Mathpix OCR | 손글씨 수식 → LaTeX |
| Manim | 시각화 영상 자동 생성 |

### 5. 다중 풀이 생성
같은 문제 → 대수적·기하적·조합적·귀납적 N개 접근

WhyMath의 다중 풀이는 6가지 `solution_approaches`(대수적·기하적·조합적·귀납적·시각적·역방향 등)를 축으로 한다. PRD v1.1의 `SolutionPath` 엔티티는 이 6가지 접근 *각각의 내부 구조*를 정의하는 스키마로 흡수한다 — 즉 `solution_approaches`는 *어떤 유형의 풀이인가*를, `SolutionPath`는 *그 풀이가 어떤 개념을 어떤 순서로 통과하는가*를 담당한다. (상세는 아래 "PRD v1.1 엔티티 통합" 참조)

### 6. 응답 캐싱
- Redis 기반
- TTL 1주
- 동일 컨텍스트 재호출 방지

> **콘텐츠 전략(2층 캐시·render-vs-generate)의 상세 → `03c_content_strategy_cache.md`**: 위 Redis 캐시는 *프롬프트-해시*
> 계층(정확 반복)이다. 그 위에 *개념 주소화 중립 DSL 캐시*(영구 자산)와 교수법 어댑터 렌더를 얹어, "AI가 매번 생성"이
> 아니라 "중립 자산을 선택 + 얇게 렌더"로 비용을 낮춘다(교수법 선택·적응은 L4 `04d_adaptive_pedagogy_engine.md`).

## 모델 풀

라우팅에는 **세 축**이 있다 — *비용·위치 축*(어디서 생성하나), *로컬 모델 패밀리 축*(LOCAL일 때 수학 vs NLP 어느 패밀리인가), *로컬 모델 크기 축*(어느 크기인가). 아래 표의 `CostTier` 열이 비용·위치 축이고, LOCAL 행은 `ModelFamily`(MATH/GENERAL) × `LocalModelTier`(fast/mid/quality)로 갈린다. 세 축의 통합·분기 결정 로직은 **`docs/architecture/03a_l3_router_design.md`**(라우터 상세 설계서) 참조.

> **명칭 충돌 해소**: `mid`가 두 축에 모두 존재한다 — 비용·위치 축의 클라우드 중급(`CLOUD_MID`=Claude Sonnet)과 로컬 크기 축의 7b 모델(`LocalModelTier.MID`). 혼동 방지를 위해 *비용·위치 축의 클라우드 티어는 `CLOUD_` 접두사로 표기*하고(`CLOUD_MID`/`CLOUD_HIGH`, 기존 `LLMTier.MID`/`HIGH`에 대응), `mid`를 단독으로 쓰지 않는다. 상세 규칙은 03a §0.1.

> **패밀리 축(축3) 추가**: 2026-05-20 Phaiakes9 태스크 인지 실측이 드러낸 바, 로컬은 *크기만*으로 부족하고 **태스크 유형(수학 계산 vs NLP)에 따라 모델 패밀리를 먼저 갈라야** 한다 — NLP(추출·정규화·매칭)를 수학 특화 모델(`qwen2-math`)로 돌리면 7b조차 0%, 일반 모델(`qwen2.5`)로 바꾸니 match 3b=100%·translate 7b=75%였다. 따라서 로컬 실제 모델 = (패밀리 `MATH`/`GENERAL`) × (크기 fast/mid). 상세 규칙·근거는 03a §0.2·§A.0·§C.0.

| CostTier (비용·위치) | ModelFamily (패밀리) | LocalModelTier (크기) | 모델 | 위치 | 비용/1k | p50·용도 |
|---|---|---|---|---|---|---|
| LOCAL | MATH | fast | qwen2-math:1.5b | Phaiakes9 | 0원 | 1.0s · 수학 산술·1단계 계산 (산술 87.5%) |
| LOCAL | MATH | mid | qwen2-math:7b | Phaiakes9 | 0원 | 3.9s · 수학 풀이·2~3단계 추론·깊이추론 (산술 100%) |
| LOCAL | GENERAL | fast | qwen2.5:3b | Phaiakes9 | 0원 | 1.0s · NLP 개념ID 매칭·분류 (match 100%) |
| LOCAL | GENERAL | mid | qwen2.5:7b | Phaiakes9 | 0원 | 3.9s · NLP 개념추출·번역정규화 (translate 75%) |
| LOCAL | (무관) | quality | qwen3.5:27b | Phaiakes9 | 0원 | 13.9s · 검증·복잡 추론·PRM·백그라운드(비동기 전용) |
| CLOUD_MID | — | — | Claude Sonnet 4.6 | API | ~$0.003/$0.015 | 어려운 진단·일반 코칭 (목표 18%) |
| CLOUD_MID | — | — | GPT-5-mini | API | 유사 | 대안 |
| CLOUD_HIGH | — | — | Claude Opus 4.7 | API | ~$0.015/$0.075 | 어려운 진단 (목표 2%) |
| CLOUD_HIGH | — | — | GPT-5 / o3 | API | 비쌈 | 킬러 문항·증명 |

> 크기 3종(fast/mid/quality)은 2026-05-19 GPU 지연 벤치로, **패밀리 2종(MATH/GENERAL)은 2026-05-20 태스크 인지 품질 실측**으로 확정(둘 다 `MEMORY.md` 결정 로그). **fast만 SLA 게이트(p50<2s) 통과** → 동기 즉답 기본 경로. quality(27b)는 *동기 불가, 비동기 큐 전용*이며 패밀리 무관(27b가 양 패밀리 포괄). 분기 결정표는 03a §C.0(패밀리)·§C.2(크기).

## 환각 방어 (5중 + PRD 4중 레이어 통합)

### WhyMath 5중 환각 방어 (기존)

1. 응답 형식 검증 (스키마)
2. PRM 단계 검증
3. 도구 검증 (수치는 SymPy)
4. 자기 일관성 (N회 → 다수결)
5. 사람 검수 큐 (신뢰도 낮을 때)

### PRD v1.1 환각 방어 4중 레이어 흡수·정렬

WhyMath PRD v1.1은 환각 방어를 *4중 레이어*로 정의했다. 이는 WhyMath 5중 방어와 *대체 관계가 아니라 정렬·보강 관계*다. 두 체계를 다음과 같이 매핑한다.

| PRD 4중 레이어 | 내용 | WhyMath 5중과의 관계 |
|---|---|---|
| ① evidence-based 프롬프트 | LLM이 근거를 *verbatim quote*(원문 그대로 인용)하도록 강제. 출처 없는 주장 생성 차단. | WhyMath 1번(스키마 검증)을 **선행 보강** — *생성 단계에서* 환각을 줄이는 입력측 방어. 5중 방어는 출력측 검증이 중심이었으므로 이 레이어가 가장 큰 신규 가치. |
| ② SymPy/Lean 자동 검증 | 수식·수치는 SymPy, 형식 증명은 Lean으로 기계 검증. | WhyMath 3번(도구 검증)과 **동일 축** — Lean 형식 증명을 명시적으로 추가. |
| ③ 자기검증 패스 | *별도 LLM 호출*로 생성 결과를 재검토 (생성 LLM과 분리된 검증 LLM). | WhyMath 4번(자기 일관성)을 **확장** — 단순 N회 다수결을 넘어, 검증 전용 프롬프트·모델로 교차 검증. L3 LLM 5개 핵심 호출지점 중 "자기검증" 항목과 연결. |
| ④ 사람 표본 검수 | 생성물의 10% 표본 + 사용자 신고분을 사람이 검수. | WhyMath 5번(사람 검수 큐)을 **정량화** — "신뢰도 낮을 때"라는 조건부 검수에 더해, *상시 10% 무작위 표본* + *사용자 신고 트리거*를 명시. |

**정렬 후 통합 방어 체계** (생성 → 검증 → 운영 순):
- **입력측 (생성 전·중)**: ① evidence-based 프롬프트 — verbatim quote 강제
- **출력측 자동 (생성 직후)**: 1번 스키마 검증 → ②/3번 SymPy·Lean·도구 검증 → 2번 PRM 단계 검증
- **출력측 교차 (자동, 추가 호출)**: ③/4번 자기검증 패스 + 자기 일관성 다수결
- **운영측 (지속)**: ④/5번 사람 검수 — 신뢰도 낮은 건 즉시 큐 + 상시 10% 무작위 표본 + 사용자 신고 트리거

> **원칙**: PRD 4중 레이어와 WhyMath 5중 방어는 *번호가 다른 두 리스트*가 아니라 *하나의 파이프라인*이다. 어느 단계도 생략 불가 — CLAUDE.md 절대 금기 "LLM 응답을 검증 없이 학생에게 제공 금지"의 구체적 실행이다. 특히 ① evidence-based 프롬프트는 *데이터 출처가 L1 검정교과서 단원명·성취기준 등 인용 가능 범위*임을 verbatim quote로 강제해, 저작권 금기(본문 복제 금지)와도 직결된다.

## PRD v1.1 엔티티 통합

### SolutionPath — 개념 시퀀스로 인코딩된 풀이 (L3 보유)

PRD v1.1의 `SolutionPath`는 풀이를 *자연어 텍스트*가 아니라 **개념 노드를 통과하는 시퀀스**로 인코딩하는 엔티티다. WhyMath L3가 보유하며, 기존 다중 풀이 생성의 출력 구조를 *구조화*한다.

**`solution_approaches`와의 관계 (경계 명시)**:
- WhyMath의 `solution_approaches`(6가지 풀이 유형: 대수적·기하적·조합적·귀납적·시각적·역방향)는 *풀이의 분류 축*이다.
- PRD의 `SolutionPath`는 그 6가지 *각 유형의 한 인스턴스가 갖는 내부 스키마*다.
- 즉 한 문제에 대해 L3는 여러 개의 `SolutionPath`를 생성하고, 각 `SolutionPath`는 `approach_type` 필드로 6가지 유형 중 하나에 태깅된다. "기하적 풀이"가 곧 하나의 `SolutionPath`이며, 그 안에 개념 시퀀스·단계·힌트가 담긴다.

```python
class SolutionStep(BaseModel):
    """풀이 한 단계"""
    order: int
    content: str                      # 단계 내용 (자연어 + 수식)
    concept_node_id: str              # 이 단계가 통과하는 L1 개념 그래프 노드
    hint: str                         # 이 단계에서 막힌 학생용 힌트 (L4 graded Hint와 연결)
    common_errors: list[str]          # 이 단계에서 흔한 오류 (L1 misconceptions와 매핑)
    reasoning_type: ReasoningType | None   # 스텝 단위 추론 유형 (폐쇄 7종·선택·§ReasoningStep)
    justification: Justification | None    # 정당화 근거 참조 (정리·개념·이전 스텝·선택)
    sympy_verified: bool              # 이 단계가 SymPy 자동 검증을 통과했는지
    lean_verified: bool | None        # 형식 증명 단계인 경우 Lean 검증 여부

class SolutionPath(BaseModel):
    """문제 1개에 대한 풀이 경로 1개"""
    problem_id: str
    approach_type: str                # WhyMath 6가지 solution_approaches 중 하나
    concept_sequence: list[str]       # 통과하는 개념 노드 ID의 순서열 — 풀이의 '골격'
    steps: list[SolutionStep]         # 단계별 상세 (내용·힌트·흔한 오류·검증 표시)
    embedding: list[float]            # 풀이 임베딩 벡터 (유사 풀이 검색·군집용)
    verified_by_human: bool           # 사람 검수 통과 여부 (환각 방어 ④와 연결)
```

- **`concept_sequence`**: 풀이의 *골격*. "이 풀이는 [개념A] → [개념B] → [개념C] 순으로 개념을 통과한다"를 노드 ID 순서열로 표현. 자연어 풀이 텍스트는 `steps[].content`에 남지만, *비교·검색·분류의 기준*은 `concept_sequence`다.
- **`steps`**: 각 단계의 내용 + 막힌 학생용 힌트 + 흔한 오류 + SymPy/Lean 검증 표시. 힌트는 L4 교수학 엔진의 graded `Hint`로 전달되고, 흔한 오류는 L2 오개념 매핑·L1 misconceptions 카탈로그와 연결된다.
- **`embedding`**: 풀이 임베딩 벡터. 유사 풀이 검색(벡터 DB)·풀이 군집화에 사용. 임베딩 모델은 CLAUDE.md 기술 스택 표의 OpenAI text-embedding-3-large.
- **L2 연결**: L2 `MasteryState.preferred_solution_style`(02 문서 참조)은 이 `SolutionPath.approach_type`을 값으로 갖는다. L2가 "이 학생은 기하적 `SolutionPath`에서 정답률·체류시간이 좋다"를 추적하면, L4가 힌트·다중 풀이 제시 순서를 정할 때 그 유형의 `SolutionPath`를 우선 노출한다.
  > ⚠️ **실측 부기(2026-08-11 — 04f §정정)**: `MasteryState`·`preferred_solution_style`은 **코드에 없다**(04d §2.1 "생산자 부재" 판정). 이 연결은 설계 스케치이며, 현행 교수법 선택의 실제 입력은 `StudentSignals`(숙달 3축·오개념 가설·시도/힌트 이력·학년 밴드)다 — 04f §4 참조.

### ReasoningStep — 추론 유형·정당화의 얇은 도입 (교육 추론 엔진 §2.2)

`docs/architecture/math_dsl_evolution.md`는 MATH DSL이 **교육 추론 엔진**(§2.2·권장 1순위)으로 진화해야 한다고 판정했고, 그 첫 벽돌로 **추론 스텝의 기계가독화**(§3.5 Phase 1)를 지목한다. 지금까지 `SolutionStep.content`는 자연어+LaTeX *불투명 문자열*이라, 기계가 "이 단계가 어떤 추론 유형이며 무엇에 근거하는가"를 읽지 못했다. 이를 **얇은 선택 필드 2종**으로 연다 (기존 스펙 100% 하위호환 — strict superset).

- **`reasoning_type`** (`ReasoningType | None`): 스텝 단위 추론 유형. **폐쇄 7종** — `DEDUCTION`(연역)·`SUBSTITUTION`(치환)·`CASE_SPLIT`(사례분류)·`INDUCTION`(귀납)·`TRANSFORMATION`(동치변형)·`HEURISTIC`(휴리스틱)·`BACKWARD`(역방향). 구현 정본은 `schema/enums.py`의 `ReasoningType`(단일 좌석). `approach_type`(풀이 *전체* 6유형)과는 **다른 축** — 한 대수적 풀이 안에서도 스텝마다 치환·사례분류·귀납이 섞인다.
- **`justification`** (`Justification | None`): 이 스텝이 "왜 정당한가"의 근거 참조 — 정리 개념노드(`theorem_concept_ids`)·일반 개념노드(`concept_node_ids`)·이전 스텝(`prior_step_orders`, 각 값 < 현재 order·전방참조 금지)의 얇은 묶음. 스펙은 `schemas/v1.1/solution_path.schema.yaml`의 `Justification` 블록.

**경계 (premature abstraction 금지·§4)**:
- 둘 다 **선택(nullable·빈 기본값)** — 미지정 스텝도 유효(기존 `SolutionStep` 그대로).
- Phase 1은 **태그·근거 표현만** 둔다. 유형별 검증 결선(PRM/SymPy가 `reasoning_type`별로 검증)·LLM 태깅 파이프라인·`SolutionStep` Pydantic/ORM 실체화는 **Phase 2**(다중 풀이 생성이라는 소비처가 설 때).
- `justification`은 **참조(ID/order)만** 담는 인라인 묶음 — 완전 형식논리 증명 트리·자체 정리증명기·그래프 엣지/ORM 테이블로 승격하지 않는다(경계된 Tier3 Lean 위임·§2.9).
- `ReasoningType`은 **폐쇄집합** — 무한 세분화 온톨로지 금지(§2.2 금기). 유형 추가는 의도적 결정.

### 🚨 개념 시퀀스 동치성 판정 — 휴리스틱 + 사람 검수 병행

PRD v1.1은 `concept_sequence` 비교만으로 두 풀이의 **"자동 동치성 판정"**(같은 문제의 두 풀이가 본질적으로 같은가)을 비교적 쉽게 가정한다. **WhyMath는 이를 그대로 수용하지 않는다.**

**왜 어려운가 — 연구 난제임**:
- **같은 노드를 지나도 본질이 다를 수 있다**: 두 풀이가 동일한 개념 노드 순서열을 통과해도, 각 단계의 *논리적 정당화·적용 방식*이 다르면 동치가 아니다. (예: 같은 "이차방정식 근의 공식" 노드를 지나도, 한쪽은 판별식 조건을 빠뜨려 부분적으로 틀릴 수 있다.)
- **다른 노드를 지나도 동치일 수 있다**: 대수적 풀이와 기하적 풀이는 `concept_sequence`가 전혀 겹치지 않아도 *같은 결론에 같은 타당성으로* 도달하는 동치 풀이다. 시퀀스 거리(편집 거리 등)만으로는 "다른 풀이"로 오판한다.
- 즉 `concept_sequence`는 동치성의 *필요조건도 충분조건도 아니다*. 이는 수학 풀이 동치성 일반의 *미해결 연구 난제*이며, 단순 시퀀스 매칭으로 닫히지 않는다.

**WhyMath의 입장 — 휴리스틱 + 사람 검수 병행**:
- **휴리스틱 1차 필터** (자동): `concept_sequence` 편집 거리 + `embedding` 코사인 유사도 + 최종 답 SymPy 동치 검사 + `approach_type` 일치 여부를 조합한 *동치성 점수*를 산출. 점수가 높으면 "동치 후보", 낮으면 "비동치 후보"로 *분류만* 한다 (확정하지 않음).
- **사람 검수 2차 확정** (운영): 동치성 *판정 결과를 학생에게 노출하기 전*에는 사람 검수를 거친다. 특히 (a) 휴리스틱 점수가 경계 구간인 건, (b) 새로운 `approach_type` 조합, (c) 사용자 신고 건은 *반드시* 사람 검수 큐로 보낸다. — 환각 방어 ④/5번과 동일한 큐를 공유한다.
- **점진적 자동화**: 사람 검수 결과를 누적해 휴리스틱 점수 임계값을 보정한다. 데이터가 충분히 쌓이기 전까지 "자동 동치성 판정"을 *제품 기능으로 단정하지 않는다*. 이는 CLAUDE.md "확실하지 않을 때 자신 있게 말함 패턴 금지"의 적용이다.

> **요약**: `concept_sequence`는 동치성 판정의 *강력한 단서*이지 *판정 그 자체*가 아니다. WhyMath는 "휴리스틱으로 좁히고 사람이 닫는다"를 원칙으로 한다.

## LLM 핵심 호출지점 (PRD v1.1)

PRD v1.1은 시스템 전반에서 LLM이 *반드시 호출되는* 5개 핵심 지점을 식별했다. WhyMath L3는 이 5개를 *모델 라우터를 경유하는 표준 호출 유형*으로 흡수한다 (CLAUDE.md "LLM 호출은 항상 라우터 경유" 준수). 각 지점은 라우터에서 작업 종류·난이도에 따라 비용·위치 티어(LOCAL/CLOUD_MID/CLOUD_HIGH)와 **로컬 패밀리(MATH/GENERAL)** × 로컬 크기 티어(fast/mid/quality)로 분기된다 (지점별 기본 패밀리×티어 매핑은 03a §B.2). **2026-05-20 태스크 인지 실측**으로 1·3·4(NLP)는 `GENERAL`(qwen2.5), 2(수학 추론)는 `MATH`(qwen2-math)로 확정됐다.

| # | 호출지점 | 역할 | 비고 (패밀리·티어는 2026-05-20 실측) |
|---|---|---|---|
| 1 | **개념 추출** | 문제·풀이·교과서 텍스트에서 다루는 *수학 개념*을 추출 | L1 개념 그래프·교과서 매핑 입력 생성. **NLP → GENERAL**, 보수적 mid(qwen2.5:7b). `set_f1` 측정 한계로 티어 잠정(03a §H 후속8) |
| 2 | **깊이 추론** | 추출된 개념의 *학습 위계상 깊이·선수 개념 의존성*을 추론 | L1 개념 그래프의 엣지(의존성) 후보 생성. **수학 추론 → MATH**, mid(난이도 높으면 QUALITY/CLOUD) |
| 3 | **번역·정규화** | 다국 커리큘럼·이질적 표기의 개념·문항을 *표준 형태로 정규화* | 다국 매트릭스(Phase 3)와 연결. **NLP → GENERAL**, mid(qwen2.5:7b — 3b 50%<하한, 7b 75%) |
| 4 | **개념 ID 매칭** | 자유 텍스트로 언급된 개념을 L1 개념 그래프의 *정식 노드 ID*에 매칭 | `SolutionPath.concept_sequence` 생성의 핵심. **NLP → GENERAL**, **fast(qwen2.5:3b — 3b 100%)**. 매칭 실패 시 사람 검수 |
| 5 | **자기검증** | 생성 결과(풀이·힌트·매칭)를 *별도 LLM 호출로 재검토* | 환각 방어 ③ 자기검증 패스와 동일. **QUALITY(qwen3.5:27b, 패밀리 무관·비동기)**. 생성 LLM과 분리된 검증 프롬프트·모델 |

- **5개 모두 라우터 경유**: 직접 호출 금지. 각 호출은 Langfuse 추적·Redis 캐싱 검토 대상이다.
- **NLP 호출지점(1·3·4)은 GENERAL 패밀리로 라우팅**: 수학 특화 모델로 돌리면 7b조차 0%였던 실측 교정(03a §0.2). 일반 모델(qwen2.5)이 정보 추출·형식 변환·코드 매칭에 적합하다.
- **개념 추출·번역정규화·개념 ID 매칭(1·3·4)**은 반복성이 높아 *캐싱 적중률 기여가 크다* — 동일 교과서 텍스트·동일 개념 표현은 재호출 없이 캐시 반환. (패밀리가 GENERAL이어도 캐싱 전략은 동일.)
- **자기검증(5)**은 *추가 비용*을 발생시키지만 환각 방어의 필수 레이어다. 비용 통제 KPI(학생당 월 LLM 비용)와 상충할 수 있으므로, 신뢰도가 이미 높은 LOCAL 생성물에는 자기검증을 *샘플링*으로 적용하는 등 라우터 정책으로 균형을 잡는다.

## 인터페이스 (L4·L5 호출)

```python
class L3LLMService:
    async def generate(
        self, prompt: str, system: str,
        request: RoutingRequest,
        context: dict | None = None
    ) -> LLMResponse: ...

    # PRD v1.1 SolutionPath — 개념 시퀀스로 인코딩된 풀이 생성
    async def generate_solution_paths(
        self, problem_id: str, n: int = 3
    ) -> list[SolutionPath]: ...

    # 두 풀이의 동치성 — 휴리스틱 점수만 반환, 확정은 사람 검수
    async def score_solution_equivalence(
        self, path_a: SolutionPath, path_b: SolutionPath
    ) -> EquivalenceScore: ...  # {score, verdict: "동치후보"|"비동치후보"|"검수필요"}
    
    async def verify_steps(
        self, problem: str, steps: list[str]
    ) -> list[StepVerification]: ...
    
    # 선언적 시각화 *명세*만 생성한다(05 §5.2·schema/visualization.py). 렌더(Manim·
    # Desmos·three.js)는 L5 ④ 비상구 책임 — bytes(영상) 반환은 7계층 경계 위반이었다.
    # 구현·검증 게이트: l3/visualization.py (슬라이스 92).
    async def generate_visualization_spec(
        self, concept: str, level: str
    ) -> Visualization: ...  # 선언적 JSON 명세 (영상 아님)
    
    async def generate_multi_solutions(
        self, problem: str, n: int = 3
    ) -> list[Solution]: ...
```

## 비용 통제

### 사용자별 일일 한도 (원)
- Free: 100
- Basic: 500
- Premium: 2,000
- Gifted: 5,000

### KPI
- 학생당 월 평균 LLM 비용 (목표: 1,000원 이하 → 500원)
- 로컬 LLM 비율 (목표: 80%+)
- 캐싱 적중률 (목표: 30%+ → 50%+)

## 성공 기준

### Phase 1
- ✅ 라우터 (로컬 80%) — LLM 5개 핵심 호출지점 모두 라우터 경유
- ✅ SymPy 통합 — 환각 방어 ② 자동 검증
- ✅ Mathpix OCR
- ✅ Langfuse 추적
- ✅ 학생당 월 LLM 비용 < 1,000원
- ✅ evidence-based 프롬프트 (환각 방어 ① verbatim quote 강제)

### Phase 2
- ✅ PRM 가동
- ✅ Manim 자동 생성
- ✅ 다중 풀이 — `SolutionPath` 구조(개념 시퀀스·단계·힌트·검증 표시)로 생성
- ✅ 캐싱 30%+
- ✅ 자기검증 패스 (환각 방어 ③ 별도 LLM 호출)
- ✅ 동치성 휴리스틱 점수 + 사람 검수 큐 연동

### Phase 3+
- ✅ 자체 PRM 학습
- ✅ 캐싱 50%+
- ✅ 동치성 판정 점진적 자동화 (사람 검수 누적 → 임계값 보정)
- ✅ Lean 형식 증명 검증 (환각 방어 ②)
