# 05. 출처·정합 — Kiki ChatGPT 설계안 통합 기록

> **성격**: Kiki가 업로드한 ChatGPT UI 설계 대화 원본(2026-07-24·"UI관련파일 1/2")을 이 도메인(01~04)에 어떻게 반영했는지의 **정합 기록**. 어느 아이디어를 채택했고, 어디서 WhyMath 확정 결정과 충돌해 교정했는지를 투명하게 남긴다.
>
> **원본 보존 정책**(Kiki 결정): 원본 `.docx` 바이너리는 저장소에 **커밋하지 않는다**. 본문 요지는 01~04 문서와 본 문서에 반영·인용한다.

---

## §1. 원본 5개 문서 ↔ WhyMath 문서 매핑

업로드된 6개 파일 중 2개는 중복이라 **5개 고유 문서**다.

| 원본 | 주제 | 대응 질문 | 반영 문서 |
|---|---|---|---|
| **[A]** | 파이프라인 → 학습 여정(Learning Journey)·"메뉴가 사라지는 UI"·목표 카드·3계층 | Q1 | [01 §5](01_student_pipeline_to_menus.md) |
| **[B]** | 6개 역할 UI 레이어·연령대별 차이·공통 네비·목표 중심·Phase 1~6 | Q2 | [02 §2·§7](02_student_ui_master_plan.md) |
| **[C]** | 관리 UI = Meta OS / Control Center·폐쇄 피드백 루프·이벤트·플러그인 | Q3/Q4 | [03 §5](03_admin_console_plan.md)·[04 §6](04_admin_console_architecture.md) |
| **[D]** | Admin Control Center 22모듈 + 5 EOS Studio·4계층 | Q3 | [03 §5](03_admin_console_plan.md) |
| **[E]** | 기술 아키텍처·8 core engines·계층 스택 | Q4 | [04 §6](04_admin_console_architecture.md) |

---

## §2. 큰 그림에서 원본과 WhyMath는 이미 일치한다

핵심 논지가 서로 독립적으로 같은 결론에 도달했다 — 이것이 통합이 자연스러운 이유다.

| 원본의 주장 | WhyMath의 기존 원칙 | 정합 |
|---|---|---|
| "학생은 DSL·교수법을 절대 보지 않는다" | **표현 ≠ 의미**(슬89) | ✅ 동일 |
| "하나의 엔진 위 역할별 UI" | 단일 앱 + 모드/역할 분기(3앱 반려) | ✅ 동일 |
| "학년→단원→문제가 아니라 목표→성취→다음목표" | 메뉴는 파생·자동 커리큘럼 정렬 | ✅ 동일 |
| "교수전략을 콘텐츠에 고정하지 말고 런타임 선택" | `04d` 2단계 교수법 분리 | ✅ 동일 |
| "설계→생성→운영→분석 폐쇄 루프" | `04d §3.1` Adaptive Pedagogy Engine 루프 | ✅ 동일 |

---

## §3. 채택한 구체안 (원본이 더한 가치)

원본은 WhyMath 문서에 없던 **구체성**을 더했고, 그대로 채택했다.

- **학습 여정 10단계 카드 시퀀스**([A]) — 오늘목표→왜배울까→탐색→개념→예제→연습→AI피드백→오답교정→형성평가→다음목표. Polya·`SceneElement`에 매핑([01 §5]).
- **"메뉴가 사라지는 UI" / 목표 중심 카드**([A]) — 메뉴 파생 논지의 극단 실현.
- **6개 역할 UI 레이어 + 공통 네비(홈/검색/AI/알림/내정보)**([B]) — 역할 축의 구체화([02 §2]).
- **연령대별 학습 특성**([B]) — 초(큰버튼·캐릭터)~대학(CAS·시뮬레이션).
- **Control Center 4계층 + 22모듈 + 5 EOS Studio**([C]·[D]) — 관리 콘솔 IA의 구체화([03 §5]).
- **8 core engines**([E]) — L1~L7 매핑의 렌즈([04 §6]).

---

