"""EOS 기능 인벤토리 + Migration Difficulty Matrix 생성기 (EOS-68).

계획서 100(§3.3 인벤토리 필드·§3.14 6축 18점 매트릭스)을 이 저장소에 적용한다.
산출 정본 = `backlog/inventory/feature_inventory.yaml`(기계가 읽는 장부) ·
해설 = `docs/reviews/eos_feature_inventory_migration_map.md`.

## 모집단 정의 (acceptance ① — "모집단 정의를 먼저 적는다")

**기능 = FastAPI 앱에 실제로 등록된 서빙 표면 1단위(라우터) + app.py 자체 엔드포인트.**
`app.py`의 `include_router()` 호출을 파싱해 모집단을 **기계로 도출**한다 — 손으로 목록을
쓰면 라우터 추가·제거 시 조용히 어긋난다. backlog 태스크(작업 단위)·harness CLI(운영자
도구)·배치는 모집단이 아니다: 계획서 100의 인벤토리 목적이 "서빙 중인 것의 이전 계획"이기
때문이다. 이 정의로 잡히지 않는 서빙(예: WS·cron)이 생기면 이 docstring과 파서를 함께 고친다.

## 6축 점수는 실측 대리지표다 (한계 명시)

계획서 100 §3.14의 6축을 사람이 감으로 매기지 않고 측정 가능한 대리지표로 환산한다.
대리지표는 축의 *근사*이지 정의가 아니다 — 임계는 아래 상수에 전부 드러나 있고, 바꾸면
전 기능의 점수가 일관되게 다시 계산된다(행별 손조정 불가 — 그것이 표를 신뢰할 근거다).

| 축 | 대리지표 | 한계 |
|---|---|---|
| A 과목결합도 | 1-hop 폐쇄의 ADAPTER/MIXED 모듈 수(BOUNDARY_MAP 판정) | 2-hop 이상 경유는 안 보임 |
| B DB결합도 | 폐쇄가 import하는 `db.models.*` 모듈 수 | 원시 SQL·문자열 참조 사각 |
| C 모듈결합도 | 라우터의 내부 직접 import 수 | fan-in(누가 나를 부르나)은 미측정 |
| D 테스트부족 | 전용 테스트 파일·함수 수 | 공유 스위트가 커버하는 경우 과대평가 |
| E 상태변경복잡도 | 쓰기 엔드포인트(POST/PUT/PATCH/DELETE) 수 | 읽기 경로의 캐시 변이 사각 |
| F 데이터이전난이도 | B와 동일 원천(모델 모듈 수)의 다른 밴드 | 행 수·마이그레이션 이력 미반영 |

## 출시 우선도는 **제안**이다 (acceptance ④)

`release_relevance` 필드는 검증설계서 v1(EOS-51)의 개발항목 코드 좌석 대응에서 기계적으로
나온 **제안**이며, 확정은 Kiki 몫이다(PR #916 관여도 트리아지 프로토콜과 통합 판정).
그쪽 트리아지와 축이 다르다 — 그쪽은 *backlog 태스크*의 "12월 검증 관여 여부", 이쪽은
*서빙 기능*의 "Core/Adapter 귀속 + 이전 난이도"다. 겹치는 판단은 재판정하지 않고 seat
코드 인용으로 대신한다.

사용법:
    python3 scripts/analysis/eos_feature_inventory.py            # 표준출력 마크다운 + 대시보드
    python3 scripts/analysis/eos_feature_inventory.py --write    # backlog/inventory/*.yaml 갱신

종료코드: 0 = 측정 성공 · 1 = 측정 실패(모집단 0·파싱 실패 등 — 빈 장부를 성공으로 위장 금지).
"""

from __future__ import annotations

import argparse
import ast
import importlib.util
import pathlib
import re
import sys
from dataclasses import dataclass, field
from typing import Any

REPO = pathlib.Path(__file__).resolve().parents[2]
BACKEND = REPO / "src" / "backend" / "whymath_backend"
TESTS_API = REPO / "tests" / "backend" / "api"
LEDGER = REPO / "backlog" / "inventory" / "feature_inventory.yaml"
SCAN_SCRIPT = pathlib.Path(__file__).with_name("eos_core_adapter_boundary_scan.py")

