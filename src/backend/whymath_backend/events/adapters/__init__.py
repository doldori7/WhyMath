"""EOS Education Event 외부 표준 Adapter.

- xAPI (Experience API / Tin Can API)
- Caliper Analytics 1.2
- CloudEvents 1.0

모든 adapter는 EOS Canonical Education Event를 입력으로 받아 외부 표준 형식으로
변환한다. 역방향(외부 → EOS)은 현재 지원하지 않는다.
"""

from whymath_backend.events.adapters.caliper import to_caliper
from whymath_backend.events.adapters.cloudevents import to_cloudevents
from whymath_backend.events.adapters.xapi import to_xapi

__all__ = ["to_xapi", "to_caliper", "to_cloudevents"]
