"""표기 커버리지 하네스(NS-03) — "코퍼스 표기 ⊆ 지원 표기"를 CLI exit 0/1로 측정하는 게이트.

정본: `docs/architecture/notation_semantics_layer.md` §3(L3 완전성 하네스)·§4·§5 — 표기 완전성을
인상이 아니라 *측정*으로 관리한다(측정 없는 도입 없음). 지원 표기의 열거 정본은
`data/notation_support_manifest.json`(NS-02 신설)이고, 이 모듈은 리포 커밋 코퍼스
(`data/corpus/problem_bank_*/problems.jsonl` 표기 필드 + `formula_graph_v1/formulas.jsonl`의
`latex` + **[NS-05] 이론 코퍼스 4종** — concept_content(K-12·대학)·atom_graph·misconceptions
(사람이 읽는 수학 서술 텍스트 필드, `THEORY_CORPORA` 명세 참조. 구 437 개념 그래프
스냅샷은 legacy 동결 거버넌스상 의도적 제외 — 명세 주석 참조)에서 표기 토큰을
전수 추출해 지원 집합과 대조한다(hermetic·LLM 0·DB 0·결정론).

측정 축(2축 — 구조 표기는 과잉이라 제외):
  ① **LaTeX 매크로**: `\\[a-zA-Z]+` 전수 추출. 지원 = manifest 파생(정규화 매크로 입력측 +
     canonical 산출측 + accent_macros) ∪ KaTeX 렌더 *실증* allowlist 중 **근거 파일이 실재하는
     부분집합**(`proven_macros()` — 실증 없는 심볼 추가 금지). 근거가 부재한 항목은 삭제하지 않고
     `unproven`으로 격리해 리포트가 별도로 계상한다(MATH-02 ④ — 유령 근거로 지원을 넓히지 않되
     공백을 지워 없애지도 않는다).
  ② **비-ASCII 수학 글리프**: 유니코드 카테고리·블록 기반 정밀 판별(`is_math_glyph`) —
     한글·CJK·일반 문장부호는 제외해 한국어 프로즈 오탐 0을 지킨다. 지원 = manifest
     `unicode_glyph_classes`(상첨자·프라임).

게이트 판정(래칫): 누락 심볼(코퍼스 등장 ∧ 지원 집합 밖)을 **베이스라인**
(`data/notation_missing_baseline.json` — 첫 실측 산출로 생성·커밋된 Missing Symbol Report 정본)
대비 비교한다. **신규 누락 발견 시 exit 1**, 베이스라인 내 누락은 리포트만(기존 공백으로 상시
red가 되는 것과 공백 은폐를 동시에 방지). 베이스라인 갱신은 *의식적 수동 편집*만 — 자동 갱신
(`--rebaseline` 류)은 래칫을 무력화하므로 만들지 않는다. 전수 측정이라 Wilson 불요(표본 아님).

변별력 대조군(`--control-empty-support`): 지원 집합을 비워 같은 코퍼스를 돌리면 지원 토큰
(`²`·`\\frac` 등)이 전부 신규 누락이 되어 exit 1이 *실측*돼야 한다 — 실패 상태에서 실패 신호를
내는 검출기임을 봉인한다("변별력 없는 검증 스텝 금지"·coach_prose_leak_eval `--control-flag-off`
선례). 상시 회귀는 `tests/backend/l3/test_notation_coverage_eval.py`(backend pytest 잡 자동 포함).

표현≠의미: 이 게이트는 표기 토큰 *멤버십*만 측정한다 — 수학 의미·동치 판정 0(그건 SymPy 단일
권위·`l3/verify_step.py`). 침묵 실패 금지: 코퍼스·manifest·베이스라인 부재나 파싱 실패는 예외
타입명을 포함해 명시 실패한다(skip 은폐 금지).

근거 무결성(MATH-02): 지원집합이 *근거로 지목한 파일*이 실재하는지는 이 게이트가 판정하지 않고
`tests/backend/l3/test_notation_evidence_integrity.py`가 본다 — 축이 다르기 때문이다. 이 게이트는
"코퍼스에 뭐가 빠졌나"를, 그 테스트는 "우리 근거가 뭐가 유령인가"를 묻는다. 2026-08-11 실측 기준
`NS-02` 미착륙으로 Dart 실증 파일 5종이 전부 부재하며(포기 판정 — manifest `provenance`
`ns02_disposition`), 그로 인해 allowlist 24건이 `unproven`으로 격리돼 있다.

7계층: L3이 L1 로더(`l1.problem_bank.populate.load_problem_bank_records`)를 *호출*한다
(L3→L1 정방향·import-linter layers 계약 내).

사용:
    python -m whymath_backend.l3.notation_coverage
    python -m whymath_backend.l3.notation_coverage --json report.json
    python -m whymath_backend.l3.notation_coverage --control-empty-support   # exit 1이어야 정상
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import re
import sys
import unicodedata
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any, Final

from whymath_backend.l1.problem_bank.populate import load_problem_bank_records

# 종료 코드 — 게이트 CLI 관례(corpus_audit_eval·coach_prose_leak_eval 동형).
_EXIT_OK: Final[int] = 0
_EXIT_GATE_FAIL: Final[int] = 1

# LaTeX 매크로 토큰 — 백슬래시 + 영문 연속(전수·결정론). `\left|`의 `|` 같은 비영문 꼬리는
# 매크로명이 아니므로 잡지 않는다.
_MACRO_RE: Final[re.Pattern[str]] = re.compile(r"\\[a-zA-Z]+")

# ──────────────────────────────────────────────────────────────────────────
# KaTeX 렌더 실증 매크로 allowlist — *실측 근거 있는 것만*(실증 없는 심볼 추가 금지)
# ──────────────────────────────────────────────────────────────────────────
# 근거를 **기계 판독 데이터로** 보유한다(MATH-02 ②). 이전에는 매크로 위 *산문 주석*이 출처를
# 적었는데, 주석은 어떤 검사도 읽지 않으므로 근거 파일이 사라져도 게이트가 계속 green이었다 —
# 실제로 `NS-02`가 미병합 브랜치에 고립돼 착륙하지 못하면서 아래 실증 파일이 전부 부재하게 됐고,
# 그 사실을 8일간 아무도 보지 못했다(증상이 red가 아니라 green이라 더 조용했다).
# 주석을 파싱하지 않는다(취약) — 매핑 자체가 정본이고 `KATEX_PROVEN_MACROS`는 여기서 파생한다
# (이중 정의 금지). 참조 무결성은 `tests/backend/l3/test_notation_evidence_integrity.py`가 동결.
#
# 출처 규약: Dart 위젯 렌더 테스트가 flutter_math_fork(KaTeX 계열)로 실제 조판됨(폴백 아님·
# 크래시 0)을 단언한 매크로만 담는다. 새 매크로는 반드시 렌더 실증 테스트를 먼저 추가한 뒤 여기
# 등재한다 — 여기 없는 코퍼스 매크로(`\cos`·`\int`·`\pm`·`\pi` 등)는 누락으로 측정되어
# 베이스라인에 남는 것이 정직한 회계다.
_EVIDENCE_AUDIT: Final[str] = "src/mobile/test/math_notation_audit_test.dart"
_EVIDENCE_MATH_TEXT: Final[str] = "src/mobile/test/math_text_test.dart"

_PROVEN_MACRO_EVIDENCE: Final[Mapping[str, str]] = MappingProxyType(
    {
        # `_expectRenders` 위젯 조판 실증(S3-23).
        "\\partial": _EVIDENCE_AUDIT,  # 편미분 ∂·\frac{\partial f}{\partial x}
        "\\frac": _EVIDENCE_AUDIT,  # 분수형 편도함수
        "\\lim": _EVIDENCE_AUDIT,  # 극한 \lim_{x\to\infty}
        "\\to": _EVIDENCE_AUDIT,
        "\\infty": _EVIDENCE_AUDIT,
        "\\iint": _EVIDENCE_AUDIT,  # 이중적분
        "\\iiint": _EVIDENCE_AUDIT,  # 삼중적분
        "\\sqrt": _EVIDENCE_AUDIT,  # n제곱근 \sqrt[3]{x}
        "\\log": _EVIDENCE_AUDIT,  # 로그 하첨자 \log_{10}x
        "\\sin": _EVIDENCE_AUDIT,  # 역삼각 \sin^{-1}x
        # 그리스 대표(같은 파일 '그리스 대표' 루프에서 개별 조판 실증).
        "\\alpha": _EVIDENCE_AUDIT,
        "\\beta": _EVIDENCE_AUDIT,
        "\\theta": _EVIDENCE_AUDIT,
        "\\varepsilon": _EVIDENCE_AUDIT,
        "\\varkappa": _EVIDENCE_AUDIT,
        "\\varphi": _EVIDENCE_AUDIT,
        "\\omega": _EVIDENCE_AUDIT,
        "\\Gamma": _EVIDENCE_AUDIT,
        "\\Delta": _EVIDENCE_AUDIT,
        "\\Sigma": _EVIDENCE_AUDIT,
        "\\Omega": _EVIDENCE_AUDIT,
        # `f^(\prime)(x)=3\lbrack x+8\rbrack(x-6)` 조판 실증(math_text_test.dart:118-125).
        "\\prime": _EVIDENCE_MATH_TEXT,
        "\\lbrack": _EVIDENCE_MATH_TEXT,
        "\\rbrack": _EVIDENCE_MATH_TEXT,
    }
)

# 하위 호환 — 이 이름을 읽는 기존 소비처(`test_unproven_symbols_not_included` 등)를 위해 유지한다.
# **주의**: 이것은 *주장된* allowlist이지 지원집합이 아니다. 실제 지원 파생은 근거 파일이 실재하는
# 부분집합(`proven_macros()`)만 쓴다 — 유령 근거로 지원을 넓히지 않기 위해서다(MATH-02 ④).
KATEX_PROVEN_MACROS: Final[frozenset[str]] = frozenset(_PROVEN_MACRO_EVIDENCE)


def proven_macros(repo_root: Path) -> tuple[frozenset[str], frozenset[str]]:
    """근거 파일 실재 여부로 allowlist를 둘로 가른다 — `(proven, unproven)`.

    `_PROVEN_MACRO_EVIDENCE`의 `evidence_path`가 `repo_root` 기준으로 **실재하는** 매크로만
    `proven`이다. 부재 근거 항목은 삭제하지 않고 `unproven`으로 격리해 반환한다 — 지우면 공백이
    사라져 보이고, 남겨두면 유령 근거가 지원을 넓힌다. 격리는 "숨기지 않고 세기" 위한 선택이다
    (MATH-02 ④·CLAUDE.md "정직한 공백").

    순수 파일 IO(존재 검사만)·결정론. 반환 집합은 정렬 불변(frozenset)이며 호출자가 정렬한다.
    """
    proven: set[str] = set()
    unproven: set[str] = set()
    for macro, evidence in _PROVEN_MACRO_EVIDENCE.items():
        (proven if (repo_root / evidence).exists() else unproven).add(macro)
    return frozenset(proven), frozenset(unproven)


# ──────────────────────────────────────────────────────────────────────────
# NS-02 정합 검토 잔여 3건 — 게이트 *밖* 기록(notation_contract.md §6 전재)
# ──────────────────────────────────────────────────────────────────────────
# 이 게이트의 측정 축(①`\`매크로 ②비-ASCII 글리프)에 잡히지 않는 표기 품질 항목이다 —
# `sin`은 매크로가 아니고(§6-1), §6-2·§6-3은 ASCII 표기의 *조판 방식* 문제라 토큰 멤버십
# 측정과 별개 축이다. 은폐하지 않도록 리포트 known_gaps 메타로 전재한다(측정 축과 별개임을
# 명시·수정은 NS-03 범위 밖).
KNOWN_GAPS_OUT_OF_SCOPE: Final[tuple[str, ...]] = (
    "§6-1 표준함수 이탤릭 조판: sin·cos 등 표준함수가 Dart 렌더 경로에서 \\sin 연산자 매크로로 "
    "승격되지 않아 이탤릭 문자 나열(s·i·n)로 조판된다(sqrt만 승격). `sin`은 매크로 토큰이 "
    "아니라 본 게이트의 매크로 축에 잡히지 않는다 — 측정 축과 별개·기록만.",
    "§6-2 무신호 식 평문 폴백: `x+x+x`처럼 수식 신호(^ _ \\ / *) 없는 계약 canonical 식은 "
    "조판에서 빠진다(S3-21 과잉 렌더 방지 정책의 의도된 결과). ASCII 표기의 라우팅 문제라 "
    "토큰 멤버십 측정과 별개 축 — 기록만.",
    "§6-3 슬래시 나눗셈: `x/4+1`이 \\frac 수평 분수로 승격되지 않고 슬래시 그대로 조판된다"
    "(렌더 가능·의미 왜곡 없음·허용). ASCII 표기라 글리프/매크로 축 밖 — 기록만.",
)

# ──────────────────────────────────────────────────────────────────────────
# 수학 글리프 판별 (순수·결정론) — 한국어 프로즈 오탐 0이 핵심
# ──────────────────────────────────────────────────────────────────────────
# 유니코드 프라임(U+2032~2034) — 카테고리는 Po(문장부호)지만 수학 전용 표기라 명시 포함.
_PRIME_GLYPHS: Final[frozenset[str]] = frozenset("′″‴")
# Latin-1 상첨자(U+00B9·B2·B3) — 상·하첨자 블록(U+2070~209F) 밖이라 명시 포함.
_LATIN1_SUPERSCRIPTS: Final[frozenset[str]] = frozenset("¹²³")
# Latin-1 분수꼴(U+00BC~BE) — 분수꼴 블록(U+2150~215F) 밖이라 명시 포함.
_LATIN1_FRACTIONS: Final[frozenset[str]] = frozenset("¼½¾")
# 도(degree·U+00B0) — 카테고리 So지만 각도 표기라 명시 포함(수학 관련 So).
_DEGREE_SIGN: Final[str] = "°"


def is_math_glyph(ch: str) -> bool:
    """단일 문자가 *수학 표기 글리프*인지 판별(순수) — 카테고리·블록 기반 전수 규칙.

    포함: ① 수학 연산자·기호(카테고리 Sm — ×·√·−·±·≠·≤·→·∩ 등) ② 상·하첨자 블록
    U+2070~209F(ⁿ·ₙ·₁ 등·Lm/No/Sm 혼재라 블록으로) + Latin-1 상첨자 ¹²³ ③ 분수꼴
    (¼½¾·U+2150~215F) ④ 그리스 문자(U+0370~03FF의 Letter — 한국 수학 코퍼스에서 그리스
    문자는 항상 수학 표기) ⑤ 프라임 ′″‴ ⑥ 도(°).

    제외(설계·오탐 0): 한글·CJK·가나(카테고리 Lo — 프로즈이거나 코퍼스 오염이며 표기 커버리지
    축이 아님), 일반 문장부호(Po·Pd — 특히 중점 `·`은 한국어 열거 구분자와 곱셈 표기가 동형이라
    판별이 의미 해석이 되므로 표현≠의미 원칙상 측정 밖), 선지 마커류(①② 등 Enclosed
    Alphanumerics — 어느 규칙에도 안 걸려 자연 제외).
    """
    code = ord(ch)
    if code < 128:  # ASCII는 글리프 축 밖(매크로·구조 표기는 별도 축)
        return False
    if ch in _PRIME_GLYPHS or ch in _LATIN1_SUPERSCRIPTS or ch in _LATIN1_FRACTIONS:
        return True
    if ch == _DEGREE_SIGN:
        return True
    if 0x2070 <= code <= 0x209F:  # 상·하첨자 블록
        return True
    if 0x2150 <= code <= 0x215F:  # 분수꼴(Number Forms 앞부분)
        return True
    if 0x0370 <= code <= 0x03FF and unicodedata.category(ch).startswith("L"):  # 그리스 문자
        return True
    return unicodedata.category(ch) == "Sm"  # 수학 기호 카테고리


def extract_macros(text: str) -> Counter[str]:
    """텍스트에서 LaTeX 매크로 토큰 전수 추출(순수·결정론) — `\\매크로명` 형태 그대로."""
    return Counter(_MACRO_RE.findall(text))


def extract_math_glyphs(text: str) -> Counter[str]:
    """텍스트에서 비-ASCII 수학 글리프 전수 추출(순수·결정론) — `is_math_glyph` 규칙."""
    return Counter(ch for ch in text if is_math_glyph(ch))


# ──────────────────────────────────────────────────────────────────────────
# 지원 표기 집합 — manifest(정본) 파생 + KaTeX 실증 allowlist
# ──────────────────────────────────────────────────────────────────────────
@dataclass(frozen=True, slots=True)
class SupportSet:
    """지원 표기 집합 — 매크로(`\\이름` 형)·글리프(단일 문자). 불변."""

    macros: frozenset[str]
    glyphs: frozenset[str]


# 변별력 대조군용 공집합 지원 — 게이트가 실패 상태에서 실패 신호를 내는지 실측하는 데 쓴다.
EMPTY_SUPPORT: Final[SupportSet] = SupportSet(macros=frozenset(), glyphs=frozenset())


def load_support_set(manifest_path: Path, *, repo_root: Path | None = None) -> SupportSet:
    """`notation_support_manifest.json`(NS-02 정본) → 지원 표기 집합 파생(순수 파일 IO).

    매크로 = cases[].input(정규화 매크로 입력측) ∪ cases[].canonical(산출측) ∪ accent_macros
    ∪ **근거가 실재하는** 렌더 실증 allowlist(`proven_macros`). 글리프 =
    unicode_glyph_classes 전 문자. manifest가 정본이므로 여기서 별도 열거를 만들지 않는다
    (단일 진실 원천).

    **allowlist 전량이 아니라 실증 부분집합만 쓴다**(MATH-02 ④): 근거 파일이 부재한 매크로를
    지원으로 세면 유령 근거가 커버리지를 넓혀 게이트가 거짓 green이 된다. 부재분은 삭제하지 않고
    `proven_macros`가 `unproven`으로 격리해 리포트가 별도로 계상한다 — 공백을 숨기지 않고 센다.

    Args:
        manifest_path: 지원 표기 정본 경로.
        repo_root: 근거 파일 실재를 판정할 기준 루트. None이면 manifest의 조부모
            (`<root>/data/x.json` → `<root>`)로 추론한다.

    Raises:
        FileNotFoundError: manifest 부재.
        ValueError: 필수 키 부재·구조 위반(침묵 실패 금지).
    """
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    for key in ("cases", "accent_macros", "unicode_glyph_classes"):
        if key not in payload:
            raise ValueError(f"manifest 필수 키 부재: {key!r} ({manifest_path})")

    root = repo_root if repo_root is not None else manifest_path.resolve().parents[1]
    proven, _unproven = proven_macros(root)
    macros: set[str] = set(proven)
    for case in payload["cases"]:
        if not isinstance(case, dict) or "input" not in case or "canonical" not in case:
            raise ValueError(f"manifest cases 항목 구조 위반: {case!r} ({manifest_path})")
        macros.update(_MACRO_RE.findall(str(case["input"])))
        macros.update(_MACRO_RE.findall(str(case["canonical"])))
    macros.update(f"\\{name}" for name in payload["accent_macros"])

    glyphs: set[str] = set()
    for chars in payload["unicode_glyph_classes"].values():
        for token in chars:
            # 항목은 단일 문자 규약이나, 방어적으로 문자 단위로 편입한다(다문자 항목도 안전).
            glyphs.update(str(token))
    return SupportSet(macros=frozenset(macros), glyphs=frozenset(glyphs))


# ──────────────────────────────────────────────────────────────────────────
# 코퍼스 스캔 — 표기 필드 전수(문항 3필드 + 수식 latex)
# ──────────────────────────────────────────────────────────────────────────
@dataclass(slots=True)
class CorpusScan:
    """코퍼스 전수 스캔 결과 — 토큰별 {출처: 등장 횟수} 원장(집계 전 원자료)."""

    problems_scanned: int = 0
    formulas_scanned: int = 0
    theory_records_scanned: int = 0  # NS-05 — 이론 코퍼스 레코드 수(문항·수식과 별도 회계)
    # token → {source_name: count}. source_name = 코퍼스 디렉토리명(problem_bank_v1 등).
    macro_occurrences: dict[str, dict[str, int]] = field(default_factory=dict)
    glyph_occurrences: dict[str, dict[str, int]] = field(default_factory=dict)

    def _accumulate(self, table: dict[str, dict[str, int]], found: Counter[str], src: str) -> None:
        for token, count in found.items():
            per_source = table.setdefault(token, {})
            per_source[src] = per_source.get(src, 0) + count

    def add_text(self, text: str, source: str) -> None:
        """표기 필드 텍스트 1건을 두 축(매크로·글리프)으로 추출해 원장에 누적한다."""
        self._accumulate(self.macro_occurrences, extract_macros(text), source)
        self._accumulate(self.glyph_occurrences, extract_math_glyphs(text), source)


def _notation_texts(
    question_text: str | None, explanation: str | None, choices: Sequence[str] | None
) -> list[str]:
    """문항 1건의 표기 필드(question_text·answer_explanation·choices) → 비어있지 않은 텍스트."""
    texts = [t for t in (question_text, explanation) if t]
    if choices:
        texts.extend(c for c in choices if c)
    return texts


def scan_corpora(problem_paths: Sequence[Path], formulas_path: Path) -> CorpusScan:
    """리포 커밋 코퍼스 전수 스캔 — 문항 표기 3필드 + 수식 `latex`(hermetic·DB 0).

    문항은 L1 정본 로더 `load_problem_bank_records`(저작권 위생·Problem 스키마 검증 동반)로
    읽는다 — 로더의 검증 실패(위생·스키마)는 그대로 전파한다(침묵 통과 금지). 수식 JSONL은
    줄 단위 파싱하며 오류에 예외 타입명·줄 번호를 병기해 명시 실패한다.

    Raises:
        FileNotFoundError: 코퍼스 0건(전수 측정이 공허하게 통과하는 것 차단) 또는 파일 부재.
        ValueError: 수식 JSONL 파싱 실패·latex 필드 부재(줄 번호 병기).
    """
    if not problem_paths:
        raise FileNotFoundError(
            "문항 코퍼스 0건 — problem_bank_*/problems.jsonl이 없다. 전수 측정이 공허하게 "
            "통과할 수 없으므로 명시 실패한다(--corpus-root 확인)."
        )
    scan = CorpusScan()
    for path in problem_paths:
        source = path.parent.name
        for record in load_problem_bank_records(path):
            problem = record.problem
            for text in _notation_texts(
                problem.question_text, problem.answer_explanation, problem.choices
            ):
                scan.add_text(text, source)
            scan.problems_scanned += 1

    formula_source = formulas_path.parent.name
    try:
        formula_text = formulas_path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise FileNotFoundError(
            f"수식 코퍼스 부재: {formulas_path} ({type(exc).__name__}) — skip 은폐 금지"
        ) from exc
    for line_num, raw in enumerate(formula_text.splitlines(), start=1):
        stripped = raw.strip()
        if not stripped:
            continue
        try:
            obj = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{formulas_path}:{line_num}: {type(exc).__name__}: {exc}") from exc
        latex = obj.get("latex") if isinstance(obj, dict) else None
        if not isinstance(latex, str) or not latex.strip():
            raise ValueError(
                f"{formulas_path}:{line_num}: latex 필드 부재/공백 — 표기 필드 누락을 "
                "조용히 건너뛰지 않는다"
            )
        scan.add_text(latex, formula_source)
        scan.formulas_scanned += 1
    return scan


# ──────────────────────────────────────────────────────────────────────────
# 이론 코퍼스 스캔 (NS-05) — 문제은행 밖 사람이 읽는 수학 서술 텍스트 전수
# ──────────────────────────────────────────────────────────────────────────
# 2026-08-13 감사 실측으로 이론 코퍼스 5종에 미지원 글리프가 대량(atom_graph `→` 2448회·
# `−` 662·`×` 512 등) 존재하는데 본 게이트가 측정하지 않던 공백을 메운다(개념 그래프
# concepts.jsonl은 legacy snapshot 거버넌스로 제외 — 아래 명세 주석). 문항과 같은
# 아키텍처를 따른다: 파일·구조 부재는 명시 실패(침묵 skip 금지), 토큰 추출·판정 로직은
# 재사용(이중 정의 금지) — 바뀌는 것은 "어느 파일의 어느 필드를 읽나"뿐이다.
#
# 필드 선정 규칙: **사람이 읽는 수학 서술 텍스트만** 스캔한다. ID·코드·수치·분류 라벨 필드
# (code·mis_id·*_code·school_level·difficulty·mapping_* 등)는 표기 커버리지 축이 아니므로
# 제외한다 — 선정 전 필드별 토큰 분포를 전수 실측해(2026-08-13) 라벨 필드에 표기 토큰이
# 없거나 있어도 서술 필드가 같은 심볼을 이미 커버함을 확인했다.
@dataclass(frozen=True, slots=True)
class TheoryCorpusSpec:
    """이론 코퍼스 1종의 스캔 명세 — 경로·레코드 위치·텍스트 필드 열거(불변)."""

    rel_path: str  # corpus_root 기준 상대 경로
    records_key: str  # 레코드 배열의 최상위 키
    text_fields: tuple[str, ...]  # 스캔할 문자열 필드(null·결측은 스키마상 정상 — 건너뜀)
    # 레코드 안 리스트 필드(플래시카드) — 각 항목 dict의 문자열 값을 전수 스캔한다
    # (flashcards[].* 명세 — front·back·mnemonic 현행, 향후 텍스트 필드 추가도 자동 포착).
    scan_all_string_fields_of: str | None = None


# K-12·대학 이론 코퍼스 공통 필드 — 개념명(name: ÷·×·Σ·π 등 표기 실재) + 서술 5종.
# 제외: code(ID)·subject·unit(교과 분류 라벨)·review_status(검수 상태)·standard_codes(코드).
_CONTENT_TEXT_FIELDS: Final[tuple[str, ...]] = (
    "name",
    "explanation",
    "metaphor",
    "misconception",
    "formal_definition_internal",
    "accepted_expressions",
)

THEORY_CORPORA: Final[tuple[TheoryCorpusSpec, ...]] = (
    TheoryCorpusSpec(
        rel_path="concept_content_v1/content.json",
        records_key="content",
        text_fields=_CONTENT_TEXT_FIELDS,
        scan_all_string_fields_of="flashcards",
    ),
    TheoryCorpusSpec(  # 대학 이론 — 동일 구조(review_status·standard_codes만 부재).
        rel_path="concept_content_university_v1/content.json",
        records_key="content",
        text_fields=_CONTENT_TEXT_FIELDS,
        scan_all_string_fields_of="flashcards",
    ),
    # 원자 그래프 노드 — 개념명·핵심 명제·오개념·소크라틱 질문·진단 3종·비고·전이 서술.
    # 제외: code·parent_code·subunit_code·standard_codes(코드), level·grade_band·school_level·
    # subject_area·unit·subunit·cognitive_type·misconception_type·node_type(분류 라벨),
    # intrinsic_difficulty(수치)·atomicity(dict)·redacted_fields(목록). 엣지(from_name·
    # to_name 등)는 노드 name의 중복이라 스캔하지 않는다.
    TheoryCorpusSpec(
        rel_path="atom_graph_v1/graph.json",
        records_key="concepts",
        text_fields=(
            "name",
            "name_display",
            "core_proposition",
            "misconception",
            "socratic",
            "diagnostic_item",
            "diagnostic_answer",
            "diagnostic_signal",
            "notes",
            "transfer",
            "transfer_example",
        ),
    ),
    # 오개념 — 정준 진술·학생 오류 사고·교정 지점·오답 유도 규칙(전부 학생-facing 서술).
    # 제외: mis_id·*_code(ID)·school_level·domain·subunit(라벨)·error_type·difficulty·
    # severity·mapping_confidence·mapping_score·provenance_note(메타)·behavior_skills(코드 목록).
    TheoryCorpusSpec(
        rel_path="misconceptions_v1/misconceptions.json",
        records_key="misconceptions",
        text_fields=(
            "canonical_statement",
            "student_wrong_thinking",
            "correction_point",
            "distractor_rule",
        ),
    ),
    # concept_graph_v1/concepts.jsonl은 **의도적 제외**(NS-05 초판에서 포함했다가 CI의
    # test_legacy_snapshot_governance가 거부): 구 437 개념 그래프는 legacy_snapshot으로
    # 동결된 자산이고 화이트리스트(concept_atom_crosswalk·curriculum·problem_bank 빌드
    # 적재 3종) 밖 모듈의 읽기가 금지다. 표기 측정 가치도 중복이다 — 같은 개념의 서술 텍스트는
    # atom_graph_v1(노드 서술 11필드)과 concept_content_v1이 이미 커버한다. 런타임 재유입
    # 금지와 측정 공백 해소를 함께 지키는 방향이 이 제외다.
)


def _theory_record_texts(
    record: dict[str, Any], spec: TheoryCorpusSpec, *, where: str
) -> list[str]:
    """이론 레코드 1건에서 선언된 텍스트 필드의 문자열 값을 모은다(순수).

    null·결측 필드는 스키마상 정상이라 건너뛰지만, 선언된 텍스트 필드에 문자열/null 아닌 값이
    오면 스키마 드리프트다 — 조용히 건너뛰면 새 텍스트 필드가 스캔에서 새어 나가므로 명시
    실패한다(침묵 실패 금지).
    """
    texts: list[str] = []
    for field_name in spec.text_fields:
        value = record.get(field_name)
        if value is None:
            continue
        if not isinstance(value, str):
            raise ValueError(
                f"{where}: 필드 {field_name!r}이 str/null이 아님({type(value).__name__}) — "
                "스키마 드리프트: THEORY_CORPORA 명세 갱신 여부를 확인하라"
            )
        if value.strip():
            texts.append(value)
    if spec.scan_all_string_fields_of is not None:
        field = spec.scan_all_string_fields_of
        cards = record.get(field)
        if cards is None:
            cards = []
        if not isinstance(cards, list):
            raise ValueError(
                f"{where}: 필드 {field!r}이 list/null이 아님({type(cards).__name__}) — "
                "스키마 드리프트"
            )
        for card in cards:
            if not isinstance(card, dict):
                raise ValueError(
                    f"{where}: {field} 항목이 dict가 아님({type(card).__name__}) — 스키마 드리프트"
                )
            texts.extend(v for v in card.values() if isinstance(v, str) and v.strip())
    return texts


def scan_theory_corpora(corpus_root: Path, scan: CorpusScan) -> None:
    """이론 코퍼스 4종(`THEORY_CORPORA`)의 서술 텍스트를 전수 스캔해 원장에 누적한다(NS-05).

    문항·수식 스캔과 같은 원장·같은 출처 규약(디렉토리명)을 쓴다. 파일 부재·JSON 파싱 실패·
    레코드 배열 구조 위반·선언 필드의 스키마 드리프트는 전부 예외 타입명을 병기해 명시 실패
    한다 — 이론 코퍼스가 통째로 빠져도 green으로 지나가는 공허 통과를 차단하기 위해서다
    (레코드 총 0건도 명시 실패 — `scan_corpora`의 "문항 코퍼스 0건" 가드와 동일 철학).

    Raises:
        FileNotFoundError: 이론 코퍼스 파일 부재·레코드 총 0건.
        ValueError: JSON 파싱 실패·레코드 배열 부재/구조 위반·스키마 드리프트.
    """
    before = scan.theory_records_scanned
    for spec in THEORY_CORPORA:
        path = corpus_root / spec.rel_path
        source = path.parent.name
        try:
            raw = path.read_text(encoding="utf-8")
        except FileNotFoundError as exc:
            raise FileNotFoundError(
                f"이론 코퍼스 부재: {path} ({type(exc).__name__}) — 스캔 범위는 명세 전수이며 "
                "부재를 조용히 건너뛰지 않는다(skip 은폐 금지)"
            ) from exc
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}: {type(exc).__name__}: {exc}") from exc
        records = payload.get(spec.records_key) if isinstance(payload, dict) else None
        if not isinstance(records, list):
            raise ValueError(
                f"{path}: 최상위 {spec.records_key!r} 배열 부재/구조 위반 — 스캔 누락을 "
                "조용히 통과시키지 않는다"
            )
        for index, record in enumerate(records):
            if not isinstance(record, dict):
                raise ValueError(
                    f"{path}: {spec.records_key}[{index}]이 dict가 아님({type(record).__name__})"
                )
            where = f"{path}: {spec.records_key}[{index}]"
            for text in _theory_record_texts(record, spec, where=where):
                scan.add_text(text, source)
            scan.theory_records_scanned += 1
    if scan.theory_records_scanned == before:
        raise FileNotFoundError(
            f"이론 코퍼스 레코드 0건 ({corpus_root}) — 전수 측정이 공허하게 통과할 수 없으므로 "
            "명시 실패한다(문항 코퍼스 0건 가드와 동일 철학)"
        )


# ──────────────────────────────────────────────────────────────────────────
# 베이스라인 (래칫 정본) — 로드만 한다. 갱신은 의식적 수동 편집(자동 갱신 금지).
# ──────────────────────────────────────────────────────────────────────────
_BASELINE_KINDS: Final[frozenset[str]] = frozenset({"macro", "glyph"})


def load_baseline(path: Path) -> frozenset[tuple[str, str]]:
    """베이스라인 JSON → {(kind, token)} 집합. 부재·구조 위반은 명시 실패.

    베이스라인은 첫 실측 산출로 생성·커밋된 Missing Symbol Report 정본이며, 갱신(항목 추가·
    해소 제거)은 의식적 수동 편집으로만 한다 — 이 로더는 읽기 전용이고 쓰기 경로는 없다.

    Raises:
        FileNotFoundError: 베이스라인 부재(첫 생성도 수동 커밋 — 자동 생성 경로 없음).
        ValueError: JSON 파싱 실패·구조 위반(예외 타입명 병기).
    """
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise FileNotFoundError(
            f"베이스라인 부재: {path} ({type(exc).__name__}) — 첫 실측 산출을 수동 커밋해야 "
            "게이트가 가동된다(자동 생성 경로 없음·래칫 보호)"
        ) from exc
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path}: {type(exc).__name__}: {exc}") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("missing"), list):
        raise ValueError(f"{path}: 베이스라인 구조 위반 — 최상위 dict + missing 리스트 필수")
    out: set[tuple[str, str]] = set()
    for entry in payload["missing"]:
        if not isinstance(entry, dict) or "token" not in entry or "kind" not in entry:
            raise ValueError(f"{path}: missing 항목 구조 위반: {entry!r}")
        kind = str(entry["kind"])
        if kind not in _BASELINE_KINDS:
            raise ValueError(f"{path}: 알 수 없는 kind {kind!r} (허용: {sorted(_BASELINE_KINDS)})")
        out.add((kind, str(entry["token"])))
    return frozenset(out)


# ──────────────────────────────────────────────────────────────────────────
# 판정 (순수) — 누락·신규 누락·해소 회계
# ──────────────────────────────────────────────────────────────────────────
@dataclass(frozen=True, slots=True)
class MissingToken:
    """누락 심볼 1건 — 코퍼스에 등장하나 지원 집합 밖(출처·횟수 병기·Missing Symbol Report 행)."""

    token: str
    kind: str  # "macro" | "glyph"
    occurrences: int
    sources: dict[str, int]


@dataclass(frozen=True, slots=True)
class CoverageReport:
    """커버리지 측정 결과 — 전수 통계 + 누락·베이스라인 대비 신규/해소(정직 회계). 불변."""

    problems_scanned: int
    formulas_scanned: int
    theory_records_scanned: int  # NS-05 — 이론 코퍼스 레코드 수
    macro_occurrence_total: int
    macro_distinct: int
    macro_supported_distinct: int
    glyph_occurrence_total: int
    glyph_distinct: int
    glyph_supported_distinct: int
    missing: tuple[MissingToken, ...]
    new_missing: tuple[MissingToken, ...]  # 베이스라인 밖 누락 — 게이트 위반(exit 1)
    baseline_resolved: tuple[str, ...]  # 베이스라인엔 있으나 이번 측정에 없음(수동 정리 후보)
    # 근거 파일이 부재해 지원 파생에서 제외된 allowlist 매크로(MATH-02 ④ — 공백을 세는 칸).
    # 게이트 판정에 쓰지 않는다: 이건 "코퍼스에 뭐가 빠졌나"가 아니라 "우리 근거가 뭐가 유령인가"다.
    unproven_evidence_macros: tuple[str, ...] = ()

    @property
    def gate_ok(self) -> bool:
        """게이트 판정 — 신규 누락 0이면 통과(베이스라인 내 누락은 리포트만·래칫)."""
        return not self.new_missing


def _missing_for_axis(
    occurrences: dict[str, dict[str, int]], supported: frozenset[str], kind: str
) -> list[MissingToken]:
    """한 축(매크로/글리프)의 누락 목록 — 등장 횟수 내림차순·토큰 오름차순(결정론)."""
    out = [
        MissingToken(
            token=token,
            kind=kind,
            occurrences=sum(per_source.values()),
            sources=dict(sorted(per_source.items())),
        )
        for token, per_source in occurrences.items()
        if token not in supported
    ]
    out.sort(key=lambda m: (-m.occurrences, m.token))
    return out


def evaluate(
    scan: CorpusScan, support: SupportSet, baseline: frozenset[tuple[str, str]]
) -> CoverageReport:
    """스캔 원장 × 지원 집합 × 베이스라인 → 커버리지 판정(순수·IO 0)."""
    missing = _missing_for_axis(scan.macro_occurrences, support.macros, "macro")
    missing += _missing_for_axis(scan.glyph_occurrences, support.glyphs, "glyph")
    missing.sort(key=lambda m: (m.kind, -m.occurrences, m.token))

    new_missing = tuple(m for m in missing if (m.kind, m.token) not in baseline)
    observed_missing = {(m.kind, m.token) for m in missing}
    resolved = tuple(
        sorted(
            f"{kind}:{token}" for kind, token in baseline if (kind, token) not in observed_missing
        )
    )
    return CoverageReport(
        problems_scanned=scan.problems_scanned,
        formulas_scanned=scan.formulas_scanned,
        theory_records_scanned=scan.theory_records_scanned,
        macro_occurrence_total=sum(sum(per.values()) for per in scan.macro_occurrences.values()),
        macro_distinct=len(scan.macro_occurrences),
        macro_supported_distinct=sum(
            1 for token in scan.macro_occurrences if token in support.macros
        ),
        glyph_occurrence_total=sum(sum(per.values()) for per in scan.glyph_occurrences.values()),
        glyph_distinct=len(scan.glyph_occurrences),
        glyph_supported_distinct=sum(
            1 for token in scan.glyph_occurrences if token in support.glyphs
        ),
        missing=tuple(missing),
        new_missing=new_missing,
        baseline_resolved=resolved,
    )


# ──────────────────────────────────────────────────────────────────────────
# 리포트 렌더 (사람 가독) + CLI
# ──────────────────────────────────────────────────────────────────────────
def render_report(report: CoverageReport, *, control_empty_support: bool) -> str:
    """사람 가독 요약 — 전수 통계·누락 목록(전체)·신규/해소·게이트 판정."""
    lines = [
        "=" * 64,
        "표기 커버리지 하네스 (NS-03) — 코퍼스 표기 ⊆ 지원 표기 게이트",
        "=" * 64,
        f"코퍼스: 문항 {report.problems_scanned}건 · 수식 노드 {report.formulas_scanned}건 · "
        f"이론 레코드 {report.theory_records_scanned}건(NS-05)",
        f"매크로: 연 {report.macro_occurrence_total}회 / 고유 {report.macro_distinct}종 "
        f"(지원 {report.macro_supported_distinct}·누락 "
        f"{report.macro_distinct - report.macro_supported_distinct})",
        f"글리프: 연 {report.glyph_occurrence_total}회 / 고유 {report.glyph_distinct}종 "
        f"(지원 {report.glyph_supported_distinct}·누락 "
        f"{report.glyph_distinct - report.glyph_supported_distinct})",
    ]
    if control_empty_support:
        lines.append("[변별력 대조군] 지원 집합 공집합 강제 — exit 1이 나와야 검출기 정상.")
    if report.unproven_evidence_macros:
        # 공백을 숨기지 않고 센다(MATH-02 ④). 게이트 판정과 분리된 별도 줄 — 이 수가 0이 아니라는
        # 것은 "지원집합 일부가 유령 근거 위에 있었다"는 뜻이고, 그만큼 지원에서 빠졌다는 뜻이다.
        lines.append(
            f"[unproven 출처 파생 심볼 {len(report.unproven_evidence_macros)}건 — "
            "근거 파일 부재로 지원 집합에서 제외됨(삭제 아님·격리)]"
        )
        for token in report.unproven_evidence_macros:
            lines.append(f"  {token} — 근거 {_PROVEN_MACRO_EVIDENCE[token]} 부재")
    known_missing = [m for m in report.missing if m not in report.new_missing]
    if known_missing:
        lines.append(f"[누락 심볼 — 베이스라인 내 {len(known_missing)}건(리포트만·래칫)]")
        for m in known_missing:
            lines.append(f"  {m.token} ({m.kind}) x{m.occurrences} — {m.sources}")
    if report.new_missing:
        lines.append(f"[신규 누락 — 게이트 위반 {len(report.new_missing)}건]")
        for m in report.new_missing:
            lines.append(f"  {m.token} ({m.kind}) x{m.occurrences} — {m.sources}")
        lines.append(
            "  → 조치: ①지원으로 승격(렌더 실증 테스트 + manifest/allowlist 등재) 또는 "
            "②의식적 수동 편집으로 베이스라인 등재(공백 인정·Missing Symbol Report)."
        )
    if report.baseline_resolved:
        lines.append(
            f"[베이스라인 해소 {len(report.baseline_resolved)}건 — "
            "수동 편집으로 제거 검토(자동 갱신 없음)]"
        )
        for token in report.baseline_resolved:
            lines.append(f"  {token}")
    lines.append("[게이트 밖 기록 — notation_contract.md §6(측정 축과 별개)]")
    for gap in KNOWN_GAPS_OUT_OF_SCOPE:
        lines.append(f"  - {gap.splitlines()[0][:60]}…")
    verdict = "PASS" if report.gate_ok else "FAIL"
    lines.append(f"게이트 판정(신규 누락 0): {verdict}")
    lines.append("=" * 64)
    return "\n".join(lines)


def _repo_root() -> Path:
    # src/backend/whymath_backend/l3/ → repo root 5단계(harness eval 선례와 동일 깊이).
    return Path(__file__).resolve().parents[4]


def build_json_payload(report: CoverageReport, *, control_empty_support: bool) -> dict[str, Any]:
    """JSON 리포트 페이로드 — 전 통계·누락 목록·known_gaps 메타(§6 전재)."""
    payload: dict[str, Any] = dataclasses.asdict(report)
    payload["gate_ok"] = report.gate_ok
    payload["control_empty_support"] = control_empty_support
    payload["known_gaps_out_of_scope"] = list(KNOWN_GAPS_OUT_OF_SCOPE)
    return payload


def main(argv: list[str] | None = None) -> int:
    """CLI — 코퍼스 표기 커버리지 게이트. exit 0(신규 누락 0)/1(신규 누락 발견)."""
    parser = argparse.ArgumentParser(
        prog="python -m whymath_backend.l3.notation_coverage",
        description=(
            "표기 커버리지 하네스(NS-03) — 코퍼스 표기 ⊆ 지원 표기를 전수 측정하고 "
            "베이스라인 대비 신규 누락 발견 시 exit 1(래칫·hermetic·LLM 0)."
        ),
    )
    parser.add_argument(
        "--corpus-root",
        type=Path,
        default=None,
        help="코퍼스 루트(기본 repo data/corpus) — problem_bank_*/problems.jsonl + "
        "formula_graph_v1/formulas.jsonl + 이론 코퍼스 4종(THEORY_CORPORA·NS-05)을 읽는다.",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=None,
        help="지원 표기 정본(기본 repo data/notation_support_manifest.json).",
    )
    parser.add_argument(
        "--baseline",
        type=Path,
        default=None,
        help="누락 베이스라인(기본 repo data/notation_missing_baseline.json) — 갱신은 수동 편집만.",
    )
    parser.add_argument("--json", type=Path, default=None, help="JSON 리포트 출력 경로(선택).")
    parser.add_argument(
        "--control-empty-support",
        action="store_true",
        help="변별력 대조군 — 지원 집합을 비워 측정(신규 누락이 실측돼 exit 1이어야 정상).",
    )
    args = parser.parse_args(argv)

    root = _repo_root()
    corpus_root: Path = (
        args.corpus_root if args.corpus_root is not None else root / "data" / "corpus"
    )
    manifest_path: Path = (
        args.manifest
        if args.manifest is not None
        else root / "data" / "notation_support_manifest.json"
    )
    baseline_path: Path = (
        args.baseline
        if args.baseline is not None
        else root / "data" / "notation_missing_baseline.json"
    )

    # manifest는 대조군 모드에서도 *먼저* 로드한다(정본 구조 검증 자체는 항상 수행).
    support = load_support_set(manifest_path, repo_root=root)
    _proven, unproven = proven_macros(root)
    if args.control_empty_support:
        support = EMPTY_SUPPORT

    problem_paths = sorted(corpus_root.glob("problem_bank_*/problems.jsonl"))
    scan = scan_corpora(problem_paths, corpus_root / "formula_graph_v1" / "formulas.jsonl")
    scan_theory_corpora(corpus_root, scan)  # NS-05 — 이론 코퍼스 4종을 같은 원장에 누적
    baseline = load_baseline(baseline_path)
    report = dataclasses.replace(
        evaluate(scan, support, baseline),
        unproven_evidence_macros=tuple(sorted(unproven)),
    )

    print(render_report(report, control_empty_support=args.control_empty_support))
    if args.json is not None:
        payload = build_json_payload(report, control_empty_support=args.control_empty_support)
        args.json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"JSON 리포트 저장: {args.json}")
    return _EXIT_OK if report.gate_ok else _EXIT_GATE_FAIL


if __name__ == "__main__":  # pragma: no cover — 모듈 실행 진입점
    sys.exit(main())
