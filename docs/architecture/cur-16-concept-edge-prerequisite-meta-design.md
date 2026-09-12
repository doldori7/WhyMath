# CUR-16 ConceptEdge prerequisite 메타 확장 설계

> **상태**: 설계 중 (2026-08-25)  
> **범위**: `ConceptEdge` 테이블에 EOS 6_개념 DB 검토 §13의 prerequisite 메타를 추가  
> **연관**: `docs/architecture/eos_concept_db_review_adr.md` §2.11, `src/backend/whymath_backend/schema/concept.py`, `src/backend/whymath_backend/db/models/concept.py`

---

## 1. 현행 구조 실측

### 1.1 Pydantic Schema (`src/backend/whymath_backend/schema/concept.py`)

```python
class ConceptEdge(BaseModel):
    edge_id: uuid.UUID
    from_concept_id: uuid.UUID
    to_concept_id: uuid.UUID
    edge_type: EdgeType
    edge_strength: float | None      # 0-1
    typical_gap_signal: str | None
    notes: str | None
    relation_subtype: str | None
    created_at: datetime | None
```

- `extra="forbid"` — 새 필드 추가 시 existing data와의 호환성을 위해 default 값을 반드시 설정.
- 자기 자신 가리키는 엣지 금지: `_no_self_edge`.

### 1.2 ORM (`src/backend/whymath_backend/db/models/concept.py`)

```python
class ConceptEdge(Base):
    edge_id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, primary_key=True, ...)
    from_concept_id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, sa.ForeignKey("concept.concept_id"), nullable=False)
    to_concept_id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, sa.ForeignKey("concept.concept_id"), nullable=False)
    edge_type: Mapped[EdgeType] = mapped_column(_pg_enum(EdgeType, "edge_type_enum"), nullable=False)
    edge_strength: Mapped[float | None] = mapped_column(sa.Numeric(3, 2))
    typical_gap_signal: Mapped[str | None] = mapped_column(sa.Text)
    notes: Mapped[str | None] = mapped_column(sa.Text)
    relation_subtype: Mapped[str | None] = mapped_column(sa.Text)
    created_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now())

    __table_args__ = (
        sa.UniqueConstraint("from_concept_id", "to_concept_id", "edge_type"),
        sa.Index("idx_concept_edge_from", "from_concept_id", "edge_type"),
        sa.Index("idx_concept_edge_to", "to_concept_id", "edge_type"),
    )
```

### 1.3 EdgeType Enum (`src/backend/whymath_backend/schema/enums.py`)

```python
class EdgeType(str, Enum):
    PREREQUISITE = "PREREQUISITE"
    COMPOSED_OF = "COMPOSED_OF"
    ANALOGOUS_TO = "ANALOGOUS_TO"
    EXTENDS = "EXTENDS"
    CONTRASTS = "CONTRASTS"
    TRIGGERS_DISTRACTOR = "TRIGGERS_DISTRACTOR"
```

---

## 2. 추가 메타 설계

EOS 검토안 §13의 메타와 WhyMath 원칙을 결합.

| 필드 | 타입 | 제약 | 의미 | 적용 조건 |
|---|---|---|---|---|
| `required_strength` | `RequiredStrength` enum | nullable | 선수관계의 필요 강도 | `edge_type == PREREQUISITE` |
| `dependency_level` | `DependencyLevel` enum | nullable | 의존 필수 수준 | `edge_type == PREREQUISITE` |
| `minimum_mastery` | `float` | 0.0~1.0, nullable | 선수개념 최소 숙련도 | `edge_type == PREREQUISITE` |
| `curriculum_context` | `list[str]` | 기본값 `[]` | 교육과정 맥락(개정·학년·국가) | 항상 |
| `evidence_source_id` | `str` | max_length=64, nullable | 증거 출처 ID | 항상 |

### 2.1 신규 Enum

```python
class RequiredStrength(str, Enum):
    WEAK = "WEAK"
    MODERATE = "MODERATE"
    STRONG = "STRONG"
    CRITICAL = "CRITICAL"

class DependencyLevel(str, Enum):
    RECOMMENDED = "RECOMMENDED"
    EXPECTED = "EXPECTED"
    REQUIRED = "REQUIRED"
```

### 2.2 컬럼 설계

```python
# schema/ConceptEdge
required_strength: RequiredStrength | None = Field(default=None)
dependency_level: DependencyLevel | None = Field(default=None)
minimum_mastery: float | None = Field(default=None, ge=0.0, le=1.0)
curriculum_context: list[str] = Field(default_factory=list)
evidence_source_id: str | None = Field(default=None, max_length=64)

# ORM/ConceptEdge
required_strength: Mapped[RequiredStrength | None] = mapped_column(_pg_enum(RequiredStrength, "required_strength_enum"))
dependency_level: Mapped[DependencyLevel | None] = mapped_column(_pg_enum(DependencyLevel, "dependency_level_enum"))
minimum_mastery: Mapped[float | None] = mapped_column(sa.Numeric(3, 2))
curriculum_context: Mapped[list[str]] = mapped_column(ARRAY(sa.Text), nullable=False, server_default=sa.text("'{}'::text[]"))
evidence_source_id: Mapped[str | None] = mapped_column(sa.String(64))
```

---

## 3. 검증 규칙

1. **Self-edge 금지**: `_no_self_edge` 유지.
2. **Cycle 금지**: prerequisite graph는 DAG. L4 학습경로 엔진이 cycle detection을 수행하지만, DB 적재 시에도 validation.
3. **메타 일관성**: `edge_type != PREREQUISITE`이면 `required_strength`, `dependency_level`, `minimum_mastery`는 `None`이어야 한다.
4. **minimum_mastery 범위**: 0.0~1.0.

---

## 4. 마이그레이션

- `edge_type_enum` 외에 `required_strength_enum`, `dependency_level_enum` 추가.
- `concept_edge` 테이블에 5개 컬럼 추가 — 모두 nullable 또는 기본값 보유.
- existing data: `required_strength`, `dependency_level`, `minimum_mastery`, `evidence_source_id`는 NULL, `curriculum_context`는 `{}`.

---

## 5. 후속 작업

- [x] `RequiredStrength`, `DependencyLevel` enum 추가 (`src/backend/whymath_backend/schema/enums.py`)
- [x] `ConceptEdge` Pydantic 스키마 확장 (`src/backend/whymath_backend/schema/concept.py`)
- [x] `ConceptEdge` ORM 확장 (`src/backend/whymath_backend/db/models/concept.py`)
- [x] Alembic 마이그레이션 파일 작성
- [x] DAG 검증 테스트 추가 (`tests/backend/l1/test_concept_edge_prerequisite_meta.py`)
- [ ] 실 PostgreSQL에서 마이그레이션 실행 검증 (DB 기동 시)
