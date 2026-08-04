"""개념 지식 자산 도달률 관측 리포트 CLI — 빌드타임 결정론(파일시스템 정적 스캔 0·LLM 0·HTTP 0).
KG-01 acceptance②.

설계 정본: `docs/architecture/knowledge_module_gap_review.md` §5-1. concepts API 7라우트
(`api/concepts.py`)·`ConceptContent.flashcards`(코퍼스 113건 적재) 읽기 표면·
`/v1/me/weak-concepts/{concept_id}/prerequisites`·`.../learning-path`(`api/me.py`)가 Flutter
학생 앱에서 실제로 소비되는지를 정적 스캔으로 가시화한다. VIZ-01
(`visualization_reach_report.py`)의 dataclass 기반 로더/집계/렌더/JSON/CLI 구조를 그대로
복제한다.

**게이트가 아니다**(VIZ-01·`problem_bank_coverage`와 동일 원칙) — 도달 0건이어도 exit 1을
내지 않는다. 목적은 도달률을 올리는 것이 아니라 *관측 가능하게* 만드는 것이다(활성화가 아니라
가시화 — KG-01 acceptance⑥).

**정정 기록(2026-08-03, KG-01 acceptance① 반증 결과)**: 이 리포트 신설 이전 커밋된 문서
(`knowledge_module_gap_review.md` §5-1 초판)는 Flutter 앱이 실호출하는 `/v1/` 경로가 "20종"
이라고 주장했으나, 이는 `src/mobile`(테스트 목 리터럴 포함) 전체를 대상으로 한 grep의 착오였다.
`src/mobile/lib`(프로덕션 코드, `test/` 제외)만 대상으로 하면 초판 시점 **정확히 13종**이었다.
이 모듈의 `total_v1_literal_callsites` 필드가 그 정확한 분모를 매 실행마다 실측해, 향후 문서가
다시 stale해지는 것을 리포트 자체가 anchor로 방지한다.

**분모 갱신(2026-08-04, RPT-01)**: 13 → **14**. 학생 결함 신고 버튼이
`features/reports/data/defect_report_api.dart`에서 `/v1/reports/defects`를 호출하기 시작했다.
회귀 감시 가드(`test_concept_reach_report.py`)가 설계대로 발화해 이 증가를 잡았다 — 개념
표면 10종의 `미도달` 판정은 변동 없다(새 콜사이트는 개념이 아니라 신고 표면).

산출 표면 10종:
  1~7. `api/concepts.py`의 7라우트(POST/GET단건/GET목록/GET search/GET edges/PATCH/DELETE)
  8. `ConceptContent.flashcards`(JSONB) — 이를 읽어 응답에 싣는 API 엔드포인트 존재 여부
     (스캔 대상이 mobile이 아니라 `api/**/*.py` 자체 — "학생 호출 여부"가 아니라 "읽는 코드
     자체가 있는가"를 본다)
  9~10. `/v1/me/weak-concepts/{concept_id}/prerequisites`·`.../learning-path`

**알려진 한계(1급으로 노출·숨기지 않음)**: `concepts.py` 7라우트 중 4개는 URL 경로가 겹쳐서
grep만으로는 HTTP 메서드를 구분할 수 없다 — `/v1/concepts`는 `create_concept`(POST)·
`list_concepts`(GET)가, `/v1/concepts/{concept_id}`는 `read_concept`(GET)·`patch_concept`
(PATCH)·`delete_concept`(DELETE)가 공유한다. 같은 경로 리터럴이 mobile 소스에 나타나면 그
그룹의 표면 전부가 동시에 "도달"로 바뀐다 — 이는 버그가 아니라 정적 스캔의 원리적 한계이며,
`method_ambiguous_groups` 필드로 렌더·JSON에 명시 경고를 낸다.

사용:
    python -m whymath_backend.harness.concept_reach_report
    python -m whymath_backend.harness.concept_reach_report --json out/concept_reach.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

__all__ = [
    "SURFACES",
    "ConceptReachReport",
    "SurfaceReach",
    "SurfaceSpec",
    "build_report",
    "dump_json",
    "load_scan_root",
    "main",
    "render_report",
    "report_to_json",
]

_EXIT_OK = 0
_EXIT_INPUT_ERROR = 2

# harness→whymath_backend→backend→src→repo 루트(visualization_reach_report.py와 동일 관례).
_REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_MOBILE_LIB_ROOT = _REPO_ROOT / "src" / "mobile" / "lib"
DEFAULT_BACKEND_API_ROOT = _REPO_ROOT / "src" / "backend" / "whymath_backend" / "api"

# 이 이름의 디렉터리 아래는 스캔에서 제외한다 — "20 vs 13" 재발 방지 방어 가드. 기본 mobile
# root(=.../lib)는 이미 test/ 밖이지만, CLI/테스트에서 override된 root가 실수로 test 포함
# 디렉터리(예: src/mobile 전체)를 가리켜도 테스트 목 리터럴이 섞이지 않도록 이중으로 막는다.
_EXCLUDED_DIR_NAMES = {"test", "tests"}

_PLACEHOLDER_PATTERN = r"(?:\$\{?[A-Za-z_][A-Za-z0-9_]*\}?)"


def _route_pattern(path_template: str) -> re.Pattern[str]:
    """FastAPI 경로 템플릿(`/v1/concepts/{concept_id}/edges`)을 dio 호출 리터럴 매칭 정규식으로.

    `{param}` 세그먼트는 dart 문자열 보간(`$id`·`${id}`) 어디에나 매치한다(파라미터 이름 자체는
    dart 쪽과 무관 — 존재 여부만 본다). 앞뒤를 quote로 앵커링해 부분 문자열 오탐을 막는다(예:
    `/v1/concepts` 템플릿이 `/v1/concepts/search` 리터럴에 우발 매치되지 않도록).
    """
    parts = [re.escape(p) for p in re.split(r"\{[^}]+\}", path_template)]
    body = _PLACEHOLDER_PATTERN.join(parts)
    return re.compile(r"""['"]""" + body + r"""['"]""")


