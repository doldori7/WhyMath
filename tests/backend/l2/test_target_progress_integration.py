"""L2 목표 진행 상황 — `get_target_progress` 실 PG 통합 (기본 SKIP).

`get_target_progress`의 성취기준 커버리지 산정은 **원자 축**(CUR-04) 4단 실 조인
(`achievement_standard`→역인덱스, `concept_mastery_history`→`concept`→`atom_node`)이라,
단위테스트(`test_target_progress.py`)는 FakeSession으로 SELECT *순서·shape*만 검증한다. 여기서는
그 조인이 스코프 밖 성취기준을 실제로 배제하고 관측 여부를 정확히 세는지, 그리고 원자 축 매칭
여부(작동 신호)를 정확히 세는지 실 PG로 검증한다.

`test_learning_path_internal_edges_integration.py` 패턴 답습. **이 샌드박스엔 live PG가 없어
실행은 못 한다 — 작성만 하고 실행은 시도하지 않는다(이 환경의 알려진 제약, 에러 아님).**

CUR-04(acceptance④) 변별력 대조 테스트도 이 파일에 둔다 —
`test_atom_axis_matches_attainment_report_old_axis_finds_nothing`가 같은 fixture에서
`get_target_progress`(신 축)·`harness.standard_attainment_report`(신 축·기존 오라클)·구 축
counterfactual(인라인 재현) 셋을 대조한다.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime

import pytest
from pydantic import SecretStr
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from whymath_backend.config import Settings
from whymath_backend.db.models.achievement_standard import AchievementStandard
from whymath_backend.db.models.assessment import ConceptMasteryHistory
from whymath_backend.db.models.atom_node import ATOM_REVIEW_STATUS_AI_ESTIMATED, AtomNode
from whymath_backend.db.models.concept import Concept
from whymath_backend.db.models.concept_standard_link import ConceptStandardLink
from whymath_backend.db.models.user import UserProfile
from whymath_backend.harness.problem_bank_coverage import load_standards
from whymath_backend.harness.standard_attainment_report import (
    build_report,
    collect_attainment_inputs,
)
from whymath_backend.l2.target_progress import TargetProgress, get_target_progress
from whymath_backend.schema.assessment import ConceptMasteryHistory as MasteryHistorySchema
from whymath_backend.schema.concept import Concept as ConceptSchema
from whymath_backend.schema.enums import ConceptLevel, Persona, SchoolType
from whymath_backend.schema.standard import AchievementStandard as StandardSchema
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


def _atom_node(code: str, *, standard_codes: list[str]) -> AtomNode:
    """CUR-04 원자 축 픽스처 — `Concept.code == AtomNode.code` 조인 키(동일 키 공간).

    `concept_standard_link`(구 축)와 달리 `source_id`를 설정하지 않는다 — 실제 원자 백본 적재기
    (`l1/atom_graph/atom_backend_concept.py::upsert`)도 `source_id`를 세팅하지 않으므로, 이 픽스처가
    구 축 로더의 `{source_id: code}` 해석 맵에 절대 잡히지 않는 실제 원자 행의 모양을 그대로 재현한다.
    """
    return AtomNode(
        code=code,
        name_ko=f"{code} 원자 픽스처",
        level="세부개념",
        standard_codes=standard_codes,
        review_status=ATOM_REVIEW_STATUS_AI_ESTIMATED,
    )


def _mastery(
    user_id: uuid.UUID, concept_id: uuid.UUID, *, mastery: float = 0.7
) -> ConceptMasteryHistory:
    return ConceptMasteryHistory.from_schema(
        MasteryHistorySchema(
            user_id=user_id,
            concept_id=concept_id,
            measured_at=datetime.now(UTC),
            mastery=mastery,
        )
    )


async def _cleanup(
    user_id: uuid.UUID,
    concept_ids: list[uuid.UUID],
    norm_ids: list[str],
    *,
    atom_codes: list[str] | None = None,
) -> None:
    """관측→원자→개념→성취기준→프로필 순 정리(FK 순서). `atom_codes`는 `atom_node.code` 목록."""
    engine = create_async_engine(_settings().database_url)
    cids = [str(c) for c in concept_ids]
    try:
        async with engine.begin() as conn:
            await conn.execute(
                text("DELETE FROM concept_mastery_history WHERE user_id = :uid"),
                {"uid": str(user_id)},
            )
            if atom_codes:
                await conn.execute(
                    text("DELETE FROM atom_node WHERE code = ANY(:codes)"),
                    {"codes": atom_codes},
                )
            # 구 축 잔재 정리(이 파일의 테스트는 concept_standard_link를 더 이상 삽입하지 않지만,
            # 방어적으로 남겨둔다 — norm_ids 기준이라 없으면 0행 삭제로 무해).
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
    """스코프(2022 개정×고등학교) 2건 중 1건만 관측 → 50%. 스코프 밖(2015 개정)은 미집계.

    CUR-04 원자 축: X(원자 매칭+스코프 내 N1 관측)·Y(원자 매칭이나 측정 이력 없음)·
    Z(원자 매칭+측정 이력 있으나 스코프 밖 N_out) — 세 조합으로 "매칭됐다"와 "스코프 내에서
    관측됐다"가 서로 다른 조건임을 함께 검증한다(matched_concepts vs standard_coverage_observed).
    """
    if not asyncio.run(_pg_reachable()):
        pytest.skip("PostgreSQL 미도달 — 통합 테스트 건너뜀")

    sfx = uuid.uuid4().hex[:8]
    uid = uuid.uuid4()
    n1, n2, n_out = f"tp.{sfx}.n1", f"tp.{sfx}.n2", f"tp.{sfx}.nout"
    cx, cy, cz = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    code_x, code_y, code_z = f"tp.{sfx}.x", f"tp.{sfx}.y", f"tp.{sfx}.z"

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
                        _concept(cx, code_x, "관측개념X"),
                        _concept(cy, code_y, "미관측개념Y"),
                        _concept(cz, code_z, "스코프밖개념Z"),
                    ]
                )
                await s.commit()
            async with sm() as s:
                s.add_all(
                    [
                        # official_code는 _standard()의 `[{norm_id}]` 관례를 그대로 따른다.
                        _atom_node(code_x, standard_codes=[f"[{n1}]"]),
                        _atom_node(code_y, standard_codes=[f"[{n2}]"]),
                        _atom_node(code_z, standard_codes=[f"[{n_out}]"]),
                        _mastery(uid, cx),  # X는 원자 매칭 + 스코프 내(N1) → observed 기여.
                        _mastery(uid, cz),  # Z는 원자 매칭되나 스코프 밖(N_out) → 집계 제외.
                        # Y는 의도적으로 측정 이력 없음(원자 매칭 대상에서 아예 빠짐).
                    ]
                )
                await s.commit()
        finally:
            await engine.dispose()

    async def _run() -> TargetProgress:
        engine = create_async_engine(_settings().database_url)
        try:
            sm = async_sessionmaker(engine, expire_on_commit=False)
            async with sm() as session:
                return await get_target_progress(session, uid)
        finally:
            await engine.dispose()

    try:
        asyncio.run(_setup())
        progress = asyncio.run(_run())
        assert progress.standard_coverage_scope == 2  # n1·n2만(n_out 제외).
        assert progress.standard_coverage_observed == 1  # n1만 관측(n2는 미관측, n_out은 스코프 밖).
        assert progress.standard_coverage_percent == pytest.approx(50.0)
        # 작동 신호(CUR-04 acceptance⑤) — 측정 이력은 X·Z 2개념, 둘 다 원자 축에 매칭됐다
        # (Z가 스코프 밖으로 관측에서 빠지는 것과 "원자 축 매칭 자체"는 별개임을 증명).
        assert progress.standard_coverage_measured_concepts == 2
        assert progress.standard_coverage_matched_concepts == 2
    finally:
        asyncio.run(
            _cleanup(
                uid,
                [cx, cy, cz],
                [n1, n2, n_out],
                atom_codes=[code_x, code_y, code_z],
            )
        )


def test_atom_axis_matches_attainment_report_old_axis_finds_nothing() -> None:
    """CUR-04 acceptance④ — 신 축 두 표면(target_progress·standard_attainment_report)은 일치,
    구 축(concept_standard_link) counterfactual은 같은 데이터에서 아무것도 찾지 못한다.

    **정직 회계(설계 노트)**: `standard_coverage_percent`(이 학생의 *전체 스코프* 대비 커버리지)와
    `code_attainment_rate`(*전체 학생 모집단*의 이 성취기준 도달률)는 분모의 정의가 다르다(전자는
    이 학생의 스코프 성취기준 총수, 후자는 카탈로그의 코드 수) — 그래서 두 top-level 비율을
    무조건 같은 숫자로 강제하지 않는다(그렇게 강제하면 우연히 통과하는 위장 검증이 된다). 대신
    **같은 원자 축 조인이 만들어낸 같은 사실**(이 개념 → 이 성취기준코드)을 두 표면이 각자의
    지표로 모두 긍정하는지 대조한다 — 이것이 CUR-04가 실제로 고치는 불변식이다. 신선한
    `user_id`(uuid4)를 쓰므로 이 학생의 측정 이력 개수는 이 테스트가 전량 통제한다(델타 불요).
    """
    if not asyncio.run(_pg_reachable()):
        pytest.skip("PostgreSQL 미도달 — 통합 테스트 건너뜀")

    sfx = uuid.uuid4().hex[:10]
    uid = uuid.uuid4()
    cid = uuid.uuid4()
    concept_code = f"cur04.contrast.{sfx}"
    norm_id = f"cur04.{sfx}"
    official_code = f"[{norm_id}]"
    measured_at = datetime(2026, 1, 1, tzinfo=UTC)

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
                s.add(_standard(norm_id, curriculum_revision="2022 개정", school_type="고등학교"))
                s.add(_concept(cid, concept_code, "CUR-04 대조테스트 개념"))
                await s.commit()
            async with sm() as s:
                s.add(_atom_node(concept_code, standard_codes=[official_code]))
                # mastery 0.85 — L4 정본 도달 경계(0.8) 이상이라 harness 쪽 "도달"에도 함께 걸린다
                # (target_progress의 "관측"은 mastery 값과 무관 — 두 지표가 같은 값 1을 내도록
                # 의도적으로 도달 경계도 넘겨, 같은 데이터가 두 표면 모두에서 "실값"이 되게 한다).
                s.add(
                    ConceptMasteryHistory(
                        user_id=uid, concept_id=cid, measured_at=measured_at, mastery=0.85
                    )
                )
                await s.commit()
        finally:
            await engine.dispose()

    async def _measure_target_progress() -> TargetProgress:
        engine = create_async_engine(_settings().database_url)
        try:
            sm = async_sessionmaker(engine, expire_on_commit=False)
            async with sm() as session:
                return await get_target_progress(session, uid)
        finally:
            await engine.dispose()

    async def _measure_old_axis_counterfactual() -> list[str]:
        """CUR-04 이전 구 축 조인의 인라인 재현(운영 코드에서 삭제됐으므로 counterfactual로 재현).

        `_standard_code_for`/구 `get_target_progress`가 쓰던 정확히 그 조인
        (`concept_standard_link.concept_code == concept.code` → `achievement_standard`)을 이
        테스트 데이터에 대해 직접 실행해, "수정 전이었다면 무엇을 봤을지"를 라이브로 증명한다.
        """
        engine = create_async_engine(_settings().database_url)
        try:
            sm = async_sessionmaker(engine, expire_on_commit=False)
            async with sm() as session:
                stmt = (
                    select(AchievementStandard.official_code)
                    .join(
                        ConceptStandardLink,
                        ConceptStandardLink.norm_id == AchievementStandard.norm_id,
                    )
                    .where(ConceptStandardLink.concept_code == concept_code)
                )
                return list((await session.execute(stmt)).scalars().all())
        finally:
            await engine.dispose()

    async def _measure_report_attained_count() -> int:
        engine = create_async_engine(_settings().database_url)
        try:
            sm = async_sessionmaker(engine, expire_on_commit=False)
            async with sm() as session:
                inputs = await collect_attainment_inputs(session)
            catalog = load_standards(
                {
                    "standards": [
                        {
                            "norm_id": norm_id,
                            "code": official_code,
                            "curriculum_revision": "2022 개정",
                            "school_type": "고등학교",
                            "domain": "CUR-04 대조테스트",
                        }
                    ]
                }
            )
            report = build_report(inputs, catalog, revision="2022 개정")
            return report.attained_users_per_code.get(official_code, 0)
        finally:
            await engine.dispose()

    try:
        asyncio.run(_setup())
        progress = asyncio.run(_measure_target_progress())
        old_axis_hits = asyncio.run(_measure_old_axis_counterfactual())
        report_attained = asyncio.run(_measure_report_attained_count())

        # ① 구 축 counterfactual — CUR-04가 대체한 조인은 이 데이터에서 정확히 0행. 수정 전
        # 코드였다면 `_standard_code_for`도 구 `get_target_progress`도 이 값(빈 리스트)만 봤다.
        assert old_axis_hits == []

        # ② 신 축 — target_progress. 신선한 user라 측정 이력 개수는 정확히 1(원자 매칭도 1) —
        # 델타 없이 절대값으로 단정 가능하다(작동 신호 — CUR-04 acceptance⑤).
        assert progress.standard_coverage_measured_concepts == 1
        assert progress.standard_coverage_matched_concepts == 1
        assert progress.standard_coverage_observed == 1
        assert progress.standard_coverage_percent is not None
        assert progress.standard_coverage_percent > 0.0  # 구 축이었다면 0.0(①이 그 이유).

        # ③ 신 축 — standard_attainment_report(기존 오라클). 같은 원자 조인으로 같은
        # 성취기준코드에 정확히 1명(이 학생)이 도달했다고 독립적으로 계산한다.
        assert report_attained == 1

        # ④ 일치 — 두 표면 모두 "이 개념 → 이 성취기준" 원자 조인을 같은 결론(1)으로 성립시켰다.
        assert progress.standard_coverage_matched_concepts == report_attained
    finally:
        asyncio.run(_cleanup(uid, [cid], [norm_id], atom_codes=[concept_code]))
