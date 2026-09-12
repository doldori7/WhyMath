# EOS-53 전환계획 52항목 ↔ 백로그·코드 전수 대조 (2026-09)

> **지위**: `EOS-53-plan52-backlog-crosswalk` 산출물. 입력 = 전환 선언 정본
> `docs/strategy/eos_transition_declaration_2026-08-30.md` **부록 A**(추적표 02 시트 전사)와
> EOS-52 실사 `docs/reviews/eos_anchor_asset_audit_2026-09.md`(B6·B7·F1·I1 판정의 수치 정본).
> 대조 시점: 2026-08-30 · 브랜치 `claude/mvp-eos-transition-plan-ghcajm`(HEAD `366053f8`+작업 트리).
>
> **판정 4분류**: `이미 구현`(실파일 증거 필수) / `부분`(갭 명시) / `신규` / `이월`(T3·T4).
> 이미 구현·부분의 근거는 파일경로(:줄) 또는 실존 태스크 ID(전건 `backlog/tasks/`에 파일 존재
> 확인)다. 문서 언급만으로 '이미 구현' 판정한 행은 없다.
>
> **갭 후보의 태스크 번호는 이 문서가 배정하지 않는다** — 등재는 메인 세션이
> `backlog.py add`로 수행한다(HARN-10: 번호 추론 배정 금지). 본 문서는 후보 번호(#n)와
> 제안 ID *계열*만 적는다.

---

## §0. 요약

**행 수 정정(실측)**: 부록 A 전사는 **53행**(A1~A5·B1~B7·C1~C10·D1~D5·E1~E7·F1~F6·G1~G6·
H1~H4·I1~I3 — `grep -c` 실측 53)이다. 문서 표기 "52건"과 1건 불일치하나, 부록 A의 h 소계
검산(전체 560h·T1 352h)이 **53행 전부를 포함해야 정확히 성립**하므로 53행 전수를 대조
대상으로 삼았다. 원본 xlsx는 저장소 외부라 어느 쪽 표기가 정본인지는 판정 불가 — 표기
사안으로 보고한다.

**판정 분포 (53행)**:

| 판정 | 행 수 | 해당 코드 |
|---|---|---|
| 이미 구현 | **11** | A1 B1 B3 C2 C3 C5 C10 D1 E1 E4 H1 |
| 부분 | **27** | A2 A3 A4 A5 B2 B4 B6 B7 C1 C4 C7 D2 D5 E2 E3 E6 F2 F4 F5 G1 G2 G3 G4 H2 H3 H4 I3 |
| 신규 | **7** | C9 F1 F3 F6 G6 I1 I2 |
| 이월(T3·T4) | **8** | B5 C6 C8 D3 D4 E5 E7 G5 |

부분 27행 중 **11행은 기존 태스크만으로 커버**(신규 등재 불요), 나머지 부분·신규에서
**갭 후보 19건**(§2 — 즉시 13 + 등재 유보 6)을 도출했다. 선언서 §1.1의 대표 8건 사전
대조는 재실측 결과 전부 유지되며, 세부 정정 2건(E4의 DoD 세부 필드·A2의 schema_version
기실재)을 §1 해당 행에 병기했다.

---

## §1. 53행 전수 표

표기: 근거의 경로는 저장소 루트 기준. `√` = DoD 충족 실측, `갭:` = DoD 대비 미충족 축.

### A. EOS 계약 골격

| 코드 | 기능명 | Tier | 판정 | 근거 | 대응 |
|---|---|---|---|---|---|
| A1 | Canonical ID 체계 + Entity Registry | T1 | **이미 구현** | canonical_id 레지스트리·영구 동결 정책 `src/data-pipeline/data_pipeline/concept_graph/registry.py:7-11` · ID 정규식 검증 `CONCEPT_ID_PATTERN`(`math.<area>.<slug>`·교육과정 코드조각 금지) `.../concept_graph/validate.py:340-363`(data-pipeline CI 잡 경유) · DB PK 분리: `problem_id`(UUID PK)≠`external_id`/`slug`/`identity_id` `src/backend/whymath_backend/db/models/problem.py:82-91` · 원자 PK=`code`(의미 ID) `db/models/atom_node.py` | 확장은 ARCH-35(todo·Phase 2 — External ID Registry) |
| A2 | Subject-neutral Content Schema/API Contract | T1 | **부분** | `schema_version` 필드 **기실재**(011_2) `src/backend/whymath_backend/schema/problem.py:255-258` — 선언서 §1.1 표("schema_version 추가"가 S1-16 몫)보다 한 발 앞서 있음. 갭: 수학 전용 4필드의 `extensions.math` 이동 미착수(`extensions` grep 0) · YAML 계약(schemas/v1.1) 노출 · subject-neutral curriculum API | **S1-16**(todo)·**CUR-11**(todo) |
| A3 | 공통 메타데이터(학교급·출처·버전) | T1 | **부분** | `atom_node.school_level`(4급: 초/중/고/대) `db/models/atom_node.py:96` · `problem.source_type` `:94` · `problem.curriculum_version` `:110` · misconception `school_level`(`schema/misconception_catalog.py`). 갭: 버전 축 통일 — 설계만 완료(EOS-44 done), Content/Concept Version 실체화 미착수 | **EOS-47**(todo)·**EOS-49**(todo)·**ARCH-31**(todo)·**ARCH-32**(todo). CU 필수 필드는 EOS-51 ③에서 동결 |
| A4 | 저작권 원장 3종(source_asset/content_item/generation_provenance) | T1 | **부분** | 대응물 상당 착지(#861 머지): `SourceEntity`/`RightsHolderEntity`/`RightsEntity`/`ContentSourceLink`/`ContentRightsLink`/`DerivationEdge` `db/models/rights.py:67-291` · `ContentProvenance`/`GenerationLog` `db/models/provenance.py:45,131` · RightsGateway+`POST /v1/rights/check` `api/rights.py` · `l1/rights/`(gateway·policy_engine·attribution·integration). 갭: LIC-01 완결(**in_progress** — 미머지 브랜치 `claude/lic-01-rights-provenance-mvp{,-2}` 잔존) + "provenance 없는 AI 생성물 INSERT 거부"는 DB CHECK **의도적 미생성**(`provenance.py:48-50` — schema 계층 강제 방침)이라 DoD와 방침 충돌 → 집행 지점 재판정 필요 | **LIC-01**(in_progress) + 갭 후보 **#10** |
| A5 | AI Model Gateway(로컬/클라우드 라우팅) | T1 | **부분** | 게이트웨이 실재: `Router` `l3/router.py:482` · `LOCAL_MODEL_MATRIX` `:54` · providers · 조립 `l3/pipeline.py` · 라우터 경유 원칙(CLAUDE.md 절대 원칙). 갭: **데이터 등급 기반 라우팅 0건**(router·config에서 aihub/data_grade/국외 grep 0) — 부록 E 전제("AI Hub 데이터는 국외 반출 확인 전 로컬 Ollama 전용")의 기계 배선 부재 | 갭 후보 **#11** |

### B. 수학 콘텐츠 스키마

| 코드 | 기능명 | Tier | 판정 | 근거 | 대응 |
|---|---|---|---|---|---|
| B1 | 교육과정 재귀 트리(CurriculumNode) | T1 | **이미 구현**(구조 대응물) | 재귀 트리 = `atom_node.parent_code`(원자→소단원→단원→None) `db/models/atom_node.py:92-94` + `level`·`node_type` 필드 `:92,104` — 고정 6계층 아님 · 4개 학교급 등록 실측(초/중/고/대 — EOS-52: 대학 원자 1,069노드) · `CurriculumFramework`/`CurriculumVersion` 테이블(CUR-10 done) `db/models/curriculum_framework.py:26`. 계획서의 1급 UnitNode 트리는 **의도적 미채택**(2026-08-23 EOS 검토 — Concept 원본·Curriculum Overlay 원칙, CUR-09 notes) | 후속 관측은 **CUR-09**(todo) |
| B2 | 단원 구조 관리 | T2 | **부분** | 앵커 대응 구조 노드 실재(그래프 실측): `중변관-U1-S13` 이차방정식(A4)·`초수연-U2-S7~9` 분수(A1)·`초변관-U3-S2` 비와 비율(A2)·`CALC1-U1-S2` ε-δ(A7)·`LINA1-U4-S2/S3` 일차독립·기저(A8) 등 — 단원 217·소단원 643 · 단원 DSL 파일럿 1건 `data/corpus/units_v1/quadratic_maxmin.unit.yaml`. 갭: "앵커 8개"를 세트로 마킹·등록한 1급 인스턴스 없음(F1과 동일 축) | 갭 후보 **#3**(F1과 통합) |
| B3 | 선수학습 관계 그래프 | T2 | **이미 구현** | PREREQUISITE 엣지 2,210(EOS-52 실측) · backend 적재 어댑터 `l1/atom_graph/atom_backend_edge.py`(`EdgeType.PREREQUISITE`:117) · DAG 강제(구축 플레이북·prerequisite만 DAG). DoD "노드당 평균 차수 ≥1.0": 평균 (in+out) 차수 = 2×2,210/2,683 = **1.65** ≥1.0 충족(리프 1,823 기준 in+out 2.43·단방향 기준 0.82라 정의에 따라 갈림 — 산식 정의는 EOS-51에서 확정 권고) | 학교급 관통 축은 **CUR-06**(todo — F2와 공유) |
| B4 | 개념 DB(원4·8·9 흡수) | T2 | **부분** | 개념 DB 실재: `Concept`/`ConceptEdge`/`ConceptFusion` `db/models/concept.py:55,185,301` · 구 개념그래프 437 + 개념↔원자 crosswalk 437행(EOS-52) · 병합·은퇴 처리 선례(S4-07·S4-08·ARCH-13 전부 done). 갭: `supersedes` 필드 0건(src 전수 grep) — 단 이 축은 12월 검증 비관여 가능성 높음(§0-5 신규 기능 게이트) | **EOS-49**(todo — ConceptVersion 계약)와 연동, supersedes 단독 등재는 유보 권고 |
| B5 | 정의 관리 | T4 | **이월** | (§3) — 단 **S4-05**(정의 레지스터·kind 4종·todo)가 사실상 동일 축을 기등재 | 이월 + S4-05 존재 병기 |
| B6 | 오개념 DB + detection_rule 기계판정형 | T1 | **부분**(핵심 축 신규) | 오개념 DB 843행·crosswalk 64행·L4 카탈로그 64종 실재(`l4/misconception/catalog.py`) — 탐지 3계: substring 64·regex 4·SymPy 2(`wrong_form_match.py` shadow 배선). 갭(EOS-52 §3.4·§6 정본): `detection_rule` 필드 저장소 전수 **0건** · 기계채널(정규식·SymPy)의 앵커 커버 **0** → "앵커 커버분 자동 판정"은 전면 신규 제작 | 갭 후보 **#9** |
| B7 | 문제 DB + 난이도·유형(원18·19·20 병합) | T1 | **부분** | 문제 DB 실재 `db/models/problem.py` — **authored/empirical 분리 충족**: `difficulty_overall`+5축(:187-192, 저작 난이도) vs `irt_difficulty_b`·`historical_correct_rate`(:197,205, 실측 보정) · 예상 오답 `distractor_map`(:154)+`DistractorEntry.op_code` · `achievement_standard_codes`(`schema/problem.py:585`) · 코퍼스 2,638문항(EOS-52). 갭: CU 구성요소 중 **3단계 힌트 영속 미착지**(HintNode 연기 — S4-11 todo) | **S4-11**(todo) + CU 계약 동결은 **EOS-51** ③ |

### C. AI 콘텐츠 생산 (최우선)

| 코드 | 기능명 | Tier | 판정 | 근거 | 대응 |
|---|---|---|---|---|---|
| C1 | 자동 콘텐츠 생성 파이프라인 | T1 | **부분** | 사슬 대부분 실재: 생성 배치 CLI(성취기준 코드 지정·증분 축적·dedup) `harness/problem_corpus_accumulate.py`·`problem_corpus_batch.py` → 수용 게이트(SymPy 검증)→저장 순서 코드 강제 `l3/equivalent/orchestrator.py`(accepted_stored=게이트 통과+적재 완료 시만) → 검수 워크리스트 `harness/needs_review_worklist.py` → 검수 승격 인프라(#841 머지) · Run 로그 스키마 `GenerationLog` `db/models/provenance.py:131` · 실적 generated 619+rephrased 421문항. 갭: **앵커 1개 기준 E2E 실증 + Run 로그 실적재 배선 확인**(G1 게이트 9/27 차단 조건) — pedagogy 축 E2E는 실재(`tests/backend/api/test_e2e_pedagogy_pilot_integration.py` — 컴파일→생성→예심→검수→릴리스 관통) | 갭 후보 **#8** |
| C2 | DSL 콘텐츠 생성기 | T1 | **이미 구현** | `l3/dsl/` 6모듈(compiler·models·quality_gate·repair·validators·variable_engine) · 설계 정본 `docs/architecture/03d_dsl_content_generator.md` · `VariableEngine.generate(seed)`→템플릿 1건에서 시드별 다건 인스턴스(`variable_engine.py:39-74`) · DSL 통합 점검 완료(#756). "1건→CU 10건+" 운영 실적 자체는 I1 캠페인에서 실측 | — |
| C3 | 자동 문제 생성 | T1 | **이미 구현** | 성취기준 코드 단일 입력 생성: `problem_corpus_accumulate --standard-code "[10공수1-02-02]"` 옵션(모듈 docstring 사용법) · 저작권 seed 0 = 자체 코퍼스 seed + provenance 게이트(`ops/provenance_audit.py`) · 실적 619문항(EOS-52 per_bank) | — |
| C4 | 변형문제 생성 | T2 | **부분** | rephrase 파이프라인 재설계 완료(S3-15 done)·rephrased 421문항 · 변형 계보 영속(S4-14 done) · 중복 감사(QUAL-01 done). 갭: 변형 3종 발화(조건·난이도 계열·역문제 — **PB-09** todo)·"동일 skill 변형 5종" 축 미실측 | **PB-09**(todo) |
| C5 | 단계별 풀이 생성 | T1 | **이미 구현** | SolutionPath/SolutionStep 실체화+steps API(S4-09 done·`db/models/solution_path.py:56`) · 인접 단계 동치 3상태 검증(해집합 보존 동치) `l3/verify_step.py` · 라이브 단계 검증 이벤트 영속(S4-19 done) — "인접 단계 동치성 연쇄 검사 통과율 측정 가능" 충족 | — |
| C6 | 다양한 풀이법 생성 | T4 | **이월** | (§3) — 단 실측상 **이미 상당 구현**: S4-10 done — `l3/multi_solution.py`(라우터 경유 생성→SymPy 전건 검증→통과분만 뱅크·ApproachType 6종) | 이월 불필요 가능성 병기(§3) |
| C7 | 힌트 3단계 + 누설 차단 | T1 | **부분** | 힌트 지연 정책 `l4/hint_deferral.py` · 누설 검사 자산 `harness/coach_prose_leak_eval.py`(코치 프로즈 축). 갭: 힌트 3단계 **생성·영속**+정답 누설 자동검사 미착지 — **S4-11**(todo)이 정확히 이 축("graded 1~3·정답 누출 게이트·reveal_score KPI") · 힌트 fading 상한 **PED-35**(todo) | **S4-11**·**PED-35** |
| C8 | 비유/예시·질문 생성 | T4 | **이월** | (§3) — 단 비유·예시 생성기는 회수 완료(**PED-24 done**·analogy_fidelity_eval 실재) | 이월 + 부분 실재 병기(§3) |
| C9 | 연령별 설명 생성(학교급 폭) | T2 | **신규** | 동일 개념 다수준 설명 생성 0건 — concept_content는 개념당 단일 explanation/metaphor(`data/corpus/concept_content_v1/content.json` 키 실측) · 인접 태스크는 축이 다름: S4-05(정의 종류)·PRES-02(표출 프로파일)·KG-06(깊이). F7(언어 수준 부적합) 실패율 측정과 연동 필요 | 갭 후보 **#16** |
| C10 | Prompt Registry/Versioning | T1 | **이미 구현** | 프롬프트 자산 정본화 `l3/prompt_assets.py`(`PROMPT_ASSET_DIR=docs/prompts`:73) · 인라인 프롬프트 감사 `harness/prompt_asset_audit.py`(**OPS-16 done**) · Langfuse 추적(절대 원칙). 잔여 확인 축: 생성물에 prompt_version 스탬프 — `GenerationLog.prompt_template_id` 컬럼은 실재(`provenance.py:154`), 값 배선은 F5와 동일 갭 | 값 배선은 갭 후보 **#2**에 병합 |

### D. 생산물 품질 자동판정

| 코드 | 기능명 | Tier | 판정 | 근거 | 대응 |
|---|---|---|---|---|---|
| D1 | Deterministic Gate(SymPy) | T1 | **이미 구현** | 3-tier 검증 등급 체계 `l3/verification_tier.py`(기계 증명→기계 측정→잔여 검증·`is_exposable` 최종 판단) · 생성→검증(수용 게이트 = `verify_answer`+`verify_solution` 조합 `l3/equivalent/acceptance.py:15-16`)→dedup→저장 순서 **코드 강제** `l3/equivalent/orchestrator.py`(§7 흐름: `accepted_stored`는 게이트 통과+적재 완료 시만) · 사전생성 SeedValidator `l3/pregenerate/validator.py` — 선언서 §1.1의 "연쇄 강제 여부 확인" 재실측 결과 생성 경로에서 강제됨 | 노출측 후속은 **EOS-50**(G3 행) |
| D2 | QA 엔진 — 생산물 합격 판정 | T1 | **부분** | QA 오케스트레이터 실재(**ARCH-21 done**): `harness/qa_pipeline.py` — 9축 조립·단일 JSON+exit 0/1. 갭 ①: CI 강제 미완 — `continue-on-error: true` 존치(`.github/workflows/ci.yml:265-267`·`pending-task:ARCH-23`) ②: F1~F8 실패코드 자동 부여 — 실패코드 자체가 EOS-51 신설이라 부여 로직은 그 후속 | **ARCH-23**(todo) + **EOS-51**(실패코드 enum) |
| D3 | 품질 점수 + 난이도 검증 | T3 | **이월** | (§3) — 기반: 품질 15축 중 2축 승격 선례(ARCH-19 done) | 이월 |
| D4 | 중복 콘텐츠 탐지 | T4 | **이월** | (§3) — 단 **이미 상당 구현**: 구조 dedup(canonical_signature)+임베딩 코사인 dedup이 생성 배치 기본 ON(`orchestrator.py:337-355`) · 코퍼스 중복 감사(QUAL-01·QUAL-02 done) | 이월 불필요 가능성 병기(§3) |
| D5 | Cost/Latency 추적 + HIT 검수 타이머 | T1 | **부분**(핵심 축 신규) | 비용·지연 추적 실재: `GenerationLog.cost_usd`/`latency_ms`(`provenance.py:157-159`) · `ops/cost_probe.py`(인프로세스 이중 회계)·`ops/cost_report.py` · Langfuse. 갭: **HIT 검수 타이머 전무**(전 브랜치 grep 0) — 선언서 §6-6 "★없으면 12월에 잴 것이 없다" | 갭 후보 **#1** (최우선) |

### E. 깊이앵커 폐쇄루프

| 코드 | 기능명 | Tier | 판정 | 근거 | 대응 |
|---|---|---|---|---|---|
| E1 | MathLive 입력 + LaTeX(원28·29 병합) | T2 | **이미 구현** | MathLive 학생 수식 입력 표준(스택 표) · 레이아웃/제출 계약/단계 필드 연동 실기기 검증 완료(**MOB-03·MOB-06·MOB-07 전부 done**). DoD "앵커 A4 문항 입력·표시"는 이차방정식 문항 378건 실재(EOS-52)와 결합해 성립 | 확장(답 형태 계약)은 **EOS-28**(todo) |
| E2 | 채점(결정론 우선, LLM은 설명만) | T2 | **부분** | 결정론 채점 자산 실재: `l3/verify_answer.py`(SymPy 단일 권위) · 서버측 채점 shadow(**NLP-02 done**) · 결함 주입 강등전(**REC-08 done**) · LLM judge는 오개념 매칭 필터·shadow 전용(정오 판정 권위 아님 — `api/coach.py:806-818`). 갭: 채점 권위 이관 **사람 결정 대기**(**REC-07** todo)·커버리지 상한 실측치(REC-05: shadow 파생 0/2,647에서 출발) | **REC-07**(todo·Kiki 결정) |
| E3 | 학습 이력 + Event 적재(skill_ids 복수) | T1 | **부분** | `AttemptEvent` `db/models/activity.py:263` + 힌트/단계/시간 이벤트 3종 머지(**EOS-45·EOS-46·EOS-48 done**·#902·#903). 갭 ①: problem_version·evaluator_version 고정 — **EOS-47**(todo·ARCH-31 선행) ②: **skill_ids[] 복수 영속 좌석 0**(전수 grep — 런타임 브리지 `l2/skill_mastery_tracking.py:182`로 해소는 되나 이벤트에 미영속, 선언서 §5 "미확정→실측 판정" 항목의 실측 확정) ③: writer 배선 빈 좌석 3건(PR #903 자인) | **EOS-47** + 갭 후보 **#4** |
| E4 | Mastery 갱신 + mastery_history | T1 | **이미 구현** | append-only 이력 실재: `ConceptMasteryHistory` `db/models/assessment.py:169` + `SkillMasteryHistory` `:209`(복합 PK user×대상×measured_at — 시계열 불변 적재). 선언서 §1.1 "갭 —" 유지. 정직 병기: DoD 세부 문언(before/after/engine_version 컬럼)은 현행이 측정치 스냅샷+시계열 재구성으로 대체하는 구조라 컬럼 1:1 대응은 아님 — 12월 검증 관여도 낮아 재작업 불요 판단 | — |
| E5 | 진단평가 생성 + 답안 분석 | T3 | **이월** | (§3) — 진단 축 부분 실재(진단 API·MOB-10 done) | 이월 |
| E6 | 오개념 진단+약점+추천(candidates 기록) | T2 | **부분** | 추천 처치 기록 실재(**REC-03 done**): `l2/recommendation_evidence.py` — evidence_event에 problem_id·theta·pool_size·applied_weights·gate_reason meta · 오개념 진단·프로브(REC-02·MISC 계열) · 반복 추천 가시화(REC-06 done). 갭: **candidates[] 전체 후보·policy_version 미영속**(policy_version 전수 grep 0 — 선언서 §5 "미확정→실측 판정"의 실측 확정) · followed 결과 결합은 파일럿 이후로 명시 동결(REC-03 docstring) | 갭 후보 **#5** |
| E7 | 대화형 튜터 + 실시간 피드백 | T4 | **이월** | (§3) — 단 실측상 **대화형 튜터 실재**: WH-1 코치(`api/coach.py` — 소크라테스·오개념 매칭·verify 신호), 계획서의 "힌트 템플릿 대체" 가정은 저장소 실상과 다름 | 이월 + 실재 병기(§3) |

### F. 검증 전용 신규

| 코드 | 기능명 | Tier | 판정 | 근거 | 대응 |
|---|---|---|---|---|---|
| F1 | 앵커 단원 세트 정의·등록 | T1 | **신규** | 앵커 세트의 코드 정의는 EOS-52 산출물뿐: `ANCHOR_DEFS`(`scripts/analysis/eos_anchor_asset_audit.py`)+동결 코드셋 문서(실사 §2) — DB/코퍼스 1급 인스턴스 등록 0건(전 브랜치 anchor grep — EOS-52 계열 커밋뿐). EOS-51 ①이 세트 *결정*을 소유하나 *등록*은 집행 별항 | 갭 후보 **#3** |
| F2 | 학교급 간 개념 수직 연결(분수→유리수→실수) | T2 | **부분** | 학교급 관통 축을 정확히 소유한 태스크 기등재: **CUR-06**(todo — cross-school prerequisite connectivity). 원자 백본은 4급 노드·PREREQUISITE 엣지 실재(B1·B3) — 관통 체인의 존재 여부 실측이 CUR-06 본문 | **CUR-06**(todo) |
| F3 | 앵커 간 생산성 비교 계측 | T1 | **신규** | 앵커별 HIT·비용·수율·실패분포 동일 축 집계 0건(전 브랜치 grep 0). D5(HIT)·F5(Run 로그) 선행 필요 | 갭 후보 **#17** |
| F4 | 휴먼 검수 워크벤치 | T1 | **부분** | 검수 큐 UI 기등재(**ADMIN-07** todo — needs_review_worklist 소비·상태 전이·감사 로그)+검수 자산 실재(needs_review_worklist·reviewer_sample_package·검수 승격 #841). 갭: **HIT 타이머·반려코드 입력 강제** — ADMIN-07 acceptance에 미포함(실파일 확인) → acceptance 확장 필요(신규 축) | **ADMIN-07** + 갭 후보 **#1**의 acceptance 연동(확장 수단: acceptance amend CLI는 HARN-24 todo·미실재 실측 — 확장 방식은 메인 세션 판정) |
| F5 | 생성 Run 재현성 로그 | T1 | **부분** | `GenerationLog` 실재(model_name·tokens·cost·latency·prompt_template_id `provenance.py:139-165`)+어댑터 `l3/pregenerate/provenance_bridge.py`. 갭: **seed·입력 스냅샷 필드 0** · prompt_version 값 배선 미확인 · "재현" 계약(동일 입력 재실행) 테스트 0 | 갭 후보 **#2** |
| F6 | 검증 결론 리포트 자동 집계 | T1 | **신규** | Go/Conditional/No-Go 지표표 자동 생성 0건(전 브랜치 grep 0). ★최종 산출물(P4) | 갭 후보 **#18**(등재 시점 유보 가능) |

### G. 저작권 컴플라이언스

| 코드 | 기능명 | Tier | 판정 | 근거 | 대응 |
|---|---|---|---|---|---|
| G1 | provenance 미기입 INSERT 차단 | T1 | **부분** | 코퍼스 파일측 게이트 실재(**ARCH-20 done**): `ops/provenance_audit.py`(license/source_type 결손 exit 1·`:108,201`)이 qa_pipeline 축 6으로 흡수(`harness/qa_pipeline.py:418-427`). 갭: **DB INSERT 차단은 없음** — ContentProvenance는 DB CHECK 의도적 미생성(schema 계층 강제 방침 `provenance.py:48-50`), DoD("origin='ai_*' INSERT 실패")와 방침이 충돌 → 어느 계층에서 집행할지 결정 필요 | **LIC-01** 잔여 + 갭 후보 **#10** |
| G2 | 금칙 소스 스캔 CI | T1 | **부분** | policy-guard CI 잡 **상시 차단** 실재(`.github/workflows/ci.yml:1038-1081`): 검정교과서 출판사 5종×본문/예제 패턴 + 시크릿 패턴 → exit 1(continue-on-error 없음). 갭: **EBS·평가원(수능/모평) 패턴 미포함**(패턴 문자열 실측: 천재교육·비상교육·미래엔·동아출판·신사고뿐) | 갭 후보 **#7**(소형 — 기존 잡 확장) |
| G3 | publish 허용 매트릭스(tier×등급) | T1 | **부분** | 노출 게이트 자산 실재: `is_exposable`(`l3/verification_tier.py`) · 학생 노출 경로 게이트 3축(**PB-03 done**) · 품질 게이트 승격(ARCH-19 done). 갭: tier×등급 publish 매트릭스 미구현 — **EOS-50**(todo·publish gate 파이프라인) + 공개 카탈로그 무게이트(**PB-08** todo) | **EOS-50**·**PB-08** |
| G4 | seed 오염 전파 검사(재귀 CTE) | T2 | **부분** | 기반 실재: `DerivationEdge`(파생 계보 테이블) `db/models/rights.py:288`. 갭: 조상 최악 등급 `effective_grade` 재귀 CTE 상속 0건(전수 grep 0) | 갭 후보 **#14** |
| G5 | 유사도 게이트(MinHash+임베딩·원문 미보관) | T3 | **이월** | (§3) — 인접 자산: 생성측 임베딩 코사인 dedup 실재(중복 방지 목적·저작권 목적 아님) | 이월 |
| G6 | 라이선스 스냅샷 아카이버 + 감사로그 | T1 | **신규** | Tier1 소스 약관 HTML+SHA256 아카이빙 0건(`l1/rights/` grep 0 · LIC-01 acceptance 8항에 미포함 실파일 확인 · 전 브랜치 grep 0). 선언서 §5 "미포함이면 분리 등재" 지시의 실측 확정. **★소급 불가 — 시급** | 갭 후보 **#6** |

### H. 기반·계측

| 코드 | 기능명 | Tier | 판정 | 근거 | 대응 |
|---|---|---|---|---|---|
| H1 | 계층 의존 린트 + 금칙 CI | T1 | **이미 구현** | import-linter 7계층 단방향 상시(`.github/workflows/ci.yml:323-324` — `lint-imports`). EOS Core/Subject 축은 별개 결정(선언서 §1.3-③ — W1은 S1-16 계약 수준만) | — |
| H2 | 데이터 무결성 게이트(v_integrity_violations) | T1 | **부분**(뷰·게이트 신규) | `v_integrity_violations` 0건(전수 grep — 선언 문서 언급뿐). 인접 자산 산재: crosswalk 게이트 계약(코드 동결)·임베딩 네임스페이스 거버넌스 테스트·orphan 진단/정리 도구(`scripts/diagnose_atom_orphans.py`·S2-04 done). 갭: 6종(orphan·dangling·duplicate) **단일 뷰+exit 게이트** | 갭 후보 **#12** |
| H3 | 폐쇄루프 E2E 골든 3종 | T2 | **부분** | E2E 통합 3종 실재(실 PG·CI 통합 잡): `tests/backend/api/test_e2e_vertical_slice_integration.py`(온보딩→진단→문제→풀이→코치→verify)·`test_e2e_pedagogy_pilot_integration.py`(5단계 파이프라인)·`test_e2e_suneung_loop_integration.py` + nightly 스케줄(`ci.yml:17-18` cron 0 18 * * *). 갭: **선수결손·오개념 시나리오** 골든 명시 구성 없음(현행은 정상 경로 중심) | 갭 후보 **#15**(소형) |
| H4 | 주간 지표 자동 집계 cron(7지표) | T1 | **부분**(cron 신규) | 리포트 CLI 자산 다수 실재(`harness/`·`ops/` — coverage·reach·cost_report 등). 갭: **주간 cron 0건**(workflows 스케줄 = daily CI·harness-audit뿐) · `metrics/weekly.json` append 없음 · 러너 배선 자체가 미완(**OPS-19** todo — 리포트 11개 중 10개 러너 0건) · 경보 last-hop(**OPS-30** todo) | 갭 후보 **#13** + **OPS-19**·**OPS-30** |

### I. 콘텐츠 생산 운영

| 코드 | 기능명 | Tier | 판정 | 근거 | 대응 |
|---|---|---|---|---|---|
| I1 | 앵커 8×CU 생산 운영(폭 7×60 + 깊이 150) | T1 | **신규**(운영) | 생산 캠페인 실적 0 — EOS-52 실측: 문항 있는 앵커는 A4(378)·A6(261)뿐, 나머지 6개 앵커 0. 전제(D5·F1·F5·검수 강제) 미비 | 갭 후보 **#19**(G1 통과 후 등재 권고) |
| I2 | 인간 표본 검수 235 CU | T1 | **신규**(운영) | 표본 검수 캠페인 0 — 검수 도구 자산은 부분 실재(F4 행). 부록 E 권고 채택 시 235→160 CU | 갭 후보 **#19**와 동반 |
| I3 | 깊이앵커 학생 표본 20~30명 반응 수집 | T2 | **부분** | 학생 표본 수집 태스크 기등재: **S3-01**(pilot-cohort todo — 모집·KPI 베이스라인·착수 트리거 4종 명문) + 측정 하네스(S3-04 done·pilot_kpi_baseline.py). 갭: EOS 재정의(깊이앵커 대상·Spearman ρ 산출)로의 acceptance 정렬 | **S3-01**(todo) — acceptance 확장 검토(신규 등재 불요) |

---

## §2. 갭 후보 — 등재 필요 목록

**공통 규약**: ① 태스크 번호는 `backlog.py add`가 배정(HARN-10 — 아래 "계열"은 접두 제안일
뿐이다) ② 각 acceptance 초안은 측정 계약(수치·exit 판정)과 **정본화≠집행 별항**을 포함
③ §0-5 신규 기능 게이트("12월 검증에 필요한가") 통과 근거를 1줄 병기 ④ 기존 태스크로
커버되는 부분 판정 11행(A2·A3·B4·B7·C4·C7·D2·E2·F2·G3·I3)은 후보에서 제외했다(중복 등재
금지).

### 2.1 W1~W2 등재 권고 (13건)

**#1 [D5+F4] HIT 검수 타이머 + CU 단위 생산 계측** — 계열 `EOS-5x` · T1 · 원 계획 10h
- 근거: HIT 타이머 전무(전 브랜치 0) — 주 기준 지표(HIT 중앙값≤4분)를 잴 계측기 자체가 없음. §0-5: G1 차단 조건("HIT·실패코드 이벤트 적재")이자 선언 §6-6 "★없으면 검증 불가".
- acceptance 초안: ① 검수 세션 타이머 이벤트 스키마+writer(CU 단위 HIT 초·시작/종료·중단 구분) — "작동한 비율" 원칙(응답 200≠계측: 타이머 이벤트 적재율을 리포트가 말한다) ② CU당 토큰·금액 결합 집계 CLI(exit 0/1·`ops/cost_probe` 로컬 이중 회계 준수) ③ **집행 별항**: 검수 UI(ADMIN-07)가 타이머·반려코드 없이는 판정 제출 불가함을 후속 태스크 ID로 명시(ADMIN-07 acceptance 확장 — 단 amend CLI는 HARN-24 todo로 미실재 실측: 확장 방식은 등재 시 메인 세션이 판정) ④ 측정 실패가 "0분"으로 위장되지 않는 실패 경로 설계(2026-08-22 규칙).

**#2 [F5+C10 잔여] 생성 Run 재현성 로그 완결** — 계열 `EOS-5x` · T1 · 원 계획 8h
- 근거: GenerationLog에 seed·입력 스냅샷 필드 0·prompt_version 값 배선 미확인. §0-5: G1 차단 조건(Run 로그 적재)·F-Ⅲ 실패분포 분석의 전제.
- acceptance 초안: ① GenerationLog(또는 확장 테이블)에 prompt_version·model·seed·입력 스냅샷(해시+참조) 기록 — alembic ② 재현 계약 테스트: 동일 Run 레코드로 재실행 시 동일 입력이 복원됨을 동결 ③ **집행 별항**: `problem_corpus_accumulate`·`pregenerate` 두 생성 경로가 실제로 이 로그를 적재함을 통합 테스트로 확인(정본화≠집행 — GenerationLog는 이미 있으나 적재 배선이 미확인이라는 것이 이 태스크의 존재 이유).

**#3 [F1+B2 잔여] 앵커 세트 1급 등록** — 계열 `EOS-5x` · T1 · 원 계획 6h
- 근거: 앵커 정의가 EOS-52 스크립트 상수에만 존재. §0-5: G0 산출(앵커 8 vs 6 결정)의 집행 별항 — 전 계측(F3·I1)이 이 등록을 조인 축으로 씀.
- acceptance 초안: ① G0 확정 앵커 세트(8 또는 6)를 성취기준 코드(EOS-52 §2 동결 코드셋)와 함께 코퍼스/DB 1급 인스턴스로 등록(YAML=소스·DB=산출물 단방향 관례) ② 등록 무결성 게이트: 앵커 코드가 성취기준 데이터에 실재함을 CI에서 검사(코드 소멸 시 적색) ③ **집행 별항**: EOS-52 실사 스크립트·생산 배치가 하드코딩 대신 이 등록을 읽도록 전환하는 후속 지점 명시.

**#4 [E3 잔여] problem_attempted skill_ids[] 복수 영속** — 계열 `EOS-5x` 또는 `DP-0x` · T1(W2 "되돌릴 수 없는 스키마" ①)
- 근거: 이벤트에 skill_ids[] 좌석 0(런타임 브리지로만 해소). §0-5: 선언 §5가 "갭이면 태스크 등재·착수"로 지정 — 소급 불가 스키마(12월 데이터에 남길 축).
- acceptance 초안: ① attempt_event에 skill_ids[](채점 시 해소된 스킬 배열) 영속 — alembic+writer 배선 ② 기록률 리포트("작동한 비율": 신규 attempt 중 skill_ids 비어있지 않은 비율) ③ **집행 별항**: 소비 지점(skill_mastery_tracking이 이벤트 기록을 읽는 전환)은 후속 태스크 ID로 분리. EOS-47(version 고정)과 같은 테이블 — 마이그레이션 체인 조율 명시.

**#5 [E6 잔여] recommendation candidates[]·policy_version 영속** — 계열 `REC-xx` 또는 `EOS-5x` · T2(W2 스키마 ②)
- 근거: policy_version 전수 grep 0·후보 목록 미영속. §0-5: 선언 §5 지정 — 추천 효과 분석의 소급 불가 축.
- acceptance 초안: ① 추천 처치 기록(REC-03의 evidence_event 좌석)에 candidates[](후보 problem_id·점수)와 policy_version 추가 — 비민감 meta 계약(B1 원칙) 유지 ② followed 결합은 여전히 파일럿 이후임을 명문(범위 밖 별항) ③ 기록률 리포트 동반.

**#6 [G6] 라이선스 스냅샷 아카이버** — 계열 `LIC-xx` · T1 · 원 계획 6h
- 근거: 0건 실측·LIC-01 범위 밖 확인. §0-5: ★소급 불가 — 지금 약관을 캡처하지 않으면 12/31 산출물의 라이선스 근거를 영원히 재구성 불가.
- acceptance 초안: ① Tier1 소스(선언 기준 14곳 — 목록은 `licensing_safety.md` 대조로 확정) 약관 HTML+SHA256+수집 시각 아카이빙 스크립트(실패 경로 설계: 소스별 즉시 flush·타임아웃·원인 기록) ② 감사로그 테이블/파일 규약+재수집 멱등 ③ **집행 별항**: 주기 재수집(cron)은 후속(H4 축과 조율) — 1차는 수동 1회 실행 증적.

**#7 [G2 잔여] policy-guard 금칙 소스 패턴 확장** — 계열 `OPS-xx` · T1 · 원 계획 2h(소형)
- 근거: EBS·평가원 패턴 미포함 실측. §0-5: 저작권 레일(불변 계약)의 커버리지 구멍.
- acceptance 초안: ① `ci.yml` policy-guard에 EBS·평가원(수능·모의평가) 본문 인용 의심 패턴 추가 — 기존 잡 확장(신규 잡 금지) ② 오탐 우회 규약(#codeowner-ack) 유지 ③ 변별력 실측: 위반 픽스처 주입 시 실제 적색을 1회 실증(변별력 없는 검증 스텝 금지).

**#8 [C1 잔여] 앵커 1개 생성→검증→검수큐 E2E 실증** — 계열 `EOS-5x` · T1
- 근거: 사슬 부품은 전부 실재하나 앵커 축 관통 실증 0. §0-5: G1(9/27) 차단 조건 그 자체.
- acceptance 초안: ① 깊이앵커(A4) 성취기준 코드로 생성 배치→SymPy 게이트→저장→needs_review 워크리스트 생성까지 1회 관통(실측 로그 첨부) ② 관통 중 GenerationLog·(#1·#2 착지 시) HIT/Run 로그가 실제 적재됐음을 행 수로 확인 — 간접 신호(정상 응답) 금지 ③ **집행 별항**: 상시화(nightly 골든 승격)는 후속 ID 명시.

**#9 [B6 잔여] 앵커 커버 오개념 기계판정형 탐지 제작** — 계열 `MISC-xx` 또는 `EOS-5x` · T1 · 원 계획 10h
- 근거: EOS-52 §3.4/§6 — detection_rule 필드 0·기계채널 앵커 커버 0(전면 신규). §0-5: 내용 KPI "오개념 연결(OP 라벨 정확도 ≥85%)" 측정 전제.
- acceptance 초안: ① G0 확정 앵커의 오개념 커버분(현행 A4=8·A6=8 등)에 정규식 또는 SymPy 술어(`canonical_wrong_form` 선례) 탐지 채널 부여 — L4 카탈로그 3계 채널 위에 증설(신규 명명 체계 금지·kebab 체계 유지, EOS-52 §5) ② 탐지 변별력: 양성/음성 픽스처로 검출·비검출 양쪽 실측(Wilson 경계 CLI) ③ **집행 별항**: 생성 파이프라인 F6(오개념 오연결) 자동 부여 결선은 D2 후속과 공유.

**#10 [G1+A4 잔여] provenance 강제 집행 지점 결정·배선** — 계열 `LIC-xx` · T1 · 원 계획 2h+α
- 근거: DB CHECK 의도적 미생성 방침(schema 계층 강제) vs DoD "INSERT 거부"의 충돌 실측. §0-5: 저작권 레일 — F-Ⅱ(오류율) 산정 시 AI 생성물 전수의 출처 보장 전제.
- acceptance 초안: ① 방침 재판정 문서화: DB NOT NULL/CHECK vs 서비스 계층 단일 진입 강제 중 택1(현행 방침 유지 시 그 근거와 우회 불가능성 증명) ② 택한 계층에서 origin='ai_*' 무-provenance 기록이 실제 거부됨을 뮤테이션 테스트로 동결(cp 백업 원복 규칙 준수) ③ LIC-01 완결(in_progress·미머지 브랜치 2본)과의 경계 명시 — LIC-01 착지 후 잔여만 이 태스크가 소유.

**#11 [A5 잔여] 데이터 등급 기반 라우팅 정책 배선** — 계열 `EOS-5x` 또는 `OPS-xx` · T1
- 근거: 라우터에 데이터 등급 축 0건. §0-5: 부록 E 전제("AI Hub 데이터 국외 반출 확인 전 로컬 전용")의 기계화 — 위반 시 법적 리스크가 12월 산출물 전체에 소급.
- acceptance 초안: ① RoutingRequest에 데이터 등급(원천: AI Hub 유래 여부) 신호 추가 + AI Hub 유래 콘텐츠 포함 요청은 클라우드 티어 차단(로컬 강제) — 라우터 순수 결정 로직에 배선(직접 호출 금지 불변) ② 차단 발동률 리포트("작동한 비율") ③ **집행 별항**: 호출부가 등급 신호를 실제로 채우는지 소스 스캔 게이트(미지정=최고 등급 보수 기본값).

**#12 [H2] 데이터 무결성 게이트 v_integrity_violations** — 계열 `OPS-xx` · T1 · 원 계획 5h
- 근거: 단일 뷰·게이트 0건(산재 자산뿐). §0-5: G3 차단 조건("메타 누락 0")·CU 메타 완결성 판정 도구.
- acceptance 초안: ① orphan·dangling·duplicate 6종을 한 뷰(또는 동등 CLI)로 — 0건=exit 0 ② 위반 주입 변별력 실측 ③ **집행 별항**: CI 잡 배선 실재 확인(tests/infra 배선 계약 선례 — "저장소에 존재함≠돌아감").

**#13 [H4] 주간 지표 자동 집계 cron** — 계열 `OPS-xx` · T1 · 원 계획 4h
- 근거: 주간 cron 0건(daily 2종뿐)·weekly.json 없음. §0-5: 주간 리듬(W1~W17)의 계기판 — G2~G4 판정 데이터의 시계열.
- acceptance 초안: ① 월 07:00 KST cron(UTC 변환 명시)으로 7지표 `metrics/weekly.json` append(무엇을 7지표로 할지는 EOS-51 KPI에서 인용) ② 측정 실패가 "지표 0"으로 위장되지 않는 실패 경로(미측정≠0 구분) ③ 경계 명시: 러너 배선(OPS-19)·경보 last-hop(OPS-30)과 중복 등재 금지 — 이 태스크는 cron+append+최소 경보만.

### 2.2 등재 유보 권고 (6건 — 직전 주 등재 원칙·게이트 순차 등재와 동형)

**#14 [G4] seed 오염 전파 검사(재귀 CTE effective_grade)** — 계열 `LIC-xx` · T2 · W3~W4 등재. DerivationEdge 위에 조상 최악 등급 상속 — 파생 생성(C4·변형)이 본격화되는 시점 전이면 충분.
**#15 [H3 잔여] 폐쇄루프 골든 선수결손·오개념 시나리오 추가** — 계열 `OPS-xx` · T2 소형 · G4(수동 개입 0 루프) 전 등재. 기존 E2E 3종에 시나리오 2종 증설.
**#16 [C9] 연령별 설명 생성(4개 언어 수준)** — 계열 `EOS-5x` · T2 · W3+(폭 앵커 착수 시). F7 실패율 측정 계약 동반 — S4-05·PRES-02와 경계 명문 필수(정의 종류·표출 프로파일과 3분립).
**#17 [F3] 앵커 간 생산성 비교 계측** — 계열 `EOS-5x` · T1 · #1·#2 착지 후(G2 전) 등재. 앵커별 HIT·비용·수율·실패분포 동일 축 리포트.
**#18 [F6] 검증 결론 리포트 자동 집계** — 계열 `EOS-5x` · T1 · 11월(G4 전) 등재. Go/Conditional/No-Go 지표표 — 실패정의 F-Ⅰ~Ⅴ(G0 동결본)를 위반 판정 가능 형태로 기계 대조.
**#19 [I1·I2] 앵커 CU 생산·표본 검수 운영 캠페인** — 계열 `EOS-5x` · T1 · G1 통과 후 등재(생산 도구 없이 캠페인 태스크만 먼저 만들면 대장 부패). I3은 기존 S3-01 acceptance 정렬로 흡수.

---

### 2.3 등재 결과 (2026-08-30 — `backlog.py add` 배정, validate green)

| 후보 | 배정 ID | 후보 | 배정 ID |
|---|---|---|---|
| #1 | `EOS-54-hit-review-timer-cu-metrics` (prio 1) | #8 | `EOS-58-anchor-e2e-generation-proof` (prio 1) |
| #2 | `EOS-55-generation-run-reproducibility` (prio 1) | #9 | `MISC-07-anchor-machine-detection-channels` |
| #3 | `EOS-56-anchor-set-registration` (requires G-eos-g0) | #10 | `LIC-03-provenance-enforcement-layer-decision` |
| #4 | `EOS-57-attempt-skill-ids-persistence` (prio 1) | #11 | `EOS-59-data-grade-routing-policy` |
| #5 | `REC-11-candidates-policy-version-persistence` | #12 | `OPS-55-integrity-violations-gate` |
| #6 | `LIC-02-license-snapshot-archiver` (prio 1) | #13 | `OPS-56-weekly-metrics-cron` |
| #7 | `OPS-54-policy-guard-source-patterns` | — | — |

등재 중 부수 발견: `LIC-01`의 stage가 **E2**로 등재돼 있어 S3 태스크의 형식 `depends_on`이
로드맵 가드에 거부됨(실측) — LIC-03은 선행을 acceptance 문언으로 표현. LIC-01 stage의 실질
(12월 저작권 레일) 정합 재조정은 Kiki/후속 판단 사안으로 병기. 유보 6건(#14~#19)은 §2.2의
등재 시점 트리거가 만료 조건이다(만료 없는 유예 금지 준수).

---

## §3. 이월 목록 (T3·T4 — 등재하지 않음 · 2027 이월)

선언서 §3.2-① 지시대로 8건 전부 **등재하지 않고** 여기 문서화한다. 단, 4건은 저장소에
이미 부분·전체 대응물이 있어 "이월"의 실질이 다르다 — 2027 재개 시 이 표의 실측을 먼저 볼 것.

| 코드 | 항목 | Tier | 이월 사유 (1줄) |
|---|---|---|---|
| D3 | 품질 점수 + 난이도 검증 | T3 | 주 25h 시나리오 전용 확장 — 기반(품질 15축 중 2축 승격·ARCH-19 done)은 있으나 12월 판정에 불요 |
| D4 | 중복 콘텐츠 탐지 | T4 | **이월 불필요 가능성** — 구조+임베딩 dedup이 생성 배치 기본 ON(`l3/equivalent/orchestrator.py`)·코퍼스 중복 감사 완료(QUAL-01·02 done). 2027 재개 시 "신규 구축"이 아니라 임계 보정 과제 |
| B5 | 정의 관리 | T4 | B4 흡수 가능 예비 — 동일 축 태스크 S4-05(정의 레지스터·todo)가 기등재라 재개 시 신규 등재 불요 |
| C6 | 다양한 풀이법 생성 | T4 | **이월 불필요 가능성** — S4-10 done: `l3/multi_solution.py`(ApproachType 6종·SymPy 전건 검증) 실재. 잔여는 학생 대면 서빙 유보 해제뿐 |
| C8 | 비유/예시·질문 생성 | T4 | 비유·예시 생성기 회수 완료(PED-24 done) — 잔여는 질문 생성 축과 서빙 결선 |
| E5 | 진단평가 생성 + 답안 분석 | T3 | 진단 축 부분 실재(진단 API·MOB-10 done) — EOS 검증에는 폐쇄루프 계측기(A4 깊이앵커)로 충분 |
| E7 | 대화형 튜터 + 실시간 피드백 | T4 | **계획서 가정과 실상 상이** — WH-1 코치(`api/coach.py`)가 이미 대화형 튜터. "힌트 템플릿 대체"는 불요하며, 2027 과제는 신규 구축이 아니라 라이브 승격(S1-11 flip 계열) |
| G5 | 유사도 게이트(MinHash+임베딩·원문 미보관) | T3 | 저작권 목적 유사도(8-gram 0.7/코사인 0.85·원문 미보관)는 외부 소스 대량 인입 국면 과제 — 현행은 자체 생성 seed 0 원칙이라 12월 위험 낮음 |

---

## §4. 대장 명문화 — registry.yaml·MP-0·DECISIONS.md는 이 저장소에서 무엇인가

전환 계획서(006·설계서·추적표 08 시트)가 지시한 대장 3종은 **신설하지 않는다**(선언서
§1.3-① 재확인·본 crosswalk로 집행 완료). 이중 진실원천은 이 저장소가 명문으로 금지한
붕괴 경로다(CLAUDE.md 유지보수 지옥 방어·단일 진실 원천).

| 계획서 개념 | 이 저장소의 정본 | 비고 |
|---|---|---|
| MP-0 `registry.yaml` (전 항목 대장) | **`backlog/`**(tasks 436파일 + gates.yaml + events.ndjson + policy.yaml) — "다음 할 일"은 `backlog.py next`가 계산 | 본 문서 §1의 "대응" 열이 52(53)항목→기존 태스크 ID 매핑 그 자체다. 별도 매핑 파일도 만들지 않는다(이 문서가 1회성 판정 기록, 이후 추적은 backlog) |
| MP-0 6축 채점(구현·테스트·문서·배선·측정·검수) | 하네스 acceptance(측정 계약·정본화≠집행 별항) + `backlog.py done` 증적 검사(PR 증적 게이트·HARN-23) + CI 게이트(배선 실재는 `tests/infra/test_test_suite_wiring.py` 계약) | 6축을 별도 점수표로 재기입하지 않는다 — acceptance 문장이 축이다 |
| `DECISIONS.md` (ADR) | **MEMORY.md 결정 로그** + `docs/architecture/*.md`(설계 정본) | 본 crosswalk의 채택도 MEMORY 결정 로그로 기록(메인 세션 몫) |
| 이월 목록(T3·T4 POSTPONE) | backlog 미등재 + **본 문서 §3**(사유 포함) — 재개 트리거는 2027 계획 수립 시 | "만료 없는 유예 금지" 규칙 적용: §3의 재확인 지점 = 2027 계획 수립 시(G5 판정 산출물의 2027 범위 결정과 동시) |
| 게이트 G0~G5 | 하네스 사람 게이트 대장(`backlog/gates.yaml`) — G0은 `G-eos-g0-verification-design-freeze` 기등재, G1~G5는 직전 주 순차 등재 | 선언서 §1.3-② 그대로 |

---

## §5. 판정 방법·한계

**절차** (각 행 공통 — CLAUDE.md "trunk 부재를 미구현으로 단정 금지" 준수):
1. **코드·스키마·CI 실측** — Grep/Read로 실파일 확인(경로:줄 인용). 검사성 명령은 exit code·실출력으로 판정.
2. **기존 태스크 매핑** — `backlog/tasks/` 436파일 대조. 본 문서가 인용한 태스크 ID는 전건 실파일 존재+`status:` 실측(done/todo/in_progress/blocked/review)을 확인했다.
3. **미머지 브랜치 확인** — 코드 0건 판정 전 `git log --all --grep`(가시 커밋 1,896건)·`git branch -r`(원격 31브랜치) 검색. 원격 claim 대장(`origin/harness-claims`)도 확인 — 활성 claim은 EOS-53(본 태스크) 1건뿐, 신규 판정 항목의 병렬 인플라이트 없음. 특기: LIC-01 미머지 브랜치 2본(`claude/lic-01-rights-provenance-mvp{,-2}`) 존재 — A4·G1 판정에 반영.
4. **그래도 0이면 신규** — C9·F1·F3·F6·G6·I1·I2의 7건이 이 경로로 확정됐다.

**한계 (정직 명시)**:
- **shallow clone** — 본 클론은 `--is-shallow-repository: true`, HEAD 히스토리 57커밋(경계 `4471689e`·`5c4dda20`)만 보유. `git log --all`은 원격 브랜치 팁 기준 1,896커밋을 보나 **각 브랜치의 절단 이전 히스토리는 검색 불가**다. 따라서 "전 브랜치 grep 0" 판정은 가시 창 안의 부재 증명이며, 절단 이전에 만들어졌다 버려진 코드는 원리적으로 놓칠 수 있다. 완화: 판정의 1차 근거는 히스토리가 아니라 **현행 작업 트리 실파일**이고, 히스토리 검색은 "신규" 판정의 보강 증거로만 썼다.
- **prod DB 미접근** — 이 샌드박스는 whymath-pg(5433) 접근 불가. DB 적재분 판정은 저장소 파일 정본 원칙(YAML/JSON=소스·DB=산출물)에 의존하며, 적재 드리프트 확인은 EOS-52 부록 A의 Kiki 머신 명령으로 별도 수행.
- **원본 xlsx 미접근** — 부록 A 전사(53행)를 원본 "02_개발항목 52"와 재대조할 수 없다. h 소계 검산(560/352h 일치)으로 전사 정합을 간접 확인했고, "52건" 표기와의 1건 차이는 §0에 보고했다.
- **DoD 문언의 해석 여지** — B3(평균 차수 정의)·E4(before/after 컬럼 대 시계열 재구성) 등 DoD 문언과 구현 형태가 1:1이 아닌 행은 해석을 근거 열에 명시하고, 산식·형태 확정이 필요한 것은 EOS-51로 넘겼다. 판정 불확실 행을 '이미 구현'으로 올려 적은 곳은 없다(불확실은 전부 '부분'+갭 명시).
- **acceptance 초안은 초안이다** — §2의 초안은 등재 시 `backlog.py add` 시점에 메인 세션이 확정한다. 특히 소요(h)는 계획서 가정값 인용일 뿐 재추정하지 않았다(선언서 §6-4 — W6~W8 첫 실측에서 보정).

---

*작성: EOS-53 세션 (2026-08-30). 본 문서는 판정 기록이며, 등재 집행(backlog.py add)과
MEMORY 결정 로그는 메인 세션이 수행한다.*
