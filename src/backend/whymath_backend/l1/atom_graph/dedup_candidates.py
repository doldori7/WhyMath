"""원자 중복 개념 검수 게이트 — 동일 코퍼스 내 임베딩 pairwise 유사도 후보 리포트(ARCH-16).

저작 위생 도구다: 원자 백본 코퍼스(`atom_graph_v1/graph.json`) *안에서만* 원자쌍의 임베딩
코사인을 전수 비교해, 임계 이상 쌍을 **사람 검수 후보**로 산출한다(`knowledge_module_gap_review.md`
§3 D4). S4-01 초·중 확장처럼 신규 개념이 대량 유입되기 전 중복·과세분 후보를 걸러내는 게이트다.

**산출물 = 검수용 후보(자동 병합 아님)**. 중복 판정·병합은 전문가 검수 소관이며(AI 자기승인
금지), 출력 JSON의 top key는 `"dedup_candidates"`로 crosswalk 3형식(`candidates`/`review_queue`/
`crosslinks`)과 비호환이라 어떤 로더도 직접 읽을 수 없다(자동 적재 구조적 차단 —
`crosslink_candidates.py` 안전장치 동형).

경계(불변):
  - **동일 코퍼스 스코프만** — atom↔atom 비교뿐, 타 kind(개념·오개념·문제) 벡터와 교차 비교
    없음(cross-table 코사인 금지·`test_embedding_namespace_governance.py` 준수).
  - **in-memory 코사인** — DB `<=>` 미사용(pgvector allowlist 무접촉)·PG 불요. 좌석 재사용:
    `load_atoms_from_graph_json`(안전 필드 name+transfer만·redaction 경로 승계)·`build_provider`·
    `cosine_similarity`.
  - stdout에 **유사도 분포 통계**(밴드 히스토그램·근사 백분위)를 함께 낸다 — 임계값 캘리브레이션의
    실측 근거 재료(점추정·인상 판정 금지의 보조).

기본 임계 0.90은 **잠정(보수)** — 실모델(bge-m3) 분포 실측 후 조정한다(fake provider 분포는
캘리브레이션 근거가 아니다).
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path

from whymath_backend.l1.atom_graph.embedding import AtomText, load_atoms_from_graph_json
from whymath_backend.l1.embedding_provider import EmbeddingProvider, cosine_similarity

# 잠정(보수) 기본 임계 — 실모델 분포 실측 전. 근거: 동일 표현(name+transfer 사실상 일치) 수준만
# 후보로 올려 검수 부담을 낮춘다. 캘리브레이션은 stdout 분포 통계(실모델 실행)로.
DEFAULT_THRESHOLD: float = 0.90
# 후보 폭주 안전 상한(검수 큐가 사람 처리 가능 규모를 넘지 않게) — 초과분은 잘라내고 보고한다.
DEFAULT_MAX_CANDIDATES: int = 200
# 분포 히스토그램 해상도 — [0,1]을 0.01 폭 100밴드로(음수 코사인은 0 밴드로 클립).
_HISTOGRAM_BINS: int = 100

_NOTICE = (
    "AI 자기승인 금지 — 중복 판정·병합은 사람 검수(전문가) 소관. "
    "이 파일은 후보 리포트이며 어떤 적재 경로도 직접 읽지 않는다."
)


@dataclass(frozen=True, slots=True)
class DedupCandidate:
    """중복 의심 원자쌍 1건(검수용). code_a < code_b 정규화·`method`는 항상 'embedding'."""

    code_a: str
    code_b: str
    name_a: str
    name_b: str
    similarity: float
    method: str
    rationale: str


@dataclass(frozen=True, slots=True)
class SimilarityStats:
    """전수 pairwise 분포 요약 — 임계값 캘리브레이션 실측 근거 재료.

    `percentiles`는 히스토그램(0.01 밴드) 기반 *근사*값이다(전수 정렬 회피 — 169만 쌍 규모).
    `band_counts`는 상위 구간(0.80 이상)만 0.05 폭으로 펼친 카운트다.
    """

    pair_count: int
    max_similarity: float
    threshold_hits: int = 0
    percentiles: dict[str, float] = field(default_factory=dict)
    band_counts: dict[str, int] = field(default_factory=dict)


def _load_atom_names(path: Path) -> dict[str, str]:
    """graph.json에서 세부개념 원자의 code→name 맵만 읽는다(표시용 안전 필드)."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    out: dict[str, str] = {}
    for record in payload.get("concepts", []):
        if record.get("level") != "세부개념":
            continue
        code = str(record.get("code", "")).strip()
        if code:
            out[code] = str(record.get("name", "") or "").strip()
    return out


