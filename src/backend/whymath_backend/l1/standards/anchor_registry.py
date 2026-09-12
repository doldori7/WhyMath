"""EOS 검증 앵커 세트 1급 등록 — 코퍼스 레지스트리 로더 + 무결성 게이트 (EOS-56).

앵커란
------
12월 내부 검증(EOS 전환)의 **측정 조인 축**이다. 앵커 = "성취기준 코드의 동결된 묶음"이고,
원자·오개념·문항·op-code 자산은 전부 이 코드 축으로 앵커에 귀속된다(F3·I1 계측의 조인 키).

이 모듈이 있는 이유
-------------------
G0 서명(2026-08-30) 전까지 앵커 정의는 `scripts/analysis/eos_anchor_asset_audit.py`의
`ANCHOR_DEFS` **파이썬 상수 하나**뿐이었다. 분석 스크립트 안의 상수는 ① 런타임·생산 배치가
읽을 수 없고 ② 성취기준 코퍼스가 코드를 잃어도 아무도 소리내지 않는다. 이 모듈은 그 정의를
코퍼스 파일(`data/corpus/eos_anchor_set_v1/anchors.yaml`)로 1급화하고, 그 파일이 성취기준
데이터와 어긋나면 **CI가 적색을 내게** 한다.

단방향 관례 (CLAUDE.md "YAML=소스 · DB=산출물")
----------------------------------------------
YAML이 소스다. 이 모듈은 **읽기 전용**이며 DB에 쓰지 않는다(적재가 필요해지면 별도 populate
모듈이 이 로더를 소비한다 — 역방향으로 DB에서 앵커 정의를 되읽지 않는다).

침묵 실패 금지
--------------
파일 부재·YAML 파싱 실패·필수 필드 결손·scope 오타는 전부 `AnchorRegistryError`로 **명시
실패**한다 — "못 읽었으니 앵커 0건, 위반 없음"으로 통과시키지 않는다(그 형태가 정확히
게이트를 무력화한다). 예외 메시지에는 예외 타입명을 포함한다.

계층 경계
---------
L1(데이터 기반) 코퍼스 리더다. 상위 계층(L2~L6)을 import하지 않고 DB 세션도 잡지 않는다.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

import yaml

# l1/standards/anchor_registry.py → parents[5]가 레포 루트(l1/pedagogy/compile.py 관용구).
_REPO_ROOT = Path(__file__).resolve().parents[5]

_DEFAULT_REGISTRY = Path("data/corpus/eos_anchor_set_v1/anchors.yaml")

#: 폐쇄 scope 집합 — 오타를 통과시키면 "12월 대상 6건" 집계가 조용히 틀어진다.
SCOPE_DECEMBER_2026 = "december_2026"
SCOPE_DEFERRED_2027_01 = "deferred_2027_01"
KNOWN_SCOPES: frozenset[str] = frozenset({SCOPE_DECEMBER_2026, SCOPE_DEFERRED_2027_01})

_REQUIRED_ANCHOR_FIELDS: tuple[str, ...] = (
    "id",
    "title",
    "scope",
    "school_level",
    "role",
    "codes",
    "excluded",
    "note",
    "baseline",
    "depth",
)


class AnchorRegistryError(RuntimeError):
    """앵커 레지스트리 적재·구조 검증 실패 — 조용한 0건 대신 던진다."""


@dataclass(frozen=True)
class Anchor:
    """앵커 1건 — 성취기준 코드셋과 그 경계(제외 사유)를 함께 나른다."""

    id: str
    title: str
    scope: str
    school_level: str
    grade_hint: str | None
    role: str
    codes: tuple[str, ...]
    #: 인접 코드 → 제외 사유. 경계가 문서에만 있으면 6개월 뒤 복원 불가라 데이터로 나른다.
    excluded: Mapping[str, str]
    note: str
    baseline: bool
    depth: bool
    production_cu: int | None
    review_cu: int | None

    @property
    def is_december_scope(self) -> bool:
        """12월 내부 검증 대상인가(G0 확정 6앵커)."""
        return self.scope == SCOPE_DECEMBER_2026


@dataclass(frozen=True)
class AnchorRegistry:
    """레지스트리 전체 — 앵커 목록 + 동결 표지(게이트·설계문서·성취기준 소스)."""

    anchors: tuple[Anchor, ...]
    frozen_at: str
    frozen_by_gate: str
    design_doc: str
    mapping_axis: str
    #: 앵커 코드가 실재해야 하는 코퍼스 — (경로, curriculum_revision 필터 or None).
    standards_sources: tuple[tuple[str, str | None], ...]
    source_path: Path

    def by_id(self, anchor_id: str) -> Anchor:
        for anchor in self.anchors:
            if anchor.id == anchor_id:
                return anchor
        raise KeyError(f"앵커 {anchor_id!r}가 레지스트리에 없다 ({self.source_path})")

    def in_scope(self, scope: str = SCOPE_DECEMBER_2026) -> tuple[Anchor, ...]:
        """scope로 거른 앵커 — 기본값은 12월 검증 대상(G0 확정 6건)."""
        if scope not in KNOWN_SCOPES:
            raise AnchorRegistryError(f"알 수 없는 scope {scope!r} — 허용: {sorted(KNOWN_SCOPES)}")
        return tuple(a for a in self.anchors if a.scope == scope)

    def all_codes(self) -> tuple[str, ...]:
        """등재된 전 앵커의 성취기준 코드(등록 순서 유지·중복 없음은 구조 검증이 보장)."""
        return tuple(code for anchor in self.anchors for code in anchor.codes)

    def anchor_for_code(self, code: str) -> Anchor | None:
        """코드 → 소속 앵커 역인덱스. 자산 귀속(F3·I1 계측)의 조인 진입점."""
        for anchor in self.anchors:
            if code in anchor.codes:
                return anchor
        return None


def default_registry_path() -> Path:
    """저장소 정본 레지스트리 경로."""
    return _REPO_ROOT / _DEFAULT_REGISTRY


def _require(raw: Mapping[str, Any], key: str, where: str) -> Any:
    if key not in raw:
        raise AnchorRegistryError(f"{where}: 필수 필드 {key!r} 결손")
    return raw[key]


def _parse_anchor(raw: Any, index: int, source: Path) -> Anchor:
    where = f"{source} anchors[{index}]"
    if not isinstance(raw, dict):
        raise AnchorRegistryError(f"{where}: 매핑이 아니다 (실제 {type(raw).__name__})")
    for field in _REQUIRED_ANCHOR_FIELDS:
        _require(raw, field, where)

    scope = raw["scope"]
    if scope not in KNOWN_SCOPES:
        raise AnchorRegistryError(
            f"{where}: 알 수 없는 scope {scope!r} — 허용: {sorted(KNOWN_SCOPES)}"
        )

    codes = raw["codes"]
    if not isinstance(codes, list) or not codes:
        raise AnchorRegistryError(f"{where}: codes가 비어 있거나 리스트가 아니다")
    if any(not isinstance(c, str) or not c.strip() for c in codes):
        raise AnchorRegistryError(f"{where}: codes에 빈 문자열·비문자열이 있다")
    if len(set(codes)) != len(codes):
        raise AnchorRegistryError(f"{where}: codes에 중복이 있다 — {codes}")

    excluded = raw["excluded"] or {}
    if not isinstance(excluded, dict):
        raise AnchorRegistryError(f"{where}: excluded가 매핑이 아니다")
    if any(not isinstance(v, str) or not v.strip() for v in excluded.values()):
        # 사유 없는 제외는 "왜 뺐는가"를 복원 불가로 만든다 — 빈 사유를 통과시키지 않는다.
        raise AnchorRegistryError(f"{where}: excluded 항목에 제외 사유가 비어 있다")
    overlap = set(excluded) & set(codes)
    if overlap:
        raise AnchorRegistryError(f"{where}: 같은 코드가 포함·제외 양쪽에 있다 — {sorted(overlap)}")

    return Anchor(
        id=str(raw["id"]),
        title=str(raw["title"]),
        scope=str(scope),
        school_level=str(raw["school_level"]),
        grade_hint=(str(raw["grade_hint"]) if raw.get("grade_hint") is not None else None),
        role=str(raw["role"]),
        codes=tuple(str(c) for c in codes),
        excluded=MappingProxyType({str(k): str(v) for k, v in excluded.items()}),
        note=str(raw["note"]),
        baseline=bool(raw["baseline"]),
        depth=bool(raw["depth"]),
        production_cu=(int(raw["production_cu"]) if raw.get("production_cu") is not None else None),
        review_cu=(int(raw["review_cu"]) if raw.get("review_cu") is not None else None),
    )


def load_anchor_registry(path: Path | None = None) -> AnchorRegistry:
    """레지스트리 YAML → `AnchorRegistry`. 실패는 전부 `AnchorRegistryError`(침묵 0건 금지)."""
    source = path or default_registry_path()
    try:
        raw_text = source.read_text(encoding="utf-8")
    except OSError as exc:
        raise AnchorRegistryError(
            f"앵커 레지스트리를 읽지 못했다 ({source}): {type(exc).__name__}: {exc}"
        ) from exc
    try:
        doc = yaml.safe_load(raw_text)
    except yaml.YAMLError as exc:
        raise AnchorRegistryError(
            f"앵커 레지스트리 YAML 파싱 실패 ({source}): {type(exc).__name__}: {exc}"
        ) from exc
    if not isinstance(doc, dict):
        raise AnchorRegistryError(f"{source}: 최상위가 매핑이 아니다 (실제 {type(doc).__name__})")

    raw_anchors = _require(doc, "anchors", str(source))
    if not isinstance(raw_anchors, list) or not raw_anchors:
        raise AnchorRegistryError(f"{source}: anchors가 비어 있거나 리스트가 아니다")

    anchors = tuple(_parse_anchor(a, i, source) for i, a in enumerate(raw_anchors))
    ids = [a.id for a in anchors]
    if len(set(ids)) != len(ids):
        raise AnchorRegistryError(f"{source}: 앵커 id 중복 — {ids}")
    # 한 코드가 두 앵커에 걸리면 자산 집계가 이중 계상된다(조인 축의 대전제).
    seen: dict[str, str] = {}
    for anchor in anchors:
        for code in anchor.codes:
            if code in seen:
                raise AnchorRegistryError(
                    f"{source}: 코드 {code}가 {seen[code]}·{anchor.id} 두 앵커에 중복 귀속"
                )
            seen[code] = anchor.id

    raw_sources = _require(doc, "standards_sources", str(source))
    if not isinstance(raw_sources, list) or not raw_sources:
        raise AnchorRegistryError(f"{source}: standards_sources가 비어 있다")
    standards_sources: list[tuple[str, str | None]] = []
    for i, entry in enumerate(raw_sources):
        if not isinstance(entry, dict) or "path" not in entry:
            raise AnchorRegistryError(f"{source}: standards_sources[{i}]에 path가 없다")
        revision = entry.get("curriculum_revision")
        standards_sources.append((str(entry["path"]), str(revision) if revision else None))

    return AnchorRegistry(
        anchors=anchors,
        frozen_at=str(_require(doc, "frozen_at", str(source))),
        frozen_by_gate=str(_require(doc, "frozen_by_gate", str(source))),
        design_doc=str(_require(doc, "design_doc", str(source))),
        mapping_axis=str(_require(doc, "mapping_axis", str(source))),
        standards_sources=tuple(standards_sources),
        source_path=source,
    )


def load_standards_codes(registry: AnchorRegistry, repo_root: Path | None = None) -> frozenset[str]:
    """레지스트리가 지목한 성취기준 코퍼스에서 코드 집합을 읽는다.

    `curriculum_revision` 필터가 있으면 그 개정분만 인정한다 — 학교급 코퍼스 895행은
    2022·2015 개정 혼재라, 필터 없이 세면 폐지된 2015 코드가 앵커를 살려 준다(드리프트 은폐).
    """
    root = repo_root or _REPO_ROOT
    codes: set[str] = set()
    for rel_path, revision in registry.standards_sources:
        target = root / rel_path
        try:
            payload = json.loads(target.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise AnchorRegistryError(
                f"성취기준 코퍼스를 읽지 못했다 ({target}): {type(exc).__name__}: {exc}"
            ) from exc
        rows = payload.get("standards") if isinstance(payload, dict) else None
        if not isinstance(rows, list):
            raise AnchorRegistryError(f"{target}: 최상위 'standards' 배열이 없다")
        for row in rows:
            if not isinstance(row, dict) or "code" not in row:
                continue
            if revision is not None and row.get("curriculum_revision") != revision:
                continue
            codes.add(str(row["code"]))
    if not codes:
        # 0건은 "위반 없음"이 아니라 "읽기 실패"다 — 통과시키면 게이트가 상시 green이 된다.
        raise AnchorRegistryError(
            "성취기준 코드 0건 — 코퍼스 경로·개정 필터를 확인하라(게이트 무력화 방지)"
        )
    return frozenset(codes)


def verify_codes_exist(registry: AnchorRegistry, known_codes: frozenset[str]) -> tuple[str, ...]:
    """앵커 코드가 성취기준 데이터에 실재하는지 검사. 반환 = 위반 목록(빈 튜플이면 통과)."""
    violations: list[str] = []
    for anchor in registry.anchors:
        for code in anchor.codes:
            if code not in known_codes:
                violations.append(
                    f"{anchor.id}({anchor.title}): 동결 코드 {code}가 성취기준 데이터에 없다"
                )
    return tuple(violations)


# ──────────────────────────────────────────────────────────────────────────
# CLI — `python -m whymath_backend.l1.standards.anchor_registry`
# 판정은 exit 0/1(CLAUDE.md "게이트 판정은 항상 CLI exit 0/1" — 인상 판정 금지).
# ──────────────────────────────────────────────────────────────────────────
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="EOS 앵커 레지스트리 무결성 점검 — 코드 실재 검사(exit 0=통과·1=위반)."
    )
    parser.add_argument("--registry", type=Path, default=None, help="레지스트리 YAML 경로")
    parser.add_argument("--json", action="store_true", help="요약을 JSON으로 출력")
    args = parser.parse_args(argv)

    try:
        registry = load_anchor_registry(args.registry)
        known = load_standards_codes(registry)
    except AnchorRegistryError as exc:
        # 적재 실패를 exit 0으로 가리지 않는다 — 측정 실패는 측정 실패로 보여야 한다.
        print(f"[적재 실패] {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    violations = verify_codes_exist(registry, known)
    december = registry.in_scope(SCOPE_DECEMBER_2026)
    summary = {
        "registry": str(registry.source_path),
        "frozen_at": registry.frozen_at,
        "frozen_by_gate": registry.frozen_by_gate,
        "anchors_total": len(registry.anchors),
        "anchors_december_2026": len(december),
        "codes_total": len(registry.all_codes()),
        "standards_codes_indexed": len(known),
        "violations": list(violations),
    }
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(f"앵커 레지스트리: {summary['registry']} (동결 {registry.frozen_at})")
        print(
            f"  앵커 {summary['anchors_total']}건 "
            f"(12월 대상 {summary['anchors_december_2026']}건) · "
            f"코드 {summary['codes_total']}건 · "
            f"성취기준 색인 {summary['standards_codes_indexed']}건"
        )
        for v in violations:
            print(f"  ✗ {v}")
        print("판정: " + ("통과" if not violations else f"위반 {len(violations)}건"))
    return 1 if violations else 0


if __name__ == "__main__":  # pragma: no cover - CLI 진입점
    raise SystemExit(main())
