# 아키텍처 감사 6회차 (ARCH-06) — S2-08 상환 이행 실측·crosswalk 라이브 64 거버넌스 판정

> **감사일**: 2026-07-13 (5회차 `arch_audit_2026-07-12_r5.md` 이후 델타: PR #510 crosswalk 확장 75파일·15,439줄 + PR #512 S2-08 상환 — **r5와 달리 실질 코드 델타 있음**)
> **태스크**: `backlog/tasks/ARCH-06-playbook-audit.yaml` | **방법**: 정적 불변식 grep·config diff + 게이트 대장 실측 + crosswalk 계약(`crosswalk_gate_contract.md`) 행 단위 서명 실측 + S2-08 산출물 이행 실측
> **한 줄 결론**: 5회차 초점 중 **④ S2-08 상환 = 이행 완료 실측**(josa·난이도·op-code·표본 29·30 전부 main 반영). ①②③⑤는 kiki·게이트 대기로 정상 이월. **이번 회차 핵심 = #510 crosswalk 라이브 2→64의 거버넌스 판정 → NEVER 위반 아님**(전건 사람 서명·기계 reject-only·적재/노출 플립 0). 단 **대장 비정합 1건 발견**(적재 가능 corpus 커밋 vs `G-crosswalk-approval` pending·evidence:null) → 위생 상환 태스크 1건 add. 정적 불변식 회귀 0.

---

## 1. 5회차 초점 5항목 이행 판정 (arch_audit_2026-07-12_r5.md §6)

| # | 5회차 초점 | 6회차 판정 |
|---|---|---|
| ① | S1-12 라이브 실측 완료 시: 전면 실측 교체·비용 비율·verify verdict 분포·S1 게이트② 판정 | ⏸ **대기(무변화)** — `S1-12`(owner=kiki·todo) 미완. 라이브 실측 신규 기록 없음. S1 게이트② 미판정 유지(정상 추적) |
| ② | S1-11 승격 판정 — shadow 데이터 확보 후 primary 승격 가부 | ⏸ **대기(무변화)** — S1-12 선행. "측정 없는 도입 없음" 준수 유지 |
| ③ | ARCH-12(QuizMode) 결정 이행·웹 게이트 화이트리스트 봉인 해제 판정 | ⏸ **kiki 대기(무변화)** — 화이트리스트 2건 봉인 유지·회귀 유발 신규 클라이언트 수학로직 0 |
| ④ | **S2-08 상환 이행 실측** — 계통 결함 3종 수정·deferred 2건 재판정 해소 | ✅ **이행 완료(main 실측)** — PR #512 머지. ⑴ `josa.py` 헬퍼 main 반영(한자어 읽기 받침 판별·테스트 동반) ⑵ 난이도 재보정(1스텝 패밀리 전부 QUAD-EQ 2.0 이하: EXP/LOG 1.5·TRIG-VAL 1.3 등·극값 3.0 보존) ⑶ `select-min-for-max` 잔존 **0**(중립 `select-opposite-extremum`) ⑷ 표본 29 = diff 1.8·"밑 6을" / 표본 30 = diff 1.5·단위원 정의 — **deferred 2건 해소**. 코퍼스 620건 재생성·rephrased 결정론 재조정·검수 기록 문서는 재작성 아닌 주석(동결 기록 보존) = 정직성 정합. CI green(backend lint·type·test + 실PG 통합) |
| ⑤ | S2-01 착수 시: 저작권 게이트 재확인 + 전체 코퍼스 실제 확장 검수 | 🔄 **미착수(게이트 대기)** — `G-crosswalk-approval` pending(5일 경과). 단 §3의 crosswalk 라이브 64 거버넌스 판정이 게이트 clear의 선행 정보를 제공 |

---

## 2. 신규 코드 델타 점검 (r5 이후 PR #510·#512)

| 항목 | 결과 |
|---|---|
| 금지 관계 토큰 | ✅ `grep -rn "similar_to\|related_to" src/` — traversal 실사용 **0건** |
| 계층 경계 계약 | ✅ import-linter 7계층 단방향(`src/backend/pyproject.toml`) **무변경**(diff 0) |
| 스키마·마이그레이션 | ✅ 신규 alembic **0** — #510·#512 모두 마이그레이션 없음(프로덕션 DB 적재 없음과 정합) |
| 노드 순수성·엣지 | ✅ concept_graph 437노드 금지혼입 **0**·관계는 `prerequisite` 단일 유지. #510의 그래프 접점은 **정본 validator 재사용 거버넌스 테스트 추가뿐**(재구현 0·`AtomRelation.PREREQUISITE`만 참조) |
| 오개념 reactive | ✅ 탐지 카탈로그 34→64 증설분 전부 `signals` 동시발생 탐지기(reactive) — 초기 컨텍스트 preload **0** |
| LLM 노출 | ✅ #510 하네스는 "전 과정 결정론·LLM 0·기계 증명(SymPy)" — subgraph 예산 접점 없음 |
| 게이트 대장 정합 | ⚠️ §3 — crosswalk 적재 가능 corpus 커밋 vs `G-crosswalk-approval` pending **비정합 1건** |

> **환경 제약(정직 기록)**: 거버넌스 테스트는 backend venv로 직접 실행 가능해짐(r5 대비 개선) — S2-08 관련 스위트 914 passed 실측(PR #512 검증 시). #510 산출물은 CI green으로 머지됨.

## 3. crosswalk 라이브 2→64 거버넌스 판정 (이번 회차 핵심)

> **대상**: PR #510 "843↔탐지 crosswalk 확장 — 카탈로그 34→64·라이브 매핑 2→64". 확장된 crosswalk는 `crosswalk_gate_contract.md`가 봉인하는 **바로 그** 오개념 kebab↔M-id 매핑이다("별개 crosswalk" 가설 기각). 게이트 pending 상태에서의 라이브 확장이 계약 위반인지 행 단위 실측.

| 감사 축 | 판정 |
|---|---|
| **행 단위 사람 서명** | ✅ `data/corpus/misconception_crosslinks_v1/crosslinks.json` 64행 **전건** `method: manual` + `검수:Kiki 2026-07-XX` stamp(07-08/07-10/07-12) — **AI 서명(`검수:AI`) 0건**. `_provenance.json`이 "human sign-off·AI 자기승인 금지" 명시 |
| **기계 승인 경로 부재** | ✅ #510의 `crosslink_gate.py` 델타는 **기계-reject 축만** 추가(`structural_reject`·reviewer="machine") — 기계는 **반려만 가능·승인 불가**(계약 §asymmetry·초인간 검증 기준 §3.3 정합). AI 승인 경로 신설 0 |
| **검수 큐 봉인** | ✅ `misconception_crosslink_review_queue.json` 111행 **전건 pending·미서명** — `test_real_queue_all_pending_unsigned` 봉인 유지 |
| **적재·노출 플립** | ✅ 커밋에 `load_crosslinks`/populate 호출 **0**·노출 플립 0·마이그레이션 0 — 64행은 hermetic 테스트(`test_approved_crosslinks_corpus.py`: load_gate 위반 0·참조 무결성)로 동결된 **적재 가능 소스 corpus**이지 프로덕션 적재가 아님 |
| **초인간 검증 정합** | ✅ 하네스가 Wilson 게이트 CLI 패턴 준수 — `corpus_audit_eval.py` exit 0/1·`wilson_upper_bound ≤ 0.02`·min-n 200(기준 §2 S5)·`corpus_reverify.py` 1080/1080 byte-deterministic(S6) |
| **대장 비정합(발견)** | ⚠️ 사람 서명된 적재 가능 corpus가 커밋됐는데 `backlog/gates.yaml`의 `G-crosswalk-approval`은 **pending·evidence:null 그대로** — 대장이 실태를 뒤따라가지 못함. 계약 자체가 인정하는 한계(서명 위조는 도구 밖 검증·§53-54)와 결합하면, **Kiki의 서명 진위 확인 + evidence 첨부 clear**가 필요 |

**감사 결론**: crosswalk 확장은 **NEVER 위반이 아니다** — 사람 서명·기계 reject-only·큐 봉인·무적재가 전부 실측 확인됐다. 실질 결함은 **거버넌스 대장 위생**: 적재 가능 corpus 커밋 시 백로그 게이트가 동기 이동해야 한다. 조치(§5): ⑴ `G-crosswalk-approval` clear 시 evidence로 `_provenance.json` signatures 블록 + Kiki 서명 진위 확인을 첨부할 것(게이트는 kiki 소유·본 감사는 요건만 명시) ⑵ 대장 동기화 규약 명문화 + 잔여 drift(아래) 정리를 위생 상환 태스크로 add.

**Minor drift(비차단)**: `test_approved_crosslinks_corpus.py` 주석이 "총 58건·카탈로그 58·kebab∈34"로 실제(64·64)와 불일치 — 코드 동작은 정상(assert는 64), 주석만 stale.

## 4. 상시 불변식 재확인 (변경 없음)

엣지 최소 타입·노드 순수성·`prerequisite` DAG·오개념 reactive retrieval·임베딩 namespace 거버넌스·백엔드 7계층 단방향·클라이언트 무-수학로직 게이트(ARCH-10)·LLM subgraph 예산(max_nodes≤20·tokens≤3000 CI 동결·depth≤2 유예) — 전부 준수 유지.

## 5. 상환 태스크 추가 (수용기준 ③)

- **신규**: `S2-10-crosswalk-ledger-hygiene` — "crosswalk 대장 동기화 위생 — 게이트 clear evidence 요건 명문화 + 적재가능 corpus 커밋 시 대장 동기 이동 규약 + stale 주석(58→64) 정리". track=infra-debt·stage=S2·priority=3·owner=claude.
  - 근거: §3 대장 비정합 + minor drift.
  - 수용: ⑴ `crosswalk_gate_contract.md`에 "적재 가능 corpus 커밋 = `G-crosswalk-approval` 대장 동기 이동(clear 또는 notes 갱신)" 규약 추가 ⑵ `test_approved_crosslinks_corpus.py` stale 주석 64 기준 정리 ⑶ 게이트 clear evidence 요건(`_provenance.json` signatures + 진위 확인) 명문화.
  - 참고: 게이트 clear 자체는 kiki 행동(`G-crosswalk-approval` 기존 게이트가 추적) — 본 태스크는 규약·위생만.

## 6. 다음 회차(ARCH-07) 초점

1. **S1-12 라이브 실측 완료 시**: 전면 실측 교체·비용 비율·verify verdict 분포·S1 게이트② 판정 (3회차 연속 이월 — kiki 라이브 대기)
2. **S1-11 승격 판정**: shadow 데이터 확보 후 primary 승격 가부
3. **ARCH-12(QuizMode)** 결정 이행·화이트리스트 봉인 해제 판정
4. **G-crosswalk-approval clear 시**: evidence 적정성(서명 진위 확인 포함) 재확인 + S2-10 위생 상환 이행 실측
5. **S2-01 착수 시**: 저작권 게이트 재확인 + 전체 코퍼스(620문) 실제 확장 검수 품질·기계 게이트 4종 선행 실측 — S2-08 수정 반영분 기준
