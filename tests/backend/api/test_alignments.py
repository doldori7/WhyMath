"""alignments API 라우터 단위테스트 — FakeSession 주입(라이브 PG 없음, hermetic).

`GET /v1/alignments`(3축 얇은 합성)의 *엔드포인트 결선*을 검증한다: 축-우선 결정적 순서·배열
평탄화·항목 수준 standard_ref 재대조·축 필터 시 단일 조회·조기 종료(앞 축이 차면 뒤 축 미조회)·
페이지네이션 슬라이스·422 실패 경로. 실제 SQL(cardinality 가드·ANY 대조)의 정확성은
test_curricula_integration.py의 실 PG 몫이다(test_concepts.py 동형 분담).

CUR-12 경계: 이 테스트는 합성 *표면*만 동결한다 — 통합 함수(get_alignments)·소비처 정렬은
CUR-12에서 이 표면 뒤로 들어올 예정이며, 그때도 이 결선 계약(순서·축 표시·어휘 표시)은
유지돼야 한다.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime, timezone
from typing import Any

from fastapi.testclient import TestClient

from whymath_backend.app import create_app
from whymath_backend.db.models.atom_node import AtomNode
from whymath_backend.db.models.concept_standard_link import ConceptStandardLink
from whymath_backend.db.models.curriculum_entry import CurriculumEntry
from whymath_backend.db.session import get_session
from whymath_backend.schema.curriculum_entry import CurriculumEntry as CurriculumEntrySchema
from whymath_backend.schema.enums import CurriculumLicense
from whymath_backend.schema.standard import (
    ConceptStandardLink as ConceptStandardLinkSchema,
)


class _FakeScalars:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def all(self) -> list[Any]:
        return list(self._rows)


class _FakeResult:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def scalars(self) -> _FakeScalars:
        return _FakeScalars(self._rows)


class FakeSession:
    """execute 큐 기반 AsyncSession 모사(test_me_target_progress.py 관례).

    alignments 핸들러는 최대 3회 execute(축 순서 고정)하므로, 큐의 원소 순서가 곧 축 순서다
    (축 필터·조기 종료 시엔 앞에서부터 필요한 만큼만 소비). 호출 횟수를 기록해 "뒤 축 미조회"
    결선을 검증한다.
    """

    def __init__(self, execute_queue: list[list[Any]] | None = None) -> None:
        self._queue = list(execute_queue or [])
        self.execute_calls = 0

    async def execute(self, _stmt: Any) -> _FakeResult:
        self.execute_calls += 1
        if not self._queue:
            return _FakeResult([])
        return _FakeResult(self._queue.pop(0))


def _client(fake: FakeSession) -> TestClient:
    app = create_app()

    async def _override() -> AsyncIterator[FakeSession]:
        yield fake

    app.dependency_overrides[get_session] = _override
    return TestClient(app)


# ── 표본 ORM 빌더 (transient — 라이브 PG 불필요) ──────────────────────────
def _link(
    concept_code: str = "UC.poly.add", norm_id: str = "2022_10공수1_01_01"
) -> ConceptStandardLink:
    return ConceptStandardLink.from_schema(
        ConceptStandardLinkSchema(concept_code=concept_code, norm_id=norm_id, link_type="직접")
    )


def _entry(entry_id: str = "ce-0001", *, codes: list[str] | None = None) -> CurriculumEntry:
    """transient CurriculumEntry 셀 — 2축 표본(테스트 디렉터리는 패키지가 아니라 파일 내 정의).

    from_schema 경유(불변식 검증 유지 — is_present=true라 source_url 동봉).
    """
    return CurriculumEntry.from_schema(
        CurriculumEntrySchema(
            entry_id=entry_id,
            concept_id="math.algebra.polynomial",
            country_code="KR",
            source_name="NCIC",
            source_url="https://ncic.re.kr/example",
            license_id=CurriculumLicense.KR_NCIC,
            framework_id="KR_NC_2022",
            is_present=True,
            confidence=0.9,
            national_standard_codes=list(codes or ["[10공수1-01-01]"]),
            created_at=datetime(2026, 8, 30, tzinfo=timezone.utc),
            updated_at=datetime(2026, 8, 30, tzinfo=timezone.utc),
        )
    )


def _atom(code: str = "atom-001", codes: list[str] | None = None) -> AtomNode:
    """transient AtomNode — 핸들러가 읽는 컬럼(code·standard_codes)만 채운다."""
    return AtomNode(
        code=code,
        name_ko="다항식 덧셈",
        level="세부개념",
        standard_codes=list(codes or ["[10공수1-01-01]"]),
        review_status="ai_estimated",
        updated_at=datetime(2026, 8, 30, tzinfo=timezone.utc),
    )


class TestListAlignments:
    def test_axis_major_order_and_ref_kind(self) -> None:
        """3축이 고정 순서(1→2→3)로 합성되고, 축별 어휘 표시(standard_ref_kind)가 붙는다."""
        fake = FakeSession(
            execute_queue=[
                [_link()],
                [_entry("ce-0001", codes=["[10공수1-01-01]"])],
                [_atom("atom-001")],
            ]
        )
        resp = _client(fake).get("/v1/alignments")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert [i["axis"] for i in body] == [
            "concept_standard_link",
            "curriculum_entry",
            "atom_node",
        ]
        assert [i["standard_ref_kind"] for i in body] == [
            "norm_id",
            "official_code",
            "official_code",
        ]
        # 축별 부가 필드 — 1축만 link_type, 2축만 framework_id.
        assert body[0]["link_type"] == "직접"
        assert body[1]["framework_id"] == "KR_NC_2022"
        assert body[2]["link_type"] is None and body[2]["framework_id"] is None

    def test_array_axis_flattens_multiple_codes(self) -> None:
        """배열 축은 코드 1건당 항목 1건으로 평탄화된다(저장 순서 유지)."""
        fake = FakeSession(
            execute_queue=[
                [],
                [_entry("ce-0001", codes=["[10공수1-01-01]", "[10공수1-01-02]"])],
                [],
            ]
        )
        resp = _client(fake).get("/v1/alignments")
        assert resp.status_code == 200
        assert [i["standard_ref"] for i in resp.json()] == ["[10공수1-01-01]", "[10공수1-01-02]"]

    def test_standard_ref_filter_recheck_at_item_level(self) -> None:
        """standard_ref 필터는 행 매칭(SQL) 후 항목 수준으로 재대조한다 — 같은 행의 다른
        코드는 항목으로 새지 않는다."""
        fake = FakeSession(
            execute_queue=[
                [],
                [_entry("ce-0001", codes=["[10공수1-01-01]", "[10공수1-01-02]"])],
                [],
            ]
        )
        resp = _client(fake).get("/v1/alignments", params={"standard_ref": "[10공수1-01-02]"})
        assert resp.status_code == 200
        (item,) = resp.json()
        assert item["standard_ref"] == "[10공수1-01-02]"

    def test_axis_filter_queries_single_axis(self) -> None:
        """axis 필터를 주면 그 축만 조회한다(execute 1회·타 축 항목 0)."""
        fake = FakeSession(execute_queue=[[_entry("ce-0001")]])
        resp = _client(fake).get("/v1/alignments", params={"axis": "curriculum_entry"})
        assert resp.status_code == 200
        assert fake.execute_calls == 1
        assert {i["axis"] for i in resp.json()} == {"curriculum_entry"}

    def test_early_exit_skips_later_axes(self) -> None:
        """앞 축에서 offset+limit 항목이 차면 뒤 축은 조회하지 않는다(결정적 순서라 안전)."""
        fake = FakeSession(execute_queue=[[_link()], [_entry()], [_atom()]])
        resp = _client(fake).get("/v1/alignments", params={"limit": 1})
        assert resp.status_code == 200
        assert fake.execute_calls == 1
        (item,) = resp.json()
        assert item["axis"] == "concept_standard_link"

    def test_offset_slices_composed_order(self) -> None:
        """offset은 합성 순서에 적용된다 — 1축 1건을 건너뛰면 2축 항목부터 나온다."""
        fake = FakeSession(execute_queue=[[_link()], [_entry("ce-0001")], [_atom()]])
        resp = _client(fake).get("/v1/alignments", params={"offset": 1, "limit": 1})
        assert resp.status_code == 200
        (item,) = resp.json()
        assert item["axis"] == "curriculum_entry"

    def test_offset_beyond_items_returns_empty(self) -> None:
        """항목 수를 넘는 offset → 200 + [] (정직한 빈 페이지)."""
        fake = FakeSession(execute_queue=[[_link()]])
        resp = _client(fake).get("/v1/alignments", params={"offset": 500})
        assert resp.status_code == 200
        assert resp.json() == []

    def test_empty_stores_return_empty_list(self) -> None:
        """세 축 모두 빈 결과 → 200 + []."""
        resp = _client(FakeSession()).get("/v1/alignments")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_rejects_bad_parameters(self) -> None:
        """axis 미정의 값·limit/offset 범위 위반 → 422."""
        client = _client(FakeSession())
        assert client.get("/v1/alignments", params={"axis": "bogus"}).status_code == 422
        assert client.get("/v1/alignments", params={"limit": 0}).status_code == 422
        assert client.get("/v1/alignments", params={"limit": 201}).status_code == 422
        assert client.get("/v1/alignments", params={"offset": -1}).status_code == 422
        assert client.get("/v1/alignments", params={"offset": 10001}).status_code == 422
