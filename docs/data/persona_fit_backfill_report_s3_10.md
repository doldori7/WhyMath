# persona_fit 백필 실측 리포트 (S3-10)

> **한 줄**: 문제은행 6종(2,667건)의 `persona_fit`이 전부 `{}`였다 — L6 6개 모드의 persona_fit
> 폴백 경로가 항상 공집합으로 죽어 있었다. 결정론 규칙(`l1/problem_bank/persona_fit_rules.py`)
> 으로 전 2,667건을 백필하고, 실제 L6 게이팅 함수(단일 권위)로 전/후 적격 후보 수를 실측했다.

## 0. 백필 실행 결과 (2026-07-29)

```
python -m whymath_backend.harness.problem_corpus_persona_fit_backfill --all
```

| 코퍼스 | 총건 | 채움 | 이미 보유 | 밴드 분포 |
|---|---:|---:|---:|---|
| conceptual_v0 | 360 | 360 | 0 | CORE 133 · MID_HIGH 209 · HIGH 18 |
| generated_v0 | 620 | 620 | 0 | BASIC 129 · CORE 234 · MID_HIGH 139 · HIGH 97 · KILLER 21 |
| killer_v0 | 120 | 120 | 0 | KILLER 120 |
| misconception_mc_v0 | 1,080 | 1,080 | 0 | CORE 475 · MID_HIGH 511 · HIGH 94 |
| rephrased_v0 | 483 | 483 | 0 | BASIC 89 · CORE 167 · MID_HIGH 139 · HIGH 67 · KILLER 21 |
| problem_bank_v1 | 4 | 4 | 0 | CORE 4 |
| **합계** | **2,667** | **2,667** | **0** | |

**바이트 계약 검증**: 백필 전/후를 필드별 비교해 `persona_fit` 외 필드 변경 0건(전 2,663 v0 레코드)
확인. 재실행 시 6개 파일 전부 MD5 해시 동일(`already_set=총건·filled=0`) — 재실행 동일 출력
바이트 결정론 확인. 계산 근거(각 문항의 밴드·가산 구성요소)는
`docs/data/persona_fit_backfill_audit/<코퍼스명>.jsonl`에 문항당 1줄로 남겼다.

## 1. L6 persona_fit 적격 후보 수 — 전(0) → 후(N)

측정: 원본 백업(전부 `persona_fit={}`)과 백필 후 코퍼스를 각각 `Problem`으로 로드해, 실제 L6
게이팅 함수(`l6/_shared.persona_fit` 임계 통과·`is_*_eligible` 전체 적격)로 카운트.

### 수능(suneung) 모드 — acceptance 대상

| 페르소나 | persona_fit 임계 통과(전→후) | 전체 적격(전→후, 기출유형·시그니처 OR 포함) |
|---|---|---|
| A_일반고고3 | 0 → 2,667 | 30 → 2,667 |
| B_자사고N수 | 0 → 2,667 | 30 → 2,667 |
| C_검정고시N수 | 0 → 2,667 | 30 → 2,667 |

A/B/C 전 밴드의 기본 적합도가 0.5 이상으로 설계돼(정시 3개 페르소나 모두 이 코퍼스 전체가
학습 대상이라는 판단 — 갭 리뷰 §3 D3 근거) 전건 통과한다. **이 결과가 시사하는 것**: 현재 L6
`suneung_priority`는 `persona_fit` 크기가 아니라 `exam_authority_weight`·`signature_patterns`
존재·`difficulty_overall`로 순위를 매긴다 — 즉 `persona_fit`은 지금 *게이트(통과/차단)로만*
쓰이고 *순위*에는 아직 반영되지 않는다(L6 코드의 현재 사실이지 이 백필의 결함이 아니다).

### 학교진도(school_progress) 모드 — acceptance 대상

