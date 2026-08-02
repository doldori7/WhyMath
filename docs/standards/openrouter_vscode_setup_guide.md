# OpenRouter + VS Code 개발 환경 설정 가이드

> **용도**: Kiki 개인 로컬 개발 환경(VS Code)에서 OpenRouter를 경유해 여러 AI 모델(Claude, GPT, Gemini 등)을 자유롭게 전환하며 코딩 작업을 진행하기 위한 안내서.
> **범위 주의**: 이 문서는 WhyMath *앱의* LLM 라우팅(L3 계층, `config.py`·`l3/router.py`)과 무관한 **개발자 도구용 가이드**다. 프로덕션 코드의 LLM 호출 경로는 반드시 CLAUDE.md의 라우터 경유 원칙(직접 호출 금지)을 따르며, 본 문서로 인해 변경되지 않는다.

---

## 1. 왜 OpenRouter인가

OpenRouter는 여러 LLM 제공사(Anthropic·OpenAI·Google 등)의 모델을 단일 API 키·단일 엔드포인트로 호출할 수 있게 해주는 게이트웨이 서비스다. VS Code용 AI 코딩 확장(Cline 등)과 결합하면 다음이 가능하다.

- 작업 도중 모델을 자유롭게 전환(예: 설계는 Claude Opus, 반복 수정은 저가 모델)
- 여러 제공사 API 키를 각각 관리할 필요 없이 OpenRouter 키 하나로 통합
- 모델별 비용을 한 대시보드에서 비교·관리

## 2. 준비물

- VS Code 설치 완료
- OpenRouter 계정 가입 완료 (https://openrouter.ai)

## 3. 설정 절차

### 3-1. VS Code 확장 설치
1. VS Code 좌측 Extensions 탭(또는 `Ctrl+Shift+X`)을 연다.
2. "Cline"을 검색해 설치한다. (자율 코딩 에이전트로, OpenRouter 연동이 내장되어 있다.)

### 3-2. OpenRouter API 키 발급
1. https://openrouter.ai 대시보드 → **Keys** → **Create Key**.
2. 발급된 키는 즉시 안전한 곳(비밀번호 관리자 등)에 저장한다. **코드나 저장소에 하드코딩하지 않는다** (CLAUDE.md 보안 원칙).

### 3-3. Cline에 OpenRouter 연결
1. VS Code에서 Cline 아이콘을 클릭해 패널을 연다.
2. 설정(⚙️)에서 **API Provider**를 `OpenRouter`로 선택한다.
3. 3-2에서 발급한 API 키를 입력한다.

### 3-4. 모델 선택
Cline 모델 드롭다운에서 원하는 모델을 고른다. 작업 중 언제든 전환 가능하다. 예:

| 용도 | 예시 모델 |
|---|---|
| 복잡한 설계·아키텍처 판단 | `anthropic/claude-opus-*` |
| 일반 코딩·반복 수정 | `anthropic/claude-sonnet-*`, `openai/gpt-5` |
| 대량·저비용 작업 | 각 제공사의 소형 모델(mini/haiku 급) |
| 멀티모달(이미지 포함) | `google/gemini-*` |

정확한 모델 ID는 OpenRouter 모델 목록(https://openrouter.ai/models)에서 최신 상태를 확인한다 — 모델명·가격은 수시로 바뀐다.

### 3-5. 기존 작업 폴더 열고 이어가기
1. VS Code에서 `File → Open Folder`로 작업하던 프로젝트 폴더를 연다.
2. Cline 채팅창에 진행 중이던 작업 맥락을 요약해 전달한다.
3. Plan 모드로 방향을 확인한 뒤 Act 모드로 실제 변경을 진행한다.

## 4. 비용 관리 팁

- OpenRouter 대시보드 → **Activity**에서 모델별·요청별 사용량과 잔액을 확인한다.
- 모델 목록 페이지에서 토큰당 가격을 비교한 뒤 작업 난이도에 맞는 모델을 고른다.
- 크레딧 소진 알림(대시보드 → Settings)을 설정해 예상치 못한 과금을 방지한다.

## 5. 보안 체크리스트

- [ ] API 키를 코드·커밋·공개 저장소에 넣지 않았는가
- [ ] 키를 VS Code 확장 설정(로컬 저장) 또는 환경변수로만 관리하는가
- [ ] 더 이상 쓰지 않는 키는 OpenRouter 대시보드에서 즉시 폐기(Revoke)했는가

## 6. WhyMath 앱 코드와의 관계

WhyMath 백엔드의 LLM 호출은 이 가이드와 **별개**다. 프로덕션 코드는 항상:

- `config.py`의 모델 핀(`anthropic_model_mid/high` 등)과 `l3/router.py`(`LOCAL_MODEL_MATRIX`)를 통해서만 호출
- 로컬 LLM(Ollama) 우선 검토 후 클라우드 호출
- 모든 호출이 Langfuse로 추적

OpenRouter를 WhyMath 백엔드의 LLM 제공사로 *신규 채택*하려면(개발자 개인 도구가 아니라 앱 스택 변경) CLAUDE.md 기술 스택 표 갱신 + MEMORY.md 결정 로그 등재가 선행되어야 한다. 본 문서는 그 범위를 다루지 않는다.
