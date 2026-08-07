# 오개념(Misconception) 모듈 — 외부 EOS 틀 대조 갭 점검 (2026-08-03)

> **범위**: 외부 참고 문서 『03. 오개념(Misconception)』(0단계: 기능 11 오개념 DB · 12 오개념 자동
> 진단 · 13 맞춤 교정 전략, 1단계 이상 확장 제안: 14 오개념 지식 그래프 · 15 발생 원인 분석 ·
> 16 오개념 예측 · 17 진화·버전 관리 · 18 연구·통계 분석 플랫폼 · 19 AI 기반 신규 오개념 자동
> 발견 — **WhyMath 전용이 아닌 일반적인 EOS 틀**, Kiki 제공)을 현 코드베이스와 대조해 빠진 부분을
> 점검한 기록.
> **형식**: `ai_recommendation_module_gap_review.md`(같은 EOS 틀 시리즈, 2026-08-01) 답습 —
> 시리즈 **11번째** 자매편.
> **이 문서와 자매편(04e)의 역할 분리 — 의도적 이탈 고지**: 기존 gap-review 시리즈(nlp·
> ai_recommendation 등)는 갭 판정과 그 해법(D-설계)을 한 문서에 담아 왔다. Kiki가 이번엔 **갭점검과
> 설계를 2개 문서로 분리**하도록 지정했으므로, 이 문서는 **판정 + 근거만** 담고 "어떻게 고칠지"는
> 각 행에서 `04e_misconception_remediation_design.md §N`으로 위임한다.
> **결론**: 착수 가설("오개념 분야가 얇다")은 **반증됐다** — 카탈로그 843건·런타임 탐지 64종·
> distractor 태깅 1,616문항·가설/증거/임베딩 테이블·거버넌스 테스트 ~60개가 이미 프로덕션이다.
> 진짜 갭은 **진단(12) 축이 아니라 교정(13) 축**이다 — 8종 전략 중 3종만 학생-대면 경로에 배선되고
> 나머지 5종은 코드가 있거나(시각화) 입력이 없거나(선수복습·학습경로) 완전히 없다(개념재설명·
> 구체사례). 1단계(14~16)는 자산은 있으나 정본 관계·분류 개념이 없다. 2~3단계(17~19)는
> 전제조건(엔트리 버전관리·학술 재검수·연구윤리 검토)이 전무해 방향만 기록한다.

관련 정본: `04_pedagogy_engine.md`(오개념 진단·개입 파이프라인 개요) · `04b_misconception_judge_
graduation.md`(judge 졸업, 미착수) · `04c_misconception_seven_stage_separation.md`(정본 7레벨 +
§6 갭 장부 — 이 문서가 실측으로 재확인·확장하는 대상) · `04d_adaptive_pedagogy_engine.md`(오개념
유형 축 bandit) · `edge_design_part3_review.md`(관계 타입 결정 — §4 인용) · `docs/data/
misconception_catalog_v1.md`(데이터 카드) · `ai_recommendation_module_gap_review.md`(시리즈
포맷·§6 반복실수 표 선례) · `backlog/tasks/{REC-02,PED-05,S4-15}*.yaml` · `MEMORY.md` 결정 로그.

---

## §0. 전제 정리 — ID 체계 3종 병존

이후 모든 "몇 건 중 몇 건" 판정에서 **어느 체계 기준인지 매번 명시**한다 — 숫자를 섞어 쓰면
다음 세션이 오독한다(아래 §0-③ stale 사례가 그 실제 위험을 보여준다).

| 체계 | 형태 | 건수(실측) | 정본 위치 | 성격 |
|---|---|---|---|---|
| **kebab-id** | `distribution-over-power` | **64종** | `l4/misconception/catalog.py`(`CATALOG`·`CATALOG_BY_ID`) | 런타임 탐지 정본 |
| **M-id** | `M0425` | **843건** | `data/corpus/misconceptions_v1/misconceptions.json` → `misconception_catalog` 테이블 | 콘텐츠 카탈로그 |
| **ATOM:** | `ATOM:10공수1-01-01-1` | **1,823건** | `data/corpus/atom_graph_v1/graph.json` → 동일 테이블에 투영 | 원자 백본 승격 |

