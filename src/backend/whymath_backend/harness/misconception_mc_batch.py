"""오개념 커버리지 확대 수치평가 객관식 배치 — crosswalk machine-decidable 커버 상향(LLM 0).

`root_aggregate_batch`(Vieta 킬러)의 형제다. `MisconceptionEvalMCSkeletonGenerator`로 21 서브밴드
(오개념 kebab별)를 생성 → 기존 오케스트레이터(`run_batch`)·수용 게이트(S2-a)·`JsonlCorpusSink`를
**재사용**해 코퍼스를 적재한다. 목적: 기존 코퍼스가 `distractor_map`으로 커버하지 못하던 오개념
21종을 문항에 *등장*시켜 crosswalk 기계 게이트의 machine-decidable 커버리지를 끌어올린다(수치평가 MC
8→13→15 + Tier B 값형 4 + Tier C gambler 1 + 843 트랜치1 기초 계산형 6).
`crosslink_demotion_eval`의 커버리지 회계는 `problem_bank_*/problems.jsonl` glob이라 신규 코퍼스
자동 포함. 앞 3밴드는 op-code 실재, 나머지는
op-code 부재(오개념만 태깅·`DistractorEntry.op_code` 옵셔널).

조성 루트 소관(주입 원칙): 객관식 distractor의 오개념·op-code id는 여기서 L4 정본
(`CATALOG_BY_ID`·`DISTRACTOR_BY_ID`)을 읽어 L3 생성기에 *주입*한다 — L3 코드에는 L4 import·id
하드코딩이 없다(CLAUDE.md 오개념 독립 DB·계층 규칙). op-code가 없는 오개념은
`build_kebab_distractor_codes_optional`로 op_code=None을 주입한다(fail-fast는 kebab 실재에만).
harness는 import-linter 계약 밖(상위 계층 호출이 정상인 조성/ops 층 — `problem_corpus_batch` 선례).

결정론(재실행 바이트 동일): LLM 0·DB 0·타임스탬프 0·slug 기반 uuid5 problem_id·고정 시드 풀.
산출물은 v0(사람 검수 전) — 게이트 통과 ≠ 학생 노출(§03 정본). 밴드별 수율 미달(저장 < 요청)이면
종료 코드 1(조용한 실패 금지·밴드별 사유 포함).

CLI: `python -m whymath_backend.harness.misconception_mc_batch [--n N] [--out PATH] [--dry-run]`.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

from whymath_backend.harness.problem_corpus_batch import (
    BandResult,
    CorpusBatchReport,
    JsonlCorpusSink,
)
from whymath_backend.l3.equivalent.acceptance import EquivalenceSpec
from whymath_backend.l3.equivalent.misconception_eval_mc_generator import (
    MisconceptionEvalMCSkeletonGenerator,
    TemplateKind,
)
from whymath_backend.l3.equivalent.orchestrator import run_batch
from whymath_backend.l4.misconception.catalog import CATALOG_BY_ID
from whymath_backend.l4.misconception.distractor import DISTRACTOR_BY_ID

__all__ = [
    "build_kebab_distractor_codes",
    "build_kebab_distractor_codes_optional",
    "main",
    "run_misconception_mc_batch",
]

# 배치 스펙 — 모든 밴드 난이도 3.0(생성기 난이도 [2.5,3.5] 밴드 중앙·게이트 tol 0.5 안이라 만점).
_SPEC_DIFFICULTY = 3.0
_DEFAULT_N = 24  # 서브밴드당 요청 수(요구 하한 ≥24·각 풀 크기 ≥24라 100% 수율 여유).


@dataclass(frozen=True, slots=True)
class _Band:
    """서브밴드 정의 — (밴드명=kebab, 생성기 템플릿, 오개념 kebab, 성취기준 고시코드 튜플).

    성취기준은 *튜플*이다 — 한 오개념이 여러 성취기준을 가로지를 수 있어서다. 예 chain-rule은
    기본 미분(미적Ⅰ)과 합성함수 미분법(미적Ⅱ)을 함께 걸친다(합성함수 미분 오류가 두 성취기준에
    동시 귀속). 이러면 역유도 성취기준이 두 코드를 담아, crosswalk 구조 게이트가 어느 한쪽 코드의
    후보 M-id를 *거짓 자율거부*하지 않는다(다표준 오개념의 정직한 표기).
    """

    name: str
    template: TemplateKind
    kebab: str
    standard_codes: tuple[str, ...]


# 21 서브밴드 — 각 오개념 1종을 오답 선지로 태깅하는 수치평가 객관식.
#   앞 3종(distribution/chain_rule/sine_sum)은 op-code 실재(DISTRACTOR_BY_ID).
#   나머지(exp_zero 이후·Tier B 값형 포함)는 op-code 부재 — 오개념만 태깅(op_code 옵셔널).
#   성취기준 튜플은 *각 kebab의 후보 M-id가 전부 agree*하도록 잠갔다 — 어느 후보도 crosswalk 구조
#   게이트에서 거짓 자율거부되지 않게 한다(machine_reject 신규 0·인간 검수 존치).
_BANDS: tuple[_Band, ...] = (
    _Band(
        "distribution-over-power",
        "distribution",
        "distribution-over-power",
        ("[9수02-19]",),
    ),
    # chain-rule는 미적Ⅰ(미분)·미적Ⅱ(합성함수 미분법)를 함께 걸침 — 둘 다 태깅해 어느 후보도
    # 거짓 거부하지 않는다(M0370·M0077=미적Ⅰ·M0710=미적Ⅱ 후보가 모두 agree→인간 검수).
    _Band(
        "chain-rule-inner-derivative-omitted",
        "chain_rule",
        "chain-rule-inner-derivative-omitted",
        ("[12미적Ⅰ-02-01]", "[12미적Ⅱ-02-05]"),
    ),
    _Band(
        "sine-distributes-over-sum",
        "sine_sum",
        "sine-distributes-over-sum",
        ("[12미적Ⅱ-02-02]",),
    ),
    # ── 신규 5종(op-code 부재) ──
    # exponent-zero: 후보 M0105=[9수02-08] agree.
    _Band("exponent-zero", "exp_zero", "exponent-zero", ("[9수02-08]",)),
    # square-root-positivity: 후보 M0550·M0109=[9수01-07], M0647=[12대수01-01] — 둘 다 태깅해 agree.
    _Band(
        "square-root-positivity",
        "sqrt_pos",
        "square-root-positivity",
        ("[9수01-07]", "[12대수01-01]"),
    ),
    # log-distribution: 후보 M0049=[12대수01-05], M0650=[12대수01-04] — 둘 다 태깅해 agree.
    _Band(
        "log-distribution",
        "log_dist",
        "log-distribution",
        ("[12대수01-05]", "[12대수01-04]"),
    ),
    # composite-function-commutes: M0643·M0038=[10공수2-03-02], M0858=[10기수2-03-02] — 둘 다 agree.
    _Band(
        "composite-function-commutes",
        "func_compose",
        "composite-function-commutes",
        ("[10공수2-03-02]", "[10기수2-03-02]"),
    ),
    # period-of-scaled-sine: 후보 M0152=[12미적Ⅱ-02-02] agree.
    _Band(
        "period-of-scaled-sine",
        "sine_period",
        "period-of-scaled-sine",
        ("[12미적Ⅱ-02-02]",),
    ),
    # translation-sign-flip: 후보 M0411·M0850=[10기수2-01-06], M0632=[10공수2-01-06] — 둘 다 agree.
    _Band(
        "translation-sign-flip",
        "translate",
        "translation-sign-flip",
        ("[10기수2-01-06]", "[10공수2-01-06]"),
    ),
    # product-rule-naive: 후보 M0075=[12미적Ⅰ-02-01]·M0672=[12미적Ⅰ-02-04] agree(둘 다 태깅).
    #   M0424=[10공수2-03-02](합성·부분매핑)는 곱미분과 다른 단원 → cross-standard 자율거부(정당).
    _Band(
        "product-rule-naive",
        "product_rule",
        "product-rule-naive",
        ("[12미적Ⅰ-02-01]", "[12미적Ⅰ-02-04]"),
    ),
    # ── Tier B 계산가능(값형)·태깅 주의 4종 ──
    # fraction-cancellation: 후보 M0118=[9수01-04]·M0503=[6수01-06] — 둘 다 태깅해 agree.
    _Band(
        "fraction-cancellation",
        "fraction_cancel",
        "fraction-cancellation",
        ("[9수01-04]", "[6수01-06]"),
    ),
    # angle-sum-non-triangle: 후보 M0493=[4수03-25]·M0580=[9수03-05]·M0051=[9수03-03] 모두 agree.
    _Band(
        "angle-sum-non-triangle",
        "polygon_angle_sum",
        "angle-sum-non-triangle",
        ("[4수03-25]", "[9수03-05]", "[9수03-03]"),
    ),
    # area-perimeter-confusion: 후보 M0529=[6수03-11]·M0782=[12직수03-04]·M0052=[9수03-12] agree.
    _Band(
        "area-perimeter-confusion",
        "area_perimeter",
        "area-perimeter-confusion",
        ("[6수03-11]", "[12직수03-04]", "[9수03-12]"),
    ),
    # circle-radius-squared: 후보 M0630=[10공수2-01-04]·M0848=[10기수2-01-04]·M0732=[12기하02-05]
    #   모두 태깅해 agree — 특히 M0848(원의 방정식 [10기수2-01-04])이 factor-sign-flip에서 이미
    #   자동거부 대상이나, circle-radius는 그 표준을 담아 agree라 신규 거부 0(kebab별 독립 역유도).
    _Band(
        "circle-radius-squared",
        "circle_radius",
        "circle-radius-squared",
        ("[10공수2-01-04]", "[10기수2-01-04]", "[12기하02-05]"),
    ),
    # ── Tier C 계산가능(값형) — gambler(독립시행) ──
    # gambler-fallacy: 후보 M0688=[12확통02-01]·M0093=[12인수04-01]·M0794=[12수문02-02] 모두 agree.
    _Band(
        "gambler-fallacy",
        "gambler_streak",
        "gambler-fallacy",
        ("[12확통02-01]", "[12인수04-01]", "[12수문02-02]"),
    ),
    # ── 843 확장 트랜치1(기초 계산형 6종·후보 단일 M-id·표준 일치 agree) ──
    # fraction-addition-naive: 후보 M0004=[9수01-04] agree.
    _Band(
        "fraction-addition-naive",
        "fraction_addition",
        "fraction-addition-naive",
        ("[9수01-04]",),
    ),
    # negative-times-negative: 후보 M0001=[9수01-03] agree.
    _Band(
        "negative-times-negative",
        "negative_product",
        "negative-times-negative",
        ("[9수01-03]",),
    ),
    # subtract-negative-sign: 후보 M0002=[9수01-03] agree.
    _Band(
        "subtract-negative-sign",
        "subtract_negative",
        "subtract-negative-sign",
        ("[9수01-03]",),
    ),
    # absolute-value-keeps-sign: 후보 M0010=[9수01-04] agree.
    _Band(
        "absolute-value-keeps-sign",
        "absolute_value",
        "absolute-value-keeps-sign",
        ("[9수01-04]",),
    ),
    # sqrt-distributes-over-sum: 후보 M0008=[9수01-07] agree.
    _Band(
        "sqrt-distributes-over-sum",
        "sqrt_sum",
        "sqrt-distributes-over-sum",
        ("[9수01-07]",),
    ),
    # difference-of-squares-confused: 후보 M0121=[9수01-01] agree.
    _Band(
        "difference-of-squares-confused",
        "difference_of_squares",
        "difference-of-squares-confused",
        ("[9수01-01]",),
    ),
)


def _default_out_path() -> Path:
    # src/backend/whymath_backend/harness/ → repo root 4단계(problem_corpus_batch 규약 미러).
    root = Path(__file__).resolve().parents[4]
    return root / "data" / "corpus" / "problem_bank_misconception_mc_v0" / "problems.jsonl"


def build_kebab_distractor_codes(kebab: str) -> dict[str, tuple[str, str]]:
    """kebab → `{kebab: (misconception_id, op_code)}` 주입쌍 — L4 정본 역참조(fail-fast).

    kebab이 정본 오개념 카탈로그에 없거나, 그 kebab을 유발하는 op-code가 `DISTRACTOR_BY_ID`에
    없으면 `KeyError`로 즉시 실패한다(조용한 무매핑 금지·조성 루트가 무결성 소유). op-code는
    `DistractorOpCode.misconception_id == kebab`인 엔트리에서 역유도한다(`DISTRACTOR_BY_ID`는
    op-code id로 키잉되므로 misconception_id로 역탐색).
    """
    if kebab not in CATALOG_BY_ID:
        raise KeyError(f"주입 오개념 id가 정본 카탈로그에 없음: {kebab!r}")
    op_code = next((d.id for d in DISTRACTOR_BY_ID.values() if d.misconception_id == kebab), None)
    if op_code is None:
        raise KeyError(f"kebab {kebab!r}을(를) 유발하는 op-code가 DISTRACTOR_CATALOG에 없음")
    return {kebab: (kebab, op_code)}


def build_kebab_distractor_codes_optional(
    kebab: str,
) -> dict[str, tuple[str, str | None]]:
    """kebab → `{kebab: (misconception_id, op_code | None)}` — op-code 부재 허용판(fail-fast).

    `build_kebab_distractor_codes`와 달리 유발 op-code가 `DISTRACTOR_BY_ID`에 없어도 `KeyError`를
    던지지 않고 op_code=None을 담는다(수치평가 MC는 op-code 없이 오개념만 태깅 — `DistractorEntry`
    .op_code 옵셔널). 단, kebab이 정본 오개념 카탈로그에 없으면 여전히 즉시 실패한다(조용한 무매핑
    금지·조성 루트가 무결성 소유). op-code가 실재하면 그대로 담아 op-code 有 밴드와도 정합한다.
    """
    if kebab not in CATALOG_BY_ID:
        raise KeyError(f"주입 오개념 id가 정본 카탈로그에 없음: {kebab!r}")
    op_code = next((d.id for d in DISTRACTOR_BY_ID.values() if d.misconception_id == kebab), None)
    return {kebab: (kebab, op_code)}


def run_misconception_mc_batch(
    *, n_per_band: int = _DEFAULT_N, out_path: Path | None = None, write: bool = True
) -> CorpusBatchReport:
    """21 서브밴드 배치 실행 — 생성→S2-a 게이트→구조 dedup→적재(순수 결정론).

    각 밴드는 **별도 signature_index**(문제군 분리·calc 밴드 패턴 미러)를 쓴다. sink에는 밴드
    순서대로 append한다. `target_misconception_ids={kebab}`라 게이트 오개념 Jaccard가 1.0(후보가
    태깅하는 오개념이 정확히 그 kebab 1종).
    """
    resolved_out = out_path if out_path is not None else _default_out_path()
    sink = JsonlCorpusSink()
    bands: list[BandResult] = []

    for band in _BANDS:
        # op-code 有/無 무관 주입 — 부재 시 op_code=None(옵셔널). op-code 실재 밴드는 동일 결과라
        # 기존 3밴드 바이트 무변경(op-code를 그대로 담음).
        codes = build_kebab_distractor_codes_optional(band.kebab)
        spec = EquivalenceSpec(
            achievement_standard_codes=frozenset(band.standard_codes),
            target_misconception_ids=frozenset({band.kebab}),
            difficulty_overall=_SPEC_DIFFICULTY,
            answer_format=None,
        )
        index: set[str] = set()
        generator = MisconceptionEvalMCSkeletonGenerator(
            band.template, codes, skip_signatures=index
        )
        outcomes = run_batch(spec, generator, n_per_band, signature_index=index, store=sink)
        stored = sum(1 for o in outcomes if o.status == "accepted_stored")
        failures = [
            reason
            for outcome in outcomes
            if outcome.status != "accepted_stored"
            for reason in (outcome.reasons or [f"status={outcome.status}"])
        ]
        bands.append(
            BandResult(
                name=band.name,
                requested=n_per_band,
                stored=stored,
                failure_reasons=failures,
            )
        )

    total_requested = sum(b.requested for b in bands)
    total_stored = sum(b.stored for b in bands)
    written = sink.write(resolved_out) if write else None
    return CorpusBatchReport(
        bands=bands,
        total_requested=total_requested,
        total_stored=total_stored,
        written=written,
        out_path=str(resolved_out),
    )


def main(argv: list[str] | None = None) -> int:
    """CLI — 오개념 수치평가 MC 배치. 수율 미달(총 저장 < 요청)이면 exit 1(조용한 실패 금지)."""
    parser = argparse.ArgumentParser(
        prog="python -m whymath_backend.harness.misconception_mc_batch",
        description="오개념 커버리지 확대 수치평가 객관식 배치 적재(21 서브밴드·결정론).",
    )
    parser.add_argument("--n", type=int, default=_DEFAULT_N, help="서브밴드당 요청 수(기본 24).")
    parser.add_argument("--out", default=None, help="출력 코퍼스 경로(기본 misconception_mc_v0).")
    parser.add_argument("--dry-run", action="store_true", help="파일 기록 없이 밴드별 수율만 출력.")
    args = parser.parse_args(argv)

    report = run_misconception_mc_batch(
        n_per_band=args.n,
        out_path=Path(args.out) if args.out else None,
        write=not args.dry_run,
    )
    print(json.dumps(report.to_json(), ensure_ascii=False, indent=2))
    return 0 if report.fulfilled else 1


if __name__ == "__main__":  # pragma: no cover — 엔트리포인트
    sys.exit(main())
