"""개념형(개수/판정) 수치평가 객관식 스켈레톤 생성기 — 개수/판정 검증 축(결정론·LLM 0).

수치평가 MC(`misconception_eval_mc_generator`)의 개념형 형제다. 답이 *값*이 아니라 *개수/판정*(실근
개수·극값 개수·일대일 여부·등비급수 수렴 여부)인 문항을 낸다 — 이 답은 게이트가 SymPy로 *독립
계산*해 검증(`verify_real_root_count`·`verify_extremum_count`·`verify_is_one_to_one`·
`verify_geometric_convergence`)하므로 오개념의 틀린 답은 fail한다(진짜 개념 검증). 겨누는 오개념:
  - `real_root_count`: 판별식을 무시해 "이차방정식은 늘 두 실근"으로 오인(discriminant-negative-
    no-real-root) — 실근 0/1개인데 2로 답한다.
  - `extremum_count`: 임계점(f'=0)을 곧 극값으로 오인(critical-point-implies-extremum) — f(x)=(x-a)³
    은 임계점 1개(x=a)이나 극값 0개인데 1로 답한다.
  - `is_one_to_one`: "일대일 아니어도 역함수가 있다"고 오인(invertibility-without-1-1) — 포물선은
    일대일이 아니라 0인데 1로 답한다.
  - `geometric_convergence`: "등비급수는 늘 수렴한다"고 오인(geometric-series-always-converges) —
    |r|>1은 발산(0)인데 1로 답한다.

`CandidateProblem`에 `answer_kind`를 담고 `answer_map={}`(개수/판정은 근 대입 아님)로 오케스트레이터
·수용 게이트·저장 sink를 재사용한다. 오답 선지 오개념 id는 생성자 `distractor_codes`로 주입받는다
(L4 하드코딩 0·계층 규칙). 산출물은 v0(사람 검수 전) — 게이트 통과 ≠ 학생 노출.
"""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import Mapping, Sequence
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from math import gcd
from typing import Literal

from whymath_backend.l1.problem_bank.populate import ConceptTag
from whymath_backend.l3.equivalent.acceptance import EquivalenceSpec
from whymath_backend.l3.equivalent.canonicalize import canonical_signature
from whymath_backend.l3.equivalent.generator import CandidateProblem
from whymath_backend.schema.enums import (
    AnswerFormat,
    Curriculum,
    GenerationType,
    LicenseType,
    QuestionFormat,
    SourceType,
    Subject,
)
from whymath_backend.schema.problem import DistractorEntry, Problem
from whymath_backend.schema.provenance import ContentProvenance

__all__ = [
    "ConceptualCountMCSkeletonGenerator",
    "CountTemplateKind",
]

CountTemplateKind = Literal[
    "real_root_count",
    "extremum_count",
    "is_one_to_one",
    "geometric_convergence",
    "limit_equals_value",
    "is_differentiable",
    "series_converges",
]

# 개수/판정 선지 — 4지선다는 항상 {0,1,2,3}. 판정형(일대일·수렴·극한=함숫값·미분가능)은 0/1을 쓴다.
_COUNT_CHOICES: tuple[str, str, str, str] = ("0", "1", "2", "3")

# 템플릿별 L1 메타(개념 원천 src_id·단원 코드). 성취기준 코드는 spec이 공급.
_TEMPLATE_META: dict[CountTemplateKind, tuple[str, str]] = {
    "real_root_count": ("HK07", "DISC-COUNT"),
    "extremum_count": ("H:12미적Ⅰ02-01", "EXTREMUM-COUNT"),
    "is_one_to_one": ("10기수2-03-03", "FUNC-INVERSE"),
    "geometric_convergence": ("H:12미적Ⅱ01-05", "GEO-SERIES-CONV"),
    "limit_equals_value": ("H:12미적Ⅰ01-01", "LIMIT-VALUE"),
    "is_differentiable": ("H:12미적Ⅰ02-02", "DIFFERENTIABILITY"),
    "series_converges": ("H:12미적Ⅱ01-04", "SERIES-CONV"),
}


@dataclass(frozen=True, slots=True)
class _CountItem:
    """개수형 MC 뼈대 — conditions·answer_kind·정답 개수·오개념 개수(수치의 단일 진실 원천)."""

    conditions: str
    answer_kind: CountTemplateKind
    answer_str: str  # 정답 개수(문자열)
    misc_str: str  # 오개념 개수(문자열)
    question_text: str
    answer_explanation: str
    difficulty: float


