# Part 8. Context Architecture — 준수 검토 판정 (2026-07-02)

> `docs/standards/playbook_part_review_questions.md`의 **Part 8. Context Architecture**
> 체크리스트 4항목을 현재 코드베이스에 대해 검토한 판정 리포트. 코드 변경은 없다(감사 전용).
> 관련 문서: 2-Stage 오개념 계약은 `docs/architecture/04c_misconception_seven_stage_separation.md`,
> retrieval 안전은 `docs/architecture/math_dsl_retrieval_analysis.md`, 결정 로그는 `MEMORY.md`.

법칙: *"더 많이 넣을수록 더 멍청해진다." Minimal Subgraph. 6대 안정화. 2-Stage.*

---

## 판정 요약

| 항목 | 판정 | 근거·조치 |
|---|---|---|
| ① Minimal Reasoning Subgraph 예산 + **코드 상한** | **❌ 미구현(의도적 보류)** | LLM에 subgraph를 주입하는 *소비처 부재* → premature. 인접 *그래프-깊이* 캡만 존재 |
| ② 6대 안정화 | **△ 부분(대략 2.5/6)** | Reactive Misconception ✅ · Tiny Node/Shallow Traversal 부분 · Lazy Relation/Hybrid Retrieval/Chunk Embedding ❌ |
| ③ 2-Stage Context(오개념 reactive) | **△ 파이프라인 미구현·목적은 별경로 충족** | Pass#1→detector→Pass#2 오케스트레이터 없음. 단 "오개념 preload 금지"는 이미 강제됨 |
| ④ traversal guard(visited·timeout·token budget) | **△ 부분** | visited set ✅ · in-SQL depth bound ✅ · timeout·token budget guard ❌(소비처 없음) |

**한 줄 판정**: Part 8의 *LLM 컨텍스트 예산 계층*(subgraph budget·2-Stage·token guard)은 **아직 구축되지
않았고, 그것이 정상이다** — 개념 subgraph를 LLM에 주입하는 좌석이 오늘 존재하지 않으므로
("소비처 없는 추상 미도입", CLAUDE.md 절대 금기). 지금 만들면 dead code다. 대신 *해제 트리거 계약*을
아래 §트리거에 못박아, 첫 소비처 슬라이스가 착륙하는 순간 예산 계층이 함께 태어나도록 한다.

---

## 항목 ① Minimal Reasoning Subgraph — "LLM에 depth ≤ 2 · nodes ≤ 12~20 · tokens ≤ 3000만 주고 코드에 상한이 박혔나?"

**판정 ❌ 미구현(의도적 보류).**

- **소비처 부재가 근본 사실**: `/v1/coach`는 *stateless · DB 무접근 · **LLM 호출 0***이다
  (`api/coach.py:11-13`). 즉 개념 subgraph를 컨텍스트로 **LLM에 주입하는 좌석 자체가 없다**.
  주입 대상이 없으니 `max_nodes`·`max_tokens` 예산도 걸 곳이 없다.
- **코드가 직접 이를 명시**: `l2/prerequisite_recommendation.py:91-93` —
  `MAX_PREREQUISITE_DEPTH`는 *그래프 traversal 깊이 예산*이지 *"LLM 컨텍스트 예산(max_nodes·
  max_tokens)이 아니다"*, 후자는 "LLM에 subgraph를 주입하는 소비처가 생긴 뒤에 별도로 도입한다
  (지금 미존재·premature)"라고 주석에 못박혀 있다.
- **결정 로그**: `MEMORY.md`(2026-06-30·PR #357, "MATH DSL invariant 코드 게이트 동결")는 LLM subgraph
  context 예산을 **"의도적 미채택(premature/dead) — 소비처/경로 부재라 dead"**로 동결했다. Part 6
  검토(`04c`) 결정 로그의 "NOT(범위 밖)"도 동일하게 "subgraph token/max_nodes budget guard(소비처
  미존재·premature)"를 명시한 바 있다.
- **인접 구현(있는 것)**: *그래프* 깊이 예산은 하드캡으로 존재한다 —
  `MAX_PREREQUISITE_DEPTH = 5`(단일 출처 상수), 재귀 CTE에서 in-SQL `base.c.depth < max_depth`로
  bound(`prerequisite_recommendation.py:232`), API 경계 `api/me.py`(`MaxDepth` Annotated·기본 1·
  `le=MAX_PREREQUISITE_DEPTH`)가 같은 상수를 공유(매직넘버 중복 제거). 이것은 *선수개념 추천*
  좌석용이지 LLM 컨텍스트 빌더가 아니다.

## 항목 ② 6대 안정화 — "Tiny Node · Shallow Traversal · Lazy Relation · Hybrid Retrieval · Reactive Misconception · Chunk Embedding이 적용됐나?"

