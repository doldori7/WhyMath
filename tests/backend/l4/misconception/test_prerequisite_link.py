"""L4 오개념→선수코칭 브릿지(`gaps_from_active_misconceptions`) 단위테스트 (hermetic·DB 무접근).

전체 체인(kebab-id → crosswalk resolve → M-id canonical 선정 → `MisconceptionCatalog` 조회 →
`concept_src_id` 해소 → `ConceptRef` → `PrerequisiteGap`)을 라이브 PG 없이 검증한다.

- crosswalk sync 조회는 `test_misconception_crosslink_shadow.py`와 동일한 fake 엔진 주입 패턴
  (`MisconceptionCrosslinkResolver(engine=_FakeSyncEngine(rows))`)을 그대로 미러한다.
- catalog·concept async 조회는 `column_descriptions`의 entity·컬럼명으로 디스패치하는 fake
  `AsyncSession`을 쓴다 — `test_resolve.py`(skill_graph)의 "가짜 세션으로 실행 횟수까지
  단언"하는 정신을 다중 쿼리 모양 구분으로 확장한 것이다(예기치 못한 쿼리는 AssertionError로
  즉시 드러나 잘못된 캔 데이터로 조용히 통과하지 않는다).

커버:
  ① mode=off → 빈 리스트 + DB 조회 0(mock session 호출 0회로 증명)
  ② mode!=off + 정상 체인 → 올바른 PrerequisiteGap 생성
  ③ ambiguous/no_direct/no_links(canonical 실패)·concept_orphan·concept_src_id 없음·catalog 행
     부재 각각 정직 스킵(크래시 없음·잘못된 gap 없음)
  ④ 빈 active_misconceptions → 빈 결과
  ⑤ (추가) dedup·순서 보존(confidence desc 계약)·never-break(예외 타입명 로그)·N+1 회피(쿼리 수 상한)
"""

from __future__ import annotations

import logging
import uuid
from types import TracebackType
from typing import Any

import pytest

from whymath_backend.config import get_settings
from whymath_backend.db.models.concept import Concept
from whymath_backend.db.models.misconception_catalog import MisconceptionCatalog
from whymath_backend.l1.misconception.crosslink_resolve import MisconceptionCrosslinkResolver
from whymath_backend.l4.misconception.prerequisite_link import gaps_from_active_misconceptions

pytestmark = pytest.mark.asyncio

_LOGGER_NAME = "whymath.l4.misconception.prerequisite_link"


# ──────────────────────────────────────────────────────────────────────────
# fake sync 엔진(crosswalk resolver 주입) — test_misconception_crosslink_shadow.py 패턴 미러
# ──────────────────────────────────────────────────────────────────────────
class _Row:
    def __init__(
        self, kebab_id: str, mis_id: str, confidence: float | None, link_type: str = "직접매핑"
    ) -> None:
        self.kebab_id = kebab_id
        self.mis_id = mis_id
        self.confidence = confidence
        self.link_type = link_type


class _FakeSyncResult:
    def __init__(self, rows: list[object]) -> None:
        self._rows = rows

    def all(self) -> list[object]:
        return self._rows


class _FakeSyncConnection:
    def __init__(self, engine: _FakeSyncEngine) -> None:
        self._engine = engine

    def __enter__(self) -> _FakeSyncConnection:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        return None

    def execute(self, statement: object, parameters: object = None) -> _FakeSyncResult:
        return _FakeSyncResult(self._engine.rows)


class _FakeSyncEngine:
    def __init__(self, rows: list[object] | None = None) -> None:
        self.rows: list[object] = rows or []

    def connect(self) -> _FakeSyncConnection:
        return _FakeSyncConnection(self)


def _resolver(rows: list[object] | None = None) -> MisconceptionCrosslinkResolver:
    return MisconceptionCrosslinkResolver(engine=_FakeSyncEngine(rows))  # type: ignore[arg-type]


