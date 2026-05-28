"""`provenance_bridge.generation_log_from_result` 단위 테스트 — status별 success 매핑.

설계 정본: `l3/pregenerate/provenance_bridge.py`. 계층 규칙상 사전생성 결과를
`GenerationLog`(schema)로 바꾸는 연결 코드는 L3쪽에 있다(schema는 l3 import 0).

검증:
  - status별 success 매핑(written/skipped_exists=True, failed_validation/error=False)
  - error 전달(error_detail로 그대로 옮겨짐)
  - 기본 None 텔레메트리(토큰/비용/지연 — provider가 usage 미노출)
  - 인자 전달(problem_id/model_name/provenance_id/prompt_template_id)
"""

from __future__ import annotations

import uuid

import pytest

from whymath_backend.l3.pregenerate.models import PrewarmItemResult, PrewarmStatus
from whymath_backend.l3.pregenerate.provenance_bridge import generation_log_from_result


def _result(status: PrewarmStatus, error: str | None = None) -> PrewarmItemResult:
    """주어진 status의 PrewarmItemResult(테스트 헬퍼)."""
    return PrewarmItemResult(cache_key="k1", status=status, error=error)


# ──────────────────────────────────────────────────────────────────────
# status → success 매핑
# ──────────────────────────────────────────────────────────────────────
class TestSuccessMapping:
    @pytest.mark.parametrize("status", ["written", "skipped_exists"])
    def test_success_statuses_map_true(self, status: PrewarmStatus) -> None:
        """written·skipped_exists = 유효 시드 확보 = success True."""
        log = generation_log_from_result(
            _result(status),
            problem_id=uuid.uuid4(),
            model_name="qwen3-32b",
        )
        assert log.success is True

    @pytest.mark.parametrize("status", ["failed_validation", "error"])
    def test_failure_statuses_map_false(self, status: PrewarmStatus) -> None:
        """failed_validation·error = 시드 미확보 = success False."""
        log = generation_log_from_result(
            _result(status, error="some reason"),
            problem_id=uuid.uuid4(),
            model_name="qwen3-32b",
        )
        assert log.success is False


# ──────────────────────────────────────────────────────────────────────
# error 전달
# ──────────────────────────────────────────────────────────────────────
class TestErrorPropagation:
    def test_error_passed_to_error_detail(self) -> None:
        """result.error → GenerationLog.error_detail로 그대로 옮겨짐."""
        log = generation_log_from_result(
            _result("failed_validation", error="SymPy: 1=2 거짓"),
            problem_id=uuid.uuid4(),
            model_name="qwen3-32b",
        )
        assert log.error_detail == "SymPy: 1=2 거짓"

    def test_none_error_on_success(self) -> None:
        """성공 status는 error=None → error_detail None."""
        log = generation_log_from_result(
            _result("written"),
            problem_id=uuid.uuid4(),
            model_name="qwen3-32b",
        )
        assert log.error_detail is None


# ──────────────────────────────────────────────────────────────────────
# 텔레메트리 — 항상 None(provider usage 미노출)
# ──────────────────────────────────────────────────────────────────────
class TestTelemetryNone:
    def test_telemetry_fields_are_none(self) -> None:
        """토큰/비용/지연은 지어내지 않고 None(provider가 usage 미노출)."""
        log = generation_log_from_result(
            _result("written"),
            problem_id=uuid.uuid4(),
            model_name="qwen3-32b",
        )
        assert log.input_tokens is None
        assert log.output_tokens is None
        assert log.cost_usd is None
        assert log.latency_ms is None
        assert log.generated_at is None


# ──────────────────────────────────────────────────────────────────────
# 인자 전달
# ──────────────────────────────────────────────────────────────────────
class TestArgumentPassthrough:
    def test_required_args_passed(self) -> None:
        """problem_id·model_name은 필수 인자에서 그대로 옮겨짐."""
        pid = uuid.uuid4()
        log = generation_log_from_result(
            _result("written"),
            problem_id=pid,
            model_name="claude-opus-4-7",
        )
        assert log.problem_id == pid
        assert log.model_name == "claude-opus-4-7"

    def test_optional_args_default_none(self) -> None:
        """provenance_id·prompt_template_id는 기본 None."""
        log = generation_log_from_result(
            _result("written"),
            problem_id=uuid.uuid4(),
            model_name="qwen3-32b",
        )
        assert log.provenance_id is None
        assert log.prompt_template_id is None

    def test_optional_args_passed(self) -> None:
        """provenance_id·prompt_template_id를 주면 그대로 옮겨짐."""
        prov = uuid.uuid4()
        tmpl = uuid.uuid4()
        log = generation_log_from_result(
            _result("skipped_exists"),
            problem_id=uuid.uuid4(),
            model_name="qwen3-32b",
            provenance_id=prov,
            prompt_template_id=tmpl,
        )
        assert log.provenance_id == prov
        assert log.prompt_template_id == tmpl
