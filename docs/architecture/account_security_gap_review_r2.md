# 계정·보안(Account & Security) 모듈 — 외부 EOS 틀 대조 **2차 재점검(r2)** (2026-08-11)

> **범위**: 외부 참고 문서 『11. 계정·보안』(0단계 모듈 46 회원가입·로그인·인증 · 47 개인정보·보호자
> 동의 · 48 보안 + 확장 후보 49~53 RBAC·조직·기기·감사·보안정책 — **WhyMath 전용이 아닌 일반 EOS
> 틀**, Kiki 재제출)을 현 코드베이스와 다시 대조한 기록.
> **성격**: **v1과 동일한 문서의 재제출**이다(`account_security_gap_review.md`, 2026-07-30). 처음부터
> 재대조하면 v1의 판정 근거가 유실되고 중복 작업이 되므로 **델타 재점검**으로 전환했다 —
> `operations_module_gap_review_r2.md`(08-03) · `gamification_module_gap_review_r2.md`(08-04) 선례.
> **v1 이후 상태**: v1 설계 D1~D7 중 D1~D6이 `SEC-07`~`SEC-12`로 **전건 착지**했고, D7은 페이퍼로
> 남아 `MGMT-02`(owner=kiki·blocked)가 대리한다. v1이 지목한 최대 갭(콘텐츠 CUD 무인증)은 해소됐다.
> **결론 3줄**:
> 1. **최대 갭 = 미성년 동의에 "끝"이 없다** — `get_consented_user`(`api/_auth.py:81`)는
>    `parent_consent_at` 하나만 읽고, `ParentalConsent.expires_at`·`revoked_at`
>    (`db/models/parental_consent.py:75-76`)은 **writer가 상수 `None`뿐이고 reader 0**이다.
>    철회 엔드포인트도 없다. 정본 `security_privacy.md:11`이 "매 분기 재확인"을 규정하는데
>    집행 코드가 0이고, 그 줄에는 v1의 편집자 부기조차 붙지 않아 **미정정 stale 규정**으로 남았다.
>    한 번 받은 동의가 **영구히 유효**하다 — 의사결정 우선순위 2위(법적 준수·미성년자) 축. → **D9**
> 2. **두 번째 갭 = 계정에 "복구"가 없다** — 계정 식별 키가 `email_hash` 단일이고
>    (`api/auth.py:132/138`), provider의 안정 id `subject`는 **받아서 버린다**(`auth.py:102`,
>    `UserProfile`에 컬럼 0). 이메일 변경 경로도 0(`_SELF_EDITABLE`·`api/users.py:74`). 비밀번호를
>    만들지 않는 것은 v1의 옳은 결정이었지만(§2-③), 그 결정은 **이메일이 영구 불변이라는 가정** 위에
>    서 있었고 그 가정은 사실이 아니다. 소셜 계정 이메일이 바뀌면 학생은 새 계정을 받고 학습 이력을
>    영구히 잃는다. → **D8**
> 3. **v1 판정표 stale 4칸 정정 + v1이 판정하지 않은 칸 12종을 이번에 판정한다.** v1 crosswalk에는
>    외부 문서의 `이메일 변경`·`재동의 관리`·`로그인 이력 조회`·`법적 보존 예외` 등의 **행 자체가
>    없었다** — 위 갭 2건이 v1에서 안 보였던 이유는 판정이 틀려서가 아니라 **표에 칸이 없어서**다.

관련 정본: `docs/architecture/account_security_gap_review.md`(**v1 — 이 문서가 승계·정정하는 원본**) ·
`docs/standards/security_privacy.md`(보안·개인정보 표준) · `docs/legal/pipa_data_matrix.md`(역할×항목
2차원 정본) · `docs/architecture/operations_platform_gap_review.md` §3(ADMIN-01~03 소유) ·
`docs/design/ui/04_admin_console_architecture.md` §2 원칙 3~4 · `CLAUDE.md` 절대 금기(보안·데이터·
프로세스) · `MEMORY.md` 결정 로그(2026-07-30 v1 · 08-03 SEC-10/12 · 08-03 운영플랫폼).

---

## §0. 재점검 사유 — 왜 v1을 덮어쓰지 않고 r2를 새로 쓰는가

### ① 동일 문서 재제출임을 수치로 확정한다 (추론 아님)

첨부 문서의 항목을 v1 §1 crosswalk 표와 대조한 결과 **모듈 번호(46·47·48)·확장 후보 번호(49~53)·
항목 구성이 일치**한다. `MEMORY.md:2755`의 2026-07-30 결정 로그가 같은 문서를 "모듈 46 계정 관리·
47 개인정보 보호·48 보안 + 확장 후보 49~53 RBAC/조직/기기/감사/정책"으로 기록한다. 재제출이다.

### ② v1을 in-place 수정하지 않는 이유

v1은 `SEC-07`~`SEC-12` 6개 완료 태스크의 `notes`가 가리키는 **정본 참조 대상**이다. 본문을 고치면
완료 태스크의 판정 근거를 소급 변조하게 된다. v1에는 **r2 존재를 알리는 배너 1줄만** 추가하고
본문은 한 글자도 고치지 않는다(operations r2 선례).

### ③ 승계 선언 — 재판정하지 않는 것

- **v1 §2 의도적 미채택 10건** — 7단 선형 Role 서열 / 계정 상태 5종 상태기계 / 이메일·비밀번호
  로그인 + 비밀번호 찾기 / QR 로그인 / OTP·SMS 2FA / 동시 로그인 제한 / 보안 정책 런타임 편집 /
  계정 잠금 / 학생 IP 화이트리스트 / SQLi·XSS·Bot 자동 탐지. **전건 유지**. 재판정 트리거 실측:
  `Role` enum은 여전히 2값이고 `<`/`>` 비교가 `TypeError`로 동결돼 있다(`schema/enums.py:1228-1238`),
  계정 잠금 컬럼 부재도 `tests/backend/api/test_no_lockout_columns.py`가 동결 중, 공격 트래픽
  실관측은 없다. **미채택 근거가 하나도 무너지지 않았다.**
- **v1 §4 정직한 공백 9종** — TLS 종단·Google/Apple/MS 로그인·KMS/HSM·프로필 PII 암호화·익명화·
  ISMS-P·Admin BFF·조직 테넌시·TTL 15분. 전건 유지(단 §5-⑧ 발화조건은 §5에서 갱신).
