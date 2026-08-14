# AI 콘텐츠 생성 모듈 — 외부 EOS 틀 **3차 재점검(R3)** (2026-08-11)

> **범위**: 1차(2026-07-30)·2차(2026-08-03)와 **동일한 외부 참고 문서**(『14. AI 콘텐츠 생성』 —
> 기능 58 개념 설명 자동 생성 · 59 예제 자동 생성 · 60 스토리형 문제 생성 · 61 실생활 적용 문제
> 생성 **+ 확장 후보 62 힌트 · 63 풀이·해설 · 64 변형 문제 · 65 멀티모달 · 66 교수전략 기반 ·
> 67 수준별 변환 · 68 오개념 교정** — **WhyMath 전용이 아닌 일반적인 EOS 틀**, Kiki 제공 docx)를
> **2차 이후 8일간의 코드베이스 변화**와 다시 대조한 기록. 같은 외부 틀 대조 시리즈의 자매편이며,
> `solution_module_gap_review_r3.md`·`operations_module_gap_review_r3.md`(둘 다 2026-08-11)가
> 확립한 **R3 관례**(원본 비수정 + 별도 파일 + 델타 재점검)를 그대로 따른다.
>
> **성격**: 처음부터의 재대조가 **아니다**. 기능 58~68 판정과 §2 의도적 미채택 9건은 1·2차에
> 보존돼 있고 **전건 승계·재판정 0**이다. R3의 일은 문서를 다시 읽는 것이 아니라
> **1·2차가 등재한 설계 5건이 전부 착지한 뒤의 지형을 읽는 것**이다.
>
> **실측 기준**: HEAD `d088ae77` (2026-08-11). 이 문서의 모든 숫자는 재현 명령을 부록 B에 병기한다.
>
> **결론 4줄**:
> 1. **1·2차가 등재한 설계는 전부 착지했고, 착지 품질은 좋다.** `S3-26`(404 체인)·`OPS-16`(L3
>    프롬프트 감사)·`PED-07`·`CUR-02`·`S4-14` 전부 done이며, 앞의 둘은 **서빙 배선·CI 게이트까지
>    실측 확인**했다. 판정 뒤집기 **0**.
> 2. **최대 갭은 이제 "안 만든 기능"이 아니라 "만들면서 생긴 비대칭"이다.** `PB-03`이 검수를
>    fail-closed 노출 게이트로 세워 L6 7모드·기본 CAT·blueprint에 배선했는데, **`S3-26`이 만든
>    두 번째 노출 경로(`/study`)만 그 게이트를 비껴간다** — 커밋된 산출물에 **61 중 5건**이
>    이미 들어 있다 → **F1/D7**.
> 3. **두 번째 갭은 "약속의 소멸"이다.** `S3-26` notes가 "감사 축은 ARCH-21이 흡수 예정"이라
>    적었고 `ARCH-21`은 done인데, 개념 콘텐츠 축은 **9축에도 `_NOT_MEASURED_AXES`에도 없다** —
>    측정도 미측정 선언도 없는 무추적 구멍 → **F2/D8**.
> 4. **세 번째 갭은 그 둘의 상위 원인이다.** 1차 §4가 잔여 트리거 6종에 발화 조건을 적어 뒀으나
>    **조건 충족을 검사하는 주체가 0**이라, 이번에 수기로 대조하니 **3건이 이미 발화 상태**로
>    방치돼 있었다(트리거 ②·⑥ + `S3-27`의 429 조건부 제외) → **F3/D9·D10**.
>
> **등재**: 신규 태스크 4건 — `CONT-01`·`CONT-02`·`CONT-03`·`CONT-04`. 판정 뒤집기 0, 정정 1건.

관련 정본: `ai_content_generation_gap_review.md`(1차 — 58~68 전 판정·의도적 미채택 9건·설계 D1~D5·
§4 트리거 6종의 **원본**) · `ai_content_generation_gap_review_2.md`(2차 — G1/G2·`PED-07`) ·
`03_content_generation.md`·`03c_content_strategy_cache.md`·`04d_adaptive_pedagogy_engine.md`(교수법-중립
DSL 정본 — §0 논거 원본) · `problem_bank_gap_review_r2.md`(노출 4단 — `PB-03`의 모체) ·
`docs/standards/superhuman_verification_standard.md`(검증 권위 서열) · `MEMORY.md` 결정 로그(2026-08-11).

