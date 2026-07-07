"""동등문제 스켈레톤 코퍼스 배치 CLI — S2-p *조성 루트*(ops·JSONL 산출).

Phaiakes9 전용이던 배치 스크립트(run_batch_corpus.py·repo 밖)를 **repo 버전 CLI**로 승격한다.
스켈레톤 파이프라인은 LLM 0·DB 0·순수 결정론이라 어디서든 같은 산출물이 나온다 — 생성 코퍼스
(`data/corpus/problem_bank_generated_v0/problems.jsonl`)를 재현 가능하게 전면 재생성하는 것이
이 CLI의 존재 이유다.

사용법:
    python -m whymath_backend.harness.problem_corpus_batch \\
        [--out <jsonl>] [--short 90] [--mc 45] [--sqrt 30] [--sqrt-mc 20]
        [--calc-extremum 40] [--calc-tangent 40] [--calc-value 40] [--exp 25] [--log 20] [--dry-run]

동작: 문제군별 밴드를 순차 실행 → 전 후보가 S2-a 4종 게이트를 통과해야 sink에 실린다 → JSONL로
기록. **quad 문제군**(short/mc/sqrt/sqrt_mc·이차방정식 근)은 공유 signature_index로 겹침을 차단하고,
**calc 문제군**(calc-extremum=삼차 극값 x좌표·calc-tangent=삼차 접선 기울기 m인 점의 x좌표·
calc-value=삼차 극댓값·극솟값(값), 셋 다 미적분Ⅰ)은 군마다 별도 signature_index다(conditions가
도함수/극값 이차방정식이라 이차방정식과 구조 동형 → 공유 시 거짓 cross-군 dedup). 리포트를 JSON으로
stdout에 내고, **수율 미달이면 종료 코드 1**(조용한 실패 금지 — 밴드별 사유 포함).

조성 루트 소관(주입 원칙): 객관식 distractor의 오개념/op-code id는 여기서 L4 정본
(`CATALOG_BY_ID`·`DISTRACTOR_BY_ID`)을 읽어 L3 생성기에 *주입*한다 — L3 코드에는 L4 import·id
하드코딩이 없다(CLAUDE.md 오개념 독립 DB·계층 규칙). harness는 import-linter 계약 밖(상위 계층
호출이 정상인 조성/ops 층 — `agreement_gate_cli` 선례).

결정론 보장(재실행 바이트 동일): LLM 0·DB 0·타임스탬프 0·slug 기반 uuid5 problem_id·고정 시드
풀·값 정렬 선지 — 같은 인자로 두 번 실행하면 산출 파일이 바이트까지 같다(테스트 봉인). 산출물은
v0(사람 검수 전) — 게이트 통과 ≠ 학생 노출(§03 정본).
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from whymath_backend.l1.problem_bank.populate import (
    ProblemBankPopulateReport,
    ProblemBankRecord,
)
from whymath_backend.l3.equivalent.acceptance import EquivalenceSpec
from whymath_backend.l3.equivalent.calculus_skeleton_generator import (
    CalculusExtremumSkeletonGenerator,
    CalculusExtremumValueSkeletonGenerator,
    CalculusTangentSlopeSkeletonGenerator,
)
from whymath_backend.l3.equivalent.exp_log_skeleton_generator import (
    ExponentialEquationSkeletonGenerator,
    LogarithmicEquationSkeletonGenerator,
)
from whymath_backend.l3.equivalent.orchestrator import run_batch
from whymath_backend.l3.equivalent.skeleton_generator import (
    GeneratorVariant,
    SkeletonEquivalentProblemGenerator,
)
from whymath_backend.l4.misconception.catalog import CATALOG_BY_ID
from whymath_backend.l4.misconception.distractor import DISTRACTOR_BY_ID

__all__ = [
    "CorpusBatchReport",
    "JsonlCorpusSink",
    "build_distractor_codes",
    "main",
    "run_corpus_batch",
]

# 밴드 공통 스펙 — 현 스켈레톤 풀 전체가 이 성취기준([10공수1-02-02]·이차방정식의 근) 소속.
# 난이도 2.5 고정: 추정 난이도(2.0~3.6) 최대 gap 1.1 < 3.5(게이트 감쇠 수학)라 밴드 분리 불요.
_STANDARD_CODE = "[10공수1-02-02]"
_SPEC_DIFFICULTY = 2.5

# 객관식 distractor 주입쌍 — L4 정본 id(오개념·op-code). 여기 *조성 루트*에만 존재한다.
_MC_INJECTION: dict[str, tuple[str, str]] = {
    "opposite_root": ("opposite-root-selected", "select-opposite-root"),
    "sign_flip": ("factor-sign-flip", "factor-sign-flip-root"),
}

# 밴드 기본 크기 — quad 185 + calc 120 + exp 25 + log 20 = 총 350건(CI 봉인 ≥100 여유).
# 풀 실측: short 443·mc 159·sqrt 122·sqrt_mc 58·calc-extremum 162·calc-tangent 162·calc-value 150·
# exp 28·log 28.
_DEFAULT_SHORT_N = 90
_DEFAULT_MC_N = 45
_DEFAULT_SQRT_N = 30
_DEFAULT_SQRT_MC_N = 20
_DEFAULT_CALC_EXTREMUM_N = 40
_DEFAULT_CALC_TANGENT_N = 40
_DEFAULT_CALC_VALUE_N = 40
_DEFAULT_EXP_N = 25
_DEFAULT_LOG_N = 20

# 미적분(극값) 밴드 스펙 — 별도 성취기준([12미적Ⅰ-02-07]·함수의 증가·감소와 극대·극소).
# 난이도 3.3 고정: 극값 추정(3.0~4.0) 최대 gap 0.7 < 3.5(게이트 감쇠 수학)라 안전.
# **별도 signature_index 사용**: 극값 conditions는 *도함수 방정식*이라 구조가 이차방정식과
# 동형이다 — quad 밴드와 index를 공유하면 도함수 방정식이 quad 문제 방정식과 우연히 같을 때
# (같은 선택) 거짓 dedup으로 다른 문제군을 중복 처리한다. 문제군이 다르므로 dedup도 군 내부로.
_CALC_STANDARD_CODE = "[12미적Ⅰ-02-07]"
_CALC_SPEC_DIFFICULTY = 3.3

# 미적분(접선 기울기) 밴드 스펙 — 미분계수([12미적Ⅰ-02-01]·미분계수=접선 기울기). f'(x)=m의 근
# 계열이라 conditions도 도함수 방정식(이차 동형) → 극값과도 cross-군 충돌 가능 → **또 별도 index**.
_TANGENT_STANDARD_CODE = "[12미적Ⅰ-02-01]"
_TANGENT_SPEC_DIFFICULTY = 3.3

# 미적분(극값의 값) 밴드 스펙 — 극값 x좌표와 *같은* 성취기준([12미적Ⅰ-02-07]·극대·극소)·개념.
# conditions는 두 극값의 이차방정식(dummy x)이라 극값 x좌표·접선 방정식과 구조 동형 → 또 cross-군
# 오dedup 위험(극값 x=1,3의 조건과 극값 값이 1,3인 조건이 canonical 동일) → **또 별도 index**.
_VALUE_STANDARD_CODE = "[12미적Ⅰ-02-07]"
_VALUE_SPEC_DIFFICULTY = 3.3

# 지수·로그 밴드 스펙 — 대수(고2·[12대수01-08]·지수함수·로그함수 활용). conditions가 비다항
# (b**x-v·log(x,b)-k)이라 canonical signature=None → signature_index 무의미(풀 결정론 유일이라
# dedup 불요)·quad/calc(다항 signature)와 cross-군 충돌 원천 불가. 난이도 3.0: 추정(2.6~3.4)
# 최대 gap 0.4 < 0.5(tol)이라 동등성 난이도 성분 만점.
_EXPLOG_STANDARD_CODE = "[12대수01-08]"
_EXPLOG_SPEC_DIFFICULTY = 3.0


def _default_out_path() -> Path:
    """기본 산출 경로 — repo의 생성 코퍼스 v0(경로 유지 전면 교체·품질 테스트와 동일 규약).

    `__file__` = <repo>/src/backend/whymath_backend/harness/problem_corpus_batch.py 라
    parents[4]가 repo 루트다(harness→whymath_backend→backend→src→repo — 실측 확인). editable
    설치(개발 트리) 전제의 ops CLI — 배포 트리에선 `--out`으로 명시한다.
    """
    repo_root = Path(__file__).resolve().parents[4]
    return repo_root / "data" / "corpus" / "problem_bank_generated_v0" / "problems.jsonl"


def build_distractor_codes() -> dict[str, tuple[str, str]]:
    """L4 정본에서 객관식 주입 매핑을 조립 — 참조 무결성은 조성 루트가 소유(fail-fast).

    미등록 오개념 id·op-code, 또는 op-code가 다른 오개념을 가리키면 `KeyError`로 즉시 실패한다
    (조용한 무매핑 금지) — 배치가 잘못된 태깅을 코퍼스에 싣는 것을 원천 차단.
    """
    for op_key, (misconception_id, op_code) in _MC_INJECTION.items():
        if misconception_id not in CATALOG_BY_ID:
            raise KeyError(
                f"주입 오개념 id가 정본 카탈로그에 없음: {misconception_id!r} (op키 {op_key})"
            )
        op = DISTRACTOR_BY_ID.get(op_code)
        if op is None:
            raise KeyError(f"주입 op-code가 DISTRACTOR_CATALOG에 없음: {op_code!r} (op키 {op_key})")
        if op.misconception_id != misconception_id:
            raise KeyError(
                f"op-code {op_code!r}의 오개념({op.misconception_id!r})이 주입 오개념"
                f"({misconception_id!r})과 불일치 — 정본 정합 위반"
            )
    return dict(_MC_INJECTION)


def _record_to_json(record: ProblemBankRecord) -> dict[str, Any]:
    """저장 레코드 → 코퍼스 JSONL dict — 기존 v0 직렬화 형태와 정확 일치(라운드트립 봉인).

    Problem 필드(mode="json"·None 제외) + 저작 메타(`_AUTHORING_KEYS`: license·generation_type·
    (original_source)·concepts·verify). `load_problem_bank_records`가 그대로 되읽는다.
    """
    data: dict[str, Any] = record.problem.model_dump(mode="json", exclude_none=True)
    data["license"] = record.provenance.license
    data["generation_type"] = record.provenance.generation_type
    if record.provenance.original_source is not None:
        data["original_source"] = record.provenance.original_source
    data["concepts"] = [
        {"concept_src_id": tag.concept_src_id, "role": tag.role, "relevance": tag.relevance}
        for tag in record.concept_tags
    ]
    verify: dict[str, Any] = {
        "conditions": record.verify.conditions,
        "answer_map": dict(record.verify.answer_map),
    }
    if record.verify.solution_steps is not None:
        verify["solution_steps"] = list(record.verify.solution_steps)
    if record.verify.answer_selection is not None:
        verify["answer_selection"] = record.verify.answer_selection
    data["verify"] = verify
    return data


class JsonlCorpusSink:
    """JSONL 저장 좌석 — `ProblemBankSink` 구조 충족(populate만)·메모리 수집 후 `write`로 기록.

    오케스트레이터는 후보 1건을 단일 레코드 배치로 넘긴다(S2-b seam 재사용) — 이 sink는 DB 대신
    메모리에 쌓았다가 배치 종료 후 한 번에 파일로 쓴다(부분 기록 없음·원자성).
    """

    def __init__(self) -> None:
        self._records: list[ProblemBankRecord] = []

    @property
    def records(self) -> list[ProblemBankRecord]:
        return list(self._records)

    def populate(self, records: list[ProblemBankRecord]) -> ProblemBankPopulateReport:
        """레코드 배치를 메모리에 적재 — DB store와 동일 좌석 계약(리포트 반환)."""
        self._records.extend(records)
        return ProblemBankPopulateReport(
            problems_loaded=len(records),
            problem_concepts_loaded=sum(len(r.concept_tags) for r in records),
            concepts_skipped=0,
        )

    def write(self, path: Path) -> int:
        """수집분 전체를 JSONL로 기록(기존 파일 전면 교체) — 기록 행 수 반환."""
        path.parent.mkdir(parents=True, exist_ok=True)
        lines = [json.dumps(_record_to_json(r), ensure_ascii=False) for r in self._records]
        path.write_text("\n".join(lines) + "\n" if lines else "", encoding="utf-8")
        return len(lines)


@dataclass(frozen=True, slots=True)
class BandResult:
    """밴드 1개 실행 결과 — 요청/저장 수 + 미저장 사유(조용한 실패 금지)."""

    name: str
    requested: int
    stored: int
    failure_reasons: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class CorpusBatchReport:
    """배치 전체 리포트 — 밴드별 결과·총 저장 수·기록 행 수(dry-run이면 None)."""

    bands: list[BandResult]
    total_requested: int
    total_stored: int
    written: int | None
    out_path: str

    @property
    def fulfilled(self) -> bool:
        """수율 충족 — 요청 전량이 게이트를 통과해 저장됐는가."""
        return self.total_stored == self.total_requested

    def to_json(self) -> dict[str, Any]:
        return {
            "bands": [
                {
                    "name": b.name,
                    "requested": b.requested,
                    "stored": b.stored,
                    "failure_reasons": b.failure_reasons,
                }
                for b in self.bands
            ],
            "total_requested": self.total_requested,
            "total_stored": self.total_stored,
            "written": self.written,
            "out_path": self.out_path,
            "fulfilled": self.fulfilled,
        }


def run_corpus_batch(
    *,
    out_path: Path | None = None,
    short_n: int = _DEFAULT_SHORT_N,
    mc_n: int = _DEFAULT_MC_N,
    sqrt_n: int = _DEFAULT_SQRT_N,
    sqrt_mc_n: int = _DEFAULT_SQRT_MC_N,
    calc_extremum_n: int = _DEFAULT_CALC_EXTREMUM_N,
    calc_tangent_n: int = _DEFAULT_CALC_TANGENT_N,
    calc_value_n: int = _DEFAULT_CALC_VALUE_N,
    exp_n: int = _DEFAULT_EXP_N,
    log_n: int = _DEFAULT_LOG_N,
    write: bool = True,
) -> CorpusBatchReport:
    """밴드 배치 실행 — 문제군별 signature_index·밴드별 스펙 정합·JSONL 기록(순수 결정론).

    밴드 스펙의 `target_misconception_ids`는 그 밴드 후보가 실제로 방출하는 오개념 집합과
    일치시킨다(mc·sqrt_mc=주입 2종·나머지=∅) — 게이트 오개념 Jaccard가 항상 1.0(빈 spec에
    오개념 도입 시 0.0인 규칙과 정합). quad 4밴드 난이도는 2.5·calc 밴드는 3.3 고정(gap ≤ 안전폭).

    문제군별 signature_index 분리: quad 4밴드(이차방정식 근)는 **공유** index(형식 파티션이 겹침
    차단), calc 밴드(삼차 극값)는 **별도** index다 — calc conditions는 도함수 방정식이라 이차방정식
    과 구조 동형이라, 공유 시 거짓 cross-군 dedup이 난다. 두 군은 sink에 순차 append(quad→calc).
    """
    resolved_out = out_path if out_path is not None else _default_out_path()
    codes = build_distractor_codes()
    mc_target_ids = frozenset(misconception_id for misconception_id, _ in codes.values())
    mc_variants: frozenset[str] = frozenset({"multiple_choice", "sqrt_multiple_choice"})

    sink = JsonlCorpusSink()
    signature_index: set[str] = set()
    band_plans: list[tuple[str, GeneratorVariant, int, frozenset[str]]] = [
        ("short", "short_answer", short_n, frozenset()),
        ("mc", "multiple_choice", mc_n, mc_target_ids),
        ("sqrt", "sqrt", sqrt_n, frozenset()),
        ("sqrt_mc", "sqrt_multiple_choice", sqrt_mc_n, mc_target_ids),
    ]

    bands: list[BandResult] = []
    for name, variant, n, target_ids in band_plans:
        spec = EquivalenceSpec(
            achievement_standard_codes=frozenset({_STANDARD_CODE}),
            target_misconception_ids=target_ids,
            difficulty_overall=_SPEC_DIFFICULTY,
            answer_format=None,
        )
        generator = SkeletonEquivalentProblemGenerator(
            variant=variant,
            distractor_codes=codes if variant in mc_variants else None,
            skip_signatures=signature_index,
        )
        outcomes = run_batch(spec, generator, n, signature_index=signature_index, store=sink)
        stored = sum(1 for o in outcomes if o.status == "accepted_stored")
        failure_reasons = [
            reason
            for outcome in outcomes
            if outcome.status != "accepted_stored"
            for reason in (outcome.reasons or [f"status={outcome.status}"])
        ]
        bands.append(
            BandResult(name=name, requested=n, stored=stored, failure_reasons=failure_reasons)
        )

    # ── calc 문제군(삼차 극값) — 별도 signature_index(도함수 방정식 cross-군 오dedup 방지) ──
    if calc_extremum_n > 0:
        calc_index: set[str] = set()
        calc_spec = EquivalenceSpec(
            achievement_standard_codes=frozenset({_CALC_STANDARD_CODE}),
            target_misconception_ids=frozenset(),
            difficulty_overall=_CALC_SPEC_DIFFICULTY,
            answer_format=None,
        )
        calc_generator = CalculusExtremumSkeletonGenerator(skip_signatures=calc_index)
        calc_outcomes = run_batch(
            calc_spec, calc_generator, calc_extremum_n, signature_index=calc_index, store=sink
        )
        calc_stored = sum(1 for o in calc_outcomes if o.status == "accepted_stored")
        calc_failures = [
            reason
            for outcome in calc_outcomes
            if outcome.status != "accepted_stored"
            for reason in (outcome.reasons or [f"status={outcome.status}"])
        ]
        bands.append(
            BandResult(
                name="calc-extremum",
                requested=calc_extremum_n,
                stored=calc_stored,
                failure_reasons=calc_failures,
            )
        )

    # ── calc 문제군(삼차 접선 기울기) — 또 별도 signature_index(도함수 방정식 cross-군 방지) ──
    if calc_tangent_n > 0:
        tangent_index: set[str] = set()
        tangent_spec = EquivalenceSpec(
            achievement_standard_codes=frozenset({_TANGENT_STANDARD_CODE}),
            target_misconception_ids=frozenset(),
            difficulty_overall=_TANGENT_SPEC_DIFFICULTY,
            answer_format=None,
        )
        tangent_generator = CalculusTangentSlopeSkeletonGenerator(skip_signatures=tangent_index)
        tangent_outcomes = run_batch(
            tangent_spec,
            tangent_generator,
            calc_tangent_n,
            signature_index=tangent_index,
            store=sink,
        )
        tangent_stored = sum(1 for o in tangent_outcomes if o.status == "accepted_stored")
        tangent_failures = [
            reason
            for outcome in tangent_outcomes
            if outcome.status != "accepted_stored"
            for reason in (outcome.reasons or [f"status={outcome.status}"])
        ]
        bands.append(
            BandResult(
                name="calc-tangent",
                requested=calc_tangent_n,
                stored=tangent_stored,
                failure_reasons=tangent_failures,
            )
        )

    # ── calc 문제군(삼차 극값의 값) — 또 별도 signature_index(극값 쌍 이차방정식 cross-군 방지) ──
    if calc_value_n > 0:
        value_index: set[str] = set()
        value_spec = EquivalenceSpec(
            achievement_standard_codes=frozenset({_VALUE_STANDARD_CODE}),
            target_misconception_ids=frozenset(),
            difficulty_overall=_VALUE_SPEC_DIFFICULTY,
            answer_format=None,
        )
        value_generator = CalculusExtremumValueSkeletonGenerator(skip_signatures=value_index)
        value_outcomes = run_batch(
            value_spec, value_generator, calc_value_n, signature_index=value_index, store=sink
        )
        value_stored = sum(1 for o in value_outcomes if o.status == "accepted_stored")
        value_failures = [
            reason
            for outcome in value_outcomes
            if outcome.status != "accepted_stored"
            for reason in (outcome.reasons or [f"status={outcome.status}"])
        ]
        bands.append(
            BandResult(
                name="calc-value",
                requested=calc_value_n,
                stored=value_stored,
                failure_reasons=value_failures,
            )
        )

    # ── 대수 문제군(지수·로그 방정식) — 비다항 conditions(signature=None)이라 별도 index지만
    #    실질 dedup 없음(풀 결정론 유일). quad/calc와 구조 signature가 애초에 안 겹친다. ──
    for band_name, gen_factory, count in (
        ("exp", ExponentialEquationSkeletonGenerator, exp_n),
        ("log", LogarithmicEquationSkeletonGenerator, log_n),
    ):
        if count <= 0:
            continue
        explog_index: set[str] = set()
        explog_spec = EquivalenceSpec(
            achievement_standard_codes=frozenset({_EXPLOG_STANDARD_CODE}),
            target_misconception_ids=frozenset(),
            difficulty_overall=_EXPLOG_SPEC_DIFFICULTY,
            answer_format=None,
        )
        explog_outcomes = run_batch(
            explog_spec,
            gen_factory(skip_signatures=explog_index),
            count,
            signature_index=explog_index,
            store=sink,
        )
        explog_stored = sum(1 for o in explog_outcomes if o.status == "accepted_stored")
        explog_failures = [
            reason
            for outcome in explog_outcomes
            if outcome.status != "accepted_stored"
            for reason in (outcome.reasons or [f"status={outcome.status}"])
        ]
        bands.append(
            BandResult(
                name=band_name,
                requested=count,
                stored=explog_stored,
                failure_reasons=explog_failures,
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
    """CLI 엔트리 — 리포트를 JSON으로 stdout에 내고, 수율 미달이면 종료 코드 1."""
    parser = argparse.ArgumentParser(
        prog="python -m whymath_backend.harness.problem_corpus_batch",
        description=(
            "동등문제 스켈레톤 코퍼스 배치(S2-p) — 4밴드(short/mc/sqrt/sqrt_mc)를 4종 게이트에 "
            "태워 JSONL 코퍼스를 결정론 재생성한다(LLM 0·DB 0)."
        ),
    )
    parser.add_argument("--out", type=Path, default=None, help="산출 JSONL 경로(기본 코퍼스 v0).")
    parser.add_argument("--short", type=int, default=_DEFAULT_SHORT_N, help="유리근 단답형 수.")
    parser.add_argument("--mc", type=int, default=_DEFAULT_MC_N, help="유리근 객관식 수.")
    parser.add_argument("--sqrt", type=int, default=_DEFAULT_SQRT_N, help="무리근 단답형 수.")
    parser.add_argument("--sqrt-mc", type=int, default=_DEFAULT_SQRT_MC_N, help="무리근 객관식 수.")
    parser.add_argument(
        "--calc-extremum",
        type=int,
        default=_DEFAULT_CALC_EXTREMUM_N,
        help="미적분 극값(삼차함수 극대·극소 x좌표) 단답형 수.",
    )
    parser.add_argument(
        "--calc-tangent",
        type=int,
        default=_DEFAULT_CALC_TANGENT_N,
        help="미적분 접선 기울기(삼차함수 접선 기울기 m인 점의 x좌표) 단답형 수.",
    )
    parser.add_argument(
        "--calc-value",
        type=int,
        default=_DEFAULT_CALC_VALUE_N,
        help="미적분 극값의 값(삼차함수 극댓값·극솟값) 단답형 수.",
    )
    parser.add_argument(
        "--exp", type=int, default=_DEFAULT_EXP_N, help="지수방정식(bˣ=bᵏ) 단답형 수."
    )
    parser.add_argument(
        "--log", type=int, default=_DEFAULT_LOG_N, help="로그방정식(log_b x=k) 단답형 수."
    )
    parser.add_argument("--dry-run", action="store_true", help="파일 미기록 — 수율·리포트만 확인.")
    args = parser.parse_args(argv)

    report = run_corpus_batch(
        out_path=args.out,
        short_n=args.short,
        mc_n=args.mc,
        sqrt_n=args.sqrt,
        sqrt_mc_n=args.sqrt_mc,
        calc_extremum_n=args.calc_extremum,
        calc_tangent_n=args.calc_tangent,
        calc_value_n=args.calc_value,
        exp_n=args.exp,
        log_n=args.log,
        write=not args.dry_run,
    )
    json.dump(report.to_json(), sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0 if report.fulfilled else 1


if __name__ == "__main__":  # pragma: no cover — 모듈 실행 진입점
    raise SystemExit(main())
