"""②진단문항·③소크라테스 코퍼스 → backend 적재 CLI — `whymath_backend.l1.atom_probe.populate`.

원자 백본 코퍼스(`data/corpus/atom_graph_v1/graph.json`)의 세부개념 원자 ②진단문항·③소크라테스를
backend 영속 `atom_probe` 테이블에 멱등 적재한다. `l1/concept_content/populate`(콘텐츠 적재 CLI)의
탐침 짝이며 같은 CLI 골격을 따른다(argparse·`main(argv)->int`·파일 부재 `return 2`·행수 보고).
탐침은 임베딩·pgvector와 무관(순수 RDB sync 적재)하므로 vector_store 게이트가 없다.

적재 로직 0(얇은 래퍼): `load_atom_probes_from_json`/`populate_atom_probes`(projection)이 파싱·멱등
upsert를 담당한다. 본 CLI는 경로 결선·실행·보고만 한다.

사용:
    python -m whymath_backend.l1.atom_probe.populate \\
        --graph data/corpus/atom_graph_v1/graph.json
"""

from __future__ import annotations

import argparse
from pathlib import Path

from whymath_backend.l1.atom_probe.projection import (
    load_atom_probes_from_json,
    populate_atom_probes,
)

# 코퍼스 기본 경로(Phase 1 산출 관례).
_DEFAULT_GRAPH = Path("data/corpus/atom_graph_v1/graph.json")


def main(argv: list[str] | None = None) -> int:
    """원자 ②진단문항·③소크라테스(graph.json)를 `atom_probe`에 멱등 적재하고 행 수를 보고(CLI 본체).

    반환은 프로세스 종료 코드(0=성공·2=입력 파일 부재). 적재 로직은 projection이 담당하며 본 함수는
    경로 결선·실행·stdout 보고만 한다(조용한 무동작 금지 — 부재 시 명확히 보고).
    """
    parser = argparse.ArgumentParser(
        prog="whymath-atom-probe-populate",
        description=(
            "원자 ②진단문항·③소크라테스 코퍼스(atom 백본 graph.json) → backend atom_probe "
            "멱등 적재(code PK 충돌 upsert)."
        ),
    )
    parser.add_argument(
        "--graph",
        type=Path,
        default=_DEFAULT_GRAPH,
        help=f"atom 백본 graph.json 경로(기본 {_DEFAULT_GRAPH}).",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="상세 출력(현재는 표준 보고만 — 호환 자리표시).",
    )
    args = parser.parse_args(argv)

    path: Path = args.graph
    if not path.exists():
        print(f"atom 백본 graph.json 없음: {path} — 원자 코퍼스를 먼저 생성하세요.")
        return 2

    records = load_atom_probes_from_json(path)
    count = populate_atom_probes(records)
    print(f"원자 ②진단문항·③소크라테스 적재 완료: {count}건 (src={path}).")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI 진입
    raise SystemExit(main())
