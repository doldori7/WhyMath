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
            # FK 순서: 자식(dialogue_turn·attempt_event) → 부모(dialogue) → 부모(user_profile).
            await conn.execute(
                text("DELETE FROM dialogue_turn WHERE dialogue_id = ANY(:ids)"),
                {"ids": dids},
            )
            await conn.execute(
                text("DELETE FROM attempt_event WHERE user_id = :uid"),
                {"uid": str(uid)},
            )
            # WH-1 2단계 슬라이스 3 — 활성 가설 행 정리(user 단위·dialogue FK 없음).
            await conn.execute(
                text("DELETE FROM misconception_hypothesis WHERE user_id = :uid"),
                {"uid": str(uid)},
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


async def _verify_events(uid: uuid.UUID) -> list[tuple[str, bool]]:
    """user의 검산결과 attempt_event를 (event_type, passed) 목록으로 — ① 적재 검증용."""
    engine = create_async_engine(_settings().database_url)
    try:
        async with engine.connect() as conn:
            rows = await conn.execute(
                text(
                    "SELECT event_type::text, (event_data->>'passed')::bool "
                    "FROM attempt_event "
                    "WHERE user_id = :uid AND event_type = '검산결과' "
                    "ORDER BY event_at"
                ),
                {"uid": str(uid)},
            )
            return [(str(r[0]), bool(r[1])) for r in rows.all()]
    finally:
        await engine.dispose()


async def _hint_events(uid: uuid.UUID) -> list[int]:
    """user의 힌트제공 attempt_event hint_level을 event_at 오름차순 목록으로 — ⑤ 적재 검증용."""
    engine = create_async_engine(_settings().database_url)
    try:
        async with engine.connect() as conn:
            rows = await conn.execute(
                text(
                    "SELECT (event_data->>'hint_level')::int "
                    "FROM attempt_event "
                    "WHERE user_id = :uid AND event_type = '힌트제공' "
                    "ORDER BY event_at"
                ),
                {"uid": str(uid)},
            )
            return [int(r[0]) for r in rows.all()]
    finally:
        await engine.dispose()


async def _compute_hint_metric(uid: uuid.UUID) -> dict[str, object]:
    """실 PG에서 compute_wh1_surrogate_metrics를 돌려 ⑤ 상태·표본 수를 뽑는다(결선 검증)."""
    from whymath_backend.harness.wh1_evaluation import compute_wh1_surrogate_metrics

    engine = create_async_engine(_settings().database_url)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            metrics = await compute_wh1_surrogate_metrics(session, user_id=uid)
            return {
                "help_status": metrics.help_reduction_slope.status.value,
                "help_value": metrics.help_reduction_slope.value,
                "sample_hint_events": metrics.sample_hint_events,
            }
    finally:
        await engine.dispose()


async def _active_hypotheses(uid: uuid.UUID) -> list[tuple[str, float, int, int]]:
    """user의 *활성* misconception_hypothesis 행을 (mid, confidence, turns_since, count)로
    confidence 내림차순 반환 — WH-1 2단계 슬라이스 3 per-turn 영속 검증용."""
    engine = create_async_engine(_settings().database_url)
    try:
        async with engine.connect() as conn:
            rows = await conn.execute(
                text(
                    "SELECT misconception_id, confidence::float, "
                    "turns_since_evidence, evidence_count "
                    "FROM misconception_hypothesis "
                    "WHERE user_id = :uid AND is_active = TRUE "
                    "ORDER BY confidence DESC, misconception_id"
                ),
                {"uid": str(uid)},
            )
            return [(str(r[0]), float(r[1]), int(r[2]), int(r[3])) for r in rows.all()]
    finally:
        await engine.dispose()


def _client() -> TestClient:
    app = create_app()
    app.dependency_overrides[get_settings] = _settings
    return TestClient(app)


def test_create_session_persists_dialogue_and_two_turns_on_live_pg() -> None:
    """세션 생성 → 실 PG에 dialogue 1 + turn 2 영속. user_id 자동 결선."""
    if not asyncio.run(_pg_reachable()):
        pytest.skip("PostgreSQL 미도달 — 통합 테스트 건너뜀 (WHYMATH_DATABASE_URL 확인)")

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
                client.post("/v1/coach/sessions", json={"student_input": "음"}).status_code == 401
            )
    finally:
        asyncio.run(_cleanup(uid, dialogue_ids))


