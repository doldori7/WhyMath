"""L6 공용 게이팅 헬퍼(`l6/_shared.py`) 단위테스트 — 정규화·저작권 게이트·적합도.

검증:
  ① `METADATA_ONLY_SOURCES` — 평가원·EBS·교과서(본문 미보유 3종).
  ② `normalize_enum_value` — enum→.value·str→그대로·None→None.
  ③ `source_value` — source_type 문자열 정규화(enum/문자열 양쪽).
  ④ `persona_fit` — 키 enum/문자열 양쪽 적중·없으면 0.0.
  ⑤ `is_exposable` — 자체생성 등 True / 평가원·EBS·교과서 False.
  ⑥ Rule of three 재노출 — `l6.retake.gating`·`l6.suneung.gating`의
     `METADATA_ONLY_SOURCES`가 `_shared`와 *같은 객체*(import 경로 호환).

합성 픽스처만(실데이터 0). 레이어(CLAUDE.md): 테스트는 L1(`schema.problem`·`schema.enums`)·
L6(`l6._shared`)만 import한다.
"""

from __future__ import annotations

from whymath_backend.l6 import _shared
from whymath_backend.schema.enums import Curriculum, Persona, SourceType, Subject
from whymath_backend.schema.problem import Problem


def _problem(**over: object) -> Problem:
    """최소 자체생성 Problem 빌더(합성 픽스처) — RT/수능 테스트 패턴 답습."""
    kwargs: dict[str, object] = {
        "source_type": SourceType.자체생성,
        "curriculum_version": Curriculum.REVISION_2022,
        "valid_from_year": 2022,
        "subject": Subject.미적분,
        "unit_codes": ["CAL-INT-DEF"],
    }
    kwargs.update(over)
    return Problem(**kwargs)  # type: ignore[arg-type]


# ──────────────────────────────────────────────────────────────────────
# 상수
# ──────────────────────────────────────────────────────────────────────
class TestMetadataOnlySources:
    def test_three_no_body_sources(self) -> None:
        """차단 집합은 평가원·EBS·교과서(본문 미보유 3종)."""
        assert _shared.METADATA_ONLY_SOURCES == frozenset(
            {SourceType.평가원, SourceType.EBS, SourceType.교과서}
        )


# ──────────────────────────────────────────────────────────────────────
# normalize_enum_value
# ──────────────────────────────────────────────────────────────────────
class TestNormalizeEnumValue:
    def test_enum_returns_value(self) -> None:
        """enum 멤버는 .value(문자열)로 정규화된다."""
        assert _shared.normalize_enum_value(SourceType.평가원) == "평가원"
        assert _shared.normalize_enum_value(Persona.A_일반고고3) == "A_일반고고3"

    def test_str_returned_as_is(self) -> None:
        """이미 문자열이면 그대로 반환."""
        assert _shared.normalize_enum_value("자체생성") == "자체생성"

    def test_none_preserved(self) -> None:
        """None은 None으로 보존(Optional 필드 미지정)."""
        assert _shared.normalize_enum_value(None) is None


# ──────────────────────────────────────────────────────────────────────
# source_value
# ──────────────────────────────────────────────────────────────────────
class TestSourceValue:
    def test_self_generated(self) -> None:
        """자체생성 출처는 '자체생성' 문자열로 정규화된다."""
        assert _shared.source_value(_problem()) == "자체생성"

    def test_metadata_only_source(self) -> None:
        """평가원 출처(본문 미보유)도 문자열로 정규화된다."""
        assert _shared.source_value(_problem(source_type=SourceType.평가원)) == "평가원"


# ──────────────────────────────────────────────────────────────────────
# persona_fit
# ──────────────────────────────────────────────────────────────────────
class TestPersonaFit:
    def test_enum_key_hit(self) -> None:
        """persona_fit 키가 enum이면 적합도를 그대로 조회한다."""
        problem = _problem(persona_fit={Persona.A_일반고고3: 0.7})
        assert _shared.persona_fit(problem, Persona.A_일반고고3) == 0.7

    def test_string_key_hit(self) -> None:
        """use_enum_values=True로 키가 문자열이어도 적합도가 조회된다(정규화 폴백)."""
        problem = _problem(persona_fit={Persona.A_일반고고3.value: 0.6})
        assert _shared.persona_fit(problem, Persona.A_일반고고3) == 0.6

    def test_missing_key_returns_zero(self) -> None:
        """키가 없으면 0.0(미평가 = 부적합)."""
        problem = _problem(persona_fit={Persona.B_자사고N수: 0.9})
        assert _shared.persona_fit(problem, Persona.A_일반고고3) == 0.0


# ──────────────────────────────────────────────────────────────────────
# is_exposable — 저작권 노출 게이트
# ──────────────────────────────────────────────────────────────────────
class TestIsExposable:
    def test_self_generated_is_exposable(self) -> None:
        """자체생성 출처는 노출 가능(True)."""
        assert _shared.is_exposable(_problem()) is True

    def test_metadata_only_sources_not_exposable(self) -> None:
        """평가원·EBS·교과서(본문 미보유)는 노출 불가(False)."""
        for source in (SourceType.평가원, SourceType.EBS, SourceType.교과서):
            assert _shared.is_exposable(_problem(source_type=source)) is False, source


# ──────────────────────────────────────────────────────────────────────
# Rule of three 재노출 — import 경로 호환(무회귀)
# ──────────────────────────────────────────────────────────────────────
class TestReexportBackwardCompat:
    def test_retake_reexports_shared_constant(self) -> None:
        """`l6.retake.gating.METADATA_ONLY_SOURCES`가 `_shared`와 같은 객체(재노출)."""
        from whymath_backend.l6.retake import gating as retake_gating

        assert retake_gating.METADATA_ONLY_SOURCES is _shared.METADATA_ONLY_SOURCES

    def test_suneung_reexports_shared_constant(self) -> None:
        """`l6.suneung.gating.METADATA_ONLY_SOURCES`가 `_shared`와 같은 객체(재노출)."""
        from whymath_backend.l6.suneung import gating as suneung_gating

        assert suneung_gating.METADATA_ONLY_SOURCES is _shared.METADATA_ONLY_SOURCES
