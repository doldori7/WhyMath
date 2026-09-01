"""교수법 렌더 어댑터 구현 5종 — 결정론·LLM=0·개념 무관.

설계 정본: `docs/architecture/03c_content_strategy_cache.md` §2.2.

같은 `ConceptDSL`이 다섯 어댑터를 통과하면 다섯 가지 화면이 나온다 — 설명 중심(DIRECT)·질문 중심
(SOCRATIC)·풀이 제시(WORKED_EXAMPLE)·문제 우선(PROBLEM_BASED)·비유 우선(ANALOGY). 콘텐츠는 하나고
방식만 갈린다.

────────────────────────────────────────────────────────────────────────────
공통 불변식 (거버넌스 테스트가 동결)
────────────────────────────────────────────────────────────────────────────
① **개념 무관**: 어떤 어댑터도 특정 개념명(일차방정식·미분·확률…)을 알지 못한다. DSL 필드를
   일반 조작할 뿐이다 → 어댑터 수는 전략 수에 비례하고 개념 수와 무관하다(조합폭발 방지).
② **결정론·LLM=0**: 같은 (dsl, ctx) → 같은 RenderedUnit. 네트워크·난수·시계 0.
③ **검증 후 노출**: 평가 재료를 렌더하면 `verify_answer`로 정답을 확인하고, 수치·수식은
   `rephrase.classify_invariance_failure`의 봉인으로 원본 보존을 확인한다. 실패는 예외가 아니라
   `validation_signal`로 표면화한다(조용한 실패 금지).
④ **한국어 조사 일치**: 이름·값 뒤 조사는 `l3/equivalent/josa.py`가 판정한다(재발명 금지).
"""

from __future__ import annotations

from whymath_backend.l3.equivalent.josa import eul_reul, eun_neun, i_ga
from whymath_backend.l3.equivalent.rephrase import classify_invariance_failure, extract_equation
from whymath_backend.l3.pregenerate.models import ValidationSignal
from whymath_backend.l3.render.adapter import RenderContext, RenderedUnit, RenderSegment
from whymath_backend.l3.render.dsl import ConceptDSL
from whymath_backend.l3.verify_answer import verify_answer
from whymath_backend.schema.enums import PedagogyStrategy

# DSL *본문*(정의·직관·예시)이 흘러들 수 있는 세그먼트 종류 — 수식 봉인 검사의 범위.
# 나머지 종류(`prompt`·`solution_step`·`heading`·`reflection`)는 어댑터가 평가 재료나 고정 문구로
# 조립하므로 본문 수식을 싣지 않는다. SOCRATIC이 예시 본문을 `question`에 실으므로 question은 포함.
_BODY_SEGMENT_KINDS: frozenset[str] = frozenset({"definition", "intuition", "example", "question"})


def _substitute(text: str, bindings: dict[str, str]) -> str:
    """light render 치환 — `{name}` 자리를 bindings 값으로 바꾼다(없는 키는 그대로 둔다).

    `str.format`을 쓰지 않는 이유: 본문에 LaTeX 중괄호(`\\frac{a}{b}`)가 흔해 format이 KeyError로
    깨진다. 명시 치환만 수행해 수식을 건드리지 않는다.
    """
    rendered = text
    for key, value in bindings.items():
        rendered = rendered.replace("{" + key + "}", value)
    return rendered


def _seal_signal(dsl: ConceptDSL, segments: tuple[RenderSegment, ...]) -> ValidationSignal | None:
    """수식 봉인 검사 — DSL 본문의 수식이 렌더 후에도 바이트 동일하게 남았는지.

    DSL 자유 서술에서 방정식을 추출해(`extract_equation`), 그 수식을 실은 세그먼트가 봉인을
    지켰는지 `classify_invariance_failure`로 판정한다(단일 진실 원천 재사용). 추출할 수식이
    없으면 검사 대상이 아니다(None=통과).

    **검사 대상은 DSL *본문*을 실을 수 있는 세그먼트뿐이다**(`_BODY_SEGMENT_KINDS`). `prompt`·
    `solution_step`은 어느 어댑터에서도 평가 재료(`assessment.conditions`/`answer_map`)에서만
    조립되므로 DSL 본문 수식을 실을 리가 없다. 그런데 그 세그먼트들은 조건식 때문에 `=`를
    포함해 캐리어 조건(`"=" in seg.content`)에 걸리고, 그러면 *다른 출처*의 수식이 없다는
    이유로 EQUATION_ALTERED가 뜬다 — 봉인이 잡으려던 위반(본문 수식 변형)이 아니라 오탐이다.
    kind로 범위를 좁히는 것이 봉인을 *약화*시키지 않는 이유가 이것이다(본문이 흘러드는 kind는
    그대로 검사한다).
    """
    sources = [text for text in (dsl.definition, dsl.intuition) if text] + list(dsl.examples)
    for source in sources:
        equation = extract_equation(source)
        if equation is None:
            continue
        carriers = [
            seg
            for seg in segments
            if seg.kind in _BODY_SEGMENT_KINDS and (equation in seg.content or "=" in seg.content)
        ]
        for seg in carriers:
            reason = classify_invariance_failure(seg.content, equation=equation)
            if reason is not None:
                return ValidationSignal(
                    kind="other",
                    reason=f"render seal violation ({reason}) in segment kind={seg.kind}",
                )
    return None


