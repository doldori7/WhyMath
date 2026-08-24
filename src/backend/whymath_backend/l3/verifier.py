"""통합 수학 검증기 v2 contract — S4-52 설계 산출물(stub).

S4-13 v1이 확률 유한 전수형을 닫았다면, v2는 검증 진입점을 단일화하고 SymPy 불가 영역을
도메인 verifier 플러그인으로 확장하는 contract다. 이 모듈은 현재 **스켈레톤**이며
구현체는 하위 슬라이스 태스크(S4-52-1 ~ S4-52-N)에서 채운다.

계층: L3 지역. L4만 호출한다(import-linter). DB·LLM 0 — 필요한 경우 cross_verify를
주입받아 잔여 축을 검증.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from whymath_backend.harness.corpus_audit_eval import AuditLabel
from whymath_backend.l3.cross_verify import CrossVerifier
from whymath_backend.l3.finite_probability import (
    verify_finite_count,
    verify_finite_probability,
)
from whymath_backend.l3.verification_tier import VerificationTier
from whymath_backend.l3.verify_answer import AnswerVerdict

__all__ = [
    "ProblemVerifyInput",
    "VerificationVerdict",
    "Verifier",
]


class ProblemVerifyInput(BaseModel):
    """검증에 필요한 최소 입력 — `ProblemDSL` 전체가 아니라 verify 절 계약만 노출.

    L3 내부 타입이다. `schema/problem.py`의 `Problem`을 직접 받지 않아 계층 의존을
    최소화한다.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    slug: str
    question_text: str
    answer: str
    answer_kind: str
    conditions: str
    answer_explanation: str = ""
    authored_by: str = "unknown"


