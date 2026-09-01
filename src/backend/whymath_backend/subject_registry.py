"""과목 어댑터 **조립 지점**(DI seat) — Core가 구현체를 모른 채 능력을 얻는 유일한 통로 (EOS-69).

## 이 모듈이 존재하는 이유

`schema.subject_adapter.SubjectAdapter`는 *계약*이고 `l4.subject_adapter_math.MathSubjectAdapter`
는 *구현*이다. Core(`api`·`l3` CORE 키·`l4`·`l6`)가 구현을 직접 import하면 EOS-67 경계 계약이
위반으로 잡는다 — 그리고 그것이 옳다. Core가 `MathSubjectAdapter`를 아는 순간 "Physics를
붙일 때 Core를 뜯지 않아도 된다"가 거짓이 되기 때문이다.

그래서 구현체를 아는 모듈이 **정확히 하나** 필요하다. 그게 여기다. 이 모듈은 EOS 경계 배정에서
**INFRA**다(`config`·`app`과 같은 횡단 인프라) — 경계 계약의 source가 아니므로 구현체를 알아도
위반이 아니고, 알아야 일을 할 수 있다.

## 두 가지 주입 경로 (둘 다 필요하다)

1. **명시 주입** — `app.create_app`(또는 테스트)이 `set_subject_adapter(...)`로 심는다. 이것이
   *진짜* 조립이다. 과목을 바꾸려면 여기 한 줄만 바꾼다.
2. **지연 기본값** — 아무도 심지 않았으면 첫 호출에서 기본 과목을 만든다. HTTP 앱 밖 진입점
   (하네스 CLI·배치 시더·단위 테스트)이 전부 조립 코드를 복사하지 않게 하기 위한 것이다.

기본값이 math인 것은 **배포 설정**이지 Core 지식이 아니다 — 그 사실이 코드에 드러나도록,
기본값 결정은 이 파일 안에서만 일어나고 import는 함수 안에서(지연) 한다. 지연 import는
기교가 아니라 필요다: 이 모듈이 최상위에서 `l4`를 import하면 `l3` Core 모듈이 이 모듈을
import하는 순간 무거운 검증 스택이 통째로 끌려온다(그리고 import 시점 순환의 여지가 생긴다).

## 왜 "부르는 쪽이 인자로 받는" 순수 DI만 쓰지 않는가 (정직한 한계)

`verify_slot_payload(payload)`·`DirectAdapter().render(dsl, ctx)`처럼 **이미 공개 시그니처가
굳은 순수 함수·값 객체**가 호출부다. 어댑터를 필수 인자로 밀어 넣으면 4개 모듈·수십 개 호출부·
그 테스트가 전부 바뀌고, 그 변경은 이 태스크가 지켜야 할 "동작 변경이 아니라 호출 경로 변경"의
경계를 넘는다. 그래서 **선택 인자(명시 주입) + 미지정 시 이 좌석**의 조합을 쓴다 —
테스트·조립은 명시 주입으로 결정론을 유지하고, 기존 호출부는 시그니처가 그대로다.

이 좌석은 전역 상태이므로 **테스트가 바꾸면 반드시 되돌려야 한다**(`pytest-randomly`로 순서가
섞이므로 남은 전역은 다른 테스트를 깬다). 그래서 되돌림을 강제하는 컨텍스트 매니저
`use_subject_adapter()`를 함께 둔다 — 사람의 기억이 아니라 `finally`가 지킨다.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from whymath_backend.schema.subject_adapter import SubjectAdapter

__all__ = [
    "get_subject_adapter",
    "set_subject_adapter",
    "use_subject_adapter",
]

_adapter: SubjectAdapter | None = None
"""현재 조립된 과목 어댑터. None이면 아직 아무도 심지 않은 것(첫 호출에서 기본값 생성)."""


def _build_default_adapter() -> SubjectAdapter:
    """기본 과목 어댑터 생성 — **이 저장소에서 구현체를 아는 유일한 함수**.

    import를 함수 안에서 하는 이유는 모듈 docstring 참조(무거운 검증 스택 지연·순환 회피).
    과목을 바꾸려면 이 함수 또는 `set_subject_adapter` 호출부만 바꾸면 된다 — Core 코드는
    한 줄도 바뀌지 않는다(그것이 EOS 경계의 합격 기준이다).
    """
    from whymath_backend.l4.subject_adapter_math import MathSubjectAdapter

    return MathSubjectAdapter()


def set_subject_adapter(adapter: SubjectAdapter | None) -> None:
    """조립 지점에 어댑터를 심는다. `None`을 넣으면 기본값으로 되돌린다(다음 호출에서 재생성).

    프로덕션 호출부는 `app.create_app` 하나다. 테스트는 가급적 `use_subject_adapter()`를
    쓴다(되돌림 누락이 순서 의존 오염이 되는 것을 막는다).
    """
    global _adapter
    _adapter = adapter


def get_subject_adapter() -> SubjectAdapter:
    """현재 과목 어댑터를 반환한다 — 심어진 게 없으면 기본값을 1회 생성해 심는다.

    Core 호출부는 이 함수의 *반환 타입*(Protocol)만 알면 되고, 어떤 구현이 오는지는 모른다.
    """
    global _adapter
    if _adapter is None:
        _adapter = _build_default_adapter()
    return _adapter


@contextmanager
def use_subject_adapter(adapter: SubjectAdapter) -> Iterator[SubjectAdapter]:
    """지정 어댑터를 임시로 심고, 블록을 벗어나면 **반드시** 이전 상태로 되돌린다.

    전역 좌석을 건드리는 테스트의 표준 경로다. 예외로 빠져나가도 `finally`가 복원하므로,
    실패한 테스트가 뒤 테스트를 오염시키지 않는다(무작위 순서 실행 전제).
    """
    global _adapter
    previous = _adapter
    _adapter = adapter
    try:
        yield adapter
    finally:
        _adapter = previous
