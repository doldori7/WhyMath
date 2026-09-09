# G-eos63 — `attempt_event.skill_ids` 기록률 실측 회차 (Kiki 실행 런북)

> 이 문서는 게이트 **`G-eos63-skill-event-reach-sample`**(kiki·2026-09-01 등재)의 실행 절차다.
> 게이트가 풀리면 `EOS-63-attempt-skill-event-consumption`(P1)의 차단이 해제된다.
>
> **판정 기준: main `4abacdce`(2026-09-08 재확인)** — 아래 명령·플래그·기본값·경로는 전부 그
> 커밋의 코드에서 확인했다(`attempt_skill_event_reach_report.main()` 인자 정의 ·
> `config.Settings.database_url` 기본값과 `WHYMATH_` 접두 · `scripts/demo/run_demo.ps1`의 DB URL
> 규약 · `attempt_skill_reach_probe`의 exit 표).
>
> **갱신(2026-09-08)**: 최초 작성(main `3a30244c`) 시점에는 프로브(`attempt_skill_reach_probe`)가
> main에 없어 [1단계]가 그 사실을 스스로 판정해 폴백 브랜치를 고르게 돼 있었다. 그 프로브는
> **main에 착지했고 폴백 브랜치(`claude/skill-event-reach-sample-ec2w3b`)는 삭제됐다**(실측:
> `git cat-file -e origin/main:src/backend/whymath_backend/harness/attempt_skill_reach_probe.py`
> → 존재 · `git ls-remote --heads origin claude/skill-event-reach-sample-ec2w3b` → 0건). 삭제된
> ref를 fetch하면 Kiki 화면에 해석 불가한 오류가 뜨므로 [1단계]에서 그 분기를 제거했다 —
> 이제 main만 본다. (CLAUDE.md 「검증 없는 실행 안내 금지」: 안내 전 실재를 실측한다)

---

## 1. 과제 명칭

`문제시도` 이벤트 **스킬 배열 기록률 라이브 1회차 실측** — "좌석과 writer를 만들었다"와
"작동한다"를 실측으로 가른다.

## 2. 목적

`EOS-63`은 스킬 축 롤업을 **런타임 재해소** 대신 **기록된 사실**(`attempt_event.skill_ids`)을
읽도록 바꾸는 태스크다. 그 전환에는 딱 한 가지 선결 조건이 있다 —

> 기록이 실제로 쌓이고 있는가? **기록 0건 상태에서 소비를 바꾸면 스킬 숙달 전파가 죽는다.**

그 수치는 **실 PG의 실제 채점 이력**이 분모라서 CI에서는 원리적으로 나오지 않는다(매 잡의 DB가
비어 있다). 그래서 사람이 Phaiakes9에서 1회 돌려야 하고, 그것이 이 게이트다.

산출은 리포트의 **3분류**(미도달 / 해소 0건 / 해소 ≥1)와 **해소율**이며, 그것이 EOS-63
acceptance ②의 유일한 판정 재료다.

### 왜 리포트만 돌리면 안 되는가 (이 런북에 프로브가 있는 이유)

리포트는 **관측만** 한다. Phaiakes9의 prod DB에 EOS-57 writer 착지(2026-08-30) *이후*의 채점이
없으면 전 지표가 `측정 불가(분모 0)`로 나오고, 회차가 통째로 공전한다. 그래서 이 런북은
**표본을 만드는 단계**를 앞에 둔다. 프로브는 `record_attempt_skill_event`를 직접 부르지 않고
**실제 `POST /v1/me/attempts` 라우트**를 in-process로 태운다 — 직접 호출하면 도달률이 구성상
100%가 되어 측정이 아니라 동어반복이 되기 때문이다.

## 3. 구체적 절차

