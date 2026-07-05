"""L4 선수 복습 코칭 결정 — L2 선수개념 추천(막힌 선수) → "선수 먼저 복습" 코칭.

`docs/architecture/04_pedagogy_engine.md`: L4는 *결정* 계층(L3=생성·L5=노출). 본 모듈은 L2
선수개념 추천(`l2.prerequisite_recommendation.recommend_prerequisite_gaps`)이 식별한 *약개념의
막힌 선수개념*을 받아 **"막힌 선수가 있으면 후행 개념을 바로 코칭하지 말고 선수 복습을 먼저
권한다"**는 교수학적 결정을 내린다(LTHC·기초 우선·CLAUDE.md 교수학 원칙).

핵심 통찰: 후행 개념이 안 되는 *근본 원인*이 선수 결손일 수 있다. 후행을 바로 코칭하면 비계가
허공에 뜬다 — 가장 약한 선수(`gaps[0]`, L2가 weakness asc 정렬로 이미 top blocker)부터 다지는
편이 효과적이다. 이는 *바로 정답 제공*이 아니라 *선수 복습을 권유*하는 메타인지 코칭이다(답
미루기 원칙 준수).

레이어 경계 준수(L4→L2 다운워드 의존·허용): L4는 L2(`PrerequisiteGap`)를 *안다*. 이 모듈은
**순수 결정**만 한다 — DB·async·fetch 없음(데이터 fetch는 L5 오케스트레이터가 `recommend_
prerequisite_gaps`로 수행해 `gaps`를 주입). `recommend_coaching`(BKT/IRT 신호)과 동형 패턴.

redaction·노출 계약(CLAUDE.md 우선순위 #2 — 협상 불가): rationale·prompt에 삽입되는 건
*안전 표시 필드*(name_ko·concept_name)뿐이다. `PrerequisiteGap` 스키마에 본문(description·
formal_definition·evidence) 슬롯이 *없어* 구조적으로 흐를 수 없다. 학생 노출 prompt는
*격려·메타인지 유도*이며 막힌 선수를 *비난하지 않는다*(부정 강화·우열·"정답 빠르게" 금지).
"""

from __future__ import annotations

from collections.abc import Sequence

from whymath_backend.l2.prerequisite_recommendation import PrerequisiteGap
from whymath_backend.l4.metacognitive_trigger import CoachingTrigger
from whymath_backend.l4.socratic.categories import SocraticCategory


def recommend_prerequisite_coaching(gaps: Sequence[PrerequisiteGap]) -> CoachingTrigger | None:
    """막힌 선수개념 목록에서 "선수 먼저 복습" 코칭 결정 — 순수·결정론(`recommend_coaching` 동형).

    `gaps`는 L2 `recommend_prerequisite_gaps`의 결과로 **weakness asc 정렬**(`gaps[0]` = 가장
    약한 선수 = top blocker)이라고 가정한다. 비면(막힌 선수 없음) **None**을 돌려준다 — 선수
    코칭을 *하지 않는다*(L5가 fallback으로 일반 메타인지 코칭으로 넘어감). 있으면 `gaps[0]`
    기준으로 `CoachingTrigger(focus="prerequisite_review", ...)`를 빌드한다.

    rationale(교사용)·prompt(학생용)는 정적 dict 일반 템플릿 대신 **top blocker 이름으로 동적
    구성**한다(구체화). 표시명은 `name_ko`(atom_node 안전 메타·S0-4d) → `concept_name`(backend
    concept) → "선수개념" 순으로 안전하게 fallback한다(둘 다 표시용 안전 필드·본문 아님).
    선수가 2개 이상이면 rationale 끝에 "(다른 막힌 선수 N개 더 있음)"을 부가한다.

    학생 prompt는 격려·메타인지 유도이며 막힌 선수를 *비난하지 않는다*(CLAUDE.md 톤). 한국어
    조사 안전을 위해 '…부터'를 쓴다(받침 유무 무관). socratic_category는 CLARIFICATION(기초
    지향·선수 명료화).
    """
    if not gaps:
        return None  # 막힌 선수 없음 → 선수 코칭 안 함(L5가 일반 메타인지 코칭으로 fallback).

    top = gaps[0]  # L2가 weakness asc 정렬 → gaps[0] = 가장 약한 선수 = top blocker.
    # 표시명 — atom_node 안전 메타(name_ko·S0-4d) → backend concept명 → 일반어 순 fallback.
    # 셋 다 *안전 표시 필드*다(본문 슬롯 없음·redaction은 PrerequisiteGap 스키마가 보장).
    display = top.name_ko or top.concept_name or "선수개념"

    # 약점 신호(weakness) 표현 — weak_only=True면 보통 float(측정 있음)·None이면 "측정 부족".
    weakness_pct = f"{top.weakness:.0%}" if top.weakness is not None else "측정 부족"

    rationale = (
        f"이 개념의 가장 큰 장애물은 선수개념 '{display}' 미숙달로 보입니다"
        f"(약점 신호 {weakness_pct}). 후행 개념을 바로 다루기보다 선수를 먼저 다지는 편이"
        f" 효과적입니다(LTHC·기초 우선)."
    )
    # 선수가 2개 이상이면 "더 있음" 부가(top blocker만 노출하되 갯수는 알림·교사용 맥락).
    if len(gaps) > 1:
        rationale += f" (다른 막힌 선수 {len(gaps) - 1}개 더 있음)"

    # 학생용 prompt — 격려·메타인지 초대. 비난 0·"정답 빠르게" 0·우열 0. 바로 답이 아니라
    # 선수 복습을 *권유*(답 미루기 원칙). '…부터'로 한국어 조사 안전.
    prompt = (
        f"이 문제를 풀기 전에, 먼저 '{display}'부터 한 번 같이 떠올려 볼까? "
        f"기초가 탄탄해지면 지금 개념도 훨씬 또렷하게 보일 거야."
    )

    return CoachingTrigger(
        focus="prerequisite_review",
        rationale=rationale,
        prompt=prompt,
        socratic_category=SocraticCategory.CLARIFICATION,
    )


__all__ = ["recommend_prerequisite_coaching"]