# ── 6축 임계 (0~3점) — 여기(와 _score의 A 규칙) 말고는 어디에도 점수 규칙이 없다 ──
B_DBMODEL = (0, 2, 5)  # 모델 모듈 수: 0 / 1~2 / 3~5 / 6+
C_IMPORTS = (3, 8, 15)  # 내부 직접 import: ≤3 / ≤8 / ≤15 / 16+
D_TESTFN = (10, 5, 1)  # 전용 테스트 함수: ≥10→0점 / ≥5→1 / ≥1→2 / 0→3
E_WRITES = (0, 2, 5)  # 쓰기 엔드포인트: 0 / 1~2 / 3~5 / 6+
F_TABLES = (0, 1, 3)  # 모델 모듈 수: 0 / 1 / 2~3 / 4+

# 판정 밴드 — 계획서 100 §3.14 그대로
BANDS = ((4, "KEEP"), (9, "REFACTOR"), (13, "HEAVY_REFACTOR"), (18, "REPLACE_CANDIDATE"))

# ── 손 유지 메타 — 측정 불가 필드만. 근거(seat)는 검증설계서 v1 개발항목 코드 ──
# relevance: verification-loop(12월 검증 관여 제안) / platform-invariant(법정·보안 불변) /
#            deferred-candidate(2027 이월 후보 제안)
FEATURE_META: dict[str, dict[str, str]] = {
    "app-core": dict(
        user="Platform",
        domain="AI Orchestration",
        relevance="verification-loop",
        seat="C1·A5 — /v1/generate 생성 표면·게이트웨이",
    ),
    "auth": dict(
        user="Student",
        domain="Identity",
        relevance="platform-invariant",
        seat="계획서 100 P0 목록 'User/Auth' — 폐쇄루프 진입점",
    ),
    "users": dict(
        user="Student",
        domain="Identity",
        relevance="platform-invariant",
        seat="법정대리인 동의 — CLAUDE.md 법령 유래 절차(기계 대체 금지)",
    ),
    "privacy": dict(
        user="Student",
        domain="Security",
        relevance="platform-invariant",
        seat="미성년 PII PEP — 불변 계약(전환 선언 §0-6)",
    ),
    "devices": dict(
        user="Student",
        domain="Security",
        relevance="platform-invariant",
        seat="디바이스 인증 — SEC 축",
    ),
    "rights": dict(
        user="Platform",
        domain="Content",
        relevance="verification-loop",
        seat="A4·G1~G6 저작권 원장·게이트 — 콘텐츠 생산 레일(LIC-01)",
    ),
    "concepts": dict(
        user="Student",
        domain="Knowledge Graph",
        relevance="verification-loop",
        seat="B4 개념 DB 조회 표면",
    ),
    "problems": dict(
        user="Student",
        domain="Content",
        relevance="verification-loop",
        seat="B7 문제 DB — 앵커 CU의 서빙 표면",
    ),
    "me": dict(
        user="Student",
        domain="Learning Model",
        relevance="verification-loop",
        seat="E3·E4 — 학습 이력·mastery 조회",
    ),
    "coach": dict(
        user="Student",
        domain="Pedagogy",
        relevance="verification-loop",
        seat="E2·C7 — 채점 연동 코칭·힌트",
    ),
    "verify": dict(
        user="Student",
        domain="Assessment",
        relevance="verification-loop",
        seat="D1·E2 — 결정론 채점 표면",
    ),
    "study": dict(
        user="Student",
        domain="Pedagogy",
        relevance="verification-loop",
        seat="E1 — 학습 공급·교수법 처치",
    ),
    "interactions": dict(
        user="Student", domain="Event", relevance="verification-loop", seat="E3 — AttemptEvent 수집"
    ),
    "solution_paths": dict(
        user="Student",
        domain="Content",
        relevance="verification-loop",
        seat="C5 — 단계별 풀이 점층 공개",
    ),
    "dsl": dict(
        user="Admin", domain="Content", relevance="verification-loop", seat="C2 — DSL 생성기 표면"
    ),
    "curricula": dict(
        user="Admin",
        domain="Curriculum",
        relevance="verification-loop",
        seat="B1 — 교육과정 Framework/Version 조회",
    ),
    "alignments": dict(
        user="Admin",
        domain="Curriculum",
        relevance="verification-loop",
        seat="B2·F1 — 개념↔성취기준 정렬 조회(앵커 매핑)",
    ),
    "gating": dict(
        user="Student",
        domain="Application Mode",
        relevance="deferred-candidate",
        seat="대응 개발항목 없음 — L6 모드는 12월 검증 밖",
    ),
    "ocr": dict(
        user="Student",
        domain="Interaction",
        relevance="deferred-candidate",
        seat="대응 없음 — E1은 MathLive 입력이지 OCR이 아님(검증설계서 §2)",
    ),
    "speech": dict(
        user="Student",
        domain="Interaction",
        relevance="deferred-candidate",
        seat="대응 없음 — 접근성 축",
    ),
    "visualization": dict(
        user="Student", domain="Interaction", relevance="deferred-candidate", seat="대응 없음"
    ),
    "scene": dict(
        user="Student", domain="Interaction", relevance="deferred-candidate", seat="대응 없음"
    ),
    "reports": dict(
        user="Student",
        domain="QA",
        relevance="deferred-candidate",
        seat="대응 없음 — 학생 결함 신고(RPT-01)",
    ),
}


