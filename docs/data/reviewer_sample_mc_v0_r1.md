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

## 표본 01 · `wm-misc-eval-mc-1f9b1884d949`

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

## 표본 02 · `wm-misc-eval-mc-2389a71722ed`

- 도메인: `ABS-VALUE` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.8
- 성취기준: [9수01-04]

**문항**: |-2| + 12 의 값을 구하시오.

**정답**: `14`

**풀이**: 절댓값은 음이 아니므로 |-2| = 2 이고 |-2| + 12 = 14 이다. 절댓값이 음수 부호를 유지한다고 여기면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 2+12` · answer_map: {x=14}

**선지**:
- ① `-14` ← 정답
- ② `-10` ← 정답
- ③ `10` ← 오답 · 오개념 `absolute-value-keeps-sign`
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

## 표본 04 · `wm-misc-eval-mc-fe2a397962e0`

- 도메인: `ABS-VALUE` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.2
- 성취기준: [9수01-04]

**문항**: |-2| + 16 의 값을 구하시오.

**정답**: `18`

**풀이**: 절댓값은 음이 아니므로 |-2| = 2 이고 |-2| + 16 = 18 이다. 절댓값이 음수 부호를 유지한다고 여기면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 2+16` · answer_map: {x=18}

**선지**:
- ① `-18` ← 정답
- ② `-14` ← 정답
- ③ `14` ← 오답 · 오개념 `absolute-value-keeps-sign`
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

## 표본 05 · `wm-misc-eval-mc-07393165891c`

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

## 표본 06 · `wm-misc-eval-mc-03d4a68df85a`

- 도메인: `AREA-PERIMETER` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.5
- 성취기준: [12직수03-04], [6수03-11], [6수03-13]

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

## 표본 07 · `wm-misc-eval-mc-f4335e08d35a`

- 도메인: `AREA-PERIMETER` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.4
- 성취기준: [12직수03-04], [6수03-11], [6수03-13]

**문항**: 가로가 2, 세로가 7 인 직사각형의 넓이를 구하시오.

**정답**: `14`

**풀이**: 직사각형의 넓이는 가로×세로 = 2×7 = 14 이다. 둘레 2×(2+7) = 18 과 혼동하면 틀린다.

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

## 표본 08 · `wm-misc-eval-mc-193d905f3fa8`

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

## 표본 09 · `wm-misc-eval-mc-8a5fa60d73a2`

- 도메인: `AREA-PERIMETER` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.6
- 성취기준: [12직수03-04], [6수03-11], [6수03-13]

**문항**: 가로가 4, 세로가 8 인 직사각형의 넓이를 구하시오.

**정답**: `32`

**풀이**: 직사각형의 넓이는 가로×세로 = 4×8 = 32 이다. 둘레 2×(4+8) = 24 와 혼동하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 4*8` · answer_map: {x=32}

**선지**:
- ① `12` ← 정답
- ② `24` ← 오답 · 오개념 `area-perimeter-confusion`
- ③ `32` ← 정답
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

## 표본 10 · `wm-misc-eval-mc-cd4c0928e81f`

- 도메인: `AREA-PERIMETER` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.2
- 성취기준: [12직수03-04], [6수03-11], [6수03-13]

**문항**: 가로가 6, 세로가 12 인 직사각형의 넓이를 구하시오.

**정답**: `72`

**풀이**: 직사각형의 넓이는 가로×세로 = 6×12 = 72 이다. 둘레 2×(6+12) = 36 과 혼동하면 틀린다.

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

## 표본 11 · `wm-misc-eval-mc-cd82f58e145f`

- 도메인: `CALC-CHAIN` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.5
- 성취기준: [12미적Ⅰ-02-01], [12미적Ⅱ-02-05]

**문항**: 함수 f(x) = (4x + 3)^3 의 x = 1 에서의 미분계수 f'(1) 의 값을 구하시오.

**정답**: `588`

**풀이**: 연쇄법칙으로 도함수를 구하면 내부 함수의 도함수 4 를 곱해야 한다. x = 1 을 대입하면 미분계수는 588 이다. 내부 도함수 4 를 곱하지 않으면 틀린 값이 된다.

**verify(SymPy 입력)**: conditions: `x = 3*4*(4*1+3)**2` · answer_map: {x=588}

**선지**:
- ① `147` ← 오답 · 오개념 `chain-rule-inner-derivative-omitted` (op: `chain-rule-omit-inner`)
- ② `196` ← 정답
- ③ `588` ← 정답
- ④ `2352` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- [ ] ⑤ 오답↔오개념 귀속 타당(선지별 오개념·op-code)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 12 · `wm-misc-eval-mc-888ee9abe651`

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

## 표본 14 · `wm-misc-eval-mc-e3fb3fb03720`

- 도메인: `CALC-CHAIN` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.3
- 성취기준: [12미적Ⅰ-02-01], [12미적Ⅱ-02-05]

**문항**: 함수 f(x) = (2x + 4)^3 의 x = 1 에서의 미분계수 f'(1) 의 값을 구하시오.

**정답**: `216`

**풀이**: 연쇄법칙으로 도함수를 구하면 내부 함수의 도함수 2 를 곱해야 한다. x = 1 을 대입하면 미분계수는 216 이다. 내부 도함수 2 를 곱하지 않으면 틀린 값이 된다.

**verify(SymPy 입력)**: conditions: `x = 3*2*(2*1+4)**2` · answer_map: {x=216}

**선지**:
- ① `72` ← 정답
- ② `108` ← 오답 · 오개념 `chain-rule-inner-derivative-omitted` (op: `chain-rule-omit-inner`)
- ③ `216` ← 정답
- ④ `432` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
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

## 표본 17 · `wm-misc-eval-mc-506b5ef44920`

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

## 표본 18 · `wm-misc-eval-mc-58a4194da09e`

- 도메인: `CALC-PRODUCT` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.5
- 성취기준: [12미적Ⅰ-02-01], [12미적Ⅰ-02-04]

**문항**: 두 함수 f(x) = x^2, g(x) = x^3 에 대하여 함수 f(x)g(x) 의 x = 5 에서의 미분계수를 구하시오.

**정답**: `3125`

**풀이**: f(x)g(x) = x^5 이므로 미분계수는 5·5^4 = 3125 이다. (fg)' = f'g' 로 오인하면 틀린 값이 된다.

**verify(SymPy 입력)**: conditions: `x = 5*5**4` · answer_map: {x=3125}

**선지**:
- ① `750` ← 오답 · 오개념 `product-rule-naive`
- ② `3125` ← 정답
- ③ `3750` ← 정답
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

## 표본 23 · `wm-misc-eval-mc-17783181c907`

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

## 표본 24 · `wm-misc-eval-mc-6aca045ddacc`

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

## 표본 25 · `wm-misc-eval-mc-cb3531d9d8d5`

- 도메인: `CIRCLE-AREA` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3
- 성취기준: [6수03-16], [9수03-06]

**문항**: 반지름이 27 인 원의 넓이를 원주율 π로 나눈 값을 구하시오.

**정답**: `729`

**풀이**: 원의 넓이는 π×(반지름)² 이므로 π로 나눈 값은 27² 곧 729 이다. 원의 둘레 공식 2πr 과 혼동하면 2×27 곧 54 로 잘못 답한다.

**verify(SymPy 입력)**: conditions: `x = 27**2` · answer_map: {x=729}

**선지**:
- ① `27` ← 정답
- ② `54` ← 오답 · 오개념 `circle-area-circumference`
- ③ `729` ← 정답
- ④ `1458` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
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

## 표본 27 · `wm-misc-eval-mc-ded9e50574c7`

- 도메인: `CIRCLE-RADIUS` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3
- 성취기준: [10공수2-01-04], [10기수2-01-04], [12기하02-05]

**문항**: 원 x^2 + y^2 = 729 의 반지름의 길이를 구하시오.

**정답**: `27`

**풀이**: x² + y² = r² 에서 반지름은 r 이므로 r² = 729 이면 반지름은 27 이다. 우변 729 를 반지름으로 여기면 틀린다.

**verify(SymPy 입력)**: conditions: `x = sqrt(729)` · answer_map: {x=27}

**선지**:
- ① `27` ← 정답
- ② `54` ← 정답
- ③ `729` ← 오답 · 오개념 `circle-radius-squared`
- ④ `756` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- [ ] ⑤ 오답↔오개념 귀속 타당(선지별 오개념·op-code)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 28 · `wm-misc-eval-mc-7b7af9ab4d2d`

- 도메인: `CIRCLE-RADIUS` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.6
- 성취기준: [10공수2-01-04], [10기수2-01-04], [12기하02-05]

**문항**: 원 x^2 + y^2 = 144 의 반지름의 길이를 구하시오.

**정답**: `12`

**풀이**: x² + y² = r² 에서 반지름은 r 이므로 r² = 144 이면 반지름은 12 이다. 우변 144 를 반지름으로 여기면 틀린다.

**verify(SymPy 입력)**: conditions: `x = sqrt(144)` · answer_map: {x=12}

**선지**:
- ① `12` ← 정답
- ② `24` ← 정답
- ③ `144` ← 오답 · 오개념 `circle-radius-squared`
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

## 표본 29 · `wm-misc-eval-mc-da3631ce937f`

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

## 표본 30 · `wm-misc-eval-mc-797e6420385f`

- 도메인: `CIRCLE-RADIUS` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.2
- 성취기준: [10공수2-01-04], [10기수2-01-04], [12기하02-05]

**문항**: 원 x^2 + y^2 = 841 의 반지름의 길이를 구하시오.

**정답**: `29`

**풀이**: x² + y² = r² 에서 반지름은 r 이므로 r² = 841 이면 반지름은 29 이다. 우변 841 을 반지름으로 여기면 틀린다.

**verify(SymPy 입력)**: conditions: `x = sqrt(841)` · answer_map: {x=29}

**선지**:
- ① `29` ← 정답
- ② `58` ← 정답
- ③ `841` ← 오답 · 오개념 `circle-radius-squared`
- ④ `870` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
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

## 표본 37 · `wm-misc-eval-mc-4942d70f22e2`

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

## 표본 38 · `wm-misc-eval-mc-a37946b24064`

- 도메인: `COMBINE-UNLIKE` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.7
- 성취기준: [9수02-09]

**문항**: 2x + 5x² 에서 x = 6 일 때의 값을 구하시오.

**정답**: `192`

**풀이**: 차수가 다른 항은 따로 계산하므로 2x + 5x² 은 x = 6 에서 12 + 180 = 192 이다. 차수를 무시하고 7x³으로 결합하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 2*6 + 5*6**2` · answer_map: {x=192}

