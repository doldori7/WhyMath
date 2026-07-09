"""프롬프트 자산 교수학 감사 — 배포 소크라테스 발화 자산 회귀 게이트(순수·CLI).

배경: `harness/pedagogical_rubric`(answer-leakage 부정지표 + `score_tutoring_response` 루브릭)는
머지됐으나 **소비처가 0**인 고아 자산이었다. SSM 게이트 큐 #12(`docs/standards/ssm_scan_2026-Q3.md`)
는 이 루브릭의 소비처를 "**프롬프트 템플릿을 이 루브릭으로 자체 평가·회귀테스트**"로 명시했다.

본 모듈이 그 첫 소비처다 — 프로젝트가 *실제로 배포하는* 소크라테스 튜터 발화 자산
(`l4/socratic/categories.EXAMPLE_QUESTION` 6종 캐논 발문)이 루브릭 준거(① 정답 미유출 ② 소크라테스
발문)를 **항상** 만족하는지 감사한다. 이를 회귀 게이트로 봉인하면, 배포 프롬프트 예시가 최상위
교수학 금기("막혔을 때 바로 정답 제공 금지")를 절대 어기지 않음을 코드로 보장한다.

순수(DB·파일·라이브 키 무관)·런타임 경로 무접촉. 라이브러리는 자산을 **주입**받아 순수를 유지하고
(l4 미import), 배포 자산 조립은 CLI/테스트가 담당한다. "판정 근거만" 톤(`needs_review_worklist`·
`reviewer_sample_package` 규약 미러 — 근거를 모으고 강제하지 않는다).
"""

from __future__ import annotations

import argparse
import re
from collections.abc import Iterable, Mapping, Sequence

from pydantic import BaseModel, ConfigDict, Field

from whymath_backend.harness.pedagogical_rubric import (
    LeakageVerdict,
    detect_answer_leakage,
    score_tutoring_response,
)

__all__ = [
    "DEFAULT_SAMPLE_ANSWERS",
    "AssetAuditItem",
    "audit_socratic_assets",
    "extract_example_responses",
    "main",
    "render_asset_audit_markdown",
]

# 표본 정답 배터리 기본값 — 자산이 어떤 대표 정답도 유출 안 함을 교차 검증(수치·식·다자리).
# pedagogical_rubric 회귀 테스트의 `_SAMPLE_ANSWERS`와 동일 표본(일관).
DEFAULT_SAMPLE_ANSWERS: tuple[str, ...] = ("42", "13", "x=7", "3.14", "100")

# 프롬프트 문서 예시 발화 마커 — `docs/prompts/socratic_template.md`의 `- 응답 예: "..."` 한 줄
# 관례. 직선 큰따옴표 안의 발화 1건을 캡처(펜스 블록·JSON은 이 마커가 없어 자동 배제).
_EXAMPLE_MARKER = re.compile(r'^\s*-\s*응답 예:\s*"(.+)"\s*$')
# 시나리오 헤더 — 예시 발화의 라벨 추적용(`### 시나리오 N: ...`).
_SCENARIO_HEADER = re.compile(r"^\s*#{2,3}\s*(시나리오\s*\d+)")

# 유출 심각도 우선순위 — 표본 배터리 중 worst_leakage 결선(클수록 심각).
_LEAKAGE_SEVERITY: dict[LeakageVerdict, int] = {
    LeakageVerdict.clean: 0,
    LeakageVerdict.undecidable: 1,
    LeakageVerdict.leaked: 2,
}