---

## §0. 재점검 사유 — 왜 3차를 새로 쓰는가

### ① 동일 문서 3차 제출임을 확정한다 (추론 아님)

제출된 `.docx`의 기능 번호(58~61)·제목·「설명 수준 5단」·「예제 종류 6종」·「AI 콘텐츠 생성
아키텍처」·「WhyMath 관점의 확장 제안 62~68」·「WhyMath의 차별화 방향」 절 구조가 1·2차 대조
대상과 **동일**하다. 1차가 58~68 전량을, 2차가 그 판정의 재확인과 PED 계보를 다뤘다 —
**문서 쪽에는 새 표면이 남아 있지 않다.**

따라서 R3의 일은 **코드 쪽 8일치 델타**다. 그 델타가 내놓은 것이 §2다.

### ② 원본 2편을 in-place 수정하지 않는 이유

`problem_bank_gap_review_r2.md`·`gamification_module_gap_review_r2.md`·`solution_module_gap_review_r3.md`가
확립한 규약을 따른다 — **원본 비수정 + 별도 파일**. 근거:

- 원본 2편은 **완료 태스크 `S3-26`·`S3-27`·`OPS-16`·`PED-07`의 `notes`가 가리키는 정본 참조
  대상**이다. 완료된 태스크의 판정 근거를 소급 변조하면 "왜 그렇게 결정했는가"의 기록이 사라진다.
- **판정 뒤집기가 0**이라 덮어쓸 내용 자체가 없다.
- 원본의 stale 지점은 §5 정정에 **기록**한다(수정이 아니라 델타).

원본 2편에는 이 문서로 오는 **포인터 1줄**만 추가했다.

### ③ 승계 선언 — 재판정하지 않는 것

- **기능 58~68 판정 전건 승계.** 특히 **60(스토리형)·61(실생활)의 미채택을 재론하지 않는다** —
  게임화·중독성 설계 금지, 타깃 페르소나 밖(`Persona` 5종 전부 고2·고3·N수), 저작권 레일,
  그리고 `S3-15`의 3라운드 Wilson FAIL 실증이 전부 유효하다.
- **의도적 미채택 9건**(1차 §2) — 전건 승계. 재론 0.
- **설계 D1 기각**(맥락·스토리형 문항 생성) — 유효. **새 LLM 생성 경로를 열지 않는다.**
- **D2~D5** — 전부 착지했거나 승계(§1).

R3가 만드는 것은 *새 기능*이 아니라 **착지분이 남긴 이음매를 잇는 태스크**뿐이다.

---

## §1. 1·2차 설계의 착지 검증 — 델타표

1·2차가 등재한 설계 5건이 **전부 done**이 됐다. 이 저장소는 "선언≠배선" 사고가 반복된 곳이므로
**파일 존재가 아니라 서빙 배선·CI 배선·실제 값**으로 확인했다.

| 설계 | 태스크 | 2차 시점 | R3 실측 | 판정 |
|---|---|---|---|---|
| **D2** 개념 공급 무결성 | `S3-26` | todo(404 체인 불변) | **done · 진짜 닫힘**(아래 ①) | ✅ |
| **D3** 문항 유형 필드+백필 | `S3-27` | done | `problem_type_codes` **2,218/2,647(83.8%)** — 미태깅 429는 전량 `rephrased_v0` | ✅ / ⚠️ **F3** |
| **D4** L3 프롬프트 정본화·감사 | `OPS-16` | todo | **done · CI 게이트까지 배선**(아래 ②) | ✅ |
| **D5** QA 오케스트레이터 | `ARCH-21` | done(7축) | **9축**(`banned_words_pii`·`defect_report_intake` 추가) — 단 개념 축 부재 | ✅ / ⚠️ **F2** |
| **D6**(2차) 슬롯 도달성 | `PED-07` | 신규 등재 | **done** — `ops/pedagogy_content_slot_reach_report.py` 실재 | ✅ |
| **G1** 학생 도달 상한 4 | `CUR-02` | todo | **done — 그러나 관측만 착지**. `data/corpus/units_v1/`는 아직 **`quadratic_maxmin.unit.yaml` 1개 파일** | ⚠️ 승계 |

