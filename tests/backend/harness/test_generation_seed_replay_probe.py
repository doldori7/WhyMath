"""EOS-73 ③ — 결정론 재생성 계약. **성립하는 부분과 성립을 주장할 수 없는 부분을 갈라 동결한다.**

이 저장소가 CI에서 *증명할 수 있는* 계약은 여기까지다:
  A. **우리 쪽 결정성** — 같은 seed·같은 입력 스냅샷을 되먹이면 우리가 provider에 보내는
     요청이 **바이트 동일**하고, 시드를 존중하는 모델이라면 같은 출력·같은 후보가 나온다.
  B. **판정의 변별력** — 시드를 무시하는(비결정적) 모델을 넣으면 프로브가 `재현`이 아니라
     **`재현 불가`**라고 말한다. 이 대조군이 없으면 프로브는 항상 통과하는 위장 계약이 된다.
  C. **미측정의 자인** — 라이브 Ollama가 없는 CI에서 이 배포의 모델 결정성은 `미측정`이며,
     리포트가 그 사실을 문장으로 낸다. *미측정은 성립도 불성립도 아니다*.

즉 **"같은 seed → 같은 출력"이 실제 모델에서 성립한다는 주장은 이 파일이 하지 않는다.**
그 주장을 하려면 `generation_seed_replay_probe` CLI를 라이브 Ollama에서 돌려야 한다(라이브
의존 — `ops/declared_unwired_audit` 선언). 성립하지 않는 계약을 통과로 위장하지 않기 위한 분할이다.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence

import pytest

from whymath_backend.harness.generation_seed_replay_probe import (
    DETERMINISM_CLAIM_UNMEASURED,
    ReplayInput,
    ReplayInputError,
    ReplayOutcome,
    ReplayVerdict,
    classify_outputs,
    exit_code_for_outcomes,
    probe_one,
    render_report,
    replay_input_from_log,
    replay_inputs_from_logs,
    report_to_json,
)
from whymath_backend.l3.equivalent.acceptance import EquivalenceSpec
from whymath_backend.l3.equivalent.llm_generator import LLMEquivalentProblemGenerator
from whymath_backend.l3.models import GenerationResult, RoutingDecision
from whymath_backend.schema.provenance import GenerationLog

_STANDARD = "[10공수1-01-01]"


def _happy_json(root: int) -> str:
    """조립을 통과하는 최소 응답 — `root`(시드 파생)만 달라진다.

    형태는 `tests/backend/l3/test_generation_log_wiring.py`의 happy 픽스처와 같은 계약을 따른다
    (conditions=검산 재료·answer_map·unit_codes 필수).
    """
    return json.dumps(
        {
            "question_text": f"이차방정식 x^2 - {root + 2}x + {2 * root} = 0 의 두 근 중 큰 근은?",
            "answer": str(root),
            "answer_explanation": f"인수분해하면 (x-2)(x-{root})=0 이므로 큰 근은 {root}.",
            "conditions": f"x**2 - {root + 2}*x + {2 * root} = 0",
            "answer_map": {"x": str(root)},
            "answer_selection": "largest",
            "difficulty_overall": 3.0,
            "unit_codes": ["ALG-QUAD-EQ"],
            "answer_format": "자연수",
            "achievement_standard_codes": [_STANDARD],
        },
        ensure_ascii=False,
    )


class _SeedRespectingProvider:
    """시드를 **존중하는** 모델 대역 — 출력이 (프롬프트, 시스템, 시드)의 순수 함수다.

    실제 모델이 이렇게 동작하는지는 이 테스트가 주장하지 않는다(라이브 측정 대상). 여기서
    고정하는 것은 *우리 코드가 그런 모델을 만났을 때 재현을 성립시키는가*다 — 시드를 안 보내거나
    호출마다 다른 시드를 뽑으면 이 대역으로도 재현이 깨진다(= 이 테스트가 잡는 회귀).
    """

    def __init__(self) -> None:
        self.seeds: list[int | None] = []
        self.calls: list[tuple[str, str, int | None]] = []

    async def generate(
        self,
        prompt: str,
        system: str,
        decision: RoutingDecision,
        *,
        images: Sequence[str] | None = None,
        temperature: float | None = None,
        json_schema: Mapping[str, object] | None = None,
        seed: int | None = None,
    ) -> GenerationResult:
        self.seeds.append(seed)
        self.calls.append((prompt, system, seed))
        material = f"{prompt}|{system}|{seed}".encode()
        digest = int(hashlib.sha256(material).hexdigest()[:6], 16)
        return GenerationResult(_happy_json(digest % 20 + 3), usage=None)


class _SeedIgnoringProvider:
    """시드를 **무시하는** 비결정적 모델 대역 — 호출마다 다른 출력(대조군)."""

    def __init__(self) -> None:
        self._counter = 0

    async def generate(
        self,
        prompt: str,
        system: str,
        decision: RoutingDecision,
        *,
        images: Sequence[str] | None = None,
        temperature: float | None = None,
        json_schema: Mapping[str, object] | None = None,
        seed: int | None = None,
    ) -> GenerationResult:
        self._counter += 1
        return GenerationResult(f"출력 {self._counter}", usage=None)


class _FailingProvider:
    """호출 자체가 실패하는 대역 — 인프라 장애가 '재현 불가'로 위장되면 안 된다."""

    async def generate(self, *args: object, **kwargs: object) -> GenerationResult:
        raise ConnectionError("Ollama 데몬 없음")


def _spec() -> EquivalenceSpec:
    return EquivalenceSpec(
        achievement_standard_codes=frozenset({_STANDARD}),
        target_misconception_ids=frozenset(),
        difficulty_overall=3.0,
        answer_format=None,
    )


def _generator(provider: object, *, seed: int) -> LLMEquivalentProblemGenerator:
    return LLMEquivalentProblemGenerator(
        provider,  # type: ignore[arg-type]
        misconception_catalog={},
        topic_hint="이차방정식",
        generation_log_sink=None,
        seed_source=lambda: seed,
    )


# ──────────────────────────────────────────────────────────────────────
# A. 우리 쪽 결정성 — 같은 좌표를 되먹이면 같은 요청·같은 결과
# ──────────────────────────────────────────────────────────────────────
class TestOurSideIsDeterministicGivenTheSeed:
    def test_same_seed_and_spec_produce_byte_identical_requests(self) -> None:
        """되먹인 좌표로 provider에 나가는 (프롬프트·시스템·시드)가 바이트 동일해야 한다."""
        first, second = _SeedRespectingProvider(), _SeedRespectingProvider()
        _generator(first, seed=4242).generate(_spec())
        _generator(second, seed=4242).generate(_spec())
        assert first.calls == second.calls
        assert first.seeds == [4242]  # 뽑은 값이 실제로 실려 나갔다(기록≠전달 방지)

    def test_seed_respecting_model_reproduces_the_same_candidate(self) -> None:
        """시드를 존중하는 모델이라면 같은 좌표 → 같은 문항(재현 계약의 우리 쪽 절반)."""
        one = _generator(_SeedRespectingProvider(), seed=7).generate(_spec())
        two = _generator(_SeedRespectingProvider(), seed=7).generate(_spec())
        assert one is not None and two is not None
        assert one.problem.question_text == two.problem.question_text
        assert one.problem.slug == two.problem.slug

    def test_different_seed_changes_the_output_for_such_a_model(self) -> None:
        """대조군 — 시드가 다르면 달라진다(같은 값을 내면 시드가 무시되고 있다는 뜻)."""
        one = _generator(_SeedRespectingProvider(), seed=7).generate(_spec())
        two = _generator(_SeedRespectingProvider(), seed=8).generate(_spec())
        assert one is not None and two is not None
        assert one.problem.question_text != two.problem.question_text


# ──────────────────────────────────────────────────────────────────────
# B. 판정의 변별력 — 실패 상태에서 실제로 실패 신호를 내는가
# ──────────────────────────────────────────────────────────────────────
class TestProbeVerdictDiscrimination:
    async def test_seed_respecting_model_is_reported_reproduced(self) -> None:
        outcome = await probe_one(
            ReplayInput(prompt="p", system="s", seed=11, model_name="qwen2.5:7b"),
            repeat=3,
            provider_factory=lambda _model: _SeedRespectingProvider(),
        )
        assert outcome.verdict is ReplayVerdict.REPRODUCED
        assert len(set(outcome.digests)) == 1

    async def test_nondeterministic_model_is_reported_not_reproduced(self) -> None:
        """**변별력 대조군** — 재현이 성립하지 않는 상태에서 프로브가 통과하면 위장 계약이다."""
        outcome = await probe_one(
            ReplayInput(prompt="p", system="s", seed=11, model_name="qwen2.5:7b"),
            repeat=2,
            provider_factory=lambda _model: _SeedIgnoringProvider(),
        )
        assert outcome.verdict is ReplayVerdict.NOT_REPRODUCED
        assert "재현 불가" in render_report([outcome])

    async def test_call_failure_is_unmeasured_not_not_reproduced(self) -> None:
        """호출 실패는 *측정 실패*다 — 예외 타입명을 남기고 '재현 불가'로 위장하지 않는다."""
        outcome = await probe_one(
            ReplayInput(prompt="p", system="s", seed=11, model_name="qwen2.5:7b"),
            repeat=2,
            provider_factory=lambda _model: _FailingProvider(),
        )
        assert outcome.verdict is ReplayVerdict.UNMEASURED
        assert outcome.error is not None and "ConnectionError" in outcome.error

    def test_single_output_is_unmeasured_not_reproduced(self) -> None:
        """비교 대상이 1건이면 미측정 — 성립으로 반올림 금지."""
        assert classify_outputs(["같은 출력"]) is ReplayVerdict.UNMEASURED
        assert classify_outputs(["a", "a"]) is ReplayVerdict.REPRODUCED
        assert classify_outputs(["a", "b"]) is ReplayVerdict.NOT_REPRODUCED


# ──────────────────────────────────────────────────────────────────────
# C. 미측정의 자인 + 좌표 복원 거부 사유
# ──────────────────────────────────────────────────────────────────────
class TestUnmeasuredIsAdmittedNotUpgraded:
    def test_report_with_no_measurement_states_the_admission(self) -> None:
        rendered = render_report([])
        assert DETERMINISM_CLAIM_UNMEASURED in rendered
        assert "성립도 불성립도 아니다" in rendered

    def test_json_claim_is_the_admission_string_when_nothing_measured(self) -> None:
        payload = report_to_json([])
        assert payload["determinism_claim"] == DETERMINISM_CLAIM_UNMEASURED


class TestReplayInputRestoration:
    def test_record_with_seed_and_snapshot_restores_the_coordinates(self) -> None:
        log = GenerationLog(
            model_name="qwen2.5:7b",
            seed=99,
            success=True,
            input_snapshot={
                "kind": "l3.equivalent.llm_generate",
                "prompt": "프롬프트",
                "system": "시스템",
                "temperature": 0.9,
            },
        )
        restored = replay_input_from_log(log)
        assert restored.seed == 99
        assert restored.prompt == "프롬프트" and restored.system == "시스템"
        assert restored.temperature == 0.9  # 온도를 빼먹으면 다른 조건에서 재게 된다

    def test_seedless_record_is_refused_with_a_reason(self) -> None:
        """seed 없는 기록은 조용히 건너뛰지 않는다 — 분모가 왜 줄었는지가 화면에 남아야 한다."""
        log = GenerationLog(model_name="claude-sonnet-4-6", seed=None, success=True)
        with pytest.raises(ReplayInputError, match="seed 미기록"):
            replay_input_from_log(log)

    def test_missing_snapshot_and_verbatim_are_distinct_reasons(self) -> None:
        no_snapshot = GenerationLog(model_name="qwen2.5:7b", seed=1, success=True)
        hash_only = GenerationLog(
            model_name="qwen2.5:7b",
            seed=1,
            success=True,
            input_snapshot={"kind": "x", "prompt_sha256": "0" * 64},
        )
        inputs, reasons = replay_inputs_from_logs([no_snapshot, hash_only])
        assert inputs == []
        assert "input_snapshot 없음" in reasons[0]
        assert "전문 없음" in reasons[1]
        rendered = render_report([], skipped=reasons)
        assert all(reason in rendered for reason in reasons)  # 사유를 렌더가 삼키지 않는다


class TestCliExitDistinguishesTotalCallFailure:
    """전건 호출 실패(Ollama 부재)를 '측정 완료'와 같은 exit로 내보내지 않는다.

    [PR #959 Codex P2 수용] probe_one이 provider 예외를 UNMEASURED+error로 *결과화*하므로
    _run은 예외를 올리지 않는다 — 그 설계의 대가로 전건 실패가 exit 0으로 나가고 있었다.
    3값 판정으로 막은 위장이 exit 축에서 되살아난 형태다.
    """

    def _outcome(self, verdict: ReplayVerdict, error: str | None) -> ReplayOutcome:
        return ReplayOutcome(
            replay_input=None,  # type: ignore[arg-type]  # 판정은 verdict·error만 본다
            digests=(),
            verdict=verdict,
            error=error,
        )

    def test_all_unmeasured_by_call_error_is_exit_2(self) -> None:
        outcomes = [
            self._outcome(ReplayVerdict.UNMEASURED, "provider.generate failed: ConnectionError: x"),
            self._outcome(ReplayVerdict.UNMEASURED, "provider.generate failed: ConnectionError: y"),
        ]
        assert exit_code_for_outcomes(outcomes) == 2

    def test_one_real_measurement_keeps_exit_0(self) -> None:
        """부분 결과는 측정이다 — 나머지가 실패해도 리포트가 건별로 말한다."""
        outcomes = [
            self._outcome(ReplayVerdict.NOT_REPRODUCED, None),
            self._outcome(ReplayVerdict.UNMEASURED, "provider.generate failed: ConnectionError: x"),
        ]
        assert exit_code_for_outcomes(outcomes) == 0

    def test_unmeasured_without_call_error_stays_exit_0(self) -> None:
        """호출 오류가 아닌 미측정은 *측정 결과*다 — exit 2로 올리면 반대 방향 위장이 된다."""
        assert exit_code_for_outcomes([self._outcome(ReplayVerdict.UNMEASURED, None)]) == 0

    def test_no_outcomes_is_not_an_error(self) -> None:
        """프로브 대상 0건은 입력 사실이지 환경 오류가 아니다(skipped 축이 사유를 말한다)."""
        assert exit_code_for_outcomes([]) == 0
