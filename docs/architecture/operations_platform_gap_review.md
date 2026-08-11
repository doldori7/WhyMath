# 운영 플랫폼(Operations Platform) 모듈 — 외부 EOS 틀 대조 갭 점검·설계 (2026-08-03)

> ⚠️ **후속 리비전 있음 — `docs/architecture/operations_platform_gap_review_r2.md`(2026-08-11)**.
> 이 문서(v1 + §독립검증)는 **판정 시점 기록으로 보존**되며 본문은 수정하지 않는다. r2가 담은
> 델타: 판정 뒤집기 3건(D3 상환 · 2차원 매트릭스 계약 기계화 · **D1의 원인이 "미구현"에서
> "고립"으로 전환**) · 신규 설계 D5~D8 · 반복 실수 11회차 · 줄번호 드리프트 보정표.
> **이 문서의 줄번호 인용은 +51 드리프트가 있다**(`enums.py` 등 — r2 §1 말미 표 참조).

> **범위**: 외부 참고 문서 『21. 운영 플랫폼』(1단계 모듈 86 권한 관리 · 87 조직 관리 ·
> 88 학교 관리 · 89 라이선스 관리 · 90 감사(Audit) 로그, 세부 기능 약 90개 — **WhyMath 전용이
> 아닌 일반적인 SaaS 운영 틀**, Kiki 제공)을 현 코드베이스와 대조해 빠진 부분을 점검하고, 진짜
> 갭을 WhyMath 불변식(의사결정 우선순위 1 학생 웰빙 ≫ … ≫ 6 비용·효율 · dead code 금지 ·
> 이중 진실원천 금지 · 7단 선형 서열 금지 · 학습 게임화·우열 매기기 금지 · 법령 유래 절차의
> 기계 대체 금지) 안에서 설계한 기록.
> **형식**: `account_security_gap_review.md`(모듈 46~48, 2026-07-30) · `ai_recommendation_
> module_gap_review.md`(기능 80~83, 2026-08-01) 답습 — 같은 외부 EOS 틀 대조 시리즈의
> **11번째 자매편**.
> **결론**: 운영 플랫폼은 "통째로 없다"가 아니다 — 권한(86)·감사(90)의 **골격은 SEC-07~11로
> 이미 착지**했다. 진짜 갭은 **그 게이트를 통과할 사람을 만드는 경로가 0건**이라는 것이다(D1,
> 최우선). 조직·학교(87·88)·라이선스(89)는 좌석(계약·운영자) 자체가 없어 대부분 정직한 공백
> 이지만, 이미 있는 컬럼 4개가 소비처 0인 채 남아 "부분 구현된 것처럼" 오독을 유발한다(D2).
> 감사 2테이블의 보존 정책은 결정된 적이 없는데 사실상 무기한 보존 중이다(D3). 조직·학교·
> 라이선스 테넌시 자체는 D4로 페이퍼 설계만 남긴다(B2B 계약 전 코드 0). 진짜 갭 3건을 실행
> 설계(D1~D3)하고 1건을 페이퍼(D4)로 남겨 실행 태스크 3건을 백로그에 등재했다. 의도적 미채택
> 11건 · 정직한 공백 7종 · 유보 발화조건 6건. 정본 stale 4곳을 발견했고, 그중 2곳은 병렬
> 세션이 병합 시점 이전에 이미 독립적으로 정정해 §정정에서 갱신·기록만 하며, 남은 2곳(1곳은
> 상호보완, 1곳은 미해소)을 이번 대조에서 다룬다.

관련 정본: `docs/design/ui/04_admin_console_architecture.md`(Admin BFF·RBAC 원칙 3~4 정본) ·
`docs/design/ui/03_admin_console_plan.md`(관리 자원 인벤토리) · `docs/architecture/account_
security_gap_review.md`(D1 SEC-07·§4-⑧ 테넌시 유보 — 본 문서가 그 후속) · `docs/architecture/
operations_module_gap_review.md`(동명이의 — 다른 외부 틀, §0 참조) · `docs/legal/pipa_data_
matrix.md`(역할×데이터 항목 2차원 인가 정본) · `docs/standards/security_privacy.md` ·
`CLAUDE.md` 절대 금기(프로세스·안내·보안) · `MEMORY.md` 결정 로그(2026-08-03).

---

## §0. 전제

### ①-a 착수 가설이 절반 반증됐다

착수 가설은 **"운영 플랫폼은 통째로 없다"** 였다. 실측하니 절반만 맞다.

1. **감사·인증·역할 게이트는 이미 섰다** — `deletion_audit`·`privacy_audit`(SEC-09) ·
   `refresh_token_session` 회전+재사용 탐지 · `Role` enum + `UserProfile.role` +
   `require_content_admin`(SEC-07) · OAuth state·redirect allowlist·rate limit(SEC-08).
   "코드가 없다"는 가설은 틀렸다.
2. **그런데 그 게이트를 통과할 방법이 없다.** `require_content_admin`이 콘텐츠 CUD 6라우터를
   지키지만, `Role.CONTENT_ADMIN`을 부여하는 코드 경로가 **저장소 전체에 0건**이다
   (`.role =` 대입, `role=Role.CONTENT_ADMIN` 생성 kwarg — grep 전수 무일치). `api/auth.py:146`
   `resolve_user`는 role 인자 없이 사용자를 만들어 전원 `server_default='student'`로 남는다.
   **문을 만들고 열쇠를 만들지 않은 것**이다.
3. 이 두 사실을 합치면 진단이 바뀐다: "운영 플랫폼이 없다"가 아니라 **"봉인(SEC-07의 의도)과
   좌석 부재(설계 공백)가 지금 똑같은 403을 낸다"**. CUD 라우터를 호출하면 봉인이 정상 작동
   중인지, 운영자를 못 만들어서 아무도 못 쓰는 중인지 **구분되지 않는다** — CLAUDE.md "변별력
   없는 검증 스텝 금지"(2026-07-17 등재)의 **인가(authorization) 판**이다.

### ①-b 동명이의 처리 (선결)

`docs/architecture/operations_module_gap_review.md`(2026-07-29)가 **이미 존재**하며 "운영
(Operations)" 명칭을 쓴다. 그러나 대상은 **다른 외부 틀의 다른 모듈**(기능 42~50 = 콘텐츠
저작권·CMS·버전관리·QA·배포·백업·모니터링)이다. 이번 문서는 그 문서와 무관한 **1단계 운영
플랫폼 틀**(기능 86~90 = 권한·조직·학교·라이선스·감사)을 다룬다. 혼동 방지를 위해 파일명을
`operations_platform_`으로 구분한다(그 문서 §0의 "EOS" 동명이의 처리와 같은 취지의 선결).

### ①-c 틀의 아키텍처와 정본의 차이 (갭 판정의 전제)

| 틀이 전제하는 것 | WhyMath 정본의 실제 | 근거 |
|---|---|---|
| 다기관 SaaS(학교·학원·교육청 동시 운영) | **단일 B2C 앱**(Phase 1~3), B2B는 Phase 4+ | `ROADMAP.md:17` "4. B2B — 18~30개월" |
| 8단 조직 위계(교육청→학교→학급→학생) | **학생 프로필 속성**(`school_type`·`grade`)만 존재, 조직 엔티티 0 | `db/models/user.py:90-93` |
| 좌석 판매·라이선스 계약 관리 | **결제 시스템 자체가 Phase 1.5~2 예정**, 현재 코드 0줄 | `ROADMAP.md:119` "❌ 결제 시스템(Phase 1.5 또는 Phase 2)" |
| 역할 7~8단 선형 위계 | **2값(STUDENT/CONTENT_ADMIN) + 2차원(역할×데이터) 매트릭스**, 선형 서열 구조적 차단 | `schema/enums.py:1163-1194`·`pipa_data_matrix.md` |

**갭 판정 기준**: 이 문서는 "조직·라이선스가 없다"를 그 자체로 갭으로 세지 않는다(좌석 0에서는
§2 미채택이거나 §4 정직한 공백). 갭은 **①이미 만든 게이트가 통과 불가능하거나, ②이미 만든
컬럼이 소비처 없이 오독을 유발하거나, ③이미 실재하는 데이터(감사)의 정책이 결정된 적 없는
지점**에서만 성립한다.

---

## §1. 기능 86~90 전수 대조

