# review_status 백필 실측 리포트 (PB-03 — 노출 4단 ③ 검수축 활성화)

> **한 줄**: 문제은행 7종(2,647건)의 `review_status`가 전부 `None`이었다 —
> `l6._shared.is_review_cleared`(PB-03 신설)의 fail-closed 설계상 이 상태로는 L6 6모드가
> 전건 차단되는 상태였다. 코퍼스별로 기존 감사 라벨(`docs/data/corpus_audit_*.jsonl`)에
> `corpus_audit_eval`(`load_audit`·`summarize`, 단일 권위)의 측정 판정을 적용해 백필했다.
> 코퍼스가 현재 100% 자체생성이라 오늘 시점 실손실은 0 — 이건 결함 수정이 아니라
> 방어선 이중화(defense-in-depth)다.

## 0. 배경

`docs/architecture/problem_bank_gap_review_r2.md`의 노출 4단(①게이트 통과 → ②코퍼스 편입 →
③노출 적격(`is_exposable`+검수) → ④실노출) 중 ③단이 실제 코드에 3갈래로 빠져 있었다.
`review_status`(검수, 운영 축)는 `is_exposable`(저작권, 법적 축)과 **절대 하나로 합치지
않는다** — 각 호출 지점에서 독립된 `if`로 둘 다 확인한다. 이 리포트는 검수 축을 실제로
켠 백필 실행 기록이다.

## 1. 판정 규칙

`corpus_audit_eval.load_audit`·`summarize`를 함수 직접 호출로 재사용(서브프로세스 아님).
코퍼스당 감사 라벨 파일(`docs/data/corpus_audit_*.jsonl`)의 `summarize(labels)` 결과에
아래 규칙을 적용해 **코퍼스 전체에 단일 판정**을 내리고, 그 판정을 코퍼스 내 미평가
레코드 전원에 백필한다:

- 감사 라벨 파일이 없으면 → `pending`(평가 자체를 시도하지 않음 — 라벨 없음 = approved
  아님을 fail-closed로 보장).
- 있으면 `report.n < 200`이면 → `pending`(증거 부족).
- 아니면 `report.defect_rate_upper_bound(0.95) <= 0.02`면 → `approved`, 아니면 → `rejected`.

## 2. 백필 실행 결과 (2026-08-08)

```
python -m whymath_backend.harness.problem_corpus_review_status_backfill --all
```

| 코퍼스 | 총건 | 채움 | 이미 보유 | 감사 라벨 파일 | 표본 n | 결함 | 95% Wilson 상한 | 판정 |
|---|---:|---:|---:|---|---:|---:|---:|---|
| conceptual_v0 | 360 | 360 | 0 | `corpus_audit_conceptual_v0.jsonl` | 200 | 0 | 0.0133 | **approved** |
| generated_v0 | 620 | 620 | 0 | `corpus_audit_240.jsonl` | 240 | 0 | 0.0111 | **approved** |
| killer_v0 | 120 | 120 | 0 | `corpus_audit_killer_v0.jsonl` | 120 | 0 | n/a | **pending**(n=120 < 200) |
| misconception_mc_v0 | 1,080 | 1,080 | 0 | `corpus_audit_mc_v0_r2.jsonl` | 200 | 0 | 0.0133 | **approved** |
| rephrased_v0 | 429 | 429 | 0 | `corpus_audit_rephrased_v0_census.jsonl`(전수) | 429 | 0 | 0.0063 | **approved** |
| problem_bank_v1 | 4 | 4 | 0 | 없음 | — | — | — | **pending**(라벨 없음) |
| probability_finite_v0 | 34 | 34 | 0 | 없음 | — | — | — | **pending**(라벨 없음) |
| **합계** | **2,647** | **2,647** | **0** | | | | | |

`rephrased_v0`는 표본 rotation-2가 아니라 `_census`(전수 감사) 파일을 정본으로 사용했다
(PB-03 지시대로 — 표본 rotation-2는 이미 폐기된 이전 판정).

**바이트 결정론 검증**: 백필을 연속 2회 실행 — 1회차 `filled=2,647`(전건), 2회차
`already_set=2,647·filled=0`. 두 실행 사이 7개 corpus jsonl 파일의 MD5 해시가 전부 동일
(`md5sum` 직접 대조로 확인). 코퍼스 판정 근거는 `docs/data/review_status_backfill_audit/
<코퍼스 디렉터리명>.jsonl`에 문항당 1줄(총 2,647줄)로 남겼다.

**스키마 검증**: 백필 후 `problem_bank_conceptual_v0`(360건)·`problem_bank_v1`(4건) 전건을
`Problem.model_validate`(authoring 키 분리 후)로 재검증 — 전건 통과(`extra="forbid"`
위반 없음, `review_status` 필드가 정상 값으로 인식됨).

## 3. 축별 구현·확인 요약

### 축① — 기본 CAT 저작권 게이트 (`api/me.py`)

`recommend_next_problem`의 기본 CAT SQL(`candidate_stmt`, 2124행 근처)에
`Problem.source_type.notin_([s.value for s in METADATA_ONLY_SOURCES])` 조건을 추가했다.
`METADATA_ONLY_SOURCES`는 이미 같은 파일이 수능 분기(2007행)에서 쓰던 것과 동일 import
(`whymath_backend.l6.suneung`에서 재노출된 것)를 그대로 재사용 — 새 상수를 만들지 않았다.

### 축② — 검수 축 활성화

