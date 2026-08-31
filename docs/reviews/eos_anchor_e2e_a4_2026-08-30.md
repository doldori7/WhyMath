# EOS-58 — 깊이앵커 A4 생성 E2E 관통 실증 (2026-08-30 · r2 2026-08-31)

> **r2**: PR #914 codex 리뷰 3건(P1-1 검수 payload 부재 · P1-2 회차 덮어쓰기 소실 · P2 종료
> 일괄 기록)을 한 뿌리(검수 큐의 내구 저장소 부재)로 상환 — 검수 큐를 **2층 구조**(내구
> `<out>.review.jsonl` 즉시 flush + 워크리스트 md는 큐 전체의 누적 렌더 뷰)로 재설계.
> 상세 §11 · 갱신 실측 §4.1 · 계약 테스트 §11.2 · 뮤테이션 §7(r2 2건 추가).

> **태스크**: `EOS-58-anchor-e2e-generation-proof` · **앵커**: A4 중3 이차방정식 · 성취기준
> `[9수02-20]`(단일 코드) · 2022 개정 — EOS-51 검증설계서 §앵커(깊이★ 폐쇄루프)·EOS-52 실사
> (원자 3·오개념 8·op-code 3·기존 문항 378).
>
> **G1(9/27) 차단 조건 그 자체**: "부품은 전부 실재하는데 앵커 축으로 관통한 적이 0"인 상태를
> 끝낸다 — **생성 배치 → SymPy 게이트 → 저장 → needs_review 워크리스트 생성**을 실 CLI로 1회
> 관통하고, 각 단계 산출물을 **행 수로** 실측했다(간접 신호 금지).

---

## 0. 결론 요약

| 축 | 결과 |
|---|---|
| 관통(acceptance ①) | **완료** — `problem_corpus_accumulate.main()`을 A4 인자로 구동, 시도 5 → 수용 1 저장·비수용 4 검수 큐+워크리스트, exit 0 (§4 전사·r2 재실행) |
| 실적재 행 수(acceptance ②) | 코퍼스 **1행** · GenerationLog 사이드카 **5행**(성공 4·실패 1) · **검수 큐 4행**(payload 전문 3·사유만 1 — r2 신설) · 워크리스트 **항목 4**(큐 전체 렌더 뷰·md 47줄) · 배치 리포트 **1건**(stdout JSON·run_id 포함) — 전부 파일을 직접 세어 확인 |
| HIT 로그(acceptance ②) | 이 관통 구간 **0건이 정직한 관측** — 워크리스트 생성 시점에 자연스러운 적재 지점 **없음**(§6 판단·테스트로 동결) |
| 상시화(acceptance ③) | 후속 태스크 — 미등재 확인(EOS-56=앵커 1급 등록·EOS-59=데이터 등급 라우팅, 별건). **등재 문안 §9** — 등재는 메인 세션 CLI 소관 |
| 대역 범위 | **가짜는 LLM 호출부(provider.generate) 하나뿐** — 생성기 조립·라우터·SymPy 게이트·dedup·저장·워크리스트·genlog 전부 실물 (§3.1) |
| 검증 | ruff·black·mypy --strict·lint-imports 전부 EXIT=0 · 신규 5 + 인접 32 테스트 green · 변별 뮤테이션 2건 red 확인 (§5·§7) |

---

## 1. 환경 실측 (LLM 유무 — 선실측 지시 이행)

| 항목 | 실측 방법 | 결과 |
|---|---|---|
| Ollama 바이너리 | `which ollama` | 없음 |
| Ollama 데몬 | `curl http://127.0.0.1:11434/api/tags` | **HTTP 000 · connection refused** |
| `ANTHROPIC_API_KEY` | env 존재 검사(값 미출력) | 없음 |
| `OPENAI_API_KEY` | env 존재 검사(값 미출력) | 없음 |
| `WHYMATH_ANTHROPIC_API_KEY` | env 존재 검사(값 미출력) | 없음 |

→ **이 샌드박스 LLM 0 확정.** 관통 실증은 hermetic(대본 provider)으로 전 배관을 실제 실행하고
(§3.1 — 가짜는 LLM 호출부 하나), 실 LLM 라이브 관통은 Kiki 머신 명령 블록(§8)으로 동봉한다.

## 2. 배관 실측 요지

### 2.1 "needs_review 워크리스트"의 실물 — 발명하지 않고 관통시킨 것

