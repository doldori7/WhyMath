# 파일·ID 정책과 Graph DB 진화 — 플레이북 Part 9 준수 검토

> **범위**: 구축 플레이북 **Part 9. 파일·ID 정책과 Graph DB 진화**
> (`docs/standards/playbook_part_review_questions.md:92-98`) 3개 준수 항목을 현 코드베이스에
> 대해 **엄격(strict) 재검토**하고, 발견된 위반을 시정한 기록.
> **형식**: `edge_design_part3_review.md`·`part2_node_design_review.md`(플레이북 vs 현재상태 갭
> 분석) 답습.
> **결론**: 3항목 **전부 위반** 판정. Kiki가 최엄격 시정을 선택 → concept_id를 교육과정 결합
> `{TRACK}-{AREA}-{NNN}`에서 **교육과정·언어·렌더러 무관 의미론 `math.<area>.<slug>`**로 전면 재-ID,
> 표시이름 `locales/` 분리, `ids.yaml` Canonical ID Registry 신설. 3 슬라이스(P2d-a 데이터파이프라인·
> P2d-b 백엔드·P2d-c 문서)로 스테이징. 실데이터 **437 노드·581 엣지 error 0 불변**.

법칙(Part 9): *"파일명은 버려도 ID는 남는다." Canonical Stable ID · YAML→GraphDB · registry.*

---

## 요약 — 3개 항목 판정

| # | Part 9 항목 | 검토 전 | 검토 후 | 근거 |
|---|---|---|---|---|
| ① | ID가 `math.calculus.limit` 형태로 파일명·언어·**교육과정**·렌더러 무관·불변인가 | ❌ **위반** | ✅ | `{TRACK}-{AREA}-{NNN}`의 TRACK(ELEM/MID/HIGH)=**학년대=교육과정 배치 결합**·NNN=비의미론 순번. `MEMORY.md:805`는 이 ID를 "`curriculum_matrix` 개념 축과 동일 값"으로 **의도적 커리큘럼 결합** 설계 → 플레이북이 경고하는 `KR2022.math2.limit` 안티패턴. → **`math.<area>.<slug>` 전면 재-ID**(area=교육과정-독립 영역어·slug=name_ko 로마자화) |
| ② | 표시이름(locale)이 노드에서 분리(`locales/`)·slug≠canonical | ❌ **위반** | ✅ | `name_ko/en/ja`가 **노드 내장**·스키마(`concept.schema.yaml`)·아키(`01_data_foundation.md`)가 인라인 3언어 **강제** → `locales/` 미분리(Part 2 Concept Purity에도 저촉). → **name_\* 노드 제거·`locales/{lang}.json` 분리** |
| ③ | YAML→GraphDB 경로·**Canonical ID Registry**(`ids.yaml`)로 중복·rename·migration 추적 | ❌ **위반** | ✅ | registry **부재**. `id_map.csv`는 미추적 생성물·rename 이력 추적 없음. → **`ids.yaml` 신설**(canonical·src_id·aliases·P2a+P2d 이관 이력)·거버넌스 테스트로 단일 진실 동결 |

> **엄격 판정 원칙**: 이전 검토 초안의 "accepted deviation"(봐주기)을 기각했다. ①의 `{TRACK}`은
> "birth-time frozen 니모닉"이라는 변호가 가능하나, 학년대(교육과정 배치)가 ID 문자열에 남는 한
> 플레이북 "교육과정 무관"을 **문자 그대로** 위반한다. 폐기된 `UC.<domain>.<topic>.<slug>`(예
> `UC.calc.limit.epsilon-delta`)가 `math.calculus.limit` 이상에 더 가까웠고 P2a가 이를 후퇴시켰다는
> 사실이 판정을 굳힌다.

---

## 항목별 상세

### ① ID — 파일명·언어·교육과정·렌더러 무관·불변

