"""S4-19 — 3상태 단계 검증 회계(`compute_step_verification_accounting`) 단위 + 노출 봉인.

두 축을 검증한다(hermetic·라이브 DB 0):
  1) **정직 회계** — 3카운트 전부 non-NULL인 이벤트만 파생 분모(S3-07·`wh1_shadow_harvest.
     summarize` 동형)·카운트 비보유는 "구판 *또는* 검증 미실행 제출" 한 버킷으로 분리 계상·
     전이 표본 0이면 비율 None(가짜 0 금지).
  2) **노출 봉인**(2026-08-04 헌법 "정본화≠집행" 별항) — 파생 지표가 `SurrogateMetrics`/
     학생 라우트(`GET /v1/me/harness-metrics`)에 새지 않음을 3층(스키마·OpenAPI·실바디 프록시)
     으로 동결한다(ASM-07 `test_prediction_field_sealing.py` 패턴 승계). 각 층에 무력화 하한
     (스캔이 실제로 무언가를 봤는지)과 변별력(결함 샘플을 실제로 잡는지)을 동봉한다.

집계 SQL의 실 정확성(JSONB 캐스팅·FILTER)은 실 PG 통합테스트 소관 — 여기선 FakeSession이
한 행(6컬럼)을 주입해 래퍼 로직(버킷 분리·비율 파생·None 보존)만 본다(`test_wh1_evaluation.py`
FakeSession 관례 동형).
"""

from __future__ import annotations

import dataclasses
from typing import Any, cast

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from whymath_backend.app import create_app
from whymath_backend.harness.wh1_evaluation import (
    HelpReductionValidation,
    Metric,
    MetricStatus,
    R15Verdict,
    StepVerificationAccounting,
    SurrogateMetrics,
    compute_step_verification_accounting,
)

# S4-19 파생·회계 필드명 전체 — 학생 표면 어디에도 나타나면 안 되는 내부 전용 키 집합.
_S4_19_INTERNAL_KEYS: frozenset[str] = frozenset(
    {
        "step_decision_rate",
        "step_incorrect_rate",
        "counted_events",
        "uncounted_events",
        "n_correct_total",
        "n_incorrect_total",
        "n_unverifiable_total",
        "ocr_gated_events",
    }
)


class _OneRowResult:
    """`.one()`만 지원하는 execute 결과 — 집계 한 행(6컬럼) 주입용."""

    def __init__(self, one: tuple[Any, ...]) -> None:
        self._one = one

    def one(self) -> tuple[Any, ...]:
        return self._one


class _FakeSession:
    """execute 1회를 기대하고 미리 넣은 한 행을 돌려준다(stmt 무시 — SQL 정확성은 실 PG 소관)."""

    def __init__(self, row: tuple[Any, ...]) -> None:
        self._row = row
        self.execute_count = 0

    async def execute(self, _stmt: Any) -> _OneRowResult:
        self.execute_count += 1
        return _OneRowResult(self._row)


def _session(
    *,
    total: int,
    counted: int,
    sum_correct: int | None,
    sum_incorrect: int | None,
    sum_unverifiable: int | None,
    ocr_gated: int,
) -> AsyncSession:
    """집계 행(전체 수·counted 수·카운트 합 3종·ocr_gated 수)을 주입한 FakeSession."""
    return cast(
        AsyncSession,
        _FakeSession((total, counted, sum_correct, sum_incorrect, sum_unverifiable, ocr_gated)),
    )


