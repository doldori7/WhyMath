"""EOS-58 — 깊이앵커 A4(중3 이차방정식·`[9수02-20]`·2022 개정) 생성 E2E 관통 실증(hermetic).

G1 차단 조건("부품은 전부 실재하는데 앵커 축으로 관통한 적이 0")을 끝내는 재실행 가능 관통:
**생성 배치 → SymPy 수용 게이트 → 코퍼스 저장 → needs_review 검수 큐/워크리스트**를 실 CLI
(`problem_corpus_accumulate.main`)로 관통하고, 각 단계 산출물을 **행 수로** 단언한다
(간접 신호 금지 — exit 0·정상 응답은 증거가 아니다).

가짜는 **LLM 호출부(provider) 하나뿐**이다(이 환경 실측: Ollama 접속 불가·클라우드 키 0):
  - 생성기 = 실물 `LLMEquivalentProblemGenerator`(프롬프트 조립·라우터 결정·JSON 파싱·
    derive-and-verify·저작권 구조 강제·GenerationLog 방출 전부 실코드)
  - 게이트 = 실물 `evaluate_equivalent_candidate`(SymPy Tier1·근 선택·solvability·위생)
  - dedup = 실물 canonical signature(시드 = **실코퍼스의 A4 문항** — EOS-52 실사 자산)
  - 저장 = 실물 JSONL 증분 append · 검수 큐 = 실물 `needs_review_worklist` 내구 계층
  - GenerationLog = 실물 사이드카 appender(EOS-55·즉시 flush)

검수 큐 2층 계약(codex P1-1/P1-2/P2 상환 — `TestReviewQueueDurability`가 동결):
  ① 비수용 outcome 발생 **즉시** `<out>.review.jsonl`에 행 append+flush — 배치 도중 중단돼도
    그때까지의 행이 디스크에 실재(P2)
  ② 워크리스트 md는 큐 **전체**의 렌더 뷰 — 2회차 실행 후 양 회차 항목 공존(P1-2)
  ③ 전건 수용 회차가 기존 큐를 비우지 않음(P1-2)
  ④ 큐 행·워크리스트 항목에 후보 **본문**(문항·정답·검산 조건)이 실림 — slug만으로 해석
    불가하던 검수 불능 해소(P1-1)

대본 5응답이 outcome 6종 중 5종을 정확히 1건씩 유도한다(사전 프로브 실측 2026-08-30):
  ① 신규 수용(accepted_stored) ② 다근·선택 미명시 → 검수필요(needs_review)
  ③ 오답 → SymPy Tier1 fail(rejected_gate) ④ 시드 A4 문항과 같은 구조(rejected_duplicate)
  ⑤ 비JSON → 파싱 실패(generation_failed)
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path

import pytest

from whymath_backend.harness import problem_corpus_accumulate
from whymath_backend.harness.needs_review_worklist import load_review_queue_jsonl
from whymath_backend.harness.problem_corpus_accumulate import (
    default_generation_log_path,
    default_review_queue_path,
    default_worklist_path,
    main,
)
from whymath_backend.l1.problem_bank.populate import (
    ProblemBankRecord,
    load_problem_bank_records,
)
from whymath_backend.l3.equivalent.acceptance import EquivalenceSpec
from whymath_backend.l3.equivalent.canonicalize import canonical_signature
from whymath_backend.l3.equivalent.llm_generator import LLMEquivalentProblemGenerator
from whymath_backend.l3.models import GenerationResult, RoutingDecision, Usage
from whymath_backend.l3.pregenerate.provenance_bridge import load_generation_logs_jsonl
from whymath_backend.schema.enums import Subject
from whymath_backend.schema.provenance import restore_input_snapshot

# ── 앵커 A4 상수(EOS-51 검증설계서 §앵커·EOS-52 실사) ──────────────────────
_A4_STANDARD = "[9수02-20]"  # 중3 이차방정식 — 단일 성취기준(2022 개정)
_A4_TOPIC = "중3 이차방정식 — 두 근 중 더 큰 근을 구하는 형태(답 하나)"
_A4_DIFFICULTY = "2.5"  # 코퍼스 quad 밴드 스펙 난이도(problem_corpus_batch 동일)

# 실코퍼스(v0) — A4 시드 자산의 원천. 부재 시 skip(test_corpus_quality 관례).
_REPO_ROOT = Path(__file__).resolve().parents[3]
_V0_CORPUS = _REPO_ROOT / "data" / "corpus" / "problem_bank_generated_v0" / "problems.jsonl"


# ── 대본 응답(가짜는 이 대본을 돌려주는 provider 하나뿐) ───────────────────
def _response(payload: dict[str, object]) -> str:
    return json.dumps(payload, ensure_ascii=False)


_R_ACCEPT = _response(
    {
        "question_text": "이차방정식 x^2 - 40x + 391 = 0 의 두 근 중 더 큰 근을 구하시오.",
        "answer": "23",
        "answer_explanation": (
            "인수분해하면 (x-17)(x-23)=0 이므로 두 근은 17과 23이고, 더 큰 근은 23이다."
        ),
        "conditions": "x**2 - 40*x + 391 = 0",
        "answer_map": {"x": "23"},
        "answer_selection": "largest",
        "difficulty_overall": 2.5,
        "unit_codes": ["QUAD-EQ"],
        "answer_format": "자연수",
        "achievement_standard_codes": [_A4_STANDARD],
    }
)

# 다근(±11)인데 근 선택 미명시 — Tier1 pass여도 유일성 미확정 → verified→unverified 강등
# (S2-i 프로브) → 게이트 `검수필요` → orchestrator `needs_review`(사람 검수 큐).
_R_NEEDS_REVIEW = _response(
    {
        "question_text": "이차방정식 x^2 - 121 = 0 을 만족하는 자연수 x 를 구하시오.",
        "answer": "11",
        "answer_explanation": "x^2 = 121 에서 x 는 11 또는 -11 이고, 자연수는 11이다.",
        "conditions": "x**2 - 121 = 0",
        "answer_map": {"x": "11"},
        "difficulty_overall": 2.5,
        "unit_codes": ["QUAD-EQ"],
        "answer_format": "자연수",
        "achievement_standard_codes": [_A4_STANDARD],
    }
)

# 두 번째 검수필요 대본(±13) — 회차 간 누적 계약(P1-2)의 2회차 재료(다른 payload sha).
_R_NEEDS_REVIEW_2 = _response(
    {
        "question_text": "이차방정식 x^2 - 169 = 0 을 만족하는 자연수 x 를 구하시오.",
        "answer": "13",
        "answer_explanation": "x^2 = 169 에서 x 는 13 또는 -13 이고, 자연수는 13이다.",
        "conditions": "x**2 - 169 = 0",
        "answer_map": {"x": "13"},
        "difficulty_overall": 2.5,
        "unit_codes": ["QUAD-EQ"],
        "answer_format": "자연수",
        "achievement_standard_codes": [_A4_STANDARD],
    }
)

# 오답(5는 x²-4x+3=0의 근이 아님·근은 1,3) — SymPy Tier1 fail → rejected_gate.
# answer_selection을 일부러 뺀다: 있으면 생성기 derive-and-verify가 조립 단계에서 거부해
# generation_failed가 되므로(원천 거부), *게이트*의 반려 축을 보려면 게이트까지 흘려야 한다.
_R_GATE_REJECT = _response(
    {
        "question_text": "이차방정식 x^2 - 4x + 3 = 0 의 두 근 중 더 큰 근을 구하시오.",
        "answer": "5",
        "answer_explanation": "두 근을 구한 뒤 더 큰 값을 답한다.",
        "conditions": "x**2 - 4*x + 3 = 0",
        "answer_map": {"x": "5"},
        "difficulty_overall": 2.5,
        "unit_codes": ["QUAD-EQ"],
        "answer_format": "자연수",
        "achievement_standard_codes": [_A4_STANDARD],
    }
)

_R_NON_JSON = "이번 턴은 유효한 JSON 응답이 아님)))"


def _dup_of_seed(seed: ProblemBankRecord) -> str:
    """시드 A4 문항과 **구조가 같은**(발문만 다른) 대본 응답 — 회차 간 dedup의 실증 재료.

    slug는 내용 해시라 시드와 다르게 나온다 — 즉 signature dedup이 없으면 그대로 append되는
    판박이다. 게이트는 통과하고(시드 데이터는 검증 완료 재료) 구조 dedup에서만 잡혀야 한다.
    """
    var, val = next(iter(seed.verify.answer_map.items()))
    assert seed.verify.answer_selection is not None  # 픽스처가 선택 있는 시드를 고른다
    return _response(
        {
            "question_text": f"방정식 {seed.verify.conditions} 의 해 가운데 더 큰 것을 쓰시오.",
            "answer": val,
            "answer_explanation": "두 해를 비교하여 더 큰 값을 답한다.",
            "conditions": seed.verify.conditions,
            "answer_map": {var: val},
            "answer_selection": seed.verify.answer_selection,
            "difficulty_overall": 2.5,
            "unit_codes": ["QUAD-EQ"],
            "achievement_standard_codes": [_A4_STANDARD],
        }
    )


class ScriptedProvider:
    """대본 provider — 유일한 대역(LLM 호출부). 순서 소비·소진 시 IndexError(조용한 순환 금지)."""

    def __init__(self, responses: Sequence[str]) -> None:
        self._responses = list(responses)
        self._index = 0

    async def generate(
        self,
        prompt: str,
        system: str,
        decision: RoutingDecision,
        *,
        images: Sequence[str] | None = None,
        temperature: float | None = None,
        json_schema: Mapping[str, object] | None = None,
        seed: int | None = None,  # EOS-73 — LLMProvider 계약 정합(대역은 시드를 쓰지 않는다)
    ) -> GenerationResult:
        out = self._responses[self._index]  # 소진 시 IndexError — 대본 밖 호출을 숨기지 않는다
        self._index += 1
        return GenerationResult(
            out, usage=Usage(input_tokens=50, output_tokens=120, latency_ms=42.0)
        )


def _patch_live_generator(monkeypatch: pytest.MonkeyPatch, responses: Sequence[str]) -> None:
    """`_build_live_generator`의 provider 좌석만 대본으로 교체 — 나머지 조립은 실물 그대로.

    main()의 배선(인자 파싱→genlog/검수 큐 싱크 생성→생성기 주입→run→워크리스트 렌더)을 전부
    실측하기 위해 main이 넘겨주는 `topic_hint`·`generation_log_sink`를 그대로 실 생성기에
    잇는다(라이브 조립 `_build_live_generator`와 동일 구성·provider만 대본).
    """
    from whymath_backend.l4.misconception.catalog import CATALOG_BY_ID  # 조성 루트 미러

    def _build(
        topic_hint: str, *, generation_log_sink: object = None
    ) -> LLMEquivalentProblemGenerator:
        return LLMEquivalentProblemGenerator(
            ScriptedProvider(responses),  # type: ignore[arg-type]
            misconception_catalog={mid: m.name_kr for mid, m in CATALOG_BY_ID.items()},
            topic_hint=topic_hint,
            subject=Subject.공통,
            slug_prefix="wm-gen-a4",
            generation_log_sink=generation_log_sink,  # type: ignore[arg-type]
        )

    monkeypatch.setattr(problem_corpus_accumulate, "_build_live_generator", _build)


@pytest.fixture
def a4_seed(tmp_path: Path) -> Path:
    """실코퍼스 v0에서 A4(`[9수02-20]`) 문항만 필터한 시드 JSONL — 앵커 기존 자산 그대로."""
    if not _V0_CORPUS.exists():
        pytest.skip("생성 코퍼스 미존재(data/corpus/problem_bank_generated_v0/problems.jsonl)")
    lines = [
        line
        for line in _V0_CORPUS.read_text(encoding="utf-8").splitlines()
        if line.strip() and _A4_STANDARD in json.loads(line).get("achievement_standard_codes", [])
    ]
    assert len(lines) >= 100  # EOS-52 실사 시점 184건 — 대폭 축소되면 앵커 자산 회귀
    seed_path = tmp_path / "a4_seed.jsonl"
    seed_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return seed_path


def _a4_args(out: Path, *, n: int = 1) -> list[str]:
    """A4 앵커 스펙 인자(대본과 정합) — 기본 스펙([10공수1-02-02])과 어긋나면 점수가 강등된다."""
    return [
        "--out",
        str(out),
        "--n",
        str(n),
        "--standard-code",
        _A4_STANDARD,
        "--difficulty",
        _A4_DIFFICULTY,
    ]


def _first_selectable_seed(records: Sequence[ProblemBankRecord]) -> ProblemBankRecord:
    """근 선택이 명시되고 정규형 signature가 있는 첫 시드 — dup 대본의 원본."""
    for record in records:
        if record.verify.answer_selection is None:
            continue
        if canonical_signature(record.verify.conditions, record.verify.answer_selection):
            return record
    raise AssertionError("A4 시드에 근 선택·정규형 signature를 갖춘 문항이 없음(자산 회귀)")


class TestAnchorA4EndToEnd:
    def test_full_pipe_generation_gate_store_worklist(
        self,
        tmp_path: Path,
        a4_seed: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """A4 앵커 1회 관통 — 각 단계 산출물을 행 수로 단언(생성 5→수용 1→큐 4행→genlog 5)."""
        seed_records = load_problem_bank_records(a4_seed)
        seed0 = _first_selectable_seed(seed_records)
        seed_bytes_before = a4_seed.read_bytes()

        # 사전 검증(자기검증 스텝) — 대본 구조와 시드의 관계가 전제대로인지 실측으로 고정:
        # 수용 대본은 시드에 없는 신구조여야 하고, dup 대본은 시드 실재 구조여야 한다.
        seed_sigs = {
            canonical_signature(r.verify.conditions, r.verify.answer_selection)
            for r in seed_records
        }
        assert canonical_signature("x**2 - 40*x + 391 = 0", "largest") not in seed_sigs
        assert (
            canonical_signature(seed0.verify.conditions, seed0.verify.answer_selection) in seed_sigs
        )

        _patch_live_generator(
            monkeypatch,
            [_R_ACCEPT, _R_NEEDS_REVIEW, _R_GATE_REJECT, _dup_of_seed(seed0), _R_NON_JSON],
        )
        out = tmp_path / "a4_accumulated.jsonl"
        code = main(
            [
                "--seed",
                str(a4_seed),
                "--out",
                str(out),
                "--n",
                "5",
                "--standard-code",
                _A4_STANDARD,
                "--difficulty",
                _A4_DIFFICULTY,
                "--topic-hint",
                _A4_TOPIC,
            ]
        )
        assert code == 0  # 신규 수용 ≥1 — 무진전 아님

        # ── 배치 리포트(stdout JSON) — outcome 6종 중 5종이 정확히 1건씩 ──
        report = json.loads(capsys.readouterr().out)
        assert report["attempted"] == 5
        assert report["outcome_counts"] == {
            "accepted_stored": 1,
            "needs_review": 1,
            "rejected_gate": 1,
            "rejected_duplicate": 1,
            "generation_failed": 1,
        }
        assert report["accepted"] == 1
        assert report["appended"] == 1
        assert report["review_outcomes_count"] == 4  # 이 회차 비수용 4건
        assert report["seed_records"] == len(seed_records)  # A4 시드 전량이 index에 실림

        # ── 저장(코퍼스 JSONL) — 실제 행 수 1 + 앵커 메타(2022 개정·자체생성) 라운드트립 ──
        out_lines = [line for line in out.read_text(encoding="utf-8").splitlines() if line]
        assert len(out_lines) == 1
        stored_raw = json.loads(out_lines[0])
        assert stored_raw["achievement_standard_codes"] == [_A4_STANDARD]
        assert stored_raw["curriculum_version"] == "2022_REVISION"
        assert stored_raw["valid_from_year"] == 2022
        assert stored_raw["source_type"] == "자체생성"  # 저작권 구조적 강제(LLM 주장 무관)
        assert stored_raw["license"] == "WHYMATH_GENERATED"
        assert stored_raw["verify"]["conditions"] == "x**2 - 40*x + 391 = 0"
        assert stored_raw["verify"]["answer_selection"] == "largest"
        stored = load_problem_bank_records(out)
        assert len(stored) == 1  # 로더 라운드트립도 1행
        assert a4_seed.read_bytes() == seed_bytes_before  # 시드는 불변(증분 append 원칙)

        # ── GenerationLog 사이드카(EOS-55) — LLM 호출 1건당 1행·전 5행(실패 호출 포함) ──
        genlogs, genlog_errors = load_generation_logs_jsonl(default_generation_log_path(out))
        assert genlog_errors == []
        assert len(genlogs) == 5
        assert [log.success for log in genlogs] == [True, True, True, True, False]
        # 앵커 결속 — 성공 호출 전건의 입력 스냅샷이 A4 성취기준을 기록(재현 계약 위에서).
        for log in genlogs[:4]:
            restored = restore_input_snapshot(log)
            assert restored["kind"] == "l3.equivalent.llm_generate"
            assert restored["spec"]["achievement_standard_codes"] == [_A4_STANDARD]
        # CU 조인 정체성(EOS-54/55 축) — 저장된 문항 slug가 genlog cu_slug에 실재.
        cu_slugs = {log.cu_slug for log in genlogs if log.cu_slug is not None}
        assert stored[0].slug in cu_slugs

        # ── 내구 검수 큐(codex P1-1/P2) — 비수용 1건=1행·후보 본문 전문 동반 ──
        queue_entries, queue_errors = load_review_queue_jsonl(default_review_queue_path(out))
        assert queue_errors == []
        assert len(queue_entries) == 4
        assert [entry.status for entry in queue_entries] == [
            "needs_review",
            "rejected_gate",
            "rejected_duplicate",
            "generation_failed",
        ]  # 발생 순서 그대로(append-only)
        needs_review_row = queue_entries[0]
        assert needs_review_row.candidate_payload is not None
        assert (
            needs_review_row.candidate_payload["question_text"]
            == "이차방정식 x^2 - 121 = 0 을 만족하는 자연수 x 를 구하시오."
        )  # 검수자가 행만으로 문항을 본다(P1-1)
        assert needs_review_row.candidate_payload["verify"]["conditions"] == "x**2 - 121 = 0"
        assert needs_review_row.payload_sha256 is not None
        assert needs_review_row.source_line == 1  # 로더가 실제 줄 번호 주입(행 참조 재료)
        failed_row = queue_entries[3]
        assert failed_row.candidate_payload is None  # 후보 미조립 — 본문 날조 금지
        assert failed_row.reasons  # 대신 실패 사유가 말한다
        assert all(entry.recorded_at is not None for entry in queue_entries)  # append 스탬프
        assert {entry.run_id for entry in queue_entries} == {report["run_id"]}  # 리포트 조인 축

        # ── 워크리스트(큐 전체의 렌더 뷰) — 항목 4·검수필요 최상단·본문 동반(계약 ④) ──
        worklist = default_worklist_path(out).read_text(encoding="utf-8")
        assert "누적 행 4 · 항목(묶음) 4 · 로드 실패 0" in worklist
        assert "- 상태별(묶음): 검수필요 1 · 게이트거부 1 · 과유사거부 1 · 생성실패 1" in worklist
        assert "## 1. [needs_review]" in worklist  # 우선순위 최상단 = 사람 판단 대기
        assert "출현 1회" in worklist
        assert "- 문항: 이차방정식 x^2 - 121 = 0 을 만족하는 자연수 x 를 구하시오." in worklist
        assert "- 정답: 11" in worklist  # 계약 ④ — 체크박스가 실사용 가능(본문이 실림)
        assert "- 행 참조: #1" in worklist
        assert "- [ ] 수용(코퍼스 편입) / [ ] 반려 / [ ] 임계값 재검토 대상" in worklist

    def test_worklist_out_flag_overrides_sidecar_and_survives_no_progress(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """--worklist-out 경로 관통 + 무진전(exit 1) 회차에도 큐 행·워크리스트가 남는다."""
        _patch_live_generator(monkeypatch, [_R_NON_JSON])
        out = tmp_path / "acc.jsonl"
        custom = tmp_path / "검수" / "worklist.md"
        code = main(["--out", str(out), "--n", "1", "--worklist-out", str(custom)])
        assert code == 1  # 전건 generation_failed → 무진전(기존 계약 그대로)
        capsys.readouterr()
        assert not default_worklist_path(out).exists()  # 뷰는 지정 경로에만 쓴다
        # 큐 저장소는 뷰 경로와 무관하게 항상 <out>.review.jsonl(누적의 단일 원천).
        queue_entries, queue_errors = load_review_queue_jsonl(default_review_queue_path(out))
        assert queue_errors == []
        assert len(queue_entries) == 1
        content = custom.read_text(encoding="utf-8")
        assert "누적 행 1 · 항목(묶음) 1 · 로드 실패 0" in content
        assert "- 상태별(묶음): 검수필요 0 · 게이트거부 0 · 과유사거부 0 · 생성실패 1" in content
        assert "- 본문: (payload 없음 — 후보 미조립·사유만 기록)" in content

    def test_worklist_written_even_when_everything_accepted(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """전건 수용 첫 회차도 워크리스트를 기록 — '관측했고 0건'과 '미기록'을 구분(미측정≠0)."""
        _patch_live_generator(monkeypatch, [_R_ACCEPT])
        out = tmp_path / "acc.jsonl"
        code = main(
            ["--out", str(out), "--n", "1", "--standard-code", _A4_STANDARD, "--difficulty", "2.5"]
        )
        assert code == 0
        capsys.readouterr()
        content = default_worklist_path(out).read_text(encoding="utf-8")
        assert "누적 행 0 · 항목(묶음) 0 · 로드 실패 0" in content

    def test_report_json_carries_review_outcomes_count(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """리포트 JSON에 비수용 카운트·run_id가 실린다 — 큐 행과의 조인 축을 리포트가 말한다."""
        _patch_live_generator(monkeypatch, [_R_ACCEPT, _R_NON_JSON])
        out = tmp_path / "acc.jsonl"
        code = main(
            ["--out", str(out), "--n", "2", "--standard-code", _A4_STANDARD, "--difficulty", "2.5"]
        )
        assert code == 0
        report = json.loads(capsys.readouterr().out)
        assert report["review_outcomes_count"] == 1
        assert report["outcome_counts"]["generation_failed"] == 1
        assert isinstance(report["run_id"], str) and report["run_id"]


class TestReviewQueueDurability:
    """검수 큐 내구 계약(codex P1-1/P1-2/P2) — 즉시 영속·회차 누적·본문 동반을 동결."""

    def test_rows_persist_immediately_when_batch_crashes_midway(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """계약 ①(P2) — outcome 발생 즉시 행이 디스크에 실재: 배치 중단 시 그때까지 보존.

        1·2회차는 생성 실패(None), 3회차에 provider 크래시를 재현 — 배치는 죽지만 큐에는
        앞선 2행이 이미 flush돼 있어야 한다(종료 일괄 기록이면 0행 — genlog와 같은 규약).
        """

        class _CrashOnThirdGenerator:
            """1·2회차 None(생성 실패) → 3회차 RuntimeError — 장기 라이브 배치 중단 재현."""

            def __init__(self) -> None:
                self.calls = 0

            def generate(self, spec: EquivalenceSpec) -> None:
                self.calls += 1
                if self.calls >= 3:
                    raise RuntimeError("배치 중단(테스트) — 프로세스 사망 재현")
                return None

        monkeypatch.setattr(
            problem_corpus_accumulate,
            "_build_live_generator",
            lambda topic_hint, **kwargs: _CrashOnThirdGenerator(),
        )
        out = tmp_path / "acc.jsonl"
        with pytest.raises(RuntimeError):
            main(_a4_args(out, n=3))
        # 배치는 죽었지만(워크리스트 렌더 미도달) 큐 행 2건은 이미 디스크에 있다.
        assert not default_worklist_path(out).exists()
        queue_entries, queue_errors = load_review_queue_jsonl(default_review_queue_path(out))
        assert queue_errors == []
        assert len(queue_entries) == 2
        assert all(entry.status == "generation_failed" for entry in queue_entries)

    def test_second_run_accumulates_both_runs_in_worklist(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """계약 ②(P1-2) — 같은 --out 2회차 실행 후 워크리스트에 양 회차 항목이 공존한다."""
        out = tmp_path / "acc.jsonl"
        _patch_live_generator(monkeypatch, [_R_NEEDS_REVIEW])
        assert main(_a4_args(out)) == 1  # 회차 1 — 검수필요 1(무진전)
        report1 = json.loads(capsys.readouterr().out)
        _patch_live_generator(monkeypatch, [_R_NEEDS_REVIEW_2])
        assert main(_a4_args(out)) == 1  # 회차 2 — 다른 검수필요 1
        report2 = json.loads(capsys.readouterr().out)

        queue_entries, queue_errors = load_review_queue_jsonl(default_review_queue_path(out))
        assert queue_errors == []
        assert len(queue_entries) == 2  # 회차 간 append 누적(덮어쓰기 없음)
        assert {entry.run_id for entry in queue_entries} == {
            report1["run_id"],
            report2["run_id"],
        }  # 서로 다른 회차의 행이 공존
        worklist = default_worklist_path(out).read_text(encoding="utf-8")
        assert "누적 행 2 · 항목(묶음) 2 · 로드 실패 0" in worklist
        assert "x^2 - 121 = 0" in worklist  # 회차 1 항목 생존
        assert "x^2 - 169 = 0" in worklist  # 회차 2 항목 동반

    def test_all_accepted_run_does_not_wipe_existing_queue(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """계약 ③(P1-2) — 전건 수용 회차가 기존 큐를 빈 워크리스트로 교체하지 않는다."""
        out = tmp_path / "acc.jsonl"
        _patch_live_generator(monkeypatch, [_R_NEEDS_REVIEW])
        assert main(_a4_args(out)) == 1  # 회차 1 — 검수필요 1건 적재
        capsys.readouterr()
        _patch_live_generator(monkeypatch, [_R_ACCEPT])
        assert main(_a4_args(out)) == 0  # 회차 2 — 전건 수용
        capsys.readouterr()

        queue_entries, _ = load_review_queue_jsonl(default_review_queue_path(out))
        assert len(queue_entries) == 1  # 수용 회차는 큐에 아무것도 안 쓰고, 지우지도 않는다
        worklist = default_worklist_path(out).read_text(encoding="utf-8")
        assert "누적 행 1 · 항목(묶음) 1 · 로드 실패 0" in worklist
        assert "## 1. [needs_review]" in worklist  # 이전 회차 미해결 항목이 그대로 남는다
        assert "- 문항: 이차방정식 x^2 - 121 = 0 을 만족하는 자연수 x 를 구하시오." in worklist

    def test_same_candidate_reappearance_grouped_with_occurrence_count(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """같은 후보 재출현은 payload sha로 묶여 출현 횟수 표기 — 행은 전부 보존(관측)."""
        out = tmp_path / "acc.jsonl"
        for _ in range(2):  # 같은 검수필요 후보를 두 회차에 걸쳐 재출현시킨다
            _patch_live_generator(monkeypatch, [_R_NEEDS_REVIEW])
            assert main(_a4_args(out)) == 1
            capsys.readouterr()
        queue_entries, _ = load_review_queue_jsonl(default_review_queue_path(out))
        assert len(queue_entries) == 2  # 행(관측)은 2건 전부 보존
        assert queue_entries[0].payload_sha256 == queue_entries[1].payload_sha256
        worklist = default_worklist_path(out).read_text(encoding="utf-8")
        assert "누적 행 2 · 항목(묶음) 1 · 로드 실패 0" in worklist  # 뷰에서는 1항목으로 묶임
        assert "출현 2회" in worklist
        assert "- 행 참조: #1, #2" in worklist


class TestGenerationLogAnchorHonesty:
    """관통 구간의 계측 정직성 — 없는 이벤트를 지어내지 않는다(EOS-54 HIT 판단의 테스트 축)."""

    def test_no_review_timer_events_are_fabricated_in_this_span(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """생성~워크리스트 구간은 검수 타이머(HIT) 이벤트를 **쓰지 않는다** — 0건이 정직.

        HIT 이벤트(EOS-54)는 검수자 착석(started/finished/aborted·reviewer_id 필수) 계약이다.
        워크리스트 *생성*은 기계 산출이지 사람 착석이 아니므로, 이 관통이 타이머 JSONL을
        만들면 그것이 날조다 — 전건 수용 회차의 산출 디렉터리에 사이드카(코퍼스·genlog·
        worklist) 외의 파일이 생기지 않음을 동결한다(검수 큐 review.jsonl은 비수용 발생
        시에만 생긴다 — 이 회차는 비수용 0이라 부재가 정직).
        """
        _patch_live_generator(monkeypatch, [_R_ACCEPT])
        out = tmp_path / "acc.jsonl"
        code = main(
            ["--out", str(out), "--n", "1", "--standard-code", _A4_STANDARD, "--difficulty", "2.5"]
        )
        assert code == 0
        capsys.readouterr()
        produced = sorted(p.name for p in tmp_path.iterdir())
        assert produced == ["acc.genlog.jsonl", "acc.jsonl", "acc.worklist.md"]
