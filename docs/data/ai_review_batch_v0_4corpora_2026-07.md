# AI 검수 결과 — v0 잔여 4종 코퍼스 720문 (S3-09 · 2026-07-29)

> **검수 방식**: **AI 검수** (2026-07-10 Kiki 결정·`ai_review_batch_240_2026-07.md` 규약 동형). 인간 수기검수가 아님을 정직 명시한다. 검수 주체 = pedagogy 서브에이전트 **7인**(코퍼스·표본 범위 분할·SymPy 배치 재검산 병행), 모델ID 미기재(규약).
> **판정 항목**: 사람층 ①~⑥ (①발문 자연성 ②풀이 타당성 ③난이도 정합 ④성취기준 귀속 ⑤오답↔오개념 귀속[객관식] ⑥우연 유사). 기계 게이트(S2-a 4종)는 적재 시 이미 통과·**Tier1 전수 재검산(4종 2,043문) 검수 직전 전건 통과·실패 0** — 본 검수는 그 위의 교수학·표면 층이다.
> **표본**: 결정론 층화(rotation 0·`reviewer_sample_package`) — mc 200/1,080 · rephrased 200/483 · conceptual 200/360 · **killer 120/120(전수 — 코퍼스가 min-n 200 미만인 유일 케이스)**. 합 720문.
> **결론(rotation-0)**: **4개 코퍼스 전부 게이트 FAIL — 노출 부적격 유지**(게이트 통과 ≠ 학생 노출). 계통 결함 5류가 원인이며 전량 생성기·파이프라인 결함(환류 대상·`S3-12` 등재). 수학 정답 자체의 오류는 0건 — 결함은 전부 해설 수치·전제 실현성·조사·성취기준 태그·발문 위생 축(기계 Tier1 게이트의 검산 범위 밖)이다.
> **현재 상태(rotation-2 · §"Rotation-2 확인 감사 결과" 참조·S3-14)**: mc·rephrased의 rotation-1 조치 효과를 신규 독립 표본(mc 200/1,080·rephrased 200/429)으로 최종 확인. **mc는 PASS**(결함 0·Wilson 상한 1.33% ≤ 2% — rotation-0→1→2 3라운드 만에 게이트 통과 달성, `distribute-first-term-only`/`negative-distribute-sign`/`angle-sum-non-triangle` 계통 결함 재발 0건 확정). **rephrased는 3라운드 연속 FAIL**(결함 2·Wilson 상한 2.98% > 2% — 점추정은 12%→5.5%→1%로 개선됐으나 매 라운드 새로운 결함 유형이 계속 나타나 임계 통과 실패. §4.5 규약대로 4라운드째 패치-재표본 반복 대신 **근본 설계 재검토**를 신규 태스크로 등재, `S3-15-rephrase-pipeline-redesign` 참조). killer는 min-n 구조적 미달 지속(별건 코퍼스 확장 결정 필요).

## 종합 — 코퍼스별 판정 (as-found · `corpus_audit_eval --max-defect-upper 0.02 --min-n 200 --require-as-found`)

| 코퍼스 | n | 결함 | 점추정 | Wilson 95% 상한 | 판정 | 결함류 분포 |
|---|---|---|---|---|---|---|
| `problem_bank_misconception_mc_v0` | 200/1,080 | 116 | 58.00% | **63.60%** | **FAIL** (exit 1) | grammar_break 67 · standard_tag_error 44 · explanation_slip 5 |
| `problem_bank_conceptual_v0` | 200/360 | 50 | 25.00% | **30.35%** | **FAIL** (exit 1) | grammar_break 30 · explanation_slip 13 · condition_mismatch 7 |
| `problem_bank_rephrased_v0` | 200/483 | 24 | 12.00% | **16.30%** | **FAIL** (exit 1) | grammar_break 16 · other 4 · statement_mismatch 4 |
| `problem_bank_killer_v0` | 120/120 전수 | 120 | 100% | 100% | **FAIL + min-n 미달** (exit 1) | standard_tag_error 120 (계통 1건의 전건 전파) |

감사 라벨(선두 as-found 병기): `corpus_audit_mc_v0.jsonl` · `corpus_audit_conceptual_v0.jsonl` · `corpus_audit_rephrased_v0.jsonl` · `corpus_audit_killer_v0.jsonl`

**노출 지위**: 4종 모두 기존에도 표본 검수 미경유로 노출 부적격이었다 — 이번 판정으로 상태가 "미측정"에서 "**측정됨·불합격**"으로 명확해진 것이며 실질 후퇴는 없다. 합격 검수를 보유한 노출 후보는 여전히 `generated_v0` 620문(240표본 상한 1.11% PASS)뿐이다.

## 계통 결함 5류 (생성기 환류 — `S3-12-problem-bank-v0-defect-remediation`)

1. **조사(josa) 하드코딩 전방위** — grammar_break 113/720의 대부분. `misconception_eval_mc`·`conceptual_count_mc` 생성기 계열이 수·수식 읽기 기반 받침 판별(`l3/equivalent/josa.py` 헬퍼) 없이 조사를 하드코딩: `와/과`·`을/를`·`로/으로`·`은/는`·`이/가` 전 유형에서 발생(예: "10 와"→과, "x = 2 을"→를, "18² 로"→으로, "1 가"→이). **S2-08(2026-07-12)에서 trig 생성기만 고쳐진 josa 계통 결함이 이 생성기들엔 미적용 상태였음이 실측된 것.** rephrase 코퍼스의 조사 오류는 LLM 산출(아래 5).
2. **성취기준 태그 계통 오귀속** — killer 120/120 + mc 44/200. 밴드별 하드코딩 태그가 문항 내용과 불일치:
   - killer(Vieta 근집계) 전건 `[10공수1-02-02]`(판별식) — 정합은 이차형 `[10공수1-02-03]`(근과 계수의 관계)·삼차형 `[10공수1-02-07]`(간단한 삼차·사차방정식). **성취기준 정본(statement) 대조로 확정.**
   - mc: 초등 정위치 내용에 중등 코드(사다리꼴 넓이→`[9수03-12]` 닮음, 정위치 `[6수03-14]` — 정본 대조 확정 / 원 넓이→`[9수03-19]` 원주각 / 소수 곱셈→`[9수01-06]` 순환소수 / 직사각형 둘레·넓이→`[9수03-12]`), 일차방정식→`[9수02-13]`(연립), sin bx 주기→`[12미적Ⅱ-02-02]`(덧셈정리, 정위치 `[12대수02-02]`), 근과 계수→`[10공수1-02-08]`(연립이차, 정위치 `[02-03]`) 등.
3. **해설 수치 오류(explanation_slip) 18건** — ⑴ conceptual 극한 밴드 13건: 해설의 극한값 부호 반전(생성기 b−a 순서 버그 — 예: (x²−4x+3)/(x−1)의 x→1 극한 실제 **−2**를 "2"로 진술, SymPy·원문 대조 확정. 답 0은 유지) ⑵ mc 완전제곱 밴드 5건: 해설에 미치환 템플릿 변수 `(c+11)²` 노출.
4. **모순 전제(condition_mismatch) 7건** — conceptual 조건부확률 밴드: 파라미터 샘플링이 확률 공리를 검증하지 않아 **실현 불가능한 확률 설정** 생성(예: P(A)=1/12·P(B)=1/2·P(A|B)=1/2 → P(A∩B)=1/4 > P(A), 해설의 P(B|A)=3 — 확률>1. 원문 대조 확정). 문항 성립 자체가 불가한 차단성.
5. **rephrase LLM 발문 위생 게이트 부재** — rephrased 24/200: 한자·일본어 주입("두解"·"となる"), 재서술 메타 라벨 누출("원 발문:"·"원판"), 비표준 용어("원시방정식"·"다차방정식"), 요구-정답 불일치 4건(발문이 '구하는 방법'을 묻는데 정답은 값 — statement_mismatch), 조사 오류·비문. 원문 grep 교차검증: 한자/메타/용어 패턴 14건 실재. rephrase의 불변 봉인은 수치·정답·선지만 검사하고 **발문 텍스트 품질 게이트가 없다**.

### 경미 관찰 (비차단·note+ok — 파이프라인 피드백)

- **killer 난이도 표기 vs 실체**: 전건 difficulty 4.0대 표기이나 실제 풀이는 근합(−b/a)·근곱(c/a, −d/a) 1스텝 — "킬러" 코퍼스 정체성과 불일치(감사 관찰·`problem_bank_gap_review.md` D4 커버리지 관측과 연동).
- 해설 `1x`·`7/1` 미간약 표기, 선지 필러 값 다수(수학적 무해).
- 표본 md 렌더에서 distractor 미태깅 선지가 일괄 "← 정답"으로 표기(렌더 한계 — 코퍼스 무결, `reviewer_sample_package._format_choices` 후속 개선 후보).
- mc 일부 문항의 병기 코드가 내용과 느슨(개념 코드 vs 계산 코드) — 차단성 오귀속과 구분해 관찰로만 기록.

## 검증 교차확인 (검수자 신뢰가 아니라 독립 재확정)

계통 결함의 대표 주장을 오케스트레이터가 코퍼스 원문·성취기준 정본으로 직접 재검증했다:

- 극한 부호(3): `wm-count-mc-0b1c1bfefa43` 원문 해설 "극한값은 2" vs 실제 −2 — **확정**
- 모순 전제(4): `wm-count-mc-4887e176d9ac` P(A∩B)=1/4 > P(A)=1/12 — **확정**
- killer 태그(2): `[10공수1-02-02]`="판별식을 이용하여 근을 판별" / `[02-03]`="근과 계수의 관계" — 전건 Vieta 문항이므로 **오귀속 확정**
- mc 태그(2): `wm-misc-eval-mc-99495abd77df` "사다리꼴의 넓이" 문항에 `[9수03-12]`(닮음) — `[6수03-14]`(사다리꼴 넓이)가 정위치 — **확정**
- rephrase 주입(5): `두解|となる|원 발문|원시방정식|다차방정식` 코퍼스 grep 14건 — **확정**
- conceptual 조사(1): 숫자·식 뒤 `" 가 "` 코퍼스 grep 72건 — **확정**

## 기계 게이트 증적 (초인간 검증)

- **S6 상시성(Tier1 재검산)**: 검수 직전 `corpus_reverify`로 4종 2,043문 전수 재검산 — **전건 통과·실패 0** (mc 1,080 · rephrased 483 · conceptual 360 · killer 120). 이번 결함 310건이 전부 Tier1 검산 범위(정답 산출) **밖**의 축임을 뒷받침한다.
- **S5 감사 판정**: `corpus_audit_eval --max-defect-upper 0.02 --min-n 200 --require-as-found` 4회 실행 — 4종 전부 exit 1(종합 표). as-found 병기 선언은 각 감사 jsonl 선두에 기계 강제(§4.5·S2-12).
- **표본 하한**: killer는 코퍼스 120 < min-n 200 — 전수 감사로도 표본 게이트 해금 불가(구조적 미달·정직 판정). 코퍼스 확장(≥200) 또는 기준 개정 전까지 표본 게이트 경로 자체가 닫혀 있다.
- **재판정 규약(§4.5)**: 생성기 교정 후 같은 표본 재채점 금지 — 재판정은 `--rotation 1` 신규 독립 표본으로만(`S3-12` acceptance에 명시).

## Rotation-1 환류 검증 결과 (S3-12 · 2026-07-29)

**절차(§4.5 준수)**: 계통 결함 5류를 생성기 축에서 교정(josa.py 확장·태그 재귀속·해설 수치
교정·확률 공리 가드·rephrase 발문 위생 게이트 신설)한 뒤, rotation-0(위 720문)과 **무관한
신규 독립 표본**(`--rotation 1` — mc 200/1,080·conceptual 200/360·rephrased 200/429·killer
120/120 전수)을 뽑아 재검수했다. rotation-0 표본을 재채점해 FAIL→PASS를 만드는 시도는
없다(§4.5 "합격 로트 무결성" — 정본 `superhuman_verification_standard.md`).

**rotation-1 as-found 판정**(`corpus_audit_eval --max-defect-upper 0.02 --min-n 200 --require-as-found`):

| 코퍼스 | n | 결함 | 점추정 | Wilson 95% 상한 | 판정 | 결함류 분포 |
|---|---|---|---|---|---|---|
| `problem_bank_misconception_mc_v0` | 200/1,080 | 9 | 4.50% | **7.58%** | **FAIL** (exit 1) | standard_tag_error 9 |
| `problem_bank_conceptual_v0` | 200/360 | 0 | 0.00% | **1.33%** | **PASS** (exit 0) | — |
| `problem_bank_rephrased_v0` | 200/429 | 11 | 5.50% | **8.79%** | **FAIL** (exit 1) | grammar_break 3 · other 3 · statement_mismatch 5 |
| `problem_bank_killer_v0` | 120/120 전수 | 0 | 0.00% | 2.20% | **FAIL — min-n 미달**(exit 1) | — |

감사 라벨(rotation-1 as-found로 갱신): `corpus_audit_mc_v0.jsonl` · `corpus_audit_conceptual_v0.jsonl` · `corpus_audit_rephrased_v0.jsonl` · `corpus_audit_killer_v0.jsonl` (rotation-0 라벨을 덮어씀 — 사유: rotation-0의 5류 결함은 이미 생성기 교정으로 해소돼 있었고, 같은 표본 재채점은 §4.5 위반이라 새 독립 표본의 결과가 정본을 승계한다).

**rotation-1이 발견한 잔여 결함(전건 조치 완료)**:
- **mc 9건 — 성취기준 태그 오귀속 2종**: `distribute-first-term-only`·`negative-distribute-sign`(단항식×다항식 전개인데 `[9수02-09]`(다항식 덧셈·뺄셈) 태그 — 정위치 `[9수02-10]`, 5건) + `angle-sum-non-triangle`(`[9수03-03]`(삼각형 작도)이 내각합과 무관 — 정본 statement 대조 확정, 4건). **조치**: 밴드 표준코드 재태깅 + `misconceptions.json` M0017·M0018·M0051 동시 교정(agree 유지) + 코퍼스 재생성.
- **rephrased 11건 — 발문 위생 게이트 잔존 축**: 괄호 메타 지시문 누출("(원래와 같은 표현으로)" 등 4건)·차원/도형 오기술("두 차원의 이차방정식" 등 3건)·개념 오치환("중점"·"큰 극" 2건)·어형 붕괴 비문("크다음 근을"·"크다 가르키는" 2건 — 형태소 분석 없이는 일반화 불가해 명시 slug 소급 제거). **조치**: `rephrase_hygiene.py`에 3신규 축 추가(패턴 정밀화로 오탐 0 확보 — 아래 참조) + 소급 제거 목록 신설 → 코퍼스 429→429(신규 축 적용 후 443에서 14건 추가 탈락, 최종 429).
- **conceptual·killer**: rotation-1 결함 0건 — rotation-0에서 발견된 결함(극한 부호·확률 공리·판별식 태그)이 생성기 교정으로 완전 해소됐음을 독립 표본이 확인.

**정직한 결과(§4.5 — 교정했다고 임의 PASS 선언 금지)**: mc·rephrased는 rotation-1이 발견한
잔여 결함을 전부 조치했으나, **이 조치는 rotation-1 표본 자체를 재채점한 것이 아니라 코퍼스
전체(재생성·재소인)에 적용한 것**이다 — 따라서 rotation-1의 as-found 판정(위 표)은 그대로
FAIL로 기록하고, 조치 후 실제 결함율이 임계 이하인지는 **rotation-2 신규 독립 표본**으로만
확인 가능하다(§4.5 — 후속 태스크로 등재, 아래 "다음 단계" 참조). 성급한 PASS 선언보다 정직한
FAIL+조치완료 기록을 택했다.

**부수 발견·조치 — concept_src_id 계통 결함(6번째 축, AI 텍스트 검수 범위 밖)**: 위 태그
재귀속을 적용하며 misconception_mc의 `_TEMPLATE_META`(concept_src_id — 문항→개념그래프
전이의 실제 앵커, `achievement_standard_codes`와는 별도 필드)를 45템플릿 전수 대조한 결과,
**13개가 재태깅된 표준코드와 무관한 구 개념을 계속 가리키고 있었다**(이번 세션 rotation-1
교정 12건 + S3-12 1차 패스 교정 11건에서 파생 — M0052 크로스링크 회귀와 동일 계통: 표시용
태그만 고치고 그래프 앵커를 놓침) + concept_src_id 자체가 concept_graph_v1에 없는 성취기준
코드 문자열 오기였던 선재 결함 1건(`circle_radius` — S3-12와 무관, 발견 즉시 조치). 전건을
concept_graph_v1 역탐색으로 재고정하고, 크로스워크 실제 해석 경로(`derive_src_to_primary_atom`)로
0 dangling 확인 → `test_relink_governance.py`가 이제 misconception_mc_v0도 상시 감시(3→4
코퍼스, 재발 방지 — 편입 전에는 이 결함류가 무기한 미검출 상태였다).

**하네스 자기검증 사후 발견·조치 — 위생 게이트 오탐 3건**: 신규 3축(괄호 메타·차원 오기술·
개념 오치환)을 rephrase 코퍼스 대조만으로 검증했으나, 이 게이트는 `TestTextHygieneS312`를
통해 misconception_eval_mc_generator·conceptual_count_mc_generator의 설명 문구에도 **공유
적용**된다는 것이 사후 실측됐다 — "(일차항 계수)"·"(최대공약수는 1)"·"(단위: 도)"(정당한 괄호
설명) · "중점"(midpoint-sum-only 밴드의 정상 용법) · "N의 제곱이므로 그 제곱근은"(sqrt_sum
밴드의 참인 서술, 24건) 오탐을 실측 발견해 폐쇄 목록 후퇴·부정 lookahead로 정밀화(도크스트링
"2026-07-29 재검토 실측" 참조 — 향후 신규 축은 rephrase 단독이 아니라 전 코퍼스 대조가
재검증 범위).

**다음 단계(후속 태스크 — 이 문서가 만드는 신규 정직한 공백)**: mc·rephrased의 rotation-2
독립 표본 재검수(§4.5) — 조치가 실제로 결함율을 임계 이하로 낮췄는지 최종 확인. killer는
corpus_audit_eval의 min-n 200 요구를 코퍼스 크기(120) 자체가 구조적으로 충족 못 한다 —
표본 게이트 통과에는 코퍼스 확장(≥200건 추가 생성)이 선결 조건이며, 이는 결함 조치가 아니라
별도의 저작 스코프 결정이라 이 세션 범위 밖으로 정직하게 남긴다.

## Rotation-2 확인 감사 결과 (S3-14 · 2026-07-29)

**절차(§4.5 준수)**: rotation-1이 발견·조치한 잔여 결함(mc 9건 성취기준 태그 오귀속·
rephrased 11건 발문 위생)이 실제로 결함율을 임계 이하로 낮췄는지, rotation-0·1과 무관한
**신규 독립 표본**(`--rotation 2` — mc 200/1,080·rephrased 200/429)으로 최종 확인했다.
검수 주체 = pedagogy 서브에이전트 **4인**(코퍼스별 전·후반 100문씩 분할, 각자 전건 SymPy/
직접 계산 재검산 + 성취기준 정본 대조 + 조사 규칙 판별 병행). rotation-0·1 표본을 재채점하는
시도는 없다.

**rotation-2 as-found 판정**(`corpus_audit_eval --max-defect-upper 0.02 --min-n 200 --require-as-found`):

| 코퍼스 | n | 결함 | 점추정 | Wilson 95% 상한 | 판정 | 결함류 분포 |
|---|---|---|---|---|---|---|
| `problem_bank_misconception_mc_v0` | 200/1,080 | 0 | 0.00% | **1.33%** | **PASS** (exit 0) | — |
| `problem_bank_rephrased_v0` | 200/429 | 2 | 1.00% | **2.98%** | **FAIL** (exit 1) | grammar_break 2 |

감사 라벨(as-found 신규 생성): `corpus_audit_mc_v0_r2.jsonl` · `corpus_audit_rephrased_v0_r2.jsonl`
(rotation-1 라벨과 별개 보존 — rotation별 독립 기록이 §4.5 감사 추적성의 근거).

**mc — 3라운드 만에 PASS 확정**: rotation-0(FAIL 58%)→rotation-1(FAIL 4.5%)→rotation-2
(**PASS 0%**)로 수렴했다. rotation-1이 발견한 두 계통 결함(`distribute-first-term-only`/
`negative-distribute-sign`이 `[9수02-09]`→정위치 `[9수02-10]`, `angle-sum-non-triangle`이
무관한 `[9수03-03]`→정위치 `[4수03-25]`/`[9수03-05]`)이 이번 독립 표본의 해당 도메인
전건(DISTRIBUTE-PARTIAL 5문·NEG-DISTRIBUTE 4문·POLYGON-ANGLE-SUM 4문)에서 성취기준 정본
대조로 재발 0건 확정됐다. rotation-0의 조사(josa)·해설 수치·태그 계통 결함 5류 전부 재발
없음 — **`problem_bank_misconception_mc_v0`는 노출 적격 재평가 대상**(법적 게이트
`is_exposable()`은 자체생성이라 항상 통과 — 이번 PASS로 운영 정책상의 표본 감사 블로커가
해소됨. 실 노출 전환은 별도 운영 결정).

**rephrased — 3라운드 연속 FAIL, 근본 설계 재검토로 이관**: rotation-0(FAIL 12%)→rotation-1
(FAIL 5.5%)→rotation-2(FAIL 1%·Wilson 상한 2.98%)로 점추정은 꾸준히 개선됐으나, **매
라운드 임계(2%)를 상한이 넘는다** — n=200에서는 결함 2건만으로도 Wilson 상한이 2%를
초과한다(표본 크기 대비 소수 결함이 곧바로 게이트 미달로 직결되는 구간). 두 결함 모두
**기존 `rephrase_hygiene.py` 3~6축 어디에도 안 걸리는 신규 유형**이다:
- 표본16(`wm-skel-1cc6d23230b8`): "다차원 문제지만"(차원 오기술)·"크 greater한"(영단어
  주입+어형 붕괴)·"귀를"(개념 오치환 — "값을"이어야 함) 3종이 **한 문항에 동시 재발**.
  정답·verify 수치는 정확(2x²+5x+2=0 → 근 -1/2·-2 검산 일치) — 결함은 표면 어휘 층뿐.
- 표본190(`wm-log-495ada0f7043`): "log_6 x = 2의 값을 찾아보세요" — '값'의 지시 대상이
  x인지 방정식 자체인지 불명확(같은 도메인 표본191·193과 대조하면 이 표본만 목적어
  붕괴). 정답(x=36)은 정확.

**정직한 결론**: S3-14 acceptance의 "3회차부터는 근본 설계 재검토" 조항에 따라, 4번째
패턴 패치+rotation-3 반복을 이 태스크 안에서 시도하지 않는다. 매 라운드 **이전에 못 본
새로운 결함 유형**이 나타나는 패턴(휘의 두더지 잡기)은 LLM 자유 재작성 방식 자체의 예측불가
변동성이 원인일 가능성을 시사하며, 패턴 매칭 축 추가만으로는 수렴하지 않을 수 있다 — 근본
설계(결정론 템플릿 치환 등 대안) 재검토를 `S3-15-rephrase-pipeline-redesign`으로 등재했다.
`problem_bank_rephrased_v0`는 노출 부적격 유지.

## 문항별 판정 — misconception_mc (200)