def test_etag_round_trip_304_then_invalidate_on_append_on_live_pg() -> None:
    """GET → ETag → If-None-Match 304 → append → 옛 ETag로 200(자동 무효화)."""
    if not asyncio.run(_pg_reachable()):
        pytest.skip("PostgreSQL 미도달 — 통합 테스트 건너뜀 (WHYMATH_DATABASE_URL 확인)")

    uid = uuid.uuid4()
    dialogue_ids: list[uuid.UUID] = []
    try:
        asyncio.run(_add_user(uid))
        token = create_access_token(uid, settings=_settings())
        auth = {"Authorization": f"Bearer {token}"}
        with _client() as client:
            create = client.post("/v1/coach/sessions", headers=auth, json={"student_input": "처음"})
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
        pytest.skip("PostgreSQL 미도달 — 통합 테스트 건너뜀 (WHYMATH_DATABASE_URL 확인)")

    uid = uuid.uuid4()
    dialogue_ids: list[uuid.UUID] = []
    try:
        asyncio.run(_add_user(uid))
        token = create_access_token(uid, settings=_settings())
        auth = {"Authorization": f"Bearer {token}"}
        with _client() as client:
            create = client.post("/v1/coach/sessions", headers=auth, json={"student_input": "처음"})
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
            assert client.get(f"/v1/coach/sessions/{uuid.uuid4()}", headers=auth).status_code == 404

            # 무토큰 401
            assert client.get(f"/v1/coach/sessions/{did}").status_code == 401
    finally:
        asyncio.run(_cleanup(uid, dialogue_ids))


def test_append_turns_extends_existing_session_on_live_pg() -> None:
    """세션 생성 → 턴 추가 → 실 PG에 dialogue_turn 4행·turn_order 1·2·3·4 증분."""
    if not asyncio.run(_pg_reachable()):
        pytest.skip("PostgreSQL 미도달 — 통합 테스트 건너뜀 (WHYMATH_DATABASE_URL 확인)")

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
# 선수(concept_edge·약 mastery·atom_node 메타)를 실 PG에 적재하고 coach 세션 응답을 검증.
#
# ⚠️ 메타 시드 축(ARCH-13에서 교정): 이 헬퍼는 원래 구 437 `concept_node`에 시드했는데, S0-4d로
# L2 enrich가 `atom_node`로 전환된 뒤에도 갱신되지 않은 잔재였다. 울타리 이전에는 축이 어긋나도
# 행이 그냥 통과했으므로(enrich만 None) **아무도 읽지 않는 테이블에 시드하고 우연히 통과**하고
# 있었다. ARCH-13 축 울타리가 이 드리프트를 red로 드러냈고, 여기서 `atom_node`로 정렬한다
# (`test_me_integration.py::_node_meta`와 동형). 울타리를 약화시키는 대신 시드를 고치는 것이
# 맞다 — runtime truth source는 원자 단일이기 때문이다.

from datetime import datetime, timezone  # noqa: E402

from whymath_backend.db.models.assessment import ConceptMasteryHistory  # noqa: E402
from whymath_backend.db.models.atom_node import AtomNode  # noqa: E402
from whymath_backend.db.models.concept import (  # noqa: E402
    Concept,
    ConceptEdge,
    ProblemConcept,
)
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
        ConceptSchema(concept_id=cid, code=code, name_ko=name, level=ConceptLevel.세부개념)
    )