def _load_classify() -> Any:
    name = "_eos_boundary_scan_for_inventory"
    spec = importlib.util.spec_from_file_location(name, SCAN_SCRIPT)
    assert spec is not None and spec.loader is not None, f"경계 스캔 로드 불가: {SCAN_SCRIPT}"
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(name, None)
    return module.classify


def _internal_imports(path: pathlib.Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    out: list[str] = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.ImportFrom)
            and node.module
            and node.module.startswith("whymath_backend.")
        ):
            out.append(node.module[len("whymath_backend.") :])
        elif isinstance(node, ast.Import):
            out.extend(
                a.name[len("whymath_backend.") :]
                for a in node.names
                if a.name.startswith("whymath_backend.")
            )
    return out


def _module_path(mod: str) -> pathlib.Path | None:
    cand = BACKEND / (mod.replace(".", "/") + ".py")
    if cand.is_file():
        return cand
    pkg = BACKEND / mod.replace(".", "/") / "__init__.py"
    return pkg if pkg.is_file() else None


def population(log: Any) -> list[str]:
    """app.py에서 include_router된 라우터 모듈명을 기계로 도출한다."""
    src = (BACKEND / "app.py").read_text(encoding="utf-8")
    alias_to_module: dict[str, str] = {}
    for m in re.finditer(r"from whymath_backend\.api\.(\w+) import router as (\w+)", src):
        alias_to_module[m.group(2)] = m.group(1)
    # auth는 별칭 패턴이 다르다(`from ..auth import (` 블록) — include는 auth_router로 실측됨
    included = re.findall(r"app\.include_router\((\w+)\)", src)
    features: list[str] = []
    for alias in included:
        mod = alias_to_module.get(alias)
        if mod is None:
            base = alias.removesuffix("_router")
            if (BACKEND / "api" / f"{base}.py").is_file():
                mod = base
            else:
                log(f"[population][error] include_router({alias}) 대응 모듈 미해석")
                continue
        features.append(mod)
    log(f"[population] include_router {len(included)}건 → 라우터 기능 {len(features)}건 + app-core")
    return features


@dataclass
class Feature:
    feature_id: str
    name: str
    location: str
    endpoints: int
    write_endpoints: int
    adapter_deps: list[str]
    mixed_deps: list[str]
    db_model_modules: list[str]
    internal_imports: int
    test_files: int
    test_functions: int
    scores: dict[str, int] = field(default_factory=dict)
    total: int = 0
    migration_action: str = ""
    meta: dict[str, str] = field(default_factory=dict)