def _literal_pattern(literal: str) -> re.Pattern[str]:
    """경로가 아닌 리터럴 문자열(예: `flashcards` 필드명) 자체를 찾는 패턴."""
    return re.compile(re.escape(literal))


@dataclass(slots=True, frozen=True)
class SurfaceSpec:
    """표면 1건의 정의(코드 상수 — 로드 대상 아님. 표면 목록 자체가 바뀌면 코드를 고친다)."""

    key: str
    label: str
    definition_location: str
    scan_root_kind: str  # "mobile_lib" | "backend_api"
    glob: str
    pattern: re.Pattern[str]
    pattern_id: str
    note: str | None = None


SURFACES: tuple[SurfaceSpec, ...] = (
    SurfaceSpec(
        key="concepts_create",
        label="POST /v1/concepts",
        definition_location="api/concepts.py:243 (create_concept)",
        scan_root_kind="mobile_lib",
        glob="*.dart",
        pattern=_route_pattern("/v1/concepts"),
        pattern_id="path:/v1/concepts",
    ),
    SurfaceSpec(
        key="concepts_read",
        label="GET /v1/concepts/{concept_id}",
        definition_location="api/concepts.py:270 (read_concept)",
        scan_root_kind="mobile_lib",
        glob="*.dart",
        pattern=_route_pattern("/v1/concepts/{concept_id}"),
        pattern_id="path:/v1/concepts/{concept_id}",
    ),
    SurfaceSpec(
        key="concepts_list",
        label="GET /v1/concepts",
        definition_location="api/concepts.py:296 (list_concepts)",
        scan_root_kind="mobile_lib",
        glob="*.dart",
        pattern=_route_pattern("/v1/concepts"),
        pattern_id="path:/v1/concepts",
    ),
    SurfaceSpec(
        key="concepts_search",
        label="GET /v1/concepts/search",
        definition_location="api/concepts.py:172 (search_concepts_endpoint)",
        scan_root_kind="mobile_lib",
        glob="*.dart",
        pattern=_route_pattern("/v1/concepts/search"),
        pattern_id="path:/v1/concepts/search",
        note=(
            "reviewed_only=true 결과 0(원자 전량 ai_estimated)은 별도 축이다(acceptance③) — "
            "이 리포트는 클라 소비(reach) 축만 다룬다. 학생 직접 노출은 ARCH-11(subgraph depth "
            "guard, blocked) 해제 전까지 하지 않는다(nlp_module_gap_review.md §5-⑤ 승계)."
        ),
    ),
    SurfaceSpec(
        key="concepts_edges",
        label="GET /v1/concepts/{concept_id}/edges",
        definition_location="api/concepts.py:315 (list_concept_edges)",
        scan_root_kind="mobile_lib",
        glob="*.dart",
        pattern=_route_pattern("/v1/concepts/{concept_id}/edges"),
        pattern_id="path:/v1/concepts/{concept_id}/edges",
    ),
    SurfaceSpec(
        key="concepts_patch",
        label="PATCH /v1/concepts/{concept_id}",
        definition_location="api/concepts.py:337 (patch_concept)",
        scan_root_kind="mobile_lib",
        glob="*.dart",
        pattern=_route_pattern("/v1/concepts/{concept_id}"),
        pattern_id="path:/v1/concepts/{concept_id}",
    ),
    SurfaceSpec(
        key="concepts_delete",
        label="DELETE /v1/concepts/{concept_id}",
        definition_location="api/concepts.py:388 (delete_concept)",
        scan_root_kind="mobile_lib",
        glob="*.dart",
        pattern=_route_pattern("/v1/concepts/{concept_id}"),
        pattern_id="path:/v1/concepts/{concept_id}",
    ),
    SurfaceSpec(
        key="concept_content_flashcards",
        label="ConceptContent.flashcards 읽기 API",
        definition_location="db/models/concept_content.py:98 (필드) — 스캔 대상은 api/**/*.py",
        scan_root_kind="backend_api",
        glob="*.py",
        pattern=_literal_pattern("flashcards"),
        pattern_id="literal:flashcards",
        note=(
            "다른 9종과 스캔 대상이 다르다 — '학생이 호출하는가'가 아니라 "
            "'api/ 어디서든 이 필드를 읽는 코드 자체가 있는가'를 본다(코퍼스 113건 적재됨)."
        ),
    ),
    SurfaceSpec(
        key="me_prerequisites",
        label="GET /v1/me/weak-concepts/{concept_id}/prerequisites",
        definition_location="api/me.py:1391 (get_my_prerequisite_gaps)",
        scan_root_kind="mobile_lib",
        glob="*.dart",
        pattern=_route_pattern("/v1/me/weak-concepts/{concept_id}/prerequisites"),
        pattern_id="path:/v1/me/weak-concepts/{concept_id}/prerequisites",
    ),
    SurfaceSpec(
        key="me_learning_path",
        label="GET /v1/me/weak-concepts/{concept_id}/learning-path",
        definition_location="api/me.py:1507 (get_my_learning_path)",
        scan_root_kind="mobile_lib",
        glob="*.dart",
        pattern=_route_pattern("/v1/me/weak-concepts/{concept_id}/learning-path"),
        pattern_id="path:/v1/me/weak-concepts/{concept_id}/learning-path",
    ),
)

