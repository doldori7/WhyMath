"""오개념 방향 판별 judge 프롬프트 정본 — `docs/prompts/misconception_judge.md` 원문 인용(슬108).

**드리프트 방지 원칙**(`l4/polya/prompts.py` 동일 패턴): SYSTEM 문구·USER 템플릿은
`docs/prompts/misconception_judge.md`의 *원문을 그대로* 옮긴다. 표현·문구를 바꿀 때는 그 문서를
*먼저* 갱신한 뒤 코드를 맞춘다(doc-first 불변·pedagogy-designer 위임). 이 상수가 doc과 어긋나면
회귀 가드 테스트(`test_misconception_judge.py`의 원문 정합 단언)가 깨진다.

judge는 *검증자*다 — 생성·코칭이 아니다(doc §"judge의 자리"). 출력은 학생 비노출 내부 필터로,
substring·임베딩이 못 가리는 *방향(⇒ 역)·부정(≠)·등치(=)*를 언어 추론으로 판별해 거짓양성을
거른다(doc §"무엇을 푸는가"). 출력 형식은 *정확히 두 줄*(`판정:` / `근거:`).
"""

from __future__ import annotations

from whymath_backend.l4.misconception.models import Misconception

# ──────────────────────────────────────────────────────────────────────────
# SYSTEM 프롬프트 — `docs/prompts/misconception_judge.md` "SYSTEM 프롬프트"(L48-84) 원문.
# 변경 시 doc 먼저(드리프트 방지). 줄바꿈·기호·번호까지 원문 그대로 유지한다.
# ──────────────────────────────────────────────────────────────────────────
JUDGE_SYSTEM = """당신은 한국 중·고등학교 수학교육의 *진단 검증자*다.

[역할]
당신은 오개념을 *생성하거나 가르치지 않는다*. 답·힌트·풀이·코칭을 만들지 않는다.
당신은 오직 하나만 한다: 주어진 "학생 진술"이 주어진 "오개념(틀린 믿음)"을
*실제로 표현하는지* 판정한다. 당신의 판정은 학생에게 보이지 않는 내부 필터다.

[입력]
- 학생 진술: 학생이 풀이 중 적거나 말한 문장(들).
- 오개념 이름: 후보로 올라온 오개념의 이름.
- 틀린 믿음(canonical): 그 오개념을 가진 학생이 *가정하는 틀린 명제*.

[판정 — 3값 중 하나]
- 예    : 학생 진술이 그 *틀린 믿음을 실제로 표현*한다. (진짜 오개념)
- 아니오 : 학생 진술이 *수학적으로 올바르거나*, 그 오개념과 *다른 말*이다.
- 불확실 : 모호하거나 정보가 부족해 판단하기 어렵다.

[핵심 원칙 — 방향·부정·등치를 정밀히 구분]
1. 함의 방향(⇒): "A이면 B"와 그 역 "B이면 A"는 *다른 명제*다.
   틀린 믿음이 "A이면 B"인데 학생이 *올바른* 역 "B이면 A"를 적었다면 → 아니오.
   (예: 틀린 믿음 "연속이면 미분가능" vs 올바른 "미분가능하면 연속" → 아니오)
2. 부정(≠·아니다·성립하지 않는다): 틀린 믿음이 "A = B"(또는 "A이다")인데
   학생이 *올바르게* "A ≠ B"(또는 "A가 아니다")라고 적었다면 → 아니오.
   (예: 틀린 믿음 "f∘g = g∘f" vs 올바른 "합성은 순서를 바꾸면 달라진다" → 아니오)
3. 등치(=): 두 대상을 동일시한 진술인지, 단지 *나란히 언급·대조*한 진술인지 구분한다.
   대조·비교는 동일시가 아니다.
4. *수학적으로 올바른 진술은 오개념이 아니다.* 주제가 같다는 이유만으로 예라고 하지 않는다.

[보수성 — 불확실을 적극 허용]
- 진술이 단편적·모호해 틀린 믿음을 표현하는지 *확신할 수 없으면* → 불확실.
- 학생을 함부로 오개념으로 단정하지 않는다(거짓 단정 < 놓침, 학생 정서가 먼저).
- 확실히 올바르거나 확실히 다른 말일 때만 아니오. 확실히 틀린 믿음일 때만 예.

[출력 형식 — 반드시 정확히 두 줄, 다른 말 금지]
판정: 예|아니오|불확실
근거: <한 줄 설명. 방향/부정/등치 중 무엇이 근거인지 명시>"""


# ──────────────────────────────────────────────────────────────────────────
# USER 템플릿 — `docs/prompts/misconception_judge.md` "USER 템플릿"(L93-104) 원문.
# 플레이스홀더 3개(`{misconception_name}`·`{canonical_statement}`·`{student_statement}`)는
# 카탈로그(`catalog.py`)의 `name_kr`·`canonical_statement` + 학생 진술에서 주입된다.
# ──────────────────────────────────────────────────────────────────────────
JUDGE_USER_TEMPLATE = """다음 학생 진술이 이 오개념(틀린 믿음)을 표현하는가?

[오개념 이름] {misconception_name}
[틀린 믿음(canonical)] {canonical_statement}

[학생 진술]
{student_statement}

위 학생 진술이 *틀린 믿음을 실제로 표현*하면 예, *올바르거나 다른 말*이면 아니오,
*모호하면* 불확실로 판정하라. 정확히 두 줄(판정/근거)로만 답하라."""


def build_judge_user(student_statement: str, misconception: Misconception) -> str:
    """USER 프롬프트 조립 — 템플릿 3개 플레이스홀더에 학생 진술·오개념을 주입한다.

    `misconception_name`←`misconception.name_kr`(짧은 한국어 라벨), `canonical_statement`←
    `misconception.canonical_statement`(*틀린 믿음*)을 채운다(doc USER 템플릿 주석: 카탈로그
    name_kr·canonical_statement에서 옴). 템플릿 자체는 `JUDGE_USER_TEMPLATE`(doc 원문)이라
    *문구는 코드가 만들지 않는다* — 드리프트 방지(doc-first). `.format`이므로 학생 진술에
    중괄호가 있어도 안전하다(템플릿 외 치환 없음 — 학생 텍스트는 *값*으로만 들어간다).
    """
    return JUDGE_USER_TEMPLATE.format(
        misconception_name=misconception.name_kr,
        canonical_statement=misconception.canonical_statement,
        student_statement=student_statement,
    )


__all__ = ["JUDGE_SYSTEM", "JUDGE_USER_TEMPLATE", "build_judge_user"]
