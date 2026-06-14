"""Schema v1.0 시각화 선언적 명세 모델 (Pydantic) — 슬라이스 90.

설계 정본: `docs/architecture/05_interaction.md` §5.2(선언적 시각화 `Visualization` 엔티티).
PRD는 시각화를 *영상 파일이 아니라* **선언적 JSON 명세**로 정의한다 — 렌더 파라미터·데이터·
축·상호작용 규칙을 담은 구조로, 용량이 작고 버전 관리가 쉬우며 학생이 파라미터를 조작해
*능동 탐구*하고 라벨·캡션 텍스트만 갈아끼워 다국어를 지원한다(05 §5.2).

7계층 경계(05 §5.2·CLAUDE.md): 명세의 *생성·검증*은 L3(콘텐츠 생성·검증) 책임, L5(④ 국소
비상구 — three.js·Desmos·Plotly WebView)는 받은 명세를 *렌더·조작 처리*만 한다. 이 모델은
슬라이스 89 "표현≠의미" 원칙의 구현체 — 시각화는 화면 픽셀이 아니라 코어의 구조(JSON)다.

범위(슬라이스 90·사용자 결정): 순수 Pydantic *명세 계약*만. `spec`은 자유 JSON(`dict`)
— 05 §5.2가 타입별 필드를 박지 않았고, 타입별 typed 모델·Problem 임베딩·ORM/마이그레이션·
CRUD API·L3 생성 메서드는 후속 슬라이스(슬라이스 87 enum→88 매핑·배선 패턴 답습).

컨벤션(`concept.py`·`problem.py` 답습):
  - `ConfigDict(extra="forbid", use_enum_values=True, str_strip_whitespace=True)`.
  - `UUID PK` → `uuid.UUID = Field(default_factory=uuid4)`.
  - 불변식은 `@model_validator(mode="after")`(슬라이스 1 `ProblemRelation._no_self_relation` 패턴).
"""

from __future__ import annotations

import uuid
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from whymath_backend.schema.enums import VisualizationType

# ──────────────────────────────────────────────────────────────────────────
# 타입별 spec 계약 (S1 — 자유 JSON → 검증 가능 계약) — docs/architecture/05a §8 S1
# ──────────────────────────────────────────────────────────────────────────
# 설계 원칙(05a §3·§8): 각 VisualizationType의 spec을 *typed 모델*로 검증한다.
#   - 모든 필드 Optional(default None) — 빈 spec({})도 유효(골격만 생성·점층 충전).
#   - extra="allow" — *additive 계약*: 알려진 필드만 타입 검증, 미지 필드는 허용한다.
#     (보수적·false reject 0 — CLAUDE.md 정확성. closed[forbid]·required 강제는 L3
#      생성이 스키마를 타깃하는 S3로 의도적 연기 — 지금 닫으면 기존 자유 JSON 명세를
#      거짓 거부한다. 예: 기존 테스트의 {"model": ...}은 미지 필드라 허용돼야 한다.)
#   - 이 모델들은 Visualization._validate_typed_spec *게이트*로만 쓴다(spec dict 미교체).


class Graph2dParam(BaseModel):
    """interactive_graph_2d 슬라이더 파라미터 — 학생이 조작하는 변수의 이름·범위·기본값."""

    model_config = ConfigDict(extra="allow", str_strip_whitespace=True)

    name: str | None = Field(default=None, description="파라미터 이름(예: 'a')")
    min: float | None = Field(default=None, description="슬라이더 최솟값")
    max: float | None = Field(default=None, description="슬라이더 최댓값")
    step: float | None = Field(default=None, description="슬라이더 증분")
    default: float | None = Field(default=None, description="초기값")


class Graph2dSpec(BaseModel):
    """interactive_graph_2d spec — 2D 함수·관계 그래프(D3/Plotly/Desmos).

    명시 필드(함수식·정의역·슬라이더 파라미터)만 타입 검증하고, 미지 필드(예: 'model')는
    extra="allow"로 허용한다(기존 자유 JSON 명세 호환).
    """

    model_config = ConfigDict(extra="allow", str_strip_whitespace=True)

    function: str | None = Field(default=None, description="함수·관계식(예: 'a*x**2+b*x+c')")
    domain: list[float] | None = Field(default=None, description="정의역 범위(예: [-3, 3])")
    parameters: list[Graph2dParam] | None = Field(
        default=None, description="학생 조작 슬라이더 파라미터 목록"
    )


class Surface3dSpec(BaseModel):
    """interactive_surface_3d spec — 3D 곡면·입체(three.js·회전/단면 조작)."""

    model_config = ConfigDict(extra="allow", str_strip_whitespace=True)

    surface: str | None = Field(default=None, description="곡면 식(예: 'z = x**2 + y**2')")
    rotatable: bool | None = Field(default=None, description="회전 조작 가능 여부")


class SimulationSpec(BaseModel):
    """simulation_probabilistic spec — 확률 시뮬레이션(D3/Plotly·시행 반복·누적)."""

    model_config = ConfigDict(extra="allow", str_strip_whitespace=True)

    experiment: str | None = Field(default=None, description="시행 정의(예: '동전 던지기')")
    trials: int | None = Field(default=None, ge=1, description="시행 횟수(≥1)")


