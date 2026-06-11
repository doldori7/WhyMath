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
24. **discriminant-negative-no-real-root**: 판별식 D<0이면 "해가 없다" (실근은 없으나 복소근 2개 — 불능으로 단정, [HK07])
25. **root-loss-by-dividing**: ax²=bx의 양변을 x로 나눠 x=0 근 손실 (x(ax−b)=0로 인수분해해야, [J0220])
...

### 기하 영역
8. **angle-sum-non-triangle**: 비삼각형 도형 각 합 혼동
9. **similarity-vs-congruence**: 닮음과 합동 혼동
10. **area-perimeter-confusion**: 둘레 늘면 넓이 늘 거라 가정
26. **circle-radius-squared**: x²+y²=r²의 반지름을 r²로 착각 (반지름은 r, [HK22])
...

### 확률·통계
11. **gambler-fallacy**: 동전 H 5번 후 T 더 자주 나올 거
12. **prosecutor-fallacy**: P(A|B) = P(B|A)
13. **mean-vs-median**: 평균과 중앙값 혼동
27. **mutually-exclusive-implies-independent**: 배반사건이면 독립이라 가정 (P>0인 배반은 오히려 종속, [H:12확통02-05])
...

### 함수
14. **invertibility-without-1-1**: 함수가 항상 역함수 가짐 가정
15. **continuity-implies-differentiability**: 연속이면 미분가능하다고 가정 (역은 거짓 — f(x)=|x|는 0에서 연속·미분불가, [H:12미적Ⅰ02-02]). *주의*: ① 본래 stub 명 `continuity-vs-differentiability`를 함의 방향을 명시한 케밥 id로 상세화·확정. ② 도식상 번호는 함수 슬롯(#15)에 두되 *카탈로그 domain은 미적분*(`[H:12미적Ⅰ02-02]` 정착) — 아래 미적분 영역에서 재참조.
28. **composite-function-commutes**: 합성함수 f∘g = g∘f라 가정 (합성은 일반적으로 비가환, [HK35])
29. **translation-sign-flip**: y=f(x−a)를 왼쪽으로 평행이동이라 가정 (x−a는 +a만큼 오른쪽 이동, [HK24])
...

### 미적분 영역
16. **chain-rule-inner-derivative-omitted**: d/dx[sin(2x)] = cos(2x) (내부 도함수 ×2 누락)
17. **product-rule-naive**: (f·g)′ = f′·g′ (곱의 미분을 각각 미분의 곱으로)
18. **limit-equals-function-value**: lim_{x→a} f(x) = f(a) (불연속점 무시)
15. **continuity-implies-differentiability** (domain=미적분 — 위 함수 슬롯 #15에서 상세, 여기 재참조): 연속이면 미분가능 가정, f(x)=|x| 반례 [H:12미적Ⅰ02-02]
30. **critical-point-implies-extremum**: f′(a)=0이면 극값이라 단정 (f′=0은 극값의 필요조건일 뿐 — f(x)=x³은 f′(0)=0이나 변곡점, [H:12미적Ⅰ02-07])
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

### v1.2 구현(현재) — 정규식 보조 탐지(거짓 항등식의 수치 대입)

v1.1 substring(AND)은 *기호식*(`(a+b)²=a²+b²`)은 잡지만, 학생이 그 거짓 항등식에 **구체 수를
대입해 계산해버린 흔적**(`(3+4)²=3²+4²`)은 못 잡았다(§5.3 한계). v1.2는 카탈로그 항목에 선택
필드 `regex_signals`(OR)를 추가해 이 *수치 대입*을 보조 탐지한다.

- **검사 대상·방식**: 정규식은 substring과 *동일한 정규화 텍스트*(`_normalize`: NFKC+공백제거,
  위첨자 `²`→`2`)에 `re.search`로 검사한다. 따라서 정규식 패턴은 *지수를 평문으로* 쓴 정규형을
  겨냥한다(예: `(3+4)²=3²+4²`의 정규형은 `(3+4)2=32+42`).
- **confidence 의미 보존(중요)**: 분모는 **substring `signals` 개수로 유지**하고, 정규식 매치는
  분자에 *가산*하되 상한 1.0으로 캡한다:
  `confidence = min(1.0, (substr매치 + regex매치) / len(signals))`.
  그래서 substring만으로의 기존 confidence(1.0/0.5)는 **불변**이고, 정규식은 substring이 0이어도
  *추가로* 후보를 띄우는 **보조 경로**가 된다(예: 수치 대입만 있으면 0/2 → 1/2 = 0.5로 탐지).
  매치된 정규식은 `MisconceptionMatch.matched_regex_signals`에 *분리* 저장 → 기존 소비자의
  `matched_signals` 단언은 깨지지 않는다.
- **작성 원칙(disjoint·보수적)**: 수치 정규식은 *반드시* 기호 substring 케이스와 **겹치지 않게**
  쓴다. ① 피연산자를 `\d+`로 한정해 기호(`a`·`b`·`x`)에는 절대 매치되지 않게 하고, ② **명명그룹
  역참조**(`(?P<x>\d+)…(?P=x)`)로 좌·우변 항이 *글자 그대로 일치*할 때만 매치시켜 **올바른 계산**
  (`(3+4)²=49`·`√((-3)²)=3`)도 걸러낸다. 역참조 뒤에 리터럴 숫자(`2`)가 오면 `\1`은 group 12로
  오인되므로 `\N`이 아닌 **명명 역참조**를 쓴다. 정규식은 canonical_statement·교차검증(§5)에
  근거해 *과도하지 않게* — 추측 패턴 금지(pedagogy-designer 검토 대상).
- **시연 항목(3종)**: 수치화가 명확한 대수 3종에 적용.

  | id | canonical | 수치 정규식이 잡는 흔적 | 정규형(NFKC) 패턴 |
  |---|---|---|---|
  | `distribution-over-power` | (a+b)²=a²+b² | `(3+4)²=3²+4²` | `\((?P<x>\d+)\+(?P<y>\d+)\)2=(?P=x)2\+(?P=y)2` |
  | `square-root-positivity` | √(x²)=x | `√((-3)²)=-3` | `√\(\(-(?P<a>\d+)\)2\)=-(?P=a)` |
  | `fraction-cancellation` | (a+b)/a=b | `(2+4)/2=4` | `\((?P<p>\d+)\+(?P<q>\d+)\)/(?P=p)=(?P=q)` |

  나머지 항목(부등식·로그·삼각 등)의 수치 정규식은 *후속* — 표기 변이가 더 다양해
  보수적 작성·교차검증이 필요(추측 작성 금지). `regex_signals` 미설정 항목은 동작 불변.

### v1.3 구현(현재) — 짧은 영숫자 signal의 경계 매칭 (슬 109·라이브 FP 교정)

전문가 리뷰가 **라이브 결함을 실증**했다: `"분모가 10인 분수를 약분했어요"`(완전히 올바른
진술)가 `'0' ∈ '10'` 부분문자열 매칭으로 division-by-zero **풀매칭(confidence 1.0) →
COUNTEREXAMPLE 개입 발화**. v1.1의 "signals 작성 원칙"(단독 `"0"` 회피 권고)이 카탈로그에
강제되지 않았고, 단일 ASCII 문자 signal(`"b"`)도 같은 부류였다(`'b' ∈ 'ab'`).

- **경계 매칭 규칙**: *숫자-only* signal(`"0"`·`"180"`)과 *단일 ASCII 문자* signal(`"b"`)은
  정규화 텍스트에서 영숫자·소수점 경계 정규식 `(?<![0-9A-Za-z.])sig(?![0-9A-Za-z.])`으로
  매칭한다 — `10`·`0.5`·`1.0`·`a₀`(NFKC→`a0`)·`ab` 내부 오매칭 차단. 정당한 사용처(한글
  조사·`=`·`≠`·괄호·쉼표 이웃)는 비영숫자라 계속 매칭된다(거짓음성 추가 없음).
- **내용성 signal은 substring 유지**: 한글 형태소(`"곱"`)·연산자 기호(`"√"`)·복합 토큰은
  자체 의미가 있어 기존 동작 그대로다. confidence 식·분모·동률 정렬·반환 계약 전부 불변.
- **카탈로그 래칫 가드**(테스트): 경계 매칭 대상(숫자-only·단일 ASCII) signal 집합을
  스냅숏으로 잠가, 새 위험 signal 추가 시 의식적 리뷰를 강제한다.
- **잔여 한계(정직)**: 부분매칭(예: `'분모'` 단독 0.5 → REVERSE_REASONING)의 정밀도는
  substring 설계의 알려진 트레이드오프로 남는다 — 그 자리는 의미 매칭·judge 계층(슬104~108,
  게이트 off·측정 대기)이다. v1.3은 *어휘 차원* 거짓양성(풀매칭 오발화)을 직접 제거한다.

### 의미(임베딩) 매칭 층 (slice 104) — substring 거짓음성 보완

substring(AND)+정규식은 *표면 문자열*을 본다. 학생이 카탈로그 표현과 **다른 어휘로 같은
오개념을 패러프레이즈**하면(예: "분모에 변수가 와도 늘 계산된다"처럼 `"0"` 토큰을 안 쓰고
0 나눗셈 오개념을 적음) substring은 *거짓음성*(놓침)이 난다. slice 104는 이 한계를
**임베딩 코사인 유사도**로 보완하는 *의미 매칭 층*을 `diagnose()`와 **독립된 추가 API**
(`semantic_matches`)로 둔다 — `diagnose()`의 시그니처·동작은 **불변**(기본 비활성).

- **좌석 구조(7계층 준수)**: L4 매처(`SemanticMatcher`)가 *하위 인프라 좌석*을 호출한다
  (L_n→L_{n-1}). L4는 임베딩 구현을 모르고 Protocol만 본다.
  - `EmbeddingProvider`(좌석) — `FakeEmbeddingProvider`(테스트·CI hermetic·결정론 해시)·
    `LocalEmbeddingProvider`(sentence-transformers **bge-m3**·로컬 우선·지연 로드)·
    `OpenAIEmbeddingProvider`(text-embedding-3-large·키 필요·지연). 기본 `local`(CLAUDE.md
    비용·Phaiakes9). 라이브 모델 로드는 *지연 import*라 CI는 모델 다운로드·네트워크 0.
  - `VectorIndex`(좌석) + `InMemoryVectorIndex`(코사인 선형 스캔) — 카탈로그 30종엔
    인메모리가 정답(기본). **pgvector 영속 백엔드(`PgVectorIndex`)는 슬105에서 구현**(슬98
    벡터 DB=pgvector 결정의 첫 실 결선): `misconception_embedding` 테이블(`vector(1024)`)에
    표현 임베딩을 upsert(`populate_pgvector`)하고 코사인 거리(`<=>`)로 검색한다. `config.
    vector_store`(기본 `memory`)가 in-memory/pgvector를 가르고 **기본 동작은 무변경**(pgvector는
    opt-in). 슬104 `VectorIndex` Protocol이 *동기*라 PgVectorIndex(sync psycopg 격리 엔진)가
    그대로 드롭인(매처 리팩터 0). **정직 스코프(과장 금지)**: 30종엔 in-memory가 최적이고
    pgvector는 *영속화(재기동·다중 워커 공유) + 스케일 코퍼스 groundwork*다 — 30종에서
    더 빠르지 않다. **HNSW/IVFFlat 인덱스는 두지 않는다**(30종 seq-scan 최적); 스케일 코퍼스
    (개념그래프 401+·문제은행·학생 풀이)가 *fixed-dim + HNSW cosine 인덱스*의 자리다(후속·
    같은 좌석에 인덱스·차원만 추가). 슬98 `embedding_id`(concept/user 참조 필드)는 이 테이블과
    별개다(실 벡터 컬럼은 `misconception_embedding`가 소유). 실 pgvector add/search·recall은
    통합 게이트(`WHYMATH_RUN_INTEGRATION`·CI pgvector PG)로 검증한다.
- **매칭 절차**: 카탈로그 각 항목의 *표현* `f"{name_kr}. {canonical_statement}"`(틀린 믿음의
  자연어)을 1회 사전 임베딩해 인덱스에 적재(캐시)하고, 학생 텍스트를 임베딩해 코사인 상위
  후보 중 **임계값 이상**만 반환한다.
- **confidence 매핑·임계값**: `confidence = min(1.0, max(0.0, cosine))`(코사인 [0,1] 클램프 —
  음수·직교는 0, 부동소수 평행 초과는 1.0 상한). 원 코사인은 `MisconceptionMatch.
  semantic_similarity`(선택 필드·substring 경로는 None)에 클램프 없이 보존. 임계값 기본
  **0.55**(보수적·`config.misconception_semantic_threshold`) — 미만은 미매칭(짧은 공통
  토큰의 의미 근접 오탐 억제). `(cos+1)/2` 대신 클램프를 택한 이유: 임계값과 confidence가
  *같은 축*이고 무관 텍스트가 0.5로 부풀지 않음(보수).
- **정직 스코프(O recall / X 방향·부정·등치) — 과장 금지(CLAUDE.md "확실하지 않을 때 자신
  있게 말함 금지")**:
  - **O (이 슬라이스의 가치)**: *패러프레이즈·동의어 recall* 개선. 어휘가 달라도 의미가
    같으면 잡는다.
  - **X (범위 밖·해결한다고 주장 금지)**: *방향·부정·등치*. "연속⇒미분"(오개념)과 올바른
    역방향 "미분⇒연속"은 **두 문장이 의미상 가까워 임베딩만으로 못 가린다**(substring과
    동일한 *방향맹*). "f∘g≠g∘f"(올바른 비가환)도 카탈로그 "f∘g=g∘f"와 가깝다 → 의미 매처는
    *올바른 진술도 오개념 후보로 올릴 수 있다*(false positive). 이건 버그가 아니라 **한계**.
  - **방향 판별의 정본 해법은 LLM-judged/NLI = 후속 슬라이스**(여기서 해결하지 않음). 의미
    매처는 *후보를 넓히는* 보완재일 뿐, 개입 발화는 여전히 비난 없는 소크라테스형(직접
    교정·라벨링 금지)이어야 false positive의 해가 작다.
  - 이 한계는 단위테스트(`test_misconception_semantic.py` `TestDirectionBlindnessHonesty`)에
    *방향맹 정직 테스트*로 결정론적으로 못 박혀 있다(어휘 집합이 같으면 방향/부정 쌍이 동일
    유사도 → 구분 불가).

### 결합 랭킹 + coach 게이트 배선 (slice 106) — substring + 의미를 한 후보 리스트로

slice 104/105가 의미 매처를 *독립 추가 API*로 뒀고, slice 106은 그 둘을 substring `diagnose()`와
*결합*해 coach API(`/v1/coach`·`/v1/coach/sessions`·`/v1/coach/sessions/{id}/turns`)에 배선한다 —
**기본 off**(opt-in).

- **결합 랭킹(`combine_diagnoses` — 순수·`l4/misconception/combined.py`)**: 사용자 확정 결정으로
  **substring 우선·semantic 후순**이다.
  - substring 매치를 *순서 그대로 위*(`diagnose`가 confidence 내림차순 정렬한 결과 신뢰).
  - 그 아래에 **semantic-only**(substring이 못 잡은 `misconception.id`만) 의미 유사도 순서대로
    append. 같은 id는 *dedup·substring 우선*(semantic 중복 버림).
  - **재정렬 금지(핵심 불변)**: substring confidence(신호 비율)와 semantic confidence(코사인
    클램프)는 *다른 축*이라(`semantic_similarity` = 표면 근접도 ≠ 진단 신뢰) 한 키로 섞어
    재정렬하지 않는다. 블록 우선(substr 블록 → semantic 블록)으로만 정렬 → substr가 하나라도
    있으면 `matches[0]`은 **반드시 substr**. 따라서 개입(`select_intervention(matches[0])`)이
    항상 substring 진단(검증된 표면 신호) 기준으로 구동되고, cos 0.99 의미 후보가 substr conf
    0.5 *확정 진단*을 추월하는 *축 혼합 거짓 랭킹*이 생기지 않는다.
  - top_k는 **결합 *끝에서만*** 적용(substr를 미리 자르면 semantic이 substr를 밀어냄 — 양쪽을
    넉넉히 받아 결합 후 한 번만 컷).
- **게이트(`config.misconception_semantic_enabled`·기본 `False`)**: off면 coach는 substring
  `diagnose()`만 쓴다(현행 비트동일·의미 매처 미호출·임베딩 로드 0). on이면 결합한다.
  `l4_step_shadow_enabled` 미러(opt-in·env `WHYMATH_MISCONCEPTION_SEMANTIC_ENABLED`).
- **비블로킹**: on일 때 coach `_compute_matches`는 의미 매처를 `asyncio.to_thread`로 *워커
  스레드*에서 호출한다 — 블로킹 임베딩(bge-m3 등)이 이벤트 루프를 막지 않게(p50<2s·동시 요청
  보호). 매처는 프로세스 싱글톤(`api/_misconception_state.py`·lazy·double-checked locking)으로
  카탈로그 사전 임베딩을 1회만 만든다. app lifespan은 게이트 on일 때만 단일 스레드 웜업으로
  `_ensure_built`(인덱스 적재)를 미리 완료(멀티스레드 경합 안전판).
- **graceful 폴백(CLAUDE.md 가용성 우선 #1≫#6)**: 의미 매칭이 *어떤 이유로든* 실패하면(모델
  미설치·DB 미도달·임베딩 오류) substring 결과로 폴백한다(500이 아니라 200·진단 1위는 substr라
  학생 경험 유지). 실패는 *조용히 넘기지 않고* warning 로그(CLAUDE.md "장애 조용히 넘어가지 말고
  로그").
- **잠긴 계약 보존**: `_build_response_payload`에 `matches`(기본 None) 인자만 추가했다 —
  미주입(직접 sync 호출·게이트 off 경로)이면 `diagnose()`로 폴백해 *현행 비트동일*(sync성·반환
  6-튜플 형태 불변). 결합 랭킹·게이트·to_thread·폴백·잠긴 계약은 단위테스트
  (`test_misconception_combined.py`·`test_coach_semantic.py`)로 못 박혀 있다.

### 측정 하니스 (slice 107) — 결합 recall·방향맹 FP를 *수치로* 잰다

slice 106의 게이트는 **기본 off**다. 켤지(=의미 매처를 coach에 결합할지)는 *추측이 아니라
측정*으로 정해야 한다 — slice 107은 그 측정 도구(`l4/misconception/semantic_eval.py`)를 더한다.
**게이트는 여전히 off**(`config.misconception_semantic_enabled` 무변경)이고, 본 모듈은 `diagnose`·
`semantic_matches`를 *소비*만 하는 오프라인·비노출 측정기다(`step_shadow_eval.py` 미러 — 같은
`PrecisionReport`/Wilson/CLI 구조).

- **프로브셋**(`tests/backend/l4/fixtures/misconception_semantic_probes.jsonl`·92줄·검증됨):
  - **recall 프로브 60**(`expected_id` 설정·`near_id` null): *틀린* 진술을 substring signals를
    피해(임베딩만 잡게) 패러프레이즈 → 의미 매처가 `expected_id`를 끌어올리면 성공.
  - **FP 프로브 32**(`expected_id` null·`near_id` 설정): *올바른* 진술(해당 오개념과 주제만
    가까움)이라 *아무 오개념이나* 매칭되면 거짓양성, 그중 `near_id`가 끌리면 *겨냥한* 방향맹.
  - 30종 전부 recall·FP를 둘 다 보유. `kind` ∈ {paraphrase, direction-reverse, negation,
    correct-near}.
- **두 축을 분리해 측정**(정직 스코프 — 임베딩 방향맹):
  - **recall**(틀린 진술을 의미로 잡음·높을수록 좋음) → **Wilson 하한**으로 보고(recall ≥ R 정직).
  - **false_positive_rate**(올바른 진술을 오개념으로 끌어올림·낮을수록 좋음) → **Wilson 상한**으로
    보고(FP ≤ F 보수). `_wilson_upper_bound`는 slice 107 신규(step_shadow엔 하한만) — 관측 FP가
    0이어도 상한>0이라 작은 표본의 과신을 막는다(예: 0/32·95% → ≈0.08).
  - **substring 기준선**도 함께 낸다(순기여 대조). *발견*: substring `diagnose`도 FP 프로브
    28/32에서 발화한다 — 올바른/near 진술이 *같은 signal 토큰*을 공유하므로(substring도
    방향맹·catalog.py 신호 한계 주석과 정합). 즉 의미 매처의 FP는 "substring이 이미 높은 FP를
    가진" 기저 위에서 평가해야 한다(둘 다 방향 판별 불가 — LLM-judged/NLI가 정본 해법).
- **CLI**: `python -m whymath_backend.l4.misconception.semantic_eval <probes.jsonl> [--threshold
  0.55] [--sweep 0.4,0.5,0.6] [--min-recall R] [--max-fp F]`. `--sweep`는 임계값별 recall/FP 한
  줄(운영점 곡선 — 임계값↑이면 recall↓·FP↓). 게이트(min-recall/max-fp)는 *측정 도구의 옵션*일
  뿐 coach 게이트와 무관하다: `recall_lower_bound ≥ R AND fp_rate_upper_bound ≤ F`면 exit 0.
  라이브 측정은 `build_provider`(기본 local=bge-m3) — Phaiakes9에서 Kiki가 돌린다.

#### 플립 decision 기준 (제안 — 수치는 Kiki 측정 후 확정)

coach 게이트를 켜는(=의미 매처를 결합하는) **플립 조건**을 다음으로 제안한다:

> **recall_lower_bound ≥ R AND fp_rate_upper_bound ≤ F** (라이브 bge-m3·운영 임계값에서)

- **F는 보수적으로** 잡는다 — student-facing *틀린 개입*이 #1 리스크다(CLAUDE.md 의사결정
  우선순위 1≫6: 학생 안전·웰빙 ≫ 비용·효율). 의미 매처가 올바른 풀이를 오개념으로 끌어올려
  학생에게 *틀린 소크라테스 개입*을 하는 것은, 패러프레이즈를 몇 개 더 잡는 recall 이득보다
  나쁘다. 단, FP가 student-facing 손해로 *직결되는지*는 결합 랭킹이 완화한다 — slice 106의
  **블록 우선**(substr가 있으면 `matches[0]`은 반드시 substr)이 의미 매치를 *후보 확장*으로만
  노출하므로, 의미-only FP가 곧장 개입이 되려면 substring이 *비어 있어야* 한다.
- **R·F 수치는 Kiki가 라이브 측정 후 확정**한다(이 하니스의 출력으로). 플립 자체는 *후속
  슬라이스*다 — 본 슬라이스는 게이트를 켜지 않고 *근거만* 만든다.
- **FP가 F를 못 맞추면**: 플립하지 않고 방향 판별(LLM-judged/NLI) 슬라이스를 먼저 한다 —
  임베딩 방향맹은 *측정으로 확인*된 한계이지 튜닝으로 없앨 수 있는 게 아니다.

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
