# 운영(Operations) 모듈 — 외부 EOS 틀 대조 갭 점검·설계 (2026-07-29)

> ⚠️ **후속 재점검 있음 — `operations_module_gap_review_r2.md`(2026-08-03)**. 이 문서(v1)의
> 설계 D1·D2는 둘 다 구현 완료됐고(`ARCH-20`·`ARCH-21`), §1 판정표 중 **4칸이 stale**하다
> (43 CMS·47 감사 로그·48 RBAC·45-⑤ PII — r2 §1이 사유·증거와 함께 정정). 이 문서는
> **완료 태스크의 판정 근거 원본**으로 보존하며 소급 수정하지 않는다. 현행 상태는 r2를 볼 것.

> **범위**: 외부 참고 문서 『0단계 운영(EOS)』(핵심 모듈 42~45: 콘텐츠 저작권·출처 관리 ·
> 관리자 CMS · 버전 관리 · 품질 검증(QA) 엔진 + 확장 제안 46~50: 배포 · 감사 로그 · RBAC ·
> 백업·복구 · 모니터링·알림 — **WhyMath 전용이 아닌 일반적 EOS 틀**, Kiki 제공)을 현
> 코드베이스와 대조해 빠진 부분을 점검하고, 진짜 갭을 WhyMath 불변식(저작권 3중 레일·검증
> 권위 서열·anti-explosion·dead code 금기·1인 capacity 가드) 안에서 설계한 기록.
> **형식**: `problem_bank_gap_review.md`·`solution_module_gap_review.md`(갭 분석→판정→설계)
> 답습 — 같은 외부 EOS 틀 대조 시리즈(모듈 6~10 → 18~22 → 23~27)의 자매편.
> **결론**: 46(배포)·49(백업)·50(모니터링)은 이미 `OPS-01~04`로 상환 완료(2026-07-26).
> 42(저작권·출처)는 핵심 자재는 있으나 **집행 게이트가 0**(가장 시급). 45(QA)는 도구
> 40여 개가 성숙했으나 **오케스트레이션이 없다**. 43(CMS)·48(RBAC)은 의도적 지연.
> 44(버전관리)·47(감사로그)는 module 6~10 review의 기존 판정을 그대로 승계. 진짜 갭
> 2건을 설계(D1~D2)하고 신규 태스크 2건을 백로그에 등재했다. D1의 문제은행 사이드카·데이터
> 카드 부분은 `S3-11`이 다른 미머지 브랜치에서 이미 완료해 이 세션은 착수하지 않았다(원격
> done 감지 — HARN-11 실측 재확인, 이 문서의 D1 신규분은 그 태스크가 다루지 않는 CI 집행
> 게이트에 한정).

관련 정본: `docs/reviews/service_ops_mgmt_gap_review_2026-07.md`(2026-07-26, 서비스·운영·
관리 3축 검토 — `OPS-01~04`·`MGMT-01` 등재, 본 문서가 그 후속) · `docs/legal/copyright_gradient.md`
§4(콘텐츠 풀 분리·집행 절차) · `docs/data/licensing_safety.md` · `docs/standards/dev_constitution.md`
§0(EOS 어휘 정본화 — 아래 §0 참조) · `MEMORY.md` 결정 로그(2026-07-29).

---

## §0. 용어 충돌 처리 (선결)

첨부 문서의 "운영(EOS)"과 이 저장소가 폐기한 어휘 "EOS"는 **동명이의**다. `dev_constitution.md`
§0(2026-07-18 정본화)은 "EOS(Education Operating System)를 목표 단계로 선언하지 않는다"
— 이는 **대외 제품 정체성 선언**(교육 전체를 아우르는 OS로 스스로를 부르는 시점)에 대한
결정이다. 첨부 문서의 EOS는 **외부 참고 프레임워크의 명칭**(사내 백오피스 의미)일 뿐이며,
앞선 자매 문서들(`knowledge_module_gap_review.md` 등)도 이미 "외부 EOS 틀"이라는 표현을
동일하게 중립적으로 써 왔다 — 이 저장소가 스스로를 EOS로 선언하는 것과는 무관하다. 이후
서술에서 "EOS"는 전부 **외부 참고 문서**를 가리킨다. 새 계층(L8)도 만들지 않는다 — 운영은
CLAUDE.md가 규정한 **횡단 관심사**(로깅·모니터링·에러는 별도 인프라)다.

