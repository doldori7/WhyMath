# 오개념 Crosswalk 후보 매핑 — 검수용 초안 (DRAFT)

> ⚠️ **상태: 사람 검수 전 초안 · 라이브 테이블 미적재.** 이 문서는 kebab-id 전종(v0.1=30종, 현
> 카탈로그 34종·수는 `CATALOG_BY_ID` 정본) → M-id 후보 매핑 *제안*이다. **승인 전까지
> `misconception_crosslink` 테이블에 적재하지 않는다**(틀린 매핑 = 오도된 학부모/학생 리포트·
> 의사결정 우선순위 #1·#3). 마크다운이라 로더(`crosslink_loader.py`·JSON 입력)가 *직접 읽을 수
> 없는* 형태로 둔 것은 의도된 안전장치다. 검수 후 승인분만 별도 JSON으로 옮겨 적재한다.
>
> **작성**: 2026-06-30 · **계층**: L1 · **상위**: `math_dsl_remediation_design.md` §1·`misconception_crosslink_v1`(설계 문서)
> **산출 근거**: kebab 카탈로그(`l4/misconception/catalog.py`·현 34종) × M-id 코퍼스
> (`data/corpus/misconceptions_v1/misconceptions.json`·현 843종) 내용 일치 분석.

---

## 0. 검수 전 반드시 알 것

1. **코퍼스 자체가 미검수** — M-id 코퍼스 레코드는 `provenance_note: "AI생성-검수필요"` 상태다.
   crosswalk 검수와 *별개로* 매칭된 M-id 원문 정합을 병행 확인해야 한다(이중 검수).
2. **자동 채택 금지** — 아래 confidence·근거는 *검수 보조*다. 직접매핑 승격은 사람 판단으로만.
   confidence < 0.6(부분/개념겹침)은 "인접 오개념"이라 **직접매핑으로 승격 금지**.
3. **코퍼스 범위(정직)** — school_level 분포: 고등 66.4%(557) · 중등 19.0%(159) · 초등 14.7%(123).
   kebab(고등 대수·미적분·삼각·벡터 중심)과 **실질 겹침 양호** → 전종 후보 매칭(후보 없음 0).

## 1. 매핑에 쓴 신호

- **canonical_statement / student_wrong_thinking 의미 일치**(주신호 — 내용 동일/유사).
- domain·subunit 주제 정합·standard_code/concept_src_id 인접(보조).

### 1.1 후보 재생성 도구 (자동)
본 초안은 `l1/misconception/crosslink_candidates.py`(`propose_crosslink_candidates`)로 *재생성
가능*하다 — kebab `catalog_text` × M-id(`canonical_statement`+`student_wrong_thinking`)를 임베딩
코사인으로 비교해 kebab별 상위 후보를 제안한다. **신호 범위(정직)**: kebab 카탈로그엔
`standard_code`·`error_type`가 *없어* 그 두 신호는 적용 불가 → **주신호 = 임베딩 코사인**. domain은
체계가 달라 점수 미반영(rationale 메모만).
- 실행(실모델·ops): `python -m whymath_backend.l1.misconception.crosslink_candidates --out <후보.json>`
  (provider는 Settings·로컬 bge-m3 기본). 출력 top key는 `"candidates"`라 로더(`"crosslinks"`)가
  *직접 못 읽는* 검수 artifact다(자동 적재 차단).
- **자동 채택 금지**: 도구 출력도 *후보*다 — 본 표처럼 사람 검수 후 승인분만 적재한다.

## 2. 후보 매핑 (kebab → M-id) — 검수 대상

D=직접매핑 · P=부분매핑 · O=개념겹침. conf=보수적 신뢰도. 최상위 + (대안 후보).

| kebab_id | 최상위 M-id | link | conf | 근거 / 대안 |
|---|---|---|---|---|
| distribution-over-power | M0019 | D | 0.95 | (a+b)²=a²+b² 중간항 누락 일치 (+M0572 D, M0649 P) |
| sign-flip-in-inequality | M0564 | D | 0.95 | 음수 곱/나눗 부등호 그대로 (+M0028 D, M0778 D) |
| division-by-zero | M0003 | D | 0.85 | 0 나눗셈 가능성 오해 (+M0556 D 양변0, M0146 P 유리함수) |
| square-root-positivity | M0550 | D | 0.95 | √(a²)=a 단정(실제 \|a\|) (+M0647 D, M0109 P) |
| exponent-zero | M0105 | D | 0.92 | a⁰=0 정확 일치 (**직접 후보 유일·얇음**) |
| fraction-cancellation | M0118 | D | 0.80 | 덧셈식 약분 — (a+b)/a 의도 원문 확인 권장 (M0503 약함 0.45) |
| log-distribution | M0049 | D | 0.97 | log(a+b)=log a+log b 완전 일치 (+M0650) |
| discriminant-negative-no-real-root | M0610 | D | 0.95 | D<0 해없음 단정(허근) (+M0832, M0124) |
| root-loss-by-dividing | M0573 | D | 0.95 | ax²=bx 양변 x 나눠 x=0 근 손실 일치 |
| angle-sum-non-triangle | M0493 | D | 0.85 | 모양 다르면 내각합 달라짐 (+M0580 외각, M0051 약) |
| similarity-vs-congruence | M0519 | D | 0.90 | 닮음을 합동으로 (+M0588 조건 혼동) |
| area-perimeter-confusion | M0529 | D | 0.95 | 둘레·넓이 비례 오해 (+M0782, M0052) |
| circle-radius-squared | M0630 / M0848 | D | 0.93 | x²+y²=r² 반지름 r vs r² (+M0732 구) |
| gambler-fallacy | M0688 | D | 0.98 | 앞면 5번→다음 뒷면 차례 완전 일치 (+M0093, M0794) |
| prosecutor-fallacy | M0691 | D | 0.95 | P(A\|B)=P(B\|A) 완전 일치 (+M0091) |
| mean-vs-median | M0419 | D | 0.90 | 중앙값=평균 (+M0095, M0595 P) |
| mutually-exclusive-implies-independent | M0692 | D | 0.95 | 배반이면 독립 오해 (+M0391, M0090) |
| invertibility-without-1-1 | M0144 | D | 0.92 | 일대일 아닌데 역함수 존재 (+M0644, M0859) |
| composite-function-commutes | M0643 | D | 0.95 | f∘g=g∘f 같다고 봄 (+M0858, M0038 P) |
| translation-sign-flip | M0411 | D | 0.90 | 평행이동 부호 반전 (+M0850, M0632) |
| chain-rule-inner-derivative-omitted | M0370 | D | 0.90 | sin(2x) 연쇄법칙 내부도함수 누락 (+M0710, M0077) |
| product-rule-naive | M0075 | D | 0.97 | (fg)′=f′g′ 완전 일치 (+M0672, M0424) |
| limit-equals-function-value | M0665 | D | 0.95 | 극한=함숫값 단정 (+M0071 P 0.55) |
| continuity-implies-differentiability | M0670 | D | 0.97 | 연속이면 미분가능 단정 (+M0176, M0345) |
| critical-point-implies-extremum | M0080 | D | 0.95 | f′=0이면 무조건 극값 (+M0675, M0349 P) |
| geometric-series-always-converges | M0209 | D | 0.92 | \|r\|≥1인데 합 존재 (+M0705, M0703) |
| term-to-zero-implies-convergence | M0704 | D | 0.95 | 항→0이면 수렴 단정(조화급수 반례) (+M0331) |
| sine-distributes-over-sum | M0707 | D | 0.97 | sin(a+b)=sin a+sin b (**직접 후보 유일·얇음**) |
| period-of-scaled-sine | M0152 | **O** | **0.45** | "y=sin(2x) 주기=2π" 직접 진술 **부재** → **신규 M-id 추가 후보**(검수 시 결정) |
| dot-product-is-vector | M0735 | D | 0.95 | 내적 결과를 벡터로(실제 스칼라) (+M0262 P) |
| opposite-root-selected | **M0862** | **D** | **0.90** | v0.3(S2-p) — **신규 저작** M0862(발문의 큰/작은 근 지시 무시를 직접 서술·HK06·[10공수1-02-02]). 최근접 대안 M0831 O 0.40("x²=4에서 x=2만"). 검수 후 승인·적재 |
| factor-sign-flip | **M0863** | **D** | **0.90** | v0.3(S2-p) — **신규 저작** M0863((x−a)=0을 x=−a로 읽는 부호 반전을 직접 서술·HK06·[10공수1-02-02]). 최근접 대안 M0848 O 0.45(원 중심 부호 반전·주제 상이). 검수 후 승인·적재 |

## 3. 요약 / 검수 우선순위

- 32종(v0.3) 전부 ≥1 후보. 직접매핑 후보 58개(v0.3 S2-p 신규 저작 2건 포함). 최상위 평균 conf
  **0.915**(v0.1 30종 기준).
- **우선 검수(얇거나 약함)**: `period-of-scaled-sine`(직접 부재·신규 M-id 후보) · `exponent-zero`(M0105
  유일) · `sine-distributes-over-sum`(M0707 유일) · `fraction-cancellation`(M0118 원문 확인) ·
  **v0.3 S2-p 2종**(`opposite-root-selected`→M0862·`factor-sign-flip`→M0863 — 신규 저작 직접매핑
  0.90·원문 정합 검수 대상).
- conf 0.4~0.6 대안은 "인접 오개념"으로만 — 직접매핑 승격 금지.

## 4. 승인 후 적재 절차 (검수자 → 후속 슬라이스)

1. 검수자가 본 표의 각 행을 승인/수정/반려(직접매핑만 채택 권장·부분/개념겹침은 신중).
2. 승인분을 crosswalk Collection JSON으로 변환:
   `{"crosslinks": [{"kebab_id": "...", "mis_id": "...", "link_type": "직접매핑", "confidence": 0.95, "method": "manual", "note": "검수자/근거"}, ...]}`
3. `python -m whymath_backend.l1.misconception.crosslink_loader`(또는 `load_crosslinks`)로 멱등 적재.
4. read-time 해석은 `crosslink_resolve.py`(이미 구현)로 자동 — 학생 데이터 rekey 불필요.

> 게이트 공존 배선(learning_scene/wh1_loop/evidence_store에 M-id 분기)은 *적재·검수 이후* 별
> 슬라이스에서 shadow→canary로 노출(노출 전 측정).

---

## 참고
- 검수 결정 패키지(dossier): `docs/data/misconception_crosslink_review_dossier.md` — coverage·근거
  조인·81행 결정 체크리스트 통합(게이트 `G-crosswalk-approval` 검수용·read-only 준비물).
- 골격: `schema/misconception_crosslink.py`·`db/models/misconception_crosslink.py`·
  `l1/misconception/crosslink_loader.py`·`crosslink_resolve.py`·alembic `e2f3a4b5c6d7`(PR #347).
- 원천: `l4/misconception/catalog.py`(kebab·현 34)·`data/corpus/misconceptions_v1/misconceptions.json`(M-id·현 843).
- 원칙: `CLAUDE.md`(우선순위 #1 학생 안전·#3 교수학 정확성)·`math_dsl_remediation_design.md` §1.
- 변경 이력: v0.1 초안 (2026-06-30 — 후보 제안·검수 전·미적재) · v0.2 (2026-07-06 — S2-p kebab 2종
  `opposite-root-selected`·`factor-sign-flip` 후보 행 추가: 둘 다 직접 후보 부재·최근접 개념겹침만·
  신규 M-id 저작 후보, period-of-scaled-sine 선례 패턴) · v0.3 (2026-07-06 — S2-p 후속: 두 kebab의
  직접 대응 M-id를 신규 저작(M0862·M0863)해 `misconceptions_v1`에 추가(839→841). 검수 큐에
  직접매핑 행(conf 0.90) 추가·기존 개념겹침 행은 최근접 대안으로 유지·전행 pending(미승인)).
  · **v0.4 (2026-07-09 — 첫 승인분 적재)**: Kiki가 2026-07-08 직접 승인한 극값 오개념 2건
  (`extremum-max-min-confused`→M0864·`extremum-value-vs-point-confused`→M0865·직접매핑·conf 0.9)을
  promote 산출해 `data/corpus/misconception_crosslinks_v1/crosslinks.json`으로 커밋(첫 라이브 매핑).
  검수 큐 템플릿은 전행 pending 무변경(봉인 유지·AI 자기승인 아님). 나머지 79행 여전히 검수 대기.
