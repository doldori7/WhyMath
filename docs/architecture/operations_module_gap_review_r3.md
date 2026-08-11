# 운영(Operations) 모듈 — 외부 EOS 틀 대조 **3차 재점검(r3)** (2026-08-11)

> **범위**: v1(2026-07-29)·r2(2026-08-03)와 **동일한 외부 참고 문서**(『0단계 운영(EOS)』
> 핵심 모듈 42~45: 콘텐츠 저작권·출처 관리 · 관리자 CMS · 버전 관리 · 품질 검증(QA) 엔진
> \+ 확장 제안 46~50: 배포 · 감사 로그 · RBAC · 백업·복구 · 모니터링·알림 —
> **WhyMath 전용이 아닌 일반적 틀**, Kiki 제공)를 **r2 이후 8일간의 코드베이스 변화**와
> 다시 대조한 기록. 같은 외부 틀 대조 시리즈의 **13번째** 자매편.
>
> **형식**: 처음부터의 재대조가 아니라 **델타 재점검**이다(r2 §0 승계). 변화 없는 판정은
> 승계하고, ⑴ stale해진 판정 칸 ⑵ r2의 설계가 구현된 뒤 남은 실공백 ⑶ **이전 2회가 보지
> 않은 평면**만 다룬다. 판정 기호: ✅ 충족·초과 / ⚠️ 부분 / 🔴 실갭 → D /
> ⏸ 기존 추적 승계 / 🚫 의도적 미채택. D 번호는 r2에 이어 **D7**부터.
>
> **결론 3줄**:
> 1. **42(저작권)·45(검사기)는 r2 이후 오히려 강화됐다** — `ARCH-24`(금칙어·PII 축 8)·
>    `ARCH-25`(그랜드파더 만료 계약·`_KNOWN_GAPS` 빈 dict)·`PB-03`(기본 CAT 노출 경로에
>    저작권 게이트 실집행)이 전부 착지. r2가 지목한 D4·D5는 상환됐다.
> 2. **최대 갭 = QA 게이트가 9일째 fail-open이고, 이제 블로커가 2개다.** r2 D3의 `ARCH-23`은
>    미착수이며, r3가 **두 번째 블로커**를 실측 발견했다 — 축 9(`defect_report_intake`)가
>    `data-pipeline` 잡에서 **상시 `error`**(Postgres 서비스 부재)라 `continue-on-error`를
>    그대로 제거하면 CI가 상시 red가 된다. 같은 fail-open의 **2회 연속 관측** → **D7**.
> 3. **46·49·50의 "상환 승계" 판정을 정정한다.** v1·r2는 `OPS-01~04`가 done인 것만 보고
>    ✅로 승계했으나, **런북 3종이 스스로 "이건 안 했다"고 적어 둔 잔여 25종의 백로그 추적이
>    0건**이었다 — r2 자신이 D4에서 세운 논리(*"정직 표기는 침묵 통과는 막지만 영구 미상환은
>    막지 못한다"*)의 **런북 평면 재발** → **D9**.

관련 정본: `operations_module_gap_review.md`(v1 — 판정 근거 원본) ·
`operations_module_gap_review_r2.md`(r2 — 이 문서의 모체) ·
`docs/design/ui/03_admin_console_plan.md`·`04_admin_console_architecture.md`(43 설계 정본) ·
`docs/standards/incident_response_slo.md`·`db_backup_dr_runbook.md`·`deployment_cd_runbook.md`
(46·49·50 런북 정본 — **본 문서가 그 §정직한 공백을 처음으로 대장에 연결한다**) ·
`MEMORY.md` 결정 로그(2026-07-29 v1 · 2026-08-03 r2 · 2026-08-11 본 문서).

---

## §0. 재점검 사유 — 왜 r2를 덮어쓰지 않고 r3를 새로 쓰는가

**용어(v1 §0·r2 §0 승계)**: 첨부 문서의 "EOS"는 **외부 참고 프레임워크의 명칭**이고,
`dev_constitution.md` §0이 폐기한 대외 정체성 어휘 "EOS"와는 **동명이의**다. 이 저장소가
스스로를 EOS로 선언하는 것과 무관하다. **새 계층(L8)도 만들지 않는다** — 운영은 CLAUDE.md가
규정한 **횡단 관심사**다.

**r2를 in-place 수정하지 않는 이유**: r2는 완료 태스크 `ARCH-24`·`ARCH-25`의 `notes`가
가리키는 **정본 참조 대상**이다. 완료된 태스크의 판정 근거를 소급 변조하면 "왜 그렇게
결정했는가"의 기록이 사라진다. `arch_audit_2026-07-09.md → _r2/…/_r8` 리비전 파일 관례를
따르며, r2에는 이 문서로 오는 **배너 1줄**만 추가했다.

**재점검이 필요했던 실제 사유 3종** (전부 이번 세션 실측):

| 사유 | 실측 |
|---|---|
| ⑴ r2 판정표 stale | 08-03 이후 `PB-03`·`RPT-01`·`OPS-22~25`가 착지해 42·45·47 칸이 사실과 달라졌다 |
| ⑵ r2 D3의 무착지 | `ARCH-23` 9일째 `todo` — 그리고 그 acceptance가 **실행 불가능한 상태**임이 이번에 드러났다(두 번째 블로커) |
| ⑶ **이전 2회가 보지 않은 평면** | v1·r2는 46·49·50을 **태스크 상태**로만 판정했다. **런북 본문**을 읽지 않아 25종 자인 공백이 2회 연속 승계로 통과했다 |

---

## §1. r2 판정표 정정 (바뀐 칸만 — 나머지는 승계)

### 정정 ① — 모듈 42 (저작권·출처): ✅ 상환 → ✅ **강화**

| | r2 (08-03) | r3 실측 (08-11) |
|---|---|---|
| 그랜드파더 | `_KNOWN_GAPS` 5종 면제 → D5 | **`_KNOWN_GAPS: dict[str, GrandfatherEntry] = {}`**(`ops/provenance_audit.py:97` — 빈 dict). `ARCH-25`가 `S3-11`을 회수(`4293da24`)해 면제가 전부 해소 |
| 사이드카 커버리지 | 20종 | **26종 전량 보유·전량 `pool: whymath-original`**(코퍼스가 6종 늘었는데 100% 유지 — 게이트가 실제로 신규 코퍼스를 잡고 있다는 증거) |
| **런타임 집행** | `l6/_shared.py:141` `is_exposable` 호출자에 `api/me.py` **0건**(주 노출 경로에 미배선) | **`PB-03`(done, 08-08)이 기본 CAT 후보 SQL에 `source_type` 게이트를 부착** — 학생 앱이 실제로 쓰는 경로가 닫혔다. 아울러 `review_status`를 측정 게이트 판정으로 결정론 각인하고 `is_review_cleared`를 **법적 축과 분리해** 배선 |

**판정**: ✅ **강화**. r2의 D5는 완전 상환.

### 정정 ② — 모듈 45-⑤ (금칙어·PII): 🔴 실갭 → ✅ **상환**

`ARCH-24`(done)가 `harness/banned_words_pii_eval.py`를 신설해 `qa_pipeline` **축 8**로 조립했다.
사전 기반 금칙어 + `ops/log_scrubber.PII_SHAPE_PATTERNS` **재사용**, `self_reflection`/`third_party`
별도 카운터, Wilson 단측 상한 게이트. r2 D4의 설계 방향을 그대로 이행했다.

**남은 경계(갭 아님·§4로 이관)**: 이 축은 **정적 저작 코퍼스 배치 스캔**이다. 런타임에 생성되는
코치 산문에는 부착되지 않았고, `ARCH-24` acceptance ⑤가 **"배치가 1단계·실시간 부착은 별도 판단"**
으로 경계를 명시했다. 분류 함수는 순수·재사용 가능하게 분리돼 있어 부착 시 새 판정 로직이 불요하다.

### 정정 ③ — 모듈 45 (QA Pipeline): ⚠️ 강제 안 됨 → ⚠️ **유지 + 악화** → **D7**

축이 **7 → 9**로 늘었고(축 8 `ARCH-24`·축 9 `RPT-01`), 그만큼 게이트가 커졌는데
`continue-on-error: true`는 **그대로**다(`ci.yml:192`). 커진 게이트가 여전히 아무것도 막지 않는다.
그리고 **새로 늘어난 축 9가 두 번째 블로커를 만들었다** → §3 D7.

### 정정 ④ — 모듈 47 (감사 로그): ⚠️ 부분 → ⚠️ **부분 + 신규 잔여** → **D11**

| 항목 | r3 실측 |
|---|---|
| 감사 테이블 | **3종**(`DeletionAudit`·`PrivacyAudit` + **`DefectReport`** 신규, RPT-01) |
| writer 배선 | 3종 중 **2종**(`record_export_audit`·`record_consent_change_audit`). `record_admin_access_audit`는 **호출부 0곳** — 8개 grep 히트가 전부 정의·재수출·docstring |
| **신규 잔여** | **`DefectReport`에 읽기 경로가 없다** — 접수(`POST`)만 있고 조회 CLI·admin 표면 0건. 운영자의 유일한 관측이 `qa_pipeline` 축 9의 **행 수 카운트** → **D11** |

`record_admin_access_audit`의 호출부 0은 **43(CMS)의 부분집합**이라는 r2 D6 결론을 승계한다
(관리자 경로 자체가 없으므로 관리자 접근 감사도 있을 수 없다). 그러나 **D11은 다르다** —
결함 신고는 채널이 *이미 열려 실가동 중*인데 읽는 쪽만 없다.

### 정정 ⑤ — 모듈 48 (RBAC): ⚠️ 부분 → ⚠️ **부분 + 인가 데드락 실측**

`require_content_admin`(`api/_auth.py:123`)이 콘텐츠 CUD 6라우터를 지키지만
**`Role.CONTENT_ADMIN`을 부여하는 코드가 main에 0건**이다(`.role =`/`role=Role.` 전수 grep 0).
즉 그 6라우터는 현재 **아무도 통과할 수 없다(전건 403)**. 구현은 미머지 브랜치에 고립 →
**§6 에스컬레이션**(신규 태스크 없음 — `ADMIN-01`이 이미 대장에 있다).

### 정정 ⑥ — 모듈 46·49·50 (배포·백업·모니터링): ✅ 상환 승계 → 🔴 **승계 판정 정정** → **D9**

v1·r2가 `OPS-01~04` **태스크 상태**만 보고 ✅로 넘긴 칸이다. 런북 본문을 읽으니 그 문서들이
**스스로 "안 했다"고 적어 둔 항목이 25종**이고 **백로그 추적이 0건**이었다. 상세 → §3 D9.

### 승계 (변화 없음 — 재대조 생략)

| 모듈 | 판정 | 승계 근거 |
|---|---|---|
| 43 관리자 CMS | 🚫 의도적 지연(설계 정본은 실재) | §2-④ 트리거 미도달 재확인 |
| 44 버전 관리 | ✅ 승계 | DSL 축만 진짜 버전드(`unit_spec` 복합 PK `(unit_id, unit_version)`)·git+코퍼스 접미가 정본. diff/rollback 부재는 §2-⑤ |
| 45 ①②③④⑦ | ✅ / ✅ / ✅부분 / ✅ | `ARCH-21` 조립 유지 |

---

## §2. 미채택 7건 — **트리거 3차 재심** (전건 실측)

| # | 미채택 항목 | 트리거 | r3 실측 (08-11) | 결론 |
|---|---|---|---|---|
| ① | 저작권 기간 필드 | 외부 라이선스 콘텐츠 실적재 | **26종 전량 `pool: whymath-original`** — 외부 라이선스 0건 | **미도달 → 유지** |
| ② | 원본 링크 구조화 | (본문 미보유 정책 유지되는 한 영구) | `_METADATA_ONLY_SOURCES` 정책 불변 | **유지** |
| ③ | 검수="사람이 봤는가" | (검증 권위 서열이 바뀌는 한 영구) | `superhuman_verification_standard.md` 불변. 오히려 `PB-03`이 **측정 게이트 판정만** 각인(사람 입력 경로 0)해 서열을 강화 | **유지·강화** |
| ④ | CMS·RBAC 즉시 신설 | 결제 도입 or 운영자 2인+ or **CS 문의 유입** | 결제 코드 **0건**(`src/backend/` grep 무일치·README 언급만)·운영자 1인. **CS 축은 부분 발화** — `RPT-01`로 학생 신고가 실제로 들어올 수 있게 됐다. 단 이는 **CMS 전체가 아니라 판독 1건**을 요구한다 → **D11로 최소 대응** | **미도달 유지**(CMS 신설 안 함) |
| ⑤ | 교육과정 Branch 버전 트리 | (Curriculum Overlay 불변식 유지되는 한 영구) | 불변식 불변 | **유지** |
| ⑥ | UI 스크린샷 골든 | 화면 수·회귀 빈도가 유지비용 정당화 | 화면 **9개** 유지 | **미도달 → 유지** |
| ⑦ | 통계 이상치 검사 | `S3-01` 파일럿 완료 | `S3-01` **`todo`**(owner=kiki) — 실학생 응답 0 | **미도달 → 유지** |

**재심 결론: 7건 전부 미채택 유지.** ④만 **부분 발화**했고, 그에 대한 응답은 CMS 신설이 아니라
**판독 CLI 1개**(D11)다 — 트리거가 요구하는 최소 표면만 연다.

---

## §3. 설계 D7~D11 (r2의 D3~D6에 번호 연속)

### D7. QA 게이트 fail-open **9일째** — 블로커가 1개가 아니라 2개 → `ARCH-23` acceptance 보강

**갭 ⑴ — 지속**: r2 D3이 지목한 `continue-on-error: true`가 그대로다(`ci.yml:192`).
유일 블로커로 지목돼 priority 2로 상향된 `S3-28`도 여전히 `todo`. CLAUDE.md는
*"상시 실패하는 fail-open 보호를 '보호 있음'으로 신뢰 금지 — 같은 실패 경고가 환경에서
**반복 관측되면(2회+)** 그 보호는 상시 무력 상태"*라고 규정한다. **r2가 1회차, r3가 2회차**다.

**갭 ⑵ — 신규 실측(r2가 몰랐던 두 번째 블로커)**: 축 9(`defect_report_intake`)는 커밋된 코퍼스
파일이 아니라 **DB**를 읽는데, `data-pipeline` 잡에는 **Postgres 서비스가 없다**(그 잡 범위에
`services:` 블록 0건). `_run_axis_safely`가 이를 `"error"`로 격리하고,
`qa_pipeline._aggregate`가 **`"gate_fail"`과 `"error"`를 똑같이 실패로 집계**하므로 exit 1이다.

> 즉 **`ARCH-23`의 acceptance를 문자 그대로 수행하면(= `continue-on-error` 제거)
> `S3-28`이 해소돼도 CI가 상시 red가 된다.** 태스크가 실행 불가능한 상태로 등재돼 있었다.

**설계 — 신규 태스크가 아니라 `ARCH-23` acceptance 보강**(등재 완료):
1. 제거 **전에** 축 9의 환경 판정을 분리한다. 3안 중 착수 세션이 실측 택일 —
   **(a) 권장**: DB **도달 불가**를 `no_snapshot`(정당 상태·집계 제외)으로 강등하되
   **"테이블 없음"(수집 경로 미배선)과는 계속 구분**해 현 이중 회계를 3중으로 넓힌다.
   비용 0이고, "DB 없는 실행 환경"과 "수집 경로가 죽음"은 **실제로 다른 사태**다.
   (b) 잡에 Postgres 서비스 추가. (c) 축 9를 `backend-migrations` 잡으로 이설.
2. 기존 acceptance(6번째 wiring 계약·경로 필터에 검사기 소스 추가)는 유지.
3. **변별력 의무 유지** — 제거 *전* 상태에서 새 계약이 실제 red를 내는지 실측 후 제거.

**경계**: `S3-28`의 교수학 판정(130건이 실결함인지 오탐인지)은 여전히 대신하지 않는다.

### D8. **"배선됨 ≠ 강제됨"** — 교훈 사슬의 마지막 고리를 일반화 (신규 `OPS-29`)

**갭**: 이 저장소는 같은 교훈을 세 단계로 학습해 왔고, **마지막 고리만 기계화가 없다**.

| 단계 | 질문 | 기계화 |
|---|---|---|
| 존재함 ≠ 돌아감 | 이 테스트가 CI에서 실제로 실행되는가 | ✅ `test_test_suite_wiring.py`(`OPS-10`) |
| 선언함 ≠ 배선됨 | 이 공급 표면을 소비하는 쪽이 있는가 | ✅ `ops/declared_unwired_audit.py` 4축(`OPS-22`) |
| **돌아감 ≠ 막음** | **이 게이트가 실제로 PR을 막는가** | 🔴 **없음** |

r2 D3이 *"돌아감 ≠ 막음"*이라 **이름까지 붙였으나** `qa_pipeline` 1건에만 적용했고, 그 1건조차
`ARCH-23` 미착수라 **아직 아무 데도 착지하지 않았다**. 실측: `tests/infra/`의 `*_wiring.py`
**11개 중 `continue-on-error`를 assert하는 것 0건**. 비차단 스텝은 현재 **2건**
(`:192` qa_pipeline 임시 · `:923` shellcheck 설계상) — **세 번째가 조용히 늘어도 아무도 모른다**.

**설계 — `OPS-22`의 분류 계약을 *강제 상태* 축으로 이식**(새 발명 아님):
- 모든 비차단 스텝은 의도를 **선언**한다: `by-design:<사유>` 또는 `pending-task:<id>`.
- 선언 없는 `continue-on-error`(및 게이트 판정을 `|| true`로 삼키는 스텝) → **미분류 exit 1**.
- **`ARCH-25` 그랜드파더 만료 계약 재사용** — `pending-task:<id>`는 그 태스크가 실재하고
  `status != done`일 때만 유효. **done인데 남아 있으면 red**(= "게이트를 다시 켜라"는 신호).
- 착지: `tests/infra/`(hermetic — `infra-contracts` 잡이 이미 `tests/infra` 전량 실행).
- **변별력 의무(양방향)**: 선언 없는 스텝 1건 주입 → red, 되돌리면 green을 **둘 다** 실측.

**왜 과공학이 아닌가**: 대상이 2건이라 초기 대장이 2줄이고, **예방 성질이 본체**다 —
세 번째 fail-open이 선언 없이 들어오면 그 PR이 막힌다. `test_slo_contract.py`(문서 표 파싱)와
`declared_unwired_audit`(분류 계약)의 **검증된 패턴 조합**이다.

**경계**: `ARCH-23`(qa_pipeline의 실제 해제)을 대신하지 않는다. `OPS-29`는 *계약*을 만들고
qa_pipeline 스텝을 `pending-task:ARCH-23`으로 등재해 유예를 명시한다.

### D9. 런북 3종이 자인한 공백 **25종**의 백로그 추적 0건 → 46·49·50 승계 판정 정정

**갭**: v1·r2 모두 46·49·50을 *"`OPS-01~04` done → ✅ 상환"*으로 승계했다. **그 판정은 태스크
상태만 봤다.** 런북 본문의 §정직한 공백을 읽으면:

| 런북 | 자인 공백 | 추적 |
|---|---|---|
| `incident_response_slo.md` §6 | **11종** — 외부 업타임 프로브 미도입 · 페이지 알림 채널 미배선 · 지표 영속화 없음 · 경로별 미분해 · 다중 워커 해석 붕괴 · 강등 회계 미노출 · 온콜 0 … | **0건** |
| `db_backup_dr_runbook.md` §6 | **4종** — 오프사이트 사본 부재 · 백업 파일 암호화 미도입 · WAL/PITR 없음 · 스케줄 로그온 의존 | **0건** |
| `deployment_cd_runbook.md` §8 | **10종** — **실 배포 실행 0회** · 프로덕션 호스트 없음 · 레지스트리 없음 · TLS 없음 · staging 전용 호스트 없음 · **environment 승인 규칙 미등록** · `whymath-pg` 이관 미실시 … | **0건** |

이것은 **r2 자신이 D4에서 세운 논리의 재발**이다 — *"정직 표기는 침묵 통과는 막지만 영구
미상환은 막지 못한다."* r2는 그 논리를 `qa_pipeline`의 `_NOT_MEASURED_AXES` 4축에만 적용하고
**런북 평면에는 적용하지 않았다.** 런북의 정직함이 오히려 **판정을 통과시키는 근거**로 쓰였다.

**설계 — 25종 전수 트리아지 후 실갭만 등재**(백로그 244건 오염 방지):

**🔴 실갭 → 태스크 2건 (등재 완료)**

1. **`OPS-30` 관측의 마지막 1홉** —
   ⑴ **알림 발송 채널 0**: `ops/service_health.py:401` `AlertLogNotifier`가 breach를
   `logger.warning`으로만 쓴다(Slack/webhook/smtp/pagerduty **전수 grep 0건**). 런북이
   *"로그를 보고 있지 않으면 알림이 아니다"*라고 자인한다. `OPS-01`의 정교한 임계·상태전이
   억제 판정이 **사람에게 도달하지 않는다**.
   ⑵ **외부 업타임 프로브 0**: *"죽은 서버는 자기 죽음을 보고하지 못한다"* — 이것이 SLO
   **S4(학습창 가용성 99%)가 ❌ 미측정인 근본 원인**이다.
   두 홉 모두 기존 자산(`Alert`·`AlertLogNotifier` 옆 notifier 추가) 재사용이라 판정 로직 신설 0.

2. **`OPS-31` 백업의 미성년 PII 축** — 백업 파일 암호화 **규칙만 있고 도구 절차 없음**
   \+ 오프사이트 사본 부재(**prod와 같은 디스크**) + **스케줄 자동화 0건**
   (`schtasks`/`crontab`/systemd timer 전수 무일치 — 사람이 손으로 돌린다·로그오프 시 회차 누락).
   의사결정 우선순위 **2위(법적·윤리적 준수)** 축이다.

**🚫 의도적 미채택 → §4 + §5** — WAL/PITR · TLS · 레지스트리 · 프로덕션 호스트 · 무중단 배포 ·
staging 전용 호스트(전부 **호스트 미프로비저닝 종속**) · 경로별 분해 · 다중 워커 합산
(단일 워커 단계에선 무의미) · 온콜(1인 구조).

**👤 Kiki 소유 행동 → `gates.yaml` 등재 (완료)** — 실측: **기존 게이트 7건이 전부 콘텐츠/개발
축이고 운영 축 게이트가 0건**이었다(대장 자체의 공백). 태스크가 아니라 사람 행동이므로
`backlog.py gates add`(HARN-18) 경유로 3건 등재:
`G-deploy-environment-approval` · `G-backup-restore-rehearsal` · `G-backup-offsite-move`.

**⏸ 에스컬레이션만** — `deploy.yml` **실 호스트 실행 0회**. `OPS-03`은 done이지만 배포 경로는
*한 번도 돈 적 없는 골격*이고 **파일 자신이 이를 자인한다**(`deploy.yml:3-10`). 이는 D8이
기계화하는 사슬의 **배포 평면 변종**이나, 해소에 **미프로비저닝 인프라가 선결**이라 지금은
§5 트리거 등재만 한다(없는 호스트에 배포 태스크를 만들면 그 자체가 dead task다).

### D10. 백엔드 의존성 선언↔사용 게이트의 **비대칭** (신규 `OPS-32`)

**갭**: `src/backend/pyproject.toml:45-47`이 `opentelemetry-api`·`opentelemetry-sdk`·`structlog`
3종을 선언하는데 **`src/` 전체에서 import 0건**(실측). 그런데 **`MOB-08`(done)이 Flutter
`pubspec.yaml`에는 정확히 이 검사를 이미 만들었다** — "선언↔사용 거버넌스 테스트, 미사용 의존
1개를 되돌리면 red". **backend에는 대응물이 없다.**

게다가 `declared_unwired_audit`의 4축(라우트·EventType·타임시리즈·CLI)에 **의존성 축이 없어서**
이 사각은 **어느 감사기에도 안 잡힌다** — "선언≠배선"을 잡는 전용 게이트를 갖고도 그 게이트의
축 목록 밖이라 통과한 형태다.

**설계**: `MOB-08` 게이트를 backend로 **이식**(재발명 금지 — 구현을 먼저 읽고 같은 판정 규약).
3종 각각 **제거 vs 배선** 판정 동반(dead code 금지 — 좌석 없는 선언은 걷는다). 빌드·런타임 전용
의존은 허용목록에 사유 명시. 착지 위치(감사기 5번째 축 vs `tests/infra` 독립)는 착수 세션 택일.

**부수 발견 → §정정**: `CLAUDE.md` 스택 표가 모니터링을 *"Langfuse + OpenTelemetry"*로 적지만
**OTel은 import 0건**이다(Langfuse만 실배선).

### D11. **결함 신고 읽기 경로 0** — 접수만 되고 아무도 못 읽는다 (신규 `RPT-02`)

**갭**: `RPT-01`(done)이 학생 결함 신고 채널을 열었다(`POST /v1/reports/defects`, append-only).
그런데 **운영자가 신고를 읽을 수단이 `qa_pipeline` 축 9의 *행 수 카운트* 뿐**이다 — 조회 CLI
0건·admin 표면 0건(`DefectReport` 참조는 `api/reports.py`·`api/_rate_limit.py`·`qa_pipeline.py`
3곳뿐). **학생이 "이 문항 답이 이상해요"를 신고해도 어느 문항인지 아무도 못 본다.**

CLAUDE.md 금기 **"작동 신호 없는 알고리즘 부착 금지 — '작동한 비율' 원칙"**에 정면 해당한다.
채널을 붙였으면 그 채널이 **실제로 무엇을 잡았는지**를 리포트가 말해야 한다. 의사결정 우선순위
**1위(학생 안전·신뢰)** 축이기도 하다 — **신고가 사라지는 채널은 신고를 안 받는 것보다 나쁘다**
(학생은 신고했다고 믿는데 아무 일도 일어나지 않는다).

**왜 저비용·저위험인가**(실측): `DefectReport`는 **`user_id` 컬럼 자체가 없고** 자유서술도 없다 —
`category`(폐쇄 6종) + `problem_id`뿐. 즉 **PII가 구조적으로 0**이라 집계·출력에 마스킹 설계가
불요하다. append-only 계약도 그대로 유지된다.

**설계**: `ops/defect_report_digest.py` CLI 1개 — 카테고리별·문항별 집계 + 상위 신고 문항 랭킹.
기존 `ops/*_report.py` 패턴 답습, 새 판정 로직 0. 테이블 미존재와 0건 접수를 **다른 값**으로
내는 이중 회계(축 9 규약 재사용). `declared_unwired_audit` 대장에 `_OFFLINE_REPORT` 등재.

**범위 밖 동결**: HTTP admin 표면·콘솔 UI·신고 처리 상태 전이(PATCH)는 **포함하지 않는다** —
§2-④ CMS 트리거는 미도달 유지이며 이 태스크가 CMS를 앞당기지 않는다.

---

## §4. 정직한 공백 — 지금 하지 않는 것

| 공백 | 사유 | 해소 시점 |
|---|---|---|
| **런타임 코치 산문 안전 검사** | `ARCH-24` acceptance ⑤가 정한 경계 승계 — 배치가 1단계. 분류 함수가 순수 분리돼 있어 부착 시 새 판정 로직 불요 | 실시간 부착 판단이 별도로 설 때(라이브 트래픽 규모 실측 후) |
| 관리자 CMS · 콘텐츠 운영 감사 · RBAC 확장 | §2-④ 재심 미도달(결제 0·운영자 1인). **설계는 정본 실재**(`docs/design/ui/03·04`) | 결제 도입 or 운영자 2인+ |
| 저작권 기간·사용범위 세분 필드 | §2-① 재심 미도달(26/26 자체생성) | 외부 라이선스 콘텐츠 실적재 |
| UI 스크린샷 골든 · 통계 이상치 | §2-⑥⑦ 재심 미도달 | 화면 수·회귀 빈도 / `S3-01` 완료 |
| 콘텐츠 diff·rollback·버전 컬럼 | §2-⑤ 승계 — git+코퍼스 접미가 정본. 소비처 미실증 | 재현성 감사 요구 실측 |
| `content_provenance`/`generation_log` 실영속 | r2 D6 재판정 승계 — 쓰기 경로 0 유지 | 동일 |
| **WAL/PITR** | pg_dump 스냅샷 방식 유지 — 백업 사이 유실 범위를 감수 | 실학생 데이터 볼륨이 유실 감수 범위를 넘을 때 |
| **TLS·레지스트리·프로덕션 호스트·무중단 배포·staging 전용 호스트** | **전부 호스트 미프로비저닝 종속** — 없는 대상에 태스크를 만들면 dead task | 프로덕션 호스트 확보 |
| **경로별 지연 분해(S5)·다중 워커 지표 합산·지표 영속화** | 단일 워커·단일 호스트 단계에선 해석 이익이 비용을 넘지 않음 | 다중 워커 전환 or S4가 측정되기 시작한 뒤 |
| 온콜 인원 | 1인 조직 구조 — 조직 문제지 코드 문제가 아님 | 팀 확대 |
| **`deploy.yml` 실 호스트 실행 0회** | 미프로비저닝 선결 — §5 트리거만 등재 | 첫 실 배포 시도 |

---

## §5. 발화 트리거 (기계로 관측 가능한 형태)

| 항목 | 트리거 |
|---|---|
| 43 CMS · 48 RBAC 확장 | 결제 코드 첫 등장 or 운영자 좌석 2건+ 발급 |
| 저작권 기간·사용범위 세분(§2-①) | `data/corpus/*/_provenance.json`에 `pool != whymath-original` 첫 등장 |
| UI 골든(§2-⑥) | Flutter 화면 수·골든 회귀 빈도 실측 |
| 통계 이상치(§2-⑦) | `S3-01-pilot-cohort` 완료 |
| 런타임 코치 산문 안전 검사 | 라이브 코치 트래픽이 실학생에게 서빙 개시 |
| **TLS·레지스트리·무중단 배포·staging 호스트** | **프로덕션 호스트 확보**(= `deploy.yml` preflight가 처음 통과) |
| **`deploy.yml` 검증 경로 승격** | 첫 성공 실행 기록이 남을 때 — 그 전까지 `OPS-03` done은 "골격 완성"이지 "배포 가능"이 아니다 |
| WAL/PITR | 실학생 응답 적재 개시 후 유실 감수 범위 재산정 |
| 다중 워커 지표 합산 | uvicorn 워커 수 > 1 전환 |

---

## §6. 에스컬레이션 — 인가 데드락 (신규 태스크 없음)

**실측**: 콘텐츠 CUD 6라우터가 `require_content_admin`으로 봉인돼 있는데
**`CONTENT_ADMIN`을 부여하는 코드가 main에 0건** → 그 6라우터는 현재 **전건 403**이다.
"문을 만들고 열쇠를 안 만든" 상태이며, `operations_platform_gap_review.md`가 이미 지적하고
`ADMIN-01`로 등재해 뒀다(notes가 **"반복 실수 7회차"**로 자인).

**새로 드러난 것**: 구현이 **이미 완성돼 있고 미머지 브랜치에 5일째 고립**돼 있다 —
`origin/claude/admin-01-operator-seat-grant-audit`의 커밋 `8924a2e2`
(`ops/role_grant_cli.py` 231줄 + `role_change` 감사 + 테스트 526줄, 커밋 메시지가 hermetic 16 +
integration 4 + 회귀 98 통과·CLI 왕복 재현 확인을 기록). 게다가 **그 브랜치엔
`53a06c4f "backlog: ADMIN-01 done"`까지 있는데 main 대장은 `todo`**다 — 대장과 브랜치가 갈렸다.

이는 `PB-01`이 상환한 **미병합 완료분 고립의 재발**(`ADMIN-01`은 `PB-01` 범위 밖이었다).
r3 작성 시점에는 회수를 수행하지 않고(그 세션은 문서·백로그 축) **최우선 회수 권고**만 남겼다.

### §6-1. 회수 완료 (2026-08-11, 같은 날 후속 세션)

Kiki 지시로 **회수를 실행했다**. 결과와 그 과정에서 드러난 것:

| 항목 | 실측 |
|---|---|
| 회수 방식 | **`cherry-pick 8924a2e2` 1커밋** — 브랜치 머지 아님 |
| 텍스트 충돌 | **0건**. `enums.py`·`audit.py` 모두 `8924a2e2^`와 `origin/main`의 **블롭 해시가 바이트 동일**(`e4f4320c…`·`fc091645…`) — "그 사이 RPT-01·SEC-*가 고쳤을 것"이라는 가설은 **반증**됐다(`DefectCategory`는 이미 그 커밋의 부모에 있었다) |
| 왜 머지가 아닌가 | trunk 대비 35커밋 앞서 보이지만 **33개는 이미 main에 내용이 들어간 PR 스쿼시 커밋**(SHA만 다름). 분기점 `dd91d3d8`이 현재 main의 조상이 아니라 숫자가 부풀었다. 머지하면 유령 커밋을 되살린다 |

**회수의 진짜 비용은 충돌이 아니라 "고립 기간에 트렁크가 새 계약을 도입했다"는 것이었다.**
`OPS-22`(`declared_unwired_audit`)가 그 커밋보다 **나중에** 착지했고, 그 감사기는 `ops/*.py` 중
모듈 레벨 `def main(`을 가진 모듈을 **자동 수집**한다. 회수분은 그 계약을 모르므로 착지 즉시
`unclassified` 위반이 됐다 — **실측: 등재 전 `AUDIT_EXIT=1`(`✗ unclassified ops.role_grant_cli`),
등재 후 `AUDIT_EXIT=0`**(변별력 양방향 확인). 사유는 `_PRIVILEGE_ESCALATION_CLI`로 신설했다:
*"권한 상승 경로 — HTTP 미노출이 설계 확정값이므로 '미도달'이 결함이 아니라 의도한 봉인"*.

> **회수 일반 교훈(신규)**: 고립분 회수의 위험도를 *충돌 가능성*으로 재면 과소평가한다. 진짜
> 위험은 **고립 기간에 트렁크가 도입한 계약을 회수분이 모르는 것**이고, 이건 충돌이 아니라
> *새 게이트의 exit 1*로 나타난다. 회수 체크리스트에 "그 사이 새로 생긴 게이트가 이 코드를
> 어떻게 보는가"를 넣는다.

**아울러 회수분이 놓친 계약 3곳을 동기화**했다 — 멤버는 4개가 되는데 문서는 "3종"으로 남아
있었다: `AuditEventKind` 클래스 docstring · `PrivacyAudit` docstring ·
`docs/standards/security_privacy.md` 감사 부기(enums docstring이 **"그 부기와 정확히
일치시킨다"고 계약으로 선언**하고 있어, 안 고치면 자기 계약 위반).

**데드락은 아직 완전히 닫히지 않았다.** 코드가 착륙해도 **prod 좌석은 0건**이다 —
`G-operator-seat-first-grant`(Kiki 소유·명령 블록 동봉)가 clear되고 `list`가 좌석 1건 이상을
보여줄 때 비로소 닫힌다. 그때까지의 정직한 표현은 **"해소 경로가 생겼다"**이지 "해소됐다"가 아니다.

---

## §7. 반복 실수 — **10회차** (재발방지 등재)

시리즈 최댓값 9회차(`service_operations_gap_review.md` §6)에 이어 **10회차**를 등재한다.

**유형**: *"자기 문서가 자인한 공백을 판정이 읽지 않는다."*

| 회차 근거 | 형태 |
|---|---|
| r2 D4(2026-08-03) | `qa_pipeline`의 `_NOT_MEASURED_AXES`가 정직하게 "검사 안 함"을 표기했으나 **백로그 추적 0** — r2가 *"정직 표기는 침묵 통과는 막지만 영구 미상환은 막지 못한다"*로 명명하고 상환 |
| **r3 D9(2026-08-11)** | **같은 형태가 런북 평면에서 재발** — 런북 3종 §정직한 공백 25종이 추적 0건인 채 v1·r2 **2회 연속 ✅ 승계 통과**. 오히려 런북의 정직함이 판정을 통과시키는 근거로 쓰였다 |

**재발방지 대책**(CLAUDE.md 실수 관리 규약 — "다음엔 조심한다"는 대책이 아니다):
- **코드**: `OPS-29`가 *강제 상태* 축에서 같은 구조를 기계화한다(선언 없는 유예 → exit 1,
  `pending-task` 만료 계약). 이 계약의 본질은 **"자인한 공백은 추적 ID를 갖거나 사유를
  선언해야 한다"**이며, 런북 평면에도 같은 규약을 넓힐 수 있는 원형이다.
- **태스크**: `OPS-30`·`OPS-31`이 25종 중 실갭 2건을 상환한다.
- **게이트**: 사람 소유 3건을 `gates.yaml`에 등재해 **운영 축 게이트 0건 상태 자체를 해소**했다.
- **판정 규약**: 이후 자매편은 46·49·50류 "런북으로 상환된 축"을 승계할 때
  **태스크 상태가 아니라 런북 본문의 §정직한 공백을 함께 읽는다**(본 문서 §1 정정 ⑥이 선례).

---

## §정정 — stale 정본 (이번 대조에서 실측 발견)

| 위치 | 현 표기 | 실측 | 조치 |
|---|---|---|---|
| `CLAUDE.md` 스택 표 "모니터링" 행 | "Langfuse + OpenTelemetry \| LLM 추적 표준" | **OTel은 `pyproject.toml` 선언만·import 0건**. 실배선은 Langfuse 단독 | 실측 단서 병기(본 PR) — 의존 자체의 제거/배선 판정은 `OPS-32` |
| `ARCH-23` acceptance 라인 참조 | `ci.yml:186` | 현재 **`:192`**(그 사이 주석 증가) | 보강 시 함께 정정(완료) |
| r2 §부록 "wiring 테스트 5개" | (r2 시점 정확) | 현재도 5개 유지 — **`tests/infra/*_wiring.py`는 11개** | r3 본문이 11로 명시 |

> `docs/design/ui/03·04`(43 설계 정본)는 이번 대조에서 stale 없음 — `SEC-07` 반영이 이미 돼 있고
> 모듈 레지스트리 설계도 현행이다.

---

## §8. 실행 — 백로그 등재 · 중복 회피 대장

### 신규 등재 (ID는 `backlog.py add`가 배정 — 번호 추론 금지·HARN-10)

| 설계 | 태스크 | stage/prio |
|---|---|---|
| **D8** | `OPS-29-ci-enforcement-declaration-contract` | S3 / 2 |
| **D9-1** | `OPS-30-alerting-last-hop-and-uptime-probe` | S4 / 2 |
| **D9-2** | `OPS-31-backup-encryption-offsite-schedule` | S4 / 2 |
| **D10** | `OPS-32-backend-dependency-declaration-usage-gate` | S4 / 3 |
| **D11** | `RPT-02-defect-report-readout-cli` | S3 / 3 |

> **번호 가드 실동작 기록**: 최초 `OPS-26`으로 등재 시도 → CLI가 **원격 브랜치
> `claude/whymath-ai-integration-check-5qqcp4`의 `OPS-26`과 충돌**을 잡고 `OPS-29`를 제안해
> 그대로 따랐다(HARN-15 교차 브랜치 스캔이 실제로 병렬 세션의 인플라이트 번호를 막은 사례).

### 기존 태스크 수정

- `ARCH-23-qa-gate-enforcement` — **acceptance 2항 추가**(축 9 상시 error 처리 3안) + notes에
  2회차 관측·라인번호 정정 기록. **신규 태스크를 만들지 않은 이유**: 갭이 새로 생긴 게 아니라
  기존 태스크가 **실행 불가능한 상태**였던 것이므로 그 태스크를 고치는 것이 맞다.

### 게이트 등재 (사람 소유 — `gates add`)

`G-deploy-environment-approval`(14일 리마인드) · `G-backup-restore-rehearsal`(30일) ·
`G-backup-offsite-move`(30일). 전부 `assignee: kiki`.

### 중복 등재 금지 대장 (이번에 등재하지 **않는** 것과 그 소유자)

| 주제 | 기존 추적 |
|---|---|
| canonicalize 130건 판정 | `S3-28`(수정 없음 — r2가 이미 priority 상향) |
| qa_pipeline 실제 해제 | `ARCH-23`(보강만·신규 아님) |
| 운영자 좌석 발급 | `ADMIN-01`(**회수 대기** — §6) |
| 감사 보존 정책 | `ADMIN-03` |
| dead 테넌시·과금 컬럼 | `ADMIN-02` |
| 실응답 통계·난이도 루프 | `S4-15` · `S3-01` |
| 로그 PII 스크러버 | `SEC-11`(done) — D9·D11과 다른 평면 |
| 관리자 CMS·RBAC 확장(43·48) | `docs/design/ui/03·04` 설계 정본 + §2-④ 트리거 대기 — **미등재가 의도** |
| 배포 인프라 프로비저닝 | §5 트리거(호스트 확보) — dead task 방지 |
| 런타임 코치 산문 안전 검사 | §4 정직한 공백(`ARCH-24` 경계 승계) |

---

## 부록 — 실측 근거 (2026-08-11, 브랜치 `claude/whymath-eos-review-64f81f`, HEAD `959ec4ad`)

| 주장 | 확인 명령·위치 |
|---|---|
| QA 게이트 여전히 fail-open | `grep -n "continue-on-error" .github/workflows/ci.yml` → `:192`(qa_pipeline)·`:923`(shellcheck) 2건 |
| **축 9 상시 error(2번째 블로커)** | `awk 'NR>=111&&NR<=198' .github/workflows/ci.yml \| grep -c "services:"` → **0** (data-pipeline 잡에 Postgres 없음) |
| error가 실패로 집계 | `harness/qa_pipeline.py` `_aggregate` — `result.status in ("gate_fail", "error")` |
| `ARCH-23` 미착수 | `backlog/tasks/ARCH-23-qa-gate-enforcement.yaml` `status: todo`(r3 보강 전) |
| `S3-28` 미착수 | `backlog/tasks/S3-28-*.yaml` `status: todo` |
| wiring 테스트에 강제 계약 0 | `grep -rln "continue-on-error" tests/infra/` → **0** / `ls tests/infra/*_wiring.py \| wc -l` → **11** |
| 그랜드파더 전부 해소 | `ops/provenance_audit.py:97` `_KNOWN_GAPS: dict[str, GrandfatherEntry] = {}` |
| 사이드카 26/26·전량 자체생성 | `for d in data/corpus/*/; do [ -f "$d/_provenance.json" ] \|\| echo NO; done` → 무출력 / `grep -h '"pool"' data/corpus/*/_provenance.json \| sort \| uniq -c` → `26 "pool": "whymath-original"` |
| 금칙어·PII 축 실재(축 8) | `harness/banned_words_pii_eval.py` + `qa_pipeline.py` `_axis_banned_words_pii` |
| 알림 발송 채널 0 | `grep -rn "Slack\|slack\|webhook\|smtp\|SMTP\|pagerduty" src/backend/whymath_backend/ops/service_health.py \| wc -l` → **0** (`AlertLogNotifier`는 `:401`) |
| 백업 스케줄 자동화 0 | `grep -rln "schtasks\|crontab\|systemd.*timer\|OnCalendar" scripts/ infra/ \| wc -l` → **0** |
| 백엔드 의존성 3종 import 0 | `grep -rn "import structlog\|from opentelemetry\|import opentelemetry" --include=*.py src/ \| wc -l` → **0** (선언은 `src/backend/pyproject.toml:45-47`) |
| `record_admin_access_audit` 호출부 0 | `grep -rn "record_admin_access_audit" --include=*.py src/` → 8히트 전부 정의·재수출·docstring |
| 결함 신고 읽기 경로 0 | `DefectReport` 참조 = `api/reports.py`·`api/_rate_limit.py`·`harness/qa_pipeline.py` 3곳 (조회 CLI·admin 표면 0) |
| **role 부여 코드 0** | `grep -rn "\.role = \\\|role=Role\." --include=*.py src/backend/whymath_backend/ \| wc -l` → **0** |
| ADMIN-01 구현 고립 | `git show --stat 8924a2e2` → 5파일 815줄. `git branch -r --contains 8924a2e2` → `origin/claude/admin-01-operator-seat-grant-audit`만(main 조상 아님). 그 브랜치에 `53a06c4f "backlog: ADMIN-01 done"` |
| 결제 코드 0(§2-④) | `grep -rln "토스\|tosspayments\|payment" src/backend/` → `README.md` 1건(코드 0) |
| 런북 자인 공백 | `incident_response_slo.md` §6(11행 표) · `db_backup_dr_runbook.md` §6(4불릿) · `deployment_cd_runbook.md` §8(미프로비저닝 표 8행 + 검증하지 않는 것 4불릿) |
| `deploy.yml` 실행 0회 | `.github/workflows/deploy.yml:3-10` 자인 — *"한 번도 실 호스트에 실행된 적 없는 골격"* |
| 운영 축 게이트 0건(등재 전) | `backlog/gates.yaml` 7건 전부 crosswalk·파트너·실기기·orphan·라이브키·은퇴원자·S5 — 배포/백업/모니터링 0 |
| 등재 후 대장 무결성 | `python3 scripts/harness/backlog.py validate; echo "EXIT=$?"` → `태스크 244건, 게이트 10건` · `EXIT=0` |

---

**버전**: 1.0 | **작성**: 2026-08-11 | **교차링크**: [v1](operations_module_gap_review.md) · [r2](operations_module_gap_review_r2.md) · [운영 플랫폼](operations_platform_gap_review.md) · [서비스 운영](service_operations_gap_review.md) · [관리 콘솔 계획](../design/ui/03_admin_console_plan.md)·[아키텍처](../design/ui/04_admin_console_architecture.md) · `../standards/incident_response_slo.md` · `db_backup_dr_runbook.md` · `deployment_cd_runbook.md`
