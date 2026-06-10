"""L3 시각화 *명세* 생성기 — 개념 → 선언적 Visualization (05 §5.2). 슬라이스 92.

7계층 경계: L3는 시각화 *명세*(구조·JSON)만 생성·검증한다. 실제 렌더(Manim·Desmos·
three.js)는 L5 ④ 국소 비상구의 책임이다(05 §5.2·CLAUDE.md "표현≠의미"·슬라이스 89).
03 문서의 옛 `generate_visualization()->bytes`(Manim 영상 반환)는 이 경계를 위반했다 —
본 모듈은 *bytes가 아니라 Visualization 명세*를 돌려주어 정합한다(슬라이스 90
`schema/visualization.py`).

흐름: 프롬프트 → `pipeline.generate`(라우터 경유 — CLAUDE.md "LLM은 항상 라우터 경유") →
원시 출력 → `parse_visualization_spec`(JSON 추출 → `Visualization` 검증 *게이트*) → 반환.
검증 안 된 명세는 절대 통과시키지 않는다(CLAUDE.md "LLM 응답을 검증 없이 제공 금지") —
`Visualization` 모델(구조 + 슬90 `animation_prerendered⟹조작불가` 불변식)이 그 게이트다.

범위(슬라이스 92): 라우터 경유 생성 + 파싱·검증 게이트. 프롬프트는 기능적 최소형(자유
JSON spec). 교수학적 프롬프트 정련(pedagogy-designer·Langfuse·A/B)·타입별 typed spec·
spec 내 함수식 SymPy 검증은 후속.
"""

from __future__ import annotations

import json
import re

from pydantic import ValidationError

from whymath_backend.l3.interfaces import CacheBackend, LLMProvider, TraceSink
from whymath_backend.l3.models import RoutingRequest
from whymath_backend.l3.pipeline import generate
from whymath_backend.schema.visualization import Visualization


class InvalidVisualizationSpecError(ValueError):
    """LLM 출력이 유효한 Visualization 명세가 아님 — 파싱 실패 또는 스키마 위반.

    검증 게이트가 *검증 안 된 명세*를 통과시키지 않기 위해 던진다(CLAUDE.md "LLM 응답을
    검증 없이 제공 금지"). 호출자는 재생성·사람 검수로 대응한다.
    """


# ```json ... ``` 또는 ``` ... ``` 코드펜스 추출(LLM이 흔히 감싸는 형태).
_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


def _extract_json_object(text: str) -> str:
    """원시 LLM 출력에서 JSON 객체 문자열을 추출(코드펜스·산문 둘러쌈 허용).

    ① ```json ... ``` 코드펜스가 있으면 그 안을 취하고, ② 첫 '{'~마지막 '}'를 JSON 객체
    후보로 잘라낸다. 객체 경계를 못 찾으면 `InvalidVisualizationSpecError`.
    """
    s = text.strip()
    fence = _FENCE_RE.search(s)
    if fence is not None:
        s = fence.group(1).strip()
    start = s.find("{")
    end = s.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise InvalidVisualizationSpecError("LLM 출력에서 JSON 객체를 찾지 못했다")
    return s[start : end + 1]


def parse_visualization_spec(text: str) -> Visualization:
    """LLM 원시 출력 → 검증된 `Visualization` 명세 (검증 게이트).

    코드펜스·산문을 벗기고 JSON 객체를 추출해 `Visualization`으로 검증한다. JSON 파싱
    실패·스키마 위반(예: `animation_prerendered`+`interactive=True`, 슬90 불변식)은 모두
    `InvalidVisualizationSpecError`로 거부한다 — *검증 통과한 명세만* 반환한다.
    """
    raw = _extract_json_object(text)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise InvalidVisualizationSpecError(f"JSON 파싱 실패: {exc}") from exc
    try:
        return Visualization.model_validate(data)
    except ValidationError as exc:
        raise InvalidVisualizationSpecError(f"Visualization 스키마 위반: {exc}") from exc


# 시스템 프롬프트 — 선언적 명세 JSON 하나만 출력(렌더 아님). 기능적 최소형(슬92 범위).
_SYSTEM_PROMPT = (
    "당신은 수학 학습 앱의 시각화 *명세* 생성기다. 개념을 가장 잘 드러내는 선언적 시각화 "
    "명세를 JSON 객체 하나로만 출력한다(렌더 이미지가 아니라 명세 — 렌더는 클라이언트가 "
    "한다). 설명·코드펜스 없이 아래 형태의 JSON 하나만 출력하라:\n"
    '{"type": "<interactive_graph_2d|interactive_surface_3d|simulation_probabilistic|'
    'animation_prerendered>", "spec": {렌더 파라미터·데이터·축·상호작용 규칙}, '
    '"caption": "<한 줄 캡션>", "interactive": <true|false>}\n'
    "규칙: type은 위 4종 중 하나의 영문 값. animation_prerendered는 조작 불가이므로 "
    "interactive=false. spec은 해당 type에 맞는 자유 JSON(예: interactive_graph_2d → "
    "함수식·정의역·슬라이더 파라미터)."
)


def _user_prompt(concept: str, level: str) -> str:
    """개념·수준 → 사용자 프롬프트(시각화 명세 1개 요청)."""
    return (
        f"개념: {concept}\n"
        f"대상 수준: {level}\n"
        "이 개념을 가장 잘 드러내는 시각화 명세 JSON 하나를 출력하라."
    )


async def generate_visualization_spec(
    concept: str,
    level: str,
    req: RoutingRequest,
    *,
    provider: LLMProvider,
    cache: CacheBackend,
    trace: TraceSink,
) -> Visualization:
    """개념·수준 → 선언적 `Visualization` 명세(05 §5.2)를 라우터 경유로 생성·검증.

    렌더가 아니라 *명세*만 만든다(렌더는 L5 ④ 비상구·7계층 경계). `pipeline.generate`로
    라우터를 거쳐 LLM을 호출하고(CLAUDE.md "LLM은 항상 라우터 경유"), 원시 출력을
    `parse_visualization_spec`로 검증해 반환한다 — 검증 실패는 `InvalidVisualizationSpecError`.

    Args:
        concept: 시각화할 수학 개념(예: "삼각함수의 주기성").
        level: 대상 수준(예: "고등학교 2학년").
        req: 라우팅 입력 신호(task_type="generate" 권장). 라우팅·예산·SLA·동기 여부는
            호출자 책임 — QUALITY 비동기로 라우팅되면 `generate`가 큐 미주입 시
            `QualityQueueUnavailableError`를 던진다(이 함수는 동기 경로 전제).
        provider/cache/trace: `pipeline.generate` DI(라우터 경유 생성·캐시·관측).

    Returns:
        검증된 `Visualization` 명세.

    Raises:
        InvalidVisualizationSpecError: LLM 출력이 유효한 Visualization이 아님.
    """
    result = await generate(
        req,
        _user_prompt(concept, level),
        _SYSTEM_PROMPT,
        provider=provider,
        cache=cache,
        trace=trace,
    )
    return parse_visualization_spec(result.text)