---

## §1. 모듈 42~50 ↔ WhyMath crosswalk 판정

### 모듈 42. 콘텐츠 저작권·출처 관리 — **핵심 자재는 있으나 집행 게이트 0**

| 문서 항목 | WhyMath 현행 | 판정 |
|---|---|---|
| 관리 대상(교과서·교육과정·성취기준·문제·그림·AI 생성물 등) | `schema/provenance.py`(`ContentProvenance`)·`schema/problem.py`(`_METADATA_ONLY_SOURCES`)가 전 콘텐츠 유형에 원본출처·라이선스·생성타입을 강제 | ✅ |
| 출처(Source) | `SourceType`(평가원·EBS·교과서·자체생성 등) + 코퍼스 사이드카 `source_citation` | ✅ |
| 라이선스 | `LicenseType`(6종: PUBLIC_DOMAIN·EBS_LICENSED·AIHUB_OPEN·WHYMATH_GENERATED·USER_GENERATED·THIRD_PARTY_LICENSED) + `CurriculumLicense`(5종: KR-NCIC 등) | ⚠️ 부분 → **D1** (공공누리 세유형·CC 계열 미표현) |
| 저작권 기간(등록일·만료일·갱신) | 필드 없음 — 전량 `WHYMATH_GENERATED`(자체생성, 기간 개념 자체가 무의미)라 지금까지 무증상 | 🚫 §2-① (소비처 없는 필드 신설 금지) |
| 사용 범위(내부만/학생공개/상업가능/AI학습가능) | 필드 없음 — `is_exposable()`(`l6/_shared.py:141`)이 노출 여부는 이미 게이팅하나 세분류(상업/AI학습) 축은 부재 | ⚠️ 부분 → **D1** (외부 라이선스 도입 시 소비처 발생) |
| 원본 링크(URL·파일·PDF) | 코퍼스 사이드카 `source_citation`에 서술형으로만 존재 — 구조화 필드 없음 | 🚫 §2-② (본문 미보유 정책상 원본 참조 자체가 저작권 위험 — 의도적 비구조화) |
| AI 생성 여부 → 사람 검수 | `generation_type`(FULLY_GENERATED 등) + `review_status` 필드 실재. 검수는 **AI 검수 게이트**로 대체(2026-07-10 전환, 초인간 검증 기준) — "사람이 봤는가"가 아니라 측정 게이트 통과 여부 | 🚫 §2-③ (module 18 D2 선례 동형 — 이미 판정된 사안, 재설계 불필요) |
| **자동 경고(라이선스별 상업 이용 불가 → 생성 차단)** | **집행 게이트가 0건** — `copyright_gradient.md` §4.2가 명령한 `pool` 필드(콘텐츠 풀 분리) 자체가 코드·스키마 어디에도 없다(전수 grep 무일치). CI `policy-guard` 잡은 출판사명 문자열 패턴만 검사, 라이선스 필드 결손은 보지 않는다. 코퍼스 사이드카 결손도 있었으나(문제은행 v0 6종은 `S3-11-problem-bank-data-card`가 별도 미머지 브랜치에서 이미 해소 — §3 D1 참조. 그 태스크 범위 밖인 `problem_bank_probability_finite_v0`·`concept_visualization_v1` 2종은 이번 세션에서 직접 소급 작성) 사이드카는 **집행을 강제하지 않는다** — 존재 여부를 CI가 확인하지 않는 한 언제든 재발 가능 | 🔴 **최대 갭 → D1** |

**42 종합**: 스키마·불변식(`_METADATA_ONLY_SOURCES` validator)은 틀보다 엄격하게 이미 있다.
진짜 갭은 자재가 아니라 **집행**이다 — 사이드카 결손과 `pool` 차단 게이트 부재.

### 모듈 43. 관리자 CMS — **전무, 의도적 지연**

