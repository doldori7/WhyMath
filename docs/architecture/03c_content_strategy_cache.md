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

```python
async def supply(req: ContentRequest) -> ContentResponse:
    # ① 전략 선택 — L4 권위(04d). 그리고 반드시 교수학 게이트 통과(비용#6이 교수학#3 역전 금지).
    strat = await runtime_pedagogy_selector.select(req.student_state)         # 04d §2
    strat = gate(strat, pack.forbidden_modes, req.polya_stage)               # 완전예제 냉담 제공 불가
    # ② 개념 주소화 조회(영구 자산·프롬프트-해시 캐시와 별개의 상위 계층)
    dsl = await concept_dsl_cache.get(req.atom_code)
    if dsl is not None and adapter[strat].can_render(dsl):
        rendered = adapter[strat].render(dsl, req.ctx)                        # 0원·결정론(대부분 경로)
        if rendered.validation_signal is None:                               # 검증 통과분만 노출
            record(content_source="dsl_render", cost_krw=0.0)
            return served(rendered)
        # 검증 실패 → 미검증 노출 금지·폴백
    # ③ 신규 개념 or 진짜 새 조합만 — 기존 라우터 경유 생성
    resp = await l3_pipeline.generate(build_prompt(req, strat), system, routing_req)  # 03/03a
    record(content_source="generate", cost_krw=resp.cost_krw)
    maybe_promote_to_dsl(req, resp)                                          # 고가치 생성물 → DSL 자산 승격(검수 큐)
    return served(resp)
```

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

**신규 지표** — `langfuse_fields`(`l3/router.py`)에 `content_source: dsl_render|prompt_cache|generate` 추가 +
**로컬 이중 회계**(`ops/cost_probe` 선례 — 판정치를 SaaS에만 의존 금지, `CLAUDE.md`):
`dsl_render_rate`·`render_verify_pass_rate`·`generate_rate`·`dsl_promotion_rate`.

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
