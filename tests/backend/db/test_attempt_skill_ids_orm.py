"""EOS-57 — `attempt_event.skill_ids[]` 영속 계약 (DB 연결 없이).

기존 테이블 ALTER형 태스크라 검증 축은 EOS-48(`test_event_time_active_time_orm.py`)과 동형이다:
**비파괴**(nullable·server_default 없음 — 기존 행/writer 무영향·백필 날조 방지)와 **round-trip
정합**(신규 ORM 컬럼이 Pydantic schema에 대응 필드를 가져 `to_schema`가 extra='forbid'에서
깨지지 않음)을 못박는다.

여기에 이 태스크 고유의 축 하나가 더 붙는다 — **None ≠ []**. 이 구분이 무너지면 기록률
리포트가 "writer가 안 돌았다"(미기록)와 "돌았는데 해소 0건"(실측)을 같은 글자로 말하게 되고,
"작동한 비율" 원칙(CLAUDE.md)이 데이터 층에서부터 측정 불가가 된다.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path

from whymath_backend.db.models.activity import AttemptEvent
from whymath_backend.schema.activity import AttemptEvent as AttemptEventSchema
from whymath_backend.schema.enums import EventType

_REPO_ROOT = Path(__file__).resolve().parents[3]
_VERSIONS_DIR = _REPO_ROOT / "src" / "backend" / "alembic" / "versions"
_MIGRATION_GLOB = "*attempt_event_skill_ids.py"


class TestNonDestructiveColumn:
    def test_skill_ids_nullable_without_server_default(self) -> None:
        """nullable + server_default 없음 — 기존 행 백필 0.

        `DEFAULT '{}'::text[]`를 달면 기존 행 전체가 "해소 0건"으로 채워져 미기록과 구분이
        사라진다(EOS-48이 시각 컬럼에서 막은 것과 같은 날조 유형).
        """
        column = AttemptEvent.__table__.columns["skill_ids"]
        assert column.nullable is True
        assert column.server_default is None
        assert len(column.foreign_keys) == 0  # 배열 느슨참조(이 테이블의 기존 3 참조와 동형)

    def test_existing_columns_untouched(self) -> None:
        """기존 컬럼 불변 — 복합 PK·event_at NOT NULL 그대로(기존 소비자 회귀 0의 근거)."""
        assert AttemptEvent.__table__.columns["event_at"].nullable is False
        assert AttemptEvent.__table__.columns["event_at"].primary_key is True
        assert AttemptEvent.__table__.columns["event_id"].primary_key is True
        assert AttemptEvent.__table__.columns["event_data"].nullable is True


class TestNoneIsNotEmpty:
    """미기록(None)과 해소 0건([])은 round-trip 전 구간에서 다른 값으로 남는다."""

    def test_unrecorded_stays_none(self) -> None:
        schema = AttemptEventSchema(
            event_at=datetime(2026, 9, 1, 1, 0, tzinfo=UTC),
            event_type=EventType.검산결과,  # 이 축을 쓰지 않는 이벤트 → 미기록
            user_id=uuid.uuid4(),
        )
        restored = AttemptEvent.from_schema(schema).to_schema()
        assert restored.skill_ids is None  # []로 승격되지 않는다

    def test_resolved_zero_stays_empty_list(self) -> None:
        schema = AttemptEventSchema(
            event_at=datetime(2026, 9, 1, 1, 0, tzinfo=UTC),
            event_type=EventType.문제시도,
            user_id=uuid.uuid4(),
            skill_ids=[],  # 해소는 실행됐고 매핑이 0건
        )
        restored = AttemptEvent.from_schema(schema).to_schema()
        assert restored.skill_ids == []  # None으로 접히지 않는다
        assert restored.skill_ids is not None

    def test_resolved_ids_round_trip_preserves_order(self) -> None:
        ids = ["skill.factorization", "skill.quadratic-formula"]
        schema = AttemptEventSchema(
            event_at=datetime(2026, 9, 1, 1, 0, tzinfo=UTC),
            event_type=EventType.문제시도,
            user_id=uuid.uuid4(),
            skill_ids=ids,
        )
        restored = AttemptEvent.from_schema(schema).to_schema()
        assert restored.skill_ids == ids
        assert "skill_ids" in restored.model_dump()  # export payload 노출 전제


class TestMigrationFile:
    def test_migration_adds_column_and_enum_value_symmetrically(self) -> None:
        """EOS-57 마이그레이션 존재·add/drop 대칭·upgrade 구간 server_default 0건."""
        matches = list(_VERSIONS_DIR.glob(_MIGRATION_GLOB))
        assert len(matches) == 1, "EOS-57 마이그레이션 파일이 정확히 1개여야 한다"
        source = matches[0].read_text(encoding="utf-8")
        assert "ALTER TYPE event_type_enum ADD VALUE IF NOT EXISTS '문제시도'" in source
        assert '"skill_ids"' in source
        assert 'op.drop_column("attempt_event", "skill_ids")' in source
        upgrade_src = source.split("def upgrade()")[1].split("def downgrade()")[0]
        # 백필 날조 방지(핵심 비파괴 계약) — 키워드 인자 형태로 검사한다. 맨 substring은
        # 이 규약을 *설명하는 주석*에도 걸려 변별력이 없다(정상 상태에서 실패한다).
        assert "server_default=" not in upgrade_src

    def test_no_table_or_constraint_mutation(self) -> None:
        """컬럼 add/drop + enum add만 — 테이블·제약 변경 0건(hypertable 전환과 무충돌)."""
        source = next(_VERSIONS_DIR.glob(_MIGRATION_GLOB)).read_text(encoding="utf-8")
        assert "op.create_table(" not in source
        assert "op.drop_table(" not in source
        assert "op.create_unique_constraint(" not in source
        assert "op.drop_constraint(" not in source

    def test_chain_is_linear_on_the_single_head(self) -> None:
        """체인 조율(acceptance ①) — EOS-54(84c782415837) 위에 선형으로 쌓인다.

        저장소는 단일 head 관례다. 작성 시점 부모는 EOS-48(c9bc2555282e)이었으나 main에 EOS-54가
        먼저 착지해 브랜치 head 2개가 됐고, 재부모화로 선형화했다(두 리비전은 건드리는 객체가
        겹치지 않아 순서 의존 0 — 마이그레이션 docstring). 형제 EOS-47이 브랜치 head를 만들지
        않도록 down_revision을 이름으로 동결한다.
        """
        source = next(_VERSIONS_DIR.glob(_MIGRATION_GLOB)).read_text(encoding="utf-8")
        assert 'down_revision: str | None = "84c782415837"' in source
