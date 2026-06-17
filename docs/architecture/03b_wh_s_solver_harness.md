# WhyMath 솔버 하네스(WH-S) 설계안 v0.1

> **목적**: WhyMath 시스템 자체의 수학 문제해결능력 — 새로운 유형·고난도·난해한
> 문제에 대한 *검증 가능한* 해결 — 을 자기 진화 루프로 점진 상승시키는
> 독립 서브시스템 설계.
> 
> **자매 문서**: WhyMath 튜터링 하네스(WH-1) 설계안 v0.3 — WH-1은 학생을 가르치는
> 하네스, WH-S는 시스템이 스스로 푸는 하네스다. 두 하네스는 상태 관리·검증기 등
> 인프라를 공유하되 목적·보상·운영 모드가 다르다 (§8 비교표).
> 
> 작성일: 2026-06-13 | 버전: 0.1

> **편집자 주 (저장소 정합, 2026-06-12)**: 원안 prose를 보존하되, 잠금된 기술 결정과의 정합을 위해
> **ChromaDB → pgvector**로 교정했다(§8 비교표 1건) — 2026-06-10 슬98: 벡터 store를 PostgreSQL 16
> 확장(pgvector)으로 통합하고 별도 ChromaDB를 폐기. 현 구현 좌석과의 매핑은 문서 끝
> "현 구현 매핑(편집자 부기)" 절 참조.

-----

## 0. 핵심 논리 — 왜 솔버는 튜터보다 확실한가

WH-1의 최대 리스크는 R1(튜터링 품질의 보상 신호 부재)이었다.
WH-S에는 이 문제가 **존재하지 않는다**: 수학 풀이의 옳고 그름은
SymPy 검산·수치 대입·형식 증명(Lean)으로 기계 판정이 가능하다.
즉 하네스-1이 검색에서 성공한 조건(객관 보상 = 리콜)이
수학 풀이에는 더 강한 형태로 존재한다.

이 경로는 이미 입증된 전례가 있다:

|시스템                                         |핵심 구성                                      |결과                            |
|--------------------------------------------|-------------------------------------------|------------------------------|
|rStar-Math (Microsoft, 2025.1)              |7B 소형 모델 + MCTS + 과정 보상 모델(PPM), 자기 진화 4라운드|MATH 58.8% → 90.0%, AIME 상위권  |
|AlphaProof + AlphaGeometry2 (DeepMind, 2024)|Lean 검증기를 보상으로 한 RL + 트리 탐색                |IMO 2024 은메달 (6문제 중 4, 28/42점)|
|STaR (2022)                                 |검증 통과 풀이만 골라 재학습하는 부트스트랩                   |자기 생성 데이터로 추론 능력 향상의 원형       |
|하네스-1 (2026.6)                              |상태 외부화 + 도구 루프, 약 4,400개 데이터               |20B로 대형 상용 모델 검색 성능 능가        |

공통 교훈: **“모델 크기보다 환경(검증기 + 상태 관리 + 탐색)이 능력 상승을 결정한다.”**
이것이 1인 개발·로컬 워크스테이션(Phaiakes9) 체제에서 WH-S가 성립하는 근거다.

-----

## 1. 시스템 개요

```
┌─────────────────────────────────────────────────────────┐
│                      WH-S 솔버 하네스                      │
│                                                         │
│  [문제 큐] → [웜 스타트: 유사 문제·패턴 검색]                │
│      ↓                                                  │
│  [솔버 루프]  LLM(정책) ⇄ 8개 도구 ⇄ 풀이 상태(트리)        │
│      ↓                                                  │
│  [검증기 스택]  Tier1 수치 → Tier2 기호 → Tier3 형식        │
│      ↓                                                  │
│  [판정] 통과 → 검증 풀이 저장소 / 실패 → 실패 로그            │
│      ↓                                                  │
│  [자기 진화]  검증 풀이 → SFT/RL 데이터 → 모델 갱신 → 반복    │
└─────────────────────────────────────────────────────────┘
```

운영 모드는 **오프라인 배치**다. 학생 응대(WH-1)와 달리 레이턴시 제약이 없으므로,
난해한 문제 1개에 수 분~수십 분의 탐색 컴퓨트를 투입할 수 있다.
이것이 test-time compute 스케일링이며, WH-S 능력의 절반은 여기서 나온다.

