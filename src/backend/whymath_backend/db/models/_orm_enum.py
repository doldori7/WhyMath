"""ORM enum 매핑 공유 헬퍼 — `schema/enums.py` str-Enum을 PG native enum으로 잇는다.

이 두 함수는 원래 `models/problem.py`에 있었으나, 도메인 ORM이 6개로 늘면서(problem +
concept·provenance·user·curriculum_entry·textbook_mapping) *모든 모듈이 동일한 enum 매핑
규칙*을 공유해야 하므로 여기로 추출했다(동작 불변 — problem.py는 이제 여기서 import한다).

ENUM 매핑 규칙(중요):
  `schema/enums.py`의 기존 str-Enum을 *재사용*한다. `sa.Enum(..., values_callable=...)`로
  매핑하되 `values_callable=lambda e: [m.value for m in e]`를 *반드시* 둔다 — 멤버명≠값인
  enum이 있어, 이게 없으면 SQLAlchemy가 PostgreSQL enum을 *멤버명*으로 만들어 DDL 값과
  어긋난다. 이 배치에서 실제로 멤버명≠값인 enum:
    - `Curriculum.REVISION_2015 = "2015_REVISION"` (problem 도메인)
    - `CurriculumLicense.KR_NCIC = "KR-NCIC"` 등 5종 (curriculum_entry 도메인 — 하이픈 값은
      Python 식별자로 못 써서 멤버명에 언더스코어, 값에 하이픈)
  PG 타입명은 각 DDL의 `*_enum`명을 그대로 박는다(`name=`).
"""

from __future__ import annotations

from collections.abc import Callable
from enum import Enum

import sqlalchemy as sa


def _enum_values(enum_cls: type[Enum]) -> Callable[[type[Enum]], list[str]]:
    """`sa.Enum`의 `values_callable` 인자 — enum의 *값*(멤버명 아님)으로 PG enum 생성.

    `Curriculum.REVISION_2015 = "2015_REVISION"`·`CurriculumLicense.KR_NCIC = "KR-NCIC"`처럼
    멤버명≠값인 enum 때문에 *필수*다. 이게 없으면 SQLAlchemy가 멤버명('REVISION_2015'·
    'KR_NCIC')으로 PG enum 라벨을 만들어 DDL 값('2015_REVISION'·'KR-NCIC')과 어긋난다.
    SQLAlchemy는 이 콜러블에 enum 클래스를 넘기므로 시그니처는 `(enum_cls) -> list[str]`이다.
    """
    # enum_cls를 닫아(closure) 받지만, SQLAlchemy가 전달하는 인자(동일 클래스)를 그대로
    # 순회해도 결과가 같다. 명시적으로 enum_cls를 순회해 값 리스트를 만든다.
    return lambda _e: [member.value for member in enum_cls]


def _pg_enum(enum_cls: type[Enum], name: str) -> sa.Enum:
    """`schema/enums.py` str-Enum을 PG native enum으로 — values_callable·타입명 고정.

    `name`은 각 도메인 DDL의 `*_enum` 타입명을 그대로 박는다(예: 'source_type_enum').
    """
    return sa.Enum(enum_cls, name=name, values_callable=_enum_values(enum_cls))


__all__ = ["_enum_values", "_pg_enum"]
