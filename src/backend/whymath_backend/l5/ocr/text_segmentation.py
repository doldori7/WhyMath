"""텍스트 풀이 → 단계(step) 분해 — 구조 판별만(순수·의미 판정 0·LLM 0).

**목적**: `api/verify.py:8-10`·`04a_wh1_tutoring_harness.md:605`가 "텍스트→단계 분해는
L5(OCR·공간정보) 책임"이라 명시하지만, 실제 이미지 경로(`assemble.py`)는 bbox 읽기순
정렬만 하고 *텍스트 입력*의 분해는 코어에 정본이 없었다(`docs/architecture/
nlp_module_gap_review.md` §3 D3). 그 자리를 실제로 채우고 있던 건 Flutter 클라이언트
(`chat_controller.dart::_splitSteps` + `latex_to_plain.dart::_unwrapDisplaylines`)뿐이었고,
"백엔드를 미러링한다"는 주석만 있을 뿐 동기화를 강제하는 장치가 없어 2026-07-20에 실제로
드리프트가 터졌다(`\\displaylines{}`의 행 구분자 `\\\\`가 `'\\n'` 분해에 걸리지 않아 단일
0-전이 스텝이 되는 실기기 사고). 이 모듈이 그 정본이다.

**`data/segmentation_contract.json`이 이 함수의 골든 테스트 계약이다** — 두 구현(이 파일과
모바일 `_splitSteps`/`_unwrapDisplaylines`)이 *같은 JSON*을 읽어 동일 판정을 내는지
교차 검증한다(`notation_contract.json` 선례와 동형 패턴). 계약 JSON은 건드리지 않는다.

**L5 배치 이유**: 설계 정본이 "텍스트→단계 분해는 L5 책임"이라 명시하고, 이 파일은
자매 계약인 `l5/ocr/verify.py::_latex_to_sympifiable`(기호 치환 미러)과 같은 서브시스템에
둔다. L3(`l3/verify_solution.py`)는 *이미 분해된* steps를 검증하는 계층이지 분해 자체를
하는 계층이 아니다(레이어 경계 유지 — 분해와 검증을 섞지 않는다).

**표현 ≠ 의미**: 이 함수는 여전히 표기/구조 변환이지 수학 판정이 아니다. 기호 치환
(`\\frac`·`\\pi` 등)은 이 계약의 범위 밖 — 그건 `l5/ocr/verify.py::_latex_to_sympifiable`
↔ `latex_to_plain.dart`의 별개 기존 계약이다(혼동 금지).

LLM 사용 0 — 분해는 순수 구조 판별이다. `verify.py`가 든 사유(방정식 풀이·변형 체인
혼동으로 거짓 incorrect 위험)가 그대로 유효하다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

__all__ = [
    "SegmentationResult",
    "segment_solution_text",
]

# `\displaylines{...}` 래퍼 탐지 마커 — MathLive가 내는 여러 줄 LaTeX 직렬화 표식.
_DISPLAYLINES_MARKER = "\\displaylines"


def _unwrap_displaylines(text: str) -> str:
    """`\\displaylines{...}` 래퍼를 벗겨 안쪽만 돌려준다(중첩 중괄호 균형 스캔). 없으면 원문 유지.

    `latex_to_plain.dart::_unwrapDisplaylines`의 이식(균형 스캔 방식 동일) — MathLive가 내는
    여러 줄 LaTeX 직렬화 래퍼를 구조적으로 벗긴다(기호 치환은 하지 않는다).
    """
    idx = text.find(_DISPLAYLINES_MARKER)
    if idx < 0:
        return text
    brace_start = text.find("{", idx)
    if brace_start < 0:
        return text
    depth = 0
    for i in range(brace_start, len(text)):
        c = text[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return text[brace_start + 1 : i]
    return text  # 불균형 중괄호 — 원문 유지(보수적).


@dataclass(frozen=True, slots=True)
class SegmentationResult:
    """`segment_solution_text`의 결과 — 분해된 단계 목록 + 구조적 의심(fail-closed) 플래그.

    `ambiguous=True`는 분해가 *실패했다*는 뜻이 아니라, displaylines 마커가 원문에 있는데도
    결과가 1스텝 이하로 뭉개져 2026-07-20류 재발이 의심된다는 관측 신호다(차단하지 않는다 —
    조용히 정상 취급만 하지 않는다).
    """

    steps: tuple[str, ...]
    ambiguous: bool


def segment_solution_text(text: str) -> SegmentationResult:
    """텍스트 풀이 → 단계(step) 목록(순수·구조 판별만·의미 판정 0·LLM 0).

    `data/segmentation_contract.json`이 이 함수의 골든 테스트 계약이다(정본).
    """
    original = text
    unwrapped = _unwrap_displaylines(text)
    # LaTeX 행 구분자 '\\'(백슬래시 2개)를 줄바꿈과 동일하게 취급 — displaylines·평문 양쪽을
    # 하나의 분해 경로로 통합한다(latex_to_plain.dart가 별도 함수 두 개로 나눈 것의 통합).
    normalized = unwrapped.replace("\\\\", "\n")
    parts = re.split(r"\r\n|\r|\n", normalized)
    steps = tuple(s.strip() for s in parts if s.strip())
    # fail-closed 관측: displaylines 마커가 원문에 있는데 결과가 1스텝 이하면 구조적으로
    # 의심스럽다(2026-07-20류 재발 신호) — 조용히 정상 취급하지 않고 플래그만 남긴다(차단 아님).
    ambiguous = _DISPLAYLINES_MARKER in original and len(steps) <= 1
    return SegmentationResult(steps=steps, ambiguous=ambiguous)
