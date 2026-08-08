"""`api/gating._fetch_candidates`의 절단 관측 로그 단위테스트(PB-03 축③, hermetic).

`_CANDIDATE_FETCH_LIMIT`(3000)만큼 코퍼스가 커지려면 실 DB가 필요하므로, 이 테스트는 상수를
monkeypatch로 작게 낮추고 `_fetch_candidates`를 직접 호출한다(라우터 경유 없이 함수 단위) —
가짜 세션이 fetch 호출과 count 호출을 순서로 구분해 응답한다. 변별력 확인: 상한 미만 행에서는
로그가 찍히지 않고, 상한과 정확히 같은 행에서는 정확한 truncated 건수와 함께 찍힌다(로그 코드가
있어도 실제로 발화하는지 확인 없이 "구현됨"으로 치지 않는다 — CLAUDE.md 변별력 규칙).
"""

from __future__ import annotations

import logging
from typing import Any

import pytest

from whymath_backend.api import gating as gating_module
from whymath_backend.db.models.problem import Problem
from whymath_backend.schema.enums import Curriculum, ReviewStatus, SourceType, Subject
from whymath_backend.schema.problem import Problem as ProblemSchema


def _problem(slug: str) -> Problem:
    return Problem.from_schema(  # type: ignore[arg-type]
        ProblemSchema(
            slug=slug,
            source_type=SourceType.자체생성,
            review_status=ReviewStatus.approved,
            curriculum_version=Curriculum.REVISION_2022,
            valid_from_year=2022,
            subject=Subject.미적분,
            unit_codes=["CAL-INT-DEF"],
        )
    )


class _FakeScalars:
    def __init__(self, rows: list[Problem]) -> None:
        self._rows = rows

    def all(self) -> list[Problem]:
        return list(self._rows)


class _FakeCandidateResult:
    def __init__(self, rows: list[Problem]) -> None:
        self._rows = rows

    def scalars(self) -> _FakeScalars:
        return _FakeScalars(self._rows)


class _FakeCountResult:
    def __init__(self, total: int) -> None:
        self._total = total

    def scalar_one(self) -> int:
        return self._total


class _OrderedFakeSession:
    """1번째 execute()=후보 fetch, 2번째(있으면)=count(*) — 호출 순서로만 구분(hermetic)."""

    def __init__(self, rows: list[Problem], total: int) -> None:
        self._rows = rows
        self._total = total
        self.execute_calls = 0

    async def execute(self, _stmt: Any) -> _FakeCandidateResult | _FakeCountResult:
        self.execute_calls += 1
        if self.execute_calls == 1:
            return _FakeCandidateResult(self._rows)
        return _FakeCountResult(self._total)


@pytest.mark.asyncio
async def test_no_truncation_below_limit_no_warning(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """fetch 건수가 상한 미만이면 count(*) 재조회도, 경고 로그도 없다."""
    monkeypatch.setattr(gating_module, "_CANDIDATE_FETCH_LIMIT", 5)
    session = _OrderedFakeSession(rows=[_problem(f"p{i}") for i in range(3)], total=3)
    with caplog.at_level(logging.WARNING, logger="whymath_backend.api.gating"):
        result = await gating_module._fetch_candidates(session)  # type: ignore[arg-type]
    assert len(result) == 3
    assert session.execute_calls == 1  # count(*) 재조회 자체가 없어야 함
    assert not any("truncated" in rec.message for rec in caplog.records)


@pytest.mark.asyncio
async def test_truncation_at_limit_logs_exact_count(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """fetch 건수가 상한과 정확히 같으면 count(*) 재조회 후 정확한 truncated 건수로 경고."""
    monkeypatch.setattr(gating_module, "_CANDIDATE_FETCH_LIMIT", 3)
    session = _OrderedFakeSession(rows=[_problem(f"p{i}") for i in range(3)], total=10)
    with caplog.at_level(logging.WARNING, logger="whymath_backend.api.gating"):
        result = await gating_module._fetch_candidates(session)  # type: ignore[arg-type]
    assert len(result) == 3
    assert session.execute_calls == 2  # count(*) 재조회가 실제로 일어남
    warnings = [rec.message for rec in caplog.records if "truncated" in rec.message]
    assert len(warnings) == 1
    assert "fetched=3" in warnings[0]
    assert "total=10" in warnings[0]
    assert "truncated=7" in warnings[0]
