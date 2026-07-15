# 라이브 비용·지연 실측 핸드오프 (S1-12 · ROADMAP 병목 ②)

> **상태**: ✅ **실측 완료(2026-07-14·Kiki 라이브 세션)** — 결과표 기입·판정 완료(아래) | **owner**: kiki(실측)·claude(기록·판정 서기)
> **측정 도구 검증(2026-07-13)**: `live_preflight --no-smoke` exit 0(설정·판정 경로 건전·클라우드/Ollama 미설정 정직 보고)·§3 배치 CLI(`problem_corpus_accumulate`)·§5 판독 CLI(`ops.cost_report`) 인자 확정·런북 자리표시자 해소. **claude-소유 선제 준비분(측정 스크립트·판독기)은 완비** — 잔여는 Kiki의 라이브 실호출뿐(클라우드 환경 도달 불가).
> **목적**: Phaiakes9 라이브 호출의 비용·지연을 실측해 S1 탈출 게이트 ②("루프당 비용 실측·로컬 80%")와
> verify 커버리지 게이트 승격 판정의 **추정치를 실측치로 교체**한다. 이 문서의 결과표가 채워지면 S1-12 done.
> **원칙**: 숫자는 날조하지 않는다 — 실행 안 한 항목은 빈칸으로 둔다(추정 vs 실측 구분·`cost_krw=None` vs `0.0`).

---

## 개통 이정표 (완료분)

| 이정표 | 상태 | 증적 |
|---|---|---|
| 모델 6종 pull | ✅ | qwen2-math:1.5b/7b · qwen2.5:3b/7b · qwen3.5:27b · qwen3-vl:8b |
| 스모크 도달성 | ✅ | `check_status()` → reachable:True · missing:[] · **READY:True** |
| 파이프라인 ① rephrase | ✅ | 590 attempted → **184 rephrased / 406 unchanged**(전부 안전 사유: 원문 동일 or 수치 불변 봉인) |
| 클라우드 티어 비용 실측 | ✅ 2026-07-14 | preflight cloud_mid 1콜 0.4066원(63/5 tok·1187ms)·cost_report 33이벤트 판독 |
| 파이프라인 ② LLM 생성 라이브 | ✅ 2026-07-14 | accumulate n=5 → **accepted_stored 1**(게이트 통과 실적재)·rejected_duplicate 4(구조 dedup 정상 — 해당 spec 코퍼스 포화) |

---

## Kiki 실행 런북 (Phaiakes9 머신 · `WhyMath\src\backend`, venv 활성)

라이브 계측 데이터를 생성하는 순서. 상세는 `infra/phaiakes9/LIVE_LLM_ACTIVATION.md` §6·§7·§10·§11.

### 1. §10 클라우드·관측성 키 (비용 실측의 전제)
```powershell
# 관측성 (Langfuse) — 미설정 시 계측이 계산만 되고 버려짐(sink 영구 no-op)
[Environment]::SetEnvironmentVariable("WHYMATH_LANGFUSE_PUBLIC_KEY", "pk-lf-…", "User")
[Environment]::SetEnvironmentVariable("WHYMATH_LANGFUSE_SECRET_KEY", "sk-lf-…", "User")
# 클라우드 LLM (Anthropic) — CLOUD_MID/HIGH 경로 (로컬 온리면 생략 가능)
[Environment]::SetEnvironmentVariable("WHYMATH_ANTHROPIC_API_KEY", "sk-ant-…", "User")
# ⚠ 모델 alias가 404면 실제 사용 가능한 ID 핀 (코드 변경 0):
# [Environment]::SetEnvironmentVariable("WHYMATH_ANTHROPIC_MODEL_MID", "claude-…", "User")
```

### 2. 계측 흐름 즉석 검증 (서버 없이 — 키 투입 직후 1회)
```powershell
python -m whymath_backend.ops.live_preflight --via-pipeline --json preflight.json
```
→ `l3.pipeline.generate`를 태워 `l3_routing` 이벤트를 실제 기록·flush. 출력의 **③ 실측 cost_krw·토큰**을
아래 결과표에 기록. (Anthropic 미설정이면 LOCAL 폴백 0원이라도 기록 증명 성립.)

