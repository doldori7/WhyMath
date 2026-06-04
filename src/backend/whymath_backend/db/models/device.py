"""디바이스 자격증명 영속 ORM — 슬라이스 23 `PgDeviceStore` 백킹 테이블.

OAuth-style 등록의 영속 표면(슬라이스 22 인메모리 → 23 PG-backed). `register`는 새 행 INSERT,
`verify`는 PK lookup + secret 재계산, `revoke`는 `revoked=true` UPDATE. 본 모델은 *서버 내부*
크리덴셜 테이블이라 `schema/`(Pydantic) 상응물이 없다(register 응답은 라우터가 즉시 dict 조립
— 분리 schema가 secret_plain을 한 번이라도 더 거치는 표면을 만들지 않는다).

설계 결정:
- **PK는 device_id(VARCHAR)**: 슬라이스 22의 `register`가 `str(uuid.uuid4())`로 발급해 외부
  계약이 *문자열 토큰*이다(UUID native로 좁히면 다른 형식의 device_id 발급 옵션을 봉쇄). 길이
  64는 UUID4 36자 + 미래 호환 버퍼.
- **user_id FK → user_profile.user_id**: 폐기 시 본인 소유 검증·관리자 조회를 위한 참조 무결성
  (CASCADE는 적용 안 함 — 사용자 삭제 시 device row는 명시적으로 처리. 후속 GDPR 슬라이스).
- **secret_plain은 평면 VARCHAR**: KDF 불능(`_device_store.py` 모듈 docstring 참조). KMS envelope는
  후속(`secret_encrypted bytea + nonce bytea`로 컬럼 추가하는 마이그레이션 + verify 분기).
- **revoked 인덱스 미포함**: 매 verify가 PK lookup이고 revoke는 드물어 보조 인덱스 불필요.
  user_id 인덱스는 `list_for_user`(관리자 표면 후속) 성능을 위해 미리 둔다.
- **created_at NOT NULL**: 등록 시각 추적(보안 감사·디바이스 수명 분석). revoked_at은 nullable
  (미폐기는 NULL).
"""

from __future__ import annotations

import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from whymath_backend.db.base import Base


class DeviceCredential(Base):
    """디바이스 자격증명 영속 — `PgDeviceStore.register/verify/revoke`의 백킹 행.

    secret_plain은 *서명 검증을 위해* 평문 저장(KDF 불능). DB 접근권자가 노출 위협의
    1차 경계 — KMS envelope으로 정식 분리는 후속(`_device_store.py` 모듈 docstring).
    """

    __tablename__ = "device_credential"

    # PK = device_id(서버 생성 UUID4 문자열). VARCHAR(64) — UUID 36 + 버퍼.
    device_id: Mapped[str] = mapped_column(sa.String(length=64), primary_key=True)
    # user_profile.user_id FK — 본인 소유 검증·관리자 조회용. CASCADE 미적용.
    user_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid, sa.ForeignKey("user_profile.user_id"), nullable=False, index=True
    )
    # HMAC 재계산에 원본 필요(KDF 불능). KMS envelope는 후속.
    secret_plain: Mapped[str] = mapped_column(sa.String(length=128), nullable=False)
    # 폐기 플래그 — verify는 revoked=True면 False 반환. revoke는 idempotent.
    revoked: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, server_default=sa.text("false")
    )
    # 등록 시각 — 보안 감사·디바이스 수명 분석.
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    # 폐기 시각 — 미폐기는 NULL. revoke 시 server-side는 안 두고 store 코드가 채운다(현재 시각).
    revoked_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    # slice 32: 마지막 verify 성공 시각 — "30일 미사용 자동 폐기" 정책·보안 이상 탐지 기반.
    # CachedDeviceStore 사용 시 *cache miss*에서만 갱신되므로 정밀도는 cache TTL(기본 60s).
    last_used_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    # slice 63: 등록 순번(DB 단조 증가·IDENTITY) — list_for_user 동률(같은 created_at/
    # last_used_at) 2차 정렬키. InMemoryDeviceStore.seq(slice 54)와 parity. SELECT엔 미노출
    # (ORDER BY 전용·DeviceInfo에 없음). INSERT 시 DB가 자동 할당(register는 미지정).
    seq: Mapped[int] = mapped_column(sa.BigInteger, sa.Identity(), nullable=False)


__all__ = ["DeviceCredential"]
