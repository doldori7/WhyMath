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

알려진 공백 — 그랜드파더 (§_KNOWN_GAPS)
--------------------------------------
`S3-11-problem-bank-data-card`가 다른 세션에서 이미 문제은행 v0 사이드카 5종을 완결했으나
(2026-07-29 실측, 미머지 브랜치) 이 브랜치 시점엔 아직 main에 랜딩하지 않았다. 그 5종은
사이드카 부재를 SIDECAR_MISSING으로 잡지 않고 "알려진 공백"으로 건너뛴다 — 이미 다른
태스크가 추적 중인 것을 이 게이트가 새 위반으로 재선언하면 안 된다(중복 신호 금지). S3-11이
머지되면 이 딕셔너리에서 해당 항목을 지운다(자동 해제 아님 — 손 유지보수, HARN-10류 grandfather
선례와 동형). 그랜드파더 항목은 반드시 사유를 달아야 한다(`test_provenance_audit.py`가 동결).

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

from pydantic import ValidationError

from whymath_backend.schema.corpus_provenance import CorpusProvenanceSidecar

__all__ = [
    "AuditReport",
    "Violation",
    "audit_corpus_root",
    "default_corpus_root",
    "main",
]

_EXIT_OK = 0
_EXIT_VIOLATIONS = 1

# 코퍼스명 → 그랜드파더 사유. 사이드카 부재를 위반으로 잡지 않고 건너뛴다.
# 항목 추가/삭제는 반드시 사유 + 추적 태스크 id를 남긴다(test_provenance_audit.py가 동결).
_S3_11_PENDING = "S3-11-problem-bank-data-card 진행 중(다른 세션, 미머지) — 랜딩 시 제거"
_KNOWN_GAPS: dict[str, str] = {
    "problem_bank_conceptual_v0": _S3_11_PENDING,
    "problem_bank_generated_v0": _S3_11_PENDING,
    "problem_bank_killer_v0": _S3_11_PENDING,
    "problem_bank_misconception_mc_v0": _S3_11_PENDING,
    "problem_bank_rephrased_v0": _S3_11_PENDING,
}

_PROBLEM_RECORD_FILENAME = "problems.jsonl"
_REQUIRED_RECORD_FIELDS: tuple[str, ...] = ("license", "source_type")


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


def audit_corpus_root(corpus_root: Path) -> AuditReport:
    """`corpus_root` 하위 코퍼스 디렉터리를 전수 순회해 판정한다(위 3항목 + 그랜드파더)."""
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
            reason = _KNOWN_GAPS.get(corpus_dir.name)
            if reason is not None:
                report.grandfathered.append(f"{corpus_dir.name} — {reason}")
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
