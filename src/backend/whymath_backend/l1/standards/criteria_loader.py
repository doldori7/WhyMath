"""KICE 평가기준·성취수준 코퍼스(achievement_criteria_v1) → backend 적재기 (CUR-07).

`l1/standards/standard_loader.py`(NCIC `standards_v1`/`standards_university_v1` — 개별 성취기준
전체 레코드 적재)의 *성격이 다른* 짝이다. `achievement_criteria_v1`(CUR-05 회수,
`data/corpus/achievement_criteria_v1/achievement_criteria.json`)은 개별 성취기준 레코드가 아니라
**13 school_level×subject 세트**이며, 각 세트가 ①단원 계층 ②성취기준→평가준거 코드 커버리지
③단원→성취수준 등급 커버리지 3필드를 갖는다(데이터 카드 `docs/data/achievement_criteria_v1.md`
§2). 이 로더는 그중 ②·③만 다룬다(①`unit_hierarchy`는 이 태스크 범위 밖 — 반입 안 함, 스키마
설계 정본 = `schema/standard.py` 모듈 docstring "CUR-07 확장").

────────────────────────────────────────────────────────────────────────────
코퍼스 포맷 (바로 배열 — Collection 표지 래핑 없음)
────────────────────────────────────────────────────────────────────────────
`standard_loader._as_collection`이 다루는 `standards_v1`(`{"standards": [...], ...}` 단일 객체)과
달리, `achievement_criteria.json`은 **최상위가 바로 배열**이다(`[ {school_level, subject,
unit_hierarchy, standard_criteria_coverage, achievement_levels_by_unit}, ... ]`, 13원소 — 실측
확인). `SOURCE_CITATION`/`LICENSE_NOTICE` 같은 표지 메타가 없다(그 역할은 옆의
`_provenance.json`이 대신한다). 이 모듈은 그 바로-배열 형태를 그대로 받는다.

────────────────────────────────────────────────────────────────────────────
두 필드, 두 다른 조인 축 — 강제로 하나로 합치지 않는다(CUR-07 핵심 설계 결정)
────────────────────────────────────────────────────────────────────────────
`schema/standard.py` 모듈 docstring "CUR-07 확장"이 실측 근거를 기록한다. 요약:

  ① `standard_criteria_coverage`(official_code 단위, 459건 전량) — `(curriculum_revision,
     official_code)` 대조로 이미 적재된 `AchievementStandard` 행을 찾아 `evaluation_criteria_codes`
     컬럼을 **UPDATE**한다(`CriteriaCoverageStore`). 코퍼스 자체엔 `curriculum_revision` 필드가
     없다 — `_provenance.json`의 두 출처가 모두 "2015 개정 교육과정에 따른 ... 평가기준 개발
     연구"이므로 `DEFAULT_CURRICULUM_REVISION = "2015 개정"` 상수로 고정한다(교차검증: 459/459가
     `standards_v1`의 2015 개정 official_code 집합과 정확히 일치 — 실측 완료, 미확인 추론 아님).
     매칭 실패(해당 official_code가 그 revision으로 적재돼 있지 않음)는 **조용히 건너뛰지 않고**
     `CriteriaMatchResult.unmatched`/`unmatched_codes`로 정직 계상하고 로그에 남긴다("작동한 비율"
     원칙 — CLAUDE.md).
  ② `achievement_levels_by_unit`(unit 문자열 단위, 54건) — 개별 성취기준과 **연결하지 않는다**
     (`AchievementLevelUnit` 별도 테이블에 upsert만 한다, `AchievementLevelUnitStore`). 근거는
     `db/models/achievement_level_unit.py` 모듈 docstring 참조.

두 store를 조합하는 `load_achievement_criteria`가 이 모듈의 공개 진입점이다.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from whymath_backend.config import Settings, get_settings

# 슬3 sync 엔진 빌더 재사용(신규 seam 0) — standard_loader.py와 동일 규약.
from whymath_backend.l1.concept_graph.embedding import _build_sync_engine
from whymath_backend.schema.standard import AchievementLevelUnit

if TYPE_CHECKING:
    from sqlalchemy.engine import Engine

logger = logging.getLogger("whymath.l1.standards.criteria_loader")

# achievement_criteria_v1은 2015 개정 KICE 평가기준 보고서 2건에서만 추출됐다(_provenance.json
# sources — 데이터 카드 §1). 코퍼스 자체엔 curriculum_revision 필드가 없어 상수로 고정한다(모듈
# docstring §① — 459/459 교차검증 완료).
DEFAULT_CURRICULUM_REVISION = "2015 개정"

# 로더 기본 출처 식별자 — AchievementLevelUnit.source_document에 채운다(코퍼스 폴더명과 동일).
DEFAULT_SOURCE_DOCUMENT = "achievement_criteria_v1"


# ──────────────────────────────────────────────────────────────────────────
# 코퍼스 입력 정규화 (list | Path → 레코드 배열)
# ──────────────────────────────────────────────────────────────────────────
def _as_records(source: list[dict[str, Any]] | Path) -> list[dict[str, Any]]:
    """코퍼스 입력을 레코드 배열로 정규화 — `achievement_criteria.json`은 *바로 배열*이다.

    `standard_loader._as_collection`(Collection 표지 dict)과는 다른 형태(모듈 docstring) — 여기선
    `list`를 그대로 받거나, `Path`면 JSON을 로드해 최상위가 배열인지 검사한다.

    Raises:
        FileNotFoundError: Path가 가리키는 파일 부재.
        TypeError: list·Path가 아닌 입력, 또는 Path 내용이 배열이 아님.
    """
    if isinstance(source, list):
        return source
    if isinstance(source, Path):
        loaded: Any = json.loads(source.read_text(encoding="utf-8"))
        if not isinstance(loaded, list):
            raise TypeError(
                f"achievement_criteria_v1 코퍼스는 최상위가 배열이어야 합니다: "
                f"{type(loaded).__name__} (파일: {source})"
            )
        return loaded
    raise TypeError(f"코퍼스 입력은 list 또는 Path여야 합니다: {type(source).__name__}")


# ──────────────────────────────────────────────────────────────────────────
# 코퍼스 → 평탄화 (standard_code→criteria_codes 맵 / AchievementLevelUnit 목록)
# ──────────────────────────────────────────────────────────────────────────
def _extract_coverage(records: Sequence[dict[str, Any]]) -> dict[str, list[str]]:
    """전 레코드의 `standard_criteria_coverage`를 `{standard_code: criteria_codes}`로 평탄화.

    코퍼스 전체에서 `standard_code`는 실측상 전역 유일하다(459/459 — NCIC 코드가 과목 접두를
    이미 포함해 레코드 간 충돌이 없다). 이론상 중복이 있어도 여기서는 *마지막 레코드 우선*으로
    접힌다(다른 로더의 "입력 내 중복은 마지막 우선 dedup" 관례와 동형).
    """
    coverage: dict[str, list[str]] = {}
    for record in records:
        for entry in record.get("standard_criteria_coverage", []):
            coverage[entry["standard_code"]] = list(entry.get("criteria_codes", []))
    return coverage


def _extract_level_units(
    records: Sequence[dict[str, Any]],
    *,
    source_document: str | None,
) -> list[AchievementLevelUnit]:
    """전 레코드의 `achievement_levels_by_unit`을 `schema.AchievementLevelUnit` 목록으로 평탄화.

    각 원소는 소속 레코드의 `school_level`·`subject`를 그대로 물려받는다(코퍼스 원문 그대로 —
    닫힌 enum 강제 없음, `AchievementLevelUnit` schema 방침).
    """
    units: list[AchievementLevelUnit] = []
    for record in records:
        school_level = record["school_level"]
        subject = record["subject"]
        for entry in record.get("achievement_levels_by_unit", []):
            units.append(
                AchievementLevelUnit(
                    school_level=school_level,
                    subject=subject,
                    unit=entry["unit"],
                    levels=list(entry.get("levels", [])),
                    source_document=source_document,
                )
            )
    return units


# ──────────────────────────────────────────────────────────────────────────
# 반환 타입 (정직 계상 — 매칭/미매칭 둘 다 호출자에게 남긴다)
# ──────────────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class CriteriaMatchResult:
    """평가준거 코드 매칭 결과 — "작동한 비율" 원칙(CLAUDE.md): 매칭 실패도 반환값에 남는다."""

    matched: int
    unmatched: int
    # 불변(tuple) 기본값 — dataclass 가변 기본값 금지 규칙에 안 걸림(field() 불요).
    unmatched_codes: tuple[str, ...] = ()


@dataclass(frozen=True)
class CriteriaLoadResult:
    """`load_achievement_criteria` 종합 반환 — 평가준거 매칭 통계 + 단원 등급 적재 수."""

    criteria: CriteriaMatchResult
    level_units_loaded: int


# ──────────────────────────────────────────────────────────────────────────
# ① CriteriaCoverageStore — (curriculum_revision, official_code) 대조 UPDATE
# ──────────────────────────────────────────────────────────────────────────
class CriteriaCoverageStore:
    """`achievement_standard.evaluation_criteria_codes`를 대조 매칭·UPDATE(sync).

    `norm_id`를 모르는 상태(코퍼스는 `official_code`만 준다)라 PK가 아니라 UNIQUE
    `(curriculum_revision, official_code)`로 대조한다 — 그 복합키가 유일함을 DB 제약이 보장하므로
    UPDATE는 각 코드당 최대 1행만 건드린다. 매칭 실패는 **조용히 넘어가지 않고**
    `CriteriaMatchResult`로 반환·로그 경고한다(official_code가 그 revision으로 아직 적재되지
    않았거나, 표기 체계가 다를 수 있음 — 데이터 카드 §4 경고).
    """

    def __init__(self, *, engine: Engine | None = None, settings: Settings | None = None) -> None:
        self._engine = engine
        self._settings = settings

    @property
    def _resolved_settings(self) -> Settings:
        """설정 지연 해석 — 주입 우선, 없으면 캐시된 전역 Settings(standard_loader 패턴)."""
        if self._settings is None:
            self._settings = get_settings()
        return self._settings

    def _get_engine(self) -> Engine:
        """sync 엔진 지연 해석 — 주입 우선, 없으면 슬3 빌더로 생성·캐시(신규 seam 0)."""
        if self._engine is None:
            self._engine = _build_sync_engine(self._resolved_settings)
        return self._engine

    def _load_known_pairs(self) -> set[tuple[str, str]]:
        """`achievement_standard`의 `(curriculum_revision, official_code)` 전량 단일 조회(N+1 0).

        매칭 대조 집합 — official_code 대조가 존재하는 (revision, code) 쌍인지 확인하는 데 쓴다
        (standard_loader의 `_load_known_norm_ids` 동형 패턴).
        """
        from sqlalchemy import select

        from whymath_backend.db.models.achievement_standard import (
            AchievementStandard as AchievementStandardORM,
        )

        stmt = select(
            AchievementStandardORM.curriculum_revision, AchievementStandardORM.official_code
        )
        with self._get_engine().connect() as conn:
            rows = conn.execute(stmt).all()
        return {(row.curriculum_revision, row.official_code) for row in rows}

    def apply(
        self,
        coverage: dict[str, list[str]],
        *,
        curriculum_revision: str = DEFAULT_CURRICULUM_REVISION,
    ) -> CriteriaMatchResult:
        """`{official_code: criteria_codes}` 맵을 `(curriculum_revision, official_code)` 대조로
        `achievement_standard.evaluation_criteria_codes`에 UPDATE. 매칭/미매칭 정직 계상.

        빈 입력은 (0, 0, ())로 조기 반환. UPDATE는 SQLAlchemy Core `update()`(원시 SQL 아님).
        """
        if not coverage:
            return CriteriaMatchResult(matched=0, unmatched=0, unmatched_codes=())

        from sqlalchemy import update

        from whymath_backend.db.models.achievement_standard import (
            AchievementStandard as AchievementStandardORM,
        )

        known_pairs = self._load_known_pairs()
        matched = 0
        unmatched_codes: list[str] = []

        with self._get_engine().begin() as conn:
            for official_code, criteria_codes in coverage.items():
                if (curriculum_revision, official_code) not in known_pairs:
                    unmatched_codes.append(official_code)
                    continue
                stmt = (
                    update(AchievementStandardORM)
                    .where(
                        AchievementStandardORM.curriculum_revision == curriculum_revision,
                        AchievementStandardORM.official_code == official_code,
                    )
                    .values(evaluation_criteria_codes=criteria_codes)
                )
                conn.execute(stmt)
                matched += 1

        if unmatched_codes:
            # 조용한 스킵 금지(CLAUDE.md "작동한 비율" 원칙) — 개수·표본을 로그에 남긴다.
            logger.warning(
                "평가준거 코드 매칭 실패 %d건(curriculum_revision=%s) — official_code가 그 "
                "개정으로 적재돼 있지 않거나 코드 표기 체계가 다를 수 있음(데이터 카드 §4): %s",
                len(unmatched_codes),
                curriculum_revision,
                unmatched_codes,
            )

        return CriteriaMatchResult(
            matched=matched,
            unmatched=len(unmatched_codes),
            unmatched_codes=tuple(unmatched_codes),
        )


# ──────────────────────────────────────────────────────────────────────────
# ② AchievementLevelUnitStore — (school_level, subject, unit) 자연키 멱등 upsert
# ──────────────────────────────────────────────────────────────────────────
class AchievementLevelUnitStore:
    """단원 단위 성취수준 등급 커버리지 → `achievement_level_unit` 멱등 upsert(sync).

    자연 유일키 `(school_level, subject, unit)` 충돌 시 `DO UPDATE`로 `levels`·`source_document`만
    갱신하고 **unit_id(UUID PK)는 SET하지 않아 보존**한다(`concept_standard_link`의 link_id 보존
    패턴 미러). 입력 내 같은 자연키 중복은 *마지막 우선* dedup(실측: 코퍼스 자체에 3건 존재 —
    같은 값이라 무손실이지만 다른 값이어도 안전하도록 dedup은 항상 수행).
    """

    def __init__(self, *, engine: Engine | None = None, settings: Settings | None = None) -> None:
        self._engine = engine
        self._settings = settings

    @property
    def _resolved_settings(self) -> Settings:
        """설정 지연 해석 — 주입 우선, 없으면 캐시된 전역 Settings(standard_loader 패턴)."""
        if self._settings is None:
            self._settings = get_settings()
        return self._settings

    def _get_engine(self) -> Engine:
        """sync 엔진 지연 해석 — 주입 우선, 없으면 슬3 빌더로 생성·캐시(신규 seam 0)."""
        if self._engine is None:
            self._engine = _build_sync_engine(self._resolved_settings)
        return self._engine

    def populate(self, units: Sequence[AchievementLevelUnit]) -> int:
        """단원 등급 schema 모델들을 `achievement_level_unit`에 멱등 upsert. 반환=적재 행 수(dedup).

        ① (school_level, subject, unit) 기준 *마지막 우선* dedup → ② 각 행을
        `ON CONFLICT(school_level, subject, unit) DO UPDATE`로 적재(levels·source_document
        갱신·unit_id는 SET 안 함·보존). 입력 빈 0.
        """
        if not units:
            return 0

        from sqlalchemy.dialects.postgresql import insert as pg_insert

        from whymath_backend.db.models.achievement_level_unit import (
            AchievementLevelUnit as AchievementLevelUnitORM,
        )

        # 자연 유일키 기준 dedup(마지막 우선) — 단일 배치 ON CONFLICT 중복행 오류 방지.
        by_key: dict[tuple[str, str, str], AchievementLevelUnit] = {
            (u.school_level, u.subject, u.unit): u for u in units
        }
        deduped = list(by_key.values())

        with self._get_engine().begin() as conn:
            for unit in deduped:
                stmt = pg_insert(AchievementLevelUnitORM).values(
                    school_level=unit.school_level,
                    subject=unit.subject,
                    unit=unit.unit,
                    levels=unit.levels,
                    source_document=unit.source_document,
                )
                # 자연키 충돌 시 levels·source_document만 갱신 — unit_id(PK) 미-SET(보존·멱등).
                stmt = stmt.on_conflict_do_update(
                    index_elements=[
                        AchievementLevelUnitORM.school_level,
                        AchievementLevelUnitORM.subject,
                        AchievementLevelUnitORM.unit,
                    ],
                    set_={
                        "levels": stmt.excluded.levels,
                        "source_document": stmt.excluded.source_document,
                    },
                )
                conn.execute(stmt)
        return len(deduped)


# ──────────────────────────────────────────────────────────────────────────
# 공개 진입점 — 두 store를 조합해 코퍼스 1건을 전부 적재
# ──────────────────────────────────────────────────────────────────────────
def load_achievement_criteria(
    source: list[dict[str, Any]] | Path,
    *,
    engine: Engine | None = None,
    settings: Settings | None = None,
    criteria_store: CriteriaCoverageStore | None = None,
    level_store: AchievementLevelUnitStore | None = None,
    curriculum_revision: str = DEFAULT_CURRICULUM_REVISION,
    source_document: str | None = DEFAULT_SOURCE_DOCUMENT,
) -> CriteriaLoadResult:
    """`achievement_criteria_v1` 코퍼스(list|Path) → 평가준거 코드 매칭 + 단원 등급 적재(둘 다).

    ① `standard_criteria_coverage`를 평탄화해 `CriteriaCoverageStore.apply`로 기존
    `achievement_standard` 행을 UPDATE(매칭/미매칭 정직 계상) ② `achievement_levels_by_unit`을
    평탄화해 `AchievementLevelUnitStore.populate`로 멱등 upsert. 두 축은 서로 독립이라 한쪽이
    0건이어도 다른 쪽은 정상 진행한다(모듈 docstring — 강제 결합 없음).

    Raises:
        FileNotFoundError: source가 Path인데 파일 부재.
        TypeError: source가 list·Path가 아니거나(또는 Path 내용이 배열이 아님).
        pydantic.ValidationError: 코퍼스 행이 `AchievementLevelUnit` schema 형식을 위반.
    """
    records = _as_records(source)
    coverage = _extract_coverage(records)
    units = _extract_level_units(records, source_document=source_document)

    resolved_settings = settings if settings is not None else get_settings()
    c_store = (
        criteria_store
        if criteria_store is not None
        else CriteriaCoverageStore(engine=engine, settings=resolved_settings)
    )
    l_store = (
        level_store
        if level_store is not None
        else AchievementLevelUnitStore(engine=engine, settings=resolved_settings)
    )

    match_result = c_store.apply(coverage, curriculum_revision=curriculum_revision)
    level_count = l_store.populate(units)
    return CriteriaLoadResult(criteria=match_result, level_units_loaded=level_count)


# ──────────────────────────────────────────────────────────────────────────
# CLI — `python -m whymath_backend.l1.standards.criteria_loader` (populate.py 골격 미러)
# ──────────────────────────────────────────────────────────────────────────
_DEFAULT_CORPUS = Path("data/corpus/achievement_criteria_v1/achievement_criteria.json")


def main(argv: list[str] | None = None) -> int:
    """achievement_criteria_v1 코퍼스 → backend 적재 CLI 본체. 반환은 프로세스 종료 코드.

    적재 로직 0(얇은 래퍼) — `load_achievement_criteria`가 파싱·매칭·upsert를 전부 담당하고
    본 함수는 경로 결선·실행·stdout 보고만 한다(populate.py 동일 골격). 매칭 실패는 exit 0으로
    가리지 않고 표준출력에 개수·목록을 보고한다(조용한 성공 위장 금지).
    """
    import argparse

    parser = argparse.ArgumentParser(
        prog="whymath-criteria-populate",
        description=(
            "achievement_criteria_v1 코퍼스 → backend achievement_standard."
            "evaluation_criteria_codes 매칭 UPDATE + achievement_level_unit 멱등 적재."
        ),
    )
    parser.add_argument(
        "--corpus",
        type=Path,
        default=_DEFAULT_CORPUS,
        help=f"achievement_criteria_v1 코퍼스 JSON 경로(기본 {_DEFAULT_CORPUS}).",
    )
    parser.add_argument(
        "--curriculum-revision",
        default=DEFAULT_CURRICULUM_REVISION,
        help=f"평가준거 코드 매칭 대조 개정(기본 '{DEFAULT_CURRICULUM_REVISION}').",
    )
    args = parser.parse_args(argv)

    corpus_path: Path = args.corpus
    if not corpus_path.exists():
        print(f"achievement_criteria_v1 코퍼스 없음: {corpus_path}")
        return 2

    result = load_achievement_criteria(corpus_path, curriculum_revision=args.curriculum_revision)
    print(
        f"평가준거 코드 매칭: {result.criteria.matched}건 매칭·{result.criteria.unmatched}건 "
        f"미매칭(curriculum_revision={args.curriculum_revision}). "
        f"단원별 성취수준 적재: {result.level_units_loaded}건 (corpus={corpus_path})."
    )
    if result.criteria.unmatched_codes:
        print(f"미매칭 official_code 목록: {', '.join(result.criteria.unmatched_codes)}")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI 진입
    raise SystemExit(main())


__all__ = [
    "DEFAULT_CURRICULUM_REVISION",
    "DEFAULT_SOURCE_DOCUMENT",
    "AchievementLevelUnitStore",
    "CriteriaCoverageStore",
    "CriteriaLoadResult",
    "CriteriaMatchResult",
    "load_achievement_criteria",
    "main",
]