| 문서 항목 | WhyMath 현행 | 판정 |
|---|---|---|
| 관리 가능 항목(교육과정·개념·문제·오개념·사용자·통계·로그·권한 등) | 각 도메인 API(`api/concepts.py`·`api/problems.py` 등)는 실재하나 **단일 관리자 콘솔**은 없음 — DB 직접 조회로 운영자 1인 감내 중 | 🚫 §2-④ |
| 관리자 권한 계층(Super Admin→교육과정 관리자→…) | 역할(role)·권한(permission) 모델 0건(`schema/user.py` 전수 확인) | 🚫 §2-④ (48과 커플링) |
| 승인 Workflow(작성→검토→승인→배포) | 콘텐츠 축은 수용 게이트(`l3/equivalent/acceptance.py`)가, 백로그 축은 CLI claim/done이 이 역할을 이미 대신함(사람 아닌 기계 워크플로) | ✅ (다른 형태로) |
| 운영 Dashboard(오늘 생성 문제·오류 개수 등) | 없음 — 운영 CLI 산출 리포트(`docs/data/problem_bank_coverage_2026-07.md` 등)가 배치 관측을 대신함 | 🚫 §2-④ |

**43 종합**: 운영자 1인·β 소규모 단계에서 CMS 신설은 과공학(YAGNI) — CLAUDE.md 1인 capacity
가드와 정면 충돌. 재판정 트리거는 §5.

### 모듈 44. 버전 관리 — **module 6~10 review의 기존 판정 승계** (신규 설계 없음)

`knowledge_module_gap_review.md` §2-②가 이미 이 주제를 판정했다: "per-row 버전 필드 없음
— 🚫 의도적 미채택. 버전 정본은 git + 코퍼스 버전(`*_v1`) + `_provenance.json` +
`review_status`". 이 판정은 문제은행·개념 그래프뿐 아니라 **저장소 전체의 콘텐츠 버전
관리 방식**이라 42~50 범위에도 그대로 적용된다 — 재설계하지 않는다.

| 문서 항목 | WhyMath 현행 | 판정 |
|---|---|---|
| 대상별 버전(교육과정→단원→개념→…→DSL) | 코퍼스 세대 접미(`_v0`→`_v1`) + git 커밋 이력 + alembic 69본(스키마 버전) | ✅ (승계) |
| Diff(추가·삭제·수정) | git diff가 정본 — 별도 diff 엔진 없음 | ✅ (승계, git이 충분) |
| Rollback | git revert + alembic downgrade | ✅ (승계) |
| Branch(2022/2025 교육과정 동시 운영) | 플레이북 불변식 5 "Curriculum은 Overlay"(개념 영속·매핑만 교체)가 이미 이 요구를 흡수 — 별도 버전 트리 불필요 | 🚫 §2-⑤ (신규 판정) |
| Release(Beta→Stable→LTS) | `OPS-03`(배포 CD) + 코퍼스 승격 규칙(게이트 통과→코퍼스 편입→노출 적격→실노출, "노출 4단 구분") | ✅ (승계 — 코퍼스 승격이 Release 개념의 실질) |

### 모듈 45. 품질 검증(QA) 엔진 — **도구 성숙, 오케스트레이션 0**

| 문서 검사항목 | WhyMath 현행 | 판정 |
|---|---|---|
| ① 문항 검사(정답·중복·난이도·교육과정 일치) | `harness/corpus_audit_eval.py`(6축 초인간 검증)·`l3/equivalent/acceptance.py`(4종 수용 게이트) | ✅ (틀보다 엄격) |
| ② 수식 검사(MathLive↔LaTeX↔렌더↔역변환 동일성) | `l3/equivalent/canonicalize.py`(SymPy 동치 판정) + `counterexample_fuzz.py`(수치 반례 ≥10,000회) | ✅ |
| ③ 개념 검사(정의·공식·선수학습 누락, 연결 그래프 이상) | `ARCH-11`(subgraph depth 가드, 유예 중) + concept graph reachability 테스트 | ✅ 부분 |
| ④ 오개념 검사(연결·피드백·치료 콘텐츠) | `misconception_crosslinks_v1`·`crosslink_demotion_eval.py` | ✅ |
| ⑤ AI 출력 검사(환각·교육과정 위반·금칙어·개인정보) | `harness/coach_prose_leak_eval.py`(AI 출력 누설)만 존재 — 금칙어·PII·교육과정 위반 검사기는 없음 | ⚠️ 부분 |
| ⑥ UI 검사(모바일·태블릿·PC 스크린샷 비교) | 0건(`src/mobile/test`에 golden 없음) | 🚫 §2-⑥ |
| ⑦ 성능 검사(API·DB·AI 속도·캐시 적중률) | `ops/service_health.py`(`OPS-01`)가 헬스·에러율은 보나 콘텐츠 QA 파이프라인과 연결되어 있지 않음 | ⚠️ 부분 |
| ⑧ 통계 검사(정답률 이상치·이탈) | 0건(실학생 데이터 0 — `S3-01` 이후 사안) | 🚫 §2-⑦ |
| **자동 QA Pipeline(작성→검사 매트릭스→리포트→검토→승인→배포)** | **오케스트레이션 0** — 위 도구들이 각자 CLI로 흩어져 있고, 이들을 조립해 단일 리포트+exit 0/1로 판정하는 층이 없다 | 🔴 **최대 갭 → D2** |

