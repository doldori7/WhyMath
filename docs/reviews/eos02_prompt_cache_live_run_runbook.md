# EOS-02 라이브 회차 런북 — 프롬프트 캐시 적중 계측 (Kiki 직접 수행)

> 게이트: `G-eos02-prompt-cache-live-run` (assignee kiki · 2026-09-07 등재)
> 태스크: `EOS-02-prompt-cache-live-measurement` — 이 게이트가 clear되기 전에는 에이전트 착수 후보에서 제외된다(착수 조건).
> 판정 기준 커밋: main `b75f495d` (EOS-99 #1023 착지 상태 — `--subscription`·`--budget-krw` 플래그와 `prompt_cache` 리포트 블록이 모두 이 커밋에 실재함을 실측했다).

---

## 0. 사전 브리핑 (6항목)

1. **과제 명칭** — Anthropic 프롬프트 캐시가 *실제로 작동하는지* 재는 라이브 회차 1회.
2. **목적** — 캐시 플래그(`anthropic_prompt_caching`)의 기본값을 켤지 판단할 **실측 근거**를 만든다. 지금까지는 hermetic(가짜 provider) 테스트라 적중률이 정의되지 않았다. 결과 블록 하나가 EOS-02 acceptance ②③의 판정 재료 전부다. 계측 없이 켜지 않는다(EOS-99 ④ 승계).
3. **구체적 절차** — 창 ① 하나에서 §1(키 자가검증 10초) → §2(회차 실행 3~10분·클라우드 12회 호출) → §3(리포트 블록 출력 10초) 순서. §3 출력 블록을 그대로 세션에 회신한다.
4. **성공 기준** — §3에서 `CALLS_WITH_CACHE_TELEMETRY`가 **0보다 크면** 측정이 성립한 것이다(state가 무엇이든 회신). `0`이면 클라우드로 안 나간 것이므로 적중률을 읽지 말고 §2의 두 플래그(`--subscription premium`·`--budget-krw 5000`)가 둘 다 들어갔는지 먼저 본다. `STALE_FILES`가 0이 아니면 회차가 돌지 않는다 — 남은 파일 목록을 회신하고 지우지 않는다.
5. **실행 환경** — Phaiakes9 = 평소 쓰는 Windows PowerShell(별도 접속 없음). 작업 디렉터리 `C:\Users\kiki\Desktop\__AI\WhyMath`. 선행 조건: `.venv` 존재 · Anthropic 키가 User 환경변수 `WHYMATH_ANTHROPIC_API_KEY`로 등록돼 있음(게이트 `G-phaiakes9-key` cleared 상태를 근거로 등록됐다고 본다 — §1이 실측한다) · 인터넷 연결 · **Ollama 가동**(창 ② — MP-02 런북과 동일. 생성기는 표준 CompositeProvider(Ollama+Anthropic)를 지연 구성하므로 로컬 경로가 필요한 하위 호출이 있을 수 있다. 캐시 텔레메트리는 클라우드 호출만 세므로 로컬 호출이 섞여도 적중률 분모는 흐려지지 않는다). Docker는 불요.
6. **창 구분** — **새 창 ②**에서 `ollama serve`(서버 점유 창 · 이후 조작 금지 · Ctrl+C는 중단 신호). **새 창 ①**에서 §1~§3을 순서대로 붙여넣는다.

**예상 비용**: claude-sonnet-4-6 12회 호출 · 회차당 수백 원 이내(예산 상한 `--budget-krw 5000`이 라우터 쪽 안전장치).

---

## 0-b. Ollama 기동 — 창 ② (서버 점유 창)

```powershell
# Windows PowerShell (= Phaiakes9) · 창 ② — 서버 점유 창 · 이후 조작 금지 · Ctrl+C는 복사가 아니라 중단 신호
ollama serve
```

이미 떠 있으면(`Error: listen tcp 127.0.0.1:11434: bind` 류) 그대로 두고 창 ①로 간다 — 기존 데몬이 곧 서버다.

---

## 1. 키 자가검증 — 창 ①

키 값은 출력하지 않는다. 길이와 생략 문자(`…`) 포함 여부만 본다.

```powershell
# Windows PowerShell (= Phaiakes9) · 창 ①
cd C:\Users\kiki\Desktop\__AI\WhyMath
$K = [Environment]::GetEnvironmentVariable("WHYMATH_ANTHROPIC_API_KEY", "User")
"KEY_LEN=$($K.Length) HAS_ELLIPSIS=$([bool]($K -match '…')) STARTS_SK=$([bool]($K -like 'sk-ant-*'))"
```

**성공**: `KEY_LEN=`이 80 이상 · `HAS_ELLIPSIS=False` · `STARTS_SK=True`.
**실패**: `KEY_LEN=0`이면 키가 User 환경변수에 없다 — 회차를 돌리지 말고 그 줄을 회신한다(등록 절차는 별도 안내).

---

## 2. 회차 실행 — 창 ① (3~10분)

**설계 판단 3건**(태스크가 지정하지 않아 세션이 정한 값):

1. **캐시 플래그를 이 창에서만 켠다** — `$env:WHYMATH_ANTHROPIC_PROMPT_CACHING = "true"`. 기본값(False)은 건드리지 않는다. 판정 ③이 끝나기 전에 기본값을 바꾸면 "계측 없이 켜기"가 된다.
2. **새 출력 폴더** `problem_bank_eos02_cache_probe_v0` — 기존 코퍼스와 섞지 않는다. 축적기는 append-only라 앞 시도 잔여물이 dedup 분모를 흐린다(MP-02 런북 §3과 같은 이유).
3. **`--n 12`** — acceptance ①의 최소 n=10에 여유 2회. 기대 적중률 ≈ (n−1)/n = 91.7%.

두 플래그 `--subscription premium --budget-krw 5000`은 **둘 다** 있어야 클라우드로 나간다(실측 2026-09-07: premium/0=local · free/5000=local · premium/5000=cloud_mid).

```powershell
# Windows PowerShell (= Phaiakes9) · 창 ①
cd C:\Users\kiki\Desktop\__AI\WhyMath
$Py = ".\.venv\Scripts\python.exe"
$env:WHYMATH_ANTHROPIC_PROMPT_CACHING = "true"
$Out = "data\corpus\problem_bank_eos02_cache_probe_v0\problems.jsonl"
$Stale = @($Out, "$Out.rounds.jsonl", "$Out.genlog.jsonl", "$Out.review.jsonl") | Where-Object { Test-Path $_ }
"STALE_FILES=$($Stale.Count)"
if ($Stale.Count -gt 0) { "중단: 앞 시도의 산출물이 남아 있습니다 → $($Stale -join ', ')" }
if ($Stale.Count -eq 0) { New-Item -ItemType Directory -Force -Path (Split-Path $Out) | Out-Null }
if ($Stale.Count -eq 0) { & $Py -m whymath_backend.harness.problem_corpus_accumulate --out $Out --n 12 --subscription premium --budget-krw 5000 --standard-code "[9수02-20]" --difficulty 2.5 | Tee-Object -FilePath "eos02_report.json"; "ACCUMULATE_EXIT=$LASTEXITCODE" }
```

**예상 출력**: 진행 로그가 흐른 뒤 마지막에 리포트 JSON, 그리고 `ACCUMULATE_EXIT=0`(신규 수용 0건이면 `1` — 이 회차에서는 수용 건수가 아니라 캐시 블록이 목적이므로 `1`이어도 §3으로 진행한다). 리포트는 `eos02_report.json`에 저장된다(stdout은 리포트 JSON만 — 로그는 stderr).

> 각 줄을 `if`로 감싼 이유: 붙여넣기 실행에서는 줄마다 독립 실행돼 `throw`가 뒤 줄을 멈추지 못한다.

---

## 3. 판정 블록 출력 — 창 ①

```powershell
# Windows PowerShell (= Phaiakes9) · 창 ①
cd C:\Users\kiki\Desktop\__AI\WhyMath
$R = Get-Content "eos02_report.json" -Raw | ConvertFrom-Json
$R.prompt_cache | ConvertTo-Json
"CALLS_WITH_CACHE_TELEMETRY=$($R.prompt_cache.calls_with_cache_telemetry) STATE=$($R.prompt_cache.state) HIT_RATE=$($R.prompt_cache.hit_rate)"
```

**성공**: `CALLS_WITH_CACHE_TELEMETRY`가 0보다 크다. 이때 `STATE`는 다음 중 하나다 — 어느 값이든 **블록 전체를 그대로 회신**한다(판정은 세션이 한다):

| STATE | 뜻 | 세션의 다음 행동 |
|---|---|---|
| `enabled_working` | 켰고 적중이 있다 | `HIT_RATE`가 0.9 근처면 정상. ③ 기본값 전환 판단으로 진행 |
| `enabled_not_working` | 켰는데 적중 0% | 원인 규명(프리픽스가 최소 캐시 토큰 미만인지 · 회차마다 프리픽스가 갈리는지) |
| `disabled` / `disabled_but_hit` | 플래그가 꺼진 채 돌았다 | §2의 `$env:` 줄이 같은 창에서 실행됐는지 확인 후 재실행 |
| `unmeasured` / `unknown_flag` | 분모 없음 / 플래그 미상 | 블록 회신 — 세션이 provider 텔레메트리 경로를 본다 |

**실패**: `CALLS_WITH_CACHE_TELEMETRY=0`(`STATE=not_applicable`). 클라우드로 나가지 않은 것이다 — 0%가 아니라 **미측정**이다. §2의 명령 줄에 두 플래그가 모두 있는지, §1 키가 유효한지 확인하고 §2를 새 폴더 이름(`_v1`)으로 다시 돌린다.

---

## 4. 게이트 clear (세션이 수행)

회신된 블록을 근거로 세션이 EOS-02 acceptance ②③을 판정하고, 게이트는 저장소 밖 행위(라이브 실측)라 `--no-base`로 닫는다:

```
python3 scripts/harness/backlog.py gates clear G-eos02-prompt-cache-live-run --as kiki --evidence "<회신 블록 요약: state·hit_rate·calls_with_cache_telemetry>" --no-base "라이브 회차 실측 — 저장소 밖 행위"
```

이 명령은 **세션이** 실행한다(Kiki 머신 안내 아님 — 미머지 게이트 항목의 CLI 조작을 Kiki 머신에 안내하지 않는 규칙 2026-08-31).
