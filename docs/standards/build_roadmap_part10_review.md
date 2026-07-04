# 구축 플레이북 Part 10(구축 로드맵) 설계-준수 검토

> **상태**: 검토(review) + 단계8 불변식 코드 동결(governance) · **계층**: 횡단(로드맵·순서·경계 규율) · **작성일**: 2026-07-03
> **검토 대상**: `docs/standards/playbook_part_review_questions.md` **Part 10 — 구축 로드맵**
> (법칙: *10단계 순서 준수 · MVP→중급→최종 · Curriculum 역추적 분해*)
> **상위/관련**: `docs/standards/build_checkpoint_questions.md`(10단계 **진행** 축·본 문서는 **설계-준수** 축) ·
> `math_dsl_risk_register.md`(§2 Q10-⑧ "LLM 전체 그래프 미열람") · `current_phase_checklist.md`(보류 대장 원천) ·
> `subject_expansion_readiness.md`(보류 대장 §8) · `tests/backend/l1/test_five_node_connectivity_governance.py`(핵심5노드 동결)

---

## 0. 요지 (BLUF)

Part 10의 3대 검문을 **실코드로 재확인**한 결과 **모두 준수(갭 없음)**다. 유일한 잠재 쟁점이던
단계8 "LLM 전체 그래프 노출"은 현행 코드상 **잠재/미래 리스크지 현존 결함이 아니다**(graph→LLM
컨텍스트 빌더 부재·소비처 없음). 그 경계가 회귀로 무너지지 않도록 **Q10-⑧ 불변식을 거버넌스
테스트로 CI 동결**(`test_llm_subgraph_budget_invariant.py`)했고, 수치 상한 guard(builder)는 소비처
등장 트리거까지 보류로 재분류했다. 코드 변경은 최소(주석 1곳·거버넌스 테스트 2건), 나머지는
경계·순서 규율의 명문화다.

---

## 1. 3대 검문 판정

### ① 10단계 순서를 건너뛰지 않았나 — **준수**
- 순서(10-1): 1 철학 → 2 기능분리 → 3 개념구조화 → 4 오개념 → 5 시각화 → 6 UI DSL → 7 렌더링 →
  8 AI튜터 → 9 평가 → 10 자동화. 실코드 상태: 1·2 완료, 3·4·5·9 구현, 6·7·8·10 진행. 역전 없음.
- "오개념 구조화(4) 전에 AI튜터(8) 고도화" 유형의 역전 신호 점검: **위반 아님**. AI튜터
  (`api/coach.py`·`harness/wh1_*`)는 오개념 canonical ID의 미수렴분(kebab 30 / M-id 839)을 **하드
  소비하지 않는다** — reactive 매칭(`l4/misconception`)·`PrerequisiteGap`·mastery 등 *구조 신호*만
  받는다. 즉 오개념 정체성 수렴(잔여=사람 검수)과 AI튜터 진행은 결합돼 있지 않다.
- 다만 단계3의 **개념그래프(403·437) ↔ 원자그래프(1,837·2,697) 이중 진실 원천**은 "추적 항목"으로
  유지한다(granularity governance 테스트가 병존을 의도 동결). 유지보수 지옥 징후는 아직 없음(동기화
  규칙이 governance로 강제)이나, 증분 편집 소비처 생길 때 canonical 동기화 게이트를 재검토한다.

### ② MVP 경계를 지키나·최종단계 기능을 조기 당기지 않았나 — **준수**
- MVP 경계(10-2): 입력→tokenizer→Pratt→basic AST→normalize→renderer + 핵심5노드. 현 단계는 이
  경계 내부(입력 정규화=Part 4 마감·핵심5노드=governance 동결)이며, **중급/최종 기능을 앞당기지
  않았다**:
  - `multimodal AST`(최종): 코드의 `multimodal`은 `l3/router.py:409` **OCR 비전 라우팅 reason**뿐 —
    AST가 아니다.
  - `step reasoning`·`semantic feedback`·`adaptive interaction`·`장기 학습 메모리`(최종): 코드 부재.
  - **자기진화(Lean4 Tier3)**·**Manim 동영상**: 런타임 미도입 — `whs/*`·`l3/*`·`schema/*`의 "Lean4/Manim"
    언급은 전부 *docstring 보류 기록*이고 **능동 import 0**(게이트 `test_build_roadmap_boundary_gate.py`).
  - **WH-S `whs/self_evolution.py` disambiguation**: 이는 *오프라인 솔버 SFT*(verified 풀이→학습 레코드·
    순수 코어)로, 보류된 **DSL/Lean4 자기진화와 별개**다(경계 명문화·조기당김 아님).
