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
- **해소 명령** — `backlog.py gates clear <id> --evidence "<근거>"` 그대로 복사 가능

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
python3 scripts/harness/backlog.py amend <id> --reason "..." [--acceptance "정정 항"] [--gate <G-id>] [--track <트랙>]
                                                   # 등재된 태스크의 정정 CLI(HARN-24) — tasks/*.yaml 손편집 금지
python3 scripts/harness/backlog.py add --id ... --title ... --path "src/backend/**"  # /plan 산출물
python3 scripts/harness/backlog.py validate        # 무결성 전수 검증
python3 scripts/harness/backlog.py claims list --verbose   # 원격 claim 현황 (누가 무엇을)
python3 scripts/harness/backlog.py claims release <id> [--force]  # claim 해제 (남의 것은 --force)
python3 scripts/harness/backlog.py claims reap [--apply]   # stale claim 청소 (기본 dry-run)
python3 scripts/harness/backlog.py claims reap --auto      # 무인 집행 — 확정 사유만 (CI 전용)
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
