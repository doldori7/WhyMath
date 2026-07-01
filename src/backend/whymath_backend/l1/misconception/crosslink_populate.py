"""오개념 crosswalk 승인 매핑 → backend 적재 CLI.

모듈: `whymath_backend.l1.misconception.crosslink_populate`.

사람 검수·승인된 crosswalk 매핑(`data/corpus/misconception_crosslink_v1/crosslinks.json`·Collection
JSON·`{"crosslinks":[{kebab_id, mis_id, link_type, confidence, method, note}, ...]}`)을 backend 영속
`misconception_crosslink` 테이블에 멱등 upsert한다. `l1/misconception/populate`(M-id 카탈로그 적재
CLI)의 *crosswalk* 짝이며 같은 CLI 골격을 따른다(argparse·`main(argv)->int`·파일 부재 `return 2`·
stdout 행수 보고).

**매핑 = 사람 검수 산출물**(math_dsl_remediation_design.md §1·CLAUDE.md 우선순위 #1·#3): 틀린 매핑은
오도된 학부모/학생 리포트로 이어지므로, 이 CLI는 *검수·승인된* Collection만 적재한다(자동 후보
`crosslink_candidates.py` 출력의 top key는 "candidates"라 이 로더가 직접 못 읽음 — 자동 적재 차단).

적재 로직 0(얇은 래퍼): `load_crosslinks`(crosslink_loader)가 Collection 파싱·멱등 upsert를 담당.
본 CLI는 경로 결선·실행·보고만 한다.

사용:
    python -m whymath_backend.l1.misconception.crosslink_populate \\
        --crosslinks data/corpus/misconception_crosslink_v1/crosslinks.json
"""

from __future__ import annotations

import argparse
from pathlib import Path

from whymath_backend.l1.misconception.crosslink_loader import load_crosslinks

# 승인 매핑 기본 경로(검수 산출 관례 — misconception_crosslink_v1).
_DEFAULT_CROSSLINKS = Path("data/corpus/misconception_crosslink_v1/crosslinks.json")


def main(argv: list[str] | None = None) -> int:
    """crosswalk 승인 Collection JSON을 `misconception_crosslink`에 멱등 적재·행 수 보고(CLI 본체).

    반환은 프로세스 종료 코드(0=성공·2=입력 파일 부재). 적재 로직은 `load_crosslinks`가 담당하며 본
    함수는 경로 결선·실행·stdout 보고만 한다(조용한 무동작 금지 — 부재 시 명확히 보고).
    """
    parser = argparse.ArgumentParser(
        prog="whymath-crosslink-populate",
        description=(
            "오개념 crosswalk 승인 매핑(Collection JSON) → backend misconception_crosslink "
            "멱등 적재((kebab_id, mis_id, link_type) 트리플 충돌 upsert)."
        ),
    )
    parser.add_argument(
        "--crosslinks",
        type=Path,
        default=_DEFAULT_CROSSLINKS,
        help=f"crosswalk 승인 Collection JSON 경로(기본 {_DEFAULT_CROSSLINKS}).",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="상세 출력(현재는 표준 보고만 — 호환 자리표시).",
    )
    args = parser.parse_args(argv)

    path: Path = args.crosslinks
    if not path.exists():
        print(f"crosswalk 승인 Collection 없음: {path} — 검수 후 승인분 JSON을 먼저 공급하세요.")
        return 2

    count = load_crosslinks(None, path)
    print(f"crosswalk 적재 완료: {count}건 (src={path}).")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI 진입
    raise SystemExit(main())
