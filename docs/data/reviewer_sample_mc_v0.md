# 검수자용 샘플 문항 패키지 (자체생성 동등문제 코퍼스 v0)

> 전체 코퍼스 1080문에서 결정론 층화 샘플링으로 뽑은 대표 표본 200문. 같은 코퍼스·N이면 바이트까지 재현된다(난수 0·정렬 기반).

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

- 도메인: ABS-VALUE 5 · AREA-PERIMETER 5 · CALC-CHAIN 5 · CALC-PRODUCT 5 · CIRCLE-AREA 5 · CIRCLE-RADIUS 5 · COMBINATION-COUNT 5 · COMBINE-UNLIKE 5 · COMPLETE-SQUARE 5 · CONE-VOLUME 5 · CONJUGATE-PRODUCT 5 · DECIMAL-MULT 5 · DIFF-SQUARES 5 · DISTRIBUTE-PARTIAL 5 · EXP-PRODUCT 5 · EXP-ZERO 5 · FRACTION-ADD 5 · FRACTION-CANCEL 5 · FUNC-COMPOSE 5 · FUNC-TRANSLATE 5 · GCD-LCM 4 · LOG-DIST 4 · MIDPOINT-NO-HALF 4 · MIXED-MULT 4 · NEG-DISTRIBUTE 4 · NEG-EVEN-POWER 4 · NEG-PRODUCT 4 · NEG-SQUARE 4 · POLY-PRODUCT 4 · POLYGON-ANGLE-SUM 4 · POWER-OF-POWER 4 · PROB-INDEPENDENT-TRIAL 4 · REMAINDER-THEOREM 4 · SAME-ITEM-PERM 4 · SCALE-AREA 4 · SCALE-VOLUME 4 · SQRT-POS 4 · SQRT-SUM 4 · SQUARE-DIFF 4 · SUBTRACT-NEG 4 · TRANSPOSE-SIGN 4 · TRAPEZOID-AREA 4 · TRIG-ADD 4 · TRIG-PERIOD 4 · VIETA-SUM 4
- 발문형식: 객관식 200
- 객관식 오개념: absolute-value-keeps-sign 5 · angle-sum-non-triangle 4 · area-perimeter-confusion 5 · chain-rule-inner-derivative-omitted 5 · circle-area-circumference 5 · circle-radius-squared 5 · combination-no-denominator 5 · combine-unlike-terms 5 · complete-square-naive 5 · composite-function-commutes 5 · cone-volume-no-third 5 · conjugate-product-sum 5 · decimal-mult-place 5 · difference-of-squares-confused 5 · distribute-first-term-only 5 · distribution-over-power 4 · exponent-product-multiplies 5 · exponent-zero 5 · fraction-addition-naive 5 · fraction-cancellation 5 · gambler-fallacy 4 · gcd-lcm-confused 4 · log-distribution 4 · midpoint-sum-only 4 · mixed-number-mult-whole 4 · negative-distribute-sign 4 · negative-even-power-sign 4 · negative-square-precedence 4 · negative-times-negative 4 · period-of-scaled-sine 4 · power-of-power-adds 4 · product-rule-naive 5 · remainder-theorem-sign 4 · same-item-permutation-no-divide 4 · scale-area-linear 4 · scale-volume-linear 4 · sine-distributes-over-sum 4 · sqrt-distributes-over-sum 4 · square-of-difference-no-cross 4 · square-root-positivity 4 · subtract-negative-sign 4 · translation-sign-flip 5 · transpose-no-sign-change 4 · trapezoid-area-no-half 4 · vieta-sign-error 4
- 난이도 범위: 2.5 ~ 3.5
- 강제 오개념 누락: ['extremum-max-min-confused', 'extremum-value-vs-point-confused', 'factor-sign-flip', 'opposite-root-selected']

---

## 표본 01 · `wm-misc-eval-mc-f3278bb9356e`

- 도메인: `ABS-VALUE` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.8
- 성취기준: [9수01-04]

**문항**: |-4| + 21 의 값을 구하시오.

**정답**: `25`

**풀이**: 절댓값은 음이 아니므로 |-4| = 4 이고 |-4| + 21 = 25 이다. 절댓값이 음수 부호를 유지한다고 여기면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 4+21` · answer_map: {x=25}

**선지**:
- ① `-25` ← 정답
- ② `-17` ← 정답
- ③ `17` ← 오답 · 오개념 `absolute-value-keeps-sign`
- ④ `25` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 02 · `wm-misc-eval-mc-40eaaea68255`

- 도메인: `ABS-VALUE` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3
- 성취기준: [9수01-04]

**문항**: |-6| + 21 의 값을 구하시오.

**정답**: `27`

**풀이**: 절댓값은 음이 아니므로 |-6| = 6 이고 |-6| + 21 = 27 이다. 절댓값이 음수 부호를 유지한다고 여기면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 6+21` · answer_map: {x=27}

**선지**:
- ① `-27` ← 정답
- ② `-15` ← 정답
- ③ `15` ← 오답 · 오개념 `absolute-value-keeps-sign`
- ④ `27` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 03 · `wm-misc-eval-mc-1d192c96f608`

- 도메인: `ABS-VALUE` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.2
- 성취기준: [9수01-04]

**문항**: |-2| + 5 의 값을 구하시오.

**정답**: `7`

**풀이**: 절댓값은 음이 아니므로 |-2| = 2 이고 |-2| + 5 = 7 이다. 절댓값이 음수 부호를 유지한다고 여기면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 2+5` · answer_map: {x=7}

**선지**:
- ① `-7` ← 정답
- ② `-3` ← 정답
- ③ `3` ← 오답 · 오개념 `absolute-value-keeps-sign`
- ④ `7` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 04 · `wm-misc-eval-mc-07393165891c`

- 도메인: `ABS-VALUE` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.5
- 성취기준: [9수01-04]

**문항**: |-12| + 21 의 값을 구하시오.

**정답**: `33`

**풀이**: 절댓값은 음이 아니므로 |-12| = 12 이고 |-12| + 21 = 33 이다. 절댓값이 음수 부호를 유지한다고 여기면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 12+21` · answer_map: {x=33}

**선지**:
- ① `-33` ← 정답
- ② `-9` ← 정답
- ③ `9` ← 오답 · 오개념 `absolute-value-keeps-sign`
- ④ `33` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 05 · `wm-misc-eval-mc-9e122e331cd2`

- 도메인: `ABS-VALUE` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.4
- 성취기준: [9수01-04]

**문항**: |-2| + 7 의 값을 구하시오.

**정답**: `9`

**풀이**: 절댓값은 음이 아니므로 |-2| = 2 이고 |-2| + 7 = 9 이다. 절댓값이 음수 부호를 유지한다고 여기면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 2+7` · answer_map: {x=9}

**선지**:
- ① `-9` ← 정답
- ② `-5` ← 정답
- ③ `5` ← 오답 · 오개념 `absolute-value-keeps-sign`
- ④ `9` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 06 · `wm-misc-eval-mc-c55b36a96884`

- 도메인: `AREA-PERIMETER` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.4
- 성취기준: [12직수03-04], [6수03-11], [9수03-12]

**문항**: 가로가 2, 세로가 7 인 직사각형의 넓이를 구하시오.

**정답**: `14`

**풀이**: 직사각형의 넓이는 가로×세로 = 2×7 = 14 이다. 둘레 2×(2+7) = 18 와 혼동하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 2*7` · answer_map: {x=14}

**선지**:
- ① `9` ← 정답
- ② `14` ← 정답
- ③ `18` ← 오답 · 오개념 `area-perimeter-confusion`
- ④ `28` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 07 · `wm-misc-eval-mc-7a10aea79a18`

- 도메인: `AREA-PERIMETER` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.9
- 성취기준: [12직수03-04], [6수03-11], [9수03-12]

**문항**: 가로가 5, 세로가 10 인 직사각형의 넓이를 구하시오.

**정답**: `50`

**풀이**: 직사각형의 넓이는 가로×세로 = 5×10 = 50 이다. 둘레 2×(5+10) = 30 와 혼동하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 5*10` · answer_map: {x=50}

**선지**:
- ① `15` ← 정답
- ② `30` ← 오답 · 오개념 `area-perimeter-confusion`
- ③ `50` ← 정답
- ④ `100` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 08 · `wm-misc-eval-mc-4e903da30eef`

- 도메인: `AREA-PERIMETER` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.5
- 성취기준: [12직수03-04], [6수03-11], [9수03-12]

**문항**: 가로가 7, 세로가 15 인 직사각형의 넓이를 구하시오.

**정답**: `105`

**풀이**: 직사각형의 넓이는 가로×세로 = 7×15 = 105 이다. 둘레 2×(7+15) = 44 와 혼동하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 7*15` · answer_map: {x=105}

**선지**:
- ① `22` ← 정답
- ② `44` ← 오답 · 오개념 `area-perimeter-confusion`
- ③ `105` ← 정답
- ④ `210` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 09 · `wm-misc-eval-mc-b1c65ad1577a`

- 도메인: `AREA-PERIMETER` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.2
- 성취기준: [12직수03-04], [6수03-11], [9수03-12]

**문항**: 가로가 6, 세로가 12 인 직사각형의 넓이를 구하시오.

**정답**: `72`

**풀이**: 직사각형의 넓이는 가로×세로 = 6×12 = 72 이다. 둘레 2×(6+12) = 36 와 혼동하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 6*12` · answer_map: {x=72}

**선지**:
- ① `18` ← 정답
- ② `36` ← 오답 · 오개념 `area-perimeter-confusion`
- ③ `72` ← 정답
- ④ `144` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 10 · `wm-misc-eval-mc-1191c8aad19d`

- 도메인: `AREA-PERIMETER` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.6
- 성취기준: [12직수03-04], [6수03-11], [9수03-12]

**문항**: 가로가 8, 세로가 15 인 직사각형의 넓이를 구하시오.

**정답**: `120`

**풀이**: 직사각형의 넓이는 가로×세로 = 8×15 = 120 이다. 둘레 2×(8+15) = 46 와 혼동하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 8*15` · answer_map: {x=120}

**선지**:
- ① `23` ← 정답
- ② `46` ← 오답 · 오개념 `area-perimeter-confusion`
- ③ `120` ← 정답
- ④ `240` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 11 · `wm-misc-eval-mc-b3bb65300930`

- 도메인: `CALC-CHAIN` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.5
- 성취기준: [12미적Ⅰ-02-01], [12미적Ⅱ-02-05]

**문항**: 함수 f(x) = (5x + 1)^3 의 x = 3 에서의 미분계수 f'(3) 의 값을 구하시오.

**정답**: `3840`

**풀이**: 연쇄법칙으로 도함수를 구하면 내부 함수의 도함수 5 를 곱해야 한다. x = 3 을 대입하면 미분계수는 3840 이다. 내부 도함수 5 를 곱하지 않으면 틀린 값이 된다.

**verify(SymPy 입력)**: conditions: `x = 3*5*(5*3+1)**2` · answer_map: {x=3840}

**선지**:
- ① `768` ← 오답 · 오개념 `chain-rule-inner-derivative-omitted` (op: `chain-rule-omit-inner`)
- ② `1280` ← 정답
- ③ `3840` ← 정답
- ④ `19200` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 12 · `wm-misc-eval-mc-47accf44cdde`

- 도메인: `CALC-CHAIN` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.3
- 성취기준: [12미적Ⅰ-02-01], [12미적Ⅱ-02-05]

**문항**: 함수 f(x) = (5x + 4)^3 의 x = 2 에서의 미분계수 f'(2) 의 값을 구하시오.

**정답**: `2940`

**풀이**: 연쇄법칙으로 도함수를 구하면 내부 함수의 도함수 5 를 곱해야 한다. x = 2 을 대입하면 미분계수는 2940 이다. 내부 도함수 5 를 곱하지 않으면 틀린 값이 된다.

**verify(SymPy 입력)**: conditions: `x = 3*5*(5*2+4)**2` · answer_map: {x=2940}

**선지**:
- ① `588` ← 오답 · 오개념 `chain-rule-inner-derivative-omitted` (op: `chain-rule-omit-inner`)
- ② `980` ← 정답
- ③ `2940` ← 정답
- ④ `14700` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 13 · `wm-misc-eval-mc-acf1b79da89f`

- 도메인: `CALC-CHAIN` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.2
- 성취기준: [12미적Ⅰ-02-01], [12미적Ⅱ-02-05]

**문항**: 함수 f(x) = (4x + 2)^3 의 x = 3 에서의 미분계수 f'(3) 의 값을 구하시오.

**정답**: `2352`

**풀이**: 연쇄법칙으로 도함수를 구하면 내부 함수의 도함수 4 를 곱해야 한다. x = 3 을 대입하면 미분계수는 2352 이다. 내부 도함수 4 를 곱하지 않으면 틀린 값이 된다.

**verify(SymPy 입력)**: conditions: `x = 3*4*(4*3+2)**2` · answer_map: {x=2352}

**선지**:
- ① `588` ← 오답 · 오개념 `chain-rule-inner-derivative-omitted` (op: `chain-rule-omit-inner`)
- ② `784` ← 정답
- ③ `2352` ← 정답
- ④ `9408` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 14 · `wm-misc-eval-mc-9505004d763d`

- 도메인: `CALC-CHAIN` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.5
- 성취기준: [12미적Ⅰ-02-01], [12미적Ⅱ-02-05]

**문항**: 함수 f(x) = (2x + 3)^3 의 x = 3 에서의 미분계수 f'(3) 의 값을 구하시오.

**정답**: `486`

**풀이**: 연쇄법칙으로 도함수를 구하면 내부 함수의 도함수 2 를 곱해야 한다. x = 3 을 대입하면 미분계수는 486 이다. 내부 도함수 2 를 곱하지 않으면 틀린 값이 된다.

**verify(SymPy 입력)**: conditions: `x = 3*2*(2*3+3)**2` · answer_map: {x=486}

**선지**:
- ① `162` ← 정답
- ② `243` ← 오답 · 오개념 `chain-rule-inner-derivative-omitted` (op: `chain-rule-omit-inner`)
- ③ `486` ← 정답
- ④ `972` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 15 · `wm-misc-eval-mc-cf6e28ba3f4a`

- 도메인: `CALC-CHAIN` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.9
- 성취기준: [12미적Ⅰ-02-01], [12미적Ⅱ-02-05]

**문항**: 함수 f(x) = (4x + 3)^3 의 x = 2 에서의 미분계수 f'(2) 의 값을 구하시오.

**정답**: `1452`

**풀이**: 연쇄법칙으로 도함수를 구하면 내부 함수의 도함수 4 를 곱해야 한다. x = 2 을 대입하면 미분계수는 1452 이다. 내부 도함수 4 를 곱하지 않으면 틀린 값이 된다.

**verify(SymPy 입력)**: conditions: `x = 3*4*(4*2+3)**2` · answer_map: {x=1452}

**선지**:
- ① `363` ← 오답 · 오개념 `chain-rule-inner-derivative-omitted` (op: `chain-rule-omit-inner`)
- ② `484` ← 정답
- ③ `1452` ← 정답
- ④ `5808` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 16 · `wm-misc-eval-mc-fd5ac974df02`

- 도메인: `CALC-PRODUCT` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.4
- 성취기준: [12미적Ⅰ-02-01], [12미적Ⅰ-02-04]

**문항**: 두 함수 f(x) = x^1, g(x) = x^3 에 대하여 함수 f(x)g(x) 의 x = 5 에서의 미분계수를 구하시오.

**정답**: `500`

**풀이**: f(x)g(x) = x^4 이므로 미분계수는 4·5^3 = 500 이다. (fg)' = f'g' 로 오인하면 틀린 값이 된다.

**verify(SymPy 입력)**: conditions: `x = 4*5**3` · answer_map: {x=500}

**선지**:
- ① `75` ← 오답 · 오개념 `product-rule-naive`
- ② `375` ← 정답
- ③ `500` ← 정답
- ④ `2500` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 17 · `wm-misc-eval-mc-0192090932f3`

- 도메인: `CALC-PRODUCT` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.5
- 성취기준: [12미적Ⅰ-02-01], [12미적Ⅰ-02-04]

**문항**: 두 함수 f(x) = x^3, g(x) = x^3 에 대하여 함수 f(x)g(x) 의 x = 4 에서의 미분계수를 구하시오.

**정답**: `6144`

**풀이**: f(x)g(x) = x^6 이므로 미분계수는 6·4^5 = 6144 이다. (fg)' = f'g' 로 오인하면 틀린 값이 된다.

**verify(SymPy 입력)**: conditions: `x = 6*4**5` · answer_map: {x=6144}

**선지**:
- ① `2304` ← 오답 · 오개념 `product-rule-naive`
- ② `6144` ← 정답
- ③ `9216` ← 정답
- ④ `24576` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 18 · `wm-misc-eval-mc-506b5ef44920`

- 도메인: `CALC-PRODUCT` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.9
- 성취기준: [12미적Ⅰ-02-01], [12미적Ⅰ-02-04]

**문항**: 두 함수 f(x) = x^1, g(x) = x^1 에 대하여 함수 f(x)g(x) 의 x = 2 에서의 미분계수를 구하시오.

**정답**: `4`

**풀이**: f(x)g(x) = x^2 이므로 미분계수는 2·2^1 = 4 이다. (fg)' = f'g' 로 오인하면 틀린 값이 된다.

**verify(SymPy 입력)**: conditions: `x = 2*2**1` · answer_map: {x=4}

**선지**:
- ① `1` ← 오답 · 오개념 `product-rule-naive`
- ② `2` ← 정답
- ③ `4` ← 정답
- ④ `8` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 19 · `wm-misc-eval-mc-7f0a47e53b77`

- 도메인: `CALC-PRODUCT` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.5
- 성취기준: [12미적Ⅰ-02-01], [12미적Ⅰ-02-04]

**문항**: 두 함수 f(x) = x^1, g(x) = x^2 에 대하여 함수 f(x)g(x) 의 x = 8 에서의 미분계수를 구하시오.

**정답**: `192`

**풀이**: f(x)g(x) = x^3 이므로 미분계수는 3·8^2 = 192 이다. (fg)' = f'g' 로 오인하면 틀린 값이 된다.

**verify(SymPy 입력)**: conditions: `x = 3*8**2` · answer_map: {x=192}

**선지**:
- ① `16` ← 오답 · 오개념 `product-rule-naive`
- ② `128` ← 정답
- ③ `192` ← 정답
- ④ `1536` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 20 · `wm-misc-eval-mc-de79c922bb7b`

- 도메인: `CALC-PRODUCT` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.2
- 성취기준: [12미적Ⅰ-02-01], [12미적Ⅰ-02-04]

**문항**: 두 함수 f(x) = x^1, g(x) = x^2 에 대하여 함수 f(x)g(x) 의 x = 4 에서의 미분계수를 구하시오.

**정답**: `48`

**풀이**: f(x)g(x) = x^3 이므로 미분계수는 3·4^2 = 48 이다. (fg)' = f'g' 로 오인하면 틀린 값이 된다.

**verify(SymPy 입력)**: conditions: `x = 3*4**2` · answer_map: {x=48}

**선지**:
- ① `8` ← 오답 · 오개념 `product-rule-naive`
- ② `32` ← 정답
- ③ `48` ← 정답
- ④ `192` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 21 · `wm-misc-eval-mc-bc459d538e50`

- 도메인: `CIRCLE-AREA` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.2
- 성취기준: [9수03-19]

**문항**: 반지름이 7 인 원의 넓이를 원주율 π로 나눈 값을 구하시오.

