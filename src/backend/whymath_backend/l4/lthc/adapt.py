"""LTHC 적응 — Polya 단계 × 숙달도 → 진입점·확장·비계 조정안.

`docs/architecture/04_pedagogy_engine.md` §"LTHC"(L117-119) "동일 task를 학생 수준에 맞춰
진입점·확장 조정" 정본 구현.

설계:
- *진입점*(low threshold): "초보"에 강하게 노출. `polya_4step.md` Stage 2 정본 어구 인용.
- *확장*(high ceiling): "숙달"에 강하게 노출. NRICH 4종 — 일반화·변형·증명·다른 풀이.
- *비계*(scaffolds): "발전 중"에 강하게 노출. 중간 수준 공통.

스펙 분량 자체가 3줄(L117-119)로 매우 짧음 → 콘텐츠 라이브러리는 후속(pedagogy-designer
+ NRICH 라이선스 협력 후, `docs/strategy/partnerships.md` §"NRICH Cambridge MMP"). v1은
*Polya 정본 어구* + *NRICH 일반 원칙* 어구만 채택(허위 라벨링 회피).
"""

from __future__ import annotations

from whymath_backend.l4.lthc.models import LthcAdaptation, MasteryLevel
from whymath_backend.l4.models import PolyaStage

# 단계별 진입점 후보 — `docs/prompts/polya_4step.md` Stage 2(계획) L26-30 정본 어구.
# 모든 단계가 *낮은 진입*을 가질 수 있되, Polya 2단계(계획)에서 가장 풍부하게 등장.
_ENTRY_BY_STAGE: dict[PolyaStage, tuple[str, ...]] = {
    PolyaStage.UNDERSTAND: (
        "주어진 정보를 한 줄씩 적어볼래?",
        "그림이나 표로 정리해볼까?",
    ),
    PolyaStage.PLAN: (
        "비슷한 문제 본 적 있어?",
        "더 작은 경우부터 시작해볼까?",
        "그림·표·도형으로 정리하면 어때?",
    ),
    PolyaStage.EXECUTE: (
        "막힌 단계 직전까지만 다시 볼래?",
        "한 단계만 더 좁혀서 적어볼래?",
    ),
    PolyaStage.REVIEW: (
        "답이 합리적인지 검산해볼까?",
        "단위·크기 감각으로도 맞는지 봐줄래?",
    ),
}


# 단계별 확장 후보 — NRICH 원칙(일반화·변형·증명·다른 풀이). 4단계(검토)에서 가장 풍부.
# 1·2단계도 가벼운 확장 가능. 출처: NRICH Cambridge MMP(`partnerships.md` §"NRICH").
_EXTENSIONS_BY_STAGE: dict[PolyaStage, tuple[str, ...]] = {
    PolyaStage.UNDERSTAND: ("이 문제의 *핵심 구조*가 뭐 같아?",),
    PolyaStage.PLAN: (
        "여러 방법 중에 *왜* 그 방법을 골랐어?",
        "이 전략이 항상 통할까, 아니면 조건이 필요할까?",
    ),
    PolyaStage.EXECUTE: ("이 단계를 *일반화*하면 어떻게 돼?",),
    PolyaStage.REVIEW: (
        "이 발상을 *다른 문제*에도 쓸 수 있을까? (전이)",
        "조건을 *바꾸면* 결과는 어떻게 달라질까?",
        "*왜 항상* 그럴까? 증명할 수 있어?",
        "같은 결과에 *다른 풀이*로도 도달할 수 있어?",
    ),
}


# 단계별 비계 후보 — 막힘 시 보조 발화. 답을 주지 않는 가이드(CLAUDE.md 답 미루기 원칙).
_SCAFFOLDS_BY_STAGE: dict[PolyaStage, tuple[str, ...]] = {
    PolyaStage.UNDERSTAND: (
        "문제를 한 번 더 천천히 읽어볼까?",
        "어디부터 안 풀리는지 콕 짚어줄래?",
    ),
    PolyaStage.PLAN: (
        "지금 떠오르는 단어 하나만 적어볼래?",
        "비슷한 단원 문제 풀었던 게 있을까?",
    ),
    PolyaStage.EXECUTE: (
        "어디서 막혔는지 같이 봐줄게.",
        "직전 단계가 맞다고 가정하고, 다음 *한 줄*만 시도해볼래?",
    ),
    PolyaStage.REVIEW: ("전체 흐름을 *세 줄*로 요약해줄래?",),
}


