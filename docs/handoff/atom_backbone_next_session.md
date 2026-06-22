# 원자 백본 마이그레이션 — 다음 세션 인계 (Phase 2c ~ 5)

> **목적**: 이 세션에서 Phase 0·1·2a·**대학 U1~U4**·**통합 마스터 정본화(R1)**·**K-12 콘텐츠 캡처(R2)**·
> **Phase 2b 원자 임베딩(R3)**을 완료·푸시했다. 다음 세션이 *재유도 없이* 이어가도록 상태·환경·규율·
> 다음 단계를 못 박는다. **진실 원천은 `MEMORY.md`의 "원자 백본 전면 교체" 결정 로그**다.

---

## 1. 현재 상태 (2026-06-22)

- **브랜치**: `claude/admiring-faraday-ouvlfx` (PR 미생성 · 전부 커밋·푸시됨)
- ✅ **Phase 0** — 데이터카드 `docs/data/atom_graph_v1.md` + `licensing_safety.md` 등록
- ✅ **Phase 1 (data-pipeline)** — `data_pipeline/atom_graph/`(extract→transform→validate→CLI) + 커밋된 코퍼스 `data/corpus/atom_graph_v1/graph.json`(노드 2,697 = 원자 1,837·단원 217·소단원 643 / 엣지 2,213 / 서술형 raw 1,007 / 대학 513)
- ✅ **Phase 1 (backend)** — `l1/atom_graph/atom_backend_{concept,edge}.py`·`populate.py` → `concept`/`concept_edge` 적재 + 마이그레이션 `d5e6f7a8b9c0`(concept_edge.relation_subtype)
- ✅ **Phase 2a** — `atom_node` 메타 프로젝션(`db/models/atom_node.py`·`l1/atom_graph/atom_node_projection.py`·마이그레이션 `e6f7a8b9c0d1`)
- ✅ **대학 통합 U1~U4 완료** (2026-06-22, 사용자가 통합마스터 xlsx 업로드 → "대학만 지금 통합" 결정·플랜 `synchronous-crafting-squid`):
  - **U1** (`d5fdcd8`) `data_pipeline/standards_university/` → `data/corpus/standards_university_v1/`(대학 성취기준 409·링크 409·자체작성·redaction 불요)
  - **U2** (`2f40184`) `data_pipeline/atom_graph/university_standard_fill.py` → graph.json 대학 원자 513 `standard_codes` 채움(소단원→성취기준 1:1·멱등·K-12 무변경)
  - **U3** (`0e4343b`) 대학 성취기준 backend 적재 검증(기존 범용 `standard_loader` 재사용·신규 코드 0·단위 hermetic+통합 gated). **주의**: atom concept `source_id` 미설정 → concept_standard_link 해석은 orphan skip(atom↔성취기준은 `atom.standard_codes`가 담당)
  - **U4** (`39846a6`) `data_pipeline/concept_content_university/` → `data/corpus/concept_content_university_v1/`(대학 소단원 409 콘텐츠 4종+암기카드 409·자체작성·검수필요·**정식정의 학생비노출**·휘발 xlsx 보존). **DB 투영은 Phase 3**
- ✅ **통합 마스터 정본화 + R1~R3 완료** (2026-06-22, 플랜 `encapsulated-zooming-chipmunk` · 사용자가 16시트 통합 마스터 xlsx[sha `83a0d288…`]를 업로드 → "마스터 정본화 → 재생성 후 2b" 결정):
  - **R1** (`8dfe1ad`) 원자 백본 재생성 — 미적 원자ID **129개 raw→하이픈** 채택(파이프라인 재실행만·코드 변경 0·transform이 원자ID 그대로 적재)·`university_standard_fill` 재실행(대학 513)·graph.json diff **100% 미적**·K-12 핵심명제 0누수. 정본 sha `83a0d288…`
  - **R2** (`ca2dd2e`) `data_pipeline/concept_content/` → `data/corpus/concept_content_v1/`(K-12 개념 437 콘텐츠 4종 + 암기카드 113 · U4 미러 · **K-12 성취기준 본문 미수록=redaction**·연결성취기준 코드만 다리·정식정의 학생 비노출)
  - **R3 (=Phase 2b)** (`5ca3bec`) 원자 임베딩 `atom_embedding`(PK=code·vector(1024)·입력=**name+transfer만**·`level=="세부개념"` 1,837·원문 비저장)·마이그레이션 `f7a8b9c0d1e2`
