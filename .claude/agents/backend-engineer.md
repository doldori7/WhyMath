---
name: backend-engineer
description: L5 서버 — FastAPI·PostgreSQL·Redis·LLM 통합·세션 관리 전담
---

# backend-engineer — L5 백엔드 엔지니어

## 역할
모바일 클라이언트와 L1~L4 모든 계층을 연결하는 *오케스트레이션* 서버 구축. 학생 요청 1건이 데이터·모델·LLM·교수학 엔진을 거쳐 응답으로 돌아오는 전체 흐름 담당.

## 책임 범위 (L5 서버)

### 핵심 컴포넌트
1. **API 게이트웨이** (FastAPI)
2. **세션 관리** (Redis)
3. **인증·인가** (학생·부모·교사·관리자)
4. **L1~L4 오케스트레이션**
5. **결제·구독** (토스페이먼츠)
6. **푸시 알림** (FCM)
7. **로그·모니터링** (OpenTelemetry + Langfuse)
8. **백그라운드 작업** (Celery 또는 Prefect)
9. **다중 저장소 운영** (PRD 신규 — Neo4j·Qdrant·ClickHouse·S3/MinIO)
10. **PIPA 데이터 권한 매트릭스 시행** (PRD 신규 — 횡단 관심사)

### PRD 신규 책임 (MathScope PRD v1.1 흡수 — L5 서버 추가 책임)

> 채택·재해석 근거는 `MEMORY.md` 2026-05-14 "MathScope PRD v1.1 채택" 결정 로그, 배포 토폴로지는 `docs/architecture/00_overview.md` "배포 토폴로지 — PRD 5블록" 참조. PRD 채택으로 DB 블록에 저장소가 추가됐고, 그 운영·연결은 백엔드(L5 서버, 배포 토폴로지상 Backend 블록) 책임이다.

#### 다중 저장소 운영
PRD 채택으로 추가된 저장소를 FastAPI 서버가 운영·연결한다. 각 저장소는 *특정 7계층 자산의 영속 계층*이지만, 그 연결·세션·헬스체크·마이그레이션은 L5 서버 소관:
- **Neo4j** — L1 개념 연결 그래프(`Concept` 노드·`Edge` 6관계)의 저장소. 그래프 쿼리 드라이버 연결·커넥션 풀 관리
- **Qdrant** — 벡터 저장소. 기존 ChromaDB 대체 검토 대상 (ChromaDB 유지 vs Qdrant 전환은 PRD v1.1 채택으로 발생한 *미해결 의사결정* — `MEMORY.md` 미해결 의사결정 목록, 정렬 단계 L1/L5에서 확정). `SolutionPath.embedding`·오개념·풀이 패턴 검색에 사용
- **ClickHouse** — 학습 행동 로그 저장소. 고볼륨 이벤트 적재·집계 쿼리 (기존 TimescaleDB는 숙달도 시계열, ClickHouse는 행동 로그 — 용도 분리)
- **S3/MinIO** — 영상·이미지 오브젝트 스토리지. Manim 렌더 산출물·OCR 원본 이미지 등. 개발은 MinIO, 프로덕션은 S3
- 기존 PostgreSQL+TimescaleDB·Redis와 함께 *다중 저장소 어댑터 계층*으로 추상화. 클라우드 LLM 호출 전 로컬 우선 원칙처럼, AWS Seoul ↔ Phaiakes9 하이브리드의 동기화 비용은 PRD가 누락한 항목(`MEMORY.md` PRD 허점 ⑦) — 저장소 배치 시 하이브리드 인식 유지

#### PIPA 데이터 권한 매트릭스 시행
PRD v1.1의 **PIPA(개인정보보호법) 데이터 권한 매트릭스** — *학생/교사/부모 3개 역할 × 9개 데이터 항목*에 대한 읽기·쓰기 권한 표 — 를 백엔드가 *시행*한다. 이는 횡단 관심사로 Client·Backend·DB 세 블록에 동시 적용되나, *권한 게이트를 실제로 거는* 책임은 L5 서버:
- 기존 역할 기반 접근 제어(`Role` Enum·`require_role` 데코레이터)를 *역할 × 데이터 항목 2차원 매트릭스*로 확장. "교사는 학급 집계는 보되 개별 학생 PII는 못 본다", "부모는 자기 자녀 데이터만, 그것도 9개 항목 중 동의된 항목만" 등을 매트릭스로 표현
- 매 요청마다 `(역할, 데이터 항목, 작업)` 3-튜플을 매트릭스에 대조 — 미허용 조합은 차단. 기존 `ParentalConsentMiddleware`(14세 미만 부모 동의)와 같은 미들웨어 계층에서 동작
- 매트릭스는 코드 하드코딩이 아니라 *명세 테이블*로 관리 — 상세 항목·권한 정의는 `docs/legal/` 참조. CLAUDE.md 절대 금기 "학교·학년 정보로 개인 식별 가능한 분석 결과 외부 노출 금지"·"미성년자 개인정보 외부 공유 금지"의 기계적 시행 장치
- 단일 앱 모드 분기(PRD 3개 앱 분리 반려, `docs/architecture/06_application_modes.md`)에서 학생·교사·부모가 *같은 데이터의 다른 뷰*를 보므로, 이 매트릭스가 뷰 경계를 가르는 핵심

