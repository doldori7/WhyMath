"""콘텐츠 출처·라이선스 집행 게이트 — ARCH-20
(`docs/architecture/operations_module_gap_review.md` §3 D1).

배경
----
`docs/legal/copyright_gradient.md` §4.2가 "CI 또는 데이터 파이프라인 검증 단계에서 `pool`
필드 누락 콘텐츠를 차단"을 명령했으나, 실측(2026-07-29) 결과 이 집행 지점이 **0건**이었다
— `pool` 필드 자체가 코드·데이터 어디에도 없었고, CI `policy-guard` 잡은 검정교과서 본문
문자열 패턴만 검사할 뿐 코퍼스 사이드카의 라이선스 필드는 전혀 보지 않았다. 이 CLI가 그
집행 지점이다.

판정 항목
--------
① SIDECAR_MISSING   — `data/corpus/<코퍼스>/_provenance.json` 자체가 없다.
② SCHEMA_INVALID    — 사이드카는 있으나 `CorpusProvenanceSidecar` 계약(`pool` 필수 +
   서지 정보 ≥1건) 위반(JSON 파싱 실패 포함).
③ RECORD_FIELDS_MISSING — 문제은행 계열(`problems.jsonl` 보유 코퍼스)의 레코드 중
   `license`/`source_type` 필드가 결손된 건. 학생 노출 문항의 저작권 메타는 레코드
   단위로도 채워져 있어야 한다(`schema/problem.py` 정본과 정합).

알려진 공백 — 그랜드파더 (§_KNOWN_GAPS) — ARCH-25 갱신 (2026-08-03)
--------------------------------------------------------------
`S3-11-problem-bank-data-card`가 다른 세션(미머지 브랜치 `claude/education-os-architecture-mr0fbq`)
에서 문제은행 v0 사이드카 5종(`problem_bank_{conceptual,generated,killer,misconception_mc,
rephrased}_v0`)을 완결해뒀으나, 5일간 트렁크 착륙이 지연됐다(`docs/architecture/
operations_module_gap_review_r2.md` §3 D5). ARCH-25가 그 커밋을 cherry-pick으로 회수하고
(누락됐던 `pool` 필드 5건 보정 포함) 실측 감사(위반 0건)로 확인한 뒤, 이 딕셔너리에서 5개
항목을 **제거했다** — 이제 실제 사이드카가 있으므로 그랜드파더가 필요 없다. `_KNOWN_GAPS`는
현재 (아마) 빈 dict다.

D5가 지적한 근본 문제: 손 유지보수(사람이 해제를 잊으면 영구 면제가 된다)에 기계 안전망이
없었다. 그래서 ARCH-25가 계약 자체를 강화했다 — `_KNOWN_GAPS`의 값은 이제 자유 문자열이
아니라 `GrandfatherEntry(task_id, reason)`이다. `task_id`는 반드시 실존하는
`backlog/tasks/<task_id>.yaml`을 가리켜야 하고(`_load_backlog_task_status`), 그 태스크가
`status: done`인데 항목이 여전히 남아 있으면 `test_provenance_audit.py`가 **red**를 낸다.
자동 해제는 하지 않는다(면제 해제는 사람 판단 — CLAUDE.md "법령 유래 절차 기계 대체 금지"류
원칙과 동형: 이 경우는 법령은 아니지만 "정책 판단의 자동화 금지"라는 같은 정신) — 방치만
구조적으로 막는다.

종료 코드
--------
- 0 : 위반 0건(그랜드파더 제외).
- 1 : 위반 ≥1건.

사용
----
    python -m whymath_backend.ops.provenance_audit                # data/corpus 기본 경로
    python -m whymath_backend.ops.provenance_audit --corpus-root <dir>  # 테스트용 대체 경로
    python -m whymath_backend.ops.provenance_audit --json report.json
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from pydantic import ValidationError

from whymath_backend.schema.corpus_provenance import CorpusProvenanceSidecar

__all__ = [
    "AuditReport",
    "GrandfatherEntry",
    "Violation",
    "audit_corpus_root",
    "check_grandfather_task_status",
    "default_corpus_root",
    "main",
]

_EXIT_OK = 0
_EXIT_VIOLATIONS = 1

# 이 파일(ops/provenance_audit.py) 기준 저장소 루트 — ops/ → whymath_backend/ → backend/ →
# src/ → repo root(harness/problem_bank_coverage.py의 `_REPO_ROOT` 관례와 계층 깊이 동일).
_REPO_ROOT = Path(__file__).resolve().parents[4]
_BACKLOG_TASKS_DIR = _REPO_ROOT / "backlog" / "tasks"


@dataclass(slots=True, frozen=True)
class GrandfatherEntry:
    """그랜드파더 항목 — task_id는 자유 텍스트가 아니라 구조적으로 분리된 필드다.

    이래야 기계가 `task_id`로 backlog/tasks/<task_id>.yaml을 찾아 status를 검사할 수 있다
    (자유 문자열에서 정규식으로 ID를 뽑아내는 방식은 오탐/누락에 취약해 채택하지 않는다).
    """

    task_id: str
    reason: str


# 코퍼스명 → 그랜드파더 항목. 사이드카 부재를 위반으로 잡지 않고 건너뛴다.
# 항목 추가는 반드시 실존 백로그 task_id + 사유를 남긴다(test_provenance_audit.py가 동결).
# ARCH-25(2026-08-03)가 S3-11 5종을 회수·해소해 현재 비어 있다 — 형태만 남겨둔다.
_KNOWN_GAPS: dict[str, GrandfatherEntry] = {}

_PROBLEM_RECORD_FILENAME = "problems.jsonl"
_REQUIRED_RECORD_FIELDS: tuple[str, ...] = ("license", "source_type")


def _load_backlog_task_status(task_id: str, *, backlog_tasks_dir: Path) -> str | None:
    """`backlog/tasks/<task_id>.yaml`의 `status` 필드를 읽는다.

    파일 자체가 없으면 `None`(태스크 미존재 — 그랜드파더 계약 위반 판정에 사용).
    파일은 있으나 YAML 파싱이 깨졌거나 `status` 필드가 없으면 침묵하지 않고 예외를
    던진다(침묵 실패 금지 — CLAUDE.md). backlog CLI 전체를 import하지 않고 `status`
    필드 하나만 최소로 읽는다(과공학 금지).
    """
    task_path = backlog_tasks_dir / f"{task_id}.yaml"
    if not task_path.is_file():
        return None

    try:
        payload = yaml.safe_load(task_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ValueError(f"{task_path} YAML 파싱 실패 — {exc}") from exc

    if not isinstance(payload, dict) or "status" not in payload:
        raise ValueError(f"{task_path}에 status 필드가 없다 — 태스크 스키마 위반.")

    return str(payload["status"])


def check_grandfather_task_status(
    known_gaps: dict[str, GrandfatherEntry],
    *,
    backlog_tasks_dir: Path,
) -> list[str]:
    """그랜드파더 목록의 방치 여부를 검사한다 — 자동 해제는 하지 않는다.

    각 항목이 가리키는 `task_id`가 ①실존하지 않거나 ②이미 `status: done`인데 여전히
    `_KNOWN_GAPS`에 남아 있으면 그 사실을 사람이 읽을 문자열로 반환한다(빈 리스트 =
    문제 없음). 호출자(테스트)가 이 결과를 red 판정에 쓴다 — 이 함수 자체는 아무것도
    지우거나 고치지 않는다(면제 해제는 사람 판단).
    """
    problems: list[str] = []
    for corpus_name, entry in known_gaps.items():
        status = _load_backlog_task_status(entry.task_id, backlog_tasks_dir=backlog_tasks_dir)
        if status is None:
            problems.append(
                f"{corpus_name}: 그랜드파더가 참조하는 태스크 {entry.task_id}가 "
                f"{backlog_tasks_dir}에 존재하지 않는다."
            )
        elif status == "done":
            problems.append(
                f"{corpus_name}: 참조 태스크 {entry.task_id}가 이미 done인데 그랜드파더 "
                "항목이 _KNOWN_GAPS에 남아 있다 — 사람이 제거해야 한다(자동 해제 아님)."
            )
    return problems


@dataclass(slots=True, frozen=True)
class Violation:
    corpus: str
    kind: str
    detail: str


@dataclass(slots=True)
class AuditReport:
    corpus_root: str
    corpora_scanned: int
    grandfathered: list[str] = field(default_factory=list)
    violations: list[Violation] = field(default_factory=list)

    @property
    def exit_code(self) -> int:
        return _EXIT_OK if not self.violations else _EXIT_VIOLATIONS


def default_corpus_root() -> Path:
    """`data/corpus` 저장소 정본 경로 — harness CLI 공통 관용구(`parents[4]`,
    `problem_corpus_batch.py` 선례 답습: ops/ → whymath_backend/ → backend/ → src/ → repo root)."""
    return Path(__file__).resolve().parents[4] / "data" / "corpus"


def _check_record_fields(corpus_dir: Path) -> Violation | None:
    """`problems.jsonl` 보유 코퍼스만 레코드 레벨 license/source_type 결손을 검사한다."""
    records_path = corpus_dir / _PROBLEM_RECORD_FILENAME
    if not records_path.is_file():
        return None

    missing_count = 0
    total = 0
    sample_slugs: list[str] = []
    for line_no, line in enumerate(records_path.read_text(encoding="utf-8").splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        total += 1
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            return Violation(
                corpus=corpus_dir.name,
                kind="RECORD_JSON_INVALID",
                detail=f"{records_path.name}:{line_no} JSON 파싱 실패 — {exc}",
            )
        missing_fields = [f for f in _REQUIRED_RECORD_FIELDS if not record.get(f)]
        if missing_fields:
            missing_count += 1
            if len(sample_slugs) < 3:
                identifier = record.get("slug") or record.get("problem_id") or f"line {line_no}"
                sample_slugs.append(identifier)

    if missing_count == 0:
        return None
    return Violation(
        corpus=corpus_dir.name,
        kind="RECORD_FIELDS_MISSING",
        detail=(
            f"{missing_count}/{total}건 license/source_type 결손 "
            f"(예: {', '.join(sample_slugs)})"
        ),
    )


def audit_corpus_root(
    corpus_root: Path,
    *,
    known_gaps: dict[str, GrandfatherEntry] | None = None,
) -> AuditReport:
    """`corpus_root` 하위 코퍼스 디렉터리를 전수 순회해 판정한다(위 3항목 + 그랜드파더).

    `known_gaps`를 생략하면 모듈 전역 `_KNOWN_GAPS`를 쓴다(프로덕션 경로). 테스트가
    합성 그랜드파더 목록을 주입해 프로덕션 dict(현재 빈 dict일 가능성이 높다)에
    의존하지 않고 판정 로직 자체를 검증할 수 있도록 파라미터로 노출한다.
    """
    grandfather_map = _KNOWN_GAPS if known_gaps is None else known_gaps
    report = AuditReport(corpus_root=str(corpus_root), corpora_scanned=0)

    if not corpus_root.is_dir():
        report.violations.append(
            Violation(
                corpus="<root>",
                kind="CORPUS_ROOT_MISSING",
                detail=f"{corpus_root} 이(가) 디렉터리가 아니다 — 경로를 확인하라.",
            )
        )
        return report

    for corpus_dir in sorted(p for p in corpus_root.iterdir() if p.is_dir()):
        report.corpora_scanned += 1
        sidecar_path = corpus_dir / "_provenance.json"

        if not sidecar_path.is_file():
            entry = grandfather_map.get(corpus_dir.name)
            if entry is not None:
                report.grandfathered.append(f"{corpus_dir.name} — {entry.reason}")
                continue
            report.violations.append(
                Violation(
                    corpus=corpus_dir.name,
                    kind="SIDECAR_MISSING",
                    detail=f"{sidecar_path} 이(가) 없다.",
                )
            )
            continue

        try:
            payload = json.loads(sidecar_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            report.violations.append(
                Violation(
                    corpus=corpus_dir.name,
                    kind="SCHEMA_INVALID",
                    detail=f"JSON 파싱 실패 — {exc}",
                )
            )
            continue

        try:
            CorpusProvenanceSidecar.model_validate(payload)
        except ValidationError as exc:
            report.violations.append(
                Violation(
                    corpus=corpus_dir.name,
                    kind="SCHEMA_INVALID",
                    detail=str(exc),
                )
            )
            continue

        record_violation = _check_record_fields(corpus_dir)
        if record_violation is not None:
            report.violations.append(record_violation)

    return report


def _render_stdout(report: AuditReport) -> str:
    lines: list[str] = []
    lines.append("=" * 60)
    lines.append("콘텐츠 출처·라이선스 집행 게이트 (ARCH-20)")
    lines.append("=" * 60)
    lines.append(f"코퍼스 루트    : {report.corpus_root}")
    lines.append(f"스캔한 코퍼스  : {report.corpora_scanned}")
    if report.grandfathered:
        lines.append(f"그랜드파더(공백 알려짐, 위반 아님): {len(report.grandfathered)}")
        for entry in report.grandfathered:
            lines.append(f"  · {entry}")
    if report.violations:
        lines.append(f"위반          : {len(report.violations)}건")
        for v in report.violations:
            lines.append(f"  ✗ [{v.kind}] {v.corpus}: {v.detail}")
    else:
        lines.append("위반          : 0건")
    lines.append("-" * 60)
    verdict = (
        "정상(exit 0)" if report.exit_code == _EXIT_OK else f"위반 발견(exit {report.exit_code})"
    )
    lines.append(f"결과: {verdict}")
    lines.append("=" * 60)
    return "\n".join(lines)


def _write_json(report: AuditReport, path: Path) -> None:
    payload = dataclasses.asdict(report)
    payload["violations"] = [dataclasses.asdict(v) for v in report.violations]
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m whymath_backend.ops.provenance_audit",
        description="코퍼스 사이드카(_provenance.json)의 pool 필드·서지 정보·레코드 결손 감사.",
    )
    parser.add_argument(
        "--corpus-root",
        dest="corpus_root",
        default=None,
        help="감사 대상 data/corpus 디렉터리(생략 시 저장소 정본 data/corpus).",
    )
    parser.add_argument(
        "--json",
        dest="json_path",
        default=None,
        help="JSON 리포트 저장 경로(선택).",
    )
    args = parser.parse_args(argv)

    corpus_root = Path(args.corpus_root) if args.corpus_root else default_corpus_root()
    report = audit_corpus_root(corpus_root)

    print(_render_stdout(report))
    if args.json_path is not None:
        json_path = Path(args.json_path)
        _write_json(report, json_path)
        print(f"JSON 리포트 저장: {json_path}")

    return report.exit_code


if __name__ == "__main__":
    sys.exit(main())
