# Math DSL 구조 리스크 레지스터 — 10대 실패모드 분석

> **상태**: 분석(analysis) · **계층**: 횡단(L1·L3·L4·L5) · **작성일**: 2026-06-30
> **정본 상위**: `math_dsl_principles_review.md`(플레이북 검토 — 정합/충돌/공백). 본 문서는 그
> "공백" 절을 *현 코드 근거(파일·라인)*로 구체화한 리스크 레지스터다.
> **근거**: 코드 정밀 조사 3축(L1 원자 그래프 / L5 시각화·LearningScene / 오개념·AST·retrieval), 2026-06-30.
> **범위**: 분석만 — 수정은 *방향*만 제시(작업 항목화는 별도 `/plan`). §5는 이 실패모드를 **목표 규모**
> (전과정·10만+ 문제·오개념 수천·proof system 등)로 전방 투영한 임계점 분석(2026-07-01 추가).

---

## 0. 현재 구조 스냅샷

| 항목 | 현황 | 근거 |
|---|---|---|
| L1 그래프 규모 | 노드 2,697(단원 217·소단원 643·원자 1,837) | `data/corpus/atom_graph_v1/graph.json` |
| 엣지 | 2,213 — **전량 `PREREQUISITE`**, strength **0.8 균일** | `l1/atom_graph/atom_backend_edge.py` |
| Branching | 평균 out 1.25 / max out 7 / max in 4 (희소) | graph.json 실측 |
| 순환 | 현재 **acyclic** — 단 적재 파이프라인에 **cycle 검출 게이트 없음**(self-loop만 차단) | `schema/concept.py:228-299`·`l1/atom_graph/populate.py` |
| 시각화 spec | 렌더러 종속 필드 **0**(no fps/shader/canvas/pixel/color)·`extra="forbid"` | `schema/visualization.py:132-199` |
| LearningScene | 6 element kind·불변식 3종·참조 무결성 게이트·interaction state 누출 **0** | `l4/learning_scene.py:79-312` |
| 오개념 | **3중 표현**: kebab 30종(런타임)·M-id 839종(콘텐츠)·개념노드 JSONB 자유서술 — **FK 없음** | `l4/misconception/catalog.py`·`schema/misconception_catalog.py:9-12`·`schema/concept.py:213` |
| 수식 동치 | 명시 AST 없음 — SymPy(py)·mathjs(js) **각자 파싱·정규화** | `l3/verify_step.py`·`src/web/graphing-calculator/src/lib/graph2dSpec.js` |

**한 줄 평**: *표현 계층은 invariant가 스키마로 박혀 견고, 그래프 위생은 아직 무방비, 오개념
정체성은 이미 부채.* 폭발은 대부분 *시작 전* — 지금이 invariant를 박을 적기다.

---

## 1. 10대 실패모드 위험도

| # | 실패모드 | 위험도 | 핵심 동인 (코드 근거) |
|---|---|---|---|
| 1 | **misconception overlap** | 🔴 높음 | 3중 표현(kebab/M-id/JSONB) FK 없음·방향맹 매처 (`catalog.py`·`misconception_catalog.py:9-12`) |
| 2 | **semantic ambiguity** | 🔴 높음 | 위 + "객체 vs 해석" 미구분·원자 임베딩 신호 얇음 (`atom_graph/embedding.py:81`) |
| 3 | **curriculum inconsistency** | 🟠 중상 | atom code에 개정연도 박힘 (⚠️ "노드 내장 + Overlay 이중"은 2026-06-30 제거 완료·§5 ⑩ 박스 — 잔여는 atom code 개정 분리뿐) |
| 4 | **AI retrieval failure** | 🟠 중간 | 방향맹 임베딩·hybrid fusion 전략 부재·가설 store 미연결 (`semantic/matcher.py:9-18`·`api/scene.py`) |
| 5 | **relation explosion** | 🟠 중간(잠재) | `ANALOGOUS_TO`·`CONTRASTS`·`TRIGGERS_DISTRACTOR` 선언·미적재 → 적재 시 N² (`enums.py` EdgeType) |
| 6 | **AST duplication** | 🟠 중간 | SymPy(py)·mathjs(js) 병렬 정규화 → drift (`verify_step.py`·`graph2dSpec.js`) |
| 7 | **cyclic dependency** | 🟡 낮음(무방비) | 현재 acyclic이나 reachability/SCC 게이트 없음 (`populate.py`) |
| 8 | **node explosion** | 🟡 낮음 | 입도 판정 규칙 미명문(과분할)·Formula/Proof 미도입 |
| 9 | **renderer coupling** | 🟢 낮음 | spec 렌더러 독립·`extra="forbid"` (`visualization.py:186-199`) |
| 10 | **interaction state leakage** | 🟢 낮음 | spec stateless·런타임 분리 (`learning_scene.py`·`scene_models.dart`) |

---

