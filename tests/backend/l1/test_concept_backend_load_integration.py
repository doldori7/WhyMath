"""개념그래프 → backend `Concept` 런타임 적재 *통합테스트* — 브리지 슬1 (WHYMATH_RUN_INTEGRATION).

마이그레이션 head가 적용된 **실 PostgreSQL**(`concept` 테이블)에 개념을 런타임 엔티티로 적재해
*UC↔UUID 브리지*가 실제로 서는지 본다(슬2/3/117이 UC 공간 투영을 봤다면, 여기선 backend
`concept` UUID PK·`code`=UC 행이 생기고 멱등·redaction·L2 결선 가능성이 성립하는지). CI
`backend — 마이그레이션·통합 (실 PG)` 잡이 `pgvector/pgvector:pg16` + `alembic upgrade head` 후
`WHYMATH_RUN_INTEGRATION=1`로 수집·실행한다(신규 CI 잡 불요 — 기존 잡이 `tests/backend/l1/`를 수집).
PG 미도달 시 graceful skip(슬117 미러).

검증:
  ① 적재 → `concept` row 존재·`code`=UC·name_ko·level=세부개념·유도 필드 반영
  ② **redaction** — description·formal_definition·intuitive_explanation이 실제 NULL
  ③ 멱등 — 같은 UC 재적재 시 행 1개·값 갱신·**UUID PK 보존**(브리지 안정성)
  ④ **L2 mastery 연결 가능성** — 적재된 concept UUID로 `concept_mastery_history`가 INSERT됨
     (UUID concept ↔ UC 브리지가 런타임 숙달 키로 동작 — get_current_mastery 폴백/조회 경로)
"""

from __future__ import annotations

import uuid

import pytest

from whymath_backend.config import Settings
from whymath_backend.l1.concept_graph.backend_concept import (
    BackendConceptRecord,
    populate_backend_concepts,
)
from whymath_backend.schema.enums import ConceptLevel, Subject

pytestmark = pytest.mark.integration

# 통합테스트 적재 키(UC 규약·정리 대상). 실 데이터 UC와 충돌하지 않도록 it- 접두 slug.
_UC_A = "UC.x.it.backend-concept-a"
_UC_B = "UC.x.it.backend-concept-b"


def _sync_engine() -> object:
    """통합테스트용 sync(psycopg) 엔진 — 정리·조회용 raw 엔진."""
    from sqlalchemy import create_engine
    from sqlalchemy.pool import NullPool

    settings = Settings()
    url = settings.sync_database_url
    if settings.db_disable_pool:
        return create_engine(url, poolclass=NullPool)
    return create_engine(url)


def _reachable() -> bool:
    """실 PG 도달 + `concept` 테이블 존재(마이그레이션 적용) 여부."""
    from sqlalchemy import text

    engine = _sync_engine()
    try:
        with engine.connect() as conn:  # type: ignore[attr-defined]
            conn.execute(text("SELECT count(*) FROM concept"))
        return True
    except Exception:
        return False
    finally:
        engine.dispose()  # type: ignore[attr-defined]


def _cleanup(keys: list[str]) -> None:
    """concept 적재 행 정리(UC code 기준) — 자식 mastery 행 먼저(FK 순서)."""
    from sqlalchemy import text

    engine = _sync_engine()
    try:
        with engine.begin() as conn:  # type: ignore[attr-defined]
            # 적재된 concept의 UUID로 들어간 mastery 자식 먼저 제거(④ 테스트 잔여).
            conn.execute(
                text(
                    "DELETE FROM concept_mastery_history WHERE concept_id IN "
                    "(SELECT concept_id FROM concept WHERE code = ANY(:keys))"
                ),
                {"keys": keys},
            )
            conn.execute(
                text("DELETE FROM concept WHERE code = ANY(:keys)"), {"keys": keys}
            )
    finally:
        engine.dispose()  # type: ignore[attr-defined]


def _skip_if_unreachable() -> None:
    if not _reachable():
        pytest.skip(
            "PostgreSQL 미도달(또는 마이그레이션 미적용) — 통합 테스트 건너뜀 "
            "(WHYMATH_DATABASE_URL·alembic upgrade head 확인)"
        )