_V1_LITERAL_PATTERN = re.compile(r"""['"](/v1/[^'"]*)['"]""")


def load_scan_root(path: Path, *, label: str) -> Path:
    """스캔 루트 디렉터리 존재 검증(VIZ-01의 `load_catalog` 대응) — "입력을 못 읽음"과 "읽었는데
    0건(미도달)"은 다른 실패 축이므로 여기서 분리한다.

    Raises:
        ValueError: 디렉터리가 아니거나 존재하지 않음.
    """
    if not path.is_dir():
        raise ValueError(f"{label} 스캔 루트가 디렉터리가 아니거나 존재하지 않음: {path}")
    return path


def _is_excluded(path: Path, root: Path) -> bool:
    return any(part.lower() in _EXCLUDED_DIR_NAMES for part in path.relative_to(root).parts)


def _scan(root: Path, glob: str, pattern: re.Pattern[str]) -> tuple[str, ...]:
    """`root` 아래 `glob` 파일을 정렬 순회하며 `pattern` 매치 파일의 root-상대경로를 모은다.

    결정론(정렬)·부작용 0. 디코드 실패 파일은 조용히 skip(바이너리·비UTF-8 혼입 방어).
    """
    matched: list[str] = []
    for path in sorted(root.rglob(glob)):
        if _is_excluded(path, root):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if pattern.search(text):
            matched.append(str(path.relative_to(root)))
    return tuple(matched)


