# 검수자용 샘플 문항 패키지 (자체생성 동등문제 코퍼스 v0)

> 전체 코퍼스 429문에서 결정론 층화 샘플링으로 뽑은 대표 표본 200문. 같은 코퍼스·N이면 바이트까지 재현된다(난수 0·정렬 기반).

## 저작권 보증

이 표본의 전건은 **자체생성**(`source_type=자체생성` · `license=WHYMATH_GENERATED` · `generation_type=FULLY_GENERATED`)이다. 코퍼스는 성취기준 + 구조 signature만으로 결정론 생성됐으며 **평가원·EBS·검정 교과서 본문을 애초에 보유하지 않는다**(본문 미보유). 사실·구조 정보는 저작권 대상이 아니라는 근거(`docs/data/licensing_safety.md` §109-112·§125) 위에 선다.

## 정직성 주의 (검수자 유의)

- **단답형에는 오개념 태그가 없다** — 오답↔오개념 귀속 검수(사람 판단 ⑤)는 객관식에만 유효.
- **외부 저작물 대비 유사도 검사 산출물은 부재하다** — 저작권 보증은 유사도 스캔이 아니라 *생성 방식*(본문 미보유·성취기준+시그니처 결정론 생성) 근거다. 사람 판단 ⑥(우연 유사)이 이 공백을 메운다.
- **명시적 `verify_status` 필드는 없다** — 기계 검증 ✓는 "코퍼스에 적재됨 = S2-a 게이트 통과"라는 사실을 표시할 뿐, 별도 상태 필드를 읽은 것이 아니다.

## 검수 서명란

검수자는 각 표본의 사람 판단 공란을 채운 뒤 아래에 서명한다.

- 상태(택1): `pending` / `approved` / `rejected` / `deferred`
- 서명: `검수:{reviewer} {reviewed_on}` (예 `검수:홍길동 2026-07-08`)

## 표본 커버리지

- 도메인: QUAD-EQ 69 · ARITH-SEQ 28 · CALC-TANGENT 19 · CALC-EXTREMUM-VALUE 18 · CALC-EXTREMUM 17 · CALC-EXTREMUM-MC 14 · GEO-SEQ 14 · EXP-EQ 9 · LOG-EQ 6 · TRIG-VAL 6
- 발문형식: 객관식 37 · 단답형 163
- 객관식 오개념: extremum-max-min-confused 14 · extremum-value-vs-point-confused 14 · factor-sign-flip 23 · opposite-root-selected 23
- 난이도 범위: 1.3 ~ 4
- 강제 오개념 누락: 없음(4종 전부 포함)

---

## 표본 01 · `wm-skel-f664ed64520f`

- 도메인: `QUAD-EQ` · 발문형식: 단답형 · 정답형식: 실수 · 난이도: 3.2
- 성취기준: [10공수1-02-02]

**문항**: 이차방정식 (x - 4)^2 = 12 의 두 근 중 더 큰 근의 값을 구하시오.

**정답**: `2*sqrt(3) + 4`

**풀이**: 완전제곱꼴에서 x - 4 = ±√12 이므로 x = 4 ± √12 이다. 이 중 큰 근은 4 + √12이다.

**verify(SymPy 입력)**: conditions: `(x - 4)**2 = 12` · answer_map: {x=2*sqrt(3) + 4} · 근 선택: largest

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 02 · `wm-skel-06badf890112`

- 도메인: `QUAD-EQ` · 발문형식: 단답형 · 정답형식: 분수 · 난이도: 2.9
- 성취기준: [10공수1-02-02]

**문항**: 3x^2 + x - 2 = 0이라는 이차방정식의 두 실근 중 더 큰 근의 값을 구하시오.

**정답**: `2/3`

**풀이**: 좌변을 인수분해하면 (3x - 2)(x + 1) = 0 이고, 두 근은 -1과 2/3이다. 이 중 큰 근은 2/3이다.

**verify(SymPy 입력)**: conditions: `3*x**2 + 1*x - 2 = 0` · answer_map: {x=2/3} · 근 선택: largest

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 03 · `wm-skel-624b52a48ccb`

- 도메인: `QUAD-EQ` · 발문형식: 단답형 · 정답형식: 실수 · 난이도: 3.2
- 성취기준: [10공수1-02-02]

**문항**: 이차방정식 x^2 = 3 의 두 근 중 더 큰 근의 값을 구하시오.

**정답**: `sqrt(3)`

**풀이**: x^2 = 3 이므로 x = ±√3 이다. 이 중 큰 근은 √3이다.

**verify(SymPy 입력)**: conditions: `x**2 = 3` · answer_map: {x=sqrt(3)} · 근 선택: largest

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 04 · `wm-skel-9136fcca4597`

- 도메인: `QUAD-EQ` · 발문형식: 단답형 · 정답형식: 실수 · 난이도: 2.9
- 성취기준: [10공수1-02-02]

**문항**: 이차방정식 2x^2 + 9x - 5 = 0의 작은 근을 찾아보세요.

**정답**: `-5`

**풀이**: 좌변을 인수분해하면 (2x - 1)(x + 5) = 0 이고, 두 근은 -5와 1/2이다. 이 중 작은 근은 -5이다.

**verify(SymPy 입력)**: conditions: `2*x**2 + 9*x - 5 = 0` · answer_map: {x=-5} · 근 선택: smallest

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 05 · `wm-skel-9e1bd1f05242`

- 도메인: `QUAD-EQ` · 발문형식: 단답형 · 정답형식: 실수 · 난이도: 3.2
- 성취기준: [10공수1-02-02]

**문항**: 이차방정식 (x - 3)^2 = 2 를 풀어 작은 근을 구하시오.

**정답**: `3 - sqrt(2)`

**풀이**: 완전제곱꼴에서 x - 3 = ±√2 이므로 x = 3 ± √2 이다. 이 중 작은 근은 3 - √2이다.

**verify(SymPy 입력)**: conditions: `(x - 3)**2 = 2` · answer_map: {x=3 - sqrt(2)} · 근 선택: smallest

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 06 · `wm-skel-ee87a36dfac4`

- 도메인: `QUAD-EQ` · 발문형식: 단답형 · 정답형식: 실수 · 난이도: 3.2
- 성취기준: [10공수1-02-02]

**문항**: 이차방정식 (x - 4)^2 = 11 의 두 근 중 더 큰 값은 얼마인가?

**정답**: `sqrt(11) + 4`

**풀이**: 완전제곱꼴에서 x - 4 = ±√11 이므로 x = 4 ± √11 이다. 이 중 큰 근은 4 + √11이다.

**verify(SymPy 입력)**: conditions: `(x - 4)**2 = 11` · answer_map: {x=sqrt(11) + 4} · 근 선택: largest

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 07 · `wm-skel-218f93d1ceff`

- 도메인: `QUAD-EQ` · 발문형식: 객관식 · 정답형식: 실수 · 난이도: 3.2
- 성취기준: [10공수1-02-02]

**문항**: 이차방정식 (x + 2)^2 = 13 의 두 근 중 큰 근은?

**정답**: `-2 + sqrt(13)`

**풀이**: 완전제곱꼴에서 x + 2 = ±√13 이므로 x = -2 ± √13 이다. 이 중 큰 근은 -2 + √13이다.

**verify(SymPy 입력)**: conditions: `(x + 2)**2 = 13` · answer_map: {x=-2 + sqrt(13)} · 근 선택: largest

**선지**:
- ① `-sqrt(13) - 2` ← 오답 · 오개념 `opposite-root-selected` (op: `select-opposite-root`)
- ② `2 - sqrt(13)` ← 오답 · 오개념 `factor-sign-flip` (op: `factor-sign-flip-root`)
- ③ `-2 + sqrt(13)` ← 정답
- ④ `2 + sqrt(13)` ← 오답 · 오개념 `factor-sign-flip` (op: `factor-sign-flip-root`)

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- [ ] ⑤ 오답↔오개념 귀속 타당(선지별 오개념·op-code)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 08 · `wm-skel-48349bfa9b31`

- 도메인: `QUAD-EQ` · 발문형식: 객관식 · 정답형식: 분수 · 난이도: 2.9
- 성취기준: [10공수1-02-02]

**문항**: 이차방정식 2x^2 + x - 6 = 0의 두 실근 중 더 큰 값을 찾아보시오.

**정답**: `3/2`

**풀이**: 좌변을 인수분해하면 (2x - 3)(x + 2) = 0 이고, 두 근은 -2와 3/2이다. 이 중 큰 근은 3/2이다.

**verify(SymPy 입력)**: conditions: `2*x**2 + 1*x - 6 = 0` · answer_map: {x=3/2} · 근 선택: largest

**선지**:
- ① `-2` ← 오답 · 오개념 `opposite-root-selected` (op: `select-opposite-root`)
- ② `-3/2` ← 오답 · 오개념 `factor-sign-flip` (op: `factor-sign-flip-root`)
- ③ `3/2` ← 정답
- ④ `2` ← 오답 · 오개념 `factor-sign-flip` (op: `factor-sign-flip-root`)

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- [ ] ⑤ 오답↔오개념 귀속 타당(선지별 오개념·op-code)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 09 · `wm-skel-64c5ca08552c`

- 도메인: `QUAD-EQ` · 발문형식: 객관식 · 정답형식: 실수 · 난이도: 2.9
- 성취기준: [10공수1-02-02]

**문항**: 이차방정식 2x^2 - 3x - 5 = 0의 두 근 중 작은 수는 무엇일까요?

**정답**: `-1`

**풀이**: 좌변을 인수분해하면 (2x - 5)(x + 1) = 0 이고, 두 근은 -1과 5/2이다. 이 중 작은 근은 -1이다.

**verify(SymPy 입력)**: conditions: `2*x**2 - 3*x - 5 = 0` · answer_map: {x=-1} · 근 선택: smallest

**선지**:
- ① `-5/2` ← 오답 · 오개념 `factor-sign-flip` (op: `factor-sign-flip-root`)
- ② `-1` ← 정답
- ③ `1` ← 오답 · 오개념 `factor-sign-flip` (op: `factor-sign-flip-root`)
- ④ `5/2` ← 오답 · 오개념 `opposite-root-selected` (op: `select-opposite-root`)

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- [ ] ⑤ 오답↔오개념 귀속 타당(선지별 오개념·op-code)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 10 · `wm-skel-6aa09f238699`

- 도메인: `QUAD-EQ` · 발문형식: 단답형 · 정답형식: 실수 · 난이도: 2.2
- 성취기준: [10공수1-02-02]

**문항**: 이차방정식 x^2 - 6x - 27 = 0 의 작은 근을 구하시오.

**정답**: `-3`

**풀이**: 좌변을 인수분해하면 (x + 3)(x - 9) = 0 이고, 두 근은 -3과 9이다. 이 중 작은 근은 -3이다.

**verify(SymPy 입력)**: conditions: `x**2 - 6*x - 27 = 0` · answer_map: {x=-3} · 근 선택: smallest

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 11 · `wm-skel-bed81b2202dd`

- 도메인: `QUAD-EQ` · 발문형식: 단답형 · 정답형식: 실수 · 난이도: 2.2
- 성취기준: [10공수1-02-02]

**문항**: 이차방정식 x^2 + x - 12 = 0 의 작은 근을 구하시오.

**정답**: `-4`

**풀이**: 좌변을 인수분해하면 (x + 4)(x - 3) = 0 이고, 두 근은 -4와 3이다. 이 중 작은 근은 -4이다.

**verify(SymPy 입력)**: conditions: `x**2 + 1*x - 12 = 0` · answer_map: {x=-4} · 근 선택: smallest

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 12 · `wm-skel-0e91b357b1b6`

- 도메인: `QUAD-EQ` · 발문형식: 단답형 · 정답형식: 자연수 · 난이도: 2
- 성취기준: [10공수1-02-02]

**문항**: 이차방정식 x^2 - 5x + 6 = 0의 작은 근을 구하시오.

**정답**: `2`

**풀이**: 좌변을 인수분해하면 (x - 2)(x - 3) = 0 이고, 두 근은 2와 3이다. 이 중 작은 근은 2이다.

**verify(SymPy 입력)**: conditions: `x**2 - 5*x + 6 = 0` · answer_map: {x=2} · 근 선택: smallest

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 13 · `wm-skel-d782cf61cf93`

- 도메인: `QUAD-EQ` · 발문형식: 단답형 · 정답형식: 자연수 · 난이도: 2
- 성취기준: [10공수1-02-02]

**문항**: 이차방정식 x^2 - 5x = 0 의 두 근 중에서 더 큰 근의 값을 구하시오.

**정답**: `5`

**풀이**: 좌변을 인수분해하면 (x)(x - 5) = 0 이고, 두 근은 0과 5이다. 이 중 큰 근은 5이다.

**verify(SymPy 입력)**: conditions: `x**2 - 5*x = 0` · answer_map: {x=5} · 근 선택: largest

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 14 · `wm-skel-fbd8a85e48dd`

- 도메인: `QUAD-EQ` · 발문형식: 단답형 · 정답형식: 실수 · 난이도: 3.2
- 성취기준: [10공수1-02-02]

**문항**: 이차방정식 (x - 2)^2 = 13의 작은 근을 찾아보세요.

**정답**: `2 - sqrt(13)`

**풀이**: 완전제곱꼴에서 x - 2 = ±√13 이므로 x = 2 ± √13 이다. 이 중 작은 근은 2 - √13이다.

**verify(SymPy 입력)**: conditions: `(x - 2)**2 = 13` · answer_map: {x=2 - sqrt(13)} · 근 선택: smallest

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 15 · `wm-skel-533719969945`

- 도메인: `QUAD-EQ` · 발문형식: 단답형 · 정답형식: 실수 · 난이도: 2
- 성취기준: [10공수1-02-02]

**문항**: 이차방정식 x^2 + x = 0 을 풀어 큰 근을 구하시오.

**정답**: `0`

**풀이**: 좌변을 인수분해하면 (x + 1)(x) = 0 이고, 두 근은 -1과 0이다. 이 중 큰 근은 0이다.

**verify(SymPy 입력)**: conditions: `x**2 + 1*x = 0` · answer_map: {x=0} · 근 선택: largest

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 16 · `wm-skel-1cc6d23230b8`

- 도메인: `QUAD-EQ` · 발문형식: 객관식 · 정답형식: 분수 · 난이도: 2.9
- 성취기준: [10공수1-02-02]

**문항**: 다차원 문제지만 이차방정식 2x^2 + 5x + 2 = 0의 두 근 중에서 크 greater한 귀를 찾아보세요.

**정답**: `-1/2`

**풀이**: 좌변을 인수분해하면 (2x + 1)(x + 2) = 0 이고, 두 근은 -2와 -1/2이다. 이 중 큰 근은 -1/2이다.

**verify(SymPy 입력)**: conditions: `2*x**2 + 5*x + 2 = 0` · answer_map: {x=-1/2} · 근 선택: largest

**선지**:
- ① `-2` ← 오답 · 오개념 `opposite-root-selected` (op: `select-opposite-root`)
- ② `-1/2` ← 정답
- ③ `1/2` ← 오답 · 오개념 `factor-sign-flip` (op: `factor-sign-flip-root`)
- ④ `2` ← 오답 · 오개념 `factor-sign-flip` (op: `factor-sign-flip-root`)

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- [ ] ⑤ 오답↔오개념 귀속 타당(선지별 오개념·op-code)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 17 · `wm-skel-6fb7d5dbc287`

- 도메인: `QUAD-EQ` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.2
- 성취기준: [10공수1-02-02]

**문항**: 이차방정식 x^2 - x - 20 = 0 의 두 실근 중 큰 수는?

**정답**: `5`

**풀이**: 좌변을 인수분해하면 (x + 4)(x - 5) = 0 이고, 두 근은 -4와 5이다. 이 중 큰 근은 5이다.

**verify(SymPy 입력)**: conditions: `x**2 - 1*x - 20 = 0` · answer_map: {x=5} · 근 선택: largest

**선지**:
- ① `-5` ← 오답 · 오개념 `factor-sign-flip` (op: `factor-sign-flip-root`)
- ② `-4` ← 오답 · 오개념 `opposite-root-selected` (op: `select-opposite-root`)
- ③ `4` ← 오답 · 오개념 `factor-sign-flip` (op: `factor-sign-flip-root`)
- ④ `5` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- [ ] ⑤ 오답↔오개념 귀속 타당(선지별 오개념·op-code)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 18 · `wm-skel-f750afcbbd98`

- 도메인: `QUAD-EQ` · 발문형식: 단답형 · 정답형식: 분수 · 난이도: 2.9
- 성취기준: [10공수1-02-02]

**문항**: 이차방정식 2x^2 + 9x + 7 = 0 의 두 근 중 작은 근을 구하시오.

**정답**: `-7/2`

**풀이**: 좌변을 인수분해하면 (2x + 7)(x + 1) = 0 이고, 두 근은 -7/2과 -1이다. 이 중 작은 근은 -7/2이다.

**verify(SymPy 입력)**: conditions: `2*x**2 + 9*x + 7 = 0` · answer_map: {x=-7/2} · 근 선택: smallest

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 19 · `wm-skel-48d657f8d56c`

- 도메인: `QUAD-EQ` · 발문형식: 단답형 · 정답형식: 분수 · 난이도: 2.6
- 성취기준: [10공수1-02-02]

**문항**: 4x^2 - 4x + 1 = 0 의 중근을 구하시오.

**정답**: `1/2`

**풀이**: 좌변을 인수분해하면 (2x - 1)^2 = 0 이므로 근은 1/2 (중근) 하나뿐이다.

**verify(SymPy 입력)**: conditions: `4*x**2 - 4*x + 1 = 0` · answer_map: {x=1/2} · 근 선택: unique

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 20 · `wm-skel-80cf67aef1f1`

- 도메인: `QUAD-EQ` · 발문형식: 단답형 · 정답형식: 실수 · 난이도: 2
- 성취기준: [10공수1-02-02]

**문항**: 이차방정식 x^2 + 6x = 0 을 푼 후 작은 근을 구하시오.

**정답**: `-6`

**풀이**: 좌변을 인수분해하면 (x + 6)(x) = 0 이고, 두 근은 -6과 0이다. 이 중 작은 근은 -6이다.

**verify(SymPy 입력)**: conditions: `x**2 + 6*x = 0` · answer_map: {x=-6} · 근 선택: smallest

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 21 · `wm-skel-d20bc34950ba`

- 도메인: `QUAD-EQ` · 발문형식: 단답형 · 정답형식: 자연수 · 난이도: 2
- 성취기준: [10공수1-02-02]

**문항**: 이차방정식 x^2 - 6x + 8 = 0 의 큰 근을 구하여라.

**정답**: `4`

**풀이**: 좌변을 인수분해하면 (x - 2)(x - 4) = 0 이고, 두 근은 2와 4이다. 이 중 큰 근은 4이다.

**verify(SymPy 입력)**: conditions: `x**2 - 6*x + 8 = 0` · answer_map: {x=4} · 근 선택: largest

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 22 · `wm-skel-7c1913d788f0`

- 도메인: `QUAD-EQ` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.4
- 성취기준: [10공수1-02-02]

**문항**: 이차방정식 x^2 - 13x + 40 = 0 의 두 근 중 작은 수는 얼마인가?

**정답**: `5`

**풀이**: 좌변을 인수분해하면 (x - 5)(x - 8) = 0 이고, 두 근은 5와 8이다. 이 중 작은 근은 5이다.

**verify(SymPy 입력)**: conditions: `x**2 - 13*x + 40 = 0` · answer_map: {x=5} · 근 선택: smallest

**선지**:
- ① `-8` ← 오답 · 오개념 `factor-sign-flip` (op: `factor-sign-flip-root`)
- ② `-5` ← 오답 · 오개념 `factor-sign-flip` (op: `factor-sign-flip-root`)
- ③ `5` ← 정답
- ④ `8` ← 오답 · 오개념 `opposite-root-selected` (op: `select-opposite-root`)

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- [ ] ⑤ 오답↔오개념 귀속 타당(선지별 오개념·op-code)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 23 · `wm-skel-f2a05fc8e0bb`

- 도메인: `QUAD-EQ` · 발문형식: 단답형 · 정답형식: 실수 · 난이도: 2.4
- 성취기준: [10공수1-02-02]

**문항**: x^2 - 49 = 0이라는 방정식의 두 해 중 작은 값은 얼마인가?

**정답**: `-7`

**풀이**: 좌변을 인수분해하면 (x + 7)(x - 7) = 0 이고, 두 근은 -7과 7이다. 이 중 작은 근은 -7이다.

