"""L4 judge-shadow harvest — judge would-remove/keep verdict 분포를 집계(오프라인·비노출).

`shadow.observe_misconception_judge_shadow`가 `judge_record_logger`로 emit한
`MisconceptionJudgeShadowObservation` 라인을 모은 파일을 읽어, judge가 의미 후보를 얼마나
**걸러내는지**(would-remove=NOT_EXPRESSES)와 **유지하는지**(would-keep=EXPRESSES+UNCERTAIN),
그리고 verdict 분포·불확실률을 집계한다 — 04b Phase 1이 judge 노출(on) *전제*로 요구하는
"노출 전 실데이터 judge 효과 검증"이다. `semantic_shadow_harvest`·`wrong_form_shadow_harvest`
정본 패턴을 미러한다.

canary 결정의 세 신호:
  - **remove_rate**(would-remove / 후보): judge가 의미 후보 중 몇 %를 FP로 걸러내나 — 통합의
    *가치*(정밀도 향상). 지나치게 높으면 over-removal(recall 손실) 경계.
  - **uncertain_rate**(UNCERTAIN / 후보): 모호·폴백(형식 위반·seam 예외) 비율 — judge *신뢰
    리스크*. 높으면 judge 라우팅·프롬프트 재점검 신호.
  - **would_remove_id_freq**: judge가 가장 자주 걸러낸 오개념 id — 의미 매처 FP의 주 원천 진단.

파이프라인:
    observe_misconception_judge_shadow(judge_record_logger JSON) → (운영이 JSON 수집) obs.jsonl
    → python -m whymath_backend.l4.misconception.judge_shadow_harvest obs.jsonl
    → verdict 분포·remove/uncertain 율 검토 → judge 노출(on)·라우팅 결정

**비노출·오프라인**: HTTP/런타임/DB 경로 0(순수 파싱·집계). **프라이버시**: 관측 자체가 학생 진술·
judge 근거를 담지 않으므로(추상 오개념 id·verdict 카운트만) 요약도 비식별이다(shadow.py 규약).
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Iterable
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from whymath_backend.l4.misconception.shadow import MisconceptionJudgeShadowObservation


def load_observations(text: str) -> list[MisconceptionJudgeShadowObservation]:
    """JSONL 텍스트(한 줄당 관측 JSON) → 리스트. 빈 줄·`#` 무시(harvest 정본 동형).

    파싱 오류는 line 번호와 함께 ValueError로 던진다(조용한 누락 금지).
    """
    observations: list[MisconceptionJudgeShadowObservation] = []
    for line_num, raw in enumerate(text.splitlines(), start=1):
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        try:
            observations.append(MisconceptionJudgeShadowObservation.model_validate_json(stripped))
        except Exception as exc:  # noqa: BLE001 — 줄 번호 컨텍스트와 함께 재던짐
            raise ValueError(f"line {line_num}: {exc}") from exc
    return observations


class JudgeShadowSummary(BaseModel):
    """judge-shadow verdict 분포 요약 1건 — would-remove/keep·불확실률·라우팅(judge 노출 근거).

    관측·후보 총량, verdict 분포(EXPRESSES/NOT_EXPRESSES/UNCERTAIN), 후보-단위 remove/uncertain
    율, judge가 걸러낸 오개념 id별 빈도, 관측에 섞인 라우팅 프로파일을 담는다 — judge 노출(on)이
    "얼마나 안전하게 FP를 걸러내나(remove_rate)·얼마나 모호한가(uncertain_rate)"로 결정된다.
    """

    model_config = ConfigDict(extra="forbid")

    total: int
    """관측 총건수."""

    candidates: int
    """judge에 투입된 의미 후보 총수(관측별 `candidate_count` 합·율 분모)."""

    verdict_expresses: int
    """`예`(EXPRESSES) 총 판정 수 — 진짜 오개념 표현으로 본 후보(유지)."""

    verdict_not_expresses: int
    """`아니오`(NOT_EXPRESSES) 총 판정 수 — judge가 제거할 후보(=would-remove)."""

    verdict_uncertain: int
    """`불확실`(UNCERTAIN) 총 판정 수 — 모호 + 모든 폴백의 귀착점(유지·보수)."""

    would_keep: int
    """유지 후보 총수(`verdict_expresses + verdict_uncertain` — recall 보존분)."""

    remove_rate: float
    """`verdict_not_expresses / candidates`(후보 0이면 0.0) — judge FP 필터 강도(통합 가치)."""

    uncertain_rate: float
    """`verdict_uncertain / candidates`(후보 0이면 0.0) — judge 모호·폴백 비율(신뢰 리스크)."""

    would_remove_id_freq: dict[str, int]
    """오개념 id → judge가 제거(would-remove)한 횟수(키 정렬) — 의미 매처 FP 주 원천."""

    routings: list[str]
    """관측에 등장한 서로 다른 judge 라우팅 프로파일 라벨(정렬·None 제외) — 운영점 맥락."""


def summarize(
    observations: Iterable[MisconceptionJudgeShadowObservation],
) -> JudgeShadowSummary:
    """관측 스트림 → judge verdict 분포 요약(순수·결정론).

    verdict 카운트는 관측의 `verdict_*` 필드(권위)를 합산하고, id별 제거 빈도는 `would_remove_ids`
    목록에서 센다. 율은 후보 총수(`candidate_count` 합) 대비로 낸다. 라우팅은 non-null 라벨의
    합집합을 정렬해 담는다(운영점이 섞였는지 맥락 제공).
    """
    obs = list(observations)
    total = len(obs)
    candidates = sum(o.candidate_count for o in obs)
    n_expresses = sum(o.verdict_expresses for o in obs)
    n_not_expresses = sum(o.verdict_not_expresses for o in obs)
    n_uncertain = sum(o.verdict_uncertain for o in obs)

    remove_id_freq: dict[str, int] = {}
    routings: set[str] = set()
    for o in obs:
        for mid in o.would_remove_ids:
            remove_id_freq[mid] = remove_id_freq.get(mid, 0) + 1
        if o.judge_routing is not None:
            routings.add(o.judge_routing)

    return JudgeShadowSummary(
        total=total,
        candidates=candidates,
        verdict_expresses=n_expresses,
        verdict_not_expresses=n_not_expresses,
        verdict_uncertain=n_uncertain,
        would_keep=n_expresses + n_uncertain,
        remove_rate=(n_not_expresses / candidates if candidates else 0.0),
        uncertain_rate=(n_uncertain / candidates if candidates else 0.0),
        would_remove_id_freq=dict(sorted(remove_id_freq.items())),
        routings=sorted(routings),
    )


def format_summary(summary: JudgeShadowSummary) -> str:
    """verdict 분포 요약 → 사람이 읽는 리포트(judge 노출 판단용·마지막 줄은 파싱 가능한 JSON)."""
    remove_pct = f"{summary.remove_rate * 100:.1f}%"
    uncertain_pct = f"{summary.uncertain_rate * 100:.1f}%"
    lines = [
        "# judge-shadow 분포 — would-remove/keep·불확실률(judge 노출 근거)",
        f"관측 total={summary.total} 후보 candidates={summary.candidates} "
        f"routings={summary.routings}",
        f"verdict: 예={summary.verdict_expresses} 아니오={summary.verdict_not_expresses} "
        f"불확실={summary.verdict_uncertain} | would_keep={summary.would_keep}",
        f"remove_rate={remove_pct}(FP 필터 강도) uncertain_rate={uncertain_pct}(신뢰 리스크)",
        f"would-remove id별: {summary.would_remove_id_freq}",
        summary.model_dump_json(),
    ]
    return "\n".join(lines)


def _run(specs_path: Path) -> int:
    text = specs_path.read_text(encoding="utf-8")
    print(format_summary(summarize(load_observations(text))))
    return 0


def main(argv: list[str] | None = None) -> int:
    """CLI 엔트리 — 관측 JSONL → judge verdict 분포 요약(stdout). 종료 0."""
    parser = argparse.ArgumentParser(
        prog="python -m whymath_backend.l4.misconception.judge_shadow_harvest",
        description=(
            "judge-shadow 관측 JSONL → would-remove/keep·verdict 분포 요약 — judge 노출(on) "
            "근거(remove_rate/uncertain_rate)·FP 원천(would-remove id) (오프라인·비노출)."
        ),
    )
    parser.add_argument(
        "specs_path",
        type=str,
        help="MisconceptionJudgeShadowObservation JSONL 경로(judge_record_logger 수집물)",
    )
    args = parser.parse_args(argv)
    specs_path: str = args.specs_path
    return _run(Path(specs_path))


if __name__ == "__main__":  # pragma: no cover — 엔트리포인트, _run/main이 테스트 대상
    sys.exit(main())


__all__ = [
    "JudgeShadowSummary",
    "format_summary",
    "load_observations",
    "main",
    "summarize",
]
