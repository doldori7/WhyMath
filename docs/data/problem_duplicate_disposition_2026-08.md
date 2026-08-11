# 실중복 9쌍 콘텐츠 판정 기록 — QUAL-02 (2026-08)

- **태스크**: `QUAL-02-real-duplicate-pair-disposition` (QUAL-01 가시화 후속 — 해소 축)
- **판정일**: 2026-08-11
- **기준 HEAD**: `959ec4ad` (NS-04·QUAL-01·QUAL-03 머지 직후, 브랜치 `claude/whymath-dsl-integration-check-bmjic8`)
- **감사 도구**: `python -m whymath_backend.harness.problem_duplication_audit` — 이 태스크에서 **실행 전용**(S4-16 세션과 파일 겹침으로 수정 금지)
- **판정 원칙**: 일괄 삭제·자동 규칙 금지 — 9쌍 각각 레코드 **전문을 읽어** 쌍별 개별 판정(아래 표의 근거는 전부 이번 세션 실측)

## 0. 요약

QUAL-01(2026-08-10)이 확정한 실중복 9쌍을 쌍별로 판정한 결과 **9쌍 전부에서 한쪽을 은퇴**(총 9레코드 제거: `problem_bank_rephrased_v0` 8건 + `problem_bank_generated_v0` 1건), 반대쪽 9레코드는 유지. 반영 후 감사 재실행으로 **확정 실중복 9→0쌍·데모 풀 동시노출 1→0쌍** 확인(§4). 병합 판정 쌍은 없음 — 모든 쌍에서 두 레코드가 실질 동일이라 병합할 차이 자체가 없었다.

## 1. 최우선 처리 — 쌍 9 (데모/파일럿 풀 동시 노출 유일 쌍)

**`wm-skel-92cd1ba2bbf5`(generated_v0) ↔ `wm-quad-eq-larger-root`(problem_bank_v1)** — "이차방정식 x^2 - 5x + 6 = 0 의 두 근 중 큰 근을 구하시오." 단답형·정답 3. 데모 풀 코퍼스(`seed_demo.py` `_CORPORA` = v1·generated_v0·misconception_mc_v0)에 양쪽이 **동시 적재되던 유일한 쌍** — 실사용자(데모·파일럿)가 같은 문항을 두 번 만날 수 있던 상태.

**판정: `wm-skel-92cd1ba2bbf5` 은퇴 · `wm-quad-eq-larger-root` 유지.**

**전문 대조 실측** (두 레코드 전량 필드 대조):
- **동일**: question_text(바이트 동일)·answer("3")·`verify.conditions`("x**2 - 5*x + 6 = 0")·`verify.answer_map`({x:"3"})·`verify.answer_selection`("largest")·problem_type_codes(`ptype.solve-for-unknown`)·concepts(HK06 PRIMARY 0.95)·persona_fit(5종 전부)·난이도 2.0·question_format·answer_format·unit_codes(QUAD-EQ). 해설도 실질 동일(공백 표기 "(x - 2)(x - 3)" vs "(x-2)(x-3)"만 차이).
- **차이(정직 기록)**: ① 성취기준 태그 — skel `[9수02-20]`(S3-15가 스켈레톤 185건을 정위치 재태깅한 결과) vs v1 `[10공수1-02-02]`(수제 저작 시 태그·v1 검수 소관은 본 태스크 범위 밖). ② skel 측에만 `verify.solution_steps` 2단계·`유사` relations 3건 발신·review_status=approved·problem_id. ③ v1 측에만 keywords 3종("이차방정식·인수분해·근"). → 유지 측이 **완전한 상위집합은 아니다**(착수 가설 '상위호환'의 부분 수정) — 그러나 런타임 소비 축(문항·정답·SymPy 검산 재료·유형·개념·페르소나) 전부에서 동등하다.

