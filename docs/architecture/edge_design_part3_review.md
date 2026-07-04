# 관계(Edge) 설계 — 플레이북 Part 3 준수 검토

> **범위**: 구축 플레이북 **Part 3. 관계(Edge) 설계**(`docs/standards/playbook_part_review_questions.md:41-48`)
> 4개 준수 항목을 현 코드베이스에 대해 검토하고 발견된 갭을 교정한 기록.
> **형식**: `math_dsl_principles_review.md`(플레이북 vs 현재상태 갭 분석) 답습.
> **결론**: 4항목 중 3개가 **부분 준수**였고, 마이그레이션 없이(어휘 crosswalk·build-time 불변식·
> 문서화) 교정했다. 실데이터(437노드·581엣지) 검증 **error 0 불변**.

법칙(Part 3): *Node ≠ Relation 물리적 별도 파일. AI Graph vs Runtime Graph 분리. 단방향 + weight.*

---

## 요약 — 4개 항목 판정

| # | Part 3 항목 | 검토 전 | 검토 후 | 근거 |
|---|---|---|---|---|
| ① | 관계가 `relations/*.json` 별도 파일인가 (노드 15KB→1KB) | ⚠️ 대체로 | ✅ | 엣지는 `prerequisite_edges.jsonl`·`graph.json.edges`로 이미 물리 분리, 노드 소형. `prerequisite_concept_ids` 역정규화 캐시의 **일관성 불변식 부재** → 신규 `prerequisite_cache_consistency`로 방어 |
| ② | Edge 타입 5~8개 · `similar_to`/`related_to` 미사용 | ⚠️ | ✅ | 개수(7)·금지어 부재는 OK였으나 **어휘 3중 drift**(pipeline 7 / backend 6 / atom 1·이름 상이) → **crosswalk 단일 명세 + 양쪽 거버넌스 테스트** 도입 |
| ③ | AI Graph vs Runtime Graph 분리 | ✅(문서 갭) | ✅ | Concept Purity + 3중 store로 실질 분리됨. 플레이북 명칭 문서화·**모델 purity 가드 테스트** 추가 |
| ④ | 단방향 canonical + weight · 낮은 weight 제거 | ⚠️ | ✅ | 단방향 canonical(`[src,dst,relation]`)·`strength` OK였으나 **weight floor/pruning 부재** → `MIN_EDGE_STRENGTH` + `weak_edge` 불변식 |

---

## 항목별 상세

### ① 관계 = 노드와 물리적 별도 파일

**현황(양호):** 개념 엣지는 노드와 물리적으로 분리 저장된다.
- 원천 엣지: `data/corpus/concept_graph_v1/prerequisite_edges.jsonl`(581행)
- 정형 산출: `graph.json`의 `edges` 배열(노드 `concepts`와 별도 키)
- 노드 파일은 소형이라 플레이북의 "limit node 15KB" 문제는 발생하지 않는다.

**갭:** `Concept.prerequisite_concept_ids`(`models.py:162`)가 prerequisite 엣지를 노드에
역정규화(조회 캐시)한다 — dual-truth. transform이 엣지에서 캐시를 역채우므로 *생성 시점엔*
일치하나(실데이터 mismatch 0), `graph.json` 산출물이 하위에서 독립 편집·적재될 때 drift를
잡을 안전망이 없었다.

**교정:** `validate_graph`에 **`prerequisite_cache_consistency`**(warning) 추가 —
노드 캐시 집합 == `{src | prerequisite 엣지 ∧ dst==concept_id}`. 불일치 시 누락/잉여를 리포트.
(`validate.py` 7c절, `test_validate.py::TestPrerequisiteCacheConsistency`.)

### ② Edge 타입 5~8개 · 금지 어휘

**현황:** pipeline `Relation`은 7종(5~8 예산 내), `similar_to`/`related_to`는 어느 어휘에도
없다. backend `ANALOGOUS_TO`(유사)는 traversal에서 배제된다(약한 관계 N² 방어).

**갭(핵심):** 관계 어휘가 **3중으로 존재하고 이름·개수가 어긋난다** — 단일 진실 원천 부재.

