"""L4 LTHC — Low Threshold High Ceiling 적응.

스펙 §"LTHC"(L117-119) "NRICH 원칙. 동일 task를 학생 수준에 맞춰 진입점·확장 조정".
범위: 단계·숙달도 → 진입점/확장/비계 후보 결정. L2 학습자 모델 연계·LLM 동적 변형은 후속.
"""

from __future__ import annotations

from whymath_backend.l4.lthc.adapt import adapt_lthc
from whymath_backend.l4.lthc.models import LthcAdaptation, MasteryLevel

__all__ = ["LthcAdaptation", "MasteryLevel", "adapt_lthc"]
