"""PED-04 D1 reader ② 순수 조립 단위테스트 — `l4/session_recall.py`.

핵심 invariant:
- 구조적 복호 0: `SessionRecall`의 모든 필드가 enum/id 문자열/정수라, 학생 원문을 실을 자리가
  타입상 존재하지 않는다(모델 필드셋을 전수 검사해 동결).
- 전 축 공백이면 None(빈 회상 날조 금지).
- `unresolved_hypothesis_ids`는 워밍스타트 전용 — 이 파일은 그 계약을 필드 존재로만 확인하고,
  실제 미주입은 `tests/backend/harness/test_wh1_llm_policy.py`가 프롬프트 비노출로 확인한다.
"""

from __future__ import annotations

from whymath_backend.l4.models import PolyaStage
from whymath_backend.l4.session_recall import SessionRecall, assemble_session_recall
from whymath_backend.schema.enums import SocraticStrategy


class TestSessionRecallStructuralGuarantee:
    def test_all_fields_are_typed_non_freetext(self) -> None:
        """필드 타입 전수 검사 — 문자열 자유 필드(원문을 실을 수 있는 타입)가 하나도 없어야 한다."""
        fields = SessionRecall.model_fields
        assert set(fields) == {
            "last_polya_stage",
            "last_socratic_strategies",
            "unresolved_hypothesis_ids",
            "turns_since",
        }
        # str 타입 필드는 tuple[str, ...](id 목록)뿐이지 최상위 str 필드가 아님을 확인.
        assert fields["last_polya_stage"].annotation == PolyaStage | None

    def test_frozen_and_extra_forbid(self) -> None:
        recall = SessionRecall(turns_since=0)
        assert recall.model_config.get("frozen") is True
        assert recall.model_config.get("extra") == "forbid"


class TestAssembleSessionRecall:
    def test_all_axes_empty_returns_none(self) -> None:
        result = assemble_session_recall(
            last_stage_step=None,
            strategies=[],
            active_hypothesis_ids=[],
            turns_since=0,
        )
        assert result is None

    def test_stage_only_returns_recall(self) -> None:
        result = assemble_session_recall(
            last_stage_step=2,
            strategies=[],
            active_hypothesis_ids=[],
            turns_since=3,
        )
        assert result is not None
        assert result.last_polya_stage is PolyaStage.PLAN
        assert result.turns_since == 3

    def test_none_strategies_dropped(self) -> None:
        """전략 목록의 None은 버린다 — NULL을 채워 회상을 과장하지 않는다."""
        result = assemble_session_recall(
            last_stage_step=1,
            strategies=[SocraticStrategy.조건확인, None, SocraticStrategy.단계분해, None],
            active_hypothesis_ids=[],
            turns_since=1,
        )
        assert result is not None
        assert result.last_socratic_strategies == (
            SocraticStrategy.조건확인,
            SocraticStrategy.단계분해,
        )

    def test_max_strategies_truncates_to_most_recent(self) -> None:
        strategies = [
            SocraticStrategy.조건확인,
            SocraticStrategy.단계분해,
            SocraticStrategy.예시제시,
            SocraticStrategy.유사문제,
        ]
        result = assemble_session_recall(
            last_stage_step=1,
            strategies=strategies,
            active_hypothesis_ids=[],
            turns_since=1,
            max_strategies=2,
        )
        assert result is not None
        # 최근 것(꼬리) 2개만 남는다.
        assert result.last_socratic_strategies == (
            SocraticStrategy.예시제시,
            SocraticStrategy.유사문제,
        )

    def test_active_hypothesis_ids_passthrough(self) -> None:
        result = assemble_session_recall(
            last_stage_step=None,
            strategies=[],
            active_hypothesis_ids=["M001", "M002"],
            turns_since=0,
        )
        assert result is not None
        assert result.unresolved_hypothesis_ids == ("M001", "M002")

    def test_negative_turns_since_clamped_to_zero(self) -> None:
        result = assemble_session_recall(
            last_stage_step=1,
            strategies=[],
            active_hypothesis_ids=[],
            turns_since=-5,
        )
        assert result is not None
        assert result.turns_since == 0
