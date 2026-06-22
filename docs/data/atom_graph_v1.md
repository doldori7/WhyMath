# 와이매스 원자 백본 데이터셋 v1 (자체작성·K-12 3축 + 대학) — 데이터 카드

> **요약**: 기존 개념그래프(437개념·581엣지)를 **원자(atom) 단위로 한 층 더 미세화**한 신규 학습
> 백본. **원자 1,837 · 선수엣지 3,220**(원자ID 2,213 + 서술형 1,007) · 초·중·고 + 대학 4축.
> 성취기준 코드(NCIC)·교수학 4요소(오개념·진단문항·소크라테스·전이)·원자성 메타를 포함하며,
> 기존 백본을 **전면 교체**한다(마이그레이션 로드맵: `ROADMAP.md` 및 결정 로그 참조).
>
> **상태(2026-06-22)**: 통합 코퍼스 마스터 정본화 — graph.json 재생성(미적 원자ID 하이픈 채택·
> 대학 fill 재실행). 코퍼스(`data/corpus/atom_graph_v1/`)는 신규 파이프라인 `data_pipeline/atom_graph/`
> 산출(§6). (직전 상태 2026-06-21: Phase 0 데이터카드 작성.)

---

## 1. 출처·프로비넌스

| 항목 | 값 |
|---|---|
| 형태 | 사용자 업로드 **통합 코퍼스 마스터** xlsx(16 시트) — 파이프라인은 `원자_통합마스터`·`선수엣지_통합` 2시트만 정형화 |
| 업로드일 | **2026-06-22 정본 마스터 채택**(직전 2026-06-21 정비본 대체) |
| 원본 sha256 | `83a0d2883fe8552868916181f04ebe687f24dd9cabb91ec4b3096d59a767d0e0` (1,763,395 bytes) |
| 직전 소스 | `759f163a…`(917,455 bytes, 2026-06-21) — 미적 원자ID raw였음 |
| 저작 | 와이매스 자체작성(교수학 주석·원자화·대학 신규축) + 공공 표준 *코드* 참조(NCIC) |
| 산출 코퍼스(Phase 1) | `data/corpus/atom_graph_v1/graph.json` + `_provenance.json` |

> 원본 xlsx는 **커밋하지 않는다**(§3 redaction 대상 자유텍스트 포함 — NCIC 본문·핵심명제·정식정의).
> 진실 원천은 redaction을 적용한 코퍼스(graph.json)다. 재추출 시 동일 sha256 원본을 사용자에게 재요청한다.

### 표기 정비 이력(전수 검증 완료)
- 비표준 사이시옷 점검: **초기값→초깃값 15곳은 원본에서 수정 완료**. **자리값→자릿값 13 · 경계값→
  경곗값 4(총 17)는 Phase 1 transform 사이시옷 정규화로 흡수**(회색지대 고유값 등은 유지·결정론).
- 코드 정합(정본 마스터 반영): **미적Ⅰ/Ⅱ 원자ID·연결성취기준이 마스터에서 하이픈으로 통일**
  (`12미적Ⅰ-01-01-1`·`[12미적Ⅰ-01-01]`) — 직전 소스는 원자ID raw(`12미적Ⅰ01-01-1`)였으나 공수·기수와
  내부 불일치라 마스터가 교정. transform의 연결성취기준 하이픈 정규화는 이제 무연산(소스 사전정규화,
  provenance `미적하이픈` 토큰 0·`_distinct` 43 유지). **129 원자ID만 하이픈으로 변경**, 노드/엣지/
  redaction 카운트는 직전과 동일. 코퍼스 `standards_v1` 무수정·전 연결성취기준 조인 OK.

---

## 2. 스키마 (시트 → 코퍼스)

### 2.1 원자_통합마스터 (1,837행 · 31열)
순번 · 출처 · 교육과정 · 학교급 · 학년/학년군 · 영역/과목 · **단원** · **소단원** · **소단원코드** ·
**원자ID** · 원자명 · 원자명_표시 · **인지축**(개념/절차/표상) · **노드유형**(선행/구성/결과) ·
**오개념유형**(6종) · **난이도**(1~5) · **연결성취기준** · *핵심명제/성취기준내용* · ①오개념 ·
②진단문항 · ②정답·통과기준 · ②미통과·오답신호 · ③소크라테스질문 · ④전이 · ④전이예시 ·
선수원자 · 원자성a · 원자성b · 원자성c · 원자성d · 비고

### 2.2 선수엣지_통합 (3,220행 · 11열)
출처 · **관계유형**(원본/소단원내/소단원간/학년간/학교급간(추정)/참고[서술형]) · **from(선수)** ·
from_원자명 · from_학교급 · from_유형(원자ID/서술형) · 관계(선수) · **to(후행)** · to_원자명 ·
to_학교급 · 학교급연계

