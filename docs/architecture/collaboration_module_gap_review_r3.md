# 협업(Collaboration) 모듈 — 3차 재점검(r3): 착지 3건의 집행 실측 (2026-08-11)

> **범위**: 외부 참고 문서 『17. 협업』(기능 70 교사 클래스 관리 · 71 학부모 대시보드 · 72 그룹 학습 ·
> 73 토론 기능 · 74 과제 배포, 세부 50개 — **WhyMath 전용이 아닌 일반 EOS 틀**, Kiki 제공)의
> **세 번째 제출**에 대한 재점검.
>
> **성격**: 이 편은 **처음부터의 재대조가 아니다**. 동일 대조가 2026-07-31(v1)·2026-08-04(v2)에
> 이미 수행됐고 그로부터 등재된 `COLLAB-01`~`03`이 **전부 `done`**이다. 따라서 이 편이 묻는 것은
> *"협업에 무엇이 빠졌나"*가 아니라 **"완료 선언된 것이 실제로 돌아가는가"**다.
>
> **v1·v2 이후 상태**: `COLLAB-01`(계약) done(2026-08-05) · `COLLAB-02`(파기 방향) done(2026-08-04) ·
> `COLLAB-03`(집계 writer) done(2026-08-10). v1의 D4(정본 Phase 모순)는 직접 교정 완료.
>
> **결론**:
> 1. **v1의 "협업은 전 스택 0" 스냅샷은 전건 여전히 유효**하다 — 라우터 16개 중 협업 0 · 63테이블 중
>    협업 0 · `l7/` 부재 · Flutter 교사·학부모 화면 0 · Next.js 교사 웹 0 · 알림 인프라 0 ·
>    태스크 255건 중 협업 기능 0. **이것은 부채가 아니라 판정의 결과**이며 코드·문서·백로그가
>    일치하게 그 사실을 명시한다.
> 2. **세부 50개 판정 뒤집기 0.** 착지로 위치가 바뀐 칸은 2개뿐이고 그중 1개는 **정밀화**다(§2).
> 3. **착지 3건 중 2건에 집행 공백이 남았다** — `COLLAB-01`의 게이트는 **자기 계약 파일이 CI 트리거
>    축 밖**이라 계약 단독 수정 PR에서 돌지 않고(D5), `COLLAB-03`의 롤업은 **부르는 주체가 0건**이며
>    응답이 "미집계"와 "무활동"을 구분하지 않는다(D6).
> 4. **계약이 실태보다 느슨해진 곳이 1건** 있다 — `access_matrix.json` #8의 `produced_by`가 `ASM-07`이
>    삭제한 필드를 가리키고, 거버넌스 테스트 ⓓ는 **그 참조가 실재하는지 보지 않는다**(D7).
>
> **핵심 판정**: v1이 *"협업의 임계 경로는 화면이 아니라 매트릭스"*라고 적었다면, r3의 판정은
> **"매트릭스는 깔렸는데 그 매트릭스를 지키는 장치 자신이 깨울 입력 경로 밖에 있다"**이다.

관련 정본: `collaboration_module_gap_review.md`(v1 — **무수정**) ·
`collaboration_landing_design.md`(v2 — **무수정**) · `07_community.md`(L7 정본) ·
`docs/legal/pipa_data_matrix.md`(권한 매트릭스 원천) · `data/access_matrix.json`(계약) ·
`assessment_module_gap_review.md`(`ASM-02`·`ASM-07` — D7의 상대편) ·
`MEMORY.md` 결정 로그(2026-07-31 · 2026-08-04 · 2026-08-11).

---

## §0. 재점검 사유 — 스코프 고정

### ①-a 동일 문서 재제출임을 수치로 확정 (추론 아님)

| 축 | 3차 제출본(2026-08-11) | v1 기록(2026-07-31) | 일치 |
|---|---|---|---|
| 기능 번호 | 70~74 | 70~74 | ✅ |
| 기능 명칭 | 교사 클래스 관리 / 학부모 대시보드 / 그룹 학습 / 토론 기능 / 과제 배포 | 동일 | ✅ |
| 세부 기능 수 | 70:10 · 71:10 · 72:10 · 73:10 · 74:10 = **50** | **50** | ✅ |
| 단계 표기 | "1단계" | "1단계"(**반려**됨) | ✅ |
| 아키텍처 그림 | 관리자 → 협업 → AI Tutor/Learning Analytics → 학생 | 동일 | ✅ |

세부 항목까지 문자열 단위로 동일하다. **새로 대조할 제안이 0개**이므로 §1을 기능 체크리스트로
반복하지 않는다 — 그건 v1의 복사이고 무가치하다.

### ①-b v1·v2를 in-place 수정하지 않는 이유

