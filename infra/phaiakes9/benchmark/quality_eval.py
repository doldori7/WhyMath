"""Phaiakes9 — FAST vs MID 로컬 모델 *품질* 평가 하니스 (03a §H 후속1).

L3 라우터의 FAST 호출지점에서 **qwen2-math:1.5b(FAST) vs qwen2-math:7b(MID)**
품질을 비교해, FAST 기본값이 충분한지 / 일부를 MID로 승급(03a §C.2 조정)할지
*결정*하기 위한 평가셋·채점기·러너. `bench_latency.py`(지연 벤치)의 자매 도구로,
구조(데이터클래스·Protocol·lazy import·argparse main)를 미러링한다.

핵심 설계:
    - **결정적(프로그램) 채점.** LLM-as-judge를 쓰지 않는다 — 채점기는 순수 함수
      (set_f1·exact_match·normalize_form)이며 호출지점별로 매핑된다.
    - **모델 호출은 `_OllamaClientProtocol` 경유.** 테스트는 가짜 클라이언트를 주입해
      Ollama·GPU 없이 통과한다. 실제 모델 실행은 Phaiakes9(Ollama·GPU)에서 Kiki가
      수행하며, 테스트/CI는 *순수 로직만* 검증한다(이 컨테이너엔 모델·GPU 없음).
    - **결정 규칙(03a §C.2 조정 신호).** 호출지점별로 FAST 정확도가 MID 정확도에
      충분히 근접(`>= MID_acc - DELTA`)하고 절대 하한(`>= ABS_MIN`)을 넘으면
      "FAST 유지", 아니면 "MID 승급 권고". 임계값은 *문서화된 상수*다(아래 주석).

사용:
    python quality_eval.py [--fast-model qwen2-math:1.5b] [--mid-model qwen2-math:7b]

환경변수:
    WHYMATH_OLLAMA_HOST       ollama 호스트 (디폴트: http://localhost:11434)
    WHYMATH_QEVAL_FAST_MODEL  FAST 모델 ID (디폴트: qwen2-math:1.5b)
    WHYMATH_QEVAL_MID_MODEL   MID 모델 ID (디폴트: qwen2-math:7b)
    WHYMATH_QEVAL_SAMPLES     평가셋 JSON 경로 (디폴트: ./fast_tier_eval.json)
    WHYMATH_QEVAL_OUTPUT      결과 JSON 출력 경로 (디폴트: results/qeval_<ts>.json)
    WHYMATH_QEVAL_NUM_PREDICT 모델당 생성 토큰 한도 (디폴트: 256)

종료 코드:
    0 = 평가 완료 + 모든 호출지점 FAST 유지 권고
    1 = 평가 완료, 1개 이상 호출지점에서 MID 승급 권고
    2 = 에러(평가셋 없음·로드 실패 등)

테스트 가능성:
    - `ollama` Python 클라이언트 호출은 `_OllamaClientProtocol` 추상 인터페이스 경유
    - 단위 테스트에서 `run_evaluation(client=FakeClient(...))` 로 주입 가능
    - 채점기·파서는 순수 함수라 모델 없이 직접 검증 가능
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import platform
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Final, Protocol, cast

# ---- 상수 -------------------------------------------------------------------
DEFAULT_HOST: Final[str] = "http://localhost:11434"
DEFAULT_FAST_MODEL: Final[str] = "qwen2-math:1.5b"
DEFAULT_MID_MODEL: Final[str] = "qwen2-math:7b"
DEFAULT_NUM_PREDICT: Final[int] = 256

# 결정 규칙 임계값 (03a §H 후속1) ----------------------------------------------
# ⚠️ 03a §H 후속1은 이 임계값을 *미확정*으로 남겼다("품질 차이가 충분히 작은지").
# 아래 값은 fabricate가 아니라 *합리적 기본값 + 튜닝 가능*한 시작점이다. Kiki가
# Phaiakes9 실측 후 호출지점별 분포를 보고 보정한다(03a §H 후속1·후속2와 동일).
#
#   DELTA  : FAST가 MID보다 이만큼까지 낮아도 "충분히 근접"으로 본다(상대 허용차).
#            근거: FAST는 비용·지연(p50 1초 vs 4초)에서 압도적이므로, 정확도가
#            소폭(<= 7%p) 낮아도 SLA·throughput 이득이 이를 상쇄한다고 본다.
#            (03a §A.1 — FAST만 SLA 게이트 통과.)
#   ABS_MIN: 호출지점이 학생 노출 전 다른 검증(환각 방어 파이프라인)을 거치더라도,
#            FAST 단독 정확도가 이 하한 미만이면 그 호출지점은 FAST에 부적합으로
#            본다(절대 하한). 0.60 = "최소 다수는 맞아야 한다"는 보수적 기준.
DELTA: Final[float] = 0.07
ABS_MIN: Final[float] = 0.60

# 부동소수점 경계 비교용 허용 오차. 측정 정확도는 float이므로 임계값과의 *정확한*
# 동치(예: 0.60 vs 0.67-0.07)가 FP 잡음으로 뒤집히지 않게 한다(결정 안정성).
_EPS: Final[float] = 1e-9

# 채점기 식별자 (호출지점 → 채점기 매핑) --------------------------------------
GRADER_SET_F1: Final[str] = "set_f1"
GRADER_EXACT: Final[str] = "exact_match"

# 호출지점(03a §B.2 CallSite) → 채점기 매핑.
# CONCEPT_EXTRACT(①)는 개념 *집합* → set_f1(부분 점수).
# TRANSLATE(③)·CONCEPT_ID_MATCH(④)·산술(call_site 없음)은 단일 답 → exact_match.
CALL_SITE_GRADER: Final[dict[str, str]] = {
    "extract": GRADER_SET_F1,  # ① 개념 추출 — 집합 F1
    "translate": GRADER_EXACT,  # ③ 번역·정규화 — 정규형 정확 매칭
    "match": GRADER_EXACT,  # ④ 개념 ID 매칭 — 코드 정확 매칭
    "__arithmetic__": GRADER_EXACT,  # 간단 산술(call_site=null) — 정답 정확 매칭
}
"""호출지점 → 채점기 식별자. call_site가 null이면 '__arithmetic__' 키 사용."""


# ---- 도메인 타입 ------------------------------------------------------------
@dataclass(slots=True, frozen=True)
class EvalItem:
    """평가셋 항목 1건 (fast_tier_eval.json의 items[])."""

    id: str
    call_site: str | None  # 'extract'/'translate'/'match' 또는 None(산술)
    task_type: str
    difficulty: str
    prompt: str
    gold: list[str] | str  # 집합(extract) 또는 단일 문자열(나머지)

    def grader(self) -> str:
        """이 항목에 적용할 채점기 식별자 (CALL_SITE_GRADER 매핑)."""
        key = self.call_site if self.call_site is not None else "__arithmetic__"
        return CALL_SITE_GRADER.get(key, GRADER_EXACT)


@dataclass(slots=True, frozen=True)
class ItemScore:
    """한 모델이 한 항목을 푼 채점 결과."""

    item_id: str
    call_site: str | None
    grader: str
    score: float  # 0.0~1.0 (exact는 0/1, set_f1은 F1)
    correct: bool  # score >= 정답 임계(exact는 1.0, set_f1은 F1==1.0)
    raw_response: str
    parsed: list[str] | str  # 파서가 추출한 답
    error: str | None = None


@dataclass(slots=True)
class CallSiteAggregate:
    """한 모델의 한 호출지점(또는 산술 그룹) 집계."""

    call_site: str  # 'extract'/'translate'/'match'/'__arithmetic__'
    grader: str
    n_items: int
    mean_score: float  # 평균 점수(set_f1은 평균 F1)
    accuracy: float  # correct 비율(exact_match류 정확도)
    n_errors: int


@dataclass(slots=True)
class ModelResult:
    """한 모델(FAST 또는 MID)의 전체 평가 결과."""

    model: str
    role: str  # 'fast' 또는 'mid'
    item_scores: list[ItemScore]
    by_call_site: list[CallSiteAggregate]


@dataclass(slots=True)
class CallSiteVerdict:
    """한 호출지점에 대한 FAST vs MID 비교 판정 (결정 규칙)."""

    call_site: str
    grader: str
    fast_accuracy: float
    mid_accuracy: float
    delta: float  # DELTA 상수(허용 상대차)
    abs_min: float  # ABS_MIN 상수(절대 하한)
    keep_fast: bool  # True=FAST 유지, False=MID 승급 권고
    verdict: str  # 사람이 읽는 한 줄 판정


@dataclass(slots=True)
class EvaluationReport:
    """최종 품질 평가 보고서. JSON 직렬화 대상."""

    timestamp: str
    fast_model: str
    mid_model: str
    host: str
    machine: dict[str, Any]
    n_items: int
    num_predict: int
    delta: float
    abs_min: float
    fast_result: ModelResult
    mid_result: ModelResult
    verdicts: list[CallSiteVerdict]
    overall_keep_fast: bool  # 모든 호출지점에서 FAST 유지면 True


# ---- Ollama 클라이언트 추상화 (테스트 주입용) -------------------------------
class _OllamaClientProtocol(Protocol):
    """ollama 비동기 클라이언트의 최소 인터페이스.

    실제 `ollama.AsyncClient` 와 동형이지만, 테스트에서는 임의 객체로 대체 가능.
    """

    async def generate(  # noqa: D401 — 외부 라이브러리 시그니처 보존
        self,
        model: str,
        prompt: str,
        stream: bool = False,
        options: dict[str, Any] | None = None,
    ) -> dict[str, Any]: ...


def _build_default_client(host: str) -> _OllamaClientProtocol:
    """기본 ollama AsyncClient 생성. import 실패 시 명확한 에러.

    `ollama` import는 *이 함수 안에서만* 한다(모듈 최상단 X). stdlib만으로 모듈을
    로드 가능하게 하여, 테스트가 Ollama 미설치 환경에서도 동작하도록 보장한다.
    importlib로 동적 로드하여, ollama 타입 스텁 유무와 무관하게 mypy --strict를
    통과한다. 실제 `ollama.AsyncClient`는 `.get(...)` 가능한 응답을 돌려주므로
    `_OllamaClientProtocol`과 런타임 동형이며, cast로 명시 연결한다.
    """
    import importlib

    try:
        ollama = importlib.import_module("ollama")
    except ImportError as exc:  # pragma: no cover — 환경 의존
        raise RuntimeError(
            "ollama Python 클라이언트가 설치되지 않았습니다. "
            "`pip install ollama` 후 다시 실행하세요."
        ) from exc
    client = ollama.AsyncClient(host=host)
    return cast("_OllamaClientProtocol", client)


# ---- 평가셋 로드 ------------------------------------------------------------
def load_items(path: Path) -> list[EvalItem]:
    """fast_tier_eval.json 에서 평가 항목 로드.

    각 항목은 id·call_site·task_type·difficulty·prompt·gold 를 가진다.
    gold는 call_site=='extract'이면 list[str], 그 외에는 str 이어야 한다.
    """
    raw = json.loads(path.read_text(encoding="utf-8"))
    items = raw.get("items", [])
    result: list[EvalItem] = []
    for it in items:
        call_site = it.get("call_site")
        gold = it["gold"]
        result.append(
            EvalItem(
                id=str(it["id"]),
                call_site=str(call_site) if call_site is not None else None,
                task_type=str(it.get("task_type", "")),
                difficulty=str(it.get("difficulty", "")),
                prompt=str(it["prompt"]),
                gold=list(gold) if isinstance(gold, list) else str(gold),
            )
        )
    return result


def detect_machine() -> dict[str, Any]:
    """현재 머신의 기본 사양을 best-effort로 수집 (bench_latency.py와 동일)."""
    info: dict[str, Any] = {
        "platform": platform.platform(),
        "python_version": platform.python_version(),
        "machine": platform.machine(),
    }
    # /proc/cpuinfo 에서 모델명 추출 (Linux만)
    try:
        cpu_path = Path("/proc/cpuinfo")
        if cpu_path.exists():
            for line in cpu_path.read_text(encoding="utf-8", errors="ignore").splitlines():
                if line.startswith("model name"):
                    info["cpu"] = line.split(":", 1)[1].strip()
                    break
    except OSError:
        pass
    # /proc/meminfo 에서 메모리 (GB) 추출
    try:
        mem_path = Path("/proc/meminfo")
        if mem_path.exists():
            for line in mem_path.read_text(encoding="utf-8", errors="ignore").splitlines():
                if line.startswith("MemTotal:"):
                    kb = int(line.split()[1])
                    info["ram_gb"] = round(kb / 1024 / 1024, 1)
                    break
    except (OSError, ValueError, IndexError):
        pass
    return info


# ---- 정규화·파서 (순수 함수) ------------------------------------------------
# 연산자 주변 공백을 한 칸으로 통일하기 위한 토큰 패턴.
_OPERATOR_PATTERN: Final[str] = r"(<=|>=|!=|==|[-+*/=<>])"


def normalize_form(text: str) -> str:
    """수식·답 문자열을 정규화한다 (결정적 채점의 기준).

    규칙(파서 가정):
      1. 양끝 공백 제거(strip), 소문자화(lower).
      2. 유니코드 비교 연산자(≤·≥·≠·×·÷)를 ASCII(<=·>=·!=·*·/)로 치환.
      3. 모든 공백을 제거한 뒤, 이항 연산자 주위에 공백 한 칸을 *재삽입*하여
         'x^2+3x-4' 와 'x^2 + 3x - 4' 가 같은 정규형이 되도록 한다.
      4. 곱셈 별표 'x*y' 와 'x * y' 도 동일하게 정규화된다.

    주의: 단항 음수(예: '-2')도 이 규칙에서 ' - 2'가 되지만, gold와 모델 출력에
    *동일하게* 적용되므로 매칭에는 문제가 없다(정규화는 양쪽에 똑같이 적용).
    """
    s = text.strip().lower()
    # 유니코드 연산자 → ASCII
    replacements = {
        "≤": "<=",
        "≥": ">=",
        "≠": "!=",
        "×": "*",
        "÷": "/",
        "−": "-",  # 유니코드 마이너스(U+2212) → 하이픈
    }
    for src, dst in replacements.items():
        s = s.replace(src, dst)
    # 모든 공백 제거
    s = re.sub(r"\s+", "", s)
    # 이항 연산자 주위 공백 한 칸 재삽입 → 표기 변형 흡수
    s = re.sub(_OPERATOR_PATTERN, r" \1 ", s)
    # 연산자 재삽입으로 생긴 중복 공백 정리
    s = re.sub(r"\s+", " ", s).strip()
    return s


def normalize_concept(text: str) -> str:
    """개념 이름을 정규화한다 (집합 비교용).

    규칙: strip + lower + *모든 공백 제거*. '곱셈 공식'과 '곱셈공식', '근의 공식'과
    '근의공식'을 같게 취급한다(한국어 띄어쓰기 변형 흡수). 연산자 처리는 하지 않는다.
    """
    return re.sub(r"\s+", "", text.strip().lower())


def parse_concept_list(raw: str) -> list[str]:
    """모델 응답에서 개념 *리스트*를 추출한다 (CONCEPT_EXTRACT ①).

    파서 가정(프롬프트가 "개념을 쉼표로 나열" 지시):
      - 응답의 *마지막 비어있지 않은 줄*을 답 줄로 본다(앞선 설명 줄 무시).
      - 'ANSWER:'·'개념:' 등 접두 라벨이 있으면 콜론 뒤만 취한다.
      - 쉼표(,) 또는 한국어 가운뎃점(·)·세미콜론(;)으로 분할한다.
      - 각 항목을 strip 하고 빈 항목·번호 접두("1.", "-")를 제거한다.
    """
    line = _last_answer_line(raw)
    line = _strip_label(line)
    # 쉼표·가운뎃점·세미콜론으로 분할
    parts = re.split(r"[,·;]", line)
    out: list[str] = []
    for p in parts:
        cleaned = _strip_list_bullet(p).strip()
        if cleaned:
            out.append(cleaned)
    return out


def parse_single_answer(raw: str) -> str:
    """모델 응답에서 *단일 답*을 추출한다 (TRANSLATE·MATCH·산술).

    파서 가정(프롬프트가 "답만 마지막 줄에 'ANSWER:' 뒤에" 지시):
      - 응답에 'ANSWER:' 라벨이 있으면 *마지막* 'ANSWER:' 뒤 텍스트를 취한다.
      - 없으면 *마지막 비어있지 않은 줄* 전체를 답으로 본다.
      - 결과를 strip 한다(정규화는 채점기에서 수행).
    """
    # 마지막 ANSWER: 라벨 우선
    matches = list(re.finditer(r"(?:answer|정답)\s*[:：]\s*", raw, flags=re.IGNORECASE))
    if matches:
        last = matches[-1]
        tail = raw[last.end() :]
        # 라벨 뒤 첫 줄만(여러 줄이면 첫 줄)
        first_line = tail.splitlines()[0] if tail.splitlines() else tail
        return first_line.strip()
    return _last_answer_line(raw)


def _last_answer_line(raw: str) -> str:
    """응답의 마지막 비어있지 않은 줄을 반환(없으면 빈 문자열)."""
    lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
    return lines[-1] if lines else ""


def _strip_label(line: str) -> str:
    """'ANSWER:'·'개념:' 등 선두 라벨을 제거하고 콜론 뒤만 반환."""
    m = re.match(r"\s*(?:answer|정답|개념|concepts?)\s*[:：]\s*(.*)$", line, flags=re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return line


def _strip_list_bullet(part: str) -> str:
    """'1.'·'-'·'*' 등 목록 글머리표를 제거."""
    return re.sub(r"^\s*(?:\d+[.)]|[-*•])\s*", "", part)


# ---- 채점기 (순수 함수) -----------------------------------------------------
def exact_match(parsed: str, gold: str) -> float:
    """정규화 후 정확 매칭 → 1.0 또는 0.0 (TRANSLATE·MATCH·산술).

    수식류(연산자 포함)와 코드/숫자 모두 normalize_form으로 정규화해 비교한다.
    """
    return 1.0 if normalize_form(parsed) == normalize_form(gold) else 0.0


def set_f1(parsed: list[str], gold: list[str]) -> float:
    """개념 *집합* F1 점수 (CONCEPT_EXTRACT ①).

    parsed·gold를 normalize_concept으로 정규화한 *집합*으로 만든 뒤
    precision/recall의 조화평균(F1)을 반환한다. 부분 점수를 준다.
    빈 집합 처리: gold가 비면 정의 불가 → parsed도 비면 1.0, 아니면 0.0.
    """
    p_set = {normalize_concept(x) for x in parsed if x.strip()}
    g_set = {normalize_concept(x) for x in gold if x.strip()}
    if not g_set:
        return 1.0 if not p_set else 0.0
    if not p_set:
        return 0.0
    tp = len(p_set & g_set)
    if tp == 0:
        return 0.0
    precision = tp / len(p_set)
    recall = tp / len(g_set)
    return 2 * precision * recall / (precision + recall)


def set_f1_parts(parsed: list[str], gold: list[str]) -> tuple[float, float, float]:
    """set_f1의 (precision, recall, f1) 3요소 반환 — 디버깅·리포트용."""
    p_set = {normalize_concept(x) for x in parsed if x.strip()}
    g_set = {normalize_concept(x) for x in gold if x.strip()}
    if not g_set:
        v = 1.0 if not p_set else 0.0
        return v, v, v
    if not p_set:
        return 0.0, 0.0, 0.0
    tp = len(p_set & g_set)
    if tp == 0:
        return 0.0, 0.0, 0.0
    precision = tp / len(p_set)
    recall = tp / len(g_set)
    f1 = 2 * precision * recall / (precision + recall)
    return precision, recall, f1


def grade_item(item: EvalItem, raw_response: str) -> ItemScore:
    """한 항목의 raw 응답을 파싱·채점한다 (호출지점별 채점기 디스패치).

    - extract → parse_concept_list + set_f1 (correct = F1 == 1.0).
    - translate/match/산술 → parse_single_answer + exact_match (correct = 1.0).
    파싱·채점 중 예외는 score=0.0·error 로 흡수한다(러너가 죽지 않도록).
    """
    grader = item.grader()
    try:
        if grader == GRADER_SET_F1:
            assert isinstance(item.gold, list)
            parsed_list = parse_concept_list(raw_response)
            score = set_f1(parsed_list, item.gold)
            return ItemScore(
                item_id=item.id,
                call_site=item.call_site,
                grader=grader,
                score=score,
                correct=score >= 1.0,
                raw_response=raw_response,
                parsed=parsed_list,
            )
        # exact_match류
        assert isinstance(item.gold, str)
        parsed_one = parse_single_answer(raw_response)
        score = exact_match(parsed_one, item.gold)
        return ItemScore(
            item_id=item.id,
            call_site=item.call_site,
            grader=grader,
            score=score,
            correct=score >= 1.0,
            raw_response=raw_response,
            parsed=parsed_one,
        )
    except Exception as exc:  # noqa: BLE001 — 채점 오류를 결과로 흡수
        return ItemScore(
            item_id=item.id,
            call_site=item.call_site,
            grader=grader,
            score=0.0,
            correct=False,
            raw_response=raw_response,
            parsed="",
            error=f"{type(exc).__name__}: {exc}",
        )


# ---- 집계 (순수 함수) -------------------------------------------------------
def _group_key(score: ItemScore) -> str:
    """집계 그룹 키 — call_site가 없으면 '__arithmetic__'."""
    return score.call_site if score.call_site is not None else "__arithmetic__"


def aggregate_by_call_site(scores: list[ItemScore]) -> list[CallSiteAggregate]:
    """호출지점(또는 산술 그룹)별로 평균 점수·정확도·에러 수를 집계한다.

    그룹 키 순서를 안정화(정렬)하여 보고서 재현성을 확보한다.
    """
    groups: dict[str, list[ItemScore]] = {}
    for s in scores:
        groups.setdefault(_group_key(s), []).append(s)

    out: list[CallSiteAggregate] = []
    for key in sorted(groups):
        bucket = groups[key]
        n = len(bucket)
        mean_score = sum(s.score for s in bucket) / n if n else 0.0
        accuracy = sum(1 for s in bucket if s.correct) / n if n else 0.0
        n_errors = sum(1 for s in bucket if s.error is not None)
        grader = bucket[0].grader if bucket else GRADER_EXACT
        out.append(
            CallSiteAggregate(
                call_site=key,
                grader=grader,
                n_items=n,
                mean_score=round(mean_score, 4),
                accuracy=round(accuracy, 4),
                n_errors=n_errors,
            )
        )
    return out


# ---- 결정 규칙 (03a §C.2 조정 신호) -----------------------------------------
def decide_call_site(
    call_site: str,
    grader: str,
    fast_accuracy: float,
    mid_accuracy: float,
    *,
    delta: float = DELTA,
    abs_min: float = ABS_MIN,
) -> CallSiteVerdict:
    """한 호출지점에 대해 FAST 유지 / MID 승급을 판정한다 (결정 규칙).

    규칙(03a §H 후속1 — 임계값은 문서화된 상수, 위 DELTA/ABS_MIN 주석 참조):
      keep_fast := (fast_accuracy >= mid_accuracy - delta)
                   AND (fast_accuracy >= abs_min)

    - 첫 조건: FAST가 MID에 *충분히 근접*(상대 허용차 delta 이내).
    - 둘째 조건: FAST가 *절대 하한* abs_min 이상(근접해도 둘 다 낮으면 부적합).
    둘 다 만족해야 FAST 유지. 아니면 MID 승급 권고(C.2 결정표에서 해당 호출지점의
    기본 FAST → MID로 조정).
    """
    # _EPS 허용 오차로 경계 동치를 안정화(FP 잡음 방지).
    near_mid = fast_accuracy >= (mid_accuracy - delta) - _EPS
    above_floor = fast_accuracy >= abs_min - _EPS
    keep_fast = near_mid and above_floor

    if keep_fast:
        verdict = (
            f"FAST 유지: FAST 정확도 {fast_accuracy:.2%} ≥ MID {mid_accuracy:.2%} - "
            f"{delta:.0%} 이고 절대 하한 {abs_min:.0%} 충족."
        )
    elif not above_floor:
        verdict = (
            f"MID 승급 권고: FAST 정확도 {fast_accuracy:.2%} 가 절대 하한 "
            f"{abs_min:.0%} 미달 — 이 호출지점은 FAST에 부적합."
        )
    else:
        verdict = (
            f"MID 승급 권고: FAST 정확도 {fast_accuracy:.2%} 가 MID {mid_accuracy:.2%} 에 "
            f"비해 {delta:.0%} 초과로 낮음 — C.2에서 이 호출지점을 MID로 조정 권고."
        )

    return CallSiteVerdict(
        call_site=call_site,
        grader=grader,
        fast_accuracy=round(fast_accuracy, 4),
        mid_accuracy=round(mid_accuracy, 4),
        delta=delta,
        abs_min=abs_min,
        keep_fast=keep_fast,
        verdict=verdict,
    )


def build_verdicts(
    fast_aggs: list[CallSiteAggregate],
    mid_aggs: list[CallSiteAggregate],
    *,
    delta: float = DELTA,
    abs_min: float = ABS_MIN,
) -> list[CallSiteVerdict]:
    """FAST·MID 집계를 호출지점별로 짝지어 판정 목록을 만든다.

    한쪽에만 있는 호출지점은 상대 정확도 0.0으로 간주(보수적). 정렬된 키 순서.
    """
    fast_map = {a.call_site: a for a in fast_aggs}
    mid_map = {a.call_site: a for a in mid_aggs}
    keys = sorted(set(fast_map) | set(mid_map))

    verdicts: list[CallSiteVerdict] = []
    for key in keys:
        fa = fast_map.get(key)
        ma = mid_map.get(key)
        fast_acc = fa.accuracy if fa else 0.0
        mid_acc = ma.accuracy if ma else 0.0
        grader = (fa or ma).grader if (fa or ma) else GRADER_EXACT  # type: ignore[union-attr]
        verdicts.append(
            decide_call_site(key, grader, fast_acc, mid_acc, delta=delta, abs_min=abs_min)
        )
    return verdicts


# ---- 호출 실행 --------------------------------------------------------------
async def _call_once(
    client: _OllamaClientProtocol,
    model: str,
    item: EvalItem,
    num_predict: int,
) -> str:
    """단일 generate 호출. 응답 텍스트만 반환(예외는 상위로 전파하지 않음).

    실패 시 빈 문자열 대신 'ERROR: ...' 문자열을 반환하여 채점기가 0점 처리한다.
    """
    try:
        response = await client.generate(
            model=model,
            prompt=item.prompt,
            stream=False,
            options={"num_predict": num_predict},
        )
        return str(response.get("response", ""))
    except Exception as exc:  # noqa: BLE001 — 모든 오류를 결과 문자열로 흡수
        return f"ERROR: {type(exc).__name__}: {exc}"


async def _evaluate_model(
    client: _OllamaClientProtocol,
    model: str,
    role: str,
    items: list[EvalItem],
    num_predict: int,
) -> ModelResult:
    """한 모델로 전체 항목을 순차 평가(호출 → 채점 → 집계).

    순차 호출인 이유: 품질 평가는 throughput이 목적이 아니라 *결정성*이 중요하고,
    GPU 단일 점유 모델(특히 MID)에서 동시 호출은 의미가 없다(03a §A.1).
    """
    scores: list[ItemScore] = []
    for item in items:
        raw = await _call_once(client, model, item, num_predict)
        scores.append(grade_item(item, raw))
    return ModelResult(
        model=model,
        role=role,
        item_scores=scores,
        by_call_site=aggregate_by_call_site(scores),
    )


# ---- 공개 API ---------------------------------------------------------------
async def run_evaluation(
    *,
    fast_model: str,
    mid_model: str,
    items: list[EvalItem],
    host: str = DEFAULT_HOST,
    num_predict: int = DEFAULT_NUM_PREDICT,
    delta: float = DELTA,
    abs_min: float = ABS_MIN,
    client: _OllamaClientProtocol | None = None,
) -> EvaluationReport:
    """FAST vs MID 품질 평가 1회 수행. 단위 테스트는 client 인자로 주입.

    Args:
        fast_model: FAST 모델 ID(qwen2-math:1.5b).
        mid_model: MID 모델 ID(qwen2-math:7b).
        items: 평가 항목 리스트.
        host: ollama 호스트(client 미주입 시 사용).
        num_predict: 호출당 생성 토큰 한도.
        delta: 결정 규칙 상대 허용차(기본 DELTA).
        abs_min: 결정 규칙 절대 하한(기본 ABS_MIN).
        client: 테스트에서 주입하는 모의 클라이언트. None이면 기본 생성.

    Returns:
        EvaluationReport(JSON 직렬화 가능).
    """
    if not items:
        raise ValueError("평가 항목이 비어 있습니다. fast_tier_eval.json 확인.")

    real_client = client if client is not None else _build_default_client(host)

    fast_result = await _evaluate_model(real_client, fast_model, "fast", items, num_predict)
    mid_result = await _evaluate_model(real_client, mid_model, "mid", items, num_predict)

    verdicts = build_verdicts(
        fast_result.by_call_site,
        mid_result.by_call_site,
        delta=delta,
        abs_min=abs_min,
    )
    overall_keep_fast = all(v.keep_fast for v in verdicts)

    return EvaluationReport(
        timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        fast_model=fast_model,
        mid_model=mid_model,
        host=host,
        machine=detect_machine(),
        n_items=len(items),
        num_predict=num_predict,
        delta=delta,
        abs_min=abs_min,
        fast_result=fast_result,
        mid_result=mid_result,
        verdicts=verdicts,
        overall_keep_fast=overall_keep_fast,
    )


def report_to_dict(report: EvaluationReport) -> dict[str, Any]:
    """EvaluationReport → JSON 직렬화 가능 dict."""
    return asdict(report)


# ---- CLI --------------------------------------------------------------------
def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Phaiakes9 FAST vs MID 로컬 모델 품질 평가 (WhyMath 03a §H 후속1)",
    )
    p.add_argument(
        "--fast-model",
        default=os.environ.get("WHYMATH_QEVAL_FAST_MODEL", DEFAULT_FAST_MODEL),
        help=f"FAST 모델 ID (디폴트: {DEFAULT_FAST_MODEL})",
    )
    p.add_argument(
        "--mid-model",
        default=os.environ.get("WHYMATH_QEVAL_MID_MODEL", DEFAULT_MID_MODEL),
        help=f"MID 모델 ID (디폴트: {DEFAULT_MID_MODEL})",
    )
    p.add_argument(
        "--host",
        default=os.environ.get("WHYMATH_OLLAMA_HOST", DEFAULT_HOST),
        help=f"ollama 호스트 (디폴트: {DEFAULT_HOST})",
    )
    p.add_argument(
        "--samples",
        type=Path,
        default=Path(
            os.environ.get(
                "WHYMATH_QEVAL_SAMPLES",
                str(Path(__file__).parent / "fast_tier_eval.json"),
            )
        ),
        help="평가셋 JSON 경로",
    )
    _out_env = os.environ.get("WHYMATH_QEVAL_OUTPUT", "").strip()
    p.add_argument(
        "--out",
        type=Path,
        # 빈 문자열이면 None(→ _default_output_path 사용). Path("")는 PosixPath('.')
        # 로 평가되어 디렉터리에 쓰려다 실패하므로, 명시적으로 None을 둔다.
        default=Path(_out_env) if _out_env else None,
        help="결과 JSON 경로 (미지정 시 ./results/qeval_<ts>.json)",
    )
    p.add_argument(
        "--num-predict",
        type=int,
        default=int(os.environ.get("WHYMATH_QEVAL_NUM_PREDICT", DEFAULT_NUM_PREDICT)),
        help=f"호출당 생성 토큰 한도 (디폴트: {DEFAULT_NUM_PREDICT})",
    )
    p.add_argument(
        "--delta",
        type=float,
        default=DELTA,
        help=f"결정 규칙 상대 허용차 (디폴트: {DELTA})",
    )
    p.add_argument(
        "--abs-min",
        type=float,
        default=ABS_MIN,
        help=f"결정 규칙 절대 하한 (디폴트: {ABS_MIN})",
    )
    return p


def _default_output_path() -> Path:
    """results/qeval_YYYY-MM-DD_HHMMSS.json"""
    ts = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    base = Path(__file__).parent.parent / "results"
    base.mkdir(parents=True, exist_ok=True)
    return base / f"qeval_{ts}.json"


def _print_summary(report: EvaluationReport) -> None:
    """사람이 읽는 호출지점별 판정 요약을 stdout에 출력."""
    print()
    print("[qeval] ─────────────────────────────────────")
    print(f"[qeval] FAST 모델: {report.fast_model}")
    print(f"[qeval] MID  모델: {report.mid_model}")
    print(f"[qeval] 결정 규칙: DELTA={report.delta} ABS_MIN={report.abs_min}")
    print("[qeval] 호출지점별 판정:")
    for v in report.verdicts:
        flag = "✅ FAST 유지" if v.keep_fast else "⬆️  MID 승급 권고"
        print(
            f"[qeval]   - {v.call_site} ({v.grader}): "
            f"FAST {v.fast_accuracy:.2%} vs MID {v.mid_accuracy:.2%} → {flag}"
        )
        print(f"[qeval]     {v.verdict}")
    overall = "✅ 전부 FAST 유지" if report.overall_keep_fast else "⬆️  일부 MID 승급 권고"
    print(f"[qeval] 종합: {overall}")


def main(argv: list[str] | None = None) -> int:
    """엔트리포인트. 종료 코드: 0=전부 FAST 유지, 1=일부 MID 승급 권고, 2=에러."""
    args = _build_arg_parser().parse_args(argv)

    if not args.samples.exists():
        print(f"[qeval] ❌ 평가셋 파일 없음: {args.samples}", file=sys.stderr)
        return 2

    items = load_items(args.samples)
    if not items:
        print(f"[qeval] ❌ 평가셋이 비어 있음: {args.samples}", file=sys.stderr)
        return 2

    print(f"[qeval] FAST 모델: {args.fast_model}")
    print(f"[qeval] MID  모델: {args.mid_model}")
    print(f"[qeval] 호스트: {args.host}")
    print(f"[qeval] 항목 수: {len(items)}")
    print(f"[qeval] num_predict: {args.num_predict}")
    print()

    try:
        report = asyncio.run(
            run_evaluation(
                fast_model=args.fast_model,
                mid_model=args.mid_model,
                items=items,
                host=args.host,
                num_predict=args.num_predict,
                delta=args.delta,
                abs_min=args.abs_min,
            )
        )
    except Exception as exc:  # noqa: BLE001
        print(f"[qeval] ❌ 평가 실패: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    out_path = args.out or _default_output_path()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(report_to_dict(report), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    _print_summary(report)
    print(f"[qeval] 결과 저장: {out_path}")

    return 0 if report.overall_keep_fast else 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
