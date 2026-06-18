"""학습 증거 보존기한 파기 ops CLI(`privacy/retention_purge_cli.py`) — 단위(hermetic·러너 주입).

DB 없이 CLI *배선*만 검증한다: ① `--as-of` 파싱·미지정 시 오늘(UTC) ② 파기 행수 → `{as_of,
purged}` JSON stdout ③ 종료 코드 0(파기 0건도 정상). 실 DB 파기는 evidence_store 통합테스트가
검증한다(중복 0). 합성 `purge_fn`을 주입한다(asyncio.run 가능한 코루틴).
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime

import pytest

from whymath_backend.privacy import retention_purge_cli as cli


def _runner(count: int, *, seen: dict[str, date]):  # type: ignore[no-untyped-def]
    async def _purge(as_of: date) -> int:
        seen["as_of"] = as_of
        return count

    return _purge


class TestRetentionPurgeCli:
    def test_explicit_as_of_parsed_and_passed(self, capsys: pytest.CaptureFixture[str]) -> None:
        """--as-of YYYY-MM-DD → 그 날짜로 파기·JSON에 반영."""
        seen: dict[str, date] = {}
        code = cli.main(["--as-of", "2026-06-01"], purge_fn=_runner(7, seen=seen))
        assert code == 0
        assert seen["as_of"] == date(2026, 6, 1)
        out = json.loads(capsys.readouterr().out)
        assert out == {"as_of": "2026-06-01", "purged": 7}

    def test_default_as_of_is_today_utc(self, capsys: pytest.CaptureFixture[str]) -> None:
        """--as-of 미지정 → 오늘(UTC)로 파기."""
        seen: dict[str, date] = {}
        code = cli.main([], purge_fn=_runner(0, seen=seen))
        assert code == 0
        assert seen["as_of"] == datetime.now(UTC).date()
        # 파기 0건도 정상(만료분 없음)·종료 코드 0.
        out = json.loads(capsys.readouterr().out)
        assert out["purged"] == 0 and out["as_of"] == datetime.now(UTC).date().isoformat()

    def test_invalid_as_of_errors(self, capsys: pytest.CaptureFixture[str]) -> None:
        """잘못된 날짜 형식 → argparse 에러(SystemExit·비정상 종료)."""
        with pytest.raises(SystemExit):
            cli.main(["--as-of", "not-a-date"], purge_fn=_runner(0, seen={}))
