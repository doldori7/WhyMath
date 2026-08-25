"""디바이스 secret 봉투 암호화 단위테스트 — AES-256-GCM (slice 72, hermetic).

프리미티브(`SecretCipher`)와 팩토리(`build_secret_cipher`)를 격리 검증한다 — round-trip·
nonce 유일성·변조 탐지(GCM 인증)·잘못된 키/길이·키 미설정 비활성.
"""

from __future__ import annotations

import base64
import os

import pytest
from cryptography.exceptions import InvalidTag
from pydantic import SecretStr

from whymath_backend.api._crypto import (
    MultiKeyCipher,
    SecretCipher,
    build_dialogue_content_cipher,
    build_secret_cipher,
    encrypt_dialogue_content,
    encrypt_secret_for_storage,
    require_device_secret_cipher,
    resolve_dialogue_content,
    resolve_stored_secret,
)
from whymath_backend.config import Settings

_KEY = os.urandom(32)
_SECRET = "integration-jwt-secret-0123456789abcdef"


def _settings(enc_key_b64: str = "", fallback_keys_b64: str = "") -> Settings:
    return Settings(
        jwt_secret_key=SecretStr(_SECRET),
        device_secret_encryption_key=SecretStr(enc_key_b64),
        device_secret_decryption_fallback_keys=SecretStr(fallback_keys_b64),
    )


def _dialogue_settings(enc_key_b64: str = "", fallback_keys_b64: str = "") -> Settings:
    return Settings(
        jwt_secret_key=SecretStr(_SECRET),
        dialogue_content_encryption_key=SecretStr(enc_key_b64),
        dialogue_content_decryption_fallback_keys=SecretStr(fallback_keys_b64),
    )


class TestSecretCipher:
    def test_round_trip(self) -> None:
        """encrypt → decrypt가 원본 평문 복원."""
        cipher = SecretCipher(_KEY)
        ct, nonce = cipher.encrypt("s3cr3t-token-xyz")
        assert cipher.decrypt(ct, nonce) == "s3cr3t-token-xyz"

    def test_round_trip_non_ascii(self) -> None:
        """비-ASCII(한글·이모지)도 utf-8 round-trip."""
        cipher = SecretCipher(_KEY)
        secret = "비밀토큰🔐áé"
        ct, nonce = cipher.encrypt(secret)
        assert cipher.decrypt(ct, nonce) == secret

    def test_nonce_unique_per_encrypt(self) -> None:
        """같은 평문도 매 encrypt가 새 nonce·다른 ciphertext(결정론 노출 차단)."""
        cipher = SecretCipher(_KEY)
        ct1, n1 = cipher.encrypt("same")
        ct2, n2 = cipher.encrypt("same")
        assert n1 != n2
        assert ct1 != ct2
        # 그래도 둘 다 같은 평문으로 복호
        assert cipher.decrypt(ct1, n1) == cipher.decrypt(ct2, n2) == "same"

    def test_tamper_detected(self) -> None:
        """ciphertext 1바이트 변조 → 복호가 InvalidTag(조용한 비트플립 차단)."""
        cipher = SecretCipher(_KEY)
        ct, nonce = cipher.encrypt("token")
        tampered = bytes([ct[0] ^ 0x01]) + ct[1:]
        with pytest.raises(InvalidTag):
            cipher.decrypt(tampered, nonce)

    def test_wrong_key_fails(self) -> None:
        """다른 키로는 복호 불가(InvalidTag) — DB dump만으로 복호 불가의 근거."""
        ct, nonce = SecretCipher(_KEY).encrypt("token")
        with pytest.raises(InvalidTag):
            SecretCipher(os.urandom(32)).decrypt(ct, nonce)

    def test_wrong_nonce_fails(self) -> None:
        """nonce 불일치 → 복호 실패."""
        cipher = SecretCipher(_KEY)
        ct, _nonce = cipher.encrypt("token")
        with pytest.raises(InvalidTag):
            cipher.decrypt(ct, os.urandom(12))

    def test_invalid_key_length_rejected(self) -> None:
        """32바이트 아닌 키는 ValueError(부팅 fail-fast 근거)."""
        with pytest.raises(ValueError, match="32바이트"):
            SecretCipher(os.urandom(16))