- **v1 D7 페이퍼(동의 문안·scope·버전 스탬프)** — `MGMT-02` blocked 유지. 아래 D9는 **문안이 아니라
  집행 메커니즘**만 다루므로 D7과 충돌하지 않는다(경계는 D9 본문에 명시).

### ④ 병렬 세션 소유권 — 재설계 금지 대장

이 재점검의 **가장 큰 실측 발견은 갭이 아니라 소유권**이다. 원격 브랜치
`claude/whymath-issues-review-k20m0w`에 **`docs/reviews/functional_security_audit_2026-08-08.md`**
와 그 산출 태스크 6건이 있는데, **`origin/main`에는 그 파일들이 없다**.

| 태스크 | 내용 | 브랜치 상태 | main |
|---|---|---|---|
| `SEC-13` | `/v1/me/harness-metrics` 원시지표·`GAMING_SUSPECT` 학생 노출 → admin 게이트 | done | 파일 부재 |
| `SEC-14` | **X-Forwarded-For 무조건 신뢰 봉합 — `trusted_proxy_ip_allowlist` deny-by-default** | done | 파일 부재 |
| `SEC-15` | 무인증 정답·`/v1/jobs` 노출 봉합(`PublicProblem` 허용목록 투영) | done | 파일 부재 |
| `SEC-16` | `/outcome` 쓰기 소유권 바인딩(키드 해시) | done | 파일 부재 |
| `SEC-17` | OCR 업로드 크기·MIME 검증(413/415) | done | 파일 부재 |
| `SEC-18` | prod `/docs`·`/openapi.json` 비활성 + CORS 정책 동결 | **in_progress**(claim 중) | 파일 부재 |

추가로 `SEC-19-generate-rate-limit`이 `claude/whymath-ai-integration-check-5qqcp4`에,
`SEC-13-external-store-manifest-truthfulness`가 `claude/whymath-ai-recommendation-review-q8tvcx`에
있다 — 즉 **`SEC-` 번호대가 main 밖에서 4개 브랜치에 걸쳐 분기**해 있고, `SEC-13`은 두 브랜치가
서로 다른 태스크에 배정했다(§7).

`ADMIN-01`은 `claude/admin-01-operator-seat-grant-audit`에 **실물 757줄**(`ops/role_grant_cli.py`
231줄 + 테스트 526줄)이 `done`으로 있고, main의 같은 태스크는 `todo`다. `ADMIN-02`는
`claude/admin-02-dead-tenancy-billing-columns`에서 **`blocked`로 재판정**됐다("4컬럼 일괄 drop"이라는
main acceptance가 부정확하며 `school_id`만 drop 후보라는 결론).

**이 문서는 위 8건을 재설계하지 않는다.** 특히 `api/_rate_limit.py:938` `_client_ip`의 XFF 무검증
신뢰는 main에 **현존**하지만 `SEC-14`가 이미 소유하므로 등재하지 않는다. §6에 이 소유권 사고를
반복 실수로 등재한다.

---

## §1. v1 판정표 정정 — stale 칸만 (v1을 수정하지 않고 여기 기록)

| v1 위치 | v1 서술 | 2026-08-11 실측 | 정정 |
|---|---|---|---|
| §0·§3 D1(`:18`, `:201`) | "`/v1/concepts`·`/v1/problems` CUD 완전 무인증(DELETE 포함) — **최대 갭**" | `api/concepts.py:55,244,342,391`·`api/problems.py:32,57,184,231`이 `RequireContentAdmin` 실배선 | **해소**(SEC-07). v1의 최대 갭은 더 이상 최대 갭이 아니다 |
| §3 D6(`:350`) | "`retention_purge_cli.py:8`이 '실행 진입점이 없어 retention이 집행되지 않았다'고 자백 — 스케줄 grep 0" | `docker-compose.prod.yml:143-166`에 24h 셸 루프 배선(SEC-12 done) | **해소**. 단 **`retention_purge_cli.py:8` docstring 자체가 stale**(배선된 뒤에도 "진입점이 없다"고 말한다) → §4-① |
| §3 D7(`:396-398`)·§5-⑤ | "`gates` 서브커맨드에 `add`가 없어 CLI 경로가 없다(설계 공백) — 손편집하지 않는다" | `backlog.py gates add`가 **존재**한다 | **유보 근거 2개 중 1개 해소**. 잔여는 공개 β 결정뿐 → §5-⑤ 갱신. `gates.yaml` **법무 게이트 0건**은 여전히 사실(게이트 7건 전부 기술·시연·의사결정 축) |
| §3 D4(`:301`) | "학생이 기기를 분실하면 자기 세션을 끊을 방법이 없다" | `SEC-10`(서버 3라우트, 08-03) + **`MOB-12`**(`account_security_screen.dart`, 08-10) 2단계로 착지 | **해소**. 다만 SEC-10 `done` 시점에도 학생 체감은 미해소였고, 그 구간을 발견한 것은 갭 리뷰가 아니라 `ops/declared_unwired_audit.py`(OPS-22)다 → §6 |

**정정하지 않는 칸**: v1 §1의 나머지 판정은 실측상 유효하다. 특히 `device_credential ≠ 로그인 세션`
경계(v1 §1 후보 51의 "보안 착시" 지적)는 지금도 정확하며, `SEC-10`이 그 경계를 코드·문서에 못 박았다.

---

## §2. v1 crosswalk 미판정 칸 12종 — 이번에 판정한다

v1 §1의 4개 표는 촘촘했지만 **외부 문서의 일부 항목에 대해 행 자체를 만들지 않았다**. 갭 리뷰에서
"판정이 ⚠️인 칸"은 추적되지만 **"표에 없는 칸"은 아무도 추적하지 않는다** — 이 12종이 그 사각이다.

