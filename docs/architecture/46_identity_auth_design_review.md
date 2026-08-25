# 46_회원가입·로그인·인증 설계 검토 — 외부 EOS Identity Platform 설계안 대조 (2026-08-25)

> **범위**: 사용자가 제출한 『46_회원가입·로그인·인증 설계 검토』(80절, EOS Identity & Access
> Platform 설계안)을 현 WhyMath 코드베이스 및 기존 결정과 대조한 갭 검토.
> **성격**: **r2(`account_security_gap_review_r2.md`)의 델타가 아닌 별도 문서**. r2가 『11.
> 계정·보안』 틀(46·47·48·49~53)을 다룬다면, 이 설계안은 모듈 46 단독에 대한 80절 심화안이므로
> 별도 보관. r2와 상호 참조하며 r2 본문 판정은 그대로 둔다.
> **결론 3줄**:
> 1. 문서의 상당수 권장(토큰 회전·세션 관리·동의 게이트·역할 게이트)은 **이미 구현돼 있다** —
>    "처음부터 구축"이 아니라 "현 구현 기준으로 갭을 선별"해야 한다.
> 2. 문서는 **4가지 봉인 결정**과 정면 충돌: 비밀번호·계정 잠금·이메일 평문 저장·로그인 이력 수집.
>    이를 무시하면 미머지 브랜치의 동결 테스트와 `security_privacy.md` 정본이 깨진다.
> 3. 이 설계안의 진짜 가치는 **Identity/Account 분리**(r2 D8 해법) · **Relationship 기반 인가** ·
>    **7계층 내 Identity 배치 결정**에 있다. 채택은 이 3점에 집중하고 나머지는 현 결정을 존중할 때
>    재설계 비용이 가장 적다.

관련 정본: `docs/architecture/account_security_gap_review.md`(v1) ·
`docs/architecture/account_security_gap_review_r2.md`(현 정본, 2026-08-11) ·
`docs/standards/security_privacy.md`(보안·개인정보 표준) ·
`docs/legal/pipa_data_matrix.md`(역할×항목 2차원 정본) ·
`CLAUDE.md` 절대 금기 · `MEMORY.md` 결정 로그.

---

## §0. 대상 문서 식별

제출된 문서는 80절로 구성되며, 다음 핵심 주장을 한다.

- Identity ≠ Account ≠ Role ≠ Profile ≠ Credential ≠ Session(§1-2)
- 추천 엔티티: Person → Identity → Account/Credential/Session/Device/ExternalIdentity/Profile/Membership/RoleAssignment/Relationship/Consent(§3)
- MVP 필수(§72): Identity/Account/이메일 가입·인증·로그인/안전한 Password Hash/Password Reset/Session/Access·Refresh Token/Logout/Rate Limit/Security Event/역할/보호자 관계/Consent·Authorization·Audit 연결
- 장기: Passkey/MFA/SSO/Organization/Risk Engine/Service·AI Agent Identity(§68, 75, 79)

이 문서는 기술적으로 대부분 옳다. 문제는 **WhyMath에 맞는가?** 이다.

---

## §1. 절별 대조표