| 페르소나 | persona_fit 폴백(진도 정보 없음 가정, 전→후) |
|---|---|
| A_일반고고3 | 0 → 2,667 |
| D_학종고2 | 0 → 2,449 |

D는 BASIC 밴드(난이도 <2.0, 218건)에서 기본 적합도 0.40(+질문형식 가산 최대 0.05 = 0.45)이
임계 0.5에 못 미쳐 제외된다 — 218건 격차(2,667−2,449)가 정확히 BASIC 밴드 건수와 일치한다.
**의도된 결과다**: 학종(세특·자유연구) 페르소나는 순수 기초 확인 문항보다 변별 구간 이상
콘텐츠가 탐구 소재로 더 유용하다는 설계 판단(모듈 docstring)이 실측에 그대로 나타난다.

### [부가 측정] 다른 4개 모드 — 참고용(acceptance 대상 아님)

| 모드 | 페르소나 | 전→후 |
|---|---|---|
| RT(재수) | B_자사고N수 | 0 → 2,667 |
| RT(재수) | C_검정고시N수 | 0 → 2,667 |
| 메타인지(공유 코어) | A~D | 0 → 1,631 |
| 메타인지(공유 코어) | E_홈스쿨링영재 | 0 → 958 |

메타인지는 `distractor_map` 보유(1,630건)가 주신호라 persona_fit 임계와 결합해 A~D는 1,631건
(distractor_map 보유 + persona_fit≥0.5), E는 킬러·상위 밴드에서만 임계를 넘어 958건으로
갈린다 — **페르소나 간 실질적 차등**이 여기서 드러난다(suneung/RT는 전건 통과라 차등이 안 보임).

## 2. 정직한 공백 — 이 백필이 열지 못하는 것

**영재(gifted)·사고력(thinking) 모드는 여전히 0건이다.** 두 모드의 적격 조건은 `persona_fit`
*외에* 다음을 AND로 요구하는데, 코퍼스 6종 전체에서 그 필드가 **항상 부재**함을 실측했다:

| 모드 | 추가 필요 신호 | 코퍼스 실측 |
|---|---|---|
| 영재(E, `is_gifted_eligible`) | `bloom_level == CREATE` 또는 `is_cross_unit == True` | `bloom_level` 전건 None · `is_cross_unit` 전건 False |
| 사고력(D 등, `is_thinking_eligible`) | `bloom_level ∈ {ANALYZE, EVALUATE, CREATE}` | `bloom_level` 전건 None |

즉 `persona_fit`을 아무리 정교하게 채워도 이 두 모드는 **여전히 죽어 있다** — 병목은 persona_fit
이 아니라 `bloom_level`/`is_cross_unit` 태깅 부재다. 이 축의 백필은 이 태스크 범위 밖이며
(S3-10 acceptance는 suneung/school_progress만 요구), 별도 태스크 후보로 남긴다.

또한 복합 사고 시그니처 3종(`CASE_ANALYSIS_DEEP`·`GRAPH_SHAPE_INFERENCE`·`CROSS_UNIT_FUSION`)도
현 코퍼스에 **0건** — D/E의 `complex_reasoning_bonus`는 이번 백필에서 이론상으로만 존재하고
실제로 한 번도 적용되지 않았다(감사 로그로 확인 가능 — 모든 항목의 `complex_reasoning_bonus`가
빈 dict).

## 3. 관련

- 규칙 정본: `src/backend/whymath_backend/l1/problem_bank/persona_fit_rules.py`
- 백필 CLI: `src/backend/whymath_backend/harness/problem_corpus_persona_fit_backfill.py`
- 계산 근거 감사 로그: `docs/data/persona_fit_backfill_audit/*.jsonl`
- 회귀 동결: `tests/backend/l1/problem_bank/test_persona_fit_rules.py` ·
  `tests/backend/harness/test_problem_corpus_persona_fit_backfill.py`
- 갭 원본: `docs/architecture/problem_bank_gap_review.md` §3 D3