| # | 외부 문서 항목 | WhyMath 현행(실측) | 판정 |
|---|---|---|---|
| 1 | 46 사용자 유형 **연구자** | `Role` 2값(STUDENT·CONTENT_ADMIN) | 🚫 미채택 — 좌석 없는 역할 금지(v1 §2-① 승계). 연구 데이터 접근은 역할이 아니라 **익명화 자산** 축이고 그 자산은 동의가 없어 존재하지 않는다(v1 §4-⑤) |
| 2 | 46 세션 **로그인 이력 조회** | `GET /v1/auth/sessions`는 *활성 세션*만. 로그인 *이력* 0 | 🚫 미채택 — 이력은 "언제·어디서 로그인했나"의 시계열이고, **미성년 학생의 접속 시각 이력 자체가 프로파일링 자산**이 된다(v1 §3 D3이 본인 조회 전수 감사를 거부한 것과 동일 논리). 낯선 기기 인지 목적은 활성 세션 목록이 이미 충족 |
| 3 | 46 계정 복구 **이메일 변경** | 경로 0(`_SELF_EDITABLE`·`api/users.py:74`에 이메일 없음). 식별 키가 `email_hash` 단일 | ⚠️ **→ D8**. v1이 판정하지 않은 가장 비싼 칸 |
| 4 | 47 미성년 **재동의 관리** | `expires_at` 컬럼·인덱스는 있고 **reader 0**. 정본은 "매 분기 재확인" 규정 | ⚠️ **→ D9** |
| 5 | 47 미성년 **동의 철회**(v1은 "필드만·경로 미완"으로 D7에 동반) | `revoked_at` writer는 상수 `None` 1곳, reader 0, 철회 라우트 0 | ⚠️ **→ D9**. v1이 D7(페이퍼)에 묶어 **추적 태스크가 0건**이 된 항목 |
| 6 | 47 보존 **삭제 예정일** | `_RETENTION_PLAN`(`privacy/retention.py`)이 cutoff를 계산해 즉시 파기 — "예정일" 개념 없음 | 🚫 미채택 — 예정일을 저장하면 **파기 시점이 두 곳**(계획 + 행)이 되어 이중 진실원천. 즉시 파기가 데이터 최소화에 더 부합 |
| 7 | 47 보존 **법적 보존 예외** | `deletion_audit`·`privacy_audit`이 파기 계획에서 의도적 제외 = 사실상의 예외 | ⏸ 기존 추적 — **`ADMIN-03`이 소유**(명문화 + 동결, 연한 숫자는 `MGMT-02` 후행). 이번에 등재하지 않는다 |
| 8 | 48 암호화 **토큰 암호화**(저장 시) | 액세스·리프레시는 **저장하지 않는다**(클라 secure storage · 서버는 `jti` allowlist만) | ✅ 구조적 무해당 — 저장하지 않는 것이 암호화보다 강하다. `refresh_token_session`은 토큰이 아니라 세션 id 행 |
| 9 | 48 암호화 **API Key 암호화** / API 보안 **API Key** | 우리가 *발급*하는 API Key는 0. *소비*하는 외부 키(`anthropic`·`openai`)는 env 단일원천 | 🚫 무해당 — 발급 표면 0. 외부 키 축은 `SEC-11` 스크러버 + `policy-guard`가 담당(사각은 → D10) |
| 10 | 48 전송 **Secure Cookie**·**CSRF 방어** | 쿠키 미사용(`set_cookie` grep 0·Bearer 헤더 전용). OAuth CSRF는 HMAC `state`로 방어(`api/auth.py:206-238`, SEC-08) | ✅ 쿠키 축은 구조적 무해당 / OAuth 축은 충족. TLS·HSTS·CORS는 v1 §4-① + **`SEC-18` 소유** |
| 11 | 48 권한 예시 **AI Prompt 수정** | 프롬프트는 코드·Langfuse 자산이고 런타임 편집 표면 0 | 🚫 미채택 — 런타임 프롬프트 편집 UI는 v1 §2-⑦(보안 정책 중앙관리)와 동형의 이중 진실원천. 프롬프트 변경은 PR·CI 경유가 더 강한 통제 |
| 12 | 48 관리자 보안 **중요 작업 재인증**(step-up) | MFA·재인증 코드 0 | ⏸ v1 §5-① 승계 — 관리자 계정이 **실제 발급**될 때 발화. `ADMIN-01`(고립)이 그 발급 경로다 |

**12종 중 신규 설계로 승격되는 것은 3·4·5뿐이고, 3은 D8·4와 5는 D9로 묶인다.** 나머지 9종은
미채택·무해당·기존 추적으로 닫힌다 — **닫는 것도 판정이며, 판정하지 않으면 미래 세션이 다시 연다.**

---

## §3. 잔여 갭 관측 G1~G5 → 설계 D8~D12

> 번호는 v1의 D1~D7을 이어받는다. 실행 순서: **D9 → D8 → D12 → D10 → D11**.
> D9가 최우선인 이유는 심각도가 아니라 **되돌릴 수 없음**이다 — 철회를 집행하지 않은 기간 동안
> 수집·처리된 미성년 데이터는 사후에 "동의가 있었다"로 되돌릴 수 없다. D12는 D8·D10보다 작지만
> **다른 세션의 폐기 위험을 막는 장치**라 앞에 둔다.

### G1 — 계정에 "복구"가 없다: 식별 키가 이메일 해시 단일 → **D8**

**관측**. `resolve_user`(`api/auth.py:138`)는 `email_hash`(`auth.py:132` — sha256 소문자 이메일)로
`UserProfile`을 upsert한다. 한편 `OAuthIdentity`(`auth.py:92`)는 provider의 **안정 사용자 id**를
`subject`(`auth.py:102`)로 받고 docstring에 "후속 계정 연결용"이라고 쓰여 있는데, `UserProfile`에는
provider·subject 컬럼이 **하나도 없다**(`db/models/user.py` 전 컬럼 확인 — `inkang_provider`는 인강
업체명으로 다른 축). **받아서 버린다.**

**세 갈래로 문제가 된다**:
1. **학습 이력 영구 상실** — 학생이 카카오/네이버 계정의 이메일을 바꾸면 `email_hash`가 달라져
   `resolve_user`가 **신규 계정을 만든다**. 기존 계정에 접근할 수단은 0이다: 비밀번호가 없고
   (v1 §2-③, 옳은 결정), 이메일 변경 경로도 없다(`_SELF_EDITABLE`·`api/users.py:74`). v1은
   "비밀번호 찾기는 구조적 무해당"이라고 정확히 판정했지만, 그 판정은 **이메일이 영구 불변이라는
   가정** 위에 서 있었고 그 가정은 검증된 적이 없다.
