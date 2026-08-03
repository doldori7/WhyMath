"""[OPS-17] 클라 `X-App-Version` 상수 ↔ `pubspec.yaml` `version:` 드리프트 게이트.

왜 이 테스트가 있는가
--------------------
`src/mobile/lib/core/api_client.dart`가 서버 최소버전 계약 헤더(`X-App-Version`)에 싣는 값은
`Env.appVersion`(`src/mobile/lib/core/env.dart`)이라는 *손으로 유지보수하는* Dart 상수다.
Dart는 빌드타임에 `pubspec.yaml`을 읽을 수 없어(런타임 코드생성 파이프라인 신설은 과공학) 이
상수는 `pubspec.yaml`의 `version:`(빌드번호 `+N` 제외)과 **사람이 손으로** 동기화해야 한다.

손 동기화는 반드시 드리프트한다 — `pubspec.yaml`만 올리고 `env.dart`를 잊으면, 서버가 보내는
`X-App-Version`이 실제 빌드보다 낮게 신고되어 OPS-17 최소버전 게이트가 오판(멀쩡한 최신
빌드를 구버전으로 오인해 426 차단, 또는 그 반대)할 수 있다. 이 파일은 OPS-10/11의 "배선
실재성" 관용구(소스 오브 트루스를 직접 읽고 파싱 — 못 찾으면 조용한 skip이 아니라
`AssertionError`)를 그대로 답습해 그 드리프트를 CI에서 기계로 잡는다.

검증 계약
--------
① `pubspec.yaml`의 `version:`(빌드번호 제거)과 `env.dart`의 `appVersion` 상수가 일치한다
② 빌드번호(`+N`) 제거가 실제로 동작한다(파싱 정확성)
③ 파서가 위장하지 않는다 — 파일/필드를 못 찾으면 "위반 0 통과"가 아니라 **실패**
④ 변별력 — 실제로 다른 버전 문자열을 넣으면 실제로 다른 값이 나온다(자동화된 반증)
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_PUBSPEC_PATH = _REPO_ROOT / "src" / "mobile" / "pubspec.yaml"
_ENV_DART_PATH = _REPO_ROOT / "src" / "mobile" / "lib" / "core" / "env.dart"

_VERSION_LINE_RE = re.compile(r"(?m)^version:\s*(\S+)\s*$")
_APP_VERSION_CONST_RE = re.compile(r"appVersion\s*=\s*['\"]([^'\"]+)['\"]")


def _read_pubspec_version(path: Path = _PUBSPEC_PATH) -> str:
    """`pubspec.yaml`의 `version:`을 읽어 빌드번호(`+N`)를 제거한 `X.Y.Z`를 돌려준다.

    파일/필드를 못 찾으면 조용히 넘어가지 않고 `AssertionError`로 실패한다(위장 차단 —
    `test_infra_lint_wiring.py::_job_run_scripts` 선례와 동형).
    """
    if not path.is_file():
        raise AssertionError(f"{path} 이(가) 없다 — pubspec 버전을 확인할 수 없다.")
    text = path.read_text(encoding="utf-8")
    match = _VERSION_LINE_RE.search(text)
    if match is None:
        raise AssertionError(f"{path}에서 `version:` 필드를 찾을 수 없다.")
    raw = match.group(1)
    return raw.split("+", 1)[0]  # 빌드번호(+N) 제거 — 예: "0.1.0+1" → "0.1.0"


def _read_env_dart_app_version(path: Path = _ENV_DART_PATH) -> str:
    """`env.dart`의 `appVersion` 상수 값을 읽는다.

    파일/상수를 못 찾으면 `AssertionError`로 실패한다(위장 차단).
    """
    if not path.is_file():
        raise AssertionError(f"{path} 이(가) 없다 — env.dart appVersion을 확인할 수 없다.")
    text = path.read_text(encoding="utf-8")
    match = _APP_VERSION_CONST_RE.search(text)
    if match is None:
        raise AssertionError(f"{path}에서 `appVersion` 상수를 찾을 수 없다.")
    return match.group(1)


def test_app_version_matches_pubspec_version() -> None:
    """계약 ① — 실 저장소의 두 소스가 일치한다(드리프트 0)."""
    pubspec_version = _read_pubspec_version()
    env_version = _read_env_dart_app_version()
    assert env_version == pubspec_version, (
        f"env.dart appVersion({env_version!r})과 pubspec.yaml version({pubspec_version!r})이 "
        "드리프트했다 — OPS-17 X-App-Version 계약이 실제 빌드 버전과 어긋난다. "
        "pubspec.yaml의 version:을 올렸다면 env.dart의 appVersion도 함께 올려라."
    )


def test_pubspec_version_strips_build_number(tmp_path: Path) -> None:
    """계약 ② — `+N` 빌드번호가 실제로 제거된다."""
    fake_pubspec = tmp_path / "pubspec.yaml"
    fake_pubspec.write_text("name: x\nversion: 1.2.3+45\n", encoding="utf-8")
    assert _read_pubspec_version(fake_pubspec) == "1.2.3"


def test_parser_fails_loudly_when_pubspec_missing(tmp_path: Path) -> None:
    """계약 ③ — pubspec 자체가 없으면 조용한 통과가 아니라 예외."""
    missing = tmp_path / "does_not_exist.yaml"
    with pytest.raises(AssertionError, match="없다"):
        _read_pubspec_version(missing)


def test_parser_fails_loudly_when_env_dart_missing(tmp_path: Path) -> None:
    """계약 ③ — env.dart 자체가 없으면 조용한 통과가 아니라 예외."""
    missing = tmp_path / "does_not_exist.dart"
    with pytest.raises(AssertionError, match="없다"):
        _read_env_dart_app_version(missing)


def test_parser_fails_loudly_when_version_field_missing(tmp_path: Path) -> None:
    """계약 ③ — `version:` 필드가 없는 pubspec은 예외(빈 문자열로 위장 통과 금지)."""
    fake_pubspec = tmp_path / "pubspec.yaml"
    fake_pubspec.write_text("name: x\n", encoding="utf-8")
    with pytest.raises(AssertionError, match="찾을 수 없다"):
        _read_pubspec_version(fake_pubspec)


def test_parser_fails_loudly_when_app_version_const_missing(tmp_path: Path) -> None:
    """계약 ③ — `appVersion` 상수가 없는 env.dart는 예외."""
    fake_env = tmp_path / "env.dart"
    fake_env.write_text("class Env {}\n", encoding="utf-8")
    with pytest.raises(AssertionError, match="찾을 수 없다"):
        _read_env_dart_app_version(fake_env)


def test_drift_is_actually_detected(tmp_path: Path) -> None:
    """계약 ④(변별력) — 실제로 버전이 어긋난 두 파일은 실제로 다른 값을 낸다.

    (수동으로 pubspec 버전을 바꿔보고 이 테스트가 fail하는지 확인하는 절차의 자동화 대응 —
    fixture 파일로 드리프트 상태를 재현해 파서 자체의 변별력을 CI에서 상시 검증한다.)
    """
    fake_pubspec = tmp_path / "pubspec.yaml"
    fake_pubspec.write_text("name: x\nversion: 9.9.9+1\n", encoding="utf-8")
    fake_env = tmp_path / "env.dart"
    fake_env.write_text(
        "class Env { static const String appVersion = '0.1.0'; }\n", encoding="utf-8"
    )
    assert _read_pubspec_version(fake_pubspec) != _read_env_dart_app_version(fake_env)
