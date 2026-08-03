"""study `k_type` 값 전달 동결 — str-mixin Enum 맹글링 재발 방지.

정본: `docs/architecture/04e_pedagogy_strategy_catalog.md` §4. grade_band 생산자 배선 테스트는
PED-08(coach 실행용 축 수렴)이 `_build_signals`를 `l4/pedagogy/signal_assembly.py`로 추출하며
`tests/backend/l4/pedagogy/test_signal_assembly.py`로 이관했다(회귀 0 — 동일 어서션).

k_type 소스 스캔 동결: `str(objective.k_type)`은 str-mixin Enum이라 "KnowledgeType.CONCEPT"로
맹글링된다 — 2026-07-29 실측: ① 팩 조회(`get_pack`) 상시 미스 ② `evidence_event.k_type`
native enum 플러시가 LookupError로 실패(/study 500) ③ PED-06 카탈로그 필터 k_type 축 상시
공집합. 수정(`.value`)의 회귀를 소스 스캔으로 동결한다(`test_render_governance.py` 소스 스캔
선례 — 엔드포인트 hermetic 클라이언트 없이 가장 싼 동결).

hermetic: DB 0.
"""

from __future__ import annotations

import inspect

from whymath_backend.api import study


class TestKTypeValueFrozen:
    """k_type 맹글링 회귀 동결 — `str(enum)`이 아니라 `.value`가 흐른다(모듈 docstring 사고)."""

    def test_source_has_no_str_mangled_k_type(self) -> None:
        source = inspect.getsource(study)
        assert "str(objective.k_type)" not in source, (
            "str(objective.k_type)은 'KnowledgeType.CONCEPT'로 맹글링된다 — "
            "팩 조회 미스·native enum 플러시 실패·카탈로그 필터 공집합(2026-07-29 실측). "
            ".value를 쓰라."
        )
        assert "objective.k_type.value" in source

    def test_mangling_premise_still_holds(self) -> None:
        # 이 동결의 전제 실측 — str-mixin Enum의 str()은 값이 아니다(전제가 바뀌면 동결 재검토).
        from whymath_backend.schema.enums import KnowledgeType

        assert str(KnowledgeType.CONCEPT) != KnowledgeType.CONCEPT.value
        assert KnowledgeType.CONCEPT.value == "CONCEPT"
