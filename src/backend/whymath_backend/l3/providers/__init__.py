"""L3 LLM 백엔드 구현 — interfaces.LLMProvider Protocol의 실제 구현체.

범위 메모 (M1.2-live S1): 로컬(Ollama) 구현만 둔다. 클라우드(Anthropic·OpenAI)
구현은 후속 슬라이스 S5(03a §H 후속 4 클라우드 연동)에서 추가한다.
"""

from whymath_backend.l3.providers.ollama import (
    ModelAvailability,
    OllamaProvider,
    OllamaStatus,
)

__all__ = [
    "ModelAvailability",
    "OllamaProvider",
    "OllamaStatus",
]