## 2. 10개 질문 답변

### Q1. 지금 가장 위험한 노드 종류
- **① `ConceptNode.common_misconceptions`(JSONB 자유서술, `schema/concept.py:213`)** — 플레이북이
  "노드에 절대 넣지 말 것" 1순위로 꼽은 *오개념 리스트 노드 내장*이 실재. 카탈로그(kebab)와 FK
  없이 같은 오개념을 다르게 표현 → 오염원. (진단 경로에서는 이미 미사용 — `05a` RS2.)
- **② 집계 노드(단원·소단원 860개)** — 최대 out-degree 7. retrieval에 쓰이면 hub로 attention
  오염(플레이북: L1/L2 노드는 "검색 핵심으로 쓰지 말 것").
- **③ 미도입 `FormulaNode`** — 변형식(변수명·항순서) 노드화하면 즉시 폭발. *지금 없는 게 정답*
  (플레이북: 공식은 맨 마지막·canonical만).

### Q2. 미래에 폭발할 relation 종류
enum에 **선언만 되고 미적재**인 셋이 정확한 위험원(`enums.py` EdgeType):
- **`ANALOGOUS_TO`(유비/related)** — 약한 semantic. 적재 시작 시 N² 폭발·traversal 붕괴.
- **`CONTRASTS`(frequently_confused)** — 양방향·dense화 경향.
- **`TRIGGERS_DISTRACTOR`(개념↔오개념 다리)** — 두 그래프 연결 순간 cycle·context explosion 진입로.

PREREQUISITE만 쓰는 지금이 가장 건강. 위 셋은 "구조적으로 제거 불가능"할 때만, traversal=0(ranking
전용)으로 도입해야 한다.

### Q3. retrieval ambiguity가 가장 높은 영역
**오개념 매칭**(`l4/misconception/semantic/matcher.py:9-18` 자체 명시). "연속이면 미분가능" vs
올바른 "미분가능하면 연속", "f∘g=g∘f" vs "≠", "둘레↔넓이" — substring·임베딩 **모두 방향·부정·
등치를 못 가림**. judge(LLM)가 "제거만" 해서 완화하나 잔여 FP 45.5%(`04b`). 개념 retrieval은 임베딩
namespace 분리·희소 그래프라 상대적으로 안전.

### Q4. 유지보수 지옥 가능성이 높은 구조
"Single change → global rebuild" 후보 3:
- **오개념 3중 표현**(kebab 30 / M-id 839 / JSONB) FK 없음 — 하나 고치면 나머지 침묵 drift.
- **교육과정 이중**(노드 내장 `grade_introduced`·`curriculum_version` + `CurriculumEntry` overlay)
  — 진실 출처 2개. **⚠️ 정정(2026-07-03·§5 ⑩ 박스)**: 노드 4필드는 2026-06-30 제거·Overlay 단일 진실
  전환 완료 — 본 줄은 제거 *이전* 스냅샷.
- **수식 파서 이중**(SymPy + mathjs) — 동치 규칙이 두 언어에 따로.

### Q5. 교육과정 변경 시 가장 취약한 부분
**노드 내장 교육과정 필드**(`Concept.grade_introduced`·`semester_introduced`·`curriculum_version`·
`subject`, `schema/concept.py:147-160`)와 **atom code 자체**('2수01-01-2'에 2022 개정 의미 박힘).
플레이북 철칙은 "concept_id는 영속, curriculum은 Overlay". 지금은 Overlay(`CurriculumEntry`)가
있으면서도 노드가 교육과정을 들고 있어, 2028 개정·다국 확장 시 둘이 충돌. → **방향**: 노드 내장
필드를 동결/제거하고 Overlay를 단일 진실로.

> **⚠️ 정정(2026-07-03·§5 ⑩ 박스)**: 노드 내장 4필드는 2026-06-30 drop 마이그레이션으로 제거됐고
> (`schema/concept.py:147-160` 인용 무효) Overlay `CurriculumEntry`가 단일 진실이다. 본 절은 제거
> *이전* 스냅샷 — 남은 것은 atom code 개정 분리(deferred-with-spec)와 개정 폐집합 단일출처(완료)뿐.

### Q6. visualization/plugin 교체 시 깨질 부분
대부분 안전(spec 렌더러 독립). 깨질 좁은 지점만:
- **`graph2dSpec.js`의 mathjs 변환**(`**`→`^`·`toTex`) — 렌더러별 정규화가 웹 플러그인에 살아있어
  Desmos→타 엔진 교체 시 `graph2dSpecToState` 재구현 필요.
- **`AnimationSpec.asset_id`** — Manim 사전렌더 파이프라인 종속(렌더러 변경 시 자산 재생성).
- **base64 `spec_param` 공유링크** — 고정 wire 포맷(호환성 부채).