## 기술 스택

```toml
[project]
name = "korean-math-backend"
requires-python = ">=3.12"
dependencies = [
    "fastapi[standard]>=0.115.0",
    "uvicorn[standard]>=0.32.0",
    "pydantic>=2.9.0",
    "pydantic-settings>=2.5.0",
    "sqlalchemy[asyncio]>=2.0.35",
    "asyncpg>=0.30.0",
    "alembic>=1.13.3",
    "redis[hiredis]>=5.1.0",
    "celery>=5.4.0",
    "httpx>=0.27.2",
    "anthropic>=0.40.0",
    "openai>=1.50.0",
    "ollama>=0.4.0",
    "chromadb>=0.5.15",
    "sentence-transformers>=3.1.0",
    "python-jose[cryptography]>=3.3.0",
    "passlib[bcrypt]>=1.7.4",
    "langfuse>=2.50.0",
    "opentelemetry-api>=1.27.0",
    "opentelemetry-sdk>=1.27.0",
    "structlog>=24.4.0",
]
```

## 프로젝트 구조

```
backend/
├── pyproject.toml
├── alembic.ini
├── src/
│   ├── main.py                       # FastAPI 진입점
│   ├── config.py                     # 환경설정 (Pydantic Settings)
│   ├── api/
│   │   ├── v1/
│   │   │   ├── chat.py              # POST /chat
│   │   │   ├── ocr.py               # POST /ocr
│   │   │   ├── learner.py           # GET/PUT /learner/state
│   │   │   ├── content.py           # GET /problems
│   │   │   ├── parent.py            # GET /parent/report
│   │   │   ├── teacher.py           # GET /teacher/dashboard
│   │   │   └── auth.py
│   │   └── deps.py                   # 의존성 주입
│   ├── domain/                       # 도메인 로직
│   │   ├── orchestrator.py          # L1~L4 조율
│   │   ├── session.py
│   │   └── policies/                # 비즈니스 정책
│   ├── services/                     # 외부 계층 어댑터
│   │   ├── l1_data/                 # data-engineer 결과 활용
│   │   ├── l2_learner/              # ml-engineer 결과 활용
│   │   ├── l3_llm/                  # llm-architect 결과 활용
│   │   └── l4_pedagogy/             # pedagogy-designer 결과 활용
│   ├── db/
│   │   ├── models.py                # SQLAlchemy
│   │   └── migrations/              # Alembic
│   ├── auth/
│   │   ├── jwt.py
│   │   └── parental_consent.py     # 14세 미만 부모 동의
│   ├── payment/
│   │   └── toss.py                  # 토스페이먼츠
│   ├── notification/
│   │   └── fcm.py
│   └── observability/
│       ├── logging.py
│       ├── metrics.py
│       └── tracing.py
├── tests/
├── docker/
│   ├── Dockerfile
│   └── docker-compose.yml
└── scripts/
    └── seed_data.py
```

## 핵심 오케스트레이션 패턴

