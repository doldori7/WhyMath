# UI 설계 도메인 인덱스 (`docs/design/ui/`)

> **성격**: WhyMath의 **UI/정보구조(IA) 설계 정본**. 기존 아키텍처 문서(`../architecture/05_interaction.md` 등)가 *계층 책임*을 정의한다면, 이 도메인은 그 위에서 **화면·메뉴·네비게이션·역할·관리 콘솔을 어떻게 조립하는가**를 설계한다.
>
> **작성 배경**: 저장소에는 UX 지침이 아키텍처 문서와 코드 주석에 흩어져 있을 뿐, 전용 UI 설계·IA 문서가 없었다. 관리(admin) UI는 코드도 계획 문서도 없었다. 이 도메인이 그 공백을 메운다. (2026-07-24 신설 — `MEMORY.md` 결정 로그 참조)
>
> **Round 2 통합**(2026-07-24): Kiki가 업로드한 ChatGPT UI 설계 대화 원본([A]~[E])의 구체안(학습 여정·6역할 UI·Control Center 22모듈·8 core engines)을 01~04에 반영하고, 채택/충돌을 [05_source_reconciliation](05_source_reconciliation.md)에 정리. 원본 `.docx`는 미커밋(본문만 반영).

---

## 문서 지도

| 문서 | 다루는 질문 | 한 줄 요약 |
|---|---|---|
| **[01_student_pipeline_to_menus.md](01_student_pipeline_to_menus.md)** | 5단계 파이프라인 → 학생 메뉴 | "교육목적→교수전략→콘텐츠구성→DSL→자동생성"을 학생 UI로 **선형 투영하지 않는다**. UI는 선언적 명세의 렌더러이고 메뉴는 파생 산출물. |
| **[02_student_ui_master_plan.md](02_student_ui_master_plan.md)** | 전 대상(초등~대학·진로/재수/영재) + 영업(교사·부모·학원) | 단일 앱 + **적응형 셸(Adaptive Shell)** — 연령대 × 모드 × 역할 3축 분기. 영업 표면(학부모 보고서·교사 웹·학원 B2B). |
| **[03_admin_console_plan.md](03_admin_console_plan.md)** | 앱 관리 UI 구성 | **내부 운영 백오피스**(신설) vs 교사·학부모 대시보드(L7·Phase3) 구분. Control Center 4계층·22모듈 매핑·검수 큐. |
| **[04_admin_console_architecture.md](04_admin_console_architecture.md)** | 관리 UI 아키텍처 | Next.js + **Admin BFF** + **RBAC 선결**(현재 부재). 8 core engines ↔ L1~L7 매핑·감사 로그·이중 회계. |
| **[05_source_reconciliation.md](05_source_reconciliation.md)** | 출처·정합 기록 | Kiki ChatGPT 설계안(원본 [A]~[E]) 통합 기록 — 채택 항목·**충돌 원장 5건**·EOS 북극성 처리. |
| **[06_design_system.md](06_design_system.md)** | 학생 앱 디자인 토큰·테마 정본 | 색(`fromSeed`·정서 안전 error=앰버)·간격(`AppSpacing` 4pt+오프리듬)·타이포(`textTheme` 롤)·다크모드·접근성 규약. **구현 착지**(MOB-09~11). |

### 정본 경계 (기존 아키텍처 문서와의 관계)

이 도메인은 아래 문서를 **대체하지 않고 UI/IA 관점으로 재조직·확장**한다. 계층 책임·계약의 정본은 여전히 아키텍처 문서다.

- `../architecture/05_interaction.md` — **L5 상호작용 정본**(디바이스 전략·정서 안전 UI·자동 커리큘럼 정렬 입출력·시각화 스택). 화면 계약의 뿌리.
- `../architecture/05a_learning_scene_dsl.md` — **학습 장면 합성 DSL 정본**(`SceneElement` 7종·답 미루기/낙인 금지 스키마 불변식).
- `../architecture/06_application_modes.md` — **L6 응용 모드 정본**(6모드·`ModeConfig`·자동 커리큘럼 정렬 7차원·단일 앱 분기).
- `../architecture/07_community.md` — **L7 커뮤니티·소셜 정본**(다중 풀이 갤러리·학부모 보고서·교사 대시보드).
- `../architecture/04d_adaptive_pedagogy_engine.md`·`03c_content_strategy_cache.md` — **런타임 교수법 선택·교수법-중립 렌더 정본**(01 문서의 파이프라인 재해석 근거).

---

## 전역 UI 불변식 (4개 문서 공통·위배 금지)