| 외부 문서 절 | 핵심 권고 | WhyMath 현행(실측) | 판정 |
|---|---|---|---|
| §5 Account 상태기계(PENDING/ACTIVE/LOCKED/SUSPENDED/DISABLED/DELETED) | 6 상태 + 전이 명시 | `UserProfile`에 `is_active`/`is_deleted`/`deleted_at` 3상태(`db/models/user.py:172-174`). `LOCKED`/`SUSPENDED` **컬럼 부재** — 의도적 미도입, `tests/backend/api/test_no_lockout_columns.py`가 동결 | ⚠️ 충돌 — 봉인 결정. 상태 확장 시 재결정 필요 |
| §7 인증 방법 Credential Registry(PASSKEY/TOTP/EMAIL_OTP/GOOGLE/KAKAO…) | `authenticators` 추상 테이블 | 현재 OAuth provider(Kakao/Naver)가 `provider` 컬럼으로 하드코딩. 2FA/Passkey/TOTP 미구현(v1 §4 정직한 공백) | ✅ 신규·채택 가치, 장기 |
| §8-9 비밀번호 정책·Argon2id 저장 | 비밀번호 로그인 P0 | **비밀번호 로그인 부재**. OAuth 전용 정책. `passlib`은 선언만(`pyproject.toml` `passlib` extras? 실제론 argon2-cffi가 아닌 일반 패스워드 모듈 선언) | ❌ 충돌 — P0에서 제외된 봉인 결정 |
| §10 Passkey를 장기 기본 인증 후보 | Account 1:N Authenticator | 미구현(v1 §4 정직한 공백) | ✅ 신규·채택 가치, 장기 |
| §13-16 세션 관리·Refresh Token 회전·재사용 탐지·Logout All | RT 회전 + reuse detection + 세션 폐기 | `api/auth.py:413-429`에서 이미 재사용 탐지 + 전체 세션 패닉 취소. `DELETE /sessions` 전체 로그아웃 `:527`, 단건 `:538` 구현 | ✅ 구현됨 |
| §17-18 Device 별도 객체 | `devices` 테이블 | `DeviceCredential`(`db/models/device.py:38`)은 **rate limit 신뢰용**, 로그인 세션용 기기 아님. r2 §0-②에서도 "device_credential ≠ 로그인 세션" 강조. `GET /sessions`의 platform은 세션 자체에서 추출 | ⚠️ 경계 혼동 가능. 별도 Device 모델은 장기 고려 |
| §20 로그인 실패 처리· progressive delay | LOCKED 상태 | **계정 잠금 미도입**. 공격자가 타인 계정을 DoS 잠금할 수 있다는 우려가 봉인 이유(v1 §2) | ❌ 충돌 |
| §21 계정 존재 노출 방지 | 이메일·OTP 엔드포인트에서 일반 메시지 | 현재 비밀번호 리셋/이메일 가입 경로가 없어 해당 공격면이 좁음. OAuth 가입은 provider가 응답 처리 | ✅ 이미 OAuth 설계에서 간접 충족 |
| §22 복구 ≥ 인증 보증 | Account Recovery Assurance ≥ Auth Assurance | 계정 복구 경로 자체가 **부재**(r2 D8). 식별 키가 `email_hash` 단일, provider `subject`는 버려짐. 이메일 변경 경로 0 | ⚠️ **이 문서의 가장 중요한 신규 가치**. D8 해법의 출발점 |
| §24 보호자·학생 계정 분리 | Relationship(`GUARDIAN_OF`) | 부모 계정/역할 부재. `parent_email_hash`만 `UserProfile`에 있음(`user.py:151`) | ✅ 신규·채택 가치, Phase 3+ |
| §25-26 미성년 동의·생년월일 최소화 | 연령 구간/법정대리인 동의 | `get_consented_user`(`api/_auth.py:92`) 게이트 구현. `expires_at`·`revoked_at`은 reader/writer 부재(r2 D9) | ⚠️ 부분 구현. 법규 보강 필요(§3) |
| §27-28 이메일 별도 모델·이메일 변경 보안 이벤트 | `email_addresses` 테이블 | `email_hash` 단일 컬럼(`user.py:83`). 이메일 변경 경로 0 | ⚠️ D8 연결. 단 문서의 평문 `normalized_email`은 현 PII 미수집 정책과 충돌 |
| §30-31 Social Login·Account Linking | provider+subject 연결, 이메일로 자동 합병 금지 | `api/auth.py`에서 OAuth 콜백 시 `email_hash` upsert. provider `subject` 미보존 | ⚠️ 현재는 email_hash 기반 병합 — 설계안의 "자동 합병 금지"는 채택 가치 |
| §32-33 OIDC/OAuth + JWT 최소 정보 | Authorization Code + PKCE, sub/iss/aud/scope/session_id | 현재는 카카오/네이버 OAuth 콜백. JWT payload는 `user_id`, `role`, `is_minor` 등(`security.py`). PKCE는 **미사용**(v1 §4 정직한 공백) | ⚠️ PKCE·JWT 최소화 개선 필요 |
| §34-36 Role/ABAC/ReBAC | Role은 Token에 과도하게 고정하지 말 것, 관계 기반 인가 | `Role` enum 2값(`schema/enums.py:1473`), `<`/`>` 비교 TypeError로 동결. `access_matrix.json`은 2D 역할×항목 매트릭스. ABAC/ReBAC 미구현 | ✅ Relationship 기반 인가는 WhyMath 핵심 가치(§5) |
| §37-39 조직·멀티테넌시·Provisioning | Organization, Membership, Invitation | 미구현(v1 §4 정직한 공백) | ✅ 장기 가치, 학교 SSO 전 단계 |
| §40 Invitation 모델 | token_hash 저장 | 미구현 | ✅ 장기 |
| §41 계정 삭제 vs 데이터 삭제 분리 | Account deletion ≠ Learning data deletion | `privacy/erasure.py`에서 `UserProfile` 삭제 + 18테이블 원자 삭제. **학습 데이터 보존** 경로는 현재 삭제권만 있음 | ⚠️ 정책 보강 필요 |
| §42-43 Auth Event 표준 발행·Audit 분리 | `identity.authentication.succeeded` 등 | `privacy/audit.py` 4종 writer(export·consent·admin·role) 구현. **인증 이벤트 전용 writer는 부재** | ⚠️ 부분 구현. §4 감사 확장 필요 |
| §55-56 Frontend token 저장·CSRF/XSS | HttpOnly Secure SameSite Cookie, BFF | 모바일(Secure Storage/Keystore) 미언급. 웹 쪽은 현재 SPA OAuth 흐름 | ⚠️ 모바일 전략 보강 필요(§3) |
| §57-58 Rate Limit·OTP 목적 분리 | IP/account/device 한도, purpose-bound OTP | `/callback`·`/refresh`에 IP rate limit 부착. OTP 메커니즘 부재 | ⚠️ OTP 설계 시 채택 |
| §60-61 Admin 인증 분리·Super Admin | MFA 강제, 짧은 세션, step-up, approval | `CONTENT_ADMIN`만 존재. 별도 Admin BFF/승인 체계 미구현(v1 §4 정직한 공백) | ✅ 장기 |
| §65-66 Observability·SLO | login_success_rate, P95/P99 | 미수집(v1 §3 D3: 학생 접속 시각 이력 = 프로파일링 자산화 거부) | ❌ 충돌 |
| §68 배포 전략 | Modular Monolith → 분리 | 현재는 L5 인증 집행(`security.py:1`) + 횡단 privacy. 별도 Identity 모듈 미정 | ⚠️ **7계층 배치 결정 필요**(§5) |
| §72 MVP 필수 목록 | 이메일 가입·비밀번호·Password Reset P0 | 현재 OAuth 전용 정책과 충돌 | ❌ P0 재정의 필요(§5) |
| §80 개발 우선순위 | 46-1→46-12 시퀀스 | 현재 최대 미해소는 모바일 OAuth code 획득 스텁(`src/mobile/lib/features/auth/data/oauth_code_requester.dart:34-47`) | ⚠️ 우선순위 재정렬 필요 |