def _difficulty(seed: int) -> float:
    """종합 난이도를 [2.5, 3.5] 밴드에 결정론 분산 — spec 난이도 3.0·tol 0.5 안이라 동등성 만점."""
    return round(2.5 + (seed % 11) * 0.1, 1)


def _build_real_root_count_pool() -> tuple[_CountItem, ...]:
    """이차방정식 x²+bx+c=0 의 서로 다른 실근 개수 뼈대 풀 — 판별식 ≤ 0(실근 0/1)만.

    오개념(판별식 무시·늘 2근)이 *틀린 답*을 주는 경우만 낸다: 판별식<0(실근 0)·판별식=0(중근·실근
    1). 정답 0 또는 1·오개념 오답은 항상 2. b²-4c≤0 되도록 (b,c) 순회. conditions dedup(같은 이차식
    구조 signature 공유 방지는 오케스트레이터가 kind payload로 처리).
    """
    pool: list[_CountItem] = []
    seen: set[str] = set()
    for b in range(0, 8):
        for c in range(1, 18):
            disc = b * b - 4 * c
            if disc > 0:
                continue  # 실근 2개 → 오개념이 우연히 정답(무의미) → 제외.
            correct = 1 if disc == 0 else 0  # 판별식=0 중근(1개)·<0 실근 없음(0개).
            conditions = f"x**2 + {b}*x + {c} = 0" if b else f"x**2 + {c} = 0"
            if conditions in seen:
                continue
            seen.add(conditions)
            b_disp = f" + {b}x" if b else ""
            pool.append(
                _CountItem(
                    conditions=conditions,
                    answer_kind="real_root_count",
                    answer_str=str(correct),
                    misc_str="2",
                    question_text=(
                        f"이차방정식 x^2{b_disp} + {c} = 0 의 서로 다른 실근의 개수를 구하시오."
                    ),
                    answer_explanation=(
                        f"판별식 D = {b}^2 - 4·{c} = {disc} 이므로 "
                        + (
                            "중근을 가져 서로 다른 실근은 1개"
                            if disc == 0
                            else "실근이 없다(0개)"
                        )
                        + ". 판별식을 무시하고 늘 2근이라 답하면 틀린다."
                    ),
                    difficulty=_difficulty(b + c),
                )
            )
    return tuple(pool)


def _build_extremum_count_pool() -> tuple[_CountItem, ...]:
    """삼차함수 f(x)=(x-a)³+c 의 극값 개수 뼈대 풀 — 임계점 1개이나 극값 0개(오개념 정확 표적).

    f'(x)=3(x-a)²는 x=a에서만 0이나 부호가 안 바뀌어(항상 ≥0) 극값이 없다. 정답 0·오개념 오답은
    임계점 개수 1. (a,c) 순회·conditions dedup. 오개념(임계점=극값)이 틀린 답 1을 주는 정확한 유형.
    """
    pool: list[_CountItem] = []
    seen: set[str] = set()
    for a in range(1, 7):
        for c in range(0, 6):
            conditions = f"(x - {a})**3 + {c}" if c else f"(x - {a})**3"
            if conditions in seen:
                continue
            seen.add(conditions)
            c_disp = f" + {c}" if c else ""
            pool.append(
                _CountItem(
                    conditions=conditions,
                    answer_kind="extremum_count",
                    answer_str="0",
                    misc_str="1",
                    question_text=(
                        f"삼차함수 f(x) = (x - {a})^3{c_disp} 의 극값의 개수를 구하시오."
                    ),
                    answer_explanation=(
                        "도함수가 완전제곱 꼴이라 한 점에서만 0이 되고 그 좌우로 부호가 바뀌지 "
                        "않으므로 극값이 없다 — 극값은 0개다. 도함수가 0인 임계점을 곧 극값으로 "
                        "여기면 1로 잘못 답한다."
                    ),
                    difficulty=_difficulty(a + c),
                )
            )
    return tuple(pool)


