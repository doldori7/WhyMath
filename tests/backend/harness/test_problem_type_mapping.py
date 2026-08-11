"""생성기 identity → problem_type_id 매핑표(S3-27·PB-07) — 골든 분포·계보 분류·변별력·
만료 계약 테스트.

**변별력**(CLAUDE.md "변별력 없는 검증 스텝 금지"): `TestMutationDetection`이 매핑표 항목 1개를
일부러 틀리게 바꾼 뒤 골든 분포 대조가 *실제로* 어긋남을 직접 실행해 증명한다(오매핑 주입 → 검사
실패, 복원 → 검사 통과 — 두 상태 모두 이 테스트 안에서 실행·확인한다).

실제 저장소의 코퍼스 파일(`data/corpus/problem_bank_*/problems.jsonl` — 2026-07-30 S3-27 백필
+ 2026-08-11 PB-07 rephrased 계보 백필 결과물)을 직접 읽어 전수 대조한다 — 합성 fixture가
아니라 *실제 산출물*이 골든 값과 일치하는지 보는 것이 이 매핑표의 유일한 존재 이유이기 때문이다.

**제외 만료 계약**(PB-07·`TestExclusionExpiryContract`): `EXCLUDED_CORPORA` 좌석의 각 항목이
①실재하는 backlog 태스크를 참조하는지 ②참조 태스크가 done인데 항목이 방치되지 않았는지를
상시 대조한다 — `ops/provenance_audit`의 `TestGrandfatherExpiryContract`(ARCH-25)와 동형.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pytest
import yaml

from whymath_backend.harness import problem_type_mapping as ptm
from whymath_backend.schema.enums import RelationType

# tests/backend/harness/test_x.py → parents[3] = repo 루트(harness→backend→tests→root).
_REPO_ROOT = Path(__file__).resolve().parents[3]
_CORPUS_ROOT = _REPO_ROOT / "data" / "corpus"
_PROBLEM_TYPES_PATH = _CORPUS_ROOT / "problem_type_graph_v1" / "problem_types.jsonl"

# 골든 분포(2026-07-30 S3-27 백필 실측 — `harness/problem_type_backfill.py` 산출물과 정합).
# 이 상수가 어긋나면 매핑표가 바뀌었다는 뜻이다 — 의도적 변경이면 이 상수도 함께 갱신할 것.
_GOLDEN_CORPUS_TYPE_TOTALS: dict[str, dict[str, int]] = {
    ptm.CORPUS_V1: {
        ptm.PTYPE_SOLVE_FOR_UNKNOWN: 2,
        ptm.PTYPE_DETERMINE_COEFFICIENT: 1,
        ptm.PTYPE_COUNT_SOLUTIONS: 1,
    },
    # QUAD-EQ(184)+CALC-TANGENT(40)+EXP-EQ(25)+LOG-EQ(20)+TRIG-EQ(12)=281(solve) ·
    # CALC-EXTREMUM(40)+VALUE(40)+MC(30)+IRR(30)=140(optimize) ·
    # ARITH-SEQ(60)+GEO-SEQ(30)+ARITH-SUM(45)+GEO-SUM(20)+TRIG-VAL(13)=168(evaluate) · IND-SEQ=30.
    # (QUAD-EQ 185→184: 2026-08-11 QUAL-02가 `wm-skel-92cd1ba2bbf5`를 실중복 은퇴 —
    #  docs/data/problem_duplicate_disposition_2026-08.md)
    ptm.CORPUS_GENERATED_V0: {
        ptm.PTYPE_SOLVE_FOR_UNKNOWN: 281,
        ptm.PTYPE_OPTIMIZE_EXTREMUM: 140,
        ptm.PTYPE_EVALUATE_EXPRESSION: 168,
        ptm.PTYPE_GENERALIZE_PATTERN: 30,
    },
    ptm.CORPUS_CONCEPTUAL_V0: {
        ptm.PTYPE_COUNT_SOLUTIONS: 96,  # 4밴드 × 24
        ptm.PTYPE_VERIFY_CLAIM: 264,  # 11밴드 × 24
    },
    ptm.CORPUS_KILLER_V0: {
        ptm.PTYPE_EVALUATE_EXPRESSION: 120,
    },
    # 42밴드×24=1008(evaluate) · transpose-no-sign-change=24(solve) ·
    # combination-no-denominator·same-item-permutation-no-divide=2밴드×24=48(enumerate).
    ptm.CORPUS_MISCONCEPTION_MC_V0: {
        ptm.PTYPE_EVALUATE_EXPRESSION: 1008,
        ptm.PTYPE_SOLVE_FOR_UNKNOWN: 24,
        ptm.PTYPE_ENUMERATE_CASES: 48,
    },
    ptm.CORPUS_PROBABILITY_FINITE_V0: {
        ptm.PTYPE_EVALUATE_EXPRESSION: 26,
        ptm.PTYPE_ENUMERATE_CASES: 8,
    },
}

# 계보 분류 골든(2026-08-11 PB-07 실측 — 부모는 전건 generated_v0):
# QUAD-EQ(146)+CALC-TANGENT(40)+EXP-EQ(21)+LOG-EQ(14)=221(solve) ·
# CALC-EXTREMUM(37)+CALC-EXTREMUM-VALUE(34)+CALC-EXTREMUM-MC(26)=97(optimize) ·
# ARITH-SEQ(60)+GEO-SEQ(30)+TRIG-VAL(13)=103(evaluate).
_GOLDEN_REPHRASED_TYPE_TOTALS: dict[str, int] = {
    ptm.PTYPE_SOLVE_FOR_UNKNOWN: 221,
    ptm.PTYPE_OPTIMIZE_EXTREMUM: 97,
    ptm.PTYPE_EVALUATE_EXPRESSION: 103,
}

_GOLDEN_TOTAL_TAGGED = 2638  # 직접 2,217 + 계보 421 — 7종 전건(PB-07이 rephrased 제외 해제)
_GOLDEN_LINEAGE_TOTAL = 421  # rephrased_v0 총량(QUAL-02 은퇴 9건 반영 — 429→421)


def _load_corpus_lines(name: str) -> list[dict[str, object]]:
    path = _CORPUS_ROOT / name / "problems.jsonl"
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def _distribution_for(name: str) -> Counter[str]:
    """코퍼스 1종의 실제 레코드에 `classify_record`를 적용한 유형별 분포(빈 리스트는 무시)."""
    counts: Counter[str] = Counter()
    for record in _load_corpus_lines(name):
        for ptype in ptm.classify_record(name, record):
            counts[ptype] += 1
    return counts


def _parent_type_index() -> dict[str, list[str]]:
    """직접 분류 6종의 slug → 유도 유형 색인 — 계보 분류 입력
    (`problem_type_backfill._build_parent_type_index`와 동형·실 코퍼스는 slug 중복 0건)."""
    index: dict[str, list[str]] = {}
    for name in ptm.TARGET_CORPORA:
        for record in _load_corpus_lines(name):
            slug = record.get("slug")
            assert isinstance(slug, str)
            assert slug not in index, f"slug 중복: {slug} — 계보 조인 전제 붕괴"
            index[slug] = ptm.classify_record(name, record)
    return index


def _lineage_distribution_for(name: str) -> Counter[str]:
    """계보 코퍼스 1종의 실제 레코드에 `classify_rephrased_record`를 적용한 유형별 분포."""
    index = _parent_type_index()
    counts: Counter[str] = Counter()
    for record in _load_corpus_lines(name):
        for ptype in ptm.classify_rephrased_record(record, index):
            counts[ptype] += 1
    return counts


class TestGoldenDistribution:
    """매핑표를 실제 코퍼스 전량에 적용한 결과가 골든 값과 정확히 일치하는지 — 정상 매핑 대조."""

    @pytest.mark.parametrize("corpus_name", list(_GOLDEN_CORPUS_TYPE_TOTALS))
    def test_corpus_distribution_matches_golden(self, corpus_name: str) -> None:
        assert dict(_distribution_for(corpus_name)) == _GOLDEN_CORPUS_TYPE_TOTALS[corpus_name]

    def test_rephrased_distribution_matches_golden(self) -> None:
        # PB-07 계보 백필 골든 — 부모(generated_v0) 유형 승계 결과가 실측 골든과 정확히 일치.
        assert dict(_lineage_distribution_for(ptm.CORPUS_REPHRASED_V0)) == (
            _GOLDEN_REPHRASED_TYPE_TOTALS
        )

    def test_total_tagged_matches_golden(self) -> None:
        # 직접 6종(classify_record) + 계보 1종(classify_rephrased_record) = 7종 전건 2,638.
        direct = sum(
            sum(dist.values()) for name in ptm.TARGET_CORPORA for dist in [_distribution_for(name)]
        )
        lineage = sum(
            sum(dist.values())
            for name in ptm.LINEAGE_CORPORA
            for dist in [_lineage_distribution_for(name)]
        )
        assert direct + lineage == _GOLDEN_TOTAL_TAGGED

    def test_rephrased_v0_is_lineage_target_not_excluded(self) -> None:
        # PB-07: rephrased는 직접 분류 대상이 아니라 *계보 분류* 대상이며, 더 이상 제외가 아니다
        # (구 사유 "S4-14 미착지" 소멸 — problem_bank_gap_review_r3.md §3 G2).
        assert ptm.CORPUS_REPHRASED_V0 not in ptm.TARGET_CORPORA
        assert ptm.LINEAGE_CORPORA == (ptm.CORPUS_REPHRASED_V0,)
        assert ptm.EXCLUDED_CORPORA == {}  # 제외 좌석은 비었다 — 만료 계약이 재등재를 규율.
        assert len(_load_corpus_lines(ptm.CORPUS_REPHRASED_V0)) == _GOLDEN_LINEAGE_TOTAL

    def test_classify_record_returns_empty_for_lineage_corpus(self) -> None:
        # 계보 코퍼스는 단일 레코드 서명으로 분류 불가 — `classify_record`는 침묵 오분류 대신
        # 빈 리스트로 정직하게 미분류를 드러낸다(분류는 `classify_rephrased_record` 소관).
        sample = _load_corpus_lines(ptm.CORPUS_REPHRASED_V0)[0]
        assert ptm.classify_record(ptm.CORPUS_REPHRASED_V0, sample) == []


class TestMappingIntegrity:
    """매핑표 값의 구조적 정합 — 정본 카탈로그(problem_type_graph_v1)와의 대조."""

    def test_all_mapped_type_ids_exist_in_real_catalog(self) -> None:
        # 이 모듈의 PTYPE_* 상수 값이 정본 problem_types.jsonl에 실재하는지 교차 확인
        # (오탈자·정본 드리프트 방지 — 모듈 docstring의 "재정의 아님" 전제를 기계로 검증).
        catalog_ids = {
            json.loads(line)["problem_type_id"]
            for line in _PROBLEM_TYPES_PATH.read_text(encoding="utf-8").splitlines()
            if line.strip()
        }
        assert catalog_ids == ptm.ALL_PROBLEM_TYPE_IDS

    def test_no_untagged_records_in_target_corpora(self) -> None:
        # acceptance③: 대상 6개 코퍼스는 전량 태깅됨(0건 미태깅) — 실측 확인.
        for name in ptm.TARGET_CORPORA:
            records = _load_corpus_lines(name)
            untagged = sum(1 for r in records if not ptm.classify_record(name, r))
            assert untagged == 0, f"{name}에 미태깅 {untagged}건 — 매핑표 공백"

    def test_no_untagged_records_in_lineage_corpora(self) -> None:
        # PB-07 acceptance①·②: 계보 코퍼스도 전량 태깅(계보 추적 성립 421/421 — 추적 불가
        # 잔여 0건을 저장소 차원에서 동결한다. 잔여가 생기면 이 테스트가 건수를 드러낸다).
        index = _parent_type_index()
        for name in ptm.LINEAGE_CORPORA:
            records = _load_corpus_lines(name)
            untagged = sum(1 for r in records if not ptm.classify_rephrased_record(r, index))
            assert untagged == 0, f"{name}에 계보 추적 불가(미태깅) {untagged}건"

    def test_stored_rephrased_codes_match_lineage_derivation(self) -> None:
        # 저장된 problem_type_codes(PB-07 백필 산출물)가 계보 유도 값과 전건 일치 — 멱등 계약의
        # 저장소 대조판(백필 2회 실행 바이트 동일의 정적 등가물).
        index = _parent_type_index()
        for record in _load_corpus_lines(ptm.CORPUS_REPHRASED_V0):
            derived = ptm.classify_rephrased_record(record, index)
            assert record.get("problem_type_codes") == derived, record.get("slug")


class TestMutationDetection:
    """변별력 증명(acceptance⑤) — 매핑표 항목 1개를 오염시키면 골든 대조가 실제로 실패한다.

    한 테스트 안에서 ①오염 상태(불일치 확인) ②원복 상태(일치 확인) 둘 다 실행한다 —
    monkeypatch가 테스트 종료 시 자동 원복하므로 그 전에 명시적으로 두 상태를 모두 관측한다.
    """

    def test_mutated_generated_v0_entry_breaks_golden_check(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        golden = _GOLDEN_CORPUS_TYPE_TOTALS[ptm.CORPUS_GENERATED_V0]

        # 오염 전 — 정상 매핑은 골든과 일치해야 한다(대조군).
        assert dict(_distribution_for(ptm.CORPUS_GENERATED_V0)) == golden

        # 오염 — QUAD-EQ(184건 — QUAL-02 은퇴 1건 반영) 매핑을 일부러 틀린 유형으로 바꾼다.
        corrupted = dict(ptm._GENERATED_V0_UNIT_TO_TYPE)
        corrupted[("QUAD-EQ",)] = ptm.PTYPE_SKETCH_GRAPH  # 명백히 틀린 유형(방정식 풀이가 아님).
        monkeypatch.setattr(ptm, "_GENERATED_V0_UNIT_TO_TYPE", corrupted)

        mutated_distribution = dict(_distribution_for(ptm.CORPUS_GENERATED_V0))
        # 이것이 변별력의 핵심 단언 — 오매핑 주입 시 골든과 실제로 달라져야 한다(실패를 실패로
        # 잡아낸다). 이 단언 자체가 통과하지 못하면(=오염 전후가 같으면) 골든 체크가 무의미하다는
        # 뜻이라 이 테스트가 실패해야 정상이다.
        assert mutated_distribution != golden
        assert mutated_distribution[ptm.PTYPE_SKETCH_GRAPH] == 184
        assert (
            mutated_distribution[ptm.PTYPE_SOLVE_FOR_UNKNOWN]
            == golden[ptm.PTYPE_SOLVE_FOR_UNKNOWN] - 184
        )

        # 원복(monkeypatch.undo는 fixture teardown에서도 자동 실행되지만, 같은 테스트 안에서
        # "복원 후 재통과"까지 명시적으로 확인한다 — acceptance⑤가 요구하는 두 상태 모두 실행).
        monkeypatch.undo()
        assert dict(_distribution_for(ptm.CORPUS_GENERATED_V0)) == golden

    def test_mutated_misconception_kebab_entry_breaks_golden_check(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        golden = _GOLDEN_CORPUS_TYPE_TOTALS[ptm.CORPUS_MISCONCEPTION_MC_V0]
        assert dict(_distribution_for(ptm.CORPUS_MISCONCEPTION_MC_V0)) == golden

        corrupted = dict(ptm._MISCONCEPTION_MC_V0_KEBAB_TO_TYPE)
        corrupted["transpose-no-sign-change"] = ptm.PTYPE_EVALUATE_EXPRESSION  # 실제는 방정식 풀이.
        monkeypatch.setattr(ptm, "_MISCONCEPTION_MC_V0_KEBAB_TO_TYPE", corrupted)

        mutated = dict(_distribution_for(ptm.CORPUS_MISCONCEPTION_MC_V0))
        assert mutated != golden
        assert ptm.PTYPE_SOLVE_FOR_UNKNOWN not in mutated  # 24건이 evaluate-expression으로 흡수됨.
        assert mutated[ptm.PTYPE_EVALUATE_EXPRESSION] == golden[ptm.PTYPE_EVALUATE_EXPRESSION] + 24

        monkeypatch.undo()
        assert dict(_distribution_for(ptm.CORPUS_MISCONCEPTION_MC_V0)) == golden


class TestLineageClassification:
    """계보 분류(PB-07) 단위 계약 — 부모 slug 복원·유형 승계·침묵 오분류 금지."""

    def test_rel_type_variant_literal_matches_schema_enum(self) -> None:
        # `_REL_TYPE_VARIANT` 리터럴이 정본(schema/enums.py RelationType.변형)과 정확히 일치 —
        # PTYPE_* 상수의 "재정의 아님·정본 대조" 원칙과 동일한 드리프트 방지 거버넌스.
        assert ptm._REL_TYPE_VARIANT == RelationType.변형.value

    def test_parent_slug_resolved_from_single_variant_relation(self) -> None:
        record = {
            "relations": [
                {"parent_slug": "wm-skel-abc", "relation_type": "변형", "similarity_score": 1.0}
            ]
        }
        assert ptm.rephrased_parent_slug(record) == "wm-skel-abc"

    def test_parent_slug_ignores_non_variant_relations(self) -> None:
        # "유사"(S4-14 형제 태깅) 등 다른 관계 타입은 계보가 아니다 — 섞여 있어도 "변형"만 본다.
        record = {
            "relations": [
                {"parent_slug": "wm-sibling", "relation_type": "유사", "similarity_score": 0.9},
                {"parent_slug": "wm-skel-abc", "relation_type": "변형", "similarity_score": 1.0},
            ]
        }
        assert ptm.rephrased_parent_slug(record) == "wm-skel-abc"

    def test_parent_slug_none_when_no_relations_or_ambiguous(self) -> None:
        # 침묵 오분류 금지 — 0건·서로 다른 부모 2건·비정상 형태는 전부 None(미태깅).
        assert ptm.rephrased_parent_slug({}) is None
        assert ptm.rephrased_parent_slug({"relations": []}) is None
        assert ptm.rephrased_parent_slug({"relations": "not-a-list"}) is None
        two_parents = {
            "relations": [
                {"parent_slug": "wm-a", "relation_type": "변형"},
                {"parent_slug": "wm-b", "relation_type": "변형"},
            ]
        }
        assert ptm.rephrased_parent_slug(two_parents) is None

    def test_classify_inherits_parent_type_and_handles_missing_parent(self) -> None:
        record = {
            "relations": [{"parent_slug": "wm-skel-abc", "relation_type": "변형"}],
        }
        index = {"wm-skel-abc": [ptm.PTYPE_SOLVE_FOR_UNKNOWN]}
        assert ptm.classify_rephrased_record(record, index) == [ptm.PTYPE_SOLVE_FOR_UNKNOWN]
        # 색인에 부모가 없으면(계보로도 추적 불가) 빈 리스트 — 백필 리포트 untagged가 센다.
        assert ptm.classify_rephrased_record(record, {}) == []
        # 부모가 미태깅이면 자식도 미태깅(승계할 유형이 없다 — 날조 금지).
        assert ptm.classify_rephrased_record(record, {"wm-skel-abc": []}) == []

    def test_real_corpus_lineage_resolves_for_all_records(self) -> None:
        # acceptance① 동결 — 실 코퍼스 421건 전건이 "변형" 계보 1건을 갖고, 부모 slug가 직접
        # 분류 6종 색인에서 유일하게 해석된다(2026-08-11 실측: 421/421·부모 전건 generated_v0).
        index = _parent_type_index()
        records = _load_corpus_lines(ptm.CORPUS_REPHRASED_V0)
        assert len(records) == _GOLDEN_LINEAGE_TOTAL
        for record in records:
            slug = ptm.rephrased_parent_slug(record)
            assert slug is not None, f"{record.get('slug')} 계보 부재"
            assert slug in index, f"{record.get('slug')} 부모 {slug} 색인 미해석"


def _write_task_yaml(tasks_dir: Path, task_id: str, status: str) -> None:
    """백로그 태스크 YAML 최소 픽스처(만료 계약 테스트 전용) —
    `find_exclusion_expiry_violations`가 실제로 읽는 `id`·`status`만 담는다
    (`tests/backend/ops/test_provenance_audit.py` 동명 헬퍼와 동형)."""
    tasks_dir.mkdir(parents=True, exist_ok=True)
    (tasks_dir / f"{task_id}.yaml").write_text(
        yaml.safe_dump({"id": task_id, "status": status}, allow_unicode=True),
        encoding="utf-8",
    )


class TestExclusionExpiryContract:
    """제외 만료 계약(PB-07) — task_id 참조 무결성 + done 방치 트립와이어.

    `EXCLUDED_CORPORA`의 각 항목이 ①실재하는 backlog 태스크를 참조하는지 ②참조된 태스크가
    이미 done인데 항목이 방치되지 않았는지를 상시 대조한다. `ops/provenance_audit`의
    `TestGrandfatherExpiryContract`(ARCH-25)와 동형 — 같은 성격의 좌석(`EXCLUDED_CORPORA`)이
    계약 밖에 남아 rephrased 제외가 사유 소멸 후 6일 방치된 2회차 재발 방지
    (`problem_bank_gap_review_r3.md` §6-ⓑ). 자동 해제가 아니다 — 해제는 여전히 사람 판단이고,
    이 계약은 방치를 구조적으로 드러내는 트립와이어일 뿐이다.

    변별력 확인(CLAUDE.md "변별력 없는 검증 스텝 금지"): monkeypatch로 `EXCLUDED_CORPORA`를
    테스트 전용 딕셔너리로 교체해 ①②가 실제로 위반을 검출하는지(red)와, 정상 상태에서는
    검출하지 않는지(green)를 모두 확인한다 — 성공/성공 또는 실패/실패로 같은 값이 나오면
    위장이다. 실좌석 뮤테이션 red 실측(acceptance ④)은 구현 세션이 cp 백업 방식으로 별도
    수행했다(PB-07 리포트).
    """

    def test_real_excluded_corpora_reference_real_and_non_done_tasks(self) -> None:
        """저장소의 실 `EXCLUDED_CORPORA`(PB-07 해제 후 빈 딕셔너리)가 계약을 위반하지 않는다.
        비어 있으면 자명 통과 — 지금 뭔가를 잡으려는 게 아니라, 향후 항목이 재등재될 때
        방치를 기계로 드러내는 상시 트립와이어로 배선해 두는 것이 핵심이다(아래 monkeypatch
        테스트가 변별력을 실측한다). ARCH-25의 빈 `_KNOWN_GAPS` 테스트와 동형."""
        violations = ptm.find_exclusion_expiry_violations()
        assert violations == [], f"제외 만료 계약 위반: {violations}"

    def test_real_seat_is_empty_after_pb07_release(self) -> None:
        """PB-07 해제 상태 동결 — 좌석이 다시 채워지려면 ExclusionEntry(task_id 강제)를 거쳐야
        하고, 그 항목은 위 상시 테스트의 대조를 받는다(빈 상태에서도 계약 유효 — acceptance ③)."""
        assert ptm.EXCLUDED_CORPORA == {}

    def test_nonexistent_task_id_is_flagged(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """① 실존하지 않는 task_id를 가리키는 제외 항목은 위반으로 잡혀야 한다(red).

        참조 대상 태스크 파일을 아예 만들지 않는다 — "존재하지 않는 ID" 시나리오 재현."""
        tasks_dir = tmp_path / "tasks"
        tasks_dir.mkdir()
        monkeypatch.setattr(
            ptm,
            "EXCLUDED_CORPORA",
            {
                "fake_corpus": ptm.ExclusionEntry(
                    task_id="NONEXISTENT-TASK-ID-XYZ", reason="테스트용 사유"
                )
            },
        )
        violations = ptm.find_exclusion_expiry_violations(tasks_dir=tasks_dir)
        assert len(violations) == 1
        assert "NONEXISTENT-TASK-ID-XYZ" in violations[0]

    def test_done_task_still_excluded_is_flagged(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """② 참조된 태스크가 이미 done인데 제외 항목이 남아 있으면 위반으로 잡혀야 한다(red)
        — 이번 사고 그 자체("S4-14 done 후 6일 방치")를 시나리오로 재현한다."""
        tasks_dir = tmp_path / "tasks"
        _write_task_yaml(tasks_dir, "FAKE-DONE-TASK", status="done")
        monkeypatch.setattr(
            ptm,
            "EXCLUDED_CORPORA",
            {"fake_corpus": ptm.ExclusionEntry(task_id="FAKE-DONE-TASK", reason="테스트용 사유")},
        )
        violations = ptm.find_exclusion_expiry_violations(tasks_dir=tasks_dir)
        assert len(violations) == 1
        assert "FAKE-DONE-TASK" in violations[0]

    def test_todo_task_is_not_flagged(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """대조군(green) — 참조된 태스크가 아직 done이 아니면 위반이 아니다. ②가 done 여부로
        실제 갈리는지(같은 코드 경로에서 done만 다르게) 확인해 변별력을 보강한다."""
        tasks_dir = tmp_path / "tasks"
        _write_task_yaml(tasks_dir, "FAKE-TODO-TASK", status="todo")
        monkeypatch.setattr(
            ptm,
            "EXCLUDED_CORPORA",
            {"fake_corpus": ptm.ExclusionEntry(task_id="FAKE-TODO-TASK", reason="테스트용 사유")},
        )
        violations = ptm.find_exclusion_expiry_violations(tasks_dir=tasks_dir)
        assert violations == []
