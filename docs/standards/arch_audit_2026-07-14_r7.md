# 아키텍처 감사 7회차 (ARCH-07) — S2-01/S2-02 적대 검증·crosswalk clear 적정성·ARCH-12 이행 실측

> **일시**: 2026-07-14 · **기준 HEAD**: `ee34ca2`(#517 머지) · **선행**: `arch_audit_2026-07-13_r6.md`
> **방법 특기**: 이번 회차 감사 대상의 다수(초점 4·5·S2-02 델타)가 **감사 주체(claude 세션)의
> 자기 작업**이다 — 자기-감사 약점을 완화하기 위해 해당 3영역은 **반증 프레임의 적대적 검증
> 서브에이전트**(독립 컨텍스트·"부적정 증거를 적극 탐색·반증 실패 시에만 적정")에 위임했고,
> 발견 결함은 전건 회차 내 상환했다.

## 1. 6회차 초점 5항목 이행 판정 (arch_audit_2026-07-13_r6.md §6)

| # | 초점 | 판정 |
|---|---|---|
| ① | S1-12 라이브 실측 완료 시 전면 실측 교체 | ⏸ **4회차 연속 이월** — kiki 라이브 대기(S1-12 todo·owner kiki). 델타: **#516 런북 de-risk** — 측정 도구 3종(`live_preflight`·`cost_report`·`problem_corpus_accumulate`) 검증·자리표시자 해소로 Kiki 잔여 행동이 "런북 실행→결과표→판정" 한 세션으로 축소됨 |
| ② | S1-11 승격 판정 | ⏸ 이월 — shadow verdict 분포(라이브) 미확보. S1-12 의존 유지가 정당("측정 없는 도입 없음") |
| ③ | ARCH-12(QuizMode) 결정 이행·화이트리스트 봉인 해제 판정 | ✅ **이행 완료·봉인 유지가 정당** — 게이트 테스트 헤더(데모 전용 예외 공식 존치·강제 트리거 명기)와 QuizMode 주석(GraphingCalculator.jsx:536) 실측·화이트리스트 정확 2건 동결. 봉인 해제는 강제 트리거(학생 노출 진입) 전 없음. **발견·상환**: 테스트 35행 stale 주석 "(ARCH-12 결정 대기)" → 결정 완료 반영 |
| ④ | G-crosswalk-approval clear evidence 적정성(서명 진위 포함)+S2-10 이행 | ✅ **조건부 적정 → 결함 3건 상환 후 적정** (§3-A) |
| ⑤ | S2-01 착수 시 저작권 게이트+620문 확장 검수 품질·기계 게이트 4종 | ✅ **반증 5건 전부 실패(품질 실측 성립)·정직 유보 2건 상환** (§3-B) |

## 2. 신규 코드 델타 점검 (r6 이후 PR #515·#516·#517)

- **#515(S2-01)**: 검수 산출물 3종 + josa 교정 — §3-B에서 적대 검증.
- **#516(S1-12 런북)**: 문서-only de-risk — 코드 0·판정 ①에 반영.
- **#517(S2-02)**: 신규 `whs/corpus_replay.py`·reverify Tier2 확장·15 생성기 steps — §3-C에서 적대 검증.
  **import-linter 7계층 단방향 KEPT**(corpus_replay 포함·1 kept 0 broken 실측).

## 3. 적대 검증 3건 (이번 회차 핵심 — 자기-감사 완화)

### 3-A. G-crosswalk-approval clear 적정성 — **조건부 적정 → 상환 완료**

반증 실패(실체 성립): ⑴ 64행 **전건** `검수:Kiki` 스탬프 실재(`_provenance.json` 64·`crosslinks.json` 64·미서명 0)
⑵ **스탬프가 clear보다 14시간 선존**(`fbbcc53` 07:07 vs clear `7d35e6f` 21:38) — clear 시점 위조·자기승인
아님·"완료분 동기화" 주장 성립 ⑶ 기계 reject-only(`crosslink_gate.py` 승인 경로 부재·`structural_reject`)
⑷ `load_crosslinks` 자동 프로덕션 호출 0(ops 수동 CLI뿐) ⑸ S2-10 이행 실재(계약 §대장 동기화 신설·stale 58 정리 0건).

반증 부분 성공 — **evidence 품질 결함 3건, 회차 내 상환**:
1. 날짜 열거 부정확(최다 07-12 42/64 누락) → 3날짜 전량(2·20·42건)으로 정정
2. 계약 clear evidence 요건 ⑵(Kiki 본인 승인 확인 명시 문구) 미충족 → 2026-07-13 세션 결정
   ("대장 정합까지" 선택·AskUserQuestion 기록) 참조 추가
3. S2-10 artifact 해시 dangling(`b14597b` 부재) → 실 구현 커밋 `a86486c`(#513) 정정

### 3-B. S2-01 검수 품질(620문·Wilson 240) — **반증 5건 전부 실패·유보 2건 상환**

반증 실패: ⑴ 표본 결정론·1:1 무결(코퍼스@#515 기준 재현·15도메인·오개념 4종·slug↔pid 정확 일치)
⑵ 문서↔jsonl 240행 전건 정합·defect 2건 서사 은폐 없음 ⑶ Wilson exit 0 재현(상한 0.0111)
⑷ 저작권 620/620 완전 균일(original_source 0) ⑸ 검수 실질성(문항별 개별 note·복붙 아님·정직 고지 실재).
기계 게이트 4종 재실행 green(Tier1 620·강등전 100/100·Wilson·S2-a).

정직 유보 2건 — **회차 내 상환**:
- **A. 표본 md stale**: #517의 코퍼스 verify 블록 확장으로 `reviewer_sample_240_v0.md`가 현행
  코퍼스와 바이트 불일치(판정 기준 필드는 전부 불변) → S2-08 선례(동결 기록·재작성 금지)대로
  **전방 주석** 추가.
- **B. Wilson PASS의 교정후-재채점 의존**: as-found(2/240) 채점 시 상한 **0.0249 > 0.02(FAIL)** —
  PASS는 교정·재생성 후 재채점 결과. 전 코퍼스 as-found(4/620) 상한 0.0143은 통과라 실체 결론
  불변이나, 같은 표본 재채점의 fail→pass 전환은 엄밀 acceptance sampling 규약과 다름 →
  문서에 **as-found 정직 병기** + 규약 명문화 상환 태스크 **S2-11** 신설.

### 3-C. S2-02 델타(corpus_replay·PRM·reverify Tier2) — **반증 4/5 완전 실패·문서 결함 1건 상환**

반증 실패: ⑴ 7계층·import 방향 위반 0(상향 import 없음·WH-S=L3/L1 업스트림 설계 정합)
⑵ 수치 전건 재현(1,282·good 663·bad 619·620 전수·prm_score null 1,282/1,282)·순환성 고지 도처
실재·"솔버가 풀었다"류 과대표현 0 ⑶ **PRM 라벨 무결 — good 20/20 correct·bad 20/20 incorrect
재검증** ⑷ reverify "incorrect만 fail" 설계는 명시 기록 + 방어 실효(수용 게이트가 unverifiable 0
강제 — 적재 코퍼스는 구성상 unverifiable 전이 0) ⑸ 완전 결정론(시드 셔플만·datetime/uuid4 0).

반증 부분 성공 — **상환**: `whs_production_run_2026-07.md:68`의 good=663 유도 검산 주석이
673으로 합산되는 산술 오류(TRIG-EQ 이중 계상·헤드라인 663과 데이터는 무결) → 실데이터 분포
(1-good 577·2-good 43)로 교정.

## 4. 상시 불변식 재확인

- alembic 단일 head `c4d5e6f0a1b2` ✓ · import-linter 7계층 단방향 **KEPT**(1 kept 0 broken) ✓
- relink 거버넌스 6 passed ✓ · 웹 수학판정 게이트 화이트리스트 2건 동결 ✓
- 저작권 레일: 생성 코퍼스 620/620 자체생성 균일(§3-B ⑷) ✓

## 5. 상환 (수용기준 ③) — 전건 회차 내 처리

| 발견 | 상환 |
|---|---|
| ARCH-12 stale 주석(테스트 35행) | 즉시 수정(커밋 `1067765`) |
| crosswalk evidence 결함 3건 | gates.yaml·S2-10 artifact 정정(커밋 `e24a693`) |
| S2-02 doc 검산 산술 오류 | doc:68 교정(커밋 `6dce368`) |
| S2-01 표본 md stale·Wilson as-found | 전방 주석·정직 병기(본 회차 커밋) |
| acceptance sampling 규약 공백 | **S2-11-acceptance-sampling-rigor** backlog add |

## 6. 다음 회차(ARCH-08) 초점

1. **S1-12 라이브 실측 완료 시**(5회차 이월): 전면 실측 교체·로컬 비율·verify verdict 분포·S1 게이트② 판정
2. **S1-11 승격 판정**: shadow 데이터 확보 후
3. **S2-11 규약 이행**: 초인간 검증 표준 §5 독립 재표본 규약 명문화 실측
4. **S2-02 후속 착수 시**: LLM 정책 탐색의 replay bank 웜스타트 실측·진짜 풀이율 곡선(1.0 미만 정상) 기록 검증
5. **S2-04(orphan) 착수 시**: G-orphan-prod-run clear evidence 적정성(prod 리포트 실재·cleanup dry-run→confirm 순서 준수)
