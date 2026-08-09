"""select_probe 변별력 실측 — REC-02 ⑤(공급 배선 전후 ok=True 건수 0 → >0).

`LLMTutorPolicy` + `run_tutoring_turn`(둘 다 실물·모킹 0)을 직접 돌려, 도구6(`select_probe`)의
실행 결과가 후보 공급 유무에 따라 실제로 달라짐을 증명한다. `probe_selection.py`(L4 순수 선택)는
*무수정*이며, 이 테스트도 그 계약을 그대로 소비할 뿐이다(⑥ L4 순수 계약 유지의 소비측 증거).

기존(공급 배선 전 상태 재현) — `probe_candidates=()`(정책 기본값, `wh1_llm_policy.py:143`의
과거 상수)면 `plan_probe([], ...)`가 항상 `None` → `SelectProbeAction` 실행 결과는 항상
`ok=False`(`wh1_loop.py:472` "판별 문항 없음"). 배선 후(이 테스트가 `assemble_probe_candidate_pool`
이 만들 법한 실제 `ProbeCandidate`를 직접 주입) 같은 활성 가설·같은 턴에서 `ok=True`로 달라진다.
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence

from whymath_backend.harness.wh1_llm_policy import LLMTutorPolicy
from whymath_backend.harness.wh1_loop import TurnOutcome, run_tutoring_turn
from whymath_backend.l3.models import GenerationResult, RoutingDecision
from whymath_backend.l4.misconception.hypothesis import MisconceptionHypothesis
from whymath_backend.l4.misconception.probe_selection import ProbeCandidate

_TARGET_MID = "mis.target"


class _ScriptedProvider:
    """select_probe 1회 → end_turn(격려)로 종료 — 도구6의 ok/detail만 관측하면 되는 최소 스크립트."""

    def __init__(self) -> None:
        self._calls = 0
        self.prompts: list[str] = []

    async def generate(
        self,
        prompt: str,
        system: str,
        decision: RoutingDecision,
        *,
        images: Sequence[str] | None = None,
    ) -> GenerationResult:
        self.prompts.append(prompt)
        self._calls += 1
        if self._calls == 1:
            return GenerationResult('{"kind": "select_probe"}')
        return GenerationResult('{"kind": "end_turn", "action_type": "격려"}')


def _hyp(mid: str) -> MisconceptionHypothesis:
    return MisconceptionHypothesis(
        misconception_id=mid, confidence=0.7, turns_since_evidence=0, evidence_count=1
    )


def _run(
    *, probe_candidates: Sequence[ProbeCandidate], provider: _ScriptedProvider | None = None
) -> TurnOutcome:
    policy = LLMTutorPolicy(
        provider if provider is not None else _ScriptedProvider(),
        probe_candidates=probe_candidates,
        theta=0.0,
    )
    return asyncio.run(
        run_tutoring_turn(
            policy=policy,
            turn_index=1,  # 1 % 5 != 0 → ε-탐색 턴 아님(활용 분기·최상위 활성 가설 겨냥).
            initial_hypotheses=[_hyp(_TARGET_MID)],
            max_tool_calls=8,
        )
    )


def _select_probe_result(outcome: TurnOutcome) -> object:
    matches = [r for r in outcome.trace if r.kind == "select_probe"]
    assert len(matches) == 1, "select_probe가 정확히 1회 호출됐어야 한다"
    return matches[0]


class TestVariance:
    def test_empty_candidates_always_fails_ok_false(self) -> None:
        """배선 전 상태 재현 — probe_candidates=()면 항상 ok=False(변별력 0의 재현)."""
        outcome = _run(probe_candidates=())
        result = _select_probe_result(outcome)
        assert result.ok is False
        assert "판별 문항 없음" in result.detail

    def test_matching_candidate_flips_to_ok_true(self) -> None:
        """배선 후 — 활성 가설 mid를 태깅한 실제 후보가 있으면 ok=True로 달라진다(⑤ 변별력)."""
        candidate = ProbeCandidate(
            problem_id="p1",
            difficulty=0.0,
            discrimination=1.0,
            misconception_tags=frozenset({_TARGET_MID}),
        )
        outcome = _run(probe_candidates=[candidate])
        result = _select_probe_result(outcome)
        assert result.ok is True
        assert "p1" in result.detail

    def test_non_matching_candidate_still_fails(self) -> None:
        """후보가 있어도 활성 가설과 무관한 태그면 여전히 ok=False(억지 매칭 없음 확인)."""
        candidate = ProbeCandidate(
            problem_id="p-other",
            difficulty=0.0,
            misconception_tags=frozenset({"mis.unrelated"}),
        )
        outcome = _run(probe_candidates=[candidate])
        result = _select_probe_result(outcome)
        assert result.ok is False


class TestExplorationBranchAlsoBenefits:
    """③ ε-탐색 성립 — outside_mids로 태깅된 후보가 있어야 탐색 턴이 거부되지 않는다."""

    def test_exploration_turn_without_outside_candidates_is_rejected(self) -> None:
        policy = LLMTutorPolicy(
            _ScriptedProvider(),
            probe_candidates=[
                ProbeCandidate(
                    problem_id="p1", difficulty=0.0, misconception_tags=frozenset({_TARGET_MID})
                )
            ],
            theta=0.0,
            outside_mids=["mis.outside"],  # 겨냥 표적은 있으나 그 태그를 가진 후보가 없음.
        )
        outcome = asyncio.run(
            run_tutoring_turn(
                policy=policy,
                turn_index=5,  # 5 % 5 == 0 → ε-탐색 강제 턴.
                initial_hypotheses=[_hyp(_TARGET_MID)],
                max_tool_calls=8,
            )
        )
        result = _select_probe_result(outcome)
        assert result.ok is False
        assert "ε-탐색" in result.detail  # §2.2 규칙2 거부(wh1_loop.py:463) — 후보 미공급의 대가.

    def test_exploration_turn_with_outside_candidate_succeeds(self) -> None:
        """outside_mids 태깅 후보가 있으면(=하네스가 함께 질의한 경우) ε-탐색이 성립한다."""
        policy = LLMTutorPolicy(
            _ScriptedProvider(),
            probe_candidates=[
                ProbeCandidate(
                    problem_id="p-outside",
                    difficulty=0.0,
                    misconception_tags=frozenset({"mis.outside"}),
                )
            ],
            theta=0.0,
            outside_mids=["mis.outside"],
        )
        outcome = asyncio.run(
            run_tutoring_turn(
                policy=policy,
                turn_index=5,
                initial_hypotheses=[_hyp(_TARGET_MID)],
                max_tool_calls=8,
            )
        )
        result = _select_probe_result(outcome)
        assert result.ok is True


class TestNoPreloadInPrompt:
    """② reactive retrieval 회귀 동결 — probe_candidates가 채워져도 LLM 프롬프트엔 안 실린다.

    `outside_mids`가 이미 지키던 계약(`wh1_llm_policy.py` `_build_prompt`가 candidates·
    outside_mids를 렌더링 대상에 아예 포함하지 않음)이 REC-02 배선 이후에도 깨지지 않았는지
    직접 문자열 검사로 봉인한다 — 오개념을 초기 context에 preload하지 않는다는 CLAUDE.md
    불변식의 이 기능 한정 회귀 테스트.
    """

    def test_candidate_problem_id_and_tags_never_in_prompt(self) -> None:
        sentinel_problem_id = "p-ZZPIIZZ"
        sentinel_tag = "mis.ZZSENTINELZZ"
        provider = _ScriptedProvider()
        outcome = _run(
            probe_candidates=[
                ProbeCandidate(
                    problem_id=sentinel_problem_id,
                    difficulty=0.0,
                    misconception_tags=frozenset({_TARGET_MID, sentinel_tag}),
                )
            ],
            provider=provider,
        )
        # select_probe가 실제로 성공했는지 먼저 확인 — 후보가 "쓰였는데도" 안 샜음을 보이려면
        # 후보가 실제로 소비된 턴이어야 의미가 있다(공회전 검사 방지).
        assert _select_probe_result(outcome).ok is True
        joined_prompts = " ".join(provider.prompts)
        assert sentinel_problem_id not in joined_prompts
        assert sentinel_tag not in joined_prompts
        # 주의: `_TARGET_MID`는 *활성 가설*(evidence-backed)이라 `active_hypotheses` 요약에는
        # 정당하게 실린다(reactive retrieval은 "증거 없는 오개념 preload 금지"이지, 이미 증거로
        # 선 활성 가설 표시를 금지하지 않는다) — 여기서 검사하지 않는다. 이 테스트가 봉인하는
        # 것은 *probe 후보 전용* 필드(candidate problem_id·후보만의 추가 태그)의 비노출이다.