**선지**:
- ① `12` ← 정답
- ② `180` ← 정답
- ③ `192` ← 정답
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

## 표본 39 · `wm-misc-eval-mc-69505b4575ce`

- 도메인: `COMBINE-UNLIKE` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.6
- 성취기준: [9수02-09]

**문항**: 2x + 3x² 에서 x = 7 일 때의 값을 구하시오.

**정답**: `161`

**풀이**: 차수가 다른 항은 따로 계산하므로 2x + 3x² 은 x = 7 에서 14 + 147 = 161 이다. 차수를 무시하고 5x³으로 결합하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 2*7 + 3*7**2` · answer_map: {x=161}

**선지**:
- ① `14` ← 정답
- ② `147` ← 정답
- ③ `161` ← 정답
- ④ `1715` ← 오답 · 오개념 `combine-unlike-terms`

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
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

## 표본 41 · `wm-misc-eval-mc-2bd8f127cfd6`

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

## 표본 42 · `wm-misc-eval-mc-b510740ff69f`

- 도메인: `COMPLETE-SQUARE` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.1
- 성취기준: [9수02-19]

**문항**: x² + 10x 에서 x = 7 일 때의 값을 구하시오.

**정답**: `119`

**풀이**: x² + 10x 는 x = 7 에서 49 + 70 = 119 이다. 이를 (x+10)²으로 오인하면 (7+10)² = 289 가 되어 틀린다.

**verify(SymPy 입력)**: conditions: `x = 7**2 + 10*7` · answer_map: {x=119}

**선지**:
- ① `49` ← 정답
- ② `70` ← 정답
- ③ `119` ← 정답
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

## 표본 43 · `wm-misc-eval-mc-9fe940004295`

- 도메인: `COMPLETE-SQUARE` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.4
- 성취기준: [9수02-19]

**문항**: x² + 7x 에서 x = 2 일 때의 값을 구하시오.

**정답**: `18`

**풀이**: x² + 7x 는 x = 2 에서 4 + 14 = 18 이다. 이를 (x+7)²으로 오인하면 (2+7)² = 81 이 되어 틀린다.

**verify(SymPy 입력)**: conditions: `x = 2**2 + 7*2` · answer_map: {x=18}

**선지**:
- ① `4` ← 정답
- ② `14` ← 정답
- ③ `18` ← 정답
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

## 표본 45 · `wm-misc-eval-mc-0d3f7d53d659`

- 도메인: `COMPLETE-SQUARE` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.3
- 성취기준: [9수02-19]

**문항**: x² + 9x 에서 x = 10 일 때의 값을 구하시오.

**정답**: `190`

**풀이**: x² + 9x 는 x = 10 에서 100 + 90 = 190 이다. 이를 (x+9)²으로 오인하면 (10+9)² = 361 이 되어 틀린다.

**verify(SymPy 입력)**: conditions: `x = 10**2 + 9*10` · answer_map: {x=190}

**선지**:
- ① `90` ← 정답
- ② `100` ← 정답
- ③ `190` ← 정답
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

## 표본 47 · `wm-misc-eval-mc-3b8a76dfa0d5`

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

## 표본 48 · `wm-misc-eval-mc-ff6c4f73471c`

- 도메인: `CONE-VOLUME` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.5
- 성취기준: [9수03-08]

**문항**: 밑면의 반지름이 2, 높이가 9 인 원뿔의 부피를 원주율 π로 나눈 값을 구하시오.

**정답**: `12`

**풀이**: 원뿔의 부피는 ⅓×π×(반지름)²×높이 이므로 π로 나눈 값은 2²×9÷3 곧 12 이다. ⅓ 을 빠뜨려 원기둥 부피로 계산하면 36 이 되어 틀린다.

**verify(SymPy 입력)**: conditions: `x = 2**2*9/3` · answer_map: {x=12}

**선지**:
- ① `12` ← 정답
- ② `18` ← 정답
- ③ `24` ← 정답
- ④ `36` ← 오답 · 오개념 `cone-volume-no-third`

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- [ ] ⑤ 오답↔오개념 귀속 타당(선지별 오개념·op-code)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 49 · `wm-misc-eval-mc-6e857921f843`

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

## 표본 50 · `wm-misc-eval-mc-c2f74c881635`

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

## 표본 52 · `wm-misc-eval-mc-cbabd3ece209`

- 도메인: `CONJUGATE-PRODUCT` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.1
- 성취기준: [9수01-07]

**문항**: (√6 + 1)(√6 - 1) 의 값을 구하시오.

**정답**: `5`

**풀이**: 켤레 무리수의 곱은 (√6)² - 1² = 6 - 1 = 5 이다. 합차공식 부호를 오용해 6 + 1로 답하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 6 - 1` · answer_map: {x=5}

**선지**:
- ① `5` ← 정답
- ② `6` ← 정답
- ③ `7` ← 오답 · 오개념 `conjugate-product-sum`
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

## 표본 53 · `wm-misc-eval-mc-fc32d9f48dd6`

- 도메인: `CONJUGATE-PRODUCT` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.4
- 성취기준: [9수01-07]

**문항**: (√9 + 1)(√9 - 1) 의 값을 구하시오.

**정답**: `8`

**풀이**: 켤레 무리수의 곱은 (√9)² - 1² = 9 - 1 = 8 이다. 합차공식 부호를 오용해 9 + 1로 답하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 9 - 1` · answer_map: {x=8}

**선지**:
- ① `8` ← 정답
- ② `9` ← 정답
- ③ `10` ← 오답 · 오개념 `conjugate-product-sum`
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

## 표본 54 · `wm-misc-eval-mc-3442752d71e4`

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

## 표본 57 · `wm-misc-eval-mc-29b738d87126`

- 도메인: `DECIMAL-MULT` · 발문형식: 객관식 · 정답형식: 실수 · 난이도: 2.5
- 성취기준: [6수01-13]

**문항**: 0.4 × 0.7 의 값을 구하시오.

**정답**: `7/25`

**풀이**: 0.4 × 0.7 은 소수점 아래 자릿수를 더해 28/100 = 7/25 이다. 자릿수를 무시하면 28/10로 틀린다.

**verify(SymPy 입력)**: conditions: `x = 4*7/100` · answer_map: {x=7/25}

**선지**:
- ① `7/25` ← 정답
- ② `2/5` ← 정답
- ③ `7/10` ← 정답
- ④ `14/5` ← 오답 · 오개념 `decimal-mult-place`

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- [ ] ⑤ 오답↔오개념 귀속 타당(선지별 오개념·op-code)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 58 · `wm-misc-eval-mc-2332a33b9d44`

- 도메인: `DECIMAL-MULT` · 발문형식: 객관식 · 정답형식: 실수 · 난이도: 2.7
- 성취기준: [6수01-13]

**문항**: 0.5 × 0.8 의 값을 구하시오.

**정답**: `2/5`

**풀이**: 0.5 × 0.8 은 소수점 아래 자릿수를 더해 40/100 = 2/5 이다. 자릿수를 무시하면 40/10으로 틀린다.

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

## 표본 59 · `wm-misc-eval-mc-b1a09d11cfbc`

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

## 표본 60 · `wm-misc-eval-mc-f82f7d77855c`

- 도메인: `DECIMAL-MULT` · 발문형식: 객관식 · 정답형식: 실수 · 난이도: 2.9
- 성취기준: [6수01-13]

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

## 표본 61 · `wm-misc-eval-mc-c3e9379fd24c`

- 도메인: `DIFF-SQUARES` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.5
- 성취기준: [9수02-19]

**문항**: x = 15, a = 6 일 때 x² - a² 의 값을 구하시오.

**정답**: `189`

**풀이**: x² - a² = (x-a)(x+a) 이므로 x=15, a=6 을 대입하면 189 이다. 제곱의 차를 차의 제곱 (x-a)²으로 여기면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 189` · answer_map: {x=189}

