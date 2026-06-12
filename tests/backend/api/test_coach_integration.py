"""coach 세션 라우터 통합테스트 — 실 PG로 dialogue + turn 영속 검증 (기본 SKIP).

`POST /v1/coach/sessions`가 ① dialogue 1행 + ② 학생/AI turn 2행을 실제 영속하는지 검증.
미성년 PII 외부 노출 금기 정합 검증을 위해 외부 user_id 토큰으로 본인 user_id가 적재되는지
도 확인(타인 데이터 차단 — slice 3 `test_me_integration` 패턴 답습).

get_settings만 오버라이드(jwt secret), get_session은 실 PG. FK 순서: dialogue commit
먼저 → turns commit. 정리는 자식(dialogue_turn) → 부모(dialogue) → 부모(user_profile).
"""

from __future__ import annotations

import asyncio
import uuid

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from whymath_backend.app import create_app
from whymath_backend.config import Settings, get_settings
from whymath_backend.db.models.user import UserProfile
from whymath_backend.schema.enums import Persona
from whymath_backend.schema.user import UserProfile as UserProfileSchema
from whymath_backend.security import create_access_token

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


async def _add_user(uid: uuid.UUID) -> None:
    engine = create_async_engine(_settings().database_url)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            session.add(
                UserProfile.from_schema(
                    UserProfileSchema(user_id=uid, persona_primary=Persona.A_일반고고3)
                )
            )
            await session.commit()
    finally:
        await engine.dispose()


async def _cleanup(uid: uuid.UUID, dialogue_ids: list[uuid.UUID]) -> None:
    engine = create_async_engine(_settings().database_url)
    dids = [str(d) for d in dialogue_ids]
    try:
        async with engine.begin() as conn:
            # FK 순서: 자식(dialogue_turn) → 부모(dialogue) → 부모(user_profile).
            await conn.execute(
                text("DELETE FROM dialogue_turn WHERE dialogue_id = ANY(:ids)"),
                {"ids": dids},
            )
            await conn.execute(
                text("DELETE FROM dialogue WHERE dialogue_id = ANY(:ids)"),
                {"ids": dids},
            )
            await conn.execute(
                text("DELETE FROM user_profile WHERE user_id = :uid"),
                {"uid": str(uid)},
            )
    finally:
        await engine.dispose()


async def _count_turns(dialogue_id: uuid.UUID) -> int:
    engine = create_async_engine(_settings().database_url)
    try:
        async with engine.connect() as conn:
            row = await conn.execute(
                text("SELECT COUNT(*) FROM dialogue_turn " "WHERE dialogue_id = :did"),
                {"did": str(dialogue_id)},
            )
            return int(row.scalar_one())
    finally:
        await engine.dispose()


def _client() -> TestClient:
    app = create_app()
    app.dependency_overrides[get_settings] = _settings
    return TestClient(app)


def test_create_session_persists_dialogue_and_two_turns_on_live_pg() -> None:
    """세션 생성 → 실 PG에 dialogue 1 + turn 2 영속. user_id 자동 결선."""
    if not asyncio.run(_pg_reachable()):
        pytest.skip(
            "PostgreSQL 미도달 — 통합 테스트 건너뜀 (WHYMATH_DATABASE_URL 확인)"
        )

    uid = uuid.uuid4()
    dialogue_ids: list[uuid.UUID] = []
    try:
        asyncio.run(_add_user(uid))
        token = create_access_token(uid, settings=_settings())
        auth = {"Authorization": f"Bearer {token}"}
        with _client() as client:
            resp = client.post(
                "/v1/coach/sessions",
                headers=auth,
                json={"student_input": "내 풀이는 (a+b)² = a² + b² 이렇게 했어"},
            )
            assert resp.status_code == 201, resp.text
            body = resp.json()
            dialogue_id = uuid.UUID(body["dialogue_id"])
            dialogue_ids.append(dialogue_id)

            # ① misconception 검출 + counterexample intervention 결선
            assert body["intervention"]["pattern"] == "counterexample"
            # ② 실 PG에 dialogue_turn 정확히 2행
            assert asyncio.run(_count_turns(dialogue_id)) == 2

            # ③ 무토큰 401(인증 게이트)
            assert (
                client.post(
                    "/v1/coach/sessions", json={"student_input": "음"}
                ).status_code
                == 401
            )
    finally:
        asyncio.run(_cleanup(uid, dialogue_ids))


