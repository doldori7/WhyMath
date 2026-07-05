"""거버넌스 동결 — 임베딩 namespace = 테이블(kind) × subject (과목 확장 S1·invariant ⑨).

`l1/embedding_primitives.py` namespace 불변식을 코드로 동결한다(`test_edge_relation_governance.py`
선례 — enum·적재 거버넌스를 한곳에 묶는 스타일). 네 갈래:

  ① **스키마 계약**: 세 임베딩 ORM(`MisconceptionEmbedding`·`ConceptEmbedding`·`AtomEmbedding`)
     전부 subject 컬럼 보유·NOT NULL·server_default가 `DEFAULT_EMBEDDING_SUBJECT`('수학')와
     일치(단일 진실·드리프트 0). kind/namespace 컬럼은 *없음*(테이블명이 kind를 함의 — 기각 동결).
  ② **대칭 게이트(9지점)**: 세 인덱스의 search·existing_text_hashes·upsert가 *전부* subject
     스코프를 건다 — 가짜 엔진으로 컴파일된 SQL에 subject 술어/컬럼이 있는지 3인덱스 × 3경로
     전수 확인(한 지점이라도 누락되면 즉시 red — 교과 혼입의 조용한 구멍 차단).
  ③ **cross-table 코사인 금지 게이트**: `.cosine_distance(` 사용 모듈을 소스 스캔해 3개 인덱스
     모듈 allowlist로 고정 — 서로 다른 kind 테이블 간 SQL 코사인 join은 이 테스트를 *의식적으로*
     수정해야만 가능하다. (`crosslink_candidates.py`의 in-memory `cosine_similarity` 교차는
     오개념 도메인 내부 휴리스틱이라 예외 — DB 질의 경계를 넘지 않으며 이 스캔에 안 잡힌다.)
  ④ **텍스트 불변 계약(재임베딩 0 보증)**: 세 임베딩 텍스트 빌더 출력에 subject가 유입되지
     않고, text_hash가 인덱스 subject와 무관하다 — subject는 컬럼/스코프에만 들어간다
     (`EMBEDDING_TEXT_FORMAT_VERSION==2` 불변·기존 벡터 전량 유효).

hermetic: DB 불요(ORM 메타데이터·가짜 엔진 컴파일·소스 스캔만).
"""

from __future__ import annotations

from pathlib import Path
from types import TracebackType

from whymath_backend.db.models.atom_embedding import AtomEmbedding
from whymath_backend.db.models.concept_embedding import ConceptEmbedding
from whymath_backend.db.models.misconception_embedding import MisconceptionEmbedding
from whymath_backend.l1.atom_graph.embedding import AtomEmbeddingIndex, atom_embedding_text
from whymath_backend.l1.concept_graph.embedding import (
    ConceptEmbeddingIndex,
    concept_embedding_text,
)
from whymath_backend.l1.embedding_primitives import (
    DEFAULT_EMBEDDING_SUBJECT,
    EMBEDDING_TEXT_FORMAT_VERSION,
    join_embedding_text,
    text_hash,
)
from whymath_backend.l4.misconception.catalog import CATALOG
from whymath_backend.l4.misconception.semantic.matcher import catalog_text
from whymath_backend.l4.misconception.semantic.pgvector_index import PgVectorIndex

# 세 임베딩 ORM — kind(자산 종류)는 *테이블명이 함의*한다(별도 컬럼 기각·docstring ①).
# 관점(2026-07-04·S0-4b): `ConceptEmbedding`(구 437 `concept_embedding`)은 `legacy_snapshot`으로
# 격하됐다(런타임 검색은 원자 임베딩을 읽음). 단 namespace 불변식(subject 스코프·cross-table 코사인
# 금지)은 스냅샷 테이블에도 그대로 유효하므로 여기 3-ORM 대칭 검사에서 계속 동결한다(로직 불변).
_EMBEDDING_MODELS = (MisconceptionEmbedding, ConceptEmbedding, AtomEmbedding)


# ──────────────────────────────────────────────────────────────────────────
# 가짜 sync 엔진 — begin()/connect() 컨텍스트 + execute() (PG 없이 SQL 컴파일 캡처)
# (test_concept_embedding.py `_FakeEngine` 선례 — 여기선 statement 기록만 필요)
# ──────────────────────────────────────────────────────────────────────────
class _FakeResult:
    def all(self) -> list[object]:
        return []


class _FakeConnection:
    def __init__(self, engine: _FakeEngine) -> None:
        self._engine = engine

    def __enter__(self) -> _FakeConnection:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        return None

    def execute(self, statement: object) -> _FakeResult:
        self._engine.executed.append(statement)
        return _FakeResult()