다리는 `misconception_crosslink` 테이블 **64건**(전부 수동 검수 `직접매핑`)뿐 — kebab 64종 전부가
M-id에 연결됐으나, **M-id 843건 중 779건(843−64)은 런타임 탐지와 무연결**이다. 이 갭은 의도적
미채택이 아니라 crosswalk 검수 진행 중 상태다(`docs/data/misconception_crosslink_review_dossier.md`
1,061줄이 그 검수 도시에).

### §0-② stale 표기 발견 (이번 대조에서 실측)
`04c_misconception_seven_stage_separation.md:130`(§5 "Identity/Canonical" 절)은 "런타임 탐지
정본(kebab-id **30종**·`CATALOG_BY_ID`)"이라 적고 있으나, 실측 `CATALOG` 길이는 **64종**이다.
`docs/architecture/02_learner_model.md:218`도 동일 방향의 stale("오개념 카탈로그 **30개** 매칭"
성공 기준)을 갖고 있다 — **두 문서가 서로 다른 시점의 같은 숫자(30)를 각자 굳혀 놓은 것**으로
보인다(2026-07-12 MEMORY 로그: 탐지 카탈로그가 34→40→46→52→58→64로 5회 트랜치 확장됐다). 이
정정은 소유 문서(04c·02)의 몫이며 이 문서는 사실만 기록한다.

---

## §1. 0단계 — 기능 11 「오개념 DB」 항목별 대조

| 세부 관리 항목 | WhyMath 현행 | 판정 | 근거 |
|---|---|---|---|
| 오개념 ID·이름·설명 | `mis_id`·`canonical_statement`(M-id) / `id`·`name_kr`(kebab) | ✅ | `db/models/misconception_catalog.py` · `l4/misconception/models.py` |
| 발생 원인 | `student_wrong_thinking`(자연어 서술) — **구조화된 원인 분류축은 없음** | △ | §4(15 원인분석)로 이관 |
| 관련 개념 | `concept_src_id`(느슨참조, FK 아님) | ✅ 부분 | `misconception_catalog.concept_src_id` — `concept_graph_v1.misconception_codes`는 437/437 전부 `[]`(반대 방향 매핑 미충전) |
| 선수 개념 부족 여부 | 없음(전용 필드 없음, `concept_src_id` 해소로 간접 추론만 가능) | ⚠️ | `l1/misconception/resolve.py` |
| 심각도(severity) | `("blocking","local","cosmetic")` 3단계, 843건 중 blocking 344/local 319/cosmetic 71/null 109 | ✅ | `schema/misconception_catalog.py:41 SEVERITY_VALUES` |
| 발생 빈도(frequency) | **컬럼 없음** — 의도적 미채택(§6-①) | 🚫 | `warmstart.py:84`가 `mapping_score`를 현저성 프록시로 대용 |
| 학년 | `school_level`(초1~고3 전 구간 커버 — 진로선택214·일반선택162·중159·공통144·초5~6:50·초3~4:44·융합41·초1~2:29) | ✅ | `misconceptions_v1/misconceptions.json` |
| 단원 | `domain`(48종) | ✅ | 동일 |
| 관련 성취기준 | `standard_code`·`ccss_code` | ✅ | `db/models/misconception_catalog.py` |
| 대표 오답 | `distractor_rule`(자연어 규칙) + `Problem.distractor_map` JSONB(구조화) | ✅ | §2·§3 참조 |
| 진단 규칙 | kebab 카탈로그의 `signals`·`regex_signals`(64종만, M-id 843건엔 진단 규칙 없음) | ✅ 부분 | `l4/misconception/catalog.py` |
| 교정 전략 | `correction_point`(자연어, DB엔 있으나 런타임 `Misconception` Pydantic 모델엔 미매핑) | △ | §3(13 맞춤교정) 전체 |
| 추천 콘텐츠 | `behavior_skills: ARRAY(Text)`(843건 중 806건 채움) | ✅ 부분 | 마이그레이션 `20260707_1700` — "junction 아님, 신규 엣지 타입 0" 명시 |
| 연구 논문 연결(citation) | **엔트리 단위 없음** — `provenance_note`는 `"AI생성-검수필요"` 파이프라인 태그일 뿐 학술 근거 아님 | 🚫 | `misconceptions_v1/misconceptions.json` `_provenance.json` — 843건이 학술 근거 없는 AI 생성·미검수 상태 |
| 버전관리(엔트리 단위) | **없음** — `created_at`/`updated_at`조차 `misconception_catalog`엔 없음(디렉터리 `_v1`만 버저닝) | 🚫 | `misconception_hypothesis`·`misconception_embedding`엔 타임스탬프 있으나 카탈로그 본체엔 없음 |
| 오개념 간 관계(상위/하위/원인/결과/동시발생) | **없음** | ⚠️ | §4(14 지식그래프)로 이관 — `04e §2` |