**45 종합**: 검사기 자산은 틀의 요구를 대부분 충족하거나 초과한다(①②④는 틀보다 엄격).
없는 것은 검사기가 아니라 **그것들을 하나의 판정으로 묶는 얇은 조립 층**이다.

### 모듈 46~50. 확장 제안 — **3/5 이미 상환, 2/5 의도적 지연**

| # | 문서 제안 | WhyMath 현행 | 판정 |
|---|---|---|---|
| 46 | 배포(Release) 관리 | `.github/workflows/deploy.yml`(preflight+deploy)·`docker-compose.prod.yml`·`docs/architecture/deployment_cd_runbook.md` = `OPS-03`(done, 2026-07-26) | ✅ 상환 완료 |
| 47 | 감사 로그 | `db/models/audit.py`(`DeletionAudit`, append-only)·`generation_log` 테이블(마이그레이션만, 쓰기 경로 0)·`backlog/events.ndjson`(개발 프로세스 감사) — **콘텐츠·데이터 운영 실행 감사만 공백** | ⚠️ 부분 → **D2 범위에 흡수** |
| 48 | 권한·역할(RBAC) 관리 | role/permission 모델 0건 | 🚫 §2-④ (43과 커플링, 동일 재판정 트리거) |
| 49 | 백업·복구 | `scripts/backup/backup_whymath_pg.ps1`·`docs/architecture/db_backup_dr_runbook.md`·`tests/infra/test_backup_script.py` = `OPS-02`(done, 2026-07-26) | ✅ 상환 완료 |
| 50 | 모니터링·알림 | `ops/service_health.py`·`docs/standards/incident_response_slo.md` = `OPS-01`/`OPS-04`(done, 2026-07-26) | ✅ 상환 완료 |

**46~50 종합**: 첨부 문서가 "확장 제안"으로 얹은 5건 중 3건은 2026-07-26 서비스·운영·관리
3축 검토에서 이미 상환됐다(`docs/reviews/service_ops_mgmt_gap_review_2026-07.md`). 남은
감사 로그(47) 공백은 42의 집행 게이트(D1)·45의 QA 오케스트레이션(D2) 작업이 만드는 실행
흔적으로 자연히 채워지므로 별도 태스크를 만들지 않는다(§3 D2 참조).

---

## §2. 의도적 미채택 판정 (협상 불가 근거)

