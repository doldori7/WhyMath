"""problem_embedding 테이블 — 문제 발문 dedup pgvector 영속 (S2-c 과유사 dedup 게이트)

문제 코퍼스 dedup 마이그레이션 S2-c — S2-b가 자체생성 동등문제를 backend `problem`에 적재한 뒤,
각 문제의 *발문(question_text) 의미 임베딩*을 pgvector에 영속하는 백킹 테이블을 만든다. PK=
problem_id(UUID)로 `problem.problem_id`와 *동일 키 공간*(FK·ondelete CASCADE)이라 문제 엔티티와
벡터가 한 키로 join된다. `atom_embedding`(Phase 2b) 마이그레이션을 문제용으로 미러링한다(신규
테이블·additive·무영향).

upgrade:
  - `CREATE EXTENSION IF NOT EXISTS vector` — pgvector 확장 활성(`vector` 타입 사용 전제).
    선행 임베딩 마이그레이션(misconception/concept/atom)이 이미 생성하므로 정상 체인에선 무동작
    (IF NOT EXISTS). *그러나 여기서도 명시 실행*하는 이유: 이 마이그레이션이 단독 적용되거나
    (cherry-pick) 선행 확장 마이그레이션이 어떤 경로로 빠져도 `problem_embedding`의 `vector`
    컬럼 생성이 안전하도록 자기완결적으로 보장한다(atom_embedding 마이그레이션과 동일 규약).
  - `problem_embedding` 테이블:
    - `problem_id`(UUID PK·`problem.problem_id`와 동일 키 공간·**느슨참조·하드 FK 없음**) —
      atom_embedding이 concept.code를 FK 없이 같은 키로만 참조하는 것과 동형(임베딩 적재를 문제
      적재 순서/트랜잭션과 분리·ORM docstring). upsert 충돌 키(atom_embedding의 code PK 짝).
    - `embedding`(pgvector `vector(1024)`) — 발문 임베딩(기본 bge-m3 1024차원).
    - `provider`·`model`·`dim`·`text_hash`·`created_at` — 임베딩 공간 메타·표현 변경/멱등 감지·
      생성 시각. **원문(source_text)은 컬럼으로 두지 않는다**(redaction·중복 — 발문은
      `problem.question_text`에 이미 있음·ORM docstring 참조).
  - **subject 축 없음**: 세 임베딩 테이블(misconception/concept/atom)이 가진 subject 교과 축을
    이 테이블은 두지 않는다 — dedup은 문제 코퍼스 *내부* 자기-kind 질의이고 Phase 1 코퍼스가
    전량 수학이라 provider·model 공간 필터만으로 충분하다(과장 금지·후속 확장 여지).
  - **HNSW/IVFFlat 인덱스 없음**: `atom_embedding`과 동일 — 현 규모(Phase 1 손저작 코퍼스)는
    seq-scan이 최적(스케일 코퍼스는 fixed-dim + HNSW cosine 인덱스가 정석·후속).

downgrade (왕복 안전 — CI가 `downgrade -1`→`upgrade head` 왕복 검증):
  - `problem_embedding` 테이블만 drop. **`vector` 확장은 drop하지 않는다** — 선행 임베딩
    테이블들이 *여전히 `vector` 타입 컬럼을 소유*하므로 확장을 떨어뜨리면 그 테이블들이 깨진다.
    확장 생애주기는 *맨 처음 확장을 도입한* misconception_embedding 마이그레이션의 downgrade가
    책임진다(확장 소유권은 한 곳·atom_embedding과 동일 규약).

차원 메모: `embedding`은 `vector(1024)`로 고정한다(`config.embedding_dim` 기본값과 정합·ORM
`ProblemEmbedding.embedding`·선행 3 임베딩 테이블과 동일). 임베딩 *모델* 교체로 차원이 달라지면
(Fake 64·te-3-large 3072) config·ORM과 함께 *새 마이그레이션*으로 컬럼 차원을 바꾼다(마이그레이션은
결정적이어야 하므로 여기선 정본 기본값을 박는다).

Revision ID: c3d4e5f0a1b3
Revises: c3d4e5f0a1b2
Create Date: 2026-07-05 12:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c3d4e5f0a1b3"
down_revision: str | None = "c3d4e5f0a1b2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# 정본 임베딩 차원(config.embedding_dim 기본 1024·bge-m3). 마이그레이션은 결정적이어야 하므로
# 런타임 설정이 아닌 고정 리터럴을 박는다(모델 교체 시 새 마이그레이션으로 변경·atom_embedding
# 동일).
_EMBEDDING_DIM = 1024


def upgrade() -> None:
    # pgvector 확장 — vector 타입 사용 전제. 선행 임베딩 마이그레이션이 이미 만들었으면 무동작
    # (IF NOT EXISTS). 자기완결적 보장(단독 적용·cherry-pick 안전·atom_embedding 동일 규약).
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "problem_embedding",
        sa.Column("problem_id", sa.Uuid(), nullable=False),
        sa.Column("embedding", Vector(_EMBEDDING_DIM), nullable=False),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("model", sa.Text(), nullable=False),
        sa.Column("dim", sa.Integer(), nullable=False),
        sa.Column("text_hash", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        # 하드 FK 없음(느슨참조) — atom_embedding이 concept.code를 FK 없이 같은 키로만 참조하는
        # 것과 동형. 임베딩 적재를 문제 적재 순서/트랜잭션과 분리한다(docstring).
        sa.PrimaryKeyConstraint("problem_id", name=op.f("pk_problem_embedding")),
    )


def downgrade() -> None:
    # 테이블만 drop. `vector` 확장은 선행 임베딩 테이블들이 여전히 소유하므로 *떨어뜨리지
    # 않는다*(확장 소유권은 도입 마이그레이션에 있음 — docstring 참조).
    op.drop_table("problem_embedding")
