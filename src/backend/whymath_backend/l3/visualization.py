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

VIZ-02(렌더 계약 파생): LLM에 제시하는 type 목록은 **하드코딩이 아니라
`data/render_contract.json`(invariant ⑩ 렌더 선택 단일 진실원)에서 파생**한다 —
`web_adapter`가 있는(= 렌더 경로가 실재하는) 타입만 제시한다. 이전엔 프롬프트가 4종을
문자열 리터럴로 제시해 `animation_prerendered`(계약상 `web_adapter: null`·Manim 구현 0건)를
생성기가 고를 수 있었고, 그 명세는 어디서도 렌더되지 않았다(웹은 조용히 미렌더·Flutter는
caption 카드로 강등 — LLM 비용 낭비 + caption이 예고한 시각화 불이행). 스키마·enum·계약의
`animation_prerendered` 좌석은 **존치**한다(`S4-03`·Manim 배선 시 계약 한 줄로 복귀) —
죽이는 것은 *생성 경로*뿐이다. 게이트: `tests/backend/schema/test_render_contract.py`.

7계층: 계약 파일을 *읽는* 것은 L5(렌더러 구현)에 대한 의존이 아니다. L3가 소비하는 것은
"이 type에 렌더 경로가 있는가"라는 **술어 하나**이며 렌더러 식별자·구현체를 코드에 담지
않는다(Renderer=Plugin 유지). 배포 자산(`data/`)을 L3가 읽는 선례: `l3/render/
assessment_bank.py`·`l3/notation_coverage.py`. import 방향은 그대로 L3→schema다.
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Sequence
from functools import lru_cache
from pathlib import Path

from pydantic import ValidationError

from whymath_backend.l3.interfaces import CacheBackend, LLMProvider, TraceSink
from whymath_backend.l3.models import RoutingRequest
from whymath_backend.l3.pipeline import generate
from whymath_backend.l3.prompt_assets import fill, prompt_text
from whymath_backend.schema.concept import Concept as ConceptSchema
from whymath_backend.schema.visualization import Visualization

logger = logging.getLogger("whymath.l3.visualization")


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


# ──────────────────────────────────────────────────────────────────────
# 렌더 계약 파생 — "생성기가 제시하는 타입 ⊆ 렌더 경로가 있는 타입" (VIZ-02)
# ──────────────────────────────────────────────────────────────────────
# 계약 파일 경로 — 레포 루트 기준 고정(cwd 무관). 이 파일은
# src/backend/whymath_backend/l3/visualization.py라 parents[4]가 레포 루트다
# (`l3/render/assessment_bank.py`가 같은 관례로 코퍼스 산출물을 앵커한다).
_REPO_ROOT = Path(__file__).resolve().parents[4]
RENDER_CONTRACT_PATH = _REPO_ROOT / "data" / "render_contract.json"

# 계약 최상위 키 — 이 로더와 계약 파일의 유일한 결합면(웹 vitest·백엔드 계약 테스트와 공유).
RENDER_CONTRACT_RENDERERS_KEY = "renderers"
# 렌더 경로 유무 판정 필드. null이면 "그 type을 그릴 수 있는 어댑터가 없다"는 계약의 선언이다
# (Flutter도 WebView로 같은 웹 어댑터에 태우므로 이 필드가 두 클라 공통의 렌더 가능성 술어다).
RENDER_CONTRACT_ADAPTER_KEY = "web_adapter"

# type별 spec 예시 — LLM이 채울 키 힌트. 키 집합은 *계약상 렌더 가능한 타입 집합과 정확히
# 일치*해야 한다: 렌더 불가 타입의 예시가 남으면 dead code이고, 렌더 가능한데 예시가 없으면
# LLM이 그 type의 spec을 못 채운다. 이 등식은 게이트가 동결한다
# (tests/backend/schema/test_render_contract.py).
_SPEC_EXAMPLES: dict[str, str] = {
    # 관계식·부등식 두 예시는 PR #703 스쿼시에서 유실된 VIZ-04 예시의 복원이다(VIZ-07에서
    # 재착륙). 수직선 예시는 VIZ-07 신설 — 값 문자열만 확장하며 키 집합은 불변이다(키 집합 ==
    # 렌더 가능 타입 등식을 test_render_contract.py가 동결).
    "interactive_graph_2d": (
        '{"function":"a*x**2+b*x+c", "domain":[-3,3], '
        '"parameters":[{"name":"a","min":-5,"max":5,"step":0.1,"default":1}]}'
        ' / 관계식·음함수(원 등) 허용: {"function":"x**2 + y**2 = 1", "domain":[-2,2]}'
        ' / 부등식 영역: {"function":"y > x**2", "domain":[-3,3]}'
        " / 수직선(1D 축 — 정수·부등식 해·구간): "
        '{"number_line":{"points":[{"value":2}],'
        '"intervals":[{"start":2,"end":null,"start_open":false}]},"domain":[-5,5]}'
    ),
    "interactive_surface_3d": '{"surface":"z = x**2 + y**2", "rotatable":true}',
    "simulation_probabilistic": (
        '{"experiment":"동전 던지기", "trials":200, '
        '"outcomes":[{"label":"앞면","weight":1},{"label":"뒷면","weight":1}]}'
    ),
}