판정 기호: `✅` 충족·초과 / `✅ **단, …**` 충족이지만 단서 있음 / `△` 부분(부품은 있으나
배선·소비처 없음) / `⚠️` 진짜 갭 → D / `🚫` 의도적 미채택 → §2 / `⏸` 좌석 0(정직한 공백) → §4

### 기능 86 — 권한 관리 (Authorization Management)

**역할(Role) 관리** (8종 제안)

| 세부 항목 | WhyMath 현행 | 판정 |
|---|---|---|
| 학생 | `Role.STUDENT`(기본 발급) | ✅ |
| 교사 | 역할 미도입 — `pipa_data_matrix.md`가 "B2B 맥락의 담당 강사"로 별도 정의, Phase 3+ | 🚫 §2-① |
| 학부모 | 역할이 아니라 `parental_consent` 별도 축(동의 주체이지 로그인 주체 아님) | 🚫 §2-② |
| 학교 관리자 | 좌석 0 | ⏸ §4-① |
| 교육청 관리자 | 좌석 0 | ⏸ §4-① |
| 콘텐츠 관리자 | `Role.CONTENT_ADMIN` — enum·컬럼·게이트 실재 | ✅ **단, 부여 경로 0건** → **D1** |
| 운영 관리자 | `CONTENT_ADMIN`과 구분되는 권한 항목이 아직 없음(SEC-07 결정) | 🚫 §2-③ |
| 시스템 관리자(Super Admin) | 미도입(dead code 금지 — 좌석 없는 역할) | 🚫 §2-③ |

**권한(Permission) 관리** (8종 제안)

| 세부 항목 | WhyMath 현행 | 판정 |
|---|---|---|
| 메뉴 접근 권한 | 클라(Flutter)가 역할별 화면을 결정하지 않음 — 서버는 API 인가만, "메뉴" 개념 자체가 클라 UI 관심사(표현≠의미) | 🚫 §2-④ |
| 콘텐츠 생성/수정/삭제 | `api/concepts.py:244/342/391`·`api/problems.py:57/184/231` — `RequireContentAdmin` 부착(SEC-07) | ✅ **단, D1과 동일 결함** |
| 문제은행 관리 | 콘텐츠 CRUD와 동일 표면 | ✅ (상동) |
| AI 기능 사용 권한 | `app.py:679` `POST /v1/generate` — `CurrentUser`(역할 불문, 인증만). 세분화된 "AI 기능" 권한 항목 없음 | △ (§4-②) |
| 보고서 조회 | `ops/cost_report.py`·`ops/cost_probe.py` — **HTTP 미노출**(CLI 전용), 권한 개념 자체가 무의미(인터넷에 없음) | 🚫 §2-⑤ |
| 사용자 관리 | `api/users.py`(GET/PATCH 본인만), 타인 사용자 관리 API 0건 | ⏸ §4-① |
| 시스템 설정 변경 | `config.py` env 단일 진실원천, 런타임 편집 UI 없음(의도적) | 🚫 §2-⑥ |
| API 접근 권한 | API 키·클라이언트 인가 개념 없음 — JWT 사용자 인증만 | 🚫 §2-⑦ |

**고급 기능** (6종 제안)

| 세부 항목 | WhyMath 현행 | 판정 |
|---|---|---|
| RBAC | `require_role`(`api/_auth.py:96`) — 역할 게이트 실재 | ✅ |
| 세분화된 권한(Granular Permission) | 역할=단순 열거값 비교뿐, 2차원(역할×데이터항목) 매트릭스는 **`pipa_data_matrix.md`에 설계만** 있고 인가 코드로 구현되지 않음 | △ (§4-③) |
| 권한 상속 | 미도입 — 선형 서열의 다른 이름 | 🚫 §2-⑧ |
| 임시 권한 부여(TTL) | 미도입 | 🚫 §2-⑨ |
| 다중 조직 권한 | 조직 엔티티 자체가 0 | 🚫 §2-⑩ |
| SSO 및 OAuth 연동 | 카카오·네이버 provider 구현 실재(`api/oauth_providers.py`) + state·redirect allowlist(SEC-08) | ✅ **단, 클라 code 획득 스텁이라 실 로그인 0회**(account §1 모듈46 승계) |

### 기능 87 — 조직 관리 (Organization Management)

| 세부 항목 | WhyMath 현행 | 판정 |
|---|---|---|
| 조직 구조(교육청·학교·학원·기업교육·개인학습그룹) | 엔티티 0 — `organization`/`tenant` 테이블 전무(ORM 63테이블 grep 무일치) | ⏸ §4-④ → **D4(페이퍼)** |
| 조직 생성·계층·이동·병합·정책설정·통계 | 상동 | ⏸ §4-④ |
| 조직 관리자 지정·교사 배정·학생 배정·그룹/반 관리·권한 위임 | `db/models/user.py:93` `school_id`(FK 없는 고아 컬럼, 읽기·쓰기 코드 0건) 외 전무 | ⚠️ **D2**(dead 컬럼) + ⏸ §4-④ |

### 기능 88 — 학교 관리 (School Management)

| 세부 항목 | WhyMath 현행 | 판정 |
|---|---|---|
| 학교 등록·학년 관리 | `school_type`(enum 12종)·`grade`(Integer) — **학생 프로필 속성**으로만 존재, 학교 엔티티 아님 | △ (경계만 존재 — §4-④) |
| 학급 관리 | `class`/`classroom` 테이블 0 | ⏸ §4-④ |
| 교사 관리·학생 관리(기관 시점) | 학생은 `user_profile` 개인 단위로만 존재, 기관 소속 조회 불가 | ⏸ §4-④ |
| 학기 관리·시간표 연동·성적 연동·출석 연동·과제 관리·시험 일정 관리 | 전무 — NEIS 등 외부 학사 시스템 연동 없음 | 🚫 §2-⑪ |
| 학교 성취도 분석·학년별 통계·학급 비교·교사 활동 분석·학교 리포트 | 전무 | 🚫 §2-⑫ |

### 기능 89 — 라이선스 관리 (License Management)

| 세부 항목 | WhyMath 현행 | 판정 |
|---|---|---|
| 라이선스 종류(개인·학교·학원·교육청·기업·체험판·프리미엄) | `SubscriptionTier`(`schema/enums.py:784`) — **free/basic/premium 3값뿐**, B2B 종류 없음 | ⚠️ **D2**(dead 컬럼) |
| 라이선스 발급·만료일·사용자수·기능제한·자동갱신·계약이력 | `subscription_started_at`·`subscription_renewed_at` 컬럼 존재하나 **읽는 코드 0건**(결제 시스템 부재) | ⚠️ **D2** |
| 활성 사용자·라이선스 사용률·남은 좌석수·기능이용통계 | 전무 — `is_active`(계정 활성)는 있으나 좌석 개념과 무관 | ⏸ §4-⑤ |
| 계약 현황 Dashboard | 콘솔 자체가 0(`04_admin_console_architecture.md` §8 제안 단계) | ⏸ §4-⑤ |
| (참고) 콘텐츠 저작권 라이선스 `LicenseType`(`enums.py:444`) | 실재하나 **이 모듈과 다른 축**(상용 라이선스 아니라 콘텐츠 출처 라이선스) — `ARCH-20`이 그 집행 게이트를 별도로 다룬다 | ✅ (경로 다름, 혼동 금지) |

### 기능 90 — 감사(Audit) 로그

**사용자 활동**

| 세부 항목 | WhyMath 현행 | 판정 |
|---|---|---|
| 로그인/로그아웃 | 감사 테이블에 미기록(리프레시 세션 자체는 `refresh_token_session`에 있으나 "감사" 목적 append-only 기록 아님) | 🚫 §2-⑬(정직한 공백 §4-⑥) |
| 권한 변경 | `AuditEventKind` 3종(export_data/consent_change/admin_access)에 **`role_change` 없음** — 역할 부여 자체가 불가능하니(§0-①-2) 지금은 당연히 0건 | ⚠️ **D1**(D1과 함께 해소) |
| 비밀번호 변경 | 비밀번호 자체가 없음(SSO 전용 — account §2-③ 승계) | 🚫 (구조적 무해당) |
| 계정 생성/삭제 | 삭제는 `deletion_audit`(SEC-07 이전부터 실재) — 생성은 미기록(로그인 성공 자체가 미감사이므로 상동 이유) | ✅ 삭제만 / 🚫 생성(§2-⑬) |
| 개인정보 조회 | 본인 조회 29개 엔드포인트는 **의도적 미감사**(프로파일링 자산화 회피). 본인 아닌 조회(`admin_access`)는 writer만 있고 호출부 0(콘솔 부재) | 🚫 본인조회 / △ 관리자조회(§5-②) |
| 콘텐츠 수정 | 콘텐츠 CUD 감사 없음(권한 게이트는 있으나 감사 없음) | ⏸ §5-② |

