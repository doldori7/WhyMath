#!/usr/bin/env python3
"""계층별 커버리지 게이트 — `coverage.xml`을 읽어 `whymath_backend` 서브패키지(계층)별
라인 커버리지가 각 층의 바닥선(floor) 이상인지 검사한다. 미달 계층이 하나라도 있으면 exit 1.

배경(ARCH-14 ② '강화' 경로): 백엔드는 그동안 **집계 70%**(`--cov-fail-under=70`)만 강제했고,
`docs/standards/testing.md`가 선언한 계층별 목표(도메인 L4 90%·L1/L2/L5 80%·L3 70%)는 문서 선언만
있고 CI가 강제하지 않았다(선언↔강제 불일치). 이 게이트가 계층별 최소선을 *실제로* 강제한다.

바닥선 원칙: **실측 baseline 기준 ratchet**(회귀 방지). 선언 지향치(declared)는 주석으로 병기하되,
게이트 값은 실측 이상으로만 상향한다 — 지향치가 실측보다 높으면 그 값으로 게이트할 수 없다
(즉사). 실측이 지향치에 도달하면 바닥선을 지향치까지 끌어올린다.

집계 게이트와 상보: `--cov-fail-under=70`은 전체 하한, 이 게이트는 계층별 하한(한 계층이 아무리
낮아도 집계 평균에 묻히던 사각을 닫는다). hermetic — coverage.xml만 읽고 DB·네트워크 0.
"""

from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from collections import defaultdict

# 계층별 바닥선(%) — testing.md 선언 목표를 그대로 강제한다. CI 실측(2026-07-25·backend
# lint 잡 자가보고)이 전 계층에서 선언치를 상회해(api 98.3·l1 86.7·l2 96.9·l3 95.4·l4 95.2·
# 집계 92.83%), 바닥선을 선언 지향치로 직접 설정 가능(≥5pt 여유·회귀 방지). 커버리지가
# 내려가면 이 선에서 red — 지향치 하향은 금지, 상향만 허용(점진 강화).
LAYER_FLOORS: dict[str, float] = {
    "l1": 80.0,  # 데이터 — 실측 86.7%
    "l2": 80.0,  # ML 모델 — 실측 96.9%
    "l3": 70.0,  # LLM 통합(모킹) — 실측 95.4%
    "l4": 90.0,  # 도메인 로직 — 실측 95.2%
    "api": 80.0,  # API/L5 — 실측 98.3%
}
# l5(상호작용·OCR/Manim 등 외부 의존)·l6·횡단(db·schema·ops·privacy·whs)은 집계 70%로 커버
# (계층별 게이트 미부여 — testing.md 미선언 또는 외부 의존 과다). 필요 시 확장.


def layer_coverage(xml_path: str) -> dict[str, tuple[int, int]]:
    """coverage.xml → {서브패키지: (covered_lines, total_lines)}. `whymath_backend/<pkg>/...`의
    첫 세그먼트를 계층 키로 집계한다."""
    root = ET.parse(xml_path).getroot()
    agg: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for cls in root.iter("class"):
        parts = cls.get("filename", "").replace("\\", "/").split("/")
        # coverage.xml의 filename은 <source>(=whymath_backend 패키지 루트) 기준 *상대경로*다
        # (예: 'l1/foo.py'·'api/_auth.py'·루트 모듈 'config.py'). 절대경로나 whymath_backend
        # 접두가 붙는 변형도 흡수하도록, whymath_backend 이후로 잘라낸 뒤 첫 세그먼트를 계층으로.
        if "whymath_backend" in parts:
            parts = parts[parts.index("whymath_backend") + 1 :]
        if not parts:
            continue
        top = parts[0]
        if top.endswith(".py"):  # 패키지 루트 모듈(계층 아님)
            continue
        lines = cls.find("lines")
        if lines is None:
            continue
        for ln in lines.findall("line"):
            agg[top][1] += 1
            if int(ln.get("hits", "0")) > 0:
                agg[top][0] += 1
    return {k: (v[0], v[1]) for k, v in agg.items()}


def evaluate(
    coverage: dict[str, tuple[int, int]], floors: dict[str, float]
) -> tuple[list[str], list[str]]:
    """(실패 계층, 무측정 계층) 반환. 무측정(total=0)은 커버리지 설정 오류로 간주해 실패 처리."""
    failed: list[str] = []
    unmeasured: list[str] = []
    for layer, floor in sorted(floors.items()):
        covered, total = coverage.get(layer, (0, 0))
        if total == 0:
            unmeasured.append(layer)
            failed.append(layer)
            continue
        if 100.0 * covered / total < floor:
            failed.append(layer)
    return failed, unmeasured


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    xml_path = argv[0] if argv else "coverage.xml"
    coverage = layer_coverage(xml_path)

    print(f"{'layer':6} {'cov%':>7} {'floor':>7}  판정  (covered/total · 지향)")
    aspirations = {"l1": 80, "l2": 80, "l3": 70, "l4": 90, "api": 80}
    for layer, floor in sorted(LAYER_FLOORS.items()):
        covered, total = coverage.get(layer, (0, 0))
        pct = 100.0 * covered / total if total else 0.0
        verdict = "무측정" if total == 0 else ("PASS" if pct >= floor else "FAIL")
        asp = aspirations.get(layer, 0)
        print(
            f"{layer:6} {pct:6.1f}% {floor:6.1f}%  {verdict:4}  ({covered}/{total} · 지향 {asp}%)"
        )

    failed, unmeasured = evaluate(coverage, LAYER_FLOORS)
    if unmeasured:
        print(
            f"무측정 계층(coverage.xml에 라인 0): {unmeasured} — "
            "커버리지 설정(--cov 범위) 확인 필요(성공 위장 방지·명시 실패)."
        )
    if failed:
        print(f"FAIL — 계층별 커버리지 바닥선 미달: {sorted(set(failed))}")
        return 1
    print("PASS — 전 계층 바닥선 충족")
    return 0


if __name__ == "__main__":  # pragma: no cover — 엔트리포인트
    sys.exit(main())