| 단계 | 무엇이 일어나는가 | 예상 출력 | 소요 |
|---|---|---|---|
| ① 체크아웃 | main으로 detached 이동(지역 브랜치 무변경) | `PROBE_FILE_OK=True` | ~20초 |
| ② 환경 | UTF-8 콘솔 + prod DB(5433) URL 주입 + **포트 도달성**·import 확인 | `PORT5433_OPEN=True` | ~10초 |
| ③ 사전 관측 | 지금 DB에 무엇이 있는지 읽는다(**쓰기 0**) | 리포트 마크다운 | ~10초 |
| ④ 표본 생성 | 채점 20건을 실제 라우트로 제출 | 회차 요약 + `work\eos63\probe.json` | 1~3분 |
| ⑤ 사후 측정 | 프로브 회차 창으로 리포트 재실행 | 리포트 + `work\eos63\report.json` | ~10초 |
| ⑥ 자가검증 | 창 안 이벤트 수·해소율을 뽑아 출력 | `EVENTS=..` `E2E_RATE=..` | 즉시 |

**쓰기가 남는다(의도)**: ④는 prod DB에 채점 행을 남긴다 — 남지 않으면 ⑤가 볼 것이 없다.
행은 전부 프로브 전용 고정 사용자
`c5de83b3-9143-58e8-a7a8-cf378801c065` 소유라 사후 식별·정리가 user_id 하나로 끝난다(§7).

## 4. 성공 기준

**판정은 리포트의 수치로 한다.** 프로브의 exit code는 *회차가 성립했는가*만 말한다.

### 성공

⑥의 자가검증이 `EVENTS≥1`을 내면 이 게이트가 요구한 실측은 성립한다. 그 다음 해소율을 읽는다:

| 관측 | 뜻 | EOS-63에 주는 판정 |
|---|---|---|
| 해소 ≥1이 다수 | concept→skill 브리지가 산다 | **전환 가능** — 수치를 EOS-63 notes에 남기고 착수 |
| 전부 `해소 0건`(`[]`) | writer는 돌았고 **매핑 데이터가 비었다** | 전환 보류 — 대책은 코드가 아니라 **브리지 데이터 보강** |
| `이벤트 있으나 skill_ids NULL`이 0이 아님 | **병리** — 이 컬럼을 NULL로 쓰는 다른 경로가 생겼다 | 조사 태스크 등재 |

`coach_completion` 행이 `0`인 것은 **정상**이다 — 프로브가 그 경로를 태우지 않는다(코치 대화
완료 경로). "0으로 보이는 것"과 "죽은 것"을 여기서 혼동하지 않는다.

### 실패 — 프로브 exit code별 대처 (전부 서로 다른 번호다)

| exit | 뜻 | 대처 |
|---:|---|---|
| 2 | DB 미도달 | ②의 `PORT5433_OPEN`이 먼저 잡는다 — 컨테이너 생존이 아니라 **호스트 포트 도달성**을 본다(§[2단계] 대처) |
| 3 | **스키마 뒤처짐** — `attempt_event.skill_ids` 부재 | §6의 마이그레이션 블록을 1회 실행 후 ④부터 재개 |
| 4 | 후보 문제 0건 | 코퍼스 미적재 — **prod에 시드하지 않는다**(§7-2). 이 회차는 여기서 끝나고, 그 사실 자체가 측정 결과다 |
| 5 | 제출 전건 실패 | 화면의 「실패 사유」 표(예외 타입명)를 그대로 세션에 전달 |

`해소율 0%`는 **실패가 아니라 측정값**이다(exit 0). 그 경우도 게이트는 닫힌다 — 닫히지 않는 것은
*측정이 안 된 경우*뿐이다.

> **단, exit 4(후보 문제 0건)는 다르다.** 그것은 해소율이 0인 것이 아니라 **분모를 만들 수조차
> 없는** 상태이고, prod에 시드해서 만드는 것은 2026-07-26 확정 결정 위반이다(§7-2). 이 경우
> 게이트를 닫을지 여부는 사람의 판단이며, 세션이 대신 닫지 않는다 — 남은 해소율 축은
> `EOS-43-skill-resolution-isolated-db-measurement`가 격리 DB에서 소유한다.

