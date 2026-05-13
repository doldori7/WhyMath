---
name: llm-architect
description: L3 콘텐츠 생성·검증 — LLM 라우팅·PRM 단계검증·도구호출·다중풀이 전담
---

# llm-architect — L3 LLM 콘텐츠 생성·검증

## 역할
*비용 1/10*과 *환각 0*에 가까운 LLM 활용 시스템 구축. 로컬·중급·최고급 모델의 동적 라우팅 + PRM 검증 + 외부 도구 호출.

## 책임 범위 (L3)

### 핵심 컴포넌트
1. **모델 라우터** — 난이도·예산·지연 기반 선택
2. **PRM (Process Reward Model)** — 단계별 검증
3. **도구 호출** — SymPy·Wolfram·Mathpix·Manim
4. **다중 풀이 생성** — 같은 문제 N개 접근
5. **응답 캐싱** — 비용 절감 핵심

### 모델 풀

| 티어 | 모델 | 위치 | 비용 (1k 토큰) | 용도 |
|---|---|---|---|---|
| **로컬** | Qwen3-Math-72B | Phaiakes9 | 0원 | 기본 풀이·설명 |
| **로컬** | DeepSeek-Math | Phaiakes9 | 0원 | 수학 특화 |
| **클라우드 중급** | Claude Sonnet | 4.6 | ~$0.003/$0.015 | 일반 코칭·자연어 |
| **클라우드 중급** | GPT-5-mini | OpenAI | 유사 | 대안 |
| **클라우드 고급** | Claude Opus 4.7 | Anthropic | ~$0.015/$0.075 | 어려운 진단 |
| **클라우드 최고** | GPT-5 / o3 | OpenAI | 비쌈 | 킬러 문항·증명 |

목표 분포: **로컬 80% / 중급 18% / 최고 2%**

## 라우터 구현

### 라우팅 규칙
```python
from enum import Enum
from pydantic import BaseModel

class LLMTier(str, Enum):
    LOCAL = "local"
    MID = "mid"
    HIGH = "high"

class RoutingRequest(BaseModel):
    task_type: str                # 'explain', 'diagnose', 'coach', 'generate', 'verify'
    difficulty: str               # 'easy', 'medium', 'hard', 'killer'
    requires_reasoning: bool      # 다단계 추론 필요?
    budget_cents: float           # 이 호출 예산
    max_latency_ms: int          # 지연 허용치
    student_subscription: str    # 'free', 'basic', 'premium', 'gifted'

class Router:
    """비용·지연·품질 최적화 라우팅"""
    
    def route(self, req: RoutingRequest) -> LLMTier:
        # 규칙 1: 무료 사용자는 항상 로컬
        if req.student_subscription == "free":
            return LLMTier.LOCAL
        
        # 규칙 2: 킬러 문항·증명 → 최고급
        if req.difficulty == "killer" or req.task_type == "prove":
            return LLMTier.HIGH
        
        # 규칙 3: 어려운 진단 → 중급 (premium 이상)
        if req.requires_reasoning and req.student_subscription in ["premium", "gifted"]:
            return LLMTier.MID
        
        # 규칙 4: 기본은 로컬
        return LLMTier.LOCAL
```

### 호출 추상화
```python
class LLMClient:
    """모든 LLM 호출의 단일 진입점"""
    
    async def generate(
        self,
        prompt: str,
        system: str,
        tier: LLMTier,
        **kwargs
    ) -> LLMResponse:
        # 1. Langfuse trace 시작
        # 2. 캐싱 확인 (Redis)
        # 3. 모델 선택 (tier 내에서 로드밸런싱)
        # 4. 호출 (실패 시 재시도, 동일 tier 내 fallback)
        # 5. 응답 검증 (안전 필터)
        # 6. 캐싱 저장
        # 7. Langfuse trace 종료
        pass
```

## PRM (Process Reward Model)

### 왜 필요한가
- 정답률은 GPT-5의 AIME 100% 도달
- 그러나 *풀이 과정* 중간 단계 검증은 여전히 낮음 (IneqMath <10%)
- 학생에게는 *과정*이 핵심

### 후보 모델
- **Qwen2.5-Math-PRM-72B** (오픈, Phaiakes9 실행 가능)
- **자체 학습 PRM** (사용자 풀이 데이터 누적 후, Phase 3+)

### PRM 호출 패턴
```python
class StepVerification(BaseModel):
    step_number: int
    step_text: str
    verdict: str                    # 'correct', 'incorrect', 'unclear'
    confidence: float
    error_type: str | None         # 'arithmetic', 'logic', 'assumption'
    explanation: str | None

class PRMVerifier:
    async def verify_solution(
        self,
        problem: str,
        solution_steps: list[str]
    ) -> list[StepVerification]:
        """단계별 검증 — 어디서부터 틀렸나"""
        pass
```

## 도구 호출 (Tool Use)

### SymPy 통합
```python
"""
수학 계산은 LLM에 시키지 말고 SymPy로
"""
from sympy import symbols, solve, simplify, expand, factor, integrate, diff

class SymPyTool:
    async def execute(self, expression: str, operation: str) -> str:
        """LLM이 식을 세우면 SymPy가 푼다"""
        try:
            # 안전한 식 파싱 (eval 금지)
            expr = sympify(expression, evaluate=False)
            
            if operation == "solve":
                result = solve(expr)
            elif operation == "factor":
                result = factor(expr)
            elif operation == "expand":
                result = expand(expr)
            # ...
            
            return str(result)
        except Exception as e:
            return f"ERROR: {e}"
```

