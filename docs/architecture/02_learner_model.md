# L2. 학습자 모델 (Learner Model)

> *LLM이 못 하는* 일을 한다: 6개월·1년·3년 학습 곡선·개념 의존성·반복 실패 추적.

## 책임

학생의 *시간축에 걸친 상태*를 통계적으로 추적·예측한다. 출력은 L3 LLM의 컨텍스트로 주입.

## 왜 LLM과 분리하나

- LLM은 *현재 발화*만 봄. 토큰 한계로 6개월 이력 주입 불가
- 장기 추적은 *별도 통계 모델*만 가능
- LLM에는 *요약된 상태*만 전달 (BKT 확률, 오개념 벡터, IRT 능력)

## 핵심 모델

> ### 🚨 모델 도입 순서 — BKT 유지 (PRD v1.1 흡수 시 결정)
>
> WhyMath PRD v1.1은 학습자 모델로 **IRT theta + 망각곡선 + 협업필터링**만 채택하고 **BKT를 제외**했다. 그러나 BKT 단계 도입은 *유지*한다.
>
> **근거**:
> - **BKT는 콜드스타트에 필수**: BKT는 *적은 데이터로도* 성취기준별 숙달을 추적할 수 있다. 성취기준당 4개 파라미터만 추정하면 되고, 학생 1명의 풀이 몇 건으로도 베이지안 업데이트가 동작한다.
> - **IRT는 데이터 다량 필요**: 문항 모수(난이도·변별도) 추정에는 다수 학생의 응답 행렬이 필요하다. Phase 1 β 100명 단계에서는 문항당 응답 수가 부족해 모수가 불안정하다.
> - **협업필터링은 사용자 적으면 무력**: 유사 학습자 기반 추천은 임계 사용자 수 미만에서 신호가 약하다.
>
> **따라서**: WhyMath는 **BKT (Phase 1) → IRT (Phase 2) → DKT (Phase 3+)** 의 단계 도입을 유지하고, PRD의 *IRT theta·망각곡선·협업필터링*은 그 위에 **보강**한다 (대체가 아님). 각 단계는 이전 단계를 폐기하지 않고 *공존*한다 — Phase 2 이후에도 신규 성취기준·신규 학생의 콜드스타트는 BKT가 담당한다.

### 1. BKT (Bayesian Knowledge Tracing) — Phase 1
- 성취기준당 1개 4-파라미터 모델
- (P(L0), P(T), P(S), P(G))
- 학생 풀이 결과로 베이지안 업데이트
- 도구: `pyBKT` 또는 자체 구현
- **역할**: 콜드스타트 숙달 추적의 *기본 엔진*. Phase 2 이후에도 폐기되지 않고, IRT theta로 보강되는 토대로 남는다.

### 2. DKT (Deep Knowledge Tracing) — Phase 3+
- RNN/Transformer 기반
- BKT의 *독립성 가정* 완화 (개념 간 연결)
- 도입 조건: 사용자 N>10,000

### 3. IRT (Item Response Theory)
- **1PL (Rasch)** — Phase 1: 난이도 단순 추정
- **2PL** — Phase 2: 변별도 추가
- **3PL** — Phase 3+: 추측 모수 추가
- 어댑티브 출제 (Fisher Information)
- **개념별 theta + 신뢰구간** (PRD `MasteryState` 흡수): 학생 능력을 단일 스칼라가 아니라 *개념 노드별 theta 추정값 + 신뢰구간(confidence interval)* 으로 보유. 신뢰구간은 "이 학생이 이 개념에서 어느 정도 능력인지를 *얼마나 확신*하는가"를 나타내며, 어댑티브 출제·개입 판단의 핵심 입력이다. 데이터가 적으면 구간이 넓고(불확실), 누적될수록 좁아진다.

