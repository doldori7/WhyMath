"""채점 확정 시 해소된 스킬 배열을 `attempt_event`에 영속하는 writer (EOS-57).

**존재 이유(소급 불가 축)**: `l2.skill_mastery_tracking.record_problem_attempt_skill_mastery`는
채점 순간 concept→skill 브리지로 스킬을 *해소*해 `skill_mastery_history`를 적재하지만, **어떤
스킬이 이 시도에 귀속됐는가**는 런타임에서만 존재하고 버려져 왔다(EOS-53 crosswalk 갭 #4 실측:
영속 좌석 0). 숙달 시계열은 "스킬 s의 값이 언제 어떻게 변했는가"를 남길 뿐, "시도 a가 스킬
{s1,s2}를 건드렸다"는 결합은 남기지 않는다 — 그 결합은 문항↔개념↔스킬 매핑이 이후에 바뀌면
**영원히 재구성 불가**다(W2 "되돌릴 수 없는 스키마" ①). 12월 데이터에 남길 축이라 지금 적재한다.

**계층 위치**: L2(학습자 모델)의 영속 좌석이다 — 해소 규칙(모델 B·역할 비대칭)은
`skill_mastery_tracking`이 소유하고, 이 모듈은 *그 결과를 기록*만 한다. 채점 경로(L5 API 핸들러)
2곳이 같은 writer를 경유하도록 여기에 단일 seam을 둔다(중복 구현 금지 — `_complete_problem`이
`submit_attempt`의 L2 헬퍼를 재사용하는 기존 관례와 동형).

**범위 경계(EOS-57 acceptance ③ 집행 별항)**: 이 모듈은 **영속 좌석 + writer까지**다. 소비 지점
전환(`skill_mastery_tracking`이 런타임 해소 대신 이 이벤트 기록을 읽는 것)은 후속 태스크
**EOS-63**(`attempt-skill-event-consumption`)이 소유한다 — 지금 소비를 바꾸면 기록이 0건인 상태에서
숙달 전파가 죽는다(기록이 먼저 쌓여야 하며, 전환 선결 조건은 기록률 리포트의 실측 수치다).

**None ≠ [] 규약**: `skill_ids`는 nullable이고 server_default가 없다.
  - NULL = writer 미도달(구판 이벤트·다른 event_type·이 배선 이전의 시도)
  - `[]`  = 해소를 *실행했고* 매핑이 0건이었다(concept→skill 브리지 미보유 문항)
둘을 구분해야 기록률 리포트가 "안 돌았다"와 "돌았는데 0건"을 다른 글자로 말할 수 있다
(`harness/attempt_skill_event_reach_report.py` — CLAUDE.md "작동한 비율" 원칙).
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable
from datetime import UTC, datetime
from enum import Enum

from sqlalchemy.ext.asyncio import AsyncSession

from whymath_backend.db.models.activity import AttemptEvent
from whymath_backend.schema.enums import EventType
from whymath_backend.schema.event_data_contract import build_event_data

__all__ = ["AttemptSource", "record_attempt_skill_event"]


class AttemptSource(str, Enum):
    """채점 경로 라벨(폐쇄 2종) — `문제시도` 이벤트 `event_data.source`.

    한 경로에만 writer가 배선되는 회귀를 기록률 리포트가 *경로별 분모*로 잡아내기 위한 축이다
    (전체 평균 하나면 한쪽 경로 전멸이 절반의 감소로 희석돼 보인다).
    """

    attempt_submit = "attempt_submit"
    """`POST /v1/me/attempts` — 클라 자가보고 `is_correct`를 신뢰하는 v1 경로(api/me.py)."""

    coach_completion = "coach_completion"
    """코치 대화 완료 확정 — 서버가 `verify_final_answer`로 판정한 경로(api/coach.py)."""


async def record_attempt_skill_event(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    attempt_id: uuid.UUID,
    problem_id: uuid.UUID,
    is_correct: bool,
    skill_ids: Iterable[str],
    source: AttemptSource,
    event_at: datetime | None = None,
) -> AttemptEvent:
    """해소된 스킬 배열을 `문제시도` 이벤트 1건으로 적재하고 **commit까지 수행**한다.

    `skill_ids`는 *해소 결과 그대로*를 순서 보존·중복 제거해 싣는다(빈 반복자면 `[]` — None으로
    승격하지 않는다: "해소했는데 0건"은 실측이고 NULL은 미기록이라 의미가 다르다).

    commit을 여기서 하는 이유: 두 호출부 모두 이 시점에 이미 attempt를 commit해 트랜잭션 경계가
    닫혀 있고(숙달 전파 헬퍼도 자체 commit한다), 기록 유실 시 "채점은 됐는데 스킬 귀속만 사라진"
    상태가 조용히 생기는 것을 막아야 한다. 예외는 삼키지 않는다 — 실패하면 호출부로 전파해
    핸들러의 트랜잭션 정책이 판정한다(침묵 실패 금지: best-effort로 삼키면 소급 불가 축이
    무증상으로 비는데, 그것이 이 태스크가 존재하는 이유 자체다).

    전파 설계가 배포에서 안전한 근거(실측·가정 아님): `문제시도` enum 값이 DB에 없으면 이
    INSERT가 실패해 채점 응답이 500이 된다 — 즉 "코드가 마이그레이션보다 먼저 뜨는" 순서에
    민감하다. `deploy.yml`은 `alembic upgrade head`를 컨테이너 기동(`up -d`)보다 **먼저**
    실행하므로(deploy.yml:184-190) 신규 코드가 트래픽을 받을 때는 값이 이미 존재한다.
    `skip_migration=true`는 운영자의 명시적 롤백 선택이며 런북 §6이 판단 기준을 소유한다.

    `event_at`은 서버 기록(수신) 시각이다 — 이 테이블의 기존 writer 전부와 같은 의미로 서버
    `now(UTC)`를 넣는다(EOS-48 실측 명문화). 클라 신고 발생 시각(`event_time`)은 채점 경로에
    신고 축이 없어 채우지 않는다(NULL=미신고 — 수신 시각 복제는 날조).
    """
    # 순서 보존 중복 제거 — 같은 스킬이 여러 개념에서 해소돼도 배열엔 1회만(집계 분모 왜곡 0).
    deduped: list[str] = list(dict.fromkeys(skill_ids))
    event = AttemptEvent(
        event_at=event_at or datetime.now(UTC),
        attempt_id=attempt_id,
        user_id=user_id,
        problem_id=problem_id,
        event_type=EventType.문제시도,
        event_data=build_event_data(
            EventType.문제시도,
            is_correct=is_correct,
            source=source.value,
        ),
        skill_ids=deduped,  # [] 유지(None 승격 금지 — 미기록과 해소 0건은 다른 사실).
    )
    session.add(event)
    await session.commit()
    return event
