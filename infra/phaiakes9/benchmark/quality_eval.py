"""Phaiakes9 — FAST vs MID 로컬 모델 *품질* 평가 하니스 (03a §H 후속1).

L3 라우터의 FAST 호출지점에서 로컬 소형(FAST) vs 대형(MID) 모델 품질을 비교해,
FAST 기본값이 충분한지 / 일부를 MID로 승급(03a §C.2 조정)할지 *결정*하기 위한
평가셋·채점기·러너. `bench_latency.py`(지연 벤치)의 자매 도구로, 구조(데이터클래스·
Protocol·lazy import·argparse main)를 미러링한다.

**태스크 패밀리 인지(task-aware) 모델 매핑 — 이 하니스의 핵심 설계:**
    Phaiakes9 실측이 드러낸 근본 결함은 *모델 패밀리*(수학 특화 vs 일반)와 *태스크*의
    불일치였다. 정보 추출(extract)·표기 정규화(translate)·코드 매칭(match)은 본질이
    NLP 작업이라, 수학 풀이 특화 모델(qwen2-math)은 7b조차 거의 0%였다. 즉 "1.5b vs
    7b 크기" 문제가 아니라 *모델 패밀리가 태스크와 안 맞은 것*이었다. 그래서 항목을
    두 패밀리로 가른다:
      - **NLP**: call_site ∈ {extract, translate, match} → 일반 모델(qwen2.5).
      - **MATH**: call_site is None(산술) → 수학 특화 모델(qwen2-math).
    러너는 *각 항목의 패밀리*에 맞는 (fast, mid) 모델 쌍으로 호출한다. 따라서 결과의
    FAST 열 = 패밀리별 소형, MID 열 = 패밀리별 대형이며, 각 패밀리는 자기에게 맞는
    모델로만 평가된다. 패밀리별 (fast, mid) 모델은 CLI/env로 설정 가능하다(아래).

핵심 설계:
    - **결정적(프로그램) 채점.** LLM-as-judge를 쓰지 않는다 — 채점기는 순수 함수
      (set_f1·exact_match·normalize_form)이며 호출지점별로 매핑된다.
    - **결정성(재현 가능 측정).** LLM 샘플링은 비결정적이라 실행마다 점수가 출렁인다
      (실측 산술 37~62%). _call_once는 generate options에 temperature=0을 넣어
      실행 간 변동을 제거한다(측정 안정성).
    - **모델 호출은 `_OllamaClientProtocol` 경유.** 테스트는 가짜 클라이언트를 주입해
      Ollama·GPU 없이 통과한다. 실제 모델 실행은 Phaiakes9(Ollama·GPU)에서 Kiki가
      수행하며, 테스트/CI는 *순수 로직만* 검증한다(이 컨테이너엔 모델·GPU 없음).
    - **결정 규칙(03a §C.2 조정 신호).** 호출지점별로 FAST 정확도가 MID 정확도에
      충분히 근접(`>= MID_acc - DELTA`)하고 절대 하한(`>= ABS_MIN`)을 넘으면
      "FAST 유지", 아니면 "MID 승급 권고". 임계값은 *문서화된 상수*다(아래 주석).

호스트:
    기본·권장 호스트는 `127.0.0.1:11434`(Windows Native GPU Ollama) — DEFAULT_HOST는
    `http://localhost:11434`로 이를 가리킨다. ⚠️ 경고: `172.17.112.1`은 WSL2 CPU
    Ollama라 *속도만* 느릴 뿐 정확도(품질 측정 결과)에는 영향이 없다 — 품질 측정은
    어느 호스트에서든 동일한 결론을 내야 한다(temperature=0 결정성 + 결정적 채점).

사용:
    # 패밀리별 (fast, mid) 모델을 따로 지정(기본값은 아래 DEFAULT_*):
    python quality_eval.py \\
        [--math-fast qwen2-math:1.5b] [--math-mid qwen2-math:7b] \\
        [--nlp-fast qwen2.5:3b]       [--nlp-mid qwen2.5:7b]

환경변수:
    WHYMATH_OLLAMA_HOST       ollama 호스트 (디폴트: http://localhost:11434)
    WHYMATH_QEVAL_MATH_FAST   MATH 패밀리 FAST 모델 (디폴트: qwen2-math:1.5b)
    WHYMATH_QEVAL_MATH_MID    MATH 패밀리 MID  모델 (디폴트: qwen2-math:7b)
    WHYMATH_QEVAL_NLP_FAST    NLP  패밀리 FAST 모델 (디폴트: qwen2.5:3b)
    WHYMATH_QEVAL_NLP_MID     NLP  패밀리 MID  모델 (디폴트: qwen2.5:7b)
    WHYMATH_QEVAL_SAMPLES     평가셋 JSON 경로 (디폴트: ./fast_tier_eval.json)
    WHYMATH_QEVAL_OUTPUT      결과 JSON 출력 경로 (디폴트: results/qeval_<ts>.json)
    WHYMATH_QEVAL_NUM_PREDICT 모델당 생성 토큰 한도 (디폴트: 512 — 수학 모델 과추론 잘림 방지)

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
# DEFAULT_HOST는 그대로 Windows Native GPU Ollama(127.0.0.1:11434)를 가리킨다.
# 172.17.112.1(WSL2 CPU)은 속도만 느리고 정확도엔 무관(모듈 docstring "호스트" 참조).
DEFAULT_HOST: Final[str] = "http://localhost:11434"
DEFAULT_NUM_PREDICT: Final[int] = 512

# 태스크 패밀리 식별자 -------------------------------------------------------
# 실측 근본 결함(수학 특화 모델이 정보추출·매칭·형식변환 NLP 작업에 부적합)을
# 바로잡기 위해, 항목을 두 패밀리로 나눠 *패밀리에 맞는* 모델로 평가한다.
FAMILY_MATH: Final[str] = "math"  # 산술(call_site=None) — 수학 특화 모델
FAMILY_NLP: Final[str] = "nlp"  # extract/translate/match — 일반 모델

# 호출지점 → 패밀리 매핑. call_site가 None(산술)이면 MATH, 그 외는 NLP.
# NLP 호출지점: 정보 추출(extract)·표기 정규화(translate)·코드 매칭(match)은
# 수학 풀이가 아니라 정보처리/형식변환이라 일반 모델(qwen2.5)이 적합하다.
CALL_SITE_FAMILY: Final[dict[str, str]] = {
    "extract": FAMILY_NLP,  # ① 개념 추출 — NLP
    "translate": FAMILY_NLP,  # ③ 번역·정규화 — NLP
    "match": FAMILY_NLP,  # ④ 개념 ID 매칭 — NLP
}
"""호출지점 → 태스크 패밀리. call_site가 None(산술)이면 기본 FAMILY_MATH."""

# 패밀리별 기본 (fast, mid) 모델 — CLI/env로 덮어쓸 수 있는 시작점.
#   MATH: 수학 특화 qwen2-math (산술에 강함).
#   NLP : 일반 qwen2.5 (정보추출·매칭·형식변환에 적합 — 실측이 요구한 교정).
DEFAULT_MATH_FAST_MODEL: Final[str] = "qwen2-math:1.5b"
DEFAULT_MATH_MID_MODEL: Final[str] = "qwen2-math:7b"
DEFAULT_NLP_FAST_MODEL: Final[str] = "qwen2.5:3b"
DEFAULT_NLP_MID_MODEL: Final[str] = "qwen2.5:7b"

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

    def family(self) -> str:
        """이 항목의 태스크 패밀리 (CALL_SITE_FAMILY 매핑).

        extract/translate/match → FAMILY_NLP(일반 모델), call_site None(산술) →
        FAMILY_MATH(수학 특화 모델). 러너는 이 패밀리로 (fast, mid) 모델을 고른다.
        """
        if self.call_site is None:
            return FAMILY_MATH
        return CALL_SITE_FAMILY.get(self.call_site, FAMILY_NLP)


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


@dataclass(slots=True, frozen=True)
class ModelMatrix:
    """패밀리별 (fast, mid) 모델 매핑 — 태스크 패밀리 인지 라우팅의 핵심.

    러너는 각 항목의 family()로 이 매트릭스에서 (fast, mid) 모델을 골라 호출한다.
    MATH 패밀리(산술)는 수학 특화 모델, NLP 패밀리(extract/translate/match)는
    일반 모델을 쓴다. 값은 CLI/env로 주입된다(기본은 DEFAULT_* 상수).
    """

    math_fast: str = DEFAULT_MATH_FAST_MODEL
    math_mid: str = DEFAULT_MATH_MID_MODEL
    nlp_fast: str = DEFAULT_NLP_FAST_MODEL
    nlp_mid: str = DEFAULT_NLP_MID_MODEL

    def model_for(self, family: str, role: str) -> str:
        """패밀리(math/nlp)·역할(fast/mid)에 해당하는 모델 ID를 반환.

        알 수 없는 패밀리는 보수적으로 NLP로 간주한다(대부분의 호출지점이 NLP).
        """
        is_fast = role == "fast"
        if family == FAMILY_MATH:
            return self.math_fast if is_fast else self.math_mid
        return self.nlp_fast if is_fast else self.nlp_mid


@dataclass(slots=True)
class ModelResult:
    """한 역할(FAST 또는 MID)의 전체 평가 결과.

    태스크 패밀리 인지 라우팅에서는 한 역할이 *여러 모델*(패밀리별)을 쓰므로,
    `model`은 대표 표기("nlp=...,math=...")이고, 항목별 실제 모델은 ItemScore와
    by_call_site로 추적한다(아래 models_used).
    """

    model: str  # 역할의 사용 모델 요약 표기(패밀리별)
    role: str  # 'fast' 또는 'mid'
    item_scores: list[ItemScore]
    by_call_site: list[CallSiteAggregate]
    models_used: dict[str, str]  # {family: model_id} — 이 역할에서 패밀리별 실제 모델


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
    """최종 품질 평가 보고서. JSON 직렬화 대상.

    태스크 패밀리 인지 라우팅이므로 단일 fast/mid 모델 대신 *패밀리별 매트릭스*를
    기록한다(math_fast/math_mid/nlp_fast/nlp_mid). 패밀리별 사용 모델은 각 ModelResult
    의 models_used에도 남는다.
    """

    timestamp: str
    matrix: dict[str, str]  # ModelMatrix asdict — 패밀리별 (fast, mid) 모델 4종
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


def _strip_answer_wrapping(text: str) -> str:
    """추출한 답 구간에서 *의미 없는 감싸기·앞장식*을 제거한다 (결정적 strip).

    실측 qwen2-math 출력은 답을 콜론·등호·마크다운·LaTeX 인라인 수식으로 감싸는
    일이 잦다(예: ": 45", "= x^2", "$x$", "\\(x\\)", "**x**", "`x`"). 이런 장식은
    *정답 여부*와 무관하므로 모두 벗겨 순수 답만 남긴다. gold·모델 출력 어디에도
    동일하게 적용되지 않고 *추출 후 한 번만* 수행하는 정리 단계다.

    수행 순서(고정점까지 반복 — 중첩 감싸기 흡수):
      1. 양끝 공백 제거.
      2. LaTeX 인라인 수식 감싸기 '\\(...\\)' / '$...$' 의 *바깥 한 겹* 제거.
      3. 마크다운 강조 '**...**' / '*...*' / '`...`' 의 *바깥 한 겹* 제거.
      4. 선두 콜론(:·：)·등호(=) 제거(": 45" → "45", "= x" → "x").
    """
    prev = None
    s = text
    while prev != s:
        prev = s
        s = s.strip()
        # LaTeX 인라인 수식 감싸기 한 겹 제거: \( ... \) (안쪽에 또 다른 \(·\) 없을 때만
        # — '\(a\) + \(b\)' 같은 두 개의 분리 수식을 잘못 벗기지 않게 한다).
        m = re.fullmatch(r"\\\((?:(?!\\[()]).)*\\\)", s, flags=re.DOTALL)
        if m:
            s = s[2:-2]
            continue
        # $ ... $ (안쪽에 '$' 없을 때만 — '$a$ + $b$' 오벗김 방지).
        m = re.fullmatch(r"\$+([^$]*)\$+", s, flags=re.DOTALL)
        if m:
            s = m.group(1)
            continue
        # 마크다운 강조 한 겹 제거: **..** (안쪽에 '*' 없을 때만).
        m = re.fullmatch(r"\*\*([^*]*)\*\*", s, flags=re.DOTALL)
        if m:
            s = m.group(1)
            continue
        # *..* (안쪽에 '*' 없을 때만 — 'x*y' 곱셈은 보존).
        m = re.fullmatch(r"\*([^*]+)\*", s, flags=re.DOTALL)
        if m:
            s = m.group(1)
            continue
        # `..` (안쪽에 '`' 없을 때만).
        m = re.fullmatch(r"`([^`]*)`", s, flags=re.DOTALL)
        if m:
            s = m.group(1)
            continue
        # 선두 콜론·등호 제거(": 45" / "= x" 같은 앞장식)
        m = re.match(r"^\s*[:：=]\s*(.*)$", s, flags=re.DOTALL)
        if m:
            s = m.group(1)
            continue
    return s.strip()


def _normalize_latex(text: str) -> str:
    """LaTeX 수식 표기를 ASCII 산술 표기로 변환한다 (정규화 전처리).

    모델이 LaTeX(예: '\\frac{a}{b}', 'x^{2}', 'a \\times b')로 답하고 gold는 ASCII
    ('a/b', 'x^2', 'a*b')일 때 채점이 어긋나는 것을 막는다. gold·모델 출력 *양쪽에
    동일하게* 적용되므로 채점 의미는 불변이다(닫힌 PR #8 keeper 흡수).

    변환:
      - '\\frac{a}{b}' → '(a)/(b)'  — 분자·분모를 괄호로 감싸 우선순위 보존.
      - '\\times' / '\\cdot' → '*'   — 곱셈 명령.
      - '\\div' → '/'                — 나눗셈 명령.
      - 'x^{n}' → 'x^n'              — 지수 중괄호 제거(한 글자/여러 글자 모두).
      - '\\left' / '\\right' 제거    — 크기 조절 명령(괄호 자체는 보존).
    """
    s = text
    # \frac{a}{b} → (a)/(b). 중첩이 있을 수 있으니 고정점까지 반복(안쪽부터 해소).
    frac_pat = re.compile(r"\\frac\s*\{([^{}]*)\}\s*\{([^{}]*)\}")
    prev = None
    while prev != s:
        prev = s
        s = frac_pat.sub(r"(\1)/(\2)", s)
    # \left / \right 제거(괄호는 남김). 명령 뒤 백슬래시 구분자 보존 위해 \b 미사용.
    s = re.sub(r"\\left", "", s)
    s = re.sub(r"\\right", "", s)
    # \times / \cdot → *, \div → / (긴 명령부터; 워드 경계로 '\cdotx' 오치환 방지).
    s = re.sub(r"\\times\b", "*", s)
    s = re.sub(r"\\cdot\b", "*", s)
    s = re.sub(r"\\div\b", "/", s)
    # ^{n} → ^n (지수 중괄호 제거).
    s = re.sub(r"\^\{([^{}]*)\}", r"^\1", s)
    return s


def normalize_form(text: str) -> str:
    """수식·답 문자열을 정규화한다 (결정적 채점의 기준).

    규칙(파서 가정):
      0. 답 감싸기·앞장식 제거(_strip_answer_wrapping) — 선두 ':'·'=', 수식 감싸기
         '$...$'/'\\(...\\)' 를 벗겨 ': 45'·'$45$' 가 '45' 와 매칭되게 한다.
      1. LaTeX 표기 변환(_normalize_latex) — '\\frac{a}{b}'→'(a)/(b)', 'x^{2}'→'x^2',
         '\\times'/'\\cdot'→'*', '\\div'→'/', '\\left'/'\\right' 제거.
      2. 양끝 공백 제거(strip), 소문자화(lower).
      3. 유니코드 비교 연산자(≤·≥·≠·×·÷)를 ASCII(<=·>=·!=·*·/)로 치환.
      4. 모든 공백을 제거한 뒤, 이항 연산자 주위에 공백 한 칸을 *재삽입*하여
         'x^2+3x-4' 와 'x^2 + 3x - 4' 가 같은 정규형이 되도록 한다.
      5. 곱셈 별표 'x*y' 와 'x * y' 도 동일하게 정규화된다.

    주의: 단항 음수(예: '-2')도 이 규칙에서 ' - 2'가 되지만, gold와 모델 출력에
    *동일하게* 적용되므로 매칭에는 문제가 없다(정규화는 양쪽에 똑같이 적용).
    """
    # 0. 감싸기·앞장식 제거(양쪽에 동일 적용 — 매칭 의미 불변).
    s = _strip_answer_wrapping(text)
    # 1. LaTeX 표기 → ASCII (소문자화 전: '\Frac' 같은 변형은 없다고 가정, 명령은 소문자).
    s = _normalize_latex(s).lower()
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
    # 단일 토큰을 둘러싼 불필요한 괄호 제거: \frac 변환 산물 '(5)/(6)'를 gold 표기 '5/6'와
    # 일치시킨다(실측 AR05). 연산자 포함 그룹('(a+b)')은 보존(우선순위 의미). 양쪽 동일 적용.
    s = re.sub(r"\(([^()+\-*/]+)\)", r"\1", s)
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


def _extract_answer_span(raw: str) -> str:
    """모델 응답에서 *최종답 구간*(문자열)을 추출한다 (단일·개념 공통 1차 추출).

    실측 로컬 모델 출력 형식을 견고히 흡수하기 위해 *우선순위 폴백*을 따른다.
    여기서는 답 구간을 한 덩어리 문자열로만 돌려주고, 단일답/개념 분할·정리는
    각 parse_* 가 후처리한다.

    우선순위(앞이 우선):
      1. 마지막 '<ANSWER>...</ANSWER>' 내용(프롬프트가 강제하는 형식 계약). 태그 안의
         내용만 취하며 여러 줄도 허용한다(개념 나열 시 줄바꿈 흡수).
      2. 마지막 '####' 뒤 내용(구 계약·호환). 같은 줄만 취한다.
      3. '\\boxed{...}' 의 *가장 안쪽* 내용(수학 모델이 최종답을 자주 넣는 곳).
      4. 라벨('ANSWER:'/'정답:'/'답:'/'정답은') 중 *마지막* 뒤 같은 줄.
      5. 마지막 비어있지 않은 줄 전체.
    어느 단계도 못 찾으면 빈 문자열.
    """
    # 1. 마지막 '<ANSWER>...</ANSWER>' 내용(1순위 형식 계약).
    answer_tags = list(re.finditer(r"<ANSWER>(.*?)</ANSWER>", raw, flags=re.DOTALL | re.IGNORECASE))
    if answer_tags:
        return answer_tags[-1].group(1).strip()
    # 2. 마지막 '####' 뒤 같은 줄(구 계약 폴백).
    hashes = list(re.finditer(r"####", raw))
    if hashes:
        tail = raw[hashes[-1].end() :]
        first_line = tail.splitlines()[0] if tail.splitlines() else tail
        return first_line.strip()
    # 3. 가장 안쪽 \boxed{...} (중첩 중괄호는 균형 스캔으로 안쪽을 택함).
    boxed = _innermost_boxed(raw)
    if boxed is not None:
        return boxed.strip()
    # 4. 마지막 라벨 뒤 같은 줄.
    labeled = _last_label_value(raw)
    if labeled is not None:
        return labeled.strip()
    # 5. 마지막 비어있지 않은 줄.
    return _last_answer_line(raw)


def _innermost_boxed(raw: str) -> str | None:
    """'\\boxed{...}' 의 *가장 안쪽* 중괄호 내용을 반환(없으면 None).

    중첩 '\\boxed{\\boxed{42}}' 나 내부에 '{}' 가 섞인 경우에도 안쪽 내용을
    얻기 위해, 각 '\\boxed{' 출현마다 균형 잡힌 닫는 괄호까지 스캔한 뒤,
    그 안에 또 '\\boxed{' 가 있으면 더 안쪽을 택한다(재귀). 마지막 출현 우선.
    """
    starts = [m.end() for m in re.finditer(r"\\boxed\s*\{", raw)]
    if not starts:
        return None
    # 마지막 \boxed 출현을 기준으로 균형 스캔.
    open_idx = starts[-1]
    depth = 1
    i = open_idx
    while i < len(raw) and depth > 0:
        if raw[i] == "{":
            depth += 1
        elif raw[i] == "}":
            depth -= 1
            if depth == 0:
                break
        i += 1
    inner = raw[open_idx:i]
    # 안쪽에 또 boxed 가 있으면 더 안쪽을 택함(중첩 흡수).
    nested = _innermost_boxed(inner)
    return nested if nested is not None else inner


def _last_label_value(raw: str) -> str | None:
    """라벨('ANSWER:'/'정답:'/'답:'/'정답은') 중 마지막 뒤 같은 줄을 반환.

    없으면 None. '정답은' 처럼 콜론 없는 한국어 라벨도 흡수한다.
    """
    pattern = r"(?:answer|정답은|정답|답)\s*[:：]?\s*"
    matches = list(re.finditer(pattern, raw, flags=re.IGNORECASE))
    if not matches:
        return None
    last = matches[-1]
    tail = raw[last.end() :]
    first_line = tail.splitlines()[0] if tail.splitlines() else tail
    return first_line


def parse_concept_list(raw: str) -> list[str]:
    """모델 응답에서 개념 *리스트*를 추출한다 (CONCEPT_EXTRACT ①).

    1차로 _extract_answer_span 으로 답 구간을 얻은 뒤(프롬프트는 '<ANSWER>개념1,
    개념2</ANSWER>'를 강제, 실측은 '####'·라벨·문장도 섞임 → 폴백으로 흡수), 다음을 한다:
      - 감싸기·앞장식(_strip_answer_wrapping)을 제거한다.
      - 쉼표(,)·한국어 가운뎃점(·)·세미콜론(;)으로 분할한다.
      - 각 항목의 글머리표('1.', '-', '*')·앞뒤 공백을 제거하고 빈 항목은 버린다.
    """
    span = _extract_answer_span(raw)
    # 개념 전용 선두 라벨('개념:'/'concepts:')도 제거(_extract_answer_span 의 답 라벨
    # 집합엔 없으므로 여기서 한 번 더). '####'/'\\boxed' 폴백을 거친 뒤에도 안전.
    span = re.sub(r"^\s*(?:개념|concepts?)\s*[:：]\s*", "", span, flags=re.IGNORECASE)
    span = _strip_answer_wrapping(span)
    # 쉼표·가운뎃점·세미콜론으로 분할
    parts = re.split(r"[,·;]", span)
    out: list[str] = []
    for p in parts:
        cleaned = _strip_list_bullet(p).strip()
        if cleaned:
            out.append(cleaned)
    return out


def parse_single_answer(raw: str) -> str:
    """모델 응답에서 *단일 답*을 추출한다 (TRANSLATE·MATCH·산술).

    1차로 _extract_answer_span 으로 답 구간을 얻고(우선순위: '<ANSWER>..</ANSWER>'
    → '####' → '\\boxed{}' → 라벨 → 마지막 줄), 감싸기·앞장식(_strip_answer_wrapping)을
    벗겨 순수 답만 돌려준다. 정규화(공백·연산자·대소문자)는 채점기(normalize_form)에서
    수행한다.
    """
    span = _extract_answer_span(raw)
    return _strip_answer_wrapping(span)


def _last_answer_line(raw: str) -> str:
    """응답의 마지막 비어있지 않은 줄을 반환(없으면 빈 문자열)."""
    lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
    return lines[-1] if lines else ""


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
            # temperature=0: LLM 샘플링은 비결정적이라 실행마다 점수가 출렁인다
            # (실측 산술 37~62%). 0으로 고정해 *재현 가능한 측정*을 만든다 — FAST/MID
            # 품질 비교는 측정 잡음이 아니라 모델 차이를 봐야 하므로 결정성이 필수.
            options={"num_predict": num_predict, "temperature": 0},
        )
        return str(response.get("response", ""))
    except Exception as exc:  # noqa: BLE001 — 모든 오류를 결과 문자열로 흡수
        return f"ERROR: {type(exc).__name__}: {exc}"


async def _evaluate_model(
    client: _OllamaClientProtocol,
    matrix: ModelMatrix,
    role: str,
    items: list[EvalItem],
    num_predict: int,
) -> ModelResult:
    """한 역할(fast/mid)로 전체 항목을 순차 평가(호출 → 채점 → 집계).

    태스크 패밀리 인지: 각 항목의 family()로 matrix에서 (이 역할의) 모델을 골라
    호출한다. 즉 NLP 항목은 일반 모델, MATH 항목(산술)은 수학 특화 모델이 같은
    역할 안에서 섞여 쓰인다. models_used에 패밀리별 실제 모델을 기록한다.

    순차 호출인 이유: 품질 평가는 throughput이 목적이 아니라 *결정성*이 중요하고,
    GPU 단일 점유 모델(특히 MID)에서 동시 호출은 의미가 없다(03a §A.1).
    """
    scores: list[ItemScore] = []
    models_used: dict[str, str] = {}
    for item in items:
        family = item.family()
        model = matrix.model_for(family, role)
        models_used[family] = model
        raw = await _call_once(client, model, item, num_predict)
        scores.append(grade_item(item, raw))
    return ModelResult(
        model=_summarize_models(models_used),
        role=role,
        item_scores=scores,
        by_call_site=aggregate_by_call_site(scores),
        models_used=models_used,
    )


def _summarize_models(models_used: dict[str, str]) -> str:
    """패밀리별 사용 모델을 'nlp=...,math=...' 한 줄 요약으로 — 보고서 가독용."""
    return ",".join(f"{fam}={models_used[fam]}" for fam in sorted(models_used))


# ---- 공개 API ---------------------------------------------------------------
async def run_evaluation(
    *,
    matrix: ModelMatrix,
    items: list[EvalItem],
    host: str = DEFAULT_HOST,
    num_predict: int = DEFAULT_NUM_PREDICT,
    delta: float = DELTA,
    abs_min: float = ABS_MIN,
    client: _OllamaClientProtocol | None = None,
) -> EvaluationReport:
    """FAST vs MID 품질 평가 1회 수행. 단위 테스트는 client 인자로 주입.

    태스크 패밀리 인지: 각 항목은 family()에 따라 matrix에서 (fast, mid) 모델을 골라
    평가된다. FAST 결과 = 패밀리별 소형 모델, MID 결과 = 패밀리별 대형 모델.

    Args:
        matrix: 패밀리별 (fast, mid) 모델 매핑(ModelMatrix).
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

    fast_result = await _evaluate_model(real_client, matrix, "fast", items, num_predict)
    mid_result = await _evaluate_model(real_client, matrix, "mid", items, num_predict)

    verdicts = build_verdicts(
        fast_result.by_call_site,
        mid_result.by_call_site,
        delta=delta,
        abs_min=abs_min,
    )
    overall_keep_fast = all(v.keep_fast for v in verdicts)

    return EvaluationReport(
        timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        matrix=asdict(matrix),
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
        "--math-fast",
        default=os.environ.get("WHYMATH_QEVAL_MATH_FAST", DEFAULT_MATH_FAST_MODEL),
        help=f"MATH 패밀리 FAST 모델 (산술, 디폴트: {DEFAULT_MATH_FAST_MODEL})",
    )
    p.add_argument(
        "--math-mid",
        default=os.environ.get("WHYMATH_QEVAL_MATH_MID", DEFAULT_MATH_MID_MODEL),
        help=f"MATH 패밀리 MID 모델 (산술, 디폴트: {DEFAULT_MATH_MID_MODEL})",
    )
    p.add_argument(
        "--nlp-fast",
        default=os.environ.get("WHYMATH_QEVAL_NLP_FAST", DEFAULT_NLP_FAST_MODEL),
        help=f"NLP 패밀리 FAST 모델 (extract/translate/match, 디폴트: {DEFAULT_NLP_FAST_MODEL})",
    )
    p.add_argument(
        "--nlp-mid",
        default=os.environ.get("WHYMATH_QEVAL_NLP_MID", DEFAULT_NLP_MID_MODEL),
        help=f"NLP 패밀리 MID 모델 (extract/translate/match, 디폴트: {DEFAULT_NLP_MID_MODEL})",
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
    m = report.matrix
    print()
    print("[qeval] ─────────────────────────────────────")
    print(f"[qeval] MATH 패밀리(산술): FAST={m['math_fast']} / MID={m['math_mid']}")
    print(
        f"[qeval] NLP  패밀리(extract/translate/match): "
        f"FAST={m['nlp_fast']} / MID={m['nlp_mid']}"
    )
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

    matrix = ModelMatrix(
        math_fast=args.math_fast,
        math_mid=args.math_mid,
        nlp_fast=args.nlp_fast,
        nlp_mid=args.nlp_mid,
    )
    print(f"[qeval] MATH 패밀리(산술): FAST={matrix.math_fast} / MID={matrix.math_mid}")
    print(
        f"[qeval] NLP  패밀리(extract/translate/match): "
        f"FAST={matrix.nlp_fast} / MID={matrix.nlp_mid}"
    )
    print(f"[qeval] 호스트: {args.host}")
    print(f"[qeval] 항목 수: {len(items)}")
    print(f"[qeval] num_predict: {args.num_predict}")
    print()

    try:
        report = asyncio.run(
            run_evaluation(
                matrix=matrix,
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