### ① `S3-26` — 404 체인은 진짜로 해소됐고, 빌드타임 필터도 견고하다

2차까지 두 번 재확인된 404 체인(`dsl.py` `assessment=None` → `ProblemBasedAdapter.can_render`
항상 False → `api/study.py` HTTP 404)이 **실제로 끊겼다**:

- `l4/content_supply.py:52` `from whymath_backend.l3.render.assessment_bank import attach_assessment`
- 같은 파일 `:240`·`:248`에서 **실호출** — 캐시 히트 경로와 신규 조립 경로 양쪽 모두.
- 빌드타임 후보 필터(`harness/concept_assessment_index.py`)는 3겹이다:
  ①저작권 위생(`:232` — `source_type=자체생성` + `license=WHYMATH_GENERATED`만, **타 출처 본문
  상속 금지**) ②`corpus_reverify._reverify_one`이 `pass`를 낸 문항만 ③`answer_map`·`conditions`
  비어 있지 않음(빈 검증의 통과 위장 금지).
- **미커버 376건을 code 목록으로 명시 기록** — 커버된 것만 세는 침묵 통과를 구조적으로 차단.
- 리포트가 **주입 전/후를 둘 다 재현**해 "두 값이 같으면 측정 자체가 무효"임이 드러나게 설계됨(변별력).

> 이 슬라이스는 이 저장소의 규약을 모범적으로 지켰다. **F1은 이 설계의 결함이 아니라, 이 설계가
> 만들어진 뒤에 착지한 `PB-03`과의 사이에 생긴 비대칭이다.**

### ② `OPS-16` — 정본화 + CI 게이트 + 배선 실재성 동결까지

- 정본: `docs/prompts/l3_equivalent_gen.md`·`l3_rephrase.md`·`l3_visualization.md`·`l3_cross_verify.md` 4종.
- 게이트: `.github/workflows/ci.yml:308` — `python -m whymath_backend.harness.prompt_asset_audit --axis l3`.
- 배선 동결: `tests/infra/test_prompt_asset_audit_wiring.py`가 ⑴스텝 존재 ⑵`-m` 모듈 실행 형태
  ⑶**`--axis socratic`으로 퇴행하면 실패**("그 축은 항상 exit 0")까지 검사한다.

"검증 장치를 만들고 배선 확인 없이 완료 선언 금지" 조항을 정확히 충족한 사례다.

### ③ 메타 태그 소생 — 1차 "5필드 전부 0건"의 현재

1차가 "메타 태그 사망 실측"으로 기록한 5필드(전 코퍼스 2,647건에서 전부 0건)의 현재:

| 필드 | 1차(2026-07-30) | R3(2026-08-11) | 소생 태스크 |
|---|---|---|---|
| `persona_fit` | 0 / 2,647 | **2,647 / 2,647 (100%)** | `S3-10` done |
| `problem_type_codes` | 필드 부재 | **2,218 / 2,647 (83.8%)** | `S3-27` done → 잔여 **F3** |
| `review_status` | 필드 부재 | **2,647 / 2,647 (100%)** | `PB-03` done |
| `visual_type` | 0 / 2,647 | **0 / 2,647 (불변)** | ⏸ `S4-03` todo |
| `has_visual` | 0 / 2,647 | **0 / 2,647 (불변)** | ⏸ `S4-03` todo |
| `requires_graph_sketch` | 0 / 2,647 | **0 / 2,647 (불변)** | ⏸ `S4-03` todo |

기능 59의 1차 진단("생성은 강한데 **무엇이 없는지 볼 수 없다**")은 **대수·유형 축에서는 해소됐고
시각 축에서는 그대로다**. 시각 축은 `S4-03` 승계이므로 신규 등재 0.

