# 운영(Operations) 모듈 — 외부 EOS 틀 대조 **2차 재점검(r2)** (2026-08-03)

> ⚠️ **후속 재점검 있음 — `operations_module_gap_review_r3.md`(2026-08-11)**. 이 문서(r2)의
> 설계 **D4·D5는 구현 완료**(`ARCH-24`·`ARCH-25`)됐고 **D3는 9일째 미착수**(`ARCH-23` todo)다.
> r3가 D3에 **두 번째 블로커**(축 9 `defect_report_intake` 상시 error)를 실측 추가했고,
> §1 판정 중 42·45-⑤·47이 stale해졌다. 또한 r2가 46·49·50을 "`OPS-01~04` done → 상환"으로
> 승계한 판정을 r3 §1 정정 ⑥이 **정정**한다(런북 3종 자인 공백 25종 추적 0건).
> 이 문서는 **완료 태스크의 판정 근거 원본**으로 보존하며 소급 수정하지 않는다. 현행은 r3.

> **범위**: v1(`operations_module_gap_review.md`, 2026-07-29)과 **동일한 외부 참고 문서**
> (『0단계 운영(EOS)』 핵심 모듈 42~45 + 확장 제안 46~50 — WhyMath 전용이 아닌 일반적 틀,
> Kiki 제공)를 **v1 이후 5일간의 코드베이스 변화**와 다시 대조한 기록.
> **성격**: 처음부터의 재대조가 아니라 **델타 재점검**이다. v1의 판정 대부분은 유효하므로
> 승계하고, ⑴ **stale해진 판정 칸**과 ⑵ **v1의 설계(D1·D2)가 구현된 뒤 남은 실공백**만 다룬다.
> **v1 이후 상태**: v1이 설계한 D1·D2가 **둘 다 구현 완료**됐다 —
> `ARCH-20-content-provenance-enforcement-gate`(done, 2026-07-30) ·
> `ARCH-21-qa-pipeline-orchestrator`(done, 2026-08-02).
>
> **결론 3줄**:
> 1. **최대 갭 = QA 게이트가 상시 fail-open**. `ARCH-21`이 만든 게이트가 CI에 배선은 됐으나
>    `ci.yml:186` `continue-on-error: true`로 **아무것도 막지 않고**, 그 사실을 기계로 감시하는
>    장치가 없다(`test_qa_pipeline_wiring.py`는 5개 계약을 동결하나 강제 여부는 보지 않는다).
>    CLAUDE.md 금기 "상시 실패하는 fail-open 보호를 '보호 있음'으로 신뢰 금지"에 정면 해당 → **D3**.
> 2. **두 번째 갭 = 학생 대면 출력의 금칙어·PII 검사기 0**. `qa_pipeline`이 정직하게
>    "검사 안 함"으로 표기하지만(`banned_words_pii`) **백로그 추적이 0건**이라 상환 일정이 없다.
>    의사결정 우선순위 1위(학생 안전) 축인데 추적조차 없다 → **D4**.
> 3. **v1 판정표 stale 4칸 정정** — 43(CMS)·47(감사 로그)·48(RBAC)·45-⑤(PII). 특히 v1은
>    `docs/design/ui/03·04_admin_console_*.md`(관리 콘솔 계획·아키텍처 **정본**)를 참조하지 않은
>    채 43번을 "전무"로 판정했다. 코드가 0인 것은 맞지만 **설계는 이미 정본이 있다**.

관련 정본: `docs/architecture/operations_module_gap_review.md`(v1 — 이 문서의 모체, 판정 근거의
원본) · `docs/design/ui/03_admin_console_plan.md`·`04_admin_console_architecture.md`(관리 콘솔
정본 — v1 미참조분) · `docs/reviews/service_ops_mgmt_gap_review_2026-07.md`(`OPS-01~04`) ·
`docs/legal/copyright_gradient.md` §4 · `MEMORY.md` 결정 로그(2026-07-29 v1 · 2026-07-30 ARCH-20 ·
2026-08-02 ARCH-21 · 2026-08-03 본 문서).

---

## §0. 재점검 사유 — 왜 v1을 덮어쓰지 않고 r2를 새로 쓰는가

**용어**: v1 §0의 처리를 그대로 승계한다 — 첨부 문서의 "EOS"는 **외부 참고 프레임워크의 명칭**
(사내 백오피스 의미)이고, `dev_constitution.md` §0이 폐기한 대외 정체성 어휘 "EOS"와는 **동명이의**다.
이 저장소가 스스로를 EOS로 선언하는 것과 무관하다. 새 계층(L8)도 만들지 않는다 — 운영은 CLAUDE.md가
규정한 **횡단 관심사**다.