-----

## 2. 풀이 상태 설계 (Solver State)

하네스-1의 “후보 문서 저장소 / 큐레이션 세트 / 증거 그래프”를 솔버용으로 번역:

### 2.1 풀이 경로 트리 (Solution Tree)

- 노드 = 풀이 상태(현재까지의 변형·중간 결과), 엣지 = 풀이 행동(전략 적용)
- MCTS 방식 확장: 방문 횟수, 과정 보상 추정치, verify 결과를 노드에 저장
- PostgreSQL: `solution_nodes(problem_id, parent_id, state_repr, action, prm_score, verify_status, visits)`

### 2.2 검증된 중간 결과 저장소 (Verified Lemma Store)

하네스-1의 큐레이션 세트에 해당. 탐색 중 verify를 통과한 부분 결과
(예: “이 식은 x>0에서 단조증가”)를 보관 — 다른 가지에서 재사용하여 중복 탐색 제거.
난해한 문제일수록 이 재사용이 탐색 효율을 결정한다.

### 2.3 실패 접근 로그 (Dead-End Log)

같은 막다른 길의 재진입을 차단. `(state_hash, action)` 쌍을 기록하고
탐색 정책이 이를 회피. 하네스-1의 “중복 자동 압축·정리”에 해당하며,
LLM의 고질적 약점(같은 실수 반복)을 상태 관리로 구조 차단한다.

### 2.4 검증 풀이 저장소 (Verified Solution Bank)

최종 통과한 완전 풀이 경로. 두 가지 용도:
① 자기 진화 학습 데이터 (§5) ② WH-1 튜터의 콘텐츠 원천 (§7)
한 문제의 **다중 풀이 경로**(대수적/기하적/귀납적)를 모두 보관 — 풀이 다양성 자체가 자산.

-----

## 3. 전용 도구 8종

|#|도구                       |기능                                    |비고                   |
|-|-------------------------|--------------------------------------|---------------------|
|1|`parse_problem`          |문제 텍스트 → 구조화 표현 (조건, 구할 것, 도메인, 패턴 후보)|CSAT 55+108 패턴 분류기 결합|
|2|`retrieve_similar`       |검증 풀이 저장소·패턴 DB에서 유사 문제·풀이 검색         |웜 스타트 (§4)           |
|3|`decompose`              |부분문제 분해 / 보조 목표 설정                    |풀이 트리 분기 생성          |
|4|`apply_strategy`         |전략 적용 1스텝 (치환, 케이스 분할, 보조선, 귀류 등)     |WH-1 §11.1 전략 사전 공유  |
|5|`verify`                 |Tier1~3 검증기 스택 호출 (§4)                |모든 중간 단계에 적용 가능      |
|6|`conjecture_check`       |추측의 수치 반례 탐색 (랜덤+경계값 대입)              |가지치기용 — 거짓 추측 조기 폐기  |
|7|`log_lemma / log_deadend`|중간 결과·실패 기록                           |§2.2, §2.3           |
|8|`finalize`               |완전 풀이 조립 + 최종 검증 + 저장소 커밋             |end_search 대응        |

WH-1과 마찬가지로 **verify 없는 finalize는 하네스가 거부**한다.
단 WH-1의 3상태와 달리, WH-S에서 unverifiable 최종 풀이는 저장소에
`unverified` 등급으로 격리 — 학습 데이터로 절대 사용하지 않는다 (보상 해킹 차단, §6 R-S2).

-----

## 4. 검증기 스택 (Verifier Stack) — WH-S의 심장

검증 가능성의 경계가 곧 WH-S 능력의 경계다. 3계층으로 설계한다:

### Tier 1 — 수치 검증 (커버리지 최광, 신뢰도 최저)

- 답 검산: 구한 답을 원 조건에 대입, 랜덤 수치 샘플 + 경계값/특이점 검사
- 적용 범위: 단답형·객관식 (수능 문항의 대부분)
- 한계: 과정이 틀려도 답이 맞는 경로를 통과시킴 → 단독 사용 금지

### Tier 2 — 기호 검증 (주력)

