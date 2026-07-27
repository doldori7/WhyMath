"""그래프 분석 코어 — prerequisite DAG 허브·영향도 + blocking 오개념 전파(순수 함수·I/O 분리).

지표 정의:
  - **in_degree / out_degree** — 선수엣지(from=선수 → to=후속) 기준 차수.
  - **downstream_count** — 그 원자를 선수로 (직·간접) 요구하는 하류 원자 수(자기 제외·BFS).
    "이 원자가 무너지면 몇 개가 막히는가" = 저작·검수 우선순위 신호.
  - **오개념 전파** — `severity=blocking` 오개념의 대응 개념(`concept_src_id`→
    `concept_graph_v1.source_id`→`concept_id`)을 crosswalk로 원자 집합에 얹고, 그 원자들의
    하류 도달 합집합 크기를 센다(원자 집합 전체 — primary만 아님·`transfer.py` 전파 규칙 동형).

해석 실패(원천 미존재·crosswalk 미매핑)는 **skip + 보고**한다(침묵 실패 금지). 사이클은
DAG 불변식 위반이라 error로 보고한다(BFS 자체는 visited set으로 안전 종료).
"""

from __future__ import annotations

import json
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path

_BLOCKING = "blocking"
_ATOM_LEVEL = "세부개념"


@dataclass(slots=True)
class NodeMetrics:
    """원자 1개의 그래프 지표(허브 랭킹 행)."""

    code: str
    name: str
    in_degree: int
    out_degree: int
    downstream_count: int


@dataclass(slots=True)
class MisconceptionImpact:
    """blocking 오개념 1건의 전파 영향(랭킹 행)."""

    mis_id: str
    statement: str
    concept_id: str
    atom_count: int
    blocked_downstream_count: int


@dataclass(slots=True)
class AnalyticsReport:
    """분석 산출물 — 허브 전량·전파 전량·해석 실패 목록·사이클 오류."""

    atom_count: int = 0
    edge_count: int = 0
    blocking_total: int = 0
    hubs: list[NodeMetrics] = field(default_factory=list)
    impacts: list[MisconceptionImpact] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    cycle: list[str] | None = None

    @property
    def success(self) -> bool:
        """DAG 불변식(사이클 0)이 유지되면 성공 — skip은 성공을 막지 않는다(보고 대상)."""
        return self.cycle is None

    def report_text(self, top_n: int = 20) -> str:
        """사람용 요약 — 허브 top-N·전파 top-N·skip·사이클."""
        lines = [
            "[그래프 분석 리포트 — 빌드타임 오프라인·저작/검수 우선순위용]",
            f"  원자 {self.atom_count:,} · 선수엣지 {self.edge_count:,}"
            f" · blocking 오개념 {self.blocking_total:,}",
        ]
        if self.cycle is not None:
            lines.append(f"  [ERROR] prerequisite 사이클: {' → '.join(self.cycle)}")
        lines.append(f"  허브 top-{top_n} (하류 도달 수 기준):")
        for m in self.hubs[:top_n]:
            lines.append(
                f"    {m.code} {m.name} — 하류 {m.downstream_count:,}"
                f" (in {m.in_degree}/out {m.out_degree})"
            )
        lines.append(f"  blocking 오개념 전파 top-{top_n} (막히는 하류 원자 수 기준):")
        for imp in self.impacts[:top_n]:
            lines.append(
                f"    {imp.mis_id} [{imp.concept_id}] — 하류 {imp.blocked_downstream_count:,}"
                f" (원자 {imp.atom_count}개) {imp.statement[:40]}"
            )
        if self.skipped:
            lines.append(f"  해석 실패(skip) {len(self.skipped)}건:")
            for msg in self.skipped[:10]:
                lines.append(f"    - {msg}")
            if len(self.skipped) > 10:
                lines.append(f"    … 외 {len(self.skipped) - 10}건")
        return "\n".join(lines)


