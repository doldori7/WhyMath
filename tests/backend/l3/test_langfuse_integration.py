"""LangfuseSink 통합 테스트 — 실제 Langfuse 전송 (Phaiakes9/클라우드 전용).

기본 SKIP. 실행하려면 환경변수 `WHYMATH_RUN_INTEGRATION=1` *그리고* Langfuse 키
(`WHYMATH_LANGFUSE_PUBLIC_KEY`·`WHYMATH_LANGFUSE_SECRET_KEY`, 필요 시
`WHYMATH_LANGFUSE_HOST`)를 설정한다. CI는 이 변수·키를 설정하지 않으므로 자동으로
빠진다(tests/backend/conftest.py의 게이트 + 아래 키 부재 시 graceful skip).
redis 통합 테스트(test_redis_integration.py)가 미도달 시 skip한 것과 같은 패턴이다.

목적: 결정 필드 dict → 실제 Langfuse 이벤트 전송 + flush가 인증·네트워크와 함께
e2e로 동작하는지 Kiki가 Phaiakes9/클라우드 프로젝트에서 확인. 라이브러리(langfuse)는
이미 의존성에 있고(langfuse>=2.50.0; 설치본 4.6.1), `langfuse.Langfuse`로 연결한다.

never-break 보장 검증도 겸한다: 잘못된 키로도 record()가 예외를 던지지 않아야 한다.

설계 정본: docs/architecture/03a_l3_router_design.md §F.2(Langfuse 필드 표).
"""

from __future__ import annotations

import pytest
from pydantic import SecretStr

from whymath_backend.config import Settings
from whymath_backend.l3.trace import LangfuseSink

pytestmark = pytest.mark.integration


def _live_settings() -> Settings:
    """환경변수(WHYMATH_LANGFUSE_*)에서 실제 키를 읽은 Settings."""
    return Settings()


def _sample_fields() -> dict[str, object]:
    """langfuse_fields() 형태의 대표 결정 dict(03a §F.2)."""
    return {
        "cost_tier": "local",
        "local_family": "math",
        "local_model": "fast",
        "mode": "sync",
        "est_latency_ms": 1010,
        "est_cost_krw": 0.0,
        "call_site": None,
        "cache_hit": False,
        "escalated_from": None,
        "student_id_hash": "integration-test-hash",
        "reason": "integration",
    }


def test_record_and_flush_on_live_langfuse() -> None:
    """실제 Langfuse로 이벤트를 보내고 flush가 인증·네트워크와 함께 동작한다.

    키가 없으면 graceful skip(설정되지 않은 환경에선 통합 테스트 의미 없음).
    """
    settings = _live_settings()
    if not settings.langfuse_configured:
        pytest.skip("Langfuse 키 미설정 — WHYMATH_LANGFUSE_PUBLIC_KEY/SECRET_KEY 설정 필요")

    sink = LangfuseSink(settings=settings)
    assert sink.configured is True

    # 기록은 예외 없이 끝나야 한다(전송은 백그라운드 배치).
    sink.record(_sample_fields())

    # 실제 클라이언트를 꺼내 flush로 배치를 강제 전송한다(인증·네트워크 검증).
    # auth_check()가 있으면 키 유효성도 확인한다(라이브러리 버전별 가용).
    client = sink._get_client()
    assert client is not None
    auth_check = getattr(client, "auth_check", None)
    if callable(auth_check):
        assert auth_check() is True, "Langfuse 인증 실패 — 키 확인"
    flush = getattr(client, "flush", None)
    if callable(flush):
        flush()  # 미전송 배치를 동기 전송. 네트워크 오류면 여기서 드러난다.


def test_record_never_raises_with_bad_keys_on_live_path() -> None:
    """잘못된 키로 실제 클라이언트를 만들어도 record()는 예외를 던지지 않는다.

    never-break 보장(CLAUDE.md 우선순위 #1 ≫ #6)의 라이브 검증: 인증 실패가
    학생 생성을 깨면 안 된다. 가짜 키라도 *real* langfuse 클라이언트가 생성되며,
    전송 오류는 백그라운드에서 흡수되고 record()는 조용히 반환해야 한다.
    """
    bad = Settings(
        langfuse_public_key="pk-invalid-xxxxx",
        langfuse_secret_key=SecretStr("sk-invalid-xxxxx"),
        langfuse_host="https://cloud.langfuse.com",
    )
    sink = LangfuseSink(settings=bad)
    assert sink.configured is True
    # 예외가 새어나오면 실패. 잘못된 키여도 생성은 비차단이어야 한다.
    sink.record(_sample_fields())
