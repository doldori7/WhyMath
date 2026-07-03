# Part 8. Context Architecture — 준수 검토 판정 (2026-07-02, 심화 재검토 rev.2)

> `docs/standards/playbook_part_review_questions.md`의 **Part 8. Context Architecture**
> 체크리스트 4항목 + 상세 명세(6대 안정화 수치·2-Stage 흐름·8-4 규모/비용·완화 전략)를 현재
> 코드베이스에 대해 검토한 판정 리포트. 코드 변경은 없다(감사 전용).
> **rev.2 재검토**: 초판(PR #405)의 *이분법*("소비처 부재 → 전부 보류")을 더 세밀한 렌즈로
> 재실측해 **3분류**(이미 충족 / 소비처 대기)로 정정하고, 규모·비용·용어 정합 절을 추가했다.
> 관련: `docs/architecture/04c_misconception_seven_stage_separation.md`(2-Stage 오개념 계약),
> `math_dsl_retrieval_analysis.md`(retrieval 안전), `concept_node_layering_decision.md`(노드 계층), `MEMORY.md`.

법칙: *"더 많이 넣을수록 더 멍청해진다." Minimal Subgraph. 6대 안정화. 2-Stage.*

---

## 판정 요약 (rev.2 — 3분류)

초판은 "LLM subgraph 소비처가 없으니 전부 보류"라고 이분법으로 판정했다. 재실측 결과 이는
**부정확**하다 — 6대 안정화 중 일부는 *이미 충족*(때로 playbook보다 강하게)돼 있고, 나머지만
소비처 대기다.

| 분류 | 항목 | 근거(요약) |
|---|---|---|
| **① 이미 충족** | **Embedding Namespace 분리** | 3테이블 물리 분리·cross-table 코사인 금지·subject 축, `test_embedding_namespace_governance.py` 9점 동결 |
| | **Relation pruning** | playbook의 "저-weight 제거"보다 **강한** PREREQUISITE-only *type-gate*(약한 타입 미적재·`test_edge_relation_governance.py` 동결) |
| | **Reactive Misconception** | 턴별 reactive·preload 0, `04c` 7단계 분리 manifest 동결 |
| | **Tiny Node(검색 계층)** | 검색에 실제 쓰이는 *projection*(`concept_node`·`atom_node`)이 본문 슬롯 부재로 구조적 thin·`test_concept_node_purity.py` 동결 |
| **② 소비처 대기(premature)** | Minimal Subgraph token/max_nodes 예산 · 2-Stage(Pass#1/Pass#2) · Hybrid Retrieval · **Chunk Embedding**(별도 definition/intuition/example 인덱스) · Context Compression Layer · Hot Cache/prebuilt reasoning pack · Multi-Scale 재구조화 | LLM에 subgraph를 주입하는 좌석 부재 → 지금 만들면 dead code(CLAUDE.md "소비처 없는 추상 미도입") |

**체크리스트 4항목 대응**: ① Minimal Subgraph 예산 = ②(소비처 대기) · ② 6대 안정화 = **①(4/6 충족)+②(2/6 대기)** · ③ 2-Stage = 파이프라인 ②·오개념 reactive 목적은 ①충족 · ④ traversal guard = visited/depth ①·timeout/token ②.

**한 줄 판정**: Part 8의 *데이터·검색 위생*(namespace·relation·reactive·tiny node 검색계층)은 **이미
갖춰졌고 동결됐다**. 남은 것은 *LLM 컨텍스트 조립 계층*(예산·2-Stage·hybrid·chunk·compression·
cache)인데, 이는 개념 subgraph를 LLM에 주입하는 좌석이 생겨야 의미가 있어 **의도적으로 대기**한다.

---

## 항목 ① Minimal Reasoning Subgraph — "LLM에 depth ≤ 2 · nodes ≤ 12~20 · tokens ≤ 3000만 주고 코드에 상한이 박혔나?"

**판정 ❌ 미구현(의도적 보류 — ②분류).** (초판과 동일 결론)

- **소비처 부재**: `/v1/coach`는 *stateless · DB 무접근 · LLM 호출 0*(`api/coach.py:11-13`). 개념
  subgraph를 컨텍스트로 LLM에 주입하는 좌석 자체가 없어 `max_nodes`·`max_tokens`를 걸 곳이 없다.
- **코드가 명시**: `l2/prerequisite_recommendation.py:91-93` — `MAX_PREREQUISITE_DEPTH`는 *그래프
  깊이 예산*이지 *LLM 컨텍스트 예산이 아니며* 후자는 "소비처가 생긴 뒤 도입(지금 premature)"이라
  주석에 못박힘. `MEMORY.md` #357이 이를 dead/premature로 동결.
- **인접 구현**: 그래프 깊이 하드캡 `MAX_PREREQUISITE_DEPTH=5`·in-SQL `depth < max_depth`
  (`:232`)·API 공유 상한(`api/me.py` `MaxDepth`). 선수추천 좌석용이지 LLM 빌더가 아니다.

## 항목 ② 6대 안정화 — "Tiny Node · Shallow Traversal · Lazy Relation · Hybrid Retrieval · Reactive Misconception · Chunk Embedding이 적용됐나?"

**판정 △ (4/6 이미 충족 · 2/6 소비처 대기).** rev.2에서 Namespace·Relation·Tiny Node를 승격 정정.

| 안정화 | 판정 | 근거 |
|---|---|---|
| **Tiny Node** | ✅ 검색 계층 충족 | **검색에 쓰이는 것은 projection**(`concept_node`·`atom_node`)이고 이는 본문(`description`·`formal_definition`) *슬롯 부재*로 구조적 thin(Part 2 Stage A+B redaction)·`test_concept_node_purity.py` 동결. *소스* `graph.json` 원자는 ②③④ 교수학 본문을 의도적으로 보유(진실원천·Phase 3에 `atom_probe`/`misconception_catalog`/`concept_content`로 분할)하나 이는 *데이터 파일*이지 retrieval 노드가 아님(아래 §Tiny Node 주). |
| **Shallow Traversal** | △ 부분 | `prerequisite_recommendation.py` `max_depth` 기본 1·상한 5. LLM subgraph용 depth≤2 캡은 소비처 대기(①). |
| **Lazy Relation** | ❌ 소비처 대기 | edge를 재귀 CTE로 eager fetch. lazy 로딩은 subgraph 빌더가 생길 때. |
| **Hybrid Retrieval** | ❌ 소비처 대기 | `l1/concept_graph/retrieval.py::search_concepts`는 순수 벡터 top-k + 게이트(`min_similarity`·`domain`·`reviewed_only`). graph/lexical 융합 없음. |
| **Reactive Misconception** | ✅ | 턴별 reactive(`l4/misconception/diagnose.py`·`coach.py::_compute_matches`)·preload 0·`misconception_semantic_mode` 기본 off·`04c` 동결. |
| **Chunk Embedding** | ❌ 소비처 대기 | 엔티티당 fused vector 1개(`join_embedding_text` `l1/embedding_primitives.py:92`). `ConceptContent`(`db/models/concept_content.py:55-99`)에 분리 가능 필드(metaphor·misconception·formal_definition_internal·explanation) 있으나 metaphor+accepted만 임베딩·별도 인덱스/150~500토큰 sizing 없음. |

### Relation pruning — playbook보다 강함(승격 정정)

playbook 8-2 ②는 "relation에 weight 부여·낮은 weight 제거"를 요구한다. 코드는 이를 *더 강한
방식*으로 이미 달성한다:
- `edge_strength`(`db/models/concept.py:195`)는 **정렬 tie-breaker로만** 쓰이고 컷하지 않는다
  (`prerequisite_recommendation.py:249`).
- 대신 **로더가 PREREQUISITE 관계만 적재**하고 나머지를 skip한다
  (`l1/concept_graph/backend_edge.py:145-148`·`l1/atom_graph/atom_backend_edge.py:103-105`).
- `test_edge_relation_governance.py`가 이를 동결한다 — 약한 타입 전량 미적재 단언·`similar_to`/
  `related_to` 토큰 금지·관계 예산 5~8개(N² dense-graph 폭발 차단).
- 즉 "저-weight edge 제거"(여전히 잡음 edge를 그래프에 남김)보다 **type-gate**(잡음 edge를 애초
  적재 안 함)가 우월하며, weight-prune 미채택이 옳다. 초판이 이를 "❌ Lazy Relation"과 뭉뚱그린
  것은 과소평가였다.

### Tiny Node — "파일 크기"의 올바른 대상(주)

playbook 8-2 ①은 "노드 파일 1~4KB·10KB 금지"를 말한다. 이 코퍼스에는 이 문장이 *액면 그대로*
매핑되지 않는다 — 노드는 개별 파일이 아니라 단일 `graph.json`(atom 4.8MB·concept 472KB)의
배열 원소다(실측 노드 객체 크기 atom 598~2,637B·concept 445~570B, 전부 10KB 미만). 더 중요한 것은
**"파일 크기"의 진짜 의도는 retrieval precision·임베딩 오염 방지**라는 점이다. 따라서 이 불변식의
올바른 대상은 *검색에 주입되는 노드*(projection `concept_node`/`atom_node`)이고, 그것은 이미:
- 본문 슬롯이 **구조적으로 부재**(Part 2 순수성 Stage A+B로 `description`·`formal_definition`·
  `metaphor`·`accepted_expressions` 노드에서 제거·이관),
- `test_concept_node_purity.py`가 field 이름을 동결(pedagogy 금칙·본문 재유입 차단).

*소스* `graph.json` 원자가 ②③④ 본문을 보유하는 것은 설계다(진실원천 → Phase 3 분할). 소스에
바이트 게이트를 걸면 *정당하게 rich한 소스 원자*를 오탐하고, projection에 걸면 위 구조적 보증과
*중복*이다. ∴ **별도 바이트 게이트는 불필요**하며 Tiny Node는 검색 계층에서 이미 충족이다.
(단, 향후 projection에 본문성 필드가 늘면 바이트 예산 게이트를 검색 계층에 추가하는 것은 열려 있다.)

## 항목 ③ 2-Stage Context — "Intent Router → … → Pass#2로 오개념이 reactive로만 로드되나?"

**판정 △ 파이프라인 미구현(②) · 오개념 reactive 목적은 이미 충족(①).** (초판과 동일)

- 6단계 오케스트레이터 없음: `l3/router.py`=비용-티어(intent 아님)·`l3/pipeline.py::generate()`=
  단일 패스(이미 조립된 prompt 수신·Pass#1/Pass#2 없음)·`api/coach.py`=reactive 매칭이나 LLM 미호출.
- 그러나 2-Stage의 *핵심 목적*("오개념 preload 금지·탐지 후 reactive")은
  `04c_misconception_seven_stage_separation.md:84,100-101`에서 정본·동결. 오염 방지는 파이프라인
  없이도 달성.

## 항목 ④ traversal guard — "visited set · timeout · token budget guard가 있나?"

**판정 △ 부분.** (초판과 동일)

- visited set ✅(`prerequisite_recommendation.py:257-262` `seen`)·in-SQL depth bound ✅(`:232`).
- timeout ❌·token budget guard ❌ — LLM subgraph 소비처가 없어 token 예산 개념 자체가 미존재(②).

---

## §규모·비용 — "고등수학 전체를 넣으면"(8-4 편입)

이 절은 *구현이 아니라 분석 프레이밍*이다 — 트리거 슬라이스에서 예산·guard가 왜 **필수**인지의
정량 근거를 남긴다.

- **먼저 죽는 것은 모델이 아니라 Context Orchestration.** Transformer attention은 `O(n²)`이라
  4K→16K tokens면 ~16배. 긴 context는 attention dilution·irrelevant retrieval·misconception
  contamination·latency·hallucination을 부른다. 병목 순서: **① AI Context Orchestration → ②
  Graph Traversal → ③ Embedding Reranking → ④ Curriculum Synchronization.**
- **관계가 노드보다 먼저 폭발한다.** 규모 추정(고등 전체): 개념 400~1,200 · 오개념 3천~1.5만 ·
  문제유형 2천~1만 · 전체 파일 5천~3만 · **관계 2만~20만(`O(N log N)~O(N²)`)** · embedding chunk
  5만~50만. 시스템은 파일 개수가 아니라 **traversal**로 죽는다.
- **∴ 예산·guard는 협상 불가.** 트리거 시 `max_nodes=12·max_relations=20·max_tokens=3000`
  하드캡, `depth ≤ 2` bounded traversal, token budget guard, embedding namespace 분리(이미 있음),
  misconception delayed retrieval(이미 있음)가 *동시에* 들어가야 한다. 이것이 §트리거 계약이다.

## §용어 정합 — Multi-Scale Graph

playbook 완화 전략의 "Multi-Scale Graph(Macro 개념 / Teaching / Misconception 3계층 분리)"는
**코드의 "3계층"과 다른 축**이다:
- 코드의 "3계층" = `ConceptLevel` **단원 > 소단원 > 세부개념**(입도 ladder, `schema/enums.py:538`).
- playbook의 Multi-Scale = **macro / teaching / misconception 스케일**(retrieval 계층 분리).

물리 분리(concept / atom / misconception 테이블·임베딩)는 존재하나 축이 입도(concept↔atom 이중
truth source)와 misconception catalog이지 macro/teaching/misconception 스케일이 아니다. Multi-Scale
재구조화는 소비처 대기(②)이며, 도입 시 위 용어 충돌을 먼저 정리해야 한다.

---

## 왜 지금(②를) 안 짓는가 (근거 체인)

1. ②의 예산·2-Stage·hybrid·chunk·compression·cache는 전부 **"LLM에 개념 subgraph를 주입하는
   좌석"**을 전제한다.
2. 그 좌석은 오늘 없다(`/v1/coach` LLM 0·`l3/pipeline.py` 단일 패스로 이미 조립된 프롬프트만 수신).
3. 소비처 없이 만들면 **dead code** — CLAUDE.md 절대금기("소비처 없는 추상 미도입", `MEMORY.md`
   #357·#389)의 정면 위반. 특히 Chunk Embedding은 재임베딩 비용까지 발생(별도 인덱스를 질의하는
   consumer 없이는 순손실).
4. ∴ ②의 의도적 보류가 준수다. ①(namespace·relation·reactive·tiny-node 검색계층)은 이미 충족·동결.

## 해제 트리거 계약 — "언제·어떤 모양으로 ②를 도입하나"

**트리거**: 첫 *LLM에 concept subgraph를 주입하는 좌석*(WH-1 튜터링 루프 실배선 `harness/wh1_loop.py`,
앵커 `04c:84,100` 단계4 "Context (LLM)")이 착륙하는 **바로 그 슬라이스**에서 ②를 함께 도입한다.

**도입 시 계약**(구현 아님):
- **하드캡 단일 출처 상수**(매직넘버 금지·`MAX_PREREQUISITE_DEPTH` 선례): `depth ≤ 2`·
  `max_nodes ≤ 12~20`·`max_relations ≤ 20`·`max_tokens ≤ 3000`, *context builder 코드에 실제로 박기*.
- **재사용 좌석**: traversal=`prerequisite_recommendation.py` 재귀 CTE(visited set 재사용)·검색=
  `search_concepts`(게이트 재사용)·redaction=`concept_node`(본문 부재 유지)·namespace=기존 3인덱스.
- **guard**: visited set(재사용) + 신규 wall-clock timeout + 신규 token budget guard(직렬화 직전 컷).
- **6대 안정화 잔여 동반**: Hybrid Retrieval(벡터+graph+rule) · Chunk Embedding(`limit.definition`/
  `intuition`/`example` 150~500토큰 분리·concept/misconception/example 인덱스 분리·재임베딩 1회) ·
  Lazy Relation.
- **2-Stage 골격**: Pass#1(개념 subgraph) → Misconception Detector → Pass#2(reactive), `04c` 오개념
  preload 금지 유지.
- **규모 완화**: Context Compression Layer(중간 summarizer)·Hot Cache(자주 쓰는 subgraph를 prebuilt
  reasoning pack으로)·Multi-Scale 분리(위 §용어 정합 선결).
- **동결 테스트**: `test_embedding_namespace_governance.py` 패턴 미러로 상한 상수·guard 존재를
  컴파일 단언 동결(DB 불필요).

---

## 잔여 리스크 · 후속

- **최우선**: 트리거 좌석(LLM 튜터링 Pass#1)이 없으면 ②는 계속 대기다 — 결함이 아니라 소비처
  대기다. `build_checkpoint_questions.md`의 stage 8 🔴는 *구현 실패*가 아니라 *구현 시 예산·guard를
  반드시 함께 넣으라*는 경고로 읽는다(§규모·비용이 그 정량 근거).
- **이미 갖춘 자산**: 개념/edge ORM + offline DAG 검증 · 선수 깊이 하드캡 + visited set · 벡터
  검색 + 안전 게이트 · reactive 오개념(7단계 동결) · **임베딩 namespace freeze** · **relation
  type-gate freeze** · **node purity freeze**. 트리거 시 이들을 *조립*하면 되고 바닥부터 짜지 않는다.
- **범위 밖(이 검토가 하지 않은 것)**: ②의 어떤 것도 구현하지 않음(트리거 이연) · Tiny Node 바이트
  게이트 신설(검색 계층이 이미 구조적 충족이라 불필요·소스 게이트는 오탐) · 코드/테스트/스키마/
  마이그레이션 변경.
