"""답 형태 요구 문항 실측 — EOS-28 acceptance ① (도입 판정 근거).

이 스크립트가 답하는 질문은 하나다: **"형태를 지시하는 문항이 코퍼스에 실제로 있는가?"**
없으면 EOS-28은 유보로 전환된다(측정 없는 도입 없음 — CLAUDE.md).

────────────────────────────────────────────────────────────────────────────
왜 "내가 아는 형태 어휘로 grep"하지 않는가
────────────────────────────────────────────────────────────────────────────
그 방식은 **내가 고른 이름이 틀렸을 때 조용히 0건**을 낸다(CLAUDE.md 「부재 판정 절차」).
실제로 1차 시도에서 `꼴로` 패턴이 24건을 잡았는데 **전부 "사다리꼴"** 오탐이었다.

그래서 두 축을 함께 돌린다:
  A. **역할 기반 전수 추출** — 지시문 꼬리(`…로 나타내시오`·`…를 구하시오`)를 정규식으로
     뽑아 *데이터가 어휘를 말하게* 한다. 내가 상상하지 못한 형태 어휘가 있으면 여기 나온다.
  B. **형태 어휘 매칭** — A가 드러낸 어휘 + 교과서 관용 형태 지시를 후보로 세되,
     **값 질문과 구별**한다("인수분해를 이용하여 근을 구하시오"는 *방법* 힌트이지 형태
     요구가 아니다 — 답은 여전히 수 하나다).

A의 출력을 눈으로 보지 않고 B만 믿으면 안 된다. 그래서 `--tails`로 A를 항상 볼 수 있게 둔다.

종료코드: 0 = 측정 성공(건수와 무관) · 1 = 측정 자체 실패(코퍼스 없음·파싱 불가).
  건수로 exit 1을 내지 않는 이유: 이것은 게이트가 아니라 계측기다. 0건이라는 *측정 결과*와
  측정을 못 했다는 *실패*는 반드시 구별돼야 한다(측정 실패가 "이상 없음"으로 위장 금지).
"""

from __future__ import annotations

import argparse
import collections
import json
import pathlib
import re
import sys

DEFAULT_CORPUS = pathlib.Path("data/corpus")

# ── 축 A: 지시문 꼬리 — 역할로 뽑는다(어휘를 가정하지 않는다) ──────────────
INSTRUCTION_TAIL = re.compile(
    r"([^\s,.]{0,14})(?:으?로|하여|해서)?\s*"
    r"(나타내|구하|쓰|답하|표현하|계산하|정리하|간단히)[시여]?[오라기]"
)

# ── 축 B: 형태 요구 어휘 ─────────────────────────────────────────────────
# **답 자체의 표기 형태**를 지시하는 것만 넣는다. 풀이 *방법* 지시는 제외다.
#
# 판별 기준: 그 지시를 어겨도 값이 같을 수 있는가?
#   "기약분수로 나타내시오" → 2/72도 값은 같다 → **형태 요구**(여기 포함)
#   "인수분해를 이용하여 근을 구하시오" → 답은 수 하나이고 표기 자유 → 방법 지시(제외)
#
# 각 패턴에 `negative`(오탐 차단)를 함께 둔다 — 변별력 없는 패턴은 측정이 아니라 위장이다.
FORM_PATTERNS: dict[str, tuple[str, str | None]] = {
    "reduced_fraction": (r"기약\s*분수", None),
    "factored": (r"인수\s*분해\s*(?:하[시여]|한\s*(?:꼴|형태))", r"이용하여|사용하여"),
    "expanded": (r"전개\s*하[시여]", None),
    "rationalized": (r"분모\s*를?\s*유리화", None),
    "simplified": (r"간단히\s*(?:하|나타내|정리)", None),
    "decimal_places": (r"소수\s*(?:점\s*아래\s*)?[0-9]+\s*째|반올림\s*하여", None),
    # `꼴` 단독은 쓰지 않는다 — "사다리꼴"·"원뿔꼴"에 걸린다(1차 시도 오탐 24건 전건).
    "specified_form": (r"[0-9a-zA-Z가-힣)\]]\s*꼴로\s*(?:나타내|쓰|표현)", r"사다리꼴|마름모꼴"),
}


def _iter_problems(corpus: pathlib.Path, errors: list[str]):
    """문항 뱅크 전수 순회 — 파일별로 즉시 yield(마지막에 모아 저장하지 않는다).

    파싱 실패는 `errors`에 누적된다. 호출자가 그것을 보고 **측정 실패로 판정**해야 한다 —
    경고만 찍고 넘어가면 불완전한 코퍼스로 낸 수치가 완전한 것처럼 읽힌다.
    """
    banks = sorted(corpus.glob("problem_bank_*/problems.jsonl"))
    if not banks:
        raise FileNotFoundError(f"문항 뱅크를 찾지 못했다: {corpus}/problem_bank_*/problems.jsonl")
    for path in banks:
        bank = path.parent.name
        for lineno, line in enumerate(path.open(encoding="utf-8"), start=1):
            line = line.strip()
            if not line:
                continue
            try:
                yield bank, lineno, json.loads(line)
            except json.JSONDecodeError as exc:
                # 삼키지 않는다 — 실패 위치를 남기고 **호출자에게 올린다**.
                # 계속 진행하면 부분 코퍼스로 "0건"을 내고, 그 0건이 어휘 게이트를 통과시킨다
                # (측정 실패가 측정 결과로 위장 — 2026-09-01 리뷰 지적).
                errors.append(f"{path}:{lineno} JSON 파싱 실패: {exc}")
                print(f"[scan][error] {errors[-1]}", file=sys.stderr)