`COLLAB-01`~`03`의 `notes`가 판정 근거로 **v1의 § 번호를 지목**한다(예: `COLLAB-02.notes` =
"collaboration_module_gap_review.md §3 D2"). v1을 소급 변조하면 완료된 태스크가 *왜 그렇게
결정됐는가*를 가리키는 좌표가 사라진다. 정정 사항은 **§정정에만** 기록한다
(`gamification_r2`·`learning_path_r2`·`solution_r3` 공통 규율 승계).

### ①-c 승계 선언 — 이 편이 **재판정하지 않는 것**

- **세부 50개 판정 전건**(🚫22 · ⌛15 · ⏸5 · ✅4 · △2 · ⚠️2) — §2의 2칸 외 변경 없음
- **§2 의도적 미채택 8종**(①화이트보드·그룹채팅·게시판 ②AI 토론요약·팩트체크 ③출석 ④LMS ⑤성적반영
  ⑥팀 성과·랭킹 ⑦그룹 AI Tutor ⑧학급 코드 초대) — 영구/조건부 구분 포함 **전건 승계**
- **v2의 소유 축 A~E 5분류 · 3배관 처리표 · B형 익명화 3기준 · 보호자 접근 ⓒ/ⓑ 권고 ·
  매트릭스 확장 10~15번** — 전건 승계
- **틀의 "1단계" 표기 반려** — Phase 3+는 자의적 배치가 아니라 선결 조건의 귀결이라는 v1 판정 승계
- **역할 서열 설계**(`account_security_gap_review.md` §2-①) — 재판정 대상 아님

### ①-d 갭이 아닌 것 — 정직 자인은 트리거다

다음은 **코드·계약이 스스로 미완임을 밝힌 곳**이며 갭으로 계수하지 않는다(v1 §0 ①-d 규율 승계).

- `data/access_matrix.json` `consumers` — 소비처를 "governance gate"와 "future seat (Phase 3+)"
  둘로만 열거. 런타임 인가에 쓰이지 않음을 **계약 자신이 자인**
- `roles.teacher.role_enum_value: null` · `status: "planned"` — 좌석 없는 역할 미개설의 명시
- `privacy/audit.py:11` — `record_admin_access_audit` 호출부 0곳 자인
- `l3/escalation_defaults.py:12,40` — `subscription_tier` 실 DB 읽기 미도입 자인
- `erasure.py:161` `external_erasure_targets()` — PG 밖 삭제는 목록만 반환하고 실행은 ops 책임임을 명시

---

## §1. 착지 3건의 집행 실측

판정 기준은 **3단**이다 — ⓐ 산출물이 실재하는가 ⓑ CI에서 돌아가는가 ⓒ **집행 지점이 있는가**.
ⓐ만 보고 완료로 치는 것이 CLAUDE.md 2026-08-04가 금지한 *"정본화를 집행으로 착각한 완료 선언"*이다.

| 태스크 | ⓐ 실재 | ⓑ CI 배선 | ⓒ 집행 지점 | 판정 |
|---|---|---|---|---|
| **COLLAB-01** 권한 매트릭스 계약 | ✅ `data/access_matrix.json`(9,632B · 9항목 × 4역할 × `full｜summary｜none`) + `tests/backend/schema/test_access_matrix.py`(21KB · 변별력 4축) | **△ 부분** — 테스트 파일은 `tests/backend/**`로 트리거되나 **계약 파일 자신이 필터 밖** | ⌛ 서빙 필터링은 `planned` 역할 좌석(정당한 유예·자인됨) / **⚠️ 참조 무결성 사각** | **→ D5 · D7** |
| **COLLAB-02** 파기 완전성 방향 역전 | ✅ `privacy/erasure.py:124-140` 사유 명시 허용목록 3건 + `tests/backend/privacy/test_erasure_plan_completeness.py` | ✅ `tests/backend/**` | ✅ `Base.metadata.tables` 전수 스윕 — 협업 테이블 신설 시 **강제로 red** | **✅ 완결** |
| **COLLAB-03** 학습지표 writer | ✅ `l2/learning_metrics_rollup.py` + `harness/learning_metrics_rollup_cli.py` + `GET /v1/me/learning-metrics`(`api/me.py:3382`) | ✅ `tests/backend/**` | **⚠️ 부르는 주체 0건** — 자동 적재가 일어나지 않고, 응답이 "미집계"와 "무활동"을 구분하지 않음 | **→ D6** |

**COLLAB-02는 이 세 건 중 유일하게 3단을 다 통과한다.** 주목할 점은 그 집행이 *협업 테이블이 아직
0건인데도* 유효하다는 것이다 — "학생 삭제가 공유 풀이·토론글까지 전파되는가"는 현재 **대상 공집합**
이므로 vacuously true이지만, 완전성 스윕이 존재하므로 **협업 테이블이 신설되는 순간 red가 나서 강제로
결정하게 된다**. v1이 D2를 D3보다 앞세운 이유("되돌릴 수 없음")가 설계대로 작동한 형태다.

