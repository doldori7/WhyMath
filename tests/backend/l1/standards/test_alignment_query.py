"""정렬 통합 조회(`get_alignments`) 단위테스트 — 3축 합성·조인 회계·어휘 비통일 (CUR-12).

hermetic — FakeSession(큐잉된 행)만 쓴다. 실 SQL(cardinality 가드·ANY 대조)의 정확성은
`test_curricula_integration.py`류 실 PG 몫이다(`test_alignments.py`가 세운 분담 그대로).

검증 축:
  - **축 합성 순서**가 선언 순서(1→2→3)로 고정 — 값 사전순이 아니다(`api/alignments.py`의
    페이지네이션 prefix 보존이 이 순서에 기댄다·구현 중 실제로 밟은 함정).
  - **조인 회계**(acceptance ②) — probed/matched가 "매핑 없음"과 "조인 실패"를 구분하고,
    전건 미매칭이면 `join_blackout`이 서고 `log_join_stats`가 **warning**으로 승격한다.
    변별력 양방향: 매칭이 하나라도 있으면 경고가 서지 않는다.
  - **미측정 ≠ 0** — 조기 종료로 건너뛴 축은 `queried_axes`에서 빠진다(0이 "없음"이 아니라
    "안 봄"임을 구분).
  - **어휘 비통일**(Phase 2 범위 밖) — 축별 `standard_ref_kind`가 그대로 실린다.
  - **alignment_type은 로깅 전용**(acceptance ③) — 현재 전 축 미기록이라 항상 None이고,
    회계가 그 사실을 '(미상)'으로 드러낸다.
"""

from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Any, get_args

import pytest

from whymath_backend.l1.standards.alignment_query import (
    ALL_AXES,
    AXIS_ORDER,
    AlignmentAxis,
    AlignmentType,
    get_alignments,
    log_join_stats,
)


class _FakeResult:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def all(self) -> list[Any]:
        return list(self._rows)


class _FakeSession:
    """execute 큐 — 원소 순서가 곧 축 조회 순서(빈 큐는 빈 결과)."""

    def __init__(self, execute_queue: list[list[Any]] | None = None) -> None:
        self._queue = list(execute_queue or [])
        self.execute_calls = 0

    async def execute(self, _stmt: Any) -> _FakeResult:
        self.execute_calls += 1
        if not self._queue:
            return _FakeResult([])
        return _FakeResult(self._queue.pop(0))


def _link_row(concept_code: str = "UC.poly", norm_id: str = "2022_10공수1_01_01") -> Any:
    """1축 행 — (ConceptStandardLink 유사 객체, concept_id)."""
    link = type(
        "_Link", (), {"concept_code": concept_code, "norm_id": norm_id, "link_type": "직접"}
    )()
    return (link, None)


def _entry_row(
    concept_id: str = "math.algebra.poly",
    codes: list[str] | None = None,
    framework_id: str | None = "KR_NC_2022",
) -> Any:
    """2축 행 — (CurriculumEntry 유사 객체, concept_id)."""
    entry = type(
        "_Entry",
        (),
        {
            "concept_id": concept_id,
            "national_standard_codes": list(codes or ["[10공수1-01-01]"]),
            "framework_id": framework_id,
        },
    )()
    return (entry, None)


def _atom_row(
    code: str | None = "atom-001",
    codes: list[str] | None = None,
    concept_id: uuid.UUID | None = None,
) -> Any:
    """3축 행 — (atom_code, standard_codes, concept_id). atom_code=None = OUTER JOIN 미스.

    `codes=None`을 *명시*하면 "원자 행은 있으나 성취기준 배열이 비었다"를 뜻한다. 기본값은
    코드 1건이 실린 정상 행이다(1·2축 빌더와 대칭).
    """
    if code is not None and codes is None:
        codes = ["[10공수1-01-01]"]
    return (code, codes, concept_id)


