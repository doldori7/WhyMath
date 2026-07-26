"""미성년 대화 본문 봉투 암호화 결선 단위테스트 — coach 헬퍼·ORM seam (감사상환 #2, hermetic).

`_build_dialogue_turn`(4개 write 경로의 단일 캡슐)·`DialogueTurn.to_schema`(ciphertext 컬럼
제외)를 DB 없이 격리 검증한다. 왕복(암호화→복호)·키 미설정 평문 폴백·본문 없는 턴 분기.
"""

from __future__ import annotations

import os
import uuid

from whymath_backend.api._crypto import SecretCipher, resolve_dialogue_content
from whymath_backend.api.coach import _build_dialogue_turn
from whymath_backend.db.models.dialogue import DialogueTurn as DialogueTurnORM
from whymath_backend.schema.dialogue import DialogueTurn as DialogueTurnSchema
from whymath_backend.schema.enums import ContentType, TurnRole

_KEY = os.urandom(32)


def _schema(content: str | None = "학생 원문 (a+b)²=a²+b²") -> DialogueTurnSchema:
    return DialogueTurnSchema(
        dialogue_id=uuid.uuid4(),
        turn_order=1,
        role=TurnRole.student,
        content=content,
        content_type=ContentType.텍스트,
    )


class TestBuildDialogueTurn:
    """coach `_build_dialogue_turn` — 4개 write 경로가 공유하는 암호화 캡슐."""

    def test_with_cipher_encrypts_and_nulls_plaintext(self) -> None:
        """cipher 있으면 content=NULL·content_encrypted/nonce 세팅(평문 원문 DB 부재)."""
        cipher = SecretCipher(_KEY)
        turn = _build_dialogue_turn(_schema(), cipher)
        assert turn.content is None  # 프라이버시 단언: 평문 원문 부재
        assert isinstance(turn.content_encrypted, bytes)
        assert isinstance(turn.content_nonce, bytes)
        # 복호하면 원문
        decrypted = cipher.decrypt(turn.content_encrypted, turn.content_nonce)
        assert decrypted == "학생 원문 (a+b)²=a²+b²"

    def test_without_cipher_plaintext_fallback(self) -> None:
        """cipher None(키 미설정)이면 평문 폴백 — content=평문·encrypted=None."""
        turn = _build_dialogue_turn(_schema(), None)
        assert turn.content == "학생 원문 (a+b)²=a²+b²"
        assert turn.content_encrypted is None
        assert turn.content_nonce is None

    def test_round_trip_via_resolve(self) -> None:
        """write 헬퍼 저장표현 → resolve_dialogue_content 복호가 원문 복원(read 경로 정합)."""
        cipher = SecretCipher(_KEY)
        turn = _build_dialogue_turn(_schema("복호 왕복 본문"), cipher)
        restored = resolve_dialogue_content(
            cipher, turn.content, turn.content_encrypted, turn.content_nonce
        )
        assert restored == "복호 왕복 본문"

    def test_none_content_no_ciphertext(self) -> None:
        """본문 없는 턴(content None)은 암호화 대상 없음 — 세 컬럼 모두 None."""
        cipher = SecretCipher(_KEY)
        turn = _build_dialogue_turn(_schema(content=None), cipher)
        assert turn.content is None
        assert turn.content_encrypted is None
        assert turn.content_nonce is None


class TestToSchemaExcludesCiphertext:
    """ORM→schema seam이 봉투 암호화 컬럼을 제외(schema extra='forbid'·ciphertext 비노출)."""

    def test_to_schema_drops_encryption_columns(self) -> None:
        """content_encrypted/content_nonce 세팅된 ORM도 to_schema가 실패 없이 복원(제외)."""
        cipher = SecretCipher(_KEY)
        turn = _build_dialogue_turn(_schema("암호화 행"), cipher)
        schema = turn.to_schema()  # extra='forbid'라 ciphertext가 새면 여기서 예외
        # content는 NULL(암호화 행) — 복호는 handler 층 책임(schema엔 ciphertext 없음)
        assert schema.content is None
        assert not hasattr(schema, "content_encrypted")
        assert schema.turn_order == 1

    def test_non_schema_columns_constant(self) -> None:
        """제외 컬럼 상수가 암호화 세 축(content·image_uri·image_analysis)의 짝을 정확히 포함.

        SEC-01에서 이미지 두 축이 추가됐다. 새 ciphertext 컬럼을 여기 빠뜨리면 `to_schema()`가
        schema `extra='forbid'`에 걸려 터지거나(즉시 발각) 더 나쁘게는 ciphertext가 응답·export에
        새므로, 상수를 목록으로 동결한다.
        """
        assert DialogueTurnORM._NON_SCHEMA_COLUMNS == frozenset(
            {
                "content_encrypted",
                "content_nonce",
                "image_uri_encrypted",
                "image_uri_nonce",
                "image_analysis_encrypted",
                "image_analysis_nonce",
            }
        )
