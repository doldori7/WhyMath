"""검수자용 샘플 패키지(reviewer_sample_package) 단위테스트 — 결정성·층화 쿼터·완전성(hermetic).

실 코퍼스를 스켈레톤 배치(`run_corpus_batch`)로 소형 재현해 fixture로 쓴다(LLM 0·DB 0·네트워크
0). 배치는 결정론이라 fixture도 재현 가능하다 — 표본 선택의 결정성·층화 쿼터·오개념 강제 포함을
봉인한다. 자체생성 코퍼스라 학생 PII가 원천적으로 없음도 확인한다.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from whymath_backend.harness.problem_corpus_batch import run_corpus_batch
from whymath_backend.harness.reviewer_sample_package import (
    REQUIRED_MISCONCEPTIONS,
    SampleProblem,
    allocate_quota,
    load_sample_corpus,
    main,
    render_markdown,
    select_sample,
    summarize_sample,
)

# "## 표본 01 · …" 문항 블록 헤더만 매칭(머리말 "## 표본 커버리지"와 충돌 회피).
_PROBLEM_HEADER = re.compile(r"^## 표본 \d\d ", re.MULTILINE)


def _build_corpus(tmp_path: Path) -> Path:
    """소형 결정론 코퍼스 — quad(단답/객관)·calc-value-mc(오개념 2종)·저빈도(trig/log) 포함.

    오개념 4종을 전부 실으려면 quad 객관식(factor-sign-flip·opposite-root-selected)과
    calc-value-mc(extremum-*-confused 2종)가 필요하다. 저빈도 도메인 강제 포함 검증용으로 trig·log를
    소량 넣는다.
    """
    out = tmp_path / "corpus.jsonl"
    report = run_corpus_batch(
        out_path=out,
        short_n=20,
        mc_n=8,
        sqrt_n=6,
        sqrt_mc_n=4,
        calc_extremum_n=6,
        calc_tangent_n=6,
        calc_value_n=6,
        calc_value_mc_n=6,
        calc_extremum_irr_n=6,
        exp_n=5,
        log_n=3,
        arith_n=6,
        geo_n=4,
        trig_n=2,
        arith_sum_n=0,
        geo_sum_n=0,
        trig_eq_n=0,
        seq_inductive_n=0,
        write=True,
    )
    assert report.fulfilled
    return out


def _load(tmp_path: Path) -> list[SampleProblem]:
    return load_sample_corpus(_build_corpus(tmp_path).read_text(encoding="utf-8"))


class TestLoad:
    def test_loads_all_and_hygiene(self, tmp_path: Path) -> None:
        problems = _load(tmp_path)
        assert len(problems) > 30
        # 전건 자체생성 위생(populate 규약과 정합)
        assert all(p.source_type == "자체생성" for p in problems)
        assert all(p.license == "WHYMATH_GENERATED" for p in problems)
        assert all(p.generation_type == "FULLY_GENERATED" for p in problems)

    def test_distractor_op_code_optional(self) -> None:
        """op_code 없는 distractor_map(misconception_mc·conceptual_v0 실형태)도 적재·렌더된다.

        정본 `schema.problem.DistractorEntry`의 op_code는 선택(None=미상)인데 로컬 사본이
        필수로 더 엄격해 mc/conceptual 코퍼스 표본 생성이 통째로 죽던 2026-07-29 S3-09 실측
        결함의 회귀 봉인. 렌더는 None이면 `(op: ...)` 접미를 생략해야 한다.
        """
        row = {
            "problem_id": "y",
            "slug": "s-op-none",
            "unit_codes": ["QUAD-EQ"],
            "question_format": "객관식",
            "answer_format": "정수",
            "question_text": "q",
            "answer": "1",
            "difficulty_overall": 2.0,
            "license": "WHYMATH_GENERATED",
            "source_type": "자체생성",
            "generation_type": "FULLY_GENERATED",
            "choices": ["1", "2"],
            "distractor_map": [{"choice_index": 1, "misconception_id": "exponent-zero"}],
        }
        problems = load_sample_corpus(json.dumps(row, ensure_ascii=False))
        assert problems[0].distractor_map[0].op_code is None
        md = render_markdown(problems, corpus_size=1)
        assert "오개념 `exponent-zero`" in md
        assert "(op:" not in md

    def test_rejects_non_generated_source(self) -> None:
        row = {
            "problem_id": "x",
            "slug": "s",
            "unit_codes": ["QUAD-EQ"],
            "question_format": "단답형",
            "answer_format": "정수",
            "question_text": "q",
            "answer": "1",
            "difficulty_overall": 2.0,
            "license": "WHYMATH_GENERATED",
            "source_type": "평가원",  # 위생 위반
            "generation_type": "FULLY_GENERATED",
        }
        try:
            load_sample_corpus(json.dumps(row, ensure_ascii=False))
        except ValueError as exc:
            assert "저작권 위생" in str(exc)
        else:  # pragma: no cover — 실패 시에만 도달
            raise AssertionError("자체생성 아닌 행을 거부하지 않았다")

    def test_rejects_duplicate_problem_id(self) -> None:
        row = {
            "problem_id": "dup",
            "slug": "s",
            "unit_codes": ["QUAD-EQ"],
            "question_format": "단답형",
            "answer_format": "정수",
            "question_text": "q",
            "answer": "1",
            "difficulty_overall": 2.0,
            "license": "WHYMATH_GENERATED",
            "source_type": "자체생성",
            "generation_type": "FULLY_GENERATED",
        }
        text = "\n".join([json.dumps(row, ensure_ascii=False)] * 2)
        try:
            load_sample_corpus(text)
        except ValueError as exc:
            assert "중복 problem_id" in str(exc)
        else:  # pragma: no cover
            raise AssertionError("중복 problem_id를 거부하지 않았다")


class TestAllocateQuota:
    def test_floor_one_and_sum(self) -> None:
        counts = {"A": 185, "B": 60, "C": 13, "D": 20}
        quota = allocate_quota(counts, 30)
        assert sum(quota.values()) == 30
        assert all(v >= 1 for v in quota.values())  # 모든 도메인 최소 1
        assert quota["A"] == max(quota.values())  # 최대 도메인이 최대 쿼터

    def test_deterministic(self) -> None:
        counts = {"A": 185, "B": 60, "C": 13, "D": 20, "E": 40}
        assert allocate_quota(counts, 30) == allocate_quota(counts, 30)

    def test_caps_at_available(self) -> None:
        # 도메인 C는 2문뿐 — 쿼터가 2를 넘지 못한다.
        counts = {"A": 185, "B": 2}
        quota = allocate_quota(counts, 30)
        assert quota["B"] <= 2

    def test_raises_when_n_below_domains(self) -> None:
        try:
            allocate_quota({"A": 1, "B": 1, "C": 1}, 2)
        except ValueError:
            pass
        else:  # pragma: no cover
            raise AssertionError("N < 도메인 수인데 오류를 내지 않았다")


class TestSelectSample:
    def test_exact_n(self, tmp_path: Path) -> None:
        problems = _load(tmp_path)
        sample = select_sample(problems, 30)
        assert len(sample) == 30

    def test_deterministic_byte_identical(self, tmp_path: Path) -> None:
        problems = _load(tmp_path)
        first = select_sample(problems, 30)
        second = select_sample(problems, 30)
        assert [p.problem_id for p in first] == [p.problem_id for p in second]

    def test_all_domains_present(self, tmp_path: Path) -> None:
        problems = _load(tmp_path)
        all_domains = {p.domain for p in problems}
        sample_domains = {p.domain for p in select_sample(problems, 30)}
        # 저빈도 도메인(trig·log)도 강제 포함 — 전 도메인이 표본에 있다.
        assert all_domains == sample_domains

    def test_low_frequency_domains_covered(self, tmp_path: Path) -> None:
        problems = _load(tmp_path)
        sample = select_sample(problems, 30)
        domains = {p.domain for p in sample}
        assert "TRIG-VAL" in domains
        assert "LOG-EQ" in domains

    def test_all_required_misconceptions_covered(self, tmp_path: Path) -> None:
        problems = _load(tmp_path)
        sample = select_sample(problems, 30)
        covered: set[str] = set()
        for p in sample:
            covered |= p.misconception_ids
        for mis in REQUIRED_MISCONCEPTIONS:
            assert mis in covered, f"강제 오개념 미포함: {mis}"

    def test_returns_all_when_n_exceeds_corpus(self, tmp_path: Path) -> None:
        problems = _load(tmp_path)
        sample = select_sample(problems, len(problems) + 100)
        assert len(sample) == len(problems)


class TestSummaryAndRender:
    def test_summary_no_missing(self, tmp_path: Path) -> None:
        problems = _load(tmp_path)
        sample = select_sample(problems, 30)
        coverage = summarize_sample(sample, corpus_size=len(problems))
        assert coverage.n == 30
        assert coverage.missing_required_misconceptions == []
        assert len(coverage.domain_counts) == len({p.domain for p in problems})

    def test_render_field_completeness(self, tmp_path: Path) -> None:
        problems = _load(tmp_path)
        sample = select_sample(problems, 30)
        md = render_markdown(sample, corpus_size=len(problems))
        # 머리말 필수 요소(저작권 보증·정직성 주의·서명란)
        assert "저작권 보증" in md
        assert "정직성 주의" in md
        assert "단답형에는 오개념 태그가 없다" in md
        assert "외부 저작물 대비 유사도 검사 산출물은 부재" in md
        assert "verify_status` 필드는 없다" in md
        assert "검수:{reviewer} {reviewed_on}" in md
        # 문항별 필드가 전건 채워짐
        assert len(_PROBLEM_HEADER.findall(md)) == 30
        for p in sample:
            assert p.question_text in md
            assert p.slug in md
        # 기계 ✓ + 사람 공란 분리
        assert "기계 검증 완료" in md
        assert "사람 판단" in md
        assert "- [ ] ① 발문 자연스러움" in md
        # 마지막 줄은 파싱 가능한 커버리지 JSON
        last = md.strip().splitlines()[-1]
        assert last.startswith("<!-- coverage: ") and last.endswith(" -->")
        payload = json.loads(last[len("<!-- coverage: ") : -len(" -->")])
        assert payload["n"] == 30

    def test_render_deterministic(self, tmp_path: Path) -> None:
        problems = _load(tmp_path)
        sample = select_sample(problems, 30)
        a = render_markdown(sample, corpus_size=len(problems))
        b = render_markdown(sample, corpus_size=len(problems))
        assert a == b

    def test_mc_choices_link_misconception(self, tmp_path: Path) -> None:
        problems = _load(tmp_path)
        sample = select_sample(problems, 30)
        md = render_markdown(sample, corpus_size=len(problems))
        # 적어도 한 객관식 표본의 오답↔오개념(op-code) 표시가 있다.
        assert "← 오답 · 오개념" in md
        assert "← 정답" in md

    def test_no_student_pii(self, tmp_path: Path) -> None:
        # 자체생성 코퍼스라 학생 식별자·풀이 원문이 없다 — SampleProblem 스키마에도 없음.
        problems = _load(tmp_path)
        for p in problems:
            dumped = p.model_dump()
            assert "student_id" not in dumped
            assert "user_id" not in dumped


class TestCli:
    def test_main_writes_file(self, tmp_path: Path) -> None:
        corpus = _build_corpus(tmp_path)
        out = tmp_path / "sample.md"
        rc = main(["--n", "30", "--corpus", str(corpus), "--out", str(out)])
        assert rc == 0
        assert out.exists()
        assert len(_PROBLEM_HEADER.findall(out.read_text(encoding="utf-8"))) == 30

    def test_main_missing_corpus_exit_2(self, tmp_path: Path) -> None:
        rc = main(["--corpus", str(tmp_path / "nope.jsonl"), "--out", str(tmp_path / "o.md")])
        assert rc == 2

    def test_main_deterministic_output(self, tmp_path: Path) -> None:
        corpus = _build_corpus(tmp_path)
        out1 = tmp_path / "a.md"
        out2 = tmp_path / "b.md"
        assert main(["--n", "30", "--corpus", str(corpus), "--out", str(out1)]) == 0
        assert main(["--n", "30", "--corpus", str(corpus), "--out", str(out2)]) == 0
        assert out1.read_bytes() == out2.read_bytes()


# ── 표본 회전(S2-11) — 교정 후 재판정용 신규 독립 표본 재추출 ──


def test_rotation_zero_is_identity(tmp_path: Path) -> None:
    # rotation=0은 항등 — 기존 산출물(reviewer_sample_240_v0 등) 바이트 불변 보장.
    problems = _load(tmp_path)
    base = select_sample(problems, 30)
    rot0 = select_sample(problems, 30, rotation=0)
    assert [p.problem_id for p in base] == [p.problem_id for p in rot0]


def test_rotation_deterministic_and_distinct(tmp_path: Path) -> None:
    # 같은 rotation이면 바이트 재현, 다른 rotation이면 선택이 실질 재배열(verdict-blind 재추출).
    problems = _load(tmp_path)
    r1a = select_sample(problems, 30, rotation=1)
    r1b = select_sample(problems, 30, rotation=1)
    assert [p.problem_id for p in r1a] == [p.problem_id for p in r1b]
    r0 = {p.problem_id for p in select_sample(problems, 30)}
    r1 = {p.problem_id for p in r1a}
    assert r0 != r1  # 선택키 재배열 실효