### 3. llm_generator 소량 배치 (클라우드 호출 유발)
```powershell
# 동등문제 LLM 축적 배치(n=5) — 기존 코퍼스 signature 주입해 중복 차단·수용분만 append.
# 라이브 LLM 필요 → l3_routing 이벤트·GenerationLog에 실측 토큰/비용/지연이 쌓인다.
python -m whymath_backend.harness.problem_corpus_accumulate `
    --seed data/corpus/problem_bank_generated_v0/problems.jsonl `
    --out live_accum.jsonl --n 5 --standard-code 12미적Ⅰ-02-07 --difficulty 3
# (산출물 live_accum.jsonl은 v0·라이브 LLM 결과라 커밋하지 않는다 — §이후 연결 규약)
```

### 4. §7 judge shadow 측정
```powershell
$env:WHYMATH_MISCONCEPTION_JUDGE_SHADOW = "true"   # routing=general_mid
# judge 게이트/shadow 호출 비용도 l3_routing으로 흐름(#467)
```

### 5. §11 판독 → 결과표 채우기
**한 명령으로 결과표를 자동 산출**(수동 Langfuse 판독 대체 — `ops/cost_report.py`가 `l3_routing`을
p50/p90·로컬비율·캐시적중·튜닝 제안으로 집계):
```powershell
# 라이브 세션 직후엔 --days 1 권장. JSON을 아래 결과표에 옮겨 적는다.
python -m whymath_backend.ops.cost_report --days 1 --json cost_report.json
```
출력 매핑: `tier_stats[local|cloud_mid|cloud_high]`의 cost_krw/tokens/latency 분포(p50·p90·합) →
비용·지연 표 / `local_ratio` → 로컬:클라우드 판정선(≥0.8) / `suggested_est_*` → S1-13 router 튜닝 입력.

**결과표 자동 기입(전기 오류 0)**: JSON을 아래에 넣으면 표에 붙여넣을 행이 그대로 나온다:
```powershell
python ..\..\scripts\fill_live_cost_table.py cost_report.json
```
(미측정 셀은 '—' 유지 — 날조 금지. verify verdict 분포 표만 별도 소스 `GET /v1/me/harness-metrics`.)

보조 판독원(교차 확인용):
- `GET /v1/me/harness-metrics`(api/me.py): 대리 지표 7종 — verify 통과율 등(verdict 분포 표)
- `GenerationLog` 테이블: 호출별 토큰·지연 실측(배치 회계)

---

## 결과표 (Kiki 실측 후 기입 — 빈칸 = 미측정)

### 비용 (루프당·티어별)
| cost_tier | 호출 수 | cost_krw (합/평균) | input/output tokens (평균) | 비고 |
|---|---|---|---|---|
| LOCAL | 24 | 0.0 (로컬) | —¹ | 라우터 목표 80% |
| CLOUD_MID | 9 | 63.7098 / 7.0789² | —¹ | Sonnet 경로 |
| CLOUD_HIGH | 0 | — | — | 호출 0(미발생) |
| **로컬:클라우드 비율** | 24:9 | | | **72.7% — 판정선(≥80%) 미달³** |

전역 분포(33이벤트·tier 미분해¹): input p50 74·p90 95·mean 77 (n=32) / output p50 358·p90 506·mean 333 (n=32) / cost p50 0·p90 9.6743·mean 1.9306·합 63.7098 (n=33) / 캐시 적중 0/33.

¹ 실측이 판독기 구판(tier_stats 확장 이전)으로 수행돼 티어별 토큰·지연 분해가 JSON에 없음 — 차기 실측은 `cost_report`가 자동 분해(2026-07-14 확장). ² 유도치: LOCAL 24건 전부 cost 0.0 기록 → 클라우드 합=전역 합 63.7098·평균=63.7098/9(산술 유도·측정 아님 명시). ³ **대표성 캐비엇**: 이 33이벤트는 측정 세션 트래픽(클라우드 유발 스모크+배치 포함)이라 프로덕션 루프 믹스가 아님 — 판정선 재판정은 S1-13 라우터 튜닝(아래) 후 대표 트래픽으로.

### 지연
| 경로 | p50 latency_ms | p90 latency_ms | 비고 |
|---|---|---|---|
| LOCAL (Ollama) | —¹ | —¹ | 티어 미분해(각주 ¹) |
| CLOUD_MID | —¹ | —¹ | preflight 단일 콜 실측 1187ms(참고) |
| (전역·33이벤트) | 3250 | 8165 | mean 3858 |

