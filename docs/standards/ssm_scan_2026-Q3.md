# SSM 분기 스캔 2026-Q3

> **작성일**: 2026-07-09 | **이전 스캔 대비 델타**: 최초 스캔(베이스라인 확립·이전 스캔 없음) | **스캐너**: Claude Code(위임 조사) + Kiki 검수 대기
>
> **근거 표준**: `system_superiority_maintenance.md`(SSM v1.0). 4대 축을 §3 정의대로 순회하고, 각 후보를 §5 도입 게이트(우선순위 종속·측정 없는 도입 없음·구조 붕괴 방어)에 걸어 §5-③ 4종(도입/파일럿/보류/기각) 또는 유지/관찰로 1차 판정.
>
> **⚠️ 이번 스캔의 구조적 제약(정직)**: 도입 게이트 §5-(b) *"측정 없는 도입 없음"*. 현재 Phaiakes9 라이브 키·Langfuse 실측 계측선이 **대부분 미가동**(ROADMAP "라이브 선행분=키 투입 후"·MEMORY 2026-07-08 라우터 비용 실측 1건 비대표). 따라서 **본 스캔은 "도입" 판정을 0건으로 두고**, 유망 후보는 전부 *파일럿(측정 후 재판정)*·불확실은 *보류*로 귀결한다. 스택 실변경 0 → CLAUDE.md 기술 스택 표 미변경.
>
> **불확실 표기**: 1차 출처(공식 릴리스·arXiv·벤치 리더보드) 교차검증된 항목만 판정에 반영. SEO 블로그 단일 출처 수치(모델 버전·점수)는 `[불확실]`로 표기하고 판정을 유보한다.

---

## 축별 관찰

### ① 모델·LLM

현행 베이스라인: 로컬 fast/mid/quality = `qwen2-math:1.5b`(p50 1,010ms·124 tok/s·SLA PASS) / `qwen2-math:7b` / `qwen3.5:27b`, 태스크 패밀리 라우팅(수학=qwen2-math·NLP=qwen2.5), 클라우드 티어 라우터 경유(Claude/GPT-5/Gemini 2.5). (MEMORY 2026-05-16~20 결정)

| 후보 | 신호(우월성) | 리스크 | 1차 판정 |
|---|---|---|---|
| **DeepSeekMath V2 / DeepSeek-V3.2** (MIT·수학 SOTA, `DeepSeek-Math` 후계) | 수학 특화 + 오픈웨이트/MIT, self-verification 지향. 우리 quality/검증 티어의 직접 상향 후보 | 대형 MoE → 로컬 서빙 GPU 부담(Phaiakes9 실측 필요)·성숙도 초기 | **파일럿** |
| **Qwen3 후속 수학·추론 라인** (현행 Qwen3-Math 계열) | Apache 2.0·0.6B~32B 경량 패밀리로 온디바이스 유연·다국어 | 순수 경쟁수학(AIME/HMMT)은 DeepSeekMath V2에 밀릴 수 있음 | **유지 + 인지** |
| **PRM 재랭킹** (Qwen2.5-Math-PRM·Skywork-o1-PRM·Math-Shepherd) | 풀이 *단계* 검증/오답 진단 강화 — L3 PRM·best-of-N 재랭킹에 저비용으로 얹기 | 대부분 Qwen2.5 세대 기반 → 최신 베이스와 궁합 재확인 | **파일럿** |
| **클라우드 프론티어 신버전** (Opus 4.x·GPT-5.5·Gemini 3.1 정황) | 최상위 추론 갱신·멀티모달·가격 인하 정황 | 세부 버전·점수가 `[불확실]`(SEO 출처). 라우터가 클라우드 티어를 이미 추상화 → 교체 저위험 | **보류**(공식 릴리스 재검증 후) |

멀티모달 손글씨 수식(HMER): 범용 VLM은 손글씨 수식에서 오차 전파 지속 보고(Uni-MuMER·VEHME·FERMAT) → **현 "PaddleOCR + Qwen3-VL 하이브리드" 설계 방향 자체는 재확인됨**(③축 OCR과 연결).