| slug | 도메인 | 형식 | verdict | 결함류 | 비고 |
|---|---|---|---|---|---|
| `wm-misc-eval-mc-f3278bb9356e` | ABS-VALUE | 객관식 | ok |  | 4+21=25 검산·오답17=부호유지값 정합. 표본md 비태깅 선지 '정답' 라벨은 렌더 오표기(코퍼스 무결) |
| `wm-misc-eval-mc-40eaaea68255` | ABS-VALUE | 객관식 | ok |  | 6+21=27 검산·오답15=b−a 정합. [9수01-04](대소)보다 [9수01-05](사칙계산) 정밀 — 경미 |
| `wm-misc-eval-mc-1d192c96f608` | ABS-VALUE | 객관식 | ok |  | 2+5=7 검산·오답3 정합. 한자릿 덧셈에 난이도 3.2는 상단이나 gross 아님 |
| `wm-misc-eval-mc-07393165891c` | ABS-VALUE | 객관식 | ok |  | 12+21=33 검산·오답9 정합. 코드 경미(대소관계 — 계산 문항) |
| `wm-misc-eval-mc-9e122e331cd2` | ABS-VALUE | 객관식 | ok |  | 2+7=9 검산·오답5 정합. 코드 경미 동일 |
| `wm-misc-eval-mc-c55b36a96884` | AREA-PERIMETER | 객관식 | defect | standard_tag_error | [9수03-12](닮음) 오귀속([6수03-13] 정위치)·해설 '18 와'→과 조사오류. 14 검산 정합 |
| `wm-misc-eval-mc-7a10aea79a18` | AREA-PERIMETER | 객관식 | defect | standard_tag_error | [9수03-12] 오귀속·'30 와'→과 조사오류. 50 검산·둘레30 정합 |
| `wm-misc-eval-mc-4e903da30eef` | AREA-PERIMETER | 객관식 | defect | standard_tag_error | [9수03-12](닮음) 무관 오귀속. 105 검산·둘레44 정합·조사 정상 |
| `wm-misc-eval-mc-b1c65ad1577a` | AREA-PERIMETER | 객관식 | defect | standard_tag_error | [9수03-12] 오귀속·'36 와'→과 조사오류. 72 검산·둘레36 정합 |
| `wm-misc-eval-mc-1191c8aad19d` | AREA-PERIMETER | 객관식 | defect | standard_tag_error | [9수03-12] 오귀속·'46 와'→과 조사오류. 120 검산·둘레46 정합 |
| `wm-misc-eval-mc-b3bb65300930` | CALC-CHAIN | 객관식 | ok |  | f'(3)=15·16²=3840 검산·오답768=내부도함수 5 누락값 정합 |
| `wm-misc-eval-mc-47accf44cdde` | CALC-CHAIN | 객관식 | defect | grammar_break | 해설 'x = 2 을'→를 조사오류(이·모음). 2940 검산·오답588 정합 |
| `wm-misc-eval-mc-acf1b79da89f` | CALC-CHAIN | 객관식 | ok |  | f'(3)=2352 검산·오답588=내부 4 누락값 정합 |
| `wm-misc-eval-mc-9505004d763d` | CALC-CHAIN | 객관식 | ok |  | f'(3)=486 검산·오답243=내부 2 누락값 정합 |
| `wm-misc-eval-mc-cf6e28ba3f4a` | CALC-CHAIN | 객관식 | defect | grammar_break | 해설 'x = 2 을'→를 조사오류. 1452 검산·오답363 정합 |
| `wm-misc-eval-mc-fd5ac974df02` | CALC-PRODUCT | 객관식 | ok |  | (fg)'(5)=4·5³=500 검산·오답75=f'g' 정합. 발문 x^1 표기 경미 |
| `wm-misc-eval-mc-0192090932f3` | CALC-PRODUCT | 객관식 | ok |  | (fg)'(4)=6·4⁵=6144 검산·오답2304=f'g' 정합 |
| `wm-misc-eval-mc-506b5ef44920` | CALC-PRODUCT | 객관식 | ok |  | (fg)'(2)=4 검산·오답1=f'g' 정합. x^1 표기 경미 |
| `wm-misc-eval-mc-7f0a47e53b77` | CALC-PRODUCT | 객관식 | ok |  | (fg)'(8)=192 검산·오답16=f'g' 정합. x^1 표기 경미 |
| `wm-misc-eval-mc-de79c922bb7b` | CALC-PRODUCT | 객관식 | ok |  | (fg)'(4)=48 검산·오답8=f'g' 정합. x^1 표기 경미 |
| `wm-misc-eval-mc-bc459d538e50` | CIRCLE-AREA | 객관식 | defect | standard_tag_error | [9수03-19](원주각) 오귀속 — 원 넓이는 [6수03-16]/[9수03-06]. 49 검산·오답14=2r 정합 |
| `wm-misc-eval-mc-4bcd4f8ab63a` | CIRCLE-AREA | 객관식 | defect | standard_tag_error | [9수03-19] 오귀속·'6 로'→으로 조사오류. 9 검산·오답6 정합 |
| `wm-misc-eval-mc-55a2da4abb38` | CIRCLE-AREA | 객관식 | defect | standard_tag_error | [9수03-19](원주각) 오귀속. 144 검산·오답24=둘레값 정합 |
| `wm-misc-eval-mc-d925b497d7f2` | CIRCLE-AREA | 객관식 | defect | standard_tag_error | [9수03-19] 오귀속·'10 로'→으로 조사오류. 25 검산·오답10 정합 |
| `wm-misc-eval-mc-36670db3a71e` | CIRCLE-AREA | 객관식 | defect | standard_tag_error | [9수03-19] 오귀속·'40 로'→으로 조사오류. 400 검산·오답40 정합 |
| `wm-misc-eval-mc-30b235071a6f` | CIRCLE-RADIUS | 객관식 | ok |  | √400=20 검산·오답400=우변값 정합. [12기하02-05](구) 병기는 인접 확장 경미 |
| `wm-misc-eval-mc-8c98c6772bab` | CIRCLE-RADIUS | 객관식 | defect | grammar_break | 해설 '529 을'→를 조사오류(구·모음). 23 검산·오답529 정합 |
| `wm-misc-eval-mc-c0fc6035800b` | CIRCLE-RADIUS | 객관식 | defect | grammar_break | 해설 '49 을'→를 조사오류. 7 검산·오답49 정합 |
| `wm-misc-eval-mc-da3631ce937f` | CIRCLE-RADIUS | 객관식 | defect | grammar_break | 해설 '625 을'→를 조사오류. 25 검산·오답625 정합 |
| `wm-misc-eval-mc-1e31774a6ddb` | CIRCLE-RADIUS | 객관식 | ok |  | √256=16 검산·오답256 정합 |
| `wm-misc-eval-mc-ee2ca5a8705b` | COMBINATION-COUNT | 객관식 | defect | grammar_break | 해설 '3024 이 되어'→가 조사오류. 126 독립 재산출 일치(verify 동어반복)·오답=9P4 정합 |
| `wm-misc-eval-mc-edc3b9adc18e` | COMBINATION-COUNT | 객관식 | ok |  | 715 독립 재산출 일치(verify 동어반복)·오답17160=13P4 정합. [10공수1-03-03] 미태깅 관찰 |
| `wm-misc-eval-mc-1b9f3fa938c8` | COMBINATION-COUNT | 객관식 | defect | grammar_break | 발문 '17C3 를'→을 조사오류(씨삼 받침). 680 재산출·오답4080=17P3 정합 |
| `wm-misc-eval-mc-920ed3c75ed1` | COMBINATION-COUNT | 객관식 | defect | grammar_break | 발문 '8C3 를'→을 조사오류. 56 재산출·오답336=8P3 정합 |
| `wm-misc-eval-mc-598156be0943` | COMBINATION-COUNT | 객관식 | defect | grammar_break | 발문 '22C3 를'→을 조사오류. 1540 재산출·오답9240=22P3 정합 |
| `wm-misc-eval-mc-6c18f15031f4` | COMBINE-UNLIKE | 객관식 | defect | grammar_break | 해설 'x² 는'→은 조사오류(제곱 받침). 400 검산·오답4096=(2+6)x³ 정합 |
| `wm-misc-eval-mc-455079633c2d` | COMBINE-UNLIKE | 객관식 | defect | grammar_break | 'x² 는'→은 조사오류. 182 검산·오답2744=8x³ 정합 |
| `wm-misc-eval-mc-331dbfee9bf5` | COMBINE-UNLIKE | 객관식 | defect | grammar_break | 'x² 는'→은 조사오류. 92 검산·오답512=8x³ 정합 |
| `wm-misc-eval-mc-c73030d5f5ab` | COMBINE-UNLIKE | 객관식 | defect | grammar_break | 'x² 는'→은 조사오류. 102 검산·오답1512=7x³ 정합 |
| `wm-misc-eval-mc-40e81e5712ae` | COMBINE-UNLIKE | 객관식 | defect | grammar_break | 'x² 는'→은 조사오류. 22 검산·오답56=7x³ 정합 |
| `wm-misc-eval-mc-9033ca808ea6` | COMPLETE-SQUARE | 객관식 | defect | explanation_slip | 해설 미치환 변수 '(c+11)²' 노출·'²로'→으로 조사. 152 검산·오답361=(8+11)² 정합 |
| `wm-misc-eval-mc-d36d3ebfa81e` | COMPLETE-SQUARE | 객관식 | defect | explanation_slip | '(c+3)²' 미치환 노출·'²로' 조사. 108 검산·오답144=(9+3)² 정합 |
| `wm-misc-eval-mc-bfeb183216e2` | COMPLETE-SQUARE | 객관식 | defect | explanation_slip | '(c+11)²' 미치환 노출·'²로' 조사. 102 검산·오답289=(6+11)² 정합 |
| `wm-misc-eval-mc-e7e2c414106d` | COMPLETE-SQUARE | 객관식 | defect | explanation_slip | '(c+3)²' 미치환 노출·'²로' 조사. 54 검산·오답81=(6+3)² 정합 |
| `wm-misc-eval-mc-1516a2b1c943` | COMPLETE-SQUARE | 객관식 | defect | explanation_slip | '(c+10)²' 미치환 노출·'²로' 조사. 75 검산·오답225=(5+10)² 정합 |
| `wm-misc-eval-mc-3b8a76dfa0d5` | CONE-VOLUME | 객관식 | ok |  | 6²·24/3=288 검산·오답864=⅓ 누락값 정합 |
| `wm-misc-eval-mc-0d86997f6c35` | CONE-VOLUME | 객관식 | defect | grammar_break | 해설 '126 가 되어'→이 조사오류(육 받침). 42 검산·오답126 정합 |
| `wm-misc-eval-mc-3e30ff78aa7f` | CONE-VOLUME | 객관식 | ok |  | 228 검산·오답684=⅓ 누락값 정합 |
| `wm-misc-eval-mc-6baa4aaa58c8` | CONE-VOLUME | 객관식 | defect | grammar_break | 해설 '30 가 되어'→이 조사오류(십 받침). 10 검산·오답30 정합 |
| `wm-misc-eval-mc-d8bf0bdeb1f2` | CONE-VOLUME | 객관식 | defect | grammar_break | 해설 '576 가 되어'→이 조사오류. 192 검산·오답576 정합 |
| `wm-misc-eval-mc-fdf52fb7014f` | CONJUGATE-PRODUCT | 객관식 | ok |  | 12−1=11 검산·오답13=합차 부호오용(a+b²) 정합 |
| `wm-misc-eval-mc-3442752d71e4` | CONJUGATE-PRODUCT | 객관식 | ok |  | 27−1=26 검산·오답28 정합 |
| `wm-misc-eval-mc-a5216b8500ac` | CONJUGATE-PRODUCT | 객관식 | ok |  | 20−1=19 검산·오답21 정합 |
| `wm-misc-eval-mc-ff13e0735b6c` | CONJUGATE-PRODUCT | 객관식 | ok |  | 17−1=16 검산·오답18 정합 |
| `wm-misc-eval-mc-b0ab3f07f97c` | CONJUGATE-PRODUCT | 객관식 | ok |  | 25−1=24 검산·오답26 정합. √25 미간약 표기는 경미 관찰 |
| `wm-misc-eval-mc-3cf80cb03830` | DECIMAL-MULT | 객관식 | defect | standard_tag_error | [9수01-06](순환소수) 오귀속 — 소수 곱셈은 [6수01-13]. 9/50 검산·오답9/5 정합 |
| `wm-misc-eval-mc-7357f49bd1d4` | DECIMAL-MULT | 객관식 | defect | standard_tag_error | [9수01-06] 오귀속·조사 2건('0.8 는'→은·'40/10로'→으로). 2/5 검산·오답4 정합 |
| `wm-misc-eval-mc-dbbda5e77056` | DECIMAL-MULT | 객관식 | defect | standard_tag_error | [9수01-06] 오귀속·'20/10로'→으로 조사. 1/5 검산·오답2 정합 |
| `wm-misc-eval-mc-4556c6afb958` | DECIMAL-MULT | 객관식 | defect | standard_tag_error | [9수01-06] 오귀속. 2/25 검산·오답4/5 정합. 소수 문항 분수 선지 관찰 |
| `wm-misc-eval-mc-cebc0297895d` | DECIMAL-MULT | 객관식 | defect | standard_tag_error | [9수01-06] 오귀속. 27/50 검산·오답27/5 정합 |
| `wm-misc-eval-mc-d513d4860a75` | DIFF-SQUARES | 객관식 | defect | standard_tag_error | [9수01-01](소인수분해) 오귀속 — 합차는 [9수02-19]. '1 를'→을·'(x-a)²로'→으로 조사. 80 검산 |
| `wm-misc-eval-mc-0e2e0cf72122` | DIFF-SQUARES | 객관식 | defect | standard_tag_error | [9수01-01] 오귀속·'7 를'→을·'²로' 조사. 207 검산·오답81=(x−a)² 정합 |
| `wm-misc-eval-mc-0d48d12855d6` | DIFF-SQUARES | 객관식 | defect | standard_tag_error | [9수01-01] 오귀속·'1 를'→을·'²로' 조사. 195 검산·오답169 정합 |
| `wm-misc-eval-mc-8dcd375aca75` | DIFF-SQUARES | 객관식 | defect | standard_tag_error | [9수01-01] 오귀속·'(x-a)²로'→으로 조사. 21 검산·오답9 정합(verify 동어반복) |
| `wm-misc-eval-mc-c4417eb5eef7` | DIFF-SQUARES | 객관식 | defect | standard_tag_error | [9수01-01] 오귀속·'(x-a)²로'→으로 조사. 221 검산·오답169 정합 |
| `wm-misc-eval-mc-36638ab78abc` | DISTRIBUTE-PARTIAL | 객관식 | defect | grammar_break | 해설 'x = 8 를'→을 조사오류(팔 받침). 30 검산·오답23=앞항만 분배 정합 |
| `wm-misc-eval-mc-e9f9cede4ebe` | DISTRIBUTE-PARTIAL | 객관식 | defect | grammar_break | 'x = 8 를'→을 조사오류. 45 검산·오답31 정합 |
| `wm-misc-eval-mc-5f18fea93c77` | DISTRIBUTE-PARTIAL | 객관식 | defect | grammar_break | 'x = 7 를'→을 조사오류. 54 검산·오답44 정합 |
| `wm-misc-eval-mc-e05f082ccee2` | DISTRIBUTE-PARTIAL | 객관식 | defect | grammar_break | 'x = 8 를'→을 조사오류. 75 검산·오답47 정합 |
| `wm-misc-eval-mc-83b6e540c6a4` | DISTRIBUTE-PARTIAL | 객관식 | defect | grammar_break | 'x = 6 를'→을 조사오류. 32 검산·오답26 정합 |
| `wm-misc-eval-mc-eba4a8db014d` | EXP-PRODUCT | 객관식 | defect | grammar_break | 해설 '18² 로'→으로 조사오류(제곱 받침). 5832 검산·오답324=지수곱 정합 |
| `wm-misc-eval-mc-6a05422170ba` | EXP-PRODUCT | 객관식 | defect | grammar_break | '25² 로'→으로 조사오류. 15625 검산·오답625 정합 |
| `wm-misc-eval-mc-933e69216894` | EXP-PRODUCT | 객관식 | defect | grammar_break | '12² 로'→으로 조사오류. 1728 검산·오답144 정합 |
| `wm-misc-eval-mc-32fd324739bd` | EXP-PRODUCT | 객관식 | defect | grammar_break | '20² 로'→으로 조사오류. 8000 검산·오답400 정합 |
| `wm-misc-eval-mc-e90d0d0a7c53` | EXP-PRODUCT | 객관식 | defect | grammar_break | '5² 로'→으로 조사오류. 125 검산·오답25 정합 |
| `wm-misc-eval-mc-5c38950868fa` | EXP-ZERO | 객관식 | defect | grammar_break | 해설 '29 이 되어'→가 조사오류(구·모음). 30 검산·오답29=a⁰→0 정합 |
| `wm-misc-eval-mc-69d730b12ce2` | EXP-ZERO | 객관식 | ok |  | 3+1=4 검산·오답3 정합. a⁰은 중2 지수법칙 범위 확장 — 진단 맥락 방어 가능 경미 |
| `wm-misc-eval-mc-98c224385f2b` | EXP-ZERO | 객관식 | defect | grammar_break | 해설 '15 이 되어'→가 조사오류(오·모음). 16 검산·오답15 정합 |
| `wm-misc-eval-mc-4dbf11c67fd9` | EXP-ZERO | 객관식 | ok |  | 8+1=9 검산·오답8 정합 |
| `wm-misc-eval-mc-a634ced90779` | EXP-ZERO | 객관식 | ok |  | 11+1=12 검산·오답11 정합 |
| `wm-misc-eval-mc-fa746bba7864` | FRACTION-ADD | 객관식 | defect | grammar_break | '1/5 는'→은 조사오류(일 받침). 8/15 검산·오답1/4 정합. 해설 p·q 미정의 관찰 |
| `wm-misc-eval-mc-30a38614e23f` | FRACTION-ADD | 객관식 | defect | grammar_break | '1/9 는'→은 조사오류. 13/36 검산·오답2/13 정합. p·q 미정의 관찰 |
| `wm-misc-eval-mc-90c83b683056` | FRACTION-ADD | 객관식 | defect | grammar_break | '1/11 는'→은 조사오류. 15/44 검산·오답2/15 정합. p·q 미정의 관찰 |
| `wm-misc-eval-mc-c24998378764` | FRACTION-ADD | 객관식 | defect | grammar_break | '1/8 는'→은 조사오류. 11/24 검산·오답2/11 정합. p·q 미정의 관찰 |
| `wm-misc-eval-mc-979f17825c65` | FRACTION-ADD | 객관식 | defect | grammar_break | '1/10 는'→은 조사오류. 17/70 검산·오답2/17 정합. p·q 미정의 관찰 |
| `wm-misc-eval-mc-59ba3a846b05` | FRACTION-CANCEL | 객관식 | ok |  | 19/5 검산·오답14=a 소거값 정합. [9수01-04] 보조 병기는 인접 경미 |
| `wm-misc-eval-mc-217d769cdf39` | FRACTION-CANCEL | 객관식 | ok |  | 9/5 검산·오답4=b 정합 |
| `wm-misc-eval-mc-2bc199724f02` | FRACTION-CANCEL | 객관식 | defect | grammar_break | 해설 '13 를'→을 조사오류(삼 받침). 16/3 검산·오답13 정합 |
| `wm-misc-eval-mc-6ff81e773dc4` | FRACTION-CANCEL | 객관식 | defect | grammar_break | '13 를'→을 조사오류. 17/4 검산·오답13 정합 |
| `wm-misc-eval-mc-d39bbd1a1b01` | FRACTION-CANCEL | 객관식 | ok |  | 11/7 검산·오답4=b 정합 |
| `wm-misc-eval-mc-77b7d2ad33aa` | FUNC-COMPOSE | 객관식 | ok |  | f(g(3))=f(6)=7 검산·오답8=(g∘f)(3) 정합 |
| `wm-misc-eval-mc-361329886831` | FUNC-COMPOSE | 객관식 | ok |  | f(g(5))=f(25)=29 검산·오답45=(g∘f)(5) 정합 |
| `wm-misc-eval-mc-2ffe87a9b836` | FUNC-COMPOSE | 객관식 | ok |  | f(g(5))=21 검산·오답24=(g∘f) 정합 |
| `wm-misc-eval-mc-dea4f43b2883` | FUNC-COMPOSE | 객관식 | ok |  | f(g(5))=11 검산·오답12=(g∘f) 정합 |
| `wm-misc-eval-mc-a8339373cd7d` | FUNC-COMPOSE | 객관식 | ok |  | f(g(6))=25 검산·오답28=(g∘f) 정합 |
| `wm-misc-eval-mc-c558d5f5bd9f` | FUNC-TRANSLATE | 객관식 | ok |  | g(6)=f(5)=40 검산·오답70=f(7) 부호반전값 정합 |
| `wm-misc-eval-mc-7fff461a517e` | FUNC-TRANSLATE | 객관식 | ok |  | g(3)=f(2)=6 검산·오답20=f(4) 정합. 발문 'x^2 + 1x' 계수 1 표기 경미 |
| `wm-misc-eval-mc-08a02a565afd` | FUNC-TRANSLATE | 객관식 | ok |  | g(4)=f(3)=15 검산·오답35=f(5) 정합 |
| `wm-misc-eval-mc-192f1d1583b4` | FUNC-TRANSLATE | 객관식 | ok |  | g(8)=f(7)=63 검산·오답99=f(9) 정합 |
| `wm-misc-eval-mc-3c5be5ef91a5` | FUNC-TRANSLATE | 객관식 | ok |  | g(6)=f(5)=30 검산·오답56=f(7) 정합. '1x' 표기 경미 |
| `wm-misc-eval-mc-0aabd9404f73` | GCD-LCM | 객관식 | defect | grammar_break | 조사 받침 오류: '10 와'→'10과'(십·ㅂ). 수학·오답 귀속 정합 |
| `wm-misc-eval-mc-a845d39d5e1f` | GCD-LCM | 객관식 | ok |  | lcm(12,17)=204 재검산·오답 gcd=1 태깅 정합·조사 정상 |
| `wm-misc-eval-mc-600642193907` | GCD-LCM | 객관식 | ok |  | lcm(12,13)=156 재검산·오답 gcd=1 태깅 정합·조사 정상 |
| `wm-misc-eval-mc-cfbab8dd7491` | GCD-LCM | 객관식 | ok |  | lcm(2,7)=14 재검산·오답 gcd=1 태깅 정합·조사 정상 |
| `wm-misc-eval-mc-0b034bc5981b` | LOG-DIST | 객관식 | ok |  | 2^6+2^6=2^7 정답 7 검산·오답 12(로그 분배) 정합 |
| `wm-misc-eval-mc-b077c9d812f3` | LOG-DIST | 객관식 | ok |  | 2^26+2^26=2^27 정답 27 검산·오답 52(로그 분배) 정합 |
| `wm-misc-eval-mc-da51b532c81f` | LOG-DIST | 객관식 | defect | grammar_break | 조사 받침 오류: '40 로'→'으로'(사십). 수학·오답 귀속 정합 |
| `wm-misc-eval-mc-3b26e72077c4` | LOG-DIST | 객관식 | ok |  | 2^12+2^12=2^13 정답 13 검산·오답 24(로그 분배) 정합 |
| `wm-misc-eval-mc-8c480263e41b` | MIDPOINT-NO-HALF | 객관식 | ok |  | 중점 2 검산·오답 합(2 미나눔) 정합. 9수02-05 좌표 근사 귀속 관찰 |
| `wm-misc-eval-mc-f2ccca97906d` | MIDPOINT-NO-HALF | 객관식 | ok |  | 중점 17/2 검산·오답 합(2 미나눔) 정합. 9수02-05 좌표 근사 귀속 관찰 |
| `wm-misc-eval-mc-e06604beeb25` | MIDPOINT-NO-HALF | 객관식 | defect | grammar_break | 조사 받침 오류: '20로'→'으로'(이십). 수학·오답 귀속 정합 |
| `wm-misc-eval-mc-8a34a78a26bb` | MIDPOINT-NO-HALF | 객관식 | ok |  | 중점 6 검산·오답 합(2 미나눔) 정합. 9수02-05 좌표 근사 귀속 관찰 |
| `wm-misc-eval-mc-51ad78f8b69e` | MIXED-MULT | 객관식 | defect | standard_tag_error | 성취기준 오귀속: 9수01-04(대소관계)≠대분수 곱셈(정본 9수01-05). 조사 '5과'·'5 을' 오류 병존 |
| `wm-misc-eval-mc-94d2b127b4aa` | MIXED-MULT | 객관식 | defect | standard_tag_error | 성취기준 오귀속: 9수01-04(대소관계)≠대분수 곱셈(정본 9수01-05). 조사 '5 을'→'를' 병존 |
| `wm-misc-eval-mc-bb15854a3f6c` | MIXED-MULT | 객관식 | defect | standard_tag_error | 성취기준 오귀속: 9수01-04(대소관계)≠대분수 곱셈(정본 9수01-05). 조사 '2 을'→'2 를'(이) |
| `wm-misc-eval-mc-b738aff4e855` | MIXED-MULT | 객관식 | defect | standard_tag_error | 성취기준 오귀속: 9수01-04(대소관계)≠대분수 곱셈(정본 9수01-05). 수학·오답 정합 |
| `wm-misc-eval-mc-98d2c36eeaea` | NEG-DISTRIBUTE | 객관식 | ok |  | -(x-b) 대입값 3 검산·오답 뒷항 미반전 정합 |
| `wm-misc-eval-mc-4bd5ac65d2d8` | NEG-DISTRIBUTE | 객관식 | ok |  | -(x-b) 대입값 17 검산·오답 뒷항 미반전 정합 |
| `wm-misc-eval-mc-adc92ee70b90` | NEG-DISTRIBUTE | 객관식 | defect | grammar_break | 조사 받침 오류: '13 를'→'을'(십삼). 수학·오답 귀속 정합 |
| `wm-misc-eval-mc-2f2b08f73981` | NEG-DISTRIBUTE | 객관식 | defect | grammar_break | 조사 받침 오류: '10 를'→'을'(십). 수학·오답 귀속 정합 |
| `wm-misc-eval-mc-bfd5527a8a17` | NEG-EVEN-POWER | 객관식 | defect | grammar_break | 조사 받침 오류: '-46656로'→'으로'(육). 수학·오답 귀속 정합 |
| `wm-misc-eval-mc-fd1bcb5e9d6b` | NEG-EVEN-POWER | 객관식 | ok |  | 짝수 제곱 144 검산·오답 음수 부호 정합 |
| `wm-misc-eval-mc-deb4100afa60` | NEG-EVEN-POWER | 객관식 | defect | grammar_break | 조사 받침 오류: '-256로'→'으로'(육). 수학·오답 귀속 정합 |
| `wm-misc-eval-mc-6c91946cc861` | NEG-EVEN-POWER | 객관식 | ok |  | 짝수 제곱 324 검산·오답 음수 부호 정합 |
| `wm-misc-eval-mc-8745305ca760` | NEG-PRODUCT | 객관식 | ok |  | 음×음=42 검산·오답 -ab 정합. 9수01-03 개념 코드 관찰(계산은 -05) |
| `wm-misc-eval-mc-effa1c08bf01` | NEG-PRODUCT | 객관식 | ok |  | 음×음=91 검산·오답 -ab 정합. 9수01-03 개념 코드 관찰(계산은 -05) |
| `wm-misc-eval-mc-bc2945ff2f99` | NEG-PRODUCT | 객관식 | ok |  | 음×음=36 검산·오답 -ab 정합. 9수01-03 개념 코드 관찰(계산은 -05) |
| `wm-misc-eval-mc-6061b1110645` | NEG-PRODUCT | 객관식 | ok |  | 음×음=65 검산·오답 -ab 정합. 9수01-03 개념 코드 관찰(계산은 -05) |
| `wm-misc-eval-mc-b6ec99a9f169` | NEG-SQUARE | 객관식 | ok |  | -a² 우선순위 4 검산·오답 (-a)² 정합 |
| `wm-misc-eval-mc-971906fc960c` | NEG-SQUARE | 객관식 | ok |  | -a² 우선순위 -44 검산·오답 (-a)² 정합 |
| `wm-misc-eval-mc-4f4b47f02581` | NEG-SQUARE | 객관식 | ok |  | -a² 우선순위 -75 검산·오답 (-a)² 정합 |
| `wm-misc-eval-mc-51a1ad2b2136` | NEG-SQUARE | 객관식 | defect | grammar_break | 조사 받침 오류: '16로'→'으로'(십육). 수학·오답 귀속 정합 |
| `wm-misc-eval-mc-4827cb60f072` | POLY-PRODUCT | 객관식 | ok |  | (a+b)²=49 검산·오답 a²+b²(교차항 누락) 정합 |
| `wm-misc-eval-mc-666755947fdf` | POLY-PRODUCT | 객관식 | defect | grammar_break | 조사 받침 오류: '7 를'→'을'(칠). 수학·오답 귀속 정합 |
| `wm-misc-eval-mc-95a2eaa7b769` | POLY-PRODUCT | 객관식 | defect | grammar_break | 조사 받침 오류: '13 를'→'을'(십삼). 수학·오답 귀속 정합 |
| `wm-misc-eval-mc-9ff41a1611d9` | POLY-PRODUCT | 객관식 | defect | grammar_break | 조사 받침 오류: '10 를'→'을'(십). 수학·오답 귀속 정합 |
| `wm-misc-eval-mc-d3aede4d4398` | POLYGON-ANGLE-SUM | 객관식 | ok |  | (n-2)·180=1260 검산·오답 180 고정 정합. 코드셋 작도(9수03-03) 혼입 관찰 |
| `wm-misc-eval-mc-fcc08b591a89` | POLYGON-ANGLE-SUM | 객관식 | ok |  | (n-2)·180=4320 검산·오답 180 고정 정합. 코드셋 작도(9수03-03) 혼입 관찰 |
| `wm-misc-eval-mc-03b43e5af9da` | POLYGON-ANGLE-SUM | 객관식 | ok |  | (n-2)·180=4680 검산·오답 180 고정 정합. 코드셋 작도(9수03-03) 혼입 관찰 |
| `wm-misc-eval-mc-eed4edbbed0e` | POLYGON-ANGLE-SUM | 객관식 | ok |  | (n-2)·180=3780 검산·오답 180 고정 정합. 코드셋 작도(9수03-03) 혼입 관찰 |
| `wm-misc-eval-mc-24728c1fba65` | POWER-OF-POWER | 객관식 | defect | grammar_break | 조사 받침 오류: '10^5 로'→'으로'(제곱). 수학·오답 귀속 정합 |
| `wm-misc-eval-mc-27c28e2fb72b` | POWER-OF-POWER | 객관식 | defect | grammar_break | 조사 받침 오류: '5^5 로'→'으로'(제곱). 수학·오답 귀속 정합 |
| `wm-misc-eval-mc-b74654f9cb9d` | POWER-OF-POWER | 객관식 | defect | grammar_break | 조사 받침 오류: '3^9 로'→'으로'(제곱). 수학·오답 귀속 정합 |
| `wm-misc-eval-mc-fe08f363dafc` | POWER-OF-POWER | 객관식 | defect | grammar_break | 조사 받침 오류: '2^9 로'→'으로'(제곱). 수학·오답 귀속 정합 |
| `wm-misc-eval-mc-69497ffbc1f9` | PROB-INDEPENDENT-TRIAL | 객관식 | ok |  | 독립시행 p=5/11 불변·오답 p² 감소 방향 정합. 수문/인수 코드 느슨 관찰 |
| `wm-misc-eval-mc-c7feb6c01121` | PROB-INDEPENDENT-TRIAL | 객관식 | ok |  | 독립시행 p=2/7 불변·오답 p² 감소 방향 정합. 수문/인수 코드 느슨 관찰 |
| `wm-misc-eval-mc-dd613a110047` | PROB-INDEPENDENT-TRIAL | 객관식 | ok |  | 독립시행 p=1/10 불변·오답 p² 감소 방향 정합. 수문/인수 코드 느슨 관찰 |
| `wm-misc-eval-mc-439ee7947bc7` | PROB-INDEPENDENT-TRIAL | 객관식 | ok |  | 독립시행 p=2/5 불변·오답 p² 감소 방향 정합. 수문/인수 코드 느슨 관찰 |
| `wm-misc-eval-mc-58a1985da786` | REMAINDER-THEOREM | 객관식 | defect | grammar_break | 조사 받침 오류: '(x-6)로'·'f(-6)로'→'으로'(육). 수학·오답 귀속 정합 |
| `wm-misc-eval-mc-432668753f4b` | REMAINDER-THEOREM | 객관식 | defect | grammar_break | 조사 받침 오류: '7 를'→'을'(칠). 수학·오답 귀속 정합 |
| `wm-misc-eval-mc-c89de485548b` | REMAINDER-THEOREM | 객관식 | defect | grammar_break | 조사 받침 오류: '(x-6)로'→'으로'·'7 를'→'을'. 수학·오답 귀속 정합 |
| `wm-misc-eval-mc-22a80d7acb1c` | REMAINDER-THEOREM | 객관식 | defect | grammar_break | 조사 받침 오류: '7 를'→'을'(칠). 수학·오답 귀속 정합 |
| `wm-misc-eval-mc-e7150e7783a7` | SAME-ITEM-PERM | 객관식 | ok |  | n!/(p!q!)=1001 검산·오답 n! 정합. 직수04-01 맥락 한정 귀속 관찰 |
| `wm-misc-eval-mc-aa997119255b` | SAME-ITEM-PERM | 객관식 | ok |  | n!/(p!q!)=66 검산·오답 n! 정합. 직수04-01 맥락 한정 귀속 관찰 |
| `wm-misc-eval-mc-991892a94888` | SAME-ITEM-PERM | 객관식 | ok |  | n!/(p!q!)=15 검산·오답 n! 정합. 직수04-01 맥락 한정 귀속 관찰 |
| `wm-misc-eval-mc-cb74f7591a3c` | SAME-ITEM-PERM | 객관식 | ok |  | n!/(p!q!)=84 검산·오답 n! 정합. 직수04-01 맥락 한정 귀속 관찰 |
| `wm-misc-eval-mc-fcd6285b59bd` | SCALE-AREA | 객관식 | defect | standard_tag_error | 성취기준 오귀속: 9수02-07(정비례·반비례)≠닮음 넓이비(정본 9수03-12). 수학·오답 정합 |
| `wm-misc-eval-mc-6645c8b0ca5f` | SCALE-AREA | 객관식 | defect | standard_tag_error | 성취기준 오귀속: 9수02-07(정비례·반비례)≠닮음 넓이비(정본 9수03-12). 수학·오답 정합 |
| `wm-misc-eval-mc-ad4661e1a9be` | SCALE-AREA | 객관식 | defect | standard_tag_error | 성취기준 오귀속: 9수02-07(정비례·반비례)≠닮음 넓이비(정본 9수03-12). 조사 '17 를'→'을'(칠) |
| `wm-misc-eval-mc-26ec2431182d` | SCALE-AREA | 객관식 | defect | standard_tag_error | 성취기준 오귀속: 9수02-07(정비례·반비례)≠닮음 넓이비(정본 9수03-12). 수학·오답 정합 |
| `wm-misc-eval-mc-f821cf97f33b` | SCALE-VOLUME | 객관식 | defect | grammar_break | 조사 받침 오류: '20 로'→'으로'(이십). 수학·오답 귀속 정합 |
| `wm-misc-eval-mc-fde09cff6828` | SCALE-VOLUME | 객관식 | ok |  | 부피비 k³=3375 검산·오답 k(선형) 정합 |
| `wm-misc-eval-mc-1a77597ec643` | SCALE-VOLUME | 객관식 | ok |  | 부피비 k³=21952 검산·오답 k(선형) 정합 |
| `wm-misc-eval-mc-d39bfc467d74` | SCALE-VOLUME | 객관식 | defect | grammar_break | 조사 받침 오류: '23 로'→'으로'(삼). 수학·오답 귀속 정합 |
| `wm-misc-eval-mc-f8271784adee` | SQRT-POS | 객관식 | ok |  | √(x²)=·x·=15 검산·오답 -a 정합 |
| `wm-misc-eval-mc-d17a4f49d401` | SQRT-POS | 객관식 | defect | grammar_break | 조사 받침 오류: '-28 가'→'이'(팔). 수학·오답 귀속 정합 |
| `wm-misc-eval-mc-8b7513124329` | SQRT-POS | 객관식 | defect | grammar_break | 조사 받침 오류: '-20 가'→'이'(이십). 수학·오답 귀속 정합 |
| `wm-misc-eval-mc-b72d33532925` | SQRT-POS | 객관식 | ok |  | √(x²)=·x·=12 검산·오답 -a 정합 |
| `wm-misc-eval-mc-d548855e7457` | SQRT-SUM | 객관식 | defect | grammar_break | 조사 받침 오류: '10000 는'→'은'(만). 수학·오답 귀속 정합 |
| `wm-misc-eval-mc-d80812504fe6` | SQRT-SUM | 객관식 | defect | grammar_break | 조사 받침 오류: '13456 는'→'은'·'84 이'→'가'. 수학·오답 귀속 정합 |
| `wm-misc-eval-mc-59c6c705956a` | SQRT-SUM | 객관식 | defect | grammar_break | 조사 받침 오류: '1156 는'→'은'(육). 수학·오답 귀속 정합 |
| `wm-misc-eval-mc-c596b689574a` | SQRT-SUM | 객관식 | defect | grammar_break | 조사 받침 오류: '1681 는'→'은'(일). 수학·오답 귀속 정합 |
| `wm-misc-eval-mc-d1b5c2fd6967` | SQUARE-DIFF | 객관식 | defect | grammar_break | 조사 받침 오류: '2²로'→'으로'(제곱). 수학·오답 귀속 정합 |
| `wm-misc-eval-mc-64104399ef79` | SQUARE-DIFF | 객관식 | defect | grammar_break | 조사 받침 오류: '2²로'→'으로'(제곱). 수학·오답 귀속 정합 |
| `wm-misc-eval-mc-467cf759cb91` | SQUARE-DIFF | 객관식 | defect | grammar_break | 조사 받침 오류: '2²로'→'으로'(제곱). 수학·오답 귀속 정합 |
| `wm-misc-eval-mc-debe3b18f20b` | SQUARE-DIFF | 객관식 | defect | grammar_break | 조사 받침 오류: '2²로'→'으로'(제곱). 수학·오답 귀속 정합 |
| `wm-misc-eval-mc-bbb9f4302a60` | SUBTRACT-NEG | 객관식 | ok |  | a-(-b)=12 검산·오답 a-b 정합. 9수01-03 개념 코드 관찰 |
| `wm-misc-eval-mc-91082d61f63b` | SUBTRACT-NEG | 객관식 | ok |  | a-(-b)=29 검산·오답 a-b 정합. 9수01-03 개념 코드 관찰 |
| `wm-misc-eval-mc-18c1c5ea1579` | SUBTRACT-NEG | 객관식 | ok |  | a-(-b)=15 검산·오답 a-b 정합. 9수01-03 개념 코드 관찰 |
| `wm-misc-eval-mc-5b336130f36c` | SUBTRACT-NEG | 객관식 | ok |  | a-(-b)=31 검산·오답 a-b 정합. 9수01-03 개념 코드 관찰 |
| `wm-misc-eval-mc-d172ba122598` | TRANSPOSE-SIGN | 객관식 | defect | standard_tag_error | 성취기준 오귀속: 9수02-13(연립·미지수2)≠일차방정식(정본 9수02-04). 조사 '10를'→'을'·'10로'→'으로' |
| `wm-misc-eval-mc-3f6fe185706e` | TRANSPOSE-SIGN | 객관식 | defect | standard_tag_error | 성취기준 오귀속: 9수02-13(연립·미지수2)≠일차방정식(정본 9수02-04). 수학·오답 정합 |
| `wm-misc-eval-mc-832935085189` | TRANSPOSE-SIGN | 객관식 | defect | standard_tag_error | 성취기준 오귀속: 9수02-13(연립·미지수2)≠일차방정식(정본 9수02-04). 수학·오답 정합 |
| `wm-misc-eval-mc-6c39c9b22325` | TRANSPOSE-SIGN | 객관식 | defect | standard_tag_error | 성취기준 오귀속: 9수02-13(연립·미지수2)≠일차방정식(정본 9수02-04). 수학·오답 정합 |
| `wm-misc-eval-mc-99495abd77df` | TRAPEZOID-AREA | 객관식 | defect | standard_tag_error | 성취기준 오귀속: 9수03-12(닮음)≠사다리꼴 넓이(정본 6수03-14). 수학·오답 정합 |
| `wm-misc-eval-mc-e1d78ee63b31` | TRAPEZOID-AREA | 객관식 | defect | standard_tag_error | 성취기준 오귀속: 9수03-12(닮음)≠사다리꼴 넓이(정본 6수03-14). 수학·오답 정합 |
| `wm-misc-eval-mc-009769d8362a` | TRAPEZOID-AREA | 객관식 | defect | standard_tag_error | 성취기준 오귀속: 9수03-12(닮음)≠사다리꼴 넓이(정본 6수03-14). 조사 '81 가'→'이'(일) |
| `wm-misc-eval-mc-46df9a573646` | TRAPEZOID-AREA | 객관식 | defect | standard_tag_error | 성취기준 오귀속: 9수03-12(닮음)≠사다리꼴 넓이(정본 6수03-14). 조사 '198 가'→'이'(팔) |
| `wm-misc-eval-mc-882bae94d3be` | TRIG-ADD | 객관식 | ok |  | 덧셈정리 SymPy 검산 일치·오답 k(sinA+sinB) 정합·4값 상이. '1π/12' 표기 경미 |
| `wm-misc-eval-mc-09c991afab66` | TRIG-ADD | 객관식 | ok |  | 덧셈정리 SymPy 검산 일치·오답 k(sinA+sinB) 정합·4값 상이. '1π/12' 표기 경미 |
| `wm-misc-eval-mc-7e22bbdbc3c4` | TRIG-ADD | 객관식 | ok |  | 덧셈정리 SymPy 검산 일치·오답 k(sinA+sinB) 정합·4값 상이. '1π/12' 표기 경미 |
| `wm-misc-eval-mc-a62b1a02560c` | TRIG-ADD | 객관식 | ok |  | 덧셈정리 SymPy 검산 일치·오답 k(sinA+sinB) 정합·4값 상이. |
| `wm-misc-eval-mc-eba865a498da` | TRIG-PERIOD | 객관식 | defect | standard_tag_error | 성취기준 오귀속: 12미적Ⅱ-02-02(덧셈정리)≠sin bx 주기(정본 12대수02-02). 조사 '26 를'→'을'(육) |
| `wm-misc-eval-mc-5b4e9d794b6e` | TRIG-PERIOD | 객관식 | defect | standard_tag_error | 성취기준 오귀속: 12미적Ⅱ-02-02(덧셈정리)≠sin bx 주기(정본 12대수02-02). 조사 '6 를'→'을'(육) |
| `wm-misc-eval-mc-fb0c9a9199d5` | TRIG-PERIOD | 객관식 | defect | standard_tag_error | 성취기준 오귀속: 12미적Ⅱ-02-02(덧셈정리)≠sin bx 주기(정본 12대수02-02). 조사 '20 를'→'을'(이십) |
| `wm-misc-eval-mc-4907b5b4783e` | TRIG-PERIOD | 객관식 | defect | standard_tag_error | 성취기준 오귀속: 12미적Ⅱ-02-02(덧셈정리)≠sin bx 주기(정본 12대수02-02). 조사 '23 를'→'을'(삼) |
| `wm-misc-eval-mc-e4d6a7306133` | VIETA-SUM | 객관식 | defect | standard_tag_error | 성취기준 오귀속: 10공수1-02-08(연립이차)≠근과계수(정본 10공수1-02-03). 수학·오답 정합 |
| `wm-misc-eval-mc-b71ed8d5999a` | VIETA-SUM | 객관식 | defect | standard_tag_error | 성취기준 오귀속: 10공수1-02-08(연립이차)≠근과계수(정본 10공수1-02-03). 조사 '23로'→'으로'(삼) |
| `wm-misc-eval-mc-7a23f189f48f` | VIETA-SUM | 객관식 | defect | standard_tag_error | 성취기준 오귀속: 10공수1-02-08(연립이차)≠근과계수(정본 10공수1-02-03). 수학·오답 정합 |
| `wm-misc-eval-mc-15be759e7275` | VIETA-SUM | 객관식 | defect | standard_tag_error | 성취기준 오귀속: 10공수1-02-08(연립이차)≠근과계수(정본 10공수1-02-03). 수학·오답 정합 |

