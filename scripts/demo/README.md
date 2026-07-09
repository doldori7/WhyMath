# S1 실기기 학습 루프 시연 — 따라하기 런북 (Phaiakes9)

> **목적**: S1 탈출 게이트 ①(`G-kiki-device-demo` — "실기기(패드)에서 1루프 15분 완주 시연 녹화")을
> Kiki가 그대로 따라 하며 촬영할 수 있게, 녹화 전 하드 블로커 3종(인증·API_URL·LLM 키)을 원커맨드로
> 해소하는 인에이블먼트 킷 사용법이다. 호스트 OS별로 **Windows(PowerShell)** 경로(§A)와
> **리눅스/WSL**(bash) 경로(§B)를 모두 제공한다. Kiki의 Phaiakes9(라이젠 AI Max+ 395)가
> Windows면 §A를 따르면 된다.
>
> **경계**: 이 킷은 녹화를 *turnkey*로 만들 뿐 **게이트를 clear하지 않는다** — 게이트는 Kiki가 실기기
> 15분 루프를 *녹화*할 때까지 PENDING이다. 대본은 `docs/architecture/s1_e2e_demo_script.md`.

---

## 큰 그림

```
[Phaiakes9]  run_demo.sh  →  PG + 서버 기동 + 데모 토큰 발급  →  "flutter run ..." 명령 출력
     │                                                                       │
     └──────────────────── 같은 WiFi(LAN) ─────────────────────────────────┘
                                      │
                               [패드(실기기)]  그 명령으로 앱 실행 → 인증된 채 부팅 → 15분 루프 녹화
```

핵심: **Phaiakes9와 패드가 같은 WiFi**에 있어야 하고, 패드는 Phaiakes9의 **LAN IP**로 접속한다(localhost 아님).

---

# §A. Windows(PowerShell) 경로 — 이 PC가 Phaiakes9인 경우 (권장)

## A-0. 전제 (한 번 확인)

```powershell
docker version                              # Docker Desktop 실행 중이어야 함(고래 아이콘)
Invoke-RestMethod http://localhost:11434/api/tags   # Ollama for Windows 가동 → 코치 라이브(없어도 루프 완주)
pip install uv                              # uv 없으면(conda base에서 1회)
```
> `docker`가 PowerShell에서 안 되면 Docker Desktop이 꺼졌거나 WSL 전용 상태 — **PowerShell(네이티브)** 에서 실행하세요.

## A-1. 브랜치 + 백엔드 venv (최초 1회, 리포 루트에서)

```powershell
git fetch origin claude/g-kiki-device-demo-fv831n
git checkout claude/g-kiki-device-demo-fv831n

cd src\backend
uv venv --python 3.12 .venv
.\.venv\Scripts\Activate.ps1        # ← 리눅스 'source .venv/bin/activate' 대응(Scripts, bin 아님)
uv pip install -e ".[dev]"
cd ..\..
```
> `Activate.ps1`에서 "스크립트를 실행할 수 없습니다" 오류 → 먼저 `Set-ExecutionPolicy -Scope Process -Bypass` 후 재시도.

## A-2. 원커맨드 기동 (리포 루트에서)

```powershell
.\scripts\demo\run_demo.ps1
```
- 자동으로: PG(pgvector) → alembic → 문제 시드 → uvicorn(`0.0.0.0:8000`·백그라운드) → 데모 토큰 발급 →
  LAN IP·LLM 모드 + **패드에서 칠 `flutter run …` 명령** 출력. (venv는 스크립트가 자동 결선하지만 A-1 설치는 필수.)
- **처음 실행 시 Windows 방화벽 팝업**이 뜨면 Python에 **개인 네트워크 허용**(패드가 8000 포트로 붙게).
- 출력된 `flutter run …` 명령을 복사. 이 창은 서버가 백그라운드로 도는 동안 그대로 둡니다.

## A-3. 패드에서 앱 실행

패드를 이 PC와 **같은 WiFi**에 두고 연결한 뒤 `src\mobile`에서:
```powershell
cd src\mobile
flutter pub get
dart run build_runner build --delete-conflicting-outputs   # ⚠️ 필수 — .g.dart 생성(안 하면 컴파일 실패)
# A-2에서 복사한 명령 그대로:
flutter run --dart-define=API_URL=http://<이 PC LAN IP>:8000 --dart-define=DEMO_TOKEN=<토큰>
```

