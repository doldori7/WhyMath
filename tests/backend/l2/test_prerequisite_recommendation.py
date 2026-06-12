"""L2 선수개념 추천 — `prerequisite_recommendation` 단위테스트 (hermetic·PG 불요).

개념그래프 소비 선수 슬1. `recommend_prerequisite_gaps`는 세 좌석을 *조합*한다:
  ① `fetch_prerequisites`(이 모듈·concept_edge to==C→from traversal) — 선수 조회
  ② `compute_concept_diagnoses`(L2·BKT/IRT) — 선수 mastery lookup
  ③ `fetch_node_meta`(L1·concept_node UC 안전 메타) — UC enrich

셋을 *패치*해 PG 없이 좌석 *배선*만 못 박는다(실 SQL traversal·진단·조인은 통합 몫):
  - 선수 traversal 방향(to==C→from)·강도 desc
  - weak_only(막힌 선수만·미측정 제외/포함)·임계 경계
  - 정렬(weakness asc=root blocker 먼저·tie는 edge_strength desc)
  - UC enrich(name_ko·domain·review_status)·미적재 None·orphan(UC 없음)·단일 호출(N+1 0)
  - reviewed_only 게이팅(메타 없으면 보수적 제외)
  - redaction(스키마에 본문 필드 부재)
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Any, cast

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

import whymath_backend.l2.prerequisite_recommendation as prq_mod
from whymath_backend.l1.concept_graph.node_projection import ConceptNodeMeta
from whymath_backend.l2.concept_diagnosis import Agreement, ConceptDiagnosis
from whymath_backend.l2.prerequisite_recommendation import (
    PrerequisiteGap,
    PrerequisiteRow,
    recommend_prerequisite_gaps,
)

_UID = uuid.uuid4()
_CONCEPT_C = uuid.uuid4()  # 약개념(후행)
_UC_PRE_A = "UC.alg.afunction.linear"
_UC_PRE_B = "UC.alg.aset.basic"


def _row(
    *,
    cid: uuid.UUID,
    code: str | None,
    name: str | None = "선수개념",
    edge_strength: float | None = 0.8,
    depth: int = 1,
) -> PrerequisiteRow:
    return PrerequisiteRow(
        concept_id=cid,
        concept_code=code,
        name_ko=name,
        edge_strength=edge_strength,
        depth=depth,
    )


def _diagnosis(
    *,
    cid: uuid.UUID,
    code: str | None,
    bkt: float | None,
    proxy: float | None,
    agreement: Agreement = "agree",
) -> ConceptDiagnosis:
    return ConceptDiagnosis(
        concept_id=cid,
        concept_code=code,
        concept_name="개념",
        bkt_mastery=bkt,
        irt_theta=None,
        irt_mastery_proxy=proxy,
        response_count=0,
        agreement=agreement,
    )


def _fake_session() -> AsyncSession:
    return cast(AsyncSession, object())


def _patch_prereqs(
    monkeypatch: pytest.MonkeyPatch, rows: list[PrerequisiteRow]
) -> dict[str, Any]:
    """`fetch_prerequisites`를 패치 — traversal 결과를 제어·호출 인자(concept_id·max_depth) 기록.

    실 재귀 CTE는 통합 테스트(`test_prerequisite_traversal_integration.py`) 몫이고, 여기선 다양한
    depth의 PrerequisiteRow를 canned로 주입해 recommend 배선(필터·정렬·enrich)만 못 박는다.
    """
    captured: dict[str, Any] = {"calls": 0}

    async def _fake(
        _session: AsyncSession, concept_id: uuid.UUID, *, max_depth: int = 1
    ) -> list[PrerequisiteRow]:
        captured["calls"] += 1
        captured["concept_id"] = concept_id
        captured["max_depth"] = max_depth
        return rows

    monkeypatch.setattr(prq_mod, "fetch_prerequisites", _fake)
    return captured


def _patch_diagnoses(
    monkeypatch: pytest.MonkeyPatch, diagnoses: list[ConceptDiagnosis]
) -> None:
    async def _fake(_session: AsyncSession, _user_id: uuid.UUID) -> list[ConceptDiagnosis]:
        return diagnoses

    monkeypatch.setattr(prq_mod, "compute_concept_diagnoses", _fake)


def _patch_meta(
    monkeypatch: pytest.MonkeyPatch, meta: dict[str, ConceptNodeMeta] | None = None
) -> dict[str, Any]:
    captured: dict[str, Any] = {"calls": 0}
    resolved = meta if meta is not None else {}

    def _fake_fetch(
        concept_ids: Sequence[str], *, engine: object = None, settings: object = None
    ) -> dict[str, ConceptNodeMeta]:
        captured["calls"] += 1
        captured["concept_ids"] = list(concept_ids)
        return resolved

    monkeypatch.setattr(prq_mod, "fetch_node_meta", _fake_fetch)
    return captured


# ──────────────────────────────────────────────────────────────────────────
# ① 선수 traversal 방향 — fetch_prerequisites가 약개념 concept_id로 호출됨
# ──────────────────────────────────────────────────────────────────────────
class TestTraversalDirection:
    async def test_passes_concept_id_to_traversal(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        captured = _patch_prereqs(monkeypatch, [])
        _patch_diagnoses(monkeypatch, [])
        _patch_meta(monkeypatch)
        out = await recommend_prerequisite_gaps(_fake_session(), _UID, _CONCEPT_C)
        assert out == []
        # traversal이 후행 개념 C(concept_id)로 호출(to==C→from 방향은 fetch_prerequisites 책임).
        assert captured["concept_id"] == _CONCEPT_C
        assert captured["calls"] == 1
        # 기본 max_depth=1(직접 선수만·기존 1-hop 계약·후방 호환)이 전달됨.
        assert captured["max_depth"] == 1

    async def test_forwards_max_depth_to_traversal(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # max_depth는 fetch_prerequisites(재귀 CTE bound)로 그대로 전달된다(다단계 traversal).
        captured = _patch_prereqs(monkeypatch, [])
        _patch_diagnoses(monkeypatch, [])
        _patch_meta(monkeypatch)
        await recommend_prerequisite_gaps(_fake_session(), _UID, _CONCEPT_C, max_depth=3)
        assert captured["max_depth"] == 3

    async def test_no_prerequisites_short_circuits(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch_prereqs(monkeypatch, [])
        _patch_diagnoses(monkeypatch, [])
        meta_cap = _patch_meta(monkeypatch)
        out = await recommend_prerequisite_gaps(_fake_session(), _UID, _CONCEPT_C)
        assert out == []
        # 선수 0건이면 메타 조회 생략.
        assert meta_cap["calls"] == 0


# ──────────────────────────────────────────────────────────────────────────
# ② weak_only — 막힌 선수만·미측정 제외/포함·임계 경계
# ──────────────────────────────────────────────────────────────────────────
class TestWeakOnly:
    async def test_keeps_weak_prerequisites_only(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        pre_a, pre_b = uuid.uuid4(), uuid.uuid4()
        _patch_prereqs(
            monkeypatch,
            [
                _row(cid=pre_a, code=_UC_PRE_A),
                _row(cid=pre_b, code=_UC_PRE_B),
            ],
        )
        _patch_diagnoses(
            monkeypatch,
            [
                _diagnosis(cid=pre_a, code=_UC_PRE_A, bkt=0.3, proxy=0.4),  # 약 0.3<0.7
                _diagnosis(cid=pre_b, code=_UC_PRE_B, bkt=0.9, proxy=0.95),  # 강 0.9
            ],
        )
        _patch_meta(monkeypatch)
        out = await recommend_prerequisite_gaps(_fake_session(), _UID, _CONCEPT_C)
        assert [g.concept_id for g in out] == [pre_a]
        assert out[0].weakness == 0.3

    async def test_unmeasured_excluded_when_weak_only(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # 측정 없는 선수(진단 맵에 없음)는 weak_only=True면 제외(약점 근거 없음).
        pre_a, pre_b = uuid.uuid4(), uuid.uuid4()
        _patch_prereqs(
            monkeypatch,
            [_row(cid=pre_a, code=_UC_PRE_A), _row(cid=pre_b, code=_UC_PRE_B)],
        )
        _patch_diagnoses(
            monkeypatch, [_diagnosis(cid=pre_a, code=_UC_PRE_A, bkt=0.2, proxy=0.3)]
        )
        _patch_meta(monkeypatch)
        out = await recommend_prerequisite_gaps(_fake_session(), _UID, _CONCEPT_C)
        assert [g.concept_id for g in out] == [pre_a]  # pre_b 미측정 → 제외

    async def test_unmeasured_included_when_not_weak_only(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # weak_only=False면 모든 선수(미측정 포함·mastery None·insufficient).
        pre_a, pre_b = uuid.uuid4(), uuid.uuid4()
        _patch_prereqs(
            monkeypatch,
            [
                _row(cid=pre_a, code=_UC_PRE_A, edge_strength=0.9),
                _row(cid=pre_b, code=_UC_PRE_B, edge_strength=0.5),
            ],
        )
        _patch_diagnoses(
            monkeypatch, [_diagnosis(cid=pre_a, code=_UC_PRE_A, bkt=0.2, proxy=0.3)]
        )
        _patch_meta(monkeypatch)
        out = await recommend_prerequisite_gaps(
            _fake_session(), _UID, _CONCEPT_C, weak_only=False
        )
        ids = {g.concept_id for g in out}
        assert ids == {pre_a, pre_b}
        b = next(g for g in out if g.concept_id == pre_b)
        assert b.weakness is None  # 미측정
        assert b.bkt_mastery is None
        assert b.agreement == "insufficient"

    async def test_threshold_boundary_excludes_equal(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        pre_a = uuid.uuid4()
        _patch_prereqs(monkeypatch, [_row(cid=pre_a, code=_UC_PRE_A)])
        _patch_diagnoses(
            monkeypatch, [_diagnosis(cid=pre_a, code=_UC_PRE_A, bkt=0.7, proxy=0.8)]
        )
        _patch_meta(monkeypatch)
        out = await recommend_prerequisite_gaps(
            _fake_session(), _UID, _CONCEPT_C, mastery_threshold=0.7
        )
        assert out == []  # weakness 0.7 == threshold → 미만 아님 → 제외


# ──────────────────────────────────────────────────────────────────────────
# ③ 정렬 — weakness asc(root blocker 먼저)·tie는 edge_strength desc
# ──────────────────────────────────────────────────────────────────────────
class TestSorting:
    async def test_weakest_prerequisite_first(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        pre_a, pre_b = uuid.uuid4(), uuid.uuid4()
        # traversal은 강도 desc로 줄 수 있으나, 최종 정렬은 weakness asc.
        _patch_prereqs(
            monkeypatch,
            [_row(cid=pre_b, code=_UC_PRE_B), _row(cid=pre_a, code=_UC_PRE_A)],
        )
        _patch_diagnoses(
            monkeypatch,
            [
                _diagnosis(cid=pre_a, code=_UC_PRE_A, bkt=0.1, proxy=0.2),  # 더 약함
                _diagnosis(cid=pre_b, code=_UC_PRE_B, bkt=0.5, proxy=0.6),
            ],
        )
        _patch_meta(monkeypatch)
        out = await recommend_prerequisite_gaps(_fake_session(), _UID, _CONCEPT_C)
        assert [g.concept_id for g in out] == [pre_a, pre_b]  # 가장 약한 선수 먼저

    async def test_tie_breaks_on_edge_strength_desc(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        pre_a, pre_b = uuid.uuid4(), uuid.uuid4()
        _patch_prereqs(
            monkeypatch,
            [
                _row(cid=pre_a, code=_UC_PRE_A, edge_strength=0.4),
                _row(cid=pre_b, code=_UC_PRE_B, edge_strength=0.9),
            ],
        )
        # 같은 weakness(0.2) → tie → edge_strength desc(pre_b 0.9 먼저).
        _patch_diagnoses(
            monkeypatch,
            [
                _diagnosis(cid=pre_a, code=_UC_PRE_A, bkt=0.2, proxy=0.5),
                _diagnosis(cid=pre_b, code=_UC_PRE_B, bkt=0.2, proxy=0.5),
            ],
        )
        _patch_meta(monkeypatch)
        out = await recommend_prerequisite_gaps(_fake_session(), _UID, _CONCEPT_C)
        assert [g.concept_id for g in out] == [pre_b, pre_a]  # 강한 선수 먼저(tie)

    async def test_tie_breaks_on_depth_before_strength(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # weakness 동률이면 depth asc(가까운 선수 먼저)가 edge_strength보다 *우선*한다.
        # pre_far: 더 강한 선수(0.9)지만 depth 2. pre_near: 약한 선수(0.4)지만 depth 1.
        # depth가 강도보다 먼저라 pre_near(depth 1)가 앞.
        pre_near, pre_far = uuid.uuid4(), uuid.uuid4()
        _patch_prereqs(
            monkeypatch,
            [
                _row(cid=pre_far, code=_UC_PRE_B, edge_strength=0.9, depth=2),
                _row(cid=pre_near, code=_UC_PRE_A, edge_strength=0.4, depth=1),
            ],
        )
        _patch_diagnoses(
            monkeypatch,
            [
                _diagnosis(cid=pre_near, code=_UC_PRE_A, bkt=0.2, proxy=0.5),
                _diagnosis(cid=pre_far, code=_UC_PRE_B, bkt=0.2, proxy=0.5),
            ],
        )
        _patch_meta(monkeypatch)
        out = await recommend_prerequisite_gaps(_fake_session(), _UID, _CONCEPT_C)
        assert [g.concept_id for g in out] == [pre_near, pre_far]  # depth 1 먼저(강도보다 우선)
        assert [g.depth for g in out] == [1, 2]

    async def test_tie_same_depth_breaks_on_strength(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # weakness·depth 모두 동률이면 그 다음 edge_strength desc.
        pre_a, pre_b = uuid.uuid4(), uuid.uuid4()
        _patch_prereqs(
            monkeypatch,
            [
                _row(cid=pre_a, code=_UC_PRE_A, edge_strength=0.4, depth=2),
                _row(cid=pre_b, code=_UC_PRE_B, edge_strength=0.9, depth=2),
            ],
        )
        _patch_diagnoses(
            monkeypatch,
            [
                _diagnosis(cid=pre_a, code=_UC_PRE_A, bkt=0.2, proxy=0.5),
                _diagnosis(cid=pre_b, code=_UC_PRE_B, bkt=0.2, proxy=0.5),
            ],
        )
        _patch_meta(monkeypatch)
        out = await recommend_prerequisite_gaps(_fake_session(), _UID, _CONCEPT_C)
        assert [g.concept_id for g in out] == [pre_b, pre_a]  # 같은 depth 2 → 강도 desc


# ──────────────────────────────────────────────────────────────────────────
# ④ enrich — concept_node 메타·미적재 None·orphan·단일 호출(N+1 0)
# ──────────────────────────────────────────────────────────────────────────
class TestEnrichment:
    async def test_attaches_node_meta_single_call(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        pre_a = uuid.uuid4()
        _patch_prereqs(monkeypatch, [_row(cid=pre_a, code=_UC_PRE_A)])
        _patch_diagnoses(
            monkeypatch, [_diagnosis(cid=pre_a, code=_UC_PRE_A, bkt=0.2, proxy=0.3)]
        )
        cap = _patch_meta(
            monkeypatch,
            {
                _UC_PRE_A: ConceptNodeMeta(
                    name_ko="일차함수", domain="[중]함수", review_status="reviewed"
                )
            },
        )
        out = await recommend_prerequisite_gaps(_fake_session(), _UID, _CONCEPT_C)
        assert out[0].name_ko == "일차함수"
        assert out[0].domain == "[중]함수"
        assert out[0].review_status == "reviewed"
        assert out[0].edge_strength == 0.8
        assert cap["calls"] == 1
        assert cap["concept_ids"] == [_UC_PRE_A]

    async def test_missing_meta_is_none_graceful(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        pre_a = uuid.uuid4()
        _patch_prereqs(monkeypatch, [_row(cid=pre_a, code=_UC_PRE_A)])
        _patch_diagnoses(
            monkeypatch, [_diagnosis(cid=pre_a, code=_UC_PRE_A, bkt=0.2, proxy=0.3)]
        )
        _patch_meta(monkeypatch, {})  # 메타 미적재
        out = await recommend_prerequisite_gaps(_fake_session(), _UID, _CONCEPT_C)
        assert out[0].name_ko is None
        assert out[0].domain is None
        assert out[0].review_status is None
        assert out[0].concept_code == _UC_PRE_A  # 추천은 유지

    async def test_orphan_no_uc_skips_meta(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        pre_a = uuid.uuid4()
        _patch_prereqs(monkeypatch, [_row(cid=pre_a, code=None)])  # orphan(UC 없음)
        _patch_diagnoses(
            monkeypatch, [_diagnosis(cid=pre_a, code=None, bkt=0.2, proxy=0.3)]
        )
        cap = _patch_meta(monkeypatch)
        out = await recommend_prerequisite_gaps(_fake_session(), _UID, _CONCEPT_C)
        assert out[0].concept_code is None
        assert out[0].name_ko is None
        assert cap["calls"] == 0  # UC 없으면 메타 조회 생략


# ──────────────────────────────────────────────────────────────────────────
# ⑤ reviewed_only 게이팅 — reviewed만·메타 없으면 보수적 제외
# ──────────────────────────────────────────────────────────────────────────
class TestReviewedOnlyGating:
    async def test_gates_pending_and_missing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        pre_a, pre_b, pre_c = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        _patch_prereqs(
            monkeypatch,
            [
                _row(cid=pre_a, code=_UC_PRE_A),
                _row(cid=pre_b, code=_UC_PRE_B),
                _row(cid=pre_c, code="UC.x.y.z"),  # 메타 없음
            ],
        )
        _patch_diagnoses(
            monkeypatch,
            [
                _diagnosis(cid=pre_a, code=_UC_PRE_A, bkt=0.1, proxy=0.2),
                _diagnosis(cid=pre_b, code=_UC_PRE_B, bkt=0.15, proxy=0.2),
                _diagnosis(cid=pre_c, code="UC.x.y.z", bkt=0.05, proxy=0.1),
            ],
        )
        _patch_meta(
            monkeypatch,
            {
                _UC_PRE_A: ConceptNodeMeta(name_ko="A", domain="d", review_status="reviewed"),
                _UC_PRE_B: ConceptNodeMeta(name_ko="B", domain="d", review_status="pending"),
            },
        )
        out = await recommend_prerequisite_gaps(
            _fake_session(), _UID, _CONCEPT_C, reviewed_only=True
        )
        assert [g.concept_id for g in out] == [pre_a]  # pending·메타 없음 제외

    async def test_default_keeps_all_recall(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        pre_a, pre_b = uuid.uuid4(), uuid.uuid4()
        _patch_prereqs(
            monkeypatch,
            [_row(cid=pre_a, code=_UC_PRE_A), _row(cid=pre_b, code=_UC_PRE_B)],
        )
        _patch_diagnoses(
            monkeypatch,
            [
                _diagnosis(cid=pre_a, code=_UC_PRE_A, bkt=0.1, proxy=0.2),
                _diagnosis(cid=pre_b, code=_UC_PRE_B, bkt=0.15, proxy=0.2),
            ],
        )
        _patch_meta(
            monkeypatch,
            {_UC_PRE_A: ConceptNodeMeta(name_ko="A", domain="d", review_status="pending")},
        )
        out = await recommend_prerequisite_gaps(_fake_session(), _UID, _CONCEPT_C)
        assert {g.concept_id for g in out} == {pre_a, pre_b}  # 기본 False·둘 다


# ──────────────────────────────────────────────────────────────────────────
# ⑥ redaction — 스키마에 본문 필드 부재
# ──────────────────────────────────────────────────────────────────────────
def test_gap_schema_has_only_safe_fields() -> None:
    fields = set(PrerequisiteGap.model_fields)
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
        "edge_strength",
        "depth",  # 다단계 traversal — 그래프 구조 메타(안전·본문 아님)
    }
    assert fields == expected
    assert "description" not in fields
    assert "formal_definition" not in fields
    assert "intuitive_explanation" not in fields
    assert "evidence" not in fields


def test_row_dataclass_has_only_safe_fields() -> None:
    # PrerequisiteRow도 그래프 구조 값만(본문 슬롯 부재·redaction). depth 추가 정확 일치.
    import dataclasses

    fields = {f.name for f in dataclasses.fields(PrerequisiteRow)}
    assert fields == {"concept_id", "concept_code", "name_ko", "edge_strength", "depth"}


async def test_depth_propagates_row_to_gap(monkeypatch: pytest.MonkeyPatch) -> None:
    # PrerequisiteRow.depth가 PrerequisiteGap.depth로 그대로 흐른다(선수 거리 노출).
    pre_a = uuid.uuid4()
    _patch_prereqs(monkeypatch, [_row(cid=pre_a, code=_UC_PRE_A, depth=2)])
    _patch_diagnoses(monkeypatch, [_diagnosis(cid=pre_a, code=_UC_PRE_A, bkt=0.2, proxy=0.3)])
    _patch_meta(monkeypatch)
    out = await recommend_prerequisite_gaps(
        _fake_session(), _UID, _CONCEPT_C, max_depth=2
    )
    assert out[0].depth == 2