| # | 틀 제안 | 불채택 근거 |
|---|---|---|
| ① | 저작권 기간(등록일·만료일·갱신) 필드 신설 | **소비처 없는 설계 금지** — 현재 콘텐츠 전량 `WHYMATH_GENERATED`(자체생성)라 기간 개념이 성립하지 않는다. 외부 라이선스 콘텐츠(공공누리 2유형 등)가 실제로 들어올 때 D1의 enum 확장과 함께 재도입 |
| ② | 원본 링크(URL·PDF)의 구조화 저장 | 본문 미보유 정책(`_METADATA_ONLY_SOURCES`)과 충돌 여지 — 평가원·EBS 원본 URL을 구조화 저장하면 "본문 미보유"라는 저작권 방어선이 참조 링크를 통해 우회될 위험. 서술형 `source_citation`으로 충분(현행 유지) |
| ③ | 검수 상태를 "사람이 봤는가"로 관리 | **검증 권위 서열**(초인간 검증 기준 v1) — `problem_bank_gap_review.md` §2-③이 이미 동일 판정("PRD §6.4 모든 답안 사람 검수는 2026-07-10 AI 검수 전환으로 대체"). 재설계 불필요, 그대로 승계 |
| ④ | 관리자 CMS·RBAC 즉시 신설 | **1인 capacity 가드** — 운영자 1인·β 소규모는 DB 직접 조회로 감내 가능. CMS 없이도 도메인 API + 운영 CLI로 운영이 돌아가는 상태에서 신규 대형 모듈 신설은 YAGNI 위반 |
| ⑤ | 교육과정 Branch(2022/2025 동시 운영) 버전 트리 | 플레이북 불변식 5 "Curriculum은 Overlay" — 개념은 영속, 교육과정 매핑(`CurriculumEntry`)만 교체하는 구조가 이미 이 요구를 흡수. 별도 Git-branch류 버전 트리는 truth source를 둘로 만든다(붕괴 연쇄 ④ 유지보수 지옥) |
| ⑥ | UI 스크린샷 골든 비교 신규 도입 | **소비처 없는 설계 금지** — 현재 Flutter 앱 화면 수·변경 빈도 대비 골든 유지비용이 이익보다 큰 단계. 화면 수가 늘고 회귀가 실측되면 재검토 |
| ⑦ | 통계 이상치(정답률·이탈) 검사 신규 도입 | `problem_bank_gap_review.md` D9와 동일 사유 — 실학생 응답이 0인 현재 착수는 입력 없는 파이프라인(dead code). `S3-01` 파일럿 이후 D9 범위에서 통합 설계 |

---

## §3. 설계 D1~D2 (진짜 갭의 WhyMath 정합 설계)

우선순위: **저작권 집행(D1) → QA 오케스트레이션(D2)**. 저작권은 CLAUDE.md 의사결정 우선순위
2위(학생 안전 다음)이고, 파일럿(`S3-01`)에 실학생이 들어오기 전 필요한 최소 안전망이다.

### D1. 콘텐츠 출처·라이선스 집행 게이트 (S3-11 병행 + `ARCH-20` 신규)

**갭**: ⑴ 코퍼스 사이드카 결손 — 학생에게 실제 노출되는 v0 문제은행 6종(`problem_bank_
{conceptual,generated,killer,misconception_mc,probability_finite,rephrased}_v0`) 전부와
`concept_visualization_v1`. ⑵ `copyright_gradient.md` §4.2가 명령한 `pool` 필드 기반 CI/파이프라인
차단 게이트가 0건(전수 grep 무일치) — CI `policy-guard`는 문자열 패턴만 검사. ⑶ `content_provenance`/
`generation_log` 테이블은 alembic까지 배포됐으나 ORM 쓰기 경로가 0건(`schema.ContentProvenance`는
`l1/problem_bank/populate.py`·14개 L3 생성기에서 **인메모리 검증 자재**로만 쓰이고 영속화되지
않는다) — 검증은 실행되나 흔적은 안 남는다.

**⑴은 이미 진행 중 — 중복 착수 회피**: `problem_bank_gap_review.md`(모듈 18~22, 2026-07-29)의
D1이 이 갭을 먼저 설계해 `S3-11-problem-bank-data-card`로 등재했고, 이 태스크는 **현재 다른
미머지 브랜치(`claude/education-os-architecture-mr0fbq`)에서 이미 완료(done)** 상태다(`backlog.py
start S3-11-...`를 이 세션에서 실제로 시도해 원격 done 감지로 착수 거부됨 — HARN-11 미머지
done 필터가 정상 작동). 그 브랜치 diff 실측 결과 문제은행 v0 6종 + `problem_bank_v1` 전부에
이미 `_provenance.json`과 데이터 카드(`docs/data/problem_bank_corpus_v1.md`)·licensing_safety.md
갱신이 포함돼 있다 — **이 세션에서 재작성하지 않는다**(머지되면 자동 해소).