## 문항별 판정 — conceptual (200)

| slug | 도메인 | 형식 | verdict | 결함류 | 비고 |
|---|---|---|---|---|---|
| `wm-count-mc-a8ea171c0733` | DIFFERENTIABILITY | 객관식 | defect | grammar_break | 발문 '1 가'→읽기상 '이'(조사파손·240선례 값가 동형). 검산 답0·오개념1 정합 |
| `wm-count-mc-c5d1c5474e3d` | DIFFERENTIABILITY | 객관식 | defect | grammar_break | 발문 '3 가'→읽기상 '이'(조사파손·240선례 값가 동형). 검산 답0·오개념1 정합 |
| `wm-count-mc-47fb8baea5e8` | DIFFERENTIABILITY | 객관식 | defect | grammar_break | 발문 '3 가'→읽기상 '이'(조사파손·240선례 값가 동형). 검산 답0·오개념1 정합 |
| `wm-count-mc-d55fd6a4a872` | DIFFERENTIABILITY | 객관식 | ok |  | x=4 꺾임 좌-1·우+1 재확인 답0. 오답1=연속⇒미분가능 오인 정합. 선지2·3 필러 경미 |
| `wm-count-mc-8bc63a0d0f21` | DIFFERENTIABILITY | 객관식 | ok |  | x=3 꺾임 좌-1·우+1 재확인 답0. 오답1=연속⇒미분가능 오인 정합. 선지2·3 필러 경미 |
| `wm-count-mc-66e68084c47f` | DIFFERENTIABILITY | 객관식 | ok |  | x=4 꺾임 좌-1·우+1 재확인 답0. 오답1=연속⇒미분가능 오인 정합. 선지2·3 필러 경미 |
| `wm-count-mc-6c2797e2bb0d` | DIFFERENTIABILITY | 객관식 | defect | grammar_break | 발문 '·x - 1· 가'→읽기상 '이'(조사파손·240선례 값가 동형). 검산 답0·오개념1 정합 |
| `wm-count-mc-05ecfdae47c4` | DIFFERENTIABILITY | 객관식 | defect | grammar_break | 발문 '1 가'→읽기상 '이'(조사파손·240선례 값가 동형). 검산 답0·오개념1 정합 |
| `wm-count-mc-8d68f1968df0` | DIFFERENTIABILITY | 객관식 | ok |  | x=2 꺾임 좌-1·우+1 재확인 답0. 오답1=연속⇒미분가능 오인 정합. 선지2·3 필러 경미 |
| `wm-count-mc-9044ffeda5fa` | DIFFERENTIABILITY | 객관식 | defect | grammar_break | 발문 '3 가'→읽기상 '이'(조사파손·240선례 값가 동형). 검산 답0·오개념1 정합 |
| `wm-count-mc-42a2d030810c` | DIFFERENTIABILITY | 객관식 | defect | grammar_break | 발문 '1 가'→읽기상 '이'(조사파손·240선례 값가 동형). 검산 답0·오개념1 정합 |
| `wm-count-mc-1666f0868455` | DIFFERENTIABILITY | 객관식 | ok |  | x=5 꺾임 좌-1·우+1 재확인 답0. 오답1=연속⇒미분가능 오인 정합. 선지2·3 필러 경미 |
| `wm-count-mc-d4bdb17ef9fa` | DIFFERENTIABILITY | 객관식 | defect | grammar_break | 발문 '1 가'→읽기상 '이'(조사파손·240선례 값가 동형). 검산 답0·오개념1 정합 |
| `wm-count-mc-39a8a38b6f80` | DIFFERENTIABILITY | 객관식 | ok |  | x=1 꺾임 좌-1·우+1 재확인 답0. 오답1=연속⇒미분가능 오인 정합. 선지2·3 필러 경미 |
| `wm-count-mc-7ba40bc47eff` | DISC-COUNT | 객관식 | ok |  | D=-56<0 재검산 실근0=답·해설 산술 정확. 오답2=늘2근 오인 정합 |
| `wm-count-mc-c0128385dbc5` | DISC-COUNT | 객관식 | ok |  | D=-44<0 재검산 실근0=답·해설 산술 정확. 오답2=늘2근 오인 정합 |
| `wm-count-mc-754f09c29e8c` | DISC-COUNT | 객관식 | ok |  | D=-23<0 재검산 실근0=답·해설 산술 정확. 오답2=늘2근 오인 정합. '1x'표기 경미 |
| `wm-count-mc-a66405fbcdec` | DISC-COUNT | 객관식 | ok |  | D=-3<0 재검산 실근0=답·해설 산술 정확. 오답2=늘2근 오인 정합. '1x'표기 경미 |
| `wm-count-mc-f06001d45394` | DISC-COUNT | 객관식 | ok |  | D=-40<0 재검산 실근0=답·해설 산술 정확. 오답2=늘2근 오인 정합. 난이도3.5 상단 관찰 |
| `wm-count-mc-f3f071b2dd3d` | DISC-COUNT | 객관식 | ok |  | D=-16<0 재검산 실근0=답·해설 산술 정확. 오답2=늘2근 오인 정합 |
| `wm-count-mc-5884bd1d07b7` | DISC-COUNT | 객관식 | ok |  | D=-19<0 재검산 실근0=답·해설 산술 정확. 오답2=늘2근 오인 정합. '1x'표기 경미 |
| `wm-count-mc-2e433c2ed44c` | DISC-COUNT | 객관식 | ok |  | D=-15<0 재검산 실근0=답·해설 산술 정확. 오답2=늘2근 오인 정합. '1x'표기 경미 |
| `wm-count-mc-b2173df0825f` | DISC-COUNT | 객관식 | ok |  | D=-4<0 재검산 실근0=답·해설 산술 정확. 오답2=늘2근 오인 정합 |
| `wm-count-mc-ec434678a80b` | DISC-COUNT | 객관식 | ok |  | D=-28<0 재검산 실근0=답·해설 산술 정확. 오답2=늘2근 오인 정합 |
| `wm-count-mc-2731097a6f7c` | DISC-COUNT | 객관식 | ok |  | D=-12<0 재검산 실근0=답·해설 산술 정확. 오답2=늘2근 오인 정합 |
| `wm-count-mc-5b932a3fa391` | DISC-COUNT | 객관식 | ok |  | D=-64<0 재검산 실근0=답·해설 산술 정확. 오답2=늘2근 오인 정합 |
| `wm-count-mc-efd1c8c0275b` | DISC-COUNT | 객관식 | ok |  | D=-27<0 재검산 실근0=답·해설 산술 정확. 오답2=늘2근 오인 정합. '1x'표기 경미 |
| `wm-count-mc-9783f638f343` | DISC-COUNT | 객관식 | ok |  | D=-11<0 재검산 실근0=답·해설 산술 정확. 오답2=늘2근 오인 정합. '1x'표기 경미 |
| `wm-count-mc-8b0823f4aab0` | DOMAIN-EXCLUDE | 객관식 | ok |  | 분모 근 x=2,3 SymPy 재확인 2개=답. 오답0=항상정의 오인 정합 |
| `wm-count-mc-506ef36304c6` | DOMAIN-EXCLUDE | 객관식 | ok |  | 분모 근 x=3,6 SymPy 재확인 2개=답. 오답0=항상정의 오인 정합. 부수코드 9수01-03 느슨(경미) |
| `wm-count-mc-508fd4bb7d78` | DOMAIN-EXCLUDE | 객관식 | ok |  | 분모 근 x=1,5 SymPy 재확인 2개=답. 오답0=항상정의 오인 정합 |
| `wm-count-mc-9678e452edb0` | DOMAIN-EXCLUDE | 객관식 | ok |  | 분모 근 x=2 SymPy 재확인 1개=답. 오답0=항상정의 오인 정합. 중복괄호 경미 |
| `wm-count-mc-5c3246113fa1` | DOMAIN-EXCLUDE | 객관식 | ok |  | 분모 근 x=1,6 SymPy 재확인 2개=답. 오답0=항상정의 오인 정합 |
| `wm-count-mc-ba13931e42cb` | DOMAIN-EXCLUDE | 객관식 | ok |  | 분모 근 x=2,6 SymPy 재확인 2개=답. 오답0=항상정의 오인 정합 |
| `wm-count-mc-5bbc84f64509` | DOMAIN-EXCLUDE | 객관식 | ok |  | 분모 근 x=1,2,3 SymPy 재확인 3개=답. 오답0=항상정의 오인 정합 |
| `wm-count-mc-2960ff860473` | DOMAIN-EXCLUDE | 객관식 | ok |  | 분모 근 x=5,6 SymPy 재확인 2개=답. 오답0=항상정의 오인 정합 |
| `wm-count-mc-ff94c451fe07` | DOMAIN-EXCLUDE | 객관식 | ok |  | 분모 근 x=7 SymPy 재확인 1개=답. 오답0=항상정의 오인 정합. 중복괄호 경미 |
| `wm-count-mc-b3cb16442169` | DOMAIN-EXCLUDE | 객관식 | ok |  | 분모 근 x=1,3 SymPy 재확인 2개=답. 오답0=항상정의 오인 정합 |
| `wm-count-mc-d89e1f00bcb8` | DOMAIN-EXCLUDE | 객관식 | ok |  | 분모 근 x=1,4 SymPy 재확인 2개=답. 오답0=항상정의 오인 정합 |
| `wm-count-mc-0dc7792dcb88` | DOMAIN-EXCLUDE | 객관식 | ok |  | 분모 근 x=4,6 SymPy 재확인 2개=답. 오답0=항상정의 오인 정합. 부수코드 9수01-03 느슨(경미) |
| `wm-count-mc-a3210ce0661e` | DOMAIN-EXCLUDE | 객관식 | ok |  | 분모 근 x=1,2 SymPy 재확인 2개=답. 오답0=항상정의 오인 정합 |
| `wm-count-mc-5be993f08f5c` | DOMAIN-EXCLUDE | 객관식 | ok |  | 분모 근 x=3,4 SymPy 재확인 2개=답. 오답0=항상정의 오인 정합 |
| `wm-count-mc-08efb9dad61c` | EXTREMUM-COUNT | 객관식 | ok |  | f'=3(x-4)² 부호불변→극값0 재확인=답. 오답1=임계점⇒극값 오인 정합 |
| `wm-count-mc-cb24cfc6ca52` | EXTREMUM-COUNT | 객관식 | ok |  | f'=3(x-1)² 부호불변→극값0 재확인=답. 오답1=임계점⇒극값 오인 정합 |
| `wm-count-mc-46a84b73c868` | EXTREMUM-COUNT | 객관식 | ok |  | f'=3(x-4)² 부호불변→극값0 재확인=답. 오답1=임계점⇒극값 오인 정합 |
| `wm-count-mc-f9668725c9a4` | EXTREMUM-COUNT | 객관식 | ok |  | f'=3(x-2)² 부호불변→극값0 재확인=답. 오답1=임계점⇒극값 오인 정합 |
| `wm-count-mc-77aaec37f6db` | EXTREMUM-COUNT | 객관식 | ok |  | f'=3(x-4)² 부호불변→극값0 재확인=답. 오답1=임계점⇒극값 오인 정합 |
| `wm-count-mc-4893d2f13d36` | EXTREMUM-COUNT | 객관식 | ok |  | f'=3(x-3)² 부호불변→극값0 재확인=답. 오답1=임계점⇒극값 오인 정합 |
| `wm-count-mc-dc6e715f4a59` | EXTREMUM-COUNT | 객관식 | ok |  | f'=3(x-2)² 부호불변→극값0 재확인=답. 오답1=임계점⇒극값 오인 정합 |
| `wm-count-mc-8d7ffb84269b` | EXTREMUM-COUNT | 객관식 | ok |  | f'=3(x-1)² 부호불변→극값0 재확인=답. 오답1=임계점⇒극값 오인 정합 |
| `wm-count-mc-3756b759c0e9` | EXTREMUM-COUNT | 객관식 | ok |  | f'=3(x-2)² 부호불변→극값0 재확인=답. 오답1=임계점⇒극값 오인 정합 |
| `wm-count-mc-f87be9df8190` | EXTREMUM-COUNT | 객관식 | ok |  | f'=3(x-1)² 부호불변→극값0 재확인=답. 오답1=임계점⇒극값 오인 정합 |
| `wm-count-mc-7e5531004130` | EXTREMUM-COUNT | 객관식 | ok |  | f'=3(x-4)² 부호불변→극값0 재확인=답. 오답1=임계점⇒극값 오인 정합 |
| `wm-count-mc-7e674cfd9a26` | EXTREMUM-COUNT | 객관식 | ok |  | f'=3(x-3)² 부호불변→극값0 재확인=답. 오답1=임계점⇒극값 오인 정합 |
| `wm-count-mc-18f041cc3f5f` | EXTREMUM-COUNT | 객관식 | ok |  | f'=3(x-1)² 부호불변→극값0 재확인=답. 오답1=임계점⇒극값 오인 정합 |
| `wm-count-mc-d8637fcfd4c4` | EXTREMUM-COUNT | 객관식 | ok |  | f'=3(x-4)² 부호불변→극값0 재확인=답. 오답1=임계점⇒극값 오인 정합 |
| `wm-count-mc-7dab1bc70051` | FUNC-INVERSE | 객관식 | defect | grammar_break | 발문 '3 가'→읽기상 '이'(조사파손·240선례 값가 동형). 검산 답0·오개념1 정합 |
| `wm-count-mc-fe942e7d70a6` | FUNC-INVERSE | 객관식 | defect | grammar_break | 발문 '3 가'→읽기상 '이'(조사파손·240선례 값가 동형). 검산 답0·오개념1 정합. '1x' 경미 |
| `wm-count-mc-333a1e7a7c8e` | FUNC-INVERSE | 객관식 | defect | grammar_break | 발문 '1 가'→읽기상 '이'(조사파손·240선례 값가 동형). 검산 답0·오개념1 정합 |
| `wm-count-mc-e0c68c666153` | FUNC-INVERSE | 객관식 | ok |  | 이차 꼭짓점 대칭→일대일 아님 재확인 답0. 오개념1 귀속=역함수존재⇒1 추론(간접 성립). '1x' 경미 |
| `wm-count-mc-8942a5de7198` | FUNC-INVERSE | 객관식 | ok |  | 이차 꼭짓점 대칭→일대일 아님 재확인 답0. 오개념1 귀속=역함수존재⇒1 추론(간접 성립) |
| `wm-count-mc-5b4a3436ff0b` | FUNC-INVERSE | 객관식 | defect | grammar_break | 발문 '3 가'→읽기상 '이'(조사파손·240선례 값가 동형). 검산 답0·오개념1 정합 |
| `wm-count-mc-3a1befcf3172` | FUNC-INVERSE | 객관식 | defect | grammar_break | 발문 '3 가'→읽기상 '이'(조사파손·240선례 값가 동형). 검산 답0·오개념1 정합 |
| `wm-count-mc-091d35973389` | FUNC-INVERSE | 객관식 | ok |  | 이차 꼭짓점 대칭→일대일 아님 재확인 답0. 오개념1 귀속=역함수존재⇒1 추론(간접 성립) |
| `wm-count-mc-8af1df9850c2` | FUNC-INVERSE | 객관식 | ok |  | 이차 꼭짓점 대칭→일대일 아님 재확인 답0. 오개념1 귀속=역함수존재⇒1 추론(간접 성립) |
| `wm-count-mc-5d936cee4d34` | FUNC-INVERSE | 객관식 | ok |  | 이차 꼭짓점 대칭→일대일 아님 재확인 답0. 오개념1 귀속=역함수존재⇒1 추론(간접 성립) |
| `wm-count-mc-69e8f2a94f02` | FUNC-INVERSE | 객관식 | defect | grammar_break | 발문 'x^2 가'→읽기상 '이'(조사파손·240선례 값가 동형). 검산 답0·오개념1 정합 |
| `wm-count-mc-3a8b55940a78` | FUNC-INVERSE | 객관식 | ok |  | 이차 꼭짓점 대칭→일대일 아님 재확인 답0. 오개념1 귀속=역함수존재⇒1 추론(간접 성립) |
| `wm-count-mc-f27cabdcc411` | FUNC-INVERSE | 객관식 | ok |  | 이차 꼭짓점 대칭→일대일 아님 재확인 답0. 오개념1 귀속=역함수존재⇒1 추론(간접 성립) |
| `wm-count-mc-e78c1984564e` | FUNC-INVERSE | 객관식 | ok |  | 이차 꼭짓점 대칭→일대일 아님 재확인 답0. 오개념1 귀속=역함수존재⇒1 추론(간접 성립). '1x' 경미 |
| `wm-count-mc-6ad8decf52f4` | GEO-SERIES-CONV | 객관식 | ok |  | ·r·=7/4>1→발산 재확인 답0·해설 정합. 오답1=늘수렴 오인 정합. 선지2·3 필러 경미 |
| `wm-count-mc-bae1a44c1b31` | GEO-SERIES-CONV | 객관식 | ok |  | ·r·=3/2>1→발산 재확인 답0·해설 정합. 오답1=늘수렴 오인 정합. 선지2·3 필러 경미 |
| `wm-count-mc-72f2098a1474` | GEO-SERIES-CONV | 객관식 | ok |  | ·r·=7>1→발산 재확인 답0·해설 정합. 오답1=늘수렴 오인 정합. 선지2·3 필러 경미 |
| `wm-count-mc-69f41243aeb6` | GEO-SERIES-CONV | 객관식 | ok |  | ·r·=7/2>1→발산 재확인 답0·해설 정합. 오답1=늘수렴 오인 정합. 선지2·3 필러 경미 |
| `wm-count-mc-ae3f742bcd2d` | GEO-SERIES-CONV | 객관식 | ok |  | ·r·=5/2>1→발산 재확인 답0·해설 정합. 오답1=늘수렴 오인 정합. 선지2·3 필러 경미 |
| `wm-count-mc-33e6aae006ed` | GEO-SERIES-CONV | 객관식 | ok |  | ·r·=10/3>1→발산 재확인 답0·해설 정합. 오답1=늘수렴 오인 정합. 선지2·3 필러 경미 |
| `wm-count-mc-50ab97ae8874` | GEO-SERIES-CONV | 객관식 | ok |  | ·r·=11/3>1→발산 재확인 답0·해설 정합. 오답1=늘수렴 오인 정합. 선지2·3 필러 경미 |
| `wm-count-mc-2a6d046384b3` | GEO-SERIES-CONV | 객관식 | ok |  | ·r·=9/2>1→발산 재확인 답0·해설 정합. 오답1=늘수렴 오인 정합. 선지2·3 필러 경미 |
| `wm-count-mc-e5551b8b79cc` | GEO-SERIES-CONV | 객관식 | ok |  | ·r·=13/3>1→발산 재확인 답0·해설 정합. 오답1=늘수렴 오인 정합. 선지2·3 필러 경미 |
| `wm-count-mc-74b1318a4008` | GEO-SERIES-CONV | 객관식 | ok |  | ·r·=8>1→발산 재확인 답0·해설 정합. 오답1=늘수렴 오인 정합. 선지2·3 필러 경미 |
| `wm-count-mc-53db22dcfbb0` | GEO-SERIES-CONV | 객관식 | ok |  | ·r·=5>1→발산 재확인 답0·해설 정합. 오답1=늘수렴 오인 정합. 선지2·3 필러 경미 |
| `wm-count-mc-2d39c3f2d7a2` | GEO-SERIES-CONV | 객관식 | ok |  | ·r·=11>1→발산 재확인 답0·해설 정합. 오답1=늘수렴 오인 정합. 선지2·3 필러 경미 |
| `wm-count-mc-56c418c4b302` | GEO-SERIES-CONV | 객관식 | ok |  | ·r·=7/3>1→발산 재확인 답0·해설 정합. 오답1=늘수렴 오인 정합. 선지2·3 필러 경미 |
| `wm-count-mc-a57f23dcbd50` | GEOM-SIMILAR-CONGRUENT | 객관식 | ok |  | 닮음비 4/3≠1→합동 아님 재확인 답0. 오답1=닮음⇒합동 오인 정합 |
| `wm-count-mc-d6f8335950ab` | GEOM-SIMILAR-CONGRUENT | 객관식 | ok |  | 닮음비 5/4≠1→합동 아님 재확인 답0. 오답1=닮음⇒합동 오인 정합. 중2내용 난이도3.4 상단 관찰 |
| `wm-count-mc-28a528fea775` | GEOM-SIMILAR-CONGRUENT | 객관식 | ok |  | 닮음비 9/2≠1→합동 아님 재확인 답0. 오답1=닮음⇒합동 오인 정합 |
| `wm-count-mc-3ea9f4e78f12` | GEOM-SIMILAR-CONGRUENT | 객관식 | ok |  | 닮음비 3≠1→합동 아님 재확인 답0. 오답1=닮음⇒합동 오인 정합 |
| `wm-count-mc-211a93382d0d` | GEOM-SIMILAR-CONGRUENT | 객관식 | ok |  | 닮음비 5/2≠1→합동 아님 재확인 답0. 오답1=닮음⇒합동 오인 정합 |
| `wm-count-mc-1effbe34a1e6` | GEOM-SIMILAR-CONGRUENT | 객관식 | ok |  | 닮음비 3/2≠1→합동 아님 재확인 답0. 오답1=닮음⇒합동 오인 정합 |
| `wm-count-mc-c100b0550cf0` | GEOM-SIMILAR-CONGRUENT | 객관식 | ok |  | 닮음비 7≠1→합동 아님 재확인 답0. 오답1=닮음⇒합동 오인 정합 |
| `wm-count-mc-e471e4d2327f` | GEOM-SIMILAR-CONGRUENT | 객관식 | ok |  | 닮음비 5≠1→합동 아님 재확인 답0. 오답1=닮음⇒합동 오인 정합 |
| `wm-count-mc-c74707786c09` | GEOM-SIMILAR-CONGRUENT | 객관식 | ok |  | 닮음비 9≠1→합동 아님 재확인 답0. 오답1=닮음⇒합동 오인 정합. 중2내용 난이도3.5 상단 관찰 |
| `wm-count-mc-9660a0bc2575` | GEOM-SIMILAR-CONGRUENT | 객관식 | ok |  | 닮음비 1/4≠1→합동 아님 재확인 답0. 오답1=닮음⇒합동 오인 정합 |
| `wm-count-mc-9d33ea5d7257` | GEOM-SIMILAR-CONGRUENT | 객관식 | ok |  | 닮음비 1/2≠1→합동 아님 재확인 답0. 오답1=닮음⇒합동 오인 정합 |
| `wm-count-mc-11ed3612c95f` | GEOM-SIMILAR-CONGRUENT | 객관식 | ok |  | 닮음비 7/2≠1→합동 아님 재확인 답0. 오답1=닮음⇒합동 오인 정합. 중2내용 난이도3.4 상단 관찰 |
| `wm-count-mc-b5541ed7f313` | GEOM-SIMILAR-CONGRUENT | 객관식 | ok |  | 닮음비 7/4≠1→합동 아님 재확인 답0. 오답1=닮음⇒합동 오인 정합 |
| `wm-count-mc-61f9d07f97f4` | INEQ-SIGN-FLIP | 객관식 | ok |  | -4x<7: 음수 나눗셈 반전→x>꼴=1 재확인·해설 정합. 오답0=부호유지 오인 정합 |
| `wm-count-mc-d89173a2b37f` | INEQ-SIGN-FLIP | 객관식 | ok |  | -5x<2: 음수 나눗셈 반전→x>꼴=1 재확인·해설 정합. 오답0=부호유지 오인 정합 |
| `wm-count-mc-c760611d4098` | INEQ-SIGN-FLIP | 객관식 | ok |  | -5x<4: 음수 나눗셈 반전→x>꼴=1 재확인·해설 정합. 오답0=부호유지 오인 정합 |
| `wm-count-mc-8737a8a57710` | INEQ-SIGN-FLIP | 객관식 | ok |  | -3x<5: 음수 나눗셈 반전→x>꼴=1 재확인·해설 정합. 오답0=부호유지 오인 정합 |
| `wm-count-mc-d9ade4c9aab2` | INEQ-SIGN-FLIP | 객관식 | ok |  | -2x<4 해 방향 x>꼴 SymPy 재확인·답 1 일치·미반전 오개념 태깅(선지0) 정합 |
| `wm-count-mc-6605c19b9963` | INEQ-SIGN-FLIP | 객관식 | defect | grammar_break | 해설 '-3로'→'-3으로' 조사 파손(삼+으로·josa 모듈 대조). 방향판정·답1·태깅은 정합 |
| `wm-count-mc-15288f22fa08` | INEQ-SIGN-FLIP | 객관식 | ok |  | -2x<1 해 방향 x>꼴 SymPy 재확인·답 1 일치·미반전 오개념 태깅(선지0) 정합 |
| `wm-count-mc-24c096f4dcf3` | INEQ-SIGN-FLIP | 객관식 | ok |  | -2x<5 해 방향 x>꼴 SymPy 재확인·답 1 일치·미반전 오개념 태깅(선지0) 정합 |
| `wm-count-mc-55072078f563` | INEQ-SIGN-FLIP | 객관식 | ok |  | -2x<7 해 방향 x>꼴 SymPy 재확인·답 1 일치·미반전 오개념 태깅(선지0) 정합 |
| `wm-count-mc-ff2eeb55cb14` | INEQ-SIGN-FLIP | 객관식 | defect | grammar_break | 해설 '-3로'→'-3으로' 조사 파손(삼+으로·josa 모듈 대조). 방향판정·답1·태깅은 정합 |
| `wm-count-mc-2fcd5c4f9175` | INEQ-SIGN-FLIP | 객관식 | ok |  | -2x<2 해 방향 x>꼴 SymPy 재확인·답 1 일치·미반전 오개념 태깅(선지0) 정합 |
| `wm-count-mc-55ff6ae50de7` | INEQ-SIGN-FLIP | 객관식 | ok |  | -2x<8 해 방향 x>꼴 SymPy 재확인·답 1 일치·미반전 오개념 태깅(선지0) 정합 |
| `wm-count-mc-ae6568d8d8a6` | INEQ-SIGN-FLIP | 객관식 | defect | grammar_break | 해설 '-3로'→'-3으로' 조사 파손(삼+으로·josa 모듈 대조). 방향판정·답1·태깅은 정합 |
| `wm-count-mc-0b1c1bfefa43` | LIMIT-VALUE | 객관식 | defect | explanation_slip | 해설 극한값 2 거짓·실제 -2(SymPy) — 생성기 b−a 부호 버그. 답 0 유지. 발문 'f(1) 가'→'이' 조사 파손도 |
| `wm-count-mc-c492fb956991` | LIMIT-VALUE | 객관식 | defect | explanation_slip | 해설 극한값 2 거짓·실제 -2(SymPy) — 생성기 b−a 부호 버그. 답 0 유지 |
| `wm-count-mc-6267f269dc6e` | LIMIT-VALUE | 객관식 | defect | explanation_slip | 해설 극한값 -1 거짓·실제 1(SymPy) — 생성기 b−a 부호 버그. 답 0 유지 |
| `wm-count-mc-1e1b6490e05f` | LIMIT-VALUE | 객관식 | defect | explanation_slip | 해설 극한값 -1 거짓·실제 1(SymPy) — 생성기 b−a 부호 버그. 답 0 유지. 발문 'f(3) 가'→'이' 조사 파손도 |
| `wm-count-mc-e3b6db54f7be` | LIMIT-VALUE | 객관식 | defect | explanation_slip | 해설 극한값 3 거짓·실제 -3(SymPy) — 생성기 b−a 부호 버그. 답 0 유지 |
| `wm-count-mc-d41ce7394d42` | LIMIT-VALUE | 객관식 | defect | explanation_slip | 해설 극한값 3 거짓·실제 -3(SymPy) — 생성기 b−a 부호 버그. 답 0 유지. 발문 'f(1) 가'→'이' 조사 파손도 |
| `wm-count-mc-7efa69bc4bff` | LIMIT-VALUE | 객관식 | defect | explanation_slip | 해설 극한값 -1 거짓·실제 1(SymPy) — 생성기 b−a 부호 버그. 답 0 유지 |
| `wm-count-mc-c65f6b02fdf8` | LIMIT-VALUE | 객관식 | defect | explanation_slip | 해설 극한값 2 거짓·실제 -2(SymPy) — 생성기 b−a 부호 버그. 답 0 유지 |
| `wm-count-mc-e6a53165fb21` | LIMIT-VALUE | 객관식 | defect | explanation_slip | 해설 극한값 -2 거짓·실제 2(SymPy) — 생성기 b−a 부호 버그. 답 0 유지 |
| `wm-count-mc-4dda9166011e` | LIMIT-VALUE | 객관식 | defect | explanation_slip | 해설 극한값 1 거짓·실제 -1(SymPy) — 생성기 b−a 부호 버그. 답 0 유지. 발문 'f(1) 가'→'이' 조사 파손도 |
| `wm-count-mc-61bbe52e9f76` | LIMIT-VALUE | 객관식 | defect | explanation_slip | 해설 극한값 2 거짓·실제 -2(SymPy) — 생성기 b−a 부호 버그. 답 0 유지. 발문 'f(3) 가'→'이' 조사 파손도 |
| `wm-count-mc-9f2491e9ca89` | LIMIT-VALUE | 객관식 | defect | explanation_slip | 해설 극한값 -2 거짓·실제 2(SymPy) — 생성기 b−a 부호 버그. 답 0 유지 |
| `wm-count-mc-920af6281e1b` | LIMIT-VALUE | 객관식 | defect | explanation_slip | 해설 극한값 1 거짓·실제 -1(SymPy) — 생성기 b−a 부호 버그. 답 0 유지. 발문 'f(3) 가'→'이' 조사 파손도 |
| `wm-count-mc-4887e176d9ac` | PROB-CONDITIONAL | 객관식 | defect | condition_mismatch | 전제 비실현: P(A∩B)=1/4>P(A)=1/12, 해설 P(B·A)=3(확률>1) — 모순 설정 |
| `wm-count-mc-c164e8bfd25c` | PROB-CONDITIONAL | 객관식 | defect | grammar_break | 해설 '1/2 와 달라'→'과' 조사 파손(일+과·josa 모듈 대조). P(B·A)=2/3 계산·논리 정합 |
| `wm-count-mc-fd13b0a6017d` | PROB-CONDITIONAL | 객관식 | defect | condition_mismatch | 전제 비실현: P(A∩B)=7/24>P(A)=1/6, 해설 P(B·A)=7/4(확률>1) — 모순 설정 |
| `wm-count-mc-d11aaf044291` | PROB-CONDITIONAL | 객관식 | defect | grammar_break | 해설 '1/2 와 달라'→'과' 조사 파손(일+과·josa 모듈 대조). P(B·A)=3/4 계산·논리 정합 |
| `wm-count-mc-062c4123a07e` | PROB-CONDITIONAL | 객관식 | defect | condition_mismatch | 전제 비실현: P(A∩B)=7/24>P(A)=1/4, 해설 P(B·A)=7/6(확률>1) — 모순 설정 |
| `wm-count-mc-b8048facc7c8` | PROB-CONDITIONAL | 객관식 | defect | grammar_break | 해설 '1/2 와 달라'→'과' 조사 파손(일+과·josa 모듈 대조). P(B·A)=1/6 계산·논리 정합 |
| `wm-count-mc-125926984e2b` | PROB-CONDITIONAL | 객관식 | defect | condition_mismatch | 전제 비실현: P(A∩B)=1/3>P(A)=1/12, 해설 P(B·A)=4(확률>1) — 모순 설정 |
| `wm-count-mc-b7fac2bb2314` | PROB-CONDITIONAL | 객관식 | defect | grammar_break | 해설 '1/2 와 달라'→'과' 조사 파손(일+과·josa 모듈 대조). P(B·A)=3/8 계산·논리 정합 |
| `wm-count-mc-fc57a37ed602` | PROB-CONDITIONAL | 객관식 | defect | condition_mismatch | 전제 비실현: P(A∩B)=5/24>P(A)=1/12, 해설 P(B·A)=5/2(확률>1) — 모순 설정 |
| `wm-count-mc-82e17206621e` | PROB-CONDITIONAL | 객관식 | defect | condition_mismatch | 전제 비실현: P(A∩B)=1/3>P(A)=1/4, 해설 P(B·A)=4/3(확률>1) — 모순 설정 |
| `wm-count-mc-d93bafff8da7` | PROB-CONDITIONAL | 객관식 | defect | grammar_break | 해설 '1/2 와 달라'→'과' 조사 파손(일+과·josa 모듈 대조). P(B·A)=5/6 계산·논리 정합 |
| `wm-count-mc-2eb623089944` | PROB-CONDITIONAL | 객관식 | defect | condition_mismatch | 전제 비실현: P(A∩B)=1/6>P(A)=1/12, 해설 P(B·A)=2(확률>1) — 모순 설정 |
| `wm-count-mc-08f9e494da94` | PROB-CONDITIONAL | 객관식 | defect | grammar_break | 해설 '1/2 와 달라'→'과' 조사 파손(일+과·josa 모듈 대조). P(B·A)=1 계산·논리 정합 |
| `wm-count-mc-bf05bab38ae0` | PROB-INDEPENDENCE | 객관식 | ok |  | 배반 실현가능(합 1/2≤1)·곱 1/18 산술 일치·비독립 판정 정합 |
| `wm-count-mc-45603e654825` | PROB-INDEPENDENCE | 객관식 | ok |  | 배반 실현가능(합 7/12≤1)·곱 5/72 산술 일치·비독립 판정 정합 |
| `wm-count-mc-d8b634bea783` | PROB-INDEPENDENCE | 객관식 | ok |  | 배반 실현가능(합 5/6≤1)·곱 7/48 산술 일치·비독립 판정 정합 |
| `wm-count-mc-91c8329dee6e` | PROB-INDEPENDENCE | 객관식 | ok |  | 배반 실현가능(합 1/2≤1)·곱 5/144 산술 일치·비독립 판정 정합 |
| `wm-count-mc-1107cfd02ba9` | PROB-INDEPENDENCE | 객관식 | ok |  | 배반 실현가능(합 1/3≤1)·곱 1/36 산술 일치·비독립 판정 정합 |
| `wm-count-mc-e10c119cd756` | PROB-INDEPENDENCE | 객관식 | ok |  | 배반 실현가능(합 3/4≤1)·곱 7/72 산술 일치·비독립 판정 정합 |
| `wm-count-mc-21eeeedc8d64` | PROB-INDEPENDENCE | 객관식 | ok |  | 배반 실현가능(합 5/12≤1)·곱 1/24 산술 일치·비독립 판정 정합 |
| `wm-count-mc-f590d3a04627` | PROB-INDEPENDENCE | 객관식 | ok |  | 배반 실현가능(합 2/3≤1)·곱 1/12 산술 일치·비독립 판정 정합 |
| `wm-count-mc-b9649c189260` | PROB-INDEPENDENCE | 객관식 | ok |  | 배반 실현가능(합 5/12≤1)·곱 1/36 산술 일치·비독립 판정 정합 |
| `wm-count-mc-04ec42d57181` | PROB-INDEPENDENCE | 객관식 | ok |  | 배반 실현가능(합 1/2≤1)·곱 1/16 산술 일치·비독립 판정 정합 |
| `wm-count-mc-95aebbbb2a22` | PROB-INDEPENDENCE | 객관식 | ok |  | 배반 실현가능(합 1/6≤1)·곱 1/144 산술 일치·비독립 판정 정합 |
| `wm-count-mc-46e6822f04bd` | PROB-INDEPENDENCE | 객관식 | ok |  | 배반 실현가능(합 1/4≤1)·곱 1/72 산술 일치·비독립 판정 정합 |
| `wm-count-mc-3288da3ccafd` | PROB-INDEPENDENCE | 객관식 | ok |  | 배반 실현가능(합 7/12≤1)·곱 1/12 산술 일치·비독립 판정 정합 |
| `wm-count-mc-1344cc28d369` | ROOT-LOSS-DIVIDE | 객관식 | ok |  | x(4x-7)=0 두 근 SymPy 재확인·근 상실 오개념 태깅 정합 |
| `wm-count-mc-adeed8046297` | ROOT-LOSS-DIVIDE | 객관식 | ok |  | 근 0,7 2개 SymPy 재확인. 해설 '1x'·'7/1' 미간약 표기 어색(참·경미) |
| `wm-count-mc-e7f7913d8942` | ROOT-LOSS-DIVIDE | 객관식 | ok |  | x(4x-5)=0 두 근 SymPy 재확인·근 상실 오개념 태깅 정합 |
| `wm-count-mc-97c07a7e24d2` | ROOT-LOSS-DIVIDE | 객관식 | ok |  | x(2x-3)=0 두 근 SymPy 재확인·근 상실 오개념 태깅 정합 |
| `wm-count-mc-a7cd4983b46e` | ROOT-LOSS-DIVIDE | 객관식 | ok |  | 근 0,5 2개 SymPy 재확인. 해설 '1x'·'5/1' 미간약 표기 어색(참·경미) |
| `wm-count-mc-2d6de408b23b` | ROOT-LOSS-DIVIDE | 객관식 | ok |  | x(3x-4)=0 두 근 SymPy 재확인·근 상실 오개념 태깅 정합 |
| `wm-count-mc-46a277c4b593` | ROOT-LOSS-DIVIDE | 객관식 | ok |  | x(3x-7)=0 두 근 SymPy 재확인·근 상실 오개념 태깅 정합 |
| `wm-count-mc-a5ea855a4f37` | ROOT-LOSS-DIVIDE | 객관식 | ok |  | 근 0,3 2개 SymPy 재확인. 해설 '1x'·'3/1' 미간약 표기 어색(참·경미) |
| `wm-count-mc-99c1d6c60570` | ROOT-LOSS-DIVIDE | 객관식 | ok |  | 근 0,4 2개 SymPy 재확인. 해설 '1x'·'4/1' 미간약 표기 어색(참·경미) |
| `wm-count-mc-0ec745842326` | ROOT-LOSS-DIVIDE | 객관식 | ok |  | x(4x-3)=0 두 근 SymPy 재확인·근 상실 오개념 태깅 정합 |
| `wm-count-mc-fbc762098e67` | ROOT-LOSS-DIVIDE | 객관식 | ok |  | 근 0,2 2개 SymPy 재확인. 해설 '1x'·'2/1' 미간약 표기 어색(참·경미) |
| `wm-count-mc-d6024a85d484` | ROOT-LOSS-DIVIDE | 객관식 | ok |  | x(2x-7)=0 두 근 SymPy 재확인·근 상실 오개념 태깅 정합 |
| `wm-count-mc-f128cfb93f2d` | ROOT-LOSS-DIVIDE | 객관식 | ok |  | x(3x-8)=0 두 근 SymPy 재확인·근 상실 오개념 태깅 정합 |
| `wm-count-mc-0a31cdfd7968` | SERIES-CONV | 객관식 | ok |  | 조화급수형 발산 SymPy 재확인·일반항→0 참·수렴 오인 태깅 정합 |
| `wm-count-mc-d5edd6afda8a` | SERIES-CONV | 객관식 | ok |  | p=1/2 급수 발산 SymPy 재확인·일반항→0 참. '조화급수류' 명명 느슨(비교판정상 참·경미) |
| `wm-count-mc-8085880c39be` | SERIES-CONV | 객관식 | ok |  | 조화급수형 발산 SymPy 재확인·일반항→0 참·수렴 오인 태깅 정합 |
| `wm-count-mc-e6f4b9ebed0d` | SERIES-CONV | 객관식 | ok |  | p=1/2 급수 발산 SymPy 재확인·일반항→0 참. '조화급수류' 명명 느슨(비교판정상 참·경미) |
| `wm-count-mc-a950bcee1401` | SERIES-CONV | 객관식 | ok |  | 조화급수형 발산 SymPy 재확인·일반항→0 참·수렴 오인 태깅 정합 |
| `wm-count-mc-dc1a8f058301` | SERIES-CONV | 객관식 | ok |  | 조화급수형 발산 SymPy 재확인·일반항→0 참·수렴 오인 태깅 정합 |
| `wm-count-mc-294c754f8667` | SERIES-CONV | 객관식 | ok |  | p=1/2 급수 발산 SymPy 재확인·일반항→0 참. '조화급수류' 명명 느슨(비교판정상 참·경미) |
| `wm-count-mc-7f65b0eb23d8` | SERIES-CONV | 객관식 | ok |  | p=1/2 급수 발산 SymPy 재확인·일반항→0 참. '조화급수류' 명명 느슨(비교판정상 참·경미) |
| `wm-count-mc-bd87db0c9d67` | SERIES-CONV | 객관식 | ok |  | 조화급수형 발산 SymPy 재확인·일반항→0 참·수렴 오인 태깅 정합 |
| `wm-count-mc-61e08b4645c1` | SERIES-CONV | 객관식 | ok |  | p=1/2 급수 발산 SymPy 재확인·일반항→0 참. '조화급수류' 명명 느슨(비교판정상 참·경미) |
| `wm-count-mc-f06969f6813d` | SERIES-CONV | 객관식 | ok |  | p=1/2 급수 발산 SymPy 재확인·일반항→0 참. '조화급수류' 명명 느슨(비교판정상 참·경미) |
| `wm-count-mc-68bfd7cdb2c1` | SERIES-CONV | 객관식 | ok |  | p=1/2 급수 발산 SymPy 재확인·일반항→0 참. '조화급수류' 명명 느슨(비교판정상 참·경미) |
| `wm-count-mc-f08a26836b58` | SERIES-CONV | 객관식 | ok |  | 조화급수형 발산 SymPy 재확인·일반항→0 참·수렴 오인 태깅 정합 |
| `wm-count-mc-f64953409f27` | STAT-MEAN-MEDIAN | 객관식 | ok |  | 평균 21/5>중앙값 3 재계산 일치·'커서' 참. '3이나'는 이다 활용(정상) |
| `wm-count-mc-24e21bf4287e` | STAT-MEAN-MEDIAN | 객관식 | ok |  | 평균 29/5>중앙값 5 재계산 일치·'커서' 참. '5이나'는 이다 활용(정상) |
| `wm-count-mc-de882628dc15` | STAT-MEAN-MEDIAN | 객관식 | ok |  | 평균 22/5>중앙값 3 재계산 일치·'커서' 참. '3이나'는 이다 활용(정상) |
| `wm-count-mc-b2eb6f9cbd6a` | STAT-MEAN-MEDIAN | 객관식 | ok |  | 평균 38/5>중앙값 6 재계산 일치·'커서' 참. '6이나'는 이다 활용(정상) |
| `wm-count-mc-40cf1d2d2f2f` | STAT-MEAN-MEDIAN | 객관식 | ok |  | 평균 28/5>중앙값 4 재계산 일치·'커서' 참. '4이나'는 이다 활용(정상) |
| `wm-count-mc-b626a29849ca` | STAT-MEAN-MEDIAN | 객관식 | ok |  | 평균 36/5>중앙값 6 재계산 일치·'커서' 참. '6이나'는 이다 활용(정상) |
| `wm-count-mc-60a503abff6b` | STAT-MEAN-MEDIAN | 객관식 | ok |  | 평균 7>중앙값 6 재계산 일치·'커서' 참. '6이나'는 이다 활용(정상) |
| `wm-count-mc-c16ab7537f5c` | STAT-MEAN-MEDIAN | 객관식 | ok |  | 평균 39/5>중앙값 7 재계산 일치·'커서' 참. '7이나'는 이다 활용(정상) |
| `wm-count-mc-db7323fc7d6e` | STAT-MEAN-MEDIAN | 객관식 | ok |  | 평균 4>중앙값 3 재계산 일치·'커서' 참. '3이나'는 이다 활용(정상) |
| `wm-count-mc-2385c78f2d14` | STAT-MEAN-MEDIAN | 객관식 | ok |  | 평균 19/5>중앙값 3 재계산 일치·'커서' 참. '3이나'는 이다 활용(정상) |
| `wm-count-mc-c71312959593` | STAT-MEAN-MEDIAN | 객관식 | ok |  | 평균 26/5>중앙값 4 재계산 일치·'커서' 참. '4이나'는 이다 활용(정상) |
| `wm-count-mc-04746b6951e0` | STAT-MEAN-MEDIAN | 객관식 | ok |  | 평균 37/5>중앙값 6 재계산 일치·'커서' 참. '6이나'는 이다 활용(정상) |
| `wm-count-mc-db5f552cab3a` | STAT-MEAN-MEDIAN | 객관식 | ok |  | 평균 8>중앙값 7 재계산 일치·'커서' 참. '7이나'는 이다 활용(정상) |
| `wm-count-mc-b849dab81f05` | VEC-DOT-PRODUCT | 객관식 | defect | grammar_break | 해설 '= 5 은'→'는' 조사 파손(받침 무·josa 모듈 대조). 내적 산술·스칼라 판정 정합 |
| `wm-count-mc-1bf64b8076ca` | VEC-DOT-PRODUCT | 객관식 | ok |  | 내적 6 산술 재확인·스칼라 판정·벡터 오인 태깅 정합 |
| `wm-count-mc-f855116b2a8c` | VEC-DOT-PRODUCT | 객관식 | ok |  | 내적 3 산술 재확인·스칼라 판정·벡터 오인 태깅 정합 |
| `wm-count-mc-6656ba1645f6` | VEC-DOT-PRODUCT | 객관식 | defect | grammar_break | 해설 '= 2 은'→'는' 조사 파손(받침 무·josa 모듈 대조). 내적 산술·스칼라 판정 정합 |
| `wm-count-mc-94f0db2da9bd` | VEC-DOT-PRODUCT | 객관식 | defect | grammar_break | 해설 '= 4 은'→'는' 조사 파손(받침 무·josa 모듈 대조). 내적 산술·스칼라 판정 정합 |
| `wm-count-mc-f2b2664b00df` | VEC-DOT-PRODUCT | 객관식 | ok |  | 내적 8 산술 재확인·스칼라 판정·벡터 오인 태깅 정합 |
| `wm-count-mc-96943c806205` | VEC-DOT-PRODUCT | 객관식 | defect | grammar_break | 해설 '= 5 은'→'는' 조사 파손(받침 무·josa 모듈 대조). 내적 산술·스칼라 판정 정합 |
| `wm-count-mc-fc2e50326132` | VEC-DOT-PRODUCT | 객관식 | ok |  | 내적 6 산술 재확인·스칼라 판정·벡터 오인 태깅 정합 |
| `wm-count-mc-dcbad9acd643` | VEC-DOT-PRODUCT | 객관식 | ok |  | 내적 7 산술 재확인·스칼라 판정·벡터 오인 태깅 정합 |
| `wm-count-mc-c2385ae9f336` | VEC-DOT-PRODUCT | 객관식 | defect | grammar_break | 해설 '= 5 은'→'는' 조사 파손(받침 무·josa 모듈 대조). 내적 산술·스칼라 판정 정합 |
| `wm-count-mc-196d96b037f9` | VEC-DOT-PRODUCT | 객관식 | defect | grammar_break | 해설 '= 4 은'→'는' 조사 파손(받침 무·josa 모듈 대조). 내적 산술·스칼라 판정 정합 |
| `wm-count-mc-021c4db67fe0` | VEC-DOT-PRODUCT | 객관식 | ok |  | 내적 10 산술 재확인·스칼라 판정·벡터 오인 태깅 정합 |
| `wm-count-mc-e1e53bdc965e` | VEC-DOT-PRODUCT | 객관식 | defect | grammar_break | 해설 '= 9 은'→'는' 조사 파손(받침 무·josa 모듈 대조). 내적 산술·스칼라 판정 정합 |

