"""notation_coverage(NS-03 표기 커버리지 게이트) hermetic 상시 회귀 — LLM 0·DB 0.

리포 커밋 코퍼스·manifest·베이스라인으로 `main()`을 실제 완주해 게이트 판정(exit 0/1)까지
검증한다:
  ① 추출 순수 로직 — 한글 프로즈 오탐 0(핵심)·매크로/글리프 추출 정확성.
  ② 지원 집합 파생 — manifest 정본 + KaTeX 실증 allowlist·*실증 없는 심볼 미추가* 봉인.
  ③ 본판정: 실제 코퍼스 + 커밋된 베이스라인으로 exit 0(CI 상시 회귀 — backend pytest 잡 자동 포함).
  ④ 변별력 대조군: `--control-empty-support`(지원 공집합)면 지원 토큰이 전부 신규 누락으로
     실측돼 exit 1 — 실패 상태에서 실제로 실패 신호를 내는 검출기임을 상시 봉인
     ("변별력 없는 검증 스텝 금지"·test_coach_prose_leak_eval 선례).
  ⑤ 합성 신규 누락(tmp_path 코퍼스에 미지원 심볼 주입) → exit 1·베이스라인 등재 시 exit 0·
     해소 회계·부재/파싱 실패의 명시 실패(침묵 skip 금지).
  ⑥ [NS-05] 이론 코퍼스 5종(concept_content K-12·대학·atom_graph·misconceptions·
     concept_graph) 스캔 범위 — 합성 이론 레코드 주입 변별력·ID/코드 필드 미스캔·명시 실패,
     실 코퍼스에서 이론 레코드가 실측되고 신규 누락 0(커밋 베이스라인과 일치)임을 동결.

CI 상시 배선(ci.yml 게이트 스텝 추가)은 ARCH-14 소유 — 여기서는 pytest 상시 회귀로 심는다.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from whymath_backend.l3.notation_coverage import (
    # KATEX_PROVEN_MACROS는 더 이상 여기서 단언하지 않는다 — allowlist↔근거 매핑의 파생 관계는
    # test_notation_evidence_integrity.py가 전담한다(MATH-02 ③, 커버리지 손실 0).
    KNOWN_GAPS_OUT_OF_SCOPE,
    extract_macros,
    extract_math_glyphs,
    is_math_glyph,
    load_baseline,
    load_support_set,
    main,
    proven_macros,
)

# tests/backend/l3/ → parents[3] = 레포 루트(test_notation_contract.py와 동일 기준).
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_MANIFEST = _PROJECT_ROOT / "data" / "notation_support_manifest.json"
_BASELINE = _PROJECT_ROOT / "data" / "notation_missing_baseline.json"
_REAL_PROBLEMS = _PROJECT_ROOT / "data" / "corpus" / "problem_bank_v1" / "problems.jsonl"


# ──────────────────────────────────────────────────────────────────────────
# 합성 코퍼스 헬퍼 — 실제 코퍼스 1레코드를 변형(스키마·저작권 위생 검증을 그대로 통과)
# ──────────────────────────────────────────────────────────────────────────
def _write_theory_corpora(root: Path, *, explanation: str, id_token: str = "SYN") -> None:
    """합성 이론 코퍼스 5종(THEORY_CORPORA 명세의 최소 유효 구조·레코드 1건씩).

    이론 코퍼스는 게이트 스캔 범위의 필수 입력이라(NS-05 — 부재 시 명시 실패) 합성 루트에도
    항상 함께 쓴다. `id_token`은 code/mis_id/src_id 등 **미스캔 필드**에만 들어간다 —
    표기 토큰을 심어도 게이트가 읽지 않아야 하는 자리다.
    """
    content = {
        "content": [
            {
                "code": f"{id_token}-C1",
                "name": "합성 개념",
                "explanation": explanation,
                "metaphor": "합성 비유.",
                "misconception": "합성 오개념.",
                "formal_definition_internal": "합성 정의.",
                "accepted_expressions": "합성 허용 표현.",
                "flashcards": [{"front": "앞면 질문.", "back": "뒷면 답."}],
            }
        ]
    }
    for dirname in ("concept_content_v1", "concept_content_university_v1"):
        d = root / dirname
        d.mkdir(parents=True)
        (d / "content.json").write_text(json.dumps(content, ensure_ascii=False), encoding="utf-8")
    atom = root / "atom_graph_v1"
    atom.mkdir(parents=True)
    (atom / "graph.json").write_text(
        json.dumps(
            {
                "concepts": [
                    {
                        "code": f"{id_token}-A1",
                        "name": "합성 원자",
                        "socratic": "왜 그런지 스스로 설명해 보자.",
                        "diagnostic_item": "합성 진단 문항.",
                    }
                ],
                "edges": [],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    mis = root / "misconceptions_v1"
    mis.mkdir(parents=True)
    (mis / "misconceptions.json").write_text(
        json.dumps(
            {
                "misconceptions": [
                    {
                        "mis_id": f"{id_token}M1",
                        "canonical_statement": "합성 오개념 진술.",
                        "student_wrong_thinking": "합성 오류 사고.",
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    graph = root / "concept_graph_v1"
    graph.mkdir(parents=True)
    (graph / "concepts.jsonl").write_text(
        json.dumps(
            {"src_id": f"{id_token}-G1", "name_ko": "합성 개념", "metaphor": "합성 비유."},
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )


def _write_synthetic_root(
    tmp_path: Path,
    question_text: str,
    *,
    theory_explanation: str = "합성 이론 서술(표기 없음).",
    theory_id_token: str = "SYN",
) -> Path:
    """tmp_path에 합성 코퍼스 루트 구성 — 문항 1건(주입 question_text) + 무결 수식 1건 +
    이론 코퍼스 5종(NS-05 필수 입력 — 기본은 평문 서술만, 표기 토큰 0)."""
    root = tmp_path / "corpus"
    bank = root / "problem_bank_synthetic_v0"
    bank.mkdir(parents=True)
    # 실제 코퍼스 첫 레코드를 재사용해 Problem 스키마·위생 검증을 통과시킨다(본문만 주입).
    base = json.loads(_REAL_PROBLEMS.read_text(encoding="utf-8").splitlines()[0])
    base["slug"] = "synthetic-notation-coverage"
    base["question_text"] = question_text
    (bank / "problems.jsonl").write_text(
        json.dumps(base, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    formula_dir = root / "formula_graph_v1"
    formula_dir.mkdir()
    (formula_dir / "formulas.jsonl").write_text(
        '{"formula_id": "formula.synthetic", "latex": "(a+b)^{2} = a^{2} + 2ab + b^{2}"}\n',
        encoding="utf-8",
    )
    _write_theory_corpora(root, explanation=theory_explanation, id_token=theory_id_token)
    return root


def _write_baseline(tmp_path: Path, missing: list[dict[str, Any]]) -> Path:
    path = tmp_path / "baseline.json"
    path.write_text(
        json.dumps({"version": "1.0", "missing": missing}, ensure_ascii=False),
        encoding="utf-8",
    )
    return path


class TestPureExtraction:
    def test_korean_prose_zero_false_positive(self) -> None:
        """한글 프로즈·일반 문장부호·선지 마커에서 토큰 0 — 오탐 0이 글리프 축의 핵심 불변식."""
        prose = (
            "학생이 문제를 풀어 보자 — 가·나·다 항목과 ①·② 선지, ‘따옴표’와 “겹따옴표”, "
            "…(줄임표)와 「괄호」까지 전부 프로즈다. 다시 한번 볼까요?"
        )
        assert extract_math_glyphs(prose) == {}
        assert extract_macros(prose) == {}

    def test_macro_extraction(self) -> None:
        r"""매크로 축 — `\매크로명` 전수 추출(횟수 포함·결정론)."""
        text = r"\frac{1}{2} + \sqrt{x} - \cos\theta + \frac{3}{4}"
        assert extract_macros(text) == {
            "\\frac": 2,
            "\\sqrt": 1,
            "\\cos": 1,
            "\\theta": 1,
        }

    def test_glyph_classification(self) -> None:
        """글리프 판별 — 수학 기호·상하첨자·그리스·프라임·분수꼴·도는 참, 프로즈류는 거짓."""
        for ch in ("²", "×", "√", "π", "″", "ₙ", "½", "°", "≤", "→", "Σ", "⅓", "−"):
            assert is_math_glyph(ch), f"{ch!r}(U+{ord(ch):04X})는 수학 글리프여야 한다"
        for ch in ("가", "·", "—", "①", "x", "^", "解", "の", "“"):
            assert not is_math_glyph(ch), f"{ch!r}(U+{ord(ch):04X})는 수학 글리프가 아니어야 한다"

    def test_glyph_extraction_counts(self) -> None:
        assert extract_math_glyphs("x² × π″ 그리고 x²") == {
            "²": 2,
            "×": 1,
            "π": 1,
            "″": 1,
        }


class TestSupportSet:
    def test_real_manifest_derivation(self) -> None:
        """manifest 정본 파생 — 입력측·canonical측·accent·**실증된** allowlist·글리프가 편입된다.

        [MATH-02 계약 변경] 이전에는 `KATEX_PROVEN_MACROS <= support.macros`(allowlist **전량**이
        지원)를 단언했다. 이제는 **근거 파일이 실재하는 부분집합만** 지원으로 파생된다 —
        유령 근거가 지원을 넓히지 못하게 하는 것이 이 태스크의 본체이므로, 옛 단언은 바뀐 계약을
        반영해 교체한다(약화가 아니라 정밀화 — 아래 두 단언이 옛 단언보다 강하다).
        """
        support = load_support_set(_MANIFEST)
        assert "\\doubleprime" in support.macros  # 정규화 매크로 입력측(cases[].input)
        assert "\\prime" in support.macros  # canonical 산출측(cases[].canonical)
        assert "\\overline" in support.macros  # accent_macros
        # `\frac`은 allowlist에도 있으나 manifest cases에도 있어 **독립 출처**로 지원된다
        # (allowlist가 unproven이어도 빠지지 않는다는 뜻 — 출처를 혼동하지 않도록 명기).
        assert "\\frac" in support.macros

        proven, unproven = proven_macros(_PROJECT_ROOT)
        # ① 실증된 것은 반드시 들어온다.
        assert proven <= support.macros
        # ② 실증 안 된 것은 allowlist 경유로 들어오지 못한다(manifest 독립 출처는 정당하므로
        #    allowlist 기여분만 떼어 검사한다 — 이 분리가 옛 단언에는 없던 축이다).
        manifest_only = load_support_set(_MANIFEST, repo_root=_PROJECT_ROOT / "__absent__")
        assert not ((support.macros - manifest_only.macros) & unproven)

        assert "²" in support.glyphs and "′" in support.glyphs  # unicode_glyph_classes

    def test_unproven_symbols_not_included(self) -> None:
        r"""실증 없는 심볼 미추가 봉인 — 렌더 실증이 없는 `\cos` 등은 지원으로 승격되지 않고
        누락(베이스라인) 회계로 흐른다. 이 단언이 깨지면 누군가 실증 없이 allowlist를 넓힌 것."""
        support = load_support_set(_MANIFEST)
        for macro in ("\\cos", "\\int", "\\pm", "\\pi"):
            assert macro not in support.macros, f"{macro}는 렌더 실증 없이 지원에 넣을 수 없다"

    def test_manifest_structure_violation_fails(self, tmp_path: Path) -> None:
        """manifest 필수 키 부재 → 명시 실패(침묵 통과 금지)."""
        bad = tmp_path / "manifest.json"
        bad.write_text('{"cases": []}', encoding="utf-8")
        with pytest.raises(ValueError, match="필수 키 부재"):
            load_support_set(bad)


class TestGateRealCorpus:
    """실제 코퍼스 + 커밋 베이스라인으로 main() 완주 — CI 상시 회귀(본판정)."""

    def test_main_exit_zero_with_committed_baseline(self) -> None:
        """본판정 — 커밋된 베이스라인 대비 신규 누락 0 → exit 0(래칫 green)."""
        assert main([]) == 0

    def test_control_empty_support_exit_one(self) -> None:
        """변별력 봉인 — 지원 집합을 비우면 지원 토큰(²·\\frac 등)이 신규 누락으로 실측돼
        exit 1. 이 대조군이 실패하지 않으면 측정기 자체가 무변별(위장 검증)이다."""
        assert main(["--control-empty-support"]) == 1

    def test_json_report_written(self, tmp_path: Path) -> None:
        """--json 리포트 — 통계·누락 목록·신규/해소·known_gaps(§6 3건 전재) 메타."""
        out = tmp_path / "report.json"
        assert main(["--json", str(out)]) == 0
        payload = json.loads(out.read_text(encoding="utf-8"))
        assert payload["gate_ok"] is True
        assert payload["new_missing"] == []
        assert payload["problems_scanned"] > 0
        assert payload["formulas_scanned"] > 0
        # NS-05 동결 — 이론 코퍼스 5종이 실측되고 그 누락이 베이스라인과 일치함(신규 0).
        assert payload["theory_records_scanned"] > 0
        # 베이스라인 내 누락은 리포트에 남는다(공백 은폐 방지) — 첫 실측에 실존 공백이 있다.
        assert len(payload["missing"]) >= 1
        # 게이트 밖 기록 — notation_contract.md §6 3건 전재(측정 축과 별개임을 명시).
        assert payload["known_gaps_out_of_scope"] == list(KNOWN_GAPS_OUT_OF_SCOPE)
        assert len(KNOWN_GAPS_OUT_OF_SCOPE) == 3

    def test_committed_baseline_loads(self) -> None:
        """커밋된 베이스라인이 로더 구조 검증을 통과하고 비어 있지 않다(첫 실측 산출)."""
        baseline = load_baseline(_BASELINE)
        assert len(baseline) >= 1
        assert (
            "macro",
            "\\cos",
        ) in baseline  # 첫 실측 실존 공백(formula_graph_v1 유래)

    def test_committed_baseline_contains_ns05_theory_entries(self) -> None:
        """NS-05 래칫 동결 — 이론 코퍼스 첫 실측에서 계상된 신규 누락 70건이 베이스라인에
        추가만 된 상태를 봉인한다(대표 표본 단언 — 전수 목록은 본판정 exit 0이 보증)."""
        baseline = load_baseline(_BASELINE)
        # 발생 상위·각 코퍼스 대표 — 지우거나 바꾸면 래칫이 풀려 본판정이 red가 된다.
        for token in ("↔", "∫", "∞", "θ", "ε", "∂", "⊂", "∪", "⇔"):
            assert (
                "glyph",
                token,
            ) in baseline, (
                f"NS-05 베이스라인 항목 {token!r} 부재 — 래칫 후퇴(삭제·수정 금지 원칙 위반)"
            )


class TestGateSynthetic:
    """합성 코퍼스(tmp_path) — 신규 누락 주입·베이스라인 래칫·해소 회계·명시 실패."""

    def test_clean_corpus_passes(self, tmp_path: Path) -> None:
        root = _write_synthetic_root(tmp_path, "이차방정식 x^2 - 5x + 6 = 0 의 근을 구하시오.")
        baseline = _write_baseline(tmp_path, [])
        assert main(["--corpus-root", str(root), "--baseline", str(baseline)]) == 0

    def test_injected_unsupported_glyph_fails(self, tmp_path: Path) -> None:
        """미지원 글리프(⊕·U+2295 Sm) 주입 → 베이스라인 밖 신규 누락 → exit 1."""
        root = _write_synthetic_root(tmp_path, "연산 ⊕ 를 새로 정의하자.")
        baseline = _write_baseline(tmp_path, [])
        assert main(["--corpus-root", str(root), "--baseline", str(baseline)]) == 1

    def test_injected_unsupported_macro_fails(self, tmp_path: Path) -> None:
        r"""미지원 매크로(\oint) 주입 → 신규 누락 → exit 1."""
        root = _write_synthetic_root(tmp_path, r"선적분 \oint 기호를 보자.")
        baseline = _write_baseline(tmp_path, [])
        assert main(["--corpus-root", str(root), "--baseline", str(baseline)]) == 1

    def test_baseline_entry_suppresses_gate(self, tmp_path: Path) -> None:
        """래칫 — 같은 누락이 베이스라인에 등재돼 있으면 리포트만 하고 exit 0(상시 red 방지)."""
        root = _write_synthetic_root(tmp_path, "연산 ⊕ 를 새로 정의하자.")
        baseline = _write_baseline(tmp_path, [{"token": "⊕", "kind": "glyph"}])
        assert main(["--corpus-root", str(root), "--baseline", str(baseline)]) == 0

    def test_resolved_accounting(self, tmp_path: Path) -> None:
        """해소 회계 — 베이스라인에만 있고 코퍼스에 더는 없는 항목은 resolved로 보고(자동
        제거 없음 — 베이스라인 정리는 의식적 수동 편집)."""
        root = _write_synthetic_root(tmp_path, "표기 없는 평문 문항.")
        baseline = _write_baseline(tmp_path, [{"token": "\\ghost", "kind": "macro"}])
        out = tmp_path / "report.json"
        assert (
            main(
                [
                    "--corpus-root",
                    str(root),
                    "--baseline",
                    str(baseline),
                    "--json",
                    str(out),
                ]
            )
            == 0
        )
        payload = json.loads(out.read_text(encoding="utf-8"))
        assert payload["baseline_resolved"] == ["macro:\\ghost"]

    def test_missing_corpus_raises(self, tmp_path: Path) -> None:
        """코퍼스 0건 → 명시 실패(전수 측정의 공허한 통과 차단·skip 은폐 금지)."""
        empty_root = tmp_path / "corpus"
        empty_root.mkdir()
        baseline = _write_baseline(tmp_path, [])
        with pytest.raises(FileNotFoundError, match="문항 코퍼스 0건"):
            main(["--corpus-root", str(empty_root), "--baseline", str(baseline)])

    def test_malformed_formula_line_raises(self, tmp_path: Path) -> None:
        """수식 JSONL 파싱 실패 → 예외 타입명·줄 번호 병기 명시 실패(침묵 실패 금지)."""
        root = _write_synthetic_root(tmp_path, "평문 문항.")
        (root / "formula_graph_v1" / "formulas.jsonl").write_text("not json\n", encoding="utf-8")
        baseline = _write_baseline(tmp_path, [])
        with pytest.raises(ValueError, match="JSONDecodeError"):
            main(["--corpus-root", str(root), "--baseline", str(baseline)])

    def test_formula_without_latex_raises(self, tmp_path: Path) -> None:
        """latex 필드 부재 → 명시 실패(표기 필드 누락을 조용히 건너뛰지 않는다)."""
        root = _write_synthetic_root(tmp_path, "평문 문항.")
        (root / "formula_graph_v1" / "formulas.jsonl").write_text(
            '{"formula_id": "formula.broken"}\n', encoding="utf-8"
        )
        baseline = _write_baseline(tmp_path, [])
        with pytest.raises(ValueError, match="latex 필드 부재"):
            main(["--corpus-root", str(root), "--baseline", str(baseline)])

    def test_missing_baseline_raises(self, tmp_path: Path) -> None:
        """베이스라인 부재 → 명시 실패(자동 생성 경로 없음·래칫 보호)."""
        root = _write_synthetic_root(tmp_path, "평문 문항.")
        with pytest.raises(FileNotFoundError, match="베이스라인 부재"):
            main(["--corpus-root", str(root), "--baseline", str(tmp_path / "none.json")])


class TestGateTheoryCorpus:
    """이론 코퍼스 5종 스캔(NS-05) — 합성 주입 변별력·필드 선정·명시 실패."""

    def test_injected_glyph_in_theory_corpus_fails(self, tmp_path: Path) -> None:
        """이론 서술 필드(concept_content explanation)에 미지원 글리프 ⊕ 주입 →
        베이스라인 밖 신규 누락 → exit 1(문항 경로와 같은 판정이 이론 경로에서도 작동)."""
        root = _write_synthetic_root(
            tmp_path, "평문 문항.", theory_explanation="연산 ⊕ 를 새로 정의하자."
        )
        baseline = _write_baseline(tmp_path, [])
        assert main(["--corpus-root", str(root), "--baseline", str(baseline)]) == 1

    def test_id_code_fields_not_scanned(self, tmp_path: Path) -> None:
        """ID·코드 필드(code·mis_id·src_id)에만 표기 토큰이 있으면 exit 0 —
        "사람이 읽는 수학 서술 텍스트만 스캔"하는 필드 선정 규칙의 대칭 봉인.
        id_token의 ⊕가 스캔됐다면 신규 누락으로 exit 1이 됐을 것이다."""
        root = _write_synthetic_root(tmp_path, "평문 문항.", theory_id_token="S⊕N")
        baseline = _write_baseline(tmp_path, [])
        assert main(["--corpus-root", str(root), "--baseline", str(baseline)]) == 0

    def test_missing_theory_corpus_raises(self, tmp_path: Path) -> None:
        """이론 코퍼스 1종 부재 → 명시 실패(스캔 범위는 5종 전수·skip 은폐 금지)."""
        root = _write_synthetic_root(tmp_path, "평문 문항.")
        (root / "misconceptions_v1" / "misconceptions.json").unlink()
        baseline = _write_baseline(tmp_path, [])
        with pytest.raises(FileNotFoundError, match="이론 코퍼스 부재"):
            main(["--corpus-root", str(root), "--baseline", str(baseline)])

    def test_malformed_theory_json_raises(self, tmp_path: Path) -> None:
        """이론 코퍼스 JSON 파싱 실패 → 예외 타입명 병기 명시 실패(침묵 실패 금지)."""
        root = _write_synthetic_root(tmp_path, "평문 문항.")
        (root / "concept_content_v1" / "content.json").write_text("not json\n", encoding="utf-8")
        baseline = _write_baseline(tmp_path, [])
        with pytest.raises(ValueError, match="JSONDecodeError"):
            main(["--corpus-root", str(root), "--baseline", str(baseline)])

    def test_theory_records_key_missing_raises(self, tmp_path: Path) -> None:
        """레코드 배열 키 부재(구조 위반) → 명시 실패(스캔 누락을 조용히 통과시키지 않는다)."""
        root = _write_synthetic_root(tmp_path, "평문 문항.")
        (root / "atom_graph_v1" / "graph.json").write_text('{"atoms": []}', encoding="utf-8")
        baseline = _write_baseline(tmp_path, [])
        with pytest.raises(ValueError, match="배열 부재/구조 위반"):
            main(["--corpus-root", str(root), "--baseline", str(baseline)])

    def test_theory_schema_drift_raises(self, tmp_path: Path) -> None:
        """선언된 텍스트 필드에 str/null 아닌 값 → 스키마 드리프트 명시 실패 —
        새 텍스트 필드가 스캔에서 새어 나가는 것을 막는다."""
        root = _write_synthetic_root(tmp_path, "평문 문항.")
        (root / "atom_graph_v1" / "graph.json").write_text(
            json.dumps({"concepts": [{"code": "A1", "socratic": ["목록은", "드리프트"]}]}),
            encoding="utf-8",
        )
        baseline = _write_baseline(tmp_path, [])
        with pytest.raises(ValueError, match="스키마 드리프트"):
            main(["--corpus-root", str(root), "--baseline", str(baseline)])
