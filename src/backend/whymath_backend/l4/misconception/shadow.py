"""오개념 의미 매칭 *shadow 관측* — 노출 없이 substring↔semantic 불일치만 로깅 (slice 111).

`l4/step_shadow.py`(단계-비보존 shadow)의 정본 패턴을 미러한다. coach가 `misconception_semantic_
mode == "shadow"`일 때, 의미 매처를 *라이브로 돌리되* 노출은 substring 그대로 두고(off와 동일),
substring이 안 잡은 semantic-only 후보(불일치)를 **로그로만** 남긴다 — 슬107 측정 하니스는 *합성
프로브*에서 방향맹 FP를 쟀는데, shadow는 *실 학생 트래픽 분포*에서 의미 매처가 무엇을 더하는지를
무노출로 수집해 게이트 플립(`off`→`on`) 근거를 보강한다.

비노출·비차단 불변(step_shadow 계승):
- **비노출**: 반환 `None`. 호출자(coach)가 신호를 받을 변수가 없어 student-facing 누출이 구조적으로
  차단된다. 노출 응답은 `off`와 비트동일(substring)이고, shadow 로그는 *서버 로그 sink에만* 흐른다.
- **비차단**: 검출·직렬화·로깅을 한 `try`로 감싸 어떤 예외도 본류(코칭 결정·반환)를 안 깬다
  (우선순위: 학생 경험 > 진단 관측).
- **프라이버시**: 학생 풀이 원문을 레코드에 *담지 않는다*(step_shadow 규약·미성년자). 담는 건
  추상화된 오개념 id·코사인 유사도·개수(비식별).
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Coroutine
from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field

from whymath_backend.l3.interfaces import CacheBackend, LLMProvider, TraceSink
from whymath_backend.l4.misconception.intervene import select_intervention
from whymath_backend.l4.misconception.judge import JudgeProtocol, JudgeVerdict, judge_verdicts
from whymath_backend.l4.misconception.models import MisconceptionMatch
from whymath_backend.l4.misconception.visualize import visualize_misconception

logger = logging.getLogger("whymath.l4.misconception.shadow")  # step_shadow 네이밍 동형
# 구조화 레코드 JSON 한 줄(harvest 입력) — 평문 로그와 분리된 자식 로거(step_shadow.record 미러).
record_logger = logging.getLogger("whymath.l4.misconception.shadow.record")

# G1: judge would-be shadow 전용 자식 로거(`shadow.record`와 동형으로 한 단계 더 분리) —
# judge shadow 레코드만 따로 harvest/필터할 수 있게 한다.
judge_record_logger = logging.getLogger("whymath.l4.misconception.judge_shadow.record")

# MISC-01: 시각화 would-be shadow 전용 자식 로거(judge_shadow.record와 동형) — 시각화 shadow
# 레코드만 따로 harvest/필터할 수 있게 한다.
visualization_record_logger = logging.getLogger(
    "whymath.l4.misconception.visualization_shadow.record"
)


class MisconceptionShadowObservation(BaseModel):
    """의미 매칭 shadow 관측 1건의 *구조화 레코드* — record_logger JSON emit (harvest).

    노출되는 substring 후보(`substr_ids`)와 의미 매처가 *추가할* semantic-only 후보
    (`semantic_only_ids`·substring 미포착)를 담아, 실 분포에서 의미 매칭이 무엇을 더하는지(불일치)를
    수집한다. **학생 풀이 원문을 담지 않는다**(step_shadow 규약·프라이버시) — 담는 건 오개념 id·
    코사인 유사도·개수(비식별·로그 sink 한정·비노출 불변).
    """

    model_config = ConfigDict(extra="forbid")

    substr_ids: list[str]
    """노출되는(off와 동일) substring 진단 후보 id — confidence 내림차순."""

    semantic_only_ids: list[str]
    """의미 매처가 *추가할* 후보 id(substring 미포착) = 불일치. on이면 노출될 semantic-only."""

    semantic_only_similarities: list[float]
    """`semantic_only_ids` 각각의 코사인 유사도(같은 순서·None은 -1.0으로 표기)."""

    substr_count: int
    semantic_count: int
    observed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


def observe_misconception_shadow(
    substr_matches: list[MisconceptionMatch],
    semantic_matches: list[MisconceptionMatch],
) -> None:
    """substring↔semantic 불일치를 *로그로만* 관측(shadow·비차단·비노출). 반환 `None`.

    반환이 `None`이라 호출자(coach)가 신호를 받을 변수가 없다 — student-facing 누출 구조적 차단.
    coach는 `mode == "shadow"`에서만 호출하므로 이 함수는 게이트를 재검사하지 않는다(호출 시점이
    곧 shadow). 노출(반환 matches)은 coach가 substring 그대로 둔다(off 비트동일) — 본 함수는
    *부수효과(로그)만* 낸다. 어떤 예외도 본류를 깨지 않게 `try`로 감싼다(비차단).

    `semantic_only` = 의미 매처 결과 중 substring이 *안 잡은* id(`combine_diagnoses`가 `on`에서
    substring 아래에 붙일 후보). 이게 실 분포에서 의미 매처의 *순기여*(+recall)와 *방향맹 FP*가
    뒤섞인 신호다 — 사람이 로그를 보고(또는 harvest) 플립 근거를 모은다.
    """
    try:
        substr_ids = [m.misconception.id for m in substr_matches]
        substr_set = set(substr_ids)
        semantic_only = [m for m in semantic_matches if m.misconception.id not in substr_set]
        semantic_only_ids = [m.misconception.id for m in semantic_only]
        # semantic_similarity None(이론상 의미 경로에선 항상 설정)은 -1.0로 표기(레코드 타입 고정).
        sims = [
            m.semantic_similarity if m.semantic_similarity is not None else -1.0
            for m in semantic_only
        ]
        logger.info(
            "의미 매칭 shadow(비노출) — substr=%s semantic_only=%s sims=%s "
            "(substr_count=%d semantic_count=%d)",
            substr_ids,
            semantic_only_ids,
            [round(s, 3) for s in sims],
            len(substr_matches),
            len(semantic_matches),
        )
        record_logger.info(
            MisconceptionShadowObservation(
                substr_ids=substr_ids,
                semantic_only_ids=semantic_only_ids,
                semantic_only_similarities=sims,
                substr_count=len(substr_matches),
                semantic_count=len(semantic_matches),
            ).model_dump_json()
        )
    except Exception:  # noqa: BLE001 — 관측은 본류를 안 깬다(비차단 방어선·테스트 커버)
        return


# ──────────────────────────────────────────────────────────────────────────
# G1: judge would-be shadow — 의미 후보에 judge를 *비차단*으로 돌려 *걸러질 결과*만 로깅
# ──────────────────────────────────────────────────────────────────────────


class MisconceptionJudgeShadowObservation(BaseModel):
    """judge would-be shadow 관측 1건의 *구조화 레코드* — judge_record_logger JSON emit (harvest).

    `misconception_semantic_mode=="shadow"`에서 도는 *의미 후보*에 judge를 돌려, judge가 **제거할**
    후보(`would_remove_ids`·NOT_EXPRESSES)와 **유지할** 후보(`would_keep_ids`·EXPRESSES+UNCERTAIN)를
    무노출로 수집한다 → 노출 전 실데이터로 judge 효과(합성↔실 갭)를 검증한다(04b Phase 1).

    **프라이버시(미성년 PII)**: 학생 진술 원문도, judge의 `근거`(reason·학생 진술 인용 가능)도
    *담지 않는다*. `reason` 필드 자체가 없고 `extra="forbid"`라 구조적으로 차단된다(`shadow.py`
    `MisconceptionShadowObservation` 규약 계승). 담는 건 추상화된 오개념 id·verdict 카운트·임계
    (비식별·로그 sink 한정·비노출 불변).
    """

    model_config = ConfigDict(extra="forbid")

    semantic_candidate_ids: list[str]
    """judge에 *투입한* 의미 후보 id(입력 순서·matcher가 이미 threshold로 필터한 셋)."""

    would_remove_ids: list[str]
    """judge가 `아니오`(NOT_EXPRESSES)로 판정해 *제거할* 후보 id — on이면 안 노출될 것."""

    would_keep_ids: list[str]
    """judge가 `예`/`불확실`(EXPRESSES+UNCERTAIN)로 판정해 *유지할* 후보 id(recall 보존·보수)."""

    verdict_expresses: int
    """`예`(EXPRESSES) 판정 수 — 진짜 오개념 표현으로 본 후보."""

    verdict_not_expresses: int
    """`아니오`(NOT_EXPRESSES) 판정 수 — 올바름/다른 말로 본 후보(would_remove와 1:1)."""

    verdict_uncertain: int
    """`불확실`(UNCERTAIN) 판정 수 — 모호 + 모든 폴백(형식 위반·seam 예외)의 귀착점."""

    candidate_count: int
    """투입 의미 후보 총수(=len(semantic_candidate_ids))."""

    feed_threshold: float | None = None
    """후보를 matcher가 거른 코사인 임계(judge-feed 운영점·사후 해석용·04b §4). None=미주입."""

    judge_routing: str | None = None
    """judge 라우팅 프로파일 라벨(fast_math/general_mid·judge 모델 식별·04b §2). None=미주입."""

    observed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# 비차단(fire-and-forget) task의 강참조 보관소 — `create_task`가 *유일하게* 들고 있는 참조가
# 약참조라 GC가 *실행 중* task를 수거해버리는 Python 경고(asyncio docs)를 방어한다. spawn 시
# add → 완료 시 add_done_callback(discard)로 자가 정리한다. `_misconception_state.py`의 모듈
# 전역 싱글톤 관용과 동형(코드베이스에 `create_task` 선례 0이라 가장 보수적 표준 패턴 채택).
_PENDING: set[asyncio.Task[None]] = set()


def _spawn(coro: Coroutine[object, object, None]) -> None:
    """코루틴을 *비차단*으로 띄우고 즉시 반환 — 응답 경로가 judge(수 초)를 await하지 않게 한다.

    `asyncio.create_task`로 백그라운드 실행하고, GC가 실행 중 task를 수거하지 못하게 `_PENDING`에
    강참조를 잡았다가 완료 콜백으로 푼다(3중 안전망 중 GC 방어선). 호출자(coach)는 이 함수가
    *즉시* 반환하므로 judge LLM 왕복을 기다리지 않는다(노출 무지연·G1 핵심 제약).
    """
    task: asyncio.Task[None] = asyncio.create_task(coro)
    _PENDING.add(task)
    task.add_done_callback(_PENDING.discard)


async def observe_misconception_judge_shadow(
    semantic_matches: list[MisconceptionMatch],
    student_statement: str,
    *,
    judge: JudgeProtocol,
    feed_threshold: float | None = None,
    judge_routing: str | None = None,
) -> None:
    """의미 후보에 judge를 돌려 *would-be removed/kept*를 로그로만 관측(shadow·비노출). 반환 `None`.

    `judge_verdicts`(*`judge_filter` 아님* — verdict 카운트가 필요)로 각 후보를 판정한 뒤
    `result.verdict`*만* 읽어 would_remove(NOT_EXPRESSES)/would_keep(EXPRESSES+UNCERTAIN)로 분류하고
    레코드를 emit한다. judge의 `reason`/`raw`는 *버린다*(학생 진술 인용 가능=미성년 PII·레코드
    모델에 필드 없음). 빈 입력은 short-circuit(judge 미호출).

    **never-break**(비차단 방어선·`observe_misconception_shadow`의 async 미러): judge 호출·직렬화·
    로깅을 한 `try`로 감싸 *어떤 예외도* 본류(여기선 fire-and-forget task)를 깨지 않는다 — judge
    코어(`judge_verdicts`)는 이미 seam 예외→UNCERTAIN으로 never-break지만(judge.py), 직렬화·로깅
    실패까지 포함해 방어한다(우선순위: 학생 경험 > 진단 관측·CLAUDE.md #1≫#6).
    """
    if not semantic_matches:
        return  # 의미 후보 0 → judge 미호출(short-circuit·효율).
    try:
        decided = await judge_verdicts(semantic_matches, student_statement, judge=judge)
        would_remove: list[str] = []
        would_keep: list[str] = []
        n_expresses = n_not_expresses = n_uncertain = 0
        for match, result in decided:
            mid = match.misconception.id
            # `result.verdict`만 읽는다 — reason/raw(PII 가능)는 절대 레코드에 안 담는다.
            if result.verdict is JudgeVerdict.NOT_EXPRESSES:
                would_remove.append(mid)
                n_not_expresses += 1
            else:
                would_keep.append(mid)  # 예·불확실 모두 유지(recall 보존·보수)
                if result.verdict is JudgeVerdict.EXPRESSES:
                    n_expresses += 1
                else:
                    n_uncertain += 1
        candidate_ids = [m.misconception.id for m in semantic_matches]
        logger.info(
            "judge shadow(비노출) — candidates=%s would_remove=%s would_keep=%s "
            "(예=%d 아니오=%d 불확실=%d routing=%s)",
            candidate_ids,
            would_remove,
            would_keep,
            n_expresses,
            n_not_expresses,
            n_uncertain,
            judge_routing,
        )
        judge_record_logger.info(
            MisconceptionJudgeShadowObservation(
                semantic_candidate_ids=candidate_ids,
                would_remove_ids=would_remove,
                would_keep_ids=would_keep,
                verdict_expresses=n_expresses,
                verdict_not_expresses=n_not_expresses,
                verdict_uncertain=n_uncertain,
                candidate_count=len(semantic_matches),
                feed_threshold=feed_threshold,
                judge_routing=judge_routing,
            ).model_dump_json()
        )
    except Exception:  # noqa: BLE001 — 관측은 본류를 안 깬다(비차단 방어선·shadow.py:100 미러)
        return


# ──────────────────────────────────────────────────────────────────────────
# MISC-01: 오개념 교정 시각화 would-be shadow — `visualize_misconception`(슬93)을 *비차단*으로
# 돌려 생성 성공/실패만 로깅 (04b 롤아웃 패턴 재사용·`misconception_visualization_mode`)
# ──────────────────────────────────────────────────────────────────────────


class MisconceptionVisualizationShadowObservation(BaseModel):
    """시각화 would-be shadow 관측 1건의 *구조화 레코드* — visualization_record_logger JSON emit.

    `misconception_visualization_mode=="shadow"`에서, 확정 진단(개입 결정)에 대해
    `visualize_misconception`을 *비차단*으로 돌려 생성 성공/실패를 무노출로 수집한다 → 노출
    (`mode="on"`) 전 실 트래픽에서 L3 생성 성공률·LLM 왕복 실패 유형을 검증한다(04b Phase 1
    미러 — `MisconceptionJudgeShadowObservation`과 동형 목적).

    **프라이버시(미성년 PII)**: 학생 진술 원문도, 생성된 시각화의 `spec`/`caption`(학생 풀이를
    반영해 재구성된 교정 콘텐츠라 간접적으로 학생 입력을 인코딩할 수 있음)도 *담지 않는다* —
    필드 자체가 없고 `extra="forbid"`라 구조적으로 차단된다(`MisconceptionShadowObservation`
    규약 계승). 담는 건 추상화된 오개념 id·도메인·개입 패턴·수준 라벨·성공 여부·(성공 시)
    렌더 기술 타입 라벨 하나·(실패 시) 예외 타입명(비식별·로그 sink 한정·비노출 불변).
    """

    model_config = ConfigDict(extra="forbid")

    misconception_id: str
    """대상 오개념 id — `MisconceptionMatch.misconception.id`."""

    domain: str
    """오개념 카탈로그 영역(`Misconception.domain`)."""

    pattern: str
    """개입 패턴(`InterventionPattern` 값 — counterexample/reverse_reasoning). select_intervention
    이 이 match로 재산출한 값이라 `visualize_misconception`의 내부 게이트와 항상 일치한다."""

    level: str
    """학생 수준 라벨(예: '고1'·'초보') — 원문 아님, 라벨 문자열만."""

    success: bool
    """`visualize_misconception`이 검증된 `Visualization`을 반환했는지."""

    visualization_type: str | None = None
    """성공 시 `Visualization.type`(렌더 기술 라벨 — 4종 중 1개). 실패면 None."""

    error_type: str | None = None
    """실패 시 예외 타입명(CLAUDE.md 침묵 실패 금지 — `reason`/원문 없이 타입명만).
    성공이면 None."""

    observed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


async def observe_misconception_visualization_shadow(
    match: MisconceptionMatch,
    level: str,
    *,
    provider: LLMProvider,
    cache: CacheBackend,
    trace: TraceSink,
) -> None:
    """확정 진단에 `visualize_misconception`을 돌려 *성공/실패*를 로그로만 관측(shadow·비노출).

    반환 `None`이라 호출자(coach `_spawn`)가 신호를 받을 변수가 없다 — student-facing 누출이
    구조적으로 차단된다(`observe_misconception_judge_shadow` 동형). coach는
    `mode == "shadow"` ∧ intervention 확정에서만 호출하므로, 여기서 `select_intervention(match)`
    로 *다시* 게이트를 확인하는 건 재검사가 아니라 레코드의 `pattern` 필드를 이 `match`와 항상
    정합하게 유도하기 위함이다(호출자가 넘긴 intervention이 가설-기반이라 다른 misconception을
    가리킬 수 있는 경우와 무관하게, 이 함수가 실제로 시각화하는 대상은 항상 `match`).

    `visualize_misconception` 자체의 예외(`InvalidVisualizationSpecError` 포함 임의 예외)는 여기서
    *삼킨다* — 이건 shadow 관측이지 산출물이 아니므로(비차단 방어선), 단 예외 타입명은 레코드에
    남는다(침묵 실패 금지). 레코드 직렬화·로깅 자체의 실패는 별도 바깥 `try`로 방어한다
    (`observe_misconception_judge_shadow` 2단 방어 동형).
    """
    success = False
    visualization_type: str | None = None
    error_type: str | None = None
    try:
        v = await visualize_misconception(match, level, provider=provider, cache=cache, trace=trace)
    except Exception as exc:  # noqa: BLE001 — 생성 실패도 shadow 관측 대상(타입명만 기록·비차단)
        error_type = type(exc).__name__
    else:
        if v is not None:
            success = True
            # Visualization.type은 use_enum_values=True라 이미 str(enum 값)이지만, 계약이 바뀌어도
            # 방어적으로 str()을 통과시킨다(레코드 직렬화가 enum 인스턴스에 깨지지 않게).
            visualization_type = str(v.type)

    intervention = select_intervention(match)  # 레코드용 pattern 라벨 — match와 항상 정합.
    pattern = intervention.pattern.value if intervention is not None else "unknown"
    try:
        logger.info(
            "시각화 shadow(비노출) — misconception=%s pattern=%s level=%s success=%s "
            "visualization_type=%s error_type=%s",
            match.misconception.id,
            pattern,
            level,
            success,
            visualization_type,
            error_type,
        )
        visualization_record_logger.info(
            MisconceptionVisualizationShadowObservation(
                misconception_id=match.misconception.id,
                domain=match.misconception.domain,
                pattern=pattern,
                level=level,
                success=success,
                visualization_type=visualization_type,
                error_type=error_type,
            ).model_dump_json()
        )
    except Exception:  # noqa: BLE001 — 관측은 본류를 안 깬다(비차단 방어선·shadow.py:100 미러)
        return
