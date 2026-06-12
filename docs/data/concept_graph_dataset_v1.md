# 와이매스 개념그래프 데이터셋 v1 (자체작성) — 데이터 카드

> **요약**: 한국 2022 개정 교육과정 전 범위(초등~고교 선택)를 덮는 **자체작성 개념그래프**
> 시드. 403 개념 · 541 선수엣지 · 성취기준↔CCSS 코드 매핑 · 113 암기카드 · 13 국제트랙(CCSS전용).
> 본 슬라이스(101)에서는 그중 **오개념 114건을 L4 오개념 카탈로그(22종)와 교차검증**하는 데
> 사용했다(아래 §5). 전체 적재(L1 concept_graph 파이프라인)는 후속 슬라이스 결정 사항.
>
> **2026-06-12 수정본 교체**: 사용자가 원본 입력 오류(절단된 개념명·어미 등)를 바로잡은 수정본
> xlsx로 5개 jsonl + provenance를 *전량 재생성*했다(§1 버전 이력). 개념 401→403·선수엣지
> 540→541·오개념 114→116으로 소폭 증가. §5 교차검증 수치는 *초기 업로드(06-10)* 기준의
> 슬라이스 101 산출물이며 재계산하지 않았다(아래 §5 주석 참조).

---

## 1. 출처·프로비넌스

| 항목 | 값 |
|---|---|
| 형태 | 사용자 업로드 xlsx(수정본·13 시트 중 5종 사용) |
| 업로드일 | 2026-06-12 (수정본) |
| 원본 sha256 | `062695cef261386ec880313631aa349f624fcace1b7eb3d52bc031025536f90d` |
| 저작 | 와이매스 자체작성(교수학 주석) + 공공 표준 *코드* 참조 |
| 추출 산출물 | `data/corpus/concept_graph_v1/*.jsonl` (5종) + `_provenance.json` |

> 원본 xlsx는 **커밋하지 않는다**(§3 redaction 대상 자유텍스트를 포함하므로). 진실 원천은
> redaction을 적용한 jsonl이다. 재추출이 필요하면 동일 sha256 원본을 사용자에게 재요청한다.

### 버전 이력

| 일자 | sha256 | 개념 | 선수엣지 | 비고 |
|---|---|---|---|---|
| 2026-06-10 | `1274533c…8488d1` | 401 | 540 | 최초 업로드 |
| 2026-06-12 | `062695ce…36f90d` | 403 | 541 | **수정본 전량 교체** — 절단 개념명·어미 복원 등 입력 오류 정정(원본 검수보고 시트 기준). 동일 redaction 정책(§3) 적용·재생성 |

---

## 2. 스키마 (시트 → jsonl)

| jsonl | 레코드 | 핵심 필드 |
|---|---|---|
| `concepts.jsonl` | 403 | `src_id`(G01·N1·HK01·J0105·H:…), `name_ko`, `category`, `difficulty_tier`(0~24), `standard_codes`[], `ccss_code`, `metaphor`, **`misconception`**, `accepted_expressions`, `definition_provenance`, `flashcard_count` |
| `prerequisite_edges.jsonl` | 541 | `from_id`, `from_name`, `relation`(선수), `to_id`, `to_name` |
| `standard_ccss_map.jsonl` | 403 | `src_id`, `name_ko`, `standard_code_kr`, `ccss_code` |
| `flashcards.jsonl` | 113 | `grade`(A·…), `category`, `difficulty_tier`, `src_id`, `name_ko`, `front`, `back`, `mnemonic`, `exposure_condition` |
| `ccss_only_intl.jsonl` | 13 | `node_id`, `ccss_code`, `scope`, `kr_adjacent_area`, `kr_interpretation`, `kr_absence_reason` |

> **ID 체계 주의**: 본 데이터의 `src_id`(G01·N1·HK01·J0201·H:12대수01-01 등)는 기존
> concept_graph 파이프라인의 **UC 규약**(`UC.<domain>.<topic>.<slug>`)과 *다르다*. L1 전체
> 적재 시 ID 매핑/재발급이 선행되어야 한다.

---

## 3. 라이선스·안전 (CLAUDE.md 우선순위 #2)