**부수 확인**: `_provenance.json` counts 841 vs 실제 843 — 경미한 드리프트. `error_type` 선언
8종 vs 실측 10종(`극대극소혼동`·`값좌표혼동` 초과) — 어휘 강제가 파이프라인 책임으로 위임돼
통과됨.

---

## §2. 0단계 — 기능 12 「오개념 자동 진단」 4경로 대조

| 진단 방법 | WhyMath 현행 | 판정 | 근거 |
|---|---|---|---|
| ① Rule 기반 | `diagnose()` — substring `signals` AND 공출현 + `regex_signals` OR 보조(수치대입 거짓항등식) | ✅ | `l4/misconception/diagnose.py` |
| ② 패턴매칭(대표 오답 비교) | `wrong_form_match.py`(SymPy 거짓항등식) — **shadow-only**(`misconception_wrong_form_mode` 기본 `off`) / `distractor.py`(객관식 오답→오개념) — **스캐폴드**, "실시간 결선은 후속" 자체 docstring 명시 | △ | `config.py:1000` |
| ③ 개념 그래프 기반 추론 | **"없음"이 아니라 "의도적 구조 차단"** — reactive retrieval 원칙(CLAUDE.md)의 구현 | 🚫 (의도적) | `test_misconception_seven_stage_manifest.py::test_misconception_tables_disjoint_from_concept_tables`·`::test_misconception_tables_have_no_foreign_key_into_concept` |
| ④ AI(LLM) 추론 | `judge.py` — 방향 판별 **필터**(EXPRESSES/NOT_EXPRESSES/UNCERTAIN, 생성 아님) | ✅ 코어·기본 off | `04b_misconception_judge_graduation.md`(4플래그 전부 off, 미착수) |
| (문서엔 없으나 실재) 임베딩 의미매칭 | `semantic/matcher.py`(pgvector) — 기본 off | ✅ | `misconception_semantic_mode="off"` |

**출력 스키마 대조**(문서 요구: 오개념ID·신뢰도·원인·관련개념·부족선수학습·추천교정):

| 요구 필드 | WhyMath 현행 | 판정 |
|---|---|---|
| 오개념 ID | `Misconception.id`(kebab) | ✅ |
| 신뢰도 | `MisconceptionMatch.confidence: float[0,1]` | ✅ |
| 원인 | **없음** — 근사물 `matched_signals`/`matched_regex_signals`/`semantic_similarity`(디버그용)뿐 | ⚠️ |
| 관련 개념 | `concept_src_id` 해소(런타임 응답엔 미노출) | △ |
| 부족 선수학습 | **없음**(오개념→선수개념 역추적 경로 없음) | ⚠️ | §3 "선수학습복습" 행 참조 |
| 추천 교정 | 별도 모델 `InterventionDecision`으로 **분리**(진단 응답과 결합 안 됨) | △ |

**reactive retrieval 원칙 강제 지점**(CLAUDE.md L142/203/240 "오개념 preload 금지·reactive만"):
`warmstart.py:180 assemble_warmstart_probe_hints(...) -> list[str]` — 반환 타입이 `list[str]`
(mid만)이라 코칭 필드·본문이 실릴 자리가 **구조적으로 없음**. `prompt_assembler.py:56
render_misconceptions`는 이미 표면화된 활성 가설만 받고 `canonical_statement`(내용)는 미주입.
런타임 게이트 기본값 전부 off(`semantic_mode`·`judge_enabled`·`crosslink_mode`·`wrong_form_mode`).
회귀 가드: `tests/backend/harness/test_wh1_shadow.py:280-310`(warmstart가 `outside_mids`에만
실림을 스파이로 단언).

---

## §3. 0단계 — 기능 13 「맞춤 교정 전략」 8종 전수 대조 (가장 큰 갭)

