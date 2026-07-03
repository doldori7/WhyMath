"""Canonical ID Registry(`ids.yaml`) 조립·직렬화 — P2d·Part 9.

정본: docs/data/concept_graph.md §2.4(ID 규약)·docs/standards/part9_id_policy_review.md(③ registry).

배경(2026-07-02 P2d·Part 9 ③): concept_id 재명명(옛 UC → 교육과정축 코드 → canonical)의 *이력*을
추적하는 registry가 부재했다. 이 모듈은 idmap의 canonical/교육과정축/레거시UC 매핑을 합성해 각
개념의 **canonical_id·src_id·aliases·slug 원천·마이그레이션 이벤트(P2a·P2d)**를 담은 registry
dict를 만들고, 이를 `ids.yaml`(YAML)로 직렬화한다. registry는 graph.json·locale과 함께 단일
`concept_records` 원천에서 co-generate되어 드리프트가 없다(§단일 진실).

동결 정책: canonical_id는 첫 `ids.yaml` 커밋 시 영구 동결된다 — slug 교체는 명시적 rename
이벤트(migrations append)로만 하고 침묵 변경하지 않는다. name_en을 나중에 저작해도 canonical은
불변이고 locale만 개선된다.
"""

from __future__ import annotations

from typing import Any

import yaml

from data_pipeline.concept_graph.idmap import (
    build_curriculum_axis_map,
    build_id_map,
    build_legacy_uc_map,
)

# registry 스키마 버전 — 구조 변경 시 증가(소비처 하위호환 판정).
REGISTRY_VERSION: int = 1

# 재생성 커맨드(생성물 헤더·generated_by) — 수기 편집 대신 이 커맨드로 재생성한다.
GENERATED_BY: str = "python -m data_pipeline.concept_graph gen-ids"

# 마이그레이션 이벤트 상수 — 개념별 migrations 엔트리가 event/date를 이 상수에서 취한다.
#   P2a(2026-06-16): 옛 UC → 교육과정축 코드({TRACK}-{AREA}-{NNN}). 지금은 오버레이/별칭으로 격하.
#   P2d(2026-07-02): 교육과정축 코드 → canonical(math.<area>.<slug>). 교육과정-독립 의미론 ID.
P2A_EVENT: dict[str, str] = {
    "event": "P2a",
    "date": "2026-06-16",
    "description": "옛 UC → 교육과정축 코드({TRACK}-{AREA}-{NNN}) 전환(현 오버레이/별칭)",
}
P2D_EVENT: dict[str, str] = {
    "event": "P2d",
    "date": "2026-07-02",
    "description": "교육과정축 코드 → canonical(math.<area>.<slug>) 전환(교육과정-독립 의미론 ID)",
}

# YAML 헤더 주석(수기 편집 금지·재생성 안내).
_HEADER_COMMENT: str = f"# 자동 생성물 — 수기 편집 금지. 재생성: {GENERATED_BY}\n"


def build_registry(
    concepts: list[dict[str, Any]] | list[Any],
    *,
    overrides: dict[str, str] | None = None,
) -> dict[str, Any]:
    """concepts 레코드들 → Canonical ID Registry dict.

    idmap의 canonical(build_id_map)·교육과정축(build_curriculum_axis_map)·레거시UC
    (build_legacy_uc_map) 매핑을 합성한다. 개념 순서는 canonical id_map의 삽입(입력) 순서를 따른다
    (결정론·멱등).

    각 개념 엔트리:
      - canonical_id: math.<area>.<slug>(정본)
      - src_id: 원천 데이터셋 식별자
      - aliases: [교육과정축 코드, 레거시 UC, src_id](build_alias_map과 동일 순서)
      - slug_source: "name_ko"(canonical slug 파생 원천)
      - migrations: [P2a(uc→axis), P2d(axis→canonical)] 이력

    Args:
        concepts: 각 레코드는 최소 'src_id'·'category'·'name_ko'를 가진 매핑.
        overrides: canonical build_id_map으로 전달할 전문가 재명명({src_id: canonical_id}).

    Returns:
        {version, generated_by, concepts: [...]}.
    """
    records = list(concepts)
    canonical = build_id_map(records, overrides=overrides)
    axis = build_curriculum_axis_map(records)
    uc = build_legacy_uc_map(records)

    entries: list[dict[str, Any]] = []
    for src_id, canonical_id in canonical.items():
        axis_code = axis[src_id]
        uc_code = uc[src_id]
        entries.append(
            {
                "canonical_id": canonical_id,
                "src_id": src_id,
                "aliases": [axis_code, uc_code, src_id],
                "slug_source": "name_ko",
                "migrations": [
                    {
                        "event": P2A_EVENT["event"],
                        "date": P2A_EVENT["date"],
                        "from": uc_code,
                        "to": axis_code,
                    },
                    {
                        "event": P2D_EVENT["event"],
                        "date": P2D_EVENT["date"],
                        "from": axis_code,
                        "to": canonical_id,
                    },
                ],
            }
        )

    return {
        "version": REGISTRY_VERSION,
        "generated_by": GENERATED_BY,
        "concepts": entries,
    }


def dump_registry_yaml(registry: dict[str, Any]) -> str:
    """registry dict → `ids.yaml` 본문(헤더 주석 + YAML). 결정론적(sort_keys=False·입력순 보존)."""
    body = yaml.safe_dump(
        registry,
        allow_unicode=True,
        sort_keys=False,
        default_flow_style=False,
    )
    return _HEADER_COMMENT + body


def load_registry_yaml(text: str) -> dict[str, Any]:
    """`ids.yaml` 본문 → registry dict(헤더 주석은 YAML 파서가 무시)."""
    loaded = yaml.safe_load(text)
    if not isinstance(loaded, dict):
        raise ValueError(f"ids.yaml 최상위가 매핑이 아님: {type(loaded).__name__}")
    return loaded


__all__ = [
    "GENERATED_BY",
    "P2A_EVENT",
    "P2D_EVENT",
    "REGISTRY_VERSION",
    "build_registry",
    "dump_registry_yaml",
    "load_registry_yaml",
]
