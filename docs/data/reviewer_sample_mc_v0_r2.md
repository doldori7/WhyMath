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

## 표본 02 · `wm-misc-eval-mc-1f9b1884d949`

- 도메인: `ABS-VALUE` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.4
- 성취기준: [9수01-04]

**문항**: |-10| + 21 의 값을 구하시오.

**정답**: `31`

**풀이**: 절댓값은 음이 아니므로 |-10| = 10 이고 |-10| + 21 = 31 이다. 절댓값이 음수 부호를 유지한다고 여기면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 10+21` · answer_map: {x=31}

**선지**:
- ① `-31` ← 정답
- ② `-11` ← 정답
- ③ `11` ← 오답 · 오개념 `absolute-value-keeps-sign`
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

## 표본 03 · `wm-misc-eval-mc-40eaaea68255`

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

## 표본 04 · `wm-misc-eval-mc-1d192c96f608`

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

## 표본 05 · `wm-misc-eval-mc-2c095ce54863`

- 도메인: `ABS-VALUE` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.5
- 성취기준: [9수01-04]

**문항**: |-2| + 9 의 값을 구하시오.

**정답**: `11`

**풀이**: 절댓값은 음이 아니므로 |-2| = 2 이고 |-2| + 9 = 11 이다. 절댓값이 음수 부호를 유지한다고 여기면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 2+9` · answer_map: {x=11}

**선지**:
- ① `-11` ← 정답
- ② `-7` ← 정답
- ③ `7` ← 오답 · 오개념 `absolute-value-keeps-sign`
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

## 표본 06 · `wm-misc-eval-mc-dd8f92ebd07a`

- 도메인: `AREA-PERIMETER` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.4
- 성취기준: [12직수03-04], [6수03-11], [6수03-13]

**문항**: 가로가 8, 세로가 12 인 직사각형의 넓이를 구하시오.

**정답**: `96`

**풀이**: 직사각형의 넓이는 가로×세로 = 8×12 = 96 이다. 둘레 2×(8+12) = 40 과 혼동하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 8*12` · answer_map: {x=96}

**선지**:
- ① `20` ← 정답
- ② `40` ← 오답 · 오개념 `area-perimeter-confusion`
- ③ `96` ← 정답
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

## 표본 07 · `wm-misc-eval-mc-ef4a863c7421`

- 도메인: `AREA-PERIMETER` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.6
- 성취기준: [12직수03-04], [6수03-11], [6수03-13]

**문항**: 가로가 3, 세로가 9 인 직사각형의 넓이를 구하시오.

**정답**: `27`

**풀이**: 직사각형의 넓이는 가로×세로 = 3×9 = 27 이다. 둘레 2×(3+9) = 24 와 혼동하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 3*9` · answer_map: {x=27}

**선지**:
- ① `12` ← 정답
- ② `24` ← 오답 · 오개념 `area-perimeter-confusion`
- ③ `27` ← 정답
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

## 표본 08 · `wm-misc-eval-mc-b27e88351acb`

- 도메인: `AREA-PERIMETER` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.2
- 성취기준: [12직수03-04], [6수03-11], [6수03-13]

**문항**: 가로가 3, 세로가 15 인 직사각형의 넓이를 구하시오.

**정답**: `45`

**풀이**: 직사각형의 넓이는 가로×세로 = 3×15 = 45 이다. 둘레 2×(3+15) = 36 과 혼동하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 3*15` · answer_map: {x=45}

**선지**:
- ① `18` ← 정답
- ② `36` ← 오답 · 오개념 `area-perimeter-confusion`
- ③ `45` ← 정답
- ④ `90` ← 정답

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

## 표본 09 · `wm-misc-eval-mc-193d905f3fa8`

- 도메인: `AREA-PERIMETER` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.9
- 성취기준: [12직수03-04], [6수03-11], [6수03-13]

**문항**: 가로가 11, 세로가 15 인 직사각형의 넓이를 구하시오.

**정답**: `165`

**풀이**: 직사각형의 넓이는 가로×세로 = 11×15 = 165 이다. 둘레 2×(11+15) = 52 와 혼동하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 11*15` · answer_map: {x=165}

**선지**:
- ① `26` ← 정답
- ② `52` ← 오답 · 오개념 `area-perimeter-confusion`
- ③ `165` ← 정답
- ④ `330` ← 정답

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

## 표본 10 · `wm-misc-eval-mc-36e264e9ed41`

- 도메인: `AREA-PERIMETER` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.5
- 성취기준: [12직수03-04], [6수03-11], [6수03-13]

**문항**: 가로가 8, 세로가 14 인 직사각형의 넓이를 구하시오.

**정답**: `112`

**풀이**: 직사각형의 넓이는 가로×세로 = 8×14 = 112 이다. 둘레 2×(8+14) = 44 와 혼동하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 8*14` · answer_map: {x=112}

**선지**:
- ① `22` ← 정답
- ② `44` ← 오답 · 오개념 `area-perimeter-confusion`
- ③ `112` ← 정답
- ④ `224` ← 정답

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

## 표본 11 · `wm-misc-eval-mc-888ee9abe651`

- 도메인: `CALC-CHAIN` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.5
- 성취기준: [12미적Ⅰ-02-01], [12미적Ⅱ-02-05]

**문항**: 함수 f(x) = (4x + 2)^3 의 x = 1 에서의 미분계수 f'(1) 의 값을 구하시오.

**정답**: `432`

**풀이**: 연쇄법칙으로 도함수를 구하면 내부 함수의 도함수 4 를 곱해야 한다. x = 1 을 대입하면 미분계수는 432 이다. 내부 도함수 4 를 곱하지 않으면 틀린 값이 된다.

**verify(SymPy 입력)**: conditions: `x = 3*4*(4*1+2)**2` · answer_map: {x=432}

**선지**:
- ① `108` ← 오답 · 오개념 `chain-rule-inner-derivative-omitted` (op: `chain-rule-omit-inner`)
- ② `144` ← 정답
- ③ `432` ← 정답
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

## 표본 12 · `wm-misc-eval-mc-47accf44cdde`

- 도메인: `CALC-CHAIN` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.3
- 성취기준: [12미적Ⅰ-02-01], [12미적Ⅱ-02-05]

**문항**: 함수 f(x) = (5x + 4)^3 의 x = 2 에서의 미분계수 f'(2) 의 값을 구하시오.

**정답**: `2940`

**풀이**: 연쇄법칙으로 도함수를 구하면 내부 함수의 도함수 5 를 곱해야 한다. x = 2 를 대입하면 미분계수는 2940 이다. 내부 도함수 5 를 곱하지 않으면 틀린 값이 된다.

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

## 표본 13 · `wm-misc-eval-mc-4ed509a782b9`

- 도메인: `CALC-CHAIN` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.2
- 성취기준: [12미적Ⅰ-02-01], [12미적Ⅱ-02-05]

**문항**: 함수 f(x) = (2x + 3)^3 의 x = 1 에서의 미분계수 f'(1) 의 값을 구하시오.

**정답**: `150`

**풀이**: 연쇄법칙으로 도함수를 구하면 내부 함수의 도함수 2 를 곱해야 한다. x = 1 을 대입하면 미분계수는 150 이다. 내부 도함수 2 를 곱하지 않으면 틀린 값이 된다.

**verify(SymPy 입력)**: conditions: `x = 3*2*(2*1+3)**2` · answer_map: {x=150}

**선지**:
- ① `50` ← 정답
- ② `75` ← 오답 · 오개념 `chain-rule-inner-derivative-omitted` (op: `chain-rule-omit-inner`)
- ③ `150` ← 정답
- ④ `300` ← 정답

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

**풀이**: 연쇄법칙으로 도함수를 구하면 내부 함수의 도함수 4 를 곱해야 한다. x = 2 를 대입하면 미분계수는 1452 이다. 내부 도함수 4 를 곱하지 않으면 틀린 값이 된다.

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

## 표본 16 · `wm-misc-eval-mc-0d20aaf6fd12`

- 도메인: `CALC-PRODUCT` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.4
- 성취기준: [12미적Ⅰ-02-01], [12미적Ⅰ-02-04]

**문항**: 두 함수 f(x) = x^1, g(x) = x^2 에 대하여 함수 f(x)g(x) 의 x = 6 에서의 미분계수를 구하시오.

**정답**: `108`

**풀이**: f(x)g(x) = x^3 이므로 미분계수는 3·6^2 = 108 이다. (fg)' = f'g' 로 오인하면 틀린 값이 된다.

**verify(SymPy 입력)**: conditions: `x = 3*6**2` · answer_map: {x=108}

**선지**:
- ① `12` ← 오답 · 오개념 `product-rule-naive`
- ② `72` ← 정답
- ③ `108` ← 정답
- ④ `648` ← 정답

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

## 표본 17 · `wm-misc-eval-mc-e8eec835098d`

- 도메인: `CALC-PRODUCT` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.5
- 성취기준: [12미적Ⅰ-02-01], [12미적Ⅰ-02-04]

**문항**: 두 함수 f(x) = x^1, g(x) = x^1 에 대하여 함수 f(x)g(x) 의 x = 8 에서의 미분계수를 구하시오.

**정답**: `16`

**풀이**: f(x)g(x) = x^2 이므로 미분계수는 2·8^1 = 16 이다. (fg)' = f'g' 로 오인하면 틀린 값이 된다.

**verify(SymPy 입력)**: conditions: `x = 2*8**1` · answer_map: {x=16}

**선지**:
- ① `1` ← 오답 · 오개념 `product-rule-naive`
- ② `8` ← 정답
- ③ `16` ← 정답
- ④ `128` ← 정답

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

## 표본 19 · `wm-misc-eval-mc-263caac417f2`

- 도메인: `CALC-PRODUCT` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.2
- 성취기준: [12미적Ⅰ-02-01], [12미적Ⅰ-02-04]

**문항**: 두 함수 f(x) = x^1, g(x) = x^1 에 대하여 함수 f(x)g(x) 의 x = 5 에서의 미분계수를 구하시오.

**정답**: `10`

**풀이**: f(x)g(x) = x^2 이므로 미분계수는 2·5^1 = 10 이다. (fg)' = f'g' 로 오인하면 틀린 값이 된다.

**verify(SymPy 입력)**: conditions: `x = 2*5**1` · answer_map: {x=10}

**선지**:
- ① `1` ← 오답 · 오개념 `product-rule-naive`
- ② `5` ← 정답
- ③ `10` ← 정답
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

## 표본 20 · `wm-misc-eval-mc-7f0a47e53b77`

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

## 표본 21 · `wm-misc-eval-mc-43010c98e684`

- 도메인: `CIRCLE-AREA` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.4
- 성취기준: [6수03-16], [9수03-06]

**문항**: 반지름이 20 인 원의 넓이를 원주율 π로 나눈 값을 구하시오.

**정답**: `400`

**풀이**: 원의 넓이는 π×(반지름)² 이므로 π로 나눈 값은 20² 곧 400 이다. 원의 둘레 공식 2πr 과 혼동하면 2×20 곧 40 으로 잘못 답한다.

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

## 표본 22 · `wm-misc-eval-mc-a62f0388d4dc`

- 도메인: `CIRCLE-AREA` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.8
- 성취기준: [6수03-16], [9수03-06]

**문항**: 반지름이 25 인 원의 넓이를 원주율 π로 나눈 값을 구하시오.

**정답**: `625`

**풀이**: 원의 넓이는 π×(반지름)² 이므로 π로 나눈 값은 25² 곧 625 이다. 원의 둘레 공식 2πr 과 혼동하면 2×25 곧 50 으로 잘못 답한다.

**verify(SymPy 입력)**: conditions: `x = 25**2` · answer_map: {x=625}

**선지**:
- ① `25` ← 정답
- ② `50` ← 오답 · 오개념 `circle-area-circumference`
- ③ `625` ← 정답
- ④ `1250` ← 정답

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

## 표본 23 · `wm-misc-eval-mc-21a206f66b21`

- 도메인: `CIRCLE-AREA` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3
- 성취기준: [6수03-16], [9수03-06]

**문항**: 반지름이 5 인 원의 넓이를 원주율 π로 나눈 값을 구하시오.

**정답**: `25`

**풀이**: 원의 넓이는 π×(반지름)² 이므로 π로 나눈 값은 5² 곧 25 이다. 원의 둘레 공식 2πr 과 혼동하면 2×5 곧 10 으로 잘못 답한다.

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

## 표본 24 · `wm-misc-eval-mc-17783181c907`

- 도메인: `CIRCLE-AREA` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.2
- 성취기준: [6수03-16], [9수03-06]

**문항**: 반지름이 7 인 원의 넓이를 원주율 π로 나눈 값을 구하시오.

**정답**: `49`

**풀이**: 원의 넓이는 π×(반지름)² 이므로 π로 나눈 값은 7² 곧 49 이다. 원의 둘레 공식 2πr 과 혼동하면 2×7 곧 14 로 잘못 답한다.

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

## 표본 25 · `wm-misc-eval-mc-6aca045ddacc`

- 도메인: `CIRCLE-AREA` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.6
- 성취기준: [6수03-16], [9수03-06]

**문항**: 반지름이 23 인 원의 넓이를 원주율 π로 나눈 값을 구하시오.

**정답**: `529`

**풀이**: 원의 넓이는 π×(반지름)² 이므로 π로 나눈 값은 23² 곧 529 이다. 원의 둘레 공식 2πr 과 혼동하면 2×23 곧 46 으로 잘못 답한다.

**verify(SymPy 입력)**: conditions: `x = 23**2` · answer_map: {x=529}

**선지**:
- ① `23` ← 정답
- ② `46` ← 오답 · 오개념 `circle-area-circumference`
- ③ `529` ← 정답
- ④ `1058` ← 정답

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

**풀이**: x² + y² = r² 에서 반지름은 r 이므로 r² = 529 이면 반지름은 23 이다. 우변 529 를 반지름으로 여기면 틀린다.

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

## 표본 28 · `wm-misc-eval-mc-ee7d31a789f9`

- 도메인: `CIRCLE-RADIUS` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3
- 성취기준: [10공수2-01-04], [10기수2-01-04], [12기하02-05]

**문항**: 원 x^2 + y^2 = 25 의 반지름의 길이를 구하시오.

**정답**: `5`

**풀이**: x² + y² = r² 에서 반지름은 r 이므로 r² = 25 이면 반지름은 5 이다. 우변 25 를 반지름으로 여기면 틀린다.

**verify(SymPy 입력)**: conditions: `x = sqrt(25)` · answer_map: {x=5}

**선지**:
- ① `5` ← 정답
- ② `10` ← 정답
- ③ `25` ← 오답 · 오개념 `circle-radius-squared`
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

## 표본 29 · `wm-misc-eval-mc-c0fc6035800b`

- 도메인: `CIRCLE-RADIUS` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.2
- 성취기준: [10공수2-01-04], [10기수2-01-04], [12기하02-05]

**문항**: 원 x^2 + y^2 = 49 의 반지름의 길이를 구하시오.

**정답**: `7`

**풀이**: x² + y² = r² 에서 반지름은 r 이므로 r² = 49 이면 반지름은 7 이다. 우변 49 를 반지름으로 여기면 틀린다.

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

## 표본 30 · `wm-misc-eval-mc-da3631ce937f`

- 도메인: `CIRCLE-RADIUS` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.8
- 성취기준: [10공수2-01-04], [10기수2-01-04], [12기하02-05]

**문항**: 원 x^2 + y^2 = 625 의 반지름의 길이를 구하시오.

**정답**: `25`

**풀이**: x² + y² = r² 에서 반지름은 r 이므로 r² = 625 이면 반지름은 25 이다. 우변 625 를 반지름으로 여기면 틀린다.

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

## 표본 31 · `wm-misc-eval-mc-45c0bef71ebf`

- 도메인: `COMBINATION-COUNT` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.4
- 성취기준: [10공수1-03-03], [12직수04-01]

**문항**: 서로 다른 17 개에서 3 개를 뽑는 조합의 수 17C3 을 구하시오.

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

## 표본 32 · `wm-misc-eval-mc-186d3ee72dc0`

- 도메인: `COMBINATION-COUNT` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.7
- 성취기준: [10공수1-03-03], [12직수04-01]

**문항**: 서로 다른 20 개에서 4 개를 뽑는 조합의 수 20C4 를 구하시오.

**정답**: `4845`

**풀이**: 20C4 = 20!/(4!×16!) = 4845 이다. 분모의 4! 을 빠뜨리면 순열의 수 20P4 = 116280 이 되어 틀린다.

**verify(SymPy 입력)**: conditions: `x = 4845` · answer_map: {x=4845}

**선지**:
- ① `24` ← 정답
- ② `80` ← 정답
- ③ `4845` ← 정답
- ④ `116280` ← 오답 · 오개념 `combination-no-denominator`

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

## 표본 33 · `wm-misc-eval-mc-070713f3a9f3`

- 도메인: `COMBINATION-COUNT` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.1
- 성취기준: [10공수1-03-03], [12직수04-01]

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

## 표본 34 · `wm-misc-eval-mc-1e905e501397`

- 도메인: `COMBINATION-COUNT` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.5
- 성취기준: [10공수1-03-03], [12직수04-01]

**문항**: 서로 다른 8 개에서 3 개를 뽑는 조합의 수 8C3 을 구하시오.

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

## 표본 35 · `wm-misc-eval-mc-bbe9890e9aa9`

- 도메인: `COMBINATION-COUNT` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.8
- 성취기준: [10공수1-03-03], [12직수04-01]

**문항**: 서로 다른 22 개에서 3 개를 뽑는 조합의 수 22C3 을 구하시오.

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

**풀이**: 차수가 다른 항은 따로 계산하므로 2x + 6x² 은 x = 8 에서 16 + 384 = 400 이다. 차수를 무시하고 8x³으로 결합하면 틀린다.

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

## 표본 37 · `wm-misc-eval-mc-331dbfee9bf5`

- 도메인: `COMBINE-UNLIKE` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.6
- 성취기준: [9수02-09]

**문항**: 3x + 5x² 에서 x = 4 일 때의 값을 구하시오.

**정답**: `92`

**풀이**: 차수가 다른 항은 따로 계산하므로 3x + 5x² 은 x = 4 에서 12 + 80 = 92 이다. 차수를 무시하고 8x³으로 결합하면 틀린다.

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

## 표본 38 · `wm-misc-eval-mc-32442010e96b`

- 도메인: `COMBINE-UNLIKE` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.7
- 성취기준: [9수02-09]

**문항**: 3x + 4x² 에서 x = 6 일 때의 값을 구하시오.

**정답**: `162`

**풀이**: 차수가 다른 항은 따로 계산하므로 3x + 4x² 은 x = 6 에서 18 + 144 = 162 이다. 차수를 무시하고 7x³으로 결합하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 3*6 + 4*6**2` · answer_map: {x=162}

