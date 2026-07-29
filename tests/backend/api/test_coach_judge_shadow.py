"""L4 coach judge would-be shadow HTTP 결선 단위테스트 — G1(hermetic·judge 주입·라이브 0).

검증 항목:
- shadow+judge_shadow on → 응답 substring *불변*(노출 비트동일·off와 동일)·유사도 모두 None.
- **비차단(fire-and-forget) 결정론 검증**: `coach._spawn`을 monkeypatch해 코루틴을 *캡처*하고
  응답 후 동기 구동(`asyncio.run`) → would_remove_ids 단언(`test_coach_judge_gate._patch_judge`·
  `test_coach_semantic._spy_to_thread` 패턴 답습 — 좌석 주입점으로 비결정성 제거).
- judge_shadow off(기본)·`semantic_mode != shadow`(off/on)면 spawn 0회.
- never-break: `_BoomSeam` judge라도 200·substring 유지(가용성 우선).

**게이트 토글**: `_compute_matches`는 실 `get_settings()`(Depends 아님·모듈 직호출)를 읽으므로
`monkeypatch.setenv` + `get_settings.cache_clear()`로 켠다(test_coach_semantic 패턴).
**judge 주입**: `coach._judge_for_gate`를 monkeypatch해 `FakeJudge`(결정론·라이브 0)를 박는다.

전부 *동기* 테스트 함수다(`TestClient`가 async 엔드포인트를 동기 구동) — test_coach_semantic과 동형.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import AsyncIterator, Coroutine, Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from whymath_backend.api import coach
from whymath_backend.api._auth import get_consented_user
from whymath_backend.api._misconception_state import (
    reset_semantic_matcher,
    set_semantic_matcher,
)
from whymath_backend.api._rate_limit import reset_store
from whymath_backend.app import create_app
from whymath_backend.config import Settings, get_settings
from whymath_backend.db.models.user import UserProfile
from whymath_backend.db.session import get_session
from whymath_backend.l4.misconception.catalog import CATALOG_BY_ID
from whymath_backend.l4.misconception.judge import (
    FakeJudge,
    JudgeProtocol,
    JudgeVerdict,
    LLMJudge,
)
from whymath_backend.l4.misconception.models import MisconceptionMatch
from whymath_backend.l4.misconception.shadow import MisconceptionJudgeShadowObservation
from whymath_backend.schema.enums import Persona
from whymath_backend.schema.user import UserProfile as UserProfileSchema

_JUDGE_RECORD_LOGGER = "whymath.l4.misconception.judge_shadow.record"


def _judge_records(caplog: pytest.LogCaptureFixture) -> list[str]:
    """judge shadow 구조화 record 로거 JSON 라인만(평문·다른 로거 노이즈 배제)."""
    return [r.getMessage() for r in caplog.records if r.name == _JUDGE_RECORD_LOGGER]


_UID = uuid.uuid4()

# 완전 substring 매칭(confidence 1.0) — distribution-over-power. 노출은 이 substr만(불변).
_SUBSTR_FULL = "내 풀이는 (a+b)² = a² + b²로 전개했어"
# 스텁이 의미 매치로 돌려줄 distinct id(substring과 안 겹치게) — judge가 이걸 판정한다.
_SEMANTIC_ID = "division-by-zero"


@pytest.fixture(autouse=True)
def _reset_rate_limit_store() -> None:
    """매 테스트 격리 — sliding window 카운트 리셋(test_coach 패턴)."""
    asyncio.run(reset_store())


@pytest.fixture(autouse=True)
def _reset_matcher_singleton() -> Iterator[None]:
    """매 테스트 전후 의미 매처 싱글톤 격리 — 주입 누수 차단."""
    reset_semantic_matcher()
    yield
    reset_semantic_matcher()


@pytest.fixture(autouse=True)
def _restore_settings_cache() -> Iterator[None]:
    """env 토글 누수 차단 — 테스트 후 전역 Settings 캐시를 무조건 클리어."""
    yield
    get_settings.cache_clear()


def _enable_shadow(monkeypatch: pytest.MonkeyPatch) -> None:
    """매처 모드 SHADOW — env+cache_clear(judge shadow는 이 모드에서만 효력)."""
    monkeypatch.setenv("WHYMATH_MISCONCEPTION_SEMANTIC_MODE", "shadow")
    get_settings.cache_clear()


def _enable_judge_shadow(monkeypatch: pytest.MonkeyPatch) -> None:
    """judge would-be shadow 토글 ON — 매처 shadow와 *독립* 토글(비용 분리)."""
    monkeypatch.setenv("WHYMATH_MISCONCEPTION_JUDGE_SHADOW", "true")
    get_settings.cache_clear()


def _patch_judge(monkeypatch: pytest.MonkeyPatch, judge: JudgeProtocol) -> None:
    """`_judge_for_gate` 좌석을 주입 judge로 교체(좌석 주입점·hermetic·라이브 0).

    좌석은 이제 app.state 공유 provider/cache/trace를 kwargs로 받으므로 대체물도 kwargs를
    받아 무시한다(`**_`) — 실 좌석 시그니처와 호환(주입값은 FakeJudge라 소비하지 않음).
    """
    monkeypatch.setattr(coach, "_judge_for_gate", lambda **_: judge)


class _CapturedSpawn:
    """`coach._spawn`을 대체해 코루틴을 *캡처*(즉시 실행 안 함) — 비차단을 결정론으로 만든다.

    실 `_spawn`은 `create_task`로 백그라운드 실행이라 *언제 끝나는지 비결정*이다. 테스트는
    이 캡처기로 코루틴 객체만 모아두고(coach는 즉시 반환 — 비차단 계약 보존), 응답이 끝난 뒤
    `drive()`로 `asyncio.run` 동기 구동해 부수효과(레코드 로깅)를 결정론으로 관측한다. spawn
    *호출 자체*가 일어났는지(off면 0회)도 이 캡처로 센다.
    """

    def __init__(self) -> None:
        self.coros: list[Coroutine[Any, Any, None]] = []

    def __call__(self, coro: Coroutine[Any, Any, None]) -> None:
        self.coros.append(coro)  # 캡처만 — coach는 즉시 반환(비차단 계약 보존)

    @property
    def calls(self) -> int:
        return len(self.coros)

    def drive(self) -> None:
        """캡처한 코루틴을 동기 구동(응답 후·요청 루프 종료 뒤 — 부수효과 결정론 관측)."""
        for coro in self.coros:
            asyncio.run(coro)
        self.coros.clear()

    def close(self) -> None:
        """구동 안 한 캡처 코루틴을 닫는다('never awaited' 경고 방지 — 부수효과 불필요 시)."""
        for coro in self.coros:
            coro.close()
        self.coros.clear()


def _patch_spawn(monkeypatch: pytest.MonkeyPatch) -> _CapturedSpawn:
    """coach의 spawn 지점을 캡처기로 교체 + 캡처기 반환(spawn 호출 캡처·동기 구동)."""
    captured = _CapturedSpawn()
    monkeypatch.setattr(coach, "_spawn", captured)
    return captured


def _settings_no_limits() -> Settings:
    """rate limit 0(비활성)·JWT 시크릿 채움 — 게이트는 env로 따로 켠다."""
    return Settings(
        jwt_secret_key=SecretStr("test-secret-0123456789abcdef"),
        coach_rate_limit_read_per_minute=0,
        coach_rate_limit_write_per_minute=0,
        coach_rate_limit_ip_read_per_minute=0,
        coach_rate_limit_ip_write_per_minute=0,
        coach_rate_limit_device_read_per_minute=0,
        coach_rate_limit_device_write_per_minute=0,
    )


def _user() -> UserProfile:
    return UserProfile.from_schema(
        UserProfileSchema(user_id=_UID, persona_primary=Persona.A_일반고고3)
    )


class _FakeSession:
    """stateless /v1/coach용 — execute 호출 시 AssertionError(DB 무접근)."""

    async def execute(self, stmt: Any) -> None:
        raise AssertionError("coach 라우터(stateless)는 DB 쿼리하지 않아야 한다.")


def _client() -> TestClient:
    app = create_app()
    app.dependency_overrides[get_consented_user] = _user
    app.dependency_overrides[get_settings] = _settings_no_limits

    async def _sess() -> AsyncIterator[_FakeSession]:
        yield _FakeSession()

    app.dependency_overrides[get_session] = _sess
    return TestClient(app)


class _StubMatcher:
    """고정 의미 매치(distinct id)를 돌려주는 결정론 매처 — judge가 판정할 후보를 공급."""

    def match(
        self, student_solution: str, *, top_k: int, threshold: float
    ) -> list[MisconceptionMatch]:
        return [
            MisconceptionMatch(
                misconception=CATALOG_BY_ID[_SEMANTIC_ID],
                confidence=0.95,
                semantic_similarity=0.95,
            )
        ]


class _BoomSeam:
    """generate가 항상 raise — `LLMJudge` never-break(예외→UNCERTAIN→유지) 검증용."""

    async def generate(self, prompt: str, system: str) -> str:
        raise RuntimeError("judge seam 강제 실패(never-break 테스트)")


def _exposed_ids(body: dict[str, Any]) -> list[str]:
    return [m["misconception"]["id"] for m in body["misconceptions"]]


# ──────────────────────────────────────────────────────────────────────────
# ① shadow+judge_shadow on → 노출 substring 불변(off 비트동일) + spawn 1회
# ──────────────────────────────────────────────────────────────────────────
class TestExposureUnchanged:
    def test_judge_shadow_does_not_change_exposure(self, monkeypatch: pytest.MonkeyPatch) -> None:
        set_semantic_matcher(_StubMatcher())  # type: ignore[arg-type]
        _patch_judge(monkeypatch, FakeJudge({_SEMANTIC_ID: JudgeVerdict.NOT_EXPRESSES}))
        captured = _patch_spawn(monkeypatch)
        _enable_shadow(monkeypatch)
        _enable_judge_shadow(monkeypatch)
        body = _client().post("/v1/coach", json={"student_input": _SUBSTR_FULL}).json()
        # 노출은 substring 그대로 — semantic-only(division-by-zero)는 judge가 아니오여도 비노출.
        ids = _exposed_ids(body)
        assert "distribution-over-power" in ids
        assert _SEMANTIC_ID not in ids  # judge shadow는 노출을 *건드리지 않는다*
        assert all(m["semantic_similarity"] is None for m in body["misconceptions"])
        # judge shadow가 비차단으로 *스폰됐다*(의미 후보 있음 → 1회).
        assert captured.calls == 1
        captured.close()  # 이 테스트는 구동 안 함(스폰 여부만 확인) → 코루틴 닫기


# ──────────────────────────────────────────────────────────────────────────
# ② 비차단 결정론 — 캡처한 코루틴을 동기 구동 → would-be 분류 관측
# ──────────────────────────────────────────────────────────────────────────
class TestNonBlockingDeterministic:
    def test_captured_coro_records_would_remove(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        # judge가 의미 후보(division-by-zero)를 '아니오'로 판정 → would_remove에 실려 로깅.
        set_semantic_matcher(_StubMatcher())  # type: ignore[arg-type]
        _patch_judge(monkeypatch, FakeJudge({_SEMANTIC_ID: JudgeVerdict.NOT_EXPRESSES}))
        captured = _patch_spawn(monkeypatch)
        _enable_shadow(monkeypatch)
        _enable_judge_shadow(monkeypatch)
        resp = _client().post("/v1/coach", json={"student_input": _SUBSTR_FULL})
        assert resp.status_code == 200, resp.text
        assert captured.calls == 1  # 비차단 스폰 1회(응답은 이미 반환됨)
        # 응답이 끝난 뒤(요청 루프 종료) 캡처 코루틴을 동기 구동 — 부수효과(레코드) 결정론 관측.
        with caplog.at_level(logging.INFO, logger=_JUDGE_RECORD_LOGGER):
            captured.drive()
        records = _judge_records(caplog)
        assert len(records) == 1
        obs = MisconceptionJudgeShadowObservation.model_validate_json(records[0])
        assert obs.would_remove_ids == [_SEMANTIC_ID]  # 아니오 → would-be removed
        assert obs.verdict_not_expresses == 1

    def test_feed_threshold_and_routing_threaded(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        # coach가 settings의 threshold·routing을 레코드로 thread하는지(env→레코드).
        monkeypatch.setenv("WHYMATH_MISCONCEPTION_SEMANTIC_THRESHOLD", "0.40")
        monkeypatch.setenv("WHYMATH_MISCONCEPTION_JUDGE_ROUTING", "general_mid")
        set_semantic_matcher(_StubMatcher())  # type: ignore[arg-type]
        _patch_judge(monkeypatch, FakeJudge(default=JudgeVerdict.EXPRESSES))
        captured = _patch_spawn(monkeypatch)
        _enable_shadow(monkeypatch)
        _enable_judge_shadow(monkeypatch)
        _client().post("/v1/coach", json={"student_input": _SUBSTR_FULL})
        with caplog.at_level(logging.INFO, logger=_JUDGE_RECORD_LOGGER):
            captured.drive()
        records = _judge_records(caplog)
        obs = MisconceptionJudgeShadowObservation.model_validate_json(records[0])
        assert obs.feed_threshold == 0.40  # judge-feed 운영점(04b §4)
        assert obs.judge_routing == "general_mid"  # judge 모델 라벨(04b §2)


# ──────────────────────────────────────────────────────────────────────────
# ③ judge_shadow off / 매처 모드 ≠ shadow → spawn 0회
# ──────────────────────────────────────────────────────────────────────────
class TestSpawnGating:
    def test_judge_shadow_off_no_spawn(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # 매처 shadow는 켜되 judge_shadow 토글은 끔(기본) → spawn 0회(비용 분리·독립 토글).
        set_semantic_matcher(_StubMatcher())  # type: ignore[arg-type]
        _patch_judge(monkeypatch, FakeJudge(default=JudgeVerdict.NOT_EXPRESSES))
        captured = _patch_spawn(monkeypatch)
        _enable_shadow(monkeypatch)  # judge_shadow는 *안* 켠다
        body = _client().post("/v1/coach", json={"student_input": _SUBSTR_FULL}).json()
        assert captured.calls == 0  # judge_shadow off → spawn 0
        assert "distribution-over-power" in _exposed_ids(body)  # 노출 불변

    def test_mode_off_no_spawn(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # 매처 모드 off(기본)면 judge_shadow on이어도 shadow 분기 자체에 안 들어감 → spawn 0.
        set_semantic_matcher(_StubMatcher())  # type: ignore[arg-type]
        _patch_judge(monkeypatch, FakeJudge(default=JudgeVerdict.NOT_EXPRESSES))
        captured = _patch_spawn(monkeypatch)
        _enable_judge_shadow(monkeypatch)  # judge_shadow on이지만 매처 모드는 off
        body = _client().post("/v1/coach", json={"student_input": _SUBSTR_FULL}).json()
        assert captured.calls == 0  # 모드 off → shadow 분기 미진입 → spawn 0
        assert "distribution-over-power" in _exposed_ids(body)

    def test_mode_on_no_spawn(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # 매처 모드 on(노출 결합)이면 shadow 분기가 아니므로 judge_shadow는 무효 → spawn 0.
        monkeypatch.setenv("WHYMATH_MISCONCEPTION_SEMANTIC_MODE", "on")
        get_settings.cache_clear()
        set_semantic_matcher(_StubMatcher())  # type: ignore[arg-type]
        _patch_judge(monkeypatch, FakeJudge(default=JudgeVerdict.NOT_EXPRESSES))
        captured = _patch_spawn(monkeypatch)
        _enable_judge_shadow(monkeypatch)
        body = _client().post("/v1/coach", json={"student_input": _SUBSTR_FULL}).json()
        assert captured.calls == 0  # on은 shadow 분기 아님 → judge_shadow 미적용
        # on이라 semantic-only가 *노출*된다(judge shadow는 on 경로를 안 건드림 — 별 슬라이스).
        assert _SEMANTIC_ID in _exposed_ids(body)


# ──────────────────────────────────────────────────────────────────────────
# ④ never-break — judge seam 예외라도 200·substring 유지(가용성 우선)
# ──────────────────────────────────────────────────────────────────────────
class TestNeverBreak:
    def test_boom_judge_still_200_and_substring(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # 실 LLMJudge + 항상 raise하는 seam을 judge_shadow에 박아도, 비차단+never-break라
        # 응답은 200·substring 노출 불변(judge shadow 실패가 응답을 절대 안 깸).
        set_semantic_matcher(_StubMatcher())  # type: ignore[arg-type]
        _patch_judge(monkeypatch, LLMJudge(_BoomSeam()))
        captured = _patch_spawn(monkeypatch)
        _enable_shadow(monkeypatch)
        _enable_judge_shadow(monkeypatch)
        resp = _client().post("/v1/coach", json={"student_input": _SUBSTR_FULL})
        assert resp.status_code == 200, resp.text  # 500 아님(가용성 우선)
        assert "distribution-over-power" in _exposed_ids(resp.json())  # 노출 불변
        # 캡처 코루틴을 구동해도(seam이 raise) observe의 never-break로 예외 전파 0.
        captured.drive()  # 예외 없이 완료해야(LLMJudge가 UNCERTAIN 폴백·observe가 방어)
