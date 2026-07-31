# 보안·개인정보 표준

> **현행 실측 대조 (2026-07-30)**: 이 문서의 규정과 실제 구현의 격차는
> `docs/architecture/account_security_gap_review.md`가 전수 대조했다(§0 스냅샷·§1 crosswalk).
> 문서 규정과 코드가 어긋나는 절에는 **편집자 부기**로 실제 구현·정정 사유를 병기했다(원문은
> 이력 보존을 위해 삭제하지 않는다). 미상환 갭은 `SEC-07`~`SEC-12`·`MGMT-02`로 백로그 추적 중.

## 미성년자 특수 사항

### 14세 미만
- 부모 동의 *필수* (회원가입 + 매 분기 재확인)
- 부모 보고서 옵션 제공
- 채팅 데이터 *최소 수집*

### 14세 이상
- 본인 동의 (개인정보보호법)
- 데이터 사용 *명시적 통지*

## PII 분리 저장

> **⚠️ 편집자 부기 (2026-07-30 · `docs/architecture/account_security_gap_review.md` §4-④)**:
> 아래 3테이블 설계는 **폐기됐다**(원문은 이력 보존을 위해 남긴다). 실명·전화·이메일 평문을
> *애초에 수집하지 않는* 방향으로 우회했기 때문이다 — 분리 저장보다 **미수집**이 강한 보호다.
> **실제 구현**: ⑴ `UserProfile` 단일 테이블(닉네임·학년·`school_id`·`birth_year`) + PII 최소
> 수집 ⑵ 이메일은 **해시 키**로만 보관(OAuth upsert 키) ⑶ `parental_consent` 별도 테이블
> (`guardian_email_hash` — 평문 금지) ⑷ **암호화 대상은 프로필이 아니라 대화·손글씨·증거 3자산**
> (AES-256-GCM 봉투·SEC-01·`api/_crypto.py:285` fail-closed 부팅 게이트).
> `nickname`·`birth_year`·`school_*`를 암호화하지 **않는** 이유: 커리큘럼 정렬·진단의 쿼리
> 입력이라 암호화하면 조회가 불가능해진다(정직한 공백 §4-④).

```
[테이블 A: students]   ← 폐기된 설계 (아래 전체)
- id (anonymous UUID)
- nickname
- grade
- school_code

[테이블 B: student_pii] (암호화)
- student_id (FK)
- real_name_encrypted
- phone_encrypted
- email_encrypted
- parental_consent_id

[테이블 C: parental_consents]
- id
- consent_signed_at
- expires_at
- guardian_pii_encrypted
```

## 암호화

### 저장 (at rest)
- DB: PostgreSQL TDE 또는 column-level (pgcrypto)
- 파일: S3 server-side encryption
- 시크릿: HashiCorp Vault 또는 클라우드 KMS

### 전송 (in transit)
- HTTPS only
- TLS 1.3
- Certificate pinning (모바일)

## 인증

```python
# JWT + Refresh Token
ACCESS_TOKEN_TTL = timedelta(minutes=15)
REFRESH_TOKEN_TTL = timedelta(days=30)

# 학생: SSO (카카오·네이버·Apple)
# 부모: 별도 가입          ← 좌석 0 (아래 부기 참조)
# 교사: 학교 인증 (Phase 3+)  ← 좌석 0 (아래 부기 참조)
```

> **⚠️ 편집자 부기 (2026-07-30 · `account_security_gap_review.md` D1·§5-②)**: "부모 별도 가입"·
> "교사 학교 인증"은 **좌석이 0이다** — `UserProfile.role` 컬럼도, `Role` enum도 존재하지 않는다
> (실측: `db/models/`의 `role`은 `TurnRole`·`ConceptRole`로 둘 다 다른 축). 따라서 이 두 줄은
> *현행 규정*이 아니라 **미래 계획**으로 읽어야 한다.
> **Role v0(SEC-07) = 2값**: `STUDENT`(기본) · `CONTENT_ADMIN`. 좌석 없는 역할은 만들지 않는다
> (dead code 금지) — `PARENT`·`TEACHER`·`SCHOOL_ADMIN`은 Phase 3 대시보드·B2B 계약이 실체를 가질
> 때 연다(§5-②).
> **역할 추가 시 제약(협상 불가)**: 선형 서열(상위가 하위를 포함) 모델을 쓰지 않는다 —
> `docs/legal/pipa_data_matrix.md:33-47`에서 **부모 열은 학생 열의 부분집합**이다(오답 패턴·또래
> 비교·힌트 사용이 부모에게 ✕). 인가는 **2차원(역할 × 데이터 항목)** 매트릭스로만
> (`docs/design/ui/04_admin_console_architecture.md` §2 원칙 3-4).

