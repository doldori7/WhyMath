"""교수법 팩 YAML → backend 적재 CLI — `whymath_backend.l1.pedagogy.populate`.

`data/corpus/pedagogy_packs_v1/*.yaml`(7 지식유형 팩)을 backend 영속 `pedagogy_pack` 테이블에
멱등 적재한다. `l1/standards/populate`(성취기준)·`l1/misconception`(오개념) 적재 CLI의 *교수법 팩*
짝이며 같은 CLI 골격을 따른다(argparse·`main(argv)->int`·디렉터리 부재 `return 2`·stdout 행수
보고). 교수법 팩은 임베딩·pgvector와 무관(순수 RDB sync 적재)하므로 vector_store 게이트가 없다.

적재 로직 0(얇은 래퍼): `load_packs`(pack_loader)가 디렉터리 glob·YAML 파싱·schema 검증(형식·
교수학 불변식)·멱등 upsert를 전부 담당한다. 본 CLI는 경로 결선·실행·보고만 한다.

전제: 마이그레이션 head 적용된 실 PG 도달(`pedagogy_pack` + `knowledge_type` native enum). 자격은
env(시크릿 0).

사용:
    python -m whymath_backend.l1.pedagogy.populate \\
        --packs-dir data/corpus/pedagogy_packs_v1
"""

from __future__ import annotations

import argparse
from pathlib import Path

from whymath_backend.l1.pedagogy.pack_loader import load_packs

# 팩 코퍼스 기본 경로(팩당 1 YAML — 7 지식유형).
_DEFAULT_PACKS_DIR = Path("data/corpus/pedagogy_packs_v1")


def main(argv: list[str] | None = None) -> int:
    """교수법 팩 YAML 디렉터리를 backend `pedagogy_pack`에 멱등 적재하고 행 수를 보고(CLI 본체).

    반환은 프로세스 종료 코드(0=성공·2=입력 디렉터리 부재). 적재 로직은 `load_packs`가 담당하며
    본 함수는 경로 결선·실행·stdout 보고만 한다(조용한 무동작 금지 — 부재 시 명확히 보고).
    """
    parser = argparse.ArgumentParser(
        prog="whymath-pedagogy-populate",
        description=(
            "교수법 팩 YAML(팩당 1 파일) → backend pedagogy_pack 멱등 적재"
            "(k_type PK 충돌 upsert)."
        ),
    )
    parser.add_argument(
        "--packs-dir",
        type=Path,
        default=_DEFAULT_PACKS_DIR,
        help=f"교수법 팩 YAML 디렉터리 경로(기본 {_DEFAULT_PACKS_DIR}).",
    )
    args = parser.parse_args(argv)

    packs_dir: Path = args.packs_dir
    if not packs_dir.exists():
        print(f"교수법 팩 디렉터리 없음: {packs_dir} — 코퍼스가 있는지 확인하세요.")
        return 2

    count = load_packs(None, packs_dir)
    print(f"교수법 팩 적재 완료: {count}건 (packs_dir={packs_dir}).")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI 진입
    raise SystemExit(main())
