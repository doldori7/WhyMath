"""시각화 4분류 코퍼스 orphan CI 게이트 (VIZ-05).

`concept_visualization_v1/visualizability.json`의 모든 `code`가 런타임 개념 code 공간
(`atom_graph_v1/graph.json`)에 실제로 존재하는지 CI에서 기계 차단(exit 1 등가 — pytest fail)한다.
"적재는 됐는데 매치 0"은 이 저장소의 반복 실패 유형이라(`docs/architecture/
visualization_module_gap_review.md` §6) 리포트 표시가 아니라 게이트로 올린다(VIZ-05 acceptance②).

이 파일은 세 축을 검증한다:
  1. **orphan 게이트 본체** — 실 코퍼스 전건이 원자 백본 code 공간에 존재하는지(hermetic·파일
     파싱만, DB 0).
  2. **변별력**(acceptance③) — 임의 code를 존재하지 않는 값으로 바꾼 `tmp_path` fixture로 게이트가
     실제로 fail하는지 → 복원해 pass하는지(성공/실패가 같은 값이면 위장 — CLAUDE.md).
  3. **라이브 재현**(acceptance④) — 재정렬된 실제 코퍼스에서 로드한 `Visualizability.추상` 값을
     `l4/scene_generation.generate_learning_scene`에 주입해, 시각화 블록이 실제로 생략되고 LLM이
     호출되지 않는지 end-to-end 확인(코퍼스 로드 → 정책 판정 → 장면 조립까지 이어지는 재현 — 실 DB
     대신 hermetic 통합 재현으로 acceptance④를 만족시킨다, VIZ-05 태스크 노트).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from whymath_backend.l1.concept_visualization import (
    ConceptVisualizabilityRecord,
    load_concept_visualization_from_json,
)
from whymath_backend.l3.interfaces import InMemoryCache, RecordingTraceSink
from whymath_backend.l3.models import GenerationResult, RoutingDecision, RoutingRequest
from whymath_backend.l4.learning_scene import VisualizationElement
from whymath_backend.l4.scene_generation import generate_learning_scene
from whymath_backend.schema.concept import Concept
from whymath_backend.schema.enums import ConceptLevel, Visualizability, VisualizationStyle

_REPO_ROOT = Path(__file__).resolve().parents[3]
_VISUALIZABILITY_CORPUS = (
    _REPO_ROOT / "data" / "corpus" / "concept_visualization_v1" / "visualizability.json"
)
_ATOM_GRAPH = _REPO_ROOT / "data" / "corpus" / "atom_graph_v1" / "graph.json"


def _load_atom_codes(path: Path) -> frozenset[str]:
    """`atom_graph_v1/graph.json`의 `concepts[].code` 전체(레벨 무관) → 런타임 code 공간.

    orphan 판정의 분모는 진단 대상(세부개념)만이 아니라 *code 공간 전체*여야 한다 — 시각화
    코퍼스의 code가 단원·소단원 code를 가리켜도 orphan은 아니어야 하므로(오탐 방지) 필터링 없이
    전 레벨을 모은다.
    """
    payload = json.loads(path.read_text(encoding="utf-8"))
    return frozenset(c["code"] for c in payload["concepts"])


def _orphaned_codes(
    records: list[ConceptVisualizabilityRecord], atom_codes: frozenset[str]
) -> list[str]:
    """코퍼스 레코드 중 원자 백본 code 공간에 없는 code 목록(순서 보존)."""
    return [r.code for r in records if r.code not in atom_codes]


def _run_orphan_gate(*, corpus_path: Path, atom_graph_path: Path) -> None:
    """orphan 게이트 본체 — 위반이 있으면 `pytest.fail`로 어떤 code가 orphan인지 명시한다."""
    records = load_concept_visualization_from_json(corpus_path)
    atom_codes = _load_atom_codes(atom_graph_path)
    orphaned = _orphaned_codes(records, atom_codes)
    if orphaned:
        pytest.fail(
            "concept_visualization 코퍼스에 원자 백본(atom_graph_v1) code 공간과 어긋나는 "
            f"orphan code {len(orphaned)}건 — {orphaned}. "
            "적재는 되나 런타임에서 절대 매치되지 않아 시각화 정책 보호가 무력화된다"
            "(docs/architecture/visualization_module_gap_review.md §7.2)."
        )


# ── 1. orphan 게이트 본체 — 실 코퍼스 ─────────────────────────────────────────
def test_real_corpus_has_no_orphaned_codes() -> None:
    """실제 `visualizability.json` 전건이 원자 백본 code 공간에 존재한다(CI 상시 차단선)."""
    _run_orphan_gate(corpus_path=_VISUALIZABILITY_CORPUS, atom_graph_path=_ATOM_GRAPH)


def test_real_corpus_abstract_entry_matches_expected_code() -> None:
    """재정렬 후 유일 항목이 대우증명·귀류법(10공수2-02-07-1)·추상 분류인지 회귀 감시."""
    records = load_concept_visualization_from_json(_VISUALIZABILITY_CORPUS)
    assert records == [
        ConceptVisualizabilityRecord(code="10공수2-02-07-1", visualizability=Visualizability.추상)
    ]


# ── 2. 변별력 — 임의 code를 존재하지 않는 값으로 바꿔 fail→pass 상태 전이 실측 ──
def test_orphan_gate_fails_on_injected_bad_code_then_passes_when_restored(
    tmp_path: Path,
) -> None:
    """(CLAUDE.md 변별력 규칙) 게이트가 실패 상태에서 실제로 실패 신호를 내는지 실측한다.

    `tmp_path`로 격리해 실제 코퍼스 파일은 건드리지 않는다.
    """
    good_payload = json.loads(_VISUALIZABILITY_CORPUS.read_text(encoding="utf-8"))
    assert good_payload["entries"], "픽스처 전제 — 실 코퍼스가 비어있으면 이 테스트가 무의미"

    bad_payload = json.loads(json.dumps(good_payload))  # 깊은 복사
    bad_payload["entries"][0]["code"] = "존재하지-않는-코드-XYZ"
    bad_path = tmp_path / "visualizability_bad.json"
    bad_path.write_text(json.dumps(bad_payload, ensure_ascii=False), encoding="utf-8")

    # ① 주입된 orphan code — 게이트가 실제로 실패해야 한다. `pytest.fail`은 `Failed`
    #    (BaseException 하위 — 일반 Exception이 아님)를 던지므로 `pytest.fail.Exception`으로
    #    정확히 포착한다.
    with pytest.raises(pytest.fail.Exception, match="orphan code"):
        _run_orphan_gate(corpus_path=bad_path, atom_graph_path=_ATOM_GRAPH)

    # ② 복원 — 같은 atom_graph 대조로 정상 통과(성공/실패가 같은 값이면 위장이므로 반드시 대조).
    good_path = tmp_path / "visualizability_good.json"
    good_path.write_text(json.dumps(good_payload, ensure_ascii=False), encoding="utf-8")
    _run_orphan_gate(corpus_path=good_path, atom_graph_path=_ATOM_GRAPH)  # 예외 없이 통과


def test_orphaned_codes_helper_is_pure_and_order_preserving() -> None:
    """`_orphaned_codes` 순수 함수 단위 검증 — 매치되는 code는 제외, orphan만 순서 보존 반환."""
    records = [
        ConceptVisualizabilityRecord(code="A1", visualizability=Visualizability.직접),
        ConceptVisualizabilityRecord(code="GHOST-1", visualizability=Visualizability.추상),
        ConceptVisualizabilityRecord(code="A2", visualizability=Visualizability.동적),
        ConceptVisualizabilityRecord(code="GHOST-2", visualizability=Visualizability.부분),
    ]
    atom_codes = frozenset({"A1", "A2"})
    assert _orphaned_codes(records, atom_codes) == ["GHOST-1", "GHOST-2"]


# ── 3. 라이브 재현 — 재정렬된 코퍼스 값이 실제로 시각화 블록을 생략시키는지(acceptance④) ──
_GRAPH2D_SPEC = (
    '{"type": "interactive_graph_2d", "spec": {"function": "x**2"}, "interactive": true}'
)


class _FakeProvider:
    """가짜 LLMProvider — 호출 여부·내용만 기록(`test_scene_generation.py` 패턴 답습)."""

    def __init__(self, text: str) -> None:
        self._text = text
        self.calls: list[tuple[str, str, RoutingDecision]] = []

    async def generate(
        self, prompt: str, system: str, decision: RoutingDecision
    ) -> GenerationResult:
        self.calls.append((prompt, system, decision))
        return GenerationResult(self._text)


def _req() -> RoutingRequest:
    return RoutingRequest(
        task_type="generate",
        difficulty="medium",
        requires_reasoning=True,
        student_subscription="free",
    )


@pytest.mark.asyncio
async def test_reordered_corpus_abstract_value_skips_literal_visualization_live() -> None:
    """코퍼스 파일 → 로더 → 정책 게이트 → 장면 조립까지 end-to-end 재현(hermetic).

    `TestVisualizabilityGate.test_abstract_skips_literal_visualization`(test_scene_generation.py)
    이 이미 `Visualizability.추상`을 직접 주입해 일반 정책을 검증하지만, 이 테스트의 신규 가치는
    **재정렬된 실제 코퍼스 파일에서 로드한 값**을 쓴다는 점이다 — code 재정렬이 실제로 런타임
    보호를 되살렸는지를 코퍼스 로드부터 재현한다(DB 접근 불가 환경의 acceptance④ 대체 재현).
    """
    records = load_concept_visualization_from_json(_VISUALIZABILITY_CORPUS)
    assert records, "재정렬된 코퍼스가 비어있으면 이 재현이 무의미"
    abstract_record = next(r for r in records if r.visualizability == Visualizability.추상)
    assert abstract_record.code == "10공수2-02-07-1"

    concept = Concept(
        code=abstract_record.code,
        name_ko="대우증명·귀류법",
        level=ConceptLevel.세부개념,
        recommended_visual_styles=[VisualizationStyle.함수그래프],
        cognitive_type=[],
    )
    provider = _FakeProvider(_GRAPH2D_SPEC)

    scene = await generate_learning_scene(
        concept,
        "고1",
        _req(),
        provider=provider,
        cache=InMemoryCache(),
        trace=RecordingTraceSink(),
        visualizability=abstract_record.visualizability,
    )

    assert not any(isinstance(el, VisualizationElement) for el in scene.elements)
    assert provider.calls == []  # 억지 리터럴 그림을 위해 LLM을 부르지 않는다