**verify(SymPy 입력)**: conditions: `x**2 - 49 = 0` · answer_map: {x=-7} · 근 선택: smallest

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 24 · `wm-skel-4fef37fb7fb9`

- 도메인: `QUAD-EQ` · 발문형식: 단답형 · 정답형식: 분수 · 난이도: 3.1
- 성취기준: [10공수1-02-02]

**문항**: 이차방정식 3x^2 + 11x + 10 = 0 의 두 해 중 더 큰 값을 구하시오.

**정답**: `-5/3`

**풀이**: 좌변을 인수분해하면 (3x + 5)(x + 2) = 0 이고, 두 근은 -2와 -5/3이다. 이 중 큰 근은 -5/3이다.

**verify(SymPy 입력)**: conditions: `3*x**2 + 11*x + 10 = 0` · answer_map: {x=-5/3} · 근 선택: largest

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 25 · `wm-skel-ddc0064743fa`

- 도메인: `QUAD-EQ` · 발문형식: 단답형 · 정답형식: 실수 · 난이도: 2.4
- 성취기준: [10공수1-02-02]

**문항**: 이차방정식 x^2 + 12x + 35 = 0 의 두 근 중 작은 수를 구하시오.

**정답**: `-7`

**풀이**: 좌변을 인수분해하면 (x + 7)(x + 5) = 0 이고, 두 근은 -7과 -5이다. 이 중 작은 근은 -7이다.

**verify(SymPy 입력)**: conditions: `x**2 + 12*x + 35 = 0` · answer_map: {x=-7} · 근 선택: smallest

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 26 · `wm-skel-a2199f723ea2`

- 도메인: `QUAD-EQ` · 발문형식: 단답형 · 정답형식: 실수 · 난이도: 2.4
- 성취기준: [10공수1-02-02]

**문항**: 이차방정식 x^2 + 14x + 48 = 0 의 작은 근을 찾아보시오.

**정답**: `-8`

**풀이**: 좌변을 인수분해하면 (x + 8)(x + 6) = 0 이고, 두 근은 -8과 -6이다. 이 중 작은 근은 -8이다.

**verify(SymPy 입력)**: conditions: `x**2 + 14*x + 48 = 0` · answer_map: {x=-8} · 근 선택: smallest

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 27 · `wm-skel-a27a99e80f34`

- 도메인: `QUAD-EQ` · 발문형식: 객관식 · 정답형식: 실수 · 난이도: 3.2
- 성취기준: [10공수1-02-02]

**문항**: 이차방정식 (x - 1)^2 = 6 의 두 근 중 더 큰 근을 고르시오.

**정답**: `1 + sqrt(6)`

**풀이**: 완전제곱꼴에서 x - 1 = ±√6 이므로 x = 1 ± √6 이다. 이 중 큰 근은 1 + √6이다.

**verify(SymPy 입력)**: conditions: `(x - 1)**2 = 6` · answer_map: {x=1 + sqrt(6)} · 근 선택: largest

**선지**:
- ① `-sqrt(6) - 1` ← 오답 · 오개념 `factor-sign-flip` (op: `factor-sign-flip-root`)
- ② `1 - sqrt(6)` ← 오답 · 오개념 `opposite-root-selected` (op: `select-opposite-root`)
- ③ `-1 + sqrt(6)` ← 오답 · 오개념 `factor-sign-flip` (op: `factor-sign-flip-root`)
- ④ `1 + sqrt(6)` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- [ ] ⑤ 오답↔오개념 귀속 타당(선지별 오개념·op-code)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 28 · `wm-skel-57c7a290b008`

- 도메인: `QUAD-EQ` · 발문형식: 객관식 · 정답형식: 실수 · 난이도: 3.4
- 성취기준: [10공수1-02-02]

**문항**: 이차방정식 (x + 1)^2 = 12 의 두 근 중 작은 수는 얼마인가요?

**정답**: `-2*sqrt(3) - 1`

**풀이**: 완전제곱꼴에서 x + 1 = ±√12 이므로 x = -1 ± √12 이다. 이 중 작은 근은 -1 - √12이다.

**verify(SymPy 입력)**: conditions: `(x + 1)**2 = 12` · answer_map: {x=-2*sqrt(3) - 1} · 근 선택: smallest

**선지**:
- ① `-2*sqrt(3) - 1` ← 정답
- ② `1 - 2*sqrt(3)` ← 오답 · 오개념 `factor-sign-flip` (op: `factor-sign-flip-root`)
- ③ `-1 + 2*sqrt(3)` ← 오답 · 오개념 `opposite-root-selected` (op: `select-opposite-root`)
- ④ `1 + 2*sqrt(3)` ← 오답 · 오개념 `factor-sign-flip` (op: `factor-sign-flip-root`)

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- [ ] ⑤ 오답↔오개념 귀속 타당(선지별 오개념·op-code)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 29 · `wm-skel-13c578cd3565`

- 도메인: `QUAD-EQ` · 발문형식: 단답형 · 정답형식: 실수 · 난이도: 2.2
- 성취기준: [10공수1-02-02]

**문항**: x^2 - 25 = 0이라는 방정식의 두 해 중 더 작은 값은 얼마인가?

**정답**: `-5`

**풀이**: 좌변을 인수분해하면 (x + 5)(x - 5) = 0 이고, 두 근은 -5와 5이다. 이 중 작은 근은 -5이다.

**verify(SymPy 입력)**: conditions: `x**2 - 25 = 0` · answer_map: {x=-5} · 근 선택: smallest

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 30 · `wm-skel-414edb062317`

- 도메인: `QUAD-EQ` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.1
- 성취기준: [10공수1-02-02]

**문항**: 3x^2 - 17x + 20 = 0이라는 방정식의 두 실근 중 큰 근은?

**정답**: `4`

**풀이**: 좌변을 인수분해하면 (3x - 5)(x - 4) = 0 이고, 두 근은 5/3와 4이다. 이 중 큰 근은 4이다.

**verify(SymPy 입력)**: conditions: `3*x**2 - 17*x + 20 = 0` · answer_map: {x=4} · 근 선택: largest

**선지**:
- ① `-4` ← 오답 · 오개념 `factor-sign-flip` (op: `factor-sign-flip-root`)
- ② `-5/3` ← 오답 · 오개념 `factor-sign-flip` (op: `factor-sign-flip-root`)
- ③ `5/3` ← 오답 · 오개념 `opposite-root-selected` (op: `select-opposite-root`)
- ④ `4` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- [ ] ⑤ 오답↔오개념 귀속 타당(선지별 오개념·op-code)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 31 · `wm-skel-c60b366c016f`

- 도메인: `QUAD-EQ` · 발문형식: 객관식 · 정답형식: 실수 · 난이도: 2
- 성취기준: [10공수1-02-02]

**문항**: 이차방정식 x^2 + 8x + 7 = 0의 두 근 중 더 작은 근을 찾아보세요.

**정답**: `-7`

**풀이**: 좌변을 인수분해하면 (x + 7)(x + 1) = 0 이고, 두 근은 -7과 -1이다. 이 중 작은 근은 -7이다.

**verify(SymPy 입력)**: conditions: `x**2 + 8*x + 7 = 0` · answer_map: {x=-7} · 근 선택: smallest

**선지**:
- ① `-7` ← 정답
- ② `-1` ← 오답 · 오개념 `opposite-root-selected` (op: `select-opposite-root`)
- ③ `1` ← 오답 · 오개념 `factor-sign-flip` (op: `factor-sign-flip-root`)
- ④ `7` ← 오답 · 오개념 `factor-sign-flip` (op: `factor-sign-flip-root`)

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- [ ] ⑤ 오답↔오개념 귀속 타당(선지별 오개념·op-code)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 32 · `wm-skel-06f0dd89dbef`

- 도메인: `QUAD-EQ` · 발문형식: 단답형 · 정답형식: 자연수 · 난이도: 2.2
- 성취기준: [10공수1-02-02]

**문항**: 이차방정식 x^2 - 11x + 24 = 0 의 큰 근을 구하시오.

**정답**: `8`

**풀이**: 좌변을 인수분해하면 (x - 3)(x - 8) = 0 이고, 두 근은 3과 8이다. 이 중 큰 근은 8이다.

**verify(SymPy 입력)**: conditions: `x**2 - 11*x + 24 = 0` · answer_map: {x=8} · 근 선택: largest

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 33 · `wm-skel-a7c05d7953f8`

- 도메인: `QUAD-EQ` · 발문형식: 객관식 · 정답형식: 실수 · 난이도: 2.2
- 성취기준: [10공수1-02-02]

**문항**: 원하는 두 근 중 큰 수는 원래 방정식 x^2 + 11x + 30 = 0의 해에서 찾아야 합니다.

**정답**: `-5`

**풀이**: 좌변을 인수분해하면 (x + 6)(x + 5) = 0 이고, 두 근은 -6과 -5이다. 이 중 큰 근은 -5이다.

**verify(SymPy 입력)**: conditions: `x**2 + 11*x + 30 = 0` · answer_map: {x=-5} · 근 선택: largest

**선지**:
- ① `-6` ← 오답 · 오개념 `opposite-root-selected` (op: `select-opposite-root`)
- ② `-5` ← 정답
- ③ `5` ← 오답 · 오개념 `factor-sign-flip` (op: `factor-sign-flip-root`)
- ④ `6` ← 오답 · 오개념 `factor-sign-flip` (op: `factor-sign-flip-root`)

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- [ ] ⑤ 오답↔오개념 귀속 타당(선지별 오개념·op-code)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 34 · `wm-skel-3a8dd7ab2a47`

- 도메인: `QUAD-EQ` · 발문형식: 단답형 · 정답형식: 실수 · 난이도: 3.2
- 성취기준: [10공수1-02-02]

**문항**: 이차방정식 (x + 3)^2 = 3 의 두 근 중 작은 것을 찾아보세요.

**정답**: `-3 - sqrt(3)`

**풀이**: 완전제곱꼴에서 x + 3 = ±√3 이므로 x = -3 ± √3 이다. 이 중 작은 근은 -3 - √3이다.

**verify(SymPy 입력)**: conditions: `(x + 3)**2 = 3` · answer_map: {x=-3 - sqrt(3)} · 근 선택: smallest

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 35 · `wm-skel-5009db075a24`

- 도메인: `QUAD-EQ` · 발문형식: 단답형 · 정답형식: 자연수 · 난이도: 2.4
- 성취기준: [10공수1-02-02]

**문항**: 이차방정식 x^2 + 3x - 40 = 0의 두 실근 중 큰 근은 얼마인가?

**정답**: `5`

**풀이**: 좌변을 인수분해하면 (x + 8)(x - 5) = 0 이고, 두 근은 -8과 5이다. 이 중 큰 근은 5이다.

**verify(SymPy 입력)**: conditions: `x**2 + 3*x - 40 = 0` · answer_map: {x=5} · 근 선택: largest

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 36 · `wm-skel-602020dd4fc5`

- 도메인: `QUAD-EQ` · 발문형식: 단답형 · 정답형식: 자연수 · 난이도: 3.1
- 성취기준: [10공수1-02-02]

**문항**: 3x^2 - 17x + 10 = 0 방정식의 큰 근을 구하시오.

**정답**: `5`

**풀이**: 좌변을 인수분해하면 (3x - 2)(x - 5) = 0 이고, 두 근은 2/3와 5이다. 이 중 큰 근은 5이다.

**verify(SymPy 입력)**: conditions: `3*x**2 - 17*x + 10 = 0` · answer_map: {x=5} · 근 선택: largest

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 37 · `wm-skel-0047d3954eb8`

- 도메인: `QUAD-EQ` · 발문형식: 단답형 · 정답형식: 실수 · 난이도: 2.4
- 성취기준: [10공수1-02-02]

**문항**: 이차방정식 x^2 + x - 72 = 0 의 두 근 중 작은 수를 구하시오.

**정답**: `-9`

**풀이**: 좌변을 인수분해하면 (x + 9)(x - 8) = 0 이고, 두 근은 -9와 8이다. 이 중 작은 근은 -9이다.

**verify(SymPy 입력)**: conditions: `x**2 + 1*x - 72 = 0` · answer_map: {x=-9} · 근 선택: smallest

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 38 · `wm-skel-cf09661957b3`

- 도메인: `QUAD-EQ` · 발문형식: 객관식 · 정답형식: 실수 · 난이도: 3.2
- 성취기준: [10공수1-02-02]

**문항**: 이차방정식 (x - 4)^2 = 8 의 두 근 중 작은 근은?

**정답**: `4 - 2*sqrt(2)`

**풀이**: 완전제곱꼴에서 x - 4 = ±√8 이므로 x = 4 ± √8 이다. 이 중 작은 근은 4 - √8이다.

**verify(SymPy 입력)**: conditions: `(x - 4)**2 = 8` · answer_map: {x=4 - 2*sqrt(2)} · 근 선택: smallest

**선지**:
- ① `-4 - 2*sqrt(2)` ← 오답 · 오개념 `factor-sign-flip` (op: `factor-sign-flip-root`)
- ② `-4 + 2*sqrt(2)` ← 오답 · 오개념 `factor-sign-flip` (op: `factor-sign-flip-root`)
- ③ `4 - 2*sqrt(2)` ← 정답
- ④ `2*sqrt(2) + 4` ← 오답 · 오개념 `opposite-root-selected` (op: `select-opposite-root`)

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- [ ] ⑤ 오답↔오개념 귀속 타당(선지별 오개념·op-code)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 39 · `wm-skel-58d96b9ef7e9`

- 도메인: `QUAD-EQ` · 발문형식: 단답형 · 정답형식: 실수 · 난이도: 2.2
- 성취기준: [10공수1-02-02]

**문항**: 이차방정식 x^2 - 2x - 15 = 0 의 두 근 중 작은 값을 찾아보세요.

**정답**: `-3`

**풀이**: 좌변을 인수분해하면 (x + 3)(x - 5) = 0 이고, 두 근은 -3과 5이다. 이 중 작은 근은 -3이다.

**verify(SymPy 입력)**: conditions: `x**2 - 2*x - 15 = 0` · answer_map: {x=-3} · 근 선택: smallest

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 40 · `wm-skel-4d5c87728910`

- 도메인: `QUAD-EQ` · 발문형식: 단답형 · 정답형식: 자연수 · 난이도: 2.2
- 성취기준: [10공수1-02-02]

**문항**: 이차방정식 x^2 - 4x - 12 = 0 의 두 실근 중 큰 수를 찾아보시오.

**정답**: `6`

**풀이**: 좌변을 인수분해하면 (x + 2)(x - 6) = 0 이고, 두 근은 -2와 6이다. 이 중 큰 근은 6이다.

**verify(SymPy 입력)**: conditions: `x**2 - 4*x - 12 = 0` · answer_map: {x=6} · 근 선택: largest

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 41 · `wm-skel-fbc2e8e02b18`

- 도메인: `QUAD-EQ` · 발문형식: 객관식 · 정답형식: 실수 · 난이도: 3.2
- 성취기준: [10공수1-02-02]

**문항**: 이차방정식 (x + 1)^2 = 2의 두 실근 중 작은 값은?

**정답**: `-sqrt(2) - 1`

**풀이**: 완전제곱꼴에서 x + 1 = ±√2 이므로 x = -1 ± √2 이다. 이 중 작은 근은 -1 - √2이다.

**verify(SymPy 입력)**: conditions: `(x + 1)**2 = 2` · answer_map: {x=-sqrt(2) - 1} · 근 선택: smallest

**선지**:
- ① `-sqrt(2) - 1` ← 정답
- ② `1 - sqrt(2)` ← 오답 · 오개념 `factor-sign-flip` (op: `factor-sign-flip-root`)
- ③ `-1 + sqrt(2)` ← 오답 · 오개념 `opposite-root-selected` (op: `select-opposite-root`)
- ④ `1 + sqrt(2)` ← 오답 · 오개념 `factor-sign-flip` (op: `factor-sign-flip-root`)

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- [ ] ⑤ 오답↔오개념 귀속 타당(선지별 오개념·op-code)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 42 · `wm-skel-06913a6c0e0a`

- 도메인: `QUAD-EQ` · 발문형식: 단답형 · 정답형식: 분수 · 난이도: 3.1
- 성취기준: [10공수1-02-02]

**문항**: 이차방정식 3x^2 + 11x + 6 = 0 의 두 실근 중 더 큰 값을 구하시오.

**정답**: `-2/3`

**풀이**: 좌변을 인수분해하면 (3x + 2)(x + 3) = 0 이고, 두 근은 -3과 -2/3이다. 이 중 큰 근은 -2/3이다.

**verify(SymPy 입력)**: conditions: `3*x**2 + 11*x + 6 = 0` · answer_map: {x=-2/3} · 근 선택: largest

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 43 · `wm-skel-55281d38624c`

- 도메인: `QUAD-EQ` · 발문형식: 단답형 · 정답형식: 분수 · 난이도: 2.8
- 성취기준: [10공수1-02-02]

**문항**: 이차방정식 4x^2 + 20x + 25 = 0의 근을 구하는 문제입니다.

**정답**: `-5/2`

**풀이**: 좌변을 인수분해하면 (2x + 5)^2 = 0 이므로 근은 -5/2 (중근) 하나뿐이다.

**verify(SymPy 입력)**: conditions: `4*x**2 + 20*x + 25 = 0` · answer_map: {x=-5/2} · 근 선택: unique

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 44 · `wm-skel-65f4acce8a61`

- 도메인: `QUAD-EQ` · 발문형식: 단답형 · 정답형식: 실수 · 난이도: 2
- 성취기준: [10공수1-02-02]

**문항**: 이차방정식 x^2 - 4x = 0 의 두 근 중 작은 값은 얼마인가?

**정답**: `0`

**풀이**: 좌변을 인수분해하면 (x)(x - 4) = 0 이고, 두 근은 0과 4이다. 이 중 작은 근은 0이다.

**verify(SymPy 입력)**: conditions: `x**2 - 4*x = 0` · answer_map: {x=0} · 근 선택: smallest

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 45 · `wm-skel-811e3dae7ea6`

- 도메인: `QUAD-EQ` · 발문형식: 단답형 · 정답형식: 실수 · 난이도: 3.4
- 성취기준: [10공수1-02-02]

**문항**: 이차방정식 (x + 4)^2 = 3 의 두 근 중 더 큰 근의 값을 구하시오.

**정답**: `-4 + sqrt(3)`

**풀이**: 완전제곱꼴에서 x + 4 = ±√3 이므로 x = -4 ± √3 이다. 이 중 큰 근은 -4 + √3이다.

**verify(SymPy 입력)**: conditions: `(x + 4)**2 = 3` · answer_map: {x=-4 + sqrt(3)} · 근 선택: largest

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 46 · `wm-skel-719e1124c3af`

- 도메인: `QUAD-EQ` · 발문형식: 단답형 · 정답형식: 분수 · 난이도: 3.3
- 성취기준: [10공수1-02-02]

**문항**: 이차방정식 3x^2 + 25x + 42 = 0 의 두 근 중 큰 수를 구하시오.

**정답**: `-7/3`

**풀이**: 좌변을 인수분해하면 (3x + 7)(x + 6) = 0 이고, 두 근은 -6과 -7/3이다. 이 중 큰 근은 -7/3이다.

**verify(SymPy 입력)**: conditions: `3*x**2 + 25*x + 42 = 0` · answer_map: {x=-7/3} · 근 선택: largest

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 47 · `wm-skel-35e11f6e0756`

- 도메인: `QUAD-EQ` · 발문형식: 단답형 · 정답형식: 자연수 · 난이도: 3.1
- 성취기준: [10공수1-02-02]

**문항**: 3x^2 - 5x - 28 = 0이라는 방정식의 두 해 중 더 큰 값은 얼마인가?

**정답**: `4`

**풀이**: 좌변을 인수분해하면 (3x + 7)(x - 4) = 0 이고, 두 근은 -7/3과 4이다. 이 중 큰 근은 4이다.

**verify(SymPy 입력)**: conditions: `3*x**2 - 5*x - 28 = 0` · answer_map: {x=4} · 근 선택: largest

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 48 · `wm-skel-4da68ed906e3`

- 도메인: `QUAD-EQ` · 발문형식: 단답형 · 정답형식: 실수 · 난이도: 2.9
- 성취기준: [10공수1-02-02]

**문항**: 이차방정식 2x^2 + 9x + 10 = 0의 두 근 중 더 큰 값은 무엇인가요?