**이번 세션에서 직접 완료(⑴의 잔여 — S3-11 범위 밖 2종)**: `problem_bank_probability_finite_v0`
(S4-13이 신설한 별도 코퍼스, problem_bank_gap_review 범위 밖)와 `concept_visualization_v1`
(문제은행이 아니라 시각화 분류 코퍼스)는 그 브랜치 diff에도 없어 진짜 미커버 결손이었다 —
두 코퍼스의 실 레코드(`license`/`source_type`/`generation_type` 또는 시각화 분류 근거) 집계
기반으로 `problem_bank_v1` 정본 형식 그대로 소급 작성했다.

**신규 설계(⑵⑶ — S3-11 범위 밖, 전 코퍼스 대상 집행 게이트)**:
- **사이드카 계약 고정**: `_provenance.json` 필수 필드를 Pydantic 모델로 계약화(`schema/corpus_
  provenance.py`) — 기존 v1 사이드카 키(`corpus_name`/`record_count`/`source_citation`/
  `license_notice`/`copyright_rail`) 정본화 + `pool`(`whymath-original`/`external-sharealike`/
  `external-licensed`) 필드 추가(§4.2 미이행 명령 이행).
- **감사 CLI 신설**: `ops/provenance_audit.py` — `data/corpus/*` 전수 순회 → 사이드카 존재·
  스키마 적합·레코드 레벨 `license`/`source_type` 결손·메타전용 출처 위반 검사 → exit 0/1
  (`ops/live_preflight.py` CLI 형태 답습). 이 CLI의 실행 자체가 §1 모듈 47(감사 로그)이
  요구하는 "콘텐츠 운영 실행 감사"의 첫 소비처가 된다 — append-only 리포트 로그로 겸용.
- **CI 배선**: `policy-guard` 잡에 스텝 추가 + `tests/infra/`에 배선 실재성 테스트
  (`test_infra_lint_wiring.py` 패턴 — "존재함 ≠ 돌아감" 반복 사고 방어, OPS-03/10/11 선례).
- **변별력 검증 의무**: 사이드카 소급 작성 *전* 상태를 재현해 CLI가 exit 1(결손 검출)을
  실측하고, 작성 후 exit 0을 실측한다 — 성공/실패 양쪽 같은 값을 내면 위장이다.
- **enum 확장은 이번엔 보류(YAGNI, §2-①과 동일 논리)** — 소비처(외부 라이선스 실적재)가
  생길 때 alembic과 함께 `LicenseType`에 공공누리/CC 세분화를 추가한다.
- **provenance 테이블 쓰기 경로는 이번 스코프 밖**(⑶) — 감사 CLI가 "검증은 실행되나 DB
  미영속" 사실 자체를 리포트에 명시하는 것으로 1단계는 충분. 실제 영속이 필요해지는 시점
  (감사·재현성 요구 발생)에 별도 판단.

**구현 완결 기록(2026-07-30, `ARCH-20`)**: 위 설계를 그대로 구현했다. 다만 실제 코퍼스 19개를
전수 조사해 이질성을 재확인한 뒤(설계 단계의 "기존 v1 뱅크 키 정본화"보다 훨씬 자유로운 형태 —
`corpus_name`조차 3/19만 보유) `schema/corpus_provenance.py`의 계약을 **최소 공통분모**로
좁혔다: `pool` 필수 + `source_citation`/`license_notice` 중 최소 1건, `extra="allow"`(코퍼스별
자유 서술은 갈아엎지 않음 — 과공학 회피). `pool: "whymath-original"`을 실존 사이드카 19개
전부에 백필(전량 자체생성/NCIC 공공누리1유형 사실정보 인용 — Share-Alike 오염 사례 없음).
CI 배선은 `policy-guard`가 아니라 `backend` 잡에 넣었다 — `policy-guard`는 Python 셋업이
없고 문자열 grep 전용이라, 이미 Pydantic·백엔드 의존성이 설치된 `backend` 잡의 기존 게이트
스텝(`defect_detection_eval` 등) 뒤에 자연스럽게 이어 붙였다. 그랜드파더 목록(`_KNOWN_GAPS`)으로
S3-11이 다루는 문제은행 v0 5종의 사이드카 부재를 신규 위반으로 재선언하지 않는다(사유 명시,
S3-11 랜딩 시 수동 제거 — HARN-10류 grandfather 선례 동형). **변별력 실측**: 백필 전 CLI
실행 → exit 1·위반 19건(전 코퍼스 `pool` 결손) → 백필 후 재실행 → exit 0. 테스트 22건 신규
(`tests/backend/schema/test_corpus_provenance.py` 10 · `tests/backend/ops/test_provenance_audit.py`
12) + `tests/infra/test_provenance_audit_wiring.py` 2건(배선 실재성). 부수 발견: 도크스트링에
`concept_graph_v1`을 예시로 직접 언급했더니 `test_legacy_snapshot_governance.py`의 AST
문자열-리터럴 스캐너(주석 제외를 표방하나 docstring은 걸러내지 못함)가 오탐 — 일반화된
표현으로 재작성해 해소(검사기 자체는 이 태스크 범위 밖이라 손대지 않음).

