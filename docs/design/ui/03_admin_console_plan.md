# 03. 앱 관리(admin) UI 구성 계획

> **질문**: WhyMath 앱을 관리하기 위한 UI 구성 계획을 마련하라.
>
> **한 줄 답**: "관리 UI"를 **두 갈래로 분리**한다 — ⓐ **내부 운영 백오피스(Operator Console)**(신설 필요·본 문서 중심)와 ⓑ **교사·학부모 대시보드**(L7·Phase3·[02 문서](02_student_ui_master_plan.md)). 운영 백오피스의 MVP는 **기존 CLI/API를 래핑한 read-only 관측 대시보드 + 검수 큐**다.

---

## §1. 두 갈래 구분 (혼동 방지)

| | ⓐ 운영 백오피스 (Operator Console) | ⓑ 교사·학부모 대시보드 |
|---|---|---|
| 사용자 | WhyMath 팀·운영자·콘텐츠 검수자 | 학교 교사·학부모(B2B/B2C) |
| 목적 | 콘텐츠·모델·비용·품질·프라이버시 **관리** | 학급·자녀 학습 **조회** |
| 위치 | 내부망/VPN 별도 웹 | 교사=별도 웹·학부모=인앱 역할 |
| 상태 | 🔴 코드 0·계획 문서 없음 → **본 도메인이 신설** | 🔴 L7 Phase3 계획(`07`) |
| 정본 | 본 문서 + [04 아키텍처](04_admin_console_architecture.md) | `../architecture/07_community.md` |

> **현재 저장소에 admin UI 코드는 존재하지 않는다.** 운영 관리는 (i) CLI 도구(`ops/`·`scripts/harness/`), (ii) 외부 SaaS(Langfuse), (iii) **인증도 안 걸린** 콘텐츠 CRUD API로 흩어져 있다. 본 문서는 이를 하나의 콘솔로 조직하는 계획이다.

---

## §2. 관리 자원 인벤토리 — 운영 백오피스가 다뤄야 할 것

저장소 실측 기준으로, 운영자가 관리해야 하는 자원과 그 현재 위치:

### 1. 콘텐츠·지식자산 (L1)
- **대상**: concept·atom·problem·solution·misconception·visualization·PedagogyPack/UnitDSL.
- **현재 위치**: `api/concepts.py`·`api/problems.py`(CRUD 존재·**무인증** ⚠️), 코퍼스 `data/corpus/*`(+`_provenance.json`), ORM `db/models/`.
- **필요 기능**: CRUD + **검수 워크플로우** + 성취기준 태깅 확인 + 라이선스·provenance 표시.
- **검수 워크플로우(실측)**: `pedagogy_dsl.py`에 이미 fail-closed 상태 흐름 존재 — 콘텐츠 슬롯 `DRAFT → PRESCREENED → APPROVED | REJECTED`, 소단원 `DRAFT → ACTIVE`. **게이트 통과 전에는 학생에게 노출 안 됨**. 콘솔은 이 상태 전이를 사람이 승격/반려하는 UI.

### 2. LLM·라우터·모델 (L3)
- **모델 매트릭스**: `GET /status`(`app.py:374`) — Ollama 레디니스·설치 모델·클라우드 구성/도달성·`missing[]`. 운영 대시보드의 1차 상태 API.
- **cost_tier 정책**: `l3/router.py`(LOCAL/CLOUD_MID/CLOUD_HIGH), `03a_l3_router_design.md`.
- **프롬프트(Langfuse 버전)**: `docs/prompts/*.md` 원본 + Langfuse 버전 관리. → 콘솔은 **재구현하지 않고 Langfuse를 링크/임베드**.

### 3. 비용·품질·게이트 (ops·harness)
- **비용**: `ops/cost_report.py` — `l3_routing` 이벤트를 p50/p90·평균·합, 로컬:클라우드 비율, 캐시 적중률로 집계.
- **게이트**: `ops/cost_probe.py`(로컬 비율 Wilson 하한 ≥0.80 판정)·`harness/wilson.py`·`harness/agreement_gate*.py`·`corpus_audit_eval.py`·`wh1_evaluation.py`.
- **빌드 하네스**: `scripts/harness/backlog.py`(status/next/gates)·`backlog/gates.yaml`(사람 게이트 대장)·`events.ndjson`(감사 로그).

### 4. 사용자·프라이버시
- **사용자 조회**(PII 최소): `db/models/user.py`(`UserProfile`·학적·페르소나·구독·보호자 동의).
- **데이터 관리**: `privacy/export.py`(GDPR 반출)·`erasure.py`(삭제)·`retention.py`+`retention_purge_cli.py`(PII 자동 파기·`pii_retention_years=3`)·`audit.py`(삭제 감사).
- **보호자 동의**: `api/users.py` `parental-consent`·`parental_consent.py`.

### 5. 데이터셋·라이선스
- 코퍼스 카탈로그 `docs/data/dataset_catalog_v4.md`·provenance `_provenance.json`+`db/models/provenance.py`·라이선스 매트릭스 `docs/data/licensing_safety.md`·법무 `docs/legal/*`.