**정답**: `-2`

**풀이**: 좌변을 인수분해하면 (2x + 5)(x + 2) = 0 이고, 두 근은 -5/2와 -2이다. 이 중 큰 근은 -2이다.

**verify(SymPy 입력)**: conditions: `2*x**2 + 9*x + 10 = 0` · answer_map: {x=-2} · 근 선택: largest

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 49 · `wm-skel-cecf7c2d2c0b`

- 도메인: `QUAD-EQ` · 발문형식: 단답형 · 정답형식: 자연수 · 난이도: 2.2
- 성취기준: [10공수1-02-02]

**문항**: 이차방정식 x^2 - 7x + 12 = 0의 두 근 중 더 작은 값을 구하시오.

**정답**: `3`

**풀이**: 좌변을 인수분해하면 (x - 3)(x - 4) = 0 이고, 두 근은 3과 4이다. 이 중 작은 근은 3이다.

**verify(SymPy 입력)**: conditions: `x**2 - 7*x + 12 = 0` · answer_map: {x=3} · 근 선택: smallest

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 50 · `wm-skel-2f1b47957ce9`

- 도메인: `QUAD-EQ` · 발문형식: 객관식 · 정답형식: 실수 · 난이도: 3.1
- 성취기준: [10공수1-02-02]

**문항**: 이차방정식 3x^2 + 2x - 21 = 0 의 두 근 중 작은 값은 무엇일까요?

**정답**: `-3`

**풀이**: 좌변을 인수분해하면 (3x - 7)(x + 3) = 0 이고, 두 근은 -3과 7/3이다. 이 중 작은 근은 -3이다.

**verify(SymPy 입력)**: conditions: `3*x**2 + 2*x - 21 = 0` · answer_map: {x=-3} · 근 선택: smallest

**선지**:
- ① `-3` ← 정답
- ② `-7/3` ← 오답 · 오개념 `factor-sign-flip` (op: `factor-sign-flip-root`)
- ③ `7/3` ← 오답 · 오개념 `opposite-root-selected` (op: `select-opposite-root`)
- ④ `3` ← 오답 · 오개념 `factor-sign-flip` (op: `factor-sign-flip-root`)

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- [ ] ⑤ 오답↔오개념 귀속 타당(선지별 오개념·op-code)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 51 · `wm-skel-5a5ceb3e3ab8`

- 도메인: `QUAD-EQ` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2
- 성취기준: [10공수1-02-02]

**문항**: 이차방정식 x^2 - 2x - 3 = 0의 두 실근 중에서 더 큰 값을 찾아 주시오.

**정답**: `3`

**풀이**: 좌변을 인수분해하면 (x + 1)(x - 3) = 0 이고, 두 근은 -1과 3이다. 이 중 큰 근은 3이다.

**verify(SymPy 입력)**: conditions: `x**2 - 2*x - 3 = 0` · answer_map: {x=3} · 근 선택: largest

**선지**:
- ① `-3` ← 오답 · 오개념 `factor-sign-flip` (op: `factor-sign-flip-root`)
- ② `-1` ← 오답 · 오개념 `opposite-root-selected` (op: `select-opposite-root`)
- ③ `1` ← 오답 · 오개념 `factor-sign-flip` (op: `factor-sign-flip-root`)
- ④ `3` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- [ ] ⑤ 오답↔오개념 귀속 타당(선지별 오개념·op-code)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 52 · `wm-skel-37c15f418e69`

- 도메인: `QUAD-EQ` · 발문형식: 단답형 · 정답형식: 실수 · 난이도: 3.2
- 성취기준: [10공수1-02-02]

**문항**: 이차방정식 x^2 = 6의 두 근 중 더 큰 값을 구하여라.

**정답**: `sqrt(6)`

**풀이**: x^2 = 6 이므로 x = ±√6 이다. 이 중 큰 근은 √6이다.

**verify(SymPy 입력)**: conditions: `x**2 = 6` · answer_map: {x=sqrt(6)} · 근 선택: largest

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 53 · `wm-skel-78c0c833b6a7`

- 도메인: `QUAD-EQ` · 발문형식: 단답형 · 정답형식: 실수 · 난이도: 3.2
- 성취기준: [10공수1-02-02]

**문항**: 이차방정식 (x - 4)^2 = 7의 두 근 중 큰 값을 구하시오.

**정답**: `sqrt(7) + 4`

**풀이**: 완전제곱꼴에서 x - 4 = ±√7 이므로 x = 4 ± √7 이다. 이 중 큰 근은 4 + √7이다.

**verify(SymPy 입력)**: conditions: `(x - 4)**2 = 7` · answer_map: {x=sqrt(7) + 4} · 근 선택: largest

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 54 · `wm-skel-6aeea28234b3`

- 도메인: `QUAD-EQ` · 발문형식: 단답형 · 정답형식: 분수 · 난이도: 2.9
- 성취기준: [10공수1-02-02]

**문항**: 이차방정식 3x^2 - 2x - 8 = 0 의 두 근 중 작은 수를 구하시오.

**정답**: `-4/3`

**풀이**: 좌변을 인수분해하면 (3x + 4)(x - 2) = 0 이고, 두 근은 -4/3와 2이다. 이 중 작은 근은 -4/3이다.

**verify(SymPy 입력)**: conditions: `3*x**2 - 2*x - 8 = 0` · answer_map: {x=-4/3} · 근 선택: smallest

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 55 · `wm-skel-14819226271a`

- 도메인: `QUAD-EQ` · 발문형식: 객관식 · 정답형식: 분수 · 난이도: 2.9
- 성취기준: [10공수1-02-02]

**문항**: 이차방정식 3x^2 + 7x + 2 = 0의 두 근 중 더 큰 값은 무엇인가요?

**정답**: `-1/3`

**풀이**: 좌변을 인수분해하면 (3x + 1)(x + 2) = 0 이고, 두 근은 -2와 -1/3이다. 이 중 큰 근은 -1/3이다.

**verify(SymPy 입력)**: conditions: `3*x**2 + 7*x + 2 = 0` · answer_map: {x=-1/3} · 근 선택: largest

**선지**:
- ① `-2` ← 오답 · 오개념 `opposite-root-selected` (op: `select-opposite-root`)
- ② `-1/3` ← 정답
- ③ `1/3` ← 오답 · 오개념 `factor-sign-flip` (op: `factor-sign-flip-root`)
- ④ `2` ← 오답 · 오개념 `factor-sign-flip` (op: `factor-sign-flip-root`)

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- [ ] ⑤ 오답↔오개념 귀속 타당(선지별 오개념·op-code)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 56 · `wm-skel-22b42b4af884`

- 도메인: `QUAD-EQ` · 발문형식: 단답형 · 정답형식: 자연수 · 난이도: 2
- 성취기준: [10공수1-02-02]

**문항**: 이차방정식 x^2 - 5x + 4 = 0 의 두 실근 중 작은 근을 구하여라.

**정답**: `1`

**풀이**: 좌변을 인수분해하면 (x - 1)(x - 4) = 0 이고, 두 근은 1과 4이다. 이 중 작은 근은 1이다.

**verify(SymPy 입력)**: conditions: `x**2 - 5*x + 4 = 0` · answer_map: {x=1} · 근 선택: smallest

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 57 · `wm-skel-99abf435d5ce`

- 도메인: `QUAD-EQ` · 발문형식: 단답형 · 정답형식: 실수 · 난이도: 2
- 성취기준: [10공수1-02-02]

**문항**: 이차방정식 x^2 + 5x - 6 = 0 의 두 근 중 작은 근을 구하시오.

**정답**: `-6`

**풀이**: 좌변을 인수분해하면 (x + 6)(x - 1) = 0 이고, 두 근은 -6과 1이다. 이 중 작은 근은 -6이다.

**verify(SymPy 입력)**: conditions: `x**2 + 5*x - 6 = 0` · answer_map: {x=-6} · 근 선택: smallest

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 58 · `wm-skel-5277584d62db`

- 도메인: `QUAD-EQ` · 발문형식: 단답형 · 정답형식: 분수 · 난이도: 3.1
- 성취기준: [10공수1-02-02]

**문항**: 이차방정식 2x^2 + 11x + 12 = 0의 큰 근을 구하시오.

**정답**: `-3/2`

**풀이**: 좌변을 인수분해하면 (2x + 3)(x + 4) = 0 이고, 두 근은 -4와 -3/2이다. 이 중 큰 근은 -3/2이다.

**verify(SymPy 입력)**: conditions: `2*x**2 + 11*x + 12 = 0` · answer_map: {x=-3/2} · 근 선택: largest

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 59 · `wm-skel-4320d6383454`

- 도메인: `QUAD-EQ` · 발문형식: 객관식 · 정답형식: 실수 · 난이도: 2.4
- 성취기준: [10공수1-02-02]

**문항**: 이차방정식 x^2 + 13x + 42 = 0의 두 실근 중 더 작은 근을 찾아보세요.

**정답**: `-7`

**풀이**: 좌변을 인수분해하면 (x + 7)(x + 6) = 0 이고, 두 근은 -7과 -6이다. 이 중 작은 근은 -7이다.

**verify(SymPy 입력)**: conditions: `x**2 + 13*x + 42 = 0` · answer_map: {x=-7} · 근 선택: smallest

**선지**:
- ① `-7` ← 정답
- ② `-6` ← 오답 · 오개념 `opposite-root-selected` (op: `select-opposite-root`)
- ③ `6` ← 오답 · 오개념 `factor-sign-flip` (op: `factor-sign-flip-root`)
- ④ `7` ← 오답 · 오개념 `factor-sign-flip` (op: `factor-sign-flip-root`)

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- [ ] ⑤ 오답↔오개념 귀속 타당(선지별 오개념·op-code)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 60 · `wm-skel-acfa5a6f61fb`

- 도메인: `QUAD-EQ` · 발문형식: 단답형 · 정답형식: 자연수 · 난이도: 2
- 성취기준: [10공수1-02-02]

**문항**: 이차방정식 x^2 - x - 6 = 0의 두 근 중 큰 값을 구하시오.

**정답**: `3`

**풀이**: 좌변을 인수분해하면 (x + 2)(x - 3) = 0 이고, 두 근은 -2와 3이다. 이 중 큰 근은 3이다.

**verify(SymPy 입력)**: conditions: `x**2 - 1*x - 6 = 0` · answer_map: {x=3} · 근 선택: largest

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 61 · `wm-skel-15c0be0334fc`

- 도메인: `QUAD-EQ` · 발문형식: 객관식 · 정답형식: 실수 · 난이도: 3.2
- 성취기준: [10공수1-02-02]

**문항**: 이차방정식 (x - 3)^2 = 3 의 두 근 중 더 큰 값을 구하시오.

**정답**: `sqrt(3) + 3`

**풀이**: 완전제곱꼴에서 x - 3 = ±√3 이므로 x = 3 ± √3 이다. 이 중 큰 근은 3 + √3이다.

**verify(SymPy 입력)**: conditions: `(x - 3)**2 = 3` · answer_map: {x=sqrt(3) + 3} · 근 선택: largest

**선지**:
- ① `-3 - sqrt(3)` ← 오답 · 오개념 `factor-sign-flip` (op: `factor-sign-flip-root`)
- ② `-3 + sqrt(3)` ← 오답 · 오개념 `factor-sign-flip` (op: `factor-sign-flip-root`)
- ③ `3 - sqrt(3)` ← 오답 · 오개념 `opposite-root-selected` (op: `select-opposite-root`)
- ④ `sqrt(3) + 3` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- [ ] ⑤ 오답↔오개념 귀속 타당(선지별 오개념·op-code)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 62 · `wm-skel-856e80c989d4`

- 도메인: `QUAD-EQ` · 발문형식: 객관식 · 정답형식: 실수 · 난이도: 2.4
- 성취기준: [10공수1-02-02]

**문항**: 이차방정식 x^2 + x - 56 = 0의 두 근 중 작은 값을 찾아보시오.

**정답**: `-8`

**풀이**: 좌변을 인수분해하면 (x + 8)(x - 7) = 0 이고, 두 근은 -8과 7이다. 이 중 작은 근은 -8이다.

**verify(SymPy 입력)**: conditions: `x**2 + 1*x - 56 = 0` · answer_map: {x=-8} · 근 선택: smallest

**선지**:
- ① `-8` ← 정답
- ② `-7` ← 오답 · 오개념 `factor-sign-flip` (op: `factor-sign-flip-root`)
- ③ `7` ← 오답 · 오개념 `opposite-root-selected` (op: `select-opposite-root`)
- ④ `8` ← 오답 · 오개념 `factor-sign-flip` (op: `factor-sign-flip-root`)

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- [ ] ⑤ 오답↔오개념 귀속 타당(선지별 오개념·op-code)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 63 · `wm-skel-0b8e4ae375a6`

- 도메인: `QUAD-EQ` · 발문형식: 객관식 · 정답형식: 실수 · 난이도: 3.2
- 성취기준: [10공수1-02-02]

**문항**: 이차방정식 (x + 3)^2 = 8 의 두 근 중 더 작은 근을 고르시오.

**정답**: `-3 - 2*sqrt(2)`

**풀이**: 완전제곱꼴에서 x + 3 = ±√8 이므로 x = -3 ± √8 이다. 이 중 작은 근은 -3 - √8이다.

**verify(SymPy 입력)**: conditions: `(x + 3)**2 = 8` · answer_map: {x=-3 - 2*sqrt(2)} · 근 선택: smallest

**선지**:
- ① `-3 - 2*sqrt(2)` ← 정답
- ② `-3 + 2*sqrt(2)` ← 오답 · 오개념 `opposite-root-selected` (op: `select-opposite-root`)
- ③ `3 - 2*sqrt(2)` ← 오답 · 오개념 `factor-sign-flip` (op: `factor-sign-flip-root`)
- ④ `2*sqrt(2) + 3` ← 오답 · 오개념 `factor-sign-flip` (op: `factor-sign-flip-root`)

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- [ ] ⑤ 오답↔오개념 귀속 타당(선지별 오개념·op-code)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 64 · `wm-skel-32910b0522d4`

- 도메인: `QUAD-EQ` · 발문형식: 단답형 · 정답형식: 실수 · 난이도: 2.2
- 성취기준: [10공수1-02-02]

**문항**: 이차방정식 x^2 + x - 20 = 0의 두 실근 중 작은 값은 무엇인가요?

**정답**: `-5`

**풀이**: 좌변을 인수분해하면 (x + 5)(x - 4) = 0 이고, 두 근은 -5와 4이다. 이 중 작은 근은 -5이다.

**verify(SymPy 입력)**: conditions: `x**2 + 1*x - 20 = 0` · answer_map: {x=-5} · 근 선택: smallest

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 65 · `wm-skel-5bda43ce311d`

- 도메인: `QUAD-EQ` · 발문형식: 객관식 · 정답형식: 실수 · 난이도: 3.2
- 성취기준: [10공수1-02-02]

**문항**: 이차방정식 (x + 3)^2 = 7의 두 근 중 작은 수는 무엇인가요?

**정답**: `-3 - sqrt(7)`

**풀이**: 완전제곱꼴에서 x + 3 = ±√7 이므로 x = -3 ± √7 이다. 이 중 작은 근은 -3 - √7이다.

**verify(SymPy 입력)**: conditions: `(x + 3)**2 = 7` · answer_map: {x=-3 - sqrt(7)} · 근 선택: smallest

**선지**:
- ① `-3 - sqrt(7)` ← 정답
- ② `-3 + sqrt(7)` ← 오답 · 오개념 `opposite-root-selected` (op: `select-opposite-root`)
- ③ `3 - sqrt(7)` ← 오답 · 오개념 `factor-sign-flip` (op: `factor-sign-flip-root`)
- ④ `sqrt(7) + 3` ← 오답 · 오개념 `factor-sign-flip` (op: `factor-sign-flip-root`)

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- [ ] ⑤ 오답↔오개념 귀속 타당(선지별 오개념·op-code)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 66 · `wm-skel-05d7b6d290ae`

- 도메인: `QUAD-EQ` · 발문형식: 단답형 · 정답형식: 실수 · 난이도: 2.4
- 성취기준: [10공수1-02-02]

**문항**: 이차방정식 x^2 + 3x - 40 = 0 을 풀어 작은 근을 구하시오.

**정답**: `-8`

**풀이**: 좌변을 인수분해하면 (x + 8)(x - 5) = 0 이고, 두 근은 -8과 5이다. 이 중 작은 근은 -8이다.

**verify(SymPy 입력)**: conditions: `x**2 + 3*x - 40 = 0` · answer_map: {x=-8} · 근 선택: smallest

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 67 · `wm-skel-0e3f7822c426`

- 도메인: `QUAD-EQ` · 발문형식: 단답형 · 정답형식: 자연수 · 난이도: 2.2
- 성취기준: [10공수1-02-02]

**문항**: 이차방정식 x^2 - 9x + 20 = 0 의 큰 근을 찾아 주세요.

**정답**: `5`

**풀이**: 좌변을 인수분해하면 (x - 4)(x - 5) = 0 이고, 두 근은 4와 5이다. 이 중 큰 근은 5이다.

**verify(SymPy 입력)**: conditions: `x**2 - 9*x + 20 = 0` · answer_map: {x=5} · 근 선택: largest

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 68 · `wm-skel-2b5a92d28d61`

- 도메인: `QUAD-EQ` · 발문형식: 객관식 · 정답형식: 분수 · 난이도: 3.1
- 성취기준: [10공수1-02-02]

**문항**: 이차방정식 2x^2 - 11x + 14 = 0의 두 근 중 큰 수는 얼마인가요?

**정답**: `7/2`

**풀이**: 좌변을 인수분해하면 (2x - 7)(x - 2) = 0 이고, 두 근은 2와 7/2이다. 이 중 큰 근은 7/2이다.

**verify(SymPy 입력)**: conditions: `2*x**2 - 11*x + 14 = 0` · answer_map: {x=7/2} · 근 선택: largest

**선지**:
- ① `-7/2` ← 오답 · 오개념 `factor-sign-flip` (op: `factor-sign-flip-root`)
- ② `-2` ← 오답 · 오개념 `factor-sign-flip` (op: `factor-sign-flip-root`)
- ③ `2` ← 오답 · 오개념 `opposite-root-selected` (op: `select-opposite-root`)
- ④ `7/2` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- [ ] ⑤ 오답↔오개념 귀속 타당(선지별 오개념·op-code)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 69 · `wm-skel-7b30b792fd85`

- 도메인: `QUAD-EQ` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2
- 성취기준: [10공수1-02-02]

**문항**: 이차방정식 x^2 + 2x - 8 = 0 의 두 실근 중 큰 근은?

**정답**: `2`

**풀이**: 좌변을 인수분해하면 (x + 4)(x - 2) = 0 이고, 두 근은 -4와 2이다. 이 중 큰 근은 2이다.

**verify(SymPy 입력)**: conditions: `x**2 + 2*x - 8 = 0` · answer_map: {x=2} · 근 선택: largest

**선지**:
- ① `-4` ← 오답 · 오개념 `opposite-root-selected` (op: `select-opposite-root`)
- ② `-2` ← 오답 · 오개념 `factor-sign-flip` (op: `factor-sign-flip-root`)
- ③ `2` ← 정답
- ④ `4` ← 오답 · 오개념 `factor-sign-flip` (op: `factor-sign-flip-root`)

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- [ ] ⑤ 오답↔오개념 귀속 타당(선지별 오개념·op-code)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 70 · `wm-arseq-31bde47c7d29`

- 도메인: `ARITH-SEQ` · 발문형식: 단답형 · 정답형식: 자연수 · 난이도: 2
- 성취기준: [12대수03-02]

**문항**: 등차수열 {aₙ}의 첫째항이 3이고 공차가 6일 때, 제12항을 구하시오.

**정답**: `69`

**풀이**: 등차수열의 제n항은 첫째항에 공차를 (n−1)번 더한 값이므로, 제12항은 69 이다.

**verify(SymPy 입력)**: conditions: `x - (3 + (12 - 1)*6) = 0` · answer_map: {x=69} · 근 선택: unique

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 71 · `wm-arseq-02aa66a18d84`

- 도메인: `ARITH-SEQ` · 발문형식: 단답형 · 정답형식: 자연수 · 난이도: 1.8
- 성취기준: [12대수03-02]

**문항**: 등차수열 {aₙ}의 첫째항이 1이고 공차가 3일 때, 제11항을 구하시오.

**정답**: `31`

