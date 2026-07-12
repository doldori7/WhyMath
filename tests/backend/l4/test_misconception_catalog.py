"""오개념 카탈로그 정합성 단위테스트 — doc 정본 32종(Phase 1 30 + S2-p 2).

스코프 정직(False-attribute 금기): doc에 명시·상세화된 32종만 등록(기존 22 + §5.4
교차검증 후보 8: 대수+2·기하+1·확률통계+1·함수+2·미적분+2 + S2-p 대수 2: 반대 근 선택·
인수 부호 반전), 미상세 항목 추정 작성 없음.
"""

from __future__ import annotations

import re

from whymath_backend.l3.symbolic_equivalence import IdentityVerdict, identity_status
from whymath_backend.l4.misconception import (
    CATALOG,
    CATALOG_BY_ID,
    Misconception,
    diagnose,
)
from whymath_backend.l4.misconception.match_gate import _DEFAULT_CONFIDENCE_FLOOR


class TestCatalogShape:
    def test_thirty_two_entries_doc_explicit_only(self) -> None:
        # doc 명시·상세화: 대수 35 + 기하 4 + 확률통계 4 + 함수 3
        #                 + 미적분 7 + 수열 2 + 삼각함수 2 + 벡터 1 = 58
        #                 (Phase 1 30 + S2-p 2 + 극값 MC 2 + 843 트랜치1~4 각 6)
        assert len(CATALOG) == 58

    def test_all_ids_unique(self) -> None:
        ids = [m.id for m in CATALOG]
        assert len(ids) == len(set(ids))

    def test_catalog_by_id_dict_consistent(self) -> None:
        assert set(CATALOG_BY_ID.keys()) == {m.id for m in CATALOG}
        for m in CATALOG:
            assert CATALOG_BY_ID[m.id] is m