### 3-보강. 망각곡선 (Forgetting Curve) — Phase 2 (PRD v1.1 흡수)
- BKT/IRT가 추정한 숙달도는 *시간이 지나면 감쇠*한다. 마지막 풀이 이후 경과 시간에 따라 숙달 확률을 하향 보정.
- **망각곡선 강도(forgetting strength)**: 개념별·학생별로 다른 감쇠율 파라미터. 자주 복습한 개념은 강도가 낮고(천천히 잊음), 벼락치기로 익힌 개념은 강도가 높다.
- BKT 숙달 확률에 시간 감쇠항을 곱하는 방식으로 *보강* — BKT 자체를 대체하지 않는다.
- 복습 타이밍 추천(간격 반복, spaced repetition)의 근거 신호로 L4 교수학 엔진에 전달.

### 3-보강. 협업필터링 (Collaborative Filtering) — Phase 3+ (PRD v1.1 흡수)
- 유사 학습 궤적을 가진 학생군에서 *다음에 어려워할 개념·효과적이었던 학습 경로*를 추론.
- **도입 조건**: 사용자 N이 충분히 누적되어 유사 학습자 군집이 통계적으로 의미를 가질 때 (DKT 도입 시점과 유사).
- BKT/IRT의 *개인 내 추정*을 보완하는 *개인 간 추정* — 콜드스타트 학생에게 유사군의 사전 분포를 제공하는 용도로도 활용 가능.

### 4. 정서 신호 모델
입력 시그널:
- 세션 지속 시간
- 연속 오답
- 응답 시간 z-score (평소 대비)
- Rage quit (갑자기 닫기)
- 답 요구 빈도
- 재시도 횟수
- 스킵률

출력 분류:
- FLOW (몰입, 이상적)
- FRUSTRATED (좌절, 개입 필요)
- BORED (지루, 난이도↑)
- OVERWHELMED (과부하, 난이도↓)
- AT_RISK (이탈 위험, 긴급)

### 5. 오개념 매핑
풀이 패턴 → 오개념 카탈로그 매칭 (L1 misconceptions 테이블)

## PRD v1.1 엔티티 통합

### MasteryState — 개념별 숙달 상태 (L2 보유)

PRD v1.1의 `MasteryState`를 L2의 *개념 노드별 숙달 레코드*로 흡수한다. WhyMath의 기존 `LearnerState.mastery`(성취기준별 BKT 확률)를 *확장*하는 구조 — 성취기준 코드뿐 아니라 L1 개념 그래프의 개념 노드에도 숙달 상태를 부착한다.

```python
class MasteryState(BaseModel):
    """학생 1명 × 개념 노드 1개의 숙달 상태"""
    student_id: str
    concept_node_id: str          # L1 개념 그래프 노드 (성취기준 코드와 매핑됨)
    timestamp: datetime

    # BKT (Phase 1) — 콜드스타트 기본 엔진
    bkt_mastery: float            # 베이지안 숙달 확률 0~1

    # IRT (Phase 2 보강) — 데이터 누적 후
    irt_theta: float | None       # 개념별 능력 추정값 -3~+3
    irt_ci_lower: float | None    # 신뢰구간 하한
    irt_ci_upper: float | None    # 신뢰구간 상한

    # 망각곡선 (Phase 2 보강)
    forgetting_strength: float    # 개념별 감쇠율 파라미터
    last_practiced_at: datetime   # 마지막 풀이 시각 (감쇠 계산 기준)
    decayed_mastery: float        # 시간 감쇠 반영 후 숙달도

    # 선호 풀이 스타일
    preferred_solution_style: str | None  # L3 SolutionPath 유형 중 학생이 잘 푸는 접근
```

- **`bkt_mastery`는 Phase 1부터 항상 채워진다.** `irt_*` 필드는 Phase 2 데이터 누적 후 채워지며, 그 전에는 `None`.
- **선호 풀이 스타일**: 학생이 같은 문제를 *어떤 접근(대수적·기하적 등)으로 풀 때 정답률·체류시간이 좋은지* 누적 추적. 값은 L3 `SolutionPath.approach_type`(WhyMath 6가지 `solution_approaches` 중 하나, 03 문서 참조)을 그대로 취한다. L4 교수학 엔진이 힌트·다중 풀이 제시 순서를 정할 때 입력으로 사용 — L2가 추적한 선호 유형의 `SolutionPath`를 L4가 우선 노출한다.

