"""프롬프트 자산 교수학 감사 — 순수 단위 + 배포 소크라테스 자산 회귀 게이트(hermetic).

세 축:
① 순수 단위 — `audit_socratic_assets`(소크라테스 자산 통과·유출 자산 leaked 검출·worst_leakage
   우선순위·Mapping/튜플 수용·label 정렬·빈 입력)·`render_asset_audit_markdown`(카운트·근거 보존).
② **배포 자산 봉인**(핵심 소비처) — 실제 `l4.socratic.categories.EXAMPLE_QUESTION`을 감사해
   모든 캐논 발문이 (a) 소크라테스 발문이고 (b) 어떤 표본 정답도 유출하지 않음을 단언. 카테고리가
   늘면 게이트가 자동 확장. 캐논 예시가 정답 노출형으로 바뀌면 회귀로 차단(최상위 금기 봉인).
"""

from __future__ import annotations

from whymath_backend.harness.pedagogical_rubric import LeakageVerdict
from whymath_backend.harness.prompt_asset_audit import (
    audit_socratic_assets,
    render_asset_audit_markdown,
)
from whymath_backend.l4.socratic.categories import EXAMPLE_QUESTION


class TestAuditSocraticAssets:
    def test_socratic_asset_passes(self) -> None:
        """소크라테스 발문·정답 미노출 자산은 통과(발문 있음·clean)."""
        items = audit_socratic_assets({"clar": "어디까지 이해됐어?"})
        assert len(items) == 1
        assert items[0].is_socratic is True
        assert items[0].worst_leakage is LeakageVerdict.clean

    def test_leaking_asset_detected(self) -> None:
        """정답 값을 실은 발화는 leaked로 검출(발문도 없음)."""
        items = audit_socratic_assets({"bad": "정답은 42야."}, sample_answers=("42",))
        assert items[0].worst_leakage is LeakageVerdict.leaked
        assert items[0].is_socratic is False

    def test_worst_leakage_priority(self) -> None:
        """표본 중 하나라도 leaked면 worst=leaked(clean/undecidable보다 우선)."""
        items = audit_socratic_assets({"x": "남은 값은 13이다."}, sample_answers=("13", "3", "999"))
        assert items[0].worst_leakage is LeakageVerdict.leaked

    def test_undecidable_worst_when_no_leak(self) -> None:
        """유출 없고 짧은 표본만 있으면 worst=undecidable(보수·발문은 유지)."""
        items = audit_socratic_assets({"x": "왜 그렇게 했을까?"}, sample_answers=("3",))
        assert items[0].worst_leakage is LeakageVerdict.undecidable
        assert items[0].is_socratic is True

    def test_accepts_tuple_iterable(self) -> None:
        """Mapping뿐 아니라 (label, response) 튜플 이터러블도 수용."""
        items = audit_socratic_assets([("a", "어떻게 알아?")])
        assert items[0].label == "a"

    def test_sorted_by_label(self) -> None:
        """결과는 label 안정 정렬(결정론)."""
        items = audit_socratic_assets({"z": "왜?", "a": "어떻게?"})
        assert [it.label for it in items] == ["a", "z"]

    def test_empty(self) -> None:
        assert audit_socratic_assets({}) == []


class TestRenderAssetAudit:
    def test_header_counts(self) -> None:
        md = render_asset_audit_markdown(
            audit_socratic_assets(
                {"good": "왜 그렇게 했어?", "bad": "정답은 42야."}, sample_answers=("42",)
            )
        )
        assert "총 자산 2" in md
        assert "소크라테스 발문 1" in md
        assert "정답 유출 의심 1" in md

    def test_reasons_preserved(self) -> None:
        md = render_asset_audit_markdown(audit_socratic_assets({"c": "어디까지 이해됐어?"}))
        assert "소크라테스 발문 있음" in md
        assert "[c]" in md


class TestDeployedAssetSeal:
    """배포 소크라테스 자산(EXAMPLE_QUESTION)이 루브릭 준거를 전부 만족(회귀 봉인)."""

    def test_all_canonical_examples_socratic_and_leak_free(self) -> None:
        """모든 캐논 발문 = 소크라테스 발문 AND 어떤 표본 정답도 미유출(최상위 금기 봉인)."""
        items = audit_socratic_assets(
            {category.value: question for category, question in EXAMPLE_QUESTION.items()}
        )
        assert len(items) == len(EXAMPLE_QUESTION)
        for item in items:
            assert item.is_socratic is True, f"{item.label} 발문 아님: {item.response}"
            assert (
                item.worst_leakage is not LeakageVerdict.leaked
            ), f"{item.label} 정답 유출: {item.response}"