### 6. 모드·기능 플래그
- `config.py`(1105행·`WHYMATH_` env) — shadow/primary 게이트(`wh1_primary_enabled` 등)·rate limit·임베딩/벡터 셀렉터. **조회**는 안전, **런타임 오버라이드**는 신중히(현재는 프로세스 env 고정 → 오버라이드하려면 별도 설정 계층 필요·[04 §5]).

---

## §3. 검수 큐 UI — 인간은 "최종 권위"가 아니라 한 검출기

`harness/needs_review_worklist.py`가 검수 대상을 큐로 만든다. 콘솔의 검수 큐 UI는 **초인간 검증 기준 v1**의 권위 서열을 반영한다(`docs/standards/superhuman_verification_standard.md`):

```
① 기계 증명(SymPy·도구)  >  ② 측정 통과 기계 게이트(Wilson)  >  ③ 인간 폴백(측정 미달·undecidable 구간만)
```

- 검수 큐는 ③ 인간 폴백이 필요한 항목만 사람에게 올린다. ①②가 판정한 것을 사람이 뒤집는 UI가 아니다.
- **인간 검수도 오류율이 측정되는 검출기**로 취급 — "사람이 봤으니 안전"을 가정하지 않는다.

---

## §4. 정보구조(IA) — 좌측 내비 섹션

```
콘텐츠
  ├─ 개념·원자 (concept / atom)
  ├─ 문항·풀이 (problem / solution)
  ├─ 오개념 (misconception)
  └─ 교수법 팩·소단원 DSL (PedagogyPack / UnitDSL) — 검수 워크플로우
LLM·프롬프트
  ├─ 모델 매트릭스 (GET /status)
  └─ 프롬프트 (Langfuse 링크)
비용·품질
  ├─ 비용 리포트 (cost_report: p50/p90·로컬비율·캐시)
  ├─ 게이트 (Wilson PASS/FAIL·cost_probe)
  └─ 빌드 하네스 (backlog·gates 대장)
사용자·프라이버시
  ├─ 사용자 조회 (PII 최소)
  ├─ 보호자 동의 상태
  └─ 데이터 반출·삭제·보존 파기 (privacy/·감사)
데이터셋
  └─ 코퍼스 카탈로그·provenance·라이선스
설정
  └─ 기능 플래그 조회 (config.py 노브)
검수 큐 ★ (needs_review_worklist — 상시 상단)
```

---

## §5. Control Center — 4계층 프레임 + 모듈 매핑 (원본 [C]·[D])

Kiki의 ChatGPT 설계안([C]·[D])은 관리 UI를 *단순 CMS가 아니라 Education OS Control Center*로 설계할 것을 제안한다. WhyMath는 이를 **§4 좌측 내비를 조직하는 4계층 프레임**으로 채택하되, 모든 모듈을 **실재 자산에 매핑**하고 없는 것은 🔴로 표기한다(환상 방지). EOS 자체는 북극성 서사이며 조직 프레임은 확정된 L1~L7이다([05](05_source_reconciliation.md)).

### 4계층 콘솔 프레임 (원본 [D])
```
① 운영(Dashboard)      — KPI 한눈에
② 설계(Design Studio)  — Curriculum·Objective·Pedagogy·Concept·Misconception
③ 생성(Generation)     — DSL Builder·Auto Generation·Prompt·QA
④ 운영·분석(Operation) — Analytics·Deployment·Monitoring·Version
```
이 4계층은 WhyMath의 **설계 → 생성 → 운영 → 분석·개선 폐쇄 루프**와 같으며, 그 루프는 곧 `04d` Adaptive Pedagogy Engine 루프(교수법 선택→렌더→데이터 수집→효과 측정→policy 갱신)다.

### 22모듈 + 5 EOS Studio → WhyMath 자산 매핑

원본 [D]의 22개 모듈과 5개 EOS Studio를 실재 코드/데이터에 매핑한다. **대부분 데이터·엔진은 🟢 있고 UI만 🔴 없다** — 콘솔은 이들을 래핑한다.

