# 데이터 플랫폼 모듈 — "선언≠배선" 일반 탐지기 실측 기록 (2026-08-07, OPS-22)

> **범위**: 장기 미병합 브랜치 `claude/whymath-data-platform-design-8ceaf5`(2026-08-03,
> `ops/reach_audit.py` 855줄 + 본 문서 원안 510줄)가 설계한 "공급↔소비 도달 대장"을 OPS-22가
> 재구현했다. 그 브랜치는 트렁크에 랜딩한 적이 없고, 담고 있던 분류 대장(`pending-task:REC-01`
> 등)은 2026-08-03 시점 스냅샷이라 대부분 stale이었다(REC-01·VIZ-01·VIZ-02·NLP-02·SEC-10·
> REC-03·PED-05·KG-01 등이 그 사이 `done`으로 전환). 이 문서는 그 구조적 설계(4축 정적 감사·
> 그랜드파더 만료 계약)를 **재사용**하고, 분류 대장은 2026-08-07 현재 `backlog/tasks/*.yaml`
> 상태로 **처음부터 재구축**한 기록이다 — 옛 문서를 갱신한 것이 아니라 같은 제목으로 새로
> 쓴 문서다(옛 문서는 main에 존재한 적이 없다).

관련 정본: `src/backend/whymath_backend/ops/declared_unwired_audit.py`(구현) ·
`docs/architecture/operations_module_gap_review.md`(§3 D1, "만들고 입력을 잇지 않음" 최초 명명) ·
`docs/standards/superhuman_verification_standard.md`(변별력·자가검증 규율) ·
`backlog/tasks/ARCH-25-grandfather-expiry-contract.yaml`(그랜드파더 만료 계약 원조) ·
`backlog/tasks/OPS-22-generic-declared-unwired-detector.yaml`.

---

## §1. 반복된 사고 — 왜 "일반" 탐지기가 필요한가

이 저장소는 "무언가를 완비해 놓고 그것을 실제로 부르는 쪽을 잇지 않아, 코드가 존재한다는
사실이 '돌아간다'로 잘못 읽히는" 사고를 최소 6회 반복했다:

| 회차 | 사고 | 축 | 대응(사후·축 전용) |
|---|---|---|---|
| 1~2 | `tests/infra` 199건 미실행 / required check `checks=[]` 통째 미강제 | CI 배선 | OPS-03·OPS-08 |
| 3 | 시각화 공급원 적재 0행 → 학생 도달 0회 | HTTP/공급원 | VIZ-01 |
| 4 | OCR 배포 경로 양쪽 비활성 → 학생 도달 0회("3회차" 자인) | HTTP | NLP-01 |
| 5 | `/v1/me/next-problem` 개인화 입력 0행("4·5회차" 자인) | HTTP/DB | REC-01 |
| 6 | 학습시간 집계 3테이블 writer 0건 | TimescaleDB | COLLAB-03 |

매번 대응은 **그 축 전용의 사후 런타임 리포트**(`recommendation_reach_report.py`·
`pedagogy_content_slot_reach_report.py`·`harness/visualization_reach_report.py`·
`harness/concept_reach_report.py`·`harness/assessment_seat_reach_report.py`)였다. OPS-22는
이 축들을 대체하지 않고, **아직 아무도 추적하지 않는 신규 공급 표면**에서 같은 사고가
커밋 시점에 잡히도록 4개 구조 축을 빌드타임 정적으로(DB·LLM·HTTP 호출 0) 감사한다.

---

## §2. 설계 — 구 브랜치에서 재사용한 것 vs 새로 만든 것

**재사용(구조적 접근)**:
- 4축 분리(HTTP 라우트·EventType·TimescaleDB·harness CLI)와 "미도달 *수*가 아니라
  *미분류*가 실패"라는 판정 규약.
- FastAPI 0.140 `_IncludedRouter` 언랩 재귀(`_walk_routes`) — 라우트 표 추출의 함정.
- harness CLI ↔ CI의 "직접 실행 + in-process import 전이" 도달 계산(`qa_pipeline`류
  subprocess-0 관례에 대응).
- 그랜드파더 만료 계약(`pending-task:<id>`가 `backlog/tasks/<id>.yaml` 실재 + `status !=
  done`일 때만 유효) — 이 부분은 구 브랜치가 아니라 `ARCH-25`(`ops/provenance_audit.py`)에서
  이식했다(구 브랜치의 유예 대장 규약은 ARCH-25보다 먼저 쓰였으나 `GrandfatherEntry` 같은
  구조화 타입 없이 자유 문자열이었다 — 이번 구현은 ARCH-25의 더 엄격한 형태를 따랐다).

**새로 설계한 것(구 브랜치와 다른 부분)**:
- **HTTP 소비 판정 확장** — 구 브랜치는 Flutter dart 호출만 "도달"로 쳤다. 이번 구현은
  **테스트 클라이언트 호출도 도달로 인정**한다(`client.get("/v1/...")`·
  `client.request("DELETE", "/v1/...")` 양쪽 패턴). 그 결과 구 브랜치가 "서버 전용
  표면"(`server-only-by-design`)으로 분류했던 라우트 다수가 실제로는 백엔드 통합테스트가
  이미 호출하고 있어 `reached`로 자동 분류됐다 — 분류 대장이 구 브랜치보다 훨씬 작아졌다.
