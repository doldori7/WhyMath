# "EOS 1과목 완성" 3축 실측 점검 (2026-09-03)

> **판정 기준**: 코드 grep·문서 서술이 아니라 **명령 출력**으로 판정한다(CLAUDE.md).
> **대조 시점**: `claude/whymath-system-review-n75r24` @ `5bb2947b` · API 라우트 103건 · 백엔드 모듈 637개.
> **성격**: 조사 전용(코드 변경 0). 대장 변경 없음.
> **환경 한계(명시)**: 샌드박스에 백엔드 의존성 미설치 → 앱 부팅·테스트 실행 불가.
> 라우트는 AST 파싱으로, CI 결과는 GitHub API 실측으로 대체했다.

---

## §0. 결론 3줄

1. **축 3(경계)은 합격이다.** `EOS Core → Subject Contract → Math Adapter → WhyMath` 4층이 실제 코드에 있고,
   위반 0건을 **CI가 매 PR 판정**한다. 다만 계약 2층 중 **필수층은 아직 아무도 부르지 않는다**(선택층만 배선).
2. **축 1(학생 흐름)은 14단계 중 11단계가 서 있으나 3곳이 끊겼다.** 가장 큰 끊김은 **2단계(교육과정 선택)**로,
   `grade`·`school_type`을 **소비하는 코드는 4곳인데 값을 넣는 API가 0곳**이라 하위 기능들이 조용히 무효화된다.
3. **축 2(관리자 흐름)는 12단계 중 HTTP 표면이 2개뿐이고 사람 UI가 없다.** 실운영 수단은 `python -m ...` CLI 60여 개이며,
   **콘텐츠 "배포(게시)" 축은 선언만 있고 소비처 0건**이다.

**종합 판정: "EOS 1과목 완성" 미달.** 축 3은 충족, 축 1은 부분, 축 2는 미달.

---

## §1. 축 3 — EOS Core → Subject Contract → Math Adapter → WhyMath

### 1.1 4층이 실제 코드에 있는가 → **있다**

| 층 | 실체 | 실측 |
|---|---|---|
| EOS Core | 과목 중립 엔진 | **309모듈 · 71,200 LOC · sympy import 0건 · 수학어휘 0.8/kloc** |
| Subject Contract | `schema/subject_adapter.py` (필수층) + `schema/verification_capabilities.py` (선택층) | 필수 3메서드 + 선택 Protocol 8종 |
| Math Adapter | `l4/subject_adapter_math.py` | **81모듈 · 31,861 LOC · sympy 19건 · 수학어휘 27.1/kloc** |
| WhyMath(제품) | `l6/` 6모드 + `api/` + `src/mobile` | gifted·metacognition·retake·school_progress·suneung·thinking |

Core와 Adapter의 **수학어휘 밀도 차가 34배**(0.8 vs 27.1)라는 점이 경계가 명목이 아님을 보여준다.

### 1.2 경계가 집행되는가 → **된다 (CI 매 PR)**

```
python3 scripts/analysis/eos_core_adapter_boundary_scan.py
→ 대상 637파일 · CORE→ADAPTER import 위반 0건 · 스캔 오류 0건 · EXIT=0
```

정적 강제는 `src/backend/pyproject.toml`의 **import-linter 계약 3건**이며 CI `lint` 스텝에서 매 PR 판정한다.
잔여 예외는 합성 루트 경유 **2건**뿐이고, 간선 단위로 좁게 열려 있어 새 간선이 생기면 즉시 적색이 된다.

### 1.3 발견 — **필수층 계약은 정본화됐으나 집행 0**

CLAUDE.md의 「정본화를 집행으로 착각한 완료 선언 금지」 기준으로 재보면 2층이 서로 다른 상태다.

| 계약 층 | 서빙 경로 소비 | 근거 |
|---|---|---|
| **선택층** (검증 능력 5종) | ✅ **배선됨** | `api/coach.py:72-73,972,977` · `l3/render/adapters.py:25-26,77,108` · `l3/pedagogy/slot_generator.py:31,87` — 전부 `composition.py`의 `default_*()` 경유 |
| **필수층** (`SubjectAdapter` 3메서드) | ❌ **소비처 0** | `MathSubjectAdapter` 참조 전건 = 정의(schema) 1 · 구현(l4) 3 · 테스트 12 · 경계 스캔 1. 서빙 코드 **0** |

