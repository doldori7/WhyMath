"""[FLOW-HEALTH 후속] 프록시 CA 경로가 **선택적**임을 저장소 전체에 동결한다.

사고 경위 (2026-09-01 main red)
--------------------------------
`/root/.ccr/ca-bundle.crt`는 **에이전트 프록시가 있는 실행 환경에만** 존재한다.
GitHub 러너에는 없고, 게다가 `runner` 유저는 `/root`(mode 700)를 **통과조차 할 수
없다**. 두 가지가 동시에 터졌다:

① `pr_delivery_audit.py`·`pr_merge_readiness.py`·`measure_merge_gate_latency.py`가
   `--cacert <경로>`를 **무조건** 넘겨 러너에서 `curl (77) error setting certificate
   file`. 이 셋은 CI 호출처가 0건이었기 때문에 **아무도 몰랐다** — 배선하는 순간
   드러났다("존재함"과 "돌아감"은 다르다의 정확한 실례).
② `flow_health.py`는 `if Path(_CA).exists()`로 가드했는데, **`Path.exists()`는
   EACCES를 삼키지 않는다** — `pathlib._IGNORED_ERRNOS`는
   `(ENOENT, ENOTDIR, EBADF, ELOOP)`뿐이다. 그래서 "없으면 건너뛴다"는 의도가
   "없으면 `PermissionError`로 죽는다"가 됐고 잡이 통째로 실패했다.

계약
----
① 저장소의 어떤 스크립트도 `--cacert`를 무조건 넘기지 않는다.
② 그 가드는 **권한 오류에서도** 살아남는다(존재 여부만이 아니라 접근 불가도).
③ CA를 못 쓰는 환경에서 curl 인자에 `--cacert`가 아예 들어가지 않는다.
"""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_CA_LITERAL = "/root/.ccr/ca-bundle.crt"

# 이 상수를 쓰는 스크립트 전부 — 새 파일이 생겨도 자동 포함된다(하드코딩 목록 아님).
_SCRIPTS = sorted(
    p
    for p in (_REPO_ROOT / "scripts").rglob("*.py")
    if _CA_LITERAL in p.read_text(encoding="utf-8")
)


def _load(path: Path):
    spec = importlib.util.spec_from_file_location(f"_ca_{path.stem}", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


class TestNoUnconditionalCacert:
    def test_scripts_using_the_ca_were_found(self):
        """스캔이 0건이면 아래 검사들이 공허하게 통과한다 — 위장 방지."""
        assert _SCRIPTS, "CA 상수를 쓰는 스크립트를 하나도 못 찾았다 — 스캔이 깨졌다"

    @pytest.mark.parametrize("path", _SCRIPTS, ids=lambda p: p.name)
    def test_cacert_is_never_passed_unconditionally(self, path: Path):
        src = path.read_text(encoding="utf-8")
        # `"--cacert", CA` 형태로 curl 인자 목록에 직접 박는 패턴을 금지한다.
        bad = re.search(r'"--cacert",\s*_?CA\b(?!_PATH)', src)
        assert (
            not bad
        ), f"{path.name}이 --cacert를 무조건 넘긴다 — CA 없는 환경에서 curl (77)이 난다"

    @pytest.mark.parametrize("path", _SCRIPTS, ids=lambda p: p.name)
    def test_guard_helper_exists(self, path: Path):
        assert "_ca_args" in path.read_text(encoding="utf-8"), f"{path.name}에 가드 헬퍼가 없다"


class TestGuardSurvivesPermissionError:
    """② 핵심 — 존재하지 않는 경우뿐 아니라 **접근 불가**에서도 살아야 한다."""

    @pytest.mark.parametrize("path", _SCRIPTS, ids=lambda p: p.name)
    def test_permission_error_yields_empty_args(self, path: Path, monkeypatch):
        mod = _load(path)
        monkeypatch.setattr(
            mod,
            "open",
            lambda *a, **k: (_ for _ in ()).throw(PermissionError(13, "Permission denied")),
            raising=False,
        )
        assert (
            mod._ca_args() == []
        ), "권한 오류에서 빈 목록을 내야 한다 — Path.exists()는 EACCES를 전파한다"

    @pytest.mark.parametrize("path", _SCRIPTS, ids=lambda p: p.name)
    def test_missing_file_yields_empty_args(self, path: Path, monkeypatch):
        mod = _load(path)
        monkeypatch.setattr(mod, "_CA_PATH", "/nonexistent/definitely/not/here.crt")
        assert mod._ca_args() == []

    @pytest.mark.parametrize("path", _SCRIPTS, ids=lambda p: p.name)
    def test_readable_file_yields_cacert_args(self, path: Path, monkeypatch, tmp_path):
        """변별력 — 실제로 읽히는 CA가 있으면 인자를 내야 한다."""
        ca = tmp_path / "ca.crt"
        ca.write_bytes(b"dummy")
        mod = _load(path)
        monkeypatch.setattr(mod, "_CA_PATH", str(ca))
        assert mod._ca_args() == ["--cacert", str(ca)]
