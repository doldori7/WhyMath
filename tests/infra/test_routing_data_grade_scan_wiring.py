"""데이터 등급 소스 스캔 게이트의 **배선 실재 + 변별력** 동결 (EOS-59 ③).

이 저장소는 "만들었는데 안 도는 것"에 반복해서 뚫렸다(`tests/infra` 199건 미실행·브랜치
보호 required check 미강제·infra lint 잡 부재). 그래서 게이트를 하나 세울 때마다 **그것이
CI에서 실제로 실행되는지**를 기계가 대조한다(OPS-10 선례).

여기서 막는 것은 세 가지다.

① **미배선** — 스캐너가 저장소에 있는데 어떤 CI 잡도 부르지 않는 것("존재함"≠"돌아감").
② **무변별** — 스캐너가 위반을 주입해도 통과하는 것. 검사기가 성공/실패 양쪽에서 같은 값을
   내면 그것은 검증이 아니라 위장이다(CLAUDE.md "변별력 없는 검증 스텝 금지").
③ **측정 실패의 위장** — 스캔이 아무것도 못 봤는데 "위반 0 통과"로 보이는 것.

양성 대조를 함께 둬 무차별 실패가 아님을 보인다(정상 트리는 exit 0).
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

_REPO_ROOT = Path(__file__).resolve().parents[2]
_CI_WORKFLOW = _REPO_ROOT / ".github" / "workflows" / "ci.yml"
_SCANNER = _REPO_ROOT / "scripts" / "ops" / "check_routing_data_grade.py"

_CLEAN_CALL = """from whymath_backend.l3.models import RoutingRequest

REQ = RoutingRequest(
    task_type="explain",
    difficulty="easy",
    requires_reasoning=False,
    student_subscription="free",
    data_licenses=("INTERNAL_OWNED",),
)
"""

_VIOLATING_CALL = """from whymath_backend.l3.models import RoutingRequest

REQ = RoutingRequest(
    task_type="explain",
    difficulty="easy",
    requires_reasoning=False,
    student_subscription="free",
)
"""

_STAR_KWARGS_CALL = """from whymath_backend.l3.models import RoutingRequest

def build(**kwargs: object) -> RoutingRequest:
    return RoutingRequest(**kwargs)