- `l6/_shared.py`에 `is_review_cleared(problem)` 신설(`is_exposable` 바로 다음, 141행대) —
  `problem.review_status == ReviewStatus.approved`만 True, `None`/`pending`/`rejected`는
  fail-closed False. `is_exposable`과는 별개 함수로 유지(설계 핵심, 합치지 않음).
- `api/me.py`의 같은 `candidate_stmt`에 `Problem.review_status == ReviewStatus.approved`도
  독립 조건으로 추가(SQL 레벨, 축①과 같은 곳).
- L6 6개 게이팅 파일(`retake`·`suneung`·`school_progress`·`metacognition`·`gifted`·
  `thinking`의 `gating.py`) 전부에서 기존 `if not _shared.is_exposable(problem): return False`
  바로 다음 줄에 독립된 `if not _shared.is_review_cleared(problem): return False`를 추가했다
  (기존 파일 스타일 그대로 — 전 6파일 동일 `return False` 스타일 확인 후 적용).

### 축③ — L6 후보 절단 해소 (`api/gating.py`)

- `_CANDIDATE_FETCH_LIMIT`을 1000→3000으로 상향(현재 코퍼스 2,647건 + 여유).
- `_fetch_candidates`에 절단 관측을 추가 — fetch 건수가 정확히 상한과 같으면 `SELECT
  count(*)`를 추가 질의해 `logger.warning("gating candidate fetch truncated: fetched=%d
  total=%d truncated=%d", ...)`을 남긴다(조용한 절단 금지).
- **정직한 공백**: 이 sandbox에 살아있는 Postgres가 없어 실측 성능 비교는 하지 못했다 —
  보수적으로 상한만 올린 것이다. SQL 사전축소로의 재설계는 이번 범위 밖(성능 실측 후
  별도 후속).

## 4. 변별력 테스트 (신규 4종)

`tests/backend/harness/test_problem_corpus_review_status_backfill.py`(hermetic, tmp_path
기반 — 실제 `docs/data/corpus_audit_*.jsonl`을 판정 근거로 그대로 사용하는 
`compute_corpus_verdict`/`verdict_from_audit_labels` 단위 테스트 + CLI e2e)와
`tests/backend/l6/test_review_status_gate.py`(hermetic, `Problem.model_construct` 기반 —
`is_review_cleared` 단위 + L6 6모드 배선 확인), `tests/backend/api/test_gating_candidate_limit.py`
(hermetic, monkeypatch로 `_CANDIDATE_FETCH_LIMIT` 축소 + caplog로 절단 로그 검증)로 구성했다.
축①(SQL where절에 `METADATA_ONLY_SOURCES` 조건 포함 여부)은 **실PG 라이브 검증이 필요**하나
이 sandbox엔 살아있는 Postgres가 없어(기존 known 공백), `sqlalchemy.dialects.postgresql
.dml`의 컴파일된 SQL 문자열(`str(candidate_stmt.compile(dialect=postgresql.dialect(),
compile_kwargs={"literal_binds": True}))`)에 두 조건절이 실제로 나타나는지 검사하는
hermetic 화이트박스 테스트로 대체했다(정직하게 명시 — 실PG 통합 테스트는 미실행).

## 5. 정직한 잔여(못 한 것)

- `probability_finite_v0`(34건)·`problem_bank_v1`(4건) — 감사 라벨 파일이 없어 신규 감사를
  수행하지 않았다(범위 밖 명시). `pending` 고정 상태로 남는다.
- L6 성능 실측(축③ `_CANDIDATE_FETCH_LIMIT` 상향의 실 쿼리 시간 비교) — sandbox에 살아있는
  Postgres가 없어 미실행.
- `populate_problem_bank` 실DB 재적재 — 이 세션 sandbox에 Postgres가 없어 미실행(명령만
  준비: `python -m whymath_backend.l1.problem_bank.populate --problems <corpus>/problems.jsonl`,
  7개 코퍼스 각각). 즉 이번 백필로 갱신된 `review_status`·`source_type` 게이트가 실제
  운영 DB에는 아직 반영되지 않았다 — 코퍼스 JSONL(정본)만 갱신됨.
- 전체 pytest 스위트 — `uv sync`가 `pyproject.toml`의 `ocr` extra(`rapid-latex-ocr`,
  numpy<2.0 요구)와 `great-expectations`(pandas>=2.2.3 유발 numpy>=2.1 계열 요구)의 universal
  lock 충돌로 실패하는 기존에 알려진 환경 문제(이번 태스크와 무관, 2026-08-08 재확인)라
  `uv pip install -e ".[dev]"`(lock 우회)로 개별 설치해 우회했다. 이 경로로 설치된 환경에서
  `tests/backend/api/`·`tests/backend/l6/`·`tests/backend/harness/`는 실행했으나(§6 참조),
  **레포 전체 스위트는 확인하지 못했다** — CI를 최종 판정으로 넘긴다.

## 6. 관련

- 검수 축 함수: `src/backend/whymath_backend/l6/_shared.py`(`is_review_cleared`)
- 백필 CLI: `src/backend/whymath_backend/harness/problem_corpus_review_status_backfill.py`
- 판정 근거 감사 로그: `docs/data/review_status_backfill_audit/*.jsonl`
- 축①+② 배선: `src/backend/whymath_backend/api/me.py`(`recommend_next_problem` 기본 CAT
  SQL) · L6 6개 `gating.py`
- 축③: `src/backend/whymath_backend/api/gating.py`(`_CANDIDATE_FETCH_LIMIT`·`_fetch_candidates`)
- 배경 문서: `docs/architecture/problem_bank_gap_review_r2.md`(노출 4단 규약)
