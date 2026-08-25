"""EOS 204 Education Event System — SDK + adapters.

`whymath_backend.events.sdk.EducationEventSDK`를 통해 교육 이벤트를 생성하고,
`whymath_backend.events.adapters`를 통해 xAPI/Caliper/CloudEvents로 변환한다.
"""

from whymath_backend.events.sdk import EducationEventSDK, emit_education_event

__all__ = ["EducationEventSDK", "emit_education_event"]
