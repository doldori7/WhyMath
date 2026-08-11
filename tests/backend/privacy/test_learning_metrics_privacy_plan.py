"""롤업 적재 3테이블의 파기·반출·보존 정합 동결 (COLLAB-03 acceptance ⑥) — hermetic.

`l2.learning_metrics_rollup`이 세 시계열 테이블에 *적재를 시작*했다. 적재가 시작된 이상
개인정보 배관에 실제로 걸려 있는지가 검증 대상이 된다 — 배관 등재는 이미 돼 있었으나
공급원이 없어 **한 번도 발동한 적 없는 상태**였다(그래서 어긋나도 아무도 몰랐다).

이 모듈은 세 테이블의 배관 소속을 기계로 동결한다:

  · `daily_learning_metrics`·`user_behavior_metrics` — 사용자 축 PII다.
    삭제권(`_ERASURE_PLAN`) ○ · 본인 반출(`_EXPORT_PLAN`) ○ · 보존 파기(`_RETENTION_PLAN`) ○
  · `problem_solve_time_distribution` — `user_id`가 없는 *교차 사용자 집계*(비-PII)다.
    삭제권 ✕ · 반출 ✕(`export.py` 모듈 docstring의 기존 결정) · 보존 파기 ○(COLLAB-03에서 편입 —
    적재가 시작돼 상한 없이 증가하므로 「무기한 보존 금지」는 PII 여부와 무관하게 적용된다).

변별력: 각 단언은 *반대 방향*으로 어겼을 때 빨개진다 — 예컨대 누군가 편의를 위해 풀이 시간
분포를 반출에 끼워 넣으면(비-PII를 개인 반출에 섞음) 즉시 red다.

보존기간 숫자 자체는 `Settings.pii_retention_years`(기본 3년)를 그대로 상속하며 이 태스크는
새 숫자를 만들지 않는다 — 그 사실도 아래에서 동결한다.
"""

from __future__ import annotations

from whymath_backend.config import Settings
from whymath_backend.privacy.erasure import _ERASURE_PLAN
from whymath_backend.privacy.export import _EXPORT_PLAN
from whymath_backend.privacy.retention import _RETENTION_PLAN

_DAILY = "daily_learning_metrics"
_BEHAVIOR = "user_behavior_metrics"
_SOLVE_TIME = "problem_solve_time_distribution"


def _erasure_tables() -> set[str]:
    return {model.__tablename__ for model, _ in _ERASURE_PLAN}


def _export_tables() -> set[str]:
    return {model.__tablename__ for model, *_ in _EXPORT_PLAN}


def _retention_tables() -> set[str]:
    return {model.__tablename__ for model, _ in _RETENTION_PLAN}


class TestUserAxisTables:
    """사용자 축 2테이블 — 삭제권·반출·보존 셋 다 걸려야 한다."""

    def test_in_erasure_plan(self) -> None:
        tables = _erasure_tables()
        assert _DAILY in tables, "계정 삭제 시 일별 학습 지표가 남는다(GDPR 삭제권 위반)"
        assert _BEHAVIOR in tables, "계정 삭제 시 행동 지표가 남는다(GDPR 삭제권 위반)"

    def test_in_export_plan(self) -> None:
        tables = _export_tables()
        assert _DAILY in tables, "본인 반출(열람·이동권)에 일별 학습 지표가 빠졌다"
        assert _BEHAVIOR in tables, "본인 반출에 행동 지표가 빠졌다"

    def test_in_retention_plan(self) -> None:
        tables = _retention_tables()
        assert _DAILY in tables, "일별 학습 지표가 무기한 보존된다"
        assert _BEHAVIOR in tables, "행동 지표가 무기한 보존된다"


class TestCrossUserAggregateTable:
    """풀이 시간 분포 — 비-PII라 삭제권·반출은 ✕, 그러나 보존 파기는 ○(COLLAB-03 확정)."""

    def test_not_in_erasure_plan(self) -> None:
        """`user_id`가 없어 개인 삭제 대상이 아니다 — 넣으면 지울 키가 없어 오작동한다."""
        assert _SOLVE_TIME not in _erasure_tables()

    def test_not_in_export_plan(self) -> None:
        """교차 사용자 집계를 개인 반출에 섞으면 *타인 통계*를 함께 내주는 셈이다."""
        assert _SOLVE_TIME not in _export_tables()

    def test_in_retention_plan(self) -> None:
        """COLLAB-03에서 편입 — 매일 새 measured_at으로 쌓이므로 파기 경로가 없으면 무한 증가."""
        assert (
            _SOLVE_TIME in _retention_tables()
        ), "풀이 시간 분포에 보존 파기 경로가 없다 — 롤업이 매일 적재하므로 상한 없이 증가한다"

    def test_retention_column_is_measured_at(self) -> None:
        """파기 기준 컬럼이 실제로 존재하는 타임스탬프인지(오타면 런타임에 터진다)."""
        column = next(col for model, col in _RETENTION_PLAN if model.__tablename__ == _SOLVE_TIME)
        assert column == "measured_at"


class TestRetentionPeriodInherited:
    def test_no_new_retention_number_introduced(self) -> None:
        """보존기간은 기존 `pii_retention_years`(기본 3년) 상속 — 태스크 전용 숫자 없음."""
        assert Settings(jwt_secret_key="x" * 32).pii_retention_years == 3
