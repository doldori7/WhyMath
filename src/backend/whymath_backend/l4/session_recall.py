"""세션 간 구조화 회상 — 메타 한정(원문 0·복호 0). PED-04 D1 reader ②.

`docs/architecture/ai_tutor_module_gap_review.md` §2-⑤·§3 D1 정본, `04a §5.1` 강등 개정의 짝.

**왜 원문이 아니라 메타인가**: 04a v0.2는 `recall_dialogue(turn_range)`로 LLM이 과거 *원문*을
재조회하게 했으나 2026-07-29에 강등됐다. 근거 셋 — ① 대화 본문은 SEC-01 봉투 암호화라, 재조회
도구는 곧 "암호화된 미성년 대화를 열어 LLM 프롬프트에 넣는 경로"가 된다(at-rest 암호화의 실효
무력화) ② `wh1_llm_policy`의 "학생 원문·정답은 사적 필드" 격리가 WH-1 primary GA로 더 강해졌다
③ 컨텍스트 예산(`_MAX_PROMPT_TOKENS`)과도 상충한다.

**구조적 보장**: `SessionRecall`의 모든 필드는 enum·id 문자열·정수다 — 학생 원문을 실을 자리가
**타입상 존재하지 않는다**. 이것이 "복호하지 않겠다"는 약속을 주석이 아니라 타입으로 만든다.

**warmstart와의 상보(중복 금지)**: warmstart는 *무엇을 의심할지*(문항 스코프 오개념 후보),
recall은 *무엇을 이미 시도했는지*(학생 스코프 교수 이력)다. 그래서
`unresolved_hypothesis_ids`는 **LLM 프롬프트로 보내지 않는다** — 활성 가설은 이미
`TurnState.hypotheses`로 렌더되고 있어 중복이며, "오개념을 초기 context에 preload 금지"
(CLAUDE.md)에도 걸린다. 유일한 소비처는 warmstart의 `exclude_mids`로, 활성 세트 *밖*을
탐색하라는 `outside_mids`의 정의를 실제로 충족시킨다.
"""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict, Field

from whymath_backend.l4.models import PolyaStage, polya_stage_from_index
from whymath_backend.schema.enums import SocraticStrategy

__all__ = ["SessionRecall", "assemble_session_recall"]

# 회상에 싣는 최근 전략 개수 상한. 세션 간 맥락은 "최근에 어떤 결로 접근했나"만 알면 충분하고,
# 길어질수록 컨텍스트 오염(attention dilution)만 커진다(플레이북 Part 8 예산 원칙).
_MAX_STRATEGIES = 5


class SessionRecall(BaseModel):
    """직전 세션의 교수 이력 — **구조화 메타만**(원문 0·복호 0).

    필드가 전부 enum/정수/id인 것이 계약이다. 문자열 자유 필드를 추가하려는 변경은 이 모듈의
    전제를 깨는 것이므로, 추가 전에 `04a §5.1` 강등 근거를 다시 읽어야 한다.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    last_polya_stage: PolyaStage | None = Field(
        default=None, description="직전 세션이 머물던 Polya 단계(마지막 AI 턴 기준)."
    )
    last_socratic_strategies: tuple[SocraticStrategy, ...] = Field(
        default=(), description="직전 세션에서 실제로 쓴 발문 전략(시간순·최신 뒤)."
    )
    unresolved_hypothesis_ids: tuple[str, ...] = Field(
        default=(),
        description=(
            "아직 살아 있는 오개념 가설 id — **LLM 프롬프트 미주입**(모듈 docstring 참조). "
            "warmstart `exclude_mids` 전용."
        ),
    )
    turns_since: int = Field(
        default=0, ge=0, description="직전 세션 이후 이 학생이 쌓은 턴 수(경과의 대리 척도)."
    )


def assemble_session_recall(
    *,
    last_stage_step: int | None,
    strategies: Sequence[SocraticStrategy | None],
    active_hypothesis_ids: Sequence[str],
    turns_since: int,
    max_strategies: int = _MAX_STRATEGIES,
) -> SessionRecall | None:
    """조회 결과(평문 메타) → `SessionRecall`. 전 축이 비면 `None`(빈 회상 날조 금지).

    `strategies`의 None은 "그 턴에 대응 전략이 없었음"이라 그냥 버린다 — NULL을 채워 넣으면
    회상이 실제보다 촘촘해 보인다.
    """
    stage = polya_stage_from_index(last_stage_step)
    kept = tuple(s for s in strategies if s is not None)[-max_strategies:]
    ids = tuple(active_hypothesis_ids)
    if stage is None and not kept and not ids:
        return None
    return SessionRecall(
        last_polya_stage=stage,
        last_socratic_strategies=kept,
        unresolved_hypothesis_ids=ids,
        turns_since=max(0, turns_since),
    )
