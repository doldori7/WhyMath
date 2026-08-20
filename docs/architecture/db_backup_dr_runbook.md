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

## §0. 사전 준비 — 브랜치 체크아웃 (미머지 브랜치 신규 파일)

백업 스크립트는 미머지 브랜치에 있다. 재시작(force-push) 가능성이 있으므로 `fetch` + `checkout -B` 형식만 사용한다(pull 금지 — diverged 시 add/add 충돌).

```powershell
# [실행 시스템] Windows PowerShell (= Phaiakes9 이 PC, 진입 명령 불요)
cd C:\Users\kiki\Desktop\__AI\WhyMath
git fetch origin
git checkout -B claude/whymath-service-review-9r21im origin/claude/whymath-service-review-9r21im

# 자가검증: 스크립트 실재 확인 - True 여야 함
Test-Path .\scripts\backup\backup_whymath_pg.ps1
```

- **성공**: `Test-Path`가 `True`. (변별력: 이 파일은 이 브랜치에만 있어 체크아웃 실패 시 실제로 `False`가 나온다.)
- **실패 시 대처**: `git branch --show-current`로 현재 브랜치 확인 후 위 `git fetch`+`checkout -B` 두 줄 재실행.

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

## §2. 정기 스케줄 등록 — Windows 작업 스케줄러 (주 2회: 월·목 09:00)

```powershell
# [실행 시스템] Windows PowerShell (= Phaiakes9 이 PC, 진입 명령 불요)
cd C:\Users\kiki\Desktop\__AI\WhyMath
schtasks /Create /F /TN "WhyMath-PG-Backup" /SC WEEKLY /D MON,THU /ST 09:00 /TR "powershell.exe -NoProfile -ExecutionPolicy Bypass -File C:\Users\kiki\Desktop\__AI\WhyMath\scripts\backup\backup_whymath_pg.ps1"

# 자가검증 1: 스케줄 존재 - 표에 WhyMath-PG-Backup 행이 나와야 함 (없으면 ERROR 출력)
schtasks /Query /TN "WhyMath-PG-Backup"

# 자가검증 2: 1회 수동 트리거 후 산출물 확인 (등재 직후 실동작 검증 - 의무)
schtasks /Run /TN "WhyMath-PG-Backup"
Start-Sleep -Seconds 90
Get-ChildItem C:\Users\kiki\Desktop\__AI\WhyMath-backups\*.dump |
  Sort-Object LastWriteTime -Descending |
  Select-Object -First 1 Name, Length, LastWriteTime

# 자가검증 3: 마지막 실행 결과 코드 - "Last Result: 0" 이어야 함 (0 이외 = 실패)
schtasks /Query /TN "WhyMath-PG-Backup" /V /FO LIST | Select-String "Last Result"
```

- **성공**: 자가검증 1에 작업 행 표시, 자가검증 2의 최신 `.dump`가 방금 시각 + `Length > 0`, 자가검증 3이 `0`. (변별력: 트리거된 스크립트가 실패하면 새 파일이 안 생기고 Last Result가 1이 된다 — 종료코드 0/1 계약이 스케줄러 판정으로 그대로 전파된다.)
- **실패 시 대처**: 자가검증 3이 0이 아니면 같은 명령을 §1처럼 창에서 직접 실행해 `[FAIL]` 사유를 눈으로 확인한다.
- **한계(정직 기술)**: 기본 등록은 *로그온 세션에서만* 실행된다 — PC가 꺼져 있거나 로그아웃 상태면 그 회차는 건너뛴다. 놓친 주는 §1 수동 실행으로 보충한다. (SYSTEM 계정 등록은 관리자 권한 + Docker 접근 구성이 더 필요해 현 단계 미채택 — §6 미해결.)

## §3. 복구 리허설 (분기 1회 권장) — scratch 컨테이너 복원 + 무결성 검증

일회용 scratch 컨테이너(pgvector/pg16)를 **포트 55433**에 띄워 최신 백업을 복원한다. 55433은 5432(타 프로젝트)·5433(prod)·55432(demo)와 비충돌. 127.0.0.1 바인딩으로 외부 비노출(실데이터 복제본 — §4 취급 규칙 적용).

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
$dump = Get-ChildItem C:\Users\kiki\Desktop\__AI\WhyMath-backups\*.dump | Sort-Object LastWriteTime -Descending | Select-Object -First 1
Write-Host "restore target: $($dump.FullName)"
docker cp $dump.FullName whymath-restore-test:/tmp/restore.dump
docker exec whymath-restore-test pg_restore -U whymath -d whymath --no-owner /tmp/restore.dump
```

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

### 3-4. scratch 폐기 (+ prod 구성 스냅샷 보관 권장)

```powershell
# [실행 시스템] Windows PowerShell (= Phaiakes9 이 PC, 진입 명령 불요)
cd C:\Users\kiki\Desktop\__AI\WhyMath
docker rm -f whymath-restore-test

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