def test_etag_round_trip_304_then_invalidate_on_append_on_live_pg() -> None:
    """GET → ETag → If-None-Match 304 → append → 옛 ETag로 200(자동 무효화)."""
    if not asyncio.run(_pg_reachable()):
        pytest.skip(
            "PostgreSQL 미도달 — 통합 테스트 건너뜀 (WHYMATH_DATABASE_URL 확인)"
        )

    uid = uuid.uuid4()
    dialogue_ids: list[uuid.UUID] = []
    try:
        asyncio.run(_add_user(uid))
        token = create_access_token(uid, settings=_settings())
        auth = {"Authorization": f"Bearer {token}"}
        with _client() as client:
            create = client.post(
                "/v1/coach/sessions", headers=auth, json={"student_input": "처음"}
            )
            did = uuid.UUID(create.json()["dialogue_id"])
            dialogue_ids.append(did)

            # 첫 GET — ETag 캡처
            r1 = client.get(f"/v1/coach/sessions/{did}", headers=auth)
            assert r1.status_code == 200
            etag = r1.headers["ETag"]

            # 같은 ETag로 재요청 → 304(캐시 적중, 빈 본문)
            r2 = client.get(
                f"/v1/coach/sessions/{did}",
                headers={**auth, "If-None-Match": etag},
            )
            assert r2.status_code == 304
            assert r2.content == b""

            # 턴 추가 → 옛 ETag 무효화
            client.post(
                f"/v1/coach/sessions/{did}/turns",
                headers=auth,
                json={"student_input": "두번째"},
            )
            r3 = client.get(
                f"/v1/coach/sessions/{did}",
                headers={**auth, "If-None-Match": etag},
            )
            assert r3.status_code == 200, "append 후 옛 ETag는 stale → 200"
            assert r3.headers["ETag"] != etag
            assert len(r3.json()["turns"]) == 4
    finally:
        asyncio.run(_cleanup(uid, dialogue_ids))


def test_get_session_returns_dialogue_with_ordered_turns_on_live_pg() -> None:
    """세션 생성→append→GET — turn 4행이 turn_order 오름차순으로 반환."""
    if not asyncio.run(_pg_reachable()):
        pytest.skip(
            "PostgreSQL 미도달 — 통합 테스트 건너뜀 (WHYMATH_DATABASE_URL 확인)"
        )

    uid = uuid.uuid4()
    dialogue_ids: list[uuid.UUID] = []
    try:
        asyncio.run(_add_user(uid))
        token = create_access_token(uid, settings=_settings())
        auth = {"Authorization": f"Bearer {token}"}
        with _client() as client:
            create = client.post(
                "/v1/coach/sessions", headers=auth, json={"student_input": "처음"}
            )
            did = uuid.UUID(create.json()["dialogue_id"])
            dialogue_ids.append(did)
            client.post(
                f"/v1/coach/sessions/{did}/turns",
                headers=auth,
                json={"student_input": "두번째"},
            )

            # GET — 4 turns 오름차순
            resp = client.get(f"/v1/coach/sessions/{did}", headers=auth)
            assert resp.status_code == 200, resp.text
            body = resp.json()
            assert body["dialogue"]["dialogue_id"] == str(did)
            turns = body["turns"]
            assert len(turns) == 4
            assert [t["turn_order"] for t in turns] == [1, 2, 3, 4]
            # 학생/AI 교차 순서: 1=student·2=assistant·3=student·4=assistant
            assert [t["role"] for t in turns] == [
                "student",
                "assistant",
                "student",
                "assistant",
            ]
            assert turns[0]["content"] == "처음"
            assert turns[2]["content"] == "두번째"

            # 존재하지 않는 dialogue → 404
            assert (
                client.get(
                    f"/v1/coach/sessions/{uuid.uuid4()}", headers=auth
                ).status_code
                == 404
            )

            # 무토큰 401
            assert client.get(f"/v1/coach/sessions/{did}").status_code == 401
    finally:
        asyncio.run(_cleanup(uid, dialogue_ids))


