"""L6 평가 청사진(blueprint) 기반 테스트셋 조립 — 선언 명세 → 세트 조립·총점 회계.

설계 정본: `assessment_module_gap_review.md` §3 D4(평가 blueprint — 총괄평가 세트 조립 +
배점·세트 채점). 갭은 "시험지 구조가 전량 0이고 `points` 소비처가 0이라 총점 계산이 불가"였다.

**파일명이 `gating.py`가 아닌 이유**: 다른 L6 모드(`retake`·`suneung`·`school_progress`·
`thinking`·`metacognition`·`gifted`)는 전부 "이 문항을 이 학생에게 노출해도 되는가"를 판정하는
*게이팅*이라 `<모드>/gating.py`다. 이 모듈은 판정이 아니라 **선언 명세를 만족하는 문항 집합을
조립(assembly)**하는 것이 본질이라 `assembly.py`로 둔다(디렉터리-1파일 구조는 동일 답습).
후보 적격 판정은 여기서 새로 만들지 않고 L6 공용 게이트(`_shared`) 두 축을 그대로 호출한다.

────────────────────────────────────────────────────────────────────────────
CAT vs blueprint — 역할 분담 동결(D4-2·이 모듈의 존재 조건)
────────────────────────────────────────────────────────────────────────────
학습 중 문항 노출의 **정본은 CAT 단건**(`GET /v1/me/next-problem`)이다. 적응적 단건 선택이
정보량을 최대화하고 그것이 WhyMath의 정체성(사고력·메타인지 코칭)과 맞기 때문이다. 이 모듈이
만드는 *세트*는 CAT을 **대체하지 않는다** — `BLUEPRINT_USE_CASE`가 선언하는 단 하나의 용도,
**"단원 마감 측정"** 예외에만 쓴다. 이 경계는 주석뿐 아니라 테스트로 동결한다
(`tests/backend/l6/blueprint/test_assembly.py`의 CAT 경계 테스트 — `/next-problem` 핸들러
소스가 이 모듈을 참조하지 않음을 기계로 확인).

────────────────────────────────────────────────────────────────────────────
정직 회계 3원칙(CLAUDE.md 날조 금지·침묵 실패 금지의 이 모듈 구체화)
────────────────────────────────────────────────────────────────────────────
① **배점(`points`)** — 2026-08-10 실측 기준 코퍼스 2,647건이 **전량 `points=NULL`**이다.
   따라서 NULL을 0으로 접어 총점을 만들면 *가짜 총점*이 된다. 조립 결과는 배점을 두 축으로
   나눠 회계한다: `declared_total_points`(청사진이 *선언한* 배점 합)와
   `corpus_total_points`(선택된 문항의 실제 `points` 합). 후자는 미부여가 하나라도 섞이면
   **`None`** 이고 `points_missing_count`로 몇 건이 미부여인지 함께 보고한다.
② **시험시간** — `Problem`에 `estimated_time` 류 필드가 **없다**(2026-08-10 실측). 문항별
   소요시간을 추정해 채우지 않는다. 청사진이 선언한 총 시험시간(`time_limit_minutes`)을
   메타로 *보존만* 한다(문항별 배분·예측 없음).
③ **부족(shortfall)** — 요구 문항 수보다 적격 후보가 적으면 **조용히 부족한 세트를 돌려주지
   않는다**. `satisfied=False` + 셀별 `shortfall` + `unsatisfied_reasons`로 실패를 명시한다
   (호출자(api)는 이때 `Assessment` 행을 적재하지 않는다).

────────────────────────────────────────────────────────────────────────────
레이어 규칙(CLAUDE.md 7계층)
────────────────────────────────────────────────────────────────────────────
L6 → L1(`schema.problem`·`schema.enums`)·L6 공용(`l6._shared`)·L3(`l3.verify_solution`·
`l3.verify_step`)만 의존한다. L3 의존은 **부분점수 재사용** 때문이다 — 신규 채점기를 만들지
않고 기존 `verify_solution`의 `first_incorrect_index`(어느 단계까지 맞았는가)를 부분 인정
근거로 그대로 쓴다(D4-3). L6은 아무도 import하지 않는 최상위 소비자다(역방향 의존 부재).

부수효과 0·결정론(deterministic)·I/O 0·LLM 0. DB 조회·성취기준 코드 주입은 전부 호출자(L5
api) 몫이다.

반-스코프(D4 동결): 새 테이블·Alembic 마이그레이션 0(세트는 `Assessment` 행 + 문항 id 배열로
표현) · 평가원·EBS *본문* 0(저작권 게이트가 원천 차단·자체 동등문제만) · 교사용 시험지 빌더
UI·인쇄·PDF 출력 미포함(Phase 3+) · 루브릭·서술형 채점 미포함 · 성취수준 A~E·백분위·석차 0.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable, Sequence
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from whymath_backend.l3.verify_solution import SolutionVerificationResult
from whymath_backend.l3.verify_step import VerifyStepResult, VerifyStepState
from whymath_backend.l6 import _shared
from whymath_backend.schema.enums import QuestionFormat
from whymath_backend.schema.problem import Problem

__all__ = [
    "BLUEPRINT_USE_CASE",
    "DIFFICULTY_BAND_BOUNDS",
    "AssembledTestSet",
    "BlueprintCell",
    "CellFill",
    "DifficultyBand",
    "PartialCredit",
    "ExamBlueprint",
    "assemble_test_set",
    "blueprint_priority",
    "difficulty_band_of",
    "is_blueprint_eligible",
    "matches_cell",
    "partial_credit",
]


# ──────────────────────────────────────────────────────────────────────────
# 용도 동결 상수
# ──────────────────────────────────────────────────────────────────────────
BLUEPRINT_USE_CASE: Literal["unit_closure_measurement"] = "unit_closure_measurement"
"""이 모듈이 허용하는 **유일한 용도** — "단원 마감 측정"(D4-2).

