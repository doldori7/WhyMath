"""L3 관측성 싱크 구현 — interfaces.TraceSink Protocol의 실제 구현체.

범위 메모 (M1.2-live S3): Langfuse 구현만 둔다. 인메모리 스텁(RecordingTraceSink)은
테스트용으로 interfaces.py에 그대로 남는다(완벽한 hermetic 테스트 더블 — cache 패키지가
InMemoryCache를 interfaces.py에 남긴 것과 동일). OpenTelemetry 트레이싱·메트릭 등
추가 관측 백엔드는 후속 슬라이스 범위다.
"""

from whymath_backend.l3.trace.langfuse_sink import LangfuseSink

__all__ = [
    "LangfuseSink",
]