**정답**: `49`

**풀이**: 원의 넓이는 π×(반지름)² 이므로 π로 나눈 값은 7² 곧 49 이다. 원의 둘레 공식 2πr 와 혼동하면 2×7 곧 14 로 잘못 답한다.

**verify(SymPy 입력)**: conditions: `x = 7**2` · answer_map: {x=49}

**선지**:
- ① `7` ← 정답
- ② `14` ← 오답 · 오개념 `circle-area-circumference`
- ③ `49` ← 정답
- ④ `98` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 22 · `wm-misc-eval-mc-4bcd4f8ab63a`

- 도메인: `CIRCLE-AREA` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.8
- 성취기준: [9수03-19]

**문항**: 반지름이 3 인 원의 넓이를 원주율 π로 나눈 값을 구하시오.

**정답**: `9`

**풀이**: 원의 넓이는 π×(반지름)² 이므로 π로 나눈 값은 3² 곧 9 이다. 원의 둘레 공식 2πr 와 혼동하면 2×3 곧 6 로 잘못 답한다.

**verify(SymPy 입력)**: conditions: `x = 3**2` · answer_map: {x=9}

**선지**:
- ① `3` ← 정답
- ② `6` ← 오답 · 오개념 `circle-area-circumference`
- ③ `9` ← 정답
- ④ `18` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 23 · `wm-misc-eval-mc-55a2da4abb38`

- 도메인: `CIRCLE-AREA` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.6
- 성취기준: [9수03-19]

**문항**: 반지름이 12 인 원의 넓이를 원주율 π로 나눈 값을 구하시오.

**정답**: `144`

**풀이**: 원의 넓이는 π×(반지름)² 이므로 π로 나눈 값은 12² 곧 144 이다. 원의 둘레 공식 2πr 와 혼동하면 2×12 곧 24 로 잘못 답한다.

**verify(SymPy 입력)**: conditions: `x = 12**2` · answer_map: {x=144}

**선지**:
- ① `12` ← 정답
- ② `24` ← 오답 · 오개념 `circle-area-circumference`
- ③ `144` ← 정답
- ④ `288` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 24 · `wm-misc-eval-mc-d925b497d7f2`

- 도메인: `CIRCLE-AREA` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3
- 성취기준: [9수03-19]

**문항**: 반지름이 5 인 원의 넓이를 원주율 π로 나눈 값을 구하시오.

**정답**: `25`

**풀이**: 원의 넓이는 π×(반지름)² 이므로 π로 나눈 값은 5² 곧 25 이다. 원의 둘레 공식 2πr 와 혼동하면 2×5 곧 10 로 잘못 답한다.

**verify(SymPy 입력)**: conditions: `x = 5**2` · answer_map: {x=25}

**선지**:
- ① `5` ← 정답
- ② `10` ← 오답 · 오개념 `circle-area-circumference`
- ③ `25` ← 정답
- ④ `50` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 25 · `wm-misc-eval-mc-36670db3a71e`

- 도메인: `CIRCLE-AREA` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.4
- 성취기준: [9수03-19]

**문항**: 반지름이 20 인 원의 넓이를 원주율 π로 나눈 값을 구하시오.

**정답**: `400`

**풀이**: 원의 넓이는 π×(반지름)² 이므로 π로 나눈 값은 20² 곧 400 이다. 원의 둘레 공식 2πr 와 혼동하면 2×20 곧 40 로 잘못 답한다.

**verify(SymPy 입력)**: conditions: `x = 20**2` · answer_map: {x=400}

**선지**:
- ① `20` ← 정답
- ② `40` ← 오답 · 오개념 `circle-area-circumference`
- ③ `400` ← 정답
- ④ `800` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 26 · `wm-misc-eval-mc-30b235071a6f`

- 도메인: `CIRCLE-RADIUS` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.4
- 성취기준: [10공수2-01-04], [10기수2-01-04], [12기하02-05]

**문항**: 원 x^2 + y^2 = 400 의 반지름의 길이를 구하시오.

**정답**: `20`

**풀이**: x² + y² = r² 에서 반지름은 r 이므로 r² = 400 이면 반지름은 20 이다. 우변 400 을 반지름으로 여기면 틀린다.

**verify(SymPy 입력)**: conditions: `x = sqrt(400)` · answer_map: {x=20}

**선지**:
- ① `20` ← 정답
- ② `40` ← 정답
- ③ `400` ← 오답 · 오개념 `circle-radius-squared`
- ④ `420` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 27 · `wm-misc-eval-mc-8c98c6772bab`

- 도메인: `CIRCLE-RADIUS` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.6
- 성취기준: [10공수2-01-04], [10기수2-01-04], [12기하02-05]

**문항**: 원 x^2 + y^2 = 529 의 반지름의 길이를 구하시오.

**정답**: `23`

**풀이**: x² + y² = r² 에서 반지름은 r 이므로 r² = 529 이면 반지름은 23 이다. 우변 529 을 반지름으로 여기면 틀린다.

**verify(SymPy 입력)**: conditions: `x = sqrt(529)` · answer_map: {x=23}

**선지**:
- ① `23` ← 정답
- ② `46` ← 정답
- ③ `529` ← 오답 · 오개념 `circle-radius-squared`
- ④ `552` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 28 · `wm-misc-eval-mc-c0fc6035800b`

- 도메인: `CIRCLE-RADIUS` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.2
- 성취기준: [10공수2-01-04], [10기수2-01-04], [12기하02-05]

**문항**: 원 x^2 + y^2 = 49 의 반지름의 길이를 구하시오.

**정답**: `7`

**풀이**: x² + y² = r² 에서 반지름은 r 이므로 r² = 49 이면 반지름은 7 이다. 우변 49 을 반지름으로 여기면 틀린다.

**verify(SymPy 입력)**: conditions: `x = sqrt(49)` · answer_map: {x=7}

**선지**:
- ① `7` ← 정답
- ② `14` ← 정답
- ③ `49` ← 오답 · 오개념 `circle-radius-squared`
- ④ `56` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 29 · `wm-misc-eval-mc-da3631ce937f`

- 도메인: `CIRCLE-RADIUS` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.8
- 성취기준: [10공수2-01-04], [10기수2-01-04], [12기하02-05]

**문항**: 원 x^2 + y^2 = 625 의 반지름의 길이를 구하시오.

**정답**: `25`

**풀이**: x² + y² = r² 에서 반지름은 r 이므로 r² = 625 이면 반지름은 25 이다. 우변 625 을 반지름으로 여기면 틀린다.

**verify(SymPy 입력)**: conditions: `x = sqrt(625)` · answer_map: {x=25}

**선지**:
- ① `25` ← 정답
- ② `50` ← 정답
- ③ `625` ← 오답 · 오개념 `circle-radius-squared`
- ④ `650` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 30 · `wm-misc-eval-mc-1e31774a6ddb`

- 도메인: `CIRCLE-RADIUS` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3
- 성취기준: [10공수2-01-04], [10기수2-01-04], [12기하02-05]

**문항**: 원 x^2 + y^2 = 256 의 반지름의 길이를 구하시오.

**정답**: `16`

**풀이**: x² + y² = r² 에서 반지름은 r 이므로 r² = 256 이면 반지름은 16 이다. 우변 256 을 반지름으로 여기면 틀린다.

**verify(SymPy 입력)**: conditions: `x = sqrt(256)` · answer_map: {x=16}

**선지**:
- ① `16` ← 정답
- ② `32` ← 정답
- ③ `256` ← 오답 · 오개념 `circle-radius-squared`
- ④ `272` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 31 · `wm-misc-eval-mc-ee2ca5a8705b`

- 도메인: `COMBINATION-COUNT` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.7
- 성취기준: [12직수04-01]

**문항**: 서로 다른 9 개에서 4 개를 뽑는 조합의 수 9C4 를 구하시오.

**정답**: `126`

**풀이**: 9C4 = 9!/(4!×5!) = 126 이다. 분모의 4! 을 빠뜨리면 순열의 수 9P4 = 3024 이 되어 틀린다.

**verify(SymPy 입력)**: conditions: `x = 126` · answer_map: {x=126}

**선지**:
- ① `13` ← 정답
- ② `36` ← 정답
- ③ `126` ← 정답
- ④ `3024` ← 오답 · 오개념 `combination-no-denominator`

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 32 · `wm-misc-eval-mc-edc3b9adc18e`

- 도메인: `COMBINATION-COUNT` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.1
- 성취기준: [12직수04-01]

**문항**: 서로 다른 13 개에서 4 개를 뽑는 조합의 수 13C4 를 구하시오.

**정답**: `715`

**풀이**: 13C4 = 13!/(4!×9!) = 715 이다. 분모의 4! 을 빠뜨리면 순열의 수 13P4 = 17160 이 되어 틀린다.

**verify(SymPy 입력)**: conditions: `x = 715` · answer_map: {x=715}

**선지**:
- ① `17` ← 정답
- ② `52` ← 정답
- ③ `715` ← 정답
- ④ `17160` ← 오답 · 오개념 `combination-no-denominator`

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 33 · `wm-misc-eval-mc-1b9f3fa938c8`

- 도메인: `COMBINATION-COUNT` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.4
- 성취기준: [12직수04-01]

**문항**: 서로 다른 17 개에서 3 개를 뽑는 조합의 수 17C3 를 구하시오.

**정답**: `680`

**풀이**: 17C3 = 17!/(3!×14!) = 680 이다. 분모의 3! 을 빠뜨리면 순열의 수 17P3 = 4080 이 되어 틀린다.

**verify(SymPy 입력)**: conditions: `x = 680` · answer_map: {x=680}

**선지**:
- ① `20` ← 정답
- ② `51` ← 정답
- ③ `680` ← 정답
- ④ `4080` ← 오답 · 오개념 `combination-no-denominator`

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 34 · `wm-misc-eval-mc-920ed3c75ed1`

- 도메인: `COMBINATION-COUNT` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.5
- 성취기준: [12직수04-01]

**문항**: 서로 다른 8 개에서 3 개를 뽑는 조합의 수 8C3 를 구하시오.

**정답**: `56`

**풀이**: 8C3 = 8!/(3!×5!) = 56 이다. 분모의 3! 을 빠뜨리면 순열의 수 8P3 = 336 이 되어 틀린다.

**verify(SymPy 입력)**: conditions: `x = 56` · answer_map: {x=56}

**선지**:
- ① `11` ← 정답
- ② `24` ← 정답
- ③ `56` ← 정답
- ④ `336` ← 오답 · 오개념 `combination-no-denominator`

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 35 · `wm-misc-eval-mc-598156be0943`

- 도메인: `COMBINATION-COUNT` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.8
- 성취기준: [12직수04-01]

**문항**: 서로 다른 22 개에서 3 개를 뽑는 조합의 수 22C3 를 구하시오.

**정답**: `1540`

**풀이**: 22C3 = 22!/(3!×19!) = 1540 이다. 분모의 3! 을 빠뜨리면 순열의 수 22P3 = 9240 이 되어 틀린다.

**verify(SymPy 입력)**: conditions: `x = 1540` · answer_map: {x=1540}

**선지**:
- ① `25` ← 정답
- ② `66` ← 정답
- ③ `1540` ← 정답
- ④ `9240` ← 오답 · 오개념 `combination-no-denominator`

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 36 · `wm-misc-eval-mc-6c18f15031f4`

- 도메인: `COMBINE-UNLIKE` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3
- 성취기준: [9수02-09]

**문항**: 2x + 6x² 에서 x = 8 일 때의 값을 구하시오.

**정답**: `400`

**풀이**: 차수가 다른 항은 따로 계산하므로 2x + 6x² 는 x = 8 에서 16 + 384 = 400 이다. 차수를 무시하고 8x³으로 결합하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 2*8 + 6*8**2` · answer_map: {x=400}

**선지**:
- ① `16` ← 정답
- ② `384` ← 정답
- ③ `400` ← 정답
- ④ `4096` ← 오답 · 오개념 `combine-unlike-terms`

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 37 · `wm-misc-eval-mc-455079633c2d`

- 도메인: `COMBINE-UNLIKE` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.9
- 성취기준: [9수02-09]

**문항**: 5x + 3x² 에서 x = 7 일 때의 값을 구하시오.

**정답**: `182`

**풀이**: 차수가 다른 항은 따로 계산하므로 5x + 3x² 는 x = 7 에서 35 + 147 = 182 이다. 차수를 무시하고 8x³으로 결합하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 5*7 + 3*7**2` · answer_map: {x=182}

**선지**:
- ① `35` ← 정답
- ② `147` ← 정답
- ③ `182` ← 정답
- ④ `2744` ← 오답 · 오개념 `combine-unlike-terms`

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 38 · `wm-misc-eval-mc-331dbfee9bf5`

- 도메인: `COMBINE-UNLIKE` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.6
- 성취기준: [9수02-09]

**문항**: 3x + 5x² 에서 x = 4 일 때의 값을 구하시오.

**정답**: `92`

**풀이**: 차수가 다른 항은 따로 계산하므로 3x + 5x² 는 x = 4 에서 12 + 80 = 92 이다. 차수를 무시하고 8x³으로 결합하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 3*4 + 5*4**2` · answer_map: {x=92}

**선지**:
- ① `12` ← 정답
- ② `80` ← 정답
- ③ `92` ← 정답
- ④ `512` ← 오답 · 오개념 `combine-unlike-terms`

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 39 · `wm-misc-eval-mc-c73030d5f5ab`

- 도메인: `COMBINE-UNLIKE` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.7
- 성취기준: [9수02-09]

**문항**: 5x + 2x² 에서 x = 6 일 때의 값을 구하시오.

**정답**: `102`

**풀이**: 차수가 다른 항은 따로 계산하므로 5x + 2x² 는 x = 6 에서 30 + 72 = 102 이다. 차수를 무시하고 7x³으로 결합하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 5*6 + 2*6**2` · answer_map: {x=102}

**선지**:
- ① `30` ← 정답
- ② `72` ← 정답
- ③ `102` ← 정답
- ④ `1512` ← 오답 · 오개념 `combine-unlike-terms`

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 40 · `wm-misc-eval-mc-40e81e5712ae`

- 도메인: `COMBINE-UNLIKE` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.4
- 성취기준: [9수02-09]

**문항**: 3x + 4x² 에서 x = 2 일 때의 값을 구하시오.

**정답**: `22`

**풀이**: 차수가 다른 항은 따로 계산하므로 3x + 4x² 는 x = 2 에서 6 + 16 = 22 이다. 차수를 무시하고 7x³으로 결합하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 3*2 + 4*2**2` · answer_map: {x=22}

**선지**:
- ① `6` ← 정답
- ② `16` ← 정답
- ③ `22` ← 정답
- ④ `56` ← 오답 · 오개념 `combine-unlike-terms`

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 41 · `wm-misc-eval-mc-9033ca808ea6`

- 도메인: `COMPLETE-SQUARE` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.3
- 성취기준: [9수02-19]

**문항**: x² + 11x 에서 x = 8 일 때의 값을 구하시오.

**정답**: `152`

**풀이**: x² + 11x 는 x = 8 에서 64 + 88 = 152 이다. 이를 (x+11)²으로 오인하면 (c+11)²로 틀린다.

**verify(SymPy 입력)**: conditions: `x = 8**2 + 11*8` · answer_map: {x=152}

**선지**:
- ① `64` ← 정답
- ② `88` ← 정답
- ③ `152` ← 정답
- ④ `361` ← 오답 · 오개념 `complete-square-naive`

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 42 · `wm-misc-eval-mc-d36d3ebfa81e`

- 도메인: `COMPLETE-SQUARE` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.6
- 성취기준: [9수02-19]

**문항**: x² + 3x 에서 x = 9 일 때의 값을 구하시오.

**정답**: `108`

**풀이**: x² + 3x 는 x = 9 에서 81 + 27 = 108 이다. 이를 (x+3)²으로 오인하면 (c+3)²로 틀린다.

**verify(SymPy 입력)**: conditions: `x = 9**2 + 3*9` · answer_map: {x=108}

**선지**:
- ① `27` ← 정답
- ② `81` ← 정답
- ③ `108` ← 정답
- ④ `144` ← 오답 · 오개념 `complete-square-naive`

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 43 · `wm-misc-eval-mc-bfeb183216e2`

- 도메인: `COMPLETE-SQUARE` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.1
- 성취기준: [9수02-19]

**문항**: x² + 11x 에서 x = 6 일 때의 값을 구하시오.

**정답**: `102`

**풀이**: x² + 11x 는 x = 6 에서 36 + 66 = 102 이다. 이를 (x+11)²으로 오인하면 (c+11)²로 틀린다.

**verify(SymPy 입력)**: conditions: `x = 6**2 + 11*6` · answer_map: {x=102}

**선지**:
- ① `36` ← 정답
- ② `66` ← 정답
- ③ `102` ← 정답
- ④ `289` ← 오답 · 오개념 `complete-square-naive`

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 44 · `wm-misc-eval-mc-e7e2c414106d`

- 도메인: `COMPLETE-SQUARE` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.4
- 성취기준: [9수02-19]

**문항**: x² + 3x 에서 x = 6 일 때의 값을 구하시오.

**정답**: `54`

**풀이**: x² + 3x 는 x = 6 에서 36 + 18 = 54 이다. 이를 (x+3)²으로 오인하면 (c+3)²로 틀린다.

**verify(SymPy 입력)**: conditions: `x = 6**2 + 3*6` · answer_map: {x=54}

**선지**:
- ① `18` ← 정답
- ② `36` ← 정답
- ③ `54` ← 정답
- ④ `81` ← 오답 · 오개념 `complete-square-naive`

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 45 · `wm-misc-eval-mc-1516a2b1c943`

- 도메인: `COMPLETE-SQUARE` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.9
- 성취기준: [9수02-19]

**문항**: x² + 10x 에서 x = 5 일 때의 값을 구하시오.

**정답**: `75`

**풀이**: x² + 10x 는 x = 5 에서 25 + 50 = 75 이다. 이를 (x+10)²으로 오인하면 (c+10)²로 틀린다.

**verify(SymPy 입력)**: conditions: `x = 5**2 + 10*5` · answer_map: {x=75}

**선지**:
- ① `25` ← 정답
- ② `50` ← 정답
- ③ `75` ← 정답
- ④ `225` ← 오답 · 오개념 `complete-square-naive`

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 46 · `wm-misc-eval-mc-3b8a76dfa0d5`

- 도메인: `CONE-VOLUME` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.3
- 성취기준: [9수03-08]

**문항**: 밑면의 반지름이 6, 높이가 24 인 원뿔의 부피를 원주율 π로 나눈 값을 구하시오.

**정답**: `288`

**풀이**: 원뿔의 부피는 ⅓×π×(반지름)²×높이 이므로 π로 나눈 값은 6²×24÷3 곧 288 이다. ⅓ 을 빠뜨려 원기둥 부피로 계산하면 864 가 되어 틀린다.

**verify(SymPy 입력)**: conditions: `x = 6**2*24/3` · answer_map: {x=288}

**선지**:
- ① `288` ← 정답
- ② `432` ← 정답
- ③ `576` ← 정답
- ④ `864` ← 오답 · 오개념 `cone-volume-no-third`

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 47 · `wm-misc-eval-mc-0d86997f6c35`

- 도메인: `CONE-VOLUME` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.1
- 성취기준: [9수03-08]

**문항**: 밑면의 반지름이 3, 높이가 14 인 원뿔의 부피를 원주율 π로 나눈 값을 구하시오.

**정답**: `42`

**풀이**: 원뿔의 부피는 ⅓×π×(반지름)²×높이 이므로 π로 나눈 값은 3²×14÷3 곧 42 이다. ⅓ 을 빠뜨려 원기둥 부피로 계산하면 126 가 되어 틀린다.

**verify(SymPy 입력)**: conditions: `x = 3**2*14/3` · answer_map: {x=42}

**선지**:
- ① `42` ← 정답
- ② `63` ← 정답
- ③ `84` ← 정답
- ④ `126` ← 오답 · 오개념 `cone-volume-no-third`

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 48 · `wm-misc-eval-mc-3e30ff78aa7f`

- 도메인: `CONE-VOLUME` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.8
- 성취기준: [9수03-08]

**문항**: 밑면의 반지름이 6, 높이가 19 인 원뿔의 부피를 원주율 π로 나눈 값을 구하시오.

**정답**: `228`

**풀이**: 원뿔의 부피는 ⅓×π×(반지름)²×높이 이므로 π로 나눈 값은 6²×19÷3 곧 228 이다. ⅓ 을 빠뜨려 원기둥 부피로 계산하면 684 가 되어 틀린다.

**verify(SymPy 입력)**: conditions: `x = 6**2*19/3` · answer_map: {x=228}

**선지**:
- ① `228` ← 정답
- ② `342` ← 정답
- ③ `456` ← 정답
- ④ `684` ← 오답 · 오개념 `cone-volume-no-third`

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 49 · `wm-misc-eval-mc-6baa4aaa58c8`

- 도메인: `CONE-VOLUME` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.4
- 성취기준: [9수03-08]

**문항**: 밑면의 반지름이 1, 높이가 30 인 원뿔의 부피를 원주율 π로 나눈 값을 구하시오.

**정답**: `10`

**풀이**: 원뿔의 부피는 ⅓×π×(반지름)²×높이 이므로 π로 나눈 값은 1²×30÷3 곧 10 이다. ⅓ 을 빠뜨려 원기둥 부피로 계산하면 30 가 되어 틀린다.

**verify(SymPy 입력)**: conditions: `x = 1**2*30/3` · answer_map: {x=10}

**선지**:
- ① `10` ← 정답
- ② `15` ← 정답
- ③ `20` ← 정답
- ④ `30` ← 오답 · 오개념 `cone-volume-no-third`

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 50 · `wm-misc-eval-mc-d8bf0bdeb1f2`

- 도메인: `CONE-VOLUME` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.5
- 성취기준: [9수03-08]

**문항**: 밑면의 반지름이 6, 높이가 16 인 원뿔의 부피를 원주율 π로 나눈 값을 구하시오.

**정답**: `192`

**풀이**: 원뿔의 부피는 ⅓×π×(반지름)²×높이 이므로 π로 나눈 값은 6²×16÷3 곧 192 이다. ⅓ 을 빠뜨려 원기둥 부피로 계산하면 576 가 되어 틀린다.

**verify(SymPy 입력)**: conditions: `x = 6**2*16/3` · answer_map: {x=192}

**선지**:
- ① `192` ← 정답
- ② `288` ← 정답
- ③ `384` ← 정답
- ④ `576` ← 오답 · 오개념 `cone-volume-no-third`

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 51 · `wm-misc-eval-mc-fdf52fb7014f`

- 도메인: `CONJUGATE-PRODUCT` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.6
- 성취기준: [9수01-07]

**문항**: (√12 + 1)(√12 - 1) 의 값을 구하시오.

**정답**: `11`

**풀이**: 켤레 무리수의 곱은 (√12)² - 1² = 12 - 1 = 11 이다. 합차공식 부호를 오용해 12 + 1로 답하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 12 - 1` · answer_map: {x=11}

