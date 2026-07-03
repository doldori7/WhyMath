"""Part 10 MVP 경계 게이트 — "최종단계 기능 조기당김 금지"(10-2) 동결.

정본: `docs/standards/build_roadmap_part10_review.md`(Part 10 검토 정본) · 구축 플레이북 Part 10-2
(MVP→중급→최종). 법칙: MVP 경계(입력→tokenizer→Pratt→AST→normalize→renderer + 핵심5노드)를
지키고, **최종단계 기능(자기진화 Lean4·Manim 동영상·multimodal AST·step reasoning·semantic
feedback)을 조기 당기지 않는다**.

이 게이트는 새 구조를 만들지 않는다 — Part 10 검토가 확인한 "조기당김 없음" 상태를 동결한다.
누군가 최종단계 외부 의존(Lean4·Manim)을 *런타임 import*하거나 multimodal AST를 신설하면 실패.

동결 3종:
  1. **Lean4/Manim 런타임 미도입** — live 백엔드 소스에 `import lean`/`import manim` 등 *능동
     import*이 없다. (docstring·주석의 "Lean4/Manim" 언급은 *보류 기록*이라 정당 — import만 금지.)
  2. **multimodal AST 미신설** — `multimodal` 리터럴은 화이트리스트(`l3/router.py` OCR 비전
     라우팅 reason)에서만 등장한다. 그 밖의 파일에 등장하면 multimodal AST 조기당김 신호 → 실패.
  3. **보류 대장 트리거 명문화** — 검토 정본 문서의 보류 대장이 각 최종단계 기능에 *재검토
     트리거*를 명시한다(조기당김 금지의 이면 = "언제 착수하나"를 못 박음).

화이트리스트 근거: WH-S `whs/self_evolution.py`는 *오프라인 솔버 SFT*(verified 풀이→학습 레코드)
로, 보류된 DSL/Lean4 자기진화와 별개다(경계 disambiguation·docstring만·런타임 import 0).
"""

from __future__ import annotations

import re
from pathlib import Path

# repo root: tests/backend/test_*.py → parents[2].
_REPO_ROOT = Path(__file__).resolve().parents[2]
_BACKEND_SRC = _REPO_ROOT / "src" / "backend" / "whymath_backend"
_REVIEW_DOC = _REPO_ROOT / "docs" / "standards" / "build_roadmap_part10_review.md"

# 최종단계 외부 의존의 *능동 import*(런타임 도입)만 금지 — 단어 경계로 오탐(boolean·clean) 차단.
_FORBIDDEN_IMPORT = re.compile(r"^\s*(?:from|import)\s+(lean|manim)(?:\b|\.|4)", re.MULTILINE)

# `multimodal`(대소문자 무시) 허용 파일 — OCR 비전 라우팅 reason만 정당.
_MULTIMODAL_ALLOWED = {"l3/router.py"}

# 보류 대장이 트리거를 명시해야 하는 최종단계 기능 키워드.
_DEFERRED_FEATURES = ("Lean4", "Manim", "multimodal", "WH-1", "subgraph")


def _live_py_files() -> list[Path]:
    return sorted(_BACKEND_SRC.rglob("*.py"))


class TestNoFinalStageFeaturePulledForward:
    """10-2 최종단계 기능(Lean4·Manim·multimodal AST)이 live 경로에 조기당김 없음."""

    def test_no_runtime_lean_or_manim_import(self) -> None:
        offenders = [
            f"{py.relative_to(_BACKEND_SRC)}: {m.group(0).strip()}"
            for py in _live_py_files()
            for m in _FORBIDDEN_IMPORT.finditer(py.read_text(encoding="utf-8"))
        ]
        assert offenders == [], (
            f"최종단계 외부 의존 런타임 import(조기당김): {offenders} — "
            "Lean4(자기진화)·Manim(동영상)은 보류(risk_register·보류 대장). "
            "착수 트리거 도달 전 런타임 도입 금지."
        )

    def test_multimodal_literal_only_in_vision_routing(self) -> None:
        offenders = [
            str(py.relative_to(_BACKEND_SRC))
            for py in _live_py_files()
            if "multimodal" in py.read_text(encoding="utf-8").lower()
            and str(py.relative_to(_BACKEND_SRC)).replace("\\", "/") not in _MULTIMODAL_ALLOWED
        ]
        assert offenders == [], (
            f"'multimodal' 리터럴이 화이트리스트 밖 등장(multimodal AST 신호): {offenders}. "
            "허용은 OCR 비전 라우팅(l3/router.py)뿐 — multimodal AST는 최종단계(10-2)."
        )


class TestDeferralLedgerHasTriggers:
    """조기당김 금지의 이면 — 보류 대장이 각 최종단계 기능에 재검토 트리거를 명시."""

    def test_review_doc_exists(self) -> None:
        assert (
            _REVIEW_DOC.exists()
        ), f"Part 10 검토 정본 문서 부재: {_REVIEW_DOC} — 보류 대장(트리거)의 진실 원천."

    def test_each_deferred_feature_present_with_trigger(self) -> None:
        text = _REVIEW_DOC.read_text(encoding="utf-8")
        missing = [kw for kw in _DEFERRED_FEATURES if kw not in text]
        assert (
            missing == []
        ), f"보류 대장에 최종단계 기능 누락: {missing} — 각 항목은 트리거와 함께 등재돼야 함."
        # 대장 항목 수만큼 '트리거'가 등장(항목별 착수 조건 명문화 보장).
        assert text.count("트리거") >= len(
            _DEFERRED_FEATURES
        ), "보류 대장의 '트리거' 표기가 최종단계 기능 수보다 적음 — 항목별 재검토 조건 미명문화."
