"""보존기한 파기 ops CLI(`privacy/retention_purge_cli.py`) — 단위(hermetic·러너 주입).

DB 없이 CLI *배선*만 검증한다: ① `--as-of` 파싱·미지정 시 오늘(UTC) ② 테이블별 파기 행수 →
`{as_of, purged{table:n}, total}` JSON stdout ③ 종료 코드 0(파기 0건도 정상). 실 DB 파기는
evidence_store·retention 통합테스트가 검증한다(중복 0). 합성 `purge_fn`(코루틴)을 주입한다.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime

import pytest

from whymath_backend.privacy import retention_purge_cli as cli


def _runner(counts: dict[str, int], *, seen: dict[str, date]):  # type: ignore[no-untyped-def]
    async def _purge(as_of: date) -> dict[str, int]:
        seen["as_of"] = as_of
        return counts

    return _purge


class TestRetentionPurgeCli:
    def test_explicit_as_of_and_per_table_counts(self, capsys: pytest.CaptureFixture[str]) -> None:
        """--as-of YYYY-MM-DD → 그 날짜로 파기·테이블별 행수+total JSON 반영."""
        seen: dict[str, date] = {}
        code = cli.main(
            ["--as-of", "2026-06-01"],
            purge_fn=_runner(
                {"evidence_links": 1, "dialogue": 2, "learning_session": 0}, seen=seen
            ),
        )
        assert code == 0
        assert seen["as_of"] == date(2026, 6, 1)
        out = json.loads(capsys.readouterr().out)
        assert out["as_of"] == "2026-06-01"
        assert out["purged"] == {"evidence_links": 1, "dialogue": 2, "learning_session": 0}
        assert out["total"] == 3  # 합계 = 1+2+0

    def test_default_as_of_is_today_utc(self, capsys: pytest.CaptureFixture[str]) -> None:
        """--as-of 미지정 → 오늘(UTC)로 파기·파기 0건도 종료 0."""
        seen: dict[str, date] = {}
        code = cli.main([], purge_fn=_runner({"evidence_links": 0}, seen=seen))
        assert code == 0
        assert seen["as_of"] == datetime.now(UTC).date()
        out = json.loads(capsys.readouterr().out)
        assert out["total"] == 0 and out["as_of"] == datetime.now(UTC).date().isoformat()

    def test_invalid_as_of_errors(self) -> None:
        """잘못된 날짜 형식 → argparse 에러(SystemExit)."""
        with pytest.raises(SystemExit):
            cli.main(["--as-of", "not-a-date"], purge_fn=_runner({}, seen={}))