**선지**:
- ① `11` ← 정답
- ② `12` ← 정답
- ③ `13` ← 오답 · 오개념 `conjugate-product-sum`
- ④ `24` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 52 · `wm-misc-eval-mc-3442752d71e4`

- 도메인: `CONJUGATE-PRODUCT` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3
- 성취기준: [9수01-07]

**문항**: (√27 + 1)(√27 - 1) 의 값을 구하시오.

**정답**: `26`

**풀이**: 켤레 무리수의 곱은 (√27)² - 1² = 27 - 1 = 26 이다. 합차공식 부호를 오용해 27 + 1로 답하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 27 - 1` · answer_map: {x=26}

**선지**:
- ① `26` ← 정답
- ② `27` ← 정답
- ③ `28` ← 오답 · 오개념 `conjugate-product-sum`
- ④ `54` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 53 · `wm-misc-eval-mc-a5216b8500ac`

- 도메인: `CONJUGATE-PRODUCT` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.4
- 성취기준: [9수01-07]

**문항**: (√20 + 1)(√20 - 1) 의 값을 구하시오.

**정답**: `19`

**풀이**: 켤레 무리수의 곱은 (√20)² - 1² = 20 - 1 = 19 이다. 합차공식 부호를 오용해 20 + 1로 답하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 20 - 1` · answer_map: {x=19}

**선지**:
- ① `19` ← 정답
- ② `20` ← 정답
- ③ `21` ← 오답 · 오개념 `conjugate-product-sum`
- ④ `40` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 54 · `wm-misc-eval-mc-ff13e0735b6c`

- 도메인: `CONJUGATE-PRODUCT` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.1
- 성취기준: [9수01-07]

**문항**: (√17 + 1)(√17 - 1) 의 값을 구하시오.

**정답**: `16`

**풀이**: 켤레 무리수의 곱은 (√17)² - 1² = 17 - 1 = 16 이다. 합차공식 부호를 오용해 17 + 1로 답하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 17 - 1` · answer_map: {x=16}

**선지**:
- ① `16` ← 정답
- ② `17` ← 정답
- ③ `18` ← 오답 · 오개념 `conjugate-product-sum`
- ④ `34` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 55 · `wm-misc-eval-mc-b0ab3f07f97c`

- 도메인: `CONJUGATE-PRODUCT` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.8
- 성취기준: [9수01-07]

**문항**: (√25 + 1)(√25 - 1) 의 값을 구하시오.

**정답**: `24`

**풀이**: 켤레 무리수의 곱은 (√25)² - 1² = 25 - 1 = 24 이다. 합차공식 부호를 오용해 25 + 1로 답하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 25 - 1` · answer_map: {x=24}

**선지**:
- ① `24` ← 정답
- ② `25` ← 정답
- ③ `26` ← 오답 · 오개념 `conjugate-product-sum`
- ④ `50` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 56 · `wm-misc-eval-mc-3cf80cb03830`

- 도메인: `DECIMAL-MULT` · 발문형식: 객관식 · 정답형식: 실수 · 난이도: 2.5
- 성취기준: [9수01-06]

**문항**: 0.2 × 0.9 의 값을 구하시오.

**정답**: `9/50`

**풀이**: 0.2 × 0.9 는 소수점 아래 자릿수를 더해 18/100 = 9/50 이다. 자릿수를 무시하면 18/10로 틀린다.

**verify(SymPy 입력)**: conditions: `x = 2*9/100` · answer_map: {x=9/50}

**선지**:
- ① `9/50` ← 정답
- ② `1/5` ← 정답
- ③ `9/10` ← 정답
- ④ `9/5` ← 오답 · 오개념 `decimal-mult-place`

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 57 · `wm-misc-eval-mc-7357f49bd1d4`

- 도메인: `DECIMAL-MULT` · 발문형식: 객관식 · 정답형식: 실수 · 난이도: 2.7
- 성취기준: [9수01-06]

**문항**: 0.5 × 0.8 의 값을 구하시오.

**정답**: `2/5`

**풀이**: 0.5 × 0.8 는 소수점 아래 자릿수를 더해 40/100 = 2/5 이다. 자릿수를 무시하면 40/10로 틀린다.

**verify(SymPy 입력)**: conditions: `x = 5*8/100` · answer_map: {x=2/5}

**선지**:
- ① `2/5` ← 정답
- ② `1/2` ← 정답
- ③ `4/5` ← 정답
- ④ `4` ← 오답 · 오개념 `decimal-mult-place`

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 58 · `wm-misc-eval-mc-dbbda5e77056`

- 도메인: `DECIMAL-MULT` · 발문형식: 객관식 · 정답형식: 실수 · 난이도: 3.4
- 성취기준: [9수01-06]

**문항**: 0.4 × 0.5 의 값을 구하시오.

**정답**: `1/5`

**풀이**: 0.4 × 0.5 는 소수점 아래 자릿수를 더해 20/100 = 1/5 이다. 자릿수를 무시하면 20/10로 틀린다.

**verify(SymPy 입력)**: conditions: `x = 4*5/100` · answer_map: {x=1/5}

**선지**:
- ① `1/5` ← 정답
- ② `2/5` ← 정답
- ③ `1/2` ← 정답
- ④ `2` ← 오답 · 오개념 `decimal-mult-place`

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 59 · `wm-misc-eval-mc-4556c6afb958`

- 도메인: `DECIMAL-MULT` · 발문형식: 객관식 · 정답형식: 실수 · 난이도: 3.1
- 성취기준: [9수01-06]

**문항**: 0.2 × 0.4 의 값을 구하시오.

**정답**: `2/25`

**풀이**: 0.2 × 0.4 는 소수점 아래 자릿수를 더해 8/100 = 2/25 이다. 자릿수를 무시하면 8/10로 틀린다.

**verify(SymPy 입력)**: conditions: `x = 2*4/100` · answer_map: {x=2/25}

**선지**:
- ① `2/25` ← 정답
- ② `1/5` ← 정답
- ③ `2/5` ← 정답
- ④ `4/5` ← 오답 · 오개념 `decimal-mult-place`

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 60 · `wm-misc-eval-mc-cebc0297895d`

- 도메인: `DECIMAL-MULT` · 발문형식: 객관식 · 정답형식: 실수 · 난이도: 2.9
- 성취기준: [9수01-06]

**문항**: 0.6 × 0.9 의 값을 구하시오.

**정답**: `27/50`

**풀이**: 0.6 × 0.9 는 소수점 아래 자릿수를 더해 54/100 = 27/50 이다. 자릿수를 무시하면 54/10로 틀린다.

**verify(SymPy 입력)**: conditions: `x = 6*9/100` · answer_map: {x=27/50}

**선지**:
- ① `27/50` ← 정답
- ② `3/5` ← 정답
- ③ `9/10` ← 정답
- ④ `27/5` ← 오답 · 오개념 `decimal-mult-place`

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 61 · `wm-misc-eval-mc-d513d4860a75`

- 도메인: `DIFF-SQUARES` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.5
- 성취기준: [9수01-01]

**문항**: x = 9, a = 1 일 때 x² - a² 의 값을 구하시오.

**정답**: `80`

**풀이**: x² - a² = (x-a)(x+a) 이므로 x=9, a=1 를 대입하면 80 이다. 제곱의 차를 차의 제곱 (x-a)²로 여기면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 80` · answer_map: {x=80}

**선지**:
- ① `64` ← 오답 · 오개념 `difference-of-squares-confused`
- ② `80` ← 정답
- ③ `82` ← 정답
- ④ `100` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 62 · `wm-misc-eval-mc-0e2e0cf72122`

- 도메인: `DIFF-SQUARES` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.6
- 성취기준: [9수01-01]

**문항**: x = 16, a = 7 일 때 x² - a² 의 값을 구하시오.

**정답**: `207`

**풀이**: x² - a² = (x-a)(x+a) 이므로 x=16, a=7 를 대입하면 207 이다. 제곱의 차를 차의 제곱 (x-a)²로 여기면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 207` · answer_map: {x=207}

**선지**:
- ① `81` ← 오답 · 오개념 `difference-of-squares-confused`
- ② `207` ← 정답
- ③ `305` ← 정답
- ④ `529` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 63 · `wm-misc-eval-mc-0d48d12855d6`

- 도메인: `DIFF-SQUARES` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.9
- 성취기준: [9수01-01]

**문항**: x = 14, a = 1 일 때 x² - a² 의 값을 구하시오.

**정답**: `195`

**풀이**: x² - a² = (x-a)(x+a) 이므로 x=14, a=1 를 대입하면 195 이다. 제곱의 차를 차의 제곱 (x-a)²로 여기면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 195` · answer_map: {x=195}

**선지**:
- ① `169` ← 오답 · 오개념 `difference-of-squares-confused`
- ② `195` ← 정답
- ③ `197` ← 정답
- ④ `225` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 64 · `wm-misc-eval-mc-8dcd375aca75`

- 도메인: `DIFF-SQUARES` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.2
- 성취기준: [9수01-01]

**문항**: x = 5, a = 2 일 때 x² - a² 의 값을 구하시오.

**정답**: `21`

**풀이**: x² - a² = (x-a)(x+a) 이므로 x=5, a=2 를 대입하면 21 이다. 제곱의 차를 차의 제곱 (x-a)²로 여기면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 21` · answer_map: {x=21}

**선지**:
- ① `9` ← 오답 · 오개념 `difference-of-squares-confused`
- ② `21` ← 정답
- ③ `29` ← 정답
- ④ `49` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 65 · `wm-misc-eval-mc-c4417eb5eef7`

- 도메인: `DIFF-SQUARES` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.1
- 성취기준: [9수01-01]

**문항**: x = 15, a = 2 일 때 x² - a² 의 값을 구하시오.

**정답**: `221`

**풀이**: x² - a² = (x-a)(x+a) 이므로 x=15, a=2 를 대입하면 221 이다. 제곱의 차를 차의 제곱 (x-a)²로 여기면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 221` · answer_map: {x=221}

**선지**:
- ① `169` ← 오답 · 오개념 `difference-of-squares-confused`
- ② `221` ← 정답
- ③ `229` ← 정답
- ④ `289` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 66 · `wm-misc-eval-mc-36638ab78abc`

- 도메인: `DISTRIBUTE-PARTIAL` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.1
- 성취기준: [9수02-09]

**문항**: 2(x + 7) 에서 x = 8 일 때의 값을 구하시오.

**정답**: `30`

**풀이**: 분배법칙으로 2(x + 7) = 2x + 14 이므로 x = 8 를 대입하면 30 이다. 뒷항을 분배하지 않고 16 + 7로 계산하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 2 * (8 + 7)` · answer_map: {x=30}

**선지**:
- ① `14` ← 정답
- ② `16` ← 정답
- ③ `23` ← 오답 · 오개념 `distribute-first-term-only`
- ④ `30` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 67 · `wm-misc-eval-mc-e9f9cede4ebe`

- 도메인: `DISTRIBUTE-PARTIAL` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.2
- 성취기준: [9수02-09]

**문항**: 3(x + 7) 에서 x = 8 일 때의 값을 구하시오.

**정답**: `45`

**풀이**: 분배법칙으로 3(x + 7) = 3x + 21 이므로 x = 8 를 대입하면 45 이다. 뒷항을 분배하지 않고 24 + 7로 계산하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 3 * (8 + 7)` · answer_map: {x=45}

**선지**:
- ① `21` ← 정답
- ② `24` ← 정답
- ③ `31` ← 오답 · 오개념 `distribute-first-term-only`
- ④ `45` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 68 · `wm-misc-eval-mc-5f18fea93c77`

- 도메인: `DISTRIBUTE-PARTIAL` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.9
- 성취기준: [9수02-09]

**문항**: 6(x + 2) 에서 x = 7 일 때의 값을 구하시오.

**정답**: `54`

**풀이**: 분배법칙으로 6(x + 2) = 6x + 12 이므로 x = 7 를 대입하면 54 이다. 뒷항을 분배하지 않고 42 + 2로 계산하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 6 * (7 + 2)` · answer_map: {x=54}

**선지**:
- ① `12` ← 정답
- ② `42` ← 정답
- ③ `44` ← 오답 · 오개념 `distribute-first-term-only`
- ④ `54` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 69 · `wm-misc-eval-mc-e05f082ccee2`

- 도메인: `DISTRIBUTE-PARTIAL` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.4
- 성취기준: [9수02-09]

**문항**: 5(x + 7) 에서 x = 8 일 때의 값을 구하시오.

**정답**: `75`

**풀이**: 분배법칙으로 5(x + 7) = 5x + 35 이므로 x = 8 를 대입하면 75 이다. 뒷항을 분배하지 않고 40 + 7로 계산하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 5 * (8 + 7)` · answer_map: {x=75}

**선지**:
- ① `35` ← 정답
- ② `40` ← 정답
- ③ `47` ← 오답 · 오개념 `distribute-first-term-only`
- ④ `75` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 70 · `wm-misc-eval-mc-83b6e540c6a4`

- 도메인: `DISTRIBUTE-PARTIAL` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.6
- 성취기준: [9수02-09]

**문항**: 4(x + 2) 에서 x = 6 일 때의 값을 구하시오.

**정답**: `32`

**풀이**: 분배법칙으로 4(x + 2) = 4x + 8 이므로 x = 6 를 대입하면 32 이다. 뒷항을 분배하지 않고 24 + 2로 계산하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 4 * (6 + 2)` · answer_map: {x=32}

**선지**:
- ① `8` ← 정답
- ② `24` ← 정답
- ③ `26` ← 오답 · 오개념 `distribute-first-term-only`
- ④ `32` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 71 · `wm-misc-eval-mc-eba4a8db014d`

- 도메인: `EXP-PRODUCT` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.2
- 성취기준: [9수02-08]

**문항**: 18 × 18² 의 값을 구하시오.

**정답**: `5832`

**풀이**: 밑이 같은 거듭제곱의 곱은 지수를 더하므로 18 × 18² = 18^(1+2) = 18³ = 5832 이다. 지수를 곱해 18² 로 답하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 18**3` · answer_map: {x=5832}

**선지**:
- ① `18` ← 정답
- ② `324` ← 오답 · 오개념 `exponent-product-multiplies`
- ③ `5832` ← 정답
- ④ `104976` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 72 · `wm-misc-eval-mc-6a05422170ba`

- 도메인: `EXP-PRODUCT` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.8
- 성취기준: [9수02-08]

**문항**: 25 × 25² 의 값을 구하시오.

**정답**: `15625`

**풀이**: 밑이 같은 거듭제곱의 곱은 지수를 더하므로 25 × 25² = 25^(1+2) = 25³ = 15625 이다. 지수를 곱해 25² 로 답하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 25**3` · answer_map: {x=15625}

**선지**:
- ① `25` ← 정답
- ② `625` ← 오답 · 오개념 `exponent-product-multiplies`
- ③ `15625` ← 정답
- ④ `390625` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 73 · `wm-misc-eval-mc-933e69216894`

- 도메인: `EXP-PRODUCT` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.6
- 성취기준: [9수02-08]

**문항**: 12 × 12² 의 값을 구하시오.

**정답**: `1728`

**풀이**: 밑이 같은 거듭제곱의 곱은 지수를 더하므로 12 × 12² = 12^(1+2) = 12³ = 1728 이다. 지수를 곱해 12² 로 답하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 12**3` · answer_map: {x=1728}

**선지**:
- ① `12` ← 정답
- ② `144` ← 오답 · 오개념 `exponent-product-multiplies`
- ③ `1728` ← 정답
- ④ `20736` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 74 · `wm-misc-eval-mc-32fd324739bd`

- 도메인: `EXP-PRODUCT` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.4
- 성취기준: [9수02-08]

**문항**: 20 × 20² 의 값을 구하시오.

**정답**: `8000`

**풀이**: 밑이 같은 거듭제곱의 곱은 지수를 더하므로 20 × 20² = 20^(1+2) = 20³ = 8000 이다. 지수를 곱해 20² 로 답하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 20**3` · answer_map: {x=8000}

