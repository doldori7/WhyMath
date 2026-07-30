"""VIZ-01 acceptance②·⑥·⑦ — 실 PG 관통 변별력 증명 (`WHYMATH_RUN_INTEGRATION`).

`docs/architecture/visualization_module_gap_review.md` §3 D1·D2 — 학생 경로
(`POST /v1/scenes/weak-concept`)의 시각화 블록은 `l4/scene_generation.py:279`가
`concept.recommended_visual_styles`(Overlay `concept_visual_style`)와
`is_visualizable(visualizability)`(Overlay `concept_visualization`)를 **AND**로 요구한다.

이 모듈은 그 게이트를 *실 PG + 실 앱(TestClient)*으로 직접 조작해 증명한다(로더 함수 자체의
멱등 upsert 단위테스트는 `l1/concept_visual_style`·`l1/concept_visualization` 기존 테스트가
이미 커버 — 여기는 "행이 있고 없고가 학생에게 실제로 보이는 응답을 바꾸는가"만 본다):

- ② 오버레이 행 0(적재 전 상태 재현) → 응답에 `VisualizationElement`(kind="visualization") 부재
- ⑥ `concept_visual_style` 행 삽입(적재 후 상태) → 같은 개념·같은 세션에서 `VisualizationElement`
  등장(적재 전/후가 *같은 값을 내면 위장* — CLAUDE.md 변별력 원칙)
- ⑦ 그 위에 `concept_visualization`을 "추상"으로 오태깅 → 게이트가 시각화를 *보류*(성공/실패가
  구분됨을 실측) → 오태깅 삭제(복원) → 시각화가 다시 등장(정상 동작 복귀 실측)

세 상태 전이를 한 테스트 함수 안에서 순서대로(①없음→②style만→③style+추상→④style만 복원)
실측한다 — S3-27 `TestMutationDetection` 패턴의 DB-상태 버전(monkeypatch 대신 INSERT/DELETE로
"오염→복원"을 실측).

fake LLM provider(`_FakeProvider`)로 시각화 spec 생성만 대체하고(비용·네트워크 0), 나머지는
`test_e2e_vertical_slice_integration.py`의 실 PG 시딩 패턴을 그대로 따른다.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from whymath_backend.api._rate_limit import reset_store
from whymath_backend.app import create_app
from whymath_backend.config import Settings, get_settings
from whymath_backend.db.models.assessment import ConceptMasteryHistory
from whymath_backend.db.models.concept import Concept
from whymath_backend.db.models.concept_visual_style import ConceptVisualStyle
from whymath_backend.db.models.concept_visualization import ConceptVisualization
from whymath_backend.db.models.user import UserProfile
from whymath_backend.l3.models import GenerationResult, RoutingDecision
from whymath_backend.schema.assessment import (
    ConceptMasteryHistory as ConceptMasteryHistorySchema,
)
from whymath_backend.schema.concept import Concept as ConceptSchema
from whymath_backend.schema.enums import ConceptLevel, Persona, Visualizability, VisualizationStyle
from whymath_backend.schema.user import UserProfile as UserProfileSchema
from whymath_backend.security import create_access_token

pytestmark = pytest.mark.integration

_SECRET = "viz01-integration-jwt-secret-0123456789ab"

# 프로덕션 검증 게이트가 실제로 통과시키는 최소 시각화 spec(test_scene_service._VALID_JSON 미러).
_VALID_VIZ_JSON = (
    '{"type": "interactive_graph_2d", "spec": {"function": "a*x**2", '
    '"parameters": [{"name": "a"}]}, "interactive": true}'
)


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


async def _add_all(*objs: object) -> None:
    engine = create_async_engine(_settings().database_url)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            session.add_all(list(objs))
            await session.commit()
    finally:
        await engine.dispose()


async def _delete_visualization_overlay_only(code: str) -> None:
    """`concept_visualization` 행만 지운다(`concept_visual_style`은 유지 — ④ 복원 시나리오 전용)."""
    engine = create_async_engine(_settings().database_url)
    try:
        async with engine.begin() as conn:
            await conn.execute(
                text("DELETE FROM concept_visualization WHERE code = :c"), {"c": code}
            )
    finally:
        await engine.dispose()


async def _cleanup(uid: uuid.UUID, *, concept_id: uuid.UUID, code: str) -> None:
    engine = create_async_engine(_settings().database_url)
    try:
        async with engine.begin() as conn:
            await conn.execute(
                text("DELETE FROM concept_visualization WHERE code = :c"), {"c": code}
            )
            await conn.execute(
                text("DELETE FROM concept_visual_style WHERE code = :c"), {"c": code}
            )
            await conn.execute(
                text("DELETE FROM concept_mastery_history WHERE user_id = :uid"), {"uid": str(uid)}
            )
            await conn.execute(
                text("DELETE FROM concept WHERE concept_id = :cid"), {"cid": str(concept_id)}
            )
            await conn.execute(
                text("DELETE FROM user_profile WHERE user_id = :uid"), {"uid": str(uid)}
            )
    finally:
        await engine.dispose()


class _FakeProvider:
    """실 LLM 미호출 — 시각화 spec 생성 호출 시 항상 유효 JSON을 반환(검증 게이트 통과용)."""

    def __init__(self) -> None:
        self.call_count = 0

    async def generate(
        self, prompt: str, system: str, decision: RoutingDecision
    ) -> GenerationResult:
        self.call_count += 1
        return GenerationResult(_VALID_VIZ_JSON)


def _client(*, provider: _FakeProvider) -> TestClient:
    app = create_app(provider=provider)
    app.dependency_overrides[get_settings] = _settings
    return TestClient(app)


def _has_visualization_element(scene_body: dict) -> bool:
    return any(el.get("kind") == "visualization" for el in scene_body["elements"])


class TestReachDiscrimination:
    def test_overlay_absent_then_style_then_abstain_then_restored(self) -> None:
        """②→⑥→⑦을 한 시퀀스로 실측 — 오버레이 부재→style 적재→추상 오태깅→복원."""
        if not asyncio.run(_pg_reachable()):
            pytest.skip("PostgreSQL 미도달 — 통합 테스트 건너뜀 (WHYMATH_DATABASE_URL 확인)")

        uid = uuid.uuid4()
        sfx = uid.hex[:10]
        code = f"VIZ01-TEST-{sfx}"
        cid = uuid.uuid4()
        birth_year = 2000  # 성인 — ConsentedUser 동의 게이트 우회.
        t1 = datetime(2026, 1, 1, tzinfo=timezone.utc)

        try:
            asyncio.run(
                _add_all(
                    UserProfile.from_schema(
                        UserProfileSchema(
                            user_id=uid,
                            persona_primary=Persona.A_일반고고3,
                            birth_year=birth_year,
                            is_minor=False,
                        )
                    )
                )
            )
            asyncio.run(
                _add_all(
                    Concept.from_schema(
                        ConceptSchema(
                            concept_id=cid,
                            code=code,
                            name_ko="VIZ01 판별용 임시 개념",
                            level=ConceptLevel.세부개념,
                        )
                    )
                )
            )
            # BKT mastery 1건 — compute_concept_diagnoses가 이 개념을 진단 후보로 뽑도록.
            asyncio.run(
                _add_all(
                    ConceptMasteryHistory.from_schema(
                        ConceptMasteryHistorySchema(
                            user_id=uid,
                            concept_id=cid,
                            measured_at=t1,
                            mastery=0.3,
                            sample_size=1,
                        )
                    )
                )
            )

            token = create_access_token(uid, settings=_settings())
            auth = {"Authorization": f"Bearer {token}"}

            # ── ① 오버레이 행 0(D1 적재 전 상태) — VisualizationElement 부재(acceptance②) ──
            provider1 = _FakeProvider()
            asyncio.run(reset_store())
            with _client(provider=provider1) as client:
                resp1 = client.post("/v1/scenes/weak-concept", headers=auth)
            assert resp1.status_code == 200, resp1.text
            body1 = resp1.json()
            assert body1["concept_id"] == code
            assert not _has_visualization_element(
                body1
            ), "오버레이 행이 없는데 시각화 요소가 생겼다 — D1 AND 게이트 회귀"
            # 오버레이가 비어 recommended_visual_styles가 falsy이므로 LLM(spec 생성)도 호출 안 됨.
            assert provider1.call_count == 0

            # ── ② concept_visual_style 행 삽입(적재 후) — VisualizationElement 등장(acceptance⑥) ──
            asyncio.run(
                _add_all(
                    ConceptVisualStyle(
                        code=code, recommended_styles=[VisualizationStyle.함수그래프]
                    )
                )
            )
            provider2 = _FakeProvider()
            asyncio.run(reset_store())
            with _client(provider=provider2) as client:
                resp2 = client.post("/v1/scenes/weak-concept", headers=auth)
            assert resp2.status_code == 200, resp2.text
            body2 = resp2.json()
            assert _has_visualization_element(body2), (
                "concept_visual_style 행이 있는데도 시각화 요소가 안 실렸다 — "
                "적재 전(①)과 같은 값이면 변별력이 없다(위장)"
            )
            assert provider2.call_count == 1  # 시각화 spec 생성 LLM 1회 호출됨(스타일 있을 때만)

            # ── ③ concept_visualization "추상" 오태깅(acceptance⑦ — 게이트가 실제로 보류하는가) ──
            asyncio.run(
                _add_all(ConceptVisualization(code=code, visualizability=Visualizability.추상))
            )
            provider3 = _FakeProvider()
            asyncio.run(reset_store())
            with _client(provider=provider3) as client:
                resp3 = client.post("/v1/scenes/weak-concept", headers=auth)
            assert resp3.status_code == 200, resp3.text
            body3 = resp3.json()
            assert not _has_visualization_element(
                body3
            ), "'추상' 오태깅에도 시각화 요소가 실렸다 — is_visualizable 게이트가 무력하다"
            assert provider3.call_count == 0  # 게이트에서 return — LLM 호출 자체가 생략됨

            # ── ④ 오태깅 삭제(복원) — 정상 동작(②와 동일)이 재현되는지(acceptance⑦ 복원 축) ──
            asyncio.run(_delete_visualization_overlay_only(code))
            provider4 = _FakeProvider()
            asyncio.run(reset_store())
            with _client(provider=provider4) as client:
                resp4 = client.post("/v1/scenes/weak-concept", headers=auth)
            assert resp4.status_code == 200, resp4.text
            body4 = resp4.json()
            assert _has_visualization_element(
                body4
            ), "'추상' 오태깅 복원 후에도 시각화가 안 돌아왔다 — 복원 실패"
            assert provider4.call_count == 1
        finally:
            asyncio.run(_cleanup(uid, concept_id=cid, code=code))