| 전략 | WhyMath 현행 | 판정 | → 설계 위임 |
|---|---|---|---|
| ① 개념 재설명 | `content_supply.py:195 supply()` — misconception 입력 슬롯 없음(개념 code만 받음) | ⚠️ | `04e §1` 낮은 우선순위(유보) |
| ② 반례 제시 | `intervene.py` `InterventionPattern.COUNTEREXAMPLE`, confidence>0.8 | ✅ | — |
| ③ 시각화 | `visualize.py::visualize_misconception()` **코드 완비·테스트 존재**, **production 호출자 0건**(직접 실측: `api/`·`coach.py` grep 무결과, `l4/__init__.py` export + 테스트에서만 호출됨). 자체 docstring이 "`InterventionPattern.VISUALIZATION`(패턴3) 게이트는 무효 — 신뢰도 게이트 재사용으로 우회" 자백 | △ | `04e §1-1` (최우선 배선 후보) |
| ④ 선수학습 복습 | `prerequisite_coaching.py:32 recommend_prerequisite_coaching(gaps: Sequence[PrerequisiteGap])` — **misconception 파라미터 없음**(직접 실측), 트리거가 BKT/θ(개념숙달도)이지 오개념이 아님 | △ | `04e §1-2` |
| ⑤ 유사문제 반복 | `l3/equivalent/misconception_eval_mc_generator.py` + `harness/misconception_mc_batch.py` — **오프라인 전용**(crosswalk 커버리지 확대용, "v0(검수 전) — 게이트 통과 ≠ 학생 노출"), 실시간 서빙 경로 없음 | △ | `04e §1-3` |
| ⑥ AI 대화형 튜터 | `api/coach.py` + `l4/socratic/select.py` — 고신뢰+최근활성 가설 → `SocraticCategory.ASSUMPTION` 전환 | ✅ | — |
| ⑦ 생성형 문제 | ⑤와 동일 자산(오프라인, 교정 서빙 아님) | △ | `04e §1-3` |
| ⑧ 학습경로 재설계 | `l2/learning_path.py`(`order_learning_path`/`build_learning_path`) — **misconception 미소비**, `PrerequisiteGap`(개념숙달)만 입력 | ⚠️ | `04e §1` (§2 관계셋 선행 필요 — 순서 불변식) |

**요약**: 8종 중 **2종 완전 배선**(반례·거꾸로사고 — 아래 참고: intervene.py는 실제로 3종 결정
`반례/거꾸로사고/보류`를 만듦) + **AI대화형튜터 1종**(소크라테스 연동) = **3종 있음**, **3종
부분(코드는 있는데 배선·입력 끊김)**, **2종 없음**. 즉 "교정 전략이 없다"가 아니라 **"진단→교정
사이가 8종 중 5종에서 끊겨 있다"**가 정확한 진단이다.

---

## §4. 1단계 — 기능 14 지식그래프 · 15 원인분석 · 16 예측 대조

### 14. 오개념 지식 그래프
- **오개념↔오개념 관계**(상위/하위/원인/결과/동시발생): grep 저장소 전체 0건. `misconception_
  crosslink`는 관계가 아니라 **동일 오개념의 ID체계 간 정체성 매핑**(kebab↔M-id)이다.
- **개념↔오개념 연결**: `concept_graph_v1.misconception_codes` 필드는 존재하나 **437개 개념 전부
  빈 배열**(실측: `grep -c misconception_codes data/corpus/concept_graph_v1/graph.json` → 437,
  값은 항상 `[]`). 시드 CSV에서 전문가 입력 대기 상태로 남음.
- **`EdgeType.TRIGGERS_DISTRACTOR`**(`schema/enums.py:662`): **어휘만 선언, 적재 0**. enum 주석
  자체가 "misconception은 아직 그래프 노드가 아니라 L4 카탈로그(kebab id)"라고 명시.
