# 개념(Knowledge) 관리 모듈 — 외부 EOS 틀 대조 **3차 재점검(r3)** (2026-08-11)

> **범위**: 외부 참고 문서 『0단계 — 개념(Knowledge) 관리 모듈』(모듈 6~10: Concept DB ·
> Definition · Theorem · Formula · Knowledge Graph — **WhyMath 전용이 아닌 일반 EOS 틀**,
> Kiki 제공)의 **3차 제출**에 대한 델타 재점검.
> **형식**: `gamification_module_gap_review_r2.md`(동일 문서 재제출 → 델타 전환·v1 in-place 금지)
> 답습.
> **결론**: r1 설계 D1~D5 중 **3건 착지(D3·D4·D5)·2건 의도적 대기(D1·D2)**, r2 `KG-01` 착지.
> 신규 갭은 **도달 렌즈를 개념 축 전체로 확장**해서만 나왔다 — 공식(모듈 9) 축이 write-only(G1),
> D5 리포트가 산출물을 남기지 않음(G2), 정리(모듈 8) 축 스펙 선언 4건이 main에 미배선이고
> **그중 3건은 657커밋 앞선 고립 브랜치에 이미 구현돼 있음**(G3 — 초판 진단 "유령 선언"을
> 자기 정정). 신규 태스크 3건 등재 + r1/r2 stale 정정 6건 보유 + 오판 방지 2건 기록.

**판정 기호**(r1·r2 승계): ✅ 충족 / ⚠️ 진짜 갭 → 태스크 / 🚫 의도적 미채택 / ⏸ 기존 추적 승계 /
△ 재확인·변동 없음.

---

## §0. 재점검 사유 — 왜 r1을 덮어쓰지 않고 r3을 새로 쓰는가

### ① 동일 문서 3차 제출임을 수치로 확정한다 (추론 아님)

첨부 문서가 r1이 대조한 것과 같은 문서임을 인상이 아니라 대조 가능한 값으로 고정한다:

| 축 | 첨부 docx 실측 | r1 §1 기재 | 일치 |
|---|---|---|---|
| 모듈 번호·명 | 6 Concept DB · 7 Definition · 8 Theorem · 9 공식 · 10 Knowledge Graph | 동일 5종 | ✅ |
| 관계 종류 | **11종** — Prerequisite·PartOf·Generalization·Specialization·Equivalent·DependsOn·DerivedFrom·UsedIn·MisconceptionOf·Analogy·Contrast | "문서의 관계 **11종**" + 동일 11행 crosswalk 표 | ✅ |
| 그래프 기능 | **10종** — 선수학습 자동계산·최단 학습경로·개념 영향도·핵심 개념·허브 탐색·오개념 전파·학습경로 생성·AI 설명경로·교수전략 최적화·교육과정 자동검증 | "그래프 기능 **10종** 판정" 표 | ✅ |
| Concept 예시 | `C-ALG-001` / 함수 / Function / 중2 / 2022 개정 / 난이도 3 / `f(x)` | "문서의 `C-ALG-001`형" | ✅ |
| 정의 종류 | 교육과정·수학적·직관적·AI·부모·교사용·대학수준·역사적 | r1 §1 모듈7 행과 동일 | ✅ |

**따라서 모듈 6~10 crosswalk를 처음부터 다시 만들지 않는다.** 그 표는 r1 §1에 있고 유효하다.

### ② 회차 계보 — `_r2` 파일이 없는 이유

| 회차 | 산출물 위치 | 날짜 |
|---|---|---|
| **r1** | `knowledge_module_gap_review.md` **§1~§4** — crosswalk · 의도적 미채택 6건 · 설계 D1~D5 | 2026-07-27 |
| **r2** | **같은 파일 §5** — 도달 관측 렌즈 최초 적용 → `KG-01` (**in-place 추가**) | 2026-08-03 |
| **r3** | 이 파일 (별도 파일) | 2026-08-11 |

r2가 in-place로 §5를 붙인 것은 **2026-08-04 헌법 개정 *이전***이었다. 그 개정("v1은 완료 태스크의
판정 근거 원본이라 in-place 수정 금지 — 정정은 새 문서가 보유", `gamification_module_gap_review_r2.md`
경위)이 착지한 뒤인 지금은 별도 파일이 규칙이다. r1/r2는 이미 **완료 태스크 4건**(`S4-06`·
`ARCH-16`·`ARCH-17`·`KG-01`)의 acceptance 근거로 인용되고 있어 본문을 고치면 그 태스크들의
판정 근거가 사후 변조된다. 그래서 `_r2` 파일은 존재하지 않고 이 파일이 `_r3`이다.

**예외 1건 — r1 파일 최상단에 내비게이션 배너를 추가했다.** 판정·근거·수치는 한 글자도 고치지
않고, "후속 재점검 있음 · stale 6칸 · 현행은 r3" 안내만 붙였다. 근거는
`operations_module_gap_review.md:3`의 선례(v1이 r2를 가리키는 배너)이며, 배너가 없으면 r1을
먼저 읽는 다음 세션이 r3의 존재를 모른 채 stale 판정을 근거로 삼는다 — 이 문서가 막으려는
실패 유형 그 자체다. 게임화 v1은 배너 없이 두었지만(선례 2종 병존), 개념 축은 **같은 갭이 세 번
발견된 이력**이 있어 발견 가능성을 우선한다.

### ③ 승계 선언 — 재판정하지 않는 것

