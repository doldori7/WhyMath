"""concept_atom_crosswalk 유도 로직 단위테스트 — 소형 fixture로 3단계 규칙·결정론 동결.

hermetic: 커밋 코퍼스 불요 — 인메모리 ConceptRecord/AtomRecord fixture만 사용.
"""

from __future__ import annotations

from data_pipeline.concept_atom_crosswalk.derive import (
    AtomRecord,
    ConceptRecord,
    derive_crosswalk,
    jaccard,
    name_tokens,
)


def _concept(concept_id: str, name_ko: str, codes: tuple[str, ...]) -> ConceptRecord:
    return ConceptRecord(concept_id=concept_id, name_ko=name_ko, standard_codes=codes)


def _atom(code: str, name: str, codes: tuple[str, ...]) -> AtomRecord:
    return AtomRecord(code=code, name=name, standard_codes=codes)


class TestNameTokens:
    """토큰화 — 단어 run + 문자 bigram(한국어 복합어 부분 겹침 포착)."""

    def test_word_runs_and_bigrams(self) -> None:
        """중점·괄호는 구분자, run과 bigram이 함께 나온다."""
        tokens = name_tokens("자릿값·기수법")
        assert "자릿값" in tokens
        assert "기수법" in tokens
        assert "자릿" in tokens  # bigram
        assert "·" not in tokens

    def test_jaccard_bounds(self) -> None:
        """자카드 — 동일 1.0·소 0.0·빈 집합 0.0."""
        a = name_tokens("소인수분해")
        assert jaccard(a, a) == 1.0
        assert jaccard(a, name_tokens("확률")) == 0.0
        assert jaccard(frozenset(), a) == 0.0


class TestDeriveRules:
    """유도 3단계 규칙 — 유일 후보·복수 후보 랭킹·미매핑."""

    def test_single_candidate_standard_code(self) -> None:
        """1차 다리 유일 후보 → match_method='standard_code'·confidence 0.9."""
        entries = derive_crosswalk(
            [_concept("math.algebra.insubunhae", "인수분해", ("[9수02-01]",))],
            [_atom("9수02-01-1", "인수분해 기본", ("[9수02-01]",))],
        )
        assert len(entries) == 1
        entry = entries[0]
        assert entry.match_method == "standard_code"
        assert entry.atom_codes == ["9수02-01-1"]
        assert entry.primary_atom_code == "9수02-01-1"
        assert entry.confidence == 0.9

    def test_multi_candidate_name_ranking(self) -> None:
        """2차 다리 — 이름 자카드 최고 원자가 primary(코드 순서와 무관)."""
        entries = derive_crosswalk(
            [_concept("math.algebra.insubunhae", "인수분해", ("[9수02-01]",))],
            [
                _atom("9수02-01-1", "다항식의 전개", ("[9수02-01]",)),
                _atom("9수02-01-2", "인수분해 공식", ("[9수02-01]",)),
            ],
        )
        entry = entries[0]
        assert entry.match_method == "standard_code+name"
        assert entry.atom_codes == ["9수02-01-1", "9수02-01-2"]  # 후보 목록은 code 사전순
        assert entry.primary_atom_code == "9수02-01-2"  # 이름 겹침이 큰 쪽
        assert 0.5 < entry.confidence <= 0.9

    def test_unmapped_when_no_candidates(self) -> None:
        """3단계 — 교집합 0이면 강제 매핑 없이 unmapped + 사유."""
        entries = derive_crosswalk(
            [_concept("math.probability.hwakryul", "확률", ("[9수04-99]",))],
            [_atom("9수02-01-1", "인수분해", ("[9수02-01]",))],
        )
        entry = entries[0]
        assert entry.match_method == "unmapped"
        assert entry.atom_codes == []
        assert entry.primary_atom_code is None
        assert entry.confidence == 0.0
        assert entry.unmapped_reason is not None
        assert "[9수04-99]" in entry.unmapped_reason

    def test_tie_breaks_by_code_lexicographic(self) -> None:
        """결정론 — 자카드 동률(둘 다 겹침 0)이면 code 사전순 첫 원자가 primary."""
        entries = derive_crosswalk(
            [_concept("math.probability.hwakryul", "확률", ("[9수04-01]",))],
            [
                _atom("9수04-01-2", "경우의 수", ("[9수04-01]",)),
                _atom("9수04-01-1", "표본공간", ("[9수04-01]",)),
            ],
        )
        entry = entries[0]
        assert entry.primary_atom_code == "9수04-01-1"
        assert entry.confidence == 0.5  # 0.5 + 0.4×0.0

    def test_output_sorted_by_concept_id(self) -> None:
        """출력은 concept_id 사전순(입력 순서 무관·결정론)."""
        atoms = [_atom("9수02-01-1", "인수분해", ("[9수02-01]",))]
        entries = derive_crosswalk(
            [
                _concept("math.geometry.hapdong", "합동", ("[9수02-01]",)),
                _concept("math.algebra.insubunhae", "인수분해", ("[9수02-01]",)),
            ],
            atoms,
        )
        assert [e.concept_id for e in entries] == [
            "math.algebra.insubunhae",
            "math.geometry.hapdong",
        ]

    def test_multi_standard_union_candidates(self) -> None:
        """개념의 성취기준이 여러 개면 후보는 합집합(dedup)이다."""
        entries = derive_crosswalk(
            [_concept("math.algebra.insubunhae", "인수분해", ("[9수02-01]", "[9수02-02]"))],
            [
                _atom("9수02-01-1", "인수분해 기본", ("[9수02-01]",)),
                _atom("9수02-02-1", "인수분해 공식", ("[9수02-02]", "[9수02-01]")),
            ],
        )
        assert entries[0].atom_codes == ["9수02-01-1", "9수02-02-1"]
