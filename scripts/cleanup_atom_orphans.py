#!/usr/bin/env python3
"""S0-5 후속: prod 미적분 raw 원자 코드 orphan **정리** (가드·dry-run 기본).

배경
----
`diagnose_atom_orphans.py`가 식별하는 orphan(정본 `atom_graph_v1/graph.json` 코드 집합에
없는 '미적' 코드)을 prod DB에서 **삭제**한다. R1(2026-06-22)의 미적 원자ID raw→하이픈
재-ID로 prod에 남은 raw 잔재가 대상.

왜 alembic 마이그레이션이 아니라 스크립트인가
---------------------------------------------
alembic 마이그레이션은 `alembic upgrade` 시 **자동 실행**되므로 "Kiki가 진단 리포트를
확인한 뒤에만 실행"이라는 human-in-the-loop 가드를 구조적으로 걸 수 없다. prod 데이터
삭제는 진단 리포트 확정을 전제해야 하므로, **dry-run 기본 + 명시적 --confirm** 스크립트가
안전하다(진단 스크립트와 동형 패턴·데이터 마이그레이션 무추가·alembic head 불변).

안전 가드 (되돌리기 어려운 삭제이므로 4중)
------------------------------------------
1. **dry-run 기본**: 인자 없이 실행하면 삭제 대상만 출력하고 **DELETE 0**.
2. **--confirm 필수**: 실제 삭제는 이 플래그가 있어야만.
3. **정본 대조**: 삭제 대상 = '미적' 포함 코드 AND 정본 graph.json에 **없는** 것만
   (canonical에 있는 정상 원자는 절대 건드리지 않음).
4. **단일 트랜잭션 + FK 안전 순서**: concept orphan은 dependent(concept_edge·
   problem_concept) 먼저 삭제 후 본체. 어느 단계든 실패하면 전량 롤백.

실행 (Kiki — Phaiakes9 prod에서)
--------------------------------
    # 1) 먼저 진단 (읽기 전용)
    DATABASE_URL=... python scripts/diagnose_atom_orphans.py
    # 2) 리포트 확인 후 dry-run (삭제 0·대상 재확인)
    DATABASE_URL=... python scripts/cleanup_atom_orphans.py
    # 3) 확인되면 실제 삭제
    DATABASE_URL=... python scripts/cleanup_atom_orphans.py --confirm
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import sys
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[1]
_DIAGNOSE = Path(__file__).resolve().parent / "diagnose_atom_orphans.py"
_MIJEOK_MARKER = "미적"


def _load_canonical_codes() -> set[str]:
    """진단 스크립트의 `_canonical_codes`를 재사용(정본 graph.json 전 레벨 코드)."""
    spec = importlib.util.spec_from_file_location("diagnose_atom_orphans", _DIAGNOSE)
    if spec is None or spec.loader is None:  # pragma: no cover - 방어
        raise RuntimeError(f"진단 스크립트를 로드할 수 없습니다: {_DIAGNOSE}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    codes: set[str] = module._canonical_codes()
    return codes


def _find_orphan_codes(conn: Any, table: str, column: str, canonical: set[str]) -> list[str]:
    """테이블의 '미적' 코드 중 정본에 없는 orphan 코드 목록(정렬)."""
    from sqlalchemy import text

    rows = [
        r[0]
        for r in conn.execute(
            text(f"SELECT {column} FROM {table} WHERE {column} LIKE :marker"),
            {"marker": f"%{_MIJEOK_MARKER}%"},
        )
    ]
    return sorted(c for c in rows if c not in canonical)


def _cleanup(engine: Any, canonical: set[str], *, confirm: bool) -> dict[str, Any]:
    """orphan을 FK 안전 순서로 삭제(단일 트랜잭션). dry-run이면 대상만 집계."""
    from sqlalchemy import text

    report: dict[str, Any] = {"confirm": confirm, "deleted": {}, "targets": {}}

    with engine.begin() as conn:
        # ── concept 테이블 orphan (FK 파급: concept_edge·problem_concept 먼저) ──
        concept_orphans = _find_orphan_codes(conn, "concept", "code", canonical)
        report["targets"]["concept"] = concept_orphans

        # code 키 프로젝션·임베딩·콘텐츠·오개념(FK 없는 느슨참조·순서 무관)
        loose = {
            "atom_node": "code",
            "atom_embedding": "code",
            "concept_content": "code",
            "misconception_catalog": "concept_src_id",
        }
        for table, column in loose.items():
            try:
                report["targets"][table] = _find_orphan_codes(conn, table, column, canonical)
            except Exception as exc:  # 테이블 부재 등 — 집계에서 제외(진단과 동일 관용)
                report["targets"][table] = {"error": str(exc)}

        if not confirm:
            # dry-run: 삭제 없이 대상만 돌려준다(롤백은 없음 — SELECT만 했다).
            report["note"] = "dry-run — 삭제 0. 실제 삭제는 --confirm."
            return report

        # ── 실제 삭제 (--confirm) — FK 안전 순서 ──
        if concept_orphans:
            # concept UUID를 먼저 조회(FK 대상)
            uuids = [
                r[0]
                for r in conn.execute(
                    text("SELECT concept_id FROM concept WHERE code = ANY(:codes)"),
                    {"codes": concept_orphans},
                )
            ]
            if uuids:
                report["deleted"]["concept_edge"] = conn.execute(
                    text(
                        "DELETE FROM concept_edge "
                        "WHERE from_concept_id = ANY(:ids) OR to_concept_id = ANY(:ids)"
                    ),
                    {"ids": uuids},
                ).rowcount
                report["deleted"]["problem_concept"] = conn.execute(
                    text("DELETE FROM problem_concept WHERE concept_id = ANY(:ids)"),
                    {"ids": uuids},
                ).rowcount
            report["deleted"]["concept"] = conn.execute(
                text("DELETE FROM concept WHERE code = ANY(:codes)"),
                {"codes": concept_orphans},
            ).rowcount

        for table, column in loose.items():
            targets = report["targets"].get(table)
            if isinstance(targets, list) and targets:
                report["deleted"][table] = conn.execute(
                    text(f"DELETE FROM {table} WHERE {column} = ANY(:codes)"),
                    {"codes": targets},
                ).rowcount

    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="prod 미적 raw 원자 orphan 정리 (가드·dry-run 기본)"
    )
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="실제 삭제 실행(미지정 시 dry-run — 삭제 0). 진단 리포트 확인 후에만 사용.",
    )
    args = parser.parse_args()

    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url:
        print("오류: DATABASE_URL 환경변수가 필요합니다.")
        return 2

    from sqlalchemy import create_engine

    canonical = _load_canonical_codes()
    engine = create_engine(db_url)
    report = _cleanup(engine, canonical, confirm=args.confirm)

    total_targets = sum(len(v) for v in report["targets"].values() if isinstance(v, list))
    mode = "삭제 실행(--confirm)" if args.confirm else "dry-run(삭제 0)"
    print(f"[{mode}] orphan 대상 총 {total_targets}건")
    for table, targets in report["targets"].items():
        if isinstance(targets, list):
            print(f"  [{table}] {len(targets)}건" + (f": {targets[:3]}…" if targets else ""))
        else:
            print(f"  [{table}] 스캔 실패: {targets.get('error')}")
    if args.confirm:
        for table, n in report["deleted"].items():
            print(f"  삭제됨 [{table}]: {n}행")
        print("완료 — 단일 트랜잭션 커밋(실패 시 전량 롤백).")
    else:
        print("다음: 진단 리포트가 확정되면 --confirm으로 실제 삭제.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
