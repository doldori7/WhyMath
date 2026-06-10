# 오개념 진단·개입 프롬프트

> 직접 교정 ❌. 반례·구체 사례로 *자각 유도* ✅.

## 표준 패턴

```
[패턴 1: 반례 유도]
프롬프트: "{학생 가정}이 항상 맞다고 했지. 잠깐, {반례 케이스}일 때는 어떻게 돼?"

예시:
- 오개념: (a+b)² = a²+b²
- 반례: a=1, b=1
- 프롬프트: "(a+b)² = a²+b² 이라고 했지. 잠깐, a=1, b=1로 계산해볼래? 양쪽 값이 같아?"

[패턴 2: 구체 사례]
프롬프트: "{추상 진술}을 *구체적인 수*로 확인해볼래?"

[패턴 3: 시각화 유도]
프롬프트: "이걸 *그림으로* 그려볼 수 있을까?"

[패턴 4: 거꾸로 사고]
프롬프트: "이 결과가 맞다면, *원래 조건*에 어떻게 부합하는지 거꾸로 확인할 수 있을까?"
```

## 오개념 카탈로그 (Phase 1 30개)

### 대수 영역
1. **distribution-over-power**: (a+b)² = a² + b²
2. **sign-flip-in-inequality**: 음수 곱셈 후 부호 안 바꿈
3. **division-by-zero**: 분모 0 가능성 놓침
4. **square-root-positivity**: √x² = x (음수 무시)
5. **exponent-zero**: a⁰ = 0
6. **fraction-cancellation**: (a+b)/a = b
7. **log-distribution**: log(a+b) = log a + log b
...

### 기하 영역
8. **angle-sum-non-triangle**: 비삼각형 도형 각 합 혼동
9. **similarity-vs-congruence**: 닮음과 합동 혼동
10. **area-perimeter-confusion**: 둘레 늘면 넓이 늘 거라 가정
...

### 확률·통계
11. **gambler-fallacy**: 동전 H 5번 후 T 더 자주 나올 거
12. **prosecutor-fallacy**: P(A|B) = P(B|A)
13. **mean-vs-median**: 평균과 중앙값 혼동
...

### 함수
14. **invertibility-without-1-1**: 함수가 항상 역함수 가짐 가정
15. **continuity-vs-differentiability**
...

### 미적분 영역
16. **chain-rule-inner-derivative-omitted**: d/dx[sin(2x)] = cos(2x) (내부 도함수 ×2 누락)
17. **product-rule-naive**: (f·g)′ = f′·g′ (곱의 미분을 각각 미분의 곱으로)
18. **limit-equals-function-value**: lim_{x→a} f(x) = f(a) (불연속점 무시)
...

### 수열 영역
19. **geometric-series-always-converges**: 무한등비급수는 항상 수렴 (|공비|≥1 발산 무시)
20. **term-to-zero-implies-convergence**: 일반항→0이면 급수 수렴 (조화급수 반례)
...

### 삼각함수 영역
21. **sine-distributes-over-sum**: sin(a+b) = sin a + sin b
22. **period-of-scaled-sine**: y=sin(2x)의 주기는 2π (계수에 따른 주기 변화 무시)
...

### 벡터 영역
23. **dot-product-is-vector**: 두 벡터의 내적은 벡터 (내적은 스칼라)
...

## 매칭 알고리즘

```python
async def diagnose(student_solution, correct_solution, standard_code):
    """
    1. 풀이 단계별 파싱
    2. 처음 틀린 단계 식별 (PRM)
    3. 그 단계의 *패턴* 추출
    4. 오개념 카탈로그와 임베딩 유사도 매칭
    5. top-3 후보 반환
    """
    pass
```

### v1.1 구현(현재) — 규칙 기반 substring + 표기 정규화

위 의사코드는 *목표 설계*(PRM 단계파싱·임베딩 매칭)다. 현재 구현은 그 부분집합으로,
각 카탈로그 항목의 `signals`(공출현 substring, AND)를 학생 풀이에서 찾아 `confidence =
매칭수/전체신호`로 top-K를 낸다.

- **표기 정규화**(슬 101): 매칭 직전 양변을 NFKC+공백제거로 정규화한다. 학생은 `a²+b²`·
  `a² + b²`·`a^2+b^2`를 섞어 쓰므로 정규화로 *거짓음성*을 줄인다. `matched_signals`는 원본
  신호를 유지(표시·텔레메트리 불변).
- **`signals` 작성 원칙**: 토큰은 *오류의 결론*을 포착하되 **정답 진술과 구분**되어야 한다.
  바른 공통어(`"모든"`·`"다음"`·단독 `"0"`)는 정답 풀이에도 흔해 *거짓양성*을 낳으므로,
  가능하면 더 특정한 구(예: `"모든 함수"`)로 좁힌다.
- **substring의 구조적 한계**: substring은 *오류의 부재*를 탐지하지 못한다(예: "분모≠0"을
  *바르게* 확인한 풀이도 `("분모","0")`에 매칭). 이 한계의 정본 해법은 위 4단계의
  **임베딩/LLM-judged 매칭**이다(후속). 신호의 교수학적 재설계는 pedagogy-designer 검토를
  거친다(추측 수정 금지). 교육과정 정착 오개념과의 교차검증: `docs/data/concept_graph_dataset_v1.md` §5.

## 개입 결정 트리

```
오개념 감지 →
   ├─ 신뢰도 > 0.8 → 패턴 1 (반례)
   ├─ 신뢰도 0.5-0.8 → 패턴 4 (거꾸로 사고)
   └─ 신뢰도 < 0.5 → 진단 보류, 추가 학생 발화 대기
```

## 절대 금지

❌ "이건 잘못된 거야" (직접 교정)
❌ "이건 흔한 오개념이야" (학생 라벨링)
❌ "다시 풀어와" (학습 기회 박탈)
✅ "잠깐 같이 봐볼까. {반례} 일 때는?" (자각 유도)
