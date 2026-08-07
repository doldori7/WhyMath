"""서버측 답안 채점 shadow 리포트 — NLP-02(관측 전용 배치·요청 경로 무변경).

설계 정본: `docs/architecture/nlp_module_gap_review.md` §3 D2(Kiki 결정 2026-07-31 "측정
없는 도입 없음"). `student_answer`는 이미 요청 슬롯(`api/me.py::AttemptSubmitRequest`)이자
적재 컬럼(`db/models/activity.py::ProblemAttempt.student_answer`)이나 아무도 읽지 않는다 —
학습자 모델 전체(BKT·스킬 숙달 전파)가 검증되지 않은 클라이언트 `is_correct` 위에 서 있다.

이 모듈은 그 소비 0을 해소하되 **관측만** 한다:
  - `POST /v1/me/attempts`(`submit_attempt`)·`AttemptSubmitRequest`·`AttemptSubmitResponse`·
    두 mastery 전파 콜사이트(`record_problem_attempt_mastery`·`record_problem_attempt_skill_
    mastery`)는 **무변경**이다 — 이 모듈은 별도 배치 CLI(`main()`)로 분리되어 라이브 요청
    경로에 신규 SELECT·지연 0을 유지한다.
  - BKT/mastery 입력은 여전히 클라 보고 `is_correct`다(권위 이관 아님 — 이번 슬라이스는
    이중 회계 *관측*이며, "클라이언트를 믿어도 되는가"를 판단할 재료만 쌓는다).

conditions/answer_map 파생의 정확성 위험(핵심 — `derive_verify_inputs` 참조): `Problem`에는
`answer_map` 필드가 없다(이 태스크의 제약 — 신규 컬럼 0). 있는 재료는 `Problem.conditions_
parsed[*].formal`(자유서술 수식 문자열, 전 레포 소비자 0건 확인됨)과 단일 `Problem.answer`
뿐이다. 순진하게 `{"x": problem.answer}`를 무조건 답산맵으로 쓰는 것은 *안전하지 않다* —
조건의 실제 미지수가 `x`가 아니라 `y`·`t`·`n` 등이면, 대입 자체는 예외를 던지지 않고
`verify_answer`의 수치 샘플링 경로가 *엉뚱한 변수*에 값을 넣어 거짓 pass/fail을 만들 수
있다(조용한 오류 유입 — `verify_answer` 자체는 정직해도 호출자의 입력 조립이 틀리면 그
정직성이 무의미해진다). `derive_verify_inputs`가 이 위험의 유일한 방어선이다: 모든 조건의
`formal`이 파싱 가능하고 그 자유기호 합집합이 **정확히 `{"x"}`**(단일 미지수)일 때만
파생하고, 아니면 `None`(비파생)으로 물러나 `verify_answer`를 아예 호출하지 않는다 — 다중
미지수 문항은 이 슬라이스의 의도적 스코프 밖이다.

**채점 대상은 항상 학생 제출값이다**: `derive_verify_inputs`가 반환하는 `answer_map`은
`Problem.answer`(문항 정답 본문)로 채워지지만, 이는 파생 가능성(자유기호 게이트)을 확정하는
*틀*일 뿐이다. 실제 shadow 채점(`grade_attempt`)은 그 틀의 변수명에 **학생이 실제로 제출한
`student_answer`**를 대입해 `verify_answer`를 호출한다 — `Problem.answer`를 그대로 검산하면
"문항 자체의 자기정합성"만 확인할 뿐 학생 채점이 되지 않는다.

이중 회계(acceptance④): "검산 불가"(conditions/answer_map을 못 만들었거나 학생이 답을 아예
제출하지 않음)와 "검산은 했으나 unverifiable"(`verify_answer`가 3상태 중 unverifiable을
정직하게 반환)은 *서로 다른, 겹치지 않는* 버킷이다 — 전자는 `not_derivable_count`, 후자는
`verdict_counts["unverifiable"]`. 섞으면 "우리가 입력을 못 만들었다"와 "검증기가 모른다고
답했다"가 뒤섞여 실효 커버리지 판단이 왜곡된다(§4 D2 acceptance②·④ 정합).

교수학 금기(acceptance②): `unverifiable`은 오답으로 강등하지 않는다 — `client_grade_mismatch`
집계는 verdict가 `pass`/`fail`일 때만 클라 보고와 대조한다.

사용:
    python -m whymath_backend.harness.attempt_grading_shadow_report
    python -m whymath_backend.harness.attempt_grading_shadow_report --json out/shadow.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import sympy
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from whymath_backend.db.models.activity import ProblemAttempt as ProblemAttemptORM
from whymath_backend.db.models.problem import Problem as ProblemORM
from whymath_backend.l3.verify_answer import AnswerVerdict, verify_answer
from whymath_backend.schema.problem import Problem

__all__ = [
    "AttemptRecord",
    "ShadowGradingReport",
    "build_report",
    "derive_verify_inputs",
    "fetch_attempt_records",
    "grade_attempt",
    "main",
    "render_report",
    "report_to_json",
]

# 침묵실패 금지(CLAUDE.md) — 파생 실패는 보수적 None 반환이 정상 동작이라 raise하지 않지만,
# 예외 *타입명*은 debug로 남겨 계통 장애(예: formal 파싱 실패가 특정 예외로 폭증)를 관측 가능하게
# 한다(verify_answer.py의 동일 관례 — `logger.debug("... 보수 회피: %s", type(exc).__name__)`).
logger = logging.getLogger("whymath.harness.attempt_grading_shadow_report")

# 이 슬라이스가 지원하는 유일한 미지수 이름 — 다중 미지수 문항은 스코프 밖(모듈 docstring).
_SUPPORTED_UNKNOWN = "x"


# ──────────────────────────────────────────────────────────────────────────
# 파생 — conditions/answer_map(모듈 docstring의 핵심 위험 지점)
# ──────────────────────────────────────────────────────────────────────────
def derive_verify_inputs(problem: Problem) -> tuple[list[str], dict[str, str]] | None:
    """`Problem.conditions_parsed[*].formal` + `Problem.answer` → verify_answer 입력 파생.

    단일 미지수(`x`) 문항만 지원한다(모듈 docstring 위험 설명). 다음 중 하나라도 해당하면
    `None`(비파생) — **`verify_answer`를 호출하지 않는다**(false mismatch 근원 차단):
      - 조건이 하나도 없음(`conditions_parsed`가 빈 목록)
      - `Problem.answer`가 없거나 공백만
      - 어느 조건의 `formal`이 없거나 공백만
      - 어느 조건의 `formal`이 SymPy로 파싱 불가(구문 오류 등 — 보수적 회피)
      - 조건들의 자유기호 합집합이 정확히 `{"x"}`가 아님(미지수가 없거나·다른 이름이거나·
        다중 변수인 경우 — 이 게이트가 "y를 x로 오인"류 오류를 막는 유일한 방어선)

    반환은 `(conditions, answer_map)`이며 `answer_map`은 `{"x": problem.answer}` — 이 값은
    "파생 가능성이 확정됐다"는 *틀*일 뿐, 실제 shadow 채점은 `grade_attempt`가 이 틀의 키에
    학생 제출값을 대입해서 이뤄진다(모듈 docstring "채점 대상은 항상 학생 제출값이다").
    """
    if not problem.conditions_parsed:
        return None
    if not problem.answer or not problem.answer.strip():
        return None

    formals: list[str] = []
    free_symbols: set[str] = set()
    for condition in problem.conditions_parsed:
        formal = condition.formal
        if not formal or not formal.strip():
            return None
        try:
            parsed = sympy.sympify(formal, evaluate=False)
        except Exception as exc:  # noqa: BLE001 — 파싱 불가는 보수적 비파생(pass 위장 금지)
            logger.debug("derive_verify_inputs 비파생(formal 파싱 실패): %s", type(exc).__name__)
            return None
        free_symbols |= {str(s) for s in parsed.free_symbols}
        formals.append(formal)

    if free_symbols != {_SUPPORTED_UNKNOWN}:
        return None
    return formals, {_SUPPORTED_UNKNOWN: problem.answer}


def grade_attempt(problem: Problem, student_answer: str | None) -> AnswerVerdict | None:
    """(문항, 학생 제출 답안) → shadow 채점 verdict. `None`이면 not_derivable.

    `student_answer`가 없거나(None·공백) `derive_verify_inputs`가 비파생을 돌리면 `None`
    (검산 자체를 시도하지 않음 — acceptance①의 "student_answer가 있고 문항이 검산 가능하면"
    두 전제를 모두 만족할 때만 `verify_answer`를 호출한다).

    실제 대입값은 항상 `student_answer`다 — `derive_verify_inputs`가 돌린 `answer_map`은
    미지수 이름(`x`)만 취하고 값은 버린다(그 값은 `Problem.answer`이지 채점 대상이 아니다).
    """
    if student_answer is None or not student_answer.strip():
        return None
    derived = derive_verify_inputs(problem)
    if derived is None:
        return None
    conditions, canonical_answer_map = derived
    student_map = dict.fromkeys(canonical_answer_map, student_answer)
    return verify_answer(conditions, student_map)


# ──────────────────────────────────────────────────────────────────────────
# 조회 — attempt+problem 조인(얇은 I/O, 집계 로직 0 — 순수 코어는 build_report)
# ──────────────────────────────────────────────────────────────────────────
@dataclass(slots=True, frozen=True)
class AttemptRecord:
    """DB에서 읽은 attempt 1건의 최소 투영 — `build_report`(순수 집계)의 유일한 입력.

    `problem`이 `None`이면 `problem_id`가 NULL이거나 FK가 고아(조인 실패)인 경우다 —
    `build_report`는 이를 예외 없이 `not_derivable`로 집계한다(관측 정직성 — 조용히 skip해
    분모를 왜곡하지 않는다).
    """

    attempt_id: uuid.UUID
    student_answer: str | None
    client_is_correct: bool | None
    problem: Problem | None


async def fetch_attempt_records(
    session: AsyncSession,
    *,
    user_id: uuid.UUID | None = None,
    limit: int | None = None,
) -> list[AttemptRecord]:
    """`problem_attempt` ⋈ `problem` 조회 → `AttemptRecord` 리스트(각 `to_schema()` 변환).

    `user_id`(선택)로 한 사용자로 스코핑할 수 있다(운영 디버그·테스트 격리 — 생략하면 전량).
    `problem_id`가 NULL이거나 참조 문제가 삭제된 attempt는 outer join으로 `problem=None`을
    받아 집계 단계(`build_report`)에서 `not_derivable`로 처리한다(예외로 튕기지 않는다).
    """
    stmt = select(ProblemAttemptORM, ProblemORM).outerjoin(
        ProblemORM, ProblemAttemptORM.problem_id == ProblemORM.problem_id
    )
    if user_id is not None:
        stmt = stmt.where(ProblemAttemptORM.user_id == user_id)
    stmt = stmt.order_by(ProblemAttemptORM.attempt_id)
    if limit is not None:
        stmt = stmt.limit(limit)

    rows = (await session.execute(stmt)).all()
    records: list[AttemptRecord] = []
    for attempt_row, problem_row in rows:
        records.append(
            AttemptRecord(
                attempt_id=attempt_row.attempt_id,
                student_answer=attempt_row.student_answer,
                client_is_correct=attempt_row.is_correct,
                problem=problem_row.to_schema() if problem_row is not None else None,
            )
        )
    return records


# ──────────────────────────────────────────────────────────────────────────
# 집계 — 이중 회계 리포트(순수 코어 — DB·LLM·HTTP 0)
# ──────────────────────────────────────────────────────────────────────────
_VerdictState = Literal["pass", "fail", "unverifiable"]


@dataclass(slots=True, frozen=True)
class ShadowGradingReport:
    """shadow 채점 집계 결과 전량(불변) — `l4.content_supply.SupplyTally` 이중 회계 관례 답습.

    `mismatch_rate`/`unverifiable_rate`는 `verifiable_count == 0`이면 `None`이다(분모 없는
    0 금지 — "미상"을 0%로 위장하지 않는다). `client_grade_mismatch_count`는 `verifiable_count`
    행(검산이 실제로 이뤄진 행)만을 모집단으로 하고, 그중에서도 `unverifiable` verdict는
    대조 대상에서 제외한다(acceptance② — 판정 불가를 오답 신호로 쓰지 않는다).
    """

    total_attempts: int
    not_derivable_count: int
    verifiable_count: int  # == total_attempts - not_derivable_count
    # {"pass": n, "fail": n, "unverifiable": n}
    verdict_counts: dict[str, int] = field(default_factory=dict)
    client_grade_mismatch_count: int = 0

    @property
    def mismatch_rate(self) -> float | None:
        """불일치율(검산 가능 표본 대비). 표본 0이면 `None`(분모 없는 0 금지)."""
        if self.verifiable_count == 0:
            return None
        return self.client_grade_mismatch_count / self.verifiable_count

    @property
    def unverifiable_rate(self) -> float | None:
        """unverifiable 비율 — 이 기능의 *실효 커버리지*(§4 D2). 표본 0이면 `None`."""
        if self.verifiable_count == 0:
            return None
        return self.verdict_counts.get("unverifiable", 0) / self.verifiable_count

    def to_json(self) -> dict[str, Any]:
        return report_to_json(self)


def build_report(records: list[AttemptRecord]) -> ShadowGradingReport:
    """attempt 레코드 목록 → `ShadowGradingReport`(순수·부작용 0).

    각 레코드에 대해:
      1. `problem`이 없으면 `not_derivable`(FK 고아·문제 삭제).
      2. `grade_attempt`가 `None`이면 `not_derivable`(파생 실패 또는 student_answer 없음).
      3. 그 외 verdict(`pass`/`fail`/`unverifiable`)를 `verdict_counts`에 누적하고,
         verdict가 `unverifiable`이 *아니고* `client_is_correct`가 제출돼 있으면 클라 보고
         (`is_correct`)와 서버 판정(`verdict.state == "pass"`)을 대조해 불일치를 센다.
         `client_is_correct`가 `None`(레거시 미채점 행)이면 verdict는 집계하되 대조는
         건너뛴다(비교 불능 — mismatch로도 non-mismatch로도 세지 않는다).
    """
    total = len(records)
    not_derivable = 0
    verdict_counts: dict[str, int] = {"pass": 0, "fail": 0, "unverifiable": 0}
    mismatch = 0

    for record in records:
        if record.problem is None:
            not_derivable += 1
            continue
        verdict = grade_attempt(record.problem, record.student_answer)
        if verdict is None:
            not_derivable += 1
            continue
        verdict_counts[verdict.state] = verdict_counts.get(verdict.state, 0) + 1
        if verdict.state == "unverifiable":
            # 교수학 금기(acceptance②) — 판정 불가는 판정 불가. 오답/불일치로 강등 금지.
            continue
        if record.client_is_correct is None:
            continue  # 비교 불능(레거시 미채점) — mismatch 대상 아님.
        server_says_correct = verdict.state == "pass"
        if record.client_is_correct != server_says_correct:
            mismatch += 1

    return ShadowGradingReport(
        total_attempts=total,
        not_derivable_count=not_derivable,
        verifiable_count=total - not_derivable,
        verdict_counts=verdict_counts,
        client_grade_mismatch_count=mismatch,
    )


# ──────────────────────────────────────────────────────────────────────────
# 렌더 — 사람이 읽는 마크다운 + 기계가 읽는 JSON
# ──────────────────────────────────────────────────────────────────────────
def render_report(report: ShadowGradingReport) -> str:
    """리포트를 마크다운으로 렌더(순수·입력 외 계산 없음).

    acceptance④ 리터럴 문구: 불일치는 **"검산 가능 표본 N건 중 M건"**으로 표시한다 — M이
    0이어도 분모 없는 "0건"으로 위장하지 않는다. `verifiable_count == 0`(표본 자체가 없음)은
    다른 문장으로 구분한다(둘 다 "0건"으로 뭉개면 "관측이 안 됨"과 "관측했더니 0건"이
    구별 안 된다).
    """
    lines = [
        "# 서버측 답안 채점 shadow 리포트 (NLP-02)",
        "",
        "> 관측 전용 리포트다 — BKT/숙달 전파 입력은 여전히 클라이언트 보고 `is_correct`다"
        '(권위 이관 아님·Kiki 결정 2026-07-31 "측정 없는 도입 없음").',
        "",
        f"- 총 attempt: **{report.total_attempts}**",
        f"- 파생 불가(재료 없음 — conditions/formal 미보유·다중 미지수·student_answer 없음 등): "
        f"**{report.not_derivable_count}**",
        f"- 검산 가능 표본: **{report.verifiable_count}**",
        "",
        "## 3상태 분포 (검산 가능 표본 내)",
        "",
        f"- pass: {report.verdict_counts.get('pass', 0)}",
        f"- fail: {report.verdict_counts.get('fail', 0)}",
        f"- unverifiable: {report.verdict_counts.get('unverifiable', 0)}",
        "",
        "## 클라이언트 ↔ 서버 불일치 (이중 회계)",
        "",
    ]
    if report.verifiable_count == 0:
        lines.append("- 검산 가능 표본 0건 — 불일치율 측정 불가(데이터없음, 0%로 위장하지 않음).")
    else:
        rate = report.mismatch_rate
        rate_text = f"{rate:.2%}" if rate is not None else "데이터없음"
        lines.append(
            f"- 검산 가능 표본 {report.verifiable_count}건 중 "
            f"{report.client_grade_mismatch_count}건 불일치({rate_text})."
        )
        uv_rate = report.unverifiable_rate
        uv_text = f"{uv_rate:.2%}" if uv_rate is not None else "데이터없음"
        lines.append(
            f"- unverifiable 비율(이 기능의 실효 커버리지): {uv_text} — 낮을수록 "
            '"클라이언트를 믿어도 되는가" 판단 재료가 더 신뢰할 만하다.'
        )
    lines.append("")
    return "\n".join(lines)


def report_to_json(report: ShadowGradingReport) -> dict[str, Any]:
    """리포트 → JSON 직렬화 가능 dict(분모 없는 비율은 `None` 그대로 보존)."""
    return {
        "total_attempts": report.total_attempts,
        "not_derivable_count": report.not_derivable_count,
        "verifiable_count": report.verifiable_count,
        "verdict_counts": dict(report.verdict_counts),
        "client_grade_mismatch_count": report.client_grade_mismatch_count,
        "mismatch_rate": report.mismatch_rate,
        "unverifiable_rate": report.unverifiable_rate,
    }


# ──────────────────────────────────────────────────────────────────────────
# CLI (얇은 껍데기 — DB 접속·출력만, 집계는 위 순수 코어)
# ──────────────────────────────────────────────────────────────────────────
_EXIT_OK = 0
_EXIT_INPUT_ERROR = 2


def main(argv: list[str] | None = None) -> int:
    """CLI — DB에서 attempt를 읽어 shadow 채점 리포트를 출력. **게이트가 아니다**(항상 exit 0,
    DB 접속 실패만 exit 2).

    불일치·unverifiable 비율이 얼마든 exit 0이다 — 권위 이관 여부는 이 수치를 본 사람이
    판단한다(Kiki 결정 2026-07-31 "측정 없는 도입 없음" — 이 CLI는 그 측정만 낸다).
    """
    parser = argparse.ArgumentParser(
        prog="python -m whymath_backend.harness.attempt_grading_shadow_report",
        description=(
            "POST /v1/me/attempts 적재분을 verify_answer로 shadow 재검산해 클라/서버 불일치·"
            "unverifiable 비율을 관측한다(NLP-02·관측 전용·게이트 아님)."
        ),
    )
    parser.add_argument(
        "--user-id", type=uuid.UUID, default=None, help="특정 사용자로 스코핑(선택·기본 전량)"
    )
    parser.add_argument("--limit", type=int, default=None, help="조회할 attempt 상한(선택)")
    parser.add_argument(
        "--json", dest="json_path", type=Path, default=None, help="JSON 산출물 경로(선택)"
    )
    args = parser.parse_args(argv)

    async def _run() -> ShadowGradingReport:
        # lazy import — CLI를 실제로 실행할 때만 DB 세션 팩토리를 물게 한다(다른 함수의
        # 모듈 top-level import는 순수 유지).
        from whymath_backend.db.session import get_session

        async for session in get_session():
            records = await fetch_attempt_records(session, user_id=args.user_id, limit=args.limit)
            return build_report(records)
        raise RuntimeError("DB 세션을 얻지 못함")  # pragma: no cover — get_session은 항상 1회 yield

    try:
        report = asyncio.run(_run())
    except Exception as exc:  # noqa: BLE001 — DB 접속 실패 등은 타입명과 함께 보고 후 exit 2
        print(f"입력/접속 오류({type(exc).__name__}): {exc}", file=sys.stderr)
        return _EXIT_INPUT_ERROR

    print(render_report(report))
    if args.json_path is not None:
        args.json_path.parent.mkdir(parents=True, exist_ok=True)
        args.json_path.write_text(
            json.dumps(report_to_json(report), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(f"JSON 산출물: {args.json_path}")
    return _EXIT_OK


if __name__ == "__main__":  # pragma: no cover — 엔트리포인트
    sys.exit(main())
