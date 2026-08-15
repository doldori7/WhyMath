# WhyMath DSL 통합 점검 (2026-08-10)

> **범위**: 저장소의 DSL(선언적 명세) 표면 **전수 8종 + 준표면 2종**을 대상으로, 각 DSL의
> 정의→생산→저장→소비→검증 체인을 끝-끝 실측하고 DSL 상호 간 문법·권위·게이트 정합을
> 대조한다. Kiki 요청("Whymath dsl 통합 점검").
> **형식**: 외부 문서 없는 **저장소 실측 자체 대조** — `subject_content_coverage_gap_review.md`
> (2026-08-10)가 연 형식의 2번째 사례. 절 구성은 기존 갭 리뷰 시리즈 관례를 답습한다.
> **결론**: 착수 전 걱정 지점("DSL이 여러 벌이라 겹치고 충돌할 것")은 **가장 걱정하던 곳에서
> 반증됐다** — Scene↔Visualization은 중복이 아니라 설계대로 합성이고(기지 미검토 축 해소),
> 학생 대면 체인 2벌(ConceptDSL·LearningScene)은 라우트까지 완결이다. 뚫린 곳은 DSL들의
> *몸통*이 아니라 **이음매 4곳**이다: ① 같은 `conditions` 필드를 3개 문법이 공유하는데
> 검사기는 1개만 알아 오탐 130건(S3-28 판정 재료 확정) ② 표시(latex)↔검증(dsl) 병렬 필드의
> 의미 정합 게이트 0 — 실결함 1건(근의 공식 `±`→`+`근 소실) ③ 서버↔클라 scene 계약 게이트
> 0 — 필드 드리프트 4건 무감지 통과 ④ 교수법 선언≠집행 3건(mode_guard 문면 가드 프로덕션
> 호출 0 + 과대 진술 2곳·DB 갈래 dead write 2테이블). 처방: 직접 수정 2건(CI 계약 fixture
> 사각·과대 진술 정정) · 신규 등재 3건(MOB-14·NS-04·PED-16) · 기존 태스크 판정 재료 1건
> (S3-28) · 문서 stale 정오표 10건(핵심 3곳 배너 직접 정정).

관련 정본: `math_dsl_evolution.md` · `math_dsl_failure_mode_qa.md` · `math_dsl_part4_ast_review.md` ·
`math_dsl_principles_review.md` · `math_dsl_remediation_design.md` · `math_dsl_retrieval_analysis.md` ·
`math_dsl_risk_register.md` · `notation_contract.md` · `03c_content_strategy_cache.md` ·
`04d_adaptive_pedagogy_engine.md` · `05a_learning_scene_dsl.md` · `05b_visualization_classification.md` ·
MEMORY.md 결정 로그 2026-06-14(LearningScene)·2026-07-24(교수법-중립 DSL). 측정 HEAD: `5f60f37e`.

---

## §0. 전제 — 이 저장소의 "DSL"은 하나가 아니라 8개다

"DSL 통합"을 물으려면 먼저 무엇이 DSL인지 전수 확정해야 한다. 실측 인벤토리:

| # | DSL | 정의 좌석 | 정본 문서 | 학생 대면 체인 판정 |
|---|---|---|---|---|
| 1 | **ConceptDSL** (교수법-중립 콘텐츠) | `l3/render/dsl.py` | 03c | **완결** — `POST /v1/me/objectives/{id}/study` (`app.py:1087` 마운트). 유일한 개념 콘텐츠 공급 경로 |
| 2 | **LearningScene DSL** (합성 장면) | `l4/learning_scene.py` | 05a | **완결** — `POST /v1/scenes/weak-concept` → `scene_models.dart` 파서 → `scene_renderer.dart` 8-kind 렌더 |
| 3 | **Visualization 명세** | `schema/visualization.py` | 05b | **완결(합성 경유)** — scene 임베드로만 서빙. 독립 라우트 3종은 by-design 미배선(§4-②) |
| 4 | **교수법 팩** | `schema/pedagogy_pack.py` + YAML 7팩 | 04d·PED-01 | **완결(YAML 직독)** — `pack_registry` → `/v1/coach` 프롬프트 4계층 + `runtime_selector`. DB 갈래는 dead write(§2-⑥) |
| 5 | **소단원 DSL** (UnitDSL) | `schema/unit_dsl.py` + `.unit.yaml` | PED-01 | **부분** — `learning_objective` 가지만 서빙 도달. 발주서→슬롯 축은 소비자 0을 거버넌스가 명시 동결(§4-①) |
| 6 | **condition DSL** (문항 조건 등식) | `l3/equivalent/canonicalize.py:47` | S2-m/n·MEMORY 2026-07-06 | **배선·게이트 fail-open** — 생성기 조립(`llm_generator.py:680`)과 QA 축(`qa_pipeline.py:275`)이 소비하나 CI qa_pipeline 게이트는 `continue-on-error`(§2-②) |
| 7 | **표본공간 DSL** (`space=…; event=…`) | `l3/finite_probability.py:288` `parse_finite_model` | 동 파일 docstring | **완결** — `verify_answer` 확률·경우의수 판정 경로 |
| 8 | **formula `dsl` 필드** | `data_pipeline/formula_graph/models.py:73` | formula_graph 계열 | **write-only** — 적재만 있고 SELECT·파싱 소비 0. `formula_node_projection.py:21` 스스로 "조회는 Phase 5b" 자인(§4-⑤) |
| 준 | schemas/v1.1 YAML 9종 | `schemas/v1.1/` | v1.0·v1.1 | 런타임 로드 **0** — 전부 docstring 정본 방식. `hint`·`mastery_state`는 코드 참조조차 0(§4-⑥) |
| 준 | speech AST | `l3/speech_parse.py:21` | notation_contract §5 | hermetic 자족(외부 통합면 없음 — 의도) |

**따름정리**: "DSL 통합"의 위험은 표면 수가 아니라 **공유 지점**에 있다. 8종이 실제로 만나는
곳은 4곳뿐이다 — (a) `conditions` 필드(6·7이 공유) (b) `latex`↔`dsl` 병렬 필드(8) (c) scene
JSON 계약(2·3을 서버·클라가 공유) (d) 교수법 어휘(`FORBIDDEN_MODE_VOCAB`, 4·5가 공유).
§2의 갭 전부가 정확히 이 4곳에서 나왔다.

---

## §1. 체인 실측 지도 — 완결 5 · 단절 지점 요약

**라우트까지 실제 도달하는 완결 체인 5개** (전부 `app.py` 마운트 실측):

1. `concept_content_v1`(437) → `from_concept_content`(`dsl.py:130`) → `attach_assessment`
   (`assessment_bank.py:142`) → `get_concept_dsl` 캐시(`content_supply.py:217`) → `supply()`
   → 어댑터 렌더 → **`/v1/me/objectives/{id}/study`**
2. `pedagogy_packs_v1/*.yaml`(7) → `pack_registry.get_pack` → `coach.py:_pack_for` →
   `PolyaCoach.decide(pack=)` → `build_system_prompt` 4계층 → **`/v1/coach`**
   (`pedagogy_pack_prompt_enabled` GA 플래그)
3. `get_pack` → `runtime_selector.decide()`(사전 교수학 게이트 포함) → `supply()` → **`/study`**
4. `.unit.yaml` → `unit_compiler` → `learning_objective` 테이블 → `study.py:118` → **`/study`**
   (단 데이터는 소단원 1·목표 4 — 파일럿 정지 상태, §4-①)
5. scene: `generate_learning_scene`(`scene_generation.py:274`, Visualization 합성 임베드) →
   **`/v1/scenes/weak-concept`** → `scene_api.dart` → `scene_models.dart` → `scene_renderer.dart`

