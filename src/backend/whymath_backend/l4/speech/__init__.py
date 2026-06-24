"""L4 수식 음성화 — 사전·프로파일(L4 데이터)을 L3 변환 엔진에 주입하는 배선.

7계층 방향: L4→L3 forward 호출(합법). L3 엔진(`l3/speech.py`)은 L4를 import하지 않고 사전·
프로파일을 인자로 받으며(역방향 의존 회피), 이 모듈이 그 주입을 한다 — `api/visualization.py`(L5)가
L4 자산을 조합해 L3에 넘기는 선례의 L4판. 단일 진입점 `speak_latex`를 L5(api)·테스트가 소비한다.
"""

from __future__ import annotations

from whymath_backend.l3.speech import generate_speech_spec
from whymath_backend.l4.speech.profiles import PROFILES
from whymath_backend.l4.speech.symbols import FUNC_KO, LATIN_KO, TOKEN_KO
from whymath_backend.schema.speech import SpeechGradeBand, SpeechSpec

__all__ = ["PROFILES", "speak_latex"]


def speak_latex(latex: str, grade_band: SpeechGradeBand | str = SpeechGradeBand.고등) -> SpeechSpec:
    """단일 수식 LaTeX를 학년 밴드에 맞춰 한국어 낭독 명세로 변환한다(L4 사전·프로파일 주입).

    기본 밴드는 고등(MVP 페르소나 A 고3). 알 수 없는 밴드는 `SpeechGradeBand`가 ValueError.
    """
    band = SpeechGradeBand(grade_band)
    return generate_speech_spec(
        latex,
        band,
        profile=PROFILES[band],
        token_ko=TOKEN_KO,
        func_ko=FUNC_KO,
        latin_ko=LATIN_KO,
    )
