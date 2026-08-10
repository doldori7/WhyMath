"""L4 시각화 가능성 정책 — 시각화 4분류(Part 5)로 "그릴지/어떻게"를 결정.

구축 플레이북 Part 5 법칙 — "개념을 4분류(직접/동적/부분/추상)로 판별하나, 전부 똑같이 그리려
하나?" — 을 코드 게이트로 못박는다. 시각화 *생성*은 L3, *렌더*는 L5지만, "이 개념을 애초에
그려야 하는가"는 **교수학 결정(L4)**이므로 정책이 여기에 산다(설계 정본 05b).

입력은 개념의 시각화 4분류 값(`Visualizability | None`) — 개념 노드가 아니라 시각화 계층 Overlay
(`concept_visualization`·`l1/concept_visualization`)가 소유하고, 호출자(L5)가 조회해 넘긴다(노드
비내장·ADR 계층분리). None=미태깅(하위호환·기존 시각화 동작 유지). 순수 함수만(부작용 0·hermetic).
"""

from __future__ import annotations

from collections.abc import Sequence

from whymath_backend.schema.enums import Visualizability, VisualizationStyle

# 리터럴 자동 시각화를 *보류*하는 분류 — **추상**(군론·위상·논리: 리터럴 그래프가 거짓 구체성으로
# 오개념 유발·목표 렌더는 StructureGraph/메타포지 리터럴 그래프 아님). 이 경우 소크라테스·단계로
# 폴백한다(05b·CLAUDE.md 정확성). 직접·동적·**부분**(AnalogyVisual)·None(미태깅)은 시각화
# 대상 — 부분은 일부 의미를 담는 표상(확률→수형도)이 있어 억지 아님(Part 5-1).
_ABSTAIN: frozenset[Visualizability] = frozenset({Visualizability.추상})


def is_visualizable(visualizability: Visualizability | None) -> bool:
    """이 개념에 자동 시각화 명세를 생성해도 되는가.

    추상 → False(리터럴 보류·StructureGraph 목표). 직접·동적·부분·None(미태깅) → True. None을 True로
    두는 것은 *하위호환*(미태깅은 기존 동작 유지) — 태깅이 진행되면 추상만 걸러진다(부분은 시각화).
    """
    return visualizability is None or visualizability not in _ABSTAIN


# 렌더 좌석 보유 양식 — data/visual_style_contract.json의 status=="seated" 집합과 정확히
# 일치해야 한다(JSON↔Python 이중 진실원 drift 방지 —
# tests/backend/schema/test_visual_style_render_contract.py 가 교차검증). 이 모듈은 순수
# 함수·부작용 0 원칙(hermetic)이라 계약 파일을 직접 읽지 않고 리터럴
# 상수로 박는다(VIZ-04). 근거(양식↔실제 렌더 경로): 함수그래프·단위원(관계식)·부등식영역(영역
# 색칠)은 `interactive_graph_2d`(웹 `classify()`가 각각 function/implicit/inequality로 분류해
# 그린다) · 분포곡선은 PDF가 x의 함수라 `interactive_graph_2d` · 확률시뮬레이션은
# `simulation_probabilistic` · 수직선은 VIZ-07이 신설한 1D 렌더 경로(`Graph2dSpec.number_line`
# → 웹 `drawNumberLine` — classify() 6형 밖 전용 경로) · 접선도함수는 기존 접선 렌더
# (`Graph2dSpec.tangent_point` → 웹 `showTangent`/`drawTangent` — 소비 경로 소스 실측 확정,
# VIZ-07)에 좌석. 나머지 9종(입체도형·평면도형·벡터도·점화도·수형도·넓이모델·통계차트·산점도·
# 상자그림)은 표현할 렌더 타입이 없다(unseated).
_SEATED_STYLES: frozenset[VisualizationStyle] = frozenset(
    {
        VisualizationStyle.함수그래프,
        VisualizationStyle.단위원,
        VisualizationStyle.부등식영역,
        VisualizationStyle.분포곡선,
        VisualizationStyle.확률시뮬레이션,
        VisualizationStyle.수직선,
        VisualizationStyle.접선도함수,
    }
)


def has_render_seat(styles: Sequence[VisualizationStyle]) -> bool:
    """권장 시각화 양식 중 하나라도 렌더 좌석이 있으면 True.

    좌석이 0이면(권장 양식 전건이 unseated) 억지 시각화를 보류한다 — 렌더 타입이 없는 양식을
    LLM이 4종 중 하나로 강제로 골라 개념과 무관한 그림을 렌더하는 것을 막는다(VIZ-04·
    `docs/architecture/visualization_module_gap_review.md` §7.1 G1). `is_visualizable`(4분류
    게이트)과 **병렬**이며 대체하지 않는다 — 둘 다 통과해야 시각화가 생성된다.
    """
    return any(s in _SEATED_STYLES for s in styles)


def prefers_static_visual(visualizability: Visualizability | None) -> bool:
    """정적 그림 한 장으로 충분한가(직접). True면 슬라이더(param_control)를 덧붙이지 않는다.

    `직접`은 조작 없이 즉시 인지되는 개념이라 슬라이더가 불필요하다(05b). `동적`·None은 매개변수
    조작이 인지 조건이거나(동적) 미상(None·하위호환)이라 슬라이더를 허용한다.
    """
    return visualizability == Visualizability.직접
