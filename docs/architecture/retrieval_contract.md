# AI Retrieval 계약 — 임베딩 namespace · traversal 예산 · redaction · 파셋

> **상태**: 계약(contract) · **계층**: 횡단(L1 임베딩 · L2 traversal · L4 오개념) · **작성일**: 2026-07-01
> **상위**: `math_dsl_risk_register.md`(부채) · `notation_contract.md`(동치 권위) ·
> `math_dsl_remediation_design.md`(교정 설계).
> **범위**: retrieval(임베딩·의미검색·graph traversal)의 *불변 계약*과 파셋/거버넌스 규약을 한곳에
> 모은다 — `notation_contract.md`가 동치 권위를 고정하듯, 본 문서는 retrieval 안전 규약을 고정한다.

---

## 1. Retrieval 아키텍처 스냅샷 (실측)

| 축 | 규약 | 좌석 |
|---|---|---|
| 임베딩 store | **물리 분리 3 namespace** — `concept_embedding`·`atom_embedding`·`misconception_embedding` | `db/models/{concept,atom,misconception}_embedding.py` |
| 공간 격리 | 검색은 *같은 provider·model 행만* 코사인 비교(다른 임베딩 공간 혼재 차단) | `atom_graph/embedding.py` `search` |
| 원자 임베딩 입력 | **안전 구조 신호만** — name·transfer·cognitive_type·subunit | `l1/atom_graph/embedding.py` `atom_embedding_text` |
| 오개념 임베딩 입력 | `name_kr. canonical_statement`(방향맹 — recall 전용) | `l4/misconception/semantic/matcher.py` |
| 결합 포맷 권위 | 단일 — `". ".join(strip·non-empty)`·format v1 | `l1/embedding_primitives.py` `join_embedding_text` |
| graph traversal | 재귀 CTE·`MAX_PREREQUISITE_DEPTH=5`·**PREREQUISITE만**·MIN-depth dedup | `l2/prerequisite_recommendation.py` |
| LLM context 예산 | **미도입**(max_nodes·max_tokens — 소비처 부재·premature) | (없음·의도적) |

---

## 2. 불변 계약 (협상 불가)

### C1. Namespace 분리 — 임베딩 공간은 타입별로 물리 분리
concept / atom / misconception 임베딩은 **별도 테이블**이고 검색은 provider·model 공간이 일치하는
행만 본다. 타입 간 embedding collision은 구조적으로 차단된다(공통 임베딩 = 의미 오염 금지).

### C2. Redaction — 임베딩 입력은 자체 작성 안전 신호만 (CLAUDE.md 우선순위 #2)
임베딩 입력에 **성취기준 본문 근접 필드를 절대 넣지 않는다** — `core_proposition`·`description`·
`formal_definition`·4요소(`misconception`·`diagnostic_*`·`socratic`)는 텍스트 빌더가 *인자로 받지도
않는다*(구조적 차단·이중 방어). 교육과정 필드(`grade_band`·`standard_codes`)도 입력에 없다
(Overlay/code 소관·학년반복 융합 방지). 원문은 임베딩 테이블에 저장하지 않고 `text_hash`만 둔다.

### C3. 안전 파셋 — cognitive_type·subunit만 신호로 허용
원자 임베딩 신호를 풍부화하되 저작권-안전 *분류/주제 라벨*만 쓴다: `cognitive_type`(개념/절차/표상
— "객체 vs 기법 vs 표상" 축 분리)·`subunit`(소단원 주제명). 이는 본문이 아니라 분류 라벨이다.
새 파셋을 추가하려면 본문 근접이 아님을 확인하고 C2 화이트리스트를 *의도적으로* 넓혀야 한다.

### C4. Traversal 화이트리스트 — PREREQUISITE만 따른다
graph traversal은 `TRAVERSAL_ELIGIBLE_EDGE_TYPES = {PREREQUISITE}` *단일 출처*만 따른다. 약한 관계
(ANALOGOUS_TO·CONTRASTS·EXTENDS·COMPOSED_OF·TRIGGERS_DISTRACTOR)는 (a) load-time skip으로 *적재* 차단,
(b) traversal 화이트리스트로 *조회* 차단 — 두 층 이중 방어(`test_edge_relation_governance`·
`test_prerequisite_traversal_governance`).

### C5. Traversal 예산은 그래프 깊이 예산 (≠ LLM context 예산)
`MAX_PREREQUISITE_DEPTH=5`는 그래프 traversal 깊이 상한이다(단일 출처·API 경계 공유). LLM에 subgraph를
주입하는 max_nodes·max_tokens 예산은 *소비처가 생긴 뒤* 별도 도입한다(지금 미존재 — premature).

### C6. 방향 판별은 임베딩에 기대지 않는다
오개념 임베딩은 방향·부정·등치를 못 가린다(방향맹·테스트 동결). 임베딩은 *recall 확장*만 하고
방향 판별은 SymPy(`wrong_form_match`)·LLM/NLI judge가 2단으로 한다(정오 판정 임베딩 금지·C6=`notation_contract` C1과 정합).