---

## §2. 신규 갭 F1~F3

### 🔴 F1 — 검수 게이트가 개념 경로만 비껴간다 (헤드라인)

**사실**. `PB-03`(done)이 `l6/_shared.py:165`에 `is_review_cleared`를 신설했다:

```python
def is_review_cleared(problem: Problem) -> bool:
    """이 문항이 *검수*를 통과했는가 — 운영 축 노출 게이트(L6 공용, PB-03).
    `review_status`가 `approved`일 때만 True — `None`(미평가)·`pending`(평가 대기)·`rejected`
    (기준 미달) 전부 fail-closed로 False다."""
    return problem.review_status == ReviewStatus.approved
```

이 게이트는 **8개 지점에 배선**돼 있다 — `l6/{school_progress,suneung,metacognition,gifted,retake,
thinking}/gating.py` 6모드 + `l6/blueprint/assembly.py:245` + `api/me.py`(기본 CAT).

그런데 `S3-26`이 만든 **두 번째 학생 노출 경로**(`/study` 개념 평가 재료 주입)는 이 게이트를
경유하지 않는다:

| 지점 | 실측 |
|---|---|
| `concept_assessment_index.py:232` 후보 필터 | 3겹 = 저작권·reverify·`answer_map` 불변식. **`review_status` 조건 없음** |
| 같은 파일 `:110`·`:176` | `review_status`를 `IndexEntry`에 **캡처는 한다** — 그런데 **필터에도 런타임에도 소비처가 0인 죽은 필드**. 저자가 걸려다 만 흔적 |
| `l3/render/assessment_bank.py`(런타임 소비처) | `review_status`·`approved` grep **0건** |
| `api/study.py`·`l4/content_supply.py`·`l3/render/dsl.py` | `review_status` grep **0건** |

**측정된 결과** — 커밋된 `data/corpus/concept_assessment_v1/index.json`의 61 entry 중:

| 출처 코퍼스 | entry | 그 코퍼스의 `review_status` |
|---|---|---|
| `problem_bank_misconception_mc_v0` | 49 | `approved` 1080/1080 |
| `problem_bank_generated_v0` | 6 | `approved` 620/620 |
| **`problem_bank_v1`** | **5** | **`pending` 4/4** ← L6·CAT에서는 fail-closed 차단 |
| `problem_bank_rephrased_v0` | 1 | `approved` 429/429 |

해당 5건: 개념 **HK06**(이차방정식의 근)·**HK07**(판별식)·**HK09**(이차방정식과 이차함수의
관계)·**HK10**(이차함수의 그래프와 직선)·**HK11**(이차함수의 최대·최소) — 전부
`wm-quad-eq-larger-root`·`wm-quad-eq-root-count-mc`·`wm-quad-fn-axis` 3문항에서 상속.

**정직한 경계 (과장하지 않는다)**:

- 파일럿 유일 소단원 `quadratic_maxmin.unit.yaml`이 참조하는 개념은 `10공수1-02-06-*`이고
  위 5건은 `HK*` 코드다 → **오늘 학생이 그 5건에 실제로 도달할 가능성은 낮다. 현재 실손실은
  0에 가깝다.**
- 그러나 ⑴ **노출 후보 집합에는 이미 들어 있고** ⑵ 배제되는 이유가 *계약*이 아니라 *우연*이며
  (killer·probability 코퍼스가 빠진 것도 검수 게이트 때문이 아니라 reverify가 마침 걸러서다)
  ⑶ **`CUR-02`가 목표 축을 넓히는 순간 도달한다**.
- `PB-03` 자신이 **"현 코퍼스 100% 자체생성이라 실손실은 0 — 결함 수정이 아니라 규약 대칭·
  defense-in-depth이며 그 사실을 과장 없이 기록한다"**로 같은 성격의 축을 채택한 **선례**가 있다.
  F1은 그 선례와 동형이다.