**r1 §2 의도적 미채택 6건 전건 승계**(근거인 CLAUDE.md 협상 불가 조항이 하나도 바뀌지 않았다):

| # | 문서 제안 | 불채택 근거(요약) |
|---|---|---|
| ① | 학년·교육과정을 Concept 노드에 내장 | Curriculum은 Overlay(8대 구조원칙 ⑤) |
| ② | per-row 버전 필드(생성일·수정일·버전) | 버전 정본 = git + 코퍼스 버전 + `_provenance.json` + `review_status` |
| ③ | 교과서/교육과정 정의 인용 · 무검증 자동 정의 생성 | 저작권 절대 금기 · AI 자기승인 금지 |
| ④ | AI 증명 생성(학생 대면) | 검증 권위 · unverifiable 정직 경계 |
| ⑤ | 관계 11종(DependsOn·DerivedFrom·MisconceptionOf·Analogy traversal) | 관계 5~8 상한 · 오개념 독립 DB |
| ⑥ | 공식 변형 관리(변형 노드·변형 비교) | canonical-only 불변식 · 동치는 SymPy 단일 권위 |

이 6건은 **갭이 아니므로 이 문서에서 재론하지 않는다.** 4차 제출이 온다면 그때도 재론 대상이 아니다.

### ④ 이번 회차가 새로 적용하는 렌즈

r1은 **존재 렌즈**(스키마·코드가 있는가), r2는 **도달 렌즈를 개념 API에만** 적용했다.
r3은 그 도달 렌즈를 **개념 축 전체 — 공식·분석 리포트·스펙 선언 — 으로 확장**한다.
같은 문서라도 렌즈가 다르면 다른 갭이 나온다: §2의 G1~G3은 전부 이 확장에서만 나왔고,
존재 렌즈로는 세 건 모두 "있음"으로 읽힌다.

### ⑤ 실측 조건 — 무엇을 확인하지 못했는지 먼저 밝힌다