def _build_is_one_to_one_pool() -> tuple[_CountItem, ...]:
    """f(x)=x²+bx+c 가 ℝ에서 일대일대응인지 뼈대 풀 — 포물선은 늘 일대일 아님(오개념 정확 표적).

    이차함수 f'(x)=2x+b는 x=-b/2에서 부호가 바뀌므로(꼭짓점 좌우 단조 반전) f는 일대일이 아니다 —
    정답 0. "일대일이 아니어도 역함수가 있다"는 오개념(invertibility-without-1-1)은 1로 답해 fail.
    단항식(a=1·monic)으로 두어 정준 signature 충돌을 피하고(상수 c가 signature를 갈라줌), (b,c)
    순회. 상수항은 일대일 여부를 바꾸지 않는다(여전히 0). 답은 판정값(0/1)이라 SymPy 독립 검증.
    """
    pool: list[_CountItem] = []
    seen: set[str] = set()
    for b in range(0, 5):
        for c in range(0, 6):
            terms = "x**2"
            if b:
                terms += f" + {b}*x"
            if c:
                terms += f" + {c}"
            conditions = terms
            if conditions in seen:
                continue
            seen.add(conditions)
            b_disp = f" + {b}x" if b else ""
            c_disp = f" + {c}" if c else ""
            pool.append(
                _CountItem(
                    conditions=conditions,
                    answer_kind="is_one_to_one",
                    answer_str="0",
                    misc_str="1",
                    question_text=(
                        f"함수 f(x) = x^2{b_disp}{c_disp} 가 실수 전체에서 일대일대응이면 1, "
                        "아니면 0을 쓰시오."
                    ),
                    answer_explanation=(
                        "이차함수는 꼭짓점을 기준으로 증가·감소가 뒤바뀌어 서로 다른 두 x가 같은 "
                        "값을 가지므로 일대일대응이 아니다 — 0이다. 일대일이 아니어도 역함수가 "
                        "있다고 오인하면 1로 잘못 답한다."
                    ),
                    difficulty=_difficulty(b + c),
                )
            )
    return tuple(pool)


def _build_geometric_convergence_pool() -> tuple[_CountItem, ...]:
    """공비 r=p/q(|r|>1)인 등비급수의 수렴 여부 뼈대 풀 — 발산만(오개념 정확 표적).

    |r|≥1이면 등비급수는 발산한다 — 정답 0. "등비급수는 늘 수렴한다"는 오개념(geometric-series-
    always-converges)은 1로 답해 fail. 기약분수 p/q(p>q≥1) 순회·conditions dedup. 답은 판정값(0/1)
    이라 answer_kind=geometric_convergence로 SymPy 독립 검증.
    """
    pool: list[_CountItem] = []
    seen: set[str] = set()
    for q in range(1, 5):
        for p in range(q + 1, q + 11):
            if gcd(p, q) != 1:
                continue
            conditions = f"{p}/{q}"
            if conditions in seen:
                continue
            seen.add(conditions)
            r_disp = f"{p}/{q}" if q != 1 else f"{p}"
            pool.append(
                _CountItem(
                    conditions=conditions,
                    answer_kind="geometric_convergence",
                    answer_str="0",
                    misc_str="1",
                    question_text=(
                        f"공비가 r = {r_disp} 인 등비급수가 수렴하면 1, 발산하면 0을 쓰시오."
                    ),
                    answer_explanation=(
                        f"등비급수는 |r| < 1 일 때만 수렴하는데 r = {r_disp} 는 |r| > 1 이므로 "
                        "발산한다 — 0이다. 등비급수가 늘 수렴한다고 오인하면 1로 잘못 답한다."
                    ),
                    difficulty=_difficulty(p + q),
                )
            )
    return tuple(pool)


def _build_limit_equals_value_pool() -> tuple[_CountItem, ...]:
    """유리식 f(x)=(x−a)(x−b)/(x−a)의 x=a에서 lim=f(a) 여부 뼈대 풀 — 제거가능 특이점(오개념 표적).

    x=a에서 분자·분모가 함께 0(0/0)이라 함수값은 미정의이나 극한은 유한(b−a 방향)이라 lim ≠ f(a) —
    정답 0. "극한값은 늘 함수값과 같다"는 오개념(limit-equals-function-value)은 1로 답해 fail. 자동
    약분을 막으려 **분자는 전개형** x²−(a+b)x+ab로 낸다(약분되면 특이점 소멸). (a,b≠a) 순회.
    """
    pool: list[_CountItem] = []
    seen: set[str] = set()
    for a in range(1, 7):
        for b in range(1, 7):
            if b == a:
                continue  # a=b면 중근이라 극한도 특이(0 or ∞)·표적 아님.
            s, p = a + b, a * b
            conditions = f"(x**2 - {s}*x + {p})/(x - {a})"
            if conditions in seen:
                continue
            seen.add(conditions)
            pool.append(
                _CountItem(
                    conditions=conditions,
                    answer_kind="limit_equals_value",
                    answer_str="0",
                    misc_str="1",
                    question_text=(
                        f"함수 f(x) = (x^2 - {s}x + {p}) / (x - {a}) 에서 "
                        f"lim(x→{a}) f(x) = f({a}) 가 성립하면 1, 아니면 0을 쓰시오."
                    ),
                    answer_explanation=(
                        f"x = {a} 에서 분자·분모가 함께 0이 되어 함수값 f({a})는 정의되지 않지만 "
                        f"약분하면 극한값은 {b - a}로 유한하다 — 극한값과 함수값이 달라 0이다. "
                        "극한값이 늘 함수값과 같다고 오인하면 1로 잘못 답한다."
                    ),
                    difficulty=_difficulty(a + b),
                )
            )
    return tuple(pool)


