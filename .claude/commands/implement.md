---
description: 계획된 작업을 적합한 서브에이전트로 위임하여 구현
argument-hint: "[영역:기능명] 예: data:ncic-crawler, mobile:chat-ui"
---

# /implement — 구현 위임

## 임무
`$ARGUMENTS`로 받은 작업을 *해당 계층 서브에이전트*에 위임하여 컨텍스트를 격리하고 효율을 극대화한다.

## 실행 절차

### 1. 입력 파싱
형식: `[영역]:[기능명]` 또는 `[영역명]`

| 영역 prefix | 서브에이전트 | 계층 |
|---|---|---|
| `data:` | data-engineer | L1 |
| `ml:` | ml-engineer | L2 |
| `llm:` | llm-architect | L3 |
| `pedagogy:` | pedagogy-designer | L4 |
| `mobile:` | flutter-engineer | L5 |
| `backend:` | backend-engineer | L5 |
| `content:` | content-curator | L6/L7 |

### 2. 사전 점검 + 백로그 착수 (필수)
구현 전 다음 확인:

- [ ] 대응하는 backlog 태스크가 있는가? (없으면 `/plan`으로 먼저 등록)
- [ ] CLAUDE.md의 금기·원칙 위반 없는가?
- [ ] 의존하는 하위 계층 *준비 완료*?
- [ ] 테스트 전략 있는가?
- [ ] 어떤 데이터·시크릿 필요한가? (사전 확인)

태스크를 **claim하고 시작한다** (의존성·게이트 미해소면 CLI가 거부한다):

```bash
python3 scripts/harness/backlog.py start <태스크 id>
```

### 3. 서브에이전트 호출
해당 에이전트 정의(`.claude/agents/[name].md`)를 컨텍스트로 두고 작업 수행.

```
[Task 위임 형식]
- 서브에이전트: [name]
- 작업: [기능명]
- 입력: [구체적 요구사항]
- 출력: [기대 산출물]
- 제약: [CLAUDE.md 금기 + 영역별 추가 제약]
```

### 4. 구현 작업
서브에이전트가 수행하는 표준 단계:

```
a. 영역 문서 읽기 (docs/architecture/0N_*.md)
b. 표준 읽기 (docs/standards/*.md)
c. 코드 작성 (TDD 권장)
d. 테스트 작성·실행
e. 문서 업데이트
```
(PR은 서브에이전트 내부 절차가 아니라 아래 **5.5 단계**에서 오케스트레이터가 연다 —
"f. PR 준비"라는 한 줄에 맡겨 뒀더니 실제로 열리지 않았다.)

### 5. 검증
구현 완료 후 자동 점검:

- [ ] 테스트 통과
- [ ] 린터 통과 (ruff·black·dart format)
- [ ] 타입 체크 통과 (mypy·dart analyze)
- [ ] CLAUDE.md 금기 위반 없음
- [ ] MEMORY.md 결정 기록 필요한가?

### 5.5 PR 생성 (필수 — 요청을 기다리지 않는다)
커밋한 산출물이 있으면 **PR을 연다**. "PR 지시를 못 받았다"는 보류 사유가 아니다
(CLAUDE.md "✅ 절대 원칙 → 완료·병합"). **머지는 하지 않는다** — CI green 후 SQUASH 머지는
`"pr"` 지시 또는 Kiki 판단이다.

예외 4종이면 건너뛰되 **어느 예외인지 보고에 1줄로 적는다**:
조사·계획 전용(산출물 없음) / 미완·게이트 대기 / CI red / Kiki 명시 보류.

### 6. 백로그 완료 처리 (필수 — PR 증적 동반)
```bash
python3 scripts/harness/backlog.py done <태스크 id> --artifact "<PR 번호를 담은 증적>"
# 예외로 PR 없이 종결할 때만:
#   ... --artifact "<커밋>" --no-pr {investigation|incomplete|ci-red|kiki-hold}
```
증적 없는 done, 그리고 PR 참조(`#12`·`.../pull/12`) 없는 done은 CLI가 거부한다(exit 1).
해금된 후속 태스크를 확인해 보고에 포함.
(이 단계를 건너뛰면 Stop 훅이 세션 종료를 차단한다.)

### 7. 결과 보고
사용자에게 짧게 보고:

```
✅ 구현 완료: [기능명]

생성/수정된 파일:
- src/.../foo.py (신규)
- src/.../bar.py (수정)
- tests/.../test_foo.py (신규)

테스트: ✅ 24/24 통과
린터: ✅
타입: ✅

다음 단계:
> /review    # 코드 리뷰
> git commit # 커밋
```

## 원칙

### 컨텍스트 격리
- 메인 컨텍스트에 *구현 세부사항* 누적 금지
- 서브에이전트에 위임하여 메인 컨텍스트 정리 유지

### 한 번에 한 영역
- `/implement data:foo + mobile:bar` 같이 동시 위임 금지
- 한 작업 완료 후 다음

### TDD 권장
- 테스트 먼저 작성하면 의도 명확
- LLM 호출은 *반드시* 모킹

### LLM 비용 의식
- LLM 호출 코드 작성 시 *항상* 로컬 가능성 검토
- 캐싱·배치 우선 검토

## 호출 예시

```
> /implement data:ncic-crawler
> /implement ml:bkt-model
> /implement llm:router
> /implement pedagogy:polya-prompts
> /implement mobile:chat-screen
> /implement backend:session-api
> /implement content:misconception-db
```

## 안티 패턴 (피할 것)

❌ `/implement everything` — 너무 큼  
❌ `/implement Phase1` — 계획 단계와 혼동  
❌ 영역 prefix 없이 호출 — 서브에이전트 라우팅 실패  
❌ 테스트 없이 구현 완료 선언
