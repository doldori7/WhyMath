"""WH-1 2단계 종료 게이트 — 의미 매처 후보 결선(`harness/agreement_gate_semantic.py`).

단위(hermetic·결정론)는 ① 어댑터(top-1 id 추출·임계값 미달 None) ② *실* `SemanticMatcher`
경로(FakeEmbeddingProvider·결정론)를 통과한 IMPROVED/NOT_IMPROVED를 검증한다 — 단일 항목
카탈로그 + 임계값으로 후보 hit/miss를 결정론으로 통제한다(임베딩 비의존). 라이브 임베딩
(bge-m3)으로 실 라벨 프로브셋을 도는 결선은 integration(WHYMATH_RUN_INTEGRATION) 한 건.
"""

from __future__ import annotations

import importlib.util

import pytest
from whymath_backend.harness.agreement_gate import AgreementVerdict, Phase2ExitVerdict
from whymath_backend.harness.agreement_gate_semantic import (
    run_semantic_agreement_gate,
    run_semantic_phase2_exit,
    semantic_candidate_matcher,
)
from whymath_backend.l4.misconception.catalog import CATALOG
from whymath_backend.l4.misconception.models import Misconception, MisconceptionMatch
from whymath_backend.l4.misconception.semantic.provider import FakeEmbeddingProvider

# 결정론 통제용 — 카탈로그 첫 항목(실 오개념 id). 단일 항목 카탈로그로 의미 매처가 *항상*
# 이 id를 후보로 내게 하고(임계값 -∞), 베이스라인(substring)은 gibberish 프로브에 0매칭.
_M0: Misconception = CATALOG[0]


class _StubMatcher:
    """`SemanticMatcher.match` 좌석 — 주입된 결과를 그대로 반환(임베딩 비의존 어댑터 단위)."""

    def __init__(self, out: list[MisconceptionMatch]) -> None:
        self._out = out

    def match(
        self, student_solution: str, *, top_k: int, threshold: float
    ) -> list[MisconceptionMatch]:
        return self._out


class TestSemanticCandidateMatcher:
    def test_returns_top1_id(self) -> None:
        """매치 있으면 top-1 매치의 오개념 id."""
        stub = _StubMatcher([MisconceptionMatch(misconception=_M0, confidence=0.9)])
        candidate = semantic_candidate_matcher(stub, threshold=0.5)
        assert candidate("아무 진술") == _M0.id

    def test_returns_none_on_empty(self) -> None:
        """임계값 통과 후보 0(빈 결과) → None(억지 매칭 금지·그 프로브 miss)."""
        candidate = semantic_candidate_matcher(_StubMatcher([]), threshold=0.5)
        assert candidate("아무 진술") is None


class TestRunSemanticAgreementGate:
    """*실* SemanticMatcher(FakeEmbeddingProvider) 경로를 단일 항목 카탈로그로 결정론 통제."""

    def _gibberish_probes(self, n: int) -> list[tuple[str, str]]:
        # substring `diagnose`가 0매칭하는 무의미 진술 + expected_id = 단일 카탈로그 항목.
        return [(f"zzqqxx{i}", _M0.id) for i in range(n)]

    def test_semantic_beats_baseline_improved(self) -> None:
        """임계값 -∞ → 후보 전부 hit·베이스라인(gibberish) 전부 miss → IMPROVED(p=0.03125)."""
        gate = run_semantic_agreement_gate(
            provider=FakeEmbeddingProvider(dim=16),
            threshold=-2.0,  # 어떤 코사인도 통과 → 단일 항목을 항상 후보로
            catalog=(_M0,),
            probes=self._gibberish_probes(5),
        )
        assert gate.verdict is AgreementVerdict.IMPROVED
        assert gate.baseline_recall == 0.0 and gate.candidate_recall == 1.0
        assert gate.discordant_candidate_only == 5 and gate.discordant_baseline_only == 0
        assert gate.p_value is not None and gate.p_value < 0.05
        assert gate.n_probes == 5

    def test_threshold_too_high_not_improved(self) -> None:
        """임계값 2.0(코사인 상한 초과) → 후보 전부 miss·베이스라인도 miss → 동등 NOT_IMPROVED."""
        gate = run_semantic_agreement_gate(
            provider=FakeEmbeddingProvider(dim=16),
            threshold=2.0,
            catalog=(_M0,),
            probes=self._gibberish_probes(5),
        )
        assert gate.verdict is AgreementVerdict.NOT_IMPROVED
        assert gate.baseline_recall == 0.0 and gate.candidate_recall == 0.0

    def test_default_threshold_resolves_from_settings(self) -> None:
        """threshold 미지정 → Settings 기본(0.55)로 해석·크래시 없이 유효 게이트 반환."""
        probes = self._gibberish_probes(6)
        gate = run_semantic_agreement_gate(
            provider=FakeEmbeddingProvider(dim=16),
            catalog=(_M0,),
            probes=probes,
        )
        # 임계값은 데이터 의존이라 verdict는 단언하지 않고 구조만(유효 enum·프로브 수).
        assert gate.verdict in set(AgreementVerdict)
        assert gate.n_probes == 6


