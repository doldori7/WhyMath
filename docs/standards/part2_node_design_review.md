# Part 2. 노드 설계 — 준수 검토 판정 (2026-07-02) + 리치 스펙 재검토 (2026-07-03)

> `docs/standards/playbook_part_review_questions.md`의 **Part 2. 노드 설계** 체크리스트 3항목을
> 현재 코드베이스에 대해 검토한 판정 리포트. 자매 문서: 설계 결정은
> `docs/architecture/concept_node_layering_decision.md`(ADR), 결정 로그는 `MEMORY.md`.

법칙: *노드 = 학생 사고가 바뀌는 최소 단위(= 독립 오개념 발생 단위). 우선 5노드, Formula는 마지막.*

> 🔄 **2026-07-03 재검토·전면 채택 결정**: 3항목 체크리스트보다 상세한 **리치 Part 2 스펙**(12노드
> taxonomy·9계층 ConceptNode·7계층 MisconceptionNode·SkillNode/ProblemTypeNode 1급화·canonical
> FormulaNode)으로 재검토한 결과 갭 확인 → 사용자가 **전면 채택** 결정. 이는 초판의 anti-explosion
> 판정(항목 ②의 "속성/스키마 구성")과 Stage B semantic 외부화를 **반전**한다(단 CLAUDE.md
> 금기·redaction 안에서). 판정·로드맵: ADR §0·`part-2-scalable-lobster.md`(Phase 0~6). 아래 초판
> 판정은 이력으로 보존한다.

---

## 판정 요약

| 항목 | 판정 | 조치 |
|---|---|---|
| ① 입도 = 오개념 발생 단위 | **△→✅(기준 명문화·감지 동결)** | 재분할 보류(전문가 검수) + 거버넌스 테스트 |
| ② 5노드 연결·Formula 나중 | **✅(표현 방식 확정)** | 전용 노드 폭증 없이 속성/스키마로 구성·ADR 문서화 |
| ③ 계층 분리·노드 순수성 | **△→부분 수정** | `misconception_text` 제거(즉시) + 4계층 명문화 + Stage B 게이트 |

---

## 항목 ① 입도 — "함수(과대)도 기울기의 x증가량(폭발)도 아닌 오개념 발생 단위인가?"

**판정 △ → 기준 명문화 + 감지 거버넌스로 축소.**

- 개념그래프(437·3단)와 원자그래프(2,697·세부개념 레벨)가 **이중 truth source**로 병존
  (`build_checkpoint_questions.md` 단계3 최우선 리스크).
- **측정**: 세부개념 원자 1,837개는 전부 독립 오개념(`misconception`)을 보유(100%) — 현재 원자
  입도는 과세분되어 있지 않다(Part 2 §1 법칙 충족).
- 대규모 재분할은 전문가 검수 소관이라 즉시 손대지 않고, 기준을 ADR에 명문화 + 회귀 감지
  테스트(`test_node_granularity_governance.py`: 이중 카운트 동결·100% 오개념 커버리지 불변식)만 둠.

## 항목 ② 5노드 — "Concept→Misconception→Skill→ProblemType→Visualization 연결 완성·Formula 나중인가?"

**판정 ✅ (표현 방식 확정).**

- Concept(모델·437)·Misconception(`MisconceptionCatalog` 843·별도 DB·**Phase 4a enrichment**로
  `severity`·`behavior_skills`[arises-in] 추가·이미 완성 노드라 승격 무·additive만)·Visualization
  (선언 명세) 존재. **Skill=`SkillNode` 1급 노드(Phase 2a 승격)**·**ProblemType=`ProblemTypeNode`
  1급 노드(Phase 3 승격·cognitive-action canonical≠surface SignaturePattern)**. anti-explosion 기준
  (canonical·독립추정 가치)을 통과해 승격했고, 연결은 참조 키만(신규 엣지 타입 0).
- **Formula=`FormulaNode` canonical-only 1급 노드(Phase 5a 승격)** → 변형은 노드화 금지·동치는 SymPy
  위임·ID≠Signature. 위험문서 2건 anti-goal 판정을 canonical-only 조건부 허용으로 정식 개정. "Formula는
  마지막" 단계 완료(우선 5노드 전부 승격).
- Concept은 Misconception·Visualization로 *참조 키*(`misconception_codes`·
  `visualization_card_keys`)를 노출 — 5노드가 배선돼 있다(Phase 1 값 일부 미충전이어도 연결
  능력 존재). 결정·재검토 트리거는 ADR §2, 동결은 `test_five_node_connectivity_governance.py`.

## 항목 ③ 순수성 — "ConceptNode가 계층 분리됐고 renderer·prompt·curriculum·misconception·embedding을 안 넣었나?"

**판정 △ → ✅(Stage A+B 완료).**

- renderer·prompt·embedding·curriculum은 **물리적으로 분리돼 있음**(각각 L5 명세·`docs/prompts/`·
  별도 pgvector 테이블·CurriculumEntry Overlay). curriculum은 이미 노드에서 제거된 선례 있음
  (`drop_concept_subject_curriculum_version`).
- **위반(수정 전)**: identity 노드 `Concept`(data-pipeline)에 pedagogy 필드가 내장돼 있었다 —
  `misconception_text`(자유텍스트 오개념·`ConceptContent`+`MisconceptionCatalog`와 삼중 중복)·
  `metaphor`·`accepted_expressions`.
- **수정**:
  - **Stage A**: `misconception_text` 제거(DB 컬럼 미착지·유일 소비처 `common_misconceptions`가 이미
    런타임 비소비로 동결 → 마이그레이션 불필요). graph.json 재생성. 순수성 동결 테스트 신설.
  - **Stage B**: `metaphor`·`accepted_expressions` 제거. 활성 소비처를 pedagogy 계층 `ConceptContent`
    (source_id↔code 조인·437 전단사·값 바이트 동일→재임베딩 0)로 재배선 후 노드·`concept_node`
    컬럼 제거(Alembic `c7d8e9f0a1b2`·write-only 컬럼). 순수성 테스트 금칙 집합에 편입.
  - `difficulty_tier`는 semantic 속성이라 노드 적합(위반 아님) — 4계층 매핑에 명문화.

---

## 잔여 리스크 · 후속

- **입도 재분할**: 세부개념/개념 이중 truth source 통합은 전문가 검수 후 별도 과제.
- **검증**: data-pipeline 642 passed·backend 4,776 passed(비통합)·ruff·black·mypy --strict·
  lint-imports 전부 green. 실 PG 마이그레이션(`c7d8e9f0a1b2` up/down)·통합은 CI에서 검증.
