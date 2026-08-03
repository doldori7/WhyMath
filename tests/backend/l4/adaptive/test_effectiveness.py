"""L4 교수법 효과 집계 — `evidence_event` → (전략×k_type×objective) 성과 (PED-03·hermetic).

핵심 관심사 셋:
  ① **표본 0은 `None`** — "측정 안 됨"이 "0%"로 위장되지 않는다(SupplyTally 선례).
  ② **처치 미상 결과는 버린다** — 무엇을 보여줬는지 모르는 결과를 임의 배정하면 측정이 오염된다.
  ③ 판정치는 **Wilson 하한**(점추정 금지).
"""

from __future__ import annotations

import inspect
import uuid
from datetime import UTC, datetime, timedelta

from whymath_backend.db.models.evidence_event import EvidenceEvent
from whymath_backend.l2.pedagogy_evidence import (
    EVENT_TYPE_OUTCOME,
    EVENT_TYPE_TREATMENT,
    META_KEY_STRATEGY,
)
from whymath_backend.l4.pedagogy.adaptive import effectiveness
from whymath_backend.l4.pedagogy.adaptive.effectiveness import (
    EffectivenessKey,
    EffectivenessStat,
    aggregate_effectiveness,
)
from whymath_backend.schema.enums import KnowledgeType

_T0 = datetime(2026, 7, 26, tzinfo=UTC)
_OBJ = "OBJ.quadratic.01"
_K = "CONCEPT"


def _treatment(
    session_id: uuid.UUID, strategy: str, *, offset_s: int = 0, objective: str = _OBJ
) -> EvidenceEvent:
    return EvidenceEvent(
        time=_T0 + timedelta(seconds=offset_s),
        session_id=session_id,
        objective_id=objective,
        k_type=_K,
        event_type=EVENT_TYPE_TREATMENT,
        meta={META_KEY_STRATEGY: strategy},
    )


def _outcome(
    session_id: uuid.UUID,
    correct: bool,
    *,
    rt_ms: int | None = None,
    offset_s: int = 10,
    objective: str = _OBJ,
) -> EvidenceEvent:
    return EvidenceEvent(
        time=_T0 + timedelta(seconds=offset_s),
        session_id=session_id,
        objective_id=objective,
        k_type=_K,
        event_type=EVENT_TYPE_OUTCOME,
        correct=correct,
        rt_ms=rt_ms,
    )


class TestEmptySampleIsUnknown:
    def test_no_rows_gives_empty_report(self) -> None:
        report = aggregate_effectiveness([])
        assert report.stats == {}
        assert report.total_trials == 0

    def test_zero_trial_stat_reports_none_not_zero(self) -> None:
        """표본 0 → `None`. 0.0을 돌려주면 "측정 실패"가 "성과 0%"로 위장된다."""
        stat = EffectivenessStat()
        assert stat.success_rate is None
        assert stat.success_rate_lower is None
        assert stat.mean_rt_ms is None


class TestAttribution:
    def test_joins_outcome_to_treatment_by_session(self) -> None:
        sid = uuid.uuid4()
        report = aggregate_effectiveness(
            [_treatment(sid, "SOCRATIC"), _outcome(sid, True, rt_ms=4000)]
        )
        key = EffectivenessKey(strategy="SOCRATIC", k_type=_K, objective_id=_OBJ)
        assert report.stats[key].trials == 1
        assert report.stats[key].successes == 1
        assert report.stats[key].mean_rt_ms == 4000

    def test_drops_outcome_without_treatment(self) -> None:
        """처치 미상 결과는 버린다 — 임의 귀속은 측정 오염이다."""
        report = aggregate_effectiveness([_outcome(uuid.uuid4(), True)])
        assert report.stats == {}
        assert report.total_trials == 0

    def test_attribution_is_discriminative(self) -> None:
        """**변별력** — 같은 결과라도 처치 행 유무만으로 집계 여부가 뒤집힌다."""
        sid = uuid.uuid4()
        outcome = _outcome(sid, True)
        without = aggregate_effectiveness([outcome])
        with_treatment = aggregate_effectiveness([_treatment(sid, "DIRECT"), _outcome(sid, True)])
        assert without.total_trials == 0
        assert with_treatment.total_trials == 1

    def test_earliest_treatment_wins_within_session(self) -> None:
        """세션에 처치가 여러 건이면 가장 이른 것 — 결과가 그 이후에 났다는 인과 순서 보존."""
        sid = uuid.uuid4()
        report = aggregate_effectiveness(
            [
                _treatment(sid, "ANALOGY", offset_s=5),
                _treatment(sid, "DIRECT", offset_s=0),
                _outcome(sid, True, offset_s=20),
            ]
        )
        assert list(report.stats)[0].strategy == "DIRECT"

    def test_missing_correct_is_not_counted(self) -> None:
        """정답 여부 미기록 행은 분모에 넣지 않는다(모르면 세지 않는다)."""
        sid = uuid.uuid4()
        outcome = _outcome(sid, True)
        outcome.correct = None
        assert aggregate_effectiveness([_treatment(sid, "SOCRATIC"), outcome]).total_trials == 0

    def test_treatment_without_strategy_meta_is_dropped(self) -> None:
        sid = uuid.uuid4()
        treatment = _treatment(sid, "SOCRATIC")
        treatment.meta = {}
        assert aggregate_effectiveness([treatment, _outcome(sid, True)]).total_trials == 0


