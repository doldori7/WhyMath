# S3-01 파일럿 운영 런북 — 실학생 코호트 노출 + KPI 베이스라인 기록

> **대상**: Kiki(Phaiakes9 = Windows PowerShell). **목적**: S3-01(파일럿 코호트 5~10명 모집·운영)의
> 기술 운영 절차를 한 장으로. 앱 기동은 `/demo-doctor` 카탈로그, KPI 계측은 S3-04 하네스를 조립한다.
> **이 런북의 모든 명령은 실측 검증됨**(scripts/demo/run_demo.ps1·harness/pilot_kpi_baseline.py 기준).
>
> ⚠️ **선결 결정(§0)은 확정됨** — 파일럿 데이터는 **전용 영속 DB(옵션 A·`whymath-pilot-db`·5434)** 에 둔다.
> §1은 그 값이 채워진 명령으로 확정되어 있다.

---

## 0. 파일럿 데이터 DB — 확정: 전용 영속 DB (옵션 A)

파일럿 KPI(리텐션·숙달 델타)는 **여러 세션에 걸친 영속 데이터**가 필요하다. 데모 스택 기본 DB는
*일회용*(`stop_demo` 시 볼륨째 소멸)이라 쓸 수 없고, prod DB는 데모 시드가 섞여 오염된다. 그래서
**격리된 영속 DB를 신설**한다(Kiki 확정 2026-07-26):

| 옵션 | DB | 지속성 | 판정 |
|---|---|---|---|
| **✅ A. 전용 파일럿 DB (채택)** | `whymath-pilot-db`(호스트 **5434**·named volume) | ✅ 영속·격리 | prod 오염 0·데모 소멸 0. `docker-compose.pilot.yml` 1개로 셋업 |
| B. prod 오버라이드 | `whymath-pg`(5433) | ✅ 영속 | 데모 시드가 prod에 섞임 — 미채택 |
| C. 데모 기본 | `whymath-demo-db`(55432) | ❌ `stop_demo` 시 소멸 | 다세션 KPI 불가 — 미채택 |

전용 DB 정의는 리포에 커밋된 `docker-compose.pilot.yml`(pgvector/pg16·5434·named volume
`whymath_pilot_pgdata`·127.0.0.1 전용·trust). §1이 이 DB를 **run_demo보다 먼저** 띄우고, run_demo에
`WHYMATH_DEMO_DATABASE_URL`로 그 DB를 물린다.

> **왜 "먼저"인가(실측)**: `run_demo.ps1`은 `WHYMATH_DEMO_DATABASE_URL` 오버라이드가 있어도
> **컨테이너는 여전히 데모(55432)만 띄우고** 오버라이드는 *연결 문자열*(alembic·uvicorn)만 바꾼다.
> 즉 파일럿 DB(5434)를 run_demo가 대신 띄워주지 않으므로, **파일럿 DB가 먼저 healthy 상태여야**
> `alembic upgrade head`가 5434에 붙는다. 안 그러면 connection-refused로 기동 실패.
> (`stop_demo`는 데모 compose만 `down -v`하므로 파일럿 DB는 안전하게 살아남는다.)

---

## 1. 백엔드 기동 — 창 ① (서버 점유·이후 조작 금지)

```powershell
# [Phaiakes9 = Windows PowerShell · 리포 루트]
cd C:\Users\kiki\Desktop\__AI\WhyMath\WhyMath
git pull

# (1-a) 파일럿 전용 영속 DB 기동 — run_demo보다 반드시 먼저. 볼륨 보존(다세션 KPI).
docker compose -f docker-compose.pilot.yml up -d
# 헬시 대기(자가검증): "healthy"가 뜨면 준비 완료. 최대 ~1분.
docker inspect --format='{{.State.Health.Status}}' whymath-pilot-db

# (1-b) run_demo에 파일럿 DB를 물린다(연결 문자열 오버라이드). 값 확정 — 그대로 실행.
$env:WHYMATH_DEMO_DATABASE_URL = "postgresql+asyncpg://whymath@127.0.0.1:5434/whymath?ssl=disable"

# (1-c) 백엔드 기동(파일럿 DB에 alembic·문제 시드·uvicorn).
.\scripts\demo\run_demo.ps1
```

