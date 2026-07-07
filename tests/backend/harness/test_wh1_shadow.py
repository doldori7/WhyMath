"""WH-1 하네스 shadow 관측 단위테스트 — S1-b(비노출·비차단·무영속·never-break·프라이버시).

`observe_wh1_harness_shadow`를 `asyncio.run`으로 *직접* 호출하고 `FakeProvider`(스크립트된 JSON)로
정책 결정을 제어해, status·action_type·verify verdict·도구 수·가설 수 레코드를 실 네트워크·직접 LLM
호출 0으로 검증한다(`test_wh1_llm_policy.FakeProvider` + `test_misconception_shadow`의 record_logger
필터 + `model_validate_json` 패턴 답습).

핵심 단언:
- 레코드가 verify verdict·action_type·tool_calls·hypothesis_count를 담는다.
- **프라이버시**: 학생 풀이 원문·정답이 레코드/로그에 *어디에도* 없다(sentinel 부재·미성년 PII).
- **never-break**: 하네스가 raise해도 `None` 반환(예외 전파 0·부분 기록 0).
- **S1-a 계약**: `LLMTutorPolicy`가 student_text/steps를 사적 주입받아 LLM 프롬프트엔 원문 미노출.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Sequence

import pytest

from whymath_backend.harness import wh1_shadow
from whymath_backend.harness.wh1_shadow import (
    Wh1HarnessShadowObservation,
    observe_wh1_harness_shadow,
)
from whymath_backend.l3.models import GenerationResult, RoutingDecision
from whymath_backend.l4.misconception.hypothesis import MisconceptionHypothesis

_RECORD_LOGGER = "whymath.harness.wh1_shadow.record"

# 학생 풀이 원문·정답 — 레코드/로그에 *절대* 새면 안 되는 프라이버시 sentinel 토큰(미성년 PII).
# 정답 sentinel은 *고유 알파벳 토큰*이어야 한다 — 숫자('42' 등)는 레코드의 타임스탬프
# 초/마이크로초와 우연히 겹쳐 위양성(flaky)을 만든다(예: ...T22:33:42.8Z에 '42' 포함).
_STUDENT_SOLUTION = "내 풀이는 (a+b)² = a² + b²로 전개했어"
_ANSWER = "정답은 ZZANSWERZZ다"


class _FakeProvider:
    """스크립트된 JSON만 돌려주는 L3 provider 대역 — LLMProvider 충족(실 네트워크·직접 LLM 0).

    `test_wh1_llm_policy.FakeProvider` 미러. 소진되면 end_turn(격려)으로 루프를 종료시키고,
    호출마다 (prompt, system)을 `calls`에 기록해 원문 미노출(S1-a 계약)을 검증한다.
    """

    def __init__(self, responses: Sequence[str]) -> None:
        self._responses = list(responses)
        self._index = 0
        self.calls: list[tuple[str, str]] = []

    async def generate(
        self,
        prompt: str,
        system: str,
        decision: RoutingDecision,
        *,
        images: Sequence[str] | None = None,
    ) -> GenerationResult:
        self.calls.append((prompt, system))
        if self._index < len(self._responses):
            out = self._responses[self._index]
            self._index += 1
            return GenerationResult(out)
        return GenerationResult('{"kind": "end_turn", "action_type": "격려"}')


def _records(caplog: pytest.LogCaptureFixture) -> list[str]:
    """wh1 하네스 shadow 구조화 record 로거 JSON 라인만(평문·다른 로거 노이즈 배제)."""
    return [r.getMessage() for r in caplog.records if r.name == _RECORD_LOGGER]


def _hyp(mid: str, *, confidence: float = 0.7) -> MisconceptionHypothesis:
    return MisconceptionHypothesis(
        misconception_id=mid,
        confidence=confidence,
        turns_since_evidence=0,
        evidence_count=1,
    )


# ──────────────────────────────────────────────────────────────────────────
# ① 레코드가 status·action_type·verify verdict·tool_calls·가설 수를 담는다
# ──────────────────────────────────────────────────────────────────────────
class TestRecordsHarnessBehavior:
    def test_records_verdict_action_and_counts(self, caplog: pytest.LogCaptureFixture) -> None:
        # 풀이 제출 턴(has_solution_steps=True) — 하네스가 verify 의무를 강제하므로 verify_step이
        # 트레이스에 생긴다. LLM이 곧장 end_turn을 내도 정책이 verify_step으로 재지정 후 종료.
        provider = _FakeProvider(
            [
                '{"kind": "end_turn", "action_type": "격려"}',  # 정책이 verify_step으로 재지정
                '{"kind": "end_turn", "action_type": "질문"}',  # 검증 후 종료 허용
            ]
        )
        with caplog.at_level(logging.INFO, logger=_RECORD_LOGGER):
            result = asyncio.run(
                observe_wh1_harness_shadow(
                    student_solution=_STUDENT_SOLUTION,
                    solution_steps=["x = 2", "x + 1 = 3"],
                    active_hypotheses=[_hyp("distribution-over-power")],
                    provider=provider,
                )
            )
        assert result is None  # 비노출 — 호출자가 신호 받을 변수 없음
        records = _records(caplog)
        assert len(records) == 1
        obs = Wh1HarnessShadowObservation.model_validate_json(records[0])
        assert obs.status == "ended"
        assert obs.action_type == "질문"  # 검증 후 종료 발화 유형
        # verify verdict가 3-state 중 하나로 관측된다(트레이스 detail에서 추출·비식별 라벨).
        assert obs.verify_verdict in ("correct", "incorrect", "unverifiable")
        assert obs.tool_calls >= 2  # verify_step + end_turn 최소
        assert obs.hypothesis_count == 1  # 주입 가설 수 반영

    def test_no_solution_steps_verdict_none(self, caplog: pytest.LogCaptureFixture) -> None:
        # 풀이 단계 미제출 — verify 의무 없음 → verify_step 미호출 → verify_verdict=None.
        provider = _FakeProvider(['{"kind": "end_turn", "action_type": "격려"}'])
        with caplog.at_level(logging.INFO, logger=_RECORD_LOGGER):
            asyncio.run(
                observe_wh1_harness_shadow(
                    student_solution=_STUDENT_SOLUTION,
                    solution_steps=[],
                    active_hypotheses=[],
                    provider=provider,
                )
            )
        obs = Wh1HarnessShadowObservation.model_validate_json(_records(caplog)[0])
        assert obs.verify_verdict is None  # verify 미호출
        assert obs.hypothesis_count == 0

    def test_problem_id_threaded_as_id_only(self, caplog: pytest.LogCaptureFixture) -> None:
        # 문항 식별자는 id만 실린다(문항 본문 아님·비식별 조인 키).
        provider = _FakeProvider(['{"kind": "end_turn", "action_type": "격려"}'])
        with caplog.at_level(logging.INFO, logger=_RECORD_LOGGER):
            asyncio.run(
                observe_wh1_harness_shadow(
                    student_solution="풀이",
                    solution_steps=[],
                    active_hypotheses=[],
                    provider=provider,
                    problem_id="prob-123",
                    dialogue_id="dlg-456",
                )
            )
        obs = Wh1HarnessShadowObservation.model_validate_json(_records(caplog)[0])
        assert obs.problem_id == "prob-123"
        assert obs.dialogue_id == "dlg-456"


# ──────────────────────────────────────────────────────────────────────────
# ② 프라이버시 — 학생 원문·정답 미저장(미성년 PII 구조적 차단)
# ──────────────────────────────────────────────────────────────────────────
class TestNoRawLeak:
    def test_record_omits_student_solution_and_answer(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        # 학생 풀이 원문·정답이 레코드에 *어디에도* 없다(id·카운트·라벨만·shadow 규약 계승).
        provider = _FakeProvider(
            [
                '{"kind": "match_misconception"}',  # 학생 원문을 정책이 사적 사용(비노출)
                '{"kind": "end_turn", "action_type": "격려"}',
            ]
        )
        with caplog.at_level(logging.INFO, logger=_RECORD_LOGGER):
            asyncio.run(
                observe_wh1_harness_shadow(
                    student_solution=_STUDENT_SOLUTION + " " + _ANSWER,
                    solution_steps=["x = 2", "x + 1 = 3"],
                    active_hypotheses=[],
                    provider=provider,
                )
            )
        raw = _records(caplog)[0]
        assert "(a+b)" not in raw  # 학생 풀이 원문 미포함
        assert "전개했어" not in raw
        assert "ZZANSWERZZ" not in raw  # 정답 미포함
        # 파싱된 레코드에도 원문/정답 성격의 자유 텍스트 필드가 없다(고정 스키마·extra="forbid").
        parsed = json.loads(raw)
        assert set(parsed.keys()) <= {
            "status",
            "action_type",
            "verify_verdict",
            "tool_calls",
            "hypothesis_count",
            "dialogue_id",
            "problem_id",
            "observed_at",
        }

    def test_model_forbids_extra_fields(self) -> None:
        # extra="forbid" — 학생 원문 같은 PII 필드를 *주입조차* 못 한다(구조적 차단 회귀 가드).
        with pytest.raises(Exception):  # noqa: B017,PT011 — pydantic ValidationError
            Wh1HarnessShadowObservation(
                status="ended",
                action_type="격려",
                verify_verdict=None,
                tool_calls=1,
                hypothesis_count=0,
                student_solution="이런 필드는 금지",  # type: ignore[call-arg]
            )


# ──────────────────────────────────────────────────────────────────────────
# ③ S1-a 계약 — LLM 프롬프트에 학생 원문·정답 미노출(정책 사적 주입)
# ──────────────────────────────────────────────────────────────────────────
class TestPolicyPrivateInjection:
    def test_llm_prompt_never_contains_raw_solution(self) -> None:
        # 정책이 student_text/steps를 사적 필드로 받아 LLM 프롬프트엔 요약만 나간다(S1-a 계약).
        provider = _FakeProvider(
            [
                '{"kind": "match_misconception"}',
                '{"kind": "verify_step"}',
                '{"kind": "end_turn", "action_type": "격려"}',
            ]
        )
        asyncio.run(
            observe_wh1_harness_shadow(
                student_solution=_STUDENT_SOLUTION + " " + _ANSWER,
                solution_steps=["x = 2", "x + 1 = 3"],
                active_hypotheses=[],
                provider=provider,
            )
        )
        # provider가 받은 모든 (prompt, system)에 학생 원문·정답·풀이 단계가 없어야 한다.
        for prompt, system in provider.calls:
            blob = prompt + system
            assert "(a+b)" not in blob
            assert "전개했어" not in blob
            assert "ZZANSWERZZ" not in blob
            assert "x + 1 = 3" not in blob  # 풀이 단계 원문도 미노출


# ──────────────────────────────────────────────────────────────────────────
# ④ never-break — 하네스가 raise해도 None 반환(예외 전파 0)
# ──────────────────────────────────────────────────────────────────────────
class TestNeverBreak:
    def test_harness_raises_returns_none(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        # run_tutoring_turn을 강제 실패시켜도 observe는 조용히 None 반환(fire-and-forget task 보호).
        async def _boom(**_kwargs: object) -> object:
            raise RuntimeError("하네스 강제 실패(never-break 테스트)")

        monkeypatch.setattr(wh1_shadow, "run_tutoring_turn", _boom)
        with caplog.at_level(logging.INFO, logger=_RECORD_LOGGER):
            result = asyncio.run(
                observe_wh1_harness_shadow(
                    student_solution=_STUDENT_SOLUTION,
                    solution_steps=[],
                    active_hypotheses=[],
                    provider=_FakeProvider([]),
                )
            )
        assert result is None  # 예외 전파 0(never-break)
        assert _records(caplog) == []  # 실패라 부분 기록도 0


# ──────────────────────────────────────────────────────────────────────────
# ⑤ 웜스타트 배선(S1-c) — warmstart_outside_mids가 정책 사적 probe 컨텍스트로만 흐른다
# ──────────────────────────────────────────────────────────────────────────
class TestWarmstartWiring:
    """`warmstart_outside_mids`가 `LLMTutorPolicy(outside_mids=...)`로만 주입되는지 구조 동결.

    경계(감사 Q5): 웜스타트 힌트는 **진단 probe 타깃팅 전용**이라 정책의 `outside_mids`
    (→select_probe→plan_probe)로만 흘러야 하고, 코칭 관련 인자에는 결코 실리지 않는다.
    `LLMTutorPolicy`를 스파이로 감싸 생성 kwargs를 캡처해 못 박는다(preload 금기 회귀 가드).
    """

    def test_warmstart_flows_to_policy_outside_mids_only(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        captured: dict[str, object] = {}
        real_policy = wh1_shadow.LLMTutorPolicy

        def _spy_policy(provider: object, **kwargs: object) -> object:
            captured.update(kwargs)
            return real_policy(provider, **kwargs)  # type: ignore[arg-type]

        monkeypatch.setattr(wh1_shadow, "LLMTutorPolicy", _spy_policy)
        warmstart = ["M0001", "M0002", "M0003"]
        asyncio.run(
            observe_wh1_harness_shadow(
                student_solution="풀이",
                solution_steps=[],
                active_hypotheses=[],
                provider=_FakeProvider(['{"kind": "end_turn", "action_type": "격려"}']),
                warmstart_outside_mids=warmstart,
            )
        )
        # 웜스타트는 정책의 outside_mids로만 주입된다(사적 probe 컨텍스트).
        assert captured.get("outside_mids") == warmstart
        # 코칭·발화 인자로는 warmstart가 새지 않는다(preload 금기 — 코칭은 reactive 유지).
        assert captured.get("student_text") == "풀이"  # 학생 원문만 사적 주입
        for key in ("probe_candidates", "solution_steps"):
            assert warmstart != captured.get(key)

    def test_warmstart_reaches_select_probe_action(self) -> None:
        # 정책이 select_probe를 고르면 warmstart outside_mids가 SelectProbeAction에 실린다
        # (plan_probe 소비처로 흐르는 최종 경로·hermetic).
        policy = wh1_shadow.LLMTutorPolicy(
            _FakeProvider([]),
            outside_mids=["M0001", "M0002"],
        )
        action = policy._build_action({"kind": "select_probe"})
        assert action is not None
        assert getattr(action, "outside_mids", None) == ["M0001", "M0002"]

    def test_default_empty_warmstart(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # warmstart 미주입(기본 빈 튜플)이면 정책 outside_mids는 빈 리스트(기존 동작 불변).
        captured: dict[str, object] = {}
        real_policy = wh1_shadow.LLMTutorPolicy

        def _spy_policy(provider: object, **kwargs: object) -> object:
            captured.update(kwargs)
            return real_policy(provider, **kwargs)  # type: ignore[arg-type]

        monkeypatch.setattr(wh1_shadow, "LLMTutorPolicy", _spy_policy)
        asyncio.run(
            observe_wh1_harness_shadow(
                student_solution="풀이",
                solution_steps=[],
                active_hypotheses=[],
                provider=_FakeProvider(['{"kind": "end_turn", "action_type": "격려"}']),
            )
        )
        assert captured.get("outside_mids") == []
