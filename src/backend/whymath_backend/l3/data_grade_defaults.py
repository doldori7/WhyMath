"""호출부가 선언하는 *자료 등급* 프로파일의 단일 좌석 (EOS-59 ③).

왜 이 좌석이 필요한가 (`escalation_defaults.py`와 같은 논거)
------------------------------------------------------------
`RoutingRequest.data_licenses`는 "이 프롬프트에 실리는 자료가 어느 라이선스인가"를 선언한다.
프로덕션 호출부 16곳이 그 값을 각자 인라인 리터럴로 들고 있으면, **코퍼스 구성이 바뀌는 날**
(예: AIHub 유래 문항이 문제은행에 들어오는 날) 열여섯 군데를 다시 찾아다녀야 하고, 그중
하나만 빠뜨려도 그 경로만 조용히 국외로 나간다 — 그리고 그 누락은 아무 에러도 내지 않는다.

`l3/escalation_defaults.py`가 구독·예산 리터럴에 대해 이미 같은 문제를 같은 방식으로 풀었다
(여섯 호출부의 `"free"`/`0.0`을 한 자리로). 이 모듈은 그 관례를 *법적 축*에 적용한다 —
프로파일 이름은 "이 호출이 다루는 자료가 무엇인가"를 말하고, 그 이름이 어떤 `LicenseType`으로
번역되는지는 여기 한 곳만 안다.

등급 어휘를 새로 만들지 않는다
-----------------------------
아래 상수는 **새 등급 스케일이 아니라 기존 `LicenseType` 값의 이름 붙인 묶음**이다
(`escalation_defaults.StudentEscalationDefaults`가 기존 필드값을 이름 붙여 모은 것과 동형).
반출 가부의 의미는 여전히 `l1/rights/permission_map.py`가 정의하고, 이 모듈은 "우리 호출부가
다루는 자료가 그중 무엇인가"만 고른다.

2026-09-01 실측 근거 (이 배정이 오늘 참인 이유)
---------------------------------------------
`data/corpus/*/_provenance.json` 전 27개 코퍼스의 `pool`이 모두 `whymath-original`이다 —
현재 저장소에 적재된 문항·개념·오개념 자료 중 **AIHub 유래는 0건**이다. 그래서
`SELF_AUTHORED_CORPUS`가 오늘은 `INTERNAL_OWNED` 하나로 참이다.

**바뀌는 조건(명시)**: AIHub 데이터셋(`licensing_safety.md` §133의 71718·71716·71859·479·
71518 등)에서 유래한 자료가 저작 파이프라인의 입력이 되는 순간, 이 상수는
`(INTERNAL_OWNED, AIHUB_OPEN)`이 되어야 한다 — 그러면 `export_judgment`의 보수적 병합이
저작 경로 전체를 자동으로 LOCAL로 묶는다(호출부 수정 0). 그것이 이 좌석의 존재 이유다.
"""

from __future__ import annotations

from typing import Final

from whymath_backend.schema.enums import LicenseType

__all__ = [
    "SELF_AUTHORED_CORPUS",
    "STUDENT_SUBMITTED",
    "STUDENT_SUBMITTED_WITH_CORPUS",
    "SYNTHETIC_PROBE",
]


SELF_AUTHORED_CORPUS: Final[tuple[LicenseType, ...]] = (LicenseType.INTERNAL_OWNED,)
"""자체 저작 코퍼스 — 문항은행·개념 그래프·오개념 카탈로그·성취기준 매핑.

반출 가능(`INTERNAL_OWNED.export=True`) — 우리가 권리자이므로 국외 프로바이더 호출에 실어도
라이선스 위반이 아니다. **위 "바뀌는 조건"이 성립하면 여기를 고친다.**
"""

SYNTHETIC_PROBE: Final[tuple[LicenseType, ...]] = (LicenseType.WHYMATH_GENERATED,)
"""운영 계측용 합성 프롬프트 — 비용 프로브·라이브 프리플라이트의 스텁 문자열.

사람의 저작물도 학생 자료도 아닌, 이 저장소가 그 자리에서 만들어 낸 문자열이다. 반출 가능
(`WHYMATH_GENERATED.export=True`) — 클라우드 경로 계측이 이 등급 덕에 성립한다(계측이
게이트 때문에 로컬로 새면 클라우드 비용을 영영 못 잰다).
"""

STUDENT_SUBMITTED: Final[tuple[LicenseType, ...]] = (LicenseType.USER_GENERATED,)
"""학생이 제출한 자료 — 손글씨 크롭·풀이 문장 등 학생 본인의 저작.

반출 **불가**(`USER_GENERATED.export=False`) → 국내(로컬) 전용. 권리 모델의 선언이자
CLAUDE.md 절대 금기("미성년자 개인정보를 분석·마케팅 외부 공유 금지")와 같은 방향이다.
오늘 이 등급을 쓰는 경로는 이미 다른 이유로도 LOCAL이므로(비전 단축 경로·free 구독) 동작
변화는 0이며, 이 선언은 결제·구독 배선이 들어와 비즈니스 가드가 열리는 날에도 학생 자료가
국외로 나가지 않게 잡아 주는 *법적 잠금*이다.
"""

STUDENT_SUBMITTED_WITH_CORPUS: Final[tuple[LicenseType, ...]] = (
    LicenseType.USER_GENERATED,
    LicenseType.INTERNAL_OWNED,
)
"""학생 진술 + 자체 카탈로그가 *한 프롬프트에* 함께 실리는 경우(오개념 judge 등).

두 등급을 다 적는다 — 보수적 병합이 알아서 가장 제한적인 쪽(USER_GENERATED)을 택하므로
결과는 차단이지만, "무엇이 실렸는가"를 정직하게 남기는 편이 나중에 등급이 바뀔 때 판단
근거가 된다(하나로 뭉개면 카탈로그가 실렸다는 사실이 기록에서 사라진다).
"""