class VerificationVerdict(BaseModel):
    """통합 verifier의 최종 판정 — state + 등급 + 증명/잔여 축 + 감사 라벨.

    `state`는 3상태. `tier`는 "증명된 축의 집합"을 표현. `machine_axes`는 기계가 닫은 축,
    `residual_axes`는 기계가 닫지 못한 축(교차검증/인간 폴백 대상).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    state: Literal["pass", "fail", "unverifiable"] = Field(
        description="최종 판정 — pass(기계+잔여 ok), fail(결함), unverifiable(측정 불가)."
    )
    tier: VerificationTier = Field(description="검증 등급 — '증명된 축의 집합'을 표현.")
    machine_axes: tuple[str, ...] = Field(
        default_factory=tuple,
        description="기계로 닫힌 축 목록.",
    )
    residual_axes: tuple[str, ...] = Field(
        default_factory=tuple,
        description="기계가 닫지 못한 잔여 축 목록.",
    )
    reason: str | None = Field(
        default=None,
        description="fail/unverifiable 사유(학생 비노출).",
    )
    audit_labels: list[AuditLabel] = Field(
        default_factory=list,
        description="잔여 교차검증 감사 라벨.",
    )


# 기존 S4-13 v1 verifier를 래핑하는 디스패치 테이블.
# 신규 도메인은 하위 슬라이스에서 확장 — 키 중복은 구성 시점에 거부.
DomainVerifier = Callable[[str, str], tuple[AnswerVerdict, tuple[str, ...]]]


def _verify_finite_probability_pair(
    conditions: str, answer: str
) -> tuple[AnswerVerdict, tuple[str, ...]]:
    """finite_probability → (AnswerVerdict, residual_axes)."""
    verdict = verify_finite_probability(conditions, answer)
    residual = (
        "문발↔형식모델 정합",
        "등확률 가정",
    )
    return verdict, residual


def _verify_finite_count_pair(
    conditions: str, answer: str
) -> tuple[AnswerVerdict, tuple[str, ...]]:
    """finite_count → (AnswerVerdict, residual_axes)."""
    verdict = verify_finite_count(conditions, answer)
    residual = (
        "문발↔형식모델 정합",
        "등확률 가정",
    )
    return verdict, residual


# NOTE: S4-52-1 구현 시 _VERIFIERS_V2에 geometric_discrete / statistical_claim 등 추가.
#       이 스켈레톤은 기존 v1 도메인만 등록해 하위호환을 유지.
_VERIFIERS_V2: dict[str, DomainVerifier] = {
    "finite_probability": _verify_finite_probability_pair,
    "finite_count": _verify_finite_count_pair,
}


class Verifier:
    """통합 verifier v2 — 도메인 디스패치 + 잔여 축 식별 + 교차검증 연결.

    현재는 **스켈레톤**으로, 기존 finite_probability/finite_count만 실제 검증하고
    나머지 answer_kind는 `unverifiable`로 회피한다. 하위 슬라이스에서 플러그인을
    채운다.
    """

    def __init__(self, *, cross_verifier: CrossVerifier | None = None) -> None:
        self._cross_verifier = cross_verifier

    async def verify(self, problem: ProblemVerifyInput) -> VerificationVerdict:
        """통합 검증 진입점.

        1. answer_kind로 도메인 verifier 디스패치.
        2. 기계 검증 결과 + 잔여 축 획득.
        3. fail이면 즉시 fail.
        4. unverifiable이면서 잔여 축이 없으면 unverifiable.
        5. 잔여 축이 있으면 cross_verifier가 있을 때만 교차검증(설계 단계에서는 NO-OP).
        """
        verifier = _VERIFIERS_V2.get(problem.answer_kind)
        if verifier is None:
            return VerificationVerdict(
                state="unverifiable",
                tier=VerificationTier.MACHINE_SAMPLED,
                reason=f"answer_kind={problem.answer_kind!r}에 등록된 verifier가 없음(v2 미구현)",
            )

        verdict, residual_axes = verifier(problem.conditions, problem.answer)

        if verdict.state == "fail":
            return VerificationVerdict(
                state="fail",
                tier=VerificationTier.MACHINE_SAMPLED,
                machine_axes=("수치/조건 검산",),
                residual_axes=residual_axes,
                reason=verdict.reason or "기계 검증 실패",
            )

        if verdict.state == "unverifiable":
            if not residual_axes:
                return VerificationVerdict(
                    state="unverifiable",
                    tier=VerificationTier.MACHINE_SAMPLED,
                    reason=verdict.reason or "기계 검증 불가",
                )
            return VerificationVerdict(
                state="unverifiable",
                tier=VerificationTier.MACHINE_SAMPLED,
                residual_axes=residual_axes,
                reason=verdict.reason or "기계 검증 불가, 잔여 축 남음",
            )

        # pass — 잔여 축이 없으면 MACHINE_EXHAUSTIVE, 있으면 잔여 교차검증 필요.
        # NOTE: S4-52-3에서 VerificationTier 개편 시 FINITE_EXHAUSTIVE로 세분화.
        if not residual_axes:
            return VerificationVerdict(
                state="pass",
                tier=VerificationTier.MACHINE_EXHAUSTIVE,
                machine_axes=("유한 전수 검증",),
            )

        # 설계 단계: cross_verifier가 주입되지 않으면 unverifiable로 보수 회피.
        if self._cross_verifier is None:
            return VerificationVerdict(
                state="unverifiable",
                tier=VerificationTier.MACHINE_SAMPLED,
                machine_axes=("유한 전수 검증",),
                residual_axes=residual_axes,
                reason="잔여 축이 있으나 cross_verifier가 주입되지 않음(v2 스켈레톤)",
            )

        # TODO(S4-52-2): ResidueSubject 구성 후 cross_verifier.verify() 호출.
        #   현재는 설계 단계이므로 잔여 축을 사유로 unverifiable로 회피.
        return VerificationVerdict(
            state="unverifiable",
            tier=VerificationTier.MACHINE_SAMPLED,
            machine_axes=("유한 전수 검증",),
            residual_axes=residual_axes,
            reason="잔여 교차검증은 S4-52-2 구현 후 활성화",
        )
