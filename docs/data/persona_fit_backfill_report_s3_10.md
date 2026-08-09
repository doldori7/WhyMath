# persona_fit 백필 실측 리포트 (S3-10 — PB-01 회수 재실행)

> **한 줄**: 문제은행 7종(2,647건)의 `persona_fit`이 전부 `{}`였다 — L6 게이팅 모드의
> persona_fit 폴백 경로가 항상 공집합으로 죽어 있었다. 결정론 규칙
> (`l1/problem_bank/persona_fit_rules.py`)으로 전 2,647건을 백필하고, 실제 L6 게이팅 함수
> (retake·suneung·school_progress 3곳)로 전/후 적격 후보 수를 실측했다.

## 0. 경위

이 백필은 원래 미병합 브랜치(`claude/s3-10-persona-fit-2xk548`, 커밋 `fc7c9663`)에서
완료됐던 작업이다. `fc7c9663`은 main과 이력이 갈라져 있어(공통 조상 없음) 코퍼스 jsonl을
그대로 병합할 수 없었으므로, **순수 코드(규칙·CLI·테스트 5개)만 바이트 동일 포팅**하고
main 현재 코퍼스(2,647건) 위에서 백필을 **직접 재실행**했다(재적용이 아니라 재계산 —
`derive_persona_fit`은 순수 함수·부수효과 없음이므로 같은 입력 필드에 대해 항상 같은 출력을
낸다).

## 1. 백필 실행 결과 (2026-08-07, PB-01 재실행)

```
python -m whymath_backend.harness.problem_corpus_persona_fit_backfill --all
```

| 코퍼스 | 총건 | 채움 | 이미 보유 | 밴드 분포 |
|---|---:|---:|---:|---|
| conceptual_v0 | 360 | 360 | 0 | CORE 136 · MID_HIGH 207 · HIGH 17 |
| generated_v0 | 620 | 620 | 0 | BASIC 129 · CORE 234 · MID_HIGH 139 · HIGH 97 · KILLER 21 |
| killer_v0 | 120 | 120 | 0 | KILLER 120 |
| misconception_mc_v0 | 1,080 | 1,080 | 0 | CORE 475 · MID_HIGH 511 · HIGH 94 |
| rephrased_v0 | 429 | 429 | 0 | BASIC 82 · CORE 147 · MID_HIGH 112 · HIGH 67 · KILLER 21 |
| problem_bank_v1 | 4 | 4 | 0 | CORE 4 |
| probability_finite_v0 | 34 | 34 | 0 | CORE 26 · MID_HIGH 8 |
| **합계** | **2,647** | **2,647** | **0** | |

**바이트 결정론 검증**: 백필을 연속 2회 실행 — 1회차 `filled=2,647`(전건), 2회차
`already_set=2,647·filled=0`. 두 실행 사이 7개 corpus jsonl 파일의 MD5 해시가 전부 동일
(재실행 동일 출력 바이트 결정론 확인, `md5sum` 직접 대조). 계산 근거(문항별 밴드·가산
구성요소)는 `docs/data/persona_fit_backfill_audit/<코퍼스 파일명>.jsonl`에 문항당 1줄
(총 2,647줄)로 남겼다.

**단위 테스트**: `test_persona_fit_rules.py` 14건, `test_problem_corpus_persona_fit_backfill.py`
+ `test_persona_fit_backfill_corpus_coverage.py`(실 코퍼스 커버리지·L6 폴백 양수 검증) 14건 —
백필 재실행 후 전부 통과(§5 참조). `test_no_empty_persona_fit_in_real_corpus`는 백필 전 실행
시 2,647건 미채움으로 실패했고(회귀 검출 확인), 백필 후 재실행에서 통과로 전환됨을 직접 확인.

## 2. L6 3곳 persona_fit 적격 후보 수 — 전(0) → 후(N)

측정 방법: 코퍼스를 `Problem`으로 로드해 (a) `persona_fit={}`로 강제한 사본(백필 전 상태
재현) (b) 백필 후 실제 코퍼스, 양쪽에 대해 실제 L6 게이팅 함수(`l6/retake/gating.py`,
`l6/suneung/gating.py`, `l6/school_progress/gating.py`, 단일 권위)로 적격 카운트. `persona_fit`
폴백 경로만 격리하기 위해 각 게이트의 대체 신호(재수전용형 라벨·exam_type·signature_patterns·
진도 인자)는 배제했다.

