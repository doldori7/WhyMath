# 보안·개인정보 표준

## 미성년자 특수 사항

### 14세 미만
- 부모 동의 *필수* (회원가입 + 매 분기 재확인)
- 부모 보고서 옵션 제공
- 채팅 데이터 *최소 수집*

### 14세 이상
- 본인 동의 (개인정보보호법)
- 데이터 사용 *명시적 통지*

## PII 분리 저장

```
[테이블 A: students]
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
# 부모: 별도 가입
# 교사: 학교 인증 (Phase 3+)
```

> **구현 현황 (OAuth-a·a2·2026-06-14)**: JWT 발급/검증(`security.py`)·Bearer 의존성·미성년 동의
> 게이트(`api/_auth.py`)는 가동. **OAuth 로그인 콜백**(`api/auth.py`·`POST /v1/auth/{provider}/callback`
> — `OAuthProvider` Protocol → 사용자 upsert(이메일 해시 키·마이그레이션 0) → `create_access_token`)
> + **실 카카오/네이버 provider**(`api/oauth_providers.py`·httpx token→userinfo·`config.py` client
> id/secret env-only·`create_app` 기본 배선) 가동. ★**실 provider 외부 API 계약은 문서 기반 인코딩 —
> 라이브 크레덴셜로만 통합 검증 가능(로컬/CI 미검증)**, 배포 전 실 콘솔 검증 필요. **리프레시 토큰·
> 로그인 IP 레이트리밋은 후속**(OAuth-a3·a4). access 15분/refresh 30일 TTL은 리프레시 도입 시 적용
> (현재 access 기본 24h).

## 감사 로그

```python
# 모든 PII 접근 로그
class AuditLog:
    user_id: str
    action: str         # 'read_pii', 'export_data', ...
    target: str
    timestamp: datetime
    ip_address: str
    
# 보존: 5년 (개인정보보호법)
```

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