| 원본 모듈/Studio | WhyMath 자산 | 상태 |
|---|---|---|
| Dashboard(KPI) | `GET /status`+`cost_report`+`backlog` 집계 | 자산🟢·UI🔴 |
| Curriculum | `curriculum_entry`·`units_v1` | 데이터🟢·UI🔴 |
| Objective | `learning_objective`·`achievement_standard` | 데이터🟢·UI🔴 |
| **Pedagogy Studio** | `PedagogyPack`(설계-교수법·`schema/pedagogy_pack.py`) | 데이터🟢·UI🔴 |
| **Knowledge Graph Studio** | `concept_node`·`atom_node`(+Neo4j) | 데이터🟢·UI🔴 |
| **Misconception Studio** | `misconception_catalog`·`crosslink` | 데이터🟢·UI🔴 |
| Content Library | `problem`·`solution`·`concept_content`·`visualization` | 데이터🟢·UI🔴 |
| DSL Builder | UnitDSL(`unit_compiler`🟢) · ConceptDSL(`REND-01`🔴) | 혼합 |
| **Generation Pipeline** ★ | `l3/pregenerate`+select-vs-generate(`03c`) | 엔진🟡·UI🔴 |
| AI Evaluation / QA | harness 게이트(SymPy·agreement·corpus_audit·defect_detection·coach_prose_leak) | 🟢·UI🔴 |
| Assessment | L2 IRT/BKT·`verify-*`·문항은행 | 🟢·UI🔴 |
| Student Analytics | L2 `MasteryState`+`timeseries` | 🟢·UI🔴 |
| Teacher/Parent Analytics | L7 대시보드 | 🔴 Phase3(`07`) |
| **Learning Digital Twin** | L2 실시간 학습 상태·오개념·예측 시뮬 | 🔴 계획 |
| AI Models | `GET /status` 모델 매트릭스(**실제=Ollama+Claude**) | 🟢·UI🔴 |
| Prompt Library | Langfuse(버전·A/B) | 🟢 임베드 |
| Version / Deployment / Monitoring | git+`backlog events` · `infra/phaiakes9` systemd+GitHub Actions · Langfuse+`cost_probe` | 🟢·UI🔴 |
| System Settings | `config.py` 노브 + **RBAC 권한**(선결🔴) | 혼합 |
| App Management(다과목) | 현재 math-first·다과목 플러그인은 북극성 EOS | 🔴 지향 |

### ★ Generation Pipeline = Q1 5단계 파이프라인의 운영 콘솔

이 모듈이 [01 문서](01_student_pipeline_to_menus.md)의 **학생은 절대 보지 않는** 5단계 파이프라인을 *운영자가* 보고 실행하는 곳이다:

```
교육목적 → 교수전략 → 콘텐츠 → DSL → 자동생성 → QA → 배포 → 학생
                                                          ↓
                            Pedagogy 개선 ← 오개념 감지 ← Learning Analytics
```
- 학생 UI는 이 파이프라인의 *산출물*(학습 여정 카드)만 본다. 관리 콘솔은 파이프라인 *자체*를 시각화·실행·검수한다.
- 폐쇄 피드백 루프(원본 [C]) = `04d §3.1` Adaptive Pedagogy Engine. 이벤트 기반(Objective Created→…→Content Published→Misconception Detected)·다과목 플러그인은 **북극성 EOS 방향**으로 단계적 도입.

---

## §6. 안전선 (운영 백오피스 특유)

관리 UI는 강한 권한을 쥐므로 별도 안전선이 필요하다. 모두 `CLAUDE.md` 금기에서 유래:

- **표현 ≠ 의미**: 백오피스도 수학 판정을 하지 않는다. 동치·검산은 코어(SymPy) 결과를 *표시*만.
- **미성년 PII 마스킹**: 사용자 조회는 식별 최소·해시(`student_id_hash` 패턴)·학교/학년으로 개인 식별 가능한 노출 금지.
- **거부(deny) 우회 금지**: 게이트 판정(Wilson exit 0/1·사람 게이트 대장)을 **UI에서 손편집·수기 추가로 우회하지 않는다**. 콘솔은 판정 *결과를 표시*하고, 상태 변경은 정규 CLI 경로(`backlog.py`)를 호출한다. (사고 교훈: S1-14 YAML 직접 기입 차단.)
- **측정치 이중 회계**: 비용·로컬 비율 같은 핵심 판정치는 Langfuse(SaaS)뿐 아니라 인프로세스(`cost_probe`)에서도 산출. SaaS가 죽으면 콘솔은 **"측정 실패"를 명시**해야지 "0건 통과/미달"로 위장하면 안 된다. (langfuse 8일 무증상 전멸 교훈.)
- **감사 필수**: 모든 관리 액션(검수 승인·플래그·삭제)은 불변 감사 로그(→[04 §2](04_admin_console_architecture.md)).

---

## §7. 최소비용 경로 (MVP → 확장)

기존 자산을 최대한 래핑한다. **새 수학·판정 로직을 만들지 않는다.**

| 단계 | 범위 | 재사용 자산 |
|---|---|---|
| **Phase A (MVP)** | read-only 관측 대시보드 + 검수 큐 | `GET /status`·`cost_report`·`backlog.py`·`needs_review_worklist`·Langfuse 임베드 |
| **Phase B** | 콘텐츠 검수 승인·문항 CRUD (쓰기) | `api/concepts.py`·`api/problems.py`(+**RBAC 부착**)·검수 상태 전이 |
| **Phase C** | 교사 웹 B2B 합류 | `07` 교사 대시보드·같은 스택 공유 |

> **선결 과제 = RBAC**. 현재 `UserProfile`에 role 필드가 없고 콘텐츠 CRUD가 무인증이다. 어떤 쓰기 기능도 RBAC 없이는 위험하다. 아키텍처·선결 구현은 [04 문서](04_admin_console_architecture.md).

---

**버전**: 1.1 | **작성**: 2026-07-24 | **교차링크**: [00_index](00_index.md) · [04 아키텍처](04_admin_console_architecture.md) · [05_source_reconciliation](05_source_reconciliation.md) · `../architecture/07_community.md` · `../standards/superhuman_verification_standard.md`