**v1을 in-place 수정하지 않는 이유**: v1은 `ARCH-20`·`ARCH-21` 태스크 `notes`가 가리키는 **정본
참조 대상**이다. 이미 완료된 태스크의 판정 근거를 소급 변조하면 "왜 그렇게 결정했는가"의 기록이
사라진다. `docs/standards/arch_audit_2026-07-09.md → _r2/_r3/_r4` 리비전 파일 관례를 따른다.
v1에는 이 문서로 오는 **배너 1줄**만 추가했다.

**재점검이 필요했던 실제 사유 2종** (둘 다 이 세션 실측):

| 사유 | 실측 |
|---|---|
| ⑴ v1 판정표 stale | 07-29 이후 `SEC-07`(Role v0)·`SEC-09`(PrivacyAudit)·`SEC-11`(로그 스크러버)이 착지해 v1이 "0건"으로 적은 칸 3개가 사실과 달라졌다. v1 자신의 누락 1건(43번 설계 정본 미참조)도 함께 발견 |
| ⑵ D1·D2 구현이 남긴 잔여 | 설계가 코드가 되면서 **설계 단계엔 없던 새 공백**이 생겼다 — 게이트의 fail-open 상태, 미측정 축의 무추적, 그랜드파더 면제의 무기한화 |

---

## §1. v1 §1 판정표 정정 (stale 칸만)

> 변화 없는 칸은 재대조하지 않는다 — v1 §1을 그대로 승계한다. 아래는 **바뀐 칸만**이다.

### 정정 ① — 모듈 48 (RBAC): 🚫 "role/permission 모델 0건" → ⚠️ **부분 실재**

| | v1 (07-29) | r2 실측 (08-03) |
|---|---|---|
| 근거 | "role/permission 모델 0건(`schema/user.py` 전수 확인)" | `schema/enums.py:1163` `Role`(v0 **2값** STUDENT/CONTENT_ADMIN) + `api/_auth.py:96` `require_role(*roles)` + `_auth.py:123` `require_content_admin` |
| 판정 | 🚫 §2-④ 의도적 지연 | ⚠️ **부분** — 인가 축은 열렸다. 남은 것은 *역할 수*(2값)와 *항목 단위 인가*(2차원 매트릭스) |

**경위**: `SEC-07-unauthenticated-write-seal-role-v0`(done, 2026-07-30)이 v1 작성 **다음날** 착지했다.
v1의 "즉시 신설 금지(§2-④)" 판정 자체는 유지된다 — SEC-07은 CMS를 만든 게 아니라 **무인증
콘텐츠 CUD(DELETE 포함)를 봉인**한 보안 조치이고, 역할도 좌석 있는 2값으로 의도적으로 축소했다.
"CMS·RBAC를 통째로 신설하지 않는다"와 "인가 게이트는 필요한 만큼 연다"는 충돌하지 않는다.

### 정정 ② — 모듈 47 (감사 로그): "DeletionAudit + generation_log(쓰기 0)" → **감사 2종 실가동**

| | v1 (07-29) | r2 실측 (08-03) |
|---|---|---|
| 근거 | `db/models/audit.py`(`DeletionAudit`)·`generation_log`(마이그레이션만) | `db/models/audit.py:37` `DeletionAudit` + **:77 `PrivacyAudit`**. writer 실배선 — `privacy/audit.py:79/100/124`(반출·동의변경·관리자접근 3종)·`api/me.py:307`·`privacy/erasure.py:198`. reader `GET /v1/me/privacy-audit` |
| 판정 | ⚠️ 부분 → D2 흡수 | ⚠️ **부분 유지 — 다만 잔여의 정체가 바뀌었다** (아래) |

**경위**: `SEC-09`(done, 2026-07-30). **잔여의 정확한 정체**: 개인정보 축 감사는 닫혔고,
**콘텐츠 운영 액션 감사(승인·반려·플래그 변경)가 여전히 0**이다. 이건 감사 인프라가 없어서가
아니라 **감사할 액션 자체가 없기 때문**이다 — `review_status`는 전 API에서 **읽기 필터로만**
쓰이고(`api/concepts.py:137/187/229`·`api/me.py:1317`) 그 값을 *바꾸는* 엔드포인트가 없다.
즉 47의 잔여는 47의 문제가 아니라 **43(CMS)의 하위 항목**이다 → §3 D6에서 결론.