### `l6/retake/gating.py:106` — `is_retake_eligible` (RT 재수 트랙)

| 페르소나 | persona_fit 폴백 적격(전→후) |
|---|---|
| B_자사고N수 | 0 → 2,647 |
| C_검정고시N수 | 0 → 2,647 |

### `l6/suneung/gating.py:134` — `is_suneung_eligible` (수능 모드)

| 페르소나 | persona_fit 폴백 적격(전→후) |
|---|---|
| A_일반고고3 | 0 → 2,647 |
| B_자사고N수 | 0 → 2,647 |
| C_검정고시N수 | 0 → 2,647 |

A/B/C 전 밴드의 기본 적합도가 0.5 이상으로 설계돼(정시 3개 페르소나 모두 코퍼스 전체가
학습 대상이라는 판단) 전건 통과한다.

### `l6/school_progress/gating.py:206` — `is_school_progress_eligible` (학교진도 모드)

| 페르소나 | persona_fit 폴백 적격(전→후) |
|---|---|
| A_일반고고3 | 0 → 2,647 |
| D_학종고2 | 0 → 2,436 |

D는 BASIC 밴드(난이도 <2.0)에서 기본 적합도 0.40(+질문형식 가산 최대 0.05=0.45)이 임계
0.5에 못 미쳐 제외된다 — 격차(2,647−2,436=211)는 코퍼스 전체 BASIC 밴드 건수(129+82=211,
generated_v0+rephrased_v0)와 정확히 일치한다(의도된 설계 — 학종 페르소나는 순수 기초 확인
문항보다 변별 구간 이상 콘텐츠가 탐구 소재로 유용하다는 모듈 docstring 판단이 실측에
그대로 나타남).

**3곳 전부 전0 → 후N>0 확인** — L6 persona_fit 폴백 경로가 죽은 상태에서 소생했다.

## 3. `api/me.py` 정정

`fc7c9663`의 diff(7줄, `recommend_next_problem` 근처 docstring — "별도 태스크(S3-13)로 분리"
문구)를 포팅하되, 원문의 `S3-13` 참조를 이번에 새로 발급한 `S3-17-suneung-prefilter-persona-fit-widen`
으로 정정해 적용했다(main의 `S3-13`은 이미 다른 완료 태스크 — 데모 문제 풀 확장 — 이므로
ID 충돌 회피).

## 4. 정직한 공백

- 영재(gifted)·사고력(thinking) 모드는 이 백필로 열리지 않는다 — `bloom_level`·
  `is_cross_unit` 태깅이 코퍼스에 부재하기 때문(persona_fit과 무관한 별도 병목). 이 태스크
  범위 밖.
- `populate_problem_bank` 실DB 재적재는 이 세션 sandbox에 Postgres가 없어 **미실행** —
  명령(`python -m whymath_backend.l1.problem_bank.populate --problems <corpus>/problems.jsonl`,
  7개 코퍼스 각각)만 준비.
- `S3-17`(수능 SQL 사전필터 persona_fit 조건 확장, 원 커밋 `a20c851`)은 **등록만** 했고
  구현은 하지 않았다(범위 밖 — 엔드포인트 실트래픽·성능 영향을 함께 봐야 하는 별개 변경).

## 5. 관련

- 규칙 정본: `src/backend/whymath_backend/l1/problem_bank/persona_fit_rules.py`
- 백필 CLI: `src/backend/whymath_backend/harness/problem_corpus_persona_fit_backfill.py`
- 계산 근거 감사 로그: `docs/data/persona_fit_backfill_audit/*.jsonl`
- 회귀 동결: `tests/backend/l1/problem_bank/test_persona_fit_rules.py` ·
  `tests/backend/harness/test_problem_corpus_persona_fit_backfill.py` ·
  `tests/backend/harness/test_persona_fit_backfill_corpus_coverage.py`
- 정본 커밋(포팅 출처): `fc7c9663`(브랜치 `claude/s3-10-persona-fit-2xk548`)
- 회수 배경: `docs/architecture/problem_bank_gap_review_r2.md` §0-① · §3 R1