def _scan_v1_literal_callsites(mobile_root: Path) -> tuple[int, tuple[str, ...]]:
    """mobile lib 전체의 `/v1/` 리터럴 콜사이트 총계 + 상세("file:line:literal").

    이 숫자가 향후 문서(가령 "N종")의 실측 anchor다 — 손으로 다시 grep해 옮겨 적을 필요가
    없어야 stale이 재발하지 않는다.
    """
    detail: list[str] = []
    for path in sorted(mobile_root.rglob("*.dart")):
        if _is_excluded(path, mobile_root):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        rel = path.relative_to(mobile_root)
        for lineno, line in enumerate(text.splitlines(), start=1):
            for m in _V1_LITERAL_PATTERN.finditer(line):
                detail.append(f"{rel}:{lineno}:{m.group(1)}")
    return len(detail), tuple(sorted(detail))


# ──────────────────────────────────────────────────────────────────────────
# 집계 — 도달 리포트(순수 코어)
# ──────────────────────────────────────────────────────────────────────────
@dataclass(slots=True, frozen=True)
class SurfaceReach:
    """표면 1건의 도달 관측 결과. 상태는 분수가 아니라 이진 문자열이다(정직 표기 —
    acceptance③: '0건 통과'가 아니라 '미도달')."""

    key: str
    label: str
    definition_location: str
    reach_count: int
    matched_files: tuple[str, ...]
    status: str  # "도달" | "미도달"
    pattern_id: str
    note: str | None


@dataclass(slots=True, frozen=True)
class ConceptReachReport:
    """도달 관측 결과 전량(불변·렌더/직렬화의 단일 입력)."""

    surfaces: tuple[SurfaceReach, ...]
    method_ambiguous_groups: tuple[tuple[str, ...], ...]
    total_v1_literal_callsites: int
    total_v1_literal_callsites_detail: tuple[str, ...]

    @property
    def unreached_count(self) -> int:
        return sum(1 for s in self.surfaces if s.status == "미도달")


