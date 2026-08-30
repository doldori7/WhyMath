# EOS-58 — 깊이앵커 A4 생성 E2E 관통 실증 (2026-08-30)

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
| 관통(acceptance ①) | **완료** — `problem_corpus_accumulate.main()`을 A4 인자로 구동, 시도 5 → 수용 1 저장·비수용 4 워크리스트, exit 0 (§4 전사) |
| 실적재 행 수(acceptance ②) | 코퍼스 **1행** · GenerationLog 사이드카 **5행**(성공 4·실패 1) · 워크리스트 **항목 4**(md 29줄) · 배치 리포트 **1건**(stdout JSON) — 전부 파일을 직접 세어 확인 |
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
      └── <out>.worklist.md              실물 — needs_review_worklist 좌석(이번 배선)
```

### 3.2 변경 파일

| 파일 | 변경 | 판단 근거 |
|---|---|---|
| `src/backend/whymath_backend/harness/problem_corpus_accumulate.py` | ① `AccumulateReport.review_outcomes` 필드(+`to_json`에 카운트) ② `run_corpus_accumulate`가 비수용 outcome 원본 보존(batch 포착 필터와 동일) ③ `default_worklist_path`(`<out>.worklist.md`) ④ `main()`에 `--worklist-out` + **기본 사이드카 기록** | 워크리스트 좌석은 `needs_review_worklist`·batch CLI **기존 실물 미러**(신규 개념 0). **기본 ON**은 같은 CLI의 EOS-55 genlog 선례 그대로("적재가 기본이어야 '경로가 적재한다'가 참·정본화≠집행") — 플래그를 잊으면 검수 큐가 조용히 유실되는 설계 금지. 비수용 0건·무진전(exit 1) 회차에도 기록("관측했고 0건"≠"미기록"·실패 증거 보존 2026-08-22 규칙 ①) |
| `tests/backend/harness/test_eos_anchor_e2e_a4.py` (신규) | 재실행 가능한 A4 관통 통합 테스트 5건 — 실 CLI `main()` 구동·행 수 단언(§5) | E2E 선례(`test_e2e_pedagogy_pilot_integration.py`)의 "실 조립+대역 최소" 구조. provider 좌석 교체는 EOS-55 배선 테스트의 `_build_live_generator` 심 그대로 |
| `docs/reviews/eos_anchor_e2e_a4_2026-08-30.md` (본 문서) | 실측 보고 | — |

**바꾸지 않은 것(의도)**: `problem_corpus_batch`의 `--worklist-out`(선택 플래그 유지 — 스켈레톤
경로는 수율 100% 설계라 비수용이 예외 신호·스코프 밖) · `needs_review_worklist.py`(무수정 —
실물 그대로 소비) · orchestrator·acceptance(무수정 — 게이트는 검증 계약).

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
| 워크리스트 | `a4_accumulated.worklist.md` | **항목 4 / md 29줄** (1,494B) | 헤더 `총 생성 outcome: 5 · 비수용(워크리스트) 4` · `검수필요 1 · 게이트거부 1 · 과유사거부 1 · 생성실패 1` · #1=[needs_review](우선순위 최상단)에 사람 판단 체크박스 3종 |
| 회차 리포트 | stdout JSON | **1건** | 위 전문 |

워크리스트 md 항목부 발췌(전문은 러너 재실행으로 재현):

```
## 1. [needs_review] wm-gen-a4-0ffffe3d6ec1
- 동등성 점수: 1.0000
- 기계 사유:
  - 정확성 미검증 — 답이 여러 실근 중 하나이나 선택(큰 근/작은 근/유일)이 명시되지 않아
    유일하게 확정되지 않음: 근 선택(unique) — 실근이 2개라 답이 유일하게 정해지지 않음
- 사람 판단(검수자 체크):
  - [ ] 교육적으로 타당한 동등문제인가
  - [ ] 수용(코퍼스 편입) / [ ] 반려 / [ ] 임계값 재검토 대상
