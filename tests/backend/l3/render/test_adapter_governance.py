"""어댑터 거버넌스 — 개념 무관성 동결(03c §5·`test_embedding_namespace_governance` 선례 동형).

세 갈래로 "어댑터는 개념 무관"을 코드로 동결한다:
  ① **소스 스캔**: `l3/render/adapters/`의 어떤 파일도 특정 개념명을 하드코딩하지 않는다(금지
     토큰 allowlist 동결) + 각 구체 어댑터는 콘텐츠를 `dsl.*`에서만 끌어온다.
  ② **대칭**: 숫자/이름만 다른 두 DSL을 각 어댑터로 렌더하면 *구조가 동일*하다(차이는 render
     바인딩이지 새 자산 아님 — "숫자/이름만 다른 두 DSL = 위반" 거버넌스).
  ③ **개념 무관 증명**: 모든 어댑터가 구조가 서로 다른 ≥2개 DSL을 오류 없이 렌더한다.

hermetic: DB 불요(순수 렌더·소스 스캔만).
"""

from __future__ import annotations

from pathlib import Path

import pytest

import whymath_backend
from whymath_backend.l3.render.models import RenderContext, RenderedUnit
from whymath_backend.l3.render.registry import ADAPTERS
from whymath_backend.schema.concept_dsl import (
    AssessmentSeed,
    ConceptDSL,
    ExampleSpec,
    build_example_concept_dsl,
)
from whymath_backend.schema.enums import PedagogyStrategy

_ADAPTERS_DIR = Path(whymath_backend.__file__).parent / "l3" / "render" / "adapters"
_CTX = RenderContext()

# 어댑터 디렉토리 파일 집합 동결 — 새 어댑터 추가 시 이 allowlist를 *의식적으로* 갱신해야 하며,
# 그 리뷰 시점이 곧 개념 무관성 심사다(cosine_distance allowlist 선례 동형).
_EXPECTED_ADAPTER_FILES: frozenset[str] = frozenset(
    {
        "__init__.py",
        "_common.py",
        "analogy.py",
        "direct.py",
        "problem_based.py",
        "socratic.py",
        "worked_example.py",
    }
)

# 구체 어댑터 5종(콘텐츠를 dsl.*에서 끌어와야 하는 파일).
_CONCRETE_ADAPTER_FILES: tuple[str, ...] = (
    "direct.py",
    "socratic.py",
    "worked_example.py",
    "problem_based.py",
    "analogy.py",
)

# 금지 개념명 토큰 — 어댑터가 특정 개념명을 하드코딩하면 개념-무관성 위반(03c §5). 모호한 bare
# '함수'/'방정식'이 아니라 *복합 개념명*(일차방정식·미분 등)만 동결한다(false positive 회피).
_FORBIDDEN_CONCEPT_TOKENS: frozenset[str] = frozenset(
    {
        "일차방정식",
        "이차방정식",
        "이차함수",
        "일차함수",
        "미분",
        "적분",
        "삼각함수",
        "확률",
        "수열",
        "극한",
        "로그",
        "지수함수",
        "벡터",
        "인수분해",
        "피타고라스",
        "정적분",
        "도함수",
        "등차수열",
        "등비수열",
    }
)


# ──────────────────────────────────────────────────────────────────────────
# ① 소스 스캔 — 하드코딩 개념명 금지 + dsl.* 참조 동결
# ──────────────────────────────────────────────────────────────────────────
class TestSourceScan:
    def test_adapter_files_frozen(self) -> None:
        """adapters/ 파일 집합이 allowlist와 정확히 일치(추가·누락 모두 red·리뷰 강제)."""
        actual = {p.name for p in _ADAPTERS_DIR.glob("*.py")}
        assert actual == set(_EXPECTED_ADAPTER_FILES), (
            f"adapters/ 파일 집합이 allowlist와 다릅니다 — 발견 {sorted(actual)} / "
            f"허용 {sorted(_EXPECTED_ADAPTER_FILES)}. 새 어댑터가 정당하면 이 allowlist를 갱신하라."
        )

    def test_no_hardcoded_concept_names(self) -> None:
        """어떤 어댑터 파일도 특정 개념명을 하드코딩하지 않는다(개념 무관·전수 스캔)."""
        offenders: dict[str, list[str]] = {}
        for path in sorted(_ADAPTERS_DIR.glob("*.py")):
            source = path.read_text(encoding="utf-8")
            hits = [tok for tok in _FORBIDDEN_CONCEPT_TOKENS if tok in source]
            if hits:
                offenders[path.name] = sorted(hits)
        assert not offenders, (
            f"어댑터에 하드코딩된 개념명 발견: {offenders} — 어댑터는 개념 무관이어야 하고 "
            "모든 개념 콘텐츠는 dsl에서 와야 한다(03c §2·§5)."
        )

    def test_concrete_adapters_reference_dsl(self) -> None:
        """구체 어댑터 5종은 콘텐츠를 `dsl.`에서 끌어온다(DSL 주도 렌더 증거)."""
        for name in _CONCRETE_ADAPTER_FILES:
            source = (_ADAPTERS_DIR / name).read_text(encoding="utf-8")
            assert "dsl." in source, f"{name}: 콘텐츠를 dsl.*에서 끌어와야 한다(개념 무관 렌더)."


