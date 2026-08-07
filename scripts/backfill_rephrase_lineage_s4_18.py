#!/usr/bin/env python3
"""S4-18 결정론 계보 동기화 — rephrase 변형에 identity_id/problem_relation을 부여한다.

**소급(429건) + 향후(재실행 가능)** 양쪽에 쓰는 같은 스크립트다 — `problem_corpus_rephrase.py`는
의도적으로 slug/problem_id/identity_id를 건드리지 않는다(발문만 다양화하는 것이 그 함수의
계약이자, `--in` 소스 코퍼스는 이 파이프라인 전체에서 읽기 전용이라는 기존 관례 — S2-08
`reconcile_rephrased_corpus_s2_08.py`와 동형). 그래서 Phaiakes9에서 새 rephrase 배치를 돌린
뒤에는 매번 이 스크립트를 재실행해 계보를 동기화한다(멱등이라 몇 번을 돌려도 안전 — 이미
처리된 레코드는 스킵하고 신규 레코드만 처리).

배경: rephrase는 원본 Problem을 그대로 복사하며 question_text만 바꾸므로(`l3/equivalent/
rephrase.py` 계약), rephrased_v0 429건 중 392건(91%)이 원본과 *동일* slug·problem_id를
갖는다(실측 확인) — populate.py의 slug ON CONFLICT upsert가 이 둘을 *같은 DB 행*으로
병합해, problem_relation(2행 관계)을 맺을 대상 행 자체가 없다(schema._no_self_relation이
구조적으로 막음). 나머지 37건(8.6%)은 이미 별개 slug/problem_id를 갖지만 계보(relation)가
없다.

Kiki 결정(2026-07-29, identity_id/Canonical 분리): problem_id는 개체마다 절대 불변,
identity_id(신규 nullable UUID)로만 "같은 문제의 다른 표현" 계열을 묶고, problem_relation은
개별 변환 이력만 기록한다.

이 스크립트가 매 실행마다 미처리(identity_id 없는) 레코드 전부에 하는 일(최초 실행=429건):
  ① parent 판정 — slug가 원본(generated_v0)과 같으면 그 slug 자체가 parent. 다르면(재실행 시
     이미 재슬러그된 레코드 포함) 수정 불변 수학키(unit_codes·verify.conditions·
     answer_selection/aggregate/kind·answer)로 원본과 조인(`scripts/
     reconcile_rephrased_corpus_s2_08.py`와 동일 키·전건 유일성 실측 검증됨 — 620건 키 충돌 0).
  ② slug 충돌 해소(parent와 slug가 같은 경우만) — rephrase 레코드에 신규 slug
     (`f"{parent_slug}-rephrased"`)·신규 problem_id를 결정론 파생(uuid5)해 부여한다. 원본
     (parent) 행은 손대지 않는다(slug·problem_id 불변 — 재적재 시 기존 DB 행과 계속 일치·
     PK churn 0).
  ③ identity_id 부여 — parent_slug로부터 결정론 파생(uuid5)해 rephrase 레코드와 원본 레코드
     양쪽에 같은 값을 쓴다.
  ④ problem_relation 계보 — rephrase 레코드에 `relations=[{parent_slug, "변형",
     similarity_score=1.0}]` authoring 키를 추가한다(populate.py가 적재 시 upsert).
     similarity_score=1.0은 추정이 아니라 실측 사실이다 — rephrase는 conditions·answer를
     그대로 복사하므로(발문만 재작성) 수치 내용이 완전히 동일하다.

멱등: identity_id가 이미 있는 레코드는 재처리하지 않는다(재실행 안전 — slug 재채번된 뒤
재실행해도 수학키로 같은 parent를 다시 찾되 이미 분리된 slug라 재채번을 반복하지 않는다).
신규 slug 충돌(기존 코퍼스에 이미 그 slug가 있음)·수학키 조인 실패·수학키 충돌은 즉시
실패한다(조용한 누락 금지).

사용:  python3 scripts/backfill_rephrase_lineage_s4_18.py [--check]
  --check: 쓰지 않고 변경 요약만 출력(드라이런).
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
_GENERATED = _REPO / "data" / "corpus" / "problem_bank_generated_v0" / "problems.jsonl"
_REPHRASED = _REPO / "data" / "corpus" / "problem_bank_rephrased_v0" / "problems.jsonl"

# uuid5 결정론 파생 namespace(고정 상수 — 한 번 생성해 고정, 재실행 시 항상 같은 값 보장).
_IDENTITY_NAMESPACE = uuid.UUID("83ed15d5-7ce4-469b-8166-1ac4e44a176f")
_VARIANT_PROBLEM_ID_NAMESPACE = uuid.UUID("caa1a2ae-7188-43fd-bd81-06d73f118879")

_RENAME_SUFFIX = "-rephrased"


# rephrase가 발문만 바꾸고 그대로 복사하는 필드(S2-08 정본 조인키와 동형) — 조사·난이도·
# op-code 수정에 불변이고 generated 전건에서 유일함을 실측 검증했다.
def _math_key(record: dict) -> tuple:
    verify = record.get("verify") or {}
    return (
        tuple(sorted(record.get("unit_codes") or [])),
        verify.get("conditions"),
        str(record.get("answer")),
        verify.get("answer_selection"),
        verify.get("answer_aggregate"),
        verify.get("answer_kind"),
    )


def _load(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def backfill(*, check: bool) -> int:
    """전량 429건 계보 백필 — 미해석/충돌 잔여가 있으면 즉시 실패(fail-closed)."""
    generated = _load(_GENERATED)
    rephrased = _load(_REPHRASED)

    by_slug: dict[str, dict] = {g["slug"]: g for g in generated}
    by_key: dict[tuple, list[dict]] = {}
    for g in generated:
        by_key.setdefault(_math_key(g), []).append(g)
    ambiguous = {k: [g["slug"] for g in v] for k, v in by_key.items() if len(v) > 1}
    if ambiguous:
        print(
            f"치명: generated 수학키 충돌 {len(ambiguous)}건 — 조인 불가: "
            f"{list(ambiguous.items())[:3]}",
            file=sys.stderr,
        )
        return 1

    all_slugs = {r["slug"] for r in generated} | {r["slug"] for r in rephrased}

    unmatched: list[str] = []
    already_done = 0
    renamed = 0
    identity_assigned = 0
    relations_added = 0

    for record in rephrased:
        if record.get("identity_id") is not None:
            already_done += 1
            continue

        parent = by_slug.get(record["slug"])
        if parent is None:
            candidates = by_key.get(_math_key(record), [])
            if len(candidates) != 1:
                unmatched.append(record["slug"])
                continue
            parent = candidates[0]

        parent_slug = parent["slug"]
        colliding = record["slug"] == parent_slug

        if colliding:
            new_slug = f"{parent_slug}{_RENAME_SUFFIX}"
            if new_slug in all_slugs:
                print(f"치명: 신규 slug 충돌: {new_slug}", file=sys.stderr)
                return 1
            all_slugs.add(new_slug)
            record["slug"] = new_slug
            record["problem_id"] = str(uuid.uuid5(_VARIANT_PROBLEM_ID_NAMESPACE, new_slug))
            renamed += 1

        identity = str(uuid.uuid5(_IDENTITY_NAMESPACE, parent_slug))
        record["identity_id"] = identity
        parent["identity_id"] = identity
        identity_assigned += 1

        record["relations"] = [
            {"parent_slug": parent_slug, "relation_type": "변형", "similarity_score": 1.0}
        ]
        relations_added += 1

    if unmatched:
        print(
            f"치명: rephrased {len(unmatched)}건 parent 미해석(조인 실패) — {unmatched[:5]}",
            file=sys.stderr,
        )
        return 1

    print(
        f"이미 처리됨(스킵) {already_done} · slug 재채번 {renamed} · "
        f"identity_id 부여 {identity_assigned} · relation 부여 {relations_added} "
        f"(전체 {len(rephrased)}건)"
    )
    if check:
        print("[--check] 드라이런 — 파일 미수정")
        return 0

    _REPHRASED.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rephrased) + "\n",
        encoding="utf-8",
    )
    _GENERATED.write_text(
        "\n".join(json.dumps(g, ensure_ascii=False) for g in generated) + "\n",
        encoding="utf-8",
    )
    print(f"기록: {_REPHRASED}\n기록: {_GENERATED}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="S4-18 rephrase 계보(identity_id·problem_relation) 소급 백필(결정론·멱등)."
    )
    parser.add_argument(
        "--check", action="store_true", help="쓰지 않고 변경 요약만 출력(드라이런)."
    )
    args = parser.parse_args(argv)
    return backfill(check=args.check)


if __name__ == "__main__":
    raise SystemExit(main())