## 2. [rejected_gate]      — Tier1 답 검산 fail: 잔차 ≠ 0: 8 (SymPy가 오답 5를 거부)
## 3. [rejected_duplicate] — 시드 A4 실문항(wm-skel-d782cf61cf93 · x**2-5*x=0)과 정규형 동일
## 4. [generation_failed]  — 비JSON 응답 파싱 실패(None 폴백)
```

## 5. 검증 결과 (exit code 판정)

cwd `src/backend` · venv `scratchpad/venv312`:

| 검사 | 명령 | 결과 |
|---|---|---|
| ruff | `python -m ruff check . ../../tests/backend` | All checks passed! · **EXIT=0** |
| black | `python -m black --check --line-length 100 . ../../tests/backend` | 1286 files unchanged · **EXIT=0** |
| mypy | `python -m mypy --strict whymath_backend` | no issues in 552 files · **EXIT=0** |
| import-linter | `lint-imports` | 7계층 단방향 KEPT · **EXIT=0** |
| 신규 테스트 | `pytest -c pyproject.toml tests/backend/harness/test_eos_anchor_e2e_a4.py` | **5 passed** · EXIT=0 |
| 인접 테스트 | accumulate·generation_log_wiring·needs_review_worklist·corpus_batch | **56 passed**(전건 재실행 시 37 passed 재확인) · EXIT=0 |

전체 스위트는 돌리지 않았다 — **"전체는 확인하지 못했다"를 명시**한다(메인 세션·CI 몫).

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
| M1 | `acceptance._evaluate_verification` 첫 줄에 `return "verified", reasons` 삽입(**SymPy 게이트 우회**) | 반려 분포 붕괴 → 관통 테스트 red | `test_full_pipe...` **FAILED**(outcome_counts 단언 — 오답·다근이 수용으로 새는 것을 감지) · 1 failed, 4 passed · EXIT=1 | cp 복원 → `cmp` 바이트 동일 확인 |
| M2 | `main()`의 워크리스트 `write_text` 제거(**워크리스트 생성 제거**) | 워크리스트 행 수·존재 단언 red | 관통 1건 + 워크리스트 검사 3건 **FAILED**(4 failed, 1 passed — 생존 1건은 워크리스트를 읽지 않는 리포트 카운트 검사로 정상 생존) · EXIT=1 | cp 복원 → `cmp` 바이트 동일 확인 |

복원 후 재검증: 37 passed·ruff/mypy EXIT=0 (§5). git 계열 원복 미사용(미커밋 구현분 보호 규칙).

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

# 3) 자가검증 — 산출물 3종의 실제 행 수(간접 신호 금지: exit 0만으로 판정하지 않기)
Get-Content data\corpus\problem_bank_llm_live\a4_accumulated.jsonl | Measure-Object -Line
Get-Content data\corpus\problem_bank_llm_live\a4_accumulated.genlog.jsonl | Measure-Object -Line
Get-Content data\corpus\problem_bank_llm_live\a4_accumulated.worklist.md -TotalCount 6
# 기대: 코퍼스 Lines ≥ 1 · genlog Lines = 20(호출 1건=1행) · worklist 헤더에 상태별 카운트
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

## 10. 정직한 공백 (남긴 것·안 한 것)

1. **실 LLM 라이브 관통은 이 샌드박스에서 미실행** — 환경 실측(§1) LLM 0. 라이브는 §8 블록으로
   Kiki 소관. 대본 provider의 usage(50/120 토큰·42ms)는 대역 수치다 — 라이브 회차의 토큰·지연은
   실측으로만 채워진다.
2. **`review_status` ③단은 이 관통의 종점 밖** — 신규 append 레코드는 `review_status` 키가
   없어 `l6/_shared.is_review_cleared`가 fail-closed로 노출 차단한다(의도된 v0 상태 — 게이트
   통과 ≠ 학생 노출). ③단 백필은 OPS-24 좌석·검수 판정 후 소관(§9 승격 경로 초안에 포함).
3. **워크리스트 사이드카 기본 ON은 CLI 동작 변화** — 기존 라이브 사용자는 `<out>.worklist.md`
   파일이 하나 더 생긴다(무해·검수 큐 공급 목적). `problem_corpus_batch`의 선택 플래그는 그대로
   두었다(스코프 밖·수율 100% 설계 경로).
4. **`main()`의 provider는 여전히 라이브 전용 조립** — CLI 인자로 provider를 갈아끼우는 좌석은
   추가하지 않았다(기존 설계 유지·hermetic은 `_build_live_generator` 심 경유가 EOS-55 선례).
5. **전체 테스트 스위트 미실행** — 신규 5 + 인접 4파일 56건 green까지 확인. 전체는 메인
   세션·CI 판정 몫.
6. **HIT 라이브 계측은 이 관통 범위 밖** — §6 판단대로 이 구간 0건이 정직하며, 실제 HIT 행은
   검수자가 워크리스트를 소비하는 시점(EOS-54 타이머)에만 생긴다.
