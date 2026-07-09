# 아키텍처 감사 1회차 (ARCH-01) — 플레이북 불변식·7계층 경계·이중 truth source

> **감사일**: 2026-07-09 | **태스크**: `backlog/tasks/ARCH-01-playbook-audit.yaml` | **방법**: 코드 실측 (라인 단위 근거)
> **기준**: `build_checkpoint_questions.md`(진행 축) · `playbook_part_review_questions.md`(설계-준수 축)
> **한 줄 결론**: 핵심 불변식은 준수 + CI 동결 상태. 신규 위반 0건, 갭 1건(클라이언트 무-수학로직 CI 게이트 부재), 문서화된 유예 1건(depth≤2). 상환 태스크 2건 등록.

---

## 1. Part 0~12 판정표

| Part | 핵심 법칙 | 판정 | 근거 (실측) |
|---|---|---|---|
| 0 왜 만드는가 | 7대 구조 문제 역산 | ✅ | 각 모듈 docstring이 담당 문제 명시 (전수 재검문은 회차 순환) |
| 1 전체 그림 | Minimal Core·5대 분리 | ✅ | 노드에 UI/AI/렌더러/런타임 상태 누출 0 (Part 2·7 판정에 포섭) |
| 2 노드 설계 | 순수성·독립 오개념 단위 | ✅ | `atom_node.py` redaction(본문 컬럼 부재), `test_concept_node_purity.py` `_FORBIDDEN_NODE_FIELDS` 14종 + `model_fields` 스냅샷 동결, `test_node_granularity_governance.py` 입도 동결 |
| 3 관계 설계 | 엣지 5~8종·약한 관계 traversal 금지 | ✅ | pipeline `Relation` 7종·backend `EdgeType` 6종 (예산 내). `relation_crosswalk.py:68` `FORBIDDEN_RELATION_TOKENS={similar_to, related_to}`, 적재는 PREREQUISITE 단일(`LOADED_RELATION`), `test_relation_vocabulary_governance.py` `_MIN=5,_MAX=8` 동결 |
| 4 AST | 5계층 분리·CAS급 정규화 금지 | ✅ | FormulaNode canonical-only(P5a)에서 "SymPy 재구현 금지 경계" AST 스캔 동결(`test_formula_governance.py`) |
| 5 시각화 | 4분류·Renderer 독립·5상태 | ✅ | 2026-07-02 `05b` 검토 완료, `test_visualization_state_separation.py` + import-linter CI |
| 6 오개념 | reactive retrieval·preload 금지 | ✅ | `warmstart.py:18-25` preload 금지 명문 + probe 전용 격리(반환 `list[str]` mis_id — 본문 구조적 배제), `coach.py:1191-1216` shadow 경로 한정 |
| 7 Math UI DSL | Core 역류 금지 | ✅ (9블록 분기 △ 기존 판정 유지) | `test_scene_dsl_layer_governance.py` 단방향·필드 freeze. 9블록 잔여(학생모델 축 등)는 part7 review 기존 상환 계획 유효 |
| 8 Context | Minimal Subgraph 예산 | ✅/⏸ | **max_nodes≤20·max_tokens≤3000 준수·CI 동결**: `wh1_llm_policy.py:119,124` + `test_wh1_llm_policy.py:322-405`. `test_llm_subgraph_budget_invariant.py`가 LLM 경계 7지점에 전체 그래프 미주입 동결. **depth≤2는 유예** — §3 [유예 B] |
| 9 파일·ID 정책 | Canonical Stable ID | ✅ | part9 review 시정 완료분: `math.<area>.<slug>` 재-ID·locales 분리·`ids.yaml` registry, 거버넌스 6종 동결(`test_id_registry_governance.py` 등) |
| 10 구축 로드맵 | 10단계 순서 준수 | ✅ | 단계 건너뛰기 없음. 빌드 하네스 `stage_order`가 S0~S5→E1~E6 순서를 알고리즘 강제 (E축 entry_gate 하드락) |
| 11 AI 협업 | 구조 붕괴 감지기로 사용 | ✅ | 본 감사 자체가 프로토콜 이행. 빌드 하네스 ARCH-NN 반복 태스크로 제도화 |
| 12 실패 방지 | 8대 원칙·7대 붕괴 감시 | ✅ | 거버넌스 테스트 18종 상주 (§4 인벤토리). 붕괴 연쇄 1단(노드 폭발)~3단(순환참조)이 CI에서 hard-block |

