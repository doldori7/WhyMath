"""EOS 단원 구조 관측 리포트 테스트 — 결정론·변별력 동결(hermetic).

대상: `whymath_backend.harness.eos_unit_structure_observation_report`(CUR-09 후속 관측).
대부분의 테스트는 `tmp_path`에 만든 소형 픽스처로 검증한다.

**변별력**(CLAUDE.md "변별력 없는 검증 스텝 금지"): 각 테스트는 그 규약이 깨진 구현에서
실제로 실패하는지를 기준으로 짰다.
  - 현행 저장소에서는 제안한 모든 메타데이터/구조가 부재해야 한다.
  - fixture에 가상 필드를 추가하면 `present_fields` 카운트가 실제로 증가해야 한다.
  - YAML에서 `unit_concepts`가 없으면 `unit_concepts_role_present`도 False여야 한다.
  - YAML에 `unit_concepts`가 있지만 원소에 `role`이 없으면 `unit_concepts_role_present`는
    False여야 한다.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from whymath_backend.harness import eos_unit_structure_observation_report as eos


# ──────────────────────────────────────────────────────────────────────────
# 1. AST 추출 — SQLAlchemy 2.0 / Pydantic 형태 모두 컬럼·필드명 추출
# ──────────────────────────────────────────────────────────────────────────
def test_extract_class_assignments_sqlalchemy20() -> None:
    text = """
class AtomNode:
    code: Mapped[str] = mapped_column(sa.Text, primary_key=True)
    sequence: Mapped[int] = mapped_column(sa.Integer)
    order_index: Mapped[int] = mapped_column(sa.Integer)
    sort_order: Mapped[int] = mapped_column(sa.Integer)
"""
    result = eos.extract_class_assignments(text, {"AtomNode"})
    assert result["AtomNode"] == ("code", "order_index", "sequence", "sort_order")


def test_extract_class_assignments_pydantic() -> None:
    text = """
class UnitDSL:
    unit_id: str = Field(...)
    unit_concepts: list[str] = Field(...)
    coverage_weight: float = Field(...)
    order_index: int = Field(...)
"""
    result = eos.extract_class_assignments(text, {"UnitDSL"})
    assert result["UnitDSL"] == ("coverage_weight", "order_index", "unit_concepts", "unit_id")


# ──────────────────────────────────────────────────────────────────────────
# 2. YAML 키 추출 — unit_concepts 없음 / role 없음 / 모두 있음
# ──────────────────────────────────────────────────────────────────────────
def test_extract_unit_yaml_fields_all_absent() -> None:
    text = yaml.safe_dump({"unit_id": "u1", "standard_codes": ["[A]"]}, allow_unicode=True)
    assert eos.extract_unit_yaml_fields(text) == (False, False, False, False)


def test_extract_unit_yaml_fields_non_mapping_raises() -> None:
    text = yaml.safe_dump([{"unit_id": "u1"}], allow_unicode=True)
    with pytest.raises(ValueError, match="mapping"):
        eos.extract_unit_yaml_fields(text)


def test_extract_unit_yaml_fields_all_present() -> None:
    payload = {
        "unit_id": "u1",
        "order_index": 1,
        "coverage_weight": 0.5,
        "unit_concepts": [{"role": "primary"}, {"role": "supporting"}],
    }
    text = yaml.safe_dump(payload, allow_unicode=True)
    assert eos.extract_unit_yaml_fields(text) == (True, True, True, True)


def test_extract_unit_yaml_fields_role_missing() -> None:
    payload = {
        "unit_id": "u1",
        "order_index": 1,
        "coverage_weight": 0.5,
        "unit_concepts": [{"code": "a"}, {"code": "b"}],
    }
    text = yaml.safe_dump(payload, allow_unicode=True)
    assert eos.extract_unit_yaml_fields(text) == (True, True, True, False)


# ──────────────────────────────────────────────────────────────────────────
# 3. 실 저장소 관측 고정 — CUR-09 acceptance
# ──────────────────────────────────────────────────────────────────────────
def test_build_report_current_repo() -> None:
    """CUR-09 acceptance: 현행 저장소에서 EOS 설계 제안 요소는 전부 부재로 고정된다.

    **이 테스트만 hermetic이 아니다** — 실제 저장소의 모델/스키마/코퍼스 파일을 읽는다.
    """
    report = eos.build_report(eos._REPO_ROOT, units_root=eos.DEFAULT_UNITS_ROOT)
    assert report.parse_errors == ()
    assert report.total_present_model_fields == 0
    assert report.total_present_schema_fields == 0
    for obs in report.model_observations:
        assert obs.absent_fields == obs.target_fields
    for obs in report.schema_observations:
        assert obs.absent_fields == obs.target_fields
    for obs in report.corpus_observations:
        assert obs.order_index_present is False
        assert obs.coverage_weight_present is False
        assert obs.unit_concepts_present is False
        assert obs.unit_concepts_role_present is False
    assert report.concept_edge_infra.edge_type_only is True
    assert report.concept_edge_infra.edgetype_enum_members > 0


# ──────────────────────────────────────────────────────────────────────────
# 4. 변별력 — fixture에 가상 필드를 추가하면 관측값이 변해야 한다
# ──────────────────────────────────────────────────────────────────────────
def test_scan_corpus_non_mapping_records_parse_error(tmp_path: Path) -> None:
    """unit YAML 최상위가 mapping이 아니면 parse error를 기록하고 '적재됨'으로 보지 않는다."""
    units_root = tmp_path / "units"
    units_root.mkdir()
    (units_root / "bad.unit.yaml").write_text("- not_a_mapping\n", encoding="utf-8")

    errors: list[eos.ParseError] = []
    observations = eos._scan_corpus(units_root, errors)

    assert len(observations) == 1
    assert observations[0].status == "데이터없음"
    assert observations[0].order_index_present is False
    assert len(errors) == 1
    assert errors[0].source == "bad.unit.yaml"
    assert errors[0].error_type == "ValueError"


def test_extract_class_assignments_excludes_dunder_metadata() -> None:
    """``__tablename__``·``__table_args__`` 같은 클래스 메타데이터는 컬럼으로 세지 않는다."""
    text = """
