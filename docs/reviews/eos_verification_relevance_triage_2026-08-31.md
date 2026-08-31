# EOS 12월 검증 관여도 트리아지 — 잔여 182건 전수 판정 (제안)

> **지위**: `G-eos-verification-relevance-triage` **clear 조건 ①·②의 제안본** — 확정이 아니다.
> 판정 권한은 Kiki에게 있고, 이 문서는 그 판정을 받기 위한 재료다(게이트 kind=decision·assignee=kiki).
> **근거 조항**: 선언 정본 §6-5("12월 검증 비관여분은 폐기가 아니라 '검증 비관여' 표시로 이월 판정 — EOS-53 → G0") · §0-5(신규 기능 게이트). 이 절차가 미실시인 채 G0이 clear된 것이 감사 **A2**다(`docs/reviews/eos_transition_plan_compliance_audit_2026-08-31.md`).
> **작성**: 2026-08-31 · main `33c51b7f` 기준

---

## §0. 요약

잔여 **182건**(todo + blocked, 전 스테이지) 전수 판정. 표본이 아니다.

| 판정 | 건수 | 뜻 |
|---|---|---|
| **R — 관여** | **66** | 12월 검증(G1~G5 차단 조건 또는 KPI 산출)에 직접·전제로 기여 |
| **N — 비관여** | **103** | 2027 이월. **폐기가 아니다**(선언 §6-5 명문) |
| **? — 유보** | **13** | Kiki 판정 필요 — 법령·사람 결정·본 게이트의 대상 자신 |

**가장 중요한 수치**: 잔여의 **57%가 비관여**다. 지금 `backlog.py next`는 이 103건을 12월 직결 작업과 같은 우선순위 평면에서 계산하고 있다 — A2가 방치되면 남은 17주 동안 `/drive`가 뽑는 태스크의 절반 이상이 검증에 기여하지 않는다.

## §1. 판정 기준 (선언 부록 E 게이트 차단 조건에서 도출)

**R로 판정한 근거 축** — 아래 중 하나에 해당:

1. **G1~G5 차단 조건 자체** (앵커 E2E·HIT 계측·CU 물량·누설 0·메타 누락 0·학생 표본)
2. **기술/내용 KPI 12종의 산출 경로** (HIT·자동검증률·재작업률·처리량·단위비용·실패분포 / 오류율·정합률·난이도 타당도·오개념 연결·비약 지적률·힌트 누설)
3. **불변 계약** (SymPy 단일 권위·학생 제공 전 검증·Langfuse 추적·미성년 PII·저작권 레일 — 선언 §0-6)
4. **앵커 6개의 자산**(성취기준·개념·오개념·문항·기계판정 채널) — 대학 앵커 A7·A8분은 제외(EOS-51 §1-1 이월 확정)
5. **하네스 전제** — 완료분 소실·중복 구현·번호 충돌을 막는 축. 직접 기여는 아니나 *17주치 작업의 보존율*을 결정한다
6. **회수(recovery)** — 이미 만들어졌는데 고립된 완료분. 신규 개발이 아니므로 §0-5 신규 기능 게이트 대상도 아니다

**N으로 판정한 대표 군**: 타과목 E축(11건) · 랜딩/마케팅/배포 · 결제·구독·테넌시 · 백오피스 확장 · 학생 표출·접근성 확장 · 성능 최적화 · 리텐션/게임화 · 대학 콘텐츠(앵커 이월과 연동).

## §2. 전수 판정표

`축` = R의 근거(계획서 항목코드 또는 KPI축) / N의 이월 사유군. ★ = 검증설계서 §8이 집행 지점으로 명시 지목한 태스크.

