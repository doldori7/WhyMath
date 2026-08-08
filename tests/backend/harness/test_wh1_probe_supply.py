"""WH-1 probe_candidates 조립 하네스 단위테스트 — REC-02 ②③④⑤.

`assemble_probe_candidate_pool`을 실 DB 없이 검증한다 — L1 조회(`fetch_probe_candidates_by_mids`)를
monkeypatch로 대체해 순수 조립·funnel 계상·never-break만 이 모듈의 책임으로 좁힌다(L1 자체 로직은
`tests/backend/l1/problem_bank/test_probe_candidates.py`가 이미 봉인).

핵심 봉인:
- ② session=None이면 조회 없이 빈 리스트(회귀 0·로그 0).
- ③ 활성 가설 mids + outside_mids가 *합쳐져* L1에 질의된다(ε-탐색 표적이 후보 풀에 실제로
  존재할 수 있어야 §2.2 규칙2가 성립).
- ④ 후보 0의 네 사유(가설 없음/오개념 미태깅/난이도 부재/전부 응답함)가 서로 다른 값.
- ⑤ 변별력: L1이 실제 후보를 돌려주면 최종 `ProbeCandidate` 리스트가 채워진다(0 → >0).
- never-break: L1 조회 예외는 흡수돼 빈 리스트로 강등(타입명 로그).
- 오개념 preload 0: 이 함수가 만드는 후보는 로그에 mids·problem_id 원문을 싣지 않는다(카운트만).
"""

from __future__ import annotations

import asyncio
import logging

import pytest

from whymath_backend.harness import wh1_probe_supply
from whymath_backend.harness.wh1_probe_supply import (
    REASON_ALL_ADMINISTERED,
    REASON_NO_DIFFICULTY,
    REASON_NO_HYPOTHESIS,
    REASON_UNTAGGED,
    ProbeSupplyFunnel,
    _target_mids,
    assemble_probe_candidate_pool,
)
from whymath_backend.l1.problem_bank.probe_candidates import ProbeCandidateQuery, ProbeCandidateRow
from whymath_backend.l4.misconception.hypothesis import MisconceptionHypothesis

_LOGGER = "whymath.harness.wh1_probe_supply"


class _FakeSession:
    """실 AsyncSession 대역 — `fetch_probe_candidates_by_mids`를 monkeypatch하므로 속성 불필요."""


def _hyp(mid: str, *, confidence: float = 0.7) -> MisconceptionHypothesis:
    return MisconceptionHypothesis(
        misconception_id=mid, confidence=confidence, turns_since_evidence=0, evidence_count=1
    )


def _row(problem_id: str, *, difficulty: float = 3.0, tags: frozenset[str]) -> ProbeCandidateRow:
    return ProbeCandidateRow(
        problem_id=problem_id, difficulty_overall=difficulty, misconception_tags=tags
    )