class ConceptEdge:
    __tablename__ = "concept_edge"
    __table_args__ = {"schema": "public"}
    edge_id: Mapped[int] = mapped_column(primary_key=True)
    edge_type: Mapped[str]
"""
    result = eos.extract_class_assignments(text, {"ConceptEdge"})
    assert result["ConceptEdge"] == ("edge_id", "edge_type")


def test_build_report_fixture_with_fields(tmp_path: Path) -> None:
    """가상 fixture에 제안 필드를 추가하면 관측값이 실제로 증가해야 한다(변별력)."""
    model_dir = tmp_path / "src/backend/whymath_backend/db/models"
    model_dir.mkdir(parents=True)
    (model_dir / "atom_node.py").write_text(
        "class AtomNode:\n"
        "    code: Mapped[str]\n"
        "    sequence: Mapped[int]\n"
        "    order_index: Mapped[int]\n"
        "    sort_order: Mapped[int]\n",
        encoding="utf-8",
    )
    (model_dir / "concept.py").write_text(
        "class ConceptEdge:\n"
        "    edge_id: int\n"
        "    from_concept_id: int\n"
        "    to_concept_id: int\n"
        "    edge_type: str\n"
        "    edge_strength: float\n"
        "    typical_gap_signal: str\n"
        "    notes: str\n"
        "    relation_subtype: str\n"
        "    created_at: str\n",
        encoding="utf-8",
    )

    schema_dir = tmp_path / "src/backend/whymath_backend/schema"
    schema_dir.mkdir(parents=True)
    (schema_dir / "enums.py").write_text(
        "from enum import Enum\n"
        "class EdgeType(Enum):\n"
        "    PREREQUISITE = 'prerequisite'\n"
        "    SIMILAR_TO = 'similar_to'\n",
        encoding="utf-8",
    )
    (schema_dir / "unit_dsl.py").write_text(
        "class UnitDSL:\n"
        "    unit_id: str\n"
        "    unit_concepts: list[str]\n"
        "    coverage_weight: float\n"
        "    order_index: int\n"
        "class ObjectiveDSL:\n"
        "    suffix: str\n"
        "    unit_concepts: list[str]\n"
        "    coverage_weight: float\n"
        "    order_index: int\n",
        encoding="utf-8",
    )

    units_root = tmp_path / "data/corpus/units_v1"
    units_root.mkdir(parents=True)
    payload = {
        "unit_id": "fake",
        "order_index": 1,
        "coverage_weight": 0.5,
        "unit_concepts": [{"role": "primary"}, {"role": "supporting"}],
        "objectives": [],
    }
    (units_root / "fake.unit.yaml").write_text(
        yaml.safe_dump(payload, allow_unicode=True), encoding="utf-8"
    )

    model_targets = {
        "src/backend/whymath_backend/db/models/atom_node.py": {
            "AtomNode": ("sequence", "order_index", "sort_order"),
        },
    }
    schema_targets = {
        "src/backend/whymath_backend/schema/unit_dsl.py": {
            "UnitDSL": ("unit_concepts", "coverage_weight", "order_index"),
            "ObjectiveDSL": ("unit_concepts", "coverage_weight", "order_index"),
        },
    }

    report = eos.build_report(
        tmp_path,
        units_root=units_root,
        model_targets=model_targets,
        schema_targets=schema_targets,
    )

    assert report.parse_errors == ()
    atom_obs = next(obs for obs in report.model_observations if obs.class_name == "AtomNode")
    assert atom_obs.present_fields == ("sequence", "order_index", "sort_order")
    unit_obs = next(obs for obs in report.schema_observations if obs.class_name == "UnitDSL")
    assert unit_obs.present_fields == ("unit_concepts", "coverage_weight", "order_index")
    obj_obs = next(obs for obs in report.schema_observations if obs.class_name == "ObjectiveDSL")
    assert obj_obs.present_fields == ("unit_concepts", "coverage_weight", "order_index")
    corpus_obs = report.corpus_observations[0]
    assert corpus_obs.order_index_present is True
    assert corpus_obs.coverage_weight_present is True
    assert corpus_obs.unit_concepts_present is True
    assert corpus_obs.unit_concepts_role_present is True


# ──────────────────────────────────────────────────────────────────────────
# 5. CLI — exit 0/2만, JSON 산출물 결정론
# ──────────────────────────────────────────────────────────────────────────
def test_cli_exit_zero_on_current_repo(capsys: pytest.CaptureFixture[str]) -> None:
    rc = eos.main([])
    out = capsys.readouterr().out
    assert rc == 0
    assert "# EOS 단원 구조 관측 리포트" in out
    assert "0" in out  # 현재는 부재 0·존재 0 모두 0으로 표시되는 영역이 있음


def test_cli_exit_two_on_missing_repo_root(capsys: pytest.CaptureFixture[str]) -> None:
    rc = eos.main(["--repo-root", "/nonexistent/path/for/eos"])
    assert rc == eos._EXIT_INPUT_ERROR


def test_dump_json_deterministic() -> None:
    report = eos.build_report(eos._REPO_ROOT, units_root=eos.DEFAULT_UNITS_ROOT)
    a = eos.dump_json(report)
    b = eos.dump_json(report)
    assert a == b
