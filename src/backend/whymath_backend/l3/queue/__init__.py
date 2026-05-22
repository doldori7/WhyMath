"""L3 비동기 작업 큐 — QUALITY(27b) 전용 Celery 큐 (M1.2-live S4).

QUALITY(qwen3.5:27b)는 동기 호출이 금지된다(p50≈14초·GPU 단일 점유 → 병렬 미작동,
03a §D.3·§A.1). 이 패키지가 그 *비동기 경로*를 구현한다:
  - `celery_app.build_celery_app()` — broker=result backend=Redis인 Celery 앱(지연 생성).
  - `tasks.run_quality_generation` — 워커에서 OllamaProvider로 QUALITY를 실행하는 태스크.
  - `CeleryJobQueue` — interfaces.AsyncJobQueue 구현. enqueue→job_id 반환, result()로 폴링.

범위 메모: 인메모리 큐 더블은 *테스트 쪽*에 둔다(cache 패키지가 InMemoryCache를,
trace 패키지가 RecordingTraceSink를 interfaces.py에 남긴 것과 동일한 분리 — 여기서는
실제 Celery 구현만 노출한다). 큐 SLA·재시도·DLQ 정책은 후속 슬라이스 범위(03a §H 후속 6).
"""

from whymath_backend.l3.queue.celery_job_queue import CeleryJobQueue, JobStatus

__all__ = [
    "CeleryJobQueue",
    "JobStatus",
]
