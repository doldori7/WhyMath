# 빌드 하네스 (Build Harness) — 작업일정 관리·순차 조율 표준

> **정본**: `backlog/` + `scripts/harness/` | **채택**: 2026-07-08 결정로그 | **버전**: 1.2 (2026-08-10 통합점검 — gates add 반영·테스트 수 실측 정정. 1.1 이후 §4 삭제 403 런북(2026-08-06 HARN-16)이 버전 표기 없이 추가돼 있었다)
>
> 이 문서의 "빌드 하네스"는 프로젝트 *구축을 관리하는* 레이어다.
> `src/backend`의 WH-1(튜터링)·WH-S(솔버)는 **제품 런타임 하네스**로 완전히 별개다.

---

## 1. 무엇이 바뀌었나 (구 하네스 → 신 하네스)

| | 구 (2026-07-08 이전) | 신 |
|---|---|---|
| 작업일정 | 사람이 편집하는 마크다운에 분산 (stale) | `backlog/` 기계가독 단일 진실 원천 |
| 다음 작업 | 세션마다 사람이 지시·Claude가 재추론 | `next`가 결정적으로 계산 |
| 세션 시작 | 수동 `/status` | SessionStart 훅이 브리핑 자동 주입 |
| 상태 갱신 | 자율 (자주 누락) | Stop 훅이 미갱신 종료 차단 |
| 사람 대기 | ROADMAP 산문에 묻힘 | `gates.yaml` 대장 + 경과일 리마인드 |
| 순차 진행 | 없음 | `/drive` 주도 모드 루프 |
| 과목 범위 | 수학 암묵 | 다과목 개방 스키마 (E축: 물리~영어, 지구과학 배치 결정 대기) |

## 2. 단일 진실 원천 — `backlog/`

```
backlog/tracks.yaml           트랙 3종 + stage_order (S0~S5 → E1~E6)
backlog/gates.yaml            사람 게이트 대장 (Kiki 수동 대기 추적)
backlog/tasks/<id>.yaml       태스크당 1파일 — 병렬 세션 충돌 원천 차단
backlog/events/<actor>.ndjson append-only 감사 로그 — **세션(=브랜치)당 1샤드** (HARN-46)
backlog/events.ndjson         레거시 단일 대장 — 읽기 전용 역사 (신규 기록 없음)
backlog/policy.yaml           조율 정책 — 겹침·ad-hoc 감지 강제 수준 (off|warn|block)
```

> **이벤트 샤딩 경위(HARN-46 · 2026-08-31)**: 원래 단일 `events.ndjson`에 모든 세션이
> append하고 `merge=union`이 충돌을 흡수한다고 믿었다. 그러나 union은 **로컬 git에서만**
> 작동하고 **GitHub의 mergeability 판정은 저장소 merge driver를 적용하지 않는다** — 그래서
> main에 어떤 PR이 착지하든 이 파일을 만진 열린 PR은 전부 충돌(dirty)이 됐다(PR #931이
> CI green 4회를 확보하고도 머지가 반복 지연된 실측 사고 —
> `docs/reviews/pr931_merge_block_root_cause_2026-08-31.md`). 대책은 tasks/의
> 태스크당-1파일과 동형: **세션당 1샤드**로 나눠 두 브랜치가 같은 파일을 동시에 append하는
> 상황 자체를 없앤다. 소비자는 반드시 `store.event_paths()`(레거시+샤드 합집합)로 읽는다 —
> 한쪽만 읽으면 무손실이 아니다. 계약 동결 = `tests/harness/test_event_ledger_sharding.py`.

- **태스크 상태는 CLI로만 변경한다**: `python3 scripts/harness/backlog.py <cmd>`.
  직접 편집하면 PostToolUse 훅이 무결성을 검증한다 (깨지면 차단).
- ROADMAP.md·MEMORY.md는 **서사(왜)** 담당으로 존속 — 수치·순서·다음 작업의 정본은 backlog다.
- 병렬 세션: 태스크당 1파일 + `session` claim 필드 + **이벤트 세션 샤드**로
  "1 세션 = 1 도메인 = 1 브랜치 = 1 태스크"가 파일 수준에서 강제된다
  (`docs/standards/parallel_sessions.md` 연계).
- **태스크 `paths` 필드 (v1.1)**: 태스크가 만질 파일 범위를 glob으로 선언한다
  (예: `src/backend/api/**`). `start` 프리플라이트·check-edit 훅이 이 선언으로
  **교집합 작업**을 사전 감지한다. 디렉토리는 `src/backend/` 또는
  `src/backend/**` 형태로 — 와일드카드 없는 리터럴은 단일 파일로 해석된다.
  기존 태스크의 paths 부재는 위반이 아니나, 신규 태스크는 `add --path` 선언을 관례화한다.
- **태스크 `eos_priority` 필드 (v1.2 · HARN-55)**: EOS 12월 검증 등급 `P0|P1|P2|P3`.
  계획서 100의 Rule 1·3·4를 **CLI 거부**로 집행하는 축이며, 산문 규칙이 집행 지점 0으로
  떠 있던 상태(전환계획 준수 감사 A1 "높음")를 해소한다.
  - **Rule 1·3 (등급 필수)** — `add --eos-priority` 미지정은 **exit 1**. 거부 메시지가
    판정 질문("이 기능이 없으면 12월 31일 EOS 검증의 폐쇄루프가 깨지는가?")을 출력한다.
    등급을 고르려면 12월 검증 관여 여부를 판정할 수밖에 없다 — 그것이 이 게이트의 목적이다.
  - **Rule 4 (One In → One Out)** — 비종결 P0가 `policy.eos_p0_budget`(기본 50 ·
    계획서 §7 "Release P0 ≤ 50")에 닿으면 P0 신규 등재는 `--swap-out <기존 P0 id>`를
    요구하고, 그 태스크를 **P1로 강등**한다. 예산 여유 구간의 `--swap-out`은 거부한다
    (P0를 오히려 줄이므로).
  - **백필 경로** — 기존 태스크는 `amend <id> --eos-priority <등급> --reason "..."`.
    대장 손편집은 금지다. amend는 예산을 강제하지 **않는다**: amend는 *분류*이고, 분류
    결과가 예산을 넘는다면 그것은 우회가 아니라 보고해야 할 사실이다(여기서 막으면
    사람이 등급을 낮춰 적어 예산을 맞추게 된다 — 측정의 자기기만).
  - **그랜드파더와 그 만료** — 도입 시점의 기존 태스크는 `null`이 허용된다. 만료는 날짜가
    아니라 **기계**다: 게이트 `G-eos-verification-relevance-triage`가 cleared/waived가 되는
    순간(= 관여도 분류의 근거가 생긴 순간) 비종결 미지정이 `validate` 위반이 된다.
    종결(done·cancelled) 태스크는 면제 — 끝난 일에 등급을 소급하는 것은 분류가 아니라
    장부 청소다. 계약 동결 = `tests/harness/test_eos_priority_enforcement.py`(16건).

## 3. 순차 조율 규칙 (selector)

착수 가능 = `todo` ∧ 의존성 전부 done ∧ 게이트 전부 cleared/waived
∧ owner=claude ∧ 트랙 entry_gate 통과 ∧ 미claim.
정렬 = (stage 순서, priority, −해금 후속 수, id) — **결정적**.