@lru_cache(maxsize=1)
def renderable_visualization_types() -> tuple[str, ...]:
    """렌더 경로가 실재하는 `VisualizationType` 값들 — 계약 파생·1회 로드·인메모리 캐시.

    매 LLM 호출마다 파일을 읽지 않는다(`lru_cache` — `l3/render/assessment_bank.py` 선례).
    테스트는 `reset_render_contract_cache()`로 무효화한다.

    실패 처리(침묵 실패 금지 — 예외 *타입명*을 로그에 싣는다. 경로 외 값은 싣지 않는다):
        계약 파일 부재·파손처럼 **계약을 읽을 수 없는** 경우에는 `_SPEC_EXAMPLES`의 키로
        강등한다. 이 키 집합은 게이트가 계약의 렌더 가능 집합과 동일함을 CI에서 동결하므로,
        강등값은 *정상 배포에서 계약이 주는 답과 같다* — 강등 방향이 "생성 전면 붕괴"가 아니라
        "직전 정상 동작 유지"다. 계약이 **정상인데 렌더 가능 0건**인 경우는 강등하지 않는다
        (그건 계약이 명시적으로 "그릴 수 있는 것이 없다"고 말한 상태이므로, 예시 키로 폴백하면
        계약 위반이다) — 빈 튜플을 그대로 돌려주고 `_system_prompt()`가 생성을 막는다.
    """
    try:
        payload = json.loads(RENDER_CONTRACT_PATH.read_text(encoding="utf-8"))
        renderers = payload[RENDER_CONTRACT_RENDERERS_KEY]
        if not isinstance(renderers, dict) or not renderers:
            raise TypeError(
                f"{RENDER_CONTRACT_RENDERERS_KEY}가 비어있지 않은 dict가 아님: "
                f"{type(renderers).__name__}"
            )
    except (OSError, ValueError, TypeError, KeyError) as exc:
        logger.warning(
            "렌더 계약 로드 실패 — 코드 측 예시 키 집합으로 강등(생성 타입 집합 유지). "
            "error_type=%s path=%s",
            type(exc).__name__,
            RENDER_CONTRACT_PATH,
        )
        return tuple(sorted(_SPEC_EXAMPLES))
    return tuple(
        sorted(
            name
            for name, entry in renderers.items()
            if isinstance(entry, dict) and entry.get(RENDER_CONTRACT_ADAPTER_KEY)
        )
    )


def _build_system_prompt(types: Sequence[str]) -> str:
    """렌더 가능 타입 목록 → 시스템 프롬프트(순수 함수 — 전역 상태 없음·정본 캐시 경유).

    선언적 명세 JSON 하나만 출력시킨다(렌더 아님). 기능적 최소형(슬92 범위)이며, 목록 밖
    타입을 제시하지 않는 것이 이 함수의 유일한 불변식이다.

    OPS-16: *고정 문안*은 `docs/prompts/l3_visualization.md` 정본에서 인용하고, *타입 목록*은
    VIZ-02의 렌더 계약 파생을 그대로 유지한다 — 문면의 정본은 문서, 렌더 가능성의 정본은
    `data/render_contract.json`으로 갈라 두 진실 원천이 겹치지 않게 한다. spec 예시 줄은
    산문이 아니라 *데이터*(`_SPEC_EXAMPLES`)라 계약 파생 목록으로 여기서 조립한다.
    """
    lines = [
        fill(
            prompt_text("l3.visualization.system"),
            TYPE_UNION="|".join(types),
            TYPE_COUNT=str(len(types)),
        )
    ]
    lines.extend(f"  - {name}: {_SPEC_EXAMPLES[name]}" for name in types if name in _SPEC_EXAMPLES)
    if "simulation_probabilistic" in types:
        lines.append(prompt_text("l3.visualization.system_probability_note"))
    return "\n".join(lines)


@lru_cache(maxsize=1)
def _system_prompt() -> str:
    """프로덕션 시스템 프롬프트 — 계약에서 파생한 타입 목록으로 1회 조립·캐시.

    렌더 가능 타입이 0건이면 프롬프트를 만들지 않고 `RuntimeError`로 막는다. 그 상태에서
    생성하면 *무조건* 렌더 불가 명세가 나오므로(LLM 비용 100% 낭비 + caption 불이행),
    조용히 진행하는 것보다 요청을 실패시키는 쪽이 안전하다.
    """
    types = renderable_visualization_types()
    if not types:
        logger.error(
            "렌더 계약에 렌더 가능한 시각화 타입이 0건 — 명세 생성을 차단한다. path=%s",
            RENDER_CONTRACT_PATH,
        )
        raise RuntimeError(
            "렌더 가능한 시각화 타입이 없다(render_contract.json의 web_adapter 전건 null) — "
            "생성해도 렌더될 수 없으므로 시각화 명세 생성을 중단한다."
        )
    return _build_system_prompt(types)


