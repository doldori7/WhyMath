"""선수 traversal 예산(깊이·노드 수) 단일 출처 가드 — 동작 불변 동결.

선수 traversal은 두 축으로 bound된다:
① *깊이* — `MAX_PREREQUISITE_DEPTH` 단일 출처, API 경계(`api/me.py` MaxDepth)가 상한을
   *공유*(매직 넘버 중복 제거). (a) 값 동결 + (b) API가 단일 출처 참조를 함께 못 박아 drift 차단.
② *노드 수(breadth)* — `MAX_PREREQUISITE_NODES` 단일 출처 안전밸브(2026-08-05 — 구 PR#379
   `dsl-scalability-analysis-3rbgxr`의 코드 절반 재실행). 재귀 CTE 결과가 규모에서 병리적으로
   폭증하는 것만 차단하고 현재 규모에선 미발동(행동 불변). 순수 헬퍼 `_cap_by_node_budget`이
   절단 시 조용히 넘기지 않고 로깅한다(silent truncation 금지 — CLAUDE.md "AI·신뢰" 축).

⚠️ 둘 다 *그래프 traversal 예산*이다 — "LLM 컨텍스트 예산"(max_tokens)이 아니다. 그 경계는
`docs/standards/build_roadmap_part10_review.md` §4·`tests/backend/l3/test_llm_subgraph_budget_invariant.py`
가 별도로 다루며(소비처 부재·premature·미채택), 이 두 상수와는 독립이다. hermetic(introspection +
순수 헬퍼·DB·앱 기동 불요).
"""

from __future__ import annotations

import logging
import uuid
from typing import get_args

import annotated_types
import pytest

from whymath_backend.api.me import MaxDepth
from whymath_backend.l2.prerequisite_recommendation import (
    MAX_PREREQUISITE_DEPTH,
    MAX_PREREQUISITE_NODES,
    PrerequisiteRow,
    _cap_by_node_budget,
)


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


# ── 노드 수(breadth) 예산 — `MAX_PREREQUISITE_NODES` 안전밸브(순수 헬퍼) ──────────────────────


def _row(depth: int = 1, strength: float = 0.5) -> PrerequisiteRow:
    """합성 선수 행 1건 — concept_id는 매번 새 UUID(dedup 무관·캡 개수만 검증)."""
    return PrerequisiteRow(
        concept_id=uuid.uuid4(),
        concept_code="UC-SYN",
        name_ko="합성 선수",
        edge_strength=strength,
        depth=depth,
    )


def test_max_prerequisite_nodes_frozen() -> None:
    """노드 상한 값 동결 — 변경 시 의도적으로 이 테스트를 갱신하게 강제(예산 계약)."""
    assert MAX_PREREQUISITE_NODES == 64


def test_cap_under_budget_returns_all_unchanged() -> None:
    """캡 이하 → 전량 그대로 반환(현재 규모 = 행동 불변·동일 리스트 객체)."""
    rows = [_row() for _ in range(MAX_PREREQUISITE_NODES)]  # 정확히 cap = 절단 없음(<=)
    out = _cap_by_node_budget(rows)
    assert out is rows  # 미절단 경로는 입력을 그대로 통과(복사 없음)
    assert len(out) == MAX_PREREQUISITE_NODES


def test_cap_over_budget_truncates_and_preserves_order(caplog: pytest.LogCaptureFixture) -> None:
    """캡 초과 → 상위 cap개만·앞쪽 순서 보존·드롭 경고 1건(silent 금지 검증)."""
    rows = [_row() for _ in range(MAX_PREREQUISITE_NODES + 5)]  # cap+5 → 5개 드롭
    with caplog.at_level(logging.WARNING):
        out = _cap_by_node_budget(rows)
    assert len(out) == MAX_PREREQUISITE_NODES
    assert out == rows[:MAX_PREREQUISITE_NODES]  # 결정론 정렬(앞쪽=가깝고 강함) 보존
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1  # 절단은 조용히 넘기지 않는다(정확히 1건)
    assert "5" in warnings[0].getMessage()  # 드롭 수(5) 명시


def test_cap_custom_value() -> None:
    """`cap` 인자로 예산 주입 가능(단일 출처 상수 override — 테스트·튜닝 여지)."""
    rows = [_row() for _ in range(10)]
    assert len(_cap_by_node_budget(rows, cap=3)) == 3
