"""HARN-44 — 이벤트 대장 시각의 오프셋 표기 계약 동결.

## 무엇을 왜 동결하나 (사고 경위)

`store.append_event`는 `datetime.now().strftime("%Y-%m-%dT%H:%M:%S")`로 **오프셋 없는
머신 로컬 시각**을 적었다. 그래서 KST 세션이 쓴 줄과 UTC 세션이 쓴 줄이 같은 대장에
구분자 없이 섞였고, 9시간 어긋난 두 척도를 알려주는 필드가 없었다.

실측 교차검증(HARN-38 경위 규명 §3-1):
  · `done HARN-36 @2026-08-30T00:50:38` — claim 커밋 1ca71b02(+0000)와 1초 차 = **UTC** 세션
  · `start CUR-16 @2026-08-25T23:56:15` — claim 커밋 fc943cd8(+0900)와 3초 차 = **KST** 세션
두 줄의 실제 척도는 대장이 아니라 *커밋 시각과 대조해서야* 났다. 그 결과 사고 재구성에서
"어느 add가 먼저였나"(= 어느 가드를 고칠 것인가)에 답할 수 없었다.

이 파일이 동결하는 계약 3축(태스크 acceptance와 1:1):
  ① 쓰기 — `append_event`의 ts가 오프셋을 포함한다
  ② 읽기 하위호환 — 오프셋 없는 레거시 줄이 파싱 실패 없이 읽히고, 그 값이 *가정*임을
     `offset_known=False`로 말한다. 과거 줄은 소급 정정하지 않는다(날조 금지)
  ③ 정렬 변별력 — 서로 다른 TZ에서 쓴 두 줄이 **실제 시각 순서**로 정렬된다

### ③의 변별력 설계 (중요)

"오프셋이 문자열에 들어 있는가"를 검사하면 변별력이 없다 — 오프셋을 붙이기만 하고 정렬을
고치지 않아도 통과하기 때문이다. 그래서 **문자열 사전순 정렬과 실제 시각 순서가 서로
반대가 되는** 한 쌍을 골라 정렬 *결과*를 단언한다:

    "2026-09-01T09:00:00+09:00"  →  실제 00:00Z  (더 이르다)
    "2026-09-01T01:00:00+00:00"  →  실제 01:00Z  (더 늦다)

사전순으로는 `01:00+00:00` < `09:00+09:00`이라 순서가 뒤집힌다. 즉 이 테스트는 시각을
문자열로 비교하는 구현에서 **반드시 실패**한다.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import store

import backlog as cli

# 문자열 사전순과 실제 시각 순서가 어긋나는 한 쌍(위 docstring 참조).
_KST_EARLIER = "2026-09-01T09:00:00+09:00"  # = 2026-09-01T00:00:00Z
_UTC_LATER = "2026-09-01T01:00:00+00:00"  # = 2026-09-01T01:00:00Z


@pytest.fixture
def seeded_repo(git_repo: Path, monkeypatch) -> Path:
    """seed까지 끝난 저장소 (cwd 고정) — test_event_ledger_sharding.py 픽스처와 동형."""
    monkeypatch.chdir(git_repo)
    assert cli.main(["seed"]) == 0
    return git_repo


class TestWriteCarriesOffset:
    """① 쓰기 — 새로 적는 줄은 오프셋을 갖는다."""

    def test_appended_ts_is_offset_aware(self, git_repo: Path):
        """append_event가 적은 ts를 파싱하면 tzinfo가 있다.

        변별력: `datetime.now().strftime(...)`(종전 구현)으로 되돌리면 `tzinfo is None`이
        되어 이 단언이 즉시 깨진다.
        """
        store.append_event(git_repo, "start", "S1-01-alpha")
        shard = git_repo / "backlog" / "events" / "main.ndjson"
        record = json.loads(shard.read_text(encoding="utf-8").splitlines()[0])
        parsed = datetime.fromisoformat(record["ts"])
        assert parsed.tzinfo is not None, "신규 줄은 오프셋을 실어야 한다(척도 자기서술)"

    def test_appended_ts_round_trips_through_the_shared_parser(self, git_repo: Path):
        """쓰기 표기와 읽기 파서가 실제로 맞물린다(양쪽을 따로 고치는 회귀 방지)."""
        store.append_event(git_repo, "start", "S1-01-alpha")
        shard = git_repo / "backlog" / "events" / "main.ndjson"
        record = json.loads(shard.read_text(encoding="utf-8").splitlines()[0])
        moment = store.parse_event_ts(record["ts"])
        assert moment is not None
        assert moment.offset_known is True, "우리가 쓴 줄의 오프셋은 가정이 아니라 실측이다"


class TestLegacyRowsStayReadable:
    """② 읽기 하위호환 — 레거시를 버리지도, 실측인 척하지도 않는다."""

    def test_legacy_naive_row_parses_instead_of_being_dropped(self):
        """오프셋 없는 과거 줄도 읽힌다 — 못 읽으면 과거가 통째로 사라진다."""
        moment = store.parse_event_ts("2026-08-30T00:50:38")
        assert moment is not None, "레거시 줄을 파싱 실패로 버리면 안 된다"
        assert moment.moment.tzinfo is not None, "정렬 가능하도록 aware여야 한다"

    def test_legacy_row_admits_its_offset_is_assumed(self):
        """레거시의 오프셋은 *가정*이다 — 실측인 척하면 그게 날조다."""
        assert store.parse_event_ts("2026-08-30T00:50:38").offset_known is False

    def test_legacy_wall_clock_value_is_not_shifted(self):
        """가정 오프셋을 붙이되 **적힌 시각 자체는 옮기지 않는다**(소급 정정 금지).

        벽시계 값(연월일시분초)이 그대로 보존되는지 본다 — 여기서 값을 UTC로 '보정'하면
        실제 오프셋을 모르는 채 시각을 바꾸는 것이므로 복원이 아니라 날조다.
        """
        moment = store.parse_event_ts("2026-08-30T00:50:38")
        assert moment.moment.replace(tzinfo=None) == datetime(2026, 8, 30, 0, 50, 38)

    @pytest.mark.parametrize("bad", ["", "garbage", "2026-13-45T99:99:99", None, 12345])
    def test_unparseable_ts_returns_none_rather_than_raising(self, bad):
        """파싱 불가는 None — 호출자가 건너뛴다(예외로 리포트 전체를 죽이지 않는다)."""
        assert store.parse_event_ts(bad) is None


class TestOrderingAcrossTimezones:
    """③ 정렬 변별력 — 문자열이 아니라 **실제 시각**으로 정렬된다."""

    def test_cross_tz_rows_sort_by_real_instant_not_by_string(self):
        """KST 09:00(=00:00Z)이 UTC 01:00보다 **먼저**다 — 사전순과 반대.

        이 테스트가 이 태스크의 존재 이유다: 대장에 오프셋을 실은 목적이 바로
        "교차 머신 사건 순서를 재구성 가능하게" 하는 것이므로, 오프셋이 문자열에
        들어 있다는 사실이 아니라 **순서가 맞는다는 사실**을 동결해야 한다.
        """
        moments = [store.parse_event_ts(_UTC_LATER), store.parse_event_ts(_KST_EARLIER)]
        ordered = sorted(moments, key=lambda m: m.moment)
        assert ordered[0].moment == datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)
        assert ordered[1].moment == datetime(2026, 9, 1, 1, 0, tzinfo=timezone.utc)

    def test_string_sort_would_give_the_opposite_order(self):
        """대조군 — 문자열 정렬이면 순서가 뒤집힌다(위 테스트가 무엇을 잡는지 고정).

        이 단언이 깨지면 고른 표본이 더 이상 변별력을 갖지 않는다는 뜻이므로, 위
        테스트도 함께 재설계해야 한다(성공/실패 양쪽에서 같은 값을 내는 검사 방지).
        """
        assert sorted([_UTC_LATER, _KST_EARLIER])[0] == _UTC_LATER

    def test_legacy_and_offset_rows_are_mutually_comparable(self):
        """레거시(naive 가정)와 신규(aware 실측)를 섞어 정렬해도 TypeError가 나지 않는다.

        전환 직후 대장은 반드시 두 표기가 섞인 상태다 — 그때 비교가 터지면 리포트가
        통째로 죽는다.
        """
        mixed = [store.parse_event_ts("2026-08-30T00:50:38"), store.parse_event_ts(_UTC_LATER)]
        assert sorted(mixed, key=lambda m: m.moment)  # 예외 없이 정렬되면 성공


class TestConsumerReadsBothNotations:
    """소비자(policy 리포트)가 신규 줄을 조용히 누락하지 않는다 — 침묵 실패 방지."""

    def _write_shard(self, root: Path, name: str, ts: str, detail: str) -> None:
        shard_dir = root / "backlog" / "events"
        shard_dir.mkdir(parents=True, exist_ok=True)
        record = {
            "ts": ts,
            "actor": "claude/x",
            "action": "policy_warn",
            "id": "S1-01-alpha",
            "rule": "path_overlap",
            "detail": detail,
            "mode": "warn",
        }
        (shard_dir / name).write_text(
            json.dumps(record, ensure_ascii=False) + "\n", encoding="utf-8"
        )

    def test_offset_bearing_row_appears_in_the_report(self, seeded_repo: Path, capsys):
        """오프셋이 붙은 줄이 리포트에 뜬다.

        변별력: 소비자를 종전 구현(엄격 strptime + except ValueError: continue)으로
        되돌리면 이 줄은 **에러 없이 사라져** 단언이 깨진다. 크래시가 아니라 침묵
        누락이라 사람 눈으로는 잡히지 않던 부류다.
        """
        now = datetime.now().astimezone() - timedelta(hours=1)
        self._write_shard(seeded_repo, "new.ndjson", now.isoformat(timespec="seconds"), "신규표기")
        cli.main(["policy", "report", "--days", "2"])
        assert "신규표기" in capsys.readouterr().out

    def test_legacy_row_still_appears_in_the_report(self, seeded_repo: Path, capsys):
        """레거시 줄도 계속 보인다 — 신규를 살리려다 과거를 버리지 않는다."""
        naive = (datetime.now() - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%S")
        self._write_shard(seeded_repo, "old.ndjson", naive, "레거시표기")
        cli.main(["policy", "report", "--days", "2"])
        assert "레거시표기" in capsys.readouterr().out

    def test_report_discloses_assumed_offsets(self, seeded_repo: Path, capsys):
        """레거시가 섞이면 리포트가 '가정해 정렬했다'고 말한다(추정을 실측인 척 금지)."""
        naive = (datetime.now() - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%S")
        self._write_shard(seeded_repo, "old.ndjson", naive, "레거시표기")
        cli.main(["policy", "report", "--days", "2"])
        assert "가정해 정렬" in capsys.readouterr().out