### Q7. AI가 semantic distinction을 실패할 가능성
- **방향/부정/등치**(Q3) — 구조적.
- **"객체 vs 해석"** — atom 백본은 "기울기"는 있어도 "기울기 해석"을 별도 노드로 두지 않음 →
  LLM이 변화율/방향/속도 융합. 게다가 원자는 redaction으로 `name_ko + transfer`만 임베딩
  (`atom_graph/embedding.py:81`) → 신호가 얇아 구분 실패 위험↑.
- **canonical 오개념 판별** — 3중 표현 중 LLM이 정본을 못 가림.

### Q8. 지금 반드시 분리해야 하는 layer
- **교육과정 Overlay 완전 분리** — 노드에서 교육과정 필드를 떼고 `CurriculumEntry`를 단일 진실로.
- **오개념 정체성(identity) layer** — kebab/M-id/JSONB를 *하나의 canonical id*로 통합. 카탈로그=
  진실, 노드 `common_misconceptions`는 "시드 텍스트"로 강등(이미 진단 경로 미사용).
- **canonical 동치 authority 1개** — SymPy를 단일 권위로, mathjs/Lean은 그에 수렴(병렬 진실 금지).

### Q9. 지금 절대 premature abstraction 하면 안 되는 부분
- **AST 5계층 엔진** — SymPy로 충분. 단계검증 코퍼스·WH-S Tier3(Lean) 성숙 전 full AST는 과설계.
- **약한 semantic relation**(ANALOGOUS_TO/related) — 구체 수요 전 추가 금지.
- **FormulaNode·TheoremNode·ProofNode** — 공식은 마지막·증명은 scope 제외(`05a` RS4·WH-S Tier3).
- **LearningScene element의 typed union 코드젠 강제(Dart)** — 현 flat+kind가 정답(선례 0·코드젠 리스크).
- **interaction state 영속화를 spec에 흡수** — 별도 테이블로.

### Q10. 장기 생존 최소 invariant (협상 불가)
1. **ID 영속·curriculum은 ID에 없음**(code/UUID immutable).
2. **dependency 계열 엣지는 acyclic** — load 시 reachability/SCC 게이트(현재 self-loop만).
3. **노드는 의미만** — renderer/prompt/runtime/user/curriculum/오개념리스트 비내장(현재
   `common_misconceptions`·내장 교육과정이 위반).
4. **Visualization spec 렌더러 독립**(no pixel/fps/shader·`extra="forbid"` 유지).
5. **Math state ⊥ interaction/animation/UI state**(spec stateless 유지).
6. **오개념 = 단일 canonical 정체성·독립 그래프·reactive 로드만**(정상 추론 경로 진입 금지).
7. **동치 권위 1개**(SymPy 단일 진실).
8. **LLM은 전체 그래프 미열람** — bounded traversal(depth≤2·max_nodes~12) 명문화.
9. **학생 노출 전 검증 게이트 필수**(정답·낙인 필드 부재 — 현재 충족).

---

## 3. 종합

- **표현 계층(시각화·장면)은 안전** — invariant가 스키마(`extra="forbid"`·불변식·검증 게이트)로
  박혀 renderer coupling·interaction leakage·premature abstraction이 모두 낮음.
- **진짜 부채 4곳**: ① 그래프 위생(cycle 게이트 부재·약한 관계 잠재 폭발) ② 교육과정 이중화
  ③ 오개념 3중 정체성 ④ 병렬 수식 파서.
- **폭발은 시작 전** — 약한 relation 미적재·Formula/Proof 미도입·그래프 희소. 따라서 *지금이
  invariant(§2 Q10)를 코드 게이트로 박을 최적기*다. 이 부채들의 작업 항목화는 본 문서 범위 밖
  (별도 `/plan`).

---

## 4. 구현 후속 — invariant 코드 게이트 동결 (2026-06-30·PR #357)

§2 Q10 invariant 중 *회귀·미래 폭발 경로*를 코드 게이트(테스트/가드)로 동결했다. **이미 구현된
방어선은 재구현하지 않고**(적재 시점 cycle DFS·교육과정 4필드 제거·약한 relation load-time skip·
crosswalk 골격+resolver·증거저장소 shadow), **premature한 것은 도입하지 않았다**(소비처/경로 부재).

