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
- 📋 **다음 세션 후보 (서로 블로킹 없음)** — ① **M1.2 라이브 연동**(S1·S2·S3 *완료* — 위 ✅ 참조; S4~S5 후속: QUALITY 큐·클라우드) ② **빌드타임 사전생성 파이프라인**(Max 활용 코퍼스·캐시 — 2026-05-20 Max/API 결정 로그) ③ **(Kiki·Phaiakes9) per-call-site 크기 재실측**(`ollama pull bge-m3` → `quality_eval.py` @`127.0.0.1` GPU — extract 임베딩 의미매칭 포함) ④ **클라우드 티어 실연동**(03a §H#4) ⑤ **24/7 서버 운영 설계**(Phaiakes9 상시 가동)
- 📋 **Phaiakes9 카탈로그 cosmetic 정리** (별도 PR) — README.md 7군데, SETUP_GUIDE.md 1군데, 주석 4군데. 코드 동작 영향 없음, 문서 일관성만
- 📋 **Phaiakes9 systemd unit `ProtectSystem=full` 완화** (별도 PR) — `failed to persist model recommendations snapshot ... read-only file system` 경고 해소. `ReadWritePaths=/usr/share/ollama` 추가
- ✅ 완료: PRD v1.1 정합성 정렬(단계 1~5, `fd23115`~`b8d6d3d`) / CI 툴체인 점검(`3b9ff72`) / 곁다리 2건(`df03eaa`) / **NCIC PDF crawl baseline**(629건 추출, 5% 검수 완료, 2026-05-15 결정 로그) / **`main` 보호 규칙 적용**(2026-05-15, PR #1로 CI 첫 가동·status check 등록) / **M1.0a Phaiakes9 1차 셋업** (2026-05-15, NucBox EVO-X2 + WSL2) / **M1.1 CPU baseline** (qwen2-math:7b, 12.62 tok/s @ concurrent 1) / **M1.1 GPU 가속 활성화** (2026-05-16, Windows Ollama 경유 DirectML, qwen2-math:7b 32.63 tok/s + qwen3.5:27b 9.22 tok/s, CPU 대비 2.6x — 옵션 A1 채택) / **M1.1 fast tier 후보 측정** (2026-05-19, qwen2-math:1.5b GPU 124.25 tok/s @ c=1, p50 1010ms — L3 SLA 게이트 PASS, fast/mid/quality 3단계 라인업 결정) / **인터페이스 정렬·main 보호 데드락 정정·Max=빌드타임/API=런타임 결정** (2026-05-20, PR#4) / **L3 라우터 M1.2 구현** (2026-05-20, `whymath_backend/l3` 결정로직+타입 인터페이스+백엔드 CI 잡, PR#5) / **FAST tier 품질 검증 종결 + 태스크 패밀리 라우팅 확정** (2026-05-20, 결론: *수학=`qwen2-math`·NLP=`qwen2.5`* — 수학모델로 NLP는 7b조차 0%; 하니스(`<ANSWER>`·temperature=0·임베딩 의미매칭·코드추출) + 03a 축3 `ModelFamily`(§0.2·A.0·C.0·§H 후속8~12) + 라우터 코드 family 축·호출지점별 크기, PR#6~#14. 설계·인터페이스·코드·하니스 완전 정합)

### 완료된 마일스톤
- 2026-05: 7계층 아키텍처 확정
- 2026-05: 기술 스택 확정 (Flutter + FastAPI + PostgreSQL + Phaiakes9)
- 2026-05: Phase 진입 순서 확정 (메타인지 사고력 → 학교 진도 → 수능 → 영재 → B2B)
- 2026-05-14: GitHub 레포 `doldori7/WhyMath` (Private) 생성 및 첫 푸시 완료

### 미해결 의사결정
- [ ] 수학 교육 도메인 파트너 영입 (M1.3 게이트로 *지연 확정* — 트랙 미정)
- [x] ~~첫 진입 학년~~ → **고1 내신** 확정 (2026-05-13, PRD v1.1 채택 후에도 유지)
- [ ] 벡터 DB: ChromaDB 유지 vs Qdrant 전환 (PRD v1.1 채택으로 발생 — 정렬 단계3 L1/L5에서 결정)
- [ ] 사단법인·재단·법인 형태
- [ ] Cambridge MMP/NRICH 라이선스 협상 시작 시점

---

## 🧭 핵심 결정 로그 (시간 역순)

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

**최종 수정**: 2026-05-20  
**다음 정기 리뷰**: Phase 1 착수 후 첫 월
