"""골든 벤치마크 승격·동결 규약 — as-found fail-closed·회전·digest (EOS-60 acceptance ①③⑥).

정본: `harness/golden_benchmark.py`. 검증 축:
  - **as-found 무결성(⑥·fail-closed)** — rejected는 승격, approved는 ⓐ 스냅샷/ⓑ edit-aware
    verdict 없이는 **제외**. 제외분 건수가 리포트에 명시되는지까지 실측(조용한 포함 금지).
  - ⓑ 경로의 **시각 경계** — 어휘가 있어도 `--edit-aware-since` 없으면 승격 불가,
    경계 이전 검수분도 승격 불가(소급 재분류 금지·EOS-62 ④).
  - **회전(③)** — 같은 rotation 바이트 재현·다른 rotation 선택 재배열(변별력 양방향).
  - **동결(③)** — digest는 내용의 함수이며 손편집 변조는 로드 시 터진다.
  - **재채점 금지 원장** — 같은 digest·다른 리비전만 위반(같은 리비전 재실행은 허용).
  - **앵커 id 정합** — `scripts/analysis/eos_anchor_asset_audit.ANCHOR_DEFS`와 기계 대조.
  - **CLI exit** — 승격 0건·입력 부재·파싱 실패 혼입은 전부 exit 1(통과 아님).

hermetic — tmp_path·픽스처만(파일 I/O 외 부작용 0·LLM/DB/네트워크 0).
"""

from __future__ import annotations

import importlib.util
import json
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from whymath_backend.harness.golden_benchmark import (
    ANCHOR_IDS,
    AnchorRow,
    AsFoundBasis,
    AsFoundRow,
    EvaluationRecord,
    GoldenItem,
    GoldenLabel,
    append_evaluation_ledger,
    compute_digest,
    edit_aware_verdict_available,
    find_rescore_violation,
    freeze_golden_set,
    load_evaluation_ledger,
    load_golden_set,
    main,
    parse_anchor_rows,
    parse_as_found_rows,
    promote_from_events,
    render_promotion_report,
    select_by_anchor,
    write_golden_set,
)
from whymath_backend.harness.review_timer import (
    append_event_jsonl,
    finish_review,
    start_review,
)
from whymath_backend.schema.enums import GenerationFailureCode
from whymath_backend.schema.review_timer import ReviewTimerEvent

_T0 = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)


def _finish(
    cu_slug: str,
    verdict: str,
    *,
    failure_code: GenerationFailureCode | None = None,
    at: datetime | None = None,
) -> ReviewTimerEvent:
    """종결 이벤트 1건 — 실 writer(`finish_review`)를 쓴다(계약 위반은 여기서 터진다)."""
    return finish_review(
        review_session_id=uuid.uuid4(),
        cu_slug=cu_slug,
        reviewer_id="kiki",
        verdict=verdict,  # type: ignore[arg-type]
        elapsed_ms=120_000,
        failure_code=failure_code,
        occurred_at=at or _T0,
    )


def _anchors(*pairs: tuple[str, str]) -> list[AnchorRow]:
    return [AnchorRow(cu_slug=slug, anchor_id=anchor) for slug, anchor in pairs]


