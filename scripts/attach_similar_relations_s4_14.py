#!/usr/bin/env python3
"""S4-14 일회성 반영 — 커밋된 problem_bank_generated_v0에 "유사" 관계(problem_relation 재료) 부여.

**왜 `problem_corpus_batch.py`를 재실행하지 않는가**: 스켈레톤 배치는 "재현 가능"이 설계
목표지만, 실측 결과 현재 기본 인자로 신선 재실행하면 quad 문제군(short·mc·sqrt·sqrt_mc,
185건)의 내용이 **커밋된 파일과 달라진다**(선행 커밋 378e1757의 계통 오귀속 교정이 생성기
코드에는 반영됐으나 코퍼스 파일 자체는 전면 재생성 대신 부분 패치로 반영된 이력 때문으로
추정 — 재현성 자체가 이미 어긋나 있다). 전면 재생성은 621건의 의도치 않은 내용 드리프트를
낳을 위험이 있어 이 태스크 범위를 벗어난다.

대신 이 스크립트는 **커밋된 파일을 그대로 로드 → 관계만 부여 → 그대로 재기록**한다
(`load_problem_bank_records` → `_attach_similar_relations` → `_tagged_record`/`_record_to_json`
왕복이 관계 필드 외 0 diff임을 사전 실측 확인 — 시그니처 태거는 기존 태깅 레코드에 멱등이라
재태깅 무연산). 결정론·멱등: 재실행해도 관계 계산은 순수 함수라 같은 산출.

사용: python3 scripts/attach_similar_relations_s4_14.py [--check]
  --check: 쓰지 않고 관계 통계만 출력(드라이런).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO / "src" / "backend"))

from whymath_backend.harness.problem_corpus_batch import (  # noqa: E402
    JsonlCorpusSink,
    _attach_similar_relations,
)
from whymath_backend.l1.problem_bank.populate import load_problem_bank_records  # noqa: E402

_GENERATED = _REPO / "data" / "corpus" / "problem_bank_generated_v0" / "problems.jsonl"


def run(*, check: bool) -> int:
    records = load_problem_bank_records(_GENERATED)
    attached = _attach_similar_relations(records)
    total_relations = sum(len(r.relations) for r in attached)
    with_relations = sum(1 for r in attached if r.relations)
    print(
        f"레코드 {len(attached)}건 중 관계 보유 {with_relations}건 · "
        f"관계 인스턴스 합계 {total_relations}건"
    )
    if check:
        print("[--check] 드라이런 — 파일 미수정")
        return 0

    sink = JsonlCorpusSink()
    sink.set_records(attached)
    written = sink.write(_GENERATED)
    print(f"기록: {_GENERATED}({written}건)")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="S4-14 유사 관계 일회성 반영(결정론·멱등).")
    parser.add_argument("--check", action="store_true", help="쓰지 않고 통계만 출력(드라이런).")
    args = parser.parse_args(argv)
    return run(check=args.check)


if __name__ == "__main__":
    raise SystemExit(main())
