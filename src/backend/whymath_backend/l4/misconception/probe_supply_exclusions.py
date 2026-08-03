"""후보0 사유별 계상 — select_probe 공급 실패의 원인 관측 (REC-02 acceptance ④).

`l2/axis_exclusions.py`("조용한 탈락 금지" — ARCH-13)의 **패턴을 미러**한다(import는 하지
않는다 — 그 파일의 필드명은 L2 추천 좌석(약개념/선수개념 필터) 전용이라 오개념 공급 사유와
의미가 다르다). frozen dataclass + 배타적 int 카운터 + `total` property + "0건이면 무로그".

`select_probe`가 판별 문항을 못 찾는 이유는 최소 4갈래다 — 겨냥할 오개념 자체가 없거나(가설도
웜스타트도 0)·겨냥 mid가 코퍼스에 아예 안 태깅됐거나·태깅은 됐는데 난이도가 없거나·태깅+난이도는
있는데 학생이 전부 이미 풀었거나. 이 넷을 구분 못 하면 "판별 문항 없음"이 전부 같은 값으로
보여 침묵 실패가 된다(CLAUDE.md 절대 금기).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

# 좌석별 로거 네이밍은 `l2/axis_exclusions.py`(`whymath.l2`) 규약을 미러한다.
_LOGGER_PREFIX = "whymath.l4.misconception"


@dataclass(frozen=True, slots=True)
class ProbeSupplyExclusions:
    """select_probe 후보 공급 실패의 사유별 건수 — REC-02 ④(l2/axis_exclusions.py 패턴 미러).

    네 사유는 **서로 배타**다. 앞 셋(순서)은 조립 파이프라인 순서와 같다:
      no_target_mids(겨냥할 mid 자체가 없음 — 활성 가설도 outside_mids도 0) →
      untagged_mid(target mid는 있으나 코퍼스에 그 mid를 태깅한 문항이 0건) →
      missing_difficulty(태깅됐으나 difficulty_overall 없음) →
      fully_administered(태깅+난이도 있으나 전부 이미 응답함).

    `no_target_mids`가 1이면 나머지는 항상 0(조회 자체가 생략되므로). **`untagged_mid`은 mid
    개수를, 나머지 셋은 문항 개수를 센다** — 계상 단위가 다른 것은 의도다(mid 하나가 여러 문항에
    태깅될 수 있어 문항 단위로 세면 이중 계상되기 때문). 혼동하지 않도록 여기 명시한다.
    """

    no_target_mids: int = 0
    untagged_mid: int = 0
    missing_difficulty: int = 0
    fully_administered: int = 0

    @property
    def total(self) -> int:
        """제외된(=공급되지 못한) 건 총합(0이면 전량 정상 공급)."""
        return (
            self.no_target_mids
            + self.untagged_mid
            + self.missing_difficulty
            + self.fully_administered
        )


def log_probe_supply_exclusions(seat: str, exclusions: ProbeSupplyExclusions, *, kept: int) -> None:
    """제외가 1건이라도 있으면 구조화 로그 1줄 — 좌석명·카운트만(mid·문항id·학생식별 정보 0).

    제외가 0건이면 아무것도 남기지 않는다(정상 경로 소음 방지). `seat`은 `"wh1_primary"`/
    `"wh1_shadow"` 등 호출자 구분(로거 이름·메시지에 함께 실림).
    """
    if exclusions.total == 0:
        return
    logger = logging.getLogger(f"{_LOGGER_PREFIX}.{seat}")
    logger.info(
        "select_probe 후보 공급 제외 집계 seat=%s kept=%d no_target_mids=%d untagged_mid=%d "
        "missing_difficulty=%d fully_administered=%d",
        seat,
        kept,
        exclusions.no_target_mids,
        exclusions.untagged_mid,
        exclusions.missing_difficulty,
        exclusions.fully_administered,
    )


__all__ = ["ProbeSupplyExclusions", "log_probe_supply_exclusions"]