`l4/subject_adapter_math.py:151`의 `_CONFORMANCE_PROOF: SubjectAdapter = MathSubjectAdapter()`는
**타입 체커용 자기 증명**일 뿐 런타임 배선이 아니다. `composition.py`는 능력 5종만 등록하고
어댑터 자체는 등록하지 않는다.

> **의미**: "과목을 갈아끼울 수 있는가"의 중심 축(`evaluate_answer`·`detect_misconception`·`validate_problem`)이
> 아직 **서류상 계약**이다. Physics 어댑터를 꽂아도 이 3메서드를 부르는 코드가 없어 아무 일도 일어나지 않는다.

**검색 방법 명시**(부재 판정 절차): ①역할 기반 재검색(`SubjectAdapter`·`subject_adapter`·`detect_misconception`·`evaluate_answer(`)
②소비자 역추적(`composition` default_* 호출처) ③저장소 전체 `.py` 전수. 세 방법 모두 서빙 참조 0건.

---

## §2. 축 1 — 학생 흐름 14단계

### 2.1 단계별 판정

| # | 단계 | 판정 | 진입점 |
|---|---|---|---|
| 1 | 회원/프로필 | ✅ 있다 | `POST /v1/auth/{provider}/callback` · `GET/PATCH /v1/users/me` |
| 2 | **교육과정 선택** | ❌ **없다** | — (G1·G2) |
| 3 | 진단 | ✅ 있다 | `GET /v1/me/assessments` · `POST .../assemble` · `POST .../capture` |
| 4 | 학습자 상태 | ✅ 있다(온디맨드 재계산) | `GET /v1/me/mastery` · `/ability` · `/diagnosis/*` |
| 5 | 개념 추천 | ✅ 있다 | `GET /v1/me/weak-concepts` |
| 6 | 이론/콘텐츠 | ⚠️ 부분 | `GET /v1/concepts/content` · `POST /v1/me/objectives/{id}/study` (G6·G7) |
| 7 | 문제 추천 | ✅ 있다 | `GET /v1/me/next-problem` (IRT 정보량 최대) |
| 8 | 풀이 입력 | ✅ 있다(2-콜 핸드오프) | `POST /v1/ocr` · `GET /v1/problems/{id}/steps` |
| 9 | 채점 | ✅ 있다(2경로) | `POST /v1/me/attempts`(클라 보고) · 코치 완료 확정(서버 권위) |
| 10 | **오개념 판정** | ⚠️ **부분** | `POST /v1/coach*` (텍스트축만 — G4) |
| 11 | 힌트/AI 설명 | ✅ 있다 | `POST /v1/coach` (`hint_level` 점층) |
| 12 | 숙련도 갱신 | ✅ 있다 | 채점 경로 내부 자동 전파(BKT 모델 B) |
| 13 | 다음 학습 추천 | ✅ 있다 | `GET /v1/me/review-queue` · `/weak-concepts/{id}/learning-path` |
| 14 | 학습 결과 | ✅ 있다 | `POST /v1/me/objectives/{id}/outcome` · `GET /v1/me/target-progress` |

### 2.2 관통 증명 — **야간 CI가 매일 실제로 돌고 통과 중**

`e2e-nightly` 잡(실 PG·mock LLM)이 `온보딩→진단→문제→풀이→코치→verify`를 관통한다.

- **최근 12회 연속 success**(2026-08-22 ~ 2026-09-02, `event=schedule`)
- 변별력 확인: 최신 실행(run 33679048353)의 `e2e-nightly` 잡은 **skipped가 아니라 실제 실행**됐다 —
  컨테이너 기동(28초) → `alembic upgrade head` → `pytest` 5초 → 전 코퍼스 재검증 → 앵커 A4 관통, 전 스텝 success.
- 같은 밤 `backend — 전체 스위트 직렬` 잡도 **19분 18초 실행 후 success**(순서 의존 오염 탐지).