class TestBuildSecretCipher:
    def test_none_when_key_unset(self) -> None:
        """키 미설정(빈 문자열)이면 None — 암호화 비활성(평문 폴백)."""
        assert build_secret_cipher(_settings("")) is None

    def test_cipher_when_key_set(self) -> None:
        """base64 32바이트 키 설정 시 SecretCipher 반환·round-trip 동작."""
        key_b64 = base64.b64encode(os.urandom(32)).decode()
        cipher = build_secret_cipher(_settings(key_b64))
        assert cipher is not None
        ct, nonce = cipher.encrypt("token")
        assert cipher.decrypt(ct, nonce) == "token"

    def test_invalid_length_key_raises(self) -> None:
        """base64 디코딩 후 길이가 32가 아니면 ValueError(설정 오류 fail-fast)."""
        bad_b64 = base64.b64encode(os.urandom(16)).decode()
        with pytest.raises(ValueError, match="32바이트"):
            build_secret_cipher(_settings(bad_b64))

    def test_fallback_keys_enable_rotation(self) -> None:
        """slice 75: primary로 암호화한 행을, 키 회전 후(구 키=fallback) 복호 가능."""
        old_b64 = base64.b64encode(os.urandom(32)).decode()
        new_b64 = base64.b64encode(os.urandom(32)).decode()
        # 회전 전: 구 키가 primary
        old_cipher = build_secret_cipher(_settings(old_b64))
        assert old_cipher is not None
        ct, nonce = old_cipher.encrypt("tok")
        # 회전 후: 새 키 primary·구 키 fallback → 구 키 암호문 복호 OK
        rotated = build_secret_cipher(_settings(new_b64, old_b64))
        assert rotated is not None
        assert rotated.decrypt(ct, nonce) == "tok"
        # 새 암호화는 새 키 사용(구 키 단독으로는 복호 불가)
        ct2, nonce2 = rotated.encrypt("tok2")
        with pytest.raises(InvalidTag):
            old_cipher.decrypt(ct2, nonce2)

    def test_fallback_keys_parsing_ignores_blanks(self) -> None:
        """쉼표 구분·공백·빈 토큰 무시하고 fallback 키 파싱."""
        primary_b64 = base64.b64encode(os.urandom(32)).decode()
        f1, f2 = (base64.b64encode(os.urandom(32)).decode() for _ in range(2))
        cipher = build_secret_cipher(_settings(primary_b64, f" {f1} , , {f2} "))
        assert cipher is not None
        # f1로 암호화한 값을 cipher가 복호(f1이 fallback에 포함됨)
        f1_cipher = SecretCipher(base64.b64decode(f1))
        ct, nonce = f1_cipher.encrypt("via-f1")
        assert cipher.decrypt(ct, nonce) == "via-f1"


class TestMultiKeyCipher:
    """slice 75: 키 회전 — primary 암호화·primary+fallbacks 복호."""

    def test_round_trip_primary_only(self) -> None:
        cipher = MultiKeyCipher(SecretCipher(_KEY))
        ct, nonce = cipher.encrypt("tok")
        assert cipher.decrypt(ct, nonce) == "tok"

    def test_decrypts_fallback_ciphertext(self) -> None:
        """구 키(fallback)로 암호화된 값을 복호(lockout 없음)."""
        old = SecretCipher(os.urandom(32))
        new = SecretCipher(os.urandom(32))
        ct, nonce = old.encrypt("legacy")
        cipher = MultiKeyCipher(new, [old])
        assert cipher.decrypt(ct, nonce) == "legacy"

    def test_encrypt_always_uses_primary(self) -> None:
        """encrypt는 항상 primary — fallback 단독으로는 새 암호문 복호 불가."""
        old = SecretCipher(os.urandom(32))
        new = SecretCipher(os.urandom(32))
        cipher = MultiKeyCipher(new, [old])
        ct, nonce = cipher.encrypt("fresh")
        assert new.decrypt(ct, nonce) == "fresh"
        with pytest.raises(InvalidTag):
            old.decrypt(ct, nonce)

    def test_no_matching_key_raises(self) -> None:
        """primary·fallback 어느 키로도 복호 못 하면 InvalidTag."""
        ct, nonce = SecretCipher(os.urandom(32)).encrypt("x")
        cipher = MultiKeyCipher(SecretCipher(os.urandom(32)), [SecretCipher(os.urandom(32))])
        with pytest.raises(InvalidTag):
            cipher.decrypt(ct, nonce)


