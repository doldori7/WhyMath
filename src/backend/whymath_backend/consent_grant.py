"""법정대리인 신원 확인 SEAM (Protocol + STUB) — 14세 미만 동의 GRANT의 *검증 경계*.

PIPA 만14세 미만 법정대리인 동의(docs/legal/pipa_data_matrix.md §3)는 동의를 *받기* 전에
법정대리인의 *본인 확인*을 요구한다(§3.2 절차 2단계). 그러나 **본인 확인 *방식*(휴대폰
본인인증·카드·아이핀 등 중 무엇이 법적으로 적정한가)은 변호사 자문 필수**(§3.1·§3.2·§5
체크리스트)라 *지금 구현하지 않는다*. 이 모듈은 그 미래의 실 구현을 끼울 *seam*만 만든다 —
`GuardianVerifier` Protocol(경계)과 `StubGuardianVerifier`(진짜 검증을 *하지 않는* 구현).

**왜 stub인가(정직한 경계)**: `consent.py`가 연나이를 *보수적으로* 파생하고 정확한 만나이
게이팅을 변호사 자문 후속으로 미룬 것과 같은 정신이다. 가짜로 "본인 확인됨"을 만들지 않는다 —
stub은 *법적으로 유의미한 검증을 수행하지 않았음*을 결과(method="stub")로 *명시*하고, 동의
레코드는 "어떤 방식으로 검증했는가"를 감사 가능하게 남길 뿐(`db/models/parental_consent.py`)
그 방식의 법적 충분성을 단정하지 않는다. 실 본인확인(휴대폰 인증 등)은 이 Protocol을 구현한
새 클래스를 만들어 끼우면 되고(아래 "실 구현이 끼는 자리"), *그 자리만* 바꾸면 동의-기록
엔드포인트·테이블·게이트는 불변이다.

**법정대리인 *인증* 모델(별도·후속)**: "법정대리인이 *어떻게* 이 동의 화면에 접근/로그인하는가"
(자녀 계정으로? 별도 보호자 계정으로? 일회용 링크로?)는 본인 확인 *방식*과는 또 다른 문제이며
역시 변호사 자문·제품 설계 후속이다(pipa_data_matrix.md §3.4). 현재 동의-기록 엔드포인트는
*동의 대상 학생으로 인증된 세션*에서 호출되며, 보호자 인증 모델 도입 시 그 부분이 교체된다.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field


class GuardianVerificationRequest(BaseModel):
    """법정대리인 신원 확인 입력 — verifier에 넘기는 신호(미성년 PII 평문 미포함).

    `guardian_email`은 *식별·통지*용이며 검증 후 평문으로 저장하지 않는다(해시만 — 호출 측이
    `email_hash`로 변환해 레코드에 담는다). 실 본인확인 구현은 여기에 본인확인 토큰·거래 id 등
    *방식별 입력*을 확장 필드로 받게 되나, **그 입력 형식은 변호사 자문으로 방식이 확정된 뒤**
    정한다(지금 추측 필드를 박지 않는다). stub은 이 입력의 형식만 검증하고 신원은 검증하지 않는다.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    guardian_email: str = Field(
        description="법정대리인 이메일(식별·통지용 — 평문 미저장·호출 측이 해시로 변환)."
    )


class VerificationResult(BaseModel):
    """신원 확인 SEAM의 결과 — *어떤 방식으로* 검증했고 통과했는가.

    `verified`: 동의 진행 가능 여부. `method`: 검증 방식 이름(레코드의 verification_method가 됨).
    `reference`: 외부 거래의 *불투명 참조*(PII 아님·없으면 None). **법적 경계**: stub은
    `method="stub"`·`reference=None`을 돌려주며, `verified=True`라도 그것은 *법적으로 유의미한
    본인 확인이 아니라* "검증 seam이 통과를 반환했다"는 기술적 사실일 뿐이다(stub docstring).
    """

    model_config = ConfigDict(extra="forbid")

    verified: bool = Field(description="동의 진행 가능 여부(seam 통과).")
    method: str = Field(
        max_length=32,
        description="검증 방식 이름(verification_method로 기록 — 예: 'stub').",
    )
    reference: str | None = Field(
        default=None,
        max_length=255,
        description="외부 검증 거래의 불투명 참조(PII 아님). stub은 None.",
    )


