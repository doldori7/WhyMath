# 03c. 콘텐츠 전략 — 교수법-중립 DSL + Rendering Engine + 캐시 (L3/L5)

> **성격**: L3(콘텐츠 생성·검증)의 서브 설계 — `03`(무엇을) → `03a`(어떻게 라우팅) → `03b`(WH-S 솔버)에 이어
> **`03c`(무엇을 저장하고 무엇을 렌더 시점에 계산하는가)**. 교수법 *선택·적응*의 정본은 `04d_adaptive_pedagogy_engine.md`(L4/L2).
>
> **한 줄**: 콘텐츠(DSL)는 *교수법-중립*으로 한 번 생성해 영구 자산으로 저장하고, 학생 화면은 *런타임에 교수법
> 어댑터가 렌더*한다. "AI가 매번 *생성*"이 아니라 "AI가 *선택*하고 얇게 *렌더*"한다.

---

## 0. 왜 이 문서가 필요한가 (문제 정의)

과도한 AI 비용을 줄이려 콘텐츠를 미리 만들어 캐시하면 **개인화가 사라지고**, 매번 실시간 생성하면 **비용이
폭발한다**. 대부분의 AI 교육앱이 이 딜레마에서 무너진다. WhyMath의 해법은 *생성물*이 아니라 *자산의 축*을 바꾸는
것이다 — **교수 *방식*을 콘텐츠에서 분리**하여, 저장되는 것은 교수법-중립 지식 자산 하나뿐이고, 방식(설명/질문/
문제/비유…)은 렌더 시점에 학생 상태에 맞춰 얹는다.

이는 새 발명이 아니라 저장소가 이미 가진 불변식의 실현이다:
- **Renderer=Plugin** (구축 플레이북 8대 원칙 ④ — `CLAUDE.md`): Concept → Visualization/Teaching Intent → Renderer
  Adapter. *구현체 이름을 노드에 넣지 않는다*.
- **5대 분리** (`math_dsl_principles_review.md:50`): Concept ≠ Curriculum ≠ **Renderer** ≠ Prompt ≠ Misconception.
- **표현 ≠ 의미** (`CLAUDE.md` L55): 콘텐츠는 화면 문자열이 아니라 구조로 저장, 렌더는 클라가.

---

## 1. 교수법-중립 콘텐츠 DSL — 저장 자산 ("한 번 생성·영구 자산")

콘텐츠 DSL은 **"무엇을 가르치는가"만** 담는다. 교수 *방식*(강의식·발견학습·문답식·게임·탐구)은 **넣지 않는다**.

```
ConceptDSL(교수법-중립)
  name            개념명(과목 불변 id — 예: math.algebra.linear-equation)
  definition      정의(렌더러-중립 LaTeX + 구조 태그)
  examples        예시(구조화 — 숫자/맥락은 슬롯화)
  misconceptions  오개념 참조(id 배열·반응형·본문 미보유 — misconception_catalog 위임)
  relations       개념 관계(prerequisite 등·atom_node code 느슨참조)
  assessment      평가 재료(문항 시드·정답 판정 조건 — SymPy 검증 가능 구조)
```

- 이 계약은 **신규 저장 표면을 최소화**한다 — 기존 `db/models/concept_content.py`
  (`metaphor`·`misconception`·`formal_definition_internal`·`explanation`·memory cards)를 이 중립 계약으로
  **감사·정렬**하는 것이 1차 작업이다(새 테이블 신설이 아니라 기존 좌석의 중립성 확인·부족분 보강).
- 본문 표기는 **렌더러-중립 LaTeX + 구조 태그**(완전 AST 아님·화면 문자열 금지, `CLAUDE.md` L55).
- **금지**: `ConceptDSL`의 어떤 필드도 "이것은 소크라테스식으로 가르쳐라" 같은 *방식 지시*를 담지 않는다. 방식은
  §2 어댑터가 렌더 시점에 결정한다. (자기점검 항목 — §5.)