이 문서의 수치는 전부 **파일시스템·코퍼스 정적 실측**이며 부록에 재현 명령을 병기했다.
관측 리포트 CLI(`concept_reach_report` 등)는 **이 세션 컨테이너에 백엔드 의존성이 없어
(`pydantic` 미설치) 실행하지 못했다** — 대신 그 CLI가 수행하는 grep을 손으로 재현했다.
**DB 라이브 행 수는 미확인**이며, 미확인 축을 추론으로 채우지 않는다(CLAUDE.md "환경 사실의
추론 등재 금지").

---

## §1. r1·r2 설계의 상태 델타 — 바뀐 칸만

| 설계 | 태스크 | r1/r2 당시 | **2026-08-11** | 판정 |
|---|---|---|---|---|
| D1 정의 레지스터(`concept_definition` Overlay) | `S4-05` | 등재 | **todo** — `.py` 0건 | ⏸ §6 |
| D2 Theorem/Proof 페이퍼 설계 | `S4-02` | 설계 확정·코드 0 | **todo** — 테이블 0·시드 0·마이그레이션 0 재확인 | ⏸ §6 |
| D3 Formula `constraints`·`mnemonic` | `S4-06` | 등재 | **done** — `constraints` 15/25 · `mnemonic` 14/25 충전 | ✅ 단 G1 |
| D4 중복 개념 검수 게이트 | `ARCH-16` | 등재 | **done** — CLI + 검수 아티팩트 **3건** | ✅ |
| D5 그래프 분석 리포트 | `ARCH-17` | 등재 | **done** — CLI 실재, 산출 아티팩트 **0** | ⚠️ G2 |
| r2 개념 도달 관측 | `KG-01` | 등재 | **done** — 전용 CI 잡 배선(`ci.yml:652`) | ✅ |

즉 **모듈 6·9·10 축의 r1 설계는 전건 착지**했고, **모듈 7·8(D1·D2)만 남았다.** 남은 이유는
결함이 아니라 의존이며 §6에서 발화 조건을 못 박는다.

---

## §2. 신규 갭 — 실측

### G1 — 공식(모듈 9)이 write-only다: r1은 ✅로 판정했는데 소비처가 0이다 → `KG-03`

r1 §1은 모듈 9를 "대부분 충족"으로 판정하고 D3(`S4-06`)로 필드까지 채웠다. **존재 렌즈로는
정확한 판정이다.** 도달 렌즈로 보면 다르다:

| 실측 | 값 |
|---|---|
| `grep -rn "formula" src/backend/whymath_backend/api/` | **0 hits** — HTTP 표면 없음 |
| `formula_id`가 `l1/formula_graph`·`db/models/formula_node.py` **밖에서** 참조되는 곳 | **1건이며 그것은 주석**(`db/models/__init__.py:254`) |
| `canonical_signature` 충전 | **0/25**(Phase 5b 미착수) |
| `constraints` / `mnemonic` 충전 | 15/25 / 14/25 — 저작은 됐다 |
| 적재기 자기 선언 | `formula_node_projection.py` docstring: *"`dsl`은 이 프로젝션(적재 전용)에선 **write-only**"* |

즉 공식 25건과 그 위에 D3가 얹은 `constraints` 15건·`mnemonic` 14건이 **학생·교사·L2/L4·LLM
어느 경로에도 나가지 않는다.** 저작된 지식 자산이 어떤 표면으로도 나가지 않는 형태는 r2가
`flashcards` 113건에서 이미 잡은 것과 **같은 패턴**이며, 그때 개념 축만 봤기 때문에 공식 축이
빠졌다. CLAUDE.md **"작동 신호 없는 알고리즘 부착 금지 — 작동한 비율"** 대상이다.

**`S4-06`의 사후 판정을 바꾸지 않는다**: 그 태스크의 acceptance는 "필드 추가 + backfill +
canonical-only 불변 유지"였고 전건 충족했다. 갭은 그 태스크의 미이행이 아니라 **acceptance가
소비 축을 묻지 않았다는 것**이다 — 2026-08-04 헌법 개정("①정본화와 ②집행 지점 별항 분리")이
`S4-06` 등재(2026-07-27) *이후*에 생겼다는 시점 사실이 그대로 드러난 사례다.

### G2 — D5(그래프 분석 리포트)가 산출물을 남기지 않아 아무도 본 적이 없다 → `KG-04`

`ARCH-17` acceptance는 소비처를 *"저작·검수 우선순위(ops)"*로 적었다. 실측:

| 축 | 실측 |
|---|---|
| 모듈 | `data_pipeline/graph_analytics/{analytics,__main__}.py` 실재 — `compute_node_metrics`(in/out-degree·`downstream_count`)·`compute_misconception_impacts`(blocking 오개념 하류 도달)·`build_report`·`find_prerequisite_cycle` |
| 테스트 | `tests/data_pipeline/graph_analytics/{test_analytics,test_cli_and_corpus}.py` |
| **산출 아티팩트** | **0** — `docs/data/`에 허브·영향도 리포트 파일 없음 |
| **CI 배선** | **0** — `grep -rn graph_analytics .github/workflows/` 무결과 |
| 참조처 | 자기 테스트 2건 + `MEMORY.md`뿐 |

**대조가 판정을 만든다.** 같은 날 같은 문서에서 나온 D4(`ARCH-16`)는 산출물 3건을 남겼다 —
`docs/data/atom_dedup_candidates_bge_m3.json` · `atom_dedup_review_queue.json` ·
`atom_dedup_review_worksheet.md`. 그래서 D4는 "사람 검수 경로가 실재한다"고 말할 수 있고
D5는 말할 수 없다. 알고리즘은 둘 다 돌지만 **한쪽만 사람에게 도달했다.**

**부수 흡수(별도 태스크 만들지 않음) — 관계 어휘의 실적재 1종**: r1 §1 모듈10 crosswalk는
6개 관계를 "어휘 기존재(적재는 소비처 대기)"로 적었다. 이 표기는 갭 없음처럼 읽히지만 실측은:

| 좌석 | 허용 | 실적재 |
|---|---|---|
| `concept_edge.edge_type`(PG enum) | 6종 | 개념 엣지 **581건 전량 `prerequisite`** |
| 파이프라인 `Relation` | 7종 | 나머지 6종 **0건** |
| `atom_graph` `AtomRelation` | 1종 | 원자 엣지 **2,210건 전량 `prerequisite`** |

어휘 상한(5~8)은 `tests/backend/l1/test_edge_relation_governance.py:72`가 CI로 동결하고 있어
**규칙 위반이 아니다.** 문서 11종 → 어휘 7종 → **실적재 1종**이라는 사실이 crosswalk 표에
안 보이는 것이 문제다. 따라서 신규 태스크가 아니라 **`KG-04` 리포트에 관계 타입별 실적재
분포를 포함**시켜, "어휘 존재"와 "실적재"가 기계 산출물에서 분리 표기되게 한다.

### G3 — 정리(모듈 8) 축 스펙 선언 4건이 main에 미배선 · 그중 3건은 **미병합 고립**이다 → `OPS-29`

r1은 모듈 8을 "의도적 연기 + 설계 공백"으로 **정확히** 판정했다. r3이 발견한 것은 그 판정의
반대편 — **연기된 축을 이미 가리키는 스펙 선언 4건**이며, `origin/main` 기준 구현이 0이다:

| # | 선언 | 위치 | `origin/main` 실측 |
|---|---|---|---|
| ⓐ | `CognitiveType.THEOREM` | `schema/enums.py:603` | 개념 **437건 전량 `cognitive_type: None`** → 정리로 분류된 개념 **0건** |
| ⓑ | `Justification.theorem_concept_ids` | `schemas/v1.1/solution_path.schema.yaml:216` | `src/` 구현 **0건** |
| ⓒ | `lean_verified` | 같은 스키마 `:205` | `src/` 구현 **0건**. `VerificationTier` 실값은 `MACHINE_EXHAUSTIVE`·`MACHINE_SAMPLED` **2종뿐**이며 Lean 대응 값이 없다 |
| ⓓ | `ReasoningType` 폐쇄 7종 | `enums.py:535` | docstring이 명시한 대상 `SolutionStep`이 `src/`·`schemas/`에 **클래스로 없고**, `db/models/`에 `reasoning_type` 컬럼 **0건** |

#### ⚠️ 자기 정정 — 초판 진단("유령 선언 4건")은 부정확했다

이 절의 초판은 위 4건을 "선언만 있고 구현이 없는 유령 참조"로 판정했다. **`origin/main`만 보면
맞지만, 그 판정은 미머지 브랜치를 보지 않은 결과였다.** `backlog.py next` 실행 시 선택기가
`S4-09-solution-path-materialization`을 *"이미 완료(미머지)"*로 제외하는 것을 보고 추적한 결과:

**`origin/claude/whymath-solution-review-40xspg`**(main 대비 **657커밋** 앞섬 · 최종 커밋 12일 전 ·
세션 브리핑의 "미해결 장기 미머지 브랜치 — Kiki 결정 필요" 목록)에 ⓑ·ⓒ·ⓓ가 **이미 구현돼 있다**:

- `l3/solution_path.py:126` `class SolutionStep(BaseModel)` — 클래스 실재
- 같은 파일 `:107` `theorem_concept_ids: list[str]` (ⓑ) · `:179` `lean_verified: bool | None` (ⓒ)
- `schema/problem.py:681` `reasoning_type: ReasoningType | None` — **enum이 필드에 실제 결속**(ⓓ)

정밀 단서: 그 브랜치의 결속은 **Pydantic 계층**이며 `db/models/`의 ORM 컬럼은 **그 브랜치에도
없다**. 그리고 **ⓐ는 그 브랜치에서도 미해소**다(코퍼스 437건 전량 `cognitive_type: None` 동일).

**따라서 정확한 진단은 "선언≠배선"이 아니라 두 겹이다**:

| 겹 | 판정 | 처리 |
|---|---|---|
| (i) **감사기 사각** — `OPS-22`가 YAML 스펙↔코드 축을 보지 않아, main에 스펙만 있고 구현이 0인 상태가 커밋 시점에 발화하지 않는다 | ⚠️ **진짜 갭 · 유효** | → `OPS-29`. 이 사각이 없었으면 main의 미배선이 잡혔을 것이다 |
| (ii) **배선분의 미병합 고립** — ⓑⓒⓓ 구현이 657커밋 앞선 고립 브랜치에 갇혀 있다 | ⏸ **기존 추적** | 이미 "Kiki 결정 필요" 목록에 있는 브랜치 — **신규 등재하지 않고 지목만** 한다 |

**ⓓ에는 추가 위험이 하나 더 있다(이름 충돌 — 고립과 무관하게 main에 실재)**:
`l3/pedagogy/slot_generator.py:102,123`이 payload에 `"reasoning_type": slot_type`을 넣는데
그 값은 `example_pair`·`contrast_case`·`boundary_probe`·`diag_item`(**슬롯 유형**)이고,
`ReasoningType` 7종(`DEDUCTION`·`SUBSTITUTION`·`CASE_SPLIT`·`INDUCTION`·`TRANSFORMATION`·
`HEURISTIC`·`BACKWARD`)과 **교집합이 0**이다. 게다가 `l3/pedagogy/review.py:77`은 이 필드의
**존재만** 검사하고(`missing_reasoning_type`) 값을 폐쇄 enum에 대조하지 않는다. 즉 고립분이
병합되면 **같은 이름의 필드가 두 어휘를 담는 상태**가 된다 — 개명·결속은 `S4-09` 소관이며
`OPS-29`는 이 충돌을 *발화시키는 것*까지만 한다.

**교훈(이 문서가 남기는 것)**: 존재 렌즈로 4건이 다 "있음"으로 보였고, 도달 렌즈로 보니 "main에
0"이었고, **미머지 브랜치까지 보니 3건은 이미 구현돼 있었다.** 스펙↔코드 갭을 판정할 때
`origin/main`만 보면 "미배선"과 "미병합 고립"을 구별할 수 없다 — 진단이 달라지면 처방도 달라진다
(전자는 구현 태스크, 후자는 병합 결정). 이 프로젝트가 등재한 **"미병합 고립"** 반복 실수의
새 형태이며, 발견 경로는 우연이 아니라 **하네스 선택기의 미머지 done 경고**였다.

---

## §3. 정직한 공백 — 이번에 하지 않는 것

- **활성화는 하지 않는다.** `KG-03`·`KG-04`는 **가시화**다. 공식 API 신설·공식 학생 노출·
  허브 리포트를 추천에 물리는 배선은 이 회차 범위가 아니다(NLP-01·REC-01·`KG-01` 동형 경계).
- **D1의 `S3-01` 의존을 해제하지 않는다** (Kiki 확정 2026-08-11). 근거는 §6.
- **r1 본문을 수정하지 않는다.** stale 6건은 §4가 보유한다.
- **코드를 바꾸지 않는다.** 이번 산출물은 문서 + 백로그 등재 + MEMORY 결정 로그다(Kiki 확정).
- **`ReasoningType` 이름 충돌(G3-ⓓ)을 이 회차에서 고치지 않는다.** 개명·enum 결속은
  `S4-09`(SolutionPath/SolutionStep 실체화) 소관이며, `OPS-29`는 **그 사각을 발화시키는
  것까지**만 한다. 감사기가 고치지 않는다는 원칙은 `OPS-22` 자신의 "이 모듈이 하지 않는 것"
  절을 승계한다.
- **고립 브랜치를 병합하지 않는다.** `origin/claude/whymath-solution-review-40xspg`(657커밋 앞섬)에
  갇힌 ⓑⓒⓓ 구현의 회수·병합은 **Kiki 결정 대기 항목**이며 이 회차 범위가 아니다. 이 문서는
  그 브랜치가 **개념/정리 축의 무엇을 들고 있는지 실측으로 지목**하는 것까지만 한다 — 병합
  판단에 필요한 재료를 남기는 것이 목적이다.

---

## §4. r1·r2 stale 정정 — r1을 고치지 않고 r3이 보유

| r1/r2 위치 | 당시 기재 | 2026-08-11 실측 | 원인 |
|---|---|---|---|
| r1 §1 모듈6 "중복 개념 검사 **부재**" | 부재 → D4 | `ARCH-16` **done** — `l1/atom_graph/dedup_candidates.py`(threshold 0.90 · 전수 1,686,366쌍 · p99=0.64) | 그 문서가 낳은 태스크가 해소 |
| r1 §1 모듈9 "`constraints` 필드 **부재**" | 부재 → D3 | `S4-06` **done** — `constraints` 15/25 · `mnemonic` 14/25 | 동일 |
| r1 §1 모듈10 "영향도·허브·오개념 전파 **부재**" | 부재 → D5 | `ARCH-17` **done** — `graph_analytics/` | 동일 |
| r2 §5-1 "Flutter 실호출 `/v1/` **13종**" | 13 | **19종**(유니크 리터럴 · `src/mobile/lib`) | 클라 배선이 늘었다(PATH-05·RPT-01 등). 가드 테스트는 이미 20으로 갱신돼 있어 **문서만 stale** |
| r2 §5-1 "`prerequisites`·`learning-path` 도달 **0**" | 둘 다 0 | **`learning-path`는 도달**(`problems_api.dart` 실호출 · `PATH-05` done). **`prerequisites`는 여전히 0** | 절반 해소 |
| r2 §5-1 "`flashcards` 읽는 API **0개**" | 0 | **0 유지**(재확인 · 코퍼스 113건) | △ 변동 없음 |

**stale의 성질이 서로 다르다**: 앞 3건은 "그 문서가 낳은 태스크가 해소해서 생긴" 건강한 stale
이고, 4번째는 "분모가 자라는데 문서가 안 따라간" 위험한 stale이다. 후자를 리포트가
anchor로 잡게 만든 것이 `KG-01` acceptance②의 설계 의도이며, **실제로 작동했다** — 가드
테스트가 분모 증가를 잡아 갱신됐고 문서만 뒤처졌다. `KG-03`·`KG-04`도 같은 anchor 성질을
갖게 acceptance에 명시한다.

---

## §5. 오판 방지 기록 — 갭처럼 보였으나 의도적 설계였던 2건

이 절은 결론이 아니라 **다음 회차가 같은 오판을 반복하지 않게** 남기는 기록이다.
둘 다 이번 회차에서 "심각한 신규 갭"으로 보고될 뻔했고, 실측이 막았다.

### ① 원자 백본의 필드 이질성 — 두 배치가 정확히 배타적이다

세부개념 원자 1,823건의 필드 충전을 보면 두 집합이 **완벽히 배타적**이다(교집합 0):

| 집합 | 크기 | 보유 필드 | 미보유 |
|---|---|---|---|
| A | 1,311 (71.9%) | `transfer_example`·`atomicity` + concept↔atom crosswalk 도달 | `core_proposition` **0건** |
| B | 512 (28.1%) | `core_proposition` | `transfer_example`·`atomicity`·crosswalk **0건** |

`core_proposition` 충전율 28.1%만 보면 "정의 축 공급 부족"으로 읽힌다. **아니다**:
B의 512건은 **전량 대학 트랙**(`school_level='대학'` — 미적분학 I 61 · 미적분학 II 45 ·
집합과 논리 36 …)이고, `core_proposition`은 **저작권 redaction으로 적재가 구조적 차단된 필드**다
(`l1/atom_graph/__init__.py:14` *"`core_proposition`(대학 핵심명제)을 읽지도 채우지도 않는다
(구조적 차단·코퍼스/검수 보존)"* · `atom_backend_concept.py:13` redaction 우선순위 #2).
K-12(A)와 대학(B)은 애초에 다른 콘텐츠 경로를 쓴다(`concept_content_v1` 437 / `concept_content_
university_v1` 409). **의도적 설계 — 갭 아님.**

### ② 진단·소크라테스 필드가 0인 노드 860건 — 구조 컨테이너다

원자 대장 2,683건 중 860건이 `misconception`·`diagnostic_item`·`socratic`·`standard_codes`를
전부 갖지 않는다. 32.1%가 교수 자산 0으로 보이고, "성취기준 1개 이상 태그" ALWAYS 규칙 위반으로
보인다. **아니다**: 860 = **단원 217 + 소단원 643**이며 `level='세부개념'`이 아니다.
엣지 2,210건은 세부개념 1,823건만 연결한다(단원·소단원의 엣지 참여 **0**). 즉 traversal이
이 860건에 도달하는 일이 없다. **세부개념 1,823건의 4요소 충전율은 100%다.** 갭 아님.

**교훈(두 건 공통)**: 분모를 잘못 잡으면 의도적 설계가 결함으로 보인다. 개념 축 수치를 말할 때
분모는 **2,683(대장 전체)이 아니라 1,823(세부개념)**이고, 필드 축은 **K-12/대학 트랙을 나눠서**
봐야 한다. 이 문서의 모든 수치는 부록 명령으로 분모를 명시한다.

---

## §6. D1·D2 발화 조건 명문화 — 3회 연속 "최대 갭"이나 의도적 대기다

모듈 7(정의 관리)은 r1·r2·r3 **3회 연속 최대 갭**이고, 모듈 8(정리)은 3회 연속 설계 공백이다.
설계(D1·D2)는 r1에서 확정됐고 태스크(`S4-05`·`S4-02`)는 둘 다 `S3-01-pilot-cohort`
(파일럿 5~10명 모집·운영 · **owner=kiki**) 의존으로 `todo`다.

**의존을 유지한다**(Kiki 확정 2026-08-11). 근거:

- `S4-05` 자신의 notes: *"소비처 없는 저작 선행 금지 — 적재·소비 동반 슬라이스로만 착수"*.
  정의 레지스터만 먼저 만들면 **저작 부채 + dead data**다. 이것은 이 저장소가 최소 6회 반복한
  "만들고 입력을 잇지 않음"의 *공급측* 형태다.
- `S3-01`의 착수 트리거 4종은 **전부 충족 시 = 출시 직전**으로 설계돼 있다(⓪`S3-02/03/04` 완료 ✅ /
  ①`S1-11` flip 라이브 / ②`MOB-01` 완료 / ③`S3-02` 라이브 재측정 통과). 조기 착수 금지는
  희소 자원(파일럿 학생) 소진·조기출시 압력 방지가 목적이며 이 문서가 뒤집을 사안이 아니다.

**발화 조건(이 문서가 못 박는 것)** — 다음 중 하나가 성립하면 D1·D2는 대기 해제 대상이다:

1. `S3-01`이 `done`이 된다 (설계된 정상 경로), **또는**
2. `S3-01`과 무관한 소비처가 먼저 실재하게 된다 — 구체적으로 **L4 코치가 레지스터를 선택해
   설명을 바꾸는 경로**(D1) 또는 **학생 대면 증명 학습 표면**(D2)이 다른 태스크로 착지하는 경우.
   이때 D1·D2는 "소비처 없음" 사유를 잃으므로 의존을 재검토한다.

**4차 제출이 온다면**: 모듈 7·8을 "새로 발견한 갭"으로 다시 보고하지 않는다 — 위 두 조건 중
어느 것이 성립했는지만 확인하고, 성립하지 않았으면 △(재확인·변동 없음)으로 처리한다.
r1→r2→r3에서 같은 갭이 세 번 "발견"된 것 자체가 이 명문화가 없었기 때문이다.

---

## §7. 신규 갭 설계 D6~D8

### D6. 공식 축 도달 관측 리포트 (G1 → `KG-03`)

- **좌석**: `src/backend/whymath_backend/harness/formula_reach_report.py` —
  `KG-01`의 `concept_reach_report.py`(dataclass 로더/집계/렌더/JSON/CLI) 구조를 그대로 복제한다.
  빌드타임 결정론(정적 스캔 · DB 0 · LLM 0 · HTTP 0).
- **관측 표면**: ① `formula_node` 읽기 API 좌석 존재 여부(`grep formula api/**/*.py`)
  ② `formula_id`·`FormulaNode`의 자기 모듈 밖 참조 수(주석 제외)
  ③ `constraints`·`mnemonic`·`canonical_signature` 충전/총계 ④ Flutter 클라 소비 참조 수.
- **게이트가 아니다** — 도달 0이어도 exit 1을 내지 않는다(`VIZ-01`·`KG-01` 원칙).
  소비 0은 **"0건 통과"가 아니라 "미도달"**로 표기한다(분모 없는 0 금지).
- **분리 표기 의무**: "저작됐다"(constraints 15/25)와 "도달했다"(0)는 **서로 다른 축**이므로
  리포트에서 별개 필드로 낸다 — `KG-01`이 `reviewed_only` 공집합과 `reach=0`을 분리한 선례.
- **anchor 성질**: 총 공식 수·충전 수를 매 실행 재실측해 문서 stale을 리포트가 잡게 한다(§4 교훈).

### D7. D5 리포트 아티팩트 착지 + 관계 실적재 분포 (G2·G3 부수 → `KG-04`)

- **D4 3-아티팩트 선례 미러**: `graph_analytics`의 `build_report` 산출을 `docs/data/`에
  ① 기계 판독 JSON ② **사람 검수 워크시트 MD**(저작 우선순위 — 허브 상위 N·blocking 오개념
  하류 도달 상위 N)로 남긴다. `atom_dedup_review_worksheet.md`가 형식 선례다.
- **관계 타입별 실적재 분포 추가**: 허용 어휘(백엔드 6 / 파이프라인 7 / 원자 1)와 **실적재 건수**를
  나란히 낸다. 어휘 존재가 충족으로 읽히지 않게 하는 것이 목적이며, 이것으로 r1 crosswalk의
  "어휘 기존재" 표기가 기계 산출물에서 교정된다.
- **CI**: 리포트 생성 자체를 게이트로 걸지 않는다(빌드타임 오프라인 유지). 단 **드리프트 가드**
  (`--check`)는 `OPS-24` 선례를 따라 배선을 검토한다 — 아티팩트가 코퍼스와 어긋나면 red.
- **불변 유지**: LLM 컨텍스트 투입·튜터링 preload 금지(`__main__.py:32` `_NOTICE` 승계).
  전체 그래프 열람은 **오프라인 집계에서만** 허용된다는 r1 D5 판정을 그대로 승계한다.

### D8. 선언≠배선 감사기에 YAML 스펙↔코드 5번째 축 (G3 → `OPS-29`)

- **좌석**: `ops/declared_unwired_audit.py`에 축 (e) 신설 — `schemas/**/*.yaml`이 선언한
  필드·enum 중 `src/` 구현이 0인 것을 열거한다.
- **판정 규약은 기존 것을 그대로 쓴다**(새 대장 파일 만들지 않음): `reached` /
  `by-design:<사유>` / `pending-task:<id>` / 선언 없음 → **unclassified · exit 1**.
  `pending-task`는 `backlog/tasks/<id>.yaml`이 실재하고 `status != done`일 때만 유효하다는
  **그랜드파더 만료 계약**(`ARCH-25` 패턴)도 그대로 상속 — 유예의 조용한 영구화를 차단한다.
- **G3 4건의 예상 귀착**(구현 시 실측으로 확정): ⓑ`theorem_concept_ids`·ⓒ`lean_verified`·
  ⓓ`ReasoningType` → `pending-task:S4-09`(**대장에 실재하고 `status != done`이므로 유예가
  적법하다** — 구현분이 미머지 고립돼 있다는 사실이 곧 그 태스크가 열려 있어야 하는 이유다) /
  ⓐ`CognitiveType.THEOREM` → `by-design:<사유>`(정리 축 자체가 r1 §2-④ 의도적 연기) 또는
  `pending-task:S4-02`. **감사기는 고치지 않는다** — 분류를 강제할 뿐이다.
- **미병합 고립을 미배선으로 오판하지 않게 하는 축**: 이 감사기가 `origin/main`만 보는 정적
  감사라는 사실을 모듈 docstring에 명시한다. main에 구현이 0인 것과 "아무도 구현하지 않은 것"은
  다르다 — G3 자기 정정이 실증한 구별이며, `pending-task` 분류가 바로 그 구별을 담는 슬롯이다.
- **변별력 필수**: 유령 선언 4건이 축 (e)에서 **실제로 발화하는지** 양방향 실측한다. 발화하지
  않으면 축을 추가한 것이 아니라 위장을 추가한 것이다(2026-07-17 "변별력 없는 검증 스텝 금지").
- **CI 실행 여부 확인이 별항**: `OPS-22`가 이미 CI에 배선돼 있으므로 축 추가만으로 돌 것이라
  가정하지 않고 실측한다("저장소에 존재함"과 "돌아감"은 다르다 — OPS-03·OPS-10).

### 등재 요약

| 태스크 | 근거 | track | stage | priority | 성격 |
|---|---|---|---|---|---|
| `KG-03-formula-reach-observability` | G1 | math-completion | S3 | 3 | 가시화(게이트 아님) |
| `KG-04-graph-analytics-artifact-landing` | G2 + G3 부수 | math-completion | S4 | 4 | 아티팩트 + 사람 검수 경로 |
| `OPS-29-yaml-spec-unwired-audit-axis` | G3 | infra-debt | S4 | 3 | 감사기 정밀도 |

**번호 배정 경위(HARN-10 가드 실작동 기록)**: 세 건 모두 `backlog.py add` 경유이며 ID를 수기로
확정하지 않았다. 최초 시도한 `KG-02`·`OPS-26`은 **다른 세션의 원격 브랜치가 이미 점유**하고
있어 가드가 거부했고(`KG-02-concept-content-review-promotion` @ `claude/subject-problems-theory-
check-7n9n72` · `OPS-26-wh1-llm-observability-cache-wiring` @ `claude/whymath-ai-integration-
check-5qqcp4`), CLI가 제안한 번호를 그대로 채택해 `KG-03`·`KG-04`·`OPS-29`가 됐다.
**파일 목록만 눈으로 보고 "다음 번호"를 골랐다면 인플라이트 번호를 못 봐서 충돌했을 것이다** —
2026-07-18/25·07-29에 실제로 발생한 사고 유형이며, 가드가 이번에 그것을 막았다.

선점된 `KG-02`(개념 콘텐츠 검수 승격)는 검수 승격 축이므로 이 문서의 G1~G3과 관심사가 겹치지
않는다 — 다만 §5-① redaction 판정·`review_status=ai_estimated` 축과 인접하므로, 그 태스크가
병합될 때 이 문서 §5를 참조 대상으로 둔다.

**중복 등재 회피**(승계·재등재 안 함): `S4-05`·`S4-02`(§6) · `ARCH-11`(subgraph depth guard·
blocked — `l2/reasoning_subgraph.py` 부재를 `test_llm_subgraph_budget_invariant.py`의 **부재 동결
테스트**가 지킨다) · `PATH-03`(전이 순서 제약 27.0%→69.9% · 학습 경로의 유일한 열린 알고리즘 갭) ·
`PATH-04`(blocked) · `S4-09`(SolutionPath/SolutionStep 실체화 — G3-ⓑⓒⓓ 구현 소유 + 이름 충돌
개명 소관) · **`origin/claude/whymath-solution-review-40xspg`**(657커밋 앞선 고립 브랜치 —
G3-ⓑⓒⓓ 구현 보유 · 병합 결정은 Kiki 대기 항목이며 이 문서는 지목만) ·
Phase 5b `formula_refs` 충전 · chunk 임베딩(D1 착지 트리거) · `S3-28`(QA 게이트
`continue-on-error` 제거 조건 — ci.yml 주석에 만료 조건이 명시된 유예. **대장은 `todo`이나
미머지 done 마커가 있다** — 브리핑 분류상 "이미 포팅됨" 계열이며 고립 여부 판정은 이 문서 범위 밖) ·
성취기준↔Objective 분해 실데이터 0.1%(커리큘럼 Overlay 축 · `curriculum_module_gap_review.md`·
`CUR-02` 소관 · 모듈 6~10 범위 밖) · `problem.schema.yaml` `ActiveConcepts` stale(r2 §5-3 소유 지정).

---

## 부록 — 실측 재현 명령 (2026-08-11 · 리포 루트)

다음 회차가 이 문서의 stale을 **기계로** 잡을 수 있게 모든 수치에 명령을 병기한다.

```bash
# ① Flutter 실호출 /v1/ 유니크 리터럴 = 19 (분모)
grep -rhoE "'/v1/[^']*'" src/mobile/lib --include=*.dart | sort -u | wc -l

# ② 공식 축 도달 = 0 (G1)
grep -rn "formula" src/backend/whymath_backend/api/ | wc -l          # 0
grep -rn "formula_id" src/backend/whymath_backend/ \
  | grep -v "l1/formula_graph\|db/models/formula_node.py"            # 주석 1건만

# ③ D5 리포트 CI 배선 = 0 · 아티팩트 = 0 (G2)
grep -rn "graph_analytics" .github/workflows/ | wc -l                # 0
ls docs/data/ | grep -iE "hub|analytic|impact"                       # 무결과
ls docs/data/ | grep -i dedup                                        # D4는 3건 (대조)

# ④ flashcards 읽기 좌석 = 0 (△ 변동 없음)
grep -rn "flashcards" src/backend/whymath_backend/api/ | wc -l       # 0

# ⑤ 공식 코퍼스 충전율 — constraints 15/25 · mnemonic 14/25 · canonical_signature 0/25
python3 -c "
import json
rows=[json.loads(l) for l in open('data/corpus/formula_graph_v1/formulas.jsonl')]
for f in ['constraints','mnemonic','canonical_signature']:
    print(f, sum(1 for r in rows if r.get(f)), '/', len(rows))"

# ⑥ 관계 타입 실적재 — 개념 581 · 원자 2,210 전량 prerequisite (G2 부수)
python3 -c "
import json, collections
for p in ['concept_graph_v1','atom_graph_v1']:
    e=json.load(open(f'data/corpus/{p}/graph.json'))['edges']
    print(p, len(e), dict(collections.Counter(x.get('relation') for x in e)))"

# ⑦ 스펙 선언 4건 — main 기준 (G3)
python3 -c "
import json, collections
c=json.load(open('data/corpus/concept_graph_v1/graph.json'))['concepts']
print('cognitive_type:', dict(collections.Counter(str(x.get('cognitive_type')) for x in c)))"  # None 437
grep -rn "theorem_concept_ids\|lean_verified" src/ | wc -l           # 0
grep -rn "reasoning_type" src/backend/whymath_backend/db/models/ | wc -l  # 0 (ORM 컬럼 없음)
grep -rn "reasoning_type" src/backend/whymath_backend/l3/pedagogy/  # 슬롯 유형이 흐름 (이름 충돌)

# ⑦-b 고립 브랜치 대조 — **이 단계를 빼면 "미배선"과 "미병합 고립"을 구별할 수 없다** (G3 자기 정정)
B=origin/claude/whymath-solution-review-40xspg
git fetch origin claude/whymath-solution-review-40xspg
git grep -n "class SolutionStep" $B -- src/          # l3/solution_path.py:126 (BaseModel)
git grep -n "theorem_concept_ids\|lean_verified" $B -- src/ | head   # :107 / :179 구현 실재
git grep -n "reasoning_type: ReasoningType" $B -- src/  # schema/problem.py:681 enum 결속
git rev-list --count origin/main..$B                  # 657
git show $B:data/corpus/concept_graph_v1/graph.json | python3 -c "
import json,sys,collections
print(dict(collections.Counter(str(x.get('cognitive_type')) for x in json.load(sys.stdin)['concepts'])))"  # ⓐ는 그 브랜치도 None 437

# ⑧ §5 오판 방지 — 분모를 세부개념 1,823으로 잡아야 한다
python3 -c "
import json, collections
a=json.load(open('data/corpus/atom_graph_v1/graph.json'))['concepts']
print('level:', dict(collections.Counter(x.get('level') for x in a)))  # 세부개념 1823 / 단원 217 / 소단원 643
leaf=[x for x in a if x.get('level')=='세부개념']
for f in ['core_proposition','transfer_example','socratic','standard_codes']:
    print(f, sum(1 for x in leaf if x.get(f)), '/', len(leaf))"
```

**미확인 축(추론 금지)**: DB 라이브 행 수 — 이 컨테이너에 백엔드 의존성이 없어(`pydantic`
미설치) 리포트 CLI·DB 조회를 실행하지 못했다. 위 수치는 전부 코퍼스·소스 정적 실측이다.

### 관련 코드 좌석

- 공식(G1): `data_pipeline/formula_graph/models.py:43` · `db/models/formula_node.py:42` ·
  `l1/formula_graph/formula_node_projection.py`(write-only 자기 선언)
- 그래프 분석(G2): `data_pipeline/graph_analytics/analytics.py`(`compute_node_metrics`·
  `compute_misconception_impacts`·`build_report`·`find_prerequisite_cycle`)
- 관계 어휘(G2 부수): `schema/enums.py:644`(`EdgeType` 6종) ·
  `concept_graph/relation_crosswalk.py:36`(crosswalk·`LOADED_RELATION`) ·
  `tests/backend/l1/test_edge_relation_governance.py:72`(5~8 상한 동결)
- 유령 선언(G3): `schema/enums.py:603,535` · `schemas/v1.1/solution_path.schema.yaml:205,216` ·
  `l3/pedagogy/slot_generator.py:102,123` · `l3/pedagogy/review.py:77` ·
  `ops/declared_unwired_audit.py`(4축 + 판정 규약 + 그랜드파더 만료 계약)
- redaction(§5-①): `l1/atom_graph/__init__.py:14` · `l1/atom_graph/atom_backend_concept.py:13`
- 선례 리포트: `harness/concept_reach_report.py`(`KG-01`) ·
  `l1/atom_graph/dedup_candidates.py`(`ARCH-16`) · `harness/visualization_reach_report.py`(`VIZ-01`)