- **owner=claude는 *자동 착수 후보*의 조건**이다(next/status/brief). 사람-소유
  태스크(owner=kiki/partner)는 자동 후보에 절대 오르지 않지만, **소유자 본인이
  `start <id> --as <owner>` / `done <id> --as <owner> --artifact ...`로 직접
  기입할 수 있다**(HARN-06 — 2026-07-16 S1-14 사례에서 사람 태스크의 CLI 완료
  경로 부재가 실측된 설계 공백의 해소). `--as`가 태스크 owner와 불일치하면 거부,
  deps·게이트·claim·증적 검사는 사람 기입에도 동일 적용(우회 아님), 이벤트에
  `as_owner`가 남아 claude 기입과 구분된다.

- **E축 하드락**: subject-expansion 트랙은 `G-s5-subject-expansion` 통과 전
  알고리즘 수준에서 후보 제외 — "수학 완성 전 어떤 과목도 착수하지 않는다"
  (subject_expansion_e_axis_v1.md 불변 전제)가 코드로 강제된다.
- 후보 0 + 사람 게이트만 잔존 → `/drive`는 정지하고 Kiki 행동 목록을 보고한다.

## 3b. 원격 claim — 병렬 세션 실시간 조율 (v1.1)

로컬 `session` claim은 각 세션 worktree의 backlog 사본에만 기록되어 merge 전까지
서로 보이지 않는다(TOCTOU 레이스). **원격 claim**이 이 구멍을 막는다:

- `start`가 origin의 **`harness-claims` 브랜치**에 `claims/<task-id>.json`을 추가하는
  커밋을 push한다. push는 `--force-with-lease=refs/heads/harness-claims:<base>`의
  **CAS 원자성** — 그 사이 남이 브랜치를 갱신했으면 서버가 거부하므로, 두 세션이 동시에
  같은 태스크를 start해도 정확히 한쪽만 성공한다.
- **네임스페이스가 `refs/claims/*`에서 바뀐 이유(HARN-09)**: 이 실행 환경의 git 프록시가
  그 네임스페이스 push를 403 거부해 CAS가 *한 번도 성공한 적이 없었다*. 2026-07-28 실측으로
  `refs/heads/*` 커밋 push는 성공함을 확인하고 이전했다. **태스크당 브랜치가 아니라 단일
  브랜치**인 것은 같은 프록시가 ref *삭제*도 거부하기 때문이다 — 태스크당 브랜치면 해제가
  불가능해 브랜치가 영구 누적된다. 단일 브랜치면 해제가 "파일을 지우는 커밋"이라 삭제가 불요다.
  이 삭제-403의 변별 실측(create-push exit 0 vs delete-push HTTP 403)과 Kiki 위임 명령 블록은
  `parallel_sessions.md` §4 정리 「컨테이너 세션은 원격 브랜치를 삭제할 수 없다」 참조(HARN-16).
- **lease 거부 ≠ 태스크 점유**: lease 거부는 "그 사이 누군가 브랜치를 갱신했다"(대개 다른
  태스크의 claim)는 뜻이라 재fetch 후 재시도한다. 태스크 점유는 오직 브랜치 트리를 읽어
  판정한다 — 이 분리가 "남의 claim"과 "동시 갱신"을 혼동하지 않게 한다.
- claim 파일에 메타(JSON: branch·UTC ts)가 담긴다 — conflict 시 상대 세션이 즉시 식별된다.
  메타가 파손돼 홀더를 특정할 수 없어도 **conflict로 친다**(조용한 탈취 금지, 복구는 `--force`).
- 트리는 `git mktree`로 만든다 — 인덱스를 쓰지 않으므로 개발자의 스테이징·작업 트리를
  건드릴 수 없다(구조적 차단).
- **conflict만 차단**(신호가 확정적) — offline/권한 오류는 경고 + 이벤트 로그 후
  로컬 claim으로 진행한다(fail-open — 훅·CLI가 개발을 볼모로 잡지 않는다).
- `done`/`block`이 claim을 해제한다. 세션이 죽어 claim이 남으면 `claims reap`이
  **4중 기준**(TTL 초과 · 태스크 이미 done/cancelled · 태스크 미존재 ·
  **홀더 브랜치가 origin에 부재**)으로 청소한다 (기본 dry-run, 실삭제는 `--apply`).
  `reap`은 **(목록, 조회상태, 경고목록)** 을 돌려준다 — 조회 실패를 "stale 없음"으로
  위장하면 CI 교차검증이 공전한다(HARN-09 실측 사례).
- **홀더 브랜치 부재(`branch_gone`·HARN-26)**: 컨테이너 세션은 원격 브랜치를 스스로
  지우지 못하므로(HARN-16), 홀더 브랜치가 없다는 것은 그 세션의 작업이 원격에 도달한
  적조차 없다는 뜻이다 — TTL 72시간을 기다릴 이유가 없는 확정 신호다.
  단 `start`와 첫 push 사이에는 브랜치가 없는 **정상 구간**이 있으므로
  `policy.claim_branch_grace_hours`(기본 24h) 이내는 `branch_gone_recent`로 분류해
  삭제하지 않고 경고만 낸다(`task_missing_recent`와 같은 규칙).
  - grace를 TTL과 같게 두면 안 된다 — 실측(events.ndjson start→done/block 199건)에서
    **72h 초과 세션이 0건**이라, grace=72h면 `branch_gone`이 잡는 집합이 `ttl`이 잡는
    집합의 부분집합이 되어 탐지력을 1건도 추가하지 못한다. 24h 오탐 상한은 2.0%.
  - 유예가 이론이 아님을 보여준 실측: 2026-08-11 03:00Z에 "홀더 브랜치 없음"이던
    claim 3건 중 2건이 40분 뒤 정상 push됐다(살아 있는 세션이었다). 유예 없이 집행했다면
    CAS가 막아둔 중복 착수를 직접 열어줬을 것이다.
  - 원격 브랜치 조회가 실패하면 이 기준만 **보류**한다(빈 집합을 "브랜치 전멸"로 읽으면
    대장을 통째로 지운다). 보류 사실은 경고 목록에 실린다 — 침묵하지 않는다.
- **집행 지점(HARN-27)**: `.github/workflows/harness-audit.yml`이 main push·야간·수동
  트리거에서 `claims reap --auto`를 돌린다. `--auto`는 삭제를 켜되 사유를
  `remote_claims.AUTO_REAP_REASONS`(= `task_done`·`branch_gone`)로 좁힌다.
  - **왜 별도 워크플로인가**: `on:`에 `pull_request`가 아예 없어 "PR에서는 지우지 않는다"가
    조건문이 아니라 **구조적 불가능**이 된다. ci.yml의 `harness-integrity`에는 `if:` 가드가
    없어 PR에서도 돌고, 거기에 `contents: write`를 붙이면 PR 검증 경로가 쓰기 권한을 갖는다.
  - **왜 안전 집합이 코드에 있는가**: 사유를 워크플로 인자(`--reasons ttl,...`)로 두면
    YAML을 고쳐 범위를 넓힐 수 있고 파이썬 테스트가 그것을 동결하지 못한다.
    `ttl`(살아 있는 장기 세션일 수 있다)·`task_missing`(CI 러너는 main만 보므로 다른
    브랜치 등재 태스크를 구조적으로 "없음"으로 본다 — HARN-15 맹점)은 제외한다.
  - ci.yml의 dry-run 스텝은 **유지**한다 — PR마다 도는 관측 채널이고, 자동 집행에서
    제외된 사유(사람 판단 필요분)를 드러내는 유일한 화면이다.