| 계층 | enum | 개수 | 예 |
|---|---|---|---|
| L1 pipeline | `Relation`(models.py) | 7 | `generalization`·`composition`·`notation_variant` |
| L2 backend | `EdgeType`(enums.py) | 6 | `EXTENDS`·`COMPOSED_OF`·`ANALOGOUS_TO`·`TRIGGERS_DISTRACTOR` |
| atom | `AtomRelation` | 1 | `prerequisite` |

또한 산문 "6종"이 스키마·문서·docstring 전반에 stale로 남아 실제 7종(notation_variant 포함)과
불일치했다.

**교정:**
- **`relation_crosswalk.py`** 신규 — pipeline `Relation` → backend `EdgeType` 투영을 단일 명세
  (`generalization`/`specialization`→`EXTENDS`·`composition`→`COMPOSED_OF`·`contrast`→`CONTRASTS`·
  `application`/`notation_variant`→deferred). backend 전용 `ANALOGOUS_TO`·`TRIGGERS_DISTRACTOR`는
  pipeline 원천 없음(각각 traversal 배제·오개념 op-code 어휘)으로 명문화.
- **거버넌스 테스트 2곳**: `test_relation_vocabulary_governance.py`(L1 — 5~8 예산·crosswalk 전수·
  금지 토큰·traversal 배제)와 기존 `test_edge_relation_governance.py` 확장(L2 — EdgeType 값 집합
  freeze·예산·금지 토큰). 두 스위트가 분리(별도 pytest·상호 import 불가)라 backend 값 집합을
  양쪽에서 미러 freeze한다 — 미러가 어긋나면 crosswalk 표를 의식적으로 갱신해야 red가 풀린다.
- **crosswalk 정본 표**를 `docs/data/concept_graph.md` §2.2b에 추가. "6종"→"7종" 산문 전면 정리
  (`edge.schema.yaml`·`01_data_foundation.md`·`concept_graph.md`).

**적재 현황(불변):** 현 범위는 `prerequisite`만 backend `concept_edge`에 적재한다(약한 관계
유입 차단). crosswalk는 관계가 *노드화·적재될 때*의 투영 어휘를 미리 확정할 뿐 적재를 개시하지 않는다.

### ③ AI Graph vs Runtime Graph 분리

**현황(실질 준수):** 프로젝트는 플레이북의 "AI Graph/Runtime Graph" 명칭 대신 **Concept Purity +
3중 store**로 같은 원칙을 구현한다.
- AI Graph = 개념 + 최소 relation(prerequisite) + 오개념 subset(reactive) + AST → Neo4j + PG `concept_node`
- Runtime Graph = renderer·animation·layout·UI → `data/render_contract.json` + L5 클라이언트·Learning Scene DSL
- embedding = pgvector `concept_embedding`(노드 미저장·참조만)

**갭:** 이 대응이 명칭으로 문서화돼 있지 않았고, 노드 순수성을 *필드 수준*에서 동결하는 테스트가
없었다(redaction 테스트는 `description`/`formal_definition`만 커버).

**교정:**
- `concept_graph.md` §2.2c에 플레이북 라벨 ↔ Concept Purity/3중 store 대응표 추가.
- **`test_models.py::TestConceptPurity`** — `Concept` 필드 화이트리스트 freeze + renderer·animation·
  layout·embedding·prompt 토큰 필드명 부재 단언 + 렌더 실체 슬롯(`figure_spec` 등) 거부 확인.
  시각화·오개념은 *참조 키*만 허용(실체는 노드 밖).

### ④ 단방향 canonical + weight · 낮은 weight 제거

**현황:** 엣지는 단방향 canonical(복합키 `[src_concept_id, dst_concept_id, relation]`)로
저장되고 `strength`(0.0~1.0)를 보유한다.

**갭:** "낮은 weight는 제거되나?"에 해당하는 **weight floor/pruning이 전무**했다 —
검증은 cycle·inverse pair·grade 단조성만 봤다.

