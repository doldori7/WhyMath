"""dialogue 멀티모달 봉투 암호화 + 프로덕션 fail-closed — SEC-01 (hermetic).

`image_uri`(손글씨 URI)·`image_analysis`(Qwen3-VL 분석 JSONB)는 미성년 풀이 전사가 가능한
데이터인데 암호화 경로가 없었다. 이 테스트가 못 박는 것:

  ① **왕복** — 암호화 후 복호하면 원본이 그대로 돌아온다(JSONB는 직렬화 왕복 포함).
  ② **평문 컬럼이 비워진다** — 암호화 행에 원문이 남으면 암호화한 의미가 없다.
  ③ **fail-closed** — 프로덕션 추정 환경에서 키가 없으면 *조용한 평문 폴백* 대신 RuntimeError.
     **변별력**: 같은 키 부재라도 개발 환경이면 None(폴백 허용)으로 판정이 뒤집힌다.
  ④ **키 유실 시 시끄러운 실패** — 암호화 행인데 cipher가 없으면 빈 값이 아니라 예외.
"""

from __future__ import annotations

import base64
import os
from typing import Any

import pytest

from whymath_backend.api._crypto import (
    MultiKeyCipher,
    SecretCipher,
    encrypt_dialogue_image_analysis,
    encrypt_dialogue_image_uri,
    require_dialogue_content_cipher,
    resolve_dialogue_image_analysis,
    resolve_dialogue_image_uri,
)


def _cipher() -> MultiKeyCipher:
    return MultiKeyCipher(SecretCipher(os.urandom(32)))


class _FakeSecret:
    """`SecretStr` 흉내 — `get_secret_value()`만 있으면 빌더가 동작한다."""

    def __init__(self, value: str) -> None:
        self._value = value

    def get_secret_value(self) -> str:
        return self._value


class _FakeSettings:
    """빌더가 읽는 필드만 가진 최소 설정 — 실 `Settings` 구성 없이 분기를 시험한다."""

    def __init__(self, *, key: str = "", kakao: bool = False, naver: bool = False) -> None:
        self.dialogue_content_encryption_key = _FakeSecret(key)
        self.dialogue_content_decryption_fallback_keys = _FakeSecret("")
        self.kakao_configured = kakao
        self.naver_configured = naver


class TestImageUriEnvelope:
    def test_round_trip(self) -> None:
        cipher = _cipher()
        plain, encrypted, nonce = encrypt_dialogue_image_uri(cipher, "s3://bucket/hand.png")
        assert resolve_dialogue_image_uri(cipher, plain, encrypted, nonce) == "s3://bucket/hand.png"

    def test_plaintext_column_is_emptied(self) -> None:
        """암호화 행에 원문이 남으면 암호화한 의미가 없다."""
        plain, encrypted, nonce = encrypt_dialogue_image_uri(_cipher(), "s3://bucket/hand.png")
        assert plain is None
        assert encrypted is not None and nonce is not None

    def test_none_uri_produces_no_ciphertext(self) -> None:
        """이미지 없는 턴 — 암호화 대상 자체가 없다."""
        assert encrypt_dialogue_image_uri(_cipher(), None) == (None, None, None)

    def test_plaintext_fallback_without_cipher(self) -> None:
        """cipher 미설정이면 명시 평문 폴백(개발·CI 경로)."""
        assert encrypt_dialogue_image_uri(None, "s3://x") == ("s3://x", None, None)


class TestImageAnalysisEnvelope:
    def test_round_trip_preserves_structure(self) -> None:
        """JSONB는 직렬화를 거치므로 구조·한글이 그대로 돌아오는지 확인한다."""
        cipher = _cipher()
        analysis: dict[str, Any] = {
            "steps": [{"latex": "x^2+1", "confidence": 0.91}],
            "라벨": "손글씨",
            "nested": {"a": [1, 2, 3], "b": None},
        }
        plain, encrypted, nonce = encrypt_dialogue_image_analysis(cipher, analysis)
        assert plain is None
        assert resolve_dialogue_image_analysis(cipher, plain, encrypted, nonce) == analysis

    def test_serialization_is_deterministic(self) -> None:
        """같은 dict는 키 순서가 달라도 같은 평문이 된다(sort_keys) — 재현성."""
        cipher = _cipher()
        a = {"b": 1, "a": 2}
        b = {"a": 2, "b": 1}
        _, enc_a, nonce_a = encrypt_dialogue_image_analysis(cipher, a)
        _, enc_b, nonce_b = encrypt_dialogue_image_analysis(cipher, b)
        assert enc_a is not None and enc_b is not None
        # ciphertext는 nonce가 달라 다르지만, 복호 평문은 같아야 한다.
        assert resolve_dialogue_image_analysis(
            cipher, None, enc_a, nonce_a
        ) == resolve_dialogue_image_analysis(cipher, None, enc_b, nonce_b)

    def test_none_analysis_produces_no_ciphertext(self) -> None:
        assert encrypt_dialogue_image_analysis(_cipher(), None) == (None, None, None)

    def test_missing_cipher_on_encrypted_row_raises(self) -> None:
        """키 유실 — 조용한 빈 응답 대신 시끄러운 실패(운영자가 즉시 인지)."""
        cipher = _cipher()
        _, encrypted, nonce = encrypt_dialogue_image_analysis(cipher, {"x": 1})
        with pytest.raises(RuntimeError, match="복호 키가 미설정"):
            resolve_dialogue_image_analysis(None, None, encrypted, nonce)

    def test_non_dict_payload_is_integrity_error(self) -> None:
        """복호 결과가 dict가 아니면 조용히 None으로 삼키지 않는다."""
        cipher = _cipher()
        ciphertext, nonce = cipher.encrypt("[1, 2, 3]")  # 리스트 — dict 아님
        with pytest.raises(RuntimeError, match="dict가 아닙니다"):
            resolve_dialogue_image_analysis(cipher, None, ciphertext, nonce)


class TestProductionFailClosed:
    def test_raises_when_production_like_and_key_missing(self) -> None:
        """프로덕션 추정(실 OAuth provider 구성)인데 키가 없으면 거부한다.

        체크리스트는 사람이 기억해야 작동하지만 이 게이트는 잊어도 작동한다.
        """
        with pytest.raises(RuntimeError, match="프로덕션 추정 환경"):
            require_dialogue_content_cipher(_FakeSettings(key="", kakao=True))

    def test_naver_alone_also_triggers(self) -> None:
        """provider 둘 중 하나만 구성돼도 프로덕션 신호로 본다."""
        with pytest.raises(RuntimeError, match="프로덕션 추정 환경"):
            require_dialogue_content_cipher(_FakeSettings(key="", naver=True))

    def test_development_without_key_still_falls_back(self) -> None:
        """**변별력** — 같은 키 부재라도 개발 환경이면 None(폴백 허용)으로 판정이 뒤집힌다.

        위 두 테스트가 "항상 raise"라는 고장이 아님을 증명한다. 개발·CI를 막으면 아무도 못 돌린다.
        """
        assert require_dialogue_content_cipher(_FakeSettings(key="")) is None

    def test_production_with_key_returns_cipher(self) -> None:
        """키가 있으면 프로덕션에서도 정상 — 게이트는 *키 부재*만 막는다."""
        key = base64.b64encode(os.urandom(32)).decode()
        cipher = require_dialogue_content_cipher(_FakeSettings(key=key, kakao=True))
        assert cipher is not None
        ciphertext, nonce = cipher.encrypt("hello")
        assert cipher.decrypt(ciphertext, nonce) == "hello"
