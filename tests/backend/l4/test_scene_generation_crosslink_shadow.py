"""LearningScene 생성기 — 노출 표면 crosswalk shadow 배선 단위테스트.

`generate_learning_scene`이 *실제 프로브로 나가는* kebab-id마다 `observe_crosslink_shadow_async`를
부르는지(노출 가중 coverage·canary go/no-go 분모)·기본 `off`에선 부르지 않는지·관측이 scene을 바꾸지
않는지(노출 불변)·실호출이 DB 없이도 scene을 안 깨는지(never-break)를 검증한다.

shadow 함수 자체(coverage·never-break·프라이버시)는 `test_misconception_crosslink_shadow.py`가 이미
검증한다 — 본 파일은 *생성기 배선 계약*만 본다(`test_scene_generation.py`의 fake DI 패턴 답습).

설계 정본: math_dsl_remediation_design.md §1.3-3 · math_dsl_risk_register.md §4(Q10-⑥).
안전(CLAUDE.md): 측정 전용·비노출(반환 None)·기본 off·never-break(관측이 학생 경험을 안 깬다).
"""

from __future__ import annotations

import pytest

from whymath_backend.l3.interfaces import InMemoryCache, RecordingTraceSink
from whymath_backend.l3.models import RoutingDecision, RoutingRequest
from whymath_backend.l4 import scene_generation
from whymath_backend.l4.learning_scene import (
    LearningScene,
    MisconceptionProbeElement,
    SceneLearnerContext,
)
from whymath_backend.l4.misconception.catalog import CATALOG_BY_ID
from whymath_backend.l4.scene_generation import generate_learning_scene
from whymath_backend.schema.concept import Concept
from whymath_backend.schema.enums import CognitiveType, ConceptLevel

_VALID_MC_ID = next(iter(CATALOG_BY_ID))
_VALID_MC_ID2 = list(CATALOG_BY_ID)[1]


class _FakeProvider:
    """가짜 LLMProvider(호출 없어도 되지만 구조 충족) — 시각화 양식 없으면 미호출."""

    async def generate(self, prompt: str, system: str, decision: RoutingDecision) -> str:
        return '{"type": "interactive_graph_2d", "spec": {"function": "x**2"}, "interactive": true}'


def _req() -> RoutingRequest:
    return RoutingRequest(
        task_type="generate",
        difficulty="medium",
        requires_reasoning=True,
        student_subscription="free",
    )


def _concept() -> Concept:
    """시각화 양식 없는 개념(LLM 미호출·프로브 경로에 집중)."""
    return Concept(
        code="ALG-QUAD-DEF",
        name_ko="이차함수의 그래프",
        level=ConceptLevel.세부개념,
        cognitive_type=[CognitiveType.DEFINITION],
    )


async def _generate(learner_context: SceneLearnerContext | None) -> LearningScene:
    return await generate_learning_scene(
        _concept(),
        "고1",
        _req(),
        provider=_FakeProvider(),
        cache=InMemoryCache(),
        trace=RecordingTraceSink(),
        learner_context=learner_context,
        answer_deferral_max_level=4,
    )


def _probe_ids(scene: LearningScene) -> list[str]:
    return [
        el.misconception_id for el in scene.elements if isinstance(el, MisconceptionProbeElement)
    ]


class _Settings:
    """`misconception_crosslink_mode`만 갖는 최소 설정 더블(config 전체 구성 회피)."""

    def __init__(self, mode: str) -> None:
        self.misconception_crosslink_mode = mode


class _Spy:
    """`observe_crosslink_shadow_async` 스파이 — 호출된 kebab-id를 순서대로 수집."""

    def __init__(self) -> None:
        self.seen: list[str] = []

    async def __call__(self, misconception_id: str, **kwargs: object) -> None:
        self.seen.append(misconception_id)


def _ctx() -> SceneLearnerContext:
    """두 개의 카탈로그 가설(둘 다 프로브가 되는 신뢰도)."""
    return SceneLearnerContext(
        active_hypothesis_ids=[_VALID_MC_ID, _VALID_MC_ID2],
        active_hypothesis_confidences={_VALID_MC_ID: 0.9, _VALID_MC_ID2: 0.6},
    )