**은퇴/유지 방향의 결정 근거** (배선 실측 — 제거 전 전수 grep 재확인):
- `wm-quad-eq-larger-root`는 **살아있는 배선 4곳**이 참조: `src/backend/whymath_backend/harness/problem_type_mapping.py:351`(slug→유형 매핑 정본), `tests/backend/harness/test_problem_type_backfill.py`, `data/corpus/concept_assessment_v1/index.json`(진단 평가 인덱스), `docs/strategy/subject_pack_spec_v1.md`. 게다가 problem_bank_v1은 seed_demo의 필수·안정 코퍼스(수제 4건).
- `wm-skel-92cd1ba2bbf5`는 **런타임 참조 0** — 감사 도구의 서술문·그 골든 테스트(이번에 갱신)·docs/data 이력 기록(백필 감사 스냅샷·검수 표본)뿐이고, `concept_assessment_v1/index.json` 참조 0, seed_demo는 슬러그 단위 참조 없음(코퍼스 파일 단위 적재).
- `solution_steps` 손실은 수용: 문항 자체가 1단계 인수분해 수준이고, Tier1 검산 재료(conditions·answer_map·answer_selection)는 유지 측에 온전하다. 참고로 과거 검수 기록의 결함 플래그('원판이 문제의…' 비문 — `ai_review_batch_v0_4corpora_2026-07.md`)는 이 레코드가 아니라 당시 **재서술 트윈**(rephrased 검수 섹션 소속·현재 코퍼스에 부재)의 것 — 현행 generated_v0 본문은 정상이었으며, 은퇴 사유는 결함이 아니라 중복이다.

**매달린 참조 정리(은퇴의 후속 반영)**: generated_v0의 3개 레코드(`wm-skel-acfa5a6f61fb`·`wm-skel-b2b4c091bff4`·`wm-skel-9950b7d3512a` — 전부 다른 방정식)가 은퇴 슬러그를 `유사` parent로 선언하고 있었다(매달린 참조). 즉시 깨뜨리는 소비자는 없으나(계보 그래프는 미해결 parent를 노드로 유지·고아 측정은 rephrased_v0 한정) 은퇴 레코드를 가리키는 참조는 차기 감사·적재의 고아 신호가 되므로 **해당 관계 항목 3건만 제거**했다(각 레코드의 다른 relations·본문은 바이트 무변경). 정리 후 재실행 실측: orphan 0·confirmed 0 유지, 계보 그래프 노드 1041→**1040**(미해결 parent 노드 소멸)·엣지 2131→**2128**. 유지 측 review_status=pending은 기존 상태(v1 수제 검수 파이프라인 소관 — 본 태스크가 변화시키지 않음).

## 2. 쌍 1~8 — generated_v0 스켈레톤 트윈 ↔ rephrased_v0 무변화 사본 교차

구조: 스켈레톤 4종이 각각 객관식(extmc)/단답형(extv) 트윈을 갖고, 각 트윈의 재서술본이 **무변화**라서 반대 형식 트윈과 교차로 텍스트 일치(스켈레톤당 2쌍 × 4종 = 8쌍). rephrased_v0는 데모 풀 코퍼스가 아니므로 **학생 비노출**. 8쌍 각각에 대해 rephrased 레코드 전문을 자기 parent(`relations[0].parent_slug`)와 대조했다 — 전건에서 question_text·answer·choices·explanation·verify·question_format·concept_slug·difficulty **8필드 전부 동일**, 오히려 parent에만 있는 `problem_type_codes`가 결여된 **진부분집합**(콘텐츠 기여 0 + 메타 결손). 각 레코드는 스스로 `relation_type="변형", similarity_score=1.0`을 선언한다 — '변형' 라벨과 모순되는 자기 선언 무변화.

**판정: 8쌍 전부 rephrased 측 은퇴, generated 측 유지.** 은퇴 자리는 QUAL-03 계열 후속의 파이프라인 재실행 시 정상 재서술본으로 대체될 자리다. 실질 변형(다른 선지·다른 해설 가치)이 발견된 쌍은 **0건** — 있었으면 그 쌍은 유지 판정 예정이었다(착수 가설 대비 이탈 없음).