**선지**:
- ① `81` ← 오답 · 오개념 `difference-of-squares-confused`
- ② `189` ← 정답
- ③ `261` ← 정답
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

## 표본 62 · `wm-misc-eval-mc-b58ab5ab09b6`

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

## 표본 64 · `wm-misc-eval-mc-7f1e16af0938`

- 도메인: `DIFF-SQUARES` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.1
- 성취기준: [9수02-19]

**문항**: x = 14, a = 3 일 때 x² - a² 의 값을 구하시오.

**정답**: `187`

**풀이**: x² - a² = (x-a)(x+a) 이므로 x=14, a=3 을 대입하면 187 이다. 제곱의 차를 차의 제곱 (x-a)²으로 여기면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 187` · answer_map: {x=187}

**선지**:
- ① `121` ← 오답 · 오개념 `difference-of-squares-confused`
- ② `187` ← 정답
- ③ `205` ← 정답
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

## 표본 65 · `wm-misc-eval-mc-627006141f59`

- 도메인: `DIFF-SQUARES` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.9
- 성취기준: [9수02-19]

**문항**: x = 14, a = 1 일 때 x² - a² 의 값을 구하시오.

**정답**: `195`

**풀이**: x² - a² = (x-a)(x+a) 이므로 x=14, a=1 을 대입하면 195 이다. 제곱의 차를 차의 제곱 (x-a)²으로 여기면 틀린다.

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

## 표본 66 · `wm-misc-eval-mc-fdd21f9b9db2`

- 도메인: `DISTRIBUTE-PARTIAL` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.2
- 성취기준: [9수02-09]

**문항**: 4(x + 6) 에서 x = 8 일 때의 값을 구하시오.

**정답**: `56`

**풀이**: 분배법칙으로 4(x + 6) = 4x + 24 이므로 x = 8 을 대입하면 56 이다. 뒷항을 분배하지 않고 32 + 6으로 계산하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 4 * (8 + 6)` · answer_map: {x=56}

**선지**:
- ① `24` ← 정답
- ② `32` ← 정답
- ③ `38` ← 오답 · 오개념 `distribute-first-term-only`
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

## 표본 67 · `wm-misc-eval-mc-04f6ec078307`

- 도메인: `DISTRIBUTE-PARTIAL` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.1
- 성취기준: [9수02-09]

**문항**: 6(x + 3) 에서 x = 8 일 때의 값을 구하시오.

**정답**: `66`

**풀이**: 분배법칙으로 6(x + 3) = 6x + 18 이므로 x = 8 을 대입하면 66 이다. 뒷항을 분배하지 않고 48 + 3으로 계산하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 6 * (8 + 3)` · answer_map: {x=66}

**선지**:
- ① `18` ← 정답
- ② `48` ← 정답
- ③ `51` ← 오답 · 오개념 `distribute-first-term-only`
- ④ `66` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- [ ] ⑤ 오답↔오개념 귀속 타당(선지별 오개념·op-code)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 68 · `wm-misc-eval-mc-962623fa314d`

- 도메인: `DISTRIBUTE-PARTIAL` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.6
- 성취기준: [9수02-09]

**문항**: 3(x + 2) 에서 x = 7 일 때의 값을 구하시오.

**정답**: `27`

**풀이**: 분배법칙으로 3(x + 2) = 3x + 6 이므로 x = 7 을 대입하면 27 이다. 뒷항을 분배하지 않고 21 + 2로 계산하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 3 * (7 + 2)` · answer_map: {x=27}

**선지**:
- ① `6` ← 정답
- ② `21` ← 정답
- ③ `23` ← 오답 · 오개념 `distribute-first-term-only`
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

## 표본 69 · `wm-misc-eval-mc-e05f082ccee2`

- 도메인: `DISTRIBUTE-PARTIAL` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.4
- 성취기준: [9수02-09]

**문항**: 5(x + 7) 에서 x = 8 일 때의 값을 구하시오.

**정답**: `75`

**풀이**: 분배법칙으로 5(x + 7) = 5x + 35 이므로 x = 8 을 대입하면 75 이다. 뒷항을 분배하지 않고 40 + 7로 계산하면 틀린다.

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

## 표본 70 · `wm-misc-eval-mc-3e43a9dd791d`

- 도메인: `DISTRIBUTE-PARTIAL` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.9
- 성취기준: [9수02-09]

**문항**: 5(x + 2) 에서 x = 8 일 때의 값을 구하시오.

**정답**: `50`

**풀이**: 분배법칙으로 5(x + 2) = 5x + 10 이므로 x = 8 을 대입하면 50 이다. 뒷항을 분배하지 않고 40 + 2로 계산하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 5 * (8 + 2)` · answer_map: {x=50}

**선지**:
- ① `10` ← 정답
- ② `40` ← 정답
- ③ `42` ← 오답 · 오개념 `distribute-first-term-only`
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

## 표본 71 · `wm-misc-eval-mc-eba4a8db014d`

- 도메인: `EXP-PRODUCT` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.2
- 성취기준: [9수02-08]

**문항**: 18 × 18² 의 값을 구하시오.

**정답**: `5832`

**풀이**: 밑이 같은 거듭제곱의 곱은 지수를 더하므로 18 × 18² = 18^(1+2) = 18³ = 5832 이다. 지수를 곱해 18² 으로 답하면 틀린다.

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

## 표본 72 · `wm-misc-eval-mc-92008e9e6e8b`

- 도메인: `EXP-PRODUCT` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.8
- 성취기준: [9수02-08]

**문항**: 3 × 3² 의 값을 구하시오.

**정답**: `27`

**풀이**: 밑이 같은 거듭제곱의 곱은 지수를 더하므로 3 × 3² = 3^(1+2) = 3³ = 27 이다. 지수를 곱해 3² 으로 답하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 3**3` · answer_map: {x=27}

**선지**:
- ① `3` ← 정답
- ② `9` ← 오답 · 오개념 `exponent-product-multiplies`
- ③ `27` ← 정답
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

## 표본 73 · `wm-misc-eval-mc-32fd324739bd`

- 도메인: `EXP-PRODUCT` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.4
- 성취기준: [9수02-08]

**문항**: 20 × 20² 의 값을 구하시오.

**정답**: `8000`

**풀이**: 밑이 같은 거듭제곱의 곱은 지수를 더하므로 20 × 20² = 20^(1+2) = 20³ = 8000 이다. 지수를 곱해 20² 으로 답하면 틀린다.

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

## 표본 74 · `wm-misc-eval-mc-e90d0d0a7c53`

- 도메인: `EXP-PRODUCT` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3
- 성취기준: [9수02-08]

**문항**: 5 × 5² 의 값을 구하시오.

**정답**: `125`

**풀이**: 밑이 같은 거듭제곱의 곱은 지수를 더하므로 5 × 5² = 5^(1+2) = 5³ = 125 이다. 지수를 곱해 5² 으로 답하면 틀린다.

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

## 표본 75 · `wm-misc-eval-mc-e18e217bca69`

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

## 표본 76 · `wm-misc-eval-mc-b138bf53024e`

- 도메인: `EXP-ZERO` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.2
- 성취기준: [9수02-08]

**문항**: 자연수 a = 3 에 대하여 4 + a^0 의 값을 구하시오.

**정답**: `5`

**풀이**: a^0 = 1 이므로 4 + a^0 = 4 + 1 = 5 이다. a^0 을 0 으로 잘못 계산하면 4 가 되어 틀린다.

**verify(SymPy 입력)**: conditions: `x = 4 + 3**0` · answer_map: {x=5}

**선지**:
- ① `4` ← 오답 · 오개념 `exponent-zero`
- ② `5` ← 정답
- ③ `6` ← 정답
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

## 표본 77 · `wm-misc-eval-mc-f9cc17148824`

- 도메인: `EXP-ZERO` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.5
- 성취기준: [9수02-08]

**문항**: 자연수 a = 3 에 대하여 19 + a^0 의 값을 구하시오.

**정답**: `20`

**풀이**: a^0 = 1 이므로 19 + a^0 = 19 + 1 = 20 이다. a^0 을 0 으로 잘못 계산하면 19 가 되어 틀린다.

**verify(SymPy 입력)**: conditions: `x = 19 + 3**0` · answer_map: {x=20}

**선지**:
- ① `19` ← 오답 · 오개념 `exponent-zero`
- ② `20` ← 정답
- ③ `21` ← 정답
- ④ `22` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- [ ] ⑤ 오답↔오개념 귀속 타당(선지별 오개념·op-code)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 78 · `wm-misc-eval-mc-58554363ef71`

- 도메인: `EXP-ZERO` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.1
- 성취기준: [9수02-08]

**문항**: 자연수 a = 3 에 대하여 14 + a^0 의 값을 구하시오.

**정답**: `15`

**풀이**: a^0 = 1 이므로 14 + a^0 = 14 + 1 = 15 이다. a^0 을 0 으로 잘못 계산하면 14 가 되어 틀린다.

**verify(SymPy 입력)**: conditions: `x = 14 + 3**0` · answer_map: {x=15}

