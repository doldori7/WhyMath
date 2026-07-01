"""L4 wrong_form shadow harvest — SymPy vs substring 탐지 분포를 집계(오프라인·비노출).

`wrong_form_match.observe_wrong_form_shadow`가 `record_logger`로 emit한
`WrongFormShadowObservation` 라인을 모은 파일을 읽어, SymPy 거짓 항등식 탐지와 기존
substring/regex 탐지(`diagnose`)의 **일치·순기여 분포**를 집계한다 —
math_dsl_remediation_design.md §2.5가 노출 통합(substring과 결합·canary) *전제*로 요구하는
"shadow 측정"이다. `crosslink_shadow_harvest`·`step_shadow_harvest`의 정본 패턴을 미러한다.

canary 통합 결정의 두 축:
  - **SymPy 순기여**(`sympy_only_*`): substring이 놓친(변수명·표기 변이) 오개념을 SymPy가
    새로 잡은 양 — 통합의 *가치*. 높을수록 canary 근거가 강하다.
  - **substring 단독**(`substring_only_*`): substring이 잡았는데 SymPy가 못 잡은 양 — SymPy로
    *대체*하면 잃을 탐지(회귀 리스크). 설계는 대체가 아닌 *결합*이므로, 이 목록은 결합 후에도
    substring 경로가 계속 커버해야 할 오개념을 알려준다.

파이프라인:
    observe_wrong_form_shadow(record_logger JSON) → (운영이 JSON 수집) obs.jsonl
    → python -m whymath_backend.l4.misconception.wrong_form_shadow_harvest obs.jsonl
    → 분포 요약(stdout) 검토 → canary 통합 여부·결합 정책 결정

**비노출·오프라인**: HTTP/런타임/DB 경로 0(순수 파싱·집계). **프라이버시**: 관측 자체가 학생 풀이
원문을 담지 않으므로(추상 카탈로그 id·개수만) 요약도 비식별이다(wrong_form_match 규약).
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Iterable
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from whymath_backend.l4.misconception.wrong_form_match import WrongFormShadowObservation


def load_observations(text: str) -> list[WrongFormShadowObservation]:
    """JSONL 텍스트(한 줄당 관측 JSON) → 리스트. 빈 줄·`#` 무시(crosslink_shadow_harvest 동형).

    파싱 오류는 line 번호와 함께 ValueError로 던진다(조용한 누락 금지).
    """
    observations: list[WrongFormShadowObservation] = []
    for line_num, raw in enumerate(text.splitlines(), start=1):
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        try:
            observations.append(WrongFormShadowObservation.model_validate_json(stripped))
        except Exception as exc:  # noqa: BLE001 — 줄 번호 컨텍스트와 함께 재던짐
            raise ValueError(f"line {line_num}: {exc}") from exc
    return observations


class WrongFormCoverageSummary(BaseModel):
    """wrong_form shadow 탐지 분포 요약 1건 — SymPy vs substring 비교 집계(canary 통합 근거).

    관측-단위 히트 카운트와, 오개념 id별 SymPy-순기여·substring-단독 빈도를 담는다 — canary 통합은
    "SymPy가 얼마나 새로 잡고(가치), 결합 후 substring이 계속 커버해야 할 게 무엇인가"로 결정한다.
    """

    model_config = ConfigDict(extra="forbid")

    total: int
    """관측 총건수."""

    sympy_hits: int
    """SymPy가 1개 이상 탐지한 관측 수(`sympy_detected_ids` 비어있지 않음)."""

    substring_hits: int
    """substring/regex가 1개 이상 탐지한 관측 수(`substring_detected_ids` 비어있지 않음)."""

    sympy_only_hits: int
    """SymPy 순기여가 있던 관측 수(`sympy_only_ids` 비어있지 않음 — substring이 놓친 걸 잡음)."""

    substring_only_hits: int
    """substring이 잡았는데 SymPy가 못 잡은 id가 있던 관측 수(결합 유지 필요·SymPy 대체 시 회귀)."""

    agreement: int
    """SymPy 탐지 집합 == substring 탐지 집합인 관측 수(완전 일치)."""

    sympy_only_id_freq: dict[str, int]
    """오개념 id → SymPy 순기여로 잡힌 횟수(키 정렬) — 통합의 가치가 큰 오개념 순위."""

    substring_only_id_freq: dict[str, int]
    """오개념 id → substring만 잡은 횟수(키 정렬) — 결합 후 substring이 계속 커버해야 할 오개념."""


def summarize(
    observations: Iterable[WrongFormShadowObservation],
) -> WrongFormCoverageSummary:
    """관측 스트림 → SymPy vs substring 분포 요약(순수·결정론).

    `sympy_only_ids`는 관측이 이미 계산해 둔 SymPy 순기여를 신뢰해 빈도를 집계한다. substring-단독은
    `substring_detected_ids - sympy_detected_ids`(집합차)로 관측마다 새로 계산한다(대칭 신호). 빈도
    dict는 키 정렬로 결정론을 보장한다.
    """
    obs = list(observations)
    total = len(obs)
    sympy_hits = sum(1 for o in obs if o.sympy_detected_ids)
    substring_hits = sum(1 for o in obs if o.substring_detected_ids)
    sympy_only_hits = sum(1 for o in obs if o.sympy_only_ids)

    sympy_only_freq: dict[str, int] = {}
    substr_only_freq: dict[str, int] = {}
    substring_only_hits = 0
    agreement = 0
    for o in obs:
        sympy_set = set(o.sympy_detected_ids)
        substr_set = set(o.substring_detected_ids)
        if sympy_set == substr_set:
            agreement += 1
        for mid in o.sympy_only_ids:
            sympy_only_freq[mid] = sympy_only_freq.get(mid, 0) + 1
        substr_only = substr_set - sympy_set
        if substr_only:
            substring_only_hits += 1
            for mid in substr_only:
                substr_only_freq[mid] = substr_only_freq.get(mid, 0) + 1

    return WrongFormCoverageSummary(
        total=total,
        sympy_hits=sympy_hits,
        substring_hits=substring_hits,
        sympy_only_hits=sympy_only_hits,
        substring_only_hits=substring_only_hits,
        agreement=agreement,
        sympy_only_id_freq=dict(sorted(sympy_only_freq.items())),
        substring_only_id_freq=dict(sorted(substr_only_freq.items())),
    )


def format_summary(summary: WrongFormCoverageSummary) -> str:
    """분포 요약 → 사람이 읽는 리포트(canary 통합 판단용·마지막 줄은 파싱 가능한 JSON)."""
    lines = [
        "# wrong_form shadow 분포 — SymPy vs substring(canary 통합 근거)",
        f"관측 total={summary.total} | sympy_hits={summary.sympy_hits} "
        f"substring_hits={summary.substring_hits} agreement={summary.agreement}",
        f"SymPy 순기여: 관측 {summary.sympy_only_hits}건 · id별 {summary.sympy_only_id_freq}",
        f"substring 단독(결합 유지 필요): 관측 {summary.substring_only_hits}건 · "
        f"id별 {summary.substring_only_id_freq}",
        summary.model_dump_json(),
    ]
    return "\n".join(lines)


def _run(specs_path: Path) -> int:
    text = specs_path.read_text(encoding="utf-8")
    print(format_summary(summarize(load_observations(text))))
    return 0


def main(argv: list[str] | None = None) -> int:
    """CLI 엔트리 — 관측 JSONL → SymPy vs substring 분포 요약(stdout). 종료 0."""
    parser = argparse.ArgumentParser(
        prog="python -m whymath_backend.l4.misconception.wrong_form_shadow_harvest",
        description=(
            "wrong_form shadow 관측 JSONL → SymPy vs substring 탐지 분포 요약 — canary 통합 "
            "근거(SymPy 순기여)·결합 정책(substring 단독) (오프라인·비노출·노출 전 측정)."
        ),
    )
    parser.add_argument(
        "specs_path",
        type=str,
        help="WrongFormShadowObservation JSONL 경로(record_logger 수집물)",
    )
    args = parser.parse_args(argv)
    specs_path: str = args.specs_path
    return _run(Path(specs_path))


if __name__ == "__main__":  # pragma: no cover — 엔트리포인트, _run/main이 테스트 대상
    sys.exit(main())


__all__ = [
    "WrongFormCoverageSummary",
    "format_summary",
    "load_observations",
    "main",
    "summarize",
]