- SymPy: 식 변형의 동치성, 방정식 해의 완전성(근 누락 검사), 미적분 연산 검산
- 단계별 적용: 풀이 트리의 *모든 변형 엣지*에 동치 검증 → 과정 수준 보장
- 과정 보상 모델(PRM): Tier 2 통과 이력으로 자체 PRM을 점진 구축
  (rStar-Math의 PPM 방식 — 사람 라벨 없이 검증 결과에서 과정 보상 학습)

### Tier 3 — 형식 검증 (커버리지 최협, 신뢰도 최고)

- Lean 4 + Mathlib(약 200만 라인, Apache 2.0): 증명 문제의 기계 검증
- **전제 과제 — 자동형식화(autoformalization)**: 한국어 문장제 → Lean 명제 변환은
  현재 기술의 난제. 따라서 Tier 3은 다음 순서로만 확장:
  ① 이미 형식화된 문제군(miniF2F, Mathlib 연습문제)에서 증명 능력 학습
  ② 한국 교육과정 핵심 정리 ~100개의 수동 형식화 (1회성 투자)
  ③ 자동형식화는 장기 과제로 보류
- 즉 **초기 WH-S의 “검증 가능한 해결”은 Tier 1+2 범위(답 중심 문제)에서 성립**하고,
  증명 문제는 Tier 3 성숙도에 따라 단계 확장한다. 이 경계를 제품 주장에도 정직하게 반영한다.

### 판정 규칙

`최종 통과 = Tier1 통과 AND 모든 단계 Tier2 통과 (증명 문제는 + Tier3)`
이중 체크로 “틀린 과정-맞는 답” 경로의 학습 데이터 유입을 차단한다.

-----

## 5. 자기 진화 루프 (Self-Evolution Loop) — 점진 개선의 엔진

STaR/rStar-Math 레시피의 WH-S 구현. **검증기가 라벨러를 대체**하므로
사람 채점 없이 라운드가 돈다:

```
라운드 r:
  1. 문제 풀 P_r 구성 (현 능력 경계 ± α 난이도 — IRT 곤란도 기반)
  2. 현 정책 모델 M_r이 WH-S 루프로 P_r 탐색 (문제당 N회 시도, MCTS)
  3. 검증기 스택 통과 풀이만 채택 → 학습 셋 D_r
     (한 문제의 다중 풀이는 모두 채택 — 풀이 다양성 학습)
  4. M_r + D_r → SFT → M_{r+1}
     (선택: Tier2 단계 통과/실패 쌍으로 PRM 갱신 → 탐색 효율 동반 상승)
  5. 풀이율 측정 → 난이도 경계 상향 → 라운드 r+1
```

**규모 감각**: rStar-Math는 4라운드로 7B 모델을 MATH 90%까지 올렸고,
하네스-1은 약 4,400개 데이터로 충분했다. WH-S의 라운드당 목표를
“검증 풀이 1,000~2,000개”로 잡으면 1인 개발 + Phaiakes9 체제에서 현실적이다.

**난이도 사다리**: 기존 자산을 그대로 활용 —
교과 기본(545노드 연계 문항) → 수능 준킬러 → 수능 킬러(시그니처 패턴 55+108)
→ KMO 1차 → KMO 2차/IMO 셀렉션. 각 단계의 풀이율이 임계치(예: 60%)를
넘으면 다음 단계 문제를 풀에 혼입한다. “새로운 유형”에 대한 점진 개선은
이 사다리에서 **미학습 패턴의 초견 풀이율**로 직접 측정된다.

**기반 모델과 약관**: 자기 진화의 시드는 오픈 가중치 수학 특화 모델
(Qwen3-Math, DeepSeek-Math 계열)로 한다. 자기 생성 데이터로 학습하므로
WH-1 §7에서 문제가 됐던 상용 모델 출력 약관 이슈(R13)가 원천적으로 없다.

-----

## 6. 리스크 레지스터