> **다만 관통 범위는 6구간**이다. 2(교육과정)·5(개념 추천)·6(이론)·10(오개념)·12(숙련도)·13(다음 추천)·14(학습 결과)는
> 이 슬라이스에 포함되지 않는다. "14단계 전 구간 관통 증명"은 아직 없다.

### 2.3 끊김 목록

| ID | 단계 | 내용 |
|---|---|---|
| **G1** | 2 | *(서버 축 해소 — `EOS-82`, 이 PR. 클라 입력 화면은 `MOB-21` 잔여)* **`grade`·`school_type`에 HTTP writer가 0곳**이었다. `PATCH /v1/users/me`의 화이트리스트 `_SELF_EDITABLE`(`api/users.py:84-102`) 15개 필드에 둘 다 없고, 가입(`api/auth.py:159-172`)·부트스트랩 CLI도 설정하지 않는다. 반면 **소비자는 4곳**(`api/study.py:167` grade_band 교수법 필터 · `api/coach.py:1210,2243,2599` 학년 프롬프트 개인화 · `l2/target_progress.py:148` 성취기준 커버리지 스코프 · `l4/pedagogy/runtime_selector.py:136,231`). 결과: 전 학생이 영구 `None` → 해당 기능들이 **조용히 스킵/null**. ORM에는 컬럼과 인덱스(`idx_user_school`)까지 있다(`db/models/user.py:90,94,179`). |
| **G2** | 2 | 학생↔교육과정 귀속 컬럼 자체가 없다(`curriculum_framework_id`·`textbook` 0). `framework_id`는 브라우징 라우트에만 있고 user 스코프 조인 0건. 코드가 자인: `l2/learner_state.py:61-67`. |
| **G3** | 2→7 | `next-problem`의 `persona`가 프로필이 아니라 **쿼리 파라미터 기본값**(`api/me.py:2089`)에서 온다. |
| **G4** | 9→10 | **오답 채점에서 오개념 판정이 일어나지 않는다.** `AttemptSubmitResponse`(`api/me.py:692-712`)에 misconception 필드 0, 저장된 `student_answer` 소비자 0, `distractor_map`(오답 선지→오개념)의 서빙 소비자 0(하네스 전용). 오개념은 **코치 대화 텍스트축에서만** 판정된다. |
| **G5** | 11 | `HintUsage` 테이블 프로덕션 writer 0건 — 실제 힌트는 `attempt_event(EventType.힌트제공)`로만 남는다. |
| **G6** | 13→6 | `objective_id` 발견 경로 부재 — 개념 축 추천(5·13)과 objective 축 학습 공급(6·14)이 API로 연결 불가. |
| **G7** | 5→6 | `GET /v1/concepts/content`에 `code` 필터가 없어 특정 약개념의 콘텐츠를 직접 조회할 수 없다. |
| **G8** | 10 | (§1.3과 동일) `MathSubjectAdapter.detect_misconception` 좌석 미배선. |
| **G9** | 9→12 | 채점·개념숙달·스킬숙달·스킬이벤트가 **독립 commit 4개** — 중간 실패 시 attempt만 남고 숙달 미갱신. |
| **G10** | 3·10 | 오개념 판별 문항 공급(`probe_candidates`)이 하네스(`wh1_*`)에만 배선. |

### 2.4 클라이언트(Flutter) 축 — 추가 실측

앱이 실제 호출하는 엔드포인트는 **29종**(103종 중)이다. POST 호출 지점 전건은
auth · interactions · coach×3 · scene · defect-report · verify-solution · ocr · token-refresh 뿐이다.

- **`POST /v1/me/attempts` 호출 0건.** 다만 이것은 결함이 아니라 **설계된 우회**다 —
  `api/coach.py:443-444`가 *"서버가 `ProblemAttempt(is_correct=True)`를 이미 적재하고 숙달을 전파했으므로
  클라는 별도로 `POST /v1/me/attempts`를 부르지 않는다(중복 적재 금지)"* 라고 계약으로 못박고 있고,
  `_complete_problem`(`api/coach.py:990-1040`)이 같은 L2 헬퍼를 재사용한다.
