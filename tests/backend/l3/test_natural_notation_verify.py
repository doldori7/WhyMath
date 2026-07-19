"""S3-06 자연 표기 verify 안전 확장 — 실사용 제출 재현 픽스처·acceptance 동결(hermetic).

2026-07-19 자연 사용 재측정(n=6·100% unverifiable)의 실제 제출을 *원문 그대로*(캐럿 없는 지수
`x2`·유니코드 마이너스 U+2212) 재현해 다음을 동결한다:
  ① 연쇄 등식 `a=b=c` — 내부 인접쌍 동치 위반은 incorrect(진짜 오류 검출)·전부 참이면 최종
     바인딩 단일 등식으로 정규화(`x=(1+3)/2=2` → `x=2`).
  ② 근 나열/선언(`x=2, x=3`·`또는`) — 같은 변수 해집합 union → `(x-2)(x-3)=0` 전이가 correct.
  ③ 유니코드 부호(−·×·÷) 정규화 경유 판정.
  ④ **거짓 incorrect 함정 방어(최상위 제약)** — 항등식(ℝ)→값 선언 등 이질 형태 전이는
     unverifiable 유지(해집합 비교 금지). 캐럿 없는 지수(`x2`)는 재작성 보류·해집합 경로에서
     판정 불가(unverifiable 유지가 정직 — `x2`를 미지수로 풀면 거짓 incorrect).
"""

from __future__ import annotations

from whymath_backend.l3.verify_solution import verify_solution
from whymath_backend.l3.verify_step import VerifyStepState, verify_step

# Kiki 실제 제출 원문(2026-07-19 자연 사용 재측정) — 문제: "이차함수 x^2-4x+3 그래프의 축 x=a".
# step1: 캐럿 없는 지수 `x2`(Symbol로 파싱됨) + 유니코드 마이너스 U+2212(−).
# step2: 연쇄 등식 a=b=c(축 공식 파생 — 해집합 보존 변형이 *아님*).
KIKI_STEP1 = "x2−4x+3=(x−1)(x−3)"
KIKI_STEP2 = "x=(1+3)/2=2"
# 위첨자 정상 표기 변형 — step1이 항등식(모든 실수 ℝ)으로 *판정 가능*해지는 케이스(함정 재현).
KIKI_STEP1_SUPERSCRIPT = "x²−4x+3=(x−1)(x−3)"


class TestKikiSubmissionFixture:
    """실제 제출 재현 — 거짓 incorrect 0 (acceptance ①)."""

    def test_verbatim_submission_no_false_incorrect(self) -> None:
        # 원문 그대로(U+2212·x2): step1은 x2 심볼 탓에 판정 불가 → 전이는 unverifiable(정직).
        # 어떤 경우에도 incorrect(거짓 판정)가 아니어야 한다 — step2 내부는 전부 참이므로.
        result = verify_step(KIKI_STEP1, KIKI_STEP2)
        assert result.state == VerifyStepState.unverifiable
        assert result.state != VerifyStepState.incorrect

    def test_verbatim_submission_aggregate_zero_incorrect(self) -> None:
        # verify_solution 집계 수준에서도 거짓 incorrect 0 동결.
        aggregate = verify_solution([KIKI_STEP1, KIKI_STEP2])
        assert aggregate.n_incorrect == 0
        assert aggregate.has_incorrect is False
        assert aggregate.n_transitions == 1

    def test_superscript_variant_identity_to_binding_is_not_incorrect(self) -> None:
        # 함정 핵심(태스크 설계): step1이 위첨자 정상 표기면 항등식(ℝ)으로 판정된다. step2 정규화
        # `x=2`({2})와 해집합이 "다르지만" 축 공식 파생은 옳은 풀이 — 이질 형태(항등 재작성 ↔ 값
        # 선언) 전이는 해집합 비교 금지 → unverifiable 유지(S3-02에서는 거짓 incorrect였음).
        result = verify_step(KIKI_STEP1_SUPERSCRIPT, KIKI_STEP2)
        assert result.state == VerifyStepState.unverifiable
        assert result.evidence_weight == 0.5

    def test_superscript_variant_to_plain_binding_is_not_incorrect(self) -> None:
        # 연쇄 없이 값 선언만 있어도 동일 — 항등식(ℝ) → x=2({2})는 unverifiable(거짓 incorrect 0).
        result = verify_step(KIKI_STEP1_SUPERSCRIPT, "x=2")
        assert result.state == VerifyStepState.unverifiable