class TestAxisComposition:
    async def test_axis_order_is_declaration_order_not_alphabetical(self) -> None:
        """합성 순서 계약 — 값 사전순이면 atom_node가 앞으로 와 페이지네이션 prefix가 깨진다."""
        assert AXIS_ORDER == (
            AlignmentAxis.CONCEPT_STANDARD_LINK,
            AlignmentAxis.CURRICULUM_ENTRY,
            AlignmentAxis.ATOM_NODE,
        )
        assert set(AXIS_ORDER) == ALL_AXES

        session = _FakeSession([[_link_row()], [_entry_row()], [_atom_row()]])
        result = await get_alignments(session)  # type: ignore[arg-type]

        assert [a.axis for a in result.alignments] == list(AXIS_ORDER)

    async def test_axis_filter_queries_only_that_axis(self) -> None:
        session = _FakeSession([[_atom_row(codes=["[2수01-01]"])]])
        result = await get_alignments(  # type: ignore[arg-type]
            session, axes={AlignmentAxis.ATOM_NODE}
        )

        assert session.execute_calls == 1
        assert result.stats.queried_axes == (AlignmentAxis.ATOM_NODE,)

    async def test_ref_kind_is_carried_per_axis_without_unification(self) -> None:
        """어휘 통일 금지(Phase 2 범위 밖) — 1축은 norm_id, 2·3축은 official_code 그대로."""
        session = _FakeSession([[_link_row()], [_entry_row()], [_atom_row()]])
        result = await get_alignments(session)  # type: ignore[arg-type]

        assert [a.standard_ref_kind for a in result.alignments] == [
            "norm_id",
            "official_code",
            "official_code",
        ]

    async def test_array_axis_flattens_codes(self) -> None:
        session = _FakeSession(
            [[], [], [_atom_row(codes=["[2수01-01]", "[2수01-02]"])]],
        )
        result = await get_alignments(session)  # type: ignore[arg-type]

        assert [a.standard_ref for a in result.alignments] == ["[2수01-01]", "[2수01-02]"]

    async def test_framework_filter_narrows_to_the_only_axis_that_has_it(self) -> None:
        """framework_id를 가진 축은 2축뿐 — 나머지 축에 "적용한 척" 하지 않고 빼 버린다."""
        session = _FakeSession([[_entry_row()]])
        result = await get_alignments(session, framework_id="KR_NC_2022")  # type: ignore[arg-type]

        assert result.stats.axes == (AlignmentAxis.CURRICULUM_ENTRY,)
        assert session.execute_calls == 1

    async def test_empty_target_skips_queries(self) -> None:
        """대상 0건이면 SQL을 돌리지 않는다(빈 IN 낭비 회피)."""
        session = _FakeSession()
        result = await get_alignments(session, concept_ids=[])  # type: ignore[arg-type]

        assert session.execute_calls == 0
        assert result.alignments == ()
        assert result.stats.queried_axes == ()


class TestJoinAccounting:
    """acceptance ② — "매핑 없음"과 "조인 실패"를 계수로 구분한다.

    #933 리뷰 P2 상환: 초판은 probed/matched **2분류**라 아래 세 사태 중 앞의 둘이 똑같이
    `(1, 0)`으로 뭉갰다 — 그 상태로는 0%의 원인을 영원히 알 수 없다. 3분류로 고치고, 세
    사태가 **서로 다른 회계**를 낸다는 것 자체를 아래 파라미터 테이블이 동결한다.
    """

    _STATES = (
        # (라벨, 행, 기대 (probed, joined, matched), blackout)
        ("조인 미스", (None, None), (1, 0, 0), True),
        ("매핑 없음", ("atom-001", []), (1, 1, 0), False),
        ("정상", ("atom-001", ["[2수01-01]"]), (1, 1, 1), False),
    )

    @pytest.mark.parametrize(("label", "row", "expected", "blackout"), _STATES)
    async def test_three_states_have_distinct_accounting(
        self,
        label: str,
        row: tuple[str | None, list[str] | None],
        expected: tuple[int, int, int],
        blackout: bool,
    ) -> None:
        cid = uuid.uuid4()
        session = _FakeSession([[_atom_row(row[0], row[1], cid)]])
        result = await get_alignments(  # type: ignore[arg-type]
            session, concept_ids=[cid], axes={AlignmentAxis.ATOM_NODE}
        )

        actual = (result.stats.probed, result.stats.joined, result.stats.matched)
        assert actual == expected, label
        assert result.stats.join_blackout is blackout, label

    def test_state_accounting_is_pairwise_distinct(self) -> None:
        """세 기대값이 서로 달라야 이 테이블이 변별력을 갖는다 — 계약의 자기검사.

        초판이 무너진 지점이 정확히 여기다: 두 사태의 기대값이 같으면 위 파라미터 테스트는
        전부 통과하면서도 아무것도 구분하지 못한다.
        """
        assert len({expected for _, _, expected, _ in self._STATES}) == len(self._STATES)

    async def test_blackout_tracks_join_failure_not_empty_mapping(self) -> None:
        """경고 기준은 matched가 아니라 joined — 매핑만 빈 것은 정상 상태일 수 있다."""
        cid = uuid.uuid4()
        session = _FakeSession([[_atom_row("atom-001", [], cid)]])
        result = await get_alignments(  # type: ignore[arg-type]
            session, concept_ids=[cid], axes={AlignmentAxis.ATOM_NODE}
        )

        assert result.stats.matched == 0  # 성취기준은 없지만
        assert result.stats.joined == 1  # 조인은 성립했다 →
        assert result.stats.join_blackout is False  # 경고 대상이 아니다

    async def test_no_probe_is_not_a_blackout(self) -> None:
        """조회 자체를 안 했으면 blackout이 아니다 — "안 봄"과 "안 맞음"은 다르다(미측정 ≠ 0)."""
        session = _FakeSession()
        result = await get_alignments(  # type: ignore[arg-type]
            session, axes={AlignmentAxis.ATOM_NODE}
        )

        assert result.stats.probed == 0
        assert result.stats.join_blackout is False

    async def test_blackout_logs_warning(self, caplog: pytest.LogCaptureFixture) -> None:
        cid = uuid.uuid4()
        session = _FakeSession([[_atom_row(None, None, cid)]])
        result = await get_alignments(  # type: ignore[arg-type]
            session, concept_ids=[cid], axes={AlignmentAxis.ATOM_NODE}
        )

        logger = logging.getLogger("test.alignment.blackout")
        with caplog.at_level(logging.DEBUG, logger=logger.name):
            log_join_stats(result.stats, logger=logger, context="unit")
        assert any(r.levelno == logging.WARNING for r in caplog.records)

    async def test_join_success_logs_no_warning(self, caplog: pytest.LogCaptureFixture) -> None:
        """변별력 양방향 — 경고가 *항상* 뜨는 검사였다면 신호가 아니다."""
        cid = uuid.uuid4()
        session = _FakeSession([[_atom_row("atom-001", ["[2수01-01]"], cid)]])
        result = await get_alignments(  # type: ignore[arg-type]
            session, concept_ids=[cid], axes={AlignmentAxis.ATOM_NODE}
        )

        logger = logging.getLogger("test.alignment.hit")
        with caplog.at_level(logging.DEBUG, logger=logger.name):
            log_join_stats(result.stats, logger=logger, context="unit")
        assert not any(r.levelno == logging.WARNING for r in caplog.records)
        assert any(r.levelno == logging.DEBUG for r in caplog.records)