- **그러나 코치 경로는 `is_correct=True`만 적재한다.** 오답을 `ProblemAttempt`로 남기는 경로는
  `POST /v1/me/attempts`뿐인데 앱이 부르지 않으므로, **앱 경로에서 BKT/IRT에 오답 증거가 들어가지 않는다.**
  G4와 합치면 "틀린 것으로부터 배우는" 축이 학습자 모델에 도달하지 못한다.
- 온보딩(`features/onboarding`)이 모으는 것은 **목표 등급·목표 점수·시험일·출생연도** 4종이며
  교육과정·학년 선택 UI는 없다(G1의 클라이언트 측 확인).
- 교육과정·진단 이력·숙련도·복습 큐·학습 결과 화면 없음 — 화면 10개(`onboarding·login·home·chat·explore·me·problem·ocr·mathlive·account_security`).

---

## §3. 축 2 — 관리자 흐름 12단계

### 3.1 단계별 판정

| # | 단계 | 운영 수단 | 판정 |
|---|---|---|---|
| 1 | 교육과정 | 시드 JSON + `python -m ...populate` · HTTP는 **GET 4종뿐** | ⚠️ 부분 |
| 2 | 개념 | **HTTP CRUD**(`RequireContentAdmin`) + CLI | ✅ 있다 |
| 3 | Skill | 수작업 JSONL + CLI 2단 · **HTTP 0** | ⚠️ 부분 |
| 4 | 문제 | **HTTP CRUD**(`RequireContentAdmin`) + CLI + 하네스 배치 30여 종 | ✅ 있다 |
| 5 | 풀이(해설) | 문제 레코드에 동봉 · 독립 쓰기 표면 없음 | ⚠️ 부분 |
| 6 | 오개념 | CLI 적재 · **HTTP 쓰기/읽기 0** | ⚠️ 부분 |
| 7 | 교수전략 | CLI 적재(YAML 팩) · **HTTP 0** | ⚠️ 부분 |
| 8 | 콘텐츠(DSL) | HTTP 3종 — **역할 게이트 없음** | ⚠️ 권한 결함 |
| 9 | 검수 | 대화형 CLI + JSONL 큐 + Markdown 체크박스 · **UI 없음** | ⚠️ 부분 |
| 10 | 승인 | 기계 판정 각인 CLI + 수동 PATCH · **사람 승인 UI 없음** | ⚠️ 부분 |
| 11 | 버전 | 디렉터리 규약(`_v0`/`_v1` + `_provenance.json`) + Alembic · **상태머신 미배선** | ⚠️ 부분 |
| 12 | 배포 | 코드 CD는 있음 / **콘텐츠 게시 축은 죽어 있음** | ❌ 없다(콘텐츠) |

**HTTP 표면이 있는 단계는 12개 중 3개**(개념·문제·DSL)뿐이다.

### 3.2 실제 운영 수단의 실체

정규 경로는 13개 도메인이 공유하는 **단일 패턴**이다:

```
data/corpus/<도메인>_v1/ 손편집
  → python -m data_pipeline.<도메인> transform-v1   (정형화·_provenance.json 발행)
  → python -m whymath_backend.l1.<도메인>.populate  (PG upsert)
  → git commit
```

운영 CLI는 `scripts/`가 아니라 `src/backend/whymath_backend/{l1,harness,ops}/` 안에 **파이썬 모듈 60여 개**로
흩어져 있고, 콘텐츠 축 런북이 없다(코드 배포 축에는 `deployment_cd_runbook.md`가 있다).
**비개발자 운영자가 수행할 수 있는 단계는 0개다.**

### 3.3 규모 실측

| 축 | 건수 |
|---|---|
| 성취기준(standard) | **895** |
| 오개념(misconception) | **843** |
| 개념(concept) | **437** |
| 원자 백본 | **2,683 노드 / 2,210 엣지** |
| 문제 | **14,051행** (`problem_bank_*/problems.jsonl` 합계) |
| 교수전략 | 10 전략 / 7 팩 / strategies.jsonl 8 |
| **Skill** | **27** ← 개념 대비 6%, 두 자릿수 작다 |

