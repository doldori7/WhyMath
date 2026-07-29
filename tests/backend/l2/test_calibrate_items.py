"""L2 보정 배치 CLI — `calibrate_items` 단위테스트 (hermetic·monkeypatch).

slice 80: CLI 글루(`_run`: 세션 획득 → `calibrate_item_difficulties` → 엔진 정리 → 리포트)와
`main`(argparse + asyncio.run)을 DB 없이 검증한다. 보정 로직 자체는 slice 79
`test_item_calibration`·실 PG 통합테스트가 가드 — 여기선 진입점 배선(세션 수명·리포트)만 본다.
"""

from __future__ import annotations

from typing import Any

import pytest
from whymath_backend.l2 import calibrate_items


class _FakeSession:
    """async 컨텍스트 매니저 세션 스텁(calibrate가 페이크라 세션 내용은 무관)."""

    async def __aenter__(self) -> _FakeSession:
        return self

    async def __aexit__(self, *exc: object) -> bool:
        return False


class TestCli:
    def test_main_help_exits_zero(self) -> None:
        """--help → argparse가 SystemExit(0)."""
        with pytest.raises(SystemExit) as exc_info:
            calibrate_items.main(["--help"])
        assert exc_info.value.code == 0

    def test_main_runs_calibration_reports_and_disposes(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """main → 세션 1개로 보정 실행·보정 수 리포트·엔진 정리·종료 0."""
        disposed: dict[str, bool] = {}

        async def _fake_calibrate(session: Any) -> int:
            return 3

        async def _fake_dispose() -> None:
            disposed["yes"] = True

        # get_sessionmaker는 호출 시 async-CM 세션을 주는 팩토리(_FakeSession 클래스)를 반환.
        monkeypatch.setattr(calibrate_items, "get_sessionmaker", lambda settings=None: _FakeSession)
        monkeypatch.setattr(calibrate_items, "calibrate_item_difficulties", _fake_calibrate)
        monkeypatch.setattr(calibrate_items, "dispose_engine", _fake_dispose)

        assert calibrate_items.main([]) == 0
        assert disposed["yes"]  # 배치 종료 시 엔진 풀 정리
        assert "calibrated_items=3" in capsys.readouterr().out