**풀이**: 등차수열의 제n항은 첫째항에 공차를 (n−1)번 더한 값이므로, 제11항은 31 이다.

**verify(SymPy 입력)**: conditions: `x - (1 + (11 - 1)*3) = 0` · answer_map: {x=31} · 근 선택: unique

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 72 · `wm-arseq-8fdfca1070d1`

- 도메인: `ARITH-SEQ` · 발문형식: 단답형 · 정답형식: 자연수 · 난이도: 1.8
- 성취기준: [12대수03-02]

**문항**: 첫째항이 2, 공차가 2인 등차수열의 제15항을 구하시오.

**정답**: `30`

**풀이**: 등차수열의 제n항은 첫째항에 공차를 (n−1)번 더한 값이므로, 제15항은 30 이다.

**verify(SymPy 입력)**: conditions: `x - (2 + (15 - 1)*2) = 0` · answer_map: {x=30} · 근 선택: unique

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 73 · `wm-arseq-cf0a1db2d30d`

- 도메인: `ARITH-SEQ` · 발문형식: 단답형 · 정답형식: 자연수 · 난이도: 2
- 성취기준: [12대수03-02]

**문항**: 등차수열 {aₙ}의 첫째항이 1이고 공차가 5일 때, 제15항을 구하시오.

**정답**: `71`

**풀이**: 등차수열의 제n항은 첫째항에 공차를 (n−1)번 더한 값이므로, 제15항은 71 이다.

**verify(SymPy 입력)**: conditions: `x - (1 + (15 - 1)*5) = 0` · answer_map: {x=71} · 근 선택: unique

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 74 · `wm-arseq-0c7d4ed59aef`

- 도메인: `ARITH-SEQ` · 발문형식: 단답형 · 정답형식: 자연수 · 난이도: 2
- 성취기준: [12대수03-02]

**문항**: 첫째항 5, 공차 6인 등차수열에서 13번째 항의 값을 구하시오.

**정답**: `77`

**풀이**: 등차수열의 제n항은 첫째항에 공차를 (n−1)번 더한 값이므로, 제13항은 77 이다.

**verify(SymPy 입력)**: conditions: `x - (5 + (13 - 1)*6) = 0` · answer_map: {x=77} · 근 선택: unique

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 75 · `wm-arseq-32fccf4697af`

- 도메인: `ARITH-SEQ` · 발문형식: 단답형 · 정답형식: 자연수 · 난이도: 2
- 성취기준: [12대수03-02]

**문항**: 첫째항 5, 공차 6인 등차수열에서 15번째 항의 값을 구하시오.

**정답**: `89`

**풀이**: 등차수열의 제n항은 첫째항에 공차를 (n−1)번 더한 값이므로, 제15항은 89 이다.

**verify(SymPy 입력)**: conditions: `x - (5 + (15 - 1)*6) = 0` · answer_map: {x=89} · 근 선택: unique

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 76 · `wm-arseq-254465c46f94`

- 도메인: `ARITH-SEQ` · 발문형식: 단답형 · 정답형식: 자연수 · 난이도: 1.8
- 성취기준: [12대수03-02]

**문항**: 첫째항이 1, 공차가 3인 등차수열의 제10항을 구하시오.

**정답**: `28`

**풀이**: 등차수열의 제n항은 첫째항에 공차를 (n−1)번 더한 값이므로, 제10항은 28 이다.

**verify(SymPy 입력)**: conditions: `x - (1 + (10 - 1)*3) = 0` · answer_map: {x=28} · 근 선택: unique

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 77 · `wm-arseq-ac26002af2ef`

- 도메인: `ARITH-SEQ` · 발문형식: 단답형 · 정답형식: 자연수 · 난이도: 1.8
- 성취기준: [12대수03-02]

**문항**: 등차수열 {aₙ}의 첫째항이 1이고 공차가 4일 때, 제9항을 구하시오.

**정답**: `33`

**풀이**: 등차수열의 제n항은 첫째항에 공차를 (n−1)번 더한 값이므로, 제9항은 33 이다.

**verify(SymPy 입력)**: conditions: `x - (1 + (9 - 1)*4) = 0` · answer_map: {x=33} · 근 선택: unique

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 78 · `wm-arseq-007832bc44fd`

- 도메인: `ARITH-SEQ` · 발문형식: 단답형 · 정답형식: 자연수 · 난이도: 2
- 성취기준: [12대수03-02]

**문항**: 첫째항 4, 공차 6인 등차수열에서 12번째 항의 값을 구하시오.

**정답**: `70`

**풀이**: 등차수열의 제n항은 첫째항에 공차를 (n−1)번 더한 값이므로, 제12항은 70 이다.

**verify(SymPy 입력)**: conditions: `x - (4 + (12 - 1)*6) = 0` · answer_map: {x=70} · 근 선택: unique

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 79 · `wm-arseq-6d4af8d57a32`

- 도메인: `ARITH-SEQ` · 발문형식: 단답형 · 정답형식: 자연수 · 난이도: 1.8
- 성취기준: [12대수03-02]

**문항**: 첫째항이 1, 공차가 2인 등차수열의 제15항을 구하시오.

**정답**: `29`

**풀이**: 등차수열의 제n항은 첫째항에 공차를 (n−1)번 더한 값이므로, 제15항은 29 이다.

**verify(SymPy 입력)**: conditions: `x - (1 + (15 - 1)*2) = 0` · answer_map: {x=29} · 근 선택: unique

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 80 · `wm-arseq-8998642430e8`

- 도메인: `ARITH-SEQ` · 발문형식: 단답형 · 정답형식: 자연수 · 난이도: 2
- 성취기준: [12대수03-02]

**문항**: 첫째항 1, 공차 6인 등차수열에서 14번째 항의 값을 구하시오.

**정답**: `79`

**풀이**: 등차수열의 제n항은 첫째항에 공차를 (n−1)번 더한 값이므로, 제14항은 79 이다.

**verify(SymPy 입력)**: conditions: `x - (1 + (14 - 1)*6) = 0` · answer_map: {x=79} · 근 선택: unique

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 81 · `wm-arseq-01fe20b14f12`

- 도메인: `ARITH-SEQ` · 발문형식: 단답형 · 정답형식: 자연수 · 난이도: 2
- 성취기준: [12대수03-02]

**문항**: 첫째항 1, 공차 6인 등차수열에서 13번째 항의 값을 구하시오.

**정답**: `73`

**풀이**: 등차수열의 제n항은 첫째항에 공차를 (n−1)번 더한 값이므로, 제13항은 73 이다.

**verify(SymPy 입력)**: conditions: `x - (1 + (13 - 1)*6) = 0` · answer_map: {x=73} · 근 선택: unique

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 82 · `wm-arseq-253b5ee25365`

- 도메인: `ARITH-SEQ` · 발문형식: 단답형 · 정답형식: 자연수 · 난이도: 2
- 성취기준: [12대수03-02]

**문항**: 첫째항이 2, 공차가 5인 등차수열의 제13항을 구하시오.

**정답**: `62`

**풀이**: 등차수열의 제n항은 첫째항에 공차를 (n−1)번 더한 값이므로, 제13항은 62 이다.

**verify(SymPy 입력)**: conditions: `x - (2 + (13 - 1)*5) = 0` · answer_map: {x=62} · 근 선택: unique

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 83 · `wm-arseq-a47d2844a8ca`

- 도메인: `ARITH-SEQ` · 발문형식: 단답형 · 정답형식: 자연수 · 난이도: 1.8
- 성취기준: [12대수03-02]

**문항**: 첫째항이 1, 공차가 1인 등차수열의 제11항을 구하시오.

**정답**: `11`

**풀이**: 등차수열의 제n항은 첫째항에 공차를 (n−1)번 더한 값이므로, 제11항은 11 이다.

**verify(SymPy 입력)**: conditions: `x - (1 + (11 - 1)*1) = 0` · answer_map: {x=11} · 근 선택: unique

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 84 · `wm-arseq-e06c49520959`

- 도메인: `ARITH-SEQ` · 발문형식: 단답형 · 정답형식: 자연수 · 난이도: 1.6
- 성취기준: [12대수03-02]

**문항**: 등차수열 {aₙ}의 첫째항이 1이고 공차가 1일 때, 제4항을 구하시오.

**정답**: `4`

**풀이**: 등차수열의 제n항은 첫째항에 공차를 (n−1)번 더한 값이므로, 제4항은 4 이다.

**verify(SymPy 입력)**: conditions: `x - (1 + (4 - 1)*1) = 0` · answer_map: {x=4} · 근 선택: unique

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 85 · `wm-arseq-b09a9117ad8a`

- 도메인: `ARITH-SEQ` · 발문형식: 단답형 · 정답형식: 자연수 · 난이도: 2
- 성취기준: [12대수03-02]

**문항**: 첫째항이 3, 공차가 6인 등차수열의 제13항을 구하시오.

**정답**: `75`

**풀이**: 등차수열의 제n항은 첫째항에 공차를 (n−1)번 더한 값이므로, 제13항은 75 이다.

**verify(SymPy 입력)**: conditions: `x - (3 + (13 - 1)*6) = 0` · answer_map: {x=75} · 근 선택: unique

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 86 · `wm-arseq-1dd3fd129573`

- 도메인: `ARITH-SEQ` · 발문형식: 단답형 · 정답형식: 자연수 · 난이도: 2
- 성취기준: [12대수03-02]

**문항**: 첫째항 4, 공차 6인 등차수열에서 15번째 항의 값을 구하시오.

**정답**: `88`

**풀이**: 등차수열의 제n항은 첫째항에 공차를 (n−1)번 더한 값이므로, 제15항은 88 이다.

**verify(SymPy 입력)**: conditions: `x - (4 + (15 - 1)*6) = 0` · answer_map: {x=88} · 근 선택: unique

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 87 · `wm-arseq-c9a3f1d53ee8`

- 도메인: `ARITH-SEQ` · 발문형식: 단답형 · 정답형식: 자연수 · 난이도: 1.8
- 성취기준: [12대수03-02]

**문항**: 등차수열 {aₙ}의 첫째항이 1이고 공차가 2일 때, 제11항을 구하시오.

**정답**: `21`

**풀이**: 등차수열의 제n항은 첫째항에 공차를 (n−1)번 더한 값이므로, 제11항은 21 이다.

**verify(SymPy 입력)**: conditions: `x - (1 + (11 - 1)*2) = 0` · answer_map: {x=21} · 근 선택: unique

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 88 · `wm-arseq-7ee05322761a`

- 도메인: `ARITH-SEQ` · 발문형식: 단답형 · 정답형식: 자연수 · 난이도: 2
- 성취기준: [12대수03-02]

**문항**: 첫째항 1, 공차 5인 등차수열에서 10번째 항의 값을 구하시오.

**정답**: `46`

**풀이**: 등차수열의 제n항은 첫째항에 공차를 (n−1)번 더한 값이므로, 제10항은 46 이다.

**verify(SymPy 입력)**: conditions: `x - (1 + (10 - 1)*5) = 0` · answer_map: {x=46} · 근 선택: unique

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 89 · `wm-arseq-8866d05cfbed`

- 도메인: `ARITH-SEQ` · 발문형식: 단답형 · 정답형식: 자연수 · 난이도: 2
- 성취기준: [12대수03-02]

**문항**: 등차수열 {aₙ}의 첫째항이 1이고 공차가 4일 때, 제15항을 구하시오.

**정답**: `57`

**풀이**: 등차수열의 제n항은 첫째항에 공차를 (n−1)번 더한 값이므로, 제15항은 57 이다.

**verify(SymPy 입력)**: conditions: `x - (1 + (15 - 1)*4) = 0` · answer_map: {x=57} · 근 선택: unique

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 90 · `wm-arseq-91d76377b770`

- 도메인: `ARITH-SEQ` · 발문형식: 단답형 · 정답형식: 자연수 · 난이도: 1.8
- 성취기준: [12대수03-02]

**문항**: 첫째항이 1, 공차가 2인 등차수열의 제10항을 구하시오.

**정답**: `19`

**풀이**: 등차수열의 제n항은 첫째항에 공차를 (n−1)번 더한 값이므로, 제10항은 19 이다.

**verify(SymPy 입력)**: conditions: `x - (1 + (10 - 1)*2) = 0` · answer_map: {x=19} · 근 선택: unique

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 91 · `wm-arseq-c4ba1ee82ced`

- 도메인: `ARITH-SEQ` · 발문형식: 단답형 · 정답형식: 자연수 · 난이도: 2
- 성취기준: [12대수03-02]

**문항**: 등차수열 {aₙ}의 첫째항이 2이고 공차가 6일 때, 제14항을 구하시오.

**정답**: `80`

**풀이**: 등차수열의 제n항은 첫째항에 공차를 (n−1)번 더한 값이므로, 제14항은 80 이다.

**verify(SymPy 입력)**: conditions: `x - (2 + (14 - 1)*6) = 0` · answer_map: {x=80} · 근 선택: unique

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 92 · `wm-arseq-61793cbdeaca`

- 도메인: `ARITH-SEQ` · 발문형식: 단답형 · 정답형식: 자연수 · 난이도: 1.6
- 성취기준: [12대수03-02]

**문항**: 첫째항이 1, 공차가 2인 등차수열의 제9항을 구하시오.

**정답**: `17`

**풀이**: 등차수열의 제n항은 첫째항에 공차를 (n−1)번 더한 값이므로, 제9항은 17 이다.

**verify(SymPy 입력)**: conditions: `x - (1 + (9 - 1)*2) = 0` · answer_map: {x=17} · 근 선택: unique

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 93 · `wm-arseq-680852d3c2cf`

- 도메인: `ARITH-SEQ` · 발문형식: 단답형 · 정답형식: 자연수 · 난이도: 1.8
- 성취기준: [12대수03-02]

**문항**: 등차수열 {aₙ}의 첫째항이 3이고 공차가 3일 때, 제13항을 구하시오.

**정답**: `39`

**풀이**: 등차수열의 제n항은 첫째항에 공차를 (n−1)번 더한 값이므로, 제13항은 39 이다.

**verify(SymPy 입력)**: conditions: `x - (3 + (13 - 1)*3) = 0` · answer_map: {x=39} · 근 선택: unique

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 94 · `wm-arseq-db6fb5c80126`

- 도메인: `ARITH-SEQ` · 발문형식: 단답형 · 정답형식: 자연수 · 난이도: 2
- 성취기준: [12대수03-02]

**문항**: 등차수열 {aₙ}의 첫째항이 2이고 공차가 4일 때, 제15항을 구하시오.

**정답**: `58`

**풀이**: 등차수열의 제n항은 첫째항에 공차를 (n−1)번 더한 값이므로, 제15항은 58 이다.

**verify(SymPy 입력)**: conditions: `x - (2 + (15 - 1)*4) = 0` · answer_map: {x=58} · 근 선택: unique

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 95 · `wm-arseq-4fb383e65e8e`

- 도메인: `ARITH-SEQ` · 발문형식: 단답형 · 정답형식: 자연수 · 난이도: 2
- 성취기준: [12대수03-02]

**문항**: 등차수열 {aₙ}의 첫째항이 2이고 공차가 5일 때, 제11항을 구하시오.

**정답**: `52`

**풀이**: 등차수열의 제n항은 첫째항에 공차를 (n−1)번 더한 값이므로, 제11항은 52 이다.

**verify(SymPy 입력)**: conditions: `x - (2 + (11 - 1)*5) = 0` · answer_map: {x=52} · 근 선택: unique

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 96 · `wm-arseq-3f58741fb99d`

- 도메인: `ARITH-SEQ` · 발문형식: 단답형 · 정답형식: 자연수 · 난이도: 1.6
- 성취기준: [12대수03-02]

**문항**: 첫째항 1, 공차 3인 등차수열에서 8번째 항의 값을 구하시오.

**정답**: `22`

**풀이**: 등차수열의 제n항은 첫째항에 공차를 (n−1)번 더한 값이므로, 제8항은 22 이다.

**verify(SymPy 입력)**: conditions: `x - (1 + (8 - 1)*3) = 0` · answer_map: {x=22} · 근 선택: unique

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 97 · `wm-arseq-f654ffdaeca9`

- 도메인: `ARITH-SEQ` · 발문형식: 단답형 · 정답형식: 자연수 · 난이도: 1.8
- 성취기준: [12대수03-02]

**문항**: 첫째항 2, 공차 2인 등차수열에서 12번째 항의 값을 구하시오.

**정답**: `24`

**풀이**: 등차수열의 제n항은 첫째항에 공차를 (n−1)번 더한 값이므로, 제12항은 24 이다.

**verify(SymPy 입력)**: conditions: `x - (2 + (12 - 1)*2) = 0` · answer_map: {x=24} · 근 선택: unique

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 98 · `wm-calc-tan-9f7d59dc1c06`

- 도메인: `CALC-TANGENT` · 발문형식: 단답형 · 정답형식: 실수 · 난이도: 3.6
- 성취기준: [12미적Ⅰ-02-01]

**문항**: 함수 f(x) = x^3 - 54x 의 그래프 위에서 접선의 기울기가 -6인 두 점 중 x좌표가 작은 점의 x좌표를 구하시오.

**정답**: `-4`

**풀이**: f(x)를 미분해 접선의 기울기 조건 f'(x) = -6을 정리하면 3(x + 4)(x - 4) = 0 이므로 접점의 x좌표는 x = -4, x = 4 이다. 이 중 x좌표가 작은 것은 -4이다.

**verify(SymPy 입력)**: conditions: `x**2 - 16 = 0` · answer_map: {x=-4} · 근 선택: smallest

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 99 · `wm-calc-tan-c5d184e00244`

- 도메인: `CALC-TANGENT` · 발문형식: 단답형 · 정답형식: 자연수 · 난이도: 3.8
- 성취기준: [12미적Ⅰ-02-01]

**문항**: 함수 f(x) = x^3 + 9x^2 - 54x 의 그래프 위에서 접선의 기울기가 -6인 두 점 중 x좌표가 큰 점의 x좌표를 구하시오.

**정답**: `2`

**풀이**: f(x)를 미분해 접선의 기울기 조건 f'(x) = -6을 정리하면 3(x + 8)(x - 2) = 0 이므로 접점의 x좌표는 x = -8, x = 2 이다. 이 중 x좌표가 큰 것은 2이다.

**verify(SymPy 입력)**: conditions: `x**2 + 6*x - 16 = 0` · answer_map: {x=2} · 근 선택: largest

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 100 · `wm-calc-tan-02f2bf569298`

- 도메인: `CALC-TANGENT` · 발문형식: 단답형 · 정답형식: 자연수 · 난이도: 3.3
- 성취기준: [12미적Ⅰ-02-01]

**문항**: 곡선 y = f(x) = x^3 - 12x^2 + 34x 위의 점 중 접선의 기울기가 -2인 점의 x좌표가 큰 것을 구하시오.

**정답**: `6`

**풀이**: f(x)를 미분해 접선의 기울기 조건 f'(x) = -2를 정리하면 3(x - 2)(x - 6) = 0 이므로 접점의 x좌표는 x = 2, x = 6 이다. 이 중 x좌표가 큰 것은 6이다.

**verify(SymPy 입력)**: conditions: `x**2 - 8*x + 12 = 0` · answer_map: {x=6} · 근 선택: largest

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 101 · `wm-calc-tan-bb0a0db497ee`

- 도메인: `CALC-TANGENT` · 발문형식: 단답형 · 정답형식: 자연수 · 난이도: 3.6
- 성취기준: [12미적Ⅰ-02-01]

**문항**: 함수 f(x) = x^3 - 54x 의 그래프 위에서 접선의 기울기가 -6인 두 점 중 x좌표가 큰 점의 x좌표를 구하시오.

**정답**: `4`

**풀이**: f(x)를 미분해 접선의 기울기 조건 f'(x) = -6을 정리하면 3(x + 4)(x - 4) = 0 이므로 접점의 x좌표는 x = -4, x = 4 이다. 이 중 x좌표가 큰 것은 4이다.

**verify(SymPy 입력)**: conditions: `x**2 - 16 = 0` · answer_map: {x=4} · 근 선택: largest

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 102 · `wm-calc-tan-0f66511a6c1a`

- 도메인: `CALC-TANGENT` · 발문형식: 단답형 · 정답형식: 자연수 · 난이도: 3.6
- 성취기준: [12미적Ⅰ-02-01]

**문항**: 함수 f(x) = x^3 + 6x^2 - 32x 의 그래프 위에서 접선의 기울기가 4인 두 점 중 x좌표가 큰 점의 x좌표를 구하시오.

**정답**: `2`