2. **cross-provider 자연 연결의 계약 부재** — `resolve_user` docstring(`auth.py:141`)은 "같은 이메일은
   provider 무관 같은 계정으로 매핑(자연 연결)"을 **설계 의도로** 선언한다. 그런데 `OAuthIdentity`에
   `email_verified`가 없어 **provider가 이메일을 검증했는지 우리가 모른다**. 카카오·네이버는 검증하지만
   그것은 코드가 아니라 우리의 *기억*이고, 이메일 미검증 provider가 추가되는 순간 **계정 탈취 벡터**가
   된다(공격자가 피해자 이메일로 그 provider 계정을 만들면 피해자 계정에 로그인된다).
3. **의사결정 우선순위 1위 침해 경로** — 학습 이력 상실은 학생 웰빙 문제다. 그리고 미성년 계정이라
   본인이 복구를 요청할 창구도 제한적이다.

**왜 v1에서 안 보였나**: v1 §1 표의 "계정 복구" 행은 `비밀번호 찾기`·`휴면 계정`·`계정 삭제` 3개뿐
이었다. 외부 문서에 있는 **`이메일 변경`이 표에 없었다.** 판정이 틀린 게 아니라 칸이 없었다.

### D8. 계정 식별 키 축 — provider 안정 id 영속 + 이메일 변경 시 계정 연속성

**정합 설계**
- `UserProfile`에 `auth_provider`·`provider_subject` 2컬럼 + `(auth_provider, provider_subject)` 유니크.
  **신규 테이블 0** — 이미 받고 있는 값을 저장할 자리만 만든다.
- `resolve_user` 조회 우선순위를 **`(provider, subject)` → `email_hash` 폴백**으로. 폴백으로 찾힌
  기존 사용자에게는 `(provider, subject)`를 **채워 넣고 `email_hash`를 현재 이메일로 갱신**한다 →
  다음 로그인부터 이메일 변경이 계정을 끊지 않는다. 기존 행은 subject가 없으므로 폴백이 그대로
  동작한다(**무중단** — 마이그레이션은 nullable 추가 + 백필 없음).
- **PII 축 무변화**: `subject`는 provider 내 불투명 id이고 이메일이 아니다. 평문 이메일 저장은
  여전히 하지 않는다(`email_hash`만).
