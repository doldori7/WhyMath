"""HARN-46 — 이벤트 대장 세션 샤딩 계약 동결.

## 무엇을 왜 동결하나 (사고 경위)

PR #931이 CI 16잡 green을 **4회** 확보하고도 머지가 5라운드 지연됐다. 라운드 2·3·4의
원인이 전부 `backlog/events.ndjson`이다: 모든 세션이 같은 파일에 append하는데,
`.gitattributes merge=union`은 **로컬 git에서만** 작동하고 **GitHub의 mergeability
판정은 저장소 merge driver를 적용하지 않는다**. 그래서 main에 어떤 PR이 착지하든
이 파일을 함께 만진 열린 PR은 전부 dirty(충돌)가 됐다 — 로컬 병합은 매번 충돌 0,
GitHub만 충돌. 문제는 데이터가 아니라 **배치**였다.

대책 = 세션(=actor 브랜치)당 1샤드(`backlog/events/<actor>.ndjson`). 서로 다른
세션은 서로 다른 파일에 쓰므로 "두 브랜치가 같은 파일을 동시 append"하는 상황
자체가 사라진다 — 충돌을 '해소 가능'하게 두지 않고 '발생 불가능'하게 만든다
(`backlog/tasks/` 태스크당-1파일 선례와 동형).

이 파일이 동결하는 계약 5축(태스크 acceptance와 1:1):
  ① 쓰기 샤딩 — `append_event`가 actor 샤드에 기록
  ② 레거시 미기록 — `events.ndjson`은 읽기 전용 역사(바이트 불변)
  ③ 충돌 불가 속성 — 서로 다른 actor → 서로소 파일 집합
  ④ 읽기 합집합 — policy 리포트가 레거시 + 샤드 전부를 합산
  ⑤ 경로 안전·결정론 — 샤드명이 events/ 밖으로 탈출 불가·같은 입력 같은 출력

⑥(배선): 실저장소 `.gitattributes`에 샤드 union 패턴이 실제로 선언돼 있는지 —
계약을 만들고 배선을 확인하지 않으면 "저장소에 존재함"과 "돌아감"이 갈라진다
(CLAUDE.md "검증 장치를 만들고 배선 확인 없이 완료 선언 금지").
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import store

import backlog as cli

# 실저장소 루트 — ⑥ 배선 검사 전용(그 외 테스트는 전부 hermetic 임시 저장소).
_REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def seeded_repo(git_repo: Path, monkeypatch) -> Path:
    """seed까지 끝난 저장소 (cwd 고정) — test_cli.py 픽스처와 동형."""
    monkeypatch.chdir(git_repo)
    assert cli.main(["seed"]) == 0
    return git_repo


def _events_dir(root: Path) -> Path:
    return root / "backlog" / "events"


class TestShardWrite:
    """① 쓰기 샤딩 + ② 레거시 미기록."""

    def test_append_writes_to_actor_shard_not_legacy(self, git_repo: Path):
        """append_event는 actor(=브랜치) 샤드에 쓰고 레거시 파일을 만들지 않는다."""
        store.append_event(git_repo, "start", "S1-01-alpha")
        shard = _events_dir(git_repo) / "main.ndjson"  # git_repo 픽스처 브랜치 = main
        assert shard.is_file(), "샤드 파일이 생성돼야 한다"
        record = json.loads(shard.read_text(encoding="utf-8").splitlines()[0])
        assert record["actor"] == "main"
        assert record["action"] == "start"
        # 레거시 단일 대장은 **생성조차** 되지 않는다 — 신규 기록 경로가 아니다.
        assert not (git_repo / "backlog" / "events.ndjson").exists()

    def test_legacy_file_is_never_touched(self, git_repo: Path):
        """기존 레거시 파일이 있어도 append_event는 그것을 바이트 하나 안 건드린다.

        변별력: 샤딩 구현을 레거시 경로로 되돌리면(과거 코드) 이 단언이 즉시 깨진다.
        """
        legacy = git_repo / "backlog" / "events.ndjson"
        legacy.parent.mkdir(parents=True, exist_ok=True)
        original = '{"ts": "2026-01-01T00:00:00", "actor": "old", "action": "start", "id": "X"}\n'
        legacy.write_text(original, encoding="utf-8")
        store.append_event(git_repo, "done", "S1-01-alpha")
        assert legacy.read_text(encoding="utf-8") == original, "레거시는 읽기 전용 역사다"


class TestConflictImpossibility:
    """③ 충돌 불가 속성 — 사고를 재현하는 형태 그대로: 두 세션이 동시에 append."""

    def test_different_actors_write_disjoint_files(self, git_repo: Path, monkeypatch):
        """서로 다른 브랜치의 세션은 서로 다른 파일에 쓴다 — 같은 파일 동시 append 소멸.

        이것이 이 태스크의 존재 이유다: GitHub이 union을 적용하지 않아도, 애초에
        같은 파일을 두 브랜치가 만지지 않으면 충돌할 대상이 없다.
        """
        actors = iter(["claude/session-a", "claude/session-b"])
        monkeypatch.setattr(store, "current_branch", lambda _root: next(actors))
        store.append_event(git_repo, "start", "T-1")
        store.append_event(git_repo, "start", "T-2")
        shards = sorted(p.name for p in _events_dir(git_repo).glob("*.ndjson"))
        assert shards == ["claude_session-a.ndjson", "claude_session-b.ndjson"]
        # 각 샤드에는 자기 세션 기록만 있다 — 파일 집합이 서로소다.
        a = _events_dir(git_repo) / "claude_session-a.ndjson"
        b = _events_dir(git_repo) / "claude_session-b.ndjson"
        assert json.loads(a.read_text(encoding="utf-8"))["id"] == "T-1"
        assert json.loads(b.read_text(encoding="utf-8"))["id"] == "T-2"

    def test_same_actor_appends_to_same_shard(self, git_repo: Path, monkeypatch):
        """같은 actor의 연속 기록은 한 샤드에 순서대로 쌓인다(세션 내 선형성 유지)."""
        monkeypatch.setattr(store, "current_branch", lambda _root: "claude/one-session")
        store.append_event(git_repo, "start", "T-1")
        store.append_event(git_repo, "done", "T-1")
        shard = _events_dir(git_repo) / "claude_one-session.ndjson"
        actions = [
            json.loads(line)["action"] for line in shard.read_text(encoding="utf-8").splitlines()
        ]
        assert actions == ["start", "done"]


class TestShardNameSafety:
    """⑤ 경로 안전·결정론."""

    def test_shard_name_is_deterministic(self):
        assert store._event_shard_name("claude/foo-bar") == store._event_shard_name(
            "claude/foo-bar"
        )

    @pytest.mark.parametrize(
        "actor",
        ["../../etc/passwd", "..", "a/../../b", ".hidden", "한글브랜치", "", "unknown"],
    )
    def test_shard_stays_inside_events_dir(self, actor: str, tmp_path: Path):
        """어떤 actor 문자열도 events/ 디렉터리 밖을 가리키는 샤드를 만들 수 없다.

        브랜치명은 사실상 자유 문자열이다 — '..'·'/'가 경로로 해석되면 append가
        저장소 임의 위치에 파일을 만든다. 새니타이즈가 그 부류를 전부 평문자로
        접는지 resolve() 봉쇄로 단언한다.
        """
        name = store._event_shard_name(actor)
        events = (tmp_path / "backlog" / "events").resolve()
        target = (events / name).resolve()
        assert target.parent == events, f"경로 탈출: {actor!r} → {name!r}"
        assert name.endswith(".ndjson") and not name.startswith(".")
        assert "/" not in name and "\\" not in name

    def test_length_cap(self):
        """255자 파일명 한계 방어 — 긴 브랜치명도 120자 + 확장자로 잘린다."""
        name = store._event_shard_name("b" * 500)
        assert len(name) <= 120 + len(".ndjson")


class TestReadUnion:
    """④ 읽기 합집합 — 레거시 역사 + 샤드 신규 기록 무손실."""

    def test_event_paths_returns_legacy_then_shards(self, git_repo: Path):
        legacy = git_repo / "backlog" / "events.ndjson"
        legacy.parent.mkdir(parents=True, exist_ok=True)
        legacy.write_text("{}\n", encoding="utf-8")
        _events_dir(git_repo).mkdir(parents=True, exist_ok=True)
        (_events_dir(git_repo) / "b.ndjson").write_text("{}\n", encoding="utf-8")
        (_events_dir(git_repo) / "a.ndjson").write_text("{}\n", encoding="utf-8")
        names = [p.name for p in store.event_paths(git_repo)]
        assert names == ["events.ndjson", "a.ndjson", "b.ndjson"], "레거시 우선 + 샤드 이름 정렬"

    def test_policy_report_sums_legacy_and_shard(self, seeded_repo: Path, capsys):
        """policy 리포트가 레거시의 과거 warn과 샤드의 신규 warn을 **합산**한다.

        변별력: 리포트가 레거시만 읽으면(과거 코드) 1건, 샤드만 읽으면 1건 — 2건은
        합집합을 읽을 때만 나온다. 어느 쪽 퇴행이든 이 단언이 깨진다.
        """
        from datetime import datetime

        now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        legacy = seeded_repo / "backlog" / "events.ndjson"
        legacy.write_text(
            json.dumps(
                {
                    "ts": now,
                    "actor": "legacy-session",
                    "action": "policy_warn",
                    "id": "-",
                    "rule": "adhoc_edit",
                    "file": "src/legacy.py",
                    "mode": "warn",
                },
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
        store.append_event(
            seeded_repo, "policy_warn", "-", rule="adhoc_edit", file="src/new.py", mode="warn"
        )
        capsys.readouterr()
        assert cli.main(["policy", "report"]) == 0
        out = capsys.readouterr().out
        assert "adhoc_edit: 2건" in out, f"레거시+샤드 합산 실패 — 출력:\n{out}"


class TestUnionAttributeWiring:
    """⑥ 실저장소 배선 — 샤드 패턴이 .gitattributes union에 실제로 선언돼 있는가."""

    def test_gitattributes_declares_shard_union(self):
        text = (_REPO_ROOT / ".gitattributes").read_text(encoding="utf-8")
        lines = [
            line.split("#")[0].split()
            for line in text.splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]
        assert ["backlog/events/*.ndjson", "merge=union"] in lines, (
            ".gitattributes에 'backlog/events/*.ndjson merge=union'이 없다 — 같은 actor "
            "샤드가 재생성 브랜치에서 겹치는 잔여 경우의 로컬 방어가 빠진다"
        )
        # 레거시 규칙도 유지돼야 한다(역사 파일의 방어를 걷어내지 않는다).
        assert ["backlog/events.ndjson", "merge=union"] in lines
