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