class TestRunSemanticPhase2Exit:
    """결합 — recall 게이트 + 정밀도 가드를 의미 매처 후보로 한 번에(실 프로브셋·Fake provider)."""

    def test_runs_over_real_probes_structural(self) -> None:
        """실 라벨(recall 61 + fp 33) 프로브셋에 Fake provider → 결정론·구조 유효 결합 판정."""
        exit_ = run_semantic_phase2_exit(provider=FakeEmbeddingProvider(dim=16))
        # verdict는 데이터·임계값 의존이라 구조만 단언(유효 enum·두 축 판정 채워짐).
        assert exit_.verdict in set(Phase2ExitVerdict)
        assert exit_.recall_verdict in set(AgreementVerdict)
        # 정밀도 가드도 실제로 돌아 결합에 반영됐는지(두 축 모두 채워짐).
        assert exit_.precision_verdict is not None


def _require_local_embedding() -> None:
    """bge-m3 라이브 도달성 사전체크 — 미도달만 skip, 코드 버그는 fail(슬110 패턴 인라인).

    `tests/backend`는 패키지가 아니라 `l4._live_resources`를 cross-package import 못 해
    동일 사전체크를 인라인한다(자원 예외 OSError/ImportError만 skip).
    """
    if importlib.util.find_spec("sentence_transformers") is None:
        pytest.skip("sentence-transformers 미설치([embedding] extra) — bge-m3 라이브 skip")
    from whymath_backend.l4.misconception.semantic.provider import LocalEmbeddingProvider

    try:
        LocalEmbeddingProvider().embed(["도달 확인"])
    except (OSError, ImportError) as exc:  # pragma: no cover — 라이브 미도달 경로
        pytest.skip(f"bge-m3 가중치 미도달(HF/네트워크/전이 의존) — 라이브 skip: {exc}")


@pytest.mark.integration
class TestSemanticAgreementGateLive:
    """라이브 임베딩(bge-m3)으로 실 라벨 프로브셋 전체를 의미 매처 후보로 게이트 실행."""

    def test_real_probes_real_embeddings_structural(self) -> None:
        from whymath_backend.l4.misconception.semantic.provider import LocalEmbeddingProvider

        _require_local_embedding()
        gate = run_semantic_agreement_gate(provider=LocalEmbeddingProvider())
        # verdict는 데이터·임계값 의존(IMPROVED 단언 불가) — 구조 타당성만 단언.
        assert gate.verdict in set(AgreementVerdict)
        assert gate.n_probes > 0  # 실 라벨 recall 프로브셋 로드됨
        assert gate.baseline_recall is not None and 0.0 <= gate.baseline_recall <= 1.0
        assert gate.candidate_recall is not None and 0.0 <= gate.candidate_recall <= 1.0
        assert gate.p_value is not None and 0.0 <= gate.p_value <= 1.0
