"""단계 6 — 개념 그래프 검증(전문가가 채운 노드·엣지 대상).

정본 invariant: docs/data/concept_graph.md §5 + schemas/v1.1/{concept,edge}.schema.yaml.
구조 invariant(concept_id 형식·relation enum·strength 범위·evidence 비공백)는 `Concept`/
`ConceptEdge` *생성 시점*(Pydantic)에서 강제되므로, 여기서는 단일 모델로 알 수 없는 *그래프
레벨* invariant을 검증한다(ncic/validate.py의 컬렉션 검증과 같은 분담):

  - prerequisite 사이클 → **error**(순환 선수관계 = 학습 경로 불능)
  - generalization↔specialization 역쌍 → warning
  - 고립 노드(엣지 0개) → warning
  - dangling 참조(엣지 양끝·prerequisite 캐시·오개념·시각화) → warning(에러 아님 §3.3)
  - 데이터 상관: prerequisite 엣지의 src·dst 성취기준 학년 단조성(역전 시 warning)
  - **id_conformance**(canonical 규약·전 노드) → error
  - **curriculum_independence**(학년/트랙 토큰·NCIC 코드조각 부재·Part 9 하드게이트) → error
  - **id_unique**(canonical concept_id 충돌) → error
  - **alias_roundtrip**(source_id 존재·교육과정축 코드 AND 옛 UC AND src_id 별칭 보존) → error

별도로 `validate_idmap`(원천 레코드 대상)은 **area_map_total**(category 전수 매핑·0 미매핑)·
**id_unique**·**alias_roundtrip**를 *재ID 산출 직전*에 검증한다(P2d 불변식). `validate_registry`
(ids.yaml 대상)는 **registry_graph_parity·registry_id_unique·registry_field_match·
registry_migration_roundtrip**를, `validate_locales`(locales 대상)는 **locale_node_parity·
locale_nonblank**를 검증한다.

성공 기준은 **error 0건**(warning은 그래프 구축을 막지 않음 — 보수적, §3.3).
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field

from data_pipeline.concept_graph.idmap import build_alias_map, build_id_map
from data_pipeline.concept_graph.models import (
    CONCEPT_ID_PATTERN,
    CURRICULUM_AXIS_PATTERN,
    LEGACY_UC_PATTERN,
    MIN_EDGE_STRENGTH,
    Concept,
    ConceptEdge,
    Relation,
)
from data_pipeline.concept_graph.transform import TransformResult
from data_pipeline.ncic.transform import TransformError, parse_standard_code

_ERROR = "error"
_WARNING = "warning"

# curriculum_independence 가드 — canonical concept_id에 학년/트랙 토큰(교육과정 배치 결합)이
# 섞이지 않았는지 단언(Part 9 하드게이트 자동화). 단어 경계(\b·점 구분 토큰)로만 매칭한다.
_GRADE_TOKEN_PATTERN: re.Pattern[str] = re.compile(r"(?i)\b(elem|mid|high|rt|oly)\b")


@dataclass(slots=True)
class ValidationIssue:
    """그래프 검증 항목 1건."""

    severity: str  # "error" | "warning"
    ref: str  # concept_id 또는 "src→dst" 등 대상 식별
    rule: str
    detail: str


@dataclass(slots=True)
class GraphValidationReport:
    """그래프 검증 결과."""

    node_count: int = 0
    edge_count: int = 0
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def errors(self) -> list[ValidationIssue]:
        """error 심각도 이슈."""
        return [i for i in self.issues if i.severity == _ERROR]

    @property
    def warnings(self) -> list[ValidationIssue]:
        """warning 심각도 이슈."""
        return [i for i in self.issues if i.severity == _WARNING]

    @property
    def success(self) -> bool:
        """error가 없으면 성공(warning 허용)."""
        return len(self.errors) == 0

    def counts_by_rule(self) -> dict[str, int]:
        """rule별 이슈 건수(결정론적 — rule 이름 정렬). 리포트 집계용."""
        tally: dict[str, int] = {}
        for issue in self.issues:
            tally[issue.rule] = tally.get(issue.rule, 0) + 1
        return dict(sorted(tally.items()))

    def summary(self) -> str:
        """사람 가독 요약(pass/warn/fail = success/warning/error)."""
        verdict = "PASS" if self.success else "FAIL"
        return (
            f"그래프 검증[{verdict}]: 노드 {self.node_count}개, 엣지 {self.edge_count}개, "
            f"error {len(self.errors)}개, warning {len(self.warnings)}개"
        )

    def report_text(self, *, max_examples: int = 10) -> str:
        """pass/warn/fail 카운트 + rule별 집계 + 구체 위반 예시(실데이터 리포트).

        Phase 1은 warning을 *통과 처리*한다(§3 — 그래프 구축을 막지 않음). error만 실패.
        """
        lines = [self.summary()]
        tally = self.counts_by_rule()
        if tally:
            lines.append("  [rule별 집계]")
            for rule, count in tally.items():
                lines.append(f"    - {rule}: {count}건")
        for severity, label in ((_ERROR, "error"), (_WARNING, "warning")):
            picked = [i for i in self.issues if i.severity == severity]
            if not picked:
                continue
            lines.append(f"  [{label} 예시 (최대 {max_examples})]")
            for issue in picked[:max_examples]:
                lines.append(f"    [{label}] {issue.rule} | {issue.ref} | {issue.detail}")
        return "\n".join(lines)


def _grade_of(concept: Concept) -> int | None:
    """개념의 대표 NCIC 학년(첫 standard_code에서 파싱). 코드 없거나 파싱 실패 시 None."""
    for code in concept.standard_codes:
        try:
            grade, _subject, _domain, _seq = parse_standard_code(code)
            return int(grade)
        except (TransformError, ValueError):
            continue
    return None


def _find_prerequisite_cycle(edges: Sequence[ConceptEdge]) -> list[str] | None:
    """prerequisite 엣지 그래프(src=선수→dst=후행)에서 사이클 1건 탐지(DFS).

    Returns: 사이클을 이루는 노드 경로(닫힘 노드 반복 포함) 또는 None.
    """
    adj: dict[str, list[str]] = {}
    for edge in edges:
        if edge.relation == Relation.PREREQUISITE:
            adj.setdefault(edge.src_concept_id, []).append(edge.dst_concept_id)

    white, gray, black = 0, 1, 2
    color: dict[str, int] = {}
    path: list[str] = []

    def dfs(node: str) -> list[str] | None:
        color[node] = gray
        path.append(node)
        for nxt in adj.get(node, []):
            state = color.get(nxt, white)
            if state == gray:  # back-edge → 사이클
                return path[path.index(nxt) :] + [nxt]
            if state == white:
                found = dfs(nxt)
                if found is not None:
                    return found
        path.pop()
        color[node] = black
        return None

    for start in adj:
        if color.get(start, white) == white:
            cycle = dfs(start)
            if cycle is not None:
                return cycle
    return None


def validate_graph(
    concepts: Sequence[Concept],
    edges: Sequence[ConceptEdge],
    *,
    known_misconception_codes: Iterable[str] | None = None,
    known_visualization_keys: Iterable[str] | None = None,
) -> GraphValidationReport:
    """채워진 개념 그래프의 그래프 레벨 invariant 검증(§5).

    `known_*`를 주면 dangling 오개념·시각화 참조를 경고한다(미지정 시 외부 카탈로그가 없어
    검증 불가 — 건너뜀). 구조 invariant은 Concept/ConceptEdge 생성 시 이미 강제됨.
    """
    report = GraphValidationReport(node_count=len(concepts), edge_count=len(edges))
    node_ids = {c.concept_id for c in concepts}

    # 1. prerequisite 사이클 (error)
    cycle = _find_prerequisite_cycle(edges)
    if cycle is not None:
        report.issues.append(
            ValidationIssue(
                severity=_ERROR,
                ref=" → ".join(cycle),
                rule="prerequisite_cycle",
                detail="순환 선수관계 — 학습 경로 구성 불가",
            )
        )

    # 2. 엣지 양끝 dangling (warning)
    for edge in edges:
        for endpoint in (edge.src_concept_id, edge.dst_concept_id):
            if endpoint not in node_ids:
                report.issues.append(
                    ValidationIssue(
                        severity=_WARNING,
                        ref=f"{edge.src_concept_id}→{edge.dst_concept_id}",
                        rule="dangling_edge_endpoint",
                        detail=f"엣지 끝점이 노드 집합에 없음: {endpoint}",
                    )
                )

    # 3. generalization↔specialization 역쌍 (warning, 무순서쌍 1회)
    gen_pairs = {
        (e.src_concept_id, e.dst_concept_id) for e in edges if e.relation == Relation.GENERALIZATION
    }
    warned_inverse: set[frozenset[str]] = set()
    for e in edges:
        if (
            e.relation == Relation.SPECIALIZATION
            and (e.dst_concept_id, e.src_concept_id) in gen_pairs
        ):
            key = frozenset({e.src_concept_id, e.dst_concept_id})
            if key not in warned_inverse:
                warned_inverse.add(key)
                report.issues.append(
                    ValidationIssue(
                        severity=_WARNING,
                        ref=f"{e.src_concept_id}↔{e.dst_concept_id}",
                        rule="inverse_pair",
                        detail="generalization↔specialization 역방향 쌍 — 중복/방향 혼동 의심",
                    )
                )

    # 4. 고립 노드 (warning)
    incident: set[str] = set()
    for edge in edges:
        incident.add(edge.src_concept_id)
        incident.add(edge.dst_concept_id)
    for concept in concepts:
        if concept.concept_id not in incident:
            report.issues.append(
                ValidationIssue(
                    severity=_WARNING,
                    ref=concept.concept_id,
                    rule="isolated_node",
                    detail="엣지 0개 — 고립 노드",
                )
            )

    # 5. prerequisite_concept_ids 캐시 dangling (warning)
    for concept in concepts:
        for prereq in concept.prerequisite_concept_ids:
            if prereq not in node_ids:
                report.issues.append(
                    ValidationIssue(
                        severity=_WARNING,
                        ref=concept.concept_id,
                        rule="dangling_prerequisite_ref",
                        detail=f"prerequisite_concept_ids가 없는 노드 참조: {prereq}",
                    )
                )

    # 6. dangling 오개념·시각화 (warning — known_* 주어진 경우만)
    _check_dangling_catalog(
        report,
        concepts,
        "misconception_codes",
        "dangling_misconception",
        known_misconception_codes,
    )
    _check_dangling_catalog(
        report,
        concepts,
        "visualization_card_keys",
        "dangling_visualization",
        known_visualization_keys,
    )

    # 7. 데이터 상관: prerequisite 학년 단조성 (warning)
    grade_by_id = {c.concept_id: _grade_of(c) for c in concepts}
    for edge in edges:
        if edge.relation != Relation.PREREQUISITE:
            continue
        src_grade = grade_by_id.get(edge.src_concept_id)
        dst_grade = grade_by_id.get(edge.dst_concept_id)
        if src_grade is not None and dst_grade is not None and src_grade > dst_grade:
            report.issues.append(
                ValidationIssue(
                    severity=_WARNING,
                    ref=f"{edge.src_concept_id}→{edge.dst_concept_id}",
                    rule="grade_monotonic",
                    detail=f"선수개념 학년({src_grade})이 후행({dst_grade})보다 높음 — 역전 의심",
                )
            )

    # 7b. weight floor (warning) — strength가 MIN_EDGE_STRENGTH 미만인 약한 엣지(Part 3
    #     "낮은 weight는 제거되나?"). 데이터 품질 하한 — build-time에 약한 엣지를 가시화한다.
    #     Phase 1은 warning(적재 비차단). 런타임 동적 pruning은 소비처 생길 때 후속.
    for edge in edges:
        if edge.strength < MIN_EDGE_STRENGTH:
            report.issues.append(
                ValidationIssue(
                    severity=_WARNING,
                    ref=f"{edge.src_concept_id}→{edge.dst_concept_id}",
                    rule="weak_edge",
                    detail=(
                        f"strength {edge.strength} < 하한 {MIN_EDGE_STRENGTH} — "
                        "약한 엣지(그래프 dense화·traversal 희석 의심)"
                    ),
                )
            )

    # 7c. prerequisite 캐시 일관성 (warning) — 노드의 prerequisite_concept_ids 캐시가
    #     prerequisite *엣지*와 어긋나지 않는지(dual-truth drift 방어·단일 진실 원천).
    #     캐시 집합 == {src | prerequisite 엣지 ∧ dst==concept_id}. dangling(§5)은 별도 검사.
    prereq_edge_srcs: dict[str, set[str]] = {}
    for edge in edges:
        if edge.relation == Relation.PREREQUISITE:
            prereq_edge_srcs.setdefault(edge.dst_concept_id, set()).add(edge.src_concept_id)
    for concept in concepts:
        cache = set(concept.prerequisite_concept_ids)
        from_edges = prereq_edge_srcs.get(concept.concept_id, set())
        if cache != from_edges:
            missing = from_edges - cache  # 엣지엔 있으나 캐시에 없음
            extra = cache - from_edges  # 캐시에 있으나 엣지엔 없음
            report.issues.append(
                ValidationIssue(
                    severity=_WARNING,
                    ref=concept.concept_id,
                    rule="prerequisite_cache_consistency",
                    detail=(
                        "prerequisite_concept_ids 캐시가 prerequisite 엣지와 불일치 — "
                        f"엣지에만(캐시 누락): {sorted(missing)}·"
                        f"캐시에만(엣지 없음): {sorted(extra)}"
                    ),
                )
            )

    # 8. concept_id 새 규약 적합성 (error) — 생성 시 강제되나 *전 노드 명시 단언*(재ID 불변식).
    for concept in concepts:
        if not CONCEPT_ID_PATTERN.match(concept.concept_id):
            report.issues.append(
                ValidationIssue(
                    severity=_ERROR,
                    ref=concept.concept_id,
                    rule="id_conformance",
                    detail="concept_id가 'math.<area>.<slug>' 규약 위반",
                )
            )

    # 8b. curriculum_independence (error) — Part 9 하드게이트 자동화. canonical concept_id에
    #     학년/트랙 토큰(elem·mid·high·rt·oly = 교육과정 배치)이나 NCIC 코드조각이 섞이지 않고,
    #     교육과정-독립 canonical 규약을 완전 만족하는지 단언(옛 {TRACK}-{AREA}-{NNN} 결합 방지).
    for concept in concepts:
        cid = concept.concept_id
        if _GRADE_TOKEN_PATTERN.search(cid) or not CONCEPT_ID_PATTERN.fullmatch(cid):
            report.issues.append(
                ValidationIssue(
                    severity=_ERROR,
                    ref=cid,
                    rule="curriculum_independence",
                    detail=(
                        "concept_id에 학년/트랙 토큰 또는 교육과정 결합 흔적 — canonical은 "
                        "교육과정-독립이어야 함(math.<area>.<slug>·학년/NCIC 코드조각 금지)"
                    ),
                )
            )

    # 9. concept_id 유일성 (error) — 새 ID 충돌 0(서로 다른 개념이 같은 ID면 join 붕괴).
    id_counts: dict[str, int] = {}
    for concept in concepts:
        id_counts[concept.concept_id] = id_counts.get(concept.concept_id, 0) + 1
    for cid, count in id_counts.items():
        if count > 1:
            report.issues.append(
                ValidationIssue(
                    severity=_ERROR,
                    ref=cid,
                    rule="id_unique",
                    detail=f"concept_id 중복 {count}건 — 새 ID 충돌(NNN 부여 버그 의심)",
                )
            )

    # 10. alias 라운드트립 (error) — source_id 비공백, *재ID된* 개념은 옛 UC 별칭 + src_id 보존.
    #    재ID 판정: source_id != concept_id(원천 src_id가 새 PK와 다름 = 마이그레이션됨). 시드
    #    경로의 *신규* 후보(source_id == concept_id·옛 UC 없음)는 옛 UC 요건에서 면제한다 — 별칭은
    #    *전환*의 추적성 장치라 새로 만든 ID에는 보존할 옛 키가 없다.
    for concept in concepts:
        if not concept.source_id.strip():
            report.issues.append(
                ValidationIssue(
                    severity=_ERROR,
                    ref=concept.concept_id,
                    rule="alias_roundtrip",
                    detail="source_id 비어있음 — 원천 추적 불가",
                )
            )
            continue
        migrated = concept.source_id != concept.concept_id
        if not migrated:
            continue  # 신규 후보(시드) — 옛 키 없음·면제
        axis = [a for a in concept.aliases if CURRICULUM_AXIS_PATTERN.match(a)]
        if not axis:
            report.issues.append(
                ValidationIssue(
                    severity=_ERROR,
                    ref=concept.concept_id,
                    rule="alias_roundtrip",
                    detail=(
                        f"교육과정축 코드 별칭 미보존(aliases={concept.aliases!r}) — 조인 불가"
                    ),
                )
            )
        legacy = [a for a in concept.aliases if LEGACY_UC_PATTERN.match(a)]
        if not legacy:
            report.issues.append(
                ValidationIssue(
                    severity=_ERROR,
                    ref=concept.concept_id,
                    rule="alias_roundtrip",
                    detail=f"옛 UC 별칭 미보존(aliases={concept.aliases!r}) — 하위호환 join 불가",
                )
            )
        if concept.source_id not in concept.aliases:
            report.issues.append(
                ValidationIssue(
                    severity=_ERROR,
                    ref=concept.concept_id,
                    rule="alias_roundtrip",
                    detail=f"source_id가 aliases에 미포함({concept.aliases!r}) — 원천 키 조회 불가",
                )
            )

    return report


def _check_dangling_catalog(
    report: GraphValidationReport,
    concepts: Sequence[Concept],
    field_name: str,
    rule: str,
    known: Iterable[str] | None,
) -> None:
    """오개념·시각화 참조가 알려진 카탈로그 키 집합에 없으면 warning(known 미지정 시 skip)."""
    if known is None:
        return
    known_set = set(known)
    for concept in concepts:
        refs: list[str] = getattr(concept, field_name)
        for ref in refs:
            if ref not in known_set:
                report.issues.append(
                    ValidationIssue(
                        severity=_WARNING,
                        ref=concept.concept_id,
                        rule=rule,
                        detail=f"{field_name}가 카탈로그에 없는 키 참조: {ref}",
                    )
                )


def validate_idmap(
    concept_records: Sequence[Mapping[str, object]],
) -> GraphValidationReport:
    """원천 concepts 레코드의 *재ID 불변식*을 검증(P2 — `{TRACK}-{AREA}-{NNN}` 전환 안전망).

    `validate_graph`가 *구성된 Concept*를 보는 것과 달리, 여기서는 *원천 레코드*에서 직접
    id_map·alias_map을 만들어 다음을 단언한다:

      - **area_map_total**(error): 모든 레코드 category가 `_TOPIC_AREA_MAP`에 매핑된다(0 미매핑).
        미매핑이면 `build_id_map`이 KeyError를 던지므로, 이를 잡아 error 이슈로 보고한다.
      - **id_conformance**(error): 생성된 모든 새 ID가 CONCEPT_ID_PATTERN 통과.
      - **id_unique**(error): `{src_id: new_id}`에서 new_id 충돌 0(역매핑 1:1).
      - **alias_roundtrip**(error): 각 src_id의 별칭에 옛 UC(LEGACY_UC_PATTERN)·src_id가 모두 보존.

    node_count는 레코드 수, edge_count는 0(엣지 미검증 — 이 함수는 ID 레벨 전용).
    """
    report = GraphValidationReport(node_count=len(concept_records), edge_count=0)

    try:
        id_map = build_id_map(concept_records)
    except KeyError as exc:
        # 미매핑 category — build_id_map이 시끄럽게 실패. error로 환원(전수 매핑 위반).
        report.issues.append(
            ValidationIssue(
                severity=_ERROR,
                ref="(category)",
                rule="area_map_total",
                detail=f"미매핑 category 발견: {exc}",
            )
        )
        return report

    # area_map_total 통과(KeyError 없음) — 명시 PASS 마커는 두지 않는다(error 0 = 성공).
    alias_map = build_alias_map(concept_records)

    # id_conformance + id_unique
    id_to_src: dict[str, str] = {}
    for src_id, cid in id_map.items():
        if not CONCEPT_ID_PATTERN.match(cid):
            report.issues.append(
                ValidationIssue(
                    severity=_ERROR,
                    ref=src_id,
                    rule="id_conformance",
                    detail=f"canonical ID 규약 위반: {cid!r}",
                )
            )
        if cid in id_to_src:
            report.issues.append(
                ValidationIssue(
                    severity=_ERROR,
                    ref=cid,
                    rule="id_unique",
                    detail=f"새 ID 충돌: {id_to_src[cid]!r}·{src_id!r}가 공유",
                )
            )
        else:
            id_to_src[cid] = src_id

    # alias_roundtrip — src_id → 별칭에 교육과정축 코드·옛 UC·src_id 보존
    for src_id, aliases in alias_map.items():
        axis = [a for a in aliases if CURRICULUM_AXIS_PATTERN.match(a)]
        if not axis:
            report.issues.append(
                ValidationIssue(
                    severity=_ERROR,
                    ref=src_id,
                    rule="alias_roundtrip",
                    detail=f"교육과정축 코드 별칭 미보존: {aliases!r}",
                )
            )
        legacy = [a for a in aliases if LEGACY_UC_PATTERN.match(a)]
        if not legacy:
            report.issues.append(
                ValidationIssue(
                    severity=_ERROR,
                    ref=src_id,
                    rule="alias_roundtrip",
                    detail=f"옛 UC 별칭 미보존: {aliases!r}",
                )
            )
        if src_id not in aliases:
            report.issues.append(
                ValidationIssue(
                    severity=_ERROR,
                    ref=src_id,
                    rule="alias_roundtrip",
                    detail=f"src_id가 aliases에 미포함: {aliases!r}",
                )
            )

    return report


def validate_registry(
    registry: Mapping[str, object],
    concepts: Sequence[Concept],
) -> GraphValidationReport:
    """`ids.yaml` registry ⇄ 그래프 노드 정합성 검증(P2d ③ — Canonical ID Registry 불변식).

    ERROR 규칙:
      - **registry_graph_parity**: registry canonical_id 집합 == 그래프 concept_id 집합(고아 0·437).
      - **registry_id_unique**: registry canonical_id·src_id 중복 0.
      - **registry_field_match**: 개념별 registry source_id/aliases == 노드 source_id/aliases.
      - **registry_migration_roundtrip**: 재ID된 개념은 P2a·P2d 이벤트 보유·P2d.to==canonical_id·
        P2d.from이 교육과정축 별칭(CURRICULUM_AXIS_PATTERN·aliases 소속).
    """
    entries_raw = registry.get("concepts", [])
    entries: list[Mapping[str, object]] = (
        [e for e in entries_raw if isinstance(e, Mapping)] if isinstance(entries_raw, list) else []
    )
    report = GraphValidationReport(node_count=len(entries), edge_count=0)

    # registry_id_unique — canonical_id·src_id 중복.
    reg_by_canonical: dict[str, Mapping[str, object]] = {}
    seen_src: set[str] = set()
    for entry in entries:
        cid = str(entry.get("canonical_id", ""))
        sid = str(entry.get("src_id", ""))
        if cid in reg_by_canonical:
            report.issues.append(
                ValidationIssue(
                    severity=_ERROR,
                    ref=cid,
                    rule="registry_id_unique",
                    detail=f"registry canonical_id 중복: {cid!r}",
                )
            )
        else:
            reg_by_canonical[cid] = entry
        if sid in seen_src:
            report.issues.append(
                ValidationIssue(
                    severity=_ERROR,
                    ref=sid,
                    rule="registry_id_unique",
                    detail=f"registry src_id 중복: {sid!r}",
                )
            )
        seen_src.add(sid)

    node_by_id = {c.concept_id: c for c in concepts}

    # registry_graph_parity — 집합 일치(고아 양방향).
    reg_ids = set(reg_by_canonical)
    node_ids = set(node_by_id)
    for orphan in sorted(reg_ids - node_ids):
        report.issues.append(
            ValidationIssue(
                severity=_ERROR,
                ref=orphan,
                rule="registry_graph_parity",
                detail="registry에 있으나 그래프 노드에 없는 canonical_id",
            )
        )
    for orphan in sorted(node_ids - reg_ids):
        report.issues.append(
            ValidationIssue(
                severity=_ERROR,
                ref=orphan,
                rule="registry_graph_parity",
                detail="그래프 노드에 있으나 registry에 없는 concept_id",
            )
        )

    # registry_field_match + registry_migration_roundtrip(양쪽 존재하는 id만).
    for cid in sorted(reg_ids & node_ids):
        entry = reg_by_canonical[cid]
        node = node_by_id[cid]
        raw_aliases = entry.get("aliases", [])
        reg_aliases = [str(a) for a in raw_aliases] if isinstance(raw_aliases, list) else []
        if str(entry.get("src_id", "")) != node.source_id or reg_aliases != node.aliases:
            report.issues.append(
                ValidationIssue(
                    severity=_ERROR,
                    ref=cid,
                    rule="registry_field_match",
                    detail=(
                        f"registry↔노드 필드 불일치: registry(src_id={entry.get('src_id')!r}·"
                        f"aliases={reg_aliases!r}) vs 노드(source_id={node.source_id!r}·"
                        f"aliases={node.aliases!r})"
                    ),
                )
            )

        if node.source_id == node.concept_id:
            continue  # 비-마이그레이션(신규 후보) — 이벤트 요건 면제
        migrations_raw = entry.get("migrations", [])
        migrations: list[Mapping[str, object]] = (
            [m for m in migrations_raw if isinstance(m, Mapping)]
            if isinstance(migrations_raw, list)
            else []
        )
        events = {str(m.get("event", "")) for m in migrations}
        if not {"P2a", "P2d"} <= events:
            report.issues.append(
                ValidationIssue(
                    severity=_ERROR,
                    ref=cid,
                    rule="registry_migration_roundtrip",
                    detail=f"P2a·P2d 이벤트 미보유(events={sorted(events)})",
                )
            )
            continue
        p2d = next(m for m in migrations if str(m.get("event", "")) == "P2d")
        if str(p2d.get("to", "")) != cid:
            report.issues.append(
                ValidationIssue(
                    severity=_ERROR,
                    ref=cid,
                    rule="registry_migration_roundtrip",
                    detail=f"P2d.to({p2d.get('to')!r}) != canonical_id({cid!r})",
                )
            )
        p2d_from = str(p2d.get("from", ""))
        if not CURRICULUM_AXIS_PATTERN.match(p2d_from) or p2d_from not in reg_aliases:
            report.issues.append(
                ValidationIssue(
                    severity=_ERROR,
                    ref=cid,
                    rule="registry_migration_roundtrip",
                    detail=f"P2d.from({p2d_from!r}) 교육과정축 별칭 아님(aliases={reg_aliases!r})",
                )
            )

    return report


def validate_locales(
    locales: Mapping[str, object],
    concepts: Sequence[Concept],
) -> GraphValidationReport:
    """locale 테이블 ⇄ 그래프 노드 정합성 검증(P2d ② — 표시이름 분리 불변식).

    ERROR 규칙:
      - **locale_node_parity**: `locales["ko"]` 키 집합 == 그래프 concept_id 집합(양쪽 437·고아 0).
      - **locale_nonblank**: 모든 ko 표시이름이 비공백(빈 표기 금지).
    """
    ko_raw = locales.get("ko", {})
    ko: dict[str, str] = (
        {str(k): str(v) for k, v in ko_raw.items()} if isinstance(ko_raw, Mapping) else {}
    )
    report = GraphValidationReport(node_count=len(ko), edge_count=0)

    node_ids = {c.concept_id for c in concepts}
    ko_ids = set(ko)
    for orphan in sorted(ko_ids - node_ids):
        report.issues.append(
            ValidationIssue(
                severity=_ERROR,
                ref=orphan,
                rule="locale_node_parity",
                detail="locale(ko)에 있으나 그래프 노드에 없는 concept_id",
            )
        )
    for orphan in sorted(node_ids - ko_ids):
        report.issues.append(
            ValidationIssue(
                severity=_ERROR,
                ref=orphan,
                rule="locale_node_parity",
                detail="그래프 노드에 있으나 locale(ko) 표기가 없는 concept_id",
            )
        )

    for cid, name in ko.items():
        if not name.strip():
            report.issues.append(
                ValidationIssue(
                    severity=_ERROR,
                    ref=cid,
                    rule="locale_nonblank",
                    detail="ko 표시이름이 비공백 규약 위반(빈 표기)",
                )
            )

    return report


def validate_dataset(
    result: TransformResult,
    *,
    known_misconception_codes: Iterable[str] | None = None,
    known_visualization_keys: Iterable[str] | None = None,
) -> GraphValidationReport:
    """`TransformResult`(정형화 산출)의 개념·엣지를 그래프 검증(§5)으로 통과시키는 편의 함수.

    transform → validate를 잇는 얇은 어댑터. 구조 invariant은 정형화 시점(Pydantic)에서 이미
    강제되었고, 여기서는 그래프 레벨 invariant(사이클·dangling·역쌍·고립·학년 단조성)를 본다.
    """
    return validate_graph(
        result.concepts,
        result.edges,
        known_misconception_codes=known_misconception_codes,
        known_visualization_keys=known_visualization_keys,
    )


__all__ = [
    "GraphValidationReport",
    "ValidationIssue",
    "validate_dataset",
    "validate_graph",
    "validate_idmap",
    "validate_locales",
    "validate_registry",
]
