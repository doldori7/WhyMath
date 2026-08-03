"""공급↔소비 도달 대장 — "만들고 입력을 잇지 않음" 반복 실수의 기계 탐지기 (OPS-17).

왜 이 모듈이 있는가
------------------
이 저장소는 같은 사고를 **6회** 반복했다. 무언가를 완비해 놓고 *그것을 실제로 부르는 쪽*을
잇지 않아, 코드가 존재한다는 사실이 "돌아간다"로 잘못 읽힌 사고다.

    OPS-03  tests/infra 199건을 어떤 CI 잡도 실행하지 않았다
    OPS-08  브랜치 보호 required check가 `checks=[]`로 통째 미강제였다
    VIZ-01  시각화 공급원 적재 0행 → 학생 도달 0회
    NLP-01  OCR 배포 경로 양쪽 비활성 → 학생 도달 0회 ("3회차"라고 그 태스크가 자인)
    REC-01  학생 앱이 `POST /v1/me/attempts`를 부르지 않아 추천 입력 0행
            ("반복 실수 4·5회차 — 만들고 입력을 잇지 않음·만들고 켜지 않음")

매번 대응은 **그 축의 런타임 리포트**였다. 즉 사고가 난 뒤에 그 축만 관측했다. 6회 중 최소
4회는 런타임이 아니라 **정적으로**(라우트 표 ↔ 클라 호출, CLI ↔ CI 스크립트) 탐지할 수 있었다.
이 모듈이 그 일반 탐지기다 — 축별 사후 관측이 아니라 **커밋 시점의 사전 차단**.

정본 설계: `docs/architecture/data_platform_module_gap_review.md` §3 D1.

무엇을 하고 무엇을 하지 않는가
----------------------------
**한다**: 공급(선언된 좌석)과 소비(그것을 실제로 부르는 쪽)를 4개 축에서 대조하고, 소비되지
않는 항목마다 **의도가 선언되어 있는지**를 검사한다.

**하지 않는다**: 활성화·배선·writer 신설. 이 모듈은 *가시화와 차단*이지 활성화가 아니다
(`NLP-01` ⑥·`REC-01` ⑤와 동형). 미도달을 발견해도 고치지 않고, 선언되지 않은 미도달만 막는다.

판정 규약 — 미도달 *수*가 아니라 *미분류*가 실패다
-----------------------------------------------
미도달률 자체를 게이트로 걸면 즉시 영구 red이고 의미도 없다. 콘텐츠 저작 API(`POST /v1/problems`)
는 학생 앱이 부르지 않는 것이 **정상**이고, 배치 생성기 CLI는 운영자가 손으로 돌리는 것이
**정상**이다. 그래서 이 게이트가 요구하는 것은 도달률이 아니라 **의도의 선언**이다:

    reached          소비 좌석이 실측됨 — 자동 판정(대장 등재 불요)
    by-design:<사유>  소비자가 없는 것이 설계 의도 — **사유 문자열 필수**
    pending-task:<id> 미도달이나 백로그가 추적 중 — 유예(아래 규약)
    (선언 없음)       → **unclassified · exit 1**

수용기준 ②의 4분류를 축 중립 어휘로 옮긴 것이다(`student-reached`→`reached`,
`server-only-by-design`→`by-design`) — HTTP 외 축(EventType·ORM·CLI)에도 같은 어휘를 쓰기 위함.

이 규약의 예방 성질: **새 라우트를 추가하면 의도를 선언하기 전까지 CI가 red**다. `EventType`의
`EVENT_DATA_CONTRACT ∪ CONTRACT_EXEMPT == 전체`를 거버넌스 테스트로 고정한 기존 패턴
(`schema/event_data_contract.py`)을 라우트·CLI 축으로 확장한 것이며, 새 발명이 아니라 검증된
패턴의 이식이다.

유예 대장 규약 (유예의 조용한 영구화 차단)
---------------------------------------
`pending-task:<id>`는 `backlog/tasks/<id>.yaml`이 **실재하고 `status != done`**일 때만 유효하다.
태스크가 사라지거나 done이 되면 exit 1 — 유예를 걷으라는 신호다. `backlog/`가 단일 진실
원천이므로 **새 대장 파일을 만들지 않는다**(`scripts/harness`도 import하지 않는다 — 별 패키지·
계층 경계. `status` 필드만 `yaml.safe_load`로 읽는다).

`provenance_audit._KNOWN_GAPS`는 그랜드파더 사유에 태스크 id를 *문자열로만* 적어 두는데, 그
연결을 기계가 검사하지 않는다. 이 모듈은 그 구멍을 메운다(같은 규약을 `OPS-18`이 공유한다).

수집기 파손 방어 (exit 2)
------------------------
정규식이 깨져 dart 호출을 0건 수집하면 "전부 미도달"이 아니라 오히려 **"모든 항목이 유예에
걸려 통과"**로 위장될 수 있다. 각 축의 공급·소비 수에 하한을 두고, 미만이면 판정이 아니라
**입력 오류(exit 2)**로 실패한다(`visualization_reach_report._EXIT_INPUT_ERROR` 선례).
"성공/실패 양쪽에서 같은 값을 내는 검사는 검증이 아니라 위장"이라는 규칙의 자기 적용이다.

사용:
    python -m whymath_backend.ops.reach_audit
    python -m whymath_backend.ops.reach_audit --json reach_report.json
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from whymath_backend.app import create_app
from whymath_backend.schema.enums import EventType

__all__ = [
    "AxisResult",
    "ItemVerdict",
    "ReachReport",
    "app_route_entries",
    "build_report",
    "dart_call_entries",
    "main",
    "render_report",
    "route_paths",
]

_EXIT_OK = 0
_EXIT_VIOLATIONS = 1
_EXIT_INPUT_ERROR = 2

_BY_DESIGN = "by-design:"
_PENDING_TASK = "pending-task:"

# 축 이름 — 리포트 키이자 대장 키.
AXIS_HTTP = "http_routes"
AXIS_EVENT = "event_types"
AXIS_TIMESERIES = "timeseries_writers"
AXIS_CLI = "harness_clis"

# 수집기 파손 하한(exit 2). 실측(2026-08-03) 대비 넉넉히 낮게 잡아 정상 변동에는 걸리지 않고
# *추출기 자체가 깨진* 경우(0건·한 자릿수)만 잡는다. 실측: 라우트 87·dart 13·EventType 11·CLI 35.
_FLOORS: dict[str, int] = {
    "routes": 40,
    "dart_calls": 8,
    "event_types": 8,
    "timeseries_models": 1,
    "clis": 20,
}


def repo_root() -> Path:
    """저장소 루트 — ops/ → whymath_backend/ → backend/ → src/ → repo root.

    `provenance_audit.default_corpus_root`·harness CLI 공통 관용구(`parents[4]`)와 동일.
    """
    return Path(__file__).resolve().parents[4]


# ──────────────────────────────────────────────────────────────────────────
# 경로 정규화 — 서버(`{problem_id}`)와 dart(`$problemId`)의 표기를 한 축으로 모은다
# ──────────────────────────────────────────────────────────────────────────

_SERVER_PARAM = re.compile(r"\{[^}]*\}")
_DART_PARAM = re.compile(r"\$\{?[A-Za-z_][A-Za-z0-9_]*\}?")
_PARAM_TOKEN = "{param}"


def normalize_server_path(path: str) -> str:
    """FastAPI 경로의 path parameter 이름을 지운다 — `/v1/problems/{problem_id}` → `.../{param}`."""
    return _SERVER_PARAM.sub(_PARAM_TOKEN, path)


def normalize_dart_path(path: str) -> str:
    """dart 문자열 보간을 지운다 — `/v1/problems/$problemId` → `/v1/problems/{param}`."""
    return _DART_PARAM.sub(_PARAM_TOKEN, path)


# ──────────────────────────────────────────────────────────────────────────
# 축 1 — HTTP 라우트 ↔ Flutter 클라이언트 호출
# ──────────────────────────────────────────────────────────────────────────


def _collect_routes(routes: Any) -> list[tuple[str, str]]:
    """`(method, path)` 목록. FastAPI 0.140 lazy include 래퍼를 재귀로 푼다.

    **실측 함정(재구현 금지 사유)**: FastAPI 0.140부터 `include_router()`가 하위 라우트를
    `app.routes`로 평탄화하지 않고 `_IncludedRouter` 래퍼 1개만 얹는다(래퍼는 `path`가 없고
    `original_router`를 들고 있다). 순진하게 `app.routes`의 `path`만 모으면 **`/v1/**` 전체가
    통째로 누락되고**, 그러면 이 감사는 "미도달 0건"으로 조용히 통과한다 — 정확히 이 모듈이
    막으려는 위장이다. 이 재귀는 `test_slo_contract.py`가 실측으로 확립한 것을 승계한 것이다.
    """
    found: list[tuple[str, str]] = []
    for route in routes:
        inner = getattr(route, "original_router", None)
        if inner is not None:  # FastAPI 0.140 lazy include 래퍼
            found.extend(_collect_routes(inner.routes))
            continue
        path = getattr(route, "path", None)
        if not isinstance(path, str) or not path:
            continue
        methods = getattr(route, "methods", None) or ()
        for method in sorted(str(m) for m in methods):
            if method in {"HEAD", "OPTIONS"}:  # 프레임워크 자동 부가 — 소비 대상이 아니다
                continue
            found.append((method, path))
    return found


@lru_cache(maxsize=1)
def app_route_entries() -> tuple[tuple[str, str], ...]:
    """`create_app()`의 실제 `(method, path)` 표(정규화 전 원본 경로)."""
    return tuple(sorted(set(_collect_routes(create_app().routes))))


@lru_cache(maxsize=1)
def route_paths() -> frozenset[str]:
    """`create_app()`의 실제 라우트 *경로* 집합(메서드 무시).

    `tests/backend/ops/test_slo_contract.py`가 이 함수를 import해 쓴다 — OPS-04 SLO 런북의
    "문서가 안내하는 경로가 실재하는가" 검증이 그것이다. 그 파일에 있던 구현을 여기로 승격해
    라우트 표 추출의 **단일 진실 원천**으로 만들었다(위 `_collect_routes` 도크스트링의 함정을
    두 곳에서 각자 풀지 않도록).
    """
    return frozenset(path for _, path in app_route_entries())


_DART_CALL = re.compile(r"_dio\.(get|post|put|patch|delete)[^(]*\(\s*'([^']*)'", re.DOTALL)


def dart_call_entries(mobile_lib: Path) -> tuple[tuple[str, str], ...]:
    """Flutter가 실제로 호출하는 `(METHOD, 정규화 경로)` 집합.

    호출 형태는 전부 `_dio.<method><제네릭>(\\n  '<path>', …)`이다(실측 8파일 13호출). 메서드와
    경로 사이에 제네릭 인자와 **개행**이 끼므로 줄 단위 정규식으로는 잡히지 않는다(DOTALL 필수).
    제네릭 안에는 `(`가 없으므로 `[^(]*`로 건너뛴다.
    """
    found: set[tuple[str, str]] = set()
    for source in sorted(mobile_lib.rglob("*.dart")):
        text = source.read_text(encoding="utf-8")
        for match in _DART_CALL.finditer(text):
            path = match.group(2)
            if not path.startswith("/"):  # 상대 경로·비-URL 리터럴은 대상 아님
                continue
            found.add((match.group(1).upper(), normalize_dart_path(path)))
    return tuple(sorted(found))


# ──────────────────────────────────────────────────────────────────────────
# 축 2 — EventType ↔ 생산 좌석(`build_event_data`)
# ──────────────────────────────────────────────────────────────────────────


def _iter_python_sources(package_root: Path) -> list[Path]:
    return sorted(p for p in package_root.rglob("*.py") if "__pycache__" not in p.parts)


@lru_cache(maxsize=8)
def _parse_module(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def produced_event_types(package_root: Path) -> tuple[str, ...]:
    """`build_event_data(EventType.X, …)`로 실제 생산되는 EventType 이름 집합.

    첫 인자가 `EventType.검산결과` 형태의 **리터럴 속성 접근**이라 AST로 정확히 잡힌다(실측:
    `api/coach.py` 2곳·`api/interactions.py` 1곳). 변수로 우회하는 호출은 없다 — 생겼다면
    여기서 잡히지 않으므로 그 EventType은 미도달로 보고되고, 대장 등재를 강제받는다(안전 방향).
    """
    produced: set[str] = set()
    for source in _iter_python_sources(package_root):
        for node in ast.walk(_parse_module(source)):
            if not isinstance(node, ast.Call) or not node.args:
                continue
            func = node.func
            name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)
            if name != "build_event_data":
                continue
            first = node.args[0]
            if (
                isinstance(first, ast.Attribute)
                and isinstance(first.value, ast.Name)
                and first.value.id == "EventType"
            ):
                produced.add(first.attr)
    return tuple(sorted(produced))


# ──────────────────────────────────────────────────────────────────────────
# 축 3 — TimescaleDB 집계 테이블 ORM ↔ writer
# ──────────────────────────────────────────────────────────────────────────

_TIMESERIES_MODULE = "whymath_backend.db.models.timeseries"


def timeseries_models(package_root: Path) -> tuple[str, ...]:
    """`db/models/timeseries.py`가 선언한 ORM 모델 클래스명."""
    path = package_root / "db" / "models" / "timeseries.py"
    if not path.is_file():
        return ()
    module = _parse_module(path)
    return tuple(
        sorted(node.name for node in module.body if isinstance(node, ast.ClassDef) and node.bases)
    )


def timeseries_writers(package_root: Path, models: tuple[str, ...]) -> dict[str, tuple[str, ...]]:
    """모델명 → 그 ORM을 **생성(write)** 하는 모듈 목록.

    ⚠️ 이름만 보면 안 된다 — `schema/timeseries.py`에 **동명의 Pydantic 클래스**가 있어서
    이름 기반 탐지는 스키마 사용을 ORM 적재로 오인한다(실측 확인). 그래서 `db.models`에서
    import한 모듈만 대상으로 하고, 그 안에서 **생성자 호출**이 있을 때만 writer로 센다.
    읽기·삭제 참조(`select`/`delete` — `privacy/{erasure,export,retention}`)는 writer가 아니다.
    """
    writers: dict[str, set[str]] = {name: set() for name in models}
    for source in _iter_python_sources(package_root):
        if source.parts[-3:-1] == ("db", "models"):
            continue  # 선언 자신은 소비가 아니다
        module = _parse_module(source)
        imported: set[str] = set()
        for node in ast.walk(module):
            if isinstance(node, ast.ImportFrom) and node.module:
                if node.module == _TIMESERIES_MODULE or node.module.endswith("db.models"):
                    imported.update(alias.asname or alias.name for alias in node.names)
        candidates = imported & set(models)
        if not candidates:
            continue
        rel = source.relative_to(package_root).with_suffix("").as_posix().replace("/", ".")
        for node in ast.walk(module):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            called = func.id if isinstance(func, ast.Name) else None
            if called in candidates:
                writers[str(called)].add(rel)
    return {name: tuple(sorted(mods)) for name, mods in writers.items()}


# ──────────────────────────────────────────────────────────────────────────
# 축 4 — harness/ops CLI ↔ CI 실행 (직접 + in-process import 전이)
# ──────────────────────────────────────────────────────────────────────────

_CLI_PACKAGES = ("harness", "ops")
_CI_MODULE_RUN = re.compile(r"-m\s+(whymath_backend\.[\w.]+)")


def cli_modules(package_root: Path) -> tuple[str, ...]:
    """`harness/`·`ops/`에서 모듈 레벨 `def main(`을 가진 모듈(= 실행 가능한 CLI)."""
    found: list[str] = []
    for pkg in _CLI_PACKAGES:
        for source in sorted((package_root / pkg).glob("*.py")):
            module = _parse_module(source)
            if any(isinstance(n, ast.FunctionDef) and n.name == "main" for n in module.body):
                found.append(f"{pkg}.{source.stem}")
    return tuple(sorted(found))


def ci_executed_modules(ci_path: Path) -> tuple[str, ...]:
    """`ci.yml`의 `run` 스크립트가 `python -m`으로 직접 실행하는 whymath_backend 모듈."""
    if not ci_path.is_file():
        return ()
    spec: Any = yaml.safe_load(ci_path.read_text(encoding="utf-8"))
    found: set[str] = set()
    for job in ((spec or {}).get("jobs") or {}).values():
        for step in (job or {}).get("steps") or []:
            if isinstance(step, dict) and step.get("run"):
                for match in _CI_MODULE_RUN.finditer(str(step["run"])):
                    found.add(match.group(1).removeprefix("whymath_backend."))
    return tuple(sorted(found))


def _module_imports(package_root: Path, source: Path) -> set[str]:
    """이 모듈이 import하는 whymath_backend 내부 모듈(패키지 상대 dotted name).

    **`from <패키지> import <서브모듈>`을 반드시 풀어야 한다.** `qa_pipeline`은
    `from whymath_backend.harness import corpus_audit_eval, crosslink_demotion_eval`처럼
    *패키지에서 서브모듈을 꺼내는* 형태로 조립한다. 모듈 경로(`harness`)만 세면 그 CLI들이
    전부 "미도달"로 잡혀 오탐이 된다(수용기준 ① — 실제로 첫 실행에서 이 오탐이 났다).
    그래서 `<module>`과 `<module>.<name>` 후보를 **둘 다** 낸다. 실재하지 않는 후보는
    호출부의 대상 집합 교집합에서 자연히 걸러진다.
    """
    rel_parts = source.relative_to(package_root).with_suffix("").parts
    package_parts = rel_parts[:-1] if rel_parts[-1] != "__init__" else rel_parts
    out: set[str] = set()

    def _emit(dotted: str, names: list[str]) -> None:
        out.add(dotted)
        out.update(f"{dotted}.{name}" for name in names)

    for node in ast.walk(_parse_module(source)):
        if isinstance(node, ast.ImportFrom):
            names = [alias.name for alias in node.names]
            if node.level:  # 상대 import — 현재 패키지 기준으로 해석
                base = list(package_parts[: len(package_parts) - (node.level - 1)])
                if node.module:
                    base += node.module.split(".")
                _emit(".".join(base), names)
            elif node.module and node.module.startswith("whymath_backend."):
                _emit(node.module.removeprefix("whymath_backend."), names)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("whymath_backend."):
                    out.add(alias.name.removeprefix("whymath_backend."))
    return out


def reached_clis(package_root: Path, clis: tuple[str, ...], ci_roots: tuple[str, ...]) -> set[str]:
    """도달한 CLI — ⑴ CI가 직접 실행 ⑵ 프로덕션 코드가 import ⑶ ⑴·⑵에서 전이 import.

    ⑶이 핵심이다. `qa_pipeline`은 `corpus_audit_eval`을 **in-process로 import해** 조립한다
    (이 저장소는 harness CLI를 subprocess로 부르지 않는 것이 관례다). 직접 실행만 세면 그런
    모듈이 전부 "미도달"로 잡혀 오탐이 된다(수용기준 ①).

    ⑵는 `harness`/`ops` 밖(= 프로덕션 런타임)이 import하는 경우다 — 서빙 경로에 들어가 있으면
    CLI로 안 돌아도 죽은 코드가 아니다.

    테스트의 import는 세지 않는다(스코프는 `src/backend`) — 테스트가 함수를 만진다는 것과
    파이프라인에 배선됐다는 것은 다르며, 후자만이 이 축의 관심사다.
    """
    cli_set = set(clis)
    graph: dict[str, set[str]] = {}
    production_roots: set[str] = set()
    for source in _iter_python_sources(package_root):
        rel = source.relative_to(package_root).with_suffix("").as_posix().replace("/", ".")
        imports = _module_imports(package_root, source)
        graph[rel] = imports
        if not rel.startswith(_CLI_PACKAGES):
            production_roots.update(imports & cli_set)

    reached: set[str] = {m for m in ci_roots if m in cli_set} | production_roots
    frontier = list(reached)
    while frontier:
        current = frontier.pop()
        for target in graph.get(current, ()):  # 전이 폐포
            if target in cli_set and target not in reached:
                reached.add(target)
                frontier.append(target)
    return reached


# ──────────────────────────────────────────────────────────────────────────
# 분류 대장 — 미도달 항목의 *의도*를 선언한다 (여기가 이 게이트의 본체)
# ──────────────────────────────────────────────────────────────────────────
#
# 값 형식: `by-design:<사유>` 또는 `pending-task:<백로그 태스크 id>`.
# 판단 근거가 약하면 `by-design`보다 `pending-task`가 안전하다 — 유예는 만료되지만
# 오분류는 영구히 남는다.

_FRAMEWORK = "by-design:FastAPI 자동 생성 문서·스키마 표면 — 학생 클라이언트 소비 대상이 아니다"
_OPS_PROBE = "by-design:운영 프로브(OPS-01/OPS-04) — 배포·헬스체크·모니터링이 호출한다"
_AUTHORING = (
    "by-design:콘텐츠 저작·운영 표면 — 학생 앱이 아니라 운영자가 쓴다. 관리자 콘솔은 "
    "1인 capacity 가드로 의도적 미구현(operations_module_gap_review.md §2-④)"
)
_PRIVACY_RIGHT = (
    "by-design:법정 권리 이행 표면(PIPA 열람·삭제·감사) — 학생 앱 UI가 아니라 요청 처리 "
    "경로다. 앱 노출은 SEC 축의 별건 판단"
)
_INTERNAL_TOOL = "by-design:내부 도구·하네스 소비 표면 — 학생 클라이언트 대상이 아니다"

_BATCH_GENERATOR = (
    "by-design:코퍼스 생성·가공 배치 — 운영자가 입력·비용·판단을 쥐고 손으로 돌리는 것이 "
    "정상이다. CI 상시 실행은 LLM 비용을 매 PR마다 태우는 설계가 된다"
)
_LIVE_DEPENDENT = (
    "by-design:라이브 의존(API 키·GPU·Langfuse) — CI에 자격증명이 없어 원리적으로 못 돈다. "
    "가동 절차는 measurement_line_enablement.md 소관"
)
_NEEDS_LIVE_SAMPLE = (
    "by-design:실 PG·실학생 표본 의존 리포트 — 파일럿(S3-01) 전에는 입력이 0이라 CI에서 "
    "돌려도 NO_DATA만 난다"
)
_OFFLINE_REPORT = (
    "by-design:빌드타임 관측 리포트(게이트 아님) — 수치를 보려고 사람이 돌린다. exit 0/1로 "
    "머지를 막는 판정기가 아니므로 CI 상시 배선 대상이 아니다"
)

_MANIFEST: dict[str, dict[str, str]] = {
    # ── 축 1. HTTP 라우트 ────────────────────────────────────────────────
    # 학생 앱이 부르지 않는 것이 *정상*인 표면과, 부르지 않아 *문제*인 표면을 여기서 가른다.
    AXIS_HTTP: {
        # 프레임워크 자동 표면
        "GET /docs": _FRAMEWORK,
        "GET /docs/oauth2-redirect": _FRAMEWORK,
        "GET /openapi.json": _FRAMEWORK,
        "GET /redoc": _FRAMEWORK,
        # 운영 프로브
        "GET /health": _OPS_PROBE,
        "GET /health/live": _OPS_PROBE,
        "GET /health/ready": _OPS_PROBE,
        "GET /status": _OPS_PROBE,
        # 콘텐츠 저작·운영 CRUD
        "GET /v1/concepts": _AUTHORING,
        "POST /v1/concepts": _AUTHORING,
        "GET /v1/concepts/search": _AUTHORING,
        "GET /v1/concepts/{param}": _AUTHORING,
        "PATCH /v1/concepts/{param}": _AUTHORING,
        "DELETE /v1/concepts/{param}": _AUTHORING,
        "GET /v1/concepts/{param}/edges": _AUTHORING,
        "GET /v1/problems": _AUTHORING,
        "POST /v1/problems": _AUTHORING,
        "PATCH /v1/problems/{param}": _AUTHORING,
        "DELETE /v1/problems/{param}": _AUTHORING,
        "GET /v1/problems/{param}/relations": _AUTHORING,
        "GET /v1/problems/{param}/steps": _AUTHORING,
        "POST /v1/generate": _AUTHORING,
        "GET /v1/jobs/{param}": _AUTHORING,
        # 법정 권리·프라이버시 이행 표면
        "DELETE /v1/me": _PRIVACY_RIGHT,
        "GET /v1/me/deletions": _PRIVACY_RIGHT,
        "GET /v1/me/export": _PRIVACY_RIGHT,
        "GET /v1/me/privacy-audit": _PRIVACY_RIGHT,
        "POST /v1/users/me/parental-consent": (
            "by-design:법정대리인 동의 절차 표면 — 실 본인확인은 변호사 판단이 선행하는 "
            "MGMT-01 소관이라 앱 배선 자체가 그 뒤다(법령 유래 절차의 기계 대체 금지)"
        ),
        # 내부 도구·측정 표면
        "GET /v1/me/harness-metrics": _INTERNAL_TOOL,
        "GET /v1/gating/gifted": _INTERNAL_TOOL,
        "GET /v1/gating/metacognition": _INTERNAL_TOOL,
        "GET /v1/gating/retake": _INTERNAL_TOOL,
        "GET /v1/gating/school-progress": _INTERNAL_TOOL,
        "GET /v1/gating/suneung": _INTERNAL_TOOL,
        "GET /v1/gating/thinking": _INTERNAL_TOOL,
        # 인증·디바이스 — 클라가 콜백만 호출하고 갱신·해지 흐름은 미배선
        "GET /v1/auth/{param}/state": (
            "by-design:OAuth `state` 발급은 콜백 흐름의 서버측 짝 — 앱은 provider 리다이렉트로 "
            "받으므로 직접 호출하지 않는다(SEC-08)"
        ),
        "POST /v1/auth/refresh": "pending-task:SEC-10-session-visibility-global-logout",
        "POST /v1/auth/logout": "pending-task:SEC-10-session-visibility-global-logout",
        "GET /v1/devices": "pending-task:SEC-10-session-visibility-global-logout",
        "POST /v1/devices/register": "pending-task:SEC-10-session-visibility-global-logout",
        "POST /v1/devices/{param}/revoke": "pending-task:SEC-10-session-visibility-global-logout",
        "GET /v1/me/sessions": "pending-task:SEC-10-session-visibility-global-logout",
        "DELETE /v1/me/sessions/{param}": "pending-task:SEC-10-session-visibility-global-logout",
        "PATCH /v1/me/sessions/{param}/end": "pending-task:S3-16-behavior-telemetry-writers",
        # 학습 루프 텔레메트리 — **여기가 진짜 미도달**(반복 실수 5회차의 현장)
        "POST /v1/me/attempts": "pending-task:REC-01-recommendation-reach-observability",
        "POST /v1/me/ability/snapshots": "pending-task:REC-01-recommendation-reach-observability",
        "GET /v1/me/ability/snapshots": "pending-task:REC-01-recommendation-reach-observability",
        "GET /v1/me/ability": "pending-task:REC-01-recommendation-reach-observability",
        "GET /v1/me/ability/by-concept": "pending-task:REC-01-recommendation-reach-observability",
        "GET /v1/me/ability/history": "pending-task:REC-01-recommendation-reach-observability",
        "GET /v1/me/mastery": "pending-task:REC-01-recommendation-reach-observability",
        "GET /v1/me/mastery/current": "pending-task:REC-01-recommendation-reach-observability",
        "GET /v1/me/skill-mastery": "pending-task:REC-01-recommendation-reach-observability",
        "GET /v1/me/diagnosis/summary": "pending-task:REC-01-recommendation-reach-observability",
        "POST /v1/me/objectives/{param}/study": "pending-task:PED-05-learner-state-assembly",
        "POST /v1/me/objectives/{param}/outcome": (
            "pending-task:REC-03-recommendation-outcome-accounting"
        ),
        # 약점 개념 코칭 — 공급원(scenes)만 배선되고 개념 화면은 미도달
        "GET /v1/me/weak-concepts": "pending-task:REC-01-recommendation-reach-observability",
        "GET /v1/me/weak-concepts/{param}/coaching": (
            "pending-task:REC-01-recommendation-reach-observability"
        ),
        "GET /v1/me/weak-concepts/{param}/learning-path": (
            "pending-task:REC-01-recommendation-reach-observability"
        ),
        "GET /v1/me/weak-concepts/{param}/prerequisites": (
            "pending-task:REC-01-recommendation-reach-observability"
        ),
        # 대화·평가 이력 — 서버 좌석만 있고 앱 화면이 없다
        "GET /v1/me/dialogues": "pending-task:S3-16-behavior-telemetry-writers",
        "DELETE /v1/me/dialogues/{param}": "pending-task:S3-16-behavior-telemetry-writers",
        "PATCH /v1/me/dialogues/{param}/end": "pending-task:S3-16-behavior-telemetry-writers",
        "GET /v1/me/assessments": "pending-task:S3-16-behavior-telemetry-writers",
        "DELETE /v1/me/assessments/{param}": "pending-task:S3-16-behavior-telemetry-writers",
        "PATCH /v1/me/assessments/{param}/complete": (
            "pending-task:S3-16-behavior-telemetry-writers"
        ),
        # OCR·검증·시각화·음성 — 일부만 앱에 닿아 있다
        "POST /v1/ocr/pages": "pending-task:NLP-01-ocr-reachability-observability",
        "POST /v1/verify-answer": "pending-task:NLP-02-server-answer-grading-shadow",
        "POST /v1/verify-step": "pending-task:NLP-02-server-answer-grading-shadow",
        "GET /v1/visualizations/spec": "pending-task:VIZ-02-generator-render-contract-derive",
        "POST /v1/visualizations/spec": "pending-task:VIZ-02-generator-render-contract-derive",
        "POST /v1/visualizations/weak-concept": (
            "pending-task:VIZ-02-generator-render-contract-derive"
        ),
        "POST /v1/speech/latex": (
            "by-design:음성 입력은 Phase 2+ 노출 대상 — 서버 좌석만 선행 배선된 상태이고 "
            "앱 진입점 자체가 없다(활성화 판단은 이 게이트 밖)"
        ),
        "GET /v1/users/me": (
            "by-design:앱은 온보딩에서 `PATCH /v1/users/me`만 쓴다(프로필 조회는 로그인 "
            "응답에 실려 온다) — 별도 GET 왕복이 없는 것이 현 설계"
        ),
    },
    # ── 축 2. EventType ─────────────────────────────────────────────────
    # 휴면 8종은 전부 S3-16이 추적한다(생산자 0이라 페이로드 계약도 면제 상태).
    AXIS_EVENT: {
        name: "pending-task:S3-16-behavior-telemetry-writers"
        for name in (
            "문제읽기",
            "조건분석",
            "그래프그리기",
            "계산",
            "지움",
            "막힘",
            "힌트요청",
            "답입력",
        )
    },
    # ── 축 3. TimescaleDB 집계 테이블 ───────────────────────────────────
    AXIS_TIMESERIES: {
        "DailyLearningMetrics": "pending-task:S3-16-behavior-telemetry-writers",
        "UserBehaviorMetrics": "pending-task:S3-16-behavior-telemetry-writers",
        "ProblemSolveTimeDistribution": "pending-task:S3-16-behavior-telemetry-writers",
    },
    # ── 축 4. harness/ops CLI ───────────────────────────────────────────
    # 대부분은 *운영자가 손으로 돌리는 것이 정상*인 배치·리포트다. CI 게이트여야 하는데
    # 안 도는 것만 유예로 남긴다.
    AXIS_CLI: {
        # 코퍼스 생성·가공 배치 — 운영자 실행이 정상(입력·비용·판단이 사람 몫)
        "harness.conceptual_count_mc_batch": _BATCH_GENERATOR,
        "harness.finite_probability_batch": _BATCH_GENERATOR,
        "harness.misconception_mc_batch": _BATCH_GENERATOR,
        "harness.problem_corpus_accumulate": _BATCH_GENERATOR,
        "harness.problem_corpus_batch": _BATCH_GENERATOR,
        "harness.problem_corpus_rephrase": _BATCH_GENERATOR,
        "harness.problem_corpus_rephrase_diagnose": _BATCH_GENERATOR,
        "harness.problem_corpus_rephrase_sweep": _BATCH_GENERATOR,
        "harness.problem_corpus_tag": _BATCH_GENERATOR,
        "harness.problem_type_backfill": _BATCH_GENERATOR,
        "harness.root_aggregate_batch": _BATCH_GENERATOR,
        "harness.reviewer_sample_package": _BATCH_GENERATOR,
        # 라이브 의존 — CI에 키·GPU가 없어 원리적으로 못 돈다
        "ops.cost_probe": _LIVE_DEPENDENT,
        "ops.cost_report": _LIVE_DEPENDENT,
        "ops.live_preflight": _LIVE_DEPENDENT,
        "ops.dialogue_encryption_preflight": _LIVE_DEPENDENT,
        "ops.wh1_shadow_probe": _LIVE_DEPENDENT,
        "harness.wh1_shadow_harvest": _LIVE_DEPENDENT,
        # 실 DB·실학생 표본 의존 리포트
        "harness.pilot_kpi_baseline": _NEEDS_LIVE_SAMPLE,
        "harness.surrogate_baseline_report": _NEEDS_LIVE_SAMPLE,
        # 게이트여야 하는데 CI에 없는 것 — 유예로 추적
        "harness.prompt_asset_audit": "pending-task:OPS-16-l3-prompt-asset-audit",
        "harness.problem_bank_coverage": _OFFLINE_REPORT,
        "harness.visualization_reach_report": _OFFLINE_REPORT,
        "harness.rephrased_corpus_hygiene": _OFFLINE_REPORT,
        "harness.agreement_gate_cli": (
            "by-design:후보 모델 결선용 수동 비교 도구(McNemar) — 상시 게이트가 아니라 "
            "승격 판정 시점에 사람이 돌린다"
        ),
        "harness.pedagogy_policy_eval": _OFFLINE_REPORT,
        "harness.residue_cross_verify_eval": _LIVE_DEPENDENT,
        # `ops.reach_audit`(이 모듈 자신)은 대장에 없다 — 전용 `reach-audit` 잡이 `python -m`으로
        # 부르므로 CI 스캔이 도달로 잡는다. 실제로 이 항목을 by-design으로 적어 뒀더니
        # `stale-waiver`가 즉시 잡아냈다(2026-08-03 실측 — 낡은 예외 탐지의 변별력 실증).
    },
}


# ──────────────────────────────────────────────────────────────────────────
# 판정
# ──────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class ItemVerdict:
    """공급 항목 1건의 판정."""

    axis: str
    key: str
    status: str  # reached | by-design | pending-task | unclassified | stale-waiver | ...
    note: str

    @property
    def is_violation(self) -> bool:
        return self.status not in {"reached", "by-design", "pending-task"}

    def to_json(self) -> dict[str, str]:
        return {"axis": self.axis, "key": self.key, "status": self.status, "note": self.note}


@dataclass(frozen=True, slots=True)
class AxisResult:
    """축 1개의 집계."""

    axis: str
    verdicts: tuple[ItemVerdict, ...]

    @property
    def supplied(self) -> int:
        return len(self.verdicts)

    @property
    def reached(self) -> int:
        return sum(1 for v in self.verdicts if v.status == "reached")

    @property
    def violations(self) -> tuple[ItemVerdict, ...]:
        return tuple(v for v in self.verdicts if v.is_violation)

    def to_json(self) -> dict[str, Any]:
        return {
            "supplied": self.supplied,
            "reached": self.reached,
            "violations": [v.to_json() for v in self.violations],
            "items": [v.to_json() for v in self.verdicts],
        }


@dataclass(frozen=True, slots=True)
class ReachReport:
    """전 축 리포트 + 최종 판정."""

    axes: tuple[AxisResult, ...]

    @property
    def violations(self) -> tuple[ItemVerdict, ...]:
        return tuple(v for axis in self.axes for v in axis.violations)

    @property
    def exit_code(self) -> int:
        return _EXIT_OK if not self.violations else _EXIT_VIOLATIONS

    def to_json(self) -> dict[str, Any]:
        return {
            "axes": {axis.axis: axis.to_json() for axis in self.axes},
            "overall": {"pass": not self.violations, "violations": len(self.violations)},
        }


class CollectorError(RuntimeError):
    """수집기 파손 — 판정이 아니라 입력 오류(exit 2). 위장 통과 방지."""


def _task_status(backlog_tasks: Path, task_id: str) -> str | None:
    """`backlog/tasks/<id>.yaml`의 status. 파일이 없으면 None."""
    path = backlog_tasks / f"{task_id}.yaml"
    if not path.is_file():
        return None
    data: Any = yaml.safe_load(path.read_text(encoding="utf-8"))
    status = (data or {}).get("status")
    return str(status) if status is not None else None


def _classify(axis: str, key: str, is_reached: bool, backlog_tasks: Path) -> ItemVerdict:
    declared = _MANIFEST.get(axis, {}).get(key)
    if is_reached:
        if declared is not None:
            # 도달했는데 대장에 남아 있다 — 유예·예외가 낡았다는 신호(조용히 방치 금지).
            note = f"이미 도달했는데 대장에 남음: {declared}"
            return ItemVerdict(axis, key, "stale-waiver", note)
        return ItemVerdict(axis, key, "reached", "")
    if declared is None:
        return ItemVerdict(axis, key, "unclassified", "미도달인데 의도 선언이 없다")
    if declared.startswith(_BY_DESIGN):
        reason = declared[len(_BY_DESIGN) :].strip()
        if not reason:
            return ItemVerdict(axis, key, "missing-reason", "by-design인데 사유가 비어 있다")
        return ItemVerdict(axis, key, "by-design", reason)
    if declared.startswith(_PENDING_TASK):
        task_id = declared[len(_PENDING_TASK) :].strip()
        status = _task_status(backlog_tasks, task_id)
        if status is None:
            return ItemVerdict(axis, key, "expired-waiver", f"유예 근거 태스크 부재: {task_id}")
        if status == "done":
            return ItemVerdict(axis, key, "expired-waiver", f"유예 근거 태스크 완료됨: {task_id}")
        return ItemVerdict(axis, key, "pending-task", f"{task_id} ({status})")
    return ItemVerdict(axis, key, "malformed", f"알 수 없는 분류 값: {declared}")


def build_report(root: Path | None = None) -> ReachReport:
    """4축 전수 감사. DB·LLM·HTTP 0(빌드타임 결정론).

    Raises:
        CollectorError: 어느 축이든 수집 수가 하한 미만(추출기 파손) — exit 2로 이어진다.
    """
    base = root or repo_root()
    package_root = base / "src" / "backend" / "whymath_backend"
    backlog_tasks = base / "backlog" / "tasks"

    routes = app_route_entries()
    dart_calls = set(dart_call_entries(base / "src" / "mobile" / "lib"))
    events = tuple(member.value for member in EventType)
    ts_models = timeseries_models(package_root)
    clis = cli_modules(package_root)

    for label, count in (
        ("routes", len(routes)),
        ("dart_calls", len(dart_calls)),
        ("event_types", len(events)),
        ("timeseries_models", len(ts_models)),
        ("clis", len(clis)),
    ):
        if count < _FLOORS[label]:
            raise CollectorError(
                f"{label} 수집 {count}건 — 하한 {_FLOORS[label]} 미만. 추출기가 깨졌을 가능성이 "
                "높다. '미도달 0건 통과'로 위장하지 않고 입력 오류로 실패한다."
            )

    produced = set(produced_event_types(package_root))
    writers = timeseries_writers(package_root, ts_models)
    ci_roots = ci_executed_modules(base / ".github" / "workflows" / "ci.yml")
    reached_cli = reached_clis(package_root, clis, ci_roots)

    http = tuple(
        _classify(
            AXIS_HTTP,
            f"{method} {normalize_server_path(path)}",
            (method, normalize_server_path(path)) in dart_calls,
            backlog_tasks,
        )
        for method, path in routes
    )
    event = tuple(
        _classify(AXIS_EVENT, name, name in produced, backlog_tasks) for name in sorted(events)
    )
    timeseries = tuple(
        _classify(AXIS_TIMESERIES, name, bool(writers.get(name)), backlog_tasks)
        for name in ts_models
    )
    cli = tuple(_classify(AXIS_CLI, name, name in reached_cli, backlog_tasks) for name in clis)

    return ReachReport(
        axes=(
            AxisResult(AXIS_HTTP, _dedup(http)),
            AxisResult(AXIS_EVENT, event),
            AxisResult(AXIS_TIMESERIES, timeseries),
            AxisResult(AXIS_CLI, cli),
        )
    )


def _dedup(verdicts: tuple[ItemVerdict, ...]) -> tuple[ItemVerdict, ...]:
    """정규화 후 같은 키로 합쳐지는 라우트를 1건으로(예: `{id}`가 다른 이름이어도 같은 좌석)."""
    seen: dict[str, ItemVerdict] = {}
    for verdict in verdicts:
        current = seen.get(verdict.key)
        if current is None or (current.status != "reached" and verdict.status == "reached"):
            seen[verdict.key] = verdict
    return tuple(seen[key] for key in sorted(seen))


def render_report(report: ReachReport) -> str:
    lines: list[str] = ["공급↔소비 도달 대장 (OPS-17) — 미도달 수가 아니라 미분류가 실패다", ""]
    for axis in report.axes:
        unreached = axis.supplied - axis.reached
        lines.append(
            f"[{axis.axis}] 공급 {axis.supplied} · 도달 {axis.reached} · 미도달 {unreached}"
            f" · 위반 {len(axis.violations)}"
        )
        for verdict in axis.violations:
            lines.append(f"    ✗ {verdict.status:16} {verdict.key} — {verdict.note}")
    lines.append("")
    if report.violations:
        lines.append(f"판정: 실패 — 위반 {len(report.violations)}건")
        lines.append("  미도달을 고치라는 뜻이 아니다. 그 미도달이 의도인지 선언하라는 뜻이다:")
        lines.append(f"  `{_BY_DESIGN}<사유>` 또는 `{_PENDING_TASK}<백로그 태스크 id>`")
    else:
        lines.append("판정: 통과 — 모든 공급 항목이 도달했거나 의도가 선언돼 있다")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m whymath_backend.ops.reach_audit",
        description="공급↔소비 도달 대장 — 미분류 공급 항목·만료 유예를 차단한다(OPS-17).",
    )
    parser.add_argument("--root", type=Path, default=None, help="저장소 루트(기본: 자동 탐지)")
    parser.add_argument("--json", type=Path, default=None, help="리포트를 JSON으로 저장할 경로")
    args = parser.parse_args(argv)

    try:
        report = build_report(args.root)
    except CollectorError as exc:
        print(f"[reach_audit] 수집기 파손: {exc}", file=sys.stderr)
        return _EXIT_INPUT_ERROR

    print(render_report(report))
    if args.json is not None:
        args.json.write_text(
            json.dumps(report.to_json(), ensure_ascii=False, indent=2), encoding="utf-8"
        )
    return report.exit_code


if __name__ == "__main__":  # pragma: no cover - CLI 진입점
    raise SystemExit(main())
