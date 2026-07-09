"""거버넌스 동결 — Crosswalk Gate Contract (리치 Part 2 Phase 4b-1·2026-07-08).

오개념 crosswalk 승인·적재 조건의 단일 정본(`l1/misconception/crosslink_gate.py`)이 문서
(`docs/standards/crosswalk_gate_contract.md`)·두 소비처(promote·load)와 어긋나지 않게 동결한다:

  ① **load 게이트 우회 차단**: method≠manual·미서명·candidate/embedding 행은 `load_crosslinks`에서
     거부(검수 우회·AI 자기승인을 코드로 막음). 서명·manual 행만 통과.
  ② **서명 왕복 + sanctioned 경로 무손상**: `is_signed(sign(...))` 왕복·promote_approved 산출물이
     load 게이트를 통과(정본 경로는 막지 않음).
  ③ **드리프트 0**: promote(l4)·load(l1)가 같은 contract 상수를 참조 — `ReviewStatus` Literal ==
     `REVIEW_STATUSES`·promote가 `DIRECT_MIN_CONFIDENCE`를 임계로 사용.
  ④ **문서↔코드 일치**: contract 문서가 코드 상수(status·서명 필드·임계·method·서명 형식)를 담는다.

hermetic: DB 불요(순수 술어·모델 import·문서 텍스트 스캔만).
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import get_args

import pytest

from whymath_backend.l1.misconception.crosslink_gate import (
    APPROVED_STATUS,
    DIRECT_LINK_TYPE,
    DIRECT_MIN_CONFIDENCE,
    LOADABLE_METHOD,
    MACHINE_REJECT_EVIDENCE_FLOOR,
    MACHINE_REJECT_METHOD,
    MACHINE_REJECT_REVIEWER,
    REQUIRED_SIGNATURE_FIELDS,
    REVIEW_STATUSES,
    CrosslinkGateError,
    is_signed,
    load_gate_violations,
    promotion_violations,
    sign,
)
from whymath_backend.l1.misconception.crosslink_loader import load_crosslinks
from whymath_backend.l4.misconception.crosslink_review import (
    CrosslinkReviewError,
    ReviewStatus,
    promote_approved,
)
from whymath_backend.schema.misconception_crosslink import MisconceptionCrosslink

_REPO_ROOT = Path(__file__).resolve().parents[3]
_CONTRACT_DOC = _REPO_ROOT / "docs" / "standards" / "crosswalk_gate_contract.md"

_SIGNED_NOTE = "검수:Kiki 2026-07-08"


def _row(**overrides: object) -> MisconceptionCrosslink:
    base: dict[str, object] = {
        "kebab_id": "k",
        "mis_id": "M1",
        "link_type": "직접매핑",
        "confidence": 0.9,
        "method": "manual",
        "note": _SIGNED_NOTE,
    }
    base.update(overrides)
    return MisconceptionCrosslink(**base)  # type: ignore[arg-type]


# ── ① load 게이트 우회 차단 ─────────────────────────────────────────────────
def test_load_gate_passes_signed_manual_row() -> None:
    """method=manual + 검수 서명 행은 통과(위반 0)."""
    assert load_gate_violations([_row()]) == []


def test_load_gate_rejects_non_manual_method() -> None:
    """candidate 도구 method(embedding/standard_code)는 적재 거부(검수 우회 차단)."""
    assert load_gate_violations([_row(method="embedding")])
    assert load_gate_violations([_row(method="standard_code")])


def test_load_gate_rejects_unsigned_note() -> None:
    """서명 없는 note(None·날짜 없는 문자열)는 적재 거부(사람 검수 산출물 아님)."""
    assert load_gate_violations([_row(note=None)])
    assert load_gate_violations([_row(note="통합테스트 시드")])  # 날짜 없음 → 미서명


def test_load_crosslinks_raises_on_bypass() -> None:
    """`load_crosslinks`가 미서명/candidate 행을 CrosslinkGateError로 거부(관통·DB 불요)."""
    with pytest.raises(CrosslinkGateError):
        load_crosslinks(
            None,
            {
                "crosslinks": [
                    {
                        "kebab_id": "k",
                        "mis_id": "M1",
                        "link_type": "직접매핑",
                        "confidence": 0.9,
                        "method": "embedding",
                    }
                ]
            },
        )


# ── ② 서명 왕복 + sanctioned 경로 무손상 ────────────────────────────────────
def test_signature_roundtrip() -> None:
    """`is_signed(sign(...))` 왕복 True·미서명은 False."""
    stamp = sign("Kiki", date(2026, 7, 8))
    assert is_signed(stamp)
    assert is_signed(f"기존 메모 · {stamp}")  # promote가 note에 병합해도 검출
    assert not is_signed(None)
    assert not is_signed("검수자 미상")  # 날짜 없음


def test_promote_output_passes_load_gate() -> None:
    """promote_approved 산출물(승인분)이 load 게이트를 통과 — 정본 경로는 막지 않는다."""
    queue = {
        "review_queue": [
            {
                "kebab_id": next(iter(_known_kebab())),
                "mis_id": "M0049",
                "link_type": "직접매핑",
                "confidence": 0.9,
                "rationale": "동일 오개념",
                "status": "approved",
                "reviewer": "Kiki",
                "reviewed_on": "2026-07-08",
            }
        ]
    }
    payload = promote_approved(queue)
    rows = [MisconceptionCrosslink.model_validate(r) for r in payload["crosslinks"]]
    assert rows, "승인 1건이 승격돼야 한다"
    assert load_gate_violations(rows) == []  # promote 출력 = load 게이트 통과


# ── ③ 드리프트 0 (promote·load가 같은 contract 상수) ────────────────────────
def test_review_status_literal_matches_contract() -> None:
    """l4 `ReviewStatus` Literal이 contract `REVIEW_STATUSES`와 일치(어휘 단일 정본)."""
    assert set(get_args(ReviewStatus)) == set(REVIEW_STATUSES)
    assert APPROVED_STATUS in REVIEW_STATUSES


def test_promote_uses_contract_direct_threshold() -> None:
    """promote가 직접매핑 임계로 `DIRECT_MIN_CONFIDENCE`를 사용 — 임계 경계에서 거부/통과 전환."""
    kebab = next(iter(_known_kebab()))

    def _approved_direct(conf: float) -> dict[str, object]:
        return {
            "review_queue": [
                {
                    "kebab_id": kebab,
                    "mis_id": "M0049",
                    "link_type": DIRECT_LINK_TYPE,
                    "confidence": conf,
                    "rationale": "r",
                    "status": APPROVED_STATUS,
                    "reviewer": "Kiki",
                    "reviewed_on": "2026-07-08",
                }
            ]
        }

    # 임계 미만 → 승격 거부(직접매핑 conf 규칙).
    with pytest.raises(CrosslinkReviewError):
        promote_approved(_approved_direct(DIRECT_MIN_CONFIDENCE - 0.01))
    # 임계 이상 → 승격.
    assert promote_approved(_approved_direct(DIRECT_MIN_CONFIDENCE))["crosslinks"]


def test_promotion_violations_pure_contract() -> None:
    """contract promotion_violations: 승인 서명 누락·kebab 부재를 순수하게 잡는다(주입 카탈로그)."""
    # 서명 누락 승인 행.
    v = promotion_violations(
        kebab_id="k",
        mis_id="M1",
        status="approved",
        reviewer=None,
        reviewed_on=None,
        link_type="부분매핑",
        confidence=None,
        known_kebab_ids={"k"},
    )
    assert any("검수 서명" in m for m in v)
    # kebab 카탈로그 밖.
    v2 = promotion_violations(
        kebab_id="ghost",
        mis_id="M1",
        status="pending",
        reviewer=None,
        reviewed_on=None,
        link_type="부분매핑",
        confidence=None,
        known_kebab_ids={"k"},
    )
    assert any("카탈로그" in m for m in v2)


# ── ④ 문서↔코드 일치 ────────────────────────────────────────────────────────
def test_contract_doc_freezes_code_constants() -> None:
    """contract 문서가 코드 상수(status·서명 필드·임계·method·서명 형식)를 담는다(드리프트 동결)."""
    assert _CONTRACT_DOC.is_file(), f"contract 문서 부재: {_CONTRACT_DOC}"
    doc = _CONTRACT_DOC.read_text(encoding="utf-8")
    for status in REVIEW_STATUSES:
        assert status in doc, status
    for field in REQUIRED_SIGNATURE_FIELDS:
        assert field in doc, field
    assert str(DIRECT_MIN_CONFIDENCE) in doc  # "0.6"
    assert LOADABLE_METHOD in doc  # "manual"
    assert DIRECT_LINK_TYPE in doc  # "직접매핑"
    assert "검수:" in doc  # 서명 stamp 형식
    # 기계 자율 거부 축(§3.3) — 상수 드리프트 동결.
    assert MACHINE_REJECT_METHOD in doc  # "structural_reject"
    assert MACHINE_REJECT_REVIEWER in doc  # "machine"
    assert str(MACHINE_REJECT_EVIDENCE_FLOOR) in doc  # "20"


def _known_kebab() -> tuple[str, ...]:
    """실제 카탈로그 kebab-id(promote가 카탈로그 실재를 요구하므로 실 id로 테스트)."""
    from whymath_backend.l4.misconception.catalog import CATALOG_BY_ID

    return tuple(CATALOG_BY_ID)
