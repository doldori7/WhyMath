# 라이브 비용·지연 실측 핸드오프 (S1-12 · ROADMAP 병목 ②)

> **상태**: 🔄 진행 중 — 서버 개통 완료(2026-07-09·Kiki), 실측 숫자 대기 | **owner**: kiki(라이브 실호출 필수)
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
| 클라우드 티어 비용 실측 | ⬜ 대기 | §10 Anthropic+Langfuse 키 투입 후 §11 판독 |

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

### 3. §6 llm_generator 소량 배치 (클라우드 호출 유발)
```powershell
# 동등문제 LLM 생성 소량(n=5) — accepted_stored 확인. 정확한 CLI 인자는 §6 참조.
python -m whymath_backend.harness.<llm_generator 배치 명령> --n 5
```

### 4. §7 judge shadow 측정
```powershell
$env:WHYMATH_MISCONCEPTION_JUDGE_SHADOW = "true"   # routing=general_mid
# judge 게이트/shadow 호출 비용도 l3_routing으로 흐름(#467)
```

### 5. §11 판독 → 결과표 채우기
- **Langfuse `l3_routing` 이벤트**(langfuse_sink.py:47): `cost_tier`(LOCAL/CLOUD_MID/CLOUD_HIGH) 분포 →
  로컬:클라우드 비율 / `cost_krw`·`input_tokens`·`output_tokens`·`latency_ms`(실측, `est_*`와 별개 키) / `cache_hit`
- `GET /v1/me/harness-metrics`(api/me.py:1853): 대리 지표 7종 — verify 통과율 등
- `GenerationLog` 테이블: 호출별 토큰·지연 실측(배치 회계)

---

## 결과표 (Kiki 실측 후 기입 — 빈칸 = 미측정)

### 비용 (루프당·티어별)
| cost_tier | 호출 수 | cost_krw (합/평균) | input/output tokens (평균) | 비고 |
|---|---|---|---|---|
| LOCAL | | 0.0 (로컬) | | 라우터 목표 80% |
| CLOUD_MID | | | | Sonnet 경로 |
| CLOUD_HIGH | | | | Opus 경로 |
| **로컬:클라우드 비율** | | | | S1 게이트② 판정선(로컬 ≥80%) |

### 지연
| 경로 | p50 latency_ms | p90 latency_ms | 비고 |
|---|---|---|---|
| LOCAL (Ollama) | | | |
| CLOUD_MID | | | |

### verify verdict 분포 (게이트 승격 근거)
| verdict | 비율 | 비고 |
|---|---|---|
| correct | | |
| incorrect | | |
| unverifiable | | undecidable 보수 처리 비율 |

### 판정 (실측 후)
- [ ] 루프당 비용 실측 완료·로컬 ≥80% 여부:
- [ ] verify 커버리지 게이트 primary 승격 가부:
- [ ] MEMORY.md 결정로그 append:

---

## 이후 연결
- 이 표가 채워지면 **S1-12 done** → S1-13(비용/지연 보정·프롬프트 캐싱)·S2-01(동등문제 100+, +G-crosswalk-approval) 해금.
- **S1-11**(coach→하네스 단일 수렴)은 이 실측 + 라이브 shadow verdict 분포를 근거로 학생-대면 primary 승격 판정 후 착수("측정 없는 도입 없음").
- 주의: **rephrase 산출물은 커밋하지 않는다**(v0 사람 검수 전·라이브 LLM 결과 미커밋 규약).
