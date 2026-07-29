"""L2 선수개념 추천 — `prerequisite_recommendation` 단위테스트 (hermetic·PG 불요).

원자그래프 소비 선수 슬1(S0-4d·runtime truth=원자). `recommend_prerequisite_gaps`는 두 좌석을
*조합*한다:
  ① `fetch_prerequisites`(이 모듈·concept_edge to==C→from traversal + **원자 축 OUTER JOIN**) —
     선수 조회와 안전 메타를 한 쿼리로 가져온다(ARCH-13)
  ② `compute_concept_diagnoses`(L2·BKT/IRT) — 선수 mastery lookup

둘을 *패치*해 PG 없이 좌석 *배선*만 못 박는다(실 SQL traversal·진단·조인은 통합 몫):
  - 선수 traversal 방향(to==C→from)·강도 desc(concept_edge 불변)
  - weak_only(막힌 선수만·미측정 제외/포함)·임계 경계
  - 정렬(weakness asc=root blocker 먼저·tie는 depth asc → edge_strength desc)
  - enrich(name_ko·domain(←원자 subject_area)·review_status)가 traversal 행에서 옴
  - **원자 축 울타리**(ARCH-13): `atom_meta is None`(=축 밖)이면 `reviewed_only`와 무관하게 제외되고
    `off_atom_axis`로 계상 — 조용한 탈락 0. 사유가 `not_reviewed`와 섞이지 않는다.
  - reviewed_only 게이팅(축 안·검수 전만 대상)
  - redaction(스키마에 본문 필드 부재)
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, cast

import pytest
import whymath_backend.l2.prerequisite_recommendation as prq_mod
from sqlalchemy.ext.asyncio import AsyncSession
from whymath_backend.l1.atom_graph.atom_node_projection import AtomNodeMeta
from whymath_backend.l2.concept_diagnosis import Agreement, ConceptDiagnosis
from whymath_backend.l2.prerequisite_recommendation import (
    PrerequisiteGap,
    PrerequisiteRow,
    recommend_prerequisite_gaps,
    recommend_prerequisite_gaps_detailed,
)

_UID = uuid.uuid4()
_CONCEPT_C = uuid.uuid4()  # 약개념(후행)
_UC_PRE_A = "UC.alg.afunction.linear"
_UC_PRE_B = "UC.alg.aset.basic"

# 기본 축-안 메타 — 원자 메타 적재는 review_status를 상수 'ai_estimated'로 박는다(실제 운용값).
_ON_AXIS = AtomNodeMeta(name_ko="선수개념", subject_area="[중]함수", review_status="ai_estimated")


def _meta(*, name: str = "A", area: str | None = "d", review: str = "reviewed") -> AtomNodeMeta:
    return AtomNodeMeta(name_ko=name, subject_area=area, review_status=review)


def _row(
    *,
    cid: uuid.UUID,
    code: str | None,
    name: str | None = "선수개념",
    edge_strength: float | None = 0.8,
    depth: int = 1,
    atom_meta: AtomNodeMeta | None = _ON_AXIS,
) -> PrerequisiteRow:
    """선수 행 — `atom_meta` 기본값은 *축 안*(대부분 테스트의 관심사가 축이 아니므로).

    축 울타리를 시험하는 테스트만 `atom_meta=None`(축 밖)을 명시한다.
    """
    return PrerequisiteRow(
        concept_id=cid,
        concept_code=code,
        name_ko=name,
        edge_strength=edge_strength,
        depth=depth,
        atom_meta=atom_meta,
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


def _patch_prereqs(monkeypatch: pytest.MonkeyPatch, rows: list[PrerequisiteRow]) -> dict[str, Any]:
    """`fetch_prerequisites`를 패치 — traversal 결과를 제어·호출 인자(concept_id·max_depth) 기록.

    실 재귀 CTE·원자 축 OUTER JOIN은 통합 테스트(`test_prerequisite_traversal_integration.py`)와
    컴파일 SQL 거버넌스(`test_atom_axis_fence_governance.py`) 몫이고, 여기선 다양한 depth·축 상태의
    PrerequisiteRow를 canned로 주입해 recommend 배선(필터·정렬·울타리·게이팅)만 못 박는다.
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


def _patch_diagnoses(monkeypatch: pytest.MonkeyPatch, diagnoses: list[ConceptDiagnosis]) -> None:
    async def _fake(_session: AsyncSession, _user_id: uuid.UUID) -> list[ConceptDiagnosis]:
        return diagnoses

    monkeypatch.setattr(prq_mod, "compute_concept_diagnoses", _fake)


