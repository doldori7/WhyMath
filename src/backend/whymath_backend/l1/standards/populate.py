"""성취기준 코퍼스 → backend 적재 CLI — `whymath_backend.l1.standards.populate`.

#288이 커밋한 코퍼스(`data/corpus/standards_v1/{standards.json·concept_standard_links.json}`·
Collection JSON)를 backend 영속 두 테이블(`achievement_standard`·`concept_standard_link`)에 멱등
적재한다. `l1/concept_graph/populate`(개념 임베딩+노드+엣지)의 성취기준 짝이며 같은 CLI 골격을
따른다(argparse·`main(argv)->int`·파일 부재 `return 2`·stdout 행수 보고). 다만 성취기준은
임베딩·pgvector와 무관(순수 RDB sync 적재)하므로 vector_store 게이트가 없다.

적재 로직 0(얇은 래퍼): `load_standards`/`load_links`(standard_loader)가 Collection 파싱·멱등
upsert·concept 해석(`concept_src_id`→`concept.source_id`→`code`)·orphan skip을 전부 담당한다.
본 CLI는 경로 결선·실행·보고만 한다.

전제: 마이그레이션 head 적용된 실 PG 도달(`achievement_standard`·`concept_standard_link` + 링크
해석용 `concept`). 자격은 env(시크릿 0). 링크 적재는 개념이 먼저 적재돼 있어야 `concept_src_id`가
해석된다(`l1.concept_graph.populate` 선행 — 아니면 전건 개념 orphan skip).

사용:
    python -m whymath_backend.l1.standards.populate \\
        --standards data/corpus/standards_v1/standards.json \\
        --links data/corpus/standards_v1/concept_standard_links.json
"""

from __future__ import annotations

import argparse
from pathlib import Path

from whymath_backend.l1.standards.standard_loader import load_links, load_standards

# 코퍼스 기본 경로(#288 `whymath-ncic extract --output-dir data/corpus/standards_v1` 관례).
_DEFAULT_DIR = Path("data/corpus/standards_v1")
_DEFAULT_STANDARDS = _DEFAULT_DIR / "standards.json"
_DEFAULT_LINKS = _DEFAULT_DIR / "concept_standard_links.json"


def main(argv: list[str] | None = None) -> int:
    """성취기준·연결 Collection JSON을 backend 두 테이블에 멱등 적재하고 행 수를 보고(CLI 본체).

    반환은 프로세스 종료 코드(0=성공·2=입력 파일 부재). 적재 로직은 `load_standards`/`load_links`가
    담당하며 본 함수는 경로 결선·실행·stdout 보고만 한다(조용한 무동작 금지 — 부재 시 명확히 보고).
    """
    parser = argparse.ArgumentParser(
        prog="whymath-standard-populate",
        description=(
            "성취기준 코퍼스(Collection JSON) → backend achievement_standard·"
            "concept_standard_link 멱등 적재(norm_id PK·의미키 충돌 upsert)."
        ),
    )
    parser.add_argument(
        "--standards",
        type=Path,
        default=_DEFAULT_STANDARDS,
        help=f"성취기준 Collection JSON 경로(기본 {_DEFAULT_STANDARDS}).",
    )
    parser.add_argument(
        "--links",
        type=Path,
        default=_DEFAULT_LINKS,
        help=f"개념↔성취기준 연결 Collection JSON 경로(기본 {_DEFAULT_LINKS}).",
    )
    parser.add_argument(
        "--skip-links",
        action="store_true",
        help="성취기준만 적재(연결 적재 생략).",
    )
    args = parser.parse_args(argv)

    standards_path: Path = args.standards
    if not standards_path.exists():
        print(
            f"성취기준 Collection 없음: {standards_path} — "
            "`whymath-ncic extract`로 먼저 생성하세요."
        )
        return 2

    std_count = load_standards(None, standards_path)

    if args.skip_links:
        print(f"성취기준 적재 완료: {std_count}건 (연결 skip·std={standards_path}).")
        return 0

    links_path: Path = args.links
    if not links_path.exists():
        print(f"연결 Collection 없음: {links_path} — `whymath-ncic extract`로 먼저 생성하세요.")
        return 2

    link_count = load_links(None, links_path)
    print(
        f"성취기준 적재 완료: {std_count}건·연결 적재 완료: {link_count}건 "
        f"(std={standards_path}, links={links_path}). "
        "연결이 0이면 개념 미적재(l1.concept_graph.populate 선행·전건 개념 orphan)."
    )
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI 진입
    raise SystemExit(main())