class AssetAuditItem(BaseModel):
    """배포 발화 자산 1건의 교수학 감사 결과 — 근거만(reviewer 규약 톤·판정 강제 없음)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    label: str = Field(description="자산 식별자(카테고리 키 등).")
    response: str = Field(description="감사 대상 튜터 발화(배포 자산 원문).")
    is_socratic: bool = Field(description="소크라테스 발문 신호 존재(정답 무관).")
    worst_leakage: LeakageVerdict = Field(
        description="표본 정답 배터리 중 최악 유출 판정(leaked>undecidable>clean)."
    )
    reasons: list[str] = Field(
        default_factory=list, description="판정 근거 누적(학생 비노출·조용한 실패 금지)."
    )


def _worst_leakage(verdicts: Iterable[LeakageVerdict]) -> LeakageVerdict:
    """유출 verdict 집합의 최악값(심각도 최대) — 빈 표본이면 clean(보수)."""
    return max(verdicts, key=lambda v: _LEAKAGE_SEVERITY[v], default=LeakageVerdict.clean)


def _normalize_assets(
    assets: Mapping[str, str] | Iterable[tuple[str, str]],
) -> list[tuple[str, str]]:
    """자산 입력을 (label, response) 리스트로 정규화 — Mapping·튜플 이터러블 모두 수용."""
    if isinstance(assets, Mapping):
        return list(assets.items())
    return list(assets)


def extract_example_responses(markdown: str) -> list[tuple[str, str]]:
    """프롬프트 문서 마크다운에서 예시 튜터 발화를 (라벨, 발화)로 추출한다(순수·결정론).

    `docs/prompts/socratic_template.md`의 `- 응답 예: "..."` 한 줄 관례를 대상으로 한다. 줄 스캔으로
    직전 `### 시나리오 N` 헤더를 라벨로 추적하고(헤더 없으면 `응답예{i}` 폴백), 마커 줄의 큰따옴표
    안 발화를 뽑는다. 마커가 없는 시스템 프롬프트·JSON·펜스 코드 블록은 자동 배제(순수 문자열 처리·
    파일 I/O 없음). 라벨 충돌 시 `#k` 접미(결정론).
    """
    items: list[tuple[str, str]] = []
    current_scenario: str | None = None
    seen_labels: dict[str, int] = {}
    for index, line in enumerate(markdown.splitlines(), start=1):
        header = _SCENARIO_HEADER.match(line)
        if header is not None:
            current_scenario = re.sub(r"\s+", "", header.group(1))
            continue
        marker = _EXAMPLE_MARKER.match(line)
        if marker is None:
            continue
        base = current_scenario if current_scenario is not None else f"응답예{index}"
        count = seen_labels.get(base, 0) + 1
        seen_labels[base] = count
        label = base if count == 1 else f"{base}#{count}"
        items.append((label, marker.group(1)))
    return items


def audit_socratic_assets(
    assets: Mapping[str, str] | Iterable[tuple[str, str]],
    *,
    sample_answers: Sequence[str] = DEFAULT_SAMPLE_ANSWERS,
) -> list[AssetAuditItem]:
    """배포 소크라테스 발화 자산을 교수학 루브릭으로 감사한다(순수·결정론·의존성 주입).

    각 발화에 대해 ① 소크라테스 발문 신호(정답 무관 — 자산이 발문 형식인지) ② 표본 정답 배터리
    (`sample_answers`) 중 어떤 값도 유출하지 않는지(worst_leakage)를 모은다. 라이브러리는 자산을
    주입받아 순수를 유지한다(배포 자산 조립은 CLI/테스트). 정렬은 label 안정 정렬(결정론).
    """
    items: list[AssetAuditItem] = []
    for label, response in _normalize_assets(assets):
        worst = _worst_leakage(detect_answer_leakage(response, a) for a in sample_answers)
        # 소크라테스 여부는 정답 무관 — 대표 정답 하나로 스코어해 `has_socratic_prompt`만 읽는다.
        probe_answer = sample_answers[0] if sample_answers else "0"
        is_socratic = score_tutoring_response(response, answer=probe_answer).has_socratic_prompt
        reasons = [
            f"소크라테스 발문 {'있음' if is_socratic else '없음'}.",
            f"표본 정답 {len(sample_answers)}종 중 최악 유출: {worst.value}.",
        ]
        items.append(
            AssetAuditItem(
                label=label,
                response=response,
                is_socratic=is_socratic,
                worst_leakage=worst,
                reasons=reasons,
            )
        )
    items.sort(key=lambda it: it.label)
    return items


def render_asset_audit_markdown(items: list[AssetAuditItem]) -> str:
    """자산 감사 결과를 사람이 읽을 마크다운으로 렌더(순수·판정 근거만).

    헤더에 총 자산 수·소크라테스 발문 수·정답 유출 의심(leaked) 수를, 자산마다 발화·소크라테스
    여부·최악 유출·근거를 낸다. "근거만" 톤 — 회귀 테스트가 강제를 담당하고, 렌더는 진단만 한다.
    """
    socratic = sum(1 for it in items if it.is_socratic)
    leaked = sum(1 for it in items if it.worst_leakage is LeakageVerdict.leaked)
    lines: list[str] = [
        "# 프롬프트 자산 교수학 감사 (소크라테스 발화)",
        "",
        f"- 총 자산 {len(items)} · 소크라테스 발문 {socratic} · 정답 유출 의심 {leaked}",
        "- 규약: 배포 발화 자산이 최상위 금기(정답 미유출)·소크라테스 발문을 지키는지 회귀 감사.",
        "",
    ]
    for idx, item in enumerate(items, start=1):
        ok = item.is_socratic and item.worst_leakage is not LeakageVerdict.leaked
        flag = "🟢" if ok else "🔴"
        lines.append(f"## {idx}. {flag} [{item.label}]")
        lines.append(f"- 발화: {item.response}")
        lines.append(f"- 소크라테스 발문: {'예' if item.is_socratic else '아니오'}")
        lines.append(f"- 최악 유출: {item.worst_leakage.value}")
        lines.extend(f"  - {reason}" for reason in item.reasons)
        lines.append("")
    return "\n".join(lines)


def _resolve_deployed_assets() -> dict[str, str]:  # pragma: no cover — 배포 자산 조립 glue
    """배포 소크라테스 자산(`EXAMPLE_QUESTION`)을 label→발화 맵으로 조립(l4 소비·CLI 전용).

    라이브러리 순수를 지키려 l4 import는 이 CLI 헬퍼 안에서만 한다(harness→l4 = wh1_loop 기존
    방향·계약 무영향).
    """
    from whymath_backend.l4.socratic.categories import EXAMPLE_QUESTION

    return {category.value: question for category, question in EXAMPLE_QUESTION.items()}


def _run(  # pragma: no cover — 배포 자산 조립·파일 읽기 glue
    sample_answers: Sequence[str], *, prompt_file: str | None
) -> str:
    """배포 소크라테스 자산(+선택 문서 예시)을 감사해 리포트를 렌더(계산은 라이브러리·여긴 조립만).

    기본은 `EXAMPLE_QUESTION`만. `prompt_file`이 주어지면 그 마크다운의 `- 응답 예: "..."` 예시
    발화를 추출해 병합 감사한다(라벨 `시나리오N`·category값과 충돌 없음).
    """
    assets: dict[str, str] = _resolve_deployed_assets()
    if prompt_file is not None:
        with open(prompt_file, encoding="utf-8") as handle:
            for label, response in extract_example_responses(handle.read()):
                assets[label] = response
    items = audit_socratic_assets(assets, sample_answers=sample_answers)
    return render_asset_audit_markdown(items)


def main(argv: list[str] | None = None) -> int:
    """CLI 엔트리 — 배포 소크라테스 자산 교수학 감사 리포트를 stdout에 출력. 0=성공."""
    parser = argparse.ArgumentParser(
        prog="python -m whymath_backend.harness.prompt_asset_audit",
        description=(
            "배포 소크라테스 발화 자산(EXAMPLE_QUESTION·선택적으로 프롬프트 문서 예시)이 교수학 "
            "루브릭(정답 미유출·소크라테스 발문)을 지키는지 감사·리포트한다. 순수·DB 무관."
        ),
    )
    parser.add_argument(
        "--answers",
        nargs="*",
        default=list(DEFAULT_SAMPLE_ANSWERS),
        help="유출 교차검증용 표본 정답 배터리(기본: 대표 5종).",
    )
    parser.add_argument(
        "--prompt-file",
        type=str,
        default=None,
        help='추가 감사할 프롬프트 문서 경로(선택·`- 응답 예: "..."` 예시 발화 병합).',
    )
    args = parser.parse_args(argv)
    print(_run(args.answers, prompt_file=args.prompt_file))  # pragma: no cover
    return 0  # pragma: no cover


if __name__ == "__main__":  # pragma: no cover — 모듈 실행 진입점
    raise SystemExit(main())
