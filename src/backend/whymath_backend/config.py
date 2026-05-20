"""백엔드 환경설정 — Pydantic Settings 기반 단일 진실(single source).

L3 라이브 어댑터(providers·cache·tracing·queue)가 필요로 하는 *연결 정보*를 모두
여기에 모은다. CLAUDE.md 절대 금기 "API 키·시크릿을 코드에 하드코딩 금지"를 지키기
위해 모든 시크릿은 env로만 주입한다(기본값은 None 또는 로컬 개발용 안전값).

명명 규약: env 접두사 `WHYMATH_` — 벤치마크 도구(`WHYMATH_OLLAMA_HOST` 등)와 동일
컨벤션을 따라 운영자가 한 벌의 env로 벤치·서버를 모두 구성할 수 있게 한다.

범위 메모(M1.2): 본 모듈은 L3 라이브 연동에 필요한 필드만 정의한다. DB(PostgreSQL)·
인증·결제 등 다른 계층 설정은 각 계층 구현 시 이 Settings에 *추가*한다(분해 금지).
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """전역 설정 — env(`WHYMATH_*`) 또는 .env에서 로드. 전 필드 override 가능.

    설계 정본: docs/architecture/03a_l3_router_design.md §A.0(로컬 모델)·§A.1(CLOUD
    모델 풀: CLOUD_MID=Sonnet, CLOUD_HIGH=Opus)·§F.1(캐시 TTL).
    """

    model_config = SettingsConfigDict(
        env_prefix="WHYMATH_",
        env_file=".env",
        env_file_encoding="utf-8",
        # 알 수 없는 env는 무시 — 다른 계층/도구가 같은 WHYMATH_ 네임스페이스를
        # 공유하므로(예: WHYMATH_BENCH_*), 본 Settings가 모르는 키로 죽지 않게 한다.
        extra="ignore",
    )

    # ── Ollama (로컬 LLM, 축1=LOCAL) ──
    # 벤치마크(bench_latency.py)와 동일 컨벤션: WHYMATH_OLLAMA_HOST.
    # 기본은 Phaiakes9 Windows Native GPU Ollama(127.0.0.1:11434)를 가리킨다.
    ollama_host: str = "http://127.0.0.1:11434"

    # ── Anthropic (클라우드 LLM, 축1=CLOUD_*) ──
    anthropic_api_key: str | None = None
    # 03a §A.1: CLOUD_MID = Claude Sonnet 4.6, CLOUD_HIGH = Claude Opus 4.7.
    cloud_mid_model: str = "claude-sonnet-4-6"
    cloud_high_model: str = "claude-opus-4-7"

    # ── Redis (캐시 + Celery 브로커) ──
    redis_url: str = "redis://localhost:6379/0"

    # ── Langfuse (관측성, 03a §F.2) ──
    langfuse_public_key: str | None = None
    langfuse_secret_key: str | None = None
    langfuse_host: str = "https://cloud.langfuse.com"

    # ── 응답 캐시 TTL (03a §F.1) ──
    # 기본 24시간 — 동일 교과서 텍스트·개념 표현의 반복 호출을 흡수(캐싱 KPI 30%→50%).
    cache_ttl_seconds: int = 86400


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """캐시된 Settings 싱글톤 반환.

    프로세스 수명 동안 env를 한 번만 읽어 재사용한다(lru_cache). 테스트에서
    env를 바꿔 재로드하려면 `get_settings.cache_clear()` 후 다시 호출한다.
    """
    return Settings()