| 후보 | 실측 결과 | 판정 |
|---|---|---|
| `harness/needs_review_worklist.py` | `build_worklist`(비수용 GenerationOutcome→항목·우선순위 정렬) + `render_worklist_markdown`(검수자 md·needs_review에 사람 판단 체크박스) — 순수 함수 | **이것이 실물** |
| `problem_corpus_batch --worklist-out` | 스켈레톤 배치 CLI에는 위 좌석이 이미 배선돼 있음(선택 플래그) | 선례(미러 대상) |
| `problem_corpus_review_status_backfill`(OPS-24) | **다른 물건** — 노출 4단 중 ③단(코퍼스별 `review_status` 백필: corpus_audit_eval Wilson 판정 기반). 워크리스트(①단 게이트의 사람 검수 큐 입력)가 아님 | 이 관통의 종점 아님(§7 정직한 공백) |
| #841 라벨 JSONL | 검수 *판정* 승격 인프라(hit_cu_metrics `--verdicts` 입력) — 워크리스트의 하류 | 종점 아님 |

**발견한 공백**: 라이브 LLM 경로인 `problem_corpus_accumulate`는 outcome을 **카운트·사유 80자
샘플로 접어 폐기**했다 — needs_review 후보(사람 검수 큐 §03 정본의 입력)가 LLM 경로에서 휘발.
스켈레톤 배치에는 있는 좌석이 정작 LLM 경로에 없던 상태. 이번 태스크가 **같은 좌석을 미러**해
메웠다(신규 개념 0 — §3.2).

### 2.2 앵커 A4 기존 자산 (시드 활용)

- `data/corpus/problem_bank_generated_v0/problems.jsonl` 전체 **619행** 중 `[9수02-20]` 태그
  **184행** 실재(실측 2026-08-30) — quad 4밴드(short/mc/sqrt/sqrt_mc)가 S3-15 재태깅으로 A4
  성취기준에 정위치. 전건 `curriculum_version=2022_REVISION`·`review_status=approved`(기백필).
- 관통에서 이 184행을 **시드로 주입** — `load_corpus_index`가 canonical signature 184개를 전건
  적출(0.32s 실측)해 dedup index에 실었고, 시드 구조와 같은 대본 후보가 실제로
  `rejected_duplicate`로 차단됐다(§4 — 앵커 기존 자산이 배관에 살아 있음의 실증).

### 2.3 GenerationLog(EOS-55)·Run 로그의 실물

- **GenerationLog 사이드카** = `<out>.genlog.jsonl`(기본 ON·호출별 즉시 flush) —
  `LLMEquivalentProblemGenerator._emit_generation_log` → `append_generation_log_jsonl`.
  EOS-55 명명이 "생성 **Run** 재현성 로그"이므로 **호출 단위 Run 로그 = 이 사이드카**로 해석.
- **회차(배치) 단위 리포트** = `AccumulateReport` JSON(stdout 1건) — attempted/outcome_counts/
  appended (+이번에 `review_outcomes_count` 추가). 두 축 모두 §4에서 행 수로 셌다.
- 소비자 접점: `ops/hit_cu_metrics --generation-log`(CU당 토큰·비용 조인 — `cu_slug` 키).

## 3. 변경 파일 + 설계 판단

### 3.1 무엇이 실물이고 무엇이 대역인가 (배관 지도)

```
[대본 provider]──generate() 1곳만 대역
      │
      ▼
LLMEquivalentProblemGenerator          실물 — 프롬프트 정본 조립(fill/prompt_text)·Router().route()
  (provider 좌석만 교체)                      라우팅(실측: LOCAL·GENERAL→qwen2.5:7b 결정)·JSON 관대
      │                                      파싱·derive-and-verify·저작권 구조 강제·GenerationLog 방출
      ▼
orchestrator.run_batch                 실물 — 생성→게이트→구조 dedup→저장 조합
      ├── evaluate_equivalent_candidate  실물 — SymPy Tier1 답 검산·classify_solvability·
      │                                        근 선택(S2-i)·위생·LaTeX·동등성 4성분 스코어
      ├── canonical_signature dedup      실물 — 시드 = 실코퍼스 A4 184행
      └── JsonlCorpusSink → 증분 append  실물 — 코퍼스 JSONL
      │
      ├── <out>.genlog.jsonl             실물 — EOS-55 사이드카(즉시 flush)
      ├── <out>.review.jsonl             실물 — 내구 검수 큐(비수용 발생 즉시 flush·payload 전문·r2)
      └── <out>.worklist.md              실물 — 큐 전체의 누적 렌더 뷰(needs_review_worklist·r2 재설계)
```

### 3.2 변경 파일

