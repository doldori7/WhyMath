# 구축 플레이북 Part 12(실패 방지 체크리스트) 설계-준수 검토

> **상태**: 검토(review) · **계층**: 횡단(메타 · 거버넌스 · 프로세스 불변식) · **작성일**: 2026-07-03
> **검토 대상**: `docs/standards/playbook_part_review_questions.md:120-126` **Part 12 — 실패 방지 체크리스트**
> (법칙: *8대 구조원칙 만족 · 7대 붕괴 연쇄 감시 · 하드 게이트 통과*)
> **정본(단일 진실원)**: `CLAUDE.md:167-212`("🧱 구축 플레이북 불변식 & AI 질문 프로토콜" · §8대 구조 원칙 ·
> §7대 붕괴 연쇄 · §작업 전/후 하드 게이트) ·
> **교차점검**: `docs/standards/build_checkpoint_questions.md`(진행 축 10단계 + 하드 게이트) ·
> **선행 Part 검토**: `part2_node_design_review.md` · `edge_design_part3_review.md` · `math_dsl_part4_ast_review.md` ·
> `04c_misconception_seven_stage_separation.md` · `part8_context_architecture_review.md` ·
> **자매 검토(방식 정본)**: `ai_collaboration_part11_review.md`(감사+동결 방식을 그대로 이어받음)

---

## 0. 요지 (BLUF)

Part 12의 3개 검문(8대 구조원칙 · 7대 붕괴 연쇄 · 하드 게이트)은 **이미 준수**한다. **Part 11과 같은 이유로
닫을 코드 갭이 없다** — Part 12는 새 규범이 아니라 *다른 파트(2·3·4·6·8)가 이미 세운 방어들을 하나의
체크리스트로 요약*한 것이고, 그 방어 하나하나는 이미 거버넌스 테스트·스키마·검증기로 물화(物化)돼 있다.

**따라서 이 검토의 산출물은 "구현"이 아니라 "감사 + 드리프트 동결"이다** (`ai_collaboration_part11_review.md:20`과
동일 방침). Part 12를 독립 스펙 문서로 *재정의*하면 진실원이 둘(`CLAUDE.md` + 신규 문서)이 되어 12-1 #4
**유지보수 지옥**(truth source가 하나가 아님)을 스스로 유발한다 — 즉 Part 12를 재정의하는 행위 자체가 Part 12
위반이다. 그래서 본 문서는 *감사만* 하고 `CLAUDE.md:167-212`를 유일 정본으로 가리킨다. 진짜 리스크는 코드
부재가 아니라 *드리프트* — 정본 문자열이나 근거 테스트가 조용히 사라지면 이 체크리스트가 근거를 잃는다. 그
연결 무결성을 hermetic manifest(`tests/backend/test_failure_prevention_manifest.py`)로 동결한다.

> **핵심 구분 — 강제 불변식 vs 예시적 표현 (category error 방어)**:
> Part 12 체크리스트의 문장 중 일부는 *강제되는 불변식*이고, 일부는 그 불변식의 *예시적 표현*(작성 당시
> 저장 구조를 전제한 삽화)이다. 감사자가 예시적 표현을 강제 대상으로 오인하면 false positive가 난다. 아래
> §1.x에 이 구분을 명시한다(ID 형식 · "노드 파일 KB" · depth 수치). **무엇이 진짜 엄격한가**를 판정하는 것이
> 이 검토의 핵심이며, 그 자체가 Part 11 검문 ①(boundary 검사) · 검문 ②(경계)의 실천이다.

---

## 1. 3개 검문 판정

### ① 8대 구조원칙(12-2)을 현 구조가 모두 만족하나 — **정합(원칙별 거버넌스로 물화)**

정본: `CLAUDE.md:167-176`. 각 원칙 → 이를 *실행 가능한 방어*로 물화한 아티팩트:

