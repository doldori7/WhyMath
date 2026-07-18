"""이벤트 페이로드 타입별 계약 거버넌스 게이트 — invariant ⑫.

`event_data`가 자유 JSONB로 방치되던 것을 *생산 3종*(검산결과·힌트제공·시각화조작)에 대해
계약(`schema/event_data_contract.py`)으로 고정했다. 이 테스트는 그 계약이:
  1) 생산 3종을 빠짐없이 덮고(휴면 8종은 명시적 면제·분류 누락 0),
  2) 하네스가 실제로 읽는 키(passed·hint_level)를 포함하며,
  3) stray key(자유 JSONB의 씨앗)를 produce 좌석에서 거부하고,
  4) `시각화조작.payload` 내부 자유형은 의도적으로 보존하는지
를 고정한다 — 계약이 코드(생산자)와 드리프트하면 즉시 red.

`test_render_contract.py`(⑩)·`test_embedding_namespace_governance.py`(⑨)와 동형 —
계약 단일원 + 거버넌스 테스트 패턴.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from whymath_backend.schema.enums import EventType
from whymath_backend.schema.event_data_contract import (
    CONTRACT_EXEMPT_EVENT_TYPES,
    EVENT_DATA_CONTRACT,
    HintEventData,
    InteractionEventData,
    VerifyEventData,
    build_event_data,
)

# 코드가 실제로 event_data를 *쓰는* EventType — 탐사(producer 전수 grep)로 확정한 3종.
# (api/coach.py: 검산결과·힌트제공, api/interactions.py: 시각화조작.)
_PRODUCED = {EventType.검산결과, EventType.힌트제공, EventType.시각화조작}


def test_contract_covers_exactly_the_produced_types() -> None:
    """계약 키 == 실제 생산 3종(누락·잉여 0) — 단일 진실원 완전성."""
    assert set(EVENT_DATA_CONTRACT) == _PRODUCED


def test_every_event_type_is_classified() -> None:
    """계약 ∪ 면제 == 전체 EventType — 분류 누락 0(새 EventType 추가 시 어느 한쪽에 편입 강제)."""
    assert set(EVENT_DATA_CONTRACT) | CONTRACT_EXEMPT_EVENT_TYPES == set(EventType)
    # 겹침 0 — 한 타입이 계약이면서 동시에 면제일 수 없다.
    assert set(EVENT_DATA_CONTRACT).isdisjoint(CONTRACT_EXEMPT_EVENT_TYPES)


def test_dormant_types_are_exempt_not_contracted() -> None:
    """휴면 8종(문제읽기…답입력)은 면제 집합 — 계약으로 구속하지 않는다(premature 회피)."""
    dormant = {
        EventType.문제읽기,
        EventType.조건분석,
        EventType.그래프그리기,
        EventType.계산,
        EventType.지움,
        EventType.막힘,
        EventType.힌트요청,
        EventType.답입력,
    }
    assert dormant == CONTRACT_EXEMPT_EVENT_TYPES


def test_harness_consumed_keys_are_in_contract() -> None:
    """하네스가 읽는 활성 키(passed·hint_level)가 계약 필드에 존재 — 소비처↔계약 정합.

    `wh1_evaluation.py`가 `event_data['passed']`(지표 ①)·`event_data['hint_level']`(지표 ⑤)를
    읽는다. 이 키가 계약에서 빠지면 지표가 조용히 깨지므로 여기서 고정한다.
    """
    assert "passed" in VerifyEventData.model_fields
    assert "hint_level" in HintEventData.model_fields


def test_verify_normalizes_missing_error_kind() -> None:
    """`검산결과`를 passed만 주면 error_kind·mode·persona=None으로 정규화 — 드리프트 무해화.

    S3-03: 계약에 mode/persona(선택 태그)가 추가돼 미지정 시 None으로 채워진다(mode-agnostic·
    기존 생산 경로 의미 불변).
    """
    data = build_event_data(EventType.검산결과, passed=True)
    assert data == {"passed": True, "error_kind": None, "mode": None, "persona": None}


def test_verify_full_shape() -> None:
    data = build_event_data(EventType.검산결과, passed=False, error_kind="arithmetic")
    assert data == {"passed": False, "error_kind": "arithmetic", "mode": None, "persona": None}


def test_verify_mode_persona_tag() -> None:
    """S3-03: 검산결과에 mode/persona 태그를 실으면 event_data에 그대로 보존(수능 세션 식별)."""
    data = build_event_data(EventType.검산결과, passed=True, mode="suneung", persona="A_일반고고3")
    assert data == {
        "passed": True,
        "error_kind": None,
        "mode": "suneung",
        "persona": "A_일반고고3",
    }


def test_hint_shape() -> None:
    assert build_event_data(EventType.힌트제공, hint_level=3) == {
        "hint_level": 3,
        "mode": None,
        "persona": None,
    }


def test_hint_mode_persona_tag() -> None:
    """S3-03: 힌트제공에 mode/persona 태그를 실으면 event_data에 그대로 보존(⑤⑧ mode-scoped)."""
    data = build_event_data(EventType.힌트제공, hint_level=2, mode="suneung")
    assert data == {"hint_level": 2, "mode": "suneung", "persona": None}


def test_interaction_envelope_shape() -> None:
    """`시각화조작` 봉투 5키 — 생산자(interactions.py)가 쓰던 키와 정확히 일치."""
    data = build_event_data(
        EventType.시각화조작,
        interaction="param_change",
        payload={"name": "a", "value": 2},
        client_at=123,
        concept_id="math.calculus.limit",
        scene_id="scene-1",
    )
    assert set(data) == {
        "interaction",
        "payload",
        "client_at",
        "concept_id",
        "scene_id",
    }
    assert data["payload"] == {"name": "a", "value": 2}


def test_interaction_payload_stays_free() -> None:
    """봉투는 계약이지만 내부 payload는 자유형(조작 종류별 상이) — 임의 중첩 dict 허용."""
    model = InteractionEventData(
        interaction="surface_range",
        payload={"axis": "x", "range": [-5, 5], "nested": {"deep": True}},
    )
    assert model.payload["nested"] == {"deep": True}


def test_interaction_optional_context_defaults() -> None:
    """concept_id·scene_id·client_at은 선택(약점개념 흐름 밖에선 없음) → None 기본."""
    data = build_event_data(EventType.시각화조작, interaction="param_play")
    assert data == {
        "interaction": "param_play",
        "payload": {},
        "client_at": None,
        "concept_id": None,
        "scene_id": None,
    }


@pytest.mark.parametrize(
    ("event_type", "payload"),
    [
        (EventType.검산결과, {"passed": True, "bogus": 1}),
        (EventType.힌트제공, {"hint_level": 2, "extra": "x"}),
        (EventType.시각화조작, {"interaction": "p", "unknown": True}),
    ],
)
def test_stray_keys_rejected(event_type: EventType, payload: dict[str, object]) -> None:
    """계약에 없는 키는 produce 좌석에서 거부(extra='forbid') — 자유 JSONB 드리프트 차단."""
    with pytest.raises(ValidationError):
        build_event_data(event_type, **payload)


def test_type_coercion_enforced() -> None:
    """passed는 bool·hint_level은 int — 타입 강제(잘못된 타입 거부)."""
    with pytest.raises(ValidationError):
        build_event_data(EventType.힌트제공, hint_level="셋")  # 숫자 아님


def test_dormant_type_is_not_a_build_target() -> None:
    """휴면 EventType으로 build_event_data 호출은 오용 → KeyError(생산 경로 없어야 함)."""
    with pytest.raises(KeyError):
        build_event_data(EventType.막힘, foo="bar")
