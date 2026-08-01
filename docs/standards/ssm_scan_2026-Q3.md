# SSM 분기 스캔 2026-Q3

> **작성일**: 2026-07-09 (최초) · **보강**: 2026-07-10 | **이전 스캔 대비 델타**: 최초 스캔(위임 조사, PR #493 병합) 이후 (1) 라이브 웹 1차 출처 재조사로 신규 후보 3건 추가(#14~#16) 및 기존 후보 8건(#1·2·3·4·10·11·12·13) 근거 갱신 (2) 트랙 B S1 계측 스모크 결과 반영(구조적 제약 정정) — **기존 #1~13 번호·판정 구조는 보존**(`ssm_activation_handoff.md` 트랙 C가 #1·2·4·8·10·12를 번호로 직접 참조하므로 재번호 금지) | **스캐너**: Claude Code(위임 조사, 2회차는 1차 출처 교차검증 포함) + Kiki 검수 대기
>
> **근거 표준**: `system_superiority_maintenance.md`(SSM v1.0). 4대 축을 §3 정의대로 순회하고, 각 후보를 §5 도입 게이트(우선순위 종속·측정 없는 도입 없음·구조 붕괴 방어)에 걸어 §5-③ 4종(도입/파일럿/보류/기각) 또는 유지/관찰로 1차 판정.
>
> **⚠️ 이번 스캔의 구조적 제약(2026-07-10 갱신)**: 도입 게이트 §5-(b) *"측정 없는 도입 없음"*. **트랙 B S1 스모크 테스트 완료**(`MEMORY.md` 2026-07-09 실측·SSM/계측선 항목, 커밋 `46be270`): Langfuse 라이브 기록 가동 확인·CLOUD_MID 10콜(≈0.41원/콜·p50 1020ms)·LOCAL 27콜(0원·p50 739ms), 둘 다 SLA(p50<2,000ms) 통과. 그러나 **측정 프롬프트가 5토큰 비대표 출력**이라 라우터 비용상수(`_EST_ASSUMED_*`) 보정과 대표 트래픽 실측(S3~S4)은 미완 — `ssm_activation_handoff.md` **트랙 C(파일럿 측정·재판정)는 아직 착수 전**. 따라서 **본 스캔도 "도입" 판정 0건 유지**, 유망 후보는 전부 *파일럿(트랙 C 측정 대상 추가)*·불확실은 *보류*로 귀결한다. 스택 실변경 0 → CLAUDE.md 기술 스택 표 미변경. **계측 인에이블러 상태**: 미가동 → 스모크 완료(격상) → 완전 가동은 트랙 C(대표 트래픽 S3~S4) 완료 시.
>
> **불확실 표기**: 1차 출처(공식 릴리스·arXiv·벤치 리더보드) 교차검증된 항목만 판정에 반영. SEO 블로그 단일 출처 수치(모델 버전·점수)는 `[불확실]`로 표기하고 판정을 유보한다. **2026-07-10 재검증 완료**(외부 분석 검토 요청 계기): DeepSeek-V4-Pro MIT 라이선스·1.6T total/49B activated·1M ctx(huggingface.co/deepseek-ai/DeepSeek-V4-Pro LICENSE·api-docs.deepseek.com/news/news260424) / Qwen3.6-35B-A3B Apache 2.0(huggingface.co/Qwen/Qwen3.6-35B-A3B) / Claude Sonnet 5 공식 가격 $2/$10→2026-08-31 이후 $3/$15(anthropic.com/news/claude-sonnet-5) — 전부 1차 출처 확정, `[불확실]` 해제.

---

## 축별 관찰

### ① 모델·LLM

현행 베이스라인: 로컬 fast/mid/quality = `qwen2-math:1.5b`(p50 1,010ms·124 tok/s·SLA PASS) / `qwen2-math:7b` / `qwen3.5:27b`, 태스크 패밀리 라우팅(수학=qwen2-math·NLP=qwen2.5), 클라우드 티어 라우터 경유(Claude/GPT-5/Gemini 2.5). (MEMORY 2026-05-16~20 결정)

| # | 후보 | 신호(우월성) | 리스크 | 1차 판정 |
|---|---|---|---|---|
| 1 | **DeepSeekMath V2 / DeepSeek-V3.2** (MIT·수학 SOTA) | 수학 특화 + 오픈웨이트/MIT. **갱신**: DeepSeek는 2026-04 **V4 Pro**(MIT·1.6T/49B act·1M ctx)도 공개 — 로컬 서빙 불가 확정, 본 항목은 V3.2로 한정(V4 Pro는 #15) | 대형 MoE 로컬 GPU 부담·성숙도 초기 | **파일럿** |
| 2 | **Qwen3 후속 수학·추론 라인** | Apache 2.0·0.6B~32B 경량 | AIME/HMMT은 DeepSeekMath V2에 밀릴 수 있음 | **유지 + 인지** |
| 3 | **PRM 재랭킹** (Qwen2.5-Math-PRM 등) | **갱신**: ThinkPRM(1% label로 discriminative 상회)·R-PRM(ProcessBench F1 +8.7) 신세대 확인 | 학술 공개 초기 단계 | **파일럿** |
| 4 | **클라우드 프론티어 신버전** | **확정**: Claude Sonnet 5(2026-06-30 출시) $2/$10(~8/31)→$3/$15 | 인트로가 종료 후 재평가 필요 | **파일럿**(CLOUD_MID A/B, 인트로가 종료 전 실측 권장) |

멀티모달 손글씨 수식(HMER): 범용 VLM은 손글씨 수식에서 오차 전파 지속 보고(Uni-MuMER·VEHME·FERMAT) → **현 "PaddleOCR + Qwen3-VL 하이브리드" 설계 방향 자체는 재확인됨**(③축 OCR과 연결).

**신규 후보 (2026-07-10 추가)**:

| # | 후보 | 신호(우월성) | 리스크 | 1차 판정 |
|---|---|---|---|---|
| 14 | **Qwen3.6-35B-A3B** (Apache 2.0, 2026-04-16 출시) | Sparse MoE — activated 3B 부하로 AIME 2026 92.7점(35B급). **#1 V4 Pro가 로컬 배제된 후 로컬 quality 티어 유일 신후보** | 벤치 일부 SEO 집계 출처 — 공식 재확인 권장 | **파일럿**(Phaiakes9 tok/s·p50 + 수학 A/B vs qwen3.5:27b) |
| 15 | **DeepSeek V4 Pro** (MIT·1.6T/49B act·1M ctx) | GPQA Diamond 90.1·1M ctx. 라이선스 완전 개방 | **로컬 서빙 불가 확정** — 클라우드 이용 시 신규 프로바이더 필요(현 CompositeProvider=Anthropic 단일). **구조 금기 경고**: 1M ctx라도 전체 그래프 통째 투입은 Minimal Reasoning Subgraph(depth≤2·max_nodes≤12~20·≤3000 tokens) 위반 | **보류**(로컬 불가·신규 프로바이더는 별도 결정. 재검토=Anthropic 단일로 커버 안 되는 니즈 발생 시) |

출처: arxiv.org/pdf/2512.02556 · api-docs.deepseek.com/news/news251201 · api-docs.deepseek.com/news/news260424 · huggingface.co/deepseek-ai/DeepSeek-V4-Pro · huggingface.co/Qwen/Qwen3.6-35B-A3B · qwenlm.github.io/blog/qwen3 · github.com/RyanLiu112/Awesome-Process-Reward-Models · arxiv.org/pdf/2505.23566 · arxiv.org/abs/2504.16828 · anthropic.com/news/claude-sonnet-5 · platform.claude.com/docs/en/about-claude/pricing

### ② 데이터

현행 베이스라인: 법적 안전조합(NCIC 성취기준·공공누리 AI유형·AIHub + LLM 학습용 NuminaMath/PRM800K/PhET). EBS·평가원·검정교과서 본문은 자체 동등문제로 대체(`licensing_safety.md` 가이드 v2.0).

| # | 후보 | 신호 | 리스크 | 1차 판정 |
|---|---|---|---|---|
| 4 | **NuminaMath-1.5** (Apache 2.0·~90만 경쟁수학 + CoT) | **2026-07-10 확정**(huggingface.co/datasets/AI-MO/NuminaMath-1.5): Apache 2.0 라이선스 1차 출처 확인 — 상업 이용 가능 대규모 코퍼스 | GPT 계열 합성분의 약관/저작권은 여전히 보수적 검토 권장(데이터셋 저장소 라이선스와 별개 사안) | **파일럿**(약관 검토 전제) |
| 5 | **AIHub 한국 수학 데이터** (2022 개정 정합·손글씨 18만↑·문제 생성 8.4만↑) | 한국 교육과정 정합 + 손글씨 이미지 → OCR/튜터링에 직결(미션 최적합) | **공공누리 유형이 제2유형(CC BY-ND·비상업)일 가능성** → 상업 투입 전 각 페이지 개별 확인 필수(KPI #3 법적 안전) | **보류**(유형 실확인 전 투입 불가) |
| 6 | **MegaMath·Nemotron-Math·OpenMathInstruct-2** (초대규모 웹+합성) | 압도적 규모(수백 B 토큰) | 라이선스·출처 혼재(웹크롤)·한국 교육과정 정합 낮음 | **기각**(미션·라이선스 부적합) |
| 7 | **Lean4 형식검증 계열** (FormalMATH·CriticLeanBench) | 풀이 정답 검증(verifier) 파이프라인 보강 | WH-S Tier3 종속·장기 보류 항목(ROADMAP) | **보류**(WH-S Tier3 시점) |

**신규 후보 (2026-07-10 추가)**:

| # | 후보 | 신호 | 리스크 | 1차 판정 |
|---|---|---|---|---|
| 16 | **OpenR1-Math-220k** (Apache 2.0, NuminaMath-1.5 기반 파생) | DeepSeek R1이 생성한 2~4개 추론 트레이스가 붙은 22만 문항 — RL/SFT 학습용으로 #4보다 더 즉시 사용 가능 | #4와 동일 계열(NuminaMath 파생) — 약관 검토는 #4와 결선 처리 | **파일럿**(NuminaMath-1.5(#4) 법적 검토와 연동) |

출처: emergentmind.com/topics/numinamath-dataset · aihub.or.kr(dataSetSn=71859·71716·71718) · arxiv.org/pdf/2504.02807 · arxiv.org/pdf/2507.08665 · huggingface.co/datasets/AI-MO/NuminaMath-1.5 · huggingface.co/datasets/open-r1/OpenR1-Math-220k

### ③ 인프라·스택

현행 베이스라인: Vector=pgvector(PG16·슬98), Graph=Neo4j 5, 서빙=Ollama(Phaiakes9), 임베딩=CLAUDE.md 표기 `text-embedding-3-large`.

| # | 후보 | 신호 | 리스크 | 1차 판정 |
|---|---|---|---|---|
| 8 | **임베딩 Qwen3-Embedding** (MTEB 다국어 1위 ~70.6, OpenAI 64.6·Google 68.3·bge-m3 상회, 32K, 오픈웨이트) | 한국어 검색 품질 + 자체 호스팅(미성년 PII 통제) | 8B → 임베딩 비용/지연↑(경량 0.6B/4B 변형 검토). bge-m3는 MIT·다기능으로 여전히 가성비 기본기 | **파일럿** |
| 9 | **⚠️ 임베딩 표/코드 불일치(실재 미결)** | CLAUDE.md 표=`text-embedding-3-large` ↔ 실코드=`bge-m3`(dim 1024, 슬105). 임베딩 모델 확정이 MEMORY상 미결 후속 | 문서-코드 truth 이원화(유지보수 지옥 씨앗) | **정합 정정 필요**(별도 작업 라우팅·본 스캔 판정 대상 아님) |
| 10 | **OCR PaddleOCR-VL** (OmniDocBench SOTA·수식 우위·109언어) | **2026-07-10 갱신**: v1.6이 OmniDocBench v1.6 **96.3%** 달성(공식), 한국어 edit distance **0.052**(최저권) 확인 — 단일 모델로 텍스트+표+수식 → 현 하이브리드 단순화 가능 | 손글씨 수식 전용 벤치는 미확인. **한국어 손글씨 정확도 Phaiakes9 실측(목표 90%) 전제**(기존 OCR 미결 리스크와 동일) | **파일럿** |
| 11 | **pgvector / vLLM+Ollama 현행** | **2026-07-10 갱신**: pgvector v0.8 병렬 인덱스 빌드(IVFFlat 생성 -40%)·halfvec/sparsevec 추가 — 1M 스케일 Qdrant(4ms p50)가 pgvector(11ms p50)보다 빠르나 현 규모는 미달. vLLM은 8+ 동시요청부터 처리량 우위 확대(50동시=vLLM 6x·p99<3s vs Ollama p99 24.7s) — 단일요청 TTFT는 Ollama 우위(45ms vs 82ms) | 10M+·동시요청 8+에서 Qdrant/vLLM 격차 확대(메모리 +40%·처리량 격차). 현재 학생 동시접속 규모는 8 미만 추정(트래픽 실측 필요) | **유지**(Qdrant/vLLM 전환 트리거 임계— 10M+ 벡터·동시요청 8+ — 이번 조사로 재확인·구체화, 슬98 경로 보존) |

출처: milvus.io/blog/choose-embedding-model-rag-2026 · modal.com/blog/mteb-leaderboard-article · paddleocr.ai(PaddleOCR-VL) · huggingface.co/PaddlePaddle/PaddleOCR-VL · tigerdata.com/blog/pgvector-vs-qdrant · sitepoint.com/ollama-vs-vllm-performance-benchmark-2026

### ④ 경쟁·교수학

> §3 주의: 공개 정보만. 경쟁 서비스 약관·데이터 추출 금지·비교광고성 서술 금지.

| # | 후보/동향 | 신호 | 함의 | 1차 판정 |
|---|---|---|---|---|
| | **콴다(매스프레소)** | 전과목 AI 풀이·대규모 학생/문제 DB·아시아 확장(10M+ 활성 사용자, 공개 정보) | 데이터·유통 규모 열위 → WhyMath 차별화선 = *교수학 튜터링 깊이(메타인지·답 미루기) + 교육과정 정합* | **관찰** |
| | **EBS AI(단추)·토닥토닥 수학탐험대** | 공교육 연계·교육과정 정합·문제추천(공개 정보) | 방어선 = AIHub 교육과정 데이터로 정합성 확보(②축과 연결) | **관찰** |
| | **한국 AI 교과서 시장 붕괴** (2026-07-10 신규 관찰) | 정부 AI 디지털교과서 정책이 2025-03 이후 지원 축소·전면 후퇴(공개 정보: 채택률 지역 편차 8~98%·예산 철회 보도). 공교육 채널 중심 에듀텍(정부 조달 의존)은 타격, 콴다·Riiid 등 **정부 조달 비의존 B2C**는 지속 성장 | WhyMath는 원래 학생 직접 소비(B2C) 설계 — 이 붕괴가 시장 공백을 만드는지, 혹은 AI 교육 전반에 대한 신뢰 저하로 이어지는지는 추가 관찰 필요. **전략 피벗은 SSM 소관 아님** — PRD 페르소나 전략(`docs/strategy/prd_v1.2.md`) 별도 검토 대상 | **관찰**(전략 함의는 별도 문서 라우팅) |
| 12 | **교수학 평가 루브릭** (LearnLM 루브릭·MathTutorBench answer-leakage 부정지표·MetaCLASS 메타인지 코칭) | 프롬프트 템플릿을 이 루브릭으로 자체 평가·회귀테스트하면 즉시 우월성 계측 가능(KPI #1 교수학 효과·저위험). **2026-07-10 갱신**: `ssm_activation_handoff.md` 트랙 C 확인 — `harness/pedagogical_rubric.py` **이미 존재**, 계측선(트랙 B) 없이도 선행 가능 | `prompt_engineering.md`·WH-1 평가 하네스와 결선 | **파일럿**(B 없이 즉시 착수 가능 — 트랙 C 우선순위 1순위) |
| 13 | **규제 변화**(AI 기본법 2026-01-22 시행) | **2026-07-10 갱신**(1차 출처 cooley.com·trade.gov): 고영향 AI에 **학생 평가·등급·접근권 결정 AI 시스템 명시 포함** — 영향평가·생애주기 리스크관리·투명성 의무. **1년 유예기간**(과징금은 중대한 인권침해 등 예외 제외 유예) + PIPA 만14세 법정대리인 동의 | **§4 즉시 트리거(법·규제 변화) 발동 → 법무 우선**(도입 판정 대상 아님). 유예기간 내 컴플라이언스 준비 필요(과징금 유예가 "의무 없음"을 뜻하지 않음) | **즉시 대응**(`regulatory_checklist.md` 소관) |

출처: arxiv.org/pdf/2508.06583 · law.go.kr(lsiSeq=268543) · privacy.go.kr · apps.apple.com(id1270676408) · ai.ebs.co.kr · cooley.com/news/insight/2026/2026-01-27-south-koreas-ai-basic-act-overview-and-key-takeaways · seoulz.com/korea-ai-textbook-2026

---

## 게이트 대기 큐

| # | 후보 | 축 | 판정 | 다음 액션(측정 지표·재검토 시점·소관) |
|---|---|---|---|---|
| 1 | DeepSeekMath V2 / V3.2 | ① | **파일럿** | Phaiakes9 서빙 실측(tok/s·p50) + 수학 정확도 A/B vs qwen2-math. **트랙 C 대상**(`ssm_activation_handoff.md`). 재판정=라이브 계측 가동 후 |
| 2 | PRM 재랭킹(ThinkPRM/R-PRM 포함, 2026-07-10 갱신) | ① | **파일럿** | L3 검증 커버리지·PRM 통과율 델타 측정. **트랙 C 대상**. 재판정=WH-S S2~S3 시 |
| 3 | 클라우드 프론티어 신버전(Claude Sonnet 5, 2026-07-10 확정) | ① | **파일럿**(승격: 보류→파일럿) | CLOUD_MID A/B — 트랙 B S1 계측 인프라 재사용 가능. 인트로가 종료(2026-08-31) 전 실측 권장 |
| 4 | NuminaMath-1.5 (Apache 2.0 확정) | ② | **파일럿** | 합성분 약관 법적 검토(`licensing_safety.md`). **트랙 C 대상**. 재판정=검토 완료 시 |
| 5 | AIHub 한국 수학 데이터 | ② | **보류** | 각 데이터셋 공공누리 유형(상업 가능 여부) 개별 확인. 재검토=유형 확인 즉시 |
| 6 | MegaMath 등 웹크롤 대규모 | ② | **기각** | 사유: 라이선스 혼재·교육과정 정합 낮음·미션 부적합 |
| 7 | Lean4 형식검증(FormalMATH 등) | ② | **보류** | 재검토=WH-S Tier3 착수 시(장기) |
| 8 | 임베딩 Qwen3-Embedding | ③ | **파일럿** | 한국어 의미검색 품질 A/B vs bge-m3 + 8B 비용/지연. **트랙 C 대상**. 재판정=계측 가동 후 |
| 9 | 임베딩 표/코드 불일치 | ③ | **정합 정정** | CLAUDE.md 표 ↔ 코드(bge-m3) 정본화 — 별도 정합 작업 |
| 10 | OCR PaddleOCR-VL(v1.6 96.3%, 2026-07-10 갱신) | ③ | **파일럿** | Phaiakes9 한국어 손글씨 정확도(목표 90%) 실측 vs 현 하이브리드. **트랙 C 대상**. 재판정=OCR 벤치 시 |
| 11 | pgvector v0.8 / vLLM+Ollama(2026-07-10 갱신) | ③ | **유지** | Qdrant/vLLM 전환 트리거=10M+ 벡터·동시요청 8+(이번 조사로 임계 구체화, 슬98 경로) |
| 12 | 교수학 평가 루브릭(LearnLM 등) | ④ | **파일럿** | `harness/pedagogical_rubric.py` **이미 존재**(트랙 C 확인) — 계측선 없이 즉시 착수 가능. 소관=`prompt_engineering.md`·WH-1 |
| 13 | 규제(AI 기본법·만14세, 2026-07-10 상세 갱신) | ④ | **즉시 대응** | 고영향 AI=학생평가 명시 포함·1년 유예(과징금, 중대 인권침해 예외)·투명성/영향평가 의무. 소관=`regulatory_checklist.md`(법무) |
| 14 | Qwen3.6-35B-A3B (Apache 2.0, 2026-07-10 신규) | ① | **파일럿** | Phaiakes9 tok/s·p50 + 수학 A/B vs qwen3.5:27b. 재판정=계측 가동 후 |
| 15 | DeepSeek V4 Pro (MIT, 2026-07-10 신규) | ① | **보류** | 로컬 서빙 불가 확정(1.6T/49B act) — 신규 클라우드 프로바이더 추가는 별도 결정. 재검토=Anthropic 단일로 커버 안 되는 니즈 발생 시 |
| 16 | OpenR1-Math-220k (Apache 2.0, 2026-07-10 신규) | ② | **파일럿** | #4(NuminaMath-1.5) 법적 검토와 결선. 재판정=검토 완료 시 |

**분류 집계**: 도입 0 · **파일럿 9**(#1,2,3,4,8,10,12,14,16) · **보류 3**(#5,7,15) · 기각 1(#6) · 유지 1(#11) · 특수 2(#9 정합 정정·#13 즉시 대응). (2026-07-09 예비 대비: #3 보류→파일럿 승격(파일럿+1·보류-1) + 신규 #14·#16 파일럿 유입(+2) + 신규 #15 보류 유입(+1) → 파일럿 6→9·보류 3→3)

> **파일럿 공통 선결(갱신)**: 트랙 B S1 스모크 완료로 계측 인프라 자체는 가동 확인됐으나(Langfuse 라이브 기록·CLOUD_MID/LOCAL 비용·지연 1차 실측), **대표 트래픽 기반 실측(트랙 B S3~S4)과 파일럿 측정(트랙 C)은 미완**. 9건 파일럿 중 6건(#1,2,4,8,10,12)은 이미 `ssm_activation_handoff.md` 트랙 C에 측정 계획이 명시돼 있음 — **신규 3건(#3,14,16)을 트랙 C에 추가 등록 필요**. 차분기 인에이블러는 신기술이 아니라 **트랙 C 완료**(목표: 2026-Q4 스캔 전).

---

## 이번 분기 결론

- **현행 스택은 대체로 우월·유지 가능**. 핵심 코어(pgvector·로컬 서빙·태스크 패밀리 라우팅)는 교체 근거 없음 — 0.8/vLLM 갱신 조사로 전환 트리거 임계만 더 명확해짐(10M+·동시요청 8+).
- **세대 교체 신호 확대**(2026-07-10 보강): 수학 LLM=DeepSeekMath V2/V3.2 + **신규 Qwen3.6-35B-A3B**(#14, 로컬 유일 신후보) / 임베딩=Qwen3-Embedding / OCR=PaddleOCR-VL(v1.6 96.3%) / **클라우드=Claude Sonnet 5**(#3, 보류→파일럿 승격) — 전부 유망하나 **측정 대기 → 파일럿**. 즉시 도입 0(측정 없는 도입 없음 준수) 유지.
- **DeepSeek V4 Pro(#15)는 보류**: MIT·SOTA급이지만 로컬 서빙 규모 초과 확정 — "SOTA니까 도입"이 아니라 게이트 통과 여부로 판정(SSM §9 Hype 추종 금기 준수).
- **즉시 대응 1건**: 규제 변화(AI 기본법 시행, 고영향 AI=학생평가 명시 포함) → 법무 우선(§4 즉시 트리거), 1년 유예기간 내 준비 필요.
- **정합 정정 1건**: 임베딩 표/코드 불일치(te-3-large ↔ bge-m3) → 별도 정본화(본 스캔 판정 대상 아님).
- **메타 발견(갱신)**: 예비 스캔의 "측정 계측선 미가동" 병목은 **트랙 B S1 스모크 테스트로 부분 해소**(2026-07-09, `46be270`) — Langfuse 라이브 기록·CLOUD_MID/LOCAL 비용·지연 1차 확보. 그러나 비대표 트래픽(5토큰)이라 대표 실측(S3~S4)·파일럿 재판정(트랙 C)은 미완. **차분기 인에이블러 = 신기술이 아니라 트랙 C 완료**(9건 파일럿 측정·재판정, 목표: 2026-Q4 스캔 전 — `ssm_activation_handoff.md` 명시).
- **한국 AI 교육 시장 관찰**(신규): 정부 AI 교과서 정책 후퇴로 공교육 채널 의존 에듀텍은 타격, B2C(콴다 등)는 지속 성장 — WhyMath 전략 함의는 SSM 소관 밖(PRD 페르소나 전략 별도 검토).
- **다음 스캔**: 2026-Q4(2026-10-01, 라이브 Routine 이미 생성됨 — 트랙 A 완료). 즉시 트리거(규제·SOTA 신제품·비용/지연/정확도 드리프트) 발생 시 조기 발동.

*본 스캔 판정의 MEMORY 결정 로그 배출: `MEMORY.md` 2026-07-09 (문서·SSM 스캔) 항목 + 2026-07-10 보강 항목(신규 추가 예정).*

---

## 부록 A — 외부 제안 대조 (2026-08-01)

> **경위**: Kiki가 외부 채널 공유글 「AI 수학앱 최적 아키텍처 (2026)」(2편)을 제공하고 검토 요청. 글은 5대 설계 원칙(하이브리드 연산·Multi-Agent 분업·KG-RAG·CoT+Self-Consistency·적응형 학습)과 계층별 추천 스택을 제시한다.
>
> **본문 무변경 원칙**: 본 부록은 §게이트 대기 큐의 **#1~#16 번호·판정을 일절 변경하지 않는다**. 그 번호를 `ssm_activation_handoff.md` 트랙 C가 직접 참조하므로(문서 머리말 재번호 금지 제약), 대조 결과는 부록으로만 부착하고 신규 후보는 **Q4 큐**로 이월한다. 분기 스캔 산출물의 사후 변조 방지.
>
> **즉시 트리거 판정(§4-2)**: **해당 없음**. 비용·지연·정확도 드리프트 없음 · 신제품 출시 아님 · 규제 변화 아님. → Q4 스캔(2026-10-01, Routine 기생성) 입력으로 이월, 조기 발동 불요.

### A-1. 판정 요약

| 대조 항목 | 축 | 판정 | 근거 |
|---|---|---|---|
| **voyage-math 임베딩** | ③ | **Q4 큐 — 파일럿 후보(#8에 결선)** | 수학 특화 임베딩. 단 폐쇄형 API → "로컬 우선(Phaiakes9)·미성년 PII 통제"와 충돌 소지 → #8(Qwen3-Embedding vs bge-m3) A/B에 3번째 후보로 결선 |
| **Lean 4 / LeanTutor(AAAI 2026)** | ② | **#7 보류 유지 — 근거 강화(2026-08-01 1차 출처 검증 완료)** | `whs/verdict.py`·`harness.py`에 Tier3(Lean4) 좌석 주석 예약. 재검토 시점(WH-S Tier3 착수) 불변. **`[불확실]` 해제 — 단, 블로그 서술("높은 정확도")은 논문이 지지하지 않음**(A-4 참조) |
| **Whisper STT (음성 *입력*)** | ③/④ | **Q4 큐 — 신규 관찰(설계 공백)** | 실측 갭. `schema/speech.py`는 **Math-to-Speech(출력)** 전용이고 음성 *입력* 설계·코드 0건. 성격이 측정 대상이 아니라 *설계 공백*이라 Q4 재검토 시 backlog 라우팅 여부를 별도 판단 |
| KG-RAG "+35% 학습 성과"(Dong et al.) | ④ | **`[불확실]` 해제 — 인용 정확 확인. 단 신규 후보 아님(A-2 기채택 보강 증거)** | 2026-08-01 1차 출처 검증: 통제실험 n=76 무작위 배정에서 KG-RAG 6.37 vs RAG 4.71 = **+35.2%**(t=−3.75·p=.00035·d=0.86) 검산 일치. 단 도메인=금융·대상=대학 1학년·**단일 세션 즉시 객관식**(장기 파지 미측정) → 우리 KPI #1(장기 숙달)로 이전 불가(A-5) |
| **LangGraph / DSPy 오케스트레이션** | ③ | **기각** | 코드 0건은 의도적. ⓐ"LLM 호출은 항상 라우터(`l3/router.py`) 경유" 절대 원칙 위반 ⓑ비용·관측 회계가 프레임워크에 흡수 → "판정치를 외부 관측 인프라에만 의존 금지"(이중 회계) 훼손 ⓒSSM §6 KPI #5(1인 유지가능성) 악화 ⓓ결정론 게이트를 확률적 그래프로 대체 |
| **"Multi-Agent 합의 = 검증"** | ① | **기각** | 검증 권위 서열(①기계 증명 ②측정 통과 기계 게이트 ③인간) 위반. 게이트 미경유 LLM 의견은 그 자체로 권위 없음 — `l3/cross_verify.py` 모듈 주석이 명시("이 모듈은 게이트가 아니라 검출기다") |
| **"교과서/문제집 → 벡터DB 임베딩"** | ② | **기각(협상 불가)** | 최상위 금기 정면 위반 — 검정교과서·평가원 본문 복제 금지, *자체 동등문제*로 대체(`licensing_safety.md` 가이드 v2.0). 의사결정 우선순위 **#2(법적·윤리 준수)**라 비용·성능 우위로 상쇄 불가(SSM §6) |
| **Wolfram Alpha API** | ③ | **기각 — 현행 SymPy 단독 유지** | 2026-08-01 실측: 코드 0건(CLAUDE.md 표 "계획·미구현" 표기와 일치). 도입 시 ⓐ학생 데이터 외부 전송(미성년 PII) ⓑ비용 ⓒ"SymPy=동치·검증·해집합 단일 권위" 훼손 |
| MathPix API | ③ | **기각(기결정 재확인)** | 2026-05-28 미성년자 프라이버시·Phaiakes9 로컬화 사유로 이미 기각 → PaddleOCR+Qwen3-VL 전환 |
| DeepSeek-R1 / QwQ-32B / GLM-Z1-9B | ① | **정보 가치 없음(세대 뒤짐)** | 본 스캔 #14(Qwen3.6-35B-A3B)·#15(DeepSeek V4 Pro)가 이미 다음 세대를 다룸 |

### A-2. 이미 채택·구현된 항목 (글의 주장이 옳음 — 재확인)

대조 결과 글의 5대 원칙 중 4개는 **이미 구현돼 있고 일부는 글보다 강하다**. 스택 변경 근거 없음:

- **①하이브리드 연산** — `l3/symbolic_equivalence.py`·`verify_answer.py`·`equivalent/canonicalize`. CLAUDE.md 금기 "검증 없는 LLM 응답 제공 금지"로 헌법화(글은 권고 수준).
- **②역할 분업** — `whs/harness.py`(솔버)·`l3/verify_*`(검증)·`l4/socratic`·`l4/polya`(튜터링)·`l3/pregenerate`(문제 생성). 단 구현 수단은 에이전트 프레임워크가 아니라 **결정론 모듈 경계**(위 기각 사유 참조).
- **③KG-RAG** — **삼중 store 동일 UC 키**(Neo4j 그래프 · pgvector `concept_embedding` · PG 프로젝션), 403노드/541엣지 적재 완료. 글의 제안보다 앞섬.
- **④Self-Consistency** — `l3/cross_verify.py`가 **상위 호환**. 같은 프롬프트 N회 최빈답이 아니라 원리·시스템프롬프트·**가시 필드** 3축이 모두 다른 K=3을 구성 시점에 기계로 강제(`_assert_independent`) + 생성자≠검증자(`IndependenceError`).
- **⑤적응형·BKT/간격반복** — L2 학습자 모델(7계층).
- 스택 일치: pgvector · bge-m3 · MathLive · FastAPI · TexTeller(`ocr-heavy` extra 좌석).

### A-3. Q4 스캔 인계 사항

1. 신규 후보 3건(voyage-math · Lean4 재검토 신호 · Whisper STT 갭)을 **Q4 본문 축별 관찰에 정식 번호로 편입**한다(#17~ 이후 번호는 Q4 스캔이 배정).
2. **`[불확실]` 2건 전부 2026-08-01 해소** — LeanTutor(A-4·인용 유효하나 "높은 정확도" 서술은 반증) · KG-RAG(A-5·인용 정확 확인, 단 기채택 항목의 보강 증거이지 신규 후보 아님). Q4 스캔에 이월할 미검증 인용 **0건**.
3. 기각 5건(LangGraph/DSPy · Multi-Agent 합의검증 · 교과서 본문 임베딩 · Wolfram Alpha · MathPix)은 **재유입 시 본 부록을 근거로 재심 없이 기각 유지**한다. 새 근거(예: 로컬 실행 가능한 정리증명기)가 제시될 때만 재개.
4. **백로그 태스크 등재 0건** — 3건 모두 파일럿/보류/관찰이고 §5-(b) "측정 없는 도입 없음"의 공통 선결(트랙 C 대표 트래픽 측정)이 미완이라, 지금 등재하면 착수 불가 태스크가 큐를 오염시킨다.
5. **스택 실변경 0** → CLAUDE.md 기술 스택 표 미변경(§8 규약: 실변경 시에만 갱신).

### A-4. LeanTutor 1차 출처 검증 (2026-08-01 · `[불확실]` 해제)

> **출처**: Patel, M.; Bhave, R.; Lu, T.; Mehta, A.; Voss, N.; Norouzi, S.; Ranade, G. 「LeanTutor: A Formally-Verified AI Tutor for Mathematical Proofs」 UC Berkeley. **AAAI 2026 (EAAI-26) 게재 확정**(© 2026 AAAI, pp. 40672~40676). Kiki가 PDF 원문 제공 → 저자·소속·게재처 실물 확인.

**논문은 실재한다**(인용 자체는 유효). **그러나 외부 블로그의 서술 "증명 문제에서 높은 정확도를 보여줍니다"는 논문이 지지하지 않는다 — 오히려 반증된다.**

**실측 수치(Table 1 · 최고 설정 = Baseline + Staff Solution, step-by-step, pass@1)**

| 지표 | 값 |
|---|---|
| Correct tactics | 56.8% ± 3.2% |
| **Correct proofs** | **18.0% ± 6.1%** |
| **Incorrect proofs 처리** | **30.1% ± 7.4%** |

시스템 전체 평가(Table 2)는 **21개 증명**(성공적으로 autoformalize된 44개에서 추출)에 대한 5점 척도 인간 평가로, Accuracy 3.4~3.7(baseline 3.4·3.1·2.8) 수준이다. 논문은 스스로를 **"proof-of-concept"**으로 규정하고, 모델은 `gpt-4o-mini-2024-07-18`·전체 실험 비용 **$4 미만**이다.

**우리에게 유효한 소득 3건(수치 인용과 별개)**

1. **LLM-as-a-judge가 인간 평가와 정면 배치** — GPT-4 심판 도입 시 *거의 모든 축에서 baseline이 LeanTutor를 이겼고*, 이는 인간 평가와 반대였다. 저자들이 "이 패러다임의 문제를 드러낸다"고 명시. → **검증 권위 서열**("측정 통과 기계 게이트를 경유하지 않은 LLM 의견은 권위 없음" · `l3/cross_verify.py`)의 **외부 실증**. 단, 이 논문의 인간 평가도 *증명 1건당 평가자 1명*이라 평가자 간 신뢰도(IRR)가 측정되지 않았다 — 초인간 검증 기준 §6축(독립 다관점·재현성) 미달이므로 인간 평가 쪽 수치도 확정치로 인용하지 않는다.
2. **Answer Leakage를 독립 평가 축으로 채택** — 우리 "답 미루기"(`l4/hint_deferral.py`)·SSM KPI #1(교수학 효과)과 동일 축. Q3 **#12**(MathTutorBench answer-leakage 부정지표) 파일럿 방향을 외부 사례로 보강.
3. **PeanoBench** — NNG4(Buzzard et al. 2023, **Apache-2.0**) 파생 371 증명. 라이선스는 안전하나 도메인이 Peano 산술이라 ②축 코퍼스 후보로는 부적합(아래 ⓓ).

**#7 Lean4 "보류" 유지 근거가 강화됨** — 채택 불가 사유가 논문 Limitations에 저자 자인으로 명시:

- ⓐ **문제마다 형식화된 staff solution이 사전 필요** — 저자도 "좋은 autoformalizer가 없으면 교사에게 상당한 부담"이라 인정. 우리 코퍼스 규모에 비현실적.
- ⓑ **NL 단계 ↔ Lean tactic 1:1 대응 가정** — 저자가 "복잡한 증명에는 일반적으로 확장되지 않는다"고 명시.
- ⓒ **autoformalization 실패 시 잘못된 피드백을 주거나 응답 불가** — proof-level 18%면 학생 입력 대부분이 이 경로. 우리 금기 "확실하지 않을 때 자신 있게 말함 금지"와 정면 충돌.
- ⓓ **도메인이 Peano 산술**(NNG4) — 우리 MVP 타깃(A 일반고 고3·수능·학교진도=계산 중심)과 무관. 증명 중심 대학 과목용 설계.

→ **판정 불변**: #7 **보류**, 재검토 시점 = WH-S Tier3 착수 시(ROADMAP 장기). 본 논문은 Tier3 착수 시 **설계 참고 문헌**으로 인계하되, 도입 근거로는 쓰지 않는다.

### A-5. KG-RAG 1차 출처 검증 (2026-08-01 · `[불확실]` 해제)

> **출처**: Dong, C.; Yuan, Y.; Chen, K.; Cheng, S.; Wen, C. 「How to Build an Adaptive AI Tutor for Any Course Using Knowledge Graph-Enhanced Retrieval-Augmented Generation (KG-RAG)」 The Education University of Hong Kong 외. arXiv **2311.17696**. Kiki가 PDF 원문 제공.

**인용은 정확하다**(LeanTutor와 대조적). 블로그의 "KG-RAG가 일반 RAG보다 35% 학습 성과 향상"은 논문이 지지한다.

**실측(§IV-C 통제실험)** — 대학 1학년 76명 **무작위 배정**(대조군=표준 RAG n=38 / 실험군=KG-RAG n=38), 동일 자료로 3시간 자습 + 45분 튜터링 세션 후 전문가 작성 10점 객관식 평가:

| 그룹 | 평균 | SD |
|---|---|---|
| 대조군 (표준 RAG) | 4.71 | 1.93 |
| 실험군 (KG-RAG) | **6.37** | 1.92 |

검산: (6.37 − 4.71) / 4.71 = **35.2%** — 블로그 수치와 일치. t = −3.75 · p = .00035 · Cohen's d = 0.86(큰 효과크기). 설계는 적법한 RCT다.

**그러나 판정은 "신규 후보"가 아니라 "기채택 항목의 보강 증거"다** — 우리는 **이미 KG-RAG를 구현**했다(삼중 store 동일 UC 키: Neo4j 그래프 · pgvector `concept_embedding` · PG 프로젝션, 403노드/541엣지 적재 완료 · A-2 참조). 도입 게이트(§5)에 올릴 대상이 아니며 **스택 변경 0**.

**우리 맥락으로 이전할 때의 제약 4건(수치를 우리 KPI로 직접 인용 금지)**:

- ⓐ **도메인이 금융**(MIT OCW 15-401 Finance Theory I) — 수학이 아니다. 개념 간 관계 밀도·오개념 구조가 다르다.
- ⓑ **대상이 대학 1학년**(해당 과목 무경험) — 우리 MVP 타깃(A 일반고 고3)과 인지·정서 조건이 다르다.
- ⓒ **단일 세션 즉시 측정** — 장기 파지(retention) 측정 **0건**. 저자도 Limitations에서 "extended periods에 걸친 knowledge retention"을 향후 과제로 자인. 우리 SSM KPI **#1은 장기 숙달**이므로 이 수치는 #1의 근거가 될 수 없다.
- ⓓ **측정 도구가 10점 객관식** — 우리가 의도적으로 후순위에 둔 축이고, 금기 "'정답을 빠르게'를 KPI로 사용 금지"와 겹친다. 절대 점수도 6.37/10(64%)로, "정확도 문제 해결"로 읽을 수치는 아니다.
- (부수) §IV-B 학생 피드백(N=76·5점 Likert)은 통제실험과 **별개 파트**이며 설계가 약하다 — 중간값 3.0 대비 one-sample t-test이고, "The Answer is Detailed"는 p=0.289(유의하지 않음), "My Understanding Improved"는 20%가 strongly disagree인 이봉 분포를 평균 3.42로 뭉갠다. **이 표의 수치는 인용하지 않는다.**

**부수 신호(판정 변경 없음)**: 논문은 LLM으로 **DeepSeek-V3**를 택했고 사유가 ①오픈웨이트 접근성 ②MATH 90.2% ③**GPT-4 대비 운영비 약 7%**다. 우리 **#1**(DeepSeekMath V2/V3.2 · 파일럿)의 비용 축과 정합하는 외부 신호이나, 이미 파일럿 큐에 있으므로 **판정 불변**(측정 없는 도입 없음).

---

**연계 문서**: `system_superiority_maintenance.md`(근거 표준) · `../data/licensing_safety.md`(②축 라이선스 소관) · `prompt_engineering.md`(④축 교수학 루브릭) · `../legal/regulatory_checklist.md`(④축 규제 소관) · `../../MEMORY.md`(판정 배출구) · `../../CLAUDE.md`(의사결정 우선순위·기술 스택 표).
