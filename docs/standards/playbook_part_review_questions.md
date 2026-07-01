# 구축 플레이북 Part 0~12 순차 점검 질문 세트

> **목적**: WhyMath **구축 플레이북 v1.0**의 **Part 0 → Part 12(13개 파트)를 순서대로** 훑으며, 각 파트의 **고유 설계 법칙을 지금 구현이 지켰는가**(설계-준수)를 검문한다.
> **자매 문서**: `build_checkpoint_questions.md`(10단계 로드맵 = **진행** 축) · 이 문서(Part 0~12 = **설계 준수** 축) · `CLAUDE.md`(질문 프로토콜·불변식).

---

## 사용법

- Part 0 → 12를 **순서대로** 훑는다. 뒤 파트는 앞 파트를 전제하므로 건너뛰지 않는다.
- 각 파트 = **핵심 법칙 한 줄** → **설계-준수 검문 질문** → 끝에 **메타 질문**.
- "지금 어디까지 왔나(진행)"는 `build_checkpoint_questions.md`, "어떻게 질문하나"는 `CLAUDE.md` 질문 프로토콜 참조.
- ❌ 뜨는 항목은 `MEMORY.md` 결정 로그로 남긴다.

---

## Part 0. 왜 만드는가 — 교육철학

법칙: *기능은 7대 구조적 문제에서 역산된다. "문제은행이 아니라 사고 추적기."*

- [ ] 이 기능/모듈이 7대 문제(문제풀이기술중심 · 오개념누적 · 시각화부족 · 학습차이무시 · 풀이과정분석부재 · 개념연결부족 · 메타인지부족) 중 **무엇을 푸는지 한 문장**으로 말할 수 있나?
- [ ] "사진→답 · 문제은행"으로 회귀하지 않고 **사고 추적기**로 남아 있나?

## Part 1. 전체 그림 — 파이프라인 · 4계층 · 5대 분리

법칙: *Core를 작게 유지 + 5대 분리 + 3대 핵심.*

- [ ] 이 산출물이 파이프라인(AST → Concept → Misconception → Viz → UI DSL → AI튜터) **어느 칸**이며 앞뒤 인터페이스가 명확한가?
- [ ] **Minimal Core**(Concept Identity · Canonical AST · Semantic Type · Relation · Curriculum Mapping · Constraint)에 UI · AI · 렌더러 · 런타임 상태가 **새어들지** 않았나?
- [ ] **5대 분리**(Concept ≠ Curriculum / Renderer / Prompt / Misconception, AI ≠ 전체그래프)와 **Graph=진실 · UI=투영 · AI=소비자** 역할이 안 섞였나?
- [ ] **3대 핵심**(오개념 · 시각화 · 개인화)을 받치나, 보조기능에 시간을 쏟나?

## Part 2. 노드 설계

법칙: *노드 = 학생 사고가 바뀌는 최소 단위(= 독립 오개념 발생 단위). 우선 5노드, Formula는 마지막.*

- [ ] 노드 입도가 "함수"(너무 큼)도 "기울기의 x증가량"(폭발)도 아닌 **오개념 발생 단위**인가?
- [ ] 우선 5노드(Concept → Misconception → Skill → ProblemType → Visualization) 연결이 완성됐나? **Formula를 먼저** 만들어 실패 경로로 가지 않았나?
- [ ] ConceptNode가 identity / semantic / pedagogy / visualization … 계층으로 분리됐고, 노드에 renderer · prompt · curriculum · misconception · embedding을 넣지 않았나?

## Part 3. 관계(Edge) 설계

법칙: *Node ≠ Relation 물리적 별도 파일. AI Graph vs Runtime Graph 분리. 단방향 + weight.*

- [ ] 관계가 노드 안이 아니라 `relations/*.json` **별도 파일**인가? (limit node 15KB → 1KB 목표)
- [ ] Edge 타입 **5~8개**인가? `similar_to` / `related_to`를 traversal에 쓰나?
- [ ] **AI용 Graph**(concept + 최소 relation + misconception subset + AST)와 **Runtime Graph**(renderer · animation · layout · UI state)가 분리됐나?
- [ ] 단방향 canonical + weight 저장이며 낮은 weight는 제거되나?

## Part 4. AST — 의미 엔진

법칙: *AST 5계층 분리. Canonical 정규화는 교육적 범위만.*

- [ ] AST가 5계층(Parsing → Canonical → Educational Semantic → Interaction → Visualization)으로 분리됐나? **Parsing AST에 교육 의미**가 섞이지 않았나?
- [ ] Canonical 정규화가 교환 · 약분 등 **교육 범위로 제한**됐나, 삼각항등식 collapse / CAS급 normalization(undecidable · 성능폭발)으로 번지지 않았나?
- [ ] semantic_tags(개념 연결)를 AST **밖**에서 관리하나? **Math State ≠ UI State**가 지켜지나?
- [ ] implicit multiplication · unary minus · chained equality · 입력정규화(전각/Unicode)가 처리되나?

## Part 5. 시각화 시스템

법칙: *4분류(직접 / 동적 / 추상 / 불가). Renderer 독립. 5상태 분리.*

- [ ] 개념을 **시각화 4분류**로 판별하나, 전부 똑같이 그리려 하나?
- [ ] VisualizationNode에 Desmos / Canvas / WebGL **구현체 이름**이 없나? (Concept → Visualization Intent → Renderer Adapter)
- [ ] Math / Pedagogy / Interaction / Animation / UI **5상태 분리** + 의존 방향 Math → … → UI **단방향**인가?

## Part 6. 오개념 시스템