# ── ① mode=shadow → 노출된 프로브마다 관측 1회 ────────────────────────────────
class TestShadowObservesExposedProbes:
    @pytest.mark.asyncio
    async def test_observes_each_probe_kebab_id(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """mode!='off'이면 *실제 프로브로 나가는* kebab-id마다 shadow 관측이 불린다."""
        spy = _Spy()
        monkeypatch.setattr(scene_generation, "get_settings", lambda: _Settings("shadow"))
        monkeypatch.setattr(scene_generation, "observe_crosslink_shadow_async", spy)

        scene = await _generate(_ctx())

        # 관측 대상 = 실제 노출 프로브 집합과 정확히 일치(노출 가중·순서 무관 비교).
        assert sorted(spy.seen) == sorted(_probe_ids(scene))
        assert set(spy.seen) == {_VALID_MC_ID, _VALID_MC_ID2}

    @pytest.mark.asyncio
    async def test_no_probes_no_observation(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """프로브가 하나도 없으면(학습자 컨텍스트 없음) 관측 0(노출 표면이 비어있음)."""
        spy = _Spy()
        monkeypatch.setattr(scene_generation, "get_settings", lambda: _Settings("shadow"))
        monkeypatch.setattr(scene_generation, "observe_crosslink_shadow_async", spy)

        scene = await _generate(None)

        assert _probe_ids(scene) == []
        assert spy.seen == []


# ── ② mode=off(기본) → 관측 0(현행 비트동일·crosslink 조회 0) ─────────────────
class TestOffModeNoObservation:
    @pytest.mark.asyncio
    async def test_off_mode_skips_observation(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """기본 off에선 프로브가 있어도 shadow 관측을 부르지 않는다(opt-in·비트동일)."""
        spy = _Spy()
        monkeypatch.setattr(scene_generation, "get_settings", lambda: _Settings("off"))
        monkeypatch.setattr(scene_generation, "observe_crosslink_shadow_async", spy)

        scene = await _generate(_ctx())

        assert len(_probe_ids(scene)) == 2  # 프로브는 정상 생성
        assert spy.seen == []  # 관측만 스킵


# ── ③ 노출 불변 — 관측 on/off가 scene(프로브 kebab-id)을 바꾸지 않는다 ─────────
class TestExposureInvariant:
    @pytest.mark.asyncio
    async def test_probe_ids_invariant_to_mode(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """같은 컨텍스트에서 mode off/shadow가 프로브 집합을 동일하게 둔다(kebab-id 노출 불변)."""
        spy = _Spy()
        monkeypatch.setattr(scene_generation, "observe_crosslink_shadow_async", spy)

        monkeypatch.setattr(scene_generation, "get_settings", lambda: _Settings("off"))
        off_scene = await _generate(_ctx())
        monkeypatch.setattr(scene_generation, "get_settings", lambda: _Settings("shadow"))
        shadow_scene = await _generate(_ctx())

        assert _probe_ids(off_scene) == _probe_ids(shadow_scene)
        assert set(_probe_ids(shadow_scene)) == {_VALID_MC_ID, _VALID_MC_ID2}


# ── ④ never-break — 실 shadow 함수(DB 없음)여도 scene 정상 반환 ───────────────
class TestNeverBreakEndToEnd:
    @pytest.mark.asyncio
    async def test_real_shadow_call_does_not_break_scene(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """실 `observe_crosslink_shadow_async`(monkeypatch 없음)로 mode=shadow — 테스트 환경엔
        crosslink 테이블·DB가 없어 resolver가 내부에서 실패하지만, shadow는 never-break라 삼키고
        scene은 프로브 그대로 정상 반환된다(관측이 학생 경험을 안 깬다)."""
        monkeypatch.setattr(scene_generation, "get_settings", lambda: _Settings("shadow"))

        scene = await _generate(_ctx())

        assert isinstance(scene, LearningScene)
        assert set(_probe_ids(scene)) == {_VALID_MC_ID, _VALID_MC_ID2}