**풀이**: f(x)를 미분해 접선의 기울기 조건 f'(x) = 4를 정리하면 3(x + 6)(x - 2) = 0 이므로 접점의 x좌표는 x = -6, x = 2 이다. 이 중 x좌표가 큰 것은 2이다.

**verify(SymPy 입력)**: conditions: `x**2 + 4*x - 12 = 0` · answer_map: {x=2} · 근 선택: largest

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 103 · `wm-calc-tan-74d652ed1543`

- 도메인: `CALC-TANGENT` · 발문형식: 단답형 · 정답형식: 실수 · 난이도: 3.3
- 성취기준: [12미적Ⅰ-02-01]

**문항**: 곡선 y = f(x) = x^3 + 9x^2 - 6x 위의 점 중 접선의 기울기가 -6인 점의 x좌표가 작은 것을 구하시오.

**정답**: `-6`

**풀이**: f(x)를 미분해 접선의 기울기 조건 f'(x) = -6을 정리하면 3(x + 6)(x) = 0 이므로 접점의 x좌표는 x = -6, x = 0 이다. 이 중 x좌표가 작은 것은 -6이다.

**verify(SymPy 입력)**: conditions: `x**2 + 6*x = 0` · answer_map: {x=-6} · 근 선택: smallest

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 104 · `wm-calc-tan-362338e0a674`

- 도메인: `CALC-TANGENT` · 발문형식: 단답형 · 정답형식: 실수 · 난이도: 3.5
- 성취기준: [12미적Ⅰ-02-01]

**문항**: 곡선 y = f(x) = x^3 + 21x^2 + 133x 위의 점 중 접선의 기울기가 -2인 점의 x좌표가 큰 것을 구하시오.

**정답**: `-5`

**풀이**: f(x)를 미분해 접선의 기울기 조건 f'(x) = -2를 정리하면 3(x + 9)(x + 5) = 0 이므로 접점의 x좌표는 x = -9, x = -5 이다. 이 중 x좌표가 큰 것은 -5이다.

**verify(SymPy 입력)**: conditions: `x**2 + 14*x + 45 = 0` · answer_map: {x=-5} · 근 선택: largest

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 105 · `wm-calc-tan-290fc784a150`

- 도메인: `CALC-TANGENT` · 발문형식: 단답형 · 정답형식: 실수 · 난이도: 3.3
- 성취기준: [12미적Ⅰ-02-01]

**문항**: 함수 f(x) = x^3 - 6x^2 - 11x 의 그래프 위에서 접선의 기울기가 4인 두 점 중 x좌표가 작은 점의 x좌표를 구하시오.

**정답**: `-1`

**풀이**: f(x)를 미분해 접선의 기울기 조건 f'(x) = 4를 정리하면 3(x + 1)(x - 5) = 0 이므로 접점의 x좌표는 x = -1, x = 5 이다. 이 중 x좌표가 작은 것은 -1이다.

**verify(SymPy 입력)**: conditions: `x**2 - 4*x - 5 = 0` · answer_map: {x=-1} · 근 선택: smallest

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 106 · `wm-calc-tan-9f94db5eb950`

- 도메인: `CALC-TANGENT` · 발문형식: 단답형 · 정답형식: 실수 · 난이도: 3.5
- 성취기준: [12미적Ⅰ-02-01]

**문항**: 함수 f(x) = x^3 + 24x^2 + 193x 의 그래프 위에서 접선의 기울기가 4인 두 점 중 x좌표가 큰 점의 x좌표를 구하시오.

**정답**: `-7`

**풀이**: f(x)를 미분해 접선의 기울기 조건 f'(x) = 4를 정리하면 3(x + 9)(x + 7) = 0 이므로 접점의 x좌표는 x = -9, x = -7 이다. 이 중 x좌표가 큰 것은 -7이다.

**verify(SymPy 입력)**: conditions: `x**2 + 16*x + 63 = 0` · answer_map: {x=-7} · 근 선택: largest

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 107 · `wm-calc-tan-4264ce1a6acf`

- 도메인: `CALC-TANGENT` · 발문형식: 단답형 · 정답형식: 자연수 · 난이도: 3.3
- 성취기준: [12미적Ⅰ-02-01]

**문항**: 함수 f(x) = x^3 - 12x^2 + 43x 의 그래프 위에서 접선의 기울기가 -2인 두 점 중 x좌표가 작은 점의 x좌표를 구하시오.

**정답**: `3`

**풀이**: f(x)를 미분해 접선의 기울기 조건 f'(x) = -2를 정리하면 3(x - 3)(x - 5) = 0 이므로 접점의 x좌표는 x = 3, x = 5 이다. 이 중 x좌표가 작은 것은 3이다.

**verify(SymPy 입력)**: conditions: `x**2 - 8*x + 15 = 0` · answer_map: {x=3} · 근 선택: smallest

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 108 · `wm-calc-tan-5e980f9df14c`

- 도메인: `CALC-TANGENT` · 발문형식: 단답형 · 정답형식: 실수 · 난이도: 3.6
- 성취기준: [12미적Ⅰ-02-01]

**문항**: 곡선 y = f(x) = x^3 - 3x^2 - 47x 위의 점 중 접선의 기울기가 -2인 점의 x좌표가 작은 것을 구하시오.

**정답**: `-3`

**풀이**: f(x)를 미분해 접선의 기울기 조건 f'(x) = -2를 정리하면 3(x + 3)(x - 5) = 0 이므로 접점의 x좌표는 x = -3, x = 5 이다. 이 중 x좌표가 작은 것은 -3이다.

**verify(SymPy 입력)**: conditions: `x**2 - 2*x - 15 = 0` · answer_map: {x=-3} · 근 선택: smallest

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 109 · `wm-calc-tan-976b8010dbb5`

- 도메인: `CALC-TANGENT` · 발문형식: 단답형 · 정답형식: 자연수 · 난이도: 4
- 성취기준: [12미적Ⅰ-02-01]

**문항**: 함수 f(x) = x^3 - 9x^2 - 87x 의 그래프 위에서 접선의 기울기가 -6인 두 점 중 x좌표가 큰 점의 x좌표를 구하시오.

**정답**: `9`

**풀이**: f(x)를 미분해 접선의 기울기 조건 f'(x) = -6을 정리하면 3(x + 3)(x - 9) = 0 이므로 접점의 x좌표는 x = -3, x = 9 이다. 이 중 x좌표가 큰 것은 9이다.

**verify(SymPy 입력)**: conditions: `x**2 - 6*x - 27 = 0` · answer_map: {x=9} · 근 선택: largest

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 110 · `wm-calc-tan-e93a485579c5`

- 도메인: `CALC-TANGENT` · 발문형식: 단답형 · 정답형식: 자연수 · 난이도: 3.5
- 성취기준: [12미적Ⅰ-02-01]

**문항**: 함수 f(x) = x^3 - 21x^2 + 133x 의 그래프 위에서 접선의 기울기가 -2인 두 점 중 x좌표가 큰 점의 x좌표를 구하시오.

**정답**: `9`

**풀이**: f(x)를 미분해 접선의 기울기 조건 f'(x) = -2를 정리하면 3(x - 5)(x - 9) = 0 이므로 접점의 x좌표는 x = 5, x = 9 이다. 이 중 x좌표가 큰 것은 9이다.

**verify(SymPy 입력)**: conditions: `x**2 - 14*x + 45 = 0` · answer_map: {x=9} · 근 선택: largest

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 111 · `wm-calc-tan-ba13feaffd7d`

- 도메인: `CALC-TANGENT` · 발문형식: 단답형 · 정답형식: 실수 · 난이도: 3.3
- 성취기준: [12미적Ⅰ-02-01]

**문항**: 곡선 y = f(x) = x^3 + 12x^2 - 2x 위의 점 중 접선의 기울기가 -2인 점의 x좌표가 작은 것을 구하시오.

**정답**: `-8`

**풀이**: f(x)를 미분해 접선의 기울기 조건 f'(x) = -2를 정리하면 3(x + 8)(x) = 0 이므로 접점의 x좌표는 x = -8, x = 0 이다. 이 중 x좌표가 작은 것은 -8이다.

**verify(SymPy 입력)**: conditions: `x**2 + 8*x = 0` · answer_map: {x=-8} · 근 선택: smallest

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 112 · `wm-calc-tan-f881e9460f4f`

- 도메인: `CALC-TANGENT` · 발문형식: 단답형 · 정답형식: 자연수 · 난이도: 3
- 성취기준: [12미적Ⅰ-02-01]

**문항**: 곡선 y = f(x) = x^3 - 9x^2 + 18x 위의 점 중 접선의 기울기가 -6인 점의 x좌표가 큰 것을 구하시오.

**정답**: `4`

**풀이**: f(x)를 미분해 접선의 기울기 조건 f'(x) = -6을 정리하면 3(x - 2)(x - 4) = 0 이므로 접점의 x좌표는 x = 2, x = 4 이다. 이 중 x좌표가 큰 것은 4이다.

**verify(SymPy 입력)**: conditions: `x**2 - 6*x + 8 = 0` · answer_map: {x=4} · 근 선택: largest

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 113 · `wm-calc-tan-0a02899793c0`

- 도메인: `CALC-TANGENT` · 발문형식: 단답형 · 정답형식: 자연수 · 난이도: 3.3
- 성취기준: [12미적Ⅰ-02-01]

**문항**: 곡선 y = f(x) = x^3 + 3x^2 - 26x 위의 점 중 접선의 기울기가 -2인 점의 x좌표가 큰 것을 구하시오.

**정답**: `2`

**풀이**: f(x)를 미분해 접선의 기울기 조건 f'(x) = -2를 정리하면 3(x + 4)(x - 2) = 0 이므로 접점의 x좌표는 x = -4, x = 2 이다. 이 중 x좌표가 큰 것은 2이다.

**verify(SymPy 입력)**: conditions: `x**2 + 2*x - 8 = 0` · answer_map: {x=2} · 근 선택: largest

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 114 · `wm-calc-tan-d96cd9e68134`

- 도메인: `CALC-TANGENT` · 발문형식: 단답형 · 정답형식: 실수 · 난이도: 3.3
- 성취기준: [12미적Ⅰ-02-01]

**문항**: 곡선 y = f(x) = x^3 + 12x^2 + 19x 위의 점 중 접선의 기울기가 -2인 점의 x좌표가 큰 것을 구하시오.

**정답**: `-1`

**풀이**: f(x)를 미분해 접선의 기울기 조건 f'(x) = -2를 정리하면 3(x + 7)(x + 1) = 0 이므로 접점의 x좌표는 x = -7, x = -1 이다. 이 중 x좌표가 큰 것은 -1이다.

**verify(SymPy 입력)**: conditions: `x**2 + 8*x + 7 = 0` · answer_map: {x=-1} · 근 선택: largest

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 115 · `wm-calc-tan-f881d5d5e835`

- 도메인: `CALC-TANGENT` · 발문형식: 단답형 · 정답형식: 자연수 · 난이도: 4
- 성취기준: [12미적Ⅰ-02-01]

**문항**: 함수 f(x) = x^3 + 3x^2 - 140x 의 그래프 위에서 접선의 기울기가 4인 두 점 중 x좌표가 큰 점의 x좌표를 구하시오.

**정답**: `6`

**풀이**: f(x)를 미분해 접선의 기울기 조건 f'(x) = 4를 정리하면 3(x + 8)(x - 6) = 0 이므로 접점의 x좌표는 x = -8, x = 6 이다. 이 중 x좌표가 큰 것은 6이다.

**verify(SymPy 입력)**: conditions: `x**2 + 2*x - 48 = 0` · answer_map: {x=6} · 근 선택: largest

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 116 · `wm-calc-tan-d3862f551f4d`

- 도메인: `CALC-TANGENT` · 발문형식: 단답형 · 정답형식: 자연수 · 난이도: 3.5
- 성취기준: [12미적Ⅰ-02-01]

**문항**: 함수 f(x) = x^3 - 18x^2 + 90x 의 그래프 위에서 접선의 기울기가 -6인 두 점 중 x좌표가 작은 점의 x좌표를 구하시오.

**정답**: `4`

**풀이**: f(x)를 미분해 접선의 기울기 조건 f'(x) = -6을 정리하면 3(x - 4)(x - 8) = 0 이므로 접점의 x좌표는 x = 4, x = 8 이다. 이 중 x좌표가 작은 것은 4이다.

**verify(SymPy 입력)**: conditions: `x**2 - 12*x + 32 = 0` · answer_map: {x=4} · 근 선택: smallest

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 117 · `wm-calc-extv-07d379e67ade`

- 도메인: `CALC-EXTREMUM-VALUE` · 발문형식: 단답형 · 정답형식: 자연수 · 난이도: 3.5
- 성취기준: [12미적Ⅰ-02-07]

**문항**: 함수 f(x) = x^3 - 18x^2 + 96x 의 극솟값을 구하시오.

**정답**: `128`

**풀이**: f'(x) = 3(x - 4)(x - 8) 이므로 f'(x)=0의 해는 x = 4, x = 8 이다. 삼차항의 계수가 양수라 x = 4에서 극대, x = 8에서 극소이다. 따라서 극솟값은 f(8) = 128 이다.

**verify(SymPy 입력)**: conditions: `x**2 - 288*x + 20480 = 0` · answer_map: {x=128} · 근 선택: smallest

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 118 · `wm-calc-extv-63eb524d2655`

- 도메인: `CALC-EXTREMUM-VALUE` · 발문형식: 단답형 · 정답형식: 실수 · 난이도: 3.5
- 성취기준: [12미적Ⅰ-02-07]

**문항**: 삼차함수 f(x) = x^3 + 24x^2 + 189x 의 극댓값을 구하시오.

**정답**: `-486`

**풀이**: f'(x) = 3(x + 9)(x + 7) 이므로 f'(x)=0의 해는 x = -9, x = -7 이다. 삼차항의 계수가 양수라 x = -9에서 극대, x = -7에서 극소이다. 따라서 극댓값은 f(-9) = -486 이다.

**verify(SymPy 입력)**: conditions: `x**2 + 976*x + 238140 = 0` · answer_map: {x=-486} · 근 선택: largest

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 119 · `wm-calc-extv-8fc0af95c0e6`

- 도메인: `CALC-EXTREMUM-VALUE` · 발문형식: 단답형 · 정답형식: 자연수 · 난이도: 4
- 성취기준: [12미적Ⅰ-02-07]

**문항**: 삼차함수 f(x) = x^3 + 3x^2 - 144x 의 극댓값을 구하시오.

**정답**: `832`

**풀이**: f'(x) = 3(x + 8)(x - 6) 이므로 f'(x)=0의 해는 x = -8, x = 6 이다. 삼차항의 계수가 양수라 x = -8에서 극대, x = 6에서 극소이다. 따라서 극댓값은 f(-8) = 832 이다.

**verify(SymPy 입력)**: conditions: `x**2 - 292*x - 449280 = 0` · answer_map: {x=832} · 근 선택: largest

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 120 · `wm-calc-extv-b75d75d7c302`

- 도메인: `CALC-EXTREMUM-VALUE` · 발문형식: 단답형 · 정답형식: 자연수 · 난이도: 3.6
- 성취기준: [12미적Ⅰ-02-07]

**문항**: 삼차함수 f(x) = x^3 + 3x^2 - 45x 의 극댓값을 구하시오.

**정답**: `175`

**풀이**: f'(x) = 3(x + 5)(x - 3) 이므로 f'(x)=0의 해는 x = -5, x = 3 이다. 삼차항의 계수가 양수라 x = -5에서 극대, x = 3에서 극소이다. 따라서 극댓값은 f(-5) = 175 이다.

**verify(SymPy 입력)**: conditions: `x**2 - 94*x - 14175 = 0` · answer_map: {x=175} · 근 선택: largest

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 121 · `wm-calc-extv-ad3c4e560894`

- 도메인: `CALC-EXTREMUM-VALUE` · 발문형식: 단답형 · 정답형식: 실수 · 난이도: 3.5
- 성취기준: [12미적Ⅰ-02-07]

**문항**: 삼차함수 f(x) = x^3 + 21x^2 + 144x 가 극대일 때, 그 극댓값을 구하시오.

**정답**: `-320`

**풀이**: f'(x) = 3(x + 8)(x + 6) 이므로 f'(x)=0의 해는 x = -8, x = -6 이다. 삼차항의 계수가 양수라 x = -8에서 극대, x = -6에서 극소이다. 따라서 극댓값은 f(-8) = -320 이다.

**verify(SymPy 입력)**: conditions: `x**2 + 644*x + 103680 = 0` · answer_map: {x=-320} · 근 선택: largest

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 122 · `wm-calc-extv-bbd706a72ad8`

- 도메인: `CALC-EXTREMUM-VALUE` · 발문형식: 단답형 · 정답형식: 실수 · 난이도: 3.8
- 성취기준: [12미적Ⅰ-02-07]

**문항**: 함수 f(x) = x^3 + 18x^2 + 81x 의 극댓값을 구하시오.

**정답**: `0`

**풀이**: f'(x) = 3(x + 9)(x + 3) 이므로 f'(x)=0의 해는 x = -9, x = -3 이다. 삼차항의 계수가 양수라 x = -9에서 극대, x = -3에서 극소이다. 따라서 극댓값은 f(-9) = 0 이다.

**verify(SymPy 입력)**: conditions: `x**2 + 108*x = 0` · answer_map: {x=0} · 근 선택: largest

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 123 · `wm-calc-extv-872a38b56215`

- 도메인: `CALC-EXTREMUM-VALUE` · 발문형식: 단답형 · 정답형식: 실수 · 난이도: 3.3
- 성취기준: [12미적Ⅰ-02-07]

**문항**: 함수 f(x) = x^3 + 12x^2 + 45x 의 극댓값을 구하시오.

**정답**: `-50`

**풀이**: f'(x) = 3(x + 5)(x + 3) 이므로 f'(x)=0의 해는 x = -5, x = -3 이다. 삼차항의 계수가 양수라 x = -5에서 극대, x = -3에서 극소이다. 따라서 극댓값은 f(-5) = -50 이다.

**verify(SymPy 입력)**: conditions: `x**2 + 104*x + 2700 = 0` · answer_map: {x=-50} · 근 선택: largest

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 124 · `wm-calc-extv-2ea729c9642f`

- 도메인: `CALC-EXTREMUM-VALUE` · 발문형식: 단답형 · 정답형식: 자연수 · 난이도: 3.3
- 성취기준: [12미적Ⅰ-02-07]

**문항**: 삼차함수 f(x) = x^3 - 12x^2 + 45x 가 극소일 때, 그 극솟값을 구하시오.

**정답**: `50`

**풀이**: f'(x) = 3(x - 3)(x - 5) 이므로 f'(x)=0의 해는 x = 3, x = 5 이다. 삼차항의 계수가 양수라 x = 3에서 극대, x = 5에서 극소이다. 따라서 극솟값은 f(5) = 50 이다.

**verify(SymPy 입력)**: conditions: `x**2 - 104*x + 2700 = 0` · answer_map: {x=50} · 근 선택: smallest

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 125 · `wm-calc-extv-bd21cd8484d2`

- 도메인: `CALC-EXTREMUM-VALUE` · 발문형식: 단답형 · 정답형식: 자연수 · 난이도: 3.5
- 성취기준: [12미적Ⅰ-02-07]

**문항**: 삼차함수 f(x) = x^3 + 12x^2 - 27x 의 극댓값을 구하시오.

**정답**: `486`

**풀이**: f'(x) = 3(x + 9)(x - 1) 이므로 f'(x)=0의 해는 x = -9, x = 1 이다. 삼차항의 계수가 양수라 x = -9에서 극대, x = 1에서 극소이다. 따라서 극댓값은 f(-9) = 486 이다.

**verify(SymPy 입력)**: conditions: `x**2 - 472*x - 6804 = 0` · answer_map: {x=486} · 근 선택: largest

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 126 · `wm-calc-extv-ca5069175637`

- 도메인: `CALC-EXTREMUM-VALUE` · 발문형식: 단답형 · 정답형식: 자연수 · 난이도: 4
- 성취기준: [12미적Ⅰ-02-07]

**문항**: 삼차함수 f(x) = x^3 - 3x^2 - 189x 가 극대일 때, 그 극댓값을 구하시오.

**정답**: `833`

**풀이**: f'(x) = 3(x + 7)(x - 9) 이므로 f'(x)=0의 해는 x = -7, x = 9 이다. 삼차항의 계수가 양수라 x = -7에서 극대, x = 9에서 극소이다. 따라서 극댓값은 f(-7) = 833 이다.