- **⚠️ 중요한 선행 결정 (이번 대조에서 발견)**: `edge_design_part3_review.md`의 "deferred 항목"
  표가 이미 **"pedagogy 엣지화(`misconception_of` 등) — 채택 안 함, #407 신규 엣지 타입 0·참조 키
  유지"**를 명문화했다. 즉 **개념 그래프의 `EdgeType`에 오개념 관계를 얹는 것은 이미 한 번 검토되고
  거부됐다** — `Concept.misconception_codes` + `concept_src_id` 참조 키 방식이 그 결정의 결과다.
  이는 04c §6이 요구하는 "오개념 전용 관계셋"과 **범위가 다르다**(04c는 misconception↔misconception
  관계를, 거부된 결정은 misconception↔concept 엣지화를 각각 가리킨다) — 그러나 `misconception_of`라는
  동일 이름이 양쪽에 등장해 혼동 소지가 있다. `04e §2`가 이 구분을 명시적으로 정리한다.
- 판정: **⚠️ (범위를 좁혀 `04e §2`로 이관 — misconception↔misconception만, concept 엣지화는 재론하지 않음)**

### 15. 오개념 발생 원인 분석 (Causal Analysis)
- `error_type` 8종(부호오류·분배누락·순서오류·해석오류 등)은 **전부 증상축**이다.
- root vs symptom 분류, conceptual/procedural/symbolic/visual/linguistic 분류, diagnostic
  signature 필드, transfer/persistence 축은 **전무** — 04c §6-4가 이를 **"최대 미구현 갭"**이라
  자칭한다: *"단순 실수(slip)와 진짜 오개념을 구분하는 로직도 없다 — 모든 오답을 후보화한다."*
- 현재 완화책: confidence floor 0.65 + judge 방향판별 + 가설 감쇠(반감기 5턴)로 slip을 자연 배제
  (지속 증거 없으면 가설이 소멸) — 지속 승격을 막을 뿐 root/symptom 분류 자체는 없음.
- 판정: **⚠️ (`04e §3`로 이관 — 단, 04c 스스로 "라이브 오진단 실측 시 결정"이라 명시했으므로 04e도
  새 분류축을 만들지 않는다)**

