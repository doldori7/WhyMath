"""오개념 카탈로그 정합성 단위테스트 — doc 정본 14종.

스코프 정직(False-attribute 금기): doc에 명시된 14종만 등록, 추정 작성 없음.
"""

from __future__ import annotations

from whymath_backend.l4.misconception import (
    CATALOG,
    CATALOG_BY_ID,
    Misconception,
)


class TestCatalogShape:
    def test_fourteen_entries_doc_explicit_only(self) -> None:
        # doc 명시: 대수 7 + 기하 3 + 확률통계 3 + 함수 1 = 14
        assert len(CATALOG) == 14

    def test_all_ids_unique(self) -> None:
        ids = [m.id for m in CATALOG]
        assert len(ids) == len(set(ids))

    def test_catalog_by_id_dict_consistent(self) -> None:
        assert set(CATALOG_BY_ID.keys()) == {m.id for m in CATALOG}
        for m in CATALOG:
            assert CATALOG_BY_ID[m.id] is m


class TestCanonicalIdsFromDoc:
    """doc L24-50에 *명시*된 ID가 모두 존재 — 정본 정합."""

    def test_algebra_seven(self) -> None:
        algebra_ids = {
            "distribution-over-power",
            "sign-flip-in-inequality",
            "division-by-zero",
            "square-root-positivity",
            "exponent-zero",
            "fraction-cancellation",
            "log-distribution",
        }
        assert algebra_ids.issubset(CATALOG_BY_ID.keys())

    def test_geometry_three(self) -> None:
        for mid in (
            "angle-sum-non-triangle",
            "similarity-vs-congruence",
            "area-perimeter-confusion",
        ):
            assert mid in CATALOG_BY_ID

    def test_probstat_three(self) -> None:
        for mid in ("gambler-fallacy", "prosecutor-fallacy", "mean-vs-median"):
            assert mid in CATALOG_BY_ID

    def test_function_one(self) -> None:
        assert "invertibility-without-1-1" in CATALOG_BY_ID


class TestEntryFields:
    def test_every_entry_has_required_fields(self) -> None:
        for m in CATALOG:
            assert m.id
            assert m.name_kr
            assert m.canonical_statement
            assert m.counterexample
            assert m.signals
            assert len(m.signals) >= 1

    def test_immutable_frozen_pydantic(self) -> None:
        # `frozen=True` — catalog 엔트리 수정 차단(런타임 변경 회귀 가드)
        m = CATALOG[0]
        try:
            m.id = "mutated"  # type: ignore[misc]
        except (TypeError, ValueError):
            return  # 예상 — frozen
        raise AssertionError("frozen=True인데 수정됨")

    def test_domain_is_valid_literal(self) -> None:
        valid = {"대수", "기하", "확률통계", "함수"}
        for m in CATALOG:
            assert m.domain in valid


class TestNameClarity:
    """`name_kr`은 짧고 부정 표현 없음(직접 라벨링 회피 — doc 절대 금지 §)."""

    def test_no_negative_labeling_words(self) -> None:
        banned = ("바보", "틀린", "잘못", "실수")
        for m in CATALOG:
            assert not any(b in m.name_kr for b in banned), m.id


class TestExposedSurface:
    def test_misconception_typed_as_basemodel(self) -> None:
        for m in CATALOG:
            assert isinstance(m, Misconception)
