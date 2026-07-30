"""S4-14 일회성 소급 백필 — rephrased_v0(429건)에 결측 변형 계보(problem_relation 재료)를 부여.

**왜 소급이 필요한가**: `problem_corpus_rephrase.run_corpus_rephrase`는 이 태스크 이전엔
발문이 실제로 바뀐 레코드에도 원본과 **같은 slug/problem_id를 보존**했다(question_text만
교체). `problem_relation`은 `parent != related`를 스키마로 강제하므로 그 상태로는 애초에
변형 관계를 만들 수 없었다(D8 dead seat — `docs/architecture/problem_bank_gap_review.md` §3).
이제 `run_corpus_rephrase`는 발문이 바뀐 레코드에 한해 신규 slug/problem_id + `변형` 관계
태깅을 발급하지만(코드 변경은 *미래* 실행분에만 적용), 이미 커밋된 429건은 그 규칙 적용
이전 산출물이라 이 스크립트가 **같은 규칙을 소급 적용**한다.

**조인 방식**: `scripts/reconcile_rephrased_corpus_s2_08.py` 선례와 동형 — slug 조인 우선,
실패 시 수정 불변 수학키(`unit_codes, verify.conditions, verify.answer_selection, answer`)로
폴백(발문 조사 수정 등으로 slug이 소스와 어긋난 429건 중 일부 대응). 매치 후
`canonical_signature(conditions, answer_selection)`로 양측을 교차검증한다 — 수학키가 우연히
같은 구조를 가리키는 조인 오류를 하드 실패로 잡는다(조용한 오조인 금지).

**신규 identity 발급 규칙**(`problem_corpus_rephrase.py`와 동일 함수 재사용 — 공식 이원화 금지):
발문이 소스와 **다른** 레코드만 `rephrased_slug`/`_rephrased_problem_id`로 새 slug/problem_id를
받고 `relations=[{"parent_slug": ..., "relation_type": "변형", "similarity_score": 0.95}]`를
얻는다. 발문이 소스와 **같은**(원래 rephrase 시도가 fail-closed로 원문 유지된) 레코드는 이미
소스와 동일 정체성이므로 그대로 둔다 — 대신 소스의 `relations` 필드(있다면 스켈레톤 "유사"
태깅)를 그대로 복사해 필드 균일성을 유지한다(키 집합 정합 — `test_corpus_quality.py` 봉인).

결정론·멱등: 같은 입력이면 같은 출력(슬러그는 내용 해시라 재실행 무관 안정). 미매칭·시그니처
불일치 레코드는 전량 모아 즉시 실패(fail-closed — 조용한 드롭 금지).

사용: python3 -m whymath_backend.harness.rephrase_lineage_backfill [--check]
  --check: 쓰지 않고 변경 요약만 출력(드라이런).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from whymath_backend.harness.problem_corpus_rephrase import (
    _rephrased_problem_id,
    rephrased_slug,
)
from whymath_backend.l3.equivalent.canonicalize import canonical_signature

__all__ = ["BackfillReport", "backfill_rephrase_lineage", "main"]


def _repo_root() -> Path:
    """`__file__` = <repo>/src/backend/whymath_backend/harness/rephrase_lineage_backfill.py.

    parents[4]가 repo 루트(harness→whymath_backend→backend→src→repo — `problem_corpus_batch.
    _default_out_path` 실측과 동형).
    """
    return Path(__file__).resolve().parents[4]


def _default_generated_path() -> Path:
    return _repo_root() / "data" / "corpus" / "problem_bank_generated_v0" / "problems.jsonl"


def _default_rephrased_path() -> Path:
    return _repo_root() / "data" / "corpus" / "problem_bank_rephrased_v0" / "problems.jsonl"


def _math_key(record: dict[str, Any]) -> tuple[Any, ...]:
    """수정 불변 수학키 — `test_corpus_quality._math_key`/S2-08 재조정 스크립트와 동형."""
    verify = record["verify"]
    return (
        tuple(record["unit_codes"]),
        verify["conditions"],
        verify["answer_selection"],
        str(record["answer"]),
    )


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8")
    return [json.loads(line) for line in text.splitlines() if line.strip()]


class BackfillReport:
    """백필 결과 요약 — 매치·변형·미변·미매칭(fail-closed 근거) 집계."""

    def __init__(
        self,
        *,
        total: int,
        rephrased_new_identity: int,
        unchanged_kept_identity: int,
        unmatched: list[str],
        signature_mismatches: list[str],
    ) -> None:
        self.total = total
        self.rephrased_new_identity = rephrased_new_identity
        self.unchanged_kept_identity = unchanged_kept_identity
        self.unmatched = unmatched
        self.signature_mismatches = signature_mismatches

    def to_json(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "rephrased_new_identity": self.rephrased_new_identity,
            "unchanged_kept_identity": self.unchanged_kept_identity,
            "unmatched": self.unmatched,
            "signature_mismatches": self.signature_mismatches,
        }


def backfill_rephrase_lineage(
    *,
    generated_path: Path | None = None,
    rephrased_path: Path | None = None,
    check: bool = False,
) -> BackfillReport:
    """rephrased_v0 전 레코드에 소급 변형 계보를 부여(성공 시 in-place 재기록). 미매칭 시 예외.

    `check=True`면 파일을 쓰지 않고 리포트만 계산(드라이런). 미매칭·signature 불일치가 있으면
    `ValueError`(리포트에 상세 실려 있으므로 예외 메시지는 건수만 — 호출자가 리포트 전량 확인).
    """
    generated_path = generated_path or _default_generated_path()
    rephrased_path = rephrased_path or _default_rephrased_path()

    generated = _load_jsonl(generated_path)
    by_slug: dict[str, dict[str, Any]] = {g["slug"]: g for g in generated}
    by_key: dict[tuple[Any, ...], dict[str, Any]] = {_math_key(g): g for g in generated}
    if len(by_key) != len(generated):
        raise ValueError(f"치명: 생성 코퍼스 수학키 충돌 — 조인 불가({generated_path})")

    rephrased = _load_jsonl(rephrased_path)
    unmatched: list[str] = []
    signature_mismatches: list[str] = []
    new_identity = 0
    kept_identity = 0
    out_records: list[dict[str, Any]] = []

    for record in rephrased:
        slug = record.get("slug")
        source = (by_slug.get(slug) if isinstance(slug, str) else None) or by_key.get(
            _math_key(record)
        )
        if source is None:
            unmatched.append(str(slug))
            out_records.append(record)
            continue

        src_verify = source["verify"]
        rec_verify = record["verify"]
        src_sig = canonical_signature(src_verify["conditions"], src_verify["answer_selection"])
        rec_sig = canonical_signature(rec_verify["conditions"], rec_verify["answer_selection"])
        if src_sig is not None and rec_sig is not None and src_sig != rec_sig:
            signature_mismatches.append(str(slug))
            out_records.append(record)
            continue

        updated = dict(record)
        if record["question_text"] != source["question_text"]:
            # 발문 상이 — 실제 rephrase 성공 → 신규 identity + 변형 관계(코드 규칙과 동일 공식).
            parent_slug = source["slug"]
            new_slug = rephrased_slug(parent_slug, str(record["question_text"]))
            updated["slug"] = new_slug
            updated["problem_id"] = str(_rephrased_problem_id(new_slug))
            updated["relations"] = [
                {
                    "parent_slug": parent_slug,
                    "relation_type": "변형",
                    "similarity_score": 0.95,
                }
            ]
            new_identity += 1
        else:
            # 발문 동일 — 소스와 이미 같은 정체성(과거 fail-closed 유지분). 관계만 소스에서
            # 그대로 복사해 필드 균일성 유지(키 집합 정합 — 새 identity 발급 없음).
            updated["relations"] = source.get("relations", [])
            kept_identity += 1
        out_records.append(updated)

    if unmatched or signature_mismatches:
        raise ValueError(
            f"백필 실패 — 미매칭 {len(unmatched)}건({unmatched[:5]}), "
            f"signature 불일치 {len(signature_mismatches)}건({signature_mismatches[:5]})"
        )

    if not check:
        lines = [json.dumps(r, ensure_ascii=False) for r in out_records]
        rephrased_path.write_text("\n".join(lines) + "\n" if lines else "", encoding="utf-8")

    return BackfillReport(
        total=len(rephrased),
        rephrased_new_identity=new_identity,
        unchanged_kept_identity=kept_identity,
        unmatched=unmatched,
        signature_mismatches=signature_mismatches,
    )


def main(argv: list[str] | None = None) -> int:
    """CLI 엔트리 — 백필 실행 후 리포트를 JSON으로 stdout에 낸다. 실패 시 exit 1(fail-closed)."""
    parser = argparse.ArgumentParser(
        prog="python -m whymath_backend.harness.rephrase_lineage_backfill",
        description="rephrased_v0(429건) 소급 변형 계보 백필(problem_relation 재료·S4-14).",
    )
    parser.add_argument(
        "--check", action="store_true", help="쓰지 않고 변경 요약만 출력(드라이런)."
    )
    args = parser.parse_args(argv)

    try:
        report = backfill_rephrase_lineage(check=args.check)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    json.dump(report.to_json(), sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":  # pragma: no cover — 모듈 실행 진입점
    raise SystemExit(main())
