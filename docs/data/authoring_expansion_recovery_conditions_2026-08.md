# 저작 확장 11,446문 회수 조건 — `PB-06` (2026-08)

> **범위**: 미병합 브랜치 `origin/claude/whymath-mvp-plan-architecture-trjg5x`(`c8abbc17` ·
> 2026-08-09 · trunk 대비 111커밋 · 열린 PR 없음)가 담은 저작 산출물의 **회수 조건**을 확정한 기록.
> **회수·병합은 이 문서가 하지 않는다 — Kiki 소유다.** 산출물은 *결정 입력*이다.
> **정본**: `docs/architecture/problem_bank_gap_review_r3.md` §3 G1 · `PB-06` acceptance.
> **실측 기준**: main `833f46af` · 브랜치 `c8abbc17` · 2026-08-11. 수치마다 재현 명령을 1:1로 병기한다.

## §0. 요약

**회수를 CI green으로 만드는 필요충분 작업은 하나다** — 신규 30종 각각에 최소 사이드카
(`{"pool": <ContentPool 3종 중 1>, "source_citation"|"license_notice" 중 ≥1}`)를 놓는 것.
그 외 감사 축은 이미 통과한다(레코드 `license`/`source_type` 결손 0/11,446).
**단, 사이드카를 만들어 주는 CLI는 저장소에 없다**(§3) — 현재로선 30개 손 작성이 유일한 경로다.

**그리고 사이드카만으로는 부족하다.** 이 조사에서 병합을 조용히 깨뜨리는 차단 조건 2건을
추가로 찾았다(§2 ⑵⑶) — 특히 **`S4-19`·`S4-22` ID 충돌은 git도 `validate`도 잡지 못한다.**

**커버리지 효과(Kiki 결정의 정량 입력)**: 성취기준 커버 **78 → 130 / 435**(+52 · +12.0%p),
초등 **9 → 22 / 121**, 0커버 영역 **24 → 19**. 다만 대학 미적분 600문은 대장 밖 코드를 써
분자에 **0 기여**한다(§4).

> ⚠️ **`PB-06` acceptance와 R3 §3 G1이 인용한 수치 6건이 틀렸다**(§5). 특히 ④의 기준선
> "72/435 · 초등 5/121 · 0커버 25"는 셋 다 낡았다 — 이 문서는 전부 재실측값을 쓴다.

---

## §1. 실측 대장 (acceptance ①)

### 1.1 신규 코퍼스 30종 · 11,446문

```bash
B=origin/claude/whymath-mvp-plan-architecture-trjg5x
comm -13 <(git ls-tree -d --name-only origin/main data/corpus/ | sort) \
         <(git ls-tree -d --name-only $B          data/corpus/ | sort)   # 30행(problem_bank_*)
git show $B:data/corpus/<name>/problems.jsonl | grep -c '[^[:space:]]'   # 코퍼스별 건수
```

성취기준 코드 필드는 `achievement_standard_codes`다(`ProblemRecord` 속성명 `standard_codes`와
다르므로 JSON을 직접 다룰 때 혼동 주의). `unit_codes`는 **다른 체계**이며 성취기준 대장과
조인되지 않는다.