**선지**:
- ① `20` ← 정답
- ② `400` ← 오답 · 오개념 `exponent-product-multiplies`
- ③ `8000` ← 정답
- ④ `160000` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 75 · `wm-misc-eval-mc-e90d0d0a7c53`

- 도메인: `EXP-PRODUCT` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3
- 성취기준: [9수02-08]

**문항**: 5 × 5² 의 값을 구하시오.

**정답**: `125`

**풀이**: 밑이 같은 거듭제곱의 곱은 지수를 더하므로 5 × 5² = 5^(1+2) = 5³ = 125 이다. 지수를 곱해 5² 로 답하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 5**3` · answer_map: {x=125}

**선지**:
- ① `5` ← 정답
- ② `25` ← 오답 · 오개념 `exponent-product-multiplies`
- ③ `125` ← 정답
- ④ `625` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 76 · `wm-misc-eval-mc-5c38950868fa`

- 도메인: `EXP-ZERO` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.5
- 성취기준: [9수02-08]

**문항**: 자연수 a = 3 에 대하여 29 + a^0 의 값을 구하시오.

**정답**: `30`

**풀이**: a^0 = 1 이므로 29 + a^0 = 29 + 1 = 30 이다. a^0 을 0 으로 잘못 계산하면 29 이 되어 틀린다.

**verify(SymPy 입력)**: conditions: `x = 29 + 3**0` · answer_map: {x=30}

**선지**:
- ① `29` ← 오답 · 오개념 `exponent-zero`
- ② `30` ← 정답
- ③ `31` ← 정답
- ④ `32` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 77 · `wm-misc-eval-mc-69d730b12ce2`

- 도메인: `EXP-ZERO` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.1
- 성취기준: [9수02-08]

**문항**: 자연수 a = 3 에 대하여 3 + a^0 의 값을 구하시오.

**정답**: `4`

**풀이**: a^0 = 1 이므로 3 + a^0 = 3 + 1 = 4 이다. a^0 을 0 으로 잘못 계산하면 3 이 되어 틀린다.

**verify(SymPy 입력)**: conditions: `x = 3 + 3**0` · answer_map: {x=4}

**선지**:
- ① `3` ← 오답 · 오개념 `exponent-zero`
- ② `4` ← 정답
- ③ `5` ← 정답
- ④ `6` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 78 · `wm-misc-eval-mc-98c224385f2b`

- 도메인: `EXP-ZERO` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.2
- 성취기준: [9수02-08]

**문항**: 자연수 a = 3 에 대하여 15 + a^0 의 값을 구하시오.

**정답**: `16`

**풀이**: a^0 = 1 이므로 15 + a^0 = 15 + 1 = 16 이다. a^0 을 0 으로 잘못 계산하면 15 이 되어 틀린다.

**verify(SymPy 입력)**: conditions: `x = 15 + 3**0` · answer_map: {x=16}

**선지**:
- ① `15` ← 오답 · 오개념 `exponent-zero`
- ② `16` ← 정답
- ③ `17` ← 정답
- ④ `18` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 79 · `wm-misc-eval-mc-4dbf11c67fd9`

- 도메인: `EXP-ZERO` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.5
- 성취기준: [9수02-08]

**문항**: 자연수 a = 3 에 대하여 8 + a^0 의 값을 구하시오.

**정답**: `9`

**풀이**: a^0 = 1 이므로 8 + a^0 = 8 + 1 = 9 이다. a^0 을 0 으로 잘못 계산하면 8 이 되어 틀린다.

**verify(SymPy 입력)**: conditions: `x = 8 + 3**0` · answer_map: {x=9}

**선지**:
- ① `8` ← 오답 · 오개념 `exponent-zero`
- ② `9` ← 정답
- ③ `10` ← 정답
- ④ `11` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 80 · `wm-misc-eval-mc-a634ced90779`

- 도메인: `EXP-ZERO` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.8
- 성취기준: [9수02-08]

**문항**: 자연수 a = 3 에 대하여 11 + a^0 의 값을 구하시오.

**정답**: `12`

**풀이**: a^0 = 1 이므로 11 + a^0 = 11 + 1 = 12 이다. a^0 을 0 으로 잘못 계산하면 11 이 되어 틀린다.

**verify(SymPy 입력)**: conditions: `x = 11 + 3**0` · answer_map: {x=12}

**선지**:
- ① `11` ← 오답 · 오개념 `exponent-zero`
- ② `12` ← 정답
- ③ `13` ← 정답
- ④ `14` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 81 · `wm-misc-eval-mc-fa746bba7864`

- 도메인: `FRACTION-ADD` · 발문형식: 객관식 · 정답형식: 분수 · 난이도: 3.3
- 성취기준: [9수01-04]

**문항**: 1/3 + 1/5 의 값을 구하시오.

**정답**: `8/15`

**풀이**: 1/3 + 1/5 는 통분하면 (3+5)/(3·5) = 8/15 이다. 통분 없이 분자·분모를 각각 더해 2/(p+q)로 답하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = (3+5)/(3*5)` · answer_map: {x=8/15}

**선지**:
- ① `1/5` ← 정답
- ② `1/4` ← 오답 · 오개념 `fraction-addition-naive`
- ③ `1/3` ← 정답
- ④ `8/15` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 82 · `wm-misc-eval-mc-30a38614e23f`

- 도메인: `FRACTION-ADD` · 발문형식: 객관식 · 정답형식: 분수 · 난이도: 2.7
- 성취기준: [9수01-04]

**문항**: 1/4 + 1/9 의 값을 구하시오.

**정답**: `13/36`

**풀이**: 1/4 + 1/9 는 통분하면 (4+9)/(4·9) = 13/36 이다. 통분 없이 분자·분모를 각각 더해 2/(p+q)로 답하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = (4+9)/(4*9)` · answer_map: {x=13/36}

**선지**:
- ① `1/9` ← 정답
- ② `2/13` ← 오답 · 오개념 `fraction-addition-naive`
- ③ `1/4` ← 정답
- ④ `13/36` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 83 · `wm-misc-eval-mc-90c83b683056`

- 도메인: `FRACTION-ADD` · 발문형식: 객관식 · 정답형식: 분수 · 난이도: 2.9
- 성취기준: [9수01-04]

**문항**: 1/4 + 1/11 의 값을 구하시오.

**정답**: `15/44`

**풀이**: 1/4 + 1/11 는 통분하면 (4+11)/(4·11) = 15/44 이다. 통분 없이 분자·분모를 각각 더해 2/(p+q)로 답하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = (4+11)/(4*11)` · answer_map: {x=15/44}

**선지**:
- ① `1/11` ← 정답
- ② `2/15` ← 오답 · 오개념 `fraction-addition-naive`
- ③ `1/4` ← 정답
- ④ `15/44` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 84 · `wm-misc-eval-mc-c24998378764`

- 도메인: `FRACTION-ADD` · 발문형식: 객관식 · 정답형식: 분수 · 난이도: 2.5
- 성취기준: [9수01-04]

**문항**: 1/3 + 1/8 의 값을 구하시오.

**정답**: `11/24`

**풀이**: 1/3 + 1/8 는 통분하면 (3+8)/(3·8) = 11/24 이다. 통분 없이 분자·분모를 각각 더해 2/(p+q)로 답하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = (3+8)/(3*8)` · answer_map: {x=11/24}

**선지**:
- ① `1/8` ← 정답
- ② `2/11` ← 오답 · 오개념 `fraction-addition-naive`
- ③ `1/3` ← 정답
- ④ `11/24` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 85 · `wm-misc-eval-mc-979f17825c65`

- 도메인: `FRACTION-ADD` · 발문형식: 객관식 · 정답형식: 분수 · 난이도: 3.1
- 성취기준: [9수01-04]

**문항**: 1/7 + 1/10 의 값을 구하시오.

**정답**: `17/70`

**풀이**: 1/7 + 1/10 는 통분하면 (7+10)/(7·10) = 17/70 이다. 통분 없이 분자·분모를 각각 더해 2/(p+q)로 답하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = (7+10)/(7*10)` · answer_map: {x=17/70}

**선지**:
- ① `1/10` ← 정답
- ② `2/17` ← 오답 · 오개념 `fraction-addition-naive`
- ③ `1/7` ← 정답
- ④ `17/70` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 86 · `wm-misc-eval-mc-59ba3a846b05`

- 도메인: `FRACTION-CANCEL` · 발문형식: 객관식 · 정답형식: 분수 · 난이도: 3.3
- 성취기준: [6수01-06], [9수01-04]

**문항**: 두 자연수 a = 5, b = 14 에 대하여 (a + b) / a 의 값을 구하시오.

**정답**: `19/5`

**풀이**: (a + b) / a = 1 + b/a 이므로 a = 5, b = 14 를 대입하면 19/5 이다. 분자와 분모의 a 를 지워 b 로 약분하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = (5+14)/5` · answer_map: {x=19/5}

**선지**:
- ① `19/5` ← 정답
- ② `5` ← 정답
- ③ `14` ← 오답 · 오개념 `fraction-cancellation`
- ④ `19` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 87 · `wm-misc-eval-mc-217d769cdf39`

- 도메인: `FRACTION-CANCEL` · 발문형식: 객관식 · 정답형식: 분수 · 난이도: 3.4
- 성취기준: [6수01-06], [9수01-04]

**문항**: 두 자연수 a = 5, b = 4 에 대하여 (a + b) / a 의 값을 구하시오.

**정답**: `9/5`

**풀이**: (a + b) / a = 1 + b/a 이므로 a = 5, b = 4 를 대입하면 9/5 이다. 분자와 분모의 a 를 지워 b 로 약분하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = (5+4)/5` · answer_map: {x=9/5}

**선지**:
- ① `9/5` ← 정답
- ② `4` ← 오답 · 오개념 `fraction-cancellation`
- ③ `5` ← 정답
- ④ `9` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 88 · `wm-misc-eval-mc-2bc199724f02`

- 도메인: `FRACTION-CANCEL` · 발문형식: 객관식 · 정답형식: 분수 · 난이도: 3
- 성취기준: [6수01-06], [9수01-04]

**문항**: 두 자연수 a = 3, b = 13 에 대하여 (a + b) / a 의 값을 구하시오.

**정답**: `16/3`

**풀이**: (a + b) / a = 1 + b/a 이므로 a = 3, b = 13 를 대입하면 16/3 이다. 분자와 분모의 a 를 지워 b 로 약분하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = (3+13)/3` · answer_map: {x=16/3}

**선지**:
- ① `3` ← 정답
- ② `16/3` ← 정답
- ③ `13` ← 오답 · 오개념 `fraction-cancellation`
- ④ `16` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 89 · `wm-misc-eval-mc-6ff81e773dc4`

- 도메인: `FRACTION-CANCEL` · 발문형식: 객관식 · 정답형식: 분수 · 난이도: 3.1
- 성취기준: [6수01-06], [9수01-04]

**문항**: 두 자연수 a = 4, b = 13 에 대하여 (a + b) / a 의 값을 구하시오.

**정답**: `17/4`

**풀이**: (a + b) / a = 1 + b/a 이므로 a = 4, b = 13 를 대입하면 17/4 이다. 분자와 분모의 a 를 지워 b 로 약분하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = (4+13)/4` · answer_map: {x=17/4}

**선지**:
- ① `4` ← 정답
- ② `17/4` ← 정답
- ③ `13` ← 오답 · 오개념 `fraction-cancellation`
- ④ `17` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 90 · `wm-misc-eval-mc-d39bbd1a1b01`

- 도메인: `FRACTION-CANCEL` · 발문형식: 객관식 · 정답형식: 분수 · 난이도: 2.5
- 성취기준: [6수01-06], [9수01-04]

**문항**: 두 자연수 a = 7, b = 4 에 대하여 (a + b) / a 의 값을 구하시오.

**정답**: `11/7`

**풀이**: (a + b) / a = 1 + b/a 이므로 a = 7, b = 4 를 대입하면 11/7 이다. 분자와 분모의 a 를 지워 b 로 약분하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = (7+4)/7` · answer_map: {x=11/7}

**선지**:
- ① `11/7` ← 정답
- ② `4` ← 오답 · 오개념 `fraction-cancellation`
- ③ `7` ← 정답
- ④ `11` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 91 · `wm-misc-eval-mc-77b7d2ad33aa`

- 도메인: `FUNC-COMPOSE` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.1
- 성취기준: [10공수2-03-02], [10기수2-03-02]

**문항**: 두 함수 f(x) = x + 1, g(x) = 2x 에 대하여 (f∘g)(3) 의 값을 구하시오.

**정답**: `7`

**풀이**: (f∘g)(3) = f(g(3)) = f(6) = 6 + 1 = 7 이다. 순서를 뒤집어 (g∘f)(3) = g(3+1) = 8 로 하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 2*3 + 1` · answer_map: {x=7}

**선지**:
- ① `6` ← 정답
- ② `7` ← 정답
- ③ `8` ← 오답 · 오개념 `composite-function-commutes`
- ④ `9` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 92 · `wm-misc-eval-mc-361329886831`

- 도메인: `FUNC-COMPOSE` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.8
- 성취기준: [10공수2-03-02], [10기수2-03-02]

**문항**: 두 함수 f(x) = x + 4, g(x) = 5x 에 대하여 (f∘g)(5) 의 값을 구하시오.

**정답**: `29`

**풀이**: (f∘g)(5) = f(g(5)) = f(25) = 25 + 4 = 29 이다. 순서를 뒤집어 (g∘f)(5) = g(5+4) = 45 로 하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 5*5 + 4` · answer_map: {x=29}

**선지**:
- ① `25` ← 정답
- ② `29` ← 정답
- ③ `34` ← 정답
- ④ `45` ← 오답 · 오개념 `composite-function-commutes`

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 93 · `wm-misc-eval-mc-2ffe87a9b836`

- 도메인: `FUNC-COMPOSE` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.5
- 성취기준: [10공수2-03-02], [10기수2-03-02]

**문항**: 두 함수 f(x) = x + 1, g(x) = 4x 에 대하여 (f∘g)(5) 의 값을 구하시오.

**정답**: `21`

**풀이**: (f∘g)(5) = f(g(5)) = f(20) = 20 + 1 = 21 이다. 순서를 뒤집어 (g∘f)(5) = g(5+1) = 24 로 하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 4*5 + 1` · answer_map: {x=21}

**선지**:
- ① `20` ← 정답
- ② `21` ← 정답
- ③ `24` ← 오답 · 오개념 `composite-function-commutes`
- ④ `25` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 94 · `wm-misc-eval-mc-dea4f43b2883`

- 도메인: `FUNC-COMPOSE` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.3
- 성취기준: [10공수2-03-02], [10기수2-03-02]

**문항**: 두 함수 f(x) = x + 1, g(x) = 2x 에 대하여 (f∘g)(5) 의 값을 구하시오.

**정답**: `11`

**풀이**: (f∘g)(5) = f(g(5)) = f(10) = 10 + 1 = 11 이다. 순서를 뒤집어 (g∘f)(5) = g(5+1) = 12 로 하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 2*5 + 1` · answer_map: {x=11}

**선지**:
- ① `10` ← 정답
- ② `11` ← 정답
- ③ `12` ← 오답 · 오개념 `composite-function-commutes`
- ④ `13` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 95 · `wm-misc-eval-mc-a8339373cd7d`

- 도메인: `FUNC-COMPOSE` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.5
- 성취기준: [10공수2-03-02], [10기수2-03-02]

**문항**: 두 함수 f(x) = x + 1, g(x) = 4x 에 대하여 (f∘g)(6) 의 값을 구하시오.

**정답**: `25`

**풀이**: (f∘g)(6) = f(g(6)) = f(24) = 24 + 1 = 25 이다. 순서를 뒤집어 (g∘f)(6) = g(6+1) = 28 로 하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 4*6 + 1` · answer_map: {x=25}

**선지**:
- ① `24` ← 정답
- ② `25` ← 정답
- ③ `28` ← 오답 · 오개념 `composite-function-commutes`
- ④ `29` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 96 · `wm-misc-eval-mc-c558d5f5bd9f`

- 도메인: `FUNC-TRANSLATE` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.3
- 성취기준: [10공수2-01-06], [10기수2-01-06]

**문항**: 함수 f(x) = x^2 + 3x 에 대하여 g(x) = f(x - 1) 일 때, g(6) 의 값을 구하시오.

**정답**: `40`

**풀이**: y = f(x-1) 은 그래프를 오른쪽으로 1 평행이동한 것이므로 g(6) = f(6-1) = f(5) = 40 이다. 부호를 뒤집어 f(6+1) 로 계산하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 5**2 + 3*5` · answer_map: {x=40}

**선지**:
- ① `25` ← 정답
- ② `40` ← 정답
- ③ `54` ← 정답
- ④ `70` ← 오답 · 오개념 `translation-sign-flip`

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 97 · `wm-misc-eval-mc-7fff461a517e`

- 도메인: `FUNC-TRANSLATE` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.8
- 성취기준: [10공수2-01-06], [10기수2-01-06]

**문항**: 함수 f(x) = x^2 + 1x 에 대하여 g(x) = f(x - 1) 일 때, g(3) 의 값을 구하시오.

**정답**: `6`

**풀이**: y = f(x-1) 은 그래프를 오른쪽으로 1 평행이동한 것이므로 g(3) = f(3-1) = f(2) = 6 이다. 부호를 뒤집어 f(3+1) 로 계산하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 2**2 + 1*2` · answer_map: {x=6}

**선지**:
- ① `4` ← 정답
- ② `6` ← 정답
- ③ `12` ← 정답
- ④ `20` ← 오답 · 오개념 `translation-sign-flip`

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 98 · `wm-misc-eval-mc-08a02a565afd`

- 도메인: `FUNC-TRANSLATE` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3
- 성취기준: [10공수2-01-06], [10기수2-01-06]

**문항**: 함수 f(x) = x^2 + 2x 에 대하여 g(x) = f(x - 1) 일 때, g(4) 의 값을 구하시오.

**정답**: `15`

**풀이**: y = f(x-1) 은 그래프를 오른쪽으로 1 평행이동한 것이므로 g(4) = f(4-1) = f(3) = 15 이다. 부호를 뒤집어 f(4+1) 로 계산하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 3**2 + 2*3` · answer_map: {x=15}

**선지**:
- ① `9` ← 정답
- ② `15` ← 정답
- ③ `24` ← 정답
- ④ `35` ← 오답 · 오개념 `translation-sign-flip`

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 99 · `wm-misc-eval-mc-192f1d1583b4`

- 도메인: `FUNC-TRANSLATE` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.4
- 성취기준: [10공수2-01-06], [10기수2-01-06]

**문항**: 함수 f(x) = x^2 + 2x 에 대하여 g(x) = f(x - 1) 일 때, g(8) 의 값을 구하시오.

**정답**: `63`

**풀이**: y = f(x-1) 은 그래프를 오른쪽으로 1 평행이동한 것이므로 g(8) = f(8-1) = f(7) = 63 이다. 부호를 뒤집어 f(8+1) 로 계산하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 7**2 + 2*7` · answer_map: {x=63}

**선지**:
- ① `49` ← 정답
- ② `63` ← 정답
- ③ `80` ← 정답
- ④ `99` ← 오답 · 오개념 `translation-sign-flip`

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 100 · `wm-misc-eval-mc-3c5be5ef91a5`

- 도메인: `FUNC-TRANSLATE` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.1
- 성취기준: [10공수2-01-06], [10기수2-01-06]