# ──────────────────────────────────────────────────────────────────────────
# ⑥ as-found 라벨 무결성 — fail-closed
# ──────────────────────────────────────────────────────────────────────────
class TestAsFoundIntegrity:
    """승격 경로 3종과 그 부재 시 제외 — 골든의 존재 이유(FN 과소평가 방지)를 지킨다."""

    def test_rejected_promotes_as_defective_with_failure_code(self) -> None:
        events = [_finish("cu-a", "rejected", failure_code=GenerationFailureCode.F2)]
        report = promote_from_events(events, anchor_rows=_anchors(("cu-a", "A4")))

        assert report.promoted_count == 1
        item = report.promoted[0]
        assert item.label == GoldenLabel.DEFECTIVE
        assert item.failure_code == GenerationFailureCode.F2
        assert item.as_found_basis == AsFoundBasis.REJECTED_FAILURE_CODE
        assert item.anchor_id == "A4"
        assert report.excluded_ambiguous_approved == 0

    def test_approved_is_excluded_without_snapshot_or_edit_aware_verdict(self) -> None:
        """손질 후 승인이 clean으로 섞이면 FN율이 과소평가된다 — 그래서 기본 제외다."""
        events = [_finish("cu-b", "approved")]
        report = promote_from_events(events, anchor_rows=_anchors(("cu-b", "A4")))

        assert report.promoted_count == 0
        assert report.excluded_ambiguous_approved == 1

    def test_ambiguous_exclusion_is_stated_in_report(self) -> None:
        """제외는 조용히 하지 않는다 — 건수가 리포트 본문에 찍혀야 미측정이 보인다."""
        events = [_finish("cu-b", "approved"), _finish("cu-c", "approved")]
        report = promote_from_events(events, anchor_rows=_anchors(("cu-b", "A4"), ("cu-c", "A4")))

        rendered = render_promotion_report(report)
        assert "모호 승인" in rendered
        assert "2건" in rendered

    def test_pre_review_snapshot_unlocks_approved_promotion(self) -> None:
        """ⓐ 검수 전 스냅샷이 있으면 그 라벨이 정답지다(clean·defective 양쪽)."""
        events = [_finish("cu-b", "approved"), _finish("cu-c", "approved")]
        as_found = [
            AsFoundRow(cu_slug="cu-b", label=GoldenLabel.CLEAN),
            AsFoundRow(
                cu_slug="cu-c",
                label=GoldenLabel.DEFECTIVE,
                failure_code=GenerationFailureCode.F3,
            ),
        ]
        report = promote_from_events(
            events,
            anchor_rows=_anchors(("cu-b", "A4"), ("cu-c", "A5")),
            as_found_rows=as_found,
        )

        by_slug = {item.cu_slug: item for item in report.promoted}
        assert by_slug["cu-b"].label == GoldenLabel.CLEAN
        assert by_slug["cu-b"].failure_code is None
        assert by_slug["cu-c"].label == GoldenLabel.DEFECTIVE
        assert by_slug["cu-c"].failure_code == GenerationFailureCode.F3
        assert all(i.as_found_basis == AsFoundBasis.PRE_REVIEW_SNAPSHOT for i in report.promoted)
        assert report.excluded_ambiguous_approved == 0

    def test_edit_aware_since_alone_does_not_unlock_when_vocabulary_absent(self) -> None:
        """ⓑ는 어휘 실측에 걸린다 — EOS-62 미착지 상태에서 시각만 주면 여전히 제외."""
        if edit_aware_verdict_available():  # pragma: no cover - EOS-62 착지 후 경로
            pytest.skip("EOS-62 착지 — 이 케이스는 어휘 부재 상태의 계약이다")
        events = [_finish("cu-b", "approved")]
        report = promote_from_events(
            events,
            anchor_rows=_anchors(("cu-b", "A4")),
            edit_aware_since=_T0 - timedelta(days=1),
        )

        assert report.promoted_count == 0
        assert report.excluded_ambiguous_approved == 1
        assert report.edit_aware_available is False

    def test_edit_aware_path_requires_explicit_since_boundary(self, monkeypatch) -> None:
        """어휘가 있어도 경계 시각이 없으면 전부 제외 — 과거 approved의 조용한 혼입 차단."""
        monkeypatch.setattr(
            "whymath_backend.harness.golden_benchmark.edit_aware_verdict_available",
            lambda: True,
        )
        events = [_finish("cu-b", "approved")]
        report = promote_from_events(events, anchor_rows=_anchors(("cu-b", "A4")))

        assert report.promoted_count == 0
        assert report.excluded_ambiguous_approved == 1

    def test_edit_aware_path_excludes_reviews_before_boundary(self, monkeypatch) -> None:
        """소급 재분류 금지(EOS-62 ④) — 계약 착지 *이전* 검수분은 어휘가 있어도 영구 모호."""
        monkeypatch.setattr(
            "whymath_backend.harness.golden_benchmark.edit_aware_verdict_available",
            lambda: True,
        )
        boundary = _T0
        events = [
            _finish("cu-old", "approved", at=boundary - timedelta(days=1)),
            _finish("cu-new", "approved", at=boundary + timedelta(days=1)),
        ]
        report = promote_from_events(
            events,
            anchor_rows=_anchors(("cu-old", "A4"), ("cu-new", "A4")),
            edit_aware_since=boundary,
        )

        assert [i.cu_slug for i in report.promoted] == ["cu-new"]
        assert report.promoted[0].label == GoldenLabel.CLEAN
        assert report.promoted[0].as_found_basis == AsFoundBasis.EDIT_AWARE_VERDICT
        assert report.excluded_ambiguous_approved == 1

    def test_unmapped_anchor_is_excluded_not_silently_bucketed(self) -> None:
        """앵커 미매핑은 승격 불가 — 앵커별 쿼터·앵커별 FN 보고가 성립하지 않기 때문."""
        events = [_finish("cu-x", "rejected", failure_code=GenerationFailureCode.F1)]
        report = promote_from_events(events, anchor_rows=[])

        assert report.promoted_count == 0
        assert report.excluded_unmapped_anchor == 1

    def test_only_finished_events_become_labels(self) -> None:
        """started/aborted는 판정이 없다 — 라벨이 되지 못하고 분모도 오염시키지 않는다."""
        started = start_review(cu_slug="cu-a", reviewer_id="kiki")
        finished = _finish("cu-a", "rejected", failure_code=GenerationFailureCode.F1)
        report = promote_from_events([started, finished], anchor_rows=_anchors(("cu-a", "A4")))

        assert report.total_events == 2
        assert report.finished_events == 1
        assert report.promoted_count == 1

    def test_duplicate_cu_keeps_latest_verdict_only(self) -> None:
        """한 CU는 정답지에서 한 표다 — 중복 판정은 최신 1건만 승격하고 건수로 보고."""
        events = [
            _finish("cu-a", "rejected", failure_code=GenerationFailureCode.F1, at=_T0),
            _finish(
                "cu-a",
                "rejected",
                failure_code=GenerationFailureCode.F8,
                at=_T0 + timedelta(hours=1),
            ),
        ]
        report = promote_from_events(events, anchor_rows=_anchors(("cu-a", "A4")))

        assert report.promoted_count == 1
        assert report.promoted[0].failure_code == GenerationFailureCode.F8
        assert report.excluded_duplicate_cu == 1


