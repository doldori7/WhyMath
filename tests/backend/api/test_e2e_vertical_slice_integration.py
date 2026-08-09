"""S1 E2E 수직 슬라이스 *통합 증명* 하니스 — 온보딩→진단→문제→풀이→코치→verify 관통(기본 SKIP).

로드맵 최대 병목(#3 "온보딩→진단→문제→풀이→코치→verify 루프가 끝까지 관통·실증된 적 없음")을
**실 PG**로 한 번에 관통해 증명하고, 라이브 LLM 키 투입 *전*의 회귀 앵커를 만든다. 핵심 원칙:

- **mock LLM(코치 LLM 0)** — `/v1/coach/sessions`는 `decision.prompt`를 AI 턴 content로 저장할
  뿐 실제 LLM을 호출하지 않는다(coach.py 모듈 docstring 계약). shadow 하네스·의미 매처·judge는
  *전부 기본 off*(config 기본값)라 실 임베딩 provider 의존이 없다 — 결정론 경로만 관통한다.
- **실 PG** — `get_session`은 오버라이드하지 않는다(라이브 PG). `get_settings`만 테스트 Settings로
  덮어 jwt 시크릿을 mint·검증에 공유한다(기존 통합테스트 패턴 답습). 인증은 실 JWT 발급.
- **성인 유저** — ConsentedUser(미성년 동의) 게이트를 우회하려 *성인* birth_year로 시딩한다
  (동의 불요). `parental_consent`·shadow 플래그는 켜지 않는다.

발명 금지: 엔드포인트가 *실제 반환하는 것만* assert한다. 코칭 텍스트는 정밀 검증하지 않고
status code + 핵심 필드 존재/타입/불변식(answer 비노출·verify 신호·턴 영속·is_minor 서버파생)에
집중한다. 불확실하면 관대하게(존재/타입) assert한다.

베이스: `test_coach_integration.py`의 실 PG 픽스처·시딩 헬퍼 패턴을 *동형 복제*한다(각 통합
테스트 모듈이 `_settings`·`_pg_reachable` 등을 독립 정의하는 선례 — 모듈 간 test import 이중
수집 회피). FK 안전 순서 정리는 try/finally로 보장한다.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from whymath_backend.app import create_app
from whymath_backend.config import Settings, get_settings
from whymath_backend.consent import current_year_kst, derive_is_minor
from whymath_backend.db.models.assessment import ConceptMasteryHistory
from whymath_backend.db.models.atom_node import AtomNode
from whymath_backend.db.models.concept import Concept, ConceptEdge, ProblemConcept
from whymath_backend.db.models.problem import Problem
from whymath_backend.db.models.user import UserProfile
from whymath_backend.schema.assessment import (
    ConceptMasteryHistory as ConceptMasteryHistorySchema,
)
from whymath_backend.schema.concept import Concept as ConceptSchema
from whymath_backend.schema.concept import ProblemConcept as ProblemConceptSchema
from whymath_backend.schema.enums import (
    ConceptLevel,
    ConceptRole,
    Curriculum,
    EdgeType,
    MajorCategory,
    Persona,
    ReviewStatus,
    SourceType,
    Subject,
)
from whymath_backend.schema.problem import Problem as ProblemSchema
from whymath_backend.schema.user import UserProfile as UserProfileSchema
from whymath_backend.security import create_access_token

pytestmark = pytest.mark.integration

_SECRET = "integration-jwt-secret-0123456789abcdef"

# 코치 응답에 정답이 새는지 검사할 sentinel — 시딩 Problem.answer에 심고, 코치 응답 어디에도
# 등장하지 않아야 한다(학생 대면 코칭은 정답을 미룬다·CLAUDE.md·test_coach.py answer 비노출 패턴).
_ANSWER_SENTINEL = "ANSWER_SENTINEL_DONOTLEAK"

# 단계 자가검산 유발 시퀀스 — 분배법칙 오류 전이(2*(x+3) ≠ 2*x+3)라 verify_step이 incorrect로
# 판정한다(대수 비동치·SymPy 결정론). first_incorrect_index=0·has_incorrect=True를 낳는다.
_BAD_STEPS = ["2*(x+3)", "2*x+3"]
# 텍스트 레벨 거짓 등식 — arithmetic_error를 확정적으로 켜 solution_coaching 노출을 보장한다
# (단계 신호와 OR 결합·둘 다 verify 신호이므로 관통 증명이 견고해진다).
_FALSE_ARITHMETIC = "2 + 3 = 6 이므로 답은 6"


def _settings() -> Settings:
    """테스트 Settings — jwt 시크릿만 고정. database_url은 WHYMATH_DATABASE_URL 환경변수 소싱."""
    return Settings(jwt_secret_key=SecretStr(_SECRET))


async def _pg_reachable() -> bool:
    """실 PG 도달 가능 여부 — 미도달이면 통합 테스트를 skip한다(WHYMATH_DATABASE_URL 확인)."""
    engine = create_async_engine(_settings().database_url)
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
    finally:
        await engine.dispose()


async def _add_adult_user(uid: uuid.UUID, *, birth_year: int) -> None:
    """성인 유저 시딩 — is_minor=False로 ConsentedUser 게이트를 통과(동의 불요·미성년 회피).

    birth_year는 성인 연나이가 되도록 호출자가 넘긴다(예: 2000 → 2026 기준 연나이 26).
    is_minor는 시딩 시 False로 두되, 이후 온보딩 PATCH가 birth_year에서 *서버 파생*으로 덮어쓴다
    (derive_is_minor 단일 진실 — 이 관통이 그 파생을 실증한다).
    """
    engine = create_async_engine(_settings().database_url)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            session.add(
                UserProfile.from_schema(
                    UserProfileSchema(
                        user_id=uid,
                        persona_primary=Persona.A_일반고고3,
                        birth_year=birth_year,
                        is_minor=False,
                    )
                )
            )
            await session.commit()
    finally:
        await engine.dispose()


async def _add_all(*objs: object) -> None:
    """ORM 객체들을 독립 엔진으로 한 트랜잭션에 적재한다(시딩 헬퍼)."""
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
    """원자 축 안전 메타 행(code PK) — S0-4d로 enrich가 `atom_node`로 전환됐다(ARCH-13 정렬).

    이 좌석은 원래 구 437 `concept_node`에 시드했다. 그 테이블은 런타임에서 읽히지 않으므로
    "막힌 선수(선수 복습 코칭 신호 유발)"라는 이 픽스처의 *선언된 의도*가 실제로는 달성되지
    않은 채 통과하고 있었다(축 울타리 이전에는 축이 어긋나도 행이 그냥 흘렀다). 원자 축으로
    시드해 관통 슬라이스가 실제로 선수 경로를 지나가게 한다.
    `test_me_integration.py`·`test_coach_integration.py`의 같은 이름 헬퍼와 동형.
    """
    return AtomNode(
        code=uc,
        name_ko=name_ko,
        level="세부개념",
        subject_area=domain,
        review_status=review_status,
    )


def _prereq_edge(from_id: uuid.UUID, to_id: uuid.UUID, strength: float) -> ConceptEdge:
    """선수 엣지 — from(선수)이 to(후행)의 선수(PREREQUISITE)."""
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


def _problem_with_answer(pid: uuid.UUID, suffix: str) -> Problem:
    """자체생성 문제 — answer에 sentinel을 심는다(코치 응답 정답 비노출 검사용).

    source_type=자체생성은 본문 보유 금지 불변식({평가원,EBS,교과서}) 대상이 아니라 answer를
    가질 수 있다. difficulty_overall을 채워 next-problem(CAT) 후보가 될 수 있게 한다.
    """
    return Problem.from_schema(
        ProblemSchema(
            problem_id=pid,
            source_type=SourceType.자체생성,
            # PB-03 — 기본 CAT SQL도 review_status=approved만 후보(축②)라 필요.
            review_status=ReviewStatus.approved,
            curriculum_version=Curriculum.REVISION_2022,
            valid_from_year=2022,
            subject=Subject.공통,
            unit_codes=[f"U-{suffix}"],
            difficulty_overall=3.0,
            answer=_ANSWER_SENTINEL,
        )
    )


def _problem_concept(pid: uuid.UUID, cid: uuid.UUID) -> ProblemConcept:
    return ProblemConcept.from_schema(
        ProblemConceptSchema(problem_id=pid, concept_id=cid, role=ConceptRole.PRIMARY)
    )


async def _cleanup(
    uid: uuid.UUID,
    *,
    problem_ids: list[uuid.UUID],
    concept_ids: list[uuid.UUID],
    uc_ids: list[str],
    dialogue_ids: list[uuid.UUID],
) -> None:
    """FK 안전 순서 정리 — 자식부터 부모로:
    dialogue_turn→attempt_event→misconception_hypothesis→dialogue→problem_concept→
    concept_edge→concept_mastery_history→concept_node→problem→concept→user_profile.
    """
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
                text("DELETE FROM attempt_event WHERE user_id = :uid"),
                {"uid": str(uid)},
            )
            await conn.execute(
                text("DELETE FROM misconception_hypothesis WHERE user_id = :uid"),
                {"uid": str(uid)},
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


def _client() -> TestClient:
    """실 PG 클라이언트 — get_settings만 오버라이드(jwt 공유)·get_session은 라이브 PG."""
    app = create_app()
    app.dependency_overrides[get_settings] = _settings
    return TestClient(app)


def test_full_loop_onboarding_to_verify_on_live_pg() -> None:
    """온보딩→진단→문제→풀이+코치→다턴→3-tier verify 전 구간을 실 PG로 한 번에 관통 증명.

    각 단계는 status code + 핵심 필드 존재/타입/불변식만 검증한다(코칭 텍스트 비정밀 assert).
    불변식: is_minor 서버파생·answer 비노출·verify 신호(코치↔독립 verify 정합)·턴 영속.
    """
    if not asyncio.run(_pg_reachable()):
        pytest.skip("PostgreSQL 미도달 — 통합 테스트 건너뜀 (WHYMATH_DATABASE_URL 확인)")

    uid = uuid.uuid4()
    sfx = uid.hex[:8]
    # 개념 그래프 — 문제 개념 C(후행)와 그 막힌 선수 P(선수 복습 코칭 신호 유발).
    uc_c = f"UC.e2e.{sfx}.concept"
    uc_p = f"UC.e2e.{sfx}.prereq"
    c_main, c_prereq = uuid.uuid4(), uuid.uuid4()
    pid = uuid.uuid4()
    t1 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    dialogue_ids: list[uuid.UUID] = []
    birth_year = 2000  # 성인(2026 기준 연나이 26 > 14) → is_minor 서버파생 False 기대.

    try:
        # ── 시딩: 성인 유저 + 문제·개념·ProblemConcept·선수 엣지·mastery ─────────────
        asyncio.run(_add_adult_user(uid, birth_year=birth_year))
        asyncio.run(
            _add_all(
                _concept_with_code(c_main, uc_c, "이차함수"),  # 문제 개념(후행·PRIMARY)
                _concept_with_code(c_prereq, uc_p, "일차함수"),  # 막힌 선수
            )
        )
        asyncio.run(_add_all(_node_meta(uc_p, "일차함수", "[중]함수", "reviewed")))
        asyncio.run(_add_all(_problem_with_answer(pid, sfx)))
        asyncio.run(_add_all(_problem_concept(pid, c_main)))
        # 선수 엣지(P는 C의 선수·to==c_main·from==c_prereq) + 선수 약점 mastery(막힘).
        asyncio.run(_add_all(_prereq_edge(c_prereq, c_main, 0.9)))
        asyncio.run(_add_all(_mastery_row(uid, c_prereq, t1, 0.2)))

        token = create_access_token(uid, settings=_settings())
        auth = {"Authorization": f"Bearer {token}"}
        with _client() as client:
            # ── 1) 온보딩: GET /v1/users/me로 ETag 획득 → PATCH로 프로필 채움 ──────────
            # (프로필 GET/PATCH는 users 라우터 `/v1/users/me` — _SELF_EDITABLE 화이트리스트.)
            me0 = client.get("/v1/users/me", headers=auth)
            assert me0.status_code == 200, me0.text
            etag = me0.headers["ETag"]

            patched = client.patch(
                "/v1/users/me",
                headers={**auth, "If-Match": etag},
                # 자유 dict 요청 — target_grade(1~9)·birth_year·target_major_category
                # (전부 _SELF_EDITABLE). track_type은 화이트리스트에 없어 major_category로 표현.
                json={
                    "target_grade": 2,
                    "birth_year": birth_year,
                    "target_major_category": MajorCategory.이공계.value,
                },
            )
            assert patched.status_code == 200, patched.text
            body = patched.json()
            # 입력이 반영됐는지(화이트리스트 필드).
            assert body["target_grade"] == 2
            assert body["target_major_category"] == MajorCategory.이공계.value
            # is_minor는 *서버 파생*(입력 미신뢰)임을 실증 — birth_year에서 파생한 기대값과 일치.
            expected_is_minor = derive_is_minor(
                birth_year,
                current_year=current_year_kst(),
                threshold=_settings().minor_consent_age,
            )
            assert body["is_minor"] == expected_is_minor  # 성인이므로 False 기대.
            # PII(해시)는 응답에서 제외(response_model_exclude).
            assert "email_hash" not in body

            # ── 2) 진단: next-problem(CAT) + diagnosis/concepts ───────────────────────
            nxt = client.get("/v1/me/next-problem", headers=auth)
            assert nxt.status_code == 200, nxt.text
            nbody = nxt.json()
            # CAT 응답 형태 — problem_id(추천 없으면 None 가능)·theta·measurement_sufficient.
            assert "problem_id" in nbody
            assert isinstance(nbody["theta"], (int, float))
            assert isinstance(nbody["measurement_sufficient"], bool)

            diag = client.get("/v1/me/diagnosis/concepts", headers=auth)
            assert diag.status_code == 200, diag.text
            dlist = diag.json()
            assert isinstance(dlist, list)
            # 진단 목록 형태(coaching_focus 후보) — 항목이 있으면 개념·L4 코칭 필드를 갖는다.
            for item in dlist:
                assert "concept_id" in item
                assert "coaching" in item

            # ── 3) 문제 제시: GET /v1/problems/{pid} → 문제 스키마 ────────────────────
            prob = client.get(f"/v1/problems/{pid}", headers=auth)
            assert prob.status_code == 200, prob.text
            assert prob.json()["problem_id"] == str(pid)

            # ── 4) 풀이+코치: POST /v1/coach/sessions (오답 유발 풀이·단계 시퀀스) ──────
            create = client.post(
                "/v1/coach/sessions",
                headers=auth,
                json={
                    "student_input": "이 문제 이렇게 풀었는데 확인해줘",
                    "student_solution": _FALSE_ARITHMETIC,  # 거짓 등식 → arithmetic_error 확정
                    "problem_id": str(pid),
                    "solution_steps": _BAD_STEPS,  # 분배 오류 전이 → 단계 verify incorrect
                    "solution_step_types": ["계산"],  # 전이 1개(=len(steps)-1)·대수 검증 유지
                    "coaching_focus": "verify",
                },
            )
            assert create.status_code == 201, create.text
            cbody = create.json()
            did = uuid.UUID(cbody["dialogue_id"])
            dialogue_ids.append(did)

            # dialogue_id 존재·active_hypotheses는 리스트 형태(후보·낙인 아님).
            assert isinstance(cbody["active_hypotheses"], list)
            # verify 신호가 실렸다 — solution_coaching.solution_verification(단계 검증 집계).
            sol = cbody["solution_coaching"]
            assert sol is not None, "거짓 등식+오답 단계 → solution_coaching 노출"
            sv = sol["solution_verification"]
            assert sv is not None, "solution_steps 제공 → solution_verification 채워짐"
            assert sv["has_incorrect"] is True
            assert isinstance(sv["first_incorrect_index"], int)
            # WH-1 턴 인덱스(생성=1).
            assert cbody["wh1_turn_index"] == 1

            # 불변식: answer 비노출 — sentinel이 코치 응답 본문(텍스트·JSON) 어디에도 없음.
            assert _ANSWER_SENTINEL not in create.text
            assert _ANSWER_SENTINEL not in json.dumps(cbody, ensure_ascii=False)

            # ── 5) WH-1 다턴: 2턴 추가 → 턴 인덱스 증가·가설 리스트·턴 영속 ─────────────
            prev_turn_index = cbody["wh1_turn_index"]
            for _ in range(2):
                turn = client.post(
                    f"/v1/coach/sessions/{did}/turns",
                    headers=auth,
                    json={"student_input": "여기서부터 잘 모르겠어"},
                )
                assert turn.status_code == 201, turn.text
                tbody = turn.json()
                assert isinstance(tbody["active_hypotheses"], list)
                # wh1_turn_index는 교환마다 증가(누적 카운터·§2.2).
                assert tbody["wh1_turn_index"] > prev_turn_index
                prev_turn_index = tbody["wh1_turn_index"]

            # GET 세션 → 턴 영속(생성 2턴 + append 2회×2턴 = 6턴).
            got = client.get(f"/v1/coach/sessions/{did}", headers=auth)
            assert got.status_code == 200, got.text
            gbody = got.json()
            assert gbody["dialogue"]["dialogue_id"] == str(did)
            assert len(gbody["turns"]) == 6

            # ── 6) 3-tier verify: 독립 엔드포인트 POST /v1/verify-solution ────────────
            # 코치 응답 내 verify 신호와 *독립* verify가 정합함을 관통 증명(같은 오답 시퀀스).
            vresp = client.post(
                "/v1/verify-solution",
                headers=auth,
                json={"steps": _BAD_STEPS, "step_types": ["계산"]},
            )
            assert vresp.status_code == 200, vresp.text
            vbody = vresp.json()
            assert vbody["has_incorrect"] is True
            assert vbody["n_incorrect"] >= 1
            assert isinstance(vbody["first_incorrect_index"], int)
            # 정합: 코치가 실은 first_incorrect_index와 독립 verify가 동일 위치를 가리킨다.
            assert vbody["first_incorrect_index"] == sv["first_incorrect_index"]
    finally:
        # ── 7) FK 안전 순서 정리 ─────────────────────────────────────────────────────
        asyncio.run(
            _cleanup(
                uid,
                problem_ids=[pid],
                concept_ids=[c_main, c_prereq],
                uc_ids=[uc_c, uc_p],
                dialogue_ids=dialogue_ids,
            )
        )