**선지**:
- ① `18` ← 정답
- ② `144` ← 정답
- ③ `162` ← 정답
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

## 표본 39 · `wm-misc-eval-mc-4942d70f22e2`

- 도메인: `COMBINE-UNLIKE` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.9
- 성취기준: [9수02-09]

**문항**: 3x + 5x² 에서 x = 7 일 때의 값을 구하시오.

**정답**: `266`

**풀이**: 차수가 다른 항은 따로 계산하므로 3x + 5x² 은 x = 7 에서 21 + 245 = 266 이다. 차수를 무시하고 8x³으로 결합하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 3*7 + 5*7**2` · answer_map: {x=266}

**선지**:
- ① `21` ← 정답
- ② `245` ← 정답
- ③ `266` ← 정답
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

## 표본 40 · `wm-misc-eval-mc-40e81e5712ae`

- 도메인: `COMBINE-UNLIKE` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.4
- 성취기준: [9수02-09]

**문항**: 3x + 4x² 에서 x = 2 일 때의 값을 구하시오.

**정답**: `22`

**풀이**: 차수가 다른 항은 따로 계산하므로 3x + 4x² 은 x = 2 에서 6 + 16 = 22 이다. 차수를 무시하고 7x³으로 결합하면 틀린다.

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

## 표본 41 · `wm-misc-eval-mc-43f0f83fcfd8`

- 도메인: `COMPLETE-SQUARE` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.4
- 성취기준: [9수02-19]

**문항**: x² + 2x 에서 x = 7 일 때의 값을 구하시오.

**정답**: `63`

**풀이**: x² + 2x 는 x = 7 에서 49 + 14 = 63 이다. 이를 (x+2)²으로 오인하면 (7+2)² = 81 이 되어 틀린다.

**verify(SymPy 입력)**: conditions: `x = 7**2 + 2*7` · answer_map: {x=63}

**선지**:
- ① `14` ← 정답
- ② `49` ← 정답
- ③ `63` ← 정답
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

## 표본 42 · `wm-misc-eval-mc-2bd8f127cfd6`

- 도메인: `COMPLETE-SQUARE` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.9
- 성취기준: [9수02-19]

**문항**: x² + 6x 에서 x = 9 일 때의 값을 구하시오.

**정답**: `135`

**풀이**: x² + 6x 는 x = 9 에서 81 + 54 = 135 이다. 이를 (x+6)²으로 오인하면 (9+6)² = 225 가 되어 틀린다.

**verify(SymPy 입력)**: conditions: `x = 9**2 + 6*9` · answer_map: {x=135}

**선지**:
- ① `54` ← 정답
- ② `81` ← 정답
- ③ `135` ← 정답
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

## 표본 43 · `wm-misc-eval-mc-9033ca808ea6`

- 도메인: `COMPLETE-SQUARE` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.3
- 성취기준: [9수02-19]

**문항**: x² + 11x 에서 x = 8 일 때의 값을 구하시오.

**정답**: `152`

**풀이**: x² + 11x 는 x = 8 에서 64 + 88 = 152 이다. 이를 (x+11)²으로 오인하면 (8+11)² = 361 이 되어 틀린다.

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

## 표본 44 · `wm-misc-eval-mc-d36d3ebfa81e`

- 도메인: `COMPLETE-SQUARE` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.6
- 성취기준: [9수02-19]

**문항**: x² + 3x 에서 x = 9 일 때의 값을 구하시오.

**정답**: `108`

**풀이**: x² + 3x 는 x = 9 에서 81 + 27 = 108 이다. 이를 (x+3)²으로 오인하면 (9+3)² = 144 가 되어 틀린다.

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

## 표본 45 · `wm-misc-eval-mc-bfeb183216e2`

- 도메인: `COMPLETE-SQUARE` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.1
- 성취기준: [9수02-19]

**문항**: x² + 11x 에서 x = 6 일 때의 값을 구하시오.

**정답**: `102`

**풀이**: x² + 11x 는 x = 6 에서 36 + 66 = 102 이다. 이를 (x+11)²으로 오인하면 (6+11)² = 289 가 되어 틀린다.

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

## 표본 46 · `wm-misc-eval-mc-43761c491be3`

- 도메인: `CONE-VOLUME` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.4
- 성취기준: [9수03-08]

**문항**: 밑면의 반지름이 2, 높이가 18 인 원뿔의 부피를 원주율 π로 나눈 값을 구하시오.

**정답**: `24`

**풀이**: 원뿔의 부피는 ⅓×π×(반지름)²×높이 이므로 π로 나눈 값은 2²×18÷3 곧 24 이다. ⅓ 을 빠뜨려 원기둥 부피로 계산하면 72 가 되어 틀린다.

**verify(SymPy 입력)**: conditions: `x = 2**2*18/3` · answer_map: {x=24}

**선지**:
- ① `24` ← 정답
- ② `36` ← 정답
- ③ `48` ← 정답
- ④ `72` ← 오답 · 오개념 `cone-volume-no-third`

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

## 표본 47 · `wm-misc-eval-mc-6e857921f843`

- 도메인: `CONE-VOLUME` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.8
- 성취기준: [9수03-08]

**문항**: 밑면의 반지름이 1, 높이가 24 인 원뿔의 부피를 원주율 π로 나눈 값을 구하시오.

**정답**: `8`

**풀이**: 원뿔의 부피는 ⅓×π×(반지름)²×높이 이므로 π로 나눈 값은 1²×24÷3 곧 8 이다. ⅓ 을 빠뜨려 원기둥 부피로 계산하면 24 가 되어 틀린다.

**verify(SymPy 입력)**: conditions: `x = 1**2*24/3` · answer_map: {x=8}

**선지**:
- ① `8` ← 정답
- ② `12` ← 정답
- ③ `16` ← 정답
- ④ `24` ← 오답 · 오개념 `cone-volume-no-third`

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

## 표본 48 · `wm-misc-eval-mc-c2f74c881635`

- 도메인: `CONE-VOLUME` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.1
- 성취기준: [9수03-08]

**문항**: 밑면의 반지름이 6, 높이가 22 인 원뿔의 부피를 원주율 π로 나눈 값을 구하시오.

**정답**: `264`

**풀이**: 원뿔의 부피는 ⅓×π×(반지름)²×높이 이므로 π로 나눈 값은 6²×22÷3 곧 264 이다. ⅓ 을 빠뜨려 원기둥 부피로 계산하면 792 가 되어 틀린다.

**verify(SymPy 입력)**: conditions: `x = 6**2*22/3` · answer_map: {x=264}

**선지**:
- ① `264` ← 정답
- ② `396` ← 정답
- ③ `528` ← 정답
- ④ `792` ← 오답 · 오개념 `cone-volume-no-third`

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

## 표본 49 · `wm-misc-eval-mc-1071c0577851`

- 도메인: `CONE-VOLUME` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.3
- 성취기준: [9수03-08]

**문항**: 밑면의 반지름이 3, 높이가 16 인 원뿔의 부피를 원주율 π로 나눈 값을 구하시오.

**정답**: `48`

**풀이**: 원뿔의 부피는 ⅓×π×(반지름)²×높이 이므로 π로 나눈 값은 3²×16÷3 곧 48 이다. ⅓ 을 빠뜨려 원기둥 부피로 계산하면 144 가 되어 틀린다.

**verify(SymPy 입력)**: conditions: `x = 3**2*16/3` · answer_map: {x=48}

**선지**:
- ① `48` ← 정답
- ② `72` ← 정답
- ③ `96` ← 정답
- ④ `144` ← 오답 · 오개념 `cone-volume-no-third`

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

## 표본 50 · `wm-misc-eval-mc-86534071761f`

- 도메인: `CONE-VOLUME` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.5
- 성취기준: [9수03-08]

**문항**: 밑면의 반지름이 6, 높이가 27 인 원뿔의 부피를 원주율 π로 나눈 값을 구하시오.

**정답**: `324`

**풀이**: 원뿔의 부피는 ⅓×π×(반지름)²×높이 이므로 π로 나눈 값은 6²×27÷3 곧 324 이다. ⅓ 을 빠뜨려 원기둥 부피로 계산하면 972 가 되어 틀린다.

**verify(SymPy 입력)**: conditions: `x = 6**2*27/3` · answer_map: {x=324}

**선지**:
- ① `324` ← 정답
- ② `486` ← 정답
- ③ `648` ← 정답
- ④ `972` ← 오답 · 오개념 `cone-volume-no-third`

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

## 표본 51 · `wm-misc-eval-mc-9e0de74f70fe`

- 도메인: `CONJUGATE-PRODUCT` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.6
- 성취기준: [9수01-07]

**문항**: (√23 + 1)(√23 - 1) 의 값을 구하시오.

**정답**: `22`

**풀이**: 켤레 무리수의 곱은 (√23)² - 1² = 23 - 1 = 22 이다. 합차공식 부호를 오용해 23 + 1로 답하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 23 - 1` · answer_map: {x=22}