class TestComputeStepVerificationAccounting:
    async def test_mixed_ledger_counts_and_rates(self) -> None:
        """신구 혼재: counted 2건(전이 3/1/1)·비보유 3건 → 분모는 counted 전이 합(5)만."""
        session = _session(
            total=5, counted=2, sum_correct=3, sum_incorrect=1, sum_unverifiable=1, ocr_gated=1
        )
        acc = await compute_step_verification_accounting(session)
        assert acc.counted_events == 2
        assert acc.uncounted_events == 3  # 구판 또는 검증 미실행 — 분리 계상(위장 0)
        assert acc.n_correct_total == 3
        assert acc.n_incorrect_total == 1
        assert acc.n_unverifiable_total == 1
        # D6 정의: step_decision_rate=(correct+incorrect)/전체 전이·step_incorrect_rate=incorrect/전체 전이.
        assert acc.step_decision_rate == (3 + 1) / 5
        assert acc.step_incorrect_rate == 1 / 5
        assert acc.ocr_gated_events == 1

    async def test_zero_counted_events_rates_are_none(self) -> None:
        """counted 0건(전부 구판/무검증) → 파생 비율 None — 가짜 0 금지·비보유만 계상."""
        session = _session(
            total=4,
            counted=0,
            sum_correct=None,
            sum_incorrect=None,
            sum_unverifiable=None,
            ocr_gated=0,
        )
        acc = await compute_step_verification_accounting(session)
        assert acc.counted_events == 0
        assert acc.uncounted_events == 4
        assert acc.step_decision_rate is None  # 0이 아님!
        assert acc.step_incorrect_rate is None
        assert acc.n_correct_total == 0  # 합계는 0(빈 합) — 비율만 None(분모 없음)

    async def test_counted_but_zero_transitions_rates_are_none(self) -> None:
        """counted는 있으나 전이 합 0(전이 0회 제출만) → 비율 None(분모 0 — 날조 회피)."""
        session = _session(
            total=2, counted=2, sum_correct=0, sum_incorrect=0, sum_unverifiable=0, ocr_gated=0
        )
        acc = await compute_step_verification_accounting(session)
        assert acc.counted_events == 2  # 검증은 실행됨(카운트 보유) — 비보유와 구분
        assert acc.uncounted_events == 0
        assert acc.step_decision_rate is None
        assert acc.step_incorrect_rate is None

    async def test_empty_ledger_all_zero_and_none(self) -> None:
        """검산결과 이벤트 0건 → 전부 0·비율 None(표본 0을 0%로 위장하지 않음)."""
        session = _session(
            total=0,
            counted=0,
            sum_correct=None,
            sum_incorrect=None,
            sum_unverifiable=None,
            ocr_gated=0,
        )
        acc = await compute_step_verification_accounting(session)
        assert acc.counted_events == 0
        assert acc.uncounted_events == 0
        assert acc.step_decision_rate is None
        assert acc.step_incorrect_rate is None
        assert acc.ocr_gated_events == 0

    async def test_all_incorrect_rates(self) -> None:
        """변별력: incorrect만 있으면 decision율==incorrect율(둘 다 1.0) — 계산식이 실제로 갈림."""
        session = _session(
            total=1, counted=1, sum_correct=0, sum_incorrect=2, sum_unverifiable=0, ocr_gated=0
        )
        acc = await compute_step_verification_accounting(session)
        assert acc.step_decision_rate == 1.0
        assert acc.step_incorrect_rate == 1.0

    async def test_all_unverifiable_rates(self) -> None:
        """변별력(반대쪽): unverifiable만 있으면 decision율 0.0(실측 0 — None 아님)."""
        session = _session(
            total=1, counted=1, sum_correct=0, sum_incorrect=0, sum_unverifiable=3, ocr_gated=0
        )
        acc = await compute_step_verification_accounting(session)
        assert acc.step_decision_rate == 0.0  # 전이는 있었는데 판정을 못 냄 — 실측 0
        assert acc.step_incorrect_rate == 0.0

    def test_accounting_is_frozen(self) -> None:
        """회계 결과는 불변(frozen dataclass) — 소비처가 값을 조용히 바꿀 수 없다."""
        acc = StepVerificationAccounting(
            counted_events=1,
            uncounted_events=0,
            n_correct_total=1,
            n_incorrect_total=0,
            n_unverifiable_total=0,
            step_decision_rate=1.0,
            step_incorrect_rate=0.0,
            ocr_gated_events=0,
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            acc.counted_events = 2  # type: ignore[misc]


# ── 노출 봉인(3층) — 파생 지표는 학생 라우트에 나가지 않는다(노출 집행 별항) ─────────────


def _metric() -> Metric:
    return Metric(value=0.5, status=MetricStatus.MEASURED, note="테스트 note")


def _surrogate_metrics() -> SurrogateMetrics:
    """실바디 프록시용 최소 구성 SurrogateMetrics(test_growth_evidence_exposure 관례 동형)."""
    m = _metric()
    return SurrogateMetrics(
        verify_pass_rate=m,
        diagnosis_agreement_rate=m,
        session_completion_rate=m,
        tokens_per_turn=m,
        help_reduction_slope=m,
        calibration_brier=m,
        transfer_score=m,
        hint_depth_reached=m,
        mastery_gain_rate=m,
        gap_recovery_leadtime_days=m,
        misconception_resolution_rate=m,
        self_solve_rate=m,
        help_reduction_validated=HelpReductionValidation(
            verdict=R15Verdict.INSUFFICIENT_DATA, note="테스트 판정 note"
        ),
        sample_sessions=1,
        sample_resolved_dialogues=1,
        user_scoped=True,
    )


def _collect_ref_names(node: Any, out: set[str]) -> None:
    """OpenAPI 노드에서 참조 컴포넌트 스키마 이름을 재귀 수집(ASM-07 헬퍼 동형)."""
    if isinstance(node, dict):
        ref = node.get("$ref")
        if isinstance(ref, str) and ref.startswith("#/components/schemas/"):
            out.add(ref.rsplit("/", 1)[-1])
        for value in node.values():
            _collect_ref_names(value, out)
    elif isinstance(node, list):
        for item in node:
            _collect_ref_names(item, out)


def _reachable_schemas(openapi: dict[str, Any], roots: set[str]) -> set[str]:
    """루트 스키마에서 `$ref`로 도달 가능한 전체 집합(중첩 포함·ASM-07 헬퍼 동형)."""
    components = openapi.get("components", {}).get("schemas", {})
    seen: set[str] = set()
    frontier = set(roots)
    while frontier:
        name = frontier.pop()
        if name in seen or name not in components:
            continue
        seen.add(name)
        nested: set[str] = set()
        _collect_ref_names(components[name], nested)
        frontier |= nested - seen
    return seen


def _harness_metrics_response_schemas() -> tuple[set[str], dict[str, Any]]:
    """`GET /v1/me/harness-metrics` 응답에서 도달 가능한 스키마 집합 + openapi 문서."""
    openapi = create_app().openapi()
    operation = openapi["paths"]["/v1/me/harness-metrics"]["get"]  # 라우트 부재면 KeyError=red
    roots: set[str] = set()
    _collect_ref_names(operation.get("responses", {}), roots)
    return _reachable_schemas(openapi, roots), openapi


class TestStudentRouteSeal:
    """학생 라우트(`GET /v1/me/harness-metrics`) 응답에 S4-19 신규 키 0 — 3층 동결."""

    def test_schema_level_surrogate_metrics_has_no_s4_19_fields(self) -> None:
        """① 스키마 — SurrogateMetrics에 파생 필드가 없다(자동 서빙 경로 원천 차단)."""
        leaked = set(SurrogateMetrics.model_fields) & _S4_19_INTERNAL_KEYS
        assert leaked == set(), f"SurrogateMetrics에 S4-19 파생 필드가 있습니다: {sorted(leaked)}"
        # 무력화 하한 — 모델 필드 스캔이 실제로 무언가를 봤는지(기존 지표는 있어야 정상).
        assert "verify_pass_rate" in SurrogateMetrics.model_fields

    def test_serving_contract_no_s4_19_keys_in_route_schemas(self) -> None:
        """② 집행 지점 — OpenAPI상 학생 라우트 응답 스키마(중첩 $ref 포함) 어디에도 없다."""
        reachable, openapi = _harness_metrics_response_schemas()
        # 무력화 하한 — 라우트 응답에서 SurrogateMetrics가 실제로 도달돼야 아래 스캔이 유효하다.
        assert "SurrogateMetrics" in reachable
        components = openapi["components"]["schemas"]
        offenders = [
            f"{name}.{field}"
            for name in sorted(reachable)
            for field in sorted(set(components[name].get("properties", {})) & _S4_19_INTERNAL_KEYS)
        ]
        assert offenders == [], (
            "학생 라우트 응답 스키마에 S4-19 파생 키가 있습니다 — 내부 회계는 "
            f"surrogate_baseline_report(CLI)로만 렌더해야 합니다: {offenders}"
        )

    def test_scanner_detects_offending_schema(self) -> None:
        """②' 변별력 — 파생 키를 가진 스키마를 스캐너가 실제로 잡는가(0건 통과 위장 방지)."""
        fake = {
            "components": {
                "schemas": {"Offender": {"properties": {"step_decision_rate": {"type": "number"}}}}
            }
        }
        reachable = _reachable_schemas(fake, {"Offender"})
        props = fake["components"]["schemas"]["Offender"]["properties"]
        assert reachable == {"Offender"}
        assert set(props) & _S4_19_INTERNAL_KEYS == {"step_decision_rate"}

    def test_payload_level_real_body_has_no_s4_19_keys(self) -> None:
        """③ 페이로드 — 실제 직렬화 바디(model_dump) 키 집합에 S4-19 키 0(실바디 프록시).

        라우트는 response_model=SurrogateMetrics라 직렬화 경로가 이 모델 그대로다 — 인증·DB
        없이 같은 계약을 모델 직렬화로 확인한다(ASM-07 ③층 관례 — 실제 200 바디는 통합 소관).
        """
        payload = _surrogate_metrics().model_dump(mode="json")
        assert set(payload) & _S4_19_INTERNAL_KEYS == set()
        assert "verify_pass_rate" in payload  # 무력화 하한 — 빈 dict면 위 단언이 공허하다