| invariant | 게이트 | 좌석 |
|---|---|---|
| Q10-③ 노드는 의미만 | 금지 필드 + 허용 화이트리스트 동결 | `tests/.../schema/test_concept.py` |
| Q1/Q8 오개념 자유서술 | `common_misconceptions` 런타임 미사용(행동+정적) + seed 전용 주석 | `test_scene_generation.py`·`test_concept_misconception_runtime.py`·`schema/concept.py` |
| Q2 약한 relation 폭발 | EdgeType 약한 값 전부 스윕→PREREQUISITE만 적재 + traversal 배제 + 어휘 보존 | `test_edge_relation_governance.py`·`test_prerequisite_traversal_integration.py` |
| Q10-⑥ 오개념 단일 정체성 | crosswalk shadow 배선(비노출·비차단) — 저장 좌석(`_persist_active_set`·`log_evidence`) + **노출 표면 좌석**(`generate_learning_scene` 프로브별 관측 = canary 노출 가중 분모). wh1_loop는 커밋 좌석 중복이라 비채택 | `l4/misconception/hypothesis_store.py`·`evidence_store.py`·`l4/scene_generation.py`·`test_scene_generation_crosslink_shadow.py` |
| Q10-⑧(부분) traversal 예산 | `MAX_PREREQUISITE_DEPTH`(깊이)·`MAX_PREREQUISITE_NODES`(노드 수 안전밸브·2026-07-03) 단일 출처 | `l2/prerequisite_recommendation.py`·`api/me.py` |