---

## §2. 봉인 결정과의 충돌 4건 — 채택 시 반드시 재결정

이 설계안이 P0로 제시하는 항목 중 다음 4건은 WhyMath에서 **의도적으로 봉인**한 것이다. 채택하려면 기존 결정 로그를 명시적으로 개정해야 한다.

### ① 비밀번호 로그인

- 설계안: §8-9, §72 — 이메일 가입·비밀번호 Hash(PASSWORD credential) P0
- 현재: **비밀번호 로그인 부재**. OAuth(Kakao/Naver) 전용. `passlib` 선언만 있고 UI/플로우 0.
- 근거: WhyMath는 학생 비밀번호 관리 부담과 유출 리스크를 줄이기 위해 OAuth 전용으로 출발(v1 §2-③). 비밀번호 없는 인증은 이 결정의 핵심.
- 재결정 필요: 비밀번호를 도입하려면 "학부모/교사 전용", "Passkey+비밀번호 병행", "전면 폐기" 중 하나를 정해야 한다. 학생용 비밀번호는 다시 설득력 있는 위험 평가 필요.

### ② 계정 잠금(LOCKED) 상태

- 설계안: §5, §20 — `LOCKED` 상태, progressive delay, 5회 실패 lockout
- 현재: `UserProfile`에 `is_active`/`is_deleted`만 존재. `LOCKED`/`SUSPENDED` 컬럼 부재. `tests/backend/api/test_no_lockout_columns.py`가 이를 동결.
- 근거: 공격자가 타인 계정을 의도적으로 잠글 수 있는 DoS가 학생에게 더 해롭다는 판단. IP/Account 복합 rate limit은 존재하나 계정 잠금은 없음.
- 재결정 필요: Risk-Based Authentication(§19)을 도입할 때 account-level lockout을 **선택적으로** 켤 수 있게 할 것인지, 아니면 영원히 금지할 것인지.