- **저장 진화**(10-2)도 정합: 현재 YAML 저작 → PG/Neo4j 런타임(중기). 최종 Graph 확장은 미도입.

### ③ 교육과정 문장을 그대로 노드화하지 않고 7축으로 분해하나 — **준수(4대 실패모드 전부 PASS)**
Part 10-3 이차함수 루브릭으로 **실코퍼스**(`data/corpus/atom_graph_v1`·`concept_graph_v1`)를 감사:

| 실패모드 | verdict | 근거(실 id/필드) |
|---|---|---|
| ① 문장 verbatim 노드화 | **PASS** | node명=`9수02-21-1 이차함수의 개념` 류 구조 라벨. 성취기준 문장은 `standard_codes`·`핵심명제`(provenance상 **redacted**)로 분리 — 노드 정체성 아님 |
| ② 시각화-렌더러 결합 | **PASS** | `CanvasParabolaNode`류 부재. `schema/visualization.py` `Visualization`=`extra="forbid"`·픽셀/셰이더 필드 0. `VisualizationType`(`interactive_graph_2d` 등)=선언적, 렌더러명 미포함 |
| ③ Skill≠Concept 혼합 | **PASS** | `10기수1-02-05-2 꼭짓점이 최대최소`(개념) vs `10기수1-02-03-2 꼭짓점 좌표 읽기`(절차) 물리 분리. `CognitiveType`=속성 enum·`SkillNode`/`FormulaNode`/`ProblemTypeNode` 클래스 금지(governance) |
| ④ dependency 무시 | **PASS** | 선수 체인 실재: `함수→이차함수 개념→그래프성질→이차방정식관계→최대최소` (atom 선수엣지·concept `prerequisite`·`prerequisite_concept_ids` 양측) |

**7축→물리표현 매핑**: Concept·Misconception=실 노드 / Skill=`CognitiveType` 5종 enum / ProblemType·
Assessment=`Problem` schema·`atom_probe` / Visualization=schema / Interaction=`Graph2dSpec.parameters` /
Formula=**의도적 보류**("Formula 먼저 만들지 않는다"·`test_five_node_connectivity_governance.py` 동결).
→ "우선 5노드·Formula는 마지막" 규율 준수.

---

## 2. 10단계 순서 재확인 표 (실코드 교정)

| 단계 | 영역 | 상태(실코드 재확인) |
|---|---|---|
| 1 철학 · 2 기능분리 | 정체성·7계층 | ✅ 완료 |
| 3 개념구조화 | 개념 403/437·원자 1,837/2,697 (이중 진실원천=추적) | 🟢 구현 |
| 4 오개념 | 839 카탈로그+판정(canonical 수렴 잔여=사람 검수) | 🟢 구현 |
| 5 시각화 | Graph2dSpec·`Visualization`(`extra="forbid"`) | 🟢 구현 |
| 6 UI DSL · 7 렌더링 | LearningScene·Flutter/web 계산기 | 🟡 진행/프로토타입 |
| 8 AI튜터·Context | L3 라우터·WH-1 — **전체그래프 미열람 동결**(잠재 리스크·현존 결함 아님) | 🟡 진행 |
| 9 평가·개인화 | BKT·IRT·mastery·학습경로 | 🟢 구현 |
| 10 자동화·확장 | 동등문제·물리 확장 준비(S0~S3) | 🟡 진행 |

---

## 3. MVP 경계 보류 대장 (단일화·재검토 트리거)

흩어져 있던 최종/중급 기능 보류를 한 표로 모은다. 조기당김 금지의 이면 = **각 항목의 착수
트리거를 못 박는 것**. (원천: `current_phase_checklist.md` A부·`subject_expansion_readiness.md` §8·
`math_dsl_risk_register.md` §2. 본 표는 대조·단일 인덱스.)

