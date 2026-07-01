"""L4 의미매칭 shadow harvest — semantic↔substring 불일치 분포 + 유사도 버킷 집계(오프라인·비노출).

`shadow.observe_misconception_shadow`가 `record_logger`로 emit한 `MisconceptionShadowObservation`
라인을 모은 파일을 읽어, 의미 매처의 **순기여**(substring이 놓친 semantic-only 후보) 분포와
그 **코사인 유사도 분포**를 집계한다 — `misconception_semantic_mode` 게이트 플립(`off`→`on`)의
노출 전 측정이자, canary feed 임계(04b §4 "feed_threshold 운영점") 선정 근거다.
`wrong_form_shadow_harvest`·`crosslink_shadow_harvest` 정본 패턴을 미러한다.

두 신호:
  - **semantic 순기여**(`semantic_only_*`): substring이 못 잡은(의미 유사) 오개념을 의미 매처가
    새로 후보로 올린 양 — 통합의 *가치*(+recall). 방향맹 FP와 뒤섞이므로 유사도로 걸러 본다.
  - **유사도 버킷**(`sim_ge_*`): semantic-only 후보를 코사인 임계별 누적 카운트로 나눠, "feed
    임계 T를 잡으면 몇 건이 남나"를 정량화 — canary 운영점(threshold) 선정의 직접 근거.

파이프라인:
    observe_misconception_shadow(record_logger JSON) → (운영이 JSON 수집) obs.jsonl
    → python -m whymath_backend.l4.misconception.semantic_shadow_harvest obs.jsonl
    → 순기여·유사도 분포 검토 → 게이트 플립·feed 임계 결정

**비노출·오프라인**: HTTP/런타임/DB 경로 0(순수 파싱·집계). **프라이버시**: 관측 자체가 학생 풀이
원문을 담지 않으므로(추상 오개념 id·유사도·개수만) 요약도 비식별이다(shadow.py 규약).
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Iterable
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from whymath_backend.l4.misconception.shadow import MisconceptionShadowObservation


def load_observations(text: str) -> list[MisconceptionShadowObservation]:
    """JSONL 텍스트(한 줄당 관측 JSON) → 리스트. 빈 줄·`#` 무시(harvest 정본 동형).

    파싱 오류는 line 번호와 함께 ValueError로 던진다(조용한 누락 금지).
    """
    observations: list[MisconceptionShadowObservation] = []
    for line_num, raw in enumerate(text.splitlines(), start=1):
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        try:
            observations.append(MisconceptionShadowObservation.model_validate_json(stripped))
        except Exception as exc:  # noqa: BLE001 — 줄 번호 컨텍스트와 함께 재던짐
            raise ValueError(f"line {line_num}: {exc}") from exc
    return observations


class SemanticShadowCoverageSummary(BaseModel):
    """의미매칭 shadow 분포 요약 1건 — semantic 순기여 + 유사도 버킷(게이트 플립·feed 임계 근거).

    관측-단위 히트와, semantic-only 후보의 오개념 id별 빈도·코사인 유사도 버킷(누적)을 담는다.
    유사도 버킷은 feed 임계 선정을 위해 *탐지 단위*(관측이 아니라 개별 semantic-only 후보)로 센다.
    """

    model_config = ConfigDict(extra="forbid")

    total: int
    """관측 총건수."""

    substr_hits: int
    """substring 후보가 1개 이상이던 관측 수(`substr_ids` 비어있지 않음)."""

    semantic_only_hits: int
    """semantic 순기여가 있던 관측 수(`semantic_only_ids` 비어있지 않음 — substring이 놓침)."""

    semantic_only_detections: int
    """semantic-only 후보 *총 탐지 수*(관측별 `semantic_only_ids` 길이 합·유사도 버킷 분모)."""

    semantic_only_id_freq: dict[str, int]
    """오개념 id → semantic-only로 오른 횟수(키 정렬) — 의미 매처 순기여가 큰 오개념 순위."""

    sim_ge_090: int
    """유사도 ≥ 0.90인 semantic-only 탐지 수(누적·고신뢰 순기여)."""

    sim_ge_080: int
    """유사도 ≥ 0.80인 semantic-only 탐지 수(누적·`sim_ge_090` 포함)."""

    sim_ge_070: int
    """유사도 ≥ 0.70인 semantic-only 탐지 수(누적·`sim_ge_080` 포함)."""

    sim_unknown: int
    """유사도 미설정(-1.0으로 표기된) semantic-only 탐지 수 — 이론상 0(의미 경로는 항상 설정)."""


def summarize(
    observations: Iterable[MisconceptionShadowObservation],
) -> SemanticShadowCoverageSummary:
    """관측 스트림 → semantic 순기여 + 유사도 버킷 요약(순수·결정론).

    semantic-only 후보를 (id, 유사도) 쌍으로 펼쳐, id별 빈도와 코사인 임계 누적 버킷(≥0.90/0.80/
    0.70)을 센다. 유사도 -1.0(미설정)은 `sim_unknown`으로만 집계하고 임계 버킷엔 넣지 않는다
    (음수라 자연히 제외). id/유사도 목록 길이가 어긋난 비정상 레코드는 zip이 짧은 쪽에 맞춘다(관대).
    """
    obs = list(observations)
    total = len(obs)
    substr_hits = sum(1 for o in obs if o.substr_ids)
    semantic_only_hits = sum(1 for o in obs if o.semantic_only_ids)

    id_freq: dict[str, int] = {}
    detections = 0
    ge_090 = ge_080 = ge_070 = unknown = 0
    for o in obs:
        # strict=False: id/유사도 길이 어긋난 비정상 레코드는 짧은 쪽에 맞춘다(harvest 관대).
        for mid, sim in zip(o.semantic_only_ids, o.semantic_only_similarities, strict=False):
            detections += 1
            id_freq[mid] = id_freq.get(mid, 0) + 1
            if sim == -1.0:
                unknown += 1
            if sim >= 0.90:
                ge_090 += 1
            if sim >= 0.80:
                ge_080 += 1
            if sim >= 0.70:
                ge_070 += 1

    return SemanticShadowCoverageSummary(
        total=total,
        substr_hits=substr_hits,
        semantic_only_hits=semantic_only_hits,
        semantic_only_detections=detections,
        semantic_only_id_freq=dict(sorted(id_freq.items())),
        sim_ge_090=ge_090,
        sim_ge_080=ge_080,
        sim_ge_070=ge_070,
        sim_unknown=unknown,
    )


def format_summary(summary: SemanticShadowCoverageSummary) -> str:
    """분포 요약 → 사람이 읽는 리포트(게이트 플립·feed 임계 판단용·마지막 줄은 파싱 가능한 JSON)."""
    lines = [
        "# 의미매칭 shadow 분포 — semantic 순기여 + 유사도 버킷(게이트 플립·feed 임계 근거)",
        f"관측 total={summary.total} substr_hits={summary.substr_hits} "
        f"semantic_only_hits={summary.semantic_only_hits}",
        f"semantic 순기여: 탐지 {summary.semantic_only_detections}건 · "
        f"id별 {summary.semantic_only_id_freq}",
        f"유사도 버킷(누적): ≥0.90={summary.sim_ge_090} ≥0.80={summary.sim_ge_080} "
        f"≥0.70={summary.sim_ge_070} | unknown={summary.sim_unknown}",
        summary.model_dump_json(),
    ]
    return "\n".join(lines)


def _run(specs_path: Path) -> int:
    text = specs_path.read_text(encoding="utf-8")
    print(format_summary(summarize(load_observations(text))))
    return 0


def main(argv: list[str] | None = None) -> int:
    """CLI 엔트리 — 관측 JSONL → semantic 순기여·유사도 버킷 요약(stdout). 종료 0."""
    parser = argparse.ArgumentParser(
        prog="python -m whymath_backend.l4.misconception.semantic_shadow_harvest",
        description=(
            "의미매칭 shadow 관측 JSONL → semantic 순기여 + 코사인 유사도 버킷 요약 — 게이트 "
            "플립·feed 임계 선정 근거(오프라인·비노출·노출 전 측정)."
        ),
    )
    parser.add_argument(
        "specs_path",
        type=str,
        help="MisconceptionShadowObservation JSONL 경로(record_logger 수집물)",
    )
    args = parser.parse_args(argv)
    specs_path: str = args.specs_path
    return _run(Path(specs_path))


if __name__ == "__main__":  # pragma: no cover — 엔트리포인트, _run/main이 테스트 대상
    sys.exit(main())


__all__ = [
    "SemanticShadowCoverageSummary",
    "format_summary",
    "load_observations",
    "main",
    "summarize",
]