### 정정 ③ — 모듈 43 (관리자 CMS): "전무" → **코드 0 · 설계 정본 실재**

v1은 근거로 `api/`(18개 라우터, admin 없음)만 인용하고 **`docs/design/ui/`를 보지 않았다**.

| 항목 | r2 실측 |
|---|---|
| 코드 | 여전히 0 — `api/`에 admin 라우터 없음(현재 30개 모듈(라우터+`_` 헬퍼) 전수 확인) |
| **설계** | **정본 2종 실재** — `docs/design/ui/03_admin_console_plan.md`(운영 백오피스 vs 교사·학부모 대시보드 2갈래 분리·Control Center 4계층·22모듈 매핑·검수 큐·MVP=CLI/API 래핑 read-only 관측) · `04_admin_console_architecture.md`(Next.js 15 + FastAPI `/v1/admin/*` BFF + RBAC 선결·§2 원칙 4 "감사 없는 쓰기 액션 금지") |
| 추적 | `docs/design/ui/00_index.md:45`가 "RBAC 선결"을 미해결 항목 6번으로 이미 대장에 올려 뒀고, 그 항목은 `SEC-07`로 상환됐다 |

**판정**: v1의 결론(🚫 §2-④ 의도적 지연)은 **유지**한다 — 1인 capacity 가드는 그대로다. 그러나
근거 문장은 정정한다: "설계도 없다"가 아니라 **"설계는 정본으로 있고 구현만 지연"**이다. 이 구분이
중요한 이유는, 재판정 트리거가 발화했을 때 **처음부터 설계할 필요가 없다**는 뜻이기 때문이다.

### 정정 ④ — 모듈 45-⑤ (AI 출력 검사 中 금칙어·PII): 근거 갱신, 판정은 **악화**

| | v1 (07-29) | r2 실측 (08-03) |
|---|---|---|
| 근거 | "`coach_prose_leak_eval.py`만 존재 — 금칙어·PII 검사기는 없음" | 동일 + `SEC-11` `ops/log_scrubber.py` 착지했으나 **로그 평면 전용**(`logging.Filter`) — 학생에게 나가는 본문을 보지 않는다. `qa_pipeline.py:145` 스스로 "`log_scrubber`는 별도 축"이라 정확히 표기 |
| 판정 | ⚠️ 부분 | 🔴 **실갭으로 승격 → D4** — 전수 grep(`금칙어`/`banned_word`/`profanity`/`blocklist`)이 `qa_pipeline.py`의 *"검사 안 함" 선언 자체* 외에 **무일치** |

`coach_prose_leak_eval`이 무엇을 재는지 재확인: 결함주입 시험지로 **날조 정답·외래 등식 노출**을
Wilson 상한 게이트한다(교수학적 누설 축). 금칙어·PII와는 **다른 축**이다.

### 승계 (변화 없음 — 재대조 생략)

| 모듈 | v1 판정 | r2 |
|---|---|---|
| 42 저작권·출처 | 🔴 최대 갭 → D1 | ✅ **상환**(`ARCH-20`) — 단 그랜드파더 잔여 → D5 |
| 44 버전 관리 | ✅ 승계(git+코퍼스 버전+provenance) | 승계 유지 |
| 45 ①②③④ | ✅ / ✅ / ✅부분 / ✅ | 승계 유지 — `ARCH-21`이 7축으로 조립 |
| 45 자동 QA Pipeline | 🔴 최대 갭 → D2 | ⚠️ **조립은 됐으나 강제되지 않음** → D3 |
| 46 배포 · 49 백업 · 50 모니터링 | ✅ 상환(`OPS-01~04`) | 승계 유지 |

---

## §2. v1 §2 의도적 미채택 7건 — **재판정 트리거 도달 여부 실측**

> v1이 "협상 불가 근거"로 미채택한 7건 각각에 대해, v1 §5가 정한 **재판정 트리거가 발화했는지**를
> 이번 세션에 실측했다. 발화한 것이 있으면 §3으로 승격한다.

