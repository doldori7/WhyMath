"""L2 목표 진행 상황 — `get_target_progress` 실 PG 통합 (기본 SKIP).

`get_target_progress`의 성취기준 커버리지 산정은 `achievement_standard`→`concept_standard_link`
→`concept`→`concept_mastery_history` 4단 실 조인이라, 단위테스트(`test_target_progress.py`)는
FakeSession으로 SELECT *순서*만 검증한다. 여기서는 그 조인이 스코프 밖 성취기준을 실제로
배제하고 관측 여부를 정확히 세는지 실 PG로 검증한다.

`test_learning_path_internal_edges_integration.py` 패턴 답습. **이 샌드박스엔 live PG가 없어
실행은 못 한다 — 작성만 하고 실행은 시도하지 않는다(이 환경의 알려진 제약, 에러 아님).**
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime

import pytest
from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from whymath_backend.config import Settings
from whymath_backend.db.models.achievement_standard import AchievementStandard
from whymath_backend.db.models.assessment import ConceptMasteryHistory
from whymath_backend.db.models.concept import Concept
from whymath_backend.db.models.concept_standard_link import ConceptStandardLink
from whymath_backend.db.models.user import UserProfile
from whymath_backend.l2.target_progress import get_target_progress
from whymath_backend.schema.assessment import ConceptMasteryHistory as MasteryHistorySchema
from whymath_backend.schema.concept import Concept as ConceptSchema
from whymath_backend.schema.enums import ConceptLevel, Persona, SchoolType
from whymath_backend.schema.standard import AchievementStandard as StandardSchema
from whymath_backend.schema.standard import ConceptStandardLink as LinkSchema
from whymath_backend.schema.user import UserProfile as UserProfileSchema

pytestmark = pytest.mark.integration

_SECRET = "integration-jwt-secret-0123456789abcdef"


def _settings() -> Settings:
    return Settings(jwt_secret_key=SecretStr(_SECRET))


async def _pg_reachable() -> bool:
    engine = create_async_engine(_settings().database_url)
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
    finally:
        await engine.dispose()


def _standard(norm_id: str, *, curriculum_revision: str, school_type: str) -> AchievementStandard:
    return AchievementStandard.from_schema(
        StandardSchema(
            norm_id=norm_id,
            official_code=f"[{norm_id}]",
            curriculum_revision=curriculum_revision,
            grade_band="고등학교",
            school_type=school_type,
            subject="수학",
            domain="변화와 관계",
            statement=f"{norm_id} 성취기준 본문(통합테스트 픽스처).",
            source_url="https://ncic.example/standards",
        )
    )


def _concept(cid: uuid.UUID, code: str, name: str) -> Concept:
    return Concept.from_schema(
        ConceptSchema(concept_id=cid, code=code, name_ko=name, level=ConceptLevel.세부개념)
    )


def _link(concept_code: str, norm_id: str) -> ConceptStandardLink:
    return ConceptStandardLink.from_schema(
        LinkSchema(concept_code=concept_code, norm_id=norm_id, link_type="직접")
    )


def _mastery(user_id: uuid.UUID, concept_id: uuid.UUID) -> ConceptMasteryHistory:
    return ConceptMasteryHistory.from_schema(
        MasteryHistorySchema(
            user_id=user_id,
            concept_id=concept_id,
            measured_at=datetime.now(UTC),
            mastery=0.7,
        )
    )


async def _cleanup(user_id: uuid.UUID, concept_ids: list[uuid.UUID], norm_ids: list[str]) -> None:
    """관측→링크→개념→성취기준→프로필 순 정리(FK 순서)."""
    engine = create_async_engine(_settings().database_url)
    cids = [str(c) for c in concept_ids]
    try:
        async with engine.begin() as conn:
            await conn.execute(
                text("DELETE FROM concept_mastery_history WHERE user_id = :uid"),
                {"uid": str(user_id)},
            )
            await conn.execute(
                text("DELETE FROM concept_standard_link WHERE norm_id = ANY(:nids)"),
                {"nids": norm_ids},
            )
            await conn.execute(
                text("DELETE FROM concept WHERE concept_id = ANY(:cids)"), {"cids": cids}
            )
            await conn.execute(
                text("DELETE FROM achievement_standard WHERE norm_id = ANY(:nids)"),
                {"nids": norm_ids},
            )
            await conn.execute(
                text("DELETE FROM user_profile WHERE user_id = :uid"), {"uid": str(user_id)}
            )
    finally:
        await engine.dispose()


def test_scope_excludes_out_of_revision_and_counts_observed_correctly() -> None:
    """스코프(2022 개정×고등학교) 2건 중 1건만 관측 → 50%. 스코프 밖(2015 개정)은 미집계."""
    if not asyncio.run(_pg_reachable()):
        pytest.skip("PostgreSQL 미도달 — 통합 테스트 건너뜀")

    sfx = uuid.uuid4().hex[:8]
    uid = uuid.uuid4()
    n1, n2, n_out = f"tp.{sfx}.n1", f"tp.{sfx}.n2", f"tp.{sfx}.nout"
    cx, cy, cz = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()

    async def _setup() -> None:
        engine = create_async_engine(_settings().database_url)
        try:
            sm = async_sessionmaker(engine, expire_on_commit=False)
            async with sm() as s:
                s.add(
                    UserProfile.from_schema(
                        UserProfileSchema(
                            user_id=uid,
                            persona_primary=Persona.A_일반고고3,
                            school_type=SchoolType.일반고,
                        )
                    )
                )
                s.add_all(
                    [
                        _standard(n1, curriculum_revision="2022 개정", school_type="고등학교"),
                        _standard(n2, curriculum_revision="2022 개정", school_type="고등학교"),
                        # 스코프 밖(2015 개정) — 관측 여부와 무관하게 집계에서 배제돼야 함.
                        _standard(n_out, curriculum_revision="2015 개정", school_type="고등학교"),
                    ]
                )
                await s.commit()
            async with sm() as s:
                s.add_all(
                    [
                        _concept(cx, f"UC.tp.{sfx}.x", "관측개념X"),
                        _concept(cy, f"UC.tp.{sfx}.y", "미관측개념Y"),
                        _concept(cz, f"UC.tp.{sfx}.z", "스코프밖개념Z"),
                    ]
                )
                await s.commit()
            async with sm() as s:
                s.add_all(
                    [
                        _link(f"UC.tp.{sfx}.x", n1),  # X는 N1에 연결 + 관측 → observed.
                        _link(f"UC.tp.{sfx}.y", n2),  # Y는 N2에 연결이나 관측 이력 없음.
                        _link(f"UC.tp.{sfx}.z", n_out),  # Z는 스코프 밖 N_out에 연결.
                        _mastery(uid, cx),
                        _mastery(uid, cz),  # 관측은 있으나 스코프 밖이라 집계 제외돼야 함.
                    ]
                )
                await s.commit()
        finally:
            await engine.dispose()

    async def _run() -> None:
        engine = create_async_engine(_settings().database_url)
        try:
            sm = async_sessionmaker(engine, expire_on_commit=False)
            async with sm() as session:
                progress = await get_target_progress(session, uid)
                assert progress.standard_coverage_scope == 2  # n1·n2만(n_out 제외).
                assert progress.standard_coverage_observed == 1  # n1만 관측(n2는 미관측).
                assert progress.standard_coverage_percent == pytest.approx(50.0)
        finally:
            await engine.dispose()

    try:
        asyncio.run(_setup())
        asyncio.run(_run())
    finally:
        asyncio.run(_cleanup(uid, [cx, cy, cz], [n1, n2, n_out]))