학습 중 노출 정본은 CAT 단건(`GET /v1/me/next-problem`)이며, blueprint 세트는 그것을
대체하지 않는다. 이 상수는 문서가 아니라 *테스트가 대조하는 값*이다 — 용도가 늘어나려면
이 상수와 그 테스트를 함께 고쳐야 하므로, 무의식적 확장(세트가 CAT을 밀어내는 표류)을
막는 마찰 장치다.
"""


# ──────────────────────────────────────────────────────────────────────────
# 난이도 밴드
# ──────────────────────────────────────────────────────────────────────────
DifficultyBand = Literal["하", "중", "상"]
"""난이도 밴드 3구간 — `Problem.difficulty_overall`(1.0~5.0)의 구간 라벨.

**신규 enum을 만들지 않는다**(L6 오버레이 모델 규칙 — PG enum 추가는 곧 마이그레이션이다).
`Literal` 문자열 3종이라 스키마·DB 표면이 늘지 않는다.
"""

DIFFICULTY_BAND_BOUNDS: dict[DifficultyBand, tuple[float, float]] = {
    "하": (1.0, 2.5),
    "중": (2.5, 3.75),
    "상": (3.75, 5.0),
}
"""밴드별 `difficulty_overall` 구간 `[하한, 상한)` — 마지막 밴드만 상한 포함.