**선지**:
- ① `14` ← 오답 · 오개념 `exponent-zero`
- ② `15` ← 정답
- ③ `16` ← 정답
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

## 표본 79 · `wm-misc-eval-mc-a20b95e37724`

- 도메인: `EXP-ZERO` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.8
- 성취기준: [9수02-08]

**문항**: 자연수 a = 3 에 대하여 22 + a^0 의 값을 구하시오.

**정답**: `23`

**풀이**: a^0 = 1 이므로 22 + a^0 = 22 + 1 = 23 이다. a^0 을 0 으로 잘못 계산하면 22 가 되어 틀린다.

**verify(SymPy 입력)**: conditions: `x = 22 + 3**0` · answer_map: {x=23}

**선지**:
- ① `22` ← 오답 · 오개념 `exponent-zero`
- ② `23` ← 정답
- ③ `24` ← 정답
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

## 표본 80 · `wm-misc-eval-mc-da8fa977eb40`

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

## 표본 81 · `wm-misc-eval-mc-ead1852dad48`

- 도메인: `FRACTION-ADD` · 발문형식: 객관식 · 정답형식: 분수 · 난이도: 2.9
- 성취기준: [9수01-05]

**문항**: 1/7 + 1/8 의 값을 구하시오.

**정답**: `15/56`

**풀이**: 1/7 + 1/8 은 통분하면 (7+8)/(7·8) = 15/56 이다. 통분 없이 분자·분모를 각각 더해 2/(p+q)로 답하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = (7+8)/(7*8)` · answer_map: {x=15/56}

**선지**:
- ① `1/8` ← 정답
- ② `2/15` ← 오답 · 오개념 `fraction-addition-naive`
- ③ `1/7` ← 정답
- ④ `15/56` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- [ ] ⑤ 오답↔오개념 귀속 타당(선지별 오개념·op-code)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 82 · `wm-misc-eval-mc-5dd31f351a30`

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

## 표본 83 · `wm-misc-eval-mc-2e589a597f59`

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

## 표본 84 · `wm-misc-eval-mc-ab674164baa5`

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

## 표본 85 · `wm-misc-eval-mc-b76d73a6669c`

- 도메인: `FRACTION-ADD` · 발문형식: 객관식 · 정답형식: 분수 · 난이도: 2.7
- 성취기준: [9수01-05]

**문항**: 1/5 + 1/8 의 값을 구하시오.

**정답**: `13/40`

**풀이**: 1/5 + 1/8 은 통분하면 (5+8)/(5·8) = 13/40 이다. 통분 없이 분자·분모를 각각 더해 2/(p+q)로 답하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = (5+8)/(5*8)` · answer_map: {x=13/40}

**선지**:
- ① `1/8` ← 정답
- ② `2/13` ← 오답 · 오개념 `fraction-addition-naive`
- ③ `1/5` ← 정답
- ④ `13/40` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- [ ] ⑤ 오답↔오개념 귀속 타당(선지별 오개념·op-code)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 86 · `wm-misc-eval-mc-82b510e28d0e`

- 도메인: `FRACTION-CANCEL` · 발문형식: 객관식 · 정답형식: 분수 · 난이도: 2.5
- 성취기준: [6수01-06], [9수01-04]

**문항**: 두 자연수 a = 6, b = 5 에 대하여 (a + b) / a 의 값을 구하시오.

**정답**: `11/6`

**풀이**: (a + b) / a = 1 + b/a 이므로 a = 6, b = 5 를 대입하면 11/6 이다. 분자와 분모의 a 를 지워 b 로 약분하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = (6+5)/6` · answer_map: {x=11/6}

**선지**:
- ① `11/6` ← 정답
- ② `5` ← 오답 · 오개념 `fraction-cancellation`
- ③ `6` ← 정답
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

## 표본 87 · `wm-misc-eval-mc-8f45a7ea2dc4`

- 도메인: `FRACTION-CANCEL` · 발문형식: 객관식 · 정답형식: 분수 · 난이도: 3.4
- 성취기준: [6수01-06], [9수01-04]

**문항**: 두 자연수 a = 2, b = 7 에 대하여 (a + b) / a 의 값을 구하시오.

**정답**: `9/2`

**풀이**: (a + b) / a = 1 + b/a 이므로 a = 2, b = 7 을 대입하면 9/2 이다. 분자와 분모의 a 를 지워 b 로 약분하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = (2+7)/2` · answer_map: {x=9/2}

**선지**:
- ① `2` ← 정답
- ② `9/2` ← 정답
- ③ `7` ← 오답 · 오개념 `fraction-cancellation`
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

## 표본 88 · `wm-misc-eval-mc-a499e428b71b`

- 도메인: `FRACTION-CANCEL` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3
- 성취기준: [6수01-06], [9수01-04]

**문항**: 두 자연수 a = 2, b = 14 에 대하여 (a + b) / a 의 값을 구하시오.

**정답**: `8`

**풀이**: (a + b) / a = 1 + b/a 이므로 a = 2, b = 14 를 대입하면 8 이다. 분자와 분모의 a 를 지워 b 로 약분하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = (2+14)/2` · answer_map: {x=8}

**선지**:
- ① `2` ← 정답
- ② `8` ← 정답
- ③ `14` ← 오답 · 오개념 `fraction-cancellation`
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

## 표본 89 · `wm-misc-eval-mc-be813a8db016`

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

## 표본 90 · `wm-misc-eval-mc-bf0e4d0064ba`

- 도메인: `FRACTION-CANCEL` · 발문형식: 객관식 · 정답형식: 분수 · 난이도: 3.1
- 성취기준: [6수01-06], [9수01-04]

**문항**: 두 자연수 a = 7, b = 10 에 대하여 (a + b) / a 의 값을 구하시오.

**정답**: `17/7`

**풀이**: (a + b) / a = 1 + b/a 이므로 a = 7, b = 10 을 대입하면 17/7 이다. 분자와 분모의 a 를 지워 b 로 약분하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = (7+10)/7` · answer_map: {x=17/7}

**선지**:
- ① `17/7` ← 정답
- ② `7` ← 정답
- ③ `10` ← 오답 · 오개념 `fraction-cancellation`
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

## 표본 93 · `wm-misc-eval-mc-dea4f43b2883`

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

## 표본 94 · `wm-misc-eval-mc-a8339373cd7d`

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

## 표본 95 · `wm-misc-eval-mc-e2fc39cbc19f`

- 도메인: `FUNC-COMPOSE` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.5
- 성취기준: [10공수2-03-02], [10기수2-03-02]

**문항**: 두 함수 f(x) = x + 1, g(x) = 3x 에 대하여 (f∘g)(6) 의 값을 구하시오.

**정답**: `19`

**풀이**: (f∘g)(6) = f(g(6)) = f(18) = 18 + 1 = 19 이다. 순서를 뒤집어 (g∘f)(6) = g(6+1) = 21 로 하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 3*6 + 1` · answer_map: {x=19}

**선지**:
- ① `18` ← 정답
- ② `19` ← 정답
- ③ `21` ← 오답 · 오개념 `composite-function-commutes`
- ④ `22` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
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

## 표본 98 · `wm-misc-eval-mc-7fff461a517e`

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

## 표본 99 · `wm-misc-eval-mc-f0e141d1f59f`

- 도메인: `FUNC-TRANSLATE` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.1
- 성취기준: [10공수2-01-06], [10기수2-01-06]

**문항**: 함수 f(x) = x^2 + 3x 에 대하여 g(x) = f(x - 1) 일 때, g(4) 의 값을 구하시오.

**정답**: `18`

**풀이**: y = f(x-1) 은 그래프를 오른쪽으로 1 평행이동한 것이므로 g(4) = f(4-1) = f(3) = 18 이다. 부호를 뒤집어 f(4+1) 로 계산하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 3**2 + 3*3` · answer_map: {x=18}

**선지**:
- ① `9` ← 정답
- ② `18` ← 정답
- ③ `28` ← 정답
- ④ `40` ← 오답 · 오개념 `translation-sign-flip`

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- [ ] ⑤ 오답↔오개념 귀속 타당(선지별 오개념·op-code)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 100 · `wm-misc-eval-mc-bd7b13015e4e`

- 도메인: `FUNC-TRANSLATE` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3
- 성취기준: [10공수2-01-06], [10기수2-01-06]

**문항**: 함수 f(x) = x^2 + 1x 에 대하여 g(x) = f(x - 1) 일 때, g(5) 의 값을 구하시오.

**정답**: `20`

**풀이**: y = f(x-1) 은 그래프를 오른쪽으로 1 평행이동한 것이므로 g(5) = f(5-1) = f(4) = 20 이다. 부호를 뒤집어 f(5+1) 로 계산하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 4**2 + 1*4` · answer_map: {x=20}

**선지**:
- ① `16` ← 정답
- ② `20` ← 정답
- ③ `30` ← 정답
- ④ `42` ← 오답 · 오개념 `translation-sign-flip`

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- [ ] ⑤ 오답↔오개념 귀속 타당(선지별 오개념·op-code)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 101 · `wm-misc-eval-mc-4c8d5078d926`

- 도메인: `GCD-LCM` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.4
- 성취기준: [9수01-02]

**문항**: 11 과 20 의 최소공배수를 구하시오.

**정답**: `220`

**풀이**: 11과 20의 최소공배수는 220 이다(최대공약수는 1). 최소공배수와 최대공약수를 혼동하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 220` · answer_map: {x=220}

