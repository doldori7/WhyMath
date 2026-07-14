# WH-S 솔버 하네스 실가동 기록 — S2-02 (2026-07-14)

> **acceptance**: ① WH-S 배치가 동등문제에 검증 풀이·PRM 라벨 공급 ② 3-tier 검증 통과율 기록.
> 본 문서가 그 실측 기록의 정본이다. 재현 절차는 `data/corpus/whs_prm_v0/_provenance.json`.

## 0. 전제 슬라이스 — 코퍼스 검증 단계 체인 (S2-02 본편)

WH-S가 소비할 단계가 코퍼스에 없었다(`verify.solution_steps` 0/620 — Phase 2a부터 "WH-S 솔버
몫"으로 유보된 좌석). 15개 스켈레톤 생성기 전부에 **검증 가능 단계 체인 방출**을 구현했다:

| 패밀리 | 체인 형태 (전이 전부 SymPy 동치 증명) |
|---|---|
| QUAD-EQ (185·MC 포함) | 전개형 → 인수분해형 / 완전제곱형(무리근) |
| CALC 5종 (180) | **도함수 다항식** → 인수분해/완전제곱형 (`Derivative()` 전이는 unverifiable 실측 — 미분 자체는 해설 서술·체인은 도함수부터) |
| EXP/LOG (45) | 닫힌형 평가 `log(32,2) → 5` / `7**2 → 49` (방정식 변형 체인은 unverifiable 실측 — 금지) |
| ARITH/GEO-SEQ·SUM (155) | 공식 대입식 → 값 |
| IND-SEQ (30) | 점화 전개 → 일반항 대입식 → 값 (3단) |
| TRIG-VAL (13) | 도(°)식 → 라디안식 → 정확값 (3단) |
| TRIG-EQ (12) | 해 대입 검산: 좌변 함숫값 → 우변 특수값 |

- **게이트 봉인**: 수용 게이트(S2-a)의 verified는 전 전이 correct + unverifiable 0을 요구
  (acceptance.py) — steps를 방출하는 순간 배치 적재 자체가 Tier2 통과를 강제한다.
  배치 수율 620/620 유지·**slug 집합 완전 동일**(발문·answer·conditions 불변·verify 블록만 확장).
- **상시 게이트 승격**: `corpus_reverify`(S6 야간 CI)가 steps 보유 레코드의 전이 연쇄를
  재검산하도록 확장 — 상시 게이트가 Tier1-only에서 **Tier1+Tier2**로 승격됐다.
  incorrect(확정 오염)만 fail(모듈 정직 규약 유지).
- **rephrase 전파**: 483건에 수학키 조인으로 steps 전파(reconcile 스크립트 확장 —
  rephrase는 발문만 다르고 conditions·answer 동일이라 체인 유효성 동일).

## 1. 3-tier 검증 통과율 (acceptance ②)

검증 스택 = Tier1 답 검산(`verify_answer`) + Tier2 단계 연쇄(`verify_solution`) +
combiner(`whs.verdict.final_verdict`). `whs/baseline.run_baseline`으로 전 620문 실측:

| 밴드(잠정 매핑¹) | n | verified | unverified | failed | solve_rate |
|---|---|---|---|---|---|
| 교과기본 (<2.5) | 334 | 334 | 0 | 0 | 1.0000 |
| 준킬러 (2.5~3.5) | 234 | 234 | 0 | 0 | 1.0000 |
| 킬러 (>3.5) | 52 | 52 | 0 | 0 | 1.0000 |
| **전체** | **620** | **620** | **0** | **0** | **1.0000** |

¹ 밴드는 `difficulty_overall`의 잠정 구간 매핑(§5 사다리 정본 라벨링은 후속) — 킬러 구간은
"코퍼스 내 상대 상위"이지 수능 킬러 실난도 보증이 아니다.

**⚠️ 순환성 정직 고지**: 이 1.0000은 **파이프라인 무결성 지표**다 — 평가 대상이 생성기
construction trace(구성상 정답)라 자기 답을 되먹인 측정이며, 설계 §9 S0 게이트가 궁극적으로
요구하는 "시드 모델이 풀어보는" 풀이 능력 곡선이 아니다. LLM 정책(Ollama·MCTS-lite) 탐색이
붙는 시점에 이 수치는 1.0 미만으로 떨어지는 것이 정상이며, 그때부터가 진짜 베이스라인이다.

## 2. WH-S 하네스 실가동 — replay 배치 (acceptance ①)

`whs/corpus_replay.py`(신규): 코퍼스 체인을 **실제 하네스 루프(`run_solver`)**로 replay —
`ChainReplayPolicy`가 `SolverPolicy` 좌석을 구현(런타임 노드 id로 parent 체이닝·하네스 무변경),
도구 8종 중 parse→retrieve→apply_strategy(체인)→(결함 주입 오분기+log_deadend)→finalize를 구동.
불변식(verify 없는 finalize 거부·failed 차단·dedup 멱등·dead-end 회피)은 하네스가 강제.

실측 (로컬 PostgreSQL 16·alembic head·620문 전량):

| 지표 | 값 |
|---|---|
| replay 대상/성공 | 620 / 620 (실패 0) |
| finalize | **620 전건 verified** (파이프라인 무결성 — §1 고지 동일) |
| `solution_nodes` | 1,902 (= 루트 620 pending + 전이 663 VERIFIED + 오분기 619 FAILED) |
| `verified_solutions` (bank) | 620 (dedup 멱등) |
| `dead_end_log` | 619 |
| 오분기 미주입(bad_skipped) | 1 (비동치 증명 실패 — 날조 금지·정직 집계) |

- good 663 = 전이 총수 검산: 2단 체인 575문×1 + 3단 체인(TRIG-VAL 13·IND-SEQ 30)×2 + TRIG-EQ 12×1 ✓
- **결함 주입 오분기**: 마지막 단계 부호 반전(sign-flip 오개념 미러) — `verify_step`이
  incorrect(비동치)로 **증명한 경우에만** FAILED 노드로 주입(강등전 §3 방법론 미러·ground truth 기지).

## 3. PRM 학습셋 공급 (acceptance ①)

기존 `prm_builder`/`prm_builder_export_cli`(재구현 0)가 라벨된 노드에서 export:

- **산출**: `data/corpus/whs_prm_v0/prm_dataset.jsonl` — **1,282 학습쌍** (good 663 · bad 619)
- 회계: total_input 1,282 · excluded_uncertain 0(PENDING 루트는 구조 배제) · deduped 0 ·
  prm_score 전건 null(PRM 모델 미학습 — confidence 날조 금지)
- 커버리지: 620 문제 전수 · 데이터카드 = `_provenance.json`(정직 고지 4항 포함)

## 4. 검증 (게이트)

- 회귀: `l3/equivalent` + harness + corpus_quality + whs **907 passed / 2 skipped**
- 통합(@integration·실 PG): replay 왕복 1건 — finalize verified·노드 라벨(good/bad)·bank
  적재·`build_prm_dataset` good+bad 산출 봉인 (`tests/backend/whs/test_corpus_replay.py`)
- 승격 reverify: 생성 620·rephrase 483 전건 통과(Tier1+Tier2)
- ruff·black(100)·mypy strict: 신규/변경 모듈 clean

## 5. 잔여 (정직 스코프 — 후속)

- **LLM 정책 탐색**(Ollama·Phaiakes9·MCTS-lite): 진짜 풀이 능력 베이스라인·실탐색 bad 라벨.
  S1-12(라이브 개통 실측·Kiki) 이후. 이 replay가 적재한 bank가 그때의 웜스타트가 된다.
- 밴드 정본 라벨링(§5 사다리)·Dead-End Log의 PRM bad 신호 통합·Tier3(Lean4).
- killer/conceptual/misconception-MC 뱅크의 steps 방출(별도 생성기 계열 — 이번 스코프 밖).
