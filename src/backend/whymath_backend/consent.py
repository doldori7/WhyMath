"""미성년 동의 게이트의 *서버측* 연령 파생(순수, FastAPI·DB 무관) — L5 인증 집행 계층.

PIPA 만14세 미만 법정대리인 동의(docs/legal/pipa_data_matrix.md §3)의 *실효화* 한 조각이다.
동의 게이트(`api/_auth.py.get_consented_user`)는 `is_minor=True & parent_consent_at IS NULL`이면
403을 던지지만, `is_minor`가 *서버에서 파생되지 않으면* 무력하다 — 만14세 미만 사용자가
`is_minor=None`(미판정)으로 남거나 클라이언트가 `is_minor=false`를 보내 게이트를 우회할 수
있기 때문이다. 이 모듈은 `birth_year`로부터 `is_minor`를 *서버에서* 산출하는 단일 진실
함수를 제공한다(가입 콜백·PATCH 양쪽 쓰기 경로가 공유). **클라이언트가 보낸 `is_minor`는
절대 신뢰하지 않는다** — 호출 측(`api/auth.py`·`api/users.py`)이 이 파생값으로 덮어쓴다.

연나이(year-reckoning) 보수성: 우리는 `birth_year`만 수집한다(월일 미수집·개인정보 최소화,
schema/user.py docstring). 정확한 *만 나이*는 생일이 있어야 계산되지만 없으므로, 연나이
(`current_year - birth_year`)가 임계와 *같을 때까지* 미성년으로 본다(`<=` 비교). 예: 올해가
2026이고 임계 14면 birth_year=2012(연나이 14)는 생일 전이면 실제 만 13세일 수 있어 게이트한다
(과보호). 의사결정 우선순위(CLAUDE.md: 1 학생 안전·2 법적 준수 > 5 UX)상 *진짜 만13세를
게이트 안 하는 것은 위반*이고 *만14세를 게이트하는 것은 약간의 마찰*일 뿐이라, 모호하면
보호 쪽으로 기운다. 정확한 만나이 게이팅(생일 수집)·동의 GRANT 플로우·재확인 주기는 **변호사
자문 필수** 후속이다(pipa_data_matrix.md §3 체크리스트).

미상(unknown) 보존: `birth_year`가 None이면 *파생도 None*이다 — `get_consented_user`의 기존
설계("is_minor=None은 게이트 통과 = *알려진* 미성년자만 차단")를 유지한다. 미상을 강제 차단
하지 않는다(가입 단계에서 birth_year를 *필수로 받을지*는 별도 정책 결정이며, 이 함수 범위
밖이다 — 여기선 "모르면 모른다"를 그대로 둔다).
"""

from __future__ import annotations

from datetime import datetime, timezone


def current_year_kst() -> int:
    """현재 연도(UTC 기준). 연나이 파생의 `current_year` 기본 공급원.

    연 단위만 쓰므로(birth_year도 연 단위) 시간대 차이가 결과를 바꾸는 경계는 *연말~연초
    하루 남짓*뿐이고, 그 경계에서도 *보수적 게이팅* 방향으로 기운다(연초에 UTC가 한 해 늦게
    넘어가면 연나이가 1 작게 잡혀 더 오래 미성년 → 과보호). UTC로 고정해 서버 로케일 의존을
    없앤다(KST는 UTC+9라 항상 같거나 하루 앞설 뿐 — 보수성 무해). 테스트는 `current_year`를
    명시 주입해 결정론으로 검증한다(이 함수에 의존하지 않음).
    """
    return datetime.now(tz=timezone.utc).year


def derive_is_minor(
    birth_year: int | None,
    *,
    current_year: int,
    threshold: int,
) -> bool | None:
    """`birth_year`로부터 미성년 여부를 *서버측* 파생한다(클라 입력 미신뢰의 단일 진실).

    - `birth_year is None` → `None`(미상 보존 — `get_consented_user` "미상은 게이트 통과" 설계
      유지·강제 차단 안 함). "가입 시 birth_year 필수"는 별도 정책 결정(이 함수 범위 밖).
    - 그 외 → *보수적 연나이* 판정: `is_minor = (current_year - birth_year) <= threshold`.
      월일 미수집이라 연나이가 임계와 같으면 실제 만나이는 임계-1일 수 있어(생일 전) 미성년
      으로 본다(과보호 — 모듈 docstring 근거). 미래 연도(`current_year - birth_year < 0`)도
      `<= threshold`라 True가 되나, birth_year는 schema에서 1900~2100으로 검증되고 미래생은
      비정상 입력이므로 *보호 쪽*(미성년)으로 두는 것이 안전하다.
    """
    if birth_year is None:
        return None
    return (current_year - birth_year) <= threshold