**경계값 근거의 정직한 한계**: 1.0~5.0 척도를 3등분에 가깝게 자른 *선언적* 경계이며,
실제 코퍼스 난이도 분포로 보정한 값이 **아니다**(분포 기반 재보정은 실학생 응답·문항
정답률이 쌓인 뒤 별도 후속 — `S3-01`·`S4-15` 이후). 지금 분포 기반이라고 주장하면 날조다.
"""


def difficulty_band_of(problem: Problem) -> DifficultyBand | None:
    """문항의 난이도 밴드를 판정한다 — `difficulty_overall`이 없으면 **None**(미판정).

    `difficulty_overall`이 `None`(미평가)인 문항은 어떤 밴드에도 속하지 않는다. 임의로 "중"에
    넣어 밴드 제약을 만족시키면 *날조*이므로 fail-closed로 None을 돌려준다 — 그 결과 밴드를
    지정한 셀의 후보에서 자연히 빠진다(밴드 미지정 셀에는 그대로 들어간다).

    Args:
      problem: 밴드를 판정할 문항(L1 `Problem`).

    Returns:
      `"하"`/`"중"`/`"상"` 중 하나. `difficulty_overall`이 None이면 None(미판정).
    """
    difficulty = problem.difficulty_overall
    if difficulty is None:
        return None
    for band, (low, high) in DIFFICULTY_BAND_BOUNDS.items():
        # 마지막 밴드("상")만 상한을 포함한다(5.0이 어느 밴드에도 못 들어가는 구멍 방지).
        if band == "상":
            if low <= difficulty <= high:
                return band
        elif low <= difficulty < high:
            return band
    return None


# ──────────────────────────────────────────────────────────────────────────
# 선언 명세(청사진)
# ──────────────────────────────────────────────────────────────────────────
class BlueprintCell(BaseModel):
    """청사진 한 칸 — 성취기준 × 난이도 밴드 × 문항 유형에 대한 문항 수·배점 선언.

    **"유형 비율"의 표현 방식**: 비율(0~1 실수)을 따로 두지 않고 **셀별 문항 수(`count`)로만**
    표현한다. 비율은 `count / 전체 count 합`으로 유도되며, 실수 비율을 문항 수로 되돌릴 때
    생기는 반올림 모호성(3.5문항 문제)을 원천 제거한다 — 선언이 곧 정수 문항 수다.

    세 축(`standard_code`·`difficulty_band`·`question_format`)은 전부 선택적이며, `None`은
    "이 축은 제약하지 않음"을 뜻한다(무제약). 셋 다 None이면 적격 후보 전체가 대상이다.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    standard_code: str | None = Field(
        default=None,
        description="성취기준 고시코드(예 '[10공수1-02-02]'). 문항의 "
        "`achievement_standard_codes`에 포함돼야 한다. None이면 성취기준 무제약.",
    )
    difficulty_band: DifficultyBand | None = Field(
        default=None,
        description="난이도 밴드(하/중/상). None이면 난이도 무제약. 지정하면 "
        "`difficulty_overall`이 없는 문항은 밴드 미판정이라 후보에서 빠진다(날조 방지).",
    )
    question_format: QuestionFormat | None = Field(
        default=None,
        description="문항 형식(객관식/단답형/...). None이면 형식 무제약.",
    )
    count: int = Field(
        ge=1,
        description="이 셀에서 뽑을 문항 수(정수). 유형 '비율'은 셀별 count의 비로 표현된다.",
    )
    points_per_item: int | None = Field(
        default=None,
        ge=0,
        description="이 셀 문항 1개당 *선언* 배점. 코퍼스의 `Problem.points`와 다른 축이다 "
        "— 선언 총점(`declared_total_points`) 계산에만 쓰이며 코퍼스 배점을 덮어쓰지 않는다. "
        "None이면 배점 미선언(선언 총점 산출 불가).",
    )