def reset_render_contract_cache() -> None:
    """렌더 계약·시스템 프롬프트 캐시 무효화 — 테스트 격리용 seam.

    프로덕션은 계약이 프로세스 수명 동안 고정이라 호출할 일이 없다
    (`l3/render/assessment_bank.py::reset_assessment_bank_cache` 동형). 프롬프트 *문면*의
    정본 캐시는 별도다 — 정본 파일을 바꾼 테스트는 `prompt_assets.reset_prompt_asset_cache()`도
    함께 호출해야 여기 캐시된 조립 결과가 갱신된다(OPS-16).
    """
    renderable_visualization_types.cache_clear()
    _system_prompt.cache_clear()


def _user_prompt(concept: str, level: str, recommended_styles: Sequence[str] | None = None) -> str:
    """개념·수준(+권장 양식 힌트) → 사용자 프롬프트(시각화 명세 1개 요청·정본 인용)."""
    lines = [fill(prompt_text("l3.visualization.user_head"), CONCEPT=concept, LEVEL=level)]
    if recommended_styles:
        lines.append(
            fill(prompt_text("l3.visualization.user_styles"), STYLES=", ".join(recommended_styles))
        )
    lines.append(prompt_text("l3.visualization.user_tail"))
    return "\n".join(lines)


def build_visualization_prompt(
    concept: str,
    level: str,
    recommended_styles: Sequence[str] | None = None,
) -> tuple[str, str]:
    """개념·수준(+권장 양식) → (시스템, 사용자) 프롬프트 쌍 — *프로덕션 프롬프트 공개 접근자*.

    `generate_visualization_spec`이 LLM에 넘기는 *바로 그* 프롬프트를 반환한다. 라이브 평가
    하니스(`viz_eval`·`test_visualization_live`)가 프롬프트를 따로 베끼지 않고 이 함수를 통해
    *동일한* 프롬프트로 모델을 호출하게 하기 위함이다 — 평가와 프로덕션의 프롬프트 드리프트 0.

    Returns:
        (system_prompt, user_prompt) — 렌더 계약 파생 시스템 프롬프트(`_system_prompt()`)와
        `_user_prompt(...)` 결과.

    Raises:
        RuntimeError: 렌더 계약에 렌더 가능한 타입이 0건(생성해도 렌더 불가 — 생성 차단).
    """
    return _system_prompt(), _user_prompt(concept, level, recommended_styles)


async def generate_visualization_spec(
    concept: str,
    level: str,
    req: RoutingRequest,
    *,
    provider: LLMProvider,
    cache: CacheBackend,
    trace: TraceSink,
    recommended_styles: Sequence[str] | None = None,
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
        recommended_styles: 개념 권장 시각화 양식(슬88 `recommended_visual_styles`) — 주어지면
            프롬프트에 *참고 힌트*로 주입(예: 단위원·수형도). None/빈 배열이면 미주입.

    Returns:
        검증된 `Visualization` 명세.

    Raises:
        InvalidVisualizationSpecError: LLM 출력이 유효한 Visualization이 아님.
    """
    system_prompt, user_prompt = build_visualization_prompt(concept, level, recommended_styles)
    result = await generate(
        req,
        user_prompt,
        system_prompt,
        provider=provider,
        cache=cache,
        trace=trace,
    )
    return parse_visualization_spec(result.text)


async def visualization_spec_for_concept(
    concept: ConceptSchema,
    level: str,
    req: RoutingRequest,
    *,
    provider: LLMProvider,
    cache: CacheBackend,
    trace: TraceSink,
) -> Visualization:
    """`Concept`(슬88) → 그 `recommended_visual_styles`를 힌트로 주입해 시각화 명세 생성.

    슬88(개념↔교수 양식 매핑)과 슬92(명세 생성)를 잇는 다리 — 개념의 `name_ko`를 대상으로
    `recommended_visual_styles`(예: 삼각함수→단위원·확률→수형도)를 프롬프트 *참고 힌트*로
    넘겨 `generate_visualization_spec`에 위임한다(빈 양식이면 힌트 없이 동작). 진단된 약점
    개념을 시각화할 때 호출자가 Concept를 넘기면 권장 양식이 자동 반영된다.
    """
    return await generate_visualization_spec(
        concept.name_ko,
        level,
        req,
        provider=provider,
        cache=cache,
        trace=trace,
        recommended_styles=concept.recommended_visual_styles,
    )
