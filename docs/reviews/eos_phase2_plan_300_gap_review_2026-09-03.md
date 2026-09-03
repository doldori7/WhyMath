# 계획서 300 「Phase 2 — EOS Closed Learning Loop」 ↔ 저장소 실측 대조 (2026-09-03)

> **대상 문서 2종**(Kiki 제공·저장소 외부):
> ① `300_Phase 2 — EOS Closed Learning Loop 실행계획`(대상기간 2026-09-28~10-25 · Gate 2 10+1조건 · Week 1~4 · §1~§22)
> ② `006_MVP 개발 종료·EOS 전환 코딩·절차 체크리스트`(2026-08-27 · 50항목) — **재제출분**
>
> **대조 시점**: `claude/eos-transition-plan-review-w0vmjh` @ `5bb2947b`(#969) · 원격 브랜치 34 · 백로그 507태스크(미완 190).
> **성격**: 조사 전용(코드 변경 0 · 대장 변경 0). 신규 태스크 등재는 §8의 Kiki 판단 뒤.
>
> **선행 문서와의 관계**: 저장소는 이미 계획서 006·100을 흡수한 정본
> `docs/strategy/eos_transition_declaration_2026-08-30.md`(선언)와 대조 3권을 가진다 —
> `eos_source_docs_gap_review_2026-08-31.md`(006·100 축) · `eos_plan52_crosswalk_2026-09.md`(개발항목 52) ·
> `eos_phase1_plan_200_gap_review_2026-09-01.md`(200 = Phase 1). 본 문서는 그 **4권째(300 = Phase 2)**다.
> **②(006)는 이미 흡수 완료분**이므로 본 문서는 §9에서 그 사실과 잔여만 적고 재대조하지 않는다.

---

## §0. 결론 3줄

1. **계획서 300의 단일 목표("학습 폐쇄루프 완성 = 12월 성패를 가르는 Point of No Return")는 저장소 정본과 정면으로 충돌한다.** 선언 §0-3은 2026-08-30에 **폐쇄루프를 목적에서 계측기로 강등**하고(깊이앵커 1개에서만 완결) 최우선 축을 **AI 콘텐츠 생산 가능성(HIT 중앙값 4분)**으로 바꿨다. 그리고 같은 날짜 **10/25에 서로 다른 Gate 2가 두 개** 있다 — 300의 것은 *학생 루프 10조건*, 저장소 G2는 *중등 2앵커 각 60 CU + HIT ≤8분 + 자동검증 ≥70%*(콘텐츠 생산 게이트). 200 검토가 Gate 1에서 발견한 충돌이 **Gate 2에서 그대로 재현**된다(G0 이름 충돌 포함 3회차).
2. **계획서가 4주에 걸쳐 만들려는 부품은 대부분 이미 서 있다.** 14개 계약 객체 중 12개가 실모델·실스키마로 실재하고, §12가 요구한 12개 API 중 11개가 103개 엔드포인트 안에 대응물을 갖는다. Assessment·Mastery·Misconception·Recommendation 엔진은 `l2/`·`l4/`에 전부 있고, **서버 측 폐쇄루프는 이미 닫혀 있다** — `POST /v1/me/attempts` 한 번이 `mastery_updates`·`skill_mastery_updates`·`attempt_skill_event`까지 한 트랜잭션으로 전파한다(`api/me.py:715-810` 실측).
3. **진짜 갭은 계획서가 강조하지 않은 곳에 있다 — 루프가 끊긴 지점은 엔진이 아니라 *입력 도달*이다.** Flutter 앱은 `POST /v1/me/attempts`를 **한 번도 호출하지 않는다**(`src/mobile/lib/` 전수 grep 0건 · REC-01이 관측으로 등재한 사실). 백엔드 E2E도 클라 E2E도 **온보딩→진단→문제→코치→verify에서 멈추고** attempt 제출 이후 반쪽(평가→숙달→다음 추천)을 관통하지 않는다. 즉 **엔진은 다 있는데 학생이 그 엔진을 켤 수 없다.** 계획서 300이 옳게 짚은 것은 "연결성이 기능보다 중요하다"는 문장 하나이며, 그 문장이 가리키는 실제 대상은 §4의 Week 1~4 신규 구현이 아니라 **클라 1개 호출과 E2E 뒷반쪽**이다.

---

## §1. 방법

- 판정 근거는 **실파일 경로·명령 출력·태스크 ID** 중 하나여야 한다. 문서 언급만으로 "충족"한 행은 없다.
- **"trunk 부재 ≠ 미구현"**(CLAUDE.md) 준수: 갭 판정 전 `backlog/tasks/**` 507건과 원격 브랜치 34를 교차 조회했다.
- **"식별자 부재 ≠ 기능 부재"** 준수: 계획서가 제안한 *이름*으로 0건인 항목(`LearnerState` 단일 API·상태 머신 8상태 등)은 **역할로 재검색**한 뒤 판정했다. 재검색으로도 0인 항목만 갭이다.
- **부재 주장의 검색 범위 명시**: 상태 머신은 `DIAGNOSING|REMEDIATING|ADVANCING|PRACTICING` 4어휘를 `.py`·`.dart` 전수로 검색해 0건이며, 역할 재검색(세션 상태·학습 단계 전이)에서도 대응물을 찾지 못했다.
- 재현 명령:

```bash
python3 - <<'PY'   # 103개 엔드포인트 전수 추출 (§3-B 표의 분모)
import re,glob,os
for p in sorted(glob.glob('src/backend/whymath_backend/api/*.py')):
    s=open(p).read(); m=re.search(r'APIRouter\((.*?)\)',s,re.S)
    pre=re.search(r'prefix\s*=\s*"([^"]*)"',m.group(1)).group(1) if m and re.search(r'prefix',m.group(1)) else ''
    for mo in re.finditer(r'@router\.(get|post|put|patch|delete)\(\s*"?([^",\)\s]*)"?',s):
        print(mo.group(1).upper(), pre+(mo.group(2) if mo.group(2).startswith('/') else ''), os.path.basename(p))
PY
grep -rn "attempts" --include=*.dart src/mobile/lib/          # 클라 attempt 호출 = 0건
grep -rn "DIAGNOSING\|REMEDIATING\|ADVANCING\|PRACTICING" --include=*.py --include=*.dart .   # 상태 머신 = 0건
sed -n '715,810p' src/backend/whymath_backend/api/me.py       # 서버측 루프 폐쇄 실측
python3 scripts/harness/backlog.py next --n 507 --json        # 전건(절단 금지)
grep -h "^eos_priority:" backlog/tasks/*.yaml | sort | uniq -c
```

---

## §2. Gate 2 조건 대조 (계획서 §18 — 10조건 + 최중요 1조건)

| # | 계획서 300의 Gate 2 조건 | 판정 | 실측 근거 |
|---|---|---|---|
| 1 | 신규 학생 생성 가능 | **충족** | `POST /v1/auth/{provider}/callback`·`PATCH /v1/users/me`(온보딩) · 미성년 동의 게이트(`parental_consent` 3표면) · 클라 관통 `e2e_loop_flow_test.dart` ⑤ |
| 2 | 진단 완료 가능 | **충족** | `GET /v1/me/next-problem`(IRT CAT) + `GET /v1/me/diagnosis/concepts`·`/summary`(BKT↔IRT) + `POST /v1/me/assessments/assemble`(청사진 조립·ASM-04 done) |
| 3 | LearnerState 자동 생성 | **부분** | 조립기 `l2/learner_state.py` 실재(v0 8필드 — 생산자 없는 3필드는 의도적 제외). **갭: 소비처가 `api/study.py` 1곳뿐**이고 `GET /learner-state` 단일 표면이 없다 — 학생·클라는 `/me/mastery/current`·`/me/ability`·`/me/diagnosis/*`로 조각을 따로 받는다 |
| 4 | Concept 자동 선택 | **충족** | `l2/weak_concept_recommendation.py`·`prerequisite_recommendation.py` + `GET /v1/me/weak-concepts`·`/{id}/learning-path`·`/{id}/prerequisites` |
| 5 | Content → Problem 연결 | **충족** | `GET /v1/concepts/content` → `GET /v1/me/next-problem` → `GET /v1/problems/{id}` · 학습 공급 루프는 `POST /v1/me/objectives/{id}/study`로 클라 배선까지 완료(MOB-13 done) |
| 6 | Attempt → Assessment 동작 | **충족(서버) / 미도달(클라)** | 서버: `POST /v1/me/attempts`가 채점→`record_problem_attempt_mastery`→`record_problem_attempt_skill_mastery`→`record_attempt_skill_event`를 한 경로에서 수행(`api/me.py:715-810`). **클라: 호출 0건** — `src/mobile/lib/` 전수 grep에 `attempts` 없음. REC-01이 이 사실을 "입력 루프 미도달·`problem_attempt` 0행"으로 관측 등재했다 |
| 7 | Misconception 기록 | **충족** | 오개념 카탈로그 843건(M-id)+kebab crosswalk 64 · 4모델(`misconception_catalog`/`_crosslink`/`_hypothesis`/`_relation`) · 승인·적재 게이트가 `docs/standards/crosswalk_gate_contract.md`로 **코드 동결** |
| 8 | Mastery 자동 갱신 | **충족** | `ConceptMasteryHistory`·`SkillMasteryHistory` append-only 이력 + `l2/mastery_tracking.py`·`skill_mastery_tracking.py` · BKT(`l2/bkt.py`)·IRT(`l2/irt.py`) 실재. 계획서 §6의 "정답 +0.10 / 오답 −0.08" heuristic보다 **앞서 있다** |
| 9 | 다음 학습 자동 추천 | **충족·단 이유축 부분** | `GET /v1/me/next-problem`(IRT CAT·약점 가중) + 추천 회계 `l2/recommendation_evidence.py`(REC-03 done). 이유축: PATH-02/09/10 done으로 **정렬 근거 정직 표기**가 서버·영속·렌더 3단 착지. **갭: `candidates[]`·`policy_version` 영속 미착지**(REC-11 todo·P0) |
| 10 | 전체 과정 반복 가능 | **미실증** | 반복을 관통하는 테스트가 없다. `test_e2e_vertical_slice_integration.py`·`e2e_loop_flow_test.dart`는 둘 다 **온보딩→진단→문제→코치→verify에서 종료**하고 attempt 제출 이후를 밟지 않는다(§3-C) |
| ★ | **운영자 DB 개입 0으로 3연속 루프** | **일정 충돌** | 이 조건은 저장소가 **이미 채택했으나 G2(10/25)가 아니라 G4(12/13)에 배정**했다 — 선언 부록 E: *"깊이앵커 수동 개입 0 루프 3연속 + 학생 표본 ≥20명 + P0 결함 0"*. 즉 계획서의 최중요 조건은 저장소에서 **7주 뒤 게이트**다 |

**분포**: 충족 6 · 부분 2 · 서버충족/클라미도달 1 · 미실증 1 · 일정충돌 1.

> **핵심**: Gate 2 10조건 중 8건은 이미 서 있거나 부분 착지다. **막힌 곳은 6·10 두 칸이고 둘의 원인은 하나** — 학생 입력이 서버 루프에 도달하지 않으며, 그래서 반복을 실증할 수도 없다.

---

## §3. 전제 충돌 3건 — Kiki 판단이 필요한 항목

### A. Phase 2의 목적 자체 (가장 중요)

| | 계획서 300 | 저장소 정본(선언 §0-3, 2026-08-30·PR #904) |
|---|---|---|
| Phase 2의 정의 | **"12월 출시 성패를 결정하는 Point of No Return"** | 폐쇄루프는 **목적이 아니라 콘텐츠 품질을 재는 계측기** — 깊이앵커 1개에서만 완결 |
| 10월의 최우선 | 학습 폐쇄루프 완성 | **AI 콘텐츠 생산 가능성** — 출시 등급 CU 1건의 HIT 중앙값이 손익분기(4분) 아래인가 |
| 10/25 판정 | Gate 2 = 학생 루프 10조건 | **G2 = 중등 2앵커 각 60 CU + HIT 중앙값 ≤8분 + 자동검증 ≥70%** |
| 12/31 | 출시일 | **내부 검증 판정일**(Go/Conditional/No-Go) |

이 충돌은 200 검토 §3-A가 이미 지적한 것과 **같은 뿌리**이며, 여기서는 더 날카롭다 — 200은 "Phase 1을 무엇에 쓸 것인가"의 충돌이었지만, 300은 **Phase 2의 존재 이유 자체**가 다르다.

계획서 300을 그대로 실행하면 10월 4주가 통째로 학생 루프 배선에 들어가고, **G2가 요구하는 앵커 2개 × 60 CU 생산(=HIT 실측의 유일한 재료)이 시작되지 않는다.** 반대로 G2를 그대로 가면 계획서의 Gate 2 10조건 중 6·10은 12월(G4)까지 미실증으로 남는다.

**산술적으로 조정되지 않는다.** 다만 §8이 보이듯 **양립 가능한 축이 있다** — 계획서 300에서 살아남는 항목 대부분은 4주가 아니라 **수일 규모**다.

### B. 같은 날짜(10/25), 서로 다른 Gate 2 — 이름 충돌 3회차

저장소는 이미 이 유형을 두 번 겪었다(G0 vs 계획서 100 Gate 0 → 선언 §1.3-② 표기 규약 신설 / Gate 1 vs 200 → 200 검토 §3-B). **세 번째다.** "Gate 2 통과했다"가 참이면서 동시에 거짓이 되는 상태를 10/25 판정문 이전에 고정해야 한다.

**권고 표기 규약**(선언 §1.3-② 동형): 저장소 게이트는 `G0`~`G5`, 계획서 300의 것은 **`Phase 2 Gate(300)`**로 적는다. `G2`로 줄여 쓰지 않는다.

### C. 주차·기간 어긋남

계획서 300의 기간(9/28~10/25)은 선언의 주간 리듬(W1=8/31~9/6 기산)에서 **W5~W8**에 해당한다. 200 검토가 발견한 "주차 번호 1칸 어긋남"이 여기서도 유효하며, 계획서의 "Week 1~4"를 그대로 부르면 저장소 W1(8/31 주)과 충돌한다. **`P2-W1`~`P2-W4`로 표기**하는 것을 권한다.

---

## §4. 이미 서 있는 것 — 계획서가 4주를 배정한 부품의 현황

### 4.1 §1 "Learning Loop Contract" 14객체

| 계획서 객체 | 저장소 실측 | 판정 |
|---|---|---|
| Learner | `db/models/user.py` `UserProfile` | 충족 |
| LearnerState | `l2/learner_state.py`(v0 8필드 조립기) | **부분** — 소비처 1곳·단일 API 없음 |
| Curriculum | `curriculum_framework`·`curriculum_version`·`curriculum_entry` 3모델 + `api/curricula.py` | 충족 |
| Objective | `POST /v1/me/objectives/{id}/study`·`/outcome` + 성취기준 895 적재 | 충족 |
| Concept | `concept_node`(437) + 원자 백본 2,683노드·2,210엣지 | 충족 |
| Skill | `db/models/skill_node.py` `SkillNode`(PK `skill.<slug>`) + `l1/skill_graph/` | **충족·단 27건으로 얇음**(200 검토 §2 행5와 동일 진단) |
| Content | `concept_content` + `GET /v1/concepts/content` | 충족 |
| Problem | `problem`(코퍼스 2,647 + PB-13 저작확장 11,446문) | 충족 |
| Attempt | `attempt_event`(TimescaleDB hypertable) + `answer_submission`(EOS-32) | 충족 |
| Assessment | `db/models/assessment.py` `Assessment` + 4테이블 라이브 writer(ASM-03/04 done) | 충족 |
| Misconception | 카탈로그 843 + 4모델 + 게이트 계약 동결 | 충족 |
| Mastery | `ConceptMasteryHistory`·`SkillMasteryHistory` append-only | 충족 |
| Recommendation | `l2/*_recommendation.py` 3종 + `recommendation_evidence`(REC-03) | **부분** — 영속 축 REC-11 todo |
| LearningSession | `schema/activity.py` `LearningSession`(§6.1 DDL 정본) | **부분** — 스키마 실재·**writer 0**(`recommendation_evidence.py` docstring 자인: *"결합 가능한 실 학습 세션 개념이 없다"*) |

**12/14 충족 · 2 부분(LearnerState 표면·LearningSession writer) · 0 부재.**

### 4.2 §12 "반드시 필요한 API" 12건

| 계획서 API | 저장소 대응 | 판정 |
|---|---|---|
| `POST /diagnostics` | `POST /v1/me/assessments/assemble` + `GET /v1/me/diagnosis/concepts`·`/summary` | 충족(분할) |
| `GET /learner-state` | — (조각 3표면: `/me/mastery/current`·`/me/ability`·`/me/diagnosis/summary`) | **갭(합성 표면 부재)** |
| `GET /learning/next` | `GET /v1/me/next-problem` | 충족 |
| `GET /concepts/{id}` | `GET /v1/concepts/{concept_id}` | 충족 |
| `GET /contents/{id}` | `GET /v1/concepts/content` | 충족 |
| `GET /problems/{id}` | `GET /v1/problems/{problem_id}` | 충족 |
| `POST /attempts` | `POST /v1/me/attempts` | 충족(서버) |
| `POST /assessments` | `POST /v1/me/assessments/capture` | 충족 |
| `GET /recommendations/next` | `GET /v1/me/next-problem`·`/weak-concepts/{id}/learning-path` | 충족 |
| `POST /tutor/query` | `POST /v1/coach`·`/v1/coach/sessions/{id}/turns` | 충족 |
| `GET /sessions/{id}` | `GET /v1/me/sessions`·`GET /v1/coach/sessions/{dialogue_id}` | 충족 |
| `GET /learning/result` | `POST /v1/me/objectives/{id}/outcome` | 충족(메서드 다름) |

**11/12 충족 · 1 갭.** 계획서가 "API 숫자가 중요한 게 아니다"라고 스스로 적은 것이 맞다 — 표면은 이미 103개다.

### 4.3 §13 "EOS 내부 경계"

계획서가 위험 신호로 지목한 `if subject == "math":`의 Core 내부 출현은 **이미 기계로 막혀 있다**:
`EOS-65`(경계 목록) · `EOS-66`(SubjectAdapter 2층 계약 + `test_subject_adapter_two_tier_contract.py` 동결) · `EOS-67`(import-linter 3계약 CI 상시) · `EOS-69`(Core 11건 경유 배선) 전부 **done**(2026-08-31). 직접 CORE→ADAPTER import는 **오늘 실측 0건**, 합성 루트 경유 잔여 2건이 계약의 명시 예외로 남아 **G1(9/27) 재확인** 대상이다.

→ 계획서 §13은 **9월 말에 이미 끝난 일**이다.

---

## §5. 되돌리기 비싼 제안 4건 — 채택 전 명시적 결정 필요

| # | 계획서 제안 | 저장소가 이미 내린 판정 | 위험 |
|---|---|---|---|
| **A** | §3 학습 상태 머신 8상태 신설(`NEW→DIAGNOSING→READY→LEARNING→PRACTICING→ASSESSING→REMEDIATING→ADVANCING`) | 대응물 **0건**(어휘·역할 양쪽 검색) — 진짜 부재다. 다만 저장소는 상태를 **머신이 아니라 이력**으로 모델링했다(`*MasteryHistory` append-only + `attempt_event` 시계열) | 8상태를 새로 세우면 **같은 사실의 두 번째 진실 원천**이 생긴다(mastery 이력 vs 상태 필드). 붕괴 연쇄 "유지보수 지옥 ← truth source가 하나가 아님"의 교과서 사례. **필요성 근거(이 상태가 없으면 어떤 오류가 나는가)를 먼저 적어야 한다** |
| **B** | §2·§8 Mastery v1을 "정답 +0.10 / 오답 −0.08" 단순 heuristic으로 시작 | BKT·IRT·θ 추적·문항 캘리브레이션이 **이미 운영 중** | 채택하면 **작동 중인 것을 더 나쁜 것으로 교체**한다. 계획서는 저장소를 보지 못한 상태로 쓰였다(006 §8.3 자인의 연장) |
| **C** | §12 API 12종 신설 | 103개 엔드포인트에 11/12 대응 | 제2 표면(`/attempts` vs `/v1/me/attempts`) — API 어휘 분기 |
| **D** | §20 PR 단위를 "기능"에서 "Vertical Slice"로 전환 | 저장소 PR 단위는 **태스크(백로그) 1:1**이며 acceptance 전수 대조·PR 증적 게이트가 걸려 있다 | **부분 채택 권고** — 아래 §8-③ |

> 공통 원인은 200 검토와 같다: 계획서는 **저장소를 열람하지 않고** 쓰였다. 그 자체는 결함이 아니지만, **대조 없이 순서대로 실행하면 이미 있는 것을 다시 만들거나 더 나쁜 것으로 덮는다.**

---

## §6. 계획서가 옳게 짚은 진짜 갭 4건

| # | 갭 | 실측 | 대응 후보 |
|---|---|---|---|
| **G-1** | **학생 입력이 서버 루프에 도달하지 않는다** — Flutter가 `POST /v1/me/attempts`를 호출하지 않아 `problem_attempt` 0행, θ는 콜드스타트 0.0 고정, 약점 가중은 전 후보 중립(1.0) | `src/mobile/lib/` 전수 grep `attempts` 0건 · REC-01 관측 리포트 | **신규 태스크 후보 ①** (§8) |
| **G-2** | **E2E가 루프의 뒷반쪽을 밟지 않는다** — 백엔드·클라 E2E 둘 다 verify에서 종료. attempt→assessment→mastery→다음 추천 관통 실증 0 | `test_e2e_vertical_slice_integration.py:281` · `e2e_loop_flow_test.dart:156` | **신규 태스크 후보 ②** |
| **G-3** | **LearningSession writer 0** — 스키마는 §6.1 DDL로 정본화됐으나 생산자가 없어 추천 처치→결과 결합이 `uuid4()` placeholder로 끊긴다 | `l2/recommendation_evidence.py` docstring 자인 | **신규 태스크 후보 ③** |
| **G-4** | **학습 상태 머신 부재** — 다만 §5-A의 이중 진실 원천 위험과 함께 판단해야 한다 | 4어휘 전수 0건 | **판단 대기**(§8-⑤) |

**G-1·G-2는 계획서 300의 Gate 2 6·10번 미충족의 유일한 원인이며, 동시에 저장소 G4(12/13) "수동 개입 0 루프 3연속"의 선결이다.** 즉 **두 계획의 교집합**이다 — 어느 전제를 택하든 해야 한다.

---

## §7. KPI 5축 대조 (계획서 §19)

| KPI | 계획서 목표 | 저장소 실측 | 판정 |
|---|---|---|---|
| 1. Loop Completion Rate | >95% | 측정기 없음. 인접: `ops/recommendation_reach_report.py`(추천 도달) | **갭** — 분모(세션)가 G-3 때문에 정의 불가 |
| 2. State Integrity(불일치 <1%) | — | `harness/assessment_seat_reach_report.py`가 4테이블 결손 관측 | **부분** |
| 3. Explainability(이유 없는 추천 0) | — | PATH-02/09/10 done(정렬 근거 서버·영속·렌더 3단) · **REC-11 todo(P0)로 `candidates[]`·`policy_version` 미영속** | **부분** |
| 4. Manual Intervention(DB 개입 0) | — | 저장소 **G4(12/13)** 조건 | 일정 충돌(§2 ★) |
| 5. Traceability(역추적 100%) | — | `evidence_event`·`attempt_event`·`EVENT_DATA_CONTRACT` 실재. **다만 4층(Attempt·Evaluation·Assessment·Mastery) 경계 정본이 없어**(EOS-79 todo·P1) 어느 층 증거인지 판정 근거가 사람 머릿속에만 있다 | **부분** |

> KPI 3·5는 **이미 등재된 태스크(REC-11·EOS-79)가 소유**한다. 계획서가 KPI로 부른 것을 저장소는 태스크로 갖고 있다 — 신규 등재가 아니라 **우선순위 조정** 문제다.

---

## §8. 살아남는 지향성 → 조치 후보 (등재는 Kiki 판단 뒤)

계획서 300에서 **저장소가 아직 안 가진, 그리고 어느 전제에서도 유효한** 항목만 남긴다.

| # | 조치 후보 | 근거 | 규모 추정 | eos_priority 후보 |
|---|---|---|---|---|
| **①** | **Flutter attempt 제출 배선** — `POST /v1/me/attempts` 클라 호출 착지. 서버는 이미 mastery·skill·event까지 전파하므로 **클라 1개 호출이 루프를 닫는다** | G-1 · REC-01 관측 | 1~2일 | **P0** |
| **②** | **E2E 뒷반쪽 연장** — 기존 `test_e2e_vertical_slice_integration.py`·`e2e_loop_flow_test.dart`를 attempt→mastery_updates→다음 추천까지 연장(신규 테스트 파일 신설 아님) | G-2 · G4 선결 | 1~2일 | **P0** |
| **③** | **Vertical Slice PR 규약 부분 채택** — 계획서 §20을 *태스크 분해 지침*으로만 흡수: "표면 1개만 만드는 태스크"보다 "학생이 실제로 도달하는 슬라이스"를 선호. 저장소 PR:태스크 1:1은 유지(대장 정본 불변) | §5-D | 규약 1줄 | P2 |
| **④** | **LearningSession writer 판정** — 배선하거나, 안 할 거면 스키마를 폐기 판정한다(EOS-72 `ContentLifecycleState` "배선 또는 폐기" 선례 동형) | G-3 | 판정 0.5일 | P1 |
| **⑤** | **상태 머신 채택 여부 결정(Kiki 게이트 후보)** — 8상태 신설 vs 현행 이력 모델 유지. 이중 진실 원천 위험 때문에 세션이 단독 판단할 사안이 아니다 | §5-A · G-4 | 결정 | — |
| **⑥** | **Gate 2 이름 충돌 표기 규약 확정** — `G2` vs `Phase 2 Gate(300)`. 10/25 판정문 작성 **이전**에 | §3-B · 3회차 | 규약 1줄 | P1 |

**이미 등재돼 우선순위만 올리면 되는 것**: `REC-11`(P0·추천 영속) · `EOS-79`(P1·4층 경계) · `ADMIN-07`(P0·검수 UI) · `REC-10`(정직 표기 렌더).

**등재하지 않는 것**: §12 API 12종 신설 · §6 Mastery heuristic · §2 recommend() 재설계 · §3 상태 머신(⑤ 결정 전) — 전부 §5의 되돌리기 비싼 축.

---

## §9. 재제출된 006(50항목)에 대하여

**재대조하지 않는다 — 이미 흡수 완료분이다.** 경위:

- 2026-08-30 `docs/strategy/eos_transition_declaration_2026-08-30.md`가 006을 근거 문서 ①로 명시 흡수(선언 §0 · 부록 A~E).
- 2026-08-31 `docs/reviews/eos_source_docs_gap_review_2026-08-31.md` §3이 **50항목 전수 판정** — 충족 27 · 부분 13 · 의도적 미채택 5 · 갭 5.
- 2026-09-01 `docs/reviews/eos_plan52_crosswalk_2026-09.md`(EOS-53 done)가 개발항목 53건을 이미구현 11 / 부분 27 / 신규 7 / 이월 8로 전수 매핑.
- 006 §1·§44의 베이스라인 태그는 **집행 완료** — `whymath-mvp-final-2026-08-30` → `0d6fb82d`(EOS-06 done · ls-remote 역참조 실측).

**006에서 아직 살아 있는 갭 3건**(전부 등재·게이트화 완료이므로 신규 조치 불요):
1. §11·§24 기존 기능 4분류(KEEP/REFACTOR/POSTPONE/DROP) 장부 — `EOS-68` done(Migration Map)이 부분 대체, P0~P3는 `eos_priority` 필드로 **205건 백필 완료**(EOS-80 · P0 13·P1 82·P2 94·P3 15). 잔여 302건은 필드 없음 = 12월 비관여로 판정된 분.
2. §4 ADR 번호 계열 — **게이트 대기 중**(`G-eos-adr-numbering-series`[kiki/decision]).
3. §26 One In → One Out(P0 교환제) — 저장소에 규칙 부재(source_docs_gap_review §2 Rule 4). 006 재제출을 계기로 **채택 여부만 물을 가치가 있다**.

> 006의 §43("EOS 전환 = 전면 재작성이 아니다")과 §50-⑩("신규 PR마다 12월에 필요한가 Gate")은 선언 §0-5로 이미 규칙화됐다.

---

## §10. 권고 — 한 문장

**계획서 300의 4주 일정을 채택하지 말고, 그 안에서 §8의 ①②를 즉시(수일 규모) 집행한 뒤 10월을 G2(앵커 2개 × 60 CU · HIT 실측)에 쓰는 것을 권한다.** ①②는 계획서 Gate 2의 막힌 두 칸을 동시에 열고, 저장소 G4(12/13 · 수동 개입 0 루프 3연속)의 선결이며, **두 전제 어느 쪽을 택해도 버려지지 않는 유일한 교집합**이다. 반대로 계획서 순서대로 4주를 쓰면 이미 있는 엔진을 더 단순한 것으로 덮으면서(§5-B) 정작 루프는 클라 호출 1건이 없어 여전히 닫히지 않는다.

**Kiki 판단이 필요한 3건**: §3-A(Phase 2의 목적 — 폐쇄루프 vs 콘텐츠 생산) · §8-⑤(상태 머신 채택) · §9-3(One In → One Out 채택).

---

**작성**: 2026-09-03 · 조사 전용(코드·대장 변경 0)
**선행 3권**: `eos_source_docs_gap_review_2026-08-31.md` · `eos_plan52_crosswalk_2026-09.md` · `eos_phase1_plan_200_gap_review_2026-09-01.md`
