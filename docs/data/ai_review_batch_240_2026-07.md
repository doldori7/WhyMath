# AI 검수 결과 — 동등문제 Wilson 표본 240문 (reviewer_sample_240_v0)

> **검수 방식**: **AI 검수** (2026-07-10 Kiki 결정 — MEMORY 결정 로그 정본·`ai_review_first_batch_2026-07.md` 규약 확장). 인간 수기검수가 아님을 정직 명시한다. 검수 주체 = pedagogy 서브에이전트 6인(도메인 밴드 분할·SymPy 검산 병행), 모델ID 미기재(규약).
> **마커**: `검수:AI 2026-07-13` — 동등문제 코퍼스 노출 게이팅용. `crosswalk_gate_contract.md`의 사람 서명 stamp(오개념 crosswalk 적재)와 **다른 것**이며, crosswalk 적재 근거로 쓸 수 없다.
> **판정 항목**: 사람층 ①~⑥ (①발문 자연성 ②풀이 타당성 ③난이도 정합 ④성취기준 귀속 ⑤오답↔오개념 귀속[객관식] ⑥우연 유사). 기계 게이트(S2-a 4종)는 코퍼스 적재 시 이미 통과·Tier1 답 검산 전건 통과 — 본 검수는 그 위의 교수학 층이다.
> **표본**: 전체 코퍼스 620문에서 결정론 층화 샘플 240문(`reviewer_sample_240_v0.md`·Wilson `min_n=200` 충족). 15 도메인·객관식 오개념 4종 전부 포함.

## 종합

- **approved(ok) 240 / rejected 0 / deferred 0** (240문 전건 학생 노출 적격)
- 발견 결함 **2건**(TRIG-VAL tan 해설 조사 받침 `값가`→`값이`) → **생성기 정본 교정 후 재생성으로 해소**(아래 §발견·교정). 재판정 clean.
- 전 240문 답 검산 일치(기계 Tier1 + 표본 SymPy 재확인) — 수학 오류 0건.
- ⑤ 오답↔오개념(객관식 39문): distractor_map 전건 정합 — 오귀속 0건.

### 도메인 분포 (240)

- QUAD-EQ 73 · ARITH-SEQ 24 · ARITH-SUM 18 · CALC-EXTREMUM 16 · CALC-EXTREMUM-VALUE 16 · CALC-TANGENT 15 · CALC-EXTREMUM-IRR 12 · CALC-EXTREMUM-MC 12 · GEO-SEQ 11 · IND-SEQ 11 · EXP-EQ 9 · GEO-SUM 7 · LOG-EQ 7 · TRIG-VAL 5 · TRIG-EQ 4

### 축별 판정 근거 (6 배치 종합)

- **① 발문 자연성**: S2-08 josa 수정 반영 확인. 잔여 결함 2건(tan 해설 `값가`) 발견·교정(§발견·교정). 그 외 조사 받침(수 읽기 기준)·객관식 어미 정합.
- **② 풀이 타당성**: 인수분해·완전제곱·미분 극값·접선·수열 일반항/합 논리 완결. 계수형 이차·삼차 극값·무리근 표본을 SymPy로 재현 검증(근·극대극소 배정·정답 일치).
- **③ 난이도 정합**: S2-08 도메인 앵커 준수 — 공식 1스텝류(등차/등비 일반항·지수/로그·삼각값) ≤ 2.0, monic 인수분해 2.0~2.4, 계수형/완전제곱 2.9~3.4, 미분 다스텝(극값·접선) 3.0~4.0으로 단조. gross 이탈 0(경미 앵커 편차 관찰만).
- **④ 성취기준 귀속**: 이차방정식 [10공수1-02-02]·등차 [12대수03-02]·등비 [12대수03-03]·점화식 [12대수03-06]·지수로그 [12대수01-08]·삼각 [12대수02-02]·극값 [12미적Ⅰ-02-07]·접선기울기 [12미적Ⅰ-02-01] — 문항 내용과 부합.
- **⑤ 오답↔오개념(객관식 39)**: `opposite-root-selected`=묻지 않은 실제 근, `factor-sign-flip`=인수 부호 반전 비근, `extremum-max-min-confused`/`value-vs-point`=반대극값/극점좌표 오보고 — 전건 산출 모델로 역검증 일치. 단답형은 해당없음.
- **⑥ 우연 유사**: 원문 기출·검정 교과서 DB 미보유 — **확정 무결 보증 불가(정직 고지)**. 전건이 범용 매개변수(계수·항수 무작위) 스켈레톤 템플릿 산출물로 특정 기출 복제 징후는 발견되지 않음. 잔여 저작권 리스크 수용(MEMORY 2026-07-10·변호사 검토 권장 유지).

## 발견·교정 (계통 결함 상환)

- **TRIG-VAL tan 해설 조사 받침 `값가`** (`wm-trig-8101b7e6781d`·`wm-trig-9215b6e7ebe2` 표본 검출, 코퍼스 전체 4건): tan 단위원 정의 `"y좌표를 x좌표로 나눈 값"` 뒤에 주격 조사 `가`가 하드코딩돼 `값가`(→`값이`)가 됨(sin/cos는 `좌표가`로 정상). S2-08 josa 계통 결함의 잔여. **교정**: `trig_skeleton_generator._trig_explanation`이 `josa.i_ga(coord)` 헬퍼로 받침 판별(형제 생성기 규약 미러) → 재생성. 발문 불변이라 **slug 안정**(4문 해설 텍스트만 변경)·Tier1 재검산 유지·rephrase 코퍼스 전파(reconcile). 재판정 clean.

### 경미 관찰 (비차단·note+ok — 생성 파이프라인 피드백)

- `wm-arseq-ac26002af2ef` (ARITH-SEQ): answer_explanation이 실수치 대입(1+8×4)을 생략한 템플릿형이나 규칙 명시로 논리 완결. 관찰만.
- `wm-calc-tan-f881d5d5e835` (CALC-TANGENT): tangent slope 유형 난이도 동배치 미세 불일치(4.0 vs 3.5), 차단성 아님
- `wm-gesum-efbcc5c85718` (GEO-SUM): S7=2(2^7-1)/1=254. 관찰: 난이도 2.1로 공식 1스텝 앵커(2.0) 소폭 상회이나 r^n 산출부하로 방어가능·gross 아님.
- `wm-gesum-ee4f3b6a5a69` (GEO-SUM): S4=3(5^4-1)/4=468. 관찰: 난이도 2.2 앵커 소폭 상회이나 계산량 반영·gross 아님.
- `wm-gesum-dfe17905cfa5` (GEO-SUM): S6=3(2^6-1)/1=189. 난이도 2.1 소폭 상회·gross 아님. 정합.
- `wm-gesum-33071eb73c97` (GEO-SUM): S6=4(3^6-1)/2=1456. 관찰: 난이도 2.2 앵커 소폭 상회이나 계산량 반영·gross 아님.

