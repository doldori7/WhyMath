"""렌더 계층 값 객체 — RenderContext(중립 입력)·RenderBlock·RenderedUnit(산출·03c §2).

교수법 어댑터(`adapter.py`)의 입출력 타입이다. **RenderContext는 중립 원시값만** 담는다 —
L4 타입(교수법 결정·학습자 상태 객체)을 import하지 않는다. `l3/render`는 7계층 단방향 계약상
l4/l5/l6/api를 import할 수 없기 때문이다(역방향 금지·import-linter). L4 Runtime Pedagogy
Selector(04d)가 *자기* 상태를 이 중립 표면(숙달도 라벨·Polya 단계 라벨·오개념 id)으로 투영해
넘긴다 — 어댑터는 결정을 내리지 않고 이미 고른 전략을 얇게 렌더할 뿐이다(관심사 분리).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from whymath_backend.l3.pregenerate.models import ValidationSignal
from whymath_backend.schema.enums import PedagogyStrategy


class RenderContext(BaseModel):
    """어댑터 렌더 입력 컨텍스트 — **중립 원시값만**(L4 타입 미참조).

    L4 selector가 학습자 상태(BKT 숙달도·Polya 단계·반응형 오개념 후보)를 라벨/문자열로 투영해
    넘긴다. 어댑터는 이 값을 *텍스트 개인화*에만 쓰고 구조(블록 종류·개수)는 바꾸지 않는다
    (같은 ctx에서 "숫자만 다른 두 DSL"이 같은 구조를 내는 거버넌스 대칭의 전제).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    mastery_level: str | None = Field(
        default=None, description="숙달도 라벨(예 'low'|'mid'|'high')·중립 문자열(L4 투영)"
    )
    polya_stage: str | None = Field(
        default=None, description="Polya 단계 라벨(중립 문자열·L4 투영)"
    )
    misconception_ids: tuple[str, ...] = Field(
        default=(), description="반응형 오개념 후보 id(본문 미보유·id 참조만)"
    )


class RenderBlock(BaseModel):
    """렌더 산출의 구조화 블록 하나 — 종류(kind) + 본문(text).

    `kind`는 블록의 교수학적 역할(예 'definition'·'question'·'problem'·'substitution')이고, `text`는
    렌더러-중립 본문이다. 화면 최종 렌더(Flutter·웹)는 L5가 kind별로 스타일링한다(표현≠의미).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: str = Field(..., description="블록의 교수학적 역할 라벨")
    text: str = Field(..., description="렌더러-중립 본문(LaTeX/구조 태그 포함 가능)")


class RenderedUnit(BaseModel):
    """어댑터 렌더 산출 — 전략 + 블록들 + 검증 신호(03c §2 어댑터 계약 반환형).

    `validation_signal`은 관례상 **None ⇒ clean/검증 통과분**(학생 노출 가능)이다. 렌더 후 검증
    (예 완전예제/문제형의 정답 SymPy 검증)이 실패하면 `ValidationSignal`을 실어 노출을 막는다
    (미검증 노출 금지·03c §3·CLAUDE.md "검증 없이 학생 제공 금지").
    """

    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    strategy: PedagogyStrategy = Field(..., description="이 산출을 만든 교수법 전략")
    blocks: tuple[RenderBlock, ...] = Field(..., description="구조화 렌더 블록들(순서 유의)")
    validation_signal: ValidationSignal | None = Field(
        default=None, description="검증 신호 — None이면 clean(노출 가능)·아니면 미검증(노출 차단)"
    )


__all__ = ["RenderBlock", "RenderContext", "RenderedUnit"]