- **alembic head(현재)**: `f7a8b9c0d1e2` (down `e6f7a8b9c0d1` — atom_embedding pgvector. U1~U4·R1·R2는 마이그레이션 무관)
- **다음 작업**: **Phase 2c**(Neo4j 원자 그래프 재적재) — §5.2. 새 세션 권장(컨텍스트 위생).

## 2. locked 결정 (요약 — 상세는 MEMORY.md)
① 전면 교체·원자화 ② 크로스워크=문제 corpus만 ③ 4요소→정식 소스 승격 ④ 대학 513 포함+2015·2022 병행
⑤ 개념·소개념도 노드화(단원/소단원/원자 3단 계층) ⑥ 콘텐츠 4종(은유·정식정의·허용표현·암기카드)=
개념/소개념 레벨·**자체/AI 원창작**(정식정의도 원창작).
- **정규화(파이프라인 transform)**: 미적Ⅰ/Ⅱ 43코드 하이픈 추가(NCIC 일치)·사이시옷(자리값/경계값→표준형).
- **redaction**: K-12 핵심명제(NCIC 본문) 미적재(연결성취기준 코드로 다리)·대학 핵심명제는 자체작성 보존.
- **설계 정련**: backend `concept`=런타임 최소 식별만, 풍부 메타는 `atom_node` 투영(억지 enum 회피).

## 3. ⚠️ 환경 재구성 (새 컨테이너에선 필수 — /tmp·업로드는 휘발)
- **시스템 `python3`=3.11(부적합)** → 반드시 `/usr/bin/python3.12` 사용.
- backend venv:
  ```bash
  /usr/bin/python3.12 -m venv /tmp/bevenv
  cd src/backend && /tmp/bevenv/bin/pip install -e '.[dev]'
  ```
- data-pipeline venv:
  ```bash
  /usr/bin/python3.12 -m venv /tmp/wmvenv
  cd src/data-pipeline && /tmp/wmvenv/bin/pip install -e '.[dev,xlsx]'   # xlsx=openpyxl(코퍼스 재생성/캡처 시)
  ```
- **원자 소스 xlsx(통합 마스터)·대학 참조 CSV는 휘발**. 정본 마스터(sha `83a0d288…`)는 R1/R2로 *redacted 코퍼스*(`atom_graph_v1`·`concept_content_v1`)에 이미 캡처·커밋됨. **Phase 2c~5는 *커밋된 코퍼스*로 작업**하므로 xlsx 불요. (xlsx 재추출이 필요하면 사용자에게 재요청 — 원본은 NCIC 본문 포함이라 repo 미커밋.)

## 4. ⚠️ 검증 규율 (이번 세션에서 버그 2건·위임 실패 1건을 이렇게 잡았다)
- **서브에이전트 보고를 그대로 믿지 말 것** — 메인이 *ground truth*(실 게이트·실 코퍼스)로 재검증.
  (실제로 data-engineer "전수 정규화" 오보·backend-engineer "구현 대신 narration" 실패를 적발·교정.)
- **pytest는 *전체 스위트*로 실행** — 부분집합은 기존 `concept_graph` 순환 import로 collection 에러가 난다(아티팩트·실패 아님). 게이트: `cd src/backend && /tmp/bevenv/bin/pytest --cov=whymath_backend -q -m "not integration"`.
- **위임 시 명시**: "*파일을 직접 생성*하고 끝에 `git status --short`로 증명하라. 서브에이전트 spawn·리서치만 금지."
- mypy의 neo4j 충돌은 *wmvenv에 neo4j 설치 시*만 발생(CI는 `.[dev]`만 → green).

