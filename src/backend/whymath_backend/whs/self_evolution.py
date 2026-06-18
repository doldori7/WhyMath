"""WH-S 자기 진화 데이터 — 검증 풀이 → SFT 학습 레코드(설계 §5·순수).

설계 정본: `docs/architecture/03b_wh_s_solver_harness.md` §5(자기 진화 데이터). 솔버가 적재한
*verified* 풀이를 SFT(지도 미세조정) 학습 레코드로 변환하는 *순수 변환 코어*다. 라운드별 루프
(문제 풀 → MCTS 풀이 → verified 수집 → SFT)에서 "verified 수집 → 레코드화" 단계.

★학습 안전(§3·R-S2 보상 해킹 차단·CLAUDE.md 정확성 #1): 본 모듈은 **verified 등급만** 학습
레코드로 만든다 — `unverified`(판정 불가)·그 외는 *구조적으로 배제*한다. `get_verified`(저장소)가
1차 필터지만, 임의 입력(혼합 등급)에도 안전하도록 여기서 *다시* 강제한다(심층 방어). 판정 불가
풀이가 학습 데이터에 새는 일 0 — 배제 건수는 리포트에 *정직하게* 집계한다(조용히 버리지 않음).

dedup(기본 ON): 같은 문제의 *같은 지문*(`solution_fingerprint`) 경로가 데이터셋에 두 번 들어가지
않게 한다. #256 finalize dedup이 저장소 레벨에서 막지만, 다중 문제·과거 누적분을 한데 모으는
export 레벨에서 한 번 더 거른다(재발견 중복 제거·데이터 위생). 키는 `(problem_id, 지문)` —
*다른 문제*의 우연히 같은 경로는 보존(문제마다 별개 학습쌍). 정확 일치만(본질적 동치는 후속).

7계층(§7.5): WH-S 오프라인 — `verified_solutions`는 *시스템이 스스로 푼* 풀이이며 학생 PII가
아니다. 본 모듈은 순수(세션·DB 0)다 — 실 DB 배치 조회·JSONL 직렬화·ops CLI는 후속 슬라이스.
범위 밖: 문제 본문 조인(problem_id→코퍼스)·본질적 동치 dedup·PRM 쌍 추출.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Awaitable, Callable, Iterable, Iterator, Mapping
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from whymath_backend.db.models.problem import Problem
from whymath_backend.db.models.verified_solution import (
    VerifiedSolution,
    WhsSolutionGrade,
)
from whymath_backend.schema.enums import SourceType
from whymath_backend.schema.problem import _METADATA_ONLY_SOURCES
from whymath_backend.whs.solution_bank import solution_fingerprint

__all__ = [
    "SftDataset",
    "SftRecord",
    "SftStreamAccounting",
    "build_sft_dataset",
    "iter_sft_jsonl",
    "stream_sft_jsonl",
    "to_sft_record",
]


def _body_license_clean(problem: Problem) -> bool:
    """문제 본문을 *임베드해도 되는* 라이선스 청정 출처인가(저작권 게이트·우선순위 #2).

    코퍼스 저작권 불변식(`schema.Problem` validator)은 평가원·EBS·교과서(=`_METADATA_ONLY_SOURCES`)
    를 *구조 메타 전용*으로 묶어 본문 필드(question_text·answer_explanation·choices·
    conditions_parsed)를 비운다. conditions_parsed는 한때 강제 대상이 아니었으나(validator 갭) 이제
    L1에서도 강제되어 갭이 닫혔다 — 본 게이트는 export 경계의 *중복 심층 방어*(독립 2차 방어)다.
    본문 보유 합법 출처(자체생성·OER 등 메타 전용 아님)면 True. `source_type`이 enum/문자열 어느
    쪽이어도 정규화해 비교한다(validator 패턴 답습).
    """
    source_value = (
        problem.source_type.value
        if isinstance(problem.source_type, SourceType)
        else problem.source_type
    )
    return source_value not in {s.value for s in _METADATA_ONLY_SOURCES}


class SftRecord(BaseModel):
    """SFT 학습 레코드 1건 — 검증된 (문제, 풀이 경로) 쌍의 *학습신호*만 담는다.

    `solution_path`는 finalize가 적재한 구조(`conditions`·`answer`·`steps`)를 그대로 싣는다 —
    solver의 *기호* 파스다. `question_text`·`answer_explanation`·`unit_codes`·`conditions`는 코퍼스
    조인(`--with-problem`)으로 채워지는 *문제 컨텍스트*(자연어 본문·참조 해설·성취기준 코드·구조화
    조건)로, 트레이너가 "이 문제를 풀어라" 프롬프트·참조 풀이를 만들 때 쓴다 — 미조인이면 None
    (기존 동작·하위호환). 출처 메타(id·created_at·source_root_id)는 학습신호가 아니라 제외한다.

    저작권 안전(§13.2·우선순위 #2·심층 방어): **본문 3필드**(`question_text`·`answer_explanation`·
    `conditions`)는 WH-S export가 **출처 균일 게이트**(`_body_license_clean`)로 *본문 보유 합법
    출처에만* 싣고 제한 출처(평가원·EBS·교과서)면 비운다. 코퍼스 불변식(`schema.Problem`)이 1차로
    이 세 본문 필드를 제한 출처에서 NULL로 강제하므로(conditions 갭도 L1에서 닫힘), export 경계의
    게이트는 *독립 2차 방어*다 — validator 오류/회귀에도 제한 본문이 SFT로 새지 않게(#261 교훈).
    `unit_codes`는 공공 성취기준 코드라 게이트 대상이 아니다.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    problem_id: uuid.UUID = Field(description="풀이가 속한 문제(느슨참조·코퍼스 조인 키).")
    solution_path: dict[str, Any] = Field(description="검증된 풀이 경로(conditions·answer·steps).")
    strategy_tag: str | None = Field(default=None, description="전략 유형(대수적·기하적 등).")
    answer: str | None = Field(default=None, description="최종 답(증명 등 답 없으면 None).")
    question_text: str | None = Field(
        default=None, description="문제 자연어 본문(코퍼스 조인·본문 합법 출처만·미조인 시 None)."
    )
    answer_explanation: str | None = Field(
        default=None,
        description="문제 해설(참조 풀이·코퍼스 조인·본문 합법 출처만·미조인 시 None).",
    )
    unit_codes: tuple[str, ...] | None = Field(
        default=None, description="성취기준 코드(코퍼스 조인·미조인 시 None)."
    )
    conditions: tuple[dict[str, Any], ...] | None = Field(
        default=None,
        description="구조화 조건(코퍼스 조인·본문 합법 출처만·제한 출처/미조인 시 None).",
    )


class SftDataset(BaseModel):
    """`build_sft_dataset` 결과 — 레코드 + *정직한* 집계(배제·중복 건수).

    `excluded_unverified`/`deduped`는 조용히 버려지지 않은 투명 회계다(§5 라운드별 *신규* verified
    경로 수 추적·R-S2 배제 가시화). `size`(=len(records))가 실제 학습쌍 수.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    records: tuple[SftRecord, ...] = Field(description="학습 레코드(verified·dedup 후).")
    total_input: int = Field(ge=0, description="입력 풀이 총수(필터 전).")
    excluded_unverified: int = Field(ge=0, description="verified 아님으로 배제된 수(R-S2).")
    deduped: int = Field(ge=0, description="재발견 중복으로 제거된 수(같은 문제·같은 지문).")
    problems_missing: int = Field(
        default=0,
        ge=0,
        description="코퍼스에 problem_id가 없어 컨텍스트 미결합된 레코드 수(NO_DATA).",
    )
    conditions_gated: int = Field(
        default=0,
        ge=0,
        description="제한 출처라 조건 본문을 비운 레코드 수(저작권 게이트·억제 가시화).",
    )

    @property
    def size(self) -> int:
        """실제 학습쌍 수(=len(records))."""
        return len(self.records)


def to_sft_record(solution: VerifiedSolution, problem: Problem | None = None) -> SftRecord:
    """검증 풀이 1건 → SFT 레코드(순수·학습신호 필드만). 등급 검사는 `build_sft_dataset`가 한다.

    `problem`(코퍼스 조인 결과)을 주면 컨텍스트를 임베드한다. 없으면 컨텍스트 필드 전부 None
    (미조인·하위호환). **본문 3필드(question_text·answer_explanation·conditions)는 출처 균일
    게이트**(`_body_license_clean`): 본문 보유 합법 출처에만 싣고 제한 출처(평가원·EBS·교과서)면
    None(L1 validator 독립 2차 방어·#261 교훈·우선순위 #2). `unit_codes`(공공 성취기준 코드)는
    본문이 아니라 게이트 없이 조인 시 항상 포함. `Problem` ORM은 *속성만 읽고* 세션을 건드리지 않아
    순수성을 유지한다(`VerifiedSolution` 읽기와 동형).
    """
    question_text: str | None = None
    answer_explanation: str | None = None
    unit_codes: tuple[str, ...] | None = None
    conditions: tuple[dict[str, Any], ...] | None = None
    if problem is not None:
        unit_codes = tuple(problem.unit_codes)  # 공공 성취기준 코드 — 본문 아님·게이트 불요.
        if _body_license_clean(problem):
            # 본문 합법 출처만 — 본문 3필드를 export 경계에서 균일 게이트(제한 출처는 전부 None).
            question_text = problem.question_text
            answer_explanation = problem.answer_explanation
            conditions = tuple(problem.conditions_parsed)
    return SftRecord(
        problem_id=solution.problem_id,
        solution_path=solution.solution_path,
        strategy_tag=solution.strategy_tag,
        answer=solution.answer,
        question_text=question_text,
        answer_explanation=answer_explanation,
        unit_codes=unit_codes,
        conditions=conditions,
    )


def build_sft_dataset(
    solutions: Iterable[VerifiedSolution],
    *,
    dedup: bool = True,
    problem_map: Mapping[uuid.UUID, Problem] | None = None,
) -> SftDataset:
    """검증 풀이들 → SFT 데이터셋(verified만·재발견 dedup·정직 집계·순수).

    **R-S2 학습 안전(심층 방어)**: `grade != verified`인 풀이는 레코드로 만들지 않고
    `excluded_unverified`로 집계한다 — `get_verified`가 1차 필터여도 임의 입력에 안전하다.
    **dedup(기본 ON)**: 같은 `(problem_id, 지문)`이 이미 나왔으면 건너뛰고 `deduped`로 집계한다.
    입력 순서를 보존한다(결정론). 트랜잭션·DB 0(순수).

    **문제 조인(opt-in)**: `problem_map`(problem_id→Problem·호출자가 코퍼스에서 일괄 조회)을 주면
    레코드에 `question_text`·`unit_codes`·`conditions`를 결합한다. map에 *없는* problem_id는
    NO_DATA로 보고 컨텍스트를 비운 채(`problems_missing` 집계) 레코드는 *그대로 적재한다* — 풀이는
    verified라 버리지 않되 누락을 *조용히 메우지 않고 정직하게 센다*(날조 0). **저작권 게이트**:
    제한 출처(평가원·EBS·교과서)면 `conditions`를 비우고, *실제 조건이 있던* 레코드는
    `conditions_gated`로 센다(억제 가시화·우선순위 #2).
    """
    records: list[SftRecord] = []
    seen: set[tuple[uuid.UUID, str]] = set()
    total = 0
    excluded = 0
    deduped = 0
    problems_missing = 0
    conditions_gated = 0
    for sol in solutions:
        total += 1
        if sol.grade != WhsSolutionGrade.VERIFIED:
            excluded += 1  # R-S2 심층 방어 — verified 아닌 풀이는 학습 배제(배제 건수 정직 집계).
            continue
        if dedup:
            key = (sol.problem_id, solution_fingerprint(sol.solution_path))
            if key in seen:
                deduped += 1  # 같은 문제·같은 지문 재발견 — 중복 제거(가시화).
                continue
            seen.add(key)
        problem: Problem | None = None
        if problem_map is not None:
            problem = problem_map.get(sol.problem_id)
            if problem is None:
                problems_missing += 1  # 코퍼스에 없음 — 컨텍스트 비우고 정직 집계(NO_DATA).
            elif not _body_license_clean(problem) and problem.conditions_parsed:
                conditions_gated += 1  # 제한 출처 조건 억제 — 저작권 게이트 가시화(#2).
        records.append(to_sft_record(sol, problem))
    return SftDataset(
        records=tuple(records),
        total_input=total,
        excluded_unverified=excluded,
        deduped=deduped,
        problems_missing=problems_missing,
        conditions_gated=conditions_gated,
    )


def iter_sft_jsonl(dataset: SftDataset) -> Iterator[str]:
    """데이터셋의 레코드를 **JSONL 한 줄/레코드**로 yield한다(순수·결정론·레코드 순서 보존).

    각 줄은 `SftRecord`의 `model_dump_json()`(UUID→문자열·nested `solution_path` dict 처리)이다 —
    개행 없는 1줄(`json.dumps` 기본). ops export 진입점(`self_evolution_export_cli`)이 stdout으로
    흘려 `> dataset.jsonl`로 받는다. 회계 요약(배제·중복 수)은 *데이터에 섞지 않는다*(CLI가 stderr).
    """
    for record in dataset.records:
        yield record.model_dump_json()


class SftStreamAccounting(BaseModel):
    """`stream_sft_jsonl`의 *진행 중* 회계 — 스트림을 흘리며 누적, 소진 *후* 최종값을 읽는다.

    `build_sft_dataset`가 전량 적재 후 `SftDataset`에 회계를 *한 번에* 담는 것과 달리, 스트리밍은
    레코드를 다 본 시점에야 총계가 확정된다. 그래서 호출자가 이 *가변* 누산기를 만들어
    `stream_sft_jsonl`에 주입하고, 스트림이 끝난 뒤 `summary()`로 stderr 회계를 낸다(데이터 stdout과
    분리·#258 일괄 CLI와 같은 키). `SftDataset`(frozen·결과 스냅샷)과 달리 가변이다(누적 카운터).
    """

    model_config = ConfigDict(extra="forbid")

    total_input: int = Field(default=0, ge=0, description="입력 풀이 총수(필터 전).")
    records: int = Field(default=0, ge=0, description="JSONL로 흘린 학습 레코드 수.")
    excluded_unverified: int = Field(default=0, ge=0, description="verified 아님으로 배제(R-S2).")
    deduped: int = Field(default=0, ge=0, description="재발견 중복으로 제거(같은 문제·같은 지문).")
    problems_missing: int = Field(
        default=0,
        ge=0,
        description="코퍼스에 problem_id가 없어 컨텍스트 미결합된 레코드 수(NO_DATA).",
    )
    conditions_gated: int = Field(
        default=0, ge=0, description="제한 출처라 조건 본문을 비운 레코드 수(저작권 게이트)."
    )

    def summary(self) -> dict[str, int]:
        """stderr 회계 요약 dict(일괄 CLI 요약과 동일 키 `{total_input, records, ...}`)."""
        return {
            "total_input": self.total_input,
            "records": self.records,
            "excluded_unverified": self.excluded_unverified,
            "deduped": self.deduped,
            "problems_missing": self.problems_missing,
            "conditions_gated": self.conditions_gated,
        }


async def stream_sft_jsonl(
    rows: AsyncIterator[VerifiedSolution],
    accounting: SftStreamAccounting,
    *,
    dedup: bool = True,
    problem_loader: Callable[[uuid.UUID], Awaitable[Problem | None]] | None = None,
) -> AsyncIterator[str]:
    """검증 풀이 스트림 → SFT JSONL 스트림(verified만·재발견 dedup·정직 회계·순서 보존).

    `build_sft_dataset`+`iter_sft_jsonl`의 *스트리밍 등가물*이다 — 전 풀이를 list로 모아
    데이터셋을 구성하는 대신, `rows`(서버측 커서 `stream_all_verified`)를 `async for`로 한
    건씩 받아 그 자리에서 JSONL 한 줄을 yield한다. 메모리는 *한 건 + dedup 키셋 + 정수
    카운터*로 바운드된다.

    **R-S2 학습 안전(심층 방어·정확성 #1)**: `grade != verified`는 yield하지 않고
    `accounting.excluded_unverified`로 집계한다 — `stream_all_verified`가 1차 필터여도 임의
    입력에 안전하다(판정 불가 풀이 학습 누수 0). **dedup(기본 ON)**: 같은 `(problem_id,
    지문)`이 이미 나왔으면 yield 않고 `accounting.deduped`로 집계한다. 통과분만
    `accounting.records`를 올리고 `to_sft_record(...).model_dump_json()`을 yield한다(일괄
    경로와 바이트 동일).

    **문제 조인(opt-in)**: `problem_loader`(problem_id→Problem|None·async)를 주면 컨텍스트를
    결합한다. `stream_all_verified`가 `(problem_id, …)` *그룹 정렬*로 흘리므로 **단일 항목
    캐시**(현재 problem_id+Problem)로 problem_id가 바뀔 때만 loader를 부른다 — O(1) 메모리·
    O(distinct problems) 조회(#259 가드 불파괴). loader가 None을 주면(코퍼스 미존재) 컨텍스트를
    비우고 `accounting.problems_missing`로 정직 집계(NO_DATA·날조 0).

    회계는 주입된 `accounting`(가변)에 누적된다 — 스트림 소진 후 호출자가
    `accounting.summary()`로 stderr 요약을 낸다. **메모리 가드의 경계(정직)**: 행은 전량
    적재하지 않지만 dedup `seen` 키셋은 *유일하게 증가하는* 구조다 — 다만 ORM 행이 아니라
    `(UUID, sha256)` 키라 훨씬 작고, `dedup=False`면 그마저 없다.
    """
    seen: set[tuple[uuid.UUID, str]] = set()
    cached_problem_id: uuid.UUID | None = None
    cached_problem: Problem | None = None
    async for sol in rows:
        accounting.total_input += 1
        if sol.grade != WhsSolutionGrade.VERIFIED:
            accounting.excluded_unverified += 1  # R-S2 심층 방어 — verified 아님 배제(정직 집계).
            continue
        if dedup:
            key = (sol.problem_id, solution_fingerprint(sol.solution_path))
            if key in seen:
                accounting.deduped += 1  # 같은 문제·같은 지문 재발견 — 중복 제거(가시화).
                continue
            seen.add(key)
        problem: Problem | None = None
        if problem_loader is not None:
            if sol.problem_id != cached_problem_id:
                # 그룹 정렬 전제 — problem_id가 바뀔 때만 조회(단일 캐시·O(distinct) 조회).
                cached_problem_id = sol.problem_id
                cached_problem = await problem_loader(sol.problem_id)
            problem = cached_problem
            if problem is None:
                accounting.problems_missing += 1  # 코퍼스 미존재 — 컨텍스트 비우고 정직 집계.
            elif not _body_license_clean(problem) and problem.conditions_parsed:
                accounting.conditions_gated += 1  # 제한 출처 조건 억제 — 저작권 게이트 가시화(#2).
        accounting.records += 1
        yield to_sft_record(sol, problem).model_dump_json()