def _build_is_differentiable_pool() -> tuple[_CountItem, ...]:
    """f(x)=|x−a|+c 가 ℝ에서 미분가능한지 뼈대 풀 — 절댓값 꺾인점(연속이나 미분불가·오개념 표적).

    x=a에서 좌·우 미분계수가 −1·+1로 달라 미분 불가(연속은 성립) — 정답 0. "연속이면 미분가능"이라는
    오개념(continuity-implies-differentiability)은 1로 답해 fail. (a,c) 순회·conditions dedup.
    """
    pool: list[_CountItem] = []
    seen: set[str] = set()
    for a in range(1, 7):
        for c in range(0, 5):
            conditions = f"Abs(x - {a}) + {c}" if c else f"Abs(x - {a})"
            if conditions in seen:
                continue
            seen.add(conditions)
            c_disp = f" + {c}" if c else ""
            pool.append(
                _CountItem(
                    conditions=conditions,
                    answer_kind="is_differentiable",
                    answer_str="0",
                    misc_str="1",
                    question_text=(
                        f"함수 f(x) = |x - {a}|{c_disp} 가 실수 전체에서 미분가능하면 1, "
                        "아니면 0을 쓰시오."
                    ),
                    answer_explanation=(
                        f"x = {a} 에서 좌미분계수 −1·우미분계수 +1로 서로 달라 미분가능하지 않다 "
                        "(연속이기는 하다) — 0이다. 연속이면 곧 미분가능하다고 오인하면 1로 잘못 "
                        "답한다."
                    ),
                    difficulty=_difficulty(a + c),
                )
            )
    return tuple(pool)


def _build_series_converges_pool() -> tuple[_CountItem, ...]:
    """일반항 a_n→0이나 급수가 발산하는 뼈대 풀 — 조화형·p<1(오개념 정확 표적).

    일반항이 0에 수렴해도 Σa_n은 발산할 수 있다(조화급수 Σ1/n·Σ1/√n) — 정답 0. "일반항이 0이면
    급수도 수렴"이라는 오개념(term-to-zero-implies-convergence)은 1로 답해 fail. 두 발산 계열
    (1/(n+c)·1/√(n+c)) 순회·conditions dedup. 모두 일반항→0이라 오개념이 정확히 틀린 유형이다.
    """
    pool: list[_CountItem] = []
    seen: set[str] = set()
    for c in range(0, 15):
        for form in (
            f"1/(n + {c})" if c else "1/n",
            f"1/sqrt(n + {c})" if c else "1/sqrt(n)",
        ):
            conditions = form
            if conditions in seen:
                continue
            seen.add(conditions)
            disp = form.replace("sqrt", "√").replace("*", "")
            pool.append(
                _CountItem(
                    conditions=conditions,
                    answer_kind="series_converges",
                    answer_str="0",
                    misc_str="1",
                    question_text=(
                        f"일반항이 a_n = {disp} 인 급수 Σa_n 이 수렴하면 1, 발산하면 0을 쓰시오."
                    ),
                    answer_explanation=(
                        "일반항은 0에 수렴하지만 이 급수는 발산한다(조화급수류) — 0이다. 일반항이 "
                        "0에 수렴하면 급수도 수렴한다고 오인하면 1로 잘못 답한다."
                    ),
                    difficulty=_difficulty(c),
                )
            )
    return tuple(pool)


_POOL_FACTORY = {
    "real_root_count": _build_real_root_count_pool,
    "extremum_count": _build_extremum_count_pool,
    "is_one_to_one": _build_is_one_to_one_pool,
    "geometric_convergence": _build_geometric_convergence_pool,
    "limit_equals_value": _build_limit_equals_value_pool,
    "is_differentiable": _build_is_differentiable_pool,
    "series_converges": _build_series_converges_pool,
}


