# 문제은행 커버리지 관측 리포트 (D4) — 2026-08 재실측

> **요약**: 문제 코퍼스 **7종 2,647문**을 전량 스캔해 ① NCIC 성취기준 대비 커버율·0커버 목록
> ② `unit_code` × 난이도 밴드 분포 ③ 코퍼스별·질문형식별 분해 ④ 유형(`problem_type`) 축(S3-27)을
> 낸 **관측 리포트**.
> `ARCH-18-problem-bank-coverage-report` 산출물이며 설계 근거는
> `docs/architecture/problem_bank_gap_review.md` §3 **D4**(품질 15축 ⑫ 커버리지 잔여 공백).
>
> **exit 게이트가 아니다** — 커버율이 아무리 낮아도 CI를 빨갛게 만들지 않는다. 용도는
> `S4-01-math-k12-complete`(초·중 확장)의 **저작 우선순위 입력**이다("관측 없는 확장 금지").
>
> **재실측 사유(PB-02)**: 2026-07 최초본은 코퍼스 6종·2,667문 기준이었다. 이후
> `problem_bank_probability_finite_v0`(34문)가 신설되고 `problem_bank_rephrased_v0`가
> 483→429문으로 정리돼 코퍼스가 **7종·2,647문**으로 바뀌었는데도 이 문서는 갱신되지 않아
> "자기 도구와 모순" 상태였다(구식 6종·2,667 수치가 도구의 실측 7종·2,647과 불일치).
> 이 문서는 그 stale을 해소한 재실측본이며, CI에 커밋 산출물 JSON과의 재생성 diff 게이트가
> 새로 얹혀(`data-pipeline` 잡·코퍼스 변경 트리거) 같은 stale이 다시 조용히 쌓이지 않게 한다.
> 아울러 `Problem`↔`ProblemType` 백필(S3-27) 착지로 유형 축(§7)이 이번 재실측부터
> "스코프 밖"에서 **실측 대상**으로 승격됐다.

- **생성 도구**: `src/backend/whymath_backend/harness/problem_bank_coverage.py`
- **기계 산출물(전량)**: `docs/data/problem_bank_coverage_2026-07.json`
  (0커버 성취기준 357건 전량·79 단원 × 6 밴드 매트릭스·17종 유형 × 79단원 매트릭스·코퍼스별 분해)
- **측정일**: 2026-08-08 · **입력 스냅샷**: `data/corpus/problem_bank*/problems.jsonl`,
  `data/corpus/standards_v1/standards.json`, `data/corpus/problem_type_graph_v1/problem_types.jsonl`

---

## 0. 재현 (결정론 — 같은 입력이면 같은 바이트)

```bash
cd src/backend
python -m whymath_backend.harness.problem_bank_coverage \
    --json ../../docs/data/problem_bank_coverage_2026-07.json
```

옵션: `--corpus-root`(코퍼스 루트) · `--corpus NAME`(반복 지정) · `--standards`(성취기준 JSON) ·
`--revision`(커버율 분모 개정·기본 `2022 개정`) · `--max-zero-codes`(본문 0커버 나열 수) ·
`--problem-types`(유형 카탈로그 JSONL 경로).

**종료 코드는 0(성공) / 2(입력 오류)만**이다. 라인 파싱 실패는 §5 정직 회계에 카운트로 실리고
종료 코드를 바꾸지 않는다(같은 harness 축의 `corpus_audit_eval`은 *게이트*라 exit 1을 내지만
이 도구는 관측이라 내지 않는다 — 그 차이를 모듈 docstring이 명시).

CI(`.github/workflows/ci.yml` `data-pipeline` 잡)는 코퍼스 변경 시(`needs.changes.outputs.corpus
== 'true'`) 이 명령을 재실행해 산출물을 `docs/data/problem_bank_coverage_2026-07.json`과 diff한다
— 어긋나면 실패(이 문서가 stale임을 CI가 구조적으로 잡는다).

---

## 1. 성취기준 대장 실측 — "895"의 정확한 의미

| 항목 | 실측값 |
|---|---:|
| `standards.json` 레코드 수 | **895** |
| 고유 고시코드 수(개정 합집합) | **742** |
| 2022 개정 고유 코드 | **435** |
| 2015 개정 고유 코드 | **460** |

> 태스크·갭 리뷰가 말하는 "성취기준 895"는 **레코드 수**이고, 그중 153개 코드가 2015·2022 개정
> 양쪽에 중복 등재돼 있다(`norm_id`만 개정 접두로 다름). 커버율 분모를 895로 잡으면 같은 코드를
> 두 번 세는 이중 계산이 되므로, 이 리포트는 분모를 **하나의 개정 안의 고유 코드 집합**으로 잡는다.
> 문제 코퍼스는 전량 `curriculum_version = 2022_REVISION`이라 기본 분모는 **2022 개정 435**다.
> (이 대장·분모 구조는 코퍼스 종수·문항 수 변화와 무관 — 재실측에도 그대로 유지된다.)

