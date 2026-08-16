# S4-16 잔여 축 교차검증 v4 설계 — 결함별 적대적 검증기

> **상태**: 설계 제안 (구현 전)  
> **배경**: 2026-08-15, OpenRouter `qwen/qwen3.8-max` v3 반복 실행 결과에서 WhyMath 잔여 축 검출 성능이 낮게 측정됨.  
> **핵심 판단**: 성능 저하의 주요 원인은 모델 세대가 아니라 **"문제를 푸는 solver"로 LLM을 사용한 현재 검증 프로토콜**에 있음.

---

## 1. v3 측정 결과 요약

`--sample-n 5 --repeat-runs 5`로 측정한 `qwen/qwen3.8-max` 결과:

| 항목 | 결과 | 평가 |
| --- | ---: | --- |
| 전체 결함 검출률 | 49.12% | ❌ 낮음 |
| 최악 95% 하한 | 20.16% | ❌ 매우 낮음 |
| 무결함 오검출 | 21.00% | ⚠️ 높음 |
| 최악 오검출 상한 | 64.38% | ❌ 불안정 |
| 판정불가율 | 23% | ⚠️ 높음 |
| `missing_condition` | 18% | ❌ 매우 약함 |
| `unstated_equiprobability` | 78% | △ 비교적 좋음 |
| `ambiguous_wording` | 100% | ○ 좋음 |
| `multiple_valid_answers` | 4% | ❌ 사실상 실패 |

`EXIT=0`은 `--max-false-alarm-upper 0.9` 임시 기준을 만족한 것이지, 모델이 production-ready 검출기임을 의미하지 않음.

---

## 2. 현재 설계의 한계

### 2.1 관점이 결함 유형에 무차별적임

현재 `l3.cross_verify`는 3개 **generic** 관점을 사용:

1. `independent_reconstruction` — 발문만 보고 스스로 센다.
2. `adversarial_falsification` — 발문+답을 주고 결함을 찾는다.
3. `model_grounding` — 발문+형식모델을 비교한다.

이 관점들은 **어떤 결함이 있는지 모른 채** "잘못된 게 있나?"고 묻는 형태.  
결과적으로 모델은 훈련된 방향인 **"주어진 조건으로 답을 구하기"(solver)** 에 가까운 사고를 하게 됨.

### 2.2 Solver vs Adversarial Verifier

| | 일반 수학 LLM | WhyMath defect detector |
| --- | --- | --- |
| 목표 | 주어진 조건에서 정답 산출 | 주어진 조건의 빈틈·대안 탐색 |
| 사고 방향 | 정답 도출 | 반례(counterexample) 생성 |
| 결함 발견 | 부산물 | 핵심 목표 |

현재 프롬프트는 모델에게 "결함을 찾아라"고 요청하지만, **구체적인 adversarial procedure**를 제시하지 않음.

### 2.3 `missing_condition`과 `multiple_valid_answers`에서의 실패 원인

#### `missing_condition` (18%)

- 변조: "서로 구별되는 " 제거
- 모델은 "이 조건이 없어도 답을 구할 수 있는가?"로 판단
- 주사위 합 문제에서 "서로 구별"이 빠져도 합 7의 확률은 동일 → solver 관점에서 "문제없음"
- 하지만 WhyMath는 "학생이 다른 표본공간을 가정할 수 있는가?"를 봐야 함
- 모델이 **필요조건(necessary conditions) 체크리스트**를 만들어 명시 여부를 비교하지 않음

#### `multiple_valid_answers` (4%)

- 변조: "동시에" 제거 → 순서/복원 여부에 따라 답이 달라짐
- 모델은 대표적인 답 1개를 찾아서 끝냄
- "정답 A 외에 다른 해가 가능한가?"를 반증적으로 탐색하지 않음
- Counterexample generation 절차 없음

---

## 3. v4 설계 원칙

### 원칙 1: Defect-specific verification

결함 유형별로 **전용 검증 관점**을 둔다.  
4개 결함류(`missing_condition`, `unstated_equiprobability`, `ambiguous_wording`, `multiple_valid_answers`)에 대해 각각 최적화된 adversarial procedure를 실행.

### 원칙 2: Solver 금지, adversarial verifier만 사용

모든 전용 관점은 "답을 구하라"가 아니라 **"왜 이 문항이 잘못됐는지 증명하라"**는 절차여야 함.

### 원칙 3: 관점 수 K≥3 유지

결함류별로 최소 3개의 독립 관점(원리·프롬프트·가시 필드가 모두 다름)을 유지.  
기존 `_assert_independent` 메커니즘을 그대로 활용.

### 원칙 4: 기계 판정 우선

수치/동치 판정은 가능한 한 SymPy/전수 열거로 처리하고, LLM은 **명시적 절차의 실행**과 **서술적 근거**만 제공.

---

## 4. 결함류별 전용 관점 설계

### 4.1 `missing_condition` — 필요조건 체크리스트

**목표**: 문제를 유일하게 해결하기 위해 필요한 모든 조건이 명시되어 있는지 확인.

**절차**:
1. 모델은 문제를 읽고 필요조건 후보를 나열
   - 개체 구별 여부
   - 동시/순차 행위 여부
   - 복원/비복원 여부
   - 등확률 가정
   - 집계/범위/횟수 정의
2. 각 필요조건이 문항에 명시되어 있는지 yes/no로 표시
3. 명시되지 않은 조건 중, 답에 영향을 주는 것이 있으면 defect

