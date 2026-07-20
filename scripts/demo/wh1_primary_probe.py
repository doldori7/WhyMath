"""WH-1 primary(flip) 경로 in-process 측정 — 실 Ollama로 LLM 개입 실측 (서버·DB 불요).

목적: flip 기본 on 전환 전, primary 코드경로(run_tutoring_turn + LLMTutorPolicy + 실 provider)를
직접 돌려 ①LLM이 실제 호출·성공하는지(호출수·실패수) ②턴 결과(status·tool_calls·verify verdict)
③학생 발화가 하네스 템플릿/폴백인지 LLM 발화인지를 한 번에 관측한다. 서버 로그·logconfig·DB 없이
정확히 같은 하네스 코드를 태운다(측정 없는 도입 없음).
"""

import asyncio
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")  # Windows 콘솔 인코딩 안전
except Exception:  # noqa: BLE001
    pass

from whymath_backend.harness.wh1_llm_policy import LLMTutorPolicy
from whymath_backend.harness.wh1_loop import run_tutoring_turn
from whymath_backend.harness.wh1_shadow import _extract_verify_verdict

# 하네스 결정론 발화(wh1_loop.py:358,361) — 발화가 이 중 하나면 '템플릿/폴백'으로 분류.
_FALLBACKS = {
    "방금 단계에서 무엇을 근거로 그렇게 했는지 말해줄래?",
    "좋아, 지금까지 잘 하고 있어. 다음으로 가보자.",
}

_CASES = [
    ("정답 체인", "x=2", ["2x+3=7", "2x=4", "x=2"]),
    ("오답 체인", "x=1", ["2x+3=7", "2x=5", "x=1"]),
    ("자연 표기", "x=2", ["2x+3=7", "x=(7-3)/2=2"]),
]


class _CountingProvider:
    """실 provider를 감싸 LLM 호출수·실패수·첫 원문을 관측(측정 전용·계약 위임)."""

    def __init__(self, inner):
        self._inner = inner
        self.calls = 0
        self.fails = 0
        self.first_raw = None

    async def generate(self, prompt, system, decision):
        self.calls += 1
        try:
            r = await self._inner.generate(prompt, system, decision)
            if self.first_raw is None:
                self.first_raw = (getattr(r, "text", "") or "")[:400]
            return r
        except Exception as e:  # noqa: BLE001
            self.fails += 1
            print(f"      [LLM generate 예외 #{self.calls}: {type(e).__name__}: {e}]")
            raise

    def __getattr__(self, name):
        return getattr(self._inner, name)


async def run_probe(base_provider):
    print("=== WH-1 primary 경로 in-process 측정 (실 provider · 서버/DB 불요) ===")
    for label, sol, steps in _CASES:
        pp = _CountingProvider(base_provider)
        policy = LLMTutorPolicy(pp, student_text=sol, solution_steps=steps)
        try:
            outcome = await run_tutoring_turn(
                policy=policy,
                turn_index=1,
                has_solution_steps=True,
                initial_hypotheses=[],
                max_tool_calls=16,
            )
        except Exception as e:  # noqa: BLE001
            print(f"\n[{label}] 턴 예외: {type(e).__name__}: {e}")
            continue
        verdict = _extract_verify_verdict(outcome.trace)
        utter = (outcome.utterance or "").strip()
        if utter in _FALLBACKS:
            kind = "템플릿/폴백"
        elif utter:
            kind = "LLM 발화(비템플릿)"
        else:
            kind = "(빈 발화)"
        engaged = "예" if (pp.calls > 0 and pp.fails == 0) else ("일부실패" if pp.fails else "없음")
        print(f"\n[{label}]  status={outcome.status}  tool_calls={outcome.tool_calls}  verdict={verdict}")
        print(f"    LLM 호출 {pp.calls}회 (실패 {pp.fails})  → LLM 개입: {engaged}")
        print(f"    학생 발화: {utter!r}  [{kind}]")
        if pp.first_raw is not None:
            print(f"    LLM 원문(첫 호출·400자): {pp.first_raw!r}")
    print(
        "\n판독: 각 케이스 'LLM 호출>0·실패 0'이면 LLM 개입 확증. 발화가 '템플릿/폴백'이어도 "
        "설계상 정상(정답 억제 백스톱). LLM 원문이 도구선택 JSON이면 개입 확증."
    )


def _main():
    from whymath_backend.l3.providers.ollama import OllamaProvider

    asyncio.run(run_probe(OllamaProvider()))


if __name__ == "__main__":
    _main()
