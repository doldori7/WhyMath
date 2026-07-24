# 04d. 2단계 교수법 + Runtime Pedagogy Selector + Adaptive Pedagogy Engine (L4/L2)

> **성격**: L4(교수학 엔진)의 서브 설계 — `04`(교수학 결정) → `04a`(WH-1 튜터링 하네스) → `04b/04c`(오개념
> 판정·분리)에 이어 **`04d`(교수법을 언제·어떻게 *고르는가*, 그리고 그 선택을 어떻게 *학습하는가*)**. 콘텐츠
> 자산·렌더의 정본은 `03c_content_strategy_cache.md`(L3/L5).
>
> **한 줄**: 교수법은 DSL 생성 시점에 고정하지 않는다. 학생·상황마다 런타임에 *선택*하고, 장기적으로는 그 선택을
> *학습 가능한 policy*로 만든다.

---

## 0. 왜 교수법을 고정하면 안 되는가 (문제 정의)

"교육과정 → 교육목적 → **교수전략** → 콘텐츠 → DSL → 생성"처럼 교수전략을 DSL *이전*에 고정하면, 같은 교육목적이라도
**학생마다·학습상황마다·오답패턴마다** 달라져야 할 교수법이 콘텐츠에 각인되어 버린다. 실제로 같은 "일차방정식"이라도:

| 학생 | 상태 | 필요한 교수법 |
|---|---|---|
| A | 계산 실수 많음 | `RETRIEVAL`(연습 위주) |
| B | 개념 이해 부족 | `ANALOGY`(비유 설명) |
| C | 흥미 부족 | (게임형 — 초기 미채택·§2.3) |
| D | 문장제를 못 품 | `PROBLEM_BASED`/스키마 지도 |

→ **단원 → 교수법 A → 콘텐츠**(고정)가 아니라 **단원 → 중립 DSL → 런타임 교수법 선택 → 렌더**(동적)여야 한다.

---

## 1. 2단계 교수법 분리 (불변식)

교수법을 두 시점으로 **완전히 분리**한다. 사이의 산출물(DSL)은 교수법-중립을 유지한다(`03c §1`).

| 단계 | 시점 | 무엇을 결정 | 정본 |
|---|---|---|---|
| **① 설계용(Design Pedagogy)** | DSL *생성* 시(오프라인) | *무엇을* 담을지(개념·예시·오개념·평가). k_type별 CRA류 진행. | 기존 PED-01 `pedagogy_pack`(`db/models/pedagogy_dsl.py`·`schema/pedagogy_pack.py`) |
| **② 실행용(Runtime Pedagogy)** | 학생 *학습* 시(온라인) | *어떻게* 보여줄지(설명/질문/문제/비유…). 학생 상태로 선택. | **본 문서 §2 (신규)** |

