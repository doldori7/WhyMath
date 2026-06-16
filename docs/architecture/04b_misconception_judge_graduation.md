# 04b. 오개념 Judge 졸업 설계 — 실시간 coach 결선

> **상태**: 제안 (2026-06-16) · **계층**: L4 교수학 엔진
> **관련**: `04_pedagogy_engine.md` · `04a_wh1_tutoring_harness.md` · `03a_l3_router_design.md`(라우팅) · `docs/prompts/misconception_judge.md`(판정 프롬프트) · `MEMORY.md`(측정 결과) · PR #213·#214·#215

---

## 1. 목표

오개념 방향 판별 **judge**(LLM)를 *측정 전용*에서 **실시간 coach 노출**로 졸업시킨다.
judge는 의미(임베딩) 매칭이 끌어올린 오개념 후보 중 *방향·부정·등치가 어긋난*(`NOT_EXPRESSES`) 것을
걸러, 학생에게 *맞지 않는* 오개념으로 코칭하는 거짓양성(=오도된 가르침·의사결정 우선순위 #1·#3)을 줄인다.

judge는 **제거만** 하고 *생성하지 않는다* → 실패모드 = 과소코칭(안전) ≠ 오도된 가르침(위험).

---

## 2. 측정 근거 (요약 — 상세는 `MEMORY.md` 2026-06-15~16)

- **judge 개념 유효**: `general_mid`(qwen2.5:7b)는 한국어 판정 형식 100% 준수(uncertain 0). 기본
  `fast_math`(qwen2-math:1.5b)는 형식 미준수로 전부 UNCERTAIN(무효) — **모델 선택이 관건**.
- **매처는 방향맹**: `--sweep`(0.3~0.85) 결과 *좋은 임계값이 없음* — recall·FP가 함께 붕괴.
  "둘레가 길면 넓이도 크다(틀림)"와 "둘레가 길어도 넓이는 작을 수 있다(맞음)"가 같은 주제어라
  코사인이 거의 같다 → **judge가 유일 해법**.
- **judge-feed 최적 ≈ threshold 0.40**: 최종 recall 75.4% / FP 45.5%(매처 recall 정점·FP 포화).
  judge 판정율은 *임계값-무관 안정*(recall keep ~84% · FP remove ~55%).

  | judge-feed threshold | 최종 recall | 최종 FP | judge 호출 |
  |---|---|---|---|
  | 0.55 | 50.8% | 39.4% | 140 |
  | 0.50 | 65.6% | 45.5% | 337 |
  | **0.40** | **75.4%** | 45.5% | 468 |

- **두 천장**: 매처 recall 86.9%(임베딩 한계) · judge FP제거 54.5% → **잔여 FP 45.5%**(7b 한계).

---

## 3. 현 배선 현황 — 졸업이 *config 플립*인 이유

| # | 사실 | 근거(file) |
|---|---|---|
| 1 | judge 게이트 **이미 배선**(flag off) — on이면 품질게이트 *이전*에 `judge_filter` 적용 | `api/coach.py:515` · seam `_judge_for_gate`=`LLMJudge(L3JudgeSeam())` `api/coach.py:443` |
| 2 | seam이 `misconception_judge_routing`을 **존중**(general_mid 그대로 먹음) | `l4/misconception/judge_seam.py:30` |
| 3 | coach는 **단정 안 함·소크라테스 탐문**(conf>0.8 반례·0.5~0.8 역추론·<0.5 무노출) | `l4/misconception/intervene.py:50` |
| 4 | **신뢰도 게이트**(개입 ≥0.5·top-1 0.65)가 FP 2차 필터 → *실노출 FP < 측정 45.5%* 가능 | `api/coach.py` 품질게이트 |
| 5 | judge 호출 **병렬**(`asyncio.gather`) → 지연은 *서빙 동시성* 문제(코드 아님) | `l4/misconception/judge.py:230` |
| 6 | **shadow 경로 존재**(semantic만 그림자·학생원문 미저장) — 단 semantic+judge 전체는 미그림자 | `api/coach.py:541` · `l4/misconception/shadow.py:57` |

→ **졸업 ≠ 새 배선. = 플래그 플립 + 단계 검증.** (judge 코어·intervention 트리·Polya 무대 프롬프트 불변.)

---

## 4. 졸업 상태 (config)

```
misconception_semantic_mode      = on          (현 off)       # 의미 후보를 노출에 결합
misconception_judge_enabled      = true        (현 false)     # judge 필터 on
misconception_judge_routing      = general_mid (현 fast_math) # qwen2.5:7b (형식 준수)
misconception_semantic_threshold = 0.40        (현 0.55)      # recall-max (judge가 FP 필터)
```

모두 `config.py`의 `Settings` 필드(WHYMATH_ env 오버라이드) — 코드 변경 없이 단계별로 켤 수 있다.

---

## 5. 단계별 롤아웃

### Phase 1 — 전체 파이프라인 shadow (실트래픽·무노출)
- **왜**: 합성 94프로브 ↔ 실학생 표현 사이 갭. 노출 전에 *실데이터*로 judge verdict 분포·would-be
  개입률·신뢰도게이트 통과율을 확인(합성 결과 75.4%/45.5% 검증).
- **작업**: 현 shadow가 *semantic만* 로깅 → **semantic@0.40 후보에 judge를 돌려 *걸러질 결과*를
  로깅**하도록 확장(verdict·obc id·counts; **학생원문 미저장** 불변). `shadow.py` + `coach.py:541` 분기.
- **게이트**: `semantic_mode=shadow` + `judge_routing=general_mid` + (신규) judge-shadow 토글.

### Phase 2 — canary ON (소수 노출)
- 4플래그 on을 *일부 코호트/비율*에 한정(canary 게이트).
- **모니터**(Langfuse 이미 배선): 실백엔드 judge 지연 · 개입률 · 학생 반응(탐문에 교정하는가) · 해악 신호.
- **운영점 확정**: 0.40 유지 여부를 *실노출 FP*·학생 반응으로 검증.

### Phase 3 — full ON + 잔여 FP 후속
- canary 양호 → 전면 on.
- **잔여 FP 45.5% 후속**(별도 슬라이스·졸업 비차단): `qwen3.5:27b` QUALITY judge로 더 깎음 — 단
  QUALITY는 *async 전용*(03a §A.1·D.3)이라 현 sync `L3JudgeSeam` 밖 → **async judge seam** 필요.

---

## 6. 결정 + 근거

| # | 결정 | 채택 | 근거 |
|---|---|---|---|
| 1 | 운영점 | **threshold 0.40 (recall-max)** | 소크라테스 탐문 + 신뢰도게이트로 FP 저해악 → recall 우선 |
| 2 | 롤아웃 | **shadow → canary → full** | 합성↔실 갭 · 지연 미지수 de-risk |
| 3 | 지연 | **shadow 실측 → 캐시 + 배치서빙(Phaiakes9)** | 코드 병렬 완비 · 관문은 서빙 동시성 |
| 4 | 잔여 FP | **감내 + 27b async 후속**(졸업 비차단) | 탐문이라 45% 감내 가능 |

---

## 7. 슬라이스 계획

| 슬라이스 | 범위 | 크기 | 의존 |
|---|---|---|---|
| **G1** | shadow에 semantic+judge *would-be* 로깅 (Phase 1) | 소 | 현 shadow · judge |
| **G2** | canary 게이트 + 4플래그 on (Phase 2) | 소~중 | G1 검증 |
| **G3** | full on (Phase 3) | 설정 | G2 모니터 |
| F1(후속) | async QUALITY(27b) judge seam — 잔여 FP | 중 | 03a async/Celery |
| F2(후속) | judge verdict 캐시 — 지연 | 소 | L3 캐시 |
| F3(후속) | 매처 recall 개선(카탈로그/임베딩) — recall 천장 | 중 | L4 카탈로그 |

---

## 8. 리스크 / 열린 질문

- **실트래픽 분포 ≠ 합성**: 실학생 패러프레이즈가 더 다양·모호 → judge/매처 성능이 달라질 수 있음.
  → **Phase 1 shadow가 해소.**
- **지연(서빙)**: 단일 Ollama는 직렬화(측정서 후보당 ~5초). 프로덕션 배치서빙(vLLM 등) 동시성 미검증.
  → **Phase 2 canary가 실측.**
- **신뢰도 게이트 상호작용**: 0.40이 저신뢰 후보를 많이 들이지만 노출은 ≥0.5만 → *실노출 FP가 측정보다
  낮을* 수 있음(긍정). → shadow에서 정량화.
- **프라이버시(미성년)**: shadow 확장 시 *학생원문 미저장* 불변 준수(현 `shadow.py` 비식별 레코드 패턴).
- **judge LLM 검증**: judge는 *제거만*·never-break(예외→UNCERTAIN→유지) → 가용성·안전 보존
  (CLAUDE.md "LLM 응답 검증 없이 학생 제공 금지"는 judge가 *후보를 줄일 뿐 생성 안 함*으로 충족).

---

## 9. 비목표 (이 설계 범위 밖)

- judge 판정 프롬프트·오개념 카탈로그 변경(별도) · 매처 임베딩 모델 교체(F3) ·
  QUALITY async 인프라(F1) · coach intervention 트리·Polya 무대 프롬프트 변경(불변).

---

**버전**: 0.1 (제안) · **작성**: 2026-06-16 · **다음**: Kiki 검토 → G1(shadow) 착수
