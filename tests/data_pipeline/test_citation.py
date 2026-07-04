"""`data_pipeline.citation` — NCIC 출처 표기 빌더(S2) 테스트.

핵심 동결(subject_expansion_readiness.md §9 invariant):
  1. **바이트 동일성** — 3모듈 `SOURCE_CITATION`은 리팩토링 *전* 리터럴과 정확히 일치.
     직렬화 산출물·golden 테스트·코퍼스가 이 문자열을 담고 있어 값 변화는 곧 회귀다
     (코퍼스 재생성 없이도 값 불변을 증명하는 게 이 테스트의 존재 이유).
  2. **합성 정합** — 빌더 기본 출력 + 모듈별 접두/접미 래핑 = 각 모듈 `SOURCE_CITATION`.
  3. **과목 라벨 파라미터** — "과학과"(별책 9) 전달 시 라벨만 교체(고시 번호 공유).

주의: 아래 `_PRE_REFACTOR_*` 리터럴은 2026-07-02 리팩토링 직전 실측값 고정 —
빌더·모듈이 바뀌어도 이 리터럴은 절대 수정하지 않는다(수정하면 동결 무효).
"""

from __future__ import annotations

from data_pipeline.atom_graph.models import SOURCE_CITATION as ATOM_GRAPH_CITATION
from data_pipeline.citation import build_ncic_citation_core
from data_pipeline.concept_graph.models import SOURCE_CITATION as CONCEPT_GRAPH_CITATION
from data_pipeline.ncic.models import SOURCE_CITATION as NCIC_CITATION

# ──────────────────────────────────────────────────────────────────────
# 리팩토링 전 리터럴 (2026-07-02 실측 고정 — 절대 수정 금지)
# ──────────────────────────────────────────────────────────────────────
_PRE_REFACTOR_NCIC = (
    "출처: 교육부 고시 제2022-33호 [수학과 교육과정], "
    "국가교육과정정보센터(NCIC, https://www.ncic.go.kr)"
)
_PRE_REFACTOR_CONCEPT_GRAPH = (
    "개념-성취기준 매핑 근거: 교육부 고시 제2022-33호 [수학과 교육과정], "
    "국가교육과정정보센터(NCIC, https://www.ncic.go.kr)"
)
_PRE_REFACTOR_ATOM_GRAPH = (
    "원자-성취기준 매핑 근거: 교육부 고시 제2022-33호 [수학과 교육과정], "
    "국가교육과정정보센터(NCIC, https://www.ncic.go.kr). "
    "원자화·교수학 주석(4요소·원자성)·대학 축은 와이매스 자체작성."
)


class TestByteIdentity:
    """리팩토링 전후 값 바이트 동일 — golden·직렬화 산출물·코퍼스 보존 증명."""

    def test_ncic_source_citation_unchanged(self) -> None:
        assert NCIC_CITATION == _PRE_REFACTOR_NCIC

    def test_concept_graph_source_citation_unchanged(self) -> None:
        assert CONCEPT_GRAPH_CITATION == _PRE_REFACTOR_CONCEPT_GRAPH

    def test_atom_graph_source_citation_unchanged(self) -> None:
        assert ATOM_GRAPH_CITATION == _PRE_REFACTOR_ATOM_GRAPH


class TestBuilderComposition:
    """빌더 기본 출력이 3모듈의 접두/접미 래핑 합성과 정합함을 동결."""

    def test_ncic_is_prefix_plus_core(self) -> None:
        assert NCIC_CITATION == "출처: " + build_ncic_citation_core()

    def test_concept_graph_is_prefix_plus_core(self) -> None:
        assert CONCEPT_GRAPH_CITATION == "개념-성취기준 매핑 근거: " + build_ncic_citation_core()

    def test_atom_graph_is_prefix_plus_core_plus_suffix(self) -> None:
        assert ATOM_GRAPH_CITATION == (
            "원자-성취기준 매핑 근거: "
            + build_ncic_citation_core()
            + ". 원자화·교수학 주석(4요소·원자성)·대학 축은 와이매스 자체작성."
        )

    def test_default_label_equals_explicit_math_label(self) -> None:
        """기본 인자 = '수학과'(별책 8) 명시 호출과 동일."""
        assert build_ncic_citation_core() == build_ncic_citation_core("수학과")


class TestScienceSubjectLabel:
    """과학과(별책 9) 라벨 — 고시 번호는 공유·라벨만 교체(readiness doc §4.2)."""

    def test_science_label_format(self) -> None:
        cite = build_ncic_citation_core("과학과")
        assert "[과학과 교육과정]" in cite
        assert "교육부 고시 제2022-33호" in cite  # 고시 번호는 과목 간 공유(별책만 상이)
        assert "국가교육과정정보센터(NCIC, https://www.ncic.go.kr)" in cite
        assert "수학과" not in cite  # 라벨 교체 시 수학과 흔적 없음