법칙: *Misconception Contamination 방지. 개념 ≠ 오개념 7단계 분리. 오개념 ≈ 개념의 10배.*

- [ ] 오개념이 concept node 안에 **preload되지 않았나**? (embedding 오염 · reasoning drift 방지)
- [ ] 7단계 분리(Storage/DB · retrieval · embedding index · context · runtime …)가 적용됐나?
- [ ] 오개념이 **reactive retrieval로만** 들어오나? concept / misconception 인덱스가 분리됐나?

## Part 7. Math UI DSL

법칙: *"디자인 DSL"이 아니라 "인지 인터페이스 생성 언어". 9블록. UI Planner 파이프라인.*

- [ ] DSL이 개념 → 자동 화면 **인지 인터페이스 생성 언어**로 설계됐나?
- [ ] 9블록(Scene / Concept / Visualization / Interaction / Skill / Misconception / Tutoring / Assessment / AIExplanation)이 개념 · 오개념 · 행동영역에 따라 **자동 분기**하나?
- [ ] 파이프라인(Knowledge Graph → UI Planner → DSL → Renderer → Flutter/Web)에서 Core로 UI/런타임 상태가 **역류**하지 않나?

## Part 8. Context Architecture

법칙: *"더 많이 넣을수록 더 멍청해진다." Minimal Subgraph. 6대 안정화. 2-Stage.*

- [ ] LLM에 **Minimal Reasoning Subgraph**(depth ≤ 2 · nodes ≤ 12~20 · tokens ≤ 3000)만 주나? **코드에 상한**이 박혔나?
- [ ] 6대 안정화(Tiny Node · Shallow Traversal · Lazy Relation · Hybrid Retrieval · Reactive Misconception · Chunk Embedding)가 적용됐나?
- [ ] 2-Stage Context(Intent Router → Concept Resolver → Minimal Fetch → Pass#1 → Misconception Detector → Pass#2)로 오개념이 reactive로만 로드되나?
- [ ] traversal에 visited set · timeout · token budget guard가 있나?

## Part 9. 파일 · ID 정책과 Graph DB 진화

법칙: *"파일명은 버려도 ID는 남는다." Canonical Stable ID. YAML → GraphDB. registry.*

- [ ] ID가 `math.calculus.limit` 형태로 파일명 · 언어 · 교육과정 · 렌더러와 **무관 · 불변**인가? 한글 파일명 / 커리큘럼 ID(`KR2022.math2.limit`)를 쓰지 않았나?
- [ ] 표시이름(locale)이 노드에서 분리(`locales/`)됐나? **slug를 canonical ID로** 쓰지 않나?
- [ ] YAML(저작) → Graph DB(런타임) 이전 경로가 유지되나? **Canonical ID Registry**(`ids.yaml`)로 중복 · rename · migration을 추적하나?

## Part 10. 구축 로드맵

법칙: *10단계 순서 준수. MVP → 중급 → 최종. Curriculum 역추적 분해.* (진행 상세는 `build_checkpoint_questions.md`)

- [ ] 지금 단계가 10단계 **순서를 건너뛰지** 않았나? (예: 오개념 구조화 전에 AI튜터 고도화)
- [ ] MVP 경계(입력 → tokenizer → Pratt → AST → normalize → renderer + 핵심5노드)를 지키나, 최종단계 기능(자기진화 · multimodal)을 **조기 당겨** 과욕하지 않나?
- [ ] 교육과정 문장을 그대로 노드화하지 않고 Concept / Skill / Formula / 평가 / 시각화 / 오개념 축으로 **분해**하나?

## Part 11. AI 협업 방법론 *(이미 `CLAUDE.md` 각인 — 준수 점검)*

법칙: *AI = 답변기 ❌ / 구조 붕괴 감지기 ⭕. 4종 질문축 · 질문골격 · 단계적 심화.*

- [ ] AI를 코드/UI 생성기가 아니라 **구조 비평가 · boundary 검사기 · explosion 탐지기 · schema validator**로 쓰나?
- [ ] 질문에 `[역할][목표][환경][출력][검증]`과 4축(존재이유 · 경계 · 붕괴 · 분리)이 들어갔나?
- [ ] 각 설계 끝에 "실패 이유"를 되묻고 **7분할 인지행동 출력 형식**을 강제하나?

## Part 12. 실패 방지 체크리스트

법칙: *8대 구조원칙 만족. 7대 붕괴 연쇄 감시. 하드 게이트 통과.*

- [ ] 8대 구조원칙(Concept Purity / Layer Separation / Relation Typing / Renderer Plugin / Curriculum Overlay / 오개념 독립 / AI Slimming / AST 중심)을 현 구조가 **모두** 만족하나?
- [ ] 7대 붕괴 연쇄(노드폭발 → 관계폭발 → 순환참조 → 유지보수지옥 → 성능병목 → AI추론실패 → 교육일관성붕괴) 중 지금 **어느 징후**가 보이나?
- [ ] 노드 / 관계 / AI연동 **하드 게이트**를 통과했나? (`CLAUDE.md` · `build_checkpoint_questions.md` 체크리스트)

---

## 메타 질문 (각 파트 끝 필수)

> **"이 파트의 구조가 실제 서비스에서 실패하는 이유를, 노드폭발 · 관계폭발 · 순환참조 · 유지보수 · 성능 · AI추론실패 · 교육일관성붕괴 관점에서, 표면 표현이 아니라 인지 행동(cognitive action) 기준으로 분석하라."**

---

*출처: WhyMath 구축 플레이북 v1.0 — Part 0~12 전체.*
