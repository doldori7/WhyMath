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

알려진 공백 — 그랜드파더 (§_KNOWN_GAPS, 만료 계약 ARCH-25)
--------------------------------------------------------
`S3-11-problem-bank-data-card`가 다른 세션에서 문제은행 v0 사이드카 5종을 완결했었으나
(2026-07-29 실측, 당시 미머지 브랜치) 그 시점 main엔 랜딩하지 않은 상태였다. ARCH-20은 그
5종을 사이드카 부재 SIDECAR_MISSING으로 잡지 않고 "알려진 공백"으로 건너뛰는 그랜드파더를
도입했다. ARCH-25(2026-08-03)가 그 브랜치(커밋 `4293da24`)를 회수해 5종 사이드카가 트렁크에
실재하게 됐으므로 `_KNOWN_GAPS`에서 해당 항목을 전부 제거했다 — 그랜드파더는 실재하는
사이드카에는 필요 없다.

`_KNOWN_GAPS`는 자유 문자열이 아니라 `GrandfatherEntry`(`task_id` + `reason`)를 값으로 요구한다
— 사유만 적힌 그랜드파더는 그 사유를 추적할 태스크가 done으로 넘어가도 아무도 모르고 방치되기
쉽다(2026-08-03 실측: `_S3_11_PENDING`이 S3-11 랜딩 이후에도 손 유지보수를 기다리며 5일간
방치됐다). `task_id`를 구조적으로 못박아 두면 `test_provenance_audit.py`의
`TestGrandfatherExpiryContract`가 ①task_id가 backlog/tasks/*.yaml에 실재하는지
②참조된 태스크가 이미 done인데 항목이 남아 있는지를 상시 대조해 방치를 기계로 드러낸다
(자동 해제는 아니다 — 해제는 여전히 사람 판단·손 유지보수).

짝이 되는 생성 도구 (PB-11)
-------------------------
이 게이트가 요구하는 사이드카를 *만들어 주는* 도구는
`ops/corpus_provenance_sidecar.py`(`python -m whymath_backend.ops.corpus_provenance_sidecar`)다.
2026-08-11까지 그 도구가 저장소에 0개여서 계약 만족 경로가 "JSON 손 작성"뿐이었다 — 실 사이드카
26개의 `pool`은 ARCH-20의 손 백필이다. 위반을 고칠 때 사이드카를 손으로 편집하지 말고 그 CLI를
쓴다(멱등·비파괴 — 기존 `pool`·자유 서술을 보존한다).

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
    "default_backlog_tasks_dir",
    "default_corpus_root",
    "find_grandfather_expiry_violations",
    "main",
]

_EXIT_OK = 0
_EXIT_VIOLATIONS = 1


@dataclass(slots=True, frozen=True)
class GrandfatherEntry:
    """그랜드파더(면제) 항목 — 추적 가능한 백로그 태스크 ID 필수(ARCH-25 만료 계약).

    사유 문자열만으로는 태스크가 done으로 넘어가도 아무도 모른 채 항목이 방치될 수 있다
    (`_S3_11_PENDING` 5일 방치 실측 — ARCH-25 notes). `task_id`를 구조적 필드로 못박아 두면
    `find_grandfather_expiry_violations`/`TestGrandfatherExpiryContract`가 backlog/tasks의
    실제 상태와 대조해 방치를 기계로 드러낼 수 있다(자동 해제는 아니다 — 해제는 사람 판단).
    """

    task_id: str
    reason: str


# 코퍼스명 → 그랜드파더 항목(task_id + 사유). 사이드카 부재를 위반으로 잡지 않고 건너뛴다.
# 항목 추가/삭제는 반드시 실존 백로그 태스크 id + 사유를 남긴다(test_provenance_audit.py가 동결).
# 2026-08-03 ARCH-25: S3-11 회수(커밋 4293da24)로 문제은행 v0 5종 사이드카가 트렁크에 실재하게
# 되어 그랜드파더가 전부 해소됐다 — 현재 빈 딕셔너리(향후 재발 시 GrandfatherEntry로 등재).
_KNOWN_GAPS: dict[str, GrandfatherEntry] = {}

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


def default_backlog_tasks_dir() -> Path:
    """`backlog/tasks` 저장소 정본 경로(그랜드파더 만료 계약 검증용 — ARCH-25).

    `default_corpus_root`와 동일한 `parents[4]` 관용구(ops/ → whymath_backend/ → backend/ →
    src/ → repo root)로 저장소 루트를 찾은 뒤 `backlog/tasks`를 붙인다.
    """
    return Path(__file__).resolve().parents[4] / "backlog" / "tasks"


def _load_backlog_task_statuses(tasks_dir: Path) -> dict[str, str]:
    """`backlog/tasks/*.yaml`을 가볍게 파싱해 `{task_id: status}`를 반환한다.

    `scripts/harness/store.py`의 관용구(PyYAML `safe_load`만 사용 — 임의 객체 역직렬화 금지)를
    따르되, 이 CLI는 harness 상태 전이·검증 로직 전체를 재사용하지 않는다(가벼운 조회만 필요
    — 새 무거운 의존성 추가 금지). 파싱 실패·비딕셔너리 문서는 조용히 건너뛴다(태스크 YAML의
    사람 손 편집 관용을 존중 — 이 함수의 책임은 그랜드파더 대조이지 백로그 스키마 검증이 아니다).
    """
    statuses: dict[str, str] = {}
    if not tasks_dir.is_dir():
        return statuses
    for path in sorted(tasks_dir.glob("*.yaml")):
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError:
            continue
        if not isinstance(data, dict):
            continue
        task_id = data.get("id")
        status = data.get("status")
        if isinstance(task_id, str) and isinstance(status, str):
            statuses[task_id] = status
    return statuses


def find_grandfather_expiry_violations(tasks_dir: Path | None = None) -> list[str]:
    """그랜드파더 만료 계약 위반 목록을 반환한다(빈 리스트 = 위반 없음). ARCH-25.

    ① `_KNOWN_GAPS`의 `task_id`가 `backlog/tasks/*.yaml` 어디에도 없다(오타·삭제된 태스크
       참조 — 추적 불가능한 그랜드파더).
    ② 참조된 태스크가 이미 `status: done`인데 그 항목이 여전히 `_KNOWN_GAPS`에 남아 있다
       (자동 해제가 아니다 — 방치를 구조적으로 드러내는 트립와이어일 뿐, 해제는 사람 판단).

    `_KNOWN_GAPS`는 모듈 전역을 읽는다(테스트는 `monkeypatch.setattr(pa, "_KNOWN_GAPS", ...)`로
    교체) — `audit_corpus_root`의 그랜드파더 사용 방식과 동일한 관용구.
    """
    tdir = tasks_dir if tasks_dir is not None else default_backlog_tasks_dir()
    statuses = _load_backlog_task_statuses(tdir)

    violations: list[str] = []
    for corpus_name, entry in _KNOWN_GAPS.items():
        status = statuses.get(entry.task_id)
        if status is None:
            violations.append(
                f"{corpus_name}: task_id={entry.task_id!r} 이(가) backlog/tasks/*.yaml에 "
                "존재하지 않는다 — 추적 불가능한 그랜드파더."
            )
        elif status == "done":
            violations.append(
                f"{corpus_name}: task_id={entry.task_id!r} 이(가) 이미 done인데 "
                "_KNOWN_GAPS 그랜드파더 항목이 방치되어 있다 — 해제 검토 필요."
            )
    return violations


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
            entry = _KNOWN_GAPS.get(corpus_dir.name)
            if entry is not None:
                report.grandfathered.append(
                    f"{corpus_dir.name} — {entry.reason} (task_id={entry.task_id})"
                )
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
