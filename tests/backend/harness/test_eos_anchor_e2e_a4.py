"""EOS-58 — 깊이앵커 A4(중3 이차방정식·`[9수02-20]`·2022 개정) 생성 E2E 관통 실증(hermetic).

G1 차단 조건("부품은 전부 실재하는데 앵커 축으로 관통한 적이 0")을 끝내는 재실행 가능 관통:
**생성 배치 → SymPy 수용 게이트 → 코퍼스 저장 → needs_review 워크리스트 생성**을 실 CLI
(`problem_corpus_accumulate.main`)로 1회 관통하고, 각 단계 산출물을 **행 수로** 단언한다
(간접 신호 금지 — exit 0·정상 응답은 증거가 아니다).

가짜는 **LLM 호출부(provider) 하나뿐**이다(이 환경 실측: Ollama 접속 불가·클라우드 키 0):
  - 생성기 = 실물 `LLMEquivalentProblemGenerator`(프롬프트 조립·라우터 결정·JSON 파싱·
    derive-and-verify·저작권 구조 강제·GenerationLog 방출 전부 실코드)
  - 게이트 = 실물 `evaluate_equivalent_candidate`(SymPy Tier1·근 선택·solvability·위생)
  - dedup = 실물 canonical signature(시드 = **실코퍼스의 A4 문항** — EOS-52 실사 자산)
  - 저장 = 실물 JSONL 증분 append · 워크리스트 = 실물 `needs_review_worklist` 좌석
  - GenerationLog = 실물 사이드카 appender(EOS-55·즉시 flush)

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
from whymath_backend.harness.problem_corpus_accumulate import (
    default_generation_log_path,
    default_worklist_path,
    main,
)
from whymath_backend.l1.problem_bank.populate import (
    ProblemBankRecord,
    load_problem_bank_records,
)
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
    ) -> GenerationResult:
        out = self._responses[self._index]  # 소진 시 IndexError — 대본 밖 호출을 숨기지 않는다
        self._index += 1
        return GenerationResult(
            out, usage=Usage(input_tokens=50, output_tokens=120, latency_ms=42.0)
        )


def _patch_live_generator(monkeypatch: pytest.MonkeyPatch, responses: Sequence[str]) -> None:
    """`_build_live_generator`의 provider 좌석만 대본으로 교체 — 나머지 조립은 실물 그대로.

    main()의 배선(인자 파싱→genlog 싱크 생성→생성기 주입→run→워크리스트 기록)을 전부
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
        """A4 앵커 1회 관통 — 각 단계 산출물을 행 수로 단언(생성 5→수용 1→비수용 4→genlog 5)."""
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
        assert report["review_outcomes_count"] == 4  # 비수용 4건 — 워크리스트 재료
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

        # ── needs_review 워크리스트(사이드카 기본 ON) — 비수용 4건·검수필요 최상단 ──
        worklist = default_worklist_path(out).read_text(encoding="utf-8")
        assert "- 총 생성 outcome: 5 · 비수용(워크리스트) 4" in worklist
        assert "- 상태별: 검수필요 1 · 게이트거부 1 · 과유사거부 1 · 생성실패 1" in worklist
        assert "## 1. [needs_review]" in worklist  # 우선순위 최상단 = 사람 판단 대기
        assert "- [ ] 수용(코퍼스 편입) / [ ] 반려 / [ ] 임계값 재검토 대상" in worklist

    def test_worklist_out_flag_overrides_sidecar_and_survives_no_progress(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """--worklist-out 경로 관통 + 무진전(exit 1) 회차에도 워크리스트가 남는다(증거 보존)."""
        _patch_live_generator(monkeypatch, [_R_NON_JSON])
        out = tmp_path / "acc.jsonl"
        custom = tmp_path / "검수" / "worklist.md"
        code = main(["--out", str(out), "--n", "1", "--worklist-out", str(custom)])
        assert code == 1  # 전건 generation_failed → 무진전(기존 계약 그대로)
        capsys.readouterr()
        assert not default_worklist_path(out).exists()  # 지정 경로만 쓴다
        content = custom.read_text(encoding="utf-8")
        assert "- 상태별: 검수필요 0 · 게이트거부 0 · 과유사거부 0 · 생성실패 1" in content

    def test_worklist_written_even_when_everything_accepted(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """전건 수용 회차도 워크리스트를 기록 — '관측했고 0건'과 '미기록'을 구분(미측정≠0)."""
        _patch_live_generator(monkeypatch, [_R_ACCEPT])
        out = tmp_path / "acc.jsonl"
        code = main(
            ["--out", str(out), "--n", "1", "--standard-code", _A4_STANDARD, "--difficulty", "2.5"]
        )
        assert code == 0
        capsys.readouterr()
        content = default_worklist_path(out).read_text(encoding="utf-8")
        assert "- 총 생성 outcome: 1 · 비수용(워크리스트) 0" in content

    def test_report_json_carries_review_outcomes_count(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """리포트 JSON에 비수용 카운트가 실린다 — 워크리스트 재료의 존재를 리포트가 말한다."""
        _patch_live_generator(monkeypatch, [_R_ACCEPT, _R_NON_JSON])
        out = tmp_path / "acc.jsonl"
        code = main(
            ["--out", str(out), "--n", "2", "--standard-code", _A4_STANDARD, "--difficulty", "2.5"]
        )
        assert code == 0
        report = json.loads(capsys.readouterr().out)
        assert report["review_outcomes_count"] == 1
        assert report["outcome_counts"]["generation_failed"] == 1


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
        만들면 그것이 날조다 — 산출 디렉터리에 세 사이드카(코퍼스·genlog·worklist) 외의
        파일이 생기지 않음을 동결한다.
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