> **구현 현황 (OAuth-a·a2·a3·a3b·a3c·c2·c2b·2026-06-15)**: JWT 발급/검증(`security.py`)·Bearer 의존성·미성년 동의
> 게이트(`api/_auth.py`)는 가동. **OAuth 로그인 콜백**(`api/auth.py`·`POST /v1/auth/{provider}/callback`
> — `OAuthProvider` Protocol → 사용자 upsert(이메일 해시 키·마이그레이션 0) → `create_access_token`)
> + **실 카카오/네이버 provider**(`api/oauth_providers.py`·httpx token→userinfo·`config.py` client
> id/secret env-only·`create_app` 기본 배선) 가동. ★**실 provider 외부 API 계약은 문서 기반 인코딩 —
> 라이브 크레덴셜로만 통합 검증 가능(로컬/CI 미검증)**, 배포 전 실 콘솔 검증 필요. **리프레시 토큰
> (OAuth-a3)** 가동: `create_refresh_token`/`decode_refresh_token`(`security.py`·`typ:refresh` 클레임·
> 후방호환) + `POST /v1/auth/refresh`. **서버측 취소(OAuth-a3b)** 가동: 발급 리프레시마다 `jti`를 실어
> `refresh_token_session` 행(PK=jti·allowlist)을 두고 `/refresh`가 존재·미취소 확인·`POST
> /v1/auth/logout`이 행을 취소(denylist)해 *만료 전 즉시 무효화*. **회전·재사용 탐지(OAuth-a3c)** 가동:
> `/refresh`가 매번 회전(기존 세션 취소+새 액세스/리프레시 반환)하고, 이미 취소된 토큰 재제출은 재사용
> 탐지로 사용자 전체 세션을 패닉 취소한다(탈취 대응). 세션 목록/관리(`GET·DELETE /v1/auth/sessions`)는
> 후속(a3d). refresh 30일 TTL(`jwt_refresh_expire_minutes`); access는 현재 24h 유지(15분 단축은
> 모바일 refresh-on-401 배선 후). **로그인 IP 레이트리밋은 후속**(OAuth-a4). **모바일(OAuth-b)**:
> `core/token_store.dart`(`TokenStore`·OS 보안 저장소
> `flutter_secure_storage`) + `core/auth_interceptor.dart`(dio Bearer 자동 첨부) + **인증 세션
> 로직(OAuth-c1)**(`features/auth/`·`AuthApi.login`→콜백 토큰 교환·`AuthController` 저장·로그아웃·
> 상태) + **로그인 화면(OAuth-c2)**(`features/auth/presentation/login_screen.dart`·카카오/네이버 버튼
> → `OAuthCodeRequester` seam으로 code 획득 → c1 토큰 교환 → 채팅 이동·실패 graceful) 가동. ★**실
> code 획득(webview/딥링크)은 미구현 seam**(`UnsupportedOAuthCodeRequester`·명확한 오류)이라 로그인은
> *아직 작동하지 않으며* 기본 흐름(온보딩→채팅)은 강제하지 않는다(`/login` 등록만·비파괴).
> + **세션 복원 + 라우트 가드(OAuth-c2b)**: `AuthController.restore()`(시작 시 보안 저장소 토큰으로
> 인증 복원·방어적—오류 시 미인증·앱 안 죽음) + `main.dart` runApp 전 복원(`UncontrolledProviderScope`)
> + `router.dart` **비파괴 redirect**(*복원된 인증* 세션만 온보딩/로그인→채팅·미인증은 현 흐름 유지)
> 가동. ★미인증→로그인 **강제** redirect·로그아웃 반영·세션 만료는 로그인이 실제 작동하는 c3로 연기
> (그 전에 강제하면 앱이 막힘). 실 webview/딥링크 code 획득·카카오/네이버 SDK·네이티브 설정=OAuth-c3.
>
> **⚠️ 후속 항목의 백로그 배치 (2026-07-30 부기)**: 위 자백 3건은 이제 태스크로 추적된다 —
> ⑴ 세션 목록/관리(a3d) → **`SEC-10`**(`_revoke_all_user_sessions`는 **함수만 있고 엔드포인트가
> 없다**·`api/auth.py:186`·소생 대상). ⑵ 로그인 IP 레이트리밋(a4) → **`SEC-08`**(인프라는 이미
> 있다 — `api/_rate_limit.py`의 `hit_by_ip`; 부착만 남음). ⑶ 액세스 24h → 15분 단축은 **클라
> refresh-on-401 배선(MOB) 선결** — 먼저 줄이면 학생이 15분마다 튕긴다(우선순위 1 침해).
> 추가 실측 갭: OAuth **`state`·PKCE·`redirect_uri` allowlist 0**(CSRF·open redirect) → `SEC-08`.
> **경계 주의**: `device_credential`(기기 자격증명·rate limit 신뢰용)은 **로그인 세션이 아니다** —
> 기기를 폐기해도 그 기기의 JWT는 만료까지 유효하다(`SEC-10`이 세션 축을 따로 세운다).

