#!/usr/bin/env python3
"""S1-12 결과표 자동 기입기 — cost_report.json → 런북 결과표 마크다운 행(붙여넣기용).

목적(ROADMAP 병목 ② "AI는 측정 스크립트·대시보드를 선제 준비해 Kiki 수동 시간을 최소화"):
Kiki가 Phaiakes9에서 `python -m whymath_backend.ops.cost_report --days 1 --json cost_report.json`
으로 뽑은 JSON을 이 스크립트에 넣으면, `docs/strategy/live_cost_measurement_2026-07.md`의
결과표(비용·지연·판정선)에 그대로 붙여넣을 마크다운 행을 출력한다 — 수동 전기(transcription)
오류 0·빈칸 유지(측정 없는 셀은 '—'·날조 금지).

verify verdict 분포 표는 별도 소스(`GET /v1/me/harness-metrics`)라 이 스크립트 범위 밖 —
빈 행을 출력하고 소스만 안내한다(정직 스코프).

사용:
    python3 scripts/fill_live_cost_table.py cost_report.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# 런북 결과표의 티어 행 순서(고정) — cost_report의 cost_tier 값과 매핑.
_TIER_ROWS = (("local", "LOCAL"), ("cloud_mid", "CLOUD_MID"), ("cloud_high", "CLOUD_HIGH"))
_LOCAL_TARGET = 0.80  # S1 게이트② 판정선 — 로컬 ≥80%


def _cell(value: object, digits: int = 1) -> str:
    """수치 → 표 셀 문자열. None(미측정)은 '—'(빈칸 유지·0으로 날조 금지)."""
    if value is None:
        return "—"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def render_rows(report: dict) -> str:
    """cost_report JSON dict → 런북 결과표 행 마크다운(붙여넣기용)."""
    tiers: dict = report.get("tier_stats") or {}
    lines: list[str] = []

    lines.append("### 비용 (루프당·티어별) — 붙여넣기 행")
    lines.append("| cost_tier | 호출 수 | cost_krw (합/평균) | input/output tokens (평균) | 비고 |")
    lines.append("|---|---|---|---|---|")
    for key, label in _TIER_ROWS:
        ts = tiers.get(key)
        if ts is None:
            lines.append(f"| {label} | — | — | — | 표본 0(미측정) |")
            continue
        cost, itok, otok = ts["cost_krw"], ts["input_tokens"], ts["output_tokens"]
        lines.append(
            f"| {label} | {ts['events']} "
            f"| {_cell(cost.get('total'), 4)} / {_cell(cost.get('mean'), 4)} "
            f"| {_cell(itok.get('mean'), 0)} / {_cell(otok.get('mean'), 0)} | |"
        )
    ratio = report.get("local_ratio")
    verdict = (
        "판정 불가(분류 표본 0)"
        if ratio is None
        else (f"{'PASS' if ratio >= _LOCAL_TARGET else 'FAIL'} (로컬 {ratio:.1%} vs ≥80%)")
    )
    lines.append(f"| **로컬:클라우드 비율** | | | | **{verdict}** |")

    lines.append("")
    lines.append("### 지연 — 붙여넣기 행")
    lines.append("| 경로 | p50 latency_ms | p90 latency_ms | 비고 |")
    lines.append("|---|---|---|---|")
    for key, label in (("local", "LOCAL (Ollama)"), ("cloud_mid", "CLOUD_MID")):
        ts = tiers.get(key)
        lat = (ts or {}).get("latency_ms", {})
        lines.append(f"| {label} | {_cell(lat.get('p50'), 0)} | {_cell(lat.get('p90'), 0)} | |")

    lines.append("")
    lines.append("### 튜닝 제안 (S1-13 router 입력)")
    lines.append(
        f"- `_EST_ASSUMED_INPUT_TOKENS`  ← {_cell(report.get('suggested_est_input_tokens'))}"
    )
    lines.append(
        f"- `_EST_ASSUMED_OUTPUT_TOKENS` ← {_cell(report.get('suggested_est_output_tokens'))}"
    )

    lines.append("")
    lines.append("### verify verdict 분포 — 이 스크립트 범위 밖(별도 소스)")
    lines.append("`GET /v1/me/harness-metrics`의 verify 통과율·shadow verdict 분포로 채운다.")

    notes = report.get("notes") or []
    if notes:
        lines.append("")
        lines.append("### cost_report 주의 사항(원문 전달)")
        for note in notes:
            lines.append(f"- {note}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if len(args) != 1:
        print("사용: python3 scripts/fill_live_cost_table.py <cost_report.json>")
        return 2
    path = Path(args[0])
    if not path.exists():
        print(f"파일 없음: {path}")
        return 2
    report = json.loads(path.read_text(encoding="utf-8"))
    print(render_rows(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
