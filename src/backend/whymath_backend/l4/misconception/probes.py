"""오개념 라벨 프로브셋 — *프로덕션 패키지 데이터*로 단일화한 source of truth.

이 모듈은 라벨 프로브셋(`probes_v1.jsonl`)을 **패키지 데이터**로 제공하고, 그 위에서
*오프라인 진단정확도*(substring 매처 recall)를 계산한다. 프로브셋은 원래 테스트 fixture
(`tests/backend/l4/fixtures/misconception_semantic_probes.jsonl`)에 있었으나, 프로덕션 경로
(WH-1 하네스 ② 지표·`semantic_eval`)와 테스트가 *같은* 라벨셋을 single source로 참조하도록
패키지 안으로 옮겼다(prod→tests 역방향 의존 회피). `importlib.resources`로 *설치된 패키지*
에서도 로드 가능하다(개발 트리·wheel 동일).

프로브 한 줄 스키마는 `semantic_eval.MisconceptionProbe`와 동일하다:
  - **recall 프로브**: `expected_id` not null(틀린 진술 → 잡혀야 할 오개념 id·`near_id` null).
  - **FP 프로브**: `expected_id` null(올바른 진술 → 매칭되면 거짓양성·`near_id`에 겨냥 대상).

────────────────────────────────────────────────────────────────────────────
오프라인 진단정확도 (`compute_diagnostic_recall`) — 정직 스코프
────────────────────────────────────────────────────────────────────────────
이 함수가 내는 recall은 **오프라인·시스템 지표**다 — 라벨 프로브에 *substring 매처*
(`diagnose`)를 돌려 top-1 매치 id가 `expected_id`와 일치하는 비율(top-1 recall)이다.

  - **LIVE 학생별 ground-truth가 아니다.** 실제 학생의 진짜 오개념은 자가보고되지 않고
    (attempt별 진단 기록·문항-오개념 태그 부재), 따라서 학생별 일치율은 데이터 기반이 없다.
    이 지표는 *시스템 진단엔진 품질*을 잰다 — 전 user 동일값(user_id/기간 무관).
  - **substring은 보수적 기준선이다.** 의미 매처(pgvector 임베딩·`semantic_matches`)는
    패러프레이즈·동의어까지 잡아 더 높은 recall을 내지만 임베딩 의존이다. 이 함수는
    임베딩 *없이* 항상 가용한 결정론 substring 매처만 쓴다(가벼운 베이스라인).
  - **FP율/precision은 범위 밖이다.** 올바른 진술의 거짓양성·정밀도는 `semantic_eval`이
    별도로 측정한다(Wilson 상한·FP 프로브). 여기선 recall 프로브만 대상으로 한다.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
from importlib import resources
from importlib.resources.abc import Traversable
from pathlib import Path

from whymath_backend.l4.misconception.diagnose import diagnose

__all__ = [
    "PROBES_RESOURCE",
    "compute_diagnostic_recall",
    "probes_path",
    "probes_resource",
    "read_probes_text",
]

# 패키지 데이터 리소스 이름 — `whymath_backend.l4.misconception` 패키지 내부 파일.
PROBES_RESOURCE = "probes_v1.jsonl"


def probes_resource() -> Traversable:
    """라벨 프로브셋 패키지 리소스(`Traversable`) — 설치 트리·개발 트리 공통.

    `importlib.resources.files`는 *설치된 wheel*에서도 패키지 데이터를 가리키므로,
    호출자는 파일시스템 경로를 가정하지 말고 이 Traversable을 통해 텍스트를 읽는다.
    `semantic_eval.load_probes`처럼 `Path`를 요구하는 기존 API에는 `as_file`(아래
    `read_probes_text`는 직접 텍스트만 읽음)로 잠시 실파일을 빌려 쓸 수 있다.
    """
    return resources.files("whymath_backend.l4.misconception") / PROBES_RESOURCE


def read_probes_text() -> str:
    """라벨 프로브셋 JSONL 원문(UTF-8) — 설치 경로에서도 안전하게 로드.

    `probes_resource().read_text`는 zip-기반 설치에서도 동작한다(파일시스템 경로 가정 없음).
    JSONL 파싱은 호출자(또는 `compute_diagnostic_recall`)가 한다.
    """
    return probes_resource().read_text(encoding="utf-8")


@contextmanager
def probes_path() -> Iterator[Path]:
    """라벨 프로브셋을 *실파일 `Path`*로 빌려 주는 컨텍스트 매니저(설치 트리·개발 트리 공통).

    `semantic_eval.load_probes(path: Path)`처럼 `Path.read_text`를 요구하는 기존 API에
    이 프로브셋을 넘길 때 쓴다. `importlib.resources.as_file`은 개발 트리에선 패키지 내
    실파일을 그대로 가리키고, zip/wheel 설치에선 임시 추출 파일을 만들어 *컨텍스트 동안만*
    유효한 경로를 보장한다(블록을 나가면 정리). 따라서 반드시 `with` 블록 안에서 사용한다.

        with probes_path() as p:
            probes = load_probes(p)
    """
    with resources.as_file(probes_resource()) as path:
        yield path


def _iter_recall_probes() -> list[tuple[str, str]]:
    """라벨 프로브셋에서 **recall 프로브만**((statement, expected_id) 쌍) 추출.

    recall 프로브 = `expected_id`가 null이 아닌 줄(틀린 진술 → 잡혀야 할 오개념 라벨).
    FP 프로브(`expected_id` null·올바른 진술)는 제외한다 — recall 측정 대상이 아니다.
    빈 줄·`#` 주석은 무시한다(`semantic_eval.load_probes`와 동일한 관용 규칙).
    """
    pairs: list[tuple[str, str]] = []
    for line_num, raw in enumerate(read_probes_text().splitlines(), start=1):
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        try:
            record = json.loads(stripped)
        except json.JSONDecodeError as exc:  # 줄 번호 컨텍스트와 함께 재던짐(load_probes 동형)
            raise ValueError(f"line {line_num}: {exc}") from exc
        expected_id = record.get("expected_id")
        if expected_id is None:  # FP 프로브 — recall 대상 아님
            continue
        statement = record["statement"]
        pairs.append((statement, expected_id))
    return pairs


def _iter_fp_probes() -> list[str]:
    """라벨 프로브셋에서 **FP 프로브만**(올바른 진술 = `expected_id` null) 추출.

    FP 프로브 = `expected_id`가 null인 줄(틀리지 *않은* 진술 → 어떤 오개념도 매칭되면 안 됨·
    `near_id`는 겨냥 대상). 매처가 이 진술에 오개념을 매칭하면 *거짓양성*(학생을 틀렸다고
    오판)이다. recall 프로브는 제외한다. 빈 줄·`#` 주석은 무시(`_iter_recall_probes`와 동형).

    **용도**: 2단계 종료 게이트의 *정밀도(FP) 회귀 가드* — 후보 매처가 베이스라인보다 정답
    진술에 오개념을 *더 많이* 오매칭하는지 비교한다(`harness/agreement_gate`). `semantic_eval`의
    *절대* precision(Wilson 상한·단일 매처)과 달리 여기선 두 매처의 *비교* FP만 본다.
    """
    statements: list[str] = []
    for line_num, raw in enumerate(read_probes_text().splitlines(), start=1):
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        try:
            record = json.loads(stripped)
        except json.JSONDecodeError as exc:  # 줄 번호 컨텍스트와 함께 재던짐(load_probes 동형)
            raise ValueError(f"line {line_num}: {exc}") from exc
        if record.get("expected_id") is not None:  # recall 프로브 — FP 대상 아님
            continue
        statements.append(record["statement"])
    return statements


def compute_diagnostic_recall() -> tuple[int, int]:
    """오프라인 진단정확도 — 라벨 recall 프로브에 substring 매처 top-1 recall을 잰다.

    각 recall 프로브의 `statement`에 `diagnose`(substring·결정론·DB 0)를 돌려, **top-1 매치
    (confidence 내림차순 1순위)의 misconception.id == expected_id**면 hit으로 센다. `diagnose`가
    빈 리스트(매칭 0)면 miss다. 반환은 `(hit 수, recall 프로브 총수)` — 호출자(WH-1 하네스)가
    비율·NO_DATA 분기를 정한다(프로브 0건이면 (0, 0) → 날조 0 회피).

    **top-1 기준**: 진단엔진이 학생에게 *제시할* 1순위 오개념의 정확도를 잰다(top-K 중 어디든
    있으면 hit이 아니라 *1순위 일치*만 hit). 동률은 `diagnose`가 catalog 순서로 안정 정렬한다.

    순수·결정론(임베딩·DB·네트워크 0). 정직 스코프는 모듈 docstring 참조:
      - **LIVE 학생별 ground-truth가 아니다**(시스템 진단엔진 품질·전 user 동일).
      - substring은 *보수적 기준선*(의미 매처는 더 높은 recall이나 임베딩 의존).
      - **FP율/precision은 범위 밖**(semantic_eval이 별도 측정).
    """
    recall_probes = _iter_recall_probes()
    total = len(recall_probes)
    hits = 0
    for statement, expected_id in recall_probes:
        matches = diagnose(statement)
        if matches and matches[0].misconception.id == expected_id:
            hits += 1
    return hits, total
