"""WH-1 진단 프로브 후보 풀 조립 — L1 조회 + L2 난이도 변환 + L4 순수 선택 결합 (REC-02 ②③④).

설계 정본: `docs/architecture/ai_recommendation_module_gap_review.md` §3 D2. 도구6
(`select_probe`)가 라이브에서 항상 실패하던 이유는 `LLMTutorPolicy(probe_candidates=...)`를
채우는 프로덕션 호출자가 0건이었기 때문이다(`wh1_llm_policy.py:143` 기본값 `()`가 그대로 새는
구조). 이 모듈이 그 공급선이다 — **하네스(횡단 인프라·import-linter 계약 밖)만이** L1(조회)·
L2(난이도 로짓 변환)·L4(순수 `ProbeCandidate` 모델)를 자유로이 넘나들 수 있으므로, 세 계층을
잇는 조립은 여기서만 한다(L1은 L4를 모르고, L4는 DB를 모른다는 7계층 동결·CLAUDE.md).

**활성 가설이 선 뒤**(§2.2 웜 스타트·감사 §3 D2 ②) 호출된다 — `harness/wh1_primary.py`·
`harness/wh1_shadow.py`가 `_apply_hypotheses`로 영속·큐레이션한 `active_hypotheses`를 그대로
받아 이 함수 안에서 mids를 뽑는다(정책 생성보다 앞선 시점).

**reactive retrieval 준수**(CLAUDE.md "오개념을 초기 context에 preload 금지"): 이 함수가 조립하는
`ProbeCandidate` 리스트는 `LLMTutorPolicy`의 *사적 probe 컨텍스트*로만 흐른다(`outside_mids`와
동일 계약 — `wh1_llm_policy.py` `_build_prompt`가 프롬프트에 절대 싣지 않는 필드). LLM에게 가는
것은 "select_probe 도구를 쓸지" 여부뿐이고, 어떤 문항·오개념이 후보였는지는 정책이 도구 실행 시
*내부적으로만* 소비한다(`SelectProbeAction.candidates` → `plan_probe`). 이 모듈 자체도 mids를
프롬프트 문자열로 렌더하지 않는다(로그도 카운트만 — 아래 참조).

**ε-탐색 성립**(③): mids는 `active_hypotheses`(활용 표적)와 `outside_mids`(탐색 표적) *양쪽*의
합집합이다 — 후보 풀에 outside mids로 태깅된 문항이 없으면 `resolve_probe_target`이 탐색 턴에
`outside_mids[0]`을 겨냥해도 `select_probe`가 판별 문항을 못 찾아 결국 ε-탐색이 거부된다
(`wh1_loop.py:463`). 이 함수가 두 mids 원천을 합쳐 질의하는 것 자체가 ③의 배선이다.

**후보 0의 사유별 계상**(④): `ProbeSupplyFunnel`이 (가설 없음/오개념 미태깅/난이도 부재/전부
응답함) 4가지를 서로 다른 값으로 구분한다(`l2/axis_exclusions.py` 사유 계상 패턴 답습 — dataclass
+ 로거, 좌석명·정수 카운트·사유 코드만 로그, mids·problem_id·PII 0).
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from whymath_backend.l1.problem_bank.probe_candidates import fetch_probe_candidates_by_mids
from whymath_backend.l2.ability_estimation import resolve_item_difficulty_b
from whymath_backend.l4.misconception.hypothesis import MisconceptionHypothesis
from whymath_backend.l4.misconception.probe_selection import ProbeCandidate

__all__ = [
    "REASON_ALL_ADMINISTERED",
    "REASON_NO_DIFFICULTY",
    "REASON_NO_HYPOTHESIS",
    "REASON_UNTAGGED",
    "ProbeSupplyFunnel",
    "assemble_probe_candidate_pool",
]

logger = logging.getLogger("whymath.harness.wh1_probe_supply")

# 반환 후보 상한 — L1 기본값과 동형(정보이득 비교는 L4가 전량 순회하므로 넉넉히 유지).
_DEFAULT_LIMIT = 200

# 사유 코드(④) — `api/me.py` `CANDIDATE_ZERO_*` 네이밍 관례를 미러(문자열 상수·비식별).
REASON_NO_HYPOTHESIS = "no_hypothesis"  # 활성 가설·outside_mids 둘 다 비어 겨냥할 mids가 없음.
REASON_UNTAGGED = "untagged"  # mids는 있으나 코퍼스에 그 오개념을 태깅한 문항이 없음.
REASON_NO_DIFFICULTY = "no_difficulty"  # 태깅된 문항은 있으나 전부 difficulty_overall 미보유.
REASON_ALL_ADMINISTERED = "all_administered"  # 태깅+난이도 보유는 있으나 전부 이미 응답함.


@dataclass(frozen=True, slots=True)
class ProbeSupplyFunnel:
    """probe_candidates 조립 파이프라인 단계별 정직 회계 — 후보 0의 사유를 서로 다른 값으로 계상.

    네 단계는 파이프라인 순서와 같다(`l2.axis_exclusions.AxisExclusions`처럼 사유는 서로 배타적으로
    *첫 병목*만 계상 — `reason` 프로퍼티가 순서대로 판정). mids·problem_id 등 식별 정보는 담지
    않는다(정수 카운트뿐 — 로그 PII 0 불변).
    """

    mids_count: int = 0
    tagged_count: int = 0
    tagged_with_difficulty_count: int = 0
    final_count: int = 0

    @property
    def reason(self) -> str | None:
        """최종 후보가 0일 때만 값 — 4개 사유 중 파이프라인상 첫 병목(배타적 계상)."""
        if self.final_count > 0:
            return None
        if self.mids_count == 0:
            return REASON_NO_HYPOTHESIS
        if self.tagged_count == 0:
            return REASON_UNTAGGED
        if self.tagged_with_difficulty_count == 0:
            return REASON_NO_DIFFICULTY
        return REASON_ALL_ADMINISTERED


def _log_funnel(seat: str, funnel: ProbeSupplyFunnel) -> None:
    """후보 0건일 때만 구조화 로그 1줄(정상 공급은 소음 방지 — `log_axis_exclusions` 관례)."""
    reason = funnel.reason
    if reason is None:
        return
    logger.info(
        "probe_candidates 조립 0건 seat=%s reason=%s mids=%d tagged=%d tagged_with_difficulty=%d",
        seat,
        reason,
        funnel.mids_count,
        funnel.tagged_count,
        funnel.tagged_with_difficulty_count,
    )


def _target_mids(
    active_hypotheses: Sequence[MisconceptionHypothesis], outside_mids: Sequence[str]
) -> list[str]:
    """활성 가설 mids + outside mids → 순서보존 중복제거 질의 대상(③ ε-탐색 성립의 배선점).

    활용(활성 가설)과 탐색(outside_mids) *양쪽* 표적을 합쳐 질의해야 `resolve_probe_target`이
    어느 분기를 골라도(§2.2) 후보 풀에 판별 문항이 존재할 수 있다 — 한쪽만 질의하면 다른 분기는
    구조적으로 항상 후보 0(=거부)이 된다.
    """
    seen: set[str] = set()
    ordered: list[str] = []
    for mid in (*(h.misconception_id for h in active_hypotheses), *outside_mids):
        if mid not in seen:
            seen.add(mid)
            ordered.append(mid)
    return ordered


async def assemble_probe_candidate_pool(
    session: AsyncSession | None,
    *,
    active_hypotheses: Sequence[MisconceptionHypothesis],
    outside_mids: Sequence[str],
    user_id: uuid.UUID | None = None,
    seat: str = "wh1_probe_supply",
    limit: int = _DEFAULT_LIMIT,
) -> list[ProbeCandidate]:
    """활성 가설 mids + 웜스타트 outside mids → L1 역인덱스 조회 → L4 `ProbeCandidate` 조립.

    `session`이 None이면(호출자가 DB 컨텍스트를 안 가진 경로 — 예: 기존 단위테스트·shadow의
    `_spawn` 동시성 회피) 조회 자체를 시도하지 않고 빈 리스트(기존 동작 보존·회귀 0·로그 없음
    — ④ funnel은 *실제 조회*가 있었을 때만 의미가 있다). `session`은 있는데 mids가 비면
    (활성 가설·outside_mids 둘 다 없음) 조회 없이 빈 리스트 + 사유 `no_hypothesis` 로그.

    **never-break**(L1 조회 실패가 학생 턴을 깨지 않는다): DB 예외는 여기서 흡수해 예외 타입명을
    포함한 WARNING 로그만 남기고 빈 리스트로 강등한다(침묵 실패 금지·CLAUDE.md) — 호출자
    (`wh1_primary`·`wh1_shadow` 모듈의 턴 러너)의 상위 try/except와 이중 방어.

    난이도 로짓 변환은 여기서 L2 `resolve_item_difficulty_b`(JMLE 보정 `irt_difficulty_b` 우선·
    `difficulty_overall` 휴리스틱 폴백)로 수행한다 — L1은 원값만 반환하므로(L1→L2 역방향 의존
    금지) 이 조립 지점이 유일하게 두 계층을 합칠 수 있는 곳이다.

    Args:
      session: 읽기 전용 async 세션(None이면 조회 skip).
      active_hypotheses: 이번 턴의 *post-apply* 누적 활성 가설(웜 스타트·§2.2 활용 표적).
      outside_mids: 웜스타트 probe 힌트(`assemble_warmstart_probe_hints`) — 탐색 표적.
      user_id: 미응답 필터용 학생 id(L1 조회 좌석에 그대로 전달).
      seat: 로그 좌석명(shadow/primary 구분 — 회계 분리).
      limit: L1 반환 후보 상한.

    Returns:
      L4 `ProbeCandidate` 리스트(빈 리스트 가능 — 사유는 로그로 관측 가능·④).
    """
    mids = _target_mids(active_hypotheses, outside_mids)
    if session is None:
        # 세션 미제공(설계상 skip — 예: shadow의 `_spawn` 동시성 회피·기존 세션 없는 호출자)은
        # 조회 자체를 시도하지 않은 상태다. ④의 4-사유 funnel은 *실제 조회 결과*를 놓고 갈리는
        # 사유라 여기 해당하지 않는다 — 오분류(예: "untagged"로 잘못 계상) 방지를 위해 로그하지
        # 않는다(기존 `no_hypothesis`와 혼동되면 "가설은 있는데 왜 untagged?"로 오독될 수 있음).
        return []
    if not mids:
        _log_funnel(seat, ProbeSupplyFunnel(mids_count=0))
        return []

    try:
        query = await fetch_probe_candidates_by_mids(session, mids, user_id=user_id, limit=limit)
    except Exception as exc:  # noqa: BLE001 — L1 조회 실패는 턴을 안 깬다(never-break·타입명 로그).
        logger.warning(
            "probe_candidates L1 조회 실패(%s) seat=%s — 빈 후보로 진행",
            type(exc).__name__,
            seat,
            exc_info=True,
        )
        return []

    candidates: list[ProbeCandidate] = []
    for row in query.rows:
        b = resolve_item_difficulty_b(row.irt_difficulty_b, row.difficulty_overall)
        if b is None:  # 방어적 — L1이 difficulty_overall 보유만 통과시키므로 이론상 도달 안 함.
            continue
        candidates.append(
            ProbeCandidate(
                problem_id=row.problem_id,
                difficulty=b,
                discrimination=row.discrimination,
                misconception_tags=row.misconception_tags,
            )
        )

    _log_funnel(
        seat,
        ProbeSupplyFunnel(
            mids_count=len(mids),
            tagged_count=query.tagged_count,
            tagged_with_difficulty_count=query.tagged_with_difficulty_count,
            final_count=len(candidates),
        ),
    )
    return candidates