class TestEarlyExit:
    async def test_limit_skips_later_axes_and_marks_them_unqueried(self) -> None:
        """건너뛴 축의 0은 "없음"이 아니라 "안 봄" — queried_axes가 그 구분을 남긴다."""
        session = _FakeSession([[_link_row(), _link_row(norm_id="2022_10공수1_01_02")]])
        result = await get_alignments(session, limit=2)  # type: ignore[arg-type]

        assert session.execute_calls == 1
        assert result.stats.queried_axes == (AlignmentAxis.CONCEPT_STANDARD_LINK,)
        assert result.stats.axes == AXIS_ORDER  # 요청은 3축이었다
        assert result.stats.items_by_axis["atom_node"] == 0  # 그러나 "안 봄"


class TestOutcomeFilter:
    async def test_item_level_recheck_on_array_axis(self) -> None:
        """행 매칭 ≠ 항목 매칭 — 같은 배열의 다른 코드가 항목으로 새지 않는다."""
        session = _FakeSession(
            [[], [], [_atom_row(codes=["[2수01-01]", "[2수01-02]"])]],
        )
        result = await get_alignments(session, outcome_id="[2수01-02]")  # type: ignore[arg-type]

        assert [a.standard_ref for a in result.alignments] == ["[2수01-02]"]


class TestResultHelpers:
    async def test_standard_refs_are_sorted_and_deduped(self) -> None:
        """결정론 — 소비처가 '첫 코드'를 골라도 안정(coach가 그렇게 쓴다)."""
        session = _FakeSession(
            [[], [], [_atom_row(codes=["[2수01-02]", "[2수01-01]", "[2수01-02]"])]],
        )
        result = await get_alignments(session)  # type: ignore[arg-type]

        assert result.standard_refs() == ("[2수01-01]", "[2수01-02]")

    async def test_refs_by_concept_id_groups_only_uuid_asked_items(self) -> None:
        cid = uuid.uuid4()
        session = _FakeSession([[_atom_row("atom-001", ["[2수01-01]"], cid)]])
        result = await get_alignments(  # type: ignore[arg-type]
            session, concept_ids=[cid], axes={AlignmentAxis.ATOM_NODE}
        )

        assert result.refs_by_concept_id() == {cid: ("[2수01-01]",)}


class TestAlignmentTypeIsLoggingOnly:
    """acceptance ③ — 어휘는 정의하되 판정에 쓰지 않고, 미기록 상태를 숨기지 않는다."""

    def test_vocabulary_is_frozen(self) -> None:
        assert {t.value for t in AlignmentType} == {
            "TEACHES",
            "PRACTICES",
            "ASSESSES",
            "REMEDIATES",
            "EXTENDS",
            "REVIEWS",
        }

    async def test_current_axes_record_no_type_and_stats_say_so(self) -> None:
        """지금 어느 축도 교수학적 의도를 싣지 않는다 — 임의로 TEACHES를 찍지 않는다(날조 금지).

        그 사실이 회계에 '(미상)'으로 드러난다. 축이 의도를 싣기 시작하면 이 단언이 깨져
        분포를 갱신하게 된다(드리프트 감지).
        """
        session = _FakeSession([[_link_row()], [_entry_row()], [_atom_row()]])
        result = await get_alignments(session)  # type: ignore[arg-type]

        assert all(a.alignment_type is None for a in result.alignments)
        assert result.stats.type_counts == {"(미상)": 3}


