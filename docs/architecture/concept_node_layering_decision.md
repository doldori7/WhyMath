# ADR — ConceptNode 계층 분리 · 5노드 구성 · 노드 입도 결정

> **상태**: 채택(2026-07-02) · **범위**: 개념그래프 identity 노드(`Concept`)·5노드 모델·입도
> **연관**: 플레이북 Part 2(노드 설계) · CLAUDE.md 8대 구조원칙 #1(Concept Purity)·#2(Layer
> Separation) · `docs/standards/part2_node_design_review.md`(검토 판정) ·
> `docs/architecture/math_dsl_remediation_design.md`(curriculum Overlay 이관 선례)

이 문서는 구축 플레이북 **Part 2. 노드 설계** 검토(2026-07-02)에서 확정한 세 결정을 기록한다:
① ConceptNode 4계층 분리, ② 5노드(Concept→Misconception→Skill→ProblemType→Visualization)를
전용 노드 폭증 없이 구성하는 방식, ③ "독립 오개념 발생 단위" 입도 기준.

법칙(플레이북 Part 2): *노드 = 학생 사고가 바뀌는 최소 단위(= 독립 오개념 발생 단위). 우선
5노드, Formula는 마지막.*

---

## 1. ConceptNode 4계층 분리 (identity / semantic / pedagogy / visualization)

identity 노드(`data_pipeline.concept_graph.models.Concept`)의 필드는 아래 4계층으로 귀속한다.
**pedagogy·오개념·렌더러·프롬프트·임베딩·교육과정은 노드에 내장하지 않는다**(Concept Purity).

| 계층 | 노드 필드 | 원칙 |
|---|---|---|
| **identity(식별)** | `concept_id`·`source_id`·`aliases`·`name_ko/en/ja`·`domain` | 개념을 유일 식별하는 순수 정체성 |
| **semantic(의미)** | `difficulty_tier`·`standard_codes`·`prerequisite_concept_ids`·`ccss_code`·`grade_band_hint`·`review_status` | 개념의 의미 속성("핵심만 노드, 나머지는 속성") |
| **pedagogy(교수학)** | *노드 비내장* — `misconception_codes`·`visualization_card_keys`(참조 키만) | 오개념·설명·은유는 별도 계층(ConceptContent·MisconceptionCatalog)이 단일 진실 |
| **visualization(시각화)** | *노드 비내장* — `visualization_card_keys`(참조 키만) | 렌더 명세 실체는 L5(`schema/visualization.py`) |

**참조(reference) vs 내장(embed) 구분**: `misconception_codes`·`visualization_card_keys`는 실체를
담지 않는 *다리(참조 키)*라 순수성 위반이 아니다. 반대로 자유텍스트 오개념(`misconception_text`)·
은유 본문·설명은 *내장*이라 금지 — pedagogy 계층으로 외부화한다.

**2026-07-02 순수성 수정**: 자유텍스트 오개념 `misconception_text`를 노드에서 제거했다(삼중
중복 — `ConceptContent.misconception`·`MisconceptionCatalog` 839건과 겹침·오염 위험). 코드 동결:
`tests/data_pipeline/concept_graph/test_concept_node_purity.py`.

**Stage B 잔여 부채**: `metaphor`·`accepted_expressions`(pedagogy)는 의미검색 임베딩
(`l1/concept_graph/embedding.py`)·노드 프로젝션(`node_projection.py`)이 아직 소비하므로 노드에
잠정 잔류한다. `ConceptContent`(code 키) 크로스워크 완료 후 별도 이관한다 — 그때 순수성 테스트의
`_STAGE_B_PEDAGOGY_DEBT` 집합을 비운다. Stage B를 크로스워크 미완 상태로 착수하면 벡터 입력이
소실되므로 **크로스워크 완료를 게이트**로 둔다.

---

## 2. 5노드 구성 — 전용 노드 폭증 없이 (anti-explosion)

플레이북은 "우선 5노드(Concept→Misconception→Skill→ProblemType→Visualization)"를 요구한다.
CLAUDE.md는 동시에 "수학 전체를 완벽 모델링 금지 — 핵심만 노드, 나머지는 속성/AI 생성"을 강제한다.
두 원칙을 함께 지키기 위해, **모든 노드 종을 별도 테이블로 승격하지 않는다**:

| 노드 | 실현 방식 | 근거 |
|---|---|---|
| **Concept** | `Concept` 모델·`concept_graph_v1` 코퍼스(437) | identity 노드(정본) |
| **Misconception** | `MisconceptionCatalog`(839)·런타임 kebab 카탈로그(`l4/misconception/catalog.py` 30)·별도 DB | 오개념 독립 DB(원칙 #6) — Concept은 `misconception_codes`로 참조 |
| **Skill** | **`CognitiveType` enum 속성**(`schema/enums.py` — DEFINITION/THEOREM/TECHNIQUE/PATTERN/VISUAL_REASONING) | 인지 유형은 개념의 *속성*이지 별도 노드가 아니다 — 노드화 시 폭발 |
| **ProblemType** | **`Problem` 스키마**(`schema/problem.py`)·`problem_concept` N:M(`ConceptRole`) | 문항 유형은 문항 스키마로 표현 |
| **Visualization** | **`Visualization` 선언 명세**(`schema/visualization.py`) | Concept은 `visualization_card_keys`로 참조 |

**Formula는 전용 노드로 만들지 않는다**(플레이북 "Formula는 마지막" 실패 경로 회피). 공식은
개념의 속성/AI 생성으로 다루고, 노드 승격은 하지 않는다.

**동결**: `tests/backend/l1/test_five_node_connectivity_governance.py` — 5노드 대체 표현 존재·
Concept↔Misconception/Visualization 참조 다리 존재·`FormulaNode`/`SkillNode`/`ProblemTypeNode`
클래스 **부재**를 소스 스캔으로 동결한다. 누가 전용 노드를 승격하면 red가 되어 이 ADR 재검토를
강제한다.

**재검토 트리거**(승격이 정당해지는 조건): Skill/ProblemType/Formula가 *독립적으로 오개념을
발생시키고*·다수 개념에 걸쳐 재사용되며·속성 표현으로는 관계(엣지)를 못 맺는 상황이 실측될 때.
그 전까지 승격은 premature(노드 폭발 → 관계 폭발 붕괴 연쇄).

---

## 3. 노드 입도 — "독립 오개념 발생 단위"

노드 입도는 **"함수"(너무 큼)** 도 **"기울기의 x증가량"(폭발/과세분)** 도 아닌, **독립적으로
오개념이 발생·진단·교정되는 최소 단위**여야 한다.

**현황(이중 truth source)**: 개념그래프 `concept_graph_v1`(437노드·3단 ConceptLevel)와 원자그래프
`atom_graph_v1`(2,697노드·NodeLevel 단원/소단원/세부개념)가 병존한다.
`docs/standards/build_checkpoint_questions.md` 단계3이 이 이중 truth source를 최우선 유지보수
리스크로 지목했다.

**측정 결과(2026-07-02)**: 원자그래프 '세부개념' 레벨 1,837노드는 **전부 독립 오개념
(`misconception`)을 보유(100%)** — 세부개념 원자는 Part 2 §1 법칙("독립 오개념 발생 단위")을
만족한다. 즉 현재 원자 입도는 과세분되어 있지 않다.

**결정**: 대규모 재분할·통합은 전문가 검수 소관이라 즉시 코드로 손대지 않는다. 대신 입도 기준을
명문화하고, 회귀를 **감지**하는 거버넌스 테스트만 둔다:
`tests/backend/l1/test_node_granularity_governance.py` —
- 이중 truth source 노드 수(437·2,697) 스냅샷 동결(무단 재분할·중복 증식 감지).
- 세부개념 원자 100% 오개념 커버리지 불변식(오개념 없는 세부 노드 유입 = 과세분 후보 → red).

---

## 부록 — 관련 코드·문서

- 순수성 동결: `tests/data_pipeline/concept_graph/test_concept_node_purity.py`
- 5노드 연결·anti-explosion 동결: `tests/backend/l1/test_five_node_connectivity_governance.py`
- 입도 감지: `tests/backend/l1/test_node_granularity_governance.py`
- 노드 모델: `src/data-pipeline/data_pipeline/concept_graph/models.py`
- 검토 판정 리포트: `docs/standards/part2_node_design_review.md`