def _score(feature: Feature) -> None:
    def band(value: int, cuts: tuple[int, int, int]) -> int:
        return 0 if value <= cuts[0] else 1 if value <= cuts[1] else 2 if value <= cuts[2] else 3

    # A 과목결합도: ADAPTER 2+ = 3 · ADAPTER 1 = 2(+MIXED 있으면 3) · MIXED만 = 1 · 없음 = 0
    if len(feature.adapter_deps) >= 2:
        a = 3
    elif len(feature.adapter_deps) == 1:
        a = 3 if feature.mixed_deps else 2
    else:
        a = 1 if feature.mixed_deps else 0
    feature.scores = {
        "A_subject": a,
        "B_db": band(len(feature.db_model_modules), B_DBMODEL),
        "C_coupling": band(feature.internal_imports, C_IMPORTS),
        "D_tests": (
            0
            if feature.test_functions >= D_TESTFN[0]
            else (
                1
                if feature.test_functions >= D_TESTFN[1]
                else 2 if feature.test_functions >= D_TESTFN[2] else 3
            )
        ),
        "E_state": band(feature.write_endpoints, E_WRITES),
        "F_data": band(len(feature.db_model_modules), F_TABLES),
    }
    feature.total = sum(feature.scores.values())
    for upper, verdict in BANDS:
        if feature.total <= upper:
            feature.migration_action = verdict
            break


def measure(classify: Any, log: Any) -> list[Feature]:
    features: list[Feature] = []
    routers = population(log)
    for name in ["app-core", *routers]:
        if name == "app-core":
            path = BACKEND / "app.py"
            src = path.read_text(encoding="utf-8")
            eps = re.findall(r"@app\.(get|post|put|patch|delete)\(", src)
            test_glob = sorted(TESTS_API.glob("test_app*.py")) + sorted(
                (REPO / "tests" / "backend").glob("test_app*.py")
            )
        else:
            path = BACKEND / "api" / f"{name}.py"
            src = path.read_text(encoding="utf-8")
            eps = re.findall(r"@router\.(get|post|put|patch|delete)\(", src)
            test_glob = sorted(TESTS_API.glob(f"test_{name}*.py"))

        direct = _internal_imports(path)
        closure = {f"api.{name}" if name != "app-core" else "app", *direct}
        adapter, mixed, dbmods = [], [], set()
        for mod in sorted(closure):
            verdict, _, _ = classify(mod)
            if verdict == "ADAPTER":
                adapter.append(mod)
            elif verdict == "MIXED":
                mixed.append(mod)
            if mod.startswith("db.models."):
                dbmods.add(mod)
        test_functions = sum(
            len(re.findall(r"(?m)^\s*(?:async )?def test_", p.read_text(encoding="utf-8")))
            for p in test_glob
        )
        feature = Feature(
            feature_id=f"WM-API-{name.upper().replace('_', '-')}",
            name=name,
            location=str(path.relative_to(REPO)),
            endpoints=len(eps),
            write_endpoints=sum(1 for e in eps if e != "get"),
            adapter_deps=adapter,
            mixed_deps=mixed,
            db_model_modules=sorted(dbmods),
            internal_imports=len(set(direct)),
            test_files=len(test_glob),
            test_functions=test_functions,
            meta=FEATURE_META.get(
                name, dict(user="?", domain="?", relevance="unclassified", seat="메타 미등재")
            ),
        )
        _score(feature)
        features.append(feature)
        log(
            f"[measure] {feature.feature_id}: ep={feature.endpoints} "
            f"score={feature.total} → {feature.migration_action}"
        )
    return features


def dashboard(features: list[Feature]) -> dict[str, Any]:
    unclassified = [f.name for f in features if f.meta["relevance"] == "unclassified"]
    return {
        "population": len(features),
        "classified": len(features) - len(unclassified),
        "classification_rate": f"{len(features) - len(unclassified)}/{len(features)}",
        "unclassified": unclassified,
        "release_relevant_proposed": sum(
            1
            for f in features
            if f.meta["relevance"] in ("verification-loop", "platform-invariant")
        ),
        "deferred_proposed": sum(
            1 for f in features if f.meta["relevance"] == "deferred-candidate"
        ),
        "migration_actions": {
            verdict: sum(1 for f in features if f.migration_action == verdict)
            for _, verdict in BANDS
        },
    }


