"""Schema v1.0 Dialogue 모델 단위 테스트 — 생성·extra forbid·범위·required·enum 직렬화.

설계 정본: `schemas/v1.0/schema_v1.0.md` §7.1(dialogue·dialogue_turn). 2테이블 + 신규
ENUM 5종(Resolution·TurnRole·ContentType·SocraticStrategy·StudentIntent).

이 도메인에는 구조 cross-field 불변식(자기관계·카운트 정합 등)이 없어 모델에 validator가
없다(`concept.py`·`dialogue.py` 방침 — 없는 게 맞다). 따라서 불변식 분기 테스트 없이
required(DialogueTurn.turn_order)·범위(student_rating 1-5 등)·enum·JSONB·extra forbid를
검증한다.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from whymath_backend.schema.dialogue import (
    Dialogue,
    DialogueTurn,
)
from whymath_backend.schema.enums import (
    ContentType,
    Resolution,
    SocraticStrategy,
    StudentIntent,
    TurnRole,
)


# ──────────────────────────────────────────────────────────────────────
# 신규 ENUM 5종 — 값 검증(§7.1 인라인 DDL 정본; TurnRole만 영어)
# ──────────────────────────────────────────────────────────────────────
class TestDialogueEnumValues:
    def test_resolution_values_korean(self) -> None:
        """Resolution — §7.1 한글 5종(L710-711)."""
        assert Resolution.학생자력해결.value == "학생자력해결"
        assert Resolution.Socratic유도성공.value == "Socratic유도성공"
        assert {e.value for e in Resolution} == {
            "학생자력해결",
            "Socratic유도성공",
            "힌트필요",
            "풀이공개로종결",
            "포기",
        }

    def test_turn_role_values_english(self) -> None:
        """TurnRole — §7.1 영어 3종(L735)."""
        assert TurnRole.student.value == "student"
        assert {e.value for e in TurnRole} == {"student", "assistant", "system"}

    def test_content_type_values_korean(self) -> None:
        """ContentType — §7.1 한글 4종(L737)."""
        assert {e.value for e in ContentType} == {"텍스트", "수식", "이미지", "혼합"}

    def test_socratic_strategy_values_korean(self) -> None:
        """SocraticStrategy — §7.1 한글 6종(L740-741)."""
        assert SocraticStrategy.조건확인.value == "조건확인"
        assert SocraticStrategy.그래프그리기제안.value == "그래프그리기제안"
        assert {e.value for e in SocraticStrategy} == {
            "조건확인",
            "예시제시",
            "반례제시",
            "단계분해",
            "유사문제",
            "그래프그리기제안",
        }

    def test_student_intent_values_korean(self) -> None:
        """StudentIntent — §7.1 한글 5종(L747-748)."""
        assert {e.value for e in StudentIntent} == {
            "답시도",
            "질문",
            "막힘표현",
            "포기",
            "이해확인",
        }

    def test_str_enum_equality(self) -> None:
        """str-Enum — 문자열 값과 동등 비교(라우터·필터 안정성)."""
        assert Resolution.포기 == "포기"
        assert TurnRole.assistant == "assistant"
        assert SocraticStrategy.단계분해 == "단계분해"


# ──────────────────────────────────────────────────────────────────────
# Dialogue — 생성·기본값·roundtrip·범위
# ──────────────────────────────────────────────────────────────────────
class TestDialogue:
    def test_minimal_valid(self) -> None:
        """모든 필드 nullable/기본값 — 빈 생성 시 dialogue_id만 자동, flag는 False."""
        d = Dialogue()
        assert isinstance(d.dialogue_id, uuid.UUID)
        assert d.user_id is None
        assert d.resolution is None
        assert d.model_used is None
        assert d.student_rating is None
        # BOOLEAN DEFAULT FALSE
        assert d.flagged_for_review is False

    def test_full_fields_roundtrip(self) -> None:
        """전 필드 채운 대화 — 값 보존 확인."""
        uid = uuid.uuid4()
        aid = uuid.uuid4()
        pid = uuid.uuid4()
        now = datetime.now(timezone.utc)
        d = Dialogue(
            user_id=uid,
            attempt_id=aid,
            problem_id=pid,
            started_at=now,
            ended_at=now,
            resolution=Resolution.Socratic유도성공,
            total_turns=6,
            student_turns=3,
            assistant_turns=3,
            model_used="claude-opus-4-7",
            total_tokens=1500,
            estimated_cost_usd=0.0234,
            student_rating=5,
            auto_quality_score=0.88,
            flagged_for_review=True,
        )
        assert d.attempt_id == aid
        assert d.resolution == Resolution.Socratic유도성공
        assert d.total_turns == 6
        assert d.model_used == "claude-opus-4-7"
        assert d.estimated_cost_usd == pytest.approx(0.0234)
        assert d.student_rating == 5
        assert d.auto_quality_score == pytest.approx(0.88)
        assert d.flagged_for_review is True

    def test_enum_value_serialization_korean(self) -> None:
        """use_enum_values → resolution 한글 값 보존."""
        d = Dialogue(resolution=Resolution.학생자력해결)
        assert d.model_dump()["resolution"] == "학생자력해결"

    def test_student_rating_too_high_rejected(self) -> None:
        """student_rating은 1-5 — 6 거부."""
        with pytest.raises(ValidationError):
            Dialogue(student_rating=6)

    def test_student_rating_too_low_rejected(self) -> None:
        """student_rating은 1-5 — 0 거부."""
        with pytest.raises(ValidationError):
            Dialogue(student_rating=0)

    def test_auto_quality_score_too_high_rejected(self) -> None:
        """auto_quality_score는 0-1(보수 설정) — 1 초과 거부."""
        with pytest.raises(ValidationError):
            Dialogue(auto_quality_score=1.2)

    def test_estimated_cost_negative_rejected(self) -> None:
        """estimated_cost_usd는 ge=0(비용) — 음수 거부."""
        with pytest.raises(ValidationError):
            Dialogue(estimated_cost_usd=-0.01)

    def test_total_tokens_negative_rejected(self) -> None:
        """total_tokens는 ge=0(개수) — 음수 거부."""
        with pytest.raises(ValidationError):
            Dialogue(total_tokens=-1)

    def test_total_turns_negative_rejected(self) -> None:
        """total_turns는 ge=0(개수) — 음수 거부."""
        with pytest.raises(ValidationError):
            Dialogue(total_turns=-1)

    def test_invalid_resolution_rejected(self) -> None:
        """resolution에 잘못된 enum 값 거부."""
        with pytest.raises(ValidationError):
            Dialogue(resolution="존재하지않는결과")  # type: ignore[arg-type]

    def test_extra_forbidden(self) -> None:
        """extra='forbid'."""
        with pytest.raises(ValidationError):
            Dialogue(bogus="x")  # type: ignore[call-arg]


# ──────────────────────────────────────────────────────────────────────
# DialogueTurn — required(turn_order)·범위·enum·JSONB·개인정보 필드
# ──────────────────────────────────────────────────────────────────────
class TestDialogueTurn:
    def test_valid_with_required_turn_order(self) -> None:
        """turn_order(NOT NULL) 필수 — 그것만으로 생성, turn_id 자동."""
        t = DialogueTurn(turn_order=1)
        assert isinstance(t.turn_id, uuid.UUID)
        assert t.turn_order == 1
        assert t.dialogue_id is None
        assert t.role is None
        assert t.content is None
        assert t.socratic_strategy is None
        assert t.image_uri is None
        assert t.image_analysis is None

    def test_full_fields_roundtrip(self) -> None:
        """전 필드 채운 턴 — 값·JSONB 보존(특성 #8/#18/#21)."""
        did = uuid.uuid4()
        concept = uuid.uuid4()
        now = datetime.now(timezone.utc)
        t = DialogueTurn(
            dialogue_id=did,
            turn_order=3,
            spoken_at=now,
            role=TurnRole.assistant,
            content="조건 (가)를 수식으로 표현해볼까요?",
            content_type=ContentType.혼합,
            socratic_strategy=SocraticStrategy.조건확인,
            targeted_step=2,
            targeted_concept_id=concept,
            student_intent=StudentIntent.질문,
            student_understanding_signal=0.4,
            image_uri="minio://turn/xyz.png",
            image_analysis={"detected": "f(x)=x^2", "model": "qwen3-vl"},
        )
        assert t.dialogue_id == did
        assert t.turn_order == 3
        assert t.role == TurnRole.assistant
        assert t.content == "조건 (가)를 수식으로 표현해볼까요?"
        assert t.content_type == ContentType.혼합
        assert t.socratic_strategy == SocraticStrategy.조건확인
        assert t.targeted_step == 2
        assert t.targeted_concept_id == concept
        assert t.student_intent == StudentIntent.질문
        assert t.student_understanding_signal == pytest.approx(0.4)
        assert t.image_analysis["model"] == "qwen3-vl"

    def test_enum_value_serialization_korean(self) -> None:
        """use_enum_values → 한글/영어 enum 값 보존(role 영어·strategy 한글)."""
        t = DialogueTurn(
            turn_order=1,
            role=TurnRole.student,
            content_type=ContentType.수식,
            socratic_strategy=SocraticStrategy.반례제시,
            student_intent=StudentIntent.답시도,
        )
        dumped = t.model_dump()
        assert dumped["role"] == "student"
        assert dumped["content_type"] == "수식"
        assert dumped["socratic_strategy"] == "반례제시"
        assert dumped["student_intent"] == "답시도"

    def test_turn_order_required(self) -> None:
        """turn_order은 INTEGER NOT NULL → required — 누락 거부."""
        with pytest.raises(ValidationError):
            DialogueTurn()  # type: ignore[call-arg]

    def test_turn_order_zero_rejected(self) -> None:
        """turn_order은 ge=1(1부터) — 0 거부."""
        with pytest.raises(ValidationError):
            DialogueTurn(turn_order=0)

    def test_targeted_step_zero_rejected(self) -> None:
        """targeted_step은 ge=1(단계 번호) — 0 거부."""
        with pytest.raises(ValidationError):
            DialogueTurn(turn_order=1, targeted_step=0)

    def test_understanding_signal_too_high_rejected(self) -> None:
        """student_understanding_signal은 0-1(보수 설정) — 1 초과 거부."""
        with pytest.raises(ValidationError):
            DialogueTurn(turn_order=1, student_understanding_signal=1.5)

    def test_invalid_role_rejected(self) -> None:
        """role에 잘못된 enum 값 거부."""
        with pytest.raises(ValidationError):
            DialogueTurn(turn_order=1, role="존재하지않는화자")  # type: ignore[arg-type]

    def test_extra_forbidden(self) -> None:
        """extra='forbid'."""
        with pytest.raises(ValidationError):
            DialogueTurn(turn_order=1, bogus="x")  # type: ignore[call-arg]
