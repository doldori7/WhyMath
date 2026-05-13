# Phaiakes9 — Ollama + Qwen 수학 모델 운영 가이드

> M1.1 게이트 작업: Phaiakes9에 Qwen 수학 LLM을 배포하고 *p50 < 2s* 응답 속도를 측정한다.
>
> 이 디렉토리는 Kiki가 **Phaiakes9 머신 (Linux)** 에서 따라 실행할 운영 자산입니다.
> Windows PowerShell·macOS 터미널이 아닌 *Phaiakes9 콘솔* 또는 *그 머신에 SSH 접속한 세션* 에서 실행하세요.

---

## ⏪ 머신이 아직 준비 안 됐다면 — M1.0a

이 README는 *Phaiakes9가 이미 부팅·SSH 접속 가능* 한 상태를 가정합니다.
머신 자체를 처음 셋업해야 하면 먼저 **[`SETUP_GUIDE.md`](./SETUP_GUIDE.md)** 부터 따라가세요.

- 박스 부팅 → Ubuntu 24.04 설치 → SSH 키 등록 → `bootstrap.sh` 실행
- 약 2~3시간 소요
- 완료 후 이 README §2 "빠른 시작"으로 돌아옵니다

---

## 0. 사전 확인

- 머신: **Phaiakes9** (AMD Ryzen AI Max+ 395, 128 GB RAM, Linux)
- OS: **Ubuntu 24.04 LTS** 가정 (다른 배포판은 패키지 매니저만 교체)
- 권한: `sudo` 사용 가능한 사용자 계정 필요
- 네트워크: HuggingFace / ollama.ai 레지스트리 도달 가능
- 디스크 여유 (디폴트 7B 모델): **15 GB 이상** 권장
- 디스크 여유 (32B 추가): **25 GB 이상**
- 디스크 여유 (72B 추가, 가능 시): **45 GB 이상**

### CLAUDE.md 절대 금기 확인
- 모든 시크릿은 **환경변수**로 전달. 코드/스크립트에 하드코딩하지 않습니다.
- 벤치마크 표본은 **원작 문제**로만 구성. 검정교과서 본문 일체 복제 금지 (`benchmark/sample_prompts.json` 참조).

---

## 1. 디렉토리 한 눈에 보기

```
infra/phaiakes9/
├── README.md                  ← 이 문서 (Ollama·벤치마크 운영)
├── SETUP_GUIDE.md             ← 머신 처음 셋업 (M1.0a)
├── bootstrap.sh               ← Ubuntu 부팅 직후 자동 설정 (sshd·ufw·ROCm)
├── install_ollama.sh          ← Ollama 설치 (멱등)
├── pull_models.sh             ← Qwen 수학 모델 풀
├── healthcheck.sh             ← 헬스체크 (HTTP 200·모델 로드·간단 generate)
├── systemd/
│   └── ollama.service         ← systemd unit (0.0.0.0:11434 바인딩)
├── benchmark/
│   ├── bench_latency.py       ← Python 벤치마크 (ollama 클라이언트)
│   ├── sample_prompts.json    ← 고1 내신 표본 문제 (원작)
│   └── run_bench.sh           ← 벤치마크 실행 래퍼
├── results/                   ← 벤치마크 출력 (.gitignore 처리)
└── .gitignore
```

---

## 2. 빠른 시작 (5단계, 약 30분)

```bash
# 0) Phaiakes9 콘솔(SSH 세션 포함)에서, WhyMath 클론 경로로 이동
#    아래 <whymath-root> 부분은 본인 환경의 실제 경로로 대체 — 예: ~/whymath
cd <whymath-root>/infra/phaiakes9

# 1) Ollama 설치 (멱등 — 이미 설치되어 있으면 스킵)
bash install_ollama.sh

# 2) systemd 서비스 등록 (선택. 부팅 시 자동 시작)
sudo cp systemd/ollama.service /etc/systemd/system/ollama.service
sudo systemctl daemon-reload
sudo systemctl enable --now ollama

# 3) 디폴트 모델(Qwen2.5-Math-7B-Instruct) 풀
bash pull_models.sh
# (선택) 32B / 72B까지: WHYMATH_MODELS=all bash pull_models.sh

# 4) 헬스체크
bash healthcheck.sh

# 5) 벤치마크 실행 (5~20분 소요)
bash benchmark/run_bench.sh
```

