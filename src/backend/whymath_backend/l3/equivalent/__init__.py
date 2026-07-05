"""L3 동등문제 — 자체생성 동등문제 수용 게이트 (S2-a).

설계 정본: `docs/architecture/03_content_generation.md` §"개념 시퀀스 동치성 판정 —
휴리스틱 + 사람 검수 병행". 동등성은 미해결 연구 난제이므로 스코어러는 *확정이 아니라
분류*만 한다("휴리스틱으로 좁히고 사람이 닫는다"). 저작권은 구조적 불변식이 강제하므로
게이트는 값 확인만·정확성은 Tier1+Tier2 결합·위생은 시드 검증기·동등성은 4성분 가중 분류.

S2-d(`generator.py`·`orchestrator.py`): 생성부 좌석(`ScriptedGenerator`·LLM 자리표시자)과
S2 파이프라인 end-to-end 오케스트레이터(생성→게이트→dedup→저장)를 담아 S2를 닫는다.

후속: 실 LLM 생성기(Phaiakes9)·사람 검수 큐 결선·임계값 점진 보정.
"""

from whymath_backend.l3.equivalent.acceptance import (
    AcceptanceVerdict,
    EquivalenceSpec,
    EquivalenceVerdict,
    evaluate_equivalent_candidate,
)
from whymath_backend.l3.equivalent.generator import (
    CandidateProblem,
    EquivalentProblemGenerator,
    ScriptedGenerator,
)
from whymath_backend.l3.equivalent.orchestrator import (
    GenerationOutcome,
    ProblemBankSink,
    run_batch,
    run_equivalent_generation,
)

__all__ = [
    "AcceptanceVerdict",
    "CandidateProblem",
    "EquivalenceSpec",
    "EquivalenceVerdict",
    "EquivalentProblemGenerator",
    "GenerationOutcome",
    "ProblemBankSink",
    "ScriptedGenerator",
    "evaluate_equivalent_candidate",
    "run_batch",
    "run_equivalent_generation",
]
