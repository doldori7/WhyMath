"""EOS-73 ② — seed 적재율 리포트의 판정 로직 동결(수치가 아니라 *변별력*을 검증한다).

이 리포트의 수치 자체는 실제 생성 배치의 genlog JSONL이 분모라 CI에서는 낼 수 없다. 그래서
여기서 동결하는 것은 다음 다섯이다:
  ① **3분류 변별력** — 지원/구조적 불가/미상을 뭉개지 않는다(뭉개면 배선 회귀가 라우팅 구성
     변화 뒤에 숨는다).
  ② **분모 0 처리** — 0%가 아니라 `측정 불가(분모 0)`로 렌더한다.
  ③ **죽은 경로 보강** — 기록 0건인 경로도 행이 사라지지 않는다(전멸 가시화).
  ④ **판별자 정합** — 리포트가 아는 `kind` 문자열이 *실제 생산자*가 쓰는 값과 같다(눈으로 맞춘
     문자열이 조용히 갈라지는 것을 막는다).
  ⑤ **CLI exit** — 0=성공(0%여도)/2=입력 오류. 게이트가 아니다.
"""

from __future__ import annotations

from pathlib import Path

from whymath_backend.config import get_settings
from whymath_backend.harness.generation_seed_adoption_report import (
    ACCUMULATE_PATH,
    PREGENERATE_PATH,
    UNKNOWN_PATH,
    build_report,
    main,
    path_of,
    render_report,
    report_to_json,
)
from whymath_backend.l3.models import (
    CostTier,
    LocalModelTier,
    ModelFamily,
    RoutingDecision,
    RoutingRequest,
)
from whymath_backend.l3.pregenerate.models import PregenItem, PrewarmItemResult
from whymath_backend.l3.pregenerate.provenance_bridge import (
    append_generation_log_jsonl,
    generation_log_from_result,
    input_snapshot_for_prewarm,
    model_name_for_decision,
)
from whymath_backend.l3.router import QUALITY_MODEL_ID
from whymath_backend.schema.provenance import GenerationLog

_LOCAL_MODEL = QUALITY_MODEL_ID
_CLOUD_MODEL = get_settings().anthropic_model_mid


def _log(*, kind: str | None, model_name: str, seed: int | None) -> GenerationLog:
    """테스트용 기록 1건 — 경로 판별자·모델명·시드만 다르게 만든다."""
    snapshot = None if kind is None else {"kind": kind, "prompt": "p", "system": "s"}
    return GenerationLog(
        model_name=model_name,
        seed=seed,
        success=True,
        input_snapshot=snapshot,
    )


class TestThreeWayClassification:
    def test_supported_missing_is_separated_from_structurally_impossible(self) -> None:
        """지원인데 미적재(회귀)와 구조적 불가(정답 NULL)를 한 숫자로 뭉개지 않는다."""
        report = build_report(
            [
                _log(kind=ACCUMULATE_PATH, model_name=_LOCAL_MODEL, seed=1),
                _log(kind=ACCUMULATE_PATH, model_name=_LOCAL_MODEL, seed=None),
                _log(kind=ACCUMULATE_PATH, model_name=_CLOUD_MODEL, seed=None),
            ]
        )
        accumulate = next(p for p in report.paths if p.path == ACCUMULATE_PATH)
        assert accumulate.supported_total == 2  # 클라우드는 분모에서 빠진다
        assert accumulate.supported_with_seed == 1
        assert accumulate.supported_missing == 1
        assert accumulate.unsupported_total == 1
        assert accumulate.adoption_rate == 0.5  # 1/2 — 클라우드를 분모에 넣었으면 1/3이었다

    def test_unknown_model_is_its_own_bucket(self) -> None:
        """미상은 지원/불가 어느 쪽으로도 반올림하지 않는다(분모 오염·회귀 은닉 방지)."""
        report = build_report([_log(kind=ACCUMULATE_PATH, model_name="사설:7b", seed=None)])
        accumulate = next(p for p in report.paths if p.path == ACCUMULATE_PATH)
        assert (accumulate.unknown_total, accumulate.supported_total) == (1, 0)
        assert accumulate.adoption_rate is None  # 지원 기록 0 → 측정 불가

    def test_fabrication_suspect_counted_when_unsupported_carries_seed(self) -> None:
        """구조적 불가 경로에 seed가 있으면 병리다 — 조용히 넘기지 않고 센다."""
        report = build_report([_log(kind=ACCUMULATE_PATH, model_name=_CLOUD_MODEL, seed=9)])
        assert report.fabrication_suspects == 1
        assert "병리" in render_report(report)


class TestZeroDenominatorAndDeadPaths:
    def test_zero_denominator_renders_as_unmeasurable_not_zero_percent(self) -> None:
        report = build_report([])
        assert report.overall_adoption_rate is None
        rendered = render_report(report)
        assert "측정 불가(분모 0)" in rendered
        assert "0.0%" not in rendered

    def test_both_known_paths_keep_their_row_even_with_no_records(self) -> None:
        """한 경로가 통째로 멈추면 집계에서 사라진다 — 보강이 없으면 전멸이 안 보인다."""
        report = build_report([_log(kind=ACCUMULATE_PATH, model_name=_LOCAL_MODEL, seed=1)])
        assert [p.path for p in report.paths][:2] == [PREGENERATE_PATH, ACCUMULATE_PATH]
        pregenerate = next(p for p in report.paths if p.path == PREGENERATE_PATH)
        assert pregenerate.total == 0 and pregenerate.adoption_rate is None

    def test_unknown_kind_is_kept_as_its_own_row(self) -> None:
        """구판·오배선 기록을 두 경로 중 하나로 반올림하지 않는다."""
        report = build_report([_log(kind=None, model_name=_LOCAL_MODEL, seed=None)])
        assert any(p.path == UNKNOWN_PATH and p.total == 1 for p in report.paths)


