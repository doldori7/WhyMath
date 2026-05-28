"""ORM 모델 패키지 — 모든 테이블을 import해 `Base.metadata`에 등록한다.

alembic autogenerate(env.py의 `target_metadata = Base.metadata`)가 테이블을 인식하려면
모델 클래스가 *import되어 메타데이터에 등록*되어 있어야 한다. env.py가
`import whymath_backend.db.models`만 하면 이 `__init__`이 아래 모델들을 끌어와 등록한다.

PoC 범위: 도메인1 Problem(Problem·ProblemStep·ProblemRelation)만. 후속 슬라이스가
다른 도메인 ORM을 추가하면 여기 import 한 줄로 합류시킨다(alembic이 자동 인식).
"""

from __future__ import annotations

from whymath_backend.db.models.problem import (
    Problem,
    ProblemRelation,
    ProblemStep,
)

__all__ = ["Problem", "ProblemStep", "ProblemRelation"]
