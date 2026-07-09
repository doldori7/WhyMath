"""개념형(개수) 객관식 배치 — crosswalk machine-decidable 커버 상향(개수 검증·LLM 0).

`misconception_mc_batch`(수치평가)의 개념형 형제다. `ConceptualCountMCSkeletonGenerator`로 2 밴드
(실근 개수·극값 개수)를 생성 → 기존 오케스트레이터(`run_batch`)·수용 게이트(S2-a·개수 SymPy 독립
검증)·`JsonlCorpusSink`를 **재사용**해 코퍼스를 적재한다. 목적: 수치평가로 안 되는 개념형 오개념
2종(discriminant-negative-no-real-root·critical-point-implies-extremum)을 문항에 등장시켜 커버를
15/34 → 17/34로 올린다.

성취기준 튜플은 *각 kebab 후보 M-id가 전부 agree*하도록 잠갔다(거짓 자율거부 0). 이 2 kebab은
op-code 부재라 오개념만 태깅(`build_kebab_distractor_codes_optional`). 결정론·산출 v0(사람 검수 전).
CLI: `python -m whymath_backend.harness.conceptual_count_mc_batch [--n N] [--out PATH] [--dry-run]`.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

from whymath_backend.harness.misconception_mc_batch import build_kebab_distractor_codes_optional
from whymath_backend.harness.problem_corpus_batch import (
    BandResult,
    CorpusBatchReport,
    JsonlCorpusSink,
)
from whymath_backend.l3.equivalent.acceptance import EquivalenceSpec
from whymath_backend.l3.equivalent.conceptual_count_mc_generator import (
    ConceptualCountMCSkeletonGenerator,
    CountTemplateKind,
)
from whymath_backend.l3.equivalent.orchestrator import run_batch

__all__ = ["main", "run_conceptual_count_mc_batch"]

_SPEC_DIFFICULTY = 3.0
_DEFAULT_N = 24


@dataclass(frozen=True, slots=True)
class _Band:
    """서브밴드 — (밴드명=kebab, 개수 템플릿, 오개념 kebab, 성취기준 고시코드 튜플)."""

    name: str
    template: CountTemplateKind
    kebab: str
    standard_codes: tuple[str, ...]


# 2 서브밴드 — 개념형 개수 객관식. 표준 튜플은 각 kebab 후보가 전부 agree하도록 잠금(거짓거부 0).
_BANDS: tuple[_Band, ...] = (
    # discriminant: 후보 M0610=[10공수1-02-02]·M0832=[10기수1-02-02]·M0124=[9수02-20] 모두 agree.
    _Band(
        "discriminant-negative-no-real-root",
        "real_root_count",
        "discriminant-negative-no-real-root",
        ("[10공수1-02-02]", "[10기수1-02-02]", "[9수02-20]"),
    ),
    # critical-point: 후보 M0080·M0349=[12미적Ⅰ-02-01]·M0675=[12미적Ⅰ-02-07] 모두 agree.
    _Band(
        "critical-point-implies-extremum",
        "extremum_count",
        "critical-point-implies-extremum",
        ("[12미적Ⅰ-02-01]", "[12미적Ⅰ-02-07]"),
    ),
)


def _default_out_path() -> Path:
    root = Path(__file__).resolve().parents[4]
    return root / "data" / "corpus" / "problem_bank_conceptual_v0" / "problems.jsonl"


def run_conceptual_count_mc_batch(
    *, n_per_band: int = _DEFAULT_N, out_path: Path | None = None, write: bool = True
) -> CorpusBatchReport:
    """2 서브밴드 배치 실행 — 생성→S2-a 게이트(개수 검증)→구조 dedup→적재(순수 결정론)."""
    resolved_out = out_path if out_path is not None else _default_out_path()
    sink = JsonlCorpusSink()
    bands: list[BandResult] = []

    for band in _BANDS:
        codes = build_kebab_distractor_codes_optional(band.kebab)
        spec = EquivalenceSpec(
            achievement_standard_codes=frozenset(band.standard_codes),
            target_misconception_ids=frozenset({band.kebab}),
            difficulty_overall=_SPEC_DIFFICULTY,
            answer_format=None,
        )
        index: set[str] = set()
        generator = ConceptualCountMCSkeletonGenerator(band.template, codes, skip_signatures=index)
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
                name=band.name, requested=n_per_band, stored=stored, failure_reasons=failures
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
    """CLI — 개념형 개수 MC 배치. 수율 미달(총 저장 < 요청)이면 exit 1(조용한 실패 금지)."""
    parser = argparse.ArgumentParser(
        prog="python -m whymath_backend.harness.conceptual_count_mc_batch",
        description="개념형(실근 개수·극값 개수) 객관식 배치 적재(2 서브밴드·결정론).",
    )
    parser.add_argument("--n", type=int, default=_DEFAULT_N, help="서브밴드당 요청 수(기본 24).")
    parser.add_argument("--out", default=None, help="출력 코퍼스 경로(기본 conceptual_v0).")
    parser.add_argument("--dry-run", action="store_true", help="파일 기록 없이 밴드별 수율만 출력.")
    args = parser.parse_args(argv)

    report = run_conceptual_count_mc_batch(
        n_per_band=args.n,
        out_path=Path(args.out) if args.out else None,
        write=not args.dry_run,
    )
    print(json.dumps(report.to_json(), ensure_ascii=False, indent=2))
    return 0 if report.fulfilled else 1


if __name__ == "__main__":  # pragma: no cover — 엔트리포인트
    sys.exit(main())