|ID  |리스크                                           |심각도|대응                                                                                                   |
|----|----------------------------------------------|---|-----------------------------------------------------------------------------------------------------|
|R-S1|**검증 가능성 경계**: 서술형 증명·기하 작도는 Tier3 미성숙 시 검증 불가|높음 |§4 단계 확장 원칙, 능력 주장을 Tier1+2 범위로 한정                                                                   |
|R-S2|**보상 해킹**: 약한 검증기(수치 대입)를 우회하는 틀린 과정 학습       |높음 |§4 판정 규칙(전 단계 Tier2 필수), unverified 풀이 학습 배제                                                         |
|R-S3|**분포 정체**: 자기 생성 데이터만 학습 → 풀이 스타일 동질화·다양성 붕괴  |중간 |다중 풀이 전량 채택, 온도·전략 시드 다양화, 라운드마다 외부 검증 셋(미공개 기출)으로 일반화 측정                                            |
|R-S4|**컴퓨트 병목**: MCTS 탐색 + 라운드별 SFT의 Phaiakes9 부하  |중간 |오프라인 배치(야간), 문제당 탐색 예산 상한, QLoRA 미세조정으로 학습 비용 절감                                                     |
|R-S5|**자동형식화 난제**: 한국어 문장제→Lean 변환 실패              |확실 |Tier3을 장기 트랙으로 분리, 초기 능력 주장에서 제외 (§4)                                                                |
|R-S6|**난이도 추정 오류**: 문제 풀 난이도가 능력 경계와 어긋나면 라운드 효율 급락|중간 |IRT 곤란도 + 직전 라운드 풀이율로 동적 보정                                                                          |
|R-S7|**저작권**: 기출·경시 문제의 학습 데이터 사용                  |중간 |기존 저작권 가이드 v2.0의 4-Tier 전략 준수 — A등급(NuminaMath Apache 2.0, PRM800K MIT, MATH/GSM8K MIT) 우선, 기출은 평가 전용|

-----

## 7. WhyMath 제품과의 결합 — WH-S가 WH-1을 먹여 살리는 구조

WH-S는 연구 장난감이 아니라 제품 자산 생산 라인이다:

1. **킬러 문항 힌트 품질**: 검증된 다중 풀이 경로가 있어야 WH-1이
   “학생이 택한 접근에 맞는” 힌트를 줄 수 있다. 현재 LLM 즉석 풀이의
   환각 위험을 검증 풀이 저장소 조회로 대체.
1. **영재/KMO 트랙 콘텐츠**: 경시 수준 풀이·유사 문제 변형의 자체 생산 능력 —
   외부 콘텐츠 라이선스 의존도 하락.
1. **신유형 사전 검증**: 출제 변형 문항(표면 치환)의 풀이 가능성·난이도를
   WH-S가 사전 판정 → WH-1 §11.5 전이 측정용 문항 공급.
1. **PRM 공유**: WH-S가 구축한 과정 보상 모델은 WH-1 verify_step의
   PRM 점수 품질을 직접 개선한다 (PRM800K의 영어 분포 한계 보완).
1. **경계 유지**: WH-S는 WH-1의 L1(데이터)·L3(검증) 자산을 공급하는
   업스트림이며, 학생 세션 경로에는 직접 개입하지 않는다 — 7계층 원칙 유지.

-----

## 8. WH-1 vs WH-S 비교 요약

|차원    |WH-1 (튜터링 하네스)                                                 |WH-S (솔버 하네스)            |
|------|---------------------------------------------------------------|-------------------------|
|목적    |학생의 학습을 견인                                                     |시스템의 풀이 능력을 상승           |
|보상 신호 |부재 → 대리 지표 (최대 리스크 R1)                                         |**검증기 = 객관 보상** (리스크 아님) |
|운영 모드 |온라인, 레이턴시 민감                                                   |오프라인 배치, 컴퓨트 자유          |
|핵심 상태 |오개념 가설 세트 + 증거 그래프                                             |풀이 트리 + 보조정리 저장소 + 실패 로그 |
|자기 개선 |RL 보류 (보상 설계 후)                                                |**자기 진화 루프 즉시 가동 가능**    |
|능력 측정 |종단 지표 (도움 감소·전이) — 분기 단위                                       |풀이율·초견 패턴 풀이율 — 라운드 단위 즉시|
|모델 학습 |약관 검토 필요 (교사 모델)                                               |자기 생성 데이터 — 약관 이슈 없음     |
|공유 인프라|전략 사전(§11.1) · verify 스택 · PRM · PostgreSQL/pgvector · Langfuse|                         |

