"""WH-1 2단계 종료 게이트 ops CLI(`harness/agreement_gate_cli.py`) — 단위(hermetic·러너 주입).

라이브 임베딩 없이 CLI *배선*만 검증한다: ① 결합 판정→종료 코드(READY 0·NOT_READY 1·NO_DATA 2)
② stdout이 *순수 JSON*(recall/precision/decision 3축) ③ 인자(--alpha·--min-probes·--threshold)가
러너에 전달 ④ threshold 생략 시 None. 합성 `Phase2Report`를 러너로 주입한다(임베딩 비의존).
라이브 bge-b3·실 프로브셋 결선은 integration(WHYMATH_RUN_INTEGRATION) 한 건.
"""

from __future__ import annotations

import importlib.util
import json

import pytest

from whymath_backend.harness import agreement_gate_cli as cli
from whymath_backend.harness.agreement_gate import (
    Phase2ExitVerdict,
    Phase2Report,
    evaluate_agreement_gate,
    evaluate_phase2_exit,
    evaluate_precision_guard,
)


def _report(
    *, recall_paired: list[tuple[bool, bool]], precision_paired: list[tuple[bool, bool]]
) -> Phase2Report:
    """순수 evaluate로 합성 리포트 구성(임베딩 비의존)."""
    recall = evaluate_agreement_gate(recall_paired)
    precision = evaluate_precision_guard(precision_paired)
    return Phase2Report(
        recall=recall, precision=precision, decision=evaluate_phase2_exit(recall, precision)
    )


_READY = _report(recall_paired=[(False, True)] * 5, precision_paired=[(True, False)] * 5)
_NOT_READY = _report(recall_paired=[(False, True)] * 5, precision_paired=[(False, True)] * 5)
_NO_DATA = _report(recall_paired=[(False, True)] * 3, precision_paired=[(True, False)] * 5)


class TestExitCodes:
    def test_ready_exit_0(self, capsys: pytest.CaptureFixture[str]) -> None:
        """READY(recall 개선 AND 정밀도 무회귀) → 종료 코드 0."""
        assert _READY.decision.verdict is Phase2ExitVerdict.READY
        code = cli.main([], runner=lambda **_kw: _READY)
        assert code == 0
        # stdout은 순수 JSON(recall/precision/decision 3축).
        obj = json.loads(capsys.readouterr().out)
        assert set(obj) == {"recall", "precision", "decision"}
        assert obj["decision"]["verdict"] == "ready"

    def test_not_ready_exit_1(self, capsys: pytest.CaptureFixture[str]) -> None:
        """NOT_READY(정밀도 회귀가 recall 개선을 덮어씀) → 종료 코드 1."""
        assert _NOT_READY.decision.verdict is Phase2ExitVerdict.NOT_READY
        code = cli.main([], runner=lambda **_kw: _NOT_READY)
        assert code == 1
        capsys.readouterr()

    def test_no_data_exit_2(self, capsys: pytest.CaptureFixture[str]) -> None:
        """NO_DATA(프로브 부족) → 종료 코드 2(판정 보류·날조 0)."""
        assert _NO_DATA.decision.verdict is Phase2ExitVerdict.NO_DATA
        code = cli.main([], runner=lambda **_kw: _NO_DATA)
        assert code == 2
        capsys.readouterr()

    def test_exit_map_covers_all_verdicts(self) -> None:
        """종료 코드 맵이 결합 판정 3종을 모두 커버(미매핑 → KeyError 방지)."""
        assert set(cli._EXIT_BY_VERDICT) == set(Phase2ExitVerdict)


class TestArgPassing:
    def test_args_forwarded_to_runner(self, capsys: pytest.CaptureFixture[str]) -> None:
        """--alpha·--min-probes·--threshold가 러너에 그대로 전달."""
        seen: dict[str, object] = {}

        def _capture(**kwargs: object) -> Phase2Report:
            seen.update(kwargs)
            return _READY

        cli.main(["--alpha", "0.1", "--min-probes", "7", "--threshold", "0.6"], runner=_capture)
        capsys.readouterr()
        assert seen == {"alpha": 0.1, "min_probes": 7, "threshold": 0.6}

    def test_threshold_defaults_none(self, capsys: pytest.CaptureFixture[str]) -> None:
        """--threshold 생략 → None(러너가 Settings 기본으로 해석)."""
        seen: dict[str, object] = {}

        def _capture(**kwargs: object) -> Phase2Report:
            seen.update(kwargs)
            return _READY

        cli.main([], runner=_capture)
        capsys.readouterr()
        assert seen["threshold"] is None
        assert seen["alpha"] == 0.05 and seen["min_probes"] == 5  # 기본값


def _require_local_embedding() -> None:
    """bge-m3 라이브 도달성 사전체크 — 미도달만 skip(슬110 패턴 인라인·cross-package 회피)."""
    if importlib.util.find_spec("sentence_transformers") is None:
        pytest.skip("sentence-transformers 미설치([embedding] extra) — bge-m3 라이브 skip")
    from whymath_backend.l4.misconception.semantic.provider import LocalEmbeddingProvider

    try:
        LocalEmbeddingProvider().embed(["도달 확인"])
    except (OSError, ImportError) as exc:  # pragma: no cover — 라이브 미도달 경로
        pytest.skip(f"bge-m3 가중치 미도달(HF/네트워크/전이 의존) — 라이브 skip: {exc}")


@pytest.mark.integration
class TestCliLive:
    """기본 러너(라이브 bge-m3·실 프로브셋)로 CLI 전 경로 — 종료 코드·JSON 구조."""

    def test_default_runner_real_embeddings(self, capsys: pytest.CaptureFixture[str]) -> None:
        _require_local_embedding()
        code = cli.main([])  # 기본 _default_runner(라이브 임베딩)
        assert code in {0, 1, 2}  # 유효 결합 판정
        obj = json.loads(capsys.readouterr().out)
        assert set(obj) == {"recall", "precision", "decision"}
        assert obj["decision"]["verdict"] in {v.value for v in Phase2ExitVerdict}
