"""L2 목표 진행 상황(`get_target_progress`) 단위테스트 (hermetic·FakeSession).

D-day 계산은 순수(세션 무관)로, `school_type` 유무에 따른 커버리지 분기는 FakeSession으로
호출 순서·결과 결합만 검증한다(실 조인 정합은 `test_me_target_progress_integration.py`류,
이 세션에선 실행 불가). acceptance②(점수·등급 예측 필드 부재)는 `model_fields` 집합 동결로
고정한다.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from typing import Any

from whymath_backend.l2.target_progress import TargetProgress, get_target_progress

_UID = uuid.uuid4()
_AS_OF = date(2026, 8, 9)


@dataclass
class _FakeProfile:
    """`get_target_progress`가 실제로 읽는 필드만 흉내(hermetic — ORM 불요)."""

    target_exam_date: date | None = None
    target_grade: int | None = None
    target_score: int | None = None
    school_type: str | None = None


class _Result:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def all(self) -> list[Any]:
        return list(self._rows)


class _QueueSession:
    """`get()`은 프로필 1회, `execute()`는 호출 순서대로 큐잉된 결과를 반환.

    호출 순서(모듈 docstring 고정): ①`session.get`(프로필) ②스코프 SELECT ③관측 SELECT
    (스코프>0일 때만). `executed_count`로 몇 회 `execute`가 실제 불렸는지 확인해, 스코프 0건일
    때 관측 쿼리가 *생략*되는 단락 동작까지 검증한다.
    """

    def __init__(self, profile: _FakeProfile | None, execute_queue: list[list[Any]]) -> None:
        self._profile = profile
        self._queue = list(execute_queue)
        self.executed_count = 0

    async def get(self, _model: Any, _pk: Any) -> _FakeProfile | None:
        return self._profile

    async def execute(self, _stmt: Any) -> _Result:
        self.executed_count += 1
        return _Result(self._queue.pop(0))


class TestProfileMissing:
    """프로필 자체가 없으면(신규 학생 등) 전 필드 None — 예외 없이 반환."""

    async def test_no_profile_returns_all_none(self) -> None:
        session = _QueueSession(None, [])
        result = await get_target_progress(session, _UID, as_of=_AS_OF)  # type: ignore[arg-type]
        assert result == TargetProgress()
        assert session.executed_count == 0  # 프로필 부재 시 쿼리 자체를 안 낸다(단락).


class TestDday:
    """D-day 계산 — 순수(클램프 없음)."""

    async def test_future_exam_date_positive_days(self) -> None:
        profile = _FakeProfile(target_exam_date=date(2026, 9, 8), target_grade=2, target_score=130)
        session = _QueueSession(profile, [])
        result = await get_target_progress(session, _UID, as_of=_AS_OF)  # type: ignore[arg-type]
        assert result.days_until_exam == 30
        assert result.target_exam_date == date(2026, 9, 8)
        assert result.target_grade == 2
        assert result.target_score == 130

    async def test_past_exam_date_negative_no_clamp(self) -> None:
        profile = _FakeProfile(target_exam_date=date(2026, 8, 4))
        session = _QueueSession(profile, [])
        result = await get_target_progress(session, _UID, as_of=_AS_OF)  # type: ignore[arg-type]
        assert result.days_until_exam == -5

    async def test_no_exam_date_none(self) -> None:
        profile = _FakeProfile(target_exam_date=None)
        session = _QueueSession(profile, [])
        result = await get_target_progress(session, _UID, as_of=_AS_OF)  # type: ignore[arg-type]
        assert result.days_until_exam is None


class TestCoverageScopeUnavailable:
    """`school_type`이 None이면 커버리지 5필드 전부 None(스코프 계산 불가·정직 폴백)."""

    async def test_school_type_none_all_coverage_fields_none(self) -> None:
        profile = _FakeProfile(target_grade=3, school_type=None)
        session = _QueueSession(profile, [])
        result = await get_target_progress(session, _UID, as_of=_AS_OF)  # type: ignore[arg-type]
        assert result.standard_coverage_percent is None
        assert result.standard_coverage_observed is None
        assert result.standard_coverage_scope is None
        assert result.standard_coverage_measured_concepts is None  # CUR-04 작동 신호도 정직 폴백.
        assert result.standard_coverage_matched_concepts is None
        assert result.target_grade == 3  # 다른 필드는 정상 echo.
        assert session.executed_count == 0  # 스코프 쿼리 자체를 안 낸다.


class TestCoverageComputed:
    """`school_type`이 있으면 스코프→관측 순으로 조회해 비율을 계산(CUR-04 원자 축).

    스코프 행은 `(norm_id, official_code)` 2-tuple, 관측 행은 `(concept_id, standard_codes)`
    2-tuple이다 — `get_target_progress` 모듈 docstring의 원자 축 조인 shape과 정합.
    """

    async def test_percent_computed_from_scope_then_observed(self) -> None:
        profile = _FakeProfile(school_type="일반고")
        c1, c2, c3 = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        # ①스코프 4건(norm_id, official_code) ②관측 3개념 순서로 큐잉 — 순서가 바뀌면 결과가
        # 어긋난다. 관측 3개념 중: c1은 원자 매칭+스코프 내 코드 관측(N1) → observed에 기여,
        # c2는 원자 매칭됐으나 스코프 밖 코드만 가짐(무기여), c3은 원자 축 미매칭(None — join miss).
        session = _QueueSession(
            profile,
            [
                [("N1", "STD-1"), ("N2", "STD-2"), ("N3", "STD-3"), ("N4", "STD-4")],  # 스코프
                [
                    (c1, ["STD-1"]),  # 원자 매칭 + 스코프 내 코드 관측 → N1 커버.
                    (c2, ["STD-OUT-OF-SCOPE"]),  # 원자 매칭됐으나 스코프 밖 코드.
                    (c3, None),  # 원자 축 조인 미스(concept.code가 atom_node에 없음).
                ],
            ],
        )
        result = await get_target_progress(session, _UID, as_of=_AS_OF)  # type: ignore[arg-type]
        assert result.standard_coverage_scope == 4
        assert result.standard_coverage_observed == 1  # N1만 스코프 내에서 관측.
        assert result.standard_coverage_percent == 25.0
        # 작동 신호(CUR-04) — 측정 이력 3개념 중 원자 축에 매칭된 것은 c1·c2 2개(c3은 미매칭).
        assert result.standard_coverage_measured_concepts == 3
        assert result.standard_coverage_matched_concepts == 2
        assert session.executed_count == 2

    async def test_zero_scope_short_circuits_no_percent(self) -> None:
        profile = _FakeProfile(school_type="일반고")
        session = _QueueSession(profile, [[]])  # 스코프 0건 — 관측 쿼리 생략.
        result = await get_target_progress(session, _UID, as_of=_AS_OF)  # type: ignore[arg-type]
        assert result.standard_coverage_scope == 0
        assert result.standard_coverage_observed == 0
        assert result.standard_coverage_percent is None  # 0으로 나누기 회피 + "스코프 없음" 구분.
        assert result.standard_coverage_measured_concepts is None  # 관측 쿼리 자체를 안 냄.
        assert result.standard_coverage_matched_concepts is None
        assert session.executed_count == 1  # 관측 쿼리는 안 나갔다.

    async def test_measured_concepts_all_unmatched_reports_zero_matched(self) -> None:
        """측정 이력은 있으나 원자 축에 전부 미매칭 — '조인 실패' 작동 신호(CLAUDE.md 침묵 실패 금지).

        이 fixture는 CUR-04 이전 구 축이 만들어냈던 정확한 함정을 재현한다: 관측 후보는
        있지만(measured>0) 전부 join miss(matched==0)라 observed=0·percent=0.0이 나온다. 새 두
        필드가 없으면 이 0.0%이 "미도달"인지 "조인 실패"인지 구분할 수 없다.
        """
        profile = _FakeProfile(school_type="일반고")
        c1, c2 = uuid.uuid4(), uuid.uuid4()
        session = _QueueSession(
            profile,
            [
                [("N1", "STD-1")],  # 스코프 1건
                [(c1, None), (c2, None)],  # 측정 이력 2개념 — 전부 원자 축 미매칭.
            ],
        )
        result = await get_target_progress(session, _UID, as_of=_AS_OF)  # type: ignore[arg-type]
        assert result.standard_coverage_percent == 0.0
        assert result.standard_coverage_observed == 0
        assert result.standard_coverage_measured_concepts == 2  # 조인을 "시도"는 했다.
        assert result.standard_coverage_matched_concepts == 0  # 그러나 전부 실패 — 미도달과 구분.


class TestNoPredictionFields:
    """acceptance② — 점수·등급 예측 필드 부재를 스키마 계약으로 동결."""

    def test_field_set_has_no_prediction_fields(self) -> None:
        assert set(TargetProgress.model_fields) == {
            "target_exam_date",
            "days_until_exam",
            "target_grade",
            "target_score",
            "standard_coverage_percent",
            "standard_coverage_observed",
            "standard_coverage_scope",
            # CUR-04 — 원자 축 조인 작동 신호(0%가 미도달인지 조인 실패인지 구분).
            "standard_coverage_measured_concepts",
            "standard_coverage_matched_concepts",
        }