**문항**: 함수 f(x) = x^2 + 1x 에 대하여 g(x) = f(x - 1) 일 때, g(6) 의 값을 구하시오.

**정답**: `30`

**풀이**: y = f(x-1) 은 그래프를 오른쪽으로 1 평행이동한 것이므로 g(6) = f(6-1) = f(5) = 30 이다. 부호를 뒤집어 f(6+1) 로 계산하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 5**2 + 1*5` · answer_map: {x=30}

**선지**:
- ① `25` ← 정답
- ② `30` ← 정답
- ③ `42` ← 정답
- ④ `56` ← 오답 · 오개념 `translation-sign-flip`

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 101 · `wm-misc-eval-mc-0aabd9404f73`

- 도메인: `GCD-LCM` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.6
- 성취기준: [9수01-02]

**문항**: 10 와 13 의 최소공배수를 구하시오.

**정답**: `130`

**풀이**: 10와 13의 최소공배수는 130 이다(최대공약수는 1). 최소공배수와 최대공약수를 혼동하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 130` · answer_map: {x=130}

**선지**:
- ① `1` ← 오답 · 오개념 `gcd-lcm-confused`
- ② `10` ← 정답
- ③ `13` ← 정답
- ④ `130` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 102 · `wm-misc-eval-mc-a845d39d5e1f`

- 도메인: `GCD-LCM` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.2
- 성취기준: [9수01-02]

**문항**: 12 와 17 의 최소공배수를 구하시오.

**정답**: `204`

**풀이**: 12와 17의 최소공배수는 204 이다(최대공약수는 1). 최소공배수와 최대공약수를 혼동하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 204` · answer_map: {x=204}

**선지**:
- ① `1` ← 오답 · 오개념 `gcd-lcm-confused`
- ② `12` ← 정답
- ③ `17` ← 정답
- ④ `204` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 103 · `wm-misc-eval-mc-600642193907`

- 도메인: `GCD-LCM` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.8
- 성취기준: [9수01-02]

**문항**: 12 와 13 의 최소공배수를 구하시오.

**정답**: `156`

**풀이**: 12와 13의 최소공배수는 156 이다(최대공약수는 1). 최소공배수와 최대공약수를 혼동하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 156` · answer_map: {x=156}

**선지**:
- ① `1` ← 오답 · 오개념 `gcd-lcm-confused`
- ② `12` ← 정답
- ③ `13` ← 정답
- ④ `156` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 104 · `wm-misc-eval-mc-cfbab8dd7491`

- 도메인: `GCD-LCM` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.4
- 성취기준: [9수01-02]

**문항**: 2 와 7 의 최소공배수를 구하시오.

**정답**: `14`

**풀이**: 2와 7의 최소공배수는 14 이다(최대공약수는 1). 최소공배수와 최대공약수를 혼동하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 14` · answer_map: {x=14}

**선지**:
- ① `1` ← 오답 · 오개념 `gcd-lcm-confused`
- ② `2` ← 정답
- ③ `7` ← 정답
- ④ `14` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 105 · `wm-misc-eval-mc-0b034bc5981b`

- 도메인: `LOG-DIST` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.1
- 성취기준: [12대수01-04], [12대수01-05]

**문항**: log_2(2^6 + 2^6) 의 값을 구하시오.

**정답**: `7`

**풀이**: 2^6 + 2^6 = 2·2^6 = 2^7 이므로 값은 7 이다. 로그를 합에 분배해 6+6 = 12 로 하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = log(2**6 + 2**6, 2)` · answer_map: {x=7}

**선지**:
- ① `6` ← 정답
- ② `7` ← 정답
- ③ `12` ← 오답 · 오개념 `log-distribution`
- ④ `13` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 106 · `wm-misc-eval-mc-b077c9d812f3`

- 도메인: `LOG-DIST` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.9
- 성취기준: [12대수01-04], [12대수01-05]

**문항**: log_2(2^26 + 2^26) 의 값을 구하시오.

**정답**: `27`

**풀이**: 2^26 + 2^26 = 2·2^26 = 2^27 이므로 값은 27 이다. 로그를 합에 분배해 26+26 = 52 로 하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = log(2**26 + 2**26, 2)` · answer_map: {x=27}

**선지**:
- ① `26` ← 정답
- ② `27` ← 정답
- ③ `52` ← 오답 · 오개념 `log-distribution`
- ④ `53` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 107 · `wm-misc-eval-mc-da51b532c81f`

- 도메인: `LOG-DIST` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.4
- 성취기준: [12대수01-04], [12대수01-05]

**문항**: log_2(2^20 + 2^20) 의 값을 구하시오.

**정답**: `21`

**풀이**: 2^20 + 2^20 = 2·2^20 = 2^21 이므로 값은 21 이다. 로그를 합에 분배해 20+20 = 40 로 하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = log(2**20 + 2**20, 2)` · answer_map: {x=21}

**선지**:
- ① `20` ← 정답
- ② `21` ← 정답
- ③ `40` ← 오답 · 오개념 `log-distribution`
- ④ `41` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 108 · `wm-misc-eval-mc-3b26e72077c4`

- 도메인: `LOG-DIST` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.6
- 성취기준: [12대수01-04], [12대수01-05]

**문항**: log_2(2^12 + 2^12) 의 값을 구하시오.

**정답**: `13`

**풀이**: 2^12 + 2^12 = 2·2^12 = 2^13 이므로 값은 13 이다. 로그를 합에 분배해 12+12 = 24 로 하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = log(2**12 + 2**12, 2)` · answer_map: {x=13}

**선지**:
- ① `12` ← 정답
- ② `13` ← 정답
- ③ `24` ← 오답 · 오개념 `log-distribution`
- ④ `25` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 109 · `wm-misc-eval-mc-8c480263e41b`

- 도메인: `MIDPOINT-NO-HALF` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.9
- 성취기준: [9수02-05]

**문항**: 수직선 위 두 점 1, 3 의 중점의 좌표를 구하시오.

**정답**: `2`

**풀이**: 두 점의 중점은 좌표의 평균이므로 (1+3)/2 = 2 이다. 2로 나누지 않고 4로 답하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = (1+3)/2` · answer_map: {x=2}

**선지**:
- ① `1` ← 정답
- ② `2` ← 정답
- ③ `3` ← 정답
- ④ `4` ← 오답 · 오개념 `midpoint-sum-only`

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 110 · `wm-misc-eval-mc-f2ccca97906d`

- 도메인: `MIDPOINT-NO-HALF` · 발문형식: 객관식 · 정답형식: 분수 · 난이도: 3.1
- 성취기준: [9수02-05]

**문항**: 수직선 위 두 점 1, 16 의 중점의 좌표를 구하시오.

**정답**: `17/2`

**풀이**: 두 점의 중점은 좌표의 평균이므로 (1+16)/2 = 17/2 이다. 2로 나누지 않고 17로 답하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = (1+16)/2` · answer_map: {x=17/2}

**선지**:
- ① `1` ← 정답
- ② `17/2` ← 정답
- ③ `16` ← 정답
- ④ `17` ← 오답 · 오개념 `midpoint-sum-only`

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 111 · `wm-misc-eval-mc-e06604beeb25`

- 도메인: `MIDPOINT-NO-HALF` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.4
- 성취기준: [9수02-05]

**문항**: 수직선 위 두 점 1, 19 의 중점의 좌표를 구하시오.

**정답**: `10`

**풀이**: 두 점의 중점은 좌표의 평균이므로 (1+19)/2 = 10 이다. 2로 나누지 않고 20로 답하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = (1+19)/2` · answer_map: {x=10}

**선지**:
- ① `1` ← 정답
- ② `10` ← 정답
- ③ `19` ← 정답
- ④ `20` ← 오답 · 오개념 `midpoint-sum-only`

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 112 · `wm-misc-eval-mc-8a34a78a26bb`

- 도메인: `MIDPOINT-NO-HALF` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.6
- 성취기준: [9수02-05]

**문항**: 수직선 위 두 점 1, 11 의 중점의 좌표를 구하시오.

**정답**: `6`

**풀이**: 두 점의 중점은 좌표의 평균이므로 (1+11)/2 = 6 이다. 2로 나누지 않고 12로 답하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = (1+11)/2` · answer_map: {x=6}

**선지**:
- ① `1` ← 정답
- ② `6` ← 정답
- ③ `11` ← 정답
- ④ `12` ← 오답 · 오개념 `midpoint-sum-only`

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 113 · `wm-misc-eval-mc-51ad78f8b69e`

- 도메인: `MIXED-MULT` · 발문형식: 객관식 · 정답형식: 분수 · 난이도: 3.5
- 성취기준: [9수01-04]

**문항**: 5과 1/2 (대분수)에 5 을 곱한 값을 구하시오.

**정답**: `55/2`

**풀이**: 대분수 5½ = 11/2 에 5을 곱하면 55/2 = 55/2 이다. 정수부만 곱해 25½로 답하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = (11*5)/2` · answer_map: {x=55/2}

**선지**:
- ① `11/2` ← 정답
- ② `25` ← 정답
- ③ `51/2` ← 오답 · 오개념 `mixed-number-mult-whole`
- ④ `55/2` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 114 · `wm-misc-eval-mc-94d2b127b4aa`

- 도메인: `MIXED-MULT` · 발문형식: 객관식 · 정답형식: 분수 · 난이도: 2.6
- 성취기준: [9수01-04]

**문항**: 7과 1/2 (대분수)에 5 을 곱한 값을 구하시오.

**정답**: `75/2`

**풀이**: 대분수 7½ = 15/2 에 5을 곱하면 75/2 = 75/2 이다. 정수부만 곱해 35½로 답하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = (15*5)/2` · answer_map: {x=75/2}

**선지**:
- ① `15/2` ← 정답
- ② `35` ← 정답
- ③ `71/2` ← 오답 · 오개념 `mixed-number-mult-whole`
- ④ `75/2` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 115 · `wm-misc-eval-mc-bb15854a3f6c`

- 도메인: `MIXED-MULT` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3
- 성취기준: [9수01-04]

**문항**: 3과 1/2 (대분수)에 2 을 곱한 값을 구하시오.

**정답**: `7`

**풀이**: 대분수 3½ = 7/2 에 2을 곱하면 14/2 = 7 이다. 정수부만 곱해 6½로 답하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = (7*2)/2` · answer_map: {x=7}

**선지**:
- ① `7/2` ← 정답
- ② `6` ← 정답
- ③ `13/2` ← 오답 · 오개념 `mixed-number-mult-whole`
- ④ `7` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 116 · `wm-misc-eval-mc-b738aff4e855`

- 도메인: `MIXED-MULT` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.8
- 성취기준: [9수01-04]

**문항**: 6과 1/2 (대분수)에 8 을 곱한 값을 구하시오.

**정답**: `52`

**풀이**: 대분수 6½ = 13/2 에 8을 곱하면 104/2 = 52 이다. 정수부만 곱해 48½로 답하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = (13*8)/2` · answer_map: {x=52}

**선지**:
- ① `13/2` ← 정답
- ② `48` ← 정답
- ③ `97/2` ← 오답 · 오개념 `mixed-number-mult-whole`
- ④ `52` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 117 · `wm-misc-eval-mc-98d2c36eeaea`

- 도메인: `NEG-DISTRIBUTE` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.2
- 성취기준: [9수02-09]

**문항**: -(x - 5) 에서 x = 2 일 때의 값을 구하시오.

**정답**: `3`

**풀이**: 음의 부호 분배는 -(x - 5) = -x + 5 이므로 x = 2 를 대입하면 3 이다. 뒷항 부호를 반전하지 않고 -2 - 5로 계산하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 5 - 2` · answer_map: {x=3}

**선지**:
- ① `-7` ← 오답 · 오개념 `negative-distribute-sign`
- ② `-3` ← 정답
- ③ `3` ← 정답
- ④ `7` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 118 · `wm-misc-eval-mc-4bd5ac65d2d8`

- 도메인: `NEG-DISTRIBUTE` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.5
- 성취기준: [9수02-09]

**문항**: -(x - 19) 에서 x = 2 일 때의 값을 구하시오.

**정답**: `17`

**풀이**: 음의 부호 분배는 -(x - 19) = -x + 19 이므로 x = 2 를 대입하면 17 이다. 뒷항 부호를 반전하지 않고 -2 - 19로 계산하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 19 - 2` · answer_map: {x=17}

**선지**:
- ① `-21` ← 오답 · 오개념 `negative-distribute-sign`
- ② `-17` ← 정답
- ③ `17` ← 정답
- ④ `21` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 119 · `wm-misc-eval-mc-adc92ee70b90`

- 도메인: `NEG-DISTRIBUTE` · 발문형식: 객관식 · 정답형식: 분수 · 난이도: 2.9
- 성취기준: [9수02-09]

**문항**: -(x - 2) 에서 x = 13 일 때의 값을 구하시오.

**정답**: `-11`

**풀이**: 음의 부호 분배는 -(x - 2) = -x + 2 이므로 x = 13 를 대입하면 -11 이다. 뒷항 부호를 반전하지 않고 -13 - 2로 계산하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 2 - 13` · answer_map: {x=-11}

**선지**:
- ① `-15` ← 오답 · 오개념 `negative-distribute-sign`
- ② `-11` ← 정답
- ③ `11` ← 정답
- ④ `15` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 120 · `wm-misc-eval-mc-2f2b08f73981`

- 도메인: `NEG-DISTRIBUTE` · 발문형식: 객관식 · 정답형식: 분수 · 난이도: 2.6
- 성취기준: [9수02-09]

**문항**: -(x - 2) 에서 x = 10 일 때의 값을 구하시오.

**정답**: `-8`

**풀이**: 음의 부호 분배는 -(x - 2) = -x + 2 이므로 x = 10 를 대입하면 -8 이다. 뒷항 부호를 반전하지 않고 -10 - 2로 계산하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 2 - 10` · answer_map: {x=-8}

**선지**:
- ① `-12` ← 오답 · 오개념 `negative-distribute-sign`
- ② `-8` ← 정답
- ③ `8` ← 정답
- ④ `12` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 121 · `wm-misc-eval-mc-bfd5527a8a17`

- 도메인: `NEG-EVEN-POWER` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.6
- 성취기준: [9수02-08]

**문항**: (-6)^6 의 값을 구하시오.

**정답**: `46656`

**풀이**: 음수의 짝수 거듭제곱은 양수이므로 (-6)^6 = 6^6 = 46656 이다. 음수로 여겨 -46656로 답하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 6**6` · answer_map: {x=46656}

**선지**:
- ① `-46656` ← 오답 · 오개념 `negative-even-power-sign`
- ② `-6` ← 정답
- ③ `6` ← 정답
- ④ `46656` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 122 · `wm-misc-eval-mc-fd1bcb5e9d6b`

- 도메인: `NEG-EVEN-POWER` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.8
- 성취기준: [9수02-08]

**문항**: (-12)^2 의 값을 구하시오.

**정답**: `144`

**풀이**: 음수의 짝수 거듭제곱은 양수이므로 (-12)^2 = 12^2 = 144 이다. 음수로 여겨 -144로 답하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 12**2` · answer_map: {x=144}

**선지**:
- ① `-144` ← 오답 · 오개념 `negative-even-power-sign`
- ② `-12` ← 정답
- ③ `12` ← 정답
- ④ `144` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 123 · `wm-misc-eval-mc-deb4100afa60`

- 도메인: `NEG-EVEN-POWER` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.2
- 성취기준: [9수02-08]

**문항**: (-16)^2 의 값을 구하시오.

**정답**: `256`

**풀이**: 음수의 짝수 거듭제곱은 양수이므로 (-16)^2 = 16^2 = 256 이다. 음수로 여겨 -256로 답하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 16**2` · answer_map: {x=256}

**선지**:
- ① `-256` ← 오답 · 오개념 `negative-even-power-sign`
- ② `-16` ← 정답
- ③ `16` ← 정답
- ④ `256` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 124 · `wm-misc-eval-mc-6c91946cc861`

- 도메인: `NEG-EVEN-POWER` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.4
- 성취기준: [9수02-08]

**문항**: (-18)^2 의 값을 구하시오.

**정답**: `324`

**풀이**: 음수의 짝수 거듭제곱은 양수이므로 (-18)^2 = 18^2 = 324 이다. 음수로 여겨 -324로 답하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 18**2` · answer_map: {x=324}

**선지**:
- ① `-324` ← 오답 · 오개념 `negative-even-power-sign`
- ② `-18` ← 정답
- ③ `18` ← 정답
- ④ `324` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 125 · `wm-misc-eval-mc-8745305ca760`

- 도메인: `NEG-PRODUCT` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.7
- 성취기준: [9수01-03]

**문항**: (-6) × (-7) 의 값을 구하시오.

**정답**: `42`

**풀이**: 음수끼리의 곱은 양수이므로 (-6)×(-7) = 42 이다. 음수끼리 곱해도 음수라고 여기면 부호를 틀린다.

**verify(SymPy 입력)**: conditions: `x = (6)*(7)` · answer_map: {x=42}

**선지**:
- ① `-42` ← 오답 · 오개념 `negative-times-negative`
- ② `-13` ← 정답
- ③ `13` ← 정답
- ④ `42` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 126 · `wm-misc-eval-mc-effa1c08bf01`

- 도메인: `NEG-PRODUCT` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.4
- 성취기준: [9수01-03]

**문항**: (-7) × (-13) 의 값을 구하시오.

**정답**: `91`

**풀이**: 음수끼리의 곱은 양수이므로 (-7)×(-13) = 91 이다. 음수끼리 곱해도 음수라고 여기면 부호를 틀린다.

**verify(SymPy 입력)**: conditions: `x = (7)*(13)` · answer_map: {x=91}

**선지**:
- ① `-91` ← 오답 · 오개념 `negative-times-negative`
- ② `-20` ← 정답
- ③ `20` ← 정답
- ④ `91` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 127 · `wm-misc-eval-mc-bc2945ff2f99`

- 도메인: `NEG-PRODUCT` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.9
- 성취기준: [9수01-03]

**문항**: (-3) × (-12) 의 값을 구하시오.

**정답**: `36`

**풀이**: 음수끼리의 곱은 양수이므로 (-3)×(-12) = 36 이다. 음수끼리 곱해도 음수라고 여기면 부호를 틀린다.

**verify(SymPy 입력)**: conditions: `x = (3)*(12)` · answer_map: {x=36}

**선지**:
- ① `-36` ← 오답 · 오개념 `negative-times-negative`
- ② `-15` ← 정답
- ③ `15` ← 정답
- ④ `36` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 128 · `wm-misc-eval-mc-6061b1110645`

- 도메인: `NEG-PRODUCT` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.2
- 성취기준: [9수01-03]

**문항**: (-5) × (-13) 의 값을 구하시오.

**정답**: `65`

**풀이**: 음수끼리의 곱은 양수이므로 (-5)×(-13) = 65 이다. 음수끼리 곱해도 음수라고 여기면 부호를 틀린다.

**verify(SymPy 입력)**: conditions: `x = (5)*(13)` · answer_map: {x=65}

**선지**:
- ① `-65` ← 오답 · 오개념 `negative-times-negative`
- ② `-18` ← 정답
- ③ `18` ← 정답
- ④ `65` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 129 · `wm-misc-eval-mc-b6ec99a9f169`

- 도메인: `NEG-SQUARE` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.5
- 성취기준: [9수02-08]

**문항**: -2² + 8 의 값을 구하시오.

**정답**: `4`

**풀이**: 거듭제곱이 부호보다 우선하므로 -2² = -4 이고 -2² + 8 = 4 이다. -2²을 (-2)²=4로 계산하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 8 - 4` · answer_map: {x=4}