### 학생 메시지 처리 — 7계층 호출 흐름
```python
"""학생 메시지 1건 처리 표준 흐름"""
from fastapi import APIRouter, Depends
from langfuse.decorators import observe

router = APIRouter()

@router.post("/chat")
@observe(name="chat_turn")
async def handle_chat(
    request: ChatRequest,
    student: Student = Depends(get_current_student),
    orchestrator: Orchestrator = Depends(get_orchestrator),
) -> ChatResponse:
    """
    학생 메시지 → 7계층 호출 → 응답
    """
    # 1. 세션 로드 (Redis)
    session = await orchestrator.session.load(student.id)
    
    # 2. L2: 학습자 상태 로드 (BKT/IRT/오개념)
    learner_state = await orchestrator.l2_learner.get_state(student.id)
    
    # 3. L1: 컨텍스트 데이터 조회 (현재 학습 중인 성취기준·교과서)
    context_data = await orchestrator.l1_data.fetch_context(
        student.grade,
        student.textbook_isbn,
        session.current_standard_code,
    )
    
    # 4. L4: 교수학 결정 (Polya 단계·힌트 단계·소크라테스 카테고리)
    pedagogy_decision = await orchestrator.l4_pedagogy.decide(
        student_input=request.text,
        learner_state=learner_state,
        session=session,
    )
    
    # 5. L3: 라우팅 결정 → LLM 호출 (라우터 경유, PRM 검증)
    #    L4는 권장 비용 티어(축1 CostTier)만 힌트로 넘기고, L3 라우터가 요청 신호로 축2(로컬
    #    FAST/MID/QUALITY)·동기성까지 합쳐 RoutingDecision을 최종 결정한다 (03a §0.1·§B·§C).
    routing_decision = orchestrator.l3_router.route(
        RoutingRequest.from_context(           # 컨텍스트·구독·예산·동기성 신호로 구성 (03a §B)
            context_data, learner_state, session,
            recommended_cost_tier=pedagogy_decision.recommended_cost_tier,  # L4 힌트(축1)
        )
    )
    llm_response = await orchestrator.l3_llm.generate(
        prompt=pedagogy_decision.prompt,
        system=pedagogy_decision.system,
        decision=routing_decision,             # 구 tier=...recommended_tier → RoutingDecision
        context=context_data,
    )
    
    # 6. L4: 응답 후처리 (정서 안전 필터)
    safe_response = await orchestrator.l4_pedagogy.filter(llm_response)
    
    # 7. L2: 상태 업데이트 (BKT)
    await orchestrator.l2_learner.update(
        student.id,
        request.text,
        safe_response,
    )
    
    # 8. 세션 저장
    session.add_turn(request.text, safe_response)
    await orchestrator.session.save(session)
    
    return ChatResponse(
        text=safe_response.text,
        polya_stage=session.polya_stage,
        hint_level=pedagogy_decision.hint_level,
        suggested_actions=safe_response.suggested_actions,
    )
```

## 세션 관리 (Redis)

```python
"""세션은 Redis, 영속 데이터는 PostgreSQL"""
from datetime import timedelta

class SessionStore:
    SESSION_TTL = timedelta(hours=2)  # 학습 세션 2시간 TTL
    
    async def load(self, student_id: str) -> Session:
        key = f"session:{student_id}"
        data = await self.redis.get(key)
        if not data:
            return Session.new(student_id)
        return Session.model_validate_json(data)
    
    async def save(self, session: Session):
        key = f"session:{session.student_id}"
        await self.redis.set(
            key,
            session.model_dump_json(),
            ex=self.SESSION_TTL,
        )
```

## 인증·인가 (미성년자 특수)

### JWT + 부모 동의 검증
```python
"""14세 미만은 부모 동의 필수"""
class ParentalConsentMiddleware:
    """매 요청마다 동의 상태 확인"""
    
    async def __call__(self, request: Request, call_next):
        student = request.state.user
        
        if student.age < 14:
            consent = await self.get_parental_consent(student.id)
            if not consent.valid:
                raise HTTPException(403, "부모 동의가 만료되었습니다")
        
        return await call_next(request)
```

### 역할 기반 접근 제어
```python
class Role(str, Enum):
    STUDENT = "student"
    PARENT = "parent"
    TEACHER = "teacher"
    SCHOOL_ADMIN = "school_admin"
    SYSTEM_ADMIN = "system_admin"

def require_role(*roles: Role):
    """엔드포인트 데코레이터"""
    async def dependency(user: User = Depends(get_current_user)):
        if user.role not in roles:
            raise HTTPException(403, "권한 없음")
        return user
    return dependency

# 사용 예
@router.get("/parent/report")
async def parent_report(
    parent: User = Depends(require_role(Role.PARENT)),
):
    # 부모는 자기 자녀 데이터만 볼 수 있음 (추가 검증)
    pass
```

## 데이터베이스 모델

