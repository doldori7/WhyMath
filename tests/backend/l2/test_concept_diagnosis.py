"""L2 개념 진단 — `concept_diagnosis` 단위테스트 (hermetic·FakeSession).

slice 82에 api/me(L5)에서 이관. `theta_to_mastery_proxy`(순수)·`diagnosis_agreement`(순수)·
`compute_concept_diagnoses`(BKT 최신 + IRT θ 융합·agreement·약점 정렬)를 검증한다. 쿼리 순서는
BKT→IRT(`compute_concept_abilities` 재사용)이라 _QueueSession도 [mastery, irt] 순. WHERE/JOIN
정확성은 me 통합테스트가 실 PG로 — 여기선 stmt 무시·행 가공만.
"""

from __future__ import annotations

import uuid
from typing import Any, cast

from sqlalchemy.ext.asyncio import AsyncSession

from whymath_backend.l2.concept_diagnosis import (
    STEP_PANEL_ANCHOR_LOOKBACK,
    compute_concept_diagnoses,
    diagnosis_agreement,
    list_recent_attempted_problem_ids,
)

_UID = uuid.uuid4()


class _Result:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def all(self) -> list[Any]:
        return list(self._rows)


class _QueueSession:
    """execute()가 호출 순서대로 미리 준 결과를 반환 — 진단 쿼리 순서: ①BKT ②IRT."""

    def __init__(self, results: list[list[Any]]) -> None:
        self._results = list(results)

    async def execute(self, _stmt: Any) -> _Result:
        return _Result(self._results.pop(0))


def _session(bkt_rows: list[Any], irt_rows: list[Any]) -> AsyncSession:
    return cast(AsyncSession, _QueueSession([bkt_rows, irt_rows]))


def _session_single(rows: list[Any]) -> AsyncSession:
    """execute 1회짜리 큐 세션 — `list_recent_attempted_problem_ids`(단일 쿼리)용."""
    return cast(AsyncSession, _QueueSession([rows]))


class TestDiagnosisAgreement:
    """BKT↔IRT 프록시 일치 신호(둘 다 있을 때만 차이 분기)."""

    def test_insufficient_when_missing(self) -> None:
        assert diagnosis_agreement(None, 0.5) == "insufficient"
        assert diagnosis_agreement(0.5, None) == "insufficient"
        assert diagnosis_agreement(None, None) == "insufficient"

    def test_agree_within_tol(self) -> None:
        assert diagnosis_agreement(0.5, 0.5) == "agree"
        assert diagnosis_agreement(0.5, 0.65) == "agree"  # 차 0.15 ≤ 0.2

    def test_irt_higher(self) -> None:
        assert diagnosis_agreement(0.1, 0.9) == "irt_higher"

    def test_bkt_higher(self) -> None:
        assert diagnosis_agreement(0.9, 0.1) == "bkt_higher"


