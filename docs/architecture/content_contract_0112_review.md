# 011_2 Subject-neutral Content Schema / API Contract — WhyMath 수용 검토

> **태스크**: `S1-16-subject-neutral-content-contract`  
> **상태**: 결정 확정 · Phase A(schema_version) 구현 진행 중  
> **작성일**: 2026-08-19  
> **관련 문서**: `CLAUDE.md`, `schemas/v1.1/concept.schema.yaml`, `schemas/v1.1/curriculum_entry.schema.yaml`, `docs/architecture/03c_content_strategy_cache.md`, `docs/architecture/subject_expansion_readiness.md`

---

## 1. 제안 요약

011_2는 EOS(Education Operating System)로서 **과목에 종속되지 않는 콘텐츠 교환 규약**을 정의합니다.

핵심 구조:

```text
Content Envelope
├── identity
├── version (content_version / schema_version)
├── type
├── subject_refs
├── provenance
├── metadata
└── payload
      ├── core
      └── extension
```

제안의 핵심 메시지:

- **Core Schema**에는 `math_*` 같은 과목별 단어가 들어가면 안 된다.
- **Content Type**과 **Interaction Type**은 분리한다.
- **Assessment**도 과목 중립적으로 정의하고, `equation_equivalence` 같은 수학 특화 판정은 extension으로 보낸다.
- **Domain Extension Registry**를 두어 Core API를 수정하지 않고 과목을 추가한다.
- **API Contract**는 OpenAPI/JSON Schema로 기계 판독 가능하게 정의한다.
- **Schema Versioning**과 Content Versioning은 분리한다.

---

## 2. WhyMath 현행 설계와의 매핑

### 2.1 이미 수용된 부분

| 011_2 제안 | WhyMath 현행 설계 | 근거 문서/코드 |
|---|---|---|
| Subject-neutral Core | `concept` 노드에서 `subject`·`curriculum_version` 제거 | `schemas/v1.1/concept.schema.yaml`, `subject_expansion_readiness.md` §1 |
| Subject 축은 Overlay로 | `CurriculumEntry` 복합키 `(concept_id, country_code, subject)` | `schemas/v1.1/curriculum_entry.schema.yaml` |
| Content Envelope | `problem.schema.yaml`의 envelope-like 필드 구조 | `schemas/v1.1/problem.schema.yaml` |
| Renderer-중립 저장 | 교수법-중립 DSL + `PedagogyAdapter` | `docs/architecture/03c_content_strategy_cache.md` |
| AI 출력 → Contract → 검증 | L3 라우터 → PRM/SymPy/Lean → `content_provenance` | `CLAUDE.md`, `03a_l3_router_design.md` |
| Provenance & Versioning | `content_provenance`, `generation_log`, `curriculum_version` | `schemas/v1.0/schema_v1.0.md` §10 |
| JSON Schema / OpenAPI 계약 | `schemas/v1.1/*.schema.yaml` + FastAPI 자동 OpenAPI | `schemas/v1.1/` |

### 2.2 일부 수용이 필요한 부분

| 011_2 제안 | WhyMath 현황 | 결정 |
|---|---|---|
| Schema Versioning 명시 | 스키마 디렉토리(`v1.0`/`v1.1`)는 있으나 API/모델 응답에 `schema_version` 필드가 없음 | **Phase A로 수용** — `Problem`/`PublicProblem`에 추가 |
| Math Extension 분리 | `answer_transform`, `signature_patterns`, `requires_graph_sketch` 등이 `Problem` Core에 직접 있음 | **Phase B로 수용** — `extensions.math` 서브스키마로 이동 |
| `/contents` 단일 endpoint | 현재 `/problems`, `/concepts` 등 도메인별 endpoint 사용 | **MVP 보류** — 소비처 등록 후 |
| Domain Extension Registry | `AREA` 레지스트리는 예약됨(`MECH`, `ELEC` 등) | **설계 준비 완료, 구현 보류** |

### 2.3 보류/반대 부분

| 011_2 제안 | 보류/반대 근거 |
|---|---|
| MVP에서 물리/화학 Extension 구현 | Phase 1은 수학 MVP. 타 과목 콘텐츠·소비처 부재. |
| 모든 과목에 대해 `/contents` 단일 endpoint 도입 | `/problems` + subject 필터로 충분. 통합 endpoint는 과목 콘텐츠가 실제로 생긴 뒤에. |
| `assessment.method = "binary"` 일반화 | 수학에서 partial credit·수식 동치가 핵심. binary는 허용되나 math extension에 상세 판정 규칙을 둬야 함. |

---

## 3. 결정 사항

### 3.1 수용 ✅

1. **`schema_version` 필드 명시**
   - `Problem`/`PublicProblem` 및 `problem.schema.yaml`에 `schema_version` 추가.
   - 기본값: `SchemaVersion(name="whymath-problem", version="1.1.0")`.
   - Content Versioning과 Schema Versioning을 분리.

2. **Math Extension 분리 설계**
   - `extensions.math` 서브스키마를 정의하고, 수학 특화 필드를 이동.
   - 하위호환을 위해 기존 필드는 deprecated 마커를 두고 일정 기간 유지.

### 3.2 보류 🚧

1. **물리/화학 등 타 과목 Extension 구현**
   - `subject_expansion_readiness.md` §8 보류 항목 대장에 등록된 원칙 유지.
   - 실제 물리 문항/소비처가 생기기 전까지는 Core 변경만 하고 Domain Extension은 추가하지 않는다.

2. **`/contents` 단일 endpoint**
   - MVP에서는 `/problems` + `subject` 필터로 충분.
   - 통합 endpoint는 과목 확장 S2~S3에서 검토.

### 3.3 반대 ❌

없음. 제안의 방향성은 WhyMath 설계와 일치.

---

## 4. MVP 범위

```text
011_2 MVP (Phase 1)
├── schema_version 필드 추가
├── Math Extension 설계 (extensions.math 서브스키마)
├── problem.schema.yaml 반영
├── tests/backend/schema/test_problem.py 추가
└── 결정 문서 + MEMORY.md 로그

보류 (Phase 2+)
├── Physics/Chemistry Extension
├── /contents 단일 endpoint
├── Domain Extension Registry 구체화
└── External Standard Mapping
```

---

## 5. Phase별 실행 계획

### Phase A — schema_version 추가 (non-breaking)

- `schemas/v1.1/problem.schema.yaml`에 `schema_version` 필드 추가.
- `src/backend/whymath_backend/schema/problem.py`에 `SchemaVersion` 모델 및 `PublicProblem` 필드 추가.
- `tests/backend/schema/test_problem.py`에 기본값 및 extra-forbid 테스트 추가.
- PR 생성 → 머지.

### Phase B — Math Extension 분리 (breaking)

- `schemas/v1.1/problem.schema.yaml`에 `extensions.math` 서브스키마 추가.
- `src/backend/whymath_backend/schema/problem.py`에 `MathExtension` 모델 추가 및 기존 필드 deprecated 처리.
- DB 마이그레이션(ORM/alembic) 및 다운스트림 소비자 수정.
- 별도 PR로 분리하여 심사.

---

## 6. 검증 기준

- `python -m pytest tests/backend/schema/test_problem.py` green
- `ruff check`, `black --check`, `mypy --strict` 통과
- `backlog.py validate` green
- 결정 문서가 `CLAUDE.md` 및 `subject_expansion_readiness.md`와 충돌하지 않음

---

## 7. 후속 참조

- **Backlog**: `backlog/tasks/S1-16-subject-neutral-content-contract.yaml`
- **Phase A PR**: (추가 예정)
- **Phase B PR**: (추가 예정)
