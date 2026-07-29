"""Schema 수식 음성화 — SpeechSpec 불변식 게이트 + 토큰 유니온. 음성 슬라이스 S1.

`learning_scene` 게이트 테스트 정신: 정답·원시 밀반입 차단(extra="forbid")·빈 낭독 거부·
토큰↔plain_text 추적성 불변식을 단언한다(잘못된 명세는 학생 미노출).
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError
from whymath_backend.l3.speech import InvalidSpeechSpecError, parse_speech_spec
from whymath_backend.schema.speech import (
    BreakToken,
    DocumentSpeechSpec,
    SpeechGradeBand,
    SpeechSpec,
    TextToken,
)


def _valid_kwargs() -> dict[str, object]:
    return {
        "source_latex": "x^2",
        "grade_band": SpeechGradeBand.고등,
        "plain_text": "엑스 제곱",
        "tokens": [TextToken(text="엑스"), TextToken(text="제곱")],
    }


def test_valid_spec_constructs() -> None:
    """정합 명세는 생성되고 한글 enum 값이 보존된다(use_enum_values)."""
    spec = SpeechSpec(**_valid_kwargs())
    assert spec.grade_band == "고등"
    assert spec.plain_text == "엑스 제곱"


def test_empty_source_latex_rejected() -> None:
    """① source_latex 비면 거부."""
    kwargs = _valid_kwargs() | {"source_latex": "  "}
    with pytest.raises(ValidationError):
        SpeechSpec(**kwargs)


def test_empty_plain_text_rejected() -> None:
    """② plain_text 비면 거부(빈 낭독 금지)."""
    kwargs = _valid_kwargs() | {"plain_text": "", "tokens": []}
    with pytest.raises(ValidationError):
        SpeechSpec(**kwargs)


def test_tokens_must_reconstruct_plain_text() -> None:
    """③ 토큰을 이은 텍스트가 plain_text와 다르면 거부(추적성 불변식)."""
    kwargs = _valid_kwargs() | {"tokens": [TextToken(text="다른")]}
    with pytest.raises(ValidationError):
        SpeechSpec(**kwargs)


def test_break_tokens_do_not_break_reconstruction() -> None:
    """break 토큰은 plain_text 재구성에 기여하지 않는다(공백만)."""
    spec = SpeechSpec(
        **(
            _valid_kwargs()
            | {
                "tokens": [
                    TextToken(text="엑스"),
                    BreakToken(duration_ms=100),
                    TextToken(text="제곱"),
                ]
            }
        )
    )
    assert spec.plain_text == "엑스 제곱"


def test_extra_field_forbidden_blocks_answer_smuggling() -> None:
    """extra="forbid" — 정답·해설 밀반입 필드를 구조적으로 차단(learning_scene 선례)."""
    with pytest.raises(InvalidSpeechSpecError):
        parse_speech_spec(
            {
                "source_latex": "x",
                "grade_band": "고등",
                "plain_text": "엑스",
                "tokens": [{"kind": "text", "text": "엑스"}],
                "answer": "3",  # 밀반입 시도
            }
        )


def test_break_token_duration_must_be_positive() -> None:
    """BreakToken duration_ms는 0 초과여야 한다."""
    with pytest.raises(ValidationError):
        BreakToken(duration_ms=0)


def test_text_token_must_be_nonempty() -> None:
    """TextToken text는 최소 1자."""
    with pytest.raises(ValidationError):
        TextToken(text="")


def test_document_spec_rejects_empty_plain() -> None:
    """DocumentSpeechSpec도 빈 낭독을 거부한다."""
    with pytest.raises(ValidationError):
        DocumentSpeechSpec(grade_band=SpeechGradeBand.고등, plain_text="  ")
