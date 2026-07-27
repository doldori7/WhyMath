"""수식 메타 PG 프로젝션 적재 — `formula_node` 테이블 formula_id 키 멱등 upsert (P5a).

`l1/problem_type_graph/problem_type_node_projection.py`(문제유형 프로젝션)의 *수식* 짝이다.
data 산출 `formula_graph_v1/graph.json`(canonical 수식 노드)의 *안전 메타*를 `formula_node`(PG)에
멱등 upsert한다 — 검색 enrichment·필터·(후속 5b) 수식 참조 백킹.

차이(`problem_type_node_projection.py` 대비):
  - **키가 formula_id**(graph.json `formula_id`·`formula.<slug>`) — 타 노드 공간과 분리.
  - **입력 배열이 `formulas`**.
  - **latex·dsl 필수**(display·SymPy-parseable canonical 식). `canonical_signature`는 nullable 보조.
  - **동치/변형 슬롯 없음**: 변형↔canonical 동치는 런타임 SymPy(l3)가 판정 — 이 로더는 sympy를
    import하지 않는다(SymPy 재구현 금지·동치 권위는 l3 단일).
  - **review_status는 상수**('ai_estimated'·v1 자체작성이나 전문 검수 전·정직 표기).

법적(CLAUDE.md 우선순위 #2): canonical 수식은 수학적 사실·표준 표기 자체작성이라 redaction 무관.
적재 필드는 전부 안전 메타(교과서·기출 본문 0).

sync 엔진 재사용(신규 seam 0): 슬3 `embedding._build_sync_engine`을 그대로 재사용한다
(problem_type_node_projection·skill_node_projection과 동일 sync 좌석 규약·자격증명 하드코딩 0).

7계층: L1 데이터 기반의 *영속 프로젝션 적재*. 조회·소비(formula_refs·resolution)는 Phase 5b(역방향
의존 금지).
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from whymath_backend.config import Settings, get_settings
from whymath_backend.db.models.formula_node import FORMULA_REVIEW_STATUS_DEFAULT

# 슬3 sync 엔진 빌더 재사용(신규 seam 0) — problem_type_node_projection과 동일 규약.
from whymath_backend.l1.concept_graph.embedding import _build_sync_engine

if TYPE_CHECKING:
    from sqlalchemy.engine import Engine


def _opt_str(value: object) -> str | None:
    """빈 문자열·None → None, 그 외 strip한 str(problem_type_node_projection `_opt_str` 미러)."""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


@dataclass(frozen=True, slots=True)
class FormulaNodeRecord:
    """프로젝션 대상 한 canonical 수식 노드의 *안전 메타* — formula_id + 표시·검증 필드.

    `graph.json`의 한 formula에서 안전 키만 추린 값이다. 변형/동치 슬롯은 없다(동치는 런타임 SymPy·
    구조적 차단). 적재기가 이 레코드를 formula_id 키로 upsert. `review_status`는 슬롯이 없다 —
    적재기가 상수로 박는다(v1 자체작성·전문 검수 전).
    """

    formula_id: str
    name_ko: str
    family: str
    latex: str
    dsl: str
    canonical_signature: str | None
    aliases: tuple[str, ...]
    standard_codes: tuple[str, ...]
    constraints: tuple[str, ...] = ()
    mnemonic: str | None = None


def load_formulas_from_graph_json(path: Path) -> list[FormulaNodeRecord]:
    """data-pipeline 산출 `graph.json` → 수식 *안전 메타* 레코드 목록(formula_id 키).

    `formulas` 배열의 각 항목에서 안전 키만 읽어 `FormulaNodeRecord`를 만든다. `formula_id`·
    `name_ko`·`family`·`latex`·`dsl`은 필수라 누락 시 건너뛴다(NOT NULL 위반 방지·조용한 적재 금지).
    정상 코퍼스는 전 필드를 보유하므로 실경로에선 skip이 없다.

    Raises:
        FileNotFoundError: graph.json 부재.
    """
    payload = json.loads(path.read_text(encoding="utf-8"))
    out: list[FormulaNodeRecord] = []
    for record in payload.get("formulas", []):
        formula_id = _opt_str(record.get("formula_id"))
        name_ko = _opt_str(record.get("name_ko"))
        family = _opt_str(record.get("family"))
        latex = _opt_str(record.get("latex"))
        dsl = _opt_str(record.get("dsl"))
        if None in (formula_id, name_ko, family, latex, dsl):
            continue
        assert formula_id is not None and name_ko is not None and family is not None
        assert latex is not None and dsl is not None

        raw_aliases = record.get("aliases")
        aliases: tuple[str, ...] = (
            tuple(str(a) for a in raw_aliases) if isinstance(raw_aliases, (list, tuple)) else ()
        )
        raw_codes = record.get("standard_codes")
        codes: tuple[str, ...] = (
            tuple(str(c) for c in raw_codes) if isinstance(raw_codes, (list, tuple)) else ()
        )
        raw_constraints = record.get("constraints")
        constraints: tuple[str, ...] = (
            tuple(str(c) for c in raw_constraints)
            if isinstance(raw_constraints, (list, tuple))
            else ()
        )
        out.append(
            FormulaNodeRecord(
                formula_id=formula_id,
                name_ko=name_ko,
                family=family,
                latex=latex,
                dsl=dsl,
                canonical_signature=_opt_str(record.get("canonical_signature")),
                aliases=aliases,
                standard_codes=codes,
                constraints=constraints,
                mnemonic=_opt_str(record.get("mnemonic")),
            )
        )
    return out


class FormulaNodeStore:
    """수식 메타 PG 프로젝션 적재기 — `formula_node` 키 멱등 upsert(sync).

    `ProblemTypeNodeStore`(문제유형 메타 프로젝션)의 *수식 그래프* 짝이다. `upsert`는 PK 충돌 upsert
    (`INSERT ... ON CONFLICT(formula_id) DO UPDATE`)로 멱등 적재한다(같은 id 재적재 → 행 갱신·
    updated_at 갱신). `review_status`는 상수('ai_estimated')로 박는다. sync 엔진은 슬3
    `_build_sync_engine`을 재사용해 지연 생성·캐시한다(신규 seam 0). *적재 전용* 좌석이다.
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
        """설정 지연 해석 — 주입 우선, 없으면 캐시된 전역 Settings(ptype 프로젝션 패턴)."""
        if self._settings is None:
            self._settings = get_settings()
        return self._settings

    def _get_engine(self) -> Engine:
        """sync 엔진 지연 해석 — 주입 우선, 없으면 슬3 빌더로 생성·캐시(신규 seam 0)."""
        if self._engine is None:
            self._engine = _build_sync_engine(self._resolved_settings)
        return self._engine

    def upsert(self, record: FormulaNodeRecord) -> None:
        """단일 수식 메타 upsert (멱등·formula_id PK 충돌 갱신).

        `INSERT ... ON CONFLICT(formula_id) DO UPDATE` — 안전 메타 전 필드 + review_status +
        updated_at(now())을 갱신한다. aliases·standard_codes는 리스트로 바인딩(PG TEXT[]). 변형·동치
        컬럼은 없다(구조적 차단·동치는 런타임 SymPy).
        """
        from sqlalchemy import func
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        from whymath_backend.db.models.formula_node import FormulaNode

        stmt = pg_insert(FormulaNode).values(
            formula_id=record.formula_id,
            name_ko=record.name_ko,
            family=record.family,
            latex=record.latex,
            dsl=record.dsl,
            canonical_signature=record.canonical_signature,
            aliases=list(record.aliases),
            standard_codes=list(record.standard_codes),
            constraints=list(record.constraints),
            mnemonic=record.mnemonic,
            review_status=FORMULA_REVIEW_STATUS_DEFAULT,
        )
        # PK 충돌 시 갱신 — updated_at은 now()로 새로 찍는다(server_default는 INSERT 전용).
        stmt = stmt.on_conflict_do_update(
            index_elements=[FormulaNode.formula_id],
            set_={
                "name_ko": stmt.excluded.name_ko,
                "family": stmt.excluded.family,
                "latex": stmt.excluded.latex,
                "dsl": stmt.excluded.dsl,
                "canonical_signature": stmt.excluded.canonical_signature,
                "aliases": stmt.excluded.aliases,
                "standard_codes": stmt.excluded.standard_codes,
                "constraints": stmt.excluded.constraints,
                "mnemonic": stmt.excluded.mnemonic,
                "review_status": stmt.excluded.review_status,
                "updated_at": func.now(),
            },
        )
        with self._get_engine().begin() as conn:
            conn.execute(stmt)


def populate_formula_nodes(
    records: Sequence[FormulaNodeRecord],
    *,
    settings: Settings | None = None,
    store: FormulaNodeStore | None = None,
) -> int:
    """수식 안전 메타를 `formula_node`에 멱등 upsert 적재(영속 프로젝션). 반환=적재 행 수.

    `populate_problem_type_nodes`의 *수식 그래프* 짝이다 — 각 레코드를 formula_id 키로 upsert한다
    (전량·review_status='ai_estimated'). 멱등(재실행 시 갱신). store 미주입 시 슬3 sync 엔진 재사용
    `FormulaNodeStore`를 만든다.
    """
    resolved = settings if settings is not None else get_settings()
    node_store = store if store is not None else FormulaNodeStore(settings=resolved)
    for record in records:
        node_store.upsert(record)
    return len(records)


__all__ = [
    "FormulaNodeRecord",
    "FormulaNodeStore",
    "load_formulas_from_graph_json",
    "populate_formula_nodes",
]