| 파일 | 변경 | 판단 근거 |
|---|---|---|
| `src/backend/whymath_backend/harness/problem_corpus_accumulate.py` | r1: `AccumulateReport.review_outcomes`·`default_worklist_path`·`--worklist-out`+기본 기록. **r2(codex)**: ① `review_sink` 주입 seam(EOS-55 `generation_log_sink` 심 동형) — 배치 루프가 비수용 outcome **발생 즉시** 내구 큐 행을 흘림(orchestrator `run_batch` 일괄 호출 → `run_equivalent_generation` 회차 루프로 전환·계약 동일) ② `_queue_entry` — payload를 저장 경로와 동일 직렬화(`_to_record`→`_record_to_json`)로 조립(승격 가능 형태·이중 구현 0) ③ `default_review_queue_path`(`<out>.review.jsonl`) ④ `run_id`(uuid4)를 리포트·큐 행 조인 축으로 ⑤ main의 워크리스트 렌더를 **큐 파일 전체 로드**로 교체 | 기본 ON은 같은 CLI의 EOS-55 genlog 선례("적재가 기본이어야 '경로가 적재한다'가 참"). 즉시 flush는 2026-08-22 규칙 ①(실패해도 증거가 남는가). 싱크 예외는 never-break+타입명 로그(genlog 동형) |
| `src/backend/whymath_backend/harness/needs_review_worklist.py` (r2) | 내구 큐 계층 신설 — `ReviewQueueEntry`(payload 전문·sha·run_id·recorded_at·source_line)·`entry_from_outcome`(수용 상태 ValueError)·`append_review_queue_jsonl`(즉시 flush·genlog 동형)·`load_review_queue_jsonl`(타입명+줄 번호 실패 수집·줄 번호 주입)·`render_review_queue_markdown`(누적 뷰·payload sha 묶음·출현 횟수·행 참조·본문 요약). 구계층(`build_worklist`/`render_worklist_markdown`)은 무수정(batch 경로 소비) | 큐 규약의 정본 좌석. payload 직렬화는 순환 import(batch가 본 모듈 소비) 회피를 위해 주입식. sha는 `problem_id`(조립마다 새 uuid4 — 실측) 제외 canonical — 내용 동일성 키 |
| `tests/backend/harness/test_eos_anchor_e2e_a4.py` | r1 관통 5건 + **r2 계약 테스트 4건**(`TestReviewQueueDurability` — §11.2) + 재출현 묶음 1건, 기존 단언을 2층 구조로 갱신 | 계약 ①~④를 CLI(main) 레벨에서 동결 |
| `tests/backend/harness/test_needs_review_worklist.py` (r2 추가) | 큐 계층 단위 15건 — 행 조립·sha 키순서 무관·append 스탬프/source_line 미기록·로더 실패 수집·FileNotFoundError 전파·렌더 묶음/본문/접기/로드 실패 노출 | 기존 구계층 테스트 무수정 유지 |
| `docs/reviews/eos_anchor_e2e_a4_2026-08-30.md` (본 문서) | 실측 보고(r2 갱신) | — |

**바꾸지 않은 것(의도)**: `problem_corpus_batch`의 `--worklist-out`(선택 플래그·회차 메모리 뷰
유지 — 스켈레톤 경로는 수율 100% 설계·결정론 전면 재생성이라 누적 큐가 성립하지 않는 다른 물건)
· orchestrator·acceptance·llm_generator(무수정 — 게이트·생성기는 검증 계약, CUR-09 병행 트리
보호를 위해 파일대 밖 불가침).

## 4. 관통 실행 로그 (샌드박스 실실행 전사)

실행: 실 CLI `problem_corpus_accumulate.main()`을 아래 인자로 구동(대역은 provider 1곳 —
`unittest.mock.patch`로 `_build_live_generator`의 provider 좌석만 대본 교체, 조립 인자는 라이브와
동일). 대본 5응답은 outcome 6종 중 5종을 정확히 1건씩 유도하도록 사전 프로브로 실측 설계.

```
python -m whymath_backend.harness.problem_corpus_accumulate \
    --seed <A4 시드 184행.jsonl> --out a4_accumulated.jsonl --n 5 \
    --standard-code "[9수02-20]" --difficulty 2.5 \
    --topic-hint "중3 이차방정식 — 두 근 중 더 큰 근을 구하는 형태(답 하나)"
```

stdout 리포트(전문):

```json
{
  "attempted": 5,
  "accepted": 1,
  "appended": 1,
  "slug_conflicts": 0,
  "outcome_counts": {
    "accepted_stored": 1, "needs_review": 1, "rejected_gate": 1,
    "rejected_duplicate": 1, "generation_failed": 1
  },
  "seed_records": 184,
  "existing_out_records": 0,
  "run_id": "ced2462dd2884fbe852816e3b661e56e",
  "reason_sample": [
    "정확성 미검증 — 답이 여러 실근 중 하나이나 선택(큰 근/작은 근/유일)이 명시되지 않아 …",
    "정확성 실패 — Tier1 답 검산 fail: 조건 위반 — 잔차 ≠ 0: 8",
    "구조 중복 — 정규형이 같은 방정식·근 선택이 이미 코퍼스에 있음(표현만 다른 판박이·저장 차단·S2-l).",
    "생성기가 후보를 반환하지 못했습니다(None) — 생성 실패."
  ],
  "review_outcomes_count": 4
}
```
종료: **exit=0** (신규 수용 ≥1).

