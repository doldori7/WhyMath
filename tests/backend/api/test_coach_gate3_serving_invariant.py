"""S1 탈출 게이트 ③ 기계 봉인 — "학생 응답은 전부 PRM/도구 검증 통과 후"의 코드 경로 불변식.

정본: `docs/strategy/s1_exit_gate_judgement_2026-07.md` §게이트 ③.

게이트 ③의 **정직한 실체**(ARCH-08 후속 매핑): 서빙 경로는 학생에게 (i) 결정론 템플릿 텍스트
(`PolyaCoach.decide` → `STAGE_PROMPTS` 정적 dict·LLM 0 → PRM *N/A*·불변식 vacuous 성립) 또는
(ii) 도구-검증 게이팅 신호(`solution_coaching` = SymPy/`verify_solution`/`verify_step` verdict로
노출 게이팅)만 방출한다. **"학생 응답이 전부 PRM을 통과한다"는 오버클레임** — 올바른 주장은
*"학생-대면 자유 텍스트로 검증 안 된 LLM 출력이 방출되지 않는다"*이다.

본 파일은 그 불변식을 **구조상 성립 → CI 동결**로 승격한다(초인간 검증 서열: 기계 게이트 > 산문).
봉인 3종:
  1. `PolyaCoach.decide`가 반환하는 학생-대면 발화(`decision.prompt`)는 *항상* `STAGE_PROMPTS`의
     정적 템플릿 4종 중 하나다 — 학생 입력을 어떻게 바꿔도(단계·전이·좌절·답요구·마스터리 조합).
     학생 텍스트 보간·LLM 생성이 스며들면 즉시 red.
  2. 서빙 엔드포인트(`POST /v1/coach`·stateless·DB 무접근)를 실제로 태워, *응답에 실린* 발화가
     동일 정적 템플릿 집합에 속함을 end-to-end로 봉인(서빙 경로 전체가 결정론 발화만 방출).
  3. 서빙 경로 유일 LLM 콜(오개념 judge)·WH-1 하네스 shadow는 **기본 OFF**임을 동결 — 게이트 ③
     정직 프레이밍의 캐비엇 전제(누군가 기본값을 뒤집으면 "LLM 산문 미방출" 논거를 재검토해야
     하므로 이 테스트가 플래그한다).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from fastapi.testclient import TestClient
from pydantic import SecretStr

from whymath_backend.api._auth import get_consented_user
from whymath_backend.app import create_app
from whymath_backend.config import Settings, get_settings
from whymath_backend.db.models.user import UserProfile
from whymath_backend.db.session import get_session
from whymath_backend.l4 import MasteryLevel
from whymath_backend.l4.models import PolyaStage, PolyaState
from whymath_backend.l4.polya.engine import PolyaCoach
from whymath_backend.l4.polya.prompts import STAGE_PROMPTS
from whymath_backend.schema.enums import Persona
from whymath_backend.schema.user import UserProfile as UserProfileSchema

# 정적 템플릿 4종의 발화 집합 — 서빙이 방출할 수 있는 발화의 *유일한* 허용 집합.
_STATIC_PROMPTS: frozenset[str] = frozenset(sp.prompt for sp in STAGE_PROMPTS.values())

# 학생 입력 다양성 — 전이(next)·정지(stay)·좌절·답요구·풀이·후퇴 신호를 폭넓게 커버.
_STUDENT_INPUTS: tuple[str, ...] = (
    "",
    "음",
    "모르겠어요",
    "다시 설명해주세요",
    "그냥 답이 뭐예요?",
    "x = 2 라고 생각했어요",
    "이해했어요 다음으로",
    "(a+b)^2 까지 했어요",
    "잘 안 풀려요 5번째 시도예요",
)


def test_decide_utterance_is_always_static_template() -> None:
    """게이트 ③ 봉인 ① — `PolyaCoach.decide`의 발화는 언제나 정적 템플릿 4종 중 하나.

    단계 × 학생입력 × 마스터리 전수 스윕. 학생 텍스트가 발화에 보간되거나 LLM 생성이 끼면
    허용 집합을 벗어나 red — "결정론 방출·LLM 0" 불변식의 기계 동결.
    """
    coach = PolyaCoach()
    # MasteryLevel = Literal['초보', '발전 중', '숙달'] — Enum 아님(값 직접 사용).
    masteries: tuple[MasteryLevel | None, ...] = (None, "초보", "발전 중", "숙달")
    for stage in PolyaStage:
        for text in _STUDENT_INPUTS:
            for mastery in masteries:
                decision = coach.decide(
                    text,
                    PolyaState(current_stage=stage),
                    mastery_level=mastery,
                )
                assert decision.prompt in _STATIC_PROMPTS, (
                    f"서빙 발화가 정적 템플릿을 벗어남 — stage={stage} input={text!r} "
                    f"mastery={mastery}: {decision.prompt!r}"
                )


def _hermetic_client() -> TestClient:
    """`/v1/coach`(stateless) hermetic 클라이언트 — 인증 우회·DB 무접근(fake session)."""
    app = create_app()

    def _user() -> UserProfile:
        return UserProfile.from_schema(
            UserProfileSchema(
                user_id="00000000-0000-0000-0000-0000000000a1",
                persona_primary=Persona.A_일반고고3,
            )
        )

    def _settings() -> Settings:
        # 모든 레이트리밋 0(비활성)·서빙 경로 LLM 플래그는 기본값(OFF) 유지.
        return Settings(jwt_secret_key=SecretStr("test-secret-0123456789abcdef"))

    class _FakeSession:
        """stateless 경로는 DB를 안 만진다 — 접근 시 즉시 실패."""

        async def execute(self, stmt: Any) -> None:
            raise AssertionError("coach(stateless)는 DB 쿼리하지 않아야 한다.")

    async def _sess() -> AsyncIterator[_FakeSession]:
        yield _FakeSession()

    app.dependency_overrides[get_consented_user] = _user
    app.dependency_overrides[get_settings] = _settings
    app.dependency_overrides[get_session] = _sess
    return TestClient(app)


def test_served_utterance_is_static_template_end_to_end() -> None:
    """게이트 ③ 봉인 ② — 서빙 응답에 실린 발화가 정적 템플릿 집합에 속함(end-to-end).

    실제 `POST /v1/coach`를 태워 학생 입력을 바꿔도 응답 `decision.prompt`가 정적 템플릿만
    방출됨을 봉인 — 서빙 경로 전체(라우터·페이로드 조립 포함)가 결정론 발화만 낸다는 증명.
    """
    client = _hermetic_client()
    for text in _STUDENT_INPUTS:
        resp = client.post("/v1/coach", json={"student_input": text})
        assert resp.status_code == 200, (text, resp.text)
        prompt = resp.json()["decision"]["prompt"]
        assert (
            prompt in _STATIC_PROMPTS
        ), f"서빙 응답 발화가 정적 템플릿 이탈 — input={text!r}: {prompt!r}"


def test_serving_path_llm_flag_governance() -> None:
    """게이트 ③ 봉인 ③ — 서빙 경로 LLM 소비 플래그 기본값 거버넌스(기본값 조용한 변경 방지).

    게이트 ③의 "LLM 산문 미방출" 논거는 다음 전제에 기댄다: 오개념 judge(서빙 유일 LLM 콜·산문
    미방출·라벨 필터만)·WH-1 하네스 shadow(무영속·`None` 반환·비노출)는 **기본 OFF**.

    **WH-1 primary flip(S1-11)은 2026-07-20 GA로 기본 ON**으로 전환됐다 — 실기기 확인(코치 발화
    라이브)+in-process 측정(`scripts/demo/wh1_primary_probe.py` 3케이스 LLM 개입 실패 0·verdict
    정상)으로 canary 졸업(MEMORY 2026-07-20). 정직 프레이밍상 primary on은 LLM *산문 자유 방출*이
    아니라 **하네스 오케스트레이션 + 게이트된 발화**다: 발화는 verify 의무(§3.1)·정답 억제
    백스톱(§3.4·오답/미결정 턴은 결정론 소크라테스 템플릿으로만)·L4 톤필터를 통과한 것만 노출되고,
    LLM 실패·타임아웃 시 결정론 폴백. 즉 학생-대면 자유 산문은 여전히 억제된다(측정 실증: 발화가
    하네스 소크라테스 템플릿). 이 봉인은 이제 판정치를 *동결*한다 — 기본값이 다시 조용히 뒤집히면
    (judge/shadow가 켜지거나 primary가 꺼지면) red로 플래그한다.

    **프로즈 rephrase(S4-04)는 기본 OFF(canary)** — ON이어도 파생 템플릿의 정답-안전 게이트
    (등호·숫자·GT 유입 전면 차단·fail-closed=원 템플릿) 통과분만 문맥화 노출되는 계층이나,
    GA flip(기본 True)은 결함주입 측정(coach_prose_leak_eval exit 0)+실기기 확인 후 별도
    커밋으로만 한다(S1-11 canary→GA 선례). 그 전까지 이 봉인이 False를 동결한다.
    """
    settings = Settings(jwt_secret_key=SecretStr("test-secret-0123456789abcdef"))
    assert settings.misconception_judge_enabled is False
    assert settings.wh1_harness_shadow_enabled is False
    assert settings.wh1_primary_enabled is True  # 2026-07-20 GA (측정 통과·MEMORY 로그)
    assert settings.wh1_prose_rephrase_enabled is False  # S4-04 canary — GA는 측정+실기기 후