- (1-a) **자가검증**: `docker inspect ...`가 `healthy`를 출력하면 파일럿 DB 준비 완료. `starting`이 계속되면
  몇 초 뒤 재실행, `unhealthy`/오류면 Docker Desktop 가동 확인 후 `docker compose -f docker-compose.pilot.yml logs pilot-db`.
- run_demo는 **(데모 컨테이너 55432도 뜨지만 무시) → alembic upgrade head[→5434] → 문제 코퍼스 시드[→5434] → uvicorn(0.0.0.0:8000)[→5434] → 데모 토큰·LAN IP 출력**을 수행한다.
- ⚠️ **이 창은 서버가 점유한다 — 이후 다른 명령을 여기 붙여넣지 말 것.** `Ctrl+C`는 복사가 아니라 **서버 중단** 신호다. 후속(§2·§3)은 반드시 **새 창**에서.
- **자가검증(성공 신호)**: 마지막 상자에 `flutter run --dart-define=API_URL=http://<LAN IP>:8000 --dart-define=DEMO_TOKEN=<토큰>` 명령이 **값이 채워진 채** 출력되면 기동 성공. 안 뜨거나 오류면 → `/demo-doctor` §B(Docker/alembic) 표.

## 2. 앱 실기기 구동 — 창 ② (기기 USB·같은 WiFi)

```powershell
# [Phaiakes9 · 새 창 · 앱 폴더]
cd C:\Users\kiki\Desktop\__AI\WhyMath\WhyMath\src\mobile
$env:PATH = "$env:LOCALAPPDATA\Pub\Cache\bin;$env:PATH"   # fvm PATH(새 창마다·주석 아님)
fvm flutter pub get
fvm dart run build_runner build --delete-conflicting-outputs

# ▼ 창①이 출력한 '값이 채워진' 줄을 통째로 복사(자리표시 <...> 직접 타이핑 금지)
fvm flutter run --dart-define=API_URL=http://<창①출력 IP>:8000 --dart-define=DEMO_TOKEN=<창①출력 토큰>
```

- **자가검증**: 기기에 앱이 뜨고 문제가 로드되면 성공. "문제를 불러오지 못했어요"면 → `/demo-doctor` §D 첫 행(API_URL 부분복사·방화벽·**토큰 로테이션**: run_demo 재실행 시 이전 토큰 즉시 무효 → 항상 *최근* 출력에서 복사).
- 기기 미인식·빌드 실패 → `/demo-doctor` §C(Flutter/빌드)·§D 표. 1차 처방은 항상 `git pull` 후 재시도.

## 3. 학생 세션 진행 (파일럿 코호트)

학생-대면 코치는 **S1 결정론 Polya 비계**(LLM 미호출)다. 한 세션 완주 흐름(정본 대본:
`docs/architecture/s1_e2e_demo_script.md`):

1. 진단 → 약개념 도출 → 문제 제시.
2. **UNDERSTAND 전이**: "이 문제 같이 읽어볼까?"엔 **자기 언어 재진술**로 답해야 넘어간다 —
   20자↑ + 마침표/물음표/쉼표 1개 이상(예: "주어진 건 ...이고, 구할 건 ...이야."). 수식·단답은 미인정.
3. Polya 계획·실행 비계 2~3턴 → **풀이 제출**.
4. **검증 카드 완주 신호**: 카드("스스로 검산해볼까?")는 *실제 계산 오류 감지 시에만* 뜬다. 확인하려면
   순수 숫자 오류 1줄 포함 제출(예: `4 / 2 = 3`) → 색 다른 카드형 박스 출력 = 완주선.

