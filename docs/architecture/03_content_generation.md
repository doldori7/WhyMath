# L3. 콘텐츠 생성·검증 (Content Generation & Verification)

> *비용 1/10*과 *환각 0*에 가까운 LLM 활용.

## 책임

LLM 호출의 *모든 책임*을 단일 계층으로 집약: 라우팅, 호출, 도구 호출, 검증, 캐싱, 비용 추적.

## 핵심 컴포넌트

### 1. 모델 라우터
- 입력: 작업 종류·난이도·예산·구독 티어
- 출력: 사용할 LLM 티어 (LOCAL/MID/HIGH)
- **목표 분포: 로컬 80% / 중급 18% / 최고 2%**

### 2. LLM 클라이언트 (단일 진입점)
- 모든 LLM 호출은 이 클라이언트 경유
- Langfuse 자동 추적
- Redis 캐싱
- 재시도·fallback

### 3. PRM 검증기
- 단계별 정확성 검증
- 후보: Qwen2.5-Math-PRM-72B (로컬)
- 학생 응답 *전에* 검증 통과 필수

### 4. 도구 호출 (Tool Use)

| 도구 | 용도 |
|---|---|
| SymPy | 수식 계산·풀이 (LLM에 계산 시키지 말 것) |
| Wolfram Alpha | SymPy로 안 되는 복잡 케이스 |
| Mathpix OCR | 손글씨 수식 → LaTeX |
| Manim | 시각화 영상 자동 생성 |

### 5. 다중 풀이 생성
같은 문제 → 대수적·기하적·조합적·귀납적 N개 접근

### 6. 응답 캐싱
- Redis 기반
- TTL 1주
- 동일 컨텍스트 재호출 방지

## 모델 풀

| 티어 | 모델 | 위치 | 비용/1k 토큰 |
|---|---|---|---|
| LOCAL | Qwen3-Math-72B | Phaiakes9 | 0원 |
| LOCAL | DeepSeek-Math | Phaiakes9 | 0원 |
| MID | Claude Sonnet 4.6 | API | ~$0.003/$0.015 |
| MID | GPT-5-mini | API | 유사 |
| HIGH | Claude Opus 4.7 | API | ~$0.015/$0.075 |
| HIGH | GPT-5 / o3 | API | 비쌈 |

## 환각 방어 (5중)

1. 응답 형식 검증 (스키마)
2. PRM 단계 검증
3. 도구 검증 (수치는 SymPy)
4. 자기 일관성 (N회 → 다수결)
5. 사람 검수 큐 (신뢰도 낮을 때)

## 인터페이스 (L4·L5 호출)

```python
class L3LLMService:
    async def generate(
        self, prompt: str, system: str,
        request: RoutingRequest,
        context: dict | None = None
    ) -> LLMResponse: ...
    
    async def verify_steps(
        self, problem: str, steps: list[str]
    ) -> list[StepVerification]: ...
    
    async def generate_visualization(
        self, concept: str, level: str
    ) -> bytes: ...  # mp4/gif
    
    async def generate_multi_solutions(
        self, problem: str, n: int = 3
    ) -> list[Solution]: ...
```

## 비용 통제

### 사용자별 일일 한도 (원)
- Free: 100
- Basic: 500
- Premium: 2,000
- Gifted: 5,000

### KPI
- 학생당 월 평균 LLM 비용 (목표: 1,000원 이하 → 500원)
- 로컬 LLM 비율 (목표: 80%+)
- 캐싱 적중률 (목표: 30%+ → 50%+)

## 성공 기준

### Phase 1
- ✅ 라우터 (로컬 80%)
- ✅ SymPy 통합
- ✅ Mathpix OCR
- ✅ Langfuse 추적
- ✅ 학생당 월 LLM 비용 < 1,000원

### Phase 2
- ✅ PRM 가동
- ✅ Manim 자동 생성
- ✅ 다중 풀이
- ✅ 캐싱 30%+

### Phase 3+
- ✅ 자체 PRM 학습
- ✅ 캐싱 50%+
