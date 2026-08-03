"""L4 오케스트레이션 `assemble_probe_candidates` 단위테스트 — REC-02 ②③④ (hermetic).

`l1.misconception.probe_lookup.lookup_probe_candidates_by_mids`를 monkeypatch로 갈음한다
(L1 조회 자체의 정합성은 `test_misconception_probe_lookup.py`/`..._integration.py`가 이미
검증 — 이 파일은 *오케스트레이션*만 본다: 합집합 조립·ProbeCandidate 변환·사유 계상·로깅).

  ① target_mids 합집합 — 활성 가설 ∪ outside_mids(ε-탐색 풀 커버리지 근거)
  ② no_target_mids — 겨냥할 mid 자체가 없으면 조회 없이 즉시 빈 풀
  ③ untagged_mid — 코퍼스에 매칭 안 된 target mid 개수(L1의 matched_target_mids 차집합)
  ④ 난이도 변환 — irt_difficulty_b 우선·difficulty_overall 폴백(resolve_item_difficulty_b 재사용)
  ⑤ discrimination 폴백 — irt_a None/비양수면 1.0
  ⑥ misconception_tags — 문항의 distractor_map 전체 태그(검색 부분집합 아님)를 그대로 보존
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any
from unittest.mock import AsyncMock

import pytest

from whymath_backend.l1.misconception.probe_lookup import ProbeCandidateRow, ProbeLookupResult
from whymath_backend.l4.misconception import probe_supply as probe_supply_mod
from whymath_backend.l4.misconception.hypothesis import MisconceptionHypothesis
from whymath_backend.l4.misconception.probe_supply import assemble_probe_candidates

_UID = uuid.uuid4()


def _hyp(mid: str, confidence: float = 0.8) -> MisconceptionHypothesis:
    return MisconceptionHypothesis(
        misconception_id=mid, confidence=confidence, turns_since_evidence=0, evidence_count=1
    )


def _row(
    *,
    difficulty_overall: float | None = 3.0,
    irt_difficulty_b: float | None = None,
    irt_a: float | None = None,
    tags: frozenset[str] = frozenset({"M-A"}),
) -> ProbeCandidateRow:
    return ProbeCandidateRow(
        problem_id=uuid.uuid4(),
        difficulty_overall=difficulty_overall,
        irt_difficulty_b=irt_difficulty_b,
        irt_a=irt_a,
        misconception_tags=tags,
    )


def _patch_lookup(monkeypatch: pytest.MonkeyPatch, result: ProbeLookupResult) -> AsyncMock:
    mock = AsyncMock(return_value=result)
    monkeypatch.setattr(probe_supply_mod, "lookup_probe_candidates_by_mids", mock)
    return mock


def _run(coro: Any) -> Any:
    return asyncio.run(coro)


class TestNoTargetMids:
    def test_empty_active_and_outside_skips_lookup(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mock = _patch_lookup(
            monkeypatch,
            ProbeLookupResult(
                kept=(), missing_difficulty=0, fully_administered=0, matched_target_mids=frozenset()
            ),
        )
        outcome = _run(
            assemble_probe_candidates(
                object(),
                user_id=_UID,
                active_hypotheses=[],
                outside_mids=[],
                seat="test-seat",
            )
        )
        assert outcome.candidates == ()
        assert outcome.exclusions.no_target_mids == 1
        assert outcome.exclusions.untagged_mid == 0
        mock.assert_not_awaited()  # 조회 자체를 안 한다


class TestTargetMidsUnion:
    def test_active_and_outside_both_flow_into_lookup(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """③ ε-탐색 성립 근거 — 활성 세트 밖(outside_mids)도 target_mids에 합쳐져 조회된다."""
        mock = _patch_lookup(
            monkeypatch,
            ProbeLookupResult(
                kept=(_row(tags=frozenset({"M-OUTSIDE"})),),
                missing_difficulty=0,
                fully_administered=0,
                matched_target_mids=frozenset({"M-ACTIVE", "M-OUTSIDE"}),
            ),
        )
        outcome = _run(
            assemble_probe_candidates(
                object(),
                user_id=_UID,
                active_hypotheses=[_hyp("M-ACTIVE")],
                outside_mids=["M-OUTSIDE"],
                seat="test-seat",
            )
        )
        called_kwargs = mock.await_args.kwargs
        assert called_kwargs["target_mids"] == frozenset({"M-ACTIVE", "M-OUTSIDE"})
        # 탐색 겨냥(M-OUTSIDE)을 판별할 후보가 실제로 풀에 담겼다.
        tags = {t for c in outcome.candidates for t in c.misconception_tags}
        assert "M-OUTSIDE" in tags


class TestUntaggedMid:
    def test_untagged_target_mid_counted(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _patch_lookup(
            monkeypatch,
            ProbeLookupResult(
                kept=(),
                missing_difficulty=0,
                fully_administered=0,
                matched_target_mids=frozenset(),  # M-A가 코퍼스에 전혀 없음
            ),
        )
        outcome = _run(
            assemble_probe_candidates(
                object(),
                user_id=_UID,
                active_hypotheses=[_hyp("M-A")],
                outside_mids=[],
                seat="test-seat",
            )
        )
        assert outcome.exclusions.untagged_mid == 1
        assert outcome.exclusions.no_target_mids == 0
        assert outcome.candidates == ()


class TestMissingDifficultyAndFullyAdministered:
    def test_reasons_pass_through_from_lookup(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _patch_lookup(
            monkeypatch,
            ProbeLookupResult(
                kept=(),
                missing_difficulty=2,
                fully_administered=3,
                matched_target_mids=frozenset({"M-A"}),
            ),
        )
        outcome = _run(
            assemble_probe_candidates(
                object(),
                user_id=_UID,
                active_hypotheses=[_hyp("M-A")],
                outside_mids=[],
                seat="test-seat",
            )
        )
        assert outcome.exclusions.missing_difficulty == 2
        assert outcome.exclusions.fully_administered == 3


class TestCandidateConversion:
    def test_irt_difficulty_b_preferred_over_difficulty_overall(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch_lookup(
            monkeypatch,
            ProbeLookupResult(
                kept=(_row(difficulty_overall=5.0, irt_difficulty_b=1.25),),
                missing_difficulty=0,
                fully_administered=0,
                matched_target_mids=frozenset({"M-A"}),
            ),
        )
        outcome = _run(
            assemble_probe_candidates(
                object(),
                user_id=_UID,
                active_hypotheses=[_hyp("M-A")],
                outside_mids=[],
                seat="test-seat",
            )
        )
        assert outcome.candidates[0].difficulty == 1.25

    def test_difficulty_overall_fallback_when_no_irt_b(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch_lookup(
            monkeypatch,
            ProbeLookupResult(
                kept=(_row(difficulty_overall=3.0, irt_difficulty_b=None),),
                missing_difficulty=0,
                fully_administered=0,
                matched_target_mids=frozenset({"M-A"}),
            ),
        )
        outcome = _run(
            assemble_probe_candidates(
                object(),
                user_id=_UID,
                active_hypotheses=[_hyp("M-A")],
                outside_mids=[],
                seat="test-seat",
            )
        )
        # difficulty_to_logit(3.0) == 0.0 (중앙값 3 → b=0).
        assert outcome.candidates[0].difficulty == 0.0

    def test_discrimination_falls_back_to_one_when_irt_a_missing_or_nonpositive(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch_lookup(
            monkeypatch,
            ProbeLookupResult(
                kept=(_row(irt_a=None), _row(irt_a=-0.5)),
                missing_difficulty=0,
                fully_administered=0,
                matched_target_mids=frozenset({"M-A"}),
            ),
        )
        outcome = _run(
            assemble_probe_candidates(
                object(),
                user_id=_UID,
                active_hypotheses=[_hyp("M-A")],
                outside_mids=[],
                seat="test-seat",
            )
        )
        assert all(c.discrimination == 1.0 for c in outcome.candidates)

    def test_discrimination_uses_irt_a_when_positive(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _patch_lookup(
            monkeypatch,
            ProbeLookupResult(
                kept=(_row(irt_a=1.7),),
                missing_difficulty=0,
                fully_administered=0,
                matched_target_mids=frozenset({"M-A"}),
            ),
        )
        outcome = _run(
            assemble_probe_candidates(
                object(),
                user_id=_UID,
                active_hypotheses=[_hyp("M-A")],
                outside_mids=[],
                seat="test-seat",
            )
        )
        assert outcome.candidates[0].discrimination == 1.7

    def test_full_tag_set_preserved_not_search_subset(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """⑥ misconception_tags엔 이 문항의 distractor_map 전체 태그가 그대로 담긴다."""
        _patch_lookup(
            monkeypatch,
            ProbeLookupResult(
                kept=(_row(tags=frozenset({"M-A", "M-COMPETING"})),),
                missing_difficulty=0,
                fully_administered=0,
                matched_target_mids=frozenset({"M-A"}),
            ),
        )
        outcome = _run(
            assemble_probe_candidates(
                object(),
                user_id=_UID,
                active_hypotheses=[_hyp("M-A")],
                outside_mids=[],
                seat="test-seat",
            )
        )
        assert outcome.candidates[0].misconception_tags == frozenset({"M-A", "M-COMPETING"})

    def test_problem_id_cast_to_str(self, monkeypatch: pytest.MonkeyPatch) -> None:
        pid = uuid.uuid4()
        row = ProbeCandidateRow(
            problem_id=pid,
            difficulty_overall=3.0,
            irt_difficulty_b=None,
            irt_a=None,
            misconception_tags=frozenset({"M-A"}),
        )
        _patch_lookup(
            monkeypatch,
            ProbeLookupResult(
                kept=(row,),
                missing_difficulty=0,
                fully_administered=0,
                matched_target_mids=frozenset({"M-A"}),
            ),
        )
        outcome = _run(
            assemble_probe_candidates(
                object(),
                user_id=_UID,
                active_hypotheses=[_hyp("M-A")],
                outside_mids=[],
                seat="test-seat",
            )
        )
        assert outcome.candidates[0].problem_id == str(pid)
        assert isinstance(outcome.candidates[0].problem_id, str)
