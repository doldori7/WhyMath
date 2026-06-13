"""WH-S 솔버 하네스 서브시스템 — 시스템이 *스스로 푸는* 하네스(설계 `03b_*`).

WH-1(튜터링 하네스)이 학생을 가르치는 하네스라면, WH-S는 시스템의 수학 풀이 능력을 검증
가능한 자기 진화 루프로 상승시키는 *업스트림* 서브시스템이다. 7계층 원칙(§7.5): WH-S는
WH-1의 L1(데이터)·L3(검증) 자산을 공급하는 업스트림이며 **학생 세션 경로에 직접 개입하지
않는다** — 오프라인 라이브러리(발화·API 노출 없음)다.

현 좌석(S0): ① Tier1+2 판정 combiner(`verdict.py`)와 ② 베이스라인 풀이율 측정 하네스
(`baseline.py`). Tier1 수치 답 검산은 `l3/verify_answer.py`, Tier2 기호 단계 동치는
`l3/verify_solution.py`(둘 다 기존/신규 좌석)이고, `verdict.py`는 그 둘의 결과를 §4 판정 규칙으로
결합해 최종 등급(verified/unverified/failed)을 낸다. `baseline.py`는 그 검증기 스택을 *문제셋*에
돌려 §5 난이도 사다리별 풀이율(verified 비율)을 집계한다(§9 S0 게이트 산출물 — 풀이율 곡선).

범위 밖(후속): 시드 모델 실행(후보 풀이 생성·Ollama·MCTS)·솔버 루프·도구 8종·`solution_nodes`/
저장소 스키마·자기 진화·PRM·Tier3(§9 로드맵).
"""

from __future__ import annotations

from whymath_backend.whs.baseline import (
    BandResult,
    BaselineReport,
    DifficultyBand,
    EvalItem,
    run_baseline,
)
from whymath_backend.whs.verdict import (
    WhsGrade,
    WhsVerdict,
    final_verdict,
)

__all__ = [
    "BandResult",
    "BaselineReport",
    "DifficultyBand",
    "EvalItem",
    "WhsGrade",
    "WhsVerdict",
    "final_verdict",
    "run_baseline",
]