**미채택(premature)**: 증분 edge-add reachability·SCC 크론·약한 타입 reject validator·crosswalk 매핑
*자동* 적재(사람 검수 산출물·우선순위 #1·#3). **deferred-with-spec**: **LLM subgraph 컨텍스트 예산** —
소비처(WH-1 LLM 정책) 미도입이라 코드는 미구현이나, 불변식(depth≤2·max_nodes~12·약한 관계 배제)은 §5 ⑨에
**권위 단일 출처 spec으로 동결**(2026-07-03). 소비처가 생기는 순간 그 spec을 참조·별도 재발명 금지.
**잔여(사람 검수 게이트)**: 오개념 crosswalk 매핑 채택·적재(완료 2026-07-03·`docs/data/
misconception_crosslink_candidates.md`→로더 적재→shadow→canary)·교육과정 Overlay US/IMO·`required_depth`
큐레이션.

---

## 5. 목표 규모 스케일업 투영 — 10 임계점 (2026-07-01)

> **위치**: §1~§2는 *현재 스냅샷*에서 "지금 무엇이 위험한가"를 답한다. 본 절은 그 실패모드를
> **목표 규모**(수학 전과정·문제 10만+·오개념 수천·visualization 수백·interaction 수천·renderer
> 다중화·AI tutoring 통합·multi-language·adaptive·**proof system**)로 *전방 투영*해 "무엇이·언제
> 깨지는가"(임계값·트리거)와 *방향 처방*만 답한다. §2 Q10과 동일하게 **작업 항목화는 하지 않는다**
> (별도 `/plan`). 현재 규모 수치·근거는 §0~§2를 재인용하며 다시 서술하지 않는다.

### 5.0 목표 규모 스냅샷 (현재 → 목표)

| 축 | 현재(§0) | 목표 | 배율(추정) | 1차 압력 지점 |
|---|---|---|---|---|
| 개념/원자 노드 | 원자 1,837(부분·고1 미적분 중심) | 전과정(초·중·고+재수+영재) ~2~5만 | ~15~30× | Neo4j 단일 인스턴스·hub 집계노드 |
| 엣지 | 2,213 전량 `PREREQUISITE` | 희소 유지 시 ~수만 / **약한 관계 적재 시 N²** | 비선형 | `enums.py` 약한 3종 |
| 문제 | 코퍼스 구축 중 | **10만+** | — | `Problem` PG+pgvector 동거 |
| 오개념 | 2,676(kebab 30·M-id 839·원자 1,837) | 수천~1만 | ~2~4× | 3중 표현 FK 부재 drift |
| visualization type | 4(§0) | 수백 type/템플릿 | ~수십× | `_SPEC_MODEL_BY_TYPE` 정적 맵 |
| interaction 패턴 | ~15(SceneElement 6·Intervention 4·Socratic 5) | 수천 | ~100× | `SceneElement` kind 하드코딩 union |
| renderer | 실질 1(웹 계산기)+명세 | Flutter/웹/PDF/AI 다중 | — | mathjs·Manim asset 국소 종속 |
| **proof system** | **scope 밖**(`05a` RS4·WH-S Tier3) | 신규 진입 | 0→N | **최대 신규 폭발원** |

**한 줄 평**: 현재 부채 4곳(§3 종합: 그래프 위생·교육과정 이중·오개념 3중·파서 이중)은 규모에서
*증폭*되고, proof system·multi-language·renderer 다중화·visualization/interaction 폭증은 *신규* 폭발원이다.

### 5.1 10 임계점

**① 가장 먼저 폭발하는 node** — 폭발 순서 3단.
- **1순위 `ProblemNode`**(10만+·즉시·최대 볼륨). 단 이는 "노드 폭발"이 아니라 *인덱스/검색 대상 폭발*로
  관리 가능해야 한다 — Problem은 개념 그래프 노드가 **아니라** 개념을 *참조*하는 인덱스 엔티티(`Problem`
  `active_concepts`·`standard_codes`). 개념 그래프에 Problem을 노드로 흡수하면 즉시 붕괴. **경계 유지가 처방**.
- **2순위 미도입 `FormulaNode`/`ProofNode`**(proof system 진입 순간). 변형식(변수명·항순서)·증명 트리를
  노드화하면 즉시 N배(§2 Q1-③·Q9). 처방: Formula는 canonical 형만·맨 마지막, Proof는 **TheoremNode(무엇이
  참) ≠ ProofNode(왜 참) 분리(1:다)**·Lean(Tier3) 성숙 전 도입 금지(`principles_review §3.8`).
- **3순위 misconception 노드화**(`TRIGGERS_DISTRACTOR` 적재로 카탈로그가 그래프化, `enums.py:543-549`).
  수천 종을 개념 그래프에 잇는 순간 두 그래프 결합·context 폭증. 처방: 오개념은 **독립 그래프·reactive
  로드만**(§2 Q10-⑥).

**② relation density 최고 위험 영역** — `enums.py:534-541` **약한 관계 3종**(`ANALOGOUS_TO`·`CONTRASTS`·
`TRIGGERS_DISTRACTOR`). 현재 out-degree 평균 1.25(§0). 수만 노드에서 "해석↔대수 유사쌍"을 유비로 잇기
시작하면 도메인 내 준-완전그래프화 → **N² 폭발·traversal 붕괴**(§2 Q2). 임계 트리거: 약한 관계 적재
착수 그 자체. 처방: 도입해야 한다면 **traversal=0(ranking 전용)·단방향 canonical·도메인 경계 밖 금지**.
현재 load-time skip 게이트(§4·`test_edge_relation_governance.py`)를 규모 확장 뒤에도 **동결 유지**.

**③ normalization 실패 가능성** — §2 Q4 "single change→global rebuild" 3부채가 규모에서 증폭.
- 오개념 3중 표현(kebab/M-id/JSONB, FK 없음): 수천 종이면 drift가 침묵 폭증(`schema/concept.py:213`·
  `schema/misconception_catalog.py`).
- 교육과정 이중(노드 내장 잔재 + `CurriculumEntry` Overlay): multi-language가 **N개국 × 2개정**으로 곱해짐.
- 파서 이중(SymPy + mathjs): 10만 문제 검증에서 동치 규칙이 두 언어에 따로 → drift.
처방: **canonical id 일원화 · Overlay 단일 진실 · 동치 권위 1개**(§2 Q8). 규모 진입 *전*이 유일한 저비용 창.

**④ graph partition 필요 시점** — Neo4j 5.x **Community(단일 인스턴스·비클러스터)**. 임계 트리거:
(a) 개념/원자 노드 **수만 대** 진입 + (b) 선수 추천 순회(`l2/prerequisite_recommendation.py`
`MAX_PREREQUISITE_DEPTH=5`) p95 지연 상승 + (c) 집계 노드(단원·소단원 out 7, §2 Q1-②) hub 오염. 처방:
**도메인 파티션**(대수/기하/해석/확통)으로 순회를 서브그래프에 가둠 · 집계 노드는 retrieval에서 배제 ·
Community 한계 도달 시 Enterprise/샤딩은 *마지막*. 관측 트리거값을 먼저 계기화(노드 수·p95 latency).

> **④ 계기화 착수 (2026-07-03) — hook 먼저, 파티션은 마지막** — 처방의 "계기화 먼저"를 시작했다.
> 선수 traversal(`fetch_prerequisites`·프로덕션)에 **관측 hook**을 배선: 순회 노드 수(dedup 전 행)·
> 결과 수·최대 깊이·쿼리 latency를 인메모리 버킷 히스토그램(`l2/_traversal_metrics.py`)에 방출해
> 트리거(a 수만 노드·b 순회 p95·c hub 오염 규모)를 *실측*한다. `api/_device_metrics.py`의 "hook
> 도입만·exporter 후속" 관용 계승 — **opt-in**(`prerequisite_traversal_metrics_enabled`·기본 off라
> 방출·비용 0·행동 불변)이며 `get_traversal_metrics()`가 운영자/후속 exporter 조회점이다.
>
> **deferred(파티션은 "마지막")**: **p95 HTTP 미들웨어·OTel exporter 배선**(관용상 후속·지금은
> traversal-함수 레벨 latency까지)·**hub fan-out 집계·retrieval 배제 필터**·**도메인 파티션 자체**
> (대수/기하/해석/확통 서브그래프·Enterprise/샤딩) — 계기화 지표가 실측으로 임계에 접근할 때 착수.

**⑤ plugin architecture 필요 시점** — 이미 부분 존재(L3 라우터 3축 `l3/router.py`·L6 모드 디렉토리·
`InterventionPattern`). 임계 트리거: renderer 다중화 × **visualization 수백 type** → `_SPEC_MODEL_BY_TYPE`
정적 맵(`schema/visualization.py`)과 `SceneElement` **6 kind 하드코딩 union**(`l4/learning_scene.py:79-312`)이
매 type/패턴마다 코어 수정을 강요. 처방: **renderer adapter 레지스트리 + visualization type 등록제**(신규
type이 코어 재컴파일 없이 등록). 단 §2 Q9 경고 준수 — **Dart typed-union 코드젠 강제 금지**(현 flat+kind가
정답·선례 0). 트리거: type/패턴 수가 "정적 열거로 관리 불가" 임계 초과 시.