### 4.1 산출물 행 수 표 (파일 직접 계수 — 간접 신호 아님)

| 단계 | 산출물 | 실측 행 수 | 내용 확인 |
|---|---|---|---|
| 생성 | LLM 호출 | 5회(대본 5 전량 소비) | genlog와 1:1 |
| 게이트(SymPy) | 판정 | 수용 1 · 검수필요 1 · 게이트거부 1 · 구조중복 1 · 생성실패 1 | 사유 전건 리포트·워크리스트에 보존 |
| 저장 | `a4_accumulated.jsonl` | **1행** (1,213B) | `[9수02-20]`·`2022_REVISION`·`valid_from_year 2022`·`source_type 자체생성`·`license WHYMATH_GENERATED`·verify `x**2 - 40*x + 391 = 0`/largest — 로더 라운드트립 1건. 시드 파일 바이트 불변(증분 append) |
| Run 로그(EOS-55) | `a4_accumulated.genlog.jsonl` | **5행** (33,044B) | 호출 1건=1행. success `[T,T,T,T,F]` · 실패 행 `error_detail="응답 JSON 파싱 실패"` · 전 행 `model_name=qwen2.5:7b`(**실 라우터 결정** — task_type=generate·free→LOCAL·저작 패밀리 GENERAL) · 성공 4행 `cu_slug` 실림(저장 slug `wm-gen-a4-61371d379595` 포함 — hit_cu_metrics CU 조인 정체성) · `restore_input_snapshot` 전문 복원 통과(입력 스냅샷 spec에 `[9수02-20]` 기록 — 앵커 결속) |
| 검수 큐(r2) | `a4_accumulated.review.jsonl` | **4행** (4,928B) | 비수용 1건=1행·발생 즉시 flush. #1 needs_review·#2 rejected_gate·#3 rejected_duplicate는 **payload 전문**(문항·정답·해설·verify — 코퍼스 레코드 동일 직렬화·승격 가능 형태), #4 generation_failed는 payload 없음+사유만(본문 날조 금지). 전 행 `run_id=ced2462d…`(리포트와 조인) |
| 워크리스트(r2) | `a4_accumulated.worklist.md` | **항목 4 / md 47줄** (3,004B) | **큐 전체의 누적 렌더 뷰** — 헤더 `누적 행 4 · 항목(묶음) 4 · 로드 실패 0` · `상태별(묶음): 검수필요 1 · 게이트거부 1 · 과유사거부 1 · 생성실패 1` · #1=[needs_review] 최상단에 **문항·정답·해설·검산 조건 본문** + 행 참조(#1) + 사람 판단 체크박스 3종 |
| 회차 리포트 | stdout JSON | **1건** | 위 전문(run_id 포함) |

워크리스트 md 항목부 발췌(r2 — 전문은 러너 재실행으로 재현):

```
- 큐 저장소: …/a4_accumulated.review.jsonl — 누적 행 4 · 항목(묶음) 4 · 로드 실패 0
- 상태별(묶음): 검수필요 1 · 게이트거부 1 · 과유사거부 1 · 생성실패 1
- 별항: 해결 상태 추적·review_status 각인·승격 집행은 범위 밖(OPS-24·승격 태스크 소관)

## 1. [needs_review] wm-gen-a4-0ffffe3d6ec1 · 출현 1회
- 동등성 점수: 1.0000 · 최근 기록: 2026-08-31T00:10:47…+00:00 · run: ced2462d…
- 행 참조: #1
- 문항: 이차방정식 x^2 - 121 = 0 을 만족하는 자연수 x 를 구하시오.
- 정답: 11
- 해설: x^2 = 121 에서 x 는 11 또는 -11 이고, 자연수는 11이다.
- 검산 조건: x**2 - 121 = 0
- 기계 사유:
  - 정확성 미검증 — … 근 선택(unique) — 실근이 2개라 답이 유일하게 정해지지 않음
- 사람 판단(검수자 체크):
  - [ ] 교육적으로 타당한 동등문제인가
  - [ ] 수용(코퍼스 편입) / [ ] 반려 / [ ] 임계값 재검토 대상
## 2. [rejected_gate] … · 행 참조: #2 · 문항/정답/검산 조건 동반 — Tier1 잔차 ≠ 0: 8
## 3. [rejected_duplicate] … · 행 참조: #3 · 시드 A4 실문항(x**2-5*x=0·largest)과 정규형 동일
## 4. [generation_failed] (slug 없음) · 행 참조: #4 · 본문: (payload 없음 — 후보 미조립·사유만 기록)
```

## 5. 검증 결과 (exit code 판정 — r2 최종)

cwd `src/backend` · venv `scratchpad/venv312`:

| 검사 | 명령 | 결과 |
|---|---|---|
| ruff | `python -m ruff check . ../../tests/backend` | All checks passed! · **EXIT=0** |
| black | `python -m black --check --line-length 100 . ../../tests/backend` | 1287 files unchanged · **EXIT=0** |
| mypy | `python -m mypy --strict whymath_backend` | no issues in 552 files · **EXIT=0** |
| import-linter | `lint-imports` | 7계층 단방향 KEPT · **EXIT=0** |
| 신규·수정 테스트 | anchor e2e(9)·needs_review_worklist(23)·accumulate(6)·generation_log_wiring(13)·corpus_batch(28) | **79 passed** · EXIT=0 |

(r1 시점 수치: 신규 5·인접 56 — r2에서 계약 4건+재출현 1건·큐 단위 15건 추가.) 전체 스위트는
돌리지 않았다 — **"전체는 확인하지 못했다"를 명시**한다(메인 세션·CI 몫). 참고: 검증 중 트리에
CUR-09 병행 에이전트의 신규 파일이 착지 중이었다 — full-tree black의 일시 red 1회는 그 병행
쓰기와 겹친 것으로 최종 재실행에서 clean(내 파일대는 전 회차 clean).

## 6. HIT 로그(EOS-54) 판단 — 이 구간 0건이 정직한 관측인가

**판단: 0건이 정직하다. 워크리스트 생성 시점에 자연스러운 적재 지점은 없다.** 실측 근거:

1. **이벤트 계약이 사람 착석이다** — `schema/review_timer.py`·`harness/review_timer.py`의
   3이벤트(started/finished/aborted)는 전부 `reviewer_id` 필수·검수 세션(sitting) 페어링
   계약이다. 생성~워크리스트 구간에는 사람 착석이 존재하지 않는다.
2. **HIT 정의가 인간 개입 시간이다** — `ops/hit_cu_metrics` 정본(§6): "CU당 인간 개입
   시간(초): 그 CU 전 세션의 계측 경과 합". 기계 관통은 인간 개입 0초 — 이벤트를 만들면
   그것이 날조다(0 날조 금지·미측정≠0의 역방향).
3. **접점은 이미 하류에 실재한다** — 검수자가 워크리스트 항목을 여는 순간 `start_review(
   cu_slug=...)`가 HIT의 시작점이고, 이 관통이 만든 `cu_slug`(genlog·코퍼스 slug 동일 산식)가
   그대로 조인 키다. 본 관통은 저장 slug가 genlog `cu_slug`에 실림을 단언으로 동결했다 —
   즉 HIT 계측은 "이 구간에서 0건"이면서 "검수 시작 즉시 이 관통의 산출물에 붙을 수 있는"
   상태다(EOS-54/55 설계 그대로).
4. **테스트 동결** — `test_no_review_timer_events_are_fabricated_in_this_span`: 관통 산출
   디렉터리에 사이드카 3종(코퍼스·genlog·worklist) 외 파일이 생기지 않음을 단언(이 구간이
   타이머 JSONL을 만들기 시작하면 red — 날조 감지).

## 7. 변별 뮤테이션 (cp 백업 → 변조 → red 확인 → cp 복원 → cmp 대조)

| # | 변조 | 기대 | 실측 | 복원 |
|---|---|---|---|---|
| M1(r1) | `acceptance._evaluate_verification` 첫 줄에 `return "verified", reasons` 삽입(**SymPy 게이트 우회**) | 반려 분포 붕괴 → 관통 테스트 red | `test_full_pipe...` **FAILED**(outcome_counts 단언 — 오답·다근이 수용으로 새는 것을 감지) · 1 failed, 4 passed · EXIT=1 | cp 복원 → `cmp` 바이트 동일 확인 |
| M2(r1) | `main()`의 워크리스트 `write_text` 제거(**워크리스트 생성 제거**) | 워크리스트 행 수·존재 단언 red | 관통 1건 + 워크리스트 검사 3건 **FAILED** · EXIT=1 | cp 복원 → `cmp` 바이트 동일 확인 |
| Mut-A(r2) | 검수 큐 **즉시 flush를 종료 일괄 기록으로 변조**(sink 호출을 루프 밖으로) | 계약 ①(중단 시 보존) red | `test_rows_persist_immediately_when_batch_crashes_midway` **FAILED**(크래시 후 큐 0행 — 일괄 기록은 중단 시 전량 유실) · 1 failed, 8 passed · EXIT=1 — 정확히 계약 ①만 변별 | cp 복원 → `cmp` 바이트 동일 확인 |
| Mut-B(r2) | 워크리스트 **렌더를 회차 메모리로 변조**(큐 파일 로드 대신 `report.review_outcomes` 렌더) | 계약 ②③(누적·보존) red | `test_second_run_accumulates_both_runs_in_worklist`·`test_all_accepted_run_does_not_wipe_existing_queue`·재출현 묶음 테스트 **FAILED** · EXIT=1 | cp 복원 → `cmp` 바이트 동일 확인 |