### D2. QA 파이프라인 오케스트레이터 (`ARCH-21` 신규)

**갭**: §1 모듈 45 — 38개 harness 검사 모듈이 각자 CLI로 흩어져 있고 이들을 조립해 단일
판정(승인/반려)을 내는 층이 없다. "자동 QA Pipeline"(작성→검사→리포트→검토→승인→배포)에
대응하는 실행 경로가 0.

**설계**: 새 검사기를 만들지 않고 기존 자산을 조립하는 얇은 층 — `harness/qa_pipeline.py`.
- 재사용(전부 기존): `corpus_audit_eval`(문항 감사·①) · `l3/equivalent/canonicalize`(수식
  동치·②) · concept graph reachability(③) · `crosslink_demotion_eval`(오개념·④) ·
  `coach_prose_leak_eval`(AI 출력 누설·⑤ 일부) · D1의 `provenance_audit`(저작권 축, 문서의
  ①에 없던 축이나 WhyMath 우선순위상 필수 추가) · `wilson.py`(경계 판정) ·
  `defect_detection_eval.py`(결함주입 강등전).
- **없는 축은 만들지 않고 "미측정"으로 리포트에 명시** — UI 골든(§2-⑥)·통계 이상치(§2-⑦)·
  금칙어/PII(⑤ 잔여)·성능 연동(⑦). 리포트는 "검사 안 함"과 "통과"를 절대 혼동하지 않는다
  (침묵 통과 금지 — CLAUDE.md AI·신뢰).
- 산출: 단일 JSON QA 리포트(코퍼스/배치 단위) + Wilson 단측 경계 게이트 exit 0/1. CI 배선은
  `data-pipeline` 잡에 옵션 스텝으로(무거운 배치라 상시 실행은 아님 — 코퍼스 변경 시 트리거).

---

## §4. 정직한 공백 — 지금 하지 않는 것 (사유 명시)

| 공백 | 사유 | 해소 시점 |
|---|---|---|
| UI 스크린샷 골든 비교 | 소비처 없음(§2-⑥) | Flutter 화면 수·회귀 빈도가 유지비용을 정당화할 때 |
| 통계 이상치(정답률·이탈) 검사 | 실학생 응답 0 — `problem_bank_gap_review.md` D9와 동일 사유 | `S3-01` 이후 D9 범위에서 통합 |
| 금칙어·PII 자동 검사 | 전용 검사기 없음(coach_prose_leak_eval은 프롬프트 누설만 대응) — 별도 설계 필요, 이번 D1/D2 스코프 밖 | 실 학생 대화 데이터 축적 후 우선순위 재평가 |
| `content_provenance`/`generation_log` 테이블 실영속 | 감사 CLI(D1)로 1단계 충분 — 소비처(재현성 감사 요구) 미실증 | 감사·재현성 요구가 실측될 때 |

---

## §5. 실행 — 이번 세션 즉시 완료 + 백로그 등재

### 이번 세션에서 완료(태스크 등재 없이 직접 실행)

- `data/corpus/{problem_bank_probability_finite_v0,concept_visualization_v1}/_provenance.json`
  2건 소급 작성(실 레코드 집계 기반, 예외 0 확인 — 다른 미머지 브랜치가 다루는 문제은행 v0
  6종과 겹치지 않음을 diff로 재확인).
- `S3-11-problem-bank-data-card`는 **착수하지 않음** — 다른 세션이 이미 완료(미머지). 그 브랜치가
  머지되면 문제은행 축 사이드카·데이터 카드 공백은 자동 해소된다.

