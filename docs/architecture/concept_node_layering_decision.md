# ADR — ConceptNode 계층 · 노드 taxonomy · 노드 입도 결정

> **상태**: 채택(2026-07-02) → **개정(2026-07-03) — 리치 Part 2 스펙 전면 채택** · **범위**:
> 개념그래프 노드·12노드 taxonomy·입도 · **연관**: 플레이북 Part 2 · CLAUDE.md 8대 구조원칙 ·
> `docs/standards/part2_node_design_review.md` · `/root/.claude/plans/part-2-scalable-lobster.md`(로드맵)

법칙(플레이북 Part 2): *노드 = 학생 사고가 바뀌는 최소 단위(= 독립 오개념 발생 단위). 우선
5노드(Concept→Misconception→Skill→ProblemType→Visualization), Formula는 마지막.*

---

## 0. 2026-07-03 개정 — 리치 Part 2 스펙 전면 채택

초판(2026-07-02)은 anti-explosion 근거로 **Skill=속성·ProblemType=스키마·Formula 비노드**를 채택하고
ConceptNode를 **4계층**으로 분리했다. 재검토(2026-07-03)에서 리치 Part 2 스펙(12노드 taxonomy·
9계층 ConceptNode·7계층 MisconceptionNode·SkillNode 1급화·cognitive-action ProblemTypeNode·canonical
FormulaNode)과 대조한 결과 상당한 갭이 확인됐고, **사용자가 전면 채택을 결정**했다.

**이 개정이 반전하는 것**:
- 초판 §2의 "전용 노드 폭증 없이"(Skill/ProblemType/Formula 비승격) → **canonical 단위 노드 승격**.
- 초판 §1의 4계층 → **9계층**(semantic을 "노드 핵심"으로 승격).
- Stage B(metaphor·accepted 노드 외부화) → 리치 기준 이 둘은 semantic(intuition·representations)이라
  **노드로 복원**(Phase 1). 단 self-authored 한정.