def _clip01(value: float) -> float:
    return min(1.0, max(0.0, value))


def _pairwise(
    vectors: Sequence[Sequence[float]],
    *,
    threshold: float,
) -> tuple[list[tuple[int, int, float]], list[int], float]:
    """전수 pairwise 코사인 — (임계 이상 쌍, [0,1] 히스토그램, 최대값).

    numpy가 있으면 행 블록 행렬곱으로 가속하고(실모델 환경엔 sentence-transformers가 numpy를
    동봉), 없으면 순수 파이썬으로 계산한다(hermetic 테스트·소형 입력). 두 경로는 동일 결과
    계약이다(부동소수 오차 범위 내).
    """
    n = len(vectors)
    hist = [0] * _HISTOGRAM_BINS
    hits: list[tuple[int, int, float]] = []
    max_sim = 0.0
    if n < 2:
        return hits, hist, max_sim

    try:  # 선택 가속 — 의존성 아님(없으면 순수 파이썬)
        import numpy
    except ModuleNotFoundError:
        numpy = None  # type: ignore[assignment]

    if numpy is not None:
        arr = numpy.asarray(vectors, dtype=float)
        norms = numpy.linalg.norm(arr, axis=1)
        norms[norms == 0.0] = 1.0  # 영벡터 방어(cosine=0 처리와 동치)
        unit = arr / norms[:, None]
        block = 256
        for start in range(0, n, block):
            rows = unit[start : start + block]
            sims = rows @ unit.T  # (block, n)
            for local_i in range(rows.shape[0]):
                i = start + local_i
                row = sims[local_i]
                for j in range(i + 1, n):
                    sim = _clip01(float(row[j]))
                    hist[min(_HISTOGRAM_BINS - 1, int(sim * _HISTOGRAM_BINS))] += 1
                    if sim > max_sim:
                        max_sim = sim
                    if sim >= threshold:
                        hits.append((i, j, sim))
        return hits, hist, max_sim

    for i in range(n):
        for j in range(i + 1, n):
            sim = _clip01(cosine_similarity(vectors[i], vectors[j]))
            hist[min(_HISTOGRAM_BINS - 1, int(sim * _HISTOGRAM_BINS))] += 1
            if sim > max_sim:
                max_sim = sim
            if sim >= threshold:
                hits.append((i, j, sim))
    return hits, hist, max_sim


def _stats_from_histogram(
    hist: Sequence[int], max_sim: float, threshold_hits: int
) -> SimilarityStats:
    """히스토그램 → 분포 요약(근사 백분위 + 상위 밴드 카운트)."""
    total = sum(hist)
    percentiles: dict[str, float] = {}
    if total:
        cumulative = 0
        targets = {"p50": 0.50, "p90": 0.90, "p99": 0.99}
        remaining = dict(targets)
        for idx, count in enumerate(hist):
            cumulative += count
            upper = (idx + 1) / _HISTOGRAM_BINS
            for name, q in list(remaining.items()):
                if cumulative / total >= q:
                    percentiles[name] = round(upper, 2)
                    del remaining[name]
    band_counts: dict[str, int] = {}
    for lo_idx in range(80, _HISTOGRAM_BINS, 5):  # 0.80부터 0.05 폭
        lo = lo_idx / _HISTOGRAM_BINS
        hi = (lo_idx + 5) / _HISTOGRAM_BINS
        band_counts[f"[{lo:.2f},{hi:.2f})"] = sum(hist[lo_idx : lo_idx + 5])
    return SimilarityStats(
        pair_count=total,
        max_similarity=round(max_sim, 4),
        threshold_hits=threshold_hits,
        percentiles=percentiles,
        band_counts=band_counts,
    )


