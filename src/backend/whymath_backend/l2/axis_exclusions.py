"""추천 좌석의 *제외 사유* 집계·구조화 로그 — 조용한 탈락 금지 (ARCH-13).

L2 추천 좌석(약개념·선수개념)은 후보를 여러 단계로 걸러낸다. 걸러내는 것 자체는 옳다(검수 안 된
개념을 학생에게 밀지 않는다·약점 근거 없는 개념을 추천하지 않는다). 문제는 **왜 비었는지 알 수
없다**는 것이었다 — `reviewed_only=true`에서 후보 전량이 `continue`로 사라지면 호출자에겐 빈
리스트만 남고, "선수가 없다"·"전부 숙달했다"·"축이 안 맞아 전부 버려졌다"가 구분되지 않는다.

이 모듈은 그 세 갈래를 **카운트로 분리**해 관측 가능하게 만든다(CLAUDE.md "침묵 실패 금지"의 추천
좌석 판본 — 예외 삼키기와 같은 부류의 결함이다). 판정치는 프로세스 안에서 산출되며(SaaS 의존 0),
반환값과 로그 양쪽으로 나간다(이중 회계 관례).

개인정보(우선순위 #2): 로그에 싣는 것은 **좌석명과 정수 카운트뿐**이다 — concept code·user_id·
개념명·본문은 넣지 않는다(학생 식별 가능 정보 유출 금지).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

# 좌석별 로거 네이밍은 `l4/step_shadow.py`(`whymath.l4.step_shadow`) 규약을 미러한다.
_LOGGER_PREFIX = "whymath.l2"


@dataclass(frozen=True, slots=True)
class AxisExclusions:
    """추천 후보가 제외된 사유별 건수 — 어느 단계에서 몇 개가 왜 빠졌는가.

    세 사유는 **서로 배타**다(한 후보는 가장 먼저 걸린 사유 하나에만 계상된다). 순서는 파이프라인
    순서와 같다: 약점 필터 → 축 울타리 → 검수 게이팅.
    """

    off_atom_axis: int = 0  # 원자 축 밖(구 437 UC 등) — runtime truth=원자라 항상 제외
    not_reviewed: int = 0  # 축 안이지만 review_status != 'reviewed'(reviewed_only일 때만)
    not_weak: int = 0  # weak_only 필터 — 임계 이상(안 막힘) 또는 미측정(약점 근거 없음)

    @property
    def total(self) -> int:
        """제외된 후보 총합(0이면 아무도 안 빠졌다는 뜻)."""
        return self.off_atom_axis + self.not_reviewed + self.not_weak


def log_axis_exclusions(seat: str, exclusions: AxisExclusions, *, kept: int) -> None:
    """제외가 1건이라도 있으면 구조화 로그 1줄 — 좌석명·카운트만(식별 정보 0).

    제외가 0건이면 아무것도 남기지 않는다(정상 경로 소음 방지). `seat`은 로거 이름과 메시지에 함께
    실려 어느 추천 좌석의 집계인지 구분된다.
    """
    if exclusions.total == 0:
        return
    logger = logging.getLogger(f"{_LOGGER_PREFIX}.{seat}")
    logger.info(
        "추천 후보 제외 집계 seat=%s kept=%d off_atom_axis=%d not_reviewed=%d not_weak=%d",
        seat,
        kept,
        exclusions.off_atom_axis,
        exclusions.not_reviewed,
        exclusions.not_weak,
    )


__all__ = ["AxisExclusions", "log_axis_exclusions"]
