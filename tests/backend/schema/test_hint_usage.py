"""HintUsage Pydantic 계약(`schema/hint_usage.py`) — 검증 경계 (EOS-45).

`test_answer_submission.py`(EOS-32) 컨벤션 미러: DB 0·순수 모델 검증만. hint_level 폐쇄
범위(1~4·정본 l4.hint_deferral.HintLevel 수치 복제)·view_duration_ms 하한(ge=0)·필수 필드·
extra 금지를 못박는다 — DB 컬럼은 값만 담으므로(Integer/Text 좌석) 이 검증이 유일한 강제
지점이다.
"""

from __future__ import annotations

import uuid

import pytest
from pydantic import ValidationError

from whymath_backend.schema.hint_usage import HintUsage


def _minimal(**overrides: object) -> HintUsage:
    base: dict[str, object] = {
        "attempt_id": uuid.uuid4(),
        "user_id": uuid.uuid4(),
        "hint_level": 1,
    }
    base.update(overrides)
    return HintUsage.model_validate(base)


class TestHintUsageContract:
    def test_minimal_valid_defaults(self) -> None:
        """필수 3필드만으로 유효 — hint_id·시각·열람시간은 None(DB/계측 몫)."""
        usage = _minimal()
        assert usage.hint_id is None  # 동적 생성 힌트(식별자 없음) — 가짜 id 생성 금지
        assert usage.requested_at is None  # DB server_default now()가 채운다
        assert usage.view_duration_ms is None  # 미측정(0 날조 금지)

    @pytest.mark.parametrize("level", [1, 2, 3, 4])
    def test_hint_level_closed_range_accepts(self, level: int) -> None:
        """폐쇄 1~4 전부 수용(정본 l4.hint_deferral.HintLevel과 정합)."""
        assert _minimal(hint_level=level).hint_level == level

    @pytest.mark.parametrize("level", [0, 5, -1])
    def test_hint_level_rejects_out_of_range(self, level: int) -> None:
        """범위 밖(0·5·음수)은 ValidationError — DB는 값만 담으므로 여기가 유일 강제 지점."""
        with pytest.raises(ValidationError):
            _minimal(hint_level=level)

    def test_view_duration_rejects_negative(self) -> None:
        """음수 열람시간 거부(ge=0) — 미측정은 음수가 아니라 None으로 표현한다."""
        with pytest.raises(ValidationError):
            _minimal(view_duration_ms=-1)

    def test_attempt_and_user_required(self) -> None:
        """attempt 없는 힌트 사용·학생 없는 힌트 사용은 없다(required)."""
        with pytest.raises(ValidationError):
            HintUsage.model_validate({"user_id": uuid.uuid4(), "hint_level": 1})
        with pytest.raises(ValidationError):
            HintUsage.model_validate({"attempt_id": uuid.uuid4(), "hint_level": 1})

    def test_extra_fields_forbidden(self) -> None:
        """extra='forbid' — 오타 필드가 조용히 버려지지 않는다."""
        with pytest.raises(ValidationError):
            _minimal(unknown_field="x")

    def test_hint_id_length_bounded(self) -> None:
        """hint_id 폭 상한(max_length=200) — 느슨참조라도 무한 문자열은 거부."""
        with pytest.raises(ValidationError):
            _minimal(hint_id="h" * 201)
