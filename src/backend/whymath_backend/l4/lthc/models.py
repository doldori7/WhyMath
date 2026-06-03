"""LTHC — Low Threshold High Ceiling 모델·인터페이스.

`docs/architecture/04_pedagogy_engine.md` §"LTHC"(L117-119) 정본:
    NRICH 원칙. 동일 task를 학생 수준에 맞춰 진입점·확장 조정.

설계 분리:
- *진입점*(low threshold): 어떤 학생이든 *시작*할 수 있게 하는 단순화·시각화·작은 사례.
- *확장*(high ceiling): 숙달한 학생이 *더 깊이* 갈 수 있게 하는 일반화·변형·증명.
- *비계*(scaffolds): 막힘 상황에서 제공할 보조 발화(중간 수준 공통).

세 축은 *직교*다 — 한 학생에게 동시에 셋 다 제공 가능(다만 강조 비중이 다름). L4는 *결정*
계층이라 *어떤 후보가 적절한가*만 반환; 실제 노출 UI는 L5 책임.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

MasteryLevel = Literal["초보", "발전 중", "숙달"]
"""숙달도 라벨 — `docs/prompts/socratic_template.md` system prompt §"숙달도 라벨" 정본 3종.

L2 학습자 모델의 BKT/DKT 숙달도(0~1)를 *교수학 라벨*로 매핑한 결과. 정본 임계값은
socratic_template에 명시되지 않아 호출자(L2 연계 슬라이스) 책임으로 둔다.
"""


class LthcAdaptation(BaseModel):
    """단계·숙달도에 대응하는 LTHC 조정안.

    `entry_suggestions`는 낮은 진입(작은 사례·시각화 등 — 모든 수준 학생이 시작 가능),
    `extensions`는 높은 천장(일반화·변형 — 숙달 학생용), `scaffolds`는 막힘 시 보조 발화.
    각 항목은 *학생에게 보일 수 있는 한국어 발화*(직접 사용 가능 — 추가 어셈블리 불필요).
    """

    model_config = ConfigDict(extra="forbid")

    mastery_level: MasteryLevel = Field(description="이 조정안이 겨냥한 숙달도.")
    entry_suggestions: tuple[str, ...] = Field(
        default_factory=tuple,
        description=(
            "낮은 진입 후보(low threshold) — 작은 사례·시각화·유사 회상. "
            "`docs/prompts/polya_4step.md` Stage 2 정본 어구 기반."
        ),
    )
    extensions: tuple[str, ...] = Field(
        default_factory=tuple,
        description="높은 천장 후보(high ceiling) — 일반화·변형·증명·다른 풀이.",
    )
    scaffolds: tuple[str, ...] = Field(
        default_factory=tuple,
        description="비계(scaffold) — 막힘 시 보조 발화(중간 수준 공통).",
    )