# 숙달도별 *축 강조* — LTHC 핵심(동일 task의 진입·확장을 학생 수준에 맞춰 조정).
# 초보=진입+비계(천장 무리), 숙달=확장(진입은 자명), 발전 중=균형(소량씩).
_LEVEL_AXES: dict[MasteryLevel, tuple[bool, bool, bool]] = {
    # (entry_on, extension_on, scaffold_on)
    "초보": (True, False, True),
    "숙달": (False, True, False),
    "발전 중": (True, True, True),
}


def adapt_lthc(
    polya_stage: PolyaStage,
    mastery_level: MasteryLevel,
) -> LthcAdaptation:
    """단계·숙달도 → 진입점·확장·비계 후보 집합 — LTHC 적응.

    숙달도가 *어떤 축을 켜는가*를 결정한다:
    - 초보 → 진입점·비계 후보 노출, 확장은 비공(천장 강요 회피).
    - 숙달 → 확장 후보 노출, 진입·비계는 비공(자명).
    - 발전 중 → 세 축 모두 *첫 1개씩*만(균형 — 모험·안전 둘 다 옵션 제시).

    빈 후보(예: UNDERSTAND/EXECUTE 단계의 비공 extensions)는 빈 tuple — 호출자는
    그대로 사용. UI 선별·강조 시각화는 L5 책임.
    """
    entry_on, extension_on, scaffold_on = _LEVEL_AXES[mastery_level]
    if mastery_level == "발전 중":
        # 균형 — 각 축 첫 1개씩만(존재하면). 초보→숙달 전이 학생의 부담 완화.
        return LthcAdaptation(
            mastery_level=mastery_level,
            entry_suggestions=_ENTRY_BY_STAGE[polya_stage][:1],
            extensions=_EXTENSIONS_BY_STAGE[polya_stage][:1],
            scaffolds=_SCAFFOLDS_BY_STAGE[polya_stage][:1],
        )
    return LthcAdaptation(
        mastery_level=mastery_level,
        entry_suggestions=_ENTRY_BY_STAGE[polya_stage] if entry_on else (),
        extensions=_EXTENSIONS_BY_STAGE[polya_stage] if extension_on else (),
        scaffolds=_SCAFFOLDS_BY_STAGE[polya_stage] if scaffold_on else (),
    )


# L2 BKT/DKT 숙달도(0~1) → LTHC 숙달도 라벨 임계 — `lthc/models.py`가 "호출자(L2 연계 슬라이스)
# 책임"으로 남긴 갭을 메운다. 3구간: <0.4 초보·0.4~0.8 발전 중·≥0.8 숙달(경계 포함은 상위 라벨).
_DEVELOPING_THRESHOLD = 0.4
_MASTERED_THRESHOLD = 0.8


def mastery_to_level(
    bkt_mastery: float,
    *,
    developing_threshold: float = _DEVELOPING_THRESHOLD,
    mastered_threshold: float = _MASTERED_THRESHOLD,
) -> MasteryLevel:
    """L2 BKT 숙달도(0~1) → LTHC 숙달도 라벨 — `adapt_lthc` 입력 브릿지.

    `mastered_threshold` 이상 → "숙달"·`developing_threshold` 이상 → "발전 중"·미만 → "초보".
    경계값은 *상위* 라벨에 포함(≥). 기본 임계(0.4·0.8)는 정책값(모드·학년별 차등은 후속).
    BKT 숙달은 [0,1]이라 별도 clamp 불필요(호출자 계약). 순수·결정론.
    """
    if bkt_mastery >= mastered_threshold:
        return "숙달"
    if bkt_mastery >= developing_threshold:
        return "발전 중"
    return "초보"