def build_report(
    *,
    mobile_root: Path = DEFAULT_MOBILE_LIB_ROOT,
    backend_api_root: Path = DEFAULT_BACKEND_API_ROOT,
) -> ConceptReachReport:
    """10개 표면 + `/v1/` 리터럴 총계 → `ConceptReachReport`(순수·부작용 0).

    같은 `pattern_id`를 공유하는 표면은 반드시 동일한 스캔 결과를 갖는다(캐시로 보장 — 우발적
    분기 방지). 이는 재구현 실수를 막기 위함이지, 표면을 구분하지 못한다는 한계를 감추기
    위함이 아니다(`method_ambiguous_groups`가 그 한계를 그대로 드러낸다).
    """
    mobile_root = load_scan_root(mobile_root, label="mobile lib")
    backend_api_root = load_scan_root(backend_api_root, label="backend api")

    cache: dict[str, tuple[str, ...]] = {}
    surfaces: list[SurfaceReach] = []
    for spec in SURFACES:
        root = mobile_root if spec.scan_root_kind == "mobile_lib" else backend_api_root
        if spec.pattern_id not in cache:
            cache[spec.pattern_id] = _scan(root, spec.glob, spec.pattern)
        matched = cache[spec.pattern_id]
        surfaces.append(
            SurfaceReach(
                key=spec.key,
                label=spec.label,
                definition_location=spec.definition_location,
                reach_count=len(matched),
                matched_files=matched,
                status="도달" if matched else "미도달",
                pattern_id=spec.pattern_id,
                note=spec.note,
            )
        )

    groups: dict[str, list[str]] = {}
    for spec in SURFACES:
        groups.setdefault(spec.pattern_id, []).append(spec.key)
    ambiguous = tuple(tuple(v) for v in groups.values() if len(v) > 1)

    total, detail = _scan_v1_literal_callsites(mobile_root)

    return ConceptReachReport(
        surfaces=tuple(surfaces),
        method_ambiguous_groups=ambiguous,
        total_v1_literal_callsites=total,
        total_v1_literal_callsites_detail=detail,
    )


# ──────────────────────────────────────────────────────────────────────────
# 렌더 — 사람이 읽는 마크다운 + 기계가 읽는 JSON
# ──────────────────────────────────────────────────────────────────────────
def render_report(report: ConceptReachReport, *, max_listed: int = 40) -> str:
    """도달 관측 결과를 마크다운으로 렌더(순수·입력 외 계산 없음).

    목록류는 `max_listed`개까지만 본문에 싣고 잘림 사실을 문장으로 남긴다
    (`visualization_reach_report.render_report` 관례 답습 — 조용한 절단 금지).
    """
    lines: list[str] = [
        "# 개념 지식 자산 도달 관측 리포트 (KG-01)",
        "",
        "> 관측 리포트다 — **exit 게이트가 아니다**(도달 0건이어도 실패시키지 않는다).",
        "> 활성화가 아니라 가시화가 목적이다(acceptance⑥) — 클라 배선·학생 노출은 범위 밖.",
        "",
        "## 0. 표면 도달 상태",
        "",
        "| 키 | 표면 | 정의 위치 | 상태 | reach_count |",
        "|---|---|---|---|---:|",
    ]
    for s in report.surfaces:
        lines.append(
            f"| `{s.key}` | {s.label} | `{s.definition_location}` | {s.status} | {s.reach_count} |"
        )
    lines.append(f"\n- 미도달 표면: **{report.unreached_count}/{len(report.surfaces)}**")

    lines += ["", "## 1. 메서드 구분 불가 그룹(알려진 한계 — 숨기지 않는다)", ""]
    if report.method_ambiguous_groups:
        lines.append(
            "다음 표면 그룹은 URL 경로가 겹쳐 grep만으로 HTTP 메서드를 구분할 수 없다 — "
            "같은 경로 리터럴이 mobile 소스에 나타나면 그룹 전체가 동시에 '도달'로 바뀐다:"
        )
        for group in report.method_ambiguous_groups:
            lines.append("- " + " · ".join(f"`{k}`" for k in group))
    else:
        lines.append("(현재 없음)")

    lines += [
        "",
        "## 2. `/v1/` 리터럴 콜사이트 총계 (분모 실측 anchor)",
        "",
        f"- 총 **{report.total_v1_literal_callsites}**건 "
        "(`src/mobile/lib`만 — `test/` 제외. 과거 '20종' 주장은 `src/mobile` 전체를 대상으로 "
        "해 테스트 목 리터럴까지 섞인 오류였다 — "
        "`docs/architecture/knowledge_module_gap_review.md` §5-1 참조)",
    ]
    shown = report.total_v1_literal_callsites_detail[:max_listed]
    if shown:
        lines += ["", "```"]
        lines.extend(shown)
        lines.append("```")
        remainder = len(report.total_v1_literal_callsites_detail) - len(shown)
        if remainder > 0:
            lines.append(f"…외 **{remainder}**건(전량은 `--json` 산출물).")

    search_note = next((s.note for s in report.surfaces if s.key == "concepts_search"), None)
    if search_note:
        lines += ["", "## 3. `concepts_search` 특기사항", "", search_note]

    lines.append("")
    return "\n".join(lines)