class _FakeEngine:
    def __init__(self) -> None:
        self.executed: list[object] = []

    def begin(self) -> _FakeConnection:
        return _FakeConnection(self)

    def connect(self) -> _FakeConnection:
        return _FakeConnection(self)


def _compile(statement: object) -> str:
    """SQLAlchemy statement를 PostgreSQL dialect로 컴파일한 SQL 문자열(검사용)."""
    from sqlalchemy.dialects import postgresql

    return str(statement.compile(dialect=postgresql.dialect()))  # type: ignore[attr-defined]


def _compiled_params(statement: object) -> dict[str, object]:
    """컴파일된 statement의 바인딩 파라미터(컬럼값 관찰용)."""
    from sqlalchemy.dialects import postgresql

    return dict(statement.compile(dialect=postgresql.dialect()).params)  # type: ignore[attr-defined]


# 세 인덱스의 (생성자, 테이블명, upsert 호출자) — 대칭 게이트 스윕 대상.
# upsert 호출자: PgVectorIndex는 `upsert_entry(key, vec, source_text=)`, L1 두 인덱스는
# `upsert(key, vec, source_text=)`(시그니처만 다르고 SQL 구성은 동형).
def _make_indexes(subject: str | None = None) -> list[tuple[object, str, _FakeEngine]]:
    """가짜 엔진을 주입한 세 인덱스 + 테이블명 + 엔진(검사용) 목록."""
    kwargs: dict[str, object] = {"provider_name": "fake", "model_name": "fake-hash"}
    if subject is not None:
        kwargs["subject"] = subject
    out: list[tuple[object, str, _FakeEngine]] = []
    for cls, table in (
        (PgVectorIndex, "misconception_embedding"),
        (ConceptEmbeddingIndex, "concept_embedding"),
        (AtomEmbeddingIndex, "atom_embedding"),
    ):
        engine = _FakeEngine()
        index = cls(engine=engine, **kwargs)  # type: ignore[arg-type]  # 가짜 엔진(구조만 충족)
        out.append((index, table, engine))
    return out


def _run_upsert(index: object, key: str, source_text: str) -> None:
    """세 인덱스의 upsert를 시그니처 차이 무관하게 호출(PgVector=upsert_entry·L1=upsert)."""
    if isinstance(index, PgVectorIndex):
        index.upsert_entry(key, [0.1, 0.2], source_text=source_text)
    else:
        index.upsert(key, [0.1, 0.2], source_text=source_text)  # type: ignore[attr-defined]


# ──────────────────────────────────────────────────────────────────────────
# ① 스키마 계약 — subject 컬럼·NOT NULL·server_default = DEFAULT_EMBEDDING_SUBJECT
# ──────────────────────────────────────────────────────────────────────────
class TestSchemaContract:
    def test_default_subject_single_truth_is_math(self) -> None:
        """단일 진실 상수 자체 동결 — '수학'(교과 레벨·CurriculumEntry.subject와 동일 축)."""
        assert DEFAULT_EMBEDDING_SUBJECT == "수학"

    def test_all_embedding_models_have_subject_column(self) -> None:
        """세 ORM 전부 subject 컬럼 보유·NOT NULL·server_default가 상수와 일치(드리프트 0)."""
        for model in _EMBEDDING_MODELS:
            col = model.__table__.columns["subject"]
            assert col.nullable is False, f"{model.__tablename__}.subject는 NOT NULL이어야 한다"
            assert (
                col.server_default is not None
            ), f"{model.__tablename__}.subject는 server_default(기존 행 백필)가 있어야 한다"
            assert col.server_default.arg == DEFAULT_EMBEDDING_SUBJECT, (
                f"{model.__tablename__}.subject server_default가 DEFAULT_EMBEDDING_SUBJECT와 "
                "다르다(단일 진실 드리프트)"
            )

    def test_no_kind_or_namespace_column(self) -> None:
        """kind/namespace 컬럼 기각 동결 — 테이블명이 이미 kind를 함의한다(중복 축 금지)."""
        for model in _EMBEDDING_MODELS:
            names = set(model.__table__.columns.keys())
            assert "kind" not in names
            assert "namespace" not in names


