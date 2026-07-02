"""데이터셋 v1 jsonl(5종) → 확장 `Concept`/`ConceptEdge` 정형화(단계 5).

정본: docs/data/concept_graph.md §2(모델)·§4(단계 5) +
docs/data/concept_graph_dataset_v1.md §2(필드표)·§3(redaction)·§4(검수 게이트).

슬라이스 1 범위 = **개념 + 선수엣지(그래프 코어)**. flashcards(L6)·ccss_only_intl(국제트랙)은
이번 정형화에서 *raw 패스스루*로만 보존하고 모델 매핑은 하지 않는다(억지 매핑 금지 — L6/국제는
후속 슬라이스). standard_ccss_map의 ccss는 이미 `concepts.ccss_code`와 동일하므로 별도 처리
불요(데이터 검증으로 확인 — concept.ccss_code로 흡수).

매핑 규칙(concepts.jsonl → Concept):
  - concept_id = idmap.build_id_map(records)[src_id]  ← 새 ID(`{TRACK}-{AREA}-{NNN}`·충돌 0)
  - source_id = src_id;  aliases = idmap.build_alias_map(records)[src_id](= [옛 UC, src_id])
  - name_ko = name_ko;  name_en/ja = None(Phase 1 KR 단일언어)
  - domain = category(데이터셋 영역명, 예 '[고]미적분');  grade_band_hint = 첫 코드 학년군 추론
  - standard_codes 직결;  ccss_code/metaphor/accepted_expressions/difficulty_tier 풍부필드 직결
  - **misconception(자유텍스트 오개념)은 노드로 흘리지 않는다**(2026-07-02 Part 2 §3 순수성):
    Concept 모델에서 misconception_text 슬롯을 제거했다. 원시 `misconception` 값은 콘텐츠
    코퍼스(pedagogy 계층·ConceptContent)로만 흐르고 identity 노드엔 담지 않는다.
  - review_status: definition_provenance가 "수기 검수"면 reviewed, 그 외 pending(§4)
  - prerequisite_concept_ids: 엣지에서 역으로 채움(to=후행 개념의 캐시에 from=선수 ID 추가)

매핑 규칙(prerequisite_edges.jsonl → ConceptEdge):
  - relation = PREREQUISITE(데이터셋 relation은 '선수(prereq)' 단일 — 검증)
  - src/dst = idmap[from_id]/idmap[to_id]  ← 새 ID 변환
  - **evidence 합성**: 데이터셋 엣지엔 evidence/strength가 없다. 모델은 evidence 비공백·
    strength 필수 → 기본값 evidence="전문가 작성 개념그래프 v1"·evidence_source=EXPERT_REVIEW·
    strength=_DEFAULT_EDGE_STRENGTH 합성(전 엣지 동일 — 데이터셋이 강도 미보유).

법적·redaction(§3·CLAUDE.md): description·formal_definition은 *어느 산출 필드에도 싣지
않는다*. Concept 모델에 슬롯이 없어 구조적으로 차단되며, 입력 레코드의 해당 키는 *읽지도 않는다*.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field

from data_pipeline.concept_graph.idmap import build_alias_map, build_id_map
from data_pipeline.concept_graph.models import (
    Concept,
    ConceptEdge,
    EvidenceSource,
    Relation,
    ReviewStatus,
)
from data_pipeline.ncic.transform import (
    TransformError,
    infer_school_and_band,
    parse_standard_code,
)

logger = logging.getLogger("data_pipeline.concept_graph.transform")

# definition_provenance가 이 값(완전일치)이면 reviewed. §4 분포: 수기 검수 114건.
_REVIEWED_PROVENANCE: str = "수기 검수"
# 출처를 보존하면서 검수 완료를 표기하는 마커(예: "…별책8(기본수학)·AI 검수(수식·오개념 정합)").
# definition_provenance에 이 마커가 포함되면 reviewed — 출처 문자열(별책8 등)은 그대로 살린다.
_REVIEW_MARKER: str = "·AI 검수"

# 데이터셋 엣지 relation 단일 값(검증용). 그 외 값은 경고 후 PREREQUISITE로 강제하지 않고 건너뜀.
_DATASET_PREREQ_RELATION: str = "선수(prereq)"

# 엣지 evidence/strength 합성 기본값(데이터셋이 강도·근거 텍스트 미보유 — 모델 필수 충족).
_DEFAULT_EDGE_EVIDENCE: str = "전문가 작성 개념그래프 v1"
_DEFAULT_EDGE_STRENGTH: float = 0.8

# 절대 읽지 않는 redaction 대상 키(방어적 명시 — 입력에 없어야 하지만 들어와도 무시).
_REDACTED_INPUT_KEYS: frozenset[str] = frozenset({"description", "formal_definition"})


@dataclass(slots=True)
class TransformResult:
    """데이터셋 → 모델 정형화 산출.

    `concepts`/`edges`는 검증·적재로 흐르는 코어. `passthrough_flashcards`/
    `passthrough_intl`은 *모델 매핑 없이* 보존만 한 raw(후속 슬라이스 입력). `skipped`는
    파싱/매핑 실패로 제외된 항목 메시지(전문가 확인용).
    """

    concepts: list[Concept] = field(default_factory=list)
    edges: list[ConceptEdge] = field(default_factory=list)
    passthrough_flashcards: list[dict[str, object]] = field(default_factory=list)
    passthrough_intl: list[dict[str, object]] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)

    def summary(self) -> str:
        """사람 가독 요약."""
        reviewed = sum(1 for c in self.concepts if c.review_status == ReviewStatus.REVIEWED.value)
        return (
            f"정형화: 개념 {len(self.concepts)}개(reviewed {reviewed}·"
            f"pending {len(self.concepts) - reviewed}), 엣지 {len(self.edges)}개, "
            f"flashcards(raw) {len(self.passthrough_flashcards)}개, "
            f"intl(raw) {len(self.passthrough_intl)}개, skip {len(self.skipped)}건"
        )


def _grade_band_hint(standard_codes: Sequence[str]) -> str | None:
    """첫 파싱 가능한 standard_code → NCIC 학년군 문자열. 모두 실패면 None(단정 아닌 힌트)."""
    for code in standard_codes:
        try:
            grade, _subject, _domain, _seq = parse_standard_code(code)
            _school, band = infer_school_and_band(grade)
            return band
        except (TransformError, ValueError):
            continue
    return None


def _review_status(definition_provenance: str | None) -> ReviewStatus:
    """definition_provenance → 검수 상태.

    '수기 검수'(완전일치) 또는 검수 마커(`·AI 검수`) 포함이면 reviewed, 그 외(자동·검수필요)는
    pending. 마커 방식은 출처 문자열(예 '별책8(기본수학)')을 보존하면서 검수 완료를 덧붙인다(§4).
    """
    provenance = (definition_provenance or "").strip()
    if provenance == _REVIEWED_PROVENANCE or _REVIEW_MARKER in provenance:
        return ReviewStatus.REVIEWED
    return ReviewStatus.PENDING


def _opt(value: object) -> str | None:
    """빈 문자열·None → None, 그 외 str 변환(풍부 필드 정규화). 공백만도 None 취급."""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _int_opt(value: object) -> int | None:
    """difficulty_tier 등 정수 옵션 파싱. 빈/None/비정수는 None(검증은 Pydantic ge/le에 위임)."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    try:
        return int(str(value).strip())
    except ValueError:
        return None