(코치 반복·카드 미출력 등은 대부분 **버그가 아니라 설계된 S1 범위** — `/demo-doctor` §D 참조.)

## 4. KPI 베이스라인 기록 — 창 ③ (S3-04 하네스)

세션들이 쌓인 뒤(또는 파일럿 기간 종료 시) 5개 핵심 KPI 베이스라인을 **하나의 구조화 리포트**로 낸다.
**§1과 동일한 파일럿 DB(5434)** 를 봐야 하므로 같은 URL을 `WHYMATH_DATABASE_URL`에 지정한다.

```powershell
# [Phaiakes9 · 새 창 · src\backend · venv 활성]
cd C:\Users\kiki\Desktop\__AI\WhyMath\WhyMath\src\backend
.\.venv\Scripts\Activate.ps1
# §1과 동일한 파일럿 DB를 봐야 한다(값 확정 — 그대로 실행).
$env:WHYMATH_DATABASE_URL = "postgresql+asyncpg://whymath@127.0.0.1:5434/whymath?ssl=disable"

python -m whymath_backend.harness.pilot_kpi_baseline --cost-days 7
```

- **산출 KPI 5종**(각 MEASURED 값 또는 NO_DATA 사유·정직 표기): ① 학습성과(숙달 델타) ② 재사용/리텐션
  ③ 정서안전(톤 위반 — 현재 아키텍처상 NO_DATA: 결정론 coach라 위반 발화 자체 0) ④ 세션비용 P&L
  (코호트 LLM 비용만 재는 PARTIAL·per-session NO_DATA) ⑤ 입력 verify 커버리지.
- 옵션: `--since/--until`(집계 구간)·`--user-id`(개별 학생)·`--shadow-ledger <경로>`(KPI⑤ 커버리지 산출에 필요).
- **자가검증**: 리포트에 5개 KPI 행이 각각 MEASURED/NO_DATA/PARTIAL로 찍히면 성공. 전부 NO_DATA면
  DB 연결(§0 결정)·세션 데이터 유무를 먼저 확인(빈 통과 위장 아님 — 정직 표기 설계).

## 5. 성공 기준 (S3-01 acceptance) + 정리

- **성공** = 코호트(5~10명) 세션 운영 + §4 KPI 베이스라인 리포트에 **측정 가능 KPI가 MEASURED로 기록**됨.
  (NO_DATA 항목은 "무엇을 만들면 재는지"가 리포트 note에 명시된다 — 후속 과제 신호.)
- 정리(2단계·파일럿 DB는 영속이라 데모와 다르다):
  - **백엔드/데모 스택 종료**: 창①에서 `Ctrl+C` 후 `.\scripts\demo\stop_demo.ps1` — uvicorn 종료 + *데모*
    컨테이너(55432)만 볼륨째 제거한다. **파일럿 DB(5434)는 건드리지 않는다**(별도 compose).
  - **파일럿 DB**: 데이터 보존 정지는 `docker compose -f docker-compose.pilot.yml down`(볼륨 유지 —
    다음 세션에 이어서 KPI 누적). 파일럿 완전 종료·데이터 폐기는 `... down -v`(볼륨째 소멸 — 신중히).
- 게이트 기록(선택): S3-01 완료 시 harness `done` + 증적. (파일럿 착수/모집 판단 자체는 Kiki 소유.)

---

## 참조
- 파일럿 전용 영속 DB 정의: `docker-compose.pilot.yml`(5434·named volume·§0 채택)
- 앱 기동·트러블슈팅 카탈로그: `/demo-doctor` (또는 이 파일 옆 `README.md` §A)
- 세션 대본: `docs/architecture/s1_e2e_demo_script.md`
- KPI 하네스 설계: `src/backend/whymath_backend/harness/pilot_kpi_baseline.py` 헤더
- 인간 병목 현황: `docs/strategy/human_bottleneck_status_2026-07-26.md`
