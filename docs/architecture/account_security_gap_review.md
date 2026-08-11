# 계정·보안(Account & Security) 모듈 — 외부 EOS 틀 대조 갭 점검·설계 (2026-07-30)

> ⚠️ **후속판 있음 — `account_security_gap_review_r2.md`(2026-08-11)**. 이 v1 문서는 `SEC-07`~`SEC-12`
> 완료 태스크의 판정 근거이므로 **본문을 수정하지 않는다**. v1 이후 바뀐 판정(stale 4칸)·v1이 판정하지
> 않은 칸 12종·잔여 갭 D8~D12는 전부 r2에 있다.

> **범위**: 외부 참고 문서 『계정·보안』(0단계 모듈 46~48: 계정 관리 · 개인정보 보호 · 보안 —
> + 확장 후보 49~53: RBAC 관리·조직 관리·기기 관리·감사 로그·보안 정책 중앙관리. **WhyMath
> 전용이 아닌 일반적 EOS 틀**, Kiki 제공)을 현 코드베이스와 대조해 빠진 부분을 점검하고, 진짜
> 갭을 WhyMath 불변식(의사결정 우선순위 1 학생 웰빙 ≫ 2 법적 준수 ≫ … 7 개발 속도 · dead code
> 금지 · 이중 진실원천 금지 · 법령 유래 절차의 기계 대체 금지 · 미성년자 보호) 안에서 설계한 기록.
> **형식**: `knowledge_module_gap_review.md`(모듈 6~10, 07-27) · `problem_bank_gap_review.md`
> (기능 18~22, 07-28) · `solution_module_gap_review.md`(기능 23~27, 07-29) ·
> `ai_tutor_module_gap_review.md`(기능 37~41, 07-29) 답습 — **5번째 자매편**.
> **대전제 2가지**: ① 이 영역은 자매편 4편과 달리 **"약한 곳"이 아니라 낙차가 가장 큰 곳**이다 —
> 봉투 암호화·삭제권·리프레시 회전은 외부 문서보다 *엄격*한데, 콘텐츠 쓰기 표면은 **인증
> 자체가 없다**. ② 그 낙차는 우연이 아니라 **구축 순서의 그림자**다 — 학생 1인칭 경로(`/v1/me/*`)는
> 처음부터 미성년 보호 요구를 받아 조여졌고, 운영자 경로는 *운영자 좌석이 없어서* 아무도 조이지
> 않았다. 즉 갭의 형태는 "보안을 안 했다"가 아니라 **"학생용 보안만 했다"**다.
> **결론**: 모듈 47(개인정보 보호)은 **문서보다 엄격**(18테이블 원자 삭제·이동권·3자산 fail-closed
> 암호화). 모듈 46(계정)·48(보안)은 **학생 축 충족·운영 축 공백**. 최대 갭은 기능 목록에 없는
> 곳에 있다 — **`/v1/concepts`·`/v1/problems` CUD 완전 무인증**(DELETE 포함). 진짜 갭 7건을
> 설계(D1~D7, D7은 페이퍼)하고 실행 6건 + 사람 게이트 1건을 백로그에 등재했다. 의도적 미채택
> 10건 · 정직한 공백 9종 · 유보 발화조건 9건. 정본 2곳(`security_privacy.md` ·
> `ROADMAP.md`)을 개정한다.

관련 정본: `docs/standards/security_privacy.md`(보안·개인정보 표준 — 이번 개정 대상) ·
`docs/legal/pipa_data_matrix.md`(PIPA 데이터 매트릭스·역할×항목 2차원 정본) ·
`docs/design/ui/04_admin_console_architecture.md` §2 원칙 3~4(ADMIN-RBAC·감사 로그 정본) ·
`docs/design/ui/03_admin_console_plan.md` §데이터 관리 · `docs/standards/dev_constitution.md` §9
(로깅 규칙)·부록(산문→자동검사 상태) · `CLAUDE.md` 절대 금기(보안·데이터·AI·신뢰) ·
`MEMORY.md` 결정 로그(SEC-01~06 · 2026-07-30).

---

## §0. 전제 — 실측 현황 스냅샷 (2026-07-30 기준)

