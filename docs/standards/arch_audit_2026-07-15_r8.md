# 아키텍처 감사 8회차 (ARCH-08) — S1-12 실측 판정·S1-11 shadow 승격·S2-11 규약 실측

> **일시**: 2026-07-15 · **기준 HEAD**: `52c8ba5`(#520 머지) · **선행**: `arch_audit_2026-07-14_r7.md`
> **방법 특기**: r7 이후 델타(#518·#519·#520)가 **전부 감사 주체(claude 세션)의 자기 작업**이다 —
> 자기-감사 약점 완화를 위해 3개 실익 초점(①S1-12 ②S1-11 ③S2-11)을 **반증 프레임의 독립
> 적대 검증 서브에이전트 3개**(각 독립 컨텍스트·"부적정·날조·체리픽·게이트 회피를 적극 탐색·반증
> 실패 시에만 적정")에 위임했다. 세 검증기 모두 산술/통계를 독립 재계산하고 코드를 직접 실행·읽었다.

## 1. 7회차 초점 5항목 이행 판정 (arch_audit_2026-07-14_r7.md §6)

| # | 초점 | 판정 |
|---|---|---|
| ① | S1-12 라이브 실측 완료 시 전면 실측 교체·로컬 비율·verify verdict 분포 | ✅ **실측 완료·판정 적정**(5회차 이월 해소) — #518에서 33이벤트 실측(로컬 72.7%<80% as-measured)·S1-13 보정(74/358). §3-A 적대 검증: 반증 5/5 실패·산술 독립 재계산 전건 일치 |
| ② | S1-11 승격 판정(shadow 데이터 확보 후) | ✅ **shadow 분포 확보·승격 부결 유지가 적정** — #519/#520에서 라이브 실측(n=10·2배치)·검출력 4/4 실증. §3-B 적대 검증: 6 서브클레임+A~G 전건 성립·verify_step 메커니즘 SymPy 결정성 확인 |
| ③ | S2-11 규약 이행(§ 독립 재표본 명문화 실측) | ✅ **명문화·회전 메커니즘 실측 적정** — #518 §4.5 신설·`--rotation` 실증. §3-C 적대 검증: Wilson 상한 독립 재계산 일치(0.0249·0.0143)·회전 독립성 실코퍼스 실증(144/240 상이) |
| ④ | S2-02 후속(LLM 정책 replay bank 웜스타트·실풀이율 곡선) | ⏸ **N/A(미착수)** — S2-02 done이나 LLM 정책 탐색 후속 태스크 미신설. 착수 시 실익(진짜 풀이율 1.0 미만 정상 기록 검증) |
| ⑤ | S2-04(orphan) 착수 시 G-orphan clear evidence 적정성 | ⏸ **N/A(미착수)** — S2-04 todo·`G-orphan-prod-run` 여전히 kiki 대기(10일 경과). 착수 시 실익 |

## 2. 신규 코드 델타 점검 (r7 이후 PR #518·#519·#520)

- **#518(ARCH-07+S2-11+S1-12+S1-13)**: `cost_report.py` TierStats·`fill_live_cost_table.py`·`router.py` est 보정(74/358)·`reviewer_sample_package.py --rotation`·표준 §4.5 — §3-A·§3-C에서 적대 검증.
- **#519(S1-11 잔여)**: `coach.py` append_turns shadow 배선·`wh1_shadow.py` turn_index·`wh1_session.py` 보류 명문·`test_coach_wh1_convergence_governance.py`(신규)·CLAUDE.md 규칙 — §3-B에서 적대 검증.
- **#520(S1-11 실측)**: 문서-only(MEMORY·live_cost_measurement) — §3-B에서 적대 검증.
- **import-linter 7계층 단방향 KEPT**(신규 파일 포함·**1 kept 0 broken** 실측)·alembic 단일 head `c4d5e6f0a1b2`.

## 3. 적대 검증 3건 (이번 회차 핵심 — 자기-감사 완화)

### 3-A. S1-12 실측 정직성·판정 적정 — **반증 5/5 실패·적정**

반증 실패(claim 성립): ⑴ **72.7% 산술 무결**(24/33=0.7272→72.7%·재계산 일치)·토큰 n=32 vs cost/비율
n=33 차이는 LOCAL 이벤트 토큰 미기록·cost 0.0 강제 기록에서 정합(날조 아님) ⑵ **보정 74/358이 실측
p50과 정확 일치**(`round(p50)` 메커니즘·회귀 핀 `test_router.py`) ⑶ **CLOUD_MIN_COST_KRW 단일 공식
재계산 일치**(독립: MID `(74·3+358·15)/1e6·1540=8.61168`·HIGH `(74·5+358·25)/1e6·1540=14.3528`)
⑷ 유도치 `7.0789`(=63.7098/9)·비측정 셀 '—'·0 날조 경로 0(`fill_live_cost_table.py` None→'—') ⑸
80% 판정을 PASS로 위장하지 않음("미달 as-measured" 명기·S1-13 재측정 유예는 실재 대표성 한계 근거).

**상환(도큐 품질 1건)**: 토큰 n=32 vs n=33 분할이 공개되나 미서술 → 각주에 한 절 근거 추가(본 회차).

### 3-B. S1-11 shadow 배선·실측·승격 부결 판정 — **6 서브클레임+A~G 전건 성립·적정**

반증 실패: ⑴ **append_turns↔create_session shadow 배선 동형**(turn_index=`total_turns//2+1`·warmstart
동일·never-break·PII 경로 0 — 학생 텍스트는 정책 사적 필드만) ⑵ **플래그 OFF 시 spawn 0**(warmstart
포함 전 블록이 가드 내부·테스트 `captured.calls==0`) ⑶ **거버넌스 4종 `is` 동일성 봉인**(비공허 —
공유 leaf를 coach·하네스 양측이 재수출) ⑷ **turn_index 비PII**(순수 int·extra=forbid·2중 봉인) ⑸
**검출력 4/4 메커니즘 실재**(`verify_step` SymPy `expand(diff)==0`→correct·`simplify(diff).is_zero
is False`→incorrect·`(x+1)(x+2)−(x²+3x+1)=1≠0` 결정적 incorrect) ⑹ **S1-11 정직 blocked**(수용기준
미충족·flip 3전제 명시·`run_persisted_turn` dead-but-tested 명문·거짓 완료 0)·⑺ 합성 n=10 한계가 모든
verdict 서술에 병기.

**상환(도큐 품질 2건)**:
- **E. 4/4 귀속 증적 한계**: shadow 레코드가 문항·풀이 텍스트 제거(설계)·원시 로그 미커밋 → 오전개
  항목↔incorrect 1:1 귀속은 Kiki 실측 증언 의존(수동 라이브 내재 한계) → 문서에 명시 정직 고지 추가(본 회차).
- **C. 봉인 강도**: 4종 중 2종(`curate`·`verify_solution`)이 공유 leaf를 봉인(coach 래퍼 경유 경로가 아님) —
  정직 주석 존재. **coach 래퍼 경로 직접 봉인이 엄밀히 더 강함**(선택 강화·본 회차 미이행·후속 여지).

### 3-C. S2-11 규약 명문화·회전 메커니즘 — **4점 성립·적정**

반증 실패: ⑴ **§4.5 재채점 금지가 구속적**("금지 규약"·"금지한다"·"신규 독립 표본으로 한다" 명령형)
⑵ **Wilson 상한 독립 재계산 일치**(z=1.6449: 2/240→0.024867→0.0249 FAIL·4/620→0.014292→0.0143 통과)
⑶ **소급 판정 정직**(S2-01 초판이 교정후-재채점임을 명시·grandfather + as-found 병기 + 전코퍼스 백스톱·
금지 패턴을 조용히 승인 안 함) ⑷ **`--rotation` 독립성 실증**(실 620코퍼스 select_sample: rotation 0 vs 1
멤버십 144/240 상이·rotation=0 바이트 동일·결정성·verdict-blind — disjoint 아님은 코드·문서 정직 고지).

**상환(추적성 1건·본 회차)**: S2-11 yaml 수용기준이 "§5"라 적었으나 실착지 **§4.5** → 기준 문자열 정정
(artifacts 포인터는 이미 정확).

**backlog add(실체 갭 1건)**: **as-found 병기 의무가 산문뿐·향후 감사 강제 기계 게이트 부재**(프로젝트
"측정 없는 게이트" 안티패턴 관점) → **S2-12-asfound-gate** 신설(저우선·현 S2-01 실측은 병기 준수 실재).

## 4. 상시 불변식 재확인

- alembic 단일 head `c4d5e6f0a1b2` ✓ · import-linter 7계층 단방향 **KEPT**(1 kept 0 broken) ✓
- governance identity 봉인 4종(`is`) green ✓ · embedding namespace·relink 거버넌스 green(ops 포함 65 passed) ✓
- shadow 필드 봉인(turn_index 등재·extra=forbid) green(governance+shadow 14 passed) ✓

## 5. 상환 (수용기준 ③) — 전건 회차 내 처리

| 발견 | 상환 |
|---|---|
| S1-12 토큰 n=32/33 분할 미서술(도큐) | 각주 근거 추가(본 회차) |
| S1-11 4/4 귀속 증적 한계(도큐·E) | 문서 정직 고지 추가(본 회차) |
| S2-11 yaml §5↔§4.5 추적성 드리프트 | 수용기준 문자열 정정(본 회차) |
| as-found 병기 기계 게이트 부재(실체·C) | **S2-12-asfound-gate** backlog add |
| S1-11 봉인 강도(coach 래퍼 직접 봉인·선택) | 본 회차 미이행·후속 여지 기록(비-결함) |

## 6. 다음 회차(ARCH-09) 초점

1. **S1-11 flip 재판정**: 실기기 시연(`G-kiki-device-demo`) 등 실트래픽 shadow 분포 누적 후 — 합성 n=10
   → 실학생 트래픽 혼합비 확보 시 verify 게이트 승격·Kiki 사인오프(gate3 allowlist 확장) 판정.
2. **S1-14(S1 탈출 판정)**: 보정된 라우터(74/358)로 대표 트래픽 재측정 후 로컬 80% 재판정.
3. **S2-12 착수 시**: as-found 게이트 CLI exit-0/1 실측·검증 권위 서열 정합.
4. **S2-02 후속 착수 시**: LLM 정책 replay bank 웜스타트 실측·진짜 풀이율 곡선(1.0 미만 정상).
5. **S2-04(orphan) 착수 시**: `G-orphan-prod-run` clear evidence 적정성(prod 리포트 실재·dry-run→confirm 순서).