-----

## 9. 도입 로드맵

|단계|작업                                               |게이트                                 |
|--|-------------------------------------------------|------------------------------------|
|S0|검증기 스택 Tier1+2 구축, 베이스라인 측정 (시드 모델의 난이도 사다리별 풀이율)|사다리별 풀이율 곡선 확보                      |
|S1|솔버 루프 구현 (도구 8종 + 풀이 트리 + MCTS-lite), 탐색 예산 튜닝   |탐색 적용 시 풀이율이 단발 생성 대비 유의 상승         |
|S2|자기 진화 라운드 1~2 (검증 풀이 1,000개+ → QLoRA SFT)        |라운드 간 풀이율 상승 + 외부 검증 셋 일반화 확인 (R-S3)|
|S3|PRM 구축 → 탐색 효율화, 난이도 사다리 상향 (준킬러→킬러)             |미학습 패턴 초견 풀이율 상승 = “새 유형” 능력의 직접 증거 |
|S4|WH-1 결합 (검증 풀이 저장소 → 힌트 파이프라인, PRM 공유)           |WH-1 verify_step 오탐률 개선             |
|S5|(장기) Tier3: miniF2F 증명 트랙, 핵심 정리 수동 형식화          |—                                   |

S0~S1은 자기 진화 없이도 독립 가치가 있다(탐색만으로 풀이율 상승 + 검증 풀이 자산 축적).
즉 WH-S 역시 “전부 아니면 전무”가 아니라 단계마다 회수 가능한 구조다.

-----

## 10. 종합 판단

- 시스템의 문제해결능력 점진 상승은 **기대가 아니라 입증된 경로**다
  (rStar-Math, AlphaProof, STaR). WH-S는 그 경로의 필수 인프라 —
  상태 관리(중복 탐색 제거) + 검증기(보상) + 자기 진화 파이프라인 — 를 제공한다.
- 단, “검증 가능한 해결”의 정직한 경계는 초기에 Tier1+2(답 중심 문제,
  수능 전 범위)이며, 증명 문제는 Tier3 성숙도에 따라 확장된다.
- WH-1과의 결정적 차이: 보상이 객관적이므로 **자기 진화를 지금 시작할 수 있다.**
  튜터링 품질(WH-1)이 측정의 문제로 신중 도입이 필요한 것과 달리,
  WH-S는 라운드 단위로 능력 상승이 수치로 찍히는 시스템이다.

-----

## 참고

- 하네스-1: arXiv 2606.02373, github.com/pat-jj/harness-1 (Apache 2.0)
- rStar-Math: arXiv 2501.04519 (Microsoft Research)
- AlphaProof/AlphaGeometry2: DeepMind 블로그, IMO 2024 결과 (2024.7)
- STaR: arXiv 2203.14465
- Lean Mathlib: Apache 2.0 / PRM800K: MIT / NuminaMath: Apache 2.0
- 자매 문서: WhyMath 튜터링 하네스(WH-1) 설계안 v0.3
-----

## 현 구현 매핑 (편집자 부기, 2026-06-12)

> 본 설계안은 *목표 상태*다. WH-S는 학생 세션에 직접 개입하지 않는 업스트림이며(§7.5·7계층 유지), 아래는 현 구현·연계 좌석이다.

|설계안 좌석           |현 구현·연계 (가동/예정)                                       |델타·비고                                  |
|-----------------|----------------------------------------------------|---------------------------------------|
|`verify` Tier2(SymPy·PRM)|L3 도구 검증(SymPy)·PRM·WH-1 `verify_step` 공유            |PRM 한국 분포 보정은 0단계/S0 과제              |
|`retrieve_similar`/패턴 DB|개념그래프·시그니처 패턴(55+108·ROADMAP)                       |검증 풀이 저장소(`solution_nodes`)는 향후 스키마    |
|난이도 사다리(IRT)     |L2 IRT(θ)·`compute_concept_abilities`               |자기진화 라운드는 Phase 2~3                  |
|자기진화 SFT/RL      |Phaiakes9·Ollama(Qwen3-Math·DeepSeek-Math)          |오픈 가중치 시드·자기생성 데이터(약관 청정·R-S7)       |
|벡터               |**pgvector**(ChromaDB 폐기·§8 비교표 교정)                 |Postgres 16 확장 통합                     |

