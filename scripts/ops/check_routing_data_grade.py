#!/usr/bin/env python3
"""데이터 등급 라우팅 신호 소스 스캔 게이트 — `RoutingRequest`가 등급을 *명시*하는지 (EOS-59 ③).

왜 스캐너가 필요한가 — 보수 기본값만으로는 부족하다
--------------------------------------------------
`RoutingRequest.data_licenses`의 기본값은 `LicenseType.UNKNOWN`(미확인)이고, 데이터 등급
게이트는 미확인을 fail-closed로 차단한다. 그것만 두면 **등급을 아무도 안 채워도 아무 일도
일어나지 않는다** — 대신 프로덕션 전 호출부가 조용히 LOCAL로 강등돼 클라우드가 사실상 꺼진다.
그 상태는 "안전"이 아니라 *측정 불가*다: 게이트가 일해서 로컬인지, 아무도 등급을 안 적어서
로컬인지 구분할 수 없다(CLAUDE.md "0건 통과"와 "측정 실패"는 절대 같은 색이면 안 된다).

그래서 이 게이트는 **호출부가 등급을 명시했는지**를 소스에서 직접 검사한다. 그러면 보수
기본값은 *일상 동작*이 아니라 **명시를 잊었을 때만 작동하는 사고 방지용 backstop**으로 남는다.

판정 규칙
--------
`RoutingRequest(...)` 생성 호출에 `data_licenses=` 키워드가 있어야 한다. 없으면 위반이다.
`**kwargs` 언패킹만 있고 `data_licenses=`가 없는 호출도 **위반으로 본다** — 정적으로 등급이
실렸는지 증명할 수 없기 때문이다(법적 축은 모르면 막는다).

검사 대상 = **프로덕션 소스**(`src/backend/whymath_backend`·`scripts`)뿐이다. 테스트는 일부러
제외한다 — 보수 기본값의 *동작 자체*를 검증하려면 등급을 안 준 요청을 만들 수 있어야 하고,
테스트까지 강제하면 그 검증이 불가능해진다(게이트가 자기 변별력 테스트를 막는 자가당착).

자가 변별력 (이 스캐너가 조용히 통과하지 않는가)
----------------------------------------------
`RoutingRequest(` 생성 호출을 **한 건도 못 찾으면 exit 1**로 실패한다. 경로 오타·리팩터로
스캔이 헛돌면 "위반 0건 통과"처럼 보이는데, 그건 통과가 아니라 측정 실패다(OPS-08
`test_required_checks_doc`의 마커 부재 처리와 동형).

정직한 공백 (검사하지 않는 것)
-----------------------------
- `RoutingRequest.model_validate(...)`·`model_copy(update=...)`로 *만들어지는* 요청.
  2026-09-01 실측으로 프로덕션에는 그런 경로가 0건이라 지금은 사각이 아니다. 생기면 이
  스캐너를 확장해야 한다(이 문단이 그 조건의 기록이다).
- 등급 *값이 맞는지*는 판정하지 않는다 — "AIHub 자료를 다루면서 자체 저작이라고 적었다"는
  거짓 선언은 소스만 봐서 알 수 없다. 그 축은 사람의 판단이며, 호출부 주석에 근거를 남기는
  것으로 대신한다(코드 리뷰 대상).

사용:  python3 scripts/ops/check_routing_data_grade.py [경로...]
종료:  0 통과 / 1 위반 또는 측정 실패
"""

from __future__ import annotations

import ast
import pathlib
import sys

# 저장소 루트를 `__file__` 기준으로 자가 탐지 — CI가 `src/backend`를 working-directory로
# 쓰므로 cwd에 의존하면 안 된다(`ops.provenance_audit`의 자가 탐지 관례 동형).
_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]

DEFAULT_TARGETS: tuple[pathlib.Path, ...] = (
    _REPO_ROOT / "src" / "backend" / "whymath_backend",
    _REPO_ROOT / "scripts",
)