출처: arxiv.org/pdf/2512.02556 · api-docs.deepseek.com/news/news251201 · qwenlm.github.io/blog/qwen3 · github.com/RyanLiu112/Awesome-Process-Reward-Models · arxiv.org/pdf/2505.23566

### ② 데이터

현행 베이스라인: 법적 안전조합(NCIC 성취기준·공공누리 AI유형·AIHub + LLM 학습용 NuminaMath/PRM800K/PhET). EBS·평가원·검정교과서 본문은 자체 동등문제로 대체(`licensing_safety.md` 가이드 v2.0).

| 후보 | 신호 | 리스크 | 1차 판정 |
|---|---|---|---|
| **NuminaMath-1.5** (Apache 2.0·~90만 경쟁수학 + CoT) | 기존 NuminaMath 라이선스 제약 해소한 후속 — 상업 이용 가능 대규모 코퍼스 | GPT 계열 합성분의 약관/저작권은 보수적 검토 권장 | **파일럿**(약관 검토 전제) |
| **AIHub 한국 수학 데이터** (2022 개정 정합·손글씨 18만↑·문제 생성 8.4만↑) | 한국 교육과정 정합 + 손글씨 이미지 → OCR/튜터링에 직결(미션 최적합) | **공공누리 유형이 제2유형(CC BY-ND·비상업)일 가능성** → 상업 투입 전 각 페이지 개별 확인 필수(KPI #3 법적 안전) | **보류**(유형 실확인 전 투입 불가) |
| **MegaMath·Nemotron-Math·OpenMathInstruct-2** (초대규모 웹+합성) | 압도적 규모(수백 B 토큰) | 라이선스·출처 혼재(웹크롤)·한국 교육과정 정합 낮음 | **기각**(미션·라이선스 부적합) |
| **Lean4 형식검증 계열** (FormalMATH·CriticLeanBench) | 풀이 정답 검증(verifier) 파이프라인 보강 | WH-S Tier3 종속·장기 보류 항목(ROADMAP) | **보류**(WH-S Tier3 시점) |

출처: emergentmind.com/topics/numinamath-dataset · aihub.or.kr(dataSetSn=71859·71716·71718) · arxiv.org/pdf/2504.02807 · arxiv.org/pdf/2507.08665

### ③ 인프라·스택

현행 베이스라인: Vector=pgvector(PG16·슬98), Graph=Neo4j 5, 서빙=Ollama(Phaiakes9), 임베딩=CLAUDE.md 표기 `text-embedding-3-large`.

| 후보 | 신호 | 리스크 | 1차 판정 |
|---|---|---|---|
| **임베딩 Qwen3-Embedding** (MTEB 다국어 1위 ~70.6, OpenAI 64.6·Google 68.3·bge-m3 상회, 32K, 오픈웨이트) | 한국어 검색 품질 + 자체 호스팅(미성년 PII 통제) | 8B → 임베딩 비용/지연↑(경량 0.6B/4B 변형 검토). bge-m3는 MIT·다기능으로 여전히 가성비 기본기 | **파일럿** |
| **⚠️ 임베딩 표/코드 불일치(실재 미결)** | CLAUDE.md 표=`text-embedding-3-large` ↔ 실코드=`bge-m3`(dim 1024, 슬105). 임베딩 모델 확정이 MEMORY상 미결 후속 | 문서-코드 truth 이원화(유지보수 지옥 씨앗) | **정합 정정 필요**(별도 작업 라우팅·본 스캔 판정 대상 아님) |
| **OCR PaddleOCR-VL 1.x** (OmniDocBench SOTA ~94.5~96.3·수식 우위·109언어) | 단일 모델로 텍스트+표+수식 → 현 하이브리드 단순화 가능 | 손글씨 수식은 VLM 보정 병행 권장. **한국어 손글씨 정확도 Phaiakes9 실측(목표 90%) 전제**(기존 OCR 미결 리스크와 동일) | **파일럿** |
| **벡터 pgvector 현행** | 10M 벡터 미만에서 별도 DB 대비 합리적·일부 벤치 Qdrant 상회 | 5M+ 규모 p95 80~140ms 상승 | **유지**(Qdrant는 슬98이 이미 "대규모/고QPS 지연 트리거"로 재검토 경로 보존) |
| **서빙 vLLM(프로덕션)+Ollama(개발)** | vLLM 동시성 처리량 우위·Ollama 단일요청 TTFT 우위 | 수치 HW/모델 의존 | **유지**(현행 방향 재확인) |

출처: milvus.io/blog/choose-embedding-model-rag-2026 · modal.com/blog/mteb-leaderboard-article · paddleocr.ai(PaddleOCR-VL) · tigerdata.com/blog/pgvector-vs-qdrant · sitepoint.com/ollama-vs-vllm-performance-benchmark-2026

### ④ 경쟁·교수학

> §3 주의: 공개 정보만. 경쟁 서비스 약관·데이터 추출 금지·비교광고성 서술 금지.

| 후보/동향 | 신호 | 함의 | 1차 판정 |
|---|---|---|---|
| **콴다(매스프레소)** | 전과목 AI 풀이·대규모 학생/문제 DB·아시아 확장(공개 정보) | 데이터·유통 규모 열위 → WhyMath 차별화선 = *교수학 튜터링 깊이(메타인지·답 미루기) + 교육과정 정합* | **관찰** |
| **EBS AI(단추)·토닥토닥 수학탐험대** | 공교육 연계·교육과정 정합·문제추천(공개 정보) | 방어선 = AIHub 교육과정 데이터로 정합성 확보(②축과 연결) | **관찰** |
| **교수학 평가 루브릭** (LearnLM 루브릭·MathTutorBench answer-leakage 부정지표·MetaCLASS 메타인지 코칭) | 프롬프트 템플릿을 이 루브릭으로 자체 평가·회귀테스트하면 즉시 우월성 계측 가능(KPI #1 교수학 효과·저위험) | `prompt_engineering.md`·WH-1 평가 하네스와 결선 | **파일럿** |
| **규제 변화**(AI 기본법 2026-01-22 시행·PIPA 만14세 법정대리인 동의·여가부 청소년보호대책) | 고영향/생성형 투명성·안전성 의무 + 미성년 동의·연령확인 강화 | **§4 즉시 트리거(법·규제 변화) 발동 → 법무 우선**(도입 판정 대상 아님) | **즉시 대응**(`regulatory_checklist.md` 소관) |

출처: arxiv.org/pdf/2508.06583 · law.go.kr(lsiSeq=268543) · privacy.go.kr · apps.apple.com(id1270676408) · ai.ebs.co.kr

---

## 게이트 대기 큐

| # | 후보 | 축 | 판정 | 다음 액션(측정 지표·재검토 시점·소관) |
|---|---|---|---|---|
| 1 | DeepSeekMath V2 / V3.2 | ① | **파일럿** | Phaiakes9 서빙 실측(tok/s·p50) + 수학 정확도 A/B vs qwen2-math. 재판정=라이브 계측 가동 후 |
| 2 | PRM 재랭킹 | ① | **파일럿** | L3 검증 커버리지·PRM 통과율 델타 측정. 재판정=WH-S S2~S3 시 |
| 3 | 클라우드 프론티어 신버전 | ① | **보류** | 공식 릴리스·벤치 1차 출처 확인. 재검토=2026-Q4 스캔 |
| 4 | NuminaMath-1.5 | ② | **파일럿** | Apache 2.0 + 합성분 약관 법적 검토(`licensing_safety.md`). 재판정=검토 완료 시 |
| 5 | AIHub 한국 수학 데이터 | ② | **보류** | 각 데이터셋 공공누리 유형(상업 가능 여부) 개별 확인. 재검토=유형 확인 즉시 |
| 6 | MegaMath 등 웹크롤 대규모 | ② | **기각** | 사유: 라이선스 혼재·교육과정 정합 낮음·미션 부적합 |
| 7 | Lean4 형식검증(FormalMATH 등) | ② | **보류** | 재검토=WH-S Tier3 착수 시(장기) |
| 8 | 임베딩 Qwen3-Embedding | ③ | **파일럿** | 한국어 의미검색 품질 A/B vs bge-m3 + 8B 비용/지연. 재판정=계측 가동 후 |
| 9 | 임베딩 표/코드 불일치 | ③ | **정합 정정** | CLAUDE.md 표 ↔ 코드(bge-m3) 정본화 — 별도 정합 작업 |
| 10 | OCR PaddleOCR-VL | ③ | **파일럿** | Phaiakes9 한국어 손글씨 정확도(목표 90%) 실측 vs 현 하이브리드. 재판정=OCR 벤치 시 |
| 11 | pgvector / vLLM+Ollama | ③ | **유지** | Qdrant/vLLM은 대규모·고QPS 지연 트리거 시 재검토(슬98 경로) |
| 12 | 교수학 평가 루브릭(LearnLM 등) | ④ | **파일럿** | 프롬프트 템플릿을 루브릭으로 자체 평가·회귀테스트 결선. 소관=`prompt_engineering.md`·WH-1 |
| 13 | 규제(AI 기본법·만14세) | ④ | **즉시 대응** | 고위험 표시·투명성 고지·연령/동의 플로우. 소관=`regulatory_checklist.md`(법무) |

**분류 집계**: 도입 0 · 파일럿 6(#1,2,4,8,10,12) · 보류 3(#3,5,7) · 기각 1(#6) · 유지 1(#11) · 특수 2(#9 정합 정정·#13 즉시 대응).

> **파일럿 공통 선결**: 6건 전부 *Phaiakes9 라이브 계측(Langfuse 실측선) 가동*이 측정의 전제. 계측선 미가동이 이번 분기 "도입 0"의 근본 원인 → **차분기 최우선 인에이블러**는 신기술이 아니라 *측정 인프라 가동*이다.

---

## 이번 분기 결론

- **현행 스택은 대체로 우월·유지 가능**. 핵심 코어(pgvector·로컬 서빙·태스크 패밀리 라우팅)는 교체 근거 없음.
- **세대 교체 신호 3곳**(수학 LLM=DeepSeekMath V2 / 임베딩=Qwen3-Embedding / OCR=PaddleOCR-VL) — 전부 유망하나 **측정 대기 → 파일럿**. 즉시 도입 0(측정 없는 도입 없음 준수).
- **즉시 대응 1건**: 규제 변화(AI 기본법 시행·미성년 동의) → 법무 우선(§4 즉시 트리거).
- **정합 정정 1건**: 임베딩 표/코드 불일치(te-3-large ↔ bge-m3) → 별도 정본화.
- **메타 발견**: 이번 스캔의 최대 병목은 신기술 부재가 아니라 **측정 계측선 미가동**. 차분기 인에이블러 = Phaiakes9 라이브 키·Langfuse 실측 가동.
- **다음 스캔**: 2026-Q4(분기 주기). 즉시 트리거(규제·SOTA 신제품·비용/지연/정확도 드리프트) 발생 시 조기 발동.

*본 스캔 판정의 MEMORY 결정 로그 배출: `MEMORY.md` 2026-07-09 (문서·SSM 스캔) 항목.*

---

**연계 문서**: `system_superiority_maintenance.md`(근거 표준) · `../data/licensing_safety.md`(②축 라이선스 소관) · `prompt_engineering.md`(④축 교수학 루브릭) · `../legal/regulatory_checklist.md`(④축 규제 소관) · `../../MEMORY.md`(판정 배출구) · `../../CLAUDE.md`(의사결정 우선순위·기술 스택 표).