def test_append_turns_extends_existing_session_on_live_pg() -> None:
    """세션 생성 → 턴 추가 → 실 PG에 dialogue_turn 4행·turn_order 1·2·3·4 증분."""
    if not asyncio.run(_pg_reachable()):
        pytest.skip(
            "PostgreSQL 미도달 — 통합 테스트 건너뜀 (WHYMATH_DATABASE_URL 확인)"
        )

    uid = uuid.uuid4()
    dialogue_ids: list[uuid.UUID] = []
    try:
        asyncio.run(_add_user(uid))
        token = create_access_token(uid, settings=_settings())
        auth = {"Authorization": f"Bearer {token}"}
        with _client() as client:
            # 세션 생성 (turn_order 1, 2)
            create = client.post(
                "/v1/coach/sessions",
                headers=auth,
                json={"student_input": "처음 시도"},
            )
            assert create.status_code == 201
            did = uuid.UUID(create.json()["dialogue_id"])
            dialogue_ids.append(did)

            # 턴 추가 (turn_order 3, 4)
            append = client.post(
                f"/v1/coach/sessions/{did}/turns",
                headers=auth,
                json={"student_input": "두번째 시도, 잘 모르겠어"},
            )
            assert append.status_code == 201, append.text
            body = append.json()
            assert body["student_turn_order"] == 3
            assert body["assistant_turn_order"] == 4
            # 좌절 신호 → hint_level 상승(slice 3)
            assert body["decision"]["hint_level"] >= 2

            # 실 PG에 4행
            assert asyncio.run(_count_turns(did)) == 4

            # 존재하지 않는 dialogue → 404
            missing = client.post(
                f"/v1/coach/sessions/{uuid.uuid4()}/turns",
                headers=auth,
                json={"student_input": "음"},
            )
            assert missing.status_code == 404
    finally:
        asyncio.run(_cleanup(uid, dialogue_ids))


# ── 선수 복습 코칭 결선: POST /v1/coach/sessions가 막힌 선수 신호를 응답에 싣는다 ──
# 직전 슬(`GET /v1/me/.../coaching`) 통합 헬퍼와 동형 — 문제→개념(PRIMARY)·그 개념의 막힌
# 선수(concept_edge·약 mastery·concept_node 메타)를 실 PG에 적재하고 coach 세션 응답을 검증.

from datetime import datetime, timezone  # noqa: E402

from sqlalchemy.ext.asyncio import async_sessionmaker  # noqa: E402

from whymath_backend.db.models.assessment import ConceptMasteryHistory  # noqa: E402
from whymath_backend.db.models.concept import (  # noqa: E402
    Concept,
    ConceptEdge,
    ProblemConcept,
)
from whymath_backend.db.models.concept_node import ConceptNode  # noqa: E402
from whymath_backend.db.models.problem import Problem  # noqa: E402
from whymath_backend.schema.assessment import (  # noqa: E402
    ConceptMasteryHistory as ConceptMasteryHistorySchema,
)
from whymath_backend.schema.concept import Concept as ConceptSchema  # noqa: E402
from whymath_backend.schema.concept import (  # noqa: E402
    ProblemConcept as ProblemConceptSchema,
)
from whymath_backend.schema.enums import (  # noqa: E402
    ConceptLevel,
    ConceptRole,
    Curriculum,
    EdgeType,
    SourceType,
    Subject,
)
from whymath_backend.schema.problem import Problem as ProblemSchema  # noqa: E402


async def _add_all(*objs: object) -> None:
    engine = create_async_engine(_settings().database_url)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            session.add_all(list(objs))
            await session.commit()
    finally:
        await engine.dispose()


def _concept_with_code(cid: uuid.UUID, code: str, name: str) -> Concept:
    return Concept.from_schema(
        ConceptSchema(
            concept_id=cid, code=code, name_ko=name, level=ConceptLevel.세부개념
        )
    )