TARGET_CALL = "RoutingRequest"
REQUIRED_KEYWORD = "data_licenses"


def _is_routing_request_call(node: ast.Call) -> bool:
    """`RoutingRequest(...)` 또는 `모듈.RoutingRequest(...)` 생성 호출인가."""
    func = node.func
    if isinstance(func, ast.Name):
        return func.id == TARGET_CALL
    if isinstance(func, ast.Attribute):
        return func.attr == TARGET_CALL
    return False


def _has_star_kwargs(node: ast.Call) -> bool:
    """`**kwargs` 언패킹이 있는가 — 있으면 등급 실림을 정적으로 증명할 수 없다."""
    return any(keyword.arg is None for keyword in node.keywords)


def scan_file(path: pathlib.Path) -> tuple[int, list[str]]:
    """한 파일을 스캔해 (생성 호출 수, 위반 메시지 목록)을 돌려준다.

    구문 오류는 삼키지 않는다 — 파싱 못 한 파일을 "위반 0"으로 넘기면 그 파일만 검사 밖으로
    빠져나간다(침묵 실패 금지). 예외 타입명과 함께 위반으로 계상한다.
    """
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (SyntaxError, UnicodeDecodeError) as exc:
        return 0, [f"{path}: 파싱 실패({type(exc).__name__}) — 검사 불가이므로 위반으로 계상"]

    found = 0
    issues: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not _is_routing_request_call(node):
            continue
        found += 1
        names = {keyword.arg for keyword in node.keywords}
        if REQUIRED_KEYWORD in names:
            continue
        detail = (
            "**kwargs만 있고 등급 키워드가 없다(정적 증명 불가)"
            if _has_star_kwargs(node)
            else f"`{REQUIRED_KEYWORD}=` 키워드 없음"
        )
        issues.append(
            f"{path}:{node.lineno}: RoutingRequest 생성에 데이터 등급 미명시 — {detail}. "
            "이 호출의 프롬프트에 실리는 자료의 라이선스를 선언하라 "
            "(`l3.data_grade_defaults`의 프로파일 또는 명시적 LicenseType 튜플)."
        )
    return found, issues


def iter_python_files(targets: list[pathlib.Path]) -> list[pathlib.Path]:
    """대상 경로(파일 또는 디렉터리) → `.py` 파일 목록. 캐시·가상환경은 제외."""
    files: list[pathlib.Path] = []
    for target in targets:
        if target.is_file() and target.suffix == ".py":
            files.append(target)
            continue
        if not target.is_dir():
            continue
        for path in sorted(target.rglob("*.py")):
            parts = set(path.parts)
            if parts & {"__pycache__", ".venv", "venv", "node_modules", "build", "dist"}:
                continue
            files.append(path)
    return files


def main(argv: list[str]) -> int:
    targets = [pathlib.Path(a) for a in argv[1:]] or list(DEFAULT_TARGETS)
    files = iter_python_files(targets)
    if not files:
        print(f"[측정 실패] 검사할 .py 파일이 없다 — 대상: {[str(t) for t in targets]}")
        return 1

    total_calls = 0
    all_issues: list[str] = []
    for path in files:
        found, issues = scan_file(path)
        total_calls += found
        all_issues.extend(issues)

    if total_calls == 0:
        # 위반 0이지만 통과가 아니다 — 스캐너가 아무것도 못 봤다는 뜻이다.
        print(
            f"[측정 실패] {TARGET_CALL}( 생성 호출을 한 건도 찾지 못했다 "
            f"(파일 {len(files)}건 스캔). 경로·리팩터를 확인하라 — "
            "'위반 0 통과'와 '측정 실패'를 같은 색으로 두지 않는다."
        )
        return 1

    for message in all_issues:
        print(f"[FAIL] {message}")

    print(
        f"\n파일 {len(files)}건 / {TARGET_CALL} 생성 호출 {total_calls}건 / "
        f"등급 미명시 {len(all_issues)}건"
    )
    return 1 if all_issues else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
