"""repeat_recommendation_report 단위테스트 — hermetic(라이브 DB 0)·REC-06.

집계 코어(`build_repeat_report`)는 순수 함수라 픽스처로 경계까지 전수 단언하고,
`fetch_probe_inputs`는 큐 기반 가짜 세션(`test_recommendation_reach_report.py` 관례 답습)으로
실 DB 없이 쿼리 4회의 순서·매핑을 검증한다. 실 WHERE/ORDER BY/LIMIT의 SQL 정확성은 FakeSession이
stmt를 무시하므로 여기서 검증하지 않는다 — 그 축은 `tests/backend/api/test_me.py`(정렬 키 SQL
동결)와 `test_me_integration.py`(실 PG 왕복)가 맡는다.

핵심 acceptance:
  ② **원인 구분** — '제외 축 0행'(`no_attempt_exclusion`)과 '후보 풀이 실제로 1건'
     (`candidate_pool_singleton`)이 **서로 다른 값**을 내는지. 두 상태가 같은 값이면 처방이
     정반대인 두 결함이 한 얼굴이 된다(침묵 실패).
  ④ **변별력(양방향)** — `problem_attempt` 축 입력이 0→1로 켜지면 원인 코드가 바뀌고,
     되돌리면 원복되는지. 성공/실패가 같은 값이면 검증이 아니라 위장이다.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

import pytest

from whymath_backend.ops import repeat_recommendation_report as rr


# ──────────────────────────────────────────────────────────────────────────
# 가짜 세션 — execute() 호출 순서대로 큐잉 결과 반환(stmt는 무시).
# ──────────────────────────────────────────────────────────────────────────
class _FakeResult:
    def __init__(self, value: Any) -> None:
        self._value = value

    def scalar_one(self) -> Any:
        return self._value

    def all(self) -> Any:
        return self._value


class _QueueSession:
    """`fetch_probe_inputs`의 execute 4회(①attempt 총계 ②모집단 ③후보 풀 ④개념)를 큐로 반환."""

    def __init__(self, values: list[Any]) -> None:
        self._values = values
        self.calls = 0

    async def execute(self, _stmt: object) -> _FakeResult:
        value = self._values[self.calls]
        self.calls += 1
        return _FakeResult(value)


def _row(difficulty: float, *, irt_b: float | None = None) -> tuple[uuid.UUID, float, float | None]:
    return (uuid.uuid4(), difficulty, irt_b)


def _candidate(
    difficulty: float,
    *,
    concepts: tuple[str, ...] = (),
    types: tuple[str, ...] = (),
    in_corpus: bool = True,
    problem_id: uuid.UUID | None = None,
) -> rr.CandidateRow:
    return rr.CandidateRow(
        problem_id=problem_id or uuid.uuid4(),
        difficulty_overall=difficulty,
        irt_difficulty_b=None,
        concept_codes=concepts,
        problem_type_codes=types,
        in_corpus=in_corpus,
    )


def _inputs(pool: tuple[rr.CandidateRow, ...], *, attempts: int = 0) -> rr.RepeatProbeInputs:
    return rr.RepeatProbeInputs(
        theta=0.0,
        pool=pool,
        attempt_axis_row_total=attempts,
        candidate_population_total=max(len(pool), 1),
        corpus_problem_total=len(pool),
        corpus_missing_id_total=0,
    )


# ──────────────────────────────────────────────────────────────────────────
# 콜드스타트 θ — 상수 하드코딩이 아니라 l2에서 유도한다.
# ──────────────────────────────────────────────────────────────────────────
def test_cold_start_theta_is_derived_from_l2_empty_response_estimate() -> None:
    from whymath_backend.l2.irt import estimate_ability

    assert rr.cold_start_theta() == estimate_ability([])


# ──────────────────────────────────────────────────────────────────────────
# fetch_probe_inputs — 쿼리 4회 순서 계약 + 개념/유형 축 매핑.
# ──────────────────────────────────────────────────────────────────────────
async def test_fetch_probe_inputs_maps_four_queries_in_order() -> None:
    pid_a, pid_b = uuid.uuid4(), uuid.uuid4()
    session = _QueueSession(
        [
            7,  # ① problem_attempt 전체 행 수
            123,  # ② 후보 모집단
            [(pid_a, 3.0, None), (pid_b, 4.0, 1.5)],  # ③ 후보 풀
            [(pid_a, "CONCEPT-1"), (pid_a, "CONCEPT-2")],  # ④ 개념 매핑
        ]
    )
    index = rr.ProblemTypeIndex(
        by_problem_id={pid_a: ("ptype.solve-for-unknown",)}, record_total=9, missing_id_total=2
    )
    inputs = await rr.fetch_probe_inputs(
        session,  # type: ignore[arg-type]
        theta=0.0,
        problem_type_index=index,
    )
    assert session.calls == 4
    assert inputs.attempt_axis_row_total == 7
    assert inputs.candidate_population_total == 123
    assert inputs.corpus_problem_total == 9
    assert inputs.corpus_missing_id_total == 2
    first, second = inputs.pool
    assert first.problem_id == pid_a
    assert first.concept_codes == ("CONCEPT-1", "CONCEPT-2")  # 사전순 고정
    assert first.problem_type_codes == ("ptype.solve-for-unknown",)
    assert first.in_corpus is True
    # 코퍼스에 없는 문항은 '미태깅'이 아니라 '미조인'이다(서로 다른 값).
    assert second.problem_type_codes == ()
    assert second.in_corpus is False
    assert second.irt_difficulty_b == 1.5


# ──────────────────────────────────────────────────────────────────────────
# acceptance① — 진도 폭: N회 연속 호출에서 서로 다른 problem_id 수.
# ──────────────────────────────────────────────────────────────────────────
def test_observed_progress_width_is_one_while_counterfactual_opens() -> None:
    """제외 축이 죽어 있으면 N회 전부 같은 문항 — 반사실(제외 작동)에서만 진도가 열린다."""
    pool = (_candidate(3.0), _candidate(3.1), _candidate(2.9))
    report = rr.build_repeat_report(_inputs(pool), calls=5)
    assert report.calls == 5
    assert report.observed_distinct_total == 1
    assert len(report.observed_selection) == 5
    assert len(set(report.observed_selection)) == 1
    # 반사실: 후보가 3건이라 5회 호출에서 3건까지만 열린다(빈 자리를 지어내지 않는다).
    assert report.feedback_distinct_total == 3
    assert len(report.feedback_selection) == 3


def test_empty_pool_yields_no_recommendation_at_all() -> None:
    report = rr.build_repeat_report(_inputs(()), calls=3)
    assert report.observed_selection == ()
    assert report.observed_distinct_total == 0
    assert report.repeat_cause == rr.CAUSE_EMPTY_CANDIDATE_POOL


def test_calls_must_be_positive() -> None:
    with pytest.raises(ValueError, match="calls는 1 이상"):
        rr.build_repeat_report(_inputs((_candidate(3.0),)), calls=0)


# ──────────────────────────────────────────────────────────────────────────
# acceptance② — 원인 구분: 두 상태가 **서로 다른 값**을 낸다.
# ──────────────────────────────────────────────────────────────────────────
def test_repeat_cause_separates_dead_exclusion_axis_from_singleton_pool() -> None:
    """'제외 축 0행'과 '후보 풀 1건'은 처방이 정반대다 — 절대 같은 코드가 나오면 안 된다."""
    dead_axis = rr.build_repeat_report(
        _inputs((_candidate(3.0), _candidate(3.1), _candidate(2.9)), attempts=0)
    )
    singleton = rr.build_repeat_report(_inputs((_candidate(3.0),), attempts=0))

    assert dead_axis.repeat_cause == rr.CAUSE_NO_ATTEMPT_EXCLUSION
    assert singleton.repeat_cause == rr.CAUSE_CANDIDATE_POOL_SINGLETON
    assert dead_axis.repeat_cause != singleton.repeat_cause
    assert dead_axis.repeat_cause_detail != singleton.repeat_cause_detail
    # 두 경우 모두 진도 폭 실측치는 1이다 — 즉 *진도 폭만으로는 구분이 안 된다*.
    # 원인 코드가 존재하는 이유가 바로 그것이다.
    assert dead_axis.observed_distinct_total == singleton.observed_distinct_total == 1


def test_repeat_cause_marks_selector_determinism_when_axis_has_input() -> None:
    """제외 축 입력원이 실재하면 원인은 '입력 0행'이 아니라 선택기 결정론이다."""
    report = rr.build_repeat_report(
        _inputs((_candidate(3.0), _candidate(3.1)), attempts=42), calls=4
    )
    assert report.repeat_cause == rr.CAUSE_DETERMINISTIC_ARGMAX_TIE
    assert report.attempt_axis_row_total == 42


def test_repeat_cause_does_not_depend_on_call_count() -> None:
    """calls=1에서도 큰 풀이 'singleton'으로 오판되면 안 된다(호출 수가 원인을 바꾸면 가짜)."""
    pool = (_candidate(3.0), _candidate(3.1), _candidate(2.9))
    one_call = rr.build_repeat_report(_inputs(pool), calls=1)
    many_calls = rr.build_repeat_report(_inputs(pool), calls=9)
    assert one_call.repeat_cause == many_calls.repeat_cause == rr.CAUSE_NO_ATTEMPT_EXCLUSION


def test_every_cause_code_has_a_distinct_detail_sentence() -> None:
    details = list(rr.CAUSE_DETAIL.values())
    assert len(set(details)) == len(details)  # 같은 문장을 돌려주면 구분이 아니다
    assert set(rr.CAUSE_DETAIL) == {
        rr.CAUSE_EMPTY_CANDIDATE_POOL,
        rr.CAUSE_CANDIDATE_POOL_SINGLETON,
        rr.CAUSE_NO_ATTEMPT_EXCLUSION,
        rr.CAUSE_DETERMINISTIC_ARGMAX_TIE,
    }


# ──────────────────────────────────────────────────────────────────────────
# acceptance④ — 변별력(양방향): attempt 축 입력 0 → 1 → 0 왕복.
# ──────────────────────────────────────────────────────────────────────────
async def test_attempt_axis_injection_toggles_cause_bidirectionally() -> None:
    """`problem_attempt` 0행 ↔ 1행 왕복 — 원인 코드가 실제로 켜지고 꺼진다."""
    pid_a, pid_b = uuid.uuid4(), uuid.uuid4()
    pool_rows = [(pid_a, 3.0, None), (pid_b, 3.1, None)]
    index = rr.ProblemTypeIndex(by_problem_id={}, record_total=0, missing_id_total=0)

    async def _report(attempt_total: int) -> rr.RepeatReport:
        session = _QueueSession([attempt_total, 2, pool_rows, []])
        inputs = await rr.fetch_probe_inputs(
            session,  # type: ignore[arg-type]
            theta=0.0,
            problem_type_index=index,
        )
        return rr.build_repeat_report(inputs, calls=3)

    # ① 0행 — 제외 축 미도달
    zero = await _report(0)
    assert zero.repeat_cause == rr.CAUSE_NO_ATTEMPT_EXCLUSION
    assert "제외 축 입력 0행" in rr.render_report(zero)

    # ② 1행 주입 — 원인 코드 전환
    one = await _report(1)
    assert one.repeat_cause == rr.CAUSE_DETERMINISTIC_ARGMAX_TIE
    assert "제외 축 입력 0행" not in rr.render_report(one)

    # ③ 되돌림 — 원복
    back = await _report(0)
    assert back.repeat_cause == rr.CAUSE_NO_ATTEMPT_EXCLUSION
    assert back == zero


# ──────────────────────────────────────────────────────────────────────────
# 동률 계상 — 후보 순서가 선택을 가르는 상태를 수치로 드러낸다(2차 키의 근거).
# ──────────────────────────────────────────────────────────────────────────
def test_top_score_tie_total_counts_information_ties() -> None:
    """θ=0에서 b=0인 후보가 3건이면 셋 다 정보량 최대 — 순서가 선택을 가른다."""
    report = rr.build_repeat_report(
        _inputs((_candidate(3.0), _candidate(3.0), _candidate(3.0), _candidate(5.0)))
    )
    assert report.top_score_tie_total == 3


def test_top_score_tie_total_is_one_when_max_is_unique() -> None:
    report = rr.build_repeat_report(_inputs((_candidate(3.0), _candidate(4.5), _candidate(1.5))))
    assert report.top_score_tie_total == 1


def test_empty_pool_has_no_ties() -> None:
    assert rr.build_repeat_report(_inputs(())).top_score_tie_total == 0


# ──────────────────────────────────────────────────────────────────────────
# acceptance① — 집중도: 분모를 항상 함께 내고, '미태깅'과 '미조인'을 가른다.
# ──────────────────────────────────────────────────────────────────────────
def test_concentration_reports_denominator_and_top_share() -> None:
    pool = (
        _candidate(3.0, concepts=("C1",), types=("ptype.a",)),
        _candidate(3.0, concepts=("C1",), types=("ptype.a",)),
        _candidate(3.0, concepts=("C2",), types=("ptype.b",)),
        _candidate(3.0, concepts=(), types=()),  # 라벨 없음(미태깅)
    )
    report = rr.build_repeat_report(_inputs(pool))
    concept = report.concept_concentration
    assert concept.labelled_problem_total == 3
    assert concept.unlabelled_problem_total == 1
    assert concept.unresolved_problem_total == 0
    assert concept.distinct_labels == 2
    assert (concept.top_label, concept.top_count) == ("C1", 2)
    assert concept.top_share == pytest.approx(2 / 3)
    assert concept.distribution == {"C1": 2, "C2": 1}


def test_problem_type_axis_separates_untagged_from_unjoined() -> None:
    """'코퍼스엔 있는데 태그가 빔'과 '코퍼스에서 못 찾음'은 서로 다른 값이어야 한다."""
    pool = (
        _candidate(3.0, types=("ptype.a",), in_corpus=True),
        _candidate(3.0, types=(), in_corpus=True),  # 미태깅
        _candidate(3.0, types=(), in_corpus=False),  # 미조인
        _candidate(3.0, types=(), in_corpus=False),
    )
    axis = rr.build_repeat_report(_inputs(pool)).problem_type_concentration
    assert axis.labelled_problem_total == 1
    assert axis.unlabelled_problem_total == 1
    assert axis.unresolved_problem_total == 2
    assert axis.unlabelled_problem_total != axis.unresolved_problem_total


def test_concentration_top_share_is_none_when_denominator_is_zero() -> None:
    """분모 0에 0.0을 돌려주면 '쏠림 없음'으로 위장된다 — None(측정 불가)이어야 한다."""
    axis = rr.build_repeat_report(_inputs((_candidate(3.0),))).concept_concentration
    assert axis.labelled_problem_total == 0
    assert axis.top_share is None
    assert axis.top_label is None
    assert "측정 불가(분모 0)" in rr.render_report(rr.build_repeat_report(_inputs(())))


def test_concentration_ranking_is_deterministic_on_ties() -> None:
    """같은 건수 라벨은 사전순으로 고정(Counter 삽입 순서 의존 배제)."""
    pool_ab = (_candidate(3.0, concepts=("B",)), _candidate(3.0, concepts=("A",)))
    pool_ba = (_candidate(3.0, concepts=("A",)), _candidate(3.0, concepts=("B",)))
    first = rr.build_repeat_report(_inputs(pool_ab)).concept_concentration
    second = rr.build_repeat_report(_inputs(pool_ba)).concept_concentration
    assert first.top_label == second.top_label == "A"
    assert list(first.distribution) == list(second.distribution) == ["A", "B"]


# ──────────────────────────────────────────────────────────────────────────
# b 결정 불가 후보 — 0으로 뭉개지 않고 별도 계상.
# ──────────────────────────────────────────────────────────────────────────
def test_rows_without_difficulty_source_are_counted_not_silently_dropped() -> None:
    pool = (
        rr.CandidateRow(problem_id=uuid.uuid4(), difficulty_overall=None, irt_difficulty_b=None),
        _candidate(3.0),
    )
    report = rr.build_repeat_report(_inputs(pool))
    assert report.b_missing_total == 1
    assert report.candidate_pool_size == 2  # 풀 크기는 원본 그대로 보고
    assert report.observed_distinct_total == 1
    assert "b(난이도) 결정 불가로 제외된 후보: 1건" in rr.render_report(report)


# ──────────────────────────────────────────────────────────────────────────
# 코퍼스 유형 인덱스 로더 — 파손은 예외, id 부재는 계상.
# ──────────────────────────────────────────────────────────────────────────
def _write_corpus(root: Path, name: str, lines: list[str]) -> None:
    corpus_dir = root / name
    corpus_dir.mkdir(parents=True)
    (corpus_dir / "problems.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_load_problem_type_index_reads_codes_and_counts_missing_ids(tmp_path: Path) -> None:
    pid = uuid.uuid4()
    _write_corpus(
        tmp_path,
        "problem_bank_x_v0",
        [
            json.dumps({"problem_id": str(pid), "problem_type_codes": ["ptype.b", "ptype.a"]}),
            json.dumps({"slug": "no-id", "problem_type_codes": ["ptype.a"]}),  # id 없음
            "",  # 빈 줄 무시
        ],
    )
    index = rr.load_problem_type_index(tmp_path)
    assert index.by_problem_id == {pid: ("ptype.a", "ptype.b")}  # 사전순 고정
    assert index.record_total == 2
    assert index.missing_id_total == 1


def test_load_problem_type_index_returns_empty_when_root_missing(tmp_path: Path) -> None:
    index = rr.load_problem_type_index(tmp_path / "없는디렉터리")
    assert index.by_problem_id == {}
    assert index.record_total == 0


def test_load_problem_type_index_raises_on_malformed_record(tmp_path: Path) -> None:
    """파손을 빈 인덱스로 삼키면 '유형 미태깅 100%'라는 거짓 관측이 된다 — 예외로 올린다."""
    _write_corpus(tmp_path, "problem_bank_x_v0", [json.dumps([1, 2, 3])])
    with pytest.raises(TypeError, match="object가 아님"):
        rr.load_problem_type_index(tmp_path)


def test_load_problem_type_index_raises_on_non_list_codes(tmp_path: Path) -> None:
    _write_corpus(
        tmp_path,
        "problem_bank_x_v0",
        [json.dumps({"problem_id": str(uuid.uuid4()), "problem_type_codes": "ptype.a"})],
    )
    with pytest.raises(TypeError, match="problem_type_codes가 배열이 아님"):
        rr.load_problem_type_index(tmp_path)


def test_load_problem_type_index_raises_on_non_string_id(tmp_path: Path) -> None:
    _write_corpus(tmp_path, "problem_bank_x_v0", [json.dumps({"problem_id": 7})])
    with pytest.raises(TypeError, match="problem_id가 문자열이 아님"):
        rr.load_problem_type_index(tmp_path)


def test_real_corpus_smoke_has_type_codes(tmp_path: Path) -> None:
    """실제 코퍼스가 유형 축을 실제로 갖고 있는지 — 리포트의 분모가 지어낸 값이 아님을 확인."""
    index = rr.load_problem_type_index(rr.default_corpus_root())
    assert index.record_total > 2000, "코퍼스를 못 읽었다면 유형 집중도는 전부 거짓이 된다"
    tagged = sum(1 for codes in index.by_problem_id.values() if codes)
    assert tagged > 2000


# ──────────────────────────────────────────────────────────────────────────
# JSON 직렬화 — 구조·정렬.
# ──────────────────────────────────────────────────────────────────────────
def test_report_to_json_structure() -> None:
    pool = (_candidate(3.0, concepts=("C1",), types=("ptype.a",)), _candidate(3.5))
    payload: dict[str, Any] = rr.report_to_json(
        rr.build_repeat_report(_inputs(pool, attempts=0), calls=2)
    )
    assert payload["probe"]["calls"] == 2
    assert payload["probe"]["candidate_pool_size"] == 2
    assert payload["progress_width"]["observed_distinct_total"] == 1
    assert payload["progress_width"]["counterfactual_feedback_distinct_total"] == 2
    assert payload["repeat_cause"]["code"] == rr.CAUSE_NO_ATTEMPT_EXCLUSION
    assert payload["concentration"][rr.AXIS_CONCEPT]["top_label"] == "C1"
    assert payload["concentration"][rr.AXIS_PROBLEM_TYPE]["axis"] == rr.AXIS_PROBLEM_TYPE


def test_dump_json_round_trips_with_sorted_keys() -> None:
    text = rr.dump_json(rr.build_repeat_report(_inputs((_candidate(3.0),))))
    parsed = json.loads(text)
    assert parsed["repeat_cause"]["code"] == rr.CAUSE_CANDIDATE_POOL_SINGLETON
    assert list(parsed) == sorted(parsed)


# ──────────────────────────────────────────────────────────────────────────
# CLI main() — exit code·stdout/stderr·--json 산출물.
# ──────────────────────────────────────────────────────────────────────────
def _patch_run(monkeypatch: Any, report: rr.RepeatReport) -> None:
    async def _fake_run(*, calls: int, theta: float, corpus_root: Path) -> rr.RepeatReport:
        return report

    monkeypatch.setattr(rr, "_run", _fake_run)


def test_main_success_prints_report_and_returns_zero(monkeypatch: Any, capsys: Any) -> None:
    """진도 폭이 1이어도 exit 0 — 관측 리포트이지 게이트가 아니다."""
    _patch_run(monkeypatch, rr.build_repeat_report(_inputs((_candidate(3.0), _candidate(3.1)))))
    assert rr.main([]) == 0
    out = capsys.readouterr().out
    assert "반복 추천 가시화 리포트" in out
    assert rr.CAUSE_NO_ATTEMPT_EXCLUSION in out


def test_main_writes_json_when_requested(tmp_path: Any, monkeypatch: Any, capsys: Any) -> None:
    _patch_run(monkeypatch, rr.build_repeat_report(_inputs((_candidate(3.0),))))
    json_path = tmp_path / "repeat.json"
    assert rr.main(["--json", str(json_path)]) == 0
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["repeat_cause"]["code"] == rr.CAUSE_CANDIDATE_POOL_SINGLETON
    assert str(json_path) in capsys.readouterr().out


def test_main_runtime_error_reports_exception_type_name(monkeypatch: Any, capsys: Any) -> None:
    """DB 접속 등 실행 오류 시 exit 2 + stderr에 예외 **타입명**(침묵 실패 금지)."""

    class _BoomError(Exception):
        """주입 실패용 커스텀 예외 — 타입명 로그 검증이 이 이름을 찾는다."""

    async def _fake_run_raises(*, calls: int, theta: float, corpus_root: Path) -> rr.RepeatReport:
        raise _BoomError("DB 접속 실패(주입)")

    monkeypatch.setattr(rr, "_run", _fake_run_raises)
    assert rr.main([]) == 2
    assert "_BoomError" in capsys.readouterr().err


def test_main_forwards_cli_arguments(monkeypatch: Any, capsys: Any) -> None:
    """--calls/--theta/--corpus-root가 실제로 _run에 전달되는지(옵션이 장식이 아님을 확인)."""
    seen: dict[str, Any] = {}

    async def _fake_run(*, calls: int, theta: float, corpus_root: Path) -> rr.RepeatReport:
        seen.update(calls=calls, theta=theta, corpus_root=corpus_root)
        return rr.build_repeat_report(_inputs((_candidate(3.0),)))

    monkeypatch.setattr(rr, "_run", _fake_run)
    assert rr.main(["--calls", "9", "--theta", "1.25", "--corpus-root", "/tmp/x"]) == 0
    assert seen == {"calls": 9, "theta": 1.25, "corpus_root": Path("/tmp/x")}
    capsys.readouterr()


def test_main_defaults_to_cold_start_theta(monkeypatch: Any, capsys: Any) -> None:
    seen: dict[str, Any] = {}

    async def _fake_run(*, calls: int, theta: float, corpus_root: Path) -> rr.RepeatReport:
        seen["theta"] = theta
        return rr.build_repeat_report(_inputs((_candidate(3.0),)))

    monkeypatch.setattr(rr, "_run", _fake_run)
    assert rr.main([]) == 0
    assert seen["theta"] == rr.cold_start_theta()
    capsys.readouterr()