| # | 미채택 항목 | v1이 정한 트리거 | r2 실측 | 결론 |
|---|---|---|---|---|
| ① | 저작권 기간 필드 | 외부 라이선스 콘텐츠 실적재 | `data/corpus/*/_provenance.json` 20건 **전량 `pool: whymath-original`** — 외부 라이선스 0건 | **미도달 → 유지** |
| ② | 원본 링크 구조화 | (본문 미보유 정책 유지되는 한 영구) | `_METADATA_ONLY_SOURCES` 정책 변경 없음 | **유지** |
| ③ | 검수="사람이 봤는가" | (검증 권위 서열이 바뀌는 한 영구) | `superhuman_verification_standard.md` 변경 없음 | **유지** |
| ④ | CMS·RBAC 즉시 신설 | 결제 도입(Phase 2) or 운영자 2인+ or CS 문의 유입 | 결제 코드 **0건**(`토스`/`payment` grep 무일치)·운영자 1인 유지 | **미도달 → 유지** (단 §1 정정③대로 설계 정본은 실재) |
| ⑤ | 교육과정 Branch 버전 트리 | (Curriculum Overlay 불변식이 유지되는 한 영구) | 불변식 변경 없음 | **유지** |
| ⑥ | UI 스크린샷 골든 | Flutter 화면 수·회귀 빈도가 유지비용을 정당화 | 화면 **9개**(`*_screen.dart`/`*_page.dart`) — 골든 유지비 정당화 미달 | **미도달 → 유지** |
| ⑦ | 통계 이상치 검사 | `S3-01` 파일럿 완료 | `S3-01-pilot-cohort` **`status: todo`**(owner=kiki) — 실학생 응답 0 | **미도달 → 유지** |

**재심 결론: 7건 전부 미채택 유지.** 트리거가 하나도 발화하지 않았다. v1의 판정은 5일 후에도
전부 유효하며, 이번 r2의 신규 설계는 **미채택 항목의 번복이 아니라 D1·D2 구현이 만든 새 잔여**에서
나온다.

---

## §3. 설계 D3~D6 (v1의 D1·D2에 번호 연속)

### D3. QA 게이트를 fail-open에서 강제로 전환 — **최우선**

**갭**: `ARCH-21`이 만든 게이트가 CI에 있으나 **실제로는 아무것도 막지 않는다.** 무력화가 세 겹이다.

**⑴ `continue-on-error: true` (`.github/workflows/ci.yml:186`)**
첫 실행에서 `equivalence_canonicalize` 축이 코퍼스 전수 2,647건 중 **130건 위반**으로 `gate_fail`
했고, 그것이 실결함인지 `condition_dsl_violation`의 스코프 오탐인지는 교수학 판정이 필요해
`S3-28-canonicalize-answer-kind-scope-audit`로 등재됐다(`status: todo` — 등재 당시 `priority: 3`,
본 문서 §5에서 **2로 상향**).
그 판정 전까지 다른 PR의 CI를 막지 않으려고 이 스텝에만 임시 부여한 것 — **조치 자체는 옳다**
(리포트는 그대로 남고 무음 실패가 아니다). 문제는 **해제 조건이 어디에도 기계로 없다**는 것이다:
- `ci.yml`의 주석 한 줄
- `MEMORY.md` 2026-08-02 항목의 "S3-28 해소 시 이 줄을 제거해 강제 게이트로 전환"

둘 다 **사람의 기억에 의존**한다. CLAUDE.md는 이 형태를 명시적으로 금지한다 — *"'다음엔 조심한다'는
대책이 아니다 — 대책은 규칙·코드·태스크 중 하나의 형태여야 한다."* 그리고 *"상시 실패하는 fail-open
보호를 '보호 있음'으로 신뢰 금지."* 지금 `qa_pipeline`은 **매 실행 실패하는 fail-open**이다.

> 참고: `ci.yml`의 `continue-on-error`는 총 2건이나, `:852`(shellcheck warnings-only)는 **설계상
> 비차단**이라 이 갭에 해당하지 않는다. 임시 부여분은 `:186` 1건뿐이다.

**⑵ 트리거 경로 필터가 검사기 소스를 포함하지 않는다 (`ci.yml:96`)**
```
if printf '%s\n' "$files" | grep -qE '^(data/corpus/|\.github/workflows/ci\.yml$)'; then cp=true; fi
```
코퍼스가 바뀔 때만 돈다. **검사기 자신**(`harness/qa_pipeline.py`·조립 대상 7모듈·
`ops/provenance_audit.py`·`l3/equivalent/`)이 바뀌어도 안 돈다 — 판정 로직을 느슨하게 만드는
변경이 무검증 통과한다. 게이트가 자기 자신을 지키지 못하는 구조다.

**⑶ 배선 실재성 테스트가 "강제 여부"를 보지 않는다**
`tests/infra/test_qa_pipeline_wiring.py`는 5개 계약을 동결한다 — 스텝 존재·모듈 호출 형태·
`if: needs.changes.outputs.corpus`·`working-directory: .`·파서 위장 방지. **`continue-on-error`에
대한 assert는 없다.** ARCH-20/21이 학습한 교훈("존재함 ≠ 돌아감")의 **다음 단계가 빠져 있다**:
*돌아감 ≠ 막음*.

