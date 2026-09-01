"""앵커 축적 **회차 대장** — '작동한 비율'(EOS-64 ②)과 연속 무진전 알람(④)의 단일 원천.

왜 이 모듈이 있는가
------------------
EOS-58이 앵커 A4 관통을 1회 실증했지만, 그 관통이 *상시로* 일하고 있는지는 아무도 재지
않았다. 라이브 회차가 exit 0을 내도 그것은 "이번에 1건 붙었다"일 뿐이고, exit 1을 내도 그것이
"이번 회차만 안 붙었다"인지 "구조적으로 3주째 안 붙는다"인지 구분되지 않는다 — CLAUDE.md
"작동 신호 없는 알고리즘 부착 금지"("정상 응답 200은 알고리즘이 일했다는 증거가 아니다")가
정확히 이 공백을 가리킨다. 이 모듈이 그 두 공백을 메운다:

  ② **작동한 비율**(`operating_rates`) — 회차 리포트에 outcome 6종의 *분포*를 싣는다. 수용
     1건이라는 사실보다 "5시도 중 수용1·검수필요1·게이트거부1·중복1·생성실패1"이라는 분포가
     파이프라인의 각 단계가 실제로 일했다는 증거다(전건 generation_failed면 게이트·dedup은
     한 번도 안 돌았다는 뜻이고, 그건 exit 1 하나로는 안 보인다).
  ④ **연속 무진전 알람**(`judge_stagnation`) — 회차 1건씩을 append-only 대장에 남기고, 최신
     회차부터 연속으로 코퍼스가 자라지 않은 횟수를 센다. fail-open 상시 실패(같은 경고가
     매번 나는데 아무도 안 보는 상태)를 막으려면 *반복*이 판정으로 승격돼야 한다.

판정 방향 — 점추정 금지(CLAUDE.md 검증 권위)
--------------------------------------------
비율은 점추정으로 말하지 않는다. `harness/wilson`의 단측 경계를 **지표 성격에 맞는 방향**으로
쓴다(재구현 0 — 그 모듈이 단일 원천):

  - `accepted_stored`·`accepted` = "높을수록 좋은" 수용률 → **하한**(`wilson_lower_bound`).
    5/5=1.0 같은 작은 표본의 과신을 막는다(정직 — 실제보다 낮게 본다).
  - `needs_review`·`rejected_gate`·`rejected_duplicate`·`generation_failed` = "낮을수록 좋은"
    비용·결함 축 → **상한**(`wilson_upper_bound`). 0/3 관측을 "확정 0%"로 읽지 않는다.
    `needs_review`를 결함이 아니라 *사람 검수 비용*으로 보더라도 방향은 같다(적을수록 좋다).

분모 0은 "0%"가 아니라 **측정 불가**다(CLAUDE.md 미측정≠0). `attempted <= 0`이면 전 비율이
`None`이고 `measured=False`·`unmeasured_reason`이 사유를 말한다 — 0.0으로 채우면 "시도한 적
없음"이 "전건 실패"와 같은 색이 된다.

무진전의 축 — `appended`(코퍼스 성장)를 본다
-------------------------------------------
acceptance 문구는 "수용 0"이지만 이 모듈이 세는 축은 `appended`(실제로 코퍼스 JSONL에 붙은
신규 행)다. 근거: ⑴ `problem_corpus_accumulate.main`의 기존 exit 판정이 이미 `appended > 0`
이라 같은 축을 써야 신호가 갈리지 않고 ⑵ `appended > 0`이면 정의상 `accepted > 0`이지만
역은 아니다(수용됐는데 slug 충돌로 전건 스킵되면 코퍼스는 그대로다) — 즉 `appended`가 더
엄격하고, "코퍼스가 자랐는가"라는 무진전의 본래 의미에 정확히 대응한다. 대장 행에는 두 값을
모두 남겨 나중에 다른 축으로 재판정할 수 있게 한다.

매체 계약(EOS-55 genlog·EOS-58 검수 큐와 동형)
---------------------------------------------
회차 1건 = JSONL 1행, **발생 즉시 append+flush**(마지막 일괄 저장 금지 — 2026-08-22 규칙 ①).
로드 실패 줄은 삼키지 않고 **예외 타입명 + 줄 번호**만 수집한다(필드 *값*·원문 줄은 넣지
않는다 — 침묵 실패 금지). 행은 관측이므로 수정·삭제하지 않는다(append-only).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, get_args

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from whymath_backend.harness.wilson import wilson_lower_bound, wilson_upper_bound
from whymath_backend.l3.equivalent.orchestrator import GenerationOutcome

__all__ = [
    "ACCEPTED_STATUSES",
    "OUTCOME_STATUSES",
    "RoundRecord",
    "StagnationVerdict",
    "append_round_ledger",
    "default_round_ledger_path",
    "judge_stagnation",
    "load_round_ledger",
    "operating_rates",
]

# outcome 어휘는 **오케스트레이터의 Literal에서 파생**한다(재선언 금지) — 여기 손으로 6종을
# 베껴 두면 orchestrator가 상태를 추가·개명할 때 리포트가 조용히 그 상태를 빠뜨린다(분포가
# 100%가 안 되는데 아무도 모르는 상태). EOS-58 테스트 docstring의 어휘 나열도 정본이 아니다.
OUTCOME_STATUSES: tuple[str, ...] = tuple(
    get_args(GenerationOutcome.model_fields["status"].annotation)
)
if "accepted_stored" not in OUTCOME_STATUSES or len(OUTCOME_STATUSES) < 2:
    # 도입부 파생이 깨지면 "분포가 빈 dict"로 조용히 통과할 수 있다 — 그건 측정 실패이므로
    # import 시점에 정직하게 터진다(2026-08-22 "정지 장치도 변별력이 필요하다"의 반대 축:
    # 여기서는 *위장 통과*를 막는 것이 목적이라 fail-fast가 옳다).
    raise RuntimeError(
        "GenerationOutcome.status Literal에서 outcome 어휘를 파생하지 못했다 — "
        f"파생 결과={OUTCOME_STATUSES!r}. 회차 분포가 위장 통과할 수 있어 import를 중단한다."
    )

# 수용 축 — `needs_review_worklist._STORED_STATUSES`·`run_corpus_accumulate`의 비수용 판정과
# 같은 집합(두 곳이 이미 이 두 값을 쓴다). 여기서는 *비율 방향*을 가르는 데 쓴다.
ACCEPTED_STATUSES: frozenset[str] = frozenset({"accepted_stored", "accepted"})

# 기본 신뢰수준 — 저장소 전 게이트 관례(`ops/qa_confusion_matrix._CONFIDENCE` 동일).
_CONFIDENCE = 0.95

# 연속 무진전 기본 창(회차) — 2회는 소량 n 회차에서 흔한 잡음이고(대본 1건짜리 회차도 있다),
# 3회 연속이면 "이번엔 운이 없었다"로 설명되지 않는 구조 신호다. `--stagnation-window`로 조정.
DEFAULT_STAGNATION_WINDOW = 3


def _bound_direction(status: str) -> str:
    """이 outcome이 '높을수록 좋은' 축인지 — 수용은 하한, 나머지(비용·결함)는 상한."""
    return "lower" if status in ACCEPTED_STATUSES else "upper"


def operating_rates(
    outcome_counts: dict[str, int],
    *,
    attempted: int,
    confidence: float = _CONFIDENCE,
) -> dict[str, Any]:
    """회차 '작동한 비율' — outcome 6종 분포 + 방향별 Wilson 단측 경계(순수·파일 I/O 0).

    반환 dict는 회차 리포트에 그대로 실린다(`AccumulateReport.to_json`). 구조:

        {"attempted": 5, "measured": true, "confidence": 0.95,
         "unmeasured_reason": null,
         "statuses": {"accepted_stored": {"count":1, "rate":0.2,
                                          "bound":0.036, "bound_direction":"lower"}, ...},
         "unknown_statuses": {}}

    - `statuses`는 **어휘 전건**을 싣는다(관측 0인 상태도 count 0으로 명시) — 키가 없는 것과
      0건인 것은 다르다. 어휘 밖 상태가 들어오면 버리지 않고 `unknown_statuses`에 카운트만
      남긴다(조용한 누락 금지 — 어휘 드리프트를 리포트가 자백한다).
    - `attempted <= 0`이면 `measured=false`이고 전 `rate`·`bound`가 `None`이다(미측정≠0).
    - `rate`는 점추정이라 **판정 근거가 아니다**(참고용 표시). 판정은 `bound`로 한다.
    """
    measured = attempted > 0
    reason: str | None = (
        None if measured else f"시도 {attempted}회 — 분모가 없어 비율을 계산할 수 없다(0%가 아니다)"
    )

    statuses: dict[str, Any] = {}
    for status in OUTCOME_STATUSES:
        count = int(outcome_counts.get(status, 0))
        direction = _bound_direction(status)
        rate: float | None = None
        bound: float | None = None
        if measured:
            rate = count / attempted
            bound = (
                wilson_lower_bound(count, attempted, confidence)
                if direction == "lower"
                else wilson_upper_bound(count, attempted, confidence)
            )
        statuses[status] = {
            "count": count,
            "rate": rate,
            "bound": bound,
            "bound_direction": direction,
        }

    unknown = {
        status: int(count)
        for status, count in outcome_counts.items()
        if status not in OUTCOME_STATUSES
    }
    return {
        "attempted": attempted,
        "measured": measured,
        "confidence": confidence,
        "unmeasured_reason": reason,
        "statuses": statuses,
        "unknown_statuses": unknown,
    }


class RoundRecord(BaseModel):
    """회차 대장 1행 — 축적 배치 1회의 결과 요약(append-only·관측).

    `appended`가 무진전 판정 축이고 `accepted`는 참조 축이다(모듈 docstring "무진전의 축").
    `outcome_counts`를 함께 남겨 나중에 대장만으로 분포를 재계산할 수 있게 한다 — 리포트
    JSON을 따로 보관하지 않아도 회차 이력이 자족한다.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: str = Field(description="축적 회차 식별자(`AccumulateReport.run_id`와 조인).")
    out_path: str = Field(description="이 회차가 append한 코퍼스 JSONL 경로(대장의 소속 축).")
    attempted: int = Field(ge=0, description="생성 시도 횟수(분모 — 0이면 측정 불가).")
    accepted: int = Field(ge=0, description="게이트·dedup 통과 후 저장된 수용 건수.")
    appended: int = Field(ge=0, description="코퍼스에 실제로 붙은 신규 행 수(무진전 판정 축).")
    outcome_counts: dict[str, int] = Field(
        default_factory=dict, description="outcome 상태별 건수(분포 재계산 재료)."
    )
    recorded_at: datetime | None = Field(
        default=None, description="기록 시각(UTC) — append가 스탬프(매체가 찍는다)."
    )
    source_line: int | None = Field(
        default=None,
        description=(
            "매체 파생 필드 — 대장 JSONL에서의 1-기반 줄 번호. append는 기록하지 않고"
            "(파일이 줄 번호를 자칭하지 않음) 로더가 실제 위치를 주입한다."
        ),
    )


