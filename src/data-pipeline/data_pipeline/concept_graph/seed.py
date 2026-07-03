"""단계 3 — NCIC 성취기준에서 *후보* 개념 노드·prerequisite 엣지 시드 생성.

정본: docs/data/concept_graph.md §3.1·§4·§6.2. 자동화 범위는 (a) 성취기준 → 후보 Concept
*시드*, (b) parent_codes에서 prerequisite 후보 엣지 *제안*까지다. 노드 표기(locale)·
6종 관계 확정·strength·evidence는 **전문가 작성**(단계 4) 몫이라 CSV에 *빈칸*으로 남긴다.

ncic의 `RawStandardRecord`(느슨) → `AchievementStandard`(strict) 2단 패턴과 동형:
여기 CSV는 느슨한 후보(빈칸 허용)이고, 전문가가 채운 뒤 `validate.py`가 strict `Concept`/
`ConceptEdge`로 파싱·검증한다.

법적(CLAUDE.md·§1.1): 성취기준 *코드*만 `standard_codes`로 싣고 *본문(statement)*은 어떤
컬럼에도 복제하지 않는다. CSV sidecar에 `SOURCE_CITATION`(NCIC 승계 출처)을 동봉한다.
"""

from __future__ import annotations

import csv
import hashlib
import json
import logging
from collections.abc import Sequence
from datetime import datetime, timezone
from pathlib import Path

from data_pipeline.concept_graph.models import SOURCE_CITATION, EvidenceSource, Relation
from data_pipeline.ncic.models import AchievementStandard
from data_pipeline.ncic.transform import TransformError, parse_standard_code

logger = logging.getLogger("data_pipeline.concept_graph.seed")

# NCIC 과목약칭(parse_standard_code의 subject_token, 한글) → ascii 도메인약칭.
# Phase 1(고1 미적분) 중심 + 흔한 과목. 미수록 토큰은 결정론적 해시로 폴백(_subject_abbr).
# (idmap이 *레거시 UC 별칭* 생성에 이 함수를 재사용한다 — 시그니처·동작 보존 필수.)
_SUBJECT_ABBR: dict[str, str] = {
    "수": "math",
    "공수": "common",
    "공수1": "common1",
    "공수2": "common2",
    "대수": "algebra",
    "미적": "calc",
    "미적Ⅰ": "calc1",
    "미적Ⅱ": "calc2",
    "확통": "prob",
    "기하": "geom",
}

# CSV 컬럼(= Concept / ConceptEdge 필드). 빈칸 컬럼은 전문가가 채운다.
# source_id: 시드는 외부 src_id가 없어 concept_id로 채운다(신규 후보 = 자기 정체).
# aliases: 시드는 *신규* ID라 보존할 옛 키가 없다 — 빈칸(코퍼스 재ID 경로만 옛 키 보존).
# 표시이름(name_ko/en/ja): P2d·Part 9 Concept Purity로 노드에서 제거 — locale 레이어가 단일 진실.
# 시드는 후보 CSV라 표기 컬럼을 두지 않는다(전문가는 코퍼스 파이프라인에서 locale로 채움).
_CONCEPT_CSV_FIELDS: tuple[str, ...] = (
    "concept_id",
    "source_id",
    "aliases",
    "domain",
    "grade_band_hint",
    "prerequisite_concept_ids",
    "misconception_codes",
    "visualization_card_keys",
    "standard_codes",
    "notes",
)
_EDGE_CSV_FIELDS: tuple[str, ...] = (
    "src_concept_id",
    "dst_concept_id",
    "relation",
    "strength",
    "evidence",
    "evidence_source",
)

_SEED_NOTE: str = "[seed] 전문가 작성 대기 — 표기(locale)·오개념·시각화 빈칸"


def _subject_abbr(subject_token: str) -> str:
    """과목약칭(한글) → ascii 도메인약칭. 미수록은 결정론적 해시(전문가가 추후 재명명)."""
    if subject_token in _SUBJECT_ABBR:
        return _SUBJECT_ABBR[subject_token]
    return "x" + hashlib.sha1(subject_token.encode("utf-8")).hexdigest()[:6]


def build_concept_id(code: str) -> str:
    """NCIC 성취기준 코드 → 결정론적 *후보* concept_id(잠정 seed 네임스페이스 `math.seed.<...>`).

    `[9수01-01]` → `math.seed.a01-001`. 매핑: area=고정 `seed`(잠정 네임스페이스)·slug=`a`+영역코드
    (NCIC 2자리)+`-`+순번(3자리 zero-pad). 코드 유일 → ID 유일·재실행 동일(멱등).

    **Wall D(P2d·Part 9)**: 시드 경로는 NCIC *코드*만 알고 name_ko(→ 의미론 slug 원천)가 없어
    canonical 의미론 slug를 만들 수 없다. 따라서 canonical 규약(`^math\\.[a-z]+…`)을 *통과하되*
    전용 `seed` 네임스페이스로 잠정 발급한다(명백히 후보·동결). 시드 후보는 graph.json에 도달하지
    않으며(코퍼스 경로만 P2d canonical 발급), 전문가 채택 시 코퍼스 파이프라인에서 재발급된다.
    """
    _grade, _subject_token, domain_code, seq = parse_standard_code(code)
    seq_num = int(seq)
    return f"math.seed.a{domain_code}-{seq_num:03d}"


