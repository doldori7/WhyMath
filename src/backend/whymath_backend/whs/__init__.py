"""WH-S 솔버 하네스 서브시스템 — 시스템이 *스스로 푸는* 하네스(설계 `03b_*`).

WH-1(튜터링 하네스)이 학생을 가르치는 하네스라면, WH-S는 시스템의 수학 풀이 능력을 검증
가능한 자기 진화 루프로 상승시키는 *업스트림* 서브시스템이다. 7계층 원칙(§7.5): WH-S는
WH-1의 L1(데이터)·L3(검증) 자산을 공급하는 업스트림이며 **학생 세션 경로에 직접 개입하지
않는다** — 오프라인 라이브러리(발화·API 노출 없음)다.

현 좌석(S0): ① Tier1+2 판정 combiner(`verdict.py`)와 ② 베이스라인 풀이율 측정 하네스
(`baseline.py`). Tier1 수치 답 검산은 `l3/verify_answer.py`, Tier2 기호 단계 동치는
`l3/verify_solution.py`(둘 다 기존/신규 좌석)이고, `verdict.py`는 그 둘의 결과를 §4 판정 규칙으로
결합해 최종 등급(verified/unverified/failed)을 낸다. `baseline.py`는 그 검증기 스택을 *문제셋*에
돌려 §5 난이도 사다리별 풀이율(verified 비율)을 집계한다(§9 S0 게이트 산출물 — 풀이율 곡선).

S1 좌석(풀이 트리 상태 계층): ③ 풀이 경로 트리 노드 ORM(`db/models/solution_node.py` —
`SolutionNode`·`NodeVerifyStatus`·§2.1)과 ④ 그 비동기 CRUD 저장소(`node_store.py`). 솔버
루프·MCTS·도구 8종이 이 저장소로 트리 노드를 생성·조회·갱신한다(루프 본체는 후속).

S1 좌석(상태 저장소 — 추가): ⑤ 실패 접근 로그(`db/models/dead_end_log.py` `DeadEndLog`·§2.3)와
그 저장소(`dead_end_store.py` — `log_dead_end` 멱등·`is_dead_end` 회피 조회·`get_dead_ends`).
⑥ 검증 풀이 저장소(`db/models/verified_solution.py` `VerifiedSolution`·`WhsSolutionGrade`·§2.4)와
그 저장소(`solution_bank.py` — `bank_solution`·`get_solutions`·`get_verified`[학습 안전 필터]).
탐색 정책이 ⑤로 같은 막다른 길을 회피하고, `finalize`가 ⑥에 완전 풀이를 커밋한다(둘 다 루프 본체는
후속). ⑥은 등급 enum에 failed를 배제(§3·R-S2)하고 `get_verified`로 학습 데이터에서 unverified를
구조 격리한다.

S1 좌석(상태 저장소 — 완성): ⑦ 검증된 중간 결과 저장소(`db/models/verified_lemma.py`
`VerifiedLemma`·§2.2)와 그 저장소(`lemma_store.py` — `log_lemma` 멱등·`find_lemma` 재사용
조회·`get_lemmas`). 탐색이 verify 통과 부분 결과를 ⑦에 적재하고 다른 가지가 `find_lemma`로
재사용해 중복 탐색을 제거한다(검증된 보조정리만 담음 — 등급 컬럼 없음). 이로써 §2.1~§2.4 *상태
저장소 4종(트리·실패 로그·검증 풀이·검증 보조정리)* 전부 영속.

S1 좌석(솔버 루프 골격 — 추가): ⑧ `harness.py` `run_solver(session, *, problem_id, policy,
max_tool_calls)` — `SolverPolicy`(도구 선택 두뇌·주입)를 받아 도구 8종을 실행하고 검증기 스택·상태
저장소 4종에 결선하는 *결정론 루프 드라이버*. 생성 도구(parse/decompose/apply_strategy) 내용은
정책이 공급(프로덕션=LLM·테스트=`ScriptedPolicy`)하고, 하네스는 §3·§4 불변식을 강제한다 — verify
없는 finalize 거부·failed 차단·unverifiable→unverified 격리·탐색 예산 상한·dead-end 회피·검증
보조정리만 log_lemma. 액션 10종은 `kind` 판별 Pydantic 유니온.

S1 좌석(자기 진화 데이터 — 순수 코어): ⑨ `self_evolution.py` `build_sft_dataset(solutions, *,
dedup=True) -> SftDataset` — 솔버가 적재한 *verified* 풀이를 SFT 학습 레코드(`SftRecord`)로
변환한다. **verified만**(R-S2 심층 방어·`unverified` 배제·배제 건수 정직 집계)·`(problem_id,
지문)` 재발견 dedup(#256 export 레벨 연장). 실 DB export 진입점은 `solution_bank.get_all_verified`
(전 문제 verified)·`iter_sft_jsonl`(JSONL)·ops CLI(`self_evolution_export_cli`)다.

S1 좌석(자기 진화 export — 스트리밍): ⑩ 대규모 메모리 가드 — `solution_bank.stream_all_verified`
(서버측 커서 `stream_scalars`로 verified를 1건씩)·`self_evolution.stream_sft_jsonl(rows,
accounting, *, dedup=True)`(verified 필터·dedup·JSONL을 스트리밍·`SftStreamAccounting`에 누적)으로
전량 list 적재 없이 export한다. ops CLI는 `--stream` 옵트인(출력은 일괄과 동일·메모리만 바운드).

범위 밖(후속·환경 밖): LLM 정책 모델(Ollama·Phaiakes9)·생성 도구 내용 생성·MCTS-lite 탐색·자기
진화 *실 DB export·PRM·Tier3*(§9 로드맵). 본 패키지는 *상태 저장소 4종 + 결정론 루프 골격 + 자기
진화 변환 코어*까지 둔다.
"""