class TestCanonicalIdsFromDoc:
    """doc L24-50에 *명시*된 ID가 모두 존재 — 정본 정합."""

    def test_algebra_seventeen(self) -> None:
        # 기존 7 + 슬 §5.4 추가 2(discriminant·root-loss) + S2-p 추가 2(반대 근·부호 반전)
        # + 843 트랜치1 6(분수덧셈·음수곱·음수빼기·절댓값·제곱근분배·합차공식 혼동)
        # + 843 트랜치2 6(거듭제곱 곱셈/거듭제곱·음수 제곱·분배 뒷항·음수 분배·차의 제곱) = 23
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
            "opposite-root-selected",
            "factor-sign-flip",
            "fraction-addition-naive",
            "negative-times-negative",
            "subtract-negative-sign",
            "absolute-value-keeps-sign",
            "sqrt-distributes-over-sum",
            "difference-of-squares-confused",
            "exponent-product-multiplies",
            "power-of-power-adds",
            "negative-square-precedence",
            "distribute-first-term-only",
            "negative-distribute-sign",
            "square-of-difference-no-cross",
            "midpoint-sum-only",
            "scale-area-linear",
            "negative-even-power-sign",
            "combine-unlike-terms",
            "complete-square-naive",
            "conjugate-product-sum",
            "transpose-no-sign-change",
            "gcd-lcm-confused",
            "decimal-mult-place",
            "mixed-number-mult-whole",
            "remainder-theorem-sign",
            "vieta-sign-error",
        }
        assert algebra_ids.issubset(CATALOG_BY_ID.keys())
        for mid in (
            "discriminant-negative-no-real-root",
            "root-loss-by-dividing",
            "opposite-root-selected",
            "factor-sign-flip",
        ):
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
    """v1.2 `regex_signals` — 선택 필드(기본 빈 튜플)·시연 4종·전부 컴파일 가능(슬 102·후속 확장).

    슬 102 후속 보수적 확장: log-distribution(로그 합 분배·`log(2+3)=log2+log3`)를 추가했다.
    네 종 모두 *거짓 수치 항등식*만 매치하는 disjoint 정규식(명명그룹 역참조·`\\d+` 피연산자)이다.
    """

    _DEMO_IDS = {
        "distribution-over-power",
        "square-root-positivity",
        "fraction-cancellation",
        "log-distribution",
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


class TestCanonicalWrongForm:
    """선택 필드 `canonical_wrong_form` — 거짓 항등식의 *머신 검증* 표현(동치 권위 일원화·감사 §7).

    핵심 불변식: 부여된 (lhs, rhs)는 `identity_status`(SymPy 단일 권위)로 **not_identity**여야
    한다 — 'wrong form이 실제로 틀렸다'를 문자열이 아닌 기호 권위로 못 박는다. 정직 스코프:
    SymPy가 가정 없이 반증 가능한 다항 거짓 항등식에만 부여(정의역 의존·초월·유리식은 미부여).
    """

    # SymPy가 not_identity로 반증 가능한 다항 거짓 항등식만(probe로 확정).
    _AUTHORED_IDS = {"distribution-over-power", "exponent-zero"}

    def test_field_optional_and_typed(self) -> None:
        for m in CATALOG:
            if m.canonical_wrong_form is None:
                continue
            assert isinstance(m.canonical_wrong_form, tuple)
            assert len(m.canonical_wrong_form) == 2
            lhs, rhs = m.canonical_wrong_form
            assert isinstance(lhs, str) and lhs.strip()
            assert isinstance(rhs, str) and rhs.strip()

    def test_authored_set_matches(self) -> None:
        authored = {m.id for m in CATALOG if m.canonical_wrong_form is not None}
        assert authored == self._AUTHORED_IDS

    def test_wrong_form_is_proven_false_by_sympy(self) -> None:
        """★권위 일원화: 부여된 wrong form은 SymPy가 *거짓임을 증명*한다(not_identity)."""
        for mid in self._AUTHORED_IDS:
            lhs, rhs = CATALOG_BY_ID[mid].canonical_wrong_form  # type: ignore[misc]
            verdict = identity_status(lhs, rhs)
            assert verdict is IdentityVerdict.not_identity, (mid, lhs, rhs, verdict)


class TestCorrectForm:
    """선택 필드 `correct_form` — identity-shaped 오개념의 정정 형태(정밀 −1 반박 신호·tier).

    부여 8종(distribution·a⁰·log·곱미분·sin 합분배 + 슬: 신호 정밀화로 gate-safe화된 square-root·
    fraction-cancellation·chain-rule). 핵심 불변식: 정정 형태가 *자기 오개념*으로 신뢰 게이트(0.65)
    이상 confident 오진단되면 안 된다 — `signals`가 *틀린 RHS*를 포함해 정정 형태(올바른 RHS)와
    구분되는 오개념만 부여(LHS-only 느슨 신호는 신호 정밀화로 먼저 좁힌다).
    """

    _AUTHORED_IDS = {
        "distribution-over-power",
        "exponent-zero",
        "log-distribution",
        "product-rule-naive",
        "sine-distributes-over-sum",
        # 슬: 신호 정밀화(LHS식+틀린 RHS)로 gate-safe화 → correct_form 부여(#271 커버리지 완성).
        "square-root-positivity",
        "fraction-cancellation",
        "chain-rule-inner-derivative-omitted",
    }

    def test_field_optional_and_typed(self) -> None:
        # 대부분 None(대체 불가 conceptual 오개념)·부여 항목은 비어있지 않은 str.
        for m in CATALOG:
            assert m.correct_form is None or isinstance(m.correct_form, str)
            if m.id not in self._AUTHORED_IDS:
                assert m.correct_form is None, m.id

    def test_authored_set_present_and_nonempty(self) -> None:
        # 초기 부여 5종이 실제로 correct_form을 갖는다(≥5 정밀 귀속 좌석).
        authored = {m.id for m in CATALOG if m.correct_form is not None}
        assert authored == self._AUTHORED_IDS
        assert len(authored) >= 5
        for mid in self._AUTHORED_IDS:
            assert CATALOG_BY_ID[mid].correct_form, mid

    def test_correct_form_distinct_from_wrong_statement(self) -> None:
        # 정정 형태 ≠ 학생의 틀린 진술(정정은 올바른 형태라야 의미가 있다).
        for mid in self._AUTHORED_IDS:
            m = CATALOG_BY_ID[mid]
            assert m.correct_form != m.canonical_statement, mid

    def test_correct_form_is_gate_safe(self) -> None:
        # 불변식 — 정정 형태를 진단하면 *자기 오개념*을 신뢰 게이트(0.65) 이상으로 내지 않는다
        # (정정 형태가 자기 오개념으로 confident 오진단되면 student_input에서 거짓 +1을 유발).
        for mid in self._AUTHORED_IDS:
            cf = CATALOG_BY_ID[mid].correct_form
            assert cf is not None
            self_match = next((x for x in diagnose(cf, top_k=8) if x.misconception.id == mid), None)
            assert self_match is None or self_match.confidence < _DEFAULT_CONFIDENCE_FLOOR, mid


class TestExposedSurface:
    def test_misconception_typed_as_basemodel(self) -> None:
        for m in CATALOG:
            assert isinstance(m, Misconception)