### ③ 이메일 평문 저장

- 설계안: §27 — `email_addresses.normalized_email` 컬럼 권장
- 현재: `email_hash` SHA-256만 저장(`db/models/user.py:83`). PII 미수집 전략.
- 근거: 이메일 변경·보조 이메일 기능을 위해 평문이 필요하지만, WhyMath는 **PII 최소화**를 택해 해시로 식별.
- 재결정 필요: 평문 이메일을 저장하려면 암호화(KMS envelope)와 수집 목적 공개가 필요. 평문 없이 Identity/Account 분리를 할 수 있는지(예: hash 기준 연결) 먼저 검토해야 한다.

### ④ 로그인 이력 수집

- 설계안: §13-14, §65 — 세션 IP/UA/auth_level/risk_level, Observability 지표
- 현재: **로그인 이력(접속 시각 이력) 수집 거부**. `GET /v1/auth/sessions`는 활성 세션만. r2 §2-2에 "학생 접속 시각 이력 자체가 프로파일링 자산"이라는 논거.
- 근거: 미성년 학생 대상 서비스에서 접속 패턴은 민감한 행동 데이터. 보안(낯선 기기 인지) 목적은 활성 세션로 충족.
- 재결정 필요: Risk Engine(§19)을 위해서는 일부 이벤트가 필요하지만, **학생 프로파일링**과의 경계를 명시해야 한다.

---

## §3. 한국 규제·실무 누락 보강

설계안은 OWASP·NIST·W3C·개인정보보호법을 인용하지만, WhyMath가 한국 정보통신서비스로 운영될 때 필요한 사항이 빠져 있다.

### ① 정보통신망법(온라인 서비스 특례)

- **제29조**: 1년간 미이용 계정은 **분리보관·파기**해야 한다. 설계안 §62 상태 머신에 `DORMANT`가 없다.
- **제31조**: 주민등록번호 수집 제한. 학교 SSO를 연결할 때 학번·주민번호 처리 방식이 필요.
- **본인확인기관**: 만 14세 미만 보호자 동의를 받기 위한 본인확인은 **신용정보/통신사 본인확인기관** 경유가 일반적. 현재 `StubGuardianVerifier`이므로 출시 전 MGMT-01(변호사 자문)이 선행.
- 반영: 상태 머신에 `DORMANT` 추가, 휴면 계정 전환·복구 정책 명시.

### ② 이메일리스 학생

- 설계안 §72는 "이메일 가입"을 P0로 둔다. 그러나 초·중학생 상당수는 개인 이메일이나 휴대전화가 없다.
- 현재도 `email_hash` 단일 식별키라 이메일 없는 학교 발급 계정에 취약(r2 D8과 동일 뿌리).
- 반영: 학교/기관이 발급한 **username 또는 학번**을 통한 가입·로그인 플로우(Invitation/Provisioning, §39-40)를 P1 이상으로 둬야 한다.