## 감사 로그

```python
# 감사 대상 3종 (아래 부기 — "모든 PII 접근"이 아니다)
class AuditLog:
    user_id: str        # FK 아님 — 계정 삭제 후에도 감사 잔존
    action: str         # 'export_data' | 'consent_change' | 'admin_access'
    target: str
    timestamp: datetime
    ip_hash: str        # sha256(salt+ip) — 평문 IP 저장 금지

# 보존: 5년 (개인정보보호법)
```

> **⚠️ 편집자 부기 — 규정 정정 (2026-07-30 · `account_security_gap_review.md` D3)**: 원문의
> "**모든** PII 접근 로그"는 **의도적으로 채택하지 않는다**. 본인 조회 경로(`/v1/me/*` 29
> 엔드포인트)를 전수 감사하면 **미성년 학생의 학습 조회 이력 자체가 프로파일링 자산**이 되어
> (언제·무엇을 몇 번 봤는가) 미성년자 보호 원칙과 역행하고, 볼륨도 소음이다. 규정을 그대로 남겨
> 두면 **영구 미달 상태**가 되므로 경계를 확정해 정정한다.
>
> **감사 대상 = 3종만** — "시스템 밖으로 나가는 사건"과 "본인 아닌 주체의 접근":
> ⑴ **데이터 반출**(`GET /v1/me/export`) ⑵ **동의 변경** ⑶ **관리자 접근**(SEC-07 착지 후).
>
> **구현 현황(SEC-09 착지 — 2026-07-30)**: 삭제 감사는 여전히 `deletion_audit`
> (`db/models/audit.py:32`·writer `api/me.py:291`·본인 조회 `GET /v1/me/deletions`)가 **단일
> 권위**다. 위 3종(반출·동의변경·관리자접근)은 **신규 테이블 `privacy_audit`**
> (`db/models/audit.py` `PrivacyAudit`·마이그레이션 `3702d8671074`)에 담고, 삭제 이벤트를
> 여기 중복 기록하지 **않는다**(이중 진실원천 금지 — 테이블명·`deleted_at` 컬럼이 삭제 의미에
> 결합되어 있어 반출 사건을 넣으면 스키마가 거짓말을 한다. 회귀 테스트
> `tests/backend/api/test_privacy_audit_integration.py::TestDeletionDoesNotWritePrivacyAudit`가
> 동결). 두 테이블 통합은 관리자 콘솔 Phase B에서 재론.
>
> writer 3곳(`whymath_backend/privacy/audit.py`): `record_export_audit`(`api/me.py:
> export_my_data` 호출·반출 payload 조립 *후*) · `record_consent_change_audit`(`api/users.py:
> grant_parental_consent` 호출·`parental_consent` 행 삽입과 **같은 트랜잭션**) · 
> `record_admin_access_audit`(**현재 호출부 0곳** — 관리자 콘솔 Phase B가 착지할 때 배선,
> `AuditEventKind.admin_access` docstring 참조 — 가짜 이벤트 날조 금지). 본인 조회
> (`GET /v1/me/*`, 이제 29개 — 신규 `GET /v1/me/privacy-audit` 자기 자신 포함) 경로는 **감사
> 0행**을 경계로 동결한다
> (`test_privacy_audit_integration.py::TestSelfScopedRoutesProduceZeroPrivacyAuditRows`).
>
> **필드 정정 2건**: ⑴ `ip_address` 평문 → **`sha256(salt+ip)` 해시만**(반복 판정 가능·원본 복원
> 불가·`privacy.audit.hash_client_ip`·salt는 `WHYMATH_PII_AUDIT_IP_SALT`) ⑵ 감사 행에 **반출
> 내용·본문·PII 값을 저장하지 않는다**(감사가 데이터 사본이 되면 최소화 위반). append-only
> (UPDATE/DELETE 라우터 없음)·`user_id`(행위자) FK 아님은 기존 `deletion_audit` 패턴 답습.
> `target_user_id`(행위 대상 — 관리자접근에서만 행위자와 다름)·`consent_scope`(동의변경 구분
> typed 메타)는 `deletion_audit`엔 없는 신규 컬럼.

