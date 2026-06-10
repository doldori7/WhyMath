"""오개념 진단 결합(`combine_diagnoses`) 단위테스트 — slice 106 (순수·MisconceptionMatch 직접 조립).

`combine_diagnoses`는 *순수*(provider·index 무관·원소 변형 0)라 MisconceptionMatch를 직접
조립해 결합 랭킹·dedup·top_k·재정렬 금지를 라이브 없이 검증한다. 사용자 확정 결정(substring
우선·semantic 후순)과 핵심 불변(no-cross-axis-resort·블록 우선)을 못 박는다.
"""

from __future__ import annotations

from whymath_backend.l4.misconception import combine_diagnoses
from whymath_backend.l4.misconception.catalog import CATALOG_BY_ID
from whymath_backend.l4.misconception.models import MisconceptionMatch


def _substr_match(mid: str, confidence: float) -> MisconceptionMatch:
    """substring 경로 결과 모사 — semantic_similarity=None(03 substring 경로 계약)."""
    return MisconceptionMatch(
        misconception=CATALOG_BY_ID[mid],
        confidence=confidence,
        matched_signals=("토큰",),
    )


def _semantic_match(mid: str, cosine: float) -> MisconceptionMatch:
    """의미 경로 결과 모사 — semantic_similarity 채움·confidence=클램프(03 matcher.py 매핑)."""
    return MisconceptionMatch(
        misconception=CATALOG_BY_ID[mid],
        confidence=min(1.0, max(0.0, cosine)),
        semantic_similarity=cosine,
    )


class TestSubstringOnTop:
    """substring 매치가 결합 결과의 *위*에 순서 그대로 온다(사용자 확정: substring 우선)."""

    def test_substring_block_preserved_order(self) -> None:
        substr = [
            _substr_match("distribution-over-power", 1.0),
            _substr_match("division-by-zero", 0.5),
        ]
        out = combine_diagnoses(substr, [], top_k=5)
        assert [m.misconception.id for m in out] == [
            "distribution-over-power",
            "division-by-zero",
        ]
        # 원소 변형 0 — 같은 객체를 그대로 재배치(순수성).
        assert out[0] is substr[0]
        assert out[1] is substr[1]

    def test_substring_carries_no_semantic_similarity(self) -> None:
        out = combine_diagnoses([_substr_match("division-by-zero", 1.0)], [], top_k=5)
        assert out[0].semantic_similarity is None


class TestSemanticAppendedBelow:
    """semantic-only 후보는 substring 블록 *아래*에 의미 유사도 순서 그대로 붙는다."""

    def test_semantic_only_below_substring(self) -> None:
        substr = [_substr_match("distribution-over-power", 0.5)]
        sem = [
            _semantic_match("division-by-zero", 0.9),
            _semantic_match("continuity-implies-differentiability", 0.7),
        ]
        out = combine_diagnoses(substr, sem, top_k=5)
        assert [m.misconception.id for m in out] == [
            "distribution-over-power",  # substr 위(conf 0.5여도)
            "division-by-zero",  # semantic 아래(cos 0.9)
            "continuity-implies-differentiability",  # semantic 아래(cos 0.7)
        ]

    def test_semantic_order_preserved(self) -> None:
        # 의미 매처가 이미 유사도 내림차순으로 준 순서를 그대로 보존(여기서 재정렬 안 함).
        sem = [
            _semantic_match("division-by-zero", 0.8),
            _semantic_match("distribution-over-power", 0.6),
        ]
        out = combine_diagnoses([], sem, top_k=5)
        assert [m.misconception.id for m in out] == [
            "division-by-zero",
            "distribution-over-power",
        ]


class TestDedupPreferSubstring:
    """같은 misconception.id는 substring 우선·semantic 중복 버림(dedup)."""

    def test_dedup_keeps_substring_drops_semantic(self) -> None:
        substr = [_substr_match("division-by-zero", 0.5)]
        sem = [_semantic_match("division-by-zero", 0.99)]  # 같은 id·높은 cos
        out = combine_diagnoses(substr, sem, top_k=5)
        # 결과는 substr 1건만 — semantic 중복은 버려진다(substr 우선).
        assert len(out) == 1
        assert out[0].misconception.id == "division-by-zero"
        assert out[0].semantic_similarity is None  # substr 결과(semantic 아님)
        assert out[0].confidence == 0.5  # substr confidence 유지(cos 0.99로 덮지 않음)

    def test_dedup_mixed_some_overlap(self) -> None:
        substr = [_substr_match("distribution-over-power", 1.0)]
        sem = [
            _semantic_match("distribution-over-power", 0.95),  # 중복 → 버림
            _semantic_match("division-by-zero", 0.8),  # 신규 → 아래 추가
        ]
        out = combine_diagnoses(substr, sem, top_k=5)
        assert [m.misconception.id for m in out] == [
            "distribution-over-power",  # substr(중복 dedup)
            "division-by-zero",  # semantic-only
        ]


