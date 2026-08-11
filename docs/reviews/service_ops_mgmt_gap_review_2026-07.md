# 서비스·운영·관리 공백 검토 (2026-07-26)

> **목적**: WhyMath를 "서비스·운영·관리" 세 축에서 실측 검토하고, *비어있는 부분*을 (a) 진짜 공백 vs (b) 로드맵상 의도된 지연으로 구분해 정본화한다. 검토 근거는 전부 저장소 실측(파일 경로 병기) — 인상 판정 금지.
>
> **검토 시점 현 위치**: Phase 1 MVP 심화(1인 개발) · S1 탈출 선언(2026-07-16) · S2 완료 · S3 14/15 · 백엔드 466 py·테스트 480·alembic 65.

---

## 0. 한 줄 판정

> **수학 코어(L1–L4)는 과잉 성숙. "비어있는 부분"은 전부 코어 바깥 — 제품을 실제로 *운영*하고 *관리*하는 층에 몰려 있다.**
>
> 결정적 실측: **백로그(단일 진실 원천)는 수학 코어를 S0~S5·E1~E6·ARCH 60여 태스크로 촘촘히 추적하지만, 운영 축(배포·모니터링·백업·장애대응) 태스크는 검토 시점 0건이었다** (`deploy|monitor|backup|alert|observability|incident` 검색 무일치). 즉 운영은 *미구현*이 아니라 **미계획**이었다 — 이번 검토로 OPS-01~04·MGMT-01을 등재해 상환 추적을 개시한다(§5).

---

## 1. 서비스(Service) 축

| 영역 | 상태 | 증거 | 판정 |
|---|---|---|---|
| API 코어 | ✅ 14개 라우터(auth/users/me/coach/problems/verify/ocr/visualization/scene/speech/devices/gating/interactions/concepts) | `src/backend/whymath_backend/api/` | 성숙 |
| 진단·숙달·학습경로 **엔드포인트** | ✅ `/v1/me/*`에 mastery·ability·diagnosis·weak-concepts·learning-path·recommend 다수 | `api/me.py` | 엔드포인트 성숙 |
| 위 표면의 **학생 도달** | ❌ Flutter 실호출 `/v1/` **13종에 경로 API 0종**. 경로 3종은 `concept_id`를 인자로 요구하는데 그 값을 고르는 조립 좌석이 0이라 학생이 호출할 방법 자체가 없다 | `learning_path_module_gap_review.md` §0-③ | **미도달 — `PATH-01`** (2026-08-03 정정: 코드 성숙도와 학생 도달을 한 칸에 합쳐 "학습자 대면·성숙"으로 판정했던 것을 분리) |
| E2E 제품 루프 (사진→OCR→진단→코칭 완주) | ⚠️ WH-1 하네스 primary 승격(S1-11 done)·실기기 15분 루프 시연 PASS. 파일럿 실사용 검증은 미착수 | `harness/wh1_*.py`, `api/coach.py`(1,719 loc) | **부분 — S3-01이 남은 조각** |
| L6 응용 모드 | ⚠️ suneung(gating+recommendation 396 loc)·metacognition·thinking·gifted·retake 존재하나 수능 외 얇음 | `l6/` | 부분 (S2-06·S3-03 done, 심화는 S4) |
| 결제·구독 | ❌ `subscription_tier`(free/basic/premium) **스키마 필드만**. 결제 라우터·토스페이먼츠·환불 전무 | `schema/user.py:259`, `schema/enums.py:782` | **의도된 지연** (Phase 2 M2.3) |
| 부모/교사 대시보드(L7) | ❌ admin/teacher/parent 라우터·웹 전무 (web = graphing-calculator 단일) | `src/web/` | 의도된 지연 (Phase 3) |
| 커뮤니티·풀이 갤러리(L7) | ❌ 전무 | — | 의도된 지연 (Phase 3) |
| 알림·푸시 | ❌ 전무 | — | 의도된 지연 (Phase 3 M3.2) |

**서비스 축 결론**: 유일하게 "지금 아픈" 곳은 **파일럿 실사용 검증(S3-01, todo)** — 코어는 준비됐고 학생 5~10명 실측만 남았다. 결제·대시보드·커뮤니티는 로드맵 순서상 정당한 지연이며 신규 태스크 불요(백로그 오염 방지).

## 2. 운영(Operations) 축 — **3축 중 최대 공백**

