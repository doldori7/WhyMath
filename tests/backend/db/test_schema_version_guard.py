"""기동 시 스키마 버전 가드 — SEC-03 (hermetic).

이 테스트가 못 박는 것:

  ① **동결** — `KNOWN_REVISIONS`/`EXPECTED_ALEMBIC_HEAD`가 실제 alembic 이력과 일치한다.
     wheel에 `alembic/versions/`가 없어 런타임은 상수를 믿을 수밖에 없으므로, 그 상수가
     실물과 어긋나는 순간 여기서 터져야 한다(인프로세스 이중 회계).
  ② **판정 3분기** — MATCH / BEHIND / AHEAD. 특히 AHEAD를 BEHIND로 오분류하면 *정상 롤백*에서
     기동이 막혀 가드 자체가 장애 원인이 된다.
  ③ **fail-closed 변별력** — 같은 뒤처짐이라도 프로덕션이면 raise, 개발이면 통과로 판정이
     뒤집힌다. 개발·CI까지 막으면 아무도 못 돌린다.
  ④ **확인 실패를 통과로 위장하지 않는다** — DB 미도달 시 프로덕션은 거부한다.
"""

from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path
from typing import Any

import pytest

from whymath_backend.db.schema_version import (
    EXPECTED_ALEMBIC_HEAD,
    KNOWN_REVISIONS,
    SchemaVersionVerdict,
    classify_applied_head,
    read_applied_heads,
    verify_schema_version,
)


class _FakeSettings:
    """프로덕션 추정 분기만 시험하는 최소 설정 대역."""

    def __init__(self, *, kakao: bool = False, naver: bool = False) -> None:
        self.kakao_configured = kakao
        self.naver_configured = naver


def _alembic_revisions_from_disk() -> tuple[str, ...]:
    """실제 마이그레이션 파일에서 base→head 위상 순서를 읽는다(상수의 대조군)."""
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    backend_root = Path(__file__).resolve().parents[3] / "src" / "backend"
    config = Config(str(backend_root / "alembic.ini"))
    config.set_main_option("script_location", str(backend_root / "alembic"))
    script = ScriptDirectory.from_config(config)
    return tuple(rev.revision for rev in script.walk_revisions())[::-1]


class TestConstantIsFrozenAgainstRealHistory:
    def test_known_revisions_matches_alembic_history(self) -> None:
        """상수가 실제 이력과 순서까지 같아야 한다 — 어긋나면 런타임 판정이 통째로 거짓이 된다."""
        assert KNOWN_REVISIONS == _alembic_revisions_from_disk()

    def test_expected_head_is_the_real_head(self) -> None:
        """마이그레이션을 추가하고 상수를 안 고치면 여기서 잡힌다."""
        assert EXPECTED_ALEMBIC_HEAD == _alembic_revisions_from_disk()[-1]

    def test_no_duplicate_revisions(self) -> None:
        """중복이 있으면 `in` 기반 BEHIND 판정이 흔들린다."""
        assert len(set(KNOWN_REVISIONS)) == len(KNOWN_REVISIONS)


class TestClassify:
    def test_current_head_is_match(self) -> None:
        assert classify_applied_head(EXPECTED_ALEMBIC_HEAD) is SchemaVersionVerdict.MATCH

    def test_older_revision_is_behind(self) -> None:
        """SEC-02 실측이 만난 실제 상태 — 암호화 마이그레이션 이전 리비전."""
        assert classify_applied_head("f3a4b5c6d7e8") is SchemaVersionVerdict.BEHIND

    def test_never_migrated_is_behind(self) -> None:
        """alembic_version 행 없음 = 스키마 부재 = 뒤처짐의 극단."""
        assert classify_applied_head(None) is SchemaVersionVerdict.BEHIND

    def test_unknown_revision_is_ahead(self) -> None:
        """**변별력** — 코드가 모르는 리비전은 AHEAD여야 한다.

        BEHIND로 오분류하면 정상 롤백(코드만 되돌리고 DB는 앞선 상태)에서 프로덕션 기동이
        막혀 가드가 장애 원인이 된다.
        """
        assert classify_applied_head("ffffffffffff") is SchemaVersionVerdict.AHEAD


class _FakeResult:
    def __init__(self, rows: list[tuple[str]]) -> None:
        self._rows = rows

    def all(self) -> list[tuple[str]]:
        return list(self._rows)


class _FakeSession:
    def __init__(self, rows: list[tuple[str]]) -> None:
        self._rows = rows

    async def execute(self, _stmt: Any) -> _FakeResult:
        return _FakeResult(self._rows)


class TestReadAppliedHeads:
    async def test_reads_and_sorts(self) -> None:
        session = _FakeSession([("b",), ("a",)])
        assert await read_applied_heads(session) == ("a", "b")

    async def test_empty_table(self) -> None:
        assert await read_applied_heads(_FakeSession([])) == ()


