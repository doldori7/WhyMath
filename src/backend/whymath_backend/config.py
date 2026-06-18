"""백엔드 환경설정 — pydantic-settings 기반 (CLAUDE.md 보안 금기: 시크릿 하드코딩 금지).

모든 설정은 *환경변수*로 주입한다. 이 파일에는 호스트·시크릿을 하드코딩하지 않으며
기본값은 *로컬 개발용 무해 디폴트*(예: Ollama 로컬 데몬 주소)만 둔다.

범위 메모 (M1.2-live): S1은 L3 라우터 ↔ 실제 Ollama 결선 + FastAPI 앱을 다뤘고,
S2가 Redis 캐시 설정(redis_url)을 추가했으며, S3가 Langfuse 관측성 설정(공개키·
시크릿키·호스트)을 추가했고, S4가 QUALITY(27b) 비동기 큐(Celery, broker=Redis)
설정을 추가했으며, S5가 클라우드 LLM(Anthropic Claude — API 키·모델 ID·타임아웃)
설정을 추가한다(03a §H 후속 4 클라우드 연동). DB 설정은 후속 슬라이스에서 추가한다 —
여기서는 가동 중인 슬라이스에 필요한 최소 설정만 노출한다.

시크릿 처리 (CLAUDE.md 보안 금기 "API 키·시크릿 코드 하드코딩 금지"): Langfuse
시크릿 키는 `SecretStr`로 받아 *로그·repr에 평문 노출을 차단*한다. 공개키·시크릿키는
*기본값을 두지 않는다*(빈 문자열 = "미설정") — 키가 없으면 관측성은 영구 no-op으로
스스로 비활성된다(LangfuseSink). 호스트는 무해한 공개 디폴트(cloud.langfuse.com)를
둘 수 있다(시크릿 아님).
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """환경변수 기반 설정 — `WHYMATH_` 접두사 (예: `WHYMATH_OLLAMA_HOST`).

    pydantic-settings가 환경변수·`.env`에서 값을 읽는다. 시크릿은 코드가 아니라
    배포 환경의 환경변수/시크릿 매니저로 주입한다 (CLAUDE.md 보안 금기).
    """

    model_config = SettingsConfigDict(
        env_prefix="WHYMATH_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # 다른 슬라이스(DB·결제 등) 환경변수와 공존 — 모르는 키 무시
    )

    # ── Ollama (로컬 LLM, Phaiakes9) ──
    ollama_host: str = Field(
        default="http://127.0.0.1:11434",
        description=(
            "Ollama 데몬 주소. 로컬 개발 기본값은 무해한 로컬 루프백. "
            "프로덕션(Phaiakes9)은 환경변수 WHYMATH_OLLAMA_HOST로 주입 (시크릿 아님)"
        ),
    )
    ollama_request_timeout_s: float = Field(
        default=30.0,
        ge=0.0,
        description=(
            "Ollama 단일 호출 타임아웃(초). QUALITY(27b, p50≈14s)는 동기 호출하지 "
            "않으므로(03a §D.3) 이 타임아웃은 FAST/MID 동기 경로 기준 (S1 범위)"
        ),
    )

    # ── 영속 DB (PostgreSQL 16 + asyncpg, 영속 슬라이스) ──
    # 영속 레이어(SQLAlchemy 2.0 async + alembic)가 읽는 연결 URL. redis_url과 동일한
    # plain-str + WHYMATH_ env 오버라이드 패턴 — 로컬 기본값은 자격증명 없는 무해 디폴트라
    # 시크릿이 아니다(CLAUDE.md 보안 금기 비저촉). 프로덕션 자격증명은 코드 밖 환경변수로만.
    database_url: str = Field(
        default="postgresql+asyncpg://whymath@127.0.0.1:5432/whymath",
        description=(
            "PostgreSQL 연결 URL(asyncpg 드라이버, async). 로컬 개발 기본값은 자격증명 없는 "
            "무해한 로컬 루프백(시크릿 아님). 프로덕션(Phaiakes9)은 WHYMATH_DATABASE_URL로 "
            "주입하며 자격증명을 포함할 수 있다(→ 코드 밖). 풀 설정(pool_size 등)은 PoC 범위 밖."
        ),
    )
    # 연결 풀 비활성(NullPool). 기본 False(프로덕션은 풀 사용). True면 매 체크아웃마다 새
    # asyncpg 연결을 만들고 닫는다 — *테스트(통합) 환경*에서 모듈 전역 엔진이 여러 asyncio
    # 이벤트 루프에 걸쳐 재사용될 때 발생하는 "another operation is in progress"(죽은 루프에
    # 바인딩된 풀 연결 재사용)를 회피. CI 통합테스트가 WHYMATH_DB_DISABLE_POOL=1로 켠다.
    db_disable_pool: bool = Field(
        default=False,
        description=(
            "True면 NullPool(연결 풀 비활성·매 체크아웃 새 연결). 통합테스트가 다중 이벤트 "
            "루프에서 전역 엔진을 재사용할 때의 asyncpg 루프 바인딩 충돌 회피용. 기본 False."
        ),
    )

    # ── 응답 캐시 (Redis, S2부터 실제 만료 적용) ──
    redis_url: str = Field(
        default="redis://127.0.0.1:6379/0",
        description=(
            "Redis 연결 URL. 로컬 개발 기본값은 무해한 로컬 루프백 DB 0. "
            "프로덕션(Phaiakes9)은 환경변수 WHYMATH_REDIS_URL로 주입. 시크릿 아님 — "
            "인증이 필요하면 URL에 환경변수로 자격증명을 담는다(코드 하드코딩 금지)"
        ),
    )
    cache_ttl_s: int = Field(
        default=3600,
        ge=0,
        description=(
            "응답 캐시 TTL(초). S2 RedisCache가 SET ... EX로 실제 만료 적용(03a §F.1). "
            "0이면 RedisCache는 만료 없이 저장(무기한 폴백 — redis가 EX 0를 거부하므로)"
        ),
    )

    l3_shadow_validation_enabled: bool = Field(
        default=True,
        description=(
            "L3 런타임 shadow 검증(결정론 관계 검증·slice 40~47) 활성 여부. True(기본)면 "
            "/v1/generate 동기 경로와 QUALITY 워커가 생성물의 거짓 수치 관계를 비차단으로 "
            "관측(신호 기록·로그). False면 끈다(SymPy 검증 비용 제거·디버깅). 비차단이라 "
            "반환 텍스트·캐시 동작은 어느 쪽이든 불변 — 관측 신호 유무만 달라진다."
        ),
    )

    l3_skip_cache_on_signal: bool = Field(
        default=False,
        description=(
            "shadow 검증이 환각 신호를 낸 /v1/generate 미스 생성물을 캐시에 적재하지 않을지 "
            "(slice 42 캐시 위생). True면 증명된 거짓 수치 관계 출력을 *영속화하지 않는다* "
            "(다음 동일 요청은 재생성). False(기본)면 기존 동작(항상 적재). `l3_shadow_"
            "validation_enabled`가 False면 신호 자체가 없어 무효과. 반환 텍스트는 불변 "
            "(캐시만 건너뜀)·정확성 무해(false positive 시 재생성 비용만)."
        ),
    )

    l4_step_shadow_enabled: bool = Field(
        default=False,
        description=(
            "L4 중간 step 등가성 shadow 관측(slice 62~63) 활성 여부. True면 /v1/coach 경로가 학생 "
            "풀이의 *단계-비보존*(인접 변환이 해집합을 안 지킴)을 `detect_step_breaks`로 검출해 "
            "logger.info로 관측한다. **student-facing 미노출**(SolutionCoaching·HTTP 응답 불변) — "
            "순차유도 오류(A)와 변수재사용(B)을 구문 분리 못 해 노이즈가 섞이므로 학생엔 안 보이고 "
            "진단 데이터(향후 L7·교사 대시보드)로만 쓴다. **False(기본·opt-in)**: (A)/(B) 노이즈가 "
            "구조적·sink 미구현이라 보수적 off. WHYMATH_L4_STEP_SHADOW_ENABLED=true로 켠다."
        ),
    )

    l4_server_mastery_enabled: bool = Field(
        default=True,
        description=(
            "L4 코칭(세션/턴)이 서버 L2 저장소(ConceptMasteryHistory)의 *실제* 숙달도를 "
            "클라이언트 전송 bkt_mastery보다 우선해 쓸지(slice 70·진짜 L2↔L4 루프). "
            "True(기본·정식기능)면 /v1/coach/sessions·turns가 문항 PRIMARY 개념의 현재 "
            "숙달도를 조회해 hint level 보수화·LTHC 조정에 반영한다(클라 전송값 변조·단절 제거). "
            "명시 mastery_level(라벨)은 여전히 최우선. **student-facing 미노출**(결정에만 쓰고 "
            "decision/CoachResponse 불변). stateless /v1/coach는 DB가 없어 무관(클라값). "
            "False면 기존 동작(클라 bkt만). WHYMATH_L4_SERVER_MASTERY_ENABLED=false로 끈다."
        ),
    )

    l4_server_theta_enabled: bool = Field(
        default=True,
        description=(
            "L4 코칭(세션/턴)이 서버 L2 저장소(AbilitySnapshot)의 *실제* IRT 능력 θ를 조회해 "
            "BKT↔θ 교차검증 코칭(slice 73)에 쓸지. True(기본·정식기능)면 /v1/coach/sessions·"
            "turns가 학생의 최신 전과목 θ를 조회해, BKT 숙달과 *불일치*할 때(θ↑·BKT↓=추측 의심 "
            "→ consolidate·BKT↑·θ↓=망각 의심 → retrieval) `solution_coaching`으로 메타인지 "
            "코칭을 노출한다. **θ 수치는 student-facing 미노출**(결정에만 쓰고 노출되는 건 정성 "
            "코칭 발화뿐). θ 스냅샷이 없거나(희소) False면 교차검증 불가 → diagnose → 비노출"
            "(기존 동작). WHYMATH_L4_SERVER_THETA_ENABLED=false로 끈다."
        ),
    )
    l4_theta_min_responses: int = Field(
        default=3,
        ge=0,
        description=(
            "개념별 θ를 코칭 BKT↔θ 교차검증에 *쓰기 위한* 최소 응답수(slice 76 노이즈 가드). "
            "개념 θ 스냅샷의 response_count가 이 미만이면(응답 1~2개의 극단 θ=±4 등) 신뢰하지 "
            "않고 전과목 θ로 폴백한다. 0이면 응답수 게이트 사실상 해제. "
            "WHYMATH_L4_THETA_MIN_RESPONSES로 조정."
        ),
    )
    l4_theta_max_se: float = Field(
        default=1.0,
        gt=0.0,
        description=(
            "개념별 θ를 신뢰할 표준오차(SE) 상한(slice 76 노이즈 가드). 개념 θ의 SE가 이 초과거나 "
            "측정 불가(SE 없음·정보 0의 극단 θ)면 전과목 θ로 폴백한다. 크게 두면 SE 게이트 완화. "
            "WHYMATH_L4_THETA_MAX_SE로 조정."
        ),
    )

    # ── QUALITY(27b) 비동기 큐 (Celery, broker=result backend=Redis, S4) ──
    # QUALITY는 동기 호출 불가(p50≈14초·GPU 단일 점유, 03a §D.3) → 작업 큐 전용이다.
    # broker·result-backend는 *기본값을 두지 않고*(빈 = "redis_url에서 파생") 명시
    # 오버라이드가 없으면 redis_url을 그대로 재사용한다(아래 celery_* property).
    # 별도 환경변수로 분리 인프라(전용 broker DB 등)를 가리키게 할 수 있다.
    celery_broker_url: str = Field(
        default="",
        description=(
            "Celery broker URL. 빈 값(기본)이면 redis_url을 재사용한다(단일 Redis로 "
            "캐시+큐 운영). 전용 broker로 분리하려면 WHYMATH_CELERY_BROKER_URL로 주입. "
            "시크릿 아님 — 인증이 필요하면 URL에 환경변수로 자격증명을 담는다(하드코딩 금지)."
        ),
    )
    celery_result_backend: str = Field(
        default="",
        description=(
            "Celery result backend URL. 빈 값(기본)이면 redis_url을 재사용한다. "
            "job_id로 QUALITY 결과를 폴링하려면 result backend가 필요하다(03a §D.3 폴링). "
            "분리하려면 WHYMATH_CELERY_RESULT_BACKEND로 주입."
        ),
    )

    # ── 관측성 (Langfuse, S3부터 실제 전송) ──
    # 시크릿: 공개키·시크릿키는 *기본값 없음*(빈 = 미설정). 둘 다 채워져야 LangfuseSink가
    # 활성화되고, 하나라도 비면 영구 no-op(03a §F.2 관측성은 best-effort). 시크릿 키는
    # SecretStr로 평문 repr/로그 노출을 차단한다(CLAUDE.md 보안 금기).
    langfuse_public_key: str = Field(
        default="",
        description=(
            "Langfuse 공개키(pk-...). 기본값 없음(빈 = 미설정). 환경변수 "
            "WHYMATH_LANGFUSE_PUBLIC_KEY로 주입. 비면 관측성은 영구 no-op으로 비활성."
        ),
    )
    langfuse_secret_key: SecretStr = Field(
        default=SecretStr(""),
        description=(
            "Langfuse 시크릿키(sk-...). SecretStr — repr/로그에 평문 노출 안 됨. "
            "기본값 없음(빈 = 미설정). 환경변수 WHYMATH_LANGFUSE_SECRET_KEY로만 주입 "
            "(CLAUDE.md 보안 금기: 코드 하드코딩 금지). 비면 관측성 no-op."
        ),
    )
    langfuse_host: str = Field(
        default="https://cloud.langfuse.com",
        description=(
            "Langfuse 호스트 URL. 무해한 공개 디폴트(클라우드). 셀프호스트는 환경변수 "
            "WHYMATH_LANGFUSE_HOST로 주입. 시크릿 아님 — 호스트만으로는 전송 불가(키 필요)."
        ),
    )

    # ── 클라우드 LLM (Anthropic Claude, S5 — 03a §C.1·§A.0 CLOUD_MID/HIGH 경로) ──
    # 라우터가 내리는 CLOUD_MID(Sonnet)·CLOUD_HIGH(Opus) 결정을 실제 생성으로 잇는다.
    # API 키는 *기본값 없음*(빈 = 미설정) — 키가 없으면 AnthropicProvider는 클라우드
    # 결정에 대해 명확한 오류를 던지고(조용한 강등 금지), /status는 cloud_configured=
    # False로 보고한다. 모델 ID는 alias 기본값(env 오버라이드 가능, 03a §H 후속 4).
    anthropic_api_key: SecretStr = Field(
        default=SecretStr(""),
        description=(
            "Anthropic API 키(sk-ant-...). SecretStr — repr/로그에 평문 노출 안 됨. "
            "기본값 없음(빈 = 미설정). 환경변수 WHYMATH_ANTHROPIC_API_KEY로만 주입 "
            "(CLAUDE.md 보안 금기: 코드 하드코딩 금지). 비면 클라우드 생성 불가."
        ),
    )
    anthropic_model_mid: str = Field(
        default="claude-sonnet-4-6",
        description=(
            "CLOUD_MID 티어 모델 ID(축1, 03a §A.0). 기본 Claude Sonnet 4.6 alias. "
            "환경변수 WHYMATH_ANTHROPIC_MODEL_MID로 핀/오버라이드. 시크릿 아님."
        ),
    )
    anthropic_model_high: str = Field(
        default="claude-opus-4-7",
        description=(
            "CLOUD_HIGH 티어 모델 ID(축1, 03a §A.0). 기본 Claude Opus 4.7 alias. "
            "환경변수 WHYMATH_ANTHROPIC_MODEL_HIGH로 핀/오버라이드. 시크릿 아님."
        ),
    )
    anthropic_max_tokens: int = Field(
        default=16000,
        ge=1,
        description=(
            "Anthropic messages.create의 max_tokens(필수 인자). 비스트리밍 동기 호출 "
            "기준 안전 기본값(SDK ~10분 타임아웃 가드 미만). WHYMATH_ANTHROPIC_MAX_TOKENS로 조정."
        ),
    )
    anthropic_request_timeout_s: float = Field(
        default=60.0,
        ge=0.0,
        description=(
            "Anthropic 단일 호출 타임아웃(초). 클라우드는 동기 경로(03a §C.4 mode=sync). "
            "ollama_request_timeout_s 미러. WHYMATH_ANTHROPIC_REQUEST_TIMEOUT_S로 조정."
        ),
    )
    # ── 클라우드 품질·비용 튜닝 노브 (전부 기본 OFF = 현 동작 유지, 03a §H 후속 4) ──
    # 최적값은 *라이브 측정* 후에야 정할 수 있어(키 필요·Kiki) 기본은 '생략/끔'이다 —
    # 코드 변경 없이 env로 켜고 튜닝할 수 있게 *배선만* 해 둔다.
    anthropic_effort: str = Field(
        default="",
        description=(
            "클라우드 호출 effort(output_config.effort) — low/medium/high/xhigh/max. "
            "빈 값(기본)이면 *생략*(현 동작 유지). Sonnet 4.6·Opus 4.7만 지원(구형 모델 핀 시 "
            "400 주의). xhigh/max는 max_tokens 상향 권장. 최적값은 라이브 측정 후 "
            "WHYMATH_ANTHROPIC_EFFORT로 설정(03a §H 후속 4)."
        ),
    )
    anthropic_thinking: bool = Field(
        default=False,
        description=(
            "True면 클라우드 호출에 adaptive thinking(thinking={'type':'adaptive'}) 적용. "
            "기본 False(생략, 현 동작 유지) — thinking은 동기 지연·비용을 늘리므로 라이브 측정 "
            "후 WHYMATH_ANTHROPIC_THINKING로 켠다(생성 텍스트는 type=='text' 블록만 사용)."
        ),
    )
    anthropic_prompt_caching: bool = Field(
        default=False,
        description=(
            "True면 messages.create에 top-level cache_control(ephemeral) 적용(prefix 캐시). "
            "기본 False(현 동작 유지) — 적중은 라이브 키로만 검증 가능하고 system 프롬프트가 "
            "L4/L5 미확정이라 효과 잠정. 짧은 프리픽스는 최소 토큰 미만이라 무효(silent no-op)."
        ),
    )

    # ── 인증(JWT 집행 계층, L5) ──
    # UserProfile엔 credential 필드가 없다 — JWT는 sub=user_id만 담는 *집행 토큰*이고, 실제
    # 로그인(카카오/네이버 OAuth, 후속)이 create_access_token을 호출해 발급한다. 시크릿은 코드
    # 하드코딩 금지(anthropic_api_key 패턴) — 비면 토큰 발급/검증이 명확한 오류를 던진다.
    jwt_secret_key: SecretStr = Field(
        default=SecretStr(""),
        description=(
            "JWT 서명 시크릿(HS256). SecretStr — repr/로그 평문 노출 안 됨. 기본값 없음(빈 = "
            "미설정). 환경변수 WHYMATH_JWT_SECRET_KEY로만 주입(하드코딩 금지). 비면 인증 불가."
        ),
    )
    jwt_algorithm: str = Field(
        default="HS256",
        description=(
            "JWT 서명 알고리즘(기본 HS256 대칭). WHYMATH_JWT_ALGORITHM로 오버라이드. 시크릿 아님."
        ),
    )
    jwt_expire_minutes: int = Field(
        default=60 * 24,
        ge=1,
        description="액세스 토큰 만료(분). 기본 24시간. WHYMATH_JWT_EXPIRE_MINUTES로 조정.",
    )
    jwt_refresh_expire_minutes: int = Field(
        default=60 * 24 * 30,  # 30일(security_privacy.md REFRESH_TOKEN_TTL)
        ge=1,
        description="리프레시 토큰 만료(분). 기본 30일. WHYMATH_JWT_REFRESH_EXPIRE_MINUTES로 조정.",
    )

    # ── 미성년 동의 게이트(PIPA 만14세 미만, L5) ──
    # 서버측 `is_minor` 파생의 연령 임계(법정 기준). PIPA는 *만 14세 미만*의 개인정보 처리에
    # 법정대리인 동의를 요구하므로(docs/legal/pipa_data_matrix.md §3) 기본 14다. 이 값은
    # `consent.derive_is_minor`가 birth_year로 `is_minor`를 파생할 때 쓰는 *유일한* 연령 기준
    # 으로, 콜백(가입)·PATCH 양쪽 쓰기 경로가 공유한다(법정 기준 변경 시 한 곳만 바꾼다).
    # birth_year만 수집(월일 미수집)하므로 파생은 *보수적 연나이*다 — 정확한 만나이 게이팅·
    # 동의 GRANT 플로우·동의 재확인 주기는 변호사 자문 후속(pipa_data_matrix.md §3 체크리스트).
    minor_consent_age: int = Field(
        default=14,
        ge=0,
        description=(
            "미성년 동의 게이트 연령 임계(만 나이·법정 기준). PIPA 만14세 미만 법정대리인 동의 "
            "(docs/legal/pipa_data_matrix.md §3) → 기본 14. `consent.derive_is_minor`가 "
            "birth_year로 `is_minor`를 파생할 때의 유일한 기준(가입 콜백·PATCH 공유). 정확한 "
            "만나이엔 생일(월일)이 필요하나 birth_year만 수집해 *보수적 연나이*로 파생한다 — "
            "법정 기준 자체는 변호사 자문으로 확정. WHYMATH_MINOR_CONSENT_AGE로 조정."
        ),
    )
    parental_consent_grant_enabled: bool = Field(
        default=False,
        description=(
            "법정대리인 동의 *기록(GRANT)* 엔드포인트(POST /v1/users/me/parental-consent·PIPA "
            "만14세 미만 §3) 활성 여부. **기본 False(prod 안전)**: 신원 확인이 아직 "
            "StubGuardianVerifier(실 본인확인 미구현·변호사 자문 후속)라, 켜면 미성년이 임의 "
            "이메일로 *스스로 동의를 부여*해 게이트를 우회할 수 있다(self-consent). 실 "
            "GuardianVerifier(휴대폰 본인인증 등) 결선 전까지 off로 둬 동의 경로를 막는다(off면 "
            "404). consent_grant.py·pipa_data_matrix.md §3.5. "
            "WHYMATH_PARENTAL_CONSENT_GRANT_ENABLED로 조정."
        ),
    )

    # ── OAuth 로그인(카카오·네이버 SSO, OAuth-a2) ──
    # client_id는 공개 식별자(일반 str)·client_secret은 SecretStr·env-only(하드코딩 금지).
    # 비면 해당 provider 미등록(create_app이 레지스트리에서 제외 → 콜백 404).
    kakao_client_id: str = Field(
        default="",
        description=(
            "카카오 REST API 키(client_id·공개 식별자). 환경변수 WHYMATH_KAKAO_CLIENT_ID. "
            "비면 카카오 로그인 미등록(콜백 404)."
        ),
    )
    kakao_client_secret: SecretStr = Field(
        default=SecretStr(""),
        description=(
            "카카오 client_secret(선택·관리자 설정 시). SecretStr·env-only "
            "(WHYMATH_KAKAO_CLIENT_SECRET·하드코딩 금지)."
        ),
    )
    naver_client_id: str = Field(
        default="",
        description=(
            "네이버 client_id(공개 식별자). 환경변수 WHYMATH_NAVER_CLIENT_ID. "
            "비면 네이버 로그인 미등록(콜백 404)."
        ),
    )
    naver_client_secret: SecretStr = Field(
        default=SecretStr(""),
        description=(
            "네이버 client_secret. SecretStr·env-only(WHYMATH_NAVER_CLIENT_SECRET·하드코딩 금지)."
        ),
    )

    # ── L4 코치 엔드포인트 rate limit ──
    coach_rate_limit_read_per_minute: int = Field(
        default=60,
        ge=0,
        description=(
            "L4 코치 *읽기* 엔드포인트(GET /v1/coach/sessions/{id})의 사용자당 분당 요청 "
            "상한. 0=비활성. 읽기는 ETag/304 캐싱으로 경량 — 쓰기보다 높게 둔다."
        ),
    )
    evidence_retention_years: int = Field(
        default=3,
        ge=1,
        description=(
            "학습 증거(evidence_links — 미성년 오개념 진단 증거)의 *기본 보존기한*(년). 적재 시점 "
            "기준 retention_until을 채워 `purge_expired`가 경과분 파기(GDPR 데이터 최소화·무기한 "
            "보존 금지). 기본 3년(2026-06-18 합의)·미성년 보존은 규제 대상이라 법무 확정 시 조정. "
            "log_evidence가 retention_until 미제공 시 today+이 값으로 채운다."
        ),
    )
    coach_rate_limit_write_per_minute: int = Field(
        default=30,
        ge=0,
        description=(
            "L4 코치 *쓰기* 엔드포인트(POST /v1/coach·POST /v1/coach/sessions·POST "
            "/v1/coach/sessions/{id}/turns)의 사용자당 분당 요청 상한. 0=비활성. DB 쓰기·"
            "후속 LLM 호출 비용을 고려해 읽기보다 낮게 둔다."
        ),
    )
    coach_rate_limit_ip_read_per_minute: int = Field(
        default=120,
        ge=0,
        description=(
            "L4 코치 *읽기* 엔드포인트의 *IP 단위* 분당 요청 상한(미인증 표면 노출 시). "
            "0=비활성. 인증 사용자보다 *느슨하게* 둔다(공유 NAT·캠퍼스 IP 보호) — 인증된 "
            "사용자 한도(`coach_rate_limit_read_per_minute`)는 별도 적용."
        ),
    )
    coach_rate_limit_ip_write_per_minute: int = Field(
        default=60,
        ge=0,
        description=(
            "L4 코치 *쓰기* 엔드포인트의 *IP 단위* 분당 요청 상한. 0=비활성. "
            "쓰기는 IP 단위에서도 상대적으로 엄격(공격·자동화 봇 방어). 인증 사용자 한도는 별도."
        ),
    )
    coach_rate_limit_device_read_per_minute: int = Field(
        default=90,
        ge=0,
        description=(
            "L4 코치 *읽기* 엔드포인트의 *디바이스(X-Device-Id) 단위* 분당 요청 상한. "
            "0=비활성. 사용자(60)와 IP(120) 사이 중간 — 한 사용자가 다중 디바이스 가능하나 "
            "한 디바이스가 폭주하면 그 디바이스만 제한."
        ),
    )
    coach_rate_limit_device_write_per_minute: int = Field(
        default=45,
        ge=0,
        description=(
            "L4 코치 *쓰기* 엔드포인트의 *디바이스 단위* 분당 요청 상한. 0=비활성. "
            "사용자(30)와 IP(60) 사이 중간."
        ),
    )
    # ── 슬라이스 97: 시각화 LLM 엔드포인트 전용 rate limit (LLM 비용 보호) ──
    visualization_rate_limit_per_minute: int = Field(
        default=15,
        ge=0,
        description=(
            "시각화 생성(`POST /v1/visualizations/weak-concept`)의 *사용자 단위* 분당 상한. "
            "0=비활성. coach write(30)보다 낮음 — LLM 호출(생성·검증)이라 비용↑(coach는 "
            "프롬프트 결정만·LLM 미호출). 별 category로 coach write와 버킷 분리."
        ),
    )
    visualization_rate_limit_ip_per_minute: int = Field(
        default=30,
        ge=0,
        description=(
            "시각화 생성의 *IP 단위* 분당 상한. 0=비활성. 공유 NAT 방어(사용자 한도의 2배)."
        ),
    )
    visualization_rate_limit_device_per_minute: int = Field(
        default=22,
        ge=0,
        description="시각화 생성의 *디바이스 단위* 분당 상한. 0=비활성. 사용자(15)와 IP(30) 사이.",
    )
    # ── 슬라이스 27: 디바이스 store 운영 모드(lifespan 결선) ──
    device_store_mode: Literal["none", "pg", "pg_cached"] = Field(
        default="none",
        description=(
            "디바이스 자격증명 store 활성 모드. `none`(기본)=비활성·slice 21 공유 secret 폴백. "
            "`pg`=`PgDeviceStore` 단독(영속·HA, slice 23). "
            "`pg_cached`=`CachedDeviceStore(PgDeviceStore, Redis)`(verify 캐시·고QPS 최적화, "
            "slice 26). 운영 lifespan이 본 설정 읽어 store 자동 활성·종료 시 정리."
        ),
    )

    # ── 슬라이스 33: 디바이스 자동 폐기 idle 임계 ──
    device_credential_max_idle_days: int = Field(
        default=30,
        ge=1,
        description=(
            "`cleanup_stale_devices` 호출 시 *N일 이상 미사용*(last_used_at < now - N일·"
            "한 번도 사용 안 했으면 created_at 기준)인 활성 device를 자동 폐기. 30일 기본 — "
            "정상 사용자는 매월 1회 이상 verify(앱 사용)이라 무영향·잊혀진/분실 device만 폐기. "
            "운영은 Celery beat·cron으로 일일 호출 권장. 0 미만은 비활성 의도라 ge=1로 금지."
        ),
    )

    # ── 슬라이스 31: startup health check 타임아웃 ──
    device_store_health_check_timeout_seconds: float = Field(
        default=5.0,
        gt=0.0,
        description=(
            "부팅 시 `ping_device_store_health`가 각 의존성(PG·Redis) ping에 허용하는 최대 "
            "응답 시간(초). 초과 시 RuntimeError로 fail-fast — slice 30의 *무한 대기* 한계 "
            "해소. 기본 5s — 정상 인프라엔 충분(>1s면 인프라 점검 필요)·네트워크 깜빡임은 "
            "쿠버네티스 readiness probe로 외부 재시도."
        ),
    )

    # ── 슬라이스 35: startup health check 재시도(exponential backoff) ──
    device_store_health_check_max_retries: int = Field(
        default=3,
        ge=1,
        description=(
            "부팅 시 각 ping을 최대 N회 시도(첫 시도 포함). 일시적 인프라 깜빡임 흡수 — "
            "slice 30 한계 ③(재시도 없음) + slice 31 한계 ①(쿠버네티스 외부 재시도만) 해소. "
            "기본 3 — 정상 인프라엔 1회 통과·일시 실패 시 backoff 후 재시도. 1=재시도 비활성."
        ),
    )
    device_store_health_check_retry_backoff_seconds: float = Field(
        default=2.0,
        gt=0.0,
        description=(
            "재시도 사이 exponential backoff 기본 간격(초). 실제 대기는 `backoff * 2^attempt` "
            "(attempt=0,1,...): 2s·4s·8s. max_retries=3 시 총 대기 ~6s(timeout 별도 합산)."
        ),
    )
    device_store_health_check_retry_jitter: bool = Field(
        default=False,
        description=(
            "slice 36: 재시도 backoff에 AWS-style *full jitter* 적용"
            "(`uniform(0, base*2^attempt)`). k8s 다수 pod 동시 재시작 시 thundering herd"
            "(인프라 회복 직후 동시 재폭주) 차단. 기본 False — 단일 노드/예측 가능 backoff "
            "우선. 다중 pod 운영은 True 권장."
        ),
    )

    # ── 슬라이스 26: verify 결과 Redis 캐시 TTL ──
    device_verify_cache_ttl_seconds: int = Field(
        default=60,
        ge=0,
        description=(
            "디바이스 verify 결과 캐시 TTL(초). `CachedDeviceStore` 사용 시만 의미. "
            "낮을수록 revoke 후 stale 기간 짧음(권장 60s — DB 부담 절감과 invalidation "
            "신선도 절충). 0=캐시 비활성. 운영 lifespan에서 `CachedDeviceStore(inner, cache, "
            "ttl_seconds=settings.device_verify_cache_ttl_seconds)`로 주입."
        ),
    )
    # ── 슬라이스 48: count 캐시 TTL(verify와 별 — count는 register/revoke만 영향) ──
    device_count_cache_ttl_seconds: int = Field(
        default=300,
        ge=0,
        description=(
            "디바이스 count 캐시 TTL(초). count는 verify보다 갱신 빈도 *낮음*"
            "(register/revoke만 영향·verify는 영향 0) → 더 긴 TTL로 cache hit rate 향상. "
            "기본 300s(5분). register/revoke 시 즉시 invalidate되므로 stale 위험 ≈ 0. "
            "0=count 캐시 비활성(verify_ttl로 폴백)."
        ),
    )
    # ── 슬라이스 49: include_revoked=True count 전용 TTL ──
    device_count_all_cache_ttl_seconds: int | None = Field(
        default=None,
        ge=0,
        description=(
            "`include_revoked=True` count 전용 TTL(초). 폐기 이력 포함 count는 *훨씬 드물게* "
            "조회됨(주로 보안 감사·관리자 화면) → 더 긴 TTL로 hit rate 향상 가능. None(기본)이면 "
            "`device_count_cache_ttl_seconds` 그대로 사용(slice 48 backward compat). "
            "운영 보고로 active와 all 사용 빈도 차이 확인 후 조정."
        ),
    )

    # ── 슬라이스 25: 디바이스 등록 전용 rate limit (`/v1/devices/register`) ──
    device_register_rate_limit_per_minute: int = Field(
        default=5,
        ge=0,
        description=(
            "디바이스 등록(`POST /v1/devices/register`)의 *사용자 단위* 분당 상한. 0=비활성. "
            "등록은 드문 작업(첫 실행 1회·기기 변경)이라 매우 낮게 — sock-puppet 디바이스 "
            "양산·DB 자격증명 폭증 차단. coach `write`와 *별 키 공간*"
            "(category=device_register)."
        ),
    )
    device_register_rate_limit_ip_per_minute: int = Field(
        default=10,
        ge=0,
        description=(
            "디바이스 등록의 *IP 단위* 분당 상한. 0=비활성. 공유 NAT/학교/공공 와이파이에서 "
            "여러 사용자가 등록 가능하도록 사용자 한도(5)의 2배."
        ),
    )
    device_secret_encryption_key: SecretStr = Field(
        default=SecretStr(""),
        description=(
            "slice 72: 디바이스 secret at-rest 봉투 암호화 마스터 키(base64 인코딩 32바이트="
            "AES-256). 빈 값=암호화 비활성(평문 저장·기존 동작 폴백). DB 밖(env/Settings)에 "
            "두어 DB dump만으로는 secret 복호 불가하게 한다. `WHYMATH_DEVICE_SECRET_"
            "ENCRYPTION_KEY` env로만 주입(SecretStr — repr/로그 평문 차단·하드코딩 금지). "
            '키 생성: `python -c "import base64,os; '
            'print(base64.b64encode(os.urandom(32)).decode())"`. 진짜 KMS(HSM)는 후속.'
        ),
    )
    device_secret_decryption_fallback_keys: SecretStr = Field(
        default=SecretStr(""),
        description=(
            "slice 75: 키 회전용 *복호 전용* fallback 키 목록(쉼표 구분 base64 32바이트). "
            "primary 키 회전 시 구 키를 여기 두면 구 키로 암호화된 행이 lockout 없이 복호된다 "
            "(encrypt는 항상 primary). 전 행 재암호화 후 제거. 빈 값=fallback 없음. "
            "`WHYMATH_DEVICE_SECRET_DECRYPTION_FALLBACK_KEYS` env(SecretStr·하드코딩 금지)."
        ),
    )

    coach_device_hmac_secret: SecretStr = Field(
        default=SecretStr(""),
        description=(
            "디바이스 서명 검증용 HMAC 비밀키. 빈 기본=비활성(슬라이스 20 동작 그대로). "
            "설정 시 클라이언트는 `X-Device-Sig: HMAC-SHA256(secret, device_id) hex`를 동봉 — "
            "유효하지 않으면 device 차원 검사 비활성(fail-safe·user+IP만 적용). "
            "**위협 모델**: 앱 바이너리에서 secret 추출 가능 — *trivial spoofing*(랜덤 ID "
            "반복) 방어용. 정식 디바이스 인증은 OAuth-style 등록 후속. WHYMATH_COACH_DEVICE_"
            "HMAC_SECRET env로만 주입(SecretStr — repr/로그 평문 차단·하드코딩 금지)."
        ),
    )
    coach_rate_limit_backend: Literal["memory", "redis"] = Field(
        default="memory",
        description=(
            "rate limit 백엔드 — `memory`=프로세스-로컬 deque(기본·테스트·로컬), "
            "`redis`=Redis ZSET sliding window(분산/HA 정합·다중 워커/인스턴스 시 필수). "
            "`redis` 선택 시 `redis_url`로 연결, 라이브 도달성은 lazy."
        ),
    )

    # ── 슬라이스 104: L4 오개념 *의미(임베딩) 매칭* 좌석 (substring 거짓음성 보완) ──
    # L4 SemanticMatcher가 카탈로그 표현·학생 텍스트를 임베딩해 코사인 유사도로 패러프레이즈·
    # 동의어를 잡는다(substring AND가 못 잡던 *의미 recall*). **정직 스코프**: 임베딩은 의미
    # recall만 개선하고 *방향·부정·등치*("연속⇒미분" vs 역)는 substring과 똑같이 못 가린다
    # (방향 판별은 LLM-judged/NLI 후속 — docs/prompts/misconception_diagnosis.md §의미 매칭 층).
    # 기본은 `local`(bge-m3·로컬 우선·CLAUDE.md 비용·Phaiakes9). 라이브 로드는 *지연 import*라
    # 이 설정만으로는 모델 다운로드·네트워크가 일어나지 않는다(CI hermetic).
    embedding_provider: Literal["local", "openai", "fake"] = Field(
        default="local",
        description=(
            "오개념 의미 매칭 임베딩 제공자. `local`(기본)=sentence-transformers bge-m3(로컬 "
            "우선·Phaiakes9). `openai`=text-embedding-3-large(클라우드·키 필요). `fake`=결정론 "
            "해시 벡터(테스트·CI hermetic 전용·라이브 의존 0). 좌석 선택만이고 실제 모델 로드는 "
            "지연(import 시점이 아니라 첫 embed 호출 시)."
        ),
    )
    embedding_model_local: str = Field(
        default="BAAI/bge-m3",
        description=(
            "로컬(sentence-transformers) 임베딩 모델 ID. 기본 bge-m3(다국어·한국어 강건). "
            "WHYMATH_EMBEDDING_MODEL_LOCAL로 오버라이드. 시크릿 아님."
        ),
    )
    embedding_model_openai: str = Field(
        default="text-embedding-3-large",
        description=(
            "OpenAI 임베딩 모델 ID(embedding_provider=openai일 때). 기본 text-embedding-3-large "
            "(CLAUDE.md 임베딩 표준). WHYMATH_EMBEDDING_MODEL_OPENAI로 오버라이드. 시크릿 아님."
        ),
    )
    openai_api_key: SecretStr = Field(
        default=SecretStr(""),
        description=(
            "OpenAI API 키(sk-...). SecretStr — repr/로그 평문 노출 안 됨. 기본값 없음(빈 = "
            "미설정). 환경변수 WHYMATH_OPENAI_API_KEY로만 주입(CLAUDE.md 보안 금기: 하드코딩 "
            "금지). 비면 OpenAIEmbeddingProvider는 명확한 오류(조용한 폴백 금지)."
        ),
    )
    misconception_semantic_threshold: float = Field(
        default=0.55,
        ge=-1.0,
        le=1.0,
        description=(
            "오개념 의미 매칭 코사인 임계값(이 *미만*은 미매칭). 보수적 기본 0.55 — 거짓양성 "
            "억제(짧은 공통 토큰의 의미 근접 오탐 방지). semantic_matches(threshold=)로 호출별 "
            "오버라이드 가능. WHYMATH_MISCONCEPTION_SEMANTIC_THRESHOLD로 전역 조정."
        ),
    )
    misconception_judge_routing: Literal["fast_math", "general_mid"] = Field(
        default="fast_math",
        description=(
            "오개념 방향 판별 judge 라우팅 프로파일(슬108 후속·측정 실험용). **`fast_math`"
            "(기본·현행)** = 로컬 FAST MATH(qwen2-math:1.5b). 단 2026-06-15 라이브 측정에서 "
            "한국어 판정 형식(`판정: 예/아니오/불확실`) 미준수로 전부 UNCERTAIN→FP 감소 0(작은 "
            "수학 모델이 NLP 분류·형식 준수에 부적합). **`general_mid`** = GENERAL MID"
            "(qwen2.5:7b)로 라우팅해 형식 준수·방향 판별 재측정(판단은 NLP 분류라 일반 instruct "
            "모델 적합). judge는 coach 미배선이라 이 값은 *측정 경로*(CLI `--judge`·통합 "
            "테스트)에만 영향. WHYMATH_MISCONCEPTION_JUDGE_ROUTING로 전환."
        ),
    )

    misconception_semantic_mode: Literal["off", "shadow", "on"] = Field(
        default="off",
        description=(
            "L4 coach 오개념 진단의 *의미(임베딩) 매칭 결합* 모드(slice 106·111). 3값: "
            "**`off`(기본·opt-in)** = coach는 substring `diagnose()`만(현행 비트동일·의미 매처 "
            "미호출·임베딩 로드 0). **`shadow`** = 의미 매처를 *라이브로 돌리되* 노출은 substring "
            "그대로(off와 동일)이고 substring↔semantic *불일치만 로깅*한다(slice 111·step_shadow "
            "미러·비노출·학생 원문 미포함) — 합성 프로브가 아닌 *실 분포*에서 플립 근거 수집. "
            "**`on`** = substring 아래에 semantic-only 후보를 결합해 *노출*(combine_diagnoses·"
            "substring 우선·재정렬 없음). shadow·on의 의미 매칭은 *비블로킹*(asyncio.to_thread)·"
            "실패 시 substring graceful 폴백(200 유지)·matches[0]은 substr면 항상 substr. 기본 "
            "off는 ① bge-m3 로드 비용 ② 방향맹 FP를 보수적으로 막기 위함. `l4_step_shadow_enabled` "
            "미러. WHYMATH_MISCONCEPTION_SEMANTIC_MODE=shadow|on으로 켠다."
        ),
    )

    misconception_judge_enabled: bool = Field(
        default=False,
        description=(
            "L4 coach 오개념 진단에 *방향 판별 LLM-judge 필터*(slice 108)를 켤지. **False(기본·"
            "opt-in)·이번 슬라이스 미사용**: 슬108은 judge 코어 + 측정 하니스만 만들고 coach에 "
            "*배선하지 않는다*(라이브 judge 효과를 Kiki Phaiakes9 측정 후 후속 슬라이스에서 결정). "
            "이 플래그는 그 후속 coach 배선용 *예약*이다 — 현재 어떤 런타임 경로도 읽지 않는다"
            "(`_compute_matches` 무변경). True여도 이번 슬라이스엔 동작 변화 0. judge는 substring·"
            "임베딩이 못 가리는 방향(⇒ 역)·부정(≠)·등치(=)를 언어 추론으로 판별해 `아니오`(올바름/"
            "다른 말) 후보만 거른다(예·불확실 유지·recall 보존). 라우팅/모델은 L3 재사용(로컬 "
            "FAST·라우터 경유). `l4_step_shadow_enabled`·`misconception_semantic_mode` 미러. "
            "WHYMATH_MISCONCEPTION_JUDGE_ENABLED=true로 켠다(후속)."
        ),
    )

    misconception_judge_shadow: bool = Field(
        default=False,
        description=(
            "L4 coach 오개념 진단에서 *judge would-be shadow 로깅*(G1·04b Phase 1)을 켤지. "
            "**False(기본·opt-in)·현행 비트동일**: 노출(student-facing)은 *절대 불변*이고, "
            '`misconception_semantic_mode=="shadow"`일 때만 효력이 있다(매처가 라이브로 도는 '
            "그 경로에서, 의미 후보에 judge를 *비차단*으로 돌려 *걸러질 결과*(would-be removed/"
            "kept)를 무노출로 로깅). 노출 전 실데이터로 judge 효과를 검증하기 위함(합성↔실 갭). "
            "**매처 shadow(`misconception_semantic_mode`·싸다)와 비용 분리**: judge는 LLM(수 초)"
            "이라 매처 shadow와 on/off가 *독립*이어야 한다(이 플래그가 별 토글). judge는 응답 "
            "경로를 *지연시키지 않는다* — fire-and-forget(asyncio.create_task)으로 띄우고 즉시 "
            "반환한다(coach는 judge를 await하지 않음). 레코드엔 *학생 원문·judge reason 미저장* "
            "(미성년 PII — verdict 카운트·id·임계만). `misconception_judge_enabled`(노출 게이트)와 "
            "별개다(이쪽은 노출 필터·저쪽은 비노출 측정). "
            "WHYMATH_MISCONCEPTION_JUDGE_SHADOW=true로 켠다."
        ),
    )

    # ── 슬라이스 105: 오개념 임베딩 *영속(pgvector) 백엔드* 좌석 선택 ──
    # 슬104 VectorIndex 좌석에 PgVectorIndex(pgvector 백엔드)를 추가한다. **기본은 `memory`**
    # (InMemoryVectorIndex·기본 동작 무변경) — pgvector는 *opt-in*이다. 카탈로그 30종엔
    # in-memory 선형 스캔이 최적이고(슬104 docstring), pgvector는 *영속화 + 스케일 코퍼스
    # groundwork*다(과장 금지 — 30종에 pgvector가 더 빠르다고 주장하지 않는다). 슬98 결정
    # (벡터 DB=pgvector·Postgres 16 통합)의 첫 실 결선 자리.
    vector_store: Literal["memory", "pgvector"] = Field(
        default="memory",
        description=(
            "오개념 의미 매칭 벡터 인덱스 백엔드. `memory`(기본)=InMemoryVectorIndex(코사인 "
            "선형 스캔·카탈로그 30종 최적·라이브 의존 0). `pgvector`=PgVectorIndex(PostgreSQL "
            "pgvector 영속화·스케일 groundwork·sync psycopg 격리 엔진). `pgvector` 선택 시에만 "
            "psycopg/pgvector를 *지연 import*하므로 기본(memory) 경로는 sync 드라이버 불요. "
            "WHYMATH_VECTOR_STORE로 조정."
        ),
    )
    embedding_dim: int = Field(
        default=1024,
        ge=1,
        description=(
            "PgVectorIndex `misconception_embedding.embedding` 컬럼 차원(pgvector `vector(N)`). "
            "기본 1024(bge-m3). 임베딩 *모델*과 일치해야 한다(Fake 64·OpenAI te-3-large 3072). "
            "30종 코퍼스는 seq-scan이라 고정 차원이 검색 성능엔 무관하나, SQLAlchemy `Vector` "
            "타입·마이그레이션이 차원을 박으므로 모델 교체 시 이 값과 마이그레이션을 함께 "
            "맞춘다(in-memory 경로는 무관 — 차원 무지정 동작). WHYMATH_EMBEDDING_DIM로 조정."
        ),
    )

    @property
    def sync_database_url(self) -> str:
        """`database_url`(async asyncpg)에서 *sync psycopg* 드라이버 URL을 파생(슬105).

        PgVectorIndex는 슬104 `VectorIndex` Protocol이 *동기*라 sync SQLAlchemy 엔진을
        쓴다(03a 로컬-우선처럼 *벡터 store 좌석에 한정*해 sync 드라이버 도입 — async 앱
        엔진은 무변경). 자격증명·호스트·DB명은 그대로 보존하고 *드라이버만* `+psycopg`로
        바꾼다. 문자열 치환이 아니라 `make_url(...).set(drivername=...)`로 파싱·재조립해
        패스워드 인코딩·포트 등 엣지를 안전 처리한다(시크릿은 코드에 0 — `database_url`이
        env에서 오고 이 프로퍼티는 변환만). asyncpg가 아닌 다른 드라이버(예: 이미 psycopg)면
        그대로 psycopg로 정규화한다(드라이버 토큰만 교체).
        """
        from sqlalchemy.engine import make_url

        return (
            make_url(self.database_url)
            .set(drivername="postgresql+psycopg")
            .render_as_string(hide_password=False)
        )

    @property
    def openai_configured(self) -> bool:
        """OpenAI API 키가 채워졌는가(임베딩 클라우드 호출 가능 여부, 슬104).

        비어 있으면 미설정 — OpenAIEmbeddingProvider는 첫 embed에서 명확한 오류를 던진다
        (조용한 폴백 금지·CLAUDE.md "모르면 모른다고"). 값은 로그에 남기지 않는다.
        """
        return bool(self.openai_api_key.get_secret_value())

    @property
    def langfuse_configured(self) -> bool:
        """Langfuse 공개키·시크릿키가 *둘 다* 채워졌는가(전송 가능 여부).

        하나라도 비어 있으면 미설정으로 보고 LangfuseSink는 no-op이 된다. SecretStr는
        `get_secret_value()`로만 평문을 꺼내며, 여기서는 *비어 있는지*만 본다(값 로그 X).
        """
        return bool(self.langfuse_public_key) and bool(self.langfuse_secret_key.get_secret_value())

    @property
    def anthropic_configured(self) -> bool:
        """Anthropic API 키가 채워졌는가(클라우드 생성 가능 여부, S5).

        비어 있으면 미설정으로 보고 AnthropicProvider는 클라우드 결정에 명확한 오류를
        던진다(조용한 LOCAL 강등 금지 — 라우터가 정당한 이유로 클라우드를 택했으므로).
        SecretStr는 `get_secret_value()`로만 평문을 꺼내며, 여기서는 *비어 있는지*만 본다.
        """
        return bool(self.anthropic_api_key.get_secret_value())

    @property
    def jwt_configured(self) -> bool:
        """JWT 시크릿이 채워졌는가(토큰 발급/검증 가능 여부).

        비어 있으면 미설정 — `create_access_token`/`decode_access_token`이 명확한 오류를
        던진다(빈 시크릿으로 토큰을 발급/검증하는 사고 방지). 값은 로그에 남기지 않는다.
        """
        return bool(self.jwt_secret_key.get_secret_value())

    @property
    def kakao_configured(self) -> bool:
        """카카오 로그인이 구성됐는가(client_id 존재). 비면 콜백 레지스트리에서 제외(404)."""
        return bool(self.kakao_client_id)

    @property
    def naver_configured(self) -> bool:
        """네이버 로그인이 구성됐는가(client_id 존재). 비면 콜백 레지스트리에서 제외(404)."""
        return bool(self.naver_client_id)

    @property
    def effective_celery_broker_url(self) -> str:
        """실제 Celery broker URL — celery_broker_url이 비어 있으면 redis_url로 폴백.

        단일 Redis로 캐시(S2)와 큐(S4)를 함께 운영하는 것이 기본이다(03a §D.3). 전용
        broker가 필요하면 WHYMATH_CELERY_BROKER_URL로 분리 인프라를 가리킨다.
        """
        return self.celery_broker_url or self.redis_url

    @property
    def effective_celery_result_backend(self) -> str:
        """실제 Celery result backend URL — 비어 있으면 redis_url로 폴백.

        job_id로 QUALITY 결과를 조회하려면(폴링, 03a §D.3) result backend가 필요하다.
        기본은 broker와 같은 redis_url을 재사용한다.
        """
        return self.celery_result_backend or self.redis_url


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """프로세스 단위로 캐시된 Settings 접근자.

    `lru_cache`로 단일 인스턴스를 재사용한다(환경변수는 프로세스 수명 동안 고정 가정).
    테스트에서 환경을 바꿔 재로딩하려면 `get_settings.cache_clear()`를 호출한다.
    """
    return Settings()