벤치마크 결과는 `results/YYYY-MM-DD_HHMMSS.json`에 저장됩니다. p50 / p90 / p99 latency, tokens/sec, 동시 요청별 처리량이 기록됩니다.

---

## 3. 단계별 상세

### 3.1 Ollama 설치 — `install_ollama.sh`

```bash
bash install_ollama.sh
```

- 공식 설치 스크립트(https://ollama.com/install.sh)를 호출합니다.
- 이미 `ollama` 바이너리가 존재하면 버전만 출력하고 종료합니다 (멱등).
- 설치 후 `ollama --version`을 출력합니다.

**문제 시**: 회사망/프록시 환경에서는 `curl`이 막힐 수 있습니다. 그때는 https://github.com/ollama/ollama/releases 에서 `.tgz`를 수동 다운로드 → `/usr/local/bin/`에 압축 해제.

### 3.2 systemd 서비스 — `systemd/ollama.service`

설치 스크립트가 자체 unit을 만들 수 있으나, 우리는 **0.0.0.0:11434 바인딩**(다른 머신에서 호출)을 위해 명시적으로 덮어씁니다.

```bash
sudo cp systemd/ollama.service /etc/systemd/system/ollama.service
sudo systemctl daemon-reload
sudo systemctl enable --now ollama
sudo systemctl status ollama
```

- 환경변수 `OLLAMA_HOST=0.0.0.0:11434` 가 핵심입니다.
- GPU/CPU 자동 감지는 ollama 런타임이 알아서 합니다.
- 로그: `journalctl -u ollama -f`

**보안 주의**: 0.0.0.0 바인딩은 방화벽 뒤에서만 허용하세요. Phaiakes9는 폐쇄망 가정. 외부 노출이 필요하면 reverse proxy + 인증을 추가하세요.

### 3.3 모델 풀 — `pull_models.sh`

```bash
# 디폴트: 7B만 (약 4.4 GB)
bash pull_models.sh

# 32B 포함 (약 19 GB 추가)
WHYMATH_MODELS=mid bash pull_models.sh

# 7B + 32B + 72B 전체 (약 45 GB 추가)
WHYMATH_MODELS=all bash pull_models.sh
```

| 환경변수 값 | 풀 대상 |
|---|---|
| (미설정) / `default` / `7b` | `qwen2.5-math:7b-instruct` |
| `mid` | + `qwen2.5-math:32b-instruct` (있을 경우) |
| `all` | + `qwen2.5-math:72b-instruct` 또는 `qwen2.5:72b-instruct` 폴백 |

**디폴트로 Qwen2.5-Math-7B-Instruct를 선택한 이유**
1. ollama.ai 레지스트리에 실재하며 정상 동작 확인 가능 (가설 모델인 Qwen3-Math와 달리).
2. 7B는 Ryzen AI Max+ 395 + 128 GB RAM 환경에서 CPU 추론으로도 *수 초 이내* 응답 가능 → p50 < 2s 게이트와 직접 비교 가능.
3. 한국 고1 내신 수준의 수학 응답에 충분한 품질 (NuminaMath·MATH 벤치마크 기준).
4. 디스크 사용 4 GB 대로 *재실행 부담* 최소.

**Qwen3-Math가 실재하면**: `WHYMATH_MODELS_OVERRIDE` 환경변수로 모델 ID를 직접 지정할 수 있도록 스크립트가 설계되어 있습니다. 자세한 사용 예는 `pull_models.sh` 상단 주석 참조.

### 3.4 헬스체크 — `healthcheck.sh`

```bash
bash healthcheck.sh
```

3가지를 차례로 확인합니다.

1. **HTTP 200**: `GET http://localhost:11434/`
2. **모델 로드**: `GET /api/tags` 응답에 `qwen2.5-math` 가 포함되는지
3. **간단 generate**: `POST /api/generate` 로 "2+2는?"을 던지고 응답을 받는지

3개 모두 통과해야 종료 코드 0. 하나라도 실패하면 stderr에 한국어 안내가 출력됩니다.

### 3.5 벤치마크 실행 — `benchmark/run_bench.sh`

```bash
bash benchmark/run_bench.sh
```

내부적으로 `benchmark/bench_latency.py`를 실행합니다.

- 디폴트 모델: `qwen2.5-math:7b-instruct`
- 표본: `benchmark/sample_prompts.json` (고1 내신 5~10문항, 원작)
- 동시 요청: 1, 2, 4, 8 (각 단계마다 표본 전체 1회)
- 출력: `results/YYYY-MM-DD_HHMMSS.json`
- p50/p90/p99 latency (ms), 평균 tokens/sec, 게이트 통과 여부

### 3.6 모델 / 동시도 / 호스트 변경

```bash
WHYMATH_BENCH_MODEL=qwen2.5-math:32b-instruct \
WHYMATH_BENCH_CONCURRENCY=1,4 \
WHYMATH_OLLAMA_HOST=http://localhost:11434 \
bash benchmark/run_bench.sh
```

---

## 4. MEMORY.md 결정 로그 첨부 형식

벤치마크가 성공하면 `results/YYYY-MM-DD_HHMMSS.json` 파일이 생성됩니다. MEMORY.md에 다음 형식으로 *수동* 첨부하세요.

```markdown
### 2026-MM-DD: M1.1 Phaiakes9 Qwen 수학 모델 응답 속도 측정
**컨텍스트**: M1.1 게이트 — "Phaiakes9 Qwen3-Math 응답 속도 p50<2s 측정 완료 + NCIC 크롤러 가동"
**측정 환경**:
- 머신: Phaiakes9 (Ryzen AI Max+ 395, 128GB RAM)
- 모델: qwen2.5-math:7b-instruct (Qwen3-Math 부재 시 대체)
- 표본: 고1 내신 원작 8문항
- 도구: infra/phaiakes9/benchmark/bench_latency.py
**결과** (results/2026-MM-DD_HHMMSS.json 발췌):
- concurrent=1: p50=Xms / p90=Yms / p99=Zms / tokens/sec=N
- concurrent=4: ...
- 게이트 통과 여부 (p50 < 2000ms): true/false
**결정**: ...
**상태**: ...
```

`results/` 디렉토리는 git에서 무시됩니다 (`infra/phaiakes9/.gitignore` 참조). 결과 JSON은 보안상 *발췌만* MEMORY.md에 붙여 넣으세요.

---

## 5. 트러블슈팅

| 증상 | 원인 후보 | 조치 |
|---|---|---|
| `ollama: command not found` | install 스크립트 실패 | `bash install_ollama.sh` 재실행, 로그 확인 |
| `curl: (7) Failed to connect to localhost:11434` | 서비스 미기동 | `sudo systemctl status ollama` / `journalctl -u ollama` |
| `pull manifest unknown` | 모델명 오타 또는 미존재 | `WHYMATH_MODELS_OVERRIDE` 로 모델명 직접 지정. ollama.ai/library 에서 확인 |
| 응답이 너무 느림 (>10s) | 모델이 콜드 로드 중 | 헬스체크 generate를 2~3회 사전 실행해 워밍업 후 측정 |
| OOM (메모리 부족) | 32B/72B 동시 로드 | `ollama ps` 로 로드된 모델 확인, `ollama stop` 으로 정리 |
| `Permission denied` (systemd) | sudo 누락 | `sudo` 붙여서 재실행 |
| 벤치마크 p50 >> 2000ms | 디스크 I/O 병목 또는 양자화 미적용 | `ollama show qwen2.5-math:7b-instruct` 로 양자화 확인 (Q4_K_M 등) |

---

## 6. 후속 작업 (이번 PR 범위 밖)

- `/implement llm:phaiakes9-router` — FastAPI 라우터 + `L3LLMService` 구현체. 이번 PR은 *인프라*만, *서버 코드*는 별도 위임.
- `/implement data:ncic-crawler` — NCIC 성취기준 크롤러. M1.1 게이트의 또 다른 절반.

---

## 7. 표준 준수 체크리스트

- [x] 모든 쉘 스크립트는 `set -euo pipefail`
- [x] 한국어 echo 메시지 (Kiki 선호)
- [x] 시크릿 하드코딩 없음 (환경변수만)
- [x] 검정교과서 본문 인용 없음 (원작 표본만)
- [x] 단위 테스트는 ollama 호출 모킹 (`tests/infra/test_benchmark.py`)
- [x] `results/` git 무시 (개인정보 보호)
