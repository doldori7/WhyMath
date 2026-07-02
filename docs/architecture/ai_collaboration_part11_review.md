# 구축 플레이북 Part 11(AI 협업 방법론) 설계-준수 검토

> **상태**: 검토(review) · **계층**: 횡단(메타 · 거버넌스 · 프로세스 불변식) · **작성일**: 2026-07-02
> **검토 대상**: `docs/standards/playbook_part_review_questions.md:108-114` **Part 11 — AI 협업 방법론**
> (법칙: *AI = 답변기 ❌ / 구조 붕괴 감지기 ⭕ · 4종 질문축 · 질문골격 · 단계적 심화*)
> **정본(단일 진실원)**: `CLAUDE.md:156-193`("🧱 구축 플레이북 불변식 & AI 질문 프로토콜" · §"AI 질문 프로토콜") ·
> **교차점검**: `build_checkpoint_questions.md:111`(교차 #4 "답변기 아니라 구조 붕괴 감지기") ·
> **선행 Part 검토**: `part2_node_design_review.md` · `edge_design_part3_review.md` · `math_dsl_part4_ast_review.md` ·
> `04c_misconception_seven_stage_separation.md`

---

## 0. 요지 (BLUF)

Part 11의 3개 검문은 **이미 준수**한다. 다른 파트(2·4·6)와 결정적으로 다른 점: **닫을 코드 갭이 없다.** Part 11은
"AI를 답변기가 아니라 *구조 붕괴 감지기*로 쓴다"는 **프로세스 불변식**이고, 그 정의는 이미 `CLAUDE.md:156-193`에
정본으로 각인돼 모든 세션이 자동 로드한다. 검문 ①은 코드(거버넌스 테스트·검증기·budget guard)로 강하게
뒷받침되고, ②③은 프로토콜 정의 + 실천 증거(생성 프롬프트 골격 · 선행 검토의 메타 질문 시연)로 충족된다.

**따라서 이 검토의 산출물은 "구현"이 아니라 "감사 + 드리프트 동결"이다.** 진짜 리스크는 코드 부재가 아니라
*드리프트* — `CLAUDE.md`의 프로토콜 정의나 검문 ①을 떠받치는 거버넌스 테스트가 조용히 사라지면 이 체크리스트가
근거를 잃는다. 그 연결 무결성을 hermetic manifest(`tests/backend/test_ai_collaboration_protocol_manifest.py`)로
동결한다.

> **핵심 구분 — 두 종류의 "프롬프트 골격"을 혼동하지 않는다 (category error 방어)**:
> - **AI 협업 골격** `[역할][목표][환경][출력][검증]`(Part 11·`CLAUDE.md:190`) = *개발자가 설계 시점에 Claude에게
>   묻는* 방식. 대상은 아키텍처·구조 비평.
> - **런타임 튜터링 프롬프트** `[학생 컨텍스트][행동 원칙][권장 결정][응답 형식]`(`prompt_engineering.md`) = *학생에게
>   응답을 생성하는* L4 프롬프트. 대상은 학습자.
> - `docs/prompts/*`(6종: socratic · misconception_diagnosis · misconception_judge · multi_solution_gen ·
>   polya_4step · prm_verification)은 **후자(런타임)**를 올바르게 따르므로 협업 골격 미적용이 정상이다. Part 11
>   준수를 *런타임 프롬프트 라이브러리*에 요구하면 category error — 협업 골격의 준수 표면은 CLAUDE.md 프로토콜 +
>   *생성/설계 시점* 프롬프트(아래 ②)다.

---

## 1. 3개 검문 판정

### ① AI를 코드/UI 생성기가 아니라 구조 비평가·boundary 검사기·explosion 탐지기·schema validator로 쓰나 — **강하게 정합(코드로 뒷받침)**

프로토콜 정의: `CLAUDE.md:188`("코드 생성기 ❌ → 구조 비평가·boundary 검사기·explosion 탐지기·schema validator ⭕").
저장소는 이 원칙을 *실행 가능한 방어*로 물화(物化)했다 — AI/자동화의 몫은 구조를 *생성*하는 게 아니라 *드리프트·폭발을
감지*하는 것:

- **explosion 탐지기(폭발 감지)**:
  - `tests/backend/l1/test_edge_relation_governance.py` — `PREREQUISITE`만 적재, 약한 관계(ANALOGOUS_TO 등)가
    새어들면 red. N² dense화 차단.
  - `tests/backend/l1/test_five_node_connectivity_governance.py` — `FormulaNode`/`SkillNode`/`ProblemTypeNode`
    부재를 소스 스캔으로 동결(노드 폭발 차단).
  - `tests/data_pipeline/concept_graph/test_relation_vocabulary_governance.py` — 관계 타입 예산 5~8 + 금칙
    (`similar_to`/`related_to`) 부재.
- **boundary 검사기(경계)**:
  - `tests/backend/l1/test_embedding_namespace_governance.py` — 임베딩 namespace = table(kind) × subject
    대칭 게이트 + cross-table 코사인 금지.
  - `tests/data_pipeline/concept_graph/test_concept_node_purity.py` — Concept 노드에 renderer/prompt/curriculum/
    misconception/embedding 필드 부재(순수성).
- **schema validator(스키마 검증)**:
  - `src/data-pipeline/data_pipeline/concept_graph/validate.py` · `.../atom_graph/validate.py` — `prerequisite_cycle`
    를 **error**로 강제(DAG 보장) + id 형식·dangling·isolated 규칙.
- **budget guard(예산 가드)**:
  - `MAX_PREREQUISITE_DEPTH=5`(`l2/prerequisite_recommendation.py`, 동결 `tests/backend/l2/test_prerequisite_depth_budget.py`)
    · `anthropic_max_tokens`(LLM 컨텍스트 예산).

**메타 증거**: Part 2·3·4·6 검토 시리즈 자체가 "AI를 구조 붕괴 감지기로 쓴" 실천이다 — 각 검토는 코드를 양산한 게
아니라 *경계·폭발·순환을 판정*하고 그 판정을 테스트로 동결했다(예: Part 4는 5계층 AST를 *짓지 않은 것*이 정답임을
판정, Part 6은 preload 금지를 재확인·동결).

### ② 질문에 `[역할][목표][환경][출력][검증]` + 4축(존재이유·경계·붕괴·분리)이 들어가나 — **정합(각인 + 생성 프롬프트 실천)**

- **정의(정본)**: `CLAUDE.md:189`(4종 질문 축 ①존재 이유 ②경계 ③붕괴 ④분리) · `CLAUDE.md:190`(질문 골격
  `[역할][목표][환경][출력][검증]`). 모든 세션 자동 로드로 *강제*된다.
- **실천 증거(설계/생성 시점 프롬프트)**: 골격은 실제 코드가 LLM에 보내는 *생성 프롬프트*에 적용돼 있다 —
  `src/data-pipeline/data_pipeline/{ncic,concept_graph,atom_graph}/__main__.py` · `src/backend/whymath_backend/l4/misconception/judge_prompts.py`.
- **경계(위 §0 핵심 구분)**: 런타임 튜터링 프롬프트(`docs/prompts/*`)는 이 골격이 아니라 `prompt_engineering.md`
  표준을 따른다 — 정상이며 위반 아님.

### ③ 각 설계 끝에 "실패 이유"를 되묻고 7분할 인지행동 출력 형식을 강제하나 — **정합(정의 + 문서 강제 + 시연)**

- **정의(정본)**: `CLAUDE.md:192`(단계적 심화 `생성 → 비판 → 반례 → 개선 → 테스트 → 자동화` + "각 노드 설계 끝에
  반드시 묻는다 — 실패하는 이유") · `CLAUDE.md:193`(7분할 `1.구조적 2.교육적 3.AI retrieval 4.scaling 5.maintenance
  6.canonicalization 위험 7.mitigation` + "인지 행동(cognitive action) 기준").
- **문서 강제**: `playbook_part_review_questions.md:126`("메타 질문 (각 파트 끝 필수)") + `:128`(7대 붕괴 연쇄·
  cognitive-action 메타 질문)이 *모든* Part 검토 끝에 이 되묻기를 의무화한다.
- **시연**: `math_dsl_part4_ast_review.md:87`(§2 "메타 질문 — 7대 붕괴 연쇄 관점 인지행동 분석")이 7대 붕괴 연쇄에
  대해 실제로 인지행동 기준 분석을 수행 — 형식이 실동함을 입증. 본 문서 §2도 같은 형식을 따른다.

## 1.x 수용된 경계 / 관찰 (부채 아님)

- **(a) 독립 정본 스펙 문서 미신설 — 의도**: 프로토콜 정의는 `CLAUDE.md`에 이미 완전하다. 별도 문서로 재정의하면
  *이중 진실원*이 되어 "단일 진실 원천"(플레이북 유지보수 지옥 방어)을 스스로 위반한다. 따라서 본 문서는 *감사*만
  하고 재정의하지 않으며, `CLAUDE.md:156-193`을 유일 정본으로 가리킨다. **이 결정 자체가 검문 ①의 boundary 검사
  실천**(무엇을 독립 문서로 분리하지 *않을지*를 판정).
- **(b) 프롬프트 골격 구분(category error 방어)** — §0 핵심 구분. 감사자가 런타임 라이브러리에 협업 골격을 강요하지
  않도록 명문화.
- **(c) 메타 질문 섹션의 균일성 — 경미한 실천 관찰(후속)**: 검문 ③은 정의·강제·시연이 갖춰졌으나, *모든* 검토 문서가
  명시 "메타 질문" 섹션을 갖진 않는다(`math_dsl_part4_ast_review.md`는 보유; `edge_design_part3_review.md`·
  `04c_…`는 미보유). 규칙(`:126` "각 파트 끝 필수")은 존재하므로 *기계적 강제*(예: 검토 문서 lint)는 별도 후속.
  본 검토는 이를 코드 갭이 아닌 *practice 관찰*로 기록한다.
- **소스 0 · 마이그레이션 0.**

---

## 2. 메타 질문 — 7대 붕괴 연쇄 관점 인지행동 분석

> *"이 파트의 구조가 실제 서비스에서 실패하는 이유를, 노드폭발 · 관계폭발 · 순환참조 · 유지보수 · 성능 · AI추론실패 ·
> 교육일관성붕괴 관점에서, 표면 표현이 아니라 인지 행동(cognitive action) 기준으로 분석하라."*

Part 11의 실패는 *코드*가 아니라 **개발자의 인지 행동**에서 시작한다 — "AI에게 무엇을, 어떻게 묻는가"가 어긋나는
순간 붕괴 연쇄의 *진입로*가 열린다.

- **AI 추론 실패(가장 먼저)**: 개발자가 AI를 "구조 붕괴 감지기"가 아니라 "답변기"로 쓰기 시작하면(=전체 그래프를
  통째로 주고 "만들어줘"라고 물으면), attention dilution으로 AI가 *그럴듯한 잘못된 구조*를 뱉는다. 이것이 연쇄의
  머리다 — 인지 행동의 오류가 곧바로 추론 실패로 전이된다.
- **노드폭발 / 관계폭발**: AI를 코드 생성기로 쓰면 "모든 것을 노드화·관계화"하는 제안을 무비판 수용하게 된다. 4축 중
  ②경계·④분리를 묻지 않으면 폭발을 막을 *인지적 제동*이 사라진다. `test_five_node_connectivity_governance.py`·
  `test_relation_vocabulary_governance.py`는 이 제동을 *기계화*한 것 — 사람의 질문 규율이 흔들려도 red로 붙잡는다.
- **순환참조**: ③붕괴("어디서 실패하는가")를 되묻지 않으면 교육 그래프의 본질적 순환을 DAG로 강제할 계기를 놓친다.
  `validate.py`의 `prerequisite_cycle` error가 최후 방어선.
- **유지보수 지옥**: Part 11 자신을 독립 정본 문서로 재정의하면 진실원이 둘(CLAUDE.md + 신규 문서)이 되어 이 붕괴를
  스스로 유발한다(§1.x-a). 그래서 *감사만* 한다 — 인지 행동 수준에서 "무엇을 만들지 *않을지*"를 판정한 결과.
- **성능 병목**: AI에 전체 그래프를 주는 습관(=답변기 사용)은 context traversal 폭증으로 직결된다. budget guard
  (depth ≤ 5 · token cap)는 인지 습관의 실패를 시스템이 흡수하도록 한 것.
- **교육 일관성 붕괴(최종 귀결)**: 위 전부의 종착. Part 11은 이 연쇄의 *발원지(질문하는 인지 행동)*를 규율함으로써
  나머지 6개를 상류에서 차단하는 메타-파트다. 그래서 코드가 아니라 *프로토콜의 실재와 근거의 무결성*을 지키는 것이
  이 파트의 방어다.

**드리프트 실패 시나리오(이 manifest가 막는 것)**: 누군가 `CLAUDE.md`에서 프로토콜 섹션을 지우거나, 검문 ①의
거버넌스 테스트를 삭제하면 — 체크리스트는 그대로 "준수"라 말하지만 근거가 증발한다(침묵 실패). manifest가 red로
이를 강제 노출한다.

---

## 3. 결론

1. **Part 11 ①②③ 준수** — 코드 갭 없음. ①은 거버넌스 테스트·검증기·budget guard로 물화, ②③은
   `CLAUDE.md:188-193` 정본 + 생성 프롬프트·메타 질문 시연으로 충족.
2. **감사 + 동결** — 재정의(이중 진실원) 대신 hermetic manifest로 (i) 프로토콜 정의의 온전성, (ii) 검문 ① 근거
   거버넌스 테스트의 실재, (iii) 메타 질문 강제·시연의 실재를 드리프트로부터 동결.
3. **경계 지킴** — 협업 골격 ≠ 런타임 튜터링 프롬프트(category error 방어). 독립 스펙 문서 미신설(단일 진실원 유지).
4. **후속(범위 밖)**: 검토 문서의 "메타 질문 각 파트 끝 필수" 규칙을 기계적으로 강제하는 lint(모든 `*_review.md`
   섹션 검사)는 별도 슬라이스(§1.x-c). 소스/마이그레이션 변경 없음.

---

## 참고
- 정본: `CLAUDE.md:156-193`(구축 플레이북 불변식 & AI 질문 프로토콜)
- 질문지: `docs/standards/playbook_part_review_questions.md:108-114`(Part 11)·`:126-128`(메타 질문) ·
  `docs/standards/build_checkpoint_questions.md:111`(교차 #4)
- 근거 테스트(검문 ①): `tests/backend/l1/test_edge_relation_governance.py` ·
  `.../test_five_node_connectivity_governance.py` · `.../test_embedding_namespace_governance.py` ·
  `tests/data_pipeline/concept_graph/test_relation_vocabulary_governance.py` ·
  `.../test_concept_node_purity.py` · `tests/backend/l2/test_prerequisite_depth_budget.py`
- 검증기: `src/data-pipeline/data_pipeline/concept_graph/validate.py` · `.../atom_graph/validate.py`
- 생성 프롬프트(검문 ②): `src/data-pipeline/data_pipeline/{ncic,concept_graph,atom_graph}/__main__.py` ·
  `src/backend/whymath_backend/l4/misconception/judge_prompts.py`
- 동결 테스트: `tests/backend/test_ai_collaboration_protocol_manifest.py`(본 검토의 대응 manifest)
- 선행: `math_dsl_part4_ast_review.md`(§2 메타 질문 시연) · `04c_misconception_seven_stage_separation.md`(감사+동결 선례)
- 변경 이력: v0.1 (2026-07-02 — Part 11 AI 협업 방법론 감사 + 드리프트 동결)