# ──────────────────────────────────────────────────────────────────────────
# ② 대칭 — 숫자/이름만 다른 두 DSL = 같은 구조(render 바인딩이지 새 자산 아님)
# ──────────────────────────────────────────────────────────────────────────
def _dsl_variant_a() -> ConceptDSL:
    """일차 조건 DSL A — 이름·숫자만 B와 다름(구조 동일)."""
    return build_example_concept_dsl(name="math.algebra.one", coef=2, const=3, rhs=7)  # x=2


def _dsl_variant_b() -> ConceptDSL:
    """일차 조건 DSL B — A와 이름·숫자만 다름(구조 동일)."""
    return build_example_concept_dsl(name="math.algebra.two", coef=5, const=1, rhs=16)  # x=3


class TestSymmetry:
    @pytest.mark.parametrize("strategy", list(ADAPTERS))
    def test_number_name_only_diff_yields_same_structure(self, strategy: PedagogyStrategy) -> None:
        """숫자/이름만 다른 두 DSL → 블록 구조(kind 시퀀스) 동일·본문만 다름(대칭 거버넌스)."""
        adapter = ADAPTERS[strategy]
        unit_a = adapter.render(_dsl_variant_a(), _CTX)
        unit_b = adapter.render(_dsl_variant_b(), _CTX)

        kinds_a = tuple(b.kind for b in unit_a.blocks)
        kinds_b = tuple(b.kind for b in unit_b.blocks)
        assert kinds_a == kinds_b, (
            f"{strategy.value}: 숫자/이름만 다른데 구조가 다르다({kinds_a} vs {kinds_b}) — "
            "구조는 개념 무관이어야 한다(차이는 render 바인딩)."
        )
        # 둘 다 clean(검증 통과분)이어야 대칭이 의미 있다.
        assert unit_a.validation_signal is None
        assert unit_b.validation_signal is None
        # 차이는 *바인딩*(본문)에 있다 — 완전히 동일하면 슬롯화가 안 된 것.
        texts_a = tuple(b.text for b in unit_a.blocks)
        texts_b = tuple(b.text for b in unit_b.blocks)
        assert texts_a != texts_b, f"{strategy.value}: 본문이 동일 — 숫자 바인딩이 반영되지 않음."


# ──────────────────────────────────────────────────────────────────────────
# ③ 개념 무관 증명 — 구조가 다른 ≥2개 DSL을 모든 어댑터가 오류 없이 렌더
# ──────────────────────────────────────────────────────────────────────────
def _multi_concept_dsl() -> ConceptDSL:
    """구조가 다른 DSL — 예시 3·평가 시드 2(팩토리 DSL과 구조 상이)."""
    return ConceptDSL(
        name="math.number.linear-pair",
        definition="여러 일차 조건의 해를 구하는 개념.",
        examples=[
            ExampleSpec(statement="$x - 4 = 0$", slots={"context": "길이"}),
            ExampleSpec(statement="$2y = 10$", slots={"context": "무게"}),
            ExampleSpec(statement="$z + 1 = 6$", slots={"context": "시간"}),
        ],
        misconception_ids=["mc-a", "mc-b"],
        assessment=[
            AssessmentSeed(conditions=["x - 4 = 0"], answer={"x": "4"}),
            AssessmentSeed(conditions=["2*y = 10"], answer={"y": "5"}),
        ],
    )


class TestConceptAgnosticAcrossStructures:
    @pytest.mark.parametrize("strategy", list(ADAPTERS))
    def test_renders_two_structurally_different_dsls(self, strategy: PedagogyStrategy) -> None:
        """각 어댑터가 구조가 다른 두 DSL을 오류 없이 clean 렌더(개념·구조 무관 증명)."""
        adapter = ADAPTERS[strategy]
        for dsl in (build_example_concept_dsl(), _multi_concept_dsl()):
            assert adapter.can_render(dsl), f"{strategy.value}: can_render False({dsl.name})"
            unit = adapter.render(dsl, _CTX)
            assert isinstance(unit, RenderedUnit)
            assert unit.blocks, f"{strategy.value}: 빈 블록({dsl.name})"
            assert (
                unit.validation_signal is None
            ), f"{strategy.value}: 유효 DSL인데 검증 신호가 실림({dsl.name})"

    def test_direct_structure_scales_with_examples(self) -> None:
        """구조가 개념 콘텐츠에 따라 달라진다 — 예시 1개 vs 3개면 DIRECT 블록 수가 다르다."""
        adapter = ADAPTERS[PedagogyStrategy.DIRECT]
        single = adapter.render(build_example_concept_dsl(), _CTX)  # 예시 1
        multi = adapter.render(_multi_concept_dsl(), _CTX)  # 예시 3
        assert len(multi.blocks) > len(single.blocks)