**선지**:
- ① `22` ← 정답
- ② `23` ← 정답
- ③ `24` ← 오답 · 오개념 `conjugate-product-sum`
- ④ `46` ← 정답

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

## 표본 52 · `wm-misc-eval-mc-a5216b8500ac`

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

## 표본 53 · `wm-misc-eval-mc-ff13e0735b6c`

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

## 표본 54 · `wm-misc-eval-mc-3ffbd1916ddd`

- 도메인: `CONJUGATE-PRODUCT` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3
- 성취기준: [9수01-07]

**문항**: (√16 + 1)(√16 - 1) 의 값을 구하시오.

**정답**: `15`

**풀이**: 켤레 무리수의 곱은 (√16)² - 1² = 16 - 1 = 15 이다. 합차공식 부호를 오용해 16 + 1로 답하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 16 - 1` · answer_map: {x=15}

**선지**:
- ① `15` ← 정답
- ② `16` ← 정답
- ③ `17` ← 오답 · 오개념 `conjugate-product-sum`
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

## 표본 55 · `wm-misc-eval-mc-4da26685b702`

- 도메인: `CONJUGATE-PRODUCT` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.8
- 성취기준: [9수01-07]

**문항**: (√14 + 1)(√14 - 1) 의 값을 구하시오.

**정답**: `13`

**풀이**: 켤레 무리수의 곱은 (√14)² - 1² = 14 - 1 = 13 이다. 합차공식 부호를 오용해 14 + 1로 답하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 14 - 1` · answer_map: {x=13}

**선지**:
- ① `13` ← 정답
- ② `14` ← 정답
- ③ `15` ← 오답 · 오개념 `conjugate-product-sum`
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

## 표본 56 · `wm-misc-eval-mc-5d420b6f13eb`

- 도메인: `DECIMAL-MULT` · 발문형식: 객관식 · 정답형식: 실수 · 난이도: 3.4
- 성취기준: [6수01-13]

**문항**: 0.4 × 0.5 의 값을 구하시오.

**정답**: `1/5`

**풀이**: 0.4 × 0.5 는 소수점 아래 자릿수를 더해 20/100 = 1/5 이다. 자릿수를 무시하면 20/10으로 틀린다.

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

## 표본 57 · `wm-misc-eval-mc-45546cd0c03b`

- 도메인: `DECIMAL-MULT` · 발문형식: 객관식 · 정답형식: 실수 · 난이도: 2.9
- 성취기준: [6수01-13]

**문항**: 0.7 × 0.8 의 값을 구하시오.

**정답**: `14/25`

**풀이**: 0.7 × 0.8 은 소수점 아래 자릿수를 더해 56/100 = 14/25 이다. 자릿수를 무시하면 56/10으로 틀린다.

**verify(SymPy 입력)**: conditions: `x = 7*8/100` · answer_map: {x=14/25}

**선지**:
- ① `14/25` ← 정답
- ② `7/10` ← 정답
- ③ `4/5` ← 정답
- ④ `28/5` ← 오답 · 오개념 `decimal-mult-place`

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

## 표본 58 · `wm-misc-eval-mc-dd3aeb29ac04`

- 도메인: `DECIMAL-MULT` · 발문형식: 객관식 · 정답형식: 실수 · 난이도: 2.5
- 성취기준: [6수01-13]

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

## 표본 59 · `wm-misc-eval-mc-5557a2e7e34e`

- 도메인: `DECIMAL-MULT` · 발문형식: 객관식 · 정답형식: 실수 · 난이도: 2.7
- 성취기준: [6수01-13]

**문항**: 0.6 × 0.7 의 값을 구하시오.

**정답**: `21/50`

**풀이**: 0.6 × 0.7 은 소수점 아래 자릿수를 더해 42/100 = 21/50 이다. 자릿수를 무시하면 42/10로 틀린다.

**verify(SymPy 입력)**: conditions: `x = 6*7/100` · answer_map: {x=21/50}

**선지**:
- ① `21/50` ← 정답
- ② `3/5` ← 정답
- ③ `7/10` ← 정답
- ④ `21/5` ← 오답 · 오개념 `decimal-mult-place`

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

## 표본 60 · `wm-misc-eval-mc-b1a09d11cfbc`

- 도메인: `DECIMAL-MULT` · 발문형식: 객관식 · 정답형식: 실수 · 난이도: 3.1
- 성취기준: [6수01-13]

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

## 표본 61 · `wm-misc-eval-mc-b58ab5ab09b6`

- 도메인: `DIFF-SQUARES` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.6
- 성취기준: [9수02-19]

**문항**: x = 16, a = 7 일 때 x² - a² 의 값을 구하시오.

**정답**: `207`

**풀이**: x² - a² = (x-a)(x+a) 이므로 x=16, a=7 을 대입하면 207 이다. 제곱의 차를 차의 제곱 (x-a)²으로 여기면 틀린다.

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

## 표본 62 · `wm-misc-eval-mc-051533c1ce74`

- 도메인: `DIFF-SQUARES` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.5
- 성취기준: [9수02-19]

**문항**: x = 6, a = 4 일 때 x² - a² 의 값을 구하시오.

**정답**: `20`

**풀이**: x² - a² = (x-a)(x+a) 이므로 x=6, a=4 를 대입하면 20 이다. 제곱의 차를 차의 제곱 (x-a)²으로 여기면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 20` · answer_map: {x=20}

**선지**:
- ① `4` ← 오답 · 오개념 `difference-of-squares-confused`
- ② `20` ← 정답
- ③ `52` ← 정답
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

## 표본 63 · `wm-misc-eval-mc-d48add54ec78`

- 도메인: `DIFF-SQUARES` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.2
- 성취기준: [9수02-19]

**문항**: x = 14, a = 4 일 때 x² - a² 의 값을 구하시오.

**정답**: `180`

**풀이**: x² - a² = (x-a)(x+a) 이므로 x=14, a=4 를 대입하면 180 이다. 제곱의 차를 차의 제곱 (x-a)²으로 여기면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 180` · answer_map: {x=180}

**선지**:
- ① `100` ← 오답 · 오개념 `difference-of-squares-confused`
- ② `180` ← 정답
- ③ `212` ← 정답
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

## 표본 64 · `wm-misc-eval-mc-e4dd35395df3`

- 도메인: `DIFF-SQUARES` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.1
- 성취기준: [9수02-19]

**문항**: x = 10, a = 7 일 때 x² - a² 의 값을 구하시오.

**정답**: `51`

**풀이**: x² - a² = (x-a)(x+a) 이므로 x=10, a=7 을 대입하면 51 이다. 제곱의 차를 차의 제곱 (x-a)²으로 여기면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 51` · answer_map: {x=51}

**선지**:
- ① `9` ← 오답 · 오개념 `difference-of-squares-confused`
- ② `51` ← 정답
- ③ `149` ← 정답
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

## 표본 65 · `wm-misc-eval-mc-86b795e4af38`

- 도메인: `DIFF-SQUARES` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.9
- 성취기준: [9수02-19]

**문항**: x = 19, a = 7 일 때 x² - a² 의 값을 구하시오.

**정답**: `312`

**풀이**: x² - a² = (x-a)(x+a) 이므로 x=19, a=7 을 대입하면 312 이다. 제곱의 차를 차의 제곱 (x-a)²으로 여기면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 312` · answer_map: {x=312}

**선지**:
- ① `144` ← 오답 · 오개념 `difference-of-squares-confused`
- ② `312` ← 정답
- ③ `410` ← 정답
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

## 표본 66 · `wm-misc-eval-mc-763ae8923ec0`

- 도메인: `DISTRIBUTE-PARTIAL` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.9
- 성취기준: [9수02-10]

**문항**: 6(x + 2) 에서 x = 7 일 때의 값을 구하시오.

**정답**: `54`

**풀이**: 분배법칙으로 6(x + 2) = 6x + 12 이므로 x = 7 을 대입하면 54 이다. 뒷항을 분배하지 않고 42 + 2로 계산하면 틀린다.

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

## 표본 67 · `wm-misc-eval-mc-f31af922d8d9`

- 도메인: `DISTRIBUTE-PARTIAL` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.2
- 성취기준: [9수02-10]

**문항**: 5(x + 5) 에서 x = 8 일 때의 값을 구하시오.

**정답**: `65`

**풀이**: 분배법칙으로 5(x + 5) = 5x + 25 이므로 x = 8 을 대입하면 65 이다. 뒷항을 분배하지 않고 40 + 5로 계산하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 5 * (8 + 5)` · answer_map: {x=65}

**선지**:
- ① `25` ← 정답
- ② `40` ← 정답
- ③ `45` ← 오답 · 오개념 `distribute-first-term-only`
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

## 표본 68 · `wm-misc-eval-mc-b6ede37b407c`

- 도메인: `DISTRIBUTE-PARTIAL` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.4
- 성취기준: [9수02-10]

**문항**: 6(x + 6) 에서 x = 8 일 때의 값을 구하시오.

**정답**: `84`

**풀이**: 분배법칙으로 6(x + 6) = 6x + 36 이므로 x = 8 을 대입하면 84 이다. 뒷항을 분배하지 않고 48 + 6으로 계산하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 6 * (8 + 6)` · answer_map: {x=84}

**선지**:
- ① `36` ← 정답
- ② `48` ← 정답
- ③ `54` ← 오답 · 오개념 `distribute-first-term-only`
- ④ `84` ← 정답

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

## 표본 69 · `wm-misc-eval-mc-f6c035e0277a`

- 도메인: `DISTRIBUTE-PARTIAL` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.1
- 성취기준: [9수02-10]

**문항**: 2(x + 7) 에서 x = 8 일 때의 값을 구하시오.

**정답**: `30`

**풀이**: 분배법칙으로 2(x + 7) = 2x + 14 이므로 x = 8 을 대입하면 30 이다. 뒷항을 분배하지 않고 16 + 7로 계산하면 틀린다.

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

## 표본 70 · `wm-misc-eval-mc-8bfe811053a7`

- 도메인: `DISTRIBUTE-PARTIAL` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.6
- 성취기준: [9수02-10]

**문항**: 4(x + 2) 에서 x = 6 일 때의 값을 구하시오.

**정답**: `32`

**풀이**: 분배법칙으로 4(x + 2) = 4x + 8 이므로 x = 6 을 대입하면 32 이다. 뒷항을 분배하지 않고 24 + 2로 계산하면 틀린다.

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

## 표본 71 · `wm-misc-eval-mc-e97bcce9bb7c`

- 도메인: `EXP-PRODUCT` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.2
- 성취기준: [9수02-08]

**문항**: 7 × 7² 의 값을 구하시오.

**정답**: `343`

**풀이**: 밑이 같은 거듭제곱의 곱은 지수를 더하므로 7 × 7² = 7^(1+2) = 7³ = 343 이다. 지수를 곱해 7² 으로 답하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 7**3` · answer_map: {x=343}

**선지**:
- ① `7` ← 정답
- ② `49` ← 오답 · 오개념 `exponent-product-multiplies`
- ③ `343` ← 정답
- ④ `2401` ← 정답

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

## 표본 72 · `wm-misc-eval-mc-81e8bdcd0787`

- 도메인: `EXP-PRODUCT` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.4
- 성취기준: [9수02-08]

**문항**: 9 × 9² 의 값을 구하시오.

**정답**: `729`

**풀이**: 밑이 같은 거듭제곱의 곱은 지수를 더하므로 9 × 9² = 9^(1+2) = 9³ = 729 이다. 지수를 곱해 9² 으로 답하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 9**3` · answer_map: {x=729}

**선지**:
- ① `9` ← 정답
- ② `81` ← 오답 · 오개념 `exponent-product-multiplies`
- ③ `729` ← 정답
- ④ `6561` ← 정답

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

## 표본 73 · `wm-misc-eval-mc-6a05422170ba`

- 도메인: `EXP-PRODUCT` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.8
- 성취기준: [9수02-08]

**문항**: 25 × 25² 의 값을 구하시오.

**정답**: `15625`

**풀이**: 밑이 같은 거듭제곱의 곱은 지수를 더하므로 25 × 25² = 25^(1+2) = 25³ = 15625 이다. 지수를 곱해 25² 으로 답하면 틀린다.

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

## 표본 74 · `wm-misc-eval-mc-e18e217bca69`

- 도메인: `EXP-PRODUCT` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.6
- 성취기준: [9수02-08]

**문항**: 23 × 23² 의 값을 구하시오.

**정답**: `12167`