class ExamBlueprint(BaseModel):
    """평가 청사진 — 성취기준×난이도 밴드×유형 비율·문항 수·배점 배분·시험시간의 선언 명세.

    이 객체 하나가 "시험지가 어떻게 생겨야 하는가"의 전부다(D4-1). 조립기는 이 선언을 만족하는
    문항 집합을 *자체 동등문제 코퍼스*에서 뽑을 뿐, 선언을 스스로 완화하지 않는다.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    title: str = Field(
        min_length=1,
        max_length=200,
        description="청사진 이름(예 '2학기 중간 — 지수함수 단원 마감 측정').",
    )
    cells: list[BlueprintCell] = Field(
        min_length=1,
        description="청사진 칸 목록(선언 순서 = 조립 순서). 최소 1칸.",
    )
    time_limit_minutes: int | None = Field(
        default=None,
        ge=1,
        le=600,
        description="선언 총 시험시간(분). **메타 보존 전용** — 문항별 소요시간을 추정하지 "
        "않는다(`Problem`에 소요시간 필드가 없음·2026-08-10 실측). 조립 판정에 쓰이지 않는다.",
    )

    def total_requested_count(self) -> int:
        """청사진이 요구하는 총 문항 수 = 모든 셀 `count`의 합."""
        return sum(cell.count for cell in self.cells)


# ──────────────────────────────────────────────────────────────────────────
# 후보 적격·우선순위
# ──────────────────────────────────────────────────────────────────────────
def is_blueprint_eligible(problem: Problem) -> bool:
    """이 문항을 blueprint 세트에 담아도 되는가 — **두 축을 각각 독립된 `if`로** 확인한다.

    ① `_shared.is_exposable` — 저작권·법적 축(평가원/EBS/교과서 본문 미보유 출처 차단).
    ② `_shared.is_review_cleared` — 검수·운영 축(`review_status == approved`만 통과).

    두 축을 **절대 합치지 않는다**(PB-03 설계 핵심 — `l6/_shared.py:165` docstring 명시).
    합치면 "왜 빠졌는가"가 한 덩어리가 되어 저작권 차단과 검수 미통과를 구분할 수 없고, 한쪽
    축의 완화가 다른 축까지 조용히 열어버린다. 여기서는 그래서 `and`로 묶지 않고 순차 `if`
    두 개로 쓴다(가독성이 아니라 *분리 가능성*이 목적이다).

    Args:
      problem: 적격성을 판정할 문항(L1 `Problem`).

    Returns:
      두 축을 모두 통과하면 True, 하나라도 실패하면 False(fail-closed).
    """
    # ① 저작권·법적 축 — 본문 미보유 출처(평가원·EBS·교과서)는 학생 노출 불가.
    if not _shared.is_exposable(problem):
        return False
    # ② 검수·운영 축 — approved만 통과(None·pending·rejected 전부 차단). ①과 별개 축이다.
    if not _shared.is_review_cleared(problem):
        return False
    return True


def matches_cell(problem: Problem, cell: BlueprintCell) -> bool:
    """문항이 청사진 한 칸의 세 축 제약을 만족하는가 — 적격 게이트와는 *별개* 판정.

    각 축은 셀에서 `None`이면 무제약(항상 통과)이고, 값이 있으면 다음을 요구한다:
      - `standard_code`: 문항의 `achievement_standard_codes`에 그 코드가 포함(비영속 필드라
        L5가 원자 축 조인으로 주입한다 — 주입이 없으면 빈 리스트라 자연히 불일치).
      - `difficulty_band`: `difficulty_band_of(problem)`이 그 밴드와 같음(난이도 미평가 문항은
        밴드가 None이라 불일치 — 날조 대신 탈락).
      - `question_format`: 문항 형식이 같음(use_enum_values 대응 — 문자열로 정규화 비교).

    Args:
      problem: 대조할 문항(L1 `Problem`).
      cell: 대조 기준이 되는 청사진 칸.

    Returns:
      세 축을 모두 만족하면 True.
    """
    if (
        cell.standard_code is not None
        and cell.standard_code not in problem.achievement_standard_codes
    ):
        return False
    if cell.difficulty_band is not None and difficulty_band_of(problem) != cell.difficulty_band:
        return False
    if cell.question_format is not None:
        # use_enum_values=True 환경에서 양쪽이 enum/문자열 어느 쪽이든 같은 척도로 비교한다.
        if _shared.normalize_enum_value(problem.question_format) != _shared.normalize_enum_value(
            cell.question_format
        ):
            return False
    return True


def blueprint_priority(problem: Problem) -> float:
    """세트에 담을 우선순위 가중치(높을수록 먼저) — 결정론·부수효과 0.

    두 신호만 쓴다(적을수록 설명 가능하다):
      - **배점 보유** +2.0 — `points`가 있는 문항을 앞세운다. 이 세트의 유일한 실측 총점 축이
        `corpus_total_points`인데, 미부여가 하나라도 섞이면 그 총점이 `None`이 되기 때문이다
        (정직 회계 ①). 즉 이 가중은 "총점을 산출할 수 있는 세트"를 선호한다는 뜻이다.
        2026-08-10 현재 코퍼스는 전량 NULL이라 이 항은 *실질 무신호*지만(전 문항 동률),
        배점이 채워지는 순간 자동으로 작동한다.
      - **검수 점수** +`review_score/5.0`(0.0~1.0) — 검수 품질이 높은 문항을 약하게 앞세운다.
        `review_score`가 None이면 0.0(무신호). `is_review_cleared`(approved 여부)와 다른 축이다
        — 그쪽은 통과/차단 게이트, 이쪽은 통과한 것들 사이의 *순서*다.

    동률(같은 가중치)은 호출자가 넘긴 입력 순서를 유지한다(`assemble_test_set`의 안정정렬).

    Args:
      problem: 가중치를 계산할 문항(L1 `Problem`).

    Returns:
      우선순위 가중치(0.0 이상). 값 자체에 절대적 의미는 없고 *상대 순서*만 쓰인다.
    """
    weight = 0.0
    if problem.points is not None:
        weight += 2.0
    if problem.review_score is not None:
        weight += problem.review_score / 5.0
    return weight


# ──────────────────────────────────────────────────────────────────────────
# 조립 결과
# ──────────────────────────────────────────────────────────────────────────
class CellFill(BaseModel):
    """청사진 한 칸의 조립 결과 — 무엇을 몇 개 요구했고 몇 개를 채웠는가."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    cell_index: int = Field(ge=0, description="청사진 `cells` 배열에서의 인덱스(선언 순서).")
    requested_count: int = Field(ge=1, description="이 칸이 요구한 문항 수.")
    eligible_count: int = Field(
        ge=0,
        description="적격 게이트 2축 + 셀 제약 3축을 모두 통과한 *선택 전* 후보 수(앞 칸에서 "
        "이미 쓰인 문항은 제외한 뒤의 수). `requested_count`보다 작으면 부족이 확정된다.",
    )
    selected_problem_ids: list[uuid.UUID] = Field(
        default_factory=list,
        description="이 칸에 실제로 담긴 문항 id(우선순위 내림차순·안정정렬).",
    )
    shortfall: int = Field(
        ge=0, description="부족분 = requested_count - 실제 선택 수. 0이면 이 칸은 충족."
    )


