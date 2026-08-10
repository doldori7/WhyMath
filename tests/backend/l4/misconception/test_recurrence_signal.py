"""오개념 재발신호 단위테스트 — MISC-06 (hermetic·PG 불요·fake session·결정론).

04e §4의 좁힌 "예측"(같은 오개념의 재발 가능성만·BKT/DKT 비융합·낙인 방지)을 검증한다.
`get_recurrence_signals`(읽기 전용 산출)·`order_mids_by_recurrence`(outside_mids 재정렬 —
유일 소비)·`assemble_warmstart_probe_hints`(ⓔ 배선)를 fake async 세션으로 검증한다
(실 PG·실 네트워크 0 — `test_warmstart.py`·`test_misconception_slip_report.py` 스타일 답습).

검증 축(태스크 필수 케이스):
  ① 정렬 정확성 — 재발 이력 mid가 앞으로(count desc → recency desc → 원순서 동률 결정론)
  ② 하위호환 — 신호 없음/이력 없음이면 기존 순서 완전 불변
  ③ 변별력(양방향) — 재정렬이 `resolve_probe_target`의 ε-탐색 표적을 실제로 바꾼다
     (`test_wh1_select_probe_variance.py`의 "신호가 선택을 바꾼다" 선례)
  ④ 낙인·경계 동결 — 활성 가설은 신호에 안 담기고(활용 타깃 불변) 입력 비변형·주입 0
  ⑤ stateless — `user_id=None`이면 재발 조회 0·기존 동작 그대로(reactive·graceful)
  ⑥ 반박(−1) 배제 — 반박 레코드는 재발 카운트·최근성 어느 쪽에도 안 섞인다
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

import pytest

from whymath_backend.l4.misconception.hypothesis import MisconceptionHypothesis
from whymath_backend.l4.misconception.hypothesis_store import (
    MisconceptionRecurrenceSignal,
    get_recurrence_signals,
    order_mids_by_recurrence,
)
from whymath_backend.l4.misconception.probe_selection import resolve_probe_target
from whymath_backend.l4.misconception.warmstart import assemble_warmstart_probe_hints


# ──────────────────────────────────────────────────────────────────────────
# fake async 세션 — 질의를 *첫 컬럼명*으로 라우팅(스냅샷/고빈도 카탈로그 둘 다 2열이라
# 컬럼 수만으로는 구분 불가 — test_warmstart.py의 ncols 라우팅을 이름 라우팅으로 확장)
# ──────────────────────────────────────────────────────────────────────────
class _FakeEvidence:
    """`EvidenceLink` 최소 대역 — 집계가 읽는 3필드(mid·polarity·created_at)만."""

    def __init__(self, mid: str, polarity: int, created_at: datetime) -> None:
        self.misconception_id = mid
        self.polarity = polarity
        self.created_at = created_at


class _FakeScalars:
    def __init__(self, items: list[Any]) -> None:
        self._items = items

    def all(self) -> list[Any]:
        return self._items


class _FakeResult:
    def __init__(self, rows: list[Any] | None = None, entities: list[Any] | None = None) -> None:
        self._rows = rows or []
        self._entities = entities or []

    def all(self) -> list[Any]:
        return self._rows

    def scalars(self) -> _FakeScalars:
        return _FakeScalars(self._entities)


class _FakeSession:
    """AsyncSession 최소 흉내 — 재발신호·웜스타트 질의만 canned 응답(읽기 전용·add/flush 부재).

    쓰기 메서드(add/flush/commit)를 아예 정의하지 않는다 — 검증 대상이 쓰기를 시도하면
    AttributeError로 즉사한다(읽기 전용 계약의 구조적 검증). 질의 카운터로 reactive(⑤ —
    user_id 없으면 재발 조회 0)를 실측한다.
    """

    def __init__(
        self,
        *,
        snapshot_rows: list[tuple[str, bool]] | None = None,
        evidence: list[_FakeEvidence] | None = None,
        high_freq_rows: list[tuple[str, float | None]] | None = None,
        evidence_error: Exception | None = None,
    ) -> None:
        self._snapshot_rows = snapshot_rows or []
        self._evidence = evidence or []
        self._high_freq_rows = high_freq_rows or []
        self._evidence_error = evidence_error
        self.snapshot_queries = 0
        self.evidence_queries = 0
        self.high_freq_queries = 0

    async def execute(self, statement: Any) -> _FakeResult:
        descs = statement.column_descriptions
        first_name = descs[0]["name"]
        if len(descs) == 2 and first_name == "misconception_id":
            self.snapshot_queries += 1
            return _FakeResult(rows=list(self._snapshot_rows))
        if len(descs) == 2 and first_name == "mis_id":
            self.high_freq_queries += 1
            return _FakeResult(rows=list(self._high_freq_rows))
        # 나머지는 EvidenceLink 엔티티 select(`get_evidence_for_student`).
        assert first_name == "EvidenceLink", f"예상 밖 질의: {first_name}"
        self.evidence_queries += 1
        if self._evidence_error is not None:
            raise self._evidence_error
        return _FakeResult(entities=list(self._evidence))


def _run(coro: Any) -> Any:
    return asyncio.run(coro)


def _ts(day: int, hour: int = 0) -> datetime:
    return datetime(2026, 8, day, hour, tzinfo=timezone.utc)


def _signal(
    mid: str, *, count: int, last: datetime, had_row: bool = True
) -> MisconceptionRecurrenceSignal:
    return MisconceptionRecurrenceSignal(
        misconception_id=mid,
        prior_support_count=count,
        last_support_at=last,
        had_hypothesis_row=had_row,
    )


def _hyp(mid: str, confidence: float) -> MisconceptionHypothesis:
    return MisconceptionHypothesis(
        misconception_id=mid, confidence=confidence, turns_since_evidence=0, evidence_count=1
    )


_UID = uuid.uuid4()


# ──────────────────────────────────────────────────────────────────────────
# ① 정렬 정확성 — count desc → recency desc → 원순서(안정 정렬 동률 결정론)
# ──────────────────────────────────────────────────────────────────────────
class TestOrderingCorrectness:
    def test_recurrence_history_moves_to_front_by_count_desc(self) -> None:
        """지지 횟수 큰 mid가 앞으로 — 신호 없는 mid는 원래 상대 순서로 뒤."""
        signals = {
            "mis.c": _signal("mis.c", count=3, last=_ts(1)),
            "mis.b": _signal("mis.b", count=1, last=_ts(1)),
        }
        out = order_mids_by_recurrence(["mis.a", "mis.b", "mis.c", "mis.d"], signals)
        assert out == ["mis.c", "mis.b", "mis.a", "mis.d"]

    def test_count_tie_broken_by_recency_desc(self) -> None:
        """count 동률이면 last_support_at 최신순."""
        signals = {
            "mis.old": _signal("mis.old", count=2, last=_ts(1)),
            "mis.new": _signal("mis.new", count=2, last=_ts(5)),
        }
        out = order_mids_by_recurrence(["mis.x", "mis.old", "mis.new"], signals)
        assert out == ["mis.new", "mis.old", "mis.x"]

    def test_full_tie_preserves_original_order(self) -> None:
        """count·recency 완전 동률은 원래 순서 보존(안정 정렬 — 입력 순서가 곧 tiebreak)."""
        signals = {
            "mis.a": _signal("mis.a", count=2, last=_ts(3)),
            "mis.b": _signal("mis.b", count=2, last=_ts(3)),
        }
        assert order_mids_by_recurrence(["mis.a", "mis.b"], signals) == ["mis.a", "mis.b"]
        assert order_mids_by_recurrence(["mis.b", "mis.a"], signals) == ["mis.b", "mis.a"]

    def test_signals_never_inject_new_mids(self) -> None:
        """signals에만 있는 mid는 결과에 추가되지 않는다 — 우선순위 신호일 뿐 공급원 아님(04e §5)."""
        signals = {"mis.ghost": _signal("mis.ghost", count=9, last=_ts(9))}
        assert order_mids_by_recurrence(["mis.a"], signals) == ["mis.a"]


# ──────────────────────────────────────────────────────────────────────────
# ② 하위호환 — 신호 없음이면 기존 순서 완전 불변
# ──────────────────────────────────────────────────────────────────────────
class TestBackwardsCompatNoSignal:
    def test_empty_signals_identity_order(self) -> None:
        base = ["mis.a", "mis.b", "mis.c"]
        assert order_mids_by_recurrence(base, {}) == base

    def test_unmatched_signals_identity_order(self) -> None:
        """이력이 있어도 입력 풀과 안 겹치면 순서 불변."""
        signals = {"mis.other": _signal("mis.other", count=5, last=_ts(2))}
        base = ["mis.a", "mis.b"]
        assert order_mids_by_recurrence(base, signals) == base


# ──────────────────────────────────────────────────────────────────────────
# ③ 변별력(양방향) — 재정렬이 ε-탐색 probe 표적을 실제로 바꾼다
# ──────────────────────────────────────────────────────────────────────────
class TestSignalChangesProbeTarget:
    def test_reorder_changes_exploration_target_bidirectional(self) -> None:
        """같은 턴·같은 활성 가설에서 정렬 전=mis.a, 정렬 후=mis.b — 신호가 선택을 바꾼다."""
        active = [_hyp("mis.active", 0.8)]
        base = ["mis.a", "mis.b"]
        # 정렬 전 — ε-탐색 턴(5)은 outside_mids[0]="mis.a"를 겨냥한다.
        before = resolve_probe_target(active, base, turn_index=5)
        assert before is not None
        assert before.is_exploration is True
        assert before.target_misconception_id == "mis.a"
        # "mis.b"에만 재발 이력 → 재정렬 후 첫 표적이 "mis.b"로 바뀐다.
        signals = {"mis.b": _signal("mis.b", count=2, last=_ts(3))}
        reordered = order_mids_by_recurrence(base, signals)
        assert reordered == ["mis.b", "mis.a"]
        after = resolve_probe_target(active, reordered, turn_index=5)
        assert after is not None
        assert after.target_misconception_id == "mis.b"
        assert before.target_misconception_id != after.target_misconception_id  # 변별력

    def test_no_signal_keeps_original_target(self) -> None:
        """신호가 없으면 표적도 그대로 — 재정렬 자체가 무동작이라 하위호환."""
        active = [_hyp("mis.active", 0.8)]
        base = ["mis.a", "mis.b"]
        target = resolve_probe_target(active, order_mids_by_recurrence(base, {}), turn_index=5)
        assert target is not None
        assert target.target_misconception_id == "mis.a"


# ──────────────────────────────────────────────────────────────────────────
# ④ 낙인·경계 동결 — 활성 가설 무변조(개입 경로 공유)·입력 비변형
# ──────────────────────────────────────────────────────────────────────────
class TestActiveHypothesesFrozen:
    def test_signals_exclude_active_mids(self) -> None:
        """활성(is_active=True) mid는 신호에 안 담긴다 — 재발은 '비활성' 전용(낙인·정의 정합)."""
        session = _FakeSession(
            snapshot_rows=[("mis.act", True), ("mis.dorm", False)],
            evidence=[
                _FakeEvidence("mis.act", 1, _ts(1)),
                _FakeEvidence("mis.dorm", 1, _ts(2)),
            ],
        )
        signals = _run(get_recurrence_signals(session, _UID))
        assert set(signals) == {"mis.dorm"}

    def test_order_does_not_mutate_input(self) -> None:
        """입력 시퀀스 비변형 — 새 리스트 반환(활성 리스트 공유 소비처 보호와 동형 원칙)."""
        base = ["mis.a", "mis.b", "mis.c"]
        before = list(base)
        out = order_mids_by_recurrence(base, {"mis.c": _signal("mis.c", count=2, last=_ts(1))})
        assert base == before  # 입력 그대로
        assert out is not base
        assert out == ["mis.c", "mis.a", "mis.b"]

    def test_exploitation_target_unaffected_by_reordered_outside(self) -> None:
        """비탐색(활용) 턴은 재정렬된 outside가 있어도 최상위 *활성 가설*을 그대로 겨냥한다.

        재발신호는 ε-탐색 우선순위에만 닿고, 개입 경로와 공유되는 active_hypotheses의
        순서·내용·활용 타깃엔 어떤 영향도 없다(acceptance ① — 코칭강도 결정 미사용).
        """
        active = [_hyp("mis.top", 0.9), _hyp("mis.second", 0.5)]
        reordered = ["mis.b", "mis.a"]  # 재발신호로 재정렬됐다고 가정한 outside
        target = resolve_probe_target(active, reordered, turn_index=3)  # 비탐색 턴
        assert target is not None
        assert target.is_exploration is False
        assert target.target_misconception_id == "mis.top"
        assert target.competing_mids == frozenset({"mis.second"})
        # 활성 가설 시퀀스 무변조(순서·내용 그대로 — 개입 경로가 이 리스트를 공유한다).
        assert [h.misconception_id for h in active] == ["mis.top", "mis.second"]


# ──────────────────────────────────────────────────────────────────────────
# ⑤ stateless·배선 — user_id 없으면 재발 조회 0, 있으면 재정렬(warmstart ⓔ)
# ──────────────────────────────────────────────────────────────────────────
class TestWarmstartWiring:
    def test_user_id_none_skips_recurrence_queries_and_keeps_order(self) -> None:
        """stateless 경로(user_id=None) — 재발 조회 자체가 0이고 기존 순서 그대로(하위호환)."""
        session = _FakeSession(
            high_freq_rows=[("M0001", 0.9), ("M0002", 0.8)],
            snapshot_rows=[("M0002", False)],
            evidence=[_FakeEvidence("M0002", 1, _ts(1))],
        )
        out = _run(assemble_warmstart_probe_hints(session, domain="d"))
        assert out == ["M0001", "M0002"]
        assert session.snapshot_queries == 0  # reactive — 귀속 학생 없으면 조회조차 안 한다
        assert session.evidence_queries == 0

    def test_user_id_reorders_by_recurrence(self) -> None:
        """user_id가 있으면 재발 이력 있는 M0002가 첫 탐색 표적으로 앞선다(ⓔ 배선 실증)."""
        session = _FakeSession(
            high_freq_rows=[("M0001", 0.9), ("M0002", 0.8)],
            snapshot_rows=[("M0002", False)],
            evidence=[_FakeEvidence("M0002", 1, _ts(1))],
        )
        out = _run(assemble_warmstart_probe_hints(session, domain="d", user_id=_UID))
        assert out == ["M0002", "M0001"]
        assert session.snapshot_queries == 1
        assert session.evidence_queries == 1
        # 경계 동결 — 반환은 여전히 순수 mis_id 문자열 리스트(코칭 필드 실을 자리 없음).
        assert all(isinstance(m, str) for m in out)

    def test_recurrence_failure_falls_back_to_base_order(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """신호 조회 실패는 힌트를 깨지 않는다 — 기존 순서 + 예외 타입명 로그(침묵 실패 금지)."""
        session = _FakeSession(
            high_freq_rows=[("M0001", 0.9), ("M0002", 0.8)],
            snapshot_rows=[("M0002", False)],
            evidence_error=RuntimeError("evidence 조회 실패"),
        )
        with caplog.at_level(logging.WARNING, logger="whymath.l4.misconception.warmstart"):
            out = _run(assemble_warmstart_probe_hints(session, domain="d", user_id=_UID))
        assert out == ["M0001", "M0002"]  # never-break — 기본 힌트 생존
        assert any("RuntimeError" in rec.getMessage() for rec in caplog.records)

    def test_empty_pool_skips_recurrence_queries(self) -> None:
        """조립 결과가 비면 재발 조회도 없다(빈 리스트 재정렬은 무의미 — 쿼리 절약)."""
        session = _FakeSession(high_freq_rows=[])
        out = _run(assemble_warmstart_probe_hints(session, domain="d", user_id=_UID))
        assert out == []
        assert session.snapshot_queries == 0
        assert session.evidence_queries == 0


# ──────────────────────────────────────────────────────────────────────────
# ⑥ 반박(−1) 배제 + 집계 정확성
# ──────────────────────────────────────────────────────────────────────────
class TestGetRecurrenceSignals:
    def test_refutation_only_mid_absent(self) -> None:
        """반박(−1)만 있는 mid는 재발 후보가 아니다 — 신호 자체가 없다."""
        session = _FakeSession(
            snapshot_rows=[("mis.r", False)],
            evidence=[
                _FakeEvidence("mis.r", -1, _ts(1)),
                _FakeEvidence("mis.r", -1, _ts(2)),
            ],
        )
        signals = _run(get_recurrence_signals(session, _UID))
        assert signals == {}

    def test_refutation_not_mixed_into_count_or_recency(self) -> None:
        """+1만 카운트하고, 최근성도 +1 레코드의 최신 created_at(−1이 더 늦어도 무시)."""
        session = _FakeSession(
            snapshot_rows=[("mis.m", False)],
            evidence=[
                _FakeEvidence("mis.m", 1, _ts(1)),
                _FakeEvidence("mis.m", 1, _ts(2)),
                _FakeEvidence("mis.m", -1, _ts(9)),  # 반박이 가장 최근이어도 최근성에 안 섞임
            ],
        )
        signals = _run(get_recurrence_signals(session, _UID))
        assert set(signals) == {"mis.m"}
        assert signals["mis.m"].prior_support_count == 2
        assert signals["mis.m"].last_support_at == _ts(2)
        assert signals["mis.m"].had_hypothesis_row is True

    def test_no_snapshot_row_still_counts_with_flag(self) -> None:
        """스냅샷 행이 없어도(가설 미형성 이력) 지지 증거가 있으면 재발 후보 — 행 부재를 표기."""
        session = _FakeSession(
            snapshot_rows=[],
            evidence=[_FakeEvidence("mis.n", 1, _ts(4))],
        )
        signals = _run(get_recurrence_signals(session, _UID))
        assert set(signals) == {"mis.n"}
        assert signals["mis.n"].had_hypothesis_row is False

    def test_recency_is_max_regardless_of_row_order(self) -> None:
        """최근성은 max(created_at) — 행 순서가 흔들려도 결정론(방어적 max 추적)."""
        session = _FakeSession(
            snapshot_rows=[("mis.m", False)],
            evidence=[
                _FakeEvidence("mis.m", 1, _ts(5)),
                _FakeEvidence("mis.m", 1, _ts(2)),  # 뒤 행이 더 과거여도
            ],
        )
        signals = _run(get_recurrence_signals(session, _UID))
        assert signals["mis.m"].last_support_at == _ts(5)