def to_yaml(features: list[Feature], dash: dict[str, Any]) -> str:
    """PyYAML 없이 결정론 직렬화 — 장부는 diff 가능해야 한다(키 순서 고정)."""
    lines = [
        "# EOS 기능 인벤토리 + Migration Difficulty Matrix — 기계 생성 장부 (EOS-68)",
        "# 재생성: python3 scripts/analysis/eos_feature_inventory.py --write",
        "# 손편집 금지 — 점수 임계·메타는 생성기(정본)에 있다. 여기 고치면 다음 생성이 덮는다.",
        "# release_relevance는 *제안*이다 — 확정은 Kiki(#916 트리아지 프로토콜과 통합 판정).",
        "schema_version: 1",
        "dashboard:",
        f"  population: {dash['population']}",
        f"  classification_rate: {dash['classification_rate']}",
        f"  release_relevant_proposed: {dash['release_relevant_proposed']}",
        f"  deferred_proposed: {dash['deferred_proposed']}",
        "  migration_actions:",
    ]
    lines += [f"    {k}: {v}" for k, v in dash["migration_actions"].items()]
    lines.append("features:")
    for f in features:
        lines += [
            f"  - feature_id: {f.feature_id}",
            f"    location: {f.location}",
            f"    user: {f.meta['user']}",
            f"    domain: {f.meta['domain']}",
            "    status: Production",
            f"    endpoints: {f.endpoints}",
            f"    write_endpoints: {f.write_endpoints}",
            f"    eos_ownership: {'Core+Adapter' if f.adapter_deps else 'Core'}",
            f"    adapter_deps: [{', '.join(f.adapter_deps)}]",
            f"    mixed_deps: [{', '.join(f.mixed_deps)}]",
            f"    db_model_modules: {len(f.db_model_modules)}",
            f"    internal_imports: {f.internal_imports}",
            f"    test_files: {f.test_files}",
            f"    test_functions: {f.test_functions}",
            "    matrix:",
        ]
        lines += [f"      {axis}: {score}" for axis, score in f.scores.items()]
        lines += [
            f"    matrix_total: {f.total}",
            f"    migration_action: {f.migration_action}",
            f"    release_relevance: {f.meta['relevance']}",
            f"    seat: \"{f.meta['seat']}\"",
        ]
    return "\n".join(lines) + "\n"


def to_markdown(features: list[Feature], dash: dict[str, Any]) -> str:
    lines = [
        "| 기능 | 사용자 | Domain | EP(쓰기) | Adapter 의존 | 테스트fn "
        "| A B C D E F | 계 | 판정 | 출시(제안) |",
        "|---|---|---|---|---|---:|---|---:|---|---|",
    ]
    for f in sorted(features, key=lambda x: -x.total):
        axis_keys = ("A_subject", "B_db", "C_coupling", "D_tests", "E_state", "F_data")
        axes = " ".join(str(f.scores[k]) for k in axis_keys)
        lines.append(
            f"| `{f.name}` | {f.meta['user']} | {f.meta['domain']} "
            f"| {f.endpoints}({f.write_endpoints}) "
            f"| {len(f.adapter_deps)}A/{len(f.mixed_deps)}M | {f.test_functions} | {axes} "
            f"| **{f.total}** | {f.migration_action} | {f.meta['relevance']} |"
        )
    lines += [
        "",
        f"**대시보드**: 모집단 {dash['population']} · 분류율 {dash['classification_rate']} · "
        f"검증 관여 제안(P0 상당) {dash['release_relevant_proposed']} · "
        f"이월 후보 {dash['deferred_proposed']} · "
        f"판정 분포 {dash['migration_actions']}",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="backlog/inventory/*.yaml 갱신")
    args = parser.parse_args(argv)

    def log(msg: str) -> None:
        print(msg, file=sys.stderr, flush=True)

    try:
        classify = _load_classify()
        features = measure(classify, log)
    except Exception as exc:  # noqa: BLE001 — 계측기 최상위: 원인 타입을 남기고 실패
        log(f"[fatal] 측정 실패 {type(exc).__name__}: {exc}")
        return 1
    if len(features) < 10:
        log(f"[fatal] 모집단 {len(features)}건 — app.py 파싱이 무너졌다(빈 장부 위장 금지)")
        return 1

    dash = dashboard(features)
    print(to_markdown(features, dash))
    if args.write:
        LEDGER.parent.mkdir(parents=True, exist_ok=True)
        LEDGER.write_text(to_yaml(features, dash), encoding="utf-8")
        log(f"[out] ledger → {LEDGER.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