**시스템 활동**

| 세부 항목 | WhyMath 현행 | 판정 |
|---|---|---|
| 설정 변경 | `config.py` env 부팅시 고정, 런타임 변경 자체가 없어 감사 대상 무의미 | 🚫 §2-⑥ 승계 |
| AI 모델 변경 | 모델 라우팅은 요청 단위 자동 결정(`l3/router.py`)이지 사람이 "변경"하는 설정이 아님. 라우팅 결정은 `l3_routing`(Langfuse) 이벤트로 별도 관측 — 감사와 목적이 다름(운영 감사 아니라 비용 관측) | ✅ (경로 다름) |
| 데이터 수정 | 콘텐츠 CUD와 동일(§상동) | ⏸ §5-② |
| 백업/복구 | `docs/architecture/db_backup_dr_runbook.md`(OPS-02) — 스크립트 로그·수동 리허설 기록. **DB 감사 테이블 아님**(런북 산출물) | ✅ (경로 다름, 운영 런북) |
| 배포 기록 | `docs/architecture/deployment_cd_runbook.md`(OPS-03) + Git 커밋/PR 이력 — **DB 감사 테이블 아님**(형상관리가 기록) | ✅ (경로 다름) |
| 장애 처리 | `docs/standards/incident_response_slo.md` 런북 프로세스 — DB 감사 아님 | ✅ (경로 다름) |

**감사 기능**

| 세부 항목 | WhyMath 현행 | 판정 |
|---|---|---|
| 변경 이력(Who, When, What) | `deletion_audit`·`privacy_audit`은 이벤트 종류·행위자·시각만(대상 리소스의 **이전값/변경값은 없음** — 삭제·반출·동의변경은 애초 "값 비교"가 무의미한 이벤트라 설계상 불필요) | ✅ (현재 이벤트 종류 범위 안에서 충분) |
| 이전 값/변경 값 비교 | 콘텐츠 CUD·역할 변경처럼 "값이 바뀌는" 이벤트의 비교 로그는 없음(§5-②·D1 범위 밖) | ⏸ §5-② |
| 검색 및 필터 | `GET /v1/me/deletions`·`GET /v1/me/privacy-audit` — 본인 스코핑만, 관리자 검색 API 0(콘솔 부재) | △ (본인만) |
| 장기 보관 | `deletion_audit`·`privacy_audit`은 `_RETENTION_PLAN`(`privacy/retention.py:46`)에 **미포함 = 사실상 무기한**. 그 결정이 문서 어디에도 명문화되지 않음 | ⚠️ **D3** |
| 감사 보고서 생성 | 자동 생성 없음(SQL 조회로 대체 가능한 현재 행수 규모) | 🚫 §2-⑭ |
| 이상 행위 탐지 | 미도입 | 🚫 §2-⑮(account §2-⑩ 승계) |

---

## §2. 의도적 미채택 판정 (15건 — 협상 불가 근거)

| # | 문서 제안 | 불채택 근거 |
|---|---|---|
| ① | 8단 선형 역할(학생↓교사↓학부모↓학교↓교육청↓콘텐츠↓운영↓Super Admin) | `pipa_data_matrix.md:33-47`이 반증(부모 열은 학생 열의 부분집합이지 하위집합이 아님). `schema/enums.py:1179-1184`가 이미 `str` mixin 미사용으로 서열 비교 연산을 구조적으로 차단 — **`account_security_gap_review.md` §2-① 승계, 재판정 아님** |
| ② | 학부모를 로그인 **역할**로 승격 | 학부모는 *동의 주체*(`parental_consent`)이지 앱 로그인 주체가 아니다. 역할로 승격하면 §2-①의 선형 서열 문제가 학부모 축에서 재발한다 |
| ③ | `SYSTEM_ADMIN`을 `CONTENT_ADMIN`과 별도 역할로 신설 | 지금 구분할 **권한 항목이 없다**(SEC-07 결정 승계). 좌석 없는 역할은 dead code — 역할 추가는 마이그레이션 1줄이라 필요해지면 즉시 연다 |
| ④ | 메뉴 접근 권한(화면 단위 인가) | **표현 ≠ 의미** — 화면 구성은 클라(Flutter) 관심사다. 서버는 API 리소스 단위로만 인가하고, "메뉴"라는 UI 개념을 코어에 넣지 않는다 |
| ⑤ | 보고서 조회 권한 UI | `cost_report`·`cost_probe`는 **HTTP 미노출**(인터넷에 없는 CLI). 노출 자체가 없는 표면에 권한 개념을 만드는 것은 dead code |
| ⑥ | 시스템 설정 변경(런타임 정책 편집 UI) | `config.py` env가 **단일 진실원천**이고 부팅 시 검증된다. 런타임 오버라이드를 열면 "설정이 두 곳"이 된다(이중 진실원천 금지) — `account_security_gap_review.md` §2-⑦ 승계 |
| ⑦ | API 접근 권한(API 키 발급) | 클라는 사용자 JWT로만 인증한다. 별도 API 키 체계는 지금 소비처가 없다(외부 파트너 API 연동 계약이 생길 때 발화) |
| ⑧ | 권한 상속 | 선형 서열의 다른 이름 — 2차원(역할×데이터 항목) 매트릭스와 양립 불가 |
| ⑨ | 임시 권한 부여(TTL) | 좌석 자체가 0인 상태에서 만료 로직은 dead code. CLI grant/revoke(D1)로 즉시 회수 가능해 TTL의 실익도 낮다 |
| ⑩ | 다중 조직 권한 | 조직 엔티티 자체가 0(D4 페이퍼 대상) |
| ⑪ | 시간표·성적·출석 연동(NEIS 등 외부 학사 시스템) | 계약·법령 표면(교육기관 시스템 연동)이고, 성적·출석 원자료 반입은 미성년 PII를 새로 늘린다(우선순위 2). Phase 4 B2B + 변호사 검토 없이는 착수 자체가 위험 |
| ⑫ | 학교 성취도 분석·학급 비교·교사 활동 분석 | **CLAUDE.md 게임화 금기와 정면 충돌** — `pipa_data_matrix.md` #8(또래 비교)은 학생 본인조차 ◐(요약만), 부모는 ✕로 둔다. 학급/학교 단위 *순위* 비교는 그 매트릭스를 기관 단위로 우회하는 형태다. 채택하려면 서열이 아닌 형태(개념 커버리지·오개념 분포)로 바꿔야 한다 — 대체 방향은 §3 D4 |
| ⑬ | 로그인/로그아웃·계정 생성을 감사 테이블에 기록 | `AuditEventKind` 설계 결정(`schema/enums.py:1114-1123`)이 **"시스템 밖으로 나가는 사건"과 "본인 아닌 주체의 접근"만** 감사 대상으로 좁혔다(`account_security_gap_review.md` D3 경계 승계). 로그인은 시스템 안에서 일어나는 본인 행위라 대상 밖 — `refresh_token_session`(세션 allowlist)이 이미 로그인 상태를 추적하므로 이중 진실원천도 된다 |
| ⑭ | 감사 보고서 자동 생성 | 콘솔 Phase B 이후. 현재 감사 2테이블 행수 규모(수백~수천 행)에서 SQL 조회로 충분 — 자동화는 측정 없는 도입 |
| ⑮ | 이상 행위 탐지 | `account_security_gap_review.md` §2-⑩ 승계 — 공격 트래픽 0인 파일럿 규모에서 탐지기는 오탐 + 경고 습관화(fail-open 소음) 리스크가 실익보다 크다 |

---

## §3. 진짜 갭 설계

### D1 — 운영자 좌석 발급 경로 + 역할 변경 감사 (최우선)

**문제**: `require_content_admin`(`api/_auth.py:123`)이 콘텐츠 CUD 6라우터를 지키지만,
`Role.CONTENT_ADMIN`을 부여하는 코드 경로가 저장소 전체에 **0건**이다. 지금 열려면 prod DB에
원시 SQL `UPDATE`를 날리는 수밖에 없다 — CLAUDE.md "모든 DB 접근은 ORM" 위반이자 **무감사**
(누가 언제 왜 부여했는지 기록이 남지 않는다), 재현 불가능한 수동 조작이다. 동시에
`AuditEventKind`(`schema/enums.py:1114`)에 권한 변경 어휘가 없어, 지금 부여를 만들더라도
**기록할 곳이 없다**.

