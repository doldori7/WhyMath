"""PED-01 DSL 스키마 동결 lock — 파일럿 E2E 1회 완주 후 필드셋을 잠근다(hermetic).

acceptance "이차함수 파일럿 1개가 …E2E 1회 완주 후 DSL 스키마 동결(필드 추가는 2번째 소단원
실요구 시)"의 *기계적 시행*이다. UnitDSL·ObjectiveDSL·PedagogyPack·SlotSpec의 필드셋과 폐쇄
어휘(FORBIDDEN_MODE_VOCAB·SUBJECT_NOUN_BLOCKLIST)·api_version 핀을 동결 리터럴과 대조한다 —
필드 추가/개명/삭제 시 이 테스트가 깨져 "2번째 소단원 실요구" 명시 검토를 강제한다. governance
테스트(runtime_selector selectable 동결) 선례 동형.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from whymath_backend.schema.pedagogy_pack import (
    FORBIDDEN_MODE_VOCAB,
    SUBJECT_NOUN_BLOCKLIST,
    PedagogyPack,
    SlotSpec,
)
from whymath_backend.schema.unit_dsl import ObjectiveDSL, UnitDSL

# ── 동결 리터럴 (PED-01 완주 시점 — 변경은 "2번째 소단원 실요구" 전제) ──
_UNIT_DSL_FIELDS = {
    "unit_id",
    "unit_version",
    "api_version",
    "title",
    "curriculum_rev",
    "standard_codes",
    "concept_nodes",
    "objectives",
}
_OBJECTIVE_DSL_FIELDS = {
    "suffix",
    "statement",
    "standard_code",
    "source_verb",
    "k_type",
    "k_type_secondary",
    "concept_nodes",
    "misconception_ids",
    "slot_overrides",
    "evidence_overrides",
    "phase_overrides",
}
_PEDAGOGY_PACK_FIELDS = {
    "k_type",
    "pack_version",
    "api_version",
    "is_stub",
    "socratic_prompt",
    "fading_schedule",
    "forbidden_modes",
    "required_slots",
    "default_evidence",
}
_SLOT_SPEC_FIELDS = {"type", "count"}

_CORPUS = Path(__file__).resolve().parents[3] / "data" / "corpus"


class TestSchemaFieldFreeze:
    def test_unit_dsl_fields(self) -> None:
        assert set(UnitDSL.model_fields) == _UNIT_DSL_FIELDS

    def test_objective_dsl_fields(self) -> None:
        assert set(ObjectiveDSL.model_fields) == _OBJECTIVE_DSL_FIELDS

    def test_pedagogy_pack_fields(self) -> None:
        assert set(PedagogyPack.model_fields) == _PEDAGOGY_PACK_FIELDS

    def test_slot_spec_fields(self) -> None:
        assert set(SlotSpec.model_fields) == _SLOT_SPEC_FIELDS


class TestClosedVocabFreeze:
    def test_forbidden_mode_vocab(self) -> None:
        assert len(FORBIDDEN_MODE_VOCAB) == 7
        assert "WORKED_EXAMPLE_FIRST" in FORBIDDEN_MODE_VOCAB

    def test_subject_noun_blocklist(self) -> None:
        assert len(SUBJECT_NOUN_BLOCKLIST) == 13
        assert "이차함수" in SUBJECT_NOUN_BLOCKLIST


class TestPilotCorpusStillValidates:
    """동결된 계약이 파일럿 코퍼스를 여전히 통과 — 동결이 실 데이터를 깨지 않음을 증명."""

    def test_pilot_unit_validates(self) -> None:
        unit = yaml.safe_load(
            (_CORPUS / "units_v1" / "quadratic_maxmin.unit.yaml").read_text(encoding="utf-8")
        )
        u = UnitDSL.model_validate(unit)
        assert u.api_version == "unit/0.1"  # api_version 핀
        assert len(u.objectives) == 4

    def test_all_packs_validate(self) -> None:
        for path in sorted((_CORPUS / "pedagogy_packs_v1").glob("*.yaml")):
            pack = PedagogyPack.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
            assert pack.api_version == "1.0"  # 팩 api_version 핀
