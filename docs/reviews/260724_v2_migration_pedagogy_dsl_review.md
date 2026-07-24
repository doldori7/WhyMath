# v2 마이그레이션 · 교수법 DSL 설계 — 적용사항 검토서

> **대상**: 업로드된 2종 — `260724_phase0_v2_migration_pedagogy_dsl.sql`(원시 SQL 마이그레이션) + `…v2_DSL….docx`(교수법 방법론 검토 문서 v2)
> **기준**: 이 마이그레이션을 **지금 코드베이스에 적용해도 되는가** — 결함·중복·거버넌스·컴플라이언스를 실측으로 판정
> **작성일**: 2026-07-24
> **근거**: 세 갈래 코드베이스 실측(마이그레이션 인프라 · L4 교수법 엔진 · backlog/아키텍처). 모든 주장에 파일 경로·라인 병기. 부록 A 색인.
> **후속 산출물**: 수정 Alembic 리비전 초안 `260724_v2_migration_pedagogy_dsl.alembic_draft.py`(같은 디렉터리 · **미적용**).

---

## 0. 판정 요약

**설계(문서)는 견고하다. 그러나 마이그레이션(SQL)은 현 상태로 적용하면 안 된다.** 세 층위의 문제:

- 🔴 **컴플라이언스**: `evidence_event.payload`(학생 원문 발화)를 **평문 저장** → CLAUDE.md NEVER("미성년자 채팅 데이터 평문 저장 금지") 위반. `license_tier TEXT`가 기존 저작권 안전장치를 **우회**.
- 🟠 **정합성/중복**: `content_material`의 provenance 컬럼이 **이미 구축된 `content_provenance`+`generation_log`와 중복**. `license_tier 'T1'..'T4'`는 **어디에도 정의되지 않은 새 라벨셋**. `evidence_event`는 기존 `attempt_event` 하이퍼테이블과 개념 중복.
- 🟡 **형식/거버넌스**: 저장소는 **Alembic 전용**인데 원시 `.sql`. 이 작업을 승인하는 **backlog 태스크·MEMORY 결정 없음**. "Phase 0 v2 마이그레이션"은 저장소 어디에도 없는 표현이며, 실제 스테이지는 **S3(파일럿)**.

**권고: 지금 적용하지 말 것.** 거버넌스 등재(backlog + MEMORY) 선행 → Blocking 해소 → 기존 시스템과 정합 재설계 → Alembic화 후 파일럿 스코프로 최소 적용.

---

## 1. 실측 사실 — 설계 전제 vs 코드베이스

| 설계/마이그레이션의 전제 | 코드베이스 실측 | 근거 |
|---|---|---|
| 원시 `.sql` 마이그레이션 | 저장소는 **Alembic 전용**(리비전 63개). 원시 `.sql` 0개. 하이퍼테이블·enum은 리비전 내 `op.execute()`로 이미 처리 | `src/backend/alembic/versions/` · `alembic.ini` |
| `core-engine/`·`subject-math/` 모노레포 | **존재하지 않음.** 백엔드는 단일 패키지 `whymath_backend/l1..l6`. 팩 로더·프롬프트 조립기·guard·evidence evaluator·DSL·컴파일러 **전부 그린필드** | `src/backend/whymath_backend/l4/` |
| `content_material`(생성 이력·라이선스) | **`content_provenance`+`generation_log` 이미 존재**. `concept_content`(K-12 437 + 대학 409) 콘텐츠 좌석도 존재 | `db/models/provenance.py` · `schemas/v1.0/schema_v1.0.md §10.1` · `db/models/concept_content.py` |
| `license_tier TEXT 'T1'..'T4'` | T1-T4 스킴 **미정의**. 실제 축은 ① Tier 0-3(수집 전략) ② A+…E 등급 ③ `LicenseType` enum. 셋 다 T1-T4 아님 | `docs/legal/copyright_guide_v2.md §6.3` · `docs/data/licensing_safety.md` · `schema/enums.py:443` |
| `evidence_event` 하이퍼테이블 | **`attempt_event` 하이퍼테이블 + `evidence_links` 이미 존재** — 개념 중복. 하이퍼테이블 5종 운용 중 | `alembic/…_timeseries_.py:415-431` · `db/models/evidence_link.py` |
| `knowledge_type` ENUM(7종) | 겹치는 분류 enum 이미 3개 → **4번째 인지 택소노미**. house style은 status/type을 plain `sa.Text`로 둠(하드 ENUM과 상충) | `data-pipeline/…/atom_graph/models.py:55` · `schema/enums.py:594,616` · `db/models/concept_content.py:29` |
| `concept_nodes` "545 그래프 노드" | 545는 **stale 목표치**. 실측: 개념그래프 **437(legacy_snapshot 봉인)** vs 원자백본 **2,697(런타임 단일 진실)**. 코드 네임스페이스 다중 | `data/corpus/*/graph.json` · `docs/architecture/04a_wh1_tutoring_harness.md:558` · `system_deep_dive.md:157` |
| 오개념 top-3 = "ChromaDB" | ChromaDB는 **stale**(2026-06-10 슬98로 pgvector 대체). 실검색은 pgvector 구현 완료 | `l4/misconception/combined.py` · `…/semantic/pgvector_index.py` |
| BKT·출구 게이트 P≥0.95 | BKT 성숙. 그러나 **P≥0.95 출구 게이트 없음**·generic evidence-event 인입 없음 | `l2/bkt.py` · `l2/mastery_tracking.py` |
| 프로젝트 = "Phase 0" | **S1 종료 게이트 2026-07-16 PASS · S2 완료 · 현재 S3(파일럿)**. "Phase 0 v2"는 저장소에 없음 | `backlog/tasks/S1-14…` · `docs/strategy/status_roadmap_2026-07.md` |