**가시 필드**: `question_text`만.

**출력 JSON 예시**:
```json
{
  "necessary_conditions": [
    {"condition": "주사위가 서로 구별되는지", "explicit": false, "affects_answer": true}
  ],
  "verdict": "defect",
  "defect_class": "missing_condition",
  "reason": "..."
}
```

### 4.2 `unstated_equiprobability` — 등확률 가정 분리

**목표**: "각 결과가 같은 가능성으로 나온다"는 가정이 명시적/암묵적인지 구분.

**절차**:
1. 문제에서 등확률 관련 문구("가능성이 같을 때", "공정한", "무작위로") 추출
2. 등확률 가정이 **확률 계산에 직접 필요한지** 확인
3. 문구가 없고 계산에 필요하면 defect
4. "무작위", "임의로" 등의 맥락이 등확률을 정당화하는지 판단

**가시 필드**: `question_text`만.

### 4.3 `ambiguous_wording` — 현재 관점 유지

현재 `adversarial_falsification`의 일부가 이미 이 역할을 수행.  
단, v4에서는 **문장의 두 가지 이상 합리적 해석**을 명시적으로 생성하도록 절차화.

**출력 JSON 예시**:
```json
{
  "interpretations": [
    {"reading": "...", "answer": "1/3"},
    {"reading": "...", "answer": "2/3"}
  ],
  "verdict": "defect",
  "defect_class": "ambiguous_wording",
  "reason": "..."
}
```

### 4.4 `multiple_valid_answers` — 반례 생성

**목표**: 주어진 정답 외에 다른 합리적 답을 실제로 만들어내는지 확인.

**절차**:
1. 주어진 조건에서 합리적 해석 1개를 선택 → 정답 A 계산
2. **조건 하나를 합리적으로 다르게 해석** → 정답 B 탐색
   - "동시에" → "순서대로"
   - "복원" → "비복원"
   - "서로 구별" → "구별 안 함"
3. SymPy/전수 열거로 B가 실제로 존재하는지 검증
4. A ≠ B이면 defect

**가시 필드**: `question_text`, `answer`.

**출력 JSON 예시**:
```json
{
  "primary_answer": "1/3",
  "alternative_assumption": "순서대로 뽑는다면",
  "alternative_answer": "2/5",
  "verdict": "defect",
  "defect_class": "multiple_valid_answers",
  "reason": "..."
}
```

---

## 5. 아키텍처 변경

### 5.1 `l3/cross_verify.py`

- `Perspective`는 이미 원리·프롬프트·가시 필드·판정 함수를 묶고 있음.
- 결함류별 `Perspective` 튜플을 추가:
  - `MISSING_CONDITION_PERSPECTIVES`
  - `UNSTATED_EQUIPROBABILITY_PERSPECTIVES`
  - `AMBIGUOUS_WORDING_PERSPECTIVES`
  - `MULTIPLE_VALID_ANSWERS_PERSPECTIVES`
- `_judge_labelled` 외에 `_judge_missing_condition`, `_judge_multiple_valid_answers` 등 추가.

### 5.2 `harness/residue_gate_demotion_battle.py`

- `run_residue_demotion_battle`에서 결함류별로 다른 `CrossVerifier` 생성
- 각 결함류는 자신의 전용 관점 세트를 사용
- aggregate 규칙은 그대로 유지(하나라도 defect → defect, 하나라도 unclear → unclear)

### 5.3 `docs/prompts/l3_cross_verify.md`

- v4 프롬프트 블록 추가
- 기존 v2 프롬프트는 유지(v3 반복 프로토콜과의 호환)

---

## 6. 구현 계획

| 단계 | 작업 | 파일 |
| --- | --- | --- |
| 1 | `missing_condition` 전용 관점 3개 구현 | `l3/cross_verify.py` |
| 2 | `multiple_valid_answers` 전용 관점 3개 구현 | `l3/cross_verify.py` |
| 3 | `unstated_equiprobability`, `ambiguous_wording` 관점 강화 | `l3/cross_verify.py` |
| 4 | v4 프롬프트 정본 작성 | `docs/prompts/l3_cross_verify.md` |
| 5 | 결함류별 verifier 구성 | `harness/residue_gate_demotion_battle.py` |
| 6 | fake verifier로 변별력 테스트 추가 | `tests/backend/harness/test_residue_gate_demotion_battle.py` |
| 7 | v3 반복 프로토콜로 재측정 | PowerShell |
| 8 | production-ready 기준 확정 | `MEMORY.md` |

---

## 7. 검증 계획

- `ambiguous_wording` 100%, `unstated_equiprobability` 78% 수준은 유지
- `missing_condition` 18% → 60% 이상 향상 목표
- `multiple_valid_answers` 4% → 50% 이상 향상 목표
- 전체 검출 하한 평균 0.30 → 0.50 이상
- 판정불가율 23% → 15% 이하

---

## 8. 리스크

- **비용 증가**: 결함류별로 별도 관점을 두면 LLM 호출 수가 4배로 늘어날 수 있음.  
  → `--sample-n` 조절로 제어, OpenRouter batch endpoint 검토.
- **프롬프트 복잡도**: 관점 수가 늘어나면 독립성 검사와 유지보수 부담 증가.
- **기계 검증 의존**: `multiple_valid_answers`의 counterexample은 SymPy/전수 열거로 반드시 검증.