**현황(위반):** 정본 `concept_id` = `{TRACK}-{AREA}-{NNN}`(예 `HIGH-CALC-042`).
- `TRACK` ∈ {ELEM, MID, HIGH, RT, OLY}는 첫 `standard_codes`의 **학년대수**(2/4/6=ELEM·9=MID·10/12=HIGH)에서 파생 → **학년(교육과정 배치)이 정본 키에 밀봉**. `HIGH-`는 `KR2022.math2.limit`의 `math2`(고등 과목)와 동형.
- `NNN`은 (TRACK, AREA) 그룹 안 순번 → **비의미론**(`math.calculus.limit`의 semantic slug와 반대).
- `MEMORY.md:805`·`concept_graph.md §2.4`가 이 ID를 "`curriculum_matrix`의 '개념 축'과 동일 값을 공유"하도록 설계 = **정본 ID를 커리큘럼 축에 의도적 결합**(플레이북 8대 원칙 ⑤ Curriculum Overlay 위반 — 커리큘럼은 overlay여야지 ID에 박으면 안 됨).

**갭:** 학년 재배치·교육과정 개정 시 같은 수학 개념의 canonical ID가 흔들린다(같은 극한 개념이 한국 고등·타국 중등이면 TRACK이 달라짐). "파일명은 버려도 ID는 남는다"의 정신 위반.

**교정(P2d-a):** 정본을 **`math.<area>.<slug>`**(교육과정·언어·렌더러 무관 의미론)로 전면 재-ID.
- `<area>` = `_TOPIC_AREA_MAP`(레벨 접두 제거 후 토픽→AREA 코드)을 `_AREA_SLUG_MAP`으로 **교육과정-독립 영역어**에 사상(GEO→geometry·CALC→calculus·`[중]기하`·`[고]기하`→동일 `geometry`). **학년 결합이 사라진다.**
- `<slug>` = `name_ko`의 결정론적 로마자화(`hangul_romanize.romanize`·국립국어원 표기법 기반 간이 음역·외부 lib 0). 발급 시 동결.
- 옛 `{TRACK}-{AREA}-{NNN}`은 폐기하되 **`aliases`의 교육과정축 오버레이 코드**로 보존 → `curriculum_matrix` "개념 축" join을 alias 조회로 유지(Curriculum Overlay 원칙 준수).
- 실측: 437 개념 → 415 유일 `(area,slug)` + **22 충돌**(기본수학↔공통수학·grade 제거로 병합)에 `(tier,src_id)` 정렬 `-2` 접미 = 437 유일 canonical. 학년 토큰 0.

### ② 표시이름 locale 분리 · slug≠canonical

**현황(위반):** `name_ko`(필수)·`name_en`·`name_ja`가 **노드 필드**. `concept.schema.yaml:74-92`·
`01_data_foundation.md:80`이 인라인 3언어를 **강제**(스키마 자체가 플레이북과 모순). 표시문자열이
identity 노드에 붙어 Part 2 Concept Purity에도 저촉. (slug를 canonical로 쓰진 않음 — 그 소항목은 준수.)

**갭:** 표시이름이 노드에 있으면 렌더러·튜터가 개념 정체성과 표시문자열을 한 곳에서 읽어, i18n 확장
시 언어별 표시가 개념 노드를 오염시킨다(pedagogy·relation을 노드에서 뺀 것과 같은 논리로 분리 필요).

**교정(P2d-a):** `Concept` 모델에서 `name_ko/en/ja` **3필드 제거**. 표시이름은
`data/corpus/concept_graph_v1/locales/{ko,en,ja}.json`(`{canonical_id: name}`)이 단일 진실.
Phase 1은 `ko.json`만 충전(437 전건)·`en/ja`는 `{}`(미저작). 노드는 순수 개념 식별·의미만 보유.
canonical `<slug>`가 name_ko에서 파생되지만 **발급 후 동결** → `name_en` 저작은 `locales/en.json`만
채우고 canonical은 불변(churn 0). 백엔드 표시 조회는 locale 조인으로 재소싱(값 동일·재임베딩 0).

### ③ YAML→GraphDB · Canonical ID Registry (`ids.yaml`)

