#!/usr/bin/env python3
"""prod 원자 코드 정리 — orphan(미적 raw)·은퇴 원자(dedup ledger) 공용 가드 스크립트.

두 가지 모드 (둘 다 dry-run 기본·--confirm 필수)
------------------------------------------------
1. **orphan 모드(기본)** — S0-5 후속: '미적' 포함 코드 중 정본 `atom_graph_v1/graph.json`에
   없는 raw 잔재를 삭제. R1(2026-06-22) 미적 원자ID raw→하이픈 재-ID의 prod 잔재 대상.
2. **은퇴 모드(`--retired-from-ledger`)** — S4-08: S4-07 중복 원자 병합으로 은퇴한 원자
   (`dedup_merges_v1.json` applied[].retired — 기수 11·미적Ⅱ 2·NUMER 1 = 14코드)를 **정확
   일치**로 삭제. 재적재(populate)는 upsert-only라 은퇴 행이 prod에 잔존하기 때문. LIKE
   마커('미적') 스캔은 기수/NUMER를 못 보므로 ledger 코드 목록이 정본이다.

왜 alembic 마이그레이션이 아니라 스크립트인가
---------------------------------------------
alembic 마이그레이션은 `alembic upgrade` 시 **자동 실행**되므로 "Kiki가 진단 리포트를
확인한 뒤에만 실행"이라는 human-in-the-loop 가드를 구조적으로 걸 수 없다. prod 데이터
삭제는 진단 리포트 확정을 전제해야 하므로, **dry-run 기본 + 명시적 --confirm** 스크립트가
안전하다(진단 스크립트와 동형 패턴·데이터 마이그레이션 무추가·alembic head 불변).

안전 가드 (되돌리기 어려운 삭제이므로 5중)
------------------------------------------
1. **dry-run 기본**: 인자 없이 실행하면 삭제 대상만 출력하고 **DELETE 0**.
2. **--confirm 필수**: 실제 삭제는 이 플래그가 있어야만.
3. **정본 대조**: 삭제 대상은 정본 graph.json에 **없는** 코드만. 은퇴 모드는 추가로
   ledger 코드가 정본에 하나라도 존재하면 **전체 거부**(병합 미반영 코퍼스 위에서 실행
   방지 — 코퍼스·ledger 버전 불일치 가드).
4. **M-series 보호**: misconception_catalog는 `mis_id LIKE 'ATOM:%'` 행만 스캔·삭제.
   구 M-series의 concept_src_id는 `H:12미적Ⅰ01-01` 같은 개념그래프 원천 키로 graph.json
   어휘와 원래 다른 것이 정상이다. (사고 경위: diagnose는 2026-07-16 이 오탐 필터를
   갖췄지만 cleanup 스캔·삭제엔 누락 — H: 행 140+건이 '미적' LIKE에 걸려 --confirm 시
   삭제될 잠재 결함을 S4-08에서 정합)
5. **단일 트랜잭션 + FK 안전 순서**: concept은 dependent(concept_edge·problem_concept)
   먼저 삭제 후 본체. 어느 단계든 실패하면 전량 롤백.

실행 (Kiki — Phaiakes9 prod에서)
--------------------------------
    # 1) dry-run (삭제 0·대상 확인) — orphan 모드는 플래그 없이, 은퇴 모드는 아래처럼
    DATABASE_URL=... python scripts/cleanup_atom_orphans.py --retired-from-ledger
    # 2) 리포트 확인 후 실제 삭제
    DATABASE_URL=... python scripts/cleanup_atom_orphans.py --retired-from-ledger --confirm
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[1]
_DIAGNOSE = Path(__file__).resolve().parent / "diagnose_atom_orphans.py"
_LEDGER = _REPO_ROOT / "data" / "corpus" / "atom_graph_v1" / "dedup_merges_v1.json"
_MIJEOK_MARKER = "미적"

# 테이블별 추가 술어 — misconception_catalog는 ATOM: 승격분만(가드 4·스캔·삭제 공용)
_EXTRA_WHERE = {"misconception_catalog": " AND mis_id LIKE 'ATOM:%'"}


def _load_canonical_codes() -> set[str]:
    """진단 스크립트의 `_canonical_codes`를 재사용(정본 graph.json 전 레벨 코드)."""
    spec = importlib.util.spec_from_file_location("diagnose_atom_orphans", _DIAGNOSE)
    if spec is None or spec.loader is None:  # pragma: no cover - 방어
        raise RuntimeError(f"진단 스크립트를 로드할 수 없습니다: {_DIAGNOSE}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    codes: set[str] = module._canonical_codes()
    return codes


def _load_retired_codes(ledger_path: Path = _LEDGER) -> list[str]:
    """병합 ledger(applied[].retired)의 은퇴 원자 코드 목록(정렬·정본은 ledger)."""
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    return sorted(m["retired"] for m in ledger["applied"])


def _find_target_codes(
    conn: Any, table: str, column: str, canonical: set[str], retired: list[str] | None
) -> list[str]:
    """테이블에서 삭제 대상 코드 목록(정렬) — 정본에 없는 것만.

    orphan 모드(retired=None)는 '미적' LIKE 스캔 후 정본 차집합, 은퇴 모드는 ledger 코드
    정확 일치. misconception_catalog는 두 모드 모두 ATOM: 행만 본다(가드 4).
    """
    from sqlalchemy import text

    extra = _EXTRA_WHERE.get(table, "")
    if retired is None:
        sql = f"SELECT {column} FROM {table} WHERE {column} LIKE :marker{extra}"
        params: dict[str, Any] = {"marker": f"%{_MIJEOK_MARKER}%"}
    else:
        sql = f"SELECT {column} FROM {table} WHERE {column} = ANY(:codes){extra}"
        params = {"codes": retired}
    rows = [r[0] for r in conn.execute(text(sql), params)]
    return sorted({c for c in rows if c not in canonical})


def _cleanup(
    engine: Any,
    canonical: set[str],
    *,
    confirm: bool,
    retired: list[str] | None = None,
) -> dict[str, Any]:
    """대상을 FK 안전 순서로 삭제(단일 트랜잭션). dry-run이면 대상만 집계."""
    from sqlalchemy import text

    if retired is not None:
        # 가드 3(은퇴 모드): ledger 코드가 정본에 존재 = 병합 미반영 코퍼스 — 전체 거부.
        overlap = sorted(set(retired) & canonical)
        if overlap:
            raise ValueError(
                f"ledger 은퇴 코드가 정본 코퍼스에 존재 — 코퍼스·ledger 불일치(삭제 거부): "
                f"{overlap[:5]}"
            )

    report: dict[str, Any] = {"confirm": confirm, "deleted": {}, "targets": {}}

    with engine.begin() as conn:
        # ── concept 테이블 대상 (FK 파급: concept_edge·problem_concept 먼저) ──
        concept_targets = _find_target_codes(conn, "concept", "code", canonical, retired)
        report["targets"]["concept"] = concept_targets

        # code 키 프로젝션·임베딩·콘텐츠·오개념(FK 없는 느슨참조·순서 무관)
        loose = {
            "atom_node": "code",
            "atom_embedding": "code",
            "concept_content": "code",
            "misconception_catalog": "concept_src_id",
        }
        for table, column in loose.items():
            try:
                report["targets"][table] = _find_target_codes(
                    conn, table, column, canonical, retired
                )
            except Exception as exc:  # 테이블 부재 등 — 집계에서 제외(진단과 동일 관용)
                report["targets"][table] = {"error": str(exc)}

        if not confirm:
            # dry-run: 삭제 없이 대상만 돌려준다(롤백은 없음 — SELECT만 했다).
            report["note"] = "dry-run — 삭제 0. 실제 삭제는 --confirm."
            return report

        # ── 실제 삭제 (--confirm) — FK 안전 순서 ──
        if concept_targets:
            # concept UUID를 먼저 조회(FK 대상)
            uuids = [
                r[0]
                for r in conn.execute(
                    text("SELECT concept_id FROM concept WHERE code = ANY(:codes)"),
                    {"codes": concept_targets},
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
                {"codes": concept_targets},
            ).rowcount

        for table, column in loose.items():
            targets = report["targets"].get(table)
            if isinstance(targets, list) and targets:
                extra = _EXTRA_WHERE.get(table, "")
                report["deleted"][table] = conn.execute(
                    text(f"DELETE FROM {table} WHERE {column} = ANY(:codes){extra}"),
                    {"codes": targets},
                ).rowcount

    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="prod 원자 코드 정리 — orphan(미적 raw)·은퇴 원자(ledger) 공용 (가드·dry-run 기본)"
    )
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="실제 삭제 실행(미지정 시 dry-run — 삭제 0). dry-run 리포트 확인 후에만 사용.",
    )
    parser.add_argument(
        "--retired-from-ledger",
        action="store_true",
        help="dedup_merges_v1.json applied의 은퇴 원자 코드를 정확 일치로 정리(S4-07 후속).",
    )
    args = parser.parse_args()

    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url:
        print("오류: DATABASE_URL 환경변수가 필요합니다.")
        return 2

    from sqlalchemy import create_engine

    canonical = _load_canonical_codes()
    retired: list[str] | None = None
    if args.retired_from_ledger:
        retired = _load_retired_codes()
        print(f"은퇴 모드 — ledger 은퇴 코드 {len(retired)}건: {retired[:3]}…")
    engine = create_engine(db_url)
    try:
        report = _cleanup(engine, canonical, confirm=args.confirm, retired=retired)
    except ValueError as exc:
        print(f"오류: {exc}")
        return 2

    total_targets = sum(len(v) for v in report["targets"].values() if isinstance(v, list))
    mode = "삭제 실행(--confirm)" if args.confirm else "dry-run(삭제 0)"
    print(f"[{mode}] 정리 대상 총 {total_targets}건")
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
        print("다음: 대상이 확인되면 --confirm으로 실제 삭제.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