## 문항별 판정 — rephrased (200)

| slug | 도메인 | 형식 | verdict | 결함류 | 비고 |
|---|---|---|---|---|---|
| `wm-skel-126a2ead2c3c` | QUAD-EQ | 객관식 | defect | other | 발문 '원판을 다루는' 허위 맥락+'작게 하는 수' 왜곡(재서술 메타 누출). 수학·선지 정상 |
| `wm-skel-f664ed64520f` | QUAD-EQ | 단답형 | ok |  | SymPy·발문-수식 일치. 해설 √12(=2√3) 미정리 표기 경미 |
| `wm-skel-06badf890112` | QUAD-EQ | 단답형 | ok |  | SymPy 재검증·발문-수식 일치·발문 자연·[10공수1-02-02] 적합 |
| `wm-skel-624b52a48ccb` | QUAD-EQ | 단답형 | ok |  | SymPy 재검증·발문-수식 일치·발문 자연·[10공수1-02-02] 적합 |
| `wm-skel-cd0b59fdceaa` | QUAD-EQ | 단답형 | defect | grammar_break | '크면서 근을 찾아보세요' 비문(어미 파손). 수학 정상 |
| `wm-skel-07c0b591ca85` | QUAD-EQ | 객관식 | ok |  | SymPy·선지 op 정합. '중에 큰 수' 구어투 경미 |
| `wm-skel-ee87a36dfac4` | QUAD-EQ | 단답형 | ok |  | SymPy 재검증·발문-수식 일치·발문 자연·[10공수1-02-02] 적합 |
| `wm-skel-20d0e5d3fbf8` | QUAD-EQ | 객관식 | defect | grammar_break | '두解는 중에서 크다 근은?' 한자 주입+비문. 수학·선지 정상 |
| `wm-skel-26c127b54da3` | QUAD-EQ | 단답형 | ok |  | SymPy 재검증·발문-수식 일치·발문 자연·[10공수1-02-02] 적합 |
| `wm-skel-87d059e107e4` | QUAD-EQ | 단답형 | ok |  | SymPy 일치(중근 unique)·발문 자연·귀속 적합 |
| `wm-skel-218f93d1ceff` | QUAD-EQ | 객관식 | ok |  | SymPy 재검증·발문-수식 일치·선지 오개념 op 재유도 정합·발문 자연 |
| `wm-skel-74c7585495a2` | QUAD-EQ | 객관식 | defect | other | 발문 앞 '원 발문:' 재서술 메타 라벨 누출. 수학·선지 정상 |
| `wm-skel-a71a3b26384a` | QUAD-EQ | 단답형 | defect | grammar_break | '10 를'→'10을' 조사 받침 오류(240선례 값가 동형). 수학 정상 |
| `wm-skel-48349bfa9b31` | QUAD-EQ | 객관식 | ok |  | SymPy 재검증·발문-수식 일치·선지 오개념 op 재유도 정합·발문 자연 |
| `wm-skel-e6bf176a1a4c` | QUAD-EQ | 단답형 | ok |  | SymPy 재검증·발문-수식 일치·발문 자연·[10공수1-02-02] 적합 |
| `wm-skel-bed81b2202dd` | QUAD-EQ | 단답형 | ok |  | SymPy 재검증·발문-수식 일치·발문 자연·[10공수1-02-02] 적합 |
| `wm-skel-1b7b0252c428` | QUAD-EQ | 단답형 | ok |  | SymPy 재검증·발문-수식 일치·발문 자연·[10공수1-02-02] 적합 |
| `wm-skel-1fbdd8048343` | QUAD-EQ | 단답형 | ok |  | SymPy 재검증·발문-수식 일치·발문 자연·[10공수1-02-02] 적합 |
| `wm-skel-fbd8a85e48dd` | QUAD-EQ | 단답형 | ok |  | SymPy 재검증·발문-수식 일치·발문 자연·[10공수1-02-02] 적합 |
| `wm-skel-2e294cadab2b` | QUAD-EQ | 단답형 | defect | other | 비표준 용어 '원시방정식'으로 이차방정식 오명명. 수학 정상 |
| `wm-skel-92cd1ba2bbf5` | QUAD-EQ | 단답형 | defect | grammar_break | '원판이 문제의…' 비문+원판 메타 누출. 요구(큰 근)는 verify와 일치 |
| `wm-skel-7b02121cf400` | QUAD-EQ | 단답형 | ok |  | SymPy·발문-수식 일치. '작게 나온 값' 표현 경미 어색 |
| `wm-skel-1cc6d23230b8` | QUAD-EQ | 객관식 | defect | grammar_break | '크 greater한 귀를' 영어 주입+어휘 파손(근→귀). 수학·선지 정상 |
| `wm-skel-f750afcbbd98` | QUAD-EQ | 단답형 | ok |  | SymPy 재검증·발문-수식 일치·발문 자연·[10공수1-02-02] 적합 |
| `wm-skel-f50f96b5a691` | QUAD-EQ | 객관식 | ok |  | SymPy 재검증·발문-수식 일치·선지 오개념 op 재유도 정합·발문 자연 |
| `wm-skel-d20bc34950ba` | QUAD-EQ | 단답형 | ok |  | SymPy 재검증·발문-수식 일치·발문 자연·[10공수1-02-02] 적합 |
| `wm-skel-7c1913d788f0` | QUAD-EQ | 객관식 | ok |  | SymPy 재검증·발문-수식 일치·선지 오개념 op 재유도 정합·발문 자연 |
| `wm-skel-348a8d6767e5` | QUAD-EQ | 단답형 | ok |  | SymPy 재검증·발문-수식 일치·발문 자연·[10공수1-02-02] 적합 |
| `wm-skel-acecb80fd523` | QUAD-EQ | 단답형 | ok |  | SymPy 재검증·발문-수식 일치·발문 자연·[10공수1-02-02] 적합 |
| `wm-skel-9e64e7fce855` | QUAD-EQ | 단답형 | defect | other | 비표준 용어 '원시방정식'. 그 외 발문·수학 정상 |
| `wm-skel-7bc8c5e3f0ed` | QUAD-EQ | 단답형 | ok |  | SymPy 재검증·발문-수식 일치·발문 자연·[10공수1-02-02] 적합 |
| `wm-skel-64f012348e22` | QUAD-EQ | 단답형 | ok |  | SymPy 재검증·발문-수식 일치·발문 자연·[10공수1-02-02] 적합 |
| `wm-skel-a27a99e80f34` | QUAD-EQ | 객관식 | ok |  | SymPy 재검증·발문-수식 일치·선지 오개념 op 재유도 정합·발문 자연 |
| `wm-skel-414edb062317` | QUAD-EQ | 객관식 | ok |  | SymPy 재검증·발문-수식 일치·선지 오개념 op 재유도 정합·발문 자연 |
| `wm-skel-c60b366c016f` | QUAD-EQ | 객관식 | ok |  | SymPy 재검증·발문-수식 일치·선지 오개념 op 재유도 정합·발문 자연 |
| `wm-skel-a7c05d7953f8` | QUAD-EQ | 객관식 | ok |  | SymPy·선지 정합. '원하는·원래' 군더더기 어색하나 문법·의미 전달 가능 |
| `wm-skel-991ec1659ca4` | QUAD-EQ | 단답형 | defect | grammar_break | '두解 중 더 큰 解의 값' 한자 解 주입. 수학 정상 |
| `wm-skel-8ea59b001e72` | QUAD-EQ | 단답형 | defect | grammar_break | '두解 중 큰解을' 한자 주입+조사 오류(解을→해를). 수학 정상 |
| `wm-skel-e855457a2d51` | QUAD-EQ | 단답형 | ok |  | SymPy 재검증·발문-수식 일치·발문 자연·[10공수1-02-02] 적합 |
| `wm-skel-2407e0fb541b` | QUAD-EQ | 객관식 | defect | grammar_break | '두解 (근) 중 더 큰 것 뽑으시오' 한자 주입+조사 생략. 선지 정상 |
| `wm-skel-0047d3954eb8` | QUAD-EQ | 단답형 | ok |  | SymPy 재검증·발문-수식 일치·발문 자연·[10공수1-02-02] 적합 |
| `wm-skel-cf09661957b3` | QUAD-EQ | 객관식 | ok |  | SymPy·선지 op 정합. 해설 √8(=2√2) 미정리 표기 경미 |
| `wm-skel-10e4b5e97e17` | QUAD-EQ | 단답형 | ok |  | SymPy 재검증·발문-수식 일치·발문 자연·[10공수1-02-02] 적합 |
| `wm-skel-d5f5ea458863` | QUAD-EQ | 단답형 | defect | grammar_break | '크다음 근' 어휘 파손. 수학 정상 |
| `wm-skel-4d5c87728910` | QUAD-EQ | 단답형 | ok |  | SymPy 재검증·발문-수식 일치·발문 자연·[10공수1-02-02] 적합 |
| `wm-skel-fbc2e8e02b18` | QUAD-EQ | 객관식 | ok |  | SymPy 재검증·발문-수식 일치·선지 오개념 op 재유도 정합·발문 자연 |
| `wm-skel-add928d88130` | QUAD-EQ | 객관식 | ok |  | SymPy 재검증·발문-수식 일치·선지 오개념 op 재유도 정합·발문 자연 |
| `wm-skel-caa1e44bebe7` | QUAD-EQ | 객관식 | ok |  | SymPy 재검증·발문-수식 일치·선지 오개념 op 재유도 정합·발문 자연 |
| `wm-skel-06913a6c0e0a` | QUAD-EQ | 단답형 | ok |  | SymPy 재검증·발문-수식 일치·발문 자연·[10공수1-02-02] 적합 |
| `wm-skel-55281d38624c` | QUAD-EQ | 단답형 | ok |  | SymPy 일치(중근). 명령형 없이 '…문제입니다' 서술이나 요구 명확(경미) |
| `wm-skel-65f4acce8a61` | QUAD-EQ | 단답형 | ok |  | SymPy 재검증·발문-수식 일치·발문 자연·[10공수1-02-02] 적합 |
| `wm-skel-811e3dae7ea6` | QUAD-EQ | 단답형 | ok |  | SymPy 재검증·발문-수식 일치·발문 자연·[10공수1-02-02] 적합 |
| `wm-skel-6189d3879556` | QUAD-EQ | 객관식 | ok |  | SymPy 재검증·발문-수식 일치·선지 오개념 op 재유도 정합·발문 자연 |
| `wm-skel-4da68ed906e3` | QUAD-EQ | 단답형 | ok |  | SymPy 재검증·발문-수식 일치·발문 자연·[10공수1-02-02] 적합 |
| `wm-skel-7d304bf33b3f` | QUAD-EQ | 단답형 | defect | statement_mismatch | 발문이 '구하는 방법'을 물음 — 정답은 값(-1/2)이라 요구-정답 불일치 |
| `wm-skel-f70a7458a099` | QUAD-EQ | 객관식 | ok |  | SymPy·선지 op 정합. '작게 나오는 값' 표현 경미 어색 |
| `wm-skel-32b1ba50a208` | QUAD-EQ | 단답형 | defect | grammar_break | '다차방정식'+'두解 중 큰 解를' 용어 오류·한자 주입. 수학 정상 |
| `wm-skel-5a5ceb3e3ab8` | QUAD-EQ | 객관식 | ok |  | SymPy 재검증·발문-수식 일치·선지 오개념 op 재유도 정합·발문 자연 |
| `wm-skel-37c15f418e69` | QUAD-EQ | 단답형 | ok |  | SymPy 재검증·발문-수식 일치·발문 자연·[10공수1-02-02] 적합 |
| `wm-skel-5ce459035e06` | QUAD-EQ | 단답형 | ok |  | SymPy 재검증·발문-수식 일치·발문 자연·[10공수1-02-02] 적합 |
| `wm-skel-1f14321740b3` | QUAD-EQ | 객관식 | defect | grammar_break | '(더 작은) 근을 찾는다: … 두 해 중에서' 미완결 문장 파편. 선지 정상 |
| `wm-skel-0f7bbeee6adf` | QUAD-EQ | 단답형 | ok |  | SymPy 재검증·발문-수식 일치·발문 자연·[10공수1-02-02] 적합 |
| `wm-skel-14819226271a` | QUAD-EQ | 객관식 | ok |  | SymPy 재검증·발문-수식 일치·선지 오개념 op 재유도 정합·발문 자연 |
| `wm-skel-ebbb64b77387` | QUAD-EQ | 단답형 | ok |  | SymPy 재검증·발문-수식 일치·발문 자연·[10공수1-02-02] 적합 |
| `wm-skel-22b42b4af884` | QUAD-EQ | 단답형 | ok |  | SymPy 재검증·발문-수식 일치·발문 자연·[10공수1-02-02] 적합 |
| `wm-skel-b113f66bb41b` | QUAD-EQ | 단답형 | defect | grammar_break | '두解となる 근' 한자+일본어 주입. 수학 정상 |
| `wm-skel-95d89a679484` | QUAD-EQ | 단답형 | ok |  | SymPy 재검증·발문-수식 일치·발문 자연·[10공수1-02-02] 적합 |
| `wm-skel-fa2520c2b6d5` | QUAD-EQ | 객관식 | ok |  | SymPy 재검증·발문-수식 일치·선지 오개념 op 재유도 정합·발문 자연 |
| `wm-skel-45c392a025fb` | QUAD-EQ | 단답형 | ok |  | SymPy 재검증·발문-수식 일치·발문 자연·[10공수1-02-02] 적합 |
| `wm-skel-f4dd792e864f` | QUAD-EQ | 단답형 | ok |  | SymPy 재검증·발문-수식 일치·발문 자연·[10공수1-02-02] 적합 |
| `wm-skel-6f315c79a3f0` | QUAD-EQ | 객관식 | ok |  | SymPy 재검증·발문-수식 일치·선지 오개념 op 재유도 정합·발문 자연 |
| `wm-skel-21daa1aa0a1f` | QUAD-EQ | 단답형 | defect | statement_mismatch | '방법은 어떨까요' 방법 물음 — 정답은 값(-8) 불일치. '다차방정식' 용어 오류 동반 |
| `wm-skel-15c0be0334fc` | QUAD-EQ | 객관식 | ok |  | SymPy 재검증·발문-수식 일치·선지 오개념 op 재유도 정합·발문 자연 |
| `wm-skel-856e80c989d4` | QUAD-EQ | 객관식 | ok |  | SymPy 재검증·발문-수식 일치·선지 오개념 op 재유도 정합·발문 자연 |
| `wm-skel-3eb00ae303f2` | QUAD-EQ | 단답형 | defect | grammar_break | '10 를'→'10을' 조사 받침 오류. 수학 정상 |
| `wm-skel-32910b0522d4` | QUAD-EQ | 단답형 | ok |  | SymPy 재검증·발문-수식 일치·발문 자연·[10공수1-02-02] 적합 |
| `wm-skel-2b5a92d28d61` | QUAD-EQ | 객관식 | ok |  | SymPy 재검증·발문-수식 일치·선지 오개념 op 재유도 정합·발문 자연 |
| `wm-skel-54c14025ef80` | QUAD-EQ | 단답형 | ok |  | SymPy 재검증·발문-수식 일치·발문 자연·[10공수1-02-02] 적합 |
| `wm-arseq-377e1711f323` | ARITH-SEQ | 단답형 | ok |  | SymPy 재검증(a1+(n-1)d) 일치·발문 파라미터 정합·자연·[12대수03-02] 적합 |
| `wm-arseq-8fdfca1070d1` | ARITH-SEQ | 단답형 | ok |  | SymPy 재검증(a1+(n-1)d) 일치·발문 파라미터 정합·자연·[12대수03-02] 적합 |
| `wm-arseq-d9bc4e7de33d` | ARITH-SEQ | 단답형 | ok |  | SymPy 재검증(a1+(n-1)d) 일치·발문 파라미터 정합·자연·[12대수03-02] 적합 |
| `wm-arseq-cf0a1db2d30d` | ARITH-SEQ | 단답형 | ok |  | SymPy 재검증(a1+(n-1)d) 일치·발문 파라미터 정합·자연·[12대수03-02] 적합 |
| `wm-arseq-a7219c78f522` | ARITH-SEQ | 단답형 | ok |  | SymPy 재검증(a1+(n-1)d) 일치·발문 파라미터 정합·자연·[12대수03-02] 적합 |
| `wm-arseq-925deb220ac6` | ARITH-SEQ | 단답형 | ok |  | SymPy 재검증(a1+(n-1)d) 일치·발문 파라미터 정합·자연·[12대수03-02] 적합 |
| `wm-arseq-b1caf7744512` | ARITH-SEQ | 단답형 | ok |  | SymPy 재검증(a1+(n-1)d) 일치·발문 파라미터 정합·자연·[12대수03-02] 적합 |
| `wm-arseq-ac26002af2ef` | ARITH-SEQ | 단답형 | ok |  | SymPy 재검증(a1+(n-1)d) 일치·발문 파라미터 정합·자연·[12대수03-02] 적합 |
| `wm-arseq-007832bc44fd` | ARITH-SEQ | 단답형 | ok |  | SymPy 재검증(a1+(n-1)d) 일치·발문 파라미터 정합·자연·[12대수03-02] 적합 |
| `wm-arseq-6a5c614903b2` | ARITH-SEQ | 단답형 | ok |  | SymPy 재검증(a1+(n-1)d) 일치·발문 파라미터 정합·자연·[12대수03-02] 적합 |
| `wm-arseq-253b5ee25365` | ARITH-SEQ | 단답형 | ok |  | SymPy 재검증(a1+(n-1)d) 일치·발문 파라미터 정합·자연·[12대수03-02] 적합 |
| `wm-arseq-e06c49520959` | ARITH-SEQ | 단답형 | ok |  | SymPy 재검증(a1+(n-1)d) 일치·발문 파라미터 정합·자연·[12대수03-02] 적합 |
| `wm-arseq-6c526e9c28e3` | ARITH-SEQ | 단답형 | ok |  | SymPy 재검증(a1+(n-1)d) 일치·발문 파라미터 정합·자연·[12대수03-02] 적합 |
| `wm-arseq-1dd3fd129573` | ARITH-SEQ | 단답형 | ok |  | SymPy 재검증(a1+(n-1)d) 일치·발문 파라미터 정합·자연·[12대수03-02] 적합 |
| `wm-arseq-fc8de6c546a8` | ARITH-SEQ | 단답형 | ok |  | SymPy 재검증(a1+(n-1)d) 일치·발문 파라미터 정합·자연·[12대수03-02] 적합 |
| `wm-arseq-c9a3f1d53ee8` | ARITH-SEQ | 단답형 | ok |  | SymPy 재검증(a1+(n-1)d) 일치·발문 파라미터 정합·자연·[12대수03-02] 적합 |
| `wm-arseq-7ee05322761a` | ARITH-SEQ | 단답형 | ok |  | SymPy 재검증(a1+(n-1)d) 일치·발문 파라미터 정합·자연·[12대수03-02] 적합 |
| `wm-arseq-91d76377b770` | ARITH-SEQ | 단답형 | ok |  | SymPy 재검증(a1+(n-1)d) 일치·발문 파라미터 정합·자연·[12대수03-02] 적합 |
| `wm-arseq-c4ba1ee82ced` | ARITH-SEQ | 단답형 | ok |  | SymPy 재검증(a1+(n-1)d) 일치·발문 파라미터 정합·자연·[12대수03-02] 적합 |
| `wm-arseq-c64031c472ce` | ARITH-SEQ | 단답형 | ok |  | SymPy 재검증(a1+(n-1)d) 일치·발문 파라미터 정합·자연·[12대수03-02] 적합 |
| `wm-arseq-db6fb5c80126` | ARITH-SEQ | 단답형 | ok |  | SymPy 재검증(a1+(n-1)d) 일치·발문 파라미터 정합·자연·[12대수03-02] 적합 |
| `wm-arseq-4fb383e65e8e` | ARITH-SEQ | 단답형 | ok |  | SymPy 재검증(a1+(n-1)d) 일치·발문 파라미터 정합·자연·[12대수03-02] 적합 |
| `wm-arseq-b876e6c52936` | ARITH-SEQ | 단답형 | ok |  | a1=2,d=5,n=10→47 재유도·verify·정답 일치. 발문·해설 자연. 귀속 정합 |
| `wm-arseq-827d5ec25ad9` | ARITH-SEQ | 단답형 | ok |  | a1=2,d=3,n=13→38 재유도·verify·정답 일치. 발문·해설 자연. 귀속 정합 |
| `wm-arseq-cb1839be1dd8` | ARITH-SEQ | 단답형 | ok |  | a1=1,d=3,n=6→16 재유도·verify·정답 일치. 발문·해설 자연. 귀속 정합 |
| `wm-calc-ext-662d3f9c62e3` | CALC-EXTREMUM | 단답형 | ok |  | f' 근 극대x=-8·극소x=0 재유도, 질의 극점 x=0 일치. 'f(x)…가' 통용체 |
| `wm-calc-ext-f22d9eeec986` | CALC-EXTREMUM | 단답형 | ok |  | f' 근 극대x=-8·극소x=2 재유도, 질의 극점 x=-8 일치. 'f(x)…가' 통용체 |
| `wm-calc-ext-0598394a6ff3` | CALC-EXTREMUM | 단답형 | ok |  | f' 근 극대x=-3·극소x=9 재유도, 질의 극점 x=-3 일치. 'f(x)…가' 통용체 |
| `wm-calc-ext-783de36f65d6` | CALC-EXTREMUM | 단답형 | ok |  | f' 근 극대x=-1·극소x=3 재유도, 질의 극점 x=-1 일치. 'f(x)…가' 통용체 |
| `wm-calc-ext-d199c5fdd29b` | CALC-EXTREMUM | 단답형 | ok |  | f' 근 극대x=2·극소x=8 재유도, 질의 극점 x=2 일치. 'f(x)…가' 통용체 |
| `wm-calc-ext-921bf10f6940` | CALC-EXTREMUM | 단답형 | ok |  | f' 근 극대x=5·극소x=9 재유도, 질의 극점 x=5 일치. 'f(x)…가' 통용체 |
| `wm-calc-ext-83f1c86f74a5` | CALC-EXTREMUM | 단답형 | ok |  | f' 근 극대x=-6·극소x=0 재유도, 질의 극점 x=0 일치. 'f(x)…가' 통용체 |
| `wm-calc-ext-8c193941df77` | CALC-EXTREMUM | 단답형 | ok |  | f' 근 극대x=-8·극소x=6 재유도, 질의 극점 x=6 일치. 'f(x)…가' 통용체 |
| `wm-calc-ext-33c602d14141` | CALC-EXTREMUM | 단답형 | ok |  | f' 근 극대x=-3·극소x=5 재유도, 질의 극점 x=5 일치. 'f(x)…가' 통용체 |
| `wm-calc-ext-6acccbead5d3` | CALC-EXTREMUM | 단답형 | ok |  | f' 근 극대x=1·극소x=7 재유도, 질의 극점 x=1 일치. 'f(x)…가' 통용체 |
| `wm-calc-ext-a677addfed9d` | CALC-EXTREMUM | 단답형 | ok |  | f' 근 극대x=-4·극소x=4 재유도, 질의 극점 x=-4 일치. 'f(x)…가' 통용체 |
| `wm-calc-ext-bb0738c9788f` | CALC-EXTREMUM | 단답형 | ok |  | f' 근 극대x=4·극소x=8 재유도, 질의 극점 x=8 일치. 'f(x)…가' 통용체 |
| `wm-calc-ext-139f4f98bdcc` | CALC-EXTREMUM | 단답형 | ok |  | f' 근 극대x=-7·극소x=1 재유도, 질의 극점 x=1 일치. 'f(x)…가' 통용체 |
| `wm-calc-ext-3dcd4f4357bb` | CALC-EXTREMUM | 단답형 | ok |  | f' 근 극대x=-4·극소x=2 재유도, 질의 극점 x=-4 일치. 'f(x)…가' 통용체 |
| `wm-calc-ext-7a775c313056` | CALC-EXTREMUM | 단답형 | ok |  | f' 근 극대x=7·극소x=9 재유도, 질의 극점 x=7 일치. 'f(x)…가' 통용체 |
| `wm-calc-ext-fcf3615d090e` | CALC-EXTREMUM | 단답형 | ok |  | f' 근 극대x=3·극소x=5 재유도, 질의 극점 x=5 일치. 'f(x)…가' 통용체 |
| `wm-calc-ext-87ebbd5cfb65` | CALC-EXTREMUM | 단답형 | ok |  | f' 근 극대x=2·극소x=6 재유도, 질의 극점 x=2 일치. 'f(x)…가' 통용체 |
| `wm-calc-extv-07d379e67ade` | CALC-EXTREMUM-VALUE | 단답형 | ok |  | 극대x=4·극소x=8, 질의 극값 128 재유도 일치. 발문·해설 정합 |
| `wm-calc-extv-2894b75b7aae` | CALC-EXTREMUM-VALUE | 단답형 | ok |  | 극대x=5·극소x=9, 질의 극값 275 재유도 일치. 발문·해설 정합 |
| `wm-calc-extv-8fc0af95c0e6` | CALC-EXTREMUM-VALUE | 단답형 | ok |  | 극대x=-8·극소x=6, 질의 극값 832 재유도 일치. 발문·해설 정합 |
| `wm-calc-extv-25ee5b3efcb8` | CALC-EXTREMUM-VALUE | 단답형 | ok |  | 극대x=1·극소x=7, 질의 극값 10 재유도 일치. 발문·해설 정합 |
| `wm-calc-extv-fc779224ca56` | CALC-EXTREMUM-VALUE | 단답형 | ok |  | 극대x=-3·극소x=7, 질의 극값 108 재유도 일치. 발문·해설 정합 |
| `wm-calc-extv-c2ce1da494fa` | CALC-EXTREMUM-VALUE | 단답형 | ok |  | 극대x=-6·극소x=2, 질의 극값 216 재유도 일치. 발문·해설 정합 |
| `wm-calc-extv-ad3c4e560894` | CALC-EXTREMUM-VALUE | 단답형 | ok |  | 극대x=-8·극소x=-6, 질의 극값 -320 재유도 일치. 발문·해설 정합 |
| `wm-calc-extv-fca5494a067b` | CALC-EXTREMUM-VALUE | 단답형 | ok |  | 극대x=-3·극소x=7, 질의 극값 -392 재유도 일치. 발문·해설 정합 |
| `wm-calc-extv-0c2ce466bfc6` | CALC-EXTREMUM-VALUE | 단답형 | ok |  | 극대x=-9·극소x=-1, 질의 극값 243 재유도 일치. 발문·해설 정합 |
| `wm-calc-extv-8742a8f5d365` | CALC-EXTREMUM-VALUE | 단답형 | ok |  | 극대x=5·극소x=7, 질의 극값 196 재유도 일치. 발문·해설 정합 |
| `wm-calc-extv-c81060cda0fc` | CALC-EXTREMUM-VALUE | 단답형 | ok |  | 극대x=-8·극소x=0, 질의 극값 0 재유도 일치. 발문·해설 정합 |
| `wm-calc-extv-5c4a86d7a72a` | CALC-EXTREMUM-VALUE | 단답형 | ok |  | 극대x=-3·극소x=1, 질의 극값 -5 재유도 일치. 발문·해설 정합 |
| `wm-calc-extv-01f786ab766c` | CALC-EXTREMUM-VALUE | 단답형 | ok |  | 극대x=-9·극소x=7, 질의 극값 -833 재유도 일치. 발문·해설 정합 |
| `wm-calc-extv-e6a3024dc72b` | CALC-EXTREMUM-VALUE | 단답형 | ok |  | 극대x=-4·극소x=0, 질의 극값 32 재유도 일치. 발문·해설 정합 |
| `wm-calc-extv-3eae62dfa946` | CALC-EXTREMUM-VALUE | 단답형 | ok |  | 극대x=-3·극소x=3, 질의 극값 -54 재유도 일치. 발문·해설 정합 |
| `wm-calc-extv-e32a2915a063` | CALC-EXTREMUM-VALUE | 단답형 | ok |  | 극대x=-9·극소x=7, 질의 극값 1215 재유도 일치. 발문·해설 정합 |
| `wm-calc-extv-2dc042e5ab00` | CALC-EXTREMUM-VALUE | 단답형 | ok |  | 극대x=-8·극소x=-6, 질의 극값 -324 재유도 일치. 발문·해설 정합 |
| `wm-calc-tan-9f7d59dc1c06` | CALC-TANGENT | 단답형 | ok |  | f'=-6 접점 x=-4, 4, 선택(small)=-4 일치. x좌표 질의 정합 |
| `wm-calc-tan-c5d184e00244` | CALC-TANGENT | 단답형 | ok |  | f'=-6 접점 x=-8, 2, 선택(large)=2 일치. x좌표 질의 정합 |
| `wm-calc-tan-02f2bf569298` | CALC-TANGENT | 단답형 | ok |  | f'=-2 접점 x=2, 6, 선택(large)=6 일치. x좌표 질의 정합 |
| `wm-calc-tan-0f66511a6c1a` | CALC-TANGENT | 단답형 | ok |  | f'=4 접점 x=-6, 2, 선택(large)=2 일치. x좌표 질의 정합 |
| `wm-calc-tan-290fc784a150` | CALC-TANGENT | 단답형 | ok |  | f'=4 접점 x=-1, 5, 선택(small)=-1 일치. x좌표 질의 정합 |
| `wm-calc-tan-99d328120688` | CALC-TANGENT | 단답형 | ok |  | f'=-2 접점 x=-2, 4, 선택(large)=4 일치. x좌표 질의 정합 |
| `wm-calc-tan-7994f0e16285` | CALC-TANGENT | 단답형 | ok |  | f'=-2 접점 x=-9, 1, 선택(large)=1 일치. x좌표 질의 정합 |
| `wm-calc-tan-4fd6facd3699` | CALC-TANGENT | 단답형 | ok |  | f'=4 접점 x=-8, 6, 선택(small)=-8 일치. x좌표 질의 정합 |
| `wm-calc-tan-da1f27ee77d8` | CALC-TANGENT | 단답형 | ok |  | f'=-2 접점 x=-1, 9, 선택(small)=-1 일치. x좌표 질의 정합 |
| `wm-calc-tan-99db28357220` | CALC-TANGENT | 단답형 | ok |  | f'=4 접점 x=-5, 3, 선택(small)=-5 일치. x좌표 질의 정합 |
| `wm-calc-tan-ba13feaffd7d` | CALC-TANGENT | 단답형 | ok |  | f'=-2 접점 x=-8, 0, 선택(small)=-8 일치. x좌표 질의 정합 |
| `wm-calc-tan-04a46e7f6ffa` | CALC-TANGENT | 단답형 | ok |  | f'=-2 접점 x=-1, 3, 선택(large)=3 일치. x좌표 질의 정합 |
| `wm-calc-tan-a33087001766` | CALC-TANGENT | 단답형 | ok |  | f'=4 접점 x=7, 9, 선택(large)=9 일치. x좌표 질의 정합 |
| `wm-calc-tan-0a02899793c0` | CALC-TANGENT | 단답형 | ok |  | f'=-2 접점 x=-4, 2, 선택(large)=2 일치. x좌표 질의 정합 |
| `wm-calc-tan-f881d5d5e835` | CALC-TANGENT | 단답형 | ok |  | f'=4 접점 x=-8, 6, 선택(large)=6 일치. x좌표 질의 정합 |
| `wm-calc-tan-baf70003e7a6` | CALC-TANGENT | 단답형 | ok |  | f'=-2 접점 x=-5, -3, 선택(large)=-3 일치. x좌표 질의 정합 |
| `wm-calc-extmc-8481b53c00e2` | CALC-EXTREMUM-MC | 객관식 | ok |  | 극값 -539 재유도 일치·정답∈선지. 오답 op(극점x·반대극값) 역산 전건 정합 |
| `wm-calc-extmc-803cec54fad3` | CALC-EXTREMUM-MC | 객관식 | ok |  | 극값 100 재유도 일치·정답∈선지. 오답 op(극점x·반대극값) 역산 전건 정합 |
| `wm-calc-extmc-2e23148010b0` | CALC-EXTREMUM-MC | 객관식 | ok |  | 극값 325 재유도 일치·정답∈선지. 오답 op(극점x·반대극값) 역산 전건 정합 |
| `wm-calc-extmc-8fc0433707f2` | CALC-EXTREMUM-MC | 객관식 | ok |  | 극값 -243 재유도 일치·정답∈선지. 오답 op(극점x·반대극값) 역산 전건 정합 |
| `wm-calc-extmc-5c4a86d7a72a` | CALC-EXTREMUM-MC | 객관식 | ok |  | 극값 -5 재유도 일치·정답∈선지. 오답 op(극점x·반대극값) 역산 전건 정합 |
| `wm-calc-extmc-34abe4cd4c5b` | CALC-EXTREMUM-MC | 객관식 | ok |  | 극값 -52 재유도 일치·정답∈선지. 오답 op(극점x·반대극값) 역산 전건 정합 |
| `wm-calc-extmc-3ccc6c8c3b7c` | CALC-EXTREMUM-MC | 객관식 | ok |  | 극값 243 재유도 일치·정답∈선지. 오답 op(극점x·반대극값) 역산 전건 정합 |
| `wm-calc-extmc-5af27b145d2b` | CALC-EXTREMUM-MC | 객관식 | ok |  | 극값 1215 재유도 일치·정답∈선지. 오답 op(극점x·반대극값) 역산 전건 정합 |
| `wm-calc-extmc-829f17b06867` | CALC-EXTREMUM-MC | 객관식 | ok |  | 극값 -320 재유도 일치·정답∈선지. 오답 op(극점x·반대극값) 역산 전건 정합 |
| `wm-calc-extmc-588713791a72` | CALC-EXTREMUM-MC | 객관식 | ok |  | 극값 275 재유도 일치·정답∈선지. 오답 op(극점x·반대극값) 역산 전건 정합 |
| `wm-calc-extmc-de4e71f518eb` | CALC-EXTREMUM-MC | 객관식 | ok |  | 극값 28 재유도 일치·정답∈선지. 오답 op(극점x·반대극값) 역산 전건 정합 |
| `wm-calc-extmc-156e734b8684` | CALC-EXTREMUM-MC | 객관식 | ok |  | 극값 -4 재유도 일치·정답∈선지. 오답 op(극점x·반대극값) 역산 전건 정합 |
| `wm-geseq-e00a9dc7f844` | GEO-SEQ | 단답형 | ok |  | a1=3,r=2,n=3→12 재유도 일치. 발문 자연·조사 정합. 귀속 [12대수03-03] 정합 |
| `wm-geseq-4cde5745b9f4` | GEO-SEQ | 단답형 | ok |  | a1=2,r=3,n=4→54 재유도 일치. 발문 자연·조사 정합. 귀속 [12대수03-03] 정합 |
| `wm-geseq-cf7244855e39` | GEO-SEQ | 단답형 | ok |  | a1=3,r=2,n=6→96 재유도 일치. 발문 자연·조사 정합. 귀속 [12대수03-03] 정합 |
| `wm-geseq-2bd0734f5ed7` | GEO-SEQ | 단답형 | ok |  | a1=4,r=5,n=4→500 재유도 일치. 발문 자연·조사 정합. 귀속 [12대수03-03] 정합 |
| `wm-geseq-d50bd54b7ce0` | GEO-SEQ | 단답형 | ok |  | a1=3,r=2,n=5→48 재유도 일치. 발문 자연·조사 정합. 귀속 [12대수03-03] 정합 |
| `wm-geseq-c08ef55a5983` | GEO-SEQ | 단답형 | ok |  | a1=1,r=3,n=3→9 재유도 일치. 발문 자연·조사 정합. 귀속 [12대수03-03] 정합 |
| `wm-geseq-cc22267ef882` | GEO-SEQ | 단답형 | ok |  | a1=2,r=5,n=4→250 재유도 일치. 발문 자연·조사 정합. 귀속 [12대수03-03] 정합 |
| `wm-geseq-4e744367bd4b` | GEO-SEQ | 단답형 | ok |  | a1=1,r=5,n=5→625 재유도 일치. 발문 자연·조사 정합. 귀속 [12대수03-03] 정합 |
| `wm-geseq-846c1a304a75` | GEO-SEQ | 단답형 | ok |  | a1=4,r=3,n=5→324 재유도 일치. 발문 자연·조사 정합. 귀속 [12대수03-03] 정합 |
| `wm-geseq-ac837e7dacae` | GEO-SEQ | 단답형 | ok |  | a1=2,r=2,n=8→256 재유도 일치. 발문 자연·조사 정합. 귀속 [12대수03-03] 정합 |
| `wm-geseq-73f6009d0134` | GEO-SEQ | 단답형 | ok |  | a1=3,r=5,n=3→75 재유도 일치. 발문 자연·조사 정합. 귀속 [12대수03-03] 정합 |
| `wm-geseq-8c5dab49fb26` | GEO-SEQ | 단답형 | ok |  | a1=1,r=5,n=4→125 재유도 일치. 발문 자연·조사 정합. 귀속 [12대수03-03] 정합 |
| `wm-exp-bf4187b90d38` | EXP-EQ | 단답형 | ok |  | 2^x=512→x=9 재유도 일치. 발문 자연·조사 정합. 귀속 [12대수01-08] 정합 |
| `wm-exp-0a4b30c856f9` | EXP-EQ | 단답형 | ok |  | 7^x=49→x=2 재유도 일치. 발문 자연·조사 정합. 귀속 [12대수01-08] 정합 |
| `wm-exp-e091ec7d2fbe` | EXP-EQ | 단답형 | ok |  | 3^x=729→x=6 재유도 일치. 발문 자연·조사 정합. 귀속 [12대수01-08] 정합 |
| `wm-exp-f17f3efb8a5f` | EXP-EQ | 단답형 | ok |  | 2^x=8→x=3 재유도 일치. 발문 자연·조사 정합. 귀속 [12대수01-08] 정합 |
| `wm-exp-bd1bd80d99fb` | EXP-EQ | 단답형 | ok |  | 10^x=10→x=1 재유도 일치. 발문 자연·조사 정합. 귀속 [12대수01-08] 정합 |
| `wm-exp-fa0547a019f8` | EXP-EQ | 단답형 | ok |  | 2^x=128→x=7 재유도 일치. 발문 자연·조사 정합. 귀속 [12대수01-08] 정합 |
| `wm-exp-2f9363738cf2` | EXP-EQ | 단답형 | defect | grammar_break | 발문 '25 을' 조사 받침 오류(이십오→를). 수치·정답 재유도는 일치. 하드코딩 을 계통 |
| `wm-exp-f972237eb614` | EXP-EQ | 단답형 | ok |  | 3^x=27→x=3 재유도 일치. 발문 자연·조사 정합. 귀속 [12대수01-08] 정합 |
| `wm-exp-887ff396d4e8` | EXP-EQ | 단답형 | ok |  | 5^x=5→x=1 재유도 일치. 발문 자연·조사 정합. 귀속 [12대수01-08] 정합 |
| `wm-exp-187727943cdd` | EXP-EQ | 단답형 | ok |  | 6^x=216→x=3 재유도 일치. 발문 자연·조사 정합. 귀속 [12대수01-08] 정합 |
| `wm-log-cf20781a8130` | LOG-EQ | 단답형 | defect | grammar_break | 발문 '2 을' 조사 오류(이→를)+'x가 …만족하는 값은' 구문 비틀림. 수학은 일치 |
| `wm-log-5195ee31653e` | LOG-EQ | 단답형 | ok |  | log_7 x=2→x=49 재유도 일치. 발문·해설 정합. |
| `wm-log-d026609848a9` | LOG-EQ | 단답형 | defect | statement_mismatch | 재서술 도입 '5의 제곱'은 거짓(실제 5^3=125)·'찾아보세' 어미 파손. 오도 차단 |
| `wm-log-d9913c6d1e24` | LOG-EQ | 단답형 | ok |  | log_3 x=4→x=81 재유도 일치. 발문·해설 정합. |
| `wm-log-d5bd9c691022` | LOG-EQ | 단답형 | defect | grammar_break | '원시적으로 무엇인지' 무의미 비문+'2 을' 조사 오류. 수학 재유도는 일치 |
| `wm-log-14bd3014b6b9` | LOG-EQ | 단답형 | defect | statement_mismatch | '5의 거듭제곱근' 용어 거짓(5=5^1 거듭제곱)+'log_5 x = 1 때' 조사 탈락 |
| `wm-log-2b749c441368` | LOG-EQ | 단답형 | ok |  | log_3 x=6→x=729 재유도 일치. 발문·해설 정합. 재서술 자연(수치 불변) |
| `wm-log-31d6d0011812` | LOG-EQ | 단답형 | ok |  | log_2 x=2→x=4 재유도 일치. 발문·해설 정합. |
| `wm-trig-9e0cdc4b2179` | TRIG-VAL | 단답형 | ok |  | sin 60°=sqrt(3)/2 단위원 정의 해설 정합. |
| `wm-trig-13f33b616fa4` | TRIG-VAL | 단답형 | ok |  | sin 30°=1/2 단위원 정의 해설 정합. |
| `wm-trig-8101b7e6781d` | TRIG-VAL | 단답형 | ok |  | tan 60°=sqrt(3) 단위원 정의 해설 정합. 값이 조사 교정 전파 확인 |
| `wm-trig-9215b6e7ebe2` | TRIG-VAL | 단답형 | ok |  | tan 150°=-sqrt(3)/3 단위원 정의 해설 정합. 값이 조사 교정 전파 확인 |
| `wm-trig-3d36abdc44eb` | TRIG-VAL | 단답형 | ok |  | cos 180°=-1 단위원 정의 해설 정합. |