**선지**:
- ① `-12` ← 정답
- ② `-4` ← 정답
- ③ `4` ← 정답
- ④ `12` ← 오답 · 오개념 `negative-square-precedence`

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 130 · `wm-misc-eval-mc-971906fc960c`

- 도메인: `NEG-SQUARE` · 발문형식: 객관식 · 정답형식: 분수 · 난이도: 2.6
- 성취기준: [9수02-08]

**문항**: -7² + 5 의 값을 구하시오.

**정답**: `-44`

**풀이**: 거듭제곱이 부호보다 우선하므로 -7² = -49 이고 -7² + 5 = -44 이다. -7²을 (-7)²=49로 계산하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 5 - 49` · answer_map: {x=-44}

**선지**:
- ① `-54` ← 정답
- ② `-44` ← 정답
- ③ `44` ← 정답
- ④ `54` ← 오답 · 오개념 `negative-square-precedence`

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 131 · `wm-misc-eval-mc-4f4b47f02581`

- 도메인: `NEG-SQUARE` · 발문형식: 객관식 · 정답형식: 분수 · 난이도: 2.9
- 성취기준: [9수02-08]

**문항**: -9² + 6 의 값을 구하시오.

**정답**: `-75`

**풀이**: 거듭제곱이 부호보다 우선하므로 -9² = -81 이고 -9² + 6 = -75 이다. -9²을 (-9)²=81로 계산하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 6 - 81` · answer_map: {x=-75}

**선지**:
- ① `-87` ← 정답
- ② `-75` ← 정답
- ③ `75` ← 정답
- ④ `87` ← 오답 · 오개념 `negative-square-precedence`

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 132 · `wm-misc-eval-mc-51a1ad2b2136`

- 도메인: `NEG-SQUARE` · 발문형식: 객관식 · 정답형식: 분수 · 난이도: 3.2
- 성취기준: [9수02-08]

**문항**: -4² + 3 의 값을 구하시오.

**정답**: `-13`

**풀이**: 거듭제곱이 부호보다 우선하므로 -4² = -16 이고 -4² + 3 = -13 이다. -4²을 (-4)²=16로 계산하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 3 - 16` · answer_map: {x=-13}

**선지**:
- ① `-19` ← 정답
- ② `-13` ← 정답
- ③ `13` ← 정답
- ④ `19` ← 오답 · 오개념 `negative-square-precedence`

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 133 · `wm-misc-eval-mc-4827cb60f072`

- 도메인: `POLY-PRODUCT` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.2
- 성취기준: [9수02-19]

**문항**: 두 수 a, b에 대하여 a = 2, b = 5 일 때, (a+b)^2 의 값을 구하시오.

**정답**: `49`

**풀이**: (a+b)^2 = a^2 + 2ab + b^2 이므로 a = 2, b = 5 를 대입하면 (a+b)^2 = 49 이다. 교차항 2ab 를 빠뜨리면 a^2+b^2 가 되어 틀린다.

**verify(SymPy 입력)**: conditions: `x = (2+5)**2` · answer_map: {x=49}

**선지**:
- ① `20` ← 정답
- ② `29` ← 오답 · 오개념 `distribution-over-power` (op: `power-distributed-no-cross-term`)
- ③ `39` ← 정답
- ④ `49` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 134 · `wm-misc-eval-mc-666755947fdf`

- 도메인: `POLY-PRODUCT` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.4
- 성취기준: [9수02-19]

**문항**: 두 수 a, b에 대하여 a = 2, b = 7 일 때, (a+b)^2 의 값을 구하시오.

**정답**: `81`

**풀이**: (a+b)^2 = a^2 + 2ab + b^2 이므로 a = 2, b = 7 를 대입하면 (a+b)^2 = 81 이다. 교차항 2ab 를 빠뜨리면 a^2+b^2 가 되어 틀린다.

**verify(SymPy 입력)**: conditions: `x = (2+7)**2` · answer_map: {x=81}

**선지**:
- ① `28` ← 정답
- ② `53` ← 오답 · 오개념 `distribution-over-power` (op: `power-distributed-no-cross-term`)
- ③ `67` ← 정답
- ④ `81` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 135 · `wm-misc-eval-mc-95a2eaa7b769`

- 도메인: `POLY-PRODUCT` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.9
- 성취기준: [9수02-19]

**문항**: 두 수 a, b에 대하여 a = 2, b = 13 일 때, (a+b)^2 의 값을 구하시오.

**정답**: `225`

**풀이**: (a+b)^2 = a^2 + 2ab + b^2 이므로 a = 2, b = 13 를 대입하면 (a+b)^2 = 225 이다. 교차항 2ab 를 빠뜨리면 a^2+b^2 가 되어 틀린다.

**verify(SymPy 입력)**: conditions: `x = (2+13)**2` · answer_map: {x=225}

**선지**:
- ① `52` ← 정답
- ② `173` ← 오답 · 오개념 `distribution-over-power` (op: `power-distributed-no-cross-term`)
- ③ `199` ← 정답
- ④ `225` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 136 · `wm-misc-eval-mc-9ff41a1611d9`

- 도메인: `POLY-PRODUCT` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.6
- 성취기준: [9수02-19]

**문항**: 두 수 a, b에 대하여 a = 2, b = 10 일 때, (a+b)^2 의 값을 구하시오.

**정답**: `144`

**풀이**: (a+b)^2 = a^2 + 2ab + b^2 이므로 a = 2, b = 10 를 대입하면 (a+b)^2 = 144 이다. 교차항 2ab 를 빠뜨리면 a^2+b^2 가 되어 틀린다.

**verify(SymPy 입력)**: conditions: `x = (2+10)**2` · answer_map: {x=144}

**선지**:
- ① `40` ← 정답
- ② `104` ← 오답 · 오개념 `distribution-over-power` (op: `power-distributed-no-cross-term`)
- ③ `124` ← 정답
- ④ `144` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 137 · `wm-misc-eval-mc-d3aede4d4398`

- 도메인: `POLYGON-ANGLE-SUM` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.4
- 성취기준: [4수03-25], [9수03-03], [9수03-05]

**문항**: 9각형의 내각의 크기의 합을 구하시오. (단위: 도)

**정답**: `1260`

**풀이**: n각형의 내각의 합은 (n - 2)·180° 이므로 9각형은 (9 - 2)·180 = 1260° 이다. 모든 다각형의 내각의 합을 180° 로 여기면 틀린다.

**verify(SymPy 입력)**: conditions: `x = (9-2)*180` · answer_map: {x=1260}

**선지**:
- ① `180` ← 오답 · 오개념 `angle-sum-non-triangle`
- ② `1260` ← 정답
- ③ `1440` ← 정답
- ④ `1620` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 138 · `wm-misc-eval-mc-fcc08b591a89`

- 도메인: `POLYGON-ANGLE-SUM` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.9
- 성취기준: [4수03-25], [9수03-03], [9수03-05]

**문항**: 26각형의 내각의 크기의 합을 구하시오. (단위: 도)

**정답**: `4320`

**풀이**: n각형의 내각의 합은 (n - 2)·180° 이므로 26각형은 (26 - 2)·180 = 4320° 이다. 모든 다각형의 내각의 합을 180° 로 여기면 틀린다.

**verify(SymPy 입력)**: conditions: `x = (26-2)*180` · answer_map: {x=4320}

**선지**:
- ① `180` ← 오답 · 오개념 `angle-sum-non-triangle`
- ② `4320` ← 정답
- ③ `4500` ← 정답
- ④ `4680` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 139 · `wm-misc-eval-mc-03b43e5af9da`

- 도메인: `POLYGON-ANGLE-SUM` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.1
- 성취기준: [4수03-25], [9수03-03], [9수03-05]

**문항**: 28각형의 내각의 크기의 합을 구하시오. (단위: 도)

**정답**: `4680`

**풀이**: n각형의 내각의 합은 (n - 2)·180° 이므로 28각형은 (28 - 2)·180 = 4680° 이다. 모든 다각형의 내각의 합을 180° 로 여기면 틀린다.

**verify(SymPy 입력)**: conditions: `x = (28-2)*180` · answer_map: {x=4680}

**선지**:
- ① `180` ← 오답 · 오개념 `angle-sum-non-triangle`
- ② `4680` ← 정답
- ③ `4860` ← 정답
- ④ `5040` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 140 · `wm-misc-eval-mc-eed4edbbed0e`

- 도메인: `POLYGON-ANGLE-SUM` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.6
- 성취기준: [4수03-25], [9수03-03], [9수03-05]

**문항**: 23각형의 내각의 크기의 합을 구하시오. (단위: 도)

**정답**: `3780`

**풀이**: n각형의 내각의 합은 (n - 2)·180° 이므로 23각형은 (23 - 2)·180 = 3780° 이다. 모든 다각형의 내각의 합을 180° 로 여기면 틀린다.

**verify(SymPy 입력)**: conditions: `x = (23-2)*180` · answer_map: {x=3780}

**선지**:
- ① `180` ← 오답 · 오개념 `angle-sum-non-triangle`
- ② `3780` ← 정답
- ③ `3960` ← 정답
- ④ `4140` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 141 · `wm-misc-eval-mc-24728c1fba65`

- 도메인: `POWER-OF-POWER` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.9
- 성취기준: [9수02-08]

**문항**: (10^2)^3 의 값을 구하시오.

**정답**: `1000000`

**풀이**: 거듭제곱의 거듭제곱은 지수를 곱하므로 (10^2)^3 = 10^6 = 1000000 이다. 지수를 더해 10^5 로 답하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 10**6` · answer_map: {x=1000000}

**선지**:
- ① `100` ← 정답
- ② `1000` ← 정답
- ③ `100000` ← 오답 · 오개념 `power-of-power-adds`
- ④ `1000000` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 142 · `wm-misc-eval-mc-27c28e2fb72b`

- 도메인: `POWER-OF-POWER` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.5
- 성취기준: [9수02-08]

**문항**: (5^2)^3 의 값을 구하시오.

**정답**: `15625`

**풀이**: 거듭제곱의 거듭제곱은 지수를 곱하므로 (5^2)^3 = 5^6 = 15625 이다. 지수를 더해 5^5 로 답하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 5**6` · answer_map: {x=15625}

**선지**:
- ① `25` ← 정답
- ② `125` ← 정답
- ③ `3125` ← 오답 · 오개념 `power-of-power-adds`
- ④ `15625` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 143 · `wm-misc-eval-mc-b74654f9cb9d`

- 도메인: `POWER-OF-POWER` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.6
- 성취기준: [9수02-08]

**문항**: (3^2)^7 의 값을 구하시오.

**정답**: `4782969`

**풀이**: 거듭제곱의 거듭제곱은 지수를 곱하므로 (3^2)^7 = 3^14 = 4782969 이다. 지수를 더해 3^9 로 답하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 3**14` · answer_map: {x=4782969}

**선지**:
- ① `9` ← 정답
- ② `2187` ← 정답
- ③ `19683` ← 오답 · 오개념 `power-of-power-adds`
- ④ `4782969` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 144 · `wm-misc-eval-mc-fe08f363dafc`

- 도메인: `POWER-OF-POWER` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.5
- 성취기준: [9수02-08]

**문항**: (2^3)^6 의 값을 구하시오.

**정답**: `262144`

**풀이**: 거듭제곱의 거듭제곱은 지수를 곱하므로 (2^3)^6 = 2^18 = 262144 이다. 지수를 더해 2^9 로 답하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 2**18` · answer_map: {x=262144}

**선지**:
- ① `8` ← 정답
- ② `64` ← 정답
- ③ `512` ← 오답 · 오개념 `power-of-power-adds`
- ④ `262144` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 145 · `wm-misc-eval-mc-69497ffbc1f9`

- 도메인: `PROB-INDEPENDENT-TRIAL` · 발문형식: 객관식 · 정답형식: 분수 · 난이도: 3
- 성취기준: [12수문02-02], [12인수04-01], [12확통02-01]

**문항**: 앞면이 나올 확률이 5/11 인 동전을 던져 앞면이 3번 연속 나왔다. 다음 시행에서 앞면이 나올 확률을 구하시오.

**정답**: `5/11`

**풀이**: 각 시행은 독립이라 이전 결과와 무관하게 다음 앞면 확률은 5/11 그대로다. 연속으로 나왔으니 이제 덜 나온다고 여기는 도박사 오류에 빠지면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 5/11` · answer_map: {x=5/11}

**선지**:
- ① `25/121` ← 오답 · 오개념 `gambler-fallacy`
- ② `5/22` ← 정답
- ③ `5/11` ← 정답
- ④ `6/11` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 146 · `wm-misc-eval-mc-c7feb6c01121`

- 도메인: `PROB-INDEPENDENT-TRIAL` · 발문형식: 객관식 · 정답형식: 분수 · 난이도: 3.4
- 성취기준: [12수문02-02], [12인수04-01], [12확통02-01]

**문항**: 앞면이 나올 확률이 2/7 인 동전을 던져 앞면이 3번 연속 나왔다. 다음 시행에서 앞면이 나올 확률을 구하시오.

**정답**: `2/7`

**풀이**: 각 시행은 독립이라 이전 결과와 무관하게 다음 앞면 확률은 2/7 그대로다. 연속으로 나왔으니 이제 덜 나온다고 여기는 도박사 오류에 빠지면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 2/7` · answer_map: {x=2/7}

**선지**:
- ① `4/49` ← 오답 · 오개념 `gambler-fallacy`
- ② `1/7` ← 정답
- ③ `2/7` ← 정답
- ④ `5/7` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 147 · `wm-misc-eval-mc-dd613a110047`

- 도메인: `PROB-INDEPENDENT-TRIAL` · 발문형식: 객관식 · 정답형식: 분수 · 난이도: 2.5
- 성취기준: [12수문02-02], [12인수04-01], [12확통02-01]

**문항**: 앞면이 나올 확률이 1/10 인 동전을 던져 앞면이 3번 연속 나왔다. 다음 시행에서 앞면이 나올 확률을 구하시오.

**정답**: `1/10`

**풀이**: 각 시행은 독립이라 이전 결과와 무관하게 다음 앞면 확률은 1/10 그대로다. 연속으로 나왔으니 이제 덜 나온다고 여기는 도박사 오류에 빠지면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 1/10` · answer_map: {x=1/10}

**선지**:
- ① `1/100` ← 오답 · 오개념 `gambler-fallacy`
- ② `1/20` ← 정답
- ③ `1/10` ← 정답
- ④ `9/10` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 148 · `wm-misc-eval-mc-439ee7947bc7`

- 도메인: `PROB-INDEPENDENT-TRIAL` · 발문형식: 객관식 · 정답형식: 분수 · 난이도: 3.2
- 성취기준: [12수문02-02], [12인수04-01], [12확통02-01]

**문항**: 앞면이 나올 확률이 2/5 인 동전을 던져 앞면이 3번 연속 나왔다. 다음 시행에서 앞면이 나올 확률을 구하시오.

**정답**: `2/5`

**풀이**: 각 시행은 독립이라 이전 결과와 무관하게 다음 앞면 확률은 2/5 그대로다. 연속으로 나왔으니 이제 덜 나온다고 여기는 도박사 오류에 빠지면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 2/5` · answer_map: {x=2/5}

**선지**:
- ① `4/25` ← 오답 · 오개념 `gambler-fallacy`
- ② `1/5` ← 정답
- ③ `2/5` ← 정답
- ④ `3/5` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 149 · `wm-misc-eval-mc-58a1985da786`

- 도메인: `REMAINDER-THEOREM` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.1
- 성취기준: [10공수1-01-01]

**문항**: 다항식 x² + 7x + 4 를 (x - 6)로 나눈 나머지를 구하시오.

**정답**: `82`

**풀이**: 나머지정리로 f(6) = 6² + 7·6 + 4 = 82 이다. 부호를 반대로 f(-6)로 대입하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 6**2 + 6*7 + 4` · answer_map: {x=82}

**선지**:
- ① `-2` ← 오답 · 오개념 `remainder-theorem-sign`
- ② `4` ← 정답
- ③ `40` ← 정답
- ④ `82` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 150 · `wm-misc-eval-mc-432668753f4b`

- 도메인: `REMAINDER-THEOREM` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.7
- 성취기준: [10공수1-01-01]

**문항**: 다항식 x² + 4x + 7 를 (x - 2)로 나눈 나머지를 구하시오.

**정답**: `19`

**풀이**: 나머지정리로 f(2) = 2² + 4·2 + 7 = 19 이다. 부호를 반대로 f(-2)로 대입하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 2**2 + 2*4 + 7` · answer_map: {x=19}

**선지**:
- ① `3` ← 오답 · 오개념 `remainder-theorem-sign`
- ② `7` ← 정답
- ③ `11` ← 정답
- ④ `19` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 151 · `wm-misc-eval-mc-c89de485548b`

- 도메인: `REMAINDER-THEOREM` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.9
- 성취기준: [10공수1-01-01]

**문항**: 다항식 x² + 2x + 7 를 (x - 6)로 나눈 나머지를 구하시오.

**정답**: `55`

**풀이**: 나머지정리로 f(6) = 6² + 2·6 + 7 = 55 이다. 부호를 반대로 f(-6)로 대입하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 6**2 + 6*2 + 7` · answer_map: {x=55}

**선지**:
- ① `7` ← 정답
- ② `31` ← 오답 · 오개념 `remainder-theorem-sign`
- ③ `43` ← 정답
- ④ `55` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 152 · `wm-misc-eval-mc-22a80d7acb1c`

- 도메인: `REMAINDER-THEOREM` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.2
- 성취기준: [10공수1-01-01]

**문항**: 다항식 x² + 6x + 7 를 (x - 5)로 나눈 나머지를 구하시오.

**정답**: `62`

**풀이**: 나머지정리로 f(5) = 5² + 6·5 + 7 = 62 이다. 부호를 반대로 f(-5)로 대입하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 5**2 + 5*6 + 7` · answer_map: {x=62}

**선지**:
- ① `2` ← 오답 · 오개념 `remainder-theorem-sign`
- ② `7` ← 정답
- ③ `32` ← 정답
- ④ `62` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 153 · `wm-misc-eval-mc-e7150e7783a7`

- 도메인: `SAME-ITEM-PERM` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.8
- 성취기준: [12직수04-01]

**문항**: 4 개의 A 와 10 개의 B, 모두 14 개의 문자를 일렬로 배열하는 경우의 수를 구하시오.

**정답**: `1001`

**풀이**: 같은 것이 있는 순열이므로 14! 을 각 문자 개수의 계승 4!·10! 로 나눈다: 14!/(4!×10!) = 1001 이다. 중복을 나누지 않고 14! 로 두면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 1001` · answer_map: {x=1001}

**선지**:
- ① `1001` ← 정답
- ② `24024` ← 정답
- ③ `3632428800` ← 정답
- ④ `87178291200` ← 오답 · 오개념 `same-item-permutation-no-divide`

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 154 · `wm-misc-eval-mc-aa997119255b`

- 도메인: `SAME-ITEM-PERM` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.6
- 성취기준: [12직수04-01]

**문항**: 2 개의 A 와 10 개의 B, 모두 12 개의 문자를 일렬로 배열하는 경우의 수를 구하시오.

**정답**: `66`

