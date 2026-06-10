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

from pydantic import BaseModel, ConfigDict, Field, model_validator

from whymath_backend.schema.enums import VisualizationType


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