"""


def _run_scanner(*targets: Path) -> subprocess.CompletedProcess[str]:
    """스캐너를 서브프로세스로 돌린다 — CI가 부르는 방식 그대로(exit code로 판정).

    타임아웃을 건다(외부 프로세스 호출에는 전부 타임아웃 — CLAUDE.md 2026-08-22).
    """
    return subprocess.run(
        [sys.executable, str(_SCANNER), *(str(t) for t in targets)],
        capture_output=True,
        text=True,
        timeout=120,
    )


# ──────────────────────────────────────────────────────────────────────
# ① 배선 실재 — CI가 실제로 부르는가
# ──────────────────────────────────────────────────────────────────────
def test_scanner_exists_at_the_path_ci_references() -> None:
    assert _SCANNER.is_file(), f"스캐너 부재: {_SCANNER}"


def test_ci_backend_job_runs_the_scanner() -> None:
    """`backend` 잡이 스캐너를 부르는지 — 워크플로를 파싱해 스텝 단위로 확인한다."""
    workflow = yaml.safe_load(_CI_WORKFLOW.read_text(encoding="utf-8"))
    backend_steps = workflow["jobs"]["backend"]["steps"]
    runs = [str(step.get("run", "")) for step in backend_steps]
    matched = [cmd for cmd in runs if "check_routing_data_grade.py" in cmd]
    assert matched, (
        "ci.yml `backend` 잡에 check_routing_data_grade.py 실행 스텝이 없다 — "
        "게이트가 저장소에만 있고 돌지 않는다"
    )


def test_ci_step_is_blocking_not_advisory() -> None:
    """비차단(continue-on-error·|| true)으로 붙으면 게이트가 아니라 경고 수집기가 된다."""
    workflow = yaml.safe_load(_CI_WORKFLOW.read_text(encoding="utf-8"))
    backend_steps = workflow["jobs"]["backend"]["steps"]
    step = next(
        s for s in backend_steps if "check_routing_data_grade.py" in str(s.get("run", ""))
    )
    assert not step.get("continue-on-error"), "게이트 스텝이 continue-on-error로 붙어 있다"
    assert not re.search(r"\|\|\s*true|;\s*true", str(step["run"])), (
        "게이트 호출의 exit code를 `|| true`가 삼키고 있다"
    )


# ──────────────────────────────────────────────────────────────────────
# ② 변별력 — 결함을 주입하면 실제로 실패하는가 (+ 양성 대조)
# ──────────────────────────────────────────────────────────────────────
def test_clean_tree_passes(tmp_path: Path) -> None:
    """양성 대조 — 등급을 명시한 호출만 있으면 exit 0."""
    (tmp_path / "clean.py").write_text(_CLEAN_CALL, encoding="utf-8")
    result = _run_scanner(tmp_path)
    assert result.returncode == 0, f"정상 트리인데 실패했다:\n{result.stdout}\n{result.stderr}"


def test_missing_grade_keyword_is_detected(tmp_path: Path) -> None:
    """결함 주입 ① — `data_licenses=` 없는 생성 호출 → exit 1."""
    (tmp_path / "violating.py").write_text(_VIOLATING_CALL, encoding="utf-8")
    result = _run_scanner(tmp_path)
    assert result.returncode == 1, f"위반을 못 잡았다:\n{result.stdout}"
    assert "data_licenses" in result.stdout


def test_star_kwargs_without_explicit_grade_is_detected(tmp_path: Path) -> None:
    """결함 주입 ② — `**kwargs` 언패킹은 등급 실림을 정적으로 증명할 수 없다 → 위반."""
    (tmp_path / "star.py").write_text(_STAR_KWARGS_CALL, encoding="utf-8")
    result = _run_scanner(tmp_path)
    assert result.returncode == 1, f"**kwargs 우회를 못 잡았다:\n{result.stdout}"


def test_unparseable_file_is_counted_as_a_violation_not_skipped(tmp_path: Path) -> None:
    """결함 주입 ③ — 파싱 실패를 조용히 넘기면 그 파일만 검사 밖으로 빠진다(침묵 실패)."""
    (tmp_path / "clean.py").write_text(_CLEAN_CALL, encoding="utf-8")
    (tmp_path / "broken.py").write_text("def f(:\n", encoding="utf-8")
    result = _run_scanner(tmp_path)
    assert result.returncode == 1
    assert "파싱 실패" in result.stdout


# ──────────────────────────────────────────────────────────────────────
# ③ 측정 실패의 위장 — 아무것도 못 봤을 때 통과처럼 보이지 않는가
# ──────────────────────────────────────────────────────────────────────
def test_zero_calls_found_is_a_measurement_failure_not_a_pass(tmp_path: Path) -> None:
    """`RoutingRequest(` 호출이 0건이면 exit 1 — '위반 0 통과'와 '측정 실패'는 다른 색이다."""
    (tmp_path / "unrelated.py").write_text("X = 1\n", encoding="utf-8")
    result = _run_scanner(tmp_path)
    assert result.returncode == 1, f"측정 실패가 통과로 위장됐다:\n{result.stdout}"
    assert "측정 실패" in result.stdout


def test_empty_target_is_a_measurement_failure(tmp_path: Path) -> None:
    result = _run_scanner(tmp_path / "does-not-exist")
    assert result.returncode == 1
    assert "측정 실패" in result.stdout


# ──────────────────────────────────────────────────────────────────────
# 현행 저장소 — 게이트가 지금 실제로 통과하는가
# ──────────────────────────────────────────────────────────────────────
def test_repository_passes_the_gate_today() -> None:
    """프로덕션 호출부 전건이 등급을 명시한 상태를 동결한다(새 호출부가 생기면 여기서 적색)."""
    result = _run_scanner()
    assert result.returncode == 0, f"저장소가 게이트를 통과하지 못한다:\n{result.stdout}"
    match = re.search(r"RoutingRequest 생성 호출 (\d+)건", result.stdout)
    assert match is not None, f"스캔 요약을 읽지 못했다:\n{result.stdout}"
    assert int(match.group(1)) > 0, "생성 호출 0건 — 스캐너가 실물을 못 봤다"


@pytest.mark.parametrize("marker", ["data_licenses", "RoutingRequest"])
def test_scanner_targets_are_not_silently_empty(marker: str) -> None:
    """스캐너 소스가 검사 대상 상수를 실제로 들고 있는지 — 리팩터로 이름이 바뀌면 알려준다."""
    body = _SCANNER.read_text(encoding="utf-8")
    assert marker in body
