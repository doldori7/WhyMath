"""오개념 진단 결합 — substring `diagnose()` + 의미 매칭(`semantic_matches`) 병합 (slice 106).

slice 104/105가 의미(임베딩) 매처를 *독립 추가 API*(`semantic_matches`/`SemanticMatcher`)로
뒀고, 이 모듈은 그 둘을 한 후보 리스트로 *결합*한다 — 어느 한쪽 시그니처·동작도 건드리지 않고
(둘 다 불변), 결과 원소도 변형하지 않는 **순수** 합성 계층이다.

────────────────────────────────────────────────────────────────────────────
결합 랭킹 (사용자 확정 결정: substring 우선·semantic 후순)
────────────────────────────────────────────────────────────────────────────
1. **substring 매치를 그대로 위**(`diagnose`가 confidence 내림차순으로 이미 정렬한 순서 보존).
2. 그 아래에 **semantic-only 매치**(substring이 못 잡은 `misconception.id`만) 의미 유사도
   순서 그대로 append. substring이 이미 잡은 id는 *dedup·substring 우선*(semantic 중복 버림).
3. **결합 *끝에서만* top_k 컷** — substr를 top_k로 미리 자르고 semantic을 붙이면 substr가
   semantic에 밀려 잘릴 수 있으므로, 양쪽을 넉넉히 받아 *결합 후* 한 번만 자른다.

**재정렬 금지(핵심 불변)**: 두 confidence 축을 *섞지 않는다*. substring confidence(매칭 신호
비율 0~1)와 semantic confidence(코사인 클램프 0~1)는 *다른 축*이라(models.py
`semantic_similarity` docstring: "confidence와 다른 축 — 진단 신뢰가 아니라 표면 근접도"),
하나의 confidence 키로 전체를 재정렬하면 cos 0.99짜리 의미 후보가 substring conf 0.5짜리
*확정 진단*을 추월하는 *축 혼합 거짓 랭킹*이 생긴다. 그래서 **블록 우선**(substr 블록 → semantic
블록)으로만 정렬한다 — substr가 하나라도 있으면 `matches[0]`은 *반드시* substr다. 이로써
개입 결정(`select_intervention(matches[0])`)이 항상 substring 진단(검증된 표면 신호) 기준으로
구동되고, 의미 매치는 *후보를 넓히는* 보완재로만 노출된다(정직 스코프 — 방향맹 한계 보존).

7계층: 이 결합도 L4 안의 *순수 합성*이다 — provider·index·임베딩을 *모른다*(이미 만들어진
match 리스트 두 개만 받는다). 라이브 의존 0이라 단위테스트가 MisconceptionMatch를 직접 조립해
hermetic하게 검증한다.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from whymath_backend.l4.misconception.diagnose import diagnose
from whymath_backend.l4.misconception.models import MisconceptionMatch
from whymath_backend.l4.misconception.semantic.matcher import semantic_matches
from whymath_backend.l4.misconception.semantic.provider import EmbeddingProvider

_DEFAULT_TOP_K = 3


def combine_diagnoses(
    substring_matches: list[MisconceptionMatch],
    semantic_matches_result: list[MisconceptionMatch],
    *,
    top_k: int = _DEFAULT_TOP_K,
) -> list[MisconceptionMatch]:
    """substring 후보(위) + semantic-only 후보(아래)를 dedup 병합 후 *결합 끝에서만* top_k 컷.

    **순수**: provider·index를 모르고, 입력 두 리스트의 원소를 *변형하지 않으며*(같은 객체를
    그대로 재배치만), 부수효과 0. 호출 순서·내용에만 의존한다.

    랭킹(사용자 확정 — substring 우선·semantic 후순):
      - substring_matches를 *순서 그대로* 위에 둔다(diagnose가 confidence 내림차순으로 정렬한
        결과를 신뢰 — 여기서 재정렬하지 않는다).
      - semantic_matches_result 중 substring이 *이미 잡은* `misconception.id`는 버린다
        (dedup·substring 우선). 남은 semantic-only를 *의미 유사도 순서 그대로* 아래에 append.
      - **재정렬 금지**: 두 confidence 축(substr 신호비율 vs cos 클램프)을 한 키로 섞어
        재정렬하지 않는다 → substr가 하나라도 있으면 결과[0]은 반드시 substr(블록 우선).
      - **top_k는 결합 *끝에서만***: substr를 미리 자르지 않고(잘리면 semantic이 substr를
        밀어냄) 결합 후 한 번만 자른다. top_k<=0이면 빈 리스트.

    동률·순서 안정성은 입력 두 리스트의 순서에 위임한다(diagnose·matcher가 각자 카탈로그
    순서로 안정 정렬). 빈 양쪽 입력은 빈 리스트.
    """
    if top_k <= 0:
        return []
    # substring 블록을 먼저(순서 보존). 이미 잡은 id를 기록해 semantic 중복을 dedup한다.
    combined: list[MisconceptionMatch] = list(substring_matches)
    seen_ids = {m.misconception.id for m in substring_matches}
    # semantic-only(substring이 못 잡은 id)만 아래에 append — 의미 유사도 순서 그대로.
    for sem in semantic_matches_result:
        if sem.misconception.id in seen_ids:
            continue  # dedup·substring 우선(같은 오개념은 substr 결과를 신뢰)
        seen_ids.add(sem.misconception.id)
        combined.append(sem)
    # 결합 *끝에서만* top_k 컷 — substr 우선·semantic 후순 블록 순서를 유지한 채 자른다.
    return combined[:top_k]


@runtime_checkable
class _SemanticMatcherLike(Protocol):
    """캐시된 의미 매처 좌석 — `combined_diagnose`가 재사용할 `.match`만 좁게 선언.

    `SemanticMatcher.match(student_solution, *, top_k, threshold)`의 부분집합. 사전 임베딩
    캐시를 재사용하려면 일회성 `semantic_matches` 대신 이 좌석을 넘긴다(03 matcher.py 정석).
    """

    def match(
        self, student_solution: str, *, top_k: int, threshold: float
    ) -> list[MisconceptionMatch]:
        """학생 텍스트 → 의미 유사 오개념 후보(SemanticMatcher.match의 부분집합)."""
        ...


def combined_diagnose(
    student_solution: str,
    *,
    provider: EmbeddingProvider,
    matcher: _SemanticMatcherLike | None = None,
    top_k: int = _DEFAULT_TOP_K,
    threshold: float | None = None,
) -> list[MisconceptionMatch]:
    """편의 진입점 — `diagnose()` + 의미 매칭을 한 번에 돌려 `combine_diagnoses`로 병합.

    `diagnose()`(substring+regex)와 의미 매칭을 *각각 넉넉히*(결합 끝 컷 전제) 뽑아 결합한다.
    `matcher`가 주어지면 그 `.match`(사전 임베딩 캐시 재사용)를, 없으면 `semantic_matches(...)`
    (일회성 — 매 호출 카탈로그 재임베딩)를 쓴다. 호출자(오케스트레이터)는 보통 SemanticMatcher
    인스턴스를 캐시해 `matcher=`로 넘긴다(03 matcher.py docstring 정석). threshold 미지정 시
    의미 매처가 Settings 기본(0.55)을 쓴다(matcher 경로는 threshold가 필수 인자라 미지정 시
    `semantic_matches`만 Settings 폴백을 제공 — matcher 재사용 시 호출자가 threshold를 준다).

    이 함수는 *동기*다 — `diagnose`·`semantic_matches`·`matcher.match` 모두 동기(L4
    misconception 경로는 sync). 비블로킹/폴백/게이트는 *호출자*(api/coach.py `_compute_matches`)
    책임이고, 본 함수는 순수 합성 + 두 매처 호출만 한다(라우터의 to_thread·try/except와 분리).
    """
    substr = diagnose(student_solution, top_k=top_k)
    if matcher is not None and threshold is not None:
        sem = matcher.match(student_solution, top_k=top_k, threshold=threshold)
    else:
        # matcher가 threshold 없이 주어지면 Settings 기본을 쓰는 일회성 진입점으로 폴백한다
        # (matcher.match는 threshold가 필수라 Settings 폴백을 못 받음 — 캐시 재사용은 threshold
        # 명시가 전제). 캐시 이점이 필요하면 호출자가 threshold를 함께 넘긴다.
        sem = semantic_matches(
            student_solution, provider=provider, top_k=top_k, threshold=threshold
        )
    return combine_diagnoses(substr, sem, top_k=top_k)


__all__ = ["combine_diagnoses", "combined_diagnose"]