## 5. 다음 작업 순서 (각 슬라이스 4게이트+커밋, 미러 대상 명시)
1. ✅ **Phase 2b — 원자 임베딩(pgvector)** (`5ca3bec`·완료) — 신규 `atom_embedding`(PK=code·vector(1024))·`l1/atom_graph/embedding.py`(입력=**name+transfer만**·`level=="세부개념"` 1,837·ON CONFLICT(code)·원문 비저장). hermetic 26 + 통합 gated. 마이그레이션 `f7a8b9c0d1e2`.
2. **Phase 2c — Neo4j 원자 그래프 재적재**(MERGE 멱등) ← **다음**. **미러**: `data_pipeline/concept_graph/load.py`(NEO4J_* env·`.[neo4j]` extra).
3. **Phase 3 — 4요소 승격 + 콘텐츠 4종 저작**: ①오개념→`misconception_catalog`·②진단문항→`problem`(+`problem_concept`·`distractor_map`)·③소크라테스→`problem_step.socratic_prompt`·④전이=이미 atom_node. 콘텐츠 4종(은유/정식정의[자체창작]/허용표현/암기카드)=개념/소개념 레벨·AI 생성+검수.
4. **Phase 4 — 문제 크로스워크**: 기존 문제의 *소단원/단원 매칭* + *성취기준 코드* 2중 다리로 `problem_concept`를 원자 code로 재연결(교차검증·검수 큐).
5. **Phase 5 — 정리**: 구 `concept_graph_v1` 코퍼스·구 437 concept 폐기, 전 계층 통합테스트, `MEMORY.md`·`ROADMAP.md` 갱신.

## 6. ✅ 대학 성취기준 파일 (2026-06-22 수신·U1~U4 완료 — 아래는 원래 계획·이력)

> **해결됨**: 사용자가 업로드한 파일은 §6 예상(대학 성취기준만)보다 넓은 *개념-레벨 통합마스터*
> (구 437개념 + 대학 409소단원·콘텐츠4종)였다. 대학 코드 100% 원자DB 조인 확인 후 "대학만 지금
> 통합"(K-12 콘텐츠는 Phase 3 437→원자 크로스워크로 분리). U1(standards 코퍼스)·U2(원자 연결성취기준
> 채움)·U3(적재 검증)·U4(콘텐츠 캡처) 완료. 상세는 §1·MEMORY.md.
- 파일: **`2022-2015개정_수학_성취기준_통합마스터.xlsx`**(대학 추가본).
- **대학 단원/소단원은 이미 원자 DB에 존재**(코드까지: `CALC1-U1`·`CALC1-U1-S1` 등·32과목·단원 148·소단원 409). 사용자에게 *그 코드 재사용* 안내함(참조 CSV 전달 완료).
- **진짜 빠진 건 대학 *성취기준***(대학 513 원자 `standard_codes` 전부 빈값).
- 받으면: ① standards 코퍼스에 **대학 성취기준 확장**(NCIC 아님 = **자체작성**으로 `licensing_safety.md` 분류·redaction 불요) ② 대학 513 원자 `연결성취기준` 채움(transform 재생성 또는 후처리) ③ 코드 정합 검증(미적 하이픈 사태 방지).

## 7. 핵심 경로
- 코퍼스: `data/corpus/atom_graph_v1/{graph.json,_provenance.json}` · 콘텐츠 `data/corpus/concept_content_v1/`(K-12)·`concept_content_university_v1/`(대학)
- 파이프라인: `src/data-pipeline/data_pipeline/atom_graph/` · `concept_content/`(K-12 콘텐츠)
- backend 적재: `src/backend/whymath_backend/l1/atom_graph/`(concept·edge·atom_node·**embedding**)
- 데이터카드: `docs/data/atom_graph_v1.md` · 라이선스: `docs/data/licensing_safety.md`
- 결정 로그(진실 원천): `MEMORY.md` "원자 백본 전면 교체 마이그레이션 착수"
