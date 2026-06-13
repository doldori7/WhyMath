"""베이스라인 풀이율 측정 하네스 — WH-S 솔버 하네스 S0(설계 §9 S0 게이트·§5 난이도 사다리).

설계안(`docs/architecture/03b_wh_s_solver_harness.md`) §9 **S0 게이트**:
  "검증기 스택 Tier1+2 구축, **베이스라인 측정**(시드 모델의 난이도 사다리별 풀이율) →
   사다리별 풀이율 곡선 확보."
검증기 스택(Tier1 `verify_answer`·Tier2 `verify_solution`·판정 `final_verdict`)은 이미 가동
중이다. 본 모듈은 그 스택을 *문제셋*에 돌려 **난이도 사다리(§5)별 풀이율(verified 비율)**을
집계하는 하네스다 — S0 게이트의 산출물인 "사다리별 풀이율 곡선"의 구조를 제공한다.

§5 난이도 사다리(5단계·순서 의미):
  교과 기본 → 수능 준킬러 → 수능 킬러 → KMO 1차 → KMO 2차/IMO.
밴드가 올라갈수록 풀이율이 떨어지는 곡선을 측정해 시스템의 현재 풀이 능력 경계를 가늠한다.

**정직성(§5 "검증기 스택 통과 풀이만 채택"·§3 격리·R-S2 보상 해킹 차단)**:
  `solve_rate`는 *오직 verified(검증기 스택 통과)* 비율이다. unverified(판정 불가 격리)·failed
  (오답·틀린 과정)는 **미해결로 센다** — 약한 검증으로 통과를 위장하지 않는다. Tier1 단독 pass를
  풀이로 세지 않고 반드시 Tier2 전 단계 correct와 결합한 verified만 풀이로 인정한다
  (`final_verdict`의 §4 이중 체크 상속).

**결정론**: 검증기 스택(`verify_answer`/`verify_solution`)이 고정 시드라 같은 입력 항목에 같은
리포트를 낸다(재현·디버그·회귀).

**재구현 0(조합만)**: 본 모듈은 판정 로직을 *재구현하지 않는다*. `verify_answer`(Tier1)·
`verify_solution`(Tier2)·`final_verdict`(combiner)를 *그대로 호출*하고 그 등급을 밴드별·전체로
카운트·집계만 한다. 세 함수의 보수성(판정 불가 → unverified 격리·거짓 incorrect 회피)을 상속한다.

정직 스코프(범위 밖 — 후속):
  - **시드 모델 실행**(후보 풀이 *생성*·Ollama·Phaiakes9·MCTS)은 이 환경 밖·후속이다. 본 하네스는
    *이미 생성된* (문제·후보 답·후보 단계) 평가 항목(`EvalItem`)을 받아 검증·집계만 한다 — 모델
    출력의 자연 착지점이다.
  - **솔버 루프·`solution_nodes`/저장소 스키마·자기 진화·PRM·Tier3**(Lean4)도 후속이다(§9 로드맵).
  - 본 슬라이스는 *검증·집계 하네스*(오프라인 라이브러리·API 노출 0·DB 0·모델 0)만이다.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from whymath_backend.l3.verify_answer import verify_answer
from whymath_backend.l3.verify_solution import verify_solution
from whymath_backend.schema.enums import StepType
from whymath_backend.whs.verdict import final_verdict

__all__ = [
    "BandResult",
    "BaselineReport",
    "DifficultyBand",
    "EvalItem",
    "run_baseline",
]


class DifficultyBand(str, Enum):
    """WH-S 난이도 사다리 밴드 — §5 5단계(한국어 값·선언 순서가 사다리 순서).

    기존 스키마 enums에 이 *사다리 라벨*에 적합한 enum이 없어(문항 `difficulty_overall`은 1~5
    실수·`tags`는 자유 라벨) WH-S 로컬로 정의한다. 선언 순서(`교과기본`→`준킬러`→`킬러`→`KMO1차`
    →`KMO2차`)가 §5 사다리 순서이며, 밴드가 올라갈수록 풀이율이 떨어지는 곡선을 측정한다.

    str·Enum 다중상속이라 직렬화 시 한국어 값이 그대로 보존된다(`ConceptLevel` 선례).
    """

    교과기본 = "교과기본"
    """교과 기본 — 학교 진도 표준 난이도(사다리 최하단)."""

    준킬러 = "준킬러"
    """수능 준킬러 — 중상 난이도."""

    킬러 = "킬러"
    """수능 킬러 — 최상위 수능 난이도."""

    KMO1차 = "KMO1차"
    """한국수학올림피아드 1차 — 경시 입문."""

    KMO2차 = "KMO2차"
    """KMO 2차/IMO 수준 — 사다리 최상단(증명·고난도)."""


# 사다리 순서(밴드 → 인덱스) — 리포트의 밴드 정렬·곡선 x축에 쓴다(선언 순서 정본).
_BAND_ORDER: tuple[DifficultyBand, ...] = (
    DifficultyBand.교과기본,
    DifficultyBand.준킬러,
    DifficultyBand.킬러,
    DifficultyBand.KMO1차,
    DifficultyBand.KMO2차,
)


class EvalItem(BaseModel):
    """베이스라인 평가 항목 1건 — *이미 생성된* (문제·후보 답·후보 단계)(frozen·순수 데이터).

    시드 모델이 한 문제에 대해 낸 후보 풀이를 검증기 스택에 넣기 위한 입력이다(생성은 범위 밖·
    후속). `conditions`는 Tier1 답 검산용(답이 만족해야 할 원 조건)·`answer`는 후보 답 치환맵·
    `steps`는 Tier2 단계 동치 검증용 표현식 시퀀스(없으면 답만 검증)다.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    band: DifficultyBand = Field(
        description="이 항목이 속한 난이도 사다리 밴드(§5) — 밴드별 풀이율 집계 키.",
    )
    conditions: str | Sequence[str] = Field(
        description=(
            "Tier1 답 검산용 원 조건 — 후보 답이 만족해야 할 등식/부등식(단일 str) 또는 "
            "연립(Sequence[str]). `verify_answer`에 그대로 전달."
        ),
    )
    answer: Mapping[str, str] = Field(
        description="후보 답 치환맵(예 {'x':'3'}·{'x':'2','y':'1'}) — `verify_answer`에 전달.",
    )
    steps: Sequence[str] = Field(
        default=(),
        description=(
            "Tier2 단계 동치 검증용 후보 풀이 단계 표현식 시퀀스(이미 분해됨). 비우면 단계 검증 "
            "0개(전이 0)라 답(Tier1)만으로 등급이 결정된다."
        ),
    )
    step_types: Sequence[StepType] | None = Field(
        default=None,
        description=(
            "각 전이의 단계 유형(`verify_solution`에 전달·길이=len(steps)-1이어야 함). "
            "None이면 전 전이 유형 미지정."
        ),
    )
    problem_id: str | None = Field(
        default=None,
        description="추적용 문제 식별자(선택) — 집계에는 쓰이지 않고 디버그·역추적용.",
    )