| 코퍼스 | 문항수 | 성취기준 코드 | 사이드카 |
|---|---:|---|---|
| `problem_bank_polynomial_arithmetic_v0` | 1,500 | [10공수1-01-01] · [10기수1-01-01] · [10기수1-01-02] | **없음** |
| `problem_bank_complex_number_arithmetic_v0` | 900 | [10공수1-02-01] | **없음** |
| `problem_bank_probability_law_v0` | 724 | [12확통02-02] · [12확통02-03] · [12확통02-06] | **없음** |
| `problem_bank_elementary_gcd_lcm_v0` | 600 | [6수01-04] · [6수01-05] | **없음** |
| `problem_bank_elementary_rounding_v0` | 600 | [6수01-03] | **없음** |
| `problem_bank_linear_inequality_system_v0` | 600 | [10공수1-02-09] · [10기수1-02-07] | **없음** |
| `problem_bank_polynomial_factoring_v0` | 600 | [10공수1-01-03] · [10기수1-01-03] | **없음** |
| `problem_bank_calculus1_integral_v0` | 400 | [12미적Ⅰ-03-02] · [12미적Ⅰ-03-04] · [12미적Ⅰ-03-05] · [12미적Ⅰ-03-06] | **없음** |
| `problem_bank_coordinate_geometry_v0` | 400 | [10공수2-01-01] · [10공수2-01-02] | **없음** |
| `problem_bank_elementary_division_remainder_v0` | 400 | [4수01-07] | **없음** |
| `problem_bank_elementary_v0` | 400 | [2수01-06] | **없음** |
| `problem_bank_sample_mean_distribution_v0` | 400 | [12확통03-06] | **없음** |
| `problem_bank_university_calc1_chain_quotient_v0` | 400 | [CALC1-02-03] · [CALC1-02-04] | **없음** |
| `problem_bank_vector_operations_v0` | 400 | [12기하03-01] · [12기하03-02] | **없음** |
| `problem_bank_matrix_ops_v0` | 320 | [10공수1-04-02] | **없음** |
| `problem_bank_binomial_distribution_v0` | 300 | [12확통03-03] | **없음** |
| `problem_bank_elementary_volume_measure_v0` | 300 | [6수03-15] · [6수03-18] · [6수03-19] | **없음** |
| `problem_bank_elementary_area_measure_v0` | 270 | [6수03-12] · [6수03-17] | **없음** |
| `problem_bank_discrete_ev_v0` | 200 | [12확통03-02] | **없음** |
| `problem_bank_highschool_quotient_rule_v0` | 200 | [12미적Ⅱ-02-04] | **없음** |
| `problem_bank_middle_function_v0` | 200 | [9수02-14] | **없음** |
| `problem_bank_quad_ineq_v0` | 200 | [10공수1-02-11] | **없음** |
| `problem_bank_university_calc1_v0` | 200 | [CALC1-02-02] | **없음** |
| `problem_bank_measurement_unit_conversion_v0` | 180 | [4수03-16] · [4수03-18] · [4수03-21] | **없음** |
| `problem_bank_permutation_combination_v0` | 160 | [10공수1-03-01] · [10공수1-03-02] | **없음** |
| `problem_bank_radian_conversion_v0` | 144 | [12대수02-01] | **없음** |
| `problem_bank_sequence_sigma_v0` | 132 | [12대수03-04] · [12대수03-05] | **없음** |
| `problem_bank_calculus2_trig_integral_v0` | 130 | [12미적Ⅱ-03-01] · [12미적Ⅱ-03-05] · [12미적Ⅱ-03-07] | **없음** |
| `problem_bank_combination_binomial_v0` | 121 | [12확통01-02] · [12확통01-03] | **없음** |
| `problem_bank_conic_section_focus_v0` | 65 | [12기하01-01] · [12기하01-02] · [12기하01-03] | **없음** |
| **합계 30종** | **11,446** | **고유 55개** | **30/30 부재** |

### 1.2 결정론 생성기 — **30파일**(주장 35는 오기 · §5-⑤)

전량 `src/backend/whymath_backend/l3/equivalent/<topic>_skeleton_generator.py`.

```bash
comm -13 <(git ls-tree -r --name-only origin/main src/backend/whymath_backend/l3/equivalent/ | sort) \
         <(git ls-tree -r --name-only $B          src/backend/whymath_backend/l3/equivalent/ | sort) | wc -l   # 30
```

동반 신규(트리 차집합): 생성기 테스트 30 · `harness/*_batch.py` 적재 드라이버 30 · 그 테스트 30.

### 1.3 저작 태스크 — **32건**(주장 22는 범위 누락 · §5-⑥)

```bash
comm -13 <(git ls-tree --name-only origin/main backlog/tasks/ | sort) \
         <(git ls-tree --name-only $B          backlog/tasks/ | sort) | wc -l   # 32
```

`S4-30`~`S4-51` 22건 외에 **`S4-19`·`S4-20`·`S4-22`~`S4-29` 10건**이 더 있고 전부 `done`이며
코퍼스 10종(`elementary_v0` 400 · `matrix_ops` 320 · `coordinate_geometry` 400 ·
`university_calc1` 200 · `middle_function` 200 · `discrete_ev` 200 · `quad_ineq` 200 ·
`sequence_sigma` 132 등)을 만들었다. **회수 범위를 `S4-30`~`S4-51`로 잡으면 그 10종이 태스크 없이
고아가 된다** → 범위는 `S4-19`~`S4-51`이어야 코퍼스 30종이 태스크와 닫힌다.