| 태스크 | 상태 | stage | 판정 | 축 | 사유 |
|---|---|---|---|---|---|
| `ADMIN-05-bff-readonly` | todo | S4 | **R** | F4 | Admin BFF에 검수 큐 조회가 포함 — ADMIN-07의 서버 축 |
| `ADMIN-06-admin-web-shell` | todo | S4 | **R** | F4 | 백오피스 셸 = ADMIN-07 진입점(자인) |
| `ADMIN-07-review-ui` | todo | S4 | **R** | F4★ | 휴먼 검수 워크벤치 그 자체 — HIT 타이머·반려코드 강제의 집행 지점(EOS-54 accept③ 고아 상태) |
| `ADMIN-09-profile-collection-inventory-contract` | todo | S4 | **R** | I3 | 학생 표본 20~30명 수집 시 PII 수집이 실제 발생 — 대장 없이 수집 불가 |
| `ARCH-11-subgraph-depth-guard` | blocked | S1 | **R** | 플레이북 | Minimal Subgraph depth≤2 — 생성이 그래프 컨텍스트를 쓰는 순간 AI 추론 실패 방어선(불변식) |
| `ARCH-23-qa-gate-enforcement` | todo | S3 | **R** | D2★ | QA 게이트 fail-open 해소 — 검증설계서 §4·§8이 실패코드 자동부여 집행 지점으로 지목 |
| `ARCH-31` | todo | S4 | **R** | F5 | Content Version 분리 — Run 재현성·버전 스냅샷(EOS-44/47 계열) |
| `ARCH-32` | todo | S3 | **R** | A4 | Source 엔티티 분리 — 저작권 원장 3종 축 |
| `ASM-06-distractor-misconception-reverse-link` | blocked | S4 | **R** | 내용KPI | 오답 선택지→오개념 역링크 — op-code 라벨 정확도·실오답 매칭 KPI의 재료 |
| `CONT-04-rephrased-corpus-type-tagging-completion` | todo | S4 | **R** | B7 | rephrased 429문 유형 태깅 — 문항 코퍼스 자산 |
| `CUR-06-cross-school-prerequisite-connectivity` | todo | S4 | **R** | F2 | 학교급 경계 선수 연결 — F2(3개 학교급 관통 체인) 계측기 |
| `CUR-07-achievement-standard-schema-extension` | todo | S3 | **R** | B4 | AchievementStandard 확장 — 앵커 성취기준 자산 |
| `CUR-09-eos-unit-structure-review-adoption` | todo | S3 | **R** | B1/B2 | EOS 단원 구조 — 앵커가 트리 실노드로 존재해야 함(B2 DoD) |
| `EOS-28-answer-form-contract` | todo | S3 | **R** | E2 | 답 형태 계약 — 채점 변별(깊이앵커 폐쇄루프) |
| `EOS-47-attempt-version-pinning` | todo | S4 | **R** | E3 | problem_attempt 버전 고정 — W2 되돌릴 수 없는 스키마 |
| `EOS-49-concept-version-contract` | todo | S3 | **R** | 버전규율 | ConceptVersion 계약 — Event Envelope 버전 규율 |
| `EOS-50-publish-gate-pipeline` | todo | S3 | **R** | D1★ | Publish Gate — Draft→Publish 검증 파이프라인 |
| `EOS-56-anchor-set-registration` | todo | S3 | **R** | F1★ | 앵커 세트 1급 등록 — G0 확정 세트의 DB 인스턴스화 |
| `EOS-58-anchor-e2e-generation-proof` | todo | S3 | **R** | G1★ | 앵커 A4 생성→검증→검수큐 E2E — G1(9/27) 차단 조건 그 자체 |
| `EOS-59-data-grade-routing-policy` | todo | S3 | **R** | A5 | 데이터 등급 라우팅 — AI Hub 국외 반출 무해화(선언 §6-3 전제) |
| `EOS-63-attempt-skill-event-consumption` | todo | S3 | **R** | E3 | skill_ids 소비 전환 — EOS-57 승계 |
| `HARN-22-id-number-suggestion-race` | todo | S4 | **R** | 하네스 | 번호 예약 부재 — 병렬 세션 실충돌(작업 손실 경로) |
| `HARN-24-task-acceptance-amend-cli` | todo | S4 | **R** | 하네스★ | acceptance amend + requires_gates 부착 경로 — 본 게이트의 집행 수단 자체가 이것에 막혀 block 우회 중 |
| `HARN-28-isolation-scan-shallow-relocation` | todo | S4 | **R** | 하네스 | 고립 스캔이 CCR에서 구조적으로 꺼짐 — 완료분 소실 경로(5회차 방지) |
| `HARN-30-pr-delivery-state-observability` | todo | S4 | **R** | 하네스 | PR 배송 상태 미관측 — 미머지 고립의 직전 단계 |
| `HARN-31-doneless-isolation-blindspot` | todo | S3 | **R** | 하네스 | done 표기 없는 브랜치 항구 무시 — 고립 사각 |
| `HARN-33-gates-yaml-blockscalar-preserve` | todo | S4 | **R** | 하네스 | gates.yaml 라운드트립이 notes 파손 — G1~G5 집행 수단의 무결성 |
| `HARN-37-ported-classification-false-positive` | todo | S3 | **R** | 하네스 | '이미 포팅됨' 오분류 2회차 — 갭 판정 오류율 |
| `HARN-38-eos-number-collision-renumber` | todo | S3 | **R** | 하네스★ | EOS 번호 충돌 3회차 — EOS-49/50/51 동번호 이종 |
| `KG-02-concept-content-review-promotion` | blocked | S4 | **R** | 내용KPI | 이론 콘텐츠 검수 승격(AI 자기승인 금지) — 인간 검수 축 |
| `LIC-03-provenance-enforcement-layer-decision` | blocked | S3 | **R** | G1★ | provenance 강제 집행 지점 — 'provenance 없는 AI 생성물 INSERT 거부'(A4·G1 DoD) |
| `MATH-04-curriculum-notation-range-gate` | todo | S4 | **R** | 내용KPI | 교육과정 표기 범위 게이트 — 표기 커버리지 |
| `MISC-07-anchor-machine-detection-channels` | todo | S3 | **R** | B6★ | 앵커 커버 오개념 기계판정 채널 — 검증설계서 §8 집행 지점(현재 커버 0) |
| `MISC-18-match-gate-single-enforcement` | todo | S3 | **R** | 내용KPI | 오개념 품질 게이트 단일 집행 — floor 0.65 주경로 미적용 |
| `MOB-18-issues-review-nonsecurity-recovery` | todo | S3 | **R** | 회수 | k20m0w 고립 done 15건 회수 — 완료분 소실 방지 |
| `OPS-19-observability-report-runner-wiring` | todo | S4 | **R** | 계측 | 리포트 11개 중 10개 러너 0건 — '미측정'이 '문제없음'으로 읽히는 구조(§6-6) |
| `OPS-27-quality-worker-container-deploy` | todo | S4 | **R** | C1 | QUALITY 비동기 워커 미배포 — 202 작업 영구 pending(생성 파이프라인 정지) |
| `OPS-36-wh1-llm-observability-cache-wiring` | todo | S4 | **R** | 비용KPI | WH-1 LLM 관측·캐시 결선 — 단위비용 KPI의 표본 복구 |
| `OPS-38-ci-gate-reachability-contract-recovery` | todo | S4 | **R** | 회수 | OPS-19 완료분 회수(q8tvcx) |
| `OPS-40-service-ops-r2-recovery` | todo | S3 | **R** | 회수 | 서비스 운영 r2 회수(5t5lmv) |
| `OPS-41-doc-fleet-pr-backfill` | todo | S3 | **R** | 회수 | 설계문서 fleet 5건 PR 백필 — 고립 해소 |
| `OPS-53-cp949-cli-output-safety-audit` | todo | S3 | **R** | 계측 | cp949 CLI 크래시 — 측정 회차 공전 방지(2026-08-22 규칙) |
| `OPS-54-policy-guard-source-patterns` | todo | S3 | **R** | G2★ | policy-guard 금칙 소스 확장 — EBS·평가원 검출(G2 DoD) |
| `OPS-55-integrity-violations-gate` | todo | S3 | **R** | H2★ | 무결성 게이트 6종 — G3 '메타 누락 0' 차단 조건 |
| `OPS-56-weekly-metrics-cron` | todo | S3 | **R** | H4★ | 주간 7지표 cron — 검증설계서 §6이 인용원 |
| `PB-02-declaration-wiring-reconciliation` | todo | S3 | **R** | 상시성 | 선언≠배선 봉합 + 커버리지 리포트 재생성 CI |
| `PB-08-public-catalog-exposure-contract` | todo | S3 | **R** | G3 | 공개 카탈로그 노출 계약 — pending 158건·정답 노출(publish 허용 매트릭스 축) |
| `PB-09-variant-three-modes-activation` | todo | S4 | **R** | C4 | 변형 3종 발화 — 변형문제 생성 |
| `PB-10-difficulty-loop-wiring-observability` | todo | S4 | **R** | D3 | 난이도 갱신 루프 — 난이도 타당도 KPI의 계측기 |
| `PED-26-gdmwhk-catalog-recovery-reconciliation` | todo | S4 | **R** | 회수 | 교수전략 카탈로그 3차 완성본 회수 — 4차 중복 구현 차단 |
| `PED-27-harness-metrics-operator-gate` | todo | S3 | **R** | 학생안전 | 원시 대리지표 학생 토큰 봉인 — PED-08 노출 계약 우회로 폐쇄 |
| `PED-28-exposure-contract-serving-crosswalk-gate` | todo | S3 | **R** | 학생안전 | 노출 계약↔서빙 양방향 대조 게이트 |
| `PED-35-hint-fading-ceiling-contract` | todo | S3 | **R** | C7/F8 | 힌트 유도-제공 상한 — 3단계 힌트·누설 무관용 축 |
| `REC-11-candidates-policy-version-persistence` | todo | S3 | **R** | W2★ | candidates[]·policy_version 영속 — W2 되돌릴 수 없는 스키마 ②(소급 불가) |
| `S1-16-subject-neutral-content-contract` | todo | S1 | **R** | A2★ | Subject-neutral Content Contract — 선언 §3.2-③ W1 항목(9/2 예정) |
| `S3-24-shadow-recovery-bucket-b` | blocked | S3 | **R** | 회수 | 미머지 회수 버킷 B |
| `S3-25-shadow-recovery-bucket-c` | todo | S3 | **R** | 회수 | 미머지 회수 버킷 C |
| `S3-28-canonicalize-answer-kind-scope-audit` | todo | S3 | **R** | B7 | condition_dsl 오탐 130건 판정 — 코퍼스 품질 |
| `S4-11-hint-content-generation` | todo | S4 | **R** | CU★ | 힌트 내용 생성 + 영속 — 검증설계서 §3이 지목한 CU 마지막 공백 |
| `S4-16-residue-gate-demotion-battle` | blocked | S4 | **R** | 검증권위 | 잔여 축 게이트 강등전 — 기계 게이트 승격 절차 |
| `S4-54` | todo | S4 | **R** | A3 | SymPy 불가 영역 verifier v2 — A3(비대수 기준선 앵커)의 검증 대안 |
| `S4-55` | todo | S4 | **R** | A3 | Verification Tier 개편 — 동 |
| `S4-56` | todo | S4 | **R** | A3 | Cross-Verify v2 CLI·Wilson 게이트 — 동 |
| `S4-57` | todo | S4 | **R** | A3 | 단계 B 도메인 발화 조건 — 동 |
| `S4-58` | todo | S4 | **R** | A3 | statistical_claim DSL — A3 확률·통계 앵커 |
| `SEC-19-generate-rate-limit` | todo | S4 | **R** | 비용KPI | /v1/generate 레이트리밋 — 유일한 무제한 LLM 비용 표면 |
| `CUR-11-subject-neutral-curriculum-api` | blocked | S3 | **?** | 게이트대상 | 본 게이트의 판정 대상 4건 중 하나(실구현·라우터 5종) |
| `CUR-12-curriculum-alignment-unified-view` | blocked | S3 | **?** | 게이트대상 | 본 게이트의 판정 대상(서빙 소비처 리팩토링) |
| `CUR-17` | blocked | S3 | **?** | 게이트대상 | 본 게이트의 판정 대상(설계 — concept resolve는 관여 여지 큼) |
| `CUR-18` | blocked | S3 | **?** | 게이트대상 | 본 게이트의 판정 대상(설계) |
| `MGMT-01-guardian-real-verification` | blocked | S3 | **?** | 법령 | 법정대리인 실 본인확인 — 변호사 자문 선행(기계 대체 금지 항목) |
| `MGMT-02-terms-privacy-policy-counsel` | blocked | S3 | **?** | 법령 | 약관·처리방침 문안 — 변호사 검토(Kiki 재판정 대상·선언 §6-3) |
| `OPS-31-backup-encryption-offsite-schedule` | todo | S4 | **?** | PII | 백업 암호화·오프사이트 — 미성년 PII 불변 계약 축(게이트 2건 이미 pending) |
| `OPS-48-quality-tier-moe-accuracy-battle` | todo | S4 | **?** | 처리량KPI | MoE 정확도 대조 — 처리량 30 CU/h·단위비용 250원 KPI에 직접 영향 |
| `OPS-50` | todo | S5 | **?** | F1 | MoE 파싱 실패율 16% — F1(수식·파싱) 실패분포에 직결 |
| `PED-34-cognitive-load-prompt-principle` | todo | S3 | **?** | C9/F7 | 인지부하 프롬프트 원칙 — C9 연령별 설명·F7(언어 수준) KPI와 접점 |
| `REC-07-grading-authority-transfer-decision` | todo | S3 | **?** | 사람결정 | 채점 권위 이관 — Kiki 결정(REC-08 게이트 입력) |
| `S3-01-pilot-cohort` | todo | S3 | **?** | I3 | 파일럿 코호트 — G4 '학생 표본 ≥20명' 차단 조건이나 착수 트리거 4종 미충족 |
| `SEC-31-student-work-envelope-encryption` | todo | S3 | **?** | PII | 학생 답안 봉투 암호화 — 미성년 PII 불변 계약(학생 표본 수집 시 발화) |
| `ADMIN-02-dead-tenancy-billing-columns` | blocked | S4 | N | 이월 | 결제·구독 축 — 2027 범위(선언 §0-2) |
| `ADMIN-04-module-registry` | todo | S4 | N | 이월 | 백오피스 모듈 레지스트리 — 검수 워크벤치와 별개 운영 확장 |
| `ADMIN-10-audit-event-foundation` | todo | S4 | N | 이월 | 공통 audit_event 기반 — 운영 축 |
| `ARCH-30-coding-e-axis-design-recovery` | todo | E1 | N | E축 | 코딩/정보 E축 — 타과목 |
| `ARCH-33` | todo | S3 | N | 이월 | Learner/User 역할 분리 — 운영·권한 축 |
| `ARCH-34` | todo | E1 | N | E축 | Subject ontology 타과목 확장 |
| `ARCH-35` | todo | E2 | N | E축 | External ID Registry(Phase 2) |
| `ASM-10-test-set-attribution-observability` | todo | S3 | N | 이월 | 조립 세트 귀속 관측 |
| `ASM-11-assessment-seat-student-reach` | todo | S4 | N | 이월 | 평가 좌석 학생 도달 |
| `COLLAB-05-access-matrix-reference-integrity` | todo | S3 | N | 이월 | 권한 매트릭스 참조 무결성 |
| `COLLAB-06-learning-metrics-freshness-signal` | todo | S4 | N | 이월 | 학습지표 롤업 신선도 |
| `CONT-02-concept-content-audit-axis-disposition` | todo | S4 | N | 이월 | 개념 콘텐츠 감사 축 거취 |
| `CONT-03-deferral-trigger-expiry-contract` | todo | S4 | N | 이월 | 유예 트리거 만료 계약 — 프로세스 위생(직결 아님) |
| `CUR-13-learning-outcome-fields-extension` | todo | S3 | N | 이월 | Learning Outcome/Competency 필드 확장 |
| `CUR-14-case-1-1-mapping-document` | todo | S3 | N | 이월 | 1EdTech CASE 외부 교환 — 대외 상호운용 |
| `DP-02-analytics-event-envelope` | todo | S4 | N | 이월 | 분석 이벤트 envelope |
| `DP-03-attempt-event-idempotency` | todo | S4 | N | 이월 | attempt_event 멱등성 |
| `DP-04-event-contract-governance` | todo | S4 | N | 이월 | 이벤트 계약 거버넌스 |
| `E1-01-dimensional-consistency` | todo | E1 | N | E축 | 물리 E축 |
| `E1-02-problem-subject-area` | todo | E1 | N | E축 | Problem.subject_area — 타과목 전제 |
| `E1-03-phy-area-registration` | todo | E1 | N | E축 | 물리 AREA 등록 |
| `E1-04-physics-misconception-seed` | todo | E1 | N | E축 | 물리 오개념 시드 |
| `E1-90-earth-science-placement` | todo | E1 | N | E축 | 지구과학 배치 결정 |
| `E2-01-chemistry-pack` | todo | E2 | N | E축 | 화학 팩 |
| `E3-01-biology-pack` | todo | E3 | N | E축 | 생물 팩 |
| `E4-01-history-social-pack` | todo | E4 | N | E축 | 역사·사회 팩 |
| `E5-01-korean-pack` | todo | E5 | N | E축 | 국어 팩 |
| `E6-01-english-pack` | todo | E6 | N | E축 | 영어 팩 |
| `FAB-02-fabric-audit` | todo | E1 | N | E축 | fabric 수렴 감사 — 교차 과목 |
| `HARN-25-doc-series-suffix-blindspot` | todo | S4 | N | 하네스 | 문서 접미어 사각 — 소형 |
| `HARN-32-merge-race-ci-duration-vs-main-cadence` | todo | S4 | N | 하네스 | CI 소요 vs main 머지 간격 경합 — 불편이지 손실 아님 |
| `KG-04-graph-analytics-artifact-landing` | todo | S4 | N | 이월 | 그래프 분석 리포트 아티팩트 |
| `KG-05-university-content-mechanical-pattern-fix` | todo | S4 | N | 이월 | 대학 콘텐츠 손질 — 대학 앵커 A7·A8은 2027 이월 확정(EOS-51 §1-1) |
| `KG-06-concept-content-depth-enrichment` | todo | S5 | N | 이월 | 이론 콘텐츠 깊이 보강(S5) |
| `MISC-01-visualization-shadow-rollout` | todo | S3 | N | 이월 | 시각화 게이트 결선 |
| `MISC-02-prerequisite-coaching-misconception-link` | blocked | S4 | N | 이월 | 선수학습 복습↔오개념 연동 |
| `MISC-03-misconception-similar-problem-serving` | todo | S3 | N | 이월 | 유사문제 실시간 서빙 |
| `MISC-05-root-symptom-slip-observation-report` | todo | S4 | N | 이월 | root/symptom·slip 관측 리포트 |
| `MISC-06-misconception-recurrence-signal` | todo | S4 | N | 이월 | 오개념 재발신호 좌석 |
| `MISC-17-ocr-solution-into-diagnosis` | todo | S3 | N | 이월 | OCR 풀이 → 진단 합류 |
| `MISC-19-analogy-signal-wiring-or-removal` | todo | S4 | N | 이월 | ANALOGY 신호 배선 또는 삭제 |
| `MISC-20-resolution-rate-honesty` | todo | S3 | N | 이월 | 오개념 해소율 정직화 — 학생 노출 축 |
| `MOB-11-return-support-minimal` | todo | S3 | N | 이월 | 복귀 지원 — 리텐션 축 |
| `MOB-16-coaching-time-goal-axis-reach` | todo | S3 | N | 이월 | 코칭 시간·목표축 도달 |
| `NLP-07-ocr-confidence-threshold-canon` | todo | S4 | N | 이월 | OCR 저신뢰 임계 정본화 |
| `NLP-08-partial-credit-seat-disposition` | todo | S4 | N | 이월 | partial_credit 좌석 처분 |
| `OPS-26-vendored-calculator-asset-freshness-gate` | todo | S4 | N | 이월 | 계산기 번들 신선도 게이트 |
| `OPS-28-declared-unwired-audit-blindspots` | todo | S4 | N | 이월 | 감사기 사각 3종 |
| `OPS-30-alerting-last-hop-and-uptime-probe` | todo | S4 | N | 이월 | 업타임 프로브·알림 채널 |
| `OPS-32-backend-dependency-declaration-usage-gate` | todo | S4 | N | 이월 | 의존성 선언↔사용 게이트 |
| `OPS-33-yaml-spec-unwired-audit-axis` | todo | S4 | N | 이월 | yaml_spec 감사 축 |
| `OPS-34-offline-report-recipient-contract` | todo | S4 | N | 이월 | 오프라인 리포트 수취인 계약 |
| `OPS-35-audit-membership-consumption-detection` | todo | S4 | N | 이월 | EVENT 축 멤버십 소비 탐지 |
| `OPS-39-prod-schema-drift-observability` | todo | S4 | N | 이월 | prod 스키마 드리프트 관측 |
| `OPS-42-client-reach-axis` | todo | S3 | N | 이월 | 학생 도달 축 감사기 확장 |
| `OPS-43-local-llm-stack-optimization` | todo | S4 | N | 이월 | 로컬 LLM 스택 최적화 |
| `OPS-47-backend-job-timeout-headroom` | todo | S3 | N | 이월 | backend 잡 타임아웃 여유 |
| `OPS-52` | todo | S3 | N | 이월 | ROCm/llama.cpp 시도 |
| `PATH-03-transitive-ordering-edges` | todo | S4 | N | 이월 | 전이 순서 제약 |
| `PATH-04-learning-path-corpus-ingestion` | blocked | S4 | N | 이월 | 학습경로 코퍼스 677행 |
| `PATH-11-multi-weak-concept-orderability-axis` | todo | S4 | N | 이월 | 다중 약개념 순서화 축 |
| `PATH-12-me-tab-review-queue-consumption` | todo | S3 | N | 이월 | 복습 큐 학생 도달 |
| `PATH-13-target-axis-exposure-decision` | todo | S4 | N | 이월 | 목표축 노출 판정 |
| `PB-04-l6-mode-reach-observability` | todo | S3 | N | 이월 | L6 모드 도달 관측 |
| `PED-14-time-to-mastery-normalization` | todo | S3 | N | 이월 | Time-to-Mastery 정규화 |
| `PED-17-study-generate-fallback-decision` | todo | S4 | N | 이월 | 학습 공급 폴백 결정 |
| `PED-18-tutor-primary-operation-rate` | todo | S4 | N | 이월 | AI 튜터 작동 비율 관측 |
| `PED-19-concept-question-routing-seam` | todo | S4 | N | 이월 | 개념 질의 라우팅 seam |
| `PED-29-antigamification-efficacy-measurement` | todo | S3 | N | 이월 | 반게임화 효능 측정 |
| `PED-31-eos-pedagogy-strategy-library-gap-design` | todo | S3 | N | 이월 | 교수전략 라이브러리 경계 설계 |
| `PED-36-learning-scenario-bank-schema` | todo | S3 | N | 이월 | 학습 시나리오 뱅크 스키마 |
| `PRES-01-segment-body-blocks` | todo | S4 | N | 이월 | 본문 세그먼트 블록 모델 |
| `PRES-02-audience-display-profiles` | todo | S5 | N | 이월 | 대상층×디바이스 표출 프로파일 |
| `PRES-03-student-web-surface` | todo | S5 | N | 이월 | 학생용 웹 표출 착수 판정 |
| `PRES-04-math-aria-speechspec-reuse` | todo | S4 | N | 이월 | 수식 접근성 aria |
| `REC-10-next-problem-honesty-fields-render` | todo | S3 | N | 이월 | 추천 정직 표기 렌더 |
| `RPT-02-defect-report-readout-cli` | todo | S3 | N | 이월 | 결함 신고 판독 CLI |
| `S3-33-coach-answer-input-surface-expansion` | todo | S3 | N | 이월 | 코치 답안 입력면 확장 |
| `S3-34-coach-session-hygiene` | todo | S3 | N | 이월 | 코치 세션 위생 |
| `S4-01-math-k12-complete` | todo | S4 | N | 이월 | 수학 K-12 전면 완성 — 앵커 6개 체제에서 불요 |
| `S4-02-proof-learning-support` | todo | S4 | N | 이월 | 증명 학습 지원 |
| `S4-03-visualization-type-expansion` | todo | S4 | N | 이월 | 시각화 유형 확장 |
| `S4-05-concept-definition-registers` | todo | S4 | N | 이월 | 정의 레지스터 |
| `S4-12-solution-comparison-clustering` | todo | S4 | N | 이월 | 풀이 비교 군집 |
| `S4-15-response-driven-difficulty-loop` | todo | S4 | N | 이월 | 실응답 난이도 루프(파일럿 후) |
| `S4-22-attempt-event-signal-consumer-wiring` | todo | S4 | N | 이월 | attempt_event 신호 소비 배선 |
| `S5-01-expansion-gate-judgement` | todo | S5 | N | E축 | S5 확장 게이트 판정 |
| `SEC-02-prod-dialogue-key-measurement` | todo | S4 | N | 이월 | prod 대화 암호화 키 실측 |
| `SEC-21-account-identity-key-provider-subject` | todo | S4 | N | 이월 | 계정 식별 키 축 |
| `SEC-22-supply-chain-secret-scan-gaps` | todo | S4 | N | 이월 | 공급망·시크릿 스캔 |
| `SEC-23-token-typ-grandfather-sunset` | todo | S4 | N | 이월 | 토큰 typ 그랜드파더 일몰 |
| `SEC-26-cors-security-headers-middleware` | todo | S3 | N | 이월 | CORS·보안 헤더 |
| `SEC-27-async-job-ownership-check` | todo | S3 | N | 이월 | 비동기 작업 소유권 검사 |
| `SEC-28-device-secret-encryption-fail-closed` | todo | S3 | N | 이월 | device secret 평문 폴백 금지 (타 세션 claim 중) |
| `SEC-29-admin-access-audit-wiring` | todo | S3 | N | 이월 | 관리자 접근 감사 배선 |
| `SEC-30-declared-unwired-waiver-staleness` | todo | S3 | N | 이월 | 면제 4건 만료 조건 |
| `SOL-03-solution-seat-reach-and-audit-axis` | todo | S4 | N | 이월 | 풀이 좌석 도달 리포트 |
| `SOL-04-reasoning-type-vocabulary-collision` | todo | S4 | N | 이월 | reasoning_type 어휘 충돌 |
| `VIZ-08-visualization-doc-code-alignment` | todo | S4 | N | 이월 | 시각화 문서·주석 정합 |
| `VIZ-09-spec-function-sympy-parse-gate` | todo | S4 | N | 이월 | 시각화 sympify 파싱 게이트 |
| `VIZ-10-problem-axis-visualization-dead-chain` | todo | S4 | N | 이월 | problem 축 시각화 죽은 사슬 |
| `WEB-01-landing-static-v1` | todo | S4 | N | 이월 | 공개 랜딩 v1 — 2027 마케팅 |
| `WEB-02-landing-deploy` | todo | S4 | N | 이월 | 랜딩 배포 배선 |


