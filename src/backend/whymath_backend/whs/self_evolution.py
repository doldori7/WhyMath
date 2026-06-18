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
from collections.abc import AsyncIterator, Iterable, Iterator
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from whymath_backend.db.models.verified_solution import (
    VerifiedSolution,
    WhsSolutionGrade,
)
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


class SftRecord(BaseModel):
    """SFT 학습 레코드 1건 — 검증된 (문제, 풀이 경로) 쌍의 *학습신호*만 담는다.

    `solution_path`는 finalize가 적재한 구조(`conditions`·`answer`·`steps`)를 그대로 싣는다 —
    문제 본문 조인(problem_id→코퍼스)·프롬프트 템플릿화는 트레이너 책임(후속). 출처 메타
    (id·created_at·source_root_id)는 학습신호가 아니라 제외한다.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    problem_id: uuid.UUID = Field(description="풀이가 속한 문제(느슨참조·코퍼스 조인 키).")
    solution_path: dict[str, Any] = Field(description="검증된 풀이 경로(conditions·answer·steps).")
    strategy_tag: str | None = Field(default=None, description="전략 유형(대수적·기하적 등).")
    answer: str | None = Field(default=None, description="최종 답(증명 등 답 없으면 None).")


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

    @property
    def size(self) -> int:
        """실제 학습쌍 수(=len(records))."""
        return len(self.records)


def to_sft_record(solution: VerifiedSolution) -> SftRecord:
    """검증 풀이 1건 → SFT 레코드(순수·학습신호 필드만). 등급 검사는 `build_sft_dataset`가 한다."""
    return SftRecord(
        problem_id=solution.problem_id,
        solution_path=solution.solution_path,
        strategy_tag=solution.strategy_tag,
        answer=solution.answer,
    )


def build_sft_dataset(
    solutions: Iterable[VerifiedSolution],
    *,
    dedup: bool = True,
) -> SftDataset:
    """검증 풀이들 → SFT 데이터셋(verified만·재발견 dedup·정직 집계·순수).

    **R-S2 학습 안전(심층 방어)**: `grade != verified`인 풀이는 레코드로 만들지 않고
    `excluded_unverified`로 집계한다 — `get_verified`가 1차 필터여도 임의 입력에 안전하다.
    **dedup(기본 ON)**: 같은 `(problem_id, 지문)`이 이미 나왔으면 건너뛰고 `deduped`로 집계한다.
    입력 순서를 보존한다(결정론). 트랜잭션·DB 0(순수).
    """
    records: list[SftRecord] = []
    seen: set[tuple[uuid.UUID, str]] = set()
    total = 0
    excluded = 0
    deduped = 0
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
        records.append(to_sft_record(sol))
    return SftDataset(
        records=tuple(records),
        total_input=total,
        excluded_unverified=excluded,
        deduped=deduped,
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

    def summary(self) -> dict[str, int]:
        """stderr 회계 요약 dict(일괄 CLI 요약과 동일 키 `{total_input, records, ...}`)."""
        return {
            "total_input": self.total_input,
            "records": self.records,
            "excluded_unverified": self.excluded_unverified,
            "deduped": self.deduped,
        }


async def stream_sft_jsonl(
    rows: AsyncIterator[VerifiedSolution],
    accounting: SftStreamAccounting,
    *,
    dedup: bool = True,
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

    회계는 주입된 `accounting`(가변)에 누적된다 — 스트림 소진 후 호출자가
    `accounting.summary()`로 stderr 요약을 낸다. **메모리 가드의 경계(정직)**: 행은 전량
    적재하지 않지만 dedup `seen` 키셋은 *유일하게 증가하는* 구조다 — 다만 ORM 행이 아니라
    `(UUID, sha256)` 키라 훨씬 작고, `dedup=False`면 그마저 없다.
    """
    seen: set[tuple[uuid.UUID, str]] = set()
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
        accounting.records += 1
        yield to_sft_record(sol).model_dump_json()