### ③ Flutter 모바일 토큰 저장

- 설계안 §55-56은 웹/HttpOnly 쿠키·BFF 중심. 주 클라이언트인 Flutter의 Secure Storage/Keystore·iOS Keychain 사용, 백그라운드 access token 갱신 전략이 없다.
- 반영: "인증 상태 저장" 플랫폼별 매트릭스(웹·iOS·Android) 추가.

### ④ 보호자 복구 체계

- 설계안 §23 "Parent Assisted Recovery"는 교육 EOS에서 중요하다고 언급.
- 현재 부모 계정이 없어 Parent Assisted Recovery 불가. `parent_email_hash`로만 단방향 연락 가능.
- 반영: Relationship 모델(§24) 도입 시 복구 권한 위임을 함께 설계.

---

## §4. 기술 보완점

### ① NIST SP 800-63 최신판

- 설계안 §8은 NIST 가이드 방향을 올바르게 인용했으나, **SP 800-63-4(2025년 7월 최종판)** 기준으로 갱신해야 한다.
- 구체 규칙: single-factor 비밀번호 최소 15자·복잡성 규칙 금지·주기적 변경 강제 금지·유출 비밀번호 대조 필수. WhyMath가 비밀번호를 도입할 경우 이를 따르는 것이 표준.

### ② OAuth 2.0 최신 BCP

- 설계안 §14는 RFC 9700(BCP) 인용이 정확하다. refresh token rotation만이 아니라 **PKCE 필수화**, **sender-constrained token(DPoP/mTLS)** 권고를 함께 반영해야 한다.
- 현재: PKCE 미사용(v1 §4 정직한 공백). 모바일 OAuth code 획득조차 스텁(`oauth_code_requester.dart:34-47`).

### ③ JWT 운용

- 설계안 §33은 JWT에 최소 정보만 넣으라고 올바르게 지시.
- 누락: `alg` 고정/알고리즘 혼동 방지, **JWKS 키 로테이션**, `kid` injection 방어, **access token 즉시 무효화 수단**(짧은 TTL 외 admin 강제 로그아웃·권한 박탈 시 필요).
- 현재 `security.py`는 HS256 단일 키. refresh만 서버측 취소 가능. access token은 만료까지 유효.

### ④ Passkey 세부

- 설계안 §10은 Passkey를 장기 후보로 올바르게 권고.
- 누락: **동기화 패스키** vs **기기 바운드** 구분, **attestation 신뢰 정책**, "패스키를 잃으면?"과 §23 복구의 연결. 설계안 §23에 Recovery Code/Parent Assisted Recovery가 있지만 passkey 특수 시나리오는 명시되지 않음.

### ⑤ 감사 이벤트 확장

- 설계안 §42-43의 표준 인증 이벤트(성공/실패/패스키 등록/세션 생성 등)는 `privacy/audit.py` 4종 writer에 추가해야 한다.
- 현재 감사는 반출·동의변경·관리자접근·역할변경. **인증/세션 이벤트 전용 writer 부재**.

---

## §5. WhyMath 특수 결정: 7계층 배치 + P0 재정의

### ① 7계층 내 Identity 배치

- 현재 `security.py:1` docstring은 "L5 인증 집행 계층"이라 명시. `privacy/__init__.py:3-6`은 횡단 인프라.
- 설계안 §68은 Modular Monolith 내 `auth/identity/session/consent/organization/` 모듈 분리를 권고.
- 결정 필요: Identity 모델을 L2(학습자 모델)에 넣을 것인가, L5(api)에 둘 것인가, 아니면 횡단 모듈로 둘 것인가? import-linter 계약(`api > l6 > l5 > l4 > l3 > l2 > l1 > schema`)을 어기지 않으려면:
  - Credential/Session = L5(인증 집행)
  - Person/Identity/Account/Relationship = L2 또는 별도 횡단(authorization context)
  - Authorization 평가 = L5/L6 경계