관측 보조: `dsl_render_rate`는 `study.py:208` 프로덕션 로그 + `concept_assessment_index`
before/after 리포트가 소비한다 — **MEMORY 2026-07-30 "프로덕션 리포트 소비처 0"은 S3-26으로
부분 해소**(단 `ops/` 정식 리포트 항목은 여전히 0 — `cost_report.py:147`가 in-process 이중
회계 원칙에 따라 스스로를 관측 보조로 강등했기 때문. 현 상태 서술이 정확하려면 "라우트
로그 1 + 오프라인 리포트 1, ops 리포트 0").

**단절 지점**(상세 판정은 §2·§4): 발주서→슬롯 축 전체(§4-① 동결) · pedagogy_pack/UnitSpec
DB reader 0(§2-⑥) · mode_guard 문면 가드(§2-⑤) · formula dsl 소비(§4-⑤) ·
`/v1/visualizations/*` 3라우트(§4-②) · scene 서버↔클라 계약 게이트(§2-④).

---

## §2. 이번 점검의 확정 사실 — 이음매 갭 6 + 기지 공백 해소 2

### ① Scene ↔ Visualization: 중복 아님 — 합성 확정 (기지 미검토 축 해소)

MEMORY 결정 로그의 기지 공백("`05a_learning_scene_dsl.md` 미완독으로 Scene DSL과
Visualization의 중복 여부는 미검토 축", 2026-07 시각화 인벤토리 항)을 이번에 닫는다.
실측: `LearningScene`은 시각화 필드를 재정의하지 않고 `learning_scene.py:96-100`
`VisualizationElement.ref: Visualization`으로 **참조 임베드**하며, `scene_generation.py:347-357`이
`generate_visualization_spec` 결과를 그대로 합성한다. 모바일 `Visualization` 파서도
`scene_models.dart` **1벌**뿐이다. 05a가 약속한 "Visualization 위 합성 계층"이 설계 그대로다.
05a 불변식(답 미루기·낙인 금지)의 코드 게이트도 실재·이중화 확인 — `learning_scene.py:269`
`_validate_invariants` + `test_scene_dsl_layer_governance.py` 금지 토큰 11종 + Dart판
`no_math_logic_governance_test.dart`. 잔여 관찰 2건은 저위험 정직 공백으로 §4-⑦·⑧에 격리.

유일한 실제 중복은 스키마가 아니라 **서빙 오케스트레이션**이다: `api/scene.py:93-107` ↔
`api/visualization.py:85-114`가 개념 로드→스타일→가시성→숙달→라우팅 ~40행을 미러하고
주석 스스로 "미러"라 부른다. 후자의 3라우트가 클라 호출자 0(by-design 등재)이므로 이
중복의 처방은 리팩터가 아니라 **PED-16 판정 시 라우트 거취와 함께 결정**(§3-D4 notes).

### ② condition DSL 오탐 130건 — 원인 확정, S3-28 판정 재료 (본 세션 핵심 실측)

`S3-28`(todo)이 "probability/stats DSL 130건 오탐 **가능성** 판정"으로 등재해 두고
`.github/workflows/ci.yml`의 qa_pipeline 게이트가 `continue-on-error`(fail-open)로 대기
중이던 사안이다. 본 세션에서 **오탐 확정 + 구조 원인 확정**까지 실측했다:

**같은 `verify.conditions` 필드를 3개 문법이 공유한다.** 판별 키는 `answer_kind`인데
`condition_dsl_violation(condition)`은 `answer_kind`를 인자로 받지 않는다 — 스코프 필터
부재가 130건의 구조적 원인이다.

| 문법 | 생산자 | 정당한 소비자(파서) | 위반 판정 |
|---|---|---|---|
| ① 맨 (부)등식 `3*x**2-7*x+4 = 0` | 스켈레톤 생성기 대다수(`skeleton_generator.py:367` 등) | `canonicalize.py` sympify | 통과 (2,517건) |
| ② CSV 수치 리스트 `1,2,3,4,9` | `conceptual_count_mc_generator.py:447+` | `verify_answer.py:1338+` `_parse_number_list` | **오탐 96건** |
| ③ 표본공간 미니 DSL `space=dice(n=2,faces=6); event=sum==2` | `finite_probability_skeleton_generator.py:118+` | `finite_probability.py:288` `parse_finite_model` | **오탐 34건** |

**130건 재현 분해**(본 세션 직접 재현 — 코퍼스 2,647건 전수, CI 주석 수치와 정확 일치):
`mean_equals_median` 24 + `events_independent` 24 + `conditional_equal` 24 +
`dot_product_scalar` 24 (이상 문법 ②=96) + `finite_probability` 26 + `finite_count` 8
(이상 문법 ③=34). **6개 answer_kind 전부 자체 파서가 정상 소비하는 정당 데이터**이며 결함
0건이다. 처방 방향(구현은 S3-28 소유): `answer_kind`로 문법 ②③을 각자의 파서 검증에
위임(스코프 필터)하고, 문법 ①만 `condition_dsl_violation`에 남긴 뒤 `continue-on-error`
제거. 부차 결함 1건 동봉 — 아래 ③.

### ③ condition 검사기의 전처리 계약 분열 — `to_sympy_source` 우회

`notation_contract.md` §3은 `to_sympy_source`(`l3/symbolic_equivalence.py`)를 **입력 정규화
단일 권위**로 선언했다. 그런데 `condition_dsl_violation`은 `sympy.sympify` **직접 호출**
(`canonicalize.py:66-67`)이라 유니코드 위첨자·암묵곱을 처리하지 못하고, 같은 검사기를 쓰는
두 경로의 계약이 갈린다 — `test_formula_governance.py:137`은 `to_sympy_source(dsl)`를
**거쳐서** 호출하고, `qa_pipeline`·`llm_generator`는 원문을 직접 넣는다. 결과: `2x = 0`
같은 입력이 경로에 따라 위반/통과가 뒤집힌다. 현행 코퍼스에서 실피해 0(문법 ①은 전부
`*` 명시 곱)이나, S3-28 구현 시 스코프 필터와 함께 정규화 경유를 일원화해야 재발 축이
닫힌다. (S3-28 notes에 반영 — §3.)

### ④ scene 응답 계약: 서버↔클라 교차 게이트 0 — 필드 드리프트 4건 무감지 통과

백엔드 필드 동결(`test_scene_dsl_layer_governance.py` 화이트리스트)과 py↔js 교차 골든
(`render_contract.json`·`notation_contract.json`)은 있는데, **백엔드↔Dart scene 계약
테스트가 없다**(`scene_models.dart`를 참조하는 테스트·스크립트 0건). 그 사각으로 이미
드리프트 4건이 CI를 통과해 있다:

| 백엔드 필드 | 상태 | 성격 |
|---|---|---|
| `SceneLearnerContext.active_hypothesis_confidences` (`learning_scene.py:75`) | `api/scene.py:121`이 실제 채워 보내는데 클라가 파싱 안 함 | **활성 드리프트** |
| `ParamControlElement.value_range` (`:118`) / `.step` (`:121`) | 생성자(`scene_generation.py:367`)도 안 채우고 클라도 모름 | **죽은 좌석 2** |
| `Visualization.visualization_id` (`schema/visualization.py:213`) | 클라 부재 | 드리프트 |

런타임 파손은 없다(json_serializable이 미지 키 무시) — 그래서 더 위험하다. 침묵 통과가
계약 부재의 증거다. 같은 축의 잔여: `math_dsl_failure_mode_qa.md` invariant ⑩("렌더 선택
단일 진실원")이 py/js는 계약화됐는데 **Flutter `scene_renderer.dart:107` `webViewTypes`가
하드코딩 집합**으로 남아 3벌 중 1벌이 미계약. → **MOB-14 등재**(§3-D2).

### ⑤ 교수법 문면 가드(mode_guard) — 프로덕션 호출 0 + 과대 진술 2곳 (정본화≠집행 재발형)

`l4/pedagogy/mode_guard.py:127` `check_forbidden_modes`(팩이 금지한 교수 모드가 코치 *응답
문면*에 등장했는지의 사후 가드)의 프로덕션 호출자는 **0**이다 — 유일 소비처는 오프라인
결함주입 측정 `harness/pedagogy_pack_fidelity_eval.py`(CI 상시). 그런데 선언은 배선을
주장한다:

- `config.py:229` `pedagogy_pack_prompt_enabled` 설명 — "4계층 발문 조립기·**forbidden_modes
  가드를** … 경로에 얹을지 … OFF면 팩 조립기/**guard 미호출**" → 실측: ON이어도 guard는
  호출되지 않는다(`polya/engine.py:105-118`은 `build_system_prompt`만 호출).
- `l4/pedagogy/__init__.py:5` — "모드 가드(`mode_guard`)를 stateless 코치 경로에 옵트인·플래그
  게이트로 얹는다" → 동일 과대 진술.

이는 PED-06→PED-08이 잡았던 **"정본화를 집행으로 착각"** 유형의 재발형이다(그때는 노출
계약, 이번은 억제 계약). 완화 요인: *사전* 가드는 실재한다 — `runtime_selector.py:83+`가
같은 어휘로 선택 시점에 WORKED_EXAMPLE 축을 강등하고, `mode_guard` 자신도 6개 모드를
`DEFERRED_MODES` 정직 공백으로 선언했다. 즉 구멍은 "가드 전무"가 아니라 **"응답 문면
사후축의 집행 지점 부재 + 그 부재를 가리는 선언"**이다. 처방: 과대 진술 2곳은 본 세션
직접 정정(§3-F2), 집행 지점 배선 여부는 **PED-16 판정**(§3-D4).

> **해결 부기(2026-08-15)**: PED-16의 재검토 조건("WH-1 루프가 PedagogyPack을 참조하게 되는
> 시점")은 PED-23(회수)이 충족했다 — coach가 `decide(pack=)`에 넣은 같은 팩 객체를
> `run_wh1_primary_turn(pack=)`으로 thread해 톤필터 직전 런타임 가드를 복원
> (`mode_guard_runtime_enabled` 옵트인·기본 OFF). 본 절의 나머지는 감사 시점 기록으로 유지.

### ⑥ 교수법 DSL의 DB 갈래 — dead write 2테이블 (이중 정본 위험)

- `pedagogy_pack` 테이블: `PedagogyPackStore.populate`(`l1/pedagogy/populate.py` CLI)가 쓰기만
  하고 **ORM reader 0**(select/get 전수 grep 0건). 런타임은 전부 `pack_registry`의 YAML 직독.
- `unit_spec` 테이블: `unit_compiler.py:304`가 쓰기만 하고 reader 0.
  `harness/objective_coverage.py:295`(CUR-02 산출물)조차 DB가 아니라 `.unit.yaml` 파일을
  직접 glob한다(테이블 우회).

`pack_registry.py:10`이 "L1 시더의 DB 적재와 무관한 별개 좌석"이라 자인하므로 *몰래 남은*
코드는 아니다. 그러나 reader 0 테이블은 YAML 개정 후 재시드를 잊는 순간 **조용히 갈라지는
두 번째 정본**이고, OPS-22 탐지기의 4축(HTTP·EventType·시계열·CLI) 어디에도 안 잡히는
사각이다(시계열 축은 TimescaleDB 테이블만 스캔). 거취 판정(제거 vs 레지스트리의 DB 전환
vs by-design 선언+감사축 확장)은 **PED-16**(§3-D4).

### ⑦ 공유 계약 fixture의 CI 사각 — `data/*.json` 변경이 어느 잡도 안 깨움 (본 세션 수정)

`notation_contract.md` §4는 "새 케이스는 fixture에만 추가하면 **양 CI가 자동 검증**"을
약속했는데, PR 경로필터 실측 결과 거짓이었다(수정 전 기준): backend 필터는
`^(src/backend/|tests/backend/|conftest\.py$|ci\.yml$)`, web 필터는
`^(src/web/|schemas/|ci\.yml$)` — **`data/notation_contract.json`(py↔js 수치 골든)과
`data/render_contract.json`(py↔js 렌더 계약)만 바꾸는 PR은 두 골든 잡이 모두 skip**되고,
결함은 머지 후 main push 전체 실행에서야 터진다. 이는 2026-07-21 정합성 검토가 `schemas/`에
대해 봉합한 "교차영역 계약 드리프트 사각"과 정확히 같은 부류의 잔여다. 파일 2개를
backend·web 필터에 명시 추가하는 **본 세션 직접 수정**(§3-F1) — 두 파일 변경은 드물어
비용 영향은 무시 가능하고, 약속("양 CI 자동 검증")이 그제서야 참이 된다.

### ⑧ formula `latex`↔`dsl` — 같은 레코드 안의 서로 다른 수학 (정합 게이트 0)

`formula_graph_v1/formulas.jsonl` 25건은 표시용 `latex`와 검증용 `dsl`을 병렬 보유하는데
**두 필드의 의미 동치를 확인하는 게이트가 없다**(`validate.py`는 id 유일성·family 단일성만,
`test_formula_governance.py:129`는 dsl의 *파싱 가능성*만). 실결함 1건 직접 확인:

```
formula.quadratic.roots
  latex: x = \frac{-b \pm \sqrt{b^2 - 4ac}}{2a}     ← 두 근(±)
  dsl:   x == (-b + sqrt(b**2 - 4*a*c))/(2*a)        ← +근 하나만
```

`dsl`은 현재 write-only(§4-⑤)라 학생 피해 0이지만, Phase 5b(formula_refs·resolution)가
이 필드를 소비하기 시작하는 순간 **음의 근이 계약에서 소실된 채 유통**된다. 소비 시작
*전*이 봉인 적기다. vieta 계열의 기호 불일치(latex `\alpha,\beta` ↔ dsl `r_1,r_2`)는
관례 차이로 실害 없음(전건 조사 결과 의미 결함은 ± 1건). → **NS-04 등재**(§3-D3).

---

## §3. 처방 — 직접 수정 2 · 신규 등재 3 · 기존 태스크 재료 1

### 직접 수정 (본 세션·본 브랜치)

- **F1. CI 계약 fixture 사각 봉합** (§2-⑦): `ci.yml` backend·web 경로필터에
  `data/notation_contract\.json$`·`data/render_contract\.json$` 추가. `schemas/` 선례
  (2026-07-21)와 동일 원리 — 공유 계약 아티팩트는 그 계약의 골든을 실행하는 모든 잡을
  트리거해야 한다.
- **F2. 과대 진술 정정** (§2-⑤): `config.py:229` 설명·`l4/pedagogy/__init__.py:5` docstring을
  실상("조립기 배선·문면 가드는 오프라인 측정 전용, 집행 지점은 PED-16 판정")으로 정정.
  동작 무변경(설명 텍스트만).
- **F3. math_dsl 문서 stale 핵심 3곳 배너** (§5): failure_mode_qa(FormulaNode 정면 충돌) ·
  remediation_design(§1.3-2/3 완료·배선 역전) · retrieval_analysis(§4 skill 엔티티 실재).

### 신규 등재 (backlog.py add)

- **D2 → `MOB-14`** scene DSL 서버↔클라 계약 동결: 드리프트 4필드 각각
  파싱 추가/좌석 제거 판정 + `webViewTypes` 하드코딩을 `render_contract.json` 계약으로 결선
  (invariant ⑩ 잔여 1/3) + 재발 방지 게이트(계약 fixture 또는 응답 골든의 Dart판 —
  `no_math_logic_governance_test.dart` 선례 형식).
- **D3 → `NS-04`** formula `latex`↔`dsl` 의미 정합 게이트: SymPy 기반 동치 검사(±·해집합
  보존 축 포함)를 `test_formula_governance` 계열에 추가하고 `quadratic.roots` 결함을 ±-중립
  형(예: `(2*a*x + b)**2 == b**2 - 4*a*c`) 또는 근 열거형으로 봉인. Phase 5b 소비 시작 전
  선결.
- **D4 → `PED-16`** 교수법 DSL 선언≠집행 3건 판정: ⓐ mode_guard 문면 가드 집행 지점
  (코치 응답 경로 배선 vs by-design 선언) ⓑ `pedagogy_pack` dead write(제거 vs registry DB
  전환 vs 유지+감사) ⓒ `unit_spec` dead write 동일 판정. §2-①의 scene↔visualization 서빙
  미러 40행·라우트 거취도 이 판정에 병합(별건 등재로 쪼개지 않는다 — 전부 "선언과 집행의
  거리" 한 축).

### 기존 태스크 판정 재료 (등재 불요·구현 소유권 불변)

- **S3-28**: §2-②·③이 판정 재료다 — "오탐 가능성"은 **오탐 확정**(130건 전건 문법 ②③의
  정당 데이터·결함 0), 구조 원인은 answer_kind 스코프 필터 부재, 동봉 결함은 전처리 계약
  분열. 구현(스코프 위임 + `continue-on-error` 제거)은 S3-28 착수자 몫.

---

## §4. 의도적 미채택·정직한 공백 — 재등재 금지 목록

이번 실측에서 "끊김"으로 관측됐으나 **의도가 선언돼 있거나 기존 좌석이 이미 추적 중**이라
갭으로 등재하지 않는 것들. 재발견·중복 등재를 막기 위해 발화조건과 함께 명시한다.

1. **발주서(work_order)→슬롯 생성→서빙 축 전 구간 소비자 0** — 고장이 아니라
   `test_zero_production_callers_governance.py:154`가 `src/` 전수 스캔으로 **명시 동결**한
   파일럿 정지 상태(신규 소비자 1줄에 CI red). 커버리지 관측은 CUR-02(done)가 좌석 완비.
   발화조건: 소단원 DSL 저작이 재개돼 두 번째 `.unit.yaml`이 들어올 때(그때 발주서→슬롯
   시그니처 불일치 — `work_order`의 `{objective_id, slot_type, count}` vs `build_slot_rows`의
   `slot_manifest` — 도 함께 상환).
2. **`/v1/visualizations/*` 3라우트 클라 호출자 0** — `declared_unwired_audit.py:733-745`가
   by-design 등재 완료(OPS-22 축). 거취는 PED-16 판정에 병합(§3-D4).
3. **figure.spec 부재** — 부재가 아니라 **거부가 정본**: 노드에 렌더 명세를 넣지 않는다
   (Renderer=Plugin). `test_models.py:270-272`가 거부 자체를 CI로 동결.
4. **AST 5계층 미구축** — `math_dsl_part4_ast_review.md` 판정 여전히 유효(전수 grep:
   Semantic AST 계층 0건·speech AST는 hermetic 자족). 과공학 방지 축 유지.
5. **formula `dsl` 소비 0** — `formula_node_projection.py:21` "Phase 5b" 자인. 단 소비 시작
   전 NS-04(정합 게이트)가 선결이라는 순서 제약이 이번에 추가됐다.
6. **schemas/v1.1 런타임 로드 0** — docstring 정본 방식은 전 스키마 공통의 의도. 다만
   `hint.schema.yaml`·`mastery_state.schema.yaml`은 **코드 참조조차 0**(타 스키마의 YAML 내부
   상호 참조뿐) — 페이퍼 갭으로만 기록. 발화조건: 힌트 영속화·숙달 상태 v1.1 물화 착수 시
   해당 스키마의 현행성 재검(§5 정오표와 같은 stale 위험).
7. **`answer_deferral_max_level` 구속력 0** — `api/scene.py`가 미전달(기본 4) + 생성이
   `hint_level=1` 하드코딩이라 답 미루기 불변식 ①이 프로덕션에서 자명하게 참. 스키마
   게이트는 실재하므로 결함 아님. 발화조건: hint_level 가변 생성(LLM 발화 소켓 확장) 도입 시
   운영 파라미터를 학생 상태 기반으로 전달해 게이트에 변별력 부여.
8. **`parse_learning_scene` 프로덕션 미배선·concept_id 참조 무결성 S3 연기** — 생성자
   `@model_validator`가 3불변식을 동등 실행하고, 카탈로그 사전 필터(`scene_generation.py:248`)
   + concept가 DB 실재 로드라 실위험 낮음. 05a §4-1의 연기 선언 유지.
9. **PROBLEM_BASED 렌더 가능 61/437(14%)** — S3-26이 참조 주입 배선까지 완료, 잔여는
   `concept_assessment_v1` 뱅크 커버리지(콘텐츠 저작 축). 문제은행 커버리지 계보(ARCH-18·
   ARCH-28/KG-02 — 미머지 subject 리뷰)에 종속 — 별도 등재 시 중복.
10. **`l1.pedagogy.compile`·`populate` CLI 수동 운영** — 데이터가 소단원 1개인 파일럿
    시절의 자연 상태. OPS-22 harness_clis 축은 `harness/`·`ops/`만 스캔하므로 사각이나,
    발화조건(1과 동일)에 묶는다. DEFERRED_MODES 6종(`mode_guard`)·`KTypeResolver` 클래스
    테스트 전용도 같은 부류의 선언된 정직 공백.

---

## §5. math_dsl 문서 계열 stale 정오표 (실측 대조 10건)

문서 7종+notation_contract를 코드와 전수 대조한 결과. **의사결정을 오도할 수 있는 핵심
3건(★)은 본 세션에서 배너로 직접 정정**, 나머지는 이 정오표가 정본이다(개별 문서의 수치를
일일이 고치면 다음 실측 때 또 stale — 리뷰 문서가 최신 실측을 정본화하는 시리즈 관례).

| # | 문서:위치 | 문서 서술 | 실측 | 처리 |
|---|---|---|---|---|
| 1★ | `math_dsl_failure_mode_qa.md` Part A #1·Q9-1 | "FormulaNode 미도입 = 정답·premature 금지" | `db/models/formula_node.py`·`l1/formula_graph/` 실재. 자매 문서(evolution·risk_register)는 2026-07-08 canonical-only 개정 배너 보유, 이 문서만 누락 — 계열 내 정면 충돌 | 배너 정정(F3) |
| 2★ | `math_dsl_remediation_design.md` §1.3-2 | "M-id crosswalk 매핑 채택·적재는 잔여" | `misconception_crosslinks_v1/crosslinks.json` 64건 채택·적재 완료(검수:Kiki 2026-07-12) | 배너 정정(F3) |
| 3★ | 동 §1.3-3 | "`learning_scene`·`wh1_loop` shadow 배선 불필요로 종결" | 두 곳 모두 배선 실재(`learning_scene.py:369`·`wh1_loop.py:498`) — 문서 판정과 코드가 정반대 | 배너 정정(F3) |
| 4★ | `math_dsl_retrieval_analysis.md` §4 | "skill 엔티티는 존재하지 않는다·승격은 principles_review 결정 대기" | `skill_node`·`problem_type_node`·`formula_node`·`strategy_node`·`solution_node` 5종 ORM 실재. 결정은 `concept_node_layering_decision.md` §0에서 기완료 | 배너 정정(F3) |
| 5 | `failure_mode_qa` Part C ⑩·⑫ | "invariant 신설 필요(순위 3·6)" | ⑫ 완료(`event_data_contract.py`+게이트) · ⑩ 2/3 완료(py/js 계약·Flutter 잔여는 MOB-14) | 정오표+1★ 배너에 병기 |
| 6 | 그래프 규모 — `evolution` §1 "503노드/541엣지" vs `risk_register`·`failure_mode_qa` "2,697/2,213" | 3중 불일치 | 실측 `atom_graph_v1/graph.json` = **2,683 노드(217/643/1,823)·2,210 엣지** | 정오표 정본 |
| 7 | 오개념 규모 — 3개 문서 공통 "kebab 30·M-id 839" | — | 실측 kebab **64**(`catalog.py`)·M-id **843** | 정오표 정본 |
| 8 | `risk_register` §0/§1 라인 앵커(`concept.py:213` 등) | — | PR #350·#417 리팩터로 전부 다른 코드 지칭 — 파일 단위만 유효 | 정오표 경고 |
| 9 | `notation_contract.md` §4 "fixture만 추가하면 양 CI 자동 검증" | — | 거짓이었다(§2-⑦) → **F1 수정으로 참이 됨** | F1로 해소 |
| 10 | `notation_contract.md` §5 "speech 골든 38케이스" 외 소수치 | — | 실측 39(게이트 ≥30이라 무해)·embedding 거버넌스 13→15 테스트 | 정오표 정본 |

이 밖에 대조가 **일치를 확인**한 축(불변식 게이트 6종 실재·적재 시점 cycle DFS·traversal
예산 depth 5+breadth 64 단일 출처·EdgeType 6종 동결·py↔js 골든 실재 등)은 지면 관계로
생략한다 — "약속 대비 실재" 판정에서 계열 전체의 다수는 **실재**였다. stale은 코드가
문서보다 *앞서간* 흔적이 대부분이며(완료·배선을 문서가 못 따라옴), 코드가 문서를 어긴
방향의 위반은 mode_guard 과대 진술(§2-⑤)이 유일했다.

---

*측정: 2026-08-10 · HEAD `5f60f37e` · 게이트 실측 — OPS-22 4축 감사 exit 0 · DSL 게이트
테스트 103건 통과(l3/render 40·scene 거버넌스·pedagogy 스키마 동결·ORM — 범위 한정 실행,
전체 스위트는 CI 판정) · condition 위반 130건 재현 일치.*