class ConceptualCountMCSkeletonGenerator:
    """개념형 개수/판정 객관식 결정론 스켈레톤 생성기 — `EquivalentProblemGenerator` 좌석(LLM 0).

    `template`(real_root_count/extremum_count/is_one_to_one/geometric_convergence)이 수학 실체를,
    `distractor_codes`가 오답 선지의 오개념 id를 정한다(L4 하드코딩 0·계층 규칙). 각 문항은 오답
    1건만 태깅(filler 미태깅). 풀을 순서대로 소비(소진 시 None). `skip_signatures`로 기존 구조
    건너뜀.
    """

    def __init__(
        self,
        template: CountTemplateKind,
        distractor_codes: Mapping[str, tuple[str, str | None]],
        *,
        skip_signatures: AbstractSet[str] | None = None,
        slug_prefix: str = "wm-count-mc",
        subject: Subject = Subject.공통,
        curriculum_version: Curriculum = Curriculum.REVISION_2022,
        valid_from_year: int = 2022,
        concept_relevance: float = 0.95,
    ) -> None:
        if template not in _POOL_FACTORY:
            raise ValueError(
                f"미지원 template: {template!r} (real_root_count/extremum_count/"
                "is_one_to_one/geometric_convergence)"
            )
        if not distractor_codes:
            raise ValueError(
                "distractor_codes 주입 누락 — 오개념 오답 태깅용 id가 필요하다."
            )
        self._misconception_id, self._op_code = next(iter(distractor_codes.values()))
        self._template: CountTemplateKind = template
        self._pool = _POOL_FACTORY[template]()
        self._index = 0
        self._skip = skip_signatures
        self._slug_prefix = slug_prefix
        self._subject = subject
        self._curriculum_version = curriculum_version
        self._valid_from_year = valid_from_year
        concept_src_id, unit_code = _TEMPLATE_META[template]
        self._unit_codes = [unit_code]
        self._concept_tags = [
            ConceptTag(
                concept_src_id=concept_src_id,
                role="PRIMARY",
                relevance=concept_relevance,
            )
        ]

    def generate(self, spec: EquivalenceSpec) -> CandidateProblem | None:
        """다음 뼈대를 후보로 조립 — skip 집합에 있는 구조는 건너뛰고, 풀 소진 시 None."""
        while self._index < len(self._pool):
            item = self._pool[self._index]
            self._index += 1
            if self._skip is not None:
                signature = canonical_signature(
                    item.conditions, f"kind:{item.answer_kind}"
                )
                if signature is not None and signature in self._skip:
                    continue
            return self._assemble(spec, item)
        return None

    def _assemble(self, spec: EquivalenceSpec, item: _CountItem) -> CandidateProblem:
        standard_codes = sorted(spec.achievement_standard_codes)
        slug = self._stable_slug(item.question_text, item.answer_str, standard_codes)
        misc_index = _COUNT_CHOICES.index(item.misc_str)

        distractor_map = [
            DistractorEntry(
                choice_index=misc_index,
                misconception_id=self._misconception_id,
                op_code=self._op_code,
            )
        ]
        problem = Problem(
            problem_id=uuid.uuid5(uuid.NAMESPACE_URL, f"whymath:problem:{slug}"),
            slug=slug,
            source_type=SourceType.자체생성,
            curriculum_version=self._curriculum_version,
            valid_from_year=self._valid_from_year,
            subject=self._subject,
            unit_codes=list(self._unit_codes),
            difficulty_overall=item.difficulty,
            question_format=QuestionFormat.객관식,
            answer_format=AnswerFormat.자연수,  # 개수는 비음 정수.
            achievement_standard_codes=standard_codes,
            question_text=item.question_text,
            choices=list(_COUNT_CHOICES),
            answer=item.answer_str,
            answer_explanation=item.answer_explanation,
            distractor_map=distractor_map,
        )
        provenance = ContentProvenance(
            generation_type=GenerationType.FULLY_GENERATED,
            license=LicenseType.WHYMATH_GENERATED,
            original_source=None,
            transformation_pipeline={
                "steps": [
                    "결정론 개념형 개수 MC 스켈레톤 조립(실근/극값 개수 4지선다·오개념 개수 태깅)",
                    "S2-a 수용 게이트(개수 SymPy 독립 검증)",
                    "사람 검수 큐(오개념 귀속 교수학 검수)",
                ],
            },
        )
        return CandidateProblem(
            problem=problem,
            provenance=provenance,
            conditions=item.conditions,
            answer_map={},  # 개수는 근 대입 아님 — 게이트가 answer_kind로 독립 계산.
            answer_selection=None,
            answer_aggregate=None,
            answer_kind=item.answer_kind,
            solution_steps=None,
            concept_tags=list(self._concept_tags),
        )

    def _stable_slug(
        self, question_text: str, answer: str, codes: Sequence[str]
    ) -> str:
        """결정론 안정 slug — 내용 해시(멱등 upsert 키)."""
        payload = "|".join([question_text, answer, ",".join(sorted(codes))])
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]
        return f"{self._slug_prefix}-{digest}"
