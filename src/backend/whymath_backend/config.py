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