| 보류 항목 | tier | 재검토 트리거 |
|---|---|---|
| **자기진화 (DSL/Lean4 Tier3)** | 최종 | WH-S 단계검증 코퍼스 성숙 + 증명형 문제 소비처 등장 (risk_register Q9) |
| **Manim 동영상 렌더** | 최종 | 정적 그래프로 Phase 1 불충분 판명 + 시각화 3대핵심 약화 계측 시 |
| **multimodal AST** | 최종 | 손글씨/그래프 입력을 AST로 통합하는 소비처 등장 (현재 OCR은 비전 라우팅으로 충분) |
| **WH-1 전략단계 (Lv2~3)** | 최종 | Polya 답미루기 지표 안정 + 전략 코칭 A/B 근거 확보 |
| **LLM subgraph builder (예산 guard)** | 중급 | **graph→LLM 컨텍스트 소비처 최초 등장** — 그때 canonical seam으로 신설(§4) |

---

## 4. 단계8 Q10-⑧ 불변식 코드 동결 (핵심 결정)

- **현행 사실**: graph→LLM 컨텍스트 빌더가 **없다**. 모든 LLM 호출은 `LLMProvider.generate(prompt:
  str, system: str, …)` 문자열 계약을 지나며, 프롬프트 빌더는 스칼라(`concept: str`)·단일 reactive
  `Misconception`만 받는다. `l2/prerequisite_recommendation.py`의 `MAX_PREREQUISITE_DEPTH=5`는 *그래프
  traversal 깊이 예산*이지 LLM 컨텍스트 예산(max_nodes·max_tokens)이 아니다.
- **결정**: Q10-⑧("LLM 전체 그래프 미열람")을 **거버넌스 테스트로 CI 동결** —
  `tests/backend/l3/test_llm_subgraph_budget_invariant.py`가 (a) LLM 경계에 `Concept`/`ConceptEdge`/`Atom`
  **컬렉션** 주입 금지, (b) traversal 예산 단일 출처(`api/me MaxDepth`가 `le=MAX_PREREQUISITE_DEPTH` 공유)를
  동결한다. 이것이 "코드 강제"의 정당한 실현(CI 게이트·Part 6 동결 선례).
- **수치 상한 계약**(depth≤2·max_nodes~12·max_tokens~3000)은 **문서 계약**으로만 명문화하고, 능동
  guard를 박는 `l2/reasoning_subgraph.py` builder는 **소비처 트리거까지 보류**(§3). 근거: (a)
  `math_dsl_risk_register.md`가 "LLM subgraph 예산"을 미채택(premature)으로 기록, (b) 10-2 tier가
  subgraph/Context를 중급/최종으로 분류 → **지금 builder 신설은 Part 10 check② "조기당김"에 저촉**.
- **risk_register 재분류**: Q10-⑧의 *불변식 동결 몫*을 미채택 목록에서 §4 동결 표로 이관(테스트
  좌석 명시). builder(능동 예산 guard)는 미채택 유지 + 트리거 명문화.

---

## 5. 메타 질문 — 7대 붕괴 연쇄 관점 (인지 행동 기준)

- **노드/관계 폭발**: 핵심5노드·Edge 5~8·Formula 보류·`similar_to` traversal 배제로 억제(Part 2·3
  검토 완결). 이차함수 감사가 과세분·verbatim 노드화 부재를 실증.
- **AI 추론 실패(attention dilution)**: 본 Part의 최대 위험. 방어는 "전체 그래프 미열람" — *인지
  행동*으로 보면, 튜터가 학생의 *한 수*에 대응할 때 필요한 것은 전체 지식지도가 아니라 *지금 막힌
  선수·활성 오개념 가설*뿐이다. 현 구조(구조 신호만 소비)가 이 인지 행동에 이미 정렬돼 있고,
  불변식 동결이 그 정렬을 회귀로부터 지킨다.
- **유지보수 지옥**: 개념↔원자 이중 진실원천이 유일 후보 — governance 동결로 봉인, 증분 편집
  소비처 등장 시 재검토(premature 방지).
- **교육 일관성 붕괴**: 위 방어의 최종 귀결로서, 조기당김(최종기능 선점)이 MVP 인지 흐름(입력→
  분해→진단→소크라테스→오개념)을 흐리지 않도록 보류 대장 트리거가 규율.

---

*출처: WhyMath 구축 플레이북 v1.0 Part 10 · 사용자 제공 10-1/10-2/10-3(2026-07-03).*
