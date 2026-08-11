"""PED-05 — coach `_grade_for`/`_standard_code_for` 개인화 슬롯 해석 seam.

두 축(`test_coach_pack_wiring.py`와 동형 관례):
- **hermetic**: `problem_id`/`user_id` 미해석 경로(프로필 없음·문항 없음·개념 미매핑)는 fake
  session/DB 없이 graceful None을 확인한다.
- **@integration(PG)**: 실제 `user_profile.grade`·**원자 축**(`concept.code == atom_node.code` →
  `atom_node.standard_codes`)이 값을 낸다(CUR-04 — 구 축 `concept_standard_link →
  achievement_standard`는 더 이상 쓰지 않는다). 구 축 잔재가 있어도(negative control) 무시되고
  원자 축 값만 반환되는지까지 함께 검증한다(변별력 — 조용히 구 축으로 폴백하는 회귀 방지).
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from pydantic import SecretStr
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from whymath_backend.api.coach import _grade_for, _standard_code_for
from whymath_backend.config import Settings, get_settings
from whymath_backend.db.models.achievement_standard import (
    AchievementStandard as OrmAchievementStandard,
)
from whymath_backend.db.models.atom_node import ATOM_REVIEW_STATUS_AI_ESTIMATED
from whymath_backend.db.models.atom_node import AtomNode as OrmAtomNode
from whymath_backend.db.models.concept import Concept, ProblemConcept
from whymath_backend.db.models.concept_standard_link import (
    ConceptStandardLink as OrmConceptStandardLink,
)
from whymath_backend.db.models.problem import Problem
from whymath_backend.db.models.user import UserProfile
from whymath_backend.schema.concept import Concept as ConceptSchema
from whymath_backend.schema.concept import ProblemConcept as ProblemConceptSchema
from whymath_backend.schema.enums import (
    ConceptLevel,
    ConceptRole,
    Curriculum,
    Persona,
    SourceType,
    Subject,
)
from whymath_backend.schema.problem import Problem as ProblemSchema
from whymath_backend.schema.standard import (
    AchievementStandard as SchemaAchievementStandard,
)
from whymath_backend.schema.standard import (
    ConceptStandardLink as SchemaConceptStandardLink,
)
from whymath_backend.schema.user import UserProfile as SchemaUserProfile

_SECRET = "integration-jwt-secret-0123456789abcdef"
_PRIMARY_CODE = "PED05-GRADE-STD-TEST"


class _FakeSession:
    """`session.get`만 필요한 hermetic 좌석 — `_grade_for` None 경로 확인용."""

    async def get(self, _model: Any, _pk: Any) -> Any:
        return None


# ──────────────────────────────────────────────────────────────────────────
# hermetic — None 폴백 경로(DB 미접촉 또는 조회 결과 없음)
# ──────────────────────────────────────────────────────────────────────────
async def test_grade_for_none_when_profile_missing() -> None:
    assert await _grade_for(_FakeSession(), uuid.uuid4()) is None  # type: ignore[arg-type]


async def test_standard_code_for_none_when_problem_id_none() -> None:
    assert await _standard_code_for(_FakeSession(), None) is None  # type: ignore[arg-type]


# ──────────────────────────────────────────────────────────────────────────
# @integration(PG) — 실제 조인이 값을 낸다
# ──────────────────────────────────────────────────────────────────────────
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


@pytest.mark.integration
async def test_grade_and_standard_code_resolve_on_real_pg() -> None:
    """CUR-04 — 원자 축(`atom_node.standard_codes`)이 값을 낸다. 구 축(`concept_standard_link`)
    잔재가 *같은 concept_code*에 남아 있어도(negative control) 무시되고 원자 축 값만 반환되는지
    함께 확인한다 — "조용히 구 축으로 폴백" 회귀를 잡는 변별력 검사(CLAUDE.md 변별력 원칙)."""
    if not await _pg_reachable():
        pytest.skip("실 PG 미도달 — WHYMATH_DATABASE_URL 확인(통합 잡에서 실행)")

    settings = _settings()
    uid = uuid.uuid4()
    cid = uuid.uuid4()
    pid = uuid.uuid4()
    pid_unmapped = uuid.uuid4()
    norm_id = "PED05-TEST-NORM-01"
    official_code = "[12미적01-01]"  # 원자 축(atom_node.standard_codes)이 반환해야 할 정답.
    # negative control — 같은 concept_code를 가리키는 구 축 잔재. 실제 로더는 원자 행(source_id
    # 미설정)을 이 축에 절대 연결하지 못하지만(모듈 docstring), 이 테스트는 "설령 잔재가 있어도
    # 새 코드가 더는 이 축을 보지 않는다"를 직접 증명하기 위해 *의도적으로* 삽입한다.
    stale_norm_id = "PED05-STALE-OLD-AXIS-NORM"
    stale_official_code = "[STALE-OLD-AXIS-SHOULD-BE-IGNORED]"
    sync_engine = create_engine(settings.sync_database_url)

    def _cleanup() -> None:
        with sync_engine.begin() as conn:
            conn.execute(
                text("DELETE FROM problem_concept WHERE problem_id = ANY(:p)"),
                {"p": [pid, pid_unmapped]},
            )
            conn.execute(
                text("DELETE FROM problem WHERE problem_id = ANY(:p)"),
                {"p": [pid, pid_unmapped]},
            )
            conn.execute(
                text("DELETE FROM concept_standard_link WHERE concept_code = :c"),
                {"c": _PRIMARY_CODE},
            )
            conn.execute(
                text("DELETE FROM achievement_standard WHERE norm_id = ANY(:n)"),
                {"n": [norm_id, stale_norm_id]},
            )
            conn.execute(text("DELETE FROM atom_node WHERE code = :c"), {"c": _PRIMARY_CODE})
            conn.execute(text("DELETE FROM concept WHERE concept_id = :c"), {"c": cid})
            conn.execute(text("DELETE FROM user_profile WHERE user_id = :u"), {"u": uid})

    async_engine = create_async_engine(settings.database_url)
    try:
        _cleanup()
        maker = async_sessionmaker(async_engine, expire_on_commit=False)
        async with maker() as s:
            s.add(
                UserProfile.from_schema(
                    SchemaUserProfile(user_id=uid, persona_primary=Persona.A_일반고고3, grade=12)
                )
            )
            s.add(
                Concept.from_schema(
                    ConceptSchema(
                        concept_id=cid,
                        code=_PRIMARY_CODE,
                        name_ko="PED-05 테스트 개념",
                        level=ConceptLevel.세부개념,
                    )
                )
            )
            for p in (pid, pid_unmapped):
                s.add(
                    Problem.from_schema(
                        ProblemSchema(
                            problem_id=p,
                            source_type=SourceType.자체생성,
                            curriculum_version=Curriculum.REVISION_2022,
                            valid_from_year=2022,
                            subject=Subject.공통,
                            unit_codes=["U-PED05"],
                            difficulty_overall=3.0,
                            answer="42",
                        )
                    )
                )
            await s.commit()
        async with maker() as s:
            s.add(
                ProblemConcept.from_schema(
                    ProblemConceptSchema(problem_id=pid, concept_id=cid, role=ConceptRole.PRIMARY)
                )
            )
            await s.commit()
        async with maker() as s:
            # 원자 축(정답 경로) — Concept.code == AtomNode.code 조인 키.
            s.add(
                OrmAtomNode(
                    code=_PRIMARY_CODE,
                    name_ko="PED-05 테스트 원자",
                    level="세부개념",
                    standard_codes=[official_code],
                    review_status=ATOM_REVIEW_STATUS_AI_ESTIMATED,
                )
            )
            s.add(
                OrmAchievementStandard.from_schema(
                    SchemaAchievementStandard(
                        norm_id=norm_id,
                        official_code=official_code,
                        curriculum_revision="2022 개정",
                        grade_band="고등학교",
                        school_type="고등학교",
                        subject="미적분Ⅰ",
                        domain="변화와 관계",
                        statement="PED-05 테스트 성취기준.",
                        source_url="https://ncic.example/ped05",
                    )
                )
            )
            # negative control — 구 축 잔재(위 docstring 참조). 새 코드가 이 값을 반환하면 회귀.
            s.add(
                OrmAchievementStandard.from_schema(
                    SchemaAchievementStandard(
                        norm_id=stale_norm_id,
                        official_code=stale_official_code,
                        curriculum_revision="2022 개정",
                        grade_band="고등학교",
                        school_type="고등학교",
                        subject="미적분Ⅰ",
                        domain="변화와 관계",
                        statement="PED-05 구 축 negative control 성취기준.",
                        source_url="https://ncic.example/ped05-stale",
                    )
                )
            )
            await s.commit()
        async with maker() as s:
            s.add(
                OrmConceptStandardLink.from_schema(
                    SchemaConceptStandardLink(
                        concept_code=_PRIMARY_CODE, norm_id=stale_norm_id, link_type="직접"
                    )
                )
            )
            await s.commit()

        async with async_sessionmaker(async_engine, expire_on_commit=False)() as s:
            assert await _grade_for(s, uid) == 12
            # 원자 축 값이 반환된다 — 구 축 negative control(stale_official_code)이 아니다.
            resolved = await _standard_code_for(s, pid)
            assert resolved == official_code
            assert resolved != stale_official_code
            # fail-soft — 개념 미매핑 문항은 None.
            assert await _standard_code_for(s, pid_unmapped) is None
            # 문항 없음 → None.
            assert await _standard_code_for(s, None) is None
            # 프로필 없는 user_id → None.
            assert await _grade_for(s, uuid.uuid4()) is None
    finally:
        get_settings.cache_clear()
        _cleanup()
        await async_engine.dispose()
        sync_engine.dispose()
