# MEMORY.md — 결정 로그·현재 상태

> **이 파일은 *대화의 휘발성*에 대한 방어선입니다.**  
> 새로운 결정, 폐기된 접근, 핵심 인사이트를 누적 기록.  
> Claude 세션이 끝나도 *진실*은 여기 남습니다.

---

## 🏷️ 브랜드 (확정)

- **앱명**: WhyMath (와이매스)
- **슬로건 (KR)**: 답이 아닌, 이유를 묻는 수학
- **슬로건 (EN)**: The math that asks why.
- *상세는 아래 "2026-05-14: 브랜드명 확정" 결정 로그 참조*

---

## 📍 현재 상태 (2026-05 시점)

### Phase
- [x] Phase 0: 청사진 수립 완료 (CLAUDE.md, ROADMAP.md, 7계층 아키텍처)
- [~] **Phase 1: MVP 개발 (0~6개월) — *착수*** (2026-05-13)
- [ ] Phase 2: 풀 K-12 (6~12개월)
- [ ] Phase 3: 영재·B2B (12~24개월)

### 활성 작업
- 🔄 **L1.NCIC.정제** (별도 PR) — `_PdfStandardExtractor` 영역 추출 + 본문/해설 분리 (2026-05-15 결정 로그 참조)
- 🔄 **ROCm 7.2+ Linux native 시도** (옵션 F, 별도 세션) — DirectML 32 tok/s 의 *2-3x 잠재력* 시도. BIOS UMA Frame Buffer Fixed 48-64GB + Linux Kernel 6.18.4+ + ROCm 7.2.0+ 요구. 출발점: `infra/phaiakes9/GPU_ACTIVATION_FOLLOWUP.md` §3 옵션 A·C
- ✅ **M1.2-live S1 완료** (계획·구현·검증 2026-05-21 — `/plan M1.2-live`) — L3 라우터 스텁→실연동 첫 슬라이스 (Ollama 로컬 경로). 범위: ① `l3/providers/ollama.py`(`OllamaProvider`, `resolve_model`→모델 ID, ollama lazy + Protocol seam) ② `l3/pipeline.py`(`generate()`: route→캐시 get→히트면 반환·미스면 생성→캐시 set→trace.record; `mode=="async"`(QUALITY)는 S4까지 sentinel 차단, 동기 호출 금지) ③ `app.py` FastAPI(`/health` 생존·`/status` Ollama 도달성+모델 매트릭스 가용성·`POST /v1/generate` — *원시 출력, 학생 직접 노출 아님; 03 환각 방어 선행*) ④ `config.py`(pydantic-settings, env 전용·시크릿 0). 캐시/추적은 인메모리 스텁 재사용. 테스트=단위(CI 가짜 주입 70%+)+`integration` 마커(Phaiakes9 실측). **후속 슬라이스**: S2 Redis CacheBackend·S3 Langfuse TraceSink·S4 Celery QUALITY 큐(동시성1, §D.3)·S5 클라우드 Anthropic(§H#4 Phase1 후반). backend-engineer 위임 후 **메인 독립 재검증**: 4게이트 green(ruff·black·mypy-strict·pytest **170 passed/2 integration skip**)·커버리지 **100%**. integration은 `WHYMATH_RUN_INTEGRATION` env 게이트로 CI 자동 skip(`tests/backend/conftest.py`, 라이브 Ollama는 Kiki·Phaiakes9 실측). 신규 소스 5(`config.py`·`app.py`·`l3/pipeline.py`·`l3/providers/{__init__,ollama}.py`) + 테스트 5 + `conftest.py` 수정. 판단: `/v1/generate` 본문은 `request:RoutingRequest` 중첩(extra=forbid 충돌 회피)·QUALITY는 503 JSON·`check_status`는 provider feature-detect.
- ✅ **M1.2-live S2 완료** (구현·검증 2026-05-21) — 인메모리 캐시 스텁 → 실 Redis CacheBackend 교체. 신규 `l3/cache/redis_cache.py`(`RedisCache`, redis.asyncio lazy + `_RedisClient` seam, 실 TTL `SET EX`·`ttl<=0`은 무만료 폴백·`_decode` bytes/str 방어·`ping()` 향후 레디니스용) + `config.py` `redis_url`(env, 시크릿 0) + `create_app()` 기본 캐시 RedisCache(지연 연결, 앱 구성 시 라이브 Redis 불필요). 현 브랜치에 S1 위 스택(PR #17 확장). **메인 독립 재검증**: 4게이트 green(ruff·black·mypy-strict·pytest **193 passed/6 integration skip**)·커버리지 **100%**(`redis_cache.py` 100%). CI hermetic 유지: 단위는 가짜 redis+`InMemoryCache` 주입, 라이브 Redis 4건은 `WHYMATH_RUN_INTEGRATION` 게이트(Kiki·Phaiakes9). `/status`·라우터·파이프라인 미변경. **후속**: S3 Langfuse·S4 Celery 큐·S5 클라우드.
- ✅ **M1.2-live S3 완료** (구현·검증 2026-05-21) — 인메모리 트레이스 스텁 → 실 Langfuse TraceSink 교체. 신규 `l3/trace/langfuse_sink.py`(`LangfuseSink`, langfuse **4.6.1**(v3 OTel SDK) lazy + `_LangfuseClient` seam, `create_event(name="l3_routing", metadata=…)`·태그는 metadata 내 `tags` 리스트로(v3엔 tags 인자 없음)) + `config.py` Langfuse 키(공개키·`SecretStr` 시크릿키 **기본값 없음**·호스트만 무해 디폴트·`langfuse_configured` 프로퍼티) + `create_app()` 기본 trace LangfuseSink(지연·자가 비활성). **시크릿 안전**: SecretStr 평문은 클라이언트 생성 순간만 추출·로그/repr 노출 0·하드코딩 0. **never-break**: 미설정→영구 no-op(네트워크 0)·예외는 삼킴(관측성<가용성, CLAUDE.md #1≫#6)·로그에 키/PII 없음(`student_id_hash`는 이미 해시, 통과만). 현 브랜치에 S1·S2 위 스택(PR #17). **메인 독립 재검증**(langfuse env 제거 상태): 4게이트 green(ruff·black·mypy-strict·pytest **217 passed/8 integration skip**)·커버리지 **100%**(`langfuse_sink.py` 100%). 라이브 Langfuse 2건은 `WHYMATH_RUN_INTEGRATION`+키 이중 게이트(Kiki). `/status`·라우터·파이프라인 미변경. **후속**: S4 Celery QUALITY 큐·S5 클라우드.
- ✅ **M1.2-live S4 완료** (구현·검증 2026-05-21) — QUALITY(27b) 비동기 큐(Celery, broker=Redis). 신규 `l3/queue/`(`celery_app.py` build_celery_app **worker_concurrency=1**·prefetch=1·JSON 직렬화·lazy / `tasks.py` `run_quality_generation_payload`(플레인)+태스크, `asyncio.run`으로 async provider 실행 / `celery_job_queue.py` `CeleryJobQueue`(`AsyncJobQueue`)+`JobStatus`, `_CeleryApp`/`_CeleryResult` seam, name-based `send_task`·`result()` 기능탐지) + `config.py` `celery_broker_url`/`celery_result_backend`(빈=redis_url 폴백, `effective_celery_*`). 파이프라인 async 분기: QUALITY→enqueue→`GenerationResult(status=queued, job_id)`(큐 None→`QualityQueueUnavailableError`, enqueue 실패도 변환→503). `app.py`: `/v1/generate` QUALITY→**202+job_id**, 신규 `GET /v1/jobs/{job_id}`(폴링, success=text·failure/unknown=사유, 500 없음). **fresh main(S1–S3 머지, `db84a66`) 위 새 브랜치 `claude/m12-live-s4`**. **메인 독립 재검증**: 4게이트 green(ruff·black·mypy-strict·pytest **259 passed/10 integration skip**, 3.6s=브로커 미연결 hermetic)·커버리지 **100%**. **never-break**: 브로커 다운→503(500 아님)·result 조회 오류→`unknown` 흡수. 동시성1은 앱설정+기동명령 `celery … worker -c 1` 이중 강제(§D.3). 판단: JSON 직렬화(pickle X)·name-based dispatch(큐앱≠워커앱). **후속**: §H#6 큐 SLA(retry/DLQ/backpressure 미정)·S5 클라우드.
- ✅ **M1.2-live S5 완료** (계획·구현·검증 2026-05-23 — `/plan`) — 클라우드 티어 실연동(Anthropic Claude, 03a §H 후속 4). 라우터가 이미 내리던 CLOUD_MID(Sonnet 4.6)·CLOUD_HIGH(Opus 4.7) 결정을 실제 생성으로 잇는다(기존 기본 provider `OllamaProvider`는 클라우드 거부). 신규 `l3/providers/anthropic.py`(`AnthropicProvider`, `anthropic` AsyncAnthropic lazy + `_AnthropicClient`/`_Messages`/`_Models` seam, `resolve_cloud_model`→모델 ID, **plain `messages.create`(샘플링·thinking 인자 0 — Opus 4.7 400 회피)**·`_extract_text`(content 블록 `type=="text"`만 join)·`check_status`=`models.list` 도달성·`AnthropicStatus`) + `l3/providers/composite.py`(`CompositeProvider`, `cost_tier` 디스패치 LOCAL→Ollama·CLOUD_*→Anthropic, `check_status`=로컬 위임·`check_cloud_status`=클라우드 분리 — **pipeline/app `generate(provider=)` 시그니처 무변경**) + `config.py` Anthropic 설정(`anthropic_api_key` **SecretStr·기본값 없음**·`anthropic_model_mid/high` alias·`anthropic_max_tokens`·`anthropic_request_timeout_s`·`anthropic_configured` 프로퍼티) + `app.py` 기본 provider=`CompositeProvider(Ollama+Anthropic)`·`StatusBody` 클라우드 필드(선택, 기본 None=미노출)·`/status` cloud_* 분기(기존 로컬 매핑 보존). **클라우드는 mode=sync(03a §C.4)→Celery 큐 미경유→워커 무변경**(불변식상 QUALITY만 async). **시크릿 안전**: 평문은 클라이언트 생성 순간만 추출·로그/repr 0·하드코딩 0. **never-break vs fail-loud 구분**: `/status`는 클라우드 미설정·도달 불가를 비크래시 보고(500 X); 그러나 `generate`는 *클라우드 결정인데 키 없으면* **명확한 RuntimeError**(조용한 LOCAL 강등 금지 — 정확성>가용성, CLAUDE.md #3). **fresh branch `claude/tender-knuth-zXu1L`**. **메인 독립 재검증**: 4게이트 green(ruff·black·mypy-strict·pytest **306 passed/13 integration skip**)·커버리지 `anthropic.py`·`composite.py`·`config.py` **100%**(TOTAL 99%). 라이브 Anthropic 3건은 `WHYMATH_RUN_INTEGRATION`+키 이중 게이트(Kiki). 라우터·파이프라인·큐 미변경. **범위 결정(Kiki)**: 프롬프트 캐싱·실측 비용/지연·`guard_cloud` 임계값 보정·thinking/effort 튜닝은 라이브 키 보정 후속(§H#4 잔여). **후속**: 토큰 usage 기반 실비용 회계(`response.usage`→budget 차감, provider 반환 계약 변경 필요)·프롬프트 캐싱.
- ✅ **M1.2-live S5 잔여 — 튜닝 노브 배선** (2026-05-23, "잔여진행") — 라이브 키가 없어 *실측 보정·thinking 튜닝값·캐시 적중 검증*은 Kiki 몫이라, **키 없이 가능한 코드 배선만** 추가: `config.py` `anthropic_effort`(str, 기본 "")·`anthropic_thinking`(bool, 기본 False)·`anthropic_prompt_caching`(bool, 기본 False) + `AnthropicProvider.generate`가 *설정된 경우에만* `output_config={effort}`·`thinking={type:adaptive}`·top-level `cache_control={ephemeral}`를 싣는다(`_Messages.create` seam에 `**kwargs`). **전부 기본 OFF=현 동작 무변경**(Opus 4.7 plain create 유지) — Kiki가 env로 켜고 튜닝(코드 변경 0). 4게이트 green(pytest **313 passed/13 skip**)·`anthropic.py`·`config.py` 커버리지 **100%**. **여전히 키 필요(미진행)**: effort/thinking 최적값·캐시 적중률·실측 비용/지연·`guard_cloud` 임계값(§H#4) + 토큰 usage 실비용 회계(L3 `LLMProvider` 반환 계약 변경 — 별도 슬라이스로 분리, 파급 큼).
- ✅ **빌드타임 사전생성 — 슬라이스 1 (캐시 사전적재 하니스)** 완료 (계획·구현·검증 2026-05-23 — `/plan 2`) — MEMORY 2026-05-20 "Max=빌드타임" 결정의 첫 실현. 신규 `l3/pregenerate/` 패키지: `models.py`(`PregenItem` pydantic·`PrewarmReport`·`PrewarmItemResult`)·`validator.py`(`SeedValidator` Protocol + `BasicSeedValidator` 최소 위생 — 비어있음·길이·오류 마커)·`prewarmer.py`(`CachePrewarmer`, **런타임 `pipeline.generate`와 *같은* `Router`·`cache_key_for` 재사용** → 동일 키로 적재 → 런타임 캐시 히트 보장)·`__main__.py`(JSONL CLI, `python -m whymath_backend.l3.pregenerate <specs.jsonl>`). **두 입력 모드**: 인제스트(`precomputed_response` — Max-Claude 시드) / 생성(provider 호출). **무만료 적재**(`ttl_seconds=0` 기본 — S2 RedisCache의 ttl<=0 무만료 활용). **QUALITY async는 명시 error**(런타임이 async 분기에서 캐시를 안 쳐서 사전적재 무의미, pipeline.py:128-149). **킬러 테스트**: pre-warm 후 동일 (req,prompt,system)으로 `pipeline.generate` → `cache_hit=True`·runtime provider 미호출(키 정합 e2e 증명). **fresh branch `claude/tender-knuth-zXu1L`(S5 머지 후 그 위에 적층)**. 4게이트 green(ruff·black·mypy-strict·pytest **338 passed/13 skip**)·신규 5개 모듈 **전부 커버리지 100%** (`__init__`·`__main__`·`models`·`prewarmer`·`validator`, TOTAL 99%). 변경 없음: 런타임(`pipeline.py`·`app.py`·`router.py`·`cache/`·`providers/`). **후속**: L1 성취기준→스펙 자동 생성·DB 코퍼스 내구화(Redis 플러시 대비)·PRM/SymPy 검증 통합·Max 인제스트 포맷 확정·캐시 에빅션/리프레시 정책.
- ✅ **빌드타임 사전생성 — 슬라이스 B (SymPy 산술 검증 게이트)** 완료 (구현·검증 2026-05-28 — 합의 순서 A→B→C에서 **B 우선**) — A(L1 성취기준→스펙)는 조사 결과 *실데이터 부재(`data/ncic` 비어 있음)·L4 프롬프트 미구현(docs만)·크로스패키지 결합(`data_pipeline`↔`whymath_backend`)*으로 이 환경 완전검증 불가라 보류; B는 의존 0이라 먼저. `validator.py`에 `SymPyArithmeticValidator`(응답의 *순수 수치 등식*을 SymPy로 검증 — 거짓이면 시드 탈락; 03 환각 방어의 *도구 검증* 첫 조각) + `ChainValidator`(여러 검증기 AND 합성) 추가, CLI 기본 게이트를 `Basic→SymPy` 체인으로 강화. **false-positive 0 설계**: 유니코드 연산자(×÷−·) 정규화 후 *독립 수치 등식*만 검사 — 연산자·변수·한글 인접("x + 1 = 2"의 "1=2")은 건너뛰고(경계 검사), 개행은 강한 구분자로 *줄별* 검사. 거짓이 *증명*될 때만 탈락(심볼릭·파싱불가·판정불가는 통과). max_checks로 과부하 차단. **fresh branch `claude/tender-knuth-zXu1L`(slice 1 머지 후 main 위 재시작)**. 4게이트 green(ruff·black·mypy-strict·pytest **366 passed/13 skip**)·`validator.py`·`__main__.py` 커버리지 **100%**(TOTAL 99%). 런타임 미변경. **후속**: A(성취기준→스펙, pedagogy-designer 동반·실데이터 Kiki 환경)·PRM/LLM-judge·Lean 증명 검증·C(M1.2 시나리오+SolutionPath).
- ✅ **Schema v1.0 — 슬라이스 1 (ENUM + Problem, 법적 교정)** 완료 (구현·검증 2026-05-28, `/plan` 승인→backend-engineer 위임→**메인 독립 4게이트 재검증**) — 신규 `whymath_backend/schema/`(`enums.py` 14 str-Enum[SourceType·ExamType·Curriculum·Subject·QuestionFormat·AnswerFormat·SignaturePattern 10종·Persona A~E·VisualType·LicenseType·GenerationType·ReviewStatus·StepType·RelationType, Schema v1.0 §14.3 값 그대로]·`problem.py` `Condition`/`Problem`(50+필드)/`ProblemStep`/`ProblemRelation`·`__init__`) + 테스트 2(`tests/backend/schema/`). **법적 교정 invariant**(MEMORY 2026-05-28): `_METADATA_ONLY_SOURCES={평가원,EBS,교과서}` source_type이면 `question_text`·`answer_explanation`·`choices` 비어야(아니면 ValidationError; 저작권 가이드 v2.0 §32 단서·§136·§140) — `@model_validator(mode="after")`. **Pydantic-first**(코드베이스 전체가 Pydantic-only·`ncic/load_to_postgres` NotImplementedError seam 답습; SQLAlchemy/alembic은 DB 배포 시 후속). **메인 4게이트 green**: ruff·black·mypy-strict("no issues, 28 files")·pytest **432 passed/13 skip**(366→+66)·신규 schema 모듈 cov **100%**. 판단: DDL NOT NULL `question_text`/`answer`→Optional 완화(메타전용 레코드 표현·법적교정 정합), JSONB는 `conditions_parsed`만 `list[Condition]` 서브모델·자유형은 dict, DECIMAL→float(ge/le 범위), `Curriculum.REVISION_2022`(숫자접두 금지). **검증 주의**: backend-engineer가 권한 제약으로 게이트 실증 못 해(정적 추론만) 메인에서 재실행 — black 2파일 실제 재포맷 필요했음(에이전트 "black 안정" 주장 오류 → 메인이 교정). **후속**: 슬라이스 2(`provenance.py` ContentProvenance+generation_log, license/generation_type 교정, l3 pregenerate 연결)→3 Concept→4 User→5 Activity/Dialogue→6 Assessment/TimeSeries→7 textbook_mapping→(후속)SQLAlchemy+alembic.
- ✅ **Schema v1.0 — 슬라이스 2 (Provenance: ContentProvenance+GenerationLog, license/gen 법적 교정·l3 연결)** 완료 (구현 backend-engineer 위임→**메인 독립 재검증**, 2026-05-28) — 신규 `schema/provenance.py`(`ContentProvenance` 16필드+법적 `@model_validator(after)`·`GenerationLog` 12필드, 둘 다 §10.1 DDL)·`l3/pregenerate/provenance_bridge.py`(`generation_log_from_result` 순수 어댑터)·`schema/__init__` export + 테스트 2. **법적 invariant**(MEMORY 2026-05-28 속편 "스키마 법적 교정"·저작권 가이드 v2.0 §32단서·§136·§140): **(A)** `generation_type=ORIGINAL` 전역거부 · **(B)** `license=EBS_LICENSED` 전역거부(둘 다 공식제휴 Phase3+ 예약) · **(C)** `original_source∈_METADATA_ONLY_SOURCES{평가원·EBS·교과서}`이면 (C-1)`license=WHYMATH_GENERATED`만 허용·(C-2)`generation_type` 변형류(VARIANT_*/COMPOSED/FULLY_GENERATED)만(None·비변형 거부)·(C-3)`original_reference` 본문성 키 denylist 차단(구조 메타만). enum/문자열 정규화(use_enum_values). **계층 규칙 준수**: `schema`(L1)는 l3 import 0; 연결 어댑터는 l3쪽 배치(L3→L1 허용). provider가 usage 미노출(prewarmer.py:111)→토큰/비용/지연 None(후속). 신규 2모듈 cov **100%**. **CI 동일 격리 venv(py3.12+`pip install -e .[dev]`) 4게이트 green**: black 26.5.1·ruff 0.15.15·mypy-strict(30파일)·pytest **500 passed**(432→+68, `--cov-fail-under=70` 통과). **⚠️ 도구 drift 발견·교정(전 슬라이스 영향)**: ① **black 거짓통과 함정** — `black … ../../tests/` mixed-path는 common-base=repo루트(black config 없음)→기본 **line-length 88** fallback→통과로 보임. 정본 검증은 `cd src/backend && black --check .`(=CI, **ll=100**·py3.12·black<27). slice1·slice2 둘 다 88로 잘못 포맷돼 있었음 → **slice1 `problem.py`도 이번에 100으로 함께 교정(포맷만, 의미 0)**. ② **시스템 black 26.3.1은 py3.11→py3.12 코드 파싱 불가**(검증 부적합) — py3.12 venv 필수. ③ **CI 갭(발견)**: ruff/black/mypy 게이트는 src/backend 기준이라 `tests/backend/**`는 미검사(pytest 실행만). **후속**: 슬라이스 3 Concept(§4 concept·concept_edge·problem_concept·concept_fusion)→4 User→5 Activity/Dialogue→6 Assessment/TS→7 textbook_mapping→(후속)SQLAlchemy+alembic.
- ✅ **Schema v1.0 — 슬라이스 3 (Concept Graph: §4 4모델 + ENUM 4종)** 완료 (backend-engineer 위임→**메인 독립 재검증**, 2026-05-28) — `enums.py`+4(`ConceptLevel` 단원/소단원/세부개념·`CognitiveType` 5·`EdgeType` 5·`ConceptRole` 4; §14.3 부재→§4.2 인라인 DDL 주석 정본, slice1 ExamType 방식)·신규 `schema/concept.py`(`Concept` 20필드·`ConceptEdge`·`ProblemConcept` N:M·`ConceptFusion`)·`__init__` export +8·테스트 1(41 케이스). **구조 invariant**(`@model_validator(after)`, slice1 `ProblemRelation._no_self_relation` 패턴): `Concept._no_self_parent`(parent≠concept_id)·`ConceptEdge._no_self_edge`(from≠to). **법적 판단**: concept free-text(`description`·`formal_definition`·`intuitive_explanation`)는 교과서/EBS 표현 복제 금지지만 *구조 신호가 없어* validator 강제 불가 → docstring 3곳 문서화만(검수 단계 책임). slice1/2 본문 차단은 source_type/license라는 구조 신호가 있었던 것과 대비 — **가짜 validator 날조 회피**. 복합 PK(`ProblemConcept`=problem+concept+role, role도 required)·`concept_ids` min_length=1·`embedding_id`는 ChromaDB 외부참조 UUID(벡터 저장 아님, §4.3 인프라설정 제외). ge/le 판단(DDL 미명시, 각 description 명시): weight_in_curriculum 0-1·fusion_difficulty 1-5·grade 1-12·semester 1-2. **CI 동일 venv(`/tmp/civ`) 4게이트 green**: black 26.5.1(31파일·이번엔 에이전트가 `/tmp/civ` 사용→거짓통과 없음)·ruff·mypy-strict(31)·pytest **541 passed**(500→+41, cov-fail-under=70)·concept.py cov **100%**. **trust 메모**: 에이전트가 enum 4종을 *추가*(+75줄)해 놓고 보고선 "이미 있었음(수정 불필요)"이라 오서술(슬라이스마다 자체보고 신뢰성 반복 이슈) — 실제 작업·값은 정확, 메인이 ground truth(git diff·게이트) 확인. **후속**: 슬라이스 4 User(§5 user_profile·user_track_history·user_persona_history·user_state_snapshot; school_type·region·track_type·persona 등 ENUM 다수 신규).
- ✅ **Schema v1.0 — 슬라이스 4 (User: §5 4모델 + ENUM 7종)** 완료 (backend-engineer 위임→**메인 독립 재검증**, 2026-05-28) — `enums.py`+7(`SchoolType` §14.3 12값·`TrackType` 8·`MajorCategory` 8·`Device` 4[iPhone `#noqa N815`]·`NoteApp` 4·`SubscriptionTier` 3·`Accessibility` 5)·신규 `schema/user.py`(`UserProfile` 40필드·`UserTrackHistory`·`UserPersonaHistory` 복합PK·`UserStateSnapshot`)·`__init__` +11·테스트 1(46). **결정(Kiki 확인요): `gender`·`school_region`은 enum 아닌 `str | None`** — §14.3 정의 없고 §5.1 DDL 주석 미완결(gender 값 미기재·region "강남/대치/지방/**...**"), v1.1은 region을 시도교육청 *코드 문자열*로 모델링, 미성년 민감정보라 닫힌 카테고리 강제 부적절 → 닫힌 enum 날조 회피, **Kiki 값 확정 시 enum 승격**(가역적·필드 description에 명시). **개인정보**: UserProfile은 미성년 민감정보(email_hash·birth_year 연단위·parent_consent_at) — CLAUDE.md 금기 docstring 상기만, "is_minor→parent_consent 필수" cross-field 강제 안 함(동의 *대기* 상태 정당히 존재→미들웨어/검수 책임; concept.py 방침). validator 0(구조 불변식 없음=없는 게 맞음). `persona_primary`만 required. `target_exam_date`=`date`(DATE형). ge/le 판단(DDL 미명시, 각 description 근거): birth_year 1900-2100·grade 10-14·target_score/spend/days ge=0·estimated_grade 1-9·percentile 0-100·session_quality 0-1. **CI 동일 venv(`/tmp/civ`) 4게이트 green**: black 26.5.1(32파일)·ruff·mypy-strict(32)·pytest **587 passed**(541→+46, cov-fail-under=70·전체 99.95%)·user.py cov **100%**. **trust 메모(3회째 반복)**: 에이전트가 enum 7종을 *추가*(+112줄)해 놓고 "이미 있었음(수정 불필요)"이라 또 오서술 — 실제 작업·값은 정확, 메인이 git diff·게이트로 ground truth 확인(이 자체보고 패턴은 슬라이스마다 재검증 필수임을 재확인). **후속**: 슬라이스 5 Activity/Dialogue(§6 학습활동·§7 Socratic 대화).
- ✅ **Schema v1.0 — 슬라이스 5 (Activity §6 + Dialogue §7: 5모델 + ENUM 8종)** 완료 (backend-engineer 위임→**메인 독립 재검증**, 2026-05-28) — `enums.py`+8(`SessionType` 5·`AttemptMode` 4·`EventType` 8·`Resolution` 5·`TurnRole` 3·`ContentType` 4·`SocraticStrategy` 6·`StudentIntent` 5; §14.3 부재→§6/§7 인라인 DDL 정본)·신규 `schema/activity.py`(`LearningSession` 14·`ProblemAttempt` 21·`AttemptEvent` 7)·`schema/dialogue.py`(`Dialogue` 16·`DialogueTurn` 14)·`__init__` +13·테스트 2(57). **BIGSERIAL 처리**: `AttemptEvent.event_id`는 BIGSERIAL→`int|None=Field(default=None,ge=1)`(DB-assigned·default_factory 불가), `event_at`은 TIMESTAMPTZ NOT NULL→required(복합 PK·TimescaleDB hypertable 분할키). `DialogueTurn.turn_order` NOT NULL→required(ge=1, UNIQUE(dialogue_id,turn_order)). **개인정보**: ProblemAttempt(student_answer·handwriting_uri·ocr_result)·DialogueTurn(content·image_uri·image_analysis)=미성년 학생 데이터 — "평문 저장 금지"는 저장계층(암호화·미들웨어) 책임이라 docstring 상기만(가짜 validator 금지, user.py/concept.py 방침). validator 0(구조 불변식 없음; total_turns=student+assistant 카운트 정합도 system 턴 때문에 미강제). ge/le: focus/engagement/confidence/quality/understanding score 0-1·step/turn_order ge=1·counts/tokens/cost ge=0·student_rating 1-5·time_vs_expected ge=0·network_type str(VARCHAR 비enum). **CI 동일 venv(`/tmp/civ`) 4게이트 green**: black 26.5.1(34파일)·ruff·mypy-strict(34)·pytest **644 passed**(587→+57, cov-fail-under=70)·activity/dialogue cov **100%**. **⚠️ trust 메모(악화·4회째)**: 에이전트가 이번엔 enum 8종을 실제 추가(+113줄)해 놓고 "이미 있었음·enums.py 미수정"이라 보고하며 **수정파일 목록에서 enums.py를 누락** — 보고대로 믿었으면 enums.py 커밋 누락→CI 깨짐. **git status가 진실, 에이전트 자체보고는 *파일 목록조차* 신뢰 불가** → 매 슬라이스 `git status`+게이트 ground truth 확인이 필수(이미 그렇게 함). **후속**: 슬라이스 6 Assessment(§8 assessment·concept_mastery_history; assessment_type·mental_phase ENUM 신규·hypertable)→7 TimeSeries(§9)→textbook_mapping/curriculum_entry(v1.1 이식)→(후속)SQLAlchemy+alembic.
- ✅ **Schema v1.0 — 슬라이스 6 (Assessment §8: 2모델 + ENUM 2종)** 완료 (backend-engineer 위임→**메인 독립 재검증**, 2026-05-28) — `enums.py`+2(`AssessmentType` 5[`D_100예측="D-100예측"` — 식별자는 언더스코어·값은 하이픈 정본]·`MentalPhase` 6[D_100_PLUS·D_100_50·D_50_30·D_30_7·D_7_0·평상시, D-100 코칭 특성 #50])·신규 `schema/assessment.py`(`Assessment` 17필드·`ConceptMasteryHistory` 복합PK+hypertable)·`__init__` +4·테스트 1(26). `Assessment` 5개 JSONB 진단필드(concept/pattern_diagnosis·weak/strong_points·recommended_path)→`list[dict[str,Any]]`(weak/strong은 상세 담게 list[dict], list[str] 대신). `ConceptMasteryHistory` 복합 PK(user_id·concept_id·measured_at) 셋 required·TimescaleDB hypertable(7일 청크). 개인정보(미성년 진단 데이터) docstring 상기만(PIPA 권한매트릭스·저장계층 책임)·validator 0(구조 불변식 없음). ge/le: admission_probability·mastery·confidence 0-1·estimated_grade 1-9·percentile 0-100·score/sample_size ge=0. **CI 동일 venv(`/tmp/civ`) 4게이트 green**: black 26.5.1(35파일)·ruff·mypy-strict(35)·pytest **670 passed**(644→+26, cov-fail-under=70)·assessment.py cov **100%**. trust 메모(5회째): 에이전트가 `git status`는 정확히 붙였으나 또 "enums.py/assessment.py 이미 작성됨·이번 미수정"이라 오귀속(자기가 run 초반 만든 걸 '이전 것'으로 착각) — git status가 진실(enums.py +51줄·assessment.py 신규 = 이 슬라이스 산출), 메인이 ground truth 확인 후 커밋. **후속**: 슬라이스 7 TimeSeries(§9 daily_learning_metrics·problem_solve_time_distribution·user_behavior_metrics — 전부 hypertable·복합PK·persona_enum 재사용)→textbook_mapping/curriculum_entry(v1.1 이식)→(후속)SQLAlchemy+alembic.
- ✅ **Schema v1.0 — 슬라이스 7 (TimeSeries §9: 3모델, 도메인 마지막) → 🎯 8개 도메인 전부 완료** (backend-engineer 위임→**메인 독립 재검증**, 2026-05-28) — 신규 `schema/timeseries.py`(`DailyLearningMetrics` 8필드·`ProblemSolveTimeDistribution` 7필드·`UserBehaviorMetrics` 4필드)·`__init__` +3·테스트 1(29). **신규 enum 0**(Persona 재사용·metric_name VARCHAR str → `enums.py` 미수정, git status로 확인). 세 모델 모두 복합 PK(전 구성요소 required) + TimescaleDB hypertable(30/7/7일): DailyLearningMetrics`(user_id, metric_date[DATE→date])`·ProblemSolveTimeDistribution`(problem_id, persona[Persona enum이나 PK라 required], measured_at)`·UserBehaviorMetrics`(user_id, metric_name[str open set], measured_at)`. `metric_value`(DECIMAL10,4) **범위 무제약**(metric_name마다 의미 달라). 개인정보(churn_risk 등 미성년 *행동분석*) docstring 상기만·validator 0(분위수 p10≤p50≤p90·카운트 정합 미강제). **CI 동일 venv(`/tmp/civ`) 4게이트 green**: black 26.5.1(36파일)·ruff·mypy-strict(36)·pytest **699 passed**(670→+29, cov-fail-under=70)·timeseries.py cov **100%**. **🎯 마일스톤: Schema v1.0 8개 도메인(Problem·Provenance·Concept·User·Activity·Dialogue·Assessment·TimeSeries) Pydantic 구현 전부 완료** — `schema/` 패키지 9파일(enums+8도메인)·str-Enum 35종·모델 ~30종, 누적 pytest 699 passed, 신규 schema 모듈 전부 cov 100%. 전 슬라이스 black line-length 100·mypy-strict 통과. **후속**: ① v1.1 이식분 `curriculum_entry`(NCIC 성취기준 1급 — L1 파이프라인 산출)·`textbook_mapping`(교과서 구조 메타 — 자동 커리큘럼 정렬, 법적 안전) ② (후속)SQLAlchemy+alembic DB 매핑(`ncic/load_to_postgres` seam).
- ✅ **Schema — 슬라이스 8a (v1.1 이식: CurriculumEntry, 다국 커리큘럼 매트릭스)** 완료 (backend-engineer 위임→**메인 독립 재검증**, 2026-05-28) — `enums.py`+2(`RequiredDepth` 4[awareness/procedural/conceptual/mastery]·`CurriculumLicense` 5[`KR_NCIC="KR-NCIC"` 등 — 하이픈 식별자 처리, slice6 D_100예측 선례])·신규 `schema/curriculum_entry.py`(`CurriculumEntry` 30필드, 복합키 (concept_id×country_code)+표면키 entry_id)·`__init__` +3·테스트 1(35). 정본 `schemas/v1.1/curriculum_entry.schema.yaml`(v1.0 8도메인 밖, NCIC=한국 열). **강제 invariant 2개**(`@model_validator`): `is_present=true→source_url 비어있지 않아야`·`country_code='IMO'→confidence≤0.7`. **str 결정**(enum 날조 회피, slice4 방침): country_code(ISO 풀스케일 수용·Phase1 KR/US/IMO 가드는 파이프라인)·grade_band·cognitive_level(NCIC `AchievementStandard.subject`가 str인 것과 정합). source_url은 YAML required:true이나 invariant 정합 위해 `str|None`+validator. created_at/updated_at은 YAML required:true→required(slice1~7 Optional과 다름). cross-dataset invariant(concept_id/NCIC 코드 실재·복합키 유일성·Phase1 국가가드)는 파이프라인 책임 docstring. **CI 동일 venv(`/tmp/civ`) 4게이트 green**: black 26.5.1(37파일)·ruff·mypy-strict(37)·pytest **734 passed**(699→+35, cov-fail-under=70)·curriculum_entry.py cov **100%**. **⚠️ 에이전트 크래시(신규 실패유형)**: 서브에이전트가 *최종 보고 메시지 파싱 실패*로 크래시(보고 0개) — 그러나 36 tool-use 동안 4파일을 전부 올바르게 작성. 메인이 git status·게이트·코드 전수 검토로 ground truth 확인 → **보고가 아예 없어도 독립검증이 작동**(자체보고 신뢰 불가 원칙의 극단 사례). **후속**: 슬라이스 8b TextbookMapping(`schemas/v1.1/textbook_mapping.schema.yaml` — TextbookMapping+TextbookUnit(자기참조 트리)+TextbookToneProfile; **법적 핵심**: learning_objective_text는 legal_review_status='cleared' 전까지 null 강제·isbn 13자리·교과서 본문/문제 일절 미수집).
- ✅ **Schema — 슬라이스 8b (v1.1 이식: TextbookMapping, 마지막) → 🎯 Schema 구현 정본 전부 완료** (backend-engineer 위임→**메인 독립 재검증**, 2026-05-28) — `enums.py`+1(`LegalReviewStatus` not_required/pending/cleared — `ReviewStatus`와 별개·교과서 학습목표 저작권 검토)·신규 `schema/textbook_mapping.py`(`TextbookMapping` PK=isbn·`TextbookUnit` 자기참조 트리·`TextbookToneProfile`)·`__init__` +4·테스트 1(55). 정본 `schemas/v1.1/textbook_mapping.schema.yaml`. **🚨법적 invariant 2개**(`@model_validator`): ① isbn 13자리(`^\d{13}$`) ② **learning_objective_text 게이팅** — `legal_review_status≠cleared`면 `unit_tree` 전 단원 `learning_objective_text=None` 강제(교과서 학습목표는 저작물·변호사검토 전 미수집; MEMORY PRD 허점⑥ 한국법에 fair use 부재 — slice1 본문차단·slice2 license차단과 같은 *구조 신호(legal_review_status) 기반 진짜 invariant*, enum/문자열 정규화) + `TextbookUnit._no_self_parent`. unit_title max_length=200(본문혼입 모델 가드). **저작권 안전선**(YAML 헤더·CLAUDE.md): 구조 메타만(목차·단원명·페이지*번호*·서지 ISBN/출판사/서명/저자·교육과정 코드), 본문·예제·문제·풀이·그림 *일절 미수집* — 교과서 문제는 standard_codes/concept_ids로 자체 코퍼스 동등문제 대체(파이프라인에 "교과서 문제 수집" 단계 자체가 없음). str 유지: subject·publisher(NCIC subject str 정합). cross-dataset·트리 사이클 검증은 파이프라인 책임 docstring. **CI 동일 venv(`/tmp/civ`) 4게이트 green**: black 26.5.1(38파일)·ruff·mypy-strict(38)·pytest **789 passed**(734→+55, cov-fail-under=70)·textbook_mapping.py cov **100%**. trust(6회째): enums.py +36줄(LegalReviewStatus) 추가해 놓고 "이미 있었음" 또 오귀속 — git status가 진실, 메인 확인. **🎯 마일스톤: Schema 구현 정본 전부 완료** — v1.0 8도메인(Problem·Provenance·Concept·User·Activity·Dialogue·Assessment·TimeSeries) + v1.1 이식 2종(CurriculumEntry·TextbookMapping). `schema/` 12파일(enums + 11 모델모듈)·**str-Enum 38종·모델 ~36종**·누적 **pytest 789 passed**·신규 모듈 전부 cov 100%·전 슬라이스 black(ll=100)·mypy-strict 통과. 관통 원칙: 법적 교정은 *구조 신호 있을 때만* validator 강제(Problem 본문·Provenance license/gen·TextbookMapping 학습목표 게이팅), 신호 없으면 docstring 문서화(concept 설명·user 동의·학생 데이터). **후속**: SQLAlchemy+alembic DB 매핑(전 모델 → PostgreSQL16/TimescaleDB hypertable/ChromaDB, `ncic/load_to_postgres` seam·복합PK·hypertable 변환).
- ✅ **DB 영속 레이어 PoC (SQLAlchemy 2.0 async + alembic) — 인프라 + Problem 도메인** 완료 (backend-engineer 위임[ORM·인프라·스캐폴드]→**메인이 로컬 PG16으로 마이그레이션 생성·실검증**, 2026-05-28) — 사용자 결정: *별도 ORM*(SQLModel 아님)·*인프라+1도메인 PoC*. 신규 `whymath_backend/db/`(`base.Base` DeclarativeBase+naming_convention·`session` **lazy** async engine/`get_session`/`dispose`·`models/problem.py` ORM `Problem`·`ProblemStep`·`ProblemRelation`)·`config.database_url`(asyncpg DSN, WHYMATH_ override)·alembic 스캐폴드(`alembic.ini`·async `env.py`·`script.py.mako`)·초기 마이그레이션 `4c6d083dfeef_initial_problem_domain`·테스트(`tests/backend/db/`). **ORM 핵심**: `schema/enums.py` enum 재사용 + `_pg_enum(values_callable=lambda e:[m.value...])` **필수**(`Curriculum.REVISION_2015→"2015_REVISION"` 등 멤버명≠값 보존 — 없으면 PG enum이 멤버명으로 생성돼 §14.3 DDL과 어긋남)·JSONB(conditions_parsed·persona_fit·choices)·ARRAY(TEXT[]·enum[])·GIN 4종·UUID `gen_random_uuid()`·복합PK·FK. **변환 헬퍼** `from_schema`/`to_schema`(mapper 컬럼키 필터 — schema(검증)↔db(영속) seam). 본문 미보유 invariant는 schema.Problem 책임(ORM 컬럼만·가짜 CHECK 없음). **메인 PG16 실검증**(postgres 유저·:55432, root는 PG 실행 거부): autogenerate→**upgrade(3테이블·11 enum)→downgrade(잔존 테이블·enum 0)→재-upgrade→`alembic check` "No new upgrade operations"** 왕복 green. **메인 교정 2건**: ① autogenerate가 downgrade에서 native enum 미drop → 재-upgrade "type already exists" 실패(alembic 표준 갭) → downgrade에 `postgresql.ENUM(name).drop(checkfirst=True)` 11종 추가 ② `script.py.mako`의 잘못된 "템플릿" docstring(모든 마이그레이션 오염) 제거. **4게이트 green**: black 26.5.1(45파일)·ruff·mypy-strict(43)·pytest **803 passed**(789→+14)·신규 db 모듈 cov 100%(session.py 33%=런타임 연결 경로 — PG 통합검증으로 커버). persona_fit은 JSONB라 persona_enum 미생성(∴ 11 enum). 검증가능성 메모: **이 sandbox는 TimescaleDB 확장 미설치·PG 서버 기본 미가동**이나 postgres 유저로 PG16 클러스터를 띄워 비-hypertable 도메인은 실검증 가능(hypertable 5종은 후속 env). **후속**: 나머지 8도메인 ORM·마이그레이션(동일 패턴 적층)·TimescaleDB hypertable 5종(`create_hypertable` raw op, 확장 있는 env)·FastAPI 라우터 get_session 배선·ncic `load_to_postgres` 구현.
- ✅ **DB 영속 레이어 — 배치 1 (5도메인 ORM·마이그레이션 적층): concept·provenance·user·curriculum_entry·textbook_mapping** 완료 (backend-engineer 위임[ORM]→**메인이 로컬 PG16 마이그레이션 생성·왕복 실검증**, 2026-05-28) — 신규 `db/models/`(`_orm_enum.py`[공통 `_pg_enum`/`_enum_values` 추출·problem.py도 import 전환]·concept[4테이블]·provenance[2]·user[4]·curriculum_entry[1]·textbook_mapping[2테이블 관계형])·테스트 5·마이그레이션 `1551744048aa`(problem 위 적층, 13테이블). problem.py 패턴 그대로(enum values_callable·JSONB·ARRAY·복합PK·FK·from_schema/to_schema). **textbook 비-1:1**: 중첩(unit_tree·tone_profile)→관계형 2테이블(`units` relationship·`ON DELETE CASCADE`·tone_profile JSONB 컬럼)+중첩 변환. `curriculum_entry` PK=entry_id 단일 + `UNIQUE(concept_id,country_code)`. 느슨참조(concept_ids·standard_codes·national_standard_codes 등)는 FK 아님(cross-dataset 파이프라인 책임). **메인 PG16 실검증**: upgrade(16테이블·28enum)→downgrade-1(3테이블·11enum, 공유enum 보존)→재upgrade→downgrade base(0·0)→`alembic check` 무드리프트 왕복 green. **메인 교정 2건(다중 마이그레이션 native-enum)**: ① **공유 enum 3종**(source_type·subject·curriculum — concept/provenance가 problem 마이그레이션 enum 재사용)을 `postgresql.ENUM(create_type=False)`로 재생성 방지(안 하면 upgrade "type already exists") + downgrade에서 *안* 떨굼(problem 소유) ② 신규 enum 17종은 downgrade에서 `ENUM(name).drop(checkfirst=True)`. **4게이트 green**: black 52·ruff·mypy-strict(49파일)·pytest **857 passed**(803→+54)·신규 db 모듈 cov 100%. ⚠️ **사후정정(2026-05-29 배치2 세션서 발견·교정)**: 배치1 커밋(`f0b9e19`) 당시 위 교정 2건이 *실제로는 파일에 안 들어갔음* — 첫 turn에 Edit 3개가 "File has not been read yet"로 **조용히 실패**했고 직후 API 오류(`thinking` 블록)가 검증 출력을 가려 *upgrade가 3·11(실패)인데 16·28로 오인*하고 그대로 커밋. **근본원인**: 공유-enum `DuplicateObject`는 **증분 배포 경로**(problem→배치1을 *별도 alembic invocation*으로 — 실제 운영 패턴)에서만 발현, `base→head` 단일 invocation은 SQLAlchemy가 동명 enum을 *프로세스 내 dedup*해 충돌을 감춤(∴ 배치2-on-배치1 단일왕복 테스트는 거짓 통과). 배치2 세션서 `downgrade base` 잔존 enum 17 발견→배치1 파일 ground-truth 확인(create_type=False 0개)→교정 2건 **재적용**·증분배포 시뮬(3·11→16·28→26·38→0·0)·`alembic check` green 재확인. **교훈**: 마이그레이션 검증은 *반드시 증분 경로*로(단일 base→head는 enum 충돌 위양성), git diff로 Edit 실제 반영 확인.
- ✅ **DB 영속 레이어 — 배치 2 (4도메인 ORM·마이그레이션, 마지막): activity·dialogue·assessment·timeseries** 완료 (backend-engineer 위임[ORM]→**메인이 로컬 PG16 마이그레이션 생성·증분배포 왕복 실검증 + 배치1 사후교정**, 2026-05-29) — 신규 `db/models/`(activity[3테이블: learning_session·problem_attempt·attempt_event]·dialogue[2: dialogue·dialogue_turn]·assessment[2: assessment·concept_mastery_history]·timeseries[3: daily_learning_metrics·problem_solve_time_distribution·user_behavior_metrics])·테스트 4·마이그레이션 `bb30b816083d`(배치1 위 적층, 10테이블). **복합 PK 다수**: attempt_event(event_id BIGSERIAL+event_at)·concept_mastery_history(user+concept+measured_at)·daily_learning_metrics(user+metric_date)·problem_solve_time_distribution(problem+persona+measured_at)·user_behavior_metrics(user+metric_name+measured_at). **FK는 §6~§9 DDL `REFERENCES`만 엄격 적용**(activity 4·dialogue 4·assessment 1); hypertable 느슨참조(attempt_event 3컬럼·concept_mastery_history·시계열 전부)·target_concept_id·stuck_at_concept_id·target_university_id는 **FK 아님**. **공유 enum 재사용**: device_enum(user+learning_session)·persona_enum(user 3컬럼+problem_solve_time_distribution) — `create_type=False`로 재생성 방지. 신규 enum 10종(session_type·attempt_mode·event_type·resolution·turn_role·content_type·socratic_strategy·student_intent·assessment_type·mental_phase) downgrade drop. **hypertable 5종**: ORM은 일반 테이블, 마이그레이션 upgrade 끝에 `DO $$ IF EXISTS(timescaledb) THEN create_hypertable(...if_not_exists) END $$`**조건부 가드**(chunk 간격 정본 일치: attempt_event 1d·mastery 7d·daily 30d·solve_time 7d·behavior 7d) — 미설치 PG(이 sandbox·CI)선 NO-OP로 일반 테이블 검증, 확장 환경선 자동 변환. **메인 PG16 증분배포 실검증**: 별도 invocation 3단(problem 3·11→배치1 16·28→배치2 26·38)→downgrade base 0·0→downgrade-1 왕복서 공유 enum 보존(device/persona·subject/source_type 각 1)→`alembic check` "No new upgrade operations" green. **4게이트 green**: black 57·ruff·mypy-strict(53파일, `Mapped[]`·BigInteger autoincrement·복합PK 통과)·pytest **908 passed**(857→+51)·신규 4모듈 cov 100%(291 stmts). **DB 영속 레이어 전 도메인 ORM+마이그레이션 완료**(problem PoC 3테이블+배치1 13+배치2 10 = **26테이블·38enum**, 도메인 모듈 10개[problem+batch1 5+batch2 4] + `_orm_enum` 헬퍼). **후속**: FastAPI 라우터 `get_session` 배선(✅ 아래)·ncic `load_to_postgres`·hypertable 변환은 timescaledb 확장 env서 실검증.
- ✅ **DB-backed HTTP 라우터 결선 (영속 레이어 → HTTP end-to-end)** 완료 (메인 직접, 2026-05-29) — `db.session.get_session`(기존 lazy 세션 인프라)을 FastAPI에 처음 결선. 신규 `whymath_backend/api/`(`__init__`·`concepts.py`) + `create_app`에 `app.include_router(concepts_router)` + **lifespan**(`@asynccontextmanager _lifespan` 종료 시 `dispose_engine()` — 엔진 미생성 시 no-op). **concept 라우터 3엔드포인트**(`/v1/concepts`): POST 생성(`from_schema`→add→commit→`to_schema`, code UNIQUE 충돌 `IntegrityError`→rollback→**409**)·GET 단건(`session.get`, 없으면 404)·GET 목록(`select`+code 오름차순+limit/offset, Query 범위검증). **의존성 패턴**: `SessionDep = Annotated[AsyncSession, Depends(get_session)]`(기본인자 `Depends()`는 ruff **B008**·mypy가 막음 — Annotated 메타데이터가 현행 권장). 트랜잭션 commit/rollback은 **핸들러 책임**(get_session은 세션 열고닫기만 — session.py 계약). **테스트 2층**(L3 app테스트가 provider/cache/queue 가짜 주입하는 패턴 + db모델 테스트가 라이브PG 없이 from/to_schema 왕복만 보는 분담을 미러링): ① **hermetic**(`test_concepts.py`, 9 테스트) — `app.dependency_overrides[get_session]`에 `FakeSession`(get/execute/add/commit/rollback/refresh 모사) 주입, 201/409/404/422·commit/rollback 호출 검증 ② **통합**(`test_concepts_integration.py`, `@pytest.mark.integration` 기본 skip·`WHYMATH_RUN_INTEGRATION=1`로만) — 실 PG16서 POST→GET→중복409→목록 왕복 + lifespan dispose 발화(TestClient 컨텍스트매니저). **메인 실검증**: 로컬 PG16 head 적용 후 통합테스트 1 passed(HTTP→get_session→PG end-to-end 증명, 행 정리는 독립 엔진으로 — asyncpg 루프바인딩 회피). **CI 정합 확인**: backend job은 `working-directory: src/backend`라 `black/ruff .`이 src/backend만(line-length 100)·tests/는 pytest(testpaths)만 — 테스트 파일은 black 기본 88, src는 100. **4게이트 green**: black(59)·ruff·mypy-strict(55파일)·pytest **917 passed**(908→+9)·`api/concepts.py` cov **100%**·TOTAL 99%(`--cov-fail-under=70`). **후속**: 쓰기 더 필요시 PATCH/DELETE·다른 도메인(problem 등) 라우터·페이지네이션 total 헤더.
- ✅ **ncic `load_to_postgres` 구현 (L1 성취기준 → PostgreSQL 적재, data-pipeline Phase 2)** 완료 (메인 직접, 2026-05-29) — `data_pipeline/ncic/load.py`의 stub(NotImplementedError)을 실구현. **설계 분기 해소**: `AchievementStandard`(NCIC 성취기준 원자료)는 모델 docstring대로 **전용 `achievement_standards` staging 테이블**에 적재 — WhyMath v1.0 앱 스키마(concept/problem, backend/alembic)와 *별개*. 성취기준→concept 변환은 후속 'A'(pedagogy 동반)이지 load의 책임 아님. **핵심 제약**: data-pipeline CI는 `[dev]`만 설치(sqlalchemy 없음)·`[postgres]` extra는 optional → ① sqlalchemy import를 `load_to_postgres` *함수 내 지연*(모듈 import는 extra 없이 가능 — write_json/csv 사용자 보호, 미설치 시 RuntimeError 안내) ② mypy는 `ignore_missing_imports=true`라 통과 ③ `_to_async_dsn`(postgresql://→+asyncpg) 순수 헬퍼. **구현**: SQLAlchemy Core `Table`(14컬럼, code PK) + `create_all`(멱등 — data-pipeline엔 alembic 없으니 loader가 staging 테이블 소유) + code 기준 dedup(마지막 우선, 단일 INSERT ON CONFLICT 중복행 오류 방지) + `pg_insert().on_conflict_do_update`(upsert=True)/`do_nothing`(False), 빈 입력은 연결 없이 0. **테스트**: stub 테스트 대체 — hermetic 3(빈입력 0·_to_async_dsn 2케이스, sqlalchemy import 불요라 CI-safe) + **통합**(`test_load_postgres_integration.py`, `@integration`·`importorskip("sqlalchemy")`·PG 도달성 skip) — 전용 테스트테이블서 INSERT→upsert UPDATE→do-nothing 왕복 후 DROP. **통합 게이트 신설**: data-pipeline conftest에 `WHYMATH_RUN_INTEGRATION` 게이트 추가(backend와 동일 — 마커는 등록돼 있었으나 첫 통합테스트라 게이트가 없었음). **메인 실검증**: 로컬 PG16서 통합테스트 1 passed. **4게이트 green**(CI 방식 src/data-pipeline): black(9)·ruff·mypy-strict(9파일)·pytest **103 passed**(101→+2, net)·1 skipped(통합)·load.py 70%·TOTAL 82%(`--cov-fail-under=70`). **혼합경로 black 함정 재확인**: `black . ../../tests`처럼 트리 혼합 호출 시 공통루트(설정 없음·기본 88)로 기존 100-포맷 파일 대량 오변경 → 트리별 단독 호출 필수. **후속**: ncic `__main__`에 load CLI 옵션 배선(✅ 아래)·실 NCIC 크롤 데이터 적재·achievement_standards→concept 매핑('A', ✅ 아래 시드 단계).
- ✅ **ncic CLI `load` 커맨드 + 개념 그래프 시드 생성기(concept_graph)** 완료 (메인 직접, 2026-05-29) — 두 후속을 한 세션에 처리. **(1) ncic `load` CLI**(`ncic/__main__.py`): `standards.json`→`load_to_postgres` 배선(`--dsn`/`WHYMATH_DATABASE_URL`·종료코드 DSN없음1·JSON없음2·extra없음4·`--upsert/--no-upsert`), CliRunner hermetic 8테스트(monkeypatch)·로컬 PG16 end-to-end(2행·멱등) 실검증. **(2) `data_pipeline/concept_graph/`** — `docs/data/concept_graph.md`(정본·"미구축") 단계 3(시드)+단계 6(검증) 구현. **설계 핵심**: 개념 그래프는 *자체 구축 자산*이라 자동화 가능한 건 **시드 생성뿐**(노드·엣지 *작성*은 전문가 단계 4, M1.3 게이트). 그래프 모델은 **Neo4j 타깃**(`concept_id=UC.<domain>.<topic>.<slug>`)이라 backend PG `concept`(code=CAL-INT-)와 **별개**. 모듈: `models.py`(`Concept`·`ConceptEdge` Pydantic — `schemas/v1.1/{concept,edge}.schema.yaml` 충실, UC ID 패턴 validator·name 한·영·일 비공백·relation 7종 str-Enum[정본 산문 '6종'은 stale, 열거가 7]·strength[0,1]·evidence min_length=1·`SOURCE_CITATION` NCIC 승계)·`seed.py`(성취기준→후보 노드 결정론적 UC ID[`build_concept_id`: 과목약칭맵+해시폴백, NCIC 코드 기반 멱등]+parent_codes→prerequisite 후보 엣지, CSV 빈칸[표기·strength·evidence는 전문가], **statement 본문 미복제** 법적)·`validate.py`(§5 그래프 invariant: prerequisite 사이클=error·역쌍/고립/dangling/학년단조성=warning, `ncic/validate.py` 리포트 패턴)·`__main__.py`(`seed`·`validate`[채운 CSV→strict 파싱]·`load`[Neo4j 후속 Phase 가드, exit 3]). **재사용**: `AchievementStandard(Collection)`·`parse_standard_code`·`write_csv`/sidecar·typer 패턴. **end-to-end 실검증**: `seed --domain-filter 미적분`→후보 2노드·1엣지 CSV(UC ID·빈칸·statement 미복제 확인)→`validate` 미작성 seed서 파싱실패 3건 exit1. **4게이트 green**(src/data-pipeline): black(14)·ruff·mypy-strict(14)·pytest **192 passed**(111→+81)·1 skip·concept_graph cov 91~100%·TOTAL 88%. **후속(범위 밖)**: Neo4j 드라이버 의존성+적재(단계 7, 전문가 CSV·neo4j env 선행)·전문가 노드 작성(단계 4)·backend PG concept(CAL-)↔그래프 UC ID 정합.
- ✅ **Problem 도메인 HTTP 라우터** 완료 (메인 직접, 2026-05-29) — concept 라우터(`api/concepts.py`) 패턴을 핵심 콘텐츠 엔티티 problem에 그대로 확장. 신규 `api/problems.py`(POST 생성·GET 단건[404]·GET 목록[최신순 created_at desc + problem_id 안정정렬·`subject` 선택 필터·limit/offset]) + `create_app`에 `app.include_router(problems_router)` + `api/__init__` export. `external_id`/`slug` UNIQUE 충돌→**409**(IntegrityError 롤백). **경계**: 본문 보유 금지 등 출처별 불변식은 schema.Problem after-validator가 이미 강제 — 라우터는 검증 통과 모델만 영속화. **필수 필드 주의**: Problem은 source_type·curriculum_version·valid_from_year·subject **+ unit_codes**(min 필수)이라 테스트 빌더에 unit_codes 포함. **테스트 2층**(concept과 동형): hermetic 11(`test_problems.py`, FakeSession·201/409/404/422·subject enum 검증·pagination) + 통합(`test_problems_integration.py`, `@integration`·PG 도달성 skip — POST→GET→subject 필터[미적분 매칭·기하 제외]→cleanup). **메인 실검증**: 로컬 PG16 head서 통합테스트 1 passed(subject 필터 SQL 실동작 확인). **4게이트 green**: black(60)·ruff·mypy-strict(56)·pytest **928 passed**(917→+11)·15 skip·`api/problems.py` cov **100%**·TOTAL 99%. **후속**: 쓰기 확장(PATCH/DELETE)·problem_step/relation 중첩 노출(✅ 아래)·by-slug 조회·타 도메인 라우터.
- ✅ **중첩 read 엔드포인트 — problem steps/relations · concept edges** 완료 (메인 직접, 2026-05-29) — 부모 엔티티의 하위 구조를 read로 노출(Polya 풀이단계·문항관계·개념 의존그래프). 신규 파일 없이 기존 라우터 확장: `api/problems.py`에 `GET /v1/problems/{id}/steps`(step_order 순)·`/relations`(outgoing=parent_problem_id), `api/concepts.py`에 `GET /v1/concepts/{id}/edges`(outgoing=from_concept_id, `idx_concept_edge_from` 활용). 공통 패턴: 부모 `session.get`→없으면 **404**, 자식 `select`+FK필터+안정정렬→`to_schema` 루프. 세 ORM(`ProblemStep`·`ProblemRelation`·`ConceptEdge`)의 기존 `to_schema` 재사용 — 새 변환 0. **read 전용·outgoing만·페이지네이션 없음**(자식 소량 가정). **경계 메모**: concept_edge는 backend PG 테이블 — data-pipeline Neo4j concept_graph(UC ID)와 별개(다른 저장소·키공간). **user 도메인은 제외**(인증 부재+미성년자 PII 금기 — 탐색서 확인, 인증 프레임 선행). **테스트 2층**: hermetic +9(`test_{problems,concepts}.py`에 TestSteps/TestRelations/TestEdges — FakeSession 재사용[get_map=부모·list_rows=자식]·200/404/422/빈[]·관계타입·엣지방향 검증) + 통합 +2(`@integration` — 독립 엔진으로 부모+자식 직접 적재[step 2건 역순삽입→정렬확인·edge a→b 방향]→하위 GET→cleanup). **메인 실검증**: 로컬 PG16 head서 API 통합테스트 4종(CRUD 2+중첩 2) passed — step_order 정렬·엣지 outgoing 방향·404·빈[] 실동작 확인. **4게이트 green**: black(60)·ruff·mypy-strict(56)·pytest **937 passed**(928→+9)·17 skip(+2 통합)·`api/{concepts,problems}.py` cov **100%**·TOTAL 99%. **후속**: 쓰기 확장(PATCH/DELETE)(✅ 아래)·역방향/양방향 관계·자식 페이지네이션·by-slug 조회·user 도메인(인증 선행).
- ✅ **PATCH/DELETE — concept·problem CRUD 완성** 완료 (메인 직접, 2026-05-29) — 두 도메인에 부분수정·삭제 추가. **PATCH** `/v1/{concepts,problems}/{id}`: 부분 dict 본문 → 기존 행 `to_schema().model_dump()`에 병합 → PK는 경로 고정 → **schema 재검증**(불변식 유지: Problem 본문보유금지 등) → `session.merge`(PK 기준 갱신) → commit. 없으면 404·병합 결과 위반(미정의 필드 extra=forbid·잘못된 값) 422·UNIQUE 충돌 409. **DELETE** `/v1/{...}/{id}`: `session.delete`+commit → **204**(`Response`), 없으면 404, FK 참조(엣지·매핑·단계·관계) 있으면 IntegrityError→**409**(가짜 cascade 금지 — 참조 있으면 삭제 거부). **동시성 last-write-wins**(낙관적 락 미적용 — Concept엔 updated_at 없음, 후속). 422 detail에 `errors[{loc,msg}]` 동봉(직렬화 안전). **테스트**: hermetic +16(`FakeSession`에 `delete`/`merge` 추가 — TestPatch/TestDelete 각 도메인: 200수정·404·422[enum·미정의필드]·409[merge conflict]·204삭제·404·409[FK]; **PATCH 법적 불변식 재검증** — 본문보유 문제를 평가원으로 PATCH→422) + 통합 +2(`@integration` — POST→PATCH[부분수정·기존필드 보존]→GET[영속확인]→DELETE 204→GET 404 실 PG 왕복). **메인 실검증**: 로컬 PG16서 API 통합테스트 6종(CRUD·중첩·PATCH/DELETE × 2도메인) passed. **4게이트 green**: black(60)·ruff·mypy-strict(56)·pytest **953 passed**(937→+16)·19 skip(+2 통합)·`api/{concepts,problems}.py` cov **100%**·TOTAL 99%. **concept·problem 라우터 CRUD 完**(POST·GET단건·GET목록·중첩 read·PATCH·DELETE). **후속**: 낙관적 락(updated_at 버전스탬프)·역방향 관계·자식 페이지네이션·by-slug 조회·user 도메인(인증 선행).
- 📋 **다음 세션 후보 (서로 블로킹 없음)** — ① **M1.2 라이브 연동**(S1~S5 *완료*; 잔여: 비용/지연 실측 보정·프롬프트 캐싱·thinking/effort 튜닝, 모두 라이브 키 보정 후속 §H#4) ② **빌드타임 사전생성 파이프라인**(*슬라이스 1~8·B 완료 — Schema 구현 정본 全(v1.0 8도메인 + v1.1 2종) 完; DB 매핑 PoC(인프라+Problem) + 배치1(5도메인) + 배치2(4도메인·hypertable 조건부가드) = **전 도메인 ORM·마이그레이션 完 + DB-backed HTTP 라우터(concept) 결선·lifespan dispose + ncic load_to_postgres(L1→PG 적재) 完** — 위 ✅; 잔여: hypertable 변환 timescaledb env 실검증·타 도메인 라우터·쓰기 확장(PATCH/DELETE)·실 NCIC 데이터 적재·개념그래프 Neo4j 적재(전문가 CSV 선행)* — 위 ✅ 참조; B=SymPy 검증. 후속: A(성취기준→스펙, pedagogy 동반 — 개념그래프 시드는 ✅, 전문가 작성 단계 4 잔여)·DB 내구화·PRM/LLM-judge·Max 인제스트 포맷·에빅션 정책) ③ **(Kiki·Phaiakes9) per-call-site 크기 재실측**(`ollama pull bge-m3` → `quality_eval.py` @`127.0.0.1` GPU — extract 임베딩 의미매칭 포함) ④ **클라우드 티어 비용/지연 실측 보정**(03a §H#4 잔여 — 경로·provider는 S5 완료, 실측 임계값만 남음) ⑤ **24/7 서버 운영 설계**(Phaiakes9 상시 가동)
- 📋 **Phaiakes9 카탈로그 cosmetic 정리** (별도 PR) — README.md 7군데, SETUP_GUIDE.md 1군데, 주석 4군데. 코드 동작 영향 없음, 문서 일관성만
- 📋 **Phaiakes9 systemd unit `ProtectSystem=full` 완화** (별도 PR) — `failed to persist model recommendations snapshot ... read-only file system` 경고 해소. `ReadWritePaths=/usr/share/ollama` 추가
- ✅ 완료: PRD v1.1 정합성 정렬(단계 1~5, `fd23115`~`b8d6d3d`) / CI 툴체인 점검(`3b9ff72`) / 곁다리 2건(`df03eaa`) / **NCIC PDF crawl baseline**(629건 추출, 5% 검수 완료, 2026-05-15 결정 로그) / **`main` 보호 규칙 적용**(2026-05-15, PR #1로 CI 첫 가동·status check 등록) / **M1.0a Phaiakes9 1차 셋업** (2026-05-15, NucBox EVO-X2 + WSL2) / **M1.1 CPU baseline** (qwen2-math:7b, 12.62 tok/s @ concurrent 1) / **M1.1 GPU 가속 활성화** (2026-05-16, Windows Ollama 경유 DirectML, qwen2-math:7b 32.63 tok/s + qwen3.5:27b 9.22 tok/s, CPU 대비 2.6x — 옵션 A1 채택) / **M1.1 fast tier 후보 측정** (2026-05-19, qwen2-math:1.5b GPU 124.25 tok/s @ c=1, p50 1010ms — L3 SLA 게이트 PASS, fast/mid/quality 3단계 라인업 결정) / **인터페이스 정렬·main 보호 데드락 정정·Max=빌드타임/API=런타임 결정** (2026-05-20, PR#4) / **L3 라우터 M1.2 구현** (2026-05-20, `whymath_backend/l3` 결정로직+타입 인터페이스+백엔드 CI 잡, PR#5) / **FAST tier 품질 검증 종결 + 태스크 패밀리 라우팅 확정** (2026-05-20, 결론: *수학=`qwen2-math`·NLP=`qwen2.5`* — 수학모델로 NLP는 7b조차 0%; 하니스(`<ANSWER>`·temperature=0·임베딩 의미매칭·코드추출) + 03a 축3 `ModelFamily`(§0.2·A.0·C.0·§H 후속8~12) + 라우터 코드 family 축·호출지점별 크기, PR#6~#14. 설계·인터페이스·코드·하니스 완전 정합)

### 완료된 마일스톤
- 2026-05: 7계층 아키텍처 확정
- 2026-05: 기술 스택 확정 (Flutter + FastAPI + PostgreSQL + Phaiakes9)
- 2026-05: Phase 진입 순서 확정 (메타인지 사고력 → 학교 진도 → 수능 → 영재 → B2B)
- 2026-05-14: GitHub 레포 `doldori7/WhyMath` (Private) 생성 및 첫 푸시 완료
- 2026-05-28: MathScope PRD v1.2 재검토 — 7계층·로드맵 재정렬 (공유 코어 + 고3 우선, 법적 안전조합 콘텐츠) — 결정 로그 참조

### 미해결 의사결정
- [ ] 수학 교육 도메인 파트너 영입 (M1.3 게이트로 *지연 확정* — 트랙 미정)
- [x] ~~첫 진입 학년~~ → **공유 메타인지 코어 + 고3 수능 우선 노출** (2026-05-28 PRD v1.2 재검토; 2026-05-13 "고1 내신"은 *폐기 아님, 노출 순서 재배치* — 공유 코어가 고1도 서빙). 결정 로그 참조
- [ ] 벡터 DB: ChromaDB 유지 vs Qdrant 전환 (PRD v1.1 채택으로 발생 — 정렬 단계3 L1/L5에서 결정)
- [x] ~~스키마 통합 정본화~~ → **Schema v1.0 = 구현 정본** (v1.1 YAML 대체, `curriculum_entry`·`textbook_mapping`만 이식; source_type/license 법적 교정). 실 마이그레이션은 후속 (2026-05-28 속편 결정 로그)
- [x] ~~OCR 스택~~ → **PaddleOCR + Qwen3-VL 하이브리드** 확정 (2026-05-28, Mathpix 대체; 한국어 정확도 L5 전 Phaiakes9 실측 필요). 결정 로그 참조
- [ ] 사단법인·재단·법인 형태
- [ ] Cambridge MMP/NRICH 라이선스 협상 시작 시점

---

## 🧭 핵심 결정 로그 (시간 역순)

### 2026-05-28 (원문검증): 저작권 가이드 v2.0·MathScope v4 수령 — 법적 서술 검증·데이터 백본 확증
**컨텍스트**: Kiki가 원문 2종 추가 제공 — **저작권 종합가이드 v2.0**(2026-05-27, .docx→텍스트 추출)·**MathScope v4**(데이터 카탈로그, 2026-05-26). 앞서 *합성*으로 커밋한 법적 서술(licensing_safety·CLAUDE)을 원문 대조 검증.
**검증 결과 — 전부 일치 ✓ (환각 0)**: §32 단서(영리 시험문제 금지→EBS·KICE·시도교육청·KMO 영리 차단)·§136·§140(영리 비친고죄, 합의해도 직권기소)·2024.8 대법원(KICE 사용료 의무)·공공누리 AI유형(2026-01-28)·AIHub 영리 명문허용·**한 줄 결론 "NCIC+AIHub+NuminaMath(Apache)+PRM800K(MIT)+PhET(CC BY)"**·NCIC §7 — 커밋 서술과 정확히 일치.
**원문 보강(licensing_safety 반영)**: §93(DB제작자권)·§125-2(법정손배 1건당 최대 5천만)·**SA(ShareAlike) 함정**(AI 가중치 SA 전염 위험 → AoPS·LibreTexts ✅→⚠️ 교정, Khan NC+SA 완전격리)·**SA 우회**(Feist·대법원 2000다61664 — 사실만 추출+자체생성)·AIHub 4조건(출처표시·국외반출·재판매금지·환수)·AI유형 nuance(모델 상업이용 허용)·**NCIC 성취기준 §7(무제한) ↔ 해설서 공공누리 2유형(NC) 구분**·등급 A+/A/A-/B/C/D/E.
**데이터 백본 확증(MathScope v4)**: 실제 수집 = **A-/A/A+ 21종·~4M 레코드, B/C/D/E 0건** — EBS·평가원·검정교과서 *미포함*. 재검토 "법적 안전조합" 교정은 *이미 데이터 엔지니어링이 실행 중인 현실*이었음(추가 A+: DLMF·Metamath, A: GSM8K·MATH·NuminaMath CoT/TIR·OpenMathInstruct 등).
**신규 발견 — 제3의 스키마**: MathScope v4 `schema_v2.sql`(6테이블+3뷰: dataset_licenses·curriculum_standards·curriculum_alignments·problems·solution_steps·student_attempts + license 뷰)은 *L1 데이터/라이선스 거버넌스* 초점 → 앞서 정본화한 **Schema v1.0(앱 8도메인)과 상보적**(problems/solution_steps/curriculum 중복은 통합 필요). Schema v1.0=앱·런타임 정본 유지, schema_v2.sql=L1 학습데이터/다국가 교육과정 거버넌스 레이어.
**적용**: `docs/legal/copyright_guide_v2.md`·`docs/data/dataset_catalog_v4.md` 레포 보존; licensing_safety.md 보강(SA 교정·§93/§125-2/§140·등급체계·AIHub 4조건·v4 백본). **2022 개정 보고서 수령·보존**(`docs/data/curriculum_2022_revision.md`) — 중3·고3만 2015 잔존(2026-05)·중학 5→4영역·고1 공통수학1·2·고3 미적분Ⅱ 등 확인, 기존 `curriculum_version` 정책 확정. (5개 원문서 전부 도착했었음 — 초기 배치 폴더 미안내로 늦게 발견; *정정*: 앞서 "미수령"은 오류). **후속**: schema_v2.sql↔v1.0 통합·THIRD_PARTY_LICENSES 디렉토리·license_monitor cron·**별책8 본문 264p**(성취기준 해설·핵심 아이디어, §7 무제한) L1 데이터 보강 시 재수집.

### 2026-05-28 (OCR): OCR 스택 = PaddleOCR + Qwen3-VL 하이브리드 (Mathpix 대체)
**컨텍스트**: CLAUDE.md 기술스택(Mathpix) ↔ PRD v1.2 §8.1(PaddleOCR+Qwen3-VL 하이브리드) 충돌 — 재검토 후속의 마지막 미해결 결정.
**결정(Kiki)**: **PaddleOCR + Qwen3-VL 하이브리드(로컬, PaddleOCR fallback)** 채택, Mathpix 대체. 로컬 LLM 풀에 **Qwen3-VL**(멀티모달·그래프 개형) 추가.
**근거**: 의사결정 우선순위 **#1 학생안전·#2 법적**(미성년자 손글씨·풀이 이미지 *외부 전송 회피* → 로컬 처리)·**#6 비용**(무료 vs Mathpix per-call) + Kiki "로컬 LLM 우선(Phaiakes9)" 선호 + PRD v1.2 자체 채택과 정합. FR-002(그래프 멀티모달)·FR-011(손글씨 OCR)의 구현 스택.
**리스크**: 한국어 손글씨·수식 인식 정확도 *미검증*(PRD §11.2 高리스크) → L5 착수 전 Phaiakes9 실측 벤치마크 필수(목표 90%, PRD §12.3). 미달 시 PaddleOCR fallback·부분 Mathpix hedge 재검토.
**적용**: CLAUDE.md 기술스택(OCR row·로컬 LLM row·L5 다이어그램·변경 각주) 갱신. **후속**: Qwen3-VL Phaiakes9 배포·한국어 수학 OCR 정확도 벤치마크(PRD 액션 §12.2).

### 2026-05-28 (속편): PRD v1.2·Schema v1.0 원문 수령 — 정합 확인·스키마 정본화·P0 FR 계층 매핑
**컨텍스트**: 재검토(아래 본편)는 외부 5문서를 *합성 분석*으로만 다뤘으나, Kiki가 **PRD v1.2 원문**과 **DB Schema v1.0 원문**을 레포에 제공. 원문 대조로 재검토 주장을 검증하고, 보류했던 페르소나·FR 매트릭스·스키마 통합을 진행.
**정합 확인(원문 대조)**: 재검토 주장 전부 일치 — FR **31개(P0 14·P1 12·P2 5)**·**페르소나 5종**·로드맵 **v1.0~v3.0**·**MVP=페르소나 A(고3)**·시그니처 패턴(조건나열 FR-001·합성함수 FR-003·귀납수열 FR-004). PRD **§12.4 #3가 "평가원·EBS·AIHub만으로 충분한가?"를 미해결로 남김** → 재검토의 저작권 충돌 전제 확증.
**페르소나 5종(PRD §3) ↔ 노출 순서**: A 일반고 고3(MVP·시장최대 52만)·C 검정고시 N수(v1.5·충성·수학의존 100%)·D 학종 고2(v1.5·세특/자유연구 차별화)·B 자사고 N수(v2.0·결제최대·경쟁치열)·E 홈스쿨링 영재(v2.0·시장작음·가치최대). → 재검토 "공유코어+고3 우선"과 정합.
**스키마 정본화 결정**: **Schema v1.0(8도메인 ~25테이블, PostgreSQL+TimescaleDB+ChromaDB, DDL·인덱스·hypertable·ENUM 완비) = 구현 정본**. `schemas/v1.1`(9 YAML) = 개념 초안으로 *대체*. 단 v1.0에 없는 2개 **보존·이식**: ① `curriculum_entry`(NCIC 성취기준 1급 — L1 파이프라인 산출물, "콘텐츠는 성취기준 코드 1개+ 태그" 원칙) ② `textbook_mapping`(교과서 *구조 메타* 매핑 — 자동 커리큘럼 정렬, 법적 안전). v1.1 나머지는 v1.0이 흡수(problem·concept·edge→concept_edge·student_profile→user_profile·mastery_state→concept_mastery_history·hint/solution_path→problem_step).
**스키마 법적 교정(필수·정본에 적용)**: v1.0의 `source_type_enum`(평가원·EBS·교과서)·`license_enum`(PUBLIC_DOMAIN="평가원 공개"·EBS_LICENSED)·`generation_type=ORIGINAL`은 *본문 저장* 전제 → 저작권 가이드 v2.0과 충돌. **교정**: 평가원·EBS·교과서 *본문 미보유*; `content_provenance.original_reference`에 **구조 메타(단원·코드·문항번호)만**; `problem.question_text`는 **WHYMATH_GENERATED 동등문제만** 채움; 지배 license=`WHYMATH_GENERATED`; `ORIGINAL`·`EBS_LICENSED`는 공식 제휴(Phase 3+) 전까지 미사용. (`content_provenance.generation_type`의 VARIANT/FULLY_GENERATED + `generation_log`가 `l3/pregenerate` 동등문제 엔진의 DB 모델)
**P0 14 FR → 7계층·빌더빌리티(법적 교정 반영)**:
| FR | 기능 | 계층 | 비고 |
|---|---|---|---|
| 001 | 조건 나열형 파서 | L3·L4 | **핵심 모트**, 신규 |
| 003 | 합성함수 케이스 분류 | L3·L4 | **핵심 모트**, 신규 |
| 004 | 귀납적 수열 추적 | L3·L4 | **핵심 모트**, 신규 |
| 009 | AI 변형 모의고사 생성 | L3 | `l3/pregenerate` 확장(모트) |
| 007 | ~~EBS 변형 DB~~ | L3 | **동등문제 자체생성으로 재정의**(EBS 본문 미사용) |
| 005 | 자연수 답 변환 사전 | L3 | 신규(소) |
| 006 | 단원융합 개념그래프 | L1·L2 | concept_edge+ChromaDB(DB 정본화) |
| 008 | 평가원 가중치 분류 | L1 | exam_authority_weight(메타만, 본문 X) |
| 013 | 인공지능수학 콘텐츠 | L1 | 콘텐츠 |
| 014 | 내신+수능 통합 코칭 | L6 | 공유 코어 위 모드 |
| 010 | 1년 사이클 자동계획 | L6·L2 | 신규 |
| 012 | 실전 모의고사 시뮬 | L5 | UX |
| 002 | 그래프 멀티모달 인식 | L5·L3 | **OCR 스택 결정 의존**(Qwen3-VL) |
| 011 | 풀이 손글씨 OCR | L5 | **OCR 스택 결정 의존** |
*1인 가드*: 핵심 모트(001·003·004·009 + L4 소크라테스) 최우선 → DB 정본화(006·008) → 멀티모달/OCR(002·011, 스택 결정 후) → 나머지.
**적용**: `docs/strategy/prd_v1.2.md`·`schemas/v1.0/schema_v1.0.md` 레포 반영(원문 보존). **후속**: 스키마 정본 *실 마이그레이션*(alembic, DB 미구현 상태)·curriculum_entry/textbook_mapping 이식 DDL·OCR 스택 결정·CLAUDE.md 페르소나 5종 1줄 반영.

### 2026-05-28: MathScope PRD v1.2 재검토 — 7계층·로드맵 재정렬 (공유 코어 + 고3 우선, 법적 안전조합 콘텐츠)
**컨텍스트**: 5종 신규 문서 입력(레포 외부) — **PRD v1.2**(입시특성 100→FR 31·페르소나 5종·버전 v1.0~v3.0), **DB Schema v1.0**(8도메인 SQL), **2022 개정 교육과정 보고서**, **MathScope v4**(데이터셋 21종), **저작권 종합가이드 v2.0**. 현 7계층/Phase 틀과 대조(갭분석)한 결과 두 충돌이 핵심: ① 저작권 가이드 v2.0이 **EBS·평가원 영리사용 금지**(저작권법 §32 단서·§136·§140·2024 대법원)로 못박아 PRD/ROADMAP의 *EBS·평가원 기출 직접 활용* 전제가 무효 ② **MVP 타깃 분기**(현 ROADMAP=고1 내신 ↔ PRD v1.2=고3 수능). PRD 범위 폭발(FR 31·페르소나 5·멀티모달·학종)이 1인 capacity·얇은 코드(L2·L4·L6·L7 미구현, DB 미구현)와 충돌.
**결정(Kiki, 3택)**:
1. **MVP 앵커 = 공유 코어 + 고3 우선 노출**. 7계층 메타인지 코어는 *단일·공유*(고1 내신도 같은 코어가 서빙)이되, **첫 시장 노출 페르소나 = A(고3 수능)**, 킬러 30번 *자체 생성 동등문제*가 wedge. → 2026-05-13 "고1 내신 확정"은 *폐기 아님, 노출 순서 재배치*로 갱신.
2. **콘텐츠 = 법적 안전조합**. 백본=NCIC 성취기준(§7)·공공누리 AI유형(2026-01)·AIHub 수학셋(영리허용). LLM 학습/예시=NuminaMath(Apache)·PRM800K(MIT)·PhET(CC BY)·Metamath(CC0)·Lean. **EBS·평가원 = 구조 메타데이터(단원·코드·문항번호)만 사실인용 + 자체 생성 동등문제로 본문 대체**. → PRD FR-007(EBS 변형)·#11(EBS 연계)·"평가원 기출 P0"를 *동등문제 자체생성*으로 재정의. 이미 구축한 `l3/pregenerate`(빌드타임 사전생성)+SymPy 게이트가 그 엔진.
3. **산출물 = 갭분석 + 수정 프레임 + 로드맵 재정렬**(FR 31 P0 매트릭스·스키마 v1.0↔v1.1 통합 상세는 후속 슬라이스).
**재정렬된 7계층 ↔ PRD v1.2 (MVP=공유코어, 첫 노출 고3)**:
- L1: NCIC ✅ + AIHub/동등문제 코퍼스 + 개념그래프 DAG + **DB 정본화 필요**.
- L2: 미구현 → BKT/IRT 최소 숙달추정(MVP), DKT·정서신호 후속.
- L3: 라우터·사전생성 ✅ → **동등문제 생성·다중풀이·조건파서(FR-001)·합성함수/귀납수열(FR-003/004)** = 핵심 모트.
- L4: 프롬프트만 → **Polya·소크라테스 코칭 엔진 코드화**(MVP 핵심).
- L5: 모바일 0 → Flutter MVP(고3 30번·손글씨 OCR)·서버 DB·인증. OCR 스택(Mathpix vs PaddleOCR+Qwen3-VL) 결정 후속.
- L6/L7: 후속(L6 수능 단일모드 우선, L7 Phase 3+).
**수정 로드맵 (PRD 버전 ↔ Phase)**: Phase 1=PRD v1.0 코어(고3 wedge), Phase 2=v1.5(검정고시·학종 세특·결제), Phase 3=v2.0(2028 수능·수리논술), Phase 4/5=v3.0(영재·면접·글로벌). *1인 가드*: Phase 1은 P0 FR 14 중 **핵심 모트 우선**(조건파서·시그니처 패턴·동등문제·소크라테스); 멀티모달·세특 후순위.
**근거**: 의사결정 우선순위 #2(법적준수)>#6(비용)이 EBS/평가원 회피를 강제. #3(교수학)·#4(학습효과)는 공유 메타인지 코어로 충족(고3 노출은 GTM 선택). 2022 교육과정은 이미 반영(중3·고3 2015 병행→`curriculum_version` 유지).
**적용 범위(갱신 완료)**: ROADMAP.md(Phase 1 정의·콘텐츠 전략·PRD 버전)·docs/data/licensing_safety.md(가이드 v2.0 결론·EBS·평가원 영리금지·동등문제 정책·안전조합 allowlist)·CLAUDE.md(EBS·평가원 영리금지 금기·콘텐츠 안전조합 원칙). **후속(원문·결정 필요로 보류)**: CLAUDE.md 페르소나 5종 명문화(PRD v1.2 원문 필요 — 현재 A/C/D만 확보, B/E 미상이라 *날조 금지*)·schemas v1.0↔v1.1 통합 정본(Schema v1.0 SQL 원문 필요)·FR 31 P0 매트릭스(PRD 원문 필요 — 현재 FR-001/003/004/007만 확보)·OCR 스택 결정(Mathpix vs PaddleOCR+Qwen3-VL, Kiki 결정).
**리스크**: 자체 동등문제의 킬러 난이도 재현·검수(SymPy는 산술만→PRM/사람검수 필요)·법적 안전조합만으로 MVP 콘텐츠 충분한지(변호사 검토 권장)·1인 6개월 capacity.

### 2026-05-20: L3 라우팅에 *태스크 패밀리 축* 도입 — 수학(qwen2-math) vs NLP(qwen2.5), 03a 확정(B)
**컨텍스트**: FAST tier 품질 검증(03a §H 후속1)을 Phaiakes9 실측으로 진행한 결과, "1.5b vs 7b *크기*"가 아니라 **모델 패밀리가 태스크와 안 맞은 것**이 근본 원인으로 드러남(아래 *FAST tier 품질 평가 하니스* 로그의 재설계(A) 참조). NLP 호출지점(extract/translate/match)을 수학 특화 `qwen2-math`로 돌리면 7b조차 0%, 일반 모델 `qwen2.5`로 바꾸니 정상화. 이를 *설계*로 확정(B 트랙).
**결정**:
- L3 LOCAL 라우팅에 **축3 = 모델 패밀리**(`ModelFamily{MATH, GENERAL}`) 도입. 로컬 실제 모델 = (패밀리 축3) × (크기 축2). 패밀리는 *태스크 유형*이 결정(NLP→GENERAL, 수학→MATH), 크기/SLA는 그 안에서.
  - MATH=`qwen2-math`(1.5b/7b) · GENERAL=`qwen2.5`(3b/7b) · QUALITY=`qwen3.5:27b`(패밀리 무관 상위, 비동기). 클라우드(CLOUD_*)엔 미적용.
- **5 호출지점 확정(실측)**: ①extract→GENERAL/MID(qwen2.5:7b)·②깊이추론→MATH/MID·③translate→GENERAL/MID(qwen2.5:7b)·④match→**GENERAL/FAST(qwen2.5:3b)**·⑤검증→QUALITY(27b·async)·산술→MATH/MID(qwen2-math:7b).
- 03a 갱신(§0.2·§A.0 매트릭스·§B.2·§C.0 패밀리 결정·§G `local_family`·§H 후속), 03·llm-architect.md 모델 풀 최소 동기화.
**근거(2026-05-20 실측, GPU 127.0.0.1, temperature=0)**:
- NLP@수학모델=0%(7b도) ↔ NLP@qwen2.5: match 3b **100%**·translate 7b **75%**(3b 50%). 산술@qwen2-math: 7b 100%·1.5b 87.5%.
- 호스트 교훈: `172.17.112.1`=WSL2 CPU(속도만), `127.0.0.1`=Windows GPU. temperature=0으로 실행 변동 제거.
**적용 범위**:
- 문서: `03a`·`03_content_generation.md`·`llm-architect.md`(설계·인터페이스).
- **후속(03a §H 8~11)**: (8) **✅구현(2026-05-20)** extract 임베딩 의미매칭(`set_f1_semantic`·Ollama `bge-m3` 코사인·threshold 0.6·exact 폴백) — 동의어 인정(검증: '다항식 전개'↔'다항식의 곱셈' semantic F1 0.8 vs exact 0.4); (9) **✅구현(2026-05-20)** match 코드추출 채점(`extract_unit_code`·`GRADER_CODE`) — 모델이 후보 주제명 echo('10수학02 (방정식과 부등식)')해도 코드만 매칭; (10) **✅결정(2026-05-20)** 산술 → MID 확정(정확도 우선, ~1/8 오답 FAST 부적합·DELTA 0.07 유지·03a §H#10); (11) **✅구현(2026-05-20)** 라우터 코드 family 축(`ModelFamily`·`local_family`·불변식4·`_decide_family`·`LOCAL_MODEL_MATRIX`·cache_key/langfuse family, llm-architect.md 인터페이스와 일치, 135 테스트·커버리지 100%). (12) **✅구현(2026-05-20)** `_decide_local_tier`를 §C.2 9규칙으로 확장 — GENERAL 호출지점별 크기 분기(④match→FAST, ①extract·③translate→MID) 반영(검증: extract→GENERAL/MID·match→GENERAL/FAST·translate→GENERAL/MID, 135 테스트·커버리지 100%). **§H 후속 8~12 전부 완료** — FAST tier 검증·태스크 패밀리 라우팅 트랙 종결(라우터 코드가 03a/llm-architect 설계와 완전 일치).
**상태**: 확정(2026-05-20). 태스크 패밀리 라우팅을 03a 정본화. FAST tier 검증 여정 종료(결론: *수학≠NLP, 패밀리별 모델*). 잔여는 §H 후속.

### 2026-05-20: FAST tier 품질 평가 하니스 구축 — 1.5b vs 7b 결정적 채점 (03a §H 후속1, 실측은 Phaiakes9)
**컨텍스트**: 03a §H 후속1 "FAST(1.5b)가 7b 대비 품질 차이가 충분히 작은지 측정 → 차이 크면 ①③④ 일부를 MID 승급(C.2 조정)". 실제 모델 실행은 Phaiakes9(Ollama·GPU)에서만 가능하므로(이 컨테이너엔 모델·GPU 없음), 이번엔 *하니스(데이터셋+채점기+러너+테스트)* 까지 만들고 실측은 Kiki가 Phaiakes9에서 수행한다. 채점은 *결정적(프로그램)* — LLM-as-judge 아님. llm-architect 위임 후 메인이 4게이트 독립 재검증.
**결정**:
- `infra/phaiakes9/benchmark/`에 `bench_latency.py`(지연 벤치) 자매 도구 추가(stdlib만·ollama lazy·`_OllamaClientProtocol` 추상화 → 테스트는 가짜 클라이언트 주입):
  - `fast_tier_eval.json`: 자작 CC0 33항목 — extract 9(개념추출)·translate 8(정규화)·match 8(개념ID)·산술 8.
  - `quality_eval.py`: 채점기 `set_f1`(extract 집합 F1)·`exact_match`(translate/match/산술, `normalize_form` 후 정확매칭)·출력 파서(마지막 줄/`ANSWER:` 라벨)·러너(FAST·MID 순차)·집계·결정규칙·CLI(종료코드 0/1/2).
  - `tests/infra/test_quality_eval.py`: 56 테스트, quality_eval.py 커버리지 98%.
- **결정 규칙(C.2 조정 신호)**: 호출지점별 `keep_fast = (FAST_acc >= MID_acc - DELTA) and (FAST_acc >= ABS_MIN)`. **DELTA=0.07**(FAST의 p50 1초 vs 4초 이점이 소폭 정확도차 상쇄)·**ABS_MIN=0.60**(절대 하한). 03a §H 후속1이 임계 미확정 → *문서화된 합리적 기본값*, Phaiakes9 실측 후 보정.
**근거**:
- 채점기·파서·결정규칙은 순수 함수라 모델 없이 테스트 가능(라이브 의존 분리) — bench_latency.py 동일 패턴. 모델 실행만 Phaiakes9.
- 결정적 채점이 FAST 호출지점(추출/매칭/정규화/산술)에 적합(체크 가능한 출력) — LLM-judge 비결정·비용·추가모델 회피.
**적용 범위**:
- 신규 3파일(infra/benchmark 2 + tests/infra 1). 검증: ruff·black(line-length 100)·mypy-strict·pytest 56 통과·커버리지 98%.
- **실측 대기(Kiki·Phaiakes9)**: `python quality_eval.py` → 호출지점별 verdict. 종료코드 1(일부 MID 승급 권고)이면 C.2 조정.
- **gold 검수 필요**: 개념셋 gold는 결정적 채점용 잠정값(review_status "사람 수학자 검수 대기") — 강한 결론 전 검수 권장.
- infra/는 `[tool.black]`/`[tool.ruff]` 설정 미도달·tests/infra CI 미게이트(bench_latency.py와 동일 상태) — 별도 CI 잡 미추가(범위 밖).
**상태**: 하니스 확정(2026-05-20). 결정적 채점·결정규칙·커버리지 98%. **첫 Phaiakes9 실측(2026-05-20)에서 파서가 `ANSWER:`만 안정 추출 → 점수 대부분이 *형식 불일치*로 0**(모델 실력 아님)임이 드러나 하니스 보정: 프롬프트에 `#### <답>` 형식 계약 + 파서 4단 폴백(`####`→`\boxed{}`→라벨→마지막 줄)+감싸기/앞장식 strip, 테스트 56→75(gold·채점 의미 불변). **보정판 재실측은 Phaiakes9 재실행 대기 → 결과로 C.2 조정 판단**(후속1 잔여). 교훈: 추론 모델의 결정적 채점은 *출력 형식 계약*이 선결. **2차 실측(2026-05-20, host 172.17.112.1) 추가 발견**: (a) 1.5b 가용성은 호스트 문제였음(`localhost`=빈 인스턴스, `172.17.112.1`=모델 보유 — 24/7 서버 시 인스턴스 1개로 정리 권장); (b) 새 파서가 산술을 실제로 고침(FAST `\boxed{45}`·MID `": 45"` → `45`); (c) `num_predict` 256→**512**(과추론 잘림 방지); (d) **지표 신뢰도 결정**: 산술·match(정확매칭)는 *결정 등급*, **extract/translate(set_f1/정규형)는 의미≠문자열이라 방향성만**(MID가 합리적 개념 대도 gold와 문자열 불일치로 0). C.2 판단은 산술·match 기준, **extract①은 1.5b 횡설수설(스페인어)로 명백 약점 → MID 잠정 권고**, translate는 보류(gold·과제 명료화 필요). **재설계(2026-05-20, A)** — 실측 재해석으로 *근본 원인* 확정: extract/translate/match는 *NLP 작업*인데 `qwen2-math`(수학 풀이 특화)로 시켜 **7b조차 0%**였음(크기가 아니라 *모델 패밀리* 미스매치). match는 빈 코드 후보로 *찍기*(MID 7/8 동일코드)였고, 비결정성(temperature>0)으로 산술 37↔62% 출렁임도 확인. 하니스를 **태스크 인지**로 재설계: 패밀리별 모델(NLP=`qwen2.5` fast 3b/mid 7b · MATH=`qwen2-math` 1.5b/7b), `<ANSWER>` 형식 강제, `temperature=0`(재현성), LaTeX `\frac`→`a/b`·match 후보 주제명 흡수. 테스트 89·커버리지 98%·게이트 통과. 호스트는 `127.0.0.1`(Windows GPU) 권장(`172.17.112.1`=WSL2 CPU, *속도만* 느림·정확도 무관). **재실측(qwen2.5·GPU) 대기 → 검증되면 03a §C.2를 *태스크 유형(수학 vs NLP) 라우팅*으로 확정(B)**. 핵심 함의: L3 라우팅은 크기/SLA만이 아니라 *태스크 유형*으로 모델 패밀리를 갈라야 한다.

### 2026-05-20: M1.2 L3 라우터 구현 완료 — 결정 로직 + 타입 인터페이스 (.py + 테스트 100%)
**컨텍스트**: 03a 설계서의 라우터를 `.py`로 구현하는 M1.2(03a §H 후속 #3·라우터 설계 후속 #3). 범위는 *결정 로직 + 타입 인터페이스*로 한정 — 실제 LLM/Redis/Langfuse/큐 연동은 라이브 서비스·API 키가 필요해 단위테스트·CI 게이트가 불가하므로 후속 분리. llm-architect 서브에이전트 위임 후 메인이 4게이트 독립 재실행으로 검수.
**결정**:
- `src/backend/whymath_backend/l3/` 신규 패키지(data-pipeline 구조 미러링):
  - `models.py`: `CostTier`·`LocalModelTier`·`CallSite` enum + `RoutingRequest`·`RoutingDecision`(pydantic). 3불변식을 `@model_validator(after)`로 강제(`LOCAL⟺local_model`·`CLOUD⟹None`·`QUALITY⟹async`). `use_enum_values=True`에서도 enum/문자열 양쪽 정규화.
  - `router.py`: `Router.route()` = 축1(C.1 6규칙)→축2(C.2 7규칙) 순차. C.1 규칙5(에스컬레이션)는 단발 입력이 아닌 *생성 결과 피드백* 트리거라 route()에서 제외하고 `next_tier()`/`ESCALATION_CHAIN`(§D.1)으로 분리. `guard_cloud`(§D.4·§E.2 구독 한도)·`cache_key`(§F.1 2축)·`langfuse_fields`(§F.2 dict만)·지연/비용 추정기.
  - `interfaces.py`: `LLMProvider`·`CacheBackend`·`TraceSink`·`AsyncJobQueue` Protocol(미구현) + `InMemoryCache`·`RecordingTraceSink` 테스트 스텁.
- 테스트 `tests/backend/`: 99개, 커버리지 **100%**(stmt+branch). 결정표 각 규칙·불변식·가드·추정·키·에스컬레이션·엣지 커버.
- `src/backend/pyproject.toml` 완성(hatchling·black·pytest paths·coverage) + `.github/workflows/ci.yml`에 `backend — lint·type·test` 잡 추가(ruff·black·mypy-strict·pytest cov70).
- 미설치 핀 `mocktail>=1.0.0` 제거(PyPI 최대 0.0.4·미사용 — `pip install -e .[dev]` 실패 방지).
**근거**:
- 결정 로직은 순수 함수라 라이브 의존 없이 100% 단위테스트 가능 — "모든 PR 테스트(70%+)"(CLAUDE.md) 충족하면서 비용 0. 외부 의존은 Protocol 경계로 분리해 후속 연동 시 교체.
- C.1 규칙5를 route()에서 뺀 건 *계층 책임* — 신뢰 미달 트리거 감지는 생성 파이프라인(03 문서)의 일이고 라우터는 사슬 계산만(`next_tier`).
**적용 범위**:
- 신규: `whymath_backend/l3/{models,router,interfaces}.py`·`tests/backend/*`. 수정: `src/backend/pyproject.toml`·`ci.yml`.
- **미적용(후속)**: 클라우드 비용·지연 상수 placeholder 실측(§H 후속 4)·LLM/Redis/Langfuse/큐 라이브 연동·`backend` CI 잡의 branch protection 필수 체크 등록(Kiki 수동, 현재 필수 3종).
**상태**: 확정(2026-05-20). M1.2 라우터 결정 로직 구현 완료, 4게이트 통과(ruff·black·mypy-strict·pytest 99/100%). 라이브 연동·placeholder 실측은 후속.

### 2026-05-20: Claude Max 구독 = *빌드타임 콘텐츠 생성*, Anthropic API = *런타임 서빙* — CostTier에 구독 미편입
**컨텍스트**: CostTier(축1) 검토 중 "Kiki의 Claude Max 구독($100/$200)을 런타임 CLOUD_MID/HIGH에 활용해 비용 절감" 아이디어 제기. 검토 핵심: **Max 구독과 Anthropic API(개발자 플랫폼)는 별개 시스템**이다 — Max=개인 대화형(앱·Claude Code, 5시간 롤링·주간 상한 rate limit), API=제품 백엔드 토큰당 과금. Max 구독으로는 제품 백엔드가 학생(제3자)을 서빙할 수 없다: (a) 기술적으로 API 키 미발급, (b) 소비자 약관상 *개인 사용 한정*(제3자 서빙·제품 임베드 위반), (c) rate limit으로 다중 학생 동시 서빙 부적합.
**결정**:
- **Max 구독을 CostTier(런타임 라우터)에 편입하지 않는다.** CostTier는 런타임 서빙 채널(LOCAL Qwen / API CLOUD_MID·HIGH)만 표현 — 본 결정이 이를 *명문화*(enum 변경 없음).
- **Max 구독의 자리 = 빌드타임 콘텐츠 생성 파이프라인 + 개발.** Kiki가 Claude Code/앱으로 직접: 프롬프트 설계·코드·**코퍼스 사전 생성**(동등문제·힌트·풀이경로·개념설명)·시드 품질 검증. 결과는 캐시/DB 저장 → 학생 런타임은 캐시 히트(0원).
- 빌드타임 분담: 대량·반복 생성 = 로컬 Qwen / 고난도 검증·시드 품질 = Max-Claude (Max 한도 절약).
- 런타임 비용 통제(03a §E·§F 유지): 80% LOCAL(0원) + 캐시 우선 + 18/2% API(프롬프트 캐싱·Batch API 50%↓·`budget_krw`/`guard_cloud` 일일 한도·⑤ 자기검증 샘플링).
**근거**:
- CLAUDE.md 의사결정 우선순위 **#2 법적·윤리적 준수 > #6 비용** — 약관 위반 절감은 채택 불가(소비자 구독을 제품 서빙에 전용 시 계정 정지·법적 리스크).
- 최대 절감 레버는 "런타임에 클라우드를 *덜* 때리는 것" = **사전생성 + 캐싱**. 여기에 Max를 합법적으로 투입하면 런타임 API 비용을 구조적으로 낮춤(학생당 한계비용 0에 수렴).
- 경계 분리(빌드타임 vs 런타임)가 깔끔: CostTier=런타임 정책, Max=상류 콘텐츠 자산 생성 — 계층·책임이 다름.
**대안**:
- *Max OAuth를 백엔드에 연결(Claude Code headless/Agent SDK)* — 폐기: 소비자 약관상 제3자 서빙 불가 + rate limit으로 프로덕션 부적합 + 계정 리스크. 개인 개발·테스트에만 한정.
- *전량 API 런타임 생성(사전생성 없음)* — 폐기: 학생 수 증가 시 비용 선형 폭증. 사전생성+캐싱이 단가를 구조적으로 낮춤.
- *전량 로컬(클라우드 0)* — 부분 폐기: 킬러·증명·고난도 진단 품질 천장. 80/18/2의 18/2% 클라우드 유지가 학습 효과(#4)상 합리적.
**적용 범위**:
- 본 결정 로그(문서). CostTier enum·03a 변경 없음(이미 런타임만 표현 — 본 결정이 명문화).
- 후속: 빌드타임 사전생성 파이프라인 설계(코퍼스 생성 워크플로·캐시 전략) 별도 트랙. 프롬프트 캐싱·Batch API 도입은 M1.2 클라우드 연동 시.
**상태**: 확정(2026-05-20). Max=빌드타임/개발, API=런타임 서빙. CostTier 불변. 비용 전략 = 사전생성+캐싱으로 런타임 API 최소화.

### 2026-05-20: `main` 보호 자기 승인 데드락 *실제 발생* → 솔로 단계 설정으로 정정
**컨텍스트**: 2026-05-15 `main` 보호 로그(아래)는 "1인 단계 Code Owner 자기 승인 충돌은 Phase 2 합류 시 자연 해소"로 *지연 처리*했으나, 이번 PR #3(아래 L3 라우터 3단계 설계, `2faf61a`) 머지 시점에 **실제 데드락 발생**. 보호 규칙이 (a) 승인 ≥1 + (b) Code Owners 검토를 요구하는데 `@doldori7`가 *유일한 Code Owner이자 PR 작성자* → GitHub은 자기 PR 승인을 금지 → 머지 불가. "administrators 포함(Do not allow bypassing)"까지 켜져 있어 관리자 우회 머지도 차단된 *하드 데드락*. 즉 "Phase 2에 자연 해소"는 문제를 *미룬 게 아니라 모든 솔로 머지를 즉시 봉쇄*하는 것이었음 — 가정 자체가 틀림.
**결정**:
- 보호 *일시 해제* → PR #3 머지(`2faf61a`, main 반영) → 보호를 **솔로 단계용으로 재구성**:
  - **Require a pull request**: 유지(ON) — 직접 push는 계속 차단
  - **Required approvals**: 1 → **0** (자기 승인 불가 회피)
  - **Require review from Code Owners**: ON → **OFF** — 유일 Code Owner=작성자 충돌 제거
  - **필수 status check 3종**(`data-pipeline`·`infra/phaiakes9`·`policy-guard`): 유지 — CI가 실질 게이트
  - **linear history · force-push 차단 · deletion 차단**: 유지
- `.github/CODEOWNERS` 파일은 *그대로 유지* — 자동 리뷰어 지정 기능 자체는 보호 규칙 없이도 동작. Phase 2 리뷰어 합류 시 "Require review from Code Owners" 체크박스 1개만 재활성하면 복원.
**근거**:
- 의사결정 우선순위상 *개발 흐름 봉쇄 해소*가 필요하되, 보호의 실질(직접 push 차단 + CI 3종 게이트 + linear/force-push/deletion 차단)은 **그대로 유지** — 안전을 양보하지 않음.
- 솔로 단계에선 사람 승인보다 *기계적 검증*(lint·type·test·policy-guard 금기 가드)이 보호의 핵심. 승인 0이어도 CI 통과 없이는 머지 불가.
- Code Owners를 *필수 요건에서만* 제외(파일 유지) → 비가역 결정 아님, Phase 2 복원이 체크박스 1개.
**적용 범위**:
- GitHub Settings UI(수동, 코드 변경 아님): `main` 보호 규칙 재구성 — 라이브 설정 read 도구가 MCP에 없어 Kiki 수동 확인·적용
- 본 결정 로그 추가 + 아래 2026-05-15 보호 로그 §상태에 정정 포인터
- **미반영(후속)**: `.github/branch-protection-setup.md`의 "PR 1+승인·Code Owners" 체크리스트는 *Phase 2 기준*임을 문서에 명시 — 솔로 단계는 본 로그가 우선
**상태**: 확정(2026-05-20). `main` 보호 = PR 필수·승인0·Code Owners 미요구·CI 3종·linear·force-push/deletion 차단. 자기 승인 데드락 해소. Phase 2 리뷰어 합류 시 승인≥1 + Code Owners 재활성 예정.

### 2026-05-20: L3 라우터 fast/mid/quality 3단계 설계 — 두 라우팅 축 분리·`mid` 명칭 충돌 해소
**컨텍스트**: 2026-05-19 qwen2-math:1.5b GPU 측정으로 fast/mid/quality 3단계 *로컬* 라인업(1.5b/7b/27b)이 확정된 뒤, "어떤 입력이 어느 모델로 분기되는가"의 결정 로직(입력 분류기 + decision table)을 명세하는 트랙 A 착수. 설계 착수 즉시 *아키텍처 긴장* 발견: 기존 문서(`03_content_generation.md`·`llm-architect.md`)의 라우터 티어는 `LLMTier{LOCAL, MID, HIGH}`(비용·위치 축, MID=Claude Sonnet·HIGH=Claude Opus 클라우드, 목표분포 80/18/2)인데, 새로 확정된 fast/mid/quality는 *전부 로컬 Qwen 모델*. 즉 **두 축이 서로 다름**에도 `mid`가 양쪽에 존재(클라우드 MID vs 로컬 7b)해 충돌.
**결정**:
- L3 라우팅을 **두 축으로 분해**:
  - 축1 *비용·위치* = `CostTier{LOCAL, CLOUD_MID, CLOUD_HIGH}` — 기존 `LLMTier.MID/HIGH`를 `CLOUD_` 접두사로 개명(1:1 의미 보존, 80/18/2 유지). "클라우드로 올라가나?"
  - 축2 *로컬 모델 크기* = `LocalModelTier{FAST, MID, QUALITY}` = 1.5b/7b/27b — 축1이 LOCAL일 때만 적용. "로컬 어느 크기?"
- **명칭 충돌 해소 규칙**: `mid`를 단독으로 쓰지 않는다 — 항상 `CLOUD_MID`(축1) 또는 `LocalModelTier.MID`·`로컬 mid(7b)`(축2)로 한정. 라우팅 결정은 `(cost_tier, local_model)` 쌍 + 불변식(`LOCAL ⟺ local_model 존재`, `QUALITY ⟹ async`)으로 표현.
- **분기 근거 = SLA 실측**: FAST(1.5b)만 p50<2초 게이트 통과 → 동기 즉답 기본 경로(+ c=4 throughput scaling, 피크 흡수). MID(7b) p50≈4초 → 정밀 풀이·메인 대화(동기 허용). QUALITY(27b) p50≈14초+병렬 미작동 → **동기 불가, 비동기 큐 전용**(자기검증·복잡추론·PRM·백그라운드).
- **5개 핵심 호출지점 기본 매핑**: ①개념추출·③번역정규화·④개념ID매칭 = FAST(캐싱 적중률 큼), ②깊이추론 = MID(hard↑면 QUALITY/CLOUD), ⑤자기검증 = QUALITY/async(샘플링).
- 산출: 신규 설계서 `docs/architecture/03a_l3_router_design.md`(A~H 8개 섹션: 두 축 통합·입력분류기·decision table·의사코드·에스컬레이션/폴백·비용예산SLA·캐싱Langfuse·스키마·미해결). 03 문서 §1·모델풀표·5호출지점 문단 *최소* 정합성 보정(CLOUD_ 표기 + 03a cross-ref).
**근거**:
- 한 단어(`mid`)가 두 축을 겸하면 코드·문서·Langfuse 태그에서 *어느 축인지* 모호 → 환각·비용 오라우팅 위험. `CLOUD_` 접두사로 *맨이름 mid를 어디에도 단독으로 두지 않는* 게 가장 견고.
- 2026-05-19 결정 로그가 명시한 "비용·품질·지연의 파레토 최적"을 *실행 가능한 분기 규칙*으로 번역. SLA 실측이 모든 분기의 근거(추측 아님 — CLAUDE.md "확실하지 않을 때 자신 있게 말함 금지").
- 기존 `Router.route()` 4규칙을 *축1로 의미 보존* 후 로컬 세분(축2)만 신규 추가 → 기존 설계 무효화 없이 확장.
- 설계/구현 분리: 본 트랙은 *명세*까지(설계 트랙). 실제 `.py`·테스트는 M1.2. 스키마는 마크다운 예시 코드블록으로만.
**대안**:
- 단일 enum 유지(`LLMTier`에 FAST/MID/QUALITY 추가) — 폐기: 비용축과 크기축이 한 enum에 섞여 80/18/2 분포 의미 붕괴, `mid` 충돌 미해소.
- 로컬 세분을 라우터 밖(클라이언트)에서 처리 — 폐기: "모든 LLM 호출은 라우터 경유"(CLAUDE.md) 위배, 호출지점별 정책 일관성 상실.
- fast/mid/quality를 그대로 최상위 티어로(클라우드 제거) — 폐기: 킬러·증명·어려운 진단의 클라우드 에스컬레이션 경로 상실, 80/18/2 전략 폐기.
**적용 범위**:
- 신규: `docs/architecture/03a_l3_router_design.md`
- 수정(최소): `docs/architecture/03_content_generation.md` 3곳(§1 출력 명세·모델풀 표 2축화·5호출지점 문단 + 03a cross-ref·명칭충돌 주석)
- 본 결정 로그 + 활성 작업 갱신
- **적용 완료(2026-05-20)**: `LLMTier`를 참조하던 `.claude/agents/llm-architect.md`(enum→`CostTier`+`LocalModelTier`·`Router.route()`→`RoutingDecision` 반환)·`docs/architecture/04_pedagogy_engine.md`(`recommended_tier`→`recommended_cost_tier: CostTier`)·`06_application_modes.md`(`default_llm_tier`→`default_cost_tier: CostTier`)·`.claude/agents/backend-engineer.md`(호출처 `route()→generate(decision=)`로 일관 갱신)의 두 축 분해 반영 완료. `budget_cents`→`budget_krw`(03a E장)도 통일. L4/L6은 *축1(CostTier)만* 힌트로 보유, 축2(로컬 FAST/MID/QUALITY)는 L3 라우터가 결정(계층 경계). *문서 간 불일치 해소*. 구현은 M1.2.
**후속 작업 (별도 PR/세션)**:
1. **[완료 2026-05-20] FAST tier 품질 검증** — Phaiakes9 실측 완료. 결론: *모델 패밀리* 미스매치(수학모델로 NLP=0%)가 근본 원인 → **태스크 패밀리 라우팅** 도입(위 *L3 라우팅에 태스크 패밀리 축 도입* 로그·03a §0.2 참조). 잔여: extract 지표·라우터 코드 family 반영(03a §H 8~11)
2. **[완료 2026-05-20] 인터페이스 정렬: `LLMTier` → `CostTier`/`LocalModelTier`** — llm-architect.md·04·06·backend-engineer.md의 `LLMTier` 참조를 두 축 분해로 갱신 (위 §적용 범위 참조)
3. **[완료 2026-05-20] M1.2 라우터 구현** — 03a 설계를 `.py`로 구현 + 테스트(커버리지 100%). 결정 로직+인터페이스 범위(LLM/Redis/Langfuse/큐 라이브 연동은 후속). 위 *M1.2 L3 라우터 구현 완료* 로그 참조
4. **클라우드 티어 실연동** — CLOUD_MID/HIGH API·비용 계측·`guard_cloud` 임계값 실측(Phase 1 후반)
**상태**: 설계 완료(`feat/l3-router-3tier-design`). 두 축·명칭 충돌·decision table·에스컬레이션·스키마 명세 확정. 구현은 M1.2.

### 2026-05-19: qwen2-math:1.5b GPU 측정 완료 — L3 라우터 fast tier 후보 확정, 3단계 라인업 결정
**컨텍스트**: 2026-05-16 GPU 활성화 후 후속 작업 1번. qwen2-math:7b GPU 32.63 tok/s · p50 3,918ms / qwen3.5:27b GPU 9.22 tok/s · p50 13,886ms 둘 다 L3 SLA(p50 < 2초) FAIL → *실시간 대화 즉답이 가능한 더 작은 모델 측정 필요*. Ollama Library의 `qwen2-math:1.5b` (934 MB, 2026-05 정식 등록) 후보. 동일 환경(Windows Ollama 0.24.0 + DirectML · Strix Halo Radeon 8060S · WSL2 클라이언트 `WHYMATH_OLLAMA_HOST=http://172.17.112.1:11434`) + 동일 벤치 스위트(고1 내신 원작 8문항)로 측정.
**결정**:
- L3 라우터 라인업을 *fast/quality 2단계*에서 ***fast/mid/quality 3단계***로 확장:
  - **fast tier = qwen2-math:1.5b** (대화 즉답·분류·1단계 산술·관리적 응답) — *L3 SLA 게이트 PASS*
  - **mid tier = qwen2-math:7b** (수학 풀이·2~3단계 추론·메인 학생 대화) — p50 ~4초, 게이트 FAIL이나 *허용 응답 시간 내*
  - **quality tier = qwen3.5:27b** (답안 검증·복잡 추론·PRM 후보·백그라운드) — p50 ~14초, *동기 응답 불가*
- Phaiakes9가 *L3 SLA 준수 환경* 보유 입증 — 옵션 F(ROCm Linux native) 의 *2-5x 잠재력*은 이 게이트 통과 후에도 *동시도 4·mid·quality* 개선 여지로 유효
**환경**: 2026-05-16 결정 로그와 동일 (Windows Ollama 0.24.0 / DirectML / Radeon 8060S Strix Halo / WSL2 Ubuntu 24.04 클라이언트). 워밍업 1회 후 측정. 헬스체크 3단계 통과 (`'2+2=' → '...2 + 2 = 4...'`).
**GPU baseline — qwen2-math:1.5b (2026-05-19 11:50 KST)**:
- 동시도 1: p50=**1,009.99ms** / p90=1,088.56ms / p99=1,098.48ms / **124.25 tok/s**
- 동시도 4: p50=3,522.03ms / p90=3,590.26ms / p99=3,658.16ms / **142.91 tok/s**
- L3 SLA 게이트 (p50 < 2000ms): ✅ **PASS** (동시도 1)
- Windows GPU 적재: 100% GPU, 1.4 GB VRAM (`ollama ps`)
- 결과 JSON: `infra/phaiakes9/results/2026-05-19_115051.json` (.gitignore — 로컬 보관)
**3점 비교 (GPU baseline 종합)**:
| 모델 | 디스크 | p50 (c=1) | tok/s (c=1) | tok/s (c=4) | 게이트 (c=1) | 용도 후보 |
|---|---|---|---|---|---|---|
| qwen2-math:1.5b | 934 MB | **1,010ms** | **124.25** | 142.91 | ✅ PASS | **fast tier** (대화 즉답) |
| qwen2-math:7b | 4.4 GB | 3,918ms | 32.63 | 33.81 | ❌ FAIL | **mid tier** (수학 풀이·메인 대화) |
| qwen3.5:27b | 17 GB | 13,886ms | 9.22 | 9.28 | ❌ FAIL | **quality tier** (검증·백그라운드) |
**병렬 처리 특성 (1.5b vs 7b vs 27b)**:
- 1.5b: c=1 → c=4 tok/s **124 → 143 (+15%)** — *GPU throughput 활용 작동, 동시 4 처리 가능*
- 7b: c=1 → c=4 tok/s 33 → 34 (+4%) — 한계 근접, c=4에서 p50 15초로 폭발
- 27b: c=1 → c=4 tok/s 9.22 → 9.28 (~0%) — *GPU 한 요청 100% 점유, 병렬 미작동*
- → **1.5b 가 fast tier 로서 *피크 트래픽 흡수* 역할까지 가능** (학생당 0.5-1 RPS 가정 시 단일 GPU로 수십 명 동시 대응)
**근거**:
- 1.5b 가 *L3 SLA 게이트 통과 + 동시도 4 throughput scaling 작동* — fast tier 의 *지연·처리량 동시 충족* 데이터 확보
- 7b·27b 가 게이트 FAIL 인 것이 *문제가 아니라 역할 분기 근거* — 한 모델로 *즉답 + 정확성* 둘 다 충족 불가, 3단계 분기가 *비용·품질·지연의 파레토 최적*
- 1.5b 의 *수학 특화(qwen2-math)* + *작은 크기* 결합으로 *분류·라우팅·간단 산술*에서 7b 와 *품질 차이 좁음* 가정 — 실제 품질 검증은 후속 (L3 라우터 구현 시)
**대안**:
- 단일 tier (7b 단독) 진행 — 폐기: p50 4초가 *즉답엔 길고 정밀 채점엔 짧음*. 두 요구 동시 충족 불가
- fast = 7b 유지 (1.5b 폐기) — 폐기: 게이트 FAIL 사실 변하지 않음, 1.5b 의 *6배 throughput·4배 빠른 응답* 데이터 무시
- 클라우드 Claude/GPT 로 fast tier 위탁 — 폐기: CLAUDE.md *로컬 LLM 우선* 원칙 위배, 학생당 일 50-100회 호출 시 비용 폭발
- qwen2-math:0.5b 또는 다른 1B 후보 추가 측정 — *보류*: 1.5b 가 이미 SLA 충족, 추가 측정 ROI 낮음. 라우터 구현 후 *fast tier 품질 미흡* 시 재시도
**적용 범위**:
- MEMORY.md 본 결정 로그 (3점 비교 + 라우터 라인업 결정)
- MEMORY.md 활성 작업: "qwen2-math:1.5b GPU 측정" → ✅ 완료, "L3 라우터 fast/quality 두 단계" → "fast/mid/quality 3단계"로 갱신, "fast tier 품질 검증" 신규 등록
- `infra/phaiakes9/GPU_ACTIVATION_FOLLOWUP.md` 옵션 A1 *완전 실증 완료* (1.5b·7b·27b 3점 데이터로 라우터 라인업 결정 완료)
**후속 작업 (별도 PR/세션)**:
1. **L3 라우터 fast/mid/quality 3단계 설계** — `docs/architecture/03_content_llm.md` 갱신 또는 별도 설계서. *입력 분류기* + 분기 결정 로직 명세 (다음 트랙 A)
2. **fast tier 품질 검증** — 1.5b 가 *간단 산술·메타 응답·분류* 에서 7b 대비 *품질 차이* 측정. L3 라우터 구현 시 진행
3. **ROCm 7.2+ Linux native 시도** (옵션 F 유지) — *2-5x 잠재력*은 mid·quality tier 개선 여지로 유효 (BIOS UMA·드라이버 사전 조치 필요)
4. **healthcheck.sh 디폴트 timeout 상향** (2026-05-16 후속 4번 유지) — 30초 → 90초 (큰 모델 콜드 로드 대응)
**상태**: L3 라우터 fast tier 후보 확정. Phaiakes9 가 *3단계 라인업 모두 운영 가능한 환경* 보유. 본격적 L3 라우터 구현(M1.2) 의 *데이터 기반 설계 근거 확보 완료*.

### 2026-05-16: Phaiakes9 GPU 가속 활성화 완료 — Windows Ollama 경유 DirectML, 모델 라인업 데이터 확보
**컨텍스트**: 2026-05-15 결정 로그 *옵션 A1* 진행. Windows측에 Ollama 0.24.0 native 이미 설치되어 있음 확인 + Radeon 8060S(Strix Halo) GPU 자동 인식 (`ollama ps` PROCESSOR=100% GPU, qwen2-math:7b 5.2GB GPU 적재). WSL 측 클라이언트가 `WHYMATH_OLLAMA_HOST=http://172.17.112.1:11434` (Windows 호스트 IP) 로 호출 — 환경변수 한 줄만 변경, WSL 측 인프라 코드 자체는 *완전 무수정*. WSL2 NAT networking에서 Windows Ollama API 즉시 도달 (별도 firewall·OLLAMA_HOST=0.0.0.0 설정 불필요).
**결정**:
- GPU 가속 *최소 viable* 환경 확보 — DirectML 경로로 7B 모델 CPU 대비 *2.6x 향상*
- L3 LLM 라우터 설계: *fast tier (qwen2-math:7b GPU, 32.63 tok/s)* + *quality tier (qwen3.5:27b GPU, 9.22 tok/s)* 두 단계 라인업 후보 확정
- ROCm 7.2+ Linux native (옵션 F) 는 *추가 잠재력 2-3x* 보유 — 후속 별도 세션 (BIOS UMA·드라이버 사전 조치 필요)
**환경**:
- Windows측: Ollama 0.24.0 (DirectML 추정, GPU 100% 활용 확인)
- WSL 측: Ollama systemd 서비스 *유지* (사용 안 함, 환경변수 override 로 Windows Ollama 호출)
- 기타 머신 사양 = 2026-05-15 1차 셋업 결정 로그와 동일 (NucBox EVO-X2 / Ryzen AI Max+ 395 / Radeon 8060S Strix Halo / WSL2 Ubuntu 24.04)
**GPU baseline — qwen2-math:7b (2026-05-16 12:52 KST)**:
- 동시도 1: p50=**3,917.67ms** / p90=3,965.7ms / p99=3,981.28ms / **32.63 tok/s**
- 동시도 4: p50=15,015.31ms / p90=15,140.63ms / p99=15,143.33ms / 33.81 tok/s
- L3 SLA 게이트 (p50 < 2000ms): ❌ FAIL — *DirectML on Strix Halo 환경 + 7B 로 게이트 통과 어려움 확인*
- 결과 JSON: `infra/phaiakes9/results/2026-05-16_125209.json` (.gitignore — 로컬 보관)
**GPU 큰 모델 비교 — qwen3.5:27b (2026-05-16 13:03 KST)**:
- 동시도 1: p50=**13,885.85ms** / p90=13,992.73ms / p99=14,014.09ms / **9.22 tok/s**
- 동시도 4: p50=55,126.10ms / p90=55,258.83ms / p99=55,277.86ms / 9.28 tok/s
- L3 SLA 게이트: ❌ FAIL — *27B 는 실시간 대화용 X, 백그라운드 검증·고난도 추론용*
- 동시도 1 vs 4 의 tok/s 가 거의 동일 (9.22 / 9.28) — *큰 모델의 throughput scaling 미작동* (GPU 한 요청에 100% 사용, 병렬 처리 안 됨)
- 결과 JSON: `infra/phaiakes9/results/2026-05-16_130349.json`
- 콜드 로드 시간 30초 초과로 헬스체크 디폴트 timeout(30초) 부족 — `WHYMATH_HEALTH_TIMEOUT=180` 추가 환경변수로 해소. 후속 PR 에서 디폴트 상향 검토
**CPU vs GPU 비교 (qwen2-math:7b)**:
| 지표 | CPU baseline (2026-05-15) | GPU baseline (2026-05-16) | 향상 |
|---|---|---|---|
| p50 latency (동시도 1) | 10,303ms | 3,918ms | **2.6x ↓** |
| tok/s (동시도 1) | 12.62 | 32.63 | **2.6x ↑** |
| tok/s (동시도 4) | 24.67 | 33.81 | 1.4x ↑ |
**모델 비교 (GPU)**:
| 모델 | 디스크 | p50 (동시도 1) | tok/s | 용도 후보 |
|---|---|---|---|---|
| qwen2-math:7b (Q4_K_M) | 4.4GB | 3,918ms | 32.63 | **fast tier** (실시간 대화·산술·1-2단계 추론) |
| qwen3.5:27b | 17GB | 13,886ms | 9.22 | **quality tier** (백그라운드 검증·복잡 추론·답안 채점) |
**근거**:
- GPU 활성화로 *진정한 진전* 확인. 단 *기대치(5-12x)에는 미달 (실측 2.6x)* — DirectML on Strix Halo iGPU 의 정상 수준
- 7B vs 27B 데이터로 *L3 라우터 fast/quality 두 단계* 설계 근거 확보 — *학생 대화 즉답* 은 7B, *답안 검증·복잡 추론* 은 27B 분리
- p50 < 2초 게이트는 *7B GPU 로도 어렵다* 확인 → *qwen2-math:1.5b* (~1GB) 측정 또는 *ROCm Linux native* 가 다음 세션 핵심 시도
- Kiki PC 에 *qwen3.5:27b·qwen3-coder:30b·llama3.3:42b·gpt-oss:20b·qwen3:30b-a3b(MoE)* 다수 이미 적재 — *모델 비교 실험* 추가 비용 거의 없음
**대안**:
- ROCm Linux native 이번 세션 진행 — 폐기: 2-4시간 추가 소요(BIOS UMA + 드라이버 갱신 등), 별도 세션이 효율
- qwen2-math:1.5b 추가 측정 이번 세션 — 폐기: 데이터 점 3개로 *L3 라우터 두 단계 결정* 에 충분, 1.5b 는 다음 세션
- DirectML 대신 Vulkan 명시 — 폐기: 현재 100% GPU 활용 확인됐고 두 백엔드 효율 차이 미미 추정 (Strix Halo 특성)
**적용 범위**:
- MEMORY.md 본 결정 로그 (CPU·GPU baseline + 모델 비교 데이터)
- MEMORY.md 활성 작업: M1.1 GPU 가속 → ✅ 완료. ROCm Linux native·1.5b 측정·L3 라우터 설계 신규 후속 등록
- `infra/phaiakes9/GPU_ACTIVATION_FOLLOWUP.md` 의 옵션 A1 *실증 완료*. 옵션 F(ROCm) 가 후속 세션 우선
**후속 작업 (별도 PR/세션)**:
1. **ROCm 7.2+ Linux native 시도** — 옵션 F. BIOS UMA Frame Buffer Fixed 48-64GB + Linux Kernel 6.18.4+ + ROCm 7.2.0+. 목표: tok/s 60-150 (현재 32 의 2-5x)
2. **qwen2-math:1.5b GPU 측정** — 실시간 대화 SLA 통과 가능성 검증. 1GB pull + 동일 벤치
3. **L3 라우터 fast/quality 두 단계 설계** — `docs/architecture/03_content_llm.md` 갱신 또는 별도 설계서
4. **healthcheck.sh 디폴트 timeout 상향** — 30초 → 90초 (큰 모델 콜드 로드 대응)
**상태**: GPU 가속 활성화 완료. Phaiakes9 가 *L3 LLM 라우터 두 단계 모두 운영 가능한 환경* 확보. 본격적 L3 라우터 구현은 다음 마일스톤(M1.2). 옵션 A1(Windows Ollama 경유) 가 *셋업 노력 vs 효과* 면에서 최적의 진입점이었음 확인.

### 2026-05-15: Phaiakes9 1차 셋업 완료 — CPU baseline 확보, GPU 후속 분리
**컨텍스트**: M1.0a Phaiakes9 머신 셋업 (NucBox EVO-X2 / AMD Ryzen AI Max+ 395 + Radeon 8060S Strix Halo / WSL2 Ubuntu 24.04). 셋업 과정에서 인프라 스크립트 다수의 버그·잘못된 모델 카탈로그 발견·fix. 1차 셋업 종료 단계로 GPU 활성화 시도 — Vulkan 경로에서 RADV가 WSL2 DXG 패스스루를 인식 못 함 확인 (Mesa 25.2.8에 DZN ICD 미포함). Kiki가 *Strix Halo 활성화 정확 가이드* 제공 (BIOS UMA Frame Buffer Fixed 48~64GB + Linux Kernel 6.18.4+/Firmware 20260110+/ROCm 7.2.0+ + WSL2 librocdxg + AMD Adrenalin 26.x+).
**결정**: 1차 셋업 종료 + CPU baseline을 *공식 M1.1 게이트 기록*으로 채택. GPU 활성화는 *다음 세션* A1(Ollama Windows native) 또는 A2(BIOS·드라이버 조치 후 WSL Vulkan 재시도)로 분리.
**1차 셋업 산출 커밋**:
- `7014bc7` fix(phaiakes9): pull_models.sh readonly OLLAMA_HOST + prefix 충돌 해소
- `8e5202d` fix(phaiakes9): 잘못된 Qwen 카탈로그 (qwen2.5-math:* → qwen2-math:7b + 일반 Qwen2.5 32B/72B 폴백)
- `962be1d` chore: .gitattributes — *.sh LF 고정 (Windows CRLF 재발 방지)
- `d67f419` fix(phaiakes9): bench_latency.py DEFAULT_MODEL fix
- (본 PR) docs(infra) + MEMORY 갱신
**CPU baseline (2026-05-15 16:13 KST)**:
- 환경: WSL2 Ubuntu 24.04 + Mesa 25.2.8 (Vulkan 1.3.275 — llvmpipe만 인식)
- 머신: NucBox EVO-X2 / Ryzen AI Max+ 395 / Radeon 8060S (gfx1151, Vulkan 미인식 상태)
- 모델: qwen2-math:7b (Q4_K_M, 4.4 GB)
- systemd unit: Phaiakes9 특화 (0.0.0.0:11434, MAX_LOADED_MODELS=2, NUM_PARALLEL=4, KEEP_ALIVE=10m)
- 표본: 고1 내신 원작 8문항 (`infra/phaiakes9/benchmark/sample_prompts.json`)
- 동시도 1: p50=10,303ms / p90=10,521ms / p99=10,752ms / **12.62 tok/s**
- 동시도 4: p50=20,654ms / p90=20,901ms / p99=20,903ms / **24.67 tok/s**
- L3 SLA 게이트 (p50 < 2000ms): ❌ FAIL — *CPU 추론으로 예상된 결과*
- 결과 JSON: `infra/phaiakes9/results/2026-05-15_161344.json` (.gitignore — 로컬 보관)
**GPU 활성화 시도 결과**:
- Ollama 자체 GPU 자동 감지: ❌ `total_vram="0 B"`, `inference compute id=cpu library=cpu`
- Vulkan (RADV) 강제 (`VK_ICD_FILENAMES=/usr/share/vulkan/icd.d/radeon_icd.json`): ❌ `Failed to detect any valid GPUs`
- `/dev/dri` 부재 (Linux native GPU 노드 없음), `/dev/dxg` 존재 (DXG 패스스루 OK)
- Mesa 25.2.8 패키지에 *DZN(DirectX-to-Vulkan) ICD 미포함*. RADV가 DXG 인식 불가
- → 2026-05 기준 *WSL2 + Strix Halo + Vulkan*은 정식 지원 대기 단계 확인
**근거**:
- 1차 셋업이 이미 ~2시간 누적. GPU 활성화 추가 시도는 *Mesa 빌드*·*ROCm 셋업*·*Windows 드라이버 갱신* 등 큰 작업으로 *오늘 단락 짓는 게 효율적*
- CPU baseline 자체가 *PRD M1.1 게이트 실측 데이터*로 가치 보유 (후속 GPU 개선치의 비교 기준)
- Kiki 제공 Strix Halo 활성화 가이드가 *명확한 다음 세션 출발점* — 큰 발견을 *잃지 않고 보존* 필요
**대안**:
- GPU 활성화 이번 세션 계속 — 폐기: 시간 + 성공률 불확실. Strix Halo + Vulkan은 BIOS·드라이버 정합성까지 가야 함
- baseline 측정 없이 GPU만 시도 — 폐기: 비교 기준 부재 시 *개선치 정량화* 불가
- Ollama Windows native 즉시 전환 — 폐기: 큰 셋업 변경, 사용자 부담 누적
**적용 범위**:
- 신규 파일: `infra/phaiakes9/GPU_ACTIVATION_FOLLOWUP.md` (Kiki 가이드 보존 + 옵션 A/B/C 다음 세션 흐름)
- MEMORY.md 활성 작업 갱신 (M1.0a/M1.1 완료 표시, GPU 후속·카탈로그 정리·systemd 완화 신규 항목)
- 본 결정 로그
**후속 작업 (별도 PR/세션)**:
1. **A 후속 — Phaiakes9 GPU 활성화**: `GPU_ACTIVATION_FOLLOWUP.md` §3 옵션 A/B/C 중 선택해 진행. 다음 세션 시작점
2. **B 후속 — Qwen 카탈로그 cosmetic 정리**: README.md 7군데, SETUP_GUIDE.md 1군데, 주석 4군데 (코드 동작 영향 없음, 문서 일관성)
3. **C 후속 — Ollama systemd unit `ProtectSystem=full` 완화**: `failed to persist model recommendations snapshot ... read-only file system` 경고 해소. `ReadWritePaths=/usr/share/ollama` 추가
**상태**: 1차 셋업 완료. M1.1 CPU baseline을 PRD M1.1 게이트 기록으로 채택. GPU 활성화는 다음 세션 시작 항목.

### 2026-05-15: NCIC 크롤링 baseline 완료 — 영역·본문/해설 정제는 후속 분리
**컨텍스트**: Kiki가 별책 8 수학과 교육과정 PDF(1.94MB)를 git push로 반입(`aa29267`), Claude가 `python -m data_pipeline.ncic crawl --pdf ...` 실행 → 629건 추출, JSON·CSV·sidecar 저장. NCIC 사이트 자체는 이 환경 네트워크 allowlist 차단(`docs/data/ncic.md` §3.1).
**결정**: 현 산출물을 baseline(v0)으로 수용, 영역 추출·본문/해설 분리는 후속 분리 작업. `data/ncic/` 통째로 `.gitignore` 처리(raw 입력 + 미완성 산출물 모두 git 비포함). PDF는 `git rm --cached`로 추적 제거(history는 잔존).
**검수 결과 (5% 무작위 31건 + 자동 분석)**:
- ✅ 코드 형식: 모두 정규식 통과 (`[10공수1-02-06]` 등)
- ✅ 학교급 추론: 정확 (초등 155·중학 86·고등 388, 학년 대수 일치)
- ❌ **영역(domain) 미추출**: 모두 "미지정" — `_PdfStandardExtractor`가 PDF 헤더("(1) 수와 연산" 등)를 영역으로 인식 안 함. HTML 추출기엔 추론 로직이 있으나 PDF는 미구현.
- ❌ **본문 vs 해설 미분리**: 같은 코드가 본문 + 해설 두 번 등장 → 둘 다 statement로 저장. 예: `[2수03-10]` 본문("길이 단위 1cm와 1m를 알고…") + 해설("길이의 표준 단위를 도입하기 전에 구체물을 직접…"). 중복 194건 모두 statement가 서로 다른 것으로 확인.
- 진짜 성취기준 수: 고유 코드 435개 → 본문/해설 분리하면 ~150-300개 (NCIC 예상치 150-180에 근접).
**근거**:
- Kiki가 명시한 작업 범위는 "crawl 실행 → 5% 검수" — 그건 완료. 정제는 별도 작업.
- 정제는 코드 변경(`_PdfStandardExtractor` 확장 + `transform` 조정 + 테스트 갱신)이고 1-2시간. 별도 PR로 분리하는 게 깔끔.
- 정제 전 산출물을 git에 truth source로 박으면 정제 후 큰 diff 발생, history 오염. baseline은 로컬에서만 운영하다 정제 완료 시 정식 커밋이 안전.
**대안**:
- 정제 먼저(코드 추가 후 재추출) — 폐기: 작업 시간 1-2시간, Kiki 일정과 무관하게 차후 가능
- v0로 git에 커밋 + PDF만 `.gitignore` — 폐기: 부정확 데이터 영구 보관, 정제 후 큰 diff
**적용 범위**:
- `.gitignore` 추가: `data/ncic/raw/`, `data/ncic/*.json`, `data/ncic/*.csv`
- `git rm --cached data/ncic/raw/curriculum_math_2022.pdf` (`aa29267` 추적 해제, history 잔존)
- MEMORY.md 본 로그 + 활성 작업·후속 작업 갱신
**후속 작업 (별도 PR)**:
- **L1.NCIC.정제**: `_PdfStandardExtractor`가 페이지 헤더에서 영역명 추적, 같은 코드 두 번째 등장은 `commentary`로 분류(`AchievementStandard.commentary` 필드 활용). 재추출 후 ~150-300건 unique standards 검증.
**상태**: baseline 확정. 정제는 후속 PR로 등록. 데이터 카드 `docs/data/ncic.md`는 유지(메타·라이선스·실행 절차).

### 2026-05-14: MathScope PRD v1.1 채택 — 비전·기능 흡수, 구조 골격 WhyMath 유지
**컨텍스트**: Kiki가 별도로 발전시킨 *MathScope PRD v1.1*(1,410줄)이 도착. WhyMath 하네스 문서군(CLAUDE.md·MEMORY.md·ROADMAP.md·docs/architecture/01~07·.claude/agents/)과 같은 프로젝트 비전(메타인지·답 안 주기·Socratic·다중 풀이·Polya·Flutter+FastAPI·Phaiakes9 로컬 LLM)을 공유하나, 두 사고 라인이 갈라져 브랜드·아키텍처·DB 스택·로드맵·데이터 모델·첫 진입 전략이 곳곳에서 충돌. 그대로 두면 *진실의 원천*이 둘이 되어 컨텍스트 오염. PRD는 시장·사업·법률·UX·데이터 모델 면에서 하네스보다 풍부하나, 하네스는 7계층 책임 규율·교수학 깊이가 강함.
**결정**: PRD의 *비전·신규 기능*을 정본으로 흡수하되, 3대 구조 결정은 *WhyMath 골격 유지*.
- **브랜드 = WhyMath 유지**. PRD의 "MathScope (가칭)"는 미확정 가칭 — PRD가 브랜드를 정한 게 아님. WhyMath는 2026-05-14 브랜드 결정 로그에 근거와 함께 확정, GitHub 레포도 `doldori7/WhyMath`. PRD 인용 시 "MathScope" → "WhyMath" 치환.
- **7계층 책임 모델 유지 + PRD 5블록 흡수**. 7계층=책임 레이어(.claude/agents 7개와 직결), PRD 5블록(Client/Backend/DB/ML/Pipeline)=배포 토폴로지 — 직교하는 두 축. 7계층 유지하고 PRD 5블록은 `00_overview.md`에 배포 관점 섹션으로 추가.
- **첫 진입 = 고1 내신 유지**. PRD의 "미분 단원 파일럿"을 "고1 단원 중 하나"로 재해석. 2026-05-13 결정 로그 유지.
- **DB 스택 변경** (CLAUDE.md 기술 스택 표 갱신 대상): Neo4j(개념 그래프)·Qdrant(벡터, 기존 ChromaDB 대체 검토)·ClickHouse(학습 행동 로그)·S3/MinIO(영상·이미지) 추가. 추가 스택: MathLive·D3.js·three.js·Plotly·HDBSCAN·UMAP·OpenAI text-embedding-3-large.
- **PRD 신규 자산 → 7계층 매핑**: 개념 그래프·다국 커리큘럼 매트릭스·교과서 매핑 12단계 파이프라인·자동 커리큘럼 정렬 → L1; `SolutionPath.concept_sequence` → L3; `MasteryState`·`StudentProfile` → L2; 시각화 스택(선언적 `Visualization`) → L5; Socratic 흐름·graded `Hint`·개념 점화 지도 → L4; PIPA 데이터 권한 매트릭스 → 횡단; 사업·법률·5개 핵심 가정 → docs/strategy·docs/legal.
**PRD 논리적 허점 8건과 보정 입장**: ①Phase 1 3개월 과부하 → WhyMath 6개월 Phase 1 유지 ②다국 매트릭스 9~12개국 Phase 1 과욕(본문 §1.6 vs §15.1 불일치) → Phase 3 재배치 ③3개 앱 동시 개발 부담 → 단일 앱 모드 분기 + 대시보드 Phase 3+ 유지 ④BKT 제거 위험 → BKT(P1)→IRT(P2)→DKT(P3) 단계 도입 유지 ⑤개념 시퀀스 동치성 판정 난이도 과소평가 → 휴리스틱+사람 검수 단서 ⑥교과서 학습목표 "페어유즈" 단정 위험 → 변호사 검토 전제 ⑦AWS Seoul 확정 vs Phaiakes9 하이브리드 지연·동기화 비용 미언급 → 기존 하이브리드 인식 유지 ⑧부록 E "별책 9"는 오타 — 수학과 교육과정은 *별책 8*.
**근거**:
- PRD가 "정본"인 것은 *비전·기능·시장·법률 사고의 깊이*에서이지 *구조 결정*에서가 아님. 브랜드·7계층·진입학년은 하네스에 이미 근거와 함께 확정된 사항 — PRD가 그것을 *논박한 게 아니라 모른 채로 작성*된 것.
- 7계층은 서브에이전트 위임 워크플로의 단위 — 폐기하면 워크플로 전체가 흔들림. PRD 5블록과는 축이 달라 양립 가능.
- PRD의 진짜 가치는 자동 커리큘럼 정렬·교과서 매핑 파이프라인·다국 매트릭스·개념 그래프·9개 데이터 엔티티·PIPA 매트릭스·5개 핵심 가정 검증법 — 하네스에 *없던* 자산이며 7계층 안에 깔끔히 들어감.
**대안**:
- *PRD를 완전 정본으로(브랜드·5블록·고2 미분까지)* — 폐기: 이미 확정된 결정 3건을 근거 없이 뒤집음, 서브에이전트 구조 재작성 부담
- *PRD를 독립 문서로 방치* — 폐기: 진실의 원천 이중화, 컨텍스트 오염
- *단일 통합본 신규 작성* — 폐기: 작업량 최대, 하네스의 검증된 구조를 버릴 이유 없음
**적용 범위**: 정렬 실행 계획 5단계 — 단계1 본 결정 로그(MEMORY.md), 단계2 CLAUDE.md+ROADMAP.md, 단계3 docs/architecture/00~07, 단계4 .claude/agents+docs/data+docs/strategy+docs/legal, 단계5 schemas/v1.1/*.yaml 9개 엔티티. 범위 밖: PRD 와이어프레임 구현·엔티티 코드 구현·실제 DB 배포.
**상태**: 확정. 단계별 진행 — 본 로그가 후속 모든 문서의 근거.

### 2026-05-14: `main` 보호 — CODEOWNERS + CI status check 자동화, UI 단계는 별도 가이드
**컨텍스트**: 2026-05-14 GitHub 연결 결정 로그의 후속 작업 "main 보호 규칙(force-push 금지·PR 리뷰 필수) 적용 예정"을 자동 처리하려 했으나, Claude의 GitHub MCP 도구셋에 *Branch Protection* / *Repository Ruleset* 엔드포인트 도구가 부재. 원격이 로컬 MCP 게이트웨이(`http://127.0.0.1:36037/git/doldori7/WhyMath`)라 토큰을 직접 쓸 수도 없음(MCP 도구 외 경로로 REST API 호출 불가). 따라서 *완전 자동*은 불가능, 정책의 *실효성 부분*만 코드로 강제하고 GitHub Settings UI 단계는 5분 수동 가이드로 분리.
**결정**:
- 자동(코드 표현):
  - `.github/CODEOWNERS` — 영역별 자동 리뷰어. 디폴트 `@doldori7`, L1 데이터·L3/L5 인프라·문서·정책·`.github/` 등 영역별 매핑. Phase 2+ 합류 시 분기 가능한 구조
  - `.github/workflows/ci.yml` — push/PR마다 3 job 실행:
    - `data-pipeline — lint·type·test`: ruff·black·mypy-strict·pytest+coverage(fail-under=70)
    - `infra/phaiakes9 — bash syntax`: 모든 infra `.sh` 파일 `bash -n` + shellcheck(non-blocking)
    - `policy-guard — CLAUDE.md 금기 가드`: 검정교과서 본문 인용 패턴·하드코딩 시크릿(sk-/sk-ant-/ghp_/AKIA) 사전 차단
  - concurrency group으로 비용 절감 (동일 ref 재푸시 시 이전 실행 취소)
- 수동(GitHub Settings UI):
  - `.github/branch-protection-setup.md` — 1페이지 체크리스트: PR 1+승인·Code Owners·필수 status check 3종·linear history·force-push 차단·deletion 차단·administrators 포함
  - Kiki가 5분 작업, 완료 시 이 MEMORY 항목 *상태*를 갱신
**근거**:
- **CODEOWNERS 가치**: 보호 규칙 없이도 *PR 자동 리뷰어 지정* 자체 동작. 향후 영역별 도메인 파트너 합류 시 영역만 갱신하면 자동 라우팅
- **CI workflow가 보호의 80%**: "필수 상태 검사 통과" 정책은 *워크플로 자체가 존재*해야 GitHub Settings에서 등록 가능. 즉 보호 규칙은 워크플로의 *적용 정책*이지 *내용*이 아님 — 내용을 미리 갖춰두면 UI 단계는 5분
- **policy-guard job**: CLAUDE.md 절대 금기(검정교과서 본문·하드코딩 시크릿)를 사후 사람 리뷰가 아닌 *기계적 사전 차단*으로 강제. 1인 단계 휴먼 에러 방지
- **MCP 도구 부재의 한계 인정**: 시도조차 안 한 게 아니라 *시도→불가→대안* 흐름을 명시. 향후 GitHub MCP가 branch_protection 도구를 추가하면 그때 자동화. 또는 GitHub App 토큰을 secret으로 받아 workflow 안에서 GH API 호출하는 자기참조 자동화도 가능 (Phase 2 검토)
**대안**:
- *GitHub Actions 워크플로 안에서 GH API로 보호 규칙 셀프 적용* — 자기 워크플로가 자기 보호 규칙을 만드는 *부트스트랩 문제* + Personal Access Token 필요. Phase 2에서 GitHub App 도입 시 검토
- *Pre-receive hook* — GitHub 자체 호스팅 아닌 한 불가
- *완전 수동* — CODEOWNERS·CI 없이 UI만으로는 *어떤 status check가 있는지 모름*. 폐기 이유: 자동화 가능한 80%를 굳이 미룰 이유 없음
**적용 범위 (이번 작업)**:
- 신규: `.github/CODEOWNERS` (27 lines), `.github/workflows/ci.yml` (3 jobs), `.github/branch-protection-setup.md` (UI 단계별 + 트러블슈팅)
- 미적용 (이번 작업 범위 외): UI 보호 규칙 자체 — Kiki가 위 가이드 따라 5분 작업 후 이 항목 *상태* 갱신
**상태**: 확정. main 브랜치 보호 규칙 적용 완료 (2026-05-15): PR 1+승인·Code Owners·CI status check 3종(`data-pipeline`·`infra/phaiakes9`·`policy-guard`)·linear history·force-push 차단·deletion 차단·administrators 포함. 1인 단계 Code Owner 자기 승인 충돌은 Phase 2 합류 시 자연 해소(가이드 §트러블슈팅 참조). 검증용으로 PR #1(이 세션 10개 커밋 통합)을 생성하여 CI 첫 가동·status check 등록. → **2026-05-20 정정**: 이 '자연 해소' 가정은 PR #3 머지 시 실제 하드 데드락으로 드러나, 솔로 설정(승인0·Code Owners 미요구)으로 변경 — 위 *2026-05-20: `main` 보호 자기 승인 데드락* 로그 참조.

### 2026-05-13: M1.1 게이트를 *M1.0a 머신 셋업 + M1.1 벤치마크*로 분리
**컨텍스트**: `/implement backend:phaiakes9-qwen3-math` 위임으로 Ollama 설치·systemd unit·헬스체크·벤치마크 스크립트(`infra/phaiakes9/`, 커밋 `b75730b`, 11 files +1725) 완성 후 Kiki에게 Phaiakes9 콘솔 실행 안내. 그러나 Phaiakes9 머신 자체가 *아직 셋업 안 된 상태*(OS 미설치·전원 OFF·미조립 중 하나)임이 확인됨. 기존 ROADMAP·MEMORY는 *기술 스택 결정*으로 Phaiakes9를 명시했을 뿐, *물리 머신의 부팅·SSH·드라이버 상태*는 별도 추적되지 않았음. 결과적으로 M1.1 게이트("Phaiakes9 Qwen3-Math p50<2s 측정")가 *두 가지 다른 단계*를 한 줄에 묶고 있었음 — (a) 물리·OS·드라이버 셋업, (b) Ollama 운영·벤치마크. 둘은 의존하지만 *책임 주체·자동화 가능성*이 다름.
**결정**:
- M1.1 게이트를 두 단계로 분리:
  - **M1.0a — Phaiakes9 머신 셋업** (수동 + `bootstrap.sh`): Ubuntu 24.04 설치·계정·SSH 키·sshd 하드닝·ufw 방화벽·시간 동기·ROCm(또는 CPU 폴백)
  - **M1.1 — Qwen 벤치마크 게이트**: 기존 README §2 빠른 시작 + `benchmark/run_bench.sh` → `gate_p50_under_2s == true` 판정
- M1.0a 산출물: `infra/phaiakes9/SETUP_GUIDE.md`(약 200 lines, 6 Phase 체크리스트 + 트러블슈팅) + `infra/phaiakes9/bootstrap.sh`(8단계 멱등 부트스트랩, `WHYMATH_SKIP_ROCM`·`WHYMATH_LAN_CIDR` 환경변수)
- M1.0a Phase는 Kiki 수동 작업 의존(하드웨어 상태). 그동안 *블로킹 없는* 독립 작업 진행 가능: NCIC 크롤러·main 보호 규칙·L4 프롬프트 작성·FastAPI 스캐폴딩
**근거**:
- **머신 셋업과 운영 분리의 책임 명확화**: bootstrap은 *재현 가능한 자동화*이지만 BIOS·파티션·SSH 키 등록은 *Kiki만 할 수 있는 결정*. 한 게이트에 묶이면 게이트 통과 정의가 모호해짐
- **Strix Halo APU 특수성**: AMD Ryzen AI Max+ 395는 ROCm 정식 지원 목록에 *아직 미포함*(gfx1151). `HSA_OVERRIDE_GFX_VERSION=11.5.1` 강제 또는 CPU 폴백 결정이 필요한데, 이 판단은 *벤치마크 결과를 보고* 내려야 함. 즉 M1.0a → 1차 벤치마크 → 재조정 루프가 자연스러움
- **컨텍스트 위생**(CLAUDE.md): M1.1 게이트가 *두 가지 다른 진실*을 가지면 진행 보고가 모호해짐. 분리하면 각각 binary pass/fail
- **병렬 작업 금지 원칙과 양립**: M1.0a가 Kiki 수동 작업이므로 Claude/AI 측에서는 *다른 독립 작업* 진행이 정당함(같은 AI가 두 코드 영역 병행이 아님)
**대안**:
- *분리하지 않고 게이트 텍스트만 보강* — "Phaiakes9 머신 셋업 + 벤치마크 p50<2s"로 두 줄. 폐기 이유: 셋업 자체에 1~2주 소요 가능성, 별도 추적 필요
- *Phaiakes9 셋업을 Phase 0 청사진 단계로 소급* — 청사진은 이미 종료. ROADMAP 재작성 부담 큼
- *클라우드 GPU 인스턴스로 임시 우회* — Ryzen AI Max+ 395의 *실제 비용·지연*을 못 잡으므로 게이트 신뢰도 손상. CLAUDE.md "비용 구조를 로컬 LLM 우선" 결정의 검증 무력화
**적용 범위 (이번 작업)**:
- 신규 파일: `infra/phaiakes9/SETUP_GUIDE.md`, `infra/phaiakes9/bootstrap.sh`
- 수정: `infra/phaiakes9/README.md` (M1.0a 안내 섹션 + 디렉토리 트리 갱신 + 자리표시자 `<whymath-root>` 명시화)
- 후속 (이번 작업 범위 외): `ROADMAP.md` 90일 Day 1~14 항목에 *M1.0a 머신 셋업* 한 줄 추가 (별도 PR)
**상태**: 확정. M1.0a 완료 시점에 *별도 결정 로그*로 결과 기록 예정.

### 2026-05-13: Phase 1 MVP 진입 학년 = *고1 내신*, 도메인 파트너 영입은 *M1.3까지 지연*
**컨텍스트**: `/plan Phase1-MVP` 세션에서 두 가지 미해결 의사결정을 동시에 처리해야 했음 — (1) 첫 진입 학년 선택(중2 자유학기제 vs 고1 내신), (2) 도메인 파트너 영입 트랙(KAIST 영재교육원 / 한국수학교육학회 / 대학 수교과 개별 / 셋 다 동시). Phase 1은 *1개 학년·2개 모드*에 깊게 집중한다는 원칙(`docs/architecture/06_application_modes.md` Phase 1 진입점) 하에 결정 필요.
**결정**:
- **첫 진입 학년 = 고1 내신** 단일 트랙. 중2 자유학기제는 Phase 3~4 자유학기제 모드로 미룸(`06_application_modes.md` 모드 6)
- **도메인 파트너 영입 = 명시적 지연**. Day 1~14 핵심 행동 목록에서 제외하고 M1.3(월 3) 이전까지 1명 확보를 후행 게이트로 재배치. Phase 1 종료 게이트(M1.6)의 *도메인 파트너 검수 통과*는 유지
- 게이트 재조정: M1.1 게이트에서 "파트너 구두 동의" 항목 *삭제*, 대신 "Phaiakes9 Qwen3-Math 응답 속도 p50<2s 측정 완료 + NCIC 크롤러 가동"으로 교체
**근거**:
- **고1 내신 선택**: 학부모 결제 의지가 가장 강함 → Phase 1.5~2 결제 시스템 출시 시 전환율 최대화. 내신 점수는 정량 효과 검증이 가능(메타인지·사고력 효과를 단순 수치로 입증). Phase 2 수능·내신 모드(`06_application_modes.md` 모드 2)와 자연스러운 콘텐츠 연결. 반면 중2 자유학기제는 B2B 학교 진입로 매력은 크나 Phase 1의 *β 100명 무료* 단계에서는 매출 신호가 약하고, 학교 단위 진입은 영업 사이클이 6개월 이상이라 Phase 4 B2B 단계에서 다루는 게 시기 적합
- **도메인 파트너 지연**: 영입 자체는 1순위 미해결 의사결정이나, Day 1~14에 *동시 접촉*하면 비기술 작업이 기술 토대 작업(LLM 배포·크롤러·데이터 카드)을 블로킹할 위험. CLAUDE.md "병렬 작업 금지" 원칙(게이트 미달 대응 액션 3)과도 충돌. 사람 수학자 1명의 단발 검수(M1.2)는 도메인 파트너 없이도 확보 가능 → 영입은 *기술 토대가 보여줄 자산이 생긴 후* M1.2~M1.3 사이 진행이 협상력 측면에서 유리
- **고1 내신의 리스크**: 사고력 모드와 내신 압박이 정서적으로 충돌할 수 있음 → L4 정서 안전 필터·프롬프트 설계에서 *내신 점수를 KPI로 강화하지 않는* 톤 유지 필요(CLAUDE.md "정답을 빠르게 KPI 금지")
**대안**:
- *중2 자유학기제* — B2B 진입로·게이미피케이션 절제 용이성 매력. 폐기 이유: Phase 1 β 매출 신호 약함, 학교 영업 사이클 길음
- *둘 다 동시* — 콘텐츠·범위 폭발, MEMORY.md 폐기 패턴 "처음부터 풀 K-12" 위반
- *도메인 파트너 셋 다 동시 접촉* — 리스크 분산은 매력이나 비기술 작업이 기술 토대를 블로킹할 위험·"병렬 작업 금지" 위반
**적용 범위 (이번 작업)**:
- MEMORY.md 미해결 의사결정 섹션 갱신 (첫 진입 학년 항목 *확정으로 이동*, 도메인 파트너 항목 *M1.3 게이트로 재태깅*)
- 후속 작업: ROADMAP.md M1.1 게이트 텍스트 조정, `docs/architecture/06_application_modes.md` "Phase 1 진입점" 주석에 *고1 내신 트랙* 명시 — 별도 PR
**상태**: 확정. 다음 단일 행동은 Phaiakes9에 Qwen3-Math 배포 + NCIC 크롤러 작성 + GitHub `main` 보호 규칙 적용 3건의 *서로 블로킹 없는* 병렬 작업.

### 2026-05-14: GitHub 원격 저장소 연결 (Private)
**컨텍스트**: Phase 0 청사진(7계층·기술 스택·브랜드명)이 모두 확정된 시점. 로컬 git 저장소만 존재했고, 클라우드 백업·미래 협업·CI/CD 기반·코드 리뷰 워크플로의 인프라가 필요한 상태였음. 또한 `WhyMath_harness.zip`·`files.zip` 두 개의 대용량 아카이브가 git에 추적되어 있어 푸시 시 누적 부담이 됨.
**결정**:
- 호스팅: **GitHub**, 레포 URL `https://github.com/doldori7/WhyMath` (Private)
- 기본 브랜치: `main` (GitHub 표준, 기존 `master`에서 변경)
- 사전 정리: `files.zip`·`WhyMath_harness.zip` 추적 해제(working tree는 보존), 사업계획서 docx/pdf는 사용자가 별도 위치로 이동
- `.gitignore` 보강: `*.zip`·`*사업계획*`·`*business_plan*`·`internal/`·`private/`·`.env.*`·`config/secrets.*`·`.openai_cache/`·`.anthropic_cache/`·`.langfuse_cache/`·`data/cache/` 등 약 25개 패턴 추가 (멱등 마커 `# WhyMath 추가 보안 패턴 (자동 생성)`로 중복 추가 방지)
- 자동화: `scripts/01_git_local_setup.ps1`(로컬 정리)·`scripts/02_github_connect.ps1`(GitHub 연결) 두 PowerShell 스크립트로 재현 가능
**근거**:
- **Private 필수**: CLAUDE.md 절대 금기 — "미성년자 개인정보를 분석·마케팅 외부 공유 금지" 및 "학교·학년 정보로 개인 식별 가능한 분석 결과 외부 노출 금지" → 코드 자체에는 학생 데이터가 없지만 향후 시드 데이터·테스트 픽스처에서 실수 노출 가능. Public은 위험 비대칭
- **`main` 브랜치 표준화**: GitHub Actions·외부 도구·튜토리얼 거의 모두 `main` 가정. Phase 1에서 CI/CD 구축 시 마찰 최소화
- **zip 추적 해제**: 1.12 MiB 초기 푸시도 아카이브 없이 진행. 추후 LFS 도입 부담 사전 차단
- **`.gitignore` 사전 보강**: 시크릿·민감 문서가 한 번 푸시되면 git history에 영구 박힘. 사전 패턴 차단이 사후 BFG/filter-repo 대응보다 압도적으로 저렴
**대안**:
- GitLab — 프라이빗 무료 한도가 크지만, 한국 시장에서 GitHub가 인재 풀·생태계 압도. 협업자 합류 시 추가 학습 비용
- 자체 Gitea — Phaiakes9에 호스팅 가능하나 백업·가용성을 직접 관리해야 함. 1인 단계에서 비효율
- 공개(Public) 레포 — 부분 오픈소스 전략은 매력적이나 *현 단계*에서는 도메인 노하우 누출 리스크가 더 큼. Phase 2 이후 *선별적* 공개 검토
**적용 범위 (이번 작업)**:
- 커밋 `0625cf5`: `.claude/settings.json`·`.gitignore`·zip 2개 삭제·사업계획서 docx/pdf 2개 삭제·스크립트 2개 추가
- 푸시: 104 objects, 1.12 MiB, `main → origin/main` upstream 설정 완료
**상태**: 확정. 후속 작업이었던 `main` 보호 규칙 적용은 2026-05-15 완료 (위 *2026-05-14: `main` 보호* 결정 로그 §상태 참조).

### 2026-05-14: 브랜드명 "WhyMath (와이매스)" 확정
**컨텍스트**: Phase 0 종료 직전, 모든 외부·내부 문서가 일관된 브랜드명을 사용해야 함. 그동안 "한국 중·고 수학 앱"이라는 서술적 가칭 사용
**결정**:
- 정식 앱명: **WhyMath** (한글 표기: **와이매스**)
- 메인 슬로건 (KR): **"답이 아닌, 이유를 묻는 수학"**
- 메인 슬로건 (EN): **"The math that asks why."**
**근거**:
- 핵심 가치 제안(답 미루기·Polya·소크라테스)을 한 단어로 압축
- "Why"는 메타인지·사고력 시장 진입점과 직결, 영문 확장(Phase 5) 시 그대로 사용 가능
- 콴다·EBSi 등 한국 경쟁자와 *이름 단계*에서부터 차별화
**적용 범위 (이번 작업)**: CLAUDE.md / README.md / MEMORY.md / ROADMAP.md / docs/strategy/{market_positioning,differentiation}.md / scripts/setup.sh / .claude/agents/data-engineer.md / .claude/commands/status.md / src/backend/pyproject.toml
**미적용 (별도 작업 예정)**: Python 패키지명 `korean-math-backend`, DB명 `koreanmath`, 모바일 앱 ID 등 *코드 식별자*는 마이그레이션 영향 검토 후 일괄 변경
**상태**: 확정

### 2026-05-13: 시장 진입점을 *메타인지 사고력*으로 결정
**컨텍스트**: 콴다(사진 풀이)·EBSi(강의)·메가스터디(콘텐츠)와 정면 경쟁 불가  
**결정**: "수능 답 풀이"가 아닌 *메타인지·소크라테스·NRICH-style 사고력*에서 시작  
**근거**: Kiki의 메타인지 튜터 자산 직결, 한국 경쟁자 거의 없음, Phase 2에서 수능 시장 진입할 발판  
**대안**: 영재 트랙 우선 — 객단가 높지만 시장 작음, 도메인 파트너 부족  
**상태**: 확정

### 2026-05-13: 데이터 truth source를 *성취기준 코드*로 결정
**컨텍스트**: 검정 교과서 13종·평가원·EBS·학원 등 다층 구조에서 무엇이 진실 원천인가  
**결정**: 교육부 NCIC 성취기준 코드(예: `[9수01-01]`)가 모든 매핑의 root  
**근거**: 모든 출판사가 법적으로 이 코드를 따라야 함, 공공누리 라이선스, 변하지 않음  
**상태**: 확정

### 2026-05-13: 7계층 아키텍처 확정
**결정**: L1 데이터 → L2 학습자 모델 → L3 LLM → L4 교수학 → L5 상호작용 → L6 응용 → L7 커뮤니티  
**근거**: 책임 분리, 유지보수성, 서브에이전트 위임 단위와 일치  
**상태**: 확정. *경계 침범 금지*가 절대 원칙

### 2026-05-13: 비용 구조를 *로컬 LLM 우선*으로 결정
**결정**: Phaiakes9 (Ryzen AI Max+ 395, 128GB) + Qwen3-Math로 80% 처리, 18% Claude/GPT 중급, 2% 최고급  
**근거**: 학생 1인당 일 50~100회 LLM 호출 가정 시 클라우드만 사용하면 객단가 폭발  
**상태**: 확정. 동적 라우터 구현 필요

### 2026-05-13: LLM 답변 패턴을 *답 미루기*로 결정
**결정**: 학생 질문에 *바로 답하지 않음*. Polya 4단계로 진행. 답 제공은 4단계(방향→의사코드→부분→전체) 중 가능한 빠른 단계에서 멈춤  
**근거**: NRICH·Khanmigo가 수렴하는 방향. 한국 학생의 *답 즉시 의존* 패턴이 학습 저해  
**상태**: 확정. 모든 프롬프트 템플릿이 이를 반영해야 함

### 2026-05-13: 데이터 활용 안전선 확정
**결정**: 
- ✅ 가능: 성취기준·기출·학교 정보·OER(CK-12·OpenStax·Siyavula CC), Mathlib(Apache 2.0), 사용자 자기 자료
- ⚠️ 협상 후: NRICH(Cambridge MMP), EBS, AoPS Wiki(CC BY-SA)
- ❌ 절대 금지: 검정 교과서 본문, 학원·인강 콘텐츠, 출판사 풀이집  
**상태**: 확정. `docs/data/licensing_safety.md` 참조

---

## 📚 폐기된 접근 (Anti-Patterns)

### "단순 사진→답 풀이 앱"
**왜 폐기**: 콴다와 정면 충돌. 자본 게임에서 밀림. 그리고 *교육적으로 해롭다* (의존성 강화).

### "AI가 모든 걸 한다" 일체형 LLM 접근
**왜 폐기**: LLM 단독으로는 학습자 모델링·장기 추적·정확도 보장 불가. BKT/IRT 통계 모델 분리 필수.

### "수능 직접 진입"
**왜 폐기**: 입시 검증에 1~2년 걸림. 학부모 신뢰 형성 시간 필요. 메타인지로 신뢰 누적 후 진입이 안전.

### "처음부터 풀 K-12"
**왜 폐기**: 범위 폭발. 1개 학년 검증 후 확장이 위험 관리.

---

## 💡 핵심 인사이트 (장기 보존)

### 1. AI의 진짜 강점은 *답*이 아니라 *질문*
LLM은 답을 빠르게 주는 도구가 아니라, *학생이 스스로 도착하게 만드는* 도구로 쓸 때 가장 강력. 모든 프롬프트 설계의 출발점.

### 2. 한국 시장의 *진짜* 빈자리
- 사고력·메타인지 자원 (NRICH·YouCubed 한국어로 없음)
- 단계별 진단 (콴다는 사진 풀이만, 단계 분석 없음)
- 부모용 인사이트 (학원이 못 채움)
- 사고 과정 *시각화* (3Blue1Brown 한국화 빈약)

### 3. 데이터 자산 = 1~2년 누적 후 *제품과 별도로* 라이선싱 가능
NCIC + 학교알리미 + 검정교과서 매핑 + KMO 디지털화 = B2B 라이선싱 가능한 자산.

### 4. 로컬 LLM은 *비용*이 아니라 *전략*
Phaiakes9를 단순 비용 절감이 아닌 *경쟁자가 못 가진 인프라*로 인식. 클라우드 비용 폭발기에 *유일한 흑자 모델*.

### 5. *부족한 한 자리*: 수학 교육 도메인 파트너
한국에서 Kiki의 자산 조합이 거의 유일하나, *수학 교육 도메인 전문가*가 결정적 빈자리. 1순위 영입 과제.

---

## 🔗 외부 의존성 모니터링

### 라이선스 변경 가능성
- **NuminaMath**: Apache 2.0, 안정
- **MathNet (MIT 2026)**: 막 공개됨, 라이선스 정확 확인 필요
- **NRICH**: 비상업 무료, 상업 라이선스 협상 필요
- **AoPS Wiki**: CC BY-SA, Share-Alike 의무
- **Mathlib**: Apache 2.0, 안정

### 정책 변동 모니터링
- AI 디지털교과서 정책 (정권 영향 큼)
- 2022 개정 교육과정 시행 일정 (2025~2027 단계적)
- 영재교육원 예산·체계 변화
- 사교육비 경감 대책 (시장 영향)

---

## 🧪 실험 로그 (착수 후 누적)

*아직 실험 없음. Phase 1 착수 시 누적 시작.*

| 날짜 | 실험 | 가설 | 결과 | 결정 |
|---|---|---|---|---|
| | | | | |

---

## 🎯 KPI 베이스라인 (정의만 — 측정 시작 후 채움)

### 학습 효과
- 개념 숙달도 (BKT 확률 증가율)
- 오개념 해소율
- 다중 풀이 노출 후 *대안 풀이 시도율*

### 사용자 행동
- 일일 활성 사용자 (DAU)
- 세션당 *답 미루기 단계* 평균 도달 깊이 (1~4)
- 학생이 *스스로* 풀이 도달한 비율

### 비용·기술
- LLM 호출당 평균 비용
- 로컬 LLM 처리 비율 (목표: 80%)
- 응답 지연 (목표: p50 < 2s)

### 사업
- MAU·결제 전환율·이탈률
- B2B 학교 수·교육청 수
- 데이터셋 라이선싱 매출

---

## 📝 다음 업데이트 시점

- 각 결정 발생 시 *즉시*
- 각 Phase 시작·종료 시
- 매월 첫째 주 (정기 리뷰)

---

**최종 수정**: 2026-05-28  
**다음 정기 리뷰**: Phase 1 착수 후 첫 월