# ──────────────────────────────────────────────────────────────────────────
# ③ 과적합 방지 — 회전·동결·재채점 금지
# ──────────────────────────────────────────────────────────────────────────
def _item(slug: str, anchor: str = "A4", label: GoldenLabel = GoldenLabel.DEFECTIVE) -> GoldenItem:
    return GoldenItem(
        cu_slug=slug,
        anchor_id=anchor,
        label=label,
        failure_code=GenerationFailureCode.F2 if label == GoldenLabel.DEFECTIVE else None,
        as_found_basis=AsFoundBasis.REJECTED_FAILURE_CODE,
    )


class TestRotationAndFreeze:
    """S2-11 재추출·동결 기록 — "교정 후 같은 표본 재채점 금지"의 골든 적용."""

    def test_same_rotation_is_byte_reproducible(self) -> None:
        items = [_item(f"cu-{i:03d}") for i in range(20)]
        first = select_by_anchor(items, quota=5, rotation=3)
        second = select_by_anchor(items, quota=5, rotation=3)

        assert [i.cu_slug for i in first] == [i.cu_slug for i in second]

    def test_different_rotation_reorders_selection(self) -> None:
        """변별력 양방향 — 회전이 실제로 다른 표본을 뽑아야 재추출 규약이 의미를 가진다."""
        items = [_item(f"cu-{i:03d}") for i in range(40)]
        rot0 = {i.cu_slug for i in select_by_anchor(items, quota=5, rotation=0)}
        rot1 = {i.cu_slug for i in select_by_anchor(items, quota=5, rotation=1)}

        assert rot0 != rot1

    def test_quota_applies_per_anchor(self) -> None:
        items = [_item(f"a4-{i}", "A4") for i in range(10)] + [
            _item(f"a5-{i}", "A5") for i in range(3)
        ]
        selected = select_by_anchor(items, quota=5)

        counts: dict[str, int] = {}
        for item in selected:
            counts[item.anchor_id] = counts.get(item.anchor_id, 0) + 1
        assert counts == {"A4": 5, "A5": 3}  # 못 채운 앵커는 있는 만큼(0 채움 금지)

    def test_report_exposes_quota_shortfall(self) -> None:
        events = [_finish("cu-a", "rejected", failure_code=GenerationFailureCode.F1)]
        report = promote_from_events(events, anchor_rows=_anchors(("cu-a", "A4")))

        rendered = render_promotion_report(report, quota=30)
        assert "쿼터(30) 미달" in rendered
        assert "A1: 0건" in rendered  # 표본 0인 앵커도 표에 남는다(침묵 금지)

    def test_freeze_records_version_rotation_and_digest(self) -> None:
        golden = freeze_golden_set(
            [_item("cu-a"), _item("cu-b")], golden_version="v1", rotation=2, frozen_at=_T0
        )

        assert golden.golden_version == "v1"
        assert golden.rotation == 2
        assert golden.frozen_at == _T0
        assert golden.digest == compute_digest(golden.items)
        assert [i.cu_slug for i in golden.items] == ["cu-a", "cu-b"]

    def test_digest_is_content_function_not_order_function(self) -> None:
        one = freeze_golden_set([_item("cu-a"), _item("cu-b")], golden_version="v1")
        two = freeze_golden_set([_item("cu-b"), _item("cu-a")], golden_version="v1")

        assert one.digest == two.digest

    def test_label_edit_changes_digest(self) -> None:
        """라벨을 바꾸면 다른 골든이다 — 같은 셋으로 위장한 재채점을 digest가 막는다."""
        base = freeze_golden_set([_item("cu-a")], golden_version="v1")
        edited = freeze_golden_set([_item("cu-a", label=GoldenLabel.CLEAN)], golden_version="v1")

        assert base.digest != edited.digest

    def test_tampered_file_fails_to_load(self, tmp_path: Path) -> None:
        """손편집 변조는 무증상으로 통과하지 않는다(로드 시 validator가 터진다)."""
        path = tmp_path / "golden.json"
        write_golden_set(path, freeze_golden_set([_item("cu-a")], golden_version="v1"))
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["items"][0]["label"] = "clean"
        payload["items"][0]["failure_code"] = None
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

        with pytest.raises(ValueError, match="digest"):
            load_golden_set(path)

    def test_roundtrip_preserves_items(self, tmp_path: Path) -> None:
        path = tmp_path / "golden.json"
        golden = freeze_golden_set([_item("cu-a"), _item("cu-b")], golden_version="v2", rotation=1)
        write_golden_set(path, golden)

        loaded = load_golden_set(path)
        assert loaded.digest == golden.digest
        assert loaded.rotation == 1
        assert [i.cu_slug for i in loaded.items] == ["cu-a", "cu-b"]


