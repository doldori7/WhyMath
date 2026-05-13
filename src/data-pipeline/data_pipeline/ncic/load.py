"""성취기준 컬렉션을 파일·DB로 저장.

Phase 1 (현재): PostgreSQL 미배포 → 파일 저장만 동작.
  - `write_json`: 공공누리 출처 + 라이선스 + 메타데이터 + 데이터 (사람·기계 모두 가독)
  - `write_csv`: 표 분석용 (Excel·Pandas 친화)

Phase 2 시그니처만 (`load_to_postgres`): 호출 시 NotImplementedError.
"""

from __future__ import annotations

import csv
import json
import logging
from collections.abc import Sequence
from datetime import datetime, timezone
from pathlib import Path

from data_pipeline.ncic.models import (
    LICENSE_NOTICE,
    SOURCE_CITATION,
    AchievementStandard,
    AchievementStandardCollection,
)

logger = logging.getLogger("data_pipeline.ncic.load")

# CSV 컬럼 순서 (안정)
_CSV_FIELDS: tuple[str, ...] = (
    "code",
    "school_type",
    "grade_band",
    "subject",
    "domain",
    "sub_domain",
    "statement",
    "commentary",
    "big_idea",
    "curriculum_revision",
    "effective_from",
    "parent_codes",
    "source_url",
    "source_document",
)


def _make_collection(
    standards: Sequence[AchievementStandard],
    *,
    crawler_version: str = "0.1.0",
) -> AchievementStandardCollection:
    """저장용 컬렉션 객체 생성 (출처·라이선스·시각 메타데이터 동봉)."""
    return AchievementStandardCollection(
        collected_at=datetime.now(tz=timezone.utc).isoformat(),
        crawler_version=crawler_version,
        standards=list(standards),
    )


def write_json(
    standards: Sequence[AchievementStandard],
    output_path: Path,
    *,
    crawler_version: str = "0.1.0",
    indent: int = 2,
) -> AchievementStandardCollection:
    """성취기준을 JSON으로 저장.

    JSON 표지에 SOURCE_CITATION + LICENSE_NOTICE를 *반드시* 포함.

    Args:
        standards: 저장 대상.
        output_path: 출력 파일 경로 (디렉토리 자동 생성).
        crawler_version: 메타데이터.
        indent: JSON 들여쓰기.

    Returns:
        생성한 컬렉션 객체.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    collection = _make_collection(standards, crawler_version=crawler_version)

    # ensure_ascii=False — 한국어 그대로
    output_path.write_text(
        collection.model_dump_json(indent=indent),
        encoding="utf-8",
    )
    logger.info(
        "JSON 저장: %s (%d개 성취기준, %d bytes)",
        output_path,
        collection.count,
        output_path.stat().st_size,
    )
    return collection


def write_csv(
    standards: Sequence[AchievementStandard],
    output_path: Path,
) -> int:
    """성취기준을 CSV로 저장.

    CSV는 표지 행에 출처를 *주석으로* 둘 수 없으므로,
    동봉 메타데이터는 별도 sidecar 파일(`<name>.meta.json`)로 함께 기록.

    Args:
        standards: 저장 대상.
        output_path: 출력 파일 경로.

    Returns:
        저장된 행 수.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rows_written = 0
    with output_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=_CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for std in standards:
            row = std.model_dump(mode="json")
            # list → 세미콜론 구분 (CSV 호환)
            row["parent_codes"] = ";".join(std.parent_codes) if std.parent_codes else ""
            # None → 빈 문자열
            for k in list(row.keys()):
                if row[k] is None:
                    row[k] = ""
            writer.writerow(row)
            rows_written += 1

    # 메타데이터 sidecar
    sidecar = output_path.with_suffix(".meta.json")
    sidecar.write_text(
        json.dumps(
            {
                "source_citation": SOURCE_CITATION,
                "license_notice": LICENSE_NOTICE,
                "rows": rows_written,
                "csv_file": output_path.name,
                "collected_at": datetime.now(tz=timezone.utc).isoformat(),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    logger.info("CSV 저장: %s (%d행) + sidecar: %s", output_path, rows_written, sidecar)
    return rows_written


# ──────────────────────────────────────────────────────────────────────
# Phase 2 PostgreSQL 적재 (시그니처만 — 미구현)
# ──────────────────────────────────────────────────────────────────────
async def load_to_postgres(
    standards: Sequence[AchievementStandard],
    *,
    dsn: str,
    table_name: str = "achievement_standards",
    upsert: bool = True,
) -> int:
    """PostgreSQL `achievement_standards` 테이블에 적재.

    Phase 1 (현재): *미구현*. Phase 2에 `[postgres]` extra + Alembic 마이그레이션
    구축 후 backend-engineer가 구현.

    Args:
        standards: 적재 대상.
        dsn: PostgreSQL 연결 문자열 (asyncpg 형식).
        table_name: 테이블명.
        upsert: code PK 충돌 시 UPDATE 여부.

    Returns:
        적재된 행 수.

    Raises:
        NotImplementedError: 항상.
    """
    raise NotImplementedError(
        "Phase 2에 backend-engineer가 구현 예정. " "현재는 `write_json` / `write_csv` 사용."
    )


__all__ = ["load_to_postgres", "write_csv", "write_json"]