class AnimationSpec(BaseModel):
    """animation_prerendered spec — 미리 렌더된 애니메이션(Manim·조작 불가)."""

    model_config = ConfigDict(extra="allow", str_strip_whitespace=True)

    asset_id: str | None = Field(default=None, description="사전 렌더 자산 식별자")
    duration_seconds: float | None = Field(default=None, gt=0, description="재생 길이(초·>0)")


# VisualizationType → spec 모델 매핑. 4종 enum 전부를 덮는다(완전성은 테스트가 단언).
_SPEC_MODEL_BY_TYPE: dict[VisualizationType, type[BaseModel]] = {
    VisualizationType.interactive_graph_2d: Graph2dSpec,
    VisualizationType.interactive_surface_3d: Surface3dSpec,
    VisualizationType.simulation_probabilistic: SimulationSpec,
    VisualizationType.animation_prerendered: AnimationSpec,
}


def validate_spec_for_type(vtype: VisualizationType, spec: dict[str, Any]) -> BaseModel:
    """spec dict를 해당 VisualizationType의 typed 모델로 검증해 반환(타입 위반→ValidationError).

    검증 게이트 헬퍼 — 호출자는 반환 모델 자체보다 *검증 통과/위반*에 의존한다(05a §3·§8).
    """
    return _SPEC_MODEL_BY_TYPE[vtype].model_validate(spec)


# ──────────────────────────────────────────────────────────────────────────
# 핵심: Visualization (05 §5.2 선언적 시각화 명세 — 렌더 기술 + 선언적 spec)
# ──────────────────────────────────────────────────────────────────────────
class Visualization(BaseModel):
    """선언적 시각화 명세 — 05 §5.2 `Visualization` 엔티티.

    `type`이 렌더 도구를 결정하고(L5 ④ 비상구가 선택), `spec`이 그 도구가 그릴 선언적
    파라미터·데이터·축·상호작용 규칙을 담는다(v1은 타입별 자유 JSON). `caption`은 다국어
    텍스트 레이어, `interactive`는 학생 파라미터 조작 가능 여부다.

    불변식(`@model_validator(mode="after")`): `animation_prerendered`는 *조작 불가*
    (05 §5.2)이므로 `interactive`는 반드시 False여야 한다. 나머지 3종은 능동 탐구가 핵심이라
    조작 가능(기본 True)이되 정적 표시를 위해 False도 허용한다.
    """

    model_config = ConfigDict(
        # 추가 필드 금지 — Pydantic 모델이 명세의 단일 진실
        extra="forbid",
        # 직렬화 시 enum 값을 그대로(type="interactive_graph_2d" 등)
        use_enum_values=True,
        # 문자열 양끝 공백 제거
        str_strip_whitespace=True,
    )

    # ===== 기본 식별 =====
    visualization_id: uuid.UUID = Field(
        default_factory=uuid4,
        description="시각화 명세 PK (UUID)",
    )

    # ===== 렌더 기술·선언적 명세 =====
    type: VisualizationType = Field(
        ...,
        description="렌더 기술 4종 — L5 ④ 비상구가 이 값으로 렌더 도구 선택(05 §5.2)",
    )
    spec: dict[str, Any] = Field(
        default_factory=dict,
        description="선언적 렌더 명세 — 파라미터·데이터·축·상호작용 규칙(타입별 구조·v1 자유 JSON)",
    )
    caption: str | None = Field(
        default=None,
        description="다국어 캡션·라벨 텍스트(05 §5.2 — 명세에 언어 레이어만 교체)",
    )
    interactive: bool = Field(
        default=True,
        description="학생 파라미터 조작 가능 여부(animation_prerendered는 False — 05 §5.2)",
    )

    @model_validator(mode="after")
    def _prerendered_not_interactive(self) -> Visualization:
        """05 §5.2 — animation_prerendered는 '조작 불가'이므로 interactive=False 강제."""
        if self.type == VisualizationType.animation_prerendered and self.interactive:
            raise ValueError(
                "animation_prerendered는 interactive=False여야 한다 (05 §5.2 '조작 불가')"
            )
        return self

    @model_validator(mode="after")
    def _validate_typed_spec(self) -> Visualization:
        """05a §8 S1 — spec을 type별 typed 모델로 검증(자유 JSON → 검증 가능 계약).

        spec은 dict로 보존하고(직렬화·JSONB 저장 불변) 여기서는 *게이트*로만 검증한다 —
        타입 위반(예: graph_2d function=123)은 ValidationError로 거부된다. use_enum_values=True라
        self.type이 문자열일 수 있어 VisualizationType으로 정규화 후 조회한다.
        """
        vtype = VisualizationType(self.type)
        try:
            _SPEC_MODEL_BY_TYPE[vtype].model_validate(self.spec)
        except ValidationError as exc:
            raise ValueError(f"{vtype.value} spec 위반: {exc}") from exc
        return self
