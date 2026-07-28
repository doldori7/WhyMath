"""대화 암호화 프리플라이트 CLI — SEC-05 (hermetic).

이 테스트가 못 박는 핵심은 하나다: **왕복 성공은 암호화의 증거가 아니다.**
키가 없으면 코드는 평문 폴백으로 동작하고 왕복은 그대로 성공한다 — 왕복만 보는 검증은
"성공"을 보고하면서 미성년 평문을 흘린다. 그래서 판정은 *저장 표현*(암호문/평문 증가분)이
쥔다.

  ① 판정 규칙 — 평문이 늘면 FAIL(왕복이 성공해도).
  ② **변별력** — 같은 왕복 성공이라도 암호문이 늘면 PASS로 뒤집힌다.
  ③ 측정 실패를 통과로 위장하지 않는다.
  ④ via-api에서 평문이 늘면 범인을 *서버 프로세스*로 지목한다(2026-07-16 절반 성립 함정).
"""

from __future__ import annotations

from whymath_backend.ops.dialogue_encryption_preflight import (
    EncryptionCounts,
    PreflightReport,
    _judge,
)


def _counts(*, enc: int, plain: int) -> EncryptionCounts:
    return EncryptionCounts(
        content_encrypted=enc,
        content_plaintext=plain,
        image_uri_encrypted=0,
        image_uri_plaintext=0,
        analysis_encrypted=0,
        analysis_plaintext=0,
    )


def _report(
    *,
    mode: str = "direct",
    round_trip: bool,
    before: tuple[int, int],
    after: tuple[int, int],
) -> PreflightReport:
    report = PreflightReport(mode=mode, key_configured=True, round_trip_ok=round_trip)
    report.before = _counts(enc=before[0], plain=before[1])
    report.after = _counts(enc=after[0], plain=after[1])
    _judge(report)
    return report


class TestRoundTripAloneIsNotEvidence:
    def test_round_trip_ok_but_plaintext_grew_is_fail(self) -> None:
        """평문 폴백 상황 — 왕복은 성공하지만 암호화는 안 됐다. 통과시키면 안 된다."""
        report = _report(round_trip=True, before=(0, 0), after=(0, 1))
        assert not report.passed
        assert any("평문 저장이 늘었습니다" in f for f in report.failures)

    def test_round_trip_ok_and_ciphertext_grew_is_pass(self) -> None:
        """**변별력** — 같은 왕복 성공이라도 암호문이 늘면 판정이 PASS로 뒤집힌다.

        위 테스트가 "항상 FAIL"이라는 고장이 아님을 증명한다.
        """
        report = _report(round_trip=True, before=(0, 0), after=(1, 0))
        assert report.passed, report.failures


class TestJudgeRules:
    def test_round_trip_mismatch_is_fail(self) -> None:
        report = _report(round_trip=False, before=(0, 0), after=(1, 0))
        assert any("왕복 불일치" in f for f in report.failures)

    def test_no_ciphertext_growth_is_fail(self) -> None:
        """행이 안 생겼거나 암호화 비활성 — 조용히 통과시키지 않는다."""
        report = _report(round_trip=True, before=(3, 0), after=(3, 0))
        assert any("암호문이 늘지 않았습니다" in f for f in report.failures)

    def test_unmeasured_counts_are_not_a_pass(self) -> None:
        """측정 실패를 '정상'으로 바꾸지 않는다(ops/cost_probe 이중 회계와 같은 규칙)."""
        report = PreflightReport(mode="direct", key_configured=True, round_trip_ok=True)
        _judge(report)
        assert not report.passed
        assert any("측정하지 못했습니다" in f for f in report.failures)


class TestCulpritAttribution:
    def test_via_api_blames_server_process(self) -> None:
        """CLI에 키가 있어도 서버가 못 보면 평문이 는다 — 고칠 대상을 정확히 지목해야 한다."""
        report = _report(mode="via-api", round_trip=True, before=(0, 0), after=(0, 2))
        assert any("서버 프로세스" in f for f in report.failures)

    def test_direct_blames_current_process(self) -> None:
        report = _report(mode="direct", round_trip=True, before=(0, 0), after=(0, 1))
        assert any("이 프로세스" in f for f in report.failures)