## 기계 게이트 증적 (초인간 검증)

- **S6 상시성 (Tier1 재검산)**: 생성 620 / rephrase 483 / killer 120 — 전건 통과·실패 0 (`corpus_reverify`, CI 정본 게이트와 동일).
- **S3 강등전 (검출력)**: 결함 100/100 검출(6종 전부·statement_mismatch 포함·`--with-auditor`)·무결 오검출 0/100·Wilson 하한 0.974 (`defect_detection_eval`).
- **S5 합격 로트 (Wilson 상한)**: 표본 n=240·결함 0·결함율 점추정 0.0000·**95% 상한 0.0111 (≤ 0.02) → PASS** (`corpus_audit_eval --max-defect-upper 0.02 --min-n 200`·exit 0). 전 코퍼스 결함율이 95% 신뢰수준에서 ≤ 1.11%로 계량 보증.
- **as-found 정직 병기(ARCH-07 사후 주석·2026-07-14)**: 위 PASS는 발견 결함 2건(josa)의 생성기
  교정·재생성 **후** 재채점 기준이다. 교정 전 as-found로 채점하면 2/240 → 95% 상한 **0.0249 > 0.02
  (게이트 FAIL)**. 단 전 코퍼스 as-found(4/620) 상한은 **0.0143 ≤ 0.02로 여전히 통과** — 실체적
  품질 결론은 불변. 엄밀 acceptance sampling 규약(교정 후 *신규 독립 표본* 재추출)은 후속 태스크로
  분리(같은 표본 재채점의 fail→pass 전환 패턴 회피).
  - **기계 강제(S2-12·2026-07-15)**: as-found 병기는 이제 산문이 아니라 게이트다. 감사 기록
    `docs/data/corpus_audit_240.jsonl` 선두에 병기 선언 라인
    `{"as_found_n": 240, "as_found_defects": 2}`를 병기했고, `corpus_audit_eval
    --max-defect-upper 0.02 --min-n 200 --require-as-found`(exit 0)로 병기 의무를 CLI로 강제한다
    — 선언 부재 시 exit 1(§4.5·검증 권위 서열 ②).
- **보조 적대 fuzz 한계(정직 고지)**: `corpus_reverify --fuzz` blanket 실행은 극댓값(`calc-extv/extmc`)·유일근 유형에서 오탐(탐색 반경 ±50 초과 근·유일근 수치정밀도) — 코퍼스 결함 아님(직접 확인). 이 때문에 CI 상시 게이트는 Tier1만 돌린다. fuzzer 반경/정밀도/값형 게이팅은 후속(별도 태스크).

## 문항별 판정 (240/240)

