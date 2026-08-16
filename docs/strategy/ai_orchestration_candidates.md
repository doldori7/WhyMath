# WhyMath AI 오케스트레이션 후보 리스트

> **기준일**: 2026-08-14  
> **출처**: [Arena AI Leaderboard](https://arena.ai/leaderboard/), [OpenRouter Rankings](https://openrouter.ai/rankings#benchmarks), [OpenRouter](https://openrouter.ai/)  
> **목적**: 7계층 아키텍처(L3 콘텐츠 생성·검증, L4 교수학 엔진, L6 응용 모드)에 배선할 LLM 후보를 외부 리더보드 기준으로 정리.  
> **주의**: 아래 순위는 2026-08-14 기준 공개 리더보드의 "종합/다부문" 섹션 순위를 재구성한 것으로, WhyMath 도메인(한국어 중·고등 수학)에서의 실제 성능과는 별도 측정이 필요하다.

---

## 1. 선정 기준

WhyMath는 "답이 아닌 이유를 묻는 수학"이므로 모델 선정은 단순 벤치 순위가 아닌 아래 축으로 평가한다.

| 축 | 가중 | 평가 항목 |
|---|---|---|
| 수학·추론 | 높음 | 대수·확률·기하·증명에서의 단계적 추론, 자기검증, PRM 적합성 |
| 한국어 | 높음 | 한국어 수학 용어·존댓말 코칭·문맥 유지 |
| 비용 | 중간 | 1k token당 가격, 일일 예산, 구독 모델 적합성 |
| 지연 | 중간 | p50 응답 지연, 동기 경로 SLA 2초 게이트 |
| 도구/검증 | 중간 | JSON schema 준수, 함수 호출, SymPy/Lean 연동 용이성 |
| 비전 | 낮음~중간 | 사진 입력(OCR 전)·필기 인식, 현재는 OCR 후 텍스트 파이프라인 우선 |

> **운영 원칙**: 현재 라우터는 로컬(Ollama) 80% · 중급 클라우드(Anthropic Sonnet 4.6) 18% · 고급 클라우드(Anthropic Opus 4.7) 2% 목표. OpenRouter는 S4-16 harness 임시 경로로만 사용하며, 운영 라우터에 직접 연결하지 않는다.

---

## 2. Tier 1 — 운영 고려 후보 (종합 상위 + 한국어·수학 검증 우선)

| 후보 | OpenRouter ID | Arena AI 종합 | WhyMath 용도 | 평가 |
|---|---|---|---|---|
| **Claude Sonnet 4.6** | `anthropic/claude-sonnet-4-6` | 상위권 | 코칭·프롬프트 정렬·자기검증 | 현재 운영 중급 클라우드. 한국어·지시 따르기 우수. 비용 $3/$15 per 1M. |
| **Claude Opus 4.7** | `anthropic/claude-opus-4-7` | 상위권 | 어려운 진단·증명·오개념 분석 | 현재 운영 고급 클라우드. 복잡 추론에 강하나 비용 $5/$25 per 1M으로 제한적 사용. |
| **Qwen 3.8 Max** | `qwen/qwen3.8-max` | 8위 | S4-16 임시 교차검증·수학 추론 | OpenRouter intelligence 58.1(참고). 한국어·수학 성능 우수, 비용 중간. |
| **Kimi K3 Max** | `moonshot/kimi-k3-max` | 11위 | 한국어 수학 생성·긴 맥락 코칭 | Moonshot의 한국어 성능이 양호한 것으로 알려짐. 긴 컨텍스트에 유리. |
| **Gemini 3.1 Pro Preview** | `google/gemini-3.1-pro-preview` | 13위 | 비전+수학 통합(후보) | 구글 Gemini, 멀티모달 기본 강점. 현재 WhyMath는 OCR 후 텍스트 파이프라인이라 운영 배선은 제한적. |
| **Gemini 3 Pro** | `google/gemini-3-pro` | 14위 | 코칭·개념 설명 | 상위권. 한국어 처리 및 JSON schema 준수 추가 측정 필요. |
| **Qwen 3.7 Max Preview** | `qwen/qwen3.7-max-preview` | 25위 | 수학 추론·코드 생성 | Qwen 라인업 내 후속 모델. 3.8-max 대비 안정성·비용 trade-off 검토. |
| **Claude Sonnet 4.5 20250929** | `anthropic/claude-sonnet-4-5-20250929` | 30위/57위 | 중급 코칭·백업 | Sonnet 4.6의 이전 세대로 폴백/비교용. |
| **Qwen 3.5 Max Preview** | `qwen/qwen3.5-max-preview` | 39위 | 경량 수학 검증 | 비용 대비 수학 성능이 괜찮을 수 있으나 상위 모델 대비 정확도 하락 우려. |

---

## 3. Tier 2 — S4-16 임시·비교 측정 후보

S4-16 강등전은 K=3 교차검증을 로컬 Ollama로 통과하지 못해 OpenRouter를 통해 임시 클라우드 후보를 태우는 용도다. 이 모델들은 harness 측정용이지 운영 라우터에 직접 연결되지 않는다.

| 후보 | OpenRouter ID | Arena AI 종합 | S4-16 평가 |
|---|---|---|---|---|
| **Qwen 3.8 Max** | `qwen/qwen3.8-max` | 8위 | 기본값. 2026-08-14 기준 S4-16 첫 시도 모델. |
| **DeepSeek V4 Pro** | `deepseek/deepseek-v4-pro` | 50위 | OpenRouter 가격이 낮은 편. 한국어·JSON 안정성 추가 확인 필요. |
| **Gemini 3.7 Flash** | `google/gemini-3.7-flash` | 미측정/추론 | Flash 라인업으로 지연·비용 우선. 정확도 trade-off 측정 필요. |
| **DeepSeek V4 Flash** | `deepseek/deepseek-v4-flash` | 84위 | 비용 우선 후보. 강등전에서 정확도가 너무 떨어지면 제외. |

---

## 4. Tier 3 — 특수 목적 후보

| 후보 | OpenRouter ID | 용도 | 비고 |
|---|---|---|---|
| **Qwen3-VL 235B** | `qwen/qwen3-vl-235b-a22b-instruct` | 비전 수학(손으로 찍은 문제)·도표 | 현재는 OCR 후 텍스트 파이프라인이 운영이나, 향후 end-to-end 비전 경로 PoC 시 후보. |
| **Gemini 2.5 Pro / 3 Pro** | `google/gemini-2.5-pro`, `google/gemini-3-pro` | 멀티모달 + 긴 문서 | 교과서 페이지 전체 이미지 입력·개념도 추출 후보. |
| **Muse Spark 1.2 (xHigh)** | `meta/muse-spark-1.2-xhigh` | 4위(종합) | Meta 모델. 한국어·수학 도메인 적합성 미확인. |
| **GPT-5.6 Sol xHigh** | `openai/gpt-5.6-sol-xhigh` | 18위 | OpenAI 모델. Sol 시리즈는 추론에 특화된 것으로 보이나 정확한 OpenRouter ID 및 가격 확인 필요. |

---

## 5. WhyMath 라우터 배선 제안 (2026-08-14 임시)

### 5.1 운영 라우터(현행 유지)
- **FAST/로컬**: `qwen2-math:1.5b`(산술 1단계), `qwen2.5:3b`(NLP 추출/매칭)
- **MID/로컬**: `qwen2-math:7b`(2~3단계 추론), `qwen2.5:7b`(NLP 번역/정규화)
- **QUALITY/로컬**: `qwen3.5:27b`(검증·복잡추론·비동기)
- **CLOUD_MID**: `claude-sonnet-4-6`(코칭·자연어)
- **CLOUD_HIGH**: `claude-opus-4-7`(어려운 진단·오개념)

### 5.2 S4-16 harness 임시
- **OpenRouter 고정**: `qwen/qwen3.8-max` 기본, 후속 비교 측정으로 `deepseek/deepseek-v4-pro`, `google/gemini-3.7-flash` 교체 실험.

### 5.3 추가 검토가 필요한 모델
- **Kimi K3 Max**: 한국어 코칭 품질 실측이 필요함.
- **Gemini 3.1 Pro/3 Pro**: JSON schema + SymPy 연동 안정성 실측.
- **Qwen 3.7/3.8 Max**: PRM 단계검증과의 결합 실측.

---

## 6. 리스크 및 주의사항

1. **리더보드 ≠ 도메인**: Arena AI 순위는 일반 대화/추론 벤치에 가중되어 있어, 한국어 중·고등 수학에서의 실제 성능은 별도 측정(`harness/residue_gate_demotion_battle.py` 등)으로 검증해야 한다.
2. **비용 변동**: OpenRouter 가격은 공급자·모델 버전에 따라 수시로 변할 수 있다. 운영 배선 전 `actual_cost_krw` 기반 일일 예산 게이트를 통과시켜야 한다.
3. **API 키 보안**: OpenRouter API 키는 환경변수로 주입하며, 로그·이미지 레이어에 남기지 않는다. 노출 시 즉시 재발급한다.
4. **헤더 계약**: OpenRouter는 `HTTP-Referer`, `X-Title` 헤더를 요구할 수 있다. `_FixedModelOpenRouterProvider._build_client()`에 `default_headers`로 등록해야 연결된다.

---

## 7. 다음 행동

- [ ] S4-16 harness에서 `qwen/qwen3.8-max`로 결함 검출률 재측정.
- [ ] `deepseek/deepseek-v4-pro`와 `google/gemini-3.7-flash`로 동일 코퍼스 교차 비교.
- [ ] 한국어 수학 코퍼스(파일럿 확률 외)에서 Tier 1 모델별 코칭 품질 블라인드 평가.
- [ ] OpenRouter Auto Router 실험: 단일 모델 고정 vs OpenRouter market-routing의 비용·품질 trade-off.