| # | 원칙 | 물화 아티팩트(근거) | 판정 |
|---|---|---|---|
| 1 | **Concept Purity** | `tests/data_pipeline/concept_graph/test_concept_node_purity.py`(노드에 renderer/prompt/curriculum/misconception/embedding 부재) · `concept_graph.md`§2.2c · `part2_node_design_review.md:51-68` | 강 정합 |
| 2 | **Layer Separation** | 7계층 import-linter 계약 CI 강제(`build_checkpoint_questions.md:45,75`·`playbook_part_review_questions.md:69`) · `tests/backend/l1/test_no_import_cycle.py` · `tests/backend/schema/test_visualization_state_separation.py`(Math→…→UI 단방향) | 정합 |
| 3 | **Relation Typing 최소화(5~8)** | `schemas/v1.1/edge.schema.yaml`(관계 7종) · `tests/data_pipeline/concept_graph/test_relation_vocabulary_governance.py`(예산 5~8 + `similar_to`/`related_to` 금칙) | 정합 |
| 4 | **Renderer는 Plugin** | `docs/architecture/05b_visualization_classification.md`(Concept→Visualization Intent→Adapter) · `data/render_contract.json` · `tests/backend/schema/test_render_contract.py` · `test_visualization_state_separation.py`(Intent≠구현체) | 정합 |
| 5 | **Curriculum은 Overlay** | `schemas/v1.1/curriculum_entry.schema.yaml`(개념 영속·매핑만 교체) · `drop_concept_subject_curriculum_version` 선례(`part2_node_design_review.md:57`) | 정합 |
| 6 | **오개념은 독립 DB(Reactive)** | `docs/architecture/04c_misconception_seven_stage_separation.md` · MisconceptionCatalog 별도 저장 · preload 금지 하드게이트(`CLAUDE.md:210`) | 정합 |
| 7 | **AI Context Slimming(subgraph depth≤2, nodes 12~20)** | `CLAUDE.md:209` · `docs/architecture/math_dsl_principles_review.md:115-122`(depth·max_nodes·max_tokens 예산) | 정합(§1.x-d 관찰) |
| 8 | **AST 중심** | `math_dsl_*` 시리즈(원칙·evolution·part4 AST 검토·risk register) | 정합 |

### ② 7대 붕괴 연쇄(12-1) 중 어느 징후가 보이나 — **정합(연쇄 전 구간 방어 실재; 인지행동 분석은 §2)**

정본: `CLAUDE.md:177-185`. 연쇄 `노드폭발 → 관계폭발 → 순환참조 → 유지보수지옥 → 성능병목 → AI추론실패 →
교육일관성붕괴`의 각 마디에 대응 방어가 실재한다:

- **노드폭발** ← `tests/backend/l1/test_five_node_connectivity_governance.py`(SkillNode/FormulaNode/ProblemTypeNode
  부재 동결 — "모든 것을 노드화" 차단).
- **관계폭발** ← `test_relation_vocabulary_governance.py`(예산 5~8 · `similar_to`/`related_to` 금칙) ·
  `test_edge_relation_governance.py`(traversal에 `prerequisite`만 적재 → N² dense화 차단).
- **순환참조** ← `src/data-pipeline/data_pipeline/concept_graph/validate.py`의 `prerequisite_cycle`을 **error**로
  강제(DAG 보장) · `tests/backend/l1/test_no_import_cycle.py`.
- **유지보수지옥** ← 단일 진실원 규율 — 본 검토가 재정의 대신 `CLAUDE.md`를 가리키는 것 자체가 방어(§0).
- **성능병목** ← budget guard: subgraph `depth≤2`(`CLAUDE.md:209`) · `MAX_PREREQUISITE_DEPTH=5`
  (동결 `tests/backend/l2/test_prerequisite_depth_budget.py`) · token cap.
- **AI추론실패** ← Minimal Reasoning Subgraph(`math_dsl_principles_review.md:115-122`) + embedding namespace
  경계(`test_embedding_namespace_governance.py`).
- **교육일관성붕괴** ← 위 6개의 최종 귀결. 상류 방어가 서면 자동 차단.

> 현 시점 **명백한 붕괴 징후는 관찰되지 않음.** 잠재 압력 2곳은 이미 열린 질문으로 추적 중(§1.x-c/d):
> 단일 `graph.json`의 retrieval precision(성능병목 상류) · subgraph 예산 수치의 중앙 명문화(AI추론실패 상류).

### ③ 노드/관계/AI연동 하드 게이트(12-3)를 통과하나 — **정합(게이트별 근거 테스트 매핑)**

정본: `CLAUDE.md:195-212`.