def _assessment_signal(dsl: ConceptDSL) -> ValidationSignal | None:
    """평가 재료 정답 검증 — 렌더에 실린 답이 조건을 만족하는지(Tier1 SymPy).

    `verify_answer`는 pass/fail/unverifiable 3-state다. **fail만 차단**한다 — unverifiable(기호적
    판정 불가)은 거짓 신호를 만들지 않기 위해 통과시키되, 상위 검증(Tier2·PRM)이 남는다.
    """
    if dsl.assessment is None:
        return None
    verdict = verify_answer(list(dsl.assessment.conditions), dsl.assessment.answer_map)
    if verdict.state == "fail":
        return ValidationSignal(
            kind="solution",
            reason=f"assessment answer failed verification: {verdict.reason}",
        )
    return None


def _validate(dsl: ConceptDSL, segments: tuple[RenderSegment, ...]) -> ValidationSignal | None:
    """렌더 산출 검증 파이프 — 봉인 → 평가 정답. 먼저 걸린 신호를 돌려준다(통과=None)."""
    return _seal_signal(dsl, segments) or _assessment_signal(dsl)


def _finish(
    strategy: PedagogyStrategy,
    dsl: ConceptDSL,
    segments: list[RenderSegment],
) -> RenderedUnit:
    """세그먼트 열을 검증해 RenderedUnit으로 봉한다(모든 어댑터 공통 종결부)."""
    frozen = tuple(segments)
    return RenderedUnit(
        strategy=strategy,
        dsl_code=dsl.code,
        segments=frozen,
        validation_signal=_validate(dsl, frozen),
    )


class DirectAdapter:
    """직접교수 — 정의를 앞세워 설명하고 예시로 굳힌다."""

    @property
    def strategy(self) -> PedagogyStrategy:
        return PedagogyStrategy.DIRECT

    def can_render(self, dsl: ConceptDSL) -> bool:
        # 설명할 실체(정의 또는 직관)가 있어야 한다.
        return dsl.definition is not None or dsl.intuition is not None

    def render(self, dsl: ConceptDSL, ctx: RenderContext) -> RenderedUnit:
        segments: list[RenderSegment] = [RenderSegment(kind="heading", content=dsl.name)]
        if dsl.definition:
            segments.append(
                RenderSegment(kind="definition", content=_substitute(dsl.definition, ctx.bindings))
            )
        if dsl.intuition:
            segments.append(
                RenderSegment(kind="intuition", content=_substitute(dsl.intuition, ctx.bindings))
            )
        for example in dsl.examples:
            segments.append(
                RenderSegment(kind="example", content=_substitute(example, ctx.bindings))
            )
        return _finish(self.strategy, dsl, segments)


class SocraticAdapter:
    """소크라테스식 — 정의를 *주지 않고* 발문으로 스스로 도달하게 한다.

    핵심 차이: 정의는 화면에 실리지 않는다(학생이 답할 자리를 비운다). 개념명은 발문의 재료로만
    쓰이며, 조사는 `josa`가 판정한다(개념명이 무엇이든 문법이 맞는다 — 개념 무관성의 실천).
    """

    @property
    def strategy(self) -> PedagogyStrategy:
        return PedagogyStrategy.SOCRATIC

    def can_render(self, dsl: ConceptDSL) -> bool:
        return True  # 이름만 있어도 발문은 던질 수 있다.

    def render(self, dsl: ConceptDSL, ctx: RenderContext) -> RenderedUnit:
        name = dsl.name
        segments: list[RenderSegment] = [
            RenderSegment(kind="heading", content=name),
            RenderSegment(
                kind="question",
                content=(
                    f"{name}{eun_neun(name)} 무엇을 뜻한다고 생각하나요? 자기 말로 설명해 보세요."
                ),
            ),
        ]
        for example in dsl.examples:
            rendered = _substitute(example, ctx.bindings)
            segments.append(
                RenderSegment(
                    kind="question",
                    content=f"다음 사례{i_ga('사례')} 왜 그렇게 되는지 설명해 볼까요? {rendered}",
                )
            )
        segments.append(
            RenderSegment(
                kind="question",
                content=f"어떤 점{i_ga('점')} 가장 헷갈리나요? 헷갈리는 지점을 말해 주세요.",
            )
        )
        return _finish(self.strategy, dsl, segments)


