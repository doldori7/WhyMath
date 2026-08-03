"""`pedagogy_content_slot` 상태별 건수 리포트 테스트(PED-06) — acceptance①.

구성:
  - `build_report`/`render_report`/`report_to_json` 순수 단위테스트(DB 0) — 화이트리스트
    0 채움·`total==0` "실행한 적이 없음" 문구·화이트리스트 밖 상태(드리프트) 처리.
  - **변별력 discriminating 테스트** — 실 PostgreSQL 필요(`pytest.mark.integration`,
    `tests/backend/harness/test_attempt_grading_shadow_report.py`의 async 엔진 seed/cleanup
    관례 답습). `pedagogy_content_slot` 행을 최소 FK 사슬(unit_spec→learning_objective→
    content_slot)로 직접 시딩해 리포트 값이 **실행 전(0) → 삽입 후(증가) → 상태 전이 후
    (재분배) → 정리 후(원복)**로 실제로 바뀌는지 실측한다(acceptance① "실행 전/후 값이
    실제로 바뀌는지 변별력 확인" 리터럴 요구).
"""

from __future__ import annotations

import pytest
from sqlalchemy import text, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from whymath_backend.config import Settings
from whymath_backend.db.models.pedagogy_dsl import (
    LearningObjective,
    PedagogyContentSlot,
    UnitSpec,
)
from whymath_backend.ops.pedagogy_content_slot_reach_report import (
    ALL_STATUSES,
    build_report,
    fetch_status_counts,
    render_report,
    report_to_json,
)
from whymath_backend.schema.enums import KnowledgeType

pytestmark = pytest.mark.filterwarnings("ignore")


# ──────────────────────────────────────────────────────────────────────────
# build_report / render_report / report_to_json — 순수 단위테스트(DB 0)
# ──────────────────────────────────────────────────────────────────────────
class TestBuildReportPure:
    def test_empty_counts_zero_fills_all_known_statuses(self) -> None:
        """관측치가 0건이어도 ALL_STATUSES 4개 키가 전부 0으로 채워진다(분모 누락 방지)."""
        report = build_report({})
        assert report.total == 0
        assert report.by_status == {status: 0 for status in ALL_STATUSES}
        assert report.unknown_statuses == {}

    def test_known_statuses_pass_through_and_total_sums(self) -> None:
        counts = {"DRAFT": 3, "PRESCREENED": 2, "APPROVED": 1, "REJECTED": 0}
        report = build_report(counts)
        assert report.total == 6
        assert report.by_status == counts

    def test_unknown_status_is_bucketed_separately_but_counted_in_total(self) -> None:
        """CHECK 제약 화이트리스트 밖 값(스키마 드리프트) — 조용히 삼키지 않고 따로 담는다."""
        report = build_report({"DRAFT": 1, "MYSTERY": 5})
        assert report.by_status["DRAFT"] == 1
        assert report.unknown_statuses == {"MYSTERY": 5}
        assert report.total == 6  # 실제 행 수는 항상 정직하게 보존

    def test_render_report_zero_total_says_never_run(self) -> None:
        """total==0 → "실행한 적이 없음"(측정 실패로 위장하지 않는다)."""
        rendered = render_report(build_report({}))
        assert "실행한 적이 없음" in rendered
        assert "0" in rendered

    def test_render_report_nonzero_total_shows_counts_not_never_run(self) -> None:
        rendered = render_report(build_report({"DRAFT": 4}))
        assert "실행한 적이 없음" not in rendered
        assert "총 건수: **4**" in rendered

    def test_render_report_lists_unknown_statuses_section(self) -> None:
        rendered = render_report(build_report({"MYSTERY": 2}))
        assert "화이트리스트 밖 상태" in rendered
        assert "MYSTERY" in rendered

    def test_report_to_json_roundtrip(self) -> None:
        report = build_report({"DRAFT": 1, "APPROVED": 2})
        payload = report_to_json(report)
        assert payload["total"] == 3
        assert payload["by_status"]["DRAFT"] == 1
        assert payload["by_status"]["APPROVED"] == 2
        assert payload["unknown_statuses"] == {}


# ──────────────────────────────────────────────────────────────────────────
# 변별력 discriminating 테스트(acceptance①) — 실 PostgreSQL 필요
# ──────────────────────────────────────────────────────────────────────────
_SECRET_SETTINGS = Settings()

# 이 테스트 전용 소단원/목표 id — 실제 파일럿(quadratic_maxmin)과 겹치지 않게 별도 네임스페이스.
_UNIT_ID = "PED-06-reach-report-probe"
_OBJECTIVE_ID = f"{_UNIT_ID}:obj-0"


async def _pg_reachable() -> bool:
    engine = create_async_engine(_SECRET_SETTINGS.database_url)
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
    finally:
        await engine.dispose()