| 영역 | 상태 | 증거 | 판정 |
|---|---|---|---|
| CI | ✅ 9개 잡(backend/migrations/data-pipeline/mobile/web/infra-shell/policy-guard/harness-integrity 등) | `.github/workflows/ci.yml` | 성숙 |
| **CD(배포)** | ❌ deploy 잡 없음. 프로덕션 Dockerfile·compose.prod·IaC 전무 — `docker-compose.demo.yml`(일회용 볼륨) + Phaiakes9 개발 스크립트만 | `infra/phaiakes9/` | 🔴 **진짜 공백 → OPS-03** |
| **서비스 관측성·알림** | ❌ Langfuse(LLM 추적)+OTel+`ops/cost_probe`(비용)만. 서비스 헬스·에러율·업타임 **알림 전무** (Sentry/Prometheus/Grafana류 무일치) | `ops/` | 🔴 **진짜 공백 → OPS-01** |
| **DB 백업·DR** | ❌ prod DB = docker `whymath-pg`(단일 머신:5433). 백업 스크립트·복구 절차·리허설 전무 | CLAUDE.md 로컬 DB 지도 | 🔴 **진짜 공백 → OPS-02** |
| **장애 대응·SLO** | ❌ 런북은 `shadow_measurement_runbook.md` 하나(측정용). 인시던트 플레이북·SLO 정의 없음 | `docs/architecture/` | 🔴 **진짜 공백 → OPS-04** |
| 시크릿 관리 | ⚠️ env 기반·수동. 자리표시자 키 사고(2026-07-16) 후 자가검증 규칙으로 보완됐으나 도구화는 미착수 | CLAUDE.md 시크릿 규칙 | 보류 가능 (규칙으로 완화 중) |
| LLM 비용 통제 | ⚠️ `cost_probe`는 *측정*(이중 회계)만 — 런타임 per-user 예산 상한 강제 없음 (KPI: 학생당 월 ≤1,000원) | `ops/cost_probe.py` | 부분 — ~~CACHE-01 계열에서 후속~~ **승계처 소멸**(2026-08-11 정정: `CACHE-01`은 done인데 예산 상한은 여전히 미배선). 현행 판정 = 비용에 대해 **fail-closed**(학생 경로가 구조적으로 LOCAL 고정이라 비용 사고 위험 0)이므로 상한 강제는 **결제 도입 결정의 하류**로 유예. 도달 계상은 OPS-18(done)이 관측 좌석을 열어 뒀다 |
| ClickHouse 행동로그 | ❌ 스택 표에 있으나 미배선 | — | 의도된 지연 (스케일 후) |

**운영 축 결론**: β 100명 규모여도 **에러 알림 + DB 백업은 없으면 안 되는 최소 안전망**이다. 특히 이 프로젝트는 "무증상 전멸"을 이미 두 번 겪었다(langfuse 8일·shadow 좀비 서버) — 서비스 레벨에서 같은 패턴이 재발하면 학생 대면 장애가 *조용히* 진행된다. OPS-01(관측성)·OPS-02(백업)를 S3(파일럿 전) 우선 배치한 이유다.

## 3. 관리(Management·거버넌스) 축 — **문서는 강, 집행이 절반**

| 영역 | 상태 | 증거 | 판정 |
|---|---|---|---|
| 법률 문서 | ✅ 저작권 가이드 v2(77KB)·PIPA 매트릭스·규제 체크리스트·라이선스 안전조합 | `docs/legal/`, `docs/data/licensing_safety.md` | 성숙 |
| 데이터 거버넌스 | ✅ 데이터 카드 35+·카탈로그 v4·검수 대장 | `docs/data/` | 성숙 |
| 콘텐츠 안전 검증 | ✅ 초인간 검증 기준·Wilson 게이트·PRM·결함주입 강등전 | `docs/standards/superhuman_verification_standard.md` | 성숙 |
| 개인정보 권리 행사 | ✅ 삭제(erasure)·열람/이관(export)·보존(retention)·퍼지 CLI 실코드 | `src/backend/whymath_backend/privacy/` | 성숙 (PIPA 대응 양호) |
| **법정대리인 실 본인확인** | ⚠️ 동의 게이트(403)+감사 스키마(append-only)+GRANT 경로는 실존. 그러나 본인확인은 `StubGuardianVerifier`(method="stub") — 실 방식의 법적 적정성은 **변호사 자문 전제로 의도적 미구현** | `schema/parental_consent.py`, `consent_grant.py`, `api/auth.py:131` | 🔴 **런칭 차단 요인 → MGMT-01 (owner=kiki)** |
| 암호화 at-rest | ⚠️ AES-256-GCM 봉투 프리미티브 존재·device secret 결선은 후속·dialogue 이미지 암호화는 SEC-01(todo)로 기추적 — *검토 직후 #599로 done, 프로덕션 키 실측은 `SEC-02`(owner=kiki) 분리 등재됨* | `api/_crypto.py`, `SEC-01` | 부분 — **기추적** (신규 등재 불요) |
| 관리자·운영자 도구 (admin 콘솔·CS·모더레이션 UI·운영 BI) | ❌ 전무 | — | 의도된 지연 (β 소규모는 DB 직접 조회로 감내 — 결제 도입(Phase 2) 시 재검토) |
| 도메인 파트너 검수 | ⚠️ AI 검수 전환으로 대체(S2-05 done·2026-07-10 결정). 인간 수학자 검수 라운드는 사람 트랙 수동 대기 | ROADMAP Day 46~60, 병목 #4 | 기추적 (사람 게이트) |