**판정 △ 부분(대략 2.5/6).** 항목별:

| 안정화 | 판정 | 근거 |
|---|---|---|
| **Tiny Node** | △ 설계상 부분 충족 | `concept_node`는 본문(`description`·`formal_definition`) redact된 얇은 projection(`db/models/concept_node.py`)·Part 2 순수성 수정으로 pedagogy 필드도 이관됨. 단 "Tiny Node"로 명명·게이트된 모듈은 없음 |
| **Shallow Traversal** | △ 부분 | `prerequisite_recommendation.py` `max_depth` 기본 1·상한 5. LLM subgraph용 depth≤2 캡은 없음(①) |
| **Lazy Relation** | ❌ | edge를 재귀 CTE로 eager fetch. lazy relation 로딩 메커니즘 없음 |
| **Hybrid Retrieval** | ❌ | `l1/concept_graph/retrieval.py::search_concepts`는 **순수 벡터 top-k**(pgvector 코사인) + 게이트(`min_similarity`·`domain`·`reviewed_only`). graph/lexical 융합(하이브리드) 없음 |
| **Reactive Misconception** | ✅ | 턴별 reactive 진단(`l4/misconception/diagnose.py`·`api/coach.py::_compute_matches`), 초기 context preload 경로 0. `misconception_semantic_mode` 기본 `off`. `04c` 7단계 분리로 동결 |
| **Chunk Embedding** | ❌ | 엔티티당 벡터 1개(`l1/concept_graph/embedding.py`·`atom_graph/embedding.py`). 플레이북 `limit.definition`/`intuition`/`example` chunk 분리 미도입 |

- 실질 준수는 **Reactive Misconception 1종이 강함**(코드 강제·동결 테스트 있음). Tiny Node·Shallow
  Traversal은 *인접 목적*이 부분 달성됐으나 6대 안정화 프레임으로 명명·게이트되진 않았다.
- Hybrid Retrieval·Chunk Embedding·Lazy Relation은 **LLM subgraph 소비처가 생길 때 함께 도입할
  후보**다(①과 동일 트리거) — 지금은 소비처가 없어 미도입.

## 항목 ③ 2-Stage Context — "Intent Router → Concept Resolver → Minimal Fetch → Pass#1 → Misconception Detector → Pass#2로 오개념이 reactive로만 로드되나?"

**판정 △ 파이프라인 미구현 · 목적(오개념 미preload)은 별경로로 이미 충족.**

- **6단계 오케스트레이터는 없다**:
  - `l3/router.py`는 *비용-티어 라우터*(FAST/MID/QUALITY·모델 패밀리 결정)이지 *intent* 라우터가
    아니다.
  - `l3/pipeline.py::generate()`는 **단일 패스** — route → 캐시 → provider.generate → (opt) shadow
    검증 → trace. 이미 조립된 `prompt`/`system`을 받고, 개념 fetch도 오개념 detect도 **Pass#1/Pass#2
    2패스 구조도 없다**.
  - `api/coach.py`는 reactive 매칭·코칭 결정을 내리지만 두-패스 LLM 구조가 아니며 LLM을 호출하지
    않는다(①).
- **그러나 2-Stage의 *핵심 목적*은 이미 만족**: "오개념을 초기 context에 preload하지 말고 탐지된
  뒤에만 reactive로 결선"이라는 계약은 `04c_misconception_seven_stage_separation.md:84,100-101`에서
  정본화·manifest 동결됐다. 즉 *오개념 오염 방지*는 2-Stage 파이프라인 없이도 달성돼 있다.
- 남은 것은 "개념 subgraph를 Pass#1으로 LLM에 주고, detector 후 Pass#2"라는 **2패스 골격 자체**인데,
  이는 ①의 소비처(LLM 튜터링 좌석)가 생겨야 의미가 있다.

## 항목 ④ traversal guard — "visited set · timeout · token budget guard가 있나?"

**판정 △ 부분.**

- **visited set ✅**: `prerequisite_recommendation.py:257-262`가 `seen: set[uuid.UUID]`로 dedup(MIN
  depth 유지·origin 제외). DAG 보장(offline `concept_graph/validate.py`의 `prerequisite_cycle`
  hard error)에 더한 방어.
- **depth bound ✅**: in-SQL `base.c.depth < max_depth`(재귀 CTE bound, line 232).
- **timeout ❌ · token budget guard ❌**: wall-clock timeout도, subgraph→prompt 직전 token 컷도
  없다 — LLM subgraph 소비처가 없어 *token 예산 개념 자체가 미존재*다(①). 현재 traversal은 SQL
  재귀라 DB가 종료를 보장하고, 결과는 프롬프트가 아니라 *선수 추천 목록*으로 소비된다.