**선지**:
- ① `1` ← 오답 · 오개념 `gcd-lcm-confused`
- ② `11` ← 정답
- ③ `20` ← 정답
- ④ `220` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
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

## 표본 104 · `wm-misc-eval-mc-8d87ed647298`

- 도메인: `GCD-LCM` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.6
- 성취기준: [9수01-02]

**문항**: 4 와 19 의 최소공배수를 구하시오.

**정답**: `76`

**풀이**: 4와 19의 최소공배수는 76 이다(최대공약수는 1). 최소공배수와 최대공약수를 혼동하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 76` · answer_map: {x=76}

**선지**:
- ① `1` ← 오답 · 오개념 `gcd-lcm-confused`
- ② `4` ← 정답
- ③ `19` ← 정답
- ④ `76` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
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

## 표본 107 · `wm-misc-eval-mc-270f3556cdff`

- 도메인: `LOG-DIST` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.6
- 성취기준: [12대수01-04], [12대수01-05]

**문항**: log_2(2^23 + 2^23) 의 값을 구하시오.

**정답**: `24`

**풀이**: 2^23 + 2^23 = 2·2^23 = 2^24 이므로 값은 24 이다. 로그를 합에 분배해 23+23 = 46 으로 하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = log(2**23 + 2**23, 2)` · answer_map: {x=24}

**선지**:
- ① `23` ← 정답
- ② `24` ← 정답
- ③ `46` ← 오답 · 오개념 `log-distribution`
- ④ `47` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- [ ] ⑤ 오답↔오개념 귀속 타당(선지별 오개념·op-code)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 108 · `wm-misc-eval-mc-d2f6a5c9b890`

- 도메인: `LOG-DIST` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.9
- 성취기준: [12대수01-04], [12대수01-05]

**문항**: log_2(2^15 + 2^15) 의 값을 구하시오.

**정답**: `16`

**풀이**: 2^15 + 2^15 = 2·2^15 = 2^16 이므로 값은 16 이다. 로그를 합에 분배해 15+15 = 30 으로 하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = log(2**15 + 2**15, 2)` · answer_map: {x=16}

**선지**:
- ① `15` ← 정답
- ② `16` ← 정답
- ③ `30` ← 오답 · 오개념 `log-distribution`
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

## 표본 110 · `wm-misc-eval-mc-0e2fe5f29ba4`

- 도메인: `MIDPOINT-NO-HALF` · 발문형식: 객관식 · 정답형식: 분수 · 난이도: 3.4
- 성취기준: [9수02-05]

**문항**: 수직선 위 두 점 1, 8 의 중점의 좌표를 구하시오.

**정답**: `9/2`

**풀이**: 두 점의 중점은 좌표의 평균이므로 (1+8)/2 = 9/2 이다. 2로 나누지 않고 9로 답하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = (1+8)/2` · answer_map: {x=9/2}

**선지**:
- ① `1` ← 정답
- ② `9/2` ← 정답
- ③ `8` ← 정답
- ④ `9` ← 오답 · 오개념 `midpoint-sum-only`

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- [ ] ⑤ 오답↔오개념 귀속 타당(선지별 오개념·op-code)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 111 · `wm-misc-eval-mc-f2ccca97906d`

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

## 표본 113 · `wm-misc-eval-mc-8184ba24252d`

- 도메인: `MIXED-MULT` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3
- 성취기준: [9수01-05]

**문항**: 3과 1/2 (대분수)에 2 를 곱한 값을 구하시오.

**정답**: `7`

**풀이**: 대분수 3½ = 7/2 에 2를 곱하면 14/2 = 7 이다. 정수부만 곱해 6½로 답하면 틀린다.

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

## 표본 114 · `wm-misc-eval-mc-660adc4987e1`

- 도메인: `MIXED-MULT` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.5
- 성취기준: [9수01-05]

**문항**: 8과 1/2 (대분수)에 2 를 곱한 값을 구하시오.

**정답**: `17`

**풀이**: 대분수 8½ = 17/2 에 2를 곱하면 34/2 = 17 이다. 정수부만 곱해 16½로 답하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = (17*2)/2` · answer_map: {x=17}

**선지**:
- ① `17/2` ← 정답
- ② `16` ← 정답
- ③ `33/2` ← 오답 · 오개념 `mixed-number-mult-whole`
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

## 표본 115 · `wm-misc-eval-mc-20c298d1cbd8`

- 도메인: `MIXED-MULT` · 발문형식: 객관식 · 정답형식: 분수 · 난이도: 2.8
- 성취기준: [9수01-05]

**문항**: 7과 1/2 (대분수)에 7 을 곱한 값을 구하시오.

**정답**: `105/2`

**풀이**: 대분수 7½ = 15/2 에 7을 곱하면 105/2 = 105/2 이다. 정수부만 곱해 49½로 답하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = (15*7)/2` · answer_map: {x=105/2}

**선지**:
- ① `15/2` ← 정답
- ② `49` ← 정답
- ③ `99/2` ← 오답 · 오개념 `mixed-number-mult-whole`
- ④ `105/2` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- [ ] ⑤ 오답↔오개념 귀속 타당(선지별 오개념·op-code)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 116 · `wm-misc-eval-mc-de01ef7f9bb2`

- 도메인: `MIXED-MULT` · 발문형식: 객관식 · 정답형식: 분수 · 난이도: 2.6
- 성취기준: [9수01-05]

**문항**: 7과 1/2 (대분수)에 5 를 곱한 값을 구하시오.

**정답**: `75/2`

**풀이**: 대분수 7½ = 15/2 에 5를 곱하면 75/2 = 75/2 이다. 정수부만 곱해 35½로 답하면 틀린다.

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

## 표본 118 · `wm-misc-eval-mc-adc92ee70b90`

- 도메인: `NEG-DISTRIBUTE` · 발문형식: 객관식 · 정답형식: 분수 · 난이도: 2.9
- 성취기준: [9수02-09]

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

## 표본 119 · `wm-misc-eval-mc-2f2b08f73981`

- 도메인: `NEG-DISTRIBUTE` · 발문형식: 객관식 · 정답형식: 분수 · 난이도: 2.6
- 성취기준: [9수02-09]

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

## 표본 120 · `wm-misc-eval-mc-6a902da47b1b`

- 도메인: `NEG-DISTRIBUTE` · 발문형식: 객관식 · 정답형식: 분수 · 난이도: 3.5
- 성취기준: [9수02-09]

**문항**: -(x - 2) 에서 x = 8 일 때의 값을 구하시오.

**정답**: `-6`

**풀이**: 음의 부호 분배는 -(x - 2) = -x + 2 이므로 x = 8 을 대입하면 -6 이다. 뒷항 부호를 반전하지 않고 -8 - 2로 계산하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 2 - 8` · answer_map: {x=-6}

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

## 표본 121 · `wm-misc-eval-mc-fd1bcb5e9d6b`

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

## 표본 122 · `wm-misc-eval-mc-da0d4a6580a9`

- 도메인: `NEG-EVEN-POWER` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.6
- 성취기준: [9수02-08]

**문항**: (-8)^4 의 값을 구하시오.

**정답**: `4096`

**풀이**: 음수의 짝수 거듭제곱은 양수이므로 (-8)^4 = 8^4 = 4096 이다. 음수로 여겨 -4096으로 답하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 8**4` · answer_map: {x=4096}

**선지**:
- ① `-4096` ← 오답 · 오개념 `negative-even-power-sign`
- ② `-8` ← 정답
- ③ `8` ← 정답
- ④ `4096` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
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

**풀이**: 음수의 짝수 거듭제곱은 양수이므로 (-16)^2 = 16^2 = 256 이다. 음수로 여겨 -256으로 답하면 틀린다.

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

## 표본 129 · `wm-misc-eval-mc-971906fc960c`

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

## 표본 130 · `wm-misc-eval-mc-4f4b47f02581`

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

## 표본 131 · `wm-misc-eval-mc-51a1ad2b2136`

- 도메인: `NEG-SQUARE` · 발문형식: 객관식 · 정답형식: 분수 · 난이도: 3.2
- 성취기준: [9수02-08]

**문항**: -4² + 3 의 값을 구하시오.

**정답**: `-13`

**풀이**: 거듭제곱이 부호보다 우선하므로 -4² = -16 이고 -4² + 3 = -13 이다. -4²을 (-4)²=16으로 계산하면 틀린다.

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

## 표본 132 · `wm-misc-eval-mc-176e79b4dab5`

- 도메인: `NEG-SQUARE` · 발문형식: 객관식 · 정답형식: 분수 · 난이도: 3.5
- 성취기준: [9수02-08]

**문항**: -9² + 1 의 값을 구하시오.

**정답**: `-80`

