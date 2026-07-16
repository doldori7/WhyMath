# 재부팅-후 백엔드 서버 기동 + shadow verdict 수집 런북 (Phaiakes9 / Windows)

> **목적**: Phaiakes9 재부팅 후, WhyMath 백엔드 서버를 로컬 기동하고 WH-1 하네스 **shadow verdict**
> (S1-11 flip 재판정 입력)를 수집하기까지의 환경설정을 원커맨드로 재현한다. 2026-07-16 세션에서
> 여러 함정(IPv6·asyncpg SSL·로깅 레벨·데모 DB 휘발)을 실측으로 규명해 확정한 절차다.
>
> **경계**: 로컬 시연 호스트 전용. `WHYMATH_DEMO_AUTH_ENABLED`·`WHYMATH_JWT_SECRET_KEY`는 로컬에서만
> 켠다(신원 검증 없는 데모 토큰 발급 — prod/공개 배포 절대 금지). shadow 관측은 비노출·무영속(로그 only).

---

## 재부팅으로 사라지는 것 vs 남는 것

| 남음 (재설정 불필요) | 사라짐 (매 재부팅 재설정) |
|---|---|
| 리포 클론·git 히스토리 | 실행 중이던 uvicorn 서버 |
| `src\backend\.venv` (설치된 패키지) | **Docker 컨테이너**(`whymath-demo-db`) |
| Docker Desktop *설치* | **세션-스코프 `$env:` 변수**(DB URL·JWT·shadow 플래그) |
| User-스코프 영구 env(키) — `[Environment]::SetEnvironmentVariable(...,"User")` | 터미널마다 venv/conda 활성화 |

→ 서버+shadow 모드는 **Docker 켜기 · git pull · venv 활성화 · 세션 env 4종 · 데모 DB 재기동 · INFO 런처**가
매번 필요하다. 아래 스크립트가 env·DB·런처를 한 번에 처리한다.

---

## 1. 최신 코드 + venv (새 PowerShell 창)

```powershell
cd C:\Users\kiki\Desktop\__AI\WhyMath
git checkout main
git pull origin main          # 보정 라우터(74/358)·게이트③ 봉인 등 최신 반영
cd src\backend
.\.venv\Scripts\Activate.ps1  # 차단 시: Set-ExecutionPolicy -Scope Process -Bypass 후 재시도
```

> 전제: Docker Desktop 실행 중(작업표시줄 고래 아이콘). `.venv`가 없으면(신규 PC) `scripts\demo\README.md` §A-1의
> `python -m venv .venv` + `pip install -e ".[dev]"`를 먼저 1회 수행.

## 2. 기동 스크립트 생성 (최초 1회 — 이후 재부팅엔 파일이 남아있으면 생략)

아래를 통째로 붙여넣어 `start_server_shadow.ps1`을 만든다(리포에 커밋되지 않는 로컬 생성물):

```powershell
@'
Set-Location "C:\Users\kiki\Desktop\__AI\WhyMath\src\backend"
Write-Host "1/6 기존 서버 정리..."
Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -like "*uvicorn*" -or $_.CommandLine -like "*run_server_verbose*" } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
Start-Sleep -Seconds 2
Write-Host "2/6 환경변수(세션 스코프)..."
# 데모 DB(호스트 55432)·?ssl=disable(Windows asyncpg SSL 협상 붕괴 회피)·shadow ON·데모 인증·런타임 JWT
$env:WHYMATH_DATABASE_URL = "postgresql+asyncpg://whymath@127.0.0.1:55432/whymath?ssl=disable"
$env:WHYMATH_WH1_HARNESS_SHADOW_ENABLED = "true"
$env:WHYMATH_DEMO_AUTH_ENABLED = "true"
$env:WHYMATH_JWT_SECRET_KEY = "local-dev-only-$(Get-Random)-$(Get-Random)"
Write-Host "3/6 데모 DB(Docker) 기동..."
docker compose -f ..\..\docker-compose.demo.yml up -d demo-db
$ok=$false; for($i=0;$i -lt 60;$i++){ docker compose -f ..\..\docker-compose.demo.yml exec -T demo-db pg_isready -U whymath -d whymath *> $null; if($LASTEXITCODE -eq 0){$ok=$true;break}; Start-Sleep 1 }
if(-not $ok){ Write-Host "X DB 준비 실패 (Docker Desktop 실행 확인)" -ForegroundColor Red; exit }
Write-Host "4/6 마이그레이션..."
alembic -c alembic.ini upgrade head
if($LASTEXITCODE -ne 0){ Write-Host "X 마이그레이션 실패" -ForegroundColor Red; exit }
Write-Host "5/6 INFO 로깅 런처 생성..."
# root logger를 INFO로 강제 — 안 하면 shadow 로그(.info)가 root 기본 WARNING에서 조용히 유실된다.
@"
import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(name)s %(message)s')
import uvicorn
uvicorn.run('whymath_backend.app:create_app', factory=True, host='0.0.0.0', port=8000)
"@ | Set-Content -Encoding utf8 run_server_verbose.py
Write-Host "6/6 서버 기동(백그라운드·로그 파일)..."
Remove-Item server_stdout.log, server_stderr.log -ErrorAction SilentlyContinue
$p = Start-Process python -ArgumentList "run_server_verbose.py" -PassThru -NoNewWindow -RedirectStandardOutput server_stdout.log -RedirectStandardError server_stderr.log
# 헬스체크는 127.0.0.1로 — localhost는 Windows에서 ::1(IPv6)로 풀려 IPv4 전용 0.0.0.0 바인딩에 못 붙는다.
$ok=$false; for($i=0;$i -lt 90;$i++){ Start-Sleep 1; try{ Invoke-RestMethod "http://127.0.0.1:8000/docs" -TimeoutSec 2 | Out-Null; $ok=$true; break }catch{} }
if($ok){ Write-Host "OK 서버 준비 완료 (PID $($p.Id))" -ForegroundColor Green } else { Write-Host "X 기동 실패:" -ForegroundColor Red; Get-Content server_stderr.log -Tail 40 }
'@ | Set-Content -Encoding utf8 start_server_shadow.ps1
```