**교정:**
- **`MIN_EDGE_STRENGTH = 0.3`**(models.py) — 엣지 strength 하한 단일 임계값.
- `validate_graph`에 **`weak_edge`**(warning) — 하한 미만 엣지를 build-time에 가시화.
- 현재 데이터는 전 엣지 strength=0.8이라 **no-op**(경고 0). 향후 자동 제안·약한 관계 유입 시의
  데이터 품질 하한이다.
- **런타임 동적 pruning은 후속**(소비처 생길 때) — premature 기계 금지 원칙(`current_phase_checklist.md:58`)
  대로 여기서는 *데이터 품질 하한*만 명문화한다.

---

## 준수한 프로젝트 불변 제약

- **enum rename 금지**(`edge.schema.yaml:96-98`) — 어휘 정합은 rename이 아니라 crosswalk로 해결.
- **premature 런타임 기계 금지** — weight pruning은 build-time floor 게이트까지만.
- **Phase 1 warning=통과, error만 실패**(`validate.py`) — 신규 불변식 3종 전부 warning.
- **단일 진실 원천** — 중복 저장(캐시)은 일관성 불변식으로 방어, 어휘는 crosswalk로 단일화.

## 변경 파일

| 파일 | 변경 |
|---|---|
| `src/data-pipeline/data_pipeline/concept_graph/relation_crosswalk.py` | 신규 — 어휘 crosswalk 단일 명세 |
| `src/data-pipeline/data_pipeline/concept_graph/models.py` | `MIN_EDGE_STRENGTH` 상수 |
| `src/data-pipeline/data_pipeline/concept_graph/validate.py` | `weak_edge`·`prerequisite_cache_consistency` 불변식 |
| `tests/data_pipeline/concept_graph/test_relation_vocabulary_governance.py` | 신규 — L1 어휘 거버넌스 |
| `tests/data_pipeline/concept_graph/test_validate.py` | weak_edge·cache_consistency 케이스 |
| `tests/data_pipeline/concept_graph/test_models.py` | `TestConceptPurity` |
| `tests/backend/l1/test_edge_relation_governance.py` | EdgeType 값 freeze·예산·금지 토큰 |
| `docs/data/concept_graph.md` | §2.2b crosswalk · §2.2c AI/Runtime · "6종"→"7종" |
| `schemas/v1.1/edge.schema.yaml`·`docs/architecture/01_data_foundation.md` | "6종"→"7종" 정리 |

## 남은 후속(별도 슬라이스)

- 약한 관계(generalization 등) *적재* 개시 시 crosswalk 투영대로 backend 적재기 확장.
- 런타임 동적 weight pruning(소비처 = 학습 경로 랭킹 생길 때).
- backend 전용 어휘(ANALOGOUS_TO·TRIGGERS_DISTRACTOR)의 노드화 여부 결정.

---

# 심층 재검토 — 리치 Part 3 스펙(3-1~3-5) · 2026-07-03