**풀이**: 같은 것이 있는 순열이므로 12! 을 각 문자 개수의 계승 2!·10! 로 나눈다: 12!/(2!×10!) = 66 이다. 중복을 나누지 않고 12! 로 두면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 66` · answer_map: {x=66}

**선지**:
- ① `66` ← 정답
- ② `132` ← 정답
- ③ `239500800` ← 정답
- ④ `479001600` ← 오답 · 오개념 `same-item-permutation-no-divide`

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 155 · `wm-misc-eval-mc-991892a94888`

- 도메인: `SAME-ITEM-PERM` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.1
- 성취기준: [12직수04-01]

**문항**: 2 개의 A 와 4 개의 B, 모두 6 개의 문자를 일렬로 배열하는 경우의 수를 구하시오.

**정답**: `15`

**풀이**: 같은 것이 있는 순열이므로 6! 을 각 문자 개수의 계승 2!·4! 로 나눈다: 6!/(2!×4!) = 15 이다. 중복을 나누지 않고 6! 로 두면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 15` · answer_map: {x=15}

**선지**:
- ① `15` ← 정답
- ② `30` ← 정답
- ③ `360` ← 정답
- ④ `720` ← 오답 · 오개념 `same-item-permutation-no-divide`

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 156 · `wm-misc-eval-mc-cb74f7591a3c`

- 도메인: `SAME-ITEM-PERM` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.4
- 성취기준: [12직수04-01]

**문항**: 3 개의 A 와 6 개의 B, 모두 9 개의 문자를 일렬로 배열하는 경우의 수를 구하시오.

**정답**: `84`

**풀이**: 같은 것이 있는 순열이므로 9! 을 각 문자 개수의 계승 3!·6! 로 나눈다: 9!/(3!×6!) = 84 이다. 중복을 나누지 않고 9! 로 두면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 84` · answer_map: {x=84}

**선지**:
- ① `84` ← 정답
- ② `504` ← 정답
- ③ `60480` ← 정답
- ④ `362880` ← 오답 · 오개념 `same-item-permutation-no-divide`

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 157 · `wm-misc-eval-mc-fcd6285b59bd`

- 도메인: `SCALE-AREA` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.9
- 성취기준: [9수02-07]

**문항**: 닮음비가 4 인 두 도형의 넓이의 비를 구하시오.

**정답**: `16`

**풀이**: 넓이는 길이의 제곱에 비례하므로 닮음비 4 의 넓이의 비는 4² = 16 이다. 닮음비 4 를 그대로 넓이의 비로 답하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 4**2` · answer_map: {x=16}

**선지**:
- ① `4` ← 오답 · 오개념 `scale-area-linear`
- ② `8` ← 정답
- ③ `16` ← 정답
- ④ `64` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 158 · `wm-misc-eval-mc-6645c8b0ca5f`

- 도메인: `SCALE-AREA` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.4
- 성취기준: [9수02-07]

**문항**: 닮음비가 9 인 두 도형의 넓이의 비를 구하시오.

**정답**: `81`

**풀이**: 넓이는 길이의 제곱에 비례하므로 닮음비 9 의 넓이의 비는 9² = 81 이다. 닮음비 9 를 그대로 넓이의 비로 답하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 9**2` · answer_map: {x=81}

**선지**:
- ① `9` ← 오답 · 오개념 `scale-area-linear`
- ② `18` ← 정답
- ③ `81` ← 정답
- ④ `729` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 159 · `wm-misc-eval-mc-ad4661e1a9be`

- 도메인: `SCALE-AREA` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.1
- 성취기준: [9수02-07]

**문항**: 닮음비가 17 인 두 도형의 넓이의 비를 구하시오.

**정답**: `289`

**풀이**: 넓이는 길이의 제곱에 비례하므로 닮음비 17 의 넓이의 비는 17² = 289 이다. 닮음비 17 를 그대로 넓이의 비로 답하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 17**2` · answer_map: {x=289}

**선지**:
- ① `17` ← 오답 · 오개념 `scale-area-linear`
- ② `34` ← 정답
- ③ `289` ← 정답
- ④ `4913` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 160 · `wm-misc-eval-mc-26ec2431182d`

- 도메인: `SCALE-AREA` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.6
- 성취기준: [9수02-07]

**문항**: 닮음비가 12 인 두 도형의 넓이의 비를 구하시오.

**정답**: `144`

**풀이**: 넓이는 길이의 제곱에 비례하므로 닮음비 12 의 넓이의 비는 12² = 144 이다. 닮음비 12 를 그대로 넓이의 비로 답하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 12**2` · answer_map: {x=144}

**선지**:
- ① `12` ← 오답 · 오개념 `scale-area-linear`
- ② `24` ← 정답
- ③ `144` ← 정답
- ④ `1728` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 161 · `wm-misc-eval-mc-f821cf97f33b`

- 도메인: `SCALE-VOLUME` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.4
- 성취기준: [9수03-12]

**문항**: 닮음비가 1:20 인 두 입체도형의 부피비는 1:? 이다. ? 의 값을 구하시오.

**정답**: `8000`

**풀이**: 닮음비가 1:20 이면 부피비는 1:20³ = 1:8000 이다. 부피비를 닮음비와 같은 20 로 두면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 20**3` · answer_map: {x=8000}

**선지**:
- ① `20` ← 오답 · 오개념 `scale-volume-linear`
- ② `60` ← 정답
- ③ `400` ← 정답
- ④ `8000` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 162 · `wm-misc-eval-mc-fde09cff6828`

- 도메인: `SCALE-VOLUME` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.9
- 성취기준: [9수03-12]

**문항**: 닮음비가 1:15 인 두 입체도형의 부피비는 1:? 이다. ? 의 값을 구하시오.

**정답**: `3375`

**풀이**: 닮음비가 1:15 이면 부피비는 1:15³ = 1:3375 이다. 부피비를 닮음비와 같은 15 로 두면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 15**3` · answer_map: {x=3375}

**선지**:
- ① `15` ← 오답 · 오개념 `scale-volume-linear`
- ② `45` ← 정답
- ③ `225` ← 정답
- ④ `3375` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 163 · `wm-misc-eval-mc-1a77597ec643`

- 도메인: `SCALE-VOLUME` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.1
- 성취기준: [9수03-12]

**문항**: 닮음비가 1:28 인 두 입체도형의 부피비는 1:? 이다. ? 의 값을 구하시오.

**정답**: `21952`

**풀이**: 닮음비가 1:28 이면 부피비는 1:28³ = 1:21952 이다. 부피비를 닮음비와 같은 28 로 두면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 28**3` · answer_map: {x=21952}

**선지**:
- ① `28` ← 오답 · 오개념 `scale-volume-linear`
- ② `84` ← 정답
- ③ `784` ← 정답
- ④ `21952` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 164 · `wm-misc-eval-mc-d39bfc467d74`

- 도메인: `SCALE-VOLUME` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.6
- 성취기준: [9수03-12]

**문항**: 닮음비가 1:23 인 두 입체도형의 부피비는 1:? 이다. ? 의 값을 구하시오.

**정답**: `12167`

**풀이**: 닮음비가 1:23 이면 부피비는 1:23³ = 1:12167 이다. 부피비를 닮음비와 같은 23 로 두면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 23**3` · answer_map: {x=12167}

**선지**:
- ① `23` ← 오답 · 오개념 `scale-volume-linear`
- ② `69` ← 정답
- ③ `529` ← 정답
- ④ `12167` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 165 · `wm-misc-eval-mc-f8271784adee`

- 도메인: `SQRT-POS` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.9
- 성취기준: [12대수01-01], [9수01-07]

**문항**: √((-15)^2) 의 값을 구하시오.

**정답**: `15`

**풀이**: √(x²) = |x| 이므로 √((-15)²) = |-15| = 15 이다. √(x²) = x 로 오인하면 -15 가 되어 틀린다.

**verify(SymPy 입력)**: conditions: `x = sqrt((-15)**2)` · answer_map: {x=15}

**선지**:
- ① `-15` ← 오답 · 오개념 `square-root-positivity`
- ② `15` ← 정답
- ③ `30` ← 정답
- ④ `225` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 166 · `wm-misc-eval-mc-d17a4f49d401`

- 도메인: `SQRT-POS` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.1
- 성취기준: [12대수01-01], [9수01-07]

**문항**: √((-28)^2) 의 값을 구하시오.

**정답**: `28`

**풀이**: √(x²) = |x| 이므로 √((-28)²) = |-28| = 28 이다. √(x²) = x 로 오인하면 -28 가 되어 틀린다.

**verify(SymPy 입력)**: conditions: `x = sqrt((-28)**2)` · answer_map: {x=28}

**선지**:
- ① `-28` ← 오답 · 오개념 `square-root-positivity`
- ② `28` ← 정답
- ③ `56` ← 정답
- ④ `784` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 167 · `wm-misc-eval-mc-8b7513124329`

- 도메인: `SQRT-POS` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.4
- 성취기준: [12대수01-01], [9수01-07]

**문항**: √((-20)^2) 의 값을 구하시오.

**정답**: `20`

**풀이**: √(x²) = |x| 이므로 √((-20)²) = |-20| = 20 이다. √(x²) = x 로 오인하면 -20 가 되어 틀린다.

**verify(SymPy 입력)**: conditions: `x = sqrt((-20)**2)` · answer_map: {x=20}

**선지**:
- ① `-20` ← 오답 · 오개념 `square-root-positivity`
- ② `20` ← 정답
- ③ `40` ← 정답
- ④ `400` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 168 · `wm-misc-eval-mc-b72d33532925`

- 도메인: `SQRT-POS` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.6
- 성취기준: [12대수01-01], [9수01-07]

**문항**: √((-12)^2) 의 값을 구하시오.

**정답**: `12`

**풀이**: √(x²) = |x| 이므로 √((-12)²) = |-12| = 12 이다. √(x²) = x 로 오인하면 -12 가 되어 틀린다.

**verify(SymPy 입력)**: conditions: `x = sqrt((-12)**2)` · answer_map: {x=12}

**선지**:
- ① `-12` ← 오답 · 오개념 `square-root-positivity`
- ② `12` ← 정답
- ③ `24` ← 정답
- ④ `144` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 169 · `wm-misc-eval-mc-d548855e7457`

- 도메인: `SQRT-SUM` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.3
- 성취기준: [9수01-07]

**문항**: √(3600 + 6400) 의 값을 구하시오.

**정답**: `100`

**풀이**: 근호 안의 합 10000 는 100 의 제곱이므로 그 제곱근은 100 이다. 제곱근을 각 항에 분배하면 60 + 80 이 되어 틀린다.

**verify(SymPy 입력)**: conditions: `x = 100` · answer_map: {x=100}

**선지**:
- ① `20` ← 정답
- ② `80` ← 정답
- ③ `100` ← 정답
- ④ `140` ← 오답 · 오개념 `sqrt-distributes-over-sum`

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 170 · `wm-misc-eval-mc-d80812504fe6`

- 도메인: `SQRT-SUM` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.5
- 성취기준: [9수01-07]

**문항**: √(6400 + 7056) 의 값을 구하시오.

**정답**: `116`

**풀이**: 근호 안의 합 13456 는 116 의 제곱이므로 그 제곱근은 116 이다. 제곱근을 각 항에 분배하면 80 + 84 이 되어 틀린다.

**verify(SymPy 입력)**: conditions: `x = 116` · answer_map: {x=116}

**선지**:
- ① `4` ← 정답
- ② `84` ← 정답
- ③ `116` ← 정답
- ④ `164` ← 오답 · 오개념 `sqrt-distributes-over-sum`

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 171 · `wm-misc-eval-mc-59c6c705956a`

- 도메인: `SQRT-SUM` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.7
- 성취기준: [9수01-07]

**문항**: √(256 + 900) 의 값을 구하시오.

**정답**: `34`

**풀이**: 근호 안의 합 1156 는 34 의 제곱이므로 그 제곱근은 34 이다. 제곱근을 각 항에 분배하면 16 + 30 이 되어 틀린다.

**verify(SymPy 입력)**: conditions: `x = 34` · answer_map: {x=34}

**선지**:
- ① `14` ← 정답
- ② `30` ← 정답
- ③ `34` ← 정답
- ④ `46` ← 오답 · 오개념 `sqrt-distributes-over-sum`

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 172 · `wm-misc-eval-mc-c596b689574a`

- 도메인: `SQRT-SUM` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3
- 성취기준: [9수01-07]

**문항**: √(81 + 1600) 의 값을 구하시오.

**정답**: `41`

**풀이**: 근호 안의 합 1681 는 41 의 제곱이므로 그 제곱근은 41 이다. 제곱근을 각 항에 분배하면 9 + 40 이 되어 틀린다.

**verify(SymPy 입력)**: conditions: `x = 41` · answer_map: {x=41}

**선지**:
- ① `31` ← 정답
- ② `40` ← 정답
- ③ `41` ← 정답
- ④ `49` ← 오답 · 오개념 `sqrt-distributes-over-sum`

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 173 · `wm-misc-eval-mc-d1b5c2fd6967`

- 도메인: `SQUARE-DIFF` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.4
- 성취기준: [9수02-19]

**문항**: (7 - 2)² 의 값을 구하시오.

**정답**: `25`

**풀이**: 차의 제곱은 (7 - 2)² = 7² - 2·7·2 + 2² = 25 이다. 교차항을 누락해 7² - 2²로 계산하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = (7 - 2)**2` · answer_map: {x=25}

**선지**:
- ① `25` ← 정답
- ② `45` ← 오답 · 오개념 `square-of-difference-no-cross`
- ③ `53` ← 정답
- ④ `81` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 174 · `wm-misc-eval-mc-64104399ef79`

- 도메인: `SQUARE-DIFF` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.1
- 성취기준: [9수02-19]

**문항**: (26 - 2)² 의 값을 구하시오.

**정답**: `576`

**풀이**: 차의 제곱은 (26 - 2)² = 26² - 2·26·2 + 2² = 576 이다. 교차항을 누락해 26² - 2²로 계산하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = (26 - 2)**2` · answer_map: {x=576}

**선지**:
- ① `576` ← 정답
- ② `672` ← 오답 · 오개념 `square-of-difference-no-cross`
- ③ `680` ← 정답
- ④ `784` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 175 · `wm-misc-eval-mc-467cf759cb91`

- 도메인: `SQUARE-DIFF` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.9
- 성취기준: [9수02-19]

**문항**: (24 - 2)² 의 값을 구하시오.

**정답**: `484`

**풀이**: 차의 제곱은 (24 - 2)² = 24² - 2·24·2 + 2² = 484 이다. 교차항을 누락해 24² - 2²로 계산하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = (24 - 2)**2` · answer_map: {x=484}

**선지**:
- ① `484` ← 정답
- ② `572` ← 오답 · 오개념 `square-of-difference-no-cross`
- ③ `580` ← 정답
- ④ `676` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 176 · `wm-misc-eval-mc-debe3b18f20b`

- 도메인: `SQUARE-DIFF` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.6
- 성취기준: [9수02-19]

**문항**: (21 - 2)² 의 값을 구하시오.

**정답**: `361`

**풀이**: 차의 제곱은 (21 - 2)² = 21² - 2·21·2 + 2² = 361 이다. 교차항을 누락해 21² - 2²로 계산하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = (21 - 2)**2` · answer_map: {x=361}

**선지**:
- ① `361` ← 정답
- ② `437` ← 오답 · 오개념 `square-of-difference-no-cross`
- ③ `445` ← 정답
- ④ `529` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 177 · `wm-misc-eval-mc-bbb9f4302a60`

- 도메인: `SUBTRACT-NEG` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.6
- 성취기준: [9수01-03]

**문항**: 2 - (-10) 의 값을 구하시오.

**정답**: `12`

**풀이**: 음수를 빼면 그만큼 더해지므로 2 - (-10) = 2 + 10 = 12 이다. 부호 반전을 놓쳐 a - b로 계산하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 2+10` · answer_map: {x=12}

**선지**:
- ① `-12` ← 정답
- ② `-8` ← 오답 · 오개념 `subtract-negative-sign`
- ③ `8` ← 정답
- ④ `12` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 178 · `wm-misc-eval-mc-91082d61f63b`

- 도메인: `SUBTRACT-NEG` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.2
- 성취기준: [9수01-03]

**문항**: 8 - (-21) 의 값을 구하시오.

**정답**: `29`

**풀이**: 음수를 빼면 그만큼 더해지므로 8 - (-21) = 8 + 21 = 29 이다. 부호 반전을 놓쳐 a - b로 계산하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 8+21` · answer_map: {x=29}

**선지**:
- ① `-29` ← 정답
- ② `-13` ← 오답 · 오개념 `subtract-negative-sign`
- ③ `13` ← 정답
- ④ `29` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 179 · `wm-misc-eval-mc-18c1c5ea1579`

- 도메인: `SUBTRACT-NEG` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.9
- 성취기준: [9수01-03]

**문항**: 2 - (-13) 의 값을 구하시오.

**정답**: `15`

**풀이**: 음수를 빼면 그만큼 더해지므로 2 - (-13) = 2 + 13 = 15 이다. 부호 반전을 놓쳐 a - b로 계산하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 2+13` · answer_map: {x=15}

**선지**:
- ① `-15` ← 정답
- ② `-11` ← 오답 · 오개념 `subtract-negative-sign`
- ③ `11` ← 정답
- ④ `15` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 180 · `wm-misc-eval-mc-5b336130f36c`

- 도메인: `SUBTRACT-NEG` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.4
- 성취기준: [9수01-03]

**문항**: 10 - (-21) 의 값을 구하시오.

**정답**: `31`