---

## 2. 커버리지 핵심 수치 (분모 = 2022 개정 435 코드)

| 지표 | 값 |
|---|---:|
| 문항 총계 | **2,647** |
| 커버된 성취기준 코드 | **78 / 435 (17.9%)** |
| 0커버 성취기준 코드 | **357** |
| 코퍼스에 등장한 성취기준 코드 종수 | 78 (전부 2022 개정 실재 코드) |

### 2.1 학교급별 — 초등 7.4%가 최대 공백

| 학교급 | 커버 | 분모 | 커버율 | 0커버 |
|---|---:|---:|---:|---:|
| 초등학교 | 9 | 121 | **7.4%** | 112 |
| 고등학교 | 46 | 254 | 18.1% | 208 |
| 중학교 | 23 | 60 | **38.3%** | 37 |

### 2.2 영역별 — 0커버 상위 (분모=2022 개정 코드 수)

| 영역 | 커버 | 분모 | 커버율 | 0커버 |
|---|---:|---:|---:|---:|
| 도형과 측정 | 12 | 81 | 14.8% | **69** |
| 수와 연산 | 7 | 55 | 12.7% | **48** |
| 변화와 관계 | 12 | 37 | 32.4% | 25 |
| 자료와 가능성 | 4 | 26 | 15.4% | 22 |
| 방정식과 부등식 | 5 | 20 | 25.0% | 15 |
| 집합과 명제 | 0 | 13 | **0.0%** | 13 |
| 도형의 방정식 | 4 | 14 | 28.6% | 10 |
| 미분법 | 2 | 11 | 18.2% | 9 |
| 경우의 수 | 2 | 9 | 22.2% | 7 |
| 적분법 | 0 | 7 | **0.0%** | 7 |

> 커버율 0%인 영역은 **24개**다: 집합과 명제·적분법·통계·적분·함수와 경제·수와 경제·이차곡선·
> 행렬·자료의 분석·자료의 수집과 정리·통계와 통계적 문제·통계적 탐구·과제 탐구의 방법과·
> 과제 탐구의 이해·과제탐구의 실행·미분과 경제·사회와 수학·예술과 수학·환경과 수학·
> 이미지 데이터 처리·인공지능과 빅데이터·인공지능과 수학·텍스트 데이터 처리·행렬과 경제
> (융합·진로선택 과목군 다수). 전량은 JSON `coverage_by_domain`.

### 2.3 커버된 코드도 극단적으로 편중

| 성취기준 | 문항 |
|---|---:|
| `[9수02-20]` | **379** |
| `[12미적Ⅰ-02-07]` | 269 |
| `[12미적Ⅰ-02-01]` | 176 |
| `[12대수03-02]` | 165 |
| `[9수02-08]` | 120 |

상위 5개 코드가 **1,109문(41.9%)**을 차지한다. 커버된 78개 코드의 중앙값은 24문(오개념 MC·개념형
배치가 코드당 24문으로 균일 생성된 결과 — 재실측에도 그대로 유지).

---

## 3. 단원(`unit_code`) × 난이도 밴드

### 3.1 밴드 정의 — 기존 정본에서 유도(신설 아님)

`difficulty_overall`(1.0~5.0)의 밴드 경계는 저장소의 기존 두 정본에서 유도했다.

| 밴드 | 구간 | 근거 |
|---|---|---|
| 인지(awareness) | [1.0, 2.0) | `l6/school_progress/gating.py:_DEPTH_TARGET_DIFFICULTY` 앵커 1.5 |
| 절차(procedural) | [2.0, 3.0) | 동 앵커 2.5 |
| 개념(conceptual) | [3.0, 4.0) | 동 앵커 3.5 |
| 숙달(mastery) | [4.0, 5.0] | 동 앵커 4.5 · 하단 4.0 = `l6/gifted/gating.py:GIFTED_MIN_DIFFICULTY` |
| 미평가 | `difficulty_overall` 없음 | 값 없음 ≠ 낮음(정직 회계) |
| 범위밖 | [1.0, 5.0] 밖 | 스키마 이탈값을 밴드로 뭉개지 않음 |