- `next`/`brief`(SessionStart)가 원격 claim을 조회해 다른 세션의 작업을
  후보 제외·브리핑 노출한다.

### 3b-1. 읽기측 교차 세션 탐지 — CAS가 막힌 환경의 폴백 (HARN-07)

**사고(2026-07-27)**: 이 실행 환경의 git 프록시는 `refs/claims/*` push를 **HTTP 403**으로
거부했다. 즉 CAS claim은 "가끔 실패"가 아니라 *한 번도 성공한 적이 없었고*, fail-open이
모든 `start`를 통과시켜 중복 방지가 상시 무력이었다 — 두 세션이 OPS-07을 병렬 구현해
한쪽(테스트 735줄 포함)을 폐기했다. `events.ndjson`에 `claim_remote_unavailable`
(status=error) 45건이 그 흔적이다.

**2회차(2026-07-27, OPS-12)**: 같은 원인으로 또 났다. 읽기측 폴백이 이미 있었지만 그 폴백은
*push된* 브랜치만 보므로, 내 `start`(07:03:21)와 상대 `start`(07:06:21) 사이 3분 창을 막지
못했다 — **양쪽 다 `error+readscan_ok`** 를 받고 진행했다. 설계된 한계대로 동작했으나 한계
자체가 사고를 허용한 것이다. **규칙만으로 2회차를 못 막았다**는 것이 HARN-09(네임스페이스
이전으로 CAS 복구)의 등재 근거다 — 반복 실수는 규칙이 아니라 코드로 상환한다.

**HARN-09 이후**: CAS가 1선이고 이 읽기측 경로는 CAS가 offline/error일 때만 도는 **2선**이다.
아래 설명은 그 2선 동작이다.

**대응**: 쓰기(CAS)는 못 고치지만 **읽기는 된다**(`git fetch` 전체 브랜치 ~5초 실측).
`start`는 CAS가 `offline`/`error`를 반환한 경우에만 읽기측 탐지로 폴백한다:

1. `git fetch origin '+refs/heads/*:refs/remotes/origin/*'` (타임아웃 90초)
2. 원격 브랜치들의 `backlog/tasks/<id>.yaml`을 읽어 `status: in_progress` +
   `session:`이 **내 세션과 다른** 것을 찾는다 (최근 커밋순 최대 300개 브랜치)
3. 발견 시 **착수 거부** — 어느 브랜치·어느 세션인지 명시하고, 우회 경로
   (`--no-remote` 또는 상대 태스크 done/block)를 함께 안내한다

**이것은 CAS의 대체가 아니라 *부분* 방어다** (과장 금지 — 코드·CLI 메시지에도 매번 명시):

- 상대 세션이 **브랜치를 push한 뒤에만** 보인다. push 전 로컬에서 작업 중인 세션은
  이 방법으로 **절대** 잡히지 않는다.
- **원자성이 없다** — 두 세션이 동시에 스캔하면 둘 다 "충돌 없음"을 볼 수 있다.

그러므로 **CAS 경로는 제거하지 않는다** — 프록시 정책이 다른 환경(로컬 개발·다른 러너)
에서는 CAS가 작동하며 원자성은 그쪽이 우월하다. 읽기측은 CAS 실패 시에만 돈다
(CAS 성공 시 fetch 비용 0 — `test_CAS_성공이면_읽기측_탐지를_호출하지_않는다`가 동결).

**폴백 자체가 실패하면**(fetch 불가 등) fail-open하되 **"중복 착수 보호가 전혀 없습니다"**를
명시적으로 경고하고 `claim_readside_unavailable` 이벤트를 남긴다 — 침묵 실패 금지.
탐지 성립 시에는 `claim_readside_conflict` 이벤트가 남아 측정 가능하다.

### 3b-2. stale 홀더 처리 — 과탐이 만들던 영구 차단의 해소 (HARN-08)

**문제**: 머지·폐기된 브랜치에 남은 `in_progress`를 읽기측이 활성 claim으로 오인해
그 태스크를 **영구 차단**했다. 우회는 보호를 통째로 끄는 `--no-remote`뿐이었다.
2026-07-27 실측에서 과탐 5건이 관측됐다(ARCH-13·MOB-01·OPS-07·PED-01·S2-02).

> **조상 검사는 쓸 수 없다** — 이 저장소는 SQUASH 머지라 머지된 브랜치도 트렁크의
> 조상이 아니다. 5건 전부 `git merge-base --is-ancestor`가 False로 실측됐다.

판별은 다음 2규칙 + 태스크 단위 우회 1개다:

| 규칙 | 내용 | 근거 |
|---|---|---|
| **A. 트렁크 권위** | 트렁크(`origin/HEAD`)의 사본이 `done`/`cancelled`면 **홀더 전부 무시** | 작업이 이미 착륙했다 — 다른 브랜치의 `in_progress`는 역사적 잔재. `done`/`cancelled`는 종결 상태라 CLI로 되돌릴 수 없다 |
| **B. 트렁크는 세션이 아니다** | 트렁크 ref 자신은 홀더 후보에서 제외 | claim의 의미는 "어떤 *세션*이 그 브랜치에서 작업 중"이다. 트렁크의 `in_progress`는 활성 claim이 아니라 **대장 위생 실패**(done 미기입 머지 — OPS-07이 그 사례) |
| **C. 세분 우회** | `start <id> --ignore-remote-claim` — **그 태스크의 읽기측 판정만** 무시 | `--no-remote`(보호 전체 포기)와 구분. 무엇을 포기하는지 경고 출력 + `claim_readside_ignored` 이벤트. **CAS conflict는 무시되지 않는다**(확정 신호) |

- **기본 브랜치명은 하드코딩하지 않고, 원격 권위를 먼저 묻는다** —
  `git ls-remote --symref origin HEAD`(실측 0.3초) → 실패 시 로컬 캐시
  `git symbolic-ref refs/remotes/origin/HEAD` → 그래도 실패면 `main` 폴백.
  **순서가 안전장치다**: 로컬 `origin/HEAD`는 clone 시점 스냅샷이라 stale일 수 있고,
  2026-07-27 종단 실측에서 실제로 **세션 브랜치를 가리키는 클론**이 나왔다 — 그 값을
  1순위로 믿었다면 규칙 A가 남의 세션 브랜치를 '트렁크 권위'로 삼아 보호를 조용히
  껐을 것이다(미탐). 폴백까지 틀리면 규칙 A 신호가 '없음'이 되어 과탐 상태로 되돌아갈
  뿐이며, 해소 경로는 `ScanResult.trunk_source`·`start` stderr에 매번 표기된다.
- **나이(최종 커밋 경과일) 휴리스틱은 의도적으로 넣지 않았다** — 실측 5건이 A+B로 전부
  해소되며, 나이 컷오프는 느리게 진행하는 실 세션을 오탐 해제할 위험(거짓 음성)만 더한다.
- **걸러낸 홀더는 버리지 않는다** — `ScanResult.skipped`(사유별)에 남고 `start`가 stderr로
  요약하며 `claim_readside_stale_skipped` 이벤트로 적재된다. "보호가 안 걸렸다"와
  "보호를 스스로 껐다"가 구분돼야 하기 때문이다.