### StudentProfile — 학생 프로필 (⚠️ L1 보유, L2는 *읽기*)

PRD v1.1의 `StudentProfile`은 *자동 커리큘럼 정렬*의 입력이며, **L1 데이터 기반이 보유**한다. L2는 이를 *소유하지 않고*, L1에서 **읽어서 학습자 상태 갱신에 활용**한다. 7계층 경계상 L2는 L1을 *호출*할 수 있으나 L1의 데이터를 *구현·소유*하지 않는다.

`StudentProfile`이 담는 것 (L1 소유):
- **기본 위치**: 국가·학년·교육과정 (예: 한국·고1·2022 개정)
- **학교 정보**: 학교알리미 연동 학교 식별자
- **활성 교과서**: 현재 학교에서 쓰는 검정교과서 (12단계 교과서 매핑 파이프라인의 출력과 연결)
- **그림자 커리큘럼(shadow curriculum)**: 학원·인강 진도 — 학교 진도와 별개로 학생이 실제로 어디까지 배웠는지
- **목표**: 내신 목표 등급, 수능 목표 등 (고1 내신 첫 진입과 직결)
- **학습 선호**: 선호 시간대·세션 길이·시각화 선호 등

**L1 → L2 관계 (경계 명시)**:
- L2는 L1의 `StudentProfile`을 **읽어** 다음을 수행한다:
  - 활성 교과서·그림자 커리큘럼을 보고 *어떤 성취기준·개념 노드의 숙달도를 추적해야 하는지* 범위 결정
  - 학년·교육과정으로 BKT 사전 분포 `P(L0)` 초기값 보정 (예: 고1이 중3 성취기준을 다룰 때 사전지식 확률 상향)
  - 목표(내신 등급 등)를 L4에 전달할 `LearnerState`에 함께 실어 보냄
- L2는 `StudentProfile`을 **수정하지 않는다.** 위치·학교·교과서 변경은 L1의 책임.
- L2가 생산하는 것은 어디까지나 *학습자의 동적 상태*(`MasteryState`·`LearnerState`)이지, *학생의 정적 프로필*이 아니다.

## 출력 — LearnerState

`LearnerState`는 L2가 L3 LLM·L4 교수학 엔진에 주입하는 *요약 상태*다. PRD v1.1 엔티티 통합 후, 개념별 `MasteryState`를 집계하고 L1 `StudentProfile`에서 읽은 정적 정보를 함께 실어 전달한다.

```python
class LearnerState(BaseModel):
    student_id: str
    timestamp: datetime
    
    # --- 동적 학습 상태 (L2 생산) ---
    mastery: dict[str, float]          # {"[9수01-01]": 0.85} — BKT 숙달 확률 (콜드스타트 기본)
    mastery_states: dict[str, MasteryState]  # 개념 노드별 상세 (BKT·IRT theta·CI·망각곡선)
    general_ability: float              # IRT theta, -3~+3
    domain_abilities: dict[str, float]  # {"수와 연산": 0.8}
    active_misconceptions: list[str]
    affect: AffectState
    recent_struggles: list[str]
    recent_successes: list[str]
    
    # --- L1 StudentProfile에서 읽어온 정적 정보 (L2는 읽기만) ---
    grade: str                          # 학년 (BKT 사전 분포 보정·L4 컨텍스트용)
    curriculum: str                     # 교육과정 (예: "2022 개정")
    active_textbook_id: str | None      # 활성 검정교과서
    shadow_curriculum_progress: dict[str, str] | None  # 학원·인강 진도
    goals: dict[str, str]               # 목표 (내신 등급 등)
```