---

## §2. v1 판정의 변경분 — 바뀐 칸만

| v1 위치 | v1 기술 | r3 실측(2026-08-11) | 처리 |
|---|---|---|---|
| 71-3 약점 분석 | ⚠️ 진짜 갭 → D1 | 계약 착지(`access_matrix.json` #6 `gap_concepts`) · 뷰 좌석은 여전히 없음 | **⌛ 좌석 대기로 이동** |
| 71-4 학습시간 통계 | ⚠️ 진짜 갭 → D3 | writer·조회 좌석 실재 / **적재 주체 0 · 클라 도달 0** | **△ 부분으로 정밀화** → D6 |

**뒤집기 0.** 71-4를 ✅로 올리지 않은 이유가 이 편의 핵심이다 — 산출물이 실재하는 것과 데이터가
차는 것은 다른 축이며, v1 D3이 지목한 병("배관만 있고 데이터가 없다")은 **해소된 것이 아니라 한 단계
뒤로 이동**했다. 이전에는 *표를 채울 코드*가 없었고 지금은 *코드를 부를 주체*가 없다.

---

## §3. 잔여 갭 설계

번호는 v1의 D1~D4에 **이어 붙인다**(충돌 회피). 실행 순서는 **D5 → D7 → D6**이다 — D5가 최우선인
이유는 그것이 *다른 계약들의 게이트까지 함께 무력화하는 횡단 사각*이기 때문이다.

### D5 — 계약 fixture가 CI 트리거 축 밖이다: 게이트가 자기 계약을 지키지 못한다 (최우선)

**증상.** `.github/workflows/ci.yml:74` backend 잡의 changes 필터:

```
^(src/backend/|tests/backend/|conftest\.py$|data/notation_contract\.json$|data/render_contract\.json$|\.github/workflows/ci\.yml$)
```

`data/access_matrix.json`이 **없다**. 계약 파일만 고치는 PR은 backend 잡이 skip되고
`tests/backend/schema/test_access_matrix.py`가 **돌지 않는다** — 이 게이트가 막으라고 만들어진 바로 그
드리프트 벡터다. 항상 도는 `infra-contracts` 잡(`ci.yml:710`)은 `tests/infra`만 실행하므로 대체 경로가
아니다(계약 테스트 6개는 전부 `tests/backend/**`에 있다).

**선례가 있는데 답습 실패.** 바로 그 필터의 두 항목(`notation_contract`·`render_contract`)이 **정확히 같은
사유로** 이미 추가돼 있고, `ci.yml:71-73`에 주석까지 달려 있다 —
*"fixture-only PR이 두 골든 잡을 모두 skip하던 사각 봉합"*.

**실측 재현** (필터 정규식에 파일명을 넣어 매치 여부를 직접 확인):

| 계약 fixture | 소비 테스트 | backend 잡 |
|---|---|---|
| `data/notation_contract.json` | `tests/backend/l3/**` | 실행 ✅ |
| `data/render_contract.json` | `tests/backend/schema/**` | 실행 ✅ |
| **`data/access_matrix.json`** | `tests/backend/schema/test_access_matrix.py` | **SKIP ❌** |
| `data/visual_style_contract.json` | `tests/backend/schema/test_visual_style_render_contract.py` | **SKIP ❌** |
| `data/scene_contract.json` | `tests/backend/l4/test_scene_contract.py` 외 1 | **SKIP ❌** |
| `data/segmentation_contract.json` | `tests/backend/l5/ocr/test_text_segmentation.py` | **SKIP ❌** |
| `data/notation_support_manifest.json` | `tests/backend/l3/test_notation_coverage_eval.py` | **SKIP ❌** |

즉 `data/*.json` 계약 8개 중 트리거 등재는 **2개뿐**이며, 협업 축(`access_matrix`)은 등재되지 않은 쪽이다.

**왜 지금까지 안 드러났는가.** `COLLAB-01` acceptance ⑥은 *"신설 테스트가 실제로 CI 잡에서 실행되는지
확인한다('저장소에 존재함'과 '돌아감'은 다르다 — OPS-03·OPS-10·OPS-11 선례)"* 였다. 확인은
**테스트 파일 축**에서 이뤄졌고 정당하게 통과했다 — `tests/backend/**`는 필터에 있다.
보지 않은 것은 **계약 파일 축**이다. "존재함 ≠ 돌아감"의 한 단계 안쪽에
**"돌긴 도는데 깨울 입력 경로가 필터 밖"** 이라는 층이 있었다.

**설계** (신규 잡 0 · 신규 추상 0 · 계약 내용 변경 0).
backend 잡 필터에 계약 fixture 축을 추가한다. 개별 파일 나열이 **이미 한 번 누락을 낳았으므로**
`data/` 계약 묶음을 어떻게 표현할지(개별 나열 유지 vs 접두 패턴)는 태스크에서 정하되, 어느 쪽이든
**새 계약을 추가할 때 트리거 등재를 강제하는 장치**를 함께 둔다 — 그것이 없으면 이 결함은 다음 계약에서
그대로 재발한다.

**변별력.** 계약 파일만 변경한 상태를 합성해 필터가 `be=true`를 내는지 실측한다 — **현행에서 red,
수정 후 green**. 성공/실패에서 같은 값이 나오면 검증이 아니라 위장이다.

**하지 말 것**: 새 CI 잡 신설 · 계약 테스트를 `infra-contracts`로 이관(백엔드 의존성이 필요하므로
"29초 경량 잡" 설계를 깬다) · 계약 파일 내용 변경 · `web` 잡 필터(`ci.yml:86`)의 동일 사각은
**같은 태스크에서 함께 볼 것**(같은 두 계약만 등재돼 있다).

### D7 — 계약의 `produced_by`가 유령을 가리키고, 거버넌스 테스트는 그걸 보지 않는다

**증상.** `data/access_matrix.json` #8 `peer_comparison`(또래 비교)의 산출 매핑:

```
"produced_by": ["GET /v1/me/assessments —
  src/backend/whymath_backend/schema/assessment.py::AssessmentSchema.estimated_percentile
  (api/me.py::list_my_assessments)"]
```

실측하면 이 좌표는 **두 겹으로 어긋난다**.

1. `assessment.py`에 **`AssessmentSchema`라는 클래스가 없다** — 그 이름은 `api/me.py:175`의
   *별칭*(`Assessment as AssessmentSchema`)이고, 별칭이 가리키는 `Assessment`는 **내부·영속 정본**이다.
2. 더 중요한 것: `GET /v1/me/assessments`의 `response_model`은
   `list[StudentAssessmentSchema]`(= `StudentAssessment`)이고(`api/me.py:423`),
   **`StudentAssessment`에는 `estimated_percentile`이 없다**. `ASM-07`(2026-08-08)이
   `STUDENT_HIDDEN_PREDICTION_FIELDS` 5필드를 학생 대면 모델에서 **삭제**했기 때문이다
   (`schema/assessment.py:64-72,75,162` · 동결 테스트 `tests/backend/api/test_prediction_field_sealing.py`
   가 스키마·OpenAPI·페이로드 3층으로 봉인).

**결론 — 갭의 성격.** 학생 안전 축에는 문제가 없다. 오히려 **코드가 계약보다 엄격하다**(계약
`student=summary` vs 실태 `none`). 갭은 두 가지다:

- **계약이 실태보다 느슨하다.** 계약은 정본인데 그 정본이 더 넓은 접근을 선언하고 있다. `teacher`
  칸도 `summary`다 — Phase 3에 교사가 열릴 때 이 칸이 *"요약은 허용"*으로 읽히면 `ASM-02`가
  **(c) 학생 영구 비노출**로 닫은 결정과 정면 충돌한다. 계약이 **먼저 강제하고 있어야 한다**는 것이
  `COLLAB-01`의 존재 이유였는데, 그 계약이 최신 결정을 반영하지 못했다.
- **거버넌스 테스트에 참조 무결성 축이 없다.** ⓓ `_produced_by_violations`
  (`test_access_matrix.py:169-181`)는 *"`produced_by`가 비어 있지 않은 문자열 리스트인가"*만 본다.
  가리키는 심볼이 **실재하는지는 검사하지 않는다.** 그래서 `ASM-07`이 필드를 지웠는데도 게이트는
  green이었다. `MATH-02`("유령 근거 위에서 green인 CI 게이트 정직화")와 **같은 계열**이다.

**왜 지금까지 안 드러났는가.** 계약은 2026-08-05에 작성됐고 `ASM-07` 봉인은 2026-08-08이다.
**계약이 먼저 있었고 나중 결정이 계약을 무효화했는데, 그 사실을 아무도 red로 받지 못했다** —
D5(계약 파일이 트리거 밖)와 합쳐지면 계약은 *고쳐도 안 돌고, 안 고쳐도 안 걸리는* 상태였다.

**설계** (신규 필터링 코드 0 · 신규 컬럼 0 · 계약 해상도 값 변경은 근거 있는 1칸만).

1. **참조 무결성 검사 신설** — `produced_by`의 `path::symbol` 좌표를 실제로 해석해 파일·심볼이
   존재하는지 검사한다. 좌표 표기를 **한 형식으로 통일**한다(현재 저장소 상대 `src/backend/...`와
   짧은 `api/me.py` 두 형식이 섞여 있다).
2. **#8 칸을 실태에 맞춘다** — `student`·`teacher`를 `summary`에서 `none`으로 좁히고,
   `design_note`에 `ASM-02`(c)·`ASM-07` 봉인을 근거로 기재한다. **넓히는 방향이 아니라 좁히는
   방향**이므로 v2 §5의 `deny by default` 원칙과 정합한다.
3. **`produced_by`를 봉인 사실로 교체** — "산출 경로 없음(ASM-07 봉인)"을 표현할 수 있어야 한다.
   v2가 14·15번에 도입한 **"권한 ✕가 아니라 미산출"** 분류를 #8에 적용하는 형태다.

**변별력.** `produced_by`에 존재하지 않는 심볼을 넣어 **red** 실측 → 되돌려 green.
그리고 계약 #8을 `full`로 훼손했을 때 red가 나는 기존 변별력이 여전히 작동하는지 재확인한다.

**하지 말 것**: 역할별 응답 필터링 미들웨어 신설(`planned` 역할 좌석 — Phase 3+ · v1 §4 트리거 5) ·
`PARENT`/`TEACHER` 역할 개설 · `Assessment`(내부 정본)에서 필드 폐기(`ASM-02`가 (d)를 미채택) ·
`pipa_data_matrix.md` §2.2 표의 ●/◐/✕ 기호 변경(법무 검토 축 — 계약의 해상도 좁힘과 표 개정은
별개이며 표를 고치려면 §2.4 절차를 탄다).

### D6 — 롤업을 부르는 주체가 0건이고, 응답이 "미집계"와 "무활동"을 구분하지 않는다

**증상 ①(실행 주체).** 롤업 CLI를 호출하는 cron·celery beat·CI 잡·compose 항목이 **하나도 없다** —
`scripts/`·`.github/`·`docker-compose*.yml`·`infra/` 전건 **0**, `beat_schedule`·`crontab` 백엔드 전체 **0**.
즉 writer는 **수동 실행 전용**이고 자동 적재는 일어나지 않는다.

**증상 ②(선언과 실태의 불일치).** `api/me.py:3400` docstring은
*"공급원은 `l2.learning_metrics_rollup`(**하루 1회 CLI 롤업**)이다"* 라고 적고, `COLLAB-03`의 artifacts도
*"집계 주기 1일 1회(재집계 창 2일)로 확정"* 이라 기록했다. **그 주기를 강제하는 코드가 없다.**

**증상 ③(작동 신호 부재).** 응답 스키마 `LearningMetricsResponse`는 `summary` + `days` 둘뿐이고,
**롤업이 언제 돌았는지·며칠 치가 집계됐는지를 말하는 필드가 없다.** 그래서 학생 화면에서
*"활동이 없어서 빈 것"*과 *"집계가 한 번도 안 돌아서 빈 것"*이 **같은 값**(`days_counted == 0`)으로 보인다.

**공정 기재 — 이미 잘 돼 있는 것(갭 아님).** 같은 docstring이 *"0으로 채워 '활동 없음'처럼 위장하지
않는다"* 고 명시하고 실제로 SUM이 표본 0이면 `null`을 반환한다. **비어 있음 자체는 정직하다** —
빠진 것은 *비어 있음의 원인*이다. 이 구분을 흐리면 정직하게 만들어 둔 부분까지 갭으로 오인하게 된다.

**결론.** CLAUDE.md 2026-08-03 **"작동 신호 없는 알고리즘 부착 금지 — 작동한 비율"**의 대상이다.
*"정상 응답 200은 알고리즘이 일했다는 증거가 아니다."* 여기서는 **정상 응답 200 + 빈 배열**이
"학생이 공부를 안 했다"로도 "우리가 집계를 안 돌렸다"로도 읽힌다.

**설계** (신규 스케줄러 0 · 신규 테이블 0 · 마이그레이션 0).
`COLLAB-03` acceptance ②의 *"새 스케줄러 도입 금지"*를 **승계**한다 — 만들 것은 스케줄러가 아니라
**작동 신호**다.

1. 응답에 롤업 신선도 축을 싣는다 — 마지막 집계 시각과 집계 커버리지(요청 구간 중 롤업이 실제로
   처리한 일수). 원천은 이미 적재된 행이며 **신규 저장소 0**.
2. **미집계를 명시 상태로 만든다** — `days_counted == 0`이 "무활동"과 "미집계"를 구분하도록 한다.
3. 정기 실행 주체를 둘지 여부는 **이 태스크에서 결정하지 않는다** — 발화 트리거만 기록한다
   (아래 §4). 신호가 먼저 있어야 "안 돌고 있다"가 관측되고, 관측 없이 스케줄러를 붙이는 것은
   같은 실수의 반복이다.

**변별력.** 롤업 미실행 상태와 실행 후 상태에서 응답이 **갈리는지** assert — 갈리지 않으면 실패다.
(현행에서는 두 상태가 `days_counted == 0`으로 동일하다.)

**하지 말 것**: cron·celery beat 신설 · 교사·부모 노출(`COLLAB-03` acceptance ⑦ 승계) ·
추론 지표 생산(`churn_risk` 등 — 모델 부재·**날조 금지**) · Flutter 소비 배선(별건 — 학생 클라
도달 0은 이 태스크 범위 밖) · 0으로 채우는 형태의 "빈칸 메우기".

### 등재 요약

| 태스크 | 설계 | track / stage / layer | priority | 좌석 근거 |
|---|---|---|---|---|
| D5 | 계약 fixture CI 트리거 축 | infra-debt / S3 / infra | **2** | 현행 계약 6종에 **즉시** 적용 — 좌석 불요 |
| D7 | 계약 참조 무결성 + #8 실태 정합 | infra-debt / S3 / backend | 3 | 계약은 소비처 없이도 불변식(`render_contract` 동형) |
| D6 | 롤업 작동 신호 | math-completion / S4 / backend | 3 | `/v1/me/learning-metrics`가 이미 학생 1인칭 좌석 |

> 실제 ID는 `backlog.py add`가 배정한다 — **번호 추론 금지**(CLAUDE.md · HARN-10 · HARN-15).

---

## §4. 미등재 트리거 — v1 §4의 재확인 (P1)

**페이퍼 갭 P1 — 유보에 재확인 지점이 없다.** v1 §4의 7건은 **발화 조건만** 있고 *누가 언제 확인하는가*가
없다. CLAUDE.md 2026-08-03 *"만료 없는 유예·제외 금지"*는 유예에 만료 **또는 재확인 지점**을 요구한다.
실측하면 **11일간 아무도 확인하지 않았고 이번 r3가 첫 확인**이다.

지금 태스크로 만들면 dead task이므로(발화 조건 전건 미충족) **이 문서가 재확인 지점 자체가 된다**.
아래가 2026-08-11 기준 확인 결과이며, **다음 확인 트리거를 명시**한다.

| # | 유보 항목 | 발화 조건 | 2026-08-11 확인 | 다음 확인 트리거 |
|---|---|---|---|---|
| 1 | 교사 웹·학급·과제 배포(70·74) | Phase 3 진입 또는 B2B 학교 5곳 도입 의향 | **미발화** | ROADMAP Phase 3 게이트 갱신 시 |
| 2 | 학부모 대시보드(71) | `MGMT-01` unblock **그리고** 보호자 인증 모델 확정 | **미발화** — `MGMT-01` `blocked`(owner=kiki) | `MGMT-01` status 전이 시 |
| 3 | 알림 인프라 | 2번 발화 후 | **미발화** · 인프라 실측 0 | 2번과 동시 |
| 4 | `record_admin_access_audit` 배선 | 관리자 콘솔 Phase B 또는 교사 대시보드 착지 | **미발화** — 호출부 0곳 유지(자인됨) | `ADMIN-01` 착수 시 |
| 5 | `PARENT`·`TEACHER` 역할 개방 | 1·2번 중 하나 | **미발화** — 계약이 먼저 강제 중(선후 충족) | **D7 선행 필수**(계약 #8이 실태와 어긋난 채로 열리면 안 된다) |
| 6 | 다중 풀이 갤러리 | `S4-12` 완료 + Phase 3 | **미발화** — `S4-12` `todo` | `S4-12` done 전이 시 |
| 7 | 조직 테넌시 | B2B 계약 체결 | **미발화** — `ADMIN-02` `todo`(`school_id` 등 소비처 0) | `ADMIN-02` 착수 시 |

**5번의 선후 관계가 r3에서 바뀌었다** — v1은 *"개방 시 D1 계약이 이미 강제하고 있어야 한다"*고 적었고
그 조건은 충족됐으나, **D7이 드러낸 대로 그 계약이 최신 결정을 반영하지 못한 상태**다. 역할 개방 전에
D7이 선행해야 한다.

---

## §정정 — v1·v2 stale (원본 무수정, 여기에만 기록)

| # | 원본 기술 | r3 실측(2026-08-11) | 처리 |
|---|---|---|---|
| 1 | v1 §0 ①-b · 부록 "`db/models/*.py` `__tablename__` 전수 = **62**" | **63** | 자연 증가분이며 **협업 테이블 아님**. v1의 "협업 0" 판정은 유효 |
| 2 | v1 §0 ①-b "라우터 **15개** 중 협업 0" | **16개** 중 협업 0 | 동일 — 판정 불변 |
| 3 | `COLLAB-03` artifacts "집계 주기 1일 1회(재집계 창 2일)로 확정" · `api/me.py:3400` docstring "하루 1회 CLI 롤업" | **주기를 강제하는 코드 0** | **D6가 상환**. 문서 문구는 D6 태스크에서 실태에 맞춘다 |
| 4 | `access_matrix.json` #8 `produced_by` → `AssessmentSchema.estimated_percentile` | 해당 클래스 부재(별칭) · 학생 응답에서 `ASM-07`이 삭제 | **D7이 상환** |

**오탐 방지 — 정정 대상이 아닌 것**

- v1 D3의 *"3테이블이 파기·반출·보존 배관에 전부 등재"* → **v2가 이미 정정**했다
  (`ProblemSolveTimeDistribution`은 교차 사용자 집계라 `export.py`가 의도적 영구 제외 — 배관 등재는 2건).
  **재정정 아님.**
- v1 §5-⑦ *Live Problems Phase 불일치(정본 4 vs ROADMAP 3) 미교정* → **의도적 유보**이며 사유
  (`S4-12` 진척 의존)가 여전히 유효하다. 갭으로 계수하지 않는다.
- `data/access_matrix.json`의 런타임 소비처 0 → **계약이 자인**한 설계 의도(§0 ①-d). 갭은 "소비처가
  없다"가 아니라 **"계약이 실태와 어긋난 걸 아무도 못 잡는다"**(D7)이다.

---

## §5. 반복 실수 10회차 등재 — 트리거 축 부분 배선

| 회차 | 형태 |
|---|---|
| 1~6 | 만들고 CI 배선 안 함 / 적재 안 함 / 배포에 안 넣음 / 입력을 안 이음 / 안 켬 / 공급원을 안 이음 |
| 7 | 인가 축 단절(`require_content_admin` 통과 주체 부재) |
| 8 | dead 컬럼(만들고 읽지 않음의 스키마 판) |
| 9 | 정직 표기가 영속·렌더 경계에서 소실(`learning_path_r2`) |
| **10** | **트리거 축 부분 배선** — 테스트는 CI에 있는데 *그 테스트를 깨울 입력 경로*가 필터 밖 |

**왜 새 축인가.** 1~6은 *산출물이 어딘가에 연결되지 않은* 형태이고, 9는 *표기가 경계를 넘으며 사라진*
형태다. 10회차는 **연결이 되어 있는데 조건부**라서, 정상 상태(코드를 함께 고치는 PR)에서는 완전히
정상으로 보이고 특정 변경 형태(계약 단독 수정)에서만 무력해진다. `COLLAB-01` acceptance ⑥이
"CI에서 돌아가는가"를 **정당하게 확인하고 통과했는데도** 남았다는 점이 이 유형의 특징이다.

**남길 원칙**: *"계약 fixture를 만들면 그 fixture 자신이 CI 트리거 축에 들어갔는지 확인한다 —
테스트 파일이 트리거되는 것과 계약 파일이 트리거되는 것은 다른 축이다."*

**재발방지는 산문이 아니라 코드로.** 이 원칙을 CLAUDE.md 문장으로만 두지 않고 **D5 태스크가
"새 계약 추가 시 트리거 등재를 강제하는 장치"로 착지**시킨다(`solution_r3` R4 규율 — "다음엔
조심한다"는 대책이 아니다). 헌법 개정은 이 커밋에서 하지 않고 **등재 후보로만 제안**한다
(`learning_path_r2` §9).

---

## §6. 검증 — 무엇을 돌렸고 결과가 무엇인가

문서·백로그 변경이므로 코드 스위트는 해당 없다(`git diff --stat -- src/` **빈 결과**로 확인).
대신 **이 문서가 주장하는 사실을 실행으로 확인**했다.

- `backlog.py validate` → **exit 0**
- `pytest tests/harness` → 회귀 0
- §1·§3의 "0건" 주장 전건을 grep·정규식 매치로 실측(부록)
- **D5는 추론이 아니라 필터 정규식 직접 매치로 확인** — 계약 8개 파일명을 `ci.yml:74`의 실제 정규식에
  넣어 `access_matrix`를 포함한 5건이 매치 실패함을 실측
- **D7은 심볼 해석으로 확인** — `StudentAssessment` 필드 집합에 `estimated_percentile` 부재 ·
  `AssessmentSchema`가 `api/me.py:175`의 별칭임 · `test_access_matrix.py:169-181`이 문자열 비어있음만
  검사함을 **원문으로** 확인(추론 아님)
- **D6은 호출부 스캔으로 확인** — `learning_metrics_rollup`을 `scripts/`·`.github/`·compose·`infra/`에서
  전건 0, `beat_schedule` 0

**정직한 공백**: 전체 백엔드 스위트는 이 세션에서 돌리지 않았다(`src/` 미변경). 돌리지 못한 것은
"전체는 확인하지 못했다"로 남기고 CI를 최종 판정으로 넘긴다.

---

## §7. 이 리뷰가 답하지 않는 것

1. **정기 실행 주체를 둘 것인가**(D6 ③) — 신호가 먼저 관측돼야 판단할 수 있다. 스케줄러 신설은
   이 편의 관할이 아니다.
2. **`pipa_data_matrix.md` §2.2 표 자체의 개정** — D7은 *계약*을 실태에 맞춰 좁히는 것이고, md 표의
   ●/◐/✕ 기호 변경은 §2.4 절차(변호사 검토 포함)를 탄다. 섞지 않는다.
3. **교사 웹 IA·B2B 사업 조건·보호자 인증 방식** — v1 §5-4·5, v2 §4가 이미 소관을 지정했고
   `MGMT-01`(법무)이 정본이다. 기계 대체 금지.
4. **`data/*.json` 계약 6종 각각의 내용 정합성** — D5는 *트리거 축*만 상환한다. 트리거가 켜진 뒤
   각 계약이 실제로 실태와 맞는지는 그때 red가 말해준다(D7이 `access_matrix`에서 보인 형태).
5. **학습지표의 Flutter 도달 0** — 서버 좌석은 있고 클라가 부르지 않는다. 별건이며 모바일 축
   태스크로 다룰 사안이다.
6. **v1 §2 미채택 8종의 재론** — 승계이며 이 편의 관할이 아니다.

---

## 부록 — 재현 명령 (2026-08-11 확인)

```bash
# ① 협업 전 스택 0 (v1 스냅샷 유효성)
grep -rhoP '__tablename__\s*=\s*"\K[a-z_]+' src/backend/whymath_backend/db/models/*.py | sort -u | wc -l   # 기대: 63
grep -c "include_router" src/backend/whymath_backend/app.py                                                # 기대: 16
grep -rn "access_matrix" src/ | wc -l                                                                      # 기대: 0

# ② D5 — 계약 fixture가 backend 잡 트리거 필터에 매치되는가
for c in data/access_matrix.json data/notation_contract.json data/visual_style_contract.json \
         data/scene_contract.json data/segmentation_contract.json; do
  printf '%s\n' "$c" | grep -qE '^(src/backend/|tests/backend/|conftest\.py$|data/notation_contract\.json$|data/render_contract\.json$|\.github/workflows/ci\.yml$)' \
    && echo "$c → 실행" || echo "$c → SKIP"
done
# 기대: notation_contract만 "실행", 나머지 4건 "SKIP"
grep -rn "access_matrix" .github/workflows/   # 기대: 0건 (exit 1)

# ③ D6 — 롤업 CLI 호출 주체
grep -rn "learning_metrics_rollup" scripts/ .github/ docker-compose*.yml infra/ 2>/dev/null | wc -l  # 기대: 0
grep -rn "beat_schedule\|crontab" src/backend/ | wc -l                                               # 기대: 0

# ④ D7 — 계약이 지목한 산출 경로의 실재
grep -n "class StudentAssessment\|class Assessment" src/backend/whymath_backend/schema/assessment.py  # 기대: 75, 162
grep -rn "class AssessmentSchema" src/                                                                # 기대: 0건
grep -n "AssessmentSchema" src/backend/whymath_backend/api/me.py | head -1                            # 기대: :175 별칭 import
grep -n "response_model=list\[StudentAssessmentSchema\]" src/backend/whymath_backend/api/me.py        # 기대: :423
sed -n '169,181p' tests/backend/schema/test_access_matrix.py   # 기대: 문자열 비어있음만 검사(참조 해석 없음)

# ⑤ 범위 규율
git diff --stat -- src/          # 기대: 빈 결과
```

| 축 | 값 | 본문 위치 |
|---|---|---|
| 협업 테이블 | 63 중 0 | §정정 1 · §0 ①-d |
| 계약 fixture 트리거 등재 | 8 중 **2** | §3 D5 |
| 롤업 호출 주체 | **0** | §3 D6 |
| `produced_by` 유령 참조 | **1**(#8) | §3 D7 |
| 세부 50개 판정 뒤집기 | **0** | §2 |
| 등재 태스크 | **3** | §3 등재 요약 |

---

**버전**: 1.0 · **작성**: 2026-08-11 (claude 점검, Kiki 3차 제출)
**후속**: D5 → D7 → D6 순. 역할 개방(v1 §4 트리거 5)은 **D7 선행 필수**
**교차링크**: `collaboration_module_gap_review.md`(v1) · `collaboration_landing_design.md`(v2) ·
`assessment_module_gap_review.md`(`ASM-02`·`ASM-07`) · `07_community.md` · `docs/legal/pipa_data_matrix.md`