**풀이**: 음수를 빼면 그만큼 더해지므로 10 - (-21) = 10 + 21 = 31 이다. 부호 반전을 놓쳐 a - b로 계산하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 10+21` · answer_map: {x=31}

**선지**:
- ① `-31` ← 정답
- ② `-11` ← 오답 · 오개념 `subtract-negative-sign`
- ③ `11` ← 정답
- ④ `31` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 181 · `wm-misc-eval-mc-d172ba122598`

- 도메인: `TRANSPOSE-SIGN` · 발문형식: 객관식 · 정답형식: 분수 · 난이도: 2.6
- 성취기준: [9수02-13]

**문항**: 일차방정식 x + 10 = 2 의 해를 구하시오.

**정답**: `-8`

**풀이**: 10를 이항하면 부호가 바뀌어 x = 2 - 10 = -8 이다. 이항할 때 부호를 바꾸지 않으면 2 + 10로 틀린다.

**verify(SymPy 입력)**: conditions: `x = 2 - 10` · answer_map: {x=-8}

**선지**:
- ① `-8` ← 정답
- ② `2` ← 정답
- ③ `10` ← 정답
- ④ `12` ← 오답 · 오개념 `transpose-no-sign-change`

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 182 · `wm-misc-eval-mc-3f6fe185706e`

- 도메인: `TRANSPOSE-SIGN` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.4
- 성취기준: [9수02-13]

**문항**: 일차방정식 x + 2 = 7 의 해를 구하시오.

**정답**: `5`

**풀이**: 2를 이항하면 부호가 바뀌어 x = 7 - 2 = 5 이다. 이항할 때 부호를 바꾸지 않으면 7 + 2로 틀린다.

**verify(SymPy 입력)**: conditions: `x = 7 - 2` · answer_map: {x=5}

**선지**:
- ① `2` ← 정답
- ② `5` ← 정답
- ③ `7` ← 정답
- ④ `9` ← 오답 · 오개념 `transpose-no-sign-change`

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 183 · `wm-misc-eval-mc-832935085189`

- 도메인: `TRANSPOSE-SIGN` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.2
- 성취기준: [9수02-13]

**문항**: 일차방정식 x + 2 = 16 의 해를 구하시오.

**정답**: `14`

**풀이**: 2를 이항하면 부호가 바뀌어 x = 16 - 2 = 14 이다. 이항할 때 부호를 바꾸지 않으면 16 + 2로 틀린다.

**verify(SymPy 입력)**: conditions: `x = 16 - 2` · answer_map: {x=14}

**선지**:
- ① `2` ← 정답
- ② `14` ← 정답
- ③ `16` ← 정답
- ④ `18` ← 오답 · 오개념 `transpose-no-sign-change`

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 184 · `wm-misc-eval-mc-6c39c9b22325`

- 도메인: `TRANSPOSE-SIGN` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.9
- 성취기준: [9수02-13]

**문항**: 일차방정식 x + 2 = 13 의 해를 구하시오.

**정답**: `11`

**풀이**: 2를 이항하면 부호가 바뀌어 x = 13 - 2 = 11 이다. 이항할 때 부호를 바꾸지 않으면 13 + 2로 틀린다.

**verify(SymPy 입력)**: conditions: `x = 13 - 2` · answer_map: {x=11}

**선지**:
- ① `2` ← 정답
- ② `11` ← 정답
- ③ `13` ← 정답
- ④ `15` ← 오답 · 오개념 `transpose-no-sign-change`

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 185 · `wm-misc-eval-mc-99495abd77df`

- 도메인: `TRAPEZOID-AREA` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3
- 성취기준: [9수03-12]

**문항**: 윗변이 2, 아랫변이 6, 높이가 8 인 사다리꼴의 넓이를 구하시오.

**정답**: `32`

**풀이**: 사다리꼴의 넓이 = (윗변+아랫변)×높이÷2 = (2+6)×8÷2 = 32 이다. ÷2 를 빠뜨리면 64 가 되어 틀린다.

**verify(SymPy 입력)**: conditions: `x = (2+6)*8/2` · answer_map: {x=32}

**선지**:
- ① `16` ← 정답
- ② `32` ← 정답
- ③ `48` ← 정답
- ④ `64` ← 오답 · 오개념 `trapezoid-area-no-half`

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 186 · `wm-misc-eval-mc-e1d78ee63b31`

- 도메인: `TRAPEZOID-AREA` · 발문형식: 객관식 · 정답형식: 분수 · 난이도: 2.7
- 성취기준: [9수03-12]

**문항**: 윗변이 5, 아랫변이 14, 높이가 5 인 사다리꼴의 넓이를 구하시오.

**정답**: `95/2`

**풀이**: 사다리꼴의 넓이 = (윗변+아랫변)×높이÷2 = (5+14)×5÷2 = 95/2 이다. ÷2 를 빠뜨리면 95 가 되어 틀린다.

**verify(SymPy 입력)**: conditions: `x = (5+14)*5/2` · answer_map: {x=95/2}

**선지**:
- ① `25` ← 정답
- ② `95/2` ← 정답
- ③ `70` ← 정답
- ④ `95` ← 오답 · 오개념 `trapezoid-area-no-half`

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 187 · `wm-misc-eval-mc-009769d8362a`

- 도메인: `TRAPEZOID-AREA` · 발문형식: 객관식 · 정답형식: 분수 · 난이도: 3.2
- 성취기준: [9수03-12]

**문항**: 윗변이 2, 아랫변이 7, 높이가 9 인 사다리꼴의 넓이를 구하시오.

**정답**: `81/2`

**풀이**: 사다리꼴의 넓이 = (윗변+아랫변)×높이÷2 = (2+7)×9÷2 = 81/2 이다. ÷2 를 빠뜨리면 81 가 되어 틀린다.

**verify(SymPy 입력)**: conditions: `x = (2+7)*9/2` · answer_map: {x=81/2}

**선지**:
- ① `18` ← 정답
- ② `81/2` ← 정답
- ③ `63` ← 정답
- ④ `81` ← 오답 · 오개념 `trapezoid-area-no-half`

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 188 · `wm-misc-eval-mc-46df9a573646`

- 도메인: `TRAPEZOID-AREA` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.4
- 성취기준: [9수03-12]

**문항**: 윗변이 8, 아랫변이 14, 높이가 9 인 사다리꼴의 넓이를 구하시오.

**정답**: `99`

**풀이**: 사다리꼴의 넓이 = (윗변+아랫변)×높이÷2 = (8+14)×9÷2 = 99 이다. ÷2 를 빠뜨리면 198 가 되어 틀린다.

**verify(SymPy 입력)**: conditions: `x = (8+14)*9/2` · answer_map: {x=99}

**선지**:
- ① `72` ← 정답
- ② `99` ← 정답
- ③ `126` ← 정답
- ④ `198` ← 오답 · 오개념 `trapezoid-area-no-half`

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 189 · `wm-misc-eval-mc-882bae94d3be`

- 도메인: `TRIG-ADD` · 발문형식: 객관식 · 정답형식: 실수 · 난이도: 3.2
- 성취기준: [12미적Ⅱ-02-02]

**문항**: 두 각 A = 1π/12, B = 4π/12 에 대하여 2 sin(A + B) 의 값을 구하시오.

**정답**: `sqrt(2)/2 + sqrt(6)/2`

**풀이**: 삼각함수의 덧셈정리에 의해 sin(A + B) = sin A cos B + cos A sin B 이다. 사인을 합에 분배하여 sin A + sin B 로 계산하면 틀린 값이 된다.

**verify(SymPy 입력)**: conditions: `x = 2*sin(1*pi/12 + 4*pi/12)` · answer_map: {x=sqrt(2)/2 + sqrt(6)/2}

**선지**:
- ① `-sqrt(2)/4 + sqrt(6)/4` ← 정답
- ② `sqrt(2)/4 + sqrt(6)/4` ← 정답
- ③ `sqrt(2)/2 + sqrt(6)/2` ← 정답
- ④ `-sqrt(2)/2 + sqrt(6)/2 + sqrt(3)` ← 오답 · 오개념 `sine-distributes-over-sum` (op: `sine-distributed-over-sum`)

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 190 · `wm-misc-eval-mc-09c991afab66`

- 도메인: `TRIG-ADD` · 발문형식: 객관식 · 정답형식: 실수 · 난이도: 3
- 성취기준: [12미적Ⅱ-02-02]

**문항**: 두 각 A = 4π/12, B = 11π/12 에 대하여 sin(A + B) 의 값을 구하시오.

**정답**: `-sqrt(2)/2`

**풀이**: 삼각함수의 덧셈정리에 의해 sin(A + B) = sin A cos B + cos A sin B 이다. 사인을 합에 분배하여 sin A + sin B 로 계산하면 틀린 값이 된다.

**verify(SymPy 입력)**: conditions: `x = 1*sin(4*pi/12 + 11*pi/12)` · answer_map: {x=-sqrt(2)/2}

**선지**:
- ① `sqrt(3)*(-sqrt(6)/4 - sqrt(2)/4)/2` ← 정답
- ② `-sqrt(2)/2` ← 정답
- ③ `-sqrt(6)/8 - sqrt(2)/8` ← 정답
- ④ `-sqrt(2)/4 + sqrt(6)/4 + sqrt(3)/2` ← 오답 · 오개념 `sine-distributes-over-sum` (op: `sine-distributed-over-sum`)

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 191 · `wm-misc-eval-mc-7e22bbdbc3c4`

- 도메인: `TRIG-ADD` · 발문형식: 객관식 · 정답형식: 실수 · 난이도: 2.8
- 성취기준: [12미적Ⅱ-02-02]

**문항**: 두 각 A = 1π/12, B = 10π/12 에 대하여 3 sin(A + B) 의 값을 구하시오.

**정답**: `-3*sqrt(2)/4 + 3*sqrt(6)/4`

**풀이**: 삼각함수의 덧셈정리에 의해 sin(A + B) = sin A cos B + cos A sin B 이다. 사인을 합에 분배하여 sin A + sin B 로 계산하면 틀린 값이 된다.

**verify(SymPy 입력)**: conditions: `x = 3*sin(1*pi/12 + 10*pi/12)` · answer_map: {x=-3*sqrt(2)/4 + 3*sqrt(6)/4}

**선지**:
- ① `-3*sqrt(3)*(sqrt(2)/4 + sqrt(6)/4)/2` ← 정답
- ② `-3*sqrt(3)*(-sqrt(2)/4 + sqrt(6)/4)/2` ← 정답
- ③ `-3*sqrt(2)/4 + 3*sqrt(6)/4` ← 정답
- ④ `-3*sqrt(2)/4 + 3/2 + 3*sqrt(6)/4` ← 오답 · 오개념 `sine-distributes-over-sum` (op: `sine-distributed-over-sum`)

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 192 · `wm-misc-eval-mc-a62b1a02560c`

- 도메인: `TRIG-ADD` · 발문형식: 객관식 · 정답형식: 실수 · 난이도: 3.3
- 성취기준: [12미적Ⅱ-02-02]

**문항**: 두 각 A = 7π/12, B = 10π/12 에 대하여 2 sin(A + B) 의 값을 구하시오.

**정답**: `-sqrt(6)/2 - sqrt(2)/2`

**풀이**: 삼각함수의 덧셈정리에 의해 sin(A + B) = sin A cos B + cos A sin B 이다. 사인을 합에 분배하여 sin A + sin B 로 계산하면 틀린 값이 된다.

**verify(SymPy 입력)**: conditions: `x = 2*sin(7*pi/12 + 10*pi/12)` · answer_map: {x=-sqrt(6)/2 - sqrt(2)/2}

**선지**:
- ① `-sqrt(6)/2 - sqrt(2)/2` ← 정답
- ② `-sqrt(3)*(sqrt(2)/4 + sqrt(6)/4)` ← 정답
- ③ `-sqrt(3)*(-sqrt(6)/4 + sqrt(2)/4)` ← 정답
- ④ `sqrt(2)/2 + 1 + sqrt(6)/2` ← 오답 · 오개념 `sine-distributes-over-sum` (op: `sine-distributed-over-sum`)

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 193 · `wm-misc-eval-mc-eba865a498da`

- 도메인: `TRIG-PERIOD` · 발문형식: 객관식 · 정답형식: 실수 · 난이도: 2.9
- 성취기준: [12미적Ⅱ-02-02]

**문항**: 함수 y = sin(26x) 의 주기를 구하시오.

**정답**: `pi/13`

**풀이**: y = sin(bx) 의 주기는 2π/b 이므로 y = sin(26x) 의 주기는 2π/26 이다. 계수 26 를 무시하면 주기를 2π 로 잘못 구한다.

**verify(SymPy 입력)**: conditions: `x = 2*pi/26` · answer_map: {x=pi/13}

**선지**:
- ① `pi/26` ← 정답
- ② `pi/13` ← 정답
- ③ `2*pi` ← 오답 · 오개념 `period-of-scaled-sine`
- ④ `52*pi` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 194 · `wm-misc-eval-mc-5b4e9d794b6e`

- 도메인: `TRIG-PERIOD` · 발문형식: 객관식 · 정답형식: 실수 · 난이도: 3.1
- 성취기준: [12미적Ⅱ-02-02]

**문항**: 함수 y = sin(6x) 의 주기를 구하시오.

**정답**: `pi/3`

**풀이**: y = sin(bx) 의 주기는 2π/b 이므로 y = sin(6x) 의 주기는 2π/6 이다. 계수 6 를 무시하면 주기를 2π 로 잘못 구한다.

**verify(SymPy 입력)**: conditions: `x = 2*pi/6` · answer_map: {x=pi/3}

**선지**:
- ① `pi/6` ← 정답
- ② `pi/3` ← 정답
- ③ `2*pi` ← 오답 · 오개념 `period-of-scaled-sine`
- ④ `12*pi` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 195 · `wm-misc-eval-mc-fb0c9a9199d5`

- 도메인: `TRIG-PERIOD` · 발문형식: 객관식 · 정답형식: 실수 · 난이도: 3.4
- 성취기준: [12미적Ⅱ-02-02]

**문항**: 함수 y = sin(20x) 의 주기를 구하시오.

**정답**: `pi/10`

**풀이**: y = sin(bx) 의 주기는 2π/b 이므로 y = sin(20x) 의 주기는 2π/20 이다. 계수 20 를 무시하면 주기를 2π 로 잘못 구한다.

**verify(SymPy 입력)**: conditions: `x = 2*pi/20` · answer_map: {x=pi/10}

**선지**:
- ① `pi/20` ← 정답
- ② `pi/10` ← 정답
- ③ `2*pi` ← 오답 · 오개념 `period-of-scaled-sine`
- ④ `40*pi` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 196 · `wm-misc-eval-mc-4907b5b4783e`

- 도메인: `TRIG-PERIOD` · 발문형식: 객관식 · 정답형식: 실수 · 난이도: 2.6
- 성취기준: [12미적Ⅱ-02-02]

**문항**: 함수 y = sin(23x) 의 주기를 구하시오.

**정답**: `2*pi/23`

**풀이**: y = sin(bx) 의 주기는 2π/b 이므로 y = sin(23x) 의 주기는 2π/23 이다. 계수 23 를 무시하면 주기를 2π 로 잘못 구한다.

**verify(SymPy 입력)**: conditions: `x = 2*pi/23` · answer_map: {x=2*pi/23}

**선지**:
- ① `pi/23` ← 정답
- ② `2*pi/23` ← 정답
- ③ `2*pi` ← 오답 · 오개념 `period-of-scaled-sine`
- ④ `46*pi` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 197 · `wm-misc-eval-mc-e4d6a7306133`

- 도메인: `VIETA-SUM` · 발문형식: 객관식 · 정답형식: 분수 · 난이도: 2.8
- 성취기준: [10공수1-02-08]

**문항**: x² + 14x + 15 = 0 의 두 근의 합을 구하시오.

**정답**: `-14`

**풀이**: 근과 계수 관계로 두 근의 합은 -(일차항 계수) = -14 = -14 이다. 부호를 놓쳐 14로 답하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = -14` · answer_map: {x=-14}

**선지**:
- ① `-15` ← 정답
- ② `-14` ← 정답
- ③ `14` ← 오답 · 오개념 `vieta-sign-error`
- ④ `15` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 198 · `wm-misc-eval-mc-b71ed8d5999a`

- 도메인: `VIETA-SUM` · 발문형식: 객관식 · 정답형식: 분수 · 난이도: 2.6
- 성취기준: [10공수1-02-08]

**문항**: x² + 23x + 24 = 0 의 두 근의 합을 구하시오.

**정답**: `-23`

**풀이**: 근과 계수 관계로 두 근의 합은 -(일차항 계수) = -23 = -23 이다. 부호를 놓쳐 23로 답하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = -23` · answer_map: {x=-23}

**선지**:
- ① `-24` ← 정답
- ② `-23` ← 정답
- ③ `23` ← 오답 · 오개념 `vieta-sign-error`
- ④ `24` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 199 · `wm-misc-eval-mc-7a23f189f48f`

- 도메인: `VIETA-SUM` · 발문형식: 객관식 · 정답형식: 분수 · 난이도: 3.4
- 성취기준: [10공수1-02-08]

**문항**: x² + 9x + 10 = 0 의 두 근의 합을 구하시오.

**정답**: `-9`

**풀이**: 근과 계수 관계로 두 근의 합은 -(일차항 계수) = -9 = -9 이다. 부호를 놓쳐 9로 답하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = -9` · answer_map: {x=-9}

**선지**:
- ① `-10` ← 정답
- ② `-9` ← 정답
- ③ `9` ← 오답 · 오개념 `vieta-sign-error`
- ④ `10` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

## 표본 200 · `wm-misc-eval-mc-15be759e7275`

- 도메인: `VIETA-SUM` · 발문형식: 객관식 · 정답형식: 분수 · 난이도: 3.1
- 성취기준: [10공수1-02-08]

**문항**: x² + 17x + 18 = 0 의 두 근의 합을 구하시오.

**정답**: `-17`

**풀이**: 근과 계수 관계로 두 근의 합은 -(일차항 계수) = -17 = -17 이다. 부호를 놓쳐 17로 답하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = -17` · answer_map: {x=-17}

**선지**:
- ① `-18` ← 정답
- ② `-17` ← 정답
- ③ `17` ← 오답 · 오개념 `vieta-sign-error`
- ④ `18` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
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

<!-- coverage: {"n":200,"corpus_size":1080,"domain_counts":{"ABS-VALUE":5,"AREA-PERIMETER":5,"CALC-CHAIN":5,"CALC-PRODUCT":5,"CIRCLE-AREA":5,"CIRCLE-RADIUS":5,"COMBINATION-COUNT":5,"COMBINE-UNLIKE":5,"COMPLETE-SQUARE":5,"CONE-VOLUME":5,"CONJUGATE-PRODUCT":5,"DECIMAL-MULT":5,"DIFF-SQUARES":5,"DISTRIBUTE-PARTIAL":5,"EXP-PRODUCT":5,"EXP-ZERO":5,"FRACTION-ADD":5,"FRACTION-CANCEL":5,"FUNC-COMPOSE":5,"FUNC-TRANSLATE":5,"GCD-LCM":4,"LOG-DIST":4,"MIDPOINT-NO-HALF":4,"MIXED-MULT":4,"NEG-DISTRIBUTE":4,"NEG-EVEN-POWER":4,"NEG-PRODUCT":4,"NEG-SQUARE":4,"POLY-PRODUCT":4,"POLYGON-ANGLE-SUM":4,"POWER-OF-POWER":4,"PROB-INDEPENDENT-TRIAL":4,"REMAINDER-THEOREM":4,"SAME-ITEM-PERM":4,"SCALE-AREA":4,"SCALE-VOLUME":4,"SQRT-POS":4,"SQRT-SUM":4,"SQUARE-DIFF":4,"SUBTRACT-NEG":4,"TRANSPOSE-SIGN":4,"TRAPEZOID-AREA":4,"TRIG-ADD":4,"TRIG-PERIOD":4,"VIETA-SUM":4},"format_counts":{"객관식":200},"misconception_counts":{"absolute-value-keeps-sign":5,"angle-sum-non-triangle":4,"area-perimeter-confusion":5,"chain-rule-inner-derivative-omitted":5,"circle-area-circumference":5,"circle-radius-squared":5,"combination-no-denominator":5,"combine-unlike-terms":5,"complete-square-naive":5,"composite-function-commutes":5,"cone-volume-no-third":5,"conjugate-product-sum":5,"decimal-mult-place":5,"difference-of-squares-confused":5,"distribute-first-term-only":5,"distribution-over-power":4,"exponent-product-multiplies":5,"exponent-zero":5,"fraction-addition-naive":5,"fraction-cancellation":5,"gambler-fallacy":4,"gcd-lcm-confused":4,"log-distribution":4,"midpoint-sum-only":4,"mixed-number-mult-whole":4,"negative-distribute-sign":4,"negative-even-power-sign":4,"negative-square-precedence":4,"negative-times-negative":4,"period-of-scaled-sine":4,"power-of-power-adds":4,"product-rule-naive":5,"remainder-theorem-sign":4,"same-item-permutation-no-divide":4,"scale-area-linear":4,"scale-volume-linear":4,"sine-distributes-over-sum":4,"sqrt-distributes-over-sum":4,"square-of-difference-no-cross":4,"square-root-positivity":4,"subtract-negative-sign":4,"translation-sign-flip":5,"transpose-no-sign-change":4,"trapezoid-area-no-half":4,"vieta-sign-error":4},"difficulty_min":2.5,"difficulty_max":3.5,"missing_required_misconceptions":["extremum-max-min-confused","extremum-value-vs-point-confused","factor-sign-flip","opposite-root-selected"]} -->
