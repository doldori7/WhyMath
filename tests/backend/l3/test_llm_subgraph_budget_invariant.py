"""단계8 Q10-⑧ 불변식 CI 동결 — "LLM은 전체 그래프 미열람".

정본: `math_dsl_risk_register.md` §2 Q10-⑧ · `docs/standards/build_roadmap_part10_review.md`.

Part 10(구축 로드맵) 검토가 단계8(AI튜터·Context)을 *실코드로* 재확인한 결과: graph→LLM
컨텍스트 빌더는 아직 없고(소비처 부재·premature), AI튜터는 이미 조립된 문자열 프롬프트와
구조 신호(`PrerequisiteGap`·단일 reactive `Misconception`·mastery)만 소비한다. 따라서 "전체
그래프 노출" 🔴 는 *잠재/미래* 리스크지 현존 결함이 아니다. 이 게이트는 그 경계가 회귀로
무너지지 않도록 **동결**한다 — 누군가 concept/atom 그래프의 노드·엣지 **컬렉션**(또는 전체
그래프)을 LLM 생성·프롬프트 경계에 직접 흘리면 실패한다.

동결 2종:
  1. **LLM 생성·프롬프트 경계는 문자열·스칼라·단일 reactive 객체만** — `LLMProvider.generate`와
     프로덕션 프롬프트 빌더의 어떤 파라미터도 `Concept`/`ConceptEdge`/`Atom` **컬렉션**이나
     전체 그래프를 받지 않는다. (`concept: str` 개념명·단일 `Misconception`·`Sequence[str]`
     이미지·양식은 허용 — 그래프 구조가 아니다.)
  2. **traversal 깊이 예산 단일 출처** — `MAX_PREREQUISITE_DEPTH`가 유일 출처이며 `api/me`
     `MaxDepth`가 이를 `le=`로 공유(매직넘버 중복 0).

주의: 상한 수치(depth≤2·max_nodes~12·max_tokens~3000)의 *능동 guard*(LLM 컨텍스트 예산)는
graph→LLM 컨텍스트 **소비처가 생길 때** canonical seam으로 도입한다(risk_register 미채택→트리거).
그 seam 전까지 이 게이트가 "전체 그래프 미주입" 경계를 지킨다.
"""

from __future__ import annotations

import inspect
import re
from pathlib import Path
from typing import Callable

import pytest
from whymath_backend.l2.prerequisite_recommendation import MAX_PREREQUISITE_DEPTH
from whymath_backend.l3.interfaces import LLMProvider
from whymath_backend.l3.pipeline import _build_async_payload
from whymath_backend.l3.providers.anthropic import AnthropicProvider
from whymath_backend.l3.providers.composite import CompositeProvider
from whymath_backend.l3.providers.ollama import OllamaProvider
from whymath_backend.l3.visualization import build_visualization_prompt
from whymath_backend.l4.misconception.judge_prompts import build_judge_user

# 백엔드 소스 루트(api/me.py 단일-출처 스캔용). tests/backend/l3/ → repo root = parents[3].
_BACKEND_ROOT = Path(__file__).resolve().parents[3] / "src" / "backend" / "whymath_backend"

# 금지 어노테이션 — concept/atom 그래프의 노드·엣지 *컬렉션* 또는 전체 그래프.
# `concept: str`(개념명)·단일 `Misconception`(reactive)·`Sequence[str]`(이미지/양식)은 걸리지
# 않는다 — 그래프 구조가 아니기 때문. 걸리는 건 list[Concept]·Sequence[ConceptEdge]·전체 그래프뿐.
_FORBIDDEN_ANNOTATION = re.compile(
    r"(?:list|Sequence|Iterable|Collection|set|frozenset|tuple|Mapping|dict)"
    r"\s*\[[^\]]*\b(?:Concept|ConceptEdge|ConceptNode|Atom|AtomEdge|AtomNode)\b"
    r"|\bConceptEdge\b|\bConceptGraph\b|\bAtomGraph\b|graph\.json"
)

# LLM 생성·프롬프트 경계 — 이 경계로 그래프가 새면 Q10-⑧ 위반.
_LLM_BOUNDARY: list[tuple[str, Callable[..., object]]] = [
    ("LLMProvider.generate", LLMProvider.generate),
    ("AnthropicProvider.generate", AnthropicProvider.generate),
    ("CompositeProvider.generate", CompositeProvider.generate),
    ("OllamaProvider.generate", OllamaProvider.generate),
    ("l3.pipeline._build_async_payload", _build_async_payload),
    ("l3.visualization.build_visualization_prompt", build_visualization_prompt),
    ("l4.misconception.judge_prompts.build_judge_user", build_judge_user),
]


def _annotation_str(annotation: object) -> str:
    """`from __future__ import annotations`면 문자열, 아니면 타입 — 둘 다 문자열로 정규화."""
    return annotation if isinstance(annotation, str) else str(annotation)


class TestNoFullGraphToLLM:
    """Q10-⑧ ①: LLM 경계는 문자열·스칼라·단일 reactive 객체만 — 그래프 컬렉션 금지."""

    @pytest.mark.parametrize("label, func", _LLM_BOUNDARY, ids=[n for n, _ in _LLM_BOUNDARY])
    def test_boundary_takes_no_graph_collection(
        self, label: str, func: Callable[..., object]
    ) -> None:
        signature = inspect.signature(func)
        offenders = {
            name: _annotation_str(param.annotation)
            for name, param in signature.parameters.items()
            if param.annotation is not inspect.Parameter.empty
            and _FORBIDDEN_ANNOTATION.search(_annotation_str(param.annotation))
        }
        assert offenders == {}, (
            f"{label}: 그래프 노드·엣지 컬렉션/전체 그래프를 LLM 경계로 주입 — Q10-⑧ 위반. "
            f"위반 파라미터={offenders}. LLM에는 Minimal Reasoning Subgraph(seam 경유)만 "
            "허용된다(risk_register §2 Q10-⑧·build_roadmap_part10_review)."
        )


class TestTraversalBudgetSingleSource:
    """Q10-⑧ ②: traversal 깊이 예산은 단일 출처 — api 경계가 이를 공유."""

    def test_max_prerequisite_depth_is_positive_int(self) -> None:
        assert isinstance(MAX_PREREQUISITE_DEPTH, int)
        assert MAX_PREREQUISITE_DEPTH > 0

    def test_api_me_shares_single_source(self) -> None:
        """`api/me.py`가 `le=MAX_PREREQUISITE_DEPTH`로 상한을 공유(매직넘버 중복 금지)."""
        source = (_BACKEND_ROOT / "api" / "me.py").read_text(encoding="utf-8")
        assert "le=MAX_PREREQUISITE_DEPTH" in source, (
            "api/me.py의 MaxDepth가 MAX_PREREQUISITE_DEPTH 단일 출처를 공유하지 않음 "
            "— traversal 예산 매직넘버 중복(Q10-⑧ 단일 출처 위반)."
        )