**설계**:

1. **`S3-28` priority 3 → 2 상향.** 이 태스크가 게이트 강제 전환의 **유일한 블로커**임을 백로그가
   드러내야 한다. 지금은 우선순위 3에 묻혀 있어 "판정 대기"가 무기한이 될 수 있다.
2. **신규 태스크 — 게이트 강제 전환 + 강제 상태 동결**:
   - S3-28 판정 결과 반영 → `ci.yml:186` `continue-on-error` 제거
   - `test_qa_pipeline_wiring.py`에 **6번째 계약** 추가: *"이 스텝에 `continue-on-error`가 없을 것"*.
     이후 누가 다시 fail-open으로 되돌리면 CI가 red가 된다. **"보호가 존재함"과 "보호가 강제됨"의
     구분을 기계화**하는 것이 이 계약의 정체다.
   - **변별력 의무**: 계약 추가 전 `continue-on-error`가 있는 현 상태에서 테스트가 실제로 red를
     내는지 실측한 뒤 제거한다(CLAUDE.md "변별력 없는 검증 스텝 금지" — 성공/실패 양쪽에서 같은
     값을 내는 검사는 위장).
3. **경로 필터 확장** — `cp=true` 조건에 검사기 소스 경로를 추가한다:
   `src/backend/whymath_backend/harness/`·`src/backend/whymath_backend/ops/provenance_audit.py`·
   `src/backend/whymath_backend/l3/equivalent/`. 근거: 코퍼스 변경 빈도가 높다는 게 원래 필터를
   좁힌 이유인데, **검사기 소스 변경은 드물다** — 비용 증가가 작고 방어 이익이 크다. (상시 실행
   전환이나 주 1회 스케줄은 채택하지 않는다 — 무거운 축의 비용 대비 이익이 불명확하고, 스케줄
   실행은 PR을 막지 못해 게이트로서 약하다.)

**경계**: 이 태스크는 S3-28의 **판정 자체를 대신하지 않는다**. 130건이 실결함인지 오탐인지는
교수학·콘텐츠 판정이라 임의로 고치지 않는다(v1 D2가 `ARCH-21` 세션에서 정한 경계 승계).

### D4. 학생 대면 출력의 금칙어·PII 검사 축 — 미측정 4축의 상환 일정화

**갭**: `qa_pipeline.py:142-147`의 `_NOT_MEASURED_AXES` 4종이 리포트에 "검사 안 함"으로 **정직하게**
나온다. 이 정직 표기는 CLAUDE.md "침묵 통과 금지"를 지킨 옳은 설계다. 그러나 **백로그 추적이
0건**이다 — MEMORY 2026-08-02 항목도 "향후 별도 태스크"라고만 적고 등재하지 않았다.
**정직 표기는 침묵 통과는 막지만 영구 미상환은 막지 못한다.**

**축별 판정** (4축 각각을 이번에 결론낸다 — "향후"를 없앤다):

| 축 | 판정 | 근거 |
|---|---|---|
| `ui_golden` | 🚫 **미채택 유지** | §2-⑥ 재심 — 화면 9개, 트리거 미도달. `_NOT_MEASURED_AXES` 사유 문자열에 §2-⑥ 참조를 넣어 "미구현(실측)"이 아니라 **"의도적 미채택"**임이 리포트에서 구분되게 한다 |
| `statistical_outlier` | 🚫 **잠금 유지** | §2-⑦ 재심 — `S3-01` todo. `S4-15`(실응답 난이도 루프)가 이미 추적 중 — **중복 등재 금지** |
| `performance` | 🚫 **축 오분류로 미채택** | `ops/service_health.py`는 `check_database`/`check_redis`/`check_llm_router`/`ServiceMetrics`/`evaluate_alerts` — **가동 중 서비스의 런타임 관측**이다. 배치 콘텐츠 QA 파이프라인이 소비할 수 있는 형태가 아니고, 억지로 배선하면 CI에 라이브 서비스 의존이 생긴다. 외부 틀의 ⑦은 **다른 평면**(OPS-01 관측성)에 이미 상환돼 있다 — qa_pipeline이 그것을 흡수할 이유가 없다 |
| **`banned_words_pii`** | 🔴 **실갭 — 태스크 등재** | 아래 |