### 2.3 계층 노드화(결정 ⑤)
`단원`·`소단원`·`소단원코드` 컬럼을 **독립 concept 노드로 dedup 승격** — 3단 계층
(개념=단원 / 소개념=소단원 / 원자=세부개념), 기존 `Concept.level` enum + `parent_concept_id` 재사용.
원자.parent=소단원·소단원.parent=단원. 소단원코드 예: `초수연-U1-S1`·`공수1-U1-S1`·대학 `CALC1-U1-S1`.

---

## 3. 라이선스·안전 (CLAUDE.md 우선순위 #2)

자체작성 교수학 주석(4요소·원자성·은유 등)과 공공 표준 *코드*(NCIC 성취기준 코드)는 **안전**
(자체 코퍼스 + 사실정보). 단, 다음 자유텍스트는 NCIC 성취기준 *본문* 을 근접 복제할 수 있어
— 기존 정책(`concept_graph.md` §1.1 "본문은 어느 필드에도 복제하지 않는다") — **코퍼스에서 redact**:

| redact 필드 | 사유 |
|---|---|
| `핵심명제/성취기준내용`(K-12 원자) | NCIC 성취기준 *본문(statement)* 근접/직접 복제. 본문은 `standards_v1` 코퍼스(공공누리 1유형)에만 두고, 원자는 **연결성취기준 코드로 다리**만 놓는다 |

> **대학 원자(513)는 연결성취기준이 '없음'** → 해당 `핵심명제`는 *자체작성*이므로 보존(redact 아님).
> 4요소(①~④)·④전이예시·원자성은 자체/AI 작성 → 보존. redaction 마커는 각 레코드 `_redacted_fields`.

신규 콘텐츠 4종(결정 ⑥ — 은유·정식정의·허용표현·암기카드)은 **개념/소개념 레벨·자체/AI 원창작**으로
Phase 3에서 저작한다. 특히 **정식정의(formal_definition)는 교과서 정의 미복제·자체창작 한정**(기존
코퍼스가 저작권으로 redact했던 필드 — 자체창작에 한해 도입).

`licensing_safety.md`에 "와이매스 원자 백본 데이터셋 v1(자체작성)" 행으로 등록.

---

## 4. 검수 상태 (적재 전 게이트)

안내 시트 자기보고:
- **메타데이터 전 원자 완비**: 난이도(1~5)·오개념유형(6종)·노드유형·4요소.
- **신규 원자(연녹색)와 그 메타는 AI 추정 — 교육 전문 검토 권장**.
- 품질 재점검(2026-06-21): 구조·범주·코드·3축·**DAG 사이클 0** 통과(빈칸=대학 연결성취기준 513·
  '없음' 표기만). 선수원자↔선수엣지 일치화·원자명_표시 중복 해소 완료. 내용 표본 60개 전문 검수:
  정답(수학) 오류 0건·경미 이슈 4건 중 3건 수정·1건 정상확인.

> 본 데이터셋의 다수 메타가 **AI 추정**이므로, 적재 시 `review_status` 표식(자체 검수/AI 검수/검수필요)을
> 부여하고 학생 직접 노출은 검수 게이팅을 거친다(기존 concept_graph 규약 미러).

---

## 5. 통계 (요약 시트)

| 축 | 분포 |
|---|---|
| 학교급 | 초등 382 · 중학 180 · 고등 762 · 대학 513 = **1,837** |
| 인지축 | 개념 803 · 절차 552 · 표상 482 |
| 노드유형 | 구성 1,558 · 결과 152 · 선행 127 |
| 난이도 | 1=44 · 2=175 · 3=413 · 4=603 · 5=602 |
| 선수엣지 | 원자ID 2,213 + 서술형 1,007 = **3,220** |
| 계층 노드(승격) | 단원 **217** · 소단원 **643**(distinct 소단원코드) — 원자 1,837의 부모. 코퍼스 총 노드 **2,697** |

> 안내 시트의 "소단원코드 부여 1,324개"는 *코드를 부여받은 K-12 원자 수*(382+180+762=1,324)를 뜻하며,
> distinct 소단원코드는 **643**(단원 217)이다 — Phase 1 transform 실측.

무결성(읽기 전용 실측): 원자ID 1,837 유일·중복 0 · 원자ID 엣지 dangling 0 · DAG 사이클 0.

---

## 6. 마이그레이션·적재 (Phase 1~5 — 요약)

