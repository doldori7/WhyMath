"""오개념 임베딩 영속 적재 CLI — `python -m ...semantic.populate` (slice 105).

카탈로그 30종의 표현(`catalog_text`)을 설정된 임베딩 제공자(`config.embedding_provider`)로
임베딩해 `PgVectorIndex`(pgvector)에 upsert 적재한다. 운영(Phaiakes9)에서 사전 임베딩을
*프로세스 밖에 영속*하는 진입점이다(매처 인메모리 `_ensure_built`의 영속 대응).

전제: `WHYMATH_VECTOR_STORE=pgvector` + 마이그레이션 head 적용된 실 PG 도달. 기본(memory)에선
영속 store가 없으므로 이 CLI는 의미가 없다(pgvector 명시 시에만). 자격증명은 env(시크릿 0
하드코딩). 라이브 임베딩 모델 로드(bge-m3 다운로드·OpenAI 키)는 첫 embed에서 발생한다.

CI hermetic: 이 모듈 import만으로는 임베딩·PG 연결이 없다(provider·엔진 모두 지연). 실제
적재는 CLI 실행(`__main__`) 또는 통합테스트에서만.
"""

from __future__ import annotations

from whymath_backend.config import get_settings
from whymath_backend.l4.misconception.semantic.pgvector_index import populate_pgvector
from whymath_backend.l4.misconception.semantic.provider import build_provider


def main() -> int:
    """카탈로그를 임베딩해 PgVectorIndex에 적재하고 적재 행 수를 출력한다(CLI 본체).

    설정된 provider(local/openai/fake)를 만들어 `populate_pgvector`로 upsert한다. 반환은
    프로세스 종료 코드(0=성공). 적재 건수를 stdout으로 보고한다(운영 가시성).
    """
    settings = get_settings()
    if settings.vector_store != "pgvector":
        # memory 모드에선 영속 store가 없다 — 명확히 보고하고 비정상 종료(조용한 무동작 금지).
        print(
            "WHYMATH_VECTOR_STORE=pgvector가 아닙니다(현재: "
            f"{settings.vector_store}). pgvector 적재는 영속 store 모드에서만 의미가 있습니다."
        )
        return 2
    provider = build_provider(settings)
    count = populate_pgvector(provider, settings=settings)
    print(f"오개념 임베딩 적재 완료: {count}건 (provider={settings.embedding_provider}).")
    return 0


if __name__ == "__main__":  # pragma: no cover — CLI 진입점(통합·운영 실행 전용)
    raise SystemExit(main())