- **노드 추가 게이트**(`:196-200`): "개념 자체 vs 실행정보" 외부화 · 파일 소형 · renderer/curriculum/prompt/
  misconception/UI/embedding 미혼입 · ID 독립. → `test_concept_node_purity.py` + ID 형식 강제
  `schemas/v1.1/concept.schema.yaml:42`(regex) + `validate.py`(id 형식·dangling·isolated).
- **관계 추가 게이트**(`:202-206`): weak 관계 제거 · `prerequisite` DAG(Reachability) · `related_to`/`similar_to`
  traversal 금지 · 단방향 canonical. → `test_edge_relation_governance.py`(prerequisite만 적재) ·
  `test_relation_vocabulary_governance.py`(금칙) · `validate.py`의 `prerequisite_cycle` error.
- **AI 연동 게이트**(`:208-212`): subgraph(depth≤2, nodes 12~20) · 오개념 reactive(preload 금지) · embedding
  물리·논리 분리(cross-table 코사인 금지) · visited set·timeout·token budget guard. →
  `test_embedding_namespace_governance.py`(namespace = table × subject) · `test_prerequisite_depth_budget.py` ·
  `math_dsl_principles_review.md:115-122`(budget).

## 1.x 수용된 경계 / 관찰 (부채 아님 — Part 11 §1.x 방식 계승)

