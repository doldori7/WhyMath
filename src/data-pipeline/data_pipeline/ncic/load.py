"""성취기준 컬렉션을 파일·DB로 저장.

파일 저장(의존성 없음):
  - `write_json`: 공공누리 출처 + 라이선스 + 메타데이터 + 데이터 (사람·기계 모두 가독)
  - `write_csv`: 표 분석용 (Excel·Pandas 친화)

PostgreSQL 적재(`load_to_postgres`): `[postgres]` extra(sqlalchemy[asyncio]+asyncpg)가
필요하다. 이 모듈은 *extra 없이도 import 가능*해야 하므로(write_json/write_csv 사용자) sqlalchemy
import는 `load_to_postgres` 안에서 *지연*한다 — 미설치 시 명확한 RuntimeError로 안내한다.

`achievement_standards`는 이 로더가 소유하는 **L1 staging 테이블**이다 — WhyMath v1.0 앱 스키마
(concept·problem 등, backend/alembic)와 *별개*이며, 성취기준→concept 변환은 후속 'A' 단계
(pedagogy 동반) 책임이다. data-pipeline엔 alembic이 없으므로 테이블은 `create_all`(checkfirst,
멱등)로 보장한다.
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
    ConceptStandardLink,
    ConceptStandardLinkCollection,
)

logger = logging.getLogger("data_pipeline.ncic.load")

# CSV 컬럼 순서 (안정) — norm_id가 PK이므로 선두에 둔다.
_CSV_FIELDS: tuple[str, ...] = (
    "norm_id",
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


def _make_links_collection(
    links: Sequence[ConceptStandardLink],
    *,
    crawler_version: str = "0.1.0",
) -> ConceptStandardLinkCollection:
    """저장용 연결 컬렉션 객체 생성 (출처·라이선스·시각 메타데이터 동봉)."""
    return ConceptStandardLinkCollection(
        collected_at=datetime.now(tz=timezone.utc).isoformat(),
        crawler_version=crawler_version,
        links=list(links),
    )


def write_links_json(
    links: Sequence[ConceptStandardLink],
    output_path: Path,
    *,
    crawler_version: str = "0.1.0",
    indent: int = 2,
) -> ConceptStandardLinkCollection:
    """개념↔성취기준 연결을 JSON으로 저장.

    `write_json`과 동일 구조 — JSON 표지에 SOURCE_CITATION + LICENSE_NOTICE를 *반드시* 포함.

    Args:
        links: 저장 대상 연결.
        output_path: 출력 파일 경로 (디렉토리 자동 생성).
        crawler_version: 메타데이터.
        indent: JSON 들여쓰기.

    Returns:
        생성한 연결 컬렉션 객체.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    collection = _make_links_collection(links, crawler_version=crawler_version)

    # ensure_ascii=False — 한국어 그대로
    output_path.write_text(
        collection.model_dump_json(indent=indent),
        encoding="utf-8",
    )
    logger.info(
        "JSON 저장: %s (%d개 연결, %d bytes)",
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
# PostgreSQL 적재 ([postgres] extra 필요 — sqlalchemy import는 함수 내 지연)
# ──────────────────────────────────────────────────────────────────────
def _to_async_dsn(dsn: str) -> str:
    """동기 `postgresql://` DSN을 asyncpg 드라이버 형식으로 정규화.

    `create_async_engine`은 async 드라이버를 요구한다(`postgresql+asyncpg://`). 드라이버가
    이미 명시된(`postgresql+<driver>://`) DSN은 그대로 둔다.
    """
    prefix = "postgresql://"
    if dsn.startswith(prefix):
        return "postgresql+asyncpg://" + dsn[len(prefix) :]
    return dsn


async def load_to_postgres(
    standards: Sequence[AchievementStandard],
    *,
    dsn: str,
    table_name: str = "achievement_standards",
    upsert: bool = True,
) -> int:
    """성취기준을 PostgreSQL `achievement_standards` 테이블에 적재(upsert).

    `[postgres]` extra(sqlalchemy[asyncio]+asyncpg)가 필요하다 — 미설치 시 RuntimeError로
    설치를 안내한다(모듈 import는 extra 없이도 가능하도록 sqlalchemy를 여기서 지연 import).
    테이블은 이 로더가 소유하는 L1 staging 테이블이라 `create_all`(checkfirst, 멱등)로 보장한다.

    `norm_id`는 PK이므로 입력 내 중복은 *마지막 항목*으로 dedup한다(단일 INSERT의 ON CONFLICT가
    같은 행을 두 번 건드리는 오류 방지). `code`(official_code)는 교육과정 간 *비유일*이라 PK가 아닌
    일반 컬럼이다. `upsert=True`면 norm_id 충돌 시 나머지 컬럼을 UPDATE, False면 무시한다
    (DO NOTHING). 빈 입력은 *연결 없이* 0을 돌려준다(조기 반환).

    Args:
        standards: 적재 대상.
        dsn: PostgreSQL 연결 문자열(`postgresql://` 또는 `postgresql+asyncpg://`).
        table_name: 테이블명(기본 `achievement_standards`).
        upsert: norm_id PK 충돌 시 UPDATE 여부(False면 DO NOTHING).

    Returns:
        영향받은(적재·갱신된) 행 수.

    Raises:
        RuntimeError: `[postgres]` extra 미설치 시.
    """
    if not standards:
        return 0
    try:
        from sqlalchemy import Column, Date, MetaData, Table, Text
        from sqlalchemy.dialects.postgresql import ARRAY
        from sqlalchemy.dialects.postgresql import insert as pg_insert
        from sqlalchemy.ext.asyncio import create_async_engine
    except ModuleNotFoundError as exc:  # pragma: no cover - 환경 안내 경로
        raise RuntimeError(
            "load_to_postgres에는 [postgres] extra가 필요합니다 — "
            "`pip install -e '.[postgres]'` 후 재시도하세요."
        ) from exc

    metadata = MetaData()
    table = Table(
        table_name,
        metadata,
        # PK = norm_id (교육과정 간 유일). code는 비유일 일반 컬럼.
        Column("norm_id", Text, primary_key=True),
        Column("code", Text, nullable=False),
        Column("school_type", Text, nullable=False),
        Column("grade_band", Text, nullable=False),
        Column("subject", Text, nullable=False),
        Column("domain", Text, nullable=False),
        Column("sub_domain", Text),
        Column("statement", Text, nullable=False),
        Column("commentary", Text),
        Column("big_idea", Text),
        Column("curriculum_revision", Text, nullable=False),
        Column("effective_from", Date),
        Column("parent_codes", ARRAY(Text), nullable=False),
        Column("source_url", Text, nullable=False),
        Column("source_document", Text),
    )

    # norm_id PK 기준 dedup(마지막 우선) — 단일 배치 INSERT의 ON CONFLICT 중복행 오류 방지.
    by_norm_id: dict[str, dict[str, object]] = {
        std.norm_id: std.model_dump(mode="python") for std in standards
    }
    rows = list(by_norm_id.values())

    engine = create_async_engine(_to_async_dsn(dsn))
    try:
        async with engine.begin() as conn:
            await conn.run_sync(metadata.create_all)  # 멱등 — staging 테이블 보장
            stmt = pg_insert(table).values(rows)
            if upsert:
                stmt = stmt.on_conflict_do_update(
                    index_elements=["norm_id"],
                    set_={
                        col.name: stmt.excluded[col.name]
                        for col in table.columns
                        if col.name != "norm_id"
                    },
                )
            else:
                stmt = stmt.on_conflict_do_nothing(index_elements=["norm_id"])
            result = await conn.execute(stmt)
    finally:
        await engine.dispose()

    return result.rowcount if result.rowcount >= 0 else len(rows)


__all__ = ["load_to_postgres", "write_csv", "write_json", "write_links_json"]
