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

## 4. 미병합 브랜치 회수 + 7번째 코퍼스 확장 (2026-07-30)

이 태스크는 원래 브랜치 `claude/education-os-architecture-mr0fbq`(커밋 `837f00c1`, 2026-07-29)
에서 완료됐으나 main에 병합되지 않은 채였다. 후속 세션이 `S3-10-persona-fit-backfill`을
새로 착수하려다 `scripts/harness/backlog.py start`의 미병합 완료 거부로 이 사실을 발견해,
새 설계 대신 **그 브랜치의 실제 산출물을 회수(포팅)**했다(규칙·CLI·테스트는 바이트 동일 포팅 —
로직 변경 0). 코퍼스 데이터는 **`persona_fit` 필드만** 그 브랜치 HEAD 값으로 병합했다(그 외
필드는 원래 코퍼스 그대로 유지 — 두 브랜치가 각자 독립적으로 진행한 다른 작업(§4.1)이 서로의
`persona_fit` 백필과 뒤섞이지 않게).

### 4.1 6종 코퍼스 총건 변경 — 이 태스크와 무관한 별도 원인

위 §0 표의 `rephrased_v0` 총건(483)이 현재 코퍼스에선 **429건**이다(−54). 원인은 이 태스크와
무관한 별도 작업 `S3-12-problem-bank-v0-defect-remediation`(rotation-1 결함 조치·2026-07-29,
main 병합 `385f576b`)이 계통 결함 조치로 코퍼스를 축소했기 때문이다 — 두 브랜치 모두 이후
main을 병합해 이 변경을 반영했다(회수 시 실측 확인: `achievement_standard_codes` 재귀속 등
페르소나 적합도 신호와 무관한 필드만 달라짐 — `difficulty_overall`·`signature_patterns`·
`question_format`·`distractor_map`(persona_fit 유도 신호 4종)은 두 브랜치 간 0건 불일치).
6종 코퍼스 현재 총건: **2,613**(=2,667−54). 재실측 시 §0 표의 `rephrased_v0` 밴드 분포도
BASIC 82·CORE 147·HIGH 67·MID_HIGH 112·KILLER 21(429건, 원 표는 483건 기준이라 참고용으로만
남긴다 — as-found 정직 기록, 원 실측을 소급 수정하지 않음).

### 4.2 신규 7번째 코퍼스 `probability_finite_v0`(34건)

`KNOWN_CORPORA`가 원 구현될 당시(6종) 존재하지 않았던 코퍼스(S4-13 확률 유한 전수형 파일럿 —
원 브랜치가 갈라진 뒤 main에 신설)를 목록에 추가하고(로직 무변경 — 대상 확장만) 같은 CLI로
백필했다:

| 코퍼스 | 총건 | 채움 | 밴드 분포 |
|---|---:|---:|---|
| probability_finite_v0 | 34 | 34 | CORE 26 · MID_HIGH 8 |

수능(A/B/C, persona_fit 임계만 격리 측정) 34/34 통과. 학교진도 폴백(A/D) 34/34 통과(BASIC
밴드 0건이라 D도 전건 통과 — §1의 "BASIC만 D 탈락" 패턴과 정합).

**7종 코퍼스 전체 총건: 2,647.** 전 레코드 `persona_fit` 비어있음 0건(회귀 테스트
`tests/backend/harness/test_persona_fit_backfill_corpus_coverage.py`가 고정) — 죽은 경로 소생이
7종 전체로 확장됐다.

### 4.3 데이터 정합성 점검 — 6종 원 실측값과의 소소한 불일치 6건, 재계산으로 해소

회수 과정에서 원 브랜치 HEAD의 `persona_fit` 값을 6종 코퍼스 전 레코드에 `derive_persona_fit`
(포팅한 그 규칙 그대로)로 재계산해 대조했다 — `conceptual_v0`에서 6건(0.9%）이 저장값과
재계산값이 불일치(다른 5종·나머지 354건은 100% 일치)했다. 대조 결과 두 쌍이 서로의 값과
정확히 맞바뀐 패턴이라(레코드 A의 저장값 = 레코드 B의 재계산값, 그 반대도 성립) 원 브랜치 쪽의
merge/rebase 과정에서 생긴 국소적 불일치로 판단된다 — 근본 원인을 그 브랜치에서 추적하지 않고,
**이 6건은 현재 코퍼스 내용에 대해 포팅된 규칙으로 즉시 재계산한 값**(= 감사 로그의 값)으로
확정했다(규칙이 단일 권위이므로 규칙 재적용이 항상 정답 — 저장값은 파생물일 뿐).

### 4.4 이 세션에서 재현하지 못한 검증

원 커밋(`837f00c1`)은 mypy --strict·ruff·black·lint-imports·**실 PostgreSQL 통합 233 passed**·
전체 스위트 7589 passed(커버리지 92.28%)·계층별 커버리지 게이트까지 검증했다고 기록했다. 이
회수 세션은 sandbox에 Postgres·완전한 CI 환경이 없어(§검증 참조) 이 중 다수를 재현하지
못했다 — 포팅한 규칙·CLI·테스트(2026-07-29 커밋 시점 검증됨)는 신뢰하되, **이 세션이 새로
변경한 부분**(7번째 코퍼스 확장·`KNOWN_CORPORA` 수정·2개 테스트 갱신·신규 커버리지 테스트
1파일·`api/me.py` docstring 포팅)은 이 세션에서 가능한 hermetic pytest로만 검증했다(정직한
잔여 — CI가 최종 판정).

- `populate_problem_bank` DB 재적재는 이 세션 sandbox에 Postgres가 없어(docker 소켓 부재·
  `DATABASE_URL` 미설정 확인) **미실행** — 명령(`python -m whymath_backend.l1.problem_bank.populate
  --problems <corpus>/problems.jsonl`, 7개 코퍼스 각각)만 준비.
- `S3-13`(원 브랜치가 분리 등재한 후속 — 수능 SQL 사전필터를 persona_fit까지 넓히는 실장) 태스크
  자체는 **포팅하지 않았다** — 그 번호가 이 저장소의 main 계열에서 이미 다른 태스크
  (`S3-13-demo-problem-pool`)에 배정돼 있어 번호 재사용 충돌이 있다(빌드 하네스 "태스크 ID 번호
  추론 배정 금지" 규칙 대상 — 재번호는 후속 세션의 `backlog.py add` 경유로 넘긴다). `api/me.py`
  docstring의 "별도 태스크(S3-13)로 분리" 문구는 원문 그대로 포팅했으므로, 실제 백로그의
  `S3-13`과는 다른 참조임에 주의(정정은 그 후속 태스크가 재등재될 때 함께 처리).