# ──────────────────────────────────────────────────────────────────────────
# ② 대칭 게이트 — 3인덱스 × 3경로(search·existing_text_hashes·upsert) = 9지점 전수
# ──────────────────────────────────────────────────────────────────────────
class TestSubjectScopeSymmetry:
    def test_search_filters_subject_in_all_three_indexes(self) -> None:
        """search WHERE에 subject 술어 — 3인덱스 전수(누락 시 교과 혼입 랭킹)."""
        for index, table, engine in _make_indexes():
            index.search([1.0, 0.0], top_k=3)  # type: ignore[attr-defined]
            assert len(engine.executed) == 1, f"{table}: search가 statement 1건이어야 한다"
            compiled = _compile(engine.executed[0])
            assert f"{table}.subject" in compiled, f"{table}: search WHERE에 subject 술어 누락"

    def test_existing_text_hashes_filters_subject_in_all_three_indexes(self) -> None:
        """existing_text_hashes WHERE에 subject 술어 — 3인덱스 전수(누락 시 skip 오판)."""
        for index, table, engine in _make_indexes():
            index.existing_text_hashes(["k1", "k2"])  # type: ignore[attr-defined]
            assert len(engine.executed) == 1
            compiled = _compile(engine.executed[0])
            assert (
                f"{table}.subject" in compiled
            ), f"{table}: existing_text_hashes WHERE에 subject 술어 누락"

    def test_upsert_writes_subject_in_all_three_indexes(self) -> None:
        """upsert INSERT 컬럼 + ON CONFLICT SET에 subject — 3인덱스 전수(누락 시 라벨 미기록)."""
        for index, table, engine in _make_indexes():
            _run_upsert(index, "key-1", "표현")
            assert len(engine.executed) == 1
            compiled = _compile(engine.executed[0])
            assert f"INSERT INTO {table}" in compiled
            # INSERT 컬럼 목록에 subject 포함(값 바인딩) + 충돌 갱신 SET에도 subject 포함.
            assert "subject" in compiled, f"{table}: upsert에 subject 컬럼 누락"
            assert (
                "subject = excluded.subject" in compiled
            ), f"{table}: ON CONFLICT SET에 subject 누락(재적재 시 라벨 stale)"
            # 바인딩 값이 인덱스 subject(기본 '수학')다.
            assert _compiled_params(engine.executed[0])["subject"] == DEFAULT_EMBEDDING_SUBJECT

    def test_custom_subject_flows_to_all_nine_points(self) -> None:
        """생성자 subject('물리')가 9지점 전부에 흐른다 — 값 바인딩까지 관찰(스코프 실효성)."""
        for index, _table, engine in _make_indexes(subject="물리"):
            index.search([1.0], top_k=1)  # type: ignore[attr-defined]
            index.existing_text_hashes(["k"])  # type: ignore[attr-defined]
            _run_upsert(index, "key-1", "표현")
            search_stmt, existing_stmt, upsert_stmt = engine.executed
            # WHERE 술어 바인딩 값 — search·existing 둘 다 '물리'.
            assert "물리" in _compiled_params(search_stmt).values()
            assert "물리" in _compiled_params(existing_stmt).values()
            # upsert 컬럼 값 — '물리'.
            assert _compiled_params(upsert_stmt)["subject"] == "물리"


# ──────────────────────────────────────────────────────────────────────────
# ③ cross-table 코사인 금지 게이트 — `.cosine_distance(` 사용 모듈 allowlist 동결
# ──────────────────────────────────────────────────────────────────────────
# DB 코사인(`<=>`·cosine_distance)을 쓸 수 있는 모듈은 *자기 kind 테이블 전용* 인덱스 3개뿐이다.
# 새 모듈이 cosine_distance를 쓰면(특히 cross-table join) 이 allowlist를 *의식적으로* 수정해야
# 한다 — 그 리뷰 시점이 곧 namespace 경계 심사다. (in-memory `cosine_similarity`는 별개 —
# crosslink_candidates의 오개념 도메인 내부 교차는 DB 질의 경계를 넘지 않아 예외로 명문.)
_COSINE_DISTANCE_ALLOWLIST: frozenset[str] = frozenset(
    {
        "l4/misconception/semantic/pgvector_index.py",
        "l1/concept_graph/embedding.py",
        "l1/atom_graph/embedding.py",
    }
)


def test_cosine_distance_usage_frozen_to_three_index_modules() -> None:
    """`.cosine_distance(` 소스 스캔 — 사용 모듈이 정확히 3개 인덱스 모듈(추가·누락 모두 red)."""
    import whymath_backend

    package_root = Path(whymath_backend.__file__).parent
    users: set[str] = set()
    for path in sorted(package_root.rglob("*.py")):
        if ".cosine_distance(" in path.read_text(encoding="utf-8"):
            users.add(path.relative_to(package_root).as_posix())
    assert users == set(_COSINE_DISTANCE_ALLOWLIST), (
        "DB 코사인(cosine_distance) 사용 모듈이 allowlist와 다릅니다 — cross-table 코사인 금지 "
        f"(namespace 불변식). 발견: {sorted(users)} / 허용: {sorted(_COSINE_DISTANCE_ALLOWLIST)}. "
        "새 교차 질의가 정당하다면 embedding_primitives.py 불변식과 이 allowlist를 함께 개정하라."
    )