class TestPathDiscriminatorParity:
    """④ 판별자 정합 — 리포트의 사본 문자열이 *실제 생산자* 출력과 같은지 기계로 대조."""

    def test_pregenerate_kind_matches_the_real_producer(self) -> None:
        snapshot = input_snapshot_for_prewarm(_item())
        assert snapshot["kind"] == PREGENERATE_PATH

    def test_accumulate_kind_matches_the_real_producer(self) -> None:
        from whymath_backend.l3.equivalent.acceptance import EquivalenceSpec
        from whymath_backend.l3.equivalent.llm_generator import LLMEquivalentProblemGenerator

        generator = LLMEquivalentProblemGenerator(_NullProvider(), misconception_catalog={})
        spec = EquivalenceSpec(
            achievement_standard_codes=frozenset({"[10공수1-01-01]"}),
            target_misconception_ids=frozenset(),
            difficulty_overall=3.0,
            answer_format=None,
        )
        snapshot = generator._input_snapshot(spec, "프롬프트")
        assert snapshot["kind"] == ACCUMULATE_PATH

    def test_path_of_reads_the_snapshot_kind(self) -> None:
        log = _log(kind=PREGENERATE_PATH, model_name=_LOCAL_MODEL, seed=3)
        assert path_of(log) == PREGENERATE_PATH


def _item() -> PregenItem:
    """실제 생산자(`input_snapshot_for_prewarm`)에 넣을 최소 사전적재 항목."""
    return PregenItem(
        prompt="프롬프트",
        system="시스템",
        request=RoutingRequest(
            task_type="explain",
            difficulty="easy",
            requires_reasoning=False,
            student_subscription="free",
            sync=True,
        ),
    )


class _NullProvider:
    """호출되지 않는 provider 대역 — 스냅샷 조립만 확인하므로 generate는 쓰이지 않는다."""

    async def generate(self, *args: object, **kwargs: object) -> object:  # pragma: no cover
        raise AssertionError("이 테스트는 provider를 호출하지 않는다")


class TestEndToEndOverRealBridgeRecords:
    def test_real_prewarm_record_lands_in_the_supported_bucket(self, tmp_path: Path) -> None:
        """실제 브리지가 만든 레코드를 JSONL로 쓰고 다시 읽어 분류한다(형식 왕복 포함)."""
        decision = RoutingDecision(
            cost_tier=CostTier.LOCAL,
            local_family=ModelFamily.GENERAL,
            local_model=LocalModelTier.MID,
            mode="sync",
            reason="테스트",
            est_latency_ms=900,
        )
        log = generation_log_from_result(
            PrewarmItemResult(cache_key="k", status="written", seed=555),
            problem_id=None,
            model_name=model_name_for_decision(decision),
            seed=555,
            input_snapshot=input_snapshot_for_prewarm(_item()),
        )
        path = tmp_path / "genlog.jsonl"
        append_generation_log_jsonl(path, log)

        assert main([str(path)]) == 0  # 게이트 아님 — 성공은 0
        report = build_report([log])
        pregenerate = next(p for p in report.paths if p.path == PREGENERATE_PATH)
        assert (pregenerate.supported_total, pregenerate.supported_with_seed) == (1, 1)
        assert report.overall_adoption_rate == 1.0


class TestCliExitCodes:
    def test_missing_file_is_exit_2_not_zero_percent(self, tmp_path: Path) -> None:
        """파일 부재를 0%로 렌더하면 측정하지 않은 것을 측정한 것처럼 보이게 된다."""
        assert main([str(tmp_path / "없는파일.jsonl")]) == 2

    def test_empty_file_is_success_with_unmeasurable_rate(self, tmp_path: Path) -> None:
        path = tmp_path / "empty.jsonl"
        path.write_text("", encoding="utf-8")
        assert main([str(path)]) == 0  # 0건이어도 exit 0(게이트 아님)

    def test_parse_errors_are_reported_not_counted_as_missing_seed(self, tmp_path: Path) -> None:
        """파싱 실패는 '적재 실패'가 아니라 '측정 실패'다 — 다른 축으로 보고한다."""
        path = tmp_path / "broken.jsonl"
        path.write_text("{잘못된 JSON}\n", encoding="utf-8")
        assert main([str(path)]) == 0
        report = build_report([], parse_errors=["line 1: JSONDecodeError"])
        assert len(report.parse_errors) == 1
        assert "JSONDecodeError" in render_report(report)  # 타입명 보존(침묵 실패 금지)

    def test_json_output_carries_none_for_unmeasurable(self, tmp_path: Path) -> None:
        payload = report_to_json(build_report([]))
        assert payload["overall_adoption_rate"] is None  # 0.0이 아니라 None