자체작성 교수학 주석(오개념·은유·허용표현·암기카드)과 공공 표준 *코드*(NCIC 성취기준 코드·
CCSS 코드)는 **안전**(자체 코퍼스 + 사실정보). 단, 두 자유텍스트 컬럼은 NCIC/교과서 성취기준
*본문(statement)* 을 근접 복제했을 가능성이 있어 — `concept_graph.md` §1.1 "본문은 어느 필드에도
복제하지 않는다" — **추출 산출물에서 redact**했다:

| redact 필드 | 사유 |
|---|---|
| `concepts.description`(설명) | 성취기준 본문 근접 복제 가능성. `definition_provenance`가 "설명기반 자동파생"임을 명시 → 설명이 원천 텍스트 |
| `concepts.formal_definition`(정식정의) | 교과서 정의 근접 복제 가능성(내부·학생비노출 표기) |
| `intl.ccss_statement_en`(영문 원문) | CCSS 공식 statement — 코드만 보존, 자체 `kr_interpretation`은 유지 |

> redaction 마커: 각 레코드 `_redacted_fields`. policy-guard CI(검정교과서 출판사 패턴)는 통과하나,
> 본 redaction은 그 *너머의 정책*(성취기준 본문 비복제)을 선제 적용한 것이다.

`licensing_safety.md`(한국 자원 표)에 "와이매스 개념그래프 데이터셋 v1(자체작성)" 행으로 등록.

---

## 4. 검수 상태 (적재 전 게이트)

`definition_provenance` 분포 — **289/403이 자동생성·검수필요**(수정본 기준):

| 출처 | 개수 | 적재 가능성 |
|---|---|---|
| 수기 검수 | 114 | 검수 완료 — 우선 적재 후보 |
| 자동(설명기반)·검수필요 | 197 | 전문가 검수 후 |
| 자동 초안·검수필요 | 90 | 전문가 검수 후 |
| 신규 작성(2022 신설)·검수필요 | 2 | 전문가 검수 후 |

오개념(116건)이 채워진 개념은 대부분 "수기 검수"군과 겹쳐 신뢰도가 상대적으로 높다.

---

## 5. 교차검증 — 오개념 114 ↔ L4 카탈로그 22 (본 슬라이스 산출)

> **주석(2026-06-12)**: 이 절의 수치(오개념 114·대응 12종)는 *초기 업로드(2026-06-10)* 기준
> 슬라이스 101 산출물이다. 수정본 교체(§1 버전 이력)로 오개념은 116건으로 늘었으나, §5.2 대응은
> *성취기준 코드* 기준이라 코드가 보존된 한 결론은 유효하다. 전면 재계산은 카탈로그가 30종으로
> 확장된 시점에 별도 슬라이스로 수행한다.

### 5.1 결론
- 데이터셋 오개념은 **각 성취기준 코드에 정착**(curriculum-anchored)되어 있어, 카탈로그
  항목의 *교육과정 근거*를 독립적으로 입증한다.
- 카탈로그 22종 중 **12종이 데이터셋 오개념과 (거의) 정확히 대응** → 카탈로그 정당성 확인.
- 데이터셋에는 카탈로그 미수록의 **고가치 수능·공통 오개념 다수**가 있어 후속 확장 후보가 풍부.

### 5.2 대응(corroboration) — 카탈로그 항목 ↔ 데이터셋 오개념