**현황(위반):** registry **부재**. 추적성이 노드별 `source_id`+`aliases` + git-**미추적** 생성물
`id_map.csv` + 검증 불변식으로 **산재** → 단일 진실 원천 부재(rename/migration을 한 곳에서 추적 못 함).

**갭:** "truth source가 하나가 아님 → 유지보수 지옥"(7대 붕괴 ④)의 정확한 씨앗. 어느 키로 개념을
찾는지가 파편화되면 편집자가 한쪽만 갱신하고 join이 조용히 썩는다.

**교정(P2d-a):** **`data/corpus/concept_graph_v1/ids.yaml`**(git-tracked YAML — 플레이북 명명 그대로)
신설. 각 개념: `canonical_id`·`src_id`·`aliases`([교육과정축 코드, 옛 UC, src_id])·`slug_source`·
`migrations`(P2a `UC→axis`, P2d `axis→canonical` 2 이벤트). **전량 코퍼스(`concepts.jsonl`)에서
결정론 생성**(수기 편집 금지 by construction). `transform-v1`이 `graph.json`·`locales/ko.json`·
`ids.yaml`을 **한 실행에서 co-generate**(단일 원천·드리프트 차단) + `gen-ids` 서브커맨드.

---

## 신규 거버넌스 불변식 (실데이터 error 0)

`data_pipeline.concept_graph.validate` + `tests/data_pipeline/concept_graph/`:

| 불변식 | 심각도 | 무엇을 막나 |
|---|---|---|
| `id_conformance` | error | canonical이 `math.<area>.<slug>` 규약 준수 |
| **`curriculum_independence`** | error | canonical에 학년/트랙 토큰(`\b(elem\|mid\|high\|rt\|oly)\b`)·NCIC 코드조각 부재 — **Part 9 하드게이트 자동화** |
| `id_unique` | error | canonical 충돌 0 |
| `alias_roundtrip`(확장) | error | 재ID 개념은 옛 axis 코드 **AND** 옛 UC **AND** src_id 3중 별칭 보존 |
| **`registry_parity`** | error | `ids.yaml` canonical 집합 == graph concept_id 집합(437 1:1·orphan 0)·필드/이관 정합 |
| **`locale_parity`** | error | `locales/ko.json` 키 == graph concept_id 집합·전건 name_ko 비공백 |

신규 테스트: `test_id_registry_governance.py`(registry⇄graph 패리티·curriculum_independence 가드·
area 학년독립·alias roundtrip 2 이벤트·재생성 멱등·충돌 접미 결정론)·`test_locales_governance.py`
(locale⇄node 패리티·노드 name_\* 슬롯 부재). 개정: `test_validate.py`(437/581 error 0)·
`test_models.py`(`TestConceptPurity` name_\* 삭제·신 regex).

---

## 준수한 프로젝트 불변 제약

- **단일 진실 원천**: `concepts.jsonl`(저작)이 유일 원천 → `graph.json`·`ids.yaml`·`locales/`는 모두
  파생 committed 산출. 세 산출이 `transform-v1` 1회 실행에서 co-generate되고 거버넌스 테스트가
  동결 → `ids.yaml`이 새 dual-truth를 만들지 않는다(구조적으로 수기 편집 금지).
- **발급 후 불변**(§3.5): P2a·P2d 2회 전환은 일괄 breaking이나 추적성 무손실(aliases 3중·ids.yaml
  migrations). 전환 이후 canonical 동결.
- **Phase 1 warning=통과**: dangling 오개념/시각화·고립 노드는 error 아닌 warning(그래프 구축 비차단).

---

## 남은 후속 (별도 슬라이스·flag)

- ~~**`domain` 필드 정화**: `domain="[고]미적분"`은 여전히 교육과정 접두 보유~~ → **완료(P2e·2026-07-03)**:
  `transform._strip_domain_prefix`가 `[고]/[중]/[공통]/[기본]`을 제거해 순수 영역명으로 정화(예
  `[고]미적분`→`미적분`). idmap 경로(concept_id 파생·`[기본]` full-key)와 독립. 거버넌스:
  `test_transform.py::TestDomainPurity`(실데이터 437 domain 접두 0건 잠금).