**verify(SymPy 입력)**: conditions: `x**2 + 382*x - 1012095 = 0` · answer_map: {x=833} · 근 선택: largest

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 127 · `wm-calc-extv-8efce1e63b5a`

- 도메인: `CALC-EXTREMUM-VALUE` · 발문형식: 단답형 · 정답형식: 자연수 · 난이도: 3.8
- 성취기준: [12미적Ⅰ-02-07]

**문항**: 함수 f(x) = x^3 + 9x^2 - 48x 의 극댓값을 구하시오.

**정답**: `448`

**풀이**: f'(x) = 3(x + 8)(x - 2) 이므로 f'(x)=0의 해는 x = -8, x = 2 이다. 삼차항의 계수가 양수라 x = -8에서 극대, x = 2에서 극소이다. 따라서 극댓값은 f(-8) = 448 이다.

**verify(SymPy 입력)**: conditions: `x**2 - 396*x - 23296 = 0` · answer_map: {x=448} · 근 선택: largest

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 128 · `wm-calc-extv-01f786ab766c`

- 도메인: `CALC-EXTREMUM-VALUE` · 발문형식: 단답형 · 정답형식: 실수 · 난이도: 4
- 성취기준: [12미적Ⅰ-02-07]

**문항**: 삼차함수 f(x) = x^3 + 3x^2 - 189x 의 극솟값을 구하시오.

**정답**: `-833`

**풀이**: f'(x) = 3(x + 9)(x - 7) 이므로 f'(x)=0의 해는 x = -9, x = 7 이다. 삼차항의 계수가 양수라 x = -9에서 극대, x = 7에서 극소이다. 따라서 극솟값은 f(7) = -833 이다.

**verify(SymPy 입력)**: conditions: `x**2 - 382*x - 1012095 = 0` · answer_map: {x=-833} · 근 선택: smallest

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 129 · `wm-calc-extv-8f82815640fd`

- 도메인: `CALC-EXTREMUM-VALUE` · 발문형식: 단답형 · 정답형식: 실수 · 난이도: 3.5
- 성취기준: [12미적Ⅰ-02-07]

**문항**: 삼차함수 f(x) = x^3 + 21x^2 + 135x 가 극대일 때, 그 극댓값을 구하시오.

**정답**: `-243`

**풀이**: f'(x) = 3(x + 9)(x + 5) 이므로 f'(x)=0의 해는 x = -9, x = -5 이다. 삼차항의 계수가 양수라 x = -9에서 극대, x = -5에서 극소이다. 따라서 극댓값은 f(-9) = -243 이다.

**verify(SymPy 입력)**: conditions: `x**2 + 518*x + 66825 = 0` · answer_map: {x=-243} · 근 선택: largest

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 130 · `wm-calc-extv-464c991d5f4e`

- 도메인: `CALC-EXTREMUM-VALUE` · 발문형식: 단답형 · 정답형식: 자연수 · 난이도: 3
- 성취기준: [12미적Ⅰ-02-07]

**문항**: 함수 f(x) = x^3 - 12x 의 극댓값을 구하시오.

**정답**: `16`

**풀이**: f'(x) = 3(x + 2)(x - 2) 이므로 f'(x)=0의 해는 x = -2, x = 2 이다. 삼차항의 계수가 양수라 x = -2에서 극대, x = 2에서 극소이다. 따라서 극댓값은 f(-2) = 16 이다.

**verify(SymPy 입력)**: conditions: `x**2 - 256 = 0` · answer_map: {x=16} · 근 선택: largest

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 131 · `wm-calc-extv-822223b26c89`

- 도메인: `CALC-EXTREMUM-VALUE` · 발문형식: 단답형 · 정답형식: 실수 · 난이도: 3.3
- 성취기준: [12미적Ⅰ-02-07]

**문항**: 함수 f(x) = x^3 + 9x^2 - 21x 의 극솟값을 구하시오.

**정답**: `-11`

**풀이**: f'(x) = 3(x + 7)(x - 1) 이므로 f'(x)=0의 해는 x = -7, x = 1 이다. 삼차항의 계수가 양수라 x = -7에서 극대, x = 1에서 극소이다. 따라서 극솟값은 f(1) = -11 이다.

**verify(SymPy 입력)**: conditions: `x**2 - 234*x - 2695 = 0` · answer_map: {x=-11} · 근 선택: smallest

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 132 · `wm-calc-extv-eb6ea17090c3`

- 도메인: `CALC-EXTREMUM-VALUE` · 발문형식: 단답형 · 정답형식: 실수 · 난이도: 3.6
- 성취기준: [12미적Ⅰ-02-07]

**문항**: 삼차함수 f(x) = x^3 - 3x^2 - 45x 의 극솟값을 구하시오.

**정답**: `-175`

**풀이**: f'(x) = 3(x + 3)(x - 5) 이므로 f'(x)=0의 해는 x = -3, x = 5 이다. 삼차항의 계수가 양수라 x = -3에서 극대, x = 5에서 극소이다. 따라서 극솟값은 f(5) = -175 이다.

**verify(SymPy 입력)**: conditions: `x**2 + 94*x - 14175 = 0` · answer_map: {x=-175} · 근 선택: smallest

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 133 · `wm-calc-extv-3eae62dfa946`

- 도메인: `CALC-EXTREMUM-VALUE` · 발문형식: 단답형 · 정답형식: 실수 · 난이도: 3.3
- 성취기준: [12미적Ⅰ-02-07]

**문항**: 삼차함수 f(x) = x^3 - 27x 가 극소일 때, 그 극솟값을 구하시오.

**정답**: `-54`

**풀이**: f'(x) = 3(x + 3)(x - 3) 이므로 f'(x)=0의 해는 x = -3, x = 3 이다. 삼차항의 계수가 양수라 x = -3에서 극대, x = 3에서 극소이다. 따라서 극솟값은 f(3) = -54 이다.

**verify(SymPy 입력)**: conditions: `x**2 - 2916 = 0` · answer_map: {x=-54} · 근 선택: smallest

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 134 · `wm-calc-extv-bd68970c82ea`

- 도메인: `CALC-EXTREMUM-VALUE` · 발문형식: 단답형 · 정답형식: 실수 · 난이도: 3.3
- 성취기준: [12미적Ⅰ-02-07]

**문항**: 삼차함수 f(x) = x^3 + 12x^2 + 36x 의 극솟값을 구하시오.

**정답**: `-32`

**풀이**: f'(x) = 3(x + 6)(x + 2) 이므로 f'(x)=0의 해는 x = -6, x = -2 이다. 삼차항의 계수가 양수라 x = -6에서 극대, x = -2에서 극소이다. 따라서 극솟값은 f(-2) = -32 이다.

**verify(SymPy 입력)**: conditions: `x**2 + 32*x = 0` · answer_map: {x=-32} · 근 선택: smallest

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 135 · `wm-calc-ext-29845e77d2d6`

- 도메인: `CALC-EXTREMUM` · 발문형식: 단답형 · 정답형식: 자연수 · 난이도: 3.3
- 성취기준: [12미적Ⅰ-02-07]

**문항**: 삼차함수 f(x) = x^3 - 6x^2 - 15x 가 극솟값을 가질 때, 그 x의 값을 구하시오.

**정답**: `5`

**풀이**: f'(x) = 3(x + 1)(x - 5) 이므로 f'(x)=0의 해는 x = -1, x = 5 이다. 삼차항의 계수가 양수라 x = -1에서 극대, x = 5에서 극소이다. 따라서 극솟값을 갖는 x는 5이다.

**verify(SymPy 입력)**: conditions: `x**2 - 4*x - 5 = 0` · answer_map: {x=5} · 근 선택: largest

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 136 · `wm-calc-ext-783de36f65d6`

- 도메인: `CALC-EXTREMUM` · 발문형식: 단답형 · 정답형식: 실수 · 난이도: 3
- 성취기준: [12미적Ⅰ-02-07]

**문항**: 삼차함수 f(x) = x^3 - 3x^2 - 9x 가 극댓값을 가질 때, 그 x의 값을 구하시오.

**정답**: `-1`

**풀이**: f'(x) = 3(x + 1)(x - 3) 이므로 f'(x)=0의 해는 x = -1, x = 3 이다. 삼차항의 계수가 양수라 x = -1에서 극대, x = 3에서 극소이다. 따라서 극댓값을 갖는 x는 -1이다.

**verify(SymPy 입력)**: conditions: `x**2 - 2*x - 3 = 0` · answer_map: {x=-1} · 근 선택: smallest

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 137 · `wm-calc-ext-921bf10f6940`

- 도메인: `CALC-EXTREMUM` · 발문형식: 단답형 · 정답형식: 자연수 · 난이도: 3.5
- 성취기준: [12미적Ⅰ-02-07]

**문항**: 삼차함수 f(x) = x^3 - 21x^2 + 135x 가 극댓값을 가질 때, 그 x의 값을 구하시오.

**정답**: `5`

**풀이**: f'(x) = 3(x - 5)(x - 9) 이므로 f'(x)=0의 해는 x = 5, x = 9 이다. 삼차항의 계수가 양수라 x = 5에서 극대, x = 9에서 극소이다. 따라서 극댓값을 갖는 x는 5이다.

**verify(SymPy 입력)**: conditions: `x**2 - 14*x + 45 = 0` · answer_map: {x=5} · 근 선택: smallest

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 138 · `wm-calc-ext-8c193941df77`

- 도메인: `CALC-EXTREMUM` · 발문형식: 단답형 · 정답형식: 자연수 · 난이도: 4
- 성취기준: [12미적Ⅰ-02-07]

**문항**: 삼차함수 f(x) = x^3 + 3x^2 - 144x 가 극소가 되는 x의 값을 구하시오.

**정답**: `6`

**풀이**: f'(x) = 3(x + 8)(x - 6) 이므로 f'(x)=0의 해는 x = -8, x = 6 이다. 삼차항의 계수가 양수라 x = -8에서 극대, x = 6에서 극소이다. 따라서 극솟값을 갖는 x는 6이다.

**verify(SymPy 입력)**: conditions: `x**2 + 2*x - 48 = 0` · answer_map: {x=6} · 근 선택: largest

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 139 · `wm-calc-ext-ec42f7239643`

- 도메인: `CALC-EXTREMUM` · 발문형식: 단답형 · 정답형식: 실수 · 난이도: 3.3
- 성취기준: [12미적Ⅰ-02-07]

**문항**: 함수 f(x) = x^3 + 12x^2 + 36x 가 극대가 되는 x의 값을 구하시오.

**정답**: `-6`

**풀이**: f'(x) = 3(x + 6)(x + 2) 이므로 f'(x)=0의 해는 x = -6, x = -2 이다. 삼차항의 계수가 양수라 x = -6에서 극대, x = -2에서 극소이다. 따라서 극댓값을 갖는 x는 -6이다.

**verify(SymPy 입력)**: conditions: `x**2 + 8*x + 12 = 0` · answer_map: {x=-6} · 근 선택: smallest

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 140 · `wm-calc-ext-d5e25343b112`

- 도메인: `CALC-EXTREMUM` · 발문형식: 단답형 · 정답형식: 실수 · 난이도: 3.5
- 성취기준: [12미적Ⅰ-02-07]

**문항**: 삼차함수 f(x) = x^3 + 12x^2 - 27x 가 극대가 되는 x의 값을 구하시오.

**정답**: `-9`

**풀이**: f'(x) = 3(x + 9)(x - 1) 이므로 f'(x)=0의 해는 x = -9, x = 1 이다. 삼차항의 계수가 양수라 x = -9에서 극대, x = 1에서 극소이다. 따라서 극댓값을 갖는 x는 -9이다.

**verify(SymPy 입력)**: conditions: `x**2 + 8*x - 9 = 0` · answer_map: {x=-9} · 근 선택: smallest

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 141 · `wm-calc-ext-33c602d14141`

- 도메인: `CALC-EXTREMUM` · 발문형식: 단답형 · 정답형식: 자연수 · 난이도: 3.6
- 성취기준: [12미적Ⅰ-02-07]

**문항**: 삼차함수 f(x) = x^3 - 3x^2 - 45x 가 극소가 되는 x의 값을 구하시오.

**정답**: `5`

**풀이**: f'(x) = 3(x + 3)(x - 5) 이므로 f'(x)=0의 해는 x = -3, x = 5 이다. 삼차항의 계수가 양수라 x = -3에서 극대, x = 5에서 극소이다. 따라서 극솟값을 갖는 x는 5이다.

**verify(SymPy 입력)**: conditions: `x**2 - 2*x - 15 = 0` · answer_map: {x=5} · 근 선택: largest

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 142 · `wm-calc-ext-d69248ab9f5b`

- 도메인: `CALC-EXTREMUM` · 발문형식: 단답형 · 정답형식: 자연수 · 난이도: 3.6
- 성취기준: [12미적Ⅰ-02-07]

**문항**: 삼차함수 f(x) = x^3 + 3x^2 - 45x 가 극소가 되는 x의 값을 구하시오.

**정답**: `3`

**풀이**: f'(x) = 3(x + 5)(x - 3) 이므로 f'(x)=0의 해는 x = -5, x = 3 이다. 삼차항의 계수가 양수라 x = -5에서 극대, x = 3에서 극소이다. 따라서 극솟값을 갖는 x는 3이다.

**verify(SymPy 입력)**: conditions: `x**2 + 2*x - 15 = 0` · answer_map: {x=3} · 근 선택: largest

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 143 · `wm-calc-ext-5b3ba7bc4a54`

- 도메인: `CALC-EXTREMUM` · 발문형식: 단답형 · 정답형식: 실수 · 난이도: 3.3
- 성취기준: [12미적Ⅰ-02-07]

**문항**: 삼차함수 f(x) = x^3 + 15x^2 + 27x 가 극대가 되는 x의 값을 구하시오.

**정답**: `-9`

**풀이**: f'(x) = 3(x + 9)(x + 1) 이므로 f'(x)=0의 해는 x = -9, x = -1 이다. 삼차항의 계수가 양수라 x = -9에서 극대, x = -1에서 극소이다. 따라서 극댓값을 갖는 x는 -9이다.

**verify(SymPy 입력)**: conditions: `x**2 + 10*x + 9 = 0` · answer_map: {x=-9} · 근 선택: smallest

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 144 · `wm-calc-ext-ede0a1159929`

- 도메인: `CALC-EXTREMUM` · 발문형식: 단답형 · 정답형식: 자연수 · 난이도: 3.8
- 성취기준: [12미적Ⅰ-02-07]

**문항**: 함수 f(x) = x^3 + 9x^2 - 48x 가 극소가 되는 x의 값을 구하시오.

**정답**: `2`

**풀이**: f'(x) = 3(x + 8)(x - 2) 이므로 f'(x)=0의 해는 x = -8, x = 2 이다. 삼차항의 계수가 양수라 x = -8에서 극대, x = 2에서 극소이다. 따라서 극솟값을 갖는 x는 2이다.

**verify(SymPy 입력)**: conditions: `x**2 + 6*x - 16 = 0` · answer_map: {x=2} · 근 선택: largest

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 145 · `wm-calc-ext-a677addfed9d`

- 도메인: `CALC-EXTREMUM` · 발문형식: 단답형 · 정답형식: 실수 · 난이도: 3.6
- 성취기준: [12미적Ⅰ-02-07]

**문항**: 함수 f(x) = x^3 - 48x 가 극대가 되는 x의 값을 구하시오.

**정답**: `-4`

**풀이**: f'(x) = 3(x + 4)(x - 4) 이므로 f'(x)=0의 해는 x = -4, x = 4 이다. 삼차항의 계수가 양수라 x = -4에서 극대, x = 4에서 극소이다. 따라서 극댓값을 갖는 x는 -4이다.

**verify(SymPy 입력)**: conditions: `x**2 - 16 = 0` · answer_map: {x=-4} · 근 선택: smallest

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 146 · `wm-calc-ext-ea6416ffa632`

- 도메인: `CALC-EXTREMUM` · 발문형식: 단답형 · 정답형식: 실수 · 난이도: 3.5
- 성취기준: [12미적Ⅰ-02-07]

**문항**: 함수 f(x) = x^3 + 21x^2 + 135x 가 극대가 되는 x의 값을 구하시오.

**정답**: `-9`

**풀이**: f'(x) = 3(x + 9)(x + 5) 이므로 f'(x)=0의 해는 x = -9, x = -5 이다. 삼차항의 계수가 양수라 x = -9에서 극대, x = -5에서 극소이다. 따라서 극댓값을 갖는 x는 -9이다.

**verify(SymPy 입력)**: conditions: `x**2 + 14*x + 45 = 0` · answer_map: {x=-9} · 근 선택: smallest

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 147 · `wm-calc-ext-139f4f98bdcc`

- 도메인: `CALC-EXTREMUM` · 발문형식: 단답형 · 정답형식: 자연수 · 난이도: 3.3
- 성취기준: [12미적Ⅰ-02-07]

**문항**: 함수 f(x) = x^3 + 9x^2 - 21x 가 극소가 되는 x의 값을 구하시오.

**정답**: `1`

**풀이**: f'(x) = 3(x + 7)(x - 1) 이므로 f'(x)=0의 해는 x = -7, x = 1 이다. 삼차항의 계수가 양수라 x = -7에서 극대, x = 1에서 극소이다. 따라서 극솟값을 갖는 x는 1이다.

**verify(SymPy 입력)**: conditions: `x**2 + 6*x - 7 = 0` · answer_map: {x=1} · 근 선택: largest

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 148 · `wm-calc-ext-3dcd4f4357bb`

- 도메인: `CALC-EXTREMUM` · 발문형식: 단답형 · 정답형식: 실수 · 난이도: 3.3
- 성취기준: [12미적Ⅰ-02-07]

**문항**: 삼차함수 f(x) = x^3 + 3x^2 - 24x 가 극댓값을 가질 때, 그 x의 값을 구하시오.

**정답**: `-4`

**풀이**: f'(x) = 3(x + 4)(x - 2) 이므로 f'(x)=0의 해는 x = -4, x = 2 이다. 삼차항의 계수가 양수라 x = -4에서 극대, x = 2에서 극소이다. 따라서 극댓값을 갖는 x는 -4이다.

**verify(SymPy 입력)**: conditions: `x**2 + 2*x - 8 = 0` · answer_map: {x=-4} · 근 선택: smallest

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 149 · `wm-calc-ext-846a6b3b83b5`

- 도메인: `CALC-EXTREMUM` · 발문형식: 단답형 · 정답형식: 자연수 · 난이도: 4
- 성취기준: [12미적Ⅰ-02-07]

**문항**: 함수 f(x) = x^3 + 6x^2 - 96x 가 극소가 되는 x의 값을 구하시오.

**정답**: `4`

**풀이**: f'(x) = 3(x + 8)(x - 4) 이므로 f'(x)=0의 해는 x = -8, x = 4 이다. 삼차항의 계수가 양수라 x = -8에서 극대, x = 4에서 극소이다. 따라서 극솟값을 갖는 x는 4이다.

**verify(SymPy 입력)**: conditions: `x**2 + 4*x - 32 = 0` · answer_map: {x=4} · 근 선택: largest

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 150 · `wm-calc-ext-35363f4e2a30`

- 도메인: `CALC-EXTREMUM` · 발문형식: 단답형 · 정답형식: 실수 · 난이도: 3.5
- 성취기준: [12미적Ⅰ-02-07]

**문항**: 함수 f(x) = x^3 + 21x^2 + 144x 가 극소가 되는 x의 값을 구하시오.

**정답**: `-6`

**풀이**: f'(x) = 3(x + 8)(x + 6) 이므로 f'(x)=0의 해는 x = -8, x = -6 이다. 삼차항의 계수가 양수라 x = -8에서 극대, x = -6에서 극소이다. 따라서 극솟값을 갖는 x는 -6이다.

**verify(SymPy 입력)**: conditions: `x**2 + 14*x + 48 = 0` · answer_map: {x=-6} · 근 선택: largest

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 151 · `wm-calc-ext-729ae5cf983d`

- 도메인: `CALC-EXTREMUM` · 발문형식: 단답형 · 정답형식: 실수 · 난이도: 3.3
- 성취기준: [12미적Ⅰ-02-07]

**문항**: 삼차함수 f(x) = x^3 - 3x^2 - 24x 가 극댓값을 가질 때, 그 x의 값을 구하시오.

**정답**: `-2`

