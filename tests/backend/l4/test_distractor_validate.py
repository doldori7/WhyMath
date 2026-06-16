"""L4 distractor_map 참조 무결성 검증 단위테스트(P3b) — 카탈로그 대조.

검증: ① 미등록 misconception_id 거부, ② 미등록 op_code 거부, ③ op_code↔misconception_id
불일치 거부, ④ 정합 매핑 통과(빈 오류), ⑤ op_code 미지정 시 오개념만 검사, ⑥ 여러 위반
모아 보고, ⑦ raise 변형(fail-loud 게이트). 라이브 의존 0.

레이어(CLAUDE.md): 이 검증자는 L1 `DistractorEntry`를 import하고(L4→L1 허용) L4 카탈로그를
대조한다 — 구조(choice_index≥0 등)는 L1이 이미 보장하므로 참조 무결성만 본다.
"""

from __future__ import annotations

import pytest

from whymath_backend.l4.misconception.catalog import CATALOG_BY_ID
from whymath_backend.l4.misconception.distractor import DISTRACTOR_BY_ID
from whymath_backend.l4.misconception.validate import (
    raise_for_distractor_map,
    validate_distractor_map,
)
from whymath_backend.schema.problem import DistractorEntry

# 시드에 실재하는 정합 쌍(op_code → 그 op-code가 가리키는 misconception_id).
_VALID_OP = "power-distributed-no-cross-term"
_VALID_MIS = "distribution-over-power"


def _assert_seed_invariants() -> None:
    """전제: 테스트가 가리키는 시드 키들이 실제 카탈로그에 존재(테스트 자체 무결성)."""
    assert _VALID_MIS in CATALOG_BY_ID
    assert _VALID_OP in DISTRACTOR_BY_ID
    assert DISTRACTOR_BY_ID[_VALID_OP].misconception_id == _VALID_MIS


class TestValidateDistractorMap:
    def test_seed_invariants_hold(self) -> None:
        _assert_seed_invariants()

    def test_valid_with_op_code_passes(self) -> None:
        """정합 매핑(op_code↔misconception 일치) → 오류 없음."""
        errors = validate_distractor_map(
            [DistractorEntry(choice_index=1, misconception_id=_VALID_MIS, op_code=_VALID_OP)]
        )
        assert errors == []

    def test_valid_without_op_code_passes(self) -> None:
        """op_code 미지정 + 실재 misconception_id → 오류 없음(op_code는 선택)."""
        errors = validate_distractor_map(
            [DistractorEntry(choice_index=0, misconception_id="mean-vs-median")]
        )
        assert errors == []

    def test_empty_passes(self) -> None:
        """빈 매핑 → 오류 없음."""
        assert validate_distractor_map([]) == []

    def test_unknown_misconception_id_rejected(self) -> None:
        """미등록 misconception_id → 위반 1건(참조 무결성)."""
        errors = validate_distractor_map(
            [DistractorEntry(choice_index=1, misconception_id="this-id-does-not-exist")]
        )
        assert len(errors) == 1
        assert "미등록 misconception_id" in errors[0]
        assert "this-id-does-not-exist" in errors[0]

    def test_unknown_op_code_rejected(self) -> None:
        """미등록 op_code → 위반 1건(misconception_id는 실재해도)."""
        errors = validate_distractor_map(
            [
                DistractorEntry(
                    choice_index=1,
                    misconception_id=_VALID_MIS,
                    op_code="this-op-does-not-exist",
                )
            ]
        )
        assert len(errors) == 1
        assert "미등록 op_code" in errors[0]
        assert "this-op-does-not-exist" in errors[0]

    def test_op_code_misconception_mismatch_rejected(self) -> None:
        """op_code가 가리키는 오개념 ≠ 엔트리 오개념 → 불일치 위반.

        실재 op_code(_VALID_OP, '대수' distribution)에 *다른* 실재 misconception_id
        (mean-vs-median, 확률통계)를 매핑 — 둘 다 실재하므로 ①②는 통과하고 ③ 정합만 깬다.
        """
        errors = validate_distractor_map(
            [
                DistractorEntry(
                    choice_index=2,
                    misconception_id="mean-vs-median",
                    op_code=_VALID_OP,
                )
            ]
        )
        assert len(errors) == 1
        assert "불일치" in errors[0]
        assert _VALID_OP in errors[0]

    def test_multiple_violations_collected(self) -> None:
        """여러 위반을 *모아* 보고(인덱스 포함) — 비파괴 검사."""
        errors = validate_distractor_map(
            [
                DistractorEntry(choice_index=1, misconception_id="unknown-a"),
                DistractorEntry(
                    choice_index=2, misconception_id=_VALID_MIS, op_code="unknown-op"
                ),
                DistractorEntry(choice_index=3, misconception_id="mean-vs-median"),  # 정합
            ]
        )
        assert len(errors) == 2  # 셋 중 둘만 위반
        assert "[0]" in errors[0]  # 인덱스 0 위반
        assert "[1]" in errors[1]  # 인덱스 1 위반

    def test_mismatch_skips_when_op_code_unknown(self) -> None:
        """op_code 자체가 미등록이면 정합(③)은 평가하지 않고 ② 한 건만 보고(중복 회피)."""
        errors = validate_distractor_map(
            [
                DistractorEntry(
                    choice_index=1, misconception_id=_VALID_MIS, op_code="ghost-op"
                )
            ]
        )
        assert len(errors) == 1
        assert "미등록 op_code" in errors[0]


class TestRaiseForDistractorMap:
    def test_valid_does_not_raise(self) -> None:
        """정합 매핑 → 예외 없음."""
        raise_for_distractor_map(
            [DistractorEntry(choice_index=1, misconception_id=_VALID_MIS, op_code=_VALID_OP)]
        )

    def test_invalid_raises_value_error(self) -> None:
        """위반 시 ValueError(fail-loud 게이트) — 모든 위반을 한 메시지로."""
        with pytest.raises(ValueError, match="참조 무결성 위반"):
            raise_for_distractor_map(
                [DistractorEntry(choice_index=1, misconception_id="nope")]
            )