`skills.jsonl` 27줄 · `graph.json` skills 27 · `_provenance.json counts.skills=27` — 3중 일치.
게다가 `skill_node_projection.py:12,120,167`이 `review_status`를 **코드 상수 `'ai_estimated'`로 하드코딩**한다.
소스 JSONL에 슬롯이 없어 **검수 승급이 구조적으로 불가능**하다(formula·strategy·problem_type·atom_probe 4축 동일).

### 3.4 검수·승인의 실제 집행

**노출 판정은 단일 권위로 집행된다** — `schema/enums.py:741-770` `is_review_status_cleared`
(**`approved`만 True, fail-closed**) → `l6/_shared.py:167-193` → 집행 6곳
(`l6/{retake,suneung,school_progress,metacognition,gifted}/gating.py`, `l6/blueprint/assembly.py`).
`api/me.py:1796`의 CAT 후보 풀도 `ReviewStatus.approved`로 좁힌다. 이 축은 견고하다.

**승인 게이트 실집행**은 `harness/golden_promotion_gate.py` 4단(코퍼스 실재 → 사람 검수 HIT 이벤트 →
`review_status` 백필 각인 → Wilson 결함율 상한)이며, 거부 사유 6종을 구분한다.
이 게이트가 명시적으로 막는 위협이 *"누군가 코퍼스 JSONL의 `review_status`를 손으로 approved로 고치기"*다.

**`ContentLifecycleState`는 EOS-72(2026-08-31)에서 의도적으로 삭제**됐다(상태머신 이중화 회피).
그 결과 버전 생명주기 `DRAFT→IN_REVIEW→APPROVED→PUBLISHED→DEPRECATED→RETIRED`는
**문서(`docs/architecture/44_eos_version_management.md` §7)에만 존재**하고 코드 배선이 없다.

### 3.5 배포 — 콘텐츠 게시 축이 죽어 있다

학생 노출 조건은 **두 축의 AND**다: ①검수 축(`review_status == approved`) ②저작권 축
(`is_exposable` → `l1/rights/policy_engine.py:196-215`, `l1/rights/gateway.py:90`).

그런데 **의도된 게시 축 `problem.is_published`·`publish_at`은 소비처 0건**이다
(`schema/problem.py:816-817` 선언 + ORM 컬럼뿐). 하네스 배치 30여 개 docstring이
"검수 통과 전까지 `is_published=false`로 유지"라고 적고 있으나 **아무도 그 값을 읽지 않는다** —
`review_status=approved && is_published=false`인 문항이 그대로 나간다. (`ADMIN-12`, todo)

따라서 **예약 게시·일괄 롤백 개념이 없고**, 격리를 거는 전용 CLI/API도 없어 `PATCH`나 DB 직접 UPDATE에 의존한다.

---

## §4. 보안 관점 발견 (실측 확인분)

| # | 등급 | 내용 |
|---|---|---|
| S1 | **중** | **`/v1/dsl/{generate,validate,compile}` 3종이 인증만 요구하고 역할 게이트가 없다** (`api/dsl.py:167,250,263` = `CurrentUser`). 모듈 docstring이 *"관리자 발행은 후속 `RequireContentAdmin`으로 분리한다"*고 **스스로 미완을 자인**한다. 임의의 로그인 학생이 콘텐츠 생성 파이프라인을 호출할 수 있다 — 12단계 중 유일하게 관리자 게이트가 없는 쓰기 표면. |
| S2 | **중** | **승인 게이트의 HTTP 우회.** `PATCH /v1/problems/{id}`가 `body: dict[str, Any]`를 병합 후 `ProblemSchema`로만 재검증하므로(`api/problems.py:305,336-341`), CONTENT_ADMIN 토큰이면 `{"review_status":"approved"}` 한 줄로 `golden_promotion_gate` 4단 승격을 **완전히 우회**한다. 게이트가 코퍼스 JSONL 축에만 걸려 있다. |
| S3 | 정보 | **관리자 행위 감사 부재.** 콘텐츠 CUD(concepts·problems)에 감사 로그가 붙지 않는다 — 누가 어떤 문항을 승인·격리·삭제했는지 흔적이 없다. `record_admin_access_audit`은 ADMIN-06 전제의 dead code (`SEC-29`). |
| — | 해소 | 공개 GET 4종이 `approved`를 요구하지 않는 건(quarantined만 배제) **사고가 아니라 문서화된 결정**이다 — `api/problems.py:14-33`의 SEC-07 D1(공개 카탈로그 유지) + SEC-24(정답류는 `PublicProblem` 투영으로 구조적 제거, 키 부재가 계약) + EOS-71(격리 배제). 유출 범위는 지문·메타에 한정된다. |
| — | 확인됨 | `Role`은 **v0 2값 확정**(`STUDENT`·`CONTENT_ADMIN`, `schema/enums.py:1666`). `str` mixin을 안 쓰는 이유(서열 비교가 열리면 미성년 보호 매트릭스가 깨짐)까지 고정돼 있다. concepts·problems 쓰기 6라우트 전부 `RequireContentAdmin` — **누구나 POST 불가**. `/v1/me/harness-metrics`도 `RequireContentAdmin`으로 정정 완료(SEC-24). 데모 인증(`api/demo_auth.py`)은 명시 플래그 + 실 provider 존재 시 이중 거부. |