> **1단계 설계용 교수법과의 경계**: DSL을 *생성*할 때는 설계용 교수법(k_type별 CRA류 진행 — `04d §1`, 기존
> PED-01 `pedagogy_pack`)이 *무엇을 담을지*를 형성한다. 그러나 그 산출물인 DSL 자체는 방식-중립이다. "설계용
> 교수법은 DSL의 *생성기*에 작용하고, DSL의 *내용*에 각인되지 않는다."

---

## 2. Rendering Engine + 교수법 렌더러 어댑터 — 조합폭발의 해

**저장 = (중립 DSL, atom당 1) + (교수법 어댑터, N개·개념 무관).** 조합((atom × 교수법 × 난이도 × 상황))은 저장하지
않고 **렌더 시점에 계산**한다. 저장 자산이 *곱이 아니라 합*(`atoms + N`)이 되는 것이 이 설계의 핵심이다.

### 2.1 교수법 전략 폐쇄 enum `PedagogyStrategy`
`schema/enums.py`에 커널 소유 폐쇄 enum으로 신설(`KnowledgeType` 선례 — 폐쇄·거버넌스 전제·PG native).

| 값 | 렌더 성격 |
|---|---|
| `DIRECT` | 설명 중심(Direct Instruction) |
| `SOCRATIC` | 질문 중심(문답식) |
| `WORKED_EXAMPLE` | 완전예제 제시(⚠️ 냉담 제공 불가 — §3 게이트) |
| `PROBLEM_BASED` | 문제부터 제시 |
| `RETRIEVAL` | 인출 연습 중심 |
| `SPACING` | 분산 복습 |
| `INTERLEAVING` | 교차 연습 |
| `SELF_EXPLANATION` | 자기설명 유도 |
| `ANALOGY` | 비유 설명 |
| `VISUALIZATION` | 시각화 중심(렌더 intent → L5 시각화 명세) |

> **`GAME`(게임형) 초기 제외**: `CLAUDE.md` "무자비한 게임화·중독성 설계 금지"는 정체성 축이다. 게임형 전략의
> 추가는 별도 거버넌스 결정(중독성 없는 설계 명세 확정 후)을 전제한다 — enum 확장은 의도적 결정.

### 2.2 어댑터 계약 `l3/render/adapter.py`
```python
class PedagogyAdapter(Protocol):
    strategy: PedagogyStrategy

    def can_render(self, dsl: ConceptDSL) -> bool:
        """이 전략이 이 DSL을 렌더할 수 있는가(예: PROBLEM_BASED는 assessment 시드 필요)."""

    def render(self, dsl: ConceptDSL, ctx: RenderContext) -> RenderedUnit:
        """중립 DSL → 전략별 학생 화면 산출.
        - LLM=0 기본(결정론 템플릿 조립). 필요한 얇은 표면 변형만 §3에서 생성 폴백.
        - 재사용: josa.py(조사 일치)·rephrase.py(수식/수치 봉인)·verify_answer/canonicalize(렌더 후 검증).
        - 산출은 ValidationSignal(l3/pregenerate/models.py 재사용) 검증 통과분만 학생 노출.
        """
```

- **어댑터는 개념 무관** — `SOCRATIC` 어댑터 하나가 일차방정식·미분·확률 *모든* 개념에 작동한다. 개념별로 어댑터를
  복제하지 않는다.
- **어댑터는 순수 렌더** — 어떤 전략을 쓸지 *고르는* 책임은 어댑터가 아니라 `04d`의 Runtime Pedagogy Selector에
  있다(관심사 분리·L4 권위).
- **렌더러 구현명은 DSL에 없다** — 어댑터 레지스트리(`strategy → adapter`)가 plugin 경계다(Renderer=Plugin).

---

## 3. select-vs-generate (render-vs-generate) — 비용 계층

구현 정본: **`l4/content_supply.py`**(CACHE-01).