def scan(corpus: pathlib.Path) -> dict:
    total = 0
    parse_errors: list[str] = []
    per_bank_total: collections.Counter[str] = collections.Counter()
    hits: dict[str, list[dict]] = {name: [] for name in FORM_PATTERNS}
    tails: collections.Counter[str] = collections.Counter()

    compiled = {
        name: (re.compile(pos), re.compile(neg) if neg else None)
        for name, (pos, neg) in FORM_PATTERNS.items()
    }

    for bank, _lineno, doc in _iter_problems(corpus, parse_errors):
        total += 1
        per_bank_total[bank] += 1
        question = doc.get("question_text") or ""

        for match in INSTRUCTION_TAIL.finditer(question):
            tails[f"{match.group(1)}|{match.group(2)}"] += 1

        for name, (positive, negative) in compiled.items():
            found = positive.search(question)
            if not found:
                continue
            if negative and negative.search(question):
                continue  # 오탐 차단 — 방법 지시·동음 어휘
            hits[name].append(
                {
                    "bank": bank,
                    "slug": doc.get("slug"),
                    "answer_format": doc.get("answer_format"),
                    "question_format": doc.get("question_format"),
                    "answer": doc.get("answer"),
                    "question_text": question[:160],
                }
            )

    return {
        "total_problems": total,
        "per_bank_total": dict(per_bank_total),
        "form_hits": {name: rows for name, rows in hits.items()},
        "instruction_tails": dict(tails.most_common()),
        # 비어 있지 않으면 이 측정치는 **불완전**하다 — 소비자가 그것을 알아야 한다.
        "parse_errors": parse_errors,
    }


def render(result: dict, *, show_tails: bool) -> str:
    total = result["total_problems"]
    lines = ["# 답 형태 요구 문항 실측 (EOS-28 acceptance ①)", ""]
    lines.append(f"대상 문항 **{total}건** — 뱅크 {len(result['per_bank_total'])}종")
    lines.append("")
    lines.append("| 형태 어휘 | 적중 | 비율 | 뱅크 |")
    lines.append("|---|---:|---:|---|")
    attested = 0
    for name, rows in result["form_hits"].items():
        banks = ", ".join(sorted({r["bank"] for r in rows})) or "—"
        pct = f"{len(rows) / total * 100:.2f}%" if total else "—"
        lines.append(f"| `{name}` | {len(rows)} | {pct} | {banks} |")
        if rows:
            attested += 1
    lines.append("")
    lines.append(f"**실증된 형태 어휘: {attested}종**")
    if result["parse_errors"]:
        lines.append("")
        lines.append(f"⚠️ **측정 실패 {len(result['parse_errors'])}건** — 위 수치는 불완전하다.")
        for err in result["parse_errors"]:
            lines.append(f"- {err}")
    if attested == 0:
        lines.append("")
        lines.append("→ 0건이다. EOS-28은 **유보 전환**(측정 없는 도입 없음).")
    if show_tails:
        lines.append("")
        lines.append("## 지시문 꼬리 전수 (축 A — 데이터가 어휘를 말한다)")
        lines.append("")
        for key, count in result["instruction_tails"].items():
            lines.append(f"- `{key}` — {count}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=pathlib.Path, default=DEFAULT_CORPUS)
    parser.add_argument("--json", type=pathlib.Path, default=None)
    parser.add_argument("--tails", action="store_true", help="지시문 꼬리 전수를 함께 출력")
    args = parser.parse_args(argv)

    try:
        result = scan(args.corpus)
    except (OSError, FileNotFoundError) as exc:
        # 측정 실패는 "0건"이 아니다 — 여기서만 exit 1을 낸다.
        print(f"측정 실패({type(exc).__name__}): {exc}", file=sys.stderr)
        return 1

    print(render(result, show_tails=args.tails))
    if result["parse_errors"]:
        # docstring 계약 이행 — 파싱 불가는 "0건"이 아니라 측정 실패다.
        print(
            f"측정 실패: 코퍼스 {len(result['parse_errors'])}행을 읽지 못했다 — "
            "이 수치로 어휘를 판정하면 안 된다.",
            file=sys.stderr,
        )
        return 1
    if args.json:
        args.json.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n(JSON: {args.json})", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
