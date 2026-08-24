"""통계 자료형 검증기 — SymPy 불가 영역 v2 단계 A 실증 도메인(S4-53).

주어진 유한 데이터 표에 대한 평균·중앙값·분산·사분위수·상관계수 등을 전수 결정론으로 검증.
데이터가 주어지면 값은 확정되므로 기계 검증 가능 축이며, 잔여는 발문↔자료 정합·자료 해석
모호성·표본 추출 방법 등이다.

DSL(`verify.conditions`):
    data=[1,2,3,4,5]; stat=mean
    data=[[1,2],[3,4],[5,6]]; stat=corr; columns=[0,1]
    data=[10,20,30,40]; stat=median

지원 stat: mean(평균), median(중앙값), variance(분산·n-1), std(표준편차·n-1),
           q1(1사분위수), q3(3사분위수), corr(피어슨 상관계수·2열).

7계층: L3 지역. DB 0·LLM 0(순수 계산). import-linter L3 내부.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from statistics import correlation, median, stdev
from typing import Literal

from whymath_backend.l3.verify_answer import AnswerVerdict

__all__ = [
    "StatisticalClaimError",
    "StatisticalResult",
    "describe_statistical_model_ko",
    "parse_statistical_model",
    "verify_statistical_claim",
]


class StatisticalClaimError(ValueError):
    """DSL 파싱·모델 구성 실패 — 조용한 통과 금지(호출자가 unverifiable로 변환)."""


StatKind = Literal["mean", "median", "variance", "std", "q1", "q3", "corr"]


@dataclass(frozen=True, slots=True)
class StatisticalModel:
    """형식 모델 = 1차원 값 + corr용 2차원 표 + 요청 통계량 + 열 인덱스."""

    values: tuple[float, ...]
    table: tuple[tuple[float, ...], ...] | None
    stat: StatKind
    columns: tuple[int, ...] | None
    source: str


@dataclass(frozen=True, slots=True)
class StatisticalResult:
    """전수 계산 결과."""

    value: float | None
    n: int
    description: str


_TOL = 1e-9
_MAX_DATA_POINTS = 10_000


def _parse_data(raw: str) -> object:
    """data=[...] 문자열을 안전하게 JSON 배열로 파싱. eval 금지."""
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise StatisticalClaimError(f"data JSON 파싱 실패: {raw!r}") from exc
    if not isinstance(parsed, list):
        raise StatisticalClaimError(f"data는 배열이어야 함: {parsed!r}")
    return parsed


def _flatten_numbers(parsed: object) -> tuple[float, ...]:
    """1차원 숫자 배열 검증/변환."""
    if not isinstance(parsed, list):
        raise StatisticalClaimError(f"1차원 data는 리스트여야 함: {parsed!r}")
    if not parsed:
        raise StatisticalClaimError("data가 비어 있음")
    if len(parsed) > _MAX_DATA_POINTS:
        raise StatisticalClaimError(f"data 포인트 수 {len(parsed)}가 한도 {_MAX_DATA_POINTS} 초과")
    result: list[float] = []
    for item in parsed:
        if isinstance(item, bool):
            raise StatisticalClaimError("data에 bool 값은 허용되지 않음")
        if not isinstance(item, (int, float)):
            raise StatisticalClaimError(f"data 요소가 숫자가 아님: {item!r}")
        result.append(float(item))
    return tuple(result)


def _flatten_table(parsed: object) -> tuple[tuple[float, ...], ...]:
    """2차원 숫자 표 검증/변환."""
    if not isinstance(parsed, list):
        raise StatisticalClaimError(f"2차원 data는 리스트여야 함: {parsed!r}")
    if not parsed:
        raise StatisticalClaimError("data가 비어 있음")
    rows: list[tuple[float, ...]] = []
    expected_len: int | None = None
    for row in parsed:
        if not isinstance(row, list):
            raise StatisticalClaimError(f"data 행이 배열이 아님: {row!r}")
        if expected_len is None:
            expected_len = len(row)
        elif len(row) != expected_len:
            raise StatisticalClaimError(f"data 행 길이 불일치: {len(row)} != {expected_len}")
        converted: list[float] = []
        for item in row:
            if isinstance(item, bool):
                raise StatisticalClaimError("data에 bool 값은 허용되지 않음")
            if not isinstance(item, (int, float)):
                raise StatisticalClaimError(f"data 요소가 숫자가 아님: {item!r}")
            converted.append(float(item))
        rows.append(tuple(converted))
    if len(rows) > _MAX_DATA_POINTS:
        raise StatisticalClaimError(f"data 포인트 수 {len(rows)}가 한도 {_MAX_DATA_POINTS} 초과")
    return tuple(rows)


def _is_1d(data: object) -> bool:
    """파싱된 data가 1차원인가."""
    return isinstance(data, list) and (not data or not isinstance(data[0], list))


def _percentile(values: tuple[float, ...], p: float) -> float:
    """선형 보간법 percentile (0 <= p <= 1)."""
    if len(values) == 1:
        return values[0]
    sorted_values = sorted(values)
    n = len(sorted_values)
    pos = (n - 1) * p
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return sorted_values[lo]
    weight = pos - lo
    return sorted_values[lo] * (1 - weight) + sorted_values[hi] * weight


def parse_statistical_model(conditions: str) -> StatisticalModel:
    """`verify.conditions` 문자열 → StatisticalModel."""
    parts = conditions.split(";")
    kwargs: dict[str, str] = {}
    for part in parts:
        piece = part.strip()
        if not piece:
            continue
        if "=" not in piece:
            raise StatisticalClaimError(f"조건 절 형식 오류: {piece!r}")
        key, _, value = piece.partition("=")
        key = key.strip()
        value = value.strip()
        if key in kwargs:
            raise StatisticalClaimError(f"조건 절 중복: {key}")
        kwargs[key] = value

    if "data" not in kwargs or "stat" not in kwargs:
        raise StatisticalClaimError("data·stat 절은 필수")

    raw_data = _parse_data(kwargs["data"])
    stat_raw = kwargs["stat"].strip().lower()
    if stat_raw not in ("mean", "median", "variance", "std", "q1", "q3", "corr"):
        raise StatisticalClaimError(f"미지 stat: {stat_raw!r}")
    stat: StatKind = stat_raw  # type: ignore[assignment]

    columns: tuple[int, ...] | None = None
    if "columns" in kwargs:
        columns_raw = kwargs["columns"]
        try:
            cols = json.loads(columns_raw)
        except json.JSONDecodeError as exc:
            raise StatisticalClaimError(f"columns JSON 파싱 실패: {columns_raw!r}") from exc
        if not isinstance(cols, list):
            raise StatisticalClaimError(f"columns는 배열이어야 함: {cols!r}")
        columns = tuple(int(c) for c in cols)

    table: tuple[tuple[float, ...], ...] | None = None
    if _is_1d(raw_data):
        values = _flatten_numbers(raw_data)
        if stat == "corr":
            raise StatisticalClaimError("corr는 2차원 data가 필요함")
    else:
        table = _flatten_table(raw_data)
        if stat == "corr":
            if columns is None or len(columns) != 2:
                raise StatisticalClaimError("corr는 columns=[i,j]가 필요함")
            i, j = columns
            n_cols = len(table[0])
            if not (0 <= i < n_cols and 0 <= j < n_cols):
                raise StatisticalClaimError(f"columns 인덱스 범위 초과: {columns}")
            values = tuple(float(row[i]) for row in table)
        elif columns is not None:
            if len(columns) != 1:
                raise StatisticalClaimError(f"2차원 data에서 {stat}는 columns=[단일열]이 필요함")
            col_idx = columns[0]
            n_cols = len(table[0])
            if not (0 <= col_idx < n_cols):
                raise StatisticalClaimError(f"columns 인덱스 범위 초과: {col_idx}")
            values = tuple(float(row[col_idx]) for row in table)
            columns = None
        else:
            # 2차원 data인데 열 지정이 없으면 첫 번째 열 사용
            values = tuple(float(row[0]) for row in table)

    return StatisticalModel(
        values=values, table=table, stat=stat, columns=columns, source=conditions
    )


def _stat_value(model: StatisticalModel) -> tuple[float | None, str]:
    """요청 통계량 전수 계산."""
    values = model.values
    n = len(values)
    if n == 0:
        return None, "데이터가 비어 있음"

    if model.stat == "corr":
        if model.columns is None or len(model.columns) != 2 or model.table is None:
            return None, "corr는 2차원 data와 columns=[i,j]가 필요함"
        i, j = model.columns
        col_i = tuple(float(row[i]) for row in model.table)
        col_j = tuple(float(row[j]) for row in model.table)
        if len(col_i) < 2:
            return None, "상관계수 계산에 필요한 데이터 포인트가 2개 미만"
        try:
            value = correlation(col_i, col_j)
        except Exception as exc:  # noqa: BLE001
            return None, f"상관계수 계산 불가: {type(exc).__name__}"
        return value, f"피어슨 상관계수(n={len(col_i)}, columns={model.columns}) = {value}"

    if model.stat == "mean":
        value = sum(values) / n
        return value, f"평균(n={n}) = {value}"
    if model.stat == "median":
        value = median(values)
        return value, f"중앙값(n={n}) = {value}"
    if model.stat == "variance":
        value = stdev(values) ** 2 if n > 1 else 0.0
        return value, f"분산(n={n}, 자유도 n-1) = {value}"
    if model.stat == "std":
        value = stdev(values) if n > 1 else 0.0
        return value, f"표준편차(n={n}, 자유도 n-1) = {value}"
    if model.stat == "q1":
        value = _percentile(values, 0.25)
        return value, f"1사분위수(n={n}) = {value}"
    if model.stat == "q3":
        value = _percentile(values, 0.75)
        return value, f"3사분위수(n={n}) = {value}"
    raise StatisticalClaimError(f"미지 stat: {model.stat}")


def describe_statistical_model_ko(model: StatisticalModel, result: StatisticalResult) -> str:
    """형식 모델 + 계산 결과를 한국어 산문으로 — LLM 교차검증 관점 입력."""
    if model.stat == "corr" and model.table is not None:
        return (
            f"데이터는 {len(model.table)}개 행의 표이며, "
            f"열 {model.columns} 간 피어슨 상관계수를 계산한다. {result.description}."
        )
    return f"데이터: {list(model.values)}. {result.description}."


def _parse_claimed(answer: str) -> tuple[float | None, str | None]:
    """주장값 파싱 — '3.5', 'mean=3.5', 'a/b' 등."""
    text = answer.strip().replace(" ", "")
    if not text:
        return None, "주장값이 비어 있음"
    # 'mean=3.5' 형태에서 값 부분만 추출
    if "=" in text:
        _, _, value_text = text.partition("=")
    else:
        value_text = text
    try:
        # 분수 'a/b' 지원
        if "/" in value_text:
            num, den = value_text.split("/", 1)
            value = float(num) / float(den)
        else:
            value = float(value_text)
    except ValueError:
        return None, f"주장값 {answer!r}을 숫자로 읽을 수 없음"
    return value, None


def verify_statistical_claim(
    conditions: str, answer: str
) -> tuple[AnswerVerdict, tuple[str, ...], StatisticalResult]:
    """통계 자료형 검증 — (AnswerVerdict, residual_axes, StatisticalResult) 반환.

    pass: 계산값과 주장값이 허용오차 내 일치.
    fail: 주장값이 계산값과 다름.
    unverifiable: DSL 파싱 실패·계산 불가·주장값 파싱 불가.
    """
    residual_axes: tuple[str, ...] = ("자료↔발문 정합", "표본 추출 방법", "자료 해석의 모호성")
    try:
        model = parse_statistical_model(conditions)
        value, description = _stat_value(model)
    except StatisticalClaimError as exc:
        return (
            AnswerVerdict(state="unverifiable", reason=f"통계검증 — {exc}", samples_checked=0),
            residual_axes,
            StatisticalResult(value=None, n=0, description=""),
        )

    if value is None:
        return (
            AnswerVerdict(state="unverifiable", reason="통계검증 — 계산 불가", samples_checked=0),
            residual_axes,
            StatisticalResult(value=None, n=0, description=description),
        )

    result = StatisticalResult(value=value, n=len(model.values), description=description)

    claimed, reason = _parse_claimed(answer)
    if claimed is None:
        return (
            AnswerVerdict(
                state="unverifiable",
                reason=f"통계검증 — {reason}",
                samples_checked=result.n,
            ),
            residual_axes,
            result,
        )

    if math.isclose(value, claimed, rel_tol=_TOL, abs_tol=_TOL):
        return (
            AnswerVerdict(state="pass", reason=None, samples_checked=result.n),
            residual_axes,
            result,
        )

    return (
        AnswerVerdict(
            state="fail",
            reason=f"통계검증 — 계산값 {value}와 주장 {claimed} 불일치",
            samples_checked=result.n,
        ),
        residual_axes,
        result,
    )