| # | 유지 (generated_v0) | 은퇴 (rephrased_v0) | 문항(정규화) | 쌍별 근거 (전부 개별 실측) |
|---|---|---|---|---|
| 1 | `wm-calc-extmc-bd21cd8484d2` (객관식) | `wm-calc-extv-bd21cd8484d2-rephrased` (단답형) | x³+12x²−27x 극댓값 | 은퇴 측은 parent `wm-calc-extv-bd21cd8484d2`의 8필드 동일 사본(similarity 1.0 자기선언·problem_type_codes 결여). 유지 측은 다른 형식(객관식) 원본으로 독자 가치 보유. 사본 제거로 쌍 소멸·parent는 잔존. |
| 2 | `wm-calc-extv-bd21cd8484d2` (단답형) | `wm-calc-extmc-bd21cd8484d2-rephrased` (객관식) | x³+12x²−27x 극댓값 | 은퇴 측은 parent `wm-calc-extmc-bd21cd8484d2`의 8필드 동일 사본 — 선지(choices)까지 동일해 객관식으로서의 변별 기여도 0. 유지 측은 단답형 원본. |
| 3 | `wm-calc-extmc-cf788e51e0fd` (객관식) | `wm-calc-extv-cf788e51e0fd-rephrased` (단답형) | x³+18x²+96x 극댓값 | 은퇴 측은 parent `wm-calc-extv-cf788e51e0fd`의 8필드 동일 사본(similarity 1.0 자기선언). 콘텐츠 기여 0 + 학생 비노출 — 은퇴. |
| 4 | `wm-calc-extv-cf788e51e0fd` (단답형) | `wm-calc-extmc-cf788e51e0fd-rephrased` (객관식) | x³+18x²+96x 극댓값 | 은퇴 측은 parent `wm-calc-extmc-cf788e51e0fd`의 8필드 동일 사본 — 선지 포함 동일. 유지 측은 단답형 원본. |
| 5 | `wm-calc-extmc-5c4a86d7a72a` (객관식) | `wm-calc-extv-5c4a86d7a72a-rephrased` (단답형) | x³+3x²−9x 극솟값 | 은퇴 측은 parent `wm-calc-extv-5c4a86d7a72a`의 8필드 동일 사본(similarity 1.0 자기선언). 극솟값 밴드도 예외 없이 무변화 — 은퇴. |
| 6 | `wm-calc-extv-5c4a86d7a72a` (단답형) | `wm-calc-extmc-5c4a86d7a72a-rephrased` (객관식) | x³+3x²−9x 극솟값 | 은퇴 측은 parent `wm-calc-extmc-5c4a86d7a72a`의 8필드 동일 사본 — 선지 포함 동일. 유지 측은 단답형 원본. |
| 7 | `wm-calc-extmc-cd86d461d1b1` (객관식) | `wm-calc-extv-cd86d461d1b1-rephrased` (단답형) | x³−18x²+105x 극댓값 | 은퇴 측은 parent `wm-calc-extv-cd86d461d1b1`의 8필드 동일 사본(similarity 1.0 자기선언). 콘텐츠 기여 0 — 은퇴. |
| 8 | `wm-calc-extv-cd86d461d1b1` (단답형) | `wm-calc-extmc-cd86d461d1b1-rephrased` (객관식) | x³−18x²+105x 극댓값 | 은퇴 측은 parent `wm-calc-extmc-cd86d461d1b1`의 8필드 동일 사본 — 선지 포함 동일. 유지 측은 단답형 원본. |
| 9 | `wm-quad-eq-larger-root` (problem_bank_v1·단답형) | `wm-skel-92cd1ba2bbf5` (generated_v0·단답형) | x²−5x+6=0 큰 근 | §1 상세 — 데모 풀 동시노출 유일 쌍(최우선). 유지 측 배선 4곳 실참조 vs 은퇴 측 런타임 참조 0, 학생 노출 필드 전부 실질 동일. |

**은퇴 8건 참조 전수 확인**(제거 전): `src/`·`tests/`·`scripts/`·`data/corpus/**`(자기 라인 제외)·`seed_demo.py`·`concept_assessment_v1/index.json` 참조 0. 유일한 등장은 `docs/data/{persona_fit,review_status}_backfill_audit/*.jsonl` — 과거 백필 **실행 기록(스냅샷)**이라 수정하지 않는다(이력 위조 금지·테스트 대조 없음 확인). 코퍼스 내부 `parent_slug` 피참조도 0(고아 생성 없음 — 재실행 orphan 0으로 실측 확인).

## 3. 반영 방식 — 왜 review_status 마킹이 아니라 레코드 제거인가

**은퇴 = `problems.jsonl`에서 해당 레코드 라인 제거**(타 라인 바이트 무변경).

1. **감사 도구는 `review_status`를 필터하지 않는다** — 마킹만으로는 acceptance ③("반영 후 재실행 시 목록에서 사라짐")을 만족할 수 없다.
2. 도구에 필터를 추가하는 선택지는 **봉인** — `problem_duplication_audit.py`는 S4-16 세션과 파일 겹침이라 이 태스크에서 수정 금지(실행 전용).
3. 제거 이력은 소실되지 않는다 — 각 코퍼스 `_provenance.json`에 기존 컨벤션(S3-12 위생 정화 "483→429" 선례와 동형의 `generation_method` 날짜 병기 이력 문장 + `record_count` 갱신)으로 기록하고, 슬러그 상세는 `retired_slugs` 필드로 병기. 재유입 가드는 갱신된 골든 테스트(은퇴 슬러그 부재 단언)가 기계로 동결.