---

## §2. 차단 조건 — 1건이 아니라 **3건** (acceptance ②)

### ⑴ 사이드카 부재 30/30 — **red/green 양측 실측 완료**

`ops/provenance_audit.py`가 `--corpus-root`를 받으므로 **리포를 건드리지 않고** 임시 트리로 측정했다.

| 상태 | 명령 | 결과 |
|---|---|---|
| 사이드카 **부재** | `provenance_audit --corpus-root <tmp>` | **EXIT=1** · `SIDECAR_MISSING` **30건**(다른 종류 0) |
| 최소 사이드카 **부여** | 동일 | **EXIT=0** · 위반 **0건** |

두 상태가 **서로 다른 exit code**를 낸다 — 이 게이트는 회수의 실제 차단 조건이 맞다.
같은 값이 나왔다면 차단 조건이 아니었을 것이다.

면제 경로는 0이다 — `ARCH-25`가 `provenance_audit.py:97`의 `_KNOWN_GAPS`를 **빈 dict**로 비웠고,
그 조회는 사이드카 부재일 때만 일어난다(주장 확인).

**red를 만들지 않는 축도 확정**: 신규 11,446 레코드 전량이 `license`/`source_type`을 갖고 있어
`RECORD_FIELDS_MISSING` 0 · `qa_pipeline`의 같은 감사 축은 `continue-on-error: true`라 무해 ·
그랜드파더 만료 계약은 `_KNOWN_GAPS`가 비어 자명 통과.

### ⑵ 🔴 `S4-19`·`S4-22` ID 충돌 — **git도 `validate`도 잡지 못한다** (신규 발견)

| 번호 | main | 브랜치 |
|---|---|---|
| `S4-19` | `S4-19-live-step-verification-event-persist` | `S4-19-grade-axis-overlay-wiring` |
| `S4-22` | `S4-22-attempt-event-signal-consumer-wiring` | `S4-22-elementary-addsub-pilot-corpus` |

```bash
# 번호 충돌 전수 스캔(PREFIX-NN 동일·슬러그 상이) → 정확히 2건
```

**파일명이 다르므로 git은 충돌을 내지 않고 양쪽을 조용히 병존시킨다.** `backlog.py validate`도
full-ID가 달라 통과한다 — CLAUDE.md가 등재한 2026-07-18/25 `ARCH-13`·`OPS-15` 중복 배정과 같은
계열이며, 그 사고 기록이 *"full-ID는 슬러그 덕에 달라 validate가 통과했고 사람·문서·커밋의 번호
참조만 결정 불가가 됐다"* 고 적은 그 상태가 **머지 직후 재현된다**. 회수 전 재번호 필수.

`PB-06`·R3 어디에도 언급이 없던 조건이다.

### ⑶ shallow clone — 이 컨테이너에서는 병합 계산 자체가 불가

```bash
git merge-base origin/main $B   # exit 1 — 공통 조상 없음
```

`.git/shallow`(2 grafted roots)라 트렁크 히스토리가 잘려 있다. **트리 대 트리 비교(`ls-tree`
차집합)는 깊이와 무관하게 정확**하므로 이 문서의 수치는 영향받지 않지만, 실제 병합·`git diff`의
삭제(`D`) 판정은 신뢰할 수 없다. 회수 실행 전 `git fetch --unshallow origin` 선행 필요.

### ⑷ ~~부수 조건 — `S4-09` 회수~~ → **해소됨 (2026-08-11 착륙 전 재확인)**

