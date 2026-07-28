"""JSONB `none_as_null` 전수 거버넌스 — SEC-06 (hermetic).

**왜 규칙인가**: SQLAlchemy JSONB의 기본값(`none_as_null=False`)은 Python `None`을 SQL NULL이
아니라 **JSON 스칼라 `null`** 로 저장한다. 그러면 "값 없음"인 행이 `IS NOT NULL`을 만족해
두 가지가 동시에 깨진다:

  ① **술어 오판** — `<col> IS NOT NULL`을 "값 있음"으로 쓰는 모든 질의가 거짓양성을 낸다.
     SEC-04의 백필 굶주림(진짜 평문 행이 LIMIT 창 밖으로 밀려 영영 미처리)과 배포 실측
     거짓경보가 정확히 이 원인이었다.
  ② **NOT NULL 무력화** — `nullable=False` 컬럼도 JSON `null`은 통과시킨다(실 PG 실증).
     "필수"라고 선언한 필드가 조용히 비어 있을 수 있다.

한 컬럼만 고치면 다음 모델에서 재발한다. 그래서 **전수**를 기계로 동결한다 — 신규 JSONB
컬럼이 선언을 빠뜨리면 여기서 실패한다.

의도적 예외가 생기면 `_ALLOWED_JSON_NULL`에 **사유와 함께** 등재한다. 빈 집합이 기본이며,
등재는 "JSON null과 SQL NULL을 실제로 구분해야 하는" 경우로 한정한다.
"""

from __future__ import annotations

import importlib
import pkgutil

from sqlalchemy.dialects.postgresql import JSONB

import whymath_backend.db.models as models_pkg
from whymath_backend.db.base import Base

# (테이블, 컬럼) → 사유. JSON null과 SQL NULL의 구분이 *의미상 필요한* 컬럼만 등재한다.
_ALLOWED_JSON_NULL: dict[tuple[str, str], str] = {}


def _load_all_models() -> None:
    """모든 모델 모듈을 적재해 `Base.metadata`를 완성한다(부분 적재면 점검이 새는다)."""
    for module in pkgutil.iter_modules(models_pkg.__path__):
        importlib.import_module(f"whymath_backend.db.models.{module.name}")


def _jsonb_columns() -> list[tuple[str, str, bool]]:
    """(테이블, 컬럼, none_as_null) — 선언 문자열이 아니라 *실제 ORM 메타데이터*를 본다."""
    _load_all_models()
    return [
        (table.name, column.name, bool(column.type.none_as_null))
        for table in Base.metadata.sorted_tables
        for column in table.columns
        if isinstance(column.type, JSONB)
    ]


class TestAllJsonbColumnsDeclareNoneAsNull:
    def test_no_column_stores_python_none_as_json_null(self) -> None:
        """전 JSONB 컬럼이 `none_as_null=True`여야 한다 — 누락은 SEC-04 유형 결함의 씨앗이다."""
        offenders = [
            f"{table}.{column}"
            for table, column, none_as_null in _jsonb_columns()
            if not none_as_null and (table, column) not in _ALLOWED_JSON_NULL
        ]
        assert not offenders, (
            "다음 JSONB 컬럼이 Python None을 JSON null로 저장한다 — "
            f"`JSONB(none_as_null=True)`로 선언하세요: {offenders}"
        )

    def test_survey_is_not_empty(self) -> None:
        """**변별력의 전제** — 컬럼을 하나도 못 찾으면 위 테스트는 공허하게 통과한다.

        모델 적재가 깨지거나 탐색이 어긋나면 offenders가 항상 빈 리스트가 되어 '통과'로
        보인다. 실제로 점검 대상이 존재함을 함께 못 박는다.
        """
        assert len(_jsonb_columns()) >= 40

    def test_allowlist_entries_are_real_columns(self) -> None:
        """허용목록이 실재하지 않는 컬럼을 가리키면 방치된 예외다 — 오타·삭제 잔재를 막는다."""
        known = {(table, column) for table, column, _ in _jsonb_columns()}
        stale = [entry for entry in _ALLOWED_JSON_NULL if entry not in known]
        assert not stale, f"허용목록에 실재하지 않는 컬럼이 있습니다: {stale}"

    def test_allowlist_entries_have_reasons(self) -> None:
        """사유 없는 예외는 '왜 예외인지' 미래 세션이 알 수 없다 — 빈 사유를 금지한다."""
        blank = [entry for entry, reason in _ALLOWED_JSON_NULL.items() if not reason.strip()]
        assert not blank, f"사유가 빈 허용목록 항목: {blank}"