복원 후 재검증: 신규·인접 green(§5). git 계열 원복 미사용(미커밋 구현분 보호 규칙).

## 8. Kiki 머신 라이브 관통 (실 LLM — Phaiakes9)

**사전 브리핑(6항목)**

1. **과제 명칭**: A4 앵커 라이브 생성 관통 — 실 Ollama로 코퍼스 축적 1회차.
2. **목적**: 샌드박스 hermetic 관통(§4)과 동일 배관을 실 LLM으로 구동해, 라이브 수용률·게이트
   반려 분포·genlog·워크리스트가 실제 모델에서 어떻게 나오는지 확보(후속 nightly 상시화의
   기준선 재료).
3. **구체적 절차**: ①브랜치 최신화(1분) ②Ollama 모델 확인(수 초) ③축적 CLI 실행(n=20 기준
   수 분 — 모델 로드 포함) ④자가검증(행 수·exit). 산출물 3파일이
   `data\corpus\problem_bank_llm_live\`에 생긴다(v0·검수 전 — 학생 노출 아님).
4. **성공 기준**: `EXIT=0` + 코퍼스 행 ≥1 + genlog 행 = 20 + worklist 생성. `EXIT=1`이면
   무진전(전건 반려/실패)이며 **그래도 genlog·worklist는 남는다** — worklist 사유가 진단
   재료다(실패 시 대처: worklist 상단 사유를 보고, Ollama 미기동이면 `ollama serve` 후 재실행).
5. **실행 환경**: Windows PowerShell(= Phaiakes9 그 자체 — 별도 접속 불요) ·
   `C:\Users\kiki\Desktop\__AI\WhyMath` · 선행 조건 = Ollama 기동 + `qwen2.5:7b` 설치
   (라우터 저작 결정 실측: LOCAL·GENERAL — §4.1).
6. **창 구분**: 새 PowerShell 창 1개면 충분(장기 점유 프로세스 없음 — CLI는 종료됨).

```powershell
# [실행 시스템] Windows PowerShell (= Phaiakes9 — 별도 접속 불요)
cd C:\Users\kiki\Desktop\__AI\WhyMath

# 0) 이 태스크 브랜치의 신규 코드 확보(재시작 가능 브랜치 규약 — pull 금지·checkout -B)
#    ※ main 머지 후라면 이 두 줄 대신: git checkout main; git pull origin main
git fetch origin
git checkout -B claude/mvp-eos-transition-plan-ghcajm origin/claude/mvp-eos-transition-plan-ghcajm

# 1) 선행 조건 자가검증 — Ollama 기동 + 저작 모델 존재(둘 다 보여야 진행)
ollama list | Select-String "qwen2.5:7b"
curl.exe -s http://127.0.0.1:11434/api/tags | Select-Object -First 1
# (WHYMATH_OLLAMA_HOST는 기본값이 http://127.0.0.1:11434 라 로컬 기동이면 설정 불요)

# 2) A4 앵커 라이브 축적 — 시드 = 실코퍼스 v0 전체(619행 dedup 주입·기존 자산 보호)
python -m whymath_backend.harness.problem_corpus_accumulate `
    --seed data\corpus\problem_bank_generated_v0\problems.jsonl `
    --out data\corpus\problem_bank_llm_live\a4_accumulated.jsonl `
    --n 20 `
    --standard-code "[9수02-20]" `
    --difficulty 2.5 `
    --topic-hint "중3 이차방정식 — 두 근 중 더 큰 근을 구하는 형태(답 하나)"
echo "EXIT=$LASTEXITCODE"