- `mastery`는 LLM 프롬프트에 바로 쓰기 좋은 *얇은 요약*, `mastery_states`는 어댑티브 출제·복습 추천에 쓰는 *두꺼운 상세*. 둘 다 BKT를 토대로 한다.
- `grade`·`curriculum`·`active_textbook_id`·`shadow_curriculum_progress`·`goals`는 **L1 `StudentProfile`의 사본**이다. L2는 이를 *전달*할 뿐 *소유·수정*하지 않는다 (7계층 경계).

> **v0 축소 개정 (편집자 부기, 2026-07-29 — `ai_tutor_module_gap_review.md §3 D3`)**: 위 스키마는
> 이 클래스가 **아직 코드에 실체화되지 않은 상태**에서의 목표 전체 명세다. 실체화 착수
> (`PED-05-learner-state-assembly`)는 **생산자가 실재하는 필드만**으로 v0을 좁혀 만든다 —
> `mastery`·`general_ability`·`domain_abilities`·`active_misconceptions`·`recent_struggles`·
> `recent_successes`·`grade`·`curriculum`·`goals` 9개는 v0에 포함, 다음 4개는 **v0에서 제외**한다:
> - `affect: AffectState` — 정서 신호 생산자가 없다(`l4/pedagogy/runtime_selector.py:96-112`가
>   이미 "집중도·학습시간·선호 신호는 생산자가 없어 필드로 만들지 않는다"고 명시한 것과 같은
>   결정의 연장). 발화 조건: `ai_tutor_module_gap_review.md §3 D4`(행동 텔레메트리 생산자)가
>   먼저 착지하고 §5-③ 조건이 충족될 때.
> - `mastery_states: dict[str, MasteryState]` — `MasteryState` 자체가 미실체화 스케치다(같은
>   `runtime_selector.py`가 자인). 발화 조건: 어댑티브 출제 또는 선호 풀이 스타일 추적이
>   실소비처로 설 때(`solution_module_gap_review.md §4-⑤` 승계).
> - `active_textbook_id` — L1 좌석은 실재하나(`textbook_mapping`/`textbook_unit`) 학생 프로필과의
>   FK·L4 소비처가 0이다.
> - `shadow_curriculum_progress` — `user_profile.uses_inkang` 불리언만 있고 진도 자체가 없다.
>
> "항상 None인 필드를 두면 읽고 있다는 착시를 주지만 실제 판단에는 기여하지 못한다"(같은
> `runtime_selector.py` 결정)는 원칙을 이 계약에도 동형 적용한다. 제외 필드는 **v0 클래스의
> docstring에 사유와 함께 명시**하고, 두꺼운 목표 스키마(위 코드 블록)는 장기 지향점으로 보존한다.

## 인터페이스 (L4·L5 호출)

```python
class L2LearnerService:
    async def get_state(self, student_id: str) -> LearnerState: ...
    async def update(
        self, student_id: str,
        standard_code: str, correct: bool,
        solution_steps: list[str] | None
    ) -> LearnerState: ...
    async def detect_plateau(self, student_id: str) -> bool: ...
    async def detect_regression(self, student_id: str) -> bool: ...
    async def select_next_item(
        self, student_id: str,
        candidate_pool: list[str]
    ) -> str: ...  # 어댑티브 출제
```

## 시계열 저장 (TimescaleDB)

```sql
CREATE TABLE mastery_history (
    student_id VARCHAR(50),
    standard_code VARCHAR(20),
    timestamp TIMESTAMPTZ,
    mastery_probability DOUBLE PRECISION,
    n_attempts INTEGER,
    PRIMARY KEY (student_id, standard_code, timestamp)
);
SELECT create_hypertable('mastery_history', 'timestamp');
```

## 성공 기준

### Phase 1
- ✅ BKT 가동
- ✅ 풀이 → 숙달도 업데이트
- ✅ 오개념 카탈로그 30개 매칭

### Phase 2
- ✅ IRT 도입
- ✅ 정서 분류기
- ✅ 학습 곡선 시각화

### Phase 3+
- ✅ DKT 도입
- ✅ 정서 → 자동 개입