**이미 가동 중이고 외부 문서보다 엄격한 것**:
- **at-rest 봉투 암호화 3자산 + fail-closed 게이트**: 대화 본문·손글씨 이미지·증거 payload를
  AES-256-GCM 봉투로 저장(SEC-01). `api/_crypto.py:285` `require_dialogue_content_cipher`는
  **프로덕션 추정 환경에서 키가 없으면 부팅을 거부**한다 — 평문 폴백이 "조용히" 금기를 위반하는
  경로를 사람 기억이 아니라 게이트로 막았다(docstring: "체크리스트는 사람이 기억해야 작동하지만,
  이 게이트는 잊어도 작동한다").
- **미성년 동의 게이트**: `api/_auth.py:60` `get_consented_user` — *알려진* 미성년자
  (`is_minor=True`)인데 `parent_consent_at`이 없으면 403. `is_minor`가 None(미상)이면 차단하지
  않는 설계도 명시적(추정으로 학습을 막지 않음).
- **리프레시 회전 + 재사용 탐지 패닉 취소**: `api/auth.py:237` `/refresh`가 매번 회전하고, 이미
  취소된 토큰 재제출 시 `_revoke_all_user_sessions`(`:186`)로 **사용자 전체 세션을 패닉 취소**
  (`:260`). 탈취 대응이 외부 문서에 없는 수준까지 들어가 있다.
- **삭제권**: `privacy/erasure.py:83` `_ERASURE_PLAN` **18테이블을 단일 트랜잭션**으로 child→parent
  순서 삭제(`api/me.py` `DELETE /v1/me`). 삭제 감사 1행 동일 TX 적재(`api/me.py:291`) + 본인 조회
  (`GET /v1/me/deletions`·`:457`).
- **이동권**: `privacy/export.py` + `GET /v1/me/export`(`api/me.py:2071`) — 구조화 JSON 반출.
- **rate limit 인프라**: `api/_rate_limit.py` **1,261줄** — Redis ZSET·원자 Lua·3주체 키
  (`user`/`ip`/`device`·`hit_by_ip:135`·`hit_both:146`)·카테고리 버킷 분리·fail-safe. **인프라는
  이미 있다**(D2는 신설이 아니라 호출).
- **보존 파기 로직**: `privacy/retention.py`(순수·`retention_cutoff`·`purge_expired_records`) +
  `privacy/retention_purge_cli.py`(evidence + PII 시계열 단일 TX·테이블별 행수 JSON).

**정직 자인이 이미 코드에 있는 곳**(신뢰의 근거):
- `security_privacy.md:72` — 세션 목록/관리(`GET·DELETE /v1/auth/sessions`)는 "후속(a3d)"이라고
  자백. `:74` — "로그인 IP 레이트리밋은 후속(OAuth-a4)"이라고 자백.
- `security_privacy.md:65-66` — 실 카카오/네이버 provider 계약은 "문서 기반 인코딩 — 라이브
  크레덴셜로만 통합 검증 가능(로컬/CI 미검증)"이라고 별표까지 붙여 자백.
- `security_privacy.md:79-81` — 모바일 code 획득은 "미구현 seam"이라 **로그인은 아직 작동하지
  않는다**고 자백(`oauth_code_requester.dart` `UnsupportedOAuthCodeRequester`).
- `retention_purge_cli.py:8` — "둘 다 *실행 진입점*이 없어 retention이 집행되지 않았다"고 자백
  (CLI가 그 표면). **CLI는 생겼고, CLI를 부르는 스케줄은 아직 없다**.
- `api/me.py` 삭제 경로 — PG 밖 store(ClickHouse 등)는 `pending_external`로 **별도 삭제 필요**를
  로그로 남긴다(조용히 넘기지 않음).
- `schema/enums.py:1122-1126` — `ConsentScope`가 `service_core` 1값인 이유를 "**변호사 자문으로
  범위·문구가 확정된 뒤** 추가한다(지금 추측으로 박지 않는다 — 가짜 동의 범위를 만들지 않는다)"고
  명시.

**실측으로 확인한 공백**(grep·라인 실측):
- `api/concepts.py:231`(POST)·`:330`(PATCH)·`:379`(DELETE) · `api/problems.py:44`(POST)·`:172`
  (PATCH)·`:219`(DELETE) — **인증 의존성 0건**. 두 파일이 import하는 의존성은 `SessionDep`·
  `EmbeddingProviderDep`뿐이고 `CurrentUser`·`get_current_user`는 **등장하지 않는다**.
  `app.py:660` `/v1/generate`도 무인증(LLM 비용 표면).
- `UserProfile.role` 컬럼·`Role` enum **0** — `db/models/`의 `role`은 `dialogue.py:166`
  (`TurnRole`)·`concept.py:258`(`ConceptRole`)뿐으로 **둘 다 다른 축**. `Role`+`require_role`은
  `.claude/agents/backend-engineer.md:248-262`에 **설계만** 존재.
- `get_current_user`(`api/_auth.py:41`)가 `is_active`·`is_deleted`(`db/models/user.py:162-163`)를
  **미검사** → 비활성·탈퇴 계정의 미만료 토큰이 통과.
- `/v1/auth/*` rate limit **0** — `api/auth.py`에 `_rate_limit` import 0(rate limit 소비처는
  `coach`·`study`·`devices`·`scene`·`visualization`뿐).
- OAuth `state`·PKCE **0** — `fetch_identity(code, redirect_uri)`(`api/oauth_providers.py:42/105`)
  가 계약 전부. CSRF 방어·`redirect_uri` allowlist 없음.
- 반출 **무기록** — `DeletionAudit` writer는 `api/me.py:291`(삭제 경로) 1곳뿐. `/export`(`:2071`)는
  감사 0행.
- 로그 PII 스크러버 **0** — `logging.Filter`·`addFilter` grep **0건**.
- 익명화 **0** — `anonymi*`·`익명화`·`pseudonym` grep 0건(소비처도 0).
- 스케줄러 배선 **0** — `retention_purge_cli`를 호출하는 cron·Celery beat·CronJob 정의 grep 0
  (MEMORY 결정 로그도 "Celery-beat 자동 스케줄(현 cron/ops 수동)"을 NOT으로 명시).
- 조직 테이블 **0** — `user.py:92`에 `school_id: uuid|None` 컬럼만 있고 `school` 모델은 없다
  (`db/models/` 39개 중 부재).

**낙차의 형태**: 학생 1인칭 경로는 미성년 보호 요구가 처음부터 붙어 조여졌고(암호화·동의 게이트·
삭제권·본인 스코핑), 운영자 경로는 **운영자 좌석 자체가 없어서** 인가를 붙일 대상이 없었다. 그
결과 "학생 데이터는 암호화되는데 그 데이터가 붙은 문제는 누구나 지울 수 있다"는 비대칭이 남았다.

---

## §1. 모듈 46~48 + 후보 49~53 ↔ WhyMath crosswalk 판정

### 모듈 46. 계정 관리 — **학생 축 부분 충족 / 역할·세션 가시성 공백**

| 문서 항목 | WhyMath 현행 | 판정 |
|---|---|---|
| 통합 계정 체계 | `UserProfile` 1종(학생) + 계정계 8테이블(device·refresh·consent·track/persona/state 이력) | ⚠️ 학생만 — 역할 좌석 0 → **D1** |
| 가입: 이메일·휴대폰 | 없음 — **비밀번호를 만들지 않는다**(SSO 전용·`passlib[bcrypt]` 선언만·사용 0) | 🚫 §2-③ |
| 가입: 카카오·네이버 | 서버 구현(`api/oauth_providers.py:25-147`) / **클라 code 획득 스텁**(`oauth_code_requester.dart`) | ⚠️ 라이브 미검증 → §4-② |
| 가입: Google·Apple·MS | 없음 | §4-② |
| 로그인: SSO·자동로그인·기기기억 | JWT + `token_store.dart`(OS 보안저장소) + `restore()` | ✅ (부분) |
| 로그인: QR 로그인 | 없음 | 🚫 §2-④ |
| 인증: OTP·2FA·Passkey | 없음 | 🚫 §2-⑤ / Passkey는 ⏸ §5-⑦ |
| 인증: 관리자 MFA | 관리자 좌석 0 | ⏸ §5-① |
| 권한: 7단 선형 서열 | `role` 컬럼·enum **0** | 🚫 §2-① (**서열 모델 자체 반증**) + **D1** |
| 세션: 기기 목록 | 없음(`security_privacy.md:72` 자백) | ⚠️ → **D4** |
| 세션: 원격 로그아웃·전체 로그아웃 | `_revoke_all_user_sessions:186` **함수만 존재·엔드포인트 0** | ⚠️ → **D4**(소생) |
| 세션: 동시 로그인 제한 | 없음 | 🚫 §2-⑥ |
| 계정 복구: 비밀번호 찾기 | **구조적 무해당**(비밀번호 부재) | 🚫 §2-③ |
| 계정 복구: 휴면 계정 | `is_active` 컬럼 + retention 단일권위 | 🚫 §2-⑧ |
| 계정 삭제 | `DELETE /v1/me` + 18테이블 원자 삭제 + 감사 | ✅ (문서보다 엄격) |

### 모듈 47. 개인정보 보호 — **대부분 충족(문서보다 엄격) / 동의 범위·감사가 갭**

| 문서 항목 | WhyMath 현행 | 판정 |
|---|---|---|
| 동의: 이용약관·개인정보처리방침 | 문안 0 · `consent_version`/`terms_version` grep 0 | ⚠️ → **D7**(페이퍼) + `MGMT-02` |
| 동의: 마케팅·AI 활용·학습데이터 | `ConsentScope` = `service_core` **1값**(`enums.py:1130`) | ⚠️ → **D7** |
| 동의: 버전 관리·철회 | 철회 필드 실재 / 버전 스탬프 0 | ⚠️ → **D7** |
| 미성년: 보호자 동의 | `parental_consent` + 403 게이트 **실효** | ✅ |
| 미성년: 본인 인증 | `StubGuardianVerifier` — **의도적 stub**(가짜 법적 의사표시 회피) | ⏸ `MGMT-01` blocked |
| 미성년: 동의 철회 | 필드만·경로 미완 | ⚠️ D7 동반 |
| 개인정보: 조회·수정 | `/v1/me/*` 29 엔드포인트(본인 스코핑) | ✅ |
| 개인정보: 다운로드 | `GET /v1/me/export` | ✅ |
| 개인정보: 삭제 | `DELETE /v1/me`(18테이블 원자) | ✅ (엄격) |
| 개인정보: 익명화 | grep 0 (**소비처도 0**) | §4-⑤ |
| 보존: 기간·자동 삭제 | 로직+CLI 실재 / **정기 실행 배선 0** | ⚠️ → **D6** |
| 감사: 삭제 | `deletion_audit` append-only + 본인 조회 | ✅ |
| 감사: 조회·수정·**다운로드**·관리자 | **반출 무기록** · 관리자 좌석 0 | ⚠️ → **D3** |

### 모듈 48. 보안 — **암호화 축 초과충족 / 인증 표면·로그·전송 축 공백**

| 문서 항목 | WhyMath 현행 | 판정 |
|---|---|---|
| 암호화: 저장(at rest) | AES-256-GCM 봉투 3자산 + **fail-closed 부팅 게이트** | ✅ (엄격) |
| 암호화: 전송(in transit) | 리포에 TLS 종단 좌석 **0**(`docker-compose.prod.yml`에 nginx/caddy 없음) | §4-① |
| 암호화: KMS/HSM·pgcrypto·TDE | 단일 마스터 키 봉투(`_crypto.py` 자백) | §4-③ |
| 접근통제: RBAC 4단(사용자→역할→권한→리소스) | 본인 스코핑(`WHERE user_id`)만 · 역할 0 | ⚠️ → **D1** |
| 접근통제: 최소권한·데이터 마스킹 | 프롬프트 계층 원문 격리는 실재 / 운영 마스킹 0 | ⚠️ D3·§4-⑦ |
| API 보안: JWT | `security.py` 발급·검증·Bearer 의존성 | ✅ |
| API 보안: OAuth2 | 서버 구현 실재 / **`state`·PKCE·`redirect_uri` allowlist 0** | ⚠️ → **D2** |
| API 보안: Rate Limit | 1,261줄 인프라 실재 / **`/v1/auth/*` 부착 0** | ⚠️ → **D2** |
| API 보안: IP 제한 | 0 | 🚫 §2-⑨(학생) / ⏸ §5-①(관리자) |
| 보안 감사: 로그인 실패 추적 | 0 | ⚠️ 부분 → **D2**(rate limit로 대체) |
| 보안 감사: 비정상 IP·SQLi·XSS·Bot 탐지 | 자동 탐지 0 | 🚫 §2-⑩ / ⏸ §5-⑥ |
| 로그: PII 평문 금지 | **규정만 3곳**(`CLAUDE.md`·`dev_constitution.md:144-146`·`security_privacy.md:142`)·구현 0 | ⚠️ → **D5** |
| 관리자 보안: MFA·IP 허용목록·재인증·계정 잠금 | 관리자 좌석 0 | ⏸ §5-① |

### 확장 후보 49~53

| 후보 | WhyMath 현행 | 판정 |
|---|---|---|
| 49 RBAC 관리(역할·권한 CRUD) | 좌석 0 | **D1**(v0 2값·관리 UI는 §4-⑦) |
| 50 조직 관리(학교·학원·반) | `user.py:92` `school_id` 컬럼만 · `school` 테이블 없음 | §4-⑧ (Phase 4 B2B) |
| 51 기기 관리 | `device_credential` 실재(폐기·idle 자동정리) — **단 세션 ≠ 기기** | ✅ + 경계 명시 **D4** |
| 52 감사 로그 | 삭제만 실재 | **D3** |
| 53 보안 정책 중앙관리 | `config.py` env 단일원천 | 🚫 §2-⑦ |

**후보 51의 경계가 이 문서의 숨은 발견**: `device_credential`은 **rate limit 신뢰용 기기 자격
증명**이고 로그인 세션이 아니다. 기기를 폐기해도 그 기기가 들고 있는 **JWT는 만료까지 유효**하다.
문서의 "기기 관리 = 원격 로그아웃"을 이 테이블로 충족했다고 읽으면 **보안 착시**가 생긴다. D4가
세션 축을 따로 세우고, 문서에 경계를 못 박는다.

---

## §2. 의도적 미채택 (10건)

| # | 문서 제안 | 불채택 근거 |
|---|---|---|
| ① | **7단 선형 Role 서열**(학생↓교사↓학부모↓학원↓학교↓운영↓Super Admin) | **모델 자체가 우리 데이터와 모순**이다. `docs/legal/pipa_data_matrix.md:33-47`에서 **부모 열은 학생 열의 상위가 아니라 부분집합**이다 — 오답 패턴 ✕·또래 비교 ✕·힌트 사용 ✕(부모에게 미공개인 항목이 학생 본인에겐 ● 공개). 선형 서열은 "상위가 하위를 포함"을 전제하므로 채택하면 미성년 보호 매트릭스를 **구조적으로** 깬다. → **2차원(역할 × 데이터 항목)** 매트릭스만 채택(`04_admin_console_architecture.md` §2 원칙 3-4 정본 승계) |
| ② | 계정 상태 5종(활성·휴면·정지·탈퇴대기·삭제) 상태기계 | `is_active`·`is_deleted` 2불리언 + retention이 현 규모를 덮는다. "정지"는 관리자 좌석이 서기 전엔 집행 주체가 없고, "탈퇴대기 grace period"는 **즉시 원자 삭제가 이미 더 엄격**(유예 보관이 오히려 데이터 최소화 역행) |
| ③ | 이메일/비밀번호 로그인 + 비밀번호 찾기 | 비밀번호를 *만들지 않는 것*이 미성년 보안상 우월 — 자격증명 유출·재사용·피싱 표면을 **원천 제거**. 따라서 "비밀번호 찾기"는 구현 누락이 아니라 **구조적 무해당**. `passlib[bcrypt]` 선언(사용 0)은 **의존성 제거** 대상(D1 동반) |
| ④ | QR 코드 로그인 | 패드+폰 한 코드가 정상 형태이고 두 기기 모두 SSO가 닿는다. 공용 PC 시나리오(QR의 주 용도)는 타깃 밖 |
| ⑤ | OTP·SMS 2FA | 휴대폰 번호를 **애초에 수집하지 않는다**(PII 최소화). 2FA를 위해 미성년자 전화번호를 새로 걷는 것은 우선순위 2를 우선순위 6에 팔는 거래 |
| ⑥ | 동시 로그인 개수 제한 | 패드+폰 동시 사용이 정상 형태(CLAUDE.md 스택: "패드+폰 한 코드"). 제한은 학습 중단을 만든다 |
| ⑦ | 보안 정책 중앙관리(런타임 정책 편집 UI) | `config.py` env가 **단일 진실원천**이고 부팅 시 검증된다. 런타임 오버라이드를 열면 "설정이 두 곳"이 된다(이중 진실원천 금지). 운영 가시화는 `04_admin_console_architecture.md` §5 승계 |
| ⑧ | 로그인 실패 반복 → **계정 잠금(lockout)** | 미성년 학생이 자기 계정에서 락아웃되면 **학습 중단 = 우선순위 1(학생 웰빙) 침해**. 그리고 SSO 전용이라 "우리 쪽 실패"는 provider 왕복 실패뿐이다. 잠금 대신 **rate limit + 지연**(D2) |
| ⑨ | 학생 트래픽 IP 화이트리스트·지역 차단 | 학생은 이동한다(학교·집·독서실·테더링). IP 고정 가정은 오탐으로 학습을 막는다. 관리자 축은 별도(§5-①) |
| ⑩ | SQLi·XSS·Bot 자동 탐지 | ORM 전용·원시 SQL 최소화·렌더 계약(표현≠의미)으로 **구조적 방어**. 공격 트래픽 0인 파일럿 규모에서 탐지기는 "측정 없는 도입" + 경고 습관화(fail-open 소음) 리스크가 더 크다. WAF는 §5-⑥ |

---

## §3. 설계 D1~D7

**실행 순서**: **D1 → D2 → D3 → D5 → D4 → D6**, D7은 페이퍼. D1이 최우선인 이유는 심각도가
아니라 **되돌릴 수 없음**이다 — 무인증 DELETE는 데이터를 지운다(다른 갭은 기록이 없거나 방어가
얇을 뿐). D3·D4는 D1의 `require_role`이 서야 "관리자 접근 감사"·"세션 소유자 판정"의 대상이
정의된다.

### D1. 무인증 쓰기 표면 봉인 + Role v0 (백로그 `SEC-07`, priority 1)

**문제**: `api/concepts.py:231/330/379`·`api/problems.py:44/172/219`의 POST/PATCH/**DELETE**에
인증 의존성 0건 → 누구나 개념·문제를 생성·수정·**삭제**할 수 있다. `app.py:660` `/v1/generate`
무인증 = LLM 비용 남용 표면. 더해 `get_current_user`(`api/_auth.py:41`)가 `is_active`/`is_deleted`
를 **미검사** → 탈퇴·비활성 계정의 미만료 토큰이 통과한다.

**정본 승계(새 설계 아님)**: `docs/design/ui/04_admin_console_architecture.md` §2 원칙 3
(ADMIN-RBAC)·§8이 이미 정본이며 **"등재는 `backlog.py` 경유"라고 스스로 지시**한다. 실측 결과
백로그에 `ADMIN-RBAC` 등재는 **0건**(grep) — D1은 새 설계가 아니라 그 정본의 **등재 + 범위 축소
확정**이다.

**Role v0 = 2값 확정(축소)**: `STUDENT`(기본) · `CONTENT_ADMIN`. 정본 §2 원칙 3은 5종 골격 +
`CONTENT_ADMIN`을 제안하지만, **좌석 없는 역할은 만들지 않는다**(dead code 금지) —
`PARENT`/`TEACHER`/`SCHOOL_ADMIN`은 소비처(Phase 3 대시보드 계약)가 실체를 가질 때 열고(§5-②),
`SYSTEM_ADMIN`은 `CONTENT_ADMIN`과 구분할 권한 항목이 아직 없다. **역할 추가는 마이그레이션
1줄**이고, 잘못 만든 역할을 걷어내는 비용이 더 크다.

**정합 설계**
- `Role` enum(`schema/enums.py`) + `UserProfile.role` 컬럼(Alembic·`server_default='student'`).
- `require_role(*roles)`를 `api/_auth.py`에 신설 — 기존 `get_current_user` **위에 얹는다**
  (재계산 0·`.claude/agents/backend-engineer.md:248-262` 골격 승계).
- `get_current_user`에 `is_active`/`is_deleted` 검사 추가(401) — **기존 컬럼의 첫 reader**.
- CUD 6개 라우터 + `/v1/generate`에 부착. 읽기(GET)는 **무인증 유지**(공개 카탈로그·현 클라·데모
  경로 파괴 금지).
- `passlib[bcrypt]` 의존성 제거(§2-③).

**dead code 금지 충족**: 신규 테이블 0(컬럼 1개). enum 2값 전부 소비처 실재(STUDENT=기본 발급,
CONTENT_ADMIN=CUD 인가). **7단 서열 미도입을 테스트로 동결**해 미래 세션이 "빠진 것"으로 오인해
되살리지 않게 한다.

**acceptance 후보**
1. CUD 6라우터 + `/v1/generate`에 인가 부착 + **무인증 호출이 401/403**임을 회귀 테스트로 동결
   (GET 무인증 유지도 함께 동결 — 봉인 범위 과확대 방지).
2. `is_active=False`·`is_deleted=True` 토큰 401 동결.
3. `Role` enum **2값**·마이그레이션 기본값 `STUDENT`·**서열 비교 연산 부재**(선형 서열 미도입)를
   테스트로 동결 + `passlib` 제거 후 전체 스위트 green.

**의존**: 없음(즉시 착수). **D3·D4의 선결**. **태스크**: 신설.

### D2. 인증 표면 남용 방어 + OAuth 하드닝 (백로그 `SEC-08`, priority 1)

**문제**: `/v1/auth/*`(callback·refresh·logout) rate limit **0**(`security_privacy.md:74` 자백) →
provider 왕복 폭주·리프레시 무한 재시도. OAuth `state` **0** → **CSRF**(공격자 code 주입),
`redirect_uri` allowlist **0** → **open redirect**. 액세스 TTL 24h(스펙 15분)에 취소 수단 0.

**재계산 0**: 기존 `api/_rate_limit.py`의 `hit_by_ip`(`:135`)·`hit_both`(`:146`)를 **호출만** 한다
— 미인증 표면이라 IP 키가 정확히 그 용도이고, 이미 구현되어 있다.

**액세스 TTL 단축은 D2 범위 밖**: 15분으로 줄이면 클라 refresh-on-401 배선이 없어 **학생이 15분
마다 튕긴다**(우선순위 1 침해). MOB 축 선결 → §5-⑧에 발화조건.

**계정 잠금 대신 rate limit**: §2-⑧ 근거를 **코드 주석 + 테스트**로 남긴다 — 잠금 부재가
"빠뜨림"이 아니라 결정임을 미래 세션이 알 수 있게.

**acceptance 후보**
1. `/v1/auth/{provider}/callback`·`/refresh`에 IP 키 rate limit 부착 + 429 회귀 + Redis 부재 시
   fail-safe 거동 유지(기존 계약).
2. `state` 발급·검증(불일치 400) + `redirect_uri` allowlist(미등록 400) + 클라 계약 갱신 필요분
   문서화.
3. lockout **미도입**을 결정으로 명시(주석 + "잠금 상태 컬럼 부재" 동결 테스트).

**의존**: 없음(D1과 병행 가능). **태스크**: 신설.

### D3. 개인정보 감사 — 반출·동의 변경·관리자 접근 (백로그 `SEC-09`, priority 2)

**문제**: `security_privacy.md:88-100`이 "모든 PII 접근 로그"를 규정했는데 구현은 삭제 1종뿐이고,
**가장 감사가 필요한 반출**(`GET /v1/me/export`·`api/me.py:2071` — 데이터가 시스템 밖으로 나가는
유일한 경로)이 **무기록**이다.

**핵심 판단(경계 확정 — 규정을 그대로 구현하지 않는다)**: 본인 조회 29개 엔드포인트 전수 감사는
**하지 않는다**. 미성년 학생의 **학습 조회 이력 자체가 프로파일링 자산**이 되어(언제·무엇을 몇 번
봤는가) 미성년자 보호 원칙과 역행하고, 볼륨도 소음이다. 감사 대상은 **⑴ 데이터 반출 ⑵ 동의 변경
⑶ 관리자 접근** 3종 = **"시스템 밖으로 나가는 사건"과 "본인 아닌 주체의 접근"**만. → 정본
`security_privacy.md:88-100`을 이 경계로 **정정**한다(규정을 남겨두면 영구 미달 상태가 된다).

**이중 진실원천 회피**: 삭제 감사는 `deletion_audit`(`db/models/audit.py:32`) **단일 권위 유지** —
신규 테이블에 삭제를 **중복 기록하지 않는다**. `deletion_audit`를 확장해 쓰지 않는 이유도 명시적
이다: 테이블명·`deleted_at` 컬럼이 삭제 의미에 결합되어 있어 반출 사건을 넣으면 스키마가 거짓말을
한다. 두 테이블 통합은 §5-③ 발화조건.

**미성년 PII 경계**
- IP는 **평문 미저장** — `sha256(salt+ip)` 해시만(같은 IP 반복 판정은 되고 원본 복원은 불가).
  정본 `security_privacy.md:97`의 `ip_address` 평문 필드는 이 형태로 정정한다.
- 기존 `deletion_audit` 패턴 답습: append-only(UPDATE/DELETE 라우터 없음) · `user_id` **FK 아님**
  (계정 삭제 후에도 감사 잔존) · **콘텐츠 미저장**(메타만).
- 반출 감사는 **반출 내용을 저장하지 않는다**(무엇을 내보냈는지 = 학습 데이터 전체 → 감사가
  사본이 되면 최소화 위반).

**acceptance 후보**
1. `/v1/me/export`·동의 변경이 감사 1행 적재(동일 TX) + 실 PG 통합 + 본인 조회 경로 감사 0행
   (경계 동결).
2. 본문·PII 값 미저장 + **IP 평문 0**을 테스트로 assert.
3. `deletion_audit` 중복 기록 0 회귀(삭제 시 신규 테이블 미적재).

**의존**: D1(관리자 접근 축은 `require_role` 후행). 반출·동의 2종은 선행 가능. **태스크**: 신설.

### D4. 세션 가시성·전체 로그아웃 (백로그 `SEC-10`, priority 3)

**문제**: `_revoke_all_user_sessions`(`api/auth.py:186`)는 **이미 존재하는데** 재사용 탐지 경로
(`:260`)에서만 호출된다 — **함수는 있고 엔드포인트가 없다**(소생 대상). 세션 목록 API 0
(`security_privacy.md:72` "후속(a3d)" 자백). 학생이 기기를 분실하면 **자기 세션을 끊을 방법이
없다**.

**정합 설계**
- `GET /v1/auth/sessions`(내 활성 세션 목록) · `DELETE /v1/auth/sessions`(전체 — 기존 함수 호출) ·
  `DELETE /v1/auth/sessions/{jti}`(단건). `refresh_token_session` 테이블이 이미 allowlist라
  **신규 테이블 0**.
- **최소 수집**: 세션 행에 IP·UA 원본을 넣지 않고 **플랫폼 요약**(예 `iPad`·`Android`)만.
  목록의 목적은 "낯선 기기 인지"이고 그 이상은 미성년 PII 확대다.
- **경계 명시**: `device_credential`(rate limit 신뢰용) **≠** 로그인 세션 — 기기 폐기가 JWT를
  무효화하지 않음을 문서·docstring에 못 박는다(§1 후보 51의 보안 착시 차단).
- 액세스 토큰은 여전히 만료까지 유효하다는 **한계를 정직 표기**(전체 로그아웃 = 리프레시 취소).
  진짜 즉시 무효화는 TTL 단축(§5-⑧) 또는 denylist 축.

**acceptance 후보**
1. 3 엔드포인트 + 본인 스코핑(타인 jti 404) + `_revoke_all_user_sessions` 재사용(중복 구현 0).
2. 응답에 IP·UA 원문 0 + 플랫폼 요약만을 테스트로 동결.
3. "기기 폐기 ≠ 세션 취소"·"액세스 토큰은 만료까지 유효" 한계를 응답/문서에 명시 + 회귀.

**의존**: D1(본인 판정은 기존 `CurrentUser`로 충분하나 D1의 `is_active` 검사와 함께 착지 권장).
**태스크**: 신설.

### D5. 로그 PII·시크릿 스크러버 (백로그 `SEC-11`, priority 2)

**문제**: 저장 축은 fail-closed 게이트로 닫았는데(`_crypto.py:285`) **로깅 축은 사람 기억에
의존**한다 — `CLAUDE.md` 절대 금기·`dev_constitution.md:144-146`·`security_privacy.md:142`가
**3곳에서 규정**하는데 `logging.Filter`·`addFilter` 구현은 **0건**. 이 **비대칭 자체가 갭**이다:
같은 조직이 같은 위험을 한쪽은 게이트로, 한쪽은 훈화로 다룬다.

**정합 설계**
- `logging.Filter` 1개(`api/` 또는 `ops/`) + 루트 로거 배선(`create_app`·logconfig).
- 마스킹 대상: 학생 발화·풀이 원문 후보 필드 · `sk-`/`pk-`류 시크릿 패턴 · Bearer 토큰 ·
  이메일 · 전화 형식. **예외 타입명은 마스킹하지 않는다**(CLAUDE.md "무타입 경고 금지"와 충돌
  방지 — 스크러버가 관측성을 죽이면 8일 무증상 전멸의 재발 경로가 된다).
- **변별력 테스트 필수**(CLAUDE.md "변별력 없는 검증 스텝 금지"): 학생 원문·시크릿을 로거에
  흘리는 케이스에서 **마스킹을 끄면 테스트가 실패**해야 한다. 성공/실패 양쪽에서 같은 값을 내는
  검사는 위장이다.
- 동반: 시크릿 하드코딩 저장소 스캔 테스트(`dev_constitution.md:193`이 "코드 테스트화는 남은
  선택지"라고 자백한 항목의 **상환**).

**acceptance 후보**
1. 필터가 루트 로거에 실제 배선(**"존재함 ≠ 돌아감"** — 배선 실재성을 테스트로 동결,
   `tests/infra/test_test_suite_wiring.py` 선례).
2. **변별력 쌍**: 마스킹 해제 시 실패하는 테스트 + 예외 타입명 보존 회귀.
3. 시크릿 하드코딩 스캔 테스트 + 기존 로그 호출부 회귀(성능·포맷 무변경).

**의존**: 없음(즉시 착수 가능). **태스크**: 신설.

### D6. 보존 파기 정기 실행 배선 (백로그 `SEC-12`, priority 3)

**문제**: `privacy/retention.py`·`retention_purge_cli.py`는 **완비**되어 있고 CLI docstring이
"둘 다 실행 진입점이 없어 retention이 집행되지 않았다 — 이 CLI가 그 표면이다"라고 쓰여 있다.
그런데 **그 CLI를 부르는 스케줄이 없다**(cron·Celery beat·CronJob grep 0). 즉 보존 정책은
**집행되지 않는 상태**다. `device_credential_max_idle_days`(`config.py:632`)의 "운영은 Celery
beat·cron으로 일일 호출 권장"도 같은 상태다.

이것은 이 저장소에서 **반복된 부류**다 — CLAUDE.md 금기 "검증 장치를 만들고 배선 확인 없이 완료
선언 금지"(`tests/infra` 199건 미실행·브랜치 보호 미강제·OPS-03/08/10/11 선례). **"저장소에
존재함"과 "돌아감"은 다르다.**

**정합 설계**
- 스케줄 진입점 **1개**(Celery beat 또는 compose 기반 cron — 배포 형태에 종속되므로 착수 시
  `docker-compose.prod.yml` 실측 후 확정). 신규 로직 0 — **CLI 호출만**.
- **배선 실재성을 테스트로 동결**(`tests/infra/test_test_suite_wiring.py` 선례 답습) — 스케줄
  정의가 사라지면 테스트가 깨진다.
- **"0건 통과" vs "측정 실패" 구분**(CLAUDE.md 이중 회계 금기): 파기 0건과 실행 실패가 같은
  출력을 내면 안 된다. CLI가 이미 `{as_of, purged{table:n}, total}`를 내므로 **실행 자체가 실패한
  경우의 신호**를 스케줄 레이어에서 분리한다.
- 함께 배선 검토: `cleanup_stale_devices`(같은 "권장만 있고 스케줄 없음" 상태).

**acceptance 후보**
1. 스케줄 진입점 1개 배선 + `retention_purge_cli` 호출 경로 확인.
2. 배선 실재성 테스트(정의 삭제 시 실패).
3. dry-run 실행 증거 + **파기 0건과 실행 실패가 구분되는 출력** 동결.

**의존**: 없음. 배포 형태(OPS-03) 확정 시 배선 위치가 바뀔 수 있어 priority 3. **태스크**: 신설.

### D7. 동의 버전 원장 (**페이퍼 — 코드 0 · 태스크 신설 없음**) + `MGMT-02`(owner=kiki)

**문제**: `ConsentScope`가 `service_core` **1값**(`enums.py:1130`)이고 `consent_version`·
`terms_version` grep **0**. CLAUDE.md 금기 "학생 풀이 데이터를 **명시적 동의 없이** 학습에 사용
금지"를 **집행할 좌석이 없다** — 지금은 "학습 활용 동의"라는 개념이 스키마에 존재하지 않는다.

**왜 지금 기계장치를 만들지 않는가**: 동의 *문안*은 **법률 판단**이다(`enums.py:1122-1126`가
"변호사 자문으로 범위·문구가 확정된 뒤 추가한다 — 지금 추측으로 박지 않는다"고 이미 자백).
버전 스탬프는 문안 없이는 **writer 없는 dead 컬럼**이 되고, 더 나쁘게는 **가짜 법적 의사표시**
(내용 없는 동의 v1)를 만든다. `StubGuardianVerifier`·`MGMT-01`이 같은 이유로 stub인 것과 동형 —
CLAUDE.md "법령 유래 절차의 기계 대체 금지"의 직접 적용이다.

**등재하는 것**: `MGMT-02` = 이용약관·개인정보처리방침 **문안 확정(변호사 검토)** ·
`owner: kiki` · `status: blocked` · unblock 트리거 = **공개 β 준비 착수**(2026-07-27 Kiki의 외부
작업 일괄 연기 결정 승계). 기계장치 태스크(scope 확장·버전 스탬프·철회 경로)는 문안 회신 **후**
신설(§5-④) — 순서를 뒤집으면 dead 컬럼이 먼저 생긴다.

**런칭 차단 가시성(실측 지적)**: `MGMT-01`·`MGMT-02` 둘 다 태스크 대장에만 있고
`backlog/gates.yaml`에는 **법무 게이트가 0건**이다(실측 — 게이트 7건 전부 기술·시연 축).
공개 β를 법적으로 막는 두 항목이 "게이트"로 보이지 않는다. 다만 **지금 `gates.yaml`을 손편집하지
않는다** — `gates` 서브커맨드에 `add`가 없어 CLI 경로가 없고(설계 공백), CLAUDE.md "거부의 우회
금지"·HARN-06 선례에 따라 게이트 승격은 공개 β 결정 시점에 CLI 경로와 함께 처리한다(§5-⑤).

---

## §4. 정직한 공백 — 지금 하지 않는 것 (9종)

1. **TLS 종단·리버스 프록시·HSTS/CSP/보안헤더·CORS** — 리포에 좌석 0(`docker-compose.prod.yml`에
   nginx/caddy/traefik 없음). 현 클라는 **네이티브 앱이라 브라우저 origin이 없어** CORS는 *현재*
   불요. OPS-03(배포 IaC)·웹 콘솔 착지 시 발화(§5-①과 동반).
2. **Google·Apple·MS 로그인** — 카카오/네이버조차 클라 code 획득이 스텁이라 **실 로그인 0개
   작동**(`security_privacy.md:79-81` 자백). provider를 늘리는 건 순서 오류 — 먼저 1개를 라이브로
   작동시킨다(OAuth-c3·MOB 축).
3. **KMS/HSM·per-secret DEK·pgcrypto·TDE** — 단일 마스터 키 봉투로 현 규모 충분(`_crypto.py`
   자백). 키 관리 계층은 프로덕션 인프라 확정 후.
4. **프로필 PII 암호화**(`nickname`·`birth_year`·`school_*`) — 커리큘럼 정렬·진단의 **쿼리 입력**
   이라 암호화하면 조회가 불가능해진다. 실명·전화는 **애초 미수집**으로 이미 축소됨(문서의 PII
   분리 저장 3테이블 설계가 폐기된 이유).
5. **익명화 파이프라인** — 학습데이터 활용 동의 자체가 없어(D7) **소비처가 0**이다. 동의 없이
   익명화 자산을 만들면 그 자산의 용처가 곧 위반이 된다.
6. **ISMS-P·개인정보 영향평가(PIA)** — `pipa_data_matrix.md` §4.2 승계(Phase 2~3 판정). 인증은
   조직·프로세스 자산이고 코드 축이 아니다.
7. **Admin BFF·콘솔 UI·역할 관리 화면** — `04_admin_console_architecture.md` §8 ADMIN-BFF·
   ADMIN-WEB 승계(**중복 등재 금지**). D1은 그 정본의 선결분(RBAC)만 떼어 등재한다.
   **[2026-08-11 부기 — 순서 정정]** 방향은 유효하나 **CLI 경로가 화면보다 먼저**다. 운영자가
   1명도 없는 상태(`CONTENT_ADMIN` 부여 경로 main 0건)에서 화면부터 만드는 것은 순서 오류이며,
   좌석 발급은 `ops/role_grant_cli.py`(HTTP 미노출) 축으로 이미 설계·구현돼 회수 대기 중이다 —
   `operations_platform_gap_review.md` §3 D1·§정정, `operations_platform_gap_review_r2.md`
   §4 D5(`ADMIN-08`).
8. **조직(학교·학원·반)·멀티테넌시** — `school_id` 컬럼만 있고 `school` 테이블 없음. Phase 4
   B2B 계약이 실체를 가질 때(후보 50).
9. **클라 refresh-on-401 배선·액세스 TTL 15분·PII 접근 전수 감사** — 각각 MOB 축(§5-⑧)·
   D3 경계 밖(미성년 프로파일링 회피)·§5-③.

## §5. 유보 항목의 발화 조건 (실측 가능한 트리거)

| # | 유보 항목 | 발화 트리거 |
|---|---|---|
| ① | 관리자 MFA·IP 허용목록·중요작업 재인증·관리자 계정 잠금 + TLS/보안헤더 | 관리자 계정이 **실제 발급**될 때(D1 착지 + 콘솔 Phase B) — 관리자 표면이 브라우저로 열리는 순간 §4-①이 동시 발화 |
| ② | `PARENT`·`TEACHER`·`SCHOOL_ADMIN` 역할 | Phase 3 대시보드/B2B 계약이 **실체를 가질 때**. 추가 시 반드시 `pipa_data_matrix.md` 2차원 매트릭스로만(선형 서열 금지·§2-①) |
| ③ | `deletion_audit` ↔ 감사 테이블 통합 · PII 접근 전수 감사 | 관리자 콘솔 Phase B(관리자 접근이 실제 발생) + 감사 조회 UI가 두 테이블을 조인해야 할 때 |
| ④ | 동의 scope 확장·버전 스탬프·철회 경로 기계장치 | `MGMT-02` 문안 회신 **+** 해당 처리(학습 활용·마케팅)를 실제 개시할 때 — 둘 중 하나만으로는 dead 컬럼 |
| ⑤ | 법무 게이트(`gates.yaml`) 승격 | **공개 β 결정** 시점 + `gates add` CLI 경로 확보(HARN 축) |
| ⑥ | WAF·공격 탐지·비정상 IP 판정 | 공개 β **+ 공격 트래픽 실관측**(로그 기반). 관측 없이 켜면 오탐이 학생을 막는다 |
| ⑦ | Passkey·WebAuthn | 소셜 IdP가 보급되지 않은 시장 진입(Phase 5 글로벌) 또는 provider 장애가 실관측될 때 |
| ⑧ | 액세스 TTL 15분 + 토큰 denylist | 클라 refresh-on-401 배선 완료(MOB) — **선행 없이 단축하면 학생이 15분마다 튕긴다** |
| ⑨ | 프로필 PII 일반화(`birth_year`→연령대 버킷 등) | 코호트 N 확대로 준식별자 재식별 위험이 실측될 때 |

---

## 부록 — 실측 근거 (2026-07-30 확인)

- `api/concepts.py:231/330/379` · `api/problems.py:44/172/219` — CUD 6라우터. 두 파일의 의존성은
  `SessionDep`·`EmbeddingProviderDep`뿐이고 `CurrentUser`·`get_current_user`·`require_role`
  **참조 0**(grep). `app.py:660` `/v1/generate` 동일.
- `api/_auth.py:41` `get_current_user` — `is_active`/`is_deleted` 검사 부재(본문 전문 확인).
  `db/models/user.py:162-163`에 두 컬럼 실재. `:60` `get_consented_user` 403 게이트 실효.
- `db/models/` 전 39모델에서 `UserProfile.role` 부재 — `role` 컬럼은 `dialogue.py:166`
  (`TurnRole`)·`concept.py:258`(`ConceptRole`) 2건이며 **둘 다 다른 축**.
  `.claude/agents/backend-engineer.md:248-262`에 `Role` 5종 + `require_role` **설계만**.
- `api/auth.py` — 라우터 3개(`:198` callback·`:232` refresh·`:275` logout).
  `_revoke_all_user_sessions:186`의 유일 호출처는 `:260`(재사용 탐지). `_rate_limit` import **0**.
- `api/oauth_providers.py:42/105` — `fetch_identity(code, redirect_uri)`가 계약 전부.
  `state`·PKCE·`code_verifier`·allowlist **grep 0**.
- `api/_rate_limit.py` 1,261줄 — `hit_by_ip:135`·`hit_both:146`·`SubjectKind:102`(user/ip/device)
  실재. 소비처는 `coach`·`study`·`devices`·`scene`·`visualization`(auth 부재).
- `api/_crypto.py:285` `require_dialogue_content_cipher` — prod 추정 시 키 없으면 RuntimeError
  (fail-closed) + `is_production_like` 단일 좌석 위임.
- `privacy/erasure.py:83` `_ERASURE_PLAN` **18테이블**(child→parent 순서·주석에 CASCADE 역순 방지
  명시) + `ExternalErasureTarget`(PG 밖 store는 별도 ops 삭제·`api/me.py`가 `pending_external`
  로그).
- `api/me.py:291` `DeletionAudit` writer(삭제 경로·동일 TX) · `:457` `GET /v1/me/deletions` ·
  `:2071` `GET /export`(**감사 0행**). `@router.` 총 29개(본인 스코핑).
- `db/models/audit.py:32` `deletion_audit` — append-only·`user_id` FK 아님·`resource_type`
  `String(32)`(네이티브 enum 미생성)·`deleted_at` 컬럼(삭제 의미 결합).
- `schema/enums.py:1095` `AuditResourceType` · `:1115` `ConsentScope` · `:1130` `service_core`
  **단일 값** · `:1122-1126` 변호사 자문 전 미추가 결정 원문.
- `privacy/retention.py`(90줄·순수) · `privacy/retention_purge_cli.py:8` "실행 진입점이 없어
  retention이 집행되지 않았다" 자백. **CLI를 호출하는 스케줄 정의 grep 0**(cron·Celery beat·
  CronJob). `config.py:632` `device_credential_max_idle_days` — "Celery beat·cron 권장" 상태.
- `logging.Filter`·`addFilter` — `src/` 전체 **grep 0**. `anonymi*`·`익명화`·`pseudonym` 도 0.
- `docker-compose.prod.yml` — nginx·caddy·traefik·TLS 정의 **0**.
- `docs/legal/pipa_data_matrix.md:33-47` — 9항목 × (학생/교사/부모) 매트릭스. 부모가 ✕인 항목
  3개(오답 패턴·또래 비교·힌트 사용)가 학생 본인은 ●/◐ → **부모 ⊂ 학생**(선형 서열 반증).
- `docs/design/ui/04_admin_console_architecture.md:32-40` 원칙 3~4 · `:163` ADMIN-RBAC 제안.
  **`backlog/`에 `ADMIN-RBAC`·`ADMIN-BFF` 등재 grep 0**(미등재 확인).
- `backlog/gates.yaml` — 게이트 7건 전부 기술·시연 축. **법무·동의 게이트 0건**.
- `docs/standards/security_privacy.md:14-35`(폐기된 PII 3테이블 설계)·`:52-58`(부모/교사 가입 —
  좌석 0)·`:72`(a3d 자백)·`:74`(rate limit 자백)·`:88-100`(감사 규정)·`:142`(로그 PII 금지).
- `docs/standards/dev_constitution.md:144-146`(로그에 시크릿·개인정보 미기록)·`:193`(시크릿 형식
  자가검증 "코드 테스트화는 남은 선택지" 자백).
- `src/backend/pyproject.toml:40` `passlib[bcrypt]>=1.7.4` — `src/` 코드 사용 **0건**
  (`_device_store.py:21`은 docstring 언급).
- `src/mobile/lib/features/auth/data/oauth_code_requester.dart` —
  `UnsupportedOAuthCodeRequester.requestCode`가 예외 발생(OAuth-c3 미구현 seam).
- `ROADMAP.md` 281줄 — 보안·계정·개인정보·인증·RBAC 키워드 **0건**(유일 매치는 `:48` "Mathpix API
  계정"으로 이 축 무관).
