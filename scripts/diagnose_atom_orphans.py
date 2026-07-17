#!/usr/bin/env python3
"""S0-5: prod 미적분 raw 원자 코드 orphan 진단 (읽기 전용).

배경
----
R1(2026-06-22)에서 미적Ⅰ/Ⅱ 원자ID 129개를 raw→하이픈으로 재-ID해 정본 코퍼스
(`data/corpus/atom_graph_v1/graph.json`)를 재생성했다. CI는 fresh DB라 무관하지만,
그 전에 적재된 prod DB에는 raw(비하이픈) 형태의 미적 코드가 orphan으로 남아
정본 원자와 매칭되지 않을 수 있다 (MEMORY.md "prod 미적분 raw 129건 orphan").

raw의 정확한 형태는 기록에 없으므로, **집합 차이 방식**으로 탐지한다:
"미적"을 포함하는 코드 중 정본 graph.json의 코드 집합(전 레벨: 단원·소단원·
세부개념·대학)에 없는 것 = orphan 후보. raw 형태를 몰라도 견고하다.

실행 (Kiki — Phaiakes9 prod에서, 읽기 전용)
--------------------------------------------
    DATABASE_URL=postgresql+psycopg://... /tmp/bevenv/bin/python scripts/diagnose_atom_orphans.py

- SELECT만 수행한다 (쓰기 0). 정리 마이그레이션은 이 리포트 확정 후 별도 작업.
- 리포트는 stdout + `scripts/atom_orphan_report.json`(경로 인자로 변경 가능:
  `--out <path>`).

검사 대상 (code 키 테이블 5곳)
------------------------------
1. concept.code            — 원자/소단원/단원이 additive 적재된 런타임 테이블.
                             orphan concept 행은 FK 파급(concept_edge·problem_concept·
                             concept_mastery_history)도 함께 센다.
2. atom_node.code          — 원자 메타 프로젝션
3. atom_embedding.code     — 원자 임베딩 (PK=code)
4. concept_content.code    — 콘텐츠 4종 (K-12=437 개념코드·대학=소단원코드)
5. misconception_catalog.concept_src_id — ATOM: 네임스페이스 승격분의 느슨참조.
   **mis_id LIKE 'ATOM:%' 행만 검사한다** — 구 M-series(misconceptions_v1) 행의
   concept_src_id는 `H:12미적Ⅰ01-01` 같은 개념그래프 원천 키(H: 네임스페이스)로,
   graph.json 어휘와 원래 다른 것이 정상이다. 2026-07-16 whymath-pg 실측에서 이
   필터 없이 140건이 오탐된 것을 수정 (현행 코퍼스에도 동일 H: 코드 142건 존재).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[1]
_GRAPH_JSON = _REPO_ROOT / "data" / "corpus" / "atom_graph_v1" / "graph.json"

# 미적 계열 판별 마커 — K-12(12미적Ⅰ/Ⅱ)와 대학(미적1/미적2 소단원·단원) 모두 포함
_MIJEOK_MARKER = "미적"


def _canonical_codes() -> set[str]:
    """정본 코퍼스의 전 레벨 코드 집합 (단원·소단원·세부개념·대학)."""
    graph = json.loads(_GRAPH_JSON.read_text(encoding="utf-8"))
    return {node["code"] for node in graph["concepts"]}


def _scan(engine: Any, canonical: set[str]) -> dict[str, Any]:
    """code 키 테이블 5곳을 읽기 전용으로 스캔해 orphan 후보를 수집."""
    from sqlalchemy import text

    report: dict[str, Any] = {"tables": {}, "total_orphans": 0}
    queries: dict[str, str] = {
        "concept": "SELECT code FROM concept WHERE code LIKE :marker",
        "atom_node": "SELECT code FROM atom_node WHERE code LIKE :marker",
        "atom_embedding": "SELECT code FROM atom_embedding WHERE code LIKE :marker",
        "concept_content": "SELECT code FROM concept_content WHERE code LIKE :marker",
        # ATOM: 승격분만 — 구 M-series의 H: 네임스페이스 concept_src_id는 정상 어휘(오탐 방지)
        "misconception_catalog": (
            "SELECT concept_src_id AS code FROM misconception_catalog "
            "WHERE concept_src_id LIKE :marker AND mis_id LIKE 'ATOM:%'"
        ),
    }
    marker = f"%{_MIJEOK_MARKER}%"

    with engine.connect() as conn:
        for table, sql in queries.items():
            try:
                rows = [r[0] for r in conn.execute(text(sql), {"marker": marker})]
            except Exception as exc:  # 테이블 부재 등 — 진단이므로 계속 진행
                report["tables"][table] = {"error": str(exc)}
                continue
            orphans = sorted(c for c in rows if c not in canonical)
            entry: dict[str, Any] = {
                "scanned": len(rows),
                "orphans": len(orphans),
                "orphan_codes": orphans,
            }
            # concept 행은 FK 파급도 함께 센다 (UUID FK 경유)
            if table == "concept" and orphans:
                fanout_sql = text(
                    """
                    SELECT c.code,
                           (SELECT count(*) FROM concept_edge e
                             WHERE e.from_concept_id = c.concept_id
                                OR e.to_concept_id = c.concept_id) AS edge_refs,
                           (SELECT count(*) FROM problem_concept pc
                             WHERE pc.concept_id = c.concept_id) AS problem_refs
                      FROM concept c WHERE c.code = ANY(:codes)
                    """
                )
                entry["fk_fanout"] = [
                    {"code": r[0], "edge_refs": r[1], "problem_refs": r[2]}
                    for r in conn.execute(fanout_sql, {"codes": orphans})
                ]
            report["tables"][table] = entry
            report["total_orphans"] += len(orphans)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="prod 미적 raw 원자 코드 orphan 진단 (읽기 전용)")
    parser.add_argument(
        "--out",
        default=str(_REPO_ROOT / "scripts" / "atom_orphan_report.json"),
        help="JSON 리포트 출력 경로",
    )
    args = parser.parse_args()

    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url:
        print("오류: DATABASE_URL 환경변수가 필요합니다 (읽기 전용 SELECT만 수행).")
        return 2

    from sqlalchemy import create_engine

    canonical = _canonical_codes()
    mijeok_canonical = {c for c in canonical if _MIJEOK_MARKER in c}
    print(f"정본 코드 {len(canonical)}개 로드 (미적 계열 {len(mijeok_canonical)}개)")

    engine = create_engine(db_url)
    report = _scan(engine, canonical)
    report["canonical_total"] = len(canonical)
    report["canonical_mijeok"] = len(mijeok_canonical)

    for table, entry in report["tables"].items():
        if "error" in entry:
            print(f"  [{table}] 스캔 실패: {entry['error']}")
        else:
            print(f"  [{table}] 미적 계열 {entry['scanned']}행 중 orphan {entry['orphans']}건")
            for code in entry["orphan_codes"][:5]:
                print(f"      - {code}")
            if entry["orphans"] > 5:
                print(f"      … 외 {entry['orphans'] - 5}건 (JSON 리포트 참조)")

    Path(args.out).write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\n총 orphan {report['total_orphans']}건 — 리포트: {args.out}")
    print("다음 단계: 리포트를 확정하면 정리 마이그레이션을 별도 슬라이스로 진행 (쓰기 없음 보장).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