class TestChainInternalViolation:
    """연쇄 등식 내부 위반 — 인접쌍 거짓 *증명*은 단계 자체의 오류 → incorrect (acceptance ②)."""

    def test_internal_violation_is_incorrect(self) -> None:
        # x=(1+3)/2=3 : (1+3)/2 ≠ 3 이 수치로 증명됨 → 전이 비교와 무관하게 incorrect.
        result = verify_step(KIKI_STEP1, "x=(1+3)/2=3")
        assert result.state == VerifyStepState.incorrect
        assert result.evidence_weight == 1.0
        assert result.reason is not None
        assert "연쇄 등식 내부" in result.reason

    def test_internal_violation_on_before_side_is_incorrect(self) -> None:
        # before 쪽 체인 위반도 단계의 거짓 증명 — incorrect(표준형 검증 primitive로서 대칭).
        result = verify_step("x=(1+3)/2=3", "x=3")
        assert result.state == VerifyStepState.incorrect

    def test_violation_reason_echoes_submitted_fragments_only(self) -> None:
        # reason은 학생 제출 원문 조각만 반향한다(정답 미조회·미누출).
        result = verify_step(KIKI_STEP1, "x=(1+3)/2=3")
        assert result.reason is not None
        assert "(1+3)/2" in result.reason
        assert "3" in result.reason

    def test_chain_all_true_normalizes_to_final_binding(self) -> None:
        # 내부 전부 참이면 최종 바인딩(x=2)으로 정규화 → 해집합 보존 전이가 correct로 결정된다.
        result = verify_step("2x=4", "x=(2+2)/2=2")
        assert result.state == VerifyStepState.correct
        assert result.evidence_weight == 1.0

    def test_chain_with_two_bindings_is_unverifiable(self) -> None:
        # 판정 불가 쌍 2+(x=y=2 — 바인딩이 둘) → 체인 결속 미증명 → unverifiable(정직).
        result = verify_step("x=2", "x=y=2")
        assert result.state == VerifyStepState.unverifiable


class TestRootsEnumeration:
    """근 나열/선언 — 같은 변수 해집합 union (acceptance ③·수능 wedge 핵심 전이)."""

    def test_factored_to_roots_is_correct(self) -> None:
        # (x-2)(x-3)=0 → x=2, x=3 : 해집합 {2,3} 보존 → correct(이차방정식 자연 풀이 마지막 전이).
        result = verify_step("(x-2)*(x-3)=0", "x=2, x=3")
        assert result.state == VerifyStepState.correct
        assert result.evidence_weight == 1.0

    def test_factored_to_wrong_roots_is_incorrect(self) -> None:
        # (x-2)(x-3)=0 → x=2, x=4 : {2,3} vs {2,4}(해집합 변화) → incorrect.
        result = verify_step("(x-2)*(x-3)=0", "x=2, x=4")
        assert result.state == VerifyStepState.incorrect
        assert result.reason is not None
        assert "해집합 비보존" in result.reason

    def test_korean_or_separator_is_correct(self) -> None:
        # "또는" 구분자 + 유니코드 마이너스(U+2212) 혼용도 동일 판정.
        result = verify_step("(x−2)(x−3)=0", "x=2 또는 x=3")
        assert result.state == VerifyStepState.correct

    def test_duplicate_root_declaration_matches_double_root(self) -> None:
        # 중근: (x-2)^2=0 → x=2, x=2 : union {2} = {2} → correct(중복 선언 흡수).
        result = verify_step("(x-2)^2=0", "x=2, x=2")
        assert result.state == VerifyStepState.correct

    def test_different_variables_not_unioned(self) -> None:
        # x=2, y=3 은 연립(AND·동시 성립)이지 근 나열(OR)이 아니다 — union 오해석 금지 →
        # unverifiable(거짓 correct/incorrect 회피).
        result = verify_step("(x-2)*(x-3)=0", "x=2, y=3")
        assert result.state == VerifyStepState.unverifiable

    def test_sequence_notation_not_unioned(self) -> None:
        # 수열 항 개별 선언(a1=2, a2=3 — AND)을 근 나열(OR)로 오해석 금지 → unverifiable(정직).
        result = verify_step("(x-2)*(x-3)=0", "a1=2, a2=3")
        assert result.state == VerifyStepState.unverifiable


