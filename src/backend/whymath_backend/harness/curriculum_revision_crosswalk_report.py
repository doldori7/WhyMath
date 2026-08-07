"""교육과정 개정판 어휘 crosswalk 관측 리포트 CLI — 빌드타임 결정론 관측(LLM 0·DB 0·HTTP 0).

배경(CUR-01): 교육과정 개정판 표기가 **3개 어휘 공간**으로 분열돼 있다.
  ① `standards_v1/standards.json`의 `curriculum_revision` — 한글 `"2022 개정"`/`"2015 개정"`
  ② `units_v1/*.unit.yaml`의 `curriculum_rev` — 연도만 `"2022"`
  ③ `problem_bank*/problems.jsonl`의 `curriculum_version` — enum 값 `"2022_REVISION"` 등
     (`schema.enums.Curriculum` — `Problem.curriculum_version`이 이 enum을 쓴다)
  ④ `db/models/curriculum_entry.py`의 `curriculum_revision` — **대응 코퍼스를 찾지 못함**
     (DB ORM·Pydantic 스키마만 존재, JSON/YAML 코퍼스 파일 없음 — 조사 결과, `data/corpus/`
     전체 탐색으로 확인). 이 축은 억지로 파일을 가정하지 않고 **"관측 불가"로 정직하게
     표시**한다(CLAUDE.md 날조 금지). 향후 `data/corpus/curriculum_entry*/` 같은 코퍼스가
     생기면 이 모듈에 로더를 추가해 배선한다.

이 모듈은 세 코퍼스(①②③)를 *읽기만* 하고, 어휘 간 crosswalk 매핑표 하나로 정규 개정판 키
(`Curriculum` enum 값)로 정규화한 뒤, 축별 분포·미매핑 값·발산(divergence) 건수를 관측한다.

**게이트가 아니다**(`problem_bank_coverage`와 같은 축의 관측 리포트 원칙): 발산이 아무리 커도
**exit 1을 내지 않는다** — 종료 코드는 성공(0)과 입력 오류(2·표준 대장 부재/구조 오류, 명시
지정한 코퍼스 부재)만 구분한다. 3어휘를 1어휘로 통합하는 실제 마이그레이션(스키마 변경)은
**이 모듈의 범위 밖**이다 — 이 모듈은 crosswalk 매핑 + 발산 건수 관측만 낸다.

**정직 회계**(CLAUDE.md 침묵 실패 금지): 파싱 실패·필드 누락·crosswalk 매핑표에 없는 값은
조용히 버리지 않고 **전부 별도 카운트로 보고**한다("미매핑"과 "값 없음(필드 누락)"은 구분).

**hermetic 예외 — `schema.enums.Curriculum`을 import한다**: `problem_bank_coverage`는 "코퍼스가
스키마 enum과 어긋나도 조용히 죽지 않기 위해" 의도적으로 `schema.enums`조차 import하지 않는다.
이 모듈은 그 반대 목적(enum ↔ 코퍼스 3어휘 정합 자체를 비교하는 것이 존재 이유)이라 `Curriculum`
enum을 **정규 개정판 키의 정의 원천**으로 명시적으로 가져온다. 이 import는 순수 `Enum` 클래스
읽기일 뿐 DB·ORM·API·LLM 어느 것도 건드리지 않으므로 hermetic 원칙(DB/LLM/HTTP 접속 0)은
그대로 유지된다.

**결정론**: 난수 0·시각 의존 0·정렬 고정(정렬 기준은 각 절 참조). 같은 입력 파일 → 같은 바이트
출력(`--json` 산출물 포함).

사용:
    python -m whymath_backend.harness.curriculum_revision_crosswalk_report
    python -m whymath_backend.harness.curriculum_revision_crosswalk_report --json out/crosswalk.json

계층 메모(CLAUDE.md 7계층): 코퍼스 JSON/JSONL/YAML을 *읽기만* 하는 빌드타임 도구다(L1 데이터
조회 전용, 아무것도 쓰지 않는다). DB·ORM·API·LLM 어느 것도 호출하지 않는다.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import yaml

from whymath_backend.schema.enums import Curriculum

__all__ = [
    "AXIS_CURRICULUM_ENTRY",
    "AXIS_PROBLEM_BANK",
    "AXIS_STANDARDS",
    "AXIS_UNIT_SPEC",
    "AxisLoad",
    "AxisObservation",
    "CROSSWALK",
    "CrosswalkReport",
    "MISSING_VALUE",
    "ParseError",
    "UNMAPPED_VALUE",
    "build_report",
    "canonicalize",
    "curriculum_entry_axis_unavailable",
    "discover_problem_bank_files",
    "discover_unit_files",
    "load_problem_bank_axis",
    "load_standards_axis",
    "load_unit_spec_axis",
    "main",
    "parse_problem_bank_line",
    "parse_standards_payload",
    "parse_unit_yaml",
    "render_report",
    "report_to_json",
]

_EXIT_OK = 0
_EXIT_INPUT_ERROR = 2

# harness→whymath_backend→backend→src→repo 루트(problem_bank_coverage와 동일 관례).
_REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_CORPUS_ROOT = _REPO_ROOT / "data" / "corpus"
DEFAULT_STANDARDS_PATH = DEFAULT_CORPUS_ROOT / "standards_v1" / "standards.json"
DEFAULT_UNITS_ROOT = DEFAULT_CORPUS_ROOT / "units_v1"

UNIT_FILE_GLOB = "*.unit.yaml"
CORPUS_DIR_GLOB = "problem_bank*"
CORPUS_FILE_NAME = "problems.jsonl"

# ──────────────────────────────────────────────────────────────────────────
# 축(어휘 공간) 이름 — 렌더·JSON 열 순서 정본
# ──────────────────────────────────────────────────────────────────────────
AXIS_STANDARDS = "standards_v1.curriculum_revision"
AXIS_UNIT_SPEC = "units_v1.curriculum_rev"
AXIS_PROBLEM_BANK = "problem_bank.curriculum_version"
AXIS_CURRICULUM_ENTRY = "curriculum_entry.curriculum_revision"

# 실측 축(3어휘) — 발산·전역분포 계산 대상. curriculum_entry는 관측 자체가 없어 제외.
MEASURED_AXES: tuple[str, ...] = (AXIS_STANDARDS, AXIS_UNIT_SPEC, AXIS_PROBLEM_BANK)
ALL_AXES: tuple[str, ...] = (*MEASURED_AXES, AXIS_CURRICULUM_ENTRY)

AxisStatus = Literal["적재됨", "비어있음", "데이터없음", "대응코퍼스없음"]

# 정직 회계용 자리표시 키.
MISSING_VALUE = "(값 없음)"
UNMAPPED_VALUE = "(미매핑)"

# ──────────────────────────────────────────────────────────────────────────
# crosswalk 매핑표 — 이 모듈의 핵심 신규 로직(단 하나)
# ──────────────────────────────────────────────────────────────────────────
# 3어휘(한글 "OO 개정"·연도만 "OO"·enum 값 "OO_REVISION")를 `Curriculum` enum 값(정규 개정판
# 키)으로 매핑한다. 매핑표에 없는 값은 조용히 버리지 않고 "미매핑"으로 카운트한다(정직 회계).
CROSSWALK: dict[str, str] = {
    # ① standards_v1.curriculum_revision — 한글 "OO 개정" 표기.
    "2022 개정": Curriculum.REVISION_2022.value,
    "2015 개정": Curriculum.REVISION_2015.value,
    "2009 개정": Curriculum.REVISION_2009.value,
    # ② units_v1.curriculum_rev — 연도만 표기.
    "2022": Curriculum.REVISION_2022.value,
    "2015": Curriculum.REVISION_2015.value,
    "2009": Curriculum.REVISION_2009.value,
    # ③ problem_bank.curriculum_version — enum 값 그대로(이미 정규 키와 동형이지만, 매핑표에
    #    명시해 "정의역 전체를 이 표 하나로 설명한다"는 계약을 지킨다).
    Curriculum.REVISION_2022.value: Curriculum.REVISION_2022.value,
    Curriculum.REVISION_2015.value: Curriculum.REVISION_2015.value,
    Curriculum.REVISION_2009.value: Curriculum.REVISION_2009.value,
}

# enum에 정의된 정규 개정판 키 전량(사전순 — 결정론). "실 데이터 0건" 판정의 분모.
CANONICAL_REVISIONS: tuple[str, ...] = tuple(sorted(member.value for member in Curriculum))


def canonicalize(raw_value: str) -> str | None:
    """원시 어휘 문자열 → 정규 개정판 키(순수). 매핑표에 없으면 `None`(호출자가 "미매핑" 처리)."""
    return CROSSWALK.get(raw_value)


# ──────────────────────────────────────────────────────────────────────────
# 입력 모델 — 축 관측·파싱 실패(순수 데이터·불변)
# ──────────────────────────────────────────────────────────────────────────
@dataclass(slots=True, frozen=True)
class ParseError:
    """코퍼스 레코드 1건의 파싱/타입 실패 — 조용히 버리지 않고 보고하기 위한 기록.

    `error_type`은 예외 타입명(CLAUDE.md "침묵 실패 금지 — 예외 타입명을 로그에 포함").
    """

    axis: str
    source: str
    line_no: int | None
    error_type: str
    detail: str


@dataclass(slots=True, frozen=True)
class AxisObservation:
    """축(어휘 공간) 1건의 원시값 관측(정규화 이전, 불변).

    `raw_value`가 `None`이면 "필드 자체가 없음"(정직 회계 — 미매핑과 다른 사유)이다.
    """

    axis: str
    source: str
    line_no: int | None
    raw_value: str | None


@dataclass(slots=True, frozen=True)
class AxisLoad:
    """축 1종의 적재 결과 — 상태·관측·파싱 실패(불변).

    `status`는 "데이터없음"(코퍼스 파일/디렉터리가 없음)과 "대응코퍼스없음"(애초에 대응하는
    코퍼스 파일 자체가 이 저장소에 존재하지 않는다고 조사로 확인됨 — `curriculum_entry` 전용)을
    구분한다. 전자는 "이번엔 못 찾음", 후자는 "찾을 파일이 없다고 이미 확인함"이라는 의미 차이다.
    """

    axis: str
    status: AxisStatus
    sources: tuple[str, ...]
    observations: tuple[AxisObservation, ...]
    parse_errors: tuple[ParseError, ...]


# ──────────────────────────────────────────────────────────────────────────
# 로더 ① — standards_v1/standards.json (curriculum_revision)
# ──────────────────────────────────────────────────────────────────────────
def parse_standards_payload(
    payload: object, *, source: str
) -> tuple[tuple[AxisObservation, ...], tuple[ParseError, ...]]:
    """성취기준 JSON(dict) → (관측, 파싱실패)(순수).

    최상위가 dict가 아니거나 `standards` 배열이 없으면 ValueError로 즉시 실패한다(구조 오류는
    개별 레코드 실패와 달리 축 전체를 신뢰할 수 없게 만들므로 CLI에서 exit 2로 처리한다 —
    `problem_bank_coverage.load_standards`와 동일 원칙). 개별 레코드의 타입 오류는 그 레코드만
    `ParseError`로 격리하고 나머지는 계속 집계한다(정직 회계).
    """
    if not isinstance(payload, dict):
        raise ValueError(f"성취기준 JSON 최상위가 object가 아님(type={type(payload).__name__})")
    raw = payload.get("standards")
    if not isinstance(raw, list):
        raise ValueError("성취기준 JSON에 'standards' 배열이 없음")

    observations: list[AxisObservation] = []
    errors: list[ParseError] = []
    for idx, item in enumerate(raw):
        line_no = idx + 1
        if not isinstance(item, dict):
            errors.append(
                ParseError(
                    axis=AXIS_STANDARDS,
                    source=source,
                    line_no=line_no,
                    error_type="TypeError",
                    detail=f"standards[{idx}]가 object가 아님(type={type(item).__name__})",
                )
            )
            continue
        value = item.get("curriculum_revision")
        if value is not None and not isinstance(value, str):
            errors.append(
                ParseError(
                    axis=AXIS_STANDARDS,
                    source=source,
                    line_no=line_no,
                    error_type="TypeError",
                    detail=f"curriculum_revision가 문자열이 아님(type={type(value).__name__})",
                )
            )
            continue
        observations.append(
            AxisObservation(axis=AXIS_STANDARDS, source=source, line_no=line_no, raw_value=value)
        )
    return tuple(observations), tuple(errors)


def load_standards_axis(path: Path) -> AxisLoad:
    """`standards.json` 1개 → `AxisLoad`. 구조 오류는 그대로 예외를 올려 CLI가 exit 2로 처리한다.

    파일 자체가 없으면 예외 없이 "데이터없음" 상태로 반환한다(다른 두 로더와 동형 — 부재 자체는
    구조 오류가 아니다).
    """
    if not path.is_file():
        return AxisLoad(
            axis=AXIS_STANDARDS, status="데이터없음", sources=(), observations=(), parse_errors=()
        )
    payload = json.loads(path.read_text(encoding="utf-8"))
    observations, errors = parse_standards_payload(payload, source=path.name)
    status: AxisStatus = "적재됨" if observations else "비어있음"
    return AxisLoad(
        axis=AXIS_STANDARDS,
        status=status,
        sources=(path.name,),
        observations=observations,
        parse_errors=errors,
    )


# ──────────────────────────────────────────────────────────────────────────
# 로더 ② — units_v1/*.unit.yaml (curriculum_rev)
# ──────────────────────────────────────────────────────────────────────────
def discover_unit_files(units_root: Path) -> tuple[Path, ...]:
    """`units_v1/*.unit.yaml`을 파일명 오름차순으로 탐색(결정론). `_provenance.json` 등은 제외."""
    if not units_root.is_dir():
        return ()
    found = [p for p in units_root.glob(UNIT_FILE_GLOB) if p.is_file()]
    return tuple(sorted(found, key=lambda p: p.name))


def parse_unit_yaml(text: str, *, source: str) -> AxisObservation:
    """단원 DSL YAML 텍스트 1개 → 축 관측(순수). 실패는 예외로 올려 호출자가 `ParseError`로 담는다.

    `yaml.safe_load`만 쓴다(CLAUDE.md 방침 — 임의 객체 역직렬화 금지). 단원 파일 1개 = 관측 1건
    (`curriculum_rev`는 단원 DSL의 최상위 단일 필드 — `schema/unit_dsl.py` 정본).
    """
    payload = yaml.safe_load(text)
    if not isinstance(payload, dict):
        raise TypeError(f"단원 YAML 최상위가 object가 아님(type={type(payload).__name__})")
    value = payload.get("curriculum_rev")
    if value is not None and not isinstance(value, str):
        raise TypeError(f"curriculum_rev가 문자열이 아님(type={type(value).__name__})")
    return AxisObservation(axis=AXIS_UNIT_SPEC, source=source, line_no=None, raw_value=value)


def load_unit_spec_axis(units_root: Path) -> AxisLoad:
    """`units_v1/*.unit.yaml` 전체 → `AxisLoad`. 파일 단위 파싱 실패는 그 파일만 격리한다."""
    paths = discover_unit_files(units_root)
    if not paths:
        return AxisLoad(
            axis=AXIS_UNIT_SPEC, status="데이터없음", sources=(), observations=(), parse_errors=()
        )
    observations: list[AxisObservation] = []
    errors: list[ParseError] = []
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8")
            observations.append(parse_unit_yaml(text, source=path.name))
        except Exception as exc:  # noqa: BLE001 — 파일 단위 격리·예외 타입명을 그대로 보고
            errors.append(
                ParseError(
                    axis=AXIS_UNIT_SPEC,
                    source=path.name,
                    line_no=None,
                    error_type=type(exc).__name__,
                    detail=str(exc)[:200],
                )
            )
    status: AxisStatus = "적재됨" if observations else "비어있음"
    return AxisLoad(
        axis=AXIS_UNIT_SPEC,
        status=status,
        sources=tuple(p.name for p in paths),
        observations=tuple(observations),
        parse_errors=tuple(errors),
    )


# ──────────────────────────────────────────────────────────────────────────
# 로더 ③ — problem_bank*/problems.jsonl (curriculum_version)
# ──────────────────────────────────────────────────────────────────────────
def discover_problem_bank_files(corpus_root: Path) -> tuple[Path, ...]:
    """`problem_bank*/problems.jsonl`을 디렉터리명 오름차순으로 탐색(결정론)."""
    if not corpus_root.is_dir():
        return ()
    found = [
        child / CORPUS_FILE_NAME for child in corpus_root.glob(CORPUS_DIR_GLOB) if child.is_dir()
    ]
    return tuple(sorted(found, key=lambda p: p.parent.name))


def parse_problem_bank_line(raw: str, *, source: str, line_no: int) -> AxisObservation:
    """JSONL 한 줄 → 축 관측(순수). 실패는 예외로 올려 호출자가 `ParseError`로 담는다."""
    obj = json.loads(raw)
    if not isinstance(obj, dict):
        raise TypeError(f"레코드가 object가 아님(type={type(obj).__name__})")
    value = obj.get("curriculum_version")
    if value is not None and not isinstance(value, str):
        raise TypeError(f"curriculum_version가 문자열이 아님(type={type(value).__name__})")
    return AxisObservation(axis=AXIS_PROBLEM_BANK, source=source, line_no=line_no, raw_value=value)


def _load_problem_bank_file(path: Path, *, name: str) -> AxisLoad:
    """`problems.jsonl` 1개 → `AxisLoad`(파일 부재도 예외 없이 상태로 표현)."""
    if not path.is_file():
        return AxisLoad(
            axis=AXIS_PROBLEM_BANK,
            status="데이터없음",
            sources=(),
            observations=(),
            parse_errors=(),
        )
    observations: list[AxisObservation] = []
    errors: list[ParseError] = []
    text = path.read_text(encoding="utf-8")
    for line_no, raw in enumerate(text.splitlines(), start=1):
        stripped = raw.strip()
        if not stripped:
            continue
        try:
            observations.append(parse_problem_bank_line(stripped, source=name, line_no=line_no))
        except Exception as exc:  # noqa: BLE001 — 라인 단위 격리·예외 타입명을 그대로 보고
            errors.append(
                ParseError(
                    axis=AXIS_PROBLEM_BANK,
                    source=name,
                    line_no=line_no,
                    error_type=type(exc).__name__,
                    detail=str(exc)[:200],
                )
            )
    status: AxisStatus = "적재됨" if observations else "비어있음"
    return AxisLoad(
        axis=AXIS_PROBLEM_BANK,
        status=status,
        sources=(name,),
        observations=tuple(observations),
        parse_errors=tuple(errors),
    )


def load_problem_bank_axis(
    corpus_root: Path, names: list[str] | None = None
) -> tuple[AxisLoad, list[str]]:
    """`problem_bank*/problems.jsonl` 전량 → 단일 축 관측(여러 파일을 concat)으로 병합.

    `names`(명시 지정)를 준 경우 그 코퍼스가 없으면 두 번째 반환값(`problems`)에 메시지를 담아
    호출자(CLI)가 입력 오류로 처리하게 한다(`problem_bank_coverage._resolve_loads`와 동일 원칙 —
    *명시 지정*한 코퍼스의 부재는 사용자 실수이므로 fatal). 기본 자동 탐색으로 0건이 발견돼도
    여기서는 fatal로 취급하지 않는다 — 이 리포트는 코퍼스 3종 중 하나일 뿐이라 문제은행 축이
    비어도 나머지 두 축 관측은 여전히 유효하다(관측 리포트 원칙).
    """
    problems: list[str] = []
    if names:
        paths = tuple(corpus_root / name / CORPUS_FILE_NAME for name in names)
    else:
        paths = discover_problem_bank_files(corpus_root)

    per_file = tuple(_load_problem_bank_file(p, name=p.parent.name) for p in paths)
    if names:
        for load, name in zip(per_file, names, strict=True):
            if load.status == "데이터없음":
                problems.append(f"코퍼스 파일 없음: {corpus_root / name / CORPUS_FILE_NAME}")

    observations = tuple(obs for load in per_file for obs in load.observations)
    errors = tuple(err for load in per_file for err in load.parse_errors)
    sources = tuple(name for load in per_file for name in load.sources)
    if not paths or all(load.status == "데이터없음" for load in per_file):
        # 경로가 아예 없거나(자동 탐색 0건), 명시 지정한 코퍼스가 전부 파일 부재인 경우 —
        # "비어있음"(파일은 있는데 문항 0건)과 구분해야 하므로 "데이터없음"으로 정직하게 표기.
        status: AxisStatus = "데이터없음"
    elif observations:
        status = "적재됨"
    else:
        status = "비어있음"
    merged = AxisLoad(
        axis=AXIS_PROBLEM_BANK,
        status=status,
        sources=sources,
        observations=observations,
        parse_errors=errors,
    )
    return merged, problems


# ──────────────────────────────────────────────────────────────────────────
# 로더 ④ — curriculum_entry.curriculum_revision (대응 코퍼스 없음 — 관측 불가)
# ──────────────────────────────────────────────────────────────────────────
def curriculum_entry_axis_unavailable() -> AxisLoad:
    """`curriculum_entry.curriculum_revision` 축 — 대응 코퍼스를 찾지 못함(조사 결과).

    `db/models/curriculum_entry.py`·`schema/curriculum_entry.py`는 존재하지만 JSON/YAML/JSONL
    코퍼스 파일이 `data/corpus/` 어디에도 없다(전체 디렉터리 탐색으로 확인). 억지로 파일 경로를
    가정하거나 만들어내지 않는다(CLAUDE.md 날조 금지) — 항상 "대응코퍼스없음"으로 보고한다.
    향후 `data/corpus/curriculum_entry*/` 같은 코퍼스가 생기면 이 함수를 실제 로더로 교체한다.
    """
    return AxisLoad(
        axis=AXIS_CURRICULUM_ENTRY,
        status="대응코퍼스없음",
        sources=(),
        observations=(),
        parse_errors=(),
    )


# ──────────────────────────────────────────────────────────────────────────
# 집계 — crosswalk 발산 리포트(순수 코어)
# ──────────────────────────────────────────────────────────────────────────
@dataclass(slots=True, frozen=True)
class CrosswalkReport:
    """crosswalk 발산 관측 결과 전량(불변·렌더/직렬화의 단일 입력).

    모든 dict는 렌더 시점에 정렬해 쓰므로 삽입 순서에 의존하지 않는다(결정론).
    """

    axis_loads: tuple[AxisLoad, ...]
    canonical_revisions: tuple[str, ...]
    axis_raw_distribution: dict[str, dict[str, int]]
    axis_canonical_distribution: dict[str, dict[str, int]]
    unmapped_values: dict[str, dict[str, int]]
    zero_data_canonical_revisions: tuple[str, ...]
    global_canonical_totals: dict[str, int]
    majority_canonical: str | None
    divergence_total: int
    divergence_by_axis: dict[str, int]
    missing_field_counts: dict[str, int]
    parse_errors: tuple[ParseError, ...]

    @property
    def measured_observation_total(self) -> int:
        """실측 3축(curriculum_entry 제외)의 관측 총건수(필드 누락 포함)."""
        return sum(len(load.observations) for load in self.axis_loads if load.axis in MEASURED_AXES)

    @property
    def unmapped_total(self) -> int:
        return sum(sum(counts.values()) for counts in self.unmapped_values.values())


def build_report(loads: tuple[AxisLoad, ...]) -> CrosswalkReport:
    """축 적재 결과 → `CrosswalkReport`(순수·부작용 0).

    발산(divergence) 정의: 실측 3축(curriculum_entry 제외)의 관측을 전부 crosswalk로 정규화한
    뒤, 가장 많이 관측된 정규 개정판("다수결", 동률은 정규 키 사전순 최솟값)을 기준으로 **그와
    다른 정규 개정판을 가리키는 관측 건수**의 합이다. 필드 누락(`raw_value is None`)과 미매핑
    값은 "어느 개정판을 가리키는지 알 수 없다"는 뜻이라 발산 계산에서 제외하고 별도 카운트로
    보고한다(정직 회계 — 모르는 것을 다수결과 다르다고 단정하지 않는다).
    """
    axis_raw: dict[str, Counter[str]] = {}
    axis_canon: dict[str, Counter[str]] = {}
    unmapped: dict[str, Counter[str]] = {}
    missing_counts: dict[str, int] = {}
    global_totals: Counter[str] = Counter()
    all_parse_errors: list[ParseError] = []

    for load in loads:
        axis_raw.setdefault(load.axis, Counter())
        axis_canon.setdefault(load.axis, Counter())
        unmapped.setdefault(load.axis, Counter())
        missing_counts.setdefault(load.axis, 0)
        all_parse_errors.extend(load.parse_errors)
        for obs in load.observations:
            if obs.raw_value is None:
                axis_raw[load.axis][MISSING_VALUE] += 1
                axis_canon[load.axis][MISSING_VALUE] += 1
                missing_counts[load.axis] += 1
                continue
            axis_raw[load.axis][obs.raw_value] += 1
            canonical = canonicalize(obs.raw_value)
            if canonical is None:
                axis_canon[load.axis][UNMAPPED_VALUE] += 1
                unmapped[load.axis][obs.raw_value] += 1
                continue
            axis_canon[load.axis][canonical] += 1
            if load.axis in MEASURED_AXES:
                global_totals[canonical] += 1

    zero_data = tuple(rev for rev in CANONICAL_REVISIONS if global_totals.get(rev, 0) == 0)

    majority: str | None = None
    if global_totals:
        max_count = max(global_totals.values())
        majority = min(rev for rev, count in global_totals.items() if count == max_count)

    divergence_total = 0
    divergence_by_axis: Counter[str] = Counter()
    if majority is not None:
        for load in loads:
            if load.axis not in MEASURED_AXES:
                continue
            for obs in load.observations:
                if obs.raw_value is None:
                    continue
                canonical = canonicalize(obs.raw_value)
                if canonical is None or canonical == majority:
                    continue
                divergence_total += 1
                divergence_by_axis[load.axis] += 1

    return CrosswalkReport(
        axis_loads=loads,
        canonical_revisions=CANONICAL_REVISIONS,
        axis_raw_distribution={axis: dict(counts) for axis, counts in axis_raw.items()},
        axis_canonical_distribution={axis: dict(counts) for axis, counts in axis_canon.items()},
        unmapped_values={axis: dict(counts) for axis, counts in unmapped.items() if counts},
        zero_data_canonical_revisions=zero_data,
        global_canonical_totals=dict(global_totals),
        majority_canonical=majority,
        divergence_total=divergence_total,
        divergence_by_axis=dict(divergence_by_axis),
        missing_field_counts=missing_counts,
        parse_errors=tuple(all_parse_errors),
    )


# ──────────────────────────────────────────────────────────────────────────
# 렌더 — 사람이 읽는 마크다운 + 기계가 읽는 JSON
# ──────────────────────────────────────────────────────────────────────────
def _sorted_counts(counts: dict[str, int]) -> list[tuple[str, int]]:
    """카운트 정렬 — 값 내림차순 → 키 오름차순(결정론)."""
    return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))


def render_report(report: CrosswalkReport) -> str:
    """crosswalk 발산 관측 결과를 마크다운으로 렌더(순수·입력 외 계산 없음)."""
    lines: list[str] = [
        "# 교육과정 개정판 어휘 crosswalk 관측 리포트 (CUR-01)",
        "",
        "> 관측 리포트다 — **exit 게이트가 아니다**(발산 건수로 실패시키지 않는다).",
        "> 3어휘 통합 마이그레이션(스키마 변경)은 범위 밖 — crosswalk 매핑 + 발산 건수만 낸다.",
        "",
        "## 0. 입력 요약(축별 상태)",
        "",
        "| 축(어휘 공간) | 상태 | 소스 수 | 관측 | 파싱 실패 |",
        "|---|---|---:|---:|---:|",
    ]
    for load in report.axis_loads:
        lines.append(
            f"| `{load.axis}` | {load.status} | {len(load.sources)} | "
            f"{len(load.observations)} | {len(load.parse_errors)} |"
        )

    lines += [
        "",
        "## 1. crosswalk 매핑표",
        "",
        "| 원시값 | 정규 개정판 키 |",
        "|---|---|",
    ]
    for raw, canonical in sorted(CROSSWALK.items()):
        lines.append(f"| `{raw}` | `{canonical}` |")

    lines += ["", "## 2. 축별 원시값 분포", ""]
    for axis in ALL_AXES:
        lines.append(f"### 2.{ALL_AXES.index(axis) + 1} `{axis}`")
        lines.append("")
        counts = report.axis_raw_distribution.get(axis, {})
        if not counts:
            lines.append("- 관측 없음.")
        else:
            lines += ["| 원시값 | 건수 |", "|---|---:|"]
            for value, count in _sorted_counts(counts):
                lines.append(f"| `{value}` | {count} |")
        lines.append("")

    lines += ["## 3. 축별 정규화(canonical) 분포", ""]
    for axis in ALL_AXES:
        counts = report.axis_canonical_distribution.get(axis, {})
        lines.append(f"### 3.{ALL_AXES.index(axis) + 1} `{axis}`")
        lines.append("")
        if not counts:
            lines.append("- 관측 없음.")
        else:
            lines += ["| 정규 개정판 키 | 건수 |", "|---|---:|"]
            for value, count in _sorted_counts(counts):
                lines.append(f"| `{value}` | {count} |")
        lines.append("")

    lines += ["## 4. 미매핑 값(crosswalk 표에 없음)", ""]
    if not report.unmapped_values:
        lines.append("- 없음(모든 관측이 crosswalk 매핑표로 정규화됨).")
    else:
        lines += ["| 축 | 원시값 | 건수 |", "|---|---|---:|"]
        for axis in ALL_AXES:
            for value, count in _sorted_counts(report.unmapped_values.get(axis, {})):
                lines.append(f"| `{axis}` | `{value}` | {count} |")
        lines.append(f"- 미매핑 총계: **{report.unmapped_total}**건")

    lines += [
        "",
        "## 5. 발산(divergence) 리포트",
        "",
        "> 실측 3축(curriculum_entry 제외)을 정규화한 뒤, 가장 많이 관측된 정규 개정판(다수결)과",
        "> **다른** 값을 가리키는 관측 건수의 합. 필드 누락·미매핑은 '모르는 값'이라 발산 계산에서",
        "> 제외한다(§4·§6의 정직 회계로 별도 표시).",
        "",
        "| 정규 개정판 키 | 전역 건수(3축 합) |",
        "|---|---:|",
    ]
    for rev in report.canonical_revisions:
        lines.append(f"| `{rev}` | {report.global_canonical_totals.get(rev, 0)} |")
    majority_label = (
        f"`{report.majority_canonical}`" if report.majority_canonical else "없음(관측 0)"
    )
    lines += [
        "",
        f"- 다수결 정규 개정판: {majority_label}",
        f"- **발산 총건수: {report.divergence_total}**",
        "",
        "| 축 | 발산 건수 |",
        "|---|---:|",
    ]
    for axis in MEASURED_AXES:
        lines.append(f"| `{axis}` | {report.divergence_by_axis.get(axis, 0)} |")

    lines += ["", "## 6. enum 정의 대비 실 데이터 0건인 정규 개정판", ""]
    if not report.zero_data_canonical_revisions:
        lines.append("- 없음(enum에 정의된 모든 개정판이 1건 이상 관측됨).")
    else:
        lines.append("- " + " ".join(f"`{rev}`" for rev in report.zero_data_canonical_revisions))

    lines += [
        "",
        "## 7. 정직 회계 (누락·미지 값)",
        "",
        "> 조용히 버리지 않는다 — 아래가 모두 0이어야 위 수치를 액면 그대로 읽을 수 있다.",
        "",
        "| 항목 | 건수 |",
        "|---|---:|",
        f"| 파싱 실패 레코드 | {len(report.parse_errors)} |",
        f"| 미매핑 값(축 전체 합) | {report.unmapped_total} |",
    ]
    for axis in ALL_AXES:
        lines.append(f"| 필드 누락(`{axis}`) | {report.missing_field_counts.get(axis, 0)} |")
    if report.parse_errors:
        lines += ["", "### 7.1 파싱 실패 레코드", ""]
        for err in report.parse_errors:
            loc = f"line {err.line_no}" if err.line_no is not None else "(파일 전체)"
            lines.append(f"- `{err.axis}`/`{err.source}` {loc}: {err.error_type} — {err.detail}")
    lines.append("")
    return "\n".join(lines)


def report_to_json(report: CrosswalkReport) -> dict[str, Any]:
    """리포트 → JSON 직렬화 가능 dict(키 정렬은 dump 시 `sort_keys=True`로 고정)."""
    return {
        "axes": [
            {
                "axis": load.axis,
                "status": load.status,
                "sources": list(load.sources),
                "observations": len(load.observations),
                "parse_errors": len(load.parse_errors),
            }
            for load in report.axis_loads
        ],
        "crosswalk": dict(sorted(CROSSWALK.items())),
        "canonical_revisions": list(report.canonical_revisions),
        "axis_raw_distribution": report.axis_raw_distribution,
        "axis_canonical_distribution": report.axis_canonical_distribution,
        "unmapped_values": report.unmapped_values,
        "unmapped_total": report.unmapped_total,
        "zero_data_canonical_revisions": list(report.zero_data_canonical_revisions),
        "global_canonical_totals": report.global_canonical_totals,
        "majority_canonical": report.majority_canonical,
        "divergence_total": report.divergence_total,
        "divergence_by_axis": report.divergence_by_axis,
        "honest_accounting": {
            "parse_error_records": len(report.parse_errors),
            "parse_errors": [
                {
                    "axis": e.axis,
                    "source": e.source,
                    "line_no": e.line_no,
                    "error_type": e.error_type,
                    "detail": e.detail,
                }
                for e in report.parse_errors
            ],
            "missing_field_counts": report.missing_field_counts,
        },
    }


def dump_json(report: CrosswalkReport) -> str:
    """JSON 직렬화 — 키 정렬·들여쓰기 고정으로 같은 입력에 같은 바이트를 보장(결정론)."""
    return json.dumps(report_to_json(report), ensure_ascii=False, indent=2, sort_keys=True) + "\n"


# ──────────────────────────────────────────────────────────────────────────
# CLI (얇은 껍데기 — 경로 해석·입출력만, 집계는 위 순수 코어)
# ──────────────────────────────────────────────────────────────────────────
def main(argv: list[str] | None = None) -> int:
    """CLI 엔트리 — crosswalk 발산 관측 리포트를 stdout에 출력. **0=성공 / 2=입력 오류**(1 없음).

    발산이 아무리 커도 exit 0이다 — 게이트가 아니라 관측이기 때문. exit 2는 *관측 자체가
    불가능한* 입력 오류(성취기준 대장 부재·구조 오류, 명시 지정한 문제은행 코퍼스 부재)에만
    쓴다. 단원 YAML 디렉터리 부재·문제은행 자동 탐색 0건은 그 축이 "데이터없음"으로 표시될 뿐
    fatal이 아니다(3축 중 하나가 비어도 나머지 축 관측은 여전히 유효).
    """
    parser = argparse.ArgumentParser(
        prog="python -m whymath_backend.harness.curriculum_revision_crosswalk_report",
        description=(
            "교육과정 개정판 어휘 crosswalk 관측 리포트(CUR-01) — 3어휘(성취기준 한글 표기·"
            "단원 DSL 연도·문제은행 enum 값) crosswalk 매핑·축별 분포·발산 건수. "
            "결정론·게이트 아님(exit 0/2)."
        ),
    )
    parser.add_argument(
        "--standards",
        type=Path,
        default=DEFAULT_STANDARDS_PATH,
        help=f"NCIC 성취기준 JSON 경로(기본 {DEFAULT_STANDARDS_PATH}).",
    )
    parser.add_argument(
        "--units-root",
        type=Path,
        default=DEFAULT_UNITS_ROOT,
        help=f"단원 DSL YAML 루트 디렉터리(기본 {DEFAULT_UNITS_ROOT}).",
    )
    parser.add_argument(
        "--corpus-root",
        type=Path,
        default=DEFAULT_CORPUS_ROOT,
        help=f"문제은행 코퍼스 루트 디렉터리(기본 {DEFAULT_CORPUS_ROOT}).",
    )
    parser.add_argument(
        "--corpus",
        action="append",
        default=None,
        help="집계할 문제은행 코퍼스 디렉터리명(반복 지정 가능·기본은 problem_bank* 전량 탐색).",
    )
    parser.add_argument(
        "--json",
        dest="json_path",
        type=Path,
        default=None,
        help="JSON 산출물 경로(선택·미지정이면 stdout 마크다운만).",
    )
    args = parser.parse_args(argv)

    try:
        standards_load = load_standards_axis(args.standards)
    except Exception as exc:  # noqa: BLE001 — 입력 오류는 타입명과 함께 보고하고 exit 2
        print(f"입력 오류 — 성취기준 대장 적재 실패({type(exc).__name__}): {exc}", file=sys.stderr)
        return _EXIT_INPUT_ERROR
    if standards_load.status == "데이터없음":
        # 성취기준 대장은 crosswalk 비교의 그라운딩 축이라 부재는 구조 오류와 동급 fatal —
        # `problem_bank_coverage`가 대장 부재를 exit 2로 처리하는 것과 동일 원칙(모듈 docstring).
        print(f"입력 오류 — 성취기준 대장 파일 없음: {args.standards}", file=sys.stderr)
        return _EXIT_INPUT_ERROR

    unit_spec_load = load_unit_spec_axis(args.units_root)
    problem_bank_load, problems = load_problem_bank_axis(args.corpus_root, args.corpus)
    curriculum_entry_load = curriculum_entry_axis_unavailable()

    loads = (standards_load, unit_spec_load, problem_bank_load, curriculum_entry_load)
    report = build_report(loads)
    print(render_report(report))
    if args.json_path is not None:
        args.json_path.parent.mkdir(parents=True, exist_ok=True)
        args.json_path.write_text(dump_json(report), encoding="utf-8")
        print(f"JSON 산출물: {args.json_path}")

    if problems:
        for msg in problems:
            print(f"입력 오류 — {msg}", file=sys.stderr)
        return _EXIT_INPUT_ERROR
    return _EXIT_OK


if __name__ == "__main__":  # pragma: no cover — 엔트리포인트
    sys.exit(main())