class AssembledTestSet(BaseModel):
    """청사진 조립 결과 — 세트 + 정직한 총점·부족 회계.

    `satisfied=False`면 **이 세트를 시행용으로 쓰면 안 된다**(호출자는 적재하지 않는다).
    부분 결과(`problem_ids`)를 그대로 두는 이유는 "무엇이 얼마나 모자랐는가"를 진단하기
    위해서지, 부족한 세트를 조용히 쓰라는 뜻이 아니다(정직 회계 ③).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    title: str = Field(description="청사진 이름(그대로 전달).")
    use_case: Literal["unit_closure_measurement"] = Field(
        default=BLUEPRINT_USE_CASE,
        description="이 세트의 유일 용도 — 단원 마감 측정(CAT 대체 아님·D4-2).",
    )
    satisfied: bool = Field(
        description="모든 칸이 요구 문항 수를 채웠는가. False면 세트를 시행에 쓰면 안 된다."
    )
    problem_ids: list[uuid.UUID] = Field(
        default_factory=list,
        description="세트 전체 문항 id(칸 선언 순서 → 칸 내 우선순위 순). 중복 없음.",
    )
    cells: list[CellFill] = Field(default_factory=list, description="칸별 조립 결과.")
    requested_item_count: int = Field(ge=0, description="청사진이 요구한 총 문항 수.")
    selected_item_count: int = Field(ge=0, description="실제로 담긴 총 문항 수.")
    declared_total_points: int | None = Field(
        default=None,
        description="**선언** 총점 = Σ(칸 count × 칸 points_per_item). 배점을 선언하지 않은 "
        "칸이 하나라도 있으면 None(가짜 합산 금지).",
    )
    declared_points_missing_cells: int = Field(
        ge=0, description="`points_per_item`을 선언하지 않은 칸 수(선언 총점이 None인 이유)."
    )
    corpus_total_points: int | None = Field(
        default=None,
        description="**실측** 총점 = 선택된 문항들의 `Problem.points` 합. 배점 미부여 문항이 "
        "하나라도 섞이면 None — NULL을 0으로 접지 않는다(2026-08-10 실측: 코퍼스 2,647건 전량 "
        "points=NULL이라 현재는 사실상 항상 None).",
    )
    points_missing_count: int = Field(
        ge=0, description="선택된 문항 중 `points`가 미부여(NULL)인 건수."
    )
    time_limit_minutes: int | None = Field(
        default=None,
        description="청사진이 선언한 총 시험시간(분) — 보존만. 문항별 배분·추정 없음.",
    )
    unsatisfied_reasons: list[str] = Field(
        default_factory=list,
        description="충족 실패 사유(칸별 부족 명세). `satisfied=True`면 빈 리스트.",
    )


def assemble_test_set(
    blueprint: ExamBlueprint,
    problems: Iterable[Problem],
) -> AssembledTestSet:
    """청사진을 만족하는 테스트셋을 후보 문항에서 조립한다 — 순수·결정론·부수효과 0.

    파이프라인(`l6/suneung/gating.py:select_suneung_items` 선례 답습 — 적격 필터 → 우선순위
    내림차순 안정정렬 → 개수 절단):
      1. **적격 필터** — `is_blueprint_eligible`(저작권 축 + 검수 축 *각각*)로 후보를 거른다.
      2. **칸 순회**(선언 순서) — 각 칸에서 `matches_cell`을 만족하고 *아직 쓰이지 않은* 문항을
         모아, `blueprint_priority` 내림차순 **안정정렬**(동률은 입력 순서 보존) 후 `count`개를
         가져온다. 문항은 세트 전체에서 **중복되지 않는다**(앞 칸이 선점하면 뒷 칸 후보에서 제외).
      3. **부족 회계** — 가져온 수가 `count`보다 적으면 그 칸의 `shortfall`을 기록하고 전체
         `satisfied=False` + `unsatisfied_reasons`에 사유를 남긴다(조용한 부분 반환 금지).
      4. **총점 회계** — 선언 총점(청사진 축)과 실측 총점(코퍼스 `points` 축)을 *따로* 계산한다.
         어느 쪽이든 미부여가 섞이면 그 축은 `None`이고, 몇 건이 미부여인지 함께 보고한다.

    칸 순서가 결과를 바꾼다(앞 칸이 공유 후보를 먼저 가져간다). 이는 의도된 계약이다 — 선언
    순서가 곧 우선순위이며, 조립기가 칸 간 배분을 재최적화(백트래킹)하지 않는다. 재최적화는
    "선언대로 안 나온 이유"를 설명 불가능하게 만들기 때문이다(설명 가능성 > 충족률).

    Args:
      blueprint: 선언 명세(칸·문항 수·배점·시험시간).
      problems: 후보 문항(임의 iterable — 한 번만 순회). 호출자가 성취기준 코드를 주입해
        넘겨야 `standard_code` 축이 작동한다(비영속 필드).

    Returns:
      `AssembledTestSet` — 세트·칸별 결과·총점 2축 회계·부족 사유.
    """
    eligible = [p for p in problems if is_blueprint_eligible(p)]

    used_ids: set[uuid.UUID] = set()
    fills: list[CellFill] = []
    ordered_ids: list[uuid.UUID] = []
    selected: list[Problem] = []
    reasons: list[str] = []

    for index, cell in enumerate(blueprint.cells):
        # 이미 다른 칸이 가져간 문항은 후보에서 제외(세트 내 중복 금지).
        cell_candidates = [
            p for p in eligible if p.problem_id not in used_ids and matches_cell(p, cell)
        ]
        # 안정정렬 — 동률은 입력 순서 유지. reverse=True로 큰 가중치 우선(suneung 선례 동형).
        ranked = sorted(cell_candidates, key=blueprint_priority, reverse=True)
        picked = ranked[: cell.count]
        for problem in picked:
            used_ids.add(problem.problem_id)
            ordered_ids.append(problem.problem_id)
            selected.append(problem)

        shortfall = cell.count - len(picked)
        if shortfall > 0:
            reasons.append(
                f"cell[{index}] 부족 — 요구 {cell.count}문항, 적격 후보 "
                f"{len(cell_candidates)}문항(부족 {shortfall}문항). "
                f"제약: standard_code={cell.standard_code!r} "
                f"difficulty_band={cell.difficulty_band!r} "
                f"question_format={_shared.normalize_enum_value(cell.question_format)!r}"
            )
        fills.append(
            CellFill(
                cell_index=index,
                requested_count=cell.count,
                eligible_count=len(cell_candidates),
                selected_problem_ids=[p.problem_id for p in picked],
                shortfall=shortfall,
            )
        )

    # ── 총점 2축 회계(정직 회계 ①) ──────────────────────────────────────
    # 축A: 선언 총점 — 청사진이 칸마다 선언한 배점. 미선언 칸이 있으면 합산하지 않는다.
    declared_missing = sum(1 for cell in blueprint.cells if cell.points_per_item is None)
    declared_total: int | None = None
    if declared_missing == 0:
        declared_total = sum(
            cell.count * cell.points_per_item
            for cell in blueprint.cells
            # mypy: 위 declared_missing==0이 전 칸 non-None을 보장하지만 좁히기를 명시한다.
            if cell.points_per_item is not None
        )

    # 축B: 실측 총점 — 선택된 문항의 코퍼스 배점. NULL이 하나라도 있으면 None(0으로 접지 않는다).
    points_missing = sum(1 for p in selected if p.points is None)
    corpus_total: int | None = None
    if selected and points_missing == 0:
        corpus_total = sum(p.points for p in selected if p.points is not None)

    return AssembledTestSet(
        title=blueprint.title,
        satisfied=not reasons,
        problem_ids=ordered_ids,
        cells=fills,
        requested_item_count=blueprint.total_requested_count(),
        selected_item_count=len(ordered_ids),
        declared_total_points=declared_total,
        declared_points_missing_cells=declared_missing,
        corpus_total_points=corpus_total,
        points_missing_count=points_missing,
        time_limit_minutes=blueprint.time_limit_minutes,
        unsatisfied_reasons=reasons,
    )


# ──────────────────────────────────────────────────────────────────────────
# 부분점수 — 신규 채점기 0(기존 `verify_solution` 재사용)
# ──────────────────────────────────────────────────────────────────────────
class PartialCredit(BaseModel):
    """한 문항의 부분점수 판정 — 점수와 *왜 그 점수인지*를 함께 돌려준다.

    점수만 돌려주면 "0점"과 "판정 불가"가 구분되지 않는다(침묵 실패). 그래서 `awarded_points`가
    `None`일 때 `reason`이 그 이유를 반드시 말한다.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    awarded_points: int | None = Field(
        default=None,
        description="인정 점수. 판정 불가면 None(0점이 아니다 — reason 참조).",
    )
    credited_ratio: float | None = Field(
        default=None,
        description="인정 비율(0.0~1.0) = 첫 오류 직전까지의 전이 수 / 총 전이 수. "
        "판정 불가면 None.",
    )
    reason: Literal[
        "no_points_declared",
        "no_transitions",
        "unverifiable_prefix",
        "credited_full",
        "credited_partial",
    ] = Field(
        description="판정 사유 — 'no_points_declared'=문항 배점 미부여(코퍼스 NULL) · "
        "'no_transitions'=검증할 전이 0(단계 1개 이하) · 'unverifiable_prefix'=인정 구간에 "
        "검증 불가 전이가 있어 확언 불가 · 'credited_full'=오류 없음(전액) · "
        "'credited_partial'=첫 오류 직전까지 부분 인정.",
    )