경계는 `RequiredDepth` 앵커(1.5/2.5/3.5/4.5)의 인접 중점(2.0·3.0·4.0)이며, 최상단 4.0은 영재
트랙 심화 하한과 정확히 일치한다. 이 유도 관계는
`tests/backend/harness/test_problem_bank_coverage.py::test_difficulty_bands_derive_from_l6_anchors`가
실제 L6 상수를 import해 동결한다(L6 상수가 바뀌면 테스트가 깨져 함께 갱신하도록 강제).

### 3.2 밴드 총계 (문항 기준)

| 인지 [1.0,2.0) | 절차 [2.0,3.0) | 개념 [3.0,4.0) | 숙달 [4.0,5.0] | 미평가 | 범위밖 |
|---:|---:|---:|---:|---:|---:|
| 211 (8.0%) | 1,022 (38.6%) | 1,252 (47.3%) | 162 (6.1%) | 0 | 0 |

중간 두 밴드(절차·개념)에 **85.9%**가 몰려 있다. 숙달(4.0+) 162문 중 120문이 `killer_v0`,
42문이 `generated_v0`(21)+`rephrased_v0`(21)이다.

### 3.3 단원 편중

- 단원 수 **79종**(재실측 이전 77종에서 +2 — `probability_finite_v0` 신설이 `PROB-FINITE-ENUM`·
  `COUNT-FINITE-ENUM` 2단원을 새로 추가). 단원 귀속 합계 2,647 = 문항 수 → 현 코퍼스는
  **문항당 정확히 1 단원**(다단원 태깅 0건 — 도구는 다단원을 각 단원에 1씩 세도록 이미 지원).
- 상위 3단원이 574문(21.7%): `QUAD-EQ` 334 · `ARITH-SEQ` 120 · `POLY-ROOT` 120.
- 60개 단원이 정확히 24문(오개념 MC/개념형 균일 배치), `QUAD-FN`은 1문(최소).
- 밴드 축이 단원별로 **극단적으로 좁다**: `POLY-ROOT` 120문 전부 숙달, `IND-SEQ`·`TRIG-VAL` 전부
  인지, 60개 균일 단원은 전부 절차/개념 2밴드에만 존재. **한 단원을 난이도 사다리로 관통하는
  계열이 없다**(gap review D8 "난이도 변형 부재"의 관측 증거 — 재실측에도 재확인).

전량 매트릭스(79행 × 6밴드)는 CLI 출력 §2 및 JSON `unit_band_matrix`.

---

## 4. 코퍼스별·질문형식별 분해

| 코퍼스 | 문항 | 인지 | 절차 | 개념 | 숙달 | 객관식 | 단답형 |
|---|---:|---:|---:|---:|---:|---:|---:|
| `problem_bank_v1` | 4 | 0 | 4 | 0 | 0 | 1 | 3 |
| `problem_bank_generated_v0` | 620 | 129 | 234 | 236 | 21 | 95 | 525 |
| `problem_bank_rephrased_v0` | 429 | 82 | 147 | 179 | 21 | 80 | 349 |
| `problem_bank_misconception_mc_v0` | 1,080 | 0 | 475 | 605 | 0 | 1,080 | 0 |
| `problem_bank_conceptual_v0` | 360 | 0 | 136 | 224 | 0 | 360 | 0 |
| `problem_bank_killer_v0` | 120 | 0 | 0 | 0 | 120 | 0 | 120 |
| `problem_bank_probability_finite_v0` | 34 | 0 | 26 | 8 | 0 | 0 | 34 |
| **합계** | **2,647** | 211 | 1,022 | 1,252 | 162 | 1,616 | 1,031 |

- 질문형식은 **객관식·단답형 2종뿐**이다. 스키마 `QuestionFormat` 10종 중 합답형·서술형·
  객관식진단 등 8종은 코퍼스 0건(= 데이터 없음이 아니라 *관측된 0*).
- 객관식은 사실상 오개념 MC(1,080)+개념형(360)이 전부이며, 단답형은 스켈레톤 생성 계열+신설
  `probability_finite_v0`(34, 전량 단답형)다.

---

## 5. 정직 회계 (누락·미지 값) — 유형 축만 부분 미태깅

| 항목 | 건수 |
|---|---:|
| 파싱 실패 라인 | 0 |
| 성취기준 코드 없는 문항 | 0 |
| 단원 코드 없는 문항 | 0 |
| 난이도 없는 문항 | 0 |
| 질문형식 없는 문항 | 0 |
| 유형(`problem_type`) 없는 문항 | **429** |
| 대장에 없는 성취기준 코드(종) | 0 |
| 다른 개정(2015)에만 있는 코드(종) | 0 |
| 코퍼스 상태 `데이터없음`(파일 부재) | 0 (7종 전부 `적재됨`) |

