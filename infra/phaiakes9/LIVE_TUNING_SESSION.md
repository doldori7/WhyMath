# Phaiakes9 라이브 튜닝 세션 — 복붙 체크리스트 + Langfuse 대시보드 명세

> **목적**: 라이브 키 투입 후, 실 트래픽으로 **3레버(루프당 비용 · guard_cloud 임계값 · OCR 실성능)**를 한 세션에서
> 순차 튜닝한다. Kiki가 그대로 복붙·실행하는 절차서 + 무엇을 어디서 관찰하는지(대시보드 패널 명세).
>
> **전제**: 관측 배선은 *이미 코드에 있다*. 이 문서는 새 코드가 아니라 **세션 절차 + 대시보드 명세**만 신설한다.
> 선행 런북: `LIVE_LLM_ACTIVATION.md`(§8 로컬 활성화·§10 클라우드/관측성·§11 계측 판독) · `OCR_LIVE_VERIFICATION.md`.
>
> **정직성**: est 비용 구조는 개선됐으나(PR #484 단일 공식) **수치 튜닝은 실 트래픽 대기**다 — 프리플라이트 1콜
> (비대표)로 수치를 내리지 말 것. 이 세션이 "대표 트래픽 p50"을 처음 확보하는 자리다.

---

## 0. 세션 전 준비 (한 번)

1. 라이브 env 4종 세팅 — `LIVE_LLM_ACTIVATION.md §10`(`:216-221`)의 표 그대로:
   `WHYMATH_ANTHROPIC_API_KEY` · `WHYMATH_ANTHROPIC_MODEL_MID`/`_HIGH` · `WHYMATH_LANGFUSE_PUBLIC_KEY`/`_SECRET_KEY` · `WHYMATH_LANGFUSE_HOST`.
   - ⚠️ `.env` 저장 시 **BOM 금지** — PowerShell은 `Set-Content -Encoding ascii`(utf8은 BOM을 붙여 첫 키 줄을 깨뜨림).
   - ⚠️ 모델 ID는 실재하는 값이어야 함(오타 시 런타임 404).
2. venv 활성 · 작업 디렉토리 `src/backend`.

---

## 1. 활성 확인 (게이트) — 프리플라이트 1콜

```bash
python -m whymath_backend.ops.live_preflight --via-pipeline --json preflight.json
```

**통과 판정**(종료코드 0):
- `[판정] ① cloud_configured = 예` (`Settings().anthropic_configured`)
- `[판정] ② langfuse_configured = 예`
- `[도달성] Anthropic reachable · Ollama reachable`
- `[③ 스모크]` CLOUD_MID 실 1콜 → `실측 비용(cost_krw)` · `입력/출력 토큰` · `지연(latency_ms)` 출력 + **`Langfuse 기록·flush 완료`**.

> ⚠️ 이 1콜의 토큰(수십/수 토큰)은 **비대표**다. 여기 비용으로 상수를 바꾸지 말 것 — 아래 2단계에서 *실 튜터링 트래픽 p50*를 모은다.
> Langfuse 미설정이면 파이프라인 호출 없이 graceful skip(값 관찰 불가) → env 먼저 고칠 것.

---

## 2. 레버 A — 루프당 LLM 비용 (est ↔ actual 수렴)

**무엇을 보나**: Langfuse `l3_routing` 이벤트(이벤트명 `l3/trace/langfuse_sink.py`의 `_EVENT_NAME`). 필터 태그
`cost_tier:CLOUD_MID`(및 `CLOUD_HIGH`)로 좁혀, 실 튜터링 트래픽이 어느 정도 쌓인 뒤:

| 수집 필드 | 의미 | 튜닝 반영처 |
|---|---|---|
| `input_tokens` / `output_tokens` (실측) | 클라우드 턴 실 토큰 | **p50를 `l3/router.py`의 `_EST_ASSUMED_INPUT_TOKENS`(:129)·`_EST_ASSUMED_OUTPUT_TOKENS`(:132)에 대입** |
| `cost_krw` (실측) | 클라우드 턴 실 비용(원) | 학생당 월 환산 → 목표 <1,000원 대조 |
| `est_cost_krw` (추정) | 라우터 사전 추정(원) | actual과 산점도 비교(추정 정확도) |

**절차**:
1. 대표 트래픽(실 튜터링 턴 수십~수백) 축적을 기다린다. *프리플라이트 1콜로 하지 않는다.*
2. `cost_tier:CLOUD_MID`의 `input_tokens`·`output_tokens` **p50**를 읽는다.
3. `_EST_ASSUMED_INPUT/OUTPUT_TOKENS`에 그 p50를 대입 → `CLOUD_MIN_COST_KRW`가 **단일 공식으로 자동 재계산**된다
   (하드코딩 아님 — `router.py:143` 유도식 = 가정토큰 × `CLOUD_TOKEN_PRICE_USD_PER_1M`(:108) × `USD_TO_KRW`(:115)).
   현재 값 ≈ MID 27.72 / HIGH 46.2원(보수적 1K+1K).
4. `est_cost_krw` vs `cost_krw` 산점도가 대각선에 붙는지 확인(추정이 실측을 잘 예측하면 guard가 정확해짐).

> 근거: `router.py:118-134` 주석("라이브 트래픽 p50를 `_EST_ASSUMED_*`에 대입 → `CLOUD_MIN_COST_KRW` 자동 재계산"). PR #465(계측)·#484(est 단일 공식)의 후속.

---

## 3. 레버 B — guard_cloud 임계값 (LOCAL↔CLOUD 분포)

**무엇을 보나**: `cost_tier` 분포가 목표 **80/18/2(LOCAL/CLOUD_MID/CLOUD_HIGH)**에 수렴하는지(`03a_l3_router_design.md §E.3`).

**레버(조정 ↔ 효과)** — `l3/router.py`:
- `DAILY_LIMIT_KRW`(:94, free 100/basic 500/premium 2000/gifted 5000원) — 올리면 `budget_krw`↑ → `guard_cloud`(:288) 통과율↑ → 클라우드 비율↑. (한도는 클라우드 호출에만 차감·로컬 0원.)
- `_EST_ASSUMED_*` p50 하향(레버 A) → `cloud_min_cost`↓ → 같은 budget에서 guard 통과율↑.
- `USD_TO_KRW`(:115) — 환율 실보정만(분포 레버 아님).

**판정**: LOCAL 80% 미달이면(클라우드 과다·비용↑) 위 레버로 재조정. `guard_cloud` 규칙은 `router.py:288-303`
(①free→LOCAL ②`budget_krw < cloud_min_cost`→LOCAL ③HIGH희망+basic→MID 제한), 축1 결정은 `_decide_cost_tier`(:519).

---

## 4. 레버 C — OCR 실성능 (Qwen3-VL 실모델)

**절차**: `OCR_LIVE_VERIFICATION.md`의 extras 설치(§2)·모델 pull(§3)·env(§4)·`/v1/ocr` 스모크(§5)를 따른 뒤 분포 관찰.

**무엇을 보나**(`schema/ocr.py`):
- `overall_confidence`(평균, :166) · `min_confidence`(최솟값, :175) 분포.
- `needs_reconfirmation`(페이지 OR, :181) 발생률.
- coach `match_low_quality` 발생률(`api/coach.py:290`) — OCR 저신뢰 게이트.
- Qwen3-VL 호출은 L3 라우터 경유(`l5/ocr/recognize.py`)라 **`l3_routing`에 `cost_tier:LOCAL`·vision으로 latency_ms 흐름** → 지연도 대시보드에서 관찰.

**레버(조정 ↔ 효과)**:
- `WHYMATH_OCR_MIN_CONFIDENCE`(`config.py:915`, 기본 0.0=필터 비활성) — 올리면 저신뢰 인식이 `needs_review`로 강등(비파괴).
- coach 게이트 `ocr_confidence < 0.8`(`api/coach.py:230`) — OCR 저품질 시 코칭 강등 임계. `ocr_min_confidence`(영역 레벨)와 **독립**.

> 손글씨 오인식 보호가 목적 — 임계를 올리면 재확인 요구↑(안전)·통과율↓(마찰). 실 손글씨 표본으로 균형점 탐색.

---

## 5. Langfuse 대시보드 패널 명세 (신규)

`l3_routing` 이벤트를 소스로 아래 패널을 구성한다. 필드 근거: `router.py:396-414`(`langfuse_fields()`) · `03a §F.2`(`:414-430`).
(모든 필드는 이벤트 metadata에 실재. 태그 필터: `cost_tier`·`local_family`·`local_model`·`cache_hit`.)

| # | 패널 | 소스 필드 | 읽는 법 / 목표선 |
|---|---|---|---|
| P1 | **cost_tier 분포**(파이/스택) | `cost_tier` | LOCAL/MID/HIGH 비율 → 목표 **80/18/2** |
| P2 | **cost_krw 시계열 + 학생당 월 환산** | `cost_krw`·`student_id_hash` | 학생당 월 LLM 비용 **목표 <1,000원**(business_model) |
| P3 | **est vs actual 산점도** | `est_cost_krw` × `cost_krw` | 대각선 근접 = 추정 정확(guard 신뢰). 이탈 = 레버 A 재튜닝 |
| P4 | **지연 p50/p90 by 모델** | `latency_ms` × `local_model` | SLA 게이트 **2000ms**(동기만)·벤치 회귀 감시 |
| P5 | **캐시 적중률** | `cache_hit` | 캐싱 KPI(비용 절감) |
| P6 | **에스컬레이션·호출지점 분포** | `escalated_from`·`call_site` | 티어 상향 빈도·①~⑤ 지점 편중 |
| P7 | **NLP 라우팅 검증** | `local_family`·`reason` | GENERAL 라우팅(NLP→general/fast)이 실제 작동하는지 |
| P8 | **OCR 신뢰도**(별도 소스) | `overall_confidence`·`needs_reconfirmation` | 손글씨 인식 품질·재확인 발생률 |

**보조 판독 경로**(대시보드 외): `GET /v1/me/harness-metrics`(`api/me.py`, `tokens_per_turn` 등 대리지표 7종·`NO_DATA`→`MEASURED` 전환) · `GenerationLog` 테이블 · 프리플라이트 `--json` 리포트.

---

## 6. 세션 종료 체크

- [ ] `_EST_ASSUMED_*`를 실 p50로 갱신했는가(또는 "표본 부족"으로 다음 세션 이월 결정).
- [ ] `cost_tier` 분포가 80/18/2 밴드인가 / 이탈 시 `DAILY_LIMIT_KRW` 조정.
- [ ] 학생당 월 비용 환산이 <1,000원인가.
- [ ] OCR `needs_reconfirmation` 발생률·`ocr_min_confidence` 균형점 기록.
- [ ] 변경한 상수는 **MEMORY.md 결정 로그**에 근거(수집 p50·표본 수)와 함께 남긴다 — "비대표 표본으로 수치 변경 금지" 원칙 준수.

---

**참조**: `LIVE_LLM_ACTIVATION.md`(§8·§10·§11) · `OCR_LIVE_VERIFICATION.md` · `docs/architecture/03a_l3_router_design.md`(§E.3·§F.2·§H) · `src/backend/whymath_backend/l3/router.py`·`ops/live_preflight.py`·`l3/trace/langfuse_sink.py`.