class TestNoCrossAxisResort:
    """핵심 불변: 두 confidence 축을 섞어 재정렬하지 않는다 — semantic cos가 substr를 추월 못 함."""

    def test_high_cosine_does_not_overtake_low_substring(self) -> None:
        # substr conf 0.5(확정 진단) vs semantic cos 0.99(표면 근접). 한 축으로 재정렬하면
        # semantic이 1위가 되겠지만, 블록 우선이라 substr가 *반드시* 1위.
        substr = [_substr_match("distribution-over-power", 0.5)]
        sem = [_semantic_match("division-by-zero", 0.99)]
        out = combine_diagnoses(substr, sem, top_k=5)
        assert out[0].misconception.id == "distribution-over-power"  # substr 1위
        assert out[0].confidence == 0.5
        assert out[1].misconception.id == "division-by-zero"  # semantic 2위(cos 0.99여도)

    def test_matches_zero_is_substring_when_present(self) -> None:
        # substr가 하나라도 있으면 결과[0]은 substr(select_intervention이 substr 진단 기준 구동).
        substr = [_substr_match("division-by-zero", 0.6)]
        sem = [_semantic_match("distribution-over-power", 1.0)]
        out = combine_diagnoses(substr, sem, top_k=5)
        assert out[0] is substr[0]


class TestTopKAtEnd:
    """top_k는 *결합 끝에서만* 적용 — substr를 미리 자르지 않는다(semantic이 substr 밀어냄 방지)."""

    def test_top_k_cut_after_combine(self) -> None:
        substr = [
            _substr_match("distribution-over-power", 1.0),
            _substr_match("division-by-zero", 0.5),
        ]
        sem = [_semantic_match("continuity-implies-differentiability", 0.9)]
        out = combine_diagnoses(substr, sem, top_k=2)
        # 결합 = [substr0, substr1, sem0] → top_k=2 → [substr0, substr1]. semantic은 컷에서 탈락.
        assert [m.misconception.id for m in out] == [
            "distribution-over-power",
            "division-by-zero",
        ]

    def test_top_k_does_not_pre_cut_substring(self) -> None:
        # substr가 top_k보다 많아도(3개·top_k=2) substr끼리만 자른다 — semantic이 substr를
        # 잘라내지 않음(결합 끝 컷이라 substr 블록이 우선 채워짐).
        substr = [
            _substr_match("distribution-over-power", 1.0),
            _substr_match("division-by-zero", 0.9),
            _substr_match("continuity-implies-differentiability", 0.8),
        ]
        sem = [_semantic_match("log-distribution", 1.0)]
        out = combine_diagnoses(substr, sem, top_k=2)
        # top_k=2 → substr 상위 2개만. semantic-only는 컷 아래라 미노출.
        assert all(m.semantic_similarity is None for m in out)
        assert len(out) == 2

    def test_top_k_zero_empty(self) -> None:
        substr = [_substr_match("division-by-zero", 1.0)]
        assert combine_diagnoses(substr, [], top_k=0) == []

    def test_top_k_negative_empty(self) -> None:
        substr = [_substr_match("division-by-zero", 1.0)]
        assert combine_diagnoses(substr, [], top_k=-1) == []


class TestEmptyInputs:
    """빈 양쪽·한쪽 빈 입력 처리."""

    def test_both_empty(self) -> None:
        assert combine_diagnoses([], [], top_k=3) == []

    def test_only_substring(self) -> None:
        substr = [_substr_match("division-by-zero", 1.0)]
        out = combine_diagnoses(substr, [], top_k=3)
        assert [m.misconception.id for m in out] == ["division-by-zero"]

    def test_only_semantic(self) -> None:
        sem = [_semantic_match("division-by-zero", 0.8)]
        out = combine_diagnoses([], sem, top_k=3)
        assert [m.misconception.id for m in out] == ["division-by-zero"]
        assert out[0].semantic_similarity == 0.8

    def test_inputs_not_mutated(self) -> None:
        # 순수성 — 입력 리스트 객체가 변형되지 않는다(append/sort 부수효과 0).
        substr = [_substr_match("division-by-zero", 1.0)]
        sem = [_semantic_match("distribution-over-power", 0.9)]
        substr_before = list(substr)
        sem_before = list(sem)
        combine_diagnoses(substr, sem, top_k=3)
        assert substr == substr_before
        assert sem == sem_before