class _RaisingResolver:
    """`resolve_links_many`가 항상 raise — never-break 경로 단언용(duck-typed·실 클래스 아님)."""

    def resolve_links_many(self, kebab_ids: Any) -> dict[str, list[Any]]:
        raise RuntimeError("crosswalk DB 미도달")


class _SpyResolver:
    """`resolve_links_many` 호출 여부·인자만 기록 — off/빈입력 zero-call 증명용."""

    def __init__(self) -> None:
        self.calls: list[Any] = []

    def resolve_links_many(self, kebab_ids: Any) -> dict[str, list[Any]]:
        self.calls.append(kebab_ids)
        return {}


# ──────────────────────────────────────────────────────────────────────────
# fake async 세션 — entity+컬럼명 디스패치(catalog IN쿼리·concept_map IN쿼리·name_ko IN쿼리 구분)
# ──────────────────────────────────────────────────────────────────────────
class _FakeScalars:
    def __init__(self, rows: list[object]) -> None:
        self._rows = rows

    def all(self) -> list[object]:
        return self._rows


class _FakeExecResult:
    def __init__(
        self,
        *,
        scalars_rows: list[object] | None = None,
        all_rows: list[tuple[object, ...]] | None = None,
    ) -> None:
        self._scalars_rows = scalars_rows
        self._all_rows = all_rows

    def scalars(self) -> _FakeScalars:
        return _FakeScalars(self._scalars_rows or [])

    def all(self) -> list[tuple[object, ...]]:
        return self._all_rows or []


class _FakeAsyncSession:
    """`MisconceptionCatalog`·`Concept`(source_id 조회)·`Concept`(name_ko 조회) 3종 쿼리 디스패치.

    stmt의 `column_descriptions`(entity·컬럼명)로 라우팅한다 — 어느 쿼리가 몇 번 불렸는지
    `execute_count`로 세어 N+1 회피(배치 조회)까지 함께 검증한다.
    """

    def __init__(
        self,
        *,
        catalog_rows: list[MisconceptionCatalog] | None = None,
        concept_rows: list[tuple[str, str, uuid.UUID]] | None = None,
        name_rows: list[tuple[uuid.UUID, str | None]] | None = None,
    ) -> None:
        self._catalog_rows = catalog_rows or []
        self._concept_rows = concept_rows or []
        self._name_rows = name_rows or []
        self.execute_count = 0

    async def execute(self, stmt: Any) -> _FakeExecResult:
        self.execute_count += 1
        cols = stmt.column_descriptions
        entity = cols[0]["entity"]
        names = {c["name"] for c in cols}
        if entity is MisconceptionCatalog:
            return _FakeExecResult(scalars_rows=self._catalog_rows)
        if entity is Concept and "source_id" in names:
            return _FakeExecResult(all_rows=self._concept_rows)
        if entity is Concept and "name_ko" in names:
            return _FakeExecResult(all_rows=self._name_rows)
        raise AssertionError(f"예기치 못한 쿼리 — entity={entity} names={names}")


class _ZeroCallSession:
    """`execute`가 호출되면 즉시 실패 — off/조기스킵 경로의 zero-DB-call 증명용."""

    async def execute(self, stmt: Any) -> Any:
        raise AssertionError("이 경로에서는 session.execute가 호출되면 안 됨(회귀 0 위반)")


def _set_mode(monkeypatch: pytest.MonkeyPatch, mode: str) -> None:
    monkeypatch.setenv("WHYMATH_MISCONCEPTION_CROSSLINK_MODE", mode)
    get_settings.cache_clear()