class TestStorageHelpers:
    """slice 73: register/verify의 저장 표현 결정·복원 헬퍼(DB 무관·순수)."""

    def test_encrypt_for_storage_with_cipher(self) -> None:
        """cipher 있으면 (None, ciphertext, nonce) — 평문 컬럼 비움."""
        cipher = SecretCipher(_KEY)
        plain, enc, nonce = encrypt_secret_for_storage(cipher, "tok")
        assert plain is None
        assert enc is not None and nonce is not None
        # 복호하면 원본
        assert cipher.decrypt(enc, nonce) == "tok"

    def test_encrypt_for_storage_without_cipher_explicit_fallback(self) -> None:
        """cipher None이면 (secret_plain, None, None) — 평문 폴백."""
        assert encrypt_secret_for_storage(None, "tok", allow_plaintext_fallback=True) == (
            "tok",
            None,
            None,
        )

    def test_encrypt_for_storage_without_cipher_fail_closed(self) -> None:
        """cipher None이면서 평문 폰백 미허용 시 RuntimeError(SEC-28 fail-closed)."""
        with pytest.raises(RuntimeError, match="device secret"):
            encrypt_secret_for_storage(None, "tok")

    def test_resolve_encrypted_round_trip(self) -> None:
        """암호화 저장 → resolve가 복호해 원본 secret 복원(register→verify 경로)."""
        cipher = SecretCipher(_KEY)
        _plain, enc, nonce = encrypt_secret_for_storage(cipher, "tok")
        assert resolve_stored_secret(cipher, None, enc, nonce) == "tok"

    def test_resolve_plaintext_fallback(self) -> None:
        """평문 행(secret_plain만)은 cipher 유무와 무관하게 그대로 반환(하위 호환)."""
        assert resolve_stored_secret(None, "tok", None, None) == "tok"
        assert resolve_stored_secret(SecretCipher(_KEY), "tok", None, None) == "tok"

    def test_resolve_encrypted_without_cipher_raises(self) -> None:
        """암호화 행인데 cipher 미설정 → RuntimeError(조용한 401 lockout 대신 시끄러운 실패)."""
        cipher = SecretCipher(_KEY)
        _plain, enc, nonce = encrypt_secret_for_storage(cipher, "tok")
        with pytest.raises(RuntimeError, match="복호 키"):
            resolve_stored_secret(None, None, enc, nonce)

    def test_resolve_no_secret_raises(self) -> None:
        """평문·암호화 둘 다 없으면 데이터 무결성 오류(RuntimeError)."""
        with pytest.raises(RuntimeError, match="무결성"):
            resolve_stored_secret(SecretCipher(_KEY), None, None, None)


class TestRequireDeviceSecretCipher:
    """SEC-28: device secret cipher — prod-like 환경에서 키 미설정 시 부팅 거부."""

    def test_dev_without_key_returns_none(self) -> None:
        """개발/CI 환경(kakao/naver 미구성)에서 키 없으면 None(평문 폰백 허용)."""
        assert require_device_secret_cipher(_settings("")) is None

    def test_prod_without_key_raises(self) -> None:
        """prod-like(kakao/naver 중 하나 구성) 환경에서 키 없으면 RuntimeError."""
        dev_settings = _settings("")
        # Settings 인스턴스에 직접 OAuth provider 속성을 주입해 is_production_like를 True로.
        dev_settings.kakao_client_id = "real-kakao-id"
        with pytest.raises(RuntimeError, match="device secret"):
            require_device_secret_cipher(dev_settings)

    def test_with_key_returns_cipher(self) -> None:
        """키가 설정되면 cipher 반환 — prod/dev 구분 없음."""
        key_b64 = base64.b64encode(os.urandom(32)).decode()
        cipher = require_device_secret_cipher(_settings(key_b64))
        assert cipher is not None


