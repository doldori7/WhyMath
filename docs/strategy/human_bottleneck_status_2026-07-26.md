# 인간 병목(사람 게이트) 현황 진단 — 2026-07-26 스냅샷

> **점-시각(point-in-time) 기록.** 병목 정본은 `docs/strategy/status_roadmap_2026-07.md` §4 및 `backlog/gates.yaml`(대장)이다. 이 문서는 그것들을 수정하지 않고, 2026-07-26 기준 "지금 사람이 무엇을 해야 하는가"를 한 화면으로 요약한 진단이다.
>
> 재생성 근거: `python3 scripts/harness/backlog.py gates list` · `... status`. 문서의 모든 상태는 해당 출력과 1:1 대조 완료.

---

## 0. 한 줄 결론

**math-completion 크리티컬 패스는 사람 병목 `S3-01`(파일럿 5~10명 모집·운영, owner=kiki)을 관통한다.** `S4-01/02/03`(수학 K-12 완성 등)은 전부 `depends_on: [S3-01]`이라 파일럿이 돌기 전엔 착수할 수 없다. 다만 S3-01의 **코드 선행(S1-11·MOB-01·S3-02/03/04)은 전부 done**이고, 남은 병목은 라이브 조건(①코치 flip 라이브 확인·③S3-02 라이브 재측정 통과)과 Kiki의 "출시 직전" 모집 착수 판단뿐이다. 즉 **지금 가장 깊은 인간 병목 = 파일럿(S3-01) 착수 판단**이며, 그와 별개로 즉시 실행 가능한 인간 판단점은 **PED-01 이차함수 파일럿 E2E 실행 지시**다. (명시적 게이트 `gates.yaml` 기준으로는 즉시 clear 가능한 pending 게이트가 0건이라는 점은 유효하다.)

---

## 1. 인간 병목이 표현되는 3채널

이 프로젝트에서 "인간 병목"은 `사람 병목`/`사람 게이트`로 정형화되어 있고, 코드·데이터상 3개 채널로 나타난다.

| 채널 | 데이터 | 자동 판정 |
|---|---|---|
| ① 명시적 게이트 | `backlog/gates.yaml` 의 `Gate(status=pending)` | 태스크 `requires_gates` / 트랙 `entry_gate`로 착수 차단 |
| ② 사람 소유 태스크 | `backlog/tasks/*.yaml` 의 `owner: kiki\|partner` | selector가 `Exclusion(reason="owner")`로 자동 후보 제외 |
| ③ 정지 신호 | selector `stall_reason()` → `"human_gate"` | 후보 0 + 게이트/owner 제외만 남을 때 `/drive` 정지 |

---

## 2. 채널 ① — 명시적 사람 게이트 (`gates.yaml`, 6건)

**pending 1건 · cleared 5건.**

### ⏳ pending (1)
| 게이트 | kind | 막는 범위 | 지금 못 여는 이유 | 여는 방법(미래) |
|---|---|---|---|---|
| `G-s5-subject-expansion` | decision | `subject-expansion` 트랙 **전체 = E1~E6, 11태스크**의 `entry_gate` (E1:6, E2~E6 각1) | "수학 K-12 완성 전 어떤 과목도 착수 금지"(불변 전제). 선행 `S4-01` 미완 → 판정 태스크 `S5-01`도 착수 불가 | `S4-01` 완성 → `S5-01` 판정 → `backlog.py gates clear G-s5-subject-expansion --evidence "..."` (waive는 Kiki 전용) |

### ✔ cleared (5)
| 게이트 | 해소 근거 요약 |
|---|---|
| `G-phaiakes9-key` | 라이브 키 투입·6모델 READY·rephrase 184/590 성공(2026-07-09). 실측 비용검증은 S1-12로 이관 |
| `G-kiki-device-demo` | S1 탈출 게이트 ① 실기기 학습 루프 시연 영상 제출(2026-07-16) |
| `G-domain-partner` | **AI 검수 전환 결정**(2026-07-10)으로 게이트 요건에서 제외 — 파트너 영입은 별도 격상 트랙 |
| `G-crosswalk-approval` | 오개념 crosswalk 64행 Kiki 서명(2026-07-08~12)·기계 reject-only·프로덕션 적재 0 |
| `G-orphan-prod-run` | Kiki가 Phaiakes9 prod DB에서 진단 스크립트 실행, 진짜 orphan 0건 확인(2026-07-16) |

---

## 3. 채널 ② — 사람 소유 태스크 (`owner: kiki`, 4건)