---

# 부록 — ARCH-19 답 분포 편향(⑧)·LaTeX 게이트(⑩) 회수 (PB-01 §③)

정본 커밋 `5f2a8c0`(브랜치 `claude/education-os-architecture-mr0fbq`)에서 신규 파일 3개
(`l3/equivalent/latex_gate.py`·`l1/problem_bank/answer_distribution.py`·
`harness/answer_distribution_battle.py`) + 테스트 3개를 바이트 동일 포팅하고, 기존 파일 2개
(`acceptance.py`·`defect_seeder.py`)·테스트 2개(`test_defect_detection_eval.py`·
`test_acceptance.py`)는 `git apply`로 클린 패치했다(컨텍스트 충돌 0건). 후속 커밋 `974e933`
(S4-14 차단 — 무관)은 가져오지 않았다.

## A. 단위 테스트

포팅한 6개 파일(신규 3 + 패치 2 + 부속 테스트) 관련 테스트 전부 통과:

```
tests/backend/l3/equivalent/test_latex_gate.py
tests/backend/l1/problem_bank/test_answer_distribution.py
tests/backend/harness/test_answer_distribution_battle.py
tests/backend/harness/test_defect_detection_eval.py   (6종→7종 결함류 재계산 반영)
tests/backend/l3/equivalent/test_acceptance.py         (신규 케이스)
```
→ **93 passed** (hermetic, 소요 23.85초).

## B. ⑧ 답 분포 편향 — 실 코퍼스 재스캔 (2026-08-07)

```
python -m whymath_backend.harness.answer_distribution_battle
```

```
객관식 문항: 1,616건(선택지 4지) · malformed 0건
  위치 0: 509건 (기대 404.0)   위치 1: 405건 (기대 404.0)
  위치 2: 346건 (기대 404.0)   위치 3: 356건 (기대 404.0)
카이제곱 통계량: 41.3218 · p-value: 5.58819e-09
판정(α=0.05): 쏠림 검출(귀무가설 기각)
```

**재현 확인**: 고립 브랜치 실측(1,631문·p=1.07e-8)과 동일한 정성적 패턴(위치 0 과다·극히
유의한 p-value)이 main 현재 코퍼스(1,616문·p=5.59e-9)에서도 재현된다. 문항 수 차이(1,631→
1,616)는 이 사이 진행된 다른 코퍼스 변경(결함 조치 등, ARCH-19와 무관) 때문으로 보인다.
**원인 규명은 이 태스크 범위 밖** — 별도 후속 태스크로 남긴다(이 리포트는 재현 여부·p-value
실측만 기록).

강등전(결함 주입) 자체 검증도 재실행했다:

```
python -m whymath_backend.harness.answer_distribution_battle --battle \
  --min-detection-lower 0.9 --max-false-alarm-upper 0.1
```

```
쏠림 배치 검출   : 295/300 (점추정 0.983 · 95% Wilson 하한 0.966)
균형 배치 오검출 : 16/300  (95% Wilson 상한 0.079)
exit 0 (검출 하한 0.9 이상·오검출 상한 0.1 이하 — 게이트 통과)
```

## C. ⑩ LaTeX/문법 게이트

`latex_gate.py`(균형 검사 — `$`·중괄호·`\left`/`\right`)가 `acceptance.py`의 6번째 게이트
(`latex_ok`)로 배선됐고, `defect_seeder.py`에 `broken_latex` 7번째 결함류가 추가됐음을
`test_defect_detection_eval.py`(6종→7종 균형 재계산 반영) 통과로 확인했다.

## D. 정직한 잔여

- 원 커밋(`5f2a8c0`)이 기록한 mypy --strict·lint-imports·실PG통합 235건·전체 스위트 7,725건은
  이 회수 세션에서 재현하지 못했다(sandbox에 Postgres·완전한 CI 환경 없음) — 이 세션이 새로
  포팅/패치한 부분은 hermetic pytest(93건)로만 검증했다.
- 답 위치 쏠림의 근본 원인 규명은 하지 않았다(지시 범위 밖) — 재현 여부·p-value만 실측.