class TestCaretlessExponentHonesty:
    """캐럿 없는 지수(`x2`) — 재작성 휴리스틱 보류(S3-06 ④)·unverifiable 유지가 정직."""

    def test_caretless_exponent_equation_is_unverifiable_not_incorrect(self) -> None:
        # x2=4 → x=2 : `x2`를 미지수로 *풀면* {4} vs {2}로 거짓 incorrect가 난다(2026-07-19 실측
        # — S3-02 잠복 결함). 학생 의도(x²=4)와 수열 항 표기가 구분 불가하므로 해집합 경로는
        # 판정 불가로 보수 회피한다(정직).
        result = verify_step("x2=4", "x=2")
        assert result.state == VerifyStepState.unverifiable
        assert result.state != VerifyStepState.incorrect

    def test_kiki_step1_caretless_stays_unverifiable(self) -> None:
        # Kiki step1 원문 단독 전이 — x2 심볼 혼입 등식은 해집합 판정 불가 → unverifiable 유지.
        result = verify_step(KIKI_STEP1, "x=2")
        assert result.state == VerifyStepState.unverifiable


class TestUnicodeOperatorNormalization:
    """유니코드 부호(−·×·÷) 정규화 경유 판정 — 실측: `to_sympy_source`가 이미 처리(동결)."""

    def test_unicode_minus_equation_transform_correct(self) -> None:
        # U+2212 마이너스 등식 변형 — 2x−3=7 → 2x=10 : 둘 다 {5} → correct.
        result = verify_step("2x−3=7", "2x=10")
        assert result.state == VerifyStepState.correct

    def test_unicode_multiplication_division_correct(self) -> None:
        # U+00D7(×)·U+00F7(÷) — 2×x=6 → x=6÷2 : 둘 다 {3} → correct.
        result = verify_step("2×x=6", "x=6÷2")
        assert result.state == VerifyStepState.correct


class TestRegressionSingleEquationPath:
    """기존 단일 등식 경로(S3-02) 회귀 방지 — 동질 형태(유한↔유한) 비교는 그대로 유지."""

    def test_equation_transform_still_correct(self) -> None:
        result = verify_step("2x+3=7", "2x=4")
        assert result.state == VerifyStepState.correct

    def test_changed_solution_still_incorrect(self) -> None:
        result = verify_step("2x=6", "2x=8")
        assert result.state == VerifyStepState.incorrect

    def test_root_loss_still_incorrect(self) -> None:
        # 유한↔유한 근 유실({−2,2}→{2})은 여전히 incorrect — S3-02 해집합 보존 검출 유지.
        # (이질 형태 가드는 ℝ↔유한 만 보수 처리한다 — 동질 비교의 검출력은 후퇴하지 않음.)
        result = verify_step("x²=4", "x=2")
        assert result.state == VerifyStepState.incorrect

    def test_identity_rewriting_both_sides_still_correct(self) -> None:
        # ℝ↔ℝ(둘 다 항등 재작성)은 여전히 correct — 이질 형태 가드가 동질 ℝ 비교를 막지 않음.
        result = verify_step("(x+1)^2=x^2+2*x+1", "x^2+2*x+1=(x+1)^2")
        assert result.state == VerifyStepState.correct