def report_to_json(report: ConceptReachReport) -> dict[str, Any]:
    """리포트 → JSON 직렬화 가능 dict(키 정렬은 dump 시 `sort_keys=True`로 고정)."""
    return {
        "surfaces": [
            {
                "key": s.key,
                "label": s.label,
                "definition_location": s.definition_location,
                "reach_count": s.reach_count,
                "matched_files": list(s.matched_files),
                "status": s.status,
                "pattern_id": s.pattern_id,
                "note": s.note,
            }
            for s in report.surfaces
        ],
        "unreached_count": report.unreached_count,
        "method_ambiguous_groups": [list(g) for g in report.method_ambiguous_groups],
        "total_v1_literal_callsites": report.total_v1_literal_callsites,
        "total_v1_literal_callsites_detail": list(report.total_v1_literal_callsites_detail),
    }


def dump_json(report: ConceptReachReport) -> str:
    return json.dumps(report_to_json(report), ensure_ascii=False, indent=2, sort_keys=True) + "\n"


# ──────────────────────────────────────────────────────────────────────────
# CLI (얇은 껍데기 — 경로 해석·입출력만, 집계는 위 순수 코어)
# ──────────────────────────────────────────────────────────────────────────
def main(argv: list[str] | None = None) -> int:
    """CLI 엔트리 — 도달 관측 리포트를 stdout에 출력. **0=성공 / 2=입력 오류**(1 없음).

    도달 0건이어도 exit 0이다(게이트 아님). exit 2는 스캔 루트 자체를 읽을 수 없는 입력
    오류에만 쓴다.
    """
    parser = argparse.ArgumentParser(
        prog="python -m whymath_backend.harness.concept_reach_report",
        description=(
            "개념 지식 자산 도달 관측 리포트(KG-01) — concepts API 7라우트·flashcards 읽기·"
            "prerequisites/learning-path의 클라 소비 여부. 결정론·게이트 아님(exit 0/2)."
        ),
    )
    parser.add_argument(
        "--mobile-root",
        type=Path,
        default=DEFAULT_MOBILE_LIB_ROOT,
        help="Flutter mobile lib 루트(기본: src/mobile/lib)",
    )
    parser.add_argument(
        "--backend-api-root",
        type=Path,
        default=DEFAULT_BACKEND_API_ROOT,
        help="backend api 루트(기본: src/backend/whymath_backend/api)",
    )
    parser.add_argument(
        "--max-listed", type=int, default=40, help="본문에 나열할 목록 최대 개수(기본 40)"
    )
    parser.add_argument(
        "--json", dest="json_path", type=Path, default=None, help="JSON 산출물 경로(선택)"
    )
    args = parser.parse_args(argv)

    try:
        report = build_report(mobile_root=args.mobile_root, backend_api_root=args.backend_api_root)
    except ValueError as exc:
        print(f"입력 오류 — 스캔 루트 검증 실패({type(exc).__name__}): {exc}", file=sys.stderr)
        return _EXIT_INPUT_ERROR

    print(render_report(report, max_listed=args.max_listed))
    if args.json_path is not None:
        args.json_path.parent.mkdir(parents=True, exist_ok=True)
        args.json_path.write_text(dump_json(report), encoding="utf-8")
        print(f"JSON 산출물: {args.json_path}")
    return _EXIT_OK


if __name__ == "__main__":  # pragma: no cover — 엔트리포인트
    sys.exit(main())