## §3. 집행 수단 권고 — 표시가 아니라 기계 강등이어야 한다

선언 §6-5는 "'검증 비관여' **표시**"라고 적었으나, 표시만으로는 `next`의 우선순위 계산이 바뀌지 않는다(감사 A1의 교훈 — 산문 규칙은 집행이 아니다). 하네스에 **이미 존재하고 기계로 집행되는** 수단이 있다:

**`tracks.yaml`의 `entry_gate`** — `selector.py:76`이 트랙 전체를 `next` 후보에서 제외한다(`Exclusion(task.id, "track_gate", ...)`). 선례: `subject-expansion` 트랙이 `G-s5-subject-expansion`으로 하드락돼 있고 E축 11건이 그 방식으로 이미 잠겨 있다.

**권고**: 신규 트랙 `eos-deferred`(title: "12월 검증 비관여 — 2027 이월") + `entry_gate: G-eos-2027-scope-decision`(G5 판정 산출물인 2027 범위 결정이 clear 조건)을 만들고, N 판정 103건의 `track`을 그리로 옮긴다. 그러면 이월이 **폐기가 아니면서**(태스크는 대장에 그대로 남고 재개 트리거가 명시된다) `next`에서는 사라진다 — 선언 §6-5의 "폐기 아님"과 "만료 없는 유예·제외 금지"를 동시에 만족한다.