**풀이**: 거듭제곱이 부호보다 우선하므로 -9² = -81 이고 -9² + 1 = -80 이다. -9²을 (-9)²=81로 계산하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 1 - 81` · answer_map: {x=-80}

**선지**:
- ① `-82` ← 정답
- ② `-80` ← 정답
- ③ `80` ← 정답
- ④ `82` ← 오답 · 오개념 `negative-square-precedence`

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- [ ] ⑤ 오답↔오개념 귀속 타당(선지별 오개념·op-code)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 133 · `wm-misc-eval-mc-c7deedea9e69`

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

## 표본 134 · `wm-misc-eval-mc-666755947fdf`

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

## 표본 135 · `wm-misc-eval-mc-95a2eaa7b769`

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

## 표본 136 · `wm-misc-eval-mc-243207ec0d64`

- 도메인: `POLY-PRODUCT` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.2
- 성취기준: [9수02-19]

**문항**: 두 수 a, b에 대하여 a = 6, b = 23 일 때, (a+b)^2 의 값을 구하시오.

**정답**: `841`

**풀이**: (a+b)^2 = a^2 + 2ab + b^2 이므로 a = 6, b = 23 을 대입하면 (a+b)^2 = 841 이다. 교차항 2ab 를 빠뜨리면 a^2+b^2 이 되어 틀린다.

**verify(SymPy 입력)**: conditions: `x = (6+23)**2` · answer_map: {x=841}

**선지**:
- ① `276` ← 정답
- ② `565` ← 오답 · 오개념 `distribution-over-power` (op: `power-distributed-no-cross-term`)
- ③ `703` ← 정답
- ④ `841` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- [ ] ⑤ 오답↔오개념 귀속 타당(선지별 오개념·op-code)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 137 · `wm-misc-eval-mc-d07e73d359ce`

- 도메인: `POLYGON-ANGLE-SUM` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.9
- 성취기준: [4수03-25], [9수03-03], [9수03-05]

**문항**: 4각형의 내각의 크기의 합을 구하시오. (단위: 도)

**정답**: `360`

**풀이**: n각형의 내각의 합은 (n - 2)·180° 이므로 4각형은 (4 - 2)·180 = 360° 이다. 모든 다각형의 내각의 합을 180° 로 여기면 틀린다.

**verify(SymPy 입력)**: conditions: `x = (4-2)*180` · answer_map: {x=360}

**선지**:
- ① `180` ← 오답 · 오개념 `angle-sum-non-triangle`
- ② `360` ← 정답
- ③ `540` ← 정답
- ④ `720` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- [ ] ⑤ 오답↔오개념 귀속 타당(선지별 오개념·op-code)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 138 · `wm-misc-eval-mc-6f9214b3f450`

- 도메인: `POLYGON-ANGLE-SUM` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.4
- 성취기준: [4수03-25], [9수03-03], [9수03-05]

**문항**: 20각형의 내각의 크기의 합을 구하시오. (단위: 도)

**정답**: `3240`

**풀이**: n각형의 내각의 합은 (n - 2)·180° 이므로 20각형은 (20 - 2)·180 = 3240° 이다. 모든 다각형의 내각의 합을 180° 로 여기면 틀린다.

**verify(SymPy 입력)**: conditions: `x = (20-2)*180` · answer_map: {x=3240}

**선지**:
- ① `180` ← 오답 · 오개념 `angle-sum-non-triangle`
- ② `3240` ← 정답
- ③ `3420` ← 정답
- ④ `3600` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- [ ] ⑤ 오답↔오개념 귀속 타당(선지별 오개념·op-code)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 139 · `wm-misc-eval-mc-2577dbaa14ff`

- 도메인: `POLYGON-ANGLE-SUM` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.1
- 성취기준: [4수03-25], [9수03-03], [9수03-05]

**문항**: 17각형의 내각의 크기의 합을 구하시오. (단위: 도)

**정답**: `2700`

**풀이**: n각형의 내각의 합은 (n - 2)·180° 이므로 17각형은 (17 - 2)·180 = 2700° 이다. 모든 다각형의 내각의 합을 180° 로 여기면 틀린다.

**verify(SymPy 입력)**: conditions: `x = (17-2)*180` · answer_map: {x=2700}

**선지**:
- ① `180` ← 오답 · 오개념 `angle-sum-non-triangle`
- ② `2700` ← 정답
- ③ `2880` ← 정답
- ④ `3060` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
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

## 표본 142 · `wm-misc-eval-mc-3da8379f9dca`

- 도메인: `POWER-OF-POWER` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.5
- 성취기준: [9수02-08]

**문항**: (4^2)^5 의 값을 구하시오.

**정답**: `1048576`

**풀이**: 거듭제곱의 거듭제곱은 지수를 곱하므로 (4^2)^5 = 4^10 = 1048576 이다. 지수를 더해 4^7 으로 답하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 4**10` · answer_map: {x=1048576}

**선지**:
- ① `16` ← 정답
- ② `1024` ← 정답
- ③ `16384` ← 오답 · 오개념 `power-of-power-adds`
- ④ `1048576` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- [ ] ⑤ 오답↔오개념 귀속 타당(선지별 오개념·op-code)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 143 · `wm-misc-eval-mc-bfb182f7ca6b`

- 도메인: `POWER-OF-POWER` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.6
- 성취기준: [9수02-08]

**문항**: (5^2)^5 의 값을 구하시오.

**정답**: `9765625`

**풀이**: 거듭제곱의 거듭제곱은 지수를 곱하므로 (5^2)^5 = 5^10 = 9765625 이다. 지수를 더해 5^7 으로 답하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 5**10` · answer_map: {x=9765625}

**선지**:
- ① `25` ← 정답
- ② `3125` ← 정답
- ③ `78125` ← 오답 · 오개념 `power-of-power-adds`
- ④ `9765625` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- [ ] ⑤ 오답↔오개념 귀속 타당(선지별 오개념·op-code)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 144 · `wm-misc-eval-mc-fa716865b484`

- 도메인: `POWER-OF-POWER` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.5
- 성취기준: [9수02-08]

**문항**: (2^3)^5 의 값을 구하시오.

**정답**: `32768`

**풀이**: 거듭제곱의 거듭제곱은 지수를 곱하므로 (2^3)^5 = 2^15 = 32768 이다. 지수를 더해 2^8 으로 답하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 2**15` · answer_map: {x=32768}

**선지**:
- ① `8` ← 정답
- ② `32` ← 정답
- ③ `256` ← 오답 · 오개념 `power-of-power-adds`
- ④ `32768` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
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

## 표본 146 · `wm-misc-eval-mc-a91132468dad`

- 도메인: `PROB-INDEPENDENT-TRIAL` · 발문형식: 객관식 · 정답형식: 분수 · 난이도: 2.5
- 성취기준: [12수문02-02], [12인수04-01], [12확통02-01]

**문항**: 앞면이 나올 확률이 5/6 인 동전을 던져 앞면이 3번 연속 나왔다. 다음 시행에서 앞면이 나올 확률을 구하시오.

**정답**: `5/6`

**풀이**: 각 시행은 독립이라 이전 결과와 무관하게 다음 앞면 확률은 5/6 그대로다. 연속으로 나왔으니 이제 덜 나온다고 여기는 도박사 오류에 빠지면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 5/6` · answer_map: {x=5/6}

**선지**:
- ① `1/6` ← 정답
- ② `5/12` ← 정답
- ③ `25/36` ← 오답 · 오개념 `gambler-fallacy`
- ④ `5/6` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- [ ] ⑤ 오답↔오개념 귀속 타당(선지별 오개념·op-code)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 147 · `wm-misc-eval-mc-1b04b825f003`

- 도메인: `PROB-INDEPENDENT-TRIAL` · 발문형식: 객관식 · 정답형식: 분수 · 난이도: 3.2
- 성취기준: [12수문02-02], [12인수04-01], [12확통02-01]

**문항**: 앞면이 나올 확률이 7/11 인 동전을 던져 앞면이 3번 연속 나왔다. 다음 시행에서 앞면이 나올 확률을 구하시오.

**정답**: `7/11`

**풀이**: 각 시행은 독립이라 이전 결과와 무관하게 다음 앞면 확률은 7/11 그대로다. 연속으로 나왔으니 이제 덜 나온다고 여기는 도박사 오류에 빠지면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 7/11` · answer_map: {x=7/11}

**선지**:
- ① `7/22` ← 정답
- ② `4/11` ← 정답
- ③ `49/121` ← 오답 · 오개념 `gambler-fallacy`
- ④ `7/11` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- [ ] ⑤ 오답↔오개념 귀속 타당(선지별 오개념·op-code)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 148 · `wm-misc-eval-mc-c7feb6c01121`

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

## 표본 149 · `wm-misc-eval-mc-290d67c6c9e9`

- 도메인: `REMAINDER-THEOREM` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.2
- 성취기준: [10공수1-01-02]

**문항**: 다항식 x² + 5x + 7 을 (x - 6)으로 나눈 나머지를 구하시오.

**정답**: `73`