`solution_nodes`(§2.1)·`Verified Lemma Store`(§2.2)·`Dead-End Log`(§2.3)·`Verified Solution Bank`(§2.4) **4종 상태 저장소 전부 스키마 구현됨** + **솔버 루프 골격**(`run_solver`·도구 8종 결선·불변식·LLM 정책은 주입)(S1 슬라이스 1·2·3·4·아래). 도입은 ROADMAP상 **S0~S1(검증기 Tier1+2·솔버 루프)은 Phase 2 모트, 자기진화·PRM(S2~S3)·Lean4 Tier3(S5)는 Phase 2~3**으로 단계화한다(1인 capacity 가드).

### S0 진행 (2026-06-13)

**S0 슬라이스 1 — Tier1 수치 답 검산기 + Tier1+2 판정 규칙** 구현됨(순수·마이그레이션 0·모델 무관). **Tier2(기호·SymPy 단계 동치)는 이미 존재**(WH-1에서 만든 `l3/verify_step.py`·`l3/verify_solution.py`·verify 스택 공유). 신규:
- **Tier1 수치 검산** `l3/verify_answer.py` `verify_answer(conditions: str | Sequence[str], answer, *, n_samples=8, tol=1e-9) -> AnswerVerdict(state[pass/fail/unverifiable]·reason·samples_checked)` — 답을 원 조건에 대입·잔차 자유변수 없으면 직접 수치 평가·있으면(파라미터) **고정 시드 수치 샘플링 + 경계값(0·±1·소·대)**. **등식·부등식(>,<,≥,≤,≠)·연립(여러 조건 AND)** 지원(함수 동치 항등식은 등식+샘플링으로 커버). 부등식은 진리값 평가(엄격 경계 tol→모호 unverifiable·등호 경계→포함)·연립은 하나라도 fail→fail/전부 pass→pass/미정→unverifiable. §4 정직성: pass는 *샘플 점 만족*이지 증명 아님(신뢰도 최저·단독 사용 금지·Tier2 결합 필수)·판정 불가→unverifiable(pass 위장 금지·verify_step 상속).
- **신규 `whymath_backend/whs/` 패키지**(WH-S 서브시스템·오프라인·학생 세션 미개입 업스트림·§7.5). `whs/verdict.py` `final_verdict(answer: AnswerVerdict, steps: SolutionVerificationResult) -> WhsVerdict(grade[verified/unverified/failed]·reason·근거)` — §4 판정 규칙: **failed**=Tier1 fail OR 단계 incorrect(틀린 과정 차단·이중 체크)·**verified**=Tier1 pass AND 전 단계 correct·**unverified**=판정 불가 격리(§3·R-S2 보상 해킹 차단·*학습 데이터 배제*).
- **베이스라인 풀이율 하네스** `whs/baseline.py`(§9 S0 게이트 산출물·순수·모델 0): `DifficultyBand`(§5 사다리 5단계 교과기본·준킬러·킬러·KMO1차·KMO2차)·`EvalItem`(band·conditions·answer·steps)·`run_baseline(items) -> BaselineReport`(밴드별 BandResult: n·verified/unverified/failed·**solve_rate=verified/n**[검증 통과만 해결·unverified 격리·failed 미해결]·overall 포함·5밴드 항상). 검증기 스택(verify_answer+verify_solution+final_verdict)을 *이미 생성된* 평가 항목에 돌려 "사다리별 풀이율 곡선" 집계. 결정론(고정 시드). **시드 모델로 후보 풀이 생성은 범위 밖**(후속·하네스는 모델 출력의 검증·집계 착지점).
- **후속(S0 잔여·S1+)**: 시드 모델 실행으로 후보 풀이 *생성*(Ollama·Phaiakes9·MCTS)·솔버 루프(도구 8종)·PRM·Tier3(Lean4).

### S1 진입 (2026-06-13)

