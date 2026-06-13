"""L4 보정(calibration) 코칭 결정 단위테스트 (hermetic·순수 결정·DB 불요).

WH-1 §11.4 보정 루프 — 자기보고 확신도↔실제 정오답 불일치를 코칭으로 잇는다(측정→행동).
`recommend_calibration_coaching`을 직접 호출해 과신/과소신/None 분기·임계 경계·톤을 검증한다
(실 SQL·async 불요·순수 함수).
"""

from __future__ import annotations

from whymath_backend.l4.calibration_coaching import recommend_calibration_coaching
from whymath_backend.l4.metacognitive_trigger import CoachingTrigger
from whymath_backend.l4.socratic.categories import SocraticCategory

# 학생 prompt에 절대 나오면 안 되는 금기 표현(CLAUDE.md 교수학 톤·부정 강화·정답 즉시제공).
_FORBIDDEN_IN_PROMPT = ["빨리", "정답", "틀렸", "못"]


class TestRecommendCalibrationCoaching:
    def test_overconfident_wrong_high_confidence(self) -> None:
        """과신 구간(틀림 + 확신≥0.7) → calibration_overconfident·ASSUMPTION."""
        trig = recommend_calibration_coaching(0.9, False)
        assert isinstance(trig, CoachingTrigger)
        assert trig.focus == "calibration_overconfident"
        assert trig.socratic_category == SocraticCategory.ASSUMPTION
        assert trig.rationale and trig.prompt

    def test_underconfident_correct_low_confidence(self) -> None:
        """과소신 구간(맞음 + 확신≤0.3) → calibration_underconfident·META."""
        trig = recommend_calibration_coaching(0.1, True)
        assert isinstance(trig, CoachingTrigger)
        assert trig.focus == "calibration_underconfident"
        assert trig.socratic_category == SocraticCategory.META
        assert trig.rationale and trig.prompt

    def test_well_calibrated_correct_high_confidence_none(self) -> None:
        """잘 보정됨(맞음 + 확신 높음) → None(코칭 불요)."""
        assert recommend_calibration_coaching(0.95, True) is None

    def test_well_calibrated_wrong_low_confidence_none(self) -> None:
        """잘 보정됨(틀림 + 확신 낮음) → None(예측↔실제 일치)."""
        assert recommend_calibration_coaching(0.1, False) is None

    def test_mid_confidence_none(self) -> None:
        """중간 확신(임계 사이)은 어느 구간도 아님 → None."""
        assert recommend_calibration_coaching(0.5, False) is None
        assert recommend_calibration_coaching(0.5, True) is None

    def test_confidence_none_returns_none(self) -> None:
        """확신 미제출(None) → None(보정 평가 불가)."""
        assert recommend_calibration_coaching(None, True) is None
        assert recommend_calibration_coaching(None, False) is None

    def test_is_correct_none_returns_none(self) -> None:
        """정오답 None → None(보정 평가 불가)."""
        assert recommend_calibration_coaching(0.9, None) is None
        assert recommend_calibration_coaching(0.1, None) is None

    def test_both_none_returns_none(self) -> None:
        """둘 다 None → None."""
        assert recommend_calibration_coaching(None, None) is None

    def test_over_threshold_boundary_inclusive(self) -> None:
        """과신 임계는 양끝 포함(>=) — 정확히 0.7·틀림이면 과신."""
        trig = recommend_calibration_coaching(0.7, False)
        assert trig is not None
        assert trig.focus == "calibration_overconfident"

    def test_under_threshold_boundary_inclusive(self) -> None:
        """과소신 임계는 양끝 포함(<=) — 정확히 0.3·맞음이면 과소신."""
        trig = recommend_calibration_coaching(0.3, True)
        assert trig is not None
        assert trig.focus == "calibration_underconfident"

    def test_just_below_over_threshold_none(self) -> None:
        """과신 임계 바로 아래(0.69·틀림)는 None(경계 미만)."""
        assert recommend_calibration_coaching(0.69, False) is None

    def test_just_above_under_threshold_none(self) -> None:
        """과소신 임계 바로 위(0.31·맞음)는 None(경계 초과)."""
        assert recommend_calibration_coaching(0.31, True) is None

    def test_custom_thresholds(self) -> None:
        """임계 커스터마이즈 — over/under_threshold 인자로 구간 폭 조절."""
        # 기본(0.7)이면 None인 0.6도 over_threshold=0.5면 과신.
        assert recommend_calibration_coaching(0.6, False) is None
        trig = recommend_calibration_coaching(0.6, False, over_threshold=0.5)
        assert trig is not None and trig.focus == "calibration_overconfident"
        # 기본(0.3)이면 None인 0.4도 under_threshold=0.5면 과소신.
        assert recommend_calibration_coaching(0.4, True) is None
        trig2 = recommend_calibration_coaching(0.4, True, under_threshold=0.5)
        assert trig2 is not None and trig2.focus == "calibration_underconfident"

    def test_overconfident_prompt_tone_guard(self) -> None:
        """과신 prompt 톤 가드 — 금기 표현(빨리·정답·틀렸·못) 부재(비난 0·바로 정답 0)."""
        trig = recommend_calibration_coaching(0.9, False)
        assert trig is not None
        for forbidden in _FORBIDDEN_IN_PROMPT:
            assert forbidden not in trig.prompt, f"금기 표현 '{forbidden}' 노출"

    def test_underconfident_prompt_tone_guard(self) -> None:
        """과소신 prompt 톤 가드 — 금기 표현 부재 + 성취 명시(격려)."""
        trig = recommend_calibration_coaching(0.1, True)
        assert trig is not None
        for forbidden in _FORBIDDEN_IN_PROMPT:
            assert forbidden not in trig.prompt, f"금기 표현 '{forbidden}' 노출"
        assert "맞았어" in trig.prompt  # 성취 명시(효능감)

    def test_trigger_frozen(self) -> None:
        """CoachingTrigger는 불변(frozen) — 변경 시도 시 예외."""
        trig = recommend_calibration_coaching(0.9, False)
        assert trig is not None
        try:
            trig.focus = "advance"  # type: ignore[misc]
        except Exception as exc:  # pydantic ValidationError(frozen)
            assert "frozen" in str(exc).lower() or "instance" in str(exc).lower()
        else:  # pragma: no cover
            raise AssertionError("frozen 모델이 변경을 허용함")

    def test_deterministic(self) -> None:
        """동일 입력 → 동일 출력(순수·결정론)."""
        assert recommend_calibration_coaching(
            0.9, False
        ) == recommend_calibration_coaching(0.9, False)
