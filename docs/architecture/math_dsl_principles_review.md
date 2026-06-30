# Math DSL 구축 원칙 검토 — 「WhyMath 구축 플레이북(통합본) v1.0」

> **상태**: 검토(review) · **계층**: 횡단(L1·L3·L4·L5·Context를 가로지름) · **작성일**: 2026-06-30
> **검토 대상**: 「WhyMath 구축 플레이북 (통합본)」 v1.0(2026-06-29·55개 설계 메모 통합·Kiki 제공 DOCX)
> **관련**: `05a_learning_scene_dsl.md`(선행 검토) · `00_overview.md` · `04a`·`04b`·`03b` ·
> `src/backend/whymath_backend/schema/concept.py` · `schemas/v1.0`·`v1.1` · `MEMORY.md` · `CLAUDE.md`

---

## 0. 이 문서의 위치 — "재시작 지침"이 아니라 "자산 대조"

플레이북은 **백지(greenfield)에서 Math Cognitive OS를 세우는 설계 가이드**다. 그러나 WhyMath는
이미 **Phase 1 중반**으로 다음 자산이 가동·문서화돼 있다.

- 개념그래프 v0(437개념·581 선수엣지·Neo4j 적재) → **현재 원자 백본으로 전면 교체 진행 중**
  (원자 1,837·선수엣지 3,220·단원/소단원/원자 3단 계층·`atom_graph_v1`, 2026-06-21~ 마이그레이션)
- 오개념 카탈로그 839종 + 진단 매칭 v1.2 + judge 졸업 설계(`04b`)
- Schema v1.0(구현 정본)·v1.1 YAML(SolutionPath·MasteryState·Hint·StudentProfile)
- Pydantic 구현: `concept.py`(Concept/ConceptEdge/ProblemConcept/ConceptFusion)·`visualization.py`
  (4종 선언적 spec)·`misconception_hypothesis.py`(활성 가설)
- `LearningScene DSL`(`05a`·S0~S5e 구현 완료)·Visualization DSL(4종)
- 하네스: WH-1 튜터링(`04a`·상태 외부화)·WH-S 솔버(`03b`·MCTS+3Tier 검증)

