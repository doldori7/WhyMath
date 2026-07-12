"""crosswalk 강등전 GT 구성 테스트 — positives + injected negatives 2 tier(순수·결정론).

by-construction 정답·성취기준 tier 분류·결정론(사전순)·상한 캡을 동결한다.
"""

from __future__ import annotations

from whymath_backend.l4.misconception.crosslink_demotion_seeder import (
    CROSSLINK_POSITIVES,
    build_demotion_set,
)

# 합성 입력 — positive kebab 4종에 성취기준 부여 + M-id 성취기준 맵(같은/다른/None 섞음).
_KEBAB_STANDARDS = {
    "opposite-root-selected": frozenset({"[10공수1-02-02]"}),
    "factor-sign-flip": frozenset({"[10공수1-02-02]"}),
    "extremum-max-min-confused": frozenset({"[12미적Ⅰ-02-07]"}),
    "extremum-value-vs-point-confused": frozenset({"[12미적Ⅰ-02-07]"}),
}
_MID_STANDARDS: dict[str, str | None] = {
    "M0862": "[10공수1-02-02]",  # positive
    "M0863": "[10공수1-02-02]",  # positive + same-standard 형제
    "M0864": "[12미적Ⅰ-02-07]",  # positive
    "M0865": "[12미적Ⅰ-02-07]",  # positive + same-standard 형제
    "M0500": "[10공수1-01-01]",  # cross-standard
    "M0600": "[12미적Ⅰ-02-07]",  # (극값 kebab엔 same·이차 kebab엔 cross)
    "M0700": None,  # standard 없음 → negatives에서 제외
}


def test_positives_present_and_correct() -> None:
    trials = build_demotion_set(mid_standards=_MID_STANDARDS, kebab_standards=_KEBAB_STANDARDS)
    positives = [t for t in trials if t.tier == "positive"]
    assert {(t.kebab_id, t.mis_id) for t in positives} == set(CROSSLINK_POSITIVES)
    assert all(t.label == "correct" for t in positives)


def test_negative_tiers_classified_by_standard() -> None:
    trials = build_demotion_set(mid_standards=_MID_STANDARDS, kebab_standards=_KEBAB_STANDARDS)
    # opposite-root-selected([10공수1-02-02]): same=M0863, cross=M0500·M0600·M0864·M0865...
    same_for_opp = {
        t.mis_id
        for t in trials
        if t.kebab_id == "opposite-root-selected" and t.tier == "same_standard_neg"
    }
    assert "M0863" in same_for_opp  # 같은 성취기준 형제
    assert "M0500" not in same_for_opp  # 다른 성취기준은 cross
    # None standard(M0700)은 어느 tier에도 안 들어간다(신호 판정 불가 제외).
    assert all(t.mis_id != "M0700" for t in trials)
    # 모든 negative는 label=wrong.
    assert all(t.label == "wrong" for t in trials if t.tier != "positive")


def test_deterministic_and_capped() -> None:
    a = build_demotion_set(
        mid_standards=_MID_STANDARDS,
        kebab_standards=_KEBAB_STANDARDS,
        cross_per_positive=2,
        same_per_positive=1,
    )
    b = build_demotion_set(
        mid_standards=_MID_STANDARDS,
        kebab_standards=_KEBAB_STANDARDS,
        cross_per_positive=2,
        same_per_positive=1,
    )
    assert a == b  # 결정론(사전순·난수 0)
    for kebab, _ in CROSSLINK_POSITIVES:
        cross = [t for t in a if t.kebab_id == kebab and t.tier == "cross_standard_neg"]
        same = [t for t in a if t.kebab_id == kebab and t.tier == "same_standard_neg"]
        assert len(cross) <= 2 and len(same) <= 1  # per-positive 캡 준수