**풀이**: f'(x) = 3(x + 2)(x - 4) 이므로 f'(x)=0의 해는 x = -2, x = 4 이다. 삼차항의 계수가 양수라 x = -2에서 극대, x = 4에서 극소이다. 따라서 극댓값을 갖는 x는 -2이다.

**verify(SymPy 입력)**: conditions: `x**2 - 2*x - 8 = 0` · answer_map: {x=-2} · 근 선택: smallest

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 152 · `wm-calc-extmc-465d85d35ae5`

- 도메인: `CALC-EXTREMUM-MC` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.3
- 성취기준: [12미적Ⅰ-02-07]

**문항**: 함수 f(x) = x^3 + 9x^2 - 21x 의 극댓값으로 옳은 것을 고르시오.

**정답**: `245`

**풀이**: f'(x) = 3(x + 7)(x - 1) 이므로 f'(x)=0의 해는 x = -7, x = 1 이다. 삼차항의 계수가 양수라 x = -7에서 극대, x = 1에서 극소이다. 따라서 극댓값은 f(-7) = 245 이다.

**verify(SymPy 입력)**: conditions: `x**2 - 234*x - 2695 = 0` · answer_map: {x=245} · 근 선택: largest

**선지**:
- ① `-11` ← 오답 · 오개념 `extremum-max-min-confused` (op: `select-opposite-extremum`)
- ② `-7` ← 오답 · 오개념 `extremum-value-vs-point-confused` (op: `report-x-coordinate-for-value`)
- ③ `1` ← 오답 · 오개념 `extremum-value-vs-point-confused` (op: `report-x-coordinate-for-value`)
- ④ `245` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- [ ] ⑤ 오답↔오개념 귀속 타당(선지별 오개념·op-code)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 153 · `wm-calc-extmc-803cec54fad3`

- 도메인: `CALC-EXTREMUM-MC` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.3
- 성취기준: [12미적Ⅰ-02-07]

**문항**: 함수 f(x) = x^3 + 6x^2 - 15x 의 극댓값으로 옳은 것을 고르시오.

**정답**: `100`

**풀이**: f'(x) = 3(x + 5)(x - 1) 이므로 f'(x)=0의 해는 x = -5, x = 1 이다. 삼차항의 계수가 양수라 x = -5에서 극대, x = 1에서 극소이다. 따라서 극댓값은 f(-5) = 100 이다.

**verify(SymPy 입력)**: conditions: `x**2 - 92*x - 800 = 0` · answer_map: {x=100} · 근 선택: largest

**선지**:
- ① `-8` ← 오답 · 오개념 `extremum-max-min-confused` (op: `select-opposite-extremum`)
- ② `-5` ← 오답 · 오개념 `extremum-value-vs-point-confused` (op: `report-x-coordinate-for-value`)
- ③ `1` ← 오답 · 오개념 `extremum-value-vs-point-confused` (op: `report-x-coordinate-for-value`)
- ④ `100` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- [ ] ⑤ 오답↔오개념 귀속 타당(선지별 오개념·op-code)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 154 · `wm-calc-extmc-5b267b4c7886`

- 도메인: `CALC-EXTREMUM-MC` · 발문형식: 객관식 · 정답형식: 실수 · 난이도: 3.8
- 성취기준: [12미적Ⅰ-02-07]

**문항**: 삼차함수 f(x) = x^3 + 3x^2 - 72x 의 극솟값을 구하시오.

**정답**: `-176`

**풀이**: f'(x) = 3(x + 6)(x - 4) 이므로 f'(x)=0의 해는 x = -6, x = 4 이다. 삼차항의 계수가 양수라 x = -6에서 극대, x = 4에서 극소이다. 따라서 극솟값은 f(4) = -176 이다.

**verify(SymPy 입력)**: conditions: `x**2 - 148*x - 57024 = 0` · answer_map: {x=-176} · 근 선택: smallest

**선지**:
- ① `-176` ← 정답
- ② `-6` ← 오답 · 오개념 `extremum-value-vs-point-confused` (op: `report-x-coordinate-for-value`)
- ③ `4` ← 오답 · 오개념 `extremum-value-vs-point-confused` (op: `report-x-coordinate-for-value`)
- ④ `324` ← 오답 · 오개념 `extremum-max-min-confused` (op: `select-opposite-extremum`)

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- [ ] ⑤ 오답↔오개념 귀속 타당(선지별 오개념·op-code)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 155 · `wm-calc-extmc-cf788e51e0fd`

- 도메인: `CALC-EXTREMUM-MC` · 발문형식: 객관식 · 정답형식: 실수 · 난이도: 3.5
- 성취기준: [12미적Ⅰ-02-07]

**문항**: 삼차함수 f(x) = x^3 + 18x^2 + 96x 의 극댓값을 구하시오.

**정답**: `-128`

**풀이**: f'(x) = 3(x + 8)(x + 4) 이므로 f'(x)=0의 해는 x = -8, x = -4 이다. 삼차항의 계수가 양수라 x = -8에서 극대, x = -4에서 극소이다. 따라서 극댓값은 f(-8) = -128 이다.

**verify(SymPy 입력)**: conditions: `x**2 + 288*x + 20480 = 0` · answer_map: {x=-128} · 근 선택: largest

**선지**:
- ① `-160` ← 오답 · 오개념 `extremum-max-min-confused` (op: `select-opposite-extremum`)
- ② `-128` ← 정답
- ③ `-8` ← 오답 · 오개념 `extremum-value-vs-point-confused` (op: `report-x-coordinate-for-value`)
- ④ `-4` ← 오답 · 오개념 `extremum-value-vs-point-confused` (op: `report-x-coordinate-for-value`)

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- [ ] ⑤ 오답↔오개념 귀속 타당(선지별 오개념·op-code)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 156 · `wm-calc-extmc-2e23148010b0`

- 도메인: `CALC-EXTREMUM-MC` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 4
- 성취기준: [12미적Ⅰ-02-07]

**문항**: 함수 f(x) = x^3 - 3x^2 - 105x 의 극댓값으로 옳은 것을 고르시오.

**정답**: `325`

**풀이**: f'(x) = 3(x + 5)(x - 7) 이므로 f'(x)=0의 해는 x = -5, x = 7 이다. 삼차항의 계수가 양수라 x = -5에서 극대, x = 7에서 극소이다. 따라서 극댓값은 f(-5) = 325 이다.

**verify(SymPy 입력)**: conditions: `x**2 + 214*x - 175175 = 0` · answer_map: {x=325} · 근 선택: largest

**선지**:
- ① `-539` ← 오답 · 오개념 `extremum-max-min-confused` (op: `select-opposite-extremum`)
- ② `-5` ← 오답 · 오개념 `extremum-value-vs-point-confused` (op: `report-x-coordinate-for-value`)
- ③ `7` ← 오답 · 오개념 `extremum-value-vs-point-confused` (op: `report-x-coordinate-for-value`)
- ④ `325` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- [ ] ⑤ 오답↔오개념 귀속 타당(선지별 오개념·op-code)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 157 · `wm-calc-extmc-138cb0cd2aba`

- 도메인: `CALC-EXTREMUM-MC` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 4
- 성취기준: [12미적Ⅰ-02-07]

**문항**: 함수 f(x) = x^3 - 192x 의 극댓값으로 옳은 것을 고르시오.

**정답**: `1024`

**풀이**: f'(x) = 3(x + 8)(x - 8) 이므로 f'(x)=0의 해는 x = -8, x = 8 이다. 삼차항의 계수가 양수라 x = -8에서 극대, x = 8에서 극소이다. 따라서 극댓값은 f(-8) = 1024 이다.

**verify(SymPy 입력)**: conditions: `x**2 - 1048576 = 0` · answer_map: {x=1024} · 근 선택: largest

**선지**:
- ① `-1024` ← 오답 · 오개념 `extremum-max-min-confused` (op: `select-opposite-extremum`)
- ② `-8` ← 오답 · 오개념 `extremum-value-vs-point-confused` (op: `report-x-coordinate-for-value`)
- ③ `8` ← 오답 · 오개념 `extremum-value-vs-point-confused` (op: `report-x-coordinate-for-value`)
- ④ `1024` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- [ ] ⑤ 오답↔오개념 귀속 타당(선지별 오개념·op-code)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 158 · `wm-calc-extmc-0c9e8d8b0b06`

- 도메인: `CALC-EXTREMUM-MC` · 발문형식: 객관식 · 정답형식: 실수 · 난이도: 3.5
- 성취기준: [12미적Ⅰ-02-07]

**문항**: 함수 f(x) = x^3 + 24x^2 + 189x 의 극댓값으로 옳은 것을 고르시오.

**정답**: `-486`

**풀이**: f'(x) = 3(x + 9)(x + 7) 이므로 f'(x)=0의 해는 x = -9, x = -7 이다. 삼차항의 계수가 양수라 x = -9에서 극대, x = -7에서 극소이다. 따라서 극댓값은 f(-9) = -486 이다.

**verify(SymPy 입력)**: conditions: `x**2 + 976*x + 238140 = 0` · answer_map: {x=-486} · 근 선택: largest

**선지**:
- ① `-490` ← 오답 · 오개념 `extremum-max-min-confused` (op: `select-opposite-extremum`)
- ② `-486` ← 정답
- ③ `-9` ← 오답 · 오개념 `extremum-value-vs-point-confused` (op: `report-x-coordinate-for-value`)
- ④ `-7` ← 오답 · 오개념 `extremum-value-vs-point-confused` (op: `report-x-coordinate-for-value`)

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- [ ] ⑤ 오답↔오개념 귀속 타당(선지별 오개념·op-code)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 159 · `wm-calc-extmc-8fc0433707f2`

- 도메인: `CALC-EXTREMUM-MC` · 발문형식: 객관식 · 정답형식: 실수 · 난이도: 3.5
- 성취기준: [12미적Ⅰ-02-07]

**문항**: 삼차함수 f(x) = x^3 + 21x^2 + 135x 의 극댓값을 구하시오.

**정답**: `-243`

**풀이**: f'(x) = 3(x + 9)(x + 5) 이므로 f'(x)=0의 해는 x = -9, x = -5 이다. 삼차항의 계수가 양수라 x = -9에서 극대, x = -5에서 극소이다. 따라서 극댓값은 f(-9) = -243 이다.

**verify(SymPy 입력)**: conditions: `x**2 + 518*x + 66825 = 0` · answer_map: {x=-243} · 근 선택: largest

**선지**:
- ① `-275` ← 오답 · 오개념 `extremum-max-min-confused` (op: `select-opposite-extremum`)
- ② `-243` ← 정답
- ③ `-9` ← 오답 · 오개념 `extremum-value-vs-point-confused` (op: `report-x-coordinate-for-value`)
- ④ `-5` ← 오답 · 오개념 `extremum-value-vs-point-confused` (op: `report-x-coordinate-for-value`)

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- [ ] ⑤ 오답↔오개념 귀속 타당(선지별 오개념·op-code)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 160 · `wm-calc-extmc-3ccc6c8c3b7c`

- 도메인: `CALC-EXTREMUM-MC` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.3
- 성취기준: [12미적Ⅰ-02-07]

**문항**: 함수 f(x) = x^3 + 15x^2 + 27x 의 극댓값으로 옳은 것을 고르시오.

**정답**: `243`

**풀이**: f'(x) = 3(x + 9)(x + 1) 이므로 f'(x)=0의 해는 x = -9, x = -1 이다. 삼차항의 계수가 양수라 x = -9에서 극대, x = -1에서 극소이다. 따라서 극댓값은 f(-9) = 243 이다.

**verify(SymPy 입력)**: conditions: `x**2 - 230*x - 3159 = 0` · answer_map: {x=243} · 근 선택: largest

**선지**:
- ① `-13` ← 오답 · 오개념 `extremum-max-min-confused` (op: `select-opposite-extremum`)
- ② `-9` ← 오답 · 오개념 `extremum-value-vs-point-confused` (op: `report-x-coordinate-for-value`)
- ③ `-1` ← 오답 · 오개념 `extremum-value-vs-point-confused` (op: `report-x-coordinate-for-value`)
- ④ `243` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- [ ] ⑤ 오답↔오개념 귀속 타당(선지별 오개념·op-code)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 161 · `wm-calc-extmc-29126bd4a86a`

- 도메인: `CALC-EXTREMUM-MC` · 발문형식: 객관식 · 정답형식: 실수 · 난이도: 3.3
- 성취기준: [12미적Ⅰ-02-07]

**문항**: 함수 f(x) = x^3 + 3x^2 - 24x 의 극솟값으로 옳은 것을 고르시오.

**정답**: `-28`

**풀이**: f'(x) = 3(x + 4)(x - 2) 이므로 f'(x)=0의 해는 x = -4, x = 2 이다. 삼차항의 계수가 양수라 x = -4에서 극대, x = 2에서 극소이다. 따라서 극솟값은 f(2) = -28 이다.

**verify(SymPy 입력)**: conditions: `x**2 - 52*x - 2240 = 0` · answer_map: {x=-28} · 근 선택: smallest

**선지**:
- ① `-28` ← 정답
- ② `-4` ← 오답 · 오개념 `extremum-value-vs-point-confused` (op: `report-x-coordinate-for-value`)
- ③ `2` ← 오답 · 오개념 `extremum-value-vs-point-confused` (op: `report-x-coordinate-for-value`)
- ④ `80` ← 오답 · 오개념 `extremum-max-min-confused` (op: `select-opposite-extremum`)

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- [ ] ⑤ 오답↔오개념 귀속 타당(선지별 오개념·op-code)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 162 · `wm-calc-extmc-588713791a72`

- 도메인: `CALC-EXTREMUM-MC` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.5
- 성취기준: [12미적Ⅰ-02-07]

**문항**: 함수 f(x) = x^3 - 21x^2 + 135x 의 극댓값으로 옳은 것을 고르시오.

**정답**: `275`

**풀이**: f'(x) = 3(x - 5)(x - 9) 이므로 f'(x)=0의 해는 x = 5, x = 9 이다. 삼차항의 계수가 양수라 x = 5에서 극대, x = 9에서 극소이다. 따라서 극댓값은 f(5) = 275 이다.

**verify(SymPy 입력)**: conditions: `x**2 - 518*x + 66825 = 0` · answer_map: {x=275} · 근 선택: largest

**선지**:
- ① `5` ← 오답 · 오개념 `extremum-value-vs-point-confused` (op: `report-x-coordinate-for-value`)
- ② `9` ← 오답 · 오개념 `extremum-value-vs-point-confused` (op: `report-x-coordinate-for-value`)
- ③ `243` ← 오답 · 오개념 `extremum-max-min-confused` (op: `select-opposite-extremum`)
- ④ `275` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- [ ] ⑤ 오답↔오개념 귀속 타당(선지별 오개념·op-code)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 163 · `wm-calc-extmc-b372dc859175`

- 도메인: `CALC-EXTREMUM-MC` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3
- 성취기준: [12미적Ⅰ-02-07]

**문항**: 삼차함수 f(x) = x^3 - 12x 의 극댓값을 구하시오.

**정답**: `16`

**풀이**: f'(x) = 3(x + 2)(x - 2) 이므로 f'(x)=0의 해는 x = -2, x = 2 이다. 삼차항의 계수가 양수라 x = -2에서 극대, x = 2에서 극소이다. 따라서 극댓값은 f(-2) = 16 이다.

**verify(SymPy 입력)**: conditions: `x**2 - 256 = 0` · answer_map: {x=16} · 근 선택: largest

**선지**:
- ① `-16` ← 오답 · 오개념 `extremum-max-min-confused` (op: `select-opposite-extremum`)
- ② `-2` ← 오답 · 오개념 `extremum-value-vs-point-confused` (op: `report-x-coordinate-for-value`)
- ③ `2` ← 오답 · 오개념 `extremum-value-vs-point-confused` (op: `report-x-coordinate-for-value`)
- ④ `16` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- [ ] ⑤ 오답↔오개념 귀속 타당(선지별 오개념·op-code)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 164 · `wm-calc-extmc-81f6ef54ef34`

- 도메인: `CALC-EXTREMUM-MC` · 발문형식: 객관식 · 정답형식: 실수 · 난이도: 3
- 성취기준: [12미적Ⅰ-02-07]

**문항**: 삼차함수 f(x) = x^3 - 9x^2 + 15x 의 극솟값을 구하시오.

**정답**: `-25`

**풀이**: f'(x) = 3(x - 1)(x - 5) 이므로 f'(x)=0의 해는 x = 1, x = 5 이다. 삼차항의 계수가 양수라 x = 1에서 극대, x = 5에서 극소이다. 따라서 극솟값은 f(5) = -25 이다.

**verify(SymPy 입력)**: conditions: `x**2 + 18*x - 175 = 0` · answer_map: {x=-25} · 근 선택: smallest

**선지**:
- ① `-25` ← 정답
- ② `1` ← 오답 · 오개념 `extremum-value-vs-point-confused` (op: `report-x-coordinate-for-value`)
- ③ `5` ← 오답 · 오개념 `extremum-value-vs-point-confused` (op: `report-x-coordinate-for-value`)
- ④ `7` ← 오답 · 오개념 `extremum-max-min-confused` (op: `select-opposite-extremum`)

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- [ ] ⑤ 오답↔오개념 귀속 타당(선지별 오개념·op-code)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 165 · `wm-calc-extmc-a24fb5c74aa4`

- 도메인: `CALC-EXTREMUM-MC` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 4
- 성취기준: [12미적Ⅰ-02-07]

**문항**: 함수 f(x) = x^3 + 6x^2 - 96x 의 극댓값으로 옳은 것을 고르시오.

**정답**: `640`

**풀이**: f'(x) = 3(x + 8)(x - 4) 이므로 f'(x)=0의 해는 x = -8, x = 4 이다. 삼차항의 계수가 양수라 x = -8에서 극대, x = 4에서 극소이다. 따라서 극댓값은 f(-8) = 640 이다.

**verify(SymPy 입력)**: conditions: `x**2 - 416*x - 143360 = 0` · answer_map: {x=640} · 근 선택: largest

**선지**:
- ① `-224` ← 오답 · 오개념 `extremum-max-min-confused` (op: `select-opposite-extremum`)
- ② `-8` ← 오답 · 오개념 `extremum-value-vs-point-confused` (op: `report-x-coordinate-for-value`)
- ③ `4` ← 오답 · 오개념 `extremum-value-vs-point-confused` (op: `report-x-coordinate-for-value`)
- ④ `640` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- [ ] ⑤ 오답↔오개념 귀속 타당(선지별 오개념·op-code)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 166 · `wm-geseq-e9ded22ec0ce`

- 도메인: `GEO-SEQ` · 발문형식: 단답형 · 정답형식: 자연수 · 난이도: 1.7
- 성취기준: [12대수03-03]

**문항**: 등비수열 {aₙ}의 첫째항이 2이고 공비가 3일 때, 제5항을 구하시오.

**정답**: `162`

**풀이**: 등비수열의 제n항은 첫째항에 공비를 (n−1)번 곱한 값이므로, 제5항은 162 이다.

**verify(SymPy 입력)**: conditions: `x - (2 * 3**(5 - 1)) = 0` · answer_map: {x=162} · 근 선택: unique

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 167 · `wm-geseq-e00a9dc7f844`

- 도메인: `GEO-SEQ` · 발문형식: 단답형 · 정답형식: 자연수 · 난이도: 1.7
- 성취기준: [12대수03-03]

**문항**: 첫째항이 3, 공비가 2인 등비수열의 제3항을 구하시오.

**정답**: `12`

**풀이**: 등비수열의 제n항은 첫째항에 공비를 (n−1)번 곱한 값이므로, 제3항은 12 이다.

**verify(SymPy 입력)**: conditions: `x - (3 * 2**(3 - 1)) = 0` · answer_map: {x=12} · 근 선택: unique

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 168 · `wm-geseq-4cde5745b9f4`

- 도메인: `GEO-SEQ` · 발문형식: 단답형 · 정답형식: 자연수 · 난이도: 1.7
- 성취기준: [12대수03-03]

**문항**: 첫째항 2, 공비 3인 등비수열에서 4번째 항의 값을 구하시오.

**정답**: `54`

**풀이**: 등비수열의 제n항은 첫째항에 공비를 (n−1)번 곱한 값이므로, 제4항은 54 이다.

**verify(SymPy 입력)**: conditions: `x - (2 * 3**(4 - 1)) = 0` · answer_map: {x=54} · 근 선택: unique

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 169 · `wm-geseq-005a1c017864`