def _matches_domain(standard: AchievementStandard, domain_filter: str | None) -> bool:
    """domain 필터(부분 문자열) — subject 또는 domain에 매칭(예 '미적분'→subject '미적분Ⅰ')."""
    if domain_filter is None:
        return True
    return domain_filter in standard.subject or domain_filter in standard.domain


def seed_concepts(
    standards: Sequence[AchievementStandard],
    *,
    domain_filter: str | None = None,
) -> list[dict[str, str]]:
    """성취기준 → 후보 개념 행(CSV용 dict). 표기·오개념·시각화는 빈칸(전문가)."""
    rows: list[dict[str, str]] = []
    for std in standards:
        if not _matches_domain(std, domain_filter):
            continue
        try:
            concept_id = build_concept_id(std.code)
        except TransformError:
            logger.warning("코드 파싱 실패 — 개념 시드 건너뜀: %s", std.code)
            continue
        prereq_ids: list[str] = []
        for parent in std.parent_codes:
            try:
                prereq_ids.append(build_concept_id(parent))
            except TransformError:
                logger.warning("부모 코드 파싱 실패 — 선수 링크 누락: %s → %s", parent, std.code)
        rows.append(
            {
                "concept_id": concept_id,
                "source_id": concept_id,  # 시드는 외부 src_id 없음 — 자기 정체
                "aliases": "",  # 신규 후보 — 보존할 옛 키 없음
                "domain": std.domain,
                "grade_band_hint": std.grade_band,
                "prerequisite_concept_ids": ";".join(prereq_ids),
                "misconception_codes": "",  # 전문가
                "visualization_card_keys": "",  # 전문가
                "standard_codes": std.code,
                "notes": _SEED_NOTE,
            }
        )
    return rows


def seed_edges(
    standards: Sequence[AchievementStandard],
    *,
    domain_filter: str | None = None,
) -> list[dict[str, str]]:
    """parent_codes → prerequisite 후보 엣지 행. strength·evidence는 빈칸(전문가).

    evidence_source는 NCIC 인접성 유래라 'ncic'으로 자동 표기(근거 텍스트는 전문가가 채움).
    (src, dst) 중복은 dedup한다.
    """
    rows: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for std in standards:
        if not _matches_domain(std, domain_filter):
            continue
        try:
            dst = build_concept_id(std.code)
        except TransformError:
            continue
        for parent in std.parent_codes:
            try:
                src = build_concept_id(parent)
            except TransformError:
                continue
            if (src, dst) in seen:
                continue
            seen.add((src, dst))
            rows.append(
                {
                    "src_concept_id": src,
                    "dst_concept_id": dst,
                    "relation": Relation.PREREQUISITE.value,
                    "strength": "",  # 전문가
                    "evidence": "",  # 전문가
                    "evidence_source": EvidenceSource.NCIC.value,
                }
            )
    return rows


def _write_csv(rows: Sequence[dict[str, str]], output_path: Path, fields: tuple[str, ...]) -> int:
    """후보 행을 CSV로 저장(UTF-8-sig BOM·Excel 친화) + 출처 sidecar(.meta.json).

    ncic/load.py:write_csv 패턴. sidecar에 SOURCE_CITATION(NCIC 승계 의무)을 싣는다.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    sidecar = output_path.with_suffix(".meta.json")
    sidecar.write_text(
        json.dumps(
            {
                "source_citation": SOURCE_CITATION,
                "rows": len(rows),
                "csv_file": output_path.name,
                "stage": "seed (후보 — 전문가 작성 전)",
                "generated_at": datetime.now(tz=timezone.utc).isoformat(),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    logger.info("CSV 저장: %s (%d행) + sidecar: %s", output_path, len(rows), sidecar)
    return len(rows)


def write_concepts_csv(rows: Sequence[dict[str, str]], output_path: Path) -> int:
    """후보 개념 CSV 저장."""
    return _write_csv(rows, output_path, _CONCEPT_CSV_FIELDS)


def write_edges_csv(rows: Sequence[dict[str, str]], output_path: Path) -> int:
    """후보 엣지 CSV 저장."""
    return _write_csv(rows, output_path, _EDGE_CSV_FIELDS)
