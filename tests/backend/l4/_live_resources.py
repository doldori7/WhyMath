"""라이브 자원 도달성 사전체크 — 미도달이면 skip, 코드 버그는 fail로 전파 (슬110·리뷰 #5).

종전 bge-m3 통합 테스트는 `except Exception: pytest.skip(...)`로 *자원 미도달*(HF 429·
네트워크)뿐 아니라 *코드 버그*(TypeError·AttributeError 등)까지 skip으로 은폐했다 — 통합
테스트가 영원히 green-by-skip이 될 위험. 형제 통합(`l3/test_ollama_integration.py`의
`status.reachable` 사전체크·`api/test_rate_limit_integration.py`의 Redis ping)의 **도달성
사전체크** 패턴을 미러해, *자원 미도달만* skip하고 본 테스트의 코드 버그는 fail로 드러낸다.
"""

from __future__ import annotations

import importlib.util

import pytest


def require_local_embedding() -> None:
    """bge-m3(sentence-transformers) 라이브 가용성 사전체크 — 미도달이면 skip.

    ① `sentence_transformers` 미설치(슬110 #6: `[embedding]` extra 미설치 환경) → skip.
    ② 첫 embed로 HF 가중치 도달을 확인하되, *자원 예외*(`OSError`=HF 다운로드/네트워크·
       requests 예외는 OSError 하위·`ImportError`=torch 등 전이 의존 미설치)만 skip한다.
       `TypeError`·`AssertionError`·`KeyError`·`ValueError` 등 *코드 버그*는 잡지 않아
       호출 테스트에서 fail로 드러난다. embed 성공 시 가중치가 디스크 캐시돼 후속 호출은
       재다운로드 없이 같은 가중치를 쓴다(호출 테스트는 try/except 불요).
    """
    if importlib.util.find_spec("sentence_transformers") is None:
        pytest.skip("sentence-transformers 미설치([embedding] extra) — bge-m3 라이브 skip")
    from whymath_backend.l4.misconception.semantic.provider import LocalEmbeddingProvider

    try:
        LocalEmbeddingProvider().embed(["도달 확인"])
    except (OSError, ImportError) as exc:
        pytest.skip(f"bge-m3 가중치 미도달(HF/네트워크/전이 의존) — 라이브 skip: {exc}")


async def require_ollama_reachable() -> None:
    """로컬 Ollama 데몬 도달성 사전체크 — 미도달이면 skip (judge 라이브 측정 전제).

    `OllamaProvider.check_status()`는 데몬 미도달을 예외 흡수→`reachable=False`로 보고한다
    (비크래시). `l3/test_ollama_integration.py`의 사전체크 패턴을 그대로 미러. LLMJudge는
    Ollama 미도달 시 UNCERTAIN으로 never-break 폴백하므로, 사전체크 없이 돌리면 judge가
    *아무 일도 안 하는* 무의미한 측정이 된다 — 그래서 측정 전 명시 skip한다.
    """
    from whymath_backend.config import Settings
    from whymath_backend.l3.providers.ollama import OllamaProvider

    status = await OllamaProvider(settings=Settings()).check_status()
    if not status.reachable:
        pytest.skip(f"Ollama 미도달({status.error}) — judge 라이브 측정 skip")