**풀이**: 나머지정리로 f(6) = 6² + 5·6 + 7 = 73 이다. 부호를 반대로 f(-6)으로 대입하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 6**2 + 6*5 + 7` · answer_map: {x=73}

**선지**:
- ① `7` ← 정답
- ② `13` ← 오답 · 오개념 `remainder-theorem-sign`
- ③ `43` ← 정답
- ④ `73` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
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

## 표본 151 · `wm-misc-eval-mc-0ea657c44ed6`

- 도메인: `REMAINDER-THEOREM` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.9
- 성취기준: [10공수1-01-02]

**문항**: 다항식 x² + 3x + 6 을 (x - 6)으로 나눈 나머지를 구하시오.

**정답**: `60`

**풀이**: 나머지정리로 f(6) = 6² + 3·6 + 6 = 60 이다. 부호를 반대로 f(-6)으로 대입하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 6**2 + 6*3 + 6` · answer_map: {x=60}

**선지**:
- ① `6` ← 정답
- ② `24` ← 오답 · 오개념 `remainder-theorem-sign`
- ③ `42` ← 정답
- ④ `60` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- [ ] ⑤ 오답↔오개념 귀속 타당(선지별 오개념·op-code)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 152 · `wm-misc-eval-mc-8a9c999a04da`

- 도메인: `REMAINDER-THEOREM` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.1
- 성취기준: [10공수1-01-02]

**문항**: 다항식 x² + 7x + 4 를 (x - 6)으로 나눈 나머지를 구하시오.

**정답**: `82`

**풀이**: 나머지정리로 f(6) = 6² + 7·6 + 4 = 82 이다. 부호를 반대로 f(-6)으로 대입하면 틀린다.

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

## 표본 153 · `wm-misc-eval-mc-2be34085cd85`

- 도메인: `SAME-ITEM-PERM` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.8
- 성취기준: [12직수04-01], [12확통01-01]

**문항**: 5 개의 A 와 9 개의 B, 모두 14 개의 문자를 일렬로 배열하는 경우의 수를 구하시오.

**정답**: `2002`

**풀이**: 같은 것이 있는 순열이므로 14! 을 각 문자 개수의 계승 5!·9! 로 나눈다: 14!/(5!×9!) = 2002 이다. 중복을 나누지 않고 14! 로 두면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 2002` · answer_map: {x=2002}

**선지**:
- ① `2002` ← 정답
- ② `240240` ← 정답
- ③ `726485760` ← 정답
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

## 표본 154 · `wm-misc-eval-mc-5c7b8b26c6c6`

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

## 표본 155 · `wm-misc-eval-mc-4a32a4f21e42`

- 도메인: `SAME-ITEM-PERM` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.4
- 성취기준: [12직수04-01], [12확통01-01]

**문항**: 2 개의 A 와 7 개의 B, 모두 9 개의 문자를 일렬로 배열하는 경우의 수를 구하시오.

**정답**: `36`

**풀이**: 같은 것이 있는 순열이므로 9! 을 각 문자 개수의 계승 2!·7! 로 나눈다: 9!/(2!×7!) = 36 이다. 중복을 나누지 않고 9! 로 두면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 36` · answer_map: {x=36}

**선지**:
- ① `36` ← 정답
- ② `72` ← 정답
- ③ `181440` ← 정답
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

## 표본 156 · `wm-misc-eval-mc-1fe6a1044b0f`

- 도메인: `SAME-ITEM-PERM` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.6
- 성취기준: [12직수04-01], [12확통01-01]

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

## 표본 157 · `wm-misc-eval-mc-9f73cbdd0acf`

- 도메인: `SCALE-AREA` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.9
- 성취기준: [9수02-07], [9수03-12]

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

## 표본 158 · `wm-misc-eval-mc-cb500371b9a2`

- 도메인: `SCALE-AREA` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.6
- 성취기준: [9수02-07], [9수03-12]

**문항**: 닮음비가 23 인 두 도형의 넓이의 비를 구하시오.

**정답**: `529`

**풀이**: 넓이는 길이의 제곱에 비례하므로 닮음비 23 의 넓이의 비는 23² = 529 이다. 닮음비 23 을 그대로 넓이의 비로 답하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = 23**2` · answer_map: {x=529}

**선지**:
- ① `23` ← 오답 · 오개념 `scale-area-linear`
- ② `46` ← 정답
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

## 표본 159 · `wm-misc-eval-mc-4f27b24fb777`

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

## 표본 161 · `wm-misc-eval-mc-d10b5f798117`

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

## 표본 162 · `wm-misc-eval-mc-f821cf97f33b`

- 도메인: `SCALE-VOLUME` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.4
- 성취기준: [9수03-12]

**문항**: 닮음비가 1:20 인 두 입체도형의 부피비는 1:? 이다. ? 의 값을 구하시오.

**정답**: `8000`

**풀이**: 닮음비가 1:20 이면 부피비는 1:20³ = 1:8000 이다. 부피비를 닮음비와 같은 20 으로 두면 틀린다.

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

## 표본 163 · `wm-misc-eval-mc-12fef8dcdee5`

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

## 표본 164 · `wm-misc-eval-mc-1a77597ec643`

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

## 표본 165 · `wm-misc-eval-mc-2535859d7fba`

- 도메인: `SQRT-POS` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.9
- 성취기준: [12대수01-01], [9수01-07]

**문항**: √((-4)^2) 의 값을 구하시오.

**정답**: `4`

**풀이**: √(x²) = |x| 이므로 √((-4)²) = |-4| = 4 이다. √(x²) = x 로 오인하면 -4 가 되어 틀린다.

**verify(SymPy 입력)**: conditions: `x = sqrt((-4)**2)` · answer_map: {x=4}

**선지**:
- ① `-4` ← 오답 · 오개념 `square-root-positivity`
- ② `4` ← 정답
- ③ `8` ← 정답
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

## 표본 167 · `wm-misc-eval-mc-9649120a9a50`

- 도메인: `SQRT-POS` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.1
- 성취기준: [12대수01-01], [9수01-07]

**문항**: √((-17)^2) 의 값을 구하시오.

**정답**: `17`

**풀이**: √(x²) = |x| 이므로 √((-17)²) = |-17| = 17 이다. √(x²) = x 로 오인하면 -17 이 되어 틀린다.

**verify(SymPy 입력)**: conditions: `x = sqrt((-17)**2)` · answer_map: {x=17}

**선지**:
- ① `-17` ← 오답 · 오개념 `square-root-positivity`
- ② `17` ← 정답
- ③ `34` ← 정답
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

## 표본 169 · `wm-misc-eval-mc-f17c74af1544`

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

## 표본 170 · `wm-misc-eval-mc-ccffa72a866e`

- 도메인: `SQRT-SUM` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.5
- 성취기준: [9수01-07]

**문항**: √(81 + 144) 의 값을 구하시오.

**정답**: `15`

**풀이**: 근호 안의 합 225 는 15 의 제곱이므로 그 제곱근은 15 이다. 제곱근을 각 항에 분배하면 9 + 12 가 되어 틀린다.

**verify(SymPy 입력)**: conditions: `x = 15` · answer_map: {x=15}

**선지**:
- ① `3` ← 정답
- ② `12` ← 정답
- ③ `15` ← 정답
- ④ `21` ← 오답 · 오개념 `sqrt-distributes-over-sum`

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
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

**풀이**: 근호 안의 합 1156 은 34 의 제곱이므로 그 제곱근은 34 이다. 제곱근을 각 항에 분배하면 16 + 30 이 되어 틀린다.

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

## 표본 173 · `wm-misc-eval-mc-fbc5192e9809`

- 도메인: `SQUARE-DIFF` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.1
- 성취기준: [9수02-19]

**문항**: (4 - 2)² 의 값을 구하시오.

**정답**: `4`

**풀이**: 차의 제곱은 (4 - 2)² = 4² - 2·4·2 + 2² = 4 이다. 교차항을 누락해 4² - 2²으로 계산하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = (4 - 2)**2` · answer_map: {x=4}

**선지**:
- ① `4` ← 정답
- ② `12` ← 오답 · 오개념 `square-of-difference-no-cross`
- ③ `20` ← 정답
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

## 표본 175 · `wm-misc-eval-mc-467cf759cb91`

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

## 표본 176 · `wm-misc-eval-mc-debe3b18f20b`

- 도메인: `SQUARE-DIFF` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.6
- 성취기준: [9수02-19]

**문항**: (21 - 2)² 의 값을 구하시오.

**정답**: `361`

**풀이**: 차의 제곱은 (21 - 2)² = 21² - 2·21·2 + 2² = 361 이다. 교차항을 누락해 21² - 2²으로 계산하면 틀린다.

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

## 표본 177 · `wm-misc-eval-mc-91082d61f63b`

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

## 표본 181 · `wm-misc-eval-mc-ada431442c25`

- 도메인: `TRANSPOSE-SIGN` · 발문형식: 객관식 · 정답형식: 분수 · 난이도: 2.9
- 성취기준: [9수02-04]

**문항**: 일차방정식 x + 13 = 2 의 해를 구하시오.

**정답**: `-11`

**풀이**: 13을 이항하면 부호가 바뀌어 x = 2 - 13 = -11 이다. 이항할 때 부호를 바꾸지 않으면 2 + 13으로 틀린다.

**verify(SymPy 입력)**: conditions: `x = 2 - 13` · answer_map: {x=-11}

**선지**:
- ① `-11` ← 정답
- ② `2` ← 정답
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

## 표본 182 · `wm-misc-eval-mc-922a5e34a7a0`

- 도메인: `TRANSPOSE-SIGN` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.2
- 성취기준: [9수02-04]

