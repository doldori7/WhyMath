# 측정 계측선 가동 런북 (Measurement Line Enablement)

> **작성일**: 2026-07-09 | **버전**: 1.0 | **범위**: 운영 런북(문서 전용) · **소관**: Kiki(라이브 머신·키) + 코어(코드 완비)
>
> **한 줄**: SSM 2026-Q3 스캔이 지목한 **"차분기 최우선 인에이블러 = 측정 계측선 가동"**을 실행하는 절차. 파일럿 6건이 공통 선결로 대기하는 라이브 계측을 *어떤 순서로 켜는가*를 명문화한다.
>
> **핵심 전제(조사 결론)**: 6개 계측선은 **전부 코드/문서 배선 완료 — "코드 부재" 0건**. 단일 병목은 신규 개발이 아니라 **키 투입 · GPU 활성 · 라이브 표본 축적**이다. 이 문서는 *켜는 순서*이지 *만드는 계획*이 아니다.

---

## 1. 목적·배경

SSM 2026-Q3 스캔(`ssm_scan_2026-Q3.md`)의 결론: 유망 후보 6건이 전부 **파일럿(측정 후 재판정)**에 머물렀고, "도입 0"의 근본 원인은 신기술 부재가 아니라 **측정 계측선 미가동**이었다(라이브 키·Langfuse 실측선 부재). SSM 표준 §5-(b) "측정 없는 도입 없음"에 따라, 파일럿을 도입/기각으로 전진시키려면 먼저 계측선을 켜서 베이스라인을 확립해야 한다.

이 런북은 그 인에이블 절차다. 대상 계측 코드는 이미 배선돼 있으므로(§2), 실행은 **Kiki 라이브 머신에서 키·GPU·모델을 켜고 → 완비된 도구를 순서대로 호출**하는 것으로 완료된다.

---

## 2. 현재 상태표 (배선 vs 대기 요인)

| # | 계측선 | 코드/문서 위치 | 배선 상태 | 대기 요인 |
|---|---|---|---|---|
| 1 | WH-1 대리 지표 11종 계산 | `harness/wh1_evaluation.py::compute_wh1_surrogate_metrics` | ✅ 완비 | **DB 표본**(NO_DATA→MEASURED 전환 대기) |
| 2 | 코호트 베이스라인 리포트 CLI | `harness/surrogate_baseline_report.py` | ✅ 완비 | **라이브 PG 연결**(전체 `pragma: no cover`) |
| 3 | Langfuse 트레이싱(config·sink) | `config.py` `langfuse_*` · `l3/trace/langfuse_sink.py` | ✅ 완비 | **라이브 키 미투입**(`langfuse_configured=False`→no-op) |
| 4 | 비용/지연 계측 | `l3/router.py` 단가표·`langfuse_fields()` | ✅ 구조 완비 | **실측 토큰 p50**(지연은 placeholder) |
| 5 | 라이브 프리플라이트 검증 | `ops/live_preflight.py`(±`--via-pipeline`) | ✅ 완비 | **키 + GPU + 모델 pull** |
| 6 | 6 파일럿 측정 지표 정의 | `ssm_scan_2026-Q3.md` 게이트 대기 큐 | ✅ 명시 | **위 1~5 가동 전제** |

> 정직성 설계: 지표는 `Metric(value|None, status)` 구조(`MetricStatus`: MEASURED/NO_DATA/NOT_INSTRUMENTED/REQUIRES_DATA/REQUIRES_TOOL). 가짜 0/stub 금지 — 미계측은 `value=None`. 켜지면 자동으로 NO_DATA→MEASURED.

---

## 3. 단일 병목 = 4 인에이블러

| 인에이블러 | 무엇 | 켜는 주체 |
|---|---|---|
| **A. Langfuse 키** | `WHYMATH_LANGFUSE_PUBLIC_KEY`·`WHYMATH_LANGFUSE_SECRET_KEY` 주입 → 트레이스 축적 활성 | Kiki |
| **B. Anthropic 키** | 클라우드 티어 실측(비용·지연) 스모크·라이브 라우팅 | Kiki |
| **C. Phaiakes9 GPU + 모델 pull** | 로컬 tok/s·p50 실측(게이트 p50<2s) | Kiki(하드웨어) |
| **D. 라이브 트래픽/DB 표본** | 지표 11종 NO_DATA→MEASURED, 실측 토큰 p50 | 사용(β) 축적 |

*A·B·C는 즉시 조치, D는 사용 축적(시간)*. 그래서 런북은 A/B/C를 먼저 켜고(S1·S2), D를 축적하며 베이스라인을 캡처(S3)한 뒤 실측 보정(S4)한다.

---

## 4. 가동 런북 (순서)

### S1. 키 투입 + 프리플라이트 (인에이블러 A·B)
1. 라이브 머신에 env 주입: `WHYMATH_LANGFUSE_PUBLIC_KEY`, `WHYMATH_LANGFUSE_SECRET_KEY`, Anthropic 키(`anthropic_configured` 충족). **시크릿은 env만 — 코드/문서 하드코딩 금지**.
2. 키 투입 **직후 1회**: `python -m whymath_backend.ops.live_preflight --via-pipeline`
3. 확인(수용): 판정 ①`anthropic_configured`·②`langfuse_configured` 모두 true · Anthropic/Ollama 도달성 OK · CLOUD_MID(Sonnet) 스모크 1콜 **실측 usage→`actual_cost_krw`** 산출 · Langfuse `l3_routing` 이벤트 **실제 기록**(`--via-pipeline`가 라우터→캐시→provider→sink 전 결선 통과·`flush()`).

