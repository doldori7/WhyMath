"""학생 대면 산문(coach 발화·해설·힌트) 금칙어·PII 배치 스캔 — qa_pipeline 8번째 축(ARCH-24).

배경
----
정본: `docs/architecture/operations_module_gap_review_r2.md` §3 D4(외부 EOS 틀 모듈
45-⑤ "AI 출력 검사 中 금칙어·개인정보" 재점검). 학생에게 실제 전달되는 LLM 산문에 부적절
표현·타인 PII가 섞였는지 검사하는 결정론 검사기가 이 저장소에 0건이었다(전수 grep
"금칙어/banned_word/profanity/blocklist" 무일치 — `qa_pipeline.py`의 `_NOT_MEASURED_AXES`
선언 자체가 유일 히트). 이 모듈이 그 검사기다.

무엇을 스캔하나(학생 대면 산문 필드 — 실측 확인된 정확한 필드명)
-----------------------------------------------------------------
- `data/corpus/problem_bank*/problems.jsonl`의 `question_text`·`answer_explanation`
- `data/corpus/concept_content_v1/content.json`의 `content[].explanation`·`.metaphor`·
  `.formal_definition_internal`
- `data/corpus/misconceptions_v1/misconceptions.json`의 `misconceptions[].
  student_wrong_thinking`·`.correction_point`

검사 축 2개
-----------
1. **금칙어**(사전 기반 — 정규식 아님, 단순 부분문자열 매칭) — `BANNED_WORDS_KO`는 *최소
   스타터 세트*(비속어·차별 표현 8종)이며 **완전성을 주장하지 않는다**. 방대한 사전을
   만드는 것은 이 태스크의 목적이 아니다(과공학 금지, CLAUDE.md) — 확장 지점은 이 상수
   하나뿐이다.
2. **PII**(정규식, `ops/log_scrubber.PII_SHAPE_PATTERNS` 재사용 — 재구현 금지) — 두 방향을
   **별도 카운터**로 구분한다(뭉개지 않는다):
   ① `self_reflection`(학생 자신의 PII 반사) — 학생이 입력한 이메일/전화가 그대로 해설에
      되돌아오는 경우. 이 모듈은 *정적 저작 코퍼스*를 배치로 스캔하므로 연결된 학생 세션이
      없다 — 그래서 `classify_pii_match`가 받는 `known_student_pii`가 이 배치 경로에서는
      항상 빈 집합이고, 그 결과 이 방향은 이번 실행에서 **구조적으로 0건**이다. 침묵 실패
      금지 원칙상 "검사 안 함"이 아니라 "0건 관측"으로 정직하게 드러낸다 — 분류 함수 자체는
      순수·재사용 가능하게 분리해 둬서, 실시간 서빙 경로가 붙을 때(acceptance ⑤ — 배치가
      1단계, 실시간 부착은 별도 판단) 세션의 학생 입력을 `known_student_pii`로 넘기기만 하면
      새 판정 로직 없이 그대로 동작한다.
   ② `third_party`(타인 PII 하드코딩) — 저작 콘텐츠에 실제 이름·전화번호 등이 예시로 박혀
      있는 경우. 이 정적 코퍼스에서 실제로 걸릴 가능성이 있는 축이다.

게이트 — Wilson 단측 상한(점추정 금지)
---------------------------------------
`harness/wilson.py::wilson_upper_bound`로 "금칙어 히트 + third_party PII 히트" 합산
위반률의 상한을 낸다. 이 상한이 `--max-violation-rate-upper`를 넘으면 exit 1.

**기본 임계 0.001(0.1%)의 근거**: acceptance 문구는 "예: 0.0"을 제안했지만, Wilson
상한은 유한 표본에서 수학적으로 절대 정확히 0.0이 될 수 없다(관측 성공 0건이어도
`z²/(2n)` 근방의 양수 — `wilson_upper_bound(0, n, 0.95) > 0` for all finite n>0). 정확히
0.0을 기본값으로 두면 위반이 전혀 없는 코퍼스도 상시 게이트 실패한다. 이 저장소 코퍼스
(2026-08-03 실측, 스캔 대상 필드 7,780건 — problem_bank* 5,294 + concept_content_v1 1,311 +
misconceptions_v1 1,175)의 실제 관측 상한은 위반 0건 기준 ≈0.00035다. 0.001은 여기에 약
3배 여유를 둔 결정론 상수(코퍼스 성장 대비 여유)이며, 실제로 위반이 주입되면(특히 소규모
fixture에서는 표본이 작아 Wilson 상한이 급격히 커진다 — 예: n=5 중 1건이면 상한 ≈0.56)
즉시 초과해 exit 1로 떨어진다.

정직 회계
---------
파싱 실패·필드 타입 위반·필드 부재는 조용히 skip하지 않고 카운트로 드러낸다
(`problem_bank_coverage.py` 관례 미러). 발화 원문·매치된 PII 값 자체는 리포트/detail에
담지 않는다(저작권·프라이버시 위생 — 카운트·라벨만, `log_scrubber.py`의 "타입명만 남긴다"
원칙과 동형).

**LLM 판정 미도입** — 결정론 사전+정규식 1차만(비용·비결정성·자기승인 금지, acceptance ①).
**실시간 서빙 경로 미부착** — 이 모듈은 `problem_bank_coverage.py` 스타일의 hermetic
코퍼스 배치 스캔이다(DB·LLM·HTTP 0, 코퍼스 JSON/JSONL만 읽는다). 서빙 경로 부착은 별도
판단(acceptance ⑤).

사용:
    python -m whymath_backend.harness.banned_words_pii_eval
    python -m whymath_backend.harness.banned_words_pii_eval --json out/banned_words_pii.json
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from whymath_backend.harness.wilson import wilson_upper_bound
from whymath_backend.ops.log_scrubber import PII_SHAPE_PATTERNS

__all__ = [
    "BANNED_WORDS_KO",
    "BannedWordsPiiReport",
    "FieldRecord",
    "FieldScanResult",
    "ParseError",
    "classify_pii_match",
    "discover_fields",
    "load_concept_content_fields",
    "load_misconceptions_fields",
    "load_problem_bank_fields",
    "main",
    "render_report",
    "report_to_json",
    "run",
    "scan_field",
]

_EXIT_OK = 0
_EXIT_GATE_FAIL = 1
_EXIT_INPUT_ERROR = 2

# harness→whymath_backend→backend→src→repo 루트(다른 harness 모듈과 동일 관례 —
# `problem_bank_coverage.py`·`qa_pipeline.py`의 `parents[4]`를 그대로 미러).
_REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_CORPUS_ROOT = _REPO_ROOT / "data" / "corpus"

# 위반률 상한 기본 임계 — 근거는 모듈 docstring "게이트" 절.
_DEFAULT_MAX_VIOLATION_RATE_UPPER = 0.001

# ──────────────────────────────────────────────────────────────────────────
# 금칙어 최소 스타터 세트 — 완전성 주장 안 함. 확장 지점은 여기 하나뿐(과공학 금지).
# 비속어·차별 표현 위주 8종. 방대한 사전 구축은 이 태스크의 목적이 아니다.
# ──────────────────────────────────────────────────────────────────────────
BANNED_WORDS_KO: frozenset[str] = frozenset(
    {
        "시발",
        "씨발",
        "병신",
        "지랄",
        "개새끼",
        "미친놈",
        "죽어버려",
        "등신",
    }
)


# ──────────────────────────────────────────────────────────────────────────
# 입력 모델 — 스캔 대상 산문 필드 1건(불변). 원문은 여기서만 잠깐 들고 있고, 리포트에는
# 카운트만 올라간다(정직 회계 + 프라이버시 위생 양립).
# ──────────────────────────────────────────────────────────────────────────
@dataclass(slots=True, frozen=True)
class ParseError:
    """코퍼스 레코드 1건의 파싱/타입 실패 — 조용히 버리지 않고 보고하기 위한 기록.

    `error_type`은 예외 타입명(CLAUDE.md "침묵 실패 금지"). `detail`에는 문항 본문을 담지
    않는다(저작권·PII 위생 — 필드명·기대 타입 수준만, `problem_bank_coverage.ParseError`와
    동일 원칙).
    """

    corpus: str
    location: str
    error_type: str
    detail: str


@dataclass(slots=True, frozen=True)
class FieldRecord:
    """스캔 대상 산문 필드 1건 — (코퍼스, 필드명, 레코드 식별자, 원문)."""

    corpus: str
    field: str
    record_id: str
    text: str


# ──────────────────────────────────────────────────────────────────────────
# 로더 — 코퍼스 3종(문제은행 JSONL·개념콘텐츠 JSON·오개념 JSON)
# ──────────────────────────────────────────────────────────────────────────
_PROBLEM_BANK_FIELDS: tuple[str, ...] = ("question_text", "answer_explanation")
_CONCEPT_CONTENT_FIELDS: tuple[str, ...] = (
    "explanation",
    "metaphor",
    "formal_definition_internal",
)
_MISCONCEPTION_FIELDS: tuple[str, ...] = ("student_wrong_thinking", "correction_point")


def _extract_string_field(
    obj: dict[str, Any],
    field: str,
    *,
    corpus: str,
    record_id: str,
    fields: list[FieldRecord],
    errors: list[ParseError],
) -> None:
    """`obj[field]`가 문자열이면 `fields`에 적재, 타입 위반이면 `errors`에 카운트(조용한 skip 금지).

    필드 부재(`None`)는 에러가 아니다 — 코퍼스 스키마가 다양해 필드가 없을 수 있고, 이는
    "타입 위반"과 다른 정당한 상태다(`problem_bank_coverage.py`의 None-허용 관례 미러).
    """
    value = obj.get(field)
    if value is None:
        return
    if not isinstance(value, str):
        errors.append(
            ParseError(
                corpus=corpus,
                location=f"{record_id}:{field}",
                error_type="TypeError",
                detail=f"{field}가 문자열이 아님(type={type(value).__name__})",
            )
        )
        return
    fields.append(FieldRecord(corpus=corpus, field=field, record_id=record_id, text=value))


def _load_jsonl_objects(path: Path) -> tuple[list[dict[str, Any]], list[ParseError]]:
    """JSONL 1개 → (object 목록, 파싱 실패 목록). 파일 부재는 빈 결과(에러 아님)."""
    if not path.is_file():
        return [], []
    objects: list[dict[str, Any]] = []
    errors: list[ParseError] = []
    corpus = path.parent.name
    for line_no, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = raw.strip()
        if not stripped:
            continue
        try:
            obj = json.loads(stripped)
            if not isinstance(obj, dict):
                raise TypeError(f"레코드가 object가 아님(type={type(obj).__name__})")
            objects.append(obj)
        except Exception as exc:  # noqa: BLE001 — 라인 단위 격리·예외 타입명을 그대로 보고
            errors.append(
                ParseError(
                    corpus=corpus,
                    location=f"line {line_no}",
                    error_type=type(exc).__name__,
                    detail=str(exc)[:200],
                )
            )
    return objects, errors


def load_problem_bank_fields(corpus_root: Path) -> tuple[list[FieldRecord], list[ParseError]]:
    """`problem_bank*/problems.jsonl`의 `question_text`·`answer_explanation`을 전량 적재."""
    fields: list[FieldRecord] = []
    errors: list[ParseError] = []
    for path in sorted(corpus_root.glob("problem_bank*/problems.jsonl")):
        corpus = path.parent.name
        objects, parse_errors = _load_jsonl_objects(path)
        errors.extend(parse_errors)
        for idx, obj in enumerate(objects):
            record_id = str(obj.get("problem_id") or obj.get("slug") or f"line{idx}")
            for field in _PROBLEM_BANK_FIELDS:
                _extract_string_field(
                    obj,
                    field,
                    corpus=corpus,
                    record_id=record_id,
                    fields=fields,
                    errors=errors,
                )
    return fields, errors


def load_concept_content_fields(corpus_root: Path) -> tuple[list[FieldRecord], list[ParseError]]:
    """`concept_content_v1/content.json`의 `explanation`·`metaphor`·
    `formal_definition_internal`을 전량 적재."""
    corpus = "concept_content_v1"
    path = corpus_root / corpus / "content.json"
    fields: list[FieldRecord] = []
    errors: list[ParseError] = []
    if not path.is_file():
        return fields, errors
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 — 침묵 실패 금지: 예외 타입명 카운트
        errors.append(
            ParseError(
                corpus=corpus,
                location=str(path),
                error_type=type(exc).__name__,
                detail=str(exc)[:200],
            )
        )
        return fields, errors
    items = payload.get("content") if isinstance(payload, dict) else None
    if not isinstance(items, list):
        errors.append(
            ParseError(
                corpus=corpus,
                location=str(path),
                error_type="ValueError",
                detail="'content' 배열이 없음",
            )
        )
        return fields, errors
    for idx, item in enumerate(items):
        if not isinstance(item, dict):
            errors.append(
                ParseError(
                    corpus=corpus,
                    location=f"content[{idx}]",
                    error_type="TypeError",
                    detail=f"object가 아님(type={type(item).__name__})",
                )
            )
            continue
        record_id = str(item.get("code") or f"content[{idx}]")
        for field in _CONCEPT_CONTENT_FIELDS:
            _extract_string_field(
                item, field, corpus=corpus, record_id=record_id, fields=fields, errors=errors
            )
    return fields, errors


def load_misconceptions_fields(corpus_root: Path) -> tuple[list[FieldRecord], list[ParseError]]:
    """`misconceptions_v1/misconceptions.json`의 `student_wrong_thinking`·`correction_point`를
    전량 적재."""
    corpus = "misconceptions_v1"
    path = corpus_root / corpus / "misconceptions.json"
    fields: list[FieldRecord] = []
    errors: list[ParseError] = []
    if not path.is_file():
        return fields, errors
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 — 침묵 실패 금지: 예외 타입명 카운트
        errors.append(
            ParseError(
                corpus=corpus,
                location=str(path),
                error_type=type(exc).__name__,
                detail=str(exc)[:200],
            )
        )
        return fields, errors
    items = payload.get("misconceptions") if isinstance(payload, dict) else None
    if not isinstance(items, list):
        errors.append(
            ParseError(
                corpus=corpus,
                location=str(path),
                error_type="ValueError",
                detail="'misconceptions' 배열이 없음",
            )
        )
        return fields, errors
    for idx, item in enumerate(items):
        if not isinstance(item, dict):
            errors.append(
                ParseError(
                    corpus=corpus,
                    location=f"misconceptions[{idx}]",
                    error_type="TypeError",
                    detail=f"object가 아님(type={type(item).__name__})",
                )
            )
            continue
        record_id = str(item.get("mis_id") or f"misconceptions[{idx}]")
        for field in _MISCONCEPTION_FIELDS:
            _extract_string_field(
                item, field, corpus=corpus, record_id=record_id, fields=fields, errors=errors
            )
    return fields, errors


def discover_fields(corpus_root: Path) -> tuple[list[FieldRecord], list[ParseError]]:
    """코퍼스 3종을 전부 적재해 스캔 대상 필드 목록 + 파싱 실패 목록을 합친다."""
    fields: list[FieldRecord] = []
    errors: list[ParseError] = []
    for loader in (
        load_problem_bank_fields,
        load_concept_content_fields,
        load_misconceptions_fields,
    ):
        loaded_fields, loaded_errors = loader(corpus_root)
        fields.extend(loaded_fields)
        errors.extend(loaded_errors)
    return fields, errors


# ──────────────────────────────────────────────────────────────────────────
# 판정(순수) — 금칙어 부분문자열 + PII 정규식(재사용) 두 방향 분류
# ──────────────────────────────────────────────────────────────────────────


def classify_pii_match(
    matched_text: str, *, known_student_pii: frozenset[str] = frozenset()
) -> Literal["self_reflection", "third_party"]:
    """매치된 PII 형태 문자열의 방향 분류(순수) — 학생 본인 값과 일치하면 self_reflection.

    배치 스캔(이 모듈의 기본 사용 — `run()`)은 `known_student_pii`가 항상 빈 집합이다.
    정적 저작 코퍼스에는 연결된 학생 세션이 없어 "이 값이 그 학생이 입력한 값과 같다"를
    판정할 근거 자체가 없기 때문이다(모듈 docstring "검사 축 2개" ① 참조). 그래도 분류
    로직을 별도 함수로 분리해 둔 이유는, 실시간 서빙 경로가 붙을 때(acceptance ⑤ — 별도
    판단) 세션의 실제 학생 입력 집합을 `known_student_pii`로 넘기기만 하면 새 판정 로직
    신설 없이 이 함수를 그대로 재사용할 수 있게 하기 위함이다.
    """
    if matched_text in known_student_pii:
        return "self_reflection"
    return "third_party"


@dataclass(slots=True, frozen=True)
class FieldScanResult:
    """산문 1건의 스캔 결과(불변) — 히트 여부만(매치 원문은 담지 않는다·프라이버시 위생)."""

    banned_word_hit: bool
    pii_third_party_hit: bool
    pii_self_reflection_hit: bool


def scan_field(text: str, *, known_student_pii: frozenset[str] = frozenset()) -> FieldScanResult:
    """산문 1건을 금칙어(부분문자열) + PII(정규식) 두 축으로 스캔(순수·결정론).

    금칙어는 정규식이 아니라 단순 부분문자열 매칭이다(acceptance ① "정규식 아님" —
    한국어는 ASCII 기준 단어 경계(`\\b`)가 의미 없어 단순 포함 검사가 더 정직하다).
    PII는 `ops.log_scrubber.PII_SHAPE_PATTERNS`(이메일·한국 휴대전화)를 그대로 재사용한다
    (재구현 금지).
    """
    banned_word_hit = any(word in text for word in BANNED_WORDS_KO)
    third_party_hit = False
    self_reflection_hit = False
    for pattern in PII_SHAPE_PATTERNS:
        for match in pattern.finditer(text):
            direction = classify_pii_match(match.group(0), known_student_pii=known_student_pii)
            if direction == "self_reflection":
                self_reflection_hit = True
            else:
                third_party_hit = True
    return FieldScanResult(
        banned_word_hit=banned_word_hit,
        pii_third_party_hit=third_party_hit,
        pii_self_reflection_hit=self_reflection_hit,
    )


# ──────────────────────────────────────────────────────────────────────────
# 집계 — 배치 리포트(순수 코어)
# ──────────────────────────────────────────────────────────────────────────
@dataclass(slots=True, frozen=True)
class BannedWordsPiiReport:
    """배치 스캔 결과 전량(불변) — 정직 회계(`parse_error_count`) + 코퍼스별 분해 포함."""

    fields_scanned: int
    banned_word_hits: int
    pii_third_party_hits: int
    pii_self_reflection_hits: int
    parse_error_count: int
    by_corpus: dict[str, dict[str, int]]

    def violation_rate_upper_bound(self, confidence: float = 0.95) -> float:
        """금칙어+타인PII 위반률 Wilson 단측 상한(점추정 금지) — "낮을수록 좋은" 지표.

        `pii_self_reflection_hits`는 게이트 성공(분자)에 넣지 않는다 — 이 방향은 배치
        스캔에서 구조적으로 항상 0이라(모듈 docstring 참조) 게이트에 넣어도 신호가 없고,
        혼입하면 두 방향을 "별도 카운터로 구분"하라는 acceptance ②를 어기게 된다.
        """
        successes = self.banned_word_hits + self.pii_third_party_hits
        return wilson_upper_bound(successes, self.fields_scanned, confidence)


def run(corpus_root: Path) -> BannedWordsPiiReport:
    """코퍼스 전체를 스캔해 리포트를 낸다(하네스 관례 — `run()`은 순수 집계, I/O는 로더에 위임)."""
    fields, errors = discover_fields(corpus_root)

    banned = third_party = self_reflection = 0
    by_corpus: dict[str, dict[str, int]] = {}
    for record in fields:
        bucket = by_corpus.setdefault(
            record.corpus,
            {
                "fields": 0,
                "banned_word_hits": 0,
                "pii_third_party_hits": 0,
                "pii_self_reflection_hits": 0,
            },
        )
        bucket["fields"] += 1
        result = scan_field(record.text)
        if result.banned_word_hit:
            banned += 1
            bucket["banned_word_hits"] += 1
        if result.pii_third_party_hit:
            third_party += 1
            bucket["pii_third_party_hits"] += 1
        if result.pii_self_reflection_hit:
            self_reflection += 1
            bucket["pii_self_reflection_hits"] += 1

    return BannedWordsPiiReport(
        fields_scanned=len(fields),
        banned_word_hits=banned,
        pii_third_party_hits=third_party,
        pii_self_reflection_hits=self_reflection,
        parse_error_count=len(errors),
        by_corpus=by_corpus,
    )


# ──────────────────────────────────────────────────────────────────────────
# 렌더 — 사람용 요약 + 기계용 JSON
# ──────────────────────────────────────────────────────────────────────────


def render_report(report: BannedWordsPiiReport, *, confidence: float) -> str:
    """사람용 요약 — 발화 원문·매치 값 미출력(카운트·라벨만)."""
    lines = [
        "=" * 64,
        "학생 대면 산문 금칙어·PII 배치 스캔 (ARCH-24) — Wilson 상한 게이트",
        "=" * 64,
        f"스캔 필드: {report.fields_scanned}건 (파싱 실패 {report.parse_error_count}건)",
        f"금칙어 히트: {report.banned_word_hits}건",
        f"타인 PII 하드코딩(third_party) 히트: {report.pii_third_party_hits}건",
        f"학생 본인 PII 반사(self_reflection) 히트: {report.pii_self_reflection_hits}건 "
        "(배치 스캔은 학생 세션 연결이 없어 구조적으로 0 — 실시간 부착은 별도 판단)",
    ]
    if report.fields_scanned > 0:
        upper = report.violation_rate_upper_bound(confidence)
        lines.append(f"위반률(금칙어+타인PII) Wilson 상한({confidence:.0%}): {upper:.6f}")
    if report.by_corpus:
        lines.append("[코퍼스별 분해]")
        for name in sorted(report.by_corpus):
            counts = report.by_corpus[name]
            lines.append(
                f"  {name}: 필드 {counts['fields']} · 금칙어 {counts['banned_word_hits']} · "
                f"타인PII {counts['pii_third_party_hits']} · 본인PII반사 "
                f"{counts['pii_self_reflection_hits']}"
            )
    lines.append("=" * 64)
    return "\n".join(lines)


def report_to_json(report: BannedWordsPiiReport) -> dict[str, Any]:
    """리포트 → JSON 직렬화 가능 dict(순수)."""
    return dataclasses.asdict(report)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m whymath_backend.harness.banned_words_pii_eval",
        description=(
            "학생 대면 산문(coach 발화·해설·힌트) 금칙어·PII 배치 스캔 — 결정론(사전+정규식) "
            "1차, Wilson 단측 상한 게이트(exit 0/1). hermetic(LLM·DB·HTTP 0)."
        ),
    )
    parser.add_argument(
        "--corpus-root",
        type=Path,
        default=DEFAULT_CORPUS_ROOT,
        help=f"코퍼스 루트 디렉터리(기본 {DEFAULT_CORPUS_ROOT}).",
    )
    parser.add_argument("--confidence", type=float, default=0.95, help="Wilson 단측 신뢰수준.")
    parser.add_argument(
        "--max-violation-rate-upper",
        type=float,
        default=_DEFAULT_MAX_VIOLATION_RATE_UPPER,
        help=(
            "위반률(금칙어+타인PII) Wilson 상한 임계 — 초과면 exit 1"
            f"(기본 {_DEFAULT_MAX_VIOLATION_RATE_UPPER}, 근거는 모듈 docstring)."
        ),
    )
    parser.add_argument("--json", type=Path, default=None, help="JSON 리포트 저장 경로(선택).")
    args = parser.parse_args(argv)

    report = run(args.corpus_root)
    print(render_report(report, confidence=args.confidence))

    if args.json is not None:
        payload = report_to_json(report)
        if report.fields_scanned > 0:
            payload["violation_rate_upper_bound"] = report.violation_rate_upper_bound(
                args.confidence
            )
        args.json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"JSON 리포트 저장: {args.json}")

    if report.fields_scanned == 0:
        print(
            f"입력 오류 — 스캔 대상 필드 0건(코퍼스 경로를 확인하세요): {args.corpus_root}",
            file=sys.stderr,
        )
        return _EXIT_INPUT_ERROR

    upper = report.violation_rate_upper_bound(args.confidence)
    gate_ok = upper <= args.max_violation_rate_upper
    verdict = "PASS" if gate_ok else "FAIL"
    print(
        f"게이트 판정(위반률 상한 ≤{args.max_violation_rate_upper}): {verdict} "
        f"(관측 상한={upper:.6f})"
    )
    return _EXIT_OK if gate_ok else _EXIT_GATE_FAIL


if __name__ == "__main__":  # pragma: no cover — 엔트리포인트
    sys.exit(main())