def _record(
    code: str,
    *,
    name_ko: str = "극한",
    subject: Subject | None = Subject.미적분,
    intrinsic_difficulty: float | None = 2.17,
    misconceptions: list[dict[str, str]] | None = None,
) -> BackendConceptRecord:
    return BackendConceptRecord(
        code=code,
        name_ko=name_ko,
        level=ConceptLevel.세부개념,
        subject=subject,
        intrinsic_difficulty=intrinsic_difficulty,
        common_misconceptions=list(misconceptions or []),
    )


class TestBackendConceptRoundtrip:
    """① 적재 → row 존재·code=UC·유도 반영, ② redaction NULL."""

    def test_populate_creates_row_with_code_uc(self) -> None:
        _skip_if_unreachable()
        from sqlalchemy import text

        keys = [_UC_A]
        try:
            count = populate_backend_concepts(
                [
                    _record(
                        _UC_A,
                        name_ko="극한",
                        subject=Subject.미적분,
                        intrinsic_difficulty=2.17,
                        misconceptions=[{"misconception": "극한을 대입값으로 혼동"}],
                    )
                ],
                settings=Settings(),
            )
            assert count == 1

            engine = _sync_engine()
            try:
                with engine.connect() as conn:  # type: ignore[attr-defined]
                    row = conn.execute(
                        text(
                            "SELECT concept_id, code, name_ko, level, subject, "
                            "intrinsic_difficulty, common_misconceptions, "
                            "description, formal_definition, intuitive_explanation "
                            "FROM concept WHERE code = :c"
                        ),
                        {"c": _UC_A},
                    ).one()
                # ① 브리지·유도 반영.
                assert row.code == _UC_A  # UC = code(브리지 키)
                assert isinstance(row.concept_id, uuid.UUID)  # UUID PK 발급
                assert row.name_ko == "극한"
                assert row.level == "세부개념"  # 고정 유도(NOT NULL enum·한글 값)
                assert row.subject == "미적분"
                assert float(row.intrinsic_difficulty) == pytest.approx(2.17)
                # JSONB 오개념(자유형) — 자체 작성 주석(본문 아님).
                assert row.common_misconceptions == [
                    {"misconception": "극한을 대입값으로 혼동"}
                ]
                # ② redaction: 본문 3컬럼 NULL(검수 대기).
                assert row.description is None
                assert row.formal_definition is None
                assert row.intuitive_explanation is None
            finally:
                engine.dispose()  # type: ignore[attr-defined]
        finally:
            _cleanup(keys)

    def test_unmapped_subject_persists_null(self) -> None:
        _skip_if_unreachable()
        from sqlalchemy import text

        keys = [_UC_B]
        try:
            populate_backend_concepts(
                [_record(_UC_B, subject=None, intrinsic_difficulty=None)],
                settings=Settings(),
            )
            engine = _sync_engine()
            try:
                with engine.connect() as conn:  # type: ignore[attr-defined]
                    row = conn.execute(
                        text(
                            "SELECT subject, intrinsic_difficulty, common_misconceptions "
                            "FROM concept WHERE code = :c"
                        ),
                        {"c": _UC_B},
                    ).one()
                assert row.subject is None  # 미대응 도메인 → NULL(억지 매핑 0)
                assert row.intrinsic_difficulty is None
                assert row.common_misconceptions == []  # JSONB server_default '[]'
            finally:
                engine.dispose()  # type: ignore[attr-defined]
        finally:
            _cleanup(keys)


class TestIdempotentUuidPreserved:
    """③ 멱등 — 재적재 시 행 1개·값 갱신·UUID PK 보존(브리지 안정성)."""

    def test_reload_updates_in_place_and_preserves_uuid(self) -> None:
        _skip_if_unreachable()
        from sqlalchemy import text

        keys = [_UC_A]
        try:
            # 1차 적재 → UUID 확보.
            populate_backend_concepts(
                [_record(_UC_A, name_ko="첫 이름", subject=Subject.미적분)],
                settings=Settings(),
            )
            engine = _sync_engine()
            try:
                with engine.connect() as conn:  # type: ignore[attr-defined]
                    first_uuid = conn.execute(
                        text("SELECT concept_id FROM concept WHERE code = :c"),
                        {"c": _UC_A},
                    ).scalar_one()

                # 2차 적재(값 변경) → 같은 행 갱신·UUID 보존.
                populate_backend_concepts(
                    [_record(_UC_A, name_ko="둘째 이름", subject=Subject.기하)],
                    settings=Settings(),
                )
                with engine.connect() as conn:  # type: ignore[attr-defined]
                    rows = conn.execute(
                        text(
                            "SELECT concept_id, name_ko, subject FROM concept "
                            "WHERE code = :c"
                        ),
                        {"c": _UC_A},
                    ).all()
                # 행 1개(멱등)·값 갱신·**UUID 동일**(브리지 키 안정성 — FK 참조 보존).
                assert len(rows) == 1
                assert rows[0].concept_id == first_uuid
                assert rows[0].name_ko == "둘째 이름"
                assert rows[0].subject == "기하"
            finally:
                engine.dispose()  # type: ignore[attr-defined]
        finally:
            _cleanup(keys)