**계열 판정**: `PED-06`→`PED-08`이 만든 **"정본화≠집행"** 계열의 재발이다. 그때는 *노출* 계약,
`PED-16`은 *억제* 계약, 이번은 **검수 계약**이다. 세 번 모두 "계약 모듈은 훌륭하게 만들어졌는데
서빙 경로 하나가 그것을 부르지 않는다"는 같은 형태다. → **D7 / `CONT-01`**

### 🔴 F2 — 개념 콘텐츠 감사 축이 흡수되지도, 미측정 선언되지도 않았다

`S3-26` notes 원문: *"감사 축은 **ARCH-21 QA 오케스트레이터가 흡수 예정**"*. `ARCH-21`은 done이고
`harness/concept_content_audit.py`도 실재한다. 그런데:

- `qa_pipeline.py` 축 등록부(`:615`~) **9축**: `corpus_audit`·`equivalence_canonicalize`·
  `concept_graph_reachability`·`misconception_crosslink_demotion`·`coach_prose_leak`·
  `content_provenance`·`defect_injection_demotion`·`banned_words_pii`·`defect_report_intake`.
  **개념 콘텐츠 축 없음.**
  (주의: `concept_graph_reachability`는 원자 *그래프 구조* 도달성이지 437행 *콘텐츠* 결함 감사가
  아니다 — 2차 §1이 이미 구분해 둔 지점이다.)
- `_NOT_MEASURED_AXES`(`:175`) = `ui_golden`·`statistical_outlier`·`performance` 3건뿐.
  **개념 축은 여기에도 없다.**

즉 **측정도 안 되고 "미측정"으로 정직 선언도 안 된 상태**다. `declared_unwired_audit.py:1019`가
`harness.concept_content_audit`을 `_OFFLINE_REPORT`("빌드타임 관측 리포트 — 사람이 돌린다")로
분류하고 있어 **그 일반 탐지기에도 걸리지 않는다**. 분류 자체는 정당하나, **흡수 약속의 소멸을
아무것도 추적하지 않는다.** → **D8 / `CONT-02`**

### 🔴 F3 — 조건부 유예가 조건 충족 후에도 상환되지 않는다 (F1·F2의 상위 원인)

1차 §4는 "태스크화하지 않는 축 6종"에 **발화 조건을 명시**했다. 조건을 적어 둔 것 자체는 좋은
설계였다. 문제는 **그 조건의 충족을 검사하는 주체가 0**이라는 것이다. 이번에 수기로 대조하니
**3건이 이미 발화 상태로 방치**돼 있었다:

| 유예 | 1차가 적은 발화 조건 | R3 실측 | 상태 |
|---|---|---|---|
| 트리거 ② 개념 콘텐츠 **결함 주입 강등전** | "D2의 감사가 착지해 결함 유형이 실측된 뒤" | `S3-26` **done** | 🔥 **발화·미등재** |
| 트리거 ⑥ **변형 3/6 미구현분**(조건변형·난이도계열·역문제) | "`S4-14` 착지 후" | `S4-14` **done**(2026-08-05) | 🔥 **발화·미등재** |
| `S3-27` acceptance ④ **`rephrased_v0` 429 제외** | "`S4-14` 미착지로 원 생성기 추적 불가" | 후속 `S4-21` **done** | 🔥 **발화·미상환** |
| 트리거 ① 결정론 맥락 슬롯 | 3조건 동시(ⓐ결정론 템플릿 아키텍처 ⓑ구조 필드 ⓒD3 리포트) | ⓒ만 성립(`zero_coverage_types`), ⓐ 미착지 | 미발화(정상) |
| 트리거 ③ PRM 스코어러 | `solution §4-②` 승계 | 변화 없음 | 미발화(정상) |
| 트리거 ④ 멀티모달 | `S4-03` 착지 | `S4-03` **todo** | 미발화(정상) |
| 트리거 ⑤ 문항 소요 시간 | `S3-01` 파일럿 실측 후 | `S3-01` **todo** | 미발화(정상) |

세 번째 행은 특히 측정 가능하다: **미태깅 429건은 전량 `rephrased_v0`**이고, 그 유예의 근거였던
계보 미영속은 `S4-21-rephrase-lineage-identity-decision`(**done** — `identity_id` 신설 +
`problem_relation` 변형 이력 + 429 소급 처리)으로 해소됐다. 그런데 태깅은 재실행되지 않았다.