**풀이**: 밑이 같은 거듭제곱의 곱은 지수를 더하므로 23 × 23² = 23^(1+2) = 23³ = 12167 이다. 지수를 곱해 23² 으로 답하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 23**3` · answer_map: {x=12167}

**선지**:
- ① `23` ← 정답
- ② `529` ← 오답 · 오개념 `exponent-product-multiplies`
- ③ `12167` ← 정답
- ④ `279841` ← 정답

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

## 표본 75 · `wm-misc-eval-mc-795c45622f04`

- 도메인: `EXP-PRODUCT` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3
- 성취기준: [9수02-08]

**문항**: 16 × 16² 의 값을 구하시오.

**정답**: `4096`

**풀이**: 밑이 같은 거듭제곱의 곱은 지수를 더하므로 16 × 16² = 16^(1+2) = 16³ = 4096 이다. 지수를 곱해 16² 으로 답하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 16**3` · answer_map: {x=4096}

**선지**:
- ① `16` ← 정답
- ② `256` ← 오답 · 오개념 `exponent-product-multiplies`
- ③ `4096` ← 정답
- ④ `65536` ← 정답

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

## 표본 76 · `wm-misc-eval-mc-69d730b12ce2`

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

## 표본 77 · `wm-misc-eval-mc-98c224385f2b`

- 도메인: `EXP-ZERO` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.2
- 성취기준: [9수02-08]

**문항**: 자연수 a = 3 에 대하여 15 + a^0 의 값을 구하시오.

**정답**: `16`

**풀이**: a^0 = 1 이므로 15 + a^0 = 15 + 1 = 16 이다. a^0 을 0 으로 잘못 계산하면 15 가 되어 틀린다.

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

## 표본 78 · `wm-misc-eval-mc-d891fc9e19f8`

- 도메인: `EXP-ZERO` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.5
- 성취기준: [9수02-08]

**문항**: 자연수 a = 3 에 대하여 30 + a^0 의 값을 구하시오.

**정답**: `31`

**풀이**: a^0 = 1 이므로 30 + a^0 = 30 + 1 = 31 이다. a^0 을 0 으로 잘못 계산하면 30 이 되어 틀린다.

**verify(SymPy 입력)**: conditions: `x = 30 + 3**0` · answer_map: {x=31}

**선지**:
- ① `30` ← 오답 · 오개념 `exponent-zero`
- ② `31` ← 정답
- ③ `32` ← 정답
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

## 표본 79 · `wm-misc-eval-mc-da8fa977eb40`

- 도메인: `EXP-ZERO` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.5
- 성취기준: [9수02-08]

**문항**: 자연수 a = 3 에 대하여 18 + a^0 의 값을 구하시오.

**정답**: `19`

**풀이**: a^0 = 1 이므로 18 + a^0 = 18 + 1 = 19 이다. a^0 을 0 으로 잘못 계산하면 18 이 되어 틀린다.

**verify(SymPy 입력)**: conditions: `x = 18 + 3**0` · answer_map: {x=19}

**선지**:
- ① `18` ← 오답 · 오개념 `exponent-zero`
- ② `19` ← 정답
- ③ `20` ← 정답
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

## 표본 81 · `wm-misc-eval-mc-5dd31f351a30`

- 도메인: `FRACTION-ADD` · 발문형식: 객관식 · 정답형식: 분수 · 난이도: 3.1
- 성취기준: [9수01-05]

**문항**: 1/7 + 1/10 의 값을 구하시오.

**정답**: `17/70`

**풀이**: 1/7 + 1/10 은 통분하면 (7+10)/(7·10) = 17/70 이다. 통분 없이 분자·분모를 각각 더해 2/(p+q)로 답하면 틀린다.

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

## 표본 82 · `wm-misc-eval-mc-2e589a597f59`

- 도메인: `FRACTION-ADD` · 발문형식: 객관식 · 정답형식: 분수 · 난이도: 3.3
- 성취기준: [9수01-05]

**문항**: 1/3 + 1/5 의 값을 구하시오.

**정답**: `8/15`

**풀이**: 1/3 + 1/5 은 통분하면 (3+5)/(3·5) = 8/15 이다. 통분 없이 분자·분모를 각각 더해 2/(p+q)로 답하면 틀린다.

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

## 표본 83 · `wm-misc-eval-mc-ab674164baa5`

- 도메인: `FRACTION-ADD` · 발문형식: 객관식 · 정답형식: 분수 · 난이도: 2.5
- 성취기준: [9수01-05]

**문항**: 1/2 + 1/9 의 값을 구하시오.

**정답**: `11/18`

**풀이**: 1/2 + 1/9 은 통분하면 (2+9)/(2·9) = 11/18 이다. 통분 없이 분자·분모를 각각 더해 2/(p+q)로 답하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = (2+9)/(2*9)` · answer_map: {x=11/18}

**선지**:
- ① `1/9` ← 정답
- ② `2/11` ← 오답 · 오개념 `fraction-addition-naive`
- ③ `1/2` ← 정답
- ④ `11/18` ← 정답

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

## 표본 84 · `wm-misc-eval-mc-085259703568`

- 도메인: `FRACTION-ADD` · 발문형식: 객관식 · 정답형식: 분수 · 난이도: 2.9
- 성취기준: [9수01-05]

**문항**: 1/4 + 1/11 의 값을 구하시오.

**정답**: `15/44`

**풀이**: 1/4 + 1/11 은 통분하면 (4+11)/(4·11) = 15/44 이다. 통분 없이 분자·분모를 각각 더해 2/(p+q)로 답하면 틀린다.

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

## 표본 85 · `wm-misc-eval-mc-d2588687b524`

- 도메인: `FRACTION-ADD` · 발문형식: 객관식 · 정답형식: 분수 · 난이도: 2.7
- 성취기준: [9수01-05]

**문항**: 1/3 + 1/10 의 값을 구하시오.

**정답**: `13/30`

**풀이**: 1/3 + 1/10 은 통분하면 (3+10)/(3·10) = 13/30 이다. 통분 없이 분자·분모를 각각 더해 2/(p+q)로 답하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = (3+10)/(3*10)` · answer_map: {x=13/30}

**선지**:
- ① `1/10` ← 정답
- ② `2/13` ← 오답 · 오개념 `fraction-addition-naive`
- ③ `1/3` ← 정답
- ④ `13/30` ← 정답

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

## 표본 86 · `wm-misc-eval-mc-217d769cdf39`

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

## 표본 87 · `wm-misc-eval-mc-be813a8db016`

- 도메인: `FRACTION-CANCEL` · 발문형식: 객관식 · 정답형식: 분수 · 난이도: 3.3
- 성취기준: [6수01-06], [9수01-04]

**문항**: 두 자연수 a = 4, b = 15 에 대하여 (a + b) / a 의 값을 구하시오.

**정답**: `19/4`

**풀이**: (a + b) / a = 1 + b/a 이므로 a = 4, b = 15 를 대입하면 19/4 이다. 분자와 분모의 a 를 지워 b 로 약분하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = (4+15)/4` · answer_map: {x=19/4}

**선지**:
- ① `4` ← 정답
- ② `19/4` ← 정답
- ③ `15` ← 오답 · 오개념 `fraction-cancellation`
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

## 표본 88 · `wm-misc-eval-mc-936aa3240209`

- 도메인: `FRACTION-CANCEL` · 발문형식: 객관식 · 정답형식: 분수 · 난이도: 3
- 성취기준: [6수01-06], [9수01-04]

**문항**: 두 자연수 a = 7, b = 9 에 대하여 (a + b) / a 의 값을 구하시오.

**정답**: `16/7`

**풀이**: (a + b) / a = 1 + b/a 이므로 a = 7, b = 9 를 대입하면 16/7 이다. 분자와 분모의 a 를 지워 b 로 약분하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = (7+9)/7` · answer_map: {x=16/7}

**선지**:
- ① `16/7` ← 정답
- ② `7` ← 정답
- ③ `9` ← 오답 · 오개념 `fraction-cancellation`
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

**풀이**: (a + b) / a = 1 + b/a 이므로 a = 4, b = 13 을 대입하면 17/4 이다. 분자와 분모의 a 를 지워 b 로 약분하면 틀린다.

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

## 표본 91 · `wm-misc-eval-mc-a153cd27da64`

- 도메인: `FUNC-COMPOSE` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.8
- 성취기준: [10공수2-03-02], [10기수2-03-02]

**문항**: 두 함수 f(x) = x + 3, g(x) = 5x 에 대하여 (f∘g)(6) 의 값을 구하시오.

**정답**: `33`

**풀이**: (f∘g)(6) = f(g(6)) = f(30) = 30 + 3 = 33 이다. 순서를 뒤집어 (g∘f)(6) = g(6+3) = 45 로 하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 5*6 + 3` · answer_map: {x=33}

**선지**:
- ① `30` ← 정답
- ② `33` ← 정답
- ③ `38` ← 정답
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

## 표본 92 · `wm-misc-eval-mc-77b7d2ad33aa`

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

## 표본 93 · `wm-misc-eval-mc-4c5b33911345`

- 도메인: `FUNC-COMPOSE` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.5
- 성취기준: [10공수2-03-02], [10기수2-03-02]

**문항**: 두 함수 f(x) = x + 2, g(x) = 3x 에 대하여 (f∘g)(6) 의 값을 구하시오.

**정답**: `20`

**풀이**: (f∘g)(6) = f(g(6)) = f(18) = 18 + 2 = 20 이다. 순서를 뒤집어 (g∘f)(6) = g(6+2) = 24 로 하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 3*6 + 2` · answer_map: {x=20}

**선지**:
- ① `18` ← 정답
- ② `20` ← 정답
- ③ `23` ← 정답
- ④ `24` ← 오답 · 오개념 `composite-function-commutes`

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

## 표본 94 · `wm-misc-eval-mc-2ffe87a9b836`

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

## 표본 95 · `wm-misc-eval-mc-dea4f43b2883`

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

## 표본 96 · `wm-misc-eval-mc-943ab4abbc5c`

- 도메인: `FUNC-TRANSLATE` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.4
- 성취기준: [10공수2-01-06], [10기수2-01-06]

**문항**: 함수 f(x) = x^2 + 4x 에 대하여 g(x) = f(x - 1) 일 때, g(6) 의 값을 구하시오.

**정답**: `45`

**풀이**: y = f(x-1) 은 그래프를 오른쪽으로 1 평행이동한 것이므로 g(6) = f(6-1) = f(5) = 45 이다. 부호를 뒤집어 f(6+1) 로 계산하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 5**2 + 4*5` · answer_map: {x=45}

**선지**:
- ① `25` ← 정답
- ② `45` ← 정답
- ③ `60` ← 정답
- ④ `77` ← 오답 · 오개념 `translation-sign-flip`

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

## 표본 97 · `wm-misc-eval-mc-c558d5f5bd9f`

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

## 표본 98 · `wm-misc-eval-mc-363d0807577d`

- 도메인: `FUNC-TRANSLATE` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3
- 성취기준: [10공수2-01-06], [10기수2-01-06]

**문항**: 함수 f(x) = x^2 + 4x 에 대하여 g(x) = f(x - 1) 일 때, g(2) 의 값을 구하시오.

**정답**: `5`

**풀이**: y = f(x-1) 은 그래프를 오른쪽으로 1 평행이동한 것이므로 g(2) = f(2-1) = f(1) = 5 이다. 부호를 뒤집어 f(2+1) 로 계산하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 1**2 + 4*1` · answer_map: {x=5}

**선지**:
- ① `1` ← 정답
- ② `5` ← 정답
- ③ `12` ← 정답
- ④ `21` ← 오답 · 오개념 `translation-sign-flip`

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

## 표본 99 · `wm-misc-eval-mc-7accb5eae986`

- 도메인: `FUNC-TRANSLATE` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.1
- 성취기준: [10공수2-01-06], [10기수2-01-06]

**문항**: 함수 f(x) = x^2 + 2x 에 대하여 g(x) = f(x - 1) 일 때, g(5) 의 값을 구하시오.

**정답**: `24`

**풀이**: y = f(x-1) 은 그래프를 오른쪽으로 1 평행이동한 것이므로 g(5) = f(5-1) = f(4) = 24 이다. 부호를 뒤집어 f(5+1) 로 계산하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 4**2 + 2*4` · answer_map: {x=24}

**선지**:
- ① `16` ← 정답
- ② `24` ← 정답
- ③ `35` ← 정답
- ④ `48` ← 오답 · 오개념 `translation-sign-flip`

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

## 표본 100 · `wm-misc-eval-mc-6df802aeea56`

- 도메인: `FUNC-TRANSLATE` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.8
- 성취기준: [10공수2-01-06], [10기수2-01-06]

**문항**: 함수 f(x) = x^2 + 2x 에 대하여 g(x) = f(x - 1) 일 때, g(2) 의 값을 구하시오.

**정답**: `3`

**풀이**: y = f(x-1) 은 그래프를 오른쪽으로 1 평행이동한 것이므로 g(2) = f(2-1) = f(1) = 3 이다. 부호를 뒤집어 f(2+1) 로 계산하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 1**2 + 2*1` · answer_map: {x=3}

**선지**:
- ① `1` ← 정답
- ② `3` ← 정답
- ③ `8` ← 정답
- ④ `15` ← 오답 · 오개념 `translation-sign-flip`

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

## 표본 101 · `wm-misc-eval-mc-0bdddd045ac0`

- 도메인: `GCD-LCM` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.6
- 성취기준: [9수01-02]

**문항**: 10 과 13 의 최소공배수를 구하시오.

**정답**: `130`