**`banned_words_pii`가 실갭인 이유** (전수 grep 실측 — `금칙어`/`banned_word`/`profanity`/
`blocklist`/`forbidden_word` 가 `qa_pipeline.py`의 *"검사 안 함" 선언 자체* 외에 무일치):

- `coach_prose_leak_eval` = **날조 정답·외래 등식 노출**(교수학적 누설). 다른 축.
- `SEC-11` `ops/log_scrubber.py` = **로그 평면**(`logging.Filter`). 학생에게 나가는 본문을 보지 않는다.
- `judge_filter`(`api/coach.py:684`) = **오개념 후보 선별**. 안전 필터 아님.

즉 **학생에게 실제로 전달되는 LLM 산문에 부적절 표현·타인 PII가 섞여도 잡는 것이 없다.**
CLAUDE.md 의사결정 우선순위 **1위(학생 안전·웰빙)** 축인데 추적조차 없는 상태다.

**설계 방향** (태스크 acceptance의 골격 — 상세 설계는 착수 세션):
- **소비처 우선** — dead code 금지. 검사기를 만들되 **`qa_pipeline`의 8번째 축**으로 즉시 조립하고,
  실시간 서빙 경로 부착 여부는 별도 판단(배치 검사가 1단계).
- **결정론 우선** — 사전(사전 기반 금칙어 목록) + 정규식(연락처·이메일·주민번호 형태) 결정론
  검사가 1차. LLM 판정은 도입하지 않는다(비용·비결정성·자기승인 금지).
- **PII는 두 방향** — ⑴ 학생 자신의 PII가 출력에 반사되는가 ⑵ **타인의** PII가 생성되는가.
  `log_scrubber`의 패턴 자산(이메일·한국 휴대전화·JWT 등)을 **재사용**한다 — 재구현 금지.
- **게이트는 Wilson 단측 상한** — 점추정 금지(초인간 검증 기준 v1). 기존 `wilson.py` 재사용.
- **`_NOT_MEASURED_AXES`에서 제거**하고 실축으로 승격 — 리포트가 자동으로 정직해진다.

### D5. provenance 그랜드파더 면제의 무기한화 방지

**갭**: `ops/provenance_audit.py:69-75` `_KNOWN_GAPS`가 5종 코퍼스를 면제 중이다 —
`problem_bank_{conceptual,generated,killer,misconception_mc,rephrased}_v0`. 이들은 **학생에게 실제
노출되는** 문제은행이다. v1 D1은 "`S3-11`이 다른 브랜치에서 이미 done이니 머지되면 자동 해소"로
넘겼다. **5일이 지났고 `S3-11-problem-bank-data-card`는 여전히 `status: todo`**(그 브랜치 미머지).

이 패턴은 2026-07-30 결정 로그의 **미병합 브랜치 9일 고립 사고**와 동형이다 — "다른 곳에서 이미
됐다"는 판단이 트렁크에 착륙하지 않은 채 시간이 흐르는 형태. 그리고 ARCH-20의 그랜드파더 주석은
해제를 **손 유지보수**로 명시했다(자동 아님) — 손 유지보수는 잊히면 영구 면제가 된다.

**설계 — (a)와 (b) 동시**:

**(a) `S3-11` 회수 여부 판정 + 실행.** 그 브랜치가 살아 있는지, 회수할 diff가 무엇인지 실측하고
회수한다. 선례: `claude/shadow-data-s3-pilot-nh5kbz` Stage 1 회수(2026-07-30). 회수하면 `_KNOWN_GAPS`
5종이 즉시 비고 provenance 게이트가 **전 학생 노출 코퍼스**에 실제로 적용된다.

**(b) 그랜드파더 계약에 추적 근거를 필수화.** `_KNOWN_GAPS`의 값이 자유 문자열이 아니라 **추적
태스크 ID를 반드시 포함**하게 하고, `test_provenance_audit.py`가 다음을 동결한다:
1. 모든 항목이 실존하는 백로그 태스크 ID를 참조할 것
2. 그 태스크가 `done`인데 항목이 남아 있으면 **red**

자동 해제는 아니다(면제 해제는 사람 판단). 그러나 **방치는 구조적으로 막힌다** — (a)가 없어도
(b)만으로 "잊힌 면제"가 CI에서 드러난다. 이 부류(면제·유예가 조용히 영구화되는 패턴)는 이
저장소에 grandfather 선례가 이미 여럿이라 계약화 가치가 있다.

### D6. `content_provenance`/`generation_log` 실영속 · 콘텐츠 운영 감사 — **재판정: 미채택 유지**

