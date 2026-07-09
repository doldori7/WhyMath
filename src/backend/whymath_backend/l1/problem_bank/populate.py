"""문제 코퍼스 → backend `problem`/`problem_concept` 적재 (S2-b·L1 자체생성 동등문제 경로).

MEMORY 2026-07-04 결정이 "문제 코퍼스→DB 적재 파이프라인 부재"로 S2에 미뤄둔 바로 그 경로다.
S2-a 수용 게이트(`l3/equivalent/acceptance.py`)를 *통과한* 자체생성 동등문제를 코퍼스 JSONL
(`data/corpus/problem_bank_v1/problems.jsonl`)에서 backend 영속 `problem`·`problem_concept`
테이블로 **멱등 upsert**한다. `l1/standards/populate`(성취기준)·`l1/atom_graph/populate`(원자
백본)의 *문제* 짝이며 같은 sync 좌석·멱등 규약·orphan skip 패턴을 따른다.

────────────────────────────────────────────────────────────────────────────
계층 경계 (import-linter 계약 — L1은 L3를 import하지 않는다)
────────────────────────────────────────────────────────────────────────────
이 적재기는 L1이므로 S2-a 게이트(`l3/equivalent/acceptance`·`l3/verify_*`)를 **부르지 않는다**
(L1→L3 import 금지·7계층 역방향 의존 금지). 코퍼스에 든 문제는 *저작 시점에 이미 S2-a 게이트를
통과한* 문제라는 **계약**으로 적재된다 — 게이트 통과 증명은 코퍼스 품질 테스트
(`tests/backend/l1/problem_bank/test_corpus_quality.py`·계층 밖이라 L1+L3 동시 import 허용)가
봉인한다. 적재 파이프라인은 코퍼스를 신뢰하되 *저작권 위생*(source_type/license)만 재확인한다.

────────────────────────────────────────────────────────────────────────────
코퍼스 포맷 (JSONL — 한 줄 = 문제 1개)
────────────────────────────────────────────────────────────────────────────
각 줄은 `schema.Problem` 필드 + *저작 메타*(Problem 스키마 밖 authoring 필드)를 함께 담는다.
Problem은 `extra="forbid"`라 authoring 필드를 남기면 검증에 거부되므로, 로더가 `_AUTHORING_KEYS`
(`concepts`·`verify`·`license`·`generation_type`·`original_source`)를 *분리*한 뒤 나머지를
`Problem.model_validate`에 넘긴다(본문 불변식은 Problem이 강제).
  - `concepts`: 개념 태깅 `[{concept_src_id, role, relevance}]` — populate가 concept.source_id→
    concept_id 조인해 `problem_concept` 적재(미해석 개념은 orphan skip).
  - `verify`·`license`·`generation_type`·`original_source`: S2-a 게이트 재료(품질 테스트 소비).
    적재 파이프라인은 `license`(위생)만 보고 나머지 authoring은 레코드에 실어 반환만 한다.

────────────────────────────────────────────────────────────────────────────
저작권 위생 (코퍼스 신뢰의 최소 재확인 — 우선순위 #2)
────────────────────────────────────────────────────────────────────────────
학생에게 노출·저장되는 본문 레코드는 `source_type=자체생성`(WHYMATH_GENERATED)만 합법이다
(`schema/problem.py::_METADATA_ONLY_SOURCES` 규칙). 로더는 각 레코드가 ① `source_type==자체생성`
② `license==WHYMATH_GENERATED` ③ 안정 키 `slug` 보유인지 확인하고, 아니면 `ProblemCorpusError`로
*거부*한다(조용한 통과 금지). 본문 미보유 불변식(평가원/EBS/교과서 본문 금지)은 `Problem.
from_schema`가 거치는 `Problem` 검증이 이미 강제하므로 이 로더는 재구현하지 않는다.

────────────────────────────────────────────────────────────────────────────
멱등 (PG ON CONFLICT — standards/atom_graph 규약)
────────────────────────────────────────────────────────────────────────────
  - 문제: 안정 키 `slug`(UNIQUE) 충돌 시 `INSERT ... ON CONFLICT(slug) DO UPDATE`로 본문·메타를
    갱신하되 **problem_id(PK)·slug·created_at은 SET하지 않아 보존**한다(재적재가 식별자·생성시각
    불변). `problem_id`는 코퍼스에 없으면 매번 새로 생성되나 slug 충돌 시 기존 행의 problem_id가
    유지되며 `RETURNING problem_id`로 그 값을 받아 `problem_concept` FK에 쓴다(2회 적재 count 안정).
    입력 내 slug 중복은 *마지막 우선* dedup(단일 배치 ON CONFLICT 중복행 오류 방지·standards 선례).
  - 개념 태깅: `concept_src_id`를 `{source_id: concept_id}` 맵으로 concept_id에 *해석*(맵에 없으면
    orphan skip·집계 보고)한 뒤, 복합 PK `(problem_id, concept_id, role)` 충돌 시 `DO UPDATE`로
    `relevance`만 갱신한다. 해석된 `(concept_id, role)` 기준 dedup(마지막 우선).

concept 해석은 `l1/standards/standard_loader._load_source_id_to_code`(src_id→code)와 *동형*이되,
여기선 `problem_concept.concept_id`(UUID FK)가 필요하므로 `{source_id: concept_id}`를 만든다.
개념이 먼저 적재돼야(`l1/concept_graph`·`l1/atom_graph`) source_id 컬럼이 채워지므로, 문제 태깅은
개념 적재 다음에 와야 한다(아니면 전건 orphan skip).

sync 엔진은 슬3 `_build_sync_engine`을 재사용한다(신규 seam 0·standards/atom_graph와 동일 좌석).
자격은 env(`Settings.sync_database_url`)·하드코딩 0.

사용:
    python -m whymath_backend.l1.problem_bank.populate \\
        --problems data/corpus/problem_bank_v1/problems.jsonl

7계층: L1 데이터 기반의 *런타임 엔티티 적재*. 소비(게이팅·진단·출제)는 이 행을 *조회*하되 여기서
구현하지 않는다(역방향 의존 금지).
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from whymath_backend.config import Settings, get_settings

# 슬3 sync 엔진 빌더 재사용(신규 seam 0) — standards/atom_graph와 동일 좌석. (intra-L1 import)
from whymath_backend.l1.concept_graph.embedding import _build_sync_engine
from whymath_backend.schema.enums import ConceptRole, LicenseType, SourceType
from whymath_backend.schema.problem import Problem

if TYPE_CHECKING:
    from sqlalchemy.engine import Engine

# 코퍼스 기본 경로(신설 problem_bank_v1·손저작 시드).
_DEFAULT_PROBLEMS = Path("data/corpus/problem_bank_v1/problems.jsonl")

# Problem 스키마 밖 *저작 메타* 키 — Problem.model_validate 전에 분리한다(extra=forbid 대응).
_AUTHORING_KEYS: frozenset[str] = frozenset(
    {"concepts", "verify", "license", "generation_type", "original_source"}
)

# 본문 보유가 합법인 출처·라이선스(코퍼스 위생) — 자체생성 동등문제만 적재한다.
_ACCEPTED_SOURCE_VALUE: str = SourceType.자체생성.value
_ACCEPTED_LICENSE_VALUE: str = LicenseType.WHYMATH_GENERATED.value

# 유효 개념 역할 값 집합(ConceptRole) — 태깅 role 검증용.
_CONCEPT_ROLE_VALUES: frozenset[str] = frozenset(r.value for r in ConceptRole)


class ProblemCorpusError(ValueError):
    """문제 코퍼스가 저작권 위생·안정 키 규약을 어겨 적재를 거부할 때(조용한 통과 금지).

    거부 사유: ① `source_type != 자체생성`(본문 보유 불법 출처) ② `license != WHYMATH_GENERATED`
    ③ 안정 키 `slug` 부재(멱등 불가) ④ 개념 역할이 `ConceptRole` 밖. 본문 미보유 불변식(평가원/
    EBS/교과서) 위반은 `Problem` 검증이 먼저 `ValidationError`로 던지므로 여기 오지 않는다.
    """


# ──────────────────────────────────────────────────────────────────────────
# 저작 메타 타입 (Problem 스키마 밖 authoring — 로더가 분리·반환)
# ──────────────────────────────────────────────────────────────────────────
@dataclass(frozen=True, slots=True)
class ConceptTag:
    """개념 태깅 1건 — `concept_src_id`(개념그래프 src_id)·역할·관련도(problem_concept 재료)."""

    concept_src_id: str
    role: str  # ConceptRole 값(PRIMARY/SUPPORTING/IMPLICIT/TESTED)
    relevance: float | None = None


@dataclass(frozen=True, slots=True)
class ProblemVerifyMeta:
    """S2-a 정확성 게이트 재료 — 원 조건·치환맵·(선택)풀이 단계·근 선택. 적재엔 미사용(품질 테스트).

    `answer_selection`(S2-i·largest/smallest/unique): "큰 근/작은 근" 문제는 방정식만으론 답이
    유일하지 않아 게이트가 *어느 근인가*를 검증하는 데 쓴다(None=선택 요구 없음).
    """

    conditions: str | list[str]
    answer_map: dict[str, str]
    solution_steps: list[str] | None = None
    answer_selection: str | None = None
    answer_aggregate: str | None = None
    """S2 킬러 — 근 집계 검증 종류(sum/product). 답이 근이 아니라 근들의 합/곱인 킬러 문항."""
    answer_kind: str | None = None
    """개념형 — 개수/판정 검증 종류(개수·일대일·수렴·극한=함숫값·미분가능). 답이 값이 아닌 문항."""


@dataclass(frozen=True, slots=True)
class ProblemProvenanceMeta:
    """S2-a 저작권 게이트 재료 — ContentProvenance(generation_type/license/original_source)."""

    generation_type: str
    license: str
    original_source: str | None = None


@dataclass(frozen=True, slots=True)
class ProblemBankRecord:
    """코퍼스 1레코드 = 검증된 Problem + 저작 메타(개념 태깅·verify·provenance).

    적재 파이프라인은 `slug`·`problem`·`concept_tags`만 소비한다. `verify`·`provenance`는 코퍼스
    품질 테스트(S2-a 게이트 재현)가 쓰는 authoring이며 적재엔 관여하지 않는다(계층 경계).
    """

    slug: str
    problem: Problem
    concept_tags: tuple[ConceptTag, ...]
    verify: ProblemVerifyMeta
    provenance: ProblemProvenanceMeta


@dataclass(frozen=True, slots=True)
class ProblemBankPopulateReport:
    """문제 코퍼스 적재 결과 요약(운영 가시성·테스트 단언용).

    `problems_loaded`(문제 upsert 행 수·dedup 후)·`problem_concepts_loaded`(개념 태깅 upsert 수)·
    `concepts_skipped`(미해석 개념 orphan skip 수)·`skipped_messages`(orphan 상세·조용한 누락 금지).
    """

    problems_loaded: int
    problem_concepts_loaded: int
    concepts_skipped: int
    skipped_messages: list[str] = field(default_factory=list)


# ──────────────────────────────────────────────────────────────────────────
# 코퍼스 파싱 (JSONL → 검증된 ProblemBankRecord — authoring 분리·저작권 위생)
# ──────────────────────────────────────────────────────────────────────────
def _concept_tag_from_dict(raw: dict[str, Any], *, slug: str) -> ConceptTag:
    """개념 태깅 dict → `ConceptTag`(role 값 검증). 필수 키·역할 밖이면 `ProblemCorpusError`."""
    src_id = raw.get("concept_src_id")
    role = raw.get("role")
    if not isinstance(src_id, str) or not src_id:
        raise ProblemCorpusError(
            f"개념 태깅 concept_src_id 누락/형식오류: slug={slug} raw={raw!r}"
        )
    if not isinstance(role, str) or role not in _CONCEPT_ROLE_VALUES:
        raise ProblemCorpusError(
            f"개념 태깅 role이 ConceptRole 밖: slug={slug} role={role!r} "
            f"(허용 {sorted(_CONCEPT_ROLE_VALUES)})"
        )
    relevance = raw.get("relevance")
    rel_value = float(relevance) if isinstance(relevance, (int, float)) else None
    return ConceptTag(concept_src_id=src_id, role=role, relevance=rel_value)


def _record_from_line(raw: dict[str, Any]) -> ProblemBankRecord:
    """코퍼스 JSONL 한 줄(dict) → 검증된 `ProblemBankRecord`(authoring 분리·위생·Problem 검증).

    ① authoring 키(`_AUTHORING_KEYS`)를 분리 → ② 저작권 위생 확인(source_type=자체생성·license=
    WHYMATH_GENERATED·slug 보유) → ③ 나머지를 `Problem.model_validate`(본문 불변식 자동 강제) →
    ④ 개념 태깅·verify·provenance 저작 메타 조립. 위생 위반은 `ProblemCorpusError`(조용한 통과 X).
    """
    data = dict(raw)  # 원본 불변(호출자 dict 보호)

    # ── ① authoring 분리 ──
    concepts_raw = data.pop("concepts", []) or []
    verify_raw = data.pop("verify", None)
    license_value = data.pop("license", None)
    generation_type = data.pop("generation_type", None)
    original_source = data.pop("original_source", None)

    # ── ② 저작권 위생(코퍼스 신뢰의 최소 재확인) ──
    slug = data.get("slug")
    if not isinstance(slug, str) or not slug:
        raise ProblemCorpusError(f"안정 키 slug 부재 — 멱등 불가: raw={raw!r}")
    source_value = data.get("source_type")
    if source_value != _ACCEPTED_SOURCE_VALUE:
        raise ProblemCorpusError(
            f"코퍼스 위생 위반: source_type={source_value!r}는 적재 불가 — 본문 보유 문제는 "
            f"source_type={_ACCEPTED_SOURCE_VALUE!r}만 합법이다(평가원/EBS/교과서 등 메타 전용 "
            f"출처 거부·저작권 가이드 v2.0). slug={slug}"
        )
    if license_value != _ACCEPTED_LICENSE_VALUE:
        raise ProblemCorpusError(
            f"코퍼스 위생 위반: license={license_value!r}는 적재 불가 — 자체생성 본문의 지배 "
            f"license는 {_ACCEPTED_LICENSE_VALUE!r}여야 한다. slug={slug}"
        )

    # ── ③ Problem 검증(본문 불변식은 Problem이 강제 — 재구현 0) ──
    problem = Problem.model_validate(data)

    # ── ④ 저작 메타 조립 ──
    concept_tags = tuple(
        _concept_tag_from_dict(c, slug=slug)
        for c in concepts_raw
        if isinstance(c, dict)
    )
    verify_meta = _verify_meta_from_raw(verify_raw, slug=slug)
    provenance_meta = ProblemProvenanceMeta(
        generation_type=str(generation_type) if generation_type is not None else "",
        license=str(license_value),
        original_source=str(original_source) if original_source is not None else None,
    )
    return ProblemBankRecord(
        slug=slug,
        problem=problem,
        concept_tags=concept_tags,
        verify=verify_meta,
        provenance=provenance_meta,
    )


def _verify_meta_from_raw(verify_raw: Any, *, slug: str) -> ProblemVerifyMeta:
    """verify authoring dict → `ProblemVerifyMeta`. 부재 시 빈 조건(품질 테스트가 unverifiable)."""
    if not isinstance(verify_raw, dict):
        return ProblemVerifyMeta(conditions="", answer_map={})
    conditions = verify_raw.get("conditions", "")
    answer_map_raw = verify_raw.get("answer_map", {})
    steps_raw = verify_raw.get("solution_steps")
    if not isinstance(conditions, (str, list)):
        raise ProblemCorpusError(
            f"verify.conditions 형식오류: slug={slug} value={conditions!r}"
        )
    answer_map = {str(k): str(v) for k, v in dict(answer_map_raw).items()}
    steps = [str(s) for s in steps_raw] if isinstance(steps_raw, list) else None
    sel_raw = verify_raw.get("answer_selection")
    selection = sel_raw if sel_raw in ("largest", "smallest", "unique") else None
    agg_raw = verify_raw.get("answer_aggregate")
    aggregate = agg_raw if agg_raw in ("sum", "product") else None
    kind_raw = verify_raw.get("answer_kind")
    kind = (
        kind_raw
        if kind_raw
        in (
            "real_root_count",
            "extremum_count",
            "is_one_to_one",
            "geometric_convergence",
            "limit_equals_value",
            "is_differentiable",
            "series_converges",
        )
        else None
    )
    return ProblemVerifyMeta(
        conditions=conditions,
        answer_map=answer_map,
        solution_steps=steps,
        answer_selection=selection,
        answer_aggregate=aggregate,
        answer_kind=kind,
    )


def load_problem_bank_records(problems_path: Path) -> list[ProblemBankRecord]:
    """문제 코퍼스 JSONL을 검증된 `ProblemBankRecord` 목록으로 로드(authoring 분리·위생·검증).

    빈 줄은 건너뛴다(관대). 각 줄은 `_record_from_line`이 authoring 분리·저작권 위생·Problem 검증을
    거친다 — 위생 위반은 `ProblemCorpusError`로 전파(조용한 통과 금지). 코퍼스 품질 테스트가 반환
    레코드의 `verify`/`provenance`로 S2-a 게이트를 재현한다.

    Raises:
        FileNotFoundError: problems_path 파일 부재.
        ProblemCorpusError: 저작권 위생·안정 키·역할 위반.
        pydantic.ValidationError: 레코드가 Problem 스키마·본문 불변식 위반.
    """
    text = problems_path.read_text(encoding="utf-8")
    records: list[ProblemBankRecord] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        records.append(_record_from_line(json.loads(stripped)))
    return records


# ──────────────────────────────────────────────────────────────────────────
# 적재기 (ProblemBankStore — slug ON CONFLICT·concept 해석·orphan skip·sync)
# ──────────────────────────────────────────────────────────────────────────
class ProblemBankStore:
    """문제 코퍼스 → backend `problem`/`problem_concept` 적재기 — slug 충돌 멱등 upsert(sync).

    `AchievementStandardStore`(성취기준)·`AtomBackendEdgeStore`(엣지)의 *문제* 짝이다(같은 sync
    좌석·멱등 규약·orphan skip). `populate`는 ① `{source_id: concept_id}` 맵을 단일 조회로 만들고
    (N+1 0) ② 각 문제를 `ON CONFLICT(slug) DO UPDATE ... RETURNING problem_id`로 멱등 적재해 안정
    problem_id를 받은 뒤 ③ 개념 태깅을 concept_id로 해석(orphan skip)해 `problem_concept`에 복합 PK
    충돌 멱등 upsert한다. sync 엔진은 슬3 `_build_sync_engine`을 재사용해 지연 생성·캐시(seam 0).
    """

    def __init__(
        self,
        *,
        engine: Engine | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._engine = engine
        self._settings = settings

    @property
    def _resolved_settings(self) -> Settings:
        """설정 지연 해석 — 주입 우선, 없으면 캐시된 전역 Settings(standards 패턴)."""
        if self._settings is None:
            self._settings = get_settings()
        return self._settings

    def _get_engine(self) -> Engine:
        """sync 엔진 지연 해석 — 주입 우선, 없으면 슬3 빌더로 생성·캐시(신규 seam 0)."""
        if self._engine is None:
            self._engine = _build_sync_engine(self._resolved_settings)
        return self._engine

    def _load_source_id_to_concept_id(self) -> dict[str, Any]:
        """backend `concept` 전량을 단일 조회해 `{source_id: concept_id}` 맵 구축(N+1 0).

        개념 태깅의 `concept_src_id`(src_id)를 `problem_concept.concept_id`(UUID FK)로 해석한다 —
        standard_loader의 `{source_id: code}`(src_id→code)와 *동형*이되, 여기선 문제↔개념 N:M의 FK가
        UUID라 concept_id를 값으로 둔다. `source_id`가 NULL인 개념(재ID 전 데이터)은 키가 될 수 없어
        제외한다. 개념이 먼저 적재돼야 채워지므로 문제 태깅은 개념 적재 다음(아니면 전건 orphan).
        """
        from sqlalchemy import select

        from whymath_backend.db.models.concept import Concept

        stmt = select(Concept.source_id, Concept.concept_id)
        with self._get_engine().connect() as conn:
            rows = conn.execute(stmt).all()
        return {
            row.source_id: row.concept_id for row in rows if row.source_id is not None
        }

    def populate(
        self, records: Sequence[ProblemBankRecord]
    ) -> ProblemBankPopulateReport:
        """문제·개념 태깅을 `problem`/`problem_concept`에 멱등 upsert(해석·orphan skip·PK 보존).

        ① slug 기준 *마지막 우선* dedup(단일 배치 ON CONFLICT 중복행 오류 방지) → ② `{source_id:
        concept_id}` 맵 단일 구축 → ③ 각 문제를 `ON CONFLICT(slug) DO UPDATE ... RETURNING
        problem_id`로 적재(problem_id·slug·created_at 미-SET·보존)·안정 problem_id 획득 → ④ 개념
        태깅을 concept_id로 해석(맵에 없으면 orphan skip·집계)·해석된 `(concept_id, role)` dedup →
        ⑤ `ON CONFLICT(problem_id, concept_id, role) DO UPDATE`로 relevance만 갱신. 반환: 리포트.
        빈 입력은 0 리포트(조기 반환).
        """
        if not records:
            return ProblemBankPopulateReport(0, 0, 0, [])

        import sqlalchemy as sa
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        from whymath_backend.db.models.concept import (
            ProblemConcept as ProblemConceptORM,
        )
        from whymath_backend.db.models.problem import Problem as ProblemORM

        # ① slug 기준 dedup(마지막 우선) — 단일 배치 ON CONFLICT 중복행 오류 방지.
        by_slug: dict[str, ProblemBankRecord] = {r.slug: r for r in records}
        deduped = list(by_slug.values())

        # ② 개념 해석 맵.
        source_id_to_cid = self._load_source_id_to_concept_id()

        # 문제 갱신 컬럼 집합 — 식별자(problem_id·slug)·생성시각(created_at)은 보존(SET 제외).
        problem_cols = {col.key for col in sa.inspect(ProblemORM).mapper.column_attrs}
        problem_update_keys = problem_cols - {"problem_id", "slug", "created_at"}

        problems_loaded = 0
        problem_concepts_loaded = 0
        skipped: list[str] = []

        with self._get_engine().begin() as conn:
            for record in deduped:
                # ③ 문제 upsert(slug 충돌) + RETURNING problem_id(안정 식별자 획득).
                payload = record.problem.model_dump()
                values = {k: v for k, v in payload.items() if k in problem_cols}
                insert_stmt = pg_insert(ProblemORM).values(**values)
                problem_stmt = insert_stmt.on_conflict_do_update(
                    index_elements=[ProblemORM.slug],
                    set_={
                        key: insert_stmt.excluded[key] for key in problem_update_keys
                    },
                ).returning(ProblemORM.problem_id)
                problem_id = conn.execute(problem_stmt).scalar_one()
                problems_loaded += 1

                # ④ 개념 태깅 해석(orphan skip)·(concept_id, role) dedup(마지막 우선).
                resolved: dict[tuple[Any, str], float | None] = {}
                for tag in record.concept_tags:
                    concept_id = source_id_to_cid.get(tag.concept_src_id)
                    if concept_id is None:
                        skipped.append(
                            f"orphan concept skip(개념 미해석): slug={record.slug} "
                            f"concept_src_id={tag.concept_src_id}(맵에 없음) role={tag.role}"
                        )
                        continue
                    resolved[(concept_id, tag.role)] = tag.relevance

                # ⑤ problem_concept upsert(복합 PK 충돌 시 relevance만 갱신).
                for (concept_id, role), relevance in resolved.items():
                    pc_stmt = pg_insert(ProblemConceptORM).values(
                        problem_id=problem_id,
                        concept_id=concept_id,
                        role=role,
                        relevance=relevance,
                    )
                    pc_stmt = pc_stmt.on_conflict_do_update(
                        index_elements=[
                            ProblemConceptORM.problem_id,
                            ProblemConceptORM.concept_id,
                            ProblemConceptORM.role,
                        ],
                        set_={"relevance": pc_stmt.excluded.relevance},
                    )
                    conn.execute(pc_stmt)
                    problem_concepts_loaded += 1

        return ProblemBankPopulateReport(
            problems_loaded=problems_loaded,
            problem_concepts_loaded=problem_concepts_loaded,
            concepts_skipped=len(skipped),
            skipped_messages=skipped,
        )


# ──────────────────────────────────────────────────────────────────────────
# 공개 진입점
# ──────────────────────────────────────────────────────────────────────────
def populate_problem_bank(
    session: object | None,
    *,
    problems_path: Path = _DEFAULT_PROBLEMS,
    settings: Settings | None = None,
    store: ProblemBankStore | None = None,
) -> ProblemBankPopulateReport:
    """문제 코퍼스 JSONL을 backend `problem`/`problem_concept`에 멱등 적재. 반환=적재 리포트.

    `load_problem_bank_records`가 authoring 분리·저작권 위생·Problem 검증을 거친 레코드를 만들고,
    `ProblemBankStore.populate`가 slug 충돌 멱등 upsert·concept 해석·orphan skip을 담당한다. store
    미주입 시 슬3 sync 엔진 재사용 store를 만든다(같은 settings 공유).

    `session` 인자는 standards/misconception 로더의 좌석 규약 호환을 위한 *자리표시*다 — 이 적재기는
    sync 엔진으로 동작하므로 ORM async Session을 쓰지 않는다(None 허용). L1→L3 경계상 이 함수는 S2-a
    게이트를 부르지 않는다(코퍼스는 저작 시점에 게이트 통과분·모듈 docstring).

    Raises:
        FileNotFoundError: problems_path 파일 부재.
        ProblemCorpusError: 저작권 위생·안정 키·역할 위반(코퍼스 거부).
        pydantic.ValidationError: 레코드가 Problem 스키마·본문 불변식 위반.
    """
    del session  # async Session 미사용(sync 엔진 좌석) — 호환 자리표시.
    records = load_problem_bank_records(problems_path)
    resolved = settings if settings is not None else get_settings()
    bank_store = store if store is not None else ProblemBankStore(settings=resolved)
    return bank_store.populate(records)


def main(argv: list[str] | None = None) -> int:
    """문제 코퍼스(JSONL)를 `problem`/`problem_concept`에 멱등 적재하고 리포트를 보고(CLI 본체).

    반환은 프로세스 종료 코드(0=성공·2=입력 파일 부재). 적재 로직은 `populate_problem_bank`가
    담당하며 본 함수는 경로 결선·실행·stdout 보고만 한다(조용한 무동작 금지 — 부재 시 명확히 보고).
    """
    parser = argparse.ArgumentParser(
        prog="whymath-problem-bank-populate",
        description=(
            "문제 코퍼스(JSONL) → backend problem·problem_concept 멱등 적재"
            "(slug 충돌 upsert·concept 해석·orphan skip·자체생성 위생)."
        ),
    )
    parser.add_argument(
        "--problems",
        type=Path,
        default=_DEFAULT_PROBLEMS,
        help=f"문제 코퍼스 JSONL 경로(기본 {_DEFAULT_PROBLEMS}).",
    )
    args = parser.parse_args(argv)

    path: Path = args.problems
    if not path.exists():
        print(
            f"문제 코퍼스 없음: {path} — 코퍼스 생성기(손저작 시드)로 먼저 생성하세요."
        )
        return 2

    report = populate_problem_bank(None, problems_path=path)
    print(
        f"문제 적재 완료: {report.problems_loaded}건·개념 태깅: "
        f"{report.problem_concepts_loaded}건 (src={path}). "
        f"개념 orphan skip: {report.concepts_skipped}건"
        + (
            " (개념 미적재 — l1.concept_graph/atom_graph 선행)."
            if report.concepts_skipped
            else "."
        )
    )
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI 진입
    raise SystemExit(main())
