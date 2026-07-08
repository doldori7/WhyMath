"""오개념 crosswalk 커버리지·갭 리포트 — 검수 착수 전 "어디가 비어있나"를 정량화(read-only).

`crosslink_review_aid`(kebab별 근거 조인)의 짝이다. review_aid가 각 후보의 근거를 모아 검수자가
approve/reject를 판단하게 돕는다면, 이 모듈은 한 층 위 — **전 34 kebab(`CATALOG_BY_ID`)에 대해
검수·승격이 끝나면 canonical M-id가 잡히는가**를 `select_canonical` 정책으로 시뮬레이션해 갭을
드러낸다. 사람이 4b-2 검수에서 어디에 시간을 쓸지(후보 없음·모호·임계 미달)를 먼저 본다.

**판정 안 함·데이터 안 바꿈**(review_aid·harvest 동형): status·큐·라이브 테이블을 안 건드린다.
`select_canonical`(정책 정본·l1)을 재사용해 큐 후보로 결과만 흉내낸다.

**두 축의 이중 뷰**: `select_canonical`은 resolve-time 정책이라 confidence 임계(0.6)를 적용하지
않는다(promote 몫). 따라서 "canonical 잡힘(reason ok)"이어도 승자 직접매핑 conf가 0.6 미만이면
promote에서 막힌다. 리포트는 두 축을 함께 보인다:
  - **canonical 시뮬**(reason ok/no_links/no_direct/tie) — resolve-time에 단일 정체성이 잡히나?
  - **promote 가능성**(직접매핑 conf ≥ `DIRECT_MIN_CONFIDENCE`) — 승인 시 승격 규칙 통과하나?

분류(`CoverageClass`): `coverable`(ok·승자 conf≥임계)·`below_threshold`(ok이나 conf<임계)·
`ambiguous_tie`(직접매핑 최고 동률)·`no_direct`(직접매핑 후보 부재)·`no_candidate`(큐 후보 0).

**오프라인·순수·비노출**: 코드 카탈로그 + 검수 큐 JSON만(DB·HTTP 0·학생 식별자 없음).
harvest/review_aid 정본 패턴(load·pure build·format·CLI·마지막 줄 JSON 요약)을 미러.

파이프라인:
    python -m whymath_backend.l4.misconception.crosslink_coverage \\
        [--queue docs/data/misconception_crosslink_review_queue.json] [--status pending|all]
    → 갭 리포트(stdout) 검토 → 후보 부재/모호/임계 미달 kebab에 검수 우선순위(4b-2 사람 게이트)
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from whymath_backend.l1.misconception.crosslink_gate import (
    DIRECT_LINK_TYPE,
    DIRECT_MIN_CONFIDENCE,
)
from whymath_backend.l1.misconception.crosslink_resolve import (
    ResolvedLink,
    select_canonical,
)
from whymath_backend.l4.misconception.catalog import CATALOG_BY_ID
from whymath_backend.l4.misconception.crosslink_review import (
    CrosslinkReviewError,
    CrosslinkReviewItem,
    ReviewStatus,
    parse_review_queue,
)

# 리포트 기본 대상 — 검수 대상(pending)만. "all"은 전 상태(승인분 포함 현황 스냅샷).
DEFAULT_STATUSES: tuple[ReviewStatus, ...] = ("pending",)

DEFAULT_QUEUE_PATH = "docs/data/misconception_crosslink_review_queue.json"

# 커버리지 분류 — canonical 시뮬(select_canonical) × promote 가능성(conf 임계)의 결합.
CoverageClass = Literal[
    "coverable", "below_threshold", "ambiguous_tie", "no_direct", "no_candidate"
]


class KebabCoverage(BaseModel):
    """kebab-id 1개의 crosswalk 커버리지 — canonical 시뮬 결과 + promote 가능성(read-only)."""

    model_config = ConfigDict(extra="forbid")

    kebab_id: str
    in_catalog: bool
    """L4 탐지 카탈로그(`CATALOG_BY_ID`)에 실재 — False면 전사 왜곡(큐엔 있으나 카탈로그 밖)."""
    candidate_count: int
    """이 kebab에 걸린 큐 후보(행) 수."""
    direct_count: int
    """canonical 후보 자격 링크 수 = confidence NOT NULL인 직접매핑 수(select_canonical 기준)."""
    canonical_reason: Literal["ok", "no_links", "no_direct", "tie"]
    canonical_mis_id: str | None
    ambiguous: bool
    promotable_direct_count: int
    """직접매핑 중 confidence ≥ 임계(승격 규칙 통과 가능) 수 — 0이면 승인해도 promote 막힘."""
    classification: CoverageClass


class CoverageSummary(BaseModel):
    """커버리지 리포트 요약 1건 — 마지막 줄 JSON(검수 우선순위·진척 대시보드용)."""

    model_config = ConfigDict(extra="forbid")

    statuses: list[str]
    catalog_total: int
    """전 kebab 수(`CATALOG_BY_ID`)."""
    counts: dict[str, int]
    """분류별 kebab 수(coverable/below_threshold/ambiguous_tie/no_direct/no_candidate)."""
    no_candidate: list[str]
    """후보가 하나도 없는 kebab(정렬) — 검수 이전에 후보 저작이 선결."""
    ambiguous_tie: list[str]
    """직접매핑 최고 동률 kebab(정렬) — 사람 정책 확정 필요(자동 임의선택 금지)."""
    below_threshold: list[str]
    """canonical 시뮬은 잡히나 승자 conf<임계(정렬) — 승인해도 promote 막힘."""
    not_in_catalog: list[str]
    """큐에 있으나 카탈로그 밖 kebab(정렬) — 전사 왜곡(promote도 거부)."""


def _classify(*, candidate_count: int, reason: str, promotable_direct_count: int) -> CoverageClass:
    """canonical 시뮬 reason × promote 가능성 → 커버리지 분류(순수)."""
    if candidate_count == 0:
        return "no_candidate"
    if reason == "tie":
        return "ambiguous_tie"
    if reason == "no_direct":
        return "no_direct"
    # reason == "ok": 승자 직접매핑이 임계 이상이면 coverable, 아니면 promote 막힘(below_threshold).
    return "coverable" if promotable_direct_count >= 1 else "below_threshold"


def build_coverage(
    items: Iterable[CrosslinkReviewItem],
    *,
    catalog: dict[str, Any] | None = None,
    statuses: Iterable[ReviewStatus] = DEFAULT_STATUSES,
) -> list[KebabCoverage]:
    """검수 큐 행 → 전 카탈로그 kebab의 커버리지(순수·결정론·판정 없음).

    `statuses`에 해당하는 큐 행만 후보로 본다(기본 pending). 후보를 kebab별로 묶어 `ResolvedLink`로
    빌드 → `select_canonical`로 canonical 시뮬 + 직접매핑 conf 임계로 promote 가능성을 계산한다.
    카탈로그 전 kebab을 순회하므로 후보 0행 kebab(`no_candidate`)도 빠짐없이 드러난다. 큐에만 있고
    카탈로그 밖인 kebab(전사 왜곡)도 별도로 실어 검수 신호로 남긴다(조용한 누락 금지).
    """
    resolved_catalog = CATALOG_BY_ID if catalog is None else catalog
    wanted = set(statuses)
    by_kebab: dict[str, list[CrosslinkReviewItem]] = {}
    for item in items:
        if item.status in wanted:
            by_kebab.setdefault(item.kebab_id, []).append(item)

    # ① 카탈로그 전 kebab(후보 0행 포함) + ② 큐에만 있는 kebab(카탈로그 밖) — 합집합·정렬.
    all_kebabs = sorted(set(resolved_catalog) | set(by_kebab))
    coverages: list[KebabCoverage] = []
    for kebab_id in all_kebabs:
        candidates = by_kebab.get(kebab_id, [])
        links = [
            ResolvedLink(mis_id=c.mis_id, link_type=c.link_type, confidence=c.confidence)
            for c in candidates
        ]
        sel = select_canonical(links)
        promotable = sum(
            1
            for c in candidates
            if c.link_type == DIRECT_LINK_TYPE
            and c.confidence is not None
            and c.confidence >= DIRECT_MIN_CONFIDENCE
        )
        coverages.append(
            KebabCoverage(
                kebab_id=kebab_id,
                in_catalog=kebab_id in resolved_catalog,
                candidate_count=len(candidates),
                direct_count=sel.direct_count,
                canonical_reason=sel.reason,
                canonical_mis_id=sel.canonical_mis_id,
                ambiguous=sel.ambiguous,
                promotable_direct_count=promotable,
                classification=_classify(
                    candidate_count=len(candidates),
                    reason=sel.reason,
                    promotable_direct_count=promotable,
                ),
            )
        )
    return coverages


def summarize_coverage(
    coverages: Iterable[KebabCoverage], *, statuses: Iterable[ReviewStatus]
) -> CoverageSummary:
    """kebab 커버리지 → 분류별 카운트·검수 신호 목록 요약(순수)."""
    cov = list(coverages)
    counts: dict[str, int] = {
        c: 0 for c in ("coverable", "below_threshold", "ambiguous_tie", "no_direct", "no_candidate")
    }
    for k in cov:
        counts[k.classification] += 1
    return CoverageSummary(
        statuses=[str(s) for s in statuses],
        catalog_total=len(CATALOG_BY_ID),
        counts=counts,
        no_candidate=sorted(k.kebab_id for k in cov if k.classification == "no_candidate"),
        ambiguous_tie=sorted(k.kebab_id for k in cov if k.classification == "ambiguous_tie"),
        below_threshold=sorted(k.kebab_id for k in cov if k.classification == "below_threshold"),
        not_in_catalog=sorted(k.kebab_id for k in cov if not k.in_catalog),
    )


_CLASS_LABEL: dict[CoverageClass, str] = {
    "coverable": "✅ 승격 시 canonical 잡힘",
    "below_threshold": "△ canonical 시뮬되나 conf<임계(promote 막힘)",
    "ambiguous_tie": "⚠ 직접매핑 최고 동률(사람 정책 확정 필요)",
    "no_direct": "△ 직접매핑 후보 부재(부분/개념겹침만)",
    "no_candidate": "✗ 후보 0(후보 저작 선결)",
}


def _format_kebab(cov: KebabCoverage) -> str:
    """kebab 1건 한 줄 — 분류·후보/직접 수·canonical 시뮬 결과."""
    label = _CLASS_LABEL[cov.classification]
    cat = "" if cov.in_catalog else " ⚠카탈로그밖"
    canon = f" → {cov.canonical_mis_id}" if cov.canonical_mis_id else ""
    return (
        f"  {cov.kebab_id}{cat}: {label} "
        f"(후보 {cov.candidate_count}·직접 {cov.direct_count}·conf≥임계 "
        f"{cov.promotable_direct_count}·reason={cov.canonical_reason}{canon})"
    )


def format_coverage(coverages: Iterable[KebabCoverage], *, statuses: Iterable[ReviewStatus]) -> str:
    """kebab 커버리지 → 사람이 읽는 갭 리포트(마지막 줄은 파싱 가능한 JSON 요약).

    분류별로 묶어 검수 우선순위(후보 없음·모호·임계 미달)를 위에 보인다. **판정·status 변경 없음**
    (review_aid·harvest 동형 — 4b-2 사람 게이트가 실제 승인·적재·플립).
    """
    cov = list(coverages)
    summary = summarize_coverage(cov, statuses=statuses)
    status_label = ", ".join(str(s) for s in statuses)
    lines = [
        "# crosswalk 커버리지·갭 리포트 (read-only·판정 없음·select_canonical 시뮬)",
        f"대상 상태: {status_label} · 전 kebab {summary.catalog_total}종 · 분류 {summary.counts}",
        "검수 우선순위: no_candidate(후보 저작) → ambiguous_tie(정책) → below_threshold/no_direct.",
        "승인·적재·노출 플립은 사람(4b-2) — 이 리포트는 어디를 볼지만 가리킨다.",
        "",
    ]
    order: tuple[CoverageClass, ...] = (
        "no_candidate",
        "ambiguous_tie",
        "below_threshold",
        "no_direct",
        "coverable",
    )
    for cls in order:
        group = [c for c in cov if c.classification == cls]
        if not group:
            continue
        lines.append(f"## {cls} — {_CLASS_LABEL[cls]} ({len(group)}종)")
        lines.extend(_format_kebab(c) for c in group)
        lines.append("")
    lines.append(summary.model_dump_json())
    return "\n".join(lines)


def _run(queue_path: Path, statuses: tuple[ReviewStatus, ...]) -> int:
    """큐 읽어 갭 리포트 출력. 파일 부재 exit 2·큐 파싱 위반 exit 1(promote 규약 미러)."""
    if not queue_path.exists():
        print(f"검수 큐 없음: {queue_path}")
        return 2
    queue: dict[str, Any] = json.loads(queue_path.read_text(encoding="utf-8"))
    try:
        items = parse_review_queue(queue)
    except CrosslinkReviewError as exc:
        print(f"검수 큐 파싱 거부 — {exc}")
        return 1
    coverages = build_coverage(items, statuses=statuses)
    print(format_coverage(coverages, statuses=statuses))
    return 0


def main(argv: list[str] | None = None) -> int:
    """CLI 엔트리 — 검수 큐 → 전 kebab 커버리지·갭 리포트(stdout·read-only).

    반환은 종료 코드: 0=성공 · 1=검수 큐 파싱 위반 · 2=입력 파일 부재. status·큐·라이브 테이블을
    바꾸지 않는다(갭 진단만 — 승인·적재는 4b-2 사람 게이트).
    """
    parser = argparse.ArgumentParser(
        prog="python -m whymath_backend.l4.misconception.crosslink_coverage",
        description=(
            "오개념 crosswalk 검수 큐로 전 34 kebab의 canonical 커버리지를 select_canonical로 "
            "시뮬한 read-only 갭 리포트 — 후보 없음·모호·임계 미달을 드러낸다(판정·적재 없음)."
        ),
    )
    parser.add_argument(
        "--queue",
        type=Path,
        default=Path(DEFAULT_QUEUE_PATH),
        help=f"검수 큐 JSON 경로(기본 {DEFAULT_QUEUE_PATH})",
    )
    parser.add_argument(
        "--status",
        choices=["pending", "approved", "rejected", "deferred", "all"],
        default="pending",
        help="후보로 볼 검수 상태(기본 pending). all은 전 상태 현황.",
    )
    args = parser.parse_args(argv)
    status_arg: str = args.status
    statuses: tuple[ReviewStatus, ...] = (
        ("pending", "approved", "rejected", "deferred")
        if status_arg == "all"
        else (status_arg,)  # type: ignore[assignment]
    )
    return _run(args.queue, statuses)


if __name__ == "__main__":  # pragma: no cover — 엔트리포인트, _run/main이 테스트 대상
    sys.exit(main())


__all__ = [
    "CoverageClass",
    "CoverageSummary",
    "DEFAULT_STATUSES",
    "KebabCoverage",
    "build_coverage",
    "format_coverage",
    "main",
    "summarize_coverage",
]
