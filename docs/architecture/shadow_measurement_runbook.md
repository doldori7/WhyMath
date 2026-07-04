# Shadow → Canary 측정 런북 (오개념 게이트)

> **목적**: 오개념 진단의 네 게이트를 *노출 없이* shadow 모드로 켜고, 구조화 관측 로그를 모아
> harvest 도구로 집계해 **canary/노출(on) 승격 여부**를 정량 데이터로 결정하는 운영 절차.
> 설계 근거: `math_dsl_remediation_design.md` §1.3(crosswalk)·§2.5(wrong_form),
> `04b_misconception_judge_graduation.md`(judge·semantic). 정본 패턴: `l4/step_shadow_harvest`.

## 원칙 (협상 불가)

- **측정 전 노출 금지**: 모든 게이트는 shadow(비노출·비차단)로 *먼저 측정*한 뒤에만 canary/on을
  검토한다(의사결정 우선순위 #1 학생 안전 · #3 교수학적 정확성 ≫ #6 비용).
- **프라이버시**: 관측 레코드엔 학생 풀이 원문·식별자·judge 근거가 *구조적으로* 없다
  (`extra="forbid"` + 필드 한정 — 추상 오개념 id·개수·유사도·verdict 카운트만). 로그 sink도
  미성년 PII 취급 규약을 따른다.
- **측정 윈도에만 켠다**: shadow 모드는 비용(임베딩 로드·per-write DB 왕복·judge LLM)을 유발하므로
  상시 on이 아니라 *측정 기간 한정*으로 켠다. 기본은 전부 `off`.

## 게이트 요약

| 게이트 | 켜기(env) | record 로거 | harvest 모듈 | 핵심 결정 변수 |
|---|---|---|---|---|
| crosswalk 매핑 | `WHYMATH_MISCONCEPTION_CROSSLINK_MODE=shadow` | `whymath.l4.misconception.crosslink_shadow.record` | `crosslink_shadow_harvest` | `distinct_canonical_ratio`·`unmapped_kebab_ids`·`canonical_ambiguous_kebab_ids` |
| wrong-form(SymPy) | `WHYMATH_MISCONCEPTION_WRONG_FORM_MODE=shadow` | `whymath.l4.misconception.wrong_form_shadow.record` | `wrong_form_shadow_harvest` | `sympy_only_id_freq`(가치)·`substring_only_id_freq`(결합 유지) |
| semantic 매칭 | `WHYMATH_MISCONCEPTION_SEMANTIC_MODE=shadow` | `whymath.l4.misconception.shadow.record` | `semantic_shadow_harvest` | `semantic_only_id_freq`·`sim_ge_*`(feed 임계) |
| judge 필터 | `…SEMANTIC_MODE=shadow` + `WHYMATH_MISCONCEPTION_JUDGE_SHADOW=true` | `whymath.l4.misconception.judge_shadow.record` | `judge_shadow_harvest` | `remove_rate`(가치)·`uncertain_rate`(신뢰) |

> judge shadow는 semantic 매처가 라이브로 도는 경로에 얹히므로 `SEMANTIC_MODE=shadow`가 *전제*다
> (비용 분리: 매처 shadow는 싸고 judge는 LLM 수 초라 별 토글). judge *노출* 게이트
> (`misconception_judge_enabled`)는 이 측정 이후의 별도 결정이다.

## 절차 (게이트 공통 4단계)

### 1. shadow 켜기 (측정 윈도)
해당 env 플래그를 측정 기간에만 설정한다. 노출·verdict·DB 저장은 불변(off와 비트동일 관측)이고,
관측은 record 로거로만 흐른다.

### 2. 관측 JSONL 수집
로그 sink에서 위 표의 *record 로거 이름* 라인만 골라 한 줄당 JSON(관측 1건)인 `obs.jsonl`로 모은다
(평문 로그·다른 로거 노이즈 배제 — 로거 이름 필터). 수집은 관측 인프라(로그 파이프라인) 몫이며
harvest는 모인 파일을 읽는다.

### 3. harvest 집계 (오프라인·순수·비노출)
```bash
python -m whymath_backend.l4.misconception.crosslink_shadow_harvest   obs.jsonl
python -m whymath_backend.l4.misconception.wrong_form_shadow_harvest  obs.jsonl
python -m whymath_backend.l4.misconception.semantic_shadow_harvest    obs.jsonl
python -m whymath_backend.l4.misconception.judge_shadow_harvest       obs.jsonl
```
각 명령은 사람이 읽는 요약 리포트를 출력하고, *마지막 줄은 파싱 가능한 JSON*(요약 모델
`model_dump_json` — 스냅샷·회귀·대시보드 재적재용)이다.

### 4. 판정 (게이트별 결정 변수 → go/no-go)
아래 게이트별 절을 본다. **구체적 임계(cutoff)는 실 트래픽·제품 판단**이며 이 런북은 *어느 변수를
어느 방향으로 읽는지*만 고정한다(임의 숫자 단정 금지 — CLAUDE.md "모르면 모른다고").

---

## crosswalk 적재 (shadow 전 · canary 전제)

> shadow 측정은 *매핑이 이미 적재됐다고 전제*한다. 아래는 그 앞단계 — 사람 검수·승인된 crosswalk
> 매핑을 라이브 DB에 적재하는 절차다. 승인 자산: `data/corpus/misconception_crosslink_v1/crosslinks.json`
> (**30건** 직접매핑·Kiki "권장대로 승인" 27 + 보류/반려 후속 3·근거
> `docs/data/misconception_crosslink_candidates.md` §2.3·§2.4·§2.5).

### 0-a. 전제
- **alembic `head` 적용** — `misconception_catalog`·`misconception_crosslink` 테이블 존재(crosslink는
  마이그레이션 `e2f3a4b5c6d7`).
- **M-id 카탈로그 선행 적재(FK)** — `misconception_crosslink.mis_id`는 **실 FK →
  `misconception_catalog.mis_id`**(CASCADE)라, 카탈로그가 *먼저* 적재돼 있어야 한다(미적재 시 FK 위반).
  후속 신규 M-id(M0862·M0863)는 코퍼스(841)에 포함되므로 아래 한 번의 적재로 FK가 충족된다:
  ```bash
  python -m whymath_backend.l1.misconception.populate \
      --misconceptions data/corpus/misconceptions_v1/misconceptions.json
  ```
- **DB 자격** — `WHYMATH_DATABASE_URL`(async). 로더는 sync psycopg URL을 `Settings.sync_database_url`로
  파생한다(시크릿은 env·코드에 0).

### 0-b. 적재 (멱등)
```bash
python -m whymath_backend.l1.misconception.crosslink_populate \
    --crosslinks data/corpus/misconception_crosslink_v1/crosslinks.json
# → "crosswalk 적재 완료: 30건 (src=…/crosslinks.json)."
```
의미 유일키 `(kebab_id, mis_id, link_type)` upsert라 **재실행 안전**(중복 삽입 없음).

### 0-c. 검증
- 적재 행 수 = **30**(전 30 kebab 매핑·미매핑 0).
- read-time resolver 스모크(적재가 실제 해석되는지):
  ```python
  from whymath_backend.l1.misconception.crosslink_resolve import MisconceptionCrosslinkResolver
  MisconceptionCrosslinkResolver().resolve("distribution-over-power")  # → ["M0019"]
  ```
- 자산 무결성(스키마·FK·트리플 유일)은 `tests/backend/l1/test_crosslink_populate.py`가 CI에서 고정한다.

### 0-d. 롤백
배치 식별 note나 30개 `(kebab_id, mis_id, link_type)` 트리플로 `misconception_crosslink`에서 삭제(멱등이라
재적재 가능). crosslink 단독 삭제는 안전 — `mis_id` CASCADE는 *카탈로그* 삭제 시에만 전파한다.

### 0-e. 보류/반려 후속 (해소·§candidates 2.5)
초기 3건(§2.3 보류 2·반려 1)은 후속으로 **전부 해소**돼 적재 대상에 포함됐다: `period-of-scaled-sine`·
`angle-sum-non-triangle`은 kebab 카탈로그에서 **신규 M-id(M0862·M0863)** 발행(코퍼스 839→841),
`fraction-cancellation`은 M0118 확인. → 미적재 0(전 30 kebab 매핑).

---

## crosswalk 매핑 (kebab-id → canonical M-id)

> **전제**: 위 '## crosswalk 적재' 완료(30건 승인·`§candidates 2.4`·§2.5). 미적재 상태에선 coverage=0만 나온다.

- **가치 변수**: `distinct_canonical_ratio` — 실 런타임에 등장한 *서로 다른* kebab-id 중
  **canonical 선택 정책**(`select_canonical` — confidence NOT NULL 직접매핑의 strict 최대가
  *단독*일 때만 선정)을 통과한 비율. canary(M-id canonical 플립)는 이 커버리지가 *충분히
  차오른 뒤* 검토한다 — 원시 링크 유무(`distinct_coverage_ratio`)는 1:N을 구분 못 해 참고
  지표로 강등(1:N 링크만 세면 ambiguous 집계가 무의미).
- **큐레이션 우선순위**: `unmapped_kebab_ids` — 자주 등장하나 매핑이 없는 kebab-id부터 사람이
  crosswalk를 채운다(coverage를 올리는 최단 경로).
- **정책 필요**: `canonical_ambiguous_kebab_ids` — 직접매핑 최고 confidence *동률(tie)*이라
  canonical이 자동 선정되지 않은 kebab-id. 플립 전 사람이 우선순위를 확정해야 한다(자동 임의
  선택은 오귀속 위험이라 resolver가 정직하게 미선정). `ambiguous_kebab_ids`(1:N 원시 링크)는
  다중 표시 정책 검토용 참고 목록.
- **게이트 우회 감시**: `kebab_invalid` > 0 — 정본 카탈로그 밖 kebab-id가 게이트를 통과했다는 신호
  (조사 대상).

## crosswalk canary 승격 정책 (M-id canonical 플립)

> **무엇이 바뀌나(범위 정의)**: canary는 진단 *런타임* 경로를 바꾸지 않는다 — kebab-id는 계속 탐지·
> 저장 키다(resolver read-time 매핑 불변). canary가 바꾸는 것은 **리포트·집계 계층의 canonical 정체성**
> (학부모/교사 리포트·오개념 집계에서 kebab 대신 M-id를 대표로 표시·묶음)뿐이다. 이 좁은 표면이라
> 롤백이 안전하다(진단 불변).
>
> **원칙 계승(협상 불가)**: 측정 전 노출 금지 · 학생 안전 #1 · 교수학 정확성 #3 · 미성년 PII 보호.
> **구체 cutoff 숫자는 이 문서가 단정하지 않는다**(런북 관례 "모르면 모른다고") — *어느 변수를 어느
> 방향으로 보고 누가 sign-off하는지*의 프레임만 고정한다.

### 승격 단계 (staged)
1. **shadow(측정·현재)** — `…CROSSLINK_MODE=shadow`. 노출 0. harvest로 커버리지 수집.
2. **canary(제한 노출)** — M-id를 canonical로 *제한 범위*(내부 검수 코호트 → 소규모 %)에서 리포트·
   집계에 소비. **신규 mode 값(예 `canary`)·플립 코드는 아래 게이트 충족 후 별 슬라이스**(현재 미착수 —
   실 shadow 데이터 0이라 premature·enum 값도 미추가로 dead code 회피).
3. **full(전면)** — 전 범위 M-id canonical.

### go/no-go 결정 변수 (harvest → 사람 판정)
`crosslink_shadow_harvest` 산출을 다음 방향으로 읽고 **제품+교수학 sign-off**로 단계 승격한다:
- `distinct_coverage_ratio` **↑ 충분** — 실 등장 kebab 중 매핑 보유 비율이 합의 임계 이상.
- `unmapped_kebab_ids` **고빈도 0** — 자주 등장하는 미매핑 kebab을 먼저 큐레이션(남으면 canary에서 그
  kebab만 kebab-id 폴백). *현재 적재는 전 30 kebab 매핑이라 카탈로그 커버리지 100%* — 관측 미매핑은
  카탈로그 밖 신규 kebab 등장 신호.
- `ambiguous_kebab_ids`(1:N) **정책 확정** — *현재 적재는 30 kebab→30 M-id 1:1이라 1:N 0*. 향후
  부분매핑(P) 추가로 1:N이 생기면 **confidence 우선·다중 표시 규칙을 사람이 확정한 뒤**에만 플립.
- `kebab_invalid == 0` — 카탈로그 밖 id 유입 없음(게이트 위생 전제).
- **관측량 최소 N** — 통계적으로 의미 있는 표본 축적 후 판정(구체 수는 제품 판단).

### canary 범위 (미성년 프라이버시)
- **PII 기반 타깃팅 금지**(CLAUDE.md 금기) — 개인 식별 세그먼트로 노출 대상 선별 금지.
- 권장 순서: 내부 검수 코호트/opt-in → 소규모 *무작위* % → 확대. 학교·학년 정보로 개인 식별 가능한
  결과를 외부 노출하지 않는다.

### fallback (never-break)
- `resolve()`가 빈 결과인 kebab은 canary에서도 **kebab-id로 폴백**(resolver 기본·이미 구현). 매핑 부재·
  DB 실패가 리포트/코칭을 깨지 않는다(비차단).

### 모니터링·롤백 트리거
- 오도된 리포트 신호(학부모/교사 이의·이상 분포)·`resolve` 실패율 급증·1:N 오표시 → **즉시
  `mode=shadow`/`off` 롤백**. canary는 리포트/집계 계층만 건드리고 진단 런타임(kebab)은 불변이라
  롤백이 무상태·안전(플립 전후 진단 동일).

### 안전 불변식 (canary에서도 유지)
- **거짓 낙인 금지**: M-id 노출이 "틀렸다" 단정을 강화하지 않는다(`05a` RS2·프로브 정답/수정 필드 부재
  유지).
- **검증 게이트**: 학생 노출 전 검증(risk_register Q10-⑨) 계승 — canary가 우회로가 되지 않는다.
- **오개념 독립 그래프·reactive**: canary가 정상 추론 경로에 오개념을 주입하지 않는다(Q10-⑥).

### 코드 착수 조건 (이 정책이 게이트)
`canary` mode 값·플립 코드는 **(a) 실 shadow 데이터가 위 go/no-go 충족 + (b) 1:N 정책 확정 +
(c) 제품·교수학 sign-off** 이후에만 별 슬라이스로 착수한다. 그 전에는 착수하지 않는다(측정 전 노출 금지).

## wrong-form (SymPy 거짓 항등식)

- **가치 변수**: `sympy_only_id_freq` — substring이 놓친(변수명·표기 변이) 오개념을 SymPy가 새로
  잡은 빈도. 노출 통합은 *substring과의 결합*(대체 아님)이므로 이 순기여가 결합의 이득이다.
- **결합 유지**: `substring_only_id_freq` — SymPy가 못 잡고 substring만 잡은 오개념. 결합 후에도
  substring 경로가 계속 커버해야 할 목록(대체 시 회귀 리스크).
- **주의**: shadow는 *비노출 측정*이라 SymPy의 거짓양성/음성은 사람이 표본을 검토해 판단한다
  (거짓 낙인 방지 가드가 있으나 canary 전 표본 검수 권장).

## semantic 매칭

- **가치 변수**: `semantic_only_id_freq` — substring이 놓친(의미 유사) 오개념을 의미 매처가 후보로
  올린 빈도(+recall). 단, +recall과 방향맹 FP가 섞이므로 유사도로 걸러 본다.
- **feed 임계**: `sim_ge_090`·`sim_ge_080`·`sim_ge_070`(누적) — "feed 임계 T를 잡으면 semantic-only
  몇 건이 남나". `on` 승격 시 combine 대상 후보를 거를 코사인 운영점 선정 근거(04b §4).
- **노출 플립**: `SEMANTIC_MODE=on`은 substring 아래에 semantic-only 후보를 *결합 노출*한다
  (substring 우선·재정렬 없음·비블로킹·실패 시 substring 폴백).

## judge 필터

- **가치 변수**: `remove_rate` — judge가 의미 후보 중 FP로 판정해 걸러낼 비율(정밀도 향상). 단
  과도하면 over-removal(recall 손실)이므로 `would_keep`와 함께 본다.
- **신뢰 변수**: `uncertain_rate` — 모호·폴백(형식 위반·seam 예외) 비율. 높으면 judge 라우팅·프롬프트
  재점검 신호(신뢰 리스크). judge는 `아니오`만 거르고 `예`·`불확실`은 유지(recall 보존·보수).
- **FP 원천**: `would_remove_id_freq` — judge가 주로 걸러낸 오개념 = 의미 매처 FP 주 원천 진단.
- **운영점 맥락**: `routings` — 관측에 섞인 judge 라우팅 프로파일(서로 다른 모델의 율 차이 해석용).

---

## 참고: 단계-비보존 shadow (선례·라벨 기반)

`step_shadow`는 coverage/분포가 아니라 *A/B 라벨링 워크시트*를 낸다:
`step_shadow_harvest`(관측→`human_label:null` draft) → 사람이 A/B 채움 → `step_shadow_eval`(precision
측정). 오개념 네 게이트의 harvest는 이 *관측→오프라인 집계* 정본 패턴을 공유하되 산출이 *coverage/
분포 요약*이라는 점만 다르다(라벨 불요 — 카탈로그 id 자체가 관측에 실림).