**관리 축 결론**: 설계·문서·감사 레코드는 이미 상위권. 남은 건 **법령 유래 절차의 실집행** — 법정대리인 실 본인확인(변호사 자문 → 구현)이 미성년 대상 서비스 런칭의 단일 최대 차단 요인이다. 기계 대체 금지 영역이므로 owner=kiki로 등재했다.

---

## 4. 추적 상태 매트릭스 (검토의 핵심 산출)

| 공백 | 축 | 심각도 | 검토 전 추적 상태 | 검토 후 |
|---|---|---|---|---|
| 파일럿 실사용 검증 | 서비스 | 🔴 | **기추적** — `S3-01`(todo, next 후보) | 변동 없음 — *다음 drive 대상* |
| L6 심화·K-12 완성 | 서비스 | ⚠️ | 기추적 — S4-01~03 | 변동 없음 |
| 서비스 관측성·알림 | 운영 | 🔴 | **미추적 (0건)** | ✅ `OPS-01` 등재 (S3·prio 2) |
| DB 백업·DR | 운영 | 🔴 | **미추적 (0건)** | ✅ `OPS-02` 등재 (S3·prio 2) |
| 배포 자동화·IaC | 운영 | 🔴 | **미추적 (0건)** | ✅ `OPS-03` 등재 (S4·prio 3, OPS-02 의존) |
| 장애 런북·SLO | 운영 | ⚠️ | **미추적 (0건)** | ✅ `OPS-04` 등재 (S4·prio 4, OPS-01 의존) |
| 법정대리인 실 본인확인 | 관리 | 🔴 | **미추적** (코드 주석의 "후속"으로만 존재) | ✅ `MGMT-01` 등재 (S3·prio 1·**owner=kiki**) |
| dialogue 이미지 암호화 | 관리 | ⚠️ | 기추적 — `SEC-01` | 검토 직후 #599로 done (잔여: `SEC-02` 프로덕션 키 실측·owner=kiki) |
| 결제·대시보드·커뮤니티·푸시 | 서비스 | — | 로드맵 Phase 2/3 명시 | 태스크 미등재 (의도된 지연 — 백로그 오염 방지) |

## 5. 우선순위 권고

1. **S3-01 파일럿** (기존 next) — 서비스 축의 남은 조각. 코어는 준비됨.
2. **MGMT-01** (kiki·prio 1) — 변호사 자문은 리드타임이 길다. 파일럿(지인 학생·소규모)은 현 동의 게이트로 진행 가능하나, *공개 β 전* 완료 필수. *(2026-07-27 갱신: Kiki 결정으로 변호사 회신·외부인 리뷰 등 **외부 작업 전체를 제품 출시 전 단계로 일괄 연기** — 미완성 제품의 병목 방지. `blocked` 처리, 자문 준비물은 `docs/legal/guardian_verification_counsel_brief.md`로 완비. 이 행의 "먼저 착수" 권고는 대체됨)*
3. **OPS-01·OPS-02** (prio 2) — 파일럿에 실학생이 들어오는 순간 최소 안전망(에러 알림·백업)이 전제조건.
4. **OPS-03·OPS-04** (prio 3~4) — 공개 β·프로덕션 이전 단계에서.

## 6. 등재 내역 (2026-07-26)

`python3 scripts/harness/backlog.py add` 경유(대장 손편집 금지 준수)·`validate` green(76건):

- `OPS-01-production-observability-alerting` — 서비스 헬스·에러율·업타임 알림 + 인프로세스 이중 회계
- `OPS-02-db-backup-dr` — whymath-pg 백업·복구 리허설 런북
- `OPS-03-deploy-cd-iac` — CD deploy 잡 + compose.prod/IaC (OPS-02 의존)
- `OPS-04-incident-runbook-slo` — 장애 런북 + 최소 SLO (OPS-01 의존)
- `MGMT-01-guardian-real-verification` — 법정대리인 실 본인확인 (변호사 자문 선행·owner=kiki)

---

**작성**: claude (Kiki 지시 "서비스·운영·관리 입장에서 비어있는 부분 검토") · 산출물 형태(문서+백로그)·우선 영역(E2E/L6)은 Kiki 선택 반영
**다음 검토**: S3-01 파일럿 종료 시(운영 공백의 실측 재평가) 또는 공개 β 결정 시(MGMT-01 완료 여부 게이트)
