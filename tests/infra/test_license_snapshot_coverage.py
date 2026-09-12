"""라이선스 스냅샷 커버리지 판정기 계약 — 게이트 clear 기준의 기계 동결 (LIC-02 집행 축).

이 테스트가 지키는 것 (PR #915 리뷰 P1 수용 — 2026-08-30)
---------------------------------------------------------
게이트 `G-license-snapshot-blocked-sources`의 clear 기준은 "부분 성공"을 통과시키면 안 된다.
아카이버 exit 3(부분)과 "스냅샷 디렉터리 개수 증가"는 **20곳 중 1곳만 받아도 성립**하므로,
그 둘을 성공 기준으로 쓰면 13곳이 영구 미확보인 상태가 통과한다 — 대상이 소급 불가 자산이라
그 오판은 되돌릴 수 없다. 그래서 판정을 `license_snapshot_coverage.py`의 exit code로 옮겼고,
여기서 그 판정의 **변별력**을 동결한다:

① 전곳 확보 → exit 0 (양성 대조 — 무차별 실패가 아님)
② 1곳이라도 미확보 → exit 1 + 미확보 id 전건 출력 (부분 성공이 통과하지 않는다)
③ 감사로그가 성공이라 해도 **파일이 없으면** 미확보 (로그만 믿지 않는다)
④ 판정 불가(감사로그 부재·깨진 JSON)는 "0건 통과"가 아니라 exit 2 (침묵 실패 금지)
⑤ 현재 저장소 실상태에서 판정기가 실제로 돈다 (합성 입력에서만 도는 테스트 금지)
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT = _REPO_ROOT / "scripts" / "ops" / "license_snapshot_coverage.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("_license_coverage", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _fake_archive(root: Path, *, logged: list[str], with_files: list[str]) -> Path:
    """감사로그와 스냅샷 파일을 독립적으로 심는 합성 아카이브."""
    archive = root / "licenses"
    (archive / "snapshots").mkdir(parents=True)
    lines = [
        json.dumps({"event": "new", "source_id": sid, "ts": "2026-08-30T00:00:00Z"})
        for sid in logged
    ]
    (archive / "audit_log.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    for sid in with_files:
        d = archive / "snapshots" / sid
        d.mkdir(parents=True, exist_ok=True)
        (d / "abc123.meta.json").write_text("{}", encoding="utf-8")
    return archive


def _all_source_ids() -> list[str]:
    module = _load_module()
    return [s.source_id for s in module._load_archiver().TIER1_SOURCES]


def _run(archive_dir: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(_SCRIPT), "--archive-dir", str(archive_dir)],
        capture_output=True,
        text=True,
        timeout=60,
    )


class TestCoverageVerdict:
    def test_all_captured_exits_zero(self, tmp_path: Path) -> None:
        """① 전곳 확보 → exit 0 (양성 대조)."""
        ids = _all_source_ids()
        archive = _fake_archive(tmp_path, logged=ids, with_files=ids)
        result = _run(archive)
        assert result.returncode == 0, result.stdout + result.stderr
        assert f"{len(ids)}/{len(ids)}" in result.stdout

    def test_one_missing_source_fails(self, tmp_path: Path) -> None:
        """② 딱 1곳 빠져도 exit 1 — 부분 성공은 통과가 아니다(리뷰 P1의 핵심)."""
        ids = _all_source_ids()
        archive = _fake_archive(tmp_path, logged=ids[:-1], with_files=ids[:-1])
        result = _run(archive)
        assert result.returncode == 1
        assert ids[-1] in result.stdout

    def test_partial_capture_does_not_pass(self, tmp_path: Path) -> None:
        """② 변형 — '1곳만 새로 받은' 실제 시나리오가 통과하지 않는지 직접 확인."""
        ids = _all_source_ids()
        only_one = ids[:1]
        result = _run(_fake_archive(tmp_path, logged=only_one, with_files=only_one))
        assert result.returncode == 1
        # 미확보 전건이 보여야 다음 실행 대상을 알 수 있다
        for sid in ids[1:]:
            assert sid in result.stdout

    def test_logged_but_file_missing_is_not_captured(self, tmp_path: Path) -> None:
        """③ 로그는 성공인데 파일이 없으면 미확보 — 삭제·미커밋 상태를 놓치지 않는다."""
        ids = _all_source_ids()
        archive = _fake_archive(tmp_path, logged=ids, with_files=ids[:-1])
        result = _run(archive)
        assert result.returncode == 1
        assert ids[-1] in result.stdout


class TestVerdictFailsLoudly:
    def test_missing_audit_log_exits_two(self, tmp_path: Path) -> None:
        """④ 감사로그 부재 = 판정 불가 → exit 2 (통과 아님)."""
        empty = tmp_path / "licenses"
        empty.mkdir()
        result = _run(empty)
        assert result.returncode == 2
        assert "판정 불가" in result.stderr

    def test_corrupt_audit_log_exits_two(self, tmp_path: Path) -> None:
        """④ 깨진 JSON도 조용히 건너뛰지 않는다 — 예외 타입명 동반 exit 2."""
        archive = _fake_archive(tmp_path, logged=["ncic"], with_files=["ncic"])
        with (archive / "audit_log.jsonl").open("a", encoding="utf-8") as fh:
            fh.write("{ 이건 JSON이 아니다\n")
        result = _run(archive)
        assert result.returncode == 2
        assert "JSONDecodeError" in result.stderr


class TestRunsAgainstRealRepo:
    def test_current_repo_state_is_judged(self) -> None:
        """⑤ 실제 저장소에서 판정기가 돈다 — 합성 입력에서만 도는 테스트 금지.

        현시점 실상태는 부분 확보(6/20)라 exit 1이 정답이다. 전곳 확보가 되면 0이 되며,
        그 전환 자체가 게이트 clear 신호다. 어느 쪽이든 **2(판정 불가)는 아니어야** 한다.
        """
        result = _run(_REPO_ROOT / "data" / "licenses")
        assert result.returncode in (0, 1), f"판정 불가(2): {result.stderr}"
        assert "커버리지" in result.stdout


@pytest.mark.parametrize("flag", ["--help"])
def test_help_does_not_crash(flag: str) -> None:
    result = subprocess.run(
        [sys.executable, str(_SCRIPT), flag], capture_output=True, text=True, timeout=60
    )
    assert result.returncode == 0
