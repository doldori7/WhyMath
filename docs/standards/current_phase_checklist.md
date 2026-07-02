# 현단계 완수 체크리스트 — Phase 1(MVP) 진행 중 + 다과목 확장 준비

> **현단계 정의**: 저장소 ROADMAP.md 기준 **Phase 1(MVP) 진행 중**, 여기에 다과목 확장 로드맵의 P0(공통 기반화)에 해당하는 **확장 준비 작업**이 겹친 상태.
> **정본 관계**: Phase 게이트 수치의 정본은 `ROADMAP.md`(본 문서는 대조표). 확장 준비의 설계 정본은 `docs/architecture/subject_expansion_readiness.md`·검토 근거는 `docs/strategy/subject_expansion_roadmap_review.md`.
> **완료 판정 공통 게이트**(모든 코드 항목): pytest 전체 green(현행 ~4,600건) · ruff · black(ll=100) · mypy --strict · import-linter 계약 유지 · 커버리지 70%+.
> **상설 항목**: 각 Phase/트랙 착수 전 평가원·교육부 최신 공고 확인(2028 수능 개편 세부 변동 감시).

---

## A부 — 확장 준비 완수 조건 (브랜치 `claude/subject-expansion-architecture-m2db9s` · 슬라이스 S0~S3)

다과목 확장 로드맵 P0의 저장소 측 실체. 각 슬라이스는 자족 PR + 공통 게이트 green이 완료 판정.

### S0 — 설계 문서
- [x] `docs/architecture/subject_expansion_readiness.md` 작성: 수학 종속 9지점 전수 목록(계층별·{하드/soft/이미 중립} 3등급·파일:줄) · 조정 원칙(값싼 seam 3조건 판별식) · 로드맵 · ID/성취기준/오개념 네임스페이스 설계 · cross-subject 엣지 원칙 · 보류 항목 대장(각 항목 **착수 트리거** 명시)
- [x] MEMORY.md 결정 로그 추가(Overlay subject 축·수학 ID 불변·SymPy 단일 유지·Subject enum 수학 한정 존치·보류 4종 트리거)
- 완료 판정: 문서 내 인용 rev·경로 실재, 기존 문서(04a §8.1·math_dsl_risk_register Q5) 상호참조 정합

### S1 — CurriculumEntry `subject` 축 (유일한 마이그레이션 슬라이스)
- [x] `schemas/v1.1/curriculum_entry.schema.yaml`: `subject` 필드(required·default '수학'·**교과** 레벨 — NCIC `AchievementStandard.subject`(**과목** 레벨)와 granularity 구분 주석) · `composite_key` 3-튜플 · field_count 31
- [x] `schema/curriculum_entry.py`: `subject: str = Field(default="수학", min_length=1, ...)`
- [x] `db/models/curriculum_entry.py`: 컬럼(server_default '수학') + `UniqueConstraint(concept_id, country_code, subject)`
- [x] Alembic 마이그레이션(down_revision=`f3a4b5c6d7e8`): ADD COLUMN → 기존 UNIQUE drop → 3-튜플 UNIQUE. downgrade 대칭·왕복 검증
- [x] `l1/curriculum/curriculum_loader.py`: `_KR_SUBJECT` 상수·entry_id 규약(수학 셀 `{concept_id}:KR` 불변, 비수학만 `:{subject}` 접미) docstring
- [x] 테스트: 기본값·공백 거부·직렬화 / **같은 (concept_id, KR)에 '수학'+'물리' 두 행 공존 허용 + 동일 3-튜플 중복 거부** / KR 적재 셀 전부 '수학'·재적재 멱등
- 완료 판정: 공통 게이트 + alembic upgrade/downgrade 왕복 green

### S2 — NCIC 출처 표기 파라미터화 + 과학 코드 수용성 동결
- [x] 신규 `data_pipeline/citation.py`: `build_ncic_citation_core(subject_label="수학과")` — 고시 제2022-33호 공유·별책만 상이(별책 8 수학/별책 9 과학)
- [x] `ncic/models.py`·`concept_graph/models.py`·`atom_graph/models.py`의 `SOURCE_CITATION`을 빌더 합성으로 재작성 — **값 바이트 동일**(기존 golden/직렬화 테스트가 증명). `standards_university/models.py`는 NCIC 비유래라 불변
- [x] 과학 코드 수용성 회귀 테스트: `[12물리01-01]`·`[10통과1-01-01]`·`[12화학02-03]`·`[9과01-05]`·`[12물리Ⅱ03-02]` 패턴 통과 + `AchievementStandard(subject='물리학Ⅰ')` 생성 + norm_id `2022_12물리_01_01` 통과
- 완료 판정: 공통 게이트 + data-pipeline 커버리지 91% 유지 + 기존 코퍼스 재생성 diff 0

### S3 — 과목 중립성 회귀 게이트
- [x] `tests/data_pipeline/test_subject_neutrality_gate.py`: citation 단일 원천(3모듈이 빌더 출력 포함 + "[수학과 교육과정]" 리터럴이 `citation.py` 밖 재등장 금지) · AREA 예약 접두(물리 예약 MECH·ELEC·WAVE·THERMO·MODPHY 등) 미침범
- [x] `tests/backend/l4/test_misconception_namespace_gate.py`: 수학 오개념 30종 id가 예약 과목 접두(`phys-`·`chem-`·`bio-`·`earth-`) 비사용 + kebab 형식
- [x] `schema/enums.py` `Subject` docstring 1줄(수학 교과 한정 — 타 과목은 향후 `subject_area` 축) · `edge.schema.yaml` evidence_source 주석(`<subject>_education_literature` 패턴 규칙·rename 금지)
- 완료 판정: 공통 게이트 (값·멤버 무변경이므로 마이그레이션 0)