def _node_meta(uc: str, name_ko: str, domain: str, review_status: str) -> ConceptNode:
    return ConceptNode(
        concept_id=uc, name_ko=name_ko, domain=domain, review_status=review_status
    )


def _prereq_edge(from_id: uuid.UUID, to_id: uuid.UUID, strength: float) -> ConceptEdge:
    """선수 엣지 — from(선수)이 to(후행)의 선수."""
    return ConceptEdge(
        from_concept_id=from_id,
        to_concept_id=to_id,
        edge_type=EdgeType.PREREQUISITE.value,
        edge_strength=strength,
    )


def _mastery_row(
    uid: uuid.UUID, cid: uuid.UUID, measured_at: datetime, mastery: float
) -> ConceptMasteryHistory:
    return ConceptMasteryHistory.from_schema(
        ConceptMasteryHistorySchema(
            user_id=uid,
            concept_id=cid,
            measured_at=measured_at,
            mastery=mastery,
            sample_size=1,
        )
    )


def _problem(pid: uuid.UUID, suffix: str) -> Problem:
    return Problem.from_schema(
        ProblemSchema(
            problem_id=pid,
            source_type=SourceType.자체생성,
            curriculum_version=Curriculum.REVISION_2022,
            valid_from_year=2022,
            subject=Subject.공통,
            unit_codes=[f"U-{suffix}"],
        )
    )


def _problem_concept(pid: uuid.UUID, cid: uuid.UUID) -> ProblemConcept:
    return ProblemConcept.from_schema(
        ProblemConceptSchema(problem_id=pid, concept_id=cid, role=ConceptRole.PRIMARY)
    )


async def _cleanup_prereq(
    uid: uuid.UUID,
    *,
    problem_ids: list[uuid.UUID],
    concept_ids: list[uuid.UUID],
    uc_ids: list[str],
    dialogue_ids: list[uuid.UUID],
) -> None:
    """FK 순서 정리 — dialogue_turn→dialogue→problem_concept·concept_edge·mastery→
    concept_node→problem·concept→user_profile."""
    engine = create_async_engine(_settings().database_url)
    dids = [str(d) for d in dialogue_ids]
    pids = [str(p) for p in problem_ids]
    cids = [str(c) for c in concept_ids]
    try:
        async with engine.begin() as conn:
            await conn.execute(
                text("DELETE FROM dialogue_turn WHERE dialogue_id = ANY(:ids)"),
                {"ids": dids},
            )
            await conn.execute(
                text("DELETE FROM dialogue WHERE dialogue_id = ANY(:ids)"), {"ids": dids}
            )
            await conn.execute(
                text("DELETE FROM problem_concept WHERE problem_id = ANY(:ids)"),
                {"ids": pids},
            )
            await conn.execute(
                text("DELETE FROM concept_edge WHERE from_concept_id = ANY(:ids)"),
                {"ids": cids},
            )
            await conn.execute(
                text("DELETE FROM concept_mastery_history WHERE user_id = :uid"),
                {"uid": str(uid)},
            )
            await conn.execute(
                text("DELETE FROM concept_node WHERE concept_id = ANY(:ids)"),
                {"ids": uc_ids},
            )
            await conn.execute(
                text("DELETE FROM problem WHERE problem_id = ANY(:ids)"), {"ids": pids}
            )
            await conn.execute(
                text("DELETE FROM concept WHERE concept_id = ANY(:ids)"), {"ids": cids}
            )
            await conn.execute(
                text("DELETE FROM user_profile WHERE user_id = :uid"), {"uid": str(uid)}
            )
    finally:
        await engine.dispose()