def _patch_session(monkeypatch: pytest.MonkeyPatch, rows: list[tuple[str]] | None) -> None:
    """`verify_schema_version`이 쓰는 sessionmaker를 대역으로 바꾼다(rows=None이면 DB 미도달)."""

    class _CM:
        async def __aenter__(self) -> _FakeSession:
            assert rows is not None
            return _FakeSession(rows)

        async def __aexit__(self, *_exc: object) -> None:
            return None

    def _fake_sessionmaker(_settings: Any) -> Any:
        if rows is None:
            raise ConnectionRefusedError("DB 미도달(대역)")
        return lambda: _CM()

    monkeypatch.setattr(
        "whymath_backend.db.session.get_sessionmaker", _fake_sessionmaker, raising=True
    )


class TestVerifyFailClosed:
    async def test_production_behind_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """프로덕션에서 스키마가 뒤처지면 기동을 거부한다."""
        _patch_session(monkeypatch, [("f3a4b5c6d7e8",)])
        with pytest.raises(RuntimeError, match="뒤처졌습니다"):
            await verify_schema_version(_FakeSettings(kakao=True))

    async def test_development_behind_only_warns(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """**변별력** — 같은 뒤처짐이라도 개발이면 판정이 뒤집힌다(경고 후 기동 계속).

        위 테스트가 "항상 raise"라는 고장이 아님을 증명한다. 개발·CI를 막으면 아무도 못 돌린다.
        """
        _patch_session(monkeypatch, [("f3a4b5c6d7e8",)])
        with caplog.at_level(logging.WARNING):
            await verify_schema_version(_FakeSettings())
        assert "뒤처졌습니다" in caplog.text

    async def test_match_is_silent(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """일치하면 프로덕션에서도 통과하고 경고도 남기지 않는다 — 가드는 *불일치*만 막는다."""
        _patch_session(monkeypatch, [(EXPECTED_ALEMBIC_HEAD,)])
        with caplog.at_level(logging.WARNING):
            await verify_schema_version(_FakeSettings(kakao=True))
        assert caplog.text == ""

    async def test_ahead_does_not_block_production(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """앞선 스키마는 프로덕션에서도 막지 않는다 — 막으면 롤백이 불가능해진다."""
        _patch_session(monkeypatch, [("ffffffffffff",)])
        with caplog.at_level(logging.WARNING):
            await verify_schema_version(_FakeSettings(naver=True))
        assert "앞섭니다" in caplog.text

    async def test_unreachable_db_raises_in_production(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """확인 실패를 통과로 위장하지 않는다 — 예외 타입명을 메시지에 포함(침묵 실패 금지)."""
        _patch_session(monkeypatch, None)
        with pytest.raises(RuntimeError, match="ConnectionRefusedError"):
            await verify_schema_version(_FakeSettings(kakao=True))

    async def test_unreachable_db_only_warns_in_development(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """DB 없는 개발 환경에서 부팅이 막히면 안 된다."""
        _patch_session(monkeypatch, None)
        with caplog.at_level(logging.WARNING):
            await verify_schema_version(_FakeSettings())
        assert "확인하지 못했습니다" in caplog.text


class TestBootIsNotHeldIndefinitely:
    """블랙홀 DB(패킷 드롭)에서 부팅이 무한 대기하지 않는다 — 2026-07-28 실측 결함의 동결.

    연결 *거부*는 즉시 끝나지만 패킷이 드롭되는 호스트는 안 끝난다. 타임아웃 없이 배포했다면
    잘못된 DB 주소 하나로 부팅이 영원히 멈췄을 것이다(`ping_device_store_health` 슬라이스 31과
    같은 함정).
    """

    async def test_hanging_connection_is_bounded(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """세션 획득이 끝나지 않아도 타임아웃이 끊고 판정(프로덕션=거부)으로 넘어간다."""

        class _HangingCM:
            async def __aenter__(self) -> Any:
                await asyncio.sleep(3600)  # 영원히 안 끝나는 연결
                raise AssertionError("unreachable")

            async def __aexit__(self, *_exc: object) -> None:
                return None

        monkeypatch.setattr(
            "whymath_backend.db.session.get_sessionmaker",
            lambda _s: (lambda: _HangingCM()),
            raising=True,
        )
        settings = _FakeSettings(kakao=True)
        settings.device_store_health_check_timeout_seconds = 0.05  # type: ignore[attr-defined]

        started = time.monotonic()
        with pytest.raises(RuntimeError, match="확인하지 못했습니다"):
            await verify_schema_version(settings)
        # 타임아웃이 없으면 여기까지 오지 못한다(테스트가 매달린다) — 상한도 함께 확인.
        assert time.monotonic() - started < 2.0

    async def test_timeout_knob_is_reused_not_reinvented(self) -> None:
        """새 설정 축을 만들지 않고 기존 startup health check 노브를 쓴다(설정 표면 최소화)."""
        from whymath_backend.config import Settings

        assert hasattr(Settings, "model_fields")
        assert "device_store_health_check_timeout_seconds" in Settings.model_fields
        assert not any(
            name.startswith("schema_version") for name in Settings.model_fields
        ), "스키마 가드 전용 설정 축이 생겼다 — 재사용 원칙 위반"