### A부 보류 항목 (착수 트리거 도달 전 구현 금지 — S0 문서의 대장이 정본)
- `dimensional_consistency` primitive(sympy.physics.units) — 트리거: 물리 문항 검증 소비처 첫 등장. **커널 교체 아님**(동치 권위는 SymPy 단일 유지)
- `Problem.subject_area` 컬럼 — 트리거: 물리 문항 첫 적재 (기존 `Subject` enum에 물리 값 ADD VALUE 금지 — 축 혼동 영구화)
- 물리 오개념 시드(`phys-` 접두) — 트리거: 오개념 canonical 수렴 완료 + 물리 콘텐츠 착수
- PHY AREA 니모닉 실등록·idmap 개편 — 트리거: 물리 원천 코퍼스 category 목록 확정
- 개념 ID 재발급 — **영구 금지**(3번째 breaking·편익 0)

---

## B부 — 현단계에 이미 등록된 선결 부채 (확장의 전제 조건)

다과목 확장 로드맵 P0가 "새로 발견"한 것이 아니라 MEMORY 결정 로그에 이미 등록된 부채. 타 과목 콘텐츠 착수 전 완료가 전제인 항목에 ★.

- [ ] ★ **오개념 canonical ID 수렴** — 3중 표현(kebab 30 / M-id 839 / JSONB, FK 없음) 단일화 (MEMORY 2026-07-01 "🔴 최우선 부채"). 완료 후에만 오개념 유형 5분류(절차/개념/표상/오독/사실혼동 — 로드맵 제안 수용) 축 추가
- [ ] ★ **임베딩 namespace 분리** — concept/atom/misconception 벡터공간 분리(invariant ⑨). 이 설계에 **과목 축을 함께 반영**(로드맵의 "ChromaDB 컬렉션 분리" 항목의 올바른 실체 — 저장소는 pgvector)
- [ ] `Problem`의 `Curriculum` enum 잔여 제거 — 교육과정 Overlay 이관 완주(2026-07-01 failure-mode QA 우선순위 목록)
- [ ] 그래프 위생 게이트 — 런타임 reachability/SCC(현재 load-time DFS만). 단, 소비처(증분 edge-add 경로) 생길 때 — premature 금지
- [ ] 렌더 선택 단일 진실원(invariant ⑩ — 3곳 산재) · speech 파서 notation_contract 편입(⑪) — 과목 확장 시 렌더/음성 규칙이 과목별로 늘어나기 전에

---

## C부 — Phase 1(MVP) 종료 게이트 대조 (정본: ROADMAP.md)

### 저장소 정본 게이트 (Phase 2 진입 조건 — 변경 불가)
- [ ] β 사용자 100명 이상
- [ ] 사용자 재방문율 30%+ (7일 기준)
- [ ] Polya 답 미루기 단계 평균 2.5+ 도달
- [ ] LLM 호출 비용 학생당 월 1,000원 이하
- [ ] 도메인 파트너 검수 통과
- [ ] 미달 시 Phase 1 연장 (게이트 완화 금지)

### 다과목 로드맵 P1 체크와의 관계 (충돌 없음 — 보완 관계)
로드맵 P1(수학 출시)의 지표는 저장소 게이트를 세분·보강한다. 채택 권장 항목:
- [ ] 핵심 플로우 E2E: 촬영→OCR→개념 매칭→진단→소크라테스→오개념 태깅, 상이한 10문제 연속 무오류 (단 OCR 정본은 PaddleOCR+Qwen3-VL — 검토 문서 C5)
- [ ] 오개념 태깅 적중률 표본 검증 30건 수기 대조(목표 70%+) — 기존 "판정-실제 오개념 일치율" 대리 지표(04a §8.4 0단계 7종)와 통합 측정
- [ ] 온보딩: 학년·목표 입력→첫 진단 5문항→첫 소크라테스 체험 3분 이내
- [ ] D1/D7 리텐션 계측 — 저장소 게이트(7일 30%+)가 상위 기준, 로드맵의 "베타 종료 D7 25%+"는 베타 중간 기준으로 병기
- [ ] 만 14세 미만 법정대리인 동의 플로우 — **이미 구현 자산 존재**(`parental_consent`·ConsentScope·PIPA 매트릭스, 2026-06 슬라이스): 신규 개발이 아니라 온보딩 배선·전문가 검토 예약만 잔여
- [ ] 크래시 리포팅·저속망/오프라인 동작 정의·로컬 추론 동시 세션 상한 실측 + 클라우드 폴백 비용 상한 — L5/인프라 잔여 (클라우드 폴백은 기존 L3 라우터 경유 원칙 유지)
- [ ] 스토어 심사 준비(데이터 보안 섹션·아동 정책·구독 설계) — Phase 1.5 결제 결정과 연동(ROADMAP "의도적으로 안 하는 것" 존중: 결제는 Phase 1.5~2)

### 확장 관점 추가 게이트 (본 체크리스트 신설분)
- [ ] Phase 2(타 과목 착수) 진입 전: **A부 S0~S3 완료 + B부 ★ 2건 완료** — 이것이 다과목 로드맵 P0 완료 판정의 저장소 측 정의
- [x] 과목 순서(물리 vs 화학) MEMORY 결정 로그 확정 — **물리 우선 locked**(사용자 확인·MEMORY 2026-07-02)

---

**작성**: 2026-07-02 · **다음 갱신**: A부 슬라이스 완료 시마다 체크 반영, Phase 1 게이트 수치는 월간 검토(ROADMAP 주기)와 동기