- **Phase 1**: 신규 파이프라인 `data_pipeline/atom_graph/`(extract→transform→validate→load,
  기존 `concept_graph/` 미러). transform이 계층 노드 승격 + 표기·미적 정규화 + 관계유형→`relation_subtype`
  매핑 + 서술형 엣지 분리를 결정론으로 수행. backend `concept`·`concept_edge` 적재.
- **Phase 2**: 파생 스토어(`concept_node`·pgvector `concept_embedding`·Neo4j) 재생성.
- **Phase 3**: 4요소 정식 소스 승격(오개념 카탈로그·진단문항·소크라테스·전이) + 콘텐츠 4종 신규 저작.
- **Phase 4**: 문제 corpus 크로스워크(소단원/단원 매칭 + 성취기준 코드 2중 다리).
- **Phase 5**: 구 `concept_graph_v1` 폐기·전 계층 검증.

상세 로드맵·결정(locked ①~⑥)은 마이그레이션 플랜 및 `MEMORY.md` 결정 로그 참조.

---

## 7. Neo4j 적재 스키마 (Phase 2c — `atom_graph/load.py`)

`graph.json`을 Neo4j에 **멱등 MERGE** 적재한다(`concept_graph/load.py` 미러 — 지연 import·
`NEO4J_*` env 접속·드라이버 주입·reltype enum allowlist). **additive 원칙**: 구 437 개념 그래프
(`:Concept`/`concept_id`/`:PREREQUISITE`)와 *노드·엣지 라벨 모두 충돌하지 않게* 별도 스키마를
쓴다(Phase 5 구 폐기 전까지 병존).

| 요소 | 구 개념 그래프 | 원자 백본(신·Phase 2c) |
|---|---|---|
| 노드 라벨 | `:Concept` | **`:Atom`** |
| MERGE 키 | `concept_id` | **`code`** (원자ID/소단원코드/단원코드) |
| 제약 | `concept_id_unique` | **`atom_code_unique`** (`REQUIRE a.code IS UNIQUE`) |
| 인덱스 | `concept_domain`·`concept_name_ko` | **`atom_school_level`**(a.school_level)·**`atom_level`**(a.level) |
| 관계 타입 | `:PREREQUISITE` | **`:ATOM_PREREQUISITE`** (reltype 토큰까지 완전 분리) |

### DDL·MERGE (멱등)
```cypher
CREATE CONSTRAINT atom_code_unique IF NOT EXISTS FOR (a:Atom) REQUIRE a.code IS UNIQUE;
CREATE INDEX atom_school_level IF NOT EXISTS FOR (a:Atom) ON (a.school_level);
CREATE INDEX atom_level IF NOT EXISTS FOR (a:Atom) ON (a.level);
MERGE (a:Atom {code: $code}) SET a += $props;            -- 노드 전량(원자+단원+소단원)
MATCH (src:Atom {code: $src}) MATCH (dst:Atom {code: $dst})
MERGE (src)-[r:ATOM_PREREQUISITE]->(dst) SET r += $props; -- 선수 엣지
```

### 적재 규칙
- **노드 2,697**(원자 1,837·단원 217·소단원 643)·**엣지 2,213**(원자ID prerequisite 전량)·skip 0.
- 엣지 속성: `relation_subtype`(원본/소단원내/소단원간/학년간/학교급간(추정))·`school_link`·
  `strength`·`evidence`·`from_name`·`to_name`. `from_code`/`to_code`/`relation`은 MATCH/reltype에 쓰고
  속성으론 넣지 않는다.
- `atomicity`(a~d dict)는 **Neo4j map 속성 불가** → 결정론 JSON 문자열로 직렬화(구조 진실 원천은
  graph.json·Postgres `atom_node`). `None`·빈 dict 속성은 생략(Neo4j null 미저장).
- `parent_code`(3단 계층)는 **노드 속성**으로만 보존 — 별도 계층 관계는 만들지 않는다(Phase 3+).
  `narrative_edges_raw`(서술형 1,007)는 FK 불가라 **적재 대상 아님**(패스스루 보존).
- **redaction 불변**: AtomConcept에 K-12 핵심명제 본문 슬롯이 없어 dump에 미포함 → 구조적 차단.
  접속 자격은 `NEO4J_URI`·`NEO4J_USER`·`NEO4J_PASSWORD` env 전용(시크릿 하드코딩 금지).

### CLI·검증
```bash
python -m data_pipeline.atom_graph load --graph data/corpus/atom_graph_v1/graph.json
```
단위(Fake 드라이버·실 코퍼스 2,697/2,213/skip 0)·통합(`@integration`·`neo4j` importorskip·실
neo4j:5에서 멱등 재적재 불변·code 집합 격리 정리). CI 전용 `data-pipeline-neo4j` 잡이 실 적재 검증.
