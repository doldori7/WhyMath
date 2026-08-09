"""OCR 부품(`OcrComponents`)을 app.state에 보관·조회 — app.py(저장)와 ocr 라우터(조회) 공유.

`OcrComponents`는 *앱 수명 동안 공유*되는 의존(모델 1회 로드)이라, `_l3_state.py`(provider·
cache·trace)와 동형으로 `create_app`/lifespan이 `app.state`에 저장하고 라우터가
`request.app.state`로 조회한다. 이 모듈로 키·세터·게터를 모아 app.py와 라우터가 *순환 import
없이* 공유한다(라우터가 app.py를 import하면 순환).

OCR 비활성(`ocr_enabled=False`)·미로드 상태에서 `get_ocr_components`는 **503**으로 명확히
보고한다(조용한 폴백 없음·CLAUDE.md 가용성 우선 — 학생에겐 '잠시 후 재시도'가 정직·안전).

NLP-01 (사유 분리·도달 관측)
---------------------------
지금까지는 `OcrComponents | None`만 저장돼 None이면 이유를 몰라도 항상 같은 503 문구였다
— "비활성(config off)"과 "부품 적재 실패(import·모델 자산 부재)"가 모바일·로그 양쪽에서
무변별이었다(`docs/architecture/nlp_module_gap_review.md` §3 D1). 이 모듈은 두 가지를
더한다:

1. **사유(`OcrUnavailableReason`)** — `set_ocr_components`가 components와 함께(또는 대신)
   `unavailable_reason`을 받는다. HTTP 상태코드는 항상 503으로 유지하되(모바일은 상태코드
   만으로 판단하는 별도 태스크 진행 중 — 상태코드를 바꾸면 그 작업과 충돌), `detail`을
   `{"code", "message"}` dict로 바꿔 *기계 판독 가능한* 구분을 준다.
2. **도달 카운터(`OcrReachCounters`)** — 요청·성공·사유별 503을 인프로세스로 센다
   (`ops/service_health.ServiceMetrics`와 동형 — 동시성 전제도 동일: 단일 asyncio
   이벤트 루프·await 없는 동기 증가라 락 불요). `OcrReachSnapshot.enabled`이 '미활성'과
   '활성 상태에서 0건'을 가른다(None-vs-zero 원칙 — `ServiceMetrics.window_error_rate`
   와 동형이나, 여기선 bool 플래그 하나로 충분하다: `enabled=False`면 카운트는 애초에
   '측정 대상 아님'이지 '측정했더니 0'이 아니다).

새 DB 테이블·스키마 필드는 없다 — 전부 app.state 인프로세스 상태다(이 태스크의 범위 제약).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Literal

from fastapi import HTTPException, Request, status

from whymath_backend.l5.ocr.factory import OcrComponents

logger = logging.getLogger(__name__)

# app.state 속성 키 — create_app/lifespan(app.py)이 저장하고 아래 getter가 조회(단일 출처).
OCR_COMPONENTS_KEY = "ocr_components"
# 비활성 사유(components가 None일 때만 유의미) — components가 있으면 항상 None.
OCR_UNAVAILABLE_REASON_KEY = "ocr_unavailable_reason"
# 도달 관측 카운터(OcrReachCounters) — create_app이 앱 수명 동안 1개를 심는다.
OCR_COUNTERS_KEY = "ocr_reach_counters"

# 503 사유 어휘 — "config off"와 "부품 적재 실패"만 구분한다(그 이상 세분화는 과공학 —
# 소비자는 모바일 로그·운영자 대시보드뿐이고 둘 다 이 2분법이면 충분하다).
OcrUnavailableReason = Literal["disabled", "load_failed"]

# 사유별 503 detail — dict 형태(code·message)로 기계 판독 가능하게 분리한다. HTTP status
# code는 항상 503으로 유지(모바일 축은 상태코드만으로 비활성/실패를 판단하는 별도 세션
# 진행 중 — 여기서 상태코드를 바꾸면 그 작업과 충돌한다). 사람이 읽는 문구는 기존과
# 크게 다르지 않게 유지한다(핵심은 `code` 필드의 기계 판독성).
_UNAVAILABLE_DETAIL: dict[OcrUnavailableReason, dict[str, str]] = {
    "disabled": {
        "code": "ocr_disabled",
        "message": "OCR 기능이 현재 비활성입니다(잠시 후 재시도).",
    },
    "load_failed": {
        "code": "ocr_load_failed",
        "message": "OCR 부품 적재에 실패했습니다(잠시 후 재시도).",
    },
}
# lifespan이 발화하지 않아(TestClient without `with`) app.state에 사유가 아예 없는 경우의
# 기본값 — 기존 동작(단일 503 문구)과 동형인 "비활성"으로 취급한다.
_DEFAULT_UNAVAILABLE_REASON: OcrUnavailableReason = "disabled"


@dataclass(frozen=True, slots=True)
class OcrReachSnapshot:
    """OCR 도달 관측의 불변 스냅샷 — `/health/ready` 노출 원천.

    `enabled`은 *현재 설정 의도*를 나타낸다(`Settings.ocr_enabled`의 파생값) — components가
    로드돼 있거나(정상) 로드를 시도했다가 실패했으면(load_failed) True, 애초에 꺼져
    있으면(disabled) False다. `enabled=False`일 때 나머지 카운트가 전부 0이어도 그건
    '측정했더니 0건'이 아니라 '이 기능은 측정 대상이 아니다'로 읽어야 한다(None-vs-zero —
    `ops/service_health.MetricsSnapshot`의 None 필드와 같은 취지를, 여기선 bool 플래그로
    표현한다).
    """

    enabled: bool
    requests_total: int
    succeeded: int
    unavailable_disabled: int
    unavailable_load_failed: int


class OcrReachCounters:
    """OCR 요청 도달 관측 카운터 — 요청·성공·사유별 503(비활성/적재실패)을 센다.

    `ops/service_health.ServiceMetrics`와 동일한 동시성 전제(단일 asyncio 이벤트 루프·
    await 없는 순수 동기 증가 — 락 불요)를 따르되, *재사용이 아니라 병렬 구축*이다.
    `api/_degradation.py` 모듈 docstring의 이유와 동형: OCR 도달 관측은 어휘
    (`requests_total`/`succeeded`/`unavailable_disabled`/`unavailable_load_failed`)도
    의미(가용성 축, 강등 회계 아님)도 달라 기존 클래스에 욱여넣지 않는다.
    """

    __slots__ = (
        "_requests_total",
        "_succeeded",
        "_unavailable_disabled",
        "_unavailable_load_failed",
    )

    def __init__(self) -> None:
        self._requests_total = 0
        self._succeeded = 0
        self._unavailable_disabled = 0
        self._unavailable_load_failed = 0

    def record_request(self) -> None:
        """요청 1건이 `get_ocr_components` 디펜던시에 도달했다(성공/실패 이전)."""
        self._requests_total += 1

    def record_success(self) -> None:
        """OCR 파이프라인이 정상 완료돼 응답을 반환했다(핸들러가 호출)."""
        self._succeeded += 1

    def record_unavailable(self, reason: OcrUnavailableReason) -> None:
        """503(비활성/적재실패) 1건 기록 — 사유별로 분리 집계."""
        if reason == "disabled":
            self._unavailable_disabled += 1
        else:
            self._unavailable_load_failed += 1

    def snapshot(self, *, enabled: bool) -> OcrReachSnapshot:
        """현재 카운터의 불변 스냅샷 — `enabled`은 호출자가 현재 상태에서 판단해 넘긴다."""
        return OcrReachSnapshot(
            enabled=enabled,
            requests_total=self._requests_total,
            succeeded=self._succeeded,
            unavailable_disabled=self._unavailable_disabled,
            unavailable_load_failed=self._unavailable_load_failed,
        )


def set_ocr_components(
    app_state_holder: object,
    components: OcrComponents | None,
    *,
    unavailable_reason: OcrUnavailableReason | None = None,
) -> None:
    """app(또는 app.state 보유 객체)에 OCR 부품 + 비활성 사유를 저장 — lifespan이 부팅 시 1회 호출.

    `app_state_holder`는 `.state`를 가진 FastAPI 앱이다(타입을 object로 둬 app.py 순환 회피).

    `components`가 `None`이면 `unavailable_reason`이 **필수**다(어느 503 사유인지 명시 —
    이유 없는 None 저장을 막아 사유 분리를 코드 계약으로 강제한다). `components`가 있으면
    `unavailable_reason`은 반드시 `None`(성공 상태에 사유를 남기지 않는다).
    """
    if components is None and unavailable_reason is None:
        raise ValueError("components가 None이면 unavailable_reason을 명시해야 합니다.")
    if components is not None and unavailable_reason is not None:
        raise ValueError("components가 있으면 unavailable_reason은 None이어야 합니다.")
    app_state_holder.state.__setattr__(OCR_COMPONENTS_KEY, components)  # type: ignore[attr-defined]
    app_state_holder.state.__setattr__(  # type: ignore[attr-defined]
        OCR_UNAVAILABLE_REASON_KEY, unavailable_reason
    )


def ensure_ocr_counters(app_state_holder: object) -> OcrReachCounters:
    """app.state의 `OcrReachCounters`를 반환 — 없으면 새로 만들어 심는다(create_app 규약).

    `create_app`이 정상적으로 앱을 구성하면 이 함수를 거치지 않고도 항상 카운터가 있어야
    하지만(ServiceMetrics와 동일하게 팩토리가 명시적으로 심는다), lifespan이 발화하지
    않는 테스트 경로(`TestClient(app)` without `with`)나 app.state를 직접 조작하는
    hermetic 테스트를 위해 idempotent 접근자를 둔다 — 없으면 1회 생성해 심는다.
    """
    counters = getattr(app_state_holder.state, OCR_COUNTERS_KEY, None)  # type: ignore[attr-defined]
    if counters is None:
        counters = OcrReachCounters()
        app_state_holder.state.__setattr__(OCR_COUNTERS_KEY, counters)  # type: ignore[attr-defined]
    return counters


def get_ocr_reach_snapshot(app_state_holder: object) -> OcrReachSnapshot:
    """현재 OCR 도달 관측 스냅샷 — `/health/ready` 노출용(읽기 전용·부수효과 없음).

    `enabled`은 저장된 부품/사유 상태에서 파생한다 — 별도 bool을 이중 저장하지 않아
    드리프트를 원천 차단한다(`components`가 있거나 사유가 `load_failed`면 설정 의도는
    '켜짐'이다).
    """
    counters = ensure_ocr_counters(app_state_holder)
    components: OcrComponents | None = getattr(
        app_state_holder.state, OCR_COMPONENTS_KEY, None  # type: ignore[attr-defined]
    )
    reason: OcrUnavailableReason | None = getattr(
        app_state_holder.state,  # type: ignore[attr-defined]
        OCR_UNAVAILABLE_REASON_KEY,
        None,
    )
    enabled = components is not None or reason == "load_failed"
    return counters.snapshot(enabled=enabled)


def get_ocr_counters(request: Request) -> OcrReachCounters:
    """FastAPI 디펜던시 — 요청의 app.state에서 `OcrReachCounters`를 꺼낸다(성공 기록용).

    `post_ocr`/`post_ocr_pages` 핸들러가 정상 완료 후 `record_success()`를 호출하기 위한
    주입 지점이다(`get_ocr_components`는 실패/도달만 세고, 성공은 핸들러가 안다 — 파이프라인
    호출 자체가 예외를 던질 수 있어 핸들러 완료 시점이 유일하게 정직한 '성공' 신호다).
    """
    return ensure_ocr_counters(request.app)


def get_ocr_components(request: Request) -> OcrComponents:
    """요청의 app.state에서 OCR 부품을 꺼낸다 — 비활성/미로드면 503(조용한 폴백 없음).

    OCR이 꺼져 있거나(`ocr_enabled=False`) 부품 적재가 실패했으면 app.state에 키가 없거나
    None이라 503으로 명확히 보고한다(500 스택트레이스 금지 — 가용성 우선·정직).

    NLP-01: 503 자체는 상태코드를 유지하되(모바일이 상태코드만으로 판단), `detail`을
    사유별 dict(`{"code", "message"}`)로 분리하고 인프로세스 카운터(`OcrReachCounters`)에
    사유별로 집계한다 — "비활성"과 "적재 실패"가 로그·관측 양쪽에서 더 이상 무변별이지
    않다.
    """
    counters = ensure_ocr_counters(request.app)
    counters.record_request()
    components: OcrComponents | None = getattr(request.app.state, OCR_COMPONENTS_KEY, None)
    if components is None:
        reason: OcrUnavailableReason = (
            getattr(request.app.state, OCR_UNAVAILABLE_REASON_KEY, None)
            or _DEFAULT_UNAVAILABLE_REASON
        )
        counters.record_unavailable(reason)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_UNAVAILABLE_DETAIL[reason],
        )
    return components