**문항**: 일차방정식 x + 2 = 5 의 해를 구하시오.

**정답**: `3`

**풀이**: 2를 이항하면 부호가 바뀌어 x = 5 - 2 = 3 이다. 이항할 때 부호를 바꾸지 않으면 5 + 2로 틀린다.

**verify(SymPy 입력)**: conditions: `x = 5 - 2` · answer_map: {x=3}

**선지**:
- ① `2` ← 정답
- ② `3` ← 정답
- ③ `5` ← 정답
- ④ `7` ← 오답 · 오개념 `transpose-no-sign-change`

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
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

## 표본 184 · `wm-misc-eval-mc-0a4be774f296`

- 도메인: `TRANSPOSE-SIGN` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.6
- 성취기준: [9수02-04]

**문항**: 일차방정식 x + 2 = 10 의 해를 구하시오.

**정답**: `8`

**풀이**: 2를 이항하면 부호가 바뀌어 x = 10 - 2 = 8 이다. 이항할 때 부호를 바꾸지 않으면 10 + 2로 틀린다.

**verify(SymPy 입력)**: conditions: `x = 10 - 2` · answer_map: {x=8}

**선지**:
- ① `2` ← 정답
- ② `8` ← 정답
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

## 표본 185 · `wm-misc-eval-mc-81c901f33cc4`

- 도메인: `TRAPEZOID-AREA` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3
- 성취기준: [6수03-14]

**문항**: 윗변이 5, 아랫변이 14, 높이가 8 인 사다리꼴의 넓이를 구하시오.

**정답**: `76`

**풀이**: 사다리꼴의 넓이 = (윗변+아랫변)×높이÷2 = (5+14)×8÷2 = 76 이다. ÷2 를 빠뜨리면 152 가 되어 틀린다.

**verify(SymPy 입력)**: conditions: `x = (5+14)*8/2` · answer_map: {x=76}

**선지**:
- ① `40` ← 정답
- ② `76` ← 정답
- ③ `112` ← 정답
- ④ `152` ← 오답 · 오개념 `trapezoid-area-no-half`

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- [ ] ⑤ 오답↔오개념 귀속 타당(선지별 오개념·op-code)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 186 · `wm-misc-eval-mc-9fe9084ccfd0`

- 도메인: `TRAPEZOID-AREA` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 3.4
- 성취기준: [6수03-14]

**문항**: 윗변이 2, 아랫변이 4, 높이가 3 인 사다리꼴의 넓이를 구하시오.

**정답**: `9`

**풀이**: 사다리꼴의 넓이 = (윗변+아랫변)×높이÷2 = (2+4)×3÷2 = 9 이다. ÷2 를 빠뜨리면 18 이 되어 틀린다.

**verify(SymPy 입력)**: conditions: `x = (2+4)*3/2` · answer_map: {x=9}

**선지**:
- ① `6` ← 정답
- ② `9` ← 정답
- ③ `12` ← 정답
- ④ `18` ← 오답 · 오개념 `trapezoid-area-no-half`

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
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

## 표본 188 · `wm-misc-eval-mc-67807693ee08`

- 도메인: `TRAPEZOID-AREA` · 발문형식: 객관식 · 정답형식: 자연수 · 난이도: 2.7
- 성취기준: [6수03-14]

**문항**: 윗변이 2, 아랫변이 9, 높이가 2 인 사다리꼴의 넓이를 구하시오.

**정답**: `11`

**풀이**: 사다리꼴의 넓이 = (윗변+아랫변)×높이÷2 = (2+9)×2÷2 = 11 이다. ÷2 를 빠뜨리면 22 가 되어 틀린다.

**verify(SymPy 입력)**: conditions: `x = (2+9)*2/2` · answer_map: {x=11}

**선지**:
- ① `4` ← 정답
- ② `11` ← 정답
- ③ `18` ← 정답
- ④ `22` ← 오답 · 오개념 `trapezoid-area-no-half`

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- [ ] ⑤ 오답↔오개념 귀속 타당(선지별 오개념·op-code)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 189 · `wm-misc-eval-mc-1d264cbaae1b`

- 도메인: `TRIG-ADD` · 발문형식: 객관식 · 정답형식: 실수 · 난이도: 3.2
- 성취기준: [12미적Ⅱ-02-02]

**문항**: 두 각 A = 4π/12, B = 11π/12 에 대하여 3 sin(A + B) 의 값을 구하시오.

**정답**: `-3*sqrt(2)/2`

**풀이**: 삼각함수의 덧셈정리에 의해 sin(A + B) = sin A cos B + cos A sin B 이다. 사인을 합에 분배하여 sin A + sin B 로 계산하면 틀린 값이 된다.

**verify(SymPy 입력)**: conditions: `x = 3*sin(4*pi/12 + 11*pi/12)` · answer_map: {x=-3*sqrt(2)/2}

**선지**:
- ① `3*sqrt(3)*(-sqrt(6)/4 - sqrt(2)/4)/2` ← 정답
- ② `-3*sqrt(2)/2` ← 정답
- ③ `-3*sqrt(6)/8 - 3*sqrt(2)/8` ← 정답
- ④ `-3*sqrt(2)/4 + 3*sqrt(6)/4 + 3*sqrt(3)/2` ← 오답 · 오개념 `sine-distributes-over-sum` (op: `sine-distributed-over-sum`)

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
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

## 표본 194 · `wm-misc-eval-mc-9ca46ae6fa1f`

- 도메인: `TRIG-PERIOD` · 발문형식: 객관식 · 정답형식: 실수 · 난이도: 3.4
- 성취기준: [12대수02-02]

**문항**: 함수 y = sin(9x) 의 주기를 구하시오.

**정답**: `2*pi/9`

**풀이**: y = sin(bx) 의 주기는 2π/b 이므로 y = sin(9x) 의 주기는 2π/9 이다. 계수 9 를 무시하면 주기를 2π 로 잘못 구한다.

**verify(SymPy 입력)**: conditions: `x = 2*pi/9` · answer_map: {x=2*pi/9}

**선지**:
- ① `pi/9` ← 정답
- ② `2*pi/9` ← 정답
- ③ `2*pi` ← 오답 · 오개념 `period-of-scaled-sine`
- ④ `18*pi` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- [ ] ⑤ 오답↔오개념 귀속 타당(선지별 오개념·op-code)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 195 · `wm-misc-eval-mc-2ae7ad0ed8c7`

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

## 표본 196 · `wm-misc-eval-mc-1ac0aea74481`

- 도메인: `TRIG-PERIOD` · 발문형식: 객관식 · 정답형식: 실수 · 난이도: 2.6
- 성취기준: [12대수02-02]

**문항**: 함수 y = sin(12x) 의 주기를 구하시오.

**정답**: `pi/6`

**풀이**: y = sin(bx) 의 주기는 2π/b 이므로 y = sin(12x) 의 주기는 2π/12 이다. 계수 12 를 무시하면 주기를 2π 로 잘못 구한다.

**verify(SymPy 입력)**: conditions: `x = 2*pi/12` · answer_map: {x=pi/6}

**선지**:
- ① `pi/12` ← 정답
- ② `pi/6` ← 정답
- ③ `2*pi` ← 오답 · 오개념 `period-of-scaled-sine`
- ④ `24*pi` ← 정답

**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):
- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)
- ✓ 정확성 Tier2 — SymPy 단계 동치 (단일 답 동치)
- ✓ 위생 — 거짓 수치등식 부재
- ✓ 동등성 — 분류 게이트 통과
- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌
- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED

**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):
- [ ] ① 발문 자연스러움(한국어·수학 표기)
- [ ] ② 풀이 타당성(answer_explanation 논리)
- [ ] ③ 난이도 체감이 표기 난이도와 정합
- [ ] ④ 성취기준 귀속 타당
- [ ] ⑤ 오답↔오개념 귀속 타당(선지별 오개념·op-code)
- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)

---

## 표본 197 · `wm-misc-eval-mc-af1d8cc5ece3`

- 도메인: `VIETA-SUM` · 발문형식: 객관식 · 정답형식: 분수 · 난이도: 3.1
- 성취기준: [10공수1-02-03]

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

## 표본 198 · `wm-misc-eval-mc-eaf0bc039bfe`

- 도메인: `VIETA-SUM` · 발문형식: 객관식 · 정답형식: 분수 · 난이도: 2.6
- 성취기준: [10공수1-02-03]

**문항**: x² + 12x + 13 = 0 의 두 근의 합을 구하시오.

**정답**: `-12`

**풀이**: 근과 계수 관계로 두 근의 합은 -(일차항 계수) = -12 = -12 이다. 부호를 놓쳐 12로 답하면 틀린다.

**verify(SymPy 입력)**: conditions: `x = -12` · answer_map: {x=-12}

**선지**:
- ① `-13` ← 정답
- ② `-12` ← 정답
- ③ `12` ← 오답 · 오개념 `vieta-sign-error`
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

## 표본 199 · `wm-misc-eval-mc-5fe788a02d6e`

- 도메인: `VIETA-SUM` · 발문형식: 객관식 · 정답형식: 분수 · 난이도: 2.8
- 성취기준: [10공수1-02-03]

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