- **seed 경로**: `seed.build_concept_id`는 NCIC 코드 경로라 name_ko가 없어 의미론 slug 불가 →
  잠정 `math.seed.<code>` 네임스페이스(코퍼스 경로만 P2d 적용). 전문가 저작 시 canonical 발급.
- **name_en/ja 저작**: `locales/en.json`·`ja.json` 충전은 i18n phase 후속(canonical 불변).
- **RT/OLY 트랙**: 재수 유형카드·영재 정리 개통 시 area 어휘·registry migration 재검증.

---

## 메타 질문 (playbook:128 — 7대 붕괴 인지행동 분석)

> *"이 파트의 구조가 실제 서비스에서 실패하는 이유를 … 인지 행동(cognitive action) 기준으로."*

Part 9 위반의 인지행동 근원은 표면 ID 문자열의 미관이 아니라 **"어느 키로 개념을 찾는가"의 파편화**다.

- **교육일관성붕괴(primary·①)**: `{TRACK}`이 학년(교육과정)을 canonical에 밀봉해, 같은 수학 개념이
  학년 재배치·교육과정 개정 때 ID가 흔들린다. `math.geometry.*`는 `[중]기하`·`[고]기하`를 하나로 봐
  이 결합을 끊는다 → 개념 정체성이 교육과정 위에서 안정.
- **유지보수 지옥(③)**: canonical·옛 키·registry가 산재하면 "이 개념의 정본/옛 키가 무엇인가"에 답이
  둘 이상 → 편집자가 한쪽만 갱신·join 부패. 방어 = registry를 `concepts.jsonl`에서 *생성*하고
  `registry_parity`·재생성 동일성 테스트로 두 committed 투영을 한 원천에 동결.
- **AI추론실패·성능병목(①)**: 교육과정-버전을 ID에 박으면 매 개정이 대량 재-ID → alias 폭발·retrieval
  키 churn·임베딩 이동. canonical을 birth-frozen 의미론으로 두고 커리큘럼 매핑을 overlay(CurriculumEntry·
  aliases)에 두면 개정에도 ID·임베딩 불변.
- **교육일관성붕괴(②)**: `locales/`를 지금 강제하되 Phase 1은 `ko`만 채워, 표시이름을 개념 정체성에서
  분리. 노드에 표시문자열을 두면 렌더러/튜터가 정체성과 표시를 한 lookup에서 읽어 i18n 확장 시 오염.
- **관계/순환 무영향**: registry는 traversable edge를 담지 않는 순수 id/alias/migration 사실 → 관계
  표면·N²·순환 리스크 0.

---

## 변경 파일 (P2d 전체)

| 슬라이스 | 파일 | 변경 |
|---|---|---|
| P2d-a | `concept_graph/{models,idmap,transform,validate,__main__,seed}.py` | 신 regex·name_\* 제거·canonical 파생·충돌 접미·불변식·co-generate |
| P2d-a | `concept_graph/hangul_romanize.py`·`registry.py`(신규) | 로마자화·registry 어셈블/YAML |
| P2d-a | `data/corpus/concept_graph_v1/{graph.json,ids.yaml,locales/}` | 437 재ID·registry·locale(신규) |
| P2d-a | `tests/…/test_id_registry_governance.py`·`test_locales_governance.py`(신규)+개정 | 거버넌스 |
| P2d-b | `l1/concept_graph/{node_projection,backend_concept,embedding}.py` | name_ko를 locale 조인 재소싱·docstring |
| P2d-c | `concept.schema.yaml`·`concept_graph.md`·`curriculum_matrix.md`·`textbook_mapping.md`·`01_data_foundation.md`·`MEMORY.md`·본 문서 | 정본·stale 교정·결정 로그 |

*출처: WhyMath 구축 플레이북 v1.0 Part 9. 결정 로그: `MEMORY.md` 2026-07-02 P2d.*
