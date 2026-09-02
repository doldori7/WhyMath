# WhyMath prod DB 백업·복구(DR) 런북 — OPS-02

> 대상: docker `whymath-pg`(pgvector/pg16 · 호스트 포트 **5433** · trust · user/db=whymath).
> 시연용 `whymath-demo-db`(55432 · 볼륨 없는 일회용)와 **혼동 금지** — 스크립트가 demo-db 지정 시 명시 거부한다.
> 스크립트 본문은 **ASCII 전용**(PowerShell 5.1이 .ps1을 cp949로 읽는 실측 — 2026-07-17 logconfig 사고 선례, `tests/infra/test_backup_script.py`로 동결). 한국어 설명은 이 런북에만 둔다.

---

## 사전 브리핑 (CLAUDE.md 6항목 템플릿)

1. **과제 명칭** — prod DB(`whymath-pg`) pg_dump 정기 백업 + 복구 리허설(DR).
2. **목적** — 단일 머신(Phaiakes9) SPOF 상환. 디스크 장애·컨테이너 소실·오조작(DROP 등) 시 마지막 백업 시점으로 복구할 수 있는 `.dump` 파일을 주기적으로 남기고, "복원되는 백업"임을 리허설로 증명한다. 결과물은 `C:\Users\kiki\Desktop\__AI\WhyMath-backups\whymath_<타임스탬프>.dump`.
3. **구체적 절차** — §0 브랜치 준비(1분) → §1 수동 백업 1회(약 1~2분: 컨테이너 안 pg_dump → `pg_restore --list` 정합 검증 → 호스트 회수 → 보존 정책 적용) → §2 작업 스케줄러 등록(주 2회, 5분) → §3 복구 리허설(분기 1회 권장, 약 10분: scratch 컨테이너 55433에 복원 → 행수 대조 → 폐기).
4. **성공 기준** — 각 단계 블록에 자가검증 스텝·성공/실패 판별·실패 시 대처 1개를 병기했다. 총괄 기준: §1에서 `[OK] backup: ...` 출력 + 종료코드 0 + 크기>0인 `.dump` 생성, §3에서 prod/scratch 행수 표 일치. `[FAIL] <사유>` 출력 + 종료코드 1이면 실패(사유가 반드시 출력된다 — 침묵 실패 없음).
5. **실행 환경** — **Windows PowerShell**(= Phaiakes9 이 PC 자체 · SSH 불요), 작업 디렉터리 `C:\Users\kiki\Desktop\__AI\WhyMath`. 선행 조건: Docker Desktop 실행 중 + `whymath-pg` 컨테이너 가동(§1 스크립트가 미가동 시 사유와 함께 스스로 실패한다). 호스트에 PostgreSQL 클라이언트 불요 — 전 과정이 컨테이너 안에서 실행된다.
6. **창 구분** — **새 PowerShell 창 1개**로 전 절차 수행 가능. 장기 점유 프로세스가 없다(백업 스크립트는 수 분 내 종료, 리허설 컨테이너는 `-d` 분리 실행) → 서버 점유 창 분리 규칙 해당 없음. 단, `run_demo.ps1` 시연 서버가 돌고 있는 창은 그대로 두고 **별도 창**을 쓴다.

---

## §0. 사전 준비 — 스크립트 실재 확인 (main 체크아웃이면 그대로 진행)

백업 스크립트는 **main에 착지했다**(2026-09-01 실측: `git ls-tree origin/main scripts/backup/` → `backup_whymath_pg.ps1` 존재). 별도 브랜치 체크아웃은 **불요**하다.

```powershell
# [실행 시스템] Windows PowerShell (= Phaiakes9 이 PC, 진입 명령 불요)
cd C:\Users\kiki\Desktop\__AI\WhyMath
git fetch origin
git checkout main
$co = $LASTEXITCODE
$cur = (git branch --show-current)
if ($co -ne 0 -or $cur -ne 'main') {
  Write-Host "[FAIL] main 체크아웃 실패 (exit=$co, 현재 브랜치=$cur) — 여기서 멈춘다. pull 하지 않는다."
} else {
  git pull origin main
  Write-Host ("[CHECK] branch=" + (git branch --show-current) + " script=" + (Test-Path .\scripts\backup\backup_whymath_pg.ps1))
}
```

