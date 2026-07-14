#!/usr/bin/env python3
"""S2-08 일회성 결정론 재조정 — rephrased 코퍼스에 generated 재생성분의 수정을 전파한다.

**왜 재생성이 아니라 재조정인가**: rephrased 코퍼스(`problem_bank_rephrased_v0`)는 `rephrase.py`가
*발문(question_text)만* LLM으로 다시 쓰고 나머지 필드(해설·난이도·distractor_map·수치·정답)는
generated에서 **그대로 복사**해 만든 산출물이다. LLM 유도라 이 컨테이너에서 재생성이 불가능하다.
그런데 S2-08 결함 수정(조사 받침·난이도 앵커 재보정·op-code 방향 중립화·표본 30 단위원 용어)은
바로 그 *복사된 필드*(answer_explanation·difficulty_overall·distractor_map)에 들어 있다.

**조인 방식(정직 명시)**: generated 재생성분에서 각 rephrased 레코드를 찾아 위 3필드만 덮어쓴다.
발문 조사 수정으로 content-hash slug이 바뀐 레코드(72건 중 rephrased에 실린 54건)는 slug 조인이
깨지므로, **수정 불변 수학키**로 조인한다:
    key = (unit_codes, verify.conditions, verify.answer_selection, answer)
이 키는 조사·난이도·op-code 수정에 전부 불변이고 generated 620건에서 유일하다(검증). slug이
살아 있으면 slug 우선, 아니면 수학키로 폴백한다. **발문·slug·problem_id는 LLM 원본을 보존**한다
(rephrase의 계약 — 수치만 코드 소유, 발문은 LLM).

결정론·멱등: 같은 입력이면 같은 출력. JSON 직렬화는 원본과 바이트 동일(`ensure_ascii=False`·기본
separators·키 순서 보존). 미매칭 잔여가 있으면 즉시 실패(fail-closed·조용한 누락 금지).

사용:  python3 scripts/reconcile_rephrased_corpus_s2_08.py [--check]
  --check: 쓰지 않고 변경 요약만 출력(드라이런).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
_GENERATED = _REPO / "data" / "corpus" / "problem_bank_generated_v0" / "problems.jsonl"
_REPHRASED = _REPO / "data" / "corpus" / "problem_bank_rephrased_v0" / "problems.jsonl"

# generated 재생성분에서 rephrased로 전파할 필드(rephrase가 generated에서 복사하던 것과 동일 집합).
_COPY_FIELDS = ("answer_explanation", "difficulty_overall", "distractor_map")

# verify 블록 내부 전파 필드(S2-02) — rephrase는 발문만 바꾸고 conditions·answer가 동일하므로
# 생성기의 검증 단계 체인(solution_steps)도 그대로 유효하다(수학키 조인 대상과 같은 근거).
_COPY_VERIFY_FIELDS = ("solution_steps",)


def _math_key(record: dict) -> tuple:
    """수정 불변 수학키 — 조사·난이도·op-code 수정에 불변이고 generated에서 유일."""
    verify = record["verify"]
    return (
        tuple(record["unit_codes"]),
        verify["conditions"],
        verify["answer_selection"],
        str(record["answer"]),
    )


def _load(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def reconcile(*, check: bool) -> int:
    """rephrased에 generated 수정 3필드를 재적용 — 미매칭 시 비정상 종료(1)."""
    generated = _load(_GENERATED)
    by_slug: dict[str, dict] = {g["slug"]: g for g in generated}
    by_key: dict[tuple, dict] = {_math_key(g): g for g in generated}
    if len(by_key) != len(generated):
        print("치명: generated 수학키 충돌 — 조인 불가", file=sys.stderr)
        return 1

    rephrased = _load(_REPHRASED)
    changed = 0
    field_changes: dict[str, int] = {f: 0 for f in (*_COPY_FIELDS, *_COPY_VERIFY_FIELDS)}
    unmatched: list[str] = []
    out_lines: list[str] = []

    for record in rephrased:
        source = by_slug.get(record["slug"]) or by_key.get(_math_key(record))
        if source is None:
            unmatched.append(record["slug"])
            out_lines.append(json.dumps(record, ensure_ascii=False))
            continue
        for field in _COPY_FIELDS:
            new_value = source.get(field)
            old_value = record.get(field)
            if new_value != old_value:
                field_changes[field] += 1
                if new_value is None:
                    record.pop(field, None)
                else:
                    record[field] = new_value
        for field in _COPY_VERIFY_FIELDS:
            new_value = (source.get("verify") or {}).get(field)
            old_value = (record.get("verify") or {}).get(field)
            if new_value != old_value:
                field_changes[field] += 1
                if new_value is None:
                    record.setdefault("verify", {}).pop(field, None)
                else:
                    record.setdefault("verify", {})[field] = new_value
        if record != json.loads(json.dumps(record, ensure_ascii=False)):  # pragma: no cover
            pass  # 방어(직렬화 안정성) — 실질 무연산.
        out_lines.append(json.dumps(record, ensure_ascii=False))
        changed += 1  # (조인 성공 레코드 수 — 실제 값 변경은 field_changes로 집계)

    if unmatched:
        print(
            f"치명: rephrased {len(unmatched)}건 미매칭(조인 실패) — {unmatched[:5]}",
            file=sys.stderr,
        )
        return 1

    print(f"조인 성공 {changed}/{len(rephrased)}건 · 필드 변경 {field_changes}")
    if check:
        print("[--check] 드라이런 — 파일 미수정")
        return 0

    _REPHRASED.write_text("\n".join(out_lines) + "\n", encoding="utf-8")
    print(f"기록: {_REPHRASED}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="S2-08 rephrased 코퍼스 재조정(결정론·멱등).")
    parser.add_argument(
        "--check", action="store_true", help="쓰지 않고 변경 요약만 출력(드라이런)."
    )
    args = parser.parse_args(argv)
    return reconcile(check=args.check)


if __name__ == "__main__":
    raise SystemExit(main())