1. **보관 위치 고정**: 백업 디렉터리(`C:\Users\kiki\Desktop\__AI\WhyMath-backups`)는 Phaiakes9 로컬에만 둔다. **파일 단위 암호화 없이 클라우드 업로드·외부 공유·타 기기 복사 금지.** 오프사이트 사본이 필요하면 파일 암호화(7-Zip AES-256 또는 age) + Kiki 명시 승인 후에만 이동한다 — 구체적 절차는 §7.
2. **외부 도구 반입 금지**: 덤프 파일(또는 그 일부)을 LLM·SaaS·분석 도구에 업로드 금지 — "학생 풀이 데이터를 명시적 동의 없이 학습에 사용 금지" 금기의 백업판.
3. **보존 상한 = PIPA 파기 창**: 계정 삭제(잊힐 권리) 처리 후에도 그 학생의 데이터는 백업 안에 **최대 `RetentionDays`(기본 14일)** 잔존한다 → 파기 완료 시점은 "라이브 삭제 + RetentionDays 경과" 이후다(`deletion_audit` 기록과 함께 이 창을 파기 안내에 반영). `-RetentionDays`를 늘리면 이 잔존 창도 같이 늘어난다 — 연장은 이 트레이드오프를 인지하고 결정한다.
4. **리허설 복제본도 동급**: scratch 컨테이너는 실데이터 복제본이다 — 127.0.0.1 바인딩 유지, 리허설 종료 즉시 3-4로 폐기(볼륨 없음 = 잔존물 없음). 리허설 출력 캡처·스크린샷에 학생 행 데이터가 섞이지 않게 행수 집계만 공유한다.
5. **키 분리 유지**: 봉투 암호화 마스터 키(env)는 백업 디렉터리·덤프와 **같은 장소에 두지 않는다**(같이 유출되면 암호화가 무의미).

## §5. 운영 요약

| 항목 | 값 |
|---|---|
| 백업 주기 | 주 2회(월·목 09:00, 작업 스케줄러) + 필요 시 §1 수동 |
| 보존 | 14일(`-RetentionDays`), 최신 1개는 무조건 보존 |
| 백업 소요 | 수 분 내(현 데이터 규모), 온라인 백업(pg_dump — prod 중단 불요) |
| 복구 리허설 | 분기 1회, §3 (약 10분) |
| RPO(허용 데이터 손실) | 마지막 백업 이후 ~ 최대 3~4일(주 2회 기준) — WAL/PITR 미도입 한계 |
| RTO(복구 소요) | 리허설 실측 기준 기록(첫 리허설 후 이 표를 갱신) |
| 오프사이트 사본 | §7 스크립트 + Kiki 실행 후 `G-backup-offsite-move` clear |

## §7. 오프사이트(NAS) 사본 이동 — SPOF 부분 상환

> 목적: 로컬 백업(`C:\Users\kiki\Desktop\__AI\WhyMath-backups`)과 prod DB가 같은 물리 머신·같은 디스크에 있어 디스크 장애 시 동시 소실되는 SPOF를 부분적으로 상환한다. NAS는 내부 신뢰 구역의 별도 저장소를 가정한다.
> 전제: NAS 경로가 이미 마운트·접근 가능하고, **prod DB 서버/백업 디렉터리와 물리적으로 다른 장치**에 있다. NAS가 인터넷 공유·제3자 클라우드라면 §7-5 암호화를 **의무**로 적용한다.

### 7-1. 수동 이동 1회

스크립트: `scripts/backup/move_backup_to_nas.ps1`. ASCII 전용 — 한국어 설명은 이 런북에만 있다.

```powershell
# [실행 시스템] Windows PowerShell (= Phaiakes9 이 PC, 진입 명령 불요)
cd C:\Users\kiki\Desktop\__AI\WhyMath
Set-ExecutionPolicy -Scope Process -Bypass -Force
.\scripts\backup\move_backup_to_nas.ps1 -NasPath "\\YOUR_NAS\share\whymath-backups"

# 자가검증 1: 종료코드 - True 여야 함
$LASTEXITCODE -eq 0

# 자가검증 2: NAS에 최신 .dump 2개 존재 + 크기 > 0
Get-ChildItem "\\YOUR_NAS\share\whymath-backups\*.dump" |
  Sort-Object LastWriteTime -Descending |
  Select-Object -First 2 Name, Length, LastWriteTime

# 자가검증 3: 해시 일치 (스크립트 내부 검증 출력과 독립적으로 1건 직접 확인)
$local = Get-ChildItem C:\Users\kiki\Desktop\__AI\WhyMath-backups\*.dump |
  Sort-Object LastWriteTime -Descending | Select-Object -First 1
$nas = Get-ChildItem "\\YOUR_NAS\share\whymath-backups\$($local.Name)"
$lh = Get-FileHash $local.FullName -Algorithm SHA256
$nh = Get-FileHash $nas.FullName -Algorithm SHA256
$lh.Hash -eq $nh.Hash
```

