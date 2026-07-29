"""검증 등급 — `verify` 계약의 **최소 확장**(S4-13 ③·신규 필드 1개).

정본: `docs/architecture/problem_bank_gap_review.md` §3 D7 — "'게이트 통과=완전 검증'이
아님을 코퍼스 메타에 명시(검증 등급 필드는 기존 `verify` 계약 확장·**신규 필드 최소**)".

**신규 필드는 정확히 하나**다 — 코퍼스 레코드의 `verify.verification_tier`. 표본공간 명세는
기존 `verify.conditions`에, 검산 종류는 기존 `verify.answer_kind`에 실으므로 추가 필드가
필요 없다. 등급 하나만으로 "무엇이 증명됐고 무엇이 안 됐는가"를 코퍼스가 스스로 말한다.

**왜 필요한가**: 기존 코퍼스의 `verify`는 *무엇으로* 검산됐는지 구분하지 않는다. 그래서
난수 표본 검산(`verify_answer` Tier1 — "샘플 점에서 조건 만족·증명 아님")과 유한 표본공간
전수 열거(`finite_probability` — 그 모델 위에서는 증명)가 코퍼스 상에서 **같은 색**이었다.
등급을 명시하면 하류 게이트가 "이 문항의 잔여 미검증 축이 무엇인가"를 기계로 알 수 있다.

등급은 **서열이 아니라 축의 명세**다. `MACHINE_EXHAUSTIVE`조차 *완전 검증이 아니다* —
발문이 그 형식 모델을 뜻하는지는 기계 밖이며, 그 잔여는 `cross_verify` + Wilson 표본 검수
게이트가 로트 단위로 본다. 어떤 등급도 단독으로 학생 노출 자격을 주지 않는다.

7계층: L3 지역. 순수 enum·매핑(의존 0).
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import Enum

__all__ = [
    "VERIFICATION_TIER_KEY",
    "UnknownVerificationTierError",
    "VerificationTier",
    "read_verification_tier",
    "stamp_verification_tier",
]

VERIFICATION_TIER_KEY = "verification_tier"
"""코퍼스 레코드의 `verify` 딕셔너리 안 키 이름(신규 필드·단 하나)."""


class VerificationTier(str, Enum):
    """수치 축이 *어떻게* 검산됐는가. 서술 축(발문↔형식모델 정합)은 어느 값에서도 미검증."""

    MACHINE_EXHAUSTIVE = "machine_exhaustive"
    """유한 표본공간을 **빠짐없이 열거**해 정확 유리수로 검산 — 그 형식 모델 위에서는 증명.

    미검증 잔여: 한국어 발문이 그 모델을 뜻하는지·등확률 가정의 타당성·조건 결측 여부.
    """

    MACHINE_SAMPLED = "machine_sampled"
    """난수 표본 점에서만 조건을 확인 — `verify_answer` Tier1의 등급(증명 아님).

    미검증 잔여: 표본 밖 구간 + 위 서술 축 전부. 유한 전수 게이트의 *범위 밖*이라
    `residue_cross_verify_eval`은 이 등급을 만나면 통과시키지 않고 명시적으로 거부한다.
    """


class UnknownVerificationTierError(ValueError):
    """미지 등급 값 — 조용히 무시하지 않고 오류로 드러낸다(침묵 실패 금지)."""


def read_verification_tier(verify: Mapping[str, object]) -> VerificationTier | None:
    """코퍼스 레코드의 `verify`에서 등급을 읽는다. 키 부재는 None(등급 미명시).

    값이 있으나 미지 문자열이면 `UnknownVerificationTierError` — 신설 등급이 조용히
    "미명시"로 강등돼 게이트를 통과하는 경로를 막는다.
    """
    raw = verify.get(VERIFICATION_TIER_KEY)
    if raw is None:
        return None
    if isinstance(raw, VerificationTier):
        return raw
    if not isinstance(raw, str):
        raise UnknownVerificationTierError(f"{VERIFICATION_TIER_KEY}는 문자열이어야 함: {raw!r}")
    try:
        return VerificationTier(raw)
    except ValueError as exc:
        raise UnknownVerificationTierError(f"미지 검증 등급: {raw!r}") from exc


def stamp_verification_tier(record: dict[str, object], tier: VerificationTier) -> dict[str, object]:
    """코퍼스 레코드 JSON의 `verify`에 등급을 찍는다(원본 불변·얕은 사본 반환).

    `verify` 절이 없거나 딕셔너리가 아니면 `ValueError` — 등급만 떠 있는 레코드를 만들지
    않는다(등급은 검산 재료와 한 몸이어야 의미가 있다).
    """
    verify = record.get("verify")
    if not isinstance(verify, dict):
        raise ValueError("verify 절이 없는 레코드에는 검증 등급을 찍을 수 없음")
    stamped = dict(record)
    stamped["verify"] = {**verify, VERIFICATION_TIER_KEY: tier.value}
    return stamped