이 표의 원칙은 `CLAUDE.md`·아키텍처 문서에서 유래한 **하드 제약**이다. 어느 화면·메뉴·관리 기능도 이를 어기지 않는다.

| # | 불변식 | 의미 | 근거 |
|---|---|---|---|
| 1 | **표현 ≠ 의미** | 수학 로직·정답·검증은 서버(독립 코어 L1-L4). 클라(Flutter·웹·admin)는 View Layer — 수학 판정을 담지 않는다. 문항·수식·해설은 구조(AST/JSON)로 코어 저장·렌더는 클라. | `CLAUDE.md` 슬89, `05:15` |
| 2 | **반(反)게임화** | 정답률 랭킹·스트릭·카운트다운·보상 연출 금지. 학습 경로 시각화는 허용. (자유학기제 모드만 `gamification_level` 적정) | `05:31-34`, `CLAUDE.md` 교수학 금기 |
| 3 | **답 미루기·낙인 금지** | 막혔을 때 바로 정답 금지 — Polya 4단계·graded Hint 우선. 정답/수정 텍스트를 담을 필드가 스키마에 **구조적으로 없다**. | `05a` 스키마 불변식, `hint.schema.yaml` |
| 4 | **패드 중심 · 폰 동반 · 별도 웹** | 태블릿이 플래그십(저지연 손글씨·그래프·다중 풀이). 폰은 동반·저사양 하한선. 교사 웹만 별도 React/Next. | `05:27-28` |
| 5 | **단일 앱 + 모드/역할 분기** | 학생·학부모는 한 Flutter 앱 안 UI·권한 레이어. 교사만 별도 웹. PRD "3개 앱 분리"는 반려. | `06:170-184`, `07:61-74` |
| 6 | **RBAC 선결(관리 UI)** | 현재 `UserProfile`에 role 필드 없음·콘텐츠 CRUD 무인증. 관리 UI 도입 전 role 컬럼+`require_role`이 선결. | `db/models/user.py`(role 부재 실측), `.claude/agents/backend-engineer.md:249` |
| 7 | **거부 우회 금지·측정치 이중 회계** | 게이트 판정을 UI에서 손편집 금지. 핵심 판정치는 SaaS(Langfuse)뿐 아니라 인프로세스에서도 산출(죽으면 "측정 실패"를 보여야). | `CLAUDE.md` 프로세스·AI·신뢰 금기 |

---

## 구현 상태 범례

문서 전반에서 **계획을 구현으로 착각하지 않도록** 다음 범례를 쓴다. (`src/mobile/README.md` 청사진과 실제의 괴리를 반복하지 않기 위함.)

- 🟢 **구현됨** — 코드가 실동작(end-to-end 또는 서버측 완료)
- 🟡 **부분** — 일부 축·경로만 배선됨
- 🔴 **계획** — 설계 문서·백로그만 존재, 코드 없음

### 현재 스냅샷 (2026-07-24)

| 영역 | 상태 | 비고 |
|---|---|---|
| 학생 앱 6개 라우트(온보딩·채팅·문제·OCR·수식입력·로그인) | 🟢 | `src/mobile/lib/core/router.dart` |
| `LearningScene`/`Visualization` 선언적 명세 렌더 | 🟢 | `scene_renderer.dart`·`l4/learning_scene.py` 연결 |
| L6 6개 모드 게이팅(school_progress·suneung·thinking·metacognition·gifted·retake) | 🟢 | `l6/` 실측 |
| 자동 커리큘럼 정렬 — 깊이 축(7차원 중 1) | 🟡 | `l6/school_progress/gating.py` 깊이정렬만 |
| 하단 탭 네비게이션 셸(홈/학습/탐구/나) | 🟢 | `core/shell/app_shell.dart`·`StatefulShellRoute`(MOB-08) |
| 디자인 토큰·테마(색·간격·타이포·다크모드) | 🟢 | `lib/theme/`(MOB-09~11)·[06_design_system.md](06_design_system.md) |
| 온보딩 노출 영속·딥링크 | 🔴 | 후속 |
| ConceptDSL·PedagogyAdapter·Runtime Pedagogy Selector | 🔴 | `REND-01`/`PED-02` todo·`concept_dsl.py`·`l3/render/` 부재 실측 |
| 관리(admin) UI·교사/학부모 대시보드 | 🔴 | 코드 0·문서만(L7 Phase3) |
| RBAC(role 컬럼·`require_role`) | 🔴 | 설계만(`backend-engineer.md`) |

---

**버전**: 1.0 | **작성**: 2026-07-24 | **다음 검토**: 하단 탭 슬라이스 착수 / RBAC 착수 시점
