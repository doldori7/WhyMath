"""EOS 단원 구조 관측 리포트 CLI — 빌드타임 결정론 관측(LLM 0·DB 0·HTTP 0).

CUR-09 후속: PR #861에서 수용한 "EOS 지향 교육앱 구축 관점의 성취기준·단원 구조 설계 검토"를
현행 모델·스키마·코퍼스에 대한 관측으로 고정한다. 관측 대상은 네 축이다:

  1. **모델 컬럼 부재**: `sequence`/`order_index`/`sort_order`/`coverage_weight`/
     `weight`/`unit_concept_role`/`unit_alignment` 등 EOS 설계에서 제안한 메타데이터 컬럼이
     아직 `db/models/*`에 존재하지 않는다.
  2. **스키마 필드 부재**: `UnitDSL`·`ObjectiveDSL`에 `unit_concepts`/`coverage_weight`/
     `order_index` 필드가 없다.
  3. **코퍼스 YAML 부재**: `data/corpus/units_v1/*.unit.yaml`에 `order_index`,
     `unit_concepts`·`unit_concepts[].role`, `coverage_weight`가 없다.
  4. **ConceptEdge 적재 인프라**: `ConceptEdge`는 `edge_type` 컬럼만 존재하고, 역할·순서·
     weight 컬럼이 없다. `EdgeType` enum에는 6종이 선언돼 있지만, PREREQUISITE 외 적재는
     인프라가 없어 현재 불가능하다.

**게이트가 아니다**: 이 모듈은 "아직 없다"는 현행 상태를 관측·고정할 뿐, 부재를 차단하지
않는다. 종료 코드는 성공(0)과 입력 오류(2·지정한 저장소 루트에서 대상 파일을 찾을 수 없음)만
구분한다.

**결정론**: 난수 0·시각 의존 0·정렬 고정. 같은 저장소 상태 → 같은 바이트 출력.

**정직 회계**(CLAUDE.md 침묵 실패 금지): 파일 파싱 실패·대상 파일 부재는 조용히 넘어가지
않고 별도 카운트로 보고한다.

사용:
    python -m whymath_backend.harness.eos_unit_structure_observation_report
    python -m whymath_backend.harness.eos_unit_structure_observation_report --json out.json

계층 메모: DB 모델·스키마·코퍼스 파일을 *읽기만* 하는 빌드타임 도구다. SQLAlchemy ORM이나
Pydantic을 import하지 않고, Python AST + PyYAML로 소스/스키마/코퍼스를 정적으로 스캔한다.
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import yaml

__all__ = [
    "ConceptEdgeInfra",
    "CorpusObservation",
    "ModelObservation",
    "ObservationReport",
    "SchemaObservation",
    "build_report",
    "discover_unit_files",
    "dump_json",
    "extract_class_assignments",
    "extract_unit_yaml_fields",
    "main",
    "render_report",
    "report_to_json",
]

_EXIT_OK = 0
_EXIT_INPUT_ERROR = 2

# harness→whymath_backend→backend→src→repo 루트(다른 harness 모듈과 동일 관례).
_REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_UNITS_ROOT = _REPO_ROOT / "data" / "corpus" / "units_v1"

FileStatus = Literal["적재됨", "데이터없음", "파일없음"]

# ──────────────────────────────────────────────────────────────────────────
# 관측 대상 정의 — EOS 설계 검토에서 제안한 메타데이터 컬럼/필드
# ──────────────────────────────────────────────────────────────────────────
MODEL_TARGETS: dict[str, dict[str, tuple[str, ...]]] = {
    "src/backend/whymath_backend/db/models/atom_node.py": {
        "AtomNode": ("sequence", "order_index", "sort_order"),
    },
    "src/backend/whymath_backend/db/models/concept.py": {
        "ConceptEdge": ("role", "sequence", "order_index", "weight", "coverage_weight"),
    },
    "src/backend/whymath_backend/db/models/pedagogy_dsl.py": {
        "UnitSpec": ("sequence", "order_index", "unit_concept_role", "coverage_weight"),
        "LearningObjective": ("sequence", "order_index", "unit_concept_role", "coverage_weight"),
    },
    "src/backend/whymath_backend/db/models/achievement_standard.py": {
        "AchievementStandard": ("coverage_weight", "unit_alignment"),
    },
    "src/backend/whymath_backend/db/models/curriculum_entry.py": {
        "CurriculumEntry": ("coverage_weight", "weight", "sequence", "order_index"),
    },
}

SCHEMA_TARGETS: dict[str, dict[str, tuple[str, ...]]] = {
    "src/backend/whymath_backend/schema/unit_dsl.py": {
        "UnitDSL": ("unit_concepts", "coverage_weight", "order_index"),
        "ObjectiveDSL": ("unit_concepts", "coverage_weight", "order_index"),
    },
}

# 코퍼스 YAML에서 확인할 키/구조.
UNIT_YAML_KEYS = ("order_index", "coverage_weight")
UNIT_YAML_UNIT_CONCEPTS_KEY = "unit_concepts"
UNIT_YAML_UNIT_CONCEPTS_ROLE = "role"


# ──────────────────────────────────────────────────────────────────────────
# 입력 모델 — 관측 결과(불변)
# ──────────────────────────────────────────────────────────────────────────
@dataclass(slots=True, frozen=True)
class ModelObservation:
    """모델 파일 1개·클래스 1개의 제안 컬럼 존재/부재 관측."""

    rel_path: str
    class_name: str
    target_fields: tuple[str, ...]
    present_fields: tuple[str, ...]
    absent_fields: tuple[str, ...]


@dataclass(slots=True, frozen=True)
class SchemaObservation:
    """스키마 파일 1개·클래스 1개의 제안 필드 존재/부재 관측."""

    rel_path: str
    class_name: str
    target_fields: tuple[str, ...]
    present_fields: tuple[str, ...]
    absent_fields: tuple[str, ...]


@dataclass(slots=True, frozen=True)
class CorpusObservation:
    """소단원 YAML 1개의 EOS 구조 키 존재/부재 관측."""

    file_name: str
    status: FileStatus
    order_index_present: bool
    coverage_weight_present: bool
    unit_concepts_present: bool
    unit_concepts_role_present: bool


@dataclass(slots=True, frozen=True)
class ConceptEdgeInfra:
    """concept_edge 적재 인프라 관측."""

    edgetype_enum_members: int
    concept_edge_column_count: int
    concept_edge_columns: tuple[str, ...]
    edge_type_only: bool  # True이면 edge_type 외 역할/순서/weight 컬럼이 없음.


@dataclass(slots=True, frozen=True)
class ParseError:
    """파싱/타입 실패 1건 — 예외 타입명을 포함(CLAUDE.md 침묵 실패 금지)."""

    source: str
    error_type: str
    detail: str


@dataclass(slots=True, frozen=True)
class ObservationReport:
    """전체 관측 결과(불변·렌더/직렬화의 단일 입력)."""

    model_observations: tuple[ModelObservation, ...]
    schema_observations: tuple[SchemaObservation, ...]
    corpus_observations: tuple[CorpusObservation, ...]
    concept_edge_infra: ConceptEdgeInfra
    parse_errors: tuple[ParseError, ...]

    @property
    def total_target_model_fields(self) -> int:
        return sum(len(obs.target_fields) for obs in self.model_observations)

    @property
    def total_present_model_fields(self) -> int:
        return sum(len(obs.present_fields) for obs in self.model_observations)

    @property
    def total_target_schema_fields(self) -> int:
        return sum(len(obs.target_fields) for obs in self.schema_observations)

    @property
    def total_present_schema_fields(self) -> int:
        return sum(len(obs.present_fields) for obs in self.schema_observations)

    @property
    def corpus_files_present(self) -> int:
        return sum(1 for obs in self.corpus_observations if obs.status == "적재됨")

    @property
    def unit_concepts_anywhere(self) -> bool:
        return any(obs.unit_concepts_present for obs in self.corpus_observations)


# ──────────────────────────────────────────────────────────────────────────
# AST 기반 모델/스키마 스캔
# ──────────────────────────────────────────────────────────────────────────
def _is_public_identifier(name: str) -> bool:
    """클래스 메타데이터(``__tablename__`` 등)가 아닌 public identifier만 허용."""
    return not (name.startswith("__") and name.endswith("__"))


def extract_class_assignments(text: str, class_names: set[str]) -> dict[str, tuple[str, ...]]:
    """Python 소스 텍스트에서 지정한 클래스들의 최상위 할당 이름(컬럼/필드명)을 추출(순수).

    SQLAlchemy 2.0(`name: Mapped[...] = mapped_column(...)`)과 Pydantic
    (`name: type = Field(...)`) 모두 `AnnAssign` 형태로 처리한다. legacy
    `name = Column(...)` 할당도 `Assign` 형태로 잡는다.

    ``__tablename__``·``__table_args__`` 같은 클래스 메타데이터는 컬럼/필드로 보지 않는다.
    """
    tree = ast.parse(text)
    result: dict[str, list[str]] = {name: [] for name in class_names}
    for node in tree.body:
        if not isinstance(node, ast.ClassDef) or node.name not in class_names:
            continue
        for item in node.body:
            if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                name = item.target.id
                if _is_public_identifier(name):
                    result[node.name].append(name)
            elif isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name):
                        name = target.id
                        if _is_public_identifier(name):
                            result[node.name].append(name)
    return {name: tuple(sorted(names)) for name, names in result.items()}


def count_enum_members(text: str, enum_name: str) -> int:
    """Python 소스 텍스트에서 `enum_name` 클래스의 Enum 상수 할당 건수를 센다(순수)."""
    tree = ast.parse(text)
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == enum_name:
            count = 0
            for item in node.body:
                if (
                    isinstance(item, ast.Assign)
                    and len(item.targets) == 1
                    and isinstance(item.targets[0], ast.Name)
                ):
                    count += 1
            return count
    return 0


def _scan_model_or_schema_file(
    repo_root: Path,
    rel_path: str,
    targets: dict[str, tuple[str, ...]],
    errors: list[ParseError],
) -> tuple[tuple[str, str, tuple[str, ...], tuple[str, ...]], ...]:
    """대상 파일 1개에 대한 클래스별 제안 항목 존재/부재 집계(순수)."""
    path = repo_root / rel_path
    if not path.is_file():
        errors.append(
            ParseError(
                source=rel_path,
                error_type="FileNotFoundError",
                detail=f"대상 파일 없음: {path}",
            )
        )
        return ()
    try:
        text = path.read_text(encoding="utf-8")
        assignments = extract_class_assignments(text, set(targets))
    except Exception as exc:  # noqa: BLE001 — 파일 단위 격리, 예외 타입명 보고
        errors.append(
            ParseError(
                source=rel_path,
                error_type=type(exc).__name__,
                detail=str(exc)[:200],
            )
        )
        return ()
    rows: list[tuple[str, str, tuple[str, ...], tuple[str, ...]]] = []
    for class_name, target_fields in targets.items():
        present = tuple(f for f in target_fields if f in assignments.get(class_name, ()))
        absent = tuple(f for f in target_fields if f not in assignments.get(class_name, ()))
        rows.append((rel_path, class_name, present, absent))
    return tuple(rows)


# ──────────────────────────────────────────────────────────────────────────
# 코퍼스 YAML 스캔
# ──────────────────────────────────────────────────────────────────────────
def discover_unit_files(units_root: Path) -> tuple[Path, ...]:
    """`data/corpus/units_v1/*.unit.yaml`을 파일명 오름차순으로 탐색(결정론)."""
    if not units_root.is_dir():
        return ()
    return tuple(sorted(units_root.glob("*.unit.yaml"), key=lambda p: p.name))


def extract_unit_yaml_fields(text: str) -> tuple[bool, bool, bool, bool]:
    """소단원 YAML 텍스트 → (order_index, coverage_weight, unit_concepts, unit_concepts_role).

    `unit_concepts_role`은 `unit_concepts`가 리스트이고, 원소 dict 중 `role` 키를 1개 이상
    가진 경우에만 True다.

    Raises:
        ValueError: YAML 최상위가 mapping이 아닌 경우(리스트·스칼라·None 등).
    """
    payload = yaml.safe_load(text)
    if not isinstance(payload, dict):
        raise ValueError(f"소단원 YAML 최상위가 mapping이 아님: {type(payload).__name__}")

    order_index_present = UNIT_YAML_KEYS[0] in payload
    coverage_weight_present = UNIT_YAML_KEYS[1] in payload
    unit_concepts_present = UNIT_YAML_UNIT_CONCEPTS_KEY in payload
    unit_concepts_role_present = False
    if unit_concepts_present:
        unit_concepts = payload[UNIT_YAML_UNIT_CONCEPTS_KEY]
        if isinstance(unit_concepts, list):
            unit_concepts_role_present = any(
                isinstance(item, dict) and UNIT_YAML_UNIT_CONCEPTS_ROLE in item
                for item in unit_concepts
            )
    return (
        order_index_present,
        coverage_weight_present,
        unit_concepts_present,
        unit_concepts_role_present,
    )


def _scan_corpus(units_root: Path, errors: list[ParseError]) -> tuple[CorpusObservation, ...]:
    """소단원 YAML 전체 → EOS 구조 키 존재 관측(순수)."""
    paths = discover_unit_files(units_root)
    if not paths:
        status: FileStatus = "데이터없음" if units_root.is_dir() else "파일없음"
        return (
            CorpusObservation(
                file_name=str(units_root),
                status=status,
                order_index_present=False,
                coverage_weight_present=False,
                unit_concepts_present=False,
                unit_concepts_role_present=False,
            ),
        )
    observations: list[CorpusObservation] = []
    for path in paths:
        file_status: FileStatus = "데이터없음"
        try:
            text = path.read_text(encoding="utf-8")
            order_index, coverage_weight, unit_concepts, role = extract_unit_yaml_fields(text)
            file_status = "적재됨"
        except Exception as exc:  # noqa: BLE001 — 파일 단위 격리
            errors.append(
                ParseError(
                    source=path.name,
                    error_type=type(exc).__name__,
                    detail=str(exc)[:200],
                )
            )
            order_index = coverage_weight = unit_concepts = role = False
        observations.append(
            CorpusObservation(
                file_name=path.name,
                status=file_status,
                order_index_present=order_index,
                coverage_weight_present=coverage_weight,
                unit_concepts_present=unit_concepts,
                unit_concepts_role_present=role,
            )
        )
    return tuple(observations)


# ──────────────────────────────────────────────────────────────────────────
# ConceptEdge 인프라 스캔
# ──────────────────────────────────────────────────────────────────────────
def _scan_concept_edge_infra(repo_root: Path, errors: list[ParseError]) -> ConceptEdgeInfra:
    """concept.py에서 ConceptEdge 컬럼을, schema/enums.py에서 EdgeType 멤버 수를 관측(순수).

    EdgeType enum은 `db/models/concept.py`에서 import되는 것이 아니라
    `schema/enums.py`에 정의돼 있으므로, 정확한 멤버 수를 얻으려면 enum 정의 원천을
    스캔해야 한다.
    """
    concept_path = repo_root / "src/backend/whymath_backend/db/models/concept.py"
    enums_path = repo_root / "src/backend/whymath_backend/schema/enums.py"

    if not concept_path.is_file():
        errors.append(
            ParseError(
                source="concept.py",
                error_type="FileNotFoundError",
                detail=f"대상 파일 없음: {concept_path}",
            )
        )
    if not enums_path.is_file():
        errors.append(
            ParseError(
                source="schema/enums.py",
                error_type="FileNotFoundError",
                detail=f"대상 파일 없음: {enums_path}",
            )
        )
    if not concept_path.is_file() or not enums_path.is_file():
        return ConceptEdgeInfra(
            edgetype_enum_members=0,
            concept_edge_column_count=0,
            concept_edge_columns=(),
            edge_type_only=True,
        )

    try:
        enums_text = enums_path.read_text(encoding="utf-8")
        edgetype_members = count_enum_members(enums_text, "EdgeType")
    except Exception as exc:  # noqa: BLE001
        errors.append(
            ParseError(
                source="schema/enums.py",
                error_type=type(exc).__name__,
                detail=str(exc)[:200],
            )
        )
        edgetype_members = 0

    try:
        concept_text = concept_path.read_text(encoding="utf-8")
        assignments = extract_class_assignments(concept_text, {"ConceptEdge"})
        columns = assignments.get("ConceptEdge", ())
    except Exception as exc:  # noqa: BLE001
        errors.append(
            ParseError(
                source="concept.py",
                error_type=type(exc).__name__,
                detail=str(exc)[:200],
            )
        )
        columns = ()

    return ConceptEdgeInfra(
        edgetype_enum_members=edgetype_members,
        concept_edge_column_count=len(columns),
        concept_edge_columns=columns,
        edge_type_only=not any(
            name in columns
            for name in ("role", "sequence", "order_index", "weight", "coverage_weight")
        ),
    )


# ──────────────────────────────────────────────────────────────────────────
# 집계 — 관측 리포트
# ──────────────────────────────────────────────────────────────────────────
def build_report(
    repo_root: Path,
    *,
    units_root: Path | None = None,
    model_targets: dict[str, dict[str, tuple[str, ...]]] | None = None,
    schema_targets: dict[str, dict[str, tuple[str, ...]]] | None = None,
) -> ObservationReport:
    """저장소 루트 → EOS 단원 구조 관측 리포트(순수·부작용 0).

    `model_targets`/`schema_targets`를 지정하면 단위 테스트에서 가상 fixture를 스캔할 수 있다.
    기본값은 모듈 상수 `MODEL_TARGETS`/`SCHEMA_TARGETS`다.
    """
    errors: list[ParseError] = []

    model_obs: list[ModelObservation] = []
    for rel_path, targets in (model_targets or MODEL_TARGETS).items():
        for rel, class_name, present, absent in _scan_model_or_schema_file(
            repo_root, rel_path, targets, errors
        ):
            model_obs.append(
                ModelObservation(
                    rel_path=rel,
                    class_name=class_name,
                    target_fields=targets[class_name],
                    present_fields=present,
                    absent_fields=absent,
                )
            )

    schema_obs: list[SchemaObservation] = []
    for rel_path, targets in (schema_targets or SCHEMA_TARGETS).items():
        for rel, class_name, present, absent in _scan_model_or_schema_file(
            repo_root, rel_path, targets, errors
        ):
            schema_obs.append(
                SchemaObservation(
                    rel_path=rel,
                    class_name=class_name,
                    target_fields=targets[class_name],
                    present_fields=present,
                    absent_fields=absent,
                )
            )

    corpus_obs = _scan_corpus(units_root or DEFAULT_UNITS_ROOT, errors)
    concept_edge = _scan_concept_edge_infra(repo_root, errors)

    return ObservationReport(
        model_observations=tuple(model_obs),
        schema_observations=tuple(schema_obs),
        corpus_observations=tuple(corpus_obs),
        concept_edge_infra=concept_edge,
        parse_errors=tuple(errors),
    )


# ──────────────────────────────────────────────────────────────────────────
# 렌더 — 사람이 읽는 마크다운 + 기계가 읽는 JSON
# ──────────────────────────────────────────────────────────────────────────
def _bool_badge(value: bool) -> str:
    return "✅" if value else "❌"


def _pct(numerator: int, denominator: int) -> str:
    if denominator == 0:
        return "데이터없음"
    return f"{numerator / denominator * 100:.1f}%"


def render_report(report: ObservationReport) -> str:
    """관측 결과를 마크다운으로 렌더(순수)."""
    lines: list[str] = [
        "# EOS 단원 구조 관측 리포트 (CUR-09 후속)",
        "",
        "> 관측 리포트다 — **exit 게이트가 아니다**. EOS 설계 검토에서 제안한 메타데이터/구조"
        " 요소가 현행 저장소에 얼마나 반영됐는지 고정한다.",
        "",
        "## 1. 모델 컬럼 관측",
        "",
        "| 파일 | 클래스 | 제안 컬럼 수 | 존재 | 부재 | 부재 목록 |",
        "|---|---|---:|---:|---:|---|",
    ]
    for model_obs in report.model_observations:
        path = model_obs.rel_path
        name = model_obs.class_name
        n_target = len(model_obs.target_fields)
        n_present = len(model_obs.present_fields)
        n_absent = len(model_obs.absent_fields)
        absent_list = ", ".join(f"`{f}`" for f in model_obs.absent_fields) or "-"
        lines.append(
            f"| `{path}` | `{name}` | {n_target} | {n_present} | {n_absent} | {absent_list} |"
        )
    model_pct = _pct(report.total_present_model_fields, report.total_target_model_fields)
    lines += [
        "",
        f"- 모델 제안 컬럼 합계: **{report.total_present_model_fields}** / "
        f"{report.total_target_model_fields} ({model_pct})",
        "",
        "## 2. 스키마 필드 관측",
        "",
        "| 파일 | 클래스 | 제안 필드 수 | 존재 | 부재 | 부재 목록 |",
        "|---|---|---:|---:|---:|---|",
    ]
    for schema_obs in report.schema_observations:
        path = schema_obs.rel_path
        name = schema_obs.class_name
        n_target = len(schema_obs.target_fields)
        n_present = len(schema_obs.present_fields)
        n_absent = len(schema_obs.absent_fields)
        absent_list = ", ".join(f"`{f}`" for f in schema_obs.absent_fields) or "-"
        lines.append(
            f"| `{path}` | `{name}` | {n_target} | {n_present} | {n_absent} | {absent_list} |"
        )
    schema_pct = _pct(report.total_present_schema_fields, report.total_target_schema_fields)
    lines += [
        "",
        f"- 스키마 제안 필드 합계: **{report.total_present_schema_fields}** / "
        f"{report.total_target_schema_fields} ({schema_pct})",
        "",
        "## 3. 코퍼스 YAML 관측",
        "",
        "| 파일 | 상태 | order_index | coverage_weight | unit_concepts | unit_concepts[].role |",
        "|---|---|---|---|---|---|",
    ]
    for corpus_obs in report.corpus_observations:
        lines.append(
            f"| `{corpus_obs.file_name}` | {corpus_obs.status} | "
            f"{_bool_badge(corpus_obs.order_index_present)} | "
            f"{_bool_badge(corpus_obs.coverage_weight_present)} | "
            f"{_bool_badge(corpus_obs.unit_concepts_present)} | "
            f"{_bool_badge(corpus_obs.unit_concepts_role_present)} |"
        )
    lines += [
        "",
        f"- 소단원 YAML 파일 수: **{report.corpus_files_present}**",
        f"- 어디에도 `unit_concepts` 없음: **{not report.unit_concepts_anywhere}**",
        "",
        "## 4. ConceptEdge 적재 인프라",
        "",
        "| 항목 | 값 |",
        "|---|---|",
        f"| EdgeType enum 멤버 수 | {report.concept_edge_infra.edgetype_enum_members} |",
        f"| ConceptEdge 컬럼 수 | {report.concept_edge_infra.concept_edge_column_count} |",
        f"| edge_type 외 역할·순서·weight 컬럼 부재 | {report.concept_edge_infra.edge_type_only} |",
        "",
        "## 5. 정직 회계",
        "",
        "> 조용히 버리지 않는다 — 아래가 모두 0이어야 위 수치를 액면 그대로 읽을 수 있다.",
        "",
        "| 항목 | 건수 |",
        "|---|---:|",
        f"| 파일 파싱 실패 | {len(report.parse_errors)} |",
    ]
    if report.parse_errors:
        lines += ["", "### 5.1 파싱 실패", ""]
        for err in report.parse_errors:
            lines.append(f"- `{err.source}`: {err.error_type} — {err.detail}")
    lines.append("")
    return "\n".join(lines)


def report_to_json(report: ObservationReport) -> dict[str, Any]:
    """리포트 → JSON 직렬화 가능 dict."""
    return {
        "model_observations": [
            {
                "rel_path": model_obs.rel_path,
                "class_name": model_obs.class_name,
                "target_fields": list(model_obs.target_fields),
                "present_fields": list(model_obs.present_fields),
                "absent_fields": list(model_obs.absent_fields),
            }
            for model_obs in report.model_observations
        ],
        "schema_observations": [
            {
                "rel_path": schema_obs.rel_path,
                "class_name": schema_obs.class_name,
                "target_fields": list(schema_obs.target_fields),
                "present_fields": list(schema_obs.present_fields),
                "absent_fields": list(schema_obs.absent_fields),
            }
            for schema_obs in report.schema_observations
        ],
        "corpus_observations": [
            {
                "file_name": corpus_obs.file_name,
                "status": corpus_obs.status,
                "order_index_present": corpus_obs.order_index_present,
                "coverage_weight_present": corpus_obs.coverage_weight_present,
                "unit_concepts_present": corpus_obs.unit_concepts_present,
                "unit_concepts_role_present": corpus_obs.unit_concepts_role_present,
            }
            for corpus_obs in report.corpus_observations
        ],
        "concept_edge_infra": {
            "edgetype_enum_members": report.concept_edge_infra.edgetype_enum_members,
            "concept_edge_column_count": report.concept_edge_infra.concept_edge_column_count,
            "concept_edge_columns": list(report.concept_edge_infra.concept_edge_columns),
            "edge_type_only": report.concept_edge_infra.edge_type_only,
        },
        "summary": {
            "total_target_model_fields": report.total_target_model_fields,
            "total_present_model_fields": report.total_present_model_fields,
            "total_target_schema_fields": report.total_target_schema_fields,
            "total_present_schema_fields": report.total_present_schema_fields,
            "corpus_files_present": report.corpus_files_present,
            "unit_concepts_anywhere": report.unit_concepts_anywhere,
        },
        "honest_accounting": {
            "parse_error_count": len(report.parse_errors),
            "parse_errors": [
                {"source": e.source, "error_type": e.error_type, "detail": e.detail}
                for e in report.parse_errors
            ],
        },
    }


def dump_json(report: ObservationReport) -> str:
    """JSON 직렬화 — 키 정렬·들여쓰기 고정으로 같은 입력에 같은 바이트를 보장(결정론)."""
    return json.dumps(report_to_json(report), ensure_ascii=False, indent=2, sort_keys=True) + "\n"


# ──────────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────────
def _safe_print(text: str) -> None:
    """Windows 콘솔(cp949) 등에서 UnicodeEncodeError를 피하기 위해 stdout.buffer로 UTF-8 출력."""
    try:
        encoded = text.encode("utf-8")
        sys.stdout.buffer.write(encoded)
        sys.stdout.buffer.write(b"\n")
    except Exception as exc:  # noqa: BLE001 — 폴백이어서 예외 타입만 stderr에 보고
        exc_name = type(exc).__name__
        print(f"[eos_report] UTF-8 buffer 실패({exc_name}); print 폴백", file=sys.stderr)
        print(text)


def main(argv: list[str] | None = None) -> int:
    """CLI 엔트리 — 관측 리포트를 stdout에 출력. **0=성공 / 2=입력 오류**."""
    parser = argparse.ArgumentParser(
        prog="python -m whymath_backend.harness.eos_unit_structure_observation_report",
        description=(
            "EOS 단원 구조 관측 리포트(CUR-09 후속) — 모델/스키마/코퍼스의 "
            "sequence·order_index·coverage_weight·unit_concepts 등 EOS 설계 메타데이터 반영 현황. "
            "결정론·게이트 아님(exit 0/2)."
        ),
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=_REPO_ROOT,
        help=f"저장소 루트 디렉터리(기본 {_REPO_ROOT}).",
    )
    parser.add_argument(
        "--units-root",
        type=Path,
        default=None,
        help="소단원 YAML 루트 디렉터리(미지정 시 repo-root/data/corpus/units_v1).",
    )
    parser.add_argument(
        "--json",
        dest="json_path",
        type=Path,
        default=None,
        help="JSON 산출물 경로(선택·미지정이면 stdout 마크다운만).",
    )
    args = parser.parse_args(argv)

    units_root = args.units_root or (args.repo_root / "data" / "corpus" / "units_v1")
    report = build_report(args.repo_root, units_root=units_root)
    _safe_print(render_report(report))
    if args.json_path is not None:
        args.json_path.parent.mkdir(parents=True, exist_ok=True)
        args.json_path.write_text(dump_json(report), encoding="utf-8")
        _safe_print(f"JSON 산출물: {args.json_path}")

    if report.parse_errors:
        for err in report.parse_errors:
            print(f"입력 오류 — {err.source}: {err.error_type} — {err.detail}", file=sys.stderr)
        return _EXIT_INPUT_ERROR
    return _EXIT_OK


if __name__ == "__main__":  # pragma: no cover — 엔트리포인트
    sys.exit(main())