def partial_credit(points: int | None, verification: SolutionVerificationResult) -> PartialCredit:
    """기존 `verify_solution` 결과로 부분점수를 계산한다 — **신규 채점기 0**(D4-3).

    새 채점 로직을 만들지 않고, `SolutionVerificationResult.first_incorrect_index`("어느
    단계까지 맞았는가")를 부분 인정 근거로 그대로 재사용한다. 루브릭·서술형 채점은 범위 밖이다.

    판정 순서(전부 fail-closed — 확언할 수 없으면 점수를 만들지 않는다):
      ① `points is None` → `no_points_declared`. 배점이 없으면 부분점수도 없다. 0점으로
         접으면 "배점 미부여"가 "0점 획득"으로 위장된다(정직 회계 ①의 문항 단위 판).
      ② `n_transitions == 0` → `no_transitions`. 단계가 1개 이하라 검증할 전이가 없다
         (`verify_solution`의 빈 집계 계약 — 에러가 아니라 "검증할 것이 없음").
      ③ 인정 구간(첫 오류 직전까지의 전이들)에 `unverifiable`이 하나라도 있으면
         `unverifiable_prefix`. 검증되지 않은 전이를 "맞았다"고 세면 허위 확언이다.
      ④ 오류 없음 → `credited_full`(전액). ⑤ 그 밖 → `credited_partial`(비율 × 배점).

    비율→점수 변환은 **내림**(`int(points * ratio)`)이다. 올림은 학생에게 유리해 보이지만
    검증되지 않은 부분을 점수로 바꾸는 쪽이라 택하지 않는다.

    Args:
      points: 문항 배점(`Problem.points`). None이면 미부여.
      verification: `l3.verify_solution.verify_solution`의 결과.

    Returns:
      `PartialCredit` — 점수·비율·사유.
    """
    if points is None:
        return PartialCredit(awarded_points=None, credited_ratio=None, reason="no_points_declared")
    if verification.n_transitions == 0:
        return PartialCredit(awarded_points=None, credited_ratio=None, reason="no_transitions")

    first_incorrect = verification.first_incorrect_index
    credited_steps = verification.n_transitions if first_incorrect is None else first_incorrect
    # 인정 구간 = 첫 오류 직전까지의 전이들(오류가 없으면 전체). 이 구간에 unverifiable이
    # 섞여 있으면 "여기까지 맞았다"고 확언할 수 없다(허위 확언 금지 — CLAUDE.md AI·신뢰).
    prefix: Sequence[VerifyStepResult] = verification.steps[:credited_steps]
    if any(step.state == VerifyStepState.unverifiable for step in prefix):
        return PartialCredit(awarded_points=None, credited_ratio=None, reason="unverifiable_prefix")

    ratio = credited_steps / verification.n_transitions
    if first_incorrect is None:
        return PartialCredit(awarded_points=points, credited_ratio=1.0, reason="credited_full")
    return PartialCredit(
        awarded_points=int(points * ratio),
        credited_ratio=ratio,
        reason="credited_partial",
    )