**왜 이것이 단순 누락이 아니라 구조 문제인가**: `problem_bank_coverage.zero_coverage_types()`는
docstring이 스스로 **"§4-① 트리거의 발화 계측기"**라고 선언한 도구다. 코퍼스의 **16.2%가
미태깅**인 채로는 그 계측기의 "0커버 유형" 판정이 과대 계상된다 — **유예가 유예를 낳는다**
(트리거 ①의 발화 판정이 트리거 ③의 미상환에 오염된다).

**규약 대조**: CLAUDE.md 금기 **"만료 없는 유예·제외 금지"**(2026-08-03 결정·2026-08-10 통합점검
본문 등재)가 *"미머지 완료분을 전제로 한 유예·제외는 반드시 **만료 또는 재확인 지점**을 동반한다.
1차 집행은 규칙 산문이 아니라 코드다"*라고 적고 있다. **갭 점검 문서의 §4 트리거 절은 아직 산문
단계에 있다.** → **D9 / `CONT-03`**(일반 계약) · **D10 / `CONT-04`**(구체적 미상환 1건)

---

## §3. 설계 D7~D10 (등재 4건)

> 실행 우선순위: **D7(노출 무결성) → D10(계측기 신뢰성) → D8(감사 축 거취) → D9(일반 계약)**.
> 근거: 의사결정 우선순위 서열상 **현존 노출의 무결성**이 항상 앞서고(D7), 그다음이 판정
> 계측기의 신뢰성(D10)이며, D8·D9는 부채 정리다.

### D7. 개념 평가 재료 주입에 검수 축 집행 — `CONT-01` (math-completion·S3·p2)

- **핵심**: `concept_assessment_index.py`의 3겹 필터에 `review_status == approved`를 **4번째 겹**
  으로 추가. **신규 필드 0** — 이미 캡처되고 있는 죽은 필드의 소생일 뿐이다.
- **판정 권위 단일화**: `l6/_shared.is_review_cleared`와 같은 기준을 쓰되, 그 함수는 ORM `Problem`을
  받고 이쪽은 빌드타임 JSONL dict라 직접 재사용이 불가하다 → 기준 이원화를 피하는 방법(enum 공유
  vs 판정 헬퍼 승격)을 설계 판단으로 명시. **`is_exposable`(법적 축)과 `is_review_cleared`(운영
  축)를 분리한 `PB-03`의 설계는 유지 — 합치지 않는다**(합치면 운영 사유로 법적 게이트를 느슨하게
  하는 압력이 생긴다).
- **전후 실측 기록**: 5건이 실제로 빠지는지, `concepts_covered`가 61→몇으로 바뀌는지 기록.
  **커버율 하락은 결함이 아니라 게이트가 일한 증거**이므로 숨기지 않는다.
- **변별력 의무**: `pending` 레코드 1건 주입 → 탈락 실측 → 정상 상태 미탈락 실측(양방향).
  뮤테이션 원복은 **`cp` 백업으로만**(`git checkout` 금지 — 2026-08-10 등재 규칙).
- **경계**: 신규 학생 대면 축 0 · LLM 0 · 신규 저작 0 · 개념 설명 LLM 생성 폴백 **켜지 않는다**.

### D8. 개념 콘텐츠 감사 축의 거취 판정 — `CONT-02` (infra-debt·S4·p3)

- **택1**(둘 다 안 하는 현 상태만 금지): ⓐ `qa_pipeline`에 `concept_content` 축 흡수 —
  또는 ⓑ `_NOT_MEASURED_AXES`에 **사유와 함께** 정직 등재.
- ⓑ를 택하면 사유는 **"코드 미구현"이 아니다**(코드는 실재한다) — 실제 사유를 적는다.
- **`CONT-03`과 역할 분리**: 이 태스크는 *이 1건의 거취*, `CONT-03`은 *일반 계약*.