## A-4. 녹화 → 정리 → 게이트 clear

- **④ 15분 루프 녹화**: 아래 §공통 "15분 루프 녹화" 표를 따른다(OS 무관).
- **정리·게이트 clear**:
```powershell
.\scripts\demo\stop_demo.ps1
python scripts\harness\backlog.py gates clear G-kiki-device-demo --evidence <녹화 링크>
```

## A-*. Windows 함정

| 증상 | 원인·해결 |
|---|---|
| `uv`/`alembic`/`uvicorn` not found | venv 미설치(A-1) 또는 스크립트가 venv를 못 찾음(`src\backend\.venv\Scripts`). |
| `docker` not found | Docker Desktop 미실행 or WSL 전용. **PowerShell**에서 실행. |
| `Activate.ps1` 차단 | `Set-ExecutionPolicy -Scope Process -Bypass` 후 재시도. |
| 패드에서 서버 못 붙음 | 첫 실행 방화벽 팝업에서 **개인 네트워크 허용**·API_URL이 이 PC Wi-Fi LAN IP인지 확인(`ipconfig`). |
| 코치 발문이 밋밋 | Ollama for Windows 미가동. Ollama 앱 실행/`ollama serve` 후 재시도(`/status`가 라이브로 바뀜). |

---

# §B. 리눅스/WSL 경로 (bash)

## ⓪ 사전 확인 (호스트에서, 1분)

```bash
# (a) 라이브 Ollama 살아있나 — 코치 발문 품질의 전제(없어도 루프는 결정론으로 완주)
curl -s localhost:11434/api/tags | head -c 200      # 모델 목록이 나오면 OK

# (b) 도커·파이썬
docker compose version && python3.12 --version

# (c) Phaiakes9의 LAN IP(패드가 붙을 주소) — 첫 번째 값을 기억
hostname -I | awk '{print $1}'
```

> Ollama가 안 뜨면 `docs/strategy/live_cost_measurement_2026-07.md`의 개통 절차로 먼저 살린다.
> 안 살려도 루프 완주엔 지장 없다(코치 발문만 결정론 degraded로 밋밋).

---

## ① 브랜치 + 백엔드 세팅 (최초 1회, 리포 루트에서)

```bash
git fetch origin claude/g-kiki-device-demo-fv831n
git checkout claude/g-kiki-device-demo-fv831n

cd src/backend
uv venv --python 3.12 .venv
source .venv/bin/activate
uv pip install -e ".[dev]"
cd ../..                       # 리포 루트로 복귀
```

---

## ② 원커맨드 기동 (venv 켠 상태로, 리포 루트에서)

```bash
source src/backend/.venv/bin/activate     # 아직 안 켰다면
bash scripts/demo/run_demo.sh
```

`run_demo.sh`가 자동으로 하는 6단계(= 블로커 3종 해소):

1. throwaway Postgres(`pgvector/pgvector:pg16`) 기동 + health 대기
2. `alembic upgrade head` — DB 스키마 생성
3. `seed_demo.py` — 진단 문제 적재 (`문제 적재 완료: N건` 출력)
4. `uvicorn`을 `0.0.0.0:8000`으로 백그라운드 기동 (패드가 LAN으로 접속)
5. `POST /v1/auth/demo/callback` — **데모 토큰 자동 발급** (데모 사용자 lazy upsert)
6. LAN IP·LLM 모드 출력 + **패드에서 칠 명령** 인쇄

**성공 시 마지막 상자**:
```
════════════════════════════════════════════════════════════
 flutter run \
   --dart-define=API_URL=http://<Phaiakes9 LAN IP>:8000 \
   --dart-define=DEMO_TOKEN=<긴 토큰>
════════════════════════════════════════════════════════════
```
- 이 `flutter run …` 명령을 **복사**한다.
- `LLM 모드: 라이브(Ollama)`로 뜨는지 확인(라이브면 코치 품질 최상).
- **이 터미널은 켜 둔 채로** 둔다(서버가 여기서 돈다). 새 터미널에서 다음 단계 진행.

---

## ③ 패드(실기기)에서 앱 실행

패드를 Phaiakes9와 **같은 WiFi**에 두고 USB 연결(또는 무선 디버깅).

