"""L4 crosslink_shadow harvest — 구조화 관측(JSONL)을 coverage 요약으로 집계(오프라인·비노출).

`crosslink_shadow.observe_crosslink_shadow`가 `record_logger`로 emit한
`MisconceptionCrosslinkShadowObservation` 라인을 모은 파일을 읽어, kebab-id → canonical M-id
매핑 **coverage 분포**를 집계한다 — math_dsl_remediation_design.md §1.3 step3가 canonical id
플립(canary/full 노출) *전제*로 요구하는 "노출 전 측정"이다. crosswalk 테이블이 사람 검수로
차오를수록 coverage가 오르는 것을 관측해, canary go/no-go와 *크로스워크 큐레이션 우선순위*
(미매핑·1:N 모호 kebab-id)를 정량 근거로 삼는다. `step_shadow_harvest`(관측→라벨 draft)의
정본 패턴을 미러한다(load_observations·pure summarize·format·CLI).

파이프라인:
    observe_crosslink_shadow(record_logger JSON) → (운영이 JSON 페이로드 수집) obs.jsonl
    → python -m whymath_backend.l4.misconception.crosslink_shadow_harvest obs.jsonl
    → coverage 요약(stdout) 검토 → canary 플립 여부·미매핑 kebab-id 큐레이션 결정

**비노출·오프라인**: HTTP/런타임/DB 경로 0(순수 파싱·집계). **프라이버시**: 관측 자체가 학생
식별자·풀이 원문을 담지 않으므로(카탈로그 식별자·개수만) 요약도 비식별이다(crosslink_shadow 규약).
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Iterable
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from whymath_backend.l4.misconception.crosslink_shadow import (
    MisconceptionCrosslinkShadowObservation,
)


def load_observations(text: str) -> list[MisconceptionCrosslinkShadowObservation]:
    """JSONL 텍스트(한 줄당 관측 JSON) → 리스트. 빈 줄·`#` 무시(step_shadow_harvest 동형).

    파싱 오류는 line 번호와 함께 ValueError로 던진다(조용한 누락 금지).
    """
    observations: list[MisconceptionCrosslinkShadowObservation] = []
    for line_num, raw in enumerate(text.splitlines(), start=1):
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        try:
            observations.append(
                MisconceptionCrosslinkShadowObservation.model_validate_json(stripped)
            )
        except Exception as exc:  # noqa: BLE001 — 줄 번호 컨텍스트와 함께 재던짐
            raise ValueError(f"line {line_num}: {exc}") from exc
    return observations


class CrosslinkCoverageSummary(BaseModel):
    """crosswalk shadow coverage 요약 1건 — 관측 스트림 집계 결과(canary 근거·큐레이션 우선순위).

    관측-단위 지표(총량·매핑률·1:N 분포)와 *distinct kebab-id* 단위 지표(실 런타임 키 커버리지)를
    함께 담는다 — canary 플립은 "얼마나 많은 *서로 다른* 런타임 kebab-id가 canonical 매핑을 갖느냐"
    (distinct coverage)가 핵심이라 관측 빈도와 분리해 본다.
    """

    model_config = ConfigDict(extra="forbid")

    total: int
    """관측 총건수."""

    mapped: int
    """`mapped=True` 관측 수(canonical M-id 1개 이상 해석됨)."""

    unmapped: int
    """`mapped=False` 관측 수(coverage 0 — 미매핑)."""

    coverage_ratio: float
    """`mapped / total`(총건 0이면 0.0) — 관측-단위 매핑률."""

    single_mapped: int
    """`mis_id_count == 1` 관측 수(단일 canonical — 무모호 플립 후보)."""

    multi_mapped: int
    """`mis_id_count > 1` 관측 수(1:N 모호 — 사람 정책 결정 필요)."""

    kebab_invalid: int
    """`kebab_valid=False` 관측 수(정본 카탈로그 밖 kebab-id — 게이트 우회 진입 신호)."""

    distinct_kebab_ids: int
    """관측에 등장한 서로 다른 kebab-id 수."""

    distinct_mapped: int
    """1건 이상에서 매핑된 서로 다른 kebab-id 수(런타임 키 커버리지 분자)."""

    distinct_coverage_ratio: float
    """`distinct_mapped / distinct_kebab_ids`(0이면 0.0) — 런타임 키 단위 커버리지(canary 핵심)."""

    ambiguous_kebab_ids: list[str]
    """1건이라도 1:N(`mis_id_count > 1`)이던 kebab-id(정렬) — canonical 플립 전 사람 정책 필요."""

    unmapped_kebab_ids: list[str]
    """한 번도 매핑 안 된 서로 다른 kebab-id(정렬) — 크로스워크 큐레이션 우선순위(coverage 공백)."""


def summarize(
    observations: Iterable[MisconceptionCrosslinkShadowObservation],
) -> CrosslinkCoverageSummary:
    """관측 스트림 → coverage 요약(순수·결정론).

    관측-단위 카운트와, kebab-id로 dedup한 distinct 단위 커버리지를 함께 낸다. distinct 집계는
    "그 kebab-id가 *한 번이라도* 매핑됐는가·*한 번이라도* 1:N이었는가"를 OR로 접어 판정한다
    (분포가 시점마다 흔들려도 커버리지·모호성은 관측 전체의 합집합으로 본다).
    """
    obs = list(observations)
    total = len(obs)
    mapped = sum(1 for o in obs if o.mapped)
    single_mapped = sum(1 for o in obs if o.mis_id_count == 1)
    multi_mapped = sum(1 for o in obs if o.mis_id_count > 1)
    kebab_invalid = sum(1 for o in obs if not o.kebab_valid)

    # distinct kebab-id별 커버리지·모호성 접기(합집합 OR).
    per_mapped: dict[str, bool] = {}
    per_ambiguous: dict[str, bool] = {}
    for o in obs:
        per_mapped[o.kebab_id] = per_mapped.get(o.kebab_id, False) or o.mapped
        per_ambiguous[o.kebab_id] = per_ambiguous.get(o.kebab_id, False) or (o.mis_id_count > 1)

    distinct = len(per_mapped)
    distinct_mapped = sum(1 for v in per_mapped.values() if v)
    ambiguous_ids = sorted(k for k, v in per_ambiguous.items() if v)
    unmapped_ids = sorted(k for k, v in per_mapped.items() if not v)

    return CrosslinkCoverageSummary(
        total=total,
        mapped=mapped,
        unmapped=total - mapped,
        coverage_ratio=(mapped / total if total else 0.0),
        single_mapped=single_mapped,
        multi_mapped=multi_mapped,
        kebab_invalid=kebab_invalid,
        distinct_kebab_ids=distinct,
        distinct_mapped=distinct_mapped,
        distinct_coverage_ratio=(distinct_mapped / distinct if distinct else 0.0),
        ambiguous_kebab_ids=ambiguous_ids,
        unmapped_kebab_ids=unmapped_ids,
    )


def format_summary(summary: CrosslinkCoverageSummary) -> str:
    """coverage 요약 → 사람이 읽는 리포트(canary go/no-go 판단용·마지막 줄은 파싱 가능한 JSON).

    상단은 사람용 요약, 마지막 줄은 `model_dump_json` 한 줄(다운스트림 재적재·회귀 스냅샷용).
    """
    obs_pct = f"{summary.coverage_ratio * 100:.1f}%"
    dist_pct = f"{summary.distinct_coverage_ratio * 100:.1f}%"
    lines = [
        "# crosslink shadow coverage — 노출 전 측정(canary go/no-go 근거)",
        f"관측 total={summary.total} mapped={summary.mapped} (coverage={obs_pct}) "
        f"unmapped={summary.unmapped}",
        f"매핑 분포: single={summary.single_mapped} multi(1:N)={summary.multi_mapped} "
        f"| kebab_invalid={summary.kebab_invalid}",
        f"distinct kebab-id: {summary.distinct_kebab_ids} / 매핑됨 {summary.distinct_mapped} "
        f"(distinct coverage={dist_pct})",
        f"1:N 모호 kebab-id(정책 필요): {summary.ambiguous_kebab_ids}",
        f"미매핑 kebab-id(크로스워크 큐레이션 우선순위): {summary.unmapped_kebab_ids}",
        summary.model_dump_json(),
    ]
    return "\n".join(lines)


def _run(specs_path: Path) -> int:
    text = specs_path.read_text(encoding="utf-8")
    print(format_summary(summarize(load_observations(text))))
    return 0


def main(argv: list[str] | None = None) -> int:
    """CLI 엔트리 — 관측 JSONL → coverage 요약(stdout). 종료 0."""
    parser = argparse.ArgumentParser(
        prog="python -m whymath_backend.l4.misconception.crosslink_shadow_harvest",
        description=(
            "crosslink_shadow 관측 JSONL → kebab→M-id coverage 요약 — canary 플립 근거·미매핑/"
            "1:N kebab-id 큐레이션 우선순위(오프라인·비노출·노출 전 측정)."
        ),
    )
    parser.add_argument(
        "specs_path",
        type=str,
        help="MisconceptionCrosslinkShadowObservation JSONL 경로(record_logger 수집물)",
    )
    args = parser.parse_args(argv)
    specs_path: str = args.specs_path
    return _run(Path(specs_path))


if __name__ == "__main__":  # pragma: no cover — 엔트리포인트, _run/main이 테스트 대상
    sys.exit(main())


__all__ = [
    "CrosslinkCoverageSummary",
    "format_summary",
    "load_observations",
    "main",
    "summarize",
]
