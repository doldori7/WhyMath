"""S2 생성 *비수용 후보* 검수/진단 워크리스트 — 사람 검수 큐 결선(순수).

배경: `l3/equivalent/orchestrator.run_batch`가 낸 `GenerationOutcome`은 후보(candidate)·게이트
판정(acceptance)·사유(reasons)를 담지만, 배치(`problem_corpus_batch`)는 이를 *사유 문자열만*
남기고 폐기한다 — 검수·진단에 필요한 후보+근거가 휘발한다. `acceptance.py`가 "사람 검수 큐
결선은 후속"으로 남긴 지점이다.

본 모듈은 **비수용 outcome**(status ∉ {accepted_stored, accepted} — 즉 needs_review·
rejected_gate·rejected_duplicate·generation_failed)을 우선순위·근거와 함께 검수자/진단용
워크리스트로 정리한다. 소비처: ① needs_review 후보의 사람 검수(S2 게이트) ② 배치 수율<요청 시
"왜 거부됐나" 진단 ③ 게이트 임계값 보정 입력.

검수 큐 규약(`reviewer_sample_package` 미러): **근거만 모으고 판정하지 않는다** — 기계 사유
(reasons·동등성 점수)를 나열하고, needs_review 항목엔 사람 판단 빈 체크박스만 둔다. 순수(DB·
파일 무관)·학생 비노출(운영 산출물)·"조용한 실패 금지"(모든 사유 보존).
"""

from __future__ import annotations

from collections.abc import Iterable

from pydantic import BaseModel, ConfigDict, Field

from whymath_backend.l3.equivalent.orchestrator import GenerationOutcome

__all__ = ["WorklistItem", "build_worklist", "render_worklist_markdown"]

# 수용(적재/dry 수용)은 워크리스트 대상이 아니다 — 나머지 4종이 검수/진단 대상.
_STORED_STATUSES: frozenset[str] = frozenset({"accepted_stored", "accepted"})

# 우선순위(작을수록 위) — 검수 가치·조치 시급성 순. needs_review(사람 판단 대기)가 최상위,
# 이어 게이트 거부·과유사 거부, 생성 실패는 마지막(후보 자체 없음).
_STATUS_PRIORITY: dict[str, int] = {
    "needs_review": 0,
    "rejected_gate": 1,
    "rejected_duplicate": 2,
    "generation_failed": 3,
}


class WorklistItem(BaseModel):
    """비수용 후보 1건 — 검수/진단 워크리스트 항목(판정 없음·근거만)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: str = Field(
        description="outcome 상태(needs_review·rejected_gate·rejected_duplicate·generation_failed)."
    )
    priority: int = Field(description="정렬 우선순위(작을수록 위·상태 기반).")
    slug: str | None = Field(
        default=None,
        description="후보 문제 slug(candidate.problem.slug·생성 실패 등으로 없으면 None).",
    )
    equivalence_score: float | None = Field(
        default=None,
        description="게이트 동등성 가중 점수 0~1(acceptance 있으면·없으면 None).",
    )
    reasons: list[str] = Field(
        default_factory=list,
        description="거부/검수/실패 사유 누적(조용한 실패 금지·학생 비노출).",
    )


def _to_item(outcome: GenerationOutcome) -> WorklistItem:
    """비수용 GenerationOutcome → WorklistItem(순수·근거 추출만)."""
    slug = outcome.candidate.problem.slug if outcome.candidate is not None else None
    score = outcome.acceptance.equivalence_score if outcome.acceptance is not None else None
    return WorklistItem(
        status=outcome.status,
        priority=_STATUS_PRIORITY.get(outcome.status, len(_STATUS_PRIORITY)),
        slug=slug,
        equivalence_score=score,
        reasons=list(outcome.reasons),
    )


def build_worklist(outcomes: Iterable[GenerationOutcome]) -> list[WorklistItem]:
    """비수용 outcome을 검수/진단 워크리스트로 정리한다(순수·필터+우선순위 정렬).

    수용(accepted_stored·accepted)은 제외한다 — 나머지 4종만 항목화한다. 정렬은 (우선순위,
    동등성 점수 내림차순, slug) — 같은 상태 안에서는 *수용에 가까운(점수 높은) 후보*를 위로 올려
    검수/구제 가치가 큰 것을 먼저 보게 한다(점수 없으면 뒤로). 결정론(안정 정렬).
    """
    items = [_to_item(o) for o in outcomes if o.status not in _STORED_STATUSES]
    items.sort(key=lambda it: (it.priority, -(it.equivalence_score or 0.0), it.slug or ""))
    return items


def render_worklist_markdown(items: list[WorklistItem], *, total_outcomes: int) -> str:
    """워크리스트를 검수자/진단용 마크다운으로 렌더(순수·판정 없음).

    헤더에 총 outcome 수와 상태별 카운트(검수필요·게이트거부·과유사거부·생성실패)를, 항목마다
    상태·slug·동등성 점수·기계 사유를 낸다. needs_review 항목엔 **사람 판단 빈 체크박스**만 두어
    "근거만 모으고 판정 안 함"(reviewer_sample_package 규약)을 지킨다.
    """
    needs_review = sum(1 for it in items if it.status == "needs_review")
    gate = sum(1 for it in items if it.status == "rejected_gate")
    dup = sum(1 for it in items if it.status == "rejected_duplicate")
    failed = sum(1 for it in items if it.status == "generation_failed")

    lines: list[str] = [
        "# S2 비수용 후보 검수/진단 워크리스트",
        "",
        f"- 총 생성 outcome: {total_outcomes} · 비수용(워크리스트) {len(items)}",
        f"- 상태별: 검수필요 {needs_review} · 게이트거부 {gate} · 과유사거부 {dup} · "
        f"생성실패 {failed}",
        "- 규약: 기계 사유만 모으고 판정하지 않는다 — needs_review는 사람 판단 체크박스로 결선.",
        "",
    ]
    for idx, item in enumerate(items, start=1):
        score = "—" if item.equivalence_score is None else f"{item.equivalence_score:.4f}"
        slug = item.slug or "(slug 없음)"
        lines.append(f"## {idx}. [{item.status}] {slug}")
        lines.append(f"- 동등성 점수: {score}")
        if item.reasons:
            lines.append("- 기계 사유:")
            lines.extend(f"  - {reason}" for reason in item.reasons)
        else:
            lines.append("- 기계 사유: (없음)")
        if item.status == "needs_review":
            lines.append("- 사람 판단(검수자 체크):")
            lines.append("  - [ ] 교육적으로 타당한 동등문제인가")
            lines.append("  - [ ] 수용(코퍼스 편입) / [ ] 반려 / [ ] 임계값 재검토 대상")
        lines.append("")
    return "\n".join(lines)
