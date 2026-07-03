"""임베딩 namespace 분리 불변식 동결 — pgvector 타입별 테이블 격리 (⑥ retrieval 오염).

math_dsl_risk_register.md ⑥(retrieval indexing). 처방 1순위 "concept/misconception/example
논리 namespace 분리"는 현 3타입에 대해 **테이블-당-타입**으로 *이미 충족*돼 있다 — 각 임베딩
(concept/misconception/atom)이 별도 물리 테이블에 살아 검색 쿼리의 FROM이 한 타입만 본다
(cross-type 오염 구조적 불가). 이 가드는 그 격리를 *동결*한다:

  (a) pgvector 벡터 컬럼 테이블 집합을 **등록부와 대조** — 새 임베딩 타입(예 example 문제/풀이
      인덱스)이 반드시 *자기 테이블*로 들어오게(한 테이블에 섞이지 않게) 하고, 추가 시 등록부를
      의식적으로 갱신하게 강제(조용한 namespace 병합·오염 회귀 차단).
  (b) 각 임베딩 테이블이 정확히 **벡터 1개·단일 PK**임을 못 박는다 — namespace는 *테이블*이 쥐며
      행 discriminator(type 컬럼)로 섞지 않는다.

⚠️ ⑥의 "FP 45.5% 방향맹"은 cross-type이 *아니라* misconception 임베딩 공간 *내부*의 방향·부정·
등치 맹점이다(`l4/misconception/semantic/matcher.py:14-18`) — hybrid fusion/judge(⑥ 2순위·후속)
몫이지 이 namespace 가드가 푸는 문제가 아니다. hermetic(Base.metadata introspection·DB 불요).
"""

from __future__ import annotations

from pgvector.sqlalchemy import Vector

import whymath_backend.db.models  # noqa: F401  (전 모델 import → Base.metadata 완비)
from whymath_backend.db.base import Base

# 임베딩 namespace 등록부(동결) — 각 타입 = 자기 테이블. 새 임베딩(example 등) 추가 시 갱신 강제.
_EMBEDDING_NAMESPACE_TABLES = frozenset(
    {"concept_embedding", "misconception_embedding", "atom_embedding"}
)


def _vector_tables() -> set[str]:
    """Base.metadata에서 pgvector `Vector` 컬럼을 가진 테이블 이름 집합."""
    return {
        name
        for name, table in Base.metadata.tables.items()
        if any(isinstance(col.type, Vector) for col in table.columns)
    }


class TestEmbeddingNamespaceGovernance:
    def test_vector_tables_match_registry(self) -> None:
        """벡터 컬럼 테이블 == 등록부 — 새 임베딩 타입은 자기 테이블로(섞임 금지·등록부 갱신 강제).

        실패 시: 새 임베딩 테이블은 등록부에 등록(자기 namespace 확보)하고, 기존 테이블에 다른
        타입 벡터를 얹었다면 *별 테이블*로 분리하라(⑥ namespace 격리·의미 오염 차단).
        """
        assert _vector_tables() == set(_EMBEDDING_NAMESPACE_TABLES)

    def test_each_embedding_table_single_vector_and_single_pk(self) -> None:
        """각 임베딩 테이블은 벡터 1개·단일 PK — namespace=테이블(행 discriminator 아님)."""
        for name in sorted(_EMBEDDING_NAMESPACE_TABLES):
            table = Base.metadata.tables[name]
            vec_cols = [c for c in table.columns if isinstance(c.type, Vector)]
            assert len(vec_cols) == 1, f"{name}: 벡터 컬럼 {len(vec_cols)}개(기대 1)"
            assert len(table.primary_key.columns) == 1, f"{name}: 복합 PK(기대 단일)"
