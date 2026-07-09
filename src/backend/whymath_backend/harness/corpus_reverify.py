"""전 코퍼스 재검증 CLI — 초인간 검증 §2 "S6 상시성"(순수·결정론·LLM 0).

정본: `docs/standards/superhuman_verification_standard.md` §2 S6. 사람은 승인 후 문항을
다시 보지 않지만(재검수 0회), 기계는 **전 코퍼스를 매일 밤 전수 재검증**할 수 있다.
코퍼스 JSONL의 `verify{conditions, answer_map, answer_selection}` 재료로 각 문항의
정답을 Tier1(`verify_answer`) + 수치 반례 fuzz(`counterexample_fuzz`)로 다시 검산해,
**fail이 하나라도 있으면 exit 1**(정본 변경·데이터 오염을 야간 CI가 즉시 잡는다).

정직성: verify 재료가 없거나 파싱 불가한 문항은 skip(집계에 skipped로)하고, *fail만*
게이트를 깬다 — 재검증 불가를 오염으로 오판하지 않는다(모르면 모른다). `--fuzz`를 켜면
수치 반례까지 돌려 심볼릭 사각지대도 훑는다(느리지만 야간 배치엔 적합).

사용:
    python -m whymath_backend.harness.corpus_reverify <코퍼스.jsonl>          # Tier1+근선택
    python -m whymath_backend.harness.corpus_reverify <코퍼스.jsonl> --fuzz   # 수치 반례까지
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

from whymath_backend.l3.equivalent.counterexample_fuzz import fuzz_answer
from whymath_backend.l3.verify_answer import verify_answer, verify_root_selection

_EXIT_OK = 0
_EXIT_FAIL = 1


@dataclass(slots=True, frozen=True)
class ReverifyReport:
    """재검증 배치 결과 — 통과·실패·skip 카운트 + 실패 상세. 불변."""

    passed: int
    failed: int
    skipped: int
    failures: tuple[tuple[str, str], ...]  # (slug/id, 사유)

    @property
    def total(self) -> int:
        return self.passed + self.failed + self.skipped


def _iter_records(text: str) -> list[dict[str, object]]:
    """JSONL 텍스트 → 레코드 리스트(빈 줄·주석 무시)."""
    records: list[dict[str, object]] = []
    for line_num, raw in enumerate(text.splitlines(), start=1):
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        try:
            records.append(json.loads(stripped))
        except json.JSONDecodeError as exc:
            raise ValueError(f"line {line_num}: {exc}") from exc
    return records


def _reverify_one(record: dict[str, object], *, use_fuzz: bool) -> tuple[str, str | None]:
    """레코드 1건 재검증 → (상태, 사유). 상태: 'pass'/'fail'/'skip'. 사유는 fail/skip 때만.

    verify 재료(conditions/answer_map)가 없으면 skip. Tier1 fail 또는 근 선택 위반 또는
    (use_fuzz 시) 수치 반례 fail이면 fail. unverifiable은 오염이 아니므로 skip 처리.
    """
    verify = record.get("verify")
    if not isinstance(verify, dict):
        return "skip", "verify 재료 없음"
    conditions = verify.get("conditions")
    answer_map = verify.get("answer_map")
    selection = verify.get("answer_selection")
    if not isinstance(conditions, str) or not isinstance(answer_map, dict):
        return "skip", "conditions/answer_map 형식 부적합"
    amap = {str(k): str(v) for k, v in answer_map.items()}

    # Tier1 답 검산.
    tier1 = verify_answer(conditions, amap)
    if tier1.state == "fail":
        return "fail", f"Tier1 fail: {tier1.reason}"

    # 근 선택(있으면) — 위반은 fail, 확인 불가는 오염 아님.
    if isinstance(selection, str) and selection in ("largest", "smallest", "unique"):
        sel = verify_root_selection(conditions, amap, selection)  # type: ignore[arg-type]
        if sel.state == "fail":
            return "fail", f"근 선택({selection}) 위반: {sel.reason}"

    # 수치 반례 fuzz(옵션) — fail만 오염으로 본다.
    if use_fuzz:
        fuzz = fuzz_answer(conditions, amap, selection if isinstance(selection, str) else None)
        if fuzz.state == "fail":
            return "fail", f"수치 반례: {fuzz.reason}"

    # Tier1 pass면 통과, unverifiable(파라미터·판정 불가)은 skip(오염 아님).
    if tier1.state == "pass":
        return "pass", None
    return "skip", f"Tier1 unverifiable: {tier1.reason}"


def reverify_corpus(records: list[dict[str, object]], *, use_fuzz: bool) -> ReverifyReport:
    """레코드 리스트 전수 재검증 → 집계 리포트(순수)."""
    passed = failed = skipped = 0
    failures: list[tuple[str, str]] = []
    for record in records:
        ident = str(record.get("slug") or record.get("problem_id") or "?")
        state, reason = _reverify_one(record, use_fuzz=use_fuzz)
        if state == "pass":
            passed += 1
        elif state == "fail":
            failed += 1
            failures.append((ident, reason or ""))
        else:
            skipped += 1
    return ReverifyReport(passed=passed, failed=failed, skipped=skipped, failures=tuple(failures))


def format_report(report: ReverifyReport, *, path: str) -> str:
    """사람 가독 요약 — 통과/실패/skip + 실패 상세."""
    lines = [
        "=" * 60,
        "전 코퍼스 재검증 — 상시성(초인간 검증 S6)",
        "=" * 60,
        f"코퍼스: {path}",
        f"총 {report.total}  통과 {report.passed}  실패 {report.failed}  skip {report.skipped}",
    ]
    if report.failures:
        lines.append("[실패 상세]")
        for ident, reason in report.failures[:50]:
            lines.append(f"  {ident}: {reason}")
        if len(report.failures) > 50:
            lines.append(f"  … 외 {len(report.failures) - 50}건")
    lines.append("=" * 60)
    return "\n".join(lines)


def _run(paths: list[Path], *, use_fuzz: bool) -> int:
    exit_code = _EXIT_OK
    for path in paths:
        records = _iter_records(path.read_text(encoding="utf-8"))
        report = reverify_corpus(records, use_fuzz=use_fuzz)
        print(format_report(report, path=str(path)))
        if report.failed > 0:
            exit_code = _EXIT_FAIL
    return exit_code


def main(argv: list[str] | None = None) -> int:
    """CLI — 코퍼스 JSONL(들) 전수 재검증. 실패 1건이라도 있으면 exit 1."""
    parser = argparse.ArgumentParser(
        prog="python -m whymath_backend.harness.corpus_reverify",
        description="전 코퍼스 verify 재료로 정답을 전수 재검산(상시성 게이트·S6).",
    )
    parser.add_argument("paths", nargs="+", help="코퍼스 JSONL 경로(들).")
    parser.add_argument(
        "--fuzz", action="store_true", help="수치 반례 fuzz까지 실행(느리지만 야간 배치용)."
    )
    args = parser.parse_args(argv)
    return _run([Path(p) for p in args.paths], use_fuzz=args.fuzz)


if __name__ == "__main__":  # pragma: no cover — 엔트리포인트
    sys.exit(main())