- **템플릿 패턴 매칭** — 구 브랜치는 정규화된 문자열 완전 일치로 도달을 판정했는데, 테스트가
  흔히 쓰는 **리터럴 더미 ID**(`client.get("/v1/jobs/j1")`, 인터폴레이션이 아닌 하드코딩값)를
  그 방식으로는 못 잡는다는 것을 실측 중 발견했다(`GET /v1/jobs/{job_id}` 오탐 사례). 서버
  템플릿의 `{name}` 자리를 `[^/]+`로 푼 정규식 매칭(`_route_reached`)으로 교체해 해소했다.
- **EventType 축을 "생산자 존재"에서 "생산자 있는데 소비자 없음"으로 좁혔다** — 구 브랜치는
  전 11종(휴면 5종 포함) 중 생산자 보유 여부만 봤다. 이번 축은 **이미 생산되는 6종 중 실제로
  쿼리 필터(`ast.Compare`)로 읽히는지**만 본다(휴면 5종은 `event_data_contract.py`가 별도
  계약 면제로 이미 추적 중이라 중복 축이 되지 않게 범위를 좁혔다).
- **타임시리즈 축을 writer만이 아니라 writer↔reader 양방향**으로 봤다 — 실측 결과 3개 모델
  전부 writer 0인데, `privacy/{erasure,export,retention}.py`는 이미 **reader**(삭제·반출
  대상으로 참조)로 등재돼 있다는 "reader 있음·writer 없음"의 역방향 패턴을 발견했다.

---

## §3. 실측 스냅샷 (2026-08-07, `python -m whymath_backend.ops.declared_unwired_audit`)

```
[http_routes]      공급 91 · 도달 68 · 미도달 23 · 위반 0
[event_consumers]  공급  6 · 도달  3 · 미도달  3 · 위반 0
[timeseries_tables] 공급 3 · 도달  0 · 미도달  3 · 위반 0
[harness_clis]     공급 49 · 도달 10 · 미도달 39 · 위반 0

판정: 통과 — 모든 공급 항목이 도달했거나 의도가 선언돼 있다
```

미도달 65건 전부에 의도를 선언했다(대다수 `by-design` — 프레임워크 자동 표면·OAuth 콜백·
법정 권리 표면·내부 게이팅 도구·Phase 후속 설계·배치 생성기·라이브 의존 CLI 등). **신규
발견 — 이번 구현 중 실측으로 드러난, 어떤 기존 태스크도 추적하지 않던 공백 3건**을 아래처럼
새 백로그 태스크로 등재하고 `pending-task:`로 유예했다:

| 발견 | 축 | 신규 태스크 |
|---|---|---|
| 막힘·답입력·시각화조작 EventType — S3-16/슬96-J가 생산자만 배선, 소비자(지표·리포트) 0건 | EventType | `S4-22-attempt-event-signal-consumer-wiring` |
| SEC-10(세션 가시성·전체 로그아웃)이 서버 엔드포인트만 배선, 모바일 화면·인터셉터 0건 | HTTP | `MOB-10-auth-session-lifecycle-client-wiring` |
| PED-03(학습 공급 루프)의 study/outcome 엔드포인트를 부르는 쪽이 모바일에도 통합테스트에도 없음(단위 함수만 직접 테스트) | HTTP | `MOB-11-content-supply-loop-client-wiring` |

기존에 이미 추적 중이던 공백도 `pending-task:`로 그대로 유예했다(신규 등재하지 않음 —
중복 등재 금지): `COLLAB-03-learning-metrics-writer`(타임시리즈 3테이블 writer 0건, 그
notes가 이미 이 문서가 발견한 reader-only 패턴을 인용) · `NLP-01-ocr-reachability-
observability`(`POST /v1/ocr/pages` 다중 페이지 변형 — 단일 페이지 `POST /v1/ocr`은 이미
모바일이 호출) · `S4-16-residue-gate-demotion-battle`(진행 중인 게이트 승격 CLI).

---

## §4. 이 감사가 하지 않는 것 (정직한 공백)

- **활성화·배선 신설이 아니다** — 미도달을 발견해도 고치지 않는다. `NLP-01` ⑥·`REC-01` ⑤와
  동형("가시화까지, 활성화는 아니다").
- **기존 축별 리포트를 대체하지 않는다** — `recommendation_reach_report.py` 등은 그 축의
  *런타임 도달률*(실 DB 카운트)을 본다. 이 감사는 *빌드타임 구조*(라우트 표·AST·ci.yml)만
  본다 — 둘은 상보적이지 대체 관계가 아니다.
- **문항 수준 중복 감사(D3, 구 브랜치의 별도 설계)는 이 태스크 범위 밖이다** — 그 갭이
  현재도 유효한지는 별도 실측이 필요하며(2026-08-03 시점 코퍼스 전수 집계 결과였다),
  OPS-22는 "선언≠배선" 축만 다룬다.
- **QA 판정 보존·비집행 가시화(D2, 구 브랜치의 별도 설계)도 범위 밖** — `continue-on-error`
  waiver 동결은 이미 이 저장소에 유사 패턴(`ARCH-25` 그랜드파더 만료 계약)이 있고, OPS-22와
  별개 태스크로 다룰 사안이다.

---

## §5. 재현 방법

```bash
cd src/backend
python -m whymath_backend.ops.declared_unwired_audit          # stdout 리포트
python -m whymath_backend.ops.declared_unwired_audit --json report.json
```

CI는 `declared-unwired-audit` 잡(상시 실행 — `needs: changes` 미의존, 이유는 `.github/
workflows/ci.yml`의 해당 잡 주석 참조)이 매 push·PR마다 이 명령을 그대로 실행한다.
`tests/infra/test_declared_unwired_audit_wiring.py`가 그 배선 자체의 실재성을 동결한다.