| 태스크 | 상태 | 지금 착수 불가 이유 |
|---|---|---|
| `S1-14-exit-gate-judgement` | **done** ✅ | Kiki 2026-07-16 서명 완료 (`G-kiki-device-demo` clear) |
| `S3-01-pilot-cohort` (파일럿 5~10명 모집·운영) | todo | **`S4-01/02/03`의 선행**(이들이 `depends_on: [S3-01]`) = math 크리티컬 패스의 사람 병목. 착수 트리거 4종 중 ⓪S3-02/03/04·②MOB-01·(①의 태스크 S1-11)은 **done**이나, 라이브 조건 ①코치 flip 라이브·③S3-02 라이브 재측정(89% 하락 실확인)은 미검증. "조기 착수 금지"(희소 자원 소진·조기출시 압력 방지). 브리핑 정본 `docs/strategy/s3_pilot_briefing.md` |
| `S5-01-expansion-gate-judgement` | todo | `G-s5-subject-expansion`를 clear하는 판정 태스크 — 선행 `S4-01`(수학 K-12) 미완 |
| `E1-90-earth-science-placement` | todo | S5 게이트 뒤(E축)·"순서 날조 금지"(현 E축 문서에 미배정) |

> 참고: 사람 소유 태스크는 자동 후보에 오르지 않지만, 소유자 본인이 `start/done --as kiki`로 직접 완료 기입할 수 있다(HARN-06). 다만 위 3건은 선행조건 미충족이라 지금 기입 대상 아님.

---

## 4. 채널 ③ 밖의 "라이브 인간 판단점" (정식 게이트 아님)

- **`PED-01-pedagogy-pack-dsl-foundation`** [owner=claude · status=blocked]
  - 핵심 슬라이스 3건 머지 완료(#575·#576·컴파일러), `PED-02` 런타임 셀렉터(#590)로 선행 의존 해소.
  - 잔여 acceptance = **이차함수 파일럿 E2E 완주** 슬라이스가 "**사용자 지시 대기**"로 정지.
  - → **Kiki의 한마디("파일럿 돌려")로 즉시 풀리는 유일 항목.** owner는 claude라 정식 사람 게이트는 아니지만, 실질 병목은 사람 지시다.

---

## 5. 권고 다음 행동

1. **크리티컬 패스는 사람 병목을 관통한다**: `S4-01/02/03`(수학 K-12 완성 등)은 전부 `depends_on: [S3-01]`(파일럿, owner=kiki)이라 **파일럿이 돌기 전엔 S4 수학 코어를 착수할 수 없다.** 해금 순서 = `S3-01`(파일럿) → `S4-01` → `S5-01` → `G-s5-subject-expansion` → E축. S3-01의 코드 선행(S1-11·MOB-01·S3-02/03/04)은 모두 done이므로, 남은 병목은 (a)라이브 조건 ①flip·③재측정 검증 (b)Kiki의 "출시 직전" 모집 착수 판단이다.
2. **Kiki 결정 1건**: `PED-01` 이차함수 파일럿 실행 여부. 지시하면 claude가 E2E 완주.
3. **사람 병목과 무관한 자동화 후보**(지금 착수 가능, owner=claude): `PED-03-adaptive-pedagogy-policy`·`SEC-01-dialogue-image-encryption` (둘 다 S4·priority 5·의존성 해소).
4. **미래 리마인드**: `G-s5-subject-expansion`은 `remind_after_days: null`이라 자동 리마인드가 없다. `S4-01` 완료 시점에 수동으로 게이트 판정을 상기할 것.

---

## 6. 메타 — "Kiki 수동 시간 최소화"의 실적

이 프로젝트는 사람 병목을 **줄이는** 프로그램(초인간 검증 기준, 2026-07-08)을 명시적으로 운용한다: "인간 검수 = 안전" → "측정된 기계 게이트 = 안전". 그 결과 원래 병목 5개 중 **②(Phaiakes9 라이브)는 개통으로 clear**, **④(도메인 파트너)는 AI 검수 전환으로 게이트에서 제외**됐다. 남은 사람 항목은 전부 *법령·판단 유래*(파일럿 동의·확장 판정)로, 기계 대체가 금지된 정직 폴백 구간이다.

---

## 근거 파일

- `backlog/gates.yaml` — 게이트 대장 6건
- `backlog/tracks.yaml` — `subject-expansion.entry_gate: G-s5-subject-expansion`
- `backlog/tasks/{S1-14,S3-01,S5-01,E1-90}-*.yaml` — 사람 소유 태스크
- `backlog/tasks/{PED-01,S4-01}-*.yaml` — 라이브 판단점·크리티컬 패스
- `scripts/harness/{selector.py,report.py,backlog.py}` — `human_gate` 정지코드·게이트 표시/CLI
- `docs/architecture/glossary.md` — "사람 병목" 용어 정의
- `docs/strategy/status_roadmap_2026-07.md` §4 — 병목 Top-5 정본
- `docs/standards/superhuman_verification_standard.md` — 사람 병목 축소 기준