> **범위**: 위 4항목 체크리스트보다 상세한 **리치 Part 3 스펙**(3-1 물리분리·3-2 Edge 6+4종·
> 3-3 유지/버릴 것·3-4 순환참조·3-5 Traversal)에 대한 재검토. Part 2가 #407(2026-07-03
> `MEMORY.md`)에서 "리치 스펙 전면 채택"된 것과 짝을 이루나, **Part 3(엣지)는 #407이 재확인한
> 협상-불가 경계 안에서** 판정한다: **신규 엣지 타입 0 목표 · 노드간 연결 참조 키 우선 ·
> anti-explosion · redaction**.
> **결론**: 스펙 요구 대부분이 (a) 이미 충족, (b) 위 경계로 *참조-키 방식 실현*(엣지화 안 함),
> (c) 소비처 부재로 *deferred*(테스트·ADR·로드맵으로 동결)다. **코드·마이그레이션 0 — 판정·문서화만**
> (#407 Phase 0 패턴 답습).

## 서브섹션별 conformance

### 3-1 노드/관계 물리 분리 · AI vs Runtime Graph — ✅ 실질 충족
- node↔edge 물리 분리: `graph.json`의 `concepts`/`edges` 별도 키 + `prerequisite_edges.jsonl`(581행).
  전용 `relations/*.json` 디렉토리는 아니나 분리 *의도*(Node=존재 / Relation=해석) 달성.
- AI Graph vs Runtime Graph: Concept Purity + 3중 store(Neo4j 구조 / pgvector 임베딩 / PG 메타)
  + `render_contract.json`(§2.2c).
- 스펙 디렉토리(concepts/relations/curriculum/misconceptions/ast) 대응: concepts ✅ /
  misconceptions ✅(`misconceptions_v1/` 839건 독립) / ast ≈ `atom_graph_v1/`(원자 백본) /
  curriculum = Overlay(`curriculum_entry`) / relations = `prerequisite_edges.jsonl`+`edges`.
  → 분리 *목적* 달성, 디렉토리 형태만 상이(리네이밍 불요).

### 3-2 핵심 Edge 6종 + 확장 4종(교수학 어휘) — ⚠️ 어휘 불일치, #407로 **판정 종결**
- 현재 = 구조적 7종(`prerequisite`/`generalization`/`specialization`/`contrast`/`application`/
  `composition`/`notation_variant`). 스펙 = 교수학 6+4종.
- **판정**: #407 "신규 엣지 타입 0 목표 · 참조 키 우선"에 따라 **교수학 이름을 엣지 타입으로 채택하지
  않는다.** 스펙 pedagogy 관계는 아래 매핑대로 *이미 참조 키/역방향 쿼리/별도 카탈로그*로 실현됨.
  enum rename 금지 불변식(`edge.schema.yaml`)과도 정합.
- `similar_to`/`related_to`는 어휘·traversal 어디에도 없음(금지 토큰 동결). ✅

### 3-3 유지/버릴 것 — 부분(핵심 위험은 이미 차단)
- `similar_to`/`related_to` 제거·traversal 금지 ✅(`FORBIDDEN_RELATION_TOKENS` 동결).
- prerequisite subtype(conceptual/procedural/symbolic): backend `concept_edge.relation_subtype`
  **슬롯 존재·값 없음** → 전문가 subtype 데이터 생길 때 채움(스키마 준비됨).
- visualization subtype(static/interactive/…): `VisualizationType`/`VisualizationStyle` enum으로
  *자산 속성*에 존재(엣지 서브타입 아님).
- `transforms_to`/action graph: 미존재(greenfield). `math_dsl_*`는 *표기/렌더 DSL*이지 변환 관계
  그래프가 아님 → Part 2 로드맵(#407 MEMORY 2026-07-03) FormulaNode/AST(P5)와 함께 재판정 대상.

### 3-4 순환참조 방지 — 부분(batch 강제 O · 증분/SCC deferred)
- prerequisite DAG **batch 강제**: `validate.py::_find_prerequisite_cycle`(hard error) +
  atom load-time gate `l1/atom_graph/populate.py`(`AtomBackboneCycleError`). ✅
- 단방향 canonical: 복합키 `[src,dst,relation]`, 역방향은 런타임 쿼리(`to==C`의 `from`). ✅
- insert-time Reachability Check(`reachable(B,A)` reject): ⛔ deferred — **증분 edge-add API 부재**
  (엣지는 batch 멱등 적재·self-edge만 차단). 소비처 생길 때 도입.
- SCC(Tarjan/Kosaraju) cron: ⛔ docs-only/deferred(동일 사유·`math_dsl_risk_register.md` 미채택).
- AI 자동생성 relation namespace/`generated_by`: ❌ — 현재 전 엣지 `evidence_source=expert_review`
  (AI 생성 엣지 미존재). 도입 시 필요.
- Pedagogy↔Misconception cycle: 오개념이 엣지가 아니라 참조 키/카탈로그라 **구조적으로 발생 불가**
  (이 위험 자체가 차단됨).

### 3-5 Traversal Depth 제한 — 부분(depth·visited·related_to 금지 O · 나머지 소비처 대기)
- depth bound: `MAX_PREREQUISITE_DEPTH=5`(단일 출처, `test_prerequisite_depth_budget.py` 동결·
  API `MaxDepth` 공유). 기본 `max_depth=1`.
  **⚠️ 2단계 의미**: `5`는 *방어적 하드 캡*(그래프 traversal 재귀 bound)이고, docs의 튜터링1·심화2·
  연구3은 *아직 없는 LLM-subgraph 소비처용 교육 권장값*이다 — 서로 다른 축이라 "코드가 docs를
  어긴다"가 아니다(값은 의도적·동결이라 미변경).
- visited-set ✅ · `related_to` traversal 금지 ✅(positive prerequisite-only filter +
  `TRAVERSAL_EXCLUDED`/`FORBIDDEN` 동결). 유사도 랭킹은 pgvector `retrieval.py`(traversal과 분리).
- max_nodes/max_tokens/max_branching budget · timeout · intent-aware · context-compression:
  ⛔ deferred — **LLM subgraph 주입 소비처 부재**(코드 주석·risk_register 명시). Minimal Reasoning
  Subgraph 추출기도 소비처 생길 때.
- 런타임 weight pruning: ⛔ deferred — `MIN_EDGE_STRENGTH` build-time floor·`weak_edge` warning만;
  런타임은 `edge_strength`를 *정렬 tie-break*로만 사용(WHERE 필터 없음). 학습경로 랭킹 소비처 생길 때.

## 스펙 어휘 → 현 구현 매핑 (3-2 핵심)

| 스펙 관계 | 현 구현 (엣지 아님이면 명시) |
|---|---|
| `prerequisite` | `Relation`/`EdgeType.PREREQUISITE` — 유일 적재·travers 대상 |
| `misconception_of` | **엣지 아님** → `Concept.misconception_codes` + `MisconceptionCatalog`(839) |
| `visualizes` | **엣지 아님** → `Concept.visualization_card_keys` + `render_contract.json` |
| `required_for` | prerequisite **역방향 쿼리**(`to==C`의 `from`) — 별도 타입 아님 |
| `solved_by` | 미존재(후속 — 풀이전략은 #407 로드맵 Strategy/P6) |
| `frequently_confused_with` | `contrast`/`CONTRASTS`(의미 근접) |
| `generalizes` | `generalization`/`EXTENDS` |
| `analogous_to` | `ANALOGOUS_TO`(backend-only·**traversal 배제**) |
| `proves` / `abstraction_of` | 미존재(#407 로드맵 Proof/P6 · `generalization` 근접) |

## deferred 항목 + 재개 trigger (감사 가능한 명문화)

| deferred 항목 | 재개 trigger |
|---|---|
| insert-time Reachability Check + SCC(Tarjan) cron | 증분 edge-add API가 생길 때(현재 batch 멱등 적재) |
| Traversal Budget(max_nodes/tokens/branching)·timeout·Minimal Reasoning Subgraph·context-compression | LLM subgraph 주입 소비처가 생길 때 |
| 런타임 weight pruning | 학습경로 랭킹 소비처가 생길 때(build-time floor는 이미 존재) |
| edge subtype(prerequisite conceptual/procedural/symbolic) | 전문가 subtype 데이터(backend `relation_subtype` 슬롯 준비됨) |
| `generated_by` namespace | AI 자동생성 엣지 실도입 시 |
| `transforms_to`/action graph · FormulaNode/AST 결합 | Part 2 로드맵(#407 MEMORY 2026-07-03) **P5(FormulaNode)·AST** |
| pedagogy 엣지화(`misconception_of` 등) | **채택 안 함** — #407 신규 엣지 타입 0·참조 키 유지 |

## 판정 요지

리치 Part 3 스펙은 대부분 **① 이미 충족**(물리 분리·단방향 canonical·depth/visited/related_to 금지·
AI vs Runtime 분리), **② #407 경계로 참조-키 방식 실현**(pedagogy 관계는 엣지화하지 않음), **③ 소비처
부재로 명시적 deferred**(reachability/SCC/traversal budget/weight pruning/subtype/generated_by — 전부
trigger 명문화)다. 신규 코드·마이그레이션 없음 — Part 2 #407 Phase 0과 동일하게 **판정·문서화만** 수행한다.
