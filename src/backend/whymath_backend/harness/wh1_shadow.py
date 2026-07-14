"""WH-1 튜터링 하네스 *shadow 관측* — 노출 없이 하네스 거동만 로깅 (S1-b).

`l4/misconception/shadow.py`(judge would-be shadow)의 정본 패턴을 미러한다. coach 세션
엔드포인트가 `wh1_harness_shadow_enabled`일 때, WH-1 하네스(`LLMTutorPolicy`·S1-a)를 *라이브로
돌리되* 학생 응답은 기존 결정론 경로(`_build_response_payload`) 그대로 두고(플래그 OFF와 비트동일),
하네스가 *무슨 도구를 골랐는지·verify 판정이 무엇인지*만 **서버 로그로 남긴다** — "측정 없는
도입 없음"(04a) 원칙에 따라 실 트래픽 분포에서 하네스 거동을 무노출로 수집해 verify 게이트를
primary로 승격할 근거를 모은다(후속).

비노출·비차단·무영속 불변(judge shadow 계승):
- **비노출**: 반환 `None`. 호출자(coach)가 신호를 받을 변수가 없어 student-facing 누출이 구조적으로
  차단된다. 노출 응답은 플래그 OFF와 비트동일(결정론 경로)이고, shadow 로그는 *서버 로그 sink에만*
  흐른다.
- **비차단**: coach가 `_spawn`(create_task)으로 fire-and-forget 실행하므로 응답 경로가 하네스
  한 턴(도구 루프·LLM 왕복 수 초)을 await하지 않는다(노출 무지연). 관측·직렬화·로깅을 한 `try`로
  감싸 *어떤 예외도* 본류(학생 응답)를 안 깬다(우선순위: 학생 경험 > 진단 관측·CLAUDE.md #1≫#6).
- **무영속**: DB 영속 없이 *순수 한 턴* `run_tutoring_turn`(작업 메모리 in-memory)만 돌린다 —
  shadow는 관측만이고 상태를 영속하지 않는다(`run_persisted_turn` 아님·커밋 좌석 미접근).
- **프라이버시(미성년 PII)**: 학생 풀이 원문·풀이 단계·발화 원문·정답을 레코드에 *담지 않는다*
  (`shadow.py`:14 규약 계승). 담는 건 추상화된 status·end action_type·verify verdict·도구 호출 수·
  활성 가설 수·(있으면) 문항/세션 식별자 id뿐(비식별). 학생 원문·단계는 `LLMTutorPolicy`의
  *사적 필드*로만 주입돼(S1-a 계약) LLM 프롬프트에도 레코드에도 실리지 않는다.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Sequence
from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field

from whymath_backend.harness.wh1_llm_policy import LLMTutorPolicy
from whymath_backend.harness.wh1_loop import ToolResult, TurnOutcome, run_tutoring_turn
from whymath_backend.l3.interfaces import LLMProvider
from whymath_backend.l4.misconception.hypothesis import MisconceptionHypothesis

__all__ = ["Wh1HarnessShadowObservation", "observe_wh1_harness_shadow"]

logger = logging.getLogger("whymath.harness.wh1_shadow")  # judge shadow 네이밍 동형
# 구조화 레코드 JSON 한 줄(harvest 입력) — 평문 로그와 분리된 자식 로거(shadow.record 미러).
record_logger = logging.getLogger("whymath.harness.wh1_shadow.record")

# verify 판정 3-state를 트레이스 detail(`검증 correct(내부).`)에서 추출 — `run_tutoring_turn`은
# `last_verdict`를 `TurnOutcome`에 노출하지 않으므로(하네스 무변경 원칙) 트레이스로 관측한다.
# 'incorrect'가 'correct'를 부분 포함하므로 정규식으로 토큰 경계를 정확히 잡는다.
_VERIFY_VERDICT_RE = re.compile(r"검증 (correct|incorrect|unverifiable)")


class Wh1HarnessShadowObservation(BaseModel):
    """WH-1 하네스 shadow 관측 1건의 *구조화 레코드* — record_logger JSON emit (harvest).

    하네스 한 턴 결과에서 *비식별 요약*만 담는다: 종료 status·end action_type·verify 판정·총 도구
    호출 수·턴 종료 시 활성 가설 수·(있으면) 문항/세션 식별자 id. **학생 풀이 원문·풀이 단계·발화
    원문·정답은 담지 않는다**(`shadow.py` 규약 계승·미성년 PII) — `extra="forbid"`로 그런 필드를
    *주입조차* 못 하게 구조적으로 차단한다(비노출·로그 sink 한정 불변).
    """

    model_config = ConfigDict(extra="forbid")

    status: str
    """하네스 턴 종료 status — `ended`(발화·종료)·`budget_exhausted`(예산 소진·안전 종료)."""

    action_type: str | None
    """end_turn 행위 유형(질문|힌트|출제|격려·`ended`일 때)·비발화 요약(원문 아님·범주 라벨)."""

    verify_verdict: str | None
    """이 턴 verify_step 3-state 판정(correct|incorrect|unverifiable). verify 미호출이면 None."""

    tool_calls: int
    """총 도구 호출 횟수(하네스 트레이스 길이·거동 프로파일)."""

    hypothesis_count: int
    """턴 종료 시점 활성 오개념 가설 수(id 아님·수만·비식별)."""

    dialogue_id: str | None = None
    """세션 식별자(있으면 id만·문자열화). 학생 원문과 무관한 조인 키(비식별)."""

    turn_index: int = 1
    """세션 내 학생 턴 번호(1-기준) — 턴별 verify verdict 분포·추이 관측 키(S1-11·정수·비식별)."""

    problem_id: str | None = None
    """문항 식별자(있으면 id만·문자열화). 문항 본문 아님(코드/UUID·비식별)."""

    observed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


def _extract_verify_verdict(trace: Sequence[ToolResult]) -> str | None:
    """트레이스에서 *마지막* verify_step 판정(3-state)을 추출 — 없으면 None(verify 미호출).

    `run_tutoring_turn`이 `last_verdict`를 outcome으로 노출하지 않으므로(하네스 무변경) 트레이스
    detail(`검증 {verdict}(내부).`)에서 정규식으로 읽는다. 판정 자체는 correct/incorrect/
    unverifiable 3값뿐이라 학생 원문·정답을 담지 않는다(비식별 라벨).
    """
    for result in reversed(trace):
        if result.kind == "verify_step" and result.ok:
            match = _VERIFY_VERDICT_RE.search(result.detail)
            if match is not None:
                return match.group(1)
    return None


async def observe_wh1_harness_shadow(
    *,
    student_solution: str,
    solution_steps: Sequence[str],
    active_hypotheses: Sequence[MisconceptionHypothesis],
    provider: LLMProvider | None = None,
    turn_index: int = 1,
    max_tool_calls: int = 16,
    dialogue_id: str | None = None,
    problem_id: str | None = None,
    warmstart_outside_mids: Sequence[str] = (),
) -> None:
    """WH-1 하네스를 한 턴 돌려 *거동 요약만* 로그로 관측(shadow·비노출·무영속). 반환 `None`.

    `LLMTutorPolicy`를 구성하되 학생 원문(`student_solution`)·풀이 단계(`solution_steps`)를 정책의
    *사적 필드*로 주입한다(S1-a 계약 — LLM 프롬프트엔 요약만 나가고 원문은 match/verify 인자로만
    사적 사용). `run_tutoring_turn`(순수 한 턴·DB 무접근)으로 도구 루프를 완주시킨 뒤 결과에서
    status·end action_type·verify verdict(트레이스에서 추출)·총 도구 호출 수·활성 가설 수만 뽑아
    레코드로 emit한다. **학생 원문·풀이 단계·발화 원문·정답은 절대 레코드에 안 담는다**(미성년 PII).

    `has_solution_steps`는 `solution_steps` 유무로 정한다 — 풀이 단계가 있으면 verify 의무(§3.1)가
    걸려 하네스가 verify_step을 강제하므로, 실 트래픽에서 verify 판정 분포를 관측할 수 있다.

    **웜스타트 probe 힌트(S1-c·감사 Q5)**: `warmstart_outside_mids`(진단 시작 시 조립된 외부 오개념
    후보·`l4.misconception.warmstart`)를 `LLMTutorPolicy`의 *사적 probe 컨텍스트*(outside_mids)로만
    주입한다 — 정책이 select_probe를 고르면 `SelectProbeAction.outside_mids`에 실려 하네스의
    `plan_probe`(진단 문항 *선별*)로 흐른다. **이 힌트는 진단 probe 타깃팅 전용이다**: 코칭 context·
    개입 발화에 오개념을 preload하지 않는다(reactive retrieval 유지·CLAUDE.md). student_text·
    solution_steps와 같은 사적 주입 계약이라 LLM 프롬프트에도, shadow 레코드에도 실리지 않는다.

    **never-break**(비차단 방어선·judge shadow의 async 미러): 정책 구성·하네스 실행·직렬화·로깅을
    한 `try`로 감싸 *어떤 예외도* 본류(fire-and-forget task)를 깨지 않는다. 정책(`LLMTutorPolicy`)은
    provider 장애를 안전 강등으로 흡수하지만(never-break), 그 위 직렬화·로깅 실패까지 방어한다
    (우선순위: 학생 경험 > 진단 관측).
    """
    try:
        policy = LLMTutorPolicy(
            provider,
            # 학생 원문·풀이 단계는 프롬프트가 아니라 정책 보유값으로만 사적 사용(S1-a·요구사항 ⑥).
            student_text=student_solution,
            solution_steps=list(solution_steps),
            # 웜스타트 outside_mids도 사적 probe 컨텍스트로만 주입 — select_probe→plan_probe 전용
            # (진단 타깃팅). 코칭 context·프롬프트·레코드에 오개념 preload 0(감사 Q5·CLAUDE.md).
            outside_mids=list(warmstart_outside_mids),
        )
        outcome: TurnOutcome = await run_tutoring_turn(
            policy=policy,
            turn_index=turn_index,
            has_solution_steps=bool(solution_steps),
            initial_hypotheses=list(active_hypotheses),
            max_tool_calls=max_tool_calls,
        )
        verify_verdict = _extract_verify_verdict(outcome.trace)
        logger.info(
            "WH-1 하네스 shadow(비노출) — status=%s action_type=%s verify=%s "
            "(tool_calls=%d hypotheses=%d)",
            outcome.status,
            outcome.action_type,
            verify_verdict,
            outcome.tool_calls,
            len(outcome.hypotheses),
        )
        record_logger.info(
            Wh1HarnessShadowObservation(
                status=outcome.status,
                action_type=outcome.action_type,
                verify_verdict=verify_verdict,
                tool_calls=outcome.tool_calls,
                hypothesis_count=len(outcome.hypotheses),
                dialogue_id=dialogue_id,
                turn_index=turn_index,
                problem_id=problem_id,
            ).model_dump_json()
        )
    except Exception:  # noqa: BLE001 — 관측은 본류를 안 깬다(비차단 방어선·shadow.py:244 미러)
        return