# ──────────────────────────────────────────────────────────────────────────
# ① mode=off — 조회 0(회귀 0 핵심 메커니즘)
# ──────────────────────────────────────────────────────────────────────────
class TestModeOffGating:
    async def test_off_returns_empty_and_zero_calls(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """off(기본)면 비어 있지 않은 입력이 있어도 resolver·session 어느 쪽도 건드리지 않는다."""
        _set_mode(monkeypatch, "off")
        spy = _SpyResolver()
        try:
            result = await gaps_from_active_misconceptions(
                _ZeroCallSession(),  # type: ignore[arg-type]
                ["some-kebab", "another-kebab"],
                resolver=spy,  # type: ignore[arg-type]
            )
        finally:
            get_settings.cache_clear()
        assert result == []
        assert spy.calls == []  # resolver 자체도 안 건드림(어댑터 첫 줄 조기 반환).


# ──────────────────────────────────────────────────────────────────────────
# ④ 빈 active_misconceptions — mode와 무관하게 조기 반환
# ──────────────────────────────────────────────────────────────────────────
class TestEmptyInput:
    async def test_empty_list_returns_empty_and_zero_calls(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """mode=shadow여도 활성 오개념이 없으면 조회할 대상이 없어 즉시 빈 리스트."""
        _set_mode(monkeypatch, "shadow")
        spy = _SpyResolver()
        try:
            result = await gaps_from_active_misconceptions(
                _ZeroCallSession(), [], resolver=spy  # type: ignore[arg-type]
            )
        finally:
            get_settings.cache_clear()
        assert result == []
        assert spy.calls == []


# ──────────────────────────────────────────────────────────────────────────
# ② 정상 체인 — kebab → M-id → concept_src_id → ConceptRef → PrerequisiteGap
# ──────────────────────────────────────────────────────────────────────────
class TestFullChainResolves:
    async def test_single_misconception_resolves_to_gap(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """정상 체인 — 단일 kebab-id가 최종 PrerequisiteGap 1건으로 정확히 변환된다."""
        _set_mode(monkeypatch, "shadow")
        cid = uuid.uuid4()
        resolver = _resolver([_Row("some-kebab", "M1", 0.9)])
        session = _FakeAsyncSession(
            catalog_rows=[MisconceptionCatalog(mis_id="M1", concept_src_id="N1")],
            concept_rows=[("N1", "UC.some.code", cid)],
            name_rows=[(cid, "일차함수")],
        )
        try:
            gaps = await gaps_from_active_misconceptions(session, ["some-kebab"], resolver=resolver)
        finally:
            get_settings.cache_clear()
        assert len(gaps) == 1
        gap = gaps[0]
        assert gap.concept_id == cid
        assert gap.concept_code == "UC.some.code"
        assert gap.concept_name == "일차함수"
        assert gap.agreement == "insufficient"  # BKT/IRT 교차검증 없음 — 정직 표시.
        assert gap.depth == 1
        assert gap.weakness is None  # 허위 측정치 날조 금지.
        assert gap.bkt_mastery is None
        assert gap.irt_mastery_proxy is None
        # N+1 회피 — catalog 1 + concept_map 1(resolve_many 내부) + name_ko 1 = 3.
        assert session.execute_count == 3

    async def test_name_ko_missing_leaves_concept_name_none_gracefully(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """name_ko enrich가 못 찾아도(부분 데이터) 크래시 없이 concept_name=None으로 graceful."""
        _set_mode(monkeypatch, "shadow")
        cid = uuid.uuid4()
        resolver = _resolver([_Row("k1", "M1", 0.9)])
        session = _FakeAsyncSession(
            catalog_rows=[MisconceptionCatalog(mis_id="M1", concept_src_id="N1")],
            concept_rows=[("N1", "UC.a", cid)],
            name_rows=[],  # name_ko 없음
        )
        try:
            gaps = await gaps_from_active_misconceptions(session, ["k1"], resolver=resolver)
        finally:
            get_settings.cache_clear()
        assert len(gaps) == 1
        assert gaps[0].concept_id == cid
        assert gaps[0].concept_name is None  # graceful — "선수개념" 일반어 폴백은 L4 소비처 몫.


# ──────────────────────────────────────────────────────────────────────────
# ③ 정직한 스킵 — canonical 실패·orphan·참조 없음·catalog 부재
# ──────────────────────────────────────────────────────────────────────────
class TestHonestSkips:
    async def test_ambiguous_tie_skipped(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """직접매핑 최고 confidence 동률(tie) → canonical 미선정 → 정직 스킵(catalog 조회조차 없음)."""
        _set_mode(monkeypatch, "shadow")
        resolver = _resolver([_Row("k1", "M1", 0.8), _Row("k1", "M2", 0.8)])
        try:
            gaps = await gaps_from_active_misconceptions(
                _ZeroCallSession(), ["k1"], resolver=resolver  # type: ignore[arg-type]
            )
        finally:
            get_settings.cache_clear()
        assert gaps == []

    async def test_no_direct_mapping_skipped(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """직접매핑이 아닌 링크만 있으면(부분매핑 등) canonical 후보 자격 없음 → 스킵."""
        _set_mode(monkeypatch, "shadow")
        resolver = _resolver([_Row("k1", "M1", 0.9, link_type="부분매핑")])
        try:
            gaps = await gaps_from_active_misconceptions(
                _ZeroCallSession(), ["k1"], resolver=resolver  # type: ignore[arg-type]
            )
        finally:
            get_settings.cache_clear()
        assert gaps == []

    async def test_no_links_skipped(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """crosswalk 테이블에 그 kebab-id 행 자체가 없음(빈 테이블 등) → 스킵."""
        _set_mode(monkeypatch, "shadow")
        resolver = _resolver([])  # 완전히 빈 crosswalk
        try:
            gaps = await gaps_from_active_misconceptions(
                _ZeroCallSession(), ["k1"], resolver=resolver  # type: ignore[arg-type]
            )
        finally:
            get_settings.cache_clear()
        assert gaps == []

    async def test_no_concept_src_id_skipped(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """canonical은 선정되나 그 M-id 행에 concept_src_id가 없음("참조 없음") → 스킵."""
        _set_mode(monkeypatch, "shadow")
        resolver = _resolver([_Row("k1", "M1", 0.9)])
        session = _FakeAsyncSession(
            catalog_rows=[MisconceptionCatalog(mis_id="M1", concept_src_id=None)]
        )
        try:
            gaps = await gaps_from_active_misconceptions(session, ["k1"], resolver=resolver)
        finally:
            get_settings.cache_clear()
        assert gaps == []
        # concept_src_id 없는 행은 resolve_many에 아예 안 실림 → catalog 조회 1회뿐(추가 조회 0).
        assert session.execute_count == 1

    async def test_concept_orphan_skipped(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """concept_src_id는 있으나 `Concept.source_id`에 매칭이 없음(orphan) → 스킵(크래시 없음)."""
        _set_mode(monkeypatch, "shadow")
        resolver = _resolver([_Row("k1", "M1", 0.9)])
        session = _FakeAsyncSession(
            catalog_rows=[MisconceptionCatalog(mis_id="M1", concept_src_id="N1")],
            concept_rows=[],  # N1 미매칭 → concept_orphan
        )
        try:
            gaps = await gaps_from_active_misconceptions(session, ["k1"], resolver=resolver)
        finally:
            get_settings.cache_clear()
        assert gaps == []
        # catalog 1 + concept_map 1 = 2(orphan이라 name_ko 조회는 발생하지 않음).
        assert session.execute_count == 2

    async def test_catalog_row_missing_skipped_defensively(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """canonical M-id가 선정됐으나 `misconception_catalog`에 그 행이 없음(방어적 스킵)."""
        _set_mode(monkeypatch, "shadow")
        resolver = _resolver([_Row("k1", "M1", 0.9)])
        session = _FakeAsyncSession(catalog_rows=[])  # M1 행 부재
        try:
            gaps = await gaps_from_active_misconceptions(session, ["k1"], resolver=resolver)
        finally:
            get_settings.cache_clear()
        assert gaps == []
        assert session.execute_count == 1


# ──────────────────────────────────────────────────────────────────────────
# ⑤-a dedup — 서로 다른 오개념이 같은 개념으로 귀결되면 gap 1건만
# ──────────────────────────────────────────────────────────────────────────
class TestDedup:
    async def test_two_kebabs_same_canonical_mid_dedup_to_one_gap(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """서로 다른 kebab 두 개가 같은 canonical M-id로 귀결 → 중복 gap 없이 1건."""
        _set_mode(monkeypatch, "shadow")
        cid = uuid.uuid4()
        resolver = _resolver([_Row("k1", "M1", 0.9), _Row("k2", "M1", 0.9)])
        session = _FakeAsyncSession(
            catalog_rows=[MisconceptionCatalog(mis_id="M1", concept_src_id="N1")],
            concept_rows=[("N1", "UC.a", cid)],
            name_rows=[(cid, "일차함수")],
        )
        try:
            gaps = await gaps_from_active_misconceptions(session, ["k1", "k2"], resolver=resolver)
        finally:
            get_settings.cache_clear()
        assert len(gaps) == 1
        assert gaps[0].concept_id == cid


# ──────────────────────────────────────────────────────────────────────────
# ⑤-b 순서 보존 — active_misconceptions(confidence desc) 순서가 gaps[0] 우선순위를 결정
# ──────────────────────────────────────────────────────────────────────────
class TestOrderPreservation:
    async def test_gaps_follow_active_misconceptions_input_order(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """입력 순서(confidence desc 계약)가 출력 순서로 그대로 보존된다(gaps[0]=최고 confidence)."""
        _set_mode(monkeypatch, "shadow")
        cid_high, cid_low = uuid.uuid4(), uuid.uuid4()
        resolver = _resolver([_Row("k-high", "M1", 0.9), _Row("k-low", "M2", 0.9)])
        session = _FakeAsyncSession(
            catalog_rows=[
                MisconceptionCatalog(mis_id="M1", concept_src_id="N1"),
                MisconceptionCatalog(mis_id="M2", concept_src_id="N2"),
            ],
            concept_rows=[("N1", "UC.a", cid_high), ("N2", "UC.b", cid_low)],
            name_rows=[(cid_high, "개념A"), (cid_low, "개념B")],
        )
        try:
            gaps = await gaps_from_active_misconceptions(
                session, ["k-high", "k-low"], resolver=resolver
            )
        finally:
            get_settings.cache_clear()
        assert [g.concept_id for g in gaps] == [cid_high, cid_low]
        # 2건이어도 배치 조회라 쿼리 수는 여전히 3(N+1 회피 재확인).
        assert session.execute_count == 3


# ──────────────────────────────────────────────────────────────────────────
# ⑤-c never-break — 예기치 못한 예외는 빈 리스트로 강등 + 예외 타입명 로그
# ──────────────────────────────────────────────────────────────────────────
class TestNeverBreak:
    async def test_resolver_exception_returns_empty_and_logs_type(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """resolver가 raise해도 예외가 전파되지 않고 빈 리스트 — 로그엔 예외 타입명이 남는다."""
        _set_mode(monkeypatch, "shadow")
        try:
            with caplog.at_level(logging.WARNING, logger=_LOGGER_NAME):
                gaps = await gaps_from_active_misconceptions(
                    _ZeroCallSession(),  # type: ignore[arg-type]
                    ["k1"],
                    resolver=_RaisingResolver(),  # type: ignore[arg-type]
                )
        finally:
            get_settings.cache_clear()
        assert gaps == []
        messages = [r.getMessage() for r in caplog.records if r.name == _LOGGER_NAME]
        assert any("RuntimeError" in m for m in messages)  # 예외 타입명 로그(침묵 실패 금지).
        # 원문("crosswalk DB 미도달")은 우연히 RuntimeError 메시지에 있었을 뿐 — 로그가 요구하는
        # 건 타입명이지 원문이 아니므로, 타입명만으로 검증(민감정보 로그 없음 원칙과 정합).