## 5. 실행 환경

- **머신**: Phaiakes9(= Kiki의 작업 PC 그 자체 · 별도 접속 없음)
- **시스템**: Windows PowerShell (WSL 아님)
- **작업 디렉터리**: `C:\Users\kiki\Desktop\__AI\WhyMath`
- **선행 조건**: Docker Desktop 실행 중 · `whymath-pg` 컨테이너(호스트 포트 **5433**) 가동 ·
  `src\backend\.venv` 세팅 완료
- **DB**: prod DB = docker `whymath-pg` (5433). 데모용 55432·타 프로젝트 5432와 혼동 금지.

## 6. 창 구분

**전 단계가 같은 창 하나에서 끝난다.** 서버(uvicorn)를 띄우지 않으므로 점유 창이 없고, 창을
나눌 이유도 없다. 새 PowerShell 창 하나를 열고 아래 블록을 순서대로 붙여넣는다.

---

## 실행 블록

> 아래 블록은 **자리표시자가 하나도 없다**. 그대로 통째로 붙여넣으면 된다.
> 각 블록 끝의 자가검증 줄이 **실패 상태에서 다른 값을 낸다** — 그 값을 보고 다음 블록으로 간다.

### [1단계] 체크아웃 — main으로 detached 이동(지역 브랜치 무변경)

```powershell
# [Windows PowerShell · Phaiakes9]
cd C:\Users\kiki\Desktop\__AI\WhyMath
# 작업 트리 청결부터 확인한다 — 더러우면 아무것도 하지 않는다.
# (붙여넣기 실행에서는 `throw`가 뒤 줄을 멈추지 못하므로 뒷부분을 통째로 가드로 감싼다.)
# `--untracked-files=no`가 핵심: untracked 파일은 체크아웃을 막지도 덮어쓰지도 않는데,
# 그것까지 세면 위험하지 않은 상태에서 블록이 멈춘다(2026-09-08 실측 — `reports/`와
# `ruleset*.json` 5건 때문에 회차가 한 번 공전했다). 위험한 것은 *추적 중인* 변경뿐이다.
$Dirty = (git status --porcelain --untracked-files=no)
"TRACKED_DIRTY=" + [bool]$Dirty
if (-not $Dirty) {
  # 지역 브랜치는 손대지 않는다 — detached HEAD로만 옮긴다. `checkout -B`는 지역 브랜치
  # 포인터를 원격 tip으로 *강제 이동*시켜 아직 push하지 않은 지역 커밋을 그 브랜치에서
  # 도달 불가로 만든다. 위 청결 검사로는 그 상태가 잡히지 않는다(트리는 깨끗하니까).
  $Branch = (git rev-parse --abbrev-ref HEAD)
  "RETURN_TO=$Branch"
  git fetch origin main
  $ProbeRel = "src/backend/whymath_backend/harness/attempt_skill_reach_probe.py"
  git checkout --detach origin/main
  git log --oneline -1
  "PROBE_FILE_OK=" + (Test-Path (Join-Path (Get-Location) $ProbeRel))
}
```

**자가검증**: `TRACKED_DIRTY=False` **그리고** `PROBE_FILE_OK=True`.
`RETURN_TO=`에 찍힌 이름은 회차가 끝난 뒤 돌아갈 브랜치다(§7-4). 이 블록은 **지역 브랜치를
전혀 바꾸지 않는다** — detached HEAD로만 이동하므로 push하지 않은 지역 커밋이 안전하다.
- `TRACKED_DIRTY=True`면 추적 중인 미커밋 변경이 있어 블록이 **아무것도 하지 않은 것**이다(의도) —
  그 변경을 어떻게 할지 세션에 물은 뒤 다시 온다.
