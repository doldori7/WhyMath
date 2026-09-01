"""과목 어댑터 조립 지점(DI seat) — 주입·기본값·복원 동결 (EOS-69).

이 좌석은 **전역 상태**다. 전역은 편하지만 두 가지로 배신한다: ① 아무도 안 심었을 때 조용히
아무 일도 안 하거나 ② 테스트가 심은 가짜가 다음 테스트로 새어 나간다. 이 스위트는 그 둘을
막는다 — ①은 "기본값이 실제 계약을 만족하는 구현"임을 요구해서, ②는 컨텍스트 매니저가
예외 경로에서도 복원함을 요구해서.

`pytest-randomly`로 순서가 매번 섞이므로 ②는 이론이 아니라 실제 위험이다.
"""

from __future__ import annotations

from typing import Mapping, Sequence

import pytest

from whymath_backend import subject_registry
from whymath_backend.schema.subject_adapter import (
    AnswerEvaluation,
    ContentSealBreach,
    MisconceptionSignal,
    ProblemAnswerKeyView,
    ProblemStatement,
    ProblemValidation,
    SubjectAdapter,
)


class _StubAdapter:
    """계약을 만족하는 최소 스텁 — 판정은 하지 않고 호출 사실만 남긴다."""

    subject_id = "stub"

    def evaluate_answer(
        self, problem: ProblemStatement, answer: Mapping[str, str]
    ) -> AnswerEvaluation:
        return AnswerEvaluation(state="unverifiable", reason="stub")

    def evaluate_final_answer(
        self, problem: ProblemAnswerKeyView, student_answer: str | None
    ) -> AnswerEvaluation:
        return AnswerEvaluation(state="unverifiable", reason="stub")

    def check_equivalence_claim(self, left: str, right: str) -> AnswerEvaluation:
        return AnswerEvaluation(state="unverifiable", reason="stub")

    def check_content_seal(
        self, source_text: str, derived_texts: Sequence[str]
    ) -> ContentSealBreach | None:
        return None

    def detect_misconception(
        self, student_work: str, *, top_k: int = 3
    ) -> Sequence[MisconceptionSignal]:
        return ()

    async def validate_problem(self, problem: ProblemStatement) -> ProblemValidation:
        return ProblemValidation(state="unverifiable", reason="stub")


@pytest.fixture(autouse=True)
def _restore_seat() -> object:
    """어떤 테스트가 좌석을 건드려도 원상 복구한다 — 순서 무작위 실행의 오염 차단."""
    previous = subject_registry.get_subject_adapter()
    yield None
    subject_registry.set_subject_adapter(previous)


def test_default_adapter_satisfies_the_contract() -> None:
    """아무도 안 심었을 때의 기본값이 *실제 계약을 만족하는 구현*이어야 한다.

    기본값이 None이거나 껍데기면 Core 호출부가 조용히 검증을 건너뛰게 된다 — 그건 이
    저장소가 가장 자주 뚫린 형태(선언은 있는데 배선이 없음)다.
    """
    subject_registry.set_subject_adapter(None)
    adapter = subject_registry.get_subject_adapter()
    assert isinstance(adapter, SubjectAdapter)
    assert adapter.subject_id == "math", "현행 배포 기본 과목은 math다(설정이지 Core 지식 아님)"


def test_default_is_created_once_and_reused() -> None:
    """기본값은 매 호출 새로 만들지 않는다(무거운 검증 스택을 반복 구성하지 않는다)."""
    subject_registry.set_subject_adapter(None)
    assert subject_registry.get_subject_adapter() is subject_registry.get_subject_adapter()


def test_explicit_injection_wins_over_the_default() -> None:
    stub = _StubAdapter()
    subject_registry.set_subject_adapter(stub)
    assert subject_registry.get_subject_adapter() is stub


def test_setting_none_falls_back_to_the_default_again() -> None:
    subject_registry.set_subject_adapter(_StubAdapter())
    subject_registry.set_subject_adapter(None)
    assert subject_registry.get_subject_adapter().subject_id == "math"


def test_context_manager_restores_even_when_the_block_raises() -> None:
    """예외로 빠져나가도 복원된다 — 실패한 테스트가 뒤 테스트를 깨지 않게 하는 유일한 보증."""
    subject_registry.set_subject_adapter(None)
    before = subject_registry.get_subject_adapter()
    with pytest.raises(RuntimeError):
        with subject_registry.use_subject_adapter(_StubAdapter()):
            assert subject_registry.get_subject_adapter().subject_id == "stub"
            raise RuntimeError("의도된 실패")
    assert subject_registry.get_subject_adapter() is before


def test_core_modules_do_not_import_the_implementation() -> None:
    """조립 지점이 구현체를 아는 **유일한 모듈**임을 소스로 확인한다.

    `lint-imports`가 이미 정적으로 막지만(EOS-67), 그 계약이 꺼지거나 예외가 붙는 경우를
    대비한 이중 회계다 — 게이트 하나에만 의존하지 않는다.
    """
    import ast
    import pathlib

    root = pathlib.Path(subject_registry.__file__).parent
    # 산문(docstring·주석)은 대상이 아니다 — 계약 문서가 구현체를 *설명*하는 것은 의존이
    # 아니다. import 문만 본다(경계 스캔과 같은 축: AST).
    allowed = {"subject_registry.py", "app.py"}
    offenders: list[str] = []
    for path in sorted(root.rglob("*.py")):
        if path.name in allowed:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        names: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                names.append(node.module)
            elif isinstance(node, ast.Import):
                names.extend(alias.name for alias in node.names)
        if any("subject_adapter_math" in name for name in names):
            offenders.append(path.relative_to(root).as_posix())
    assert offenders == [], f"구현체를 import하는 모듈이 조립 지점 밖에 있다: {offenders}"
