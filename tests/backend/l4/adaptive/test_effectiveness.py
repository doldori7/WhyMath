"""L4 교수법 효과 집계 — `evidence_event` → (전략×k_type×objective) 성과 (PED-03·hermetic).

핵심 관심사 셋:
  ① **표본 0은 `None`** — "측정 안 됨"이 "0%"로 위장되지 않는다(SupplyTally 선례).
  ② **처치 미상 결과는 버린다** — 무엇을 보여줬는지 모르는 결과를 임의 배정하면 측정이 오염된다.
  ③ 판정치는 **Wilson 하한**(점추정 금지).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from whymath_backend.db.models.evidence_event import EvidenceEvent
from whymath_backend.l2.pedagogy_evidence import (
    EVENT_TYPE_OUTCOME,
    EVENT_TYPE_TREATMENT,
    META_KEY_STRATEGY,
)
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


class TestKnowledgeTypeLabelNormalization:
    """enum 멤버 입력 → 집계 키는 PG 라벨 (PED-25 ②, 구 PED-12).

    사고 경위: `_K = "CONCEPT"` 평문 픽스처만 쓰는 기존 테스트는 이 결함을 못 잡는다 —
    실 PG 왕복(native enum 컬럼)에서 SQLAlchemy가 돌려주는 것은 `KnowledgeType` **멤버**이고,
    `str(멤버)`는 `"KnowledgeType.CONCEPT"`(라벨 집합 밖)이다(api/study.py 동형 사고
    2026-08-11 실 PG 실측·`tests/backend/api/test_study_k_type_enum_binding.py` 참조).
    맹글링된 키는 리포트·정책 평가의 "CONCEPT" 셀과 영원히 조인되지 않는다(침묵 오염).
    """

    def test_enum_member_input_aggregates_under_pg_label(self) -> None:
        sid = uuid.uuid4()
        treatment = _treatment(sid, "SOCRATIC")
        outcome = _outcome(sid, True)
        # 실 PG 경로 재현 — ORM이 돌려주는 enum 멤버를 그대로 넣는다.
        treatment.k_type = KnowledgeType.CONCEPT
        outcome.k_type = KnowledgeType.CONCEPT
        report = aggregate_effectiveness([treatment, outcome])
        key = EffectivenessKey(strategy="SOCRATIC", k_type="CONCEPT", objective_id=_OBJ)
        assert report.stats[key].trials == 1
        assert "KnowledgeType.CONCEPT" not in {k.k_type for k in report.stats}

    def test_plain_string_input_still_aggregates(self) -> None:
        """멱등성 — 평문 라벨(기존 픽스처 경로)도 같은 셀로 모인다."""
        sid = uuid.uuid4()
        report = aggregate_effectiveness([_treatment(sid, "SOCRATIC"), _outcome(sid, True)])
        key = EffectivenessKey(strategy="SOCRATIC", k_type="CONCEPT", objective_id=_OBJ)
        assert report.stats[key].trials == 1
