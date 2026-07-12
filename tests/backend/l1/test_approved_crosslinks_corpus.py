"""승인 crosswalk 코퍼스 거버넌스 — Kiki 검수 승인분의 무결성·게이트·해석 동결.

`data/corpus/misconception_crosslinks_v1/crosslinks.json`은 검수 큐(전행 pending) 중 **Kiki가
직접 승인한 매핑**을 promote 산출(로더 형식)해 커밋한 것이다(사람 사인오프·AI 자기승인 아님).
2026-07-08 극값 2(M0864·M0865)·2026-07-10 트리아지 A 11 + B 8 + frac 1·2026-07-12 미매핑 Tier C
Tier C 10 + period→M0152 + root-loss→M0573 + 843 확장 트랜치1 6(신규 탐지 kebab·기초 계산형)을
승인해 **총 40건(탐지 카탈로그 40 전수 매핑)**이다. 이 테스트는 hermetic(DB 0)으로 봉인한다:
① 로더 형식·게이트 통과(method=manual·검수 서명) ② kebab∈34 카탈로그·M-id∈843 코퍼스(참조 무결성)
③ `select_canonical`이 각 kebab에 canonical M-id를 실제로 돌려줌(단절 해소·843→34 도달).
"""

from __future__ import annotations

import json
from pathlib import Path

from whymath_backend.l1.misconception.crosslink_gate import (
    LOADABLE_METHOD,
    is_signed,
    load_gate_violations,
)
from whymath_backend.l1.misconception.crosslink_resolve import (
    ResolvedLink,
    select_canonical,
)
from whymath_backend.l4.misconception.catalog import CATALOG_BY_ID
from whymath_backend.schema.misconception_crosslink import MisconceptionCrosslink

_REPO_ROOT = Path(__file__).resolve().parents[3]
_CROSSLINKS = _REPO_ROOT / "data" / "corpus" / "misconception_crosslinks_v1" / "crosslinks.json"
_MISCONCEPTIONS = _REPO_ROOT / "data" / "corpus" / "misconceptions_v1" / "misconceptions.json"

# Kiki 승인분(MEMORY 정본·07-08 극값 2·07-10 A/B/frac 20·07-12 Tier C 10+period+root-loss 12)
# — 34/34 kebab 완주·기대 매핑 동결.
_EXPECTED: dict[str, str] = {
    "extremum-max-min-confused": "M0864",
    "extremum-value-vs-point-confused": "M0865",
    "continuity-implies-differentiability": "M0670",
    "sine-distributes-over-sum": "M0707",
    "composite-function-commutes": "M0643",
    "discriminant-negative-no-real-root": "M0610",
    "limit-equals-function-value": "M0665",
    "term-to-zero-implies-convergence": "M0704",
    "factor-sign-flip": "M0863",
    "distribution-over-power": "M0019",
    "critical-point-implies-extremum": "M0080",
    "product-rule-naive": "M0075",
    "log-distribution": "M0049",
    "area-perimeter-confusion": "M0529",
    "geometric-series-always-converges": "M0209",
    "invertibility-without-1-1": "M0144",
    "opposite-root-selected": "M0862",
    "exponent-zero": "M0105",
    "circle-radius-squared": "M0848",
    "square-root-positivity": "M0550",
    "chain-rule-inner-derivative-omitted": "M0370",
    "fraction-cancellation": "M0118",
    "angle-sum-non-triangle": "M0493",
    "division-by-zero": "M0003",
    "dot-product-is-vector": "M0735",
    "gambler-fallacy": "M0688",
    "mean-vs-median": "M0419",
    "mutually-exclusive-implies-independent": "M0692",
    "prosecutor-fallacy": "M0691",
    "sign-flip-in-inequality": "M0564",
    "similarity-vs-congruence": "M0519",
    "translation-sign-flip": "M0411",
    "period-of-scaled-sine": "M0152",
    "root-loss-by-dividing": "M0573",
    "fraction-addition-naive": "M0004",
    "negative-times-negative": "M0001",
    "subtract-negative-sign": "M0002",
    "absolute-value-keeps-sign": "M0010",
    "sqrt-distributes-over-sum": "M0008",
    "difference-of-squares-confused": "M0121",
}


def _load_rows() -> list[MisconceptionCrosslink]:
    payload = json.loads(_CROSSLINKS.read_text(encoding="utf-8"))
    return [MisconceptionCrosslink.model_validate(r) for r in payload["crosslinks"]]


def _corpus_mis_ids() -> set[str]:
    data = json.loads(_MISCONCEPTIONS.read_text(encoding="utf-8"))
    items = data.get("misconceptions", data)
    return {m["mis_id"] for m in items if isinstance(m, dict) and "mis_id" in m}


def test_exact_approved_pairs() -> None:
    # 정확히 Kiki 승인 40건 — 기대 kebab→M-id 매핑 동결(드리프트 시 즉시 실패).
    rows = _load_rows()
    assert {r.kebab_id: r.mis_id for r in rows} == _EXPECTED


def test_load_gate_passes() -> None:
    # 로더 게이트 통과 — 전 행 method=manual·검수 서명 stamp(검수 우회·자기승인 차단 통과분).
    rows = _load_rows()
    assert load_gate_violations(rows) == []
    for r in rows:
        assert r.method == LOADABLE_METHOD
        assert is_signed(r.note)
        assert (
            r.confidence is not None and r.confidence >= 0.6
        )  # 직접매핑 승격 게이트 하한(DIRECT_MIN_CONFIDENCE)
        assert r.link_type == "직접매핑"


def test_referential_integrity() -> None:
    # kebab는 34 탐지 카탈로그·M-id는 843 콘텐츠 코퍼스에 실재(양측 dangling 0).
    rows = _load_rows()
    corpus_ids = _corpus_mis_ids()
    for r in rows:
        assert r.kebab_id in CATALOG_BY_ID
        assert r.mis_id in corpus_ids


def test_canonical_resolution_realized() -> None:
    # 단절 해소 증명 — select_canonical이 두 kebab에 canonical M-id를 실제로 돌려준다
    # (과거엔 링크 0으로 no_links·843 콘텐츠가 34 탐지에 도달 못 함).
    rows = _load_rows()
    for kebab, expected_mis in _EXPECTED.items():
        links = [
            ResolvedLink(mis_id=r.mis_id, link_type=r.link_type, confidence=r.confidence)
            for r in rows
            if r.kebab_id == kebab
        ]
        sel = select_canonical(links)
        assert sel.canonical_mis_id == expected_mis
        assert sel.ambiguous is False
        assert sel.reason == "ok"
