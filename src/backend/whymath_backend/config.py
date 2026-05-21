"""백엔드 환경설정 — pydantic-settings 기반 (CLAUDE.md 보안 금기: 시크릿 하드코딩 금지).

모든 설정은 *환경변수*로 주입한다. 이 파일에는 호스트·시크릿을 하드코딩하지 않으며
기본값은 *로컬 개발용 무해 디폴트*(예: Ollama 로컬 데몬 주소)만 둔다.

범위 메모 (M1.2-live S1): 본 슬라이스는 L3 라우터 ↔ 실제 Ollama 백엔드 결선과
FastAPI 앱만 다룬다. Redis·Langfuse·Celery·클라우드 LLM·DB 설정은 후속 슬라이스
(S2~S5)에서 추가한다 — 여기서는 *Ollama 연동에 필요한 최소 설정*만 노출한다.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
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

    # ── 응답 캐시 (S1은 인메모리 스텁, Redis는 S2) ──
    cache_ttl_s: int = Field(
        default=3600,
        ge=0,
        description="응답 캐시 TTL(초). S1은 인메모리 스텁이 기록만 함(만료 미구현, 03a §F.1)",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """프로세스 단위로 캐시된 Settings 접근자.

    `lru_cache`로 단일 인스턴스를 재사용한다(환경변수는 프로세스 수명 동안 고정 가정).
    테스트에서 환경을 바꿔 재로딩하려면 `get_settings.cache_clear()`를 호출한다.
    """
    return Settings()
