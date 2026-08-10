"""pedagogy_pack YAML↔DB 정합 감사 (PED-16②) — reader 0 테이블이 조용히 갈라지는지 상시 감시.

배경: `pedagogy_pack` DB 테이블은 `PedagogyPackStore`(`l1/pedagogy/pack_loader.py`)가 쓰기만
하고, 런타임 실 소비자(`l4/pedagogy/pack_registry.get_pack`)는 이 테이블을 전혀 읽지 않는다 —
YAML을 직접 읽는다(DB 무접근, 순수 파일 로드·모듈 경계는 `l4/pedagogy/__init__.py` docstring).
즉 진실원은 YAML(→`schema.pedagogy_pack.PedagogyPack`)이고, DB 테이블(`PedagogyPackORM`)은
*이중 정본*이다 — 아무도 읽지 않으므로 둘이 갈라져도 아무 테스트도 실패하지 않을 위험이 있다
(OPS-22 "일반 테이블 dead write 미감사" 사각의 실측 사례). PED-16이 이 위험을 "제거"가 아니라
"유지+감사"로 판정한 이유(blast radius 실측 — `test_pack_loader.py`의 SQL 생성 테스트 7건 +
`test_e2e_pedagogy_pilot_integration.py` step① 파괴가 이 태스크 범위 대비 과도)는
`l1/pedagogy/pack_loader.py` 모듈 docstring 참조.

이 테스트는 하드코딩 리터럴과 대조(freeze)하지 않는다 — `schema.PedagogyPack.model_fields`와
`PedagogyPackORM`의 실제 SQLAlchemy 컬럼셋을 *서로* 대조한다(제3의 스냅샷 없음). 어느 한쪽만
바뀌면 즉시 RED — 둘이 함께 바뀌어야 GREEN(자연 동기화 강제).
"""

from __future__ import annotations

import sqlalchemy as sa

from whymath_backend.db.models.pedagogy_dsl import PedagogyPack as PedagogyPackORM
from whymath_backend.schema.pedagogy_pack import PedagogyPack


def _orm_column_keys() -> set[str]:
    """`PedagogyPackORM`의 실제 매핑 컬럼 키 집합(하드코딩 아님 — mapper 실시간 introspection)."""
    return {col.key for col in sa.inspect(PedagogyPackORM).mapper.column_attrs}


def _schema_field_names() -> set[str]:
    """`schema.PedagogyPack`의 실제 Pydantic 필드명 집합(하드코딩 아님)."""
    return set(PedagogyPack.model_fields)


class TestPedagogyPackYamlDbParity:
    def test_schema_fields_equal_orm_columns(self) -> None:
        """YAML 시더 계약(schema)과 DB 컬럼(ORM)이 정확히 같은 필드셋을 가진다.

        이 등식이 깨지는 두 방향의 실제 위험:
          - schema에만 있는 필드 → `PedagogyPackStore.populate`가 `all_keys`(ORM 기준)로만
            `payload`를 추리므로, 그 필드는 **조용히 DB에 실리지 않는다**(예외 없음 — 침묵 실패).
          - ORM에만 있는 컬럼 → `payload[k]`가 `KeyError`를 내며 시더가 즉시 죽는다(요란한 실패라
            운영에선 바로 드러나지만, 이 테스트가 더 빨리·더 명확한 메시지로 잡아준다).
        """
        orm_keys = _orm_column_keys()
        schema_keys = _schema_field_names()
        only_in_schema = schema_keys - orm_keys
        only_in_orm = orm_keys - schema_keys
        assert (
            not only_in_schema
        ), f"schema.PedagogyPack에만 있고 ORM에 없는 필드(DB에 조용히 안 실림): {only_in_schema}"
        assert (
            not only_in_orm
        ), f"PedagogyPackORM에만 있고 schema에 없는 컬럼(시더가 KeyError로 죽음): {only_in_orm}"

    def test_orm_k_type_is_the_declared_primary_key(self) -> None:
        """PK 축(k_type)이 여전히 schema의 PK 개념 필드와 일치 — 멱등 upsert 충돌 키 정합."""
        pk_cols = {c.key for c in sa.inspect(PedagogyPackORM).mapper.primary_key}
        assert pk_cols == {"k_type"}
        assert "k_type" in PedagogyPack.model_fields