### D9. 유예 트리거의 만료·재확인 계약 — `CONT-03` (infra-debt·S4·p3)

- **선례 이식**: `ARCH-25`의 `GrandfatherEntry` 만료 계약 + `OPS-22`의 3분류
  (`reached` / `by-design:<사유>` / `pending-task:<id>`) — 참조 태스크가 done이 되면 waiver가
  **expired로 뒤집혀 exit 1**이 되는 형태.
- **범위 판정 선행**: 이 편에만 걸지, 갭 점검 시리즈 전편(현재 28편·각 편이 §4 트리거 절을 가짐)에
  걸지 먼저 정한다. 전편이면 수집기가 **문서 파싱**에 의존하게 되므로, 트리거를 **backlog 필드로
  승격**하는 안과 비교해 택한다.
- **대장 신설 금지** — `backlog/`가 단일 진실 원천.
- **변별력**: 양방향 실측 + 수집기 파손 시 **exit 2**(0건 통과 위장 금지).

### D10. `rephrased_v0` 429 유형 태깅 완결 — `CONT-04` (math-completion·S4·p4)

- **전제 재확인 선행**: `S4-21` 착지로 `identity_id`/`relations` 기반 부모 추적이 *실제로* 가능한지
  먼저 실측하고, 가능한 범위에서만 태깅한다(가정 기반 실행 금지).
- **상속 논거 명문화**: 재서술은 봉인 모델상 수치·정답·선지 불변이므로 **인지 행동 유형도 불변**.
  LLM 0 · 텍스트 추론 0 · 재실행 바이트 결정론(`S3-27`·`S3-10` 백필 동형).
- **실제 가치는 태깅이 아니라 계측기 신뢰성**: `zero_coverage_types()` 결과가 전후로 어떻게
  바뀌는지 기록한다. 상속 불가 잔여분은 건수·사유를 명시(부분 커버의 정직 고지 — `S3-27` 형식 유지).

---

## §4. 반복 실수 등재

### ① "정본화≠집행" 계열 — 3회차

| 회차 | 사례 | 계약의 성격 |
|---|---|---|
| 1 | `PED-06`→`PED-08` — `growth_evidence_exposure.py` 3계층 노출 계약을 만들었으나 `GET /v1/me/harness-metrics`가 원시 11지표를 그대로 반환 | **노출** 계약 |
| 2 | `PED-16` — `mode_guard.check_forbidden_modes`가 오프라인 측정 전용, 코치 응답 경로 미배선 | **억제** 계약 |
| **3** | **F1 — `is_review_cleared`가 8지점에 배선됐으나 `/study` 개념 경로만 비껴감** | **검수** 계약 |

세 번 모두 **계약 모듈 자체는 훌륭하다**. 실패는 항상 "그 계약을 부르지 않는 서빙 경로가 하나
남아 있다"는 형태다. CLAUDE.md가 이미 *"계약을 만드는 태스크의 acceptance는 ①정본화와 ②**집행
지점**을 별항으로 분리해 적는다"*를 금기로 등재했는데, **F1은 그 금기가 등재된 뒤에 생긴 사례가
아니라, 등재 이전에 만들어진 경로가 남아 있던 사례**다 — 즉 규칙은 *신규*를 막지만 *재고*를
청소하지는 않는다. `CONT-01`이 그 재고 1건이다.

### ② "약속의 소멸" 계열 — 신설 (2건)

| # | 사례 | 약속이 적힌 자리 |
|---|---|---|
| 1 | **F2** — `S3-26` notes "감사 축은 ARCH-21이 흡수 예정" → `ARCH-21` done, 흡수 0 | 완료 태스크의 `notes` |
| 2 | **F3** — 1차 §4 트리거 6종·`S3-27` acceptance ④의 조건부 제외 | 갭 점검 문서의 산문 |

**공통 원인**: 약속이 **완료 태스크의 notes**나 **문서 산문**에 적히면, 그 태스크가 done이 되는
순간 약속도 함께 "완료된 것처럼" 보인다. `backlog/`가 단일 진실 원천인데 **약속은 backlog 밖에
있다**. `CONT-03`이 이 계열의 1차 집행이다.

