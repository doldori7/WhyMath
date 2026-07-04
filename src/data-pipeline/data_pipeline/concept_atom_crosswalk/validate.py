"""437↔원자 크로스워크 검증 — 그래프 레벨 invariant(skill_graph/validate.py 패턴 미러).

행 내부 불변식(match_method별 상호 일관성·confidence 범위)은 `CrosswalkEntry`(Pydantic)가
강제하므로, 여기서는 코퍼스 전체를 놓고 봐야 아는 invariant만 본다:

  - **concept_duplicate**(error) — concept_id 중복 0(행 키·join 붕괴 방지).
  - **concept_dangling**(error) — 크로스워크 concept_id가 구 437 그래프에 실재.
  - **concept_missing**(error) — 구 437 그래프 개념 전량이 크로스워크에 존재(437행 전량 원칙 —
    미매핑도 행으로 남겨야 커버리지가 실측으로 드러난다).
  - **atom_dangling**(error) — atom_codes·primary가 신 원자 백본(level=='세부개념')에 실재.
  - **primary_invariant**(error) — primary 유일(정확히 1개)·atom_codes 포함 재확인(파일 재독
    경로 방어 — 모델 우회 유입 대비 이중 점검).

커버리지(매핑/미매핑 수)는 error가 아니라 **실측 보고**다 — 하한 동결은 거버넌스 테스트 소관.
성공 기준은 **error 0건**(skill_graph §성공 기준 미러).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from data_pipeline.concept_atom_crosswalk.models import CrosswalkEntry, MatchMethod

_ERROR = "error"
_WARNING = "warning"


@dataclass(slots=True)
class ValidationIssue:
    """검증 항목 1건(skill_graph/atom_graph 미러)."""

    severity: str  # "error" | "warning"
    ref: str
    rule: str
    detail: str


@dataclass(slots=True)
class CrosswalkValidationReport:
    """크로스워크 검증 결과 — 이슈 + 커버리지 실측(매핑/미매핑/방법별 분포)."""

    entry_count: int = 0
    mapped_count: int = 0
    unmapped_count: int = 0
    method_counts: dict[str, int] = field(default_factory=dict)
    fanout_counts: dict[int, int] = field(default_factory=dict)  # 후보 수 → 행 수(1:N 분포)
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def errors(self) -> list[ValidationIssue]:
        """error 심각도 이슈."""
        return [i for i in self.issues if i.severity == _ERROR]

    @property
    def warnings(self) -> list[ValidationIssue]:
        """warning 심각도 이슈."""
        return [i for i in self.issues if i.severity == _WARNING]

    @property
    def success(self) -> bool:
        """error가 없으면 성공(warning 허용)."""
        return len(self.errors) == 0

    def counts_by_rule(self) -> dict[str, int]:
        """rule별 이슈 건수(결정론적·rule 이름 정렬)."""
        tally: dict[str, int] = {}
        for issue in self.issues:
            tally[issue.rule] = tally.get(issue.rule, 0) + 1
        return dict(sorted(tally.items()))

    def summary(self) -> str:
        """사람 가독 요약 — PASS/FAIL + 커버리지 실측."""
        verdict = "PASS" if self.success else "FAIL"
        return (
            f"크로스워크 검증[{verdict}]: {self.entry_count}행, "
            f"매핑 {self.mapped_count} · 미매핑 {self.unmapped_count}, "
            f"error {len(self.errors)}개, warning {len(self.warnings)}개"
        )

    def report_text(self, *, max_examples: int = 10) -> str:
        """rule별 집계 + 방법·1:N 분포 + 구체 위반 예시."""
        lines = [self.summary()]
        if self.method_counts:
            lines.append("  [match_method 분포]")
            for method, count in sorted(self.method_counts.items()):
                lines.append(f"    - {method}: {count}행")
        if self.fanout_counts:
            lines.append("  [1:N 분포(후보 수 → 행 수)]")
            for fanout, count in sorted(self.fanout_counts.items()):
                lines.append(f"    - {fanout}개: {count}행")
        tally = self.counts_by_rule()
        if tally:
            lines.append("  [rule별 집계]")
            for rule, count in tally.items():
                lines.append(f"    - {rule}: {count}건")
        for severity, label in ((_ERROR, "error"), (_WARNING, "warning")):
            picked = [i for i in self.issues if i.severity == severity]
            if not picked:
                continue
            lines.append(f"  [{label} 예시 (최대 {max_examples})]")
            for issue in picked[:max_examples]:
                lines.append(f"    [{label}] {issue.rule} | {issue.ref} | {issue.detail}")
        return "\n".join(lines)


def validate_crosswalk(
    entries: Sequence[CrosswalkEntry],
    concept_ids: set[str],
    atom_codes: set[str],
) -> CrosswalkValidationReport:
    """크로스워크 전체 검증 — 양측 code 실재·전량 존재·유일성·커버리지 실측.

    Args:
        entries: 크로스워크 행 전체.
        concept_ids: 구 437 그래프의 concept_id 정본 집합.
        atom_codes: 신 원자 백본 원자(level=='세부개념') code 정본 집합.
    """
    report = CrosswalkValidationReport(entry_count=len(entries))

    seen: set[str] = set()
    for entry in entries:
        # ④ concept_id 중복 0
        if entry.concept_id in seen:
            report.issues.append(
                ValidationIssue(_ERROR, entry.concept_id, "concept_duplicate", "concept_id 중복")
            )
        seen.add(entry.concept_id)

        # ① 구 그래프 측 code 실재
        if entry.concept_id not in concept_ids:
            report.issues.append(
                ValidationIssue(
                    _ERROR, entry.concept_id, "concept_dangling", "구 437 그래프에 없는 concept_id"
                )
            )

        # ① 원자 측 code 실재(dangling 0)
        for code in entry.atom_codes:
            if code not in atom_codes:
                report.issues.append(
                    ValidationIssue(
                        _ERROR,
                        entry.concept_id,
                        "atom_dangling",
                        f"원자 백본에 없는 atom code {code!r}",
                    )
                )

        # ② primary 유일성·포함 재확인(모델도 강제하나 이중 점검 — 파일 재독 경로 방어)
        if entry.match_method == MatchMethod.UNMAPPED.value:
            report.unmapped_count += 1
        else:
            report.mapped_count += 1
            if entry.primary_atom_code is None or entry.primary_atom_code not in entry.atom_codes:
                report.issues.append(
                    ValidationIssue(
                        _ERROR,
                        entry.concept_id,
                        "primary_invariant",
                        f"primary {entry.primary_atom_code!r}가 없거나 atom_codes 밖",
                    )
                )

        # ③ 커버리지 실측용 분포 집계
        method = str(entry.match_method)
        report.method_counts[method] = report.method_counts.get(method, 0) + 1
        fanout = len(entry.atom_codes)
        report.fanout_counts[fanout] = report.fanout_counts.get(fanout, 0) + 1

    # ① 구 그래프 전량 존재(437행 전량 — 미매핑도 행으로)
    for missing in sorted(concept_ids - seen):
        report.issues.append(
            ValidationIssue(
                _ERROR, missing, "concept_missing", "구 437 그래프 개념이 크로스워크에 없음"
            )
        )

    return report