def _node_meta(uc: str, name_ko: str, domain: str, review_status: str) -> AtomNode:
    """원자 축 안전 메타 행(code PK) — S0-4d로 enrich가 `fetch_atom_node_meta`로 전환됐다.

    `test_me_integration.py::_node_meta`와 동형: 응답 DTO의 `domain` 값 소스가 원자
    `subject_area`이므로 인자 `domain`을 그 컬럼에 시드한다(필드명 유지·값 소스 교체). `level`은
    NOT NULL이라 시드 필수지만 enrich 대상이 아니라 표시 상수 '세부개념'을 박는다(값 무관).
    """
    return AtomNode(
        code=uc,
        name_ko=name_ko,
        level="세부개념",
        subject_area=domain,
        review_status=review_status,
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
    atom_node→problem·concept→user_profile."""
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
                text("DELETE FROM dialogue WHERE dialogue_id = ANY(:ids)"),
                {"ids": dids},
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
            # atom_node PK는 code(=concept.code=UC 브리지 키)라 code 컬럼으로 정리한다(ARCH-13).
            await conn.execute(
                text("DELETE FROM atom_node WHERE code = ANY(:ids)"),
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
                json={
                    "student_input": "이거 어떻게 풀어?",
                    "problem_id": str(pid_blocked),
                },
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


def test_session_create_logs_verify_event_on_live_pg() -> None:
    """student_solution 제출 → 검산결과 attempt_event 1행 적재(passed= 거짓관계 유무).

    WH-1 지표 ① 적재 결선: 거짓 수치관계(2+3=6) 포함 풀이는 passed False·미포함은 passed True.
    빈 풀이(student_solution 없음)는 적재 0(false-pass 방지). stateless /v1/coach는 미적재.
    """
    if not asyncio.run(_pg_reachable()):
        pytest.skip("PostgreSQL 미도달 — 통합 테스트 건너뜀 (WHYMATH_DATABASE_URL 확인)")

    uid = uuid.uuid4()
    dialogue_ids: list[uuid.UUID] = []
    try:
        asyncio.run(_add_user(uid))
        token = create_access_token(uid, settings=_settings())
        auth = {"Authorization": f"Bearer {token}"}
        with _client() as client:
            # ① 거짓 수치관계 풀이 → passed False.
            r1 = client.post(
                "/v1/coach/sessions",
                headers=auth,
                json={
                    "student_input": "풀었어",
                    "student_solution": "2+3=6 이므로 답은 6",
                },
            )
            assert r1.status_code == 201, r1.text
            dialogue_ids.append(uuid.UUID(r1.json()["dialogue_id"]))

            # ② 참 풀이 → passed True.
            r2 = client.post(
                "/v1/coach/sessions",
                headers=auth,
                json={
                    "student_input": "풀었어",
                    "student_solution": "2+3=5 이므로 답은 5",
                },
            )
            assert r2.status_code == 201, r2.text
            dialogue_ids.append(uuid.UUID(r2.json()["dialogue_id"]))

            # ③ 빈 풀이(student_solution 없음) → 적재 0(false-pass 방지).
            r3 = client.post(
                "/v1/coach/sessions",
                headers=auth,
                json={"student_input": "그냥 대화만"},
            )
            assert r3.status_code == 201, r3.text
            dialogue_ids.append(uuid.UUID(r3.json()["dialogue_id"]))

            events = asyncio.run(_verify_events(uid))
            # 정확히 2행(빈 풀이는 미적재)·event_type 검산결과·passed [False, True].
            assert len(events) == 2
            assert all(et == "검산결과" for et, _ in events)
            assert sorted(p for _, p in events) == [False, True]
    finally:
        asyncio.run(_cleanup(uid, dialogue_ids))


def test_session_multiturn_logs_hint_events_on_live_pg() -> None:
    """세션 생성 + 다턴 append → 힌트제공 attempt_event N행 적재(decision.hint_level·supply).

    WH-1 지표 ⑤ 적재 결선: create_session 1행 + append_turns 매 턴 1행 = 총 3행(hint_level
    1~4·decision이 산출). stateless /v1/coach는 미적재(DB 무접근 계약). 적재된 시계열로
    compute_wh1_surrogate_metrics ⑤가 MEASURED(또는 표본 부족 시 NO_DATA)가 된다.
    """
    if not asyncio.run(_pg_reachable()):
        pytest.skip("PostgreSQL 미도달 — 통합 테스트 건너뜀 (WHYMATH_DATABASE_URL 확인)")

    uid = uuid.uuid4()
    dialogue_ids: list[uuid.UUID] = []
    try:
        asyncio.run(_add_user(uid))
        token = create_access_token(uid, settings=_settings())
        auth = {"Authorization": f"Bearer {token}"}
        with _client() as client:
            # 세션 생성(턴 1) — create_session이 힌트 1행 적재.
            r1 = client.post(
                "/v1/coach/sessions",
                headers=auth,
                json={
                    "student_input": "답이 뭐야 그냥 알려줘",
                    "polya_state": {"prev_hint_level": 1},
                },
            )
            assert r1.status_code == 201, r1.text
            did = uuid.UUID(r1.json()["dialogue_id"])
            dialogue_ids.append(did)

            # append 2회 — 각 턴 힌트 1행 적재(총 3행).
            for _ in range(2):
                ra = client.post(
                    f"/v1/coach/sessions/{did}/turns",
                    headers=auth,
                    json={
                        "student_input": "답 알려줘",
                        "polya_state": {"prev_hint_level": 1},
                    },
                )
                assert ra.status_code == 201, ra.text

            levels = asyncio.run(_hint_events(uid))
            # 정확히 3행(create 1 + append 2)·각 hint_level 1~4 범위.
            assert len(levels) == 3
            assert all(1 <= lvl <= 4 for lvl in levels)

            # 적재된 시계열로 ⑤ 지표 계산 — 3점이라 종단 표본 충족 → MEASURED(또는 NO_DATA).
            metrics = asyncio.run(_compute_hint_metric(uid))
            assert metrics["sample_hint_events"] == 3
            assert metrics["help_status"] in ("measured", "no_data")
    finally:
        asyncio.run(_cleanup(uid, dialogue_ids))


# ── WH-1 2단계 §8.4 슬라이스 3: 활성 가설 세트 per-turn 영속·노출 결선 ──
# create_session·append_turns가 매칭(증거)으로 활성 가설 세트를 갱신·영속하고 응답
# active_hypotheses로 노출하는지 검증. 매칭 유발 입력은 catalog의 제곱 분배 오류
# `(a+b)² = a² + b²`(기존 test_create_session...이 counterexample intervention으로 이미 검증).

_SQUARE_DISTRIB_INPUT = "내 풀이는 (a+b)² = a² + b² 이렇게 했어"
_NO_MATCH_INPUT = "오늘 날씨가 좋네요 그냥 인사"


def test_create_session_persists_and_surfaces_active_hypotheses_on_live_pg() -> None:
    """POST /v1/coach/sessions — 매칭 있으면 active_hypotheses 채워짐 + 실 PG에 행 영속.

    ① 제곱 분배 오류 입력 → 응답 active_hypotheses 비어있지 않음·DB misconception_hypothesis
       활성 행 영속(confidence∈(0,1]·evidence_count≥1·turns_since_evidence=0).
    ② 매칭 없는 입력 → active_hypotheses 빈 리스트·새 활성 행 없음.
    ③ 기존 응답 필드(misconceptions·dialogue_id·intervention) 보존(회귀 0).
    """
    if not asyncio.run(_pg_reachable()):
        pytest.skip("PostgreSQL 미도달 — 통합 테스트 건너뜀 (WHYMATH_DATABASE_URL 확인)")

    uid = uuid.uuid4()
    dialogue_ids: list[uuid.UUID] = []
    try:
        asyncio.run(_add_user(uid))
        token = create_access_token(uid, settings=_settings())
        auth = {"Authorization": f"Bearer {token}"}
        with _client() as client:
            # ① 매칭 유발 입력 → 가설 노출 + 영속.
            resp = client.post(
                "/v1/coach/sessions",
                headers=auth,
                json={"student_input": _SQUARE_DISTRIB_INPUT},
            )
            assert resp.status_code == 201, resp.text
            body = resp.json()
            dialogue_ids.append(uuid.UUID(body["dialogue_id"]))

            hyps = body["active_hypotheses"]
            assert hyps, "매칭이 있으면 active_hypotheses 비어있지 않음"
            # 가설=후보 — 구조(confidence·후보 필드) 검증.
            top = hyps[0]
            assert 0.0 < top["confidence"] <= 1.0
            assert top["evidence_count"] >= 1
            assert top["turns_since_evidence"] == 0  # 이번 턴 증거
            # 기존 응답 필드 보존(회귀 0).
            assert body["misconceptions"], "misconceptions도 채워짐(동형 노출)"
            assert body["intervention"]["pattern"] == "counterexample"

            # DB 영속 확인 — 활성 행 1개 이상·노출과 일치.
            rows = asyncio.run(_active_hypotheses(uid))
            assert rows, "misconception_hypothesis 활성 행 영속"
            assert rows[0][0] == top["misconception_id"]

            # ② 매칭 없는 입력 → 빈 리스트·새 활성 행 없음(매칭이 없으면 가설 미생성).
            uid2 = uuid.uuid4()
            asyncio.run(_add_user(uid2))
            token2 = create_access_token(uid2, settings=_settings())
            resp2 = client.post(
                "/v1/coach/sessions",
                headers={"Authorization": f"Bearer {token2}"},
                json={"student_input": _NO_MATCH_INPUT},
            )
            assert resp2.status_code == 201, resp2.text
            body2 = resp2.json()
            uid2_dialogue = uuid.UUID(body2["dialogue_id"])
            assert body2["active_hypotheses"] == []
            assert asyncio.run(_active_hypotheses(uid2)) == []
            # uid2의 dialogue를 *자신의* 정리로 넘긴다(자식 dialogue 먼저 → user_profile FK 충족).
            asyncio.run(_cleanup(uid2, [uid2_dialogue]))
    finally:
        asyncio.run(_cleanup(uid, dialogue_ids))


def test_append_turns_accumulates_and_reinforces_hypotheses_on_live_pg() -> None:
    """append_turns 재호출 시 가설 누적·강화(같은 오개념 증거 반복)·user 격리.

    같은 매칭을 2턴 연속 제공 → evidence_count 증가(강화·누적)·confidence 단조 비감소.
    다른 user는 격리(타 user 가설 행 미오염).
    """
    if not asyncio.run(_pg_reachable()):
        pytest.skip("PostgreSQL 미도달 — 통합 테스트 건너뜀 (WHYMATH_DATABASE_URL 확인)")

    uid = uuid.uuid4()
    other = uuid.uuid4()
    dialogue_ids: list[uuid.UUID] = []
    try:
        asyncio.run(_add_user(uid))
        asyncio.run(_add_user(other))
        token = create_access_token(uid, settings=_settings())
        auth = {"Authorization": f"Bearer {token}"}
        with _client() as client:
            # 턴1(create) — 가설 생성.
            create = client.post(
                "/v1/coach/sessions",
                headers=auth,
                json={"student_input": _SQUARE_DISTRIB_INPUT},
            )
            assert create.status_code == 201, create.text
            did = uuid.UUID(create.json()["dialogue_id"])
            dialogue_ids.append(did)
            after_t1 = create.json()["active_hypotheses"]
            assert after_t1
            mid = after_t1[0]["misconception_id"]
            conf1 = after_t1[0]["confidence"]
            count1 = after_t1[0]["evidence_count"]

            # 턴2(append) — 같은 증거 반복 → 강화·누적.
            append = client.post(
                f"/v1/coach/sessions/{did}/turns",
                headers=auth,
                json={"student_input": _SQUARE_DISTRIB_INPUT},
            )
            assert append.status_code == 201, append.text
            after_t2 = append.json()["active_hypotheses"]
            assert after_t2
            same = next(h for h in after_t2 if h["misconception_id"] == mid)
            # 강화 — evidence_count 증가·confidence 비감소(reinforce 단조).
            assert same["evidence_count"] == count1 + 1
            assert same["confidence"] >= conf1
            assert same["turns_since_evidence"] == 0

            # DB 영속(누적 후) 일치.
            rows = asyncio.run(_active_hypotheses(uid))
            db_same = next(r for r in rows if r[0] == mid)
            assert db_same[3] == count1 + 1

            # user 격리 — other user는 가설 행 0(타 user 오염 없음).
            assert asyncio.run(_active_hypotheses(other)) == []
    finally:
        asyncio.run(_cleanup(uid, dialogue_ids))
        asyncio.run(_cleanup(other, []))


def test_stateless_coach_omits_active_hypotheses() -> None:
    """stateless /v1/coach 응답엔 active_hypotheses 없음(DB 없음·불변).

    실 PG 불필요(stateless·DB 무접근) — 인증만 통과하면 됨. CoachResponse는 active_hypotheses
    필드를 갖지 않으므로 응답 JSON에 키가 부재한다.
    """
    uid = uuid.uuid4()
    settings = _settings()
    token = create_access_token(uid, settings=settings)
    app = create_app()
    app.dependency_overrides[get_settings] = _settings

    # 인증 의존성을 우회하기 위해 토큰 user를 실제 조회하지 않는 stateless 경로지만,
    # ConsentedUser 게이트는 user_profile 조회를 요구할 수 있어 PG 도달 시에만 본 검증을
    # 수행한다(미도달 시 skip — stateless 경로도 ConsentedUser 게이트는 공유).
    if not asyncio.run(_pg_reachable()):
        pytest.skip("PostgreSQL 미도달 — ConsentedUser 게이트 조회 불가로 건너뜀")
    try:
        asyncio.run(_add_user(uid))
        with TestClient(app) as client:
            resp = client.post(
                "/v1/coach",
                headers={"Authorization": f"Bearer {token}"},
                json={"student_input": _SQUARE_DISTRIB_INPUT},
            )
            assert resp.status_code == 200, resp.text
            body = resp.json()
            # stateless 응답에는 active_hypotheses 키 자체가 없다(CoachResponse 불변).
            assert "active_hypotheses" not in body
            # 기존 매칭 노출은 여전히 동작(불변).
            assert body["misconceptions"]
    finally:
        asyncio.run(_cleanup(uid, []))


# ──────────────────────────────────────────────────────────────────────────
# S3-27(원 S3-10) 완료를 풀이 제출에 통합 — 실 PG end-to-end(정답 도달 → 돌아보기 1턴 → 완료 적재)
# ──────────────────────────────────────────────────────────────────────────
def _problem_with_answer(pid: uuid.UUID, suffix: str, answer: str) -> Problem:
    return Problem.from_schema(
        ProblemSchema(
            problem_id=pid,
            source_type=SourceType.자체생성,
            curriculum_version=Curriculum.REVISION_2022,
            valid_from_year=2022,
            subject=Subject.공통,
            unit_codes=[f"U-{suffix}"],
            answer=answer,
        )
    )


async def _attempt_rows(uid: uuid.UUID) -> list[tuple[str, bool | None]]:
    """user의 problem_attempt를 (problem_id, is_correct)로 — 완료 적재·제외집합 검증용."""
    engine = create_async_engine(_settings().database_url)
    try:
        async with engine.connect() as conn:
            rows = await conn.execute(
                text(
                    "SELECT problem_id::text, is_correct FROM problem_attempt "
                    "WHERE user_id = :uid ORDER BY created_at"
                ),
                {"uid": str(uid)},
            )
            return [(str(r[0]), r[1]) for r in rows.all()]
    finally:
        await engine.dispose()


async def _next_problem_excluded_ids(uid: uuid.UUID) -> set[str]:
    """`recommend_next_problem`이 미시도 필터(NOT IN)로 쓰는 *제외집합*을 그대로 재현한다 —
    problem_attempt(user·is_correct 비-NULL)의 problem_id 집합(me.py predicate 동형)."""
    engine = create_async_engine(_settings().database_url)
    try:
        async with engine.connect() as conn:
            rows = await conn.execute(
                text(
                    "SELECT problem_id::text FROM problem_attempt "
                    "WHERE user_id = :uid AND is_correct IS NOT NULL"
                ),
                {"uid": str(uid)},
            )
            return {str(r[0]) for r in rows.all()}
    finally:
        await engine.dispose()


async def _dialogue_review_state(did: uuid.UUID) -> tuple[int | None, bool]:
    """dialogue의 (review_turns_remaining, attempt_id 존재여부) — 완료 상태 영속 검증용."""
    engine = create_async_engine(_settings().database_url)
    try:
        async with engine.connect() as conn:
            row = await conn.execute(
                text(
                    "SELECT review_turns_remaining, (attempt_id IS NOT NULL) "
                    "FROM dialogue WHERE dialogue_id = :did"
                ),
                {"did": str(did)},
            )
            r = row.one()
            return (None if r[0] is None else int(r[0]), bool(r[1]))
    finally:
        await engine.dispose()


async def _concept_mastery_count(uid: uuid.UUID, cid: uuid.UUID) -> int:
    engine = create_async_engine(_settings().database_url)
    try:
        async with engine.connect() as conn:
            row = await conn.execute(
                text(
                    "SELECT COUNT(*) FROM concept_mastery_history "
                    "WHERE user_id = :uid AND concept_id = :cid"
                ),
                {"uid": str(uid), "cid": str(cid)},
            )
            return int(row.scalar_one())
    finally:
        await engine.dispose()


async def _cleanup_completion(
    uid: uuid.UUID,
    *,
    problem_ids: list[uuid.UUID],
    concept_ids: list[uuid.UUID],
    dialogue_ids: list[uuid.UUID],
) -> None:
    engine = create_async_engine(_settings().database_url)
    dids = [str(d) for d in dialogue_ids]
    pids = [str(p) for p in problem_ids]
    cids = [str(c) for c in concept_ids]
    try:
        async with engine.begin() as conn:
            # FK 순서: dialogue_turn·attempt_event → dialogue(attempt_id SET NULL) →
            # problem_attempt → mastery(concept·skill) → problem_concept → problem → concept → user.
            await conn.execute(
                text("DELETE FROM dialogue_turn WHERE dialogue_id = ANY(:ids)"), {"ids": dids}
            )
            await conn.execute(
                text("DELETE FROM attempt_event WHERE user_id = :uid"), {"uid": str(uid)}
            )
            await conn.execute(
                text("DELETE FROM misconception_hypothesis WHERE user_id = :uid"),
                {"uid": str(uid)},
            )
            await conn.execute(
                text("DELETE FROM dialogue WHERE dialogue_id = ANY(:ids)"), {"ids": dids}
            )
            await conn.execute(
                text("DELETE FROM problem_attempt WHERE user_id = :uid"), {"uid": str(uid)}
            )
            await conn.execute(
                text("DELETE FROM concept_mastery_history WHERE user_id = :uid"),
                {"uid": str(uid)},
            )
            await conn.execute(
                text("DELETE FROM skill_mastery_history WHERE user_id = :uid"), {"uid": str(uid)}
            )
            await conn.execute(
                text("DELETE FROM problem_concept WHERE problem_id = ANY(:ids)"), {"ids": pids}
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


def test_completion_via_solution_full_loop_on_live_pg() -> None:
    """S3-27(원 S3-10) end-to-end — 완료는 *풀이 제출을 통해서만*, Polya 돌아보기 1턴 경유(실 PG).

    흐름:
      ① POST /v1/coach/sessions(problem_id·solution_steps 마지막=정답) → 정답 도달 감지 →
         awaiting_reflection=True·problem_complete=False·attempt 미적재(돌아보기 대기).
      ② POST .../turns(학생 근거 응답) → problem_complete=True·completed_attempt_id 실림 →
         ProblemAttempt(is_correct=True) 실 PG 적재·개념 숙달(concept_mastery_history) 전파.
      ③ 적재된 attempt가 next-problem 제외집합(NOT IN predicate)에 포함 → 재출제 안 됨(루프 닫힘).
      ④ dialogue.review_turns_remaining·attempt_id가 실제로 영속됨.
    """
    if not asyncio.run(_pg_reachable()):
        pytest.skip("PostgreSQL 미도달 — 통합 테스트 건너뜀")

    uid = uuid.uuid4()
    sfx = uid.hex[:8]
    cid = uuid.uuid4()
    pid = uuid.uuid4()
    uc = f"UC.test.{sfx}.cmpl"
    token = create_access_token(uid, settings=_settings())
    headers = {"Authorization": f"Bearer {token}"}
    dialogue_ids: list[uuid.UUID] = []
    try:
        asyncio.run(_add_user(uid))
        asyncio.run(_add_all(_concept_with_code(cid, uc, "일차방정식")))
        asyncio.run(_add_all(_problem_with_answer(pid, sfx, "3")))
        asyncio.run(_add_all(_problem_concept(pid, cid)))

        settings = _settings()
        app = create_app()
        app.dependency_overrides[get_settings] = lambda: settings
        with TestClient(app) as client:
            # ① 정답 도달 → 돌아보기 대기(완료 아님·attempt 미적재).
            r1 = client.post(
                "/v1/coach/sessions",
                json={
                    "student_input": "다 풀었어요",
                    "problem_id": str(pid),
                    "solution_steps": ["2*x = 6", "x = 3"],
                },
                headers=headers,
            )
            assert r1.status_code == 201, r1.text
            b1 = r1.json()
            did = uuid.UUID(b1["dialogue_id"])
            dialogue_ids.append(did)
            assert b1["awaiting_reflection"] is True
            assert b1["problem_complete"] is False
            assert b1["completed_attempt_id"] is None
            assert "설명해줄래" in b1["decision"]["prompt"]
            # 아직 attempt 미적재.
            assert asyncio.run(_attempt_rows(uid)) == []

            # ② 학생 근거 응답 → 완료 확정(attempt 적재·숙달 전파).
            r2 = client.post(
                f"/v1/coach/sessions/{did}/turns",
                json={"student_input": "양변을 2로 나눠서 x=3이 나왔어요"},
                headers=headers,
            )
            assert r2.status_code == 201, r2.text
            b2 = r2.json()
            assert b2["problem_complete"] is True
            assert b2["awaiting_reflection"] is False
            assert b2["completed_attempt_id"] is not None
            assert "다음 문제로 가보자" in b2["decision"]["prompt"]

            # ProblemAttempt(is_correct=True) 실 PG 적재.
            attempts = asyncio.run(_attempt_rows(uid))
            assert len(attempts) == 1
            assert attempts[0] == (str(pid), True)
            # ③ next-problem 제외집합에 완료 문항 포함(재출제 안 됨·루프 닫힘).
            assert str(pid) in asyncio.run(_next_problem_excluded_ids(uid))
            # 개념 숙달 전파(정답 → PRIMARY 개념 측정 1건 이상).
            assert asyncio.run(_concept_mastery_count(uid, cid)) >= 1
            # ④ dialogue 상태 영속 — 돌아보기 해제(0)·완료 attempt 링크(존재).
            review_remaining, attempt_linked = asyncio.run(_dialogue_review_state(did))
            assert review_remaining == 0
            assert attempt_linked is True
    finally:
        asyncio.run(
            _cleanup_completion(
                uid, problem_ids=[pid], concept_ids=[cid], dialogue_ids=dialogue_ids
            )
        )


def test_incorrect_final_step_no_completion_on_live_pg() -> None:
    """오답 마지막 단계 — 완료 무관·attempt 미적재·기존 코칭 그대로(회귀 불변, 실 PG)."""
    if not asyncio.run(_pg_reachable()):
        pytest.skip("PostgreSQL 미도달 — 통합 테스트 건너뜀")

    uid = uuid.uuid4()
    sfx = uid.hex[:8]
    pid = uuid.uuid4()
    token = create_access_token(uid, settings=_settings())
    headers = {"Authorization": f"Bearer {token}"}
    dialogue_ids: list[uuid.UUID] = []
    try:
        asyncio.run(_add_user(uid))
        asyncio.run(_add_all(_problem_with_answer(pid, sfx, "3")))

        settings = _settings()
        app = create_app()
        app.dependency_overrides[get_settings] = lambda: settings
        with TestClient(app) as client:
            resp = client.post(
                "/v1/coach/sessions",
                json={
                    "student_input": "이렇게 풀었어요",
                    "problem_id": str(pid),
                    "solution_steps": ["2*x = 6", "x = 4"],  # 마지막 x=4 ≠ 3(오답)
                },
                headers=headers,
            )
            assert resp.status_code == 201, resp.text
            body = resp.json()
            dialogue_ids.append(uuid.UUID(body["dialogue_id"]))
            assert body["problem_complete"] is False
            assert body["awaiting_reflection"] is False
            assert body["completed_attempt_id"] is None
            assert asyncio.run(_attempt_rows(uid)) == []
    finally:
        asyncio.run(
            _cleanup_completion(uid, problem_ids=[pid], concept_ids=[], dialogue_ids=dialogue_ids)
        )
