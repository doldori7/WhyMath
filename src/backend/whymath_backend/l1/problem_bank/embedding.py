"""문제 발문 임베딩 dedup — pgvector 영속 좌석 + 과유사 게이트 (L1 문제 코퍼스·S2-c).

`l1/atom_graph/embedding.py`(원자 의미 임베딩 pgvector 좌석·Phase 2b)의 *문제 코퍼스* 짝이다.
S2-b가 자체생성 동등문제를 backend `problem`에 적재한 뒤, 이 좌석은 각 문제의 *발문
(question_text)* 을 임베딩해 `problem_embedding` 테이블(pgvector)에 멱등 upsert하고, **과유사
변형**(거의 동일한 발문 남발)을 코사인 유사도로 탐지하는 순수 질의 게이트를 제공한다.
`problem.problem_id`(UUID PK)와 *동일 키 공간*이라 문제 엔티티와 벡터가 한 키로 join된다.

**임베딩 provider seam·sync 엔진·해시·식별 헬퍼는 레이어-중립 L1 프리미티브
(`l1/embedding_primitives.py`)에서 그대로 재사용한다**(신규 seam 0 — 개념·원자·오개념과 같은
임베딩 공간 규약·Fake 주입·지연 로드·CLAUDE.md 로컬 우선).

────────────────────────────────────────────────────────────────────────────
과유사 dedup 게이트 (S2-c 핵심)
────────────────────────────────────────────────────────────────────────────
자체생성 동등문제 생성기(S2-d)가 신규 후보를 코퍼스에 저장하기 *전에*, 후보 발문의 임베딩을
`find_near_duplicates`/`is_near_duplicate`로 기존 코퍼스 벡터와 비교한다. `_NEAR_DUPLICATE_
THRESHOLD`(코사인 0.97) 이상이면 "거의 동일"로 보고 저장을 막는다. 임계값을 **높게(0.97)** 둔
이유: dedup은 *같은 문제의 미세 변형*(숫자만 바꾼 판박이)만 걸러야지, 정당한 유사 문제(같은
개념·다른 구조)까지 억누르면 코퍼스 다양성이 죽는다 — 과잉 억제를 피하려 "거의 동일" 밴드만
좁게 잡는다. 이 게이트는 *조회 함수*일 뿐 적재(`populate`)에 강제 결선하지 않는다 — 언제 부를지는
생성 파이프라인(S2-d) 몫이다(L1은 순수 질의만 소유).

────────────────────────────────────────────────────────────────────────────
임베딩 입력 = 발문(question_text)
────────────────────────────────────────────────────────────────────────────
문제의 *중복 정의축*은 발문이다 — 같은 발문(또는 미세 변형)이면 사실상 같은 문제다. 따라서
임베딩 대상 텍스트는 `question_text`뿐이다(해설·정답·선지는 제외 — 발문이 정체성). 발문이 빈
문제(메타 전용 레코드 등)는 표현이 없어 임베딩 대상에서 제외한다(빈 벡터 방지). 저작권 레일:
학생 노출 본문을 가진 문제는 `source_type=자체생성`뿐이라(`schema/problem.py` 불변식) 발문
임베딩은 자체생성 코퍼스에만 실효 — 평가원/EBS/교과서 레코드는 question_text가 비어 제외된다.

────────────────────────────────────────────────────────────────────────────
sync 엔진 (async 전용 코드베이스에 *벡터 store 좌석에 한정*된 sync 드라이버)
────────────────────────────────────────────────────────────────────────────
앱 본체는 async 전용(asyncpg)이고, 이 좌석만 sync 엔진(psycopg)을 쓴다. 프리미티브
`build_sync_engine`을 *그대로 재사용*한다(신규 빌더 0 — 지연 import·`db_disable_pool` NullPool
가드·register_vector 리스너). sync URL은 `Settings.sync_database_url`·자격증명은 코드에 0(env).

7계층: 이 좌석은 L1 데이터 기반의 *영속/적재/순수 dedup 질의 인프라*다. dedup 게이트를 *언제*
부를지(생성 파이프라인 결선)는 S2-d 생성기 몫이다 — 여기선 저장소·적재·질의만 소유한다.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import TYPE_CHECKING

from whymath_backend.config import Settings, get_settings

# 프리미티브 sync 엔진 빌더 재사용(신규 seam 0) — atom_graph/standards와 동일 좌석.
from whymath_backend.l1.embedding_primitives import (
    build_sync_engine as _build_sync_engine,
)

# 임베딩 provider seam·해시·식별·표현 결합 헬퍼 재사용(신규 금지·CLAUDE.md 로컬 우선) — 개념·
# 원자·오개념과 *같은* 좌석을 쓴다(L1→L1·역방향 의존 0·seam 0·동일 규약).
from whymath_backend.l1.embedding_primitives import (
    embed_changed,
    join_embedding_text,
    provider_model_identity,
    text_hash,
)

if TYPE_CHECKING:
    from sqlalchemy.engine import Engine

    from whymath_backend.l1.embedding_primitives import EmbeddingProvider
    from whymath_backend.schema.problem import Problem

# ──────────────────────────────────────────────────────────────────────────
# 과유사 dedup 임계값 (코사인·"거의 동일" 밴드)
# ──────────────────────────────────────────────────────────────────────────
# 코사인 유사도 ≥ 이 값이면 신규 후보를 기존 문제의 *과유사 변형*(거의 동일)으로 판정한다.
# **0.97로 높게** 둔다 — dedup은 숫자만 바꾼 판박이 같은 *미세 변형*만 걸러야지, 같은 개념의
# 정당한 유사 문제(다른 구조·다른 조건)까지 억누르면 코퍼스 다양성이 죽는다(과잉 억제 회피).
# 0.97 미만(예 0.90대 중반)은 "유사하지만 다른 문제"로 통과시켜 authoring 재량에 맡긴다.
_NEAR_DUPLICATE_THRESHOLD: float = 0.97


def problem_embedding_text(problem: Problem) -> str:
    """문제를 임베딩할 자연어 표현으로 직렬화 — **발문(question_text)만**.

    문제의 중복 정의축은 발문이므로 임베딩 대상은 `question_text`뿐이다(해설·정답·선지 제외).
    프리미티브 `join_embedding_text`로 결합·정규화(NFKC·strip·빈값 skip)한다 — 원자·개념 표현과
    *같은 포맷 계약*(`EMBEDDING_TEXT_FORMAT_VERSION`)을 공유한다. 발문이 None/공백이면 빈
    문자열을 돌려준다(호출자[populate]가 빈 표현을 거른다 — 빈 벡터 방지·안전 처리).
    """
    return join_embedding_text(problem.question_text)


class ProblemEmbeddingIndex:
    """문제 pgvector 영속 인덱스 — `problem_embedding` 테이블 upsert/검색(problem_id PK·sync).

    `AtomEmbeddingIndex`(atom_embedding)의 *문제 코퍼스* 짝이다. `upsert`는 PK 충돌 upsert
    (`INSERT ... ON CONFLICT(problem_id) DO UPDATE`)로 멱등 적재하고, `search`는 코사인 거리
    (`<=>`)로 상위 후보를 찾는다(`similarity = 1 - distance`). **같은 임베딩 공간(provider·model)
    행만** 비교한다(서로 다른 모델 벡터 혼재 방지). sync 엔진은 프리미티브 `build_sync_engine`을
    재사용해 지연 생성·캐시한다(신규 seam 0 — psycopg 연결마다 pgvector 어댑터 등록).

    provider/model은 *임베딩 공간 식별자*다 — 같은 provider라도 model이 다르면 다른 공간으로
    본다. 호출자(적재기·게이트)는 upsert/search에 *같은* provider·model을 일관되게 넘겨야 한다.
    차원 불일치는 pgvector가 적재 시점에 오류로 막는다(컬럼 `vector(N)`).

    atom_embedding과 달리 **subject 축을 두지 않는다** — dedup은 문제 코퍼스 내부 자기-kind
    질의이고 Phase 1 코퍼스가 전량 수학이라 provider·model 필터만으로 충분하다(ORM docstring).
    """

    def __init__(
        self,
        *,
        provider_name: str,
        model_name: str,
        engine: Engine | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._provider_name = provider_name
        self._model_name = model_name
        self._engine = engine
        self._settings = settings

    @property
    def _resolved_settings(self) -> Settings:
        """설정 지연 해석 — 주입 우선, 없으면 캐시된 전역 Settings(atom embedding 패턴)."""
        if self._settings is None:
            self._settings = get_settings()
        return self._settings

    def _get_engine(self) -> Engine:
        """sync 엔진 지연 해석 — 주입 우선, 없으면 프리미티브 빌더로 생성·캐시(신규 seam 0).

        첫 호출에서 `_build_sync_engine(settings)`로 sync 엔진을 만들고 인스턴스에 캐시한다.
        psycopg/SQLAlchemy/pgvector import는 *이 시점*에만 일어난다(모듈 import 깨짐 방지).
        """
        if self._engine is None:
            self._engine = _build_sync_engine(self._resolved_settings)
        return self._engine

    def upsert(self, problem_id: uuid.UUID, vector: Sequence[float], *, source_text: str) -> None:
        """단일 (problem_id, 벡터) upsert (멱등·표현 해시 기록).

        `INSERT ... ON CONFLICT(problem_id) DO UPDATE` — provider/model/dim/text_hash를 함께
        적재한다. 같은 키 재적재는 embedding/provider/model/dim/text_hash를 갱신하되
        **created_at은 SET하지 않아 최초 생성 시각을 보존**한다(멱등·atom_embedding의 updated_at
        갱신과 대비). `source_text`는 임베딩한 *발문*이고, 그 해시만 `text_hash`로 보관한다(원문
        미저장 — 변경 감지용 해시만).
        """
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        from whymath_backend.db.models.problem_embedding import ProblemEmbedding

        values = [float(x) for x in vector]
        stmt = pg_insert(ProblemEmbedding).values(
            problem_id=problem_id,
            embedding=values,
            provider=self._provider_name,
            model=self._model_name,
            dim=len(values),
            text_hash=text_hash(source_text),
        )
        # PK 충돌 시 갱신 — created_at은 보존(생성 시각 불변·SET 제외).
        stmt = stmt.on_conflict_do_update(
            index_elements=[ProblemEmbedding.problem_id],
            set_={
                "embedding": stmt.excluded.embedding,
                "provider": stmt.excluded.provider,
                "model": stmt.excluded.model,
                "dim": stmt.excluded.dim,
                "text_hash": stmt.excluded.text_hash,
            },
        )
        with self._get_engine().begin() as conn:
            conn.execute(stmt)

    def search(self, vector: Sequence[float], *, top_k: int) -> list[tuple[uuid.UUID, float]]:
        """질의 벡터에 대한 코사인 상위 top_k (problem_id, similarity)(유사도 내림차순).

        `1 - (embedding <=> :q)`(코사인 거리→유사도)로 점수를 내고 *같은 provider·model 행만*
        본다(임베딩 공간 일치). top_k<=0이면 빈 리스트. 거리 오름차순 = 유사도 내림차순으로
        정렬·LIMIT. NULL 거리(영벡터 등 정의 불가)는 0 유사도로 안전 처리.

        반환 타입은 단순 튜플 목록이다 — 이 좌석은 L1 dedup groundwork이고, 판정(threshold
        비교)은 `find_near_duplicates`/`is_near_duplicate`가 이 결과 위에 얹는다.
        """
        if top_k <= 0:
            return []
        from sqlalchemy import select

        from whymath_backend.db.models.problem_embedding import ProblemEmbedding

        query = [float(x) for x in vector]
        distance = ProblemEmbedding.embedding.cosine_distance(query)
        stmt = (
            select(
                ProblemEmbedding.problem_id,
                distance.label("distance"),
            )
            .where(
                ProblemEmbedding.provider == self._provider_name,
                ProblemEmbedding.model == self._model_name,
            )
            .order_by(distance)
            .limit(top_k)
        )
        with self._get_engine().connect() as conn:
            rows = conn.execute(stmt).all()
        return [
            (
                row.problem_id,
                (1.0 - float(row.distance)) if row.distance is not None else 0.0,
            )
            for row in rows
        ]

    def existing_text_hashes(self, problem_ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, str]:
        """주어진 problem_id들의 *현행* text_hash를 조회 — {problem_id: text_hash}(단일 SELECT).

        같은 임베딩 공간(provider·model)의 행만 본다(다른 공간은 재임베딩 필요라 미포함=변경
        취급). 적재기 skip-if-unchanged용(atom_embedding 동형). 빈 입력은 쿼리 없이 {}.
        """
        if not problem_ids:
            return {}
        from sqlalchemy import select

        from whymath_backend.db.models.problem_embedding import ProblemEmbedding

        stmt = select(ProblemEmbedding.problem_id, ProblemEmbedding.text_hash).where(
            ProblemEmbedding.problem_id.in_(list(dict.fromkeys(problem_ids))),
            ProblemEmbedding.provider == self._provider_name,
            ProblemEmbedding.model == self._model_name,
        )
        with self._get_engine().connect() as conn:
            rows = conn.execute(stmt).all()
        return {row.problem_id: row.text_hash for row in rows}


# ──────────────────────────────────────────────────────────────────────────
# 과유사 dedup 게이트 (순수 질의 함수 — 적재 비강제·authoring/생성 시점 조회)
# ──────────────────────────────────────────────────────────────────────────
def find_near_duplicates(
    index: ProblemEmbeddingIndex,
    vector: Sequence[float],
    *,
    threshold: float = _NEAR_DUPLICATE_THRESHOLD,
    top_k: int = 5,
    exclude_problem_id: uuid.UUID | None = None,
) -> list[tuple[uuid.UUID, float]]:
    """후보 벡터가 기존 코퍼스의 *과유사 변형*인 문제들을 찾는다(코사인 ≥ threshold).

    `index.search`로 상위 `top_k` 후보를 받은 뒤 similarity ≥ `threshold`(기본 0.97·"거의 동일"
    밴드)만 남긴다. `exclude_problem_id`(자기 자신 — 기존 문제 *갱신* 시 자기 행이 최상위로 잡히는
    것을 배제)는 결과에서 뺀다. 반환은 (problem_id, similarity) 유사도 내림차순 목록(비어 있으면
    과유사 없음). 순수 질의 함수 — 적재에 강제 결선하지 않는다(생성 파이프라인이 저장 전 호출).
    """
    hits = index.search(vector, top_k=top_k)
    return [(pid, sim) for pid, sim in hits if sim >= threshold and pid != exclude_problem_id]


def is_near_duplicate(
    index: ProblemEmbeddingIndex,
    vector: Sequence[float],
    *,
    threshold: float = _NEAR_DUPLICATE_THRESHOLD,
    top_k: int = 5,
    exclude_problem_id: uuid.UUID | None = None,
) -> bool:
    """후보 벡터가 기존 코퍼스에 과유사 변형을 가지면 True(저장 차단 게이트).

    `find_near_duplicates` 결과가 비어 있지 않으면 True. S2-d 생성기가 신규 동등문제 후보를
    코퍼스에 저장하기 *전에* 이 게이트로 과유사 남발을 막는다(True면 저장 거부·재생성 유도).
    """
    return bool(
        find_near_duplicates(
            index,
            vector,
            threshold=threshold,
            top_k=top_k,
            exclude_problem_id=exclude_problem_id,
        )
    )


def populate_problem_embeddings(
    problems: Sequence[Problem],
    provider: EmbeddingProvider,
    *,
    settings: Settings | None = None,
    index: ProblemEmbeddingIndex | None = None,
) -> int:
    """문제 발문을 임베딩해 `ProblemEmbeddingIndex`에 멱등 upsert 적재(dedup 코퍼스 사전 임베딩).

    `populate_atom_embeddings`의 *문제 코퍼스* 짝이다 — 각 문제의 발문 표현(`problem_embedding_
    text`)을 임베딩해 problem_id 키로 upsert한다. provider/model은 임베딩 공간 식별자로 행에
    박히고, 같은 공간만 search/게이트가 본다. 발문이 빈 문제는 제외한다(빈 벡터 방지). 멱등
    (재실행 시 갱신).

    **skip-if-unchanged(비용 절감·CLAUDE.md #6·atom_embedding 동형)**: 적재 전 현행 `text_hash`를
    조회해 발문이 *바뀐 문제만* 임베딩·upsert한다. provider/model이 다르면 재임베딩. 반환은
    *실제 적재한(변경분)* 수. skip-if-unchanged 코어는 레이어-중립 프리미티브(`embed_changed`)가
    소유한다(개념·원자·오개념 공유·중복 제거) — 키는 problem_id의 문자열 표현이고, 경계에서
    UUID↔str을 변환한다(embed_changed는 str 키 계약).

    provider의 model 이름은 *Settings*에서 해석한다(`provider_model_identity` 재사용 —
    local→embedding_model_local·openai→embedding_model_openai·fake→fake-hash). review_status
    무관 전량 적재(dedup 게이팅은 조회 몫).
    """
    resolved = settings if settings is not None else get_settings()
    provider_name, model_name = provider_model_identity(provider, resolved)
    idx = (
        index
        if index is not None
        else ProblemEmbeddingIndex(
            provider_name=provider_name, model_name=model_name, settings=resolved
        )
    )

    # 발문이 빈 문제는 제외(빈 벡터 방지) 후 (problem_id 문자열, 발문 표현) 목록 구성.
    items: list[tuple[str, str]] = []
    for problem in problems:
        text = problem_embedding_text(problem)
        if not text:
            continue
        items.append((str(problem.problem_id), text))

    def _existing(keys: Sequence[str]) -> dict[str, str]:
        # str 키 → UUID로 복원해 인덱스 조회하고, 결과를 다시 str 키로 되돌린다(embed_changed 계약).
        found = idx.existing_text_hashes([uuid.UUID(k) for k in keys])
        return {str(pid): h for pid, h in found.items()}

    def _upsert(key: str, vec: list[float], text: str) -> None:
        idx.upsert(uuid.UUID(key), vec, source_text=text)

    return embed_changed(
        items,
        provider=provider,
        existing_hashes=_existing,
        upsert=_upsert,
        item_noun="문제",
    )


__all__ = [
    "ProblemEmbeddingIndex",
    "find_near_duplicates",
    "is_near_duplicate",
    "populate_problem_embeddings",
    "problem_embedding_text",
]