def transform_concepts(
    records: Iterable[Mapping[str, object]],
    id_map: Mapping[str, str],
    alias_map: Mapping[str, Sequence[str]] | None = None,
) -> tuple[list[Concept], list[str]]:
    """concepts.jsonl 레코드 → `Concept` 목록 + skip 메시지.

    concept_id는 `id_map[src_id]`(새 ID), source_id=src_id, aliases=`alias_map[src_id]`(옛 UC +
    src_id). alias_map 미지정 시 aliases는 빈 목록(단위테스트 편의 — 실행 경로는 항상 주입).
    prerequisite_concept_ids는 *여기서 비워둔다* — 엣지 정형화 후 캐시를 역채움한다
    (transform_dataset에서 합류). redaction 키는 읽지 않는다.
    """
    aliases_by_src = alias_map or {}
    concepts: list[Concept] = []
    skipped: list[str] = []
    for record in records:
        src_id = str(record.get("src_id", "")).strip()
        if not src_id:
            skipped.append(f"concept: src_id 없음 — {record!r}")
            continue
        cid = id_map.get(src_id)
        if cid is None:
            skipped.append(f"concept {src_id}: id_map에 concept_id 없음")
            continue

        raw_codes = record.get("standard_codes") or []
        codes = [str(c) for c in raw_codes] if isinstance(raw_codes, Sequence) else []
        try:
            concept = Concept(
                concept_id=cid,
                source_id=src_id,
                aliases=list(aliases_by_src.get(src_id, [])),
                name_ko=str(record.get("name_ko", "")),
                name_en=None,
                name_ja=None,
                domain=str(record.get("category", "")),
                grade_band_hint=_grade_band_hint(codes),
                standard_codes=codes,
                metaphor=_opt(record.get("metaphor")),
                accepted_expressions=_opt(record.get("accepted_expressions")),
                ccss_code=_opt(record.get("ccss_code")),
                difficulty_tier=_int_opt(record.get("difficulty_tier")),
                review_status=_review_status(_opt(record.get("definition_provenance"))),
            )
        except (ValueError, TypeError) as exc:
            skipped.append(f"concept {src_id} ({cid}): {type(exc).__name__}")
            continue
        concepts.append(concept)
    return concepts, skipped