# ──────────────────────────────────────────────────────────────────────────
# ① 선수 traversal 방향 — fetch_prerequisites가 약개념 concept_id로 호출됨
# ──────────────────────────────────────────────────────────────────────────
class TestTraversalDirection:
    async def test_passes_concept_id_to_traversal(self, monkeypatch: pytest.MonkeyPatch) -> None:
        captured = _patch_prereqs(monkeypatch, [])
        _patch_diagnoses(monkeypatch, [])
        out = await recommend_prerequisite_gaps(_fake_session(), _UID, _CONCEPT_C)
        assert out == []
        # traversal이 후행 개념 C(concept_id)로 호출(to==C→from 방향은 fetch_prerequisites 책임).
        assert captured["concept_id"] == _CONCEPT_C
        assert captured["calls"] == 1
        # 기본 max_depth=1(직접 선수만·기존 1-hop 계약·후방 호환)이 전달됨.
        assert captured["max_depth"] == 1

    async def test_forwards_max_depth_to_traversal(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # max_depth는 fetch_prerequisites(재귀 CTE bound)로 그대로 전달된다(다단계 traversal).
        captured = _patch_prereqs(monkeypatch, [])
        _patch_diagnoses(monkeypatch, [])
        await recommend_prerequisite_gaps(_fake_session(), _UID, _CONCEPT_C, max_depth=3)
        assert captured["max_depth"] == 3

    async def test_no_prerequisites_short_circuits(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _patch_prereqs(monkeypatch, [])
        _patch_diagnoses(monkeypatch, [])
        result = await recommend_prerequisite_gaps_detailed(_fake_session(), _UID, _CONCEPT_C)
        assert result.gaps == []
        # 선수 0건이면 제외도 0건(무엇도 버려지지 않았다 — 진짜로 선수가 없는 경우).
        assert result.exclusions.total == 0


# ──────────────────────────────────────────────────────────────────────────
# ② weak_only — 막힌 선수만·미측정 제외/포함·임계 경계
# ──────────────────────────────────────────────────────────────────────────
class TestWeakOnly:
    async def test_keeps_weak_prerequisites_only(self, monkeypatch: pytest.MonkeyPatch) -> None:
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
        result = await recommend_prerequisite_gaps_detailed(_fake_session(), _UID, _CONCEPT_C)
        assert [g.concept_id for g in result.gaps] == [pre_a]
        assert result.gaps[0].weakness == 0.3
        # 강개념은 축 밖이 아니라 *안 막힌* 것 — not_weak로 계상(사유가 섞이지 않는다).
        assert result.exclusions.not_weak == 1
        assert result.exclusions.off_atom_axis == 0

    async def test_unmeasured_excluded_when_weak_only(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # 측정 없는 선수(진단 맵에 없음)는 weak_only=True면 제외(약점 근거 없음).
        pre_a, pre_b = uuid.uuid4(), uuid.uuid4()
        _patch_prereqs(
            monkeypatch,
            [_row(cid=pre_a, code=_UC_PRE_A), _row(cid=pre_b, code=_UC_PRE_B)],
        )
        _patch_diagnoses(monkeypatch, [_diagnosis(cid=pre_a, code=_UC_PRE_A, bkt=0.2, proxy=0.3)])
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
        _patch_diagnoses(monkeypatch, [_diagnosis(cid=pre_a, code=_UC_PRE_A, bkt=0.2, proxy=0.3)])
        out = await recommend_prerequisite_gaps(_fake_session(), _UID, _CONCEPT_C, weak_only=False)
        ids = {g.concept_id for g in out}
        assert ids == {pre_a, pre_b}
        b = next(g for g in out if g.concept_id == pre_b)
        assert b.weakness is None  # 미측정
        assert b.bkt_mastery is None
        assert b.agreement == "insufficient"

    async def test_threshold_boundary_excludes_equal(self, monkeypatch: pytest.MonkeyPatch) -> None:
        pre_a = uuid.uuid4()
        _patch_prereqs(monkeypatch, [_row(cid=pre_a, code=_UC_PRE_A)])
        _patch_diagnoses(monkeypatch, [_diagnosis(cid=pre_a, code=_UC_PRE_A, bkt=0.7, proxy=0.8)])
        out = await recommend_prerequisite_gaps(
            _fake_session(), _UID, _CONCEPT_C, mastery_threshold=0.7
        )
        assert out == []  # weakness 0.7 == threshold → 미만 아님 → 제외


# ──────────────────────────────────────────────────────────────────────────
# ③ 정렬 — weakness asc(root blocker 먼저)·tie는 depth asc → edge_strength desc
# ──────────────────────────────────────────────────────────────────────────
class TestSorting:
    async def test_weakest_prerequisite_first(self, monkeypatch: pytest.MonkeyPatch) -> None:
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
        out = await recommend_prerequisite_gaps(_fake_session(), _UID, _CONCEPT_C)
        assert [g.concept_id for g in out] == [pre_a, pre_b]  # 가장 약한 선수 먼저

    async def test_tie_breaks_on_edge_strength_desc(self, monkeypatch: pytest.MonkeyPatch) -> None:
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
        out = await recommend_prerequisite_gaps(_fake_session(), _UID, _CONCEPT_C)
        assert [g.concept_id for g in out] == [pre_near, pre_far]  # depth 1 먼저(강도보다 우선)
        assert [g.depth for g in out] == [1, 2]

    async def test_tie_same_depth_breaks_on_strength(self, monkeypatch: pytest.MonkeyPatch) -> None:
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
        out = await recommend_prerequisite_gaps(_fake_session(), _UID, _CONCEPT_C)
        assert [g.concept_id for g in out] == [pre_b, pre_a]  # 같은 depth 2 → 강도 desc


# ──────────────────────────────────────────────────────────────────────────
# ④ enrich — 원자 축 메타가 traversal 행에서 온다(별도 엔진 조회 0)
# ──────────────────────────────────────────────────────────────────────────
class TestEnrichment:
    async def test_attaches_atom_meta_from_row(self, monkeypatch: pytest.MonkeyPatch) -> None:
        pre_a = uuid.uuid4()
        _patch_prereqs(
            monkeypatch,
            [
                _row(
                    cid=pre_a,
                    code=_UC_PRE_A,
                    atom_meta=_meta(name="일차함수", area="[중]함수", review="reviewed"),
                )
            ],
        )
        _patch_diagnoses(monkeypatch, [_diagnosis(cid=pre_a, code=_UC_PRE_A, bkt=0.2, proxy=0.3)])
        out = await recommend_prerequisite_gaps(_fake_session(), _UID, _CONCEPT_C)
        assert out[0].name_ko == "일차함수"
        assert out[0].domain == "[중]함수"
        assert out[0].review_status == "reviewed"
        assert out[0].edge_strength == 0.8

    async def test_orphan_without_code_is_off_axis(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # code 없는 orphan은 원자 축에 있을 수 없다 — traversal OUTER JOIN이 미스라 atom_meta None.
        pre_a = uuid.uuid4()
        _patch_prereqs(monkeypatch, [_row(cid=pre_a, code=None, atom_meta=None)])
        _patch_diagnoses(monkeypatch, [_diagnosis(cid=pre_a, code=None, bkt=0.2, proxy=0.3)])
        result = await recommend_prerequisite_gaps_detailed(_fake_session(), _UID, _CONCEPT_C)
        assert result.gaps == []
        assert result.exclusions.off_atom_axis == 1


# ──────────────────────────────────────────────────────────────────────────
# ⑤ 원자 축 울타리 (ARCH-13) — 축 밖은 항상 제외·사유 분리 계상·조용한 탈락 0
# ──────────────────────────────────────────────────────────────────────────
class TestAtomAxisFence:
    async def test_off_axis_excluded_even_without_reviewed_only(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # 구 437 UC가 traversal로 흘러도(atom_node 미스) runtime truth=원자라 항상 제외한다.
        # reviewed_only=False(기본·recall 보존 경로)에서도 그렇다 — 이것이 ARCH-13의 행동 변화.
        pre_on, pre_off = uuid.uuid4(), uuid.uuid4()
        _patch_prereqs(
            monkeypatch,
            [
                _row(cid=pre_on, code=_UC_PRE_A),
                _row(cid=pre_off, code="UC-LEGACY-437", atom_meta=None),
            ],
        )
        _patch_diagnoses(
            monkeypatch,
            [
                _diagnosis(cid=pre_on, code=_UC_PRE_A, bkt=0.2, proxy=0.3),
                _diagnosis(cid=pre_off, code="UC-LEGACY-437", bkt=0.1, proxy=0.2),
            ],
        )
        result = await recommend_prerequisite_gaps_detailed(_fake_session(), _UID, _CONCEPT_C)
        assert [g.concept_id for g in result.gaps] == [pre_on]
        assert result.exclusions.off_atom_axis == 1
        assert result.exclusions.not_reviewed == 0  # 사유가 섞이지 않는다

    async def test_fence_is_discriminative(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """**변별력** — 같은 요청에서 `atom_meta` 유무만 바꾸면 판정이 실제로 뒤집힌다.

        울타리가 "항상 통과"·"항상 차단"하는 위장 검증이 아님을 보인다(REND-01 선례).
        두 호출은 행 객체를 따로 만든다 — 하나를 재사용하면 무엇이 판정을 바꿨는지 흐려진다.
        """
        pre = uuid.uuid4()
        diag = [_diagnosis(cid=pre, code=_UC_PRE_A, bkt=0.2, proxy=0.3)]

        _patch_prereqs(monkeypatch, [_row(cid=pre, code=_UC_PRE_A, atom_meta=None)])
        _patch_diagnoses(monkeypatch, diag)
        off = await recommend_prerequisite_gaps_detailed(_fake_session(), _UID, _CONCEPT_C)

        _patch_prereqs(monkeypatch, [_row(cid=pre, code=_UC_PRE_A, atom_meta=_ON_AXIS)])
        _patch_diagnoses(monkeypatch, diag)
        on = await recommend_prerequisite_gaps_detailed(_fake_session(), _UID, _CONCEPT_C)

        assert off.gaps == [] and off.exclusions.off_atom_axis == 1
        assert [g.concept_id for g in on.gaps] == [pre] and on.exclusions.off_atom_axis == 0

    async def test_exclusions_are_logged_with_counts_only(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        # 제외가 있으면 구조화 로그 1줄 — 카운트만 싣고 code·user_id는 싣지 않는다(개인정보).
        pre_off = uuid.uuid4()
        _patch_prereqs(monkeypatch, [_row(cid=pre_off, code="UC-LEGACY-437", atom_meta=None)])
        _patch_diagnoses(
            monkeypatch, [_diagnosis(cid=pre_off, code="UC-LEGACY-437", bkt=0.1, proxy=0.2)]
        )
        with caplog.at_level(logging.INFO, logger="whymath.l2.prerequisite_recommendation"):
            await recommend_prerequisite_gaps(_fake_session(), _UID, _CONCEPT_C)
        messages = [r.getMessage() for r in caplog.records]
        assert any("off_atom_axis=1" in m for m in messages)
        assert not any("UC-LEGACY-437" in m or str(_UID) in m for m in messages)

    async def test_no_log_when_nothing_excluded(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        # 정상 경로는 침묵 — 제외 0건이면 로그를 남기지 않는다(소음 방지·위 테스트의 변별력 짝).
        pre = uuid.uuid4()
        _patch_prereqs(monkeypatch, [_row(cid=pre, code=_UC_PRE_A)])
        _patch_diagnoses(monkeypatch, [_diagnosis(cid=pre, code=_UC_PRE_A, bkt=0.2, proxy=0.3)])
        with caplog.at_level(logging.INFO, logger="whymath.l2.prerequisite_recommendation"):
            out = await recommend_prerequisite_gaps(_fake_session(), _UID, _CONCEPT_C)
        assert len(out) == 1
        assert caplog.records == []

    async def test_thin_wrapper_matches_detailed_gaps(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # 기존 계약(list 반환)은 `_detailed`의 gaps와 동치 — 로직 분기 0(본체는 하나).
        pre = uuid.uuid4()
        rows = [_row(cid=pre, code=_UC_PRE_A)]
        diag = [_diagnosis(cid=pre, code=_UC_PRE_A, bkt=0.2, proxy=0.3)]
        _patch_prereqs(monkeypatch, rows)
        _patch_diagnoses(monkeypatch, diag)
        thin = await recommend_prerequisite_gaps(_fake_session(), _UID, _CONCEPT_C)
        detailed = await recommend_prerequisite_gaps_detailed(_fake_session(), _UID, _CONCEPT_C)
        assert thin == detailed.gaps


# ──────────────────────────────────────────────────────────────────────────
# ⑥ reviewed_only 게이팅 — 축 안·검수 전만 대상(축 밖과 사유 분리)
# ──────────────────────────────────────────────────────────────────────────
class TestReviewedOnlyGating:
    async def test_gates_pending_separately_from_off_axis(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        pre_a, pre_b, pre_c = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        _patch_prereqs(
            monkeypatch,
            [
                _row(cid=pre_a, code=_UC_PRE_A, atom_meta=_meta(name="A", review="reviewed")),
                _row(cid=pre_b, code=_UC_PRE_B, atom_meta=_meta(name="B", review="pending")),
                _row(cid=pre_c, code="UC.x.y.z", atom_meta=None),  # 축 밖
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
        result = await recommend_prerequisite_gaps_detailed(
            _fake_session(), _UID, _CONCEPT_C, reviewed_only=True
        )
        assert [g.concept_id for g in result.gaps] == [pre_a]
        # 같은 "제외"라도 사유가 다르다 — 뭉뚱그리면 무엇이 문제인지 알 수 없다.
        assert result.exclusions.off_atom_axis == 1  # pre_c
        assert result.exclusions.not_reviewed == 1  # pre_b

    async def test_default_keeps_all_on_axis_recall(self, monkeypatch: pytest.MonkeyPatch) -> None:
        pre_a, pre_b = uuid.uuid4(), uuid.uuid4()
        _patch_prereqs(
            monkeypatch,
            [
                _row(cid=pre_a, code=_UC_PRE_A, atom_meta=_meta(name="A", review="pending")),
                _row(cid=pre_b, code=_UC_PRE_B),
            ],
        )
        _patch_diagnoses(
            monkeypatch,
            [
                _diagnosis(cid=pre_a, code=_UC_PRE_A, bkt=0.1, proxy=0.2),
                _diagnosis(cid=pre_b, code=_UC_PRE_B, bkt=0.15, proxy=0.2),
            ],
        )
        out = await recommend_prerequisite_gaps(_fake_session(), _UID, _CONCEPT_C)
        # 기본 False — 축 안이면 검수 전이어도 남긴다(recall 보존).
        assert {g.concept_id for g in out} == {pre_a, pre_b}


# ──────────────────────────────────────────────────────────────────────────
# ⑦ redaction — 스키마에 본문 필드 부재
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
    # PrerequisiteRow도 그래프 구조 값 + 원자 축 안전 메타만(본문 슬롯 부재·redaction).
    import dataclasses

    fields = {f.name for f in dataclasses.fields(PrerequisiteRow)}
    assert fields == {
        "concept_id",
        "concept_code",
        "name_ko",
        "edge_strength",
        "depth",
        "atom_meta",
    }
    # atom_meta가 싣는 것도 안전 3종뿐 — 본문 컬럼이 atom_node에 없어 구조적으로 흐를 수 없다.
    assert {f.name for f in dataclasses.fields(AtomNodeMeta)} == {
        "name_ko",
        "subject_area",
        "review_status",
    }


async def test_depth_propagates_row_to_gap(monkeypatch: pytest.MonkeyPatch) -> None:
    # PrerequisiteRow.depth가 PrerequisiteGap.depth로 그대로 흐른다(선수 거리 노출).
    pre_a = uuid.uuid4()
    _patch_prereqs(monkeypatch, [_row(cid=pre_a, code=_UC_PRE_A, depth=2)])
    _patch_diagnoses(monkeypatch, [_diagnosis(cid=pre_a, code=_UC_PRE_A, bkt=0.2, proxy=0.3)])
    out = await recommend_prerequisite_gaps(_fake_session(), _UID, _CONCEPT_C, max_depth=2)
    assert out[0].depth == 2


# ──────────────────────────────────────────────────────────────────────────
# ⑧ 원자 축 동결(S0-4d 승계) — enrich 값 소스가 원자 subject_area·키 축 불변
# ──────────────────────────────────────────────────────────────────────────
class TestAtomAxisFrozen:
    async def test_domain_field_carries_atom_subject_area(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # S0-4d 동결: 결과 `domain` 필드는 원자 `subject_area` 값을 담는다(값 소스 교체·필드명
        # 유지). concept_edge traversal·concept_code 키 축은 불변(rekey 0). ARCH-13은 그 메타가
        # *어느 엔진에서 오는가*만 바꿨다(별도 sync 엔진 → 같은 async 쿼리의 OUTER JOIN).
        pre_a = uuid.uuid4()
        _patch_prereqs(
            monkeypatch,
            [
                _row(
                    cid=pre_a,
                    code=_UC_PRE_A,
                    atom_meta=_meta(name="집합", area="[중]집합과명제", review="reviewed"),
                )
            ],
        )
        _patch_diagnoses(monkeypatch, [_diagnosis(cid=pre_a, code=_UC_PRE_A, bkt=0.2, proxy=0.3)])
        out = await recommend_prerequisite_gaps(_fake_session(), _UID, _CONCEPT_C)
        assert out[0].domain == "[중]집합과명제"  # domain 값이 원자 subject_area
        assert out[0].name_ko == "집합"
        assert out[0].concept_code == _UC_PRE_A  # 키 축 불변(rekey 0)