- 설계용은 DSL의 *생성기*에 작용하고 DSL의 *내용*에 각인되지 않는다("Concrete→Representation→Symbol→
  Generalization"은 무엇을 담을지의 순서일 뿐, 학생 화면의 방식이 아니다).
- 실행용은 매 학습마다 재선택된다 — 저장된 방식을 재생하지 않는다.

---

## 2. Runtime Pedagogy Selector (신규·L4 ← L2·규칙기반 v1)

학생 모델을 보고 가장 효과적인 교수법 전략(`PedagogyStrategy`·`03c §2.1`)을 고른다. **L4가 결정하고 L2를
소비**한다(경계: L4는 L2를 *조회*만·역방향 의존 금지).

```python
async def select(student: StudentState) -> PedagogyStrategy:
    """학생 상태 → 교수법 전략. 규칙기반 v1(결정론 규칙표). policy 학습은 §3.

    입력(L2 소비 — 신규 학생모델 축 최소화):
      수준·오답 유형·학습 속도·집중도·학습 시간·선호·현재 성취도·직전 문제 결과
      (기존 MasteryState.preferred_solution_style·BKT 확률·정서 신호를 그대로 읽음)
    출력: PedagogyStrategy 1개(예: 오답=계산실수→RETRIEVAL·개념부족→ANALOGY·문장제→PROBLEM_BASED)
    """
    strat = _rule_table_v1(student)      # 결정론 규칙표(투명·감사 가능)
    return strat                          # 실제 사용 전 supply()의 gate()를 반드시 통과(03c §3.1)
```

- **v1은 규칙표** — 투명하고 감사 가능하다. policy 학습(§3)은 데이터가 쌓인 뒤 승격한다.
- **게이트 위임** — 선택된 전략은 `03c §3.1`의 `gate()`(금지 모드·Polya 단계)를 *반드시* 통과한다. Selector는
  "무엇이 효과적인가"를, gate는 "무엇이 교수학적으로 허용되는가"를 담당한다(효과 ≤ 허용).
- **L2 연계** — 기존 `MasteryState.preferred_solution_style`(02 문서)·BKT/정서 신호를 입력으로 소비한다. 새 학생
  모델 축을 최소로만 추가한다.

---

## 3. Adaptive Pedagogy Engine (장기 해자·측정 게이트)

교수법을 **고정 규칙이 아니라 학습 가능한 policy**로 만든다. 이것이 WhyMath의 장기 기술 해자다.

### 3.1 루프
```
교수법 선택 → 렌더(03c) → 학습 데이터 수집 → 효과 측정 → policy 갱신 → 다음 학습 반영
```

### 3.2 효과 측정 (측정 없는 도입 없음)
각 전략의 효과를 **(학생군 × 개념 × 오개념 유형)별로** 지속 측정한다:
- 지표: 정답률·체류 시간·오개념 **재발률**·**장기 파지**(간격 재검) — L2 학습 이력 + Langfuse.
- "누구에게 어떤 교수법이 가장 효과적인가"를 데이터로 답한다(인상·직관 아님).

### 3.3 policy 갱신
- **contextual bandit → (후속) RL**: 문맥(학생 상태·개념)에서 전략을 고르고 보상(효과 지표)으로 갱신.
- **안전 제약(하드)**: 교수학 우선순위(#3)를 위반하는 전략은 policy가 **애초에 고를 수 없다** — bandit의 행동
  공간에서 배제(§2 gate와 동일 축을 policy 계층에도 못박음). 비용(#6) 보상이 아무리 커도 교수학 위반을
  선택하지 못한다.
- **승격 게이트**: v1 규칙표는 즉시 가동. policy 학습분은 **오프폴리시 평가 + 결함 주입 강등전 통과** 후에만
  규칙표를 대체한다(`superhuman_verification_standard.md`·게이트 CLI PASS 경유). 데이터가 얇을 땐 규칙표가 정본.

---

## 4. 준수 + 교차링크

- **의사결정 우선순위** — §2 gate·§3.3 안전 제약이 비용(#6)의 교수학(#3) 역전을 이중으로 차단.
- **오개념 반응형** — 오답 유형 입력은 `l4/misconception/diagnose.py`(반응형 retrieval)를 경유. 초기 context
  preload 금지(`04c`).
- **L2 경계** — Selector는 L2를 조회만·업데이트는 L5 오케스트레이터가(`00_overview.md` 데이터 흐름).
- 교차링크: `03c_content_strategy_cache.md`(전략을 소비하는 렌더)·`02_learner_model.md`(입력)·
  `04_pedagogy_engine.md`(Polya·오개념)·`04a_wh1_tutoring_harness.md`(온라인 런타임).
- 실행 정본: `backlog/` — `PED-02`(Selector v1)·`PED-03`(Adaptive policy·장기).
- 북극성 서사: `../strategy/education_os_positioning_v1.md`(§2(c) "학습하는 해자").

---

**버전**: 1.0 | **작성**: 2026-07-24 | **다음 검토**: PED-02 착수 시점