- **성공**: `[OK] offsite copy complete: copied=N skipped=M ...` 출력, 자가검증 1이 `True`, 자가검증 2의 파일 크기 `> 0`, 자가검증 3이 `True`.
- **변별력**: 스크립트는 호스트 회수 전이 아니라 NAS 도달 **후** SHA-256으로 다시 검증한다. 복사 중 손상·네트워크 끊김은 해시 불일치로 `[FAIL]` + 종료코드 1이 된다.
- **실패 시 대처**: `[FAIL]` 사유 확인 → NAS 접근(`Test-Path`) → 용량 → 재실행. 해시 불일치면 해당 파일만 삭제 후 재실행(스크립트가 `Copy-Item -Force`로 덮어쓴다).
- **KeepCount**: 기본값 2. 더 많이/적게 옮기려면 `-KeepCount N`.

### 7-2. 파일 단위 암호화 (NAS가 외부/클라우드이거나 추가 보호가 필요할 때)

§4-1의 "파일 단위 암호화 없이 클라우드 업로드·외부 공유·타 기기 복사 금지"를 준수하기 위해, NAS가 내부가 아니거나 정책상 암호화를 요구하면 7-Zip AES-256으로 `.7z`를 만든 뒤 이동한다.

```powershell
# [실행 시스템] Windows PowerShell (= Phaiakes9 이 PC, 진입 명령 불요)
$7z = "C:\Program Files\7-Zip\7z.exe"
$dump = Get-ChildItem C:\Users\kiki\Desktop\__AI\WhyMath-backups\*.dump |
  Sort-Object LastWriteTime -Descending | Select-Object -First 1
$archive = Join-Path C:\Users\kiki\Desktop\__AI\WhyMath-backups "$($dump.BaseName).7z"

# 대화형으로 강력한 암호 입력 (화면에 표시되지 않음)
& $7z a -t7z -mhe=on -p $archive $dump.FullName

# 자가검증: 목록 + 해제 테스트 (임시 폴더, 복원 직후 삭제)
& $7z t $archive
```

- **주의**: 7-Zip 대화형 `-p`는 배치/스케줄러에서 사용 불가. 자동화하려면 키 관리(Windows DPAPI, HashiCorp Vault 등)가 선행돼야 하며, 평문 비밀번호를 스크립트에 하드코딩하면 금지다. 현재는 수동 게이트용 대화형 절차만 제공한다.
- **이동**: 암호화된 `.7z`를 `move_backup_to_nas.ps1`의 `-BackupDir`로 지정하면 된다(스크립트는 `.dump`만 선택한다 — 필요 시 `-Filter` 확장은 별도 태스크).

### 7-3. 정기 이동 스케줄 등록 (선택)

§2 백업 스케줄 직후에 NAS 이동을 붙인다. 로그온 세션 의존은 §2와 동일.

```powershell
# [실행 시스템] Windows PowerShell (= Phaiakes9 이 PC, 진입 명령 불요)
cd C:\Users\kiki\Desktop\__AI\WhyMath
schtasks /Create /F /TN "WhyMath-PG-Backup-Offsite" /SC WEEKLY /D MON,THU /ST 09:30 /TR "powershell.exe -NoProfile -ExecutionPolicy Bypass -File C:\Users\kiki\Desktop\__AI\WhyMath\scripts\backup\move_backup_to_nas.ps1 -NasPath \"\\YOUR_NAS\share\whymath-backups\""

# 자가검증 1~3은 7-1과 동일
schtasks /Query /TN "WhyMath-PG-Backup-Offsite"
```

### 7-4. 게이트 clear 증적

`G-backup-offsite-move` clear 시 evidence 예시:

```bash
python3 scripts/harness/backlog.py gates clear G-backup-offsite-move --evidence "NAS offsite copy completed. Host: Phaiakes9, NAS path: \\YOUR_NAS\share\whymath-backups, files copied: 2, verification: SHA-256 matched for all files, latest dump: whymath_YYYYMMDD_HHMMSS.dump (N bytes)."
```

## §6. 미해결 사항 (정직 기술)

- **오프사이트 사본 절차 도입, 실행 미완료**: NAS 이동 스크립트·검증·런북 §7은 확립됐다. 실제 사본 이동 및 `G-backup-offsite-move` clear는 Kiki가 NAS 경로를 확정하고 7-1을 실행한 뒤 완료한다.
- **백업 파일 자체 암호화 선택 절차만 도입**: §7-2에 7-Zip AES-256 대화형 절차가 있다. 키 관리·자동화는 미도입 — 외부/클라우드 NAS 사용 시 반드시 7-2를 적용하고, 키 보관은 백업 파일과 분리한다(§4-5).
- **WAL 아카이빙/PITR 없음**: pg_dump 스냅샷 방식 — 백업 사이 데이터는 유실 범위.
- **스케줄 로그온 의존**: §2 한계 참조(로그아웃/꺼짐 시 회차 누락).

---

*작성: 2026-07-26 (OPS-02-db-backup-dr) · 테이블명·암호화 실태는 `src/backend/whymath_backend/db/models/` 2026-07-26 실측.*
