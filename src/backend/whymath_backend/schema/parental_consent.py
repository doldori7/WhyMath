"""법정대리인 동의(ParentalConsent) Pydantic 스키마 — 14세 미만 동의 GRANT 감사 레코드.

PIPA 만14세 미만 법정대리인 동의(docs/legal/pipa_data_matrix.md §3·security_privacy.md
"14세 미만 부모 동의")의 *획득(GRANT)* 1건을 표현하는 append-only 감사 레코드. 동의 *게이트*
(`api/_auth.py.get_consented_user` 403)는 이미 있었으나 동의를 *받는* 경로가 없었다 — 이 스키마는
그 GRANT를 영속화하는 행의 검증·직렬화 표현이다. ORM(`db/models/parental_consent.py`)과 별도로
세운 검증 레이어이며 `to_schema`/`from_schema`가 잇는다(audit.py·user.py 동일 패턴).

**미성년 PII 보호(CLAUDE.md 절대 금기 "미성년자 개인정보 외부 공유 금지"·security_privacy.md
"PII 평문 저장 금지")**: 법정대리인 식별 정보는 *평문으로 담지 않는다* — 이메일은 sha256
해시(`guardian_email_hash`, 기존 `parent_email_hash`·`email_hash`와 동일 접근)로만 둔다. 이름·
연락처 같은 다른 PII는 *수집 자체를 하지 않는다*(데이터 최소화·§1). 신원 확인 *방식*과 그 외부
참조(`verification_ref`)는 PII가 아닌 *불투명 토큰*만 둔다(아래 필드 docstring).

**신원 확인 SEAM(법적 경계)**: `verification_method`는 동의를 검증한 *방식*의 이름이다(예:
"stub"). 실제 법정대리인 본인 확인 방식(휴대폰 본인인증·카드 등)의 법적 적정성은 **변호사 자문
필수**(§3.2·§5 체크리스트)라 *아직 구현하지 않는다* — 현재는 `StubGuardianVerifier`가
`method="stub"`을 기록할 뿐이며, 이 레코드는 "어떤 방식으로 검증했는가"를 *감사 가능하게* 남길
뿐 그 방식이 법적으로 충분하다고 단정하지 않는다(`consent_grant.py` 참조).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from whymath_backend.schema.enums import ConsentScope


class ParentalConsent(BaseModel):
    """14세 미만 법정대리인 동의 1건(GRANT 감사 레코드)의 단일 표현.

    `user_id`는 *동의의 대상 학생*(법정대리인이 *대신 동의한* 미성년 본인)이다. 한 학생이 여러
    번 동의(만료 후 재확인·범위 추가)하면 여러 행이 쌓이며(append-only), 게이트는 `user_profile.
    parent_consent_at`을 읽고 이 테이블은 *무엇을·언제·어떻게* 동의했는가의 감사 원천이 된다.
    """

    model_config = ConfigDict(
        # 추가 필드 금지 — Pydantic 모델이 스키마의 단일 진실(audit.py 패턴)
        extra="forbid",
        # enum 값 그대로 직렬화(consent_scope="service_core")
        use_enum_values=True,
        # 문자열 양끝 공백 제거
        str_strip_whitespace=True,
    )

    consent_id: uuid.UUID = Field(default_factory=uuid4, description="동의 레코드 PK(UUID)")
    user_id: uuid.UUID | None = Field(
        default=None,
        description="동의 대상 학생(법정대리인이 대신 동의한 미성년 본인) — user_profile FK",
    )
    guardian_email_hash: str | None = Field(
        default=None,
        max_length=64,
        description=(
            "법정대리인 이메일의 sha256 해시(64 hex·평문 미저장). 기존 parent_email_hash·"
            "email_hash와 동일 접근(CLAUDE.md 미성년 PII 평문 금지)."
        ),
    )
    verification_method: str | None = Field(
        default=None,
        max_length=32,
        description=(
            "동의를 검증한 방식의 이름(예: 'stub'). **법적 경계**: 실제 본인 확인 방식(휴대폰 "
            "인증·카드 등)은 변호사 자문 필수라 미구현 — 현재 StubGuardianVerifier가 'stub'만 "
            "기록(consent_grant.py). 이 필드는 *감사*용이며 방식의 법적 충분성을 단정하지 않는다."
        ),
    )
    verification_ref: str | None = Field(
        default=None,
        max_length=255,
        description=(
            "외부 검증 참조(불투명 토큰·PII 아님). 실 본인확인 연동 시 그 시스템의 거래 id 등을 "
            "담되 *개인 식별 정보는 절대 담지 않는다*. stub은 None(외부 거래 없음)."
        ),
    )
    consent_scope: ConsentScope | None = Field(
        default=None,
        description=(
            "동의 범위(무엇에 대한 동의인가). 현재 service_core(본 기능 이용)만 — 모델 학습·"
            "제3자 제공 등 별도 동의 범위는 변호사 자문 후 추가(가짜 범위 금지)."
        ),
    )
    consent_signed_at: datetime | None = Field(
        default=None,
        description="법정대리인이 동의를 완료한 시각(security_privacy.md parental_consents 필드).",
    )
    expires_at: datetime | None = Field(
        default=None,
        description=(
            "동의 만료 시각(재확인 주기). 적정 주기는 변호사 자문 필수(§3.1·§5) — None이면 "
            "만료 미설정(현재 stub 경로 기본). 게이트 만료 재차단 적용 여부는 후속."
        ),
    )
    revoked_at: datetime | None = Field(
        default=None,
        description="동의 철회 시각(철회 시 데이터 처리 절차는 변호사 자문 — §3.2). 미철회=None.",
    )
    created_at: datetime | None = Field(
        default=None,
        description="레코드 생성 시각(DB server_default now()).",
    )


class ParentalConsentGrantRequest(BaseModel):
    """`POST /v1/users/me/parental-consent` 요청 — 법정대리인 동의 제출.

    동의 *대상 학생*은 인증 세션(경로 `me`)에서 정해지므로 본문엔 학생 식별자를 받지 않는다.
    `guardian_email`은 식별·통지용이며 *평문으로 저장하지 않는다*(엔드포인트가 해시로 변환).
    실 본인확인 방식 도입 시 본인확인 토큰 등 *방식별 입력*이 여기 확장되나, 그 형식은 변호사
    자문으로 방식이 확정된 뒤 정한다(consent_grant.py — 지금 추측 필드 금지).
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    guardian_email: str = Field(
        min_length=1,
        description="법정대리인 이메일(식별·통지용 — 평문 미저장·서버가 해시로 변환).",
    )
    consent_scope: ConsentScope = Field(
        default=ConsentScope.service_core,
        description=(
            "동의 범위. 기본 service_core(본 기능 이용). 모델 학습·제3자 제공 등 별도 동의 "
            "범위는 변호사 자문 후 추가(가짜 범위 금지)."
        ),
    )


class ParentalConsentGrantResponse(BaseModel):
    """`POST /v1/users/me/parental-consent` 응답 — 동의 기록 결과.

    동의 PII(guardian_email_hash 등)는 응답에 싣지 않는다(불필요·미성년 보호). 게이트 통과의
    근거가 된 `parent_consent_at`(user_profile에 설정된 시각)과 기록된 동의 메타만 돌려준다.
    """

    model_config = ConfigDict(extra="forbid", use_enum_values=True)

    consent_id: uuid.UUID = Field(description="생성된 동의 레코드 PK.")
    consent_scope: ConsentScope = Field(description="기록된 동의 범위.")
    verification_method: str = Field(
        description="동의를 검증한 방식(예: 'stub' — 실 본인확인은 변호사 자문 후속)."
    )
    consent_signed_at: datetime = Field(description="동의 완료 시각.")
    parent_consent_at: datetime = Field(
        description="user_profile에 설정된 동의 시각(미성년 게이트 통과 근거)."
    )