**이중 truth source (최우선 점검 단계 3)**: 런타임 축은 **해소 완료** — 원자 단일 truth source, 구 437 개념그래프는 `legacy_snapshot {readonly, non_runtime, audit_only}` 격하 (S0-4a~4d, `test_legacy_snapshot_governance.py` AST 스캔 3불변식: 런타임 437 reader 0·audit 화이트리스트·lifecycle 마커). **잔여는 입도 축** — 개념(437)↔세부개념 원자(2,697)의 세분도 통합은 전문가 검수 소관 별도 과제 (part2 review 기존 판정 유지, 도메인 파트너 게이트 `G-domain-partner`와 연동).

**prerequisite DAG (단계 3-관계)**: `validate.py:134-196` 3색 DFS 사이클 탐지 → `prerequisite_cycle` **hard error** + 런타임 재귀 CTE `max_depth` 이중 방어 (`prerequisite_recommendation.py`). 준수.

## 2. 지적 사항

### [갭 A] L5 클라이언트 무-수학로직 — 규범만 존재, 자동 게이트 부재
- CLAUDE.md("수학 로직을 클라에 넣지 않는다", 슬라이스 89)는 규범 문서로만 강제됨.
- import-linter(`src/backend/pyproject.toml:158` `api > l6 > l5 > l4 > l3 > l2 > l1 > schema`)는 **Python 패키지만** 검사 — Flutter(`src/mobile`)·웹(`src/web`)은 계약 밖.
- s1_structure_audit Q8의 "subject 하드코딩 0"은 수동 확인이었고 회귀 방지 게이트가 없음.
- **판정**: 위반 사례는 미발견이나, 재발 방지 장치 부재 = 갭. → 상환 태스크 `ARCH-10-client-mathlogic-gate` 등록 (Dart 측 거버넌스 테스트 또는 CI 소스 스캔: 채점·판정·수식 동치 로직 패턴의 클라 유입 차단).

### [유예 B] Minimal Subgraph depth≤2 능동 가드 부재 — 문서화된 의도적 유예
- 현 LLM 소비처(`wh1_llm_policy._build_prompt`)는 그래프 traversal을 하지 않으므로 depth 축이 무관 (docstring 명문).
- `l2/reasoning_subgraph.py` canonical seam 미생성. 해제 트리거 계약(part8 review rev.2): **WH-1 튜터링 루프가 그래프 traversal을 도입하는 슬라이스에서 depth≤2·visited set·timeout·token budget guard를 함께 도입**.
- 주의: `MAX_PREREQUISITE_DEPTH=5`(`prerequisite_recommendation.py:98`)는 *선수 추천 traversal* 예산으로 LLM 컨텍스트 예산과 다른 축 (코드 주석으로 구분 명문화되어 있음 — 혼동 위반 아님).
- **판정**: 위반 아님. 트리거가 사람 기억에 의존하지 않도록 백로그로 이관 → `ARCH-11-subgraph-depth-guard` 등록 (depends_on: coach→하네스 수렴 = traversal 소비처 착륙 지점).

### [정비] 스냅샷 수치 stale
- `build_checkpoint_questions.md` 표: 403노드/1,837원자 → 실측 **437노드 / 원자 2,697(세부 1,837)**. 본 감사에서 갱신.

## 3. 거버넌스 테스트 인벤토리 (18종 — 감시망 현황)

**backend (15)**: gate3 학생응답 검증 · crosswalk 이전 · problem_bank 저작권 · edge 관계(PREREQUISITE 단일 적재) · 임베딩 namespace(4갈래·subject 축 = 다과목 대비 완료) · 5노드 연결 · formula(P5a) · legacy_snapshot(S0-4) · misconception enrichment(P4a) · 노드 입도 · problemtype(P3) · skill(P2a) · strategy(P6a) · 동등문제 수용(저작권) · scene DSL 계층
**data-pipeline (3)**: ID registry · locales · 관계 어휘
**예산 계열 (파일명에 governance 없음)**: `test_llm_subgraph_budget_invariant.py` · `test_prerequisite_depth_budget.py` · `test_wh1_llm_policy.py`(3중 상한)

## 4. 다음 회차(ARCH-02) 점검 초점

1. [갭 A] `ARCH-10` 이행 확인 — 클라이언트 게이트가 실제 CI red를 낼 수 있는지
2. 입도 통합(437↔2,697) 진척 — `G-domain-partner` 게이트 해소 여부와 연동
3. Part 7 9블록 잔여 축(학생모델·인터랙션 다양성) 진척
4. E축 대비: 검증기 plugin·커리큘럼 오버레이 확장 불변식 4종 (e_axis_v1 §5 항목) 사전 점검
