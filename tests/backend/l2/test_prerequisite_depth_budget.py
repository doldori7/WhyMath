"""선수 traversal 깊이 예산 단일 출처 가드 — `MAX_PREREQUISITE_DEPTH` (Q10-⑧·동작 불변 동결).

math_dsl_risk_register.md Q10-⑧(traversal 예산). 선수 traversal 깊이 상한은 L2
`MAX_PREREQUISITE_DEPTH` 단일 출처에서 나와야 하며, API 경계(`api/me.py` MaxDepth)가 그 상한을
*공유*한다(매직 넘버 중복 제거). 이 가드는 (a) 상한 값 동결과 (b) API 경계가 단일 출처를
참조함을 함께 못 박아, 한쪽만 바뀌어 경계가 어긋나는 drift를 차단한다.

⚠️ 이 예산은 *그래프 traversal 깊이*다 — "LLM 컨텍스트 예산"(max_nodes·max_tokens)이 아니다
(소비처 부재·premature). hermetic(타입 메타데이터 introspection만·DB·앱 기동 불요).
"""

from __future__ import annotations

from typing import get_args

import annotated_types

from whymath_backend.api.me import MaxDepth
from whymath_backend.l2.prerequisite_recommendation import MAX_PREREQUISITE_DEPTH


def _bound(annotated_type: object, kind: type) -> int | None:
    """`Annotated[int, Query(...)]`의 Query 메타에서 ge/le 제약(annotated_types) 값을 추출."""
    query = get_args(annotated_type)[1]
    for meta in getattr(query, "metadata", []):
        if isinstance(meta, kind):
            # Ge.ge / Le.le — 클래스명 소문자 속성으로 값 보유.
            return getattr(meta, kind.__name__.lower())
    return None


def test_max_prerequisite_depth_frozen() -> None:
    """상한 값 동결 — 변경 시 의도적으로 이 테스트를 갱신하게 강제(비용·노이즈 예산)."""
    assert MAX_PREREQUISITE_DEPTH == 5


def test_api_maxdepth_shares_single_source() -> None:
    """`api/me.py` MaxDepth의 상한(le)이 L2 단일 출처와 동일 — 매직 넘버 중복 0."""
    assert _bound(MaxDepth, annotated_types.Le) == MAX_PREREQUISITE_DEPTH


def test_api_maxdepth_lower_bound_is_one() -> None:
    """MaxDepth 하한은 1(직접 선수만이 최소·기본) — 0 이하 깊이는 무의미."""
    assert _bound(MaxDepth, annotated_types.Ge) == 1
