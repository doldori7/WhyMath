"""생성기 identity → problem_type_id 매핑표(S3-27) — 골든 분포·변별력·정본 정합 테스트.

**변별력**(CLAUDE.md "변별력 없는 검증 스텝 금지"): `TestMutationDetection`이 매핑표 항목 1개를
일부러 틀리게 바꾼 뒤 골든 분포 대조가 *실제로* 어긋남을 직접 실행해 증명한다(오매핑 주입 → 검사
실패, 복원 → 검사 통과 — 두 상태 모두 이 테스트 안에서 실행·확인한다).

실제 저장소의 코퍼스 파일(`data/corpus/problem_bank_*/problems.jsonl` — 2026-07-30 S3-27 백필
결과물)을 직접 읽어 전수 대조한다 — 합성 fixture가 아니라 *실제 산출물*이 골든 값과 일치하는지
보는 것이 이 매핑표의 유일한 존재 이유이기 때문이다.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pytest

from whymath_backend.harness import problem_type_mapping as ptm

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

_GOLDEN_TOTAL_TAGGED = 2217  # 2,638 - 421(rephrased_v0 명시 제외 — QUAL-02 은퇴 9건 반영)
_GOLDEN_EXCLUDED_TOTAL = 421


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


class TestGoldenDistribution:
    """매핑표를 실제 코퍼스 전량에 적용한 결과가 골든 값과 정확히 일치하는지 — 정상 매핑 대조."""

    @pytest.mark.parametrize("corpus_name", list(_GOLDEN_CORPUS_TYPE_TOTALS))
    def test_corpus_distribution_matches_golden(self, corpus_name: str) -> None:
        assert dict(_distribution_for(corpus_name)) == _GOLDEN_CORPUS_TYPE_TOTALS[corpus_name]

    def test_total_tagged_matches_golden(self) -> None:
        total = sum(
            sum(dist.values()) for name in ptm.TARGET_CORPORA for dist in [_distribution_for(name)]
        )
        assert total == _GOLDEN_TOTAL_TAGGED

    def test_rephrased_v0_excluded_from_target_corpora(self) -> None:
        # S4-14(변형 계보 영속) 미착지 — 백필 대상에서 명시 제외(acceptance ④).
        assert ptm.CORPUS_REPHRASED_V0 not in ptm.TARGET_CORPORA
        assert ptm.CORPUS_REPHRASED_V0 in ptm.EXCLUDED_CORPORA
        excluded_total = len(_load_corpus_lines(ptm.CORPUS_REPHRASED_V0))
        assert excluded_total == _GOLDEN_EXCLUDED_TOTAL

    def test_classify_record_returns_empty_for_excluded_corpus(self) -> None:
        # 제외 코퍼스는 어떤 레코드를 넣어도 미태깅(빈 리스트) — 침묵 오분류가 아니라 명시 미분류.
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