**왜 아무도 몰랐는가 — 변별력 없는 실패**: CUD 라우터에 인증 없이 요청하면 401, 인증됐지만
`student` 역할이면 403이 뜬다. 이 403은 **"봉인이 정상 작동 중"**(SEC-07의 의도된 결과)과
**"운영자를 만들 방법이 없어서 아무도 못 쓰는 중"**(설계 공백)을 구분하지 못한다. 두 상태가
같은 값을 낸다 — CLAUDE.md "변별력 없는 검증 스텝 금지"의 인가 판.

**핵심 판단(Kiki 결정, 2026-08-03)**: **부여 CLI와 감사를 한 태스크로 묶는다.** 04
`admin_console_architecture.md` §2 원칙 4가 "감사 없는 쓰기 액션 금지"를 명령하므로, 무감사
부여 경로를 먼저 만드는 것 자체가 그 정본 위반이다. 관리자 HTTP API·콘솔 UI는 **범위 밖**
(§5-①) — 지금은 **CLI 한 장으로 충분**(운영자 좌석이 아직 1명도 없는 단계에서 웹 UI는
과설계).

**정합 설계**(신규 테이블 0 · HTTP 표면 0 · 신규 역할 0):
1. `python -m whymath_backend.ops.role_grant_cli`(신설) — `privacy/retention_purge_cli.py`·
   `agreement_gate_cli`와 동일한 ops CLI 컨벤션(argparse·JSON stdout·종료 코드로 성공/실패
   판정). 서브커맨드: `grant <user_id> <role>` / `revoke <user_id>` / `list`. **HTTP
   미노출**(권한 상승 표면을 인터넷에 열지 않는다 — 배포 런북과 같은 "전역 배치는 HTTP
   비노출" 컨벤션).
2. `AuditEventKind`에 `role_change` 1값 추가 → **기존 `privacy_audit` 테이블을 재사용**한다
   (신규 테이블 0). 역할은 계정 속성이므로 개인정보 감사 축이 맞다. `record_role_change_audit`
   writer는 CLI가 첫 소비자.
3. 부여/회수와 감사 1행은 **동일 트랜잭션**(`api/me.py:291` `_delete_owned_resource`의 삭제
   감사 동일-TX 패턴 답습).

**dead code 금지 충족**: 신규 테이블 0(기존 `privacy_audit` 재사용). enum 1값 추가는 즉시
소비처(CLI writer)가 있다. **측정 없는 도입 없음**: `list` 서브커맨드가 현재 좌석 0명임을
그대로 보여준다(숨기지 않는다). **변별력**: 부여 전/후/회수 후 3상태가 서로 다른 HTTP 코드를
내는지 실측 — 같은 값이면 이 설계 자체가 실패다.

**acceptance 후보**
1. ① 현행 실측 고정 — `CONTENT_ADMIN` 사용자 0명 상태에서 CUD 6라우터 전건 403 재현(주장
   확인 또는 반증 — 반증되면 범위 재조정)
2. ② CLI `grant`/`revoke`/`list` 동작 + 존재하지 않는 `user_id`·잘못된 역할명 거부(비0 종료
   코드 + 사유 문자열)
3. ③ 부여/회수와 `role_change` 감사 1행이 **동일 트랜잭션**임을 동결(강제 롤백 시 감사 행도
   함께 사라짐을 실측)
4. ④ CI 배선 실재 확인 — 신규 테스트가 실제로 CI에서 실행되는지 확인(OPS-03·OPS-10 —
   "저장소에 존재함"과 "돌아감"은 다르다)
5. ⑤ 변별력 — 부여 전 403 → 부여 후 201/200 → 회수 후 다시 403의 **3상태 왕복**을 실측.
   같은 값을 내면 검증이 아니라 위장이다
6. ⑥ 범위 밖 동결 — 관리자 HTTP API(`/v1/admin/*`)·콘솔 UI·`SYSTEM_ADMIN` 역할 신설은
   포함하지 않는다(§5-①)

**의존**: 없음(즉시 착수). **태스크**: 신설.

### D2 — dead 스키마 정직화: `school_id` + `subscription_*` 4컬럼

**문제**: 읽는 코드가 0건인 컬럼 4개(`school_id`·`subscription_tier`·
`subscription_started_at`·`subscription_renewed_at`)가 스키마에 남아 있다. 존재 자체가 "조직·
과금이 부분적으로 이미 구현됐다"는 오독을 유발한다. `account_security_gap_review.md:421`
§4-⑧이 "`school_id` 컬럼만 있고 `school` 테이블 없음"을 이미 **자인**했지만, 자인만 하고
정리는 하지 않은 채 남았다.

**왜 아무도 몰랐는가**: SEC-07은 좌석 없는 역할 3종(`PARENT`·`TEACHER`·`SCHOOL_ADMIN`)을
*만들지 않는* 쪽을 택했다(dead code 금지). 그런데 같은 기준을 **이미 만들어져 있던 컬럼**에는
적용하지 않은 비대칭이 있었다 — 새로 만들 것은 걸렀지만, 이미 있던 것은 걸러진 적이 없다.

**핵심 판단(Kiki 결정, 2026-08-03)**: **드롭을 기본으로 하되, 실측이 반증하면(prod에 비영행
존재) 동결로 전환한다.** 근거는 Role v0 논리 그대로 — "재도입은 마이그레이션 1줄이고, 잘못
남긴 것을 걷어내는 비용이 더 크다". **경계**: `school_type`·`school_region`·`grade`는
**실제 소비처가 있는 학생 프로필 속성**이므로 유지한다(조직 엔티티와 혼동 금지 — §1 기능88
표 참조).

**정합 설계**(신규 테이블 0 · 신규 컬럼 0 · 대상은 삭제 후보뿐):
1. `school_id`(`user.py:93`) — FK 없는 고아 UUID 컬럼. 소비처 0.
2. `subscription_tier`·`subscription_started_at`·`subscription_renewed_at`(`user.py:142-146`)
   — 결제 시스템 부재로 값이 채워질 경로 자체가 없음.

**dead code 금지 충족**: 컬럼 4개 제거, 신규 0. **측정 없는 도입 없음**: 해당 없음(제거
작업). **변별력**: 드롭 마이그레이션 적용 전/후 컬럼 목록 스냅샷 diff가 실제로 달라지는지
실측.

**acceptance 후보**
1. ① 현행 실측 고정 — 4컬럼 소비처 0건 재현 **+ prod DB에 비영(非零) 행이 있는지 확인.
   비영이면 드롭 대신 "미사용 자인 주석 + 동결 테스트"로 범위 재조정**(Kiki 확인 필요 — 이
   확인은 사람 행동 게이트일 수 있음)
2. ② 드롭 마이그레이션 작성 + `tests/backend/api/test_no_lockout_columns.py`의 컬럼 스냅샷
   목록 동기화(41개 → 37개)
3. ③ 유지 대상(`school_type`·`school_region`·`grade`)이 함께 지워지지 않음을 동결
4. ④ 전체 스위트 green(부분 스위트 통과를 전체 통과의 근거로 보고하지 않는다 — CLAUDE.md
   프로세스 금기)
5. ⑤ 범위 밖 — `organization`/`school`/`license` 테이블 신설은 하지 않는다(§3 D4·§5-③)

**의존**: 없음. **주의**: prod 데이터 확인이 필요할 수 있어 Kiki 확인 게이트가 붙을 수 있다.
**태스크**: 신설.

### D3 — 감사 보존·파기 정책의 침묵 공백

**문제**: `deletion_audit`·`privacy_audit` 두 감사 테이블은 `_RETENTION_PLAN`
(`privacy/retention.py:46`)의 대상이 **아니다** = 사실상 무기한 보존이다. 그런데 이 결정이
`retention.py` 주석에도, `security_privacy.md`에도, `pipa_data_matrix.md`에도 **한 줄도
없다**. 감사 행은 `user_id`·`ip_hash`를 담으므로 무기한 보존은 데이터 최소화 원칙과 긴장
관계인데, 지금 상태는 "의도적으로 무기한"인지 "빠뜨려서 무기한"인지 **구분되지 않는다**.

**왜 아무도 몰랐는가**: `_RETENTION_PLAN`·`_ERASURE_PLAN` 둘 다 "학습 활동·PII 시계열"을
대상으로 설계됐고(`retention.py:43` 주석), 감사 테이블은 애초 그 논의에 들어간 적이 없다 —
누락이 아니라 **범위 밖으로 취급된 채 한 번도 재검토되지 않은 것**이다.

**핵심 판단(Kiki 결정, 2026-08-03)**: **연한 숫자를 지금 정하지 않는다** — 보존 연한 확정은
법령 유래 판단이라 CLAUDE.md "법령 유래 절차의 기계 대체 금지"에 해당하며 변호사 검토가
선행돼야 한다. 이번 범위는 **현행 동작의 명문화 + 동결**까지다.

**정합 설계**(신규 테이블 0 · 신규 컬럼 0 · 파기 로직 변경 0):
1. `privacy/retention.py` 모듈 docstring에 "감사 2테이블은 `_RETENTION_PLAN` 의도적 미포함
   + 사유(법정 증빙 성격 · 연한 미확정)"를 명문화.
2. `docs/standards/security_privacy.md`에 동일 사실을 1줄 추가.
3. 미포함 상태를 **동결 테스트**로 고정 — 미래 세션이 조용히 감사 테이블을 파기 대상에
   추가하지 못하게 한다(추가하려면 이 테스트를 먼저 고쳐야 하므로 신호가 된다 —
   `test_no_lockout_columns.py`의 "의도된 미도입 동결" 패턴 답습).

**dead code 금지 충족**: 코드 변경 0(테스트+문서만). **측정 없는 도입 없음**: 해당 없음
(정책 명문화). **변별력**: 감사 테이블을 `_RETENTION_PLAN`에 넣으면 동결 테스트가 실제로
실패하는지 확인 — 실패하지 않으면 테스트 자체가 무효다.

**acceptance 후보**
1. ① 현행 실측 고정 — 감사 2테이블이 `_RETENTION_PLAN`·`_ERASURE_PLAN` 어디에도 대상이
   아님을 재현
2. ② `retention.py` docstring + `security_privacy.md`에 명문화(코드 로직 0)
3. ③ 동결 테스트 신설 — 감사 2테이블 모델이 `_RETENTION_PLAN`에 없음을 단언
4. ④ 변별력 — 위 동결 테스트를 감사 테이블이 포함된 상태로 되돌려 실제로 실패하는지 확인
   (성공/실패 양쪽에서 같은 결과면 검증이 아니라 위장이다)
5. ⑤ 범위 밖 — 보존 연한 숫자 확정·자동 파기 배선은 하지 않는다(§5-④, `MGMT-02` 변호사
   회신 선행)

**의존**: 없음(즉시 착수). **태스크**: 신설.

### D4 — 조직·학교·라이선스 테넌시 (**페이퍼 — 코드 0 · 태스크 신설 없음**)

Kiki 결정에 따라 이번 범위는 **목표 형태와 발화조건만** 문서로 확정한다. 지금 태스크를 만들면
좌석 0인 채로 dead task가 된다.

**목표 엔티티 스케치(착지 시)**: `organization`(자기참조 계층 — `parent_org_id`, `org_type`
∈ {교육청/학교/학원/기업}) → `school`은 `organization`의 한 종류로 흡수(별도 테이블 불필요,
`org_type='school'`) → `class_group`(조직 소속·담당 교사·소속 학생 N:M) → `license`
(조직당 1계약, `plan_tier`·`seat_limit`·`expires_at`) + `license_seat`(좌석 배분, 학생 N:M).
**4엔티티가 아니라 사실상 3엔티티**(조직이 학교를 흡수) — 문서의 8단 위계보다 얇게 설계한다
(anti-explosion).

**인가는 새로 설계하지 않는다**: `pipa_data_matrix.md`의 2차원(역할×데이터 항목) 매트릭스가
이미 정본이다. 조직 테넌시가 착지해도 그 매트릭스에 **스코프 축(어느 조직 소속인가)**을
추가할 뿐, 선형 서열을 재도입하지 않는다 — "교사가 학생 위에 있다"가 아니라 "이 교사는 이
조직 소속 학생의 이 데이터 항목만 본다"는 형태를 유지한다.

**§2-⑫(학급 비교) 대체 방향**: 순위·우열 지표가 아니라 **개념 커버리지·오개념 분포**처럼
학생 개인을 서열화하지 않는 집계만 노출한다. 기관 단위 지표를 만들 때도 게임화 금기를
우회하는 형태(익명화된 순위 등)는 채택하지 않는다 — 이 제약은 스코프 축이 생겨도 유효하다.

**라이선스는 `subscription_tier` 부활이 아니다**: 상용 라이선스는 `subscription_tier`
(B2C 개인 구독)와 **다른 축**의 신규 엔티티(`license` — B2B 조직 계약)로 설계한다. 과금
컬럼을 인가 판단에 재사용하면 "구독 등급 = 권한"이 되어 §1 기능86 2차원 매트릭스와 충돌한다.

### 등재 요약

| 태스크 | 설계 | stage | priority | 근거 |
|---|---|---|---|---|
| ~~`ADMIN-01-operator-seat-grant-audit`~~ **done(2026-08-11 회수 착지)** | D1 | S4 | 2 | **CONTENT_ADMIN 부여 경로 0건** — 게이트는 섰으나 아무도 통과 못함. 최우선(되돌릴 수 없음은 아니지만 다른 모든 관리자 표면의 선결). **경위**: 구현(`8924a2e2`)이 미머지 브랜치에 6일 고립돼 있던 것을 cherry-pick으로 회수(충돌 0). 상세·회수 교훈 = `operations_module_gap_review_r3.md` §6-1. **주의 — 코드 착지 ≠ 데드락 해소**: prod 좌석이 0건인 동안 CUD 6라우터는 여전히 전건 403이며, `G-operator-seat-first-grant`(Kiki) clear 후에야 닫힌다 |
| `ADMIN-02-dead-tenancy-billing-columns` | D2 | S4 | 3 | dead 컬럼 4개 — "부분 구현된 것처럼" 오독 제거. **신규 컬럼 0**(제거만) |
| `ADMIN-03-audit-retention-policy` | D3 | S4 | 3 | 감사 2테이블 보존 정책 미결정 명문화 + 동결. **코드 로직 0** |
| D4(조직·학교·라이선스) | 페이퍼 | — | — | **태스크 신설 없음** — B2B 계약 체결 시 발화(§5-③) |
| `SEC-07`(기존) | Role v0·`require_content_admin` | — | — | **완료·승계** — D1이 그 위에 좌석 발급만 얹는다 |
| `SEC-09`(기존) | `privacy_audit`(SEC-09) | — | — | **완료·승계** — D1이 `role_change` 값만 추가 |
| `SEC-10`/`SEC-12`(기존) | 세션 가시성/보존 파기 배선 | — | — | **승계·재설계 금지** — 착수 시점 todo였으나 이 세션 진행 중 병합된 `e77218b`(2026-08-03, "SEC-10 세션 가시성·전체 로그아웃 + SEC-12 보존 파기 스케줄 배선")로 **done 전환**. D3(감사 2테이블이 `_RETENTION_PLAN` 미포함)과는 별개 축 — SEC-12는 *학습 활동 시계열*의 보존 파기 스케줄 배선이고, D3는 *감사 로그*(`deletion_audit`·`privacy_audit`) 보존 연한 미결정을 다룬다. 병합 후 `privacy/retention.py:46` `_RETENTION_PLAN` 재확인 — 감사 2테이블 여전히 미포함, D3 유효 |
| `MGMT-02`(기존) | 변호사 문안 회신 | — | — | **승계**(blocked) — D3의 보존 연한 확정이 이 태스크 회신을 전제 |
| `04_admin_console_architecture.md` §8 ADMIN-BFF/REVIEW-UI/WEB | 관리자 HTTP API·콘솔 UI | — | — | **등재하지 않는다** — 콘솔 Phase B 발화 전까지 dead task(§5-①) |

태스크는 전건 `backlog.py add` CLI 경유로 등재했다(ID 손편집 0 · 번호 충돌은 CLI가 로컬+원격
양쪽 검사 — HARN-10). `--path` 선언으로 겹침 검사를 켰다. `validate` green 확인은 부록·
`MEMORY.md` 참조.

---

## §4. 정직한 공백 — 지금 하지 않는 것 (7종)

1. **학교/교육청/학원 관리자 좌석** — 조직 엔티티 자체가 0(D4)이라 관리자 종류를 나눌 대상이
   없다. `CONTENT_ADMIN`(D1)이 유일한 비-학생 역할로 남는다.
2. **AI 기능 세분화 권한** — `POST /v1/generate`는 인증만 요구한다(`app.py:679`). "AI 기능
   사용 권한"을 별도로 쪼갤 소비처(예: 유료 티어별 AI 기능 제한)가 결제 시스템 부재로 없다.
   `ADMIN-02`가 처리하는 `subscription_tier`가 착지하면 그때 재고려한다.
3. **2차원 RBAC 매트릭스의 코드화** — `pipa_data_matrix.md`는 설계 정본으로 실재하지만, 그
   표의 각 셀을 실제 인가 체크로 구현한 코드는 아직 없다(현재 소비 축인 콘텐츠 CUD는 역할
   단순 비교로 충분해 아직 매트릭스가 필요하지 않다). 교사·부모 축이 열릴 때(§5-②) 첫
   구현체가 필요해진다.
4. **조직·학교·반 테넌시** — D4로 페이퍼만(§5-③).
5. **좌석·사용률 대시보드** — 콘솔 자체가 없고(§4-①과 동일 이유), 좌석 개념도 없다.
6. **로그인/로그아웃·계정 생성 감사 기록** — §2-⑬에서 의도적 미채택으로 판정(선례 승계),
   `refresh_token_session`이 사실상 로그인 상태 추적을 대신한다.
7. **콘텐츠 CUD·데이터 수정 감사(변경 이력)** — D1이 역할 변경만 감사하고, 콘텐츠 쓰기
   자체의 감사는 범위 밖이다(§5-②). 현재는 CUD가 사실상 아무도 못 쓰는 상태(D1 이전)라
   감사할 실 트래픽도 없다.

---

## §5. 유보 항목의 발화 조건 (실측 가능한 트리거)

| # | 유보 항목 | 발화 트리거 |
|---|---|---|
| ① | 관리자 HTTP API(`/v1/admin/*`)·콘솔 UI·`SYSTEM_ADMIN` 역할 | D1 착지 + **`CONTENT_ADMIN` 좌석이 실제로 1명 이상 발급**되고 CLI 조작 빈도(주 N회 이상)가 실측될 때 — `04_admin_console_architecture.md` §8이 그 시점의 정본 |
| ② | 콘텐츠 CUD 감사(`content_write`)·2차원 RBAC 매트릭스 코드화 | `CONTENT_ADMIN` 좌석 실발급 + 콘솔 Phase B(본인 아닌 주체의 쓰기가 실제로 발생) — `account_security_gap_review.md` §5-③과 동형 |
| ③ | 조직·학교·반 테넌시(D4) | **B2B 계약 1건 체결**(Phase 4) — `account_security_gap_review.md` §4-⑧·`ROADMAP.md:134` 승계, 재판정 아님 |
| ④ | 감사 보존 연한 확정·자동 파기 배선 | `MGMT-02` 변호사 회신 **+** 감사 행수가 실제로 증가 추세일 때(둘 중 하나만으로는 숫자를 정할 근거가 없다) |
| ⑤ | 라이선스·좌석·엔타이틀먼트 관리 | 결제 시스템 착지(Phase 1.5~2) — 그 전엔 `subscription_tier` 등 소비처가 없다(`ROADMAP.md:119`) |
| ⑥ | 관리자 MFA·IP 허용목록·중요작업 재인증 | `account_security_gap_review.md` §5-① 승계(관리자 계정 실발급 시 동시 발화) — **재판정하지 않는다** |

---

## §6. 반복 실수 — 7·8회차 등재

기존 시리즈 누적 6회차(만들고 CI 배선 안 함 → 적재 안 함 → 배포에 안 넣음 → 입력을 안 이음 →
안 켬 → 공급원을 안 이음)를 이어받는다.

| 회차 | 사례 | 형태 |
|---|---|---|
| 1 | `tests/infra` 199건이 어떤 잡도 실행하지 않음(OPS-03) | 만들고 **CI에 배선 안 함** |
| 2 | 전 시각화 스택 학생 도달 0회(VIZ-01) | 만들고 **적재 안 함** |
| 3 | OCR 전 파이프라인이 배포 경로 양쪽에서 비활성(NLP-01) | 만들고 **배포에 넣지 않음** |
| 4 | `POST /v1/me/attempts` 클라 호출 0회(REC-01) | 만들고 **입력을 잇지 않음** |
| 5 | 개인화 가중 기본 off · 개념 추천 API 6종 클라 소비 0(REC-01) | 만들고 **켜지 않음** |
| 6 | `select_probe` 후보 공급원 0(REC-02) | 만들고 **공급원을 잇지 않음** |
| **7** | `require_content_admin` 게이트에 **통과 주체를 만들지 않음**(D1) | 만들고 **인가 통로를 잇지 않음** |
| **8** | `school_id`·`subscription_*` 컬럼을 만들고 **소비처를 붙이지 않음**(D2) | 만들고 **스키마를 읽지 않음** |

7회차는 기존 6회와 형태가 다르다: 앞선 6회는 전부 *공급/입력* 축이 끊긴 사례인데, 7회차는
**인가(authorization)** 축이 끊겼다. 그리고 인가 단절은 앞선 6회의 "0건"·"비활성" 신호와
달리, **정상 봉인과 똑같은 상태코드(403)를 낸다** — 관측만으로는 구분되지 않는 새로운
하위유형이다.

---

## §정정 — stale 정본 4곳 (이번 대조에서 실측으로 발견 — 이후 2곳은 병합 시점에 이미 해소)

| 위치 | 이 세션 착수 시(2026-08-03 이전) 기술 | 실측·현황 |
|---|---|---|
| `docs/design/ui/04_admin_console_architecture.md` §2 원칙 3 | "**현재 상태(실측)**: `db/models/user.py`의 `UserProfile`에 role 필드가 **없다**. `Role` enum·`require_role`은 … **설계만** 존재. 콘텐츠 CRUD는 무인증" | **이미 정정 완료** — 병렬 세션 `99dfc3a`(2026-08-02, "관리 콘솔 UI: 모듈 자동 등록 설계 신설 + RBAC 서술 현행화")가 이 원문 자체를 SEC-07 반영 문구로 직접 고쳤다. 이 문서가 그 fork 시점 이전 스냅샷을 근거로 stale로 지목했으나, `main` 병합(본 커밋) 시점에는 원본이 **이미 최신**이다 — 후속 세션의 조치 불필요 |
| 동 문서 §8 backlog 제안 | "**ADMIN-RBAC** — `Role` enum + `UserProfile.role`(Alembic) + `require_role` + 콘텐츠 CRUD 인가 부착. (선결·최우선)" | 상동(`99dfc3a`) — `~~ADMIN-RBAC~~`로 취소선 처리 + "v0(2값) 완료" 각주로 이미 갱신됨. **ADMIN-MODULE-REGISTRY**(모듈 레지스트리·`GET /v1/admin/menu`)가 §8에 신규 항목으로 추가됐으나 backlog에는 아직 미등재(grep 확인) — 본 문서 D1과 겹치지 않는 축(메뉴 자동화 vs 좌석 발급)이라 중복 등재 위험 없음 |
| `docs/design/ui/03_admin_console_plan.md` §2 관리 자원 인벤토리·§7 | "`api/concepts.py`·`api/problems.py`(CRUD 존재·**무인증** ⚠️)" / "선결 과제 = RBAC. 현재 role 필드가 없고 무인증이다" | **이미 정정 완료**(상동 `99dfc3a`) — "RBAC v0 착지 완료·관리 콘솔 자체는 미소비"로 갱신됨. 이 문서 D1("부여 경로 0건이라 사실상 아무도 못 쓴다")이 그 갱신문이 놓친 정확한 지점을 메운다 — **상호 보완, 재정정 불필요** |
| `docs/architecture/account_security_gap_review.md` §4-⑦ | "**Admin BFF·콘솔 UI·역할 관리 화면** — `04_admin_console_architecture.md` §8 ADMIN-BFF·ADMIN-WEB 승계" | 이 파일은 병합 diff에 포함되지 않아 **fork 시점 그대로**. 방향은 유효하나, **CLI 경로(D1)가 화면보다 먼저** 필요함을 부기 — 운영자가 1명도 없는 상태에서 화면부터 만드는 것은 순서 오류. 유일하게 **아직 미해소** — 후속 세션이 이 표를 근거로 1줄 정정 |

4곳 모두 착수 시점엔 **"실제보다 덜 됐다"는 방향의 stale**이었다(앞선 시리즈 NLP·REC 편과
같은 패턴). 그러나 이 세션이 진행되는 동안 **병렬 세션이 앞의 2곳을 이미 고쳤다** —
`99dfc3a`는 이 문서와 무관하게 독립적으로 착수돼 같은 stale을 다른 방향(원본 직접 수정)으로
해소했다. 두 접근(본 문서의 "고치지 않고 표에 기록" vs `99dfc3a`의 "직접 고침")이 같은
대상에 동시에 작동한 사례로, 원본을 실제로 고치는 세션이 이긴다 — 이 §정정 표는 그 경합을
숨기지 않고 **"우리가 찾았을 때는 stale이었으나 병합 시점엔 이미 남이 고쳤다"**로 갱신해
다음 세션이 헛수고하지 않게 한다(§6의 반복 실수 패턴과 다른 축: 여기서는 *중복 발견*이지
*미도달*이 아니다).

**정정 원칙**: `.md` 1줄 단위로만 정정한다. 이번 세션은 이 문서 자체로 정정을 기록하며, 원본
파일의 직접 편집은 최소화한다(코드 로직 변경 0의 연장). 유일하게 남은 `account_security_
gap_review.md` §4-⑦은 후속 세션이 이 표를 근거로 고친다.

---

## 부록 — 실측 근거 (2026-08-03 확인)

**§0-①-2 (D1 근거)**
- `.role =` 대입·`role=Role.CONTENT_ADMIN` 생성 kwarg — `src/`·`scripts/` 전수 grep 무일치
- `api/auth.py:146-159` `resolve_user` — `UserProfile(...)` 생성 kwargs에 `role` 없음(`server_
  default='student'`만 적용)
- `api/_auth.py:96-123` `require_role`/`require_content_admin`/`RequireContentAdmin`
- `api/concepts.py:244/342/391`·`api/problems.py:57/184/231` — `RequireContentAdmin` 부착 6곳

**D2(dead 컬럼) 근거**
- `db/models/user.py:93` `school_id: Mapped[uuid.UUID | None]` — FK 없음
- `db/models/user.py:142-146` `subscription_tier`/`subscription_started_at`/
  `subscription_renewed_at`
- 4컬럼 읽기 grep: `src/` 전수에서 `schema/user.py`(Pydantic 필드 선언)·
  `alembic/versions/20260528_2223_…`(컬럼 생성) 외 소비처 0
- `account_security_gap_review.md:421` §4-⑧ 선행 자인

**D3(보존 정책) 근거**
- `privacy/retention.py:46-56` `_RETENTION_PLAN` — `Dialogue`·`ProblemAttempt`·
  `LearningSession`·`AttemptEvent`·`Assessment`·`ConceptMasteryHistory`·
  `SkillMasteryHistory`·`AbilitySnapshot`·`DailyLearningMetrics`·`UserBehaviorMetrics` 10개
  모델뿐 — `DeletionAudit`·`PrivacyAudit` 없음
- `privacy/erasure.py:21-23` `_ERASURE_PLAN` — 삭제권 맥락에서 `DeletionAudit`은 오히려
  **의도적으로 잔존**(계정 삭제 후에도 감사 남김) 시키므로 D3과 방향이 다름을 확인(삭제권의
  "잔존"과 보존기한의 "무기한"은 다른 질문 — 혼동 주의)

**§1 기능86~90 crosswalk 근거**
- `schema/enums.py:1163-1194` `Role`(2값) · `:1109-1113` `SubscriptionTier`(3값) ·
  `:1114-1138` `AuditEventKind`(3값)
- `db/models/user.py:90-93` `school_type`/`school_region`/`school_id`/`grade`
- `app.py:679` `POST /v1/generate` — `CurrentUser` 의존성(역할 불문)
- `ops/cost_report.py`·`ops/cost_probe.py` — HTTP 라우터 미등록(별도 CLI/스크립트 전용)
- `docs/architecture/db_backup_dr_runbook.md`·`docs/architecture/deployment_cd_runbook.md`·
  `docs/standards/incident_response_slo.md` — 백업·배포·장애는 DB 감사 테이블이 아니라 운영
  런북·형상관리가 기록을 대신함

**등재 검증**
- `python3 scripts/harness/backlog.py validate` — 실행 결과는 `MEMORY.md` 결정 로그에 기록
- `backlog/events.ndjson` — CLI `add` 3건 append 확인

---

## §독립 검증 (2026-08-04 — 별도 세션 교차 확인)

> **왜 이 절이 있나**: 2026-08-04 세션이 Kiki로부터 **같은 외부 문서**(『21. 운영 플랫폼』
> 86~90)를 받아 독립 착수했다가, 조사 단계에서 이 문서(당시 PR #663 · 미머지, 이후
> `b31ded26`으로 main에 스쿼시 머지됨)의 존재를 발견해 **작성 전에 중단**하고 재작성 대신
> **교차 검증**으로 전환했다(폐기 0줄). 아래는 그 세션이
> 이 문서를 열어보기 전에 독립 경로(Explore 3건 병렬 — 권한·감사 실태 / 문서·백로그 관례 /
> 개인정보·보안 — + 직접 grep 재검증)로 얻은 결과다.
>
> **성격은 append다** — §0~§정정은 **한 글자도 고치지 않았다**. 판정을 덮어쓰지 않고 검증
> 결과만 덧붙인다. r2 리비전 파일을 새로 만들지 않은 이유: r2 관례(`operations_module_gap_
> review_r2.md` §0)는 *이미 머지된 정본*이 **완료 태스크**의 판정 근거일 때 소급 변조를 막으려는
> 것인데, 이 문서는 미머지이고 참조 태스크 3건이 전부 `todo`다.

### ① 재현 확인 — CONFIRMED 3건

독립 경로에서 같은 결론에 도달했다. 판정의 근거가 한 세션의 관측에만 의존하지 않는다.

| 대상 | 독립 재현 결과 |
|---|---|
| **D1** — `CONTENT_ADMIN` 부여 경로 0건 | `\.role\s*=` 대입·`role=Role.CONTENT_ADMIN` kwarg **저장소 전수 0건** 재현. `CONTENT_ADMIN` 히트는 전부 enum 정의(`schema/enums.py:1194`)·게이트(`api/_auth.py:123`)·라우터 docstring뿐 — **부여하는 코드가 아니라 요구하는 코드만 있다**. `AuditEventKind`에 `role_change` 없음 재현. `admin_access`는 자체 docstring이 "현재 호출부 0곳"을 자인(`enums.py:1135~1141`) → **D1 유효** |
| **D3** — 감사 2테이블 무기한 보존 | `DeletionAudit`·`PrivacyAudit`이 `_RETENTION_PLAN`(`privacy/retention.py:46`)·`_ERASURE_PLAN`(`privacy/erasure.py:83`) 어디에도 없음 재현. `erasure.py`에 등장하는 `DeletionAudit`(`:56,198`)은 **삭제 계획이 아니라 writer**(삭제 전 1행 적재)라는 §부록의 구분도 재확인. SEC-12(done)가 배선한 `docker-compose.prod.yml:143-166` 사이드카는 *학습 활동 시계열* 파기라 별개 축임도 재현 → **D3 유효** |
| **D2 中 `school_id`** | FK 없는 고아 컬럼. 소비처는 스키마 미러(`schema/user.py:145`)·테스트(`test_no_lockout_columns.py:52`·`test_user.py:161,195`)뿐, 런타임 읽기·쓰기 0 재현 → **드롭 후보 타당**. 더해 **D4가 `organization`이 school을 흡수하는 설계**라 이 컬럼은 테넌시 착지 시에도 재사용되지 않는다 — 드롭의 재도입 비용이 0이라는 근거가 D4에서 나온다 |

### ② 정정 — **D2 스코프 분할**: `subscription_*`는 dead 컬럼이 아니라 **예약 좌석**

D2는 `school_id`와 `subscription_*` 3컬럼을 **같은 부류("소비처 0 = dead")로 묶어 함께 드롭**
대상으로 삼는다. `school_id`에 대해서는 위 ①대로 타당하나, `subscription_*`에 대해서는
**반증 3건**이 있다.

| # | 반증 | 위치 |
|---|---|---|
| 1 | 코드가 **명명된 미래 소비처를 스스로 선언**한다 — "결제 도입 결정 전까지는 오늘과 똑같은 값을 반환한다 … 실 `subscription_tier`/`budget_krw` DB 읽기·결제 연동은 **이 함수의 내부만** 바뀌면 된다" | `l3/escalation_defaults.py:12,40` |
| 2 | **`OPS-18`(done, 2026-08-03)** — 같은 시리즈 `service_operations_gap_review.md` D3의 산출물 — 의 acceptance ④가 *"범위 밖 동결: DB `subscription_tier` 읽기·결제·`budget_krw` 실배정 … **결제 도입 결정 이후**(§5-①)"*로 **명시적 유예를 이미 판정**했다 | `backlog/tasks/OPS-18-cloud-escalation-reach-observability.yaml` |
| 3 | 결제는 로드맵 Phase 2 M2.3로 **일정이 잡힌** 기능이다(미정 상태가 아니다) | `ROADMAP.md:119,153` |

§부록의 "4컬럼 읽기 grep … 소비처 0"은 **읽기(read)에 대해서는 정확하다** — 놓친 것은 read가
아니라 **docstring이 선언한 미래 소비처와 그것을 승인한 유예 판정**이다. 즉 이 3컬럼은
"만들고 안 읽는 dead 컬럼"(반복 실수 8회차)이 아니라 **유예 결정이 문서화된 예약 좌석**이다.

이 구분은 이 문서 자신의 기준과도 정합한다 — §2·§4는 `consecutive_active_days`류
"writer·reader 0인 좌석"을 **유지하되 채우지 않는다**고 판정해 왔다. `subscription_*`는 그보다
한 단계 더 강한 근거(명명된 소비처 + 완료 태스크의 유예 판정 + 로드맵 일정)를 갖는다.

**지금 드롭할 때의 실비용**: 마이그레이션 왕복 2회(드롭 → Phase 2 재생성) + 하루 전 완료된
OPS-18의 유예 판정과의 충돌 + `escalation_defaults`의 자기 서술이 stale이 된다.

**권고 — ADMIN-02 착수 시 스코프를 둘로 나눈다**

1. **`school_id`** → **드롭**(①의 근거 + D4가 재사용하지 않음).
2. **`subscription_tier`/`_started_at`/`_renewed_at`** → **드롭하지 않고 예약 좌석으로 명문화**:
   ⑴ 모델에 미사용 자인 주석 + `l3/escalation_defaults.py` 링크 ⑵ §5-⑤(결제 착지) 발화조건
   병기 ⑶ **동결 테스트** — "이 컬럼들은 아직 런타임 reader가 없다"를 단언해, 몰래 읽기가
   생기면(= 결제 없이 게이팅이 시작되면) 실패하게 한다.

이러면 "dead code 금지"(§2)와 "유예 판정 존중"(OPS-18·§5-⑤)을 동시에 만족하고, ADMIN-02가
지우려던 **오독("부분 구현된 것처럼 보임")도 그대로 해소**된다 — 오독의 해법은 컬럼 제거가
아니라 *왜 비어 있는지를 코드에 쓰는 것*이기 때문이다.

**이 정정을 태스크 YAML이 아니라 이 문서에 남기는 이유**: `backlog.py`에 기존 태스크의
`acceptance`·`notes`를 고치는 서브커맨드가 없다(실측 서브커맨드 전수: `status`·`next`·`start`·
`done`·`block`·`unblock`·`gates`·`add`·`validate`·`brief`·`check-stop`·`check-edit`·`claims`·
`overlap`·`policy`·`seed`). 대장 손편집은 금기(CLAUDE.md 프로세스 금기 ①)이고, ADMIN-02의
`notes`가 이미 `operations_platform_gap_review.md §3 D2`를 가리키므로 **착수 세션이 D2를 읽을
때 함께 읽는 위치**가 이 정정의 자연스러운 소유자다.

### ③ 관찰 — 태스크 판정 정정의 CLI 경로 부재 (**태스크 신설 없음**)

②에서 드러났듯, 완료 전 태스크의 판정이 바뀌었을 때 그것을 대장에 반영할 정규 경로가 없다.
이번에는 "문서가 소유자"라는 우회가 성립했으나, **문서 소유자가 없는 태스크**에서 같은 일이
생기면 손편집 유혹이 생긴다(HARN-06 선례 = CLI 경로 공백은 태스크로 등재).
**발화조건**: 문서 소유자가 없는 태스크의 판정 정정이 실제로 필요해질 때. 지금 등재하지 않는
이유는 실사례가 1건(그것도 우회 성립)뿐이라 설계 근거가 얇기 때문이다.

### ④ 이 문서가 중복 착수를 유발한 경위 — 하네스 3겹 사각

같은 외부 틀을 받은 두 세션이 서로를 못 봤다. 원인은 사람의 부주의가 아니라 **구조**다.

1. **설계 문서 세션은 backlog 태스크를 claim하지 않는다** — 태스크는 이런 세션의 *산출물*이지
   입력이 아니다. 그래서 claim 대장에 뜰 방법이 원천적으로 없다(구조적 사각).
2. **`refs/claims/*` push가 CCR 프록시 403으로 상시 실패**(2026-07-27 등재·fail-open) —
   claim이 있었어도 못 봤다. 2026-08-04 세션의 `git ls-remote origin 'refs/claims/*'`도 빈 결과.
3. **SessionStart 브리핑의 "장기 미머지 브랜치"는 4일 이상만 나열** — 이 브랜치는 착수 시점에
   1일 경과라 목록에 **없었다**. 실제로 2026-08-04 세션의 브리핑 2회(최초·resume) 모두
   `claude/whymath-operations-platform-cn6dxi`를 보여주지 않았다.

이번엔 사람이 조사 중 우연히 원격 브랜치를 뒤져 **작성 전에** 잡았다(폐기 0줄). 2026-07-27
동일 유형 사고는 735줄 폐기로 끝났다 — 즉 이번 성공은 **장치가 아니라 운**이었다.
대책은 하네스 태스크로 등재한다(아래 ⑤).

### ⑤ 등재 — 중복 착수 탐지 (신규 `HARN-`)

| 태스크 | 내용 | stage | priority |
|---|---|---|---|
| `HARN-14-doc-series-duplicate-detection` | 원격 **미머지 브랜치가 추가한 갭 리뷰 문서**를 SessionStart 브리핑에 노출 — ④의 3겹 사각 중 3번을 닫는다(1·2는 각각 구조적·HARN-07 소유) | S4 | 2 |

**선행 태스크와의 관계**: `HARN-13`(done, "장기 미병합 브랜치 기계 감지")이 만든 것이 ④-3의
그 목록이다. HARN-13은 브랜치를 **나이(4일 이상)로** 거르는데, **설계 문서 중복은 착수 당일이
가장 위험**해 그 임계 아래로 전부 새어나간다 — HARN-14는 HARN-13의 대체가 아니라 **나이 임계가
만든 사각의 보완**이다(대상도 브랜치가 아니라 *브랜치가 추가한 문서*).

**번호 주의**: 이 태스크는 `HARN-12`가 아니다 — `backlog.py add`가 `HARN-12`를 기존
`HARN-12-brief-unmerged-done-filter`와의 충돌로 거부하고 다음 빈 번호를 제안했다(HARN-10 규칙:
번호는 추론하지 않고 CLI가 배정한다).

핵심 설계 제약 2가지:
- **네트워크 실패를 "0건"으로 위장 금지** — 스캔 실패는 실패로 표시한다(측정 도구의 이중 회계
  원칙·CLAUDE.md AI·신뢰 금기).
- **변별력 필수** — 미머지 상태에서 탐지되고 머지 후 사라지는 **양방향 실측**. 성공/실패 양쪽에
  같은 값을 내는 검사는 검증이 아니라 위장이다(2026-07-17 `delay:true` 선례).

### ⑥ PR 상태 (병합 순서)

이 문서의 본체는 **PR #663**(`claude/whymath-operations-platform-cn6dxi`)에 있었다. 2026-08-04
세션은 그 커밋을 **재작성 없이 흡수**한 뒤 이 §독립 검증만 얹었다. **#663은 이후 Kiki 요청으로
스쿼시 머지됐다**(`b31ded26`, main) — 이 절은 그 위에 별도 PR로 뒤따라 들어간다(경쟁 PR
아님·중복 등재 0건).
