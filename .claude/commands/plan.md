---
description: 새 작업·기능·Phase의 상세 계획 수립
argument-hint: "[기능명 또는 영역]"
---

# /plan — 계획 수립

## 임무
사용자의 입력(`$ARGUMENTS`)에 대해 7계층 어디에 속하는지 분석하고, 구현 가능한 작업 단위로 분해한다.

## 실행 절차

### 1. 입력 분류
`$ARGUMENTS`를 다음 카테고리로 분류:

- **Phase 계획** ("Phase1", "Phase2", ...): ROADMAP.md 참조 + 마일스톤 세부화
- **계층 작업** ("L1-data", "L4-pedagogy", ...): 해당 계층 docs 참조
- **기능 단위** ("OCR 통합", "Polya 프롬프트", ...): 7계층 매핑 후 책임 분배
- **막연한 의도** ("뭐 해야 하지", "다음 할 일"): /status로 리디렉션 권유

### 2. 7계층 매핑
다음 질문에 답한다:

```
[ ] 이 작업은 어느 계층에 속하는가? (L1~L7)
[ ] 의존하는 하위 계층은? (계층 침범 점검)
[ ] 영향 받는 상위 계층은? (변경 전파 점검)
[ ] 어떤 서브에이전트가 적합한가?
```

### 3. 작업 분해
SMART 기준으로 분해:

- **Specific**: 무엇을 만드는가? (모호 금지)
- **Measurable**: 완료 기준은? (테스트·메트릭)
- **Achievable**: 2시간~2일 단위로
- **Relevant**: 현재 Phase 목표와 일치?
- **Time-bound**: 예상 소요 시간

### 4. 백로그 등록 (계획의 최종 산출물 — 문서만 남기고 끝내기 금지)
분해된 작업 단위를 **backlog 태스크로 실체화**한다. 계획은 backlog에 등록되어야
/drive가 이어받을 수 있다:

```bash
python3 scripts/harness/backlog.py add \
  --id <STAGE-NN-slug> --title "..." \
  --track <math-completion|subject-expansion|infra-debt> \
  --stage <S0~S5|E1~E6> --layer <worktree 7종> --subject <과목> \
  --priority <1~5> \
  --depends <선행 태스크 id> --gates <G-id> \
  --acceptance "완료 기준 1" --acceptance "완료 기준 2"
```

- 의존성·게이트·acceptance를 빠뜨리지 않는다 (순차 조율의 입력이다)
- 사람이 해야 하는 작업은 `--owner kiki` (자동 착수 제외)
- 등록 후 `backlog.py validate` green 확인

### 5. 계획서 출력 형식

```markdown
# 계획: [기능명]

## 📍 컨텍스트
- Phase: [현재 Phase]
- 계층: L[N] ([계층명])
- 의존성: L[M], L[K]
- 서브에이전트: [에이전트명]

## 🎯 목표
[1줄 정의]

## ✅ 완료 기준
- [ ] 기능 작동 (구체적 시나리오)
- [ ] 테스트 통과 (커버리지 70%+)
- [ ] 문서 업데이트
- [ ] MEMORY.md에 결정 기록

## 📦 작업 단위
1. [작업 1] — 예상 N시간
2. [작업 2] — 예상 N시간
...

## ⚠️ 리스크·미해결
- [예상 리스크 1]
- [질문이 필요한 점]

## 🚀 첫 단일 행동
[지금 당장 할 1가지]
```

### 6. 사용자 확인
- 계획에 대한 피드백 요청
- 우선순위 조정 옵션 제시
- 즉시 `/drive` 또는 `/implement <태스크 id>`로 넘어갈지 묻기

## 원칙

### 작게 시작
- 첫 계획은 1~2일 분량
- 큰 작업은 더 작은 작업으로 분해
- 한 번에 너무 많이 계획하지 않음

### 계층 경계 존중
- L1 작업이 L4 코드를 건드리면 → 잘못된 설계
- L4가 L2를 *구현*하면 → 책임 분리 위반
- 횡단 관심사(로깅·모니터링)는 *별도 계획*

### MEMORY.md 동기화
- 계획 확정 시 MEMORY.md에 추가
- 폐기된 대안도 기록
- 결정 근거 명시

## 호출 예시

```
> /plan Phase1-MVP
> /plan L1-ncic-crawler
> /plan 학생 손글씨 OCR 통합
> /plan 영재 트랙 추가
> /plan 도메인 파트너 영입 전략
```
