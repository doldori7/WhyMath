"""L4 step_shadow harvest — 구조화 관측(JSONL)을 A/B 라벨링 워크시트(draft)로 변환(오프라인·비노출).

slice 65 신호(평문 로그)와 slice 66 eval 코퍼스(`StepBreakLabel`) 사이를 잇는 도구. slice 67에서
`observe_step_breaks`가 `record_logger`로 emit한 `StepBreakObservation` 라인을 모은 파일을 읽어,
각 관측을 *라벨 미지정* draft 행(`human_label:null`)으로 변환한다. 사람이 A/B를 채우면 그대로
`step_shadow_eval`의 `StepBreakLabel`로 로드돼 precision이 측정된다.

파이프라인:
    observe_step_breaks(record_logger JSON) → (운영이 JSON 페이로드 수집) obs.jsonl
    → python -m whymath_backend.l4.step_shadow_harvest obs.jsonl > drafts.jsonl
    → 사람이 "human_label":null → "A"|"B" 편집
    → python -m whymath_backend.l4.step_shadow_eval drafts.jsonl

**비노출·오프라인**: HTTP/런타임/DB 경로 0. **프라이버시**: 관측에 학생 풀이 원문이 없으므로 draft의
`solution_text`는 빈 문자열(합성 시드는 원문 채우나 실 harvest는 비움 — 미성년자 프라이버시).
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import Literal

from whymath_backend.l4.step_shadow import StepBreakObservation
from whymath_backend.l4.step_shadow_eval import StepBreakLabel


def load_observations(text: str) -> list[StepBreakObservation]:
    """JSONL 텍스트(한 줄당 StepBreakObservation JSON) → 리스트. 빈 줄·`#` 무시.

    파싱 오류는 line 번호와 함께 ValueError로 던진다(`step_shadow_eval.load_labels` 동형).
    """
    observations: list[StepBreakObservation] = []
    for line_num, raw in enumerate(text.splitlines(), start=1):
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        try:
            observations.append(StepBreakObservation.model_validate_json(stripped))
        except Exception as exc:  # noqa: BLE001 — 줄 번호 컨텍스트와 함께 재던짐
            raise ValueError(f"line {line_num}: {exc}") from exc
    return observations


class LabelDraft(StepBreakLabel):
    """라벨 미지정 코퍼스 행 — `StepBreakLabel` 상속, `human_label`만 nullable(기본 None).

    상속으로 `StepBreakLabel`과 필드 집합을 구조적으로 일치(필드 드리프트 차단). draft JSONL의
    `"human_label": null`을 사람이 `"A"`/`"B"`로 고치면 그대로 `StepBreakLabel`(human_label 필수)로
    로드된다. 미지정인 채 eval에 넣으면 `load_labels`가 line ValueError로 "라벨 안 됨"을 알림.
    """

    human_label: Literal["A", "B"] | None = None  # type: ignore[assignment]


def to_draft(obs: StepBreakObservation) -> LabelDraft:
    """관측 → 라벨링 draft. candidate·observed_at·problem_id는 `note`로 보존(draft 필드엔 없음).

    `solution_text`는 빈 문자열 — 관측에 학생 풀이 원문이 없다(프라이버시). 라벨러는 추상화된
    `solset_*`·marker·verdict/candidate 단서로 A(변환오류)/B(변수재사용)를 판정한다. candidate는
    드롭한다 — eval이 라벨에서 candidate를 재계산하므로 중복 보관 불필요.
    """
    note = (
        f"verdict={obs.verdict} candidate={obs.candidate} "
        f"problem_id={obs.problem_id} step={obs.step_index} "
        f"observed_at={obs.observed_at.isoformat()}"
    )
    return LabelDraft(
        solset_before=obs.solset_before,
        solset_after=obs.solset_after,
        expected_answer=obs.expected_answer,
        human_label=None,
        var=obs.var,
        marker=obs.marker,
        solution_text="",
        source="shadow-log",
        note=note,
    )


def harvest(observations: Iterable[StepBreakObservation]) -> list[LabelDraft]:
    """관측 스트림 → draft 리스트(순수·결정론)."""
    return [to_draft(obs) for obs in observations]


def format_drafts(drafts: Iterable[LabelDraft]) -> str:
    """draft 리스트 → JSONL 문자열(`#` 안내 헤더 + 라인당 model_dump_json)."""
    lines = [
        '# harvest draft — 각 행 "human_label"을 "A"(변환오류)/"B"(변수재사용)로 채운 뒤',
        "# step_shadow_eval에 투입. solution_text는 프라이버시로 비어 있음(추상 단서로 라벨링).",
    ]
    lines.extend(d.model_dump_json() for d in drafts)
    return "\n".join(lines)


def _run(specs_path: Path) -> int:
    text = specs_path.read_text(encoding="utf-8")
    print(format_drafts(harvest(load_observations(text))))
    return 0


def main(argv: list[str] | None = None) -> int:
    """CLI 엔트리 — 관측 JSONL → 라벨링 draft JSONL(stdout). 종료 0."""
    parser = argparse.ArgumentParser(
        prog="python -m whymath_backend.l4.step_shadow_harvest",
        description=(
            "step_shadow 관측 JSONL → A/B 라벨링 워크시트(draft) — 사람이 human_label을 채워 "
            "step_shadow_eval에 투입(오프라인·비노출·해금 경로 ① harvest 단계)."
        ),
    )
    parser.add_argument(
        "specs_path", type=str, help="StepBreakObservation JSONL 경로(record_logger 수집물)"
    )
    args = parser.parse_args(argv)
    specs_path: str = args.specs_path
    return _run(Path(specs_path))


if __name__ == "__main__":  # pragma: no cover — 엔트리포인트, _run/main이 테스트 대상
    sys.exit(main())


__all__ = [
    "LabelDraft",
    "format_drafts",
    "harvest",
    "load_observations",
    "main",
    "to_draft",
]
