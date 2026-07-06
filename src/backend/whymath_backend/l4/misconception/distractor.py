"""객관식 distractor op-code 카탈로그 — *추상 오류연산* → 오개념 매핑(슬108 그라운드워크).

객관식(수능 페르소나 A) 문항의 *오답 선지*(distractor)는 보통 *특정 오개념*이 만들어낸다.
이 모듈은 그 관계를 **추상 오류연산 op-code**로 카탈로그화한다 — 즉 "어떤 잘못된 연산을 적용하면
이 오답 선지가 나오는가"를 일반화한 단위다. 이를 통해 ① 우리 *자체 동등문제*의 오답 선지를
*생성*하거나 ② 학생이 고른 오답 선지를 오개념으로 *역추적*할 수 있다.

**저작권 레일(CLAUDE.md 우선순위 #2·`schema/problem.py` 선지 검증자와 정합)**: op-code는
*추상 오류연산*(예: "거듭제곱을 각 항에 분배")이지 평가원·EBS·교과서의 *선지 본문* 복제가 아니다.
특정 시험의 선지 텍스트는 담지 않는다 — 재사용 가능한 *일반 연산 서술*만 담는다.

**범위 정직(스캐폴드)**: 이 슬라이스는 *카탈로그 + 모델 + 무결성 검증*까지다. `Problem` 선지별
메타데이터 스키마·객관식에서 *실시간 distractor→진단* 결선은 *모달리티 추가*라 후속으로 보류한다
(`EdgeType.TRIGGERS_DISTRACTOR`는 같은 슬라이스에서 어휘만 선언). `misconception_id`는 정본
오개념 카탈로그(`catalog.CATALOG_BY_ID`)의 키여야 하며, `DistractorOpCode` 생성 시점에 검증한다
(미등록 id면 즉시 실패 — fail-fast).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from whymath_backend.l4.misconception.catalog import CATALOG_BY_ID
from whymath_backend.l4.misconception.models import MisconceptionDomain


class DistractorOpCode(BaseModel):
    """오답 선지 생성/역추적 *추상 오류연산* 단위 — 정본 오개념에 매핑(불변·frozen).

    `operation`은 *일반 오류연산 서술*(특정 시험 선지 본문 아님·저작권). `misconception_id`는
    이 오답 선지를 유발하는 오개념(`catalog.CATALOG_BY_ID` 키)이며 생성 시 검증한다. `domain`은
    조직화용이고 연결된 오개념의 `domain`과 일치해야 한다(테스트가 정합 검증).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(
        description="추상 오류연산 op-code — kebab-case(예: 'power-distributed-no-cross-term').",
    )
    name_kr: str = Field(description="짧은 한국어 라벨(예: '제곱 분배(교차항 누락)').")
    domain: MisconceptionDomain = Field(description="대상 영역 — 연결 오개념의 domain과 일치.")
    operation: str = Field(
        description=(
            "오답 선지를 *생성/역추적*하는 추상 오류연산 서술. 특정 시험의 선지 본문이 아니라 "
            "재사용 가능한 일반 연산만 담는다(저작권 레일)."
        ),
    )
    misconception_id: str = Field(
        description="이 distractor가 유발하는 오개념 — `catalog.CATALOG_BY_ID` 키(생성 시 검증).",
    )

    @field_validator("misconception_id")
    @classmethod
    def _known_misconception(cls, value: str) -> str:
        """미등록 오개념 id를 *생성 시점*에 거부 — distractor는 항상 정본 오개념을 가리킨다."""
        if value not in CATALOG_BY_ID:
            raise ValueError(f"미등록 misconception_id: {value!r} — catalog.CATALOG_BY_ID에 없음.")
        return value