class TestL2MasteryBridge:
    """④ L2 mastery 연결 가능성 — 적재 concept UUID가 숙달 키로 동작(get_current_mastery 왕복).

    `concept_mastery_history.concept_id`는 §8.1 DDL에 REFERENCES가 없어 *FK가 아니다*(느슨참조).
    따라서 user_profile/concept FK 없이도 INSERT되지만, *브리지의 가치*는 런타임 L2 경로가 쓰는
    그 UUID가 곧 **개념그래프 UC에 닿는 backend concept UUID**라는 점이다 — 이 테스트는 적재된
    concept의 UUID를 mastery 키로 써 `get_current_mastery`가 되읽음을 보여, UUID concept ↔ UC
    브리지가 L2 숙달 조회 경로에서 성립함을 증명한다(약개념 추천: 이 UUID→code(UC)→그래프 메타).
    """

    def test_loaded_concept_uuid_usable_as_mastery_key(self) -> None:
        _skip_if_unreachable()
        import asyncio
        from datetime import UTC, datetime

        from sqlalchemy import text
        from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

        from whymath_backend.db.models.assessment import ConceptMasteryHistory
        from whymath_backend.l2.mastery_tracking import get_current_mastery

        keys = [_UC_A]
        user_id = uuid.uuid4()
        try:
            # 개념 적재(브리지) → backend concept UUID 확보.
            populate_backend_concepts(
                [_record(_UC_A, name_ko="극한")], settings=Settings()
            )
            engine = _sync_engine()
            try:
                with engine.connect() as conn:  # type: ignore[attr-defined]
                    concept_uuid = conn.execute(
                        text("SELECT concept_id FROM concept WHERE code = :c"),
                        {"c": _UC_A},
                    ).scalar_one()
            finally:
                engine.dispose()  # type: ignore[attr-defined]

            async def _exercise() -> float | None:
                aengine = create_async_engine(Settings().database_url)
                try:
                    maker = async_sessionmaker(aengine, expire_on_commit=False)
                    # 적재 concept UUID를 mastery 키로 INSERT(느슨참조 — FK 불요).
                    async with maker() as session:
                        session.add(
                            ConceptMasteryHistory(
                                user_id=user_id,
                                concept_id=concept_uuid,
                                measured_at=datetime.now(UTC),
                                mastery=0.42,
                                confidence=0.5,
                                sample_size=1,
                            )
                        )
                        await session.commit()
                    # L2 조회 경로가 브리지된 개념의 숙달을 되읽는다.
                    async with maker() as session:
                        return await get_current_mastery(session, user_id, concept_uuid)
                finally:
                    await aengine.dispose()

            mastery = asyncio.run(_exercise())
            assert mastery == pytest.approx(0.42)  # 브리지된 UUID가 숙달 키로 동작
        finally:
            # mastery 자식 정리(user_id 기준) + concept 정리.
            async def _cleanup_mastery() -> None:
                from sqlalchemy import text as _text
                from sqlalchemy.ext.asyncio import create_async_engine as _cae

                eng = _cae(Settings().database_url)
                try:
                    async with eng.begin() as conn:
                        await conn.execute(
                            _text(
                                "DELETE FROM concept_mastery_history WHERE user_id = :u"
                            ),
                            {"u": str(user_id)},
                        )
                finally:
                    await eng.dispose()

            import asyncio as _aio

            _aio.run(_cleanup_mastery())
            _cleanup(keys)