- 도메인: `GEO-SEQ` · 발문형식: 단답형 · 정답형식: 자연수 · 난이도: 2
- 성취기준: [12대수03-03]

**문항**: 등비수열 {aₙ}의 첫째항이 2이고 공비가 3일 때, 제6항을 구하시오.

**정답**: `486`

**풀이**: 등비수열의 제n항은 첫째항에 공비를 (n−1)번 곱한 값이므로, 제6항은 486 이다.

**verify(SymPy 입력)**: conditions: `x - (2 * 3**(6 - 1)) = 0` · answer_map: {x=486} · 근 선택: unique

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 170 · `wm-geseq-cf7244855e39`

- 도메인: `GEO-SEQ` · 발문형식: 단답형 · 정답형식: 자연수 · 난이도: 1.9
- 성취기준: [12대수03-03]

**문항**: 등비수열 {aₙ}의 첫째항이 3이고 공비가 2일 때, 제6항을 구하시오.

**정답**: `96`

**풀이**: 등비수열의 제n항은 첫째항에 공비를 (n−1)번 곱한 값이므로, 제6항은 96 이다.

**verify(SymPy 입력)**: conditions: `x - (3 * 2**(6 - 1)) = 0` · answer_map: {x=96} · 근 선택: unique

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 171 · `wm-geseq-76a217a5bac3`

- 도메인: `GEO-SEQ` · 발문형식: 단답형 · 정답형식: 자연수 · 난이도: 1.9
- 성취기준: [12대수03-03]

**문항**: 첫째항 1, 공비 5인 등비수열에서 3번째 항의 값을 구하시오.

**정답**: `25`

**풀이**: 등비수열의 제n항은 첫째항에 공비를 (n−1)번 곱한 값이므로, 제3항은 25 이다.

**verify(SymPy 입력)**: conditions: `x - (1 * 5**(3 - 1)) = 0` · answer_map: {x=25} · 근 선택: unique

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 172 · `wm-geseq-d50bd54b7ce0`

- 도메인: `GEO-SEQ` · 발문형식: 단답형 · 정답형식: 자연수 · 난이도: 1.7
- 성취기준: [12대수03-03]

**문항**: 등비수열 {aₙ}의 첫째항이 3이고 공비가 2일 때, 제5항을 구하시오.

**정답**: `48`

**풀이**: 등비수열의 제n항은 첫째항에 공비를 (n−1)번 곱한 값이므로, 제5항은 48 이다.

**verify(SymPy 입력)**: conditions: `x - (3 * 2**(5 - 1)) = 0` · answer_map: {x=48} · 근 선택: unique

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 173 · `wm-geseq-cc22267ef882`

- 도메인: `GEO-SEQ` · 발문형식: 단답형 · 정답형식: 자연수 · 난이도: 2
- 성취기준: [12대수03-03]

**문항**: 첫째항 2, 공비 5인 등비수열에서 4번째 항의 값을 구하시오.

**정답**: `250`

**풀이**: 등비수열의 제n항은 첫째항에 공비를 (n−1)번 곱한 값이므로, 제4항은 250 이다.

**verify(SymPy 입력)**: conditions: `x - (2 * 5**(4 - 1)) = 0` · answer_map: {x=250} · 근 선택: unique

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 174 · `wm-geseq-9158d6986c00`

- 도메인: `GEO-SEQ` · 발문형식: 단답형 · 정답형식: 자연수 · 난이도: 2
- 성취기준: [12대수03-03]

**문항**: 첫째항이 5, 공비가 2인 등비수열의 제7항을 구하시오.

**정답**: `320`

**풀이**: 등비수열의 제n항은 첫째항에 공비를 (n−1)번 곱한 값이므로, 제7항은 320 이다.

**verify(SymPy 입력)**: conditions: `x - (5 * 2**(7 - 1)) = 0` · answer_map: {x=320} · 근 선택: unique

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 175 · `wm-geseq-4e744367bd4b`

- 도메인: `GEO-SEQ` · 발문형식: 단답형 · 정답형식: 자연수 · 난이도: 2
- 성취기준: [12대수03-03]

**문항**: 첫째항 1, 공비 5인 등비수열에서 5번째 항의 값을 구하시오.

**정답**: `625`

**풀이**: 등비수열의 제n항은 첫째항에 공비를 (n−1)번 곱한 값이므로, 제5항은 625 이다.

**verify(SymPy 입력)**: conditions: `x - (1 * 5**(5 - 1)) = 0` · answer_map: {x=625} · 근 선택: unique

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 176 · `wm-geseq-4e69fbfa9c94`

- 도메인: `GEO-SEQ` · 발문형식: 단답형 · 정답형식: 자연수 · 난이도: 1.7
- 성취기준: [12대수03-03]

**문항**: 첫째항이 3, 공비가 2인 등비수열의 제4항을 구하시오.

**정답**: `24`

**풀이**: 등비수열의 제n항은 첫째항에 공비를 (n−1)번 곱한 값이므로, 제4항은 24 이다.

**verify(SymPy 입력)**: conditions: `x - (3 * 2**(4 - 1)) = 0` · answer_map: {x=24} · 근 선택: unique

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 177 · `wm-geseq-846c1a304a75`

- 도메인: `GEO-SEQ` · 발문형식: 단답형 · 정답형식: 자연수 · 난이도: 1.8
- 성취기준: [12대수03-03]

**문항**: 등비수열 {aₙ}의 첫째항이 4이고 공비가 3일 때, 제5항을 구하시오.

**정답**: `324`

**풀이**: 등비수열의 제n항은 첫째항에 공비를 (n−1)번 곱한 값이므로, 제5항은 324 이다.

**verify(SymPy 입력)**: conditions: `x - (4 * 3**(5 - 1)) = 0` · answer_map: {x=324} · 근 선택: unique

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 178 · `wm-geseq-dc183eb2575d`

- 도메인: `GEO-SEQ` · 발문형식: 단답형 · 정답형식: 자연수 · 난이도: 1.9
- 성취기준: [12대수03-03]

**문항**: 첫째항이 1, 공비가 2인 등비수열의 제7항을 구하시오.

**정답**: `64`

**풀이**: 등비수열의 제n항은 첫째항에 공비를 (n−1)번 곱한 값이므로, 제7항은 64 이다.

**verify(SymPy 입력)**: conditions: `x - (1 * 2**(7 - 1)) = 0` · answer_map: {x=64} · 근 선택: unique

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 179 · `wm-geseq-a078bc126d13`

- 도메인: `GEO-SEQ` · 발문형식: 단답형 · 정답형식: 자연수 · 난이도: 2
- 성취기준: [12대수03-03]

**문항**: 첫째항이 3, 공비가 5인 등비수열의 제4항을 구하시오.

**정답**: `375`

**풀이**: 등비수열의 제n항은 첫째항에 공비를 (n−1)번 곱한 값이므로, 제4항은 375 이다.

**verify(SymPy 입력)**: conditions: `x - (3 * 5**(4 - 1)) = 0` · answer_map: {x=375} · 근 선택: unique

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 180 · `wm-exp-bf4187b90d38`

- 도메인: `EXP-EQ` · 발문형식: 단답형 · 정답형식: 자연수 · 난이도: 2
- 성취기준: [12대수01-08]

**문항**: 방정식 2^x = 512 의 해를 구하시오.

**정답**: `9`

**풀이**: 2^x = 512 에서 우변을 밑 2의 거듭제곱으로 나타내면 2^9 이므로, 밑이 같아 지수를 비교하면 x = 9 이다.

**verify(SymPy 입력)**: conditions: `2**x - 512 = 0` · answer_map: {x=9} · 근 선택: unique

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 181 · `wm-exp-e2482b9581a4`

- 도메인: `EXP-EQ` · 발문형식: 단답형 · 정답형식: 자연수 · 난이도: 2
- 성취기준: [12대수01-08]

**문항**: 방정식 10^x = 1000 의 해를 구하시오.

**정답**: `3`

**풀이**: 10^x = 1000 에서 우변을 밑 10의 거듭제곱으로 나타내면 10^3 이므로, 밑이 같아 지수를 비교하면 x = 3 이다.

**verify(SymPy 입력)**: conditions: `10**x - 1000 = 0` · answer_map: {x=3} · 근 선택: unique

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 182 · `wm-exp-7e160d181bb0`

- 도메인: `EXP-EQ` · 발문형식: 단답형 · 정답형식: 자연수 · 난이도: 1.8
- 성취기준: [12대수01-08]

**문항**: 지수방정식 2^x = 16 을 만족하는 x의 값을 구하시오.

**정답**: `4`

**풀이**: 2^x = 16 에서 우변을 밑 2의 거듭제곱으로 나타내면 2^4 이므로, 밑이 같아 지수를 비교하면 x = 4 이다.

**verify(SymPy 입력)**: conditions: `2**x - 16 = 0` · answer_map: {x=4} · 근 선택: unique

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 183 · `wm-exp-701bd77157eb`

- 도메인: `EXP-EQ` · 발문형식: 단답형 · 정답형식: 자연수 · 난이도: 1.8
- 성취기준: [12대수01-08]

**문항**: 방정식 7^x = 7 의 해를 구하시오.

**정답**: `1`

**풀이**: 7^x = 7 에서 우변을 밑 7의 거듭제곱으로 나타내면 7^1 이므로, 밑이 같아 지수를 비교하면 x = 1 이다.

**verify(SymPy 입력)**: conditions: `7**x - 7 = 0` · answer_map: {x=1} · 근 선택: unique

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 184 · `wm-exp-f972237eb614`

- 도메인: `EXP-EQ` · 발문형식: 단답형 · 정답형식: 자연수 · 난이도: 1.5
- 성취기준: [12대수01-08]

**문항**: 방정식 3^x = 27 의 해를 구하시오.

**정답**: `3`

**풀이**: 3^x = 27 에서 우변을 밑 3의 거듭제곱으로 나타내면 3^3 이므로, 밑이 같아 지수를 비교하면 x = 3 이다.

**verify(SymPy 입력)**: conditions: `3**x - 27 = 0` · answer_map: {x=3} · 근 선택: unique

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 185 · `wm-exp-887ff396d4e8`

- 도메인: `EXP-EQ` · 발문형식: 단답형 · 정답형식: 자연수 · 난이도: 1.8
- 성취기준: [12대수01-08]

**문항**: 5^x = 5 일 때, x의 값을 구하시오.

**정답**: `1`

**풀이**: 5^x = 5 에서 우변을 밑 5의 거듭제곱으로 나타내면 5^1 이므로, 밑이 같아 지수를 비교하면 x = 1 이다.

**verify(SymPy 입력)**: conditions: `5**x - 5 = 0` · answer_map: {x=1} · 근 선택: unique

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 186 · `wm-exp-81dec9a901a5`

- 도메인: `EXP-EQ` · 발문형식: 단답형 · 정답형식: 자연수 · 난이도: 1.8
- 성취기준: [12대수01-08]

**문항**: 방정식 6^x = 6 의 해를 구하시오.

**정답**: `1`

**풀이**: 6^x = 6 에서 우변을 밑 6의 거듭제곱으로 나타내면 6^1 이므로, 밑이 같아 지수를 비교하면 x = 1 이다.

**verify(SymPy 입력)**: conditions: `6**x - 6 = 0` · answer_map: {x=1} · 근 선택: unique

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 187 · `wm-exp-16440cd711cc`

- 도메인: `EXP-EQ` · 발문형식: 단답형 · 정답형식: 자연수 · 난이도: 1.5
- 성취기준: [12대수01-08]

**문항**: 2^x = 4 일 때, x의 값을 구하시오.

**정답**: `2`

**풀이**: 2^x = 4 에서 우변을 밑 2의 거듭제곱으로 나타내면 2^2 이므로, 밑이 같아 지수를 비교하면 x = 2 이다.

**verify(SymPy 입력)**: conditions: `2**x - 4 = 0` · answer_map: {x=2} · 근 선택: unique

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 188 · `wm-exp-97836f3244d4`

- 도메인: `EXP-EQ` · 발문형식: 단답형 · 정답형식: 자연수 · 난이도: 2
- 성취기준: [12대수01-08]

**문항**: 5^x = 125 일 때, x의 값을 구하시오.

**정답**: `3`

**풀이**: 5^x = 125 에서 우변을 밑 5의 거듭제곱으로 나타내면 5^3 이므로, 밑이 같아 지수를 비교하면 x = 3 이다.

**verify(SymPy 입력)**: conditions: `5**x - 125 = 0` · answer_map: {x=3} · 근 선택: unique

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 189 · `wm-log-befb0891750c`

- 도메인: `LOG-EQ` · 발문형식: 단답형 · 정답형식: 자연수 · 난이도: 2
- 성취기준: [12대수01-08]

**문항**: 방정식 log_2 x = 9 의 해를 구하시오.

**정답**: `512`

**풀이**: 로그의 정의에 따라 이 방정식의 해는 밑 2를 9번 거듭제곱한 값이므로, x = 512 이다.

**verify(SymPy 입력)**: conditions: `log(x, 2) - 9 = 0` · answer_map: {x=512} · 근 선택: unique

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 190 · `wm-log-495ada0f7043`

- 도메인: `LOG-EQ` · 발문형식: 단답형 · 정답형식: 자연수 · 난이도: 1.8
- 성취기준: [12대수01-08]

**문항**: x가 만족해야 할 로그방정식 log_6 x = 2의 값을 찾아보세요.

**정답**: `36`

**풀이**: 로그의 정의에 따라 이 방정식의 해는 밑 6을 2번 거듭제곱한 값이므로, x = 36 이다.

**verify(SymPy 입력)**: conditions: `log(x, 6) - 2 = 0` · answer_map: {x=36} · 근 선택: unique

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 191 · `wm-log-7e16610c4371`

- 도메인: `LOG-EQ` · 발문형식: 단답형 · 정답형식: 자연수 · 난이도: 1.8
- 성취기준: [12대수01-08]

**문항**: log_10 x = 2 일 때, x의 값을 구하시오.

**정답**: `100`

**풀이**: 로그의 정의에 따라 이 방정식의 해는 밑 10을 2번 거듭제곱한 값이므로, x = 100 이다.

**verify(SymPy 입력)**: conditions: `log(x, 10) - 2 = 0` · answer_map: {x=100} · 근 선택: unique

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 192 · `wm-log-7b04675f160c`

- 도메인: `LOG-EQ` · 발문형식: 단답형 · 정답형식: 자연수 · 난이도: 1.8
- 성취기준: [12대수01-08]

**문항**: log_2 x = 6 일 때, x의 값을 구하시오.

**정답**: `64`

**풀이**: 로그의 정의에 따라 이 방정식의 해는 밑 2를 6번 거듭제곱한 값이므로, x = 64 이다.

**verify(SymPy 입력)**: conditions: `log(x, 2) - 6 = 0` · answer_map: {x=64} · 근 선택: unique

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 193 · `wm-log-2b749c441368`

- 도메인: `LOG-EQ` · 발문형식: 단답형 · 정답형식: 자연수 · 난이도: 2
- 성취기준: [12대수01-08]

**문항**: 로그 기호로 표현한 방정식 log_3 x = 6 의 해를 찾아보세요.

**정답**: `729`

**풀이**: 로그의 정의에 따라 이 방정식의 해는 밑 3을 6번 거듭제곱한 값이므로, x = 729 이다.

**verify(SymPy 입력)**: conditions: `log(x, 3) - 6 = 0` · answer_map: {x=729} · 근 선택: unique

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 194 · `wm-log-31d6d0011812`

- 도메인: `LOG-EQ` · 발문형식: 단답형 · 정답형식: 자연수 · 난이도: 1.5
- 성취기준: [12대수01-08]

**문항**: log_2 x = 2 일 때, x의 값을 구하시오.

**정답**: `4`

**풀이**: 로그의 정의에 따라 이 방정식의 해는 밑 2를 2번 거듭제곱한 값이므로, x = 4 이다.

**verify(SymPy 입력)**: conditions: `log(x, 2) - 2 = 0` · answer_map: {x=4} · 근 선택: unique

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 195 · `wm-trig-953420ce7766`

- 도메인: `TRIG-VAL` · 발문형식: 단답형 · 정답형식: 자연수 · 난이도: 1.3
- 성취기준: [12대수02-02]

**문항**: sin 90°의 값을 구하시오.

**정답**: `1`

**풀이**: 단위원 위에서 90°에 대응하는 점의 y좌표가 sin 90°의 값이므로, 그 값은 1 이다.

**verify(SymPy 입력)**: conditions: `x - sin(90*pi/180) = 0` · answer_map: {x=1} · 근 선택: unique

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 196 · `wm-trig-ef55cdc3df55`

- 도메인: `TRIG-VAL` · 발문형식: 단답형 · 정답형식: 실수 · 난이도: 1.4
- 성취기준: [12대수02-02]

**문항**: sin 45° 를 계산하시오.

**정답**: `sqrt(2)/2`

**풀이**: 단위원 위에서 45°에 대응하는 점의 y좌표가 sin 45°의 값이므로, 그 값은 sqrt(2)/2 이다.

**verify(SymPy 입력)**: conditions: `x - sin(45*pi/180) = 0` · answer_map: {x=sqrt(2)/2} · 근 선택: unique

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 197 · `wm-trig-51cc082daa10`

- 도메인: `TRIG-VAL` · 발문형식: 단답형 · 정답형식: 실수 · 난이도: 1.5
- 성취기준: [12대수02-02]

**문항**: 삼각함수 sin 210°의 값을 구하시오.

**정답**: `-1/2`

**풀이**: 단위원 위에서 210°에 대응하는 점의 y좌표가 sin 210°의 값이므로, 그 값은 -1/2 이다.

**verify(SymPy 입력)**: conditions: `x - sin(210*pi/180) = 0` · answer_map: {x=-1/2} · 근 선택: unique

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 198 · `wm-trig-0b583a86e95b`

- 도메인: `TRIG-VAL` · 발문형식: 단답형 · 정답형식: 실수 · 난이도: 1.6
- 성취기준: [12대수02-02]

**문항**: 삼각함수 sin 240°의 값을 구하시오.

**정답**: `-sqrt(3)/2`

**풀이**: 단위원 위에서 240°에 대응하는 점의 y좌표가 sin 240°의 값이므로, 그 값은 -sqrt(3)/2 이다.

**verify(SymPy 입력)**: conditions: `x - sin(240*pi/180) = 0` · answer_map: {x=-sqrt(3)/2} · 근 선택: unique

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 199 · `wm-trig-c0ff044c8c6c`

- 도메인: `TRIG-VAL` · 발문형식: 단답형 · 정답형식: 실수 · 난이도: 1.6
- 성취기준: [12대수02-02]

**문항**: sin 225°의 값을 구하시오.

**정답**: `-sqrt(2)/2`

**풀이**: 단위원 위에서 225°에 대응하는 점의 y좌표가 sin 225°의 값이므로, 그 값은 -sqrt(2)/2 이다.

**verify(SymPy 입력)**: conditions: `x - sin(225*pi/180) = 0` · answer_map: {x=-sqrt(2)/2} · 근 선택: unique

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 200 · `wm-trig-9215b6e7ebe2`

- 도메인: `TRIG-VAL` · 발문형식: 단답형 · 정답형식: 실수 · 난이도: 1.8
- 성취기준: [12대수02-02]

**문항**: tan 150°의 값을 구하시오.

**정답**: `-sqrt(3)/3`

**풀이**: 단위원 위에서 150°에 대응하는 점의 y좌표를 x좌표로 나눈 값이 tan 150°의 값이므로, 그 값은 -sqrt(3)/3 이다.

**verify(SymPy 입력)**: conditions: `x - tan(150*pi/180) = 0` · answer_map: {x=-sqrt(3)/3} · 근 선택: unique

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (solution_steps 有)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- 해당없음 ⑤ (단답형 — 오개념 태그 없음)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

<!-- coverage: {"n":200,"corpus_size":429,"domain_counts":{"QUAD-EQ":69,"ARITH-SEQ":28,"CALC-TANGENT":19,"CALC-EXTREMUM-VALUE":18,"CALC-EXTREMUM":17,"CALC-EXTREMUM-MC":14,"GEO-SEQ":14,"EXP-EQ":9,"LOG-EQ":6,"TRIG-VAL":6},"format_counts":{"객관식":37,"단답형":163},"misconception_counts":{"extremum-max-min-confused":14,"extremum-value-vs-point-confused":14,"factor-sign-flip":23,"opposite-root-selected":23},"difficulty_min":1.3,"difficulty_max":4.0,"missing_required_misconceptions":[]} -->