성취기준·단원·난이도·질문형식 4축은 **전 항목 0**이라 §2~§4 수치는 액면 그대로 읽어도 된다.
유형(`problem_type`) 축만 429문(전량 `problem_bank_rephrased_v0`)이 S3-27 백필 대상 밖이라
미태깅 상태다 — §7에서 이 부분성을 그대로 드러낸다(숨기지 않는다).

---

## 6. 저작 우선순위 제언 (S4-01 입력)

관측이 가리키는 순서 — *결정은 S4-01 소관이며 이 문서는 근거만 제공한다*.

1. **초등 121 코드 중 112 0커버(7.4% 커버)** — 규모 최대 공백. 단 `S4-01`은 "초·중 확장"이므로
   중학교(37 0커버·이미 38.3% 커버)보다 초등이 압도적으로 크다.
2. **영역 0% 블록 우선** — 커버율 0% 영역이 **24개**다. 집합과 명제(13)·경우의 수(7)·
   적분+적분법(13)·통계 계열(다수)은 *한 문항도 없다*. 커버 1문만 넣어도 "0커버 영역"이 사라지는
   저비용·고가시성 구간.
3. **난이도 사다리 관통 부재 해소** — 단원 대부분이 1~2밴드에만 존재한다. 신규 저작 시 같은
   단원의 인지~숙달 계열화를 함께 요구하면 D8(난이도 변형)의 공급 경로도 열린다.
4. **`[9수02-20]` 379문 과잉** — 추가 저작을 이 코드에 더 얹는 것은 한계효용이 낮다.
5. **질문형식 다양화** — 합답형·서술형 0건. 수능 합답형(ㄱㄴㄷ)은 페르소나 A의 실제 시험 형식이다.
6. **유형(`problem_type`) 미태깅 429문 해소** — `problem_bank_rephrased_v0`가 S3-27 백필 대상
   밖이다. §7의 9/17종 0커버 유형(존재성 판정·서술형 증명·word problem 모델링 등 고차 유형)이
   실제로 0인지, 태깅 누락 때문인지 이 백필을 마쳐야 구분된다.

---

## 7. 유형(`problem_type`) × 단원 분포 (S3-27 — 이번 재실측부터 실측 대상)

> 2026-07 최초본은 이 축을 "전 문항 미태깅이라 전 칸이 0"이라는 이유로 스코프 밖으로 뒀다.
> `Problem`↔`ProblemType` 백필(`harness/problem_type_backfill.py`)이 착지해 2,647건 중 **2,218건
> (83.8%)**이 결정론 태깅됐다 — 이제 의미 있는 축이라 정식으로 편입한다.

| 유형(`problem_type_id`) | 문항 |
|---|---:|
| `ptype.evaluate-expression` | 1,322 |
| `ptype.solve-for-unknown` | 308 |
| `ptype.verify-claim` | 264 |
| `ptype.optimize-extremum` | 140 |
| `ptype.count-solutions` | 97 |
| `ptype.enumerate-cases` | 56 |
| `ptype.generalize-pattern` | 30 |
| `ptype.determine-coefficient` | 1 |
| **태깅 합계** | **2,218** |
| 미태깅(`problems_without_problem_type`) | 429 |

### 7.1 0커버 유형 — 9/17종

`ptype.condition-satisfaction` · `ptype.construct-object` · `ptype.existence-decision` ·
`ptype.infer-relationship` · `ptype.model-word-problem` · `ptype.optimize-constrained` ·
`ptype.prove-statement` · `ptype.sketch-graph` · `ptype.transform-expression`

이 목록이 `ai_content_generation_gap_review.md` D3 §4-① 트리거의 발화 계측기다. 존재성 판정·
증명·word-problem 모델링·그래프 스케치 등 **고차 추론 유형이 통째로 0**이라는 점이 눈에 띈다 —
카탈로그(`data/corpus/problem_type_graph_v1/problem_types.jsonl`) 17종 × 79단원 전량 매트릭스는
JSON `problem_types.type_unit_matrix`.

---

## 8. 관련 문서

- 설계·갭 정본: `docs/architecture/problem_bank_gap_review.md` §3 D4
- 유형(S3-27) 편입 정본: `docs/architecture/ai_content_generation_gap_review.md` D3 ·
  `docs/architecture/problem_bank_gap_review.md` §5-③
- 성취기준 대장 데이터 카드: `docs/data/achievement_standards_v1.md`
- 검증 권위 기준: `docs/standards/superhuman_verification_standard.md`
- 게이트형 자매 도구(대비): `src/backend/whymath_backend/harness/corpus_audit_eval.py`
- 배선 태스크: `PB-02-declaration-wiring-reconciliation`(S6 상시성 글롭 전환 + 이 리포트의
  재생성-diff CI 게이트)
