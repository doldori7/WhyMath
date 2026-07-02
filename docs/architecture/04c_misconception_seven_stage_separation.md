# 04c. 오개념 7단계 분리 — Part 6 검토 + 정본 명세

> **상태**: 정본 (2026-07-02) · **계층**: L4 교수학 엔진 (횡단: L1 저장·L3 임베딩)
> **관련**: `04_pedagogy_engine.md` · `04b_misconception_judge_graduation.md` · `math_dsl_principles_review.md`(§3.4·§3.6) · `math_dsl_risk_register.md`(Q1·Q8) · `docs/standards/playbook_part_review_questions.md`(Part 6) · `CLAUDE.md`(§오개념 독립 DB·§8대 구조원칙 #6)

---

## 0. 이 문서가 존재하는 이유

구축 플레이북 **Part 6**(`docs/standards/playbook_part_review_questions.md:67-73`)는 오개념
시스템의 세 불변을 요구한다:

1. 오개념이 concept node에 **preload되지 않음** (embedding 오염·reasoning drift 방지)
2. **7단계 분리**(Storage/DB · retrieval · embedding index · context · runtime …)
3. **reactive retrieval만** + concept / misconception 인덱스 분리

2026-07-02 검토 결과, **현 시스템은 세 불변을 모두 코드로 강제된 상태로 준수**한다. 그러나
"**7단계 분리**"라는 용어는 저장소 어디에도 **정본으로 열거·정의된 적이 없다** — 체크리스트
자신도 5개(`Storage/DB · retrieval · embedding index · context · runtime`)만 적고 "…"로 생략했고,
`math_dsl_principles_review.md:34`는 분류 대상으로 *언급*만 한다. 이 문서가 그 공백을 닫는다:
**7단계를 실제 구현에 매핑해 정본화**하고, `tests/backend/l4/test_misconception_seven_stage_manifest.py`가
이 매핑을 **코드에서 동결**한다(명세↔코드 드리프트 차단).

> **열거 근거의 정직성**: 외부 플레이북에 완전한 7개 목록이 없으므로, 본 문서는 체크리스트의
> 명시 5단계에 **실제 구현에 이미 존재하는 2개 분리층**(Judge/Validation · Identity/Canonical)을
> 더해 7단계로 확정한다. 즉 이 열거는 "이상적으로 있어야 할 7개"가 아니라 **"지금 코드가 이미
> 분리하고 있는 7개 지점"**이다.

---

## 1. Part 6 감사 결과 (준수 근거)

### 항목 ① 오개념 concept node preload 금지 — ✅ 준수 (다중 방어)

| 방어 | 근거(file:line) |
|---|---|
| data-pipeline 노드에서 자유텍스트 `misconception_text` **제거**(2026-07-02) | commit `500b0cc` · `src/data-pipeline/data_pipeline/concept_graph/models.py` |
| 노드 순수성 정적 동결(금칙 필드 스냅샷) | `tests/data_pipeline/concept_graph/test_concept_node_purity.py`(`_FORBIDDEN_NODE_FIELDS` ∋ `misconception_text`) |
| backend 적재기가 `common_misconceptions=[]`를 **항상** 씀 | `src/backend/whymath_backend/l1/concept_graph/backend_concept.py:39,199,235` |
| 검색 서빙 프로젝션에 오개념 필드 **없음** | `src/backend/whymath_backend/db/models/concept_node.py`(name_ko·domain·코드·metaphor만) |
| 프로브가 노드 자유서술을 근거로 **안 씀**(활성 가설 ∩ 카탈로그만) | `src/backend/whymath_backend/l4/scene_generation.py:18-20` |

**수용된 부채 — `Concept.common_misconceptions: JSONB` 컬럼 존치**
backend `Concept` ORM은 아직 `common_misconceptions: JSONB` 컬럼을 *보유*한다
(`src/backend/whymath_backend/db/models/concept.py:128`). 그러나 이 컬럼은:
- **seed 메타 전용**이며 적재기가 항상 빈 배열로 채운다(위 표).
- **런타임 미사용이 정적 소스스캔으로 동결**된다:
  `tests/backend/schema/test_concept_misconception_runtime.py`가 `.common_misconceptions` 속성
  *접근*을 L1 seed 적재기(`l1/concept_graph/backend_concept.py`) **단 한 곳**으로 못박고, L4
  (코칭·진단)·하네스 런타임의 접근 **0**을 강제한다(누군가 런타임에서 읽기 시작하면 즉시 red).

→ 결정(2026-07-02): 컬럼을 **제거하지 않고 동결 유지**한다. 제거는 schema v1.0 breaking 변경인
반면, 위 두 테스트가 이미 "노드 자유서술 오개념이 런타임에 흐르지 않음"을 보장하므로 **오염
리스크는 이미 0**이다. 장기 거취(카탈로그 일원화)는 후속 슬라이스로 기록한다.

### 항목 ③ reactive retrieval만 + 인덱스 분리 — ✅ 준수

| 방어 | 근거 |
|---|---|
| reactive 기본 — 게이트 off면 substring `diagnose()`만·의미 매처 **미호출**·임베딩 로드 0 | `config.py:704`(`misconception_semantic_mode` default `"off"`) · `api/coach.py` |
| 3 임베딩(concept·misconception·atom) **물리 테이블 분리** | `db/models/{concept,misconception,atom}_embedding.py` |
| cross-table 코사인 **금지 동결**(`.cosine_distance(` allowlist 3모듈) | `tests/backend/l1/test_embedding_namespace_governance.py:228` |
| namespace 불변식 = 테이블(kind) × subject('수학' 기본) | `l1/embedding_primitives.py` |
| id-prefix 네임스페이스 분리 실측(수학 오개념이 예약 과목접두 미사용) | `tests/backend/l4/test_misconception_namespace_gate.py` |

> (참고·비위반) pgvector 영속 preload(`prebuilt_index=True`)는 코드에 갖춰졌으나 라이브 **기본
> 비활성**이다(`api/_misconception_state.py:49`). 현행은 첫 매칭 시 in-process 카탈로그 임베딩
> 웜업 — 이는 *개념 context preload*가 아니라 매처 캐시 웜업이므로 Part 6 preload 금지와 무관하다.

### 항목 ② 7단계 분리 — ⚠️→✅ (본 문서로 정본화)

---

## 2. 정본 7단계 분리

각 단계는 **개념(Concept)과 오개념(Misconception)이 분리되는 물리·논리 지점**이며, 구현 앵커와
동결 테스트를 가진다. 순서는 데이터 수명주기(저장→소비)를 따른다.

| # | 단계 | 개념 ↔ 오개념 분리 지점 | 구현 앵커 | 동결 테스트 |
|---|---|---|---|---|
| 1 | **Storage / DB** | 오개념 4테이블이 개념 테이블과 별도·FK로 개념에 결합 안 됨(loose ref)·노드에 자유텍스트 비내장 | `db/models/misconception_{catalog,hypothesis,crosslink,embedding}.py` | `test_concept_node_purity.py` · `test_concept_misconception_runtime.py` |
| 2 | **Retrieval** | reactive `diagnose()`(요청 시)·개념 조회 경로에 오개념 preload 0 | `l4/misconception/diagnose.py` · `combined.py` | `test_misconception_diagnose.py` |
| 3 | **Embedding index** | 3 임베딩 테이블 물리 분리 + cross-table 코사인 금지 | `l4/misconception/semantic/pgvector_index.py` · `l1/concept_graph/embedding.py` · `l1/atom_graph/embedding.py` | `test_embedding_namespace_governance.py` · `test_misconception_namespace_gate.py` |
| 4 | **Context (LLM)** | 초기 context에 오개념 미탑재·2-stage(개념 subgraph pass#1 → detection 후 pass#2·reactive) | `api/coach.py` · `harness/wh1_loop.py` | manifest(좌석 실재 동결) |
| 5 | **Runtime / detection gate** | 노출 게이트 off 기본·substring 우선·의미 매처 opt-in | `l4/misconception/match_gate.py` · `api/_misconception_state.py` | `test_misconception_state.py`(+ `config.py` 기본값) |
| 6 | **Judge / Validation** | LLM-judge는 **제거만·생성 안 함**·shadow→canary→full 승급 | `l4/misconception/judge.py` · `judge_seam.py` | `test_misconception_judge.py` |
| 7 | **Identity / Canonical** | 오개념 = 단일 canonical 정체성(kebab 30 정본 ↔ M-id 839 콘텐츠 crosswalk)·개념과 별 키공간 | `l4/misconception/catalog.py` · `l1/misconception/crosslink_resolve.py` | `test_misconception_crosslink.py` |

### 단계별 주석

- **1 Storage/DB** — 오개념 콘텐츠(`misconception_catalog`, PK=`mis_id`)·학생별 활성 가설
  (`misconception_hypothesis`)·crosswalk(`misconception_crosslink`)·임베딩
  (`misconception_embedding`)이 전부 개념 테이블(`concept`·`concept_node`)과 별개다. crosslink는
  `mis_id`만 실 FK(CASCADE)이고 kebab-id·`concept_src_id`는 *느슨참조*(원천 문자열·조회 시 조인).
- **2 Retrieval** — 진단은 학생 입력이 들어올 때 substring+regex `diagnose()`로 *당겨온다*. 개념
  조회(`l1/concept_graph/retrieval.py`)는 오개념을 함께 싣지 않는다.
- **3 Embedding index** — 같은 pgvector store 안에서도 kind가 *테이블*로 분리되고, 서로 다른
  kind 테이블 간 SQL 코사인 join이 allowlist(3모듈)로 금지된다. "방향맹 매처"(둘레↔넓이 코사인
  동일)가 실측된 리스크(`04b` §2)라 이 분리는 측정으로 정당화된다.
- **4 Context** — 오개념은 LLM 초기 프롬프트에 preload되지 않는다. 개념 subgraph로 1차 추론하고,
  오개념은 *탐지된 뒤*에만 reactive로 결선된다(2-stage).
- **5 Runtime gate** — `misconception_semantic_mode` 기본 `off`, `misconception_judge_enabled`
  기본 `False`. 기본 경로는 substring만 — 보수적 노출로 거짓 낙인(RS2)을 막는다.
- **6 Judge/Validation** — judge는 방향(⇒역)·부정(≠)·등치(=)가 어긋난 후보만 *걸러* 오도된
  가르침(의사결정 우선순위 #1·#3)을 줄인다. 생성하지 않으므로 실패모드는 과소코칭(안전)이다.
- **7 Identity/Canonical** — 런타임 탐지 정본(kebab-id 30종·`CATALOG_BY_ID`)과 콘텐츠 카탈로그
  (M-id 839종)는 **의도적으로 FK 미결합**이고 crosswalk로 이어진다. 개념 identity와 다른 키공간이라
  오개념 정체성이 개념 정체성에 오염되지 않는다.

---

## 3. 동결 (manifest 테스트)

`tests/backend/l4/test_misconception_seven_stage_manifest.py`가 본 명세를 코드에서 동결한다.
기존 governance 테스트(namespace·purity·runtime)와 **단언을 중복하지 않고**, 명세가 주장하는
7단계 앵커가 *전부 실재*함을 hermetic하게 확인한다:

- 7단계 각 앵커 모듈이 import 가능(존재).
- 오개념 4 ORM 테이블명이 개념 테이블명과 **disjoint**(FK 비결합 재확인).
- 항목 ①③·preload 동결을 담당하는 **기존 테스트 파일이 저장소에 실재**(연결 무결성 — 명세가
  "존재한다"고 주장한 방어가 실제로 있음).
- 런타임 게이트 기본값이 reactive(`semantic_mode="off"`·`judge_enabled=False`)로 동결.

명세를 바꾸면 이 테스트가 red가 되어 문서와 코드가 함께 움직이도록 강제한다.