**풀이**: 10과 13의 최소공배수는 130 이다(최대공약수는 1). 최소공배수와 최대공약수를 혼동하면 틀린다.

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

## 표본 102 · `wm-misc-eval-mc-d97f00cba2a3`

- 도메인: `GCD-LCM` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.2
- 성취기준: [9수01-02]

**문항**: 10 과 19 의 최소공배수를 구하시오.

**정답**: `190`

**풀이**: 10과 19의 최소공배수는 190 이다(최대공약수는 1). 최소공배수와 최대공약수를 혼동하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 190` · answer_map: {x=190}

**선지**:
- ① `1` ← 오답 · 오개념 `gcd-lcm-confused`
- ② `10` ← 정답
- ③ `19` ← 정답
- ④ `190` ← 정답

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

## 표본 103 · `wm-misc-eval-mc-cfbab8dd7491`

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

## 표본 104 · `wm-misc-eval-mc-7a20cdda6ae1`

- 도메인: `GCD-LCM` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.8
- 성취기준: [9수01-02]

**문항**: 6 과 19 의 최소공배수를 구하시오.

**정답**: `114`

**풀이**: 6과 19의 최소공배수는 114 이다(최대공약수는 1). 최소공배수와 최대공약수를 혼동하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 114` · answer_map: {x=114}

**선지**:
- ① `1` ← 오답 · 오개념 `gcd-lcm-confused`
- ② `6` ← 정답
- ③ `19` ← 정답
- ④ `114` ← 정답

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

## 표본 105 · `wm-misc-eval-mc-0881209515ab`

- 도메인: `LOG-DIST` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.4
- 성취기준: [12대수01-04], [12대수01-05]

**문항**: log_2(2^9 + 2^9) 의 값을 구하시오.

**정답**: `10`

**풀이**: 2^9 + 2^9 = 2·2^9 = 2^10 이므로 값은 10 이다. 로그를 합에 분배해 9+9 = 18 로 하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = log(2**9 + 2**9, 2)` · answer_map: {x=10}

**선지**:
- ① `9` ← 정답
- ② `10` ← 정답
- ③ `18` ← 오답 · 오개념 `log-distribution`
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

## 표본 106 · `wm-misc-eval-mc-0b034bc5981b`

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

## 표본 107 · `wm-misc-eval-mc-b077c9d812f3`

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

## 표본 110 · `wm-misc-eval-mc-38cb20eb59b5`

- 도메인: `MIDPOINT-NO-HALF` · 발문형식: 객관식 · 정답형식: 분수 · 난이도: 2.6
- 성취기준: [9수02-05]

**문항**: 수직선 위 두 점 4, 19 의 중점의 좌표를 구하시오.

**정답**: `23/2`

**풀이**: 두 점의 중점은 좌표의 평균이므로 (4+19)/2 = 23/2 이다. 2로 나누지 않고 23으로 답하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = (4+19)/2` · answer_map: {x=23/2}

**선지**:
- ① `4` ← 정답
- ② `23/2` ← 정답
- ③ `19` ← 정답
- ④ `23` ← 오답 · 오개념 `midpoint-sum-only`

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

## 표본 111 · `wm-misc-eval-mc-4ffa56ee7996`

- 도메인: `MIDPOINT-NO-HALF` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.1
- 성취기준: [9수02-05]

**문항**: 수직선 위 두 점 1, 5 의 중점의 좌표를 구하시오.

**정답**: `3`

**풀이**: 두 점의 중점은 좌표의 평균이므로 (1+5)/2 = 3 이다. 2로 나누지 않고 6으로 답하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = (1+5)/2` · answer_map: {x=3}

**선지**:
- ① `1` ← 정답
- ② `3` ← 정답
- ③ `5` ← 정답
- ④ `6` ← 오답 · 오개념 `midpoint-sum-only`

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

## 표본 112 · `wm-misc-eval-mc-e06604beeb25`

- 도메인: `MIDPOINT-NO-HALF` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.4
- 성취기준: [9수02-05]

**문항**: 수직선 위 두 점 1, 19 의 중점의 좌표를 구하시오.

**정답**: `10`

**풀이**: 두 점의 중점은 좌표의 평균이므로 (1+19)/2 = 10 이다. 2로 나누지 않고 20으로 답하면 틀린다.

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

## 표본 113 · `wm-misc-eval-mc-a3128f01dc4c`

- 도메인: `MIXED-MULT` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3
- 성취기준: [9수01-05]

**문항**: 8과 1/2 (대분수)에 8 을 곱한 값을 구하시오.

**정답**: `68`

**풀이**: 대분수 8½ = 17/2 에 8을 곱하면 136/2 = 68 이다. 정수부만 곱해 64½로 답하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = (17*8)/2` · answer_map: {x=68}

**선지**:
- ① `17/2` ← 정답
- ② `64` ← 정답
- ③ `129/2` ← 오답 · 오개념 `mixed-number-mult-whole`
- ④ `68` ← 정답

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

## 표본 114 · `wm-misc-eval-mc-cdb4b04bf321`

- 도메인: `MIXED-MULT` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.6
- 성취기준: [9수01-05]

**문항**: 6과 1/2 (대분수)에 6 을 곱한 값을 구하시오.

**정답**: `39`

**풀이**: 대분수 6½ = 13/2 에 6을 곱하면 78/2 = 39 이다. 정수부만 곱해 36½로 답하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = (13*6)/2` · answer_map: {x=39}

**선지**:
- ① `13/2` ← 정답
- ② `36` ← 정답
- ③ `73/2` ← 오답 · 오개념 `mixed-number-mult-whole`
- ④ `39` ← 정답

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

## 표본 115 · `wm-misc-eval-mc-be6cc3aa614f`

- 도메인: `MIXED-MULT` · 발문형식: 객관식 · 정답형식: 분수 · 난이도: 2.8
- 성취기준: [9수01-05]

**문항**: 5와 1/2 (대분수)에 9 를 곱한 값을 구하시오.

**정답**: `99/2`

**풀이**: 대분수 5½ = 11/2 에 9를 곱하면 99/2 = 99/2 이다. 정수부만 곱해 45½로 답하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = (11*9)/2` · answer_map: {x=99/2}

**선지**:
- ① `11/2` ← 정답
- ② `45` ← 정답
- ③ `91/2` ← 오답 · 오개념 `mixed-number-mult-whole`
- ④ `99/2` ← 정답

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

## 표본 116 · `wm-misc-eval-mc-5ba76012faf5`

- 도메인: `MIXED-MULT` · 발문형식: 객관식 · 정답형식: 분수 · 난이도: 3.5
- 성취기준: [9수01-05]

**문항**: 5와 1/2 (대분수)에 5 를 곱한 값을 구하시오.

**정답**: `55/2`

**풀이**: 대분수 5½ = 11/2 에 5를 곱하면 55/2 = 55/2 이다. 정수부만 곱해 25½로 답하면 틀린다.

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

## 표본 117 · `wm-misc-eval-mc-8c0d4b4d6e16`

- 도메인: `NEG-DISTRIBUTE` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.5
- 성취기준: [9수02-10]

**문항**: -(x - 8) 에서 x = 2 일 때의 값을 구하시오.

**정답**: `6`

**풀이**: 음의 부호 분배는 -(x - 8) = -x + 8 이므로 x = 2 를 대입하면 6 이다. 뒷항 부호를 반전하지 않고 -2 - 8로 계산하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 8 - 2` · answer_map: {x=6}

**선지**:
- ① `-10` ← 오답 · 오개념 `negative-distribute-sign`
- ② `-6` ← 정답
- ③ `6` ← 정답
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

## 표본 118 · `wm-misc-eval-mc-0f8c59a5d63d`

- 도메인: `NEG-DISTRIBUTE` · 발문형식: 객관식 · 정답형식: 분수 · 난이도: 3.2
- 성취기준: [9수02-10]

**문항**: -(x - 2) 에서 x = 5 일 때의 값을 구하시오.

**정답**: `-3`

**풀이**: 음의 부호 분배는 -(x - 2) = -x + 2 이므로 x = 5 를 대입하면 -3 이다. 뒷항 부호를 반전하지 않고 -5 - 2로 계산하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 2 - 5` · answer_map: {x=-3}

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

## 표본 119 · `wm-misc-eval-mc-44aac49232e5`

- 도메인: `NEG-DISTRIBUTE` · 발문형식: 객관식 · 정답형식: 분수 · 난이도: 2.6
- 성취기준: [9수02-10]

**문항**: -(x - 2) 에서 x = 10 일 때의 값을 구하시오.

**정답**: `-8`

**풀이**: 음의 부호 분배는 -(x - 2) = -x + 2 이므로 x = 10 을 대입하면 -8 이다. 뒷항 부호를 반전하지 않고 -10 - 2로 계산하면 틀린다.

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

## 표본 120 · `wm-misc-eval-mc-8bbd58829b86`

- 도메인: `NEG-DISTRIBUTE` · 발문형식: 객관식 · 정답형식: 분수 · 난이도: 2.9
- 성취기준: [9수02-10]

**문항**: -(x - 2) 에서 x = 13 일 때의 값을 구하시오.

**정답**: `-11`

**풀이**: 음의 부호 분배는 -(x - 2) = -x + 2 이므로 x = 13 을 대입하면 -11 이다. 뒷항 부호를 반전하지 않고 -13 - 2로 계산하면 틀린다.

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

## 표본 121 · `wm-misc-eval-mc-03d97daec04c`

- 도메인: `NEG-EVEN-POWER` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.6
- 성취기준: [9수02-08]

**문항**: (-21)^2 의 값을 구하시오.

**정답**: `441`

**풀이**: 음수의 짝수 거듭제곱은 양수이므로 (-21)^2 = 21^2 = 441 이다. 음수로 여겨 -441로 답하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 21**2` · answer_map: {x=441}

**선지**:
- ① `-441` ← 오답 · 오개념 `negative-even-power-sign`
- ② `-21` ← 정답
- ③ `21` ← 정답
- ④ `441` ← 정답

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

## 표본 122 · `wm-misc-eval-mc-17315f13fd96`

- 도메인: `NEG-EVEN-POWER` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.2
- 성취기준: [9수02-08]

**문항**: (-14)^4 의 값을 구하시오.

**정답**: `38416`

**풀이**: 음수의 짝수 거듭제곱은 양수이므로 (-14)^4 = 14^4 = 38416 이다. 음수로 여겨 -38416으로 답하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 14**4` · answer_map: {x=38416}

**선지**:
- ① `-38416` ← 오답 · 오개념 `negative-even-power-sign`
- ② `-14` ← 정답
- ③ `14` ← 정답
- ④ `38416` ← 정답

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

## 표본 123 · `wm-misc-eval-mc-fd1bcb5e9d6b`

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

## 표본 125 · `wm-misc-eval-mc-effa1c08bf01`

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

## 표본 126 · `wm-misc-eval-mc-6061b1110645`

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

## 표본 127 · `wm-misc-eval-mc-7718026ecb8a`

- 도메인: `NEG-PRODUCT` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.7
- 성취기준: [9수01-03]

**문항**: (-3) × (-10) 의 값을 구하시오.

**정답**: `30`

**풀이**: 음수끼리의 곱은 양수이므로 (-3)×(-10) = 30 이다. 음수끼리 곱해도 음수라고 여기면 부호를 틀린다.

**verify(SymPy 입력)**: conditions: `x = (3)*(10)` · answer_map: {x=30}

**선지**:
- ① `-30` ← 오답 · 오개념 `negative-times-negative`
- ② `-13` ← 정답
- ③ `13` ← 정답
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

## 표본 128 · `wm-misc-eval-mc-13bdc20fec77`

- 도메인: `NEG-PRODUCT` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.9
- 성취기준: [9수01-03]

**문항**: (-4) × (-11) 의 값을 구하시오.

**정답**: `44`

**풀이**: 음수끼리의 곱은 양수이므로 (-4)×(-11) = 44 이다. 음수끼리 곱해도 음수라고 여기면 부호를 틀린다.

**verify(SymPy 입력)**: conditions: `x = (4)*(11)` · answer_map: {x=44}

**선지**:
- ① `-44` ← 오답 · 오개념 `negative-times-negative`
- ② `-15` ← 정답
- ③ `15` ← 정답
- ④ `44` ← 정답

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

## 표본 130 · `wm-misc-eval-mc-2cb0180b61a7`

- 도메인: `NEG-SQUARE` · 발문형식: 객관식 · 정답형식: 분수 · 난이도: 3.2
- 성취기준: [9수02-08]

**문항**: -5² + 2 의 값을 구하시오.

**정답**: `-23`

**풀이**: 거듭제곱이 부호보다 우선하므로 -5² = -25 이고 -5² + 2 = -23 이다. -5²을 (-5)²=25로 계산하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 2 - 25` · answer_map: {x=-23}

**선지**:
- ① `-27` ← 정답
- ② `-23` ← 정답
- ③ `23` ← 정답
- ④ `27` ← 오답 · 오개념 `negative-square-precedence`

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

## 표본 131 · `wm-misc-eval-mc-b5c52326102a`

- 도메인: `NEG-SQUARE` · 발문형식: 객관식 · 정답형식: 분수 · 난이도: 2.9
- 성취기준: [9수02-08]

**문항**: -3² + 1 의 값을 구하시오.

**정답**: `-8`

**풀이**: 거듭제곱이 부호보다 우선하므로 -3² = -9 이고 -3² + 1 = -8 이다. -3²을 (-3)²=9로 계산하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 1 - 9` · answer_map: {x=-8}

