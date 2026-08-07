"""problem_relation 계보(S4-14) *거버넌스* — 실 코퍼스 대조 참조 무결성·anti-explosion 동결.

`test_relink_governance.py` 패턴 미러(hermetic·PG 불요·전건 커밋 코퍼스 대조):

  ① 소스 코퍼스 실재 — 부재 시 조용한 skip 대신 명시 실패(거버넌스는 loud)
  ② 관계 태깅이 실재하는 코퍼스에는 행 수 > 0(배선 자체가 죽어있지 않음을 동결 — 조용한 무력화
     방지. rephrased_v0·generated_v0가 대상)
  ③ parent_slug 참조 무결성 — 전 코퍼스 slug 합집합 안에서만 부모를 가리킨다(dangling 0)
  ④ 자기 관계 0 — 어떤 태그도 자신의 slug를 부모로 가리키지 않는다
  ⑤ relation_type ⊆ RelationType enum 값
  ⑥ 레코드당 관계 수 상한 — anti-explosion 역행 감지(선형 체인 설계가 전 쌍 연결로 퇴행하면
     여기서 즉시 적발)

코퍼스가 재유도·재저작되어 dangling·자기참조·폭발이 생기면 여기서 잡는다(드리프트 감지).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from whymath_backend.schema.enums import RelationType

# 레포 루트 앵커(tests/backend/l1/problem_bank/ → parents[4]) — `test_relink_governance.py` 동형.
_ROOT = Path(__file__).resolve().parents[4]
_CORPUS_DIR = _ROOT / "data" / "corpus"

# 관계 재료를 담는 4 문제코퍼스 — v1/misconception_mc_v0는 이번 슬라이스 배선 밖(0건 허용).
_PROBLEM_CORPORA: dict[str, Path] = {
    "problem_bank_v1": _CORPUS_DIR / "problem_bank_v1" / "problems.jsonl",
    "problem_bank_generated_v0": _CORPUS_DIR / "problem_bank_generated_v0" / "problems.jsonl",
    "problem_bank_rephrased_v0": _CORPUS_DIR / "problem_bank_rephrased_v0" / "problems.jsonl",
    "problem_bank_misconception_mc_v0": (
        _CORPUS_DIR / "problem_bank_misconception_mc_v0" / "problems.jsonl"
    ),
}

# ② 이번 슬라이스에서 관계 배선이 *실제로 살아있어야* 하는 코퍼스(행 수 > 0 하한).
_WIRED_CORPORA: frozenset[str] = frozenset(
    {"problem_bank_generated_v0", "problem_bank_rephrased_v0"}
)

# ⑥ 레코드당 관계 수 상한 — 선형 체인(K=3 백엣지 + 변형 1건 정도) 설계 상 여유를 둔 낮은 상수.
# 이 이상이면 그룹핑이 무너져 전 쌍 연결(anti-explosion 위반)로 퇴행했을 가능성이 높다.
_MAX_RELATIONS_PER_RECORD = 10

_RELATION_TYPE_VALUES: frozenset[str] = frozenset(r.value for r in RelationType)


def _iter_rows(path: Path) -> list[dict[str, object]]:
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def _all_slugs() -> set[str]:
    slugs: set[str] = set()
    for path in _PROBLEM_CORPORA.values():
        if not path.exists():
            continue
        slugs.update(str(row["slug"]) for row in _iter_rows(path))
    return slugs


def test_corpora_exist() -> None:
    """소스 코퍼스 전부 커밋 존재 — 부재 시 조용한 skip 대신 명시 실패(거버넌스는 loud)."""
    for name, path in _PROBLEM_CORPORA.items():
        assert path.exists(), f"코퍼스 부재: {name}({path})"


def test_wired_corpora_have_relations() -> None:
    """관계 배선 대상 코퍼스는 실제로 관계 태깅 행 수 > 0(조용한 무력화 방지)."""
    for name in _WIRED_CORPORA:
        rows = _iter_rows(_PROBLEM_CORPORA[name])
        count = sum(len(row.get("relations") or []) for row in rows)
        assert count > 0, f"{name}: 관계 태깅 0건 — 배선이 죽어있다(populate_relations 회귀?)"


def test_parent_slug_references_are_not_dangling() -> None:
    """모든 relations[].parent_slug가 코퍼스 전체 slug 합집합 안에 실재(dangling 0)."""
    universe = _all_slugs()
    for name, path in _PROBLEM_CORPORA.items():
        for row in _iter_rows(path):
            for rel in row.get("relations") or []:
                parent = str(rel["parent_slug"])
                assert parent in universe, (
                    f"{name}: slug={row.get('slug')} 관계 parent_slug={parent} "
                    f"가 전 코퍼스 slug 밖(dangling) — populate 시 orphan skip으로 소실."
                )


def test_no_self_relation() -> None:
    """어떤 레코드도 자기 자신을 부모로 가리키지 않는다(스키마 불변식의 저장소 재확인)."""
    for name, path in _PROBLEM_CORPORA.items():
        for row in _iter_rows(path):
            slug = str(row.get("slug"))
            for rel in row.get("relations") or []:
                assert rel["parent_slug"] != slug, f"{name}: {slug} 자기 관계 발견"


def test_relation_type_within_enum() -> None:
    """relation_type은 전부 RelationType enum 값 안(authoring 위생의 저장소 재확인)."""
    for name, path in _PROBLEM_CORPORA.items():
        for row in _iter_rows(path):
            for rel in row.get("relations") or []:
                assert rel["relation_type"] in _RELATION_TYPE_VALUES, (
                    f"{name}: {row.get('slug')} relation_type={rel['relation_type']!r} "
                    f"이 RelationType 밖"
                )


def test_relation_count_per_record_bounded() -> None:
    """레코드당 관계 수 상한 — anti-explosion 역행(전 쌍 연결 등) 감지."""
    for name, path in _PROBLEM_CORPORA.items():
        for row in _iter_rows(path):
            count = len(row.get("relations") or [])
            assert count <= _MAX_RELATIONS_PER_RECORD, (
                f"{name}: {row.get('slug')} 관계 {count}건 > 상한 {_MAX_RELATIONS_PER_RECORD} "
                f"— 그룹핑 붕괴(전 쌍 연결 회귀?) 의심"
            )


@pytest.mark.parametrize("name", sorted(_WIRED_CORPORA))
def test_similar_and_rephrase_relation_types_present(name: str) -> None:
    """관계 배선 대상 코퍼스에 최소 1건 이상의 실제 관계 유형이 실린다(빈 배선 방지 이중 확인)."""
    rows = _iter_rows(_PROBLEM_CORPORA[name])
    seen_types = {str(rel["relation_type"]) for row in rows for rel in (row.get("relations") or [])}
    assert seen_types, f"{name}: 관계 유형 0종 — 배선 무력화 의심"
    assert seen_types <= _RELATION_TYPE_VALUES