- 실환경 검증(2026-07-27): 진짜 origin 대상으로 과탐 5건 → 0건(규칙 A 4건·규칙 B 1건).
  같은 실행에서 살아 있는 claim(HARN-08 본인 브랜치)은 **여전히 홀더로 탐지**되고
  `start`가 exit 1로 거부한다 — 보호가 과잉 무력화되지 않았음을 같은 회계로 확인했다.
- 변별력 실측: 규칙 A 제거·규칙 A 과잉적용·규칙 B 제거·트렁크 해소 순서 되돌림·규칙 C 경고
  삭제 5종 돌연변이가 각각 5·5·3·2·1건의 테스트 FAIL로 검출됨
  (`tests/harness/test_remote_claims.py`·`test_cli.py`).

### 3b-3. 미머지 브랜치 4분류 — 고립과 지연의 분리 (HARN-47)

브리핑의 미머지 브랜치 목록은 **행동이 다른 네 부류**를 구분한다. 한 덩어리로 부르면
경고가 습관화되고, 습관화된 경고는 보호가 아니다(CLAUDE.md 「상시 실패하는 fail-open
보호를 '보호 있음'으로 신뢰 금지」).

| 분류 | 판정 근거 | 필요한 행동 |
|---|---|---|
| `isolated` | ahead>0 · 포팅 근거 없음 · **`refs/pull/*/head`에 tip 없음** | 회수(PR 생성) 또는 삭제. **브리핑 줄이 유일한 존재 증거다** |
| `pr_filed` | tip이 `refs/pull/<N>/head`와 일치 | 없음 — 처분은 그 PR에서. 브리핑은 번호만 건넨다 |
| `ported` | trunk 커밋이 브랜치를 인용하며 코드를 옮김 | 원본 정리만 |
| `active` | 원격 claim 맵에 존재 | 없음 — 진행 중인 정상 작업 |

**왜 이 분리가 생겼나** (2026-08-31 실측): 브리핑이 18건을 전부 "Kiki 결정 필요"로
부르고 있었는데, 그중 11건은 **이미 PR이 열려 있고 처분 라벨까지 붙어 있었다**. 경고의
61%가 이미 결정된 것을 다시 결정하라고 요구했고, 진짜 고립 7건이 그 소음에 24일간
묻혀 있었다.

**PR 판정은 오프라인 git만 쓴다** — `git ls-remote origin "refs/pull/*/head"`는 토큰·API
권한 없이 읽힌다. 판정을 외부 관측 인프라에 의존시키지 않는다는 이중 회계 원칙과 같은
방향이다. tip sha는 이미 도는 `for-each-ref`에 얹어 받으므로 브랜치당 추가 git 호출은 0.

**`active` 판정에는 원격 claim 맵이 필요하다.** 두 진입점(`cmd_brief`·`cmd_branches`)이
모두 `active_branches=frozenset(remote_claimed.values())`를 넘겨야 이 분류가 실제로 난다.
CI 진입점이 이걸 빠뜨리면 **지금 누가 작업 중인 브랜치가 "🔴 회수 또는 삭제 필요"로
경고된다** — 삭제를 유도하는 오경보이자, 이 표가 4분류라고 말하면서 CI 경로는 3분류만
낼 수 있는 상태다. 두 진입점의 배선을 각각 테스트가 붙든다
(`test_cli.py::TestStaleBranchClassificationWiring`). claim 조회 자체가 실패하면 그 사실을
출력에 남긴다 — `active`가 조용히 `isolated`로 오분류되는 것을 막기 위함이다.

**조회 실패는 "PR 없음"이 아니다.** 실패하면 그 브랜치는 `unresolved`(고립 여부 미판정)로
남고 `pr_lookup_ok=False`가 서며, `pr_lookup_error`에 **예외 타입명을 포함한 사유**가
실린다(무타입 경고는 타임아웃·git 미설치·권한 오류를 같은 글자로 보이게 만든다). 실패를 고립으로 읽으면 인프라가 죽은 순간 열린 PR 전부가
"삭제 필요"로 승격된다 — 삭제를 유도하는 오경보다.

