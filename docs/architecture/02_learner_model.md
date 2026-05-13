# L2. 학습자 모델 (Learner Model)

> *LLM이 못 하는* 일을 한다: 6개월·1년·3년 학습 곡선·개념 의존성·반복 실패 추적.

## 책임

학생의 *시간축에 걸친 상태*를 통계적으로 추적·예측한다. 출력은 L3 LLM의 컨텍스트로 주입.

## 왜 LLM과 분리하나

- LLM은 *현재 발화*만 봄. 토큰 한계로 6개월 이력 주입 불가
- 장기 추적은 *별도 통계 모델*만 가능
- LLM에는 *요약된 상태*만 전달 (BKT 확률, 오개념 벡터, IRT 능력)

## 핵심 모델

### 1. BKT (Bayesian Knowledge Tracing) — Phase 1
- 성취기준당 1개 4-파라미터 모델
- (P(L0), P(T), P(S), P(G))
- 학생 풀이 결과로 베이지안 업데이트
- 도구: `pyBKT` 또는 자체 구현

### 2. DKT (Deep Knowledge Tracing) — Phase 3+
- RNN/Transformer 기반
- BKT의 *독립성 가정* 완화 (개념 간 연결)
- 도입 조건: 사용자 N>10,000

### 3. IRT (Item Response Theory)
- **1PL (Rasch)** — Phase 1: 난이도 단순 추정
- **2PL** — Phase 2: 변별도 추가
- **3PL** — Phase 3+: 추측 모수 추가
- 어댑티브 출제 (Fisher Information)

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

## 출력 — LearnerState

```python
class LearnerState(BaseModel):
    student_id: str
    timestamp: datetime
    
    mastery: dict[str, float]          # {"[9수01-01]": 0.85}
    general_ability: float              # IRT theta, -3~+3
    domain_abilities: dict[str, float]  # {"수와 연산": 0.8}
    active_misconceptions: list[str]
    affect: AffectState
    recent_struggles: list[str]
    recent_successes: list[str]
```

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