from __future__ import annotations

from whymath_backend.db.models.dead_end_log import DeadEndLog
from whymath_backend.db.models.solution_node import (
    NodeVerifyStatus,
    SolutionNode,
)
from whymath_backend.db.models.verified_lemma import VerifiedLemma
from whymath_backend.db.models.verified_solution import (
    VerifiedSolution,
    WhsSolutionGrade,
)
from whymath_backend.whs.baseline import (
    BandResult,
    BaselineReport,
    DifficultyBand,
    EvalItem,
    run_baseline,
)
from whymath_backend.whs.dead_end_store import (
    get_dead_ends,
    is_dead_end,
    log_dead_end,
)
from whymath_backend.whs.harness import (
    Action,
    ApplyStrategyAction,
    ConjectureCheckAction,
    DecomposeAction,
    EndSearchAction,
    FinalizeAction,
    LogDeadEndAction,
    LogLemmaAction,
    ParseProblemAction,
    RetrieveSimilarAction,
    ScriptedPolicy,
    SolverOutcome,
    SolverPolicy,
    SolverState,
    ToolResult,
    VerifyAction,
    run_solver,
)
from whymath_backend.whs.lemma_store import (
    find_lemma,
    get_lemmas,
    log_lemma,
)
from whymath_backend.whs.node_store import (
    create_node,
    get_children,
    get_node,
    get_roots,
    increment_visits,
    update_evaluation,
)
from whymath_backend.whs.self_evolution import (
    SftDataset,
    SftRecord,
    SftStreamAccounting,
    build_sft_dataset,
    iter_sft_jsonl,
    stream_sft_jsonl,
    to_sft_record,
)
from whymath_backend.whs.solution_bank import (
    bank_solution,
    get_all_verified,
    get_solutions,
    get_verified,
    solution_fingerprint,
    stream_all_verified,
)
from whymath_backend.whs.verdict import (
    WhsGrade,
    WhsVerdict,
    final_verdict,
)

__all__ = [
    "Action",
    "ApplyStrategyAction",
    "BandResult",
    "BaselineReport",
    "ConjectureCheckAction",
    "DeadEndLog",
    "DecomposeAction",
    "DifficultyBand",
    "EndSearchAction",
    "EvalItem",
    "FinalizeAction",
    "LogDeadEndAction",
    "LogLemmaAction",
    "NodeVerifyStatus",
    "ParseProblemAction",
    "RetrieveSimilarAction",
    "ScriptedPolicy",
    "SftDataset",
    "SftRecord",
    "SftStreamAccounting",
    "SolutionNode",
    "SolverOutcome",
    "SolverPolicy",
    "SolverState",
    "ToolResult",
    "VerifiedLemma",
    "VerifiedSolution",
    "VerifyAction",
    "WhsGrade",
    "WhsSolutionGrade",
    "WhsVerdict",
    "bank_solution",
    "build_sft_dataset",
    "create_node",
    "final_verdict",
    "find_lemma",
    "get_all_verified",
    "get_children",
    "get_dead_ends",
    "get_lemmas",
    "get_node",
    "get_roots",
    "get_solutions",
    "get_verified",
    "increment_visits",
    "is_dead_end",
    "iter_sft_jsonl",
    "log_dead_end",
    "log_lemma",
    "run_baseline",
    "run_solver",
    "solution_fingerprint",
    "stream_all_verified",
    "stream_sft_jsonl",
    "to_sft_record",
    "update_evaluation",
]
