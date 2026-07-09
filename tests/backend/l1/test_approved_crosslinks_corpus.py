"""승인 crosswalk 코퍼스 거버넌스 — Kiki 검수 승인분(M0864·M0865)의 무결성·게이트·해석 동결.

`data/corpus/misconception_crosslinks_v1/crosslinks.json`은 검수 큐(전행 pending) 중 **Kiki가
2026-07-08 직접 승인한 2건**을 promote 산출(로더 형식)해 커밋한 것이다(사람 사인오프·AI 자기승인
아님). 이 테스트는 hermetic(DB 0)으로 봉인한다: ① 로더 형식·게이트 통과(method=manual·검수 서명)
② kebab∈34 카탈로그·M-id∈843 코퍼스(참조 무결성) ③ `select_canonical`이 두 kebab에 canonical
M-id를 실제로 돌려줌(단절 해소 = 843 콘텐츠가 34 탐지에 도달하는 첫 실현).
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

# Kiki 2026-07-08 승인분(MEMORY 정본) — 기대 매핑 동결.
_EXPECTED: dict[str, str] = {
    "extremum-max-min-confused": "M0864",
    "extremum-value-vs-point-confused": "M0865",
}


def _load_rows() -> list[MisconceptionCrosslink]:
    payload = json.loads(_CROSSLINKS.read_text(encoding="utf-8"))
    return [MisconceptionCrosslink.model_validate(r) for r in payload["crosslinks"]]


def _corpus_mis_ids() -> set[str]:
    data = json.loads(_MISCONCEPTIONS.read_text(encoding="utf-8"))
    items = data.get("misconceptions", data)
    return {m["mis_id"] for m in items if isinstance(m, dict) and "mis_id" in m}


def test_exact_approved_pairs() -> None:
    # 정확히 Kiki 승인 2건 — 기대 kebab→M-id 매핑 동결(드리프트 시 즉시 실패).
    rows = _load_rows()
    assert {r.kebab_id: r.mis_id for r in rows} == _EXPECTED


def test_load_gate_passes() -> None:
    # 로더 게이트 통과 — 전 행 method=manual·검수 서명 stamp(검수 우회·자기승인 차단 통과분).
    rows = _load_rows()
    assert load_gate_violations(rows) == []
    for r in rows:
        assert r.method == LOADABLE_METHOD
        assert is_signed(r.note)
        assert r.confidence == 0.9
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