class BandResult(BaseModel):
    """한 밴드(또는 전체)의 집계 결과 — 등급별 카운트 + 풀이율(frozen).

    `n` = 항목 수·`n_verified`/`n_unverified`/`n_failed` = `final_verdict` 등급별 카운트(합 = n).
    `solve_rate` = n_verified / n(§5 "검증기 스택 통과 풀이만 채택" — verified만 풀이로 인정·
    unverified/failed는 미해결). n=0이면 0.0(0 나눗셈 회피·정직한 빈 집계).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    band: DifficultyBand | None = Field(
        description="이 집계의 밴드. 전체(overall) 집계는 None(특정 밴드 아님).",
    )
    n: int = Field(
        description="이 밴드(또는 전체) 항목 수.",
    )
    n_verified: int = Field(
        description="verified 등급 항목 수(Tier1 통과 + 전 단계 correct·풀이 인정).",
    )
    n_unverified: int = Field(
        description="unverified 등급 항목 수(§3 격리·판정 불가·미해결로 셈).",
    )
    n_failed: int = Field(
        description="failed 등급 항목 수(오답 또는 틀린 과정·미해결로 셈).",
    )
    solve_rate: float = Field(
        description=(
            "풀이율 = n_verified/n(verified만 풀이로 인정·§5). unverified/failed는 미해결. "
            "n=0이면 0.0."
        ),
    )


class BaselineReport(BaseModel):
    """베이스라인 측정 리포트 — 밴드별 풀이율 + 전체 집계(frozen·S0 게이트 산출물).

    `bands`는 §5 사다리 순서(교과기본→…→KMO2차)대로 정렬되며, **항목이 0개인 밴드도 n=0으로
    포함**한다(곡선 x축이 항상 5밴드 고정 — 빈 밴드 생략 대신 명시적 0). `overall`은 전체 항목의
    등급별 집계·풀이율이다(band=None). 이 리포트가 "사다리별 풀이율 곡선"의 구조다.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    bands: list[BandResult] = Field(
        description="밴드별 집계(§5 사다리 순서·항목 없는 밴드도 n=0 포함·길이 항상 5).",
    )
    overall: BandResult = Field(
        description="전체 항목 집계(band=None) — 전체 n·등급별·풀이율.",
    )