```python
async def supply(*, code, signals, session, cache, k_type=None, ...) -> SupplyResult:
    # ① 선택 + 교수학 게이트 — decide()를 *내부에서* 호출하므로 우회 불가(아래 3.1).
    gate_result = decide(signals, k_type=k_type)                  # 04d §2
    # ② 개념 주소화 조회(캐시 → DB read-through·프롬프트-해시와 별개 상위 계층)
    dsl = await get_concept_dsl(code, session=session, cache=cache)
    # ③ 렌더 가능·검증 통과면 0원 반환. 불가·미검증이면 사유를 남기고 폴백.
    #    (미등록 어댑터 LookupError도 사유로 흡수 — REND-01 레지스트리 계약)
    # ④ 폴백 — 기존 라우터 경유 생성. cache_hit면 prompt_cache, 아니면 generate.
    return SupplyResult(content_source=..., strategy=..., fallback_reason=...)
```

> **초판 의사코드 교정 2건(2026-07-25 구현 시 실측)**
> ① **supply는 L3가 아니라 L4다.** L3가 L4 선택기를 호출하면 역방향이라 `lint-imports`가 깨진다. 더 중요하게는,
>    supply가 `decide()`를 *내부*에서 호출해야 **게이트를 우회할 수 없다** — 전략을 인자로 받는 설계였다면
>    호출자가 게이트를 빠뜨린 채 완전예제를 렌더할 수 있다.
> ② **`resp.cost_krw`는 존재하지 않는다.** `pipeline.GenerationResult`에는 cost·usage 필드가 없고 비용은
>    `trace.record`로만 흐른다. 경로 판정치는 §4의 in-process 축(`SupplyResult.content_source`)으로 낸다.

### 3.1 게이트 = 교수학 우선순위의 기계적 강제 (§5 준수의 핵심)
`gate()`는 select 결정 *상류*에 있다. 두 축을 강제한다:
1. **금지 모드** — 대상 목표의 `k_type` 팩 `forbidden_modes`(예: `CONCEPT`은 `WORKED_EXAMPLE_FIRST` 금지)에 걸리는
   전략은 후보에서 제외.
2. **Polya 단계** — `WORKED_EXAMPLE`은 학생이 시도 *전*(막힌 첫 순간)에 냉담 제공 불가. Polya 단계가 "시도함"을
   통과한 뒤에만 허용(`CLAUDE.md` "막혔을 때 바로 정답 제공 금지"의 실행).

→ 캐시 히트가 교수학을 위반하면 **히트를 버리고** 게이트된 생성으로 폴백한다. *비용이 교수학을 이길 수 없다.*

### 3.2 2층 캐시 (기존 인프라와의 관계)
```
(1) 개념 주소화 중립 DSL 캐시   ← 이 문서 신규. 영구 자산. atom_code로 조회. 렌더는 어댑터가.
        ↓ (miss)
(2) 프롬프트-해시 Redis 캐시     ← 기존(l3/router.py::cache_key_for, l3/cache/redis_cache.py). 정확 반복.
        ↓ (miss)
(3) generate (라우터 경유)       ← 기존(l3/pipeline.generate). 생성물은 (2)에 적재, 고가치분은 (1)로 승격.
```
- (1)은 *개념 주소화*(atom·k_type·mode) — 불투명 프롬프트 해시인 (2)와 **키 축이 다르다**. (1)은 렌더 시점 조립을
  전제하므로 몰개인화되지 않는다(개인화는 어댑터·ctx가).
- 빌드타임 사전생성(`l3/pregenerate/prewarmer.py`)은 (1)·(2)를 *채우는* 오프라인 경로로 재사용한다.

---

## 4. 비용 분포 + 측정 (SSM "측정 없는 도입 없음")

ChatGPT 설계 대화의 분포 가정(≈ 캐시사용 76% / 캐시생성 15% / 맞춤생성 5% / 나머지)을 **측정 목표**로 정형화한다.
기존 L3 KPI(`03:229–231`)에 결선:

| KPI | 기존 | 이 문서 결선 |
|---|---|---|
| 학생당 월 LLM 비용 | <1,000 → 500원 | dsl_render 비율↑ = 이 KPI의 주 동인 |
| 로컬 LLM 비율 | 80%+ | 유지 |
| 캐시 적중률 | 30% → 50% | **분해**: `dsl_render_rate` + 프롬프트-해시 hit |