### 16. 오개념 예측 (Predictive Misconception Modeling)
- BKT/DKT θ ↔ 오개념 양방향 신호 **없음** — 이것은 버그가 아니라 CLAUDE.md 원칙6("오개념은 독립
  DB")의 구현이다(`l2/bkt.py:25` "오개념 매핑은 후속" 주석, `l2/` 전체에 misconception 필드 0건).
- 오개념 상태의 시간축 자체는 **L4 독립 테이블**(`misconception_hypothesis`)에 이미 있다 — 감쇠
  반감기5턴 + 강화 + `evidence_links`(polarity ±1, net_support 집계).
- 판정: **⚠️ (`04e §4`로 이관 — BKT/DKT 비결합 유지 전제 하에 좁힌 정의로)**

---

## §5. 2~3단계 — 기능 17 버전관리 · 18 연구플랫폼 · 19 자동발견

짧게: 세 항목 모두 **전제조건이 먼저 없다**.
- **17 버전관리**: 엔트리 단위 version/created_at 필드 자체가 없다(§1 확인). 열려면 먼저 스키마에
  타임스탬프를 추가해야 하는데, 그보다 앞서 **843건이 미검수 AI생성**이라는 사실(§1 citation 행)이
  "버전 이력을 관리할 검증된 콘텐츠"라는 전제 자체를 충족 못 시킨다.
- **18 연구플랫폼**: 학술 인용 필드 부재 + 843건 미검수 AI생성 → 연구 플랫폼을 열 전제(검증된
  근거·재현 가능한 출처)가 없다.
- **19 자동발견**: `crosslink_candidates.py`류의 기존 반자동 파이프라인(779건 미연결 해소용)이
  씨앗은 될 수 있으나, 학생 데이터로 신규 오개념을 마이닝하는 것은 미성년자 데이터 사용 동의
  범위를 넘을 수 있다.

판정만 하고 방향은 `04e §6` 1개 절로 위임한다.

---

## §6. 의도적 미채택 판정 (협상 불가 근거)

| # | 문서 제안 | 불채택 근거 (CLAUDE.md·정본) |
|---|---|---|
| ① | 발생 빈도(frequency) 통계 | 실제 학생 로그 집계가 필요(현재 `problem_attempt` 등 행동 로그 자체가 얇음 — `ai_recommendation_module_gap_review.md` D1 참조). 없는 신호를 날조하지 않는다. `mapping_score`가 임시 대용 |
| ② | 개념 그래프 기반 오개념 추론(traversal) | **구축 플레이북 정면 금기** — 오개념이 개념 traversal에 진입하면 6-1 오염 연쇄(`AI reasoning 오염→retrieval precision 붕괴→relation explosion→tutoring drift→context explosion`, 04c §1)가 재현된다. `test_misconception_seven_stage_manifest.py`가 이 차단을 동결 |
| ③ | 오개념 초기 context preload | CLAUDE.md 원칙6 "오개념 독립 DB(reactive)" 정면 위반 — `warmstart.py`의 타입 수준 차단(`list[str]`)이 이를 구조적으로 강제 |
| ④ | 오개념 그래프 관계 타입 자유 확장(N종) | 관계타입 폭발 금지(5~8개 핵심만) — `04e §2`가 이 제약 안에서 최소 관계셋만 연다 |
| ⑤ | BKT/DKT ↔ 오개념 융합 예측 | CLAUDE.md 원칙6 정면 위반 — 오개념과 학습자 모델(L2)의 의도적 분리 |
| ⑥ | 성적·서열류 예측(오개념 기반 성취 예측) | `ai_recommendation_module_gap_review.md` §2-⑦ "성장곡선 예측 미채택" 근거 승계 — "정답을 빠르게"를 KPI로 쓰지 않는다는 금기의 연장 |

---

## §7. 정직한 공백 — 04c §6이 이미 자인한 것 (근거 재확인만, 해법은 04e)

1. **[Level 2] 오개념 전용 관계셋 + 노드화 미구현** — `misconception_of/caused_by/repaired_by/
   variant_of` 관계와 오개념 간 관계 그래프가 없다. 현재는 `concept_src_id` 참조 + kebab↔M-id
   crosswalk만 가진 **평면 카탈로그**. traversal 진입 차단은 이미 강제되므로 오염 위험은 없고,
   "오개념 노드화 착수 시 도입"으로 유예됐다(`04c_misconception_seven_stage_separation.md:140-144`).
2. **[Level 6] 잔여** — M-id 카탈로그가 `distractor_rule`·`correction_point`를 레코드에 병저장
   (런타임 엔진과 별개 체계·FK 무결·오염 아님). `InterventionPattern.VISUALIZATION`(패턴3) 게이트
   미결선(신뢰도 게이트 재사용으로 우회).
3. **[6-4] root vs symptom · slip 판별 — 04c 자칭 "최대 미구현 갭"** — §4(15) 참조. CLAUDE.md
   "모든 오답은 오개념 후보 분석 시도"(후보화 요구)와 "단순 실수를 오개념으로 처리 말라"(지속 승격
   제한)가 confidence floor + decay로 이미 화해돼 있다. 후속 트리거: "라이브 오진단(slip을
   오개념으로 오코칭)이 실측될 때 별도 설계 슬라이스로 결정"(04c 원문).

이 문서는 "왜 지금 안 하는가"만 재확인한다 — "어떻게 할까"는 `04e_misconception_remediation_
design.md`가 다룬다.

---

## §8. 반복 실수 등재 검토 — "완비된 소비 경로 + 미도달 공급원" 계열 이어쓰기

`ai_recommendation_module_gap_review.md` §6이 6회차까지 정리한 "만들고 ○○을 안 함" 표에 이번
대조에서 나온 두 사례가 같은 형태인지 검토한다.

| 회차 | 사례 | 형태 |
|---|---|---|
| (기존 1~6) | OPS-03·VIZ-01·NLP-01·D1(attempt 미호출)·D1(개인화 off)·D2(select_probe 공급 0) | 각각 CI/적재/배포/입력/활성화/공급원 미결선 |
| **7 (신규 후보)** | **`visualize_misconception()` 완비·production 호출자 0건** | 만들고 **서빙 경로에 배선 안 함** — VIZ-01·NLP-01과 동형(코드 완비, 도달 0) |
| **8 (신규 후보)** | **`prerequisite_coaching`이 오개념 신호를 모름** | 만들고 **신호원 하나를 안 이음** — `REC-02`(select_probe 공급 0)와 동형(인프라는 있는데 이어주는 배선 하나가 없음) |