class TestConsumerWiringIsReal:
    """집행 지점(정본화 ≠ 집행) — 소비처가 *실제로* 통합 함수를 경유하는지 정적으로 동결한다.

    "만들었다"와 "쓰인다"는 다르다(CLAUDE.md — 검증 장치를 만들고 배선 확인 없이 완료 선언
    금지). 이 테스트가 막는 것은 두 가지다: ①소비처가 import를 잃는 회귀 ②소비처가 조인을
    다시 손으로 쓰는 회귀(원자 축 조인 문자열의 재출현).
    """

    _CONSUMERS = (
        "whymath_backend/api/coach.py",
        "whymath_backend/l2/target_progress.py",
        "whymath_backend/api/alignments.py",
        "whymath_backend/api/dsl.py",
    )

    def _source(self, relative: str) -> str:
        root = Path(__file__).resolve().parents[4] / "src" / "backend"
        return (root / relative).read_text(encoding="utf-8")

    @pytest.mark.parametrize("relative", _CONSUMERS)
    def test_consumer_imports_unified_function(self, relative: str) -> None:
        body = self._source(relative)
        assert "from whymath_backend.l1.standards.alignment_query import" in body, relative
        assert "get_alignments" in body, relative

    # 정렬 3축의 ORM 모델 — 통합 함수를 경유하는 소비처는 이 테이블들을 직접 만질 이유가 없다.
    _AXIS_MODEL_IMPORTS = (
        "from whymath_backend.db.models.atom_node import",
        "from whymath_backend.db.models.concept_standard_link import",
        "from whymath_backend.db.models.curriculum_entry import",
    )

    @pytest.mark.parametrize("relative", _CONSUMERS)
    def test_consumer_does_not_touch_axis_tables_directly(self, relative: str) -> None:
        """축 ORM import의 재출현 = 조인을 손으로 다시 쓴 것 — 통합이 조용히 풀린 신호다.

        문자열 대조가 아니라 **import 구조**를 본다: 산문(docstring)에 축 이름이 나오는 것은
        정상이고(설계 근거 기록), 실제로 그 테이블을 SELECT하려면 import가 필요하다. 그래서
        이 검사는 변별력이 있다 — 실패는 배선이 실제로 풀렸을 때만 난다.
        """
        body = self._source(relative)
        for statement in self._AXIS_MODEL_IMPORTS:
            assert statement not in body, f"{relative}: {statement}"

    def test_http_axis_vocabulary_matches_core_enum(self) -> None:
        """`api/alignments.py`의 와이어 Literal과 코어 enum의 값이 갈리면 안 된다."""
        from whymath_backend.api.alignments import AlignmentAxis as WireAxis

        assert set(get_args(WireAxis)) == {a.value for a in AlignmentAxis}


class TestRefKindFilter:
    """#933 리뷰 P2 — 축 어휘가 섞인 결과를 그대로 평탄화하면 '가짜 통일'이 결과물에서 난다."""

    async def test_unfiltered_refs_can_mix_vocabularies(self) -> None:
        """결함의 실재를 동결 — 필터 없이 뽑으면 norm_id와 official_code가 한 리스트에 섞인다.

        이 사실 자체가 `kind` 인자가 필요한 이유다(소비처가 섞인 리스트로는 어느 쪽 조회도
        하지 못한다). 함수의 기본 동작을 비난하는 것이 아니라, **섞일 수 있음**을 못박는다.
        """
        session = _FakeSession([[_link_row()], [], [_atom_row()]])
        result = await get_alignments(session)  # type: ignore[arg-type]

        kinds = {a.standard_ref_kind for a in result.alignments}
        assert kinds == {"norm_id", "official_code"}
        assert len(result.standard_refs()) == 2  # 섞인 채로 나온다

    async def test_kind_filter_keeps_one_vocabulary(self) -> None:
        session = _FakeSession([[_link_row()], [], [_atom_row()]])
        result = await get_alignments(session)  # type: ignore[arg-type]

        official = result.standard_refs(kind="official_code")
        norm = result.standard_refs(kind="norm_id")
        assert official == ("[10공수1-01-01]",)
        assert norm == ("2022_10공수1_01_01",)
        assert set(official) & set(norm) == set()