### 4.1 이중 회계 — 판정치는 in-process, Langfuse는 보조 (구현 반영)

`content_source`를 관측 인프라에만 실으면, 인프라가 죽었을 때 "0건 통과"로 **위장**된다. `ops/cost_probe`가
존재하는 이유가 정확히 그 사고다(placeholder 키 → `cost_report`가 조용히 0건 보고). 그래서 두 축으로 센다:

| 축 | 좌석 | 성격 |
|---|---|---|
| **판정치(주)** | `l4/content_supply.py` — `SupplyResult.content_source` **반환** + `SupplyTally` 집계 | in-process·SaaS 무관 |
| 분포(보조) | `langfuse_fields`의 `content_source` → `ops/cost_report.content_source_counts` | 관측 인프라 의존 |

- 파이프라인은 자기 `cache_hit`에서 `prompt_cache`/`generate`를 **스스로 유도**한다(상위가 주입할 필요 없음).
  렌더 경로는 라우팅을 타지 않으므로 supply가 자기 이벤트를 기록한다.
- `SupplyTally.dsl_render_rate_lower`는 **Wilson 단측 하한**이다(점추정 아님 — `cost_probe` 관례). 표본 0이면
  `None`을 돌려 "미상"을 0%로 위장하지 않는다.

> **범위 밖(정직한 공백)**: 라이브 트래픽 기반 `dsl_render_rate` **게이트 CLI는 만들지 않았다.** 실사용 트래픽이
> 없는 상태에서 합성 요청으로 비율을 재면 아무것도 측정하지 못하는 숫자가 나온다(`cost_probe`가 표본 확보를 위해
> *의도적으로* 캐시 미스를 강제하는 것의 거울상 함정). 집계 기구까지 놓고, 게이트 판정은 트래픽 확보 후 별도 태스크.
> `render_verify_pass_rate`·`dsl_promotion_rate`도 같은 이유로 미구현(승격 경로 자체가 후속).

---

## 5. 준수(compliance) 자기점검

- **조합폭발 방지** ✅ — 저장은 `중립 DSL(atom당 1) + 어댑터 N개(개념 무관)`. (atom × mode × difficulty × objective)를
  *열거·저장하지 않는다*. 거버넌스 회귀 테스트: "숫자/이름만 다른 두 DSL = 위반"(render 바인딩이지 새 자산 아님),
  "어댑터가 특정 개념명을 하드코딩하면 위반"(`test_embedding_namespace_governance.py` 선례 동형).
- **5대 분리** ✅ — DSL(콘텐츠) ≠ 어댑터(Renderer) ≠ Selector(교수법 결정·04d) ≠ 프롬프트(generate 경로) ≠
  오개념(반응형·id 참조). curriculum은 atom_code overlay.
- **의사결정 우선순위** ✅ — §3.1 게이트가 비용(#6)을 교수학(#3) 아래에 둔다(구조적 강제).
- **SSM §5 도입 게이트** ✅ — §4 측정 계획 + 위 구조붕괴 방어.
- 인용원: `concept_node_layering_decision.md`(변형 열거 금지)·`math_dsl_principles_review.md:50`(5대 분리)·
  `system_superiority_maintenance.md §5`(도입 게이트)·`04c_misconception_seven_stage_separation.md`(오개념 반응형).

## 6. 교차링크
- 상위: `03_content_generation.md`(§6 응답 캐싱이 이 문서를 가리킴)·`03a_l3_router_design.md`(캐시 키·라우팅).
- L4 위임: **`04d_adaptive_pedagogy_engine.md`** — Runtime Pedagogy Selector(§2 `select`)·Adaptive Engine.
- 북극성 서사: `../strategy/education_os_positioning_v1.md`.
- 실행 정본(무엇을 언제): `backlog/` — `REND-01`(어댑터)·`CACHE-01`(supply/측정).

---

**버전**: 1.0 | **작성**: 2026-07-24 | **다음 검토**: REND-01/CACHE-01 착수 시점
