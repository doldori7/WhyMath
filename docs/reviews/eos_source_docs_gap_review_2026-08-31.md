# 첨부 계획문서 2종 ↔ 저장소 실측 대조 — 차이·수정 후보 (2026-08-31)

> **대상 기준 문서** (Kiki 제공·저장소 외부):
> ① `006_MVP 개발 종료·EOS 전환 코딩·절차 체크리스트`(기준일 2026-08-27 · 50개 항목 + §49 완료판정 체크리스트 A~I + §50 최우선 10건)
> ② `100_Phase 0 — Architecture Reset & Scope Freeze 상세 실행계획`(8/27~9/6 · 산출물 P0-01~P0-10 · Day 1~11 · Gate 0 A~E · Rule 1~6 · 대시보드 5숫자)
>
> **대조 시점**: main `3f512962`(#921) · 2026-08-31 · 원격 브랜치 36 · 열린 PR 16.
> **성격**: 대조는 조사 전용(코드 변경 0). 대장 변경은 **A급 5건 등재만** — Kiki 지시(2026-08-31)에 따라 `backlog.py add`로 집행했고 게이트는 손대지 않았다. B급 8건은 미등재 후보로 남는다(§5).
>
> **선행 문서와의 관계 (중복 회피)**: 저장소는 이미 ①을 흡수한 정본
> `docs/strategy/eos_transition_declaration_2026-08-30.md`(선언)와 그 준수 감사
> PR #916 `eos_transition_plan_compliance_audit_2026-08-31.md`를 가진다. **본 문서는 선언을
> 기준으로 삼지 않고 첨부 원문 ①②를 기준으로 되짚는다** — 선언이 ①을 번역하며 *의도적으로
> 바꾼 지점*과 *번역 과정에서 떨어진 지점*은 선언 준수 감사로는 구조적으로 보이지 않기
> 때문이다. ①②에만 있고 선언에 없는 축(②의 P0-02 기능 인벤토리·Migration Difficulty
> Matrix·Gate 0 A~E, ①의 §12 Feature Flag·§20 에러코드·§21 환경분리·§23 README)이 그
> 사각이며, 실제로 갭 대부분이 거기서 나왔다.

---

## §0. 요약

**결론 3줄**

1. ①의 기술·엔지니어링 축(§9 마이그레이션·§15 CI·§34 API 버저닝·§38·39 AI 검증 분리·§18 E2E)은 **첨부 문서가 요구한 수준을 이미 넘어선다** — 첨부 문서가 저장소를 보지 않고 쓰였기 때문이다(선언 §1도 같은 지적).
2. **②(Phase 0)는 흡수율이 낮다.** 10개 산출물 중 **온전 충족 0 · 부분 6**(P0-01·03·04·07·08·10) **· 갭 4**(P0-02·05·06·09)이며, **갭 4건 중 3건이 "분류·판정" 축**(P0-02 기존 기능 인벤토리 · P0-09 Migration Map · P0-03도 등급 축이 부분)이다. ②가 "Phase 0의 목적은 코딩이 아니라 분류"라고 못박은 바로 그 부분이 빠졌다.
   *(2026-08-31 정정 — 초판은 "충족 2·부분 5·미착수 3"으로 적어 §2 표와 모순됐다. 표가 옳다. 리뷰 봇 지적 수용.)*
3. 실제 갭 **13건**(A급 5·B급 8 — B급은 "미착수"가 아니라 "처리 후보"를 포함한 넓은 집합이라 §0 표의 ① 갭 5건과 모집단이 다르다). 그중 **A1 Subject Contract 실체 부재**와 **A2 Core↔Adapter 정적 경계 미강제**는 G1(9/27) 차단 조건("Core→Math 정적 의존 0")에 직결되므로 9월 내 처리가 필요하다.

**판정 분포** *(리뷰 봇 지적 3건 수용 후 — §6-5 참조)*

| 판정 | 정의 | ① 50항 | ② 기준 |
|---|---|---|---|
| 충족 | 실파일 증거로 DoD 충족 | 27 | 6 |
| 부분 | 축 일부만 착지·갭 명시 | 13 | 9 |
| 의도적 미채택 | 저장소가 근거를 남기고 거부 | 5 | 3 |
| 갭 | 미착수·미판정 | 5 | 8 |

① 합 **27+13+5+5 = 50** — 50항과 일치한다(초판은 51이었다·정정 2건).
- **B2(§12 Feature Flag)가 갭 → 부분**: 체계는 실재하고 E축 플래그만 없다(§4 B2).
- **항목 26이 부분·미채택에 이중 계수**돼 있었다. `v1/POST-v1 백로그 분리`(부분)와
  `POSTPONE≠삭제 준수`(미채택)는 같은 항목의 두 측면이라 **부분에서 한 번만** 센다.

---

## §1. 방법

- 판정 근거는 **실파일 경로(:줄)·명령 출력·태스크 ID** 중 하나여야 한다. 문서 언급만으로 "충족" 판정한 행은 없다.
- "trunk 부재≠미구현" 절차 준수: 갭 판정 전 `git branch -r`(36건)·열린 PR 16건·`backlog/tasks/**`(456건)을 교차 조회했다. 인플라이트로 확인된 항목은 갭이 아니라 **"진행 중(소유자 명시)"**로 적었다.
- **의도적 미채택**은 갭과 구분한다. 저장소가 근거를 남기고 거부한 항목(예: `docs/eos/` 7파일 트리)을 갭으로 세면 이중 진실원천을 다시 만들자는 권고가 된다.

재현 명령:

```bash
git tag -l                                    # 베이스라인 태그
ls docs/eos docs/adr 2>&1                     # 신설 금지 트리 확인
grep -rn "SubjectAdapter\|feature_flags" src/ --include=*.py   # 0건 확인
sed -n '184,200p' src/backend/pyproject.toml  # import-linter 계약 축
grep -n "^      - name:" .github/workflows/ci.yml            # CI 스텝 전수
```

---

## §2. ② Phase 0 — 산출물 P0-01~P0-10 대조

| 산출물 | 판정 | 근거 / 갭 |
|---|---|---|
| **P0-01** EOS v1 Scope | **부분** | `docs/standards/eos_verification_design_v1.md`(G0 동결본)가 앵커 6·CU 정의·KPI·실패코드로 **검증 범위**를 확정. 갭: ②가 말한 "출시 범위"와 축이 다르다 — 저장소는 12/31을 *내부 검증 판정일*로 재정의했고(선언 §0-2) 이는 근거 있는 의도적 변경이나, 그 결과 **"12월에 무엇을 만들 것인가"의 기능 목록은 어디에도 없다**(P0-03과 같은 뿌리) |
| **P0-02** Existing Feature Inventory (기존 120 기능 전수 분류) | **갭** | KEEP/REFACTOR/REPLACE/POSTPONE 판정을 담은 장부 **0건**(`grep -rl "REFACTOR\|POSTPONE" backlog/ docs/` 무실적). `backlog/` 456태스크는 *작업* 대장이지 *기능* 대장이 아니다 — 기능 단위 결합도·마이그레이션 리스크 필드가 없다. 부분 대체물: PR #916의 `eos_verification_relevance_triage_2026-08-31.md`(잔여 182건 관여도 트리아지·**제안 단계**) |
| **P0-03** EOS Feature Prioritization (270개 P0~P3) | **부분** | 대체 수행: `docs/reviews/eos_plan52_crosswalk_2026-09.md`가 **53항목**을 이미구현 11/부분 27/신규 7/이월 8로 전수 판정. 갭 2축: ⓐ 270→53으로 모집단이 축소된 경위가 문서화되지 않음(추적표 02시트가 정본이나 저장소 외부) ⓑ **P0~P3 등급이 태스크 스키마의 필드가 아니다** — `grep "eos_priority" backlog/tasks/` 0건이라 기계 질의 불가 |
| **P0-04** EOS Core Boundary v1 | **부분** | 문서 축: 선언 §1.3-③가 "실구현 보류·계약 수준만"으로 경계를 *선언*. 갭: **경계의 목록(무엇이 Core이고 무엇이 Adapter인가)을 적은 문서가 없다** — `grep -rln "EOS Core" docs/` = 2건이며 둘 다 계획·대조 문서다. ②§3.7의 Core 14항목 / Math Adapter 10항목 표에 대응하는 저장소 정본 부재 |
| **P0-05** Subject Contract v1 | **갭 (A1)** | `SubjectAdapter` 프로토콜 **0건**(src 전수 grep). 인접 착지: CUR-11 done(#920 — subject-neutral *curriculum* API 5라우터)은 계약이 아니라 API 표면. S1-16(todo·`extensions.math` 분리)이 스키마 축을 담당하나 **행위 계약**(`evaluate_answer`·`detect_misconception`·`explain`)은 소유 태스크가 없다 |
| **P0-06** Math Adapter Contract v1 | **갭 (A1과 동일 뿌리)** | 위와 같음. 현행 L1~L4가 사실상 Math Adapter이나 그것을 *계약으로* 표명한 코드·문서 없음 |
| **P0-07** Canonical Entity Model v1 | **부분** | Canonical ID는 충족 — `concept_graph/registry.py:7-11`(영구 동결 정책)·`validate.py:340-363`(`CONCEPT_ID_PATTERN`)·DB PK와 분리(`problem.py:82-91`). **`Skill`은 실체화돼 있다** — `db/models/skill_node.py`의 `SkillNode`(PK=`skill.<slug>` 멱등 upsert) + `l1/skill_graph/`(projection·resolve·populate). 갭: ②§3.10의 19개 엔티티 중 `MasteryState`·`PedagogyStrategy`의 1급 실체 미확인, 엔티티 목록 자체의 정본 문서 부재 *(초판은 Skill을 미확인으로 셌다 — 리뷰 봇 지적 수용·정정)* |
| **P0-08** Learning Event Contract v1 | **부분** | 봉투 계약 실재 — `schema/analytics_event.py:83-101`(`event_uuid`·`schema_version`·`occurred_at`·`received_at`·`source`·`session_id`·`correlation_id`·`event_type`·`payload`). 갭 2: ⓐ `subject_id`·`entity_id` 필드 부재(다과목 집계 축) ⓑ `EventType`이 튜터링 상호작용 중심 한국어 값(문제읽기·막힘·힌트요청…)이라 ②§3.12의 11개 표준 학습 이벤트와 **1:1 대응표가 없다** — EOS-45/46/48이 인접 축을 담당 |
| **P0-09** Migration Map (기존→EOS 이동 계획) | **갭** | 부재. ②§3.14 Migration Difficulty Matrix(A~F 6축 18점 → KEEP/REFACTOR/Heavy/REPLACE)를 적용한 산출물 **0건**. P0-02의 후행 산출물이라 함께 비어 있다 |
| **P0-10** Architecture Decision Records | **부분 / 의도적 미채택 혼재** | `docs/architecture/adr/` 실재(ADR-001 이벤트 저장소·ADR-002 학생 풀이 단계 엔티티) + `*_adr.md` 2건. 선언 §1.3-①은 "ADR = MEMORY.md 결정로그 + docs/architecture/"로 라우팅을 의도적으로 바꿨다. 갭: ②§3.16이 지정한 **ADR-001~010 10건 중 대응물은 2건**이며, 특히 ADR-001(Core Boundary)·ADR-002(Subject Adapter)·ADR-007(AI Gateway)는 대응 문서가 없다. 번호가 이미 다른 주제로 소진돼 **번호 충돌 위험**도 있다 |

### ②의 나머지 기준

| 기준 | 판정 | 실측 |
|---|---|---|
| Gate 0 — A(Scope) | **부분** | 12월 범위 문서 있음(검증설계서). "P0 기능 목록"·"POSTPONE 목록"·"신규 기능 추가 규칙의 **집행**" 3항 미충족(신규 기능 게이트 집행 0건 = PR #916 A1과 동일 지적) |
| Gate 0 — B(Architecture) | **미충족** | Core/Adapter 한 문장 정의 부재(P0-04) · Subject Contract 부재(P0-05) · "Core가 Math를 참조하지 않는가"를 **기계로 판정하는 수단이 없다**(§3-15 참조) |
| Gate 0 — C(Data) | **충족** | canonical ID ✓ · Concept/Misconception 관계 ✓(원자 2,683·엣지 2,210·crosswalk 64) · Event schema ✓ · LearnerState는 `mastery_history` append-only로 실재 · **`Skill`도 `SkillNode`로 실재**(초판의 유일 잔여 갭이었으나 오판정 — 정정). 4문항 전부 YES |
| Gate 0 — D(Migration) | **미충족** | P0-02·P0-09 부재로 4문항 전부 판정 불가 |
| Gate 0 — E(Release/Golden Path) | **부분** | A4 앵커 E2E 관통 실증 착지(`tests/backend/harness/test_eos_anchor_e2e_a4.py`·EOS-58 #914). 갭: 그 경로가 ②§3.15의 13단계(로그인→…→Event 기록)와 **어느 단계까지 대응하는지 대조표 없음** |
| Rule 1 신규 EOS Feature 개발 금지 | **부분** | 선언 §0-5로 규칙화. 집행 지점 0(PR #916 A1) |
| Rule 2·3 전 기능/전 EOS 기능 4분류·4등급 | **미충족** | P0-02·P0-03 참조 |
| Rule 4 **One In → One Out** (P0 교환제) | **갭** | 규칙 자체가 저장소에 없다 — 선언·백로그·`backlog.py` 전수 grep 0건. ②는 이 규칙을 "12월까지 유지해도 좋다"고 한 유일한 상시 규칙이다 |
| Rule 5 ADR 없는 아키텍처 변경 금지 | **부분** | 관행 존재(MEMORY 결정로그 의무·CLAUDE.md). ADR 형식 강제는 없음 |
| Rule 6 Core에 subject-specific 코드 금지 | **미강제** | §3-15 참조 |
| 대시보드 5숫자 | **부분** | HARN-40 작업 보드 착지(#921·backlog 투영)이나 **5숫자 중 어느 것도 표시하지 않는다** — 기존 기능 분류율·EOS 기능 분류율·Release P0 수·미결 아키텍처 결정 수·Golden Path 커버리지. 앞 4개는 P0-02/03 부재로 산출 불가 |

---

## §3. ① 50항목 대조 (요지)

충족이 명백한 항목은 근거만 적고, 부분·갭은 갭 축을 명시한다.

### 충족 (27건)

| 항 | 기준 | 근거 |
|---|---|---|
| 1 | 상태 보존·베이스라인 태그 | `whymath-mvp-final-2026-08-30`(역참조 `0d6fb82d` 실측·EOS-06 done). **날짜만 08-27→08-30**(전환 선언일 변경에 따른 근거 있는 차이) |
| 4 | 전환 ADR | 선언 문서 #904 머지(ADR 형식은 아님 — §2 P0-10) |
| 9 | DB Migration 정식 관리 | alembic 90 리비전 + CI `backend-migrations` 잡이 **fresh upgrade → downgrade base → 재upgrade 왕복**을 상시 실행(ci.yml:490-493) — ①이 요구한 rollback test가 이미 CI |
| 13 | AI 직접 호출 금지·게이트웨이 | `l3/router.py:482` + providers + CLAUDE.md 절대 원칙 |
| 14 | Prompt 버전 관리 | C10 이미구현 판정(crosswalk) · `prompt_asset_audit` CI 게이트(ci.yml:415) |
| 15 | CI 강화 | ruff·black·**mypy --strict**·unit+coverage·계층별 커버리지 floor·통합(실 PG)·마이그레이션 왕복·docker build·**결함주입 강등전 5종**·시크릿 패턴 금지(ci.yml:1077) — ①의 8종 중 architecture·security만 부분 |
| 17 | Definition of Done 강화 | `backlog.py done`의 PR 증적 게이트 + acceptance 전수 + PR 템플릿 4문답 |
| 18 | 최소 E2E Learning Loop | `test_eos_anchor_e2e_a4.py`(EOS-58 #914 — 앵커 A4 관통 실증) |
| 19 | Observability | Langfuse 배선 + 인프로세스 이중 회계(`ops/service_health`·`cost_probe`) + 침묵 실패 금지 규칙(예외 타입명 로그 의무) |
| 22 | Dependency 고정 | pyproject 상한 pin 관행(`langfuse>=2.50,<5` 선례)·npm ci·Flutter lockfile 정합 강제(ci.yml:678) |
| 25 | 신규 기능 요청 Gate | 선언 §0-5 (집행은 갭 — B1) |
| 27 | 9월 Architecture Freeze Gate | G0 `G-eos-g0-verification-design-freeze` cleared + `test_failure_definition_freeze.py`가 §5 해시로 되돌림 차단 |
| 31 | Release Gate | 검증설계서 §4~§6(실패코드 F1~F8·KPI·실패정의 F-Ⅰ~Ⅴ) + Wilson exit 0/1 관례 |
| 33 | 위험 패턴 검색 | `policy-guard`·`harness-integrity`·`declared-unwired-audit` 잡 상시 |
| 34 | API versioning | `/v1/*` 전면(`api/rights.py`·CUR-11 5라우터 등) |
| 38 | AI와 결정론 분리 | 채점 결정론 우선·SymPy 단일 권위(CLAUDE.md 불변 계약) |
| 39 | AI 출력 검증 계층 | 3-tier 검증(수치→SymPy) + PRM/도구 검증 없이는 학생 제공 금지(절대 금기) |
| 43 | 하지 말아야 할 것 | 전면 재작성 0·DB 갈아엎기 0·Neo4j 런타임 미도입·Agent 무한 증식 없음 — 전건 준수 |
| 44 | 8/28 명령 순서 | 태그·브랜치·선언 PR 전부 집행(날짜만 이동) |
| 45 | PR-0~PR-12 순서 | PR-0(선언) 완료. PR-1~4(경계·레지스트리·어댑터)는 §4 A1 참조 |
| 47 | 5개 버전 관리 | `schema_version`(문제·이벤트)·`curriculum_version`·`prompt_version`·`evaluator_version`·alembic 리비전 — 5축 실재 |
| 48 | 최상위 품질 규칙 | 검증설계서 실패정의 F-Ⅰ~Ⅴ가 동일 역할 |
| 49-B | Git 체크리스트 | 태그·PR 재분류를 제외한 전항 |
| 49-D | Data 체크리스트 | provenance·schema version·migration 착지(LIC-01 진행 중) |
| 49-G | Engineering | §15와 동일 |
| 50-① | 태그 | 완료 |
| 50-② | 전환 ADR merge | 완료(#904) |

### 부분 (13건 — 표 12행 + §4 B2)

| 항 | 기준 | 갭 축 |
|---|---|---|
| 2 | Git 기준점·브랜치 규율 | `eos/math-v1` 미생성(짧은 feature branch 권장과는 정합이라 무해). 실 갭은 **장기 미머지 36 원격 브랜치** — ①이 금지한 "장기간 살아 있는 거대 branch"가 상시 상태이며 저장소 자체가 4차례 감사(`unmerged_branch_audit_*`)로 반복 확인 |
| 7 | EOS Core Contract 고정 | 엔티티 상당수 실재하나 *계약으로* 모인 모듈 없음(P0-07) |
| 10 | Learning Event Schema | P0-08 참조 |
| 11 | 기존 기능 분류 | P0-02 참조 |
| 16 | PR Gate 변경 | 템플릿은 훌륭하나(변별력·정직한 공백 4문답) **①§16이 지정한 EOS 3블록이 없다** — Release Classification(P0/P1/P2/POST-V1) · Layer(Core/Adapter/Infra/UI) · Contract impact(API/DB/Event/Entity) |
| 24 | 열린 PR 재분류 | **미실시**. 열린 PR 16건(최고 연령 #844 = 14일) 전건 라벨 0 · MERGE/REWORK/POSTPONE/CLOSE 판정 기록 없음 |
| 26 | v1 / POST-v1 백로그 분리 | 물리 분리 없음. E축 과목팩(E1~E6 물리·화학·생물·역사·국어·영어) **10건 전건 todo**로 `next` 후보에 남아 있음 — ①§11이 12월 전 확장 금지로 지목한 바로 그 축 |
| 28 | 10월 폐쇄루프 집중 | 계획 존재(G1~G2), 집행은 향후 |
| 29 | 11/30 Feature Freeze 라벨 | GitHub 라벨 `release-blocker` **부재**(API 실조회 404). 6종 라벨 전부 미생성 |
| 30 | 12/14 Code Freeze 규칙 | 문서화 없음 |
| 36 | Repository 계층 | ORM 직접 접근이 서비스 계층에 남아 있음(부분) |
| 42 | Backup/Restore/Rollback 실검증 | 마이그레이션 왕복은 CI ✓. **DB 복구 리허설·오프사이트 사본은 사람 게이트 2건이 20일 pending**(`G-backup-restore-rehearsal`·`G-backup-offsite-move`) |


**13번째 부분 항목**: `§12 Feature Flag`는 §4 **B2**에 기술한다 — 체계는 실재하고
(환경변수 플래그 16+건) E축 기능용 플래그만 없다. 초판이 갭으로 분류했던 것을 정정한 항목이라
설명을 B급 표에 두고 여기서는 참조만 한다.

### 의도적 미채택 (5건 계수 — 표는 6행, 26은 부분에서 계수)

| 항 | 기준 | 저장소 근거 |
|---|---|---|
| 3 | `docs/eos/` 7파일 트리 | 선언 §1.3-① "신설 금지 — 이중 진실원천은 명문 금지 붕괴 경로". 정본은 `docs/strategy/`·`docs/standards/` |
| 5 | `src/eos/` + `subjects/math/` 물리 대이동 | 선언 §1.3-③ "12월 검증에 불필요 + ①§43 한 번에 재작성 금지와도 정합". **단 경계 강제 자체는 별개 — §4 A2** |
| 8 | Entity Registry (별도 신설) | A1 이미구현 판정(canonical_id 레지스트리·정규식 CI) |
| 21 | `.env.development/.test/.staging/.production` 4분리 | `config.py:1409` `is_production_like()` 주석이 명시적으로 거부 — "`environment` 축을 새로 두면 그 축 자체가 *설정하는 걸 잊는* 표면을 하나 더 만든다". 근거 있는 설계 판단 |
| 26 | POSTPONE = 삭제 아님 | 준수(취소 3건뿐·나머지 전부 보존). **계수는 부분(§3)에서 1회만** — 같은 항목의 다른 측면이라 이중 계수하지 않는다 |
| 46 | 파일 구조 최소 목표 | 5와 동일 |

### 갭 (5건) → §4로

§4 **A1**(6·7 Subject Adapter) · **A2**(32 Architecture CI Gate) · **B3**(20 Error Code) ·
**B4**(23 README 로컬 환경) · **B5**(40 Golden Dataset)

*(정정: 초판은 여기에 B2 Feature Flag를 더해 6개를 열거하고 "5건"이라 적었다 — 열거와
숫자가 어긋났다. B2는 §4에서 **부분**으로 재판정됐으므로 이 목록에서 내린다.)*

---

## §4. 실제 갭 목록 (우선순위)

### A급 — 9월 내 처리 권고 (G1 9/27 차단 조건 직결)

**A1. Subject Contract / Math Adapter 계약이 코드에 없다** (①§6·§7 · ②P0-05·P0-06 · Gate 0-B)
- 실측: `grep -rn "SubjectAdapter" src/` **0건**. CUR-11(done)은 curriculum API 표면이지 행위 계약이 아니고, S1-16(todo)은 스키마 축만 담당한다.
- 왜 갭인가: 선언 §1.3-③은 *물리 대이동*을 보류했을 뿐 **계약 수준은 W1에 하기로 명시**(“W1은 계약(contract) 수준(S1-16·CUR-11)만 진행”)했다. CUR-11은 착지했으나 S1-16은 여전히 todo이고, ②가 요구한 `evaluate_answer`/`detect_misconception`/`explain` 행위 계약은 **어느 태스크도 소유하지 않는다**.
- 영향: Gate 0-B 4문항 중 2문항이 판정 불가. "Physics를 붙일 때 Core를 뜯지 않아도 되는가"(②§4-⑥의 유일한 합격 기준)를 증명할 수단이 없다.

**A2. EOS Core ↔ Math Adapter 경계를 기계가 강제하지 않는다** (①§32·§15 architecture test · ②Rule 6 · Gate 0-B)
- 실측: `src/backend/pyproject.toml:184-199` import-linter 계약은 **7계층 축 단 1건**(api→l6→…→schema). Core/Subject 축 계약 0건. `tests/architecture/` 디렉터리 부재.
- crosswalk H1도 같은 지적("EOS Core/Subject 축은 별개")을 남겼으나 **대응 태스크가 등재되지 않았다**.
- 영향: G1(9/27) 차단 조건 "Core→Math 정적 의존 0"을 **측정할 도구가 없다**. ①§15이 "이 테스트는 매우 중요하다 — 없으면 EOS 전환이 형식적 리팩터링에 그친다"고 단독 강조한 항목이다.
- 주의: 현행 L1~L4는 Core와 Adapter가 섞여 있으므로, 계약 추가 전에 **어느 모듈이 어느 쪽인가**(P0-04)를 먼저 적어야 한다. A2는 P0-04에 의존한다.

**A3. 기능 인벤토리·Migration Map 부재** (②P0-02·P0-09·Gate 0-D · ①§11)
- 실측: KEEP/REFACTOR/REPLACE/POSTPONE 장부 0건 · Migration Difficulty Matrix 적용 0건.
- 인플라이트: PR #916의 관여도 트리아지(182건)가 **부분 대체**하나 축이 다르다 — "12월 검증에 관여하는가"는 물었지만 "EOS Core인가 Adapter인가·이전 난이도는 얼마인가"는 묻지 않았다.
- 영향: Gate 0-D 전 문항 판정 불가 + 대시보드 5숫자 중 2개 산출 불가.

**A4. 열린 PR 16건 미분류** (①§24·§49-B)
- 실측: 열린 PR 16건 전건 라벨 0. #844(8/17)·#846(8/19)·#847(8/20)은 2주 이상 방치.
- ①은 "현재 PR을 그대로 계속 merge하면 EOS 전환 선언이 무의미하다"고 이 항목을 단독 경고했다.
- 부수 확인: 내용상 이미 착지분과 중복인 PR이 있다 — #885(SEC-28)는 #922(회수 이식)와 같은 축이고, #856·#858은 LIC-01 계열 브랜치 2개(`...-mvp`·`...-mvp-2`)가 각각 열린 상태다.

**A5. P0-04 EOS Core Boundary 목록 부재**
- A1·A2의 선결. ②§3.7의 Core 14 / Adapter 10 대응표를 현행 L1~L6 패키지에 매핑한 1장 문서면 충분하다(②도 "완성된 구현이 아니라 계약의 확정"이라고 못박음).

### B급 — 12월 전 처리 권고

| # | 갭 | 기준 | 실측 | 비고 |
|---|---|---|---|---|
| **B1** | 신규 기능 게이트 집행 지점 0 | ①§25·②Rule 1 | `backlog.py` 판정 로직 0건 | **PR #916 A1과 동일 — 중복 등재 금지**, 그 PR 판정 대기 |
| **B2** | Feature Flag — **체계는 있다. E축 기능용 플래그가 없을 뿐** | ①§12 | `config.py`에 환경변수 플래그 **16+건 실재**(default OFF 10·ON 6 — `mode_guard_runtime_enabled`·`l4_step_shadow_enabled` 등)이며 서빙 경로에서 소비된다(`wh1_primary.py:254`·`api/coach.py:13`) | **초판 오판정 정정**: `grep "feature_flags"` 0건만 보고 "체계 부재"로 결론냈다 — 문자열 하나로 기능 전체의 부재를 판정한 **변별력 없는 검사**다(이 문서가 §1에서 스스로 경고한 함정). 실제 갭은 좁다: E축·연구성 기능을 끌 플래그가 아직 없다. 후보는 **기존 `Settings` 체계 확장**이지 신규 프레임워크가 아니다 — 만들면 중복이 된다. 리뷰 봇 지적 수용 |
| **B3** | 구조화 에러코드 체계 부재 | ①§20 | 예외 클래스 31개 실재하나 `EOS-XXX-NNN` 코드 축 0건. `GenerationFailureCode`(F1~F8)는 *콘텐츠* 실패 분류이지 시스템 에러코드가 아님 | 12월 판정 시 장애 분석 축 |
| **B4** | README 로컬 환경 표준화 부재 | ①§23 | README에 `venv`·`pip install`·`alembic upgrade`·`pytest` **0건**(하네스 안내 중심) | "새 개발 환경에서 README만 보고 서비스가 실행되어야 한다" 미충족 |
| **B5** | Golden Dataset 미분리 | ①§40 | `tests/golden/` 부재. 골든 자산은 테스트 파일 내부에 산재 | EOS-64(nightly 골든·todo)가 인접 소유. 모델·프롬프트 변경 시 회귀 축 |
| **B6** | PR 템플릿 EOS 3블록 부재 | ①§16 | 템플릿에 Release Classification·Layer·Contract impact 없음 | A3·A4가 선행돼야 의미가 생김(분류 체계가 없으면 체크박스가 비어 있는 칸이 됨) |
| **B7** | Feature/Code Freeze 라벨·규칙 미준비 | ①§29·§30 | `release-blocker` 라벨 404 · 12/14 규칙 문서 0건 | 11/30까지 여유 있음. 다만 ①은 "코드/프로세스로 **실제** 적용"을 요구 |
| **B8** | One In → One Out 규칙 부재 | ②Rule 4 | 전수 grep 0건 | ②가 "12월까지 유지해도 좋다"고 한 유일한 상시 규칙. B1과 같은 지점에 붙일 수 있다 |

### 갭이 아니라고 판정한 것 (오탐 방지 기록)

- **`docs/eos/` 7파일·`src/eos/` 트리 부재** — 의도적 미채택(근거 명문). 이것을 갭으로 등재하면 저장소가 명문 금지한 이중 진실원천을 만든다.
- **`.env` 4분리 부재** — `config.py:1409` 주석이 근거를 남긴 설계 판단.
- **270개 기능 목록 부재** — 원본 xlsx가 저장소 외부이며 53항목 crosswalk가 대체 수행. 다만 모집단 축소 경위는 기록 권고(P0-03 ⓐ).
- **Physics/Chemistry 미착수** — ①§11이 요구한 상태 그 자체(확장 금지). E축 과목팩 10건이 `next` 후보에 남는 것만 B급 위생 사안.

---

## §5. 수정 제안 (등재 후보 — 번호 미배정)

> **등재 현황 (2026-08-31 갱신)**: A급 5건은 Kiki 지시로 `backlog.py add` 등재 완료 —
> 아래 표의 "등재 ID" 열 참조. 번호는 CLI가 로컬 대장 + 원격 claim + 열린 PR 브랜치
> 선점분(HARN-41·EOS-60~62·LIC-05·OPS-57 실측)을 검사해 배정했다(HARN-10 준수 — 눈으로
> 고른 번호 0건). `validate` EXIT=0 · 461태스크. B급 8건은 미등재 후보로 남는다.
>
> 각 후보에 **왜 12월 검증에 필요한가**(선언 §0-5 신규 기능 게이트)를 병기했다.

### A급 — 등재 완료 (5건)

| 갭 | 등재 ID | prio | 12월 검증 관여 근거 | 선결 |
|---|---|---|---|---|
| A5 | **`EOS-65-core-adapter-boundary-map`** | 1 | G1 차단 조건("Core→Math 정적 의존 0")의 판정 기준 자체 | — |
| A1 | **`EOS-66-subject-adapter-contract`** | 1 | Gate 0-B · "Physics를 붙일 때 Core를 뜯지 않는가"의 유일한 증명 수단 | EOS-65 |
| A2 | **`EOS-67-core-adapter-import-contract`** | 1 | G1 차단 조건의 **측정 도구** | EOS-65 |
| A3 | **`EOS-68-feature-inventory-migration-map`** | 2 | Gate 0-D 전 문항 · 대시보드 5숫자 2개 | — |
| A4 | **`HARN-42-open-pr-eos-reclassification`** | 1 | ①§24 단독 경고 · #885·#856/#858 중복 실측 | — |

등재 직후 `backlog.py next` 실측: **EOS-65가 1순위**("완료 시 후속 2건 해금")·HARN-42가 3순위로
정렬됐다 — 의존 그래프가 의도대로 걸렸음을 CLI 출력으로 확인.

**등재 시 반영한 이 저장소의 재발방지 규칙** (각 태스크 acceptance에 별항으로 박음):
- *정본화≠집행* — EOS-66 ③은 "계약을 경유하는 서빙 코드 경로가 현재 0개"를 명시하고 경유
  배선을 후속 분리, EOS-67 ③은 "pyproject에 존재함 ≠ 잡이 돌아감"을 tests/infra로 대조.
- *변별력 없는 검증 스텝 금지* — EOS-67 ②는 뮤테이션으로 `lint-imports` exit 1을 실측하고
  **원복은 cp 백업으로만**(2026-08-10 git checkout 사고 규칙).
- *만료 없는 유예 금지* — EOS-67 ④는 현행 위반을 baseline 동결할 경우 만료·재확인 지점 필수.
- *거부의 우회 금지* — HARN-42 ④는 PR CLOSE·MERGE 집행을 Kiki 소유로 분리(되돌리기 어려운 행위).
- *중복 등재 금지* — EOS-68 ④는 PR #916의 관여도 트리아지와 축이 다름을 명시하고 겹치는 행의
  재판정을 금지.

**등재하지 않은 것 (의도적)**: `S1-16 착수`는 기등재 todo라 새 태스크가 필요 없다(중복 등재
금지) — A1 근거 문단에 소유자로 이미 적혀 있다.

### B급 — 미등재 후보 (8건 · Kiki 판정 대기)

| # | 후보 | 제안 계열 | 12월 검증 관여 근거 | 선결 |
|---|---|---|---|---|
| 1 | **P0~P3 등급을 태스크 스키마 필드로** + `backlog.py`에 신규 기능 게이트 질의 | HARN | B1·B8·②Rule 3·4 — **PR #916 A1과 동일 축이므로 그 PR과 통합 판정 필요** | #916 |
| 2 | **E축·연구성 기능 플래그 추가** — 기존 `config.py` `Settings` 체계에 default OFF 항목 추가(**신규 프레임워크 금지** — 16+건이 이미 그 패턴으로 산다) | OPS | ①§12 · 12월 판정 시 미완 기능 격리 | — |
| 3 | **README 로컬 부트스트랩 절** | 문서 | ①§23 · 신규 세션·기기 재현성 | — |
| 4 | **Golden Dataset 디렉터리 분리** | QA | ①§40 · EOS-64와 통합 검토 | EOS-64 |
| 5 | **선언 정본 §3~§5 갱신** — G0 확정치(앵커 6·25h·F-Ⅳ 3/6·CU 450/185) 반영 | 문서 | **PR #916 A7과 동일 — 중복 등재 금지** | #916 |
| 6 | 구조화 에러코드 체계(B3) | OPS | 11월 권고 — 아래 비제안 사유 참조 | — |
| 7 | Feature/Code Freeze 라벨·규칙(B7) | HARN | 11/30 시점 작업 | — |
| 8 | PR 템플릿 EOS 3블록(B6) | HARN | 분류 체계(EOS-68·B급 1) 선행 필요 | EOS-68 |

**B급 6~8을 지금 등재하지 않는 이유**: 각각 12월 판정 직전(11월)에 하는 편이 낫다 — PR 템플릿 3블록은 분류 체계(EOS-68)가 선행돼야 빈 칸이 되지 않고, Freeze 라벨은 11/30 시점 작업이다. 지금 등재하면 "만료 없는 유예" 없이 떠 있는 todo만 늘린다. 표에는 근거와 함께 남겨 두되 대장에는 넣지 않는다.

---

## §6. 한계 · 정직한 공백

1. **모집단 검증 불가** — ①의 "기존 기능 120개"·②의 "EOS 후보 270개"는 저장소 외부 xlsx가 정본이라, 본 대조는 *분류 산출물의 존재 여부*만 판정했고 **개수 정합은 판정하지 않았다**.
2. **의도 판정의 한계** — "의도적 미채택 6건"은 저장소에 근거 문장이 있는 것만 셌다. 근거 없이 빠진 것을 의도로 오분류했을 가능성은 배제하지 못한다.
3. **인플라이트 중복** — PR #916(선언 준수 감사)·#911(N1~N10 대조)과 본 문서는 대상 기준이 다르나 **B1·§5-7·§5-11은 #916과 같은 축**이다. 등재 전 통합 판정이 필요하다.
4. **동적 검증 없음** — 본 세션은 테스트를 실행하지 않았다(정적 대조 전용). "CI가 돈다"는 워크플로 파일 기준 판정이며 최근 실행 결과를 조회하지 않았다.
5. **초판의 오판정 3건 — 리뷰 봇(`chatgpt-codex-connector`)이 잡았다.** 전건 실측 확인 후 수용·정정했고, 정정 사실을 해당 행에 병기했다.
   - **B2 Feature Flag "체계 부재"** — `grep "feature_flags"` 0건만으로 결론냈으나 `config.py`에 16+건이 다른 이름(`*_enabled`)으로 실재한다. **이 문서가 §1에서 경고한 "변별력 없는 검사"에 문서 자신이 걸렸다** — 특정 식별자 부재를 기능 부재로 읽으면 안 된다는 교훈이 가장 비싸게 확인된 지점이다.
   - **P0-07·Gate 0-C의 `Skill` 미확인** — `SkillNode` ORM + `l1/skill_graph/` 실재. Gate 0-C는 이 정정으로 **부분 → 충족**이 됐다.
   - **§0 요약의 P0 집계** — 자기 표(§2)와 모순(충족 2·부분 5·미착수 3 → 실제 0·6·4).

   세 건 모두 *부재 주장*이었다. **"있다"는 파일을 대면 끝나지만 "없다"는 검색 방법 자체가 옳아야 성립한다** — 부재 판정의 오류율이 구조적으로 높다는 것을 이 문서가 스스로 실증했다.
6. **A2 난이도 미추정** — Core/Adapter 경계선을 현행 L1~L4에 그으면 위반이 몇 건 나오는지 측정하지 않았다. 후보 1 착수 시 첫 실측에서 드러날 값이며, 위반이 많으면 후보 2는 단계적 허용(baseline) 계약이 필요할 수 있다.