**이 축은 더 이상 회수 조건이 아니다.** 초안 작성 시점에는 `S4-09`가 `claude/whymath-solution-review-40xspg`에
`done`으로 고립돼 있고 main은 `todo`였다. 그 사이 **`SOL-01`(PR #801)이 회수해 main에서 `done`이다.**

부분 회수이긴 하다 — 실측(개별 조회):

| main에 착륙 | 여전히 부재 |
|---|---|
| `l3/solution_path.py` · `l3/solution_path_store.py` · `db/models/solution_path.py` · `whs/path_promotion.py` · alembic `20260729_1200` | `l3/multi_solution.py` · alembic `20260729_1400_d7e8f1a2b4c6` |

그러나 **잔여분은 미소유 고립이 아니다.** `SOL-01` acceptance ②가 명시한다 — *"`21e35d28`·
`707c5665`의 S4-10 WIP(ApproachType 좌석·`l3/multi_solution.py`·alembic `d7e8f1a2b4c6`)는 **범위
밖** — 알려진 실패 1건(같은 문제 2경로 시 `solution_paths` 헤더 1건만 적재)이 미해결이라
**`S4-10`이 처리한다**"*.

즉 **소유 태스크가 있으므로** 이 문서가 정의하는 문제(*"감지된 고립을 회수로 잇는 경로가 없다"*)에
해당하지 않는다. 조건표에서 뺀다.

> 이 정정은 조건을 **줄인다**. 문서의 결론이 약해지는 게 아니라 정확해지는 방향이며, `SOL-01`이
> 이 문서가 정의하려던 "회수 경로"를 다른 축에서 실제로 실행한 첫 사례라는 점도 기록해 둔다.

---

## §3. 사이드카 생성 경로 — **없다** (acceptance ③)

3중 근거로 확정한다.

1. **`pool` 키를 쓰는 non-test 코드가 정의부 2개뿐** — `schema/corpus_provenance.py` ·
   `schema/enums.py`. 실 사이드카 26개의 `pool` 값은 `ARCH-20`이 손으로 백필한 것이다.
2. **`_provenance.json`을 *쓰는* 코드는 있으나 전부 `pool`을 누락한다** — `src/data-pipeline/`의
   8개 코퍼스 빌드 CLI(`_write_provenance()`)가 생성하는 payload에 `pool`이 없어 그대로 쓰면
   **`SCHEMA_INVALID`**가 된다. 게다가 `write_text` 통째 덮어쓰기라 **기존 코퍼스에 재실행하면
   손으로 넣은 `pool`이 날아간다**(회귀 위험). 유일한 멱등 갱신
   (`atom_graph/university_standard_fill.py::_append_provenance`)은 파일이 없으면 그냥 return한다.
3. **회수 브랜치의 생성기 30개도 `_provenance` 언급 0건** — `problems.jsonl` 하나만 쓴다.

→ acceptance ③이 지시한 대로 **부재를 별도 태스크로 등재**했다(§6). 여기서 만들지 않는다.

**최소 유효 사이드카**(계약 `schema/corpus_provenance.py`, `extra="allow"`):

```json
{"pool": "whymath-original", "source_citation": "<출처 한 줄>"}
```

`ContentPool` 폐쇄 3종: `whymath-original` · `external-sharealike` · `external-licensed`.
`source_citation`·`license_notice` 중 **최소 1개가 non-empty**여야 한다(model_validator).


---

## §4. 커버리지 델타 (acceptance ④) — Kiki 결정의 정량 입력

분모는 `data/corpus/standards_v1/standards.json`의 **2022 개정 435 코드**(895 레코드 중
2022 개정 435 · 2015 개정 460). 브랜치의 대장 파일은 main과 **바이트 동일**이라 분모가 같고
델타가 성립한다. `--standards`를 main 파일로 명시 고정해 측정했다.

```bash
# 기준선
python -m whymath_backend.harness.problem_bank_coverage \
  --corpus-root data/corpus --standards data/corpus/standards_v1/standards.json --json <out>
# 회수 후 = main 7종 + 신규 30종을 한 루트에 모아 동일 명령
```

| 지표 | main (7종 2,638문) | 회수 후 (37종 14,084문) | 델타 |
|---|---:|---:|---:|
| **성취기준 커버** | **78 / 435 (17.9%)** | **130 / 435 (29.9%)** | **+52 (+12.0%p)** |
| 초등학교 | 9 / 121 (7.4%) | **22 / 121 (18.2%)** | **+13** |
| 중학교 | 23 / 60 | 24 / 60 | +1 |
| 고등학교 | 46 / 254 (18.1%) | **84 / 254 (33.1%)** | **+38** |
| **0커버 영역** | **24 / 45** | **19 / 45** | **−5** |
| 파싱 실패 | 0 | 0 | 0 |
| 성취기준 코드 없는 문항 | 0 | 0 | 0 |

**해소되는 0커버 영역 5개**: 이차곡선 · 적분 · 적분법 · 통계 · 행렬

**남는 19개 0커버 영역은 이 회수로도 안 뚫린다** — 인공지능수학 4 · 경제수학 4 · 실용통계 계열 ·
과제 탐구 3 · 사회와 수학 · 예술과 수학 · 환경과 수학 · 집합과 명제 등. 이것도 결정 입력이다
(회수가 커버리지 문제를 *끝내지 않는다*).

### 2022 개정 대장 대조 결과 — 신규 55코드는 **52 + 3**이다

- **52코드**는 435 대장에 실재하며 main 78코드와 **교집합 0**(합집합 130 = 78 + 52).
- **3코드는 대장에 없다** — `[CALC1-02-02]` · `[CALC1-02-03]` · `[CALC1-02-04]`, 각 200문
  **합계 600문**. 2015 개정에도 없다(`other_revision_only_codes` = 0). 즉 대학 미적분 2종 600문은
  회수해도 **커버율 분자에 0 기여**하고 `unknown_standard_codes`로 상시 노출된다.
  (`standards_university_v1/`이 별도 대장으로 있으나 435 분모와 무관하다.)

### 병합 방식은 커버리지 결론을 바꾸지 않는다

브랜치 단독(37종)과 union(main 7종 + 신규 30종)의 결과가 **동일**(130/435 · 19영역)이다.
브랜치가 재생성한 공유 코퍼스의 미세 차이(총 9문)는 커버 코드 집합을 바꾸지 않는다.

### 부수 실측 — 유형 축 미반영

회수 후 `problems_without_problem_type` = **11,867**. 신규 코퍼스가 `S3-27` 유형 축을 채우지
않았다는 뜻이다(커버리지 판정과는 독립).

---

## §5. 정정 — 태스크·정본이 인용한 수치 6건이 틀렸다

| # | 기술 위치 | 기술값 | 실측 | 성격 |
|---|---|---|---|---|
| ① | `PB-06` ④ · R3 §3 G1 | 기준선 **72/435** · 초등 **5/121** · 0커버 **25** | **78/435 · 9/121 · 24** | `docs/data/problem_bank_coverage_2026-07.json`(2,667문·6종)이 stale. **문서를 인용하면 안 되고 도구를 재실행해야 한다** |
| ② | `PB-06` ② | `ci.yml:301-302` | **`ci.yml:325-326`**(착륙 시점 재확인) | 라인 드리프트. 초안 작성 시엔 306-307이었고 main 전진으로 다시 밀렸다 — 라인 인용은 이렇게 빨리 낡는다 |
| ③ | `PB-06` ② · R3 | "브랜치 **전체** 사이드카 7개" | 트리 전체 **26개** / `problem_bank_*` 기준 **7/37** | 범위 표현 부정확. **결론(신규 30종 전부 부재)은 정확** |
| ④ | R3 §3 G1 | 신규 고유 코드 **55** | **52(대장 실재) + 3(대장 밖)** | 55 자체는 맞으나 커버율 기여는 52뿐 |
| ⑤ | R3 §3 G1 표 · `PB-06` ① | 생성기 **35파일** | **30파일** | R3 §부록에 **이 수치만 재현 명령이 없다**. 어떤 패턴으로도 35가 안 나온다(생성기 30 / +테스트 60 / 브랜치 전체 40) |
| ⑥ | `PB-06` ① | 저작 태스크 **22건**(S4-30~51) | 브랜치 전용 **32건**(S4-19~51) | 10건 누락 → **회수 범위가 바뀐다**(§1.3) |

### 착륙 전 재측정 (2026-08-11 · main 10커밋 전진 후)

이 문서는 *다른 문서의 낡은 수치를 정정하는 것이 본체*라, 자신이 낡은 채 착륙하지 않도록
착륙 직전 전 수치를 재측정했다. main이 `data/corpus/problem_bank_rephrased_v0/problems.jsonl`을
바꿨기 때문에 기준선이 움직였을 수 있었다.

| 축 | 재측정 결과 |
|---|---|
| §4 기준선 | **변화 없음** — 7종 2,638문 · 커버 78 · 초등 9/121 · 중등 23/60 · 고등 46/254 · 0커버 24/45 |
| §4 회수 후 | **변화 없음** — 37종 14,084문 · 커버 130 · 초등 22 · 중등 24 · 고등 84 · 0커버 19 · 대장 밖 3코드 |
| §2 ⑵ ID 충돌 | 유효(`S4-19`·`S4-22`) |
| §6 필터 발견 | **유효** — 아래 패턴 변화에도 `data/corpus/`는 여전히 미포함 |
| §2 ⑷ S4-09 | **해소** — `SOL-01`이 회수(§2 ⑷ 참조) |

"변화 없음"도 실측 결과다 — 재측정 없이 기존 표를 그대로 두는 것이 이 문서가 R3에 대해 지적한
바로 그 실수(stale 인용)이므로, 값이 같다는 사실 자체를 기록한다.

**backend 경로 필터 패턴이 그 사이 일반화됐다**: 초안 시점 `data/notation_contract\.json$` +
`data/render_contract\.json$` 나열형 → 현재 **`data/[^/]+\.json$`** 글롭. `MATH-01`이 개별 계약
파일을 나열해 메운 구멍을 누군가 글롭으로 일반화한 것이다. **그러나 이 글롭은 `data/` 바로 아래
`*.json`만 매칭하므로 `data/corpus/<코퍼스>/problems.jsonl`은 여전히 덮지 않는다** — §6의 발견은
패턴이 개선된 뒤에도 유효하다.

⑤가 특히 뼈아프다 — `추론 0 · git show 재현 명령 병기`를 요구한 문서가 **정확히 그 명령을 빠뜨린
한 칸에서 틀렸다.** 그래서 이 문서는 수치마다 명령을 1:1로 붙였다.

---

## §6. 범위 밖 (acceptance ⑤) · 발견의 처분

**이 문서가 하지 않는 것**: 회수·병합·충돌 해소(Kiki 소유) · 문항 내용 재검수 · 품질 재감사 ·
사이드카 30개 실제 생성(회수 행위의 일부 — 임시 트리에서 변별력 실측용으로만 만들고 리포에
남기지 않았다) · 사이드카 생성 CLI 구현(③이 명시 금지 — 등재만).

`PB-02`(열린 PR #739)와의 파일 분리는 이미 성립한다 — `PB-02` paths(`ci.yml` ·
`ops/provenance_audit.py` · `tests/infra/**`)와 `PB-06` paths(`docs/data/**` ·
`harness/problem_bank_coverage.py` · `backlog/tasks/**`)의 **교집합 0**. 기존
`problem_bank_coverage_2026-07.{md,json}`도 덮어쓰지 않았다(`PB-02`가 재생성 계약을 걸 대상).

### 발견 — `data/corpus/`가 backend 경로 필터에 없다 (**고치지 않음 · `PB-02` 판정 재료**)

`provenance_audit`는 `ci.yml:325-326`(backend 잡)에 배선돼 있는데 backend 필터(`ci.yml:88`)에
**`data/corpus/`가 없다**. 즉 **코퍼스 파일만 추가하는 PR은 backend 잡이 통째 skip돼 이 게이트가
한 번도 돌지 않는다** — skip은 required check에서 *충족*으로 계상되므로 조용하다.
배선 동결 테스트(`tests/infra/test_provenance_audit_wiring.py`)도 "스텝이 존재하는가"만 보고
"필터가 그 게이트가 지키는 파일을 덮는가"는 검사하지 않아 이 구멍을 못 잡는다.

회수 브랜치 자체는 `harness/*_batch.py` 30파일을 함께 담아 `backend=true`가 되므로 이 구멍에
빠지지 않는다. 위험한 것은 **"사이드카만 나중에 따로 붙이는 PR"** — 그 PR이 게이트를 우회한다.

**`MATH-01` ④(mobile 필터에 계약 4종 부재)와 동일 유형**이며, 판정 기준을 "게이트가 도는가" →
"근거가 실재하는가"(`MATH-02`) → **"트리거가 그 게이트가 지키는 파일을 덮는가"** 로 민 축의
세 번째 사례다.

**처분**: 수정 대상 파일이 전부 `PB-02` 소유라 새 태스크를 만들면 경로가 충돌한다. 따라서
**`PB-02`의 `notes`에 판정 재료로 등재**했다(구현 소유권 불변 — `dsl_integration_gap_review` §3의
"기존 태스크 판정 재료" 분류).

### 신규 등재

- **`PB-11`** — 코퍼스 사이드카 생성 CLI 부재(③의 산출). 상세는 태스크 acceptance.