---

## §5. 정정 (원본 수정 아님 — 델타 기록)

**정정 ①** — 1차 §4-⑥·`S3-27` acceptance ④·`S4-14` notes가 후속 태스크를 **`S4-18`**로 지목하고
있으나, 현재 `S4-18`은 **`S4-18-review-time-axis`**(복습 시간축·목표축 — `ai_tutor_module_gap_review`
§3 D5)로 **무관한 태스크**다. 실제 후속은 **`S4-21-rephrase-lineage-identity-decision`**(done)이다.
**태스크 소실이 아니라 번호 재배정**이며(`HARN-10`/`HARN-15` 번호 충돌 가드 계열), 참조만 stale하다.

**정정 ②** — 2차 §1이 `ARCH-21`을 "7축"으로 기록했다. 현재 **9축**이다(`ARCH-24`가
`banned_words_pii`를 `_NOT_MEASURED_AXES`에서 승격, `defect_report_intake` 신설). 2차 시점
기록으로는 정확했다.

---

## 부록 A — 방법론 함정 (이 세션에서 실측)

**태스크 `artifacts:`의 SHA로 착지를 판정하지 말 것.** 이 저장소는 squash merge를 쓰므로
`artifacts`에 적힌 브랜치 커밋 SHA는 **main의 조상이 아니다**. `git merge-base --is-ancestor`가
실패해도 **고립의 증거가 아니다** — `S3-26`의 `0661203c`도, `OPS-22`의 `0a7157f2`도 모두 조상이
아니지만 **코드는 main에 실재**한다(`ops/declared_unwired_audit.py`·`harness/concept_*.py` 확인).

**착지 판정은 SHA가 아니라 ⑴코드 실재 ⑵서빙/CI 배선 ⑶실제 값으로만 한다.**

## 부록 B — 실측 재현 명령

```bash
# F1 — index 61 entry의 출처 코퍼스 분포 (problem_bank_v1: 5 가 나와야 함)
python3 - <<'EOF'
import json,collections
d=json.load(open('data/corpus/concept_assessment_v1/index.json',encoding='utf-8'))
print(collections.Counter(e['problem_bank'] for e in d['entries']))
print("counts:", d['counts'])
EOF

# F1 — 코퍼스별 review_status 분포 (killer/probability_finite/v1 = pending)
python3 - <<'EOF'
import json,glob,collections
for p in sorted(glob.glob('data/corpus/problem_bank_*/problems.jsonl')):
    c=collections.Counter(json.loads(l)['review_status']
        for l in open(p,encoding='utf-8') if l.strip())
    print(f"{p.split('/')[-2]:36s} {dict(c)}")
EOF

# F3 — problem_type_codes 미태깅 분포 (rephrased_v0: 429 전량)
python3 - <<'EOF'
import json,glob,collections
miss=collections.Counter()
for p in sorted(glob.glob('data/corpus/problem_bank_*/problems.jsonl')):
    for l in open(p,encoding='utf-8'):
        if l.strip() and not json.loads(l).get('problem_type_codes'):
            miss[p.split('/')[-2]]+=1
print(dict(miss))
EOF
```

**코드 위치 확인**:
- F1: `l6/_shared.py:165`(`is_review_cleared`) · `harness/concept_assessment_index.py:110,176,232` ·
  `l3/render/assessment_bank.py`(`review_status` 0건) · `l4/content_supply.py:52,240,248`
- F2: `harness/qa_pipeline.py:175`(`_NOT_MEASURED_AXES`)·`:615~`(9축 등록부) ·
  `ops/declared_unwired_audit.py:1019`(`_OFFLINE_REPORT` 분류)
- F3: `harness/problem_bank_coverage.py:472`(`zero_coverage_types` docstring — "§4-① 트리거의 발화 계측기")
- 착지 검증: `.github/workflows/ci.yml:308` · `tests/infra/test_prompt_asset_audit_wiring.py` ·
  `docs/prompts/l3_*.md` 4종 · `ops/pedagogy_content_slot_reach_report.py`