v1은 이 둘을 "감사 CLI(D1)로 1단계 충분"으로 스코프 밖에 뒀다. r2에서 소비처가 생겼는지 실측했다.

| 항목 | 실측 (08-03) | 판정 |
|---|---|---|
| ORM `ContentProvenance`/`GenerationLog`(`db/models/provenance.py:45/131`) 쓰기 경로 | **여전히 0건** — 모델 파일 밖 참조는 전부 **동명의 Pydantic 스키마**(`schema/provenance.py`)이지 ORM 행이 아니다. `l3/pregenerate/provenance_bridge.py`도 인메모리 변환 어댑터일 뿐 DB에 넣지 않는다 | 🚫 **미채택 유지** |
| 콘텐츠 운영 액션 감사(승인·반려·플래그) | **감사할 액션 자체가 없다** — `review_status`는 전 API에서 읽기 필터 전용, 값을 바꾸는 엔드포인트 0 | 🚫 **미채택 유지 — 43의 하위 항목** |

**결론**: 47(감사 로그)의 잔여는 **독립 갭이 아니라 43(관리자 CMS)의 부분집합**이다. 검수 승인 UI가
없으므로 승인 감사도 있을 수 없다. `04_admin_console_architecture.md` §2 원칙4("감사 없는 쓰기 액션
금지")가 이미 CMS 설계에 감사를 **동반 조건으로 못박아** 뒀으므로, CMS 재판정 트리거(§2-④)가
발화할 때 함께 열린다. **별도 태스크를 만들지 않는다**(백로그 오염 방지).

ORM 실영속도 동일 — 소비처(재현성 감사 요구)가 실증되지 않았다. `ARCH-21` 리포트가 실행 흔적을
만들기 시작했으나 그것은 **JSON 리포트 산출물**이지 DB 영속 요구가 아니다.

---

## §4. 정직한 공백 — 지금 하지 않는 것 (v1 §4 갱신)

| 공백 | 사유 | 해소 시점 |
|---|---|---|
| UI 스크린샷 골든 | §2-⑥ 재심 미도달(화면 9개) | 화면 수·회귀 빈도가 유지비용을 정당화할 때 |
| 통계 이상치 검사 | §2-⑦ 재심 미도달(`S3-01` todo) | `S4-15`가 추적 — 신규 등재 없음 |
| **성능 검사의 QA 파이프라인 통합** | **축 오분류** — 런타임 관측(`OPS-01`)이 이미 담당하는 평면. qa_pipeline이 흡수하면 CI에 라이브 의존이 생긴다 | **영구 미채택**(발화조건 없음 — 틀의 분류를 따르지 않는다) |
| 관리자 CMS · 콘텐츠 운영 감사 · RBAC 확장 | §2-④ 재심 미도달(결제 0·운영자 1인). **설계는 정본 실재**(`docs/design/ui/03·04`) | 결제 도입 or 운영자 2인+ or CS 문의 유입 |
| `content_provenance`/`generation_log` 실영속 | 소비처 미실증(D6 재판정) | 재현성 감사 요구가 실측될 때 |
| 저작권 기간·사용범위 세분 필드 | §2-① 재심 미도달(pool 전량 whymath-original) | 외부 라이선스 콘텐츠 실적재 결정 |

---

## §5. 실행 — 백로그 등재 · 중복 회피 대장

### 신규 등재 (실제 ID는 `backlog.py add`가 배정 — 번호 추론 금지, HARN-10)

| 설계 | 내용 | stage/priority |
|---|---|---|
| **D3** | QA 게이트 강제 전환 — `continue-on-error` 제거 + wiring 6번째 계약(강제 상태 동결) + 경로 필터에 검사기 소스 추가 | S3 / 2 · `S3-28` 의존 |
| **D4** | 학생 대면 출력 금칙어·PII 검사 축 — `qa_pipeline` 8번째 축 승격, `log_scrubber` 패턴 재사용, Wilson 상한 게이트 | S3 / 2 |
| **D5** | provenance 그랜드파더 만료 계약 + `S3-11` 회수 판정 | S3 / 2 |

### 기존 태스크 수정

- `S3-28-canonicalize-answer-kind-scope-audit` — **priority 3 → 2**(D3의 유일 블로커임을 노출).

### 중복 등재 금지 대장 (이번에 등재하지 **않는** 것과 그 소유자)

| 주제 | 기존 추적 |
|---|---|
| canonicalize 130건 판정 | `S3-28`(수정만, 신규 아님) |
| 문제은행 사이드카·데이터 카드 | `S3-11`(D5가 회수 여부만 판정 — 재구현 아님) |
| 실응답 통계·난이도 루프 | `S4-15` · `S3-01` 게이트 |
| 배포·백업·모니터링·SLO(46·49·50) | `OPS-01~04`(전부 done) |
| 로그 PII 스크러버 | `SEC-11`(done) — D4는 **출력 평면**이라 다른 축 |
| Role·인가 게이트 | `SEC-07`(done) |
| 관리자 CMS·RBAC 확장(43·48) | `docs/design/ui/03·04` 설계 정본 + §2-④ 트리거 대기 — **백로그 미등재가 의도** |
| 콘텐츠 운영 감사(47 잔여) | 43의 하위 항목(D6 결론) — 별도 등재 없음 |

### 재판정 트리거 (v1 §5 승계 + 갱신)

| 항목 | 트리거 |
|---|---|
| 43 CMS · 48 RBAC 확장 | 결제 도입(Phase 2) or 운영자 2인+ or CS 문의 유입 개시 |
| 저작권 기간·사용범위 세분(§2-①) | 외부 라이선스 콘텐츠 실적재 결정(= `pool != whymath-original` 첫 등장) |
| UI 골든(§2-⑥) | Flutter 화면 수·회귀 빈도 실측 |
| 통계 이상치(§2-⑦) | `S3-01` 파일럿 완료 |
| ORM provenance 실영속(D6) | 재현성 감사 요구 실측 |

---

## 부록 — 실측 근거 (2026-08-03, 브랜치 `claude/whymath-eos-review-iyev91`, HEAD `9257567`)

| 주장 | 확인 명령·위치 |
|---|---|
| v1 D1·D2 구현 완료 | `backlog/tasks/ARCH-20-*.yaml`·`ARCH-21-*.yaml` 둘 다 `status: done` |
| QA 게이트 fail-open | `.github/workflows/ci.yml:186` `continue-on-error: true`(스텝 `:178`) |
| 트리거 필터가 검사기 소스 미포함 | `.github/workflows/ci.yml:96` `grep -qE '^(data/corpus/\|\.github/workflows/ci\.yml$)'` |
| wiring 테스트에 강제 계약 없음 | `tests/infra/test_qa_pipeline_wiring.py` — `test_*` 5개, `continue-on-error` assert 0 |
| 미측정 4축 | `src/backend/whymath_backend/harness/qa_pipeline.py:142-147` |
| 금칙어·PII 검사기 0 | `grep -rln "금칙어\|banned_word\|profanity\|blocklist\|forbidden_word" src/` → `qa_pipeline.py` 1건(선언 자체) |
| 그랜드파더 5종 | `src/backend/whymath_backend/ops/provenance_audit.py:69-75` |
| `S3-11` 미착륙 | `backlog/tasks/S3-11-problem-bank-data-card.yaml` `status: todo` |
| Role v0 실재 | `src/backend/whymath_backend/schema/enums.py:1163` · `api/_auth.py:96,123` |
| 감사 2종 실가동 | `db/models/audit.py:37,77` · `privacy/audit.py:79,100,124` · `api/me.py:307` · `privacy/erasure.py:198` |
| 콘텐츠 운영 감사 0 | `review_status` 쓰기 엔드포인트 grep 무일치 — `api/`는 읽기 필터만(`concepts.py:137,187,229`) |
| ORM provenance 쓰기 0 | `db/models/provenance.py:45,131`의 클래스명 전수 역참조 → 모델 파일 밖 히트는 전부 동명 Pydantic 스키마 |
| admin 라우터 0 | `ls src/backend/whymath_backend/api/*.py` 30개 — admin 라우터 없음 |
| CMS 설계 정본 실재 | `docs/design/ui/03_admin_console_plan.md`·`04_admin_console_architecture.md`·`00_index.md:17,18,45` |
| pool 전량 자체생성 | `grep -h '"pool"' data/corpus/*/_provenance.json \| sort \| uniq -c` → `20 "pool": "whymath-original"` |
| 결제 코드 0 | `grep -rln "토스\|tosspayments\|payment" src/backend/` 무일치 |
| Flutter 화면 9 | `find src/mobile/lib -name "*_screen.dart" -o -name "*_page.dart" \| wc -l` |
| `S3-01` 미완 | `backlog/tasks/S3-01-pilot-cohort.yaml` `status: todo`·`owner: kiki` |
| `service_health` 런타임 성격 | `ops/service_health.py:91,148,180,280,364` — `check_database`/`check_redis`/`check_llm_router`/`ServiceMetrics`/`evaluate_alerts` |
