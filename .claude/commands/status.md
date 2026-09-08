---
description: 프로젝트의 현재 상태를 종합 점검 (backlog/ 단일 진실 원천 기반)
---

# /status — 현재 상태 점검

## 임무
사용자가 *어디에 와 있고, 다음에 무엇을 해야 하는지* 한 화면에 보여준다.
상태의 정본은 **backlog/** 이다 — 마크다운을 읽고 추론하지 말고 CLI 출력을 렌더링한다.

## 실행 절차

### 1. 정본 상태 조회
```bash
python3 scripts/harness/backlog.py status
python3 scripts/harness/backlog.py validate --quiet
git log --oneline -5
git status --short
```

### 2. 보고서 출력
CLI 출력을 다음 순서로 정리 (한 화면):

```
🎯 WhyMath — 현재 상태

[스테이지] <current_stage> — 진행률 (backlog status 그대로)
[진행 중] ▶ <id> [브랜치]  /  (없음)
[차단] ✖ <id> — 사유
[사람 게이트 대기] ⏳ <G-id> [kiki] — N일 경과  ← 오래된 순
[다음 단일 행동 후보] next 상위 3건 + 선정 사유
[최근 커밋] git log 5건

[권장 다음 명령]
> /drive          # 다음 태스크부터 순차 진행
> /gates          # 사람 게이트 처리
> /plan <주제>    # 새 작업을 백로그에 추가
```

### 3. 서사적 맥락 (필요 시)
스테이지의 *의미*가 궁금할 때만 ROADMAP.md·docs/strategy/status_roadmap_2026-07.md를
보조로 읽는다. 수치·순서·다음 작업의 정본은 항상 backlog CLI다.

## 출력 원칙
- 한 화면 안에
- "다음 단일 행동"을 항상 제안 — 사용자가 *결정만 하면* 되도록
- validate 경고가 있으면 최상단에 표시

## 호출 빈도
- SessionStart 훅이 요약 브리핑을 자동 주입하므로, /status는 상세가 필요할 때
