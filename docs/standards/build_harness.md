# 빌드 하네스 (Build Harness) — 작업일정 관리·순차 조율 표준

> **정본**: `backlog/` + `scripts/harness/` | **채택**: 2026-07-08 결정로그 | **버전**: 1.1 (2026-07-16 병렬 조율 확장)
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
backlog/policy.yaml      조율 정책 — 겹침·ad-hoc 감지 강제 수준 (off|warn|block)
```

- **태스크 상태는 CLI로만 변경한다**: `python3 scripts/harness/backlog.py <cmd>`.
  직접 편집하면 PostToolUse 훅이 무결성을 검증한다 (깨지면 차단).
- ROADMAP.md·MEMORY.md는 **서사(왜)** 담당으로 존속 — 수치·순서·다음 작업의 정본은 backlog다.
- 병렬 세션: 태스크당 1파일 + `session` claim 필드 + events union-merge로
  "1 세션 = 1 도메인 = 1 브랜치 = 1 태스크"가 파일 수준에서 강제된다
  (`docs/standards/parallel_sessions.md` 연계).
- **태스크 `paths` 필드 (v1.1)**: 태스크가 만질 파일 범위를 glob으로 선언한다
  (예: `src/backend/api/**`). `start` 프리플라이트·check-edit 훅이 이 선언으로
  **교집합 작업**을 사전 감지한다. 디렉토리는 `src/backend/` 또는
  `src/backend/**` 형태로 — 와일드카드 없는 리터럴은 단일 파일로 해석된다.
  기존 태스크의 paths 부재는 위반이 아니나, 신규 태스크는 `add --path` 선언을 관례화한다.

## 3. 순차 조율 규칙 (selector)

착수 가능 = `todo` ∧ 의존성 전부 done ∧ 게이트 전부 cleared/waived
∧ owner=claude ∧ 트랙 entry_gate 통과 ∧ 미claim.
정렬 = (stage 순서, priority, −해금 후속 수, id) — **결정적**.

- **owner=claude는 *자동 착수 후보*의 조건**이다(next/status/brief). 사람-소유
  태스크(owner=kiki/partner)는 자동 후보에 절대 오르지 않지만, **소유자 본인이
  `start <id> --as <owner>` / `done <id> --as <owner> --artifact ...`로 직접
  기입할 수 있다**(HARN-06 — 2026-07-16 S1-14 사례에서 사람 태스크의 CLI 완료
  경로 부재가 실측된 설계 공백의 해소). `--as`가 태스크 owner와 불일치하면 거부,
  deps·게이트·claim·증적 검사는 사람 기입에도 동일 적용(우회 아님), 이벤트에
  `as_owner`가 남아 claude 기입과 구분된다.

- **E축 하드락**: subject-expansion 트랙은 `G-s5-subject-expansion` 통과 전
  알고리즘 수준에서 후보 제외 — "수학 완성 전 어떤 과목도 착수하지 않는다"
  (subject_expansion_e_axis_v1.md 불변 전제)가 코드로 강제된다.
- 후보 0 + 사람 게이트만 잔존 → `/drive`는 정지하고 Kiki 행동 목록을 보고한다.

## 3b. 원격 claim — 병렬 세션 실시간 조율 (v1.1)

로컬 `session` claim은 각 세션 worktree의 backlog 사본에만 기록되어 merge 전까지
서로 보이지 않는다(TOCTOU 레이스). **원격 claim**이 이 구멍을 막는다:

- `start`가 origin에 `refs/claims/<task-id>` ref를 push한다. push는
  `--force-with-lease=<ref>:`(빈 expect)의 **CAS 원자성** — 원격에 ref가 없어야만
  성공하므로, 두 세션이 동시에 같은 태스크를 start해도 정확히 한쪽만 성공한다.
- ref가 가리키는 blob에 claim 메타(JSON: branch·UTC ts)가 담긴다 — conflict 시
  상대 세션이 즉시 식별된다.
- **conflict만 차단**(신호가 확정적) — offline/권한 오류는 경고 + 이벤트 로그 후
  로컬 claim으로 진행한다(fail-open — 훅·CLI가 개발을 볼모로 잡지 않는다).
- `done`/`block`이 ref를 해제한다. 세션이 죽어 ref가 남으면 `claims reap`이
  3중 기준(TTL 초과 · 태스크 이미 done/cancelled · 태스크 미존재)으로 청소한다
  (기본 dry-run, 실삭제는 `--apply`).
- `next`/`brief`(SessionStart)가 원격 claim을 조회해 다른 세션의 작업을
  후보 제외·브리핑 노출한다.

## 3c. 조율 정책 — 단계적 강제 (warn → block)

`backlog/policy.yaml`의 rule 3종 (전부 warn으로 시작 — "측정 없는 도입 없음"):

| rule | 감지 대상 | 감지 지점 |
|---|---|---|
| `path_overlap` | 태스크 간 파일 범위 교집합 | `start` 프리플라이트 · check-edit 훅 |
| `scope_drift` | 내 claim 태스크의 선언 paths 밖 편집 | check-edit 훅 |
| `adhoc_edit` | claim 없이 코드 도메인(src/·infra/) 편집 | check-edit 훅 |

- warn = stderr 1줄 + `events.ndjson`에 `policy_warn` 적재 (측정) / block = 거부(exit 1·2).
- **승격 기준**: 2주 또는 30세션 관찰 후 (a) 실제 충돌 예방 사례 ≥1 또는 정탐률 ≥50%
  (b) 오탐으로 인한 개발 중단 0건 → 해당 rule만 block 승격.
  승격 = policy.yaml 1줄 수정 + MEMORY.md 결정로그 + `policy_promote` 이벤트.
- 측정 요약: `backlog.py policy report --days 14`.
- 겹침 판정은 보수적 2단 근사(실파일 교집합 + 정적 프리픽스 포함 — `pathscope.py`).
  과탐이 미탐보다 안전하다는 원칙. 원격 claim conflict는 단계적 도입의 예외로
  **즉시 차단**(신호가 확정적이므로).

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
python3 scripts/harness/backlog.py start|done <id> --as kiki ...  # 사람-소유 태스크의 소유자 본인 기입(HARN-06)
python3 scripts/harness/backlog.py block <id> --reason "..." / unblock <id>
python3 scripts/harness/backlog.py gates list|clear|waive
python3 scripts/harness/backlog.py add --id ... --title ... --path "src/backend/**"  # /plan 산출물
python3 scripts/harness/backlog.py validate        # 무결성 전수 검증
python3 scripts/harness/backlog.py claims list --verbose   # 원격 claim 현황 (누가 무엇을)
python3 scripts/harness/backlog.py claims release <id> [--force]  # claim 해제 (남의 것은 --force)
python3 scripts/harness/backlog.py claims reap [--apply]   # stale claim 청소 (기본 dry-run)
python3 scripts/harness/backlog.py overlap <id>    # 착수 전 겹침 진단
python3 scripts/harness/backlog.py policy show|report      # 정책 값·warn 측정 리포트
```

테스트: `uv run --with pytest --with pyyaml pytest tests/harness` (142건).

## 8. 금기

- ❌ backlog 상태를 마크다운 산문에만 기록하고 CLI 갱신 생략
- ❌ 증적(artifact) 없는 done
- ❌ evidence 없는 게이트 clear
- ❌ E축 게이트 우회 착수 (waive는 Kiki 전용 결정)
- ❌ ROADMAP "현재 위치"를 backlog와 어긋나게 단독 편집
- ❌ 원격 claim conflict를 무시하고 착수 (남의 claim 강제 해제는 `claims release --force` — 상대 세션 확인 후)
- ❌ 측정(policy report) 없이 warn→block 승격, 또는 결정로그 없는 승격