**S1 슬라이스 1 — 풀이 트리 상태 스키마 + 저장소**(설계 §2.1) 구현됨(마이그레이션 동반·**LLM 정책 모델 구동은 후속**). 솔버 루프가 쓸 *상태 계층*만:
- `db/models/solution_node.py` `SolutionNode`(테이블 `solution_nodes`)·`NodeVerifyStatus`(pending/verified/unverified/failed): `id`(UUID PK)·`problem_id`(UUID·인덱스·**FK 아님**·WH-S 독립 오프라인 느슨참조)·`parent_id`(self-FK `ondelete=CASCADE`·트리 부모·루트 NULL)·`state_repr`(JSONB)·`action`(Text)·`prm_score`(Float)·`verify_status`(enum·default pending)·`visits`(int·MCTS 방문)·`created_at`/`updated_at`. 인덱스 `problem_id`·`parent_id`.
- 마이그레이션 **`c2d3e4f5a6b7`**(down_revision `b1c2d3e4f5a6`·단일 head·upgrade=테이블+enum 자동생성+인덱스2·downgrade=인덱스→테이블→enum 명시 drop·가역).
- `whs/node_store.py`(비동기 저장소·순수 ORM·원시 SQL 0): `create_node`·`get_node`·`get_children`·`get_roots`·`increment_visits`(원자적)·`update_evaluation`. WH-S 오프라인(API 노출 0·§7.5).
- **후속(S1 잔여)**: 솔버 루프(LLM 정책·MCTS-lite·도구 8종)·§2.2 Verified Lemma Store 저장소.

**S1 슬라이스 2 — 실패 접근 로그 + 검증 풀이 저장소**(설계 §2.3·§2.4) 구현됨(마이그레이션 동반·**솔버 루프 구동은 후속**). 솔버 상태 저장소 2종:
- **§2.3 `dead_end_log`** `db/models/dead_end_log.py` `DeadEndLog`: `id`(UUID PK)·`problem_id`(UUID·**FK 아님**·느슨참조)·`state_hash`(Text)·`action`(Text)·`reason`(Text nullable)·`created_at`. **`(problem_id, state_hash, action)` UNIQUE**(멱등 — 중복 막다른 길 1행). 저장소 `whs/dead_end_store.py`: `log_dead_end`(ON CONFLICT DO NOTHING 멱등)·`is_dead_end`(EXISTS 회피 조회)·`get_dead_ends`. 탐색 정책이 행동 적용 전 `is_dead_end`로 재진입 차단(같은 실수 반복 구조 차단).
- **§2.4 `verified_solutions`** `db/models/verified_solution.py` `VerifiedSolution`·`WhsSolutionGrade`: `id`(UUID PK)·`problem_id`(느슨참조)·`grade`(enum **verified/unverified만**·failed 구조 배제·§3·R-S2)·`solution_path`(JSONB)·`strategy_tag`(Text nullable·대수/기하/귀납 다중 풀이 태그)·`answer`(Text nullable)·`source_root_id`(UUID nullable·**FK 아님**·내구 자산이라 트리 GC 비강결합)·`created_at`. 인덱스 `(problem_id, grade)`. `problem_id` UNIQUE 없음(다중 풀이). 저장소 `whs/solution_bank.py`: `bank_solution`(finalize 커밋)·`get_solutions`(전체)·`get_verified`(**verified만**·학습 데이터에서 unverified 격리·R-S2). `finalize`가 완전 풀이를 커밋.
- 마이그레이션 **`f1a2b3c4d5e6`**(down_revision `e0f1a2b3c4d5`·단일 head·upgrade=테이블 2 + enum 자동생성 + 인덱스 1·downgrade=verified_solutions[인덱스→테이블→enum 명시 drop]→dead_end_log 테이블·가역).
- **후속(S1 잔여)**: 솔버 루프(도구 `log_deadend`·`finalize`가 위 저장소 호출)·§2.2 Verified Lemma Store(아래 슬라이스 3)·해시 스킴 표준화.

