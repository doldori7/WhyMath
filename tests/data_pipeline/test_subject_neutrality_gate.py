"""과목 중립성 회귀 게이트(S3) — "새 수학 하드코딩 유입 금지" 불변식.

정본: `docs/architecture/subject_expansion_readiness.md` §9. 이 게이트는 새 구조를 만들지
않는다 — S2가 확보한 seam(출처 표기 단일 원천)과 §4.1 AREA 레지스트리 규약이 이후 변경으로
*후퇴*하지 않도록 동결만 한다.

동결 3종:
  1. **citation 단일 원천** — NCIC 유래 3모듈의 `SOURCE_CITATION`은 반드시
     `build_ncic_citation_core()` 출력을 포함(빌더 우회 하드코딩 회귀 차단).
  2. **과목 라벨 리터럴 재등장 금지** — "[수학과 교육과정]" 리터럴이 프로덕션 소스
     (`src/data-pipeline/data_pipeline/`)에 문자 그대로 재등장하면 실패. `citation.py`조차
     f-string 합성만 쓰므로 예외 없이 0이어야 한다(`standards_university`는 NCIC 비유래
     자체 표기라 애초에 이 리터럴이 없다 — 별도 예외 불요·생기면 그것도 위반).
  3. **물리 예약 AREA 니모닉 미침범** — 수학 `_TOPIC_AREA_MAP`이 §4.1 물리 예약 니모닉
     (MECH·ELEC·WAVE·THERMO·MODPHY)을 쓰면 실패. AREA는 전역 유일·정확히 한 과목 소속이
     레지스트리 규약이므로, 예약분을 수학이 선점하는 순간 물리 확장 시 ID 충돌이 된다.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from data_pipeline.citation import build_ncic_citation_core
from data_pipeline.concept_graph.idmap import _AREA_TOKEN_PATTERN, _TOPIC_AREA_MAP

# 프로덕션 소스 루트(테스트 트리는 동결 리터럴을 갖고 있으므로 스캔 제외).
_SRC_ROOT = Path(__file__).resolve().parents[2] / "src" / "data-pipeline" / "data_pipeline"

# §4.1 물리 예약 AREA 니모닉 — 실등록은 물리 원천 코퍼스 category 확정 시(보류 대장 §8).
_PHYSICS_RESERVED_AREAS: frozenset[str] = frozenset({"MECH", "ELEC", "WAVE", "THERMO", "MODPHY"})

# 과목 라벨 리터럴(대괄호 포함) — 이 파일 자체도 스캔 대상 소스에 없도록 조합으로 구성.
_MATH_LABEL_LITERAL = "[" + "수학과 교육과정" + "]"


class TestCitationSingleSource:
    """NCIC 유래 3모듈 SOURCE_CITATION이 빌더 출력을 포함 — 우회 하드코딩 회귀 차단."""

    @pytest.mark.parametrize(
        "module_path",
        [
            "data_pipeline.ncic.models",
            "data_pipeline.concept_graph.models",
            "data_pipeline.atom_graph.models",
        ],
    )
    def test_source_citation_contains_builder_core(self, module_path: str) -> None:
        module = __import__(module_path, fromlist=["SOURCE_CITATION"])
        assert build_ncic_citation_core() in module.SOURCE_CITATION

    def test_university_citation_is_independent(self) -> None:
        """대학 표준 표기는 NCIC 비유래(자체작성) — 빌더 코어를 포함하지 *않아야* 정상."""
        from data_pipeline.standards_university.models import (
            SOURCE_CITATION as UNIVERSITY_CITATION,
        )

        assert build_ncic_citation_core() not in UNIVERSITY_CITATION


class TestMathLabelLiteralBanned:
    """과목 라벨 리터럴이 프로덕션 소스에 재등장 금지 — 단일 원천은 citation.py 빌더뿐."""

    def test_no_math_label_literal_in_production_sources(self) -> None:
        offenders = [
            str(py.relative_to(_SRC_ROOT))
            for py in sorted(_SRC_ROOT.rglob("*.py"))
            if _MATH_LABEL_LITERAL in py.read_text(encoding="utf-8")
        ]
        assert offenders == [], (
            f"'{_MATH_LABEL_LITERAL}' 리터럴 재등장: {offenders} — "
            "build_ncic_citation_core(subject_label)로 합성하라(readiness doc §9)."
        )


class TestAreaRegistryReservation:
    """수학 AREA 니모닉이 물리 예약분을 침범하지 않음 + 토큰 규약 준수(이중 동결)."""

    def test_math_areas_do_not_claim_physics_reserved(self) -> None:
        claimed = _PHYSICS_RESERVED_AREAS & set(_TOPIC_AREA_MAP.values())
        assert claimed == frozenset(), (
            f"물리 예약 AREA 침범: {sorted(claimed)} — AREA는 전역 유일·1과목 소속"
            "(readiness doc §4.1 레지스트리 규약)."
        )

    def test_math_areas_conform_token_pattern(self) -> None:
        """import-time 가드(idmap 모듈 로드 시 ValueError)의 테스트 계층 이중화."""
        violations = {
            stem: area
            for stem, area in _TOPIC_AREA_MAP.items()
            if not _AREA_TOKEN_PATTERN.match(area)
        }
        assert violations == {}
