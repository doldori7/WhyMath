"""L4 오답 매핑 *참조 무결성* 검증 — `Problem.distractor_map`의 카탈로그 대조(P3b).

`schema.problem.DistractorEntry`(L1)는 *구조*만 검증한다(choice_index≥0·misconception_id 비지
않음). 이 모듈은 그 위에서 **참조 무결성**을 본다 — 즉 매핑된 오개념 id가 *정본 카탈로그에
실재*하고, op_code를 줬다면 그 op-code가 실재하며 *가리키는 오개념과 정합*한지를 검사한다.

**레이어 규칙(CLAUDE.md 역방향 의존 금지)**: 이 검증은 L4에 산다 — L1 `DistractorEntry`를
import하고(L4→L1 허용) L4 카탈로그(`CATALOG_BY_ID`·`DISTRACTOR_BY_ID`)를 대조한다. L1
`schema/problem.py`는 이 모듈을 *알지 못한다*(L1→L4 금지) — 그래서 카탈로그 실재 검증을 L1에
두지 않고 여기로 끌어올렸다. `distractor.py`의 `DistractorOpCode._known_misconception`(생성 시점
fail-fast)와 같은 *정본 참조 보장* 철학을 *런타임 매핑*으로 확장한 것이다.

**왜 fail-loud인가(CLAUDE.md 우선순위 #2 — 법적·무결성)**: 미등록 오개념을 가리키는 매핑은
오진단(엉뚱한 오개념 코칭)으로 이어지고, op_code↔오개념 불일치는 카탈로그 정합을 깬다. 조용히
넘기지 않고(절대 금지 "환각 발견 시 조용히 넘어가지 말고") 오류를 *모아 보고*하거나(검증 패스)
*예외로 차단*한다(생성 게이트).

**어디서 부르나**: *콘텐츠 생성·검증 시점*(L3 콘텐츠 생성·검증 / L4 교수학)에서 자체 동등문제의
`distractor_map`을 확정하기 직전에 호출한다 — 예: 문항 생성 파이프라인이 오답 선지를 단 뒤
`raise_for_distractor_map(problem.distractor_map)`로 게이트한다. (실제 생성 플로 결선은 본
슬라이스 범위 밖 — 검증자만 제공한다. `distractor.py` 스캐폴드와 동형.)
"""

from __future__ import annotations

from collections.abc import Iterable

from whymath_backend.l4.misconception.catalog import CATALOG_BY_ID
from whymath_backend.l4.misconception.distractor import DISTRACTOR_BY_ID
from whymath_backend.schema.problem import DistractorEntry


def validate_distractor_map(entries: Iterable[DistractorEntry]) -> list[str]:
    """`distractor_map` 엔트리들의 참조 무결성을 검사해 *오류 메시지 목록*을 돌려준다.

    빈 목록(`[]`)이면 모두 정합(통과). 비어 있지 않으면 각 문자열이 위반 1건이다(여러 위반을
    *모아* 보고 — 한 번에 한 줄씩 고치게). 예외를 던지지 않는 *비파괴* 검사라 진단 UI·로그·배치
    감사에 적합하다. 생성 게이트처럼 *즉시 차단*이 필요하면 `raise_for_distractor_map`를 쓴다.

    검사 3종:
      ① `misconception_id ∈ CATALOG_BY_ID` — 정본 오개념 실재(미등록이면 위반).
      ② op_code를 줬다면 `op_code ∈ DISTRACTOR_BY_ID` — 정본 op-code 실재.
      ③ op_code를 줬다면 `DISTRACTOR_BY_ID[op_code].misconception_id == entry.misconception_id`
         — op-code가 가리키는 오개념과 엔트리의 오개념이 *정합*(불일치면 위반).

    구조(choice_index≥0·misconception_id 비지 않음·extra forbid)는 L1 `DistractorEntry`가 이미
    보장하므로 여기서 재검증하지 않는다(유효 엔트리만 들어온다고 가정 — 레이어 분리).
    """
    errors: list[str] = []
    for index, entry in enumerate(entries):
        # ① 오개념 id가 정본 카탈로그에 실재하는가(참조 무결성·오진단 방지).
        if entry.misconception_id not in CATALOG_BY_ID:
            errors.append(
                f"distractor_map[{index}] (choice_index={entry.choice_index}): "
                f"미등록 misconception_id={entry.misconception_id!r} — "
                f"catalog.CATALOG_BY_ID에 없음."
            )

        # op_code 미지정이면 ②③는 건너뛴다(op_code는 선택 — 오개념만 매핑 가능).
        if entry.op_code is None:
            continue

        # ② op-code가 정본 카탈로그에 실재하는가.
        op_code = DISTRACTOR_BY_ID.get(entry.op_code)
        if op_code is None:
            errors.append(
                f"distractor_map[{index}] (choice_index={entry.choice_index}): "
                f"미등록 op_code={entry.op_code!r} — "
                f"distractor.DISTRACTOR_BY_ID에 없음."
            )
            # op-code가 없으면 ③(정합)은 평가 불가 — 다음 엔트리로.
            continue

        # ③ op-code가 가리키는 오개념과 엔트리의 오개념이 정합하는가(카탈로그 정합).
        if op_code.misconception_id != entry.misconception_id:
            errors.append(
                f"distractor_map[{index}] (choice_index={entry.choice_index}): "
                f"op_code={entry.op_code!r}는 misconception_id="
                f"{op_code.misconception_id!r}를 가리키는데 엔트리는 "
                f"{entry.misconception_id!r}로 불일치."
            )

    return errors


def raise_for_distractor_map(entries: Iterable[DistractorEntry]) -> None:
    """참조 무결성 위반이 하나라도 있으면 `ValueError`로 *즉시 차단*(fail-loud 게이트).

    `validate_distractor_map`를 돌려 위반이 있으면 모든 위반을 한 메시지로 묶어 던진다. 콘텐츠
    생성·검증 파이프라인(L3/L4)이 `distractor_map`을 영속·노출하기 직전 게이트로 쓴다 —
    미등록 오개념·불일치 op-code가 *조용히* 저장되지 않게 한다(CLAUDE.md 우선순위 #2).
    """
    errors = validate_distractor_map(entries)
    if errors:
        joined = "\n  - ".join(errors)
        raise ValueError("distractor_map 참조 무결성 위반(정본 카탈로그 대조 실패):\n  - " + joined)


__all__ = ["raise_for_distractor_map", "validate_distractor_map"]