def transform_edges(
    records: Iterable[Mapping[str, object]],
    id_map: Mapping[str, str],
) -> tuple[list[ConceptEdge], list[str]]:
    """prerequisite_edges.jsonl 레코드 → `ConceptEdge` 목록(evidence 합성) + skip 메시지.

    from/to id를 새 concept_id로 변환(id_map). id_map에 없는 끝점·비-선수 relation은 skip
    (억지 매핑 금지).
    """
    edges: list[ConceptEdge] = []
    skipped: list[str] = []
    for record in records:
        from_id = str(record.get("from_id", "")).strip()
        to_id = str(record.get("to_id", "")).strip()
        relation = str(record.get("relation", "")).strip()
        ref = f"{from_id}→{to_id}"

        if relation != _DATASET_PREREQ_RELATION:
            skipped.append(f"edge {ref}: 미지원 relation {relation!r}")
            continue
        src = id_map.get(from_id)
        dst = id_map.get(to_id)
        if src is None or dst is None:
            missing = from_id if src is None else to_id
            skipped.append(f"edge {ref}: id_map에 concept_id 없음({missing})")
            continue
        try:
            edges.append(
                ConceptEdge(
                    src_concept_id=src,
                    dst_concept_id=dst,
                    relation=Relation.PREREQUISITE,
                    strength=_DEFAULT_EDGE_STRENGTH,
                    evidence=_DEFAULT_EDGE_EVIDENCE,
                    evidence_source=EvidenceSource.EXPERT_REVIEW,
                )
            )
        except (ValueError, TypeError) as exc:
            skipped.append(f"edge {ref}: {type(exc).__name__}")
            continue
    return edges, skipped


def _fill_prerequisite_cache(concepts: Sequence[Concept], edges: Sequence[ConceptEdge]) -> None:
    """엣지(src=선수→dst=후행) → 각 dst 개념의 prerequisite_concept_ids 캐시 채움(in-place).

    §2.1 'Edge(prerequisite)와 중복 저장(조회 캐시)'. 결정론적 순서(엣지 순서)·중복 제거.
    """
    by_id: dict[str, Concept] = {c.concept_id: c for c in concepts}
    for edge in edges:
        if edge.relation != Relation.PREREQUISITE.value:
            continue
        target = by_id.get(edge.dst_concept_id)
        if target is None:
            continue
        if edge.src_concept_id not in target.prerequisite_concept_ids:
            target.prerequisite_concept_ids.append(edge.src_concept_id)


def _passthrough(records: Iterable[Mapping[str, object]]) -> list[dict[str, object]]:
    """flashcards·intl raw 보존(모델 매핑 없음). redaction 키는 제외하고 dict 복사.

    제외 대상은 (a) 정적 `_REDACTED_INPUT_KEYS`(description·formal_definition) + (b) 각 레코드가
    자기기술한 `_redacted_fields` 마커가 가리키는 키(예 intl의 ccss_statement_en). 데이터셋이
    redaction을 마커로 선언하므로 이를 신뢰해 *동적으로* 막는다(이중 방어 — 입력에 본문이 남아도
    산출에서 제거). 본문 비복제(§3·CLAUDE.md)는 협상 불가라 보수적으로 처리한다.
    """
    rows: list[dict[str, object]] = []
    for record in records:
        marker = record.get("_redacted_fields")
        declared: set[str] = (
            {str(k) for k in marker} if isinstance(marker, (list, tuple, set)) else set()
        )
        drop = _REDACTED_INPUT_KEYS | declared
        rows.append({k: v for k, v in record.items() if k not in drop})
    return rows


def transform_dataset(
    *,
    concept_records: Sequence[Mapping[str, object]],
    edge_records: Sequence[Mapping[str, object]],
    flashcard_records: Sequence[Mapping[str, object]] | None = None,
    intl_records: Sequence[Mapping[str, object]] | None = None,
    overrides: Mapping[str, str] | None = None,
) -> TransformResult:
    """5종 데이터셋 → 정형화 산출(개념·엣지 코어 + raw 패스스루).

    ID 매핑(idmap)을 먼저 만들고(`{TRACK}-{AREA}-{NNN}` + 옛 UC 별칭), 개념·엣지를 변환한 뒤
    prerequisite 캐시를 역채움한다. flashcards·intl은 raw 보존만(슬라이스 1 범위 밖).
    standard_ccss_map은 concept.ccss_code로 이미 흡수되어 인자로 받지 않는다.
    """
    id_map = build_id_map(concept_records, overrides=overrides)
    alias_map = build_alias_map(concept_records)

    concepts, c_skips = transform_concepts(concept_records, id_map, alias_map)
    edges, e_skips = transform_edges(edge_records, id_map)
    _fill_prerequisite_cache(concepts, edges)

    result = TransformResult(
        concepts=concepts,
        edges=edges,
        passthrough_flashcards=_passthrough(flashcard_records or []),
        passthrough_intl=_passthrough(intl_records or []),
        skipped=c_skips + e_skips,
    )
    logger.info(result.summary())
    return result


__all__ = [
    "TransformResult",
    "transform_concepts",
    "transform_dataset",
    "transform_edges",
]
