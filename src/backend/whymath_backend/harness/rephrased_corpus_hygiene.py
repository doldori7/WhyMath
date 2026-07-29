"""rephrased 코퍼스 발문 위생 일괄 적용 CLI — 위반 문항 제거(정직 축소·S3-12·결정론·LLM 0).

S3-09 감사가 확정한 rephrase 발문 텍스트 결함(한자·가나 주입/메타 라벨 누출/비표준 용어/
요구-정답 부정합/조사 오류)은 **결정론 교정이 불가**하다 — 수치 불변 봉인 때문에 발문만 LLM으로
다시 써야 하는데 이 환경은 LLM 재생성이 불가하다(Phaiakes9 라이브 전용). 따라서 위반 문항의
**탈락(제거)이 정본**이다: `rephrase_hygiene.question_hygiene_violations`(rephrase 수용 게이트
⑤축과 동일 검사기)를 커밋 코퍼스 전건에 적용해 위반 레코드를 걷어낸다.

바이트 보존: 생존 레코드는 **원 JSONL 라인 그대로** 다시 쓴다(재직렬화 0 — 무변경 필드의
바이트 드리프트 금지). 산출 리포트는 총·생존·탈락 수, 사유 분포, 탈락 (slug, 사유) 목록을
JSON으로 낸다(재검수 근거·조용한 축소 금지).

사용:
    python -m whymath_backend.harness.rephrased_corpus_hygiene            # 커밋 코퍼스 in-place
    python -m whymath_backend.harness.rephrased_corpus_hygiene --dry-run       # 판정만 출력
    python -m whymath_backend.harness.rephrased_corpus_hygiene --in A --out B  # 경로 지정

harness는 import-linter 계약 밖(조성/ops 층 — problem_corpus_rephrase 선례).
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from whymath_backend.l3.equivalent.rephrase_hygiene import question_hygiene_violations

__all__ = ["HygieneSweepReport", "main", "run_corpus_hygiene_sweep"]


def _default_corpus_path() -> Path:
    # src/backend/whymath_backend/harness/ → repo root 4단계(problem_corpus_batch 규약 미러).
    root = Path(__file__).resolve().parents[4]
    return root / "data" / "corpus" / "problem_bank_rephrased_v0" / "problems.jsonl"


@dataclass(frozen=True, slots=True)
class HygieneSweepReport:
    """일괄 적용 결과 — 총/생존/탈락 + 사유 분포 + 탈락 (slug, 사유들) 목록(불변)."""

    total: int
    kept: int
    dropped: int
    reason_counts: dict[str, int]
    dropped_items: tuple[tuple[str, tuple[str, ...]], ...]

    def to_json(self) -> dict[str, object]:
        return {
            "total": self.total,
            "kept": self.kept,
            "dropped": self.dropped,
            "reason_counts": dict(sorted(self.reason_counts.items())),
            "dropped_items": [
                {"slug": slug, "violations": list(violations)}
                for slug, violations in self.dropped_items
            ],
        }


def run_corpus_hygiene_sweep(
    in_path: Path, out_path: Path | None, *, write: bool = True
) -> HygieneSweepReport:
    """코퍼스 전건에 발문 위생 게이트 적용 — 위반 제거·생존 라인 바이트 보존(순수 파일 IO).

    각 라인을 파싱해 `question_text`를 검사하고, 위반이 하나라도 있으면 탈락시킨다. 파싱 불가
    라인은 **오염으로 단정하지 않고 예외를 그대로 던진다**(침묵 실패 금지 — 코퍼스 형식 파손은
    위생 문제가 아니라 적재 문제라 fail-loud).
    """
    raw_lines = [line for line in in_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    kept_lines: list[str] = []
    dropped_items: list[tuple[str, tuple[str, ...]]] = []
    reason_counts: Counter[str] = Counter()
    for line_num, line in enumerate(raw_lines, start=1):
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:  # 형식 파손은 fail-loud(예외 타입 포함).
            raise ValueError(f"JSONDecodeError line {line_num}: {exc}") from exc
        question = str(record.get("question_text") or "")
        violations = question_hygiene_violations(question)
        if violations:
            slug = str(record.get("slug") or f"line-{line_num}")
            dropped_items.append((slug, violations))
            for violation in violations:
                reason_counts[violation.split(":", 1)[0]] += 1
        else:
            kept_lines.append(line)

    if write:
        resolved_out = out_path if out_path is not None else in_path
        resolved_out.write_text(
            "\n".join(kept_lines) + ("\n" if kept_lines else ""), encoding="utf-8"
        )
    return HygieneSweepReport(
        total=len(raw_lines),
        kept=len(kept_lines),
        dropped=len(dropped_items),
        reason_counts=dict(reason_counts),
        dropped_items=tuple(dropped_items),
    )


def main(argv: list[str] | None = None) -> int:
    """CLI — rephrased 코퍼스 발문 위생 일괄 적용(탈락 목록·사유 분포 JSON 출력·exit 0)."""
    parser = argparse.ArgumentParser(
        prog="python -m whymath_backend.harness.rephrased_corpus_hygiene",
        description="rephrase 발문 위생 게이트를 커밋 코퍼스에 일괄 적용해 위반 문항 제거.",
    )
    parser.add_argument("--in", dest="in_path", default=None, help="입력 코퍼스 JSONL 경로.")
    parser.add_argument("--out", dest="out_path", default=None, help="출력 경로(기본 in-place).")
    parser.add_argument("--dry-run", action="store_true", help="파일 기록 없이 판정만 출력.")
    args = parser.parse_args(argv)

    in_path = Path(args.in_path) if args.in_path else _default_corpus_path()
    out_path = Path(args.out_path) if args.out_path else None
    report = run_corpus_hygiene_sweep(in_path, out_path, write=not args.dry_run)
    print(json.dumps(report.to_json(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover — 엔트리포인트
    sys.exit(main())