- `PROBE_FILE_OK=False`면 fetch가 실패했거나(네트워크) main에서 프로브가 사라진 것이다 —
  다음 단계로 가지 말고 세션에 알린다. 이 검사는 변별력이 있다: 파일이 없으면 `False`가 뜬다.

### [2단계] 환경 — UTF-8 + prod DB + 컨테이너 생존

```powershell
# [Windows PowerShell · Phaiakes9] 같은 창
$OutputEncoding = [Console]::OutputEncoding = [Text.UTF8Encoding]::new()
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
$env:WHYMATH_DATABASE_URL = "postgresql+asyncpg://whymath@127.0.0.1:5433/whymath?ssl=disable"
# 이 창은 저장소 루트에 있는데 `-m whymath_backend...`는 패키지가 venv에 설치돼 있어야 풀린다.
# 설치돼 있으면 이 줄은 무해하고(같은 코드를 가리킨다), 안 돼 있으면 이 줄이 해결한다 —
# "설치돼 있을 것이다"라는 가정 자체를 없앤다.
$env:PYTHONPATH = (Resolve-Path "src\backend").Path
$Py = "src\backend\.venv\Scripts\python.exe"
New-Item -ItemType Directory -Force -Path work\eos63 | Out-Null
"PG_CONTAINER=" + (docker ps --filter "name=whymath-pg" --filter "status=running" --format "{{.Names}}")
# 컨테이너 생존은 *간접* 신호다 — 아래 두 줄이 진짜 판정이다(2026-09-08 사고: 컨테이너가 Up이고
# pg_isready도 통과하는데 호스트에서만 못 붙는 상태가 실재했다). `PortBindings`는 만들 때 요청한
# **설정**이고 `docker ps`의 Ports·`NetworkSettings.Ports`는 **실현된 게시**다 — 이 둘이 어긋나는
# 것이 그 고장의 형태이므로, 설정이 옳다는 이유로 정상으로 읽지 않는다.
"PG_PORTS_REALIZED=" + (docker inspect -f '{{json .NetworkSettings.Ports}}' whymath-pg)
"PORT5433_OPEN=" + (Test-NetConnection -ComputerName 127.0.0.1 -Port 5433 -WarningAction SilentlyContinue).TcpTestSucceeded
"PY_OK=" + (Test-Path $Py)
& $Py -c "import whymath_backend, sys; print('IMPORT_OK=True')"
"IMPORT_EXIT=$LASTEXITCODE"
```

**자가검증**: 다섯 줄이 모두 맞아야 한다 — `PG_CONTAINER=whymath-pg` ·
`PG_PORTS_REALIZED`가 **빈 배열이 아님**(`{"5432/tcp":[{...5433...}]}`) · `PORT5433_OPEN=True` ·
`PY_OK=True` · `IMPORT_OK=True`(그리고 `IMPORT_EXIT=0`).
- `PG_CONTAINER=`이 비어 있으면 컨테이너가 죽은 것이다 — `docker start whymath-pg` 후 이 블록을
  다시 돌린다.
- **`PORT5433_OPEN=False`인데 `PG_CONTAINER`는 채워져 있으면** 포트 게시가 성립하지 않은 것이다.
  Windows의 Hyper-V/WinNAT 동적 포트 제외 범위가 5433을 삼킨 경우가 실측된 원인이다 —
  `netsh interface ipv4 show excludedportrange protocol=tcp`로 5433을 포함하는 구간이 있는지 보고,
  있으면 관리자 권한으로 `net stop winnat` → `netsh int ipv4 add excludedportrange protocol=tcp
  startport=5433 numberofports=1` → `net start winnat` 후 Docker Desktop과 컨테이너를 재기동한다
  (Docker Desktop을 먼저 종료하고 실행한다). 상세·재발 방지는 `OPS-72`가 소유한다.
- `IMPORT_OK`가 안 찍히고 `IMPORT_EXIT=1`이면 의존성 미설치다(ModuleNotFoundError의 *대상*이
  화면에 찍힌다 — 그 이름을 세션에 전달한다). 3단계로 가면 같은 실패를 DB 오류처럼 보게 되므로
  여기서 멈추는 것이 맞다.