- **cross-provider 연결 계약을 코드에 못 박는다**: provider 등록 조건("이메일을 검증하는 provider만
  자연 연결에 참여한다")을 `build_oauth_providers` docstring + 동결 테스트로. 미검증 provider를
  추가하려면 테스트가 먼저 깨지게 한다.

**범위 밖**: 사용자 주도 이메일 변경 UI · 계정 병합(한 사람이 두 계정을 이미 만든 경우) ·
`연구자` 역할(§2-①) · 휴면 계정 복구(v1 §2-⑧ 승계).

**의존**: 없음. **태스크**: 신설(아래 §7).

### G2 — 미성년 동의에 "끝"이 없다: 만료·철회 미집행 → **D9**

**관측**. `get_consented_user`(`api/_auth.py:81`)의 판정식은 `user.is_minor and user.parent_consent_at
is None` **하나뿐**이다. 반면 동의 원장 `ParentalConsent`에는:
- `expires_at`·`revoked_at`(`db/models/parental_consent.py:75-76`) — **writer는 `api/users.py:242`의
  상수 `None` 1곳뿐이고, 저장소 전체에 reader 0.**
- 모델 docstring(`:31`)은 인덱스 `idx_parental_consent_user(user_id, consent_signed_at DESC)`의
  용도를 **"학생별 최신 동의 조회(만료 재확인·감사)"**라고 쓴다 — **읽을 사람이 없는 reader를 위해
  인덱스까지 만들어 뒀다.**
- **철회 엔드포인트가 없다**(`api/users.py` 라우트 3개: `GET /me`·`PATCH /me`·`POST /me/parental-consent`).

정본 `docs/standards/security_privacy.md:11`은 "부모 동의 *필수* (회원가입 + **매 분기 재확인**)"을
규정한다. v1은 `security_privacy.md`를 5개 블록에 걸쳐 편집자 부기로 정정했는데(**폐기된 PII 3테이블·
부모/교사 좌석·감사 범위·보존 연한·시크릿/로그**) **이 줄만 손대지 않았다** — 규정은 살아 있고 집행은
0인 상태가 그대로 남았다.

**왜 이것이 최대 갭인가**
- 한 번 받은 동의가 **영구히 유효**하다. 보호자가 마음을 바꿔도 되돌릴 창구가 없고, 학생이 성년이
  되어도 동의 상태가 갱신되지 않는다.
- CLAUDE.md 절대 금기 "학생 풀이 데이터를 *명시적 동의 없이* 학습에 사용 금지"는 **동의의 존재**만
  전제하지 않는다 — **철회된 동의는 동의가 아니다**. 지금은 철회를 표현할 방법 자체가 없다.
- **되돌릴 수 없음**: 철회를 집행하지 않은 기간에 처리된 미성년 데이터는 사후 정정이 불가능하다.
- 이것은 이 저장소가 반복해 온 **"만들고 읽지 않음"**(운영플랫폼 r 8회차 dead 컬럼)의 미성년 보호 판
  이며, 동시에 **"만료 없는 유예"**(CLAUDE.md 2026-08-03)의 동의 판이다.

**정직한 인정**: 코드는 이 상태를 **자백하고 있다** — `api/users.py:203-205`가 "동의 *재확인 주기*
(`expires_at` 정책)…도 후속이다. 현재 `expires_at`은 미설정(None)으로 기록만 한다(게이트 만료 재차단은
후속)"이라고 쓴다. 문제는 자백이 **백로그로 이어지지 않은 것**이다 — v1이 이 축을 D7(페이퍼)에
동반시켰고 D7은 태스크를 신설하지 않았다. 즉 **추적 0**.

### D9. 미성년 동의 만료·철회 집행 — `expires_at`·`revoked_at`의 첫 reader + 철회 경로

**핵심 경계(이것이 D7과 충돌하지 않는 이유)**: **문안은 법률 판단이고 집행은 기계 판단이다.**
- D7/`MGMT-02`가 소유하는 것: 동의 *문구*, `ConsentScope` 확장, 약관 버전 스탬프, **재확인 주기의
  숫자**(분기인가 반기인가). 이것들은 변호사 회신 없이 정하면 **가짜 법적 의사표시**가 된다.
- D9가 소유하는 것: "**철회·만료된 동의는 게이트를 통과시키지 않는다**"는 집행. 이건 문안과 무관하고,
  오히려 **철회를 표현할 수 없는 상태를 유지하는 쪽이 법적 위험이 크다.**

**정합 설계**
- `get_consented_user`가 해당 학생의 **최신 `ParentalConsent` 행**을 읽어 `revoked_at is not None`
  또는 `expires_at <= now`면 403. `parent_consent_at` 단독 판정 폐기. 인덱스는 이미 있다(신규 인덱스 0).
- `DELETE /v1/users/me/parental-consent` 신설 — `revoked_at` 기록 + `user_profile.parent_consent_at`
  해제를 **동일 트랜잭션**으로. 기존 `record_consent_change_audit`(`privacy/audit.py:100`)를
  **재사용**한다(신규 감사 테이블 0 · SEC-09 단일 권위 유지).
- **접근 주체 경계**: 철회를 누가 호출하는가는 `MGMT-01`(법정대리인 인증 모델·blocked)에 걸려 있다.
  따라서 v0는 **학생 본인 토큰**으로 호출 가능한 경로만 연다(자기 계정의 동의를 스스로 철회 —
  법적으로 안전한 방향이고, 보호자 전용 경로는 `MGMT-01` 후행). 이 축소를 docstring에 명시한다.
- **`expires_at`은 여전히 쓰지 않는다**(writer 없음 유지) — reader만 먼저 만든다. 주기 숫자가
  확정되면 writer 1줄로 발화한다. **읽는 쪽을 먼저 세우는 것이 dead 컬럼을 만들지 않는 순서다.**
- 정본 `security_privacy.md:11`에 편집자 부기 — "매 분기"는 **잠정 참조값이며 주기 숫자는 미확정
  (`MGMT-02` 선행)이고, 만료·철회 *집행 메커니즘*은 D9로 착지"**.

**변별력 필수**(CLAUDE.md): 철회 후 보호 엔드포인트가 403이 되고, **철회 판정을 끄면 그 테스트가
실패**해야 한다. 성공/실패 양쪽에서 같은 값을 내는 검사는 위장이다.

**범위 밖**: 동의 scope 확장·약관 버전 스탬프(D7·`MGMT-02`) · 실 법정대리인 본인확인(`MGMT-01`) ·
재확인 주기 **숫자** · 보호자 전용 접근 경로.

**의존**: 없음(즉시 착수 가능). **태스크**: 신설.

### G3 — 공급망·시크릿 스캔에 사각이 있다 → **D10**

**관측**. `.github/workflows/ci.yml`의 `policy-guard` 잡(`:931`)이 하드코딩 시크릿을 grep으로 막는데:
- `--exclude-dir='tests'` — 테스트 픽스처의 진짜 키가 통과한다.
- `--include`가 `*.py *.yaml *.yml *.json *.toml`뿐 — **`.dart`·`.js`가 범위 밖**이다. Flutter 클라는
  `--dart-define`으로 토큰을 주입받는 코드가 있는 축이라 정확히 위험한 쪽이 빠졌다.
- **의존성 취약점 감사가 0건**이다 — CodeQL·gitleaks·`pip-audit`·Dependabot·Trivy 어느 것도 없다.

이건 `SEC-11`이 만든 `tests/backend/ops/test_secret_hardcoding_scan.py`(인프로세스 회계)와
`policy-guard`(CI 회계)의 **이중 회계 중 CI 쪽 표면이 좁은** 상태다. 그리고 공급망 CVE는 v1 §2-⑩이
SQLi/XSS/Bot 탐지를 미채택한 근거("공격 트래픽 실관측 없이 켜면 오탐이 학생을 막는다")가 **적용되지
않는다** — CVE 감사는 트래픽과 무관하고 오탐이 학생을 막지도 않는다. CLAUDE.md는 오히려 반대 방향을
지시한다: "의존성 pin은 검증된 메이저 범위로 **상한을 건다**"(langfuse v2/v4 혼재 사고).

### D10. 공급망·시크릿 스캔 사각 봉합

- 의존성 취약점 감사 잡 1개 CI 배선(`pip-audit` 계열). **CI에서 실제로 도는지 확인한 뒤 완료로
  친다**("저장소에 존재함 ≠ 돌아감" — `tests/infra` 199건 미실행·OPS-03/08/10/11 선례).
- `policy-guard` 시크릿 grep의 `--exclude-dir='tests'` 제거 + `.dart`·`.js` 확장자 편입. 픽스처
  오탐이 나면 **패턴을 좁히지 말고** 픽스처를 고친다(가짜 키는 가짜처럼 생겨야 한다).
- **변별력**: 가짜 시크릿·취약 pin을 심으면 실제로 red가 되는지 확인한다.
- **fail-open 금지**: `continue-on-error`를 붙이지 않는다(`ARCH-23`이 상환한 "돌아감 ≠ 막음"의 재발
  방지). 초기 노이즈가 크면 잡을 붙이되 **범위를 좁혀서** 붙인다 — 막지 않는 잡으로 붙이지 않는다.

**범위 밖**: CodeQL·SAST·WAF 전면 도입(v1 §2-⑩·§5-⑥ 승계).

**의존**: 없음. **태스크**: 신설.

### G4 — 만료 없는 토큰 그랜드파더 → **D11**

**관측**. `security.py:29`가 "후방호환: typ 없는 토큰은 액세스로 간주"를, `_decode_token`(`:75-80`)이
"`expected_type==access`면 typ가 'refresh'만 거부한다(typ 없는 기존 액세스 토큰은 허용)"을 선언한다.
**일몰 조건이 없다.** 액세스 TTL이 24h(`config.py:437`)이므로 typ 도입 커밋 + 24시간이면 typ 없는
토큰은 물리적으로 존재할 수 없는데도 계약이 열려 있다.

실질 위험은 낮다(우리가 발급하는 모든 토큰에 typ가 있다). 그러나 CLAUDE.md **"만료 없는 유예·제외
금지"**(2026-08-03 등재 — "유예는 반드시 만료 또는 재확인 지점을 동반한다")에 정면으로 해당하고,
이 규칙의 1차 집행은 산문이 아니라 **코드**여야 한다(PB-02 그랜드파더 만료 계약 선례).

### D11. 토큰 `typ` 그랜드파더 만료 계약
typ를 필수화하고(액세스도 `typ == "access"` 요구), 부재 허용이 사라졌음을 동결 테스트로 못 박는다.
**범위 밖**: 액세스 TTL 15분 단축·denylist(v1 §5-⑧ — 발화조건은 §5에서 갱신). **태스크**: 신설.

### G5 — 하네스가 이 세션의 중복 착수를 막지 못했다 → **D12**

**관측**. `scripts/harness/remote_claims.py:1274` `_DOC_SERIES_SUFFIX = "_review.md"` —
미머지 브랜치 설계 문서 탐지(`HARN-14`)가 `docs/**/*_review.md`만 본다. k20m0w의
`docs/reviews/functional_security_audit_2026-08-08.md`는 접미어가 달라 **`_is_doc_series_path`가
False를 반환**하고, 그래서 이 세션의 SessionStart 브리핑 "미머지 브랜치의 신규 설계 문서" 목록에
**뜨지 않았다**(실제 브리핑 4건은 전부 `*_gap_review.md`).

결과: 이 세션은 XFF 무검증 신뢰를 "최대 갭"으로 판정하고 태스크를 등재하기 직전까지 갔다. 그것은
`SEC-14`가 이미 **done**으로 봉합한 항목이다. 막은 것은 하네스가 아니라 **수동 브랜치 조사**였다.

`HARN-14`의 설계 주석(`remote_claims.py:1270-1272`)은 "설계 문서 중복은 *나이가 아니라 존재 자체*가
위험 신호"라고 정확히 썼는데, **존재를 판정하는 필터가 파일명 관례 1종에 묶여 있었다.** 관례를 지키지
않은 문서(=보안 감사)가 정확히 가장 위험한 문서였다.

### D12. 하네스 문서 시리즈 탐지 접미어 사각 봉합
`_DOC_SERIES_SUFFIX`를 접미어 **목록**으로 확장하거나 `docs/reviews/` 디렉터리를 스캔 대상에 편입.
**변별력**: k20m0w의 `functional_security_audit_2026-08-08.md`가 실제로 브리핑에 뜨는지 재현하고,
확장을 되돌리면 다시 사라지는지 확인한다.
**범위 밖**: `HARN-14`(나이 임계)·`HARN-15`(번호 충돌 원격 스캔) 소관 — 중복 착수 금지. **태스크**: 신설.

---

## §4. 정정 — v1·정본 stale 5곳 (원본을 수정하지 않고 여기 기록)

| # | 위치 | 현 서술 | 실측 | 처리 |
|---|---|---|---|---|
| ① | `privacy/retention_purge_cli.py:8` | "둘 다 *실행 진입점*이 없어 retention이 집행되지 않았다" | `docker-compose.prod.yml:143-166`에 24h 루프 배선(SEC-12 done) | docstring 갱신 필요. **D10 착수 세션이 동반 처리**(인프라 축 동일) |
| ② | `docs/standards/security_privacy.md:11` | "부모 동의 *필수* (회원가입 + 매 분기 재확인)" | 재확인 집행 코드 0 · 주기 미확정(`api/users.py:203-205` 자백) | **D9 acceptance에 포함**(편집자 부기) |
| ③ | v1 `:396-398`·§5-⑤ | "`gates` 서브커맨드에 `add`가 없어 CLI 경로가 없다" | `backlog.py gates add` 존재 | §1·§5-⑤에 기록. v1 본문 미수정 |
| ④ | v1 `:18`·§3 D1 | "CUD 완전 무인증 — 최대 갭" | SEC-07로 해소 | §1에 기록. v1 본문 미수정 |
| ⑤ | v1 `:301` D4 | "학생이 자기 세션을 끊을 방법이 없다" | SEC-10 + MOB-12로 해소 | §1에 기록. v1 본문 미수정 |

v1 본문은 **한 글자도 수정하지 않았다** — `SEC-07`~`SEC-12` 6개 완료 태스크의 판정 근거이기 때문.
v1 최상단에 r2 존재 배너 1줄만 추가한다.

---

## §5. 유보 항목의 발화 조건 (v1 §5 9건 승계 + 갱신)

| # | 유보 항목 | 발화 트리거 | r2 갱신 |
|---|---|---|---|
| ① | 관리자 MFA·IP 허용목록·중요작업 재인증·계정 잠금 + TLS/보안헤더 | 관리자 계정이 실제 발급될 때 | **근접**. `ADMIN-01`(발급 CLI)이 고립 브랜치에 done — 회수되는 순간 ①이 발화한다. TLS/보안헤더 축은 `SEC-18`이 선점 |
| ② | `PARENT`·`TEACHER`·`SCHOOL_ADMIN` 역할 | Phase 3 대시보드/B2B 계약이 실체를 가질 때 | 미발화 유지 |
| ③ | 감사 2테이블 통합 · PII 접근 전수 감사 | 관리자 콘솔 Phase B | 미발화 유지. `record_admin_access_audit`(`privacy/audit.py:124`)는 **호출부 0**이 여전히 정직한 상태(좌석 부재) |
| ④ | 동의 scope 확장·버전 스탬프·**재확인 주기 숫자** | `MGMT-02` 문안 회신 + 해당 처리 개시 | **범위 축소**. 만료·철회 *집행*은 D9가 분리 소유하므로, ④에 남는 것은 문안·scope·주기 숫자뿐 |
| ⑤ | 법무 게이트(`gates.yaml`) 승격 | ~~공개 β 결정 + `gates add` CLI 경로 확보~~ → **공개 β 결정만** | **근거 절반 해소**(CLI 존재). 나머지는 Kiki 결정이라 이번에도 승격하지 않는다 |
| ⑥ | WAF·공격 탐지·비정상 IP 판정 | 공개 β + 공격 트래픽 실관측 | 미발화 유지. **단 공급망 CVE 감사는 이 조건의 대상이 아니다** → D10으로 분리 |
| ⑦ | Passkey·WebAuthn | 소셜 IdP 미보급 시장 진입 또는 provider 장애 실관측 | 미발화 유지 |
| ⑧ | 액세스 TTL 15분 + 토큰 denylist | 클라 refresh-on-401 배선 완료(MOB) | **선결 조건 충족**. `MOB-12`가 `auth_interceptor.dart`에 401→refresh→재시도를 배선했다. 그러나 **지금 발화시키지 않는다** — TTL 단축의 이득(탈취 창 축소)이 실측되지 않았고, D8·D9가 같은 인증 축을 건드리는 중이다. 재판정은 D8·D9 착지 후 |
| ⑨ | 프로필 PII 일반화(`birth_year`→연령대 버킷) | 코호트 N 확대로 재식별 위험 실측 | 미발화 유지 |

---

## §6. 반복 실수 — 등재 (CLAUDE.md 실수 관리 의무)

### 미머지 고립 — 4회차 (반복 실수)

| 회차 | 사고 | 규모 |
|---|---|---|
| 1 | `claude/shadow-data-s3-pilot-nh5kbz` 9일 고립(2026-07-30) | 70커밋·128파일 |
| 2 | `OPS-07` 병렬 구현(2026-07-27) | 735줄 폐기 |
| 3 | 협업 판정 고립 → 이식으로 전환(2026-08-04) | 441행 문서 + 태스크 3건 |
| **4** | **`SEC-13`~`SEC-18`·`ADMIN-01` 고립(이번)** | **태스크 6건 + 실물 757줄 + 감사 문서 1편** |

이번 회차의 새로운 점: 고립된 것이 **`done` 상태의 완성 산출물**이라는 것이다. main의 `ADMIN-01`은
`todo`이고 `backlog.py next`가 이를 착수 후보로 계산한다 — 즉 **하네스가 재구현을 능동적으로 권한다.**
`HARN-11`(미머지 done 필터)이 이 부류를 위해 만들어졌으나, 태스크 **파일 자체가 main에 없는**
SEC-13~18은 필터의 관측 범위 밖이다(없는 파일은 done으로 보이지 않는다).

**대책**: D12(코드) — 문서 탐지 사각 봉합. 태스크 파일 축의 사각은 `HARN-15`가 이미 소유하므로
중복 등재하지 않는다. **회수(포팅) 자체는 이 세션 범위 밖**이며, §0-④가 소유권을 기록해 다음 세션이
재구현 대신 포팅을 선택할 수 있게 한다.

### 시스템 실수 (신규 등재)

**사고 경위**: 하네스의 미머지 설계 문서 탐지가 파일명 접미어 `_review.md` 1종에만 묶여 있어
(`remote_claims.py:1274`), 명명 관례를 따르지 않은 `functional_security_audit_2026-08-08.md`가
브리핑에 뜨지 않았다. 이 세션은 그 감사가 이미 봉합한 XFF 무검증 신뢰(`SEC-14`)를 "최대 갭"으로
판정해 등재 직전까지 갔고, 막은 것은 하네스가 아니라 수동 브랜치 조사였다. **폐기 0줄로 끝났지만
그것은 운이다.**

**교훈의 일반형**: 보호 장치의 **관측 범위가 명명 관례에 의존하면, 관례를 지키지 않은 산출물이
정확히 가장 위험한 산출물이 된다.** 관례를 어긴 문서일수록 새로운 형태의 작업이고, 새로운 형태일수록
중복 시 폐기량이 크다.

**대책**: D12로 등재(규칙이 아니라 **코드**로 상환 — CLAUDE.md "다음엔 조심한다는 대책이 아니다").

### 갭 리뷰 시리즈 자체의 프로세스 교훈

v1의 crosswalk 표는 촘촘했지만 **외부 문서의 12개 항목에 대해 행을 만들지 않았고**, 이번 최대 갭 2건은
정확히 그 사각(§2-③④⑤)에서 나왔다. ⚠️ 판정을 받은 칸은 태스크로 추적되지만 **표에 없는 칸은 아무도
추적하지 않는다** — 판정 ⚠️보다 **누락**이 더 오래 산다.
→ 자매 리뷰 시리즈는 crosswalk 작성 시 **외부 문서 항목의 전수 매핑을 먼저 만들고**, 판정이
미채택·무해당이어도 **행을 남긴다**(닫는 것도 판정이다). 이는 operations r2가 남긴 교훈("코드 0과
설계 0을 구분하지 않으면 미래 세션이 이미 있는 설계를 재작성한다")의 커버리지 판이다.

---

## §7. 실행 — 백로그 등재 · 중복 회피 대장

### 신규 등재 5건 (전건 `backlog.py add` CLI 경유 — ID 손편집 0, 번호는 CLI가 배정)

| 설계 | 태스크 | stage/priority | layer |
|---|---|---|---|
| D9 | `SEC-20-minor-consent-expiry-revocation-enforcement` | S4 / 1 | backend |
| D8 | `SEC-21-account-identity-key-provider-subject` | S4 / 2 | backend |
| D12 | `HARN-25-doc-series-suffix-blindspot` | S4 / 2 | infra |
| D10 | `SEC-22-supply-chain-secret-scan-gaps` | S4 / 3 | infra |
| D11 | `SEC-23-token-typ-grandfather-sunset` | S4 / 4 | backend |

`validate` green — 등재 직후 태스크 **239 → 244건**, 이후 main 머지 반영으로 **267건**(게이트 10건).

**후속 개명 1건(`HARN-22` → `HARN-25`)**: 등재 직후 main을 머지하자 `validate`가
`❌ 번호 충돌 'HARN-22'` **exit 1**로 포착했다 — 같은 시각 `HARN-22-id-number-suggestion-race`가
#778로 **먼저 머지**돼 있었다(공교롭게도 상대 태스크의 주제가 *번호 제안 경쟁* 그 자체다).
상대가 머지분이므로 이쪽을 개명했고, 재시도한 `HARN-23`도 원격
`claude/pr-without-request-1me42b`에 선점돼 **또 거부**돼 CLI 제안값 `HARN-25`를 채택했다.
번호는 전건 CLI 배정이고 YAML 손편집은 0이다. **이 사건 자체가 D12의 근거를 강화한다** —
가드는 관측만 하고 번호를 *예약*하지 않으므로, 두 세션이 각각 `add`를 돌리는 구간에서 같은 빈
번호가 양쪽에 제안된다(`HARN-22`가 추적하는 TOCTOU). 이번엔 머지 시점의 `validate`가 잡았다.

**번호 가드가 실제로 작동했고, 동시에 기존 충돌 1건을 드러냈다**: 첫 시도(`SEC-19`)가
`SEC-19-generate-rate-limit`(원격 `claude/whymath-ai-integration-check-5qqcp4`)와 충돌해 **거부**되고
CLI가 `SEC-20`을 제안했다(HARN-10·HARN-15 설계대로). 그 과정에서 전 원격 브랜치를 훑은 결과
**`SEC-13`이 두 브랜치에 서로 다른 태스크로 배정**되어 있음이 드러났다 —
`SEC-13-external-store-manifest-truthfulness`(`claude/whymath-ai-recommendation-review-q8tvcx`) vs
`SEC-13-harness-metrics-exposure-contract`(`claude/whymath-issues-review-k20m0w`). full-ID는 슬러그
덕에 달라 `validate`가 통과하지만 **문서·커밋의 "SEC-13" 참조는 결정 불가**다 — 2026-07-18/25
`ARCH-13`·07-29 `OPS-15`와 같은 유형의 3회차다. 가드는 *신규* 등재를 막을 뿐 **이미 착지한 충돌을
소급 해소하지 못한다**. 정리는 두 브랜치 회수 시점의 소관이며 이 문서는 관측만 기록한다.

### 중복 등재 금지 대장 (이번에 등재하지 **않는** 것과 그 소유자)

| 주제 | 기존 추적 |
|---|---|
| XFF 무검증 신뢰 · 무인증 정답 노출 · harness-metrics 노출 · outcome 소유권 · OCR 업로드 한도 | `SEC-13`~`SEC-17`(k20m0w, done) |
| prod `/docs`·OpenAPI 노출 · CORS · 보안 헤더 | `SEC-18`(k20m0w, in_progress) |
| 운영자 좌석 발급 · 역할 변경 감사 | `ADMIN-01`(admin-01 브랜치, done·고립) |
| dead 테넌시/결제 컬럼 | `ADMIN-02`(admin-02 브랜치, blocked·재판정됨) |
| 감사 보존·파기 정책 · 법적 보존 예외 | `ADMIN-03`(main, todo) |
| 동의 문안·scope·버전 스탬프·재확인 주기 숫자 | `MGMT-02`(blocked, kiki) |
| 실 법정대리인 본인확인 | `MGMT-01`(blocked, kiki) |
| prod 대화 암호화 키 실측 | `SEC-02`(todo, kiki) |
| 미머지 태스크 번호 충돌 원격 스캔 | `HARN-15` |
| 실 소셜 로그인 code 획득(webview) | OAuth-c3(MOB 축) |

---

## 부록 — 실측 근거 (2026-08-11 · 브랜치 `claude/whymath-account-security-dw9lww` · HEAD `959ec4ad`)

| 주장 | 확인 위치·명령 |
|---|---|
| v1 D1~D6이 SEC-07~12로 전건 done | `grep -m1 '^status:' backlog/tasks/SEC-0[7-9]*.yaml backlog/tasks/SEC-1[0-2]*.yaml` |
| CUD 무인증 해소 | `grep -n RequireContentAdmin src/backend/whymath_backend/api/{concepts,problems}.py` → 각 4건 |
| `/v1/me` 36라우트 전건 인증 | `me.py` 라우트 스캔 — `ConsentedUser` 35 · `CurrentUser` 1 · 무인증 0 |
| 계정 식별 키가 email_hash 단일 | `api/auth.py:132` `email_hash` · `:138` `resolve_user`가 `UserProfile.email_hash == digest`로 조회 |
| provider subject 미영속 | `api/auth.py:102` `subject` 수신 · `grep -n "provider\|subject" db/models/user.py` → `inkang_provider`(다른 축)만 |
| 이메일 변경 경로 0 | `api/users.py:74` `_SELF_EDITABLE` 16필드에 이메일 없음 |
| 동의 게이트가 `parent_consent_at`만 읽음 | `api/_auth.py:81-93` 전문 |
| `expires_at`·`revoked_at` reader 0 | `db/models/parental_consent.py:75-76` 정의 · `grep -rn "revoked_at" api/ privacy/` → `api/users.py:242`(상수 `None`)만, 나머지는 `refresh_token_session`·`device_credential`의 동명 컬럼 |
| 만료 재확인용 인덱스가 reader 없이 존재 | `db/models/parental_consent.py:31` "학생별 최신 동의 조회(만료 재확인·감사)" |
| 코드의 자백 | `api/users.py:203-205` "재확인 주기(expires_at 정책)…도 후속이다…게이트 만료 재차단은 후속" |
| 정본 규정 미정정 | `docs/standards/security_privacy.md:11` "회원가입 + 매 분기 재확인" — 편집자 부기 없음 |
| 철회 엔드포인트 0 | `grep -n "@router\." api/users.py` → 3건(`GET /me`·`PATCH /me`·`POST /me/parental-consent`) |
| typ 그랜드파더 만료 없음 | `security.py:29` 주석 · `:75-80` docstring |
| policy-guard 시크릿 스캔 사각 | `.github/workflows/ci.yml:958-975` — `--exclude-dir='tests'` · include에 `.dart`/`.js` 없음 |
| 의존성 취약점 감사 0건 | `.github/workflows/` 전수 — CodeQL·gitleaks·pip-audit·Trivy·Dependabot 정의 없음 |
| 문서 시리즈 탐지 접미어 1종 | `scripts/harness/remote_claims.py:1274` `_DOC_SERIES_SUFFIX = "_review.md"` · `:1277` `_is_doc_series_path` |
| SEC-13~18이 main에 없음 | `git ls-tree -r --name-only origin/main backlog/tasks/ \| grep SEC-` → SEC-01~12만 |
| SEC-13~18이 k20m0w에 있음 | `git ls-tree -r --name-only origin/claude/whymath-issues-review-k20m0w backlog/tasks/ \| grep SEC-1[3-8]` |
| ADMIN-01 실물 고립 | `git ls-tree -r --name-only origin/claude/admin-01-operator-seat-grant-audit \| grep role_grant` → 3파일 · main은 0건 |
| `gates add` CLI 존재 | `python3 scripts/harness/backlog.py --help` → `gates add <G-id> --title ...` |
| 법무 게이트 0건 | `backlog/gates.yaml` 7건 전부 기술·시연·의사결정 축 |
| retention 스케줄 배선(docstring stale) | `docker-compose.prod.yml:143-166` 24h 루프 · `privacy/retention_purge_cli.py:8` 자백문 잔존 |