# ──────────────────────────────────────────────────────────────────────────
# ② session=None — 조회 skip(회귀 0)
# ──────────────────────────────────────────────────────────────────────────
class TestSessionNoneSkip:
    def test_session_none_returns_empty_without_query(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        called = False

        async def _boom(*_a: object, **_k: object) -> ProbeCandidateQuery:
            nonlocal called
            called = True
            raise AssertionError("session=None인데 L1 조회가 호출됨")

        monkeypatch.setattr(wh1_probe_supply, "fetch_probe_candidates_by_mids", _boom)
        result = asyncio.run(
            assemble_probe_candidate_pool(
                None, active_hypotheses=[_hyp("mis.a")], outside_mids=["mis.b"]
            )
        )
        assert result == []
        assert called is False

    def test_session_none_logs_nothing(self, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level(logging.INFO, logger=_LOGGER):
            asyncio.run(
                assemble_probe_candidate_pool(
                    None, active_hypotheses=[_hyp("mis.a")], outside_mids=[]
                )
            )
        assert [r for r in caplog.records if r.name == _LOGGER] == []


# ──────────────────────────────────────────────────────────────────────────
# ③ ε-탐색 성립 — 활성 가설 mids + outside_mids가 합쳐져 질의된다
# ──────────────────────────────────────────────────────────────────────────
class TestTargetMidsUnion:
    def test_dedupes_preserving_order(self) -> None:
        result = _target_mids([_hyp("mis.a"), _hyp("mis.b")], ["mis.b", "mis.c"])
        assert result == ["mis.a", "mis.b", "mis.c"]

    def test_empty_both_yields_empty(self) -> None:
        assert _target_mids([], []) == []

    def test_outside_mids_reach_l1_query_even_with_no_active_hypotheses(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """활성 가설이 없어도(콜드스타트) outside_mids만으로 조회가 일어나야 탐색이 가능하다."""
        captured: dict[str, object] = {}

        async def _fake(session: object, mids: list[str], **kwargs: object) -> ProbeCandidateQuery:
            captured["mids"] = mids
            return ProbeCandidateQuery(rows=(), tagged_count=0, tagged_with_difficulty_count=0)

        monkeypatch.setattr(wh1_probe_supply, "fetch_probe_candidates_by_mids", _fake)
        asyncio.run(
            assemble_probe_candidate_pool(
                _FakeSession(), active_hypotheses=[], outside_mids=["mis.explore"]
            )
        )
        assert captured["mids"] == ["mis.explore"]

    def test_active_and_outside_mids_both_reach_l1_query(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        captured: dict[str, object] = {}

        async def _fake(session: object, mids: list[str], **kwargs: object) -> ProbeCandidateQuery:
            captured["mids"] = mids
            return ProbeCandidateQuery(rows=(), tagged_count=0, tagged_with_difficulty_count=0)

        monkeypatch.setattr(wh1_probe_supply, "fetch_probe_candidates_by_mids", _fake)
        asyncio.run(
            assemble_probe_candidate_pool(
                _FakeSession(),
                active_hypotheses=[_hyp("mis.active")],
                outside_mids=["mis.explore"],
            )
        )
        assert captured["mids"] == ["mis.active", "mis.explore"]


# ──────────────────────────────────────────────────────────────────────────
# ⑤ 변별력 — L1이 후보를 돌려주면 최종 ProbeCandidate가 채워진다(0 → >0)
# ──────────────────────────────────────────────────────────────────────────
class TestNonEmptyPoolAssembly:
    def test_candidates_assembled_with_difficulty_conversion(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async def _fake(session: object, mids: list[str], **kwargs: object) -> ProbeCandidateQuery:
            return ProbeCandidateQuery(
                rows=(
                    _row("p1", difficulty=2.0, tags=frozenset({"mis.a", "mis.b"})),
                    _row("p2", difficulty=4.0, tags=frozenset({"mis.a"})),
                ),
                tagged_count=2,
                tagged_with_difficulty_count=2,
            )

        monkeypatch.setattr(wh1_probe_supply, "fetch_probe_candidates_by_mids", _fake)
        result = asyncio.run(
            assemble_probe_candidate_pool(
                _FakeSession(), active_hypotheses=[_hyp("mis.a")], outside_mids=[]
            )
        )
        assert len(result) == 2
        ids = {c.problem_id for c in result}
        assert ids == {"p1", "p2"}
        # difficulty_overall(1~5) → logit 변환(중앙 3.0=0) — 휴리스틱 폴백 경로.
        p1 = next(c for c in result if c.problem_id == "p1")
        assert p1.difficulty == pytest.approx(-1.0)
        assert p1.misconception_tags == frozenset({"mis.a", "mis.b"})

    def test_irt_difficulty_b_preferred_over_heuristic(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async def _fake(session: object, mids: list[str], **kwargs: object) -> ProbeCandidateQuery:
            row = ProbeCandidateRow(
                problem_id="p1",
                difficulty_overall=3.0,
                irt_difficulty_b=1.23,
                misconception_tags=frozenset({"mis.a"}),
            )
            return ProbeCandidateQuery(rows=(row,), tagged_count=1, tagged_with_difficulty_count=1)

        monkeypatch.setattr(wh1_probe_supply, "fetch_probe_candidates_by_mids", _fake)
        result = asyncio.run(
            assemble_probe_candidate_pool(
                _FakeSession(), active_hypotheses=[_hyp("mis.a")], outside_mids=[]
            )
        )
        assert result[0].difficulty == pytest.approx(1.23)


# ──────────────────────────────────────────────────────────────────────────
# ④ 후보 0의 사유 4가지 — 서로 다른 값
# ──────────────────────────────────────────────────────────────────────────
class TestFunnelReasonDistinctness:
    def test_no_hypothesis(self) -> None:
        funnel = ProbeSupplyFunnel(mids_count=0, tagged_count=0, tagged_with_difficulty_count=0)
        assert funnel.reason == REASON_NO_HYPOTHESIS

    def test_untagged(self) -> None:
        funnel = ProbeSupplyFunnel(mids_count=3, tagged_count=0, tagged_with_difficulty_count=0)
        assert funnel.reason == REASON_UNTAGGED

    def test_no_difficulty(self) -> None:
        funnel = ProbeSupplyFunnel(mids_count=3, tagged_count=5, tagged_with_difficulty_count=0)
        assert funnel.reason == REASON_NO_DIFFICULTY

    def test_all_administered(self) -> None:
        funnel = ProbeSupplyFunnel(
            mids_count=3, tagged_count=5, tagged_with_difficulty_count=2, final_count=0
        )
        assert funnel.reason == REASON_ALL_ADMINISTERED

    def test_non_empty_final_has_no_reason(self) -> None:
        funnel = ProbeSupplyFunnel(
            mids_count=3, tagged_count=5, tagged_with_difficulty_count=2, final_count=1
        )
        assert funnel.reason is None

    def test_all_four_reasons_are_pairwise_distinct(self) -> None:
        reasons = {
            REASON_NO_HYPOTHESIS,
            REASON_UNTAGGED,
            REASON_NO_DIFFICULTY,
            REASON_ALL_ADMINISTERED,
        }
        assert len(reasons) == 4  # 변별력 — 네 값이 우연히도 서로 같으면 이 설계는 실패.

    def test_untagged_logged_end_to_end(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        async def _fake(session: object, mids: list[str], **kwargs: object) -> ProbeCandidateQuery:
            return ProbeCandidateQuery(rows=(), tagged_count=0, tagged_with_difficulty_count=0)

        monkeypatch.setattr(wh1_probe_supply, "fetch_probe_candidates_by_mids", _fake)
        with caplog.at_level(logging.INFO, logger=_LOGGER):
            result = asyncio.run(
                assemble_probe_candidate_pool(
                    _FakeSession(), active_hypotheses=[_hyp("mis.a")], outside_mids=[]
                )
            )
        assert result == []
        messages = [r.getMessage() for r in caplog.records if r.name == _LOGGER]
        assert len(messages) == 1
        assert f"reason={REASON_UNTAGGED}" in messages[0]

    def test_all_administered_logged_end_to_end(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        async def _fake(session: object, mids: list[str], **kwargs: object) -> ProbeCandidateQuery:
            return ProbeCandidateQuery(rows=(), tagged_count=3, tagged_with_difficulty_count=3)

        monkeypatch.setattr(wh1_probe_supply, "fetch_probe_candidates_by_mids", _fake)
        with caplog.at_level(logging.INFO, logger=_LOGGER):
            result = asyncio.run(
                assemble_probe_candidate_pool(
                    _FakeSession(), active_hypotheses=[_hyp("mis.a")], outside_mids=[]
                )
            )
        assert result == []
        messages = [r.getMessage() for r in caplog.records if r.name == _LOGGER]
        assert len(messages) == 1
        assert f"reason={REASON_ALL_ADMINISTERED}" in messages[0]

    def test_success_logs_nothing(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        async def _fake(session: object, mids: list[str], **kwargs: object) -> ProbeCandidateQuery:
            return ProbeCandidateQuery(
                rows=(_row("p1", tags=frozenset({"mis.a"})),),
                tagged_count=1,
                tagged_with_difficulty_count=1,
            )

        monkeypatch.setattr(wh1_probe_supply, "fetch_probe_candidates_by_mids", _fake)
        with caplog.at_level(logging.INFO, logger=_LOGGER):
            result = asyncio.run(
                assemble_probe_candidate_pool(
                    _FakeSession(), active_hypotheses=[_hyp("mis.a")], outside_mids=[]
                )
            )
        assert len(result) == 1
        assert [r for r in caplog.records if r.name == _LOGGER] == []


# ──────────────────────────────────────────────────────────────────────────
# never-break — L1 조회 예외는 흡수돼 빈 리스트(타입명 로그)
# ──────────────────────────────────────────────────────────────────────────
class TestNeverBreak:
    def test_l1_query_exception_absorbed(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        async def _boom(*_a: object, **_k: object) -> ProbeCandidateQuery:
            raise ConnectionError("DB 도달 불가(테스트)")

        monkeypatch.setattr(wh1_probe_supply, "fetch_probe_candidates_by_mids", _boom)
        with caplog.at_level(logging.WARNING, logger=_LOGGER):
            result = asyncio.run(
                assemble_probe_candidate_pool(
                    _FakeSession(), active_hypotheses=[_hyp("mis.a")], outside_mids=[]
                )
            )
        assert result == []
        messages = " ".join(r.getMessage() for r in caplog.records if r.name == _LOGGER)
        assert "ConnectionError" in messages  # 침묵 실패 금지 — 예외 타입명 로그


# ──────────────────────────────────────────────────────────────────────────
# 오개념 preload 0 — 로그에 mids·problem_id 원문이 실리지 않는다(카운트만)
# ──────────────────────────────────────────────────────────────────────────
class TestNoPreloadInLogs:
    def test_reason_log_has_no_mid_or_problem_id_strings(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        sentinel_mid = "mis.ZZSENTINELZZ"

        async def _fake(session: object, mids: list[str], **kwargs: object) -> ProbeCandidateQuery:
            return ProbeCandidateQuery(rows=(), tagged_count=0, tagged_with_difficulty_count=0)

        monkeypatch.setattr(wh1_probe_supply, "fetch_probe_candidates_by_mids", _fake)
        with caplog.at_level(logging.INFO, logger=_LOGGER):
            asyncio.run(
                assemble_probe_candidate_pool(
                    _FakeSession(), active_hypotheses=[_hyp(sentinel_mid)], outside_mids=[]
                )
            )
        joined = " ".join(r.getMessage() for r in caplog.records)
        assert sentinel_mid not in joined