# ──────────────────────────────────────────────────────────────────────────
# ④ 텍스트 불변 계약 — subject는 컬럼/스코프에만·임베딩 텍스트엔 절대 미유입(재임베딩 0)
# ──────────────────────────────────────────────────────────────────────────
class TestEmbeddingTextInvariance:
    def test_format_version_frozen_at_v2(self) -> None:
        """포맷 계약 버전 불변 — subject 축 도입이 텍스트 포맷을 건드리지 않았다."""
        assert EMBEDDING_TEXT_FORMAT_VERSION == 2

    def test_concept_text_builder_output_has_no_subject(self) -> None:
        """개념 표현 = 안전 필드 결합 그대로(subject 미포함) — 정확 일치로 동결."""
        text = concept_embedding_text(name_ko="극한", intuition="다가감", representations="수렴")
        assert text == "극한. 다가감. 수렴"
        assert DEFAULT_EMBEDDING_SUBJECT not in text

    def test_atom_text_builder_output_has_no_subject(self) -> None:
        """원자 표현 = name+transfer 결합 그대로(subject 미포함) — 정확 일치로 동결."""
        text = atom_embedding_text(name_ko="기수 원리", transfer="세는 방법의 핵심")
        assert text == "기수 원리. 세는 방법의 핵심"
        assert DEFAULT_EMBEDDING_SUBJECT not in text

    def test_catalog_text_is_exactly_safe_field_join_for_all_entries(self) -> None:
        """오개념 표현 = name_kr+canonical_statement 결합 그대로 — 전 카탈로그 정확 일치.

        ('수학' 부재 단언 대신 *정확 일치*로 동결한다 — canonical_statement가 자연어라 '수학'을
        본문으로 포함할 수 있어 부재 단언은 거짓 양성 위험. 결합식 일치가 곧 subject 미주입 증명.)
        """
        for m in CATALOG:
            assert catalog_text(m) == join_embedding_text(m.name_kr, m.canonical_statement)

    def test_text_hash_is_independent_of_index_subject(self) -> None:
        """text_hash가 인덱스 subject와 무관 — 같은 표현이면 '수학'/'물리' 어느 스코프든 동일
        해시(subject 전환이 재임베딩을 유발하지 않는다·기존 벡터 전량 유효)."""
        source = "극한. 다가감. 수렴"
        expected = text_hash(source)
        for subject in (None, "물리"):
            for index, _table, engine in _make_indexes(subject=subject):
                _run_upsert(index, "key-1", source)
                assert _compiled_params(engine.executed[0])["text_hash"] == expected


# ──────────────────────────────────────────────────────────────────────────
# 기본값 흡수 — populate·조회 좌석은 무수정(파라미터 관통 금지)으로 수학 스코프
# ──────────────────────────────────────────────────────────────────────────
def test_default_constructed_indexes_scope_to_math() -> None:
    """subject 미지정 생성 = '수학' 스코프 — 기존 호출자(populate 3벌·matcher·search_concepts)가
    시그니처 무변경으로 흡수함을 동결(관통 파라미터 금지 설계)."""
    for index, _table, _engine in _make_indexes():
        assert index._subject == DEFAULT_EMBEDDING_SUBJECT  # type: ignore[attr-defined]


def test_populate_and_query_seams_have_no_subject_parameter() -> None:
    """populate 3벌·조회 좌석 시그니처에 subject 파라미터가 *없음*을 동결(관통 금지)."""
    import inspect

    from whymath_backend.l1.atom_graph.embedding import populate_atom_embeddings
    from whymath_backend.l1.concept_graph.embedding import populate_concept_embeddings
    from whymath_backend.l1.concept_graph.retrieval import search_concepts
    from whymath_backend.l4.misconception.semantic.pgvector_index import populate_pgvector

    for fn in (
        populate_pgvector,
        populate_concept_embeddings,
        populate_atom_embeddings,
        search_concepts,
    ):
        params = set(inspect.signature(fn).parameters)
        assert "subject" not in params, (
            f"{fn.__name__}: subject는 인덱스 생성자 기본값으로 흡수한다 — 파라미터 관통 금지. "
            "비수학 적재가 필요하면 subject를 지정한 인덱스를 index=로 주입하라."
        )