**⑥ retrieval indexing 재설계 시점** — pgvector 단일 store(슬98). 임계 트리거: 10만 문제 × 다중 임베딩 +
수천 오개념 + 개념 → 벡터 수 급증·HNSW **재색인 비용**·namespace 미분리 **의미 오염**(`principles_review
§3.6`·`04b` 방향맹 실측 FP 45.5%). 재설계 **단계적**: (1순위) concept/misconception/example **논리 namespace
분리**(단일 pgvector 내 컬럼·필터, `l1/concept_graph/retrieval.py`) → (2순위) **hybrid fusion**(BM25+dense,
방향·부정·등치 보강) → (3순위) 벡터 수·recall·재색인 시간이 pgvector 한계 초과 시 **Qdrant 이관**(슬98 예고·
`MEMORY.md`). 트리거값(벡터 수·재색인 벽시계·recall@k)을 먼저 계기화.

> **⑥ 정정 + 불변식 동결 (2026-07-03)** — 위 "namespace 미분리"는 부정확하다(§3.6 review 시점 미확인
> 서술). 실제로 **1순위 namespace 분리는 이미 완료**:
> - concept/misconception/atom 임베딩이 **별도 물리 테이블**(`concept_embedding`·`misconception_
>   embedding`·`atom_embedding`, 각 `Vector(1024)`)에 격리. 검색 3함수(`ConceptEmbeddingIndex.search`·
>   `PgVectorIndex.search`·`AtomEmbeddingIndex.search`)가 **자기 테이블만 SELECT**해 cross-type 오염이
>   구조적으로 불가능하다(cross-table 벡터 JOIN/UNION 부재). Q3(`:70-71`)의 "namespace 분리·안전"이 맞고,
>   본 절·§3.6의 "미분리"가 stale. 이 격리는 회귀 가드로 동결(`test_embedding_namespace_governance.py`·
>   벡터 테이블 집합=등록부·타입별 단일 PK — 새 임베딩은 자기 테이블로).
> - **"FP 45.5% 방향맹"은 cross-type이 아니라 misconception 임베딩 *내부*의 방향·부정·등치 맹점**
>   (`semantic/matcher.py:14-18`가 자기 명세로 못 박음). → namespace(1순위)로 풀리지 않고 **2순위 hybrid
>   fusion/judge**의 몫이다(후속 슬라이스).
>
> **deferred(소비처·데이터 트리거 대기)**: (i) **example(문제/풀이) 임베딩 축 미구현** — 3분할 중 한 축이
> 빔. 도입 시 *별 테이블*로(등록부 갱신·위 가드가 강제). (ii) **hybrid fusion**(2순위) — 방향맹 해소용
> ML 슬라이스. (iii) **HNSW 인덱스·Qdrant 이관**(3순위) — 벡터 수·재색인 시간이 pgvector 한계 초과 시.
> 지금 도입은 데이터 규모 미달로 premature(계기화 먼저).

**⑦ AST canonicalization 병목** — SymPy **단일 권위**(`notation_contract.md`·`l3/verify_step.py`). 두 병목:
(a) 처리량 — 10만 문제 × 다중 풀이 × 단계 검증의 SymPy 호출량, (b) **결정불가능 경계** — proof system 진입
시 canonical 정규화가 교육적 범위를 넘으면(일반 항등식 판정) 정지 위험(`05a` RS4·§2 Q9). mathjs 병렬
파서(`graph2dSpec.js`) drift도 규모에서 확대. 처방: **SymPy 권위 유지** · 사전검증·캐싱(`l3/pregenerate`)으로
런타임 처리량 흡수 · Lean(Tier3)은 **proof scope 한정** · "**교육적으로 필요한 범위까지만 정규화**" 경계
고수(full CAS/증명 자동화로 확대 금지·§2 Q9).

**⑧ renderer abstraction 한계** — 대부분 안전(spec 렌더러 독립·`schema/visualization.py` `extra="forbid"`,
§2 Q6·Q9). 규모에서 깨지는 좁은 3점: (a) `graph2dSpec.js`의 **mathjs 변환**(`**`→`^`·`toTex`)이 웹 플러그인에
살아있어 Desmos→타 엔진 교체 시 재구현, (b) `AnimationSpec.asset_id`(`visualization.py:108`)의 **Manim
사전렌더 종속**(렌더러 변경 시 자산 재생성), (c) `?spec=` **base64(JSON) 공유링크**(`graph2dSpec.js:15`)의
고정 wire 포맷. 다중 렌더러 × visualization 수백에서 이 3점이 재구현 병목. 처방: 렌더러별 정규화를 spec
**밖**으로 · asset 파이프라인 추상화 · wire 포맷 버저닝.