## 3. 매 재부팅 실행 (서버 기동)

```powershell
.\start_server_shadow.ps1
```

`OK 서버 준비 완료 (PID …)`가 뜨면 서버가 백그라운드로 돈다. 실패 시 화면의 stderr tail이 원인을 보여준다.

## 4. shadow verdict 수집 (같은 창)

verify를 실제로 트리거하려면 `solution_steps`를 반드시 동봉한다(없으면 verify 미호출 → verdict 전부 None).

```powershell
$login = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/v1/auth/demo/callback" `
    -ContentType "application/json" -Body '{"code":"x","redirect_uri":"http://localhost/callback"}'
$headers = @{ Authorization = "Bearer $($login.access_token)" }

# 표현식 동치 배치(correct/incorrect 분리 관측) — 2번째는 의도적 오전개(incorrect 검출 확인용)
$s = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/v1/coach/sessions" -Headers $headers `
    -ContentType "application/json" `
    -Body (@{ student_input="식을 전개했어요"; student_solution="x^2 - 5*x + 6"; solution_steps=@("(x - 2)*(x - 3)","x^2 - 5*x + 6") } | ConvertTo-Json)
$did = $s.dialogue_id
$batches = @(
    @("(x + 1)*(x + 4)", "x^2 + 5*x + 4"),
    @("(x + 1)*(x + 2)", "x^2 + 3*x + 1"),
    @("(2*x - 1)*(x + 3)", "2*x^2 + 5*x - 3")
)
foreach ($p in $batches) {
    Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/v1/coach/sessions/$did/turns" -Headers $headers `
        -ContentType "application/json" -Body (@{ student_input="이것도 전개했어요"; student_solution=$p[-1]; solution_steps=$p } | ConvertTo-Json) | Out-Null
    Start-Sleep -Seconds 2
}
Start-Sleep -Seconds 30   # shadow는 백그라운드 LLM 루프 — 완료 대기
Select-String -Path server_stderr.log -Pattern "wh1_shadow.record"
```

출력의 `"verify_verdict":"correct|incorrect|unverifiable"`가 S1-11 판정 입력이다. 방정식 변형 체인은
`verify_step` 한계로 unverifiable가 정상(트래픽 모양이 verdict를 결정). 결과를 회신하면 서기가
`docs/strategy/live_cost_measurement_2026-07.md` verdict 표에 누적한다.

## 5. 정리 (작업 종료 시)

```powershell
Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" | Where-Object { $_.CommandLine -like "*run_server_verbose*" } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
docker compose -f ..\..\docker-compose.demo.yml down
```

---

## 함정표 (전부 2026-07-16 세션 실측)

| 증상 | 원인·해결 |
|---|---|
| 요청이 "원격 서버에 연결할 수 없습니다"인데 서버 로그는 정상 기동 | `localhost`가 Windows에서 `::1`(IPv6)로 풀림 · uvicorn `0.0.0.0`은 IPv4 전용 → **클라 URL을 `127.0.0.1`로** |
| `alembic`/서버 500 `ConnectionError: unexpected connection_lost()` | Windows asyncpg SSL 협상 붕괴 → DB URL에 **`?ssl=disable`**(데모 DB는 trust auth라 안전) |
| shadow 로그가 `Select-String`에 안 잡힘 | 두 로거가 root WARNING 상속 → `.info` 유실. **`logging.basicConfig(level=INFO)` 런처로 기동**(uvicorn `--log-level info`론 안 됨 — root 미변경) |
| 서버 500 `RuntimeError: JWT 시크릿 미설정` | `WHYMATH_JWT_SECRET_KEY` 세션 env 누락(재부팅으로 휘발) → 스크립트 2단계가 런타임 생성 |
| `port is already allocated`(5432) | 데모는 호스트 **55432**로 격리됨(`docker-compose.demo.yml`) — 그래도 나면 `docker compose -f docker-compose.demo.yml down` 후 재시도 |
| 서버는 떴는데 `$dialogueId`가 이전 값 그대로 | 요청 실패로 변수 미갱신(이전 값 잔존) — 실제 원인은 위 항목 중 하나. 서버 로그 tail 확인 |

## 관련 문서
- `scripts/demo/README.md` — 실기기 시연(FVM/Flutter·패드) 전체 런북
- `docs/strategy/s1_exit_gate_judgement_2026-07.md` — S1 탈출 게이트 판정(게이트 ② 재측정 명령 포함)
- `docs/strategy/live_cost_measurement_2026-07.md` — 라이브 비용·verify verdict 실측 기록