---

## 3. 10문답 요지 (retrieval 관점)

| # | 질문 | 요지 |
|---|---|---|
| 1 | ambiguous node | 원자(얇은 신호) — 파셋 풍부화로 완화(C3). 집계 노드는 임베딩 제외라 안전 |
| 2 | collision concept | "객체 vs 해석" 동일 name 계열 — cognitive_type 파셋으로 분리 |
| 3 | 실패 relation | 약한 관계(미적재·미traversal). PREREQUISITE만이라 현재 안전(C4) |
| 4 | concept vs skill vs problemType | skill 전용 노드 없음(=cognitive_type 절차). 파셋으로 분리(C3) |
| 5 | misconception retrieval | 방향맹(C6) — SymPy+judge 2단 |
| 6 | traversal 폭발 | bound·DAG·단일 관계로 낮음(C4·C5). 약한 관계 해제 시 위험 |
| 7 | context 낭비 | 소비처 없음(예산 premature·C5). 미래 hub·FP·미압축 traversal 주의 |
| 8 | symbolic vs educational | SymPy 단일 동치 권위·임베딩은 recall만(C6·`notation_contract`) |
| 9 | AST vs semantic | AST retrieval 미존재 — 조기 도입 금지(두 진실 회피) |
| 10 | future RAG 위험 | ① 얇은 원자 신호 ② 단일 임베딩 축 혼동 ③ 오개념 방향맹 ④ 약한 관계 해제 |

---

## 4. 전략 구현 상태 (D·B)

### 전략 D — semantic 파셋 신호
- **구현**: `atom_embedding_text`에 안전 파셋(cognitive_type·subunit) 추가 — 원자 벡터가 개념/절차/
  표상·주제로 분리(C3). `text_hash` 변경으로 다음 populate가 변경분 자동 재임베딩(멱등).
- **유보(premature)**: hard facet-filter 컬럼(`atom_embedding`에 cognitive_type/domain 컬럼)·facet
  필터 search API. **조회 소비처(retrieval query layer)가 생긴 뒤** 도입한다 — 지금은 임베딩 입력
  풍부화(soft 파셋)로 semantic 분리만 얻는다.

### 전략 B — relation pruning 거버넌스
- **구현**: traversal 화이트리스트 단일 출처(`TRAVERSAL_ELIGIBLE_EDGE_TYPES`) + 동결 테스트(C4).
- **유보(premature — AI 관계 증강 착수 전 필수 계약으로 기록)**:
  - `ConceptEdge.generated_by`(생성 출처)·`traversal_eligible`(관계별 조회 적격 플래그) 스키마 필드.
  - 단방향 canonical edge 강제(양방향 금지 — 현재 self-edge만 불변식).
  - **AI 자동생성 관계 거버넌스**: 별도 namespace + `generated_by` + 사람 승급 게이트 전 PREREQUISITE
    그래프 직접 삽입 절대 금지(플레이북 §3.7). 약한/AI 관계를 C4 화이트리스트에 넣기 전에 ranking
    전용(traversal 제외)임을 먼저 보장한다.

---

## 5. 미래 확장 시 체크리스트 (계약 위반 방지)

- 새 임베딩 신호 추가 → C2 본문 근접 여부 확인 → C3 화이트리스트 의도적 확장 + 테스트 갱신.
- 새 관계 traversal 편입 → C4 화이트리스트에 *의도적* 추가 + ranking-전용 여부·generated_by 확인.
- LLM subgraph 소비처 신설 → 그때 max_nodes·max_tokens 예산 단일 출처 도입(C5) + hub 노드 제외.
- 오개념 방향 판별 개선 → 임베딩이 아니라 SymPy/judge 경로에서(C6).

---

## 참고
- 상위: `math_dsl_risk_register.md`(Q1~Q10·Q10-⑧ traversal 예산) · `notation_contract.md`(동치 권위) ·
  `math_dsl_remediation_design.md`.
- 좌석: `l1/atom_graph/embedding.py`·`l1/embedding_primitives.py`·`l2/prerequisite_recommendation.py`·
  `l4/misconception/semantic/matcher.py`·`db/models/{concept,atom,misconception}_embedding.py`.
- 테스트: `tests/backend/l1/atom_graph/test_atom_embedding.py`·`tests/backend/l1/test_edge_relation_governance.py`·
  `tests/backend/l2/test_prerequisite_traversal_governance.py`·`test_prerequisite_depth_budget.py`.
- 원칙: `CLAUDE.md`(의사결정 우선순위 #2 저작권·표현≠의미·premature 금지).
- 변경 이력: v0.1 (2026-07-01 — 계약 명문화 + 전략 D/B 구현분·유보분 기록).