def propose_dedup_candidates(
    *,
    provider: EmbeddingProvider,
    atoms: Sequence[AtomText],
    names: Mapping[str, str],
    threshold: float = DEFAULT_THRESHOLD,
    max_candidates: int = DEFAULT_MAX_CANDIDATES,
) -> tuple[list[DedupCandidate], SimilarityStats]:
    """원자 안전 표현을 배치 임베딩해 임계 이상 쌍을 검수 후보로 제안한다.

    결정론적(provider가 결정론이면): similarity 내림차순 → (code_a, code_b) 사전순으로 정렬하고
    `max_candidates`로 자른다(폭주 안전 상한 — 잘린 수는 호출자가 stats.pair_count와 대조해
    보고한다). 쌍은 code 사전순으로 정규화(code_a < code_b)해 대칭 중복이 없다. 자기쌍 없음.
    """
    if not atoms:
        return [], SimilarityStats(pair_count=0, max_similarity=0.0)

    vectors = provider.embed([a.text for a in atoms])
    hits, hist, max_sim = _pairwise(vectors, threshold=threshold)
    stats = _stats_from_histogram(hist, max_sim, len(hits))

    candidates: list[DedupCandidate] = []
    for i, j, sim in hits:
        code_i, code_j = atoms[i].code, atoms[j].code
        code_a, code_b = (code_i, code_j) if code_i < code_j else (code_j, code_i)
        name_a = names.get(code_a, "")
        name_b = names.get(code_b, "")
        same_name = "이름 동일" if name_a and name_a == name_b else "이름 상이"
        candidates.append(
            DedupCandidate(
                code_a=code_a,
                code_b=code_b,
                name_a=name_a,
                name_b=name_b,
                similarity=round(sim, 4),
                method="embedding",
                rationale=f"cosine={sim:.3f} · {same_name}",
            )
        )
    candidates.sort(key=lambda c: (-c.similarity, c.code_a, c.code_b))
    return candidates[:max_candidates], stats


def render_report(
    candidates: Sequence[DedupCandidate],
    stats: SimilarityStats,
    *,
    threshold: float,
    truncated: int,
) -> str:
    """stdout 요약 — 분포 통계(임계 캘리브레이션 실측 근거)와 후보 상위를 사람에게 보여준다."""
    lines = [
        "[원자 중복 후보 리포트 — 검수용·자동 병합 아님]",
        f"  전수 쌍: {stats.pair_count:,} · 최대 유사도: {stats.max_similarity}"
        f" · 임계: {threshold} · 후보: {len(candidates)}건"
        + (f" (상한 초과 {truncated}건 절단)" if truncated else ""),
        f"  근사 백분위: {stats.percentiles}",
        "  상위 밴드 분포(임계 캘리브레이션 근거):",
    ]
    for band, count in stats.band_counts.items():
        lines.append(f"    {band}: {count:,}")
    for c in candidates[:10]:
        lines.append(f"  - {c.code_a} ↔ {c.code_b} ({c.similarity}) {c.name_a} / {c.name_b}")
    if len(candidates) > 10:
        lines.append(f"  … 외 {len(candidates) - 10}건 (JSON 참조)")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI — 후보 JSON(`--out`) + stdout 분포 리포트. 파일 부재는 exit 2."""
    import argparse

    from whymath_backend.config import get_settings
    from whymath_backend.l1.embedding_primitives import provider_model_identity
    from whymath_backend.l1.embedding_provider import build_provider

    parser = argparse.ArgumentParser(
        description="원자 중복 개념 후보 리포트(동일 코퍼스 pairwise 임베딩) — 검수용·미적재"
    )
    parser.add_argument(
        "--graph",
        type=Path,
        default=Path("data/corpus/atom_graph_v1/graph.json"),
        help="원자 백본 graph.json 경로(런타임 truth source 코퍼스)",
    )
    parser.add_argument("--out", type=Path, required=True, help="후보 JSON 출력 경로(검수용)")
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)
    parser.add_argument("--max-candidates", type=int, default=DEFAULT_MAX_CANDIDATES)
    args = parser.parse_args(list(argv) if argv is not None else None)

    if not args.graph.is_file():
        print(f"[오류] graph.json 없음: {args.graph}")
        return 2

    settings = get_settings()
    provider = build_provider(settings)
    provider_name, model_name = provider_model_identity(provider, settings)

    atoms = load_atoms_from_graph_json(args.graph)
    names = _load_atom_names(args.graph)
    candidates, stats = propose_dedup_candidates(
        provider=provider,
        atoms=atoms,
        names=names,
        threshold=args.threshold,
        max_candidates=args.max_candidates,
    )
    truncated = max(0, stats.threshold_hits - len(candidates))

    payload = {
        "notice": _NOTICE,
        "provider": provider_name,
        "model": model_name,
        "threshold": args.threshold,
        "atom_count": len(atoms),
        "stats": asdict(stats),
        "dedup_candidates": [asdict(c) for c in candidates],
    }
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(render_report(candidates, stats, threshold=args.threshold, truncated=truncated))
    print(f"[중복 후보] {len(candidates)}건 → {args.out} (사람 검수 후 병합 여부 결정)")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())


__all__ = [
    "DEFAULT_MAX_CANDIDATES",
    "DEFAULT_THRESHOLD",
    "DedupCandidate",
    "SimilarityStats",
    "propose_dedup_candidates",
    "render_report",
    "main",
]