def _grade_item(item: EvalItem) -> str:
    """한 평가 항목을 검증기 스택에 통과시켜 최종 등급 문자열을 얻는다(조합만·재구현 0).

    Tier1(`verify_answer`) + Tier2(`verify_solution`) → combiner(`final_verdict`)로 등급
    (verified/unverified/failed)을 산출한다. 세 함수의 정직성(판정 불가 → unverified 격리)을
    그대로 상속한다.
    """
    answer_verdict = verify_answer(item.conditions, item.answer)
    solution = verify_solution(item.steps, item.step_types)
    return final_verdict(answer_verdict, solution).grade


def _tally(band: DifficultyBand | None, grades: Sequence[str]) -> BandResult:
    """등급 시퀀스를 한 `BandResult`로 집계 — verified만 풀이로 셈(§5·n=0이면 solve_rate 0.0)."""
    n = len(grades)
    n_verified = sum(1 for g in grades if g == "verified")
    n_unverified = sum(1 for g in grades if g == "unverified")
    n_failed = sum(1 for g in grades if g == "failed")
    solve_rate = n_verified / n if n else 0.0
    return BandResult(
        band=band,
        n=n,
        n_verified=n_verified,
        n_unverified=n_unverified,
        n_failed=n_failed,
        solve_rate=solve_rate,
    )


def run_baseline(items: Sequence[EvalItem]) -> BaselineReport:
    """평가 항목들을 검증기 스택에 돌려 난이도 사다리별 풀이율을 집계한다 — 순수·결정론·DB 0.

    설계 §9 S0 게이트의 베이스라인 측정. 각 `EvalItem`을 `_grade_item`(verify_answer +
    verify_solution + final_verdict 조합)으로 등급화한 뒤, **밴드별·전체로 verified/unverified/
    failed를 카운트**하고 `solve_rate = verified/n`을 낸다.

    집계 규약:
      - `bands`: §5 사다리 순서(교과기본→…→KMO2차)대로 5밴드 *항상 포함*(항목 0개 밴드는 n=0·
        곡선 x축 고정). 같은 밴드의 항목들이 그 밴드 카운트에 누적된다.
      - `overall`: 전체 항목의 등급별 집계·풀이율(band=None).

    **정직성(§5·§3·R-S2)**: `solve_rate`는 *verified(검증기 스택 통과)* 비율만이다. unverified
    (판정 불가 격리)·failed(오답/틀린 과정)는 **미해결로 센다** — 보상 해킹 차단(Tier1 단독 pass를
    풀이로 위장하지 않음). 결정론: 검증기 스택이 고정 시드라 같은 items에 같은 리포트.

    엣지: 빈 items → 5밴드 전부 n=0 + overall n=0의 *빈 리포트*(에러가 아니라 정직한 빈 집계).

    범위 밖(후속): 시드 모델 실행(후보 풀이 생성·Ollama·MCTS)·솔버 루프·저장소 스키마·자기 진화.
    """
    # 밴드별 등급 버킷 초기화 — 5밴드 전부(항목 0개여도 n=0으로 리포트에 남긴다).
    per_band: dict[DifficultyBand, list[str]] = {band: [] for band in _BAND_ORDER}
    all_grades: list[str] = []

    for item in items:
        grade = _grade_item(item)
        per_band[item.band].append(grade)
        all_grades.append(grade)

    bands = [_tally(band, per_band[band]) for band in _BAND_ORDER]
    overall = _tally(None, all_grades)
    return BaselineReport(bands=bands, overall=overall)