- **성공**: `[CHECK] branch=main script=True` 한 줄.
- **실패**: `[FAIL] main 체크아웃 실패 ...` — **pull이 실행되지 않은 상태다.** 사유(다른 worktree가 main을 점유·미커밋 변경으로 전환 거부 등)를 해소한 뒤 블록을 다시 실행한다. `[CHECK]`가 나왔는데 `script=False`면 최신 main이 아닌 것이므로 `git pull origin main` 재실행.
- **변별력 근거(중요)**: `Test-Path` 단독은 이 자리에서 **변별력이 없다**. `git checkout main`이 실패해도 PowerShell은 네이티브 명령 실패로 멈추지 않고 계속 진행하며, 이어지는 `git pull origin main`은 *현재 체크아웃된 브랜치*(= 피처 브랜치)로 origin/main을 병합한다 — 그 결과 스크립트 파일은 존재하게 되어 `Test-Path`가 `True`를 내고, **잘못된 브랜치 위에서 준비 완료로 오판**된다. 그래서 종료코드와 현재 브랜치 이름을 먼저 확인하고, 통과했을 때만 pull한다. (2026-09-01 PR #952 Codex 리뷰 지적 수용)

> **정정 이력 (2026-09-01)**: 종전 §0은 `git checkout -B claude/whymath-service-review-9r21im origin/claude/...`를 지시했으나, 그 브랜치는 **원격에서 이미 삭제**돼(`git ls-remote --heads origin` 0건) 명령이 `fatal: invalid reference`로 즉시 실패한다. 게이트 `G-backup-offsite-move`·`G-backup-restore-rehearsal`가 21일 대기한 원인 후보다. CLAUDE.md「검증 없는 실행 안내 금지」의 *만료된 안내* 축 — 런북의 브랜치 참조는 그 브랜치가 머지·삭제되는 순간 조용히 무효가 된다.

## §1. 수동 백업 1회 실행

스크립트 내부 동작(전부 컨테이너 안 — 호스트 pg 클라이언트 불요):
① `whymath-demo-db` 지정 거부 + `whymath-pg` 가동 확인 → ② `pg_dump -U whymath -d whymath -Fc`로 `/tmp`에 덤프 → ③ **자가검증 A**: `pg_restore --list`로 회수 *전* 덤프 카탈로그 판독(손상 덤프는 여기서 비0 종료 = 실패 신호를 내는 변별력 있는 검사) → ④ `docker cp`로 호스트 회수 → ⑤ **자가검증 B**: 호스트 파일 존재+크기>0 → ⑥ 컨테이너 임시본 삭제 → ⑦ 보존 정책(`-RetentionDays`, 기본 14일) 적용 — 단 **최신 1개는 만료돼도 절대 삭제하지 않는다**(백업 전멸 방지).

```powershell
# [실행 시스템] Windows PowerShell (= Phaiakes9 이 PC, 진입 명령 불요)
cd C:\Users\kiki\Desktop\__AI\WhyMath
Set-ExecutionPolicy -Scope Process -Bypass -Force
.\scripts\backup\backup_whymath_pg.ps1

# 자가검증 1: 종료코드 - True 여야 함 (False = 실패, 직전 [FAIL] 사유 확인)
$LASTEXITCODE -eq 0

# 자가검증 2: 산출물 - 방금 시각의 .dump 파일, Length > 0 이어야 함
Get-ChildItem C:\Users\kiki\Desktop\__AI\WhyMath-backups\*.dump |
  Sort-Object LastWriteTime -Descending |
  Select-Object -First 1 Name, Length, LastWriteTime
```

- **성공**: `[OK] backup: ...` 출력, 자가검증 1이 `True`, 자가검증 2의 최신 파일 `LastWriteTime`이 방금이고 `Length > 0`. (변별력: 스크립트가 어느 단계에서 실패하든 종료코드 1 + `[FAIL] <사유>`가 출력되고, 손상 덤프는 호스트에 회수되지 않아 새 파일 자체가 안 생긴다.)
- **실패 시 대처**: 출력된 `[FAIL]` 사유대로 조치 — 대표 사례: `container 'whymath-pg' not found` → Docker Desktop 기동 후 `docker start whymath-pg` → 재실행.
- 보존 기간을 바꾸려면: `.\scripts\backup\backup_whymath_pg.ps1 -RetentionDays 30` (아래 §4 PIPA 잔존 창 항목도 함께 읽을 것).

## §1b. 백업 암호화 키쌍 생성 (최초 1회 — OPS-31)

> **왜 필요한가**: 덤프에는 §4가 실측한 대로 학적·프로필·활동 메타가 **평문**으로 들어간다. 파일 단위 암호화가 없으면 그 파일은 오프사이트로 나갈 수 없고(§4-1), 결국 백업이 prod와 같은 디스크에 갇힌다(§6 오프사이트 부재). 이 절이 그 매듭을 푼다.
>
> **왜 age인가**: 7-Zip AES는 *암호문구*를 쓴다 — 스케줄 실행에 쓰려면 그 암호문구가 백업 대상 옆에 상주해야 하고, 그러면 §4-5 키 분리가 성립하지 않는다. age는 **공개키로 잠그고 개인키로만 연다**: 백업 머신에는 공개키만 두고 개인키는 다른 장소에 보관한다. 백업 머신이 통째로 털려도 백업은 열리지 않는다.

```powershell
# [실행 시스템] Windows PowerShell (= Phaiakes9 이 PC, 진입 명령 불요)
cd C:\Users\kiki\Desktop\__AI\WhyMath
winget install FiloSottile.age
age-keygen -o "$env:USERPROFILE\whymath-backup-identity.key"
```

`age-keygen`이 출력한 `Public key: age1...` 한 줄을 **그대로 복사**해 수신자 파일로 만든다:

```powershell
# [실행 시스템] Windows PowerShell — 위 출력의 공개키를 아래 따옴표 안에 붙여넣는다
cd C:\Users\kiki\Desktop\__AI\WhyMath
Set-Content -Path "C:\Users\kiki\Desktop\__AI\WhyMath-backups\recipients.txt" -Value "여기에_age1로_시작하는_공개키_전체" -Encoding ascii

# 자가검증 1: 수신자 파일이 age 공개키 1줄을 담고 있는가 (True 여야 함)
(Get-Content "C:\Users\kiki\Desktop\__AI\WhyMath-backups\recipients.txt") -match '^age1[0-9a-z]{50,}$' | Select-Object -First 1

# 자가검증 2: 자리표시자가 그대로 들어가지 않았는가 (False 여야 함)
(Get-Content "C:\Users\kiki\Desktop\__AI\WhyMath-backups\recipients.txt") -like "*여기에_*"
```

- **성공**: 자가검증 1이 `True`, 자가검증 2가 `False`. (변별력: 자리표시자를 그대로 두면 1이 `False`가 되고, 백업 스크립트도 `age` 단계에서 실패하며 평문을 지운다 — 반쯤 암호화된 회차가 남지 않는다.)
- **실패 시 대처**: `age-keygen` 출력을 다시 열어 `# public key:` 줄만 붙여넣는다(개인키 줄을 붙여넣으면 자가검증 1이 `False`).

### 개인키 보관 (§4-5 키 분리의 실행)

`$env:USERPROFILE\whymath-backup-identity.key`는 **백업을 여는 유일한 수단**이다.

1. **백업 디렉터리에 두지 않는다** — 같이 유출되면 암호화가 무의미하고, 같이 소실되면 백업 전량이 영구 복구 불가가 된다.
2. 별도 매체(암호 관리자·오프라인 USB) 1부 이상 보관. **이 파일을 잃으면 모든 `.dump.age`가 영구히 열리지 않는다** — 이것이 암호화가 만드는 새 단일 실패점이며, 대책은 키 사본뿐이다.
3. 저장소에 커밋하지 않는다(`.gitignore`의 `*.key`가 이미 막지만, 위치 자체를 리포 밖에 둔다).

> 수신자 파일이 백업 디렉터리에 놓이는 순간부터 **모든 회차가 자동으로 암호화된다** — 스케줄 실행 포함. 플래그를 잊어서 평문으로 도는 경로가 없다(`tests/infra/test_backup_encryption.py::test_recipients_default_lives_in_backup_dir`가 그 기본값을 동결한다).

## §2. 정기 스케줄 등록 — 로그온 비의존 (OPS-31 개정)

> **이전 방식(`schtasks /Create`)은 로그온 세션에서만 돌았다.** PC가 꺼져 있거나 로그아웃이면 그 회차는 조용히 건너뛰어졌고, **건너뛴 상태는 정상 상태와 화면이 같았다**. 등록 스크립트가 그 두 가지를 각각 고친다: `-LogonType S4U`(로그온 없이 실행·암호 저장 없음) + `-StartWhenAvailable`(꺼져 있던 회차를 복귀 후 실행). 관리자 권한 창이 필요하다.
>
> **태스크는 2개가 등록된다** — `WhyMath-DB-Backup`(백업)과 `WhyMath-DB-Backup-Check`(신선도 검사). 둘째가 없으면 상태 대장을 **아무도 읽지 않고**, 읽지 않는 대장은 아무것도 탐지하지 못한다. 스케줄은 누락을 *줄이고*, 검사 태스크가 누락을 *보이게* 한다 — 이 분업이 §2의 요점이다. (초판은 검사 명령을 런북에 인쇄만 해서 사람이 기억하게 뒀는데, 그건 이 절이 없애려던 조용한 누락과 같은 실패 양식이다 — 2026-09-01 PR #968 리뷰 지적 수용.)

```powershell
# [실행 시스템] Windows PowerShell — **관리자 권한으로 실행** (작업 등록에 필요)
cd C:\Users\kiki\Desktop\__AI\WhyMath
.\scripts\backup\register_backup_schedule.ps1 -At 04:00 -CheckAt 09:00 -RequireEncryption
```

- **성공**: `[OK] task 'WhyMath-DB-Backup' ...`과 `[OK] task 'WhyMath-DB-Backup-Check' registered: daily 09:00, threshold 48 h, LogonType S4U` **두 줄이 모두** 나와야 한다. 한 줄만 나오면 실패다.
- **변별력**: 스크립트는 등록 후 작업을 **되읽어** `LogonType`이 실제로 `S4U`인지 확인한다. 권한이 모자라 Password 등록으로 강등되면 `[FAIL]`로 멈춘다 — "등록 성공"을 "설정이 옳다"의 근거로 쓰지 않는다.
- **실패 시 대처**: `LogonType 'Password', not S4U`가 나오면 창이 관리자 권한이 아니다. PowerShell을 "관리자 권한으로 실행"으로 다시 열어 재실행한다.

### 2-1. 실동작 검증 (등록 직후 의무)

```powershell
# [실행 시스템] Windows PowerShell (= Phaiakes9 이 PC, 진입 명령 불요)
cd C:\Users\kiki\Desktop\__AI\WhyMath
Start-ScheduledTask -TaskName "WhyMath-DB-Backup"
Start-Sleep -Seconds 120

# 자가검증 1: 마지막 실행 결과 코드 - 0 이어야 함
(Get-ScheduledTaskInfo -TaskName "WhyMath-DB-Backup").LastTaskResult

# 자가검증 2: 최신 산출물이 .dump.age(암호화본)인가
Get-ChildItem C:\Users\kiki\Desktop\__AI\WhyMath-backups\* -Include *.dump,*.dump.age |
  Sort-Object LastWriteTime -Descending | Select-Object -First 1 Name, Length, LastWriteTime

# 자가검증 3: 상태 대장이 신선한가 - exit 0 이어야 함
python scripts\backup\backup_status.py check --backup-dir "C:\Users\kiki\Desktop\__AI\WhyMath-backups" --max-age-hours 48 --require-encrypted
Write-Host "EXIT=$LASTEXITCODE"
```

- **성공**: 자가검증 1이 `0`, 2의 파일명이 **`.dump.age`로 끝나고** `Length > 0`, 3이 `EXIT=0`.
- **변별력(자가검증 3)**: 상태 파일이 없으면 `never_recorded`, 오래됐으면 `stale`, 평문이면 `--require-encrypted`가 각각 **다른 사유로** exit 1을 낸다. 세 사태의 대처가 다르므로 한 글자로 뭉개지 않는다.
- **실패 시 대처**: 자가검증 2가 `.dump`(평문)로 끝나면 §1b의 수신자 파일이 없거나 비어 있다 — 다만 `-RequireEncryption`으로 등록했다면 그 경우 백업은 애초에 실패하고 평문 파일도 남지 않는다.

### 2-2. 누락 감시 — 조용한 실패를 소리나게

**이 감시는 §2에서 등록한 `WhyMath-DB-Backup-Check` 태스크가 자동으로 수행한다.** 사람이 기억해서 돌리는 것이 아니다.

검사 태스크가 하는 일:

| 판정 | 산출물 | 태스크 결과 코드 |
|---|---|---|
| 신선함 | `backup_alert.txt`가 **있으면 삭제**(회복 표시) | 0 |
| 오래됨·기록 없음·평문 | 백업 디렉터리에 **`backup_alert.txt` 생성**(시각·사유·JSON 판정) | 1 |
| 검사 불가(파이썬·모듈 부재) | 같은 알림 파일에 그 사실 기록 | 2 |

- **알림이 회복 시 사라지는 것이 중요하다** — 안 사라지는 알림은 가구가 되고, 그러면 진짜 알림도 안 보인다.
- **정직한 한계**: 디렉터리 안의 파일은 *누가 볼 때만* 보이는 약한 신호다. 태스크의 `LastTaskResult`도 0이 아니게 되지만 그것 역시 들여다봐야 보인다. 푸시·메일·중앙 로그 같은 진짜 알림은 `OPS-04` 범위이며 이 스크립트가 대신하지 않는다.

수동으로 즉시 확인하려면(등록 검증·사고 조사 시):

```powershell
# [실행 시스템] Windows PowerShell (= Phaiakes9 이 PC, 진입 명령 불요)
cd C:\Users\kiki\Desktop\__AI\WhyMath
.\scripts\backup\check_backup_freshness.ps1 -MaxAgeHours 48 -RequireEncrypted
Write-Host "EXIT=$LASTEXITCODE"
```

- **성공**: `[OK] backup freshness check passed`, `EXIT=0`.
- **실패**: `[ALERT] ...`와 함께 알림 파일 경로가 출력되고 `EXIT=1`. `reason` 필드가 `never_recorded`(한 번도 안 돎)·`stale`(오래됨)·`plaintext_artifact`(평문이라 반출 불가) 중 어느 사태인지 말해 준다 — 셋은 대처가 다르므로 뭉개지 않는다.
- **`EXIT=2`**: 검사 자체를 못 했다(파이썬 경로 문제 등). **0으로 접지 않는다** — "검사 못 함"은 "문제 없음"이 아니다. `-PythonExe`로 인터프리터를 명시해 재실행한다(Kiki 머신은 conda base와 `.venv`가 동시 활성이라 `python`이 다른 인터프리터에 결합될 수 있다).

## §3. 복구 리허설 (분기 1회 권장) — scratch 컨테이너 복원 + 무결성 검증

일회용 scratch 컨테이너(pgvector/pg16)를 **포트 55433**에 띄워 최신 백업을 복원한다. 55433은 5432(타 프로젝트)·5433(prod)·55432(demo)와 비충돌. 127.0.0.1 바인딩으로 외부 비노출(실데이터 복제본 — §4 취급 규칙 적용).

### 3-0. 스톱워치 시작 — RTO 측정의 실행 (게이트 `G-backup-restore-rehearsal`)

> **왜 이 절이 있는가**: §5의 RTO 칸은 "첫 리허설 실측으로 채운다"고 적혀 있는데, 종전 §3에는 **시간을 재는 스텝이 하나도 없었다**. 그래서 리허설을 완주해도 게이트가 요구하는 수치가 나오지 않았다 — 절차가 산출하지 못하는 것을 게이트가 요구하는 상태였다. 이 절이 그 간극을 메운다. (CLAUDE.md「작동 신호 없는 알고리즘 부착 금지」의 런북 축 — 측정한다고 적어 놓고 측정 스텝이 없으면 측정은 일어나지 않는다.)

**이 블록부터 3-3b까지는 같은 PowerShell 창에서 연속 실행한다** — `$sw` 변수가 창에 살아 있어야 경과 시간이 나온다. 창을 닫거나 새 창으로 옮기면 3-3b가 `[FAIL]`로 그 사실을 알린다(조용히 0을 내지 않는다).

```powershell
# [실행 시스템] Windows PowerShell (= Phaiakes9 이 PC, 진입 명령 불요)
cd C:\Users\kiki\Desktop\__AI\WhyMath
$sw = [System.Diagnostics.Stopwatch]::StartNew()
Write-Host ("[RTO] stopwatch started at " + (Get-Date -Format "yyyy-MM-dd HH:mm:ss"))
```

- **성공**: `[RTO] stopwatch started at ...` 한 줄. 곧바로 3-1로 넘어간다(여기서 멈추면 대기 시간이 RTO에 섞인다).
- **측정 범위(정직 기술)**: 이 스톱워치가 재는 것은 **"백업 파일이 손에 있는 상태에서 복원 완료까지"**다. 실전 RTO는 여기에 ①장애 인지 시간 ②prod 컨테이너 재생성·구성 복원(§3-5) ③오프사이트에서 백업 회수·복호 시간이 더해진다. 그러므로 3-3b가 내는 값은 **RTO의 하한**이며, §5 표에도 그렇게 적는다 — 하한을 전체 RTO로 적으면 재해 시 복구 계획이 낙관 편향된다.

### 3-1. scratch 기동

```powershell
# [실행 시스템] Windows PowerShell (= Phaiakes9 이 PC, 진입 명령 불요)
cd C:\Users\kiki\Desktop\__AI\WhyMath
docker run -d --name whymath-restore-test -e POSTGRES_USER=whymath -e POSTGRES_DB=whymath -e POSTGRES_HOST_AUTH_METHOD=trust -p 127.0.0.1:55433:5432 pgvector/pgvector:pg16

# 자가검증: "accepting connections" 가 나와야 다음 단계 진행 (안 나오면 실패)
Start-Sleep -Seconds 5
docker exec whymath-restore-test pg_isready -U whymath -d whymath
```

- **성공**: `... accepting connections`. (변별력: 기동 실패·초기화 중이면 `no response`/오류가 나온다.)
- **실패 시 대처**: `docker logs whymath-restore-test`로 사유 확인(대개 55433 포트 충돌 또는 이름 중복 → `docker rm -f whymath-restore-test` 후 재시도).

### 3-2. 최신 백업 반입 + 복원

```powershell
# [실행 시스템] Windows PowerShell (= Phaiakes9 이 PC, 진입 명령 불요)
cd C:\Users\kiki\Desktop\__AI\WhyMath
$latest = Get-ChildItem C:\Users\kiki\Desktop\__AI\WhyMath-backups\* -Include *.dump,*.dump.age | Sort-Object LastWriteTime -Descending | Select-Object -First 1
Write-Host "restore target: $($latest.FullName)"

# 암호화본이면 복호본을 임시로 만든다 (리허설 종료 시 3-4에서 반드시 지운다)
if ($latest.Name.EndsWith(".age")) {
    $plain = Join-Path $env:TEMP "whymath-rehearsal.dump"
    age -d -i "$env:USERPROFILE\whymath-backup-identity.key" -o $plain $latest.FullName
    if ($LASTEXITCODE -ne 0) { Write-Host "[FAIL] age decrypt failed - wrong identity file?"; return }
} else {
    $plain = $latest.FullName
    Write-Host "[WARN] restoring a PLAINTEXT backup - see 1b (encryption not set up yet)"
}

docker cp $plain whymath-restore-test:/tmp/restore.dump
docker exec whymath-restore-test pg_restore -U whymath -d whymath --no-owner /tmp/restore.dump
```

> **복호본은 실데이터 평문 복제본이다** — §4-4가 scratch 컨테이너에 적용하는 규칙이 이 임시 파일에도 그대로 걸린다. 3-4의 폐기 단계가 이 파일을 지운다.


- **성공**: 무출력 종료(오류 0), 또는 말미 `errors ignored on restore: 1` 이하이면서 그 오류가 `schema "public" already exists` 뿐인 경우(pg15+ 덤프를 빈 DB에 복원할 때의 알려진 무해 오류). **테이블·데이터(COPY) 오류가 하나라도 있으면 실패.** 최종 판정은 어차피 3-3 행수 대조가 결정한다.
- **실패 시 대처**: 데이터 오류가 보이면 해당 백업 파일 불량 — 그 직전 백업 파일로 `$dump`를 바꿔(예: `Select-Object -Skip 1 -First 1`) 재시도하고, 반복되면 §1 백업을 즉시 재실행해 원인(디스크·덤프 단계)을 격리한다.

### 3-3. 무결성 검증 — 핵심 테이블 행수 대조 (prod ↔ scratch)

테이블명은 ORM 정본(`src/backend/whymath_backend/db/models/`) 실측: `atom_node`·`concept`·`problem`·`user_profile`·`dialogue`·`dialogue_turn`·`problem_attempt`·`parental_consent`.

```powershell
# [실행 시스템] Windows PowerShell (= Phaiakes9 이 PC, 진입 명령 불요)
cd C:\Users\kiki\Desktop\__AI\WhyMath
$q = "SELECT relname, n FROM (SELECT 'atom_node' AS relname, count(*) AS n FROM atom_node UNION ALL SELECT 'concept', count(*) FROM concept UNION ALL SELECT 'problem', count(*) FROM problem UNION ALL SELECT 'user_profile', count(*) FROM user_profile UNION ALL SELECT 'dialogue', count(*) FROM dialogue UNION ALL SELECT 'dialogue_turn', count(*) FROM dialogue_turn UNION ALL SELECT 'problem_attempt', count(*) FROM problem_attempt UNION ALL SELECT 'parental_consent', count(*) FROM parental_consent) t ORDER BY relname;"
Write-Host "--- prod (whymath-pg:5433) ---"
docker exec whymath-pg psql -U whymath -d whymath -c $q
Write-Host "--- scratch (restore-test:55433) ---"
docker exec whymath-restore-test psql -U whymath -d whymath -c $q
```

- **성공**: 두 표의 8개 행수가 **모두 일치**. (변별력: 복원이 누락·중단됐으면 scratch 쪽 행수가 다르거나 `ERROR: relation "..." does not exist`가 난다 — 후자는 복원 실패 확정.)
- **허용 편차(정직 기술)**: 백업 시점 이후 prod에 쓰기가 있었으면 활동 테이블(`dialogue_turn`·`problem_attempt` 등)은 prod ≥ scratch로 벌어질 수 있다. 이 경우 **콘텐츠 정본 3종(`atom_node`·`concept`·`problem`) 일치 + 나머지는 prod ≥ scratch 방향**이면 통과로 판정한다. 리허설은 가급적 유휴 시간(서버 미가동)에 수행.
- **실패 시 대처**: `relation does not exist` → 3-2 재수행. 행수 역전(scratch > prod) → 백업/복원 대상 컨테이너 혼동 의심 — 두 `docker exec` 대상 이름을 재확인.

### 3-3b. 스톱워치 정지 — RTO 하한 산출 (3-3 통과 직후 즉시)

**3-3의 행수 대조가 통과한 직후에 실행한다.** 통과하지 못했으면 그 회차는 RTO 측정 대상이 아니다 — 실패한 복구의 소요 시간은 복구 시간이 아니다.

```powershell
# [실행 시스템] Windows PowerShell — 3-0을 실행한 그 창에서 계속
cd C:\Users\kiki\Desktop\__AI\WhyMath
if (-not $sw) {
    Write-Host "[FAIL] stopwatch not found - 3-0을 실행한 창이 아니거나 창이 닫혔다. 이번 회차는 RTO 측정 불가(복원 검증 결과는 유효). 다음 리허설에서 3-0부터 다시 잰다."
} else {
    $sw.Stop()
    $mins = [math]::Round($sw.Elapsed.TotalMinutes, 1)
    Write-Host ("[RTO] restore-window elapsed = " + $mins + " min (" + $sw.Elapsed.ToString("hh\:mm\:ss") + ")")
    Write-Host "[RTO] 위 숫자를 세션에 전달하면 5절 표를 갱신한다."
}
```

- **성공**: `[RTO] restore-window elapsed = <숫자> min (hh:mm:ss)` 한 줄. **이 숫자를 세션에 그대로 전달**하면 §5 표의 RTO 칸과 게이트 evidence가 채워진다.
- **변별력**: 창이 바뀌었거나 3-0을 건너뛰었으면 `$sw`가 없어 `[FAIL]`이 나온다 — 0분이나 빈 값이 조용히 나오지 않는다. 이 경우에도 3-3까지의 **복원 성공 판정은 그대로 유효**하다(둘은 별개 사실이다). RTO만 다음 회차로 미룬다.
- **실패 시 대처**: `[FAIL]`이면 이번엔 RTO 없이 진행하고(3-4 폐기까지 정상 수행), 다음 리허설 때 3-0부터 한 창에서 수행한다.

### 3-4. scratch 폐기 (+ prod 구성 스냅샷 보관 권장)

```powershell
# [실행 시스템] Windows PowerShell (= Phaiakes9 이 PC, 진입 명령 불요)
cd C:\Users\kiki\Desktop\__AI\WhyMath
docker rm -f whymath-restore-test

# 복호본(있다면) 삭제 - 실데이터 평문 복제본을 남기지 않는다
Remove-Item (Join-Path $env:TEMP "whymath-rehearsal.dump") -ErrorAction SilentlyContinue
Test-Path (Join-Path $env:TEMP "whymath-rehearsal.dump")   # False 여야 함

# 자가검증: 빈 출력이어야 함 (이름이 출력되면 아직 남아 있음)
docker ps -a --filter "name=whymath-restore-test" --format "{{.Names}}"

# 권장: 실전 복구 대비 prod 컨테이너 구성(포트·볼륨 마운트) 스냅샷을 백업 디렉터리에 보관
docker inspect whymath-pg | Out-File -Encoding utf8 C:\Users\kiki\Desktop\__AI\WhyMath-backups\whymath-pg.inspect.json
```

- **성공**: 필터 출력이 빈 줄(컨테이너 완전 소멸 — 실데이터 복제본이 남지 않음).
- **실패 시 대처**: `docker rm -f whymath-restore-test` 재실행.

### 3-5. 실전 복구 (재해 발생 시)

절차는 리허설과 동일하되 대상만 다르다: 새 prod 컨테이너를 **5433**으로 재생성 → 3-2와 같은 `docker cp`+`pg_restore` → 3-3 검증(이때 비교 기준은 백업 당시 리허설 기록). **주의**: 재생성 전 반드시 3-4에서 보관한 `whymath-pg.inspect.json`으로 기존 볼륨 마운트·포트 구성을 확인하고 동일하게 재현한다 — 구성을 추측으로 재생성하지 않는다(환경 사실의 추론 등재 금지). 스냅샷이 없다면 리허설 §3을 한 번 수행해 먼저 확보한다.

---

## §4. PII·암호화 취급 규칙 — 백업 산출물은 민감정보다

`.dump` 파일은 **미성년 학생 데이터의 전체 복제본**이다. CLAUDE.md "학생 데이터는 민감 정보로 분류"가 백업 파일에도 그대로 적용된다.

### 덤프 내용물의 암호화 실태 (ORM 실측 — 정직 기술)

| 데이터 | 덤프 안 상태 | 근거 |
|---|---|---|
| `dialogue_turn.content`·`image_uri`·`image_analysis` (미성년 채팅·손글씨) | **봉투 암호화**(AES-256-GCM) 행은 `*_encrypted`+`*_nonce` 암호문으로 덤프됨. 마스터 키는 DB 밖(env `dialogue_content_encryption_key`) → **덤프 단독으로 복호 불가** | `db/models/dialogue.py` |
| 위 컬럼의 **과거/암호화 비활성 행** | dual-read 폴백 설계상 **평문**이 남아 있을 수 있음 — 덤프에 평문 대화가 포함될 수 있다고 *간주하고* 취급한다 | `db/models/dialogue.py` (content nullable·폴백 명시) |
| `device_credential.secret_*` | 동일 봉투 암호화(암호문 덤프) | `db/models/device.py` |
| `user_profile`의 `nickname`·`birth_year`·`gender`·`school_region`·`school_type`·`grade`·`target_universities` 등 | **평문**. 이메일은 원문이 아닌 `email_hash`·`parent_email_hash`(64자 해시)만 저장 | `db/models/user.py` |
| `parental_consent`·학습 활동(`problem_attempt`·`assessment` 등) | **평문** | `db/models/parental_consent.py` 외 |

즉 본문(대화·손글씨)은 앱 계층 암호화가 덮지만, **학적·프로필·활동 메타는 평문으로 덤프된다**. 특히 `school_type`+`school_region`+`grade`+`birth_year` 결합은 개인 식별 위험이 있다(CLAUDE.md 절대 금기: 학교·학년 정보로 개인 식별 가능한 노출 금지). 따라서:

### 취급 규칙 (의무)

1. **보관 위치 고정 + 반출 조건**: 백업 디렉터리(`C:\Users\kiki\Desktop\__AI\WhyMath-backups`)는 Phaiakes9 로컬을 기본으로 한다. **암호화되지 않은 산출물(`.dump`)은 클라우드 업로드·외부 공유·타 기기 복사 금지.** 오프사이트 사본은 **`.dump.age`(age 암호화본)만** 나갈 수 있고, 반출 전 아래 3건을 모두 만족해야 한다 — 절차는 §1b·§4-1a에 착지했다(OPS-31, 이전의 "절차 미도입" 상태 해소):
   - ⓐ `verify_encrypted_backup.py`가 **exit 0** (잠김 + 복원 가능 양방향 확인)
   - ⓑ 개인키가 반출 대상과 **다른 매체**에 있다(§4-5 — 같이 나가면 암호화가 무의미)
   - ⓒ Kiki 명시 승인 (게이트 `G-backup-offsite-move`)

### 4-1a. 반출 전 검증 (ⓐ의 실행)

```powershell
# [실행 시스템] Windows PowerShell (= Phaiakes9 이 PC, 진입 명령 불요)
cd C:\Users\kiki\Desktop\__AI\WhyMath
$art = Get-ChildItem C:\Users\kiki\Desktop\__AI\WhyMath-backups\*.dump.age | Sort-Object LastWriteTime -Descending | Select-Object -First 1
python scripts\backup\verify_encrypted_backup.py $art.FullName --identity "$env:USERPROFILE\whymath-backup-identity.key"
Write-Host "EXIT=$LASTEXITCODE"
```

- **성공**: `EXIT=0` + `① 잠김 ... OK` / `② 열림 ... OK` 두 줄.
- **변별력 3종**: 평문을 `.age`로 개명만 했으면 `not_encrypted`, 개인키가 틀리면 `decrypt_failed`, 산출물이 잘렸으면 역시 `decrypt_failed`로 각각 **exit 1**. 그리고 `age`·`pg_restore`가 없으면 **exit 2(판정 불가)** — "검사 못 함"이 "문제 없음"으로 위장되지 않는다.
- **실패 시 대처**: `EXIT=2`면 도구 부재이므로 §1b의 `winget install FiloSottile.age`를 먼저 하고 재실행한다. `EXIT=1`이면 **그 파일을 반출하지 않는다** — 사유 문면을 그대로 세션에 전달한다.
### 4-1b. 오프사이트 반출 실행 (ⓐⓑⓒ 충족 후 — 게이트 `G-backup-offsite-move`)

> **왜 이 절이 있는가**: §4-1은 반출 *조건* 3건(ⓐ검증 통과 ⓑ키 분리 ⓒKiki 승인)만 정하고 **반출 자체를 어떻게 하는지는 적지 않았다**. 조건만 있고 절차가 없으면 게이트는 "무엇을 하면 닫히는지"가 불명확한 채로 남는다 — 이 게이트가 22일 대기한 원인 중 하나다. 대상 목적지는 **클라우드 동기화 폴더**(2026-09-02 Kiki 결정).

**반출 대상은 `.dump.age`뿐이다.** `.dump`(평문)·`recipients.txt`는 나가도 되지만 개인키(`whymath-backup-identity.key`)는 **절대 같은 클라우드에 두지 않는다** — 같이 나가면 암호화가 무의미해지고, §4-5 키 분리가 성립하지 않는다. 클라우드 계정이 털리는 사태 하나로 미성년 PII 전량이 열리는 경로를 만들지 않는 것이 이 절의 전부다.

```powershell
# [실행 시스템] Windows PowerShell (= Phaiakes9 이 PC, 진입 명령 불요)
# 목적지 폴더 경로는 실제 동기화 폴더에 맞춰 아래 한 줄만 바꾼다 (이 블록의 첫 명령 인자 = 사람이 아는 값)
$Offsite = "$env:USERPROFILE\Google Drive\WhyMath-backups"

cd C:\Users\kiki\Desktop\__AI\WhyMath
New-Item -ItemType Directory -Path $Offsite -Force | Out-Null

# 평문·개인키가 섞여 나가지 않게 확장자를 명시 필터한다 (와일드카드 * 금지)
$src = Get-ChildItem "C:\Users\kiki\Desktop\__AI\WhyMath-backups\*.dump.age"
if (-not $src) {
    Write-Host "[FAIL] no .dump.age found - 1b 키쌍 생성과 백업 1회를 먼저 수행한다. 평문 .dump는 반출 대상이 아니다."
} else {
    Copy-Item $src.FullName -Destination $Offsite -Force
    Write-Host ("[OK] copied " + $src.Count + " encrypted artifact(s) to " + $Offsite)
}

# 자가검증 1: 목적지에 암호화본이 도착했고 크기가 원본과 같은가 (True 여야 함)
$a = Get-ChildItem "C:\Users\kiki\Desktop\__AI\WhyMath-backups\*.dump.age" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
$b = Get-ChildItem (Join-Path $Offsite $a.Name) -ErrorAction SilentlyContinue
($b -ne $null) -and ($b.Length -eq $a.Length)

# 자가검증 2: 개인키·평문이 목적지로 새지 않았는가 (둘 다 False 여야 함)
(Test-Path (Join-Path $Offsite "whymath-backup-identity.key"))
((Get-ChildItem $Offsite -Filter *.dump -ErrorAction SilentlyContinue) -ne $null)
```

- **성공**: `[OK] copied ...` + 자가검증 1이 `True` + 자가검증 2의 **두 줄이 모두 `False`**.
- **변별력**: 자가검증 1은 파일 존재가 아니라 **바이트 길이 일치**를 본다 — 동기화 중 잘린 사본은 존재하면서도 열리지 않으므로 `Test-Path`만으로는 구별되지 않는다. 자가검증 2는 이 절이 막으려는 사태(키 동반 유출·평문 반출)를 **직접 검사**한다.
- **실패 시 대처**: 자가검증 2가 하나라도 `True`면 **그 파일을 목적지에서 즉시 삭제**하고(`Remove-Item`), 클라우드 휴지통에서도 비운다 — 동기화 서비스는 삭제본을 30일 보관하는 경우가 많다.
- **동기화 완료 확인**: 복사는 로컬 폴더에 넣는 것까지이고, 실제 업로드는 클라우드 클라이언트가 한다. 트레이 아이콘이 "최신 상태"가 될 때까지 확인한다 — **폴더에 파일이 있다 ≠ 클라우드에 올라갔다**.

### 4-1c. 오프사이트 사본 주기적 검증 (반출은 1회가 아니다)

오프사이트 사본은 **회수해서 열어 본 적이 있을 때만** 백업이다. 분기 리허설(§3) 때 최신 백업 대신 **클라우드에서 내려받은 사본**으로 한 번 수행하면 반출 경로 전체(업로드→회수→복호→복원)가 검증된다. 이때도 개인키는 클라우드가 아니라 §1b의 별도 매체에서 가져온다.

2. **외부 도구 반입 금지**: 덤프 파일(또는 그 일부)을 LLM·SaaS·분석 도구에 업로드 금지 — "학생 풀이 데이터를 명시적 동의 없이 학습에 사용 금지" 금기의 백업판.
3. **보존 상한 = PIPA 파기 창**: 계정 삭제(잊힐 권리) 처리 후에도 그 학생의 데이터는 백업 안에 **최대 `RetentionDays`(기본 14일)** 잔존한다 → 파기 완료 시점은 "라이브 삭제 + RetentionDays 경과" 이후다(`deletion_audit` 기록과 함께 이 창을 파기 안내에 반영). `-RetentionDays`를 늘리면 이 잔존 창도 같이 늘어난다 — 연장은 이 트레이드오프를 인지하고 결정한다.
4. **리허설 복제본도 동급**: scratch 컨테이너는 실데이터 복제본이다 — 127.0.0.1 바인딩 유지, 리허설 종료 즉시 3-4로 폐기(볼륨 없음 = 잔존물 없음). 리허설 출력 캡처·스크린샷에 학생 행 데이터가 섞이지 않게 행수 집계만 공유한다.
5. **키 분리 유지**: 봉투 암호화 마스터 키(env)는 백업 디렉터리·덤프와 **같은 장소에 두지 않는다**(같이 유출되면 암호화가 무의미).

## §5. 운영 요약

| 항목 | 값 |
|---|---|
| 백업 주기 | 매일 04:00 (작업 스케줄러 · S4U 로그온 비의존) + 필요 시 §1 수동 |
| 산출물 암호화 | age 공개키 암호화(`.dump.age`) — 수신자 파일이 백업 디렉터리에 있으면 자동. 평문은 암호화 성공 후 삭제 |
| 키 보관 | 공개키 = 백업 디렉터리 `recipients.txt` / 개인키 = `%USERPROFILE%` + 별도 매체 사본(§1b) |
| 누락 감시 | `WhyMath-DB-Backup-Check` 태스크(매일 09:00) — `never_recorded`/`stale`/`plaintext_artifact`를 각각 다른 사유로 exit 1 + 알림 파일 |
| 보존 | 14일(`-RetentionDays`), 최신 1개는 무조건 보존 |
| 백업 소요 | 수 분 내(현 데이터 규모), 온라인 백업(pg_dump — prod 중단 불요) |
| 복구 리허설 | 분기 1회, §3 (약 10분) |
| RPO(허용 데이터 손실) | 마지막 백업 이후 ~ 최대 **24시간**(매일 1회 기준) — WAL/PITR 미도입 한계 |
| RTO(복구 소요) | **미측정** — 첫 리허설(게이트 `G-backup-restore-rehearsal`) §3-0/§3-3b 실측으로 이 칸을 채운다. 추정치를 적지 않는다. 기입 시 **측정 범위를 함께 적는다**: 리허설이 재는 것은 *백업 파일이 손에 있는 상태에서 복원 완료까지*(=RTO 하한)이며, 실전은 장애 인지·prod 재생성(§3-5)·오프사이트 회수가 더해진다 |

## §6. 미해결 사항 (정직 기술)

- **오프사이트 사본 부재(잔존)**: 백업이 여전히 prod와 같은 디스크에 있다 — 디스크 동시 소실에 무방비. **막던 원인 2건은 모두 해소됐다**: 반출 조건이던 암호화 절차가 §1b·§4-1a로, 반출 *절차 자체*가 §4-1b(클라우드)로 착지했다. 남은 것은 Kiki의 실행 1회다(게이트 `G-backup-offsite-move`). 목적지는 클라우드 동기화 폴더로 결정(2026-09-02) — 개인키는 동반 반출 금지(§4-5·§4-1b 자가검증 2가 검사).
- ~~**백업 파일 자체 암호화 미도입**~~ → **해소**(OPS-31): age 공개키 암호화가 백업 스크립트에 착지했고, 실패 시 평문을 남기지 않는 fail-closed다. 계약은 `tests/infra/test_backup_encryption.py`가 동결(뮤테이션 12종 전건 검출).
- ~~**스케줄 로그온 의존**~~ → **해소**(OPS-31): `register_backup_schedule.ps1`의 S4U + StartWhenAvailable. 등록 스크립트가 되읽기로 실제 `LogonType`을 판정한다.
- **WAL 아카이빙/PITR 없음**: pg_dump 스냅샷 방식 — 백업 사이 데이터는 유실 범위. OPS-31 범위 밖으로 명시 동결(acceptance ⑤).
- **RTO 미측정**: §5 참조 — 리허설 게이트가 열리기 전까지 복구 소요는 수치가 없다. 추정으로 채우지 않는다. **2026-09-02 정정**: 종전에는 §3에 시간 측정 스텝이 아예 없어 리허설을 완주해도 이 수치가 산출되지 않았다(절차가 못 내는 것을 게이트가 요구하던 상태) — §3-0·§3-3b 신설로 해소. 측정되는 것은 RTO 하한이며 실전 RTO는 그보다 크다.
- **암호화가 만든 새 단일 실패점**: 개인키를 잃으면 모든 `.dump.age`가 영구 복구 불가다. 대책은 키 사본뿐이며(§1b), 기계가 강제할 수 없는 구간이다 — 키 사본 존재 여부를 이 런북은 검증하지 못한다.
- **알림 도달성**: 검사 태스크가 만드는 것은 백업 디렉터리의 파일 하나다 — 누가 그 디렉터리를 볼 때만 보인다. 푸시·메일·중앙 로그는 `OPS-04`(로그 수집·알림) 범위이며 이 PR이 대신하지 않는다.
- **PS1 실행 검증 부재(구조적)**: `.ps1`은 Kiki 머신에서만 돌아 CI가 실행할 수 없다. 계약 테스트는 **텍스트 동결**이며 "그 문장이 있다"까지만 증명한다 — "의도대로 동작한다"는 §2-1·§4-1a의 자가검증 스텝이 담당한다.

---

*작성: 2026-07-26 (OPS-02-db-backup-dr) · 테이블명·암호화 실태는 `src/backend/whymath_backend/db/models/` 2026-07-26 실측.*
*개정: 2026-09-02 (게이트 2건 실행 준비 — §3-0/§3-3b RTO 측정 스텝 신설(리허설이 게이트 요구 수치를 산출하지 못하던 결함) · §4-1b/§4-1c 클라우드 오프사이트 반출 절차 신설(조건만 있고 절차 부재) · backup_whymath_pg.ps1의 존재하지 않는 절 참조 'section 4-2' → '1b' 정정 · §5 RTO 측정범위 명시 · §6 갱신).*
*개정: 2026-09-01 (OPS-31, PR #968 리뷰 반영: §2 검사 태스크 2개 등록·§2-2 자동 감시로 전환) — §1b 키쌍 생성 신설 · §2 로그온 비의존 스케줄로 전면 개정 · §2-2 누락 감시 신설 · §3-2/3-4 복호·폐기 반영 · §4-1 반출 조건 3건 + §4-1a 반출 전 검증 신설 · §5·§6 갱신.*