def default_round_ledger_path(out_path: Path) -> Path:
    """회차 대장 기본 경로 — 축적 산출물 곁 사이드카 `<out>.rounds.jsonl`(항상 적재).

    genlog(`<out>.genlog.jsonl`)·검수 큐(`<out>.review.jsonl`)와 같은 규약이다. 끄는 옵션을
    두지 않는 이유: 플래그를 잊으면 회차 이력이 조용히 비고, 그러면 연속 무진전 알람이 영원히
    "측정 불가"가 된다 — 알람을 껐는지 아무 일도 없었는지 구분할 수 없는 상태가 된다.
    대장은 `--out`마다 하나라 서로 다른 코퍼스의 회차가 한 창에 섞이지 않는다.
    """
    return out_path.with_suffix(".rounds.jsonl")


def append_round_ledger(path: Path, record: RoundRecord) -> RoundRecord:
    """회차 1행을 대장에 **즉시** append한다(open→기록→flush→close — genlog·검수 큐 동형).

    `recorded_at`이 비어 있으면 append 시각(UTC)으로 스탬프한다. 매체 파생 필드
    `source_line`은 기록하지 않는다(로더가 실제 줄 번호를 주입). 스탬프된 행을 반환한다.
    """
    stamped = (
        record
        if record.recorded_at is not None
        else record.model_copy(update={"recorded_at": datetime.now(UTC)})
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(stamped.model_dump_json(exclude={"source_line"}) + "\n")
        handle.flush()
    return stamped


def load_round_ledger(path: Path) -> tuple[list[RoundRecord], list[str]]:
    """대장 JSONL을 읽는다 — (유효 행[줄 번호 주입], 실패 사유[타입명+줄 번호]) 튜플.

    파싱·검증 실패 줄은 삼키지 않고 사유로 수집한다(침묵 실패 금지 — **예외 타입명** + 줄
    번호 + 실패 필드 위치만. 필드 *값*·원문 줄은 넣지 않는다 — `load_review_queue_jsonl`
    동형). 파일 부재는 FileNotFoundError 전파 — "파일 없음"과 "행 0건"은 다르다(미측정≠0).
    """
    entries: list[RoundRecord] = []
    errors: list[str] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            text = line.strip()
            if not text:
                continue
            try:
                parsed = RoundRecord.model_validate(json.loads(text))
            except ValidationError as exc:
                locs = ",".join(
                    "/".join(str(part) for part in err.get("loc", ())) or "(root)"
                    for err in exc.errors()
                )
                errors.append(f"line {line_no}: ValidationError: fields=[{locs}]")
            except Exception as exc:  # noqa: BLE001 — 사유 수집(타입명 보존)이 목적
                errors.append(f"line {line_no}: {type(exc).__name__}")
            else:
                entries.append(parsed.model_copy(update={"source_line": line_no}))
    return entries, errors


@dataclass(frozen=True, slots=True)
class StagnationVerdict:
    """연속 무진전 판정 — 알람 여부와 그 *근거*(관측 회차 수·연속 길이)를 함께 낸다.

    `measured=False`는 "무진전 아님"이 아니라 **잴 것이 없었다**는 뜻이다(대장 행 0). 두 상태를
    같은 색(alarm=False)으로만 두면 "회차를 한 번도 안 돌린 상태"가 "잘 돌고 있는 상태"로
    위장된다 — 그래서 `measured`와 `message`가 그 구분을 항상 말한다.
    """

    window: int
    """알람 임계 — 이 횟수 이상 연속 무진전이면 알람."""

    observed_rounds: int
    """대장에서 읽은 유효 회차 수(분모 — 0이면 measured=False)."""

    consecutive_zero: int
    """최신 회차부터 연속으로 `appended == 0`인 회차 수."""

    alarm: bool
    """알람 발효 여부(measured이고 consecutive_zero >= window일 때만 True)."""

    measured: bool
    """판정 재료가 있었는가 — 대장 유효 행 0이면 False(미측정≠무진전 없음)."""

    message: str
    """사람이 읽는 한 줄 — 알람·정상·측정 불가를 각각 다른 문장으로 말한다."""

    def to_json(self) -> dict[str, Any]:
        """리포트 JSON에 싣는 형태(dataclass → dict — 필드명 그대로)."""
        return {
            "window": self.window,
            "observed_rounds": self.observed_rounds,
            "consecutive_zero": self.consecutive_zero,
            "alarm": self.alarm,
            "measured": self.measured,
            "message": self.message,
        }


def judge_stagnation(
    records: list[RoundRecord],
    *,
    window: int = DEFAULT_STAGNATION_WINDOW,
    load_errors: list[str] | None = None,
) -> StagnationVerdict:
    """대장 이력에서 연속 무진전을 판정한다(순수 — 파일 I/O 0).

    `records`는 대장 파일 순서(append 순 = 시간순)로 들어온다고 본다 — 마지막 원소가 최신
    회차다. 최신부터 거슬러 `appended == 0`이 연속으로 몇 회 이어지는지 세고, 그 길이가
    `window` 이상이면 알람이다.

    `load_errors`가 있으면(대장 일부 줄이 깨짐) 유효 행만으로 판정하되 **메시지에 그 사실을
    명기**한다 — 깨진 줄이 하필 수용 회차였다면 연속 길이가 과대평가되므로, 판정을 조용히
    내리지 않고 근거의 불완전성을 함께 말한다(침묵 실패 금지).

    `window <= 0`은 알람을 상시 참으로 만들어 판정을 무의미하게 만든다 — ValueError로 거부
    한다(변별력 없는 게이트를 인자로 만들 수 없게).
    """
    if window <= 0:
        raise ValueError(f"stagnation window는 1 이상이어야 한다(받은 값 {window}).")

    errors = load_errors or []
    observed = len(records)
    if observed == 0:
        return StagnationVerdict(
            window=window,
            observed_rounds=0,
            consecutive_zero=0,
            alarm=False,
            measured=False,
            message=(
                "측정 불가 — 회차 대장에 유효 행이 0건이다(무진전이 아니라 잰 것이 없다)."
                + (f" 로드 실패 {len(errors)}행." if errors else "")
            ),
        )

    consecutive = 0
    for record in reversed(records):
        if record.appended > 0:
            break
        consecutive += 1

    alarm = consecutive >= window
    broken = f" (대장 로드 실패 {len(errors)}행 — 연속 길이가 과대평가일 수 있다)" if errors else ""
    if alarm:
        message = (
            f"연속 무진전 알람 — 최근 {consecutive}회차 연속으로 코퍼스에 신규 행이 0건이다"
            f"(임계 {window}회차·관측 {observed}회차). 생성기·게이트·dedup 중 어디서 막히는지 "
            f"회차 리포트의 작동한 비율 분포로 확인하라.{broken}"
        )
    else:
        message = (
            f"진전 관측 — 연속 무진전 {consecutive}회차(임계 {window} 미만·관측 {observed}회차)."
            f"{broken}"
        )
    return StagnationVerdict(
        window=window,
        observed_rounds=observed,
        consecutive_zero=consecutive,
        alarm=alarm,
        measured=True,
        message=message,
    )