두 사례 모두 이 문서(사실 확인)에서 등재하고, 해소 설계는 `04e §1`로 위임한다. 공통 구조는
여전히 "소비측이 완비돼 있어서 '존재함'이 '돌아감'으로 읽힌다"이며, graceful 실패(시각화는
조용히 호출되지 않고, 선수복습은 조용히 오개념을 무시)가 증상을 덮는다는 점도 동일하다.

---

## 부록 — 실측 근거 (2026-08-03 직접 검증)

**교정 전략 배선 갭(§3)**
- `src/backend/whymath_backend/l4/misconception/visualize.py` 전문 — docstring이 "패턴3 게이트
  무효" 자백(L12-14), `select_intervention(match) is None`으로 임계 일관(L66-67)
- production 호출자 grep: `l4/__init__.py`·`l4/misconception/__init__.py`(export) +
  `tests/backend/l4/test_misconception_visualize.py`(호출) 외 **0건**
- `src/backend/whymath_backend/l4/prerequisite_coaching.py:32` —
  `recommend_prerequisite_coaching(gaps: Sequence[PrerequisiteGap]) -> CoachingTrigger | None`
  (misconception 파라미터 없음, 직접 Read로 확인)
- `src/backend/whymath_backend/l2/learning_path.py` — `order_learning_path`(L143)·
  `build_learning_path`(L247) 전부 misconception 미소비
- `src/backend/whymath_backend/l4/content_supply.py:195` `supply()` — misconception 입력 슬롯 없음
- `src/backend/whymath_backend/l4/misconception/models.py:120-128` — `InterventionPattern` 4종
  (COUNTEREXAMPLE·CONCRETE_CASE·VISUALIZATION·REVERSE_REASONING), 후자 둘 결정트리 분기 없음

**지식그래프·관계(§4)**
- `data/corpus/concept_graph_v1/graph.json` — `misconception_codes` 437행 전부 `[]`(직접 확인)
- `src/backend/whymath_backend/schema/enums.py:662` — `TRIGGERS_DISTRACTOR` 어휘만, 적재 0
  (docstring L649-656 직접 확인)
- `docs/architecture/edge_design_part3_review.md:227` — **"pedagogy 엣지화(`misconception_of`
  등) — 채택 안 함, #407 신규 엣지 타입 0·참조 키 유지"** (직접 Read로 확인 — §4 인용의 근거)
- `docs/architecture/04c_misconception_seven_stage_separation.md:140-157` — §6 갭 장부 원문
  (Level2·Level6·6-4, 직접 Read로 확인)
- `docs/architecture/04c_misconception_seven_stage_separation.md:130` — kebab-id "30종" stale
  표기(직접 확인, 실측 64종과 불일치)

**진단·출력 스키마(§2)**
- `src/backend/whymath_backend/l4/misconception/diagnose.py` · `wrong_form_match.py` ·
  `distractor.py` · `judge.py`·`judge_seam.py` · `semantic/matcher.py` · `combined.py` ·
  `match_gate.py` · `warmstart.py:180`(`list[str]` 반환)
- `tests/backend/l4/test_misconception_seven_stage_manifest.py` —
  `test_misconception_tables_disjoint_from_concept_tables`·
  `test_misconception_tables_have_no_foreign_key_into_concept`(직접 grep으로 존재 확인)

**백로그·기존 태스크**
- `backlog/tasks/REC-02-misconception-probe-supply.yaml` 전문(직접 Read) — select_probe 후보 공급
  0, "반복 실수 6회차 — 만들고 공급원을 잇지 않음"
- `backlog/tasks/PED-05-learner-state-assembly.yaml` 전문(직접 Read) — `active_misconceptions`
  슬롯, acceptance ①~③
- `backlog/tasks/S4-15-response-driven-difficulty-loop.yaml` — 오개념 유발도 갱신(S4 todo)

**데이터 계층(§0-§1)**
- `src/backend/whymath_backend/db/models/misconception_catalog.py`·`misconception_hypothesis.py`·
  `misconception_crosslink.py`·`misconception_embedding.py`(전체 컬럼)
- `data/corpus/misconceptions_v1/misconceptions.json`(843건·18필드) ·
  `data/corpus/misconception_crosslinks_v1/crosslinks.json`(64건)
- `src/backend/whymath_backend/schema/misconception_catalog.py:41` `SEVERITY_VALUES`