# ──────────────────────────────────────────────────────────────────────────
# 적재(얇은 I/O) — 코퍼스 JSON → 분석 입력
# ──────────────────────────────────────────────────────────────────────────
def load_atom_dag(graph_path: Path) -> tuple[dict[str, str], list[tuple[str, str]]]:
    """atom_graph_v1 graph.json → (원자 code→name, prerequisite 엣지 [from=선수, to=후속]).

    원자(세부개념)만 노드 우주로 삼는다(단원/소단원 제외 — 엣지도 원자 간). relation이
    prerequisite가 아닌 엣지는 무시한다(현 코퍼스는 전량 prerequisite — 방어).
    """
    payload = json.loads(graph_path.read_text(encoding="utf-8"))
    names: dict[str, str] = {}
    for record in payload.get("concepts", []):
        if record.get("level") != _ATOM_LEVEL:
            continue
        code = str(record.get("code", "")).strip()
        if code:
            names[code] = str(record.get("name", "") or "").strip()
    edges: list[tuple[str, str]] = []
    for edge in payload.get("edges", []):
        if edge.get("relation") != "prerequisite":
            continue
        edges.append((str(edge["from_code"]), str(edge["to_code"])))
    return names, edges


def load_blocking_misconceptions(path: Path) -> tuple[list[dict[str, str]], int]:
    """misconceptions_v1 → (blocking 행 [mis_id·concept_src_id·statement], blocking 총수)."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows: list[dict[str, str]] = []
    for record in payload.get("misconceptions", []):
        if record.get("severity") != _BLOCKING:
            continue
        rows.append(
            {
                "mis_id": str(record.get("mis_id", "")),
                "concept_src_id": str(record.get("concept_src_id", "") or ""),
                "statement": str(record.get("canonical_statement", "") or ""),
            }
        )
    return rows, len(rows)


def load_source_id_map(concept_graph_path: Path) -> dict[str, str]:
    """concept_graph_v1 graph.json → source_id("N1") → concept_id 맵(crosswalk 조인 다리)."""
    payload = json.loads(concept_graph_path.read_text(encoding="utf-8"))
    out: dict[str, str] = {}
    for record in payload.get("concepts", []):
        src = str(record.get("source_id", "") or "").strip()
        cid = str(record.get("concept_id", "") or "").strip()
        if src and cid:
            out[src] = cid
    return out


def load_crosswalk_atoms(path: Path) -> dict[str, list[str]]:
    """crosswalk.jsonl → concept_id → atom_codes(전체 — primary만 아님·unmapped 빈 리스트 제외)."""
    out: dict[str, list[str]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        record = json.loads(line)
        atom_codes = [str(c) for c in record.get("atom_codes", []) or []]
        if atom_codes:
            out[str(record["concept_id"])] = atom_codes
    return out


# ──────────────────────────────────────────────────────────────────────────
# 계산(순수) — 차수·도달·전파
# ──────────────────────────────────────────────────────────────────────────
def find_prerequisite_cycle(edges: list[tuple[str, str]]) -> list[str] | None:
    """사이클 1건 탐지(백/화이트/그레이 비재귀 DFS — `atom_graph/validate.py` 알고리즘 미러).

    깊은 체인 대비 명시 스택. 반환은 사이클 경로(닫힘 노드 반복) 또는 None.
    """
    adj: dict[str, list[str]] = {}
    for from_code, to_code in edges:
        adj.setdefault(from_code, []).append(to_code)

    white, gray, black = 0, 1, 2
    color: dict[str, int] = {}
    for start in list(adj):
        if color.get(start, white) != white:
            continue
        stack: list[tuple[str, int]] = [(start, 0)]
        path: list[str] = [start]
        color[start] = gray
        while stack:
            node, child_idx = stack[-1]
            children = adj.get(node, [])
            if child_idx < len(children):
                stack[-1] = (node, child_idx + 1)
                nxt = children[child_idx]
                state = color.get(nxt, white)
                if state == gray:
                    return path[path.index(nxt) :] + [nxt]
                if state == white:
                    color[nxt] = gray
                    stack.append((nxt, 0))
                    path.append(nxt)
            else:
                color[node] = black
                stack.pop()
                path.pop()
    return None


def _downstream(adj: dict[str, list[str]], seeds: list[str]) -> set[str]:
    """seed 집합에서 전방(선수→후속) BFS로 도달한 하류 원자 집합(seed 자신 제외)."""
    visited: set[str] = set(seeds)
    queue: deque[str] = deque(seeds)
    reached: set[str] = set()
    while queue:
        node = queue.popleft()
        for nxt in adj.get(node, []):
            if nxt not in visited:
                visited.add(nxt)
                reached.add(nxt)
                queue.append(nxt)
    return reached


def compute_node_metrics(names: dict[str, str], edges: list[tuple[str, str]]) -> list[NodeMetrics]:
    """전 원자 차수·하류 도달 수 — downstream_count desc → out_degree desc → code 정렬."""
    adj: dict[str, list[str]] = {}
    in_deg: dict[str, int] = {}
    out_deg: dict[str, int] = {}
    for from_code, to_code in edges:
        adj.setdefault(from_code, []).append(to_code)
        out_deg[from_code] = out_deg.get(from_code, 0) + 1
        in_deg[to_code] = in_deg.get(to_code, 0) + 1

    metrics = [
        NodeMetrics(
            code=code,
            name=name,
            in_degree=in_deg.get(code, 0),
            out_degree=out_deg.get(code, 0),
            downstream_count=len(_downstream(adj, [code])),
        )
        for code, name in names.items()
    ]
    metrics.sort(key=lambda m: (-m.downstream_count, -m.out_degree, m.code))
    return metrics


def compute_misconception_impacts(
    *,
    blocking_rows: list[dict[str, str]],
    source_id_map: dict[str, str],
    crosswalk: dict[str, list[str]],
    names: dict[str, str],
    edges: list[tuple[str, str]],
) -> tuple[list[MisconceptionImpact], list[str]]:
    """blocking 오개념별 하류 전파 크기 — 해석 실패는 skip 목록으로 보고(침묵 금지).

    체인: concept_src_id → concept_id(source_id_map) → atom_codes(crosswalk·전체) →
    하류 도달 합집합 크기. 원자 우주 밖 atom_code는 그 오개념의 skip 사유로 보고한다.
    """
    adj: dict[str, list[str]] = {}
    for from_code, to_code in edges:
        adj.setdefault(from_code, []).append(to_code)

    impacts: list[MisconceptionImpact] = []
    skipped: list[str] = []
    for row in blocking_rows:
        mis_id, src_id = row["mis_id"], row["concept_src_id"]
        concept_id = source_id_map.get(src_id)
        if concept_id is None:
            skipped.append(f"{mis_id}: concept_src_id '{src_id}' 미해석(개념 그래프에 없음)")
            continue
        atom_codes = crosswalk.get(concept_id)
        if not atom_codes:
            skipped.append(f"{mis_id}: concept_id '{concept_id}' crosswalk 미매핑")
            continue
        seeds = [c for c in atom_codes if c in names]
        if not seeds:
            skipped.append(f"{mis_id}: atom_codes 전부 원자 우주 밖 — {atom_codes[:3]}…")
            continue
        impacts.append(
            MisconceptionImpact(
                mis_id=mis_id,
                statement=row["statement"],
                concept_id=concept_id,
                atom_count=len(seeds),
                blocked_downstream_count=len(_downstream(adj, seeds)),
            )
        )
    impacts.sort(key=lambda i: (-i.blocked_downstream_count, i.mis_id))
    return impacts, skipped


def build_report(
    *,
    atom_graph: Path,
    concept_graph: Path,
    misconceptions: Path,
    crosswalk: Path,
) -> AnalyticsReport:
    """코퍼스 4파일 → 분석 리포트(적재 + 계산 조립)."""
    names, edges = load_atom_dag(atom_graph)
    blocking_rows, blocking_total = load_blocking_misconceptions(misconceptions)
    source_id_map = load_source_id_map(concept_graph)
    crosswalk_atoms = load_crosswalk_atoms(crosswalk)

    impacts, skipped = compute_misconception_impacts(
        blocking_rows=blocking_rows,
        source_id_map=source_id_map,
        crosswalk=crosswalk_atoms,
        names=names,
        edges=edges,
    )
    return AnalyticsReport(
        atom_count=len(names),
        edge_count=len(edges),
        blocking_total=blocking_total,
        hubs=compute_node_metrics(names, edges),
        impacts=impacts,
        skipped=skipped,
        cycle=find_prerequisite_cycle(edges),
    )


__all__ = [
    "AnalyticsReport",
    "MisconceptionImpact",
    "NodeMetrics",
    "build_report",
    "compute_misconception_impacts",
    "compute_node_metrics",
    "find_prerequisite_cycle",
    "load_atom_dag",
    "load_blocking_misconceptions",
    "load_crosswalk_atoms",
    "load_source_id_map",
]
