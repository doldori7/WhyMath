# 문제은행(Problem Bank) 모듈 — 외부 EOS 틀 대조 갭 점검·설계 (2026-07-28)

> **범위**: 외부 참고 문서 『0단계 — 문제은행 모듈』(기능 18~22: 문제 DB · 난이도 관리 ·
> 유형 관리 · 자동 문제 생성 · 변형문제 생성 — **WhyMath 전용이 아닌 일반적 EOS 틀**,
> Kiki 제공)을 현 코드베이스와 대조해 빠진 부분을 점검하고, 진짜 갭을 WhyMath 불변식
> (저작권 3중 레일·검증 권위 서열·Curriculum-as-Overlay·anti-explosion·dead code 금기) 안에서 설계한 기록.
> **형식**: `knowledge_module_gap_review.md`(같은 EOS 틀 모듈 6~10, 2026-07-27) 답습 — 자매편.
> **대전제 2가지**: ① WhyMath에는 **이미 작동하는 문제은행이 존재한다**(자체생성 코퍼스 6종
> 2,667문 · 수용 게이트 4종 · 초인간 검증 6축 · 강등전 120/120 · IRT CAT 노출) — 이 문서는
> 무에서의 설계가 아니라 **격차 보완**이다. ② 제품 정체성은 "문제은행이 아니라 **사고
> 추적기**"(플레이북 Part 0) — 틀의 '문제 공급 공장' 프레임을 WhyMath에서는 '**검증된 사고
> 소재의 공급**'(문항 = 정답이 아니라 사고 경로·오개념 계측이 달린 단위)으로 재해석한다.
> **결론**: 기능 18 대부분 충족(출처·검증 축은 틀보다 엄격) · 19 절반(IRT 보정만 배선·실학생
> 데이터 0) · 20 분류 체계는 초과 충족·연결은 의도적 연기 · 21 4방식 충족·커버리지 편중 ·
> 22 3/6 방식 보유·계보 미영속. 진짜 갭 9건을 설계(D1~D9)하고 실행 8건을 백로그에 등재했다
> (다중 풀이 D6은 같은 날 병렬 자매편 #635의 기등재 태스크로 승계 — §3 D6).
> 의도적 미채택 6건 · 정직한 공백 4건 · 유보(발화 조건 명시) 4건.

관련 정본: `03_content_generation.md`(L3 생성·SolutionPath) · `solution_module_gap_review.md`
(같은 EOS 틀 기능 23~27 풀이 축 자매편, #635 — D6 승계처) · `docs/data/problem_type_graph_v1.md`
(유형 17종·Phase 3b) · `docs/standards/superhuman_verification_standard.md`(검증 6축·강등전) ·
`docs/data/licensing_safety.md`(저작권) · `MEMORY.md` 결정 로그(2026-07-28).

---

## §0. 전제 — 실측 현황 스냅샷 (2026-07-28 기준)

**코퍼스 6종 2,667문** (`data/corpus/problem_bank_*`, 전건 `source_type=자체생성` ·
`license=WHYMATH_GENERATED` · `generation_type=FULLY_GENERATED`):

| 코퍼스 | 건수 | 생성 방식 | 표본 검수 | `_provenance.json` |
|---|---|---|---|---|
| `problem_bank_v1` | 4 | 손저작 시드(코퍼스 저작 계약의 계약 문서) | — | ✅ |
| `problem_bank_generated_v0` | 620 | 결정론 스켈레톤 15밴드(LLM 0) | ✅ AI 검수 240표본 Wilson 95% 상한 1.11% PASS | ❌ |
| `problem_bank_rephrased_v0` | 483 | LLM 발문 다양화(수치·정답·선지 불변 봉인) | ❌ | ❌ |
| `problem_bank_misconception_mc_v0` | 1,080 | 오개념 수치평가 객관식 45서브밴드 | ❌ | ❌ |
| `problem_bank_conceptual_v0` | 360 | 개념형(개수·판정) 객관식 15밴드 | ❌ | ❌ |
| `problem_bank_killer_v0` | 120 | Vieta 근집계 킬러 단답형 | ❌ | ❌ |

**파이프라인 4축** (모두 실가동):
- **스키마 3층**: `schema/problem.py`(Pydantic 정본 705행·50+필드) → `db/models/problem.py`(ORM) →
  alembic. 저작권 validator `_METADATA_ONLY_SOURCES`(`schema/problem.py:57`) — 평가원·EBS·교과서
  출처는 본문 필드가 비어야만 통과.
- **생성·검증(L3)**: `l3/equivalent/` — 생성(스켈레톤 15종·`llm_generator`) → 수용 게이트 4종
  (`acceptance.evaluate_equivalent_candidate`: 저작권·정확성 Tier1/2·위생·동등성 분류) →
  canonical signature dedup(`canonicalize.py`) + 임베딩 dedup(코사인 0.97). 독립 감사
  `retag.py`(생성자≠검증자) · 수치 반례 `counterexample_fuzz.py`(≥10,000회).
- **적재(L1)**: `l1/problem_bank/populate.py` — JSONL→`problem`·`problem_concept` 멱등 upsert.
  L1은 L3 게이트를 호출하지 않는다(import-linter) — 게이트 통과는 **코퍼스 저작 계약**.
- **노출(L2/L6)**: `l6/_shared.py:141 is_exposable()`(저작권 최종 게이트 — 법적 우선순위가
  교수학·UX보다 앞선다) × L6 모드 게이팅 × `GET /v1/me/next-problem`(IRT CAT: θ추정→후보 50→
  Fisher 정보량 최대) × BKT 약점 가중. 난이도 보정 배치 `l2/item_calibration.py`(JMLE)·
  `l2/calibrate_items.py`.

**노출 4단 구분**(전 배치 docstring이 반복 명시하는 규약): 게이트 통과 → 코퍼스 편입 →
노출 적격(`is_exposable`+검수) → 실노출(CAT 선택). **"게이트 통과 ≠ 학생 노출."**

**역할 분담**: 문제은행(연습·평가 문항)과 `atom_probe`(원자 단위 진단문항+소크라테스 1,837건,
`docs/data/atom_probe_v1.md`)는 별개 자산이다 — 진단은 원자 프로브가, 연습·모드별 출제는
문제은행이 담당한다. 이 문서의 범위는 후자.

---

## §1. 기능 18~22 ↔ WhyMath crosswalk 판정

판정 어휘: ✅ 충족 / ⚠️ 갭 → **Dn** / 🚫 의도적 미채택 → §2 / ⏸ 기존 추적 승계(중복 등재 금지).

### 기능 18. 문제 DB — **대부분 충족** (출처·검증 축은 틀보다 엄격)

| 틀 항목 | WhyMath 현행 | 판정 |
|---|---|---|
| 표준 데이터 구조·문제 ID | 3층 스키마 + `problem_id`(UUID)·`slug`(UNIQUE·코퍼스 멱등 키)·`external_id` | ✅ |
| 본문·정답·해설·풀이 과정 | `question_text(_md)`·`choices`·`answer`·`multiple_answers`·`answer_explanation` + 검산 계약 `verify`(SymPy 조건식·answer_map — 틀에 없는 초과 축). 풀이 *단계*는 `problem_step`(Socratic) + `SolutionPath`/`SolutionStep`은 Phase 2 유보(`03_content_generation.md`) | ✅ |
| 과목·학년·단원 | `subject`·`domain`·`unit_codes[]`·`subunit`. 학년은 노드 비내장 — `CurriculumEntry` Overlay가 단일 진실 | ✅ (Overlay 형태로) |
| 성취기준·학습목표 | `achievement_standard_codes[]` — 단 **비영속**(ORM 비매핑, `schema/problem.py:495` — L5가 4단 조인으로 주입, L1/L2 직접 소비 시 빈 값) | ✅ 부분 → 발화 조건 §5-② |
| 관련 개념 | `problem_concept`(N:M·role·relevance) + S2-03 원자 백본 재연결 완료 | ✅ |
| 관련 공식 | Problem↔Formula 링크 부재 — `formula_refs` 충전은 Phase 5b 기존 계획 승계 | ⏸ §5-① |
| 관련 오개념 | `distractor_map`(오답 선지↔오개념 M-id) + misconception_mc 1,080문이 카탈로그 843 겨냥 | ✅ (틀보다 구체) |
| 문제 유형 | 기능 20 참조 — 분류 체계 실재·Problem 연결은 Phase 3b | ⏸ §5-③ |
| 난이도 | 기능 19 참조 — 5축+IRT 2모수+고전 변별도 | ✅ (틀보다 엄격) |
| 출처·저작권 | `source_type`·`source_detail` + **자체생성 온리 3중 레일**(§2-①). 틀의 '기출 수집·출처 관리' 방향은 채택 불가 | 🚫 §2-① (더 엄격한 형태로 충족) |
| 태그·키워드 | `tags[]`·`keywords[]`·`signature_patterns[]`(GIN — 한국 수능 시그니처 10종 축, 틀에 없음) | ✅ |
| 버전 | per-문항 버전 필드 없음 — git+코퍼스 버전(`*_v0/v1`)+provenance+`review_status`가 정본 | 🚫 §2-② |
| 생성 AI 여부 | `generation_type`(FULLY_GENERATED/···) + `llm_generator`는 코드가 무조건 박음 | ✅ |
| 검수 상태 | `review_status` 필드 실재(`schema/problem.py:564`) — 단 **실코퍼스 전 2,667건 미기록**이고 표본 검수 기록도 generated_v0(240표본)뿐 | ⚠️ → **D2** |
| 예상 풀이시간·정답률·변별도 | `expected_solve_seconds(_p90)`·`historical_correct_rate`·`rate_top/mid/low_grade`·`discrimination_D` — **필드만 실재, 실측 갱신 루프 없음**(실학생 데이터 0) | ⚠️ → **D9** (§4) |
| 추천 대상 | `persona_fit: dict[Persona,float]` — **전 2,667건 `{}`**(실측 2026-07-28). L6 수능 모드의 persona_fit 적격 경로가 사실상 사망 | ⚠️ → **D3** |
| 사용 횟수·최근 수정일 | `problem_attempt`/`attempt_event`에서 유도(문항 측 캐시는 소비처 생길 때)·`updated_at` | ✅ |

**18 종합**: 틀 항목의 스키마 좌석은 사실상 전부 있다. 진짜 갭은 좌석이 아니라 **채움과
운영**이다 — 검수 균일화(D2)·persona_fit(D3)·서지 정합(D1)·실측 통계(D9).

### 기능 19. 문제 난이도 관리 — **절반 충족** (구조 완비·데이터 루프 미가동)

틀의 8축 대조:

| 틀 난이도 축 | WhyMath 현행 | 판정 |
|---|---|---|
| 교육과정 난이도 | `difficulty_overall` + 5축(`diff_calculation`·`diff_interpretation`·`diff_case_analysis`·`diff_visual`·`diff_integration`) | ✅ (틀보다 세분) |
| 인지 수준(Bloom) | `bloom_level` | ✅ |
| 계산량 | `diff_calculation` | ✅ |
| 추론 난이도 | `diff_interpretation`·`diff_case_analysis` | ✅ |
| 풀이 길이 | `expected_solve_seconds(_p90)` | ✅ |
| 오개념 유발 정도 | 전용 필드 없음 — 신규 축 증설은 🚫 §2-④, `distractor_map` 오답 선지 선택률 **통계 유도**로 대체 | ⚠️ → **D9** (신규 필드 0) |
| 실제 학생 정답률 | `historical_correct_rate`·`rate_*` 필드 실재·갱신 루프 없음 | ⚠️ → **D9** |
| AI 예측 난이도 | `l3/equivalent/difficulty.py` 결정론 추정 v1(근유형·계수 가산·[1,5] 클램프·2026-07-12 앵커 재조정) | ✅ v1 |

**자동 업데이트 루프**(틀: 초기 난이도→학생 풀이→실제 정답률→AI 재평가→자동 수정):
- **절반 배선 실재**: `l2/item_calibration.py`(응답 전수→JMLE→`irt_difficulty_b` 영속) +
  `l2/calibrate_items.py` 배치 CLI + `resolve_item_difficulty_b`(보정 b 우선→휴리스틱 폴백).
  틀이 요구하는 루프의 IRT 절반은 이미 있다.
- **미가동 절반**: 정답률·`rate_*`·경험 변별도 갱신 → 5축 재평가 환류. 실학생 응답이 0인
  현재 착수 불가(§4) — **D9**로 설계만 확정하고 `S3-01-pilot-cohort` 뒤에 잠근다.

### 기능 20. 문제 유형 관리 — **분류 체계 초과 충족 · 연결은 의도적 연기**

| 틀 항목 | WhyMath 현행 | 판정 |
|---|---|---|
| 대표 유형(계산형·개념형·서술형·증명형·탐구형·실생활형·그래프형·자료해석형·함수형·기하형) | `problem_type_graph_v1` — **17유형 6 family**(값_결정·존재_판정·개수_세기·최적화·관계_추론·구성_검증). 표면 소재가 아니라 **인지 행동(cognitive action)** 기준 — 틀의 10종(소재·형식 혼합 축)보다 정교. 표면 구조는 `SignaturePattern`이 **직교 축**으로 분리 | ✅ (초과 충족) |
| 세부 속성(객관식·단답형·서술형·단계형·프로젝트형) | `question_format`·`answer_format`·`scoring_type`(정오답/진단/부분점수/시간/루브릭)·`points` | ✅ |
| 문제↔유형 연결(검색·추천 기반) | `problem_type_node` 테이블 실재·Problem 연결은 **Phase 3b 의도적 연기**(생산자/소비처 확보 후 — dead code 회피, `problem_type_graph_v1.md:90`) | ⏸ §5-③ (발화 조건 구체화) |
| 유형별 커버리지·검색·분석 | 유형×단원 관측 없음 — 커버리지 리포트(**D4**)의 유형 축은 Phase 3b 발화 후 확장으로 스코프 명시 | ⚠️ → **D4** (부분) |
| Problem Template DSL 메타정보 | 별도 DSL 계층 미도입 — **스켈레톤 생성기 15종 + `verify` 검산 계약**(SymPy 조건식)이 결정론 템플릿의 실체. 교수법 DSL(`03c`)은 별개 축 | 🚫 §2-⑥ |

### 기능 21. 자동 문제 생성 — **4방식 충족 · 커버리지 편중**

| 틀 생성 방식 | WhyMath 현행 | 판정 |
|---|---|---|
| ① Template 기반(공식→변수 변경) | 스켈레톤 생성기 15종(`l3/equivalent/*_generator.py` — SymPy 결정론·LLM 0·시드 고정 재현) | ✅ |
| ② Concept 기반(개념→학습목표→생성) | 개념·성취기준 태깅 동반 생성 + 개념형 코퍼스 `conceptual_v0` 360 + 오개념 카탈로그 843 겨냥 `misconception_mc_v0` 1,080 | ✅ |
| ③ LLM 기반(교육과정+개념+난이도) | `llm_generator.py`(라우터 경유·Phaiakes9 로컬 우선) — 저작권 삼중 방어(프롬프트·코드 강제·게이트) | ✅ |
| ④ DSL 기반 | ①의 결정론 스켈레톤+`verify` 계약이 그 자리(§2-⑥) | 🚫 §2-⑥ |
| 생성 결과(문제·정답·해설·풀이·태그·난이도) | 전 필드 산출 + **틀에 없는 초과 축**: 수용 게이트 4종 → 독립 감사 → 수치 반례 fuzz → Wilson 감사(6축 초인간 검증·강등전 120/120 검출·오검출 0) | ✅ (초과 충족) |

**갭 3건**:
- **커버리지 편중** — 실적재 15 unit_code 밴드(QUAD-EQ 185 ~ TRIG-EQ 12)는 고교 대수·미적분
  중심. 성취기준 895 대비 커버율·0커버 목록의 **측정 자체가 없다** → **D4**. 초·중 확장
  *실행*은 `S4-01-math-k12-complete` 기존 추적 승계(⏸ — 중복 등재 금지, D4가 저작 우선순위 입력).
- **다중 풀이 미가동** — "다중 풀이의 본질적 동치성 체험"은 CLAUDE.md 제품 정체성 항목인데
  공급 파이프라인이 없다(`status_roadmap_2026-07.md` S2 미체크 잔여) → **D6**.
- **SymPy 검증 불가 영역** — 확률 추론·기하 논증·벡터 등은 수치·심볼릭 검산 게이트가 성립하지
  않아 생성 경로 자체가 없다(2026-07-12 정직 기록: "수치평가 MC 소진, 개념형은 사람/LLM 경로")
  → **D7**.

### 기능 22. 변형문제 생성 — **3/6 방식 보유 · 계보 미영속**

| 틀 변형 방식 | WhyMath 현행 | 판정 |
|---|---|---|
| 숫자 변형 | 스켈레톤 파라미터화(밴드 내 계수 공간 순회) + canonical signature dedup이 판박이 차단 | ✅ |
| 조건 변형(도형·조건 교체) | 부재 | ⏸ §5-④ |
| 문맥 변형(소재 교체) | `rephrase.py` + `problem_corpus_rephrase*` CLI — 483문. 수치·정답·선지 **불변 봉인** 후 발문만 다양화 | ✅ |
| 난이도 변형(기초↔심화 계열) | 부재(밴드별 독립 생성만 — 같은 뼈대의 상하 계열화 없음) | ⏸ §5-④ |
| 역문제 생성(답→문제) | 부재 | ⏸ §5-④ |
| 오답 유도형(오개념 겨냥) | `misconception_mc_v0` 1,080문 — 오개념 카탈로그 843·64 kebab 탐지 카탈로그 기반 distractor 설계 | ✅ (틀보다 앞섬) |

**갭 — 변형 계보 미영속(D8)**: `problem_relation`(변형·유사·선수·심화·대조 + similarity_score,
`db/models/problem.py:359`)이 스키마·ORM·API에만 존재하고 **어떤 생성·적재 경로도 채우지
않는다**(실측: harness·l1·l3에서 참조 0건·코퍼스에 계보 필드 0건). rephrase 483문은 원본
문항과의 파생 관계가 기록되지 않은 채 병렬 적재돼 있다 — "변형" 기능의 데이터 기반(어떤
문항의 변형인가)이 비어 있는 상태. 틀의 흐름(변형→반복 학습·평가 지원)은 계보 없이는 "같은
문제 연속 출제 회피"·"틀린 문제의 변형 재출제" 같은 소비를 지탱하지 못한다.

---

## §2. 의도적 미채택 판정 (협상 불가 근거)

틀의 다음 항목은 **채택하지 않는다**. 각각 CLAUDE.md 협상 불가 조항·기존 판정과 1:1 대응한다.

| # | 틀 제안 | 불채택 근거 |
|---|---|---|
| ① | 기출·외부 문제 수집형 출처 관리(출처·저작권 필드로 외부 문항을 담는 방향) | **저작권 3중 레일** — 평가원·EBS·교과서 본문은 절대 금기(저작권법 §32 단서·§136·§140 영리 비친고죄). ⑴ `_METADATA_ONLY_SOURCES` validator(`schema/problem.py:57`) ⑵ provenance 지배 license=WHYMATH_GENERATED 강제 ⑶ `is_exposable()` 노출 차단(`l6/_shared.py:141`). 학생 노출 본문은 `자체생성`만 합법 — 출처 필드는 *메타데이터 매핑* 전용 |
| ② | per-문항 버전 필드(버전·개정 이력 컬럼) | 단일 진실 원천 — 버전 정본은 git + 코퍼스 버전(`*_v0/v1`) + `_provenance.json` + `review_status`(모듈 6~10 판정 §2-② 동형). 문항 개정·파생 *계보*는 버전 필드가 아니라 `problem_relation` 축(**D8**)으로 표현 |
| ③ | 검수 상태를 "사람이 봤는가"로 관리 | **검증 권위 서열**(초인간 검증 기준 v1) — ①기계 증명 ②측정 통과 기계 게이트(6축·Wilson 95% 상한 ≤2%) ③인간 폴백(측정 미달·undecidable만). PRD §6.4 "모든 답안 사람 검수"는 2026-07-10 AI 검수 전환으로 대체됨 — 이 문서·후속 태스크의 "검수"는 전부 *측정 게이트 경유*를 뜻한다 |
| ④ | 난이도 8축 전부를 신규 필드·enum으로 증설 | **anti-explosion** — 기존 5축+`bloom_level`+IRT+통계 필드로 8축 전량 crosswalk 완료(§1 기능 19 표). 유일 공백인 '오개념 유발도'는 `distractor_map` 선택률 **통계 유도**(D9)로 — 신규 필드 0 |
| ⑤ | 문제↔유형 즉시 연결·유형 축 신설 | **소비처 없는 설계 금지** — Problem↔ProblemType 연결은 Phase 3b 기존 판정(생산자/소비처 확보 후·dead code 회피) 존중. 이 문서는 연결을 앞당기지 않고 **발화 조건만 구체화**(§5-③) |
| ⑥ | 독립 Problem Template DSL 계층 신설 | 추상 이중화 금지 — 결정론 스켈레톤 생성기 15종 + `verify` 검산 계약(SymPy 조건식·answer_map)이 이미 "실행 가능한 템플릿"이다. 별도 DSL 문법을 얹으면 truth source가 둘이 된다(붕괴 연쇄 ④). LLM 다양화는 rephrase·`llm_generator` 축이 담당 |

---

## §3. 설계 D1~D9 (진짜 갭의 WhyMath 정합 설계)

우선순위 논리 — 틀의 제안 순서(18→20→21→22→19)를 현황에 재매핑하면: **노출 자격 균일화
(D2·D3) → 서지 정합(D1) → 관측(D4) → 게이트 승격(D5) → 확장(D6·D7·D8) → 실데이터 루프(D9)**.
콘텐츠 생산은 이미 돌고 있으므로, 병목은 생산이 아니라 *노출 자격과 관측*이다.

### D1. 서지 정합 — 구본 명세 강등 + 데이터 카드 + provenance (백로그 `S3-11`)

**갭**: ⑴ `schemas/v1.1/problem.schema.yaml`(311줄·"상태: 명세 단계"·미구현)이 구현 정본
(`schema/problem.py`)과 필드 체계가 다른 채 방치 — 특히 헤더 저작권 절이 "✅ 평가원 기출 —
교육적 인용 범위 내 본문 인용 OK"(구본 스탠스, 2026-05-28 metadata-only 전환 **이전**)를
선언하고, `subject_pack_spec_v1.md:171` 참조표가 이 파일을 "문제" 정본처럼 가리킨다 —
**저작권 정책 구본이 정본 행세하는 상태**. ⑵ 코퍼스 6종 중 5종(2,663문)에 `_provenance.json`
부재. ⑶ `docs/data/`에 problem_bank 데이터 카드 0장(다른 모든 코퍼스는 카드 보유) — 문제은행
지식의 실질 정본이 MEMORY 결정 로그 산재분.

**설계**:
- **이번 커밋에서 즉시**: v1.1 YAML 헤더에 구본 배너(비정본·저작권 스탠스 대체됨·구현 정본
  경로) 주석 추가 + `subject_pack_spec_v1.md` 참조표에 구현 정본 병기. 본 문서 §0이 통합
  현황 정본을 개시.
- **태스크 `S3-11-problem-bank-data-card`**: `docs/data/problem_bank_corpus_v1.md` 데이터 카드
  (6종 건수·생성 CLI·게이트·검수 현황·노출 4단 지위·재현 명령) + v0 5종 `_provenance.json`
  생성(v1 계약 문서 동형 — 저작 계약·게이트 경유 명기) + `licensing_safety.md` 대장 1줄.

### D2. 잔여 v0 코퍼스 검수 — 노출 자격의 최단 경로 (백로그 `S3-09`)

**갭**: 표본 검수(AI 검수 240표본·Wilson 95% 상한 1.11% PASS)를 통과한 것은 generated_v0
620문뿐. misconception_mc 1,080 · rephrased 483 · conceptual 360 · killer 120(합 2,043문)은
수용 게이트는 통과했으나 **표본 감사 기록이 없다** — "게이트 통과 ≠ 학생 노출" 규약상 노출
부적격 상태가 계속된다.

**설계**: 240 배치 선례(`reviewer_sample_package.py` 결정론 층화 샘플링 → AI 검수 →
`corpus_audit_eval.py --max-defect-upper 0.02 --min-n 200`) **동형**을 잔여 4종에 적용.
코퍼스별 독립 판정(합격 로트 무결성 §4.5 — 재채점 금지·as-found 병기). 불합격 코퍼스는 노출
부적격 유지 + 결함 유형을 생성기 교정으로 환류. 산출: 감사 jsonl + `docs/data/` 검수 기록
(ai_review_batch 선례 동형).

### D3. persona_fit 백필 — 죽은 적격 경로 소생 (백로그 `S3-10`)

**갭**: `persona_fit`이 전 2,667건 `{}`(실측). L6 수능 모드의 persona_fit 기반 적격·가중
경로가 항상 공집합으로 동작한다(`api/me.py` docstring이 "현 코퍼스 persona_fit 전부 {}라
실손실 0"으로 정직 기록 — 뒤집어 말하면 페르소나 축이 **한 번도 산 적 없다**). 페르소나
전략(A 고3 MVP → B·C·D·E)의 런타임 구현이 데이터 부재로 미가동.

**설계**: 규칙 기반 백필 v1 — unit_codes·난이도 밴드·signature_patterns·질문 형식에서 페르소나
적합도를 **결정론 유도**(예: 킬러 Vieta → A 고3·B 자사고 고적합). LLM 추정 아님·근거 필드
동반·바이트 결정론(재실행 동일 출력). 검증: 백필 후 l6 suneung/school_progress 적격 후보 수
전0→후N>0 실측 리포트. 페르소나별 세밀 조정은 파일럿 실데이터(D9) 후속.

### D4. 커버리지 관측 — 성취기준×단원×난이도 리포트 (백로그 `ARCH-18`)

**갭**: 15 unit_code 밴드 편중을 **측정하는 도구가 없다**(품질 15축 ⑫ 커버리지 잔여 공백).
S4-01(초·중 확장)의 저작 우선순위를 정할 근거 데이터 부재.

**설계**: 빌드타임 결정론 CLI(data-pipeline 또는 harness 축·런타임 아님) — 코퍼스 전량 스캔 →
⑴ 성취기준 895(`achievement_standard`) 대비 커버율·0커버 목록 ⑵ unit_code×난이도 밴드 분포
매트릭스 ⑶ 코퍼스별·질문형식별 분해. exit 0/1 게이트가 아니라 **관측 리포트**(저작 우선순위
입력 — 관측 없는 확장 금지). 유형(17종) 축은 Problem↔ProblemType 연결(§5-③) 발화 후
확장으로 스코프 명시 — 지금 넣으면 전 문항 유형 미태깅이라 전부 0인 무의미 축.

### D5. 품질 게이트 승격 — 15축 ⑧답 분포·⑩LaTeX (백로그 `ARCH-19`)

**갭**: 문항 품질 15축 중 기계 판정 가능한 잔여 — ⑧정답 위치 분포 편향(객관식 1,440문의
정답 번호 쏠림)·⑩LaTeX/문법 검증(렌더 불가 수식·깨진 표기)이 게이트 없이 공백.

**설계**: 수용 게이트 축 추가 — ⑧은 코퍼스 수준 분포 검정(문항 단위가 아니라 배치 산출물
검정·카이제곱류 결정론), ⑩은 문항 단위 LaTeX 파스 게이트. **신규 게이트 규약 준수 의무**:
결함 주입 강등전(⑧ 쏠림 주입·⑩ 깨진 수식 주입 — `defect_seeder.py` 결함 유형 확장) 검출률
+ 무결함 오검출 Wilson 상한 병기, CLI exit 0/1. 측정 없는 게이트는 게이트가 아니다.

### D6. 다중 풀이 최소 가동 — 정체성 갭 (⏸ 기존 추적 승계 — 2026-07-29 재판정)

**갭**: "다중 풀이의 본질적 동치성 체험"은 제품 정체성(CLAUDE.md·차별화 해자)인데 공급이
0이다. `SolutionPath`(approach_type 6종) 설계는 `03_content_generation.md`에 확정돼 있고
구현만 Phase 2 유보 — 로드맵 S2 체크리스트의 미체크 잔여.

**승계 판정**: 본 문서 초안은 신규 태스크(구 `S4-09-multi-solution-pipeline-minimal`)를
등재했으나, 같은 날 병렬 자매편 `solution_module_gap_review.md`(외부 EOS 틀 기능 23~27,
#635)가 같은 갭을 먼저 착지시켰다 — `S4-09-solution-path-materialization`(SolutionPath/
SolutionStep 실체화) → `S4-10-multi-solution-generation`(라우터 경유 생성·최종답 SymPy
동치+단계 검증 통과분만 뱅크·ApproachType 6종 실체화). **중복 등재 금지 원칙에 따라 본 축
태스크를 삭제하고 그쪽 2건을 정본으로 승계**한다.

**본 문서 관점의 보완 명세**: ⑴ 생성물 검증("검증 통과분만 뱅크·유입 0 테스트 동결")은 본
문서 §0 수용 게이트 스택과 정합 ⑵ **학생 대면 소비 슬라이스**(자기 풀이 제출 *후* '다른
접근' 노출·L4 연계·바로 정답 제공 금지 정합)는 그쪽 §4-⑥이 의도적 유보 — 발화 시 이 절이
소비 슬라이스 요구사항의 참조점 ⑶ WH-S PRM 학습쌍(good/bad) 접근 다양화 부수 산출 동일.

### D7. SymPy 불가 영역 경로 — 검증 모델의 정직한 확장 (백로그 `S4-13`)

**갭**: 현행 게이트는 "SymPy 검산 가능"이 전제라, 확률 추론·기하 논증·벡터·(향후 증명형)은
생성 경로 자체가 없다(2026-07-12 정직 기록). K-12 완성(S4-01)의 구조적 선결 문제 — 이 영역을
못 만들면 커버리지 확장이 대수 계열에 갇힌다.

**설계**: 검증 권위 서열 안에서의 대체 스택 v1 — ⑴ 가능한 부분은 기계로(확률: 유한 표본공간
전수 열거·조합 계산은 SymPy/정수 연산 가능 — "추론 서술"과 "수치 검산"을 분리해 후자는 Tier1
유지) ⑵ 기계 불가 잔여는 **독립 다관점 LLM 교차검증**(생성자≠검증자·K≥3·원리 다른 프롬프트,
S3 축 준용) + Wilson 표본 검수 게이트(S5 축) ⑶ "게이트 통과=완전 검증"이 아님을 코퍼스
메타에 명시(검증 등급 필드는 기존 `verify` 계약 확장·신규 필드 최소). 파일럿 1영역(확률
유한 전수형)으로 실증 후 확장. 기하 논증·증명형은 `S4-02-proof-learning-support`와 경계 공유
— 문항 생성은 본 태스크, 학생 증명 피드백은 S4-02(중복 금지).

### D8. 변형 계보 영속 — problem_relation dead seat 해소 (백로그 `S4-14`)

**갭**: §1 기능 22 — `problem_relation`을 채우는 경로가 0. 변형 데이터가 계보 없이 병렬
적재돼, "같은 뼈대 연속 출제 회피"(CAT 후보 필터)·"틀린 문제의 변형 재출제"(오답 후속
학습) 같은 소비를 지탱할 데이터가 없다.

**설계**: ⑴ 생성 시점 기록 — rephrase 배치가 원본 slug→변형 slug를 `problem_relation`
(변형·similarity_score) 레코드로 동반 산출, 스켈레톤 동일 밴드 내 파생은 유사 관계로 선택
기록 ⑵ 소급 백필 — rephrased_v0 483건의 원본 매핑(생성 로그·canonical signature 역추적) ⑶
적재 — `populate.py`에 relation upsert 추가(L1 멱등·저작 계약 동형) ⑷ 검증 — 행>0·참조
무결(slug 실재)·거버넌스 테스트. 첫 소비처는 CAT 후보 필터(직전 오답 문항의 형제 제외/포함
로직)로 슬라이스 동반.

### D9. 실응답 난이도 루프 — 틀의 자동 업데이트 완성 (백로그 `S4-15` · `S3-01` 잠금)

**갭**: §1 기능 19 — IRT 보정(JMLE)만 배선, 정답률·rate_*·경험 변별도·오개념 유발도 갱신
루프 부재. 실학생 응답 0이라 지금 만들면 입력 없는 파이프라인(dead code).

**설계**(착수는 `S3-01-pilot-cohort` 완료 후): ⑴ `problem_attempt` 집계 → `historical_correct_rate`·
`rate_top/mid/low_grade`·경험 `discrimination_D` 갱신 배치(`calibrate_items` 동형 CLI·결정론·
갱신 감사 로그 동반 — as-found 병기 규약 준용) ⑵ 오개념 유발도 = `distractor_map` 선지별
선택률 통계(신규 필드 0 — 리포트 축) ⑶ AI 재평가 환류는 v2(초기 난이도와 실측 괴리 상위
문항의 5축 재추정 → 검수 큐 — 자동 덮어쓰기 금지, 기계 자율 *거부*만 허용하는 crosswalk
게이트 계약 준용) ⑷ 학생 풀이 데이터 사용은 명시적 동의 전제(절대 금기 준수).

---

## §4. 정직한 공백 — 지금 하지 않는 것 (사유 명시)

| 공백 | 사유 | 해소 시점 |
|---|---|---|
| 실응답 기반 통계 전부(D9의 가동) | 실학생 응답 0 — 파일럿 전 착수는 입력 없는 파이프라인 | `S3-01` 후 (S4-15 잠금 등재) |
| FR-001 조건 나열형 발문 파서 실전화 측정 | 파서 실재·생성 문항 대상 정확도 측정 미실시(로드맵 S2 미체크). 조건 나열형 생성 밴드가 아직 소수라 측정 표본 부족 | 조건형 밴드 확대 시(D4 리포트가 시점 신호) |
| 품질 15축 ⑦ 조건 완전성 | 단일개념 코퍼스라 소비처 0 판정(2026-07-09) 유지 — 융합·조건형 확대 전 premature | 교차단원(`is_cross_unit`) 밴드 착수 시 |
| 초·중 단원 커버리지 0 | 확장 실행은 `S4-01` 기존 추적 — 이 문서는 중복 등재하지 않고 D4(관측)로 우선순위 입력만 공급 | S4-01 |

---

## §5. 유보 항목의 발화 조건 (지금 안 만들되, 언제 만드는지)

| # | 항목 | 발화 조건 |
|---|---|---|
| ① | Problem↔Formula 연결 | Phase 5b(`formula_refs` 충전) 기존 계획 승계 — 공식 검색·추천 소비처 실재 시 |
| ② | `achievement_standard_codes` 영속화(ORM 매핑) | 빌드타임 4단 조인(L5 주입·D4 리포트)으로 부족한 **런타임** 소비(성취기준 단위 CAT 필터 등)가 실측될 때 — 그 전 영속화는 이중 진실 원천 |
| ③ | Problem↔ProblemType 연결(Phase 3b) | 다음 둘 중 하나 실재 시: ⑴ D4 커버리지 리포트에 유형 축 수요(유형별 공백을 저작 우선순위로 쓰겠다는 결정) ⑵ L6 유형별 추천·출제 소비처(예: "존재_판정 유형 약점 보강" 모드) 착수. 연결 형태는 기존 판정대로 `problem_type_codes` 참조 배열(`signature_patterns` 동형) |
| ④ | 조건 변형·난이도 계열 변형·역문제 생성 | D4 리포트가 특정 밴드 재고 부족을 실측하고, D8 계보 축이 착지해 변형을 *기록할 자리*가 생긴 뒤 — 계보 없는 변형 확대는 G18 재생산 |

---

## 부록 — 실측 근거·관련 코드 (2026-07-28 실측)

- 스키마 정본: `src/backend/whymath_backend/schema/problem.py` — `_METADATA_ONLY_SOURCES`:57 ·
  `persona_fit`:483 · `achievement_standard_codes` 비영속:494~509 · `review_status`:564
- 계보 dead seat: `src/backend/whymath_backend/db/models/problem.py:359`(`ProblemRelation`) —
  harness·l1·l3 참조 0건(grep 실측)
- 노출 게이트: `src/backend/whymath_backend/l6/_shared.py:141`(`is_exposable` — "법적 우선순위가
  교수학·UX보다 앞선다")
- 난이도 보정: `src/backend/whymath_backend/l2/item_calibration.py` · `l2/calibrate_items.py`
- 생성·검증: `src/backend/whymath_backend/l3/equivalent/`(acceptance·canonicalize·retag·
  counterexample_fuzz·rephrase·defect_seeder·스켈레톤 15종) · 배치 CLI `src/backend/whymath_backend/harness/`
- 코퍼스 실측 명령: `for d in data/corpus/problem_bank_*; do wc -l $d/problems.jsonl; done`
  (2026-07-28: 4+620+483+1,080+360+120=2,667 · persona_fit 빈값 2,667/2,667 · `_provenance.json`
  v1만 · `review_status` 전건 미기록)
- 구본 명세(D1 대상): `schemas/v1.1/problem.schema.yaml`(헤더 저작권 절 구본 스탠스) ·
  `docs/strategy/subject_pack_spec_v1.md:171`(참조표)
- 기존 추적 승계(중복 등재 금지 대장): `S4-01-math-k12-complete`(초·중 확장) ·
  `S4-02-proof-learning-support`(학생 증명 피드백) · `S4-09-solution-path-materialization`+
  `S4-10-multi-solution-generation`(다중 풀이 D6 — #635 풀이 축) · Phase 3b(Problem↔
  ProblemType) · Phase 5b(formula_refs) · `S3-01-pilot-cohort`(D9 잠금 게이트)
- 검수 실적 선례(D2 동형 적용 대상): `docs/data/ai_review_batch_240_2026-07.md`(Wilson 상한
  1.11% PASS) · `harness/reviewer_sample_package.py` · `harness/corpus_audit_eval.py`