- **(a) 독립 정본 스펙 문서 미신설 — 의도**: Part 12 정의는 `CLAUDE.md:167-212`에 이미 완전하다. 재정의는
  이중 진실원 → 유지보수 지옥(12-1 #4)을 자초하므로, 본 문서는 *감사*만 하고 재정의하지 않는다. **이 판정
  자체가 검문 ①·④(무엇을 독립 문서로 분리하지 *않을지*)의 실천**이다(`ai_collaboration_part11_review.md:89-92`와 동형).

- **(b) ID 형식 — 강제 불변식 vs 예시적 표현**: 하드게이트(`CLAUDE.md:200`)는 ID 예시로 점표기
  `math.calculus.limit`을 든다. 그러나 **강제되는 불변식은 "ID가 파일명·언어·교육과정과 독립·불변"**이며,
  이는 `concept.schema.yaml:42` regex `^(ELEM|MID|HIGH|RT|OLY)-[A-Z0-9]{2,8}-\d{3}$`(예 `HIGH-CALC-042`)와
  `validate.py`로 강제된다(2026-06-16 P2a 전환, 옛 `UC.*` 점표기는 `aliases`로만 보존). 즉 `math.calculus.limit`은
  *원칙의 예시적 표현*일 뿐 강제 대상이 아니며, 실제 canonical 표기와 다르다. **드리프트가 아니라 삽화**로
  분류하되, 혼선을 줄이려면 정본 예시를 현 표기로 새로고침하는 것이 바람직 — *후속 슬라이스*(정본 편집이라
  MEMORY.md 결정 로그 동반, 본 검토 범위 밖).

- **(c) "노드 파일 1~4KB" — 저장-시대 가정의 예시적 표현**: 하드게이트(`CLAUDE.md:198`)는 노드를 개별 파일
  1~4KB로 가정하나, 실제 저장은 개별 파일이 아니라 `graph.json` 단일 집합 파일 + Neo4j
  (`concept_graph.md:19,199`). **강제 불변식은 "노드 payload가 retrieval dilution을 일으킬 만큼 크지 않을 것"**
  이며, 실제 방어는 파일 크기가 아니라 필드 단위 chunk + purity 테스트다(`edge_design_part3_review.md:31`은
  현 노드가 소형이라 문제없다고 판정). 단, *단일 대용량 `graph.json`이 retrieval precision을 떨어뜨리는지*의
  chunk 분리 검문은 열린 질문으로 남아 있다(`build_checkpoint_questions.md:52`). 관찰로 기록.

- **(d) subgraph 예산 수치의 중앙 명문화 + prerequisite depth 8 vs 5**: 하드게이트는 subgraph `depth≤2`
  (`CLAUDE.md:209`, 정본으로 정확)를 요구하나, `math_dsl_principles_review.md:119-122`는 "이 수치 예산이 한
  곳에 명문화됐는지 확인 필요"라 열어둔다. 별개로 **prerequisite 추천 depth**는 binding 상수가 코드
  `MAX_PREREQUISITE_DEPTH=5`(동결 `test_prerequisite_depth_budget.py`)인데, 이차 검토문서
  `math_dsl_principles_review.md:108,116`은 `max_depth=8`로 적어 stale하다. 두 개념(traversal subgraph
  `depth≤2` vs prerequisite 추천 depth)은 별개이며 **정본(`CLAUDE.md`)은 정확**하다 — 정정 대상은 비정본
  review 문서의 "8"이다(후속, 본 검토 범위 밖).

- **(e) 다중 노드 taxonomy는 채택된 로드맵 방향과 일치**: Part 12가 전제하는 Skill/Formula/ProblemType/Proof
  구분은 `docs/architecture/concept_node_layering_decision.md`(2026-07-03 ADR)로 채택됐고, 현재는 의도적으로
  미구현·동결 상태(`test_five_node_connectivity_governance.py`). 이는 노드폭발 차단(Phase 순차 도입)이며 위반
  아님.

- **소스 0 · 스키마 0 · 마이그레이션 0.**

---

## 2. 메타 질문 — 7대 붕괴 연쇄 관점 인지행동 분석

> *"이 파트의 구조가 실제 서비스에서 실패하는 이유를, 노드폭발 · 관계폭발 · 순환참조 · 유지보수 · 성능 ·
> AI추론실패 · 교육일관성붕괴 관점에서, 표면 표현이 아니라 인지 행동(cognitive action) 기준으로 분석하라."*
> (`playbook_part_review_questions.md:130-132` 강제)

Part 11 §2가 *"AI에게 무엇을·어떻게 묻는가"*(질문하는 인지 행동)의 이완을 다뤘다면, Part 12의 실패는
**"게이트 앞에서 무엇을 스스로 되묻는가"(통과 규율의 인지 행동)**의 이완에서 시작한다. 체크리스트는
문서가 아니라 *습관*으로 존재해야 하며, 그 습관이 풀리는 지점이 곧 붕괴의 진입로다.

- **노드폭발(첫 마디)**: 설계자가 노드 추가 게이트(`:196-200`)를 "형식적으로 체크"만 하고 *"이 데이터가
  개념 자체인가, 투영/실행 정보인가"*를 실제로 되묻지 않으면, "일단 노드로" 습관이 재발한다. 인지 행동의
  게으름이 곧 노드 수 폭증으로 전이된다. `test_five_node_connectivity_governance.py`·purity 테스트는 이
  게으름을 red로 붙잡는 *기계화된 되묻기*다.
- **관계폭발**: 관계 게이트(`:202-204`)의 *"이 관계가 없으면 AI 튜터링에서 실제 어떤 오류가 나는가"*를
  묻지 않으면, 편해 보이는 `related_to`/`similar_to`가 traversal로 새어들어 N²로 팽창한다. 방어의 본질은
  스키마가 아니라 *"근거를 대지 못하는 관계는 제거"*라는 인지 규율이며, `test_relation_vocabulary_governance.py`가
  그 규율의 마지막 성벽이다.
- **순환참조**: *"이 prerequisite이 DAG를 깨지 않는가(Reachability)"*를 되묻는 습관이 풀리면, 교육 그래프의
  본질적 순환이 그대로 적재된다. `validate.py`의 `prerequisite_cycle` error가 최후 방어선이나, 그 이전에
  게이트에서의 자문이 상류 차단이다.
- **유지보수지옥**: 가장 은밀한 인지 오류 — *"이걸 새 문서로 정리하면 깔끔하겠다"*는 정돈 욕구가 이중
  진실원을 만든다. 본 검토가 §0·§1.x-a에서 *재정의를 거부*한 것이 바로 이 인지 함정을 끊은 것이다. Part 12를
  지키는 최선의 방법은 "Part 12 문서를 더 만들지 않는 것"이라는 역설이 여기서 나온다.
- **성능병목**: AI 연동 게이트(`:208-212`)의 budget guard(depth·token)를 *"이번엔 예외로 크게"* 넘기는 순간
  context traversal이 폭증한다. `MAX_PREREQUISITE_DEPTH=5` 동결은 개별 판단의 이완을 시스템이 흡수하게 한 것.
- **AI추론실패**: 위 게이트 이완의 종착 직전 — 그래프가 커지고(노드/관계 폭발) 예산이 풀리면(성능) attention
  dilution으로 *그럴듯한 잘못된 튜터링*이 나온다. Minimal Reasoning Subgraph가 방어이나, 그 전제는 게이트
  습관의 유지다.
- **교육일관성붕괴(최종 귀결)**: 위 전부의 종착. Part 12는 *체크리스트라는 인지 습관*을 통해 나머지 6개를
  상류에서 차단하는 메타-파트다. 그래서 이 파트의 방어는 새 코드가 아니라 **정본·근거 테스트의 실재와
  체크리스트↔근거의 연결 무결성**을 지키는 것이다.

**드리프트 실패 시나리오(이 manifest가 막는 것)**: 누군가 `CLAUDE.md`에서 8대 원칙·7대 붕괴·하드게이트
블록을 지우거나, 원칙을 떠받치는 거버넌스 테스트를 삭제하면 — 체크리스트는 그대로 "통과"라 말하지만
근거가 증발한다(침묵 실패). manifest가 red로 이를 강제 노출한다.

---

## 3. 결론

1. **Part 12 ①②③ 준수** — 코드 갭 없음. 8대 원칙은 원칙별 거버넌스 테스트·스키마·검증기로 물화, 7대 붕괴는
   연쇄 전 구간에 대응 방어 실재, 하드게이트는 게이트별 근거 테스트로 매핑된다.
2. **감사 + 동결** — 재정의(이중 진실원) 대신 hermetic manifest(`tests/backend/test_failure_prevention_manifest.py`)로
   (i) 정본 정의(8원칙·7붕괴·하드게이트) 문자열의 온전성, (ii) 각 원칙·게이트 근거 아티팩트의 실재, (iii) 본
   검토 문서의 정본-참조(재정의 아님)를 드리프트로부터 동결. Part 11 manifest와 단언 *중복 없이* 상보.
3. **경계 지킴** — 강제 불변식 vs 예시적 표현 구분(§1.x-b/c/d): ID 점표기·"노드 파일 KB"·depth "8"은 예시/
   비정본이며 강제 대상 아님. 정본(`CLAUDE.md`)은 정확하다.
4. **후속(범위 밖)**: (i) 정본 ID 예시를 `HIGH-CALC-042` 계열로 새로고침, (ii) `math_dsl_principles_review.md`의
   prerequisite depth "8"→"5" 정정, (iii) subgraph 예산 수치의 중앙 명문화, (iv) 단일 `graph.json` chunk 분리
   검토 — 모두 정본/소스 편집 동반이라 별도 슬라이스(MEMORY.md 결정 로그 필요). 본 검토는 소스/스키마/
   마이그레이션 변경 0.

---

## 참고
- 정본: `CLAUDE.md:167-212`(8대 구조 원칙 · 7대 붕괴 연쇄 · 작업 전/후 하드 게이트)
- 질문지: `docs/standards/playbook_part_review_questions.md:120-126`(Part 12)·`:130-132`(메타 질문) ·
  `docs/standards/build_checkpoint_questions.md`(진행 축 + 하드 게이트)
- 근거 테스트/검증기: `tests/data_pipeline/concept_graph/test_concept_node_purity.py` ·
  `.../test_relation_vocabulary_governance.py` · `tests/backend/l1/test_edge_relation_governance.py` ·
  `.../test_five_node_connectivity_governance.py` · `.../test_embedding_namespace_governance.py` ·
  `.../test_no_import_cycle.py` · `tests/backend/l2/test_prerequisite_depth_budget.py` ·
  `tests/backend/schema/test_render_contract.py` · `.../test_visualization_state_separation.py` ·
  `src/data-pipeline/data_pipeline/concept_graph/validate.py`
- 스키마: `schemas/v1.1/concept.schema.yaml`(id regex `:42`) · `schemas/v1.1/edge.schema.yaml` ·
  `schemas/v1.1/curriculum_entry.schema.yaml`
- 동결 테스트: `tests/backend/test_failure_prevention_manifest.py`(본 검토의 대응 manifest)
- 선행/자매: `ai_collaboration_part11_review.md`(감사+동결 방식 정본) · `part2_node_design_review.md` ·
  `edge_design_part3_review.md` · `math_dsl_part4_ast_review.md` · `04c_misconception_seven_stage_separation.md` ·
  `part8_context_architecture_review.md`
- 변경 이력: v0.1 (2026-07-03 — Part 12 실패 방지 체크리스트 감사 + 드리프트 동결)
