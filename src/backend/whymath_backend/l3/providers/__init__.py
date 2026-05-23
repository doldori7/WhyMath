"""L3 LLM 백엔드 구현 — interfaces.LLMProvider Protocol의 실제 구현체.

범위 메모 (M1.2-live): S1이 로컬(Ollama) 구현을, S5가 클라우드(Anthropic Claude)
구현 + 로컬↔클라우드 디스패처(CompositeProvider)를 추가했다(03a §H 후속 4 클라우드 연동).
OpenAI 등 추가 클라우드 제공자는 후속에서 같은 패턴으로 붙인다.
"""

from whymath_backend.l3.providers.anthropic import (
    AnthropicProvider,
    AnthropicStatus,
)
from whymath_backend.l3.providers.composite import CompositeProvider
from whymath_backend.l3.providers.ollama import (
    ModelAvailability,
    OllamaProvider,
    OllamaStatus,
)

__all__ = [
    "AnthropicProvider",
    "AnthropicStatus",
    "CompositeProvider",
    "ModelAvailability",
    "OllamaProvider",
    "OllamaStatus",
]