**선지**:
- ① `-10` ← 정답
- ② `-8` ← 정답
- ③ `8` ← 정답
- ④ `10` ← 오답 · 오개념 `negative-square-precedence`

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

## 표본 132 · `wm-misc-eval-mc-6935f07c10e6`

- 도메인: `NEG-SQUARE` · 발문형식: 객관식 · 정답형식: 분수 · 난이도: 2.6
- 성취기준: [9수02-08]

**문항**: -8² + 4 의 값을 구하시오.

**정답**: `-60`

**풀이**: 거듭제곱이 부호보다 우선하므로 -8² = -64 이고 -8² + 4 = -60 이다. -8²을 (-8)²=64로 계산하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 4 - 64` · answer_map: {x=-60}

**선지**:
- ① `-68` ← 정답
- ② `-60` ← 정답
- ③ `60` ← 정답
- ④ `68` ← 오답 · 오개념 `negative-square-precedence`

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

**풀이**: (a+b)^2 = a^2 + 2ab + b^2 이므로 a = 2, b = 5 를 대입하면 (a+b)^2 = 49 이다. 교차항 2ab 를 빠뜨리면 a^2+b^2 이 되어 틀린다.

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

## 표본 134 · `wm-misc-eval-mc-c7deedea9e69`

- 도메인: `POLY-PRODUCT` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.6
- 성취기준: [9수02-19]

**문항**: 두 수 a, b에 대하여 a = 2, b = 21 일 때, (a+b)^2 의 값을 구하시오.

**정답**: `529`

**풀이**: (a+b)^2 = a^2 + 2ab + b^2 이므로 a = 2, b = 21 을 대입하면 (a+b)^2 = 529 이다. 교차항 2ab 를 빠뜨리면 a^2+b^2 이 되어 틀린다.

**verify(SymPy 입력)**: conditions: `x = (2+21)**2` · answer_map: {x=529}

**선지**:
- ① `84` ← 정답
- ② `445` ← 오답 · 오개념 `distribution-over-power` (op: `power-distributed-no-cross-term`)
- ③ `487` ← 정답
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

## 표본 135 · `wm-misc-eval-mc-666755947fdf`

- 도메인: `POLY-PRODUCT` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.4
- 성취기준: [9수02-19]

**문항**: 두 수 a, b에 대하여 a = 2, b = 7 일 때, (a+b)^2 의 값을 구하시오.

**정답**: `81`

**풀이**: (a+b)^2 = a^2 + 2ab + b^2 이므로 a = 2, b = 7 을 대입하면 (a+b)^2 = 81 이다. 교차항 2ab 를 빠뜨리면 a^2+b^2 이 되어 틀린다.

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

## 표본 136 · `wm-misc-eval-mc-95a2eaa7b769`

- 도메인: `POLY-PRODUCT` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.9
- 성취기준: [9수02-19]

**문항**: 두 수 a, b에 대하여 a = 2, b = 13 일 때, (a+b)^2 의 값을 구하시오.

**정답**: `225`

**풀이**: (a+b)^2 = a^2 + 2ab + b^2 이므로 a = 2, b = 13 을 대입하면 (a+b)^2 = 225 이다. 교차항 2ab 를 빠뜨리면 a^2+b^2 이 되어 틀린다.

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

## 표본 137 · `wm-misc-eval-mc-f8e42084620e`

- 도메인: `POLYGON-ANGLE-SUM` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.4
- 성취기준: [4수03-25], [9수03-05]

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

## 표본 138 · `wm-misc-eval-mc-687361435557`

- 도메인: `POLYGON-ANGLE-SUM` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.1
- 성취기준: [4수03-25], [9수03-05]

**문항**: 6각형의 내각의 크기의 합을 구하시오. (단위: 도)

**정답**: `720`

**풀이**: n각형의 내각의 합은 (n - 2)·180° 이므로 6각형은 (6 - 2)·180 = 720° 이다. 모든 다각형의 내각의 합을 180° 로 여기면 틀린다.

**verify(SymPy 입력)**: conditions: `x = (6-2)*180` · answer_map: {x=720}

**선지**:
- ① `180` ← 오답 · 오개념 `angle-sum-non-triangle`
- ② `720` ← 정답
- ③ `900` ← 정답
- ④ `1080` ← 정답

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

## 표본 139 · `wm-misc-eval-mc-6511e3e6c8e0`

- 도메인: `POLYGON-ANGLE-SUM` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.9
- 성취기준: [4수03-25], [9수03-05]

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

## 표본 140 · `wm-misc-eval-mc-c890be28118a`

- 도메인: `POLYGON-ANGLE-SUM` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.6
- 성취기준: [4수03-25], [9수03-05]

**문항**: 12각형의 내각의 크기의 합을 구하시오. (단위: 도)

**정답**: `1800`

**풀이**: n각형의 내각의 합은 (n - 2)·180° 이므로 12각형은 (12 - 2)·180 = 1800° 이다. 모든 다각형의 내각의 합을 180° 로 여기면 틀린다.

**verify(SymPy 입력)**: conditions: `x = (12-2)*180` · answer_map: {x=1800}

**선지**:
- ① `180` ← 오답 · 오개념 `angle-sum-non-triangle`
- ② `1800` ← 정답
- ③ `1980` ← 정답
- ④ `2160` ← 정답

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

## 표본 141 · `wm-misc-eval-mc-9500539bae1b`

- 도메인: `POWER-OF-POWER` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.5
- 성취기준: [9수02-08]

**문항**: (3^2)^5 의 값을 구하시오.

**정답**: `59049`

**풀이**: 거듭제곱의 거듭제곱은 지수를 곱하므로 (3^2)^5 = 3^10 = 59049 이다. 지수를 더해 3^7 으로 답하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 3**10` · answer_map: {x=59049}

**선지**:
- ① `9` ← 정답
- ② `243` ← 정답
- ③ `2187` ← 오답 · 오개념 `power-of-power-adds`
- ④ `59049` ← 정답

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

## 표본 142 · `wm-misc-eval-mc-b1c78c0e7ae6`

- 도메인: `POWER-OF-POWER` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.5
- 성취기준: [9수02-08]

**문항**: (5^2)^4 의 값을 구하시오.

**정답**: `390625`

**풀이**: 거듭제곱의 거듭제곱은 지수를 곱하므로 (5^2)^4 = 5^8 = 390625 이다. 지수를 더해 5^6 으로 답하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 5**8` · answer_map: {x=390625}

**선지**:
- ① `25` ← 정답
- ② `625` ← 정답
- ③ `15625` ← 오답 · 오개념 `power-of-power-adds`
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

## 표본 143 · `wm-misc-eval-mc-65c18b0721da`

- 도메인: `POWER-OF-POWER` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.6
- 성취기준: [9수02-08]

**문항**: (7^2)^3 의 값을 구하시오.

**정답**: `117649`

**풀이**: 거듭제곱의 거듭제곱은 지수를 곱하므로 (7^2)^3 = 7^6 = 117649 이다. 지수를 더해 7^5 으로 답하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 7**6` · answer_map: {x=117649}

**선지**:
- ① `49` ← 정답
- ② `343` ← 정답
- ③ `16807` ← 오답 · 오개념 `power-of-power-adds`
- ④ `117649` ← 정답

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

## 표본 144 · `wm-misc-eval-mc-24728c1fba65`

- 도메인: `POWER-OF-POWER` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.9
- 성취기준: [9수02-08]

**문항**: (10^2)^3 의 값을 구하시오.

**정답**: `1000000`

**풀이**: 거듭제곱의 거듭제곱은 지수를 곱하므로 (10^2)^3 = 10^6 = 1000000 이다. 지수를 더해 10^5 으로 답하면 틀린다.

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

## 표본 146 · `wm-misc-eval-mc-906a285a6f9b`

- 도메인: `PROB-INDEPENDENT-TRIAL` · 발문형식: 객관식 · 정답형식: 분수 · 난이도: 2.5
- 성취기준: [12수문02-02], [12인수04-01], [12확통02-01]

**문항**: 앞면이 나올 확률이 2/9 인 동전을 던져 앞면이 3번 연속 나왔다. 다음 시행에서 앞면이 나올 확률을 구하시오.

**정답**: `2/9`

**풀이**: 각 시행은 독립이라 이전 결과와 무관하게 다음 앞면 확률은 2/9 그대로다. 연속으로 나왔으니 이제 덜 나온다고 여기는 도박사 오류에 빠지면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 2/9` · answer_map: {x=2/9}

**선지**:
- ① `4/81` ← 오답 · 오개념 `gambler-fallacy`
- ② `1/9` ← 정답
- ③ `2/9` ← 정답
- ④ `7/9` ← 정답

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

## 표본 147 · `wm-misc-eval-mc-9dd33d00f1dc`

- 도메인: `PROB-INDEPENDENT-TRIAL` · 발문형식: 객관식 · 정답형식: 분수 · 난이도: 3.4
- 성취기준: [12수문02-02], [12인수04-01], [12확통02-01]

**문항**: 앞면이 나올 확률이 9/11 인 동전을 던져 앞면이 3번 연속 나왔다. 다음 시행에서 앞면이 나올 확률을 구하시오.

**정답**: `9/11`

**풀이**: 각 시행은 독립이라 이전 결과와 무관하게 다음 앞면 확률은 9/11 그대로다. 연속으로 나왔으니 이제 덜 나온다고 여기는 도박사 오류에 빠지면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 9/11` · answer_map: {x=9/11}

**선지**:
- ① `2/11` ← 정답
- ② `9/22` ← 정답
- ③ `81/121` ← 오답 · 오개념 `gambler-fallacy`
- ④ `9/11` ← 정답

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

## 표본 149 · `wm-misc-eval-mc-3482be939a80`

- 도메인: `REMAINDER-THEOREM` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.9
- 성취기준: [10공수1-01-02]

**문항**: 다항식 x² + 2x + 7 을 (x - 6)으로 나눈 나머지를 구하시오.

**정답**: `55`

**풀이**: 나머지정리로 f(6) = 6² + 2·6 + 7 = 55 이다. 부호를 반대로 f(-6)으로 대입하면 틀린다.

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

## 표본 150 · `wm-misc-eval-mc-1ca11f1b23ad`

- 도메인: `REMAINDER-THEOREM` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.7
- 성취기준: [10공수1-01-02]

**문항**: 다항식 x² + 4x + 7 을 (x - 2)로 나눈 나머지를 구하시오.

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

## 표본 151 · `wm-misc-eval-mc-595258110358`

- 도메인: `REMAINDER-THEOREM` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.1
- 성취기준: [10공수1-01-02]

**문항**: 다항식 x² + 7x + 6 을 (x - 4)로 나눈 나머지를 구하시오.

**정답**: `50`

**풀이**: 나머지정리로 f(4) = 4² + 7·4 + 6 = 50 이다. 부호를 반대로 f(-4)로 대입하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 4**2 + 4*7 + 6` · answer_map: {x=50}

**선지**:
- ① `-6` ← 오답 · 오개념 `remainder-theorem-sign`
- ② `6` ← 정답
- ③ `22` ← 정답
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

## 표본 152 · `wm-misc-eval-mc-6d0b85f1a91b`

- 도메인: `REMAINDER-THEOREM` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.2
- 성취기준: [10공수1-01-02]

**문항**: 다항식 x² + 6x + 7 을 (x - 5)로 나눈 나머지를 구하시오.

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

## 표본 153 · `wm-misc-eval-mc-5c7b8b26c6c6`

- 도메인: `SAME-ITEM-PERM` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.1
- 성취기준: [12직수04-01], [12확통01-01]

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

## 표본 154 · `wm-misc-eval-mc-e33f1be7e048`

- 도메인: `SAME-ITEM-PERM` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.8
- 성취기준: [12직수04-01], [12확통01-01]

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

## 표본 155 · `wm-misc-eval-mc-33332ae99290`

- 도메인: `SAME-ITEM-PERM` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.6
- 성취기준: [12직수04-01], [12확통01-01]

**문항**: 4 개의 A 와 8 개의 B, 모두 12 개의 문자를 일렬로 배열하는 경우의 수를 구하시오.

**정답**: `495`

**풀이**: 같은 것이 있는 순열이므로 12! 을 각 문자 개수의 계승 4!·8! 로 나눈다: 12!/(4!×8!) = 495 이다. 중복을 나누지 않고 12! 로 두면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 495` · answer_map: {x=495}

**선지**:
- ① `495` ← 정답
- ② `11880` ← 정답
- ③ `19958400` ← 정답
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

## 표본 156 · `wm-misc-eval-mc-c77578d50153`

- 도메인: `SAME-ITEM-PERM` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.4
- 성취기준: [12직수04-01], [12확통01-01]

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

## 표본 157 · `wm-misc-eval-mc-05ed1a5eab8a`

- 도메인: `SCALE-AREA` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.9
- 성취기준: [9수02-07], [9수03-12]

**문항**: 닮음비가 26 인 두 도형의 넓이의 비를 구하시오.

**정답**: `676`

**풀이**: 넓이는 길이의 제곱에 비례하므로 닮음비 26 의 넓이의 비는 26² = 676 이다. 닮음비 26 을 그대로 넓이의 비로 답하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 26**2` · answer_map: {x=676}

**선지**:
- ① `26` ← 오답 · 오개념 `scale-area-linear`
- ② `52` ← 정답
- ③ `676` ← 정답
- ④ `17576` ← 정답

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

## 표본 158 · `wm-misc-eval-mc-4f27b24fb777`

- 도메인: `SCALE-AREA` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.1
- 성취기준: [9수02-07], [9수03-12]

**문항**: 닮음비가 6 인 두 도형의 넓이의 비를 구하시오.

**정답**: `36`

**풀이**: 넓이는 길이의 제곱에 비례하므로 닮음비 6 의 넓이의 비는 6² = 36 이다. 닮음비 6 을 그대로 넓이의 비로 답하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 6**2` · answer_map: {x=36}