---

## 왜 지금 안 짓는가 (근거 체인)

1. Part 8의 예산·2-Stage·token guard는 전부 **"LLM에 개념 subgraph를 주입하는 좌석"**을 전제한다.
2. 그 좌석은 오늘 없다 — `/v1/coach`는 LLM 호출 0(`api/coach.py:11-13`), `l3/pipeline.py`는 단일 패스로
   *이미 조립된* 프롬프트만 받는다.
3. 소비처 없이 예산·2패스·guard를 만들면 **호출되지 않는 dead code**가 된다 — 이는 프로젝트 절대
   금기("소비처 없는 추상 미도입", CLAUDE.md·`MEMORY.md` #357·#389)의 정면 위반이다.
4. 따라서 **의도적 보류가 준수**다. 지금 필요한 것은 코드가 아니라 *해제 조건의 명문화*다(아래).

## 해제 트리거 계약 — "언제·어떤 모양으로 도입하나"

**트리거**: 첫 *LLM에 concept subgraph를 주입하는 좌석*이 착륙하는 **바로 그 슬라이스**에서 예산
계층을 함께 도입한다. 후보 좌석 = WH-1 튜터링 루프(`harness/wh1_loop.py` 실배선), 앵커
`04c_misconception_seven_stage_separation.md:84,100`(단계 4 "Context (LLM)").

**도입 시 계약**(지금은 계약만 — 구현 아님):

- **하드캡을 단일 출처 상수로**(매직넘버 금지 — `MAX_PREREQUISITE_DEPTH` 선례):
  `depth ≤ 2` · `max_nodes ≤ 12~20` · `max_tokens ≤ 3000`. 상한은 *context builder 코드에 실제로
  박혀야* 한다(체크리스트 ①의 "코드에 상한").
- **재사용 좌석**(신규 traversal/검색 로직 최소화):
  - traversal = `l2/prerequisite_recommendation.py` 재귀 CTE(visited set `seen` 이미 있음).
  - 검색 = `l1/concept_graph/retrieval.py::search_concepts`(`min_similarity`·`domain`·`reviewed_only`
    게이트 이미 있음).
  - redaction = `db/models/concept_node.py`(본문 컬럼 부재 — 구조적 차단 유지).
- **guard**: visited set(재사용) + **신규** wall-clock timeout + **신규** token budget guard
  (subgraph를 프롬프트로 직렬화하기 *직전* 컷).
- **6대 안정화 동반 도입**(②의 ❌ 항목): Hybrid Retrieval(벡터+graph/lexical 융합)·Chunk Embedding
  (`limit.definition`/`intuition`/`example` 150~500 tokens 분리)·Lazy Relation을 이 좌석 요구에
  맞춰 도입.
- **2-Stage 골격**(③): Pass#1(개념 subgraph) → Misconception Detector → Pass#2(reactive). 오개념
  preload 금지 규약(`04c`)을 그대로 유지.
- **동결 테스트**: `tests/backend/l1/test_embedding_namespace_governance.py`의 hermetic freeze-test
  패턴을 미러해, 상한 상수·guard 존재를 *컴파일 단언*으로 동결(DB 불필요). Part 2·Part 6 검토가
  각각 거버넌스 테스트를 남긴 선례를 따른다.

---

## 잔여 리스크 · 후속

- **최우선**: 위 트리거 좌석(LLM 튜터링 Pass#1)이 없으면 Part 8 체크리스트 4항목은 계속 "부분/미구현"
  으로 남는다 — 이는 결함이 아니라 *소비처 대기 상태*다. `build_checkpoint_questions.md`가 stage 8
  "AI 튜터·Context"를 🔴 최우선 붕괴 위험으로 표시하는 것은 *구현 실패*가 아니라 *구현 시 반드시
  이 예산·guard를 함께 넣어야 한다*는 경고로 읽어야 한다.
- **인접 자산 인벤토리(무엇은 이미 있나)**: 개념/edge ORM + offline DAG 검증 · 선수 깊이 하드캡 +
  visited set · 벡터 검색 + 안전 게이트 · reactive 오개념(7단계 분리 동결) · 임베딩 namespace
  freeze(`test_embedding_namespace_governance.py`). 트리거 시 이들을 *조립*하면 되고, 바닥부터
  새로 짜지 않는다.
- **범위 밖(이 검토가 하지 않은 것)**: subgraph 빌더·2-Stage 파이프라인·Hybrid Retrieval·Chunk
  Embedding **구현**(트리거 좌석 슬라이스로 이연) · `coach.py`에 LLM 호출 신설 · 코드/테스트/스키마/
  마이그레이션 변경.
