"""개념 콘텐츠 런타임 조회(async) — code PK 단건.

`l1/concept_visualization/overlay.py::get_visualizability`와 같은 규약이다: 같은 계열의 code-PK
projection 테이블에서 **런타임 조회는 async**, **시드 적재는 sync**(`projection.py`)로 나눈다.

이 모듈이 생기기 전까지 `concept_content`에는 *쓰기 경로만* 있었다(코퍼스 적재). CACHE-01의 공급
경로가 첫 읽기 소비자이며, L3 렌더(`l3/render/dsl.py::from_concept_content`)가 ORM 세션에 묶이지
않도록 **조회는 여기(L1)에서 하고 행만 넘긴다** — 렌더 계층의 db-free 불변식을 지키는 배치다.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from whymath_backend.db.models.concept_content import ConceptContent


async def get_concept_content(session: AsyncSession, code: str) -> ConceptContent | None:
    """개념 code로 콘텐츠 행을 조회한다(런타임·async). 행 부재→None(미적재 개념).

    PK(code) 단건 조회라 `session.get`으로 충분하다(overlay.py 선례). 호출자는 None을 "이 개념은
    아직 콘텐츠가 없다"로 해석해 생성 경로로 폴백한다 — 예외를 던지지 않는다.
    """
    return await session.get(ConceptContent, code)


__all__ = ["get_concept_content"]