**선지**:
- ① `6` ← 오답 · 오개념 `scale-area-linear`
- ② `12` ← 정답
- ③ `36` ← 정답
- ④ `216` ← 정답

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

## 표본 159 · `wm-misc-eval-mc-0bc5ad349961`

- 도메인: `SCALE-AREA` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.6
- 성취기준: [9수02-07], [9수03-12]

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

## 표본 160 · `wm-misc-eval-mc-34f717fdd396`

- 도메인: `SCALE-AREA` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.4
- 성취기준: [9수02-07], [9수03-12]

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

## 표본 161 · `wm-misc-eval-mc-1169f75bf250`

- 도메인: `SCALE-VOLUME` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.1
- 성취기준: [9수03-12]

**문항**: 닮음비가 1:17 인 두 입체도형의 부피비는 1:? 이다. ? 의 값을 구하시오.

**정답**: `4913`

**풀이**: 닮음비가 1:17 이면 부피비는 1:17³ = 1:4913 이다. 부피비를 닮음비와 같은 17 로 두면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 17**3` · answer_map: {x=4913}

**선지**:
- ① `17` ← 오답 · 오개념 `scale-volume-linear`
- ② `51` ← 정답
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

## 표본 162 · `wm-misc-eval-mc-d10b5f798117`

- 도메인: `SCALE-VOLUME` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.9
- 성취기준: [9수03-12]

**문항**: 닮음비가 1:4 인 두 입체도형의 부피비는 1:? 이다. ? 의 값을 구하시오.

**정답**: `64`

**풀이**: 닮음비가 1:4 이면 부피비는 1:4³ = 1:64 이다. 부피비를 닮음비와 같은 4 로 두면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 4**3` · answer_map: {x=64}

**선지**:
- ① `4` ← 오답 · 오개념 `scale-volume-linear`
- ② `12` ← 정답
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

## 표본 163 · `wm-misc-eval-mc-a0e5bf7862c8`

- 도메인: `SCALE-VOLUME` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.4
- 성취기준: [9수03-12]

**문항**: 닮음비가 1:9 인 두 입체도형의 부피비는 1:? 이다. ? 의 값을 구하시오.

**정답**: `729`

**풀이**: 닮음비가 1:9 이면 부피비는 1:9³ = 1:729 이다. 부피비를 닮음비와 같은 9 로 두면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 9**3` · answer_map: {x=729}

**선지**:
- ① `9` ← 오답 · 오개념 `scale-volume-linear`
- ② `27` ← 정답
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

## 표본 164 · `wm-misc-eval-mc-12fef8dcdee5`

- 도메인: `SCALE-VOLUME` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.6
- 성취기준: [9수03-12]

**문항**: 닮음비가 1:12 인 두 입체도형의 부피비는 1:? 이다. ? 의 값을 구하시오.

**정답**: `1728`

**풀이**: 닮음비가 1:12 이면 부피비는 1:12³ = 1:1728 이다. 부피비를 닮음비와 같은 12 로 두면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 12**3` · answer_map: {x=1728}

**선지**:
- ① `12` ← 오답 · 오개념 `scale-volume-linear`
- ② `36` ← 정답
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

## 표본 166 · `wm-misc-eval-mc-365a64dd2660`

- 도메인: `SQRT-POS` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.4
- 성취기준: [12대수01-01], [9수01-07]

**문항**: √((-9)^2) 의 값을 구하시오.

**정답**: `9`

**풀이**: √(x²) = |x| 이므로 √((-9)²) = |-9| = 9 이다. √(x²) = x 로 오인하면 -9 가 되어 틀린다.

**verify(SymPy 입력)**: conditions: `x = sqrt((-9)**2)` · answer_map: {x=9}

**선지**:
- ① `-9` ← 오답 · 오개념 `square-root-positivity`
- ② `9` ← 정답
- ③ `18` ← 정답
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

## 표본 167 · `wm-misc-eval-mc-d17a4f49d401`

- 도메인: `SQRT-POS` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.1
- 성취기준: [12대수01-01], [9수01-07]

**문항**: √((-28)^2) 의 값을 구하시오.

**정답**: `28`

**풀이**: √(x²) = |x| 이므로 √((-28)²) = |-28| = 28 이다. √(x²) = x 로 오인하면 -28 이 되어 틀린다.

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

## 표본 169 · `wm-misc-eval-mc-c1e9216de6d9`

- 도메인: `SQRT-SUM` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.7
- 성취기준: [9수01-07]

**문항**: √(2304 + 4096) 의 값을 구하시오.

**정답**: `80`

**풀이**: 근호 안의 합 6400 은 80 의 제곱이므로 그 제곱근은 80 이다. 제곱근을 각 항에 분배하면 48 + 64 가 되어 틀린다.

**verify(SymPy 입력)**: conditions: `x = 80` · answer_map: {x=80}

**선지**:
- ① `16` ← 정답
- ② `64` ← 정답
- ③ `80` ← 정답
- ④ `112` ← 오답 · 오개념 `sqrt-distributes-over-sum`

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

## 표본 170 · `wm-misc-eval-mc-f17c74af1544`

- 도메인: `SQRT-SUM` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.3
- 성취기준: [9수01-07]

**문항**: √(400 + 441) 의 값을 구하시오.

**정답**: `29`

**풀이**: 근호 안의 합 841 은 29 의 제곱이므로 그 제곱근은 29 이다. 제곱근을 각 항에 분배하면 20 + 21 이 되어 틀린다.

**verify(SymPy 입력)**: conditions: `x = 29` · answer_map: {x=29}

**선지**:
- ① `1` ← 정답
- ② `21` ← 정답
- ③ `29` ← 정답
- ④ `41` ← 오답 · 오개념 `sqrt-distributes-over-sum`

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

## 표본 171 · `wm-misc-eval-mc-d80812504fe6`

- 도메인: `SQRT-SUM` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.5
- 성취기준: [9수01-07]

**문항**: √(6400 + 7056) 의 값을 구하시오.

**정답**: `116`

**풀이**: 근호 안의 합 13456 은 116 의 제곱이므로 그 제곱근은 116 이다. 제곱근을 각 항에 분배하면 80 + 84 가 되어 틀린다.

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

## 표본 172 · `wm-misc-eval-mc-c596b689574a`

- 도메인: `SQRT-SUM` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3
- 성취기준: [9수01-07]

**문항**: √(81 + 1600) 의 값을 구하시오.

**정답**: `41`

**풀이**: 근호 안의 합 1681 은 41 의 제곱이므로 그 제곱근은 41 이다. 제곱근을 각 항에 분배하면 9 + 40 이 되어 틀린다.

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

## 표본 173 · `wm-misc-eval-mc-2fa98e7b2fbf`

- 도메인: `SQUARE-DIFF` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.1
- 성취기준: [9수02-19]

**문항**: (15 - 2)² 의 값을 구하시오.

**정답**: `169`

**풀이**: 차의 제곱은 (15 - 2)² = 15² - 2·15·2 + 2² = 169 이다. 교차항을 누락해 15² - 2²으로 계산하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = (15 - 2)**2` · answer_map: {x=169}

**선지**:
- ① `169` ← 정답
- ② `221` ← 오답 · 오개념 `square-of-difference-no-cross`
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

## 표본 174 · `wm-misc-eval-mc-d1b5c2fd6967`

- 도메인: `SQUARE-DIFF` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.4
- 성취기준: [9수02-19]

**문항**: (7 - 2)² 의 값을 구하시오.

**정답**: `25`

**풀이**: 차의 제곱은 (7 - 2)² = 7² - 2·7·2 + 2² = 25 이다. 교차항을 누락해 7² - 2²으로 계산하면 틀린다.

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

## 표본 175 · `wm-misc-eval-mc-20102a8293f3`

- 도메인: `SQUARE-DIFF` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.6
- 성취기준: [9수02-19]

**문항**: (10 - 2)² 의 값을 구하시오.

**정답**: `64`

**풀이**: 차의 제곱은 (10 - 2)² = 10² - 2·10·2 + 2² = 64 이다. 교차항을 누락해 10² - 2²으로 계산하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = (10 - 2)**2` · answer_map: {x=64}

**선지**:
- ① `64` ← 정답
- ② `96` ← 오답 · 오개념 `square-of-difference-no-cross`
- ③ `104` ← 정답
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

## 표본 176 · `wm-misc-eval-mc-467cf759cb91`

- 도메인: `SQUARE-DIFF` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.9
- 성취기준: [9수02-19]

**문항**: (24 - 2)² 의 값을 구하시오.

**정답**: `484`

**풀이**: 차의 제곱은 (24 - 2)² = 24² - 2·24·2 + 2² = 484 이다. 교차항을 누락해 24² - 2²으로 계산하면 틀린다.

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

## 표본 177 · `wm-misc-eval-mc-131940825cee`

- 도메인: `SUBTRACT-NEG` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.2
- 성취기준: [9수01-03]

**문항**: 2 - (-5) 의 값을 구하시오.

**정답**: `7`

**풀이**: 음수를 빼면 그만큼 더해지므로 2 - (-5) = 2 + 5 = 7 이다. 부호 반전을 놓쳐 a - b로 계산하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 2+5` · answer_map: {x=7}

**선지**:
- ① `-7` ← 정답
- ② `-3` ← 오답 · 오개념 `subtract-negative-sign`
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

## 표본 178 · `wm-misc-eval-mc-18c1c5ea1579`

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

## 표본 179 · `wm-misc-eval-mc-c699f5fac50b`

- 도메인: `SUBTRACT-NEG` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.6
- 성취기준: [9수01-03]

**문항**: 2 - (-21) 의 값을 구하시오.

**정답**: `23`

**풀이**: 음수를 빼면 그만큼 더해지므로 2 - (-21) = 2 + 21 = 23 이다. 부호 반전을 놓쳐 a - b로 계산하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 2+21` · answer_map: {x=23}

**선지**:
- ① `-23` ← 정답
- ② `-19` ← 오답 · 오개념 `subtract-negative-sign`
- ③ `19` ← 정답
- ④ `23` ← 정답

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

## 표본 181 · `wm-misc-eval-mc-7abc70550635`

- 도메인: `TRANSPOSE-SIGN` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.9
- 성취기준: [9수02-04]

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

## 표본 182 · `wm-misc-eval-mc-21179bb16cbb`

- 도메인: `TRANSPOSE-SIGN` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.6
- 성취기준: [9수02-04]

**문항**: 일차방정식 x + 2 = 21 의 해를 구하시오.

**정답**: `19`

**풀이**: 2를 이항하면 부호가 바뀌어 x = 21 - 2 = 19 이다. 이항할 때 부호를 바꾸지 않으면 21 + 2로 틀린다.

**verify(SymPy 입력)**: conditions: `x = 21 - 2` · answer_map: {x=19}

**선지**:
- ① `2` ← 정답
- ② `19` ← 정답
- ③ `21` ← 정답
- ④ `23` ← 오답 · 오개념 `transpose-no-sign-change`

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

## 표본 183 · `wm-misc-eval-mc-66ffd0eff165`

- 도메인: `TRANSPOSE-SIGN` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.4
- 성취기준: [9수02-04]

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

## 표본 184 · `wm-misc-eval-mc-0e0caa094f55`

- 도메인: `TRANSPOSE-SIGN` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.2
- 성취기준: [9수02-04]

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

## 표본 185 · `wm-misc-eval-mc-5a258b36cc6a`

- 도메인: `TRAPEZOID-AREA` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3
- 성취기준: [6수03-14]

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

## 표본 186 · `wm-misc-eval-mc-3288eb35a375`

- 도메인: `TRAPEZOID-AREA` · 발문형식: 객관식 · 정답형식: 분수 · 난이도: 3.4
- 성취기준: [6수03-14]

**문항**: 윗변이 2, 아랫변이 9, 높이가 9 인 사다리꼴의 넓이를 구하시오.

**정답**: `99/2`

**풀이**: 사다리꼴의 넓이 = (윗변+아랫변)×높이÷2 = (2+9)×9÷2 = 99/2 이다. ÷2 를 빠뜨리면 99 가 되어 틀린다.

**verify(SymPy 입력)**: conditions: `x = (2+9)*9/2` · answer_map: {x=99/2}

**선지**:
- ① `18` ← 정답
- ② `99/2` ← 정답
- ③ `81` ← 정답
- ④ `99` ← 오답 · 오개념 `trapezoid-area-no-half`

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

## 표본 187 · `wm-misc-eval-mc-b1711e1c7f84`

- 도메인: `TRAPEZOID-AREA` · 발문형식: 객관식 · 정답형식: 분수 · 난이도: 3.2
- 성취기준: [6수03-14]

**문항**: 윗변이 2, 아랫변이 9, 높이가 7 인 사다리꼴의 넓이를 구하시오.

**정답**: `77/2`

**풀이**: 사다리꼴의 넓이 = (윗변+아랫변)×높이÷2 = (2+9)×7÷2 = 77/2 이다. ÷2 를 빠뜨리면 77 이 되어 틀린다.

**verify(SymPy 입력)**: conditions: `x = (2+9)*7/2` · answer_map: {x=77/2}