## 문항별 판정 — killer (120 전수)

| slug | 도메인 | 형식 | verdict | 결함류 | 비고 |
|---|---|---|---|---|---|
| `wm-vieta-e50806772c03` | POLY-ROOT | 단답형 | defect | standard_tag_error | SymPy 근곱·c/a=-1 일치. 비에트 문항에 판별식[02-02] 태그—정합은[02-03]. 체감 1스텝<표기4.0 |
| `wm-vieta-026ee42ff8e2` | POLY-ROOT | 단답형 | defect | standard_tag_error | SymPy 근합·-b/a=-3 일치. 삼차 비에트에 이차 판별식[02-02] 태그—[02-07]류 정합. 체감 1스텝<표기4.0 |
| `wm-vieta-3209bf8844da` | POLY-ROOT | 단답형 | defect | standard_tag_error | SymPy 근합·-b/a=3 일치. 삼차 비에트에 이차 판별식[02-02] 태그—[02-07]류 정합. 체감 1스텝<표기4.0 |
| `wm-vieta-b6c05c24c86f` | POLY-ROOT | 단답형 | defect | standard_tag_error | SymPy 근합·-b/a=0 일치. 삼차 비에트에 이차 판별식[02-02] 태그—[02-07]류 정합. 체감 1스텝<표기4.0 |
| `wm-vieta-111d5bc6adf0` | POLY-ROOT | 단답형 | defect | standard_tag_error | SymPy 근곱·-d/a=-9 일치. 삼차 비에트에 이차 판별식[02-02] 태그—[02-07]류 정합. 체감 1스텝<표기4.0 |
| `wm-vieta-3b1a2e7b3151` | POLY-ROOT | 단답형 | defect | standard_tag_error | SymPy 근곱·-d/a=8 일치. 삼차 비에트에 이차 판별식[02-02] 태그—[02-07]류 정합. 체감 1스텝<표기4.0 |
| `wm-vieta-ba85fdd3479b` | POLY-ROOT | 단답형 | defect | standard_tag_error | SymPy 근곱·c/a=1 일치. 비에트 문항에 판별식[02-02] 태그—정합은[02-03]. 체감 1스텝<표기4.0 |
| `wm-vieta-2723467a953f` | POLY-ROOT | 단답형 | defect | standard_tag_error | SymPy 근곱·-d/a=2 일치. 삼차 비에트에 이차 판별식[02-02] 태그—[02-07]류 정합. 체감 1스텝<표기4.0 |
| `wm-vieta-a376e5c5b6aa` | POLY-ROOT | 단답형 | defect | standard_tag_error | SymPy 근합·-b/a=2 일치. 삼차 비에트에 이차 판별식[02-02] 태그—[02-07]류 정합. 체감 1스텝<표기4.0 |
| `wm-vieta-ae425bb7e46c` | POLY-ROOT | 단답형 | defect | standard_tag_error | SymPy 근합·-b/a=-2 일치·상이근 확인. 비에트 문항에 판별식[02-02] 태그—정합은[02-03]. 체감 1스텝<표기4.0 |
| `wm-vieta-dff4712f4a44` | POLY-ROOT | 단답형 | defect | standard_tag_error | SymPy 근합·-b/a=3 일치. 삼차 비에트에 이차 판별식[02-02] 태그—[02-07]류 정합. 체감 1스텝<표기4.0 |
| `wm-vieta-237dba2c7215` | POLY-ROOT | 단답형 | defect | standard_tag_error | SymPy 근합·-b/a=1 일치. 삼차 비에트에 이차 판별식[02-02] 태그—[02-07]류 정합. 체감 1스텝<표기4.0 |
| `wm-vieta-b1d093c3f0e1` | POLY-ROOT | 단답형 | defect | standard_tag_error | SymPy 근곱·-d/a=10 일치. 삼차 비에트에 이차 판별식[02-02] 태그—[02-07]류 정합. 체감 1스텝<표기4.0 |
| `wm-vieta-1e517cb77e94` | POLY-ROOT | 단답형 | defect | standard_tag_error | SymPy 근곱·-d/a=7 일치. 삼차 비에트에 이차 판별식[02-02] 태그—[02-07]류 정합. 체감 1스텝<표기4.0 |
| `wm-vieta-0b436dd6ffe0` | POLY-ROOT | 단답형 | defect | standard_tag_error | SymPy 근곱·c/a=-1 일치. 비에트 문항에 판별식[02-02] 태그—정합은[02-03]. 체감 1스텝<표기4.0 |
| `wm-vieta-8b41c1fc5b43` | POLY-ROOT | 단답형 | defect | standard_tag_error | SymPy 근합·-b/a=0 일치. 비에트 문항에 판별식[02-02] 태그—정합은[02-03]. 체감 1스텝<표기4.0 |
| `wm-vieta-4f74aec4d939` | POLY-ROOT | 단답형 | defect | standard_tag_error | SymPy 근곱·-d/a=6 일치. 삼차 비에트에 이차 판별식[02-02] 태그—[02-07]류 정합. 체감 1스텝<표기4.0 |
| `wm-vieta-fb3ba8b0f5e4` | POLY-ROOT | 단답형 | defect | standard_tag_error | SymPy 근곱·-d/a=4 일치. 삼차 비에트에 이차 판별식[02-02] 태그—[02-07]류 정합. 체감 1스텝<표기4.0 |
| `wm-vieta-46696dc235c7` | POLY-ROOT | 단답형 | defect | standard_tag_error | SymPy 근곱·-d/a=6 일치. 삼차 비에트에 이차 판별식[02-02] 태그—[02-07]류 정합. 체감 1스텝<표기4.0 |
| `wm-vieta-7ddf1f46919d` | POLY-ROOT | 단답형 | defect | standard_tag_error | SymPy 근곱·-d/a=-3 일치. 삼차 비에트에 이차 판별식[02-02] 태그—[02-07]류 정합. 체감 1스텝<표기4.0 |
| `wm-vieta-00114ae0fcba` | POLY-ROOT | 단답형 | defect | standard_tag_error | SymPy 근합·-b/a=-1 일치. 삼차 비에트에 이차 판별식[02-02] 태그—[02-07]류 정합. 체감 1스텝<표기4.0 |
| `wm-vieta-c59122d9151f` | POLY-ROOT | 단답형 | defect | standard_tag_error | SymPy 근합·-b/a=2 일치. 삼차 비에트에 이차 판별식[02-02] 태그—[02-07]류 정합. 체감 1스텝<표기4.0 |
| `wm-vieta-e142748d62a6` | POLY-ROOT | 단답형 | defect | standard_tag_error | SymPy 근곱·c/a=2 일치. 비에트 문항에 판별식[02-02] 태그—정합은[02-03]. 체감 1스텝<표기4.0 |
| `wm-vieta-0019e4b71770` | POLY-ROOT | 단답형 | defect | standard_tag_error | SymPy 근곱·c/a=-5 일치. 비에트 문항에 판별식[02-02] 태그—정합은[02-03]. 체감 1스텝<표기4.0 |
| `wm-vieta-727bc0faf60f` | POLY-ROOT | 단답형 | defect | standard_tag_error | SymPy 근합·-b/a=2 일치. 비에트 문항에 판별식[02-02] 태그—정합은[02-03]. 체감 1스텝<표기4.0 |
| `wm-vieta-092ccb37295c` | POLY-ROOT | 단답형 | defect | standard_tag_error | SymPy 근곱·c/a=3 일치. 비에트 문항에 판별식[02-02] 태그—정합은[02-03]. 체감 1스텝<표기4.0 |
| `wm-vieta-c37f1d83bd75` | POLY-ROOT | 단답형 | defect | standard_tag_error | SymPy 근곱·-d/a=12 일치. 삼차 비에트에 이차 판별식[02-02] 태그—[02-07]류 정합. 체감 1스텝<표기4.0 |
| `wm-vieta-b85b00f5a068` | POLY-ROOT | 단답형 | defect | standard_tag_error | SymPy 근곱·c/a=7 일치. 비에트 문항에 판별식[02-02] 태그—정합은[02-03]. 체감 1스텝<표기4.0 |
| `wm-vieta-321052ee4292` | POLY-ROOT | 단답형 | defect | standard_tag_error | SymPy 근곱·c/a=4 일치. 비에트 문항에 판별식[02-02] 태그—정합은[02-03]. 체감 1스텝<표기4.0 |
| `wm-vieta-e2c2865e3bcf` | POLY-ROOT | 단답형 | defect | standard_tag_error | SymPy 근합·-b/a=2 일치. 비에트 문항에 판별식[02-02] 태그—정합은[02-03]. 체감 1스텝<표기4.0 |
| `wm-vieta-84bbd6223966` | POLY-ROOT | 단답형 | defect | standard_tag_error | SymPy 근합·-b/a=-4 일치·상이근 확인. 비에트 문항에 판별식[02-02] 태그—정합은[02-03]. 체감 1스텝<표기4.0 |
| `wm-vieta-99d2d6c4e50d` | POLY-ROOT | 단답형 | defect | standard_tag_error | SymPy 근곱·c/a=-2 일치. 비에트 문항에 판별식[02-02] 태그—정합은[02-03]. 체감 1스텝<표기4.0 |
| `wm-vieta-74997d85032e` | POLY-ROOT | 단답형 | defect | standard_tag_error | SymPy 근곱·c/a=7 일치. 비에트 문항에 판별식[02-02] 태그—정합은[02-03]. 체감 1스텝<표기4.0 |
| `wm-vieta-fed891e8e0ef` | POLY-ROOT | 단답형 | defect | standard_tag_error | SymPy 근합·-b/a=6 일치. 삼차 비에트에 이차 판별식[02-02] 태그—[02-07]류 정합. 체감 1스텝<표기4.0 |
| `wm-vieta-249c7b42b041` | POLY-ROOT | 단답형 | defect | standard_tag_error | SymPy 근곱·c/a=2 일치. 비에트 문항에 판별식[02-02] 태그—정합은[02-03]. 체감 1스텝<표기4.0 |
| `wm-vieta-9c535c076835` | POLY-ROOT | 단답형 | defect | standard_tag_error | SymPy 근합·-b/a=6 일치·상이근 확인. 비에트 문항에 판별식[02-02] 태그—정합은[02-03]. 체감 1스텝<표기4.0 |
| `wm-vieta-6a2fe06a415f` | POLY-ROOT | 단답형 | defect | standard_tag_error | SymPy 근곱·-d/a=-18 일치. 삼차 비에트에 이차 판별식[02-02] 태그—[02-07]류 정합. 체감 1스텝<표기4.0 |
| `wm-vieta-99abb9c472fc` | POLY-ROOT | 단답형 | defect | standard_tag_error | SymPy 근합·-b/a=0 일치. 삼차 비에트에 이차 판별식[02-02] 태그—[02-07]류 정합. 체감 1스텝<표기4.0 |
| `wm-vieta-78d7cd907f98` | POLY-ROOT | 단답형 | defect | standard_tag_error | SymPy 근곱·c/a=-4 일치. 비에트 문항에 판별식[02-02] 태그—정합은[02-03]. 체감 1스텝<표기4.0 |
| `wm-vieta-07baec9b4b61` | POLY-ROOT | 단답형 | defect | standard_tag_error | SymPy 근곱·-d/a=-3 일치. 삼차 비에트에 이차 판별식[02-02] 태그—[02-07]류 정합. 체감 1스텝<표기4.0 |
| `wm-vieta-cbb55cf414e2` | POLY-ROOT | 단답형 | defect | standard_tag_error | SymPy 근합·-b/a=0 일치. 비에트 문항에 판별식[02-02] 태그—정합은[02-03]. 체감 1스텝<표기4.0 |
| `wm-vieta-329c5fc0b350` | POLY-ROOT | 단답형 | defect | standard_tag_error | SymPy 근곱·-d/a=4 일치. 삼차 비에트에 이차 판별식[02-02] 태그—[02-07]류 정합. 체감 1스텝<표기4.0 |
| `wm-vieta-235e315cab30` | POLY-ROOT | 단답형 | defect | standard_tag_error | SymPy 근합·-b/a=-1 일치. 삼차 비에트에 이차 판별식[02-02] 태그—[02-07]류 정합. 체감 1스텝<표기4.0 |
| `wm-vieta-e4d21c6b85c2` | POLY-ROOT | 단답형 | defect | standard_tag_error | SymPy 근곱·-d/a=-10 일치. 삼차 비에트에 이차 판별식[02-02] 태그—[02-07]류 정합. 체감 1스텝<표기4.0 |
| `wm-vieta-776abad877e8` | POLY-ROOT | 단답형 | defect | standard_tag_error | SymPy 근곱·-d/a=2 일치. 삼차 비에트에 이차 판별식[02-02] 태그—[02-07]류 정합. 체감 1스텝<표기4.0 |
| `wm-vieta-5a740103c76d` | POLY-ROOT | 단답형 | defect | standard_tag_error | SymPy 근곱·-d/a=3 일치. 삼차 비에트에 이차 판별식[02-02] 태그—[02-07]류 정합. 체감 1스텝<표기4.0 |
| `wm-vieta-f6f655546fda` | POLY-ROOT | 단답형 | defect | standard_tag_error | SymPy 근곱·-d/a=-4 일치. 삼차 비에트에 이차 판별식[02-02] 태그—[02-07]류 정합. 체감 1스텝<표기4.0 |
| `wm-vieta-8b5bc3d27212` | POLY-ROOT | 단답형 | defect | standard_tag_error | SymPy 근곱·c/a=-3 일치. 비에트 문항에 판별식[02-02] 태그—정합은[02-03]. 체감 1스텝<표기4.0 |
| `wm-vieta-cecac28d0bb0` | POLY-ROOT | 단답형 | defect | standard_tag_error | SymPy 근합·-b/a=-6 일치·상이근 확인. 비에트 문항에 판별식[02-02] 태그—정합은[02-03]. 체감 1스텝<표기4.0 |
| `wm-vieta-4f7061261944` | POLY-ROOT | 단답형 | defect | standard_tag_error | SymPy 근곱·c/a=-6 일치. 비에트 문항에 판별식[02-02] 태그—정합은[02-03]. 체감 1스텝<표기4.0 |
| `wm-vieta-e4773c0dfcf9` | POLY-ROOT | 단답형 | defect | standard_tag_error | SymPy 근합·-b/a=2 일치·상이근 확인. 비에트 문항에 판별식[02-02] 태그—정합은[02-03]. 체감 1스텝<표기4.0 |
| `wm-vieta-c5977086ab2e` | POLY-ROOT | 단답형 | defect | standard_tag_error | SymPy 근합·-b/a=2 일치. 비에트 문항에 판별식[02-02] 태그—정합은[02-03]. 체감 1스텝<표기4.0 |
| `wm-vieta-0627ea0ebbcc` | POLY-ROOT | 단답형 | defect | standard_tag_error | SymPy 근합·-b/a=-4 일치·상이근 확인. 비에트 문항에 판별식[02-02] 태그—정합은[02-03]. 체감 1스텝<표기4.0 |
| `wm-vieta-c9086ebed5aa` | POLY-ROOT | 단답형 | defect | standard_tag_error | SymPy 근합·-b/a=0 일치. 비에트 문항에 판별식[02-02] 태그—정합은[02-03]. 체감 1스텝<표기4.0 |
| `wm-vieta-c2b9aeff27bb` | POLY-ROOT | 단답형 | defect | standard_tag_error | SymPy 근곱·-d/a=-6 일치. 삼차 비에트에 이차 판별식[02-02] 태그—[02-07]류 정합. 체감 1스텝<표기4.0 |
| `wm-vieta-229fd47bdae5` | POLY-ROOT | 단답형 | defect | standard_tag_error | SymPy 근곱·c/a=-2 일치. 비에트 문항에 판별식[02-02] 태그—정합은[02-03]. 체감 1스텝<표기4.0 |
| `wm-vieta-6de567b4bd87` | POLY-ROOT | 단답형 | defect | standard_tag_error | SymPy 근합·-b/a=4 일치. 비에트 문항에 판별식[02-02] 태그—정합은[02-03]. 체감 1스텝<표기4.0 |
| `wm-vieta-c9bd7f31e66d` | POLY-ROOT | 단답형 | defect | standard_tag_error | SymPy 근합·-b/a=-6 일치. 비에트 문항에 판별식[02-02] 태그—정합은[02-03]. 체감 1스텝<표기4.0 |
| `wm-vieta-052bdf936d47` | POLY-ROOT | 단답형 | defect | standard_tag_error | SymPy 근합·-b/a=-1 일치. 삼차 비에트에 이차 판별식[02-02] 태그—[02-07]류 정합. 체감 1스텝<표기4.0 |
| `wm-vieta-36d8584f3a70` | POLY-ROOT | 단답형 | defect | standard_tag_error | SymPy 근곱·-d/a=-2 일치. 삼차 비에트에 이차 판별식[02-02] 태그—[02-07]류 정합. 체감 1스텝<표기4.0 |
| `wm-vieta-f578fcd78403` | POLY-ROOT | 단답형 | defect | standard_tag_error | SymPy 근합·-b/a=-2 일치. 비에트 문항에 판별식[02-02] 태그—정합은[02-03]. 체감 1스텝<표기4.0 |
| `wm-vieta-ee8308724bab` | POLY-ROOT | 단답형 | defect | standard_tag_error | SymPy 근합·-b/a=2 일치. 비에트 문항에 판별식[02-02] 태그—정합은[02-03]. 체감 1스텝<표기4.0 |
| `wm-vieta-36d07de43904` | POLY-ROOT | 단답형 | defect | standard_tag_error | SymPy 근합·-b/a=-4 일치·상이근 확인. 비에트 문항에 판별식[02-02] 태그—정합은[02-03]. 체감 1스텝<표기4.0 |
| `wm-vieta-a84ea32e18cd` | POLY-ROOT | 단답형 | defect | standard_tag_error | SymPy 근곱·c/a=6 일치. 비에트 문항에 판별식[02-02] 태그—정합은[02-03]. 체감 1스텝<표기4.0 |
| `wm-vieta-6afb9109c8c9` | POLY-ROOT | 단답형 | defect | standard_tag_error | SymPy 근곱·c/a=-2 일치. 비에트 문항에 판별식[02-02] 태그—정합은[02-03]. 체감 1스텝<표기4.0 |
| `wm-vieta-8555bb589f8e` | POLY-ROOT | 단답형 | defect | standard_tag_error | SymPy 근합·-b/a=-4 일치. 삼차 비에트에 이차 판별식[02-02] 태그—[02-07]류 정합. 체감 1스텝<표기4.0 |
| `wm-vieta-712d0285e74e` | POLY-ROOT | 단답형 | defect | standard_tag_error | SymPy 근곱·-d/a=2 일치. 삼차 비에트에 이차 판별식[02-02] 태그—[02-07]류 정합. 체감 1스텝<표기4.0 |
| `wm-vieta-658ea253327c` | POLY-ROOT | 단답형 | defect | standard_tag_error | SymPy 근합·-b/a=3 일치. 삼차 비에트에 이차 판별식[02-02] 태그—[02-07]류 정합. 체감 1스텝<표기4.0 |
| `wm-vieta-b03b24ebf626` | POLY-ROOT | 단답형 | defect | standard_tag_error | SymPy 근합·-b/a=6 일치. 비에트 문항에 판별식[02-02] 태그—정합은[02-03]. 체감 1스텝<표기4.0 |
| `wm-vieta-85412ed5e7a5` | POLY-ROOT | 단답형 | defect | standard_tag_error | SymPy 근곱·-d/a=2 일치. 삼차 비에트에 이차 판별식[02-02] 태그—[02-07]류 정합. 체감 1스텝<표기4.0 |
| `wm-vieta-4938e72d642b` | POLY-ROOT | 단답형 | defect | standard_tag_error | SymPy 근합·-b/a=7 일치. 삼차 비에트에 이차 판별식[02-02] 태그—[02-07]류 정합. 체감 1스텝<표기4.0 |
| `wm-vieta-19904b48ad5e` | POLY-ROOT | 단답형 | defect | standard_tag_error | SymPy 근합·-b/a=3 일치. 삼차 비에트에 이차 판별식[02-02] 태그—[02-07]류 정합. 체감 1스텝<표기4.0 |
| `wm-vieta-39061a2e1c2d` | POLY-ROOT | 단답형 | defect | standard_tag_error | SymPy 근곱·c/a=-5 일치. 비에트 문항에 판별식[02-02] 태그—정합은[02-03]. 체감 1스텝<표기4.0 |
| `wm-vieta-f93e0429f5e1` | POLY-ROOT | 단답형 | defect | standard_tag_error | SymPy 근곱·-d/a=-4 일치. 삼차 비에트에 이차 판별식[02-02] 태그—[02-07]류 정합. 체감 1스텝<표기4.0 |
| `wm-vieta-5d84ee630e88` | POLY-ROOT | 단답형 | defect | standard_tag_error | SymPy 근곱·-d/a=-15 일치. 삼차 비에트에 이차 판별식[02-02] 태그—[02-07]류 정합. 체감 1스텝<표기4.0 |
| `wm-vieta-b67d3e69a487` | POLY-ROOT | 단답형 | defect | standard_tag_error | SymPy 근합·-b/a=4 일치·상이근 확인. 비에트 문항에 판별식[02-02] 태그—정합은[02-03]. 체감 1스텝<표기4.0 |
| `wm-vieta-e20da474cffc` | POLY-ROOT | 단답형 | defect | standard_tag_error | SymPy 근곱·-d/a=-15 일치. 삼차 비에트에 이차 판별식[02-02] 태그—[02-07]류 정합. 체감 1스텝<표기4.0 |
| `wm-vieta-d8ce576ec402` | POLY-ROOT | 단답형 | defect | standard_tag_error | SymPy 근곱·c/a=-1 일치. 비에트 문항에 판별식[02-02] 태그—정합은[02-03]. 체감 1스텝<표기4.0 |
| `wm-vieta-59caf1b22775` | POLY-ROOT | 단답형 | defect | standard_tag_error | SymPy 근곱·c/a=-2 일치. 비에트 문항에 판별식[02-02] 태그—정합은[02-03]. 체감 1스텝<표기4.0 |
| `wm-vieta-7378be0988a1` | POLY-ROOT | 단답형 | defect | standard_tag_error | SymPy 근합·-b/a=6 일치. 비에트 문항에 판별식[02-02] 태그—정합은[02-03]. 체감 1스텝<표기4.0 |
| `wm-vieta-02863ba72799` | POLY-ROOT | 단답형 | defect | standard_tag_error | SymPy 근합·-b/a=-4 일치·상이근 확인. 비에트 문항에 판별식[02-02] 태그—정합은[02-03]. 체감 1스텝<표기4.0 |
| `wm-vieta-0aaf3a1af7c0` | POLY-ROOT | 단답형 | defect | standard_tag_error | SymPy 근합·-b/a=3 일치. 삼차 비에트에 이차 판별식[02-02] 태그—[02-07]류 정합. 체감 1스텝<표기4.0 |
| `wm-vieta-a668c99eea6c` | POLY-ROOT | 단답형 | defect | standard_tag_error | SymPy 근합·-b/a=4 일치. 비에트 문항에 판별식[02-02] 태그—정합은[02-03]. 체감 1스텝<표기4.0 |
| `wm-vieta-11b9fa15e632` | POLY-ROOT | 단답형 | defect | standard_tag_error | SymPy 근합·-b/a=-3 일치. 삼차 비에트에 이차 판별식[02-02] 태그—[02-07]류 정합. 체감 1스텝<표기4.0 |
| `wm-vieta-54b1ce6804f7` | POLY-ROOT | 단답형 | defect | standard_tag_error | SymPy 근합·-b/a=6 일치·상이근 확인. 비에트 문항에 판별식[02-02] 태그—정합은[02-03]. 체감 1스텝<표기4.0 |
| `wm-vieta-2fe4b495f897` | POLY-ROOT | 단답형 | defect | standard_tag_error | SymPy 근곱·-d/a=-15 일치. 삼차 비에트에 이차 판별식[02-02] 태그—[02-07]류 정합. 체감 1스텝<표기4.0 |
| `wm-vieta-aec8810a8cf8` | POLY-ROOT | 단답형 | defect | standard_tag_error | SymPy 근합·-b/a=1 일치. 삼차 비에트에 이차 판별식[02-02] 태그—[02-07]류 정합. 체감 1스텝<표기4.0 |
| `wm-vieta-5b5f07e577f2` | POLY-ROOT | 단답형 | defect | standard_tag_error | SymPy 근곱·-d/a=6 일치. 삼차 비에트에 이차 판별식[02-02] 태그—[02-07]류 정합. 체감 1스텝<표기4.0 |
| `wm-vieta-1c4db9ba942b` | POLY-ROOT | 단답형 | defect | standard_tag_error | SymPy 근합·-b/a=-4 일치·상이근 확인. 비에트 문항에 판별식[02-02] 태그—정합은[02-03]. 체감 1스텝<표기4.0 |
| `wm-vieta-e00426ca9cf5` | POLY-ROOT | 단답형 | defect | standard_tag_error | SymPy 근합·-b/a=-2 일치·상이근 확인. 비에트 문항에 판별식[02-02] 태그—정합은[02-03]. 체감 1스텝<표기4.0 |
| `wm-vieta-a216c1fe966b` | POLY-ROOT | 단답형 | defect | standard_tag_error | SymPy 근곱·-d/a=3 일치. 삼차 비에트에 이차 판별식[02-02] 태그—[02-07]류 정합. 체감 1스텝<표기4.0 |
| `wm-vieta-83de3dd239bd` | POLY-ROOT | 단답형 | defect | standard_tag_error | SymPy 근곱·c/a=-2 일치. 비에트 문항에 판별식[02-02] 태그—정합은[02-03]. 체감 1스텝<표기4.0 |
| `wm-vieta-65dff9cf308d` | POLY-ROOT | 단답형 | defect | standard_tag_error | SymPy 근곱·-d/a=-5 일치. 삼차 비에트에 이차 판별식[02-02] 태그—[02-07]류 정합. 체감 1스텝<표기4.0 |
| `wm-vieta-d3528183c2d4` | POLY-ROOT | 단답형 | defect | standard_tag_error | SymPy 근합·-b/a=5 일치. 삼차 비에트에 이차 판별식[02-02] 태그—[02-07]류 정합. 체감 1스텝<표기4.0 |
| `wm-vieta-eaacbd80ad20` | POLY-ROOT | 단답형 | defect | standard_tag_error | SymPy 근합·-b/a=1 일치. 삼차 비에트에 이차 판별식[02-02] 태그—[02-07]류 정합. 체감 1스텝<표기4.0 |
| `wm-vieta-af54c65d1574` | POLY-ROOT | 단답형 | defect | standard_tag_error | SymPy 근합·-b/a=1 일치. 삼차 비에트에 이차 판별식[02-02] 태그—[02-07]류 정합. 체감 1스텝<표기4.0 |
| `wm-vieta-c0911b459f73` | POLY-ROOT | 단답형 | defect | standard_tag_error | SymPy 근곱·c/a=-6 일치. 비에트 문항에 판별식[02-02] 태그—정합은[02-03]. 체감 1스텝<표기4.0 |
| `wm-vieta-d137aea217d5` | POLY-ROOT | 단답형 | defect | standard_tag_error | SymPy 근합·-b/a=1 일치. 삼차 비에트에 이차 판별식[02-02] 태그—[02-07]류 정합. 체감 1스텝<표기4.0 |
| `wm-vieta-b09214dc2d7e` | POLY-ROOT | 단답형 | defect | standard_tag_error | SymPy 근곱·c/a=-4 일치. 비에트 문항에 판별식[02-02] 태그—정합은[02-03]. 체감 1스텝<표기4.0 |
| `wm-vieta-a347dd4206e1` | POLY-ROOT | 단답형 | defect | standard_tag_error | SymPy 근곱·c/a=4 일치. 비에트 문항에 판별식[02-02] 태그—정합은[02-03]. 체감 1스텝<표기4.0 |
| `wm-vieta-0e0141e67d69` | POLY-ROOT | 단답형 | defect | standard_tag_error | SymPy 근곱·-d/a=-4 일치. 삼차 비에트에 이차 판별식[02-02] 태그—[02-07]류 정합. 체감 1스텝<표기4.0 |
| `wm-vieta-09457b54f07f` | POLY-ROOT | 단답형 | defect | standard_tag_error | SymPy 근곱·c/a=2 일치. 비에트 문항에 판별식[02-02] 태그—정합은[02-03]. 체감 1스텝<표기4.0 |
| `wm-vieta-2673fb8a6c3b` | POLY-ROOT | 단답형 | defect | standard_tag_error | SymPy 근합·-b/a=-2 일치. 삼차 비에트에 이차 판별식[02-02] 태그—[02-07]류 정합. 체감 1스텝<표기4.0 |
| `wm-vieta-bb684c7793d4` | POLY-ROOT | 단답형 | defect | standard_tag_error | SymPy 근곱·c/a=-7 일치. 비에트 문항에 판별식[02-02] 태그—정합은[02-03]. 체감 1스텝<표기4.0 |
| `wm-vieta-911e17a09738` | POLY-ROOT | 단답형 | defect | standard_tag_error | SymPy 근곱·c/a=-6 일치. 비에트 문항에 판별식[02-02] 태그—정합은[02-03]. 체감 1스텝<표기4.0 |
| `wm-vieta-db37544dc906` | POLY-ROOT | 단답형 | defect | standard_tag_error | SymPy 근곱·c/a=3 일치. 비에트 문항에 판별식[02-02] 태그—정합은[02-03]. 체감 1스텝<표기4.0 |
| `wm-vieta-6572e98eff9a` | POLY-ROOT | 단답형 | defect | standard_tag_error | SymPy 근합·-b/a=0 일치. 삼차 비에트에 이차 판별식[02-02] 태그—[02-07]류 정합. 체감 1스텝<표기4.0 |
| `wm-vieta-a05ed729d1ba` | POLY-ROOT | 단답형 | defect | standard_tag_error | SymPy 근합·-b/a=6 일치. 비에트 문항에 판별식[02-02] 태그—정합은[02-03]. 체감 1스텝<표기4.0 |
| `wm-vieta-724550c624d4` | POLY-ROOT | 단답형 | defect | standard_tag_error | SymPy 근합·-b/a=0 일치. 비에트 문항에 판별식[02-02] 태그—정합은[02-03]. 체감 1스텝<표기4.0 |
| `wm-vieta-18d26c9e2ea6` | POLY-ROOT | 단답형 | defect | standard_tag_error | SymPy 근곱·c/a=6 일치. 비에트 문항에 판별식[02-02] 태그—정합은[02-03]. 체감 1스텝<표기4.0 |
| `wm-vieta-17c117d1fb4d` | POLY-ROOT | 단답형 | defect | standard_tag_error | SymPy 근합·-b/a=-6 일치·상이근 확인. 비에트 문항에 판별식[02-02] 태그—정합은[02-03]. 체감 1스텝<표기4.0 |
| `wm-vieta-ae4ae57dfeec` | POLY-ROOT | 단답형 | defect | standard_tag_error | SymPy 근합·-b/a=-6 일치·상이근 확인. 비에트 문항에 판별식[02-02] 태그—정합은[02-03]. 체감 1스텝<표기4.0 |
| `wm-vieta-f259939964a6` | POLY-ROOT | 단답형 | defect | standard_tag_error | SymPy 근곱·-d/a=-6 일치. 삼차 비에트에 이차 판별식[02-02] 태그—[02-07]류 정합. 체감 1스텝<표기4.0 |
| `wm-vieta-ed2012fe1341` | POLY-ROOT | 단답형 | defect | standard_tag_error | SymPy 근합·-b/a=1 일치. 삼차 비에트에 이차 판별식[02-02] 태그—[02-07]류 정합. 체감 1스텝<표기4.0 |
| `wm-vieta-429730cf0a84` | POLY-ROOT | 단답형 | defect | standard_tag_error | SymPy 근합·-b/a=1 일치. 삼차 비에트에 이차 판별식[02-02] 태그—[02-07]류 정합. 체감 1스텝<표기4.0 |
| `wm-vieta-ec7a5999a82f` | POLY-ROOT | 단답형 | defect | standard_tag_error | SymPy 근합·-b/a=-2 일치·상이근 확인. 비에트 문항에 판별식[02-02] 태그—정합은[02-03]. 체감 1스텝<표기4.0 |
| `wm-vieta-60aaac08272a` | POLY-ROOT | 단답형 | defect | standard_tag_error | SymPy 근합·-b/a=1 일치. 삼차 비에트에 이차 판별식[02-02] 태그—[02-07]류 정합. 체감 1스텝<표기4.0 |
| `wm-vieta-e52995a29730` | POLY-ROOT | 단답형 | defect | standard_tag_error | SymPy 근곱·c/a=-1 일치. 비에트 문항에 판별식[02-02] 태그—정합은[02-03]. 체감 1스텝<표기4.0 |
| `wm-vieta-d945bfe1e0f1` | POLY-ROOT | 단답형 | defect | standard_tag_error | SymPy 근합·-b/a=1 일치. 삼차 비에트에 이차 판별식[02-02] 태그—[02-07]류 정합. 체감 1스텝<표기4.0 |
| `wm-vieta-9fc7328f0927` | POLY-ROOT | 단답형 | defect | standard_tag_error | SymPy 근합·-b/a=-2 일치. 삼차 비에트에 이차 판별식[02-02] 태그—[02-07]류 정합. 체감 1스텝<표기4.0 |
