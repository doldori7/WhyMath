"""L1 문제 코퍼스 — 자체생성 동등문제 코퍼스 → backend 적재 (S2-b 파이프라인).

S2-a 수용 게이트(`l3/equivalent/acceptance.py`)를 통과한 자체생성 동등문제를 코퍼스 JSONL
(`data/corpus/problem_bank_v1/problems.jsonl`)에서 backend 영속 `problem`·`problem_concept`
테이블로 멱등 적재하는 L1 경로다(MEMORY 2026-07-04이 S2로 미뤄둔 "문제 코퍼스→DB 적재").

`l1/standards`(성취기준 적재)·`l1/atom_graph`(원자 백본 적재)의 *문제* 짝이며 같은 sync 좌석·멱등
규약·orphan skip 패턴을 따른다. **계층 경계**: L1이라 S2-a 게이트(L3)를 부르지 않는다 —
코퍼스는 저작 시점에 이미 게이트를 통과한 문제라는 계약으로 적재되고, 그 계약은 코퍼스 품질
테스트가 봉인한다(import-linter L1→L3 금지·모듈 docstring 참조).

7계층: L1 데이터 기반의 *영속/적재 인프라*. 소비(게이팅·진단·출제)는 이 좌석을 호출하되 여기서
구현하지 않는다(후속·역방향 의존 금지).
"""

from __future__ import annotations

from whymath_backend.l1.problem_bank.populate import (
    ConceptTag,
    ProblemBankPopulateReport,
    ProblemBankRecord,
    ProblemBankStore,
    ProblemCorpusError,
    ProblemProvenanceMeta,
    ProblemVerifyMeta,
    load_problem_bank_records,
    main,
    populate_problem_bank,
)

__all__ = [
    "ConceptTag",
    "ProblemBankPopulateReport",
    "ProblemBankRecord",
    "ProblemBankStore",
    "ProblemCorpusError",
    "ProblemProvenanceMeta",
    "ProblemVerifyMeta",
    "load_problem_bank_records",
    "main",
    "populate_problem_bank",
]