---

## 2. 검토 지적 — 심각도별

### 🔴 Blocking (적용 전 반드시 해소)

**B1. 미성년자 원문 발화 평문 저장 (CLAUDE.md NEVER 위반).**
`evidence_event.payload JSONB`가 주석상 "원문 발화·문항 ID"를 담는다. 이는 미성년 학생의 대화 데이터인데 암호화 경로가 DDL에 전무하다. CLAUDE.md 금기 "미성년자 채팅 데이터를 평문으로 저장 금지"·원칙 "학생 데이터는 민감 정보로 분류 — 암호화 저장" 위반.
- 기존 인프라 재사용 가능: 봉투 암호화(AES-256-GCM) `dialogue_turn.content_encrypted`/`content_nonce`(`db/models/dialogue.py:167-175`) + `privacy/retention.py` 파기.
- **정확히 같은 유형의 열린 태스크가 SEC-01**(dialogue `image_uri`·`image_analysis` 평문 갭). 이 마이그레이션은 같은 결함을 신규 테이블에 재도입한다.
- **수정**: `payload` → `payload_encrypted`/`payload_nonce`(LargeBinary) + `retention_until`. 비민감 메타(문항 ID 등)만 평문 컬럼으로 분리.

**B2. 저작권 안전장치 우회.**
`license_tier TEXT DEFAULT 'T1'`는 기존 `content_provenance.license`(`LicenseType` enum + `ORIGINAL/EBS_LICENSED 차단` validator, `db/models/provenance.py:19-22,48-50`)를 **거치지 않는다**. 콘텐츠 provenance를 저작권 불변식 없는 자유 텍스트 컬럼으로 라우팅하면 4-Tier IP 오염 방지의 취지에 역행한다(CLAUDE.md 우선순위 #2 법적 준수).
- **수정**: `license_tier` 폐기 → provenance는 `content_provenance`(FK)에 위임, license 축은 기존 `LicenseType`/Tier 0-3 재사용.

**B3. 거버넌스 미승인.**
이 스키마를 승인하는 backlog 태스크도, MEMORY 결정 로그도 없다(`backlog/tasks/` 키워드 스윕 0건, `MEMORY.md` 0건). CLAUDE.md "기술 스택/스키마 변경은 MEMORY 결정 로그 필수"·"작업일정 정본은 `backlog/`". 미승인·미등재 상태로 63개 리비전 체인에 스키마를 못박으면 안 된다.
- **수정**: backlog 태스크(예 `PED-01`) + MEMORY 결정 로그 등재 후 진행. *YAML 등재는 Kiki 본인 기입*(거부 우회 금지 규칙).

### 🟠 High (설계 정합 — 적용 전 재설계)

**H1. `content_material` ↔ 기존 provenance/콘텐츠 시스템 중복.**
`generated_by`·`prompt_version`·`source_refs`·`license_tier`는 `content_provenance`(원본출처·생성유형·변형·라이선스)+`generation_log`(모델명·프롬프트템플릿·토큰·cost_usd)와 겹친다. 콘텐츠 본문 좌석은 `concept_content`가 이미 존재. 신규 테이블은 **truth source 다중화**(붕괴연쇄 4 "유지보수 지옥")를 부른다.
- **수정**: 슬롯 테이블(`pedagogy_content_slot`)은 provenance를 **소유하지 말고** `content_provenance` FK로 위임. 본문은 CLAUDE.md L55대로 **렌더러-중립 LaTeX + 구조 태그**(완전 AST 아님).

**H2. `concept_nodes` 네임스페이스 미결 + ARCH-13 얽힘.**
"545 노드"는 봉인된 legacy 개념그래프(437)를 가리킨다. 런타임 진실은 `atom_node`(2,697). 게다가 코드 스페이스가 다중(`math.<area>.<slug>` · `N1/A1` · 원자코드 · `M0425`)이라 `concept_nodes TEXT[]`가 어느 축인지 미명시.
- **ARCH-13**("개념 그래프↔원자 백본 입도 통합 — 이중 진실 원천 해소", *"설계 선행 필요"*)이 풀리기 전에 이 참조를 DB에 못박으면 이중 진실 원천을 **고착**시킨다.
- **수정**: 참조를 런타임 진실 `atom_node`로 주석 고정하되 ARCH-13 결론 대기 표식. legacy 437/545를 못박지 않음.

**H3. 원시 `.sql` → Alembic 리비전 + 계층 분리.**
현재 형식은 Alembic 체인 밖이라 head 관리·up/down·CI 검증에서 이탈한다. 또 L3(content 파이프라인)과 L2(evidence 학습자 데이터)를 한 마이그레이션에 섞어 CLAUDE.md 계층 경계(역방향 의존 금지)를 넘는다.
- **수정**: Alembic 리비전화(`op.execute`로 enum·하이퍼테이블·뷰). L2/L3는 **별도 리비전 2건**으로 분리 권고.

### 🟡 Medium (SQL·모델링 품질)

**M1. `unit_spec.status DEFAULT 'ACTIVE'` = fail-open.**
설계 취지는 게이트 통과 전 차단(`v_unit_release_gate` → BLOCKED)인데 기본값이 즉시 노출(ACTIVE)이다. 컴파일러가 BLOCKED로 뒤집기 전 창에서 미검증 소단원이 런타임 노출될 수 있다. → 기본을 `'DRAFT'`(신설)로, 게이트 통과 시에만 `'ACTIVE'`.

**M2. `v_manifest_fill` division-by-zero.**
`round(... / need.required_cnt * 100, 1)`에 `nullif` 없음. 반면 `v_prescreen_calibration`은 올바르게 `nullif(count(...),0)` 사용. `required_cnt=0` 슬롯에서 에러. → `nullif(need.required_cnt,0)`.

**M3. 멱등성 없음.** `CREATE TYPE`/`CREATE TABLE`에 방어 없음 — 재실행·부분적용 시 실패. (Alembic화 시 자연 해소)

**M4. 하드 ENUM vs house style.** `knowledge_type` ENUM·`status` CHECK는 관행(plain `sa.Text` + 게이팅 리터럴, `concept_content:29`·`atom_node`)과 상충. `knowledge_type`는 "커널 소유·과목 불변"이라 ENUM이 방어 가능하나, **결정 근거를 MEMORY에 남겨야** 한다(관행 예외).

### 🟢 Low (문서 staleness — 코드 아닌 서사)

**L1.** 설계 문서 서사의 "ChromaDB"·"545 노드"·"400 오개념"·`core-engine`/`subject-math` 경로는 stale. **마이그레이션 SQL 자체는 ChromaDB 미참조**(양호). 구현 시 코드는 `l3`/`l4`·기존 pgvector 경로로.
**L2.** `learning_objective.statement`가 교과서 유래 학습목표면 저작권 게이트 대상(기존 `learning_objective_text`는 "법률 검토 전 null" 필드). 성취기준(NCIC 공공누리) 유래 자체 분해임을 확인·표기 필요.

### ✅ 설계의 강점 (유지)

유형→팩→증거 도출 원칙 · `forbidden_modes` 런타임 가드(Kapur·Sweller를 제약으로 못박음) · 팩=데이터/평가기=코드 분리 · 유형별 상이한 달성 증거("정답≠달성") · 6장 자기부정(5개 간극 정직한 진단) — 학습과학·SW공학 양면 견고. `slot_type`을 TEXT로 둔 것(팩이 정의)은 house style과 일치. **뼈대는 신뢰할 만하다.**

---

## 3. 권고 적용 경로

1. **지금 적용하지 않는다.** 이 검토서를 근거로 결정.
2. **거버넌스 선행**: backlog 태스크(`PED-01-pedagogy-pack-dsl-foundation`, stage S4·track content/infra) + MEMORY 결정 로그(7유형 택소노미 채택·`content_material`→provenance 위임·license 축·ENUM 예외 근거). *YAML/MEMORY 등재는 Kiki 기입*.
3. **Blocking 3건 해소**: evidence payload 봉투 암호화(SEC-01 패턴) · license 축을 `LicenseType`/Tier 0-3로 통일 · MEMORY 결정.
4. **High 3건 정합**: 슬롯 테이블을 provenance FK 위임형으로 · `concept_nodes`를 atom_node로 고정(ARCH-13 대기) · Alembic화 + L2/L3 리비전 분리.
5. **파일럿 스코프 존중(S3)**: 문서의 "이차함수 1개 → E2E 1회 완주 후 동결" 원칙대로 스키마를 넓게 깔지 말고 최소로.

## 4. 후속 등재 권고 (Kiki 기입)

```text
# backlog 태스크 초안 (scripts/harness/backlog.py로 Kiki 등재)
id: PED-01-pedagogy-pack-dsl-foundation
track: content        # 또는 infra-debt
stage: S4
priority: 5
title: 교수법 팩 + 소단원 DSL 스키마 기반 (7유형→팩→증거)
notes: |
  260724 v2 마이그레이션 검토서(docs/reviews/260724_v2_migration_pedagogy_dsl_review.md) 반영.
  Blocking: evidence payload 암호화, license_tier 폐기(content_provenance 위임), MEMORY 결정.
  High: content_material→provenance FK, concept_nodes atom_node 고정(ARCH-13 대기), Alembic화.
  파일럿 스코프(이차함수 1개 E2E) 동결 규칙 준수.
depends_on: [ARCH-13]   # concept↔atom 입도 통합 결론 대기(연성 의존)
```

```text
# MEMORY 결정 로그 초안
2026-07-24 교수법 팩+DSL v2 스키마 검토 — 미승인 원시 SQL 반려, PED-01로 등재.
  결정 필요: (1) knowledge_type 7유형 ENUM 채택 여부(기존 CognitiveType/BehaviorArea와 관계)
  (2) content_material vs content_provenance/concept_content 정합 방침
  (3) license 축 통일(LicenseType/Tier 0-3, T1-T4 폐기)
  (4) evidence_event vs attempt_event 재사용 여부.
```

---

## 부록 A. 근거 색인 (실측 파일)

- **A-1 Alembic 전용·하이퍼테이블 가드**: `src/backend/alembic/versions/20260529_0224_bb30b816083d_…_timeseries_.py:415-431`(timescaledb 확장 가드 `create_hypertable`), head=`20260708_1300_c4d5e6f0a1b2_strategy_node_projection.py`.
- **A-2 provenance 중복**: `src/backend/whymath_backend/db/models/provenance.py`(`content_provenance`·`generation_log`), DDL `schemas/v1.0/schema_v1.0.md §10.1(L959-978)`. license enforcement = `schema/provenance.py` validator.
- **A-3 license 축**: `schema/enums.py:443`(`LicenseType`), `docs/legal/copyright_guide_v2.md §6.3`(Tier 0-3), `docs/data/licensing_safety.md`(A+…E 등급).
- **A-4 암호화 선례**: `db/models/dialogue.py:167-175`(봉투 암호화), `whymath_backend/privacy/retention.py`. 열린 갭 = `backlog/tasks/SEC-01-dialogue-image-encryption.yaml`.
- **A-5 노드/오개념 실측**: `data/corpus/concept_graph_v1/graph.json`(437/581·legacy_snapshot), `data/corpus/atom_graph_v1/graph.json`(2,697·런타임), `docs/architecture/system_deep_dive.md:157`.
- **A-6 ARCH-13**: `backlog/tasks/ARCH-13-concept-atom-granularity-merge.yaml`(`l2/prerequisite_recommendation.py:74-75` 문자열 code 조인 = 이중 진실 접점).
- **A-7 L4 그린필드**: `l4/polya/prompts.py`(정적 `_BASE_SYSTEM` 상수·조립 없음), `l4/polya/engine.py`(상태머신), 팩/DSL/컴파일러 부재.
- **A-8 스테이지**: `docs/strategy/status_roadmap_2026-07.md §3`(S0-S5), `backlog/tasks/S1-14-exit-gate-judgement.yaml`(done·2026-07-16 사인오프).

*— 검토서 끝 —*
