"""이벤트 페이로드 타입별 계약 단일 진실원 — invariant ⑫("event_data 자유 JSONB 금지·타입별 계약").

`AttemptEvent.event_data`는 물리적으론 `dict[str, Any]` JSONB지만, *생산되는* EventType은
페이로드 모양이 계약으로 고정돼야 한다(자유형 방치 시 오타·키 드리프트가 조용히 축적 →
분석 소비처가 깨진다). 이 모듈이 그 계약의 *단일 출처*다 — `render_contract`·`notation_contract`
선례(계약 단일원 + 거버넌스 테스트)를 백엔드 내부(교차언어 소비처 0이라 JSON golden 대신
Python 네이티브)로 실현한다.

경계(의도적 비구속):
- **휴면 8종**(문제읽기·조건분석·그래프그리기·계산·지움·막힘·힌트요청·답입력)은 생산자가
  아직 0이라 페이로드 모양이 미지 → 계약으로 구속하지 않는다(`_CONTRACT_EXEMPT`, premature 회피).
- **`시각화조작.payload`**(내부)는 조작 종류별로 달라 자유형을 *의도적으로* 유지한다 —
  봉투(interaction·payload·client_at·concept_id·scene_id)만 계약하고 내부는 열어 둔다.

강제 지점: 생산자(`api/coach.py`·`api/interactions.py`)가 `build_event_data`를 경유해 dict를
만든다 → extra="forbid" 모델이 stray key를 즉시 거부하므로 produce 좌석에서 드리프트가
구조적으로 불가능해진다(런타임 재작성·validator·DB 제약 없이 seam 1곳에서 차단).
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from whymath_backend.schema.enums import EventType


class _EventPayload(BaseModel):
    """계약 페이로드 공통 베이스 — stray key 금지(자유 JSONB 차단의 핵심)."""

    model_config = ConfigDict(extra="forbid")


class VerifyEventData(_EventPayload):
    """`검산결과` 페이로드 — WH-1 검산(verify) 결과·하네스 지표 ①(verify_pass_rate)의 입력.

    `passed`는 하네스가 실제로 읽는 유일 활성 키(`wh1_evaluation.py`)다. `error_kind`는
    거짓 수치관계의 종류(현재 write-only·향후 오개념 분석 입력)로 통과 시 None이다 →
    Optional. 픽스처가 `{passed}`만 써도 이 계약으로 정규화하면 `error_kind=None`이 되어
    관측된 드리프트가 무해화된다.

    S3-03(수능 MVP): `mode`·`persona`는 이 검산결과가 *어느 응용 모드/대상 페르소나* 세션에서
    나왔는지 표식하는 *선택* 태그다(예: mode="suneung"). 둘 다 미지정(None)이면 mode-agnostic
    (기존 동작 완전 불변)이라 기존 픽스처·라이브 이벤트가 무손상이다. 측정 계층
    (`wh1_evaluation`)이 `event_data->>'mode'`로 mode-scoped 집계를 낼 수 있게 하는 *데이터
    운반* 필드다(완전한 mode별 집계는 후속 S3-04). 값은 문자열(Literal/enum의 *값*)로 싣는다.
    """

    passed: bool = Field(..., description="거짓 수치관계 미적발(통과)=True·적발=False")
    error_kind: str | None = Field(
        default=None, description="적발된 오류 종류(통과 시 None·현재 write-only)"
    )
    mode: str | None = Field(
        default=None,
        description="응용 모드 태그(예: 'suneung'). None=미지정(mode-agnostic·기존 동작 불변).",
    )
    persona: str | None = Field(
        default=None,
        description="대상 페르소나 태그(예: 'A_일반고고3'). None=미지정(선택·후속 집계).",
    )


class HintEventData(_EventPayload):
    """`힌트제공` 페이로드 — AI가 *제공*한 노출량(supply)·하네스 지표 ⑤(도움 감소 곡선)의 입력.

    `hint_level`은 하네스가 읽는 유일 키다. 값 범위(1~4)는 계약이 아니라 *생산 로직*
    (`decision.hint_level`)의 책임 — 여기선 키·타입만 고정한다(범위 구속은 기존 동작 변경
    위험이라 도입하지 않음).

    S3-03(수능 MVP): `mode`·`persona`는 `VerifyEventData`와 *동형* 선택 태그다 — 이 힌트제공이
    어느 응용 모드/페르소나 세션에서 나왔는지 표식한다. 둘 다 None이면 mode-agnostic(기존 동작
    완전 불변). ⑤(도움 감소 곡선)·⑧(도달 깊이)의 mode-scoped 집계 데이터 운반용.
    """

    hint_level: int = Field(..., description="AI 제공 힌트 노출량(1~4·supply 신호)")
    mode: str | None = Field(
        default=None,
        description="응용 모드 태그(예: 'suneung'). None=미지정(mode-agnostic·기존 동작 불변).",
    )
    persona: str | None = Field(
        default=None,
        description="대상 페르소나 태그(예: 'A_일반고고3'). None=미지정(선택·후속 집계).",
    )


class InteractionEventData(_EventPayload):
    """`시각화조작` 페이로드 봉투 — L5 탐구적 조작의 컨텍스트(슬라이스 96-J).

    봉투 5키만 계약한다. 내부 `payload`는 조작 종류(param_change·surface_range 등)별로
    모양이 달라 `dict[str, Any]` 자유형을 *의도적으로* 유지한다 — 봉투 타이핑과 내부 자유는
    서로 다른 계층(수집 게이트는 봉투만 안다).
    """

    interaction: str = Field(..., description="조작 종류(InteractionEventIn.type)")
    payload: dict[str, Any] = Field(
        default_factory=dict, description="조작 세부(자유형·의도적 비구속)"
    )
    client_at: int | None = Field(default=None, description="클라이언트 발생 시각(epoch ms·선택)")
    concept_id: str | None = Field(default=None, description="탐구 중 개념(약점개념 scene·선택)")
    scene_id: str | None = Field(default=None, description="조작이 일어난 학습 장면(선택)")


# 생산되는 EventType → 페이로드 계약. 이 3종만 코드가 실제로 event_data를 쓴다.
EVENT_DATA_CONTRACT: dict[EventType, type[_EventPayload]] = {
    EventType.검산결과: VerifyEventData,
    EventType.힌트제공: HintEventData,
    EventType.시각화조작: InteractionEventData,
}

# 휴면(생산자 0) EventType — 페이로드 모양 미지라 계약에서 *의도적으로* 제외(premature 회피).
# 계약 ∪ 면제 == 전체 EventType 을 거버넌스 테스트가 고정한다(분류 누락 방지).
CONTRACT_EXEMPT_EVENT_TYPES: frozenset[EventType] = frozenset(
    et for et in EventType if et not in EVENT_DATA_CONTRACT
)


def build_event_data(event_type: EventType, **payload: Any) -> dict[str, Any]:
    """계약을 경유해 `event_data` dict를 만든다 — 생산 좌석의 단일 강제 지점.

    계약 있는 EventType은 해당 모델로 검증(extra="forbid" → stray key 거부·타입 강제)한 뒤
    `model_dump()`한다. 계약 없는(휴면) EventType에 이 함수를 쓰는 것은 오용이므로
    `KeyError`로 막는다(휴면 이벤트는 아직 생산 경로가 없어야 한다).
    """
    model = EVENT_DATA_CONTRACT.get(event_type)
    if model is None:
        raise KeyError(
            f"{event_type!r}는 계약이 없는(휴면) EventType — build_event_data 대상 아님. "
            f"생산 대상은 {sorted(e.value for e in EVENT_DATA_CONTRACT)} 뿐."
        )
    return model(**payload).model_dump()