class TestEvaluationLedger:
    """재채점 금지의 집행 부품 — 같은 골든 × 다른 리비전만 위반이다."""

    def test_same_revision_rerun_is_not_a_violation(self, tmp_path: Path) -> None:
        path = tmp_path / "ledger.jsonl"
        append_evaluation_ledger(
            path, EvaluationRecord(digest="d" * 64, engine_revision="abc123", evaluated_at=_T0)
        )
        records, errors = load_evaluation_ledger(path)

        assert errors == []
        assert find_rescore_violation(records, digest="d" * 64, engine_revision="abc123") is None

    def test_same_golden_different_revision_is_a_violation(self, tmp_path: Path) -> None:
        path = tmp_path / "ledger.jsonl"
        append_evaluation_ledger(
            path, EvaluationRecord(digest="d" * 64, engine_revision="abc123", evaluated_at=_T0)
        )
        records, _ = load_evaluation_ledger(path)

        violation = find_rescore_violation(records, digest="d" * 64, engine_revision="def456")
        assert violation is not None
        assert violation.engine_revision == "abc123"

    def test_missing_ledger_is_empty_not_error(self, tmp_path: Path) -> None:
        records, errors = load_evaluation_ledger(tmp_path / "absent.jsonl")
        assert records == [] and errors == []

    def test_broken_ledger_line_preserves_reason(self, tmp_path: Path) -> None:
        """침묵 실패 금지 — 파싱 실패는 예외 타입명+줄 번호로 돌아온다."""
        path = tmp_path / "ledger.jsonl"
        path.write_text('{"digest": "x"}\n', encoding="utf-8")

        records, errors = load_evaluation_ledger(path)
        assert records == []
        assert len(errors) == 1 and "KeyError" in errors[0]