> **`$LASTEXITCODE`를 단독 판정으로 쓰지 않는다**: 이 변수는 *외부 실행 파일이 실제로 돌았을 때만*
> 갱신된다. 명령이 파싱 오류 등으로 시작조차 못 하면 **이전 값이 그대로 남아 성공처럼 보인다**
> (2026-09-08 실측 — 실패한 명령 뒤에 `REPORT_EXIT=0`이 찍혔다). 그래서 아래 단계들은 exit code와
> **산출물 파일의 실재**를 함께 본다. CLAUDE.md 「래퍼가 종료 코드를 가림」 축의 PowerShell 변형이다.

### [3단계] 사전 관측 (읽기 전용 — DB에 아무것도 쓰지 않는다)

```powershell
# [Windows PowerShell · Phaiakes9] 같은 창
# 이전 회차 잔재를 먼저 지운다 — 안 지우면 옛 파일이 이번 결과인 척한다
# (CLAUDE.md 「지금 보는 것이 이번 실행 것인가」).
Remove-Item work\eos63\probe.json, work\eos63\report.json -ErrorAction SilentlyContinue
"===== 3. 사전 관측 (읽기 전용) ====="
& $Py -m whymath_backend.harness.attempt_skill_event_reach_report --json work\eos63\before.json
"BEFORE_EXIT=$LASTEXITCODE"
"===== 4. 표본 생성 20건 (여기서만 DB에 쓴다) ====="
& $Py -m whymath_backend.harness.attempt_skill_reach_probe --count 20 --json work\eos63\probe.json
"PROBE_EXIT=$LASTEXITCODE"
if (Test-Path work\eos63\probe.json) {
  "===== 5. 사후 측정 ====="
  $Since = (Get-Content work\eos63\probe.json -Raw | ConvertFrom-Json).started_at
  "SINCE=$Since"
  & $Py -m whymath_backend.harness.attempt_skill_event_reach_report --since $Since --json work\eos63\report.json
  "REPORT_EXIT=$LASTEXITCODE"
  if (Test-Path work\eos63\report.json) {
    $R = Get-Content work\eos63\report.json -Raw | ConvertFrom-Json
    $P = Get-Content work\eos63\probe.json  -Raw | ConvertFrom-Json
    "===== 6. 게이트 증적 ====="
    "WINDOW=$($R.since)"
    "ATTEMPTS=$($R.attempts_total)  EVENTS=$($R.events_total)"
    "EMPTY=$($R.events_empty_skill_ids)  NONEMPTY=$($R.events_nonempty_skill_ids)  NULL=$($R.events_null_skill_ids)"
    "WRITER_REACH=$($R.writer_reach_rate)  RESOLUTION=$($R.resolution_rate)  E2E=$($R.end_to_end_rate)"
    "PROBE_ACCEPTED=$($P.accepted)  PROBE_FAILED=$($P.failed)"
    git log --oneline -1
  } else { "REPORT_JSON_MISSING=True -- 사후 측정 실패. 화면의 오류 줄을 세션에 전달한다" }
} else { "PROBE_JSON_MISSING=True -- 표본 생성 실패. 위 PROBE_EXIT 숫자를 세션에 전달한다" }
```

**왜 한 블록인가**: 3~6단계를 따로 두었더니 회차 하나가 **4단계를 통째로 건너뛴 채 5단계로
넘어가** 공전했다(2026-09-08 실측). 붙여넣기 실행에서는 순서를 사람이 지켜 주지 않으므로,
순서를 **가드가 강제**하게 한다 — 앞 단계 산출물이 없으면 뒷 단계가 아예 돌지 않는다.

**판정은 exit code가 아니라 산출물 파일의 실재로 한다** — 위 §[2단계] 말미의 `$LASTEXITCODE`
경고 참조. `Test-Path`는 실패 상태에서 실제로 `False`를 내므로 변별력이 있다.