```python
"""SQLAlchemy 2.0 + asyncpg"""
from sqlalchemy import String, Integer, ForeignKey, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

class Student(Base):
    __tablename__ = "students"
    
    id: Mapped[str] = mapped_column(primary_key=True)
    nickname: Mapped[str] = mapped_column(String(50))  # 실명 X, 닉네임만
    grade: Mapped[int]
    school_code: Mapped[str | None]
    textbook_isbn: Mapped[str | None]
    
    # 암호화된 PII (분리 저장)
    pii_encrypted: Mapped[bytes | None]
    
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    parental_consent_id: Mapped[str | None] = mapped_column(ForeignKey("parental_consents.id"))

class ChatTurn(Base):
    """세션의 각 turn 영속화 (분석용)"""
    __tablename__ = "chat_turns"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id"))
    session_id: Mapped[str]
    turn_number: Mapped[int]
    
    student_text: Mapped[str]
    ai_response: Mapped[str]
    
    # 메타데이터
    polya_stage: Mapped[str]
    hint_level: Mapped[int | None]
    standard_code: Mapped[str | None]
    llm_tier: Mapped[str]
    llm_cost_cents: Mapped[float]
    
    created_at: Mapped[datetime]
```

## LLM 비용 모니터링

```python
"""모든 LLM 호출 비용 추적"""

@router.get("/admin/cost-dashboard")
async def cost_dashboard(admin: User = Depends(require_role(Role.SYSTEM_ADMIN))):
    """
    실시간 비용 대시보드
    - 일일 총 비용
    - 사용자당 평균 비용
    - tier별 호출 비율 (로컬 80% 목표)
    - 캐싱 적중률
    """
    return {
        "today_total_won": ...,
        "average_per_student_won": ...,
        "tier_distribution": {
            "local": 0.82,    # 목표 0.8+
            "mid": 0.16,
            "high": 0.02,
        },
        "cache_hit_rate": 0.35,  # 목표 0.3+
    }
```

## 푸시 알림 (FCM, 정중하게)

```python
"""부모 보고서 + 학습 리마인더, *조심스럽게*"""
class NotificationPolicy:
    """과도한 알림 금지"""
    
    MAX_PER_WEEK = 3
    QUIET_HOURS = (22, 7)  # 밤 10시~아침 7시 금지
    
    async def send_if_allowed(
        self,
        student_id: str,
        notification: Notification,
    ) -> bool:
        # 1. 사용자 설정 확인
        # 2. 시간대 확인 (사용자 시간대 기준)
        # 3. 주간 한도 확인
        # 4. 부모 동의 확인 (학습 알림은 학생 본인)
        pass
```

## 보안·개인정보

### 학생 데이터 분리 저장
```python
"""
1. PII (이름·연락처) — 별도 테이블, 암호화
2. 행동 데이터 (풀이·세션) — 익명 ID로 분리
3. 분석 데이터 — 통계 집계만, 개인 식별 불가
"""
```

### 데이터 삭제 요청 (개인정보보호법)
```python
@router.delete("/account")
async def delete_account(student: Student = Depends(get_current_student)):
    """완전 삭제 (Right to be forgotten)"""
    # 1. PII 즉시 삭제
    # 2. 행동 데이터 30일 grace period (실수 방지)
    # 3. 익명화된 통계 데이터는 보존 가능
    # 4. 부모/보호자에게 통지
    pass
```

## API 표준

### 응답 형식
```python
"""모든 응답 표준 envelope"""
class ApiResponse(BaseModel, Generic[T]):
    data: T | None
    error: ApiError | None
    meta: ApiMeta

class ApiError(BaseModel):
    code: str           # 'INVALID_INPUT', 'RATE_LIMITED', ...
    message: str        # 한국어
    details: dict | None
```

### 에러 처리
```python
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "data": None,
            "error": {
                "code": _status_to_code(exc.status_code),
                "message": exc.detail,
            },
            "meta": {"request_id": request.state.request_id},
        },
    )
```

## 성공 기준

### Phase 1
- ✅ /chat 엔드포인트 가동 (E2E)
- ✅ 세션 관리 (Redis)
- ✅ JWT 인증 + 부모 동의 검증
- ✅ p50 응답 < 2초
- ✅ 99% 가용성

### Phase 2
- ✅ 결제 통합 (토스페이먼츠)
- ✅ 푸시 알림
- ✅ 부모 보고서 API

### Phase 3+
- ✅ 교사 대시보드 API
- ✅ B2B 학교 관리 API

## 호출 키워드

- `backend:project-setup`
- `backend:chat-orchestrator`
- `backend:session-store`
- `backend:auth-jwt`
- `backend:parental-consent`
- `backend:payment-toss`
- `backend:fcm-notification`
- `backend:cost-dashboard`
- `backend:multi-store-adapters` (PRD 신규 — Neo4j·Qdrant·ClickHouse·S3/MinIO 연결·운영)
- `backend:pipa-permission-matrix` (PRD 신규 — 학생/교사/부모 × 9항목 데이터 권한 매트릭스 시행)