class TestBuildDialogueContentCipher:
    """감사상환 #2: 대화 본문 전용 cipher 빌더 — device 키와 *분리*된 키 소스."""

    def test_none_when_key_unset(self) -> None:
        """키 미설정(빈 문자열)이면 None — 평문 폴백(CI·기존 배포 무영향·점진 도입)."""
        assert build_dialogue_content_cipher(_dialogue_settings("")) is None

    def test_cipher_when_key_set(self) -> None:
        """base64 32바이트 키 설정 시 round-trip 동작."""
        key_b64 = base64.b64encode(os.urandom(32)).decode()
        cipher = build_dialogue_content_cipher(_dialogue_settings(key_b64))
        assert cipher is not None
        ct, nonce = cipher.encrypt("본문")
        assert cipher.decrypt(ct, nonce) == "본문"

    def test_key_source_separated_from_device(self) -> None:
        """대화 본문 키와 device secret 키는 *분리* — device 키만 설정해도 대화 cipher는 None."""
        device_only = Settings(
            jwt_secret_key=SecretStr(_SECRET),
            device_secret_encryption_key=SecretStr(base64.b64encode(os.urandom(32)).decode()),
        )
        assert build_dialogue_content_cipher(device_only) is None
        # 역방향도: 대화 키만 설정 시 device cipher는 None
        dialogue_only = _dialogue_settings(base64.b64encode(os.urandom(32)).decode())
        assert build_secret_cipher(dialogue_only) is None
        assert build_dialogue_content_cipher(dialogue_only) is not None

    def test_fallback_keys_enable_rotation(self) -> None:
        """대화 본문 키 회전 — 구 키(fallback)로 암호화한 행을 새 키 primary에서 복호."""
        old_b64 = base64.b64encode(os.urandom(32)).decode()
        new_b64 = base64.b64encode(os.urandom(32)).decode()
        old_cipher = build_dialogue_content_cipher(_dialogue_settings(old_b64))
        assert old_cipher is not None
        ct, nonce = old_cipher.encrypt("legacy-본문")
        rotated = build_dialogue_content_cipher(_dialogue_settings(new_b64, old_b64))
        assert rotated is not None
        assert rotated.decrypt(ct, nonce) == "legacy-본문"


class TestEncryptDialogueContent:
    """감사상환 #2: 대화 본문 저장 표현 결정(nullable content 분기 포함)."""

    def test_with_cipher(self) -> None:
        """cipher 있으면 (None, ciphertext, nonce) — 평문 컬럼 비움."""
        cipher = SecretCipher(_KEY)
        plain, enc, nonce = encrypt_dialogue_content(cipher, "학생 풀이 본문")
        assert plain is None
        assert enc is not None and nonce is not None
        assert cipher.decrypt(enc, nonce) == "학생 풀이 본문"

    def test_without_cipher_plaintext_fallback(self) -> None:
        """cipher None이면 (content, None, None) — 평문 폴백(명시적)."""
        assert encrypt_dialogue_content(None, "본문") == ("본문", None, None)

    def test_none_content_yields_all_none(self) -> None:
        """content None(본문 없는 턴)이면 (None, None, None) — 암호화 대상 없음."""
        assert encrypt_dialogue_content(SecretCipher(_KEY), None) == (None, None, None)
        assert encrypt_dialogue_content(None, None) == (None, None, None)


class TestResolveDialogueContent:
    """감사상환 #2: 대화 본문 노출 직전 복호(nullable content — None 허용, 무결성 raise 없음)."""

    def test_encrypted_round_trip(self) -> None:
        """암호화 저장 → resolve가 복호해 원문 복원."""
        cipher = SecretCipher(_KEY)
        _plain, enc, nonce = encrypt_dialogue_content(cipher, "복호대상")
        assert resolve_dialogue_content(cipher, None, enc, nonce) == "복호대상"

    def test_plaintext_fallback(self) -> None:
        """평문 행(content만)은 cipher 유무와 무관하게 그대로 반환(하위 호환)."""
        assert resolve_dialogue_content(None, "평문본문", None, None) == "평문본문"
        assert resolve_dialogue_content(SecretCipher(_KEY), "평문본문", None, None) == "평문본문"

    def test_none_content_returns_none(self) -> None:
        """평문·암호문 둘 다 None(본문 없는 턴)이면 None 반환 — device와 달리 raise 없음."""
        assert resolve_dialogue_content(SecretCipher(_KEY), None, None, None) is None
        assert resolve_dialogue_content(None, None, None, None) is None

    def test_encrypted_without_cipher_raises(self) -> None:
        """암호화 행인데 cipher 미설정 → RuntimeError(조용한 평문 유출 금지·시끄러운 실패)."""
        cipher = SecretCipher(_KEY)
        _plain, enc, nonce = encrypt_dialogue_content(cipher, "본문")
        with pytest.raises(RuntimeError, match="복호 키"):
            resolve_dialogue_content(None, None, enc, nonce)

    def test_key_loss_wrong_key_raises_invalid_tag(self) -> None:
        """키 유실(다른 키) → InvalidTag(조용한 넘어감 금지)."""
        _plain, enc, nonce = encrypt_dialogue_content(SecretCipher(_KEY), "본문")
        with pytest.raises(InvalidTag):
            resolve_dialogue_content(SecretCipher(os.urandom(32)), None, enc, nonce)