**S1 슬라이스 3 — 검증된 중간 결과 저장소**(설계 §2.2) 구현됨(마이그레이션 동반·**솔버 루프 구동은 후속**). 마지막 상태 저장소:
- **§2.2 `verified_lemmas`** `db/models/verified_lemma.py` `VerifiedLemma`: `id`(UUID PK)·`problem_id`(느슨참조)·`lemma_key`(Text — 재사용 매칭 키)·`lemma_repr`(JSONB — 검증된 부분 결과)·`statement`(Text nullable — 사람 가독 진술)·`source_node_id`(UUID nullable·**FK 아님**·재사용 자산이라 트리 GC 비강결합)·`created_at`. **`(problem_id, lemma_key)` UNIQUE**(멱등 — 두 가지 독립 발견해도 1행). ★등급 컬럼 없음: 저장소는 *검증된* 보조정리만 담음(`log_lemma`는 verify 통과 후 호출). 저장소 `whs/lemma_store.py`: `log_lemma`(ON CONFLICT DO NOTHING 멱등)·`find_lemma`(정확 매칭 *재사용 조회*)·`get_lemmas`. 탐색이 보조 목표에 닿을 때 `find_lemma`로 이미 검증된 결과를 재사용해 중복 탐색을 가지친다(§2.2 효율 핵심).
- 마이그레이션 **`a2b3c4d5e6f7`**(down_revision `f1a2b3c4d5e6`·단일 head·테이블1+복합 UNIQUE·enum 0·가역 — 테이블 drop만).
- **상태 저장소 완성**: §2.1~§2.4 4종(트리·검증 보조정리·실패 로그·검증 풀이) 전부 영속. **후속(S1 잔여)**: 솔버 루프 골격(아래 슬라이스 4)·키/해시 스킴 표준화·LLM 정책 모델 구동.

**S1 슬라이스 4 — 솔버 루프 골격**(설계 §3 도구 8종·§4 판정·§7) 구현됨(마이그레이션 0·**LLM 정책 모델 구동은 후속·환경 밖**). 결정론 루프 드라이버 `whs/harness.py`:
- **`run_solver(session, *, problem_id, policy, max_tool_calls=32) -> SolverOutcome`**: `SolverPolicy`(도구 선택 두뇌·주입)를 받아 도구를 실행하고 검증기 스택·상태 저장소 4종에 결선한다. **생성 도구(parse_problem·decompose·apply_strategy)의 *내용*은 정책이 공급**(프로덕션=Ollama·테스트=`ScriptedPolicy`)·하네스는 *실행·검증·기록*만.
- **강제 불변식(§3·§4)**: ① verify 없는 finalize 거부(finalize=검증기 스택 실행+커밋이 한 몸) ② **failed 차단**(`final_verdict`=failed면 미적재·검색 계속) ③ unverifiable→`unverified` 격리 적재 ④ **탐색 예산 상한**(`max_tool_calls` 초과→`budget_exhausted` 안전 종료·R-S4) ⑤ dead-end 회피(`apply_strategy`는 적용 전 `is_dead_end` 조회·노드 미생성) ⑥ 검증 보조정리만(`log_lemma`는 직전 verify=verified 전제).
- **도구 결선**: verify→검증기 스택(verify_answer+verify_solution+final_verdict)·retrieve_similar→검증풀이/보조정리 조회·conjecture_check→수치 반례(verify_answer 재사용)·log_lemma/log_deadend·finalize→verify+등급 매핑+`bank_solution`. 액션 10종(8 도구 + log 분리 + end_search)은 `kind` 판별 Pydantic 유니온(`extra=forbid·frozen`).
- 마이그레이션 0(기존 저장소·검증기 재사용). `SolverOutcome`(status: finalized/budget_exhausted/ended + 트레이스).
- **후속(S1 잔여)**: LLM 정책 모델(Ollama·Phaiakes9)·MCTS-lite 탐색·생성 도구 내용 생성·키/해시 스킴 표준화·PRM(S2)·Tier3(S5).

### 용어 정합: "545노드" (편집자 부기)

§5 난이도 사다리의 "545노드 연계 문항"에서 545는 *설계 추정치*다. 구현 커리큘럼 계층은 개념그래프 **403 개념(UC) + 541 선수엣지**이며, "545"는 레포에 실체가 없다(상세는 WH-1 문서 "용어·수치 정합" 절). 시그니처 패턴 55+108은 ROADMAP Phase 1 자산으로 유효하다.
