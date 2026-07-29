"""EvidenceEvent(L2) ORM 단위테스트 — DB 연결 *없이* 검증(hermetic·PG 0).

검토서 B1(미성년 원문 발화 평문 저장 금지·봉투 암호화)·H3(attempt_event 선례 복합 PK·느슨참조)를
잠근다. attempt_event/dialogue ORM 테스트 패턴 답습.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateIndex, CreateTable
from whymath_backend.db.base import Base
from whymath_backend.db.models.evidence_event import EvidenceEvent


def _pg_ddl(table: object) -> str:
    return str(CreateTable(table).compile(dialect=postgresql.dialect()))  # type: ignore[arg-type]


# ──────────────────────────────────────────────────────────────────────────
# 1) 등록 + 테이블명
# ──────────────────────────────────────────────────────────────────────────
def test_evidence_event_registered_in_metadata() -> None:
    """Base.metadata에 evidence_event가 등록돼 있다(alembic 인식 전제)."""
    assert "evidence_event" in Base.metadata.tables
    assert EvidenceEvent.__tablename__ == "evidence_event"


# ──────────────────────────────────────────────────────────────────────────
# 2) 복합 PK (event_id BigInteger autoincrement, time) — attempt_event 선례
# ──────────────────────────────────────────────────────────────────────────
def test_composite_pk_bigint_and_time() -> None:
    """PK는 (event_id, time)·event_id는 BigInteger autoincrement(DB-assigned)."""
    pk = [c.name for c in EvidenceEvent.__table__.primary_key.columns]
    assert pk == ["event_id", "time"]
    event_id = EvidenceEvent.__table__.c.event_id
    assert isinstance(event_id.type, sa.BigInteger)
    ddl = _pg_ddl(EvidenceEvent.__table__)
    assert "PRIMARY KEY (event_id, time)" in ddl


# ──────────────────────────────────────────────────────────────────────────
# 3) B1 — 봉투 암호화 컬럼 존재·평문 원문(payload) 부재·메타만 평문
# ──────────────────────────────────────────────────────────────────────────
def test_b1_encrypted_payload_columns_exist() -> None:
    """B1: payload_encrypted/payload_nonce(BYTEA)·retention_until(TIMESTAMPTZ) 존재."""
    cols = EvidenceEvent.__table__.c
    assert isinstance(cols.payload_encrypted.type, sa.LargeBinary)
    assert isinstance(cols.payload_nonce.type, sa.LargeBinary)
    assert isinstance(cols.retention_until.type, sa.DateTime)
    ddl = _pg_ddl(EvidenceEvent.__table__)
    assert "payload_encrypted BYTEA" in ddl
    assert "payload_nonce BYTEA" in ddl
    assert "retention_until TIMESTAMP WITH TIME ZONE" in ddl


def test_b1_no_plaintext_utterance_payload_column() -> None:
    """B1(핵심): 평문 원문 발화 컬럼('payload')이 *없다*. 비민감 메타만 평문(meta JSONB)."""
    cols = set(EvidenceEvent.__table__.c.keys())
    # 원본 draft의 평문 payload JSONB는 폐기됨 — 존재하면 CLAUDE.md NEVER 위반.
    assert "payload" not in cols
    assert "meta" in cols
    assert isinstance(EvidenceEvent.__table__.c.meta.type, postgresql.JSONB)


# ──────────────────────────────────────────────────────────────────────────
# 4) 느슨참조 (하이퍼테이블 FK 회피) + k_type native enum
# ──────────────────────────────────────────────────────────────────────────
def test_no_foreign_keys_loose_ref() -> None:
    """objective_id/session_id는 FK가 아니다(하이퍼테이블 느슨참조)·둘 다 NOT NULL."""
    assert len(EvidenceEvent.__table__.foreign_keys) == 0
    ddl = _pg_ddl(EvidenceEvent.__table__)
    assert "REFERENCES" not in ddl
    assert EvidenceEvent.__table__.c.session_id.nullable is False
    assert EvidenceEvent.__table__.c.objective_id.nullable is False
    assert isinstance(EvidenceEvent.__table__.c.objective_id.type, sa.Text)


def test_k_type_native_enum() -> None:
    """k_type은 native enum 'knowledge_type'(7유형)이다."""
    ktype = EvidenceEvent.__table__.c.k_type.type
    assert ktype.name == "knowledge_type"  # type: ignore[attr-defined]
    assert len(ktype.enums) == 7  # type: ignore[attr-defined]


# ──────────────────────────────────────────────────────────────────────────
# 5) 점수 CHECK + DESC 인덱스
# ──────────────────────────────────────────────────────────────────────────
def test_judge_fidelity_checks() -> None:
    """judge_score·fidelity_score는 0~3 CHECK(nullable 허용)."""
    ddl = _pg_ddl(EvidenceEvent.__table__)
    assert "judge_score IS NULL OR judge_score BETWEEN 0 AND 3" in ddl
    assert "fidelity_score IS NULL OR fidelity_score BETWEEN 0 AND 3" in ddl


def test_idx_ev_obj_time_desc() -> None:
    """idx_ev_obj_time은 (objective_id, time DESC) 인덱스다(idx_session_user 선례)."""
    ix = next(i for i in EvidenceEvent.__table__.indexes if i.name == "idx_ev_obj_time")
    ddl = str(CreateIndex(ix).compile(dialect=postgresql.dialect()))
    assert "objective_id" in ddl
    assert "time DESC" in ddl