**반전 불가(CLAUDE.md 협상 불가 — 전면 채택도 이 안에서)**:
- anti-explosion: 노드는 **canonical·원자 단위**로만 승격(무분별 증식 금지).
- 관계 타입 5~8개: **신규 엣지 타입 0** 목표 — 노드간 연결은 참조 키 우선.
- redaction(우선순위 #2): 성취기준·교과서 *본문* 근접 텍스트는 노드 비내장. **semantic은
  self-authored 텍스트만**.
- 오개념 독립 DB(#6)·오개념 preload 금지·임베딩 별도 store.

> 핵심 화해축: 리치 스펙은 *무엇이 노드에 속하는지의 재정의*이지 anti-explosion·redaction 폐기가
> 아니다. "계층 이름은 9개지만 **물리적 내장은 identity + semantic(self-authored)뿐**, 나머지 7계층은
> 참조/투영"으로 화해한다.

구현은 `part-2-scalable-lobster.md` 로드맵의 **Phase 0(본 문서 개정·판정) → Phase 1~6**으로 진행.

---

## 1. ConceptNode 9계층 (identity·semantic 내장 / 나머지 참조·투영)

리치 9계층을 채택하되, **물리적 내장은 identity + semantic(self-authored)에 한정**하고 나머지는
참조 키/투영으로 둔다(Concept Purity·redaction 유지).

| 계층 | 내장 여부 | 필드(현재/Phase 1 신설) | 원칙 |
|---|---|---|---|
| **identity** | 내장 | `concept_id`·`source_id`·`aliases`·`name_*`·`domain` (+`abstraction_level` 후속) | 순수 정체성 |
| **semantic** | **내장(self-authored만)** | Phase 1 신설: `core_meaning`(자체 1줄)·`intuition`(=metaphor 복원)·`representations`(=accepted 복원). `formal_definition_ref`는 참조 | 리치 "가장 중요" — 단 성취기준 본문 금지 |
| **pedagogy** | 참조 | `prerequisite_concept_ids`. 설명·explainLike는 `ConceptContent` | 선수관계만 노드 |
| **visualization** | 참조 | `visualization_card_keys`(참조 키) | 렌더 실체는 L5 |
| **assessment** | 참조 | `difficulty_tier`·`ccss_code` + Phase 1 `assessment_ids` | 난이도 스칼라 + 참조 |
| **misconception** | 참조 | `misconception_codes`(카탈로그 참조) | 실체는 독립 DB(#6) |
| **cognition** | 부분 내장 | `cognitive_type`(enum) + Phase 1 `behavior_skills`(참조)·`cognitive_load`·`abstraction_required`(스칼라) | 스칼라/참조만·자유텍스트 금지 |
| **graph_links** | 별 엔티티 | `ConceptEdge`(7종 relation) + `prerequisite_concept_ids` 캐시 | 리치보다 풍부 |
| **ast_binding** | 참조 | Phase 1 `formula_refs`(FormulaNode 참조·초기 dangling) | AST 참조만(엔진 미내장) |

**참조 vs 내장 구분**: 참조 키(`misconception_codes`·`visualization_card_keys`·`formula_refs`·
`behavior_skills`)는 실체 미보유 다리라 순수성 위반이 아니다. 자유텍스트 오개념·렌더 명세·formula
AST·성취기준 본문은 내장 금지.

### Stage B semantic 복원 판정 (Phase 0 핵심 산출물)
- `metaphor`·`accepted_expressions`는 `ConceptContent`가 **전량 와이매스 자체작성**(self-authored)이라
  **redaction 안전 → 노드 semantic 계층으로 복원 가능**(Phase 1: intuition·representations).
- `description`·`formal_definition`·`intuitive_explanation`은 성취기준 본문 근접 위험 → **노드 복원
  금지·참조만**. formalDefinition은 `concept_content.formal_definition_internal`(자체창작·학생 비노출)을
  **참조 키**로 연결.
- 결론: Stage B의 "노드 순수화"는 유지하되, 그 중 self-authored 안전 필드(metaphor·accepted)는
  semantic으로 되돌린다. 순수성 테스트의 `_FORBIDDEN_NODE_FIELDS`↔`_SEMANTIC_FIELDS` 이동은
  **모델 필드 복원과 원자적으로(Phase 1 PR)** — Phase 0은 red 구간을 만들지 않는다.

### Phase 1b 완료 — 런타임 Concept 본문·오개념 4컬럼 청산 (2026-07-03·10금지 잔재 해소)
- backend 런타임 `Concept`(schema+ORM)이 보유하던 `description`·`formal_definition`·
  `intuitive_explanation`(TEXT×3)·`common_misconceptions`(JSONB)을 **제거**했다(Alembic
  `f0a1b2c3d4e5` drop×4·up/down 대칭). 넷 다 런타임 소비처 0·전량 NULL/`[]`인 죽은 컬럼이었다.
- 이로써 "노드에 넣지 말 10가지"의 마지막 런타임 잔재(본문 근접 서술·자유텍스트 오개념)가 정본
  노드·backend 양쪽에서 해소됐다. 재유입은 `test_concept.py::_FORBIDDEN_NODE_FIELDS`(4필드 추가)와
  신규 schema↔ORM 필드 정합 동결 테스트가 차단한다. 정본: semantic(intuition·representations)·
  `formal_definition_ref`(참조)·독립 오개념 카탈로그(#6).

### 이력(2026-07-02 Stage A/B — 초판)
- Stage A: 자유텍스트 오개념 `misconception_text` 제거(삼중 중복·오염 위험·마이그레이션 0).
- Stage B: `metaphor`·`accepted_expressions` 제거 → ConceptContent 이관(재임베딩 0·Alembic
  `c7d8e9f0a1b2`). **본 개정에서 이 둘은 semantic으로 복원 예정**(misconception_text는 독립 DB 유지).

---

## 2. 노드 taxonomy — canonical 단위 승격 (초판 anti-explosion 반전)

리치 12노드를 채택하되, 각 노드는 **canonical·mastery 독립추정 가치** 기준을 통과할 때만 승격한다
(무분별 증식 금지). 초판이 "premature"로 미룬 승격을, 재검토 트리거가 충족됐다고 보고 실현한다.

| 노드 | 초판 | 전면 채택(로드맵) | 승격 정당화 기준 |
|---|---|---|---|
| Concept | ✅ | ✅ 9계층화(P1) | — |
| Misconception | ✅ 독립 DB | ✅ 7계층화(P4) | 오개념 독립 DB(#6) |
| **Skill** | 속성(enum) | **✅ 1급 노드(P2a 완료)** | mastery 독립추정 가치·행동영역 canonical |
| **ProblemType** | 스키마 | **✅ 1급 노드(P3 완료)** | cognitive-action canonical(≠surface SignaturePattern) |
| Visualization | 선언 명세 | ✅ 유지·계약 정합 | "무엇을"만·"어떻게" 금지 |
| **Formula** | 비노드 | **canonical-only 노드(P5)** | canonical 표현만(변형 노드화 금지)·SymPy 검증커널 유지 |
| Proof/Theorem | 없음 | TheoremNode≠ProofNode(P6) | 정리≠증명 분리 |
| Curriculum | Overlay | ✅ `curriculum_entry` | Overlay 유지 |
| Assessment | 스키마 | ✅ `schema/assessment.py` | — |
| Hint | YAML만 | ORM 신설(P6) | graded·답미루기 게이트 |
| Strategy | 엔진 상태 | 노드화(P6) | 폐쇄 소수집합 |
| UIInteraction | 이벤트 | 지식노드 아님·유지 | runtime concern |

**관계 폭발 방지**(협상 불가): 새 노드종 승격 시 **신규 엣지 타입 0** 목표. concept↔skill·
misconception↔skill·concept↔formula 연결은 *참조 키*와 기존 `prerequisite`/`application`만 사용.
물리 엣지 테이블 증식을 각 Phase PR의 거버넌스 테스트로 상한.

**동결 반전**: `tests/backend/l1/test_five_node_connectivity_governance.py`의 `_FORBIDDEN_NODE_CLASSES`
(SkillNode/ProblemTypeNode/FormulaNode 부재 동결)는 각 노드를 실제 추가하는 Phase PR에서 하나씩
제거하고 "승격된 노드 존재+연결" positive 테스트로 반전한다(red 구간 없이). **Phase 2a(2026-07-03)로
SkillNode를 이 집합에서 제거**했다 — `_FORBIDDEN_NODE_CLASSES=("FormulaNode","ProblemTypeNode")`로
축소하고 `test_skill_is_first_class_node`(SkillNode 모델·ORM + BehaviorArea 6종)로 반전. 신규 거버넌스
`test_skill_governance`가 BehaviorArea 6종 폐쇄·backend↔pipeline enum 값 정합·신규 엣지 타입 0을 동결.
**Phase 3(2026-07-07)로 ProblemTypeNode를 제거** — `_FORBIDDEN_NODE_CLASSES=("FormulaNode",)`로 축소하고
`test_problem_type_is_first_class_node`(ProblemTypeNode 모델·ORM)로 반전. 신규 거버넌스
`test_problemtype_governance`가 신규 엣지 타입 0·**ProblemType≠SignaturePattern 구별**·cross-corpus
dangling 0을 동결. Formula만 이 집합에 남는다(P5 승격 대기).

### Phase 3 완료 — ProblemType 1급 노드 승격 (2026-07-07)
- **cognitive-action canonical 노드**(≠surface SignaturePattern): ProblemType을 `Problem` 스키마
  표현에서 1급 노드로 격상. **신규 enum 0(D1)**: cognitive-action 축은 이미 `BehaviorArea`(Phase 2a)라
  중복 archetype enum을 두지 않고, 유형이 exercise하는 스킬(`behavior_skills`·skill_graph_v1 참조·≥1개)로
  "무슨 사고를 요구하는가"를 표현한다(P3→P2 참조·신규 엣지 타입 0).
- **data-pipeline `problem_type_graph`**(models·transform·validate·CLI) + 정본 코퍼스
  `problem_type_graph_v1`(17 유형·6 family·자체작성·ai_estimated). **backend `problem_type_node`**
  (PG 프로젝션·problem_type_id 키·**native enum 없음**·마이그레이션 `f0a1b3c4d5e6`).
- **Problem↔ProblemType 연결은 Phase 3b로 분리(D2)**: 문제는 L3 동적 생성이라 연결을 채울 생산자/소비처가
  없어 지금 매핑/컬럼/junction은 dead code("소비처 없는 추상 미도입"·2a→2b 분리 선례). 분리 불변식은
  매핑 없이 구조로 단언(노드에 surface 필드 부재·SignaturePattern 미import·id 공간 disjoint).

### Phase 2a 완료 — Skill 1급 노드 승격 (2026-07-03)
- **BehaviorArea 폐쇄 6종**(사용자 결정): `COMPUTE`·`TRANSFORM`·`INTERPRET`·`REPRESENT`·`REASON`·
  `VERIFY`(계산실행·식변형·조건해석·표상·추론·검증). 개념(무엇)과 직교하는 cognitive-action 축.
- **data-pipeline `skill_graph`**(models·transform·validate·CLI) + 정본 코퍼스 `skill_graph_v1`
  (27 스킬·6영역·12 Skill Family·전량 자체작성). **backend `skill_node`**(PG 프로젝션·skill_id 키·
  `behavior_area_enum` native·마이그레이션 `0a1b2c3d4e5f`). 스킬 연결은 참조 키(`prerequisite_
  skill_ids`·개념측 `behavior_skills`)만 — **신규 엣지 타입 0**(검증됨).
- **skill mastery + concept→skill 매핑은 Phase 2b로 분리**: 실측상 전 437개념 `behavior_skills=[]`·
  concept→skill 신호 전무 → mastery를 지금 만들면 데이터 원천 없는 dead code(CLAUDE.md "소비처 없는
  추상 미도입"). 2a는 노드·택소노미·코퍼스·프로젝션·거버넌스만(buildable·testable·P3/P4 unblock).

---

## 3. 노드 입도 — "독립 오개념 발생 단위" (유지)

노드 입도는 **"함수"(너무 큼)** 도 **"기울기의 x증가량"(폭발/과세분)** 도 아닌, **독립적으로
오개념이 발생·진단·교정되는 최소 단위**여야 한다. (리치 스펙의 L3 핵심 인지개념 vs L4 의미 해석
노드 구분 — 예: "기울기"(객체) ≠ "기울기 해석"(의미) — 도 이 기준의 세분화다.)

**현황·측정(2026-07-02)**: 개념그래프 437 + 원자그래프 2,697 이중 truth source. 원자 '세부개념'
1,837노드는 전부 독립 오개념 보유(100%) — 과세분 아님. 재분할은 전문가 검수 소관, 즉시 손대지 않고
`tests/backend/l1/test_node_granularity_governance.py`로 회귀 감지(카운트 스냅샷·100% 오개념 커버리지).

---

## 부록 — 관련 코드·문서
- 로드맵: `/root/.claude/plans/part-2-scalable-lobster.md`(Phase 0~6)
- 순수성 동결: `tests/data_pipeline/concept_graph/test_concept_node_purity.py`
- 노드 승격 동결(반전 대상): `tests/backend/l1/test_five_node_connectivity_governance.py`
- 입도 감지: `tests/backend/l1/test_node_granularity_governance.py`
- 노드 모델: `src/data-pipeline/data_pipeline/concept_graph/models.py`
- 검토 판정 리포트: `docs/standards/part2_node_design_review.md`