# ──────────────────────────────────────────────────────────────────────────
# 스키마·파서 계약
# ──────────────────────────────────────────────────────────────────────────
class TestSchemaContracts:
    def test_subject_id_defaults_to_math_and_is_settable(self) -> None:
        """Validation의 Math 비종속 좌석 — 처음부터 스키마에 있다(acceptance ⑤ 후단)."""
        assert _item("cu-a").subject_id == "math"
        physics = GoldenItem(
            cu_slug="cu-p",
            subject_id="physics",
            anchor_id="A4",
            label=GoldenLabel.CLEAN,
            as_found_basis=AsFoundBasis.PRE_REVIEW_SNAPSHOT,
        )
        assert physics.subject_id == "physics"

    def test_clean_label_rejects_failure_code(self) -> None:
        with pytest.raises(ValueError, match="clean"):
            GoldenItem(
                cu_slug="cu-a",
                anchor_id="A4",
                label=GoldenLabel.CLEAN,
                failure_code=GenerationFailureCode.F1,
                as_found_basis=AsFoundBasis.PRE_REVIEW_SNAPSHOT,
            )

    def test_unknown_anchor_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="앵커"):
            GoldenItem(
                cu_slug="cu-a",
                anchor_id="A9",
                label=GoldenLabel.CLEAN,
                as_found_basis=AsFoundBasis.PRE_REVIEW_SNAPSHOT,
            )

    def test_anchor_ids_match_frozen_audit_definition(self) -> None:
        """앵커 id 정본은 `ANCHOR_DEFS`(EOS-52 실사 스크립트) — 두 목록의 드리프트를 동결한다.

        `ANCHOR_DEFS`는 8앵커 원안(대학 A7·A8 포함)을 그대로 들고 있고, G0 확정(검증설계서
        §1-1)은 **대학 2종을 2027-01로 이월**해 6앵커로 좁혔다. 그래서 "같다"가 아니라
        "이월분을 뺀 나머지와 같다"가 계약이다 — K-12 앵커가 늘거나 줄면 이 테스트가 깨져
        골든 쿼터 축을 함께 고치게 한다.
        """
        path = (
            Path(__file__).resolve().parents[3]
            / "scripts"
            / "analysis"
            / "eos_anchor_asset_audit.py"
        )
        spec = importlib.util.spec_from_file_location("eos_anchor_asset_audit", path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        defs = {a["id"]: a for a in module.ANCHOR_DEFS}
        deferred = {"A7", "A8"}  # 대학 앵커 — §1-1 확정 결정 1(2027-01 이월)
        assert set(defs) - deferred == set(ANCHOR_IDS)
        assert all("대학" in defs[a]["title"] for a in deferred)

    def test_anchor_row_parser_rejects_vocabulary_outsiders(self) -> None:
        rows, errors = parse_anchor_rows(
            [
                {"cu_slug": "cu-a", "anchor_id": "A4"},
                {"slug": "cu-b", "anchor": "A9"},
                {"anchor_id": "A4"},
            ]
        )
        assert [r.cu_slug for r in rows] == ["cu-a"]
        assert len(errors) == 2

    def test_as_found_parser_preserves_failure_reasons(self) -> None:
        rows, errors = parse_as_found_rows(
            [
                {"cu_slug": "cu-a", "as_found_label": "clean"},
                {"cu_slug": "cu-b", "label": "sorta-ok"},
                {"cu_slug": "cu-c", "label": "defective", "failure_code": "F99"},
            ]
        )
        assert [r.cu_slug for r in rows] == ["cu-a"]
        assert len(errors) == 2
        assert all("ValueError" in e for e in errors)


# ──────────────────────────────────────────────────────────────────────────
# CLI — 측정 실패 승격(④)
# ──────────────────────────────────────────────────────────────────────────
def _write_events(path: Path, events: list[ReviewTimerEvent]) -> None:
    for event in events:
        append_event_jsonl(path, event)


def _write_anchor_map(path: Path, pairs: list[tuple[str, str]]) -> None:
    path.write_text(
        "".join(
            json.dumps({"cu_slug": slug, "anchor_id": anchor}, ensure_ascii=False) + "\n"
            for slug, anchor in pairs
        ),
        encoding="utf-8",
    )


class TestCli:
    def test_promotes_and_freezes(self, tmp_path: Path) -> None:
        events_path = tmp_path / "events.jsonl"
        anchors_path = tmp_path / "anchors.jsonl"
        out_path = tmp_path / "golden.json"
        _write_events(
            events_path,
            [
                _finish("cu-a", "rejected", failure_code=GenerationFailureCode.F2),
                _finish("cu-b", "approved"),
            ],
        )
        _write_anchor_map(anchors_path, [("cu-a", "A4"), ("cu-b", "A4")])

        code = main(
            [
                "--events",
                str(events_path),
                "--anchor-map",
                str(anchors_path),
                "--out",
                str(out_path),
                "--golden-version",
                "v1",
            ]
        )

        assert code == 0
        golden = load_golden_set(out_path)
        assert [i.cu_slug for i in golden.items] == ["cu-a"]  # approved는 fail-closed 제외

    def test_zero_promotion_is_measurement_failure(self, tmp_path: Path) -> None:
        """골든 0건은 '통과'가 아니다(acceptance ④) — 변별력 확인용 대칭 케이스."""
        events_path = tmp_path / "events.jsonl"
        anchors_path = tmp_path / "anchors.jsonl"
        _write_events(events_path, [_finish("cu-b", "approved")])
        _write_anchor_map(anchors_path, [("cu-b", "A4")])

        code = main(["--events", str(events_path), "--anchor-map", str(anchors_path)])
        assert code == 1

    def test_missing_input_is_measurement_failure(self, tmp_path: Path) -> None:
        code = main(
            [
                "--events",
                str(tmp_path / "absent.jsonl"),
                "--anchor-map",
                str(tmp_path / "absent2.jsonl"),
            ]
        )
        assert code == 1

    def test_parse_failure_blocks_freeze(self, tmp_path: Path) -> None:
        """부분 입력으로 동결 금지 — 깨진 행이 반려였다면 정답지에서 defective가 사라진다."""
        events_path = tmp_path / "events.jsonl"
        anchors_path = tmp_path / "anchors.jsonl"
        _write_events(
            events_path, [_finish("cu-a", "rejected", failure_code=GenerationFailureCode.F2)]
        )
        with events_path.open("a", encoding="utf-8") as fp:
            fp.write("{깨진 줄\n")
        _write_anchor_map(anchors_path, [("cu-a", "A4")])

        code = main(["--events", str(events_path), "--anchor-map", str(anchors_path)])
        assert code == 1

    def test_report_is_written_when_requested(self, tmp_path: Path) -> None:
        events_path = tmp_path / "events.jsonl"
        anchors_path = tmp_path / "anchors.jsonl"
        report_path = tmp_path / "report.md"
        _write_events(
            events_path, [_finish("cu-a", "rejected", failure_code=GenerationFailureCode.F2)]
        )
        _write_anchor_map(anchors_path, [("cu-a", "A4")])

        code = main(
            [
                "--events",
                str(events_path),
                "--anchor-map",
                str(anchors_path),
                "--report",
                str(report_path),
            ]
        )

        assert code == 0
        body = report_path.read_text(encoding="utf-8")
        assert "골든 벤치마크 승격 리포트" in body
        assert "as-found 라벨 무결성" in body


class TestForwardCompatEditAwareVerdict:
    """EOS-62 착지 후 상태의 선계약 — 어휘가 늘어도 이 규약이 그대로 성립하는지 미리 굳힌다.

    `ReviewVerdict`가 아직 2값이라 실 writer로는 `approved_with_edit` 이벤트를 만들 수 없다.
    그래서 `model_construct`(검증 우회)로 *착지 후 상태*를 모사한다 — 우회하는 것은 상류
    schema의 어휘 제약뿐이고, 판정 로직은 실물 그대로 돌린다.
    """

    def test_approved_with_edit_promotes_as_defective(self, monkeypatch) -> None:
        monkeypatch.setattr(
            "whymath_backend.harness.golden_benchmark.edit_aware_verdict_available",
            lambda: True,
        )
        event = ReviewTimerEvent.model_construct(
            event_id=uuid.uuid4(),
            review_session_id=uuid.uuid4(),
            cu_slug="cu-edited",
            problem_id=None,
            reviewer_id="kiki",
            event_type="finished",
            verdict="approved_with_edit",
            failure_code=GenerationFailureCode.F7,
            failure_note=None,
            elapsed_ms=90_000,
            occurred_at=_T0,
            recorded_at=None,
        )
        report = promote_from_events(
            [event],
            anchor_rows=_anchors(("cu-edited", "A5")),
            edit_aware_since=_T0 - timedelta(days=1),
        )

        assert report.promoted_count == 1
        item = report.promoted[0]
        assert item.label == GoldenLabel.DEFECTIVE  # 손질했다 = as-found는 결함이었다
        assert item.failure_code == GenerationFailureCode.F7
        assert item.as_found_basis == AsFoundBasis.EDIT_AWARE_VERDICT

    def test_vocabulary_outsider_is_counted_separately(self, monkeypatch) -> None:
        """상류가 이 규약이 모르는 값을 추가하면 모호 승인이 아니라 '어휘 밖'으로 센다."""
        monkeypatch.setattr(
            "whymath_backend.harness.golden_benchmark.edit_aware_verdict_available",
            lambda: True,
        )
        event = ReviewTimerEvent.model_construct(
            event_id=uuid.uuid4(),
            review_session_id=uuid.uuid4(),
            cu_slug="cu-escalated",
            problem_id=None,
            reviewer_id="kiki",
            event_type="finished",
            verdict="escalate",
            failure_code=None,
            failure_note=None,
            elapsed_ms=None,
            occurred_at=_T0,
            recorded_at=None,
        )
        report = promote_from_events(
            [event],
            anchor_rows=_anchors(("cu-escalated", "A5")),
            edit_aware_since=_T0 - timedelta(days=1),
        )

        assert report.promoted_count == 0
        assert report.excluded_unknown_verdict == 1
        assert report.excluded_ambiguous_approved == 0


class TestCliUnlockPaths:
    """승격 경로 ⓐ·ⓑ의 CLI 배선 — 규약이 코드로만 있고 CLI에서 못 쓰면 집행이 아니다."""

    def test_as_found_labels_unlock_clean_promotion(self, tmp_path: Path) -> None:
        events_path = tmp_path / "events.jsonl"
        anchors_path = tmp_path / "anchors.jsonl"
        as_found_path = tmp_path / "as_found.jsonl"
        out_path = tmp_path / "golden.json"
        _write_events(events_path, [_finish("cu-b", "approved")])
        _write_anchor_map(anchors_path, [("cu-b", "A4")])
        as_found_path.write_text(
            json.dumps({"cu_slug": "cu-b", "as_found_label": "clean"}) + "\n", encoding="utf-8"
        )

        code = main(
            [
                "--events",
                str(events_path),
                "--anchor-map",
                str(anchors_path),
                "--as-found-labels",
                str(as_found_path),
                "--out",
                str(out_path),
            ]
        )

        assert code == 0
        golden = load_golden_set(out_path)
        assert [i.label for i in golden.items] == [GoldenLabel.CLEAN.value]

    def test_missing_as_found_file_is_measurement_failure(self, tmp_path: Path) -> None:
        events_path = tmp_path / "events.jsonl"
        anchors_path = tmp_path / "anchors.jsonl"
        _write_events(
            events_path, [_finish("cu-a", "rejected", failure_code=GenerationFailureCode.F2)]
        )
        _write_anchor_map(anchors_path, [("cu-a", "A4")])

        code = main(
            [
                "--events",
                str(events_path),
                "--anchor-map",
                str(anchors_path),
                "--as-found-labels",
                str(tmp_path / "absent.jsonl"),
            ]
        )
        assert code == 1

    def test_missing_anchor_map_is_measurement_failure(self, tmp_path: Path) -> None:
        events_path = tmp_path / "events.jsonl"
        _write_events(
            events_path, [_finish("cu-a", "rejected", failure_code=GenerationFailureCode.F2)]
        )

        code = main(["--events", str(events_path), "--anchor-map", str(tmp_path / "absent.jsonl")])
        assert code == 1

    def test_unparsable_edit_aware_since_is_measurement_failure(self, tmp_path: Path) -> None:
        events_path = tmp_path / "events.jsonl"
        anchors_path = tmp_path / "anchors.jsonl"
        _write_events(
            events_path, [_finish("cu-a", "rejected", failure_code=GenerationFailureCode.F2)]
        )
        _write_anchor_map(anchors_path, [("cu-a", "A4")])

        code = main(
            [
                "--events",
                str(events_path),
                "--anchor-map",
                str(anchors_path),
                "--edit-aware-since",
                "어제",
            ]
        )
        assert code == 1

    def test_edit_aware_since_warns_when_vocabulary_absent(self, tmp_path: Path, capsys) -> None:
        """어휘 미착지인데 경계만 준 상태를 조용히 넘기지 않는다(경로 ⓑ 미적용 자인)."""
        if edit_aware_verdict_available():  # pragma: no cover - EOS-62 착지 후 경로
            pytest.skip("EOS-62 착지 — 이 케이스는 어휘 부재 상태의 계약이다")
        events_path = tmp_path / "events.jsonl"
        anchors_path = tmp_path / "anchors.jsonl"
        _write_events(
            events_path, [_finish("cu-a", "rejected", failure_code=GenerationFailureCode.F2)]
        )
        _write_anchor_map(anchors_path, [("cu-a", "A4")])

        code = main(
            [
                "--events",
                str(events_path),
                "--anchor-map",
                str(anchors_path),
                "--edit-aware-since",
                "2026-09-01T00:00:00+00:00",
            ]
        )

        assert code == 0
        assert "EOS-62 미착지" in capsys.readouterr().err


def test_quota_must_be_positive() -> None:
    """쿼터 0은 "아무것도 안 뽑음"을 조용히 정상 처리하게 만든다 — 계약으로 막는다."""
    with pytest.raises(ValueError, match="quota"):
        select_by_anchor([_item("cu-a")], quota=0)