| 카탈로그 id | 데이터셋(성취기준) 오개념 | 일치 |
|---|---|---|
| `distribution-over-power` | [H:12대수01-03] (a+b)ⁿ≠aⁿ+bⁿ | ◎ |
| `sign-flip-in-inequality` | [J0211] 음수 곱할 때 부등호 방향 그대로 | ◎ |
| `square-root-positivity` | [J0107]·[H:12대수01-01] √(a²)=a (실제 \|a\|) | ◎ |
| `log-distribution` | [H:12대수01-04] log(a+b)=log a+log b | ◎ |
| `gambler-fallacy` | [H:12확통02-01] 앞면 5번→다음 뒷면 차례 | ◎ |
| `prosecutor-fallacy` | [H:12확통02-04] P(A\|B)=P(B\|A) | ◎ |
| `limit-equals-function-value` | [H:12미적Ⅰ01-01] 극한값=함숫값 단정 | ◎ |
| `term-to-zero-implies-convergence` | [H:12미적Ⅱ01-04] 일반항→0 ⇒ 급수 수렴(조화급수) | ◎ |
| `sine-distributes-over-sum` | [H:12미적Ⅱ02-02] sin(a+b)=sin a+sin b | ◎ |
| `dot-product-is-vector` | [H:12기하03-03] 내적 결과를 벡터로(실제 스칼라) | ◎ |
| `period-of-scaled-sine` | [H:12대수02-02] 주기·진폭 혼동 | ○(부분) |
| `similarity-vs-congruence` | [J0312]·[J0304] 닮음비·합동 | ○(부분) |

(◎ 정확 대응 / ○ 부분 대응 — 미대응: division-by-zero·exponent-zero·fraction-cancellation·
area-perimeter-confusion·mean-vs-median·invertibility·chain-rule·product-rule·
geometric-series는 데이터셋 114에 직접 진술이 없음 — 추가 검증·향후 출처 보강 대상.)

### 5.3 신호(signal) 정밀도 평가 → 진단 매칭 정교화 근거
데이터셋의 학생 표기 변이를 보면 카탈로그 `signals`(substring AND)의 두 약점이 드러난다:

1. **거짓음성(공백/표기 변이)**: 학생은 `a²+b²`·`a² + b²`·`a^2+b^2`를 섞어 쓴다. v1 substring은
   공백·유니코드에 민감 → 본 슬라이스에서 `_match_one`에 **NFKC+공백 정규화** 도입(해소).
2. **거짓양성(짧은 공통 토큰)**: `"0"`·`"다음"`·`"모든"` 등은 정답 풀이에도 흔히 등장.
   특히 substring은 *오류의 부재*를 탐지할 수 없어(예: division-by-zero는 "분모≠0" 확인한
   *정답* 풀이도 매칭) 구조적 한계가 있다. → 정본 해법은 **임베딩/LLM-judged 매칭**(doc §매칭
   알고리즘 4단계). 본 슬라이스는 *명백한* 한 건만 정밀화(`invertibility` `"모든"→"모든 함수"`)하고
   나머지 재설계는 pedagogy-designer 검토로 이관(추측 수정 금지).

### 5.4 카탈로그 확장 후보 (미수록·수능/공통 고가치) — 후속 슬라이스
[HK07] 판별식 D<0⇒"해 없음"(허근 무시) · [HK08] 근과 계수 부호 · [HK11] 정의역 제한 최대·최소 ·
[HK14] 연립부등식 교집합↔합집합 · [HK22] 원의 방정식 반지름² · [HK24] 평행이동 부호 ·
[HK35] 합성함수 f∘g=g∘f · [HK41] 순열↔조합 · [HK39] 합·곱의 법칙 · [J0220] ax²=bx 양변 나눠 근 손실 ·
[J0106] 0.999…<1 · [J0315] 피타고라스 비직각 적용 · [H:12미적Ⅰ02-02] 연속⇒미분가능 ·
[H:12미적Ⅰ03-01] 적분상수 +C 누락 · [H:12미적Ⅰ02-07] f′=0⇒극값(변곡점) ·
[H:12확통02-05] 배반↔독립 혼동 · [H:12확통03-07] 신뢰구간 95% 해석 오류.

> 각 항목은 성취기준 코드·반례 구조가 명확해 doc-first(정본 상세화→인코딩) 확장에 적합.

---

## 6. 향후 활용

1. **L1 개념그래프 적재**(대형·후속): src_id→UC 매핑 · 스키마 확장(CCSS·은유·허용표현) ·
   540 선수엣지→`prerequisite` 엣지 · 검수 게이팅(287건).
2. **L4 오개념 확장**(후속): §5.4 후보를 doc-first로 카탈로그에 추가(30종+ 목표).
3. **암기카드**(L6): 113장 — `exposure_condition`("이해 마스터 후 노출")이 메타인지 정책과 정합.
