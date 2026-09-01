"""[EOS-64 ③] 골든 승격 경로 게이트 — 경로 밖 승격이 실제로 exit 1인가.

이 파일이 붙드는 것
------------------
③의 요구는 "정본 경로(워크리스트 검수 → 사람 판정 → review_status 백필 → Wilson 게이트)를
거친 승격만 허용하고, 경로 밖 승격은 exit 1"이다. 그러므로 여기서 확인해야 하는 것은
"통과 케이스가 통과한다"가 아니라 **경로의 각 단을 하나씩 빼면 실제로 거부되는가**다 —
성공 경로만 보는 테스트는 게이트가 사실 아무것도 안 막아도 초록이다(변별력 없는 검증 금지).

그래서 축마다 **음성 대조 1건**을 둔다: 큐에 없음 / 사람 판정 없음 / 사람이 반려함 / 코퍼스에
없음 / 백필을 안 거침(손각인) / 각인값이 approved가 아님. 그리고 **양성 대조**(전건 통과)를
함께 둬 무차별 거부가 아님을 보인다.

법정·검수 절차의 기계 대체 금지 축은 세 가지로 동결한다:
  ⓐ 사람 판정 없는 후보는 통과가 아니라 `no_human_verdict` 거부다(미측정≠정상).
  ⓑ 사람 판정을 우회하는 CLI 플래그가 **없다**(`--force`·`--skip-review` 류 부재).
  ⓒ 이 CLI는 쓰기 경로가 없다 — 입력 파일이 실행 후 바이트 불변이다.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from whymath_backend.harness.golden_promotion_gate import (
    HUMAN_REVIEW_NOTICE,
    evaluate_promotion,
    main,
    render_gate_report,
)

# 슬러그 200건짜리 배치 — Wilson 상한(기본 임계 0.02)을 통과할 만큼 큰 표본.
# 작은 배치가 통과 못 하는 것은 설계이므로(모듈 docstring), 양성 대조는 표본을 키워서 만든다.
_BATCH = tuple(f"wm-gen-a4-{i:04d}" for i in range(200))


def _eval(slugs: tuple[str, ...] = _BATCH, **overrides: object) -> object:
    """전건 통과 상태를 기본값으로 두고, 인자로 축 하나씩만 깨뜨린다."""
    kwargs: dict[str, object] = {
        "queue_slugs": set(slugs),
        "human_verdicts": {slug: "approved" for slug in slugs},
        "backfilled_slugs": set(slugs),
        "corpus_review_status": {slug: "approved" for slug in slugs},
    }
    kwargs.update(overrides)
    return evaluate_promotion(list(slugs), **kwargs)  # type: ignore[arg-type]


class TestPathEnforcement:
    """정본 경로 4단 — 각 단을 빼면 그 단의 사유로 거부된다."""

    def test_positive_control_full_path_is_approved(self) -> None:
        """양성 대조 — 4단 전건 충족 + 충분한 표본이면 승격 허용(무차별 거부가 아니다)."""
        report = _eval()
        assert report.off_path == []  # type: ignore[attr-defined]
        assert report.wilson_passed is True  # type: ignore[attr-defined]
        assert report.approved is True  # type: ignore[attr-defined]

    @pytest.mark.parametrize(
        ("override", "expected_reason"),
        [
            ({"queue_slugs": set()}, "not_in_review_queue"),
            ({"human_verdicts": {}}, "no_human_verdict"),
            ({"backfilled_slugs": set()}, "review_status_not_backfilled"),
            ({"corpus_review_status": {}}, "not_in_corpus"),
        ],
        ids=["큐_미등재", "사람판정_없음", "백필_미경유", "코퍼스_부재"],
    )
    def test_missing_stage_blocks_with_its_own_reason(
        self, override: dict[str, object], expected_reason: str
    ) -> None:
        """음성 대조 — 단 하나를 빼면 **그 단의 사유**로 전건 차단(뭉뚱그린 거부 금지)."""
        report = _eval(**override)
        assert len(report.off_path) == len(_BATCH)  # type: ignore[attr-defined]
        assert {v.blocked_reason for v in report.off_path} == {  # type: ignore[attr-defined]
            expected_reason
        }
        assert report.approved is False  # type: ignore[attr-defined]

    def test_hand_stamped_review_status_is_refused(self) -> None:
        """손각인 차단 — 코퍼스 값이 approved여도 백필 감사로그에 없으면 경로 밖이다.

        이 게이트의 존재 이유 그 자체다: 값만 보면 백필 CLI가 각인한 것과 사람이 JSONL을
        손으로 고친 것을 구분할 수 없고, `l6/_shared.is_review_cleared`는 그 둘을 똑같이
        통과시킨다.
        """
        report = _eval(backfilled_slugs=set(_BATCH[:1]))
        blocked = report.off_path  # type: ignore[attr-defined]
        assert {v.blocked_reason for v in blocked} == {"review_status_not_backfilled"}
        assert len(blocked) == len(_BATCH) - 1

    def test_pending_review_status_is_not_promotable(self) -> None:
        """각인값이 approved가 아니면 거부 — 판정 권위는 `is_review_status_cleared` 단일."""
        report = _eval(corpus_review_status={slug: "pending" for slug in _BATCH})
        assert {v.blocked_reason for v in report.off_path} == {  # type: ignore[attr-defined]
            "review_status_not_approved"
        }

    def test_human_rejected_candidate_is_never_promoted(self) -> None:
        """사람이 반려한 후보는 승격되지 않는다 — 기계가 그 판정을 뒤집지 않는다."""
        verdicts = {slug: "approved" for slug in _BATCH}
        verdicts[_BATCH[0]] = "rejected"
        report = _eval(human_verdicts=verdicts)
        assert [v.blocked_reason for v in report.off_path] == [  # type: ignore[attr-defined]
            "human_verdict_rejected"
        ]
        assert report.approved is False  # type: ignore[attr-defined]


class TestWilsonGate:
    """④단 — 결함율은 점추정이 아니라 **상한**으로 판정한다."""

    def test_small_clean_batch_cannot_prove_absence_of_defects(self) -> None:
        """무결점 5건은 통과 못 한다 — 작은 표본의 0/5를 '결함 0%'로 읽지 않는다(설계).

        하한을 썼다면 0/5가 0.0으로 나와 그대로 통과한다 — 이 단언이 방향 오류를 잡는다.
        """
        small = tuple(f"s-{i}" for i in range(5))
        report = _eval(small)
        assert report.off_path == []  # type: ignore[attr-defined]  # 경로 4단은 전건 통과
        assert report.defect_rate_upper == pytest.approx(0.3511, abs=1e-3)  # type: ignore[attr-defined]
        assert report.wilson_passed is False  # type: ignore[attr-defined]
        assert report.approved is False  # type: ignore[attr-defined]

    def test_defect_rate_denominator_is_human_reviewed_only(self) -> None:
        """분모는 *사람 검수를 받은* 제안뿐 — 미검수를 '결함 없음'으로 세지 않는다."""
        report = _eval(human_verdicts={_BATCH[0]: "approved"})
        assert report.reviewed == 1  # type: ignore[attr-defined]
        assert report.defects == 0  # type: ignore[attr-defined]

    def test_zero_reviewed_is_unmeasured_not_pass(self) -> None:
        """사람 판정 0건이면 결함율은 None(측정 불가) — 통과가 아니다."""
        report = _eval(human_verdicts={})
        assert report.defect_rate_upper is None  # type: ignore[attr-defined]
        assert report.wilson_passed is False  # type: ignore[attr-defined]


class TestReportRendering:
    """리포트가 이 게이트의 성격을 매번 명기한다(선언을 코드가 붙든다)."""

    def test_report_carries_human_review_notice_and_path(self) -> None:
        """법정·검수 절차의 기계 대체 금지 고지 + 정본 경로 4단이 산출물에 실린다."""
        rendered = render_gate_report(_eval())  # type: ignore[arg-type]
        assert HUMAN_REVIEW_NOTICE in rendered
        assert "법정·검수 절차의 기계 대체 금지" in HUMAN_REVIEW_NOTICE
        assert "① 워크리스트 검수 큐 등재" in rendered
        assert "④ Wilson 결함율 상한 게이트" in rendered

    def test_unmeasured_is_rendered_as_such(self) -> None:
        """분모 0은 '0.0000'이 아니라 '측정 불가'로 렌더된다 — 두 상태가 같은 글자면 위장이다."""
        rendered = render_gate_report(_eval(human_verdicts={}))  # type: ignore[arg-type]
        assert "측정 불가" in rendered


# ══════════════════════════════════════════════════════════════════════════
# CLI — exit 코드와 쓰기 경로 부재
# ══════════════════════════════════════════════════════════════════════════
def _fixture_files(tmp_path: Path, slugs: tuple[str, ...], *, stamped: bool = True) -> list[str]:
    """게이트 입력 4종(제안·검수 큐·검수 이벤트·코퍼스·백필 감사로그)을 실 형식으로 만든다."""
    proposal = tmp_path / "proposal.txt"
    proposal.write_text("# 승격 제안\n" + "\n".join(slugs) + "\n", encoding="utf-8")

    queue = tmp_path / "acc.review.jsonl"
    queue.write_text(
        "\n".join(
            json.dumps(
                {"status": "needs_review", "slug": slug, "reasons": [], "run_id": "run-1"},
                ensure_ascii=False,
            )
            for slug in slugs
        )
        + "\n",
        encoding="utf-8",
    )

    events = tmp_path / "review_timer.jsonl"
    events.write_text(
        "\n".join(
            json.dumps(
                {
                    "review_session_id": f"00000000-0000-4000-8000-{i:012d}",
                    "cu_slug": slug,
                    "reviewer_id": "kiki",
                    "event_type": "finished",
                    "verdict": "approved",
                },
                ensure_ascii=False,
            )
            for i, slug in enumerate(slugs)
        )
        + "\n",
        encoding="utf-8",
    )

    corpus = tmp_path / "acc.jsonl"
    corpus.write_text(
        "\n".join(
            json.dumps({"slug": slug, "review_status": "approved"}, ensure_ascii=False)
            for slug in slugs
        )
        + "\n",
        encoding="utf-8",
    )

    audit = tmp_path / "backfill_audit.jsonl"
    audit_slugs = slugs if stamped else ()
    audit.write_text(
        "".join(
            json.dumps({"slug": slug, "review_status": "approved"}, ensure_ascii=False) + "\n"
            for slug in audit_slugs
        ),
        encoding="utf-8",
    )

    return [
        "--proposal",
        str(proposal),
        "--review-queue",
        str(queue),
        "--review-events",
        str(events),
        "--corpus",
        str(corpus),
        "--backfill-audit",
        str(audit),
    ]


class TestCliExitCodes:
    def test_full_path_batch_exits_0(self, tmp_path: Path) -> None:
        """정본 경로 전건 + 충분 표본 → exit 0."""
        assert main(_fixture_files(tmp_path, _BATCH)) == 0

    def test_off_path_promotion_exits_1(self, tmp_path: Path) -> None:
        """경로 밖 승격(백필 미경유·손각인)은 exit 1 — ③의 핵심 계약."""
        assert main(_fixture_files(tmp_path, _BATCH, stamped=False)) == 1

    def test_missing_input_is_input_error_exit_2(self, tmp_path: Path) -> None:
        """입력 부재는 판정이 아니라 **입력 오류(exit 2)** — 판정 실패와 구분한다."""
        args = _fixture_files(tmp_path, _BATCH)
        (tmp_path / "acc.jsonl").unlink()
        assert main(args) == 2

    def test_empty_proposal_is_input_error_not_pass(self, tmp_path: Path) -> None:
        """제안 0건은 '전건 통과'가 아니다 — 판정할 대상이 없으면 exit 2."""
        args = _fixture_files(tmp_path, _BATCH)
        (tmp_path / "proposal.txt").write_text("# 주석뿐\n\n", encoding="utf-8")
        assert main(args) == 2

    def test_small_clean_batch_exits_1(self, tmp_path: Path) -> None:
        """무결점 5건 배치도 Wilson 상한 미달로 exit 1(설계 — 작은 표본은 증명이 아니다)."""
        assert main(_fixture_files(tmp_path, tuple(f"s-{i}" for i in range(5)))) == 1


class TestNoMachineSubstitutionForHumanReview:
    """법정·검수 절차의 기계 대체 금지 — 구조로 확인한다(산문 선언만으로는 부족)."""

    def test_cli_has_no_human_review_bypass_flag(self, tmp_path: Path) -> None:
        """ⓑ 사람 판정을 끄는 플래그가 없다 — 있으면 인자 파싱이 성공해 SystemExit 2가 안 난다."""
        base = _fixture_files(tmp_path, _BATCH)
        for flag in ("--force", "--skip-review", "--no-human-verdict", "--assume-approved"):
            with pytest.raises(SystemExit) as excinfo:
                main([*base, flag])
            assert excinfo.value.code == 2  # argparse 인자 오류 — 그런 우회 인자는 존재하지 않는다

    def test_gate_never_writes_to_its_inputs(self, tmp_path: Path) -> None:
        """ⓒ 쓰기 경로 없음 — 실행 후 입력 5종이 **바이트 불변**이다(승격 집행은 사람 몫)."""
        args = _fixture_files(tmp_path, _BATCH)
        inputs = sorted(tmp_path.iterdir())
        before = {path.name: path.read_bytes() for path in inputs}
        assert main(args) == 0
        after = {path.name: path.read_bytes() for path in sorted(tmp_path.iterdir())}
        assert after == before  # 새 파일도 없고(--json 미지정) 기존 파일도 안 고친다

    def test_started_event_alone_is_not_a_human_verdict(self, tmp_path: Path) -> None:
        """ⓐ 검수 *착수*는 판정이 아니다 — started만 있는 후보는 거부된다(미측정≠승인)."""
        args = _fixture_files(tmp_path, _BATCH)
        events = tmp_path / "review_timer.jsonl"
        events.write_text(
            "\n".join(
                json.dumps(
                    {
                        "review_session_id": f"00000000-0000-4000-8000-{i:012d}",
                        "cu_slug": slug,
                        "reviewer_id": "kiki",
                        "event_type": "started",
                    },
                    ensure_ascii=False,
                )
                for i, slug in enumerate(_BATCH)
            )
            + "\n",
            encoding="utf-8",
        )
        assert main(args) == 1