**성공 판정**: `===== 6. 게이트 증적 =====` 아래 6줄이 출력되고 `EVENTS`가 1 이상.
그 6줄과 마지막 커밋 줄을 **그대로 복사해 세션에 전달**한다 — 그것이 게이트 증적이다.

**멈춘 지점별 대처**:
- `PROBE_JSON_MISSING=True` → `PROBE_EXIT` 숫자가 원인을 가른다(§4의 exit 표).
  **`4`(후보 문제 0건)는 §7-2로 간다 — prod에 시드하지 않는다.**
- `REPORT_JSON_MISSING=True` → 사후 측정이 실패했다. 화면의 예외 타입명을 전달한다.

---

## 7. 보조 블록 (필요할 때만)

### 7-1. exit 3(스키마 뒤처짐)이 났을 때 — 마이그레이션 1회

```powershell
# [Windows PowerShell · Phaiakes9] 같은 창
cd C:\Users\kiki\Desktop\__AI\WhyMath\src\backend
& .\.venv\Scripts\python.exe -m alembic -c alembic.ini upgrade head
"EXIT=$LASTEXITCODE"
cd C:\Users\kiki\Desktop\__AI\WhyMath
```

`EXIT=0`을 확인한 뒤 [4단계]부터 재개한다.

### 7-2. exit 4(후보 문제 0건)가 났을 때 — ⛔ prod에 시드하지 않는다

> **이 절은 2026-09-09에 뒤집혔다.** 이전 판은 여기서 `& $Py scripts\demo\seed_demo.py`를
> 돌리라고 안내했다. **그 안내는 prod DB를 오염시킨다** — `seed_demo.py`는
> `WHYMATH_DATABASE_URL`을 그대로 쓰므로, 이 런북의 [2단계]가 그 변수를 prod(5433)로 설정한
> 상태에서 실행하면 문항 코퍼스 3종(손저작 4 + 단답 620 + 객관식 1080)이 **prod에 적재된다**.
> `scripts/demo/PILOT_RUNBOOK.md`의 DB 선택 표는 그 경로를 이미 기각했다 —
> *"B. prod 오버라이드 `whymath-pg`(5433) — 데모 시드가 prod에 섞임 — **미채택**"*
> (Kiki 확정 2026-07-26). 런북이 확정 결정과 충돌하고 있었다.

**exit 4가 나면 이 회차는 prod에서 끝난다.** 후보 문제 0건은 고쳐야 할 오류가 아니라
**측정 결과**다 — prod에 태울 문항이 없다는 사실 자체가 게이트가 물은 것의 일부다. §6의
사전 관측(3단계) 출력과 아래 전수 카운트를 증적으로 남기고 세션에 전달한다.

```powershell
# [Windows PowerShell · Phaiakes9] 같은 창 — 읽기 전용 전수 카운트
docker exec -i whymath-pg psql -U whymath -d whymath -v ON_ERROR_STOP=1 -c "SELECT 'problem' AS t, count(*) AS n FROM problem UNION ALL SELECT 'problem_with_difficulty', count(*) FROM problem WHERE difficulty_overall IS NOT NULL UNION ALL SELECT 'problem_attempt', count(*) FROM problem_attempt UNION ALL SELECT 'attempt_event', count(*) FROM attempt_event UNION ALL SELECT 'user_profile', count(*) FROM user_profile UNION ALL SELECT 'concept', count(*) FROM concept ORDER BY 1;"
"EXIT=$LASTEXITCODE"
```

해소율(개념→스킬 매핑이 실제로 스킬을 찾아내는 비율)은 **격리 DB**에서 따로 잰다 — 그 값은
코퍼스·브리지 데이터의 성질이지 prod 트래픽의 성질이 아니라, 같은 코퍼스면 어느 DB에서 재도
같은 답이 나온다. 그 회차는 `EOS-43-skill-resolution-isolated-db-measurement`가 소유한다.