def test_coach_session_surfaces_prerequisite_coaching_on_live_pg() -> None:
    """POST /v1/coach/sessions(problem_id) — 막힌 선수 있으면 prerequisite_coaching 노출.

    end-to-end:
      ① 문제→개념 C(PRIMARY)·C의 막힌 선수 P(concept_edge to=C·from=P·약 mastery·메타) 적재 →
         코칭 응답 `prerequisite_coaching.focus=='prerequisite_review'`·선수 이름(일차함수) 포함.
      ② 막힌 선수 없는 문제(개념엔 선수 엣지 없음) → `prerequisite_coaching is None`.
      ③ stateless /v1/coach는 problem_id 없어 항상 None.
    """
    if not asyncio.run(_pg_reachable()):
        pytest.skip("PostgreSQL 미도달 — 통합 테스트 건너뜀")

    uid = uuid.uuid4()
    sfx = uid.hex[:8]
    uc_c = f"UC.test.{sfx}.co.post"  # 후행(문제 개념)
    uc_pw = f"UC.test.{sfx}.co.preweak"  # 막힌 선수
    uc_nolink = f"UC.test.{sfx}.co.nolink"  # 선수 없는 개념(②)
    c_post, c_pw, c_nolink = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    pid_blocked, pid_clear = uuid.uuid4(), uuid.uuid4()
    t1 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    dialogue_ids: list[uuid.UUID] = []
    try:
        asyncio.run(_add_user(uid))
        asyncio.run(
            _add_all(
                _concept_with_code(c_post, uc_c, "이차함수"),  # 문제 개념(후행)
                _concept_with_code(c_pw, uc_pw, "일차함수"),  # 막힌 선수
                _concept_with_code(c_nolink, uc_nolink, "집합"),  # 선수 없는 개념
            )
        )
        asyncio.run(_add_all(_node_meta(uc_pw, "일차함수", "[중]함수", "reviewed")))
        asyncio.run(
            _add_all(
                _problem(pid_blocked, sfx + "b"),
                _problem(pid_clear, sfx + "c"),
            )
        )
        asyncio.run(
            _add_all(
                _problem_concept(pid_blocked, c_post),  # 막힌 선수 있는 문제
                _problem_concept(pid_clear, c_nolink),  # 선수 없는 문제
            )
        )
        # concept_edge — P는 C의 선수(to==c_post·from==c_pw). c_nolink엔 선수 없음.
        asyncio.run(_add_all(_prereq_edge(c_pw, c_post, 0.9)))
        # mastery — 선수 P 약점(0.2·막힘).
        asyncio.run(_add_all(_mastery_row(uid, c_pw, t1, 0.2)))

        token = create_access_token(uid, settings=_settings())
        auth = {"Authorization": f"Bearer {token}"}
        with _client() as client:
            # ① 막힌 선수 있는 문제 → 선수 복습 코칭 노출.
            resp = client.post(
                "/v1/coach/sessions",
                headers=auth,
                json={"student_input": "이거 어떻게 풀어?", "problem_id": str(pid_blocked)},
            )
            assert resp.status_code == 201, resp.text
            body = resp.json()
            dialogue_ids.append(uuid.UUID(body["dialogue_id"]))
            pc = body["prerequisite_coaching"]
            assert pc is not None
            assert pc["focus"] == "prerequisite_review"
            assert "일차함수" in pc["prompt"]  # 선수 이름(자체 코칭 문구)
            assert "일차함수" in pc["rationale"]
            # 톤 가드 — 금기 표현 부재(재사용 L4 함수 보장).
            for forbidden in ("빨리", "정답", "틀렸"):
                assert forbidden not in pc["prompt"]

            # ② 막힌 선수 없는 문제 → None.
            resp = client.post(
                "/v1/coach/sessions",
                headers=auth,
                json={"student_input": "이거는?", "problem_id": str(pid_clear)},
            )
            assert resp.status_code == 201, resp.text
            body = resp.json()
            dialogue_ids.append(uuid.UUID(body["dialogue_id"]))
            assert body["prerequisite_coaching"] is None

            # ③ stateless /v1/coach → 항상 None(problem_id 없음·DB 미사용).
            resp = client.post(
                "/v1/coach",
                headers=auth,
                json={"student_input": "이거 어떻게 풀어?"},
            )
            assert resp.status_code == 200, resp.text
            assert resp.json()["prerequisite_coaching"] is None
    finally:
        asyncio.run(
            _cleanup_prereq(
                uid,
                problem_ids=[pid_blocked, pid_clear],
                concept_ids=[c_post, c_pw, c_nolink],
                uc_ids=[uc_c, uc_pw, uc_nolink],
                dialogue_ids=dialogue_ids,
            )
        )
