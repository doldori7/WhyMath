"""문제 유형(`problem_type_codes`) 결정론 백필 CLI (S3-27·LLM 0).

`problem_corpus_tag.py`(시그니처 재태깅)와 정확히 같은 **바이트 계약**을 따른다 — 유도 결과가
기존 `problem_type_codes`와 같은 레코드는 원문 줄 바이트 그대로 통과하고, 다른 레코드만 그 한
키를 교체해 재직렬화한다(`json.dumps(..., ensure_ascii=False)`). 2회 실행은 바이트 동일(멱등).

분류 자체(생성기 identity → 유형)는 `problem_type_mapping.classify_record`가 갖고 있다 — 이
CLI는 그 표를 코퍼스 파일들에 적용하는 얇은 조성 층일 뿐이다(harness는 import-linter 계약 밖
— `problem_corpus_batch`·`problem_corpus_tag` 선례와 동형).

**대상 코퍼스(결정론 순서)** — `problem_type_mapping.TARGET_CORPORA` 6종.
`problem_bank_rephrased_v0`(429건)는 여기 없다 — `S4-14`(변형 계보 영속) 미착지로 원 생성기를
추적할 수 없어 **명시 제외**한다.

⚠️ **제외 사유 소멸 (2026-08-11 · 문제은행 R3 §정정-3 · 추적 `PB-07`)**: 위 제외 사유는 더 이상
성립하지 않는다 — `S4-14`는 2026-08-05 done이고 `S4-18`도 done이며, `rephrased_v0` 429건은
**전건 계보(`relations`)를 보유**해 원 생성기 추적이 가능하다. 그럼에도 제외가 코드에 남아 유형
태깅이 2,218/2,647(83.8%)에 멈춰 있다. 이는 CLAUDE.md 금기 *"만료 없는 유예·제외 금지"* 의
2회차이며, 해제와 만료 계약(`ARCH-25` 동형)의 이 좌석 확장은 **`PB-07`이 담당**한다.
이 배너는 `PB-07` 착지 시 함께 제거한다.
이 CLI는 그 파일을 열지도, 쓰지도 않는다 — 대신 리포트의 `excluded` 절에 파일의 행 수만 세어
정직하게 기록한다(침묵 누락 금지).

사용법:
    python -m whymath_backend.harness.problem_type_backfill \\
        [--corpus-root <dir>] [--dry-run]

리포트는 JSON(코퍼스별 총량·태깅·미태깅·변경 행 수 + 제외 코퍼스 총량) — exit 0 고정(관측·백필
CLI라 게이트가 아니다 — 미태깅 존재 자체가 정상 상태일 수 있어 `problem_bank_coverage`처럼 exit
코드로 판정하지 않는다. 파싱 불가 라인은 예외로 즉시 실패해 조용한 통과를 막는다).
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from whymath_backend.harness.problem_type_mapping import (
    EXCLUDED_CORPORA,
    TARGET_CORPORA,
    classify_record,
)

__all__ = [
    "CORPUS_FILE_NAME",
    "CorpusBackfillReport",
    "TypeBackfillReport",
    "main",
    "run_backfill",
]

# harness→whymath_backend→backend→src→repo 루트(다른 harness 모듈과 동일 관례).
_REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_CORPUS_ROOT = _REPO_ROOT / "data" / "corpus"
CORPUS_FILE_NAME = "problems.jsonl"


@dataclass(frozen=True, slots=True)
class CorpusBackfillReport:
    """코퍼스 1종의 백필 결과 — 총량·태깅·미태깅·변경 행 수(조용한 실패 금지)."""

    name: str
    total: int
    tagged: int
    changed: int
    written: int | None

    @property
    def untagged(self) -> int:
        return self.total - self.tagged

    def to_json(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "total": self.total,
            "tagged": self.tagged,
            "untagged": self.untagged,
            "changed": self.changed,
            "written": self.written,
        }


@dataclass(frozen=True, slots=True)
class TypeBackfillReport:
    """배치 전체 리포트 — 대상 코퍼스별 결과 + 명시 제외 코퍼스의 정직 회계."""

    corpora: tuple[CorpusBackfillReport, ...]
    excluded_corpora: tuple[str, ...]
    excluded_total: int

    @property
    def total_target(self) -> int:
        return sum(c.total for c in self.corpora)

    @property
    def total_tagged(self) -> int:
        return sum(c.tagged for c in self.corpora)

    @property
    def total_untagged_in_target(self) -> int:
        return sum(c.untagged for c in self.corpora)

    @property
    def grand_total(self) -> int:
        """대상 + 제외 코퍼스를 합친 전체 코퍼스 행 수(정직 회계 — 2,647건 정합 확인용)."""
        return self.total_target + self.excluded_total

    def to_json(self) -> dict[str, Any]:
        return {
            "corpora": [c.to_json() for c in self.corpora],
            "excluded_corpora": list(self.excluded_corpora),
            "excluded_total": self.excluded_total,
            "total_target": self.total_target,
            "total_tagged": self.total_tagged,
            "total_untagged_in_target": self.total_untagged_in_target,
            "grand_total": self.grand_total,
        }


def _retag_line(stripped: str, *, corpus_name: str) -> tuple[str, list[str]]:
    """JSONL 한 줄을 매핑표로 재분류 — (산출 줄, 유도된 `problem_type_codes`) 반환.

    `problem_corpus_tag._retag_line`과 동일 패턴: 유도 결과가 기존과 같으면 원문 줄 그대로
    (바이트 보존), 다르면 `problem_type_codes` 한 키만 교체해 재직렬화한다.
    """
    data: dict[str, Any] = json.loads(stripped)
    derived = classify_record(corpus_name, data)

    current_raw = data.get("problem_type_codes", [])
    current = [str(v) for v in current_raw] if isinstance(current_raw, list) else []
    if derived == current:
        return stripped, derived  # 무변경 — 원문 바이트 그대로.
    updated = dict(data)
    updated["problem_type_codes"] = derived
    return json.dumps(updated, ensure_ascii=False), derived


def _backfill_corpus_file(path: Path, *, name: str, write: bool) -> CorpusBackfillReport:
    """코퍼스 JSONL 1개 백필 — 파일 부재는 0건(코퍼스 존재는 `problem_bank_coverage` 소관)."""
    if not path.is_file():
        return CorpusBackfillReport(name=name, total=0, tagged=0, changed=0, written=None)

    text = path.read_text(encoding="utf-8")
    out_lines: list[str] = []
    total = 0
    changed = 0
    tagged = 0
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        total += 1
        out_line, derived = _retag_line(stripped, corpus_name=name)
        if out_line != stripped:
            changed += 1
        if derived:
            tagged += 1
        out_lines.append(out_line)

    written: int | None = None
    if write:
        path.write_text("\n".join(out_lines) + "\n" if out_lines else "", encoding="utf-8")
        written = len(out_lines)
    return CorpusBackfillReport(
        name=name, total=total, tagged=tagged, changed=changed, written=written
    )


def _count_lines(path: Path) -> int:
    """비어있지 않은 JSONL 줄 수(정직 회계용 — 파싱 없이 존재량만 센다)."""
    if not path.is_file():
        return 0
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())


def run_backfill(*, corpus_root: Path | None = None, write: bool = True) -> TypeBackfillReport:
    """대상 6개 코퍼스 백필 + 제외 코퍼스(`problem_bank_rephrased_v0`) 정직 회계(순수 결정론)."""
    root = corpus_root if corpus_root is not None else DEFAULT_CORPUS_ROOT
    corpora = tuple(
        _backfill_corpus_file(root / name / CORPUS_FILE_NAME, name=name, write=write)
        for name in TARGET_CORPORA
    )
    excluded = tuple(sorted(EXCLUDED_CORPORA))
    excluded_total = sum(_count_lines(root / name / CORPUS_FILE_NAME) for name in excluded)
    return TypeBackfillReport(
        corpora=corpora, excluded_corpora=excluded, excluded_total=excluded_total
    )


def main(argv: list[str] | None = None) -> int:
    """CLI 엔트리 — 백필 리포트를 JSON으로 stdout에 낸다. 게이트가 아니라 exit 0 고정."""
    parser = argparse.ArgumentParser(
        prog="python -m whymath_backend.harness.problem_type_backfill",
        description=(
            "문제 유형(problem_type_codes) 결정론 백필(S3-27) — 생성기 identity 매핑표로 "
            "6개 코퍼스를 재분류한다(LLM 0·텍스트 파싱 0·바이트 계약·멱등)."
        ),
    )
    parser.add_argument(
        "--corpus-root",
        type=Path,
        default=None,
        help=f"코퍼스 루트 디렉터리(기본 {DEFAULT_CORPUS_ROOT}).",
    )
    parser.add_argument("--dry-run", action="store_true", help="파일 미기록 — 통계만 출력.")
    args = parser.parse_args(argv)

    report = run_backfill(corpus_root=args.corpus_root, write=not args.dry_run)
    json.dump(report.to_json(), sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":  # pragma: no cover — 모듈 실행 진입점
    raise SystemExit(main())
