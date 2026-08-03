"""시각화 도달률 관측 리포트 CLI — 빌드타임 결정론 관측(DB 0·LLM 0·HTTP 0). VIZ-01 acceptance⑤.

설계 정본: `docs/architecture/visualization_module_gap_review.md` §3 D1·D2. D1이 해소되기 전
(`concept_visual_style`·`concept_visualization` 두 Overlay의 프로덕션 적재 경로가 0건) 학생
경로(`/v1/scenes/weak-concept`)의 시각화 블록은 **런타임 기준 도달률 0%**였다 — 이 사실이
관측되지 않았던 것 자체가 D1의 핵심 문제였다. 이 모듈은 그 수치를 *영구히 눈에 보이게* 한다.

**게이트가 아니다**(`problem_bank_coverage`와 동일 원칙) — 도달률이 낮아도 exit 1을 내지 않는다.
**100% 도달은 목표가 아니다**(D2) — 추상 개념(대우증명·귀류법 등)은 리터럴 시각화를 *보류하는
것이 정답*이므로, 이 리포트의 목적은 수치를 최대화하는 것이 아니라 *관측 가능하게* 만드는 것이다.

산출 3축:
  1. **시각화 가능성 분류율** — `concept_visualization` 코퍼스가 원자 백본(런타임 개념 code
     공간)의 개념을 몇 % 분류했는가. **알려진 함정을 그대로 드러낸다**: 기존 7건 코퍼스
     (`concept_visualization_v1/visualizability.json`)는 *레거시 437 개념그래프 code*로
     태깅돼 있어 원자 백본(`atom_graph_v1`) code 공간과 **전혀 겹치지 않는다**(VIZ-01 D1 실측) —
     이 불일치를 `visualization_orphaned_codes`로 정직하게 드러낸다(조용히 매치 실패로 죽이지
     않는다).
  2. **시각화 요소 도달률** — 개념 카탈로그(원자 백본 세부개념) 중 몇 %가 실제 프로덕션 게이트
     (`l4/scene_generation.py:279` = `l4/visualization_policy.is_visualizable` AND
     `recommended_visual_styles` 존재)를 통과해 시각화 요소를 받는가. LLM을 실제로 호출하지
     않고(비용·네트워크 0) 게이트 판정 함수를 그대로 재사용해 *결정론적으로* 근사한다 — 실제
     scene 생성과 유일한 차이는 spec 내용(LLM이 채움)이지, *시각화 요소를 붙일지 말지*는 이
     리포트가 그대로 재현한다(새 판정 로직 추가 0 — 기존 `is_visualizable` 재사용).
  3. **미분류 개념 목록** — 스타일·분류 둘 다 없는(완전 미관측) 개념 목록(D2 가시성 요구사항).

VIZ-04 추가 축 — **양식 정합 도달률**: 게이트를 통과한 개념 중 몇 %가 권장 양식에 *실제 렌더
좌석*이 있는가(`l4/visualization_policy.has_render_seat` 재사용 — 새 판정 로직 0). 게이트 통과만으론
"시각화 요소가 붙는다"만 알 수 있고 "그 요소가 개념과 맞는 그림인가"는 몰랐다 — 좌석 0인 양식(예:
입체도형)이 게이트를 통과하면 LLM이 4종 중 하나를 억지로 골라 개념과 무관한 그림을 렌더할 위험이
있다(`visualization_module_gap_review.md` §7.1 G1). 100% 정합도 목표가 아니다(미좌석은 보류가
정답) — 격차를 눈에 계속 보이게 하는 것이 목표.

사용:
    python -m whymath_backend.harness.visualization_reach_report
    python -m whymath_backend.harness.visualization_reach_report --json out/viz_reach.json
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from whymath_backend.l4.visualization_policy import has_render_seat, is_visualizable
from whymath_backend.schema.enums import Visualizability, VisualizationStyle

__all__ = [
    "CatalogEntry",
    "ReachReport",
    "StyleCorpus",
    "VisualizationCorpus",
    "build_report",
    "load_catalog",
    "load_style_corpus",
    "load_visualization_corpus",
    "main",
    "render_report",
    "report_to_json",
]

_EXIT_OK = 0
_EXIT_INPUT_ERROR = 2

# harness→whymath_backend→backend→src→repo 루트(problem_bank_coverage와 동일 관례).
_REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_CATALOG_PATH = _REPO_ROOT / "data" / "corpus" / "atom_graph_v1" / "graph.json"
DEFAULT_STYLE_CORPUS_PATH = (
    _REPO_ROOT / "data" / "corpus" / "concept_visual_style_v1" / "concept_visual_style.json"
)
DEFAULT_VISUALIZATION_CORPUS_PATH = (
    _REPO_ROOT / "data" / "corpus" / "concept_visualization_v1" / "visualizability.json"
)

# 카탈로그 분모 — 진단·장면 생성의 실제 대상은 원자 백본의 *세부개념*(단원·소단원은 진단 대상이
# 아니다 — `l2/concept_diagnosis`가 채점 이력이 붙는 leaf 개념만 다룬다).
_CATALOG_LEVEL = "세부개념"


@dataclass(slots=True, frozen=True)
class CatalogEntry:
    """개념 카탈로그 1건(원자 백본 세부개념) — 리포트 집계에 필요한 최소 투영."""

    code: str
    name: str


def load_catalog(payload: object) -> tuple[CatalogEntry, ...]:
    """원자 백본 `graph.json`(dict) → 세부개념 레벨 카탈로그(code 리터럴 그대로·enum 미결합).

    Raises:
        ValueError: 최상위가 dict가 아니거나 `concepts` 배열 부재(분모를 모른 채 리포트 불가).
    """
    if not isinstance(payload, dict):
        raise ValueError(
            f"atom_graph_v1 graph.json 최상위가 object가 아님(type={type(payload).__name__})"
        )
    raw = payload.get("concepts")
    if not isinstance(raw, list):
        raise ValueError("atom_graph_v1 graph.json에 'concepts' 배열이 없음")
    out: list[CatalogEntry] = []
    for idx, item in enumerate(raw):
        if not isinstance(item, dict):
            raise ValueError(f"concepts[{idx}]가 object가 아님(type={type(item).__name__})")
        if item.get("level") != _CATALOG_LEVEL:
            continue
        code = item.get("code")
        if not isinstance(code, str) or not code:
            raise ValueError(f"concepts[{idx}]에 code 문자열이 없음")
        out.append(CatalogEntry(code=code, name=str(item.get("name") or "")))
    return tuple(out)


@dataclass(slots=True, frozen=True)
class StyleCorpus:
    """`concept_visual_style.json` 투영 — code → 원시 양식 문자열 배열(어휘 검증 없이 그대로)."""

    entries: dict[str, tuple[str, ...]]


def load_style_corpus(payload: object) -> StyleCorpus:
    """권장 시각화 양식 코퍼스(dict) → code 키 매핑. 어휘 밖 값도 원문 그대로 보존(정직 회계).

    Raises:
        ValueError: 최상위가 dict가 아니거나 `entries` 배열 부재.
    """
    if not isinstance(payload, dict):
        raise ValueError(f"코퍼스 최상위가 object가 아님(type={type(payload).__name__})")
    raw = payload.get("entries")
    if not isinstance(raw, list):
        raise ValueError("코퍼스에 'entries' 배열이 없음")
    out: dict[str, tuple[str, ...]] = {}
    for idx, item in enumerate(raw):
        if not isinstance(item, dict):
            raise ValueError(f"entries[{idx}]가 object가 아님(type={type(item).__name__})")
        code = item.get("code")
        if not isinstance(code, str) or not code:
            raise ValueError(f"entries[{idx}]에 code 문자열이 없음")
        styles = item.get("recommended_styles")
        if not isinstance(styles, list):
            raise ValueError(f"entries[{idx}]({code})에 recommended_styles 배열이 없음")
        out[code] = tuple(str(s) for s in styles)
    return StyleCorpus(entries=out)


@dataclass(slots=True, frozen=True)
class VisualizationCorpus:
    """`visualizability.json` 투영 — code → 원시 4분류 문자열(어휘 검증 없이 그대로)."""

    entries: dict[str, str]


def load_visualization_corpus(payload: object) -> VisualizationCorpus:
    """시각화 가능성 코퍼스(dict) → code 키 매핑.

    Raises:
        ValueError: 최상위가 dict가 아니거나 `entries` 배열 부재.
    """
    if not isinstance(payload, dict):
        raise ValueError(f"코퍼스 최상위가 object가 아님(type={type(payload).__name__})")
    raw = payload.get("entries")
    if not isinstance(raw, list):
        raise ValueError("코퍼스에 'entries' 배열이 없음")
    out: dict[str, str] = {}
    for idx, item in enumerate(raw):
        if not isinstance(item, dict):
            raise ValueError(f"entries[{idx}]가 object가 아님(type={type(item).__name__})")
        code = item.get("code")
        if not isinstance(code, str) or not code:
            raise ValueError(f"entries[{idx}]에 code 문자열이 없음")
        value = item.get("visualizability")
        if not isinstance(value, str) or not value:
            raise ValueError(f"entries[{idx}]({code})에 visualizability 문자열이 없음")
        out[code] = value
    return VisualizationCorpus(entries=out)


# ──────────────────────────────────────────────────────────────────────────
# 집계 — 도달률 리포트(순수 코어)
# ──────────────────────────────────────────────────────────────────────────
@dataclass(slots=True, frozen=True)
class ReachReport:
    """도달률 관측 결과 전량(불변·렌더/직렬화의 단일 입력)."""

    catalog_total: int
    # ① 스타일 축
    style_corpus_entries: int
    style_matched_count: int
    style_orphaned_codes: tuple[str, ...]  # 코퍼스엔 있으나 카탈로그 code 공간과 불일치
    style_untagged_codes: tuple[str, ...]  # 카탈로그엔 있으나 스타일 미태깅
    style_distribution: dict[str, int]
    # ② 시각화 가능성(분류) 축
    visualization_corpus_entries: int
    visualization_matched_count: int
    visualization_orphaned_codes: tuple[str, ...]
    visualization_invalid_values: dict[str, int]  # 4분류 통제 어휘 밖 원시값 → 건수
    visualization_distribution: dict[str, int]
    # ③ 게이트 통과(시각화 요소 도달) 축 — is_visualizable 재사용(새 판정 로직 0)
    gate_pass_count: int
    gate_withheld_abstain_count: int  # 스타일 있으나 '추상' 분류로 보류된 개념 수
    # ④ 완전 미관측(스타일·분류 둘 다 없음)
    unclassified_both_codes: tuple[str, ...]
    # ⑤ 양식 정합 도달률(VIZ-04) — 게이트 통과 AND 권장 양식 중 렌더 좌석 보유
    # (has_render_seat 재사용)
    seat_pass_count: int

    @property
    def style_tagged_rate(self) -> float | None:
        if self.catalog_total == 0:
            return None
        return self.style_matched_count / self.catalog_total

    @property
    def visualization_tagged_rate(self) -> float | None:
        if self.catalog_total == 0:
            return None
        return self.visualization_matched_count / self.catalog_total

    @property
    def gate_pass_rate(self) -> float | None:
        if self.catalog_total == 0:
            return None
        return self.gate_pass_count / self.catalog_total

    @property
    def seat_pass_rate(self) -> float | None:
        """카탈로그 총계 대비 양식 정합 도달 비율(분모=catalog_total — gate_pass_rate와 같은 분모라
        "게이트 통과율 대비 정합률"을 별도 계산 없이 두 % 값을 나란히 비교할 수 있다)."""
        if self.catalog_total == 0:
            return None
        return self.seat_pass_count / self.catalog_total


def build_report(
    catalog: tuple[CatalogEntry, ...],
    style_corpus: StyleCorpus,
    visualization_corpus: VisualizationCorpus,
) -> ReachReport:
    """카탈로그 + 두 코퍼스 → `ReachReport`(순수·부작용 0)."""
    catalog_codes = {c.code for c in catalog}

    style_matched = {c: v for c, v in style_corpus.entries.items() if c in catalog_codes}
    style_orphaned = tuple(sorted(c for c in style_corpus.entries if c not in catalog_codes))
    style_untagged = tuple(sorted(c for c in catalog_codes if c not in style_matched))
    style_dist: Counter[str] = Counter()
    for styles in style_matched.values():
        for s in styles:
            style_dist[s] += 1

    viz_valid: dict[str, Visualizability] = {}
    viz_invalid: Counter[str] = Counter()
    for code, raw in visualization_corpus.entries.items():
        try:
            viz_valid[code] = Visualizability(raw)
        except ValueError:
            # 4분류 통제 어휘 밖(오염) — 조용히 버리지 않고 카운트한다(정직 회계).
            viz_invalid[raw] += 1

    viz_matched = {c: v for c, v in viz_valid.items() if c in catalog_codes}
    viz_orphaned = tuple(sorted(c for c in visualization_corpus.entries if c not in catalog_codes))
    viz_dist: Counter[str] = Counter(v.value for v in viz_matched.values())

    gate_pass = 0
    gate_withheld_abstain = 0
    seat_pass = 0
    for code in catalog_codes:
        styles = style_matched.get(code, ())
        classification = viz_matched.get(code)
        gate_ok = bool(styles) and is_visualizable(classification)
        if gate_ok:
            gate_pass += 1
        if styles and classification == Visualizability.추상:
            gate_withheld_abstain += 1
        if gate_ok:
            # 원시 문자열 중 통제 어휘(VisualizationStyle) 안에 드는 것만 좌석 판정에 넣는다
            # (오염값은 style_dist처럼 조용히 세지도 않지만, 좌석 판정에서도 조용히 통과시키지
            # 않는다 — has_render_seat가 유효 enum만 받는 계약이라 여기서 걸러야 한다).
            valid_styles: list[VisualizationStyle] = []
            for raw in styles:
                try:
                    valid_styles.append(VisualizationStyle(raw))
                except ValueError:
                    continue
            if has_render_seat(valid_styles):
                seat_pass += 1

    unclassified_both = tuple(
        sorted(c for c in catalog_codes if c not in style_matched and c not in viz_matched)
    )

    return ReachReport(
        catalog_total=len(catalog_codes),
        style_corpus_entries=len(style_corpus.entries),
        style_matched_count=len(style_matched),
        style_orphaned_codes=style_orphaned,
        style_untagged_codes=style_untagged,
        style_distribution=dict(style_dist),
        visualization_corpus_entries=len(visualization_corpus.entries),
        visualization_matched_count=len(viz_matched),
        visualization_orphaned_codes=viz_orphaned,
        visualization_invalid_values=dict(viz_invalid),
        visualization_distribution=dict(viz_dist),
        gate_pass_count=gate_pass,
        gate_withheld_abstain_count=gate_withheld_abstain,
        unclassified_both_codes=unclassified_both,
        seat_pass_count=seat_pass,
    )


# ──────────────────────────────────────────────────────────────────────────
# 렌더 — 사람이 읽는 마크다운 + 기계가 읽는 JSON
# ──────────────────────────────────────────────────────────────────────────
def _pct(numerator: int, denominator: int) -> str:
    if denominator == 0:
        return "데이터없음"
    return f"{numerator / denominator * 100:.2f}%"


def render_report(report: ReachReport, *, max_listed: int = 40) -> str:
    """도달률 관측 결과를 마크다운으로 렌더(순수·입력 외 계산 없음).

    목록류(0커버·미분류 등)는 `max_listed`개까지만 본문에 싣고 잘림 사실을 문장으로 남긴다
    (`problem_bank_coverage.render_report` 관례 답습 — 조용한 절단 금지).
    """
    lines: list[str] = [
        "# 시각화 도달률 관측 리포트 (VIZ-01 D1·D2)",
        "",
        "> 관측 리포트다 — **exit 게이트가 아니다**(도달률 임계로 실패시키지 않는다).",
        "> 100% 도달은 목표가 아니다(D2) — 추상 개념은 리터럴 시각화를 보류하는 것이 정답이다.",
        "",
        "## 0. 카탈로그",
        "",
        f"- 원자 백본 세부개념(진단·장면 생성 대상) 총계: **{report.catalog_total}**",
        "",
        "## 1. 시각화 가능성 분류율 (concept_visualization)",
        "",
        f"- 코퍼스 원시 항목 수: **{report.visualization_corpus_entries}**",
        f"- 카탈로그와 매치된 항목: **{report.visualization_matched_count}** "
        f"({_pct(report.visualization_matched_count, report.catalog_total)})",
        f"- 카탈로그 code 공간과 불일치(orphan — 코퍼스엔 있으나 원자 백본에 없음): "
        f"**{len(report.visualization_orphaned_codes)}**",
    ]
    if report.visualization_orphaned_codes:
        lines.append(
            "  - " + " ".join(f"`{c}`" for c in report.visualization_orphaned_codes[:max_listed])
        )
        remainder = len(report.visualization_orphaned_codes) - max_listed
        if remainder > 0:
            lines.append(f"  - …외 **{remainder}**건(전량은 `--json` 산출물).")
        lines.append(
            "  - **알려진 원인**(VIZ-01 D1 실측): 기존 7건 코퍼스는 *레거시 437 개념그래프* "
            "code로 태깅돼 원자 백본(`atom_graph_v1`) 런타임 code 공간과 키 공간이 다르다 — "
            "재작성은 이 태스크 범위 밖(별건)."
        )
    if report.visualization_invalid_values:
        lines += ["", "- 4분류 통제 어휘 밖 원시값(오염):"]
        for raw, count in sorted(report.visualization_invalid_values.items()):
            lines.append(f"  - `{raw}` — {count}건")
    if report.visualization_distribution:
        lines += ["", "| 분류 | 개념 수 |", "|---|---:|"]
        for value, count in sorted(report.visualization_distribution.items()):
            lines.append(f"| {value} | {count} |")

    lines += [
        "",
        "## 2. 권장 시각화 양식 태깅율 (concept_visual_style)",
        "",
        f"- 코퍼스 원시 항목 수: **{report.style_corpus_entries}**",
        f"- 카탈로그와 매치된 항목: **{report.style_matched_count}** "
        f"({_pct(report.style_matched_count, report.catalog_total)})",
        f"- 카탈로그 code 공간과 불일치(orphan): **{len(report.style_orphaned_codes)}**",
    ]
    if report.style_distribution:
        lines += ["", "| 양식 | 개념 수 |", "|---|---:|"]
        for style, count in sorted(
            report.style_distribution.items(), key=lambda kv: (-kv[1], kv[0])
        ):
            lines.append(f"| {style} | {count} |")

    lines += [
        "",
        "## 3. 시각화 요소 도달률 (프로덕션 게이트 재현 — l4/scene_generation.py:279)",
        "",
        f"- 게이트 통과(스타일 존재 AND is_visualizable): **{report.gate_pass_count}** "
        f"({_pct(report.gate_pass_count, report.catalog_total)})",
        f"- '추상' 분류로 명시적 보류(D2 보호 발동 관측): **{report.gate_withheld_abstain_count}**",
        "- 게이트 판정 함수는 `l4.visualization_policy.is_visualizable`를 그대로 재사용한다"
        "(신규 판정 로직 0 — 이 리포트가 실제 게이트와 어긋날 수 없다).",
    ]

    shown = report.unclassified_both_codes[:max_listed]
    remainder = len(report.unclassified_both_codes) - len(shown)
    lines += [
        "",
        "## 4. 완전 미관측 개념 (스타일·분류 둘 다 없음)",
        "",
        f"- 총 **{len(report.unclassified_both_codes)}**"
        f"({_pct(len(report.unclassified_both_codes), report.catalog_total)}) — "
        "100% 도달이 목표가 아니므로 이 수가 0이 아닌 것 자체는 실패가 아니다. "
        "저작 우선순위 입력으로 쓴다(문제은행 D4 리포트와 동형 용도).",
    ]
    if report.unclassified_both_codes:
        lines.append("- " + " ".join(f"`{c}`" for c in shown))
        if remainder > 0:
            lines.append(f"- …외 **{remainder}**건(전량은 `--json` 산출물).")

    lines += [
        "",
        "## 5. 양식 정합 도달률 (VIZ-04 — 게이트 통과 AND 권장 양식에 렌더 좌석 존재)",
        "",
        f"- 게이트 통과 중 양식 정합(좌석 보유): **{report.seat_pass_count}** "
        f"({_pct(report.seat_pass_count, report.catalog_total)})",
        f"- 게이트는 통과했으나 권장 양식 전건이 unseated(좌석 0): "
        f"**{report.gate_pass_count - report.seat_pass_count}**",
        "- 100% 정합은 목표가 아니다 — 미좌석 양식(예: 입체도형·수직선)은 시각화를 보류하는 것이 "
        "정답이다. 목표는 이 격차를 계속 눈에 보이게 하는 것이다.",
        "- 판정 함수는 `l4.visualization_policy.has_render_seat`를 그대로 재사용한다"
        "(신규 판정 로직 0).",
    ]
    lines.append("")
    return "\n".join(lines)


def report_to_json(report: ReachReport) -> dict[str, Any]:
    """리포트 → JSON 직렬화 가능 dict(키 정렬은 dump 시 `sort_keys=True`로 고정)."""
    return {
        "catalog_total": report.catalog_total,
        "visualization": {
            "corpus_entries": report.visualization_corpus_entries,
            "matched_count": report.visualization_matched_count,
            "tagged_rate": report.visualization_tagged_rate,
            "orphaned_codes": list(report.visualization_orphaned_codes),
            "invalid_values": report.visualization_invalid_values,
            "distribution": report.visualization_distribution,
        },
        "style": {
            "corpus_entries": report.style_corpus_entries,
            "matched_count": report.style_matched_count,
            "tagged_rate": report.style_tagged_rate,
            "orphaned_codes": list(report.style_orphaned_codes),
            "untagged_codes": list(report.style_untagged_codes),
            "distribution": report.style_distribution,
        },
        "gate": {
            "pass_count": report.gate_pass_count,
            "pass_rate": report.gate_pass_rate,
            "withheld_abstain_count": report.gate_withheld_abstain_count,
        },
        "unclassified_both_codes": list(report.unclassified_both_codes),
        "unclassified_both_count": len(report.unclassified_both_codes),
        "seat": {
            "pass_count": report.seat_pass_count,
            "pass_rate": report.seat_pass_rate,
        },
    }


def dump_json(report: ReachReport) -> str:
    return json.dumps(report_to_json(report), ensure_ascii=False, indent=2, sort_keys=True) + "\n"


# ──────────────────────────────────────────────────────────────────────────
# CLI (얇은 껍데기 — 경로 해석·입출력만, 집계는 위 순수 코어)
# ──────────────────────────────────────────────────────────────────────────
def main(argv: list[str] | None = None) -> int:
    """CLI 엔트리 — 도달률 관측 리포트를 stdout에 출력. **0=성공 / 2=입력 오류**(1 없음).

    도달률이 0%여도 exit 0이다(게이트 아님). exit 2는 카탈로그·코퍼스 자체를 읽을 수 없는
    입력 오류에만 쓴다.
    """
    parser = argparse.ArgumentParser(
        prog="python -m whymath_backend.harness.visualization_reach_report",
        description=(
            "시각화 도달률 관측 리포트(VIZ-01 D1·D2) — 분류율·양식 태깅율·게이트 통과율·"
            "미관측 개념 목록. 결정론·게이트 아님(exit 0/2)."
        ),
    )
    parser.add_argument(
        "--catalog", type=Path, default=DEFAULT_CATALOG_PATH, help="atom_graph_v1 graph.json 경로"
    )
    parser.add_argument(
        "--style-corpus",
        type=Path,
        default=DEFAULT_STYLE_CORPUS_PATH,
        help="concept_visual_style.json 경로",
    )
    parser.add_argument(
        "--visualization-corpus",
        type=Path,
        default=DEFAULT_VISUALIZATION_CORPUS_PATH,
        help="visualizability.json 경로",
    )
    parser.add_argument(
        "--max-listed", type=int, default=40, help="본문에 나열할 목록 최대 개수(기본 40)"
    )
    parser.add_argument(
        "--json", dest="json_path", type=Path, default=None, help="JSON 산출물 경로(선택)"
    )
    args = parser.parse_args(argv)

    try:
        catalog = load_catalog(json.loads(args.catalog.read_text(encoding="utf-8")))
    except Exception as exc:  # noqa: BLE001 — 입력 오류는 타입명과 함께 보고하고 exit 2
        print(f"입력 오류 — 카탈로그 적재 실패({type(exc).__name__}): {exc}", file=sys.stderr)
        return _EXIT_INPUT_ERROR
    try:
        style_corpus = load_style_corpus(json.loads(args.style_corpus.read_text(encoding="utf-8")))
    except Exception as exc:  # noqa: BLE001
        print(f"입력 오류 — 양식 코퍼스 적재 실패({type(exc).__name__}): {exc}", file=sys.stderr)
        return _EXIT_INPUT_ERROR
    try:
        visualization_corpus = load_visualization_corpus(
            json.loads(args.visualization_corpus.read_text(encoding="utf-8"))
        )
    except Exception as exc:  # noqa: BLE001
        print(f"입력 오류 — 분류 코퍼스 적재 실패({type(exc).__name__}): {exc}", file=sys.stderr)
        return _EXIT_INPUT_ERROR

    report = build_report(catalog, style_corpus, visualization_corpus)
    print(render_report(report, max_listed=args.max_listed))
    if args.json_path is not None:
        args.json_path.parent.mkdir(parents=True, exist_ok=True)
        args.json_path.write_text(dump_json(report), encoding="utf-8")
        print(f"JSON 산출물: {args.json_path}")
    return _EXIT_OK


if __name__ == "__main__":  # pragma: no cover — 엔트리포인트
    sys.exit(main())
