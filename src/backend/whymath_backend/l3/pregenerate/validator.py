"""사전생성 시드 검증 게이트 — Protocol + 최소 기본 구현.

설계 정본: MEMORY.md 2026-05-20 "고난도 검증·시드 품질 = Max-Claude". 슬라이스 1은
*최소 시드 위생*(비어있음·짧음·명백 오류 마커)만 본다. PRM·SymPy·Lean·LLM-judge는
후속 슬라이스(03 환각 방어 파이프라인). 본 게이트는 *시드 품질 위생*이지 학생 노출
경계가 아니다 — 학생 직접 노출 경계는 L4/L5 환각 방어가 책임진다(CLAUDE.md 금기).

검증 통과만 캐시에 적재된다 — 통과 못 한 시드는 *영원히 캐시에 안 들어가서* 런타임
이 그 요청에서 다시 provider를 호출하게 된다(즉, 실패는 안전한 폴백이지 노출 위험이
아니다).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from whymath_backend.l3.pregenerate.models import PregenItem


@runtime_checkable
class SeedValidator(Protocol):
    """사전생성 응답 검증 경계 — 통과 시 None, 실패 시 짧은 사유 문자열."""

    def validate(self, item: PregenItem, response: str) -> str | None:
        """응답을 검증한다. 통과 = `None`, 실패 = 사유 문자열(리포트·로그용)."""
        ...


class BasicSeedValidator:
    """최소 시드 위생 — 비어있음·최소 길이·명백 오류 마커. PRM 등은 후속.

    `min_length`는 *strip 후* 문자열 길이. `error_markers`는 응답에 포함되면 즉시
    탈락시키는 부분 문자열들(예: 모델이 토해낸 명시적 오류 표시). 케이스 무시.
    """

    def __init__(
        self,
        *,
        min_length: int = 1,
        error_markers: tuple[str, ...] = (),
    ) -> None:
        if min_length < 0:
            raise ValueError("min_length는 0 이상이어야 합니다")
        self._min_length = min_length
        # 정규화는 1회 — 비교는 lowercase로
        self._error_markers = tuple(m.lower() for m in error_markers if m)

    def validate(self, item: PregenItem, response: str) -> str | None:
        """비어있음·짧음·오류 마커 검사 — 통과면 None, 실패면 사유."""
        stripped = response.strip()
        if not stripped:
            return "empty response"
        if len(stripped) < self._min_length:
            return f"response too short (<{self._min_length} chars after strip)"
        if self._error_markers:
            lowered = stripped.lower()
            for marker in self._error_markers:
                if marker in lowered:
                    return f"error marker present: {marker!r}"
        return None
