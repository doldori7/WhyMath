"""오개념 카탈로그 정합성 단위테스트 — doc 정본 30종(Phase 1 목표).

스코프 정직(False-attribute 금기): doc에 명시·상세화된 30종만 등록(기존 22 + §5.4
교차검증 후보 8: 대수+2·기하+1·확률통계+1·함수+2·미적분+2), 미상세 항목 추정 작성 없음.
"""

from __future__ import annotations

import re

from whymath_backend.l4.misconception import (
    CATALOG,
    CATALOG_BY_ID,
    Misconception,
)


class TestCatalogShape:
    def test_thirty_entries_doc_explicit_only(self) -> None:
        # doc 명시·상세화: 대수 9 + 기하 4 + 확률통계 4 + 함수 3
        #                 + 미적분 5 + 수열 2 + 삼각함수 2 + 벡터 1 = 30 (Phase 1 목표)
        assert len(CATALOG) == 30

    def test_all_ids_unique(self) -> None:
        ids = [m.id for m in CATALOG]
        assert len(ids) == len(set(ids))

    def test_catalog_by_id_dict_consistent(self) -> None:
        assert set(CATALOG_BY_ID.keys()) == {m.id for m in CATALOG}
        for m in CATALOG:
            assert CATALOG_BY_ID[m.id] is m


class TestCanonicalIdsFromDoc:
    """doc L24-50에 *명시*된 ID가 모두 존재 — 정본 정합."""

    def test_algebra_nine(self) -> None:
        # 기존 7 + 슬 §5.4 추가 2(discriminant·root-loss)
        algebra_ids = {
            "distribution-over-power",
            "sign-flip-in-inequality",
            "division-by-zero",
            "square-root-positivity",
            "exponent-zero",
            "fraction-cancellation",
            "log-distribution",
            "discriminant-negative-no-real-root",
            "root-loss-by-dividing",
        }
        assert algebra_ids.issubset(CATALOG_BY_ID.keys())
        for mid in ("discriminant-negative-no-real-root", "root-loss-by-dividing"):
            assert CATALOG_BY_ID[mid].domain == "대수"

    def test_geometry_four(self) -> None:
        # 기존 3 + 슬 §5.4 추가 1(circle-radius-squared)
        for mid in (
            "angle-sum-non-triangle",
            "similarity-vs-congruence",
            "area-perimeter-confusion",
            "circle-radius-squared",
        ):
            assert mid in CATALOG_BY_ID
        assert CATALOG_BY_ID["circle-radius-squared"].domain == "기하"

    def test_probstat_four(self) -> None:
        # 기존 3 + 슬 §5.4 추가 1(mutually-exclusive-implies-independent)
        for mid in (
            "gambler-fallacy",
            "prosecutor-fallacy",
            "mean-vs-median",
            "mutually-exclusive-implies-independent",
        ):
            assert mid in CATALOG_BY_ID
        assert CATALOG_BY_ID["mutually-exclusive-implies-independent"].domain == "확률통계"

    def test_function_three(self) -> None:
        # 기존 1 + 슬 §5.4 추가 2(composite·translation)
        for mid in (
            "invertibility-without-1-1",
            "composite-function-commutes",
            "translation-sign-flip",
        ):
            assert mid in CATALOG_BY_ID
            assert CATALOG_BY_ID[mid].domain == "함수"


class TestSuneungCanonicalIds:
    """doc #16-23에 *명시·상세화*된 수능 핵심 오개념 — domain별 정합."""

    def test_calculus_five(self) -> None:
        # 기존 3 + 슬 §5.4 추가 2(continuity·critical-point).
        # continuity-implies-differentiability는 doc 함수 슬롯 #15에 상세되나
        # domain은 미적분([H:12미적Ⅰ02-02] 정착)이라 본 도메인 집합에 포함.
        for mid in (
            "chain-rule-inner-derivative-omitted",
            "product-rule-naive",
            "limit-equals-function-value",
            "continuity-implies-differentiability",
            "critical-point-implies-extremum",
        ):
            assert mid in CATALOG_BY_ID
            assert CATALOG_BY_ID[mid].domain == "미적분"

    def test_sequence_two(self) -> None:
        for mid in (
            "geometric-series-always-converges",
            "term-to-zero-implies-convergence",
        ):
            assert mid in CATALOG_BY_ID
            assert CATALOG_BY_ID[mid].domain == "수열"

    def test_trig_two(self) -> None:
        for mid in ("sine-distributes-over-sum", "period-of-scaled-sine"):
            assert mid in CATALOG_BY_ID
            assert CATALOG_BY_ID[mid].domain == "삼각함수"

    def test_vector_one(self) -> None:
        assert CATALOG_BY_ID["dot-product-is-vector"].domain == "벡터"


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
        valid = {
            "대수",
            "기하",
            "확률통계",
            "함수",
            "미적분",
            "수열",
            "삼각함수",
            "벡터",
        }
        for m in CATALOG:
            assert m.domain in valid


class TestNameClarity:
    """`name_kr`은 짧고 부정 표현 없음(직접 라벨링 회피 — doc 절대 금지 §)."""

    def test_no_negative_labeling_words(self) -> None:
        banned = ("바보", "틀린", "잘못", "실수")
        for m in CATALOG:
            assert not any(b in m.name_kr for b in banned), m.id


class TestRegexSignals:
    """v1.2 `regex_signals` — 선택 필드(기본 빈 튜플)·시연 3종·전부 컴파일 가능(슬 102)."""

    _DEMO_IDS = {
        "distribution-over-power",
        "square-root-positivity",
        "fraction-cancellation",
    }

    def test_field_defaults_empty_and_is_tuple(self) -> None:
        # 미설정 항목은 빈 튜플(하위호환 — substring 동작 불변)
        for m in CATALOG:
            assert isinstance(m.regex_signals, tuple)
            if m.id not in self._DEMO_IDS:
                assert m.regex_signals == (), m.id

    def test_demo_entries_have_regex(self) -> None:
        for mid in self._DEMO_IDS:
            assert CATALOG_BY_ID[mid].regex_signals, mid

    def test_all_regex_signals_compile(self) -> None:
        # 카탈로그의 모든 정규식은 컴파일 가능해야(런타임 re.error 회귀 가드)
        for m in CATALOG:
            for pat in m.regex_signals:
                re.compile(pat)  # 실패 시 re.error → 테스트 실패


class TestExposedSurface:
    def test_misconception_typed_as_basemodel(self) -> None:
        for m in CATALOG:
            assert isinstance(m, Misconception)
