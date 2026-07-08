# 빌드 하네스 (Build Harness) — 작업일정 관리·순차 조율 표준

> **정본**: `backlog/` + `scripts/harness/` | **채택**: 2026-07-08 결정로그 | **버전**: 1.0
>
> 이 문서의 "빌드 하네스"는 프로젝트 *구축을 관리하는* 레이어다.
> `src/backend`의 WH-1(튜터링)·WH-S(솔버)는 **제품 런타임 하네스**로 완전히 별개다.

---

## 1. 무엇이 바뀌었나 (구 하네스 → 신 하네스)

| | 구 (2026-07-08 이전) | 신 |
|---|---|---|
| 작업일정 | 사람이 편집하는 마크다운에 분산 (stale) | `backlog/` 기계가독 단일 진실 원천 |
| 다음 작업 | 세션마다 사람이 지시·Claude가 재추론 | `next`가 결정적으로 계산 |
| 세션 시작 | 수동 `/status` | SessionStart 훅이 브리핑 자동 주입 |
| 상태 갱신 | 자율 (자주 누락) | Stop 훅이 미갱신 종료 차단 |
| 사람 대기 | ROADMAP 산문에 묻힘 | `gates.yaml` 대장 + 경과일 리마인드 |
| 순차 진행 | 없음 | `/drive` 주도 모드 루프 |
| 과목 범위 | 수학 암묵 | 다과목 개방 스키마 (E축: 물리~영어, 지구과학 배치 결정 대기) |

## 2. 단일 진실 원천 — `backlog/`

```
backlog/tracks.yaml      트랙 3종 + stage_order (S0~S5 → E1~E6)
backlog/gates.yaml       사람 게이트 대장 (Kiki 수동 대기 추적)
backlog/tasks/<id>.yaml  태스크당 1파일 — 병렬 세션 충돌 원천 차단
backlog/events.ndjson    append-only 감사 로그 (merge=union)
```

- **태스크 상태는 CLI로만 변경한다**: `python3 scripts/harness/backlog.py <cmd>`.
  직접 편집하면 PostToolUse 훅이 무결성을 검증한다 (깨지면 차단).
- ROADMAP.md·MEMORY.md는 **서사(왜)** 담당으로 존속 — 수치·순서·다음 작업의 정본은 backlog다.
- 병렬 세션: 태스크당 1파일 + `session` claim 필드 + events union-merge로
  "1 세션 = 1 도메인 = 1 브랜치 = 1 태스크"가 파일 수준에서 강제된다
  (`docs/standards/parallel_sessions.md` 연계).

## 3. 순차 조율 규칙 (selector)

착수 가능 = `todo` ∧ 의존성 전부 done ∧ 게이트 전부 cleared/waived
∧ owner=claude ∧ 트랙 entry_gate 통과 ∧ 미claim.
정렬 = (stage 순서, priority, −해금 후속 수, id) — **결정적**.

- **E축 하드락**: subject-expansion 트랙은 `G-s5-subject-expansion` 통과 전
  알고리즘 수준에서 후보 제외 — "수학 완성 전 어떤 과목도 착수하지 않는다"
  (subject_expansion_e_axis_v1.md 불변 전제)가 코드로 강제된다.
- 후보 0 + 사람 게이트만 잔존 → `/drive`는 정지하고 Kiki 행동 목록을 보고한다.

## 4. 일상 워크플로우

```
세션 시작   → (자동) SessionStart 브리핑: 현재 스테이지·next 3·게이트 리마인드
주도 진행   → /drive              # 순차 루프 (기본 3태스크, 사람 게이트에서 정지)
단건 작업   → /implement <id>     # start → 구현 → done --artifact
새 계획     → /plan <주제>        # 산출물 = backlog add 태스크 등록
사람 게이트 → /gates              # clear는 evidence 필수
상세 상태   → /status
세션 종료   → (자동) Stop 훅: claim 태스크 미갱신이면 차단
```

## 5. 다과목 확장과의 관계 (비침투 원칙)

백로그의 `subject` 필드는 **빌드 관리 메타데이터**다. 런타임 `Subject` enum·
개념 그래프·문항 스키마를 일절 만지지 않는다 (subject_pack_spec_v1.md
"Subject enum ADD VALUE 금지"와 무충돌). 새 과목 추가 = `models.SUBJECTS` 1줄
+ 태스크 시딩. 문명의 어떤 교육 영역이든 — 대학 수학·물리·화학·생물·지구과학·
경제·역사·세계사·국어·영어 — 같은 스키마로 일정 관리된다. 착수 *순서*는
E축 정본 문서가 결정하며, 하네스는 그 순서를 게이트로 집행할 뿐 날조하지 않는다.

## 6. 아키텍처 감시 (infra-debt 트랙)

`ARCH-NN-playbook-audit` 반복 태스크가 플레이북 불변식(2대 철칙·8대 구조 원칙·
7대 붕괴 연쇄)·7계층 경계·이중 truth source를 정기 점검한다.
- 점검 기준: `docs/standards/build_checkpoint_questions.md` ·
  `docs/standards/playbook_part_review_questions.md`
- 감사 완료 시 다음 회차를 `backlog.py add`로 즉시 재생성한다 (감시 공백 금지).
- 위반 발견 = 상환 태스크 등록 (감사가 백로그를 먹여 살린다).

## 7. CLI 요약

```bash
python3 scripts/harness/backlog.py status          # 진행률·게이트·다음 후보 한 화면
python3 scripts/harness/backlog.py next --n 3      # 착수 가능 후보 + 선정 사유
python3 scripts/harness/backlog.py start <id>      # claim (규칙 위반 시 거부)
python3 scripts/harness/backlog.py done <id> --artifact "<PR/커밋>"   # 증적 필수
python3 scripts/harness/backlog.py block <id> --reason "..." / unblock <id>
python3 scripts/harness/backlog.py gates list|clear|waive
python3 scripts/harness/backlog.py add --id ... --title ...           # /plan 산출물
python3 scripts/harness/backlog.py validate        # 무결성 전수 검증
```

테스트: `uv run --with pytest --with pyyaml pytest tests/harness` (79건).

## 8. 금기

- ❌ backlog 상태를 마크다운 산문에만 기록하고 CLI 갱신 생략
- ❌ 증적(artifact) 없는 done
- ❌ evidence 없는 게이트 clear
- ❌ E축 게이트 우회 착수 (waive는 Kiki 전용 결정)
- ❌ ROADMAP "현재 위치"를 backlog와 어긋나게 단독 편집