**⑨ AI tutoring consistency 붕괴 위험** — 규모의 3동인.
- **context 예산 붕괴**: 수만 노드에서 bounded traversal(**depth≤2·max_nodes~12**, §2 Q10-⑧) 미준수 시
  LLM에 과대 서브그래프 유입 → 일관성 붕괴. 예산을 **단일 출처로 명문화 유지**가 방어선.
- **약한 relation traversal 유입**: ①·② 폭발이 그대로 subgraph 폭발로 전이. 처방: 약한 관계 traversal 배제.
- **오개념 정체성 3중**: 수천 종이면 LLM이 canonical을 못 가려 진단이 흔들림(§2 Q7). 처방: canonical 일원화.
현재 `MAX_PREREQUISITE_DEPTH`(깊이)·`MAX_PREREQUISITE_NODES`(노드 수 안전밸브·2026-07-03)
단일 출처·crosswalk shadow(§4)가 예방선.

> **LLM subgraph 컨텍스트 예산 spec (2026-07-03 동결·코드는 소비처 대기)** — LLM에 서브그래프를
> 주입하는 소비처(WH-1 `TutorPolicy` LLM 정책)가 *아직 없어*(§4·`harness/wh1_loop.py` query_curriculum
> 스텁) 코드 게이트는 premature다(§2 Q9). 그러나 불변식은 **지금 권위 단일 출처로 못 박아** 미래
> 소비처가 재발명·drift하지 못하게 한다:
> - **depth ≤ 2** — LLM 컨텍스트에 넣는 서브그래프는 2-hop 이내(전체 그래프 미열람).
> - **max_nodes ~ 12** — 노드 수 상한(과대 서브그래프 유입 차단).
> - **약한 관계 배제** — `ANALOGOUS_TO`·`CONTRASTS`·`TRIGGERS_DISTRACTOR`는 LLM 컨텍스트 traversal에서
>   제외(②의 N² 폭발이 subgraph 폭발로 전이하는 것 차단).
> WH-1 LLM 정책이 서브그래프를 소비하는 순간 **이 spec을 단일 출처로 참조**하고, 그래프 traversal
> 예산(`MAX_PREREQUISITE_*`, L2)과 별개의 *LLM 컨텍스트* 상수로 신설한다(별도 재발명 금지). 그 전엔
> 코드 0(dead code 회피·§4 원칙).

**⑩ curriculum versioning 문제** — 노드 내장 교육과정 4필드는 §4에서 제거·`CurriculumEntry` Overlay 전환
완료. 잔여 위험: (a) **atom code 자체에 개정연도 의미**('2수01-01-2'에 2022 개정 박힘, §2 Q5), (b)
multi-language = **국가 × 개정 축의 곱**, (c) 2028 개정 유입. 처방: **concept_id 영속·curriculum=Overlay
단일 진실**(§2 Q8·Q10-①) · code에서 개정 의미 분리 · 국가/개정을 **Overlay 차원**으로(노드 불변). 목표
규모에서 versioning은 "노드가 교육과정을 들면 즉시 붕괴, Overlay면 선형 증가"로 갈린다.