class WorkedExampleAdapter:
    """완전예제 — 풀이 과정을 끝까지 보여준다.

    ⚠️ 이 전략은 학생이 시도하기 *전*에 제공하면 "막혔을 때 바로 정답 제공 금지"를 어긴다. 그
    게이팅은 **L4 선택기(PED-02)** 책임이며 이 어댑터는 방식 실행만 한다(계층 경계 — 렌더는 선택을
    모른다). 어댑터 단독으로는 냉담 제공을 막을 수 없으므로 상위 게이트가 필수다.
    """

    @property
    def strategy(self) -> PedagogyStrategy:
        return PedagogyStrategy.WORKED_EXAMPLE

    def can_render(self, dsl: ConceptDSL) -> bool:
        # 보여줄 풀이 재료(평가 재료 또는 예시)가 있어야 한다.
        return dsl.assessment is not None or bool(dsl.examples)

    def render(self, dsl: ConceptDSL, ctx: RenderContext) -> RenderedUnit:
        segments: list[RenderSegment] = [RenderSegment(kind="heading", content=dsl.name)]
        if dsl.definition:
            segments.append(
                RenderSegment(kind="definition", content=_substitute(dsl.definition, ctx.bindings))
            )
        if dsl.assessment is not None:
            for condition in dsl.assessment.conditions:
                segments.append(
                    RenderSegment(kind="solution_step", content=f"조건을 확인합니다: {condition}")
                )
            for variable, value in sorted(dsl.assessment.answer_map.items()):
                segments.append(
                    RenderSegment(
                        kind="solution_step",
                        content=f"{variable}{eun_neun(variable)} {value}로 구해집니다.",
                    )
                )
        for example in dsl.examples:
            segments.append(
                RenderSegment(kind="example", content=_substitute(example, ctx.bindings))
            )
        return _finish(self.strategy, dsl, segments)


class ProblemBasedAdapter:
    """문제기반 — 문제를 먼저 제시하고 개념은 뒤따라 끌어온다(정답은 제시하지 않는다)."""

    @property
    def strategy(self) -> PedagogyStrategy:
        return PedagogyStrategy.PROBLEM_BASED

    def can_render(self, dsl: ConceptDSL) -> bool:
        # 앞세울 문제가 있어야 성립한다.
        return dsl.assessment is not None

    def render(self, dsl: ConceptDSL, ctx: RenderContext) -> RenderedUnit:
        segments: list[RenderSegment] = [RenderSegment(kind="heading", content=dsl.name)]
        assessment = dsl.assessment
        if assessment is not None:
            prompt = assessment.prompt or "다음 조건을 만족하는 값을 구해 보세요."
            segments.append(RenderSegment(kind="prompt", content=_substitute(prompt, ctx.bindings)))
            for condition in assessment.conditions:
                segments.append(RenderSegment(kind="prompt", content=condition))
            # 정답(answer_map)은 싣지 않는다 — 문제기반의 요점은 학생이 스스로 도달하는 것이다.
        segments.append(
            RenderSegment(
                kind="question",
                content=f"이 문제를 풀려면 어떤 개념{i_ga('개념')} 필요할까요?",
            )
        )
        return _finish(self.strategy, dsl, segments)


class AnalogyAdapter:
    """비유 — 친숙한 상황에 빗대어 직관을 먼저 세운다(개념 이해 부족에 유효)."""

    @property
    def strategy(self) -> PedagogyStrategy:
        return PedagogyStrategy.ANALOGY

    def can_render(self, dsl: ConceptDSL) -> bool:
        return dsl.intuition is not None

    def render(self, dsl: ConceptDSL, ctx: RenderContext) -> RenderedUnit:
        name = dsl.name
        segments: list[RenderSegment] = [RenderSegment(kind="heading", content=name)]
        if dsl.intuition:
            segments.append(
                RenderSegment(kind="intuition", content=_substitute(dsl.intuition, ctx.bindings))
            )
        segments.append(
            RenderSegment(
                kind="question",
                content=(
                    f"이 비유{eul_reul('비유')} {name}에 그대로 옮기면 "
                    "어떤 점이 같고 어떤 점이 다를까요?"
                ),
            )
        )
        # 비유의 한계를 반드시 짚는다 — 비유를 정의로 오인하면 그 자체가 오개념이 된다.
        segments.append(
            RenderSegment(
                kind="reflection",
                content="비유는 이해를 돕는 도구일 뿐, 정확한 정의를 대신하지 않습니다.",
            )
        )
        return _finish(self.strategy, dsl, segments)


__all__ = [
    "AnalogyAdapter",
    "DirectAdapter",
    "ProblemBasedAdapter",
    "SocraticAdapter",
    "WorkedExampleAdapter",
]