## 4. 감사 재실행 전/후 수치 (전부 실측 — before/after JSON 대조)

| 지표 | 반영 전 (2026-08-11 재확인) | 반영 후 | 비고 |
|---|---|---|---|
| T2 확정 실중복 쌍 | **9** (형식동일 1·형식상이 8) | **0** (0·0) | acceptance ③ 충족 |
| 데모 풀 동시노출 쌍 | **1** | **0** | acceptance ② 충족 |
| 총 문항 수 | **2,647** | **2,638** | −9 |
| generated_v0 / rephrased_v0 | 620 / 429 | 619 / 421 | −1 / −8 |
| 교차 텍스트 일치 원후보 | 291 | 274 | 확정 9 + 계보 제외 8쌍 소멸 |
| 계보 제외(간접 하한) | 282 | 274 | 무변화 직접 측정과 등식 유지 |
| QUAL-03 무변화 / 정상변화 | 282 / 147 | 274 / 147 | 정상변화분 무손실 |
| 무변화 비율 | 65.73% | 65.08% | 분모 421 |
| 부모미선언 / 고아참조 | 0 / 0 | 0 / 0 | 은퇴가 고아를 만들지 않음 |
| 동일 코퍼스 내부 중복 그룹 | generated 4 · rephrased 4 | generated 4 · rephrased 0 | 하단 '범위 밖' 참조 |
| 슬러그 충돌(T1) | 0 | 0 | 불변 |

before: `qual02_audit_before.json`(사전 실측)·재확인 실행으로 동일성 검증 / after: `qual02_audit_after.json` — 둘 다 세션 스크래치 산출물, 수치는 본 표에 영속.

## 5. 함께 갱신한 골든 핀 (실코퍼스 수치 단언 전수 탐색 결과)

- `tests/backend/harness/test_problem_duplication_audit.py` — 실코퍼스 스냅샷 2종: total 2647→2638, 확정 9→0(쌍별 단언 → 은퇴 슬러그 부재 + 유지 슬러그 존재 단언으로 교체), noop 429/282→421/274, 등식 `lineage_excluded == unchanged` 282→274.
- `tests/backend/harness/test_problem_type_mapping.py` — `_GOLDEN_TOTAL_TAGGED` 2218→2217(generated_v0 1건 제거 반영), `_GOLDEN_EXCLUDED_TOTAL` 429→421, generated_v0 SOLVE 분포 282→281(QUAD-EQ 185→184), 뮤테이션 변별력 테스트의 QUAD-EQ 하드코딩 185→184.
- `tests/backend/harness/test_rephrased_corpus_hygiene.py` — 커밋 코퍼스 청정 동결의 총량 하한 `>= 429`→`>= 421`(위생 위반 제거가 아니라 중복 은퇴임을 주석 병기). **패턴 grep(`== 429`)이 놓친 `>=` 하한 핀 — 전체 스위트 실행이 검출**(부분 통과 보고 금지 원칙의 실효 사례).
- `tests/backend/harness/test_curriculum_revision_crosswalk_report.py` — docstring 서술 수치(단언 아님) 2647→2638 최소 갱신.
- 그 외 실코퍼스 수치 단언 없음 확인: `test_problem_corpus_batch.py`의 620은 hermetic 생성기 실행 핀(실코퍼스 미결합), HTTP 429 상태코드 단언은 무관.

## 6. 범위 밖 (명시)

- **282(현 274) lineage 쌍 전체** — generated↔rephrased 1:1 직접 부모-자식 무변화 쌍. 개별 은퇴가 아니라 **파이프라인 재검토 후 일괄 재실행** 대상(QUAL-03 계열 후속 소관). 이 태스크는 QUAL-01이 *확정*한 9쌍만 다뤘다.
- **신규 코퍼스 생성·재서술 파이프라인 수정** — QUAL-03 소관(`run_corpus_rephrase`의 fail-closed 편입 설계 등).
- **generated_v0 내부 형식 트윈 4그룹**(extmc/extv 동일 발문) — 동일 코퍼스 내부 사안으로 T2(교차 코퍼스) 확정 목록 밖. 의도된 생성기 밴드 설계(객관식/단답형)인지 발문 차별화가 필요한지는 별도 콘텐츠 판단 대상.
- **`wm-quad-eq-larger-root`의 review_status=pending·성취기준 태그(`[10공수1-02-02]`) 적정성** — v1 수제 코퍼스 검수 절차 소관.