**선지**:
- ① `14` ← 정답
- ② `77/2` ← 정답
- ③ `63` ← 정답
- ④ `77` ← 오답 · 오개념 `trapezoid-area-no-half`

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

## 표본 188 · `wm-misc-eval-mc-a53d626d5fbc`

- 도메인: `TRAPEZOID-AREA` · 발문형식: 객관식 · 정답형식: 분수 · 난이도: 2.7
- 성취기준: [6수03-14]

**문항**: 윗변이 2, 아랫변이 13, 높이가 9 인 사다리꼴의 넓이를 구하시오.

**정답**: `135/2`

**풀이**: 사다리꼴의 넓이 = (윗변+아랫변)×높이÷2 = (2+13)×9÷2 = 135/2 이다. ÷2 를 빠뜨리면 135 가 되어 틀린다.

**verify(SymPy 입력)**: conditions: `x = (2+13)*9/2` · answer_map: {x=135/2}

**선지**:
- ① `18` ← 정답
- ② `135/2` ← 정답
- ③ `117` ← 정답
- ④ `135` ← 오답 · 오개념 `trapezoid-area-no-half`

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

## 표본 190 · `wm-misc-eval-mc-0522c33b246c`

- 도메인: `TRIG-ADD` · 발문형식: 객관식 · 정답형식: 실수 · 난이도: 3
- 성취기준: [12미적Ⅱ-02-02]

**문항**: 두 각 A = 2π/12, B = 11π/12 에 대하여 3 sin(A + B) 의 값을 구하시오.

**정답**: `-3*sqrt(6)/4 + 3*sqrt(2)/4`

**풀이**: 삼각함수의 덧셈정리에 의해 sin(A + B) = sin A cos B + cos A sin B 이다. 사인을 합에 분배하여 sin A + sin B 로 계산하면 틀린 값이 된다.

**verify(SymPy 입력)**: conditions: `x = 3*sin(2*pi/12 + 11*pi/12)` · answer_map: {x=-3*sqrt(6)/4 + 3*sqrt(2)/4}

**선지**:
- ① `3*sqrt(3)*(-sqrt(6)/4 - sqrt(2)/4)/2` ← 정답
- ② `-3*sqrt(6)/8 - 3*sqrt(2)/8` ← 정답
- ③ `-3*sqrt(6)/4 + 3*sqrt(2)/4` ← 정답
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

## 표본 191 · `wm-misc-eval-mc-870b94234f90`

- 도메인: `TRIG-ADD` · 발문형식: 객관식 · 정답형식: 실수 · 난이도: 2.8
- 성취기준: [12미적Ⅱ-02-02]

**문항**: 두 각 A = 2π/12, B = 11π/12 에 대하여 sin(A + B) 의 값을 구하시오.

**정답**: `-sqrt(6)/4 + sqrt(2)/4`

**풀이**: 삼각함수의 덧셈정리에 의해 sin(A + B) = sin A cos B + cos A sin B 이다. 사인을 합에 분배하여 sin A + sin B 로 계산하면 틀린 값이 된다.

**verify(SymPy 입력)**: conditions: `x = 1*sin(2*pi/12 + 11*pi/12)` · answer_map: {x=-sqrt(6)/4 + sqrt(2)/4}

**선지**:
- ① `sqrt(3)*(-sqrt(6)/4 - sqrt(2)/4)/2` ← 정답
- ② `-sqrt(6)/8 - sqrt(2)/8` ← 정답
- ③ `-sqrt(6)/4 + sqrt(2)/4` ← 정답
- ④ `-sqrt(2)/4 + 1/2 + sqrt(6)/4` ← 오답 · 오개념 `sine-distributes-over-sum` (op: `sine-distributed-over-sum`)

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

## 표본 192 · `wm-misc-eval-mc-0ca0aefbb46e`

- 도메인: `TRIG-ADD` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.3
- 성취기준: [12미적Ⅱ-02-02]

**문항**: 두 각 A = 1π/12, B = 5π/12 에 대하여 2 sin(A + B) 의 값을 구하시오.

**정답**: `2`

**풀이**: 삼각함수의 덧셈정리에 의해 sin(A + B) = sin A cos B + cos A sin B 이다. 사인을 합에 분배하여 sin A + sin B 로 계산하면 틀린 값이 된다.

**verify(SymPy 입력)**: conditions: `x = 2*sin(1*pi/12 + 5*pi/12)` · answer_map: {x=2}

**선지**:
- ① `2*(-sqrt(2)/4 + sqrt(6)/4)**2` ← 정답
- ② `2*(-sqrt(2)/4 + sqrt(6)/4)*(sqrt(2)/4 + sqrt(6)/4)` ← 정답
- ③ `2` ← 정답
- ④ `sqrt(6)` ← 오답 · 오개념 `sine-distributes-over-sum` (op: `sine-distributed-over-sum`)

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

## 표본 193 · `wm-misc-eval-mc-9f0b7251a4f0`

- 도메인: `TRIG-PERIOD` · 발문형식: 객관식 · 정답형식: 실수 · 난이도: 3.1
- 성취기준: [12대수02-02]

**문항**: 함수 y = sin(6x) 의 주기를 구하시오.

**정답**: `pi/3`

**풀이**: y = sin(bx) 의 주기는 2π/b 이므로 y = sin(6x) 의 주기는 2π/6 이다. 계수 6 을 무시하면 주기를 2π 로 잘못 구한다.

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

## 표본 194 · `wm-misc-eval-mc-2ae7ad0ed8c7`

- 도메인: `TRIG-PERIOD` · 발문형식: 객관식 · 정답형식: 실수 · 난이도: 2.9
- 성취기준: [12대수02-02]

**문항**: 함수 y = sin(15x) 의 주기를 구하시오.

**정답**: `2*pi/15`

**풀이**: y = sin(bx) 의 주기는 2π/b 이므로 y = sin(15x) 의 주기는 2π/15 이다. 계수 15 를 무시하면 주기를 2π 로 잘못 구한다.

**verify(SymPy 입력)**: conditions: `x = 2*pi/15` · answer_map: {x=2*pi/15}

**선지**:
- ① `pi/15` ← 정답
- ② `2*pi/15` ← 정답
- ③ `2*pi` ← 오답 · 오개념 `period-of-scaled-sine`
- ④ `30*pi` ← 정답

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

## 표본 195 · `wm-misc-eval-mc-73e09670f172`

- 도메인: `TRIG-PERIOD` · 발문형식: 객관식 · 정답형식: 실수 · 난이도: 2.6
- 성취기준: [12대수02-02]

**문항**: 함수 y = sin(23x) 의 주기를 구하시오.

**정답**: `2*pi/23`

**풀이**: y = sin(bx) 의 주기는 2π/b 이므로 y = sin(23x) 의 주기는 2π/23 이다. 계수 23 을 무시하면 주기를 2π 로 잘못 구한다.

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

## 표본 196 · `wm-misc-eval-mc-2b130d00385c`

- 도메인: `TRIG-PERIOD` · 발문형식: 객관식 · 정답형식: 실수 · 난이도: 3.4
- 성취기준: [12대수02-02]

**문항**: 함수 y = sin(20x) 의 주기를 구하시오.

**정답**: `pi/10`

**풀이**: y = sin(bx) 의 주기는 2π/b 이므로 y = sin(20x) 의 주기는 2π/20 이다. 계수 20 을 무시하면 주기를 2π 로 잘못 구한다.

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

## 표본 197 · `wm-misc-eval-mc-e80adc001dae`

- 도메인: `VIETA-SUM` · 발문형식: 객관식 · 정답형식: 분수 · 난이도: 2.8
- 성취기준: [10공수1-02-03]

**문항**: x² + 25x + 26 = 0 의 두 근의 합을 구하시오.

**정답**: `-25`

**풀이**: 근과 계수 관계로 두 근의 합은 -(일차항 계수) = -25 = -25 이다. 부호를 놓쳐 25로 답하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = -25` · answer_map: {x=-25}

**선지**:
- ① `-26` ← 정답
- ② `-25` ← 정답
- ③ `25` ← 오답 · 오개념 `vieta-sign-error`
- ④ `26` ← 정답

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

## 표본 198 · `wm-misc-eval-mc-85499f9351eb`

- 도메인: `VIETA-SUM` · 발문형식: 객관식 · 정답형식: 분수 · 난이도: 3.1
- 성취기준: [10공수1-02-03]

**문항**: x² + 6x + 7 = 0 의 두 근의 합을 구하시오.

**정답**: `-6`

**풀이**: 근과 계수 관계로 두 근의 합은 -(일차항 계수) = -6 = -6 이다. 부호를 놓쳐 6으로 답하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = -6` · answer_map: {x=-6}

**선지**:
- ① `-7` ← 정답
- ② `-6` ← 정답
- ③ `6` ← 오답 · 오개념 `vieta-sign-error`
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

## 표본 199 · `wm-misc-eval-mc-ec5fdd8a2f96`

- 도메인: `VIETA-SUM` · 발문형식: 객관식 · 정답형식: 분수 · 난이도: 2.6
- 성취기준: [10공수1-02-03]

**문항**: x² + 23x + 24 = 0 의 두 근의 합을 구하시오.

**정답**: `-23`

**풀이**: 근과 계수 관계로 두 근의 합은 -(일차항 계수) = -23 = -23 이다. 부호를 놓쳐 23으로 답하면 틀린다.

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

## 표본 200 · `wm-misc-eval-mc-2946aa9fd990`

- 도메인: `VIETA-SUM` · 발문형식: 객관식 · 정답형식: 분수 · 난이도: 3.4
- 성취기준: [10공수1-02-03]

**문항**: x² + 20x + 21 = 0 의 두 근의 합을 구하시오.

**정답**: `-20`

**풀이**: 근과 계수 관계로 두 근의 합은 -(일차항 계수) = -20 = -20 이다. 부호를 놓쳐 20으로 답하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = -20` · answer_map: {x=-20}

**선지**:
- ① `-21` ← 정답
- ② `-20` ← 정답
- ③ `20` ← 오답 · 오개념 `vieta-sign-error`
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

<!-- coverage: {"n":200,"corpus_size":1080,"domain_counts":{"ABS-VALUE":5,"AREA-PERIMETER":5,"CALC-CHAIN":5,"CALC-PRODUCT":5,"CIRCLE-AREA":5,"CIRCLE-RADIUS":5,"COMBINATION-COUNT":5,"COMBINE-UNLIKE":5,"COMPLETE-SQUARE":5,"CONE-VOLUME":5,"CONJUGATE-PRODUCT":5,"DECIMAL-MULT":5,"DIFF-SQUARES":5,"DISTRIBUTE-PARTIAL":5,"EXP-PRODUCT":5,"EXP-ZERO":5,"FRACTION-ADD":5,"FRACTION-CANCEL":5,"FUNC-COMPOSE":5,"FUNC-TRANSLATE":5,"GCD-LCM":4,"LOG-DIST":4,"MIDPOINT-NO-HALF":4,"MIXED-MULT":4,"NEG-DISTRIBUTE":4,"NEG-EVEN-POWER":4,"NEG-PRODUCT":4,"NEG-SQUARE":4,"POLY-PRODUCT":4,"POLYGON-ANGLE-SUM":4,"POWER-OF-POWER":4,"PROB-INDEPENDENT-TRIAL":4,"REMAINDER-THEOREM":4,"SAME-ITEM-PERM":4,"SCALE-AREA":4,"SCALE-VOLUME":4,"SQRT-POS":4,"SQRT-SUM":4,"SQUARE-DIFF":4,"SUBTRACT-NEG":4,"TRANSPOSE-SIGN":4,"TRAPEZOID-AREA":4,"TRIG-ADD":4,"TRIG-PERIOD":4,"VIETA-SUM":4},"format_counts":{"객관식":200},"misconception_counts":{"absolute-value-keeps-sign":5,"angle-sum-non-triangle":4,"area-perimeter-confusion":5,"chain-rule-inner-derivative-omitted":5,"circle-area-circumference":5,"circle-radius-squared":5,"combination-no-denominator":5,"combine-unlike-terms":5,"complete-square-naive":5,"composite-function-commutes":5,"cone-volume-no-third":5,"conjugate-product-sum":5,"decimal-mult-place":5,"difference-of-squares-confused":5,"distribute-first-term-only":5,"distribution-over-power":4,"exponent-product-multiplies":5,"exponent-zero":5,"fraction-addition-naive":5,"fraction-cancellation":5,"gambler-fallacy":4,"gcd-lcm-confused":4,"log-distribution":4,"midpoint-sum-only":4,"mixed-number-mult-whole":4,"negative-distribute-sign":4,"negative-even-power-sign":4,"negative-square-precedence":4,"negative-times-negative":4,"period-of-scaled-sine":4,"power-of-power-adds":4,"product-rule-naive":5,"remainder-theorem-sign":4,"same-item-permutation-no-divide":4,"scale-area-linear":4,"scale-volume-linear":4,"sine-distributes-over-sum":4,"sqrt-distributes-over-sum":4,"square-of-difference-no-cross":4,"square-root-positivity":4,"subtract-negative-sign":4,"translation-sign-flip":5,"transpose-no-sign-change":4,"trapezoid-area-no-half":4,"vieta-sign-error":4},"difficulty_min":2.5,"difficulty_max":3.5,"missing_required_misconceptions":["extremum-max-min-confused","extremum-value-vs-point-confused","factor-sign-flip","opposite-root-selected"]} -->