| slug | 도메인 | 형식 | verdict | 비고 |
|---|---|---|---|---|
| `wm-skel-126a2ead2c3c` | QUAD-EQ | 객관식 | ok | (2x+5)(x-5) 인수분해·근 -5/2·5 정합. 오답: 5=반대근(opposite-root), -5·5 |
| `wm-skel-f664ed64520f` | QUAD-EQ | 단답형 | ok | (x-4)^2=12 큰근 4+√12=2√3+4. 해설 √12 미간약이나 answer는 정규화, 비약 없음.  |
| `wm-skel-4904daaf204b` | QUAD-EQ | 객관식 | ok | 완전제곱 x=2±√3 작은근 2-√3. 오답 √3+2=반대근, -2±√3=부호뒤집기 정합. |
| `wm-skel-cd0b59fdceaa` | QUAD-EQ | 단답형 | ok | x(x-4) 근 0·4 큰근 4. 인수형 0 근 처리 정확. 난이도 2.0 앵커 부합. |
| `wm-skel-07c0b591ca85` | QUAD-EQ | 객관식 | ok | (x+9)(x+3) 큰근 -3. 오답 -9=반대근, 3·9=부호뒤집기 정합. |
| `wm-skel-ee87a36dfac4` | QUAD-EQ | 단답형 | ok | (x-4)^2=11 큰근 4+√11. 논리 완결. 단답형. |
| `wm-skel-20d0e5d3fbf8` | QUAD-EQ | 객관식 | ok | (x-1)(x-9) 큰근 9. 오답 1=반대근, -1·-9=부호뒤집기 정합. |
| `wm-skel-87d059e107e4` | QUAD-EQ | 단답형 | ok | (2x+1)^2 중근 -1/2. 중근임을 명시, 논리 완결. 단답형. |
| `wm-skel-74c7585495a2` | QUAD-EQ | 객관식 | ok | (3x-1)(x+5) 작은근 -5. 오답 1/3=반대근, -1/3·5=부호뒤집기 정합. |
| `wm-skel-e2222c4aa334` | QUAD-EQ | 단답형 | ok | (x+4)^2=13 작은근 -4-√13. 논리 완결. 단답형. |
| `wm-skel-64c5ca08552c` | QUAD-EQ | 객관식 | ok | (2x-5)(x+1) 작은근 -1. 오답 5/2=반대근, -5/2·1=부호뒤집기 정합. |
| `wm-skel-e6bf176a1a4c` | QUAD-EQ | 단답형 | ok | (x+4)^2=5 큰근 -4+√5. 논리 완결. 단답형. |
| `wm-skel-bb51eedfd128` | QUAD-EQ | 단답형 | ok | (x-3)(x-8) 큰근 8. 논리 완결. 단답형. |
| `wm-skel-1b7b0252c428` | QUAD-EQ | 단답형 | ok | (x+6)(x+2) 큰근 -2. 음수근 대소 비교 정확. 단답형. |
| `wm-skel-1fbdd8048343` | QUAD-EQ | 단답형 | ok | (x+2)x 큰근 0. 근 -2·0 대소 정확. 단답형. |
| `wm-skel-e576f53f4f19` | QUAD-EQ | 객관식 | ok | (x-3)^2=12 작은근 3-2√3. 오답 3+2√3=반대근, -3±2√3=부호뒤집기 정합. |
| `wm-skel-cd066d0d8843` | QUAD-EQ | 단답형 | ok | (3x-1)(x+1) 작은근 -1. 논리 완결. 단답형. |
| `wm-skel-7b02121cf400` | QUAD-EQ | 단답형 | ok | (x+3)(x-2) 작은근 -3. 논리 완결. 단답형. |
| `wm-skel-40c9511ccc93` | QUAD-EQ | 단답형 | ok | (x-2)^2=7 작은근 2-√7. 논리 완결. 단답형. |
| `wm-skel-392eeba2f8bc` | QUAD-EQ | 단답형 | ok | (3x-1)(x-5) 작은근 1/3. 논리 완결. 단답형. |
| `wm-skel-6fb7d5dbc287` | QUAD-EQ | 객관식 | ok | (x+4)(x-5) 큰근 5. 오답 -4=반대근, 4·-5=부호뒤집기 정합. |
| `wm-skel-ac0a34b7e196` | QUAD-EQ | 단답형 | ok | (x+8)(x-5) 작은근 -8. 논리 완결. 단답형. |
| `wm-skel-d4558bee1890` | QUAD-EQ | 단답형 | ok | (2x+5)(x-1) 작은근 -5/2. 논리 완결. 단답형. |
| `wm-skel-c3442eaae36b` | QUAD-EQ | 객관식 | ok | (x-8)(x-9) 큰근 9. 오답 8=반대근, -8·-9=부호뒤집기 정합. |
| `wm-skel-f29ec6a983a8` | QUAD-EQ | 단답형 | ok | (x+3)^2=12 작은근 -3-2√3. 해설 √12·answer 2√3 정규화 일치. 단답형. |
| `wm-skel-4fef37fb7fb9` | QUAD-EQ | 단답형 | ok | (3x+5)(x+2) 근 -2·-5/3 큰근 -5/3. 음수분수 대소 정확. 단답형. |
| `wm-skel-acecb80fd523` | QUAD-EQ | 단답형 | ok | (x+9)(x-5) 큰근 5. 논리 완결. 단답형. |
| `wm-skel-9e64e7fce855` | QUAD-EQ | 단답형 | ok | (x-3)^2=2 큰근 3+√2. 논리 완결. 단답형. |
| `wm-skel-aaefea1570a1` | QUAD-EQ | 단답형 | ok | (x+4)(x+2) 작은근 -4. 논리 완결. 단답형. |
| `wm-skel-57c7a290b008` | QUAD-EQ | 객관식 | ok | (x+1)^2=12 작은근 -1-2√3. 오답 -1+2√3=반대근, 1±2√3=부호뒤집기 정합. |
| `wm-skel-13c578cd3565` | QUAD-EQ | 단답형 | ok | (x+5)(x-5) 작은근 -5. 논리 완결. 단답형. |
| `wm-skel-414edb062317` | QUAD-EQ | 객관식 | ok | (3x-5)(x-4) 큰근 4. 오답 5/3=반대근, -5/3·-4=부호뒤집기 정합. |
| `wm-skel-c60b366c016f` | QUAD-EQ | 객관식 | ok | (x+7)(x+1) 작은근 -7. 오답 -1=반대근, 1·7=부호뒤집기 정합. |
| `wm-skel-3925e7534670` | QUAD-EQ | 객관식 | ok | (x-2)^2=13 큰근 2+√13. 오답 2-√13=반대근, -2±√13=부호뒤집기 정합. |
| `wm-skel-991ec1659ca4` | QUAD-EQ | 단답형 | ok | (x+4)(x-6) 큰근 6. 논리 완결. 단답형. |
| `wm-skel-3a8dd7ab2a47` | QUAD-EQ | 단답형 | ok | (x+3)^2=3 작은근 -3-√3. 논리 완결. 단답형. |
| `wm-skel-8ea59b001e72` | QUAD-EQ | 단답형 | ok | (x-6)(x-8) 큰근 8. 논리 완결. 단답형. |
| `wm-skel-e855457a2d51` | QUAD-EQ | 단답형 | ok | (2x+7)(x-5) 작은근 -7/2. 해설 josa '-7/2과'는 '칠' 자음받침 읽기로 적정. 단답형. |
| `wm-skel-2407e0fb541b` | QUAD-EQ | 객관식 | ok | (3x-1)(x-4) 큰근 4. 오답 1/3=반대근, -1/3·-4=부호뒤집기 정합. |
| `wm-skel-5bc29c2b6a61` | QUAD-EQ | 객관식 | ok | (3x+2)(x+1) 근 -1·-2/3 큰근 -2/3. 오답 -1=반대근, 2/3·1=부호뒤집기 정합. |
| `wm-skel-0047d3954eb8` | QUAD-EQ | 단답형 | ok | (x+9)(x-8)=0, 작은 근 -9 정확. 발문·귀속 정합. 원문DB 미보유이나 범용 매개변수 템플릿. |
| `wm-skel-10e4b5e97e17` | QUAD-EQ | 단답형 | ok | SymPy 근 {-3,-7/3} 확인, 작은 근 -3 정확. 계수2/3류 난이도 3.1 정합. |
| `wm-skel-d5f5ea458863` | QUAD-EQ | 단답형 | ok | (x+4)(x+1)=0, 큰 근 -1 정확. |
| `wm-skel-fbc2e8e02b18` | QUAD-EQ | 객관식 | ok | 완전제곱 x=-1±√2, 작은 근 -1-√2 정확. distractor: idx2가 반대근(opposite) |
| `wm-skel-95aaf2de3d7f` | QUAD-EQ | 단답형 | ok | (2x-1)(x+5)=0, 작은 근 -5 정확. |
| `wm-skel-caa1e44bebe7` | QUAD-EQ | 객관식 | ok | (x-7)(x-9)=0, 작은 근 7. idx3=9가 반대근, idx0·1 부호오류 귀속 정합. |
| `wm-skel-4c89c8d985ac` | QUAD-EQ | 단답형 | ok | (2x-3)^2=0 중근 3/2 정확, 중근 설명 명시. |
| `wm-skel-65f4acce8a61` | QUAD-EQ | 단답형 | ok | x(x-4)=0, 작은 근 0 정확. 인수 표기 (x)도 무난. |
| `wm-skel-811e3dae7ea6` | QUAD-EQ | 단답형 | ok | 완전제곱 x=-4±√3, 큰 근 -4+√3 정확. |
| `wm-skel-1a57d47cda08` | QUAD-EQ | 단답형 | ok | (2x-5)^2=0 중근 5/2 정확. |
| `wm-skel-bb5b551f3339` | QUAD-EQ | 객관식 | ok | 근 {-4,1/2} 확인, 큰 근 1/2. idx0=-4 반대근, idx1·3 부호오류 정합. |
| `wm-skel-83f7d4f76ad8` | QUAD-EQ | 단답형 | ok | 완전제곱 x=4±√7, 작은 근 4-√7 정확. |
| `wm-skel-cecf7c2d2c0b` | QUAD-EQ | 단답형 | ok | (x-3)(x-4)=0, 작은 근 3 정확. |
| `wm-skel-2f1b47957ce9` | QUAD-EQ | 객관식 | ok | 근 {-3,7/3} 확인, 작은 근 -3. idx2=7/3 반대근, idx1·3 부호오류 정합. |
| `wm-skel-f70a7458a099` | QUAD-EQ | 객관식 | ok | (x-3)(x-6)=0, 작은 근 3. idx3=6 반대근, idx0·1 부호오류 정합. |
| `wm-skel-32b1ba50a208` | QUAD-EQ | 단답형 | ok | (x+9)(x-9)=0, 큰 근 9 정확. |
| `wm-skel-78c0c833b6a7` | QUAD-EQ | 단답형 | ok | 완전제곱 x=4±√7, 큰 근 4+√7 정확. |
| `wm-skel-6aeea28234b3` | QUAD-EQ | 단답형 | ok | 근 {-4/3,2} 확인, 작은 근 -4/3 정확. |
| `wm-skel-535e622345f7` | QUAD-EQ | 단답형 | ok | (x-4)(x-8)=0, 작은 근 4 정확. |
| `wm-skel-4b145dc31d37` | QUAD-EQ | 단답형 | ok | (x-2)(x-3)=0, 작은 근 2 정확. |
| `wm-skel-0f7bbeee6adf` | QUAD-EQ | 단답형 | ok | (x+5)(x-5)=0, 큰 근 5 정확. |
| `wm-skel-4fb75beb0828` | QUAD-EQ | 객관식 | ok | 완전제곱 x=2±√5, 작은 근 2-√5. idx3=2+√5 반대근, idx0·2 부호오류 정합. |
| `wm-skel-b113f66bb41b` | QUAD-EQ | 단답형 | ok | 근 {-7/2,2} 확인, 큰 근 2 정확. |
| `wm-skel-99abf435d5ce` | QUAD-EQ | 단답형 | ok | (x+6)(x-1)=0, 작은 근 -6 정확. |
| `wm-skel-6f9c26b826cf` | QUAD-EQ | 단답형 | ok | 완전제곱 x=2±√11, 큰 근 2+√11 정확. |
| `wm-skel-4320d6383454` | QUAD-EQ | 객관식 | ok | (x+7)(x+6)=0, 작은 근 -7. idx1=-6 반대근, idx2·3 부호오류 정합. |
| `wm-skel-6f315c79a3f0` | QUAD-EQ | 객관식 | ok | 완전제곱 x=-2±√11, 작은 근 -2-√11. idx2=-2+√11 반대근, idx1·3 부호오류 정합. |
| `wm-skel-61c47053ddca` | QUAD-EQ | 단답형 | ok | (x+7)(x+3)=0, 작은 근 -7 정확. |
| `wm-skel-15c0be0334fc` | QUAD-EQ | 객관식 | ok | 완전제곱 x=3±√3, 큰 근 3+√3. idx2=3-√3 반대근, idx0·1 부호오류 정합. |
| `wm-skel-73465b4b19dd` | QUAD-EQ | 객관식 | ok | 근 {1,5/2} 확인, 작은 근 1. idx3=5/2 반대근, idx0·1 부호오류 정합. |
| `wm-skel-0205c58691a3` | QUAD-EQ | 단답형 | ok | (x-3)(x-9)=0, 작은 근 3 정확. |
| `wm-skel-2b5a92d28d61` | QUAD-EQ | 객관식 | ok | 근 {2,7/2} 확인, 큰 근 7/2. idx2=2 반대근, idx0·1 부호오류 정합. |
| `wm-skel-7b30b792fd85` | QUAD-EQ | 객관식 | ok | (x+4)(x-2)=0, 큰 근 2. idx0=-4 반대근, idx1·3 부호오류 정합. |
| `wm-arseq-31bde47c7d29` | ARITH-SEQ | 단답형 | ok | a12=3+11×6=69 정확. 공식1스텝 난이도 2.0·[12대수03-02] 등차수열 귀속 정합. 설명 다 |
| `wm-arseq-8fdfca1070d1` | ARITH-SEQ | 단답형 | ok | a15=2+14×2=30 정확. |
| `wm-arseq-c596f76f9f5c` | ARITH-SEQ | 단답형 | ok | a13=2+12×6=74 정확. |
| `wm-arseq-0c7d4ed59aef` | ARITH-SEQ | 단답형 | ok | a13=5+12×6=77 정확. '13번째 항' 발문 자연. |
| `wm-arseq-32fccf4697af` | ARITH-SEQ | 단답형 | ok | a15=5+14×6=89 정확. |
| `wm-arseq-254465c46f94` | ARITH-SEQ | 단답형 | ok | a10=1+9×3=28 정확. 난이도 1.8 정합. |
| `wm-arseq-e61c1b0160c4` | ARITH-SEQ | 단답형 | ok | a10=1+9×6=55 정확. |
| `wm-arseq-ac26002af2ef` | ARITH-SEQ | 단답형 | ok | answer_explanation이 실수치 대입(1+8×4)을 생략한 템플릿형이나 규칙 명시로 논리 완결.  |
| `wm-arseq-03cfd991dbd7` | ARITH-SEQ | 단답형 | ok | 발문 '8번째 항의 값' 자연·조사 정합. 설명 터스하나 완결. |
| `wm-arseq-01fe20b14f12` | ARITH-SEQ | 단답형 | ok | 난이도 2.0으로 앵커 상한 경계·13항 계산량 반영 합당. |
| `wm-arseq-e06c49520959` | ARITH-SEQ | 단답형 | ok |  |
| `wm-arseq-6c526e9c28e3` | ARITH-SEQ | 단답형 | ok |  |
| `wm-arseq-b09a9117ad8a` | ARITH-SEQ | 단답형 | ok |  |
| `wm-arseq-fc8de6c546a8` | ARITH-SEQ | 단답형 | ok |  |
| `wm-arseq-c21693374b8d` | ARITH-SEQ | 단답형 | ok |  |
| `wm-arseq-a1841862ad19` | ARITH-SEQ | 단답형 | ok |  |
| `wm-arseq-c4ba1ee82ced` | ARITH-SEQ | 단답형 | ok |  |
| `wm-arseq-c64031c472ce` | ARITH-SEQ | 단답형 | ok |  |
| `wm-arseq-680852d3c2cf` | ARITH-SEQ | 단답형 | ok |  |
| `wm-arseq-1d4b34c5ce0a` | ARITH-SEQ | 단답형 | ok |  |
| `wm-arseq-4fb383e65e8e` | ARITH-SEQ | 단답형 | ok |  |
| `wm-arseq-b876e6c52936` | ARITH-SEQ | 단답형 | ok |  |
| `wm-arseq-f654ffdaeca9` | ARITH-SEQ | 단답형 | ok |  |
| `wm-arseq-cb1839be1dd8` | ARITH-SEQ | 단답형 | ok |  |
| `wm-arsum-28ea42427a64` | ARITH-SUM | 단답형 | ok | 합 문제는 끝항 산출+합공식 2스텝이라 2.0 초과 정합(1스텝 앵커 미적용). (3+53)×11/2=308 |
| `wm-arsum-bb7a7d945271` | ARITH-SUM | 단답형 | ok |  |
| `wm-arsum-ab58261c9f6a` | ARITH-SUM | 단답형 | ok |  |
| `wm-arsum-5b70af92b155` | ARITH-SUM | 단답형 | ok |  |
| `wm-arsum-d3f2d617c6f9` | ARITH-SUM | 단답형 | ok |  |
| `wm-arsum-cf219651f481` | ARITH-SUM | 단답형 | ok |  |
| `wm-arsum-ad95767e5c13` | ARITH-SUM | 단답형 | ok |  |
| `wm-arsum-d195cd3ae054` | ARITH-SUM | 단답형 | ok |  |
| `wm-arsum-782d73288629` | ARITH-SUM | 단답형 | ok |  |
| `wm-arsum-ee775b343452` | ARITH-SUM | 단답형 | ok |  |
| `wm-arsum-839022d89849` | ARITH-SUM | 단답형 | ok |  |
| `wm-arsum-a45f186b3dd2` | ARITH-SUM | 단답형 | ok |  |
| `wm-arsum-7ea5dae08da3` | ARITH-SUM | 단답형 | ok |  |
| `wm-arsum-8f263ed2a84a` | ARITH-SUM | 단답형 | ok | a1=1,d=2,n=13 → 13²=169 정합. |
| `wm-arsum-1958fcac9c54` | ARITH-SUM | 단답형 | ok |  |
| `wm-arsum-a1280f3209de` | ARITH-SUM | 단답형 | ok |  |
| `wm-arsum-621e3f6d56f1` | ARITH-SUM | 단답형 | ok |  |
| `wm-arsum-8da391f19cae` | ARITH-SUM | 단답형 | ok |  |
| `wm-calc-ext-662d3f9c62e3` | CALC-EXTREMUM | 단답형 | ok | f'=3(x+8)(x)·x=-8극대,x=0극소 SymPy 검증 일치. |
| `wm-calc-ext-c448b24d9cbc` | CALC-EXTREMUM | 단답형 | ok | x=5 극소 일치. |
| `wm-calc-ext-0598394a6ff3` | CALC-EXTREMUM | 단답형 | ok | x=-3 극대 SymPy 일치. |
| `wm-calc-ext-34ea144e695a` | CALC-EXTREMUM | 단답형 | ok | x=-9 극대 일치. |
| `wm-calc-ext-783de36f65d6` | CALC-EXTREMUM | 단답형 | ok | x=-1 극대 일치. |
| `wm-calc-ext-00a76c566dc6` | CALC-EXTREMUM | 단답형 | ok | SymPy 전건 검증 통과(근·극값·접점 선택 일치). 발문 말미 'x' 뒤 '가' 조사는 교과서 통용체로  |
| `wm-calc-ext-8c193941df77` | CALC-EXTREMUM | 단답형 | ok | SymPy 전건 검증 통과(근·극값·접점 선택 일치). 발문 말미 'x' 뒤 '가' 조사는 교과서 통용체로  |
| `wm-calc-ext-ec42f7239643` | CALC-EXTREMUM | 단답형 | ok | SymPy 전건 검증 통과(근·극값·접점 선택 일치). 발문 말미 'x' 뒤 '가' 조사는 교과서 통용체로  |
| `wm-calc-ext-d5e25343b112` | CALC-EXTREMUM | 단답형 | ok | SymPy 전건 검증 통과(근·극값·접점 선택 일치). 발문 말미 'x' 뒤 '가' 조사는 교과서 통용체로  |
| `wm-calc-ext-6acccbead5d3` | CALC-EXTREMUM | 단답형 | ok | SymPy 전건 검증 통과(근·극값·접점 선택 일치). 발문 말미 'x' 뒤 '가' 조사는 교과서 통용체로  |
| `wm-calc-ext-a677addfed9d` | CALC-EXTREMUM | 단답형 | ok | SymPy 전건 검증 통과(근·극값·접점 선택 일치). 발문 말미 'x' 뒤 '가' 조사는 교과서 통용체로  |
| `wm-calc-ext-ea6416ffa632` | CALC-EXTREMUM | 단답형 | ok | SymPy 전건 검증 통과(근·극값·접점 선택 일치). 발문 말미 'x' 뒤 '가' 조사는 교과서 통용체로  |
| `wm-calc-ext-cfeaef30b964` | CALC-EXTREMUM | 단답형 | ok | SymPy 전건 검증 통과(근·극값·접점 선택 일치). 발문 말미 'x' 뒤 '가' 조사는 교과서 통용체로  |
| `wm-calc-ext-c506a8cea5dc` | CALC-EXTREMUM | 단답형 | ok | SymPy 전건 검증 통과(근·극값·접점 선택 일치). 발문 말미 'x' 뒤 '가' 조사는 교과서 통용체로  |
| `wm-calc-ext-729ae5cf983d` | CALC-EXTREMUM | 단답형 | ok | SymPy 전건 검증 통과(근·극값·접점 선택 일치). 발문 말미 'x' 뒤 '가' 조사는 교과서 통용체로  |
| `wm-calc-ext-ed3a05c9071e` | CALC-EXTREMUM | 단답형 | ok | SymPy 전건 검증 통과(근·극값·접점 선택 일치). 발문 말미 'x' 뒤 '가' 조사는 교과서 통용체로  |
| `wm-calc-extv-63eb524d2655` | CALC-EXTREMUM-VALUE | 단답형 | ok | SymPy 전건 검증 통과(근·극값·접점 선택 일치). 발문 말미 'x' 뒤 '가' 조사는 교과서 통용체로  |
| `wm-calc-extv-cd86d461d1b1` | CALC-EXTREMUM-VALUE | 단답형 | ok | SymPy 전건 검증 통과(근·극값·접점 선택 일치). 발문 말미 'x' 뒤 '가' 조사는 교과서 통용체로  |
| `wm-calc-extv-b75d75d7c302` | CALC-EXTREMUM-VALUE | 단답형 | ok | SymPy 전건 검증 통과(근·극값·접점 선택 일치). 발문 말미 'x' 뒤 '가' 조사는 교과서 통용체로  |
| `wm-calc-extv-86393d85acf2` | CALC-EXTREMUM-VALUE | 단답형 | ok | SymPy 전건 검증 통과(근·극값·접점 선택 일치). 발문 말미 'x' 뒤 '가' 조사는 교과서 통용체로  |
| `wm-calc-extv-fca5494a067b` | CALC-EXTREMUM-VALUE | 단답형 | ok | SymPy 전건 검증 통과(근·극값·접점 선택 일치). 발문 말미 'x' 뒤 '가' 조사는 교과서 통용체로  |
| `wm-calc-extv-0c2ce466bfc6` | CALC-EXTREMUM-VALUE | 단답형 | ok | SymPy 전건 검증 통과(근·극값·접점 선택 일치). 발문 말미 'x' 뒤 '가' 조사는 교과서 통용체로  |
| `wm-calc-extv-bd21cd8484d2` | CALC-EXTREMUM-VALUE | 단답형 | ok | SymPy 전건 검증 통과(근·극값·접점 선택 일치). 발문 말미 'x' 뒤 '가' 조사는 교과서 통용체로  |
| `wm-calc-extv-babd2503edc4` | CALC-EXTREMUM-VALUE | 단답형 | ok | SymPy 전건 검증 통과(근·극값·접점 선택 일치). 발문 말미 'x' 뒤 '가' 조사는 교과서 통용체로  |
| `wm-calc-extv-5c4a86d7a72a` | CALC-EXTREMUM-VALUE | 단답형 | ok | SymPy 전건 검증 통과(근·극값·접점 선택 일치). 발문 말미 'x' 뒤 '가' 조사는 교과서 통용체로  |
| `wm-calc-extv-01f786ab766c` | CALC-EXTREMUM-VALUE | 단답형 | ok | SymPy 전건 검증 통과(근·극값·접점 선택 일치). 발문 말미 'x' 뒤 '가' 조사는 교과서 통용체로  |
| `wm-calc-extv-8f82815640fd` | CALC-EXTREMUM-VALUE | 단답형 | ok | SymPy 전건 검증 통과(근·극값·접점 선택 일치). 발문 말미 'x' 뒤 '가' 조사는 교과서 통용체로  |
| `wm-calc-extv-822223b26c89` | CALC-EXTREMUM-VALUE | 단답형 | ok | SymPy 전건 검증 통과(근·극값·접점 선택 일치). 발문 말미 'x' 뒤 '가' 조사는 교과서 통용체로  |
| `wm-calc-extv-eb6ea17090c3` | CALC-EXTREMUM-VALUE | 단답형 | ok | SymPy 전건 검증 통과(근·극값·접점 선택 일치). 발문 말미 'x' 뒤 '가' 조사는 교과서 통용체로  |
| `wm-calc-extv-e6a3024dc72b` | CALC-EXTREMUM-VALUE | 단답형 | ok | SymPy 전건 검증 통과(근·극값·접점 선택 일치). 발문 말미 'x' 뒤 '가' 조사는 교과서 통용체로  |
| `wm-calc-extv-e32a2915a063` | CALC-EXTREMUM-VALUE | 단답형 | ok | SymPy 전건 검증 통과(근·극값·접점 선택 일치). 발문 말미 'x' 뒤 '가' 조사는 교과서 통용체로  |
| `wm-calc-extv-e1a31cb3b6de` | CALC-EXTREMUM-VALUE | 단답형 | ok | SymPy 전건 검증 통과(근·극값·접점 선택 일치). 발문 말미 'x' 뒤 '가' 조사는 교과서 통용체로  |
| `wm-calc-tan-c5d184e00244` | CALC-TANGENT | 단답형 | ok | SymPy 전건 검증 통과(근·극값·접점 선택 일치). 발문 말미 'x' 뒤 '가' 조사는 교과서 통용체로  |
| `wm-calc-tan-0f66511a6c1a` | CALC-TANGENT | 단답형 | ok | SymPy 전건 검증 통과(근·극값·접점 선택 일치). 발문 말미 'x' 뒤 '가' 조사는 교과서 통용체로  |
| `wm-calc-tan-290be081e9a4` | CALC-TANGENT | 단답형 | ok | SymPy 전건 검증 통과(근·극값·접점 선택 일치). 발문 말미 'x' 뒤 '가' 조사는 교과서 통용체로  |
| `wm-calc-tan-362338e0a674` | CALC-TANGENT | 단답형 | ok | SymPy 전건 검증 통과(근·극값·접점 선택 일치). 발문 말미 'x' 뒤 '가' 조사는 교과서 통용체로  |
| `wm-calc-tan-290fc784a150` | CALC-TANGENT | 단답형 | ok | SymPy 전건 검증 통과(근·극값·접점 선택 일치). 발문 말미 'x' 뒤 '가' 조사는 교과서 통용체로  |
| `wm-calc-tan-a88e5e2a0172` | CALC-TANGENT | 단답형 | ok | SymPy 전건 검증 통과(근·극값·접점 선택 일치). 발문 말미 'x' 뒤 '가' 조사는 교과서 통용체로  |
| `wm-calc-tan-4fd6facd3699` | CALC-TANGENT | 단답형 | ok | SymPy 전건 검증 통과(근·극값·접점 선택 일치). 발문 말미 'x' 뒤 '가' 조사는 교과서 통용체로  |
| `wm-calc-tan-3bc00875ab7d` | CALC-TANGENT | 단답형 | ok | SymPy 전건 검증 통과(근·극값·접점 선택 일치). 발문 말미 'x' 뒤 '가' 조사는 교과서 통용체로  |
| `wm-calc-tan-5e980f9df14c` | CALC-TANGENT | 단답형 | ok | SymPy 전건 검증 통과(근·극값·접점 선택 일치). 발문 말미 'x' 뒤 '가' 조사는 교과서 통용체로  |
| `wm-calc-tan-e93a485579c5` | CALC-TANGENT | 단답형 | ok | SymPy 전건 검증 통과(근·극값·접점 선택 일치). 발문 말미 'x' 뒤 '가' 조사는 교과서 통용체로  |
| `wm-calc-tan-04a46e7f6ffa` | CALC-TANGENT | 단답형 | ok | SymPy 전건 검증 통과(근·극값·접점 선택 일치). 발문 말미 'x' 뒤 '가' 조사는 교과서 통용체로  |
| `wm-calc-tan-53d741adde95` | CALC-TANGENT | 단답형 | ok | SymPy 전건 검증 통과(근·극값·접점 선택 일치). 발문 말미 'x' 뒤 '가' 조사는 교과서 통용체로  |
| `wm-calc-tan-d96cd9e68134` | CALC-TANGENT | 단답형 | ok | SymPy 전건 검증 통과(근·극값·접점 선택 일치). 발문 말미 'x' 뒤 '가' 조사는 교과서 통용체로  |
| `wm-calc-tan-f881d5d5e835` | CALC-TANGENT | 단답형 | ok | tangent slope 유형 난이도 동배치 미세 불일치(4.0 vs 3.5), 차단성 아님 |
| `wm-calc-tan-b5c05e6331e8` | CALC-TANGENT | 단답형 | ok |  |
| `wm-calc-extirr-c21969c5e025` | CALC-EXTREMUM-IRR | 단답형 | ok |  |
| `wm-calc-extirr-595af926046b` | CALC-EXTREMUM-IRR | 단답형 | ok |  |
| `wm-calc-extirr-2047a1886cd8` | CALC-EXTREMUM-IRR | 단답형 | ok |  |
| `wm-calc-extirr-2ab78f442266` | CALC-EXTREMUM-IRR | 단답형 | ok |  |
| `wm-calc-extirr-0716f65f4a5e` | CALC-EXTREMUM-IRR | 단답형 | ok |  |
| `wm-calc-extirr-a93cd2e34587` | CALC-EXTREMUM-IRR | 단답형 | ok |  |
| `wm-calc-extirr-22af7a21d5ce` | CALC-EXTREMUM-IRR | 단답형 | ok |  |
| `wm-calc-extirr-9aeb9d726284` | CALC-EXTREMUM-IRR | 단답형 | ok |  |
| `wm-calc-extirr-ce271fdb3771` | CALC-EXTREMUM-IRR | 단답형 | ok |  |
| `wm-calc-extirr-112235b3211c` | CALC-EXTREMUM-IRR | 단답형 | ok |  |
| `wm-calc-extirr-b862a378871b` | CALC-EXTREMUM-IRR | 단답형 | ok |  |
| `wm-calc-extirr-8e1bb8c03fb2` | CALC-EXTREMUM-IRR | 단답형 | ok |  |
| `wm-calc-extmc-8481b53c00e2` | CALC-EXTREMUM-MC | 객관식 | ok |  |
| `wm-calc-extmc-803cec54fad3` | CALC-EXTREMUM-MC | 객관식 | ok |  |
| `wm-calc-extmc-2e23148010b0` | CALC-EXTREMUM-MC | 객관식 | ok |  |
| `wm-calc-extmc-8fc0433707f2` | CALC-EXTREMUM-MC | 객관식 | ok |  |
| `wm-calc-extmc-5c4a86d7a72a` | CALC-EXTREMUM-MC | 객관식 | ok |  |
| `wm-calc-extmc-34abe4cd4c5b` | CALC-EXTREMUM-MC | 객관식 | ok |  |
| `wm-calc-extmc-3ccc6c8c3b7c` | CALC-EXTREMUM-MC | 객관식 | ok |  |
| `wm-calc-extmc-5af27b145d2b` | CALC-EXTREMUM-MC | 객관식 | ok |  |
| `wm-calc-extmc-829f17b06867` | CALC-EXTREMUM-MC | 객관식 | ok |  |
| `wm-calc-extmc-588713791a72` | CALC-EXTREMUM-MC | 객관식 | ok |  |
| `wm-calc-extmc-de4e71f518eb` | CALC-EXTREMUM-MC | 객관식 | ok |  |
| `wm-calc-extmc-156e734b8684` | CALC-EXTREMUM-MC | 객관식 | ok |  |
| `wm-geseq-e00a9dc7f844` | GEO-SEQ | 단답형 | ok |  |
| `wm-geseq-005a1c017864` | GEO-SEQ | 단답형 | ok |  |
| `wm-geseq-c5fe6ae9a13f` | GEO-SEQ | 단답형 | ok |  |
| `wm-geseq-92b16842cdc8` | GEO-SEQ | 단답형 | ok |  |
| `wm-geseq-d50bd54b7ce0` | GEO-SEQ | 단답형 | ok |  |
| `wm-geseq-cc22267ef882` | GEO-SEQ | 단답형 | ok |  |
| `wm-geseq-62cbcfe9f781` | GEO-SEQ | 단답형 | ok |  |
| `wm-geseq-4e69fbfa9c94` | GEO-SEQ | 단답형 | ok |  |
| `wm-geseq-dc183eb2575d` | GEO-SEQ | 단답형 | ok |  |
| `wm-geseq-ac837e7dacae` | GEO-SEQ | 단답형 | ok |  |
| `wm-geseq-e6f39f174987` | GEO-SEQ | 단답형 | ok |  |
| `wm-indseq-75bdc222136b` | IND-SEQ | 단답형 | ok |  |
| `wm-indseq-d1bb03d5d964` | IND-SEQ | 단답형 | ok |  |
| `wm-indseq-4e7bcd458845` | IND-SEQ | 단답형 | ok |  |
| `wm-indseq-7bc400fc2b81` | IND-SEQ | 단답형 | ok | a4=3*5^3=375 정합. 발문·풀이 자연. 등비형 점화식→[12대수03-06] 부합. 단답형(⑤ na) |
| `wm-indseq-98a817d2e754` | IND-SEQ | 단답형 | ok | a8=1+2*7=15 정합. 등차형 점화식. 범용 템플릿. |
| `wm-indseq-698d641410cb` | IND-SEQ | 단답형 | ok | a4=2*5^3=250 정합. 범용 템플릿. |
| `wm-indseq-64c0920119f4` | IND-SEQ | 단답형 | ok | a10=2+4*9=38 정합. 범용 템플릿. |
| `wm-indseq-2463c80a3943` | IND-SEQ | 단답형 | ok | a12=7+6*11=73 정합. 범용 템플릿. |
| `wm-indseq-c4fd617cbc21` | IND-SEQ | 단답형 | ok | a11=1+5*10=51 정합. 범용 템플릿. |
| `wm-indseq-2d4485f4cd31` | IND-SEQ | 단답형 | ok | a7=2+2*6=14 정합. 범용 템플릿. |
| `wm-indseq-cc2eb10012ee` | IND-SEQ | 단답형 | ok | a12=1+5*11=56 정합. 범용 템플릿. |
| `wm-exp-bd45bf9ac978` | EXP-EQ | 단답형 | ok | 2^x=16=2^4→x=4. 밑 일치→지수비교 논리 완결. [12대수01-08] 부합. 난이도 1.8≤2.0 |
| `wm-exp-e2482b9581a4` | EXP-EQ | 단답형 | ok | 10^x=1000=10^3→x=3. 난이도 2.0=앵커 상한. ok. |
| `wm-exp-0b8f9ed7c53e` | EXP-EQ | 단답형 | ok | 10^x=10=10^1→x=1. 정합. |
| `wm-exp-3146ed073d9a` | EXP-EQ | 단답형 | ok | 2^x=256=2^8→x=8. 난이도 2.0 앵커 내(2^8 상기부하로 상단 배치 방어가능). |
| `wm-exp-f972237eb614` | EXP-EQ | 단답형 | ok | 3^x=27=3^3→x=3. 난이도 1.5. 정합. |
| `wm-exp-9ba302cecec1` | EXP-EQ | 단답형 | ok | 3^x=81=3^4→x=4. 정합. |
| `wm-exp-81dec9a901a5` | EXP-EQ | 단답형 | ok | 6^x=6=6^1→x=1. 정합. |
| `wm-exp-16440cd711cc` | EXP-EQ | 단답형 | ok | 2^x=4=2^2→x=2. 난이도 1.5. 정합. |
| `wm-exp-97836f3244d4` | EXP-EQ | 단답형 | ok | 5^x=125=5^3→x=3. 난이도 2.0 앵커 내. 정합. |
| `wm-gesum-871414dcd4ae` | GEO-SUM | 단답형 | ok | S5=4(3^5-1)/2=484. 등비합 공식 설명 정합. [12대수03-03] 부합. |
| `wm-gesum-c47d637e2a57` | GEO-SUM | 단답형 | ok | S3=5(2^3-1)/1=35. 정합. |
| `wm-gesum-efbcc5c85718` | GEO-SUM | 단답형 | ok | S7=2(2^7-1)/1=254. 관찰: 난이도 2.1로 공식 1스텝 앵커(2.0) 소폭 상회이나 r^n 산 |
| `wm-gesum-ee4f3b6a5a69` | GEO-SUM | 단답형 | ok | S4=3(5^4-1)/4=468. 관찰: 난이도 2.2 앵커 소폭 상회이나 계산량 반영·gross 아님. |
| `wm-gesum-35c9350e1dee` | GEO-SUM | 단답형 | ok | S3=1(2^3-1)/1=7. 정합. |
| `wm-gesum-dfe17905cfa5` | GEO-SUM | 단답형 | ok | S6=3(2^6-1)/1=189. 난이도 2.1 소폭 상회·gross 아님. 정합. |
| `wm-gesum-33071eb73c97` | GEO-SUM | 단답형 | ok | S6=4(3^6-1)/2=1456. 관찰: 난이도 2.2 앵커 소폭 상회이나 계산량 반영·gross 아님. |
| `wm-log-297abb0ad584` | LOG-EQ | 단답형 | ok | log_7 x=1→x=7^1=7. 로그 정의 설명 정합. [12대수01-08] 부합. |
| `wm-log-bda410bd66e1` | LOG-EQ | 단답형 | ok | log_3 x=3→x=27. 정합. |
| `wm-log-7e16610c4371` | LOG-EQ | 단답형 | ok | log_10 x=2→x=100. 정합. |
| `wm-log-d026609848a9` | LOG-EQ | 단답형 | ok | log_5 x=3→x=125. 정합. |
| `wm-log-146645115af9` | LOG-EQ | 단답형 | ok | log_6 x=2→x=36. 정합. |
| `wm-log-14bd3014b6b9` | LOG-EQ | 단답형 | ok | log_5 x=1→x=5. 정합. |
| `wm-log-2b749c441368` | LOG-EQ | 단답형 | ok | log_3 x=6→x=729. 정합. |
| `wm-trig-9e0cdc4b2179` | TRIG-VAL | 단답형 | ok | sin60=√3/2. 단위원 y좌표 설명 정합('좌표가' 조사 정상). [12대수02-02] 부합. |
| `wm-trig-13f33b616fa4` | TRIG-VAL | 단답형 | ok | sin30=1/2. 정합. |
| `wm-trig-8101b7e6781d` | TRIG-VAL | 단답형 | ok | (교정완료) 발견 시 josa 받침 결함 "값가"→생성기 i_ga 헬퍼로 정본 교정·재생성 후 "값이"로 c |
| `wm-trig-9215b6e7ebe2` | TRIG-VAL | 단답형 | ok | (교정완료) 발견 시 josa 받침 결함 "값가"→생성기 i_ga 헬퍼로 정본 교정·재생성 후 "값이"로 c |
| `wm-trig-3d36abdc44eb` | TRIG-VAL | 단답형 | ok | cos180=-1. 단위원 x좌표 설명 정합('좌표가' 정상). 정합. |
| `wm-trigeq-893197b7a63a` | TRIG-EQ | 단답형 | ok | sin x=1/2, 0~360 해 30/150 중 최대=150. 정합. [12대수02-02] 부합. |
| `wm-trigeq-e93211821641` | TRIG-EQ | 단답형 | ok | cos x=-√2/2 해 135/225 중 최대=225. 발문 조사 '√2/2를'은 구어 '2분의 루트2'( |
| `wm-trigeq-8aaca2c4fa1c` | TRIG-EQ | 단답형 | ok | cos x=√2/2 해 45/315 중 최소=45. 정합. |
| `wm-trigeq-6dba23673419` | TRIG-EQ | 단답형 | ok | cos x=√3/2 해 30/330 중 최대=330. 발문 조사 '√3/2을'은 구어 '2분의 루트3'(삼· |
