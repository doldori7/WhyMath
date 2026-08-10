"""L4 오답 선택 인덱스 → 오개념 역방향 조회 (ASM-06 — REC-02의 반대 방향).

학생이 실제로 고른 객관식 보기 인덱스(`selected_choice_index`)를 문제의 `distractor_map`
(오답 선지→오개념 매핑, P3b·`schema.problem.DistractorEntry`)에 대조해 어떤 오개념이 이
오답을 유발했는지 역추적한다.

**방향 대비**:
  - `l4.misconception.distractor`(P3b 스캐폴드) 모듈 docstring이 예고한 "② 학생이 고른
    오답 선지를 오개념으로 역추적"을 실제로 결선하는 조회 함수다.
  - `l1.problem_bank.probe_candidates`(REC-02)는 *반대 방향* — 오개념 가설 집합에서
    출발해 그 오개념을 겨냥한 진단 문항 *후보*를 찾는다(가설→프로브). 이 모듈은 학생이
    이미 낸 답(선택 인덱스) 하나에서 출발해 오개념 *id 하나*를 찾는다(응답→오개념).

**선행 조사 결론(스코프 확정)**: `student_answer`는 시스템 전 구간(자유텍스트)에서 "몇 번
보기를 골랐는가" 자체를 담지 않는다 — NLP-02 shadow 채점(`harness/attempt_grading_shadow_
report.py`)은 수치/기호식 검산 오프라인 배치이지 선택 인덱스를 포착하지 않는다. 그래서
`selected_choice_index`가 `api/me.py`(`AttemptSubmitRequest`)에 신규 필드로 추가됐고,
이 함수는 그 값을 받아 오개념으로 옮기는 순수 변환만 담당한다.

**reactive retrieval(CLAUDE.md 협상 불가)**: `selected_choice_index`가 없으면(자유응답형·
클라 미전송) 즉시 `None`을 반환하고 `distractor_map`을 들여다보지도 않는다. 오개념 카탈로그를
여기서 로드하지 않는다 — 반환값은 `distractor_map`에 *이미 적힌* `misconception_id` 문자열
그대로이며, 그것이 정본 카탈로그(`catalog.CATALOG_BY_ID`)에 실재하는지의 참조 무결성은
콘텐츠 생성 시점 게이트(`l4.misconception.validate.raise_for_distractor_map`)가 이미
보장한 바를 신뢰한다 — 학생 제출마다 카탈로그를 다시 대조하는 건 이 함수의 책임이 아니다.

**형태만 본다(참조 무결성 재검증 아님)**: `l1.problem_bank.probe_candidates._match_probe_rows`
선례와 동형 — `distractor_map`은 DB JSONB 원값(list[dict])을 그대로 받는다(Pydantic
`DistractorEntry`로 재검증하지 않음). 원소가 매핑이 아니거나 `choice_index`/
`misconception_id`가 없으면 조용히 건너뛴다 — 여긴 학생 제출을 처리하는 라이브 경로라
콘텐츠 결함(형태 불량 원소)으로 요청 자체가 크래시하면 안 된다(참조 무결성 위반은 이미
생성 시점 게이트가 잡아야 할 문제 — `validate.py` docstring 참조).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

__all__ = ["resolve_misconception_from_choice"]


def resolve_misconception_from_choice(
    distractor_map: Sequence[Mapping[str, Any]] | None,
    selected_choice_index: int | None,
) -> str | None:
    """학생이 고른 보기 인덱스 → 그 오답을 유발한 오개념 id(있으면). 순수 함수(DB·I/O 0).

    Args:
      distractor_map: 이 문제의 오답 선지→오개념 매핑(`Problem.distractor_map` 원값). 각
        원소는 최소 `choice_index`(int)·`misconception_id`(str)를 갖는 매핑을 기대한다
        (`schema.problem.DistractorEntry.model_dump()`와 동형이나 raw dict도 그대로 허용).
        `None`이거나 빈 시퀀스면 매핑 없음 취급.
      selected_choice_index: 학생이 실제로 고른 0-기반 보기 인덱스(`Problem.choices` 위치).
        `None`이면 학생이 인덱스를 보고하지 않음(자유응답형 등) — `distractor_map`을 보지
        않고 즉시 `None`(reactive — 불필요한 순회 생략).

    Returns:
      일치하는 엔트리의 `misconception_id`. 다음은 모두 `None`이다: `selected_choice_index`가
      `None`·`distractor_map`이 비었거나 없음·학생이 *정답* 선지를 골라 매핑에 없음·일치하는
      엔트리의 `misconception_id`가 빈 문자열이거나 누락.
    """
    if selected_choice_index is None or not distractor_map:
        return None
    for entry in distractor_map:
        if not isinstance(entry, Mapping):
            continue  # 형태 불량 원소 — 조용히 제외(참조 무결성은 생성 시점 게이트 소관)
        if entry.get("choice_index") != selected_choice_index:
            continue
        misconception_id = entry.get("misconception_id")
        return str(misconception_id) if misconception_id else None
    return None