**결정적 사실**: 이 플레이북은 *프로젝트가 이미 한 번 검토한 외부 문서 계열의 성숙·통합판*이다.
`05a_learning_scene_dsl.md`(2026-06-14)가 그 선행 문서("수학교육앱 인터페이스 설계 자동화" DOCX/PDF)
— 동일 논지(개념DB → Semantic AST → **Math UI DSL** → UI Generator → Flutter/Web, "화면을 만들지
말고 수학 구조를 만들어라", 종착점 **Math Knowledge Runtime**) — 를 검토해 **수용 원칙 + 교정
원칙**을 이미 확정해 두었다.

따라서 본 검토의 목적은 둘이다.
1. **기존 판정의 재확인** — 플레이북의 방향성은 우리 베팅(표현≠의미·L1-L4 독립 코어·상태 외부화)의
   *외부 검증*이지 방향 전환이 아니다(`05a` §10 재확인).
2. **통합판이 새로 더한 자료의 분류** — 노드 입도·12노드·6엣지·traversal 예산·순환참조 방지
   파이프라인·AST 5계층·오개념 그래프 7단계 분리·Context 예산 등을 기존 자산과 대조해
   **정합 / 충돌 / 공백**으로 정리.

> **플레이북 관통 원칙 2문장**
> - "수학 전체를 완벽하게 모델링하지 마라. 교육적으로 압축된 인지 그래프만 만들어라."
> - "LLM에게 전체 그래프를 절대 통째로 보여주지 마라."
>
> 둘 다 우리 원칙의 재진술이다 — 전자는 슬라이스 89(표현≠의미)·"핵심만 구조화+나머지는 동적
> 생성", 후자는 WH-1 상태 외부화("LLM은 매 턴 다음 교수학적 행동만 판단")와 Context 최소화.

---

## 1. 정합 (Aligned) — 플레이북이 기존 베팅을 외부 검증함

| 플레이북 원칙 | 기존 WhyMath 자산 |
|---|---|
| **5대 분리** (Concept≠Curriculum≠Renderer≠Prompt≠Misconception, AI≠전체그래프) | 슬라이스 89(표현≠의미)·`concept.py`(curriculum/renderer/prompt 미내장)·`05a` §1 |
| **AST≠Concept≠Visualization≠Curriculum≠Misconception** | `concept.py` / `visualization.py` / `curriculum_entry.schema.yaml` / 오개념 카탈로그 물리 분리 |
| **Misconception = 실패 패턴(개념 아님)·독립 그래프** | 오개념 카탈로그(839)·`misconception_hypothesis`·`04b` judge("제거만·생성 안 함") |
| **Reactive Misconception Loading**(반응형·proactive preload 금지) | WH-1 활성 오개념 가설세트(최대 5·신뢰도·시간감쇠)·`04b` shadow→canary→full·신뢰도 게이트 |
| **"전체 그래프 금지·Minimal Reasoning Subgraph"·Context 예산** | WH-1 상태 외부화(Redis 작업메모리·TTL)·LLM은 "다음 교수학 행동"만·2-Stage 흐름 |
| **Visualization Intent ≠ Rendering Implementation**(렌더러 독립·Adapter) | `visualization.py` 선언적 spec(type+spec, 픽셀 아님)·`05`/`05a` 렌더러 분리(WebView 비상구) |
| **5상태 분리**(Math/Pedagogical/Interaction/Animation/UI) | `05a` LearningScene·`learner_context`는 *스냅샷이며 판정 아님*(임의 낙인 차단) |
| **파일경로 ≠ ID**(canonical stable ID) | 개념 `code`(`{TRACK}-{AREA}-{NNN}`)·`aliases`·`source_id`(원천 추적·롤백) |
| **확증편향 방지**(시간감쇠·반박증거 우선·ε-탐색) | WH-1 증거그래프(polarity±1)·`04b` judge never-break·시간감쇠 |
| **Graph=진실 / UI=투영 / AI=소비자** | `05a` §1 동일 3분할 명시 |
| **개념 원자(Concept Atom) = 학생 사고가 바뀌는 최소 단위** | **원자 백본 마이그레이션이 사실상 이 원칙의 실행**(거시→원자 전면 교체·3단 계층·원자 1,837) |

**판독**: 플레이북이 제시한 분리·반응형·예산·렌더러 독립 원칙은 대부분 *이미 구현 좌석 또는 명세로
존재*한다. 특히 마지막 행 — 플레이북의 "노드를 어디까지 쪼갤 것인가"(개념 원자) 원칙은,
프로젝트가 2026-06-21 착수한 **원자 백본 전면 교체**(거시 개념 437 → 원자 1,837)와 방향이 완전히
일치한다. 플레이북은 이 진행을 *사후 정당화*한다.

---

## 2. 충돌 (Conflicts) — 플레이북을 그대로 따르면 안 되는 지점

| 플레이북 권장 | WhyMath 확정/원칙 | 판정 |
|---|---|---|
| **Vector DB = Pinecone** | **pgvector**(PostgreSQL 16 확장·슬98) — 메타 동거 하이브리드(단일 SQL)·6번째 store 회피·미성년 PII 통제 DB | **pgvector 유지** (대규모 시 Qdrant 이관은 별건) |
| **저장 진화 "YAML 저작 → Graph DB 런타임"**(YAML-first) | 이미 Neo4j 적재 완료 + Schema v1.0 = 구현 정본 | **단계 이미 통과** — 신규 적용 대상 아님 |
| `misconception → warning_overlay`(붉은 강조·자동 "틀렸다"·`steps:true` 즉답) | CLAUDE.md 금기(막혔을 때 즉답·부정 피드백 정서강화·거짓 "틀렸다")·답 미루기 | **`05a`가 이미 교정** — 프로브에 정답·수정 필드 *부재*(스키마 차원 차단) |
| **4계층(Minimal Core/Optional/Plugin/Experimental)을 아키텍처로** | 7계층(책임)·5블록(배포)의 *직교 두 축* | **대체 아님** — 변경빈도/안정성 기준의 *세 번째 렌즈*로만 보각 채택 가능 |
| **범용 빌드 순서**(10단계·MVP = tokenizer/Pratt parser부터) | 이미 개념그래프·오개념·L3 라우터·DSL 등 다수 단계 통과 | **신규 착수 지침으로 오독 금지** |
| **기술 스택 일반론**(ANTLR/tree-sitter·SageMath 등) | SymPy 중심·"변경하려면 MEMORY.md 결정 로그 필수" | **예시로만** — 결정 로그가 정본 |

> **충돌의 근본 원인 (명문화)**: 플레이북은 *그래프/DSL/Context 엔지니어링*에는 강하지만,
> *저작권 안전·미성년 프라이버시·PRM/도구 검증·Polya/답 미루기 교수학*(WhyMath 의사결정
> 우선순위 #1 학생 안전 · #2 법·윤리 · #3 교수학 정확성)에는 약하다. 플레이북의 자동 "틀렸다"
> 오버레이·즉답 단계 노출 예시가 그 증거다. **이 영역의 정본은 플레이북이 아니라 CLAUDE.md ·
> `05a`(답미루기·낙인 금지 불변식) · `04a`/`04b`(검증·confidence 게이트)다.** 플레이북은 위
> 우선순위에 *종속*되어야 하며, 그 역은 성립하지 않는다.

---

## 3. 공백 (Gaps) — 통합판이 새로 더한, 채택 검토 가치가 있는 원칙

> 본 절은 **분석만** 한다(코드/스키마 작업 항목으로 전환하지 않음 — 사용자 결정 범위). 각 항목은
> "플레이북 원칙 / 기존 상태 / 검토 포인트"로 기술한다.

### 3.1 노드 입도(Granularity) 판정 기준
- **플레이북**: 핵심 노드 = "학생 사고가 실제 바뀌는 최소 단위 = 오개념 발생 단위". 노드 레벨
  L1(거시)~L5(행동영역), 가장 강력한 기준은 "독립 오개념 존재". `ConceptNode 분리 판정 알고리즘`
  (풀이행동·오개념·시각화·인터랙션·prerequisite·retrieval ambiguity 6축 중 2~3개 변하면 분리).
  "기울기"(객체) vs "기울기 해석"(의미) 구분.
- **기존 상태**: 원자 백본 교체로 *입도 자체는 이미 원자 수준으로 하강 중*(L3/L4 지향). `Concept`은
  3단 계층(`level`·`parent`)으로 입도를 구조화. 그러나 "분리/병합을 무엇으로 판정하는가"의
  *명문 기준*은 데이터 파이프라인 transform 규칙에 암묵적이다.
- **검토 포인트**: 6축 분리 알고리즘을 *원자 카탈로깅의 명시 기준*으로 채택할 여지. "객체 vs
  해석" 구분(L3 vs L4 노드)이 원자 백본에 반영돼 있는지 점검(예: `cognitive_type` 활용).

### 3.2 순환참조(Circular Dependency) 방지 파이프라인
- **플레이북**: 그래프 전체를 DAG로 만들 필요는 없고 *위험한 관계만*(prerequisite/dependency) DAG
  강제. `add_edge(A,B)` 전 Reachability Check(reachable(B,A)이면 reject), SCC 야간 배치(숨은 cycle),
  단방향 canonical edge만 저장(양방향 금지). prerequisite max_depth=8.
- **기존 상태**: `ConceptEdge._no_self_edge`는 *자기 루프*만 차단한다. **그래프 수준 acyclicity
  검출은 모델 불변식으로 보장되지 않는다**(DDL/런타임 책임으로 위임). 현재 선수엣지 3,220개 적재.
- **검토 포인트**: 다중 홉 cycle(A→B→C→A)을 막는 적재 시점 Reachability Check / 주기적 SCC
  검사가 파이프라인에 있는지 확인. 교육 그래프는 본질적으로 순환적(함수↔그래프)이라 *명시
  검출 없이는 cycle 유입이 거의 확실*하다 — 검증 공백 후보.

### 3.3 Traversal / Context 예산 상수
- **플레이북**: depth(튜터링 1·심화 2·연구 3, 4+ 위험)·max_nodes 12·max_relations 20·max_tokens
  3000·노드 파일 1~4KB(10KB+ 금지)·embedding chunk 150~500 tokens. `related_to`는 *ranking
  전용·traversal 금지*. Context Compression(raw traversal를 그대로 LLM에 주지 말 것).
- **기존 상태**: WH-1(`04a`)은 상태 외부화·세션 메모리·활성 가설 최대 5 등 *방향은 동일*. 그러나
  위 **수치 예산이 한 곳에 명문화돼 있는지는 확인 필요**.
- **검토 포인트**: WH-1 / Context 설계에 max_nodes·max_tokens·depth 상수를 단일 출처로 고정할
  여지(부록 B 수치표가 좋은 출발점). `ANALOGOUS_TO` 등 약한 관계를 traversal에서 배제하는지 점검.

### 3.4 "노드에 넣지 말아야 할 10가지"
- **플레이북**: renderer·curriculum·prompt·**오개념 리스트**·UI layout·runtime state·user data·
  embedding vector 자체·traversal cache·relation expansion 결과를 노드에 넣지 말 것(전부 외부화).
- **기존 상태**: `Concept`은 renderer/prompt/curriculum/user data/embedding 벡터를 *내장하지
  않는다*(`embedding_id`는 참조일 뿐). **대부분 준수.** 단 `Concept.common_misconceptions`
  (JSONB 자유서술 리스트)는 플레이북이 가장 경계하는 "오개념 리스트 노드 내장"에 해당한다.
- **검토 포인트**: `05a`는 이미 이 긴장을 인지해 **프로브 근거로 `common_misconceptions`를 쓰지
  않고**(자유서술·카탈로그 id 아님), 활성 가설 ∩ 오개념 카탈로그에서만 프로브를 생성한다(RS2
  거짓 낙인 차단). 즉 *런타임 경로에서는 이미 우회*. 남는 질문은 노드 내 자유서술 오개념 필드의
  장기 거취(카탈로그로 일원화 vs 시드 메타로 유지)다 — 설계 논의 사항으로 기록.

### 3.5 AST 5계층(의미 엔진)
- **플레이북**: Parsing AST → Canonical Math AST(동치 정규화) → Educational Semantic(개념 연결) →
  Interaction → Visualization. "AST는 수식을 저장하는 구조가 아니라 *수학적 의미를 저장하는
  구조*". Canonical 정규화는 "교육적으로 필요한 범위까지만"(CAS 수준 normalization·undecidable 회피).
- **기존 상태**: 프로젝트 문서에서 "Semantic AST"는 `05a` 동기 서술 수준으로 *상대적 저명세*다.
  다만 `SolutionStep.sympy_verified`/`lean_verified`(v1.1)·WH-S 3Tier 검증(수치→SymPy→Lean)이
  사실상 AST 동치·검증을 *함의*한다.
- **검토 포인트**: 입력(OCR/LaTeX/키패드)→파싱→정규화→동치판정 파이프라인을 *독립 명세*로
  둘지(플레이북 Part 4의 10단계·실패 TOP10이 좋은 체크리스트). 단 "교육적 범위까지만 정규화"
  경계는 WH-S Tier3(Lean) 성숙도·기하 scope 제외(`05a` RS4)와 정렬해 *과대구현 경계*를 지킬 것.

### 3.6 Embedding namespace 분리
- **플레이북**: concept index / misconception index / example index를 *완전 분리*(공통 임베딩 =
  의미 오염). chunk 단위 임베딩(노드 전체 임베딩 금지).
- **기존 상태**: pgvector 단일 store. namespace/인덱스 분리 여부는 인프라 설정 영역(`concept.py`
  밖)이라 본 검토 범위에서 미확인.
- **검토 포인트**: 단일 pgvector 안에서도 concept/misconception/example을 *논리적 namespace
  (컬럼·테이블·필터)로 분리*하는지 점검. `04b`가 이미 "방향맹 매처" 문제(둘레↔넓이 코사인 동일)를
  실측했으므로, 오개념 임베딩 오염 위험은 *측정으로 확인된* 실재 리스크다.

### 3.7 AI 자동생성 relation 거버넌스
- **플레이북**: AI 생성 relation은 *별도 namespace + `generated_by`*, 사람 리뷰 통과 전
  prerequisite 그래프 직접 삽입 *절대 금지*(LLM은 반드시 drift 발생).
- **기존 상태**: `ConceptEdge`에 `relation_subtype`·`notes`는 있으나 `generated_by`·검토 상태
  구분 필드는 보이지 않는다. 현재 엣지는 데이터셋 기반 적재.
- **검토 포인트**: 향후 개념그래프 AI 증강 시 적용할 거버넌스(생성 출처 표시·승급 게이트). 플레이북
  Experimental→샌드박스→사람 리뷰→Core 병합 흐름과 정합. 현재는 미적용이 정당하나 *증강 착수
  전* 명문화 필요 항목으로 기록.

### 3.8 TheoremNode ≠ ProofNode / ProblemType = 인지행동 기준
- **플레이북**: TheoremNode(무엇이 참)와 ProofNode(왜 참)를 분리(정리 1 : 증명 다). ProblemType은
  표면 형태가 아니라 *cognitive action* 기준. FormulaNode는 맨 마지막에·canonical만.
- **기존 상태**: 증명 전용 노드 모델은 없다. `ProblemConcept.role`·`SolutionPath.approach_type`은
  *풀이 인지행동* 방향과 정합(ProblemType을 인지행동으로 보는 관점 일부 반영).
- **검토 포인트**: 증명 모델링 부재는 *현재 정당*하다 — 기하·증명은 `05a` RS4·WH-S Tier3(Lean)
  성숙도에 종속해 초기 scope 제외가 정직한 경계. 영재·심화(페르소나 E·v2.0) 도달 시 TheoremNode/
  ProofNode 분리를 *장기 공백*으로 기록.

---

## 4. 종합 판단

1. **플레이북 v1.0 = 방향 전환이 아니라 기존 아키텍처 베팅의 외부 검증**이다. `05a`의 선행 판정
   (표현≠의미·독립 수학 코어의 외부 검증)을 *재확인·강화*한다. 특히 "개념 원자" 입도 원칙은
   진행 중인 원자 백본 마이그레이션과 정확히 일치한다.

2. **그대로 채택하지 않는다.** 충돌 영역(Vector DB=Pinecone·자동 "틀렸다" 오버레이·즉답 단계
   노출·범용 빌드 순서)은 CLAUDE.md 의사결정 우선순위와 결정 로그(슬98 등)가 정본이다.
   플레이북은 *그래프/DSL/Context 엔지니어링*에 강하고 *법·프라이버시·교수학 안전*에 약하므로,
   후자에 **종속**되어야 한다.

3. **가치는 "그래프 위생(graph hygiene) 체크리스트"에 있다.** 통합판이 새로 더한 노드 입도 판정
   알고리즘·DAG 순환참조 방지(Reachability/SCC)·traversal·Context 예산 상수·"노드 금지 10필드"·
   AST 5계층·embedding namespace 분리·AI relation 거버넌스는, *기존 자산을 검증·경화*하는
   체크리스트로 유효하다. 그 중 **실재 검증 공백으로 가장 주목할 두 가지**는 (a) 다중 홉
   순환참조 검출 부재(§3.2)와 (b) 오개념 임베딩 오염(§3.6·`04b` 실측 뒷받침)이다.

> 본 검토는 *정합/충돌/공백 분석*까지다(사용자 결정 범위). 위 공백을 코드/스키마 작업 항목으로
> 전환하는 일(예: 적재 시점 cycle 검출, embedding namespace 분리, traversal 예산 단일 출처화,
> AST 계층 명세)은 별도 `/plan`에서 우선순위·계층 태그와 함께 다룬다.

---

## 참고
- 검토 대상 원문: 「WhyMath 구축 플레이북(통합본)」 v1.0(2026-06-29·Kiki 제공 DOCX) — *원문 본문은
  복제하지 않고 원칙 요약·구조만 인용*(CLAUDE.md 저작권 금기 준수).
- 선행 검토: `docs/architecture/05a_learning_scene_dsl.md`(동일 외부 문서 계열·수용/교정 원칙)
- 아키텍처: `docs/architecture/00_overview.md`(7계층·5블록 직교축)·`04a`·`04b`·`03b`
- 구현 좌석: `src/backend/whymath_backend/schema/concept.py`(Concept/ConceptEdge 불변식·금지필드 대조)·
  `enums.py`(EdgeType 6종)·`schema/visualization.py`·`schema/misconception_hypothesis.py`
- 스키마: `schemas/v1.0/schema_v1.0.md`·`schemas/v1.1/{solution_path,mastery_state,hint}.schema.yaml`
- 결정 로그: `MEMORY.md`(슬98 pgvector·개념그래프 적재·원자 백본 교체·오개념 839)
- 원칙: `CLAUDE.md`(의사결정 우선순위 1~7·절대 금기·표현≠의미)
- 변경 이력: v0.1 (2026-06-30 초안 — 검토만·코드/스키마 변경 0)