def _unit_spec() -> UnitSpec:
    return UnitSpec(
        unit_id=_UNIT_ID,
        unit_version=1,
        api_version="v1",
        title="PED-06 리포트 변별력 프로브",
        curriculum_rev="2022",
        standard_codes=[],
        concept_nodes=[],
        yaml_sha256="0" * 64,
        compiler_ver="test",
        status="DRAFT",
    )


def _objective() -> LearningObjective:
    return LearningObjective(
        id=_OBJECTIVE_ID,
        unit_id=_UNIT_ID,
        unit_version=1,
        statement="프로브 목표",
        achievement_std="TEST-STD-0",
        k_type=KnowledgeType.CONCEPT,
        concept_nodes=[],
        slot_manifest={},
        exit_evidence={},
    )


def _slot(index: int) -> PedagogyContentSlot:
    return PedagogyContentSlot(
        id=f"{_OBJECTIVE_ID}:probe_slot:{index}",
        objective_id=_OBJECTIVE_ID,
        slot_type="probe_slot",
        payload={"body": f"프로브 슬롯 {index}", "reasoning_type": "probe_slot"},
        status="DRAFT",
    )


async def _cleanup() -> None:
    """FK CASCADE(unit_spec 삭제 → learning_objective → pedagogy_content_slot)로 일괄 정리."""
    engine = create_async_engine(_SECRET_SETTINGS.database_url)
    try:
        async with engine.begin() as conn:
            await conn.execute(text("DELETE FROM unit_spec WHERE unit_id = :u"), {"u": _UNIT_ID})
    finally:
        await engine.dispose()


@pytest.mark.integration
class TestDiscriminatingStatusCountsChange:
    """acceptance① — 실행 전(0)→삽입 후(증가)→상태 전이 후(재분배)→정리 후(원복) 실측.

    같은 이벤트 루프에서 전 과정을 await한다(`test_attempt_grading_shadow_report.py`의
    "단일 이벤트 루프" 관례 동형 — 헬퍼별 `asyncio.run()` 반복 호출은 죽은 루프에 바인딩된
    커넥션 풀 재사용 오류를 유발한다).
    """

    async def test_counts_rise_shift_and_restore(self) -> None:
        if not await _pg_reachable():
            pytest.skip("PostgreSQL 미도달 — 통합 테스트 건너뜀(WHYMATH_DATABASE_URL 확인)")

        await _cleanup()  # 이전 실행 잔재 방어(멱등 선행 정리)
        engine = create_async_engine(_SECRET_SETTINGS.database_url)
        try:
            sm = async_sessionmaker(engine, expire_on_commit=False)

            async def _snapshot() -> dict[str, int]:
                """실제 `fetch_status_counts`+`build_report`(테스트 대상 함수 그 자체)의 결과.

                테이블 전체를 세는 전역 관측이라 다른 데이터가 이미 있을 수 있다 — 그래서
                판정은 절대값이 아니라 이 스냅샷들 간 **델타**로 한다(병렬 실행·기존 데이터에
                안전).
                """
                async with sm() as session:
                    counts = await fetch_status_counts(session)
                return build_report(counts).by_status

            # ── 0. 실행 전 스냅샷 ──────────────────────────────────────────
            before = await _snapshot()

            # ── 1. 삽입 — unit_spec → learning_objective → 슬롯 3건(DRAFT) ────
            async with sm() as session:
                session.add(_unit_spec())
                await session.flush()
                session.add(_objective())
                await session.flush()
                session.add_all([_slot(0), _slot(1), _slot(2)])
                await session.commit()

            after_insert = await _snapshot()
            assert (
                after_insert["DRAFT"] - before["DRAFT"] == 3
            ), "삽입 직후 DRAFT 건수가 실측 3건 증가하지 않음(변별력 없음)"
            for status in ALL_STATUSES:
                if status == "DRAFT":
                    continue
                assert after_insert[status] == before[status], f"{status} 건수가 부당하게 변함"

            # ── 2. 상태 전이 — 슬롯 1건만 PRESCREENED로 승격 ──────────────────
            async with sm() as session:
                await session.execute(
                    update(PedagogyContentSlot)
                    .where(PedagogyContentSlot.id == f"{_OBJECTIVE_ID}:probe_slot:0")
                    .values(status="PRESCREENED", prescreen_score=3)
                )
                await session.commit()

            after_transition = await _snapshot()
            assert after_transition["DRAFT"] - before["DRAFT"] == 2, "DRAFT가 전이 후 줄지 않음"
            assert (
                after_transition["PRESCREENED"] - before["PRESCREENED"] == 1
            ), "상태 전이가 PRESCREENED 증가로 실측 반영되지 않음(변별력 없음)"

            # ── 3. 정리 — CASCADE 삭제 후 원복 ────────────────────────────────
            await _cleanup()
            after_cleanup = await _snapshot()
            assert after_cleanup == before, "정리 후 원복되지 않음"
        finally:
            await engine.dispose()
