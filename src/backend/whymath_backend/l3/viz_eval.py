"""L3 시각화 명세 *생성 품질* 평가 — 순수 채점·집계 로직 (작업 I).

H(슬라이스 후속)는 ① `SimulationSpec.outcomes` 스키마와 ② L3 시스템 프롬프트의 type별
예시를 보강했다. 그러나 *로컬 LLM이 그 프롬프트로 실제로 유효한 outcomes(임의 분포)·3D
surface 명세를 생성하는지*는 단위 테스트(canned/fake provider)로는 검증되지 않는다. 이
모듈은 그 라이브 평가의 *순수 채점기*다 — 모델 호출(라이브)은 `test_visualization_live`가
하고, 여기서는 채점·집계만 한다(모델·GPU 없이 CI에서 검증 가능).

설계 철학(`infra/phaiakes9/benchmark/quality_eval.py` 답습):
    - **결정적(프로그램) 채점.** LLM-as-judge를 쓰지 않는다 — 채점은 *프로덕션 검증 게이트*
      `parse_visualization_spec`(JSON 추출 → `Visualization` 스키마 검증) + type 일치 + 구조
      완성도(순수 함수)다. 재현 가능하고 CLAUDE.md "LLM 응답 검증 없이 제공 금지"에 정합.
    - **프롬프트 드리프트 0.** 평가는 `l3.visualization.build_visualization_prompt`(프로덕션
      프롬프트 공개 접근자)와 `parse_visualization_spec`(프로덕션 게이트)만 쓴다 — 평가가
      프롬프트를 따로 베끼지 않는다.

부수 산출(라우팅 보정 신호): viz `generate` 호출지점은 라우터의 NLP 집합에 없어 기본 MATH
패밀리(qwen2-math)로 라우팅된다(`l3/router.py`). 하지만 viz 명세 생성은 한국어 JSON 구조화
(NLP) 작업이라 수학특화 모델이 부적합할 수 있다 — quality_eval이 드러낸 패밀리 불일치와
동형이다. 이 평가의 패밀리별 유효율 비교가 *viz를 GENERAL로 라우팅 보정할지* 근거를 만든다
(라우터 코드 변경은 이 모듈 범위 밖 — 평가가 근거를 만든 뒤 별도 결정).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, Final, TypeGuard

from whymath_backend.l3.visualization import (
    InvalidVisualizationSpecError,
    parse_visualization_spec,
)
from whymath_backend.schema.enums import VisualizationType

# ──────────────────────────────────────────────────────────────────────────
# 상수 — 결정 임계값(문서화된 튜닝 가능 상수, quality_eval ABS_MIN 답습)
# ──────────────────────────────────────────────────────────────────────────
# 한 (패밀리 × 타입) 셀의 유효 명세 생성률이 이 하한 이상이면 그 패밀리가 그 타입에 충분히
# 적합하다고 본다. 0.6 = "최소 다수는 유효해야 한다"는 보수적 기준(quality_eval ABS_MIN=0.6와
# 동일 근거·동일 값). Kiki가 Phaiakes9 실측 분포를 보고 보정한다.
VIZ_MIN_VALID: Final[float] = 0.60

# 부동소수점 경계 비교 허용 오차(quality_eval _EPS 답습).
_EPS: Final[float] = 1e-9

# viz `generate`가 *프로덕션에서* 라우팅되는 패밀리 — 라우터 NLP 집합에 없어 MATH가 기본값
# (router.py 규칙 2·4·5 "그 외 → MATH"). 평가의 단언은 이 패밀리에 건다(프로덕션 정합).
PRODUCTION_FAMILY: Final[str] = "math"


# ──────────────────────────────────────────────────────────────────────────
# 완성도 판정 (순수 함수) — type별 spec이 *학생에게 쓸모 있는* 최소 구조를 갖췄는가
# ──────────────────────────────────────────────────────────────────────────
def _is_number(value: object) -> TypeGuard[float]:
    """bool을 제외한 실수(int/float) 여부 — JSON의 true/false가 숫자로 새는 것 차단.

    TypeGuard라 통과 시 호출부에서 value가 float로 좁혀진다(이후 `< 0` 비교가 타입 안전).
    """
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _number_line_has_valid_item(number_line: dict[str, Any]) -> bool:
    """number_line(1D 수직선·VIZ-07)에 그릴 수 있는 유효 항목이 1개 이상인가.

    유효 point = dict이고 value가 수치 / 유효 interval = dict이고 start·end 중 하나 이상 수치
    (둘 다 없으면 반직선조차 못 그린다) — 웹 어댑터(graph2dSpec.js `_numberLineToState`)의
    렌더 가능 판정과 같은 기준이다(완성도 = 렌더러에게 쓸모 있는 최소 구조).
    """
    points = number_line.get("points")
    intervals = number_line.get("intervals")
    if isinstance(points, list) and any(
        isinstance(p, dict) and _is_number(p.get("value")) for p in points
    ):
        return True
    return isinstance(intervals, list) and any(
        isinstance(iv, dict) and (_is_number(iv.get("start")) or _is_number(iv.get("end")))
        for iv in intervals
    )


def complete_graph2d(spec: dict[str, Any]) -> bool:
    """interactive_graph_2d 완성도 — 함수식(비어있지 않음)+정의역 2원소, 또는 1D 수직선.

    VIZ-07 1D 분기: `number_line` 명세는 함수식 없이도 완성일 수 있다 — number_line이 dict이고
    유효 항목(점·구간)이 1개 이상이며 domain이 2원소 수치면 완성으로 판정한다(1D 축 범위 =
    domain 재사용 규약이라 domain은 여전히 필수). 기존 함수 경로(function+domain)는 불변.
    """
    domain = spec.get("domain")
    domain_ok = isinstance(domain, list) and len(domain) == 2 and all(_is_number(x) for x in domain)
    number_line = spec.get("number_line")
    if isinstance(number_line, dict) and _number_line_has_valid_item(number_line):
        return domain_ok
    function = spec.get("function")
    if not isinstance(function, str) or not function.strip():
        return False
    return domain_ok


def complete_surface3d(spec: dict[str, Any]) -> bool:
    """interactive_surface_3d 완성도 — 곡면식(비어있지 않은 문자열)."""
    surface = spec.get("surface")
    return isinstance(surface, str) and bool(surface.strip())


def complete_simulation(spec: dict[str, Any]) -> bool:
    """simulation_probabilistic 완성도 — outcomes ≥2·각 라벨 비어있지 않음·weight ≥0.

    H가 노린 핵심: 키워드(동전·주사위) 결합이 아니라 *구조화 outcomes*로 임의 분포를
    표현했는가. outcomes가 없거나 1개면(이산 분포라 부를 수 없음) 미완성으로 본다.
    """
    outcomes = spec.get("outcomes")
    if not isinstance(outcomes, list) or len(outcomes) < 2:
        return False
    for outcome in outcomes:
        if not isinstance(outcome, dict):
            return False
        label = outcome.get("label")
        weight = outcome.get("weight")
        if not isinstance(label, str) or not label.strip():
            return False
        if not _is_number(weight) or weight < 0:
            return False
    return True


# VisualizationType → 완성도 판정기. 평가 대상 3종(2d·3d·sim)을 덮는다.
# animation_prerendered는 평가셋에 없어(렌더 자산 사전 생성 전제) 매핑하지 않는다.
_COMPLETENESS_BY_TYPE: Final[dict[VisualizationType, Callable[[dict[str, Any]], bool]]] = {
    VisualizationType.interactive_graph_2d: complete_graph2d,
    VisualizationType.interactive_surface_3d: complete_surface3d,
    VisualizationType.simulation_probabilistic: complete_simulation,
}


# ──────────────────────────────────────────────────────────────────────────
# 도메인 타입
# ──────────────────────────────────────────────────────────────────────────
@dataclass(frozen=True, slots=True)
class VizEvalItem:
    """평가셋 항목 1건 — 개념·수준 → 기대 시각화 타입.

    concept는 *자체 원작 한국어 개념*이다(검정교과서·평가원 본문 미복제 — CLAUDE.md 금기).
    expected_type은 "이 개념엔 이 시각화가 자연스럽다"는 기대이지 강제는 아니다 — 모델이
    다른 (유효한) 타입을 골라도 type_ok=False로 측정될 뿐 채점이 깨지지 않는다.
    """

    id: str
    concept: str
    level: str
    expected_type: VisualizationType


@dataclass(frozen=True, slots=True)
class VizItemScore:
    """한 모델이 한 항목을 생성한 결과의 결정적 채점.

    3단계 게이트(모두 통과해야 valid):
      1. parsed_ok — `parse_visualization_spec`(프로덕션 게이트) 통과(JSON+스키마).
      2. type_ok   — 생성된 type이 기대 type과 일치.
      3. complete  — 기대 type의 완성도 판정 통과(쓸모 있는 최소 구조).
    """

    item_id: str
    expected_type: str
    parsed_ok: bool
    type_ok: bool
    complete: bool
    valid: bool
    error: str | None = None


def grade_spec(
    raw_text: str,
    expected_type: VisualizationType,
    *,
    item_id: str = "",
) -> VizItemScore:
    """LLM 원시 출력 → 결정적 채점(VizItemScore). 모델 없이 검증 가능한 순수 함수.

    프로덕션 게이트(`parse_visualization_spec`)로 파싱·검증한 뒤, type 일치와 완성도를
    판정한다. 파싱 실패(JSON 깨짐·스키마 위반)는 parsed_ok=False·error로 흡수한다 —
    채점기가 죽지 않는다(quality_eval grade_item 패턴). valid = 파싱·type·완성도 모두 통과.
    """
    try:
        viz = parse_visualization_spec(raw_text)
    except InvalidVisualizationSpecError as exc:
        return VizItemScore(
            item_id=item_id,
            expected_type=expected_type.value,
            parsed_ok=False,
            type_ok=False,
            complete=False,
            valid=False,
            error=f"{type(exc).__name__}: {exc}",
        )

    # use_enum_values=True라 viz.type은 문자열 값이다(정규화해 비교).
    actual_type = VisualizationType(viz.type)
    type_ok = actual_type == expected_type
    checker = _COMPLETENESS_BY_TYPE.get(expected_type)
    complete = bool(checker(viz.spec)) if checker is not None else False
    return VizItemScore(
        item_id=item_id,
        expected_type=expected_type.value,
        parsed_ok=True,
        type_ok=type_ok,
        complete=complete,
        valid=type_ok and complete,
        error=None,
    )


# ──────────────────────────────────────────────────────────────────────────
# 집계·판정 (순수 함수)
# ──────────────────────────────────────────────────────────────────────────
@dataclass(frozen=True, slots=True)
class VizRunRecord:
    """한 (모델 × 항목) 실행의 채점 결과 — 라이브 러너가 모아 집계기에 넘긴다."""

    model_id: str
    family: str
    item: VizEvalItem
    score: VizItemScore


@dataclass(frozen=True, slots=True)
class CellAggregate:
    """(모델 패밀리 × 시각화 타입) 셀의 유효 명세 생성률."""

    family: str
    model_id: str
    viz_type: str
    n_items: int
    n_valid: int
    valid_rate: float


def aggregate(records: Sequence[VizRunRecord]) -> list[CellAggregate]:
    """실행 기록을 (패밀리, 타입) 셀별 유효율로 집계한다(정렬된 키 순서·재현성)."""
    buckets: dict[tuple[str, str, str], list[VizRunRecord]] = {}
    for rec in records:
        key = (rec.family, rec.model_id, rec.item.expected_type.value)
        buckets.setdefault(key, []).append(rec)

    out: list[CellAggregate] = []
    for family, model_id, viz_type in sorted(buckets):
        bucket = buckets[(family, model_id, viz_type)]
        n = len(bucket)
        n_valid = sum(1 for r in bucket if r.score.valid)
        out.append(
            CellAggregate(
                family=family,
                model_id=model_id,
                viz_type=viz_type,
                n_items=n,
                n_valid=n_valid,
                valid_rate=round(n_valid / n, 4) if n else 0.0,
            )
        )
    return out


@dataclass(frozen=True, slots=True)
class TypeVerdict:
    """한 시각화 타입에 대한 패밀리 비교 판정.

    best_*는 그 타입에서 유효율이 가장 높은 패밀리(라우팅 보정 후보), production_*는
    *현행 프로덕션 패밀리*(MATH)의 성적이다. meets_threshold가 False면 = 현행 라우팅이
    그 타입에서 부적합 → viz 라우팅 보정 필요 신호.
    """

    viz_type: str
    best_family: str
    best_rate: float
    production_family: str
    production_rate: float
    meets_threshold: bool
    verdict: str


def build_verdicts(
    cells: Sequence[CellAggregate],
    *,
    production_family: str = PRODUCTION_FAMILY,
    threshold: float = VIZ_MIN_VALID,
) -> list[TypeVerdict]:
    """셀 집계 → 타입별 패밀리 비교 판정. 정렬된 타입 순서(재현성).

    - best_family: 그 타입에서 유효율 최대 패밀리(동률이면 패밀리명 사전순 첫째).
    - production_rate: 현행 프로덕션 패밀리의 유효율(셀 없으면 0.0·보수적).
    - meets_threshold: production_rate ≥ threshold(_EPS 허용 오차로 경계 안정화).
    """
    by_type: dict[str, list[CellAggregate]] = {}
    for cell in cells:
        by_type.setdefault(cell.viz_type, []).append(cell)

    verdicts: list[TypeVerdict] = []
    for viz_type in sorted(by_type):
        type_cells = by_type[viz_type]
        # 최고 유효율 패밀리(동률은 패밀리명 사전순 — 결정성).
        best = max(type_cells, key=lambda c: (c.valid_rate, _neg_family_key(c.family)))
        prod = next((c for c in type_cells if c.family == production_family), None)
        prod_rate = prod.valid_rate if prod is not None else 0.0
        meets = prod_rate >= threshold - _EPS
        if meets:
            verdict = (
                f"{viz_type}: 프로덕션({production_family}) 유효율 {prod_rate:.0%} ≥ "
                f"하한 {threshold:.0%} — 현행 라우팅 적합."
            )
        else:
            verdict = (
                f"{viz_type}: 프로덕션({production_family}) 유효율 {prod_rate:.0%} < "
                f"하한 {threshold:.0%} — 최적은 {best.family}({best.valid_rate:.0%}); "
                f"viz 라우팅 보정 검토."
            )
        verdicts.append(
            TypeVerdict(
                viz_type=viz_type,
                best_family=best.family,
                best_rate=best.valid_rate,
                production_family=production_family,
                production_rate=prod_rate,
                meets_threshold=meets,
                verdict=verdict,
            )
        )
    return verdicts


def _neg_family_key(family: str) -> tuple[int, ...]:
    """동률 tie-break — 패밀리명 사전순 *앞*을 우선(부호 반전으로 max에서 선택)."""
    return tuple(-ord(ch) for ch in family)


# ──────────────────────────────────────────────────────────────────────────
# 평가셋 — *자체 원작* 한국어 개념(검정교과서·평가원 본문 미복제, CLAUDE.md 금기)
# ──────────────────────────────────────────────────────────────────────────
# 임의 분포(동전·주사위 키워드를 *넘어서는* 확률 실험)와 다양한 곡면을 강조한다 — H가 노린
# outcomes 구조화·임의 실험 지원이 실제로 생성되는지 본다. 2d는 대조군(가장 쉬운 타입).
EVAL_ITEMS: Final[tuple[VizEvalItem, ...]] = (
    # ── simulation_probabilistic (구조화 outcomes·임의 분포) ──
    VizEvalItem(
        id="sim-rps",
        concept="가위바위보 한 판에서 나올 수 있는 결과",
        level="중학교 2학년",
        expected_type=VisualizationType.simulation_probabilistic,
    ),
    VizEvalItem(
        id="sim-dodecahedron",
        concept="정십이면체 주사위를 한 번 굴렸을 때 나오는 눈",
        level="중학교 3학년",
        expected_type=VisualizationType.simulation_probabilistic,
    ),
    VizEvalItem(
        id="sim-defect",
        concept="불량률이 3%인 공정에서 제품 한 개를 검사했을 때의 결과",
        level="고등학교 1학년",
        expected_type=VisualizationType.simulation_probabilistic,
    ),
    VizEvalItem(
        id="sim-colored-balls",
        concept="빨강·파랑·노랑 공이 1:2:3 비율로 든 주머니에서 공 하나 꺼내기",
        level="중학교 2학년",
        expected_type=VisualizationType.simulation_probabilistic,
    ),
    # ── interactive_surface_3d (다양한 곡면) ──
    VizEvalItem(
        id="surf-saddle",
        concept="이변수함수 z = x² − y² 가 그리는 안장면",
        level="고등학교 2학년",
        expected_type=VisualizationType.interactive_surface_3d,
    ),
    VizEvalItem(
        id="surf-paraboloid",
        concept="z = x² + y² 가 그리는 회전포물면",
        level="고등학교 2학년",
        expected_type=VisualizationType.interactive_surface_3d,
    ),
    VizEvalItem(
        id="surf-wave",
        concept="z = sin(x)·cos(y) 가 그리는 물결 모양 곡면",
        level="고등학교 3학년",
        expected_type=VisualizationType.interactive_surface_3d,
    ),
    # ── interactive_graph_2d (대조군) ──
    VizEvalItem(
        id="graph-quadratic",
        concept="이차함수 y = a·x² + b·x + c 에서 계수 a 의 변화",
        level="중학교 3학년",
        expected_type=VisualizationType.interactive_graph_2d,
    ),
    VizEvalItem(
        id="graph-sine",
        concept="사인함수 y = a·sin(b·x) 의 진폭과 주기 변화",
        level="고등학교 1학년",
        expected_type=VisualizationType.interactive_graph_2d,
    ),
)
"""라이브 평가 항목. 패밀리 비교 러너가 각 후보 모델 × 이 항목으로 생성·채점한다."""
