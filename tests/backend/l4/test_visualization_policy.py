"""L4 시각화 가능성 정책 단위테스트 — 4분류(Part 5-1) 값 → 그릴지/어떻게.

정책은 개념 노드가 아니라 시각화 4분류 *값*(`Visualizability | None`)을 입력받는다(노드 비내장·
Overlay 소유·05b). hermetic: 순수 함수. 정본 taxonomy(직접/동적/부분/추상) — 어느 것도 "불가"가
아니며, 리터럴 자동 시각화를 보류하는 것은 **추상**(StructureGraph 목표)뿐이다.
"""

from __future__ import annotations

import pytest
from whymath_backend.l4.visualization_policy import is_visualizable, prefers_static_visual
from whymath_backend.schema.enums import Visualizability


class TestIsVisualizable:
    @pytest.mark.parametrize(
        ("v", "expected"),
        [
            (Visualizability.직접, True),
            (Visualizability.동적, True),
            (Visualizability.부분, True),  # 부분 시각화(AnalogyVisual·예: 확률→수형도) — 억지 아님
            (
                Visualizability.추상,
                False,
            ),  # 리터럴 그래프는 오개념 — StructureGraph 목표(미구현→보류)
            (None, True),  # 미태깅 → 하위호환(기존 동작 유지)
        ],
    )
    def test_gate(self, v: Visualizability | None, expected: bool) -> None:
        assert is_visualizable(v) is expected


class TestPrefersStaticVisual:
    @pytest.mark.parametrize(
        ("v", "expected"),
        [
            (Visualizability.직접, True),  # 정적(Geometry2D) 충분 → 슬라이더 불필요
            (Visualizability.동적, False),  # 변화 과정이 인지 조건
            (Visualizability.부분, False),
            (Visualizability.추상, False),
            (None, False),  # 미태깅 → 기존 동작(슬라이더 허용)
        ],
    )
    def test_static_preference(self, v: Visualizability | None, expected: bool) -> None:
        assert prefers_static_visual(v) is expected