**2026-09-09 실측(main `94d1f28a`)**: `problem` 0 · `problem_with_difficulty` 0 ·
`problem_attempt` 0 · `attempt_event` 0 · `concept` 2,683 · `user_profile` 2. prod DB에는
개념 백본만 있고 문항 코퍼스도 채점 이력도 전 기간 0건이다. 이 회차를 다시 돌리는 세션은
**같은 결과를 먼저 예상하고** 시작한다.

### 7-3. 표본 정리 (선택 — **게이트를 닫은 뒤에만**)

> ⚠ 이 블록은 **측정한 표본을 지운다**. 게이트 증적(§6의 6줄)을 세션에 전달하기 *전에*
> 돌리면 재측정해야 한다. 지우지 않아도 무해하다 — 프로브 사용자 한 명의 행일 뿐이다.

```powershell
# [Windows PowerShell · Phaiakes9] 같은 창
$U = "c5de83b3-9143-58e8-a7a8-cf378801c065"
docker exec -i whymath-pg psql -U whymath -d whymath -v ON_ERROR_STOP=1 -c "DELETE FROM attempt_event WHERE user_id='$U'; DELETE FROM skill_mastery_history WHERE user_id='$U'; DELETE FROM concept_mastery_history WHERE user_id='$U'; DELETE FROM problem_attempt WHERE user_id='$U'; DELETE FROM user_profile WHERE user_id='$U';"
"EXIT=$LASTEXITCODE"
```

---

### 7-4. 회차 후 원래 브랜치로 복귀

[1단계]가 detached HEAD로 옮겨 두었으므로, 끝나면 원래 자리로 돌아온다.

```powershell
# [Windows PowerShell · Phaiakes9] 같은 창
if ($Branch -and $Branch -ne "HEAD") { git checkout $Branch } else { git checkout main }
git status --short --branch
```

`$Branch`는 [1단계]가 같은 창에 남긴 값이다. 창을 새로 열었다면 `git checkout main`으로
돌아오면 된다(지역 커밋은 손대지 않았으므로 그대로 있다).

---

## 8. 게이트 clear 방법

**Kiki가 할 일은 §6의 6줄을 세션에 전달하는 것까지다.** 대장 조작(`backlog.py gates clear`)은
세션이 가져간다 — 이 문서에 그 명령을 붙여넣기 블록으로 두지 않는 이유는, 증적 문자열이
자리표시자를 포함할 수밖에 없어 그대로 실행되면 잘못된 증적이 대장에 박히기 때문이다.

세션 쪽 참고: `gates clear`의 `--evidence`에는 **판정 기준(커밋 해시 또는 PR 참조)**이 반드시
들어가야 한다(HARN-68 — 없으면 CLI가 exit 1로 거부한다). 증적 본문은 §6의 6줄 + 프로브가
돌아간 커밋 해시 + `WINDOW` 값으로 구성한다.

## 9. 이 회차가 답하지 못하는 것 (정직 고지)

- **유기적 트래픽의 writer 도달률이 아니다.** 표본을 프로브가 만들었으므로 배선이 살아 있으면
  도달률은 100%다. 그 100%가 증명하는 것은 "`attempt_submit` 경로의 writer 배선이 이 DB에서
  실제로 작동한다"까지이고, "학생들이 쓰고 있다"가 아니다.
- **`coach_completion` 경로는 미측정이다.** 리포트의 그 행이 0인 것은 죽었다는 뜻이 아니라
  이 회차가 태우지 않았다는 뜻이다. 그 경로의 실측은 실기기·코치 대화 회차가 필요하다.
- **해소율은 이 DB의 브리지 데이터에 대한 값이다.** 코퍼스가 바뀌면 값도 바뀐다 — 그래서
  증적에 판정 기준 커밋과 창(`WINDOW`)을 함께 남긴다.