---

## §5. "EOS 1과목 완성" 최종 판정

| 축 | 판정 | 근거 요약 |
|---|---|---|
| **③ 시스템 경계** | 🟢 **충족** | 4층 실재 · 위반 0 · CI 매 PR 집행 · 수학어휘 밀도 34배 차. **단 필수층 계약 미배선** |
| **① 학생 흐름** | 🟡 **부분** | 14단계 중 11개 · 야간 E2E 6구간 관통 12일 연속 green · **끊김 3곳(G1·G4·G6)** — G1은 서버 축만 이 PR에서 해소 |
| **② 관리자 흐름** | 🔴 **미달** | HTTP 표면 3/12 · 사람 UI 0 · **게시 축 사망** · Skill 27건 · 감사 부재 |

### 완성까지 남은 것 (영향 큰 순)

1. ~~**G1 — 교육과정/학년 입력 경로**~~ → **서버 축 착지(`EOS-82`, 이 PR)** · 클라 축 잔여(`MOB-21`)
   `_SELF_EDITABLE`에 `grade`·`school_type`을 추가해 API를 열었고 테스트 8건이 동결한다
   (뮤테이션 2종으로 8건 전부 red 확인). **다만 앱 온보딩에 입력 화면이 아직 없어**
   실사용 값은 여전히 들어가지 않는다 — G1은 `MOB-21` 착지 시점에 닫힌다.
2. **ADMIN-12 — 게시 축 배선** 또는 명시적 폐기. 선언만 남은 컬럼은 다음 사람을 속인다.
3. **S1 — DSL 라우트 `RequireContentAdmin` 승격.** 코드가 스스로 적어 둔 미완이다.
4. **G4 — 오답→오개념 축 연결.** `distractor_map`이 이미 코퍼스에 있는데 서빙이 안 쓴다.
5. **ADMIN-04~07 — 검수/승인 UI 4단 체인** (전부 todo). 도메인 파트너가 CLI를 쓸 수는 없다.
6. **필수층 계약 배선** 또는 "선택층만으로 간다"는 명시적 결정 기록.
7. **Skill 축 확장 + `review_status` 데이터화** (27건 · 코드 상수 하드코딩).

---

## §6. 재현 명령

```bash
python3 scripts/analysis/eos_core_adapter_boundary_scan.py          # 경계 위반 0 확인
grep -n "importlinter" -A 160 src/backend/pyproject.toml            # 정적 계약 3건
python3 scripts/harness/backlog.py next --n 500 --json              # 전건(절단 금지)
python3 scripts/harness/backlog.py gates                            # 사람 게이트 8건 대기
grep -n "_SELF_EDITABLE" -A 20 src/backend/whymath_backend/api/users.py
wc -l data/corpus/skill_graph_v1/skills.jsonl                       # 27
```

라우트 전수(103건)는 AST 파싱으로 뽑았다 — 여러 줄 데코레이터 때문에 grep은 일부를 놓친다.
