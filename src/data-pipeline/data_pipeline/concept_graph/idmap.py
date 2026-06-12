"""데이터셋 v1 `src_id` → Universal Concept ID(UC) **결정론적** 매핑.

정본: docs/data/concept_graph.md §2.4(UC 규약)·§3.5(ID 안정성) +
docs/data/concept_graph_dataset_v1.md §2(주의: 데이터셋 src_id는 UC와 *다르다* — 매핑 선행).

문제: 데이터셋 `src_id`(N1·HK01·H:12대수01-01 …)는 UC 규약과 형태가 다르다. 또 여러 개념이
*같은* NCIC 성취기준을 공유한다(예 F7·F8·F9 → 모두 [6수01-06]) — 그래서 성취기준 코드만으로
UC를 만들면 충돌이 난다(실측 7건). 해법:

  - **도메인·토픽**은 첫 standard_code에서 파생(교육과정 의미 보존): `UC.<과목약칭>.a<영역코드>.…`
    (seed.build_concept_id과 동일한 _subject_abbr·parse_standard_code 재사용).
  - **slug**는 `src_id`에서 파생(유일성 보장): src_id가 데이터셋 내에서 유일하므로 slug도 유일.
  - standard_codes가 비었거나 파싱 실패면 **폴백** `UC.x.misc.<src-slug>`(category가 아닌 src
    기반 — category는 한글이라 ascii UC에 직접 못 싣고, src가 이미 유일).

성질:
  - **결정론적**: 같은 입력 → 같은 UC(재실행 멱등). 안정 해시 불요(src_id 자체가 키).
  - **충돌 0**: src_id 유일 → slug 유일 → UC 유일(403개 검증). 충돌 시 build_id_map이 예외.
  - **재명명 가능**: `overrides`(src_id→UC)를 주입하면 전문가가 의미있는 UC로 교체 가능
    (override UC도 CONCEPT_ID_PATTERN을 통과해야 한다 — 검증).
  - **규약 준수**: 산출 UC는 모두 models.CONCEPT_ID_PATTERN을 통과.

법적: 여기서는 성취기준 *코드*만 읽어 도메인/토픽을 만든다 — 본문은 일절 만지지 않는다.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Iterable, Mapping, Sequence

from data_pipeline.concept_graph.models import CONCEPT_ID_PATTERN
from data_pipeline.concept_graph.seed import _subject_abbr
from data_pipeline.ncic.transform import TransformError, parse_standard_code

logger = logging.getLogger("data_pipeline.concept_graph.idmap")

# 폴백 도메인·토픽(standard_codes 없음/파싱 실패 시). UC 규약 ascii 슬롯.
_FALLBACK_DOMAIN: str = "x"
_FALLBACK_TOPIC: str = "misc"

# src_id → UC slug 안전화에 쓰는 치환 규칙.
_SLUG_NON_ALNUM = re.compile(r"[^a-z0-9-]+")
_SLUG_MULTI_DASH = re.compile(r"-+")


def slugify_src_id(src_id: str) -> str:
    """`src_id` → UC slug 토큰(소문자·숫자·하이픈, CONCEPT_ID_PATTERN slug 파트 호환).

    'N1'→'n1', 'HK01'→'hk01', 'H:12대수01-01'→'h-12-01-01'(콜론·한글 제거). 영숫자가
    하나도 안 남으면(이론상) ValueError — 호출부에서 막아야 하는 비정상 입력.
    """
    lowered = src_id.lower().replace(":", "-")
    cleaned = _SLUG_NON_ALNUM.sub("-", lowered)
    collapsed = _SLUG_MULTI_DASH.sub("-", cleaned).strip("-")
    if not collapsed:
        raise ValueError(f"src_id에서 UC slug를 만들 수 없음(영숫자 없음): {src_id!r}")
    return collapsed


def _domain_topic_from_codes(standard_codes: Sequence[str]) -> tuple[str, str]:
    """첫 파싱 가능한 standard_code → (도메인약칭, 토픽). 모두 실패면 폴백.

    여러 코드 중 *맨 앞의 파싱 성공* 코드를 대표로 쓴다(다중 매핑 개념도 결정론적으로 한 도메인).
    """
    for code in standard_codes:
        try:
            _grade, subject_token, domain_code, _seq = parse_standard_code(code)
        except TransformError:
            continue
        return _subject_abbr(subject_token), f"a{domain_code}"
    return _FALLBACK_DOMAIN, _FALLBACK_TOPIC


def build_concept_uc(src_id: str, standard_codes: Sequence[str]) -> str:
    """단일 `src_id`(+ 그 standard_codes) → 결정론적 UC.

    도메인/토픽은 성취기준 코드 기반(의미), slug는 src_id 기반(유일성). 폴백은 UC.x.misc.<slug>.
    산출 UC는 CONCEPT_ID_PATTERN을 통과한다(아니면 ValueError — 슬러그화 버그 가드).
    """
    domain, topic = _domain_topic_from_codes(standard_codes)
    slug = slugify_src_id(src_id)
    uc = f"UC.{domain}.{topic}.{slug}"
    if not CONCEPT_ID_PATTERN.match(uc):  # pragma: no cover - 슬러그화가 규약을 보장하나 방어
        raise ValueError(f"생성 UC가 규약 위반: {uc!r} (src_id={src_id!r})")
    return uc


def _validate_overrides(override_map: Mapping[str, str]) -> None:
    """override UC들이 규약을 지키고 서로 충돌하지 않는지 선검증."""
    seen: dict[str, str] = {}
    for src_id, uc in override_map.items():
        if not CONCEPT_ID_PATTERN.match(uc):
            raise ValueError(f"override UC 규약 위반: {src_id!r} → {uc!r}")
        if uc in seen:
            raise ValueError(f"override UC 충돌: {uc!r}를 {seen[uc]!r}·{src_id!r}가 공유")
        seen[uc] = src_id


def build_id_map(
    concepts: Iterable[Mapping[str, object]],
    *,
    overrides: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """concepts 레코드들 → {src_id: UC} 매핑 테이블(검토용·transform 입력).

    Args:
        concepts: 각 레코드는 최소 'src_id'와 'standard_codes'(list[str]) 키를 가진 매핑.
        overrides: 전문가 재명명 {src_id: UC}. 주입 시 그 src_id는 결정론 규칙 대신 override
            UC를 쓴다(단, override UC도 CONCEPT_ID_PATTERN 통과·매핑 내 유일해야 함).

    Returns:
        {src_id: UC}. 입력 순서 보존(dict 삽입 순서).

    Raises:
        ValueError: src_id 중복, UC 충돌(서로 다른 src_id가 같은 UC), override 규약 위반,
            또는 빈 src_id.
    """
    override_map = dict(overrides or {})
    _validate_overrides(override_map)

    result: dict[str, str] = {}
    uc_to_src: dict[str, str] = {}
    for record in concepts:
        src_id = str(record.get("src_id", "")).strip()
        if not src_id:
            raise ValueError(f"src_id가 빈 레코드: {record!r}")
        if src_id in result:
            raise ValueError(f"src_id 중복: {src_id!r}")

        if src_id in override_map:
            uc = override_map[src_id]
        else:
            raw_codes = record.get("standard_codes") or []
            codes = [str(c) for c in raw_codes] if isinstance(raw_codes, Sequence) else []
            uc = build_concept_uc(src_id, codes)

        if uc in uc_to_src:
            raise ValueError(
                f"UC 충돌: {uc!r}를 {uc_to_src[uc]!r}와 {src_id!r}가 공유 "
                "(slug는 src_id 유일성에 의존 — src_id 중복 또는 override 충돌 의심)"
            )
        uc_to_src[uc] = src_id
        result[src_id] = uc

    logger.info("UC 매핑 생성: %d개 src_id → %d개 유일 UC", len(result), len(uc_to_src))
    return result


def to_csv_rows(id_map: Mapping[str, str]) -> list[dict[str, str]]:
    """매핑 테이블 → CSV 행(검토용). 컬럼: src_id, concept_id(UC)."""
    return [{"src_id": src_id, "concept_id": uc} for src_id, uc in id_map.items()]


__all__ = [
    "build_concept_uc",
    "build_id_map",
    "slugify_src_id",
    "to_csv_rows",
]
