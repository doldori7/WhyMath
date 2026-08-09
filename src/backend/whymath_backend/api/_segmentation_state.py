"""단계 분해(NLP-03) 0-전이 제출 관측 — app.state 인프로세스 카운터(신규 DB 필드 0).

배경(`docs/architecture/nlp_module_gap_review.md` §3 D3 acceptance ③, CLAUDE.md 이중
회계 원칙): `api/coach.py`의 `CoachRequest.solution_steps: list[str] | None`은 **클라이언트가
이미 분해해서 보낸** 단계 목록이다 — 백엔드가 원문을 받아 직접 분해하는 라이브 경로는 없다
(이 태스크 범위에서 새 엔드포인트를 만들지 않는다). 그래서 관측 가능한 신호는 "요청에 실린
`solution_steps`의 길이가 1 이하인 비율"이다 — 클라이언트 쪽 분해(`_splitSteps`/
`_unwrapDisplaylines`)가 degenerate(0-전이)했을 가능성의 대리 신호다(2026-07-20 실기기
사고와 같은 패턴의 재발 감지).

`api/_ocr_state.py::OcrReachCounters`와 동형 패턴(불변 snapshot dataclass·인프로세스
카운터·`/health/ready` 노출)이나 *병렬 구축*이다 — 어휘(`total`/`single_or_zero_step`)도
의미(분해 degenerate 축, OCR 가용성 축과 무관)도 달라 기존 클래스에 욱여넣지 않는다
(`_ocr_state.py` 모듈 docstring의 이유와 동형).

None-vs-zero: OCR과 달리 이 축은 "요청 0건"과 "0-전이 0건"이 자연스럽게 구분된다
(`total=0`이면 그 자체로 관측 대상 요청이 없었다는 뜻이라 `total`이 분모 역할을 한다) —
`OcrReachSnapshot.enabled` 같은 별도 bool 플래그는 억지로 만들지 않는다.

새 DB 테이블·스키마 필드 0 — 전부 인프로세스 카운터다(이 태스크의 범위 제약).
"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Request

__all__ = [
    "SEGMENTATION_COUNTERS_KEY",
    "SolutionSegmentationCounters",
    "SolutionSegmentationSnapshot",
    "ensure_segmentation_counters",
    "get_segmentation_counters",
    "get_segmentation_snapshot",
]

# app.state 속성 키 — create_app(app.py)이 저장하고 아래 접근자가 조회(단일 출처,
# `_ocr_state.OCR_COUNTERS_KEY`와 동일 관례).
SEGMENTATION_COUNTERS_KEY = "solution_segmentation_counters"


@dataclass(frozen=True, slots=True)
class SolutionSegmentationSnapshot:
    """0-전이 제출 관측의 불변 스냅샷 — `/health/ready` 노출 원천.

    `total`은 `solution_steps`가 있고(None 아님) 비어있지 않은 요청 총계(분모).
    `single_or_zero_step`은 그중 `len(solution_steps) <= 1`인 건수(분자) — 클라이언트
    분해가 degenerate했을 가능성의 대리 신호다. `total=0`이면 관측 대상 요청 자체가
    없었다는 뜻이고(측정 대상 요청 부재), `single_or_zero_step`이 `total`과 같은 비율로
    크면 클라 분해 드리프트가 실사용에서 재발 중이라는 신호다.
    """

    total: int
    single_or_zero_step: int


class SolutionSegmentationCounters:
    """`solution_steps` 0-전이 제출 관측 카운터 (NLP-03 acceptance ③).

    `ops/service_health.ServiceMetrics`·`api/_ocr_state.OcrReachCounters`와 동일한 동시성
    전제(단일 asyncio 이벤트 루프·await 없는 순수 동기 증가 — 락 불요)를 따르되, 어휘·의미가
    달라 *병렬 구축*이다(재사용 아님).
    """

    __slots__ = ("_total", "_single_or_zero_step")

    def __init__(self) -> None:
        self._total = 0
        self._single_or_zero_step = 0

    def record(self, solution_steps: list[str] | None) -> None:
        """요청 1건의 `solution_steps`를 관측 — None·빈 리스트는 관측 대상 아님(카운트 안 함).

        분해 결과 자체를 안 실은 요청(클라가 미분해 텍스트만 보낸 경우 등)은 "0-전이"와
        무관한 다른 상태라 분모에서 제외한다(비어 있음 ≠ degenerate 분해).
        """
        if not solution_steps:
            return
        self._total += 1
        if len(solution_steps) <= 1:
            self._single_or_zero_step += 1

    def snapshot(self) -> SolutionSegmentationSnapshot:
        """현재 카운터의 불변 스냅샷."""
        return SolutionSegmentationSnapshot(
            total=self._total,
            single_or_zero_step=self._single_or_zero_step,
        )


def ensure_segmentation_counters(
    app_state_holder: object,
) -> SolutionSegmentationCounters:
    """app.state의 `SolutionSegmentationCounters`를 반환 — 없으면 새로 만들어 심는다.

    `create_app`이 정상 구성하면 이 함수를 거치지 않고도 항상 카운터가 있어야 하지만
    (`ensure_ocr_counters`와 동형 이유), lifespan이 발화하지 않는 테스트 경로나 app.state를
    직접 조작하는 hermetic 테스트를 위해 idempotent 접근자를 둔다.
    """
    counters = getattr(app_state_holder.state, SEGMENTATION_COUNTERS_KEY, None)  # type: ignore[attr-defined]
    if counters is None:
        counters = SolutionSegmentationCounters()
        app_state_holder.state.__setattr__(  # type: ignore[attr-defined]
            SEGMENTATION_COUNTERS_KEY, counters
        )
    return counters


def get_segmentation_snapshot(app_state_holder: object) -> SolutionSegmentationSnapshot:
    """현재 0-전이 제출 관측 스냅샷 — `/health/ready` 노출용(읽기 전용·부수효과 없음)."""
    return ensure_segmentation_counters(app_state_holder).snapshot()


def get_segmentation_counters(request: Request) -> SolutionSegmentationCounters:
    """FastAPI 디펜던시 — 요청의 app.state에서 `SolutionSegmentationCounters`를 꺼낸다.

    `api/coach.py`의 세 핸들러(`/coach`·`/coach/sessions`·`/coach/sessions/{id}/turns`)가
    `Depends`로 주입받아 `record(body.solution_steps)`를 호출한다.
    """
    return ensure_segmentation_counters(request.app)
