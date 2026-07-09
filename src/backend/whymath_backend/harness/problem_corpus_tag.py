"""시그니처 태깅 후처리 CLI — 코퍼스 JSONL의 `signature_patterns`만 결정론 재유도(S2-06).

배치 CLI(`problem_corpus_batch`)는 sink 기록 직전 태거를 적용하므로 그 산출물은 이미 태깅돼
있다 — 이 CLI는 **배치 밖 코퍼스**(rephrase 산출물·손저작 시드·과거 산출물)를 같은 태거
(`l1/problem_bank/signature_tagger.derive_signatures`)로 재태깅하는 별도 후처리 단계다(태거가
시그니처의 단일 권위 — 어느 경로로 만들어졌든 같은 규칙).

바이트 계약(결정론·비날조):
  - 유도 결과가 기존 `signature_patterns`와 같은 레코드는 **원문 줄 바이트 그대로** 통과한다
    (재직렬화 0 — 시그니처 필드 외 바이트 무변경을 구조적으로 보장).
  - 다른 레코드만 그 한 키를 교체해 재직렬화한다(json.dumps ensure_ascii=False — 코퍼스 기록
    규약과 동일 형태).
  - 2회 실행은 바이트 동일(멱등) — 첫 실행이 태거와 일치시키므로 두 번째는 전건 원문 통과.

사용법:
    python -m whymath_backend.harness.problem_corpus_tag \\
        --in <src.jsonl> [--out <dst.jsonl>] [--dry-run]

`--out` 생략 시 제자리 갱신(--in에 덮어쓰기). `--dry-run`은 파일 미기록·통계만 stdout에 낸다.
리포트는 JSON(총 레코드·변경 수·태깅 보유 수·패턴별 건수) — 조용한 실패 금지.

harness는 import-linter 계약 밖(조성/ops 층·상위 호출 정상 — problem_corpus_batch 선례).
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from whymath_backend.l1.problem_bank.populate import _AUTHORING_KEYS
from whymath_backend.l1.problem_bank.signature_tagger import derive_signatures
from whymath_backend.schema.problem import Problem

__all__ = ["TagCorpusReport", "main", "run_corpus_tag"]


@dataclass(frozen=True, slots=True)
class TagCorpusReport:
    """시그니처 태깅 리포트 — 총량·변경·태깅 보유·패턴별 건수(조용한 실패 금지)."""

    total: int
    changed: int
    tagged: int  # 태깅 후 시그니처 1개 이상 보유 레코드 수
    pattern_counts: dict[str, int] = field(default_factory=dict)
    written: int | None = None
    in_path: str = ""
    out_path: str = ""

    def to_json(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "changed": self.changed,
            "tagged": self.tagged,
            "pattern_counts": dict(sorted(self.pattern_counts.items())),
            "written": self.written,
            "in_path": self.in_path,
            "out_path": self.out_path,
        }


def _retag_line(stripped: str) -> tuple[str, list[str]]:
    """JSONL 한 줄을 태거로 재유도 — (산출 줄, 유도 시그니처 값 목록) 반환.

    authoring 키(`_AUTHORING_KEYS`)를 분리한 나머지로 Problem을 검증해 태거에 태운다(populate
    로더와 동일 분리 규약). 유도 결과가 기존과 같으면 **원문 줄 그대로**(바이트 보존), 다르면
    `signature_patterns` 한 키만 교체해 재직렬화한다(키 순서는 dict 삽입 순서 보존).
    """
    data: dict[str, Any] = json.loads(stripped)
    problem_fields = {k: v for k, v in data.items() if k not in _AUTHORING_KEYS}
    problem = Problem.model_validate(problem_fields)
    derived = [pattern.value for pattern in derive_signatures(problem)]

    current_raw = data.get("signature_patterns", [])
    current = [str(v) for v in current_raw] if isinstance(current_raw, list) else []
    if derived == current:
        return stripped, derived  # 무변경 — 원문 바이트 그대로(시그니처 외 무변경 보장)
    updated = dict(data)
    updated["signature_patterns"] = derived
    return json.dumps(updated, ensure_ascii=False), derived


def run_corpus_tag(
    *,
    in_path: Path,
    out_path: Path,
    write: bool = True,
) -> TagCorpusReport:
    """코퍼스 JSONL 전 레코드에 시그니처 태거를 적용 — 시그니처 필드 외 바이트 무변경·멱등.

    각 줄을 `_retag_line`으로 처리한다(빈 줄은 건너뜀 — populate 로더와 동일 관대함). 레코드가
    Problem 스키마·저작권 불변식을 위반하면 ValidationError로 즉시 실패한다(조용한 통과 금지 —
    태깅은 검증된 코퍼스에만 의미가 있다).
    """
    text = in_path.read_text(encoding="utf-8")
    out_lines: list[str] = []
    total = 0
    changed = 0
    tagged = 0
    pattern_counts: dict[str, int] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        total += 1
        out_line, derived = _retag_line(stripped)
        if out_line != stripped:
            changed += 1
        if derived:
            tagged += 1
            for pattern in derived:
                pattern_counts[pattern] = pattern_counts.get(pattern, 0) + 1
        out_lines.append(out_line)

    written: int | None = None
    if write:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text("\n".join(out_lines) + "\n" if out_lines else "", encoding="utf-8")
        written = len(out_lines)
    return TagCorpusReport(
        total=total,
        changed=changed,
        tagged=tagged,
        pattern_counts=pattern_counts,
        written=written,
        in_path=str(in_path),
        out_path=str(out_path),
    )


def main(argv: list[str] | None = None) -> int:
    """CLI 엔트리 — 재태깅 후 리포트를 JSON으로 stdout에 낸다(결정론·멱등·exit 0)."""
    parser = argparse.ArgumentParser(
        prog="python -m whymath_backend.harness.problem_corpus_tag",
        description=(
            "시그니처 태깅 후처리(S2-06) — 코퍼스 JSONL의 signature_patterns만 결정론 태거로 "
            "재유도한다(시그니처 필드 외 바이트 무변경·멱등·비날조)."
        ),
    )
    parser.add_argument("--in", dest="in_path", type=Path, required=True, help="입력 JSONL 경로.")
    parser.add_argument(
        "--out",
        dest="out_path",
        type=Path,
        default=None,
        help="산출 JSONL 경로(생략 시 --in 제자리 갱신).",
    )
    parser.add_argument("--dry-run", action="store_true", help="파일 미기록 — 통계만 출력.")
    args = parser.parse_args(argv)

    out_path: Path = args.out_path if args.out_path is not None else args.in_path
    report = run_corpus_tag(
        in_path=args.in_path,
        out_path=out_path,
        write=not args.dry_run,
    )
    json.dump(report.to_json(), sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":  # pragma: no cover — 모듈 실행 진입점
    raise SystemExit(main())
