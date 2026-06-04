"""WhyMath HTTP API 라우터 — DB 영속 레이어를 노출하는 FastAPI APIRouter 모음.

`app.create_app()`이 여기 라우터를 include한다. L3 생성 표면(app.py 인라인 엔드포인트)과
달리, 이 패키지의 라우터는 `db.session.get_session` 의존성으로 PostgreSQL을 읽고 쓴다 —
즉 영속 레이어(ORM·마이그레이션)를 HTTP 표면까지 end-to-end로 잇는 결선이다.

경계 메모(CLAUDE.md): 여기 노출되는 것은 *구조 데이터*(개념·문제 메타)이며, 검정교과서·
EBS·평가원 본문은 담지 않는다(자체 동등 콘텐츠만). 학생 표면화 전 LLM 생성물은 L3/app.py가
다루고, 이 라우터는 검증된 영속 엔티티의 CRUD-read만 책임진다.
"""

from __future__ import annotations

from whymath_backend.api.coach import router as coach_router
from whymath_backend.api.concepts import router as concepts_router
from whymath_backend.api.devices import router as devices_router
from whymath_backend.api.me import router as me_router
from whymath_backend.api.problems import router as problems_router
from whymath_backend.api.users import router as users_router

__all__ = [
    "coach_router",
    "concepts_router",
    "devices_router",
    "me_router",
    "problems_router",
    "users_router",
]
