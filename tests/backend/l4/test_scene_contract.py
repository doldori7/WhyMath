"""scene DSL 서버↔클라 계약 게이트 — 백엔드 측(MOB-14).

`docs/architecture/dsl_integration_gap_review.md` §2-④ 실측: scene 응답의 서버↔Dart 계약 게이트가
0건이라(`scene_models.dart`를 참조하는 백엔드·크로스 테스트 0건), Dart `json_serializable`이 미지
키를 조용히 무시해 필드 드리프트 4건이 런타임 파손 없이 CI를 통과했다. 이 파일은 그 게이트의
백엔드 절반이다 — 공유 계약 `data/scene_contract.json`의 필드셋이 코어 Pydantic 모델
(`Visualization`·`SceneLearnerContext`·`LearningScene`·`SceneElement` 8종)의 `model_fields`와
*정확히* 일치하는지 고정한다(모바일 절반 = `src/mobile/test/scene_contract_test.dart` — 둘이 합쳐
"코어 필드 ↔ 클라 파서 필드" drift를 막는다·`test_render_contract.py`·`test_notation_contract.py`
선례).

`SceneElement` 판별 유니온 8종 멤버는 하드코딩하지 않고 `typing.get_args`로 union type에서
직접 뽑는다 — 새 kind가 유니온에 추가·제거될 때 이 테스트 목록이 따로 표류하지 않는다
(`test_scene_dsl_layer_governance.py`의 하드코딩 화이트리스트와 달리, 여기선 *유니온 멤버 자체*를
계약 파일과 대조하는 것이 목적이라 이중 진실원을 만들지 않는 것이 더 중요하다).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, get_args

import pytest
from pydantic import BaseModel

from whymath_backend.l4.learning_scene import LearningScene, SceneElement, SceneLearnerContext
from whymath_backend.schema.visualization import Visualization

# tests/backend/l4/ → parents[3] = 레포 루트(test_render_contract.py와 동일 기준 산정 방식).
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_FIXTURE = _PROJECT_ROOT / "data" / "scene_contract.json"


def _load_contract() -> dict[str, Any]:
    if not _FIXTURE.exists():  # pragma: no cover - fixture는 레포에 동봉
        pytest.skip(f"scene 계약 fixture 없음: {_FIXTURE}")
    loaded: dict[str, Any] = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    return loaded


_CONTRACT = _load_contract()
_MODELS: dict[str, list[str]] = _CONTRACT["models"]
_SCENE_ELEMENTS: dict[str, list[str]] = _CONTRACT["scene_elements"]

# 계약 최상위 모델 이름 → 실제 Pydantic 클래스(단일 좌석 — 이름 문자열은 fixture와 매칭용).
_MODEL_CLASSES: dict[str, type[BaseModel]] = {
    "Visualization": Visualization,
    "SceneLearnerContext": SceneLearnerContext,
    "LearningScene": LearningScene,
}

# SceneElement 판별 유니온의 실제 멤버 클래스 — kind 기본값으로 계약의 scene_elements 키와 매칭.
_ELEMENT_MEMBERS: tuple[type[BaseModel], ...] = get_args(get_args(SceneElement)[0])
_ELEMENT_CLASS_BY_KIND: dict[str, type[BaseModel]] = {
    cls.model_fields["kind"].default: cls for cls in _ELEMENT_MEMBERS
}


@pytest.mark.parametrize("model_name", sorted(_MODELS))
def test_top_level_model_field_set_matches_contract(model_name: str) -> None:
    """(models) 계약의 필드 목록 == 실제 Pydantic 모델의 model_fields(누락·잉여 0)."""
    cls = _MODEL_CLASSES[model_name]
    assert set(cls.model_fields) == set(_MODELS[model_name]), (
        f"{model_name} 필드 드리프트: 모델={sorted(cls.model_fields)} "
        f"!= 계약={sorted(_MODELS[model_name])}"
    )


def test_contract_covers_exactly_the_scene_element_union() -> None:
    """(scene_elements 완전성) 계약의 kind 키 집합 == SceneElement 판별 유니온의 kind 집합.

    유니온에 새 kind가 추가·제거될 때 계약 파일 갱신을 강제한다(누락 kind는 클라가 영원히
    모르는 필드셋, 잉여 kind는 죽은 계약 항목).
    """
    assert set(_SCENE_ELEMENTS) == set(_ELEMENT_CLASS_BY_KIND), (
        f"scene_elements kind 표류: 계약={sorted(_SCENE_ELEMENTS)} "
        f"!= 유니온={sorted(_ELEMENT_CLASS_BY_KIND)}"
    )


@pytest.mark.parametrize("kind", sorted(_SCENE_ELEMENTS))
def test_scene_element_field_set_matches_contract(kind: str) -> None:
    """(scene_elements) 각 kind 변형의 필드셋 == 계약(누락·잉여 0) — 드리프트 4건 재발 방지 본체."""
    cls = _ELEMENT_CLASS_BY_KIND[kind]
    assert set(cls.model_fields) == set(_SCENE_ELEMENTS[kind]), (
        f"SceneElement[kind={kind}] 필드 드리프트: 모델={sorted(cls.model_fields)} "
        f"!= 계약={sorted(_SCENE_ELEMENTS[kind])}"
    )