class TestComputeConceptDiagnoses:
    """BKT 최신 + IRT θ 융합 — agreement·합집합·약점 정렬·메타."""

    async def test_both_signals_agree(self) -> None:
        cid = uuid.uuid4()
        bkt = [(cid, "C", "개념", 0.5)]
        irt = [
            (cid, "C", "개념", True, 3.0, None),
            (cid, "C", "개념", False, 3.0, None),
        ]
        out = await compute_concept_diagnoses(_session(bkt, irt), _UID)
        assert len(out) == 1
        d = out[0]
        assert d.bkt_mastery == 0.5
        assert d.irt_theta == 0.0  # 1정답1오답(b=0) → θ=0
        assert d.irt_mastery_proxy == 0.5
        assert d.response_count == 2
        assert d.agreement == "agree"
        assert d.concept_name == "개념"

    async def test_irt_higher(self) -> None:
        cid = uuid.uuid4()
        out = await compute_concept_diagnoses(
            _session([(cid, "C", "개념", 0.1)], [(cid, "C", "개념", True, 3.0, None)]),
            _UID,
        )
        d = out[0]
        assert d.irt_theta == 4.0  # 전부 정답 → 상한
        assert d.agreement == "irt_higher"

    async def test_bkt_higher(self) -> None:
        cid = uuid.uuid4()
        out = await compute_concept_diagnoses(
            _session([(cid, "C", "개념", 0.9)], [(cid, "C", "개념", False, 3.0, None)]),
            _UID,
        )
        assert out[0].agreement == "bkt_higher"

    async def test_bkt_only_insufficient(self) -> None:
        # IRT 채점 없는 개념(BKT만) → theta·proxy null·insufficient.
        cid = uuid.uuid4()
        out = await compute_concept_diagnoses(_session([(cid, "C", "개념", 0.6)], []), _UID)
        d = out[0]
        assert d.bkt_mastery == 0.6
        assert d.irt_theta is None
        assert d.irt_mastery_proxy is None
        assert d.response_count == 0
        assert d.agreement == "insufficient"

    async def test_irt_only_insufficient_uses_ability_meta(self) -> None:
        # BKT 없는 개념(IRT만) → bkt null·insufficient·메타는 ability에서.
        cid = uuid.uuid4()
        out = await compute_concept_diagnoses(
            _session([], [(cid, "TRIG", "삼각", True, 3.0, None)]), _UID
        )
        d = out[0]
        assert d.bkt_mastery is None
        assert d.irt_theta == 4.0
        assert d.agreement == "insufficient"
        assert d.concept_code == "TRIG"  # ability 메타 폴백
        assert d.concept_name == "삼각"

    async def test_weakness_sort_union(self) -> None:
        # 합집합·약점(저신호) 먼저: 전부오답(proxy≈0.02) < BKT 0.9.
        c_weak, c_strong = uuid.uuid4(), uuid.uuid4()
        bkt = [(c_strong, "S", "강", 0.9)]
        irt = [(c_weak, "W", "약", False, 3.0, None)]
        out = await compute_concept_diagnoses(_session(bkt, irt), _UID)
        assert [d.concept_id for d in out] == [c_weak, c_strong]

    async def test_empty(self) -> None:
        assert await compute_concept_diagnoses(_session([], []), _UID) == []


class TestListRecentAttemptedProblemIds:
    """SOL-02 step_panel 앵커 후보 열거 — 최근 시도 순(쿼리 정렬) 가정 하 dedupe·캡·빈 이력.

    행 모양은 `(problem_id, attempt_id)` 튜플(SELECT 절 순서). WHERE/JOIN·ORDER BY 정확성은
    실 PG 통합테스트 축이고, 여기선 행 가공(dedupe·캡·None 스킵)만 hermetic 검증한다.
    """

    async def test_dedupe_keeps_first_occurrence(self) -> None:
        """같은 문항 재시도는 첫(가장 최근) 등장만 남기고 순서를 보존한다."""
        p1, p2 = uuid.uuid4(), uuid.uuid4()
        rows = [(p1, uuid.uuid4()), (p2, uuid.uuid4()), (p1, uuid.uuid4())]
        out = await list_recent_attempted_problem_ids(_session_single(rows), _UID, uuid.uuid4())
        assert out == [p1, p2]

    async def test_cap_limits_candidates(self) -> None:
        """후보는 limit 캡으로 잘린다(앵커 탐색 지연 상한 — 문항당 경로 조회 1회씩이라)."""
        rows = [(uuid.uuid4(), uuid.uuid4()) for _ in range(6)]
        out = await list_recent_attempted_problem_ids(
            _session_single(rows), _UID, uuid.uuid4(), limit=3
        )
        assert out == [r[0] for r in rows[:3]]

    async def test_default_cap_is_lookback_constant(self) -> None:
        """기본 캡은 STEP_PANEL_ANCHOR_LOOKBACK(5) — 7행이면 5개만."""
        rows = [(uuid.uuid4(), uuid.uuid4()) for _ in range(7)]
        out = await list_recent_attempted_problem_ids(_session_single(rows), _UID, uuid.uuid4())
        assert len(out) == STEP_PANEL_ANCHOR_LOOKBACK

    async def test_null_problem_id_skipped(self) -> None:
        """problem_id NULL 행은 스킵(조인 등값 조건상 실 SQL에선 못 오지만 방어)."""
        p1 = uuid.uuid4()
        rows = [(None, uuid.uuid4()), (p1, uuid.uuid4())]
        out = await list_recent_attempted_problem_ids(_session_single(rows), _UID, uuid.uuid4())
        assert out == [p1]

    async def test_empty_when_no_attempts(self) -> None:
        """시도 이력 없음 → 빈 목록(앵커 없음 → step_panel 방출 0의 정직한 경계)."""
        assert (
            await list_recent_attempted_problem_ids(_session_single([]), _UID, uuid.uuid4()) == []
        )