### 백로그 신규 등재 (실제 ID는 `backlog.py add`가 배정 — 번호 추론 금지, HARN-10 준수)

- **`ARCH-20-content-provenance-enforcement-gate`**(D1 집행 게이트 — `schema/corpus_provenance.py` +
  `ops/provenance_audit.py` + CI 배선) — stage S3 · priority 2 · track infra-debt.
- **`ARCH-21-qa-pipeline-orchestrator`**(D2 QA 오케스트레이터 — `harness/qa_pipeline.py`,
  ARCH-20 의존) — stage S4 · priority 3 · track infra-debt.

### 재판정 트리거 (등재하지 않는 것)

| 항목 | 트리거 |
|---|---|
| 43 관리자 CMS · 48 RBAC | 결제 도입(Phase 2) 또는 운영자 2인 이상 또는 CS 문의 유입 개시 |
| 저작권 기간·사용범위 세분 필드(§2-①) | 외부 라이선스 콘텐츠(공공누리 2유형·CC BY-SA 등) 실적재 결정 |
| UI 골든·통계 이상치(§2-⑥⑦) | 화면 수/회귀 빈도 실측 또는 `S3-01` 파일럿 완료 |

---

## 부록 — 실측 근거·관련 코드 (2026-07-29 실측)

- 코퍼스 사이드카 전수 확인: `for d in data/corpus/*/; do [ -f "$d/_provenance.json" ] || echo MISS
  "$d"; done` — 이 세션 실행 당시 결손 7종. 그중 문제은행 v0 6종은 `S3-11`이 다른 미머지
  브랜치에서 이미 해소(diff 실측 확인), 잔여 2종(`problem_bank_probability_finite_v0`·
  `concept_visualization_v1`)은 본 문서 §3 D1에서 이번 세션이 직접 작성.
- `pool` 필드 부재: `grep -rn "pool" schema/ l1/ data-pipeline/` 전수 무일치.
- provenance ORM 쓰기 경로 부재: `grep -rn "from whymath_backend.db.models.provenance"
  src/backend/whymath_backend/` — `db/models/__init__.py` 재수출 외 소비처 0건.
- 라이선스 enum: `schema/enums.py:443`(`LicenseType` 6종) · `schema/enums.py:1031`
  (`CurriculumLicense` 5종) — 서로 다른 축, 공공누리 세유형·CC 미표현.
- admin/role 부재: `src/backend/whymath_backend/api/`(18개 라우터, admin 없음) ·
  `schema/user.py`(role/permission 필드 없음).
- QA 도구 인벤토리: `src/backend/whymath_backend/harness/*.py`(38모듈, `__init__` 제외) ·
  `src/backend/whymath_backend/ops/*.py`(6모듈).
- 46·49·50 상환 증거: `.github/workflows/deploy.yml` · `scripts/backup/backup_whymath_pg.ps1` ·
  `src/backend/whymath_backend/ops/service_health.py` — 전부 `docs/reviews/service_ops_mgmt_
  gap_review_2026-07.md`(2026-07-26)에서 `OPS-01~04`로 이미 등재·완료.
- 44 기존 판정 원문: `docs/architecture/knowledge_module_gap_review.md` §2-②("per-row 버전
  필드 없음 — git+코퍼스 버전+provenance+review_status가 정본").
- 기존 추적 승계(중복 등재 금지 대장): `S3-11-problem-bank-data-card`(D1의 문제은행 사이드카·
  데이터 카드 부분 — 다른 미머지 브랜치에서 이미 완료, 이 문서는 착수하지 않음) ·
  `problem_bank_gap_review.md` D9/`S4-15`(실응답 통계 — §4 공백과 동일 사유) ·
  `S3-01-pilot-cohort`(D9·§2-⑦ 잠금 게이트).
- 근접 중복 회피 경위(HARN-11 실측 재확인): 이 세션이 `S3-11-problem-bank-data-card`를
  착수 시도했으나 `backlog.py start`가 원격 done을 감지해 거부 — 로컬 백로그 사본은 여전히
  `todo`(그 브랜치가 미머지라 트렁크 사본 미갱신)였으나 하네스가 원격 브랜치 사본을 조회해
  실제 완료 상태를 잡아냈다. 착수 전 CLI 실행이 근접 중복 실행을 막은 사례.