## §4. 충돌 원장 (Conflict Ledger) — 원본과 WhyMath 확정 결정의 5개 충돌

원본을 그대로 채택하면 WhyMath의 하드 제약·확정 결정을 위반하는 지점. **구조 붕괴 감지기** 역할로 각각 교정했다.

| # | 원본 제안 | WhyMath 확정 | 교정 결과 | 반영 |
|---|---|---|---|---|
| 1 | **초등 UI에 게임 요소** | 반게임화(랭킹·스트릭·보상 금지) 하드 제약 | 시각적 재미(캐릭터·애니메이션·큰 버튼)만 허용·중독성 게임화 금지·자유학기제만 `gamification_level≤3` | [02 §2](02_student_ui_master_plan.md) |
| 2 | **멀티 LLM**(OpenAI·Gemini·DeepSeek·Kimi·OpenRouter) | 실제=Ollama 로컬 + Anthropic만·로컬 우선 | AI Models 모듈은 실제 매트릭스(`GET /status`) 반영·GPT/Gemini는 "계획·미배선" 표기 | [04 §6](04_admin_console_architecture.md) |
| 3 | **경쟁하는 새 7계층 스킴** | 확정된 L1~L7 책임 계층 | 원본 계층을 L1~L7에 *매핑*만·새 스킴 미채택 | [04 §6](04_admin_console_architecture.md) |
| 4 | **"Lesson을 학생마다 매번 생성"** | select-vs-generate(비용) | "매번 *선택·렌더*, 캐시 미스만 생성"(캐시 히트 0원) | [01 §5](01_student_pipeline_to_menus.md)·[04 §6](04_admin_console_architecture.md) |
| 5 | **Neo4j+VectorDB 병렬·k8s·마이크로서비스** | pgvector 확정(6번째 store 회피)·FastAPI 단일 | pgvector 정본·Neo4j는 개념/원자 그래프·k8s/분할은 규모 도달 시 지향 | [04 §6](04_admin_console_architecture.md) |

**공통 안전선 재확인**(원본에 없거나 약한 것을 WhyMath가 보강): RBAC 선결(role 필드 부재·CRUD 무인증), 미성년 PII 마스킹, 거부 우회 금지, 측정치 이중 회계, 답 미루기·낙인 금지 스키마 불변식.

---

## §5. EOS/EKF 프레이밍 처리 (Kiki 결정: 북극성 참조·L1~L7 유지)

원본은 **EOS**(Education Operating System)·**EKF**(Education Knowledge Fabric)를 조직 뼈대로 삼는다. WhyMath에도 이 개념은 이미 **북극성 서사**로 존재한다:

- `../strategy/knowledge_fabric_vision_v1.md` — Education Knowledge Fabric / Metadata OS(서사 정본)
- `../strategy/education_os_positioning_v1.md` — EOS 포지셔닝
- MEMORY 2026-07-24 결정: **"Education OS 북극성 채택 — 정체성 선언 아님·유예 유지"**

따라서 본 도메인은 EOS/EKF를 **지향점으로 인용**하되, 문서 뼈대는 **확정된 7계층(L1~L7)**을 유지한다. EOS를 조직 프레임으로 승격하지 않는다(아직 유예 중인 정체성을 앞당기지 않음).

---

## §6. 후속 (backlog 제안 — 등재는 `backlog.py` 경유)

원본이 시사하는 신규 UI 태스크(제안만·대장 손편집 금지):
- 학생: 하단 탭 셸·학습 여정 카드 렌더·목표 진행 UI·온보딩 영속.
- 관리: `ADMIN-RBAC`·`ADMIN-BFF`·`ADMIN-REVIEW-UI`·`ADMIN-WEB`(Generation Pipeline 콘솔 포함)([04 §8](04_admin_console_architecture.md)).

---

**버전**: 1.0 | **작성**: 2026-07-24 | **교차링크**: [00_index](00_index.md) · [01](01_student_pipeline_to_menus.md) · [02](02_student_ui_master_plan.md) · [03](03_admin_console_plan.md) · [04](04_admin_console_architecture.md)