### verify verdict 분포 (게이트 승격 근거) — ✅ 2026-07-15 라이브 실측(Kiki·shadow 로그·2배치 n=10)
| verdict | 전체(n=10) | 배치① 방정식 변형(n=6) | 배치② 표현식 동치(n=4) |
|---|---|---|---|
| correct | 30% (3) | 0 | **3** |
| incorrect | 10% (1) | 0 | **1** |
| unverifiable | 60% (6) | **6** | 0 |

**검출력 라이브 증명(배치 ②)**: 표현식 동치 체인(인수분해형→전개형·등호 없음) 4턴 중 1턴에
*의도적 오전개*(`(x+1)(x+2) → x²+3x+1`, 정답 `x²+3x+2`)를 주입 → 하네스가 정확히
`incorrect`로 검출, 나머지 3건(올바른 전개)은 전건 `correct`. **결정 가능 구간 판정 정확도
4/4(100%)** — verify 경로가 라이브에서 증명력·검출력 모두 실증.

측정 경로 정정: verdict 분포의 실소스는 `GET /v1/me/harness-metrics`(대리지표 7종·별건)가 아니라
**shadow 관측 로그**(`whymath.harness.wh1_shadow.record` — 무영속·로거 emit)다. 실측 절차:
`WHYMATH_WH1_HARNESS_SHADOW_ENABLED=true` + demo 스택(PG 55432·`?ssl=disable`) + root INFO 로깅
런처로 코치 세션+멀티턴(전 턴 `solution_steps` 동봉) → 로그 grep. **PR #519 멀티턴 배선
라이브 검증**: 두 배치 모두 turn_index 증가·dialogue_id 연결·전 관측 status=ended 정상.

**대표성 캐비엇(정직)**: n=10·합성 트래픽·트래픽 모양이 verdict를 결정한다 — 배치①(방정식 변형
체인 `A=0 → 인수분해형=0 → 근`)은 S2-02에서 확인된 `verify_step` 한계 구간이라 100% unverifiable
(예상 정합), 배치②(표현식 동치)는 100% 결정. 실학생 트래픽의 두 모양 혼합비가 곧 실효 커버리지
— 프로덕션 분포는 실트래픽에서 재측정.

### 판정 (실측 후 — 2026-07-14)
- [x] 루프당 비용 실측 완료·로컬 ≥80% 여부: **실측 완료(33이벤트) — 72.7%로 미달(as-measured)**. 단 측정 세션 믹스 대표성 제한(각주 ³)·라우터 est 가정 1000 vs 실측 p50 74/358의 대폭 괴리 → **S1-13(튜닝) 수행 후 대표 트래픽 재판정**이 정당한 절차.
- [x] verify 커버리지 게이트 primary 승격 가부: **부결 유지·단 근거 갱신(2026-07-15 재판정)** — shadow verdict 분포 확보(n=10·2배치) + **결정 가능 구간 검출력 4/4 라이브 실증**(오전개 주입 → incorrect 정확 검출). 잔여 미충족: 표본 과소(n=10·합성)·실학생 트래픽 혼합비 미지·flip 전제 ③(Kiki 사인오프+gate3 allowlist 확장) 미착수. 재판정 조건: 실기기 시연(G-kiki-device-demo) 등 실트래픽에서 shadow 분포 누적 후 Kiki 판정.
- [x] MEMORY.md 결정로그 append: 2026-07-14 S1-12 실측 항목.

### S1-13 입력(튜닝 제안 — cost_report 산출)
- `_EST_ASSUMED_INPUT_TOKENS` 1000 → **74** · `_EST_ASSUMED_OUTPUT_TOKENS` 1000 → **358**
- 대입 시 CLOUD_MIN_COST_KRW·est_cost_krw·guard_cloud 임계값 단일 공식 자동 재계산 — 로컬:클라우드 라우팅 재분포 예상 → 재측정으로 80% 판정선 재판정.

---

## 이후 연결
- 이 표가 채워지면 **S1-12 done** → S1-13(비용/지연 보정·프롬프트 캐싱)·S2-01(동등문제 100+, +G-crosswalk-approval) 해금.
- **S1-11**(coach→하네스 단일 수렴)은 이 실측 + 라이브 shadow verdict 분포를 근거로 학생-대면 primary 승격 판정 후 착수("측정 없는 도입 없음").
- 주의: **rephrase 산출물은 커밋하지 않는다**(v0 사람 검수 전·라이브 LLM 결과 미커밋 규약).