## 삭제·이전 권리

```python
@router.delete("/account")
async def delete_account(...):
    """완전 삭제 (Right to be forgotten)"""
    # 1. PII 즉시 삭제
    # 2. 행동 데이터 30일 grace period
    # 3. 익명화된 통계만 보존
    # 4. 부모/보호자 통지

@router.get("/account/export")
async def export_my_data(...):
    """데이터 이전 가능 (개인정보보호법)"""
    # JSON 형식 export
```

## 침투 테스트

- Phase 1 종료 시 1회
- Phase 2+ 분기별 1회
- 사고 시 즉시

## 사고 대응

```
사고 발생 →
   ├─ 즉시: 영향 범위 파악·증거 보존
   ├─ 24시간: 영향 받은 사용자 통지
   ├─ 72시간: 개인정보보호위원회 신고
   └─ 사후: 재발 방지·감사
```

## 절대 금지

❌ 시크릿 코드 하드코딩
❌ PII 평문 저장
❌ 미성년자 데이터 *동의 없이* 학습용 활용
❌ 학교·학년 정보로 *개인 식별 가능* 분석 외부 노출
❌ 부모에게 *불필요한* 학생 PII 노출
❌ 로그에 PII 평문 기록

> **구현 현황(SEC-11 착지 — 2026-07-31)**: 위 두 항목(시크릿 하드코딩·로그 PII)은 이제
> 규정에서 그치지 않고 기계로 강제된다. `logging.Filter`(`ops/log_scrubber.py`
> `PiiSecretScrubberFilter`) + `LogRecord` 팩토리 배선(`app.py` `create_app()` — 자식 로거
> 전파 경로까지 포함)이 `sk-`/`pk-` API 키·`Bearer` 토큰·JWT·`WHYMATH_*_KEY/SECRET/SALT` 값·
> 이메일·전화번호·학생 발화 후보 필드(`student_text` 등)를 로그 렌더 시점에 마스킹한다.
> 예외 타입명(`type(exc).__name__`)은 마스킹 대상에서 제외(위 "침묵 실패 금지"와 충돌 방지).
> 시크릿 하드코딩은 `tests/backend/ops/test_secret_hardcoding_scan.py`가 `src/backend/
> whymath_backend/` 전수를 스캔해 회귀로 동결(`dev_constitution.md:193`의 "코드 테스트화는
> 남은 선택지" 상환). 배선 실재성은 `tests/backend/ops/test_log_scrubber_wiring.py`가 동결.