### S2. Phaiakes9 GPU 활성 + 모델 pull (인에이블러 C)
1. GPU 활성: `infra/phaiakes9/GPU_ACTIVATION_FOLLOWUP.md` 절차(BIOS UMA Frame Buffer=Fixed·커널 6.18.4+·ROCm 7.2.0+, Radeon 8060S/Strix Halo gfx1151).
2. 모델 pull: `infra/phaiakes9/LIVE_LLM_ACTIVATION.md`의 6종(qwen2-math:1.5b/7b·qwen2.5:3b/7b·qwen3.5:27b·qwen3-vl:8b).
3. 확인(수용): fast tier(qwen2-math:1.5b) **p50<2,000ms**(L3 SLA 게이트) 재확인 · 7B tok/s 목표 60~150(GPU 5~12x).

### S3. 표본 축적 + 베이스라인 캡처 (인에이블러 D)
1. β 트래픽/DB 축적(세션·attempt·dialogue).
2. 코호트 베이스라인: `python -m whymath_backend.harness.surrogate_baseline_report`(`--since/--until` 선택, 기본 전체 코호트). 실 PG 연결에서 실행.
3. 확인(수용): 커버리지 **MEASURED n/11** 상승(NO_DATA→MEASURED) · R15 결합 판정(도움 감소×정답률·난이도) 정상.

### S4. 비용/지연 실측 보정 (인에이블러 A·B 산출물 활용)
1. Langfuse 실측 토큰 p50 확보 → `l3/router.py` `_EST_ASSUMED_INPUT_TOKENS`·`_EST_ASSUMED_OUTPUT_TOKENS`에 대입 → `CLOUD_MIN_COST_KRW` **자동 재계산**(단일 공식).
2. `CLOUD_LATENCY_MS`(MID=3000·HIGH=8000 placeholder) 실측 보정 · `USD_TO_KRW=1540` 라이브 확인.
3. 확인(수용): 추정 vs 실측 괴리(스캔 시점 1/69) 해소 · §4 비용/지연 드리프트 트리거 계측선 실측화.

---

## 5. 파일럿 ↔ 계측선 매핑

각 파일럿이 어느 단계가 켜지면 측정 가능한가:

| # | 파일럿 | 필요 측정 | 선결 단계 |
|---|---|---|---|
| 1 | DeepSeekMath V2/V3.2 | Phaiakes9 서빙 tok/s·p50 + 수학 정확도 A/B | **S2**(+S1 트레이스) |
| 2 | PRM 재랭킹 | L3 검증 커버리지·PRM 통과율 델타 | **S1·S3**(WH-S S2~S3 연계) |
| 4 | NuminaMath-1.5 | (측정 아님) 합성분 약관 법적 검토 | **별개**(법적 게이트·`licensing_safety.md`) |
| 8 | Qwen3-Embedding | 한국어 의미검색 품질 A/B vs bge-m3 + 8B 비용/지연 | **S1·S3·S4** |
| 10 | PaddleOCR-VL | 한국어 손글씨 정확도(목표 90%) 실측 vs 하이브리드 | **S2**(OCR 벤치) |
| 12 | 교수학 평가 루브릭 | 프롬프트 템플릿 루브릭 자체 평가·회귀테스트 | **부분 선행 가능**(WH-1 자체평가·`prompt_engineering.md`, 라이브 키 불요) |

> #4는 계측이 아니라 법적 게이트라 계측선과 무관. #12는 WH-1 오프라인 자체평가로 일부 선행 가능(라이브 계측 불요) — 나머지 5건은 S1~S4 가동이 전제.

---

## 6. 수용 게이트 (계측선 "가동됨" 판정)

- [ ] **S1**: `live_preflight --via-pipeline` green — 판정 ①② true·스모크 실측 비용 산출·Langfuse 이벤트 기록.
- [ ] **S2**: qwen2-math:1.5b p50<2,000ms 재확인·7B tok/s 목표 도달.
- [ ] **S3**: 베이스라인 리포트 커버리지 MEASURED n/11(핵심 지표 verify율·완주율·보정·전이 중 다수 MEASURED).
- [ ] **S4**: 추정 vs 실측 비용 괴리 해소·지연 placeholder 실측 대체.
- [ ] 종합: 파일럿 5건(#1·2·8·10·12)이 "측정 가능" 상태로 전환 → SSM 게이트 재판정 착수 가능.

---

## 7. 소관·경계

- **Kiki 수동**(범위 밖): 라이브 키(Langfuse·Anthropic) 발급·주입, Phaiakes9 GPU 활성(BIOS·커널·ROCm), 모델 6종 pull, β 트래픽 확보.
- **코드(완비·신규 개발 0)**: 지표 계산·베이스라인 CLI·프리플라이트·Langfuse sink·비용 공식 — 전부 존재. 이 런북은 *호출 절차*만 기술.
- **SSM 연결**: S1~S4 가동 → 베이스라인 확립 → 파일럿 6건을 SSM 도입 게이트(§5)에서 재판정. 다음 분기 스캔(2026-Q4) 전 완료가 이상적.
- **금지**: 시크릿 값·키 코드/문서 하드코딩(env 키 *이름*만 참조).

---

**연계 문서**: `system_superiority_maintenance.md`(SSM 표준·게이트) · `ssm_scan_2026-Q3.md`(파일럿 6건·메타 발견) · `../architecture/04a_wh1_tutoring_harness.md` §8.4(지표 설계 정본) · `../../infra/phaiakes9/GPU_ACTIVATION_FOLLOWUP.md`·`LIVE_LLM_ACTIVATION.md`(하드웨어 절차) · `../../MEMORY.md`(비용 구조·프리플라이트 결정 로그).