@runtime_checkable
class GuardianVerifier(Protocol):
    """법정대리인 신원 확인 경계 — 동의 진행 전 보호자 신원을 검증(또는 stub).

    동의-기록 엔드포인트(`api/users.py`)가 이 Protocol에 *주입된 구현*을 호출한다. 단위
    테스트는 가짜 구현을 주입(`app.dependency_overrides`)해 라이브 본인확인 없이 엔드포인트
    로직을 검증한다(OAuthProvider seam과 동형).

    **실 구현이 끼는 자리**: 휴대폰 본인인증·카드 등 *법적으로 적정한* 본인 확인 방식이 변호사
    자문으로 확정되면, 이 Protocol을 구현한 클래스(예: `PhoneAuthGuardianVerifier`)를 만들어
    `_default_guardian_verifier` 대신 주입하면 된다 — 엔드포인트·테이블·게이트는 불변이다.
    """

    def verify(self, request: GuardianVerificationRequest) -> VerificationResult:
        """법정대리인 신원을 검증해 결과 반환(통과/실패·방식·참조)."""
        ...


class StubGuardianVerifier:
    """**진짜 본인 확인을 하지 않는** 좌석 구현 — `method="stub"`만 기록(법적 경계).

    ⚠️ **이것은 법적으로 유의미한 법정대리인 본인 확인이 아니다.** 실제 본인 확인 방식(휴대폰
    본인인증·카드 등)의 법적 적정성은 **변호사 자문 필수**(pipa_data_matrix.md §3.1/§3.2/§5)라
    *아직 구현하지 않았다*. 이 stub은 입력 형식만 보고 `verified=True`를 돌려주되, 그 통과를
    *법적 검증으로 위장하지 않는다* — 결과의 `method="stub"`·`reference=None`이 "검증 seam이
    아직 stub임"을 *명시적으로* 남긴다(동의 레코드의 verification_method에 그대로 기록되어
    감사 시 어떤 동의가 stub으로 받아졌는지 식별 가능). 진짜 검증은 GuardianVerifier를 구현한
    새 클래스로 교체한다(GuardianVerifier docstring "실 구현이 끼는 자리").

    조용한 가짜 성공을 피하기 위해 입력의 *최소 형식*(이메일 비어있지 않음)만 확인한다 — 빈
    이메일은 `verified=False`(통지 대상조차 없음). 이는 신원 검증이 아니라 *입력 위생*이다.
    """

    METHOD = "stub"

    def verify(self, request: GuardianVerificationRequest) -> VerificationResult:
        """입력 형식만 확인하고 통과를 반환(신원 미검증·method='stub'으로 명시)."""
        # 빈 이메일이면 통지 대상조차 없으므로 미통과(입력 위생 — 신원 검증 아님).
        ok = bool(request.guardian_email.strip())
        return VerificationResult(verified=ok, method=self.METHOD, reference=None)


def _default_guardian_verifier() -> GuardianVerifier:
    """기본 verifier — 현재는 StubGuardianVerifier(실 본인확인은 변호사 자문 후속).

    FastAPI 의존성(`api/users.py`)이 이 함수를 `Depends`로 쓰고, 테스트·미래 실 구현은
    `app.dependency_overrides`로 교체한다(get_consented_user·get_session 오버라이드와 동형).
    """
    return StubGuardianVerifier()


__all__ = [
    "GuardianVerificationRequest",
    "VerificationResult",
    "GuardianVerifier",
    "StubGuardianVerifier",
    "_default_guardian_verifier",
]