> **⑩ 불변식 동결 + 현 상태 정정 (2026-07-03)** — 처방의 큰 축은 *이미 완료*됐다(§0~§3의 "노드 내장
> 잔재" 서술은 2026-06-30 drop 마이그레이션 *이전* 스냅샷 — 아래가 현재 진실):
> - **Overlay가 노드 밖 단일 진실** — `CurriculumEntry`(`schema/curriculum_entry.py`)가 `country_code`×
>   `curriculum_revision`을 **복합키/필드로 이미 수용**(`db/models/curriculum_entry.py` UniqueConstraint).
>   국가×개정 축은 구조적으로 준비됨.
> - **`Concept` 노드 교육과정 4필드 제거 완료** — drop 마이그레이션 2건(`20260630_1200`·`20260630_1600
>   _f3a4b5c6d7e8`) + 회귀 가드(`tests/backend/schema/test_concept.py` `TestConceptNodeFieldGovernance`).
>   → §1 표 3행·§2 Q4·Q5의 "노드 내장 + Overlay 이중"·`schema/concept.py:147-160` 인용은 **stale**.
> - **성취기준은 개정을 축으로 분리** — `official_code`는 개정 비유일(맨 앞=학년), 개정은 별도 필드
>   `curriculum_revision` + `norm_id` prefix로 유일화. 개정 폐집합은 **단일 진실 `_VALID_CURRICULUM_
>   REVISIONS`에서 `NORM_ID_PATTERN` 정규식을 파생**(2026-07-03·`ncic/models.py`) — 한 곳만 고치면
>   개정 추가가 정규식·검증에 함께 반영(하드코딩 drift 0).
> - **의도된 잔재**(제거 대상 아님): `Problem.curriculum_version`(문항 정합 게이팅·Concept과 독립)·
>   `concept_node`/`atom_node`의 `standard_codes`·`ccss_code`(코드=사실정보·공공·본문 아님).
>
> **deferred-with-spec (multi-language 착수 전 premature — ⑨ spec 동결과 동형)**: atom code 개정 파서·
> multi-country resolver·US/IMO 교육과정 데이터 적재는 소비처 미도입이라 *코드 미구현*. atom code는
> 이질(K-12·대학)이라 **불투명 문자열 유지**(개정 파싱 강제 금지)하고, 개정·국가는 **Overlay 축
> (`country_code`×`curriculum_revision`)을 단일 출처로 참조**한다 — 소비처가 생기면 그 축으로 해석하고
> code에서 개정을 떼어내지 않는다. 목표 규모에서 versioning은 "노드/코드가 교육과정을 들면 즉시 붕괴,
> Overlay 축이면 선형 증가"로 갈린다.

### 5.2 종합 — 임계 우선순위

| 임계 | 트리거(선행 지표) | 처방 방향 | 긴급도 |
|---|---|---|---|
| ② 약한 관계 N² | 약한 관계 적재 착수 | traversal=0·게이트 동결 | 🔴 진입 전 동결 |
| ③ 3중 정체성 drift | 오개념 수천 종 도달 | canonical 일원화 | 🔴 곱셈 폭증 전 |
| ⑩ curriculum ×국가×개정 | multi-language 착수 | Overlay 단일 진실 | 🔴 곱 축 진입 전 |
| ① Formula/Proof 노드화 | proof system 착수 | Theorem≠Proof·canonical만 | 🟠 신규 폭발원 |
| ⑥ retrieval 오염 | 벡터 수·recall 저하 | namespace→fusion→Qdrant | 🟠 단계적 |
| ④ graph partition | 수만 노드·p95 지연 | 계기화(hook 착수)→도메인 파티션 | 🟠 계기화 착수·파티션 대기 |
| ⑤ plugin 필요 | type/패턴 정적관리 불가 | 등록제·adapter | 🟡 관측 기반 |
| ⑦ AST 병목 | SymPy 처리량·proof scope | 캐싱·범위 경계 고수 | 🟡 |
| ⑨ tutoring 붕괴 | subgraph 예산 초과 | 예산 명문화 | 🟡 ①②연동 |
| ⑧ renderer 한계 | 다중 렌더러 착수 | 정규화 spec 밖 | 🟢 좁음 |

**결론**: 목표 규모의 폭발은 대부분 *아직 시작 전*이다(약한 관계 미적재·Formula/Proof 미도입·multi-language
미착수·그래프 희소). 따라서 **목표 규모 진입 *전*에 §2 Q10 invariant를 코드 게이트로 박는 것**이 유일한
저비용 창이며, §4가 그 첫 5종을 이미 동결했다. 위 표의 🔴 3건(②③⑩)은 각 "곱셈 축" 진입 직전이 마지막
방어 시점이다. 본 절은 임계·방향까지다 — 게이트 작업 항목화는 별도 `/plan`.

---

## 참고
- 정본 상위: `docs/architecture/math_dsl_principles_review.md`(플레이북 검토)
- 선행: `docs/architecture/05a_learning_scene_dsl.md`·`04b_misconception_judge_graduation.md`
- 코드: `schema/concept.py`·`schema/enums.py`·`schema/visualization.py`·`l4/learning_scene.py`·
  `l4/scene_generation.py`·`l4/misconception/`·`l1/atom_graph/`·`l3/verify_step.py`·`l3/verify_answer.py`·
  `src/web/graphing-calculator/src/lib/graph2dSpec.js`·`schema/misconception_catalog.py`
- 데이터: `data/corpus/atom_graph_v1/graph.json` · 스키마: `schemas/v1.1/curriculum_entry.schema.yaml`
- 원칙: `CLAUDE.md`(의사결정 우선순위·절대 금기·표현≠의미)
- 변경 이력: v0.1 (2026-06-30 초안 — 분석만·코드/스키마 변경 0) · v0.2 (2026-06-30 — §4 구현 후속
  추가: invariant 코드 게이트 5종 동결·PR #357) · v0.3 (2026-07-01 — §5 목표 규모 스케일업 투영 추가:
  10 임계점·트리거·방향 처방·우선순위 표. 분석만·코드/스키마 변경 0) · v0.4 (2026-07-01 — §4 Q10-⑥
  행 갱신: 오개념 crosswalk shadow에 노출 표면 좌석(`scene_generation`) 추가·wh1_loop 비채택 근거.
  구현 동반: `l4/scene_generation.py` + 신규 테스트)
