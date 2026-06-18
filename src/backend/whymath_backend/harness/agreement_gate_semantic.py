"""WH-1 2단계 종료 게이트 — 의미 매처 후보 결선(`agreement_gate` ↔ `SemanticMatcher`).

`agreement_gate.py`가 남긴 후속 *"의미 매처 후보 결선"*을 채운다. §8.4 2단계 종료 기준의
후보(candidate)를 *의미 매처*(임베딩·pgvector)로 싣고 substring 베이스라인과 라벨 프로브셋에서
McNemar로 견주어, 게이트가 실제로 "의미 매처가 substring 기준선을 **유의하게** 능가하는가"를
판정하게 한다(단순 "조금 높다"가 아니라 *유의 개선*만 2단계 종료 충족).

  - **어댑터(`semantic_candidate_matcher`)**: `SemanticMatcher.match` top-1을 게이트 `Matcher`
    (진술→top-1 오개념 id·임계값 미달이면 None)로 감싼다. 게이트는 *top-1 일치율(recall)*을
    재므로 top_k=1만 본다. 임계값 통과 후보가 없으면 None=그 프로브 miss(억지 매칭 금지·§3.3).
  - **결선(`run_semantic_agreement_gate`)**: `SemanticMatcher`를 *1회* 구축(카탈로그 사전
    임베딩 캐시·항목당 재임베딩 0)해 후보로 싣고 `run_agreement_gate`(베이스라인=substring
    기본·동일 라벨 프로브셋)에 넘긴다. `threshold` 미지정 시 Settings 기본(보수적 0.55).
  - **provider 주입 필수**(좌석): 테스트는 `FakeEmbeddingProvider`(결정론·hermetic), 프로덕션은
    `build_provider`(local/openai). 라이브 임베딩 결선은 integration(WHYMATH_RUN_INTEGRATION).

정직 스코프(`agreement_gate.py`와 동일): *오프라인·시스템 지표*다 — 라벨 프로브셋의 top-1
recall이지 LIVE per-user ground-truth가 아니다. 의미 매처는 패러프레이즈·동의어 recall은 올리나
*방향·부정·등치*는 못 가린다(임베딩 방향맹·`semantic/matcher.py` docstring) — 게이트는 그
**순효과**를 substring 대비로 잴 뿐, 의미 매처가 *옳다*고 주장하지 않는다.

계층(설계 §1): 횡단 인프라(하네스). L4 의미 매처(`SemanticMatcher`)·substring(`diagnose`)을
*조회만* 한다. 범위 밖(후속): pgvector 사전 임베딩 인덱스 결선(`index=PgVectorIndex`)·게이트
결과 API 노출·LIVE per-user 일치율(문항-오개념 태깅·attempt 진단 기록).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from whymath_backend.config import get_settings
from whymath_backend.harness.agreement_gate import (
    _DEFAULT_ALPHA,
    _MIN_PROBES,
    AgreementGate,
    Matcher,
    Phase2Exit,
    Phase2Report,
    evaluate_phase2_exit,
    run_agreement_gate,
    run_precision_guard,
)
from whymath_backend.l4.misconception.catalog import CATALOG
from whymath_backend.l4.misconception.models import Misconception, MisconceptionMatch
from whymath_backend.l4.misconception.semantic.index import VectorIndex
from whymath_backend.l4.misconception.semantic.matcher import SemanticMatcher
from whymath_backend.l4.misconception.semantic.provider import EmbeddingProvider

__all__ = [
    "run_semantic_agreement_gate",
    "run_semantic_phase2_exit",
    "run_semantic_phase2_report",
    "semantic_candidate_matcher",
]


class _MatcherLike(Protocol):
    """`SemanticMatcher.match` 시그니처 좌석 — 테스트가 가짜 매처를 주입할 수 있게 한다."""

    def match(
        self, student_solution: str, *, top_k: int, threshold: float
    ) -> list[MisconceptionMatch]: ...


def semantic_candidate_matcher(matcher: _MatcherLike, *, threshold: float) -> Matcher:
    """의미 매처(또는 호환 좌석)를 게이트 후보 `Matcher`로 감싼다 — top-1 오개념 id.

    각 진술에 `matcher.match(top_k=1, threshold=…)`을 적용해 top-1 매치의 오개념 id를 반환하고,
    임계값 통과 후보가 없으면 None(그 프로브 miss·억지 매칭 금지·§3.3). 게이트는 top-1 일치율
    (recall)을 재므로 top_k=1만 본다(`agreement_gate` 규약). `threshold`는 호출자가 고정한다
    (게이트는 *그 임계값에서의* 의미 매처 성능을 잰다 — 임계값 의존성을 명시적으로 둔다).
    """

    def _match(statement: str) -> str | None:
        results = matcher.match(statement, top_k=1, threshold=threshold)
        return results[0].misconception.id if results else None

    return _match


def run_semantic_agreement_gate(
    *,
    provider: EmbeddingProvider,
    threshold: float | None = None,
    index: VectorIndex | None = None,
    catalog: tuple[Misconception, ...] = CATALOG,
    probes: Sequence[tuple[str, str]] | None = None,
    alpha: float = _DEFAULT_ALPHA,
    min_probes: int = _MIN_PROBES,
) -> AgreementGate:
    """의미 매처를 후보로, substring을 베이스라인으로 라벨 프로브셋에서 McNemar 게이트 실행.

    `SemanticMatcher`를 *1회* 구축(카탈로그 사전 임베딩 캐시·항목당 재임베딩 0)해 후보로 싣고,
    `run_agreement_gate`(베이스라인=substring 기본·`probes` 생략 시 패키지 라벨 recall 프로브)에
    넘긴다. `threshold` 미지정 시 `Settings.misconception_semantic_threshold`(보수적 0.55).
    `provider`는 주입 필수 — 테스트는 `FakeEmbeddingProvider`, 프로덕션은 `build_provider`.
    `index` 생략 시 `SemanticMatcher`가 `InMemoryVectorIndex` 자체 생성(영속 `PgVectorIndex`
    주입은 후속).
    """
    candidate = _build_semantic_candidate(
        provider=provider, threshold=threshold, index=index, catalog=catalog
    )
    return run_agreement_gate(
        candidate=candidate, probes=probes, alpha=alpha, min_probes=min_probes
    )


def _build_semantic_candidate(
    *,
    provider: EmbeddingProvider,
    threshold: float | None,
    index: VectorIndex | None,
    catalog: tuple[Misconception, ...],
) -> Matcher:
    """의미 매처를 *1회* 구축(카탈로그 사전 임베딩 캐시)해 게이트 후보 `Matcher`로 만든다.

    `threshold` 미지정 시 `Settings.misconception_semantic_threshold`(보수적 0.55). recall 게이트·
    정밀도 가드가 *같은* 후보(같은 사전 임베딩)를 공유하도록 빌드를 한 곳에 모은다.
    """
    resolved_threshold = (
        threshold if threshold is not None else get_settings().misconception_semantic_threshold
    )
    matcher = SemanticMatcher(provider=provider, index=index, catalog=catalog)
    return semantic_candidate_matcher(matcher, threshold=resolved_threshold)


def run_semantic_phase2_report(
    *,
    provider: EmbeddingProvider,
    threshold: float | None = None,
    index: VectorIndex | None = None,
    catalog: tuple[Misconception, ...] = CATALOG,
    alpha: float = _DEFAULT_ALPHA,
    min_probes: int = _MIN_PROBES,
) -> Phase2Report:
    """의미 매처 후보로 2단계 종료 *전체 리포트* — recall 게이트 + 정밀도 가드 + 결합 판정.

    `SemanticMatcher`를 *1회* 구축(사전 임베딩 캐시)한 후보를 recall 게이트(라벨 recall 프로브)와
    정밀도 가드(FP 프로브)에 *공유* 적용하고 `evaluate_phase2_exit`로 묶어, 세 결과(두 축 수치 +
    결합 판정)를 `Phase2Report`로 반환한다. ops/스크립트가 *왜* 그 판정인지 근거와 함께 읽도록
    하는 직렬화 표면이다. provider 주입 필수(테스트=Fake·프로덕션=build_provider).
    """
    candidate = _build_semantic_candidate(
        provider=provider, threshold=threshold, index=index, catalog=catalog
    )
    recall = run_agreement_gate(candidate=candidate, alpha=alpha, min_probes=min_probes)
    precision = run_precision_guard(candidate=candidate, alpha=alpha, min_probes=min_probes)
    decision = evaluate_phase2_exit(recall, precision)
    return Phase2Report(recall=recall, precision=precision, decision=decision)


def run_semantic_phase2_exit(
    *,
    provider: EmbeddingProvider,
    threshold: float | None = None,
    index: VectorIndex | None = None,
    catalog: tuple[Misconception, ...] = CATALOG,
    alpha: float = _DEFAULT_ALPHA,
    min_probes: int = _MIN_PROBES,
) -> Phase2Exit:
    """의미 매처 후보로 2단계 종료 *결합* 판정만 — recall 유의 개선 AND 정밀도 무회귀.

    `run_semantic_phase2_report`의 `decision`만 필요한 호출자용 얇은 래퍼(후보 1회 구축·두 축
    공유는 동일). 전체 수치가 필요하면 `run_semantic_phase2_report`를 쓴다.
    """
    return run_semantic_phase2_report(
        provider=provider,
        threshold=threshold,
        index=index,
        catalog=catalog,
        alpha=alpha,
        min_probes=min_probes,
    ).decision
