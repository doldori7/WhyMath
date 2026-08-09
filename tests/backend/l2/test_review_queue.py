"""L2 복습 우선순위 큐 — `_rank_items`(순수) 단위테스트 (hermetic·DB 세션 불요).

`fetch_review_queue`가 DB에서 가져온 `(concept_id, concept_code, concept_name, mastery,
measured_at)` 행을 그대로 흉내낸 plain tuple을 `_rank_items`에 직접 넣어, 감쇠·정렬·tie-break·
정직 표기(`decay_model`/`calibrated`)·빈 입력을 검증한다. DB WHERE·DISTINCT ON 정확성은
`test_me_review_queue_integration.py`류(실 PG, 이 세션에선 실행 불가)의 몫이다.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from whymath_backend.l2.review_queue import (
    DECAY_MODEL_LABEL,
    REVIEW_QUEUE_PARAMETERS,
    ReviewQueue,
    _rank_items,
)

_AS_OF = datetime(2026, 8, 9, tzinfo=UTC)


class TestDecayChangesOrdering:
    """①변별력 — 망각 미적용(raw 정렬)과 비교해 감쇠 적용 시 순위가 뒤집히는 사례."""

    def test_old_high_mastery_becomes_more_urgent_than_recent_lower_mastery(self) -> None:
        old_high = uuid.uuid4()  # raw=0.9지만 60일 전 측정 → 크게 감쇠.
        recent_low = uuid.uuid4()  # raw=0.5·방금 측정 → 무감쇠.
        rows = [
            (old_high, "OLD", "오래된개념", 0.9, _AS_OF - timedelta(days=60)),
            (recent_low, "RECENT", "최근개념", 0.5, _AS_OF),
        ]

        # raw_mastery만으로 정렬했다면 recent_low(0.5) < old_high(0.9) — recent_low가 더 급함.
        raw_sorted_first = min(rows, key=lambda r: r[3])
        assert raw_sorted_first[0] == recent_low

        items = _rank_items(rows, _AS_OF)
        assert [i.concept_id for i in items] == [old_high, recent_low]
        # old_high의 감쇠 숙달이 recent_low보다 낮아져(급해져) 순위가 뒤집혔다.
        by_id = {i.concept_id: i for i in items}
        assert by_id[old_high].decayed_mastery < by_id[recent_low].decayed_mastery
        assert by_id[old_high].decayed_mastery < by_id[old_high].raw_mastery
        assert by_id[recent_low].decayed_mastery == by_id[recent_low].raw_mastery  # 무경과=무감쇠
        assert by_id[old_high].days_since_practice == 60.0
        assert by_id[recent_low].days_since_practice == 0.0


class TestTieBreak:
    """②동률 tie-break 결정론 — concept_code 오름차순, None은 맨 뒤."""

    def test_equal_decay_ties_break_by_code_ascending(self) -> None:
        cid_b, cid_a = uuid.uuid4(), uuid.uuid4()
        rows = [
            (cid_b, "b_concept", "나", 0.5, _AS_OF),
            (cid_a, "a_concept", "가", 0.5, _AS_OF),
        ]
        items = _rank_items(rows, _AS_OF)
        assert [i.concept_code for i in items] == ["a_concept", "b_concept"]
        assert [i.due_rank for i in items] == [1, 2]

    def test_none_code_sorts_last_among_ties(self) -> None:
        cid_none, cid_a, cid_z = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        rows = [
            (cid_none, None, None, 0.5, _AS_OF),
            (cid_z, "z_concept", "z", 0.5, _AS_OF),
            (cid_a, "a_concept", "a", 0.5, _AS_OF),
        ]
        items = _rank_items(rows, _AS_OF)
        assert [i.concept_id for i in items] == [cid_a, cid_z, cid_none]
        assert [i.due_rank for i in items] == [1, 2, 3]


class TestHonestLabeling:
    """③decay_model='bkt_p_forget'·calibrated=False 고정(문헌 전형값·정직 표기)."""

    def test_default_field_values(self) -> None:
        queue = ReviewQueue(items=[])
        assert queue.decay_model == "bkt_p_forget"
        assert queue.decay_model == DECAY_MODEL_LABEL
        assert queue.calibrated is False

    def test_review_queue_parameters_uses_nonzero_forget_rate(self) -> None:
        # 전역 DEFAULT_BKT_PARAMETERS(p_forget=0)와 달리 이 모듈 전용 파라미터는 λ>0.
        assert REVIEW_QUEUE_PARAMETERS.p_forget > 0.0


class TestReproducibility:
    """④정렬 재현성 — 같은 입력 → 같은 출력(여러 번 호출)."""

    def test_repeated_calls_produce_identical_output(self) -> None:
        rows = [
            (uuid.uuid4(), "C1", "개념1", 0.8, _AS_OF - timedelta(days=10)),
            (uuid.uuid4(), "C2", "개념2", 0.4, _AS_OF - timedelta(days=3)),
            (uuid.uuid4(), None, None, 0.6, _AS_OF - timedelta(days=30)),
        ]
        first = _rank_items(rows, _AS_OF)
        second = _rank_items(rows, _AS_OF)
        assert [i.model_dump() for i in first] == [i.model_dump() for i in second]
        # 입력 리스트 자체는 함수 호출로 변형되지 않는다(순수성).
        assert rows[0][3] == 0.8


class TestEmptyInput:
    """⑤빈 입력 → 빈 리스트."""

    def test_empty_rows_returns_empty_list(self) -> None:
        assert _rank_items([], _AS_OF) == []

    def test_rows_with_null_mastery_are_excluded(self) -> None:
        # mastery가 None인 스냅샷(방어적 처리)은 감쇠 대상이 없어 결과에서 제외.
        rows = [(uuid.uuid4(), "C", "개념", None, _AS_OF)]
        assert _rank_items(rows, _AS_OF) == []
