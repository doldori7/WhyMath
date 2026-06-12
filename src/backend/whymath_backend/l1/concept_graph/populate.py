"""개념 임베딩 영속 적재 CLI — `python -m whymath_backend.l1.concept_graph.populate` (슬3).

슬1 산출 `graph.json`(UC 키·정제)의 개념을 설정된 임베딩 제공자(`config.embedding_provider`)로
임베딩해 `ConceptEmbeddingIndex`(pgvector `concept_embedding` 테이블)에 멱등 upsert한다. 운영
(Phaiakes9)에서 개념 사전 임베딩을 *프로세스 밖에 영속*하는 진입점이다. L4 오개념 적재 CLI
(`l4.misconception.semantic.populate`)와 동형이되, 입력이 카탈로그가 아니라 `graph.json`이다.

전제: `WHYMATH_VECTOR_STORE=pgvector` + 마이그레이션 head 적용된 실 PG 도달 + `graph.json` 존재
(슬1 `transform-v1 --output-dir`로 생성). 기본(memory)에선 영속 store가 없으므로 이 CLI는 의미가
없다(pgvector 명시 시에만). 자격증명은 env(시크릿 0 하드코딩). 라이브 임베딩 모델 로드(bge-m3
다운로드·OpenAI 키)는 첫 embed에서 발생한다.

CI hermetic: 이 모듈 import만으로는 임베딩·PG 연결이 없다(provider·엔진 모두 지연). 실제
적재는 CLI 실행(`__main__`) 또는 통합테스트에서만.

사용:
    WHYMATH_VECTOR_STORE=pgvector \
    python -m whymath_backend.l1.concept_graph.populate \
        --graph data/concept_graph/graph.json
"""

from __future__ import annotations

import argparse
from pathlib import Path

from whymath_backend.config import get_settings
from whymath_backend.l1.concept_graph.embedding import (
    load_concepts_from_graph_json,
    populate_concept_embeddings,
)
from whymath_backend.l4.misconception.semantic.provider import build_provider

# graph.json 기본 경로(슬1 transform-v1 --output-dir 관례). 명시 --graph로 오버라이드.
_DEFAULT_GRAPH_PATH = Path("data/concept_graph/graph.json")


def main(argv: list[str] | None = None) -> int:
    """graph.json 개념을 임베딩해 ConceptEmbeddingIndex에 적재하고 적재 행 수를 출력(CLI 본체).

    설정된 provider(local/openai/fake)를 만들어 `populate_concept_embeddings`로 upsert한다.
    반환은 프로세스 종료 코드(0=성공·2=설정/입력 오류). 적재 건수를 stdout으로 보고한다.
    """
    parser = argparse.ArgumentParser(
        prog="whymath-concept-embedding-populate",
        description="개념그래프 graph.json → pgvector 의미 임베딩 멱등 적재(슬3).",
    )
    parser.add_argument(
        "--graph",
        type=Path,
        default=_DEFAULT_GRAPH_PATH,
        help=f"슬1 transform-v1 산출 graph.json 경로(기본 {_DEFAULT_GRAPH_PATH}).",
    )
    args = parser.parse_args(argv)

    settings = get_settings()
    if settings.vector_store != "pgvector":
        # memory 모드에선 영속 store가 없다 — 명확히 보고하고 비정상 종료(조용한 무동작 금지).
        print(
            "WHYMATH_VECTOR_STORE=pgvector가 아닙니다(현재: "
            f"{settings.vector_store}). pgvector 적재는 영속 store 모드에서만 의미가 있습니다."
        )
        return 2
    graph_path: Path = args.graph
    if not graph_path.exists():
        print(
            f"graph.json 없음: {graph_path} — 슬1 transform-v1 산출을 먼저 생성하세요 "
            "(`python -m data_pipeline.concept_graph transform-v1 --output-dir ...`)."
        )
        return 2

    concepts = load_concepts_from_graph_json(graph_path)
    provider = build_provider(settings)
    count = populate_concept_embeddings(concepts, provider, settings=settings)
    print(
        f"개념 임베딩 적재 완료: {count}건 "
        f"(provider={settings.embedding_provider}·graph={graph_path})."
    )
    return 0


if __name__ == "__main__":  # pragma: no cover — CLI 진입점(통합·운영 실행 전용)
    raise SystemExit(main())
