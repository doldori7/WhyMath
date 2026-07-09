---
description: 사람 게이트 대장 점검 — Kiki 행동 필요 항목을 한 화면 요약, clear/waive 처리
argument-hint: "[clear <G-id>|waive <G-id>] (인자 없으면 목록)"
---

# /gates — 사람 게이트 점검·리마인드

## 임무
프로젝트 진행을 막고 있는 **사람(Kiki) 행동 대기 항목**을 한 화면에 요약하고,
해소된 게이트를 증거와 함께 clear 처리한다.

## 실행 절차

### 1. 목록 (기본)
```bash
python3 scripts/harness/backlog.py gates list
```
출력에 다음을 덧붙여 보고:
- 경과일수 내림차순 정렬 (가장 오래 막힌 것 먼저)
- 각 게이트가 **몇 개의 태스크를 막고 있는지** (`backlog.py status --json`의 blocked·next로 판단)
- Kiki가 해야 할 **구체적 행동 1줄** (게이트 title·notes 기반)

### 2. clear (해소 확인 시)
증거 없이 clear 금지 — 커밋·문서·실측 기록을 evidence로 남긴다:
```bash
python3 scripts/harness/backlog.py gates clear <G-id> --evidence "<커밋/문서/기록>"
```
clear 후 `backlog.py next`를 실행해 **해금된 태스크를 즉시 보고**하고,
사용자가 원하면 `/drive`로 바로 이어간다.

### 3. waive (예외 통과)
게이트를 건너뛰는 결정은 **Kiki 전용**이다. 사용자가 명시적으로 지시했을 때만:
```bash
python3 scripts/harness/backlog.py gates waive <G-id> --reason "<사유>"
```
waive 사유는 MEMORY.md 결정로그에도 append한다.

## 원칙
- G-s5-subject-expansion(E축 하드락)은 S5 판정 태스크를 거치지 않고 clear/waive 금지
- 게이트 추가가 필요하면 backlog/gates.yaml에 스키마를 지켜 추가 후 `validate`
