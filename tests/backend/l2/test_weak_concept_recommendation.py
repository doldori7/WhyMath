"""L2 약개념 추천 — `weak_concept_recommendation` 단위테스트 (hermetic·PG 불요).

개념그래프 소비 슬2. `recommend_weak_concepts`는 두 좌석을 *재사용*한다:
  ① `compute_concept_diagnoses`(L2·BKT/IRT 융합·약점 정렬) — 진단 입력
  ② `fetch_node_meta`(L1·concept_node UC 안전 메타) — UC enrich

이 둘을 *패치*해 PG 없이 좌석 *배선*만 못 박는다(진단 로직·실 PG 조인은 각자 테스트 몫):
  - 약점 필터(임계 경계·신호 0건 제외)·정렬 보존·limit 상한
  - UC enrich(name_ko·domain·review_status 부착)·미적재 UC graceful None·orphan(UC 없음)
  - reviewed_only 게이팅(메타 없으면 보수적 제외·정렬 유지)
  - sync 좌석 to_thread 격리 — fetch_node_meta가 단일 호출·UC 중복 제거(N+1 0)
  - redaction(추천 스키마에 본문 필드 부재)
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Any, cast

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

import whymath_backend.l2.weak_concept_recommendation as wcr_mod
from whymath_backend.l1.concept_graph.node_projection import ConceptNodeMeta
from whymath_backend.l2.concept_diagnosis import Agreement, ConceptDiagnosis
from whymath_backend.l2.weak_concept_recommendation import (
    WeakConceptRecommendation,
    recommend_weak_concepts,
)

_UID = uuid.uuid4()
# 슬2 idmap UC 규약 키 예시(concept.code·concept_node PK와 동일 공간).
_UC_A = "UC.alg.afunction.linear"
_UC_B = "UC.calc.alimit.epsilon-delta"


def _diagnosis(
    *,
    code: str | None,
    name: str | None = "개념",
    bkt: float | None,
    proxy: float | None,
    agreement: Agreement = "agree",
    cid: uuid.UUID | None = None,
) -> ConceptDiagnosis:
    """진단 1건 흉내 — 약점 필터·enrich가 읽는 필드만 채운다(나머지 기본값)."""
    return ConceptDiagnosis(
        concept_id=cid or uuid.uuid4(),
        concept_code=code,
        concept_name=name,
        bkt_mastery=bkt,
        irt_theta=None,
        irt_mastery_proxy=proxy,
        response_count=0,
        agreement=agreement,
    )


def _fake_session() -> AsyncSession:
    """session은 패치된 `compute_concept_diagnoses`가 무시하므로 더미면 충분."""
    return cast(AsyncSession, object())


def _patch_diagnoses(monkeypatch: pytest.MonkeyPatch, diagnoses: list[ConceptDiagnosis]) -> None:
    """`compute_concept_diagnoses`를 패치해 canned 진단(이미 약점 정렬됐다고 가정)을 돌려준다."""

    async def _fake(_session: AsyncSession, _user_id: uuid.UUID) -> list[ConceptDiagnosis]:
        return diagnoses

    monkeypatch.setattr(wcr_mod, "compute_concept_diagnoses", _fake)


def _patch_meta(
    monkeypatch: pytest.MonkeyPatch, meta: dict[str, ConceptNodeMeta] | None = None
) -> dict[str, Any]:
    """`fetch_node_meta`를 패치해 enrich 메타를 제어·호출 인자(UC 리스트·engine)를 기록.

    반환 captured["calls"]에 호출 횟수를, ["concept_ids"]에 마지막 호출 UC를 담는다 — 좌석이
    약점 후보 UC를 *단일 호출*(N+1 0)로 넘기는지 관찰. meta 미지정이면 빈 dict(enrich 없음).
    """
    captured: dict[str, Any] = {"calls": 0}
    resolved_meta = meta if meta is not None else {}

    def _fake_fetch(
        concept_ids: Sequence[str], *, engine: object = None, settings: object = None
    ) -> dict[str, ConceptNodeMeta]:
        captured["calls"] += 1
        captured["concept_ids"] = list(concept_ids)
        captured["engine"] = engine
        return resolved_meta

    monkeypatch.setattr(wcr_mod, "fetch_node_meta", _fake_fetch)
    return captured


# ──────────────────────────────────────────────────────────────────────────
# ① 약점 필터 — 최저 신호 < 임계만·신호 0건 제외·임계 경계
# ──────────────────────────────────────────────────────────────────────────
class TestWeaknessFilter:
    async def test_keeps_below_threshold(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _patch_meta(monkeypatch)
        _patch_diagnoses(
            monkeypatch,
            [
                _diagnosis(code=_UC_A, bkt=0.3, proxy=0.5),  # 최저 0.3 < 0.7 → 약점
                _diagnosis(code=_UC_B, bkt=0.9, proxy=0.95),  # 최저 0.9 ≥ 0.7 → 제외
            ],
        )
        out = await recommend_weak_concepts(_fake_session(), _UID)
        assert [r.concept_code for r in out] == [_UC_A]
        assert out[0].weakness == 0.3  # 두 신호 중 최저

    async def test_threshold_boundary_excludes_equal(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # 경계: weakness == threshold면 *미만*이 아니므로 제외(< 비교).
        _patch_meta(monkeypatch)
        _patch_diagnoses(monkeypatch, [_diagnosis(code=_UC_A, bkt=0.7, proxy=0.8)])
        out = await recommend_weak_concepts(_fake_session(), _UID, mastery_threshold=0.7)
        assert out == []

    async def test_no_signal_excluded(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # 두 신호 모두 None이면 추천 근거 없음 → 제외(insufficient도 신호 0건은 빠진다).
        _patch_meta(monkeypatch)
        _patch_diagnoses(
            monkeypatch,
            [
                _diagnosis(code=_UC_A, bkt=None, proxy=None, agreement="insufficient"),
                _diagnosis(code=_UC_B, bkt=0.2, proxy=None, agreement="insufficient"),
            ],
        )
        out = await recommend_weak_concepts(_fake_session(), _UID)
        # 신호 1건(bkt=0.2)인 _UC_B는 약점으로 남고, 신호 0건 _UC_A는 빠진다.
        assert [r.concept_code for r in out] == [_UC_B]
        assert out[0].weakness == 0.2

    async def test_single_signal_used_as_weakness(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # 한쪽 신호만 있으면 그 값이 weakness(min of 1).
        _patch_meta(monkeypatch)
        _patch_diagnoses(monkeypatch, [_diagnosis(code=_UC_A, bkt=None, proxy=0.4)])
        out = await recommend_weak_concepts(_fake_session(), _UID)
        assert out[0].weakness == 0.4

    async def test_empty_diagnoses(self, monkeypatch: pytest.MonkeyPatch) -> None:
        captured = _patch_meta(monkeypatch)
        _patch_diagnoses(monkeypatch, [])
        out = await recommend_weak_concepts(_fake_session(), _UID)
        assert out == []
        # 약점 후보 0건이면 메타 조회도 생략(early return).
        assert captured["calls"] == 0


# ──────────────────────────────────────────────────────────────────────────
# ② 정렬 보존 — 진단의 약점 우선 순서를 그대로 유지
# ──────────────────────────────────────────────────────────────────────────
class TestSortPreserved:
    async def test_preserves_diagnosis_order(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _patch_meta(monkeypatch)
        # compute_concept_diagnoses가 약점 먼저 정렬해 준 순서(_UC_A weak → _UC_B less weak).
        _patch_diagnoses(
            monkeypatch,
            [
                _diagnosis(code=_UC_A, bkt=0.1, proxy=0.2),
                _diagnosis(code=_UC_B, bkt=0.5, proxy=0.6),
            ],
        )
        out = await recommend_weak_concepts(_fake_session(), _UID)
        assert [r.concept_code for r in out] == [_UC_A, _UC_B]


# ──────────────────────────────────────────────────────────────────────────
# ③ limit 상한 — 약점 정렬 보존하며 상위 N
# ──────────────────────────────────────────────────────────────────────────
class TestLimit:
    async def test_limit_caps_results(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _patch_meta(monkeypatch)
        _patch_diagnoses(
            monkeypatch,
            [_diagnosis(code=f"UC.x.y.{i}", bkt=0.1 + i * 0.01, proxy=0.2) for i in range(5)],
        )
        out = await recommend_weak_concepts(_fake_session(), _UID, limit=2)
        assert len(out) == 2
        assert [r.concept_code for r in out] == ["UC.x.y.0", "UC.x.y.1"]  # 상위 2(정렬 보존)


# ──────────────────────────────────────────────────────────────────────────
# ④ enrich — concept_node 메타 부착·미적재 UC None·orphan(UC 없음)·단일 호출
# ──────────────────────────────────────────────────────────────────────────
class TestEnrichment:
    async def test_attaches_node_meta(self, monkeypatch: pytest.MonkeyPatch) -> None:
        meta = {
            _UC_A: ConceptNodeMeta(name_ko="일차함수", domain="[중]함수", review_status="reviewed")
        }
        captured = _patch_meta(monkeypatch, meta)
        _patch_diagnoses(monkeypatch, [_diagnosis(code=_UC_A, bkt=0.2, proxy=0.3)])
        out = await recommend_weak_concepts(_fake_session(), _UID)
        assert out[0].name_ko == "일차함수"
        assert out[0].domain == "[중]함수"
        assert out[0].review_status == "reviewed"
        # 약점 후보 UC를 *단일 호출*로 넘긴다(N+1 0).
        assert captured["calls"] == 1
        assert captured["concept_ids"] == [_UC_A]

    async def test_missing_meta_is_none_graceful(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # concept_node에 _UC_B 메타가 없으면(적재 누락) enrich 필드 None(추천은 유지).
        meta = {_UC_A: ConceptNodeMeta(name_ko="A", domain="d", review_status="reviewed")}
        _patch_meta(monkeypatch, meta)
        _patch_diagnoses(
            monkeypatch,
            [
                _diagnosis(code=_UC_A, bkt=0.2, proxy=0.3),
                _diagnosis(code=_UC_B, bkt=0.25, proxy=0.3),
            ],
        )
        out = await recommend_weak_concepts(_fake_session(), _UID)
        assert out[1].concept_code == _UC_B
        assert out[1].name_ko is None
        assert out[1].domain is None
        assert out[1].review_status is None

    async def test_orphan_concept_no_uc(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # concept_code(UC) None인 orphan은 enrich 안 함(meta 조회 UC 목록에서도 제외).
        captured = _patch_meta(monkeypatch)
        _patch_diagnoses(monkeypatch, [_diagnosis(code=None, bkt=0.1, proxy=0.2)])
        out = await recommend_weak_concepts(_fake_session(), _UID)
        assert len(out) == 1
        assert out[0].concept_code is None
        assert out[0].name_ko is None
        # UC가 하나도 없으면 메타 조회 생략(빈 UC 목록 → 호출 0).
        assert captured["calls"] == 0

    async def test_dedupes_uc_in_single_call(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # 같은 UC 중복 후보는 메타 조회 UC 목록에서 중복 제거(IN 1회·중복 키 0).
        meta = {_UC_A: ConceptNodeMeta(name_ko="A", domain="d", review_status="reviewed")}
        captured = _patch_meta(monkeypatch, meta)
        _patch_diagnoses(
            monkeypatch,
            [
                _diagnosis(code=_UC_A, bkt=0.1, proxy=0.2),
                _diagnosis(code=_UC_A, bkt=0.15, proxy=0.2),
            ],
        )
        await recommend_weak_concepts(_fake_session(), _UID)
        assert captured["calls"] == 1
        assert captured["concept_ids"] == [_UC_A]  # 중복 제거


# ──────────────────────────────────────────────────────────────────────────
# ⑤ reviewed_only 게이팅 — reviewed만·메타 없으면 제외·기본 recall
# ──────────────────────────────────────────────────────────────────────────
class TestReviewedOnlyGating:
    async def test_gates_pending(self, monkeypatch: pytest.MonkeyPatch) -> None:
        meta = {
            _UC_A: ConceptNodeMeta(name_ko="A", domain="d", review_status="reviewed"),
            _UC_B: ConceptNodeMeta(name_ko="B", domain="d", review_status="pending"),
        }
        _patch_meta(monkeypatch, meta)
        _patch_diagnoses(
            monkeypatch,
            [
                _diagnosis(code=_UC_A, bkt=0.1, proxy=0.2),
                _diagnosis(code=_UC_B, bkt=0.15, proxy=0.2),
            ],
        )
        out = await recommend_weak_concepts(_fake_session(), _UID, reviewed_only=True)
        assert [r.concept_code for r in out] == [_UC_A]  # pending 제외·정렬 유지

    async def test_gates_missing_meta(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # 메타 없어 reviewed 확인 불가인 UC는 gated 모드에서 보수적 제외(정직).
        meta = {_UC_A: ConceptNodeMeta(name_ko="A", domain="d", review_status="reviewed")}
        _patch_meta(monkeypatch, meta)
        _patch_diagnoses(
            monkeypatch,
            [
                _diagnosis(code=_UC_A, bkt=0.1, proxy=0.2),
                _diagnosis(code=_UC_B, bkt=0.15, proxy=0.2),  # 메타 없음
                _diagnosis(code=None, bkt=0.05, proxy=0.1),  # orphan(UC 없음)
            ],
        )
        out = await recommend_weak_concepts(_fake_session(), _UID, reviewed_only=True)
        assert [r.concept_code for r in out] == [_UC_A]  # 메타 없음·orphan 모두 제외

    async def test_default_keeps_all_recall(self, monkeypatch: pytest.MonkeyPatch) -> None:
        meta = {_UC_A: ConceptNodeMeta(name_ko="A", domain="d", review_status="pending")}
        _patch_meta(monkeypatch, meta)
        _patch_diagnoses(
            monkeypatch,
            [
                _diagnosis(code=_UC_A, bkt=0.1, proxy=0.2),  # pending
                _diagnosis(code=_UC_B, bkt=0.15, proxy=0.2),  # 메타 없음
            ],
        )
        out = await recommend_weak_concepts(_fake_session(), _UID)
        assert [r.concept_code for r in out] == [_UC_A, _UC_B]  # 기본 False·둘 다 노출

    async def test_gating_then_limit(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # 게이팅 후 limit — reviewed만 카운트해 상위 N(게이팅이 limit보다 먼저).
        meta = {
            _UC_A: ConceptNodeMeta(name_ko="A", domain="d", review_status="reviewed"),
            _UC_B: ConceptNodeMeta(name_ko="B", domain="d", review_status="reviewed"),
        }
        _patch_meta(monkeypatch, meta)
        _patch_diagnoses(
            monkeypatch,
            [
                _diagnosis(code="UC.p.q.0", bkt=0.05, proxy=0.1),  # 메타 없음 → gated
                _diagnosis(code=_UC_A, bkt=0.1, proxy=0.2),  # reviewed
                _diagnosis(code=_UC_B, bkt=0.15, proxy=0.2),  # reviewed
            ],
        )
        out = await recommend_weak_concepts(_fake_session(), _UID, limit=1, reviewed_only=True)
        # gated UC 건너뛰고 reviewed 첫 1개(_UC_A)만.
        assert [r.concept_code for r in out] == [_UC_A]


# ──────────────────────────────────────────────────────────────────────────
# ⑥ redaction — 추천 스키마에 본문 필드(description·formal_definition) 부재
# ──────────────────────────────────────────────────────────────────────────
def test_recommendation_has_only_safe_fields() -> None:
    fields = set(WeakConceptRecommendation.model_fields)
    expected = {
        "concept_id",
        "concept_code",
        "concept_name",
        "bkt_mastery",
        "irt_mastery_proxy",
        "weakness",
        "agreement",
        "domain",
        "review_status",
        "name_ko",
    }
    assert fields == expected
    assert "description" not in fields
    assert "formal_definition" not in fields
    assert "intuitive_explanation" not in fields