**열림/닫힘은 판정하지 않는다.** `refs/pull/<N>/merge`가 열린 PR에만 생긴다는 통설을
실측에서 폐기했다(열린 PR 14건 중 merge ref 보유 8건, 이미 머지된 PR도 head만 잔존).
성공/실패에 같은 값을 내는 검사는 검증이 아니라 위장이므로, 답할 수 있는 질문("PR로
노출된 적이 있는가")만 답하고 나머지는 PR 번호로 사람에게 넘긴다.

**집행 지점**(정본화와 별항): SessionStart 훅 + **CI `harness-integrity` 잡**
(`backlog.py branches`). 이 스캔은 HARN-13 이후 줄곧 SessionStart 전용이었다 — 대화형
세션 밖에서는 실행 0회였다. CI 배선에는 `fetch-depth: 0`이 필수다(기본 shallow면 가드에
걸려 매 실행 "판정 보류"가 되어 초록인 채 상시 무력이 된다). 배선 실재성은
`tests/infra/test_stale_branch_scan_ci_wiring.py`가 기계로 동결한다.

## 3b-1. 중복 방어의 두 축 — 같은 *이름* vs 같은 *문제* (HARN-51)

번호 충돌 가드(HARN-10/15)가 막는 것은 **같은 식별자**를 두 세션이 배정하는 것이다.
2026-08-31~09-01 동종 6건 중 **5건이 이 축**이었고 CLI가 전건 실거부했다.

나머지 1건은 달랐다. `HARN-45`와 `HARN-48`이 같은 뿌리(차단이 교차 세션 보호를 지운다)를
**서로 다른 이름으로** 각자 구현했고, ID가 다르므로 번호 가드·claim 대장·원격 파일 스캔
**어디에도 걸리지 않았다**. 발견 경로는 기계가 아니라 상대 세션이 자기 YAML에 중복을
스스로 적어 둔 것이었다 — 그것이 없었으면 한쪽 구현이 통째로 폐기됐을 것이다(실제로 폐기됐다).

- **신호** = 공유어를 문서빈도의 역수(IDF)로 가중한 점수. 결정적이었던 것은 `차단`·`block`
  같은 일반어가 아니라 `cmd_block`·`_release_remote_claim`처럼 **저장소 안에서 드문 식별자**다.
  **IDF는 백로그 자신에서 산출**하므로 임베딩·외부 모델·네트워크가 없다.
- **대조 범위** = 로컬 in-flight **+ 원격 브랜치 사본**. 로컬만 보면 이 사고를 재현조차 못 한다
  (`HARN-48`은 별도 브랜치에 있었다). 원격 읽기는 `fetch=False` 계약을 승계해 **네트워크 0**이고,
  로컬에 이미 있는 ID는 읽기 *앞*에서 걸러 `git cat-file --batch` 1회로 끝낸다.
- **차단하지 않는다** — 유사도에 정답은 없다. 후보가 없으면 아무것도 출력하지 않고, 원격
  조회가 실패하면 침묵 대신 **판정 불가**라고 말한다(실패를 '중복 없음'과 같은 색으로 두지 않는다).
- **실측(2026-09-01 · 485건)**: 표적 검출 1위(0.1365 vs 잡음 0.0733) · 평균 후보 0.86건 ·
  최대 3건 · 완전 침묵 53%. 한계까지 포함한 정본은 `scripts/harness/similar.py` 모듈 docstring.

## 3c. 조율 정책 — 단계적 강제 (warn → block)

`backlog/policy.yaml`의 rule 3종 (전부 warn으로 시작 — "측정 없는 도입 없음"):

| rule | 감지 대상 | 감지 지점 |
|---|---|---|
| `path_overlap` | 태스크 간 파일 범위 교집합 | `start` 프리플라이트 · check-edit 훅 |
| `scope_drift` | 내 claim 태스크의 선언 paths 밖 편집 | check-edit 훅 |
| `adhoc_edit` | claim 없이 코드 도메인(src/·infra/) 편집 | check-edit 훅 |

- warn = stderr 1줄 + `events.ndjson`에 `policy_warn` 적재 (측정) / block = 거부(exit 1·2).
- **승격 기준**: 2주 또는 30세션 관찰 후 (a) 실제 충돌 예방 사례 ≥1 또는 정탐률 ≥50%
  (b) 오탐으로 인한 개발 중단 0건 → 해당 rule만 block 승격.
  승격 = policy.yaml 1줄 수정 + MEMORY.md 결정로그 + `policy_promote` 이벤트.
- 측정 요약: `backlog.py policy report --days 14`.
- 겹침 판정은 보수적 2단 근사(실파일 교집합 + 정적 프리픽스 포함 — `pathscope.py`).
  과탐이 미탐보다 안전하다는 원칙. 원격 claim conflict는 단계적 도입의 예외로
  **즉시 차단**(신호가 확정적이므로).

## 3d. 의존 선언의 두 종류 — 하드 부착 vs 소프트 분류 (HARN-52 · HARN-53)

`selector.py`는 **`depends_on`만** 본다. notes에 "선행: X 착지 후"라고 적어도 스케줄러는
모르므로, 등재자가 "막아 뒀다"고 믿는 동안 그 태스크는 다른 세션에 착수 후보로 노출된다.
그래서 `audit-deps`(CI `harness-integrity`)가 **notes의 선행 어구 ↔ `depends_on`** 을 대조한다.

문제는 어구가 잡혔다고 언제나 하드 의존인 것은 아니라는 점이다. HARN-53이 레거시 6건을
전수 분류한 결과 **하드 부착이 옳은 것은 0건**이었고, 다섯 가지 서로 다른 이유로 전부 하드가
아니었다. 그때 남는 선택지는 셋뿐이다 — ⓐ notes를 고쳐 어구를 피한다(자연어를 게이트에
맞추는 꼬리-개-흔들기) ⓑ 틀린 하드 의존을 붙인다(영구 오차단) ⓒ **왜 하드가 아닌지를
코드로 분류한다**. 저장소는 ⓒ를 택했다.

### 어느 쪽인지 판정하는 법

| 상황 | 처리 | 수단 |
|---|---|---|
| 진짜로 X가 끝나야 시작할 수 있다 | **하드 부착** | `backlog.py amend <id> --depends <full-id> --reason '...'` |
| 방향이 반대다(내가 X의 선행) | 소프트 `REVERSED` + **상대 쪽에 부착** | `SOFT_DECLARED` + `amend X --depends <나>` |
| A 또는 B 택일 | 소프트 `DISJUNCTIVE` | `depends_on`은 AND라 표현 불가 — 하나가 done이 될 때 남은 쪽을 부착 |
| 후행 스테이지 의존(E축 등) | 소프트 `STAGE_BLOCKED` | `validate`가 로드맵 순서 위반으로 거부한다 · 제외는 `status=blocked`가 담당 |
| 이미 끝난 과거 사실 서술 | 소프트 `HISTORICAL` | 앞으로의 순서 제약이 아니다 |
| 창(60자)이 잡은 ID가 선행이 아님 | 소프트 `MISREAD_REF` | 진짜 선행이 따로 있으면 그쪽을 부착 |

### 소프트 분류가 옵트아웃이 되지 않는 이유

유예(`LEGACY_EXEMPT`)와 다르다 — 유예는 "아직 안 고쳤다"라서 **만료**가 필요하고, 소프트는
"고칠 것이 없다"라는 **판정**이라 만료가 없다. 만료가 없으니 느슨해질 여지를
`find_soft_declaration_violations`가 대신 막는다:

1. 사유 **코드**는 고정 집합에서만 — 자유 서술로 "소프트니까"가 불가능하다
2. 근거 문장이 비었거나 40자 미만이면 위반 — 코드만 찍고 넘어갈 수 없다
3. 같은 쌍이 `depends_on`에도 있으면 위반 — 하드로 걸어 놓고 소프트라 적는 모순
4. 대상·참조가 백로그에 없으면 위반 — 허구가 된 분류
5. 같은 쌍이 유예에도 있으면 위반 — "고칠 것 없음"과 "아직 안 고침"은 동시에 참일 수 없다
6. **인용구**(`quotes`)가 없거나 notes에 없으면 위반 — 아래 "발생 위치 결속"
7. `DISJUNCTIVE`·`STAGE_BLOCKED`인데 태스크가 착수 후보에서 빠지지 않으면 위반 — 아래 "제외 강제"

### 발생 위치 결속 — 쌍이 아니라 *그 문장*을 분류한다

쌍(태스크, 참조)만으로 억제하면 **그 두 태스크 사이의 앞으로 모든 문장**이 함께 묻힌다. notes는
append 전용이라 나중에 진짜 선행 선언("X 착지 후 착수")이 추가돼도 스캐너와 `amend` 가드가
똑같이 green을 낸다. 그래서 분류마다 **어느 문장을 분류했는지**를 인용구로 적고, 그 인용구
구간 안에 있는 참조 토큰만 억제한다 — 분류되지 않은 새 문장은 정상적으로 잡힌다.

결속 기준은 *참조 토큰의 위치*다(어구 위치나 창 포함이 아니라). 창은 어구 좌우 60자라 옆
문장을 삼키고, 어구 기준으로 묶으면 한 어구가 잡은 *다른* 참조까지 함께 억제되기 때문이다 —
둘 다 실측으로 확인하고 좁혔다.

### 제외 강제 — 분류만 하고 막지 않으면 경고만 없앤 것이다

`DISJUNCTIVE`·`STAGE_BLOCKED`는 "*그 참조에 대해서는* `depends_on`으로 순서를 강제할 수 없다"는
뜻이다. 그러면 스케줄러 제외를 **다른 수단**이 담당해야 한다. 계약이 요구하는 것은 **결과**
(착수 후보에서 빠질 것)이지 특정 수단이 아니다 — `status=blocked`도, *다른* 참조를 하드로
부착하는 것도 유효하다. 수단을 하나로 못박으면 옳은 해법을 위반으로 만든다.

실측 배경 두 가지: `EOS-50`이 택일 선행 둘 다 미완인데 `todo`라서 착수 후보 111건에 들어
있었고(분류가 유일한 경고를 없앤 상태), 그 뒤 병렬 세션이 택일의 한쪽인 `EOS-49`를
`depends_on`에 부착해 막았다(PR #994) — 계약이 `blocked`만 인정했다면 그 옳은 해법이 위반이
됐을 것이다.

그리고 **보이지 않게 쌓이지 않는다**: `audit-deps --all`이 소프트 전건을 코드·근거와 함께
출력하고, green 줄에도 건수가 찍힌다.

### 되먹임 주의 — 정정 사유가 새 위반을 만든다

`--reason`은 notes에 append되고 notes는 이 스캐너의 입력이다. 그래서 *"…'선행'이라 선언한
방향을 부착한다"* 같은 **사유 인용**이 그 문장 안의 태스크 ID를 새 선언으로 만든다(HARN-53
실측 2건). notes는 append 전용이라 기록된 뒤에는 되돌릴 CLI 경로가 없으므로 **쓰기 전에**
거부한다 — 사유에서 선행 어구와 태스크 ID가 한 문장에 오지 않게 쓴다.

가드가 붙은 곳은 `amend`와 `block` 둘이다. `done`·`cancel`도 사유를 notes에 append하지만
그 명령들은 태스크를 스캐너가 건너뛰는 상태(`done`·`cancelled`)로 바꾸므로 위반을 만들 수
없다. 판정 대상은 **이 명령이 새로 만든** 위반뿐이다 — 기존 위반까지 막으면 위반 하나가
대장에 있는 동안 그 태스크의 모든 정정이 봉쇄되어, 게이트가 자기 정정 경로를 막는다.

---

## 4. 일상 워크플로우

```
세션 시작   → (자동) SessionStart 브리핑: 현재 스테이지·next 3·게이트 리마인드
주도 진행   → /drive              # 순차 루프 (기본 3태스크, 사람 게이트에서 정지)
단건 작업   → /implement <id>     # start → 구현 → PR 생성 → done --artifact
새 계획     → /plan <주제>        # 산출물 = backlog add 태스크 등록
사람 게이트 → /gates              # clear는 evidence 필수
상세 상태   → /status
세션 종료   → (자동) Stop 훅: claim 태스크 미갱신이면 차단
```

## 4b. 작업 보드 — 한 화면 가시화 (`board.py`)

`status`·`brief`가 *터미널 요약*(next 3건 + 게이트)이라면, 보드는 **전수 가시화**다.
"무엇을 했고 · 무엇을 하는 중이며 · 무엇이 예정인가"를 한 화면에서 본다.

```bash
python3 scripts/harness/board.py            # work/board.html 생성 (+ 터미널 요약 동시 출력)
python3 scripts/harness/board.py --text     # HTML 없이 터미널 요약만
python3 scripts/harness/board.py --json     # 페이로드 JSON (다른 도구가 소비)
python3 scripts/harness/board.py --no-remote   # 미머지 완료 스캔 생략 (배너로 판정 불가 표기)
python3 scripts/harness/board.py --out docs/reviews/board_2026-08-31.html   # 스냅샷 보관용
```

산출물은 **자기완결 HTML 1파일**이다 — 외부 CDN·폰트·서버 요청이 없어 오프라인에서도
열리고, 그대로 첨부·공유할 수 있다. 5열 칸반:

| 열 | 무엇인가 | 판정 근거 |
|---|---|---|
| 진행 중 | 세션이 claim해 작업 중 (`in_progress`·`review`) | `status` + `session` |
| 다음 착수 | 의존성·게이트 전부 해소 — 바로 시작 가능 | `selector.classify_todo` = None |
| 대기 | 등재됐으나 선행 조건 미해소 (사유 라벨 표시) | `selector.Exclusion.reason` |
| 차단 | `blocked` — 노트의 최신 `[차단 …]` 문단을 카드에 발췌 | `status` + `notes` |
| 완료 | 증적 확인된 종결 — 최근 갱신 우선 | `status == done` |

여기에 스테이지 진행률·사람 게이트·`validate` 경고가 같은 화면에 얹히고, 검색어·스테이지·
레이어·트랙·과목으로 즉시 필터된다.

**게이트 카드는 클릭하면 펼쳐진다**(네이티브 `details/summary` — 키보드 접근 가능). 접힌
상태는 id·제목·경과일(리마인드 초과면 붉은 테두리)만, 펼치면 넷을 더 보여준다:
- **메타** — 종류·담당·요청일·리마인드 임계·상태
- **이 게이트가 막고 있는 것** — `requires_gates`로 건 태스크 목록에 더해, **트랙
  `entry_gate`로 잠긴 경우 그 트랙의 미완 건수**를 함께 센다. 트랙 잠금은 태스크 쪽에
  아무 표시도 남기지 않으므로, 이걸 세지 않으면 E축 하드락이 "아무것도 안 막는 게이트"로
  보인다(실측: `G-s5-subject-expansion`이 미완 15건을 잠근다). 단 이 목록은 **의존 관계**
  이지 "현재 차단"이 아니다 — 해소된 게이트를 아직 `requires_gates`에 달고 있는 태스크가
  실재하고(`G-eos-g0-verification-design-freeze` ↔ `EOS-56`) `selector.unmet_gates`는 그
  태스크를 착수 가능으로 본다. 화면 문구는 `blocks_now`(게이트가 pending인가)로 갈린다:
  대기면 "막고 있는 것", 해소면 "전제로 걸었던 것(지금은 차단하지 않는다)".
- **상세 노트** — 발췌가 아니라 **원문 그대로**(줄바꿈 보존·스크롤). 게이트 노트에는 실행
  런북이 들어 있다(`G-operator-seat-first-grant` 2,736자) — 요약하면 그게 사라진다
- **해소 명령** — `backlog.py gates clear <id> --as <담당자> --evidence "<근거>"` 그대로 복사 가능
  (보드가 게이트의 담당자를 플래그에 실어 준다 — 복사한 사람이 곧 기록되는 주체다).
  **사람이 본인 게이트를 직접 닫을 때는 `--as kiki`를 붙인다**(HARN-60) — 붙이면 대장에
  `cleared_by: kiki`가, 생략하면 `cleared_by: claude`(에이전트 중계)가 남는다. 생략을
  거부하지 않는 이유: 에이전트 중계는 정당한 운영 형태이고(Kiki가 자기 머신에서 실행 →
  출력 전달 → 세션이 기입), 막으면 CLI를 우회한 YAML 손편집으로 밀려나 아무 기록도 안
  남는다. 목표는 금지가 아니라 **사후 증명 가능성**이다

해소된 게이트(cleared·waived)는 기본 접힌 별도 그룹에서 근거(evidence)와 함께 열람한다 —
기본 화면은 행동이 필요한 대기 게이트만 보여 준다.

**계약 3건** (`tests/harness/test_board.py`가 동결):
1. **판정 무복제** — 열 배치는 `selector.classify_todo`, 진행률은 `report.stage_progress`를
   그대로 호출한다. 보드가 자기만의 "착수 가능" 판정을 갖는 순간 이중 진실원천이 된다.
2. **무손실** — 열에 배치된 건수 + 취소 건수 = 전체 건수. 어떤 태스크도 조용히 사라지지
   않는다(보드는 요약이 아니라 전수 투영이다).
3. **미머지 완료분 재조정** — `remote_claims.scan_remote_done`(fetch 없음·네트워크 0)으로
   *다른 브랜치에서 이미 done인* 태스크를 "다음 착수"에서 빼 대기 열로 옮기고 사유를
   붙인다. `next`가 같은 이유로 후보에서 제외하는 축이며(HARN-11), 이것이 없으면 **끝난
   작업이 예정으로 보여 중복 구현을 부른다**(도입 시 실측 15건). 스캔이 실패하거나
   `--no-remote`로 건너뛰면 **빈 결과를 "완료분 없음"으로 위장하지 않고** 보드 상단에
   "판정 불가(<사유>)" 배너를 띄운다 — 측정 실패는 통과와 같은 색이면 안 된다.

보드는 **읽기 전용**이다 — `backlog/`를 일절 쓰지 않으며, 상태 변경 창구는 `backlog.py`
CLI 단독이라는 규약이 그대로 유지된다. 기본 출력 경로 `work/`는 gitignore 대상이라
생성물이 저장소를 오염시키지 않는다(스냅샷을 남기려면 `--out`으로 명시 경로를 준다).

## 5. 다과목 확장과의 관계 (비침투 원칙)

백로그의 `subject` 필드는 **빌드 관리 메타데이터**다. 런타임 `Subject` enum·
개념 그래프·문항 스키마를 일절 만지지 않는다 (subject_pack_spec_v1.md
"Subject enum ADD VALUE 금지"와 무충돌). 새 과목 추가 = `models.SUBJECTS` 1줄
+ 태스크 시딩. 문명의 어떤 교육 영역이든 — 대학 수학·물리·화학·생물·지구과학·
경제·역사·세계사·국어·영어 — 같은 스키마로 일정 관리된다. 착수 *순서*는
E축 정본 문서가 결정하며, 하네스는 그 순서를 게이트로 집행할 뿐 날조하지 않는다.

## 6. 아키텍처 감시 (infra-debt 트랙)

`ARCH-NN-playbook-audit` 반복 태스크가 플레이북 불변식(2대 철칙·8대 구조 원칙·
7대 붕괴 연쇄)·7계층 경계·이중 truth source를 정기 점검한다.
- 점검 기준: `docs/standards/build_checkpoint_questions.md` ·
  `docs/standards/playbook_part_review_questions.md`
- 감사 완료 시 다음 회차를 `backlog.py add`로 즉시 재생성한다 (감시 공백 금지).
- 위반 발견 = 상환 태스크 등록 (감사가 백로그를 먹여 살린다).

## 7. CLI 요약

```bash
python3 scripts/harness/backlog.py status          # 진행률·게이트·다음 후보 한 화면
python3 scripts/harness/backlog.py next --n 3      # 착수 가능 후보 + 선정 사유
python3 scripts/harness/backlog.py start <id>      # claim (규칙 위반 시 거부)
python3 scripts/harness/backlog.py start <id> --ignore-remote-claim  # 이 태스크의 읽기측 판정만 무시(stale 확인 후·HARN-08)
python3 scripts/harness/backlog.py start <id> --no-remote            # 원격 보호 전체 생략(오프라인·긴급)
python3 scripts/harness/backlog.py done <id> --artifact "<PR 번호를 담은 증적>"   # 증적·PR 참조 필수
python3 scripts/harness/backlog.py done <id> --artifact "<커밋>" --no-pr ci-red   # 예외 4종만(HARN-23)
python3 scripts/harness/backlog.py start|done <id> --as kiki ...  # 사람-소유 태스크의 소유자 본인 기입(HARN-06)
python3 scripts/harness/backlog.py block <id> --reason "..." / unblock <id>
                    # block은 원격 대장에 kind=block 홀드를 **게시**한다(HARN-42/48) —
                    # 머지 없이 병렬 세션의 start가 즉시 거부된다. unblock이 그 홀드를 걷는다
python3 scripts/harness/backlog.py gates list|add|clear|waive   # add = 게이트 등재 CLI(HARN-18) — gates.yaml 손편집 금지
python3 scripts/harness/backlog.py gates clear <id> --as kiki --evidence "..."  # 사람이 본인 게이트를 닫을 때 주체 명시(HARN-60)
python3 scripts/harness/backlog.py amend <id> --reason "..." [--acceptance "정정 항"] [--gate <G-id>] [--track <트랙>] [--eos-priority P0|P1|P2|P3]
                                                   # 등재된 태스크의 정정 CLI(HARN-24) — tasks/*.yaml 손편집 금지
                                                   # --eos-priority = 기존 태스크 등급 백필의 유일한 합법 경로(HARN-55)
python3 scripts/harness/backlog.py add --id ... --title ... --eos-priority P0|P1|P2|P3 --path "src/backend/**"  # /plan 산출물
#   ↑ --eos-priority는 **필수**다 — 미지정은 exit 1 (계획서 100 Rule 1·3 집행 지점 · HARN-55).
#     P0가 예산(policy.eos_p0_budget)에 닿았으면 --swap-out <기존 P0 id>로 교환한다(Rule 4)
#   ↑ add는 등재 후 두 가지를 **고지**한다(차단 아님): 가시성(HARN-43)·의미 중복 후보(HARN-51)
python3 scripts/harness/backlog.py validate        # 무결성 전수 검증
python3 scripts/harness/backlog.py claims list --verbose   # 원격 claim 현황 (누가 무엇을)
python3 scripts/harness/backlog.py claims release <id> [--force]  # claim 해제 (남의 것은 --force)
python3 scripts/harness/backlog.py claims reap [--apply]   # stale claim 청소 (기본 dry-run)
python3 scripts/harness/backlog.py claims reap --auto      # 무인 집행 — 확정 사유만 (CI 전용)
python3 scripts/harness/backlog.py branches         # 미머지 브랜치 — 고립/PR제출 분리 (HARN-47)
python3 scripts/harness/backlog.py overlap <id>    # 착수 전 겹침 진단
python3 scripts/harness/backlog.py policy show|report      # 정책 값·warn 측정 리포트
python3 scripts/harness/board.py                   # 작업 보드 HTML (work/board.html)
```

테스트: `uv run --with pytest --with pyyaml pytest tests/harness` (2026-08-10 실측 251건 —
문서 수치는 스냅샷이며 정확 수는 pytest 수집이 정본. CI `harness-integrity` 잡이
`pytest tests/harness -q`로 무작위 순서 포함 실행 — CI의 `-q`는 화면 축약일 뿐 판정이
exit code이므로 "출력 억제·잘라내기 판정 금지" 금기(CLAUDE.md 2026-08-09)의 위반이 아니라
준수 사례다. 사람이 손으로 재현할 때는 `-q` 없이 돌리고 exit code를 병기할 것).

## 8. 금기

- ❌ backlog 상태를 마크다운 산문에만 기록하고 CLI 갱신 생략
- ❌ **`get_status`로 CI 상태를 판정하기 (HARN-30)** — MCP `pull_request_read method=get_status`(= commit status API)는 이 저장소에서 **항상 `total_count: 0`**을 낸다. 이 저장소는 commit status가 아니라 **check runs**를 쓰기 때문이며, 체크런 16건이 확실한 PR에서도 0이 나온다(2026-08-11·2026-08-31 두 차례 실측). 이걸 판정에 쓰면 "CI가 안 돌았다"는 오판을 낳는다. **대신 쓸 신호**: `GET /repos/{repo}/commits/{sha}/check-runs` · `GET /actions/runs?head_sha=<sha>` · MCP `pull_request_read method=get_check_runs`. 열린 PR 전수 점검은 `python3 scripts/ops/pr_delivery_audit.py <owner/repo>`(체크런 0건 ↔ green 미머지를 처방과 함께 구분·exit 1=주의 필요).
- ❌ **"미머지 PR"을 한 덩어리로 보기 (HARN-30)** — **트리거 미발화**(체크런 0건 → *깨워야* 한다)와 **조건 충족 미머지**(→ *사람 결정* 대기)는 처방이 정반대다. 전자는 **무증상**이라 아무도 보지 않으면 조용히 방치된다(실측: `pr_delivery_audit` 첫 실행에서 열린 PR 13건 중 미발화 5건·조건충족 미머지 7건). 깨우는 방법은 **`origin/main` 재병합 push**이며, 빈 커밋·PR 재개폐는 이 저장소가 금지한 경로다.
- ❌ **머지 전에 *전체* CI를 기다리기 (HARN-32)** — 머지를 막는 것은 전체 CI가 아니라 브랜치 보호가 지정한 **필수 체크 6종**뿐이다. 이 저장소의 최장 잡 `backend — lint·type·test`(~30분)는 **필수 목록에 없다**(2026-08-31 API 실측 — `GET /repos/{repo}/rules/branches/main`). 실측 중앙값: 필수 완주 **6.5분** vs 전체 완주 **28.6분**. main은 **40.7분**마다 전진하고 규칙이 `strict_required_status_checks_policy: true`(머지 시점 up-to-date 요구)이므로 **대기 시간이 곧 패배 확률**이다 — 필수만 대기 ≈16%, 전체 대기 ≈70%. 판정은 `python3 scripts/ops/pr_merge_readiness.py <owner/repo> <pr>`(exit 0=지금 머지), 재측정은 `scripts/analysis/measure_merge_gate_latency.py`. (사고 경위: 2026-08-31 PR #916이 전체 CI를 6회 기다려 머지 시도 3회가 전부 base 전진으로 실패했다. 그 지연 창에서 차단 2건이 무력화됐다 — HARN-48 참조)
- ❌ **차단·게이트 같은 보호 조치를 "대장에 썼으니 발효했다"고 보기 (HARN-48)** — 태스크 YAML은 **main에 머지돼야** 병렬 세션에 보인다. 이 저장소의 머지 지연은 CI(~30분)와 base 전진 경합(HARN-32)으로 시간 단위이며, 그 창 전체가 보호 공백이다. **대장 조치의 실효 시점은 조치 시점이 아니라 머지 시점**이다. 머지 없이 즉시 전파되는 채널은 `harness-claims` 브랜치뿐이므로 차단은 그 채널에 게시한다(`block`이 자동 수행). 게시가 실패하면 CLI가 "이 차단은 로컬에만 있다"를 경고한다 — 그 경고를 봤으면 보호가 없는 것이다. (사고 경위: 2026-08-31 `CUR-11` — block 00:28:07 → 13분 뒤 타 세션 claim 00:41:24 → 그 세션이 구현·머지 완료(#920). 차단은 대장에 실재했고 `next`에서도 사라졌으나 아무것도 막지 못했다)
- ❌ **태스크 정정을 문서에만 착지시키고 acceptance에 반영하지 않기 (HARN-24)** — "문서가 소유자"라는 우회는 착수 세션이 그 문서를 읽을 때만 성립한다. 태스크 YAML은 *반드시* 읽히지만 참조 문서는 선택이다. 정정은 `amend`로 acceptance에 도달시킨다. (사고 경위: ADMIN-02의 범위 축소 정정이 `operations_platform_gap_review.md`에만 있고 acceptance에 없어, 그 정정을 조상으로 가진 세션이 stale acceptance ②를 그대로 집행해 `subscription_*` 3컬럼까지 드롭 — 커밋 b3a58b02)
- ❌ 증적(artifact) 없는 done
- ❌ **PR 참조 없는 done** — 산출물이 있으면 요청 없이 PR을 여는 것이 기본값이다(CLAUDE.md "완료·병합"). 증적에 `#12`·`.../pull/12`가 없으면 CLI가 exit 1로 거부하며, 예외는 `--no-pr {investigation|incomplete|ci-red|kiki-hold}`로만 통과한다(HARN-23). 스쿼시 머지 커밋의 `(#758)` 관례는 그대로 통과 — 기존 증적 표기를 바꿀 필요 없다
- ❌ evidence 없는 게이트 clear
- ❌ E축 게이트 우회 착수 (waive는 Kiki 전용 결정)
- ❌ ROADMAP "현재 위치"를 backlog와 어긋나게 단독 편집
- ❌ 원격 claim conflict를 무시하고 착수 (남의 claim 강제 해제는 `claims release --force` — 상대 세션 확인 후)
- ❌ 홀더 브랜치 생존 확인 없이 `--ignore-remote-claim` 사용 — 확인 명령(`git log -1 --format='%cr %h %s' origin/<branch>`)은 거부 메시지에 동봉된다. 살아 있는 세션이면 그 순간부터 중복 구현이다
- ❌ 과탐 1건 때문에 `--no-remote`로 보호 전체 끄기 — 태스크 단위 우회(`--ignore-remote-claim`)가 있다
- ❌ 측정(policy report) 없이 warn→block 승격, 또는 결정로그 없는 승격
- ❌ **산출물을 검수하는 게이트를 그 산출물을 *만드는* 태스크에 걸기 (2026-09-06 등재)** — `requires_gates`는 `done` 조건이 아니라 **착수 조건**이다(`selector.py:6` — 후보 = 게이트 전부 cleared/waived). 회차 산출물을 사람이 검수해야 clear되는 게이트를 회차 태스크에 걸면 *회차 전엔 검수할 것이 없고 검수 전엔 회차를 못 시작하는* 교착이 된다. 검수 게이트는 **그 산출물을 소비하는 후속 태스크**에 건다(선행 태스크 = 산출, 후속 태스크 = `depends_on` 선행 + `requires_gates` 검수). `amend`는 게이트를 *부착만* 하므로(HARN-67 ⑤) 오부착은 `cancel`+재등재로만 고칠 수 있고 번호가 소모된다 — 등재 전에 `next --n 500 --json`으로 노출 여부를 확인한다. (사고 경위: 2026-09-06 `MP-01`에 `G-eos-first-run-canary-review`를 걸어 교착 → `MP-02`(회차)·`MP-03`(골든 승격·게이트+의존)로 분리 재등재. 정정 경로 부재로 인한 번호 소모 3회차 — EOS-94·96·MP-01)
- ❌ **접두(prefix)가 99번을 다 쓴 뒤 3자리 번호를 손으로 만들기 (2026-09-06 등재)** — `TASK_ID_RE`(`models.py:109`)는 정확히 2자리만 허용하고 `_next_free_number`는 소진 시 3자리를 날조하지 않고 `None`을 내 `add`가 거부한다(HARN-21). 대응은 **새 접두 신설**이며 사람의 결정이다 — 접두는 계열의 뜻을 담아 짓고(예: `MP` = 마이크로 프로젝트 = accumulate 회차), 첫 등재 notes에 신설 사유를 적는다. **현재 소진된 접두: `EOS`(2026-09-06 · EOS-98은 #994 age-band 좌석·EOS-99는 캐시 계측이 마지막)** — EOS 축 일반의 후속 접두는 결정 게이트 `G-eos-task-prefix-exhausted`[kiki·#1001]가 정한다(그 전까지 타 세션은 `ARCH-42` 임시 등재). `MP`(#1000)는 EOS 후속이 아니라 *회차 축* 접두다. (사고 경위: `EOS-100` 등재가 형식 위반으로 거부됐다 — 실측)