- 제안: `identity/`를 L5 아래의 별도 모듈이 아니라 **L2와 L5 사이의 횡단 Identity Context**로 두되, import-linter 예외를 명시. 또는 §68의 "논리적 분리"부터 시작.

### ② P0 재정의

설계안 §72의 P0 중 WhyMath 현재 정책과 맞지 않는 것을 조정.

- **P0 유지**: Identity/Account 분리(식별자 정책), Session/Access/Refresh Token, Logout/Logout All, Rate Limit, Account Status(기존 3상태), Student/Teacher/Parent 역할 모델, Guardian Relationship, Consent 연결, Authorization/Audit 연결.
- **P0 → P1/보류**: 비밀번호 로그인, 비밀번호 reset, 계정 잠금, 로그인 이력 수집.
- **P0 추가**: 이메일리스 학교 발급 계정(Invitation), OAuth PKCE, 모바일 Secure Storage, 휴면계정(DORMANT).

### ③ 현재 최우선

- 모바일 OAuth code 획득이 스텁(`oauth_code_requester.dart:34-47`)이므로, 설계안 §72의 어떤 인증 체계보다 먼저 **실제 로그인 플로우가 end-to-end로 작동**해야 한다.
- 다음: D8(계정 복구/이메일 변경)과 D9(동의 재확인) 집행 메커니즘.

---

## §6. 후속 과업 제안

아래 항목은 `backlog.py add` 경유(번호 추론 배지 말 것)해 등재할 후보다.

1. **Identity/Account/Person 분리 설계** — D8(이메일 변경 시 학습 이력 유실) 해결의 출발점. `email_hash` 단일 키에서 벗어나는 안전한 마이그레이션 설계.
2. **Relationship 모델 + 부모/교사/학교 관계** — `GUARDIAN_OF`, `TEACHER_OF`, `MEMBER_OF`. 데이터 접근권한의 근거가 되는 핵심.
3. **이메일리스 학교 발급 계정 가입/로그인** — Invitation/Provisioning 설계.
4. **OAuth PKCE + sender-constrained token(DPoP/mTLS) 도입** — RFC 9700 준수, 모바일 탈취 리스크 완화.
5. **인증/세션 이벤트 전용 감사 writer 추가** — §42 표준 이벤트 12종.
6. **휴면계정(DORMANT) 상태 및 파기 정책** — 정보통신망법 제29조.
7. **(재결정 트리거 시) 비밀번호/Passkey 전략 재판정** — 현재 OAuth 전용 정책과의 균형.

---

## §7. 결론

이 설계안은 일반적인 EOS Identity Platform 기획서로서 **정확하고 교육 도메인에 적합한 방향**이다. 특히 Relationship을 초기에 넣고, Identity/Account/Credential을 분리하라는 지점은 WhyMath가 장기적으로 재설계 없이 확장할 수 있는 토대가 된다.

그러나 WhyMath 현재 구현과 기존 봉인 결정을 무시하면, 이 설계안은 **P0로 과도한 범위를 요구**하고 **동결 테스트를 깨뜨리는** 위험이 있다. 따라서 이 문서는 다음 우선순위로 활용해야 한다.

1. **채택**: Identity/Account/Person 분리, Relationship 기반 인가, 이메일리스 학교 계정, Passkey/SSO 장기 후보.
2. **재결정 필요**: 비밀번호, 계정 잠금, 이메일 평문, 로그인 이력 수집.
3. **보강**: 정보통신망법(휴면계정), 본인확인기관, Flutter Secure Storage, PKCE/DPoP, JWKS, 인증 감사 이벤트.
4. **보류**: Risk Engine, SCIM, AI/Service Identity, Super Admin PAM — Phase 5 이후.

이 문서를 그대로 P0 설계서로 삼지 말고, **WhyMath의 봉인 결정과 기존 갭(D8·D9)을 먼저 반영한 병합안**으로 재구성할 것을 권고한다.