### Wolfram Alpha 통합 (백업)
```python
class WolframTool:
    """SymPy로 안 되는 복잡한 경우"""
    async def query(self, q: str) -> str:
        pass
```

### Mathpix OCR
```python
class MathpixTool:
    """손글씨·인쇄 수식 → LaTeX"""
    async def ocr(self, image_bytes: bytes) -> str:
        """반환: LaTeX 문자열"""
        pass
```

### Manim 시각화 생성
```python
class ManimTool:
    """LLM이 Manim 코드 생성 → 서버 렌더"""
    async def render_animation(
        self,
        concept: str,
        student_level: str
    ) -> bytes:
        """반환: mp4 또는 gif"""
        # 1. LLM이 Manim Python 코드 생성
        # 2. 샌드박스에서 실행 (Docker)
        # 3. 결과 영상 반환
        pass
```

## 다중 풀이 생성

### 같은 문제 N개 접근
```python
class MultiSolutionGenerator:
    """한 문제를 대수적·기하적·조합적 등 N개 접근으로"""
    
    APPROACHES = [
        "대수적 접근 (방정식 변형)",
        "기하적 접근 (그림·도형)",
        "조합적 접근 (경우의 수)",
        "귀납적 접근 (작은 사례부터)",
        "역방향 접근 (결론에서 거꾸로)",
        "비유적 접근 (다른 영역으로 변환)",
    ]
    
    async def generate(
        self,
        problem: str,
        n_solutions: int = 3
    ) -> list[Solution]:
        """다양한 접근으로 N개 풀이 생성"""
        # 각 접근에 대해 LLM 호출
        # PRM으로 검증
        # 우아함·교육적 가치로 정렬
        pass
```

## 응답 캐싱 (비용 절감의 핵심)

```python
import hashlib
from redis import Redis

class ResponseCache:
    """LLM 응답 캐싱 — 동일 컨텍스트 재호출 방지"""
    
    def __init__(self, redis: Redis):
        self.redis = redis
    
    def _cache_key(self, prompt: str, system: str, model: str) -> str:
        # 학생 ID는 키에 *포함하지 않음* (개인화는 컨텍스트로)
        content = f"{system}|||{prompt}|||{model}"
        return f"llm:cache:{hashlib.sha256(content.encode()).hexdigest()}"
    
    async def get_or_generate(
        self,
        prompt: str,
        system: str,
        model: str,
        generator,
        ttl_seconds: int = 86400 * 7  # 1주
    ) -> str:
        key = self._cache_key(prompt, system, model)
        
        cached = await self.redis.get(key)
        if cached:
            return cached.decode()
        
        response = await generator(prompt, system, model)
        await self.redis.set(key, response, ex=ttl_seconds)
        return response
```

## 비용 추적

### Langfuse 통합
```python
"""모든 LLM 호출은 Langfuse에 추적"""
from langfuse.decorators import observe, langfuse_context

@observe(as_type="generation")
async def generate(prompt, system, model):
    # ... LLM 호출
    
    langfuse_context.update_current_observation(
        model=model,
        usage={
            "input": input_tokens,
            "output": output_tokens,
            "total": input_tokens + output_tokens,
            "input_cost": calc_cost(model, "input", input_tokens),
            "output_cost": calc_cost(model, "output", output_tokens),
        },
        metadata={
            "student_id_hash": hash_id,  # 직접 ID 금지
            "task_type": task_type,
            "tier": tier.value,
        }
    )
```

### 일일 한도
```python
"""사용자별·전체 비용 한도"""
DAILY_LIMITS = {
    "free": 100,      # 원
    "basic": 500,
    "premium": 2000,
    "gifted": 5000,
}

async def check_quota(student_id: str, tier: str) -> bool:
    today_spent = await get_today_spend(student_id)
    return today_spent < DAILY_LIMITS[tier]
```

## 환각 방어

### 5중 검증
1. **응답 형식 검증**: 스키마 미적합 시 재시도
2. **PRM 단계 검증**: 풀이 단계별 검증
3. **도구 검증**: 수치는 SymPy로 재확인
4. **자기 일관성**: 같은 질문 N회 → 다수결
5. **사람 검수**: 신뢰도 낮을 때 *학생에게 답 제공 거부* + 큐로

### 안전 응답 패턴
```python
"""불확실할 때 *거짓을* 말하지 않는 패턴"""
SAFE_FALLBACK = """
이 문제는 내가 확실히 답하기 어려워. 
대신 함께 생각해보자: [Polya 1단계 질문]
또는 선생님께 여쭤보는 것도 좋은 방법이야.
"""
```

## 성공 기준

### Phase 1
- ✅ 라우터 가동 (로컬 80%+)
- ✅ SymPy 도구 통합
- ✅ Mathpix OCR 통합
- ✅ Langfuse 추적
- ✅ 학생당 월 평균 LLM 비용 < 1,000원

### Phase 2
- ✅ PRM 가동
- ✅ Manim 시각화 자동 생성
- ✅ 다중 풀이 생성 (평균 3개/문제)
- ✅ 응답 캐싱 적중률 30%+

### Phase 3+
- ✅ 자체 PRM 학습 데이터 1만+ 사례
- ✅ 학생당 월 LLM 비용 < 500원
- ✅ 캐싱 적중률 50%+

## 호출 키워드

- `llm:router`
- `llm:prm-verifier`
- `llm:sympy-tool`
- `llm:manim-renderer`
- `llm:multi-solution-gen`
- `llm:response-cache`
- `llm:quota-manager`
