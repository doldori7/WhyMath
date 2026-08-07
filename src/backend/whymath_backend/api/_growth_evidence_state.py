"""성장 증거(WH-1 대리 지표) 도달 관측 카운터 — app.state 인프로세스 상태 (PED-06).

`gamification_module_gap_review.md` §3 D1: `compute_wh1_surrogate_metrics`가 지표 11종을
계산하고 `GET /v1/me/harness-metrics`로 노출하지만, Flutter가 이 엔드포인트를 *호출하기로
결정한 적 자체가 없다*(전수 실측 — 배선 부재가 아니라 결정 부재). 이 카운터는 그 주장을
계속 검증 가능하게 만든다 — 지금은 0이지만, 향후 클라가 실제로 호출하기 시작하면 이 값이
그대로 올라간다(정적 감사 하나로 끝내지 않고 라이브 신호로도 이중 회계).

`api/_ocr_state.py`(NLP-01 `OcrReachCounters`)와 동형 패턴 — 동시성 전제도 동일(단일 asyncio
이벤트 루프·await 없는 동기 증가라 락 불요). 재사용이 아니라 병렬 구축이다: 어휘
(`requests_total`)도 의미(성장 지표 노출 도달, 가용성 축 아님)도 달라 기존 `ServiceMetrics`에
욱여넣지 않는다.

**의도적으로 하지 않는 것 — 사용자별 카운트**: 요청자 `user_id`를 메모리에 누적하지 않는다.
"학생 도달 건수"는 이 값(요청 수)으로 근사한다 — distinct user set을 메모리에 두는 것은
①(가치가 낮음 — 지금은 0 대 0-아님만 증명하면 충분) ②(불필요한 식별자 누적, CLAUDE.md
미성년자 PII 최소화와 마찰) 양쪽 다 비용이 이득보다 크다.
"""

from __future__ import annotations

from dataclasses import dataclass

# app.state 속성 키 — create_app이 앱 수명 동안 1개를 심고, api/me.py·app.py(/health/ready)가
# 공유 조회한다(단일 출처).
GROWTH_EVIDENCE_COUNTERS_KEY = "growth_evidence_reach_counters"
# PED-08: `GET /v1/me/growth-evidence`(노출 계약 경유 신 라우트) 전용 슬롯 — 원시 표면
# (`/harness-metrics`, 위 키)과 *같은 카운터에 합산되면 안 된다*. 합산되면 PED-06의 3상태
# 도달 리포트(`surrogate_baseline_report.py`)가 "원시 표면에 도달했다"는 주장과 "노출 계약을
# 거쳐 도달했다"는 주장을 구분할 수 없게 되어 도달 판정 자체가 위장된다.
GROWTH_EVIDENCE_EXPOSURE_COUNTERS_KEY = "growth_evidence_exposure_reach_counters"


@dataclass(frozen=True, slots=True)
class GrowthEvidenceReachSnapshot:
    """성장 증거 도달 관측의 불변 스냅샷 — `/health/ready` 노출 원천."""

    requests_total: int


class GrowthEvidenceReachCounters:
    """성장 증거(WH-1 대리 지표) 도달 카운터 — 요청 1건당 1 증가(성공/실패 무관).

    경로에 무관한 범용 카운터다(PED-08 — 원래 `GET /v1/me/harness-metrics` 전용으로
    태어났으나, 이제 `GET /v1/me/growth-evidence`도 *별도 슬롯*으로 이 클래스를 재사용한다
    — 클래스 자체에는 어느 라우트인지에 대한 로직이 없으므로 병렬 클래스를 새로 만들지
    않는다). 두 라우트 모두 이미 `ConsentedUser` 게이트가 걸려 있어 도달 자체가 "인증된
    학생이 실제로 호출했다"를 뜻한다 — 별도 성공/실패 구분은 필요 없다(OCR과 달리 이
    엔드포인트들은 비활성 상태·부품 적재 실패 같은 조건부 가용성이 없다 — 항상 DB 조회
    성공 아니면 500).
    """

    __slots__ = ("_requests_total",)

    def __init__(self) -> None:
        self._requests_total = 0

    def record_request(self) -> None:
        """요청 1건이 `GET /v1/me/harness-metrics`에 도달했다(응답 이전 — 성공 가정 무관)."""
        self._requests_total += 1

    def snapshot(self) -> GrowthEvidenceReachSnapshot:
        """현재 카운터의 불변 스냅샷 — `/health/ready` 렌더용."""
        return GrowthEvidenceReachSnapshot(requests_total=self._requests_total)


def set_growth_evidence_counters(
    app_state_holder: object,
    counters: GrowthEvidenceReachCounters,
    *,
    key: str = GROWTH_EVIDENCE_COUNTERS_KEY,
) -> None:
    """app(또는 app.state 보유 객체)에 카운터를 저장 — create_app이 부팅 시 호출.

    `key`(기본값=기존 `/harness-metrics` 슬롯)로 저장 슬롯을 구분한다 — PED-08이
    `/growth-evidence` 전용 슬롯을 `key=GROWTH_EVIDENCE_EXPOSURE_COUNTERS_KEY`로 별도 심을
    때 이 함수를 그대로 재사용한다(병렬 함수 신설이 아니라 슬롯 매개변수화). 기본값
    유지라 기존 호출부(create_app 부팅 배선)는 무변경으로 동일 동작을 유지한다.
    """
    app_state_holder.state.__setattr__(key, counters)  # type: ignore[attr-defined]


def get_growth_evidence_counters(
    app_state_holder: object, *, key: str = GROWTH_EVIDENCE_COUNTERS_KEY
) -> GrowthEvidenceReachCounters:
    """app.state에서 카운터를 꺼낸다 — create_app 경유 앱이면 항상 존재(미설정은 버그).

    `key`(기본값=기존 `/harness-metrics` 슬롯)로 어느 슬롯을 읽을지 구분한다. 기본값 유지라
    기존 호출부(api/me.py `get_my_harness_metrics`·app.py `/health/ready`)는 무변경으로
    동일 동작을 유지한다.
    """
    counters: GrowthEvidenceReachCounters = getattr(app_state_holder.state, key)  # type: ignore[attr-defined]
    return counters


def get_growth_evidence_exposure_counters(
    app_state_holder: object,
) -> GrowthEvidenceReachCounters:
    """`GET /v1/me/growth-evidence` 전용 도달 카운터 조회(PED-08) — 원시 표면과 구분해 센다.

    `get_growth_evidence_counters`(기본 키=기존 `/harness-metrics` 슬롯)와 *합산되지 않는다*
    — 섞이면 PED-06 3상태 도달 리포트(`surrogate_baseline_report.py`)의 "원시 표면 도달"
    판정이 위장된다(모듈 docstring). 별도 클래스·별도 저장 로직 없이 제네릭 getter를 새
    키로 호출할 뿐이다.
    """
    return get_growth_evidence_counters(
        app_state_holder, key=GROWTH_EVIDENCE_EXPOSURE_COUNTERS_KEY
    )