**단, 지금 집행할 수 없다**: 기존 태스크의 `track`을 바꾸는 CLI verb가 없다(`add` 시점 전용). `HARN-24` acceptance ③이 이미 등재한 공백과 **같은 뿌리**이며, CUR-11·12·17·18을 `requires_gates` 대신 `block`으로 처리해야 했던 이유와도 같다. 따라서:

| 순서 | 조치 | 소유 |
|---|---|---|
| ① | 본 판정표 검토·확정 (R/N/? 이동) | **Kiki** |
| ② | `HARN-24` 착수 — amend verb에 `track`·`requires_gates` 부착 경로 포함 | claude |
| ③ | ②의 verb로 N 판정분 일괄 이관 + `G-eos-2027-scope-decision` 등재 | claude |
| ④ | `G-eos-verification-relevance-triage` clear + CUR-11/12/17/18 `unblock` 4건 | Kiki → claude |

**②를 건너뛰고 YAML을 손편집하지 않는다** — 103건 일괄 손편집은 이 저장소가 명문으로 금지한 대장 우회이고, ADMIN-02가 게이트를 못 붙인 채 남은 선례가 이미 있다.

## §4. 한계 (정직)

1. **판정은 제안이지 확정이 아니다.** 특히 R 66건 중 "하네스 전제"·"회수" 축은 12월 검증에 *직접* 기여하지 않는다 — 작업의 **보존율**에 기여한다. Kiki가 이 축을 R로 볼지 N으로 볼지가 이 표에서 가장 크게 갈릴 수 있는 지점이다.
2. **`?` 13건의 성격이 서로 다르다** — 법령(`MGMT-01`·`MGMT-02`·`OPS-31`·`SEC-31`)은 변호사 판단, `REC-07`·`S3-01`은 사람 결정, `CUR-11/12/17/18`은 본 게이트의 판정 대상 자신, `OPS-48`·`OPS-50`·`PED-34`는 KPI 접점이 있으나 강도가 불확실하다. 한 덩어리로 처리하면 안 된다.
3. **클론이 shallow다** — 미머지 브랜치 31개 안에서 이미 진행 중인 태스크를 보지 못했다. N으로 판정한 것 중 타 세션이 완료해 둔 것이 있을 수 있다(`git fetch --unshallow` 후 재대조 필요).
4. **판정 시점 고정** — main `33c51b7f` 기준이다. 이후 등재되는 태스크는 §0-5 신규 기능 게이트가 코드로 서기 전까지 **같은 사각에 다시 쌓인다**(감사 A1). 이 문서는 재고를 비울 뿐 유입을 막지 못한다.
5. **커버리지는 기계로 확인했다** — 판정키 182 ↔ 태스크 182 **1:1 매칭, 누락·중복 0건**(`stage`·`status` 무관 전수). 다만 *판정의 내용*은 기계가 검사할 수 없다.

