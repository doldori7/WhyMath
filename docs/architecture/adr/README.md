# ADR 계열 규약 — `docs/architecture/adr/`

> **결정일 2026-09-05 (Kiki) · 게이트 `G-eos-adr-numbering-series`의 판정**

## 규칙 3줄

1. **ADR 번호 계열은 이 디렉터리 하나뿐이다.** 다른 계열(`EOSADR-00n` 등)을 만들지 않는다.
2. **새 ADR은 다음 빈 번호를 받는다.** 눈으로 고르지 말고 `ls docs/architecture/adr/`로 확인한다.
3. **계획서 100 §3.16의 "ADR-001~010"은 번호가 아니라 결정해야 할 *주제 목록*이다.** 그 번호를
   저장소 파일명으로 쓰지 않는다 — 아래 매핑표로만 연결한다.

## 왜 이 규칙인가

계획서 100 §3.16은 ADR-001~010을 지정하는데(001 Core Boundary·002 Subject Adapter·007 AI
Gateway …), 저장소는 이미 ADR-001 = 이벤트 저장소, ADR-002 = 학생 풀이 단계 엔티티로 번호를
썼다. 계획서 번호를 그대로 채택하면 **같은 번호가 두 주제를 가리킨다** — 태스크 번호에서 세 번
겪은 HARN-10/38과 같은 유형의 사고다(`eos_source_docs_gap_review_2026-08-31.md` §7.3-④).

기존 2건을 개명하는 안은 기각했다: 코드·테스트·alembic·백로그에 걸친 `ADR-002` 참조 12건 이상이
파손된다(`grep -rn "ADR-002"` 실측).

## 현재 계열 (2026-09-05)

| 번호 | 주제 | 상태 |
|---|---|---|
| [ADR-001](./ADR-001-event-storage-postgresql-first.md) | 이벤트 저장소 PostgreSQL 우선 | 채택 |
| [ADR-002](./ADR-002-student-solution-step-entity.md) | 학생 풀이 step = 별도 정규 엔티티 | 채택 |
| [ADR-003](./ADR-003-subject-contract-v1-provisional.md) | Subject Contract v1 잠정 · 교차과목 프로브 후 Freeze | **Provisional** (target 2026-09-27) |

**다음 빈 번호: ADR-004.**

## 계획서 100 §3.16 주제 ↔ 저장소 매핑

| 계획서 주제 | 저장소 대응 | 상태 |
|---|---|---|
| Core Boundary | `docs/architecture/eos_core_adapter_boundary.md` + 배정 정본 `scripts/analysis/eos_core_adapter_boundary_scan.py`(`BOUNDARY_MAP`) | **충족** — ADR 형식은 아니나 556모듈 전수 배정으로 결정 내용이 정본화됨(EOS-65 done) |
| Subject Adapter | [ADR-003](./ADR-003-subject-contract-v1-provisional.md) · 계약 정본 `schema/subject_adapter.py`(EOS-66·EOS-69) | **부분** — 계약은 착지, 상태는 Provisional |
| AI Gateway | — | **미착수** — 대응 문서 0건 |

**나머지 7건은 주제명이 저장소에 없다.** 계획서 100 원본은 Kiki 보유이며 저장소에 반입돼 있지
않다(`grep -rln "계획서 100"` = 리뷰·계획 문서 6건, 전부 *인용*이지 원본이 아니다). 위 3건은
`eos_source_docs_gap_review_2026-08-31.md` §7.3-④가 예시로 인용한 것뿐이다.

**검색 범위 명시(부재 판정 절차)**: 위 "미착수"·"주제명 없음" 판정은 `docs/` 전체의 주제명
문자열 검색과 `docs/architecture/adr/` 파일 목록에 근거한다. 계획서 100 원본을 대조한 것이
**아니다** — 원본이 반입되면 이 표를 전수 갱신해야 한다.

## 새 ADR 쓸 때

```bash
ls docs/architecture/adr/          # 다음 빈 번호 확인
# docs/architecture/adr/ADR-00N-<주제-슬러그>.md 로 작성
# 이 README의 "현재 계열" 표에 1행 추가 + "다음 빈 번호" 갱신
```

문서 상단에 `상태`(초안/Provisional/채택/폐기)·`결정일`·`대상`·`관련`을 적는다 —
ADR-001~003이 그 형식이다.