class TestWilsonJudgement:
    def test_lower_bound_is_below_point_estimate(self) -> None:
        """게이트 판정축은 하한 — 얇은 표본에서 점추정보다 보수적이어야 한다."""
        sids = [uuid.uuid4() for _ in range(4)]
        rows: list[EvidenceEvent] = []
        for i, sid in enumerate(sids):
            rows.append(_treatment(sid, "SOCRATIC"))
            rows.append(_outcome(sid, correct=i < 3))  # 3/4 정답
        stat = aggregate_effectiveness(rows).stats[
            EffectivenessKey(strategy="SOCRATIC", k_type=_K, objective_id=_OBJ)
        ]
        assert stat.success_rate == 0.75
        assert stat.success_rate_lower is not None
        assert stat.success_rate_lower < stat.success_rate

    def test_separates_strategies(self) -> None:
        """전략별로 셀이 갈린다 — 합쳐 버리면 비교가 불가능하다."""
        s1, s2 = uuid.uuid4(), uuid.uuid4()
        report = aggregate_effectiveness(
            [
                _treatment(s1, "SOCRATIC"),
                _outcome(s1, True),
                _treatment(s2, "DIRECT"),
                _outcome(s2, False),
            ]
        )
        assert len(report.stats) == 2
        json_cells = report.to_json()["cells"]
        assert isinstance(json_cells, list)
        assert {c["strategy"] for c in json_cells} == {"SOCRATIC", "DIRECT"}


class TestKTypeLabelNotMangled:
    """PED-12 회귀 — 실 DB native enum 행에서도 라벨이 "KnowledgeType.CONCEPT"로 맹글링되지 않는다.

    study.py 동일 사고(2026-07-29)의 adaptive 판. `str(outcome.k_type)`이 str-mixin Enum이라
    낸 틀린 라벨을 `.value`(또는 이미 평문 문자열인 픽스처는 그대로)로 정규화하는 회귀 동결.
    """

    def test_real_enum_instance_yields_bare_value_label(self) -> None:
        sid = uuid.uuid4()
        treatment = _treatment(sid, "SOCRATIC")
        outcome = _outcome(sid, True)
        outcome.k_type = KnowledgeType.CONCEPT  # 실 DB native enum 행을 시뮬레이션
        report = aggregate_effectiveness([treatment, outcome])
        key = EffectivenessKey(strategy="SOCRATIC", k_type="CONCEPT", objective_id=_OBJ)
        assert report.stats[key].trials == 1
        assert all(not k.k_type.startswith("KnowledgeType.") for k in report.stats)


class TestKTypeValueSourceFrozen:
    """소스 스캔 동결 — `str(outcome.k_type)` 맹글링 패턴의 재발을 막는다 (PED-06 선례 확장)."""

    def test_source_has_no_str_mangled_k_type(self) -> None:
        source = inspect.getsource(effectiveness)
        assert "str(outcome.k_type)" not in source, (
            "str(outcome.k_type)은 'KnowledgeType.CONCEPT'로 맹글링된다 — "
            "adaptive 효과 집계의 보고 라벨이 틀리게 기록된다(PED-12·2026-07-29 실측). "
            "getattr(outcome.k_type, 'value', outcome.k_type)을 쓰라."
        )
        assert 'getattr(outcome.k_type, "value", outcome.k_type)' in source

    def test_mangling_premise_still_holds(self) -> None:
        # 이 동결의 전제 실측 — str-mixin Enum의 str()은 값이 아니다(전제가 바뀌면 동결 재검토).
        assert str(KnowledgeType.CONCEPT) != KnowledgeType.CONCEPT.value
