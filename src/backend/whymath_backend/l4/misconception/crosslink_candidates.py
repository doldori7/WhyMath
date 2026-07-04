"""오개념 crosswalk 후보 *자동 생성* 도구 — kebab(30) × M-id(839) 임베딩 유사도 제안.

crosswalk 골격(`crosslink_loader.py`·`crosslink_resolve.py`)의 *후보 제안* 보조 도구다. kebab
탐지 카탈로그(`l4/misconception/catalog.py` 30종)와 M-id 콘텐츠 카탈로그(`misconception_catalog`
839종)를 의미 임베딩 코사인으로 비교해 kebab마다 상위 후보를 제안한다.

**산출물 = 검수용 후보**(라이브 테이블 자동 적재 아님·우선순위 #1·#3). 출력 JSON은 top key가
`"candidates"`라 로더(`crosslink_loader`·`"crosslinks"` 입력)가 *직접 읽을 수 없는* 형태다(자동
적재 차단·안전장치). 검수자가 승인분만 `"crosslinks"` 형식으로 옮겨 적재한다.

신호 범위(정직): kebab 카탈로그엔 `standard_code`·`error_type`가 *없어* 설계가 가정한 두 신호는
적용 불가. **주신호 = 임베딩 코사인**(canonical_statement 의미 유사). domain은 체계가 달라(대수 vs
변화와 관계) 점수에 넣지 않고 rationale 메모로만 표기한다(보수).

좌석 재사용(신규 seam 0): `l1/embedding_provider.py`(EmbeddingProvider·build_provider·
cosine_similarity — 레이어-중립 L1)·`semantic/matcher.py::catalog_text`·`catalog.py::CATALOG`.
provider 주입(Fake=결정론 테스트·실모델=Local bge-m3/OpenAI). 순수 함수(DB 불요)·CLI는 JSON 출력.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import asdict, dataclass

from whymath_backend.l1.embedding_primitives import normalize_embedding_input
from whymath_backend.l1.embedding_provider import EmbeddingProvider, cosine_similarity
from whymath_backend.l4.misconception.catalog import CATALOG
from whymath_backend.l4.misconception.models import Misconception
from whymath_backend.l4.misconception.semantic.matcher import catalog_text
from whymath_backend.schema.misconception_catalog import MisconceptionCatalog
from whymath_backend.schema.misconception_crosslink import CrosslinkMethod, CrosslinkType

# link_type 밴드(코사인 클램프 신뢰도) — 검수 보조이지 자동 채택 기준이 아니다.
_DIRECT_MIN = 0.85  # 직접매핑
_PARTIAL_MIN = 0.60  # 부분매핑(미만은 개념겹침)


@dataclass(frozen=True, slots=True)
class CrosslinkCandidate:
    """kebab → M-id 후보 1건(검수용). `confidence`=cosine 클램프, `method`는 항상 'embedding'."""

    kebab_id: str
    mis_id: str
    confidence: float
    link_type: CrosslinkType
    method: CrosslinkMethod
    rationale: str


def _mid_text(record: MisconceptionCatalog) -> str:
    """M-id 임베딩 표현 — canonical_statement + student_wrong_thinking(틀린 믿음 자연어 신호)."""
    parts = [
        p.strip()
        for p in (record.canonical_statement, record.student_wrong_thinking)
        if p is not None and p.strip()
    ]
    # kebab 표현(`catalog_text`→`join_embedding_text`)과 *같은* NFKC 정규화로 임베딩 공간 정합.
    return normalize_embedding_input(". ".join(parts))


def _link_type_for(confidence: float) -> CrosslinkType:
    """신뢰도 밴드 → 제안 link_type(검수 보조)."""
    if confidence >= _DIRECT_MIN:
        return "직접매핑"
    if confidence >= _PARTIAL_MIN:
        return "부분매핑"
    return "개념겹침"


def _rationale(kebab: Misconception, record: MisconceptionCatalog, cosine: float) -> str:
    """후보 근거 1줄 — cosine·M-id statement 요약·domain 일치 메모(점수 미반영)."""
    cs = (record.canonical_statement or "").strip()
    cs_short = cs[:40] + "…" if len(cs) > 40 else cs
    domain_note = (
        f"domain {kebab.domain}↔{record.domain}"
        + (" 일치" if record.domain == kebab.domain else "")
        if record.domain
        else f"domain {kebab.domain}↔(없음)"
    )
    return f"cosine={cosine:.3f} · M-id: {cs_short} · {domain_note}"


def propose_crosslink_candidates(
    *,
    provider: EmbeddingProvider,
    mid_records: Sequence[MisconceptionCatalog],
    kebab_catalog: Sequence[Misconception] = CATALOG,
    top_k: int = 3,
    min_confidence: float = 0.5,
) -> list[CrosslinkCandidate]:
    """kebab × M-id 임베딩 코사인으로 kebab마다 상위 후보(임계 이상·top_k)를 제안.

    provider로 kebab 텍스트(`catalog_text`)·M-id 텍스트(`_mid_text`)를 배치 임베딩한 뒤 쌍별
    코사인을 계산한다. confidence=clamp(cosine, 0, 1). kebab마다 confidence 내림차순·mis_id
    보조정렬로 상위 `top_k`(>= `min_confidence`)만 남긴다. 결정론적(provider가 결정론이면)·DB 불요.

    빈 입력(M-id 0)·top_k<=0이면 빈 리스트. M-id 텍스트가 비면 그 후보는 cosine 0으로 자연 탈락.
    """
    if not mid_records or top_k <= 0:
        return []

    kebab_list = list(kebab_catalog)
    mid_list = list(mid_records)
    kebab_vecs = provider.embed([catalog_text(m) for m in kebab_list])
    mid_vecs = provider.embed([_mid_text(r) for r in mid_list])

    out: list[CrosslinkCandidate] = []
    for kebab, kvec in zip(kebab_list, kebab_vecs, strict=True):
        scored: list[tuple[float, MisconceptionCatalog]] = []
        for record, mvec in zip(mid_list, mid_vecs, strict=True):
            conf = min(1.0, max(0.0, cosine_similarity(kvec, mvec)))
            if conf >= min_confidence:
                scored.append((conf, record))
        # confidence 내림차순·mis_id 보조정렬(결정론) → top_k.
        scored.sort(key=lambda t: (-t[0], t[1].mis_id))
        for conf, record in scored[:top_k]:
            out.append(
                CrosslinkCandidate(
                    kebab_id=kebab.id,
                    mis_id=record.mis_id,
                    confidence=round(conf, 4),
                    link_type=_link_type_for(conf),
                    method="embedding",
                    rationale=_rationale(kebab, record, conf),
                )
            )
    return out


def _main() -> None:  # pragma: no cover - CLI 배선(실모델·ops 경로)
    import argparse
    import json
    from pathlib import Path

    from whymath_backend.l1.embedding_provider import build_provider
    from whymath_backend.l1.misconception.catalog_loader import _as_collection

    parser = argparse.ArgumentParser(
        description="오개념 crosswalk 후보 자동생성(kebab×M-id 임베딩) — 검수용·미적재"
    )
    parser.add_argument(
        "--corpus",
        type=Path,
        default=Path("data/corpus/misconceptions_v1/misconceptions.json"),
        help="M-id 코퍼스 Collection JSON 경로",
    )
    parser.add_argument("--out", type=Path, required=True, help="후보 JSON 출력 경로(검수용)")
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--min-confidence", type=float, default=0.5)
    args = parser.parse_args()

    collection = _as_collection(args.corpus)
    records = [MisconceptionCatalog.model_validate(r) for r in collection.get("misconceptions", [])]
    candidates = propose_crosslink_candidates(
        provider=build_provider(),
        mid_records=records,
        top_k=args.top_k,
        min_confidence=args.min_confidence,
    )
    # top key 'candidates' — 로더('crosslinks')가 직접 못 읽는 검수 artifact(자동 적재 차단).
    payload = {"candidates": [asdict(c) for c in candidates]}
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[crosslink 후보] {len(candidates)}건 → {args.out} (검수 후 승인분만 적재)")


if __name__ == "__main__":  # pragma: no cover
    _main()


__all__ = ["CrosslinkCandidate", "propose_crosslink_candidates"]