```bash
cd src/mobile
flutter pub get
dart run build_runner build --delete-conflicting-outputs   # ⚠️ 필수 — .g.dart 생성(안 하면 컴파일 실패)
# ②에서 복사한 명령 그대로:
flutter run --dart-define=API_URL=http://<Phaiakes9 LAN IP>:8000 --dart-define=DEMO_TOKEN=<토큰>
```

앱이 **로그인 화면 없이 인증된 채 부팅** → 라우터가 자동으로 `/problem`("오늘의 문제")로 보낸다.

---

## ④ 15분 루프 녹화

패드 화면 녹화를 켜고, 고3 학생 1명이 되어 6단계를 완주한다:

| # | 단계 | 학생 조작 | 완주 신호 |
|---|---|---|---|
| ① | **온보딩** (~2분) | 철학 3페이지 스와이프 + 목표폼 → "시작하기"(또는 "건너뛰기") | `/problem` 도착 |
| ② | **진단** (~1~2분) | 조작 없음(자동 로드) | 문제 카드 렌더 |
| ③ | **문제제시** (~1분) | 발문 읽고 → **"풀이 시작"** | 채팅 화면 도착 |
| ④ | **풀이입력** (~2~3분) | 하단 **"풀이 단계"** 토글 → 입력 → **"풀이 확인"** (또는 "수식으로 입력" MathLive) | 학생 버블 표시 |
| ⑤ | **코치 멀티턴** (~5~6분·최대 병목) | 코치 발문 읽고 후속 발화 → 보내기 **2~3턴만** | 코치 버블 + 소크라테스 배지 누적 |
| ⑥ | **검증 신호** (즉시) | 없음(자동) | **CoachSignalCard**: "N단계 중 M단계 확인" 등 |

**완주 판정**: 온보딩 후 문제 카드 → "풀이 시작" → 풀이 전송 → 코치 버블 → 그 아래 CoachSignalCard
검증 신호가 뜨면 **1루프 완주**. (상세: `docs/architecture/s1_e2e_demo_script.md`)

> 팁: 코치 턴이 시간을 좌우 → **2~3턴으로 제한**. 문제 카드 1회 사전 워밍업으로 콜드스타트 대비.

---

## ⑤ 정리 & 게이트 clear

```bash
bash scripts/demo/stop_demo.sh     # uvicorn 종료 + throwaway PG(볼륨째) 제거
# 녹화 증적(링크)을 걸어 게이트 clear:
python3 scripts/harness/backlog.py gates clear G-kiki-device-demo --evidence <녹화 링크>
```
게이트가 clear되면 `S1-14-exit-gate-judgement`(owner=kiki)로 3종 게이트 판정을 기록해 S1을 공식 탈출한다.

---

## 문제 해결 (함정표)

| 증상 | 원인·해결 |
|---|---|
| 패드에서 "문제를 불러오지 못했어요" | API_URL이 **Phaiakes9 LAN IP**인지(localhost 아님)·방화벽 8000 포트 확인. Phaiakes9에서 `curl http://<LAN_IP>:8000/health`가 `{"status":"ok"}`면 서버는 정상. |
| `flutter run` 컴파일 에러 | `dart run build_runner build --delete-conflicting-outputs` 안 돌림(③ 재실행). `.g.dart`는 리포 미커밋 생성물. |
| `CREATE EXTENSION vector` 실패 | compose 이미지가 `pgvector/pgvector:pg16`인지 확인(순정 postgres:16은 실패). |
| 코치 발문이 밋밋(canned) | LLM/Ollama 없음(degraded). 루프 완주엔 무방. Ollama 살리거나 Phaiakes9에서 실행하면 라이브. |
| `alembic`/`uvicorn` not found | venv 미활성. `source src/backend/.venv/bin/activate` 후 재실행. |

---

## 보안 주의

- `WHYMATH_DEMO_AUTH_ENABLED=true`는 **로컬 시연 호스트(Phaiakes9)에서만** 켠다. 이 플래그가 켜지면
  `/v1/auth/demo/callback`이 신원 검증 없이 데모 계정 토큰을 발급하므로 **prod/공개 배포에서 절대 금지**.
- 킷은 기본 OFF·실 provider(kakao/naver) 구성 시 등록 거부(이중 방어)·JWT 시크릿 매 실행 런타임 생성.