# 시드 op-code(8종·도메인 교차) — 각 항목은 정본 카탈로그의 실재 오개념을 가리킨다. 추상 오류연산만
# 담고 특정 시험 선지 본문은 담지 않는다(저작권). S2-p: 이차방정식 근 선택·부호 반전 2종 +
# 시드 코퍼스(wm-quad-eq-root-count-mc)가 참조하던 미등록 op-code(root-loss) 1종 상환.
# 확장은 후속 data 슬라이스(전수 코퍼스).
DISTRACTOR_CATALOG: tuple[DistractorOpCode, ...] = (
    DistractorOpCode(
        id="power-distributed-no-cross-term",
        name_kr="제곱 분배(교차항 누락)",
        domain="대수",
        operation="(a+b)²을 a²+b²로 전개해 교차항 2ab를 누락한 값을 오답 선지로 만든다.",
        misconception_id="distribution-over-power",
    ),
    DistractorOpCode(
        id="inequality-no-sign-flip",
        name_kr="부등식 부호 미반전",
        domain="대수",
        operation=(
            "부등식 양변에 음수를 곱/나눌 때 부등호 방향을 " "그대로 둔 값을 오답 선지로 만든다."
        ),
        misconception_id="sign-flip-in-inequality",
    ),
    DistractorOpCode(
        id="chain-rule-omit-inner",
        name_kr="연쇄법칙 내부 도함수 누락",
        domain="미적분",
        operation=(
            "합성함수 f(g(x))를 미분할 때 내부 도함수 g'(x)를 "
            "곱하지 않은 값을 오답 선지로 만든다."
        ),
        misconception_id="chain-rule-inner-derivative-omitted",
    ),
    DistractorOpCode(
        id="mean-reported-for-median",
        name_kr="중앙값 대신 평균",
        domain="확률통계",
        operation="중앙값을 묻는 문항에 평균을 계산한 값을 오답 선지로 만든다.",
        misconception_id="mean-vs-median",
    ),
    DistractorOpCode(
        id="sine-distributed-over-sum",
        name_kr="사인 합 분배",
        domain="삼각함수",
        operation="sin(α+β)를 sinα+sinβ로 분배한 값을 오답 선지로 만든다.",
        misconception_id="sine-distributes-over-sum",
    ),
    # ── S2-p: 이차방정식 근 선택 문제(동등문제 객관식 변형)의 결정론 distractor 3종 ──
    DistractorOpCode(
        id="select-opposite-root",
        name_kr="반대 근 선택",
        domain="대수",
        operation=(
            "큰(작은) 근을 요구하는 문항에서 요구되지 않은 반대쪽 근의 값을 " "오답 선지로 만든다."
        ),
        misconception_id="opposite-root-selected",
    ),
    DistractorOpCode(
        id="factor-sign-flip-root",
        name_kr="인수 근 부호 반전",
        domain="대수",
        operation=(
            "(x-a)=0 인수에서 근을 x=-a로 읽어 부호가 반전된 근의 값을 " "오답 선지로 만든다."
        ),
        misconception_id="factor-sign-flip",
    ),
    DistractorOpCode(
        id="root-loss-divide-by-variable",
        name_kr="변수 나눗셈 근 손실",
        domain="대수",
        operation=(
            "방정식 양변을 변수 x로 나눠 x=0 근을 잃은 결과(근의 개수·근 목록)를 "
            "오답 선지로 만든다."
        ),
        misconception_id="root-loss-by-dividing",
    ),
)
"""시드 distractor op-code 카탈로그(8종·도메인 교차) — 정본 오개념 실재 키만 참조(생성 시 검증).

스캐폴드 범위: 카탈로그·모델·무결성까지. 실시간 진단 결선·선지 메타 스키마는
후속(모듈 docstring 참조)."""


DISTRACTOR_BY_ID: dict[str, DistractorOpCode] = {d.id: d for d in DISTRACTOR_CATALOG}
"""op-code id로 O(1) 조회 — 역추적·텔레메트리에서 distractor op-code를 참조할 때."""


__all__ = ["DISTRACTOR_BY_ID", "DISTRACTOR_CATALOG", "DistractorOpCode"]
