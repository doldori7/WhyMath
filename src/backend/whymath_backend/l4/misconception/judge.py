"""오개념 방향 판별 LLM-judge — 후보 거짓양성 필터(슬108·coach 미배선).

substring(`diagnose`)·임베딩(`semantic_matches`)은 *고-recall*로 오개념 후보를 올리지만
**방향(⇒ 역)·부정(≠)·등치(=)를 못 가린다**(슬107이 수치로 못 박음 — FP 프로브에서 둘 다 발화).
judge는 그 후보들을 **검증**해, 학생 진술이 *그 오개념의 틀린 믿음을 실제로 표현하는지*(예)·
*올바르거나 다른 말인지*(아니오)·*모호한지*(불확실) 3값으로 판정한다. 코드는 이 출력으로
후보를 *필터링*한다(`judge_filter`) — judge 출력은 학생에게 직접 보이지 않는 내부 필터다
(`docs/prompts/misconception_judge.md` §"judge의 자리").

────────────────────────────────────────────────────────────────────────────
필터 규칙·보수성 (doc §"코드가 이 출력을 어떻게 쓰는가" + CLAUDE.md 의사결정 우선순위 1≫6)
────────────────────────────────────────────────────────────────────────────
- **`아니오`만 후보 제거.** `예`·`불확실`은 *유지*한다 — recall 보존. 거짓 단정(올바른 풀이를
  한 학생을 "오개념"이라 라벨)의 해가 *놓침*보다 크다(학생 정서가 먼저). 즉 judge는 *확실히
  올바르거나 다른 말일 때만* 후보를 버린다.
- **never-break 폴백**: 형식 위반·파싱 불가·빈 응답·seam 예외는 *모두* `불확실`(거짓 단정 금지·
  유지)로 귀결한다. LLM은 완벽하지 않으므로(judge 자체 오류 가능) 이 보수 폴백이 안전망이다
  (CLAUDE.md "확실하지 않을 때 자신 있게 말함 금지"·"검증 없이 학생에게 제공 금지").

────────────────────────────────────────────────────────────────────────────
배선 경계 (coach 결선 완료·게이트 기본 off)
────────────────────────────────────────────────────────────────────────────
judge는 *추가 필터 계층*이다 — `diagnose`·`semantic_matches`·`combine_diagnoses`는 *불변*이고
judge는 그 위에 얹힌다. seam은 주입(좌석) — 테스트는 `FakeJudge`/Fake seam(라이브 0), 라이브
경로는 L3 백킹 seam(`judge_seam.py` → `l3.pipeline.generate`·라우터 경유)을 넣는다.
`JudgeProtocol`로 L3 import 의존성을 격리한다.

**정정(2026-08-11)**: 종전 이 절은 "슬108: coach 미배선·하니스 측정만"이라 적고 있었으나
**stale**이다 — `api/coach.py:780`이 `misconception_judge_enabled`가 True일 때
`judge_filter(...)`를 실제로 호출한다. 배선은 완료돼 있고, 기본 off인 것은 *게이트*이지
*미배선*이 아니다(라이브 judge 효과는 여전히 Kiki Phaiakes9 측정 후 승격 — `04b`).
근거: `docs/architecture/misconception_module_gap_review_r2.md` §1 · §5-2.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Protocol, runtime_checkable

from whymath_backend.l4.misconception.judge_prompts import JUDGE_SYSTEM, build_judge_user
from whymath_backend.l4.misconception.models import Misconception, MisconceptionMatch
from whymath_backend.l4.models import LLMSeam

logger = logging.getLogger(__name__)

# FakeJudge 동적 판정 규칙(테스트 유틸) — (학생 진술, 후보 오개념)→판정.
JudgeRule = Callable[[str, Misconception], "JudgeVerdict"]

# 출력 파싱 라벨 — doc 출력 형식 "판정: 예|아니오|불확실" / "근거: ...". 코드는 *첫 줄 `판정:`*
# 뒤 토큰만 본다(둘째 줄 `근거:`는 로깅·텔레메트리용·학생 비노출). doc "판정 일관성 메모".
_VERDICT_LABEL = "판정:"
_REASON_LABEL = "근거:"


class JudgeVerdict(str, Enum):
    """judge 3값 판정 — doc §"코드가 이 출력을 어떻게 쓰는가" 표와 1:1.

    값은 ASCII 식별자(텔레메트리·로깅 안정성). 한국어 토큰(예/아니오/불확실)→이 enum 매핑은
    `parse_verdict`가 한다. 필터 의미는 *제거 대상이 `NOT_EXPRESSES`(아니오) 하나뿐*이라는 것:
    `EXPRESSES`(예)·`UNCERTAIN`(불확실)은 유지(recall 보존·보수).
    """

    EXPRESSES = "expresses"
    """예 — 학생 진술이 *틀린 믿음을 실제로 표현*한다(진짜 오개념). 후보 **유지**."""

    NOT_EXPRESSES = "not_expresses"
    """아니오 — *올바르거나*(역방향·부정·인접 사실) 그 오개념과 *다른* 말이다. 후보 **제거**."""

    UNCERTAIN = "uncertain"
    """불확실 — 모호·정보 부족. 후보 **유지**(보수) + 모든 폴백(형식 위반·예외)의 귀착점."""


@dataclass(slots=True, frozen=True)
class JudgeResult:
    """judge 판정 1건 — verdict + 근거(+ 원문 선택). 불변.

    `reason`은 doc 둘째 줄 `근거:`에서 추출한 한 줄(로깅·텔레메트리·학생 비노출). `raw`는 원
    응답 전문(디버그·관측 — 형식 위반 폴백 시 *무엇이 왔는지* 남긴다). 둘 다 *판정 의미에는
    영향 없음* — 필터는 `verdict`만 본다.
    """

    verdict: JudgeVerdict
    reason: str = ""
    raw: str = ""


@runtime_checkable
class JudgeProtocol(Protocol):
    """오개념 방향 판별 judge 경계 — L3 import 의존성 격리(LLMSeam 패턴 미러).

    judge는 *후보 1건*(학생 진술 × 후보 오개념)을 받아 3값 `JudgeResult`를 낸다. 테스트는
    `FakeJudge`(결정론·라이브 0)를 주입하고, 라이브 측정·후속 배선은 `LLMJudge`(L3 백킹 seam)를
    넣는다. `judge_filter`는 이 Protocol에만 의존한다(구현 비결합).
    """

    async def judge(self, student_statement: str, misconception: Misconception) -> JudgeResult:
        """학생 진술이 그 오개념(틀린 믿음)을 표현하는지 3값 판정한다."""
        ...


def parse_verdict(text: str) -> JudgeResult:
    """judge 응답 텍스트 → `JudgeResult`(보수적 폴백).

    doc "판정 일관성 메모"의 파싱 규약: 첫 `판정:` 줄 뒤 토큰만 본다(예/아니오/불확실). `근거:`
    줄은 추출해 `reason`에 담는다(로깅·비노출). **보수적 폴백**: 형식 위반(두 줄 아님·`판정:`
    부재·토큰 외 값)·빈 응답·파싱 불가는 *모두* `UNCERTAIN`(거짓 단정 금지·후보 유지)으로
    귀착한다 — doc "형식 위반 응답은 `불확실`로 폴백"·CLAUDE.md 안전판.

    파싱은 *관대하게*(라벨 줄을 어디서든 찾고 토큰을 부분일치로) 보되, 판정을 *함부로 단정하지
    않는다*: `예`/`아니오`/`불확실` 중 *정확히 하나*만 명확히 식별될 때 그 값을 쓰고, 모호하면
    (아무 토큰도 없거나 여러 토큰이 섞이면) UNCERTAIN으로 폴백한다.
    """
    raw = text or ""
    verdict_token: str | None = None
    reason = ""
    for line in raw.splitlines():
        stripped = line.strip()
        if verdict_token is None and stripped.startswith(_VERDICT_LABEL):
            verdict_token = stripped[len(_VERDICT_LABEL) :].strip()
        elif not reason and stripped.startswith(_REASON_LABEL):
            reason = stripped[len(_REASON_LABEL) :].strip()

    verdict = _token_to_verdict(verdict_token)
    return JudgeResult(verdict=verdict, reason=reason, raw=raw)


def _token_to_verdict(token: str | None) -> JudgeVerdict:
    """`판정:` 토큰(한국어)→`JudgeVerdict`. **정확 일치만** 인정 — 그 외 전부 `UNCERTAIN`.

    슬109 교정: 종전의 *부분 문자열 포함* 검사는 LLM의 헤징 응답을 **잘못된 방향**으로
    오파싱했다 — "판정: 아니오라고 단정하기 어렵다"(의도=불확실·유지)가 `'아니오' in token`으로
    NOT_EXPRESSES가 되어 후보를 *제거*했다(보수성 불변식 파괴·제거는 가장 위험한 방향).
    "판정: 예라고 보기 어려움"도 EXPRESSES로 오파싱됐다.

    교정 규칙: 토큰을 공백·후행 문장부호만 정리한 뒤 `예`/`아니오`/`불확실`과 **정확히
    일치**할 때만 그 값을 쓴다. 헤징·수식어·복합 표현·그 외 모든 변형은 형식 위반으로 보고
    `UNCERTAIN`(후보 유지)으로 폴백한다 — 출력 형식은 doc(`misconception_judge.md`)이 고정한
    계약이고, 계약을 벗어난 응답에서 판정을 *추측하지 않는 것*이 보수성 원칙이다.
    """
    if token is None:
        return JudgeVerdict.UNCERTAIN
    # 후행 문장부호(마침표류)만 관용 — "예."·"아니오." 같은 사소한 변형은 수용한다.
    cleaned = token.strip().rstrip(".。!?")
    if cleaned == "아니오":
        return JudgeVerdict.NOT_EXPRESSES
    if cleaned == "불확실":
        return JudgeVerdict.UNCERTAIN
    if cleaned == "예":
        return JudgeVerdict.EXPRESSES
    return JudgeVerdict.UNCERTAIN


class LLMJudge:
    """LLM 백킹 judge — `JudgeProtocol` 충족. seam 주입(좌석·L3 백킹/테스트 Fake).

    `judge()` = 프롬프트 빌드(`JUDGE_SYSTEM` + `build_judge_user`) → `seam.generate` →
    `parse_verdict`. seam은 `LLMSeam`(async `generate(prompt, system)`) — 테스트는 스크립트
    텍스트를 내는 Fake seam, 라이브는 L3 백킹 seam(로컬 우선·라우터 경유)을 넣는다.

    **never-break**(CLAUDE.md 가용성 #1≫): seam이 *어떤 이유로든* 예외를 던지면(모델 미도달·
    타임아웃·네트워크) 예외를 삼키고 `UNCERTAIN`(후보 유지)으로 폴백한다 — 진단 가용성을 깨지
    않는다. 실패는 *조용히 넘기지 않고* warning 로그로 남긴다(CLAUDE.md "장애 조용히 넘어가지
    말고 로그"). 파싱 폴백(형식 위반)은 `parse_verdict`가, 호출 폴백(예외)은 여기서 한다.
    """

    def __init__(self, seam: LLMSeam) -> None:
        self._seam = seam

    async def judge(self, student_statement: str, misconception: Misconception) -> JudgeResult:
        """후보 1건 판정 — 프롬프트 빌드→seam 호출→파싱(예외는 UNCERTAIN 폴백)."""
        user_prompt = build_judge_user(student_statement, misconception)
        try:
            response = await self._seam.generate(prompt=user_prompt, system=JUDGE_SYSTEM)
        except Exception:  # noqa: BLE001 — seam 장애는 가용성 이슈 → UNCERTAIN 폴백(never-break)
            logger.warning(
                "judge seam 호출 실패 — UNCERTAIN 폴백(후보 유지): misconception_id=%s",
                misconception.id,
                exc_info=True,
            )
            return JudgeResult(verdict=JudgeVerdict.UNCERTAIN, reason="seam 호출 실패")
        return parse_verdict(response)


class FakeJudge:
    """테스트 전용 결정론 judge — `JudgeProtocol` 충족(라이브 0).

    판정을 *완전 제어*한다: `verdicts`(misconception.id → JudgeVerdict)에 명시된 id는 그 값을,
    명시 안 된 id는 `default`(기본 UNCERTAIN — 유지)를 낸다. 또는 `rule`(콜러블: (statement,
    misconception)→JudgeVerdict)을 주면 그것이 우선한다. 라이브 LLM 없이 `judge_filter`·하니스
    judge 경로를 hermetic하게 검증하기 위한 것(프로덕션 사용 금지).
    """

    def __init__(
        self,
        verdicts: dict[str, JudgeVerdict] | None = None,
        *,
        default: JudgeVerdict = JudgeVerdict.UNCERTAIN,
        rule: JudgeRule | None = None,
    ) -> None:
        self._verdicts = dict(verdicts) if verdicts else {}
        self._default = default
        # rule이 있으면 (statement, misconception)→verdict로 동적 판정(매핑·default보다 우선).
        self._rule = rule

    async def judge(self, student_statement: str, misconception: Misconception) -> JudgeResult:
        """결정론 판정 — rule 우선, 없으면 id 매핑, 그것도 없으면 default."""
        if self._rule is not None:
            verdict = self._rule(student_statement, misconception)
        else:
            verdict = self._verdicts.get(misconception.id, self._default)
        return JudgeResult(verdict=verdict, reason="fake", raw="fake")


async def judge_verdicts(
    matches: list[MisconceptionMatch],
    student_statement: str,
    *,
    judge: JudgeProtocol,
) -> list[tuple[MisconceptionMatch, JudgeResult]]:
    """각 후보를 judge로 판정해 `(match, JudgeResult)` 쌍을 *순서 보존*해 반환(필터 이전 원자료).

    `judge_filter`의 하위 원자 — 판정 *근거*(verdict·reason)까지 보존해 *측정·감사*에 쓴다(어떤
    후보가 왜 유지/제거됐나). 후보들을 `asyncio.gather`로 *병렬* 판정한다(N개 순차 LLM 왕복의 지연
    누적 회피 — 카탈로그 top_k는 작아 병렬이 안전). gather는 *입력 순서를 보존*하므로 반환 쌍도 원래
    후보 순서다. 빈 입력은 빈 리스트.

    `judge` 구현의 never-break(seam 예외→UNCERTAIN)는 `LLMJudge`가 보장하므로 여기서 추가
    try/except는 두지 않는다 — judge는 *항상* JudgeResult를 돌려준다는 계약(Protocol)에 기댄다.
    """
    if not matches:
        return []
    results = await asyncio.gather(
        *(judge.judge(student_statement, m.misconception) for m in matches)
    )
    return list(zip(matches, results, strict=True))


async def judge_filter(
    matches: list[MisconceptionMatch],
    student_statement: str,
    *,
    judge: JudgeProtocol,
) -> list[MisconceptionMatch]:
    """후보 리스트에서 judge가 `아니오`(NOT_EXPRESSES) 판정한 것만 제거(순서 보존·async).

    각 match를 `judge_verdicts`로 판정해, *오직* `NOT_EXPRESSES`(아니오)면 제거하고 `EXPRESSES`(예)·
    `UNCERTAIN`(불확실)이면 유지한다(recall 보존·보수·doc 필터 규칙). 판정 *근거*(verdict·reason)가
    필요하면 `judge_verdicts`를 직접 쓴다(측정·감사). 빈 입력은 빈 리스트.

    이 함수는 *추가 필터*일 뿐 `combine_diagnoses`·`diagnose`·`semantic_matches`를 건드리지 않는다.
    """
    decided = await judge_verdicts(matches, student_statement, judge=judge)
    # 아니오(NOT_EXPRESSES)만 제거. 예·불확실은 유지(recall 보존).
    return [match for match, result in decided if result.verdict is not JudgeVerdict.NOT_EXPRESSES]


__all__ = [
    "FakeJudge",
    "JudgeProtocol",
    "JudgeResult",
    "JudgeVerdict",
    "LLMJudge",
    "judge_filter",
    "judge_verdicts",
    "parse_verdict",
]