# 3) 자가검증 — 산출물 4종의 실제 행 수(간접 신호 금지: exit 0만으로 판정하지 않기)
Get-Content data\corpus\problem_bank_llm_live\a4_accumulated.jsonl | Measure-Object -Line
Get-Content data\corpus\problem_bank_llm_live\a4_accumulated.genlog.jsonl | Measure-Object -Line
if (Test-Path data\corpus\problem_bank_llm_live\a4_accumulated.review.jsonl) {
  Get-Content data\corpus\problem_bank_llm_live\a4_accumulated.review.jsonl | Measure-Object -Line
} else { echo "review.jsonl 없음 = 이번 회차 비수용 0(전건 수용)" }
Get-Content data\corpus\problem_bank_llm_live\a4_accumulated.worklist.md -TotalCount 6
# 기대: 코퍼스 Lines ≥ 1 · genlog Lines = 20(호출 1건=1행) · review Lines = 비수용 수
#       (리포트 review_outcomes_count와 일치) · worklist 헤더 "누적 행 N"(회차 반복 시 누적 증가)
```

## 9. 후속 태스크 등재 문안 (acceptance ③ — 등재는 메인 세션 CLI로)

미등재 실측 확인: EOS-56=앵커 1급 등록, EOS-59=데이터 등급 라우팅 — 상시화 태스크는 없음.
아래 문안 제안(번호는 `backlog.py add`가 배정):

- **제목**: `anchor-e2e-nightly-golden` — 앵커 E2E 관통 상시화(nightly) + 골든 승격 경로 결선
- **notes 출처**: EOS-58 관통 1회 실증(`docs/reviews/eos_anchor_e2e_a4_2026-08-30.md`)의 상시화
  별항. G1 이후 "관통 1회"가 "관통이 항상 참"으로 유지되게 하는 집행 장치.
- **acceptance 초안**:
  1. **nightly 배선(hermetic 축)** — `tests/backend/harness/test_eos_anchor_e2e_a4.py`가 주기
     실행(CI cron 잡)에 실리고, 배선 실재가 기계로 동결된다(OPS-10
     `test_test_suite_wiring` 선례 — "저장소에 존재함"≠"돌아감"). *정본화≠집행 별항*.
  2. **라이브 회차 리포트(실측 축)** — Phaiakes9 라이브 축적 회차(§8 블록)의 산출물 행 수·
     수용률·outcome 분포가 회차 리포트로 남고, "작동한 비율" 원칙에 따라 생성 대비 수용/반려
     비율이 리포트 필드로 말해진다(정상 exit 0은 증거가 아님).
  3. **골든 승격 경로(사람 게이트 축)** — 라이브 산출 코퍼스가 워크리스트 검수(사람 판정)
     → `review_status` 백필(OPS-24 좌석) → Wilson 게이트(corpus_audit_eval) 통과 시에만
     골든(노출 적격 후보)으로 승격되는 경로를 문서 정본 1곳에 확정하고, 승격 CLI가 그 경로
     밖 승격을 exit 1로 거부한다. 법정 절차 대체 금지 축(사람 검수는 검출기로 측정·대체는
     강등전 경유)을 명기.
  4. **무진전 알람** — nightly 라이브 회차가 연속 N회 exit 1(전건 반려/실패)이면 그 사실이
     사람에게 보인다(fail-open 상시 실패를 "보호 있음"으로 신뢰 금지 규칙의 적용).

## 10. 정직한 공백 (남긴 것·안 한 것 — r2 갱신)

1. **실 LLM 라이브 관통은 이 샌드박스에서 미실행** — 환경 실측(§1) LLM 0. 라이브는 §8 블록으로
   Kiki 소관. 대본 provider의 usage(50/120 토큰·42ms)는 대역 수치다 — 라이브 회차의 토큰·지연은
   실측으로만 채워진다.
2. **`review_status` ③단·해결 추적·승격 집행은 이 관통의 종점 밖** — 신규 append 레코드는
   `review_status` 키가 없어 `l6/_shared.is_review_cleared`가 fail-closed로 노출 차단한다
   (의도된 v0 상태 — 게이트 통과 ≠ 학생 노출). 검수 큐 행의 "해결(체크 완료)" 상태 추적도
   범위 밖(OPS-24 백필·승격 태스크 소관) — 이번 계약은 "큐가 소실되지 않고 본문이 실린다"
   까지다(모듈 docstring 별항 자인).
3. **사이드카 기본 ON은 CLI 동작 변화** — 기존 라이브 사용자는 `<out>.review.jsonl`(비수용
   발생 시)·`<out>.worklist.md` 파일이 생긴다(무해·검수 큐 공급 목적). `problem_corpus_batch`의
   선택 플래그·회차 메모리 뷰는 그대로(다른 물건 — 결정론 전면 재생성 경로).
4. **generation_failed 행의 원시 LLM 응답 발췌는 미탑재** — 원시 출력이 생성기
   (`llm_generator`) 내부에서만 존재하고 orchestrator 밖으로 나오지 않는데, 그 파일은 이번
   수정의 파일대 밖(CUR-09 병행 트리 보호)이다. 큐 행은 실패 사유(reasons)로 정직 기록하고,
   호출별 입력·오류는 genlog(`error_detail`·입력 스냅샷)가 이미 보존한다 — 원시 *출력* 발췌
   결선은 후속(생성기 seam 확장 필요 시 별도 태스크).
5. **`main()`의 provider는 여전히 라이브 전용 조립** — CLI 인자로 provider를 갈아끼우는 좌석은
   추가하지 않았다(기존 설계 유지·hermetic은 `_build_live_generator` 심 경유가 EOS-55 선례).
6. **전체 테스트 스위트 미실행** — 신규·수정 5파일(관통 10 + 큐 단위 22 + 인접 47) green까지
   확인. 전체는 메인 세션·CI 판정 몫.
7. **HIT 라이브 계측은 이 관통 범위 밖** — §6 판단대로 이 구간 0건이 정직하며, 실제 HIT 행은
   검수자가 워크리스트를 소비하는 시점(EOS-54 타이머)에만 생긴다. r2로 큐 행이 문항 본문을
   실으므로 검수자는 워크리스트 항목에서 바로 `start_review(cu_slug=슬러그)`로 착석을 열 수
   있다(조인 키 동일).
8. **큐 파일 동시 실행 격리는 미보장** — 같은 `--out`으로 *동시에* 두 배치를 돌리면 JSONL
   append가 교차할 수 있다(행 단위 원자성은 OS append 시맨틱스 의존). 순차 회차 반복이 이
   CLI의 사용 계약이다(genlog와 동일한 기존 전제 — 신규 제약 아님).

## 11. r2 — codex 리뷰 3건 상환 내역 (PR #914)

### 11.1 세 지적 → 통합 수정 (한 뿌리: 검수 큐의 내구 저장소 부재)

| 지적 | 내용 | 수정 | 동결 테스트 |
|---|---|---|---|
| **P1-1** | needs_review 후보가 어디에도 저장되지 않음 — 워크리스트는 slug·점수·사유뿐, slug는 어떤 레코드로도 해석 불가 → 검수·체크박스·승격이 실사용 불가 | 내구 큐 `<out>.review.jsonl` 신설 — 행에 **후보 payload 전문**(코퍼스 레코드와 동일 직렬화 = 승격 가능 형태) + status·사유·점수·slug·시각·run_id. 워크리스트 항목에 문항·정답·해설·검산 조건 본문 + 행 참조 표기. payload 없는 실패는 사유만 정직 기록 | 계약 ④: 관통 테스트의 큐 행 `candidate_payload["question_text"]` 단언 + 워크리스트 `- 문항:`/`- 정답:` 단언 · 단위 `test_item_carries_candidate_body` |
| **P1-2** | 같은 `--out` 반복 실행마다 워크리스트를 그 회차 outcome으로 **덮어씀** — 이전 미해결 needs_review 소실·전건 수용 회차는 큐를 빈 파일로 교체 | 큐는 **append-only 누적**(행 = 관측·삭제 없음), 워크리스트는 **큐 전체의 렌더 뷰**로 전환 — 회차 간 누적이 기본. 같은 후보 재출현은 payload sha(인스턴스 식별자 `problem_id` 제외 canonical — 실측상 유일한 회차 간 변동 키)로 묶어 출현 횟수 표기 | 계약 ②: `test_second_run_accumulates_both_runs_in_worklist`(2회차 후 양 회차 항목 공존·run_id 2종) · 계약 ③: `test_all_accepted_run_does_not_wipe_existing_queue` · 재출현: `test_same_candidate_reappearance_grouped_with_occurrence_count`(행 2·묶음 1·출현 2회) |
| **P2** | 워크리스트가 배치 완료 후 일괄 기록 — 장기 라이브 배치 중단 시 메모리의 review 기록 전부 소실(genlog는 호출별 flush인데 자기모순) | `run_corpus_accumulate`에 `review_sink` 주입 seam(EOS-55 `generation_log_sink` 심 동형) — 배치 루프 **안**에서 비수용 outcome 발생 즉시 `append_review_queue_jsonl`(open→기록→flush→close). 마크다운 렌더는 사후(뷰) | 계약 ①: `test_rows_persist_immediately_when_batch_crashes_midway`(3회차에 provider 크래시 주입 → 배치 사망·워크리스트 미렌더에도 큐 2행 디스크 실재) |

### 11.2 계약 테스트 4건 + 로더 실패 경로

- 계약 ①~④ = `tests/backend/harness/test_eos_anchor_e2e_a4.py::TestReviewQueueDurability`
  (+ 관통 테스트의 본문 단언) — 전부 실 CLI `main()` 레벨.
- 로더(`load_review_queue_jsonl`)는 EOS-55 `load_generation_logs_jsonl` 동형 — 깨진 행은
  타입명+줄 번호로 수집(값·원문 미출력), 유효 행 생존, 파일 부재는 FileNotFoundError 전파
  (미측정≠0). 로드 실패는 워크리스트 헤더에 `⚠` 노출(조용히 사라지지 않음). 단위 15건 =
  `test_needs_review_worklist.py`의 `TestEntryFromOutcome`·`TestReviewQueueJsonl`·
  `TestRenderReviewQueue`.
- r2 뮤테이션 2건(Mut-A/Mut-B)의 red 변별 = §7.

### 11.3 r2 관통 재실행 실측 (2026-08-31 · 드라이버 전사 발췌)

- run_id `ced2462d…` · exit 0 · outcome 5종 1건씩(§4 전문 갱신됨)
- 산출물: 코퍼스 1행 · genlog 5행(33,044B) · **검수 큐 4행(4,928B — payload 전문 3·사유만 1)**
  · 워크리스트 md 47줄(누적 행 4·항목 4·본문 동반)
